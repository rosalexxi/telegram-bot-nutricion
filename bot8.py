
# =============================================================================================================================================
#                                 INICIO                                   CABECERA                                     INICIO
# ==============================================================================================================================================

import os
import re
import io
import json
import base64
import threading
import inspect
import logging
import unicodedata

from datetime import datetime, date, timedelta, time
import pytz
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from groq import Groq
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template_string

# ReportLab para PDF
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler
)

logger = logging.getLogger(__name__)

# Definición de franjas horarias (sin tildes)
FRANJAS_COMIDAS = {
    "Desayuno": (6, 11),
    "Almuerzo": (11, 16),
    "Merienda": (16, 19),
    "Cena": (19, 24)
}

load_dotenv()


GROQ_TEXTO = "openai/gpt-oss-120b"
GROQ_FOTO = "qwen/qwen3.6-27b"
GROQ_AUDIO = "whisper-large-v3"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_SHEETS_KEY_PATH = os.getenv("GOOGLE_SHEETS_KEY_PATH", "credentials.json")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "Registro_Nutricional_Bot")

ARG_TZ = pytz.timezone('America/Argentina/Buenos_Aires')

if GROQ_API_KEY:
    client_ai = Groq(api_key=GROQ_API_KEY)
else:
    client_ai = None

# Helper para conexion a Google Sheets y obtencion / creacion dinamica de pestañas por ID de usuario

def get_user_worksheet(user_id):
    """
    Obtiene o crea una pestaña dinámica 'Comidas_<user_id>' dentro de la planilla.
    """
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    
    sheet_name = f"Comidas_{user_id}"
    
    # Se usa el auxiliar get_or_create_worksheet
    ws = get_or_create_worksheet(sh, sheet_name)
    
    # Si está vacía, se inicializa con los encabezados correspondientes
    if not ws.get_all_values():
        ws.append_row([
            "Código / Nombre", 
            "Descripción", 
            "Peso (g x1000)", 
            "Calorías (x1000)", 
            "Proteínas (g x1000)", 
            "Grasas (g x1000)", 
            "Carbohidratos (g x1000)", 
            "Fibras (g x1000)"
        ])
        
    return ws

# =====================================================================================================================================
#                FINAL                                   CABECERA                                       FINAL
# =====================================================================================================================================

# =====================================================================================================================================
#              INICIO                                  PAGINA WEB    2026 08 19 R 2026 08 20         INICIO
# ======================================================================================================================================

app = Flask(__name__)

def obtener_codigo_unico(ws, codigo_base):
    """
    Lee los códigos existentes en la Columna A de la hoja recibida por parámetro
    y asigna un sufijo numérico incremental si el código ya existe.
    Ejemplo: PIZZA -> PIZZA1 -> PIZZA2
    """
    codigos_existentes = set(ws.col_values(1))
    codigo_limpio = str(codigo_base).strip().upper()
    
    if codigo_limpio not in codigos_existentes:
        return codigo_limpio

    i = 1
    mientras_repetido = f"{codigo_limpio}{i}"
    while mientras_repetido in codigos_existentes:
        i += 1
        mientras_repetido = f"{codigo_limpio}{i}"
        
    return mientras_repetido

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Nutricional - Interfaz Web</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 40px; }
        .container { max-width: 650px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        h1 { color: #2563eb; font-size: 24px; margin-bottom: 8px; }
        p.subtitle { color: #64748b; margin-top: 0; margin-bottom: 24px; font-size: 14px; }
        .status-badge { display: inline-block; background: #dcfce7; color: #166534; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; margin-bottom: 20px; }
        textarea { width: 100%; height: 100px; padding: 12px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; resize: vertical; box-sizing: border-box; }
        textarea:focus { outline: none; border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,0.1); }
        button { background: #2563eb; color: white; border: none; padding: 12px 24px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; margin-top: 12px; transition: background 0.2s; }
        button:hover { background: #1d4ed8; }
        .result-box { margin-top: 24px; background: #f1f5f9; padding: 16px; border-radius: 8px; border-left: 4px solid #2563eb; white-space: pre-wrap; font-size: 14px; }
        .error-box { background: #fee2e2; border-left-color: #dc2626; color: #991b1b; }
        .nav-link { display: inline-block; margin-top: 15px; color: #2563eb; font-size: 14px; text-decoration: none; font-weight: 600; }
        .nav-link:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Bot Nutricional - Consultas AI</h1>
        <p class="subtitle">Desglose instantáneo de nutrientes mediante Inteligencia Artificial.</p>
        <div class="status-badge">● Bot Nutricional activo y funcionando</div>
        
        <form method="POST">
            <label for="comida" style="display:block; font-weight:600; margin-bottom:8px; font-size:14px;">Describí tu comida libre:</label>
            <textarea name="comida" id="comida" placeholder="Ej: BigMac con fritas, coca regular, ensalada césar y helado...">{{ query_text or '' }}</textarea>
            <br>
            <button type="submit">Consultar Nutrientes con IA</button>
        </form>

        {% if resultado %}
            <div class="result-box">
                <strong>Desglose nutricional estimado:</strong><br><br>
                {{ resultado }}
            </div>
        {% elif error %}
            <div class="result-box error-box">
                <strong>Error:</strong> {{ error }}
            </div>
        {% endif %}

        <br>
        <a href="/calculadora{% if user_id %}?user_id={{ user_id }}{% endif %}" class="nav-link">👉 Ir al Generador y Carga de Comidas Precargadas</a>
    </div>
</body>
</html>
"""

HTML_CALCULADORA_RECETAS = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generador de Comidas Precargadas</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 30px; background-color: #f4f6f9; color: #333; }
        .container { max-width: 850px; margin: auto; background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
        h2 { color: #2c3e50; text-align: center; }
        label { font-weight: bold; display: block; margin-top: 15px; margin-bottom: 5px; }
        input[type="text"], input[type="number"], select, textarea { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; }
        textarea { height: 100px; resize: vertical; }
        .row { display: flex; gap: 15px; }
        .col { flex: 1; }
        button { background-color: #27ae60; color: white; padding: 12px; border: none; border-radius: 5px; width: 100%; font-size: 16px; font-weight: bold; cursor: pointer; margin-top: 20px; }
        button:hover { background-color: #219150; }
        #loading { display: none; text-align: center; margin-top: 15px; font-style: italic; color: #7f8c8d; }
        #resultado-section { display: none; margin-top: 25px; border-top: 2px solid #eee; padding-top: 15px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
        th { background-color: #f2f2f2; }
        .btn-save { background-color: #8e44ad; margin-top: 15px; }
        .btn-save:hover { background-color: #71368a; }
        .btn-copy { background-color: #2980b9; margin-top: 10px; }
        .btn-copy:hover { background-color: #1f6391; }
        .nav-link { display: inline-block; margin-bottom: 15px; color: #2980b9; text-decoration: none; font-weight: bold; }
        .user-badge { background: #e0f2fe; color: #0369a1; padding: 6px 12px; border-radius: 6px; font-size: 13px; font-weight: bold; display: inline-block; margin-bottom: 15px; }
        .error-user { background: #fee2e2; color: #991b1b; padding: 10px; border-radius: 6px; margin-bottom: 15px; font-weight: bold; }
    </style>
</head>
<body>

<div class="container">
    <a href="/?user_id={{ user_id }}" class="nav-link">← Volver al Buscador Nutricional</a>
    
    {% if user_id %}
        <div class="user-badge">👤 Usuario conectado: {{ user_id }} (Pestaña: Comidas_{{ user_id }})</div>
    {% else %}
        <div class="error-user">⚠️ Atención: No se ha detectado ID de usuario. Accedé desde el link enviado por Telegram para poder guardar directamente en tu planilla.</div>
    {% endif %}

    <h2>🍳 Generador de Comidas Precargadas</h2>
    
    <div class="row">
        <div class="col" style="flex: 0.4;">
            <label for="codigo">Código / Nombre (Columna A):</label>
            <input type="text" id="codigo" placeholder="Ej: PASCUALINAP" style="text-transform: uppercase;">
        </div>
        <div class="col">
            <label for="descripcion">Descripción de la Comida (Columna B):</label>
            <input type="text" id="descripcion" placeholder="Ej: Porción de pascualina de atún o torta de chocolate">
        </div>
    </div>

    <label for="recetaText">Ingredientes y Cantidades (Receta Completa):</label>
    <textarea id="recetaText" placeholder="Ej:&#10;1 kg de harina&#10;6 huevos&#10;200 g de manteca&#10;300 g de azúcar"></textarea>

    <div class="row">
        <div class="col">
            <label for="tipoCalculo">Criterio de División:</label>
            <select id="tipoCalculo" onchange="toggleCriterio()">
                <option value="porciones">Dividir por cantidad de Porciones</option>
                <option value="gramos">Dividir de a 100 gramos (Fracción fija 100g)</option>
            </select>
        </div>
        <div class="col" id="colPorciones">
            <label for="porciones">Cantidad de Porciones:</label>
            <input type="number" id="porciones" value="1" min="1">
        </div>
    </div>

    <button onclick="calcularReceta()">✨ Calcular Fila con IA</button>

    <div id="loading">🔍 Analizando ingredientes con Groq y calculando proporciones...</div>

    <div id="resultado-section">
        <h3>Fila Generada (Formato Excel x1000)</h3>
        <div style="overflow-x: auto;">
            <table id="tablaNutricional">
                <thead>
                    <tr>
                        <th>Nombre (A)</th>
                        <th>Descripción (B)</th>
                        <th>Peso (C)</th>
                        <th>Calorías (D)</th>
                        <th>Proteínas (E)</th>
                        <th>Grasas (F)</th>
                        <th>Carbohidratos (G)</th>
                        <th>Fibras (H)</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- Fila cargada mediante JS -->
                </tbody>
            </table>
        </div>

        {% if user_id %}
            <button class="btn-save" onclick="guardarEnGoogleSheets()">💾 Guardar Directamente en mi Planilla de Comidas</button>
        {% endif %}
        <button class="btn-copy" onclick="copiarFilaExcel()">📋 Copiar Fila para Pegar Manualmente en Excel</button>
    </div>
</div>

<script>
const currentUserId = "{{ user_id }}";
let ultimoResultadoCalculado = null;

function toggleCriterio() {
    const tipo = document.getElementById('tipoCalculo').value;
    const colPorciones = document.getElementById('colPorciones');
    if (tipo === 'gramos') {
        colPorciones.style.display = 'none';
    } else {
        colPorciones.style.display = 'block';
    }
}

async function calcularReceta() {
    const codigo = document.getElementById('codigo').value.trim();
    const descripcion = document.getElementById('descripcion').value.trim();
    const receta = document.getElementById('recetaText').value.trim();
    const tipoCalculo = document.getElementById('tipoCalculo').value;
    const porciones = document.getElementById('porciones').value;

    if (!codigo || !descripcion || !receta) {
        alert("Por favor completa el código, la descripción y los ingredientes.");
        return;
    }

    document.getElementById('loading').style.display = 'block';
    document.getElementById('resultado-section').style.display = 'none';

    try {
        const response = await fetch('/api/calcular-receta', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                codigo, 
                descripcion, 
                receta, 
                tipoCalculo, 
                porciones: parseInt(porciones || 1) 
            })
        });

        const data = await response.json();
        
        if (response.ok) {
            ultimoResultadoCalculado = data;
            const tbody = document.querySelector('#tablaNutricional tbody');
            tbody.innerHTML = `
                <tr id="filaExcel">
                    <td>${data.nombre}</td>
                    <td>${data.descripcion}</td>
                    <td>${data.peso}</td>
                    <td>${data.calorias}</td>
                    <td>${data.proteinas}</td>
                    <td>${data.grasas}</td>
                    <td>${data.carbohidratos}</td>
                    <td>${data.fibras}</td>
                </tr>
            `;
            document.getElementById('resultado-section').style.display = 'block';
        } else {
            alert("Error al calcular: " + (data.error || "Intente nuevamente."));
        }
    } catch (err) {
        alert("Error de conexión con el servidor.");
    } finally {
        document.getElementById('loading').style.display = 'none';
    }
}

async function guardarEnGoogleSheets() {
    if (!currentUserId) {
        alert("No hay ID de usuario asociado. Accedé mediante el link de Telegram.");
        return;
    }
    if (!ultimoResultadoCalculado) {
        alert("Primero calculá la receta antes de guardar.");
        return;
    }

    try {
        const response = await fetch('/api/guardar-comida', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: currentUserId,
                fila: ultimoResultadoCalculado
            })
        });

        const res = await response.json();
        if (response.ok) {
            // Se actualiza el código en pantalla si cambió por haber un duplicado en el servidor
            if (res.codigo_guardado) {
                ultimoResultadoCalculado.nombre = res.codigo_guardado;
                const tdNombre = document.querySelector('#filaExcel td:first-child');
                if (tdNombre) tdNombre.innerText = res.codigo_guardado;
            }
            alert("✅ ¡Éxito! " + res.message);
        } else {
            alert("❌ Error al guardar en Google Sheets: " + (res.error || "Error desconocido."));
        }
    } catch (e) {
        alert("Error de conexión al intentar guardar en la planilla.");
    }
}

function copiarFilaExcel() {
    const fila = document.getElementById('filaExcel');
    if (!fila) return;
    const celdas = Array.from(fila.querySelectorAll('td')).map(td => td.innerText);
    const textoCopiable = celdas.join('\\t');

    navigator.clipboard.writeText(textoCopiable).then(() => {
        alert("¡Fila copiada! Podés pegarla en tu Excel con Ctrl + V.");
    });
}
</script>

</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def health_check():
    user_id = request.args.get('user_id', '')
    resultado = None
    error = None
    query_text = ""
    if request.method == 'POST':
        query_text = request.form.get('comida', '').strip()
        if query_text:
            try:
                data = analizar_con_groq(query_text)
                items = data.get("items", [])
                res_lines = []
                tot_cal = 0
                tot_prot = 0
                tot_gras = 0
                tot_carb = 0
                tot_fibr = 0
                for it in items:
                    c = parse_raw_val(it.get('calorias', 0))
                    p = parse_raw_val(it.get('proteinas', 0))
                    g = parse_raw_val(it.get('grasas', 0))
                    cb = parse_raw_val(it.get('carbohidratos', 0))
                    f = parse_raw_val(it.get('fibras', 0))
                    tot_cal += c
                    tot_prot += p
                    tot_gras += g
                    tot_carb += cb
                    tot_fibr += f
                    res_lines.append(f"• {it.get('alimento')} ({it.get('peso',0)}g): {c:.1f} kcal | Prot: {p:.1f}g | Gras: {g:.1f}g | Carb: {cb:.1f}g | Fibr: {f:.1f}g")
                
                res_lines.append(f"\n---\nTOTALES: {tot_cal:.1f} kcal | Prot: {tot_prot:.1f}g | Gras: {tot_gras:.1f}g | Carb: {tot_carb:.1f}g | Fibr: {tot_fibr:.1f}g")
                resultado = "\n".join(res_lines)
            except Exception as e:
                error = str(e)
    return render_template_string(HTML_TEMPLATE, resultado=resultado, error=error, query_text=query_text, user_id=user_id)


@app.route('/calculadora', methods=['GET'])
def vista_calculadora():
    """Renderiza la calculadora de recetas recibiendo opcionalmente el user_id por URL."""
    user_id = request.args.get('user_id', '')
    return render_template_string(HTML_CALCULADORA_RECETAS, user_id=user_id)


@app.route('/api/calcular-receta', methods=['POST'])
def api_calcular_receta():
    """Procesa los datos con Groq dividiendo por porciones o por fracción fija de 100g."""
    try:
        if not client_ai:
            return jsonify({"error": "GROQ_API_KEY no está configurada en el servidor."}), 500

        data = request.get_json()
        codigo_nombre = data.get('codigo', '').strip().upper()
        descripcion = data.get('descripcion', '').strip()
        receta = data.get('receta', '').strip()
        tipo_calculo = data.get('tipoCalculo', 'porciones')  # 'porciones' o 'gramos'
        porciones = int(data.get('porciones', 1))

        prompt = f"""
        Actúa como un experto en nutrición. Se te proporciona una receta completa con sus ingredientes y sus cantidades.
        
        Receta: {descripcion}
        Ingredientes y cantidades:
        {receta}
        
        Instrucciones:
        1. Calcula la información nutricional TOTAL de la receta completa (peso total en gramos, calorías, proteínas, grasas, carbohidratos, fibras).
        2. Devuelve los valores numéricos reales en gramos/kcal para el total acumulado de la receta.
        3. Responde ÚNICAMENTE con un objeto JSON válido con la siguiente estructura:
        {{
            "peso_total": número,
            "calorias_total": número,
            "proteinas_total": número,
            "grasas_total": número,
            "carbohidratos_total": número,
            "fibras_total": número
        }}
        """

        chat_completion = client_ai.chat.completions.create(
            messages=[
                {"role": "system", "content": "Sos un asistente nutricional que responde strictly en formato JSON."},
                {"role": "user", "content": prompt}
            ],
            model=GROQ_TEXTO,
            response_format={"type": "json_object"}
        )

        raw_text = chat_completion.choices[0].message.content.strip()
        datos_total = json.loads(raw_text)

        peso_tot = float(datos_total.get('peso_total', 0))
        cal_tot = float(datos_total.get('calorias_total', 0))
        prot_tot = float(datos_total.get('proteinas_total', 0))
        gras_tot = float(datos_total.get('grasas_total', 0))
        carb_tot = float(datos_total.get('carbohidratos_total', 0))
        fibr_tot = float(datos_total.get('fibras_total', 0))

        if tipo_calculo == 'gramos':
            # División a fracción fija de 100g
            factor = 100.0 / peso_tot if peso_tot > 0 else 1.0
            peso_unitario = 100.0
            cal_unitario = cal_tot * factor
            prot_unitario = prot_tot * factor
            gras_unitario = gras_tot * factor
            carb_unitario = carb_tot * factor
            fibr_unitario = fibr_tot * factor
            desc_final = f"{descripcion} porcion 100 g"
        else:
            # División por cantidad de porciones
            div = porciones if porciones > 0 else 1
            peso_unitario = peso_tot / div
            cal_unitario = cal_tot / div
            prot_unitario = prot_tot / div
            gras_unitario = gras_tot / div
            carb_unitario = carb_tot / div
            fibr_unitario = fibr_tot / div
            desc_final = f"{descripcion} porcion {int(round(peso_unitario))} g"

        # Conversión x1000 para compatibilidad exacta con la planilla Excel/Google Sheets (Cols A-H)
        resultado_excel = {
            "nombre": codigo_nombre,
            "descripcion": desc_final,
            "peso": int(round(peso_unitario * 1000)),
            "calorias": int(round(cal_unitario * 1000)),
            "proteinas": int(round(prot_unitario * 1000)),
            "grasas": int(round(gras_unitario * 1000)),
            "carbohidratos": int(round(carb_unitario * 1000)),
            "fibras": int(round(fibr_unitario * 1000))
        }

        return jsonify(resultado_excel), 200

    except Exception as e:
        logger.error(f"Error calculando receta web con Groq: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/guardar-comida', methods=['POST'])
def api_guardar_comida():
    """Guarda la fila calculada en el último lugar libre de la pestaña 'Comidas_<user_id>', verificando que el código sea único."""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        fila = data.get('fila')

        if not user_id or not fila:
            return jsonify({"error": "Faltan parámetros obligatorios (user_id o fila)."}), 400

        ws = get_user_worksheet(user_id)
        
        # Validación de código único
        codigo_original = fila.get('nombre', '')
        codigo_unico = obtener_codigo_unico(ws, codigo_original)

        nueva_fila = [
            codigo_unico,
            fila.get('descripcion', ''),
            fila.get('peso', 0),
            fila.get('calorias', 0),
            fila.get('proteinas', 0),
            fila.get('grasas', 0),
            fila.get('carbohidratos', 0),
            fila.get('fibras', 0)
        ]
        
        ws.append_row(nueva_fila)
        
        msg_extra = f" con el código asignado '{codigo_unico}'" if codigo_unico != codigo_original else ""
        return jsonify({
            "status": "ok", 
            "codigo_guardado": codigo_unico,
            "message": f"Comida agregada en pestaña Comidas_{user_id}{msg_extra}."
        }), 200

    except Exception as e:
        logger.error(f"Error al guardar en Google Sheets: {e}")
        return jsonify({"error": str(e)}), 500


def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# Estados de conversación para Perfil y Fecha personalizada
AWAITING_PROFILE_DATA, AWAITING_CUSTOM_DATE, AWAITING_RESUMEN_MES, AWAITING_EDIT_ITEM = range(4)

# =================================================================================================================================================
#                    FINAL                                   PAGINA WEB                                     FINAL
# ================================================================================================================================================

# =================================================================================================================================================
#                       INICIO                         FUNCIONES AUXILIARES Y FORMATO                       INICIO
# ==================================================================================================================================================

async def log_error(contexto: str, excepcion: Exception, user_id: int = None):
    """
    Función centralizada para registrar errores tanto en la consola de Render como en Google Sheets.
    """
    mensaje_consola = f"Error en [{contexto}]"
    if user_id:
        mensaje_consola += f" - User ID: {user_id}"
    mensaje_consola += f": {excepcion}"

    # 1. Log en consola / Render
    logger.error(mensaje_consola)

    # 2. Log en Google Sheets (pestaña 'Logs')
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        
        ctx_str = f"ERROR | {contexto}" + (f" (User {user_id})" if user_id else "")
        await registrar_log_en_sheet(
            sh=sh, 
            contexto=ctx_str, 
            detalle=str(excepcion)
        )
    except Exception as e_sheet:
        logger.error(f"Fallo secundario: No se pudo escribir el error en Google Sheets: {e_sheet}")


def parse_raw_val(val):
    if val is None or val == "":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip().replace(',', '.')
    try:
        return float(val_str)
    except ValueError:
        return 0.0

def to_sheet_int(val):
    num = parse_raw_val(val)
    return int(round(num * 1000))

def parse_float_from_sheets(val):
    num = parse_raw_val(val)
    return num / 1000.0

def obtener_ahora_arg():
    return datetime.now(ARG_TZ)
    
def obtener_momento_y_fecha_auto():
    ahora = obtener_ahora_arg()
    hora = ahora.time()
    fecha_obj = ahora.date()
    
    if time(0, 0) <= hora < time(2, 0):
        fecha_obj = fecha_obj - timedelta(days=1)
        momento = "Cena"
    elif time(2, 0) <= hora < time(10, 0):
        momento = "Desayuno"
    elif time(10, 0) <= hora < time(12, 0):
        momento = "Colación"
    elif time(12, 0) <= hora < time(15, 0):
        momento = "Almuerzo"
    elif time(15, 0) <= hora < time(20, 0):
        momento = "Merienda"
    else:
        momento = "Cena"
        
    return fecha_obj.strftime("%Y-%m-%d"), momento
    
#               FUNCIÓN CENTRALIZADA: CÁLCULO DE TMB Y GET (Mifflin-St Jeor)  2026 08 22


def calcular_tmb_y_get(peso_actual: float, altura_cm: float, edad: int, genero: str = "masculino", actividad: str = "jubilado", peso_ideal: float = None) -> tuple[float, float]:
    """
    Calcula la Tasa Metabólica Basal (TMB) usando Mifflin-St Jeor y la Tasa de Gasto Energético Total (GET).
    Ajusta dinámicamente según el género y el nivel de actividad u ocupación del usuario.
    
    Retorna: (tmb, get)
    """
    # 1. Ajuste de valores base por seguridad
    peso = float(peso_actual) if peso_actual and peso_actual > 0 else 70.0
    altura = float(altura_cm) if altura_cm and altura_cm > 0 else 170.0
    años = int(edad) if edad and edad > 0 else 40

    # 2. Ecuación de Mifflin-St Jeor según Género
    # Hombres:  (10 * peso) + (6.25 * altura) - (5 * edad) + 5
    # Mujeres:  (10 * peso) + (6.25 * altura) - (5 * edad) - 161
    gen_clean = str(genero).strip().lower()
    if gen_clean in ["femenino", "f", "mujer", "female"]:
        tmb = (10.0 * peso) + (6.25 * altura) - (5.0 * años) - 161.0
    else:
        # Por defecto masculino
        tmb = (10.0 * peso) + (6.25 * altura) - (5.0 * años) + 5.0

    # 3. Mapeo del Factor de Actividad / Ocupación
    # Se normaliza el string de la ocupación para asignar el multiplicador de PAL (Physical Activity Level)
    act_clean = str(actividad).strip().lower()

    if any(k in act_clean for k in ["sedentario", "escritorio", "oficina", "jubilado", "reposo"]):
        factor_actividad = 1.2        # Sedentario / Muy ligera actividad
    elif any(k in act_clean for k in ["ligero", "pie", "docente", "vendedor", "caminar"]):
        factor_actividad = 1.40      # Actividad ligera (1-3 días ejerc. o trabajo de pie)
    elif any(k in act_clean for k in ["moderado", "mozo", "limpieza", "deporte"]):
        factor_actividad = 1.60       # Actividad moderada (3-5 días ejerc. / trabajo activo)
    elif any(k in act_clean for k in ["intenso", "construccion", "atleta", "fuerza"]):
        factor_actividad = 1.75      # Actividad intensa (6-7 días ejerc. pesado)
    elif any(k in act_clean for k in ["muy intenso", "cargador", "alto rendimiento"]):
        factor_actividad = 1.9        # Actividad extrema / trabajo físico muy pesado
    else:
        factor_actividad = 1.40        # Valor por defecto seguro para adultos

    # 4. Cálculo del GET
    get = tmb * factor_actividad

    return tmb, get
    

def obtener_datos_usuario(user_id):
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws = get_or_create_worksheet(sh, f"User_{user_id}")
        records = ws.get_all_records()
        if not records:
            return pd.DataFrame()
        
        df = pd.DataFrame(records)
        col_map = {}
        for c in df.columns:
            c_lower = str(c).lower()
            if 'fecha' in c_lower: col_map[c] = 'Fecha'
            elif 'momento' in c_lower or 'actividad' in c_lower: col_map[c] = 'Momento'
            elif 'alimento' in c_lower or 'detalle' in c_lower: col_map[c] = 'Alimento'
            elif 'peso' in c_lower: col_map[c] = 'Peso'
            elif 'calor' in c_lower: col_map[c] = 'Calorias'
            elif 'prote' in c_lower: col_map[c] = 'Proteinas'
            elif 'grasa' in c_lower: col_map[c] = 'Grasas'
            elif 'hidrat' in c_lower or 'carbo' in c_lower: col_map[c] = 'Carbohidratos'
            elif 'fibra' in c_lower: col_map[c] = 'Fibras'

        df = df.rename(columns=col_map)
        if "Fecha" in df.columns and not df.empty:
            df['Fecha'] = df['Fecha'].astype(str).str.strip()
            for col in ['Peso', 'Calorias', 'Proteinas', 'Grasas', 'Carbohidratos', 'Fibras']:
                if col in df.columns:
                    df[col] = df[col].apply(parse_float_from_sheets)
                else:
                    df[col] = 0.0
        return df
    except Exception as e:
        print(f"Error al obtener datos del usuario {user_id}: {e}")
        return pd.DataFrame()
 
async def mostrar_diario_fecha(query_or_update, user_id, fecha_str):
    df = obtener_datos_usuario(user_id)
    
    if df.empty:
        txt = f"📅 No hay registros ingresados para el usuario `{user_id}`."
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(txt, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(txt, parse_mode="Markdown")
        return

    df_diario = df[df['Fecha'] == fecha_str]
    
    if df_diario.empty:
        txt = f"📅 **Registro del día {fecha_str}:**\n\nNo hay registros guardados para este día."
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(txt, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(txt, parse_mode="Markdown")
        return

    momentos_dict = {}
    for _, row in df_diario.iterrows():
        momento = str(row.get("Momento", "General")).strip()
        concepto = str(row.get("Alimento", "")).strip()
        
        if me := momento.title():
            momento = me

        if momento not in momentos_dict:
            momentos_dict[momento] = []
        if concepto:
            momentos_dict[momento].append(concepto)

    lineas_desglose = []
    for momento, ítems in momentos_dict.items():
        cadena_ítems = ", ".join(ítems)
        lineas_desglose.append(f"• {momento}: {cadena_ítems}")

    tot_cons = df_diario[df_diario['Calorias'] > 0]['Calorias'].sum()
    tot_quem = abs(df_diario[df_diario['Calorias'] < 0]['Calorias'].sum())
    bal_neto = tot_cons - tot_quem

    resumen_msg = (
        f"📅 **Registro del día {fecha_str}:**\n\n"
        + "\n".join(lineas_desglose) + "\n\n"
        f"🖥️ **Consumidas:** {tot_cons:.0f} kcal\n"
        f"🔥 **Quemadas:** {tot_quem:.0f} kcal\n"
        f"⚖️ **Balance Neto:** {bal_neto:.0f} kcal"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Descargar PDF del Diario", callback_data=f"descargar_pdf_diario_{fecha_str}")]
    ])

    if hasattr(query_or_update, 'edit_message_text'):
        await query_or_update.edit_message_text(resumen_msg, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await query_or_update.message.reply_text(resumen_msg, reply_markup=keyboard, parse_mode="Markdown")
        
def obtener_ultimo_peso(user_id: int) -> dict:
    """
    Busca el último registro de peso del usuario en la pestaña 'Usuarios' de Google Sheets.
    Retorna un diccionario con la fecha o None si no lo encuentra.
    """
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        sheet_usuarios = sh.worksheet("Usuarios")
        registros = sheet_usuarios.get_all_records()

        for u in registros:
            raw_id = u.get("User ID")
            if raw_id and str(raw_id).strip() == str(user_id).strip():
                fecha_peso = u.get("Ultimo Mes Peso") or u.get("MES") or u.get("fecha")
                if fecha_peso:
                    return {"fecha": str(fecha_peso).strip()}
                    
        return None
    except Exception as e:
        logger.error(f"Error en obtener_ultimo_peso para User {user_id}: {e}")
        return None


async def _validar_peso_mes_actual(update: Update, context: ContextTypes.DEFAULT_TYPE, funcion_nombre: str) -> bool:
    """
    Verifica si existe un registro de peso para el mes y año en curso.
    Contempla celdas de Google Sheets con formato de fecha (ej: 1/08/2026, 2026-08, etc.).
    """
    user_id = update.effective_user.id
    
    try:
        ultimo_registro = obtener_ultimo_peso(user_id)
    except Exception as e:
        await log_error(f"validar_peso_{funcion_nombre}", e, user_id=user_id)
        ultimo_registro = None

    peso_valido = False
    motivo = "No se encontró ningún registro de peso histórico."

    if ultimo_registro:
        # Obtiene el valor de la fecha probando distintas llaves posibles
        fecha_val = (
            ultimo_registro.get("fecha") or 
            ultimo_registro.get("Ultimo Mes Peso") or 
            ultimo_registro.get("MES") or 
            ""
        )

        fecha_str = str(fecha_val).strip()

        if fecha_str:
            ahora = obtener_ahora_arg()
            
            # Listado de formatos habituales de Google Sheets
            formatos = [
                "%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y",
                "%Y-%m", "%m/%Y", "%Y-%m-%d %H:%M:%S",
                "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M"
            ]

            fecha_dt = None
            
            # 1. Parsear como fecha real
            for fmt in formatos:
                try:
                    fecha_dt = datetime.strptime(fecha_str, fmt)
                    break
                except ValueError:
                    continue

            # 2. Evaluación de coincidencia con el mes y año actuales
            if fecha_dt:
                if fecha_dt.year == ahora.year and fecha_dt.month == ahora.month:
                    peso_valido = True
                else:
                    motivo = f"Tu último registro de peso es de **{fecha_dt.strftime('%m/%Y')}**."
            else:
                # 3. Comparación textual directa por si viene como texto simple (ej: '2026-08')
                mes_str_iso = ahora.strftime("%Y-%m")    # 2026-08
                mes_str_lat = ahora.strftime("%m/%Y")    # 08/2026
                
                if mes_str_iso in fecha_str or mes_str_lat in fecha_str:
                    peso_valido = True

    # Si el peso no está actualizado para el mes en curso, frena la ejecución del comando
    if not peso_valido:
        mensaje = (
            f"⚠️ **Actualización de peso requerida**\n\n"
            f"{motivo}\n\n"
            f"Para poder generar tu **{funcion_nombre}**, es obligatorio contar con el "
            f"registro de peso correspondiente al mes en curso.\n\n"
            f"Por favor, actualizá tu peso utilizando el comando `/peso <valor>` (ejemplo: `/peso 78.5`) "
            f"y volvé a intentarlo."
        )
        await update.message.reply_text(mensaje, parse_mode="Markdown")
        return False

    return True

def calcular_metricas_mensuales(df_mes, perfil_dict):
    """
    Función centralizada global para procesar todos los cálculos mensuales, 
    garantizando 100% de consistencia entre Telegram, PDFs y otros módulos.
    """
    dias_registrados = df_mes['Fecha'].nunique() if (df_mes is not None and not df_mes.empty) else 1
    if dias_registrados == 0:
        dias_registrados = 1

    tot_cons_mes = float(df_mes[df_mes['Calorias'] > 0]['Calorias'].sum()) if df_mes is not None and 'Calorias' in df_mes.columns else 0.0
    tot_quem_mes = float(abs(df_mes[df_mes['Calorias'] < 0]['Calorias'].sum())) if df_mes is not None and 'Calorias' in df_mes.columns else 0.0

    prom_cons = tot_cons_mes / dias_registrados
    prom_quem = tot_quem_mes / dias_registrados
    prom_bal_neto = prom_cons - prom_quem

    tot_prot = float(df_mes['Proteinas'].sum()) if df_mes is not None and 'Proteinas' in df_mes.columns else 0.0
    tot_gras = float(df_mes['Grasas'].sum()) if df_mes is not None and 'Grasas' in df_mes.columns else 0.0
    tot_carb = float(df_mes['Carbohidratos'].sum()) if df_mes is not None and 'Carbohidratos' in df_mes.columns else 0.0
    tot_fibr = float(df_mes['Fibras'].sum()) if df_mes is not None and 'Fibras' in df_mes.columns else 0.0

    prom_cal = int(round(prom_cons))
    prom_prot = int(round(tot_prot / dias_registrados))
    prom_gras = int(round(tot_gras / dias_registrados))
    prom_carb = int(round(tot_carb / dias_registrados))
    prom_fibr = int(round(tot_fibr / dias_registrados))

    perfil_dict = perfil_dict if isinstance(perfil_dict, dict) else {}
    
    def get_perfil_num(key_list, default):
        for k in key_list:
            if k in perfil_dict and perfil_dict[k] is not None:
                val = parse_raw_val(perfil_dict[k])
                if val != 0.0:
                    return val
        return default

    edad = int(get_perfil_num(['Edad', 'edad'], 64))
    altura = get_perfil_num(['Altura', 'altura'], 167.0)
    peso_actual = get_perfil_num(['Peso', 'peso'], 108.5)
    peso_ideal = get_perfil_num(['Peso_ideal', 'peso_ideal', 'Peso Ideal'], 75.0)
    
    genero = str(perfil_dict.get('GENERO') or perfil_dict.get('Genero') or perfil_dict.get('genero', 'masculino')).strip()
    ocupacion = str(perfil_dict.get('Ocupacion') or perfil_dict.get('ocupacion') or perfil_dict.get('actividad', 'jubilado')).strip()

    peso_referencia = (peso_actual * 0.75) + (peso_ideal * 0.25)

    _, get_real = calcular_tmb_y_get(
        peso_actual=peso_actual, altura_cm=altura, edad=edad, genero=genero, actividad=ocupacion, peso_ideal=peso_ideal
    )
    _, get_meta = calcular_tmb_y_get(
        peso_actual=peso_referencia, altura_cm=altura, edad=edad, genero=genero, actividad=ocupacion, peso_ideal=peso_ideal
    )

    deficit_diario_real = get_meta - prom_bal_neto
    cambio_peso_kg = -(deficit_diario_real * dias_registrados) / 7700.0

    gen_clean = genero.lower()
    if gen_clean in ["femenino", "f", "mujer", "female"]:
        factor_proteina = 1.2
        ideal_fibr = 25
    else:
        factor_proteina = 1.5
        ideal_fibr = 30

    ideal_cal = int(round(get_meta))
    ideal_prot = int(round(peso_referencia * factor_proteina))
    ideal_gras = int(round((get_meta * 0.25) / 9.0))
    ideal_carb = int(round((get_meta * 0.50) / 4.0))

    return {
        "dias_registrados": dias_registrados,
        "prom_cal": prom_cal,
        "prom_quem": int(round(prom_quem)),
        "prom_bal_neto": int(round(prom_bal_neto)),
        "prom_prot": prom_prot,
        "prom_gras": prom_gras,
        "prom_carb": prom_carb,
        "prom_fibr": prom_fibr,
        "ideal_cal": ideal_cal,
        "ideal_prot": ideal_prot,
        "ideal_gras": ideal_gras,
        "ideal_carb": ideal_carb,
        "ideal_fibr": ideal_fibr,
        "peso_actual": int(round(peso_actual)),
        "peso_ideal": int(round(peso_ideal)),
        "peso_referencia": int(round(peso_referencia)),
        "altura": int(round(altura)),
        "edad": edad,
        "get_meta": get_meta,
        "deficit_diario_real": int(round(deficit_diario_real)),
        "cambio_peso_kg": cambio_peso_kg,
        "tot_cons": tot_cons_mes,
        "tot_quem": tot_quem_mes,
        "tot_prot": tot_prot,
        "tot_gras": tot_gras,
        "tot_carb": tot_carb,
        "tot_fibr": tot_fibr
    }
    
# =====================================================================================================================================================================
#                FINAL                        FUNCIONES AUXILIARES Y FORMATO                                      FINAL
# =====================================================================================================================================================================
   
# ======================================================================================================================================================================
#                 INICIO                           GOOGLE SHEETS OPERACIONES                                      INICIO
# ======================================================================================================================================================================

def get_gspread_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if os.path.exists(GOOGLE_SHEETS_KEY_PATH):
        creds = Credentials.from_service_account_file(GOOGLE_SHEETS_KEY_PATH, scopes=scopes)
    else:
        creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if creds_json:
            info = json.loads(creds_json)
            creds = Credentials.from_service_account_info(info, scopes=scopes)
        else:
            raise Exception("No se encontraron credenciales de Google Sheets.")
    return gspread.authorize(creds)

def get_or_create_worksheet(spreadsheet, title):
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        if title.startswith("User_"):
            ws = spreadsheet.add_worksheet(title=title, rows="1000", cols="10")
            ws.append_row(["Fecha", "Momento/Actividad", "Alimento/Detalle", "Peso (g)", "Calorías (kcal)", "Proteínas (g)", "Grasas (g)", "Hidratos (g)", "Fibras (g)"])
            return ws
        elif title.startswith("Presion_"):
            ws = spreadsheet.add_worksheet(title=title, rows="500", cols="6")
            ws.append_row(["Fecha_Hora", "Fecha_Dia", "Alta", "Baja", "Pulsaciones", "Nota"])
            return ws
        elif title.startswith("Perfil_"):
            ws = spreadsheet.add_worksheet(title=title, rows="100", cols="7")
            ws.append_row(["EDAD", "PESO", "ALTURA", "GENERO", "OCUPACION", "MES", "Fecha_Actualizacion"])
            return ws
        elif title == "Plantillas_Comidas":
            ws = spreadsheet.add_worksheet(title=title, rows="100", cols="8")
            ws.append_row(["Nombre", "Descripcion", "Peso", "Calorias", "Proteinas", "Grasas", "Carbohidratos", "Fibras"])
            return ws
        else:
            return spreadsheet.add_worksheet(title=title, rows="200", cols="10")

def guardar_en_sheets(user_id, items, fecha, momento, tipo="Comida"):
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    ws = get_or_create_worksheet(sh, f"User_{user_id}")

    rows = []
    for item in items:
        rows.append([
            str(fecha),
            str(momento),
            item.get("alimento", "Desconocido"),
            to_sheet_int(item.get("peso", 0)),
            to_sheet_int(item.get("calorias", 0)),
            to_sheet_int(item.get("proteinas", 0)),
            to_sheet_int(item.get("grasas", 0)),
            to_sheet_int(item.get("carbohidratos", 0)),
            to_sheet_int(item.get("fibras", 0))
        ])
    if rows:
        ws.append_rows(rows)
        
# =======================================================================================================================================================
#                    FINAL                              GOOGLE SHEETS OPERACIONES                      FINAL
# =======================================================================================================================================================

# =====================================================================================================================================================
#                  INICIO                        INTERFAZ Y RENDER DE CONFIRMACIÓN                      INICIO
# ======================================================================================================================================================

async def render_confirmation_screen(msg_or_query, context):
    items = context.user_data.get('pending_items', [])
    fecha = context.user_data.get('pending_fecha', obtener_ahora_arg().strftime("%Y-%m-%d"))
    momento = context.user_data.get('pending_momento', 'Comida')

    # Cambia el título si es una actividad
    if momento == 'Actividad':
        txt = f"📝 **Registro de Actividad:**\n📅 Fecha: `{fecha}`\n\n"
    else:
        txt = f"📝 **Confirmación de Ingesta:**\n📅 Fecha: `{fecha}` | Momento: `{momento}`\n\n"

    for idx, item in enumerate(items, start=1):
        peso_total = item.get('peso', 0)
        cal_total = item.get('calorias', 0)
        
        # Si la plantilla ya tiene display limpio configurado, lo usamos; si no, limpiamos el §
        alimento_str = item.get('alimento_display') or item.get('alimento', item.get('nombre', ''))
        alimento_limpio = alimento_str.replace('§', '').strip()

        if momento == 'Actividad':
            txt += f"**{idx}. {alimento_limpio}**: `{cal_total:.1f} kcal`\n"
        else:
            # Mostramos el texto limpio una sola vez (ya incluye el (x...) si era plantilla)
            txt += f"**{idx}. {alimento_limpio}** ({peso_total:.1f}g): `{cal_total:.1f} kcal`\n"

    keyboard = []
    
    # SOLO agrega la fila de Desayuno/Almuerzo/Merienda/Cena si NO es Actividad
    if momento != 'Actividad':
        m_buttons = []
        for m in ["Desayuno", "Almuerzo", "Merienda", "Cena"]:
            mark = "✅ " if m.lower() == momento.lower() else ""
            m_buttons.append(InlineKeyboardButton(f"{mark}{m}", callback_data=f"set_m_{m}"))
        keyboard.append(m_buttons)

    es_plantilla = any('§' in item.get('alimento', item.get('nombre', '')) for item in items)

    if not es_plantilla:
        for idx, item in enumerate(items, start=1):
            nombre_corto = item.get('alimento', item.get('nombre', ''))[:10]
            keyboard.append([
                InlineKeyboardButton(f"#{idx} {nombre_corto}", callback_data=f"noop_{idx}"),
                InlineKeyboardButton("✏️ Editar", callback_data=f"edit_item_{idx}"),
                InlineKeyboardButton("❌ Anular", callback_data=f"del_item_{idx}")
            ])

    hoy_str = obtener_ahora_arg().strftime("%Y-%m-%d")
    ayer_str = (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d")
    mark_hoy = "✅ " if fecha == hoy_str else ""
    mark_ayer = "✅ " if fecha == ayer_str else ""
    mark_otro = "✅ " if fecha not in [hoy_str, ayer_str] else ""

    keyboard.append([
        InlineKeyboardButton(f"{mark_hoy}Hoy", callback_data="set_d_hoy"),
        InlineKeyboardButton(f"{mark_ayer}Ayer", callback_data="set_d_ayer"),
        InlineKeyboardButton(f"{mark_otro}Otro Día", callback_data="set_d_otro")
    ])

    keyboard.append([
        InlineKeyboardButton("🗑️ ELIMINAR TODO", callback_data="cancel_entry"),
        InlineKeyboardButton("💾 GUARDAR", callback_data="confirm_save")
    ])

    markup = InlineKeyboardMarkup(keyboard)

    if hasattr(msg_or_query, 'edit_message_text'):
        await msg_or_query.edit_message_text(txt, reply_markup=markup, parse_mode="Markdown")
    elif hasattr(msg_or_query, 'edit_text'):
        await msg_or_query.edit_text(txt, reply_markup=markup, parse_mode="Markdown")
    else:
        msg_id = context.user_data.get('last_menu_msg_id')
        chat_id = msg_or_query.effective_chat.id if hasattr(msg_or_query, 'effective_chat') else None
        
        editado = False
        if msg_id and chat_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=txt,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
                editado = True
            except Exception:
                editado = False

        if not editado and hasattr(msg_or_query, 'message') and msg_or_query.message:
            nuevo_msg = await msg_or_query.message.reply_text(txt, reply_markup=markup, parse_mode="Markdown")
            context.user_data['last_menu_msg_id'] = nuevo_msg.message_id

async def procesar_y_mostrar_confirmacion(data_json, msg_obj, context):
    items = data_json.get("items", [])
    if not items:
        await msg_obj.edit_text("❌ No se pudieron detectar alimentos en la consulta.")
        return

    fecha, momento = obtener_momento_y_fecha_auto()
    context.user_data['pending_items'] = items
    context.user_data['pending_fecha'] = fecha
    context.user_data['pending_momento'] = momento

    await render_confirmation_screen(msg_obj, context)
    
# =====================================================================================================================================================
#                  FINAL                        INTERFAZ Y RENDER DE CONFIRMACIÓN                      FINAL
# ======================================================================================================================================================

# ========================================================================================================================================================
#                 INICIO                            COMANDO START                               INICIO
# =======================================================================================================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 ¡Hola! Bienvenido a tu Bot Nutricional Personalizado.\n\n"
        "📌 Funciones y Comandos Disponibles:\n\n"
        "• `/comidas`: Visualiza listado y descarga PDF.\n"
        "• `/presion 120,80,70,Nota` registra datos y nota.\n"
        "• `/presion 120,80` omite pulso y nota.\n"
        "• `/presion 2026-08` promedio mensual y PDF.\n"
        "• `/diario`: Ingestas del día y PDF detallado.\n"
        "• `/resumen`: Reporte mensual con IA y PDF.\n"
        "• `/receta`: Carga con IA una comida en planilla.\n"
        "• `/perfil`: Consulta datos biométricos.\n"
        "• `/perfil 90 `: Actualiza el peso del mes.\n\n"
        "📌 Ingreso de ingestas y actividad:\n\n"
        "• **Comidas del listado precargado:**\n"
        "  `*PIZZAJM` ingresa una unidad de la comida.\n"
        "  `*PIZZAJM,1.5` o `*CHURRO,6` ingresa la cantidad.\n\n"
        "• **Ingreso de comidas por IA:**\n"
        "  Texto, Imagen, Voz (descripción, cantidad o peso).\n"
        "• **Modificación:**\n"
        "  Ingresar `COMIDA` se conserva el peso y vuelve a la IA.\n"
        "  Ingresar `COMIDA,PESO` nuevos valores vuelve a la IA.\n\n"
        "• **Actividades fisicas:**\n"
        "  `*# minutos actividad, calorias` graba datos .\n\n"
        "📄 Te adjuntamos el manual de instrucciones actualizado en PDF."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
    pdf_buf = generar_pdf_instrucciones_bytes()
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=pdf_buf,
        filename="Manual_Bot_Nutricional.pdf"
    )

def generar_pdf_instrucciones_bytes():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    PRIMARY = colors.HexColor('#0F172A')
    SECONDARY = colors.HexColor('#2563EB')
    TEXT_COLOR = colors.HexColor('#334155')
    BG_LIGHT = colors.HexColor('#F8FAFC')
    BORDER_COLOR = colors.HexColor('#E2E8F0')

    title_style = ParagraphStyle('ModernTitle', parent=styles['Heading1'], fontSize=18, leading=22, textColor=PRIMARY, spaceAfter=4)
    subtitle_style = ParagraphStyle('ModernSubtitle', parent=styles['Normal'], fontSize=10, leading=14, textColor=SECONDARY, spaceAfter=15)
    section_style = ParagraphStyle('ModernSection', parent=styles['Heading2'], fontSize=12, leading=16, textColor=PRIMARY, spaceBefore=12, spaceAfter=6)
    body_style = ParagraphStyle('ModernBody', parent=styles['Normal'], fontSize=9, leading=14, textColor=TEXT_COLOR)
    
    story = []

    header_data = [
        [Paragraph("🤖 Guía Interactiva del Bot Nutricional", title_style)],
        [Paragraph("MANUAL DE USUARIO • ASISTENTE PERSONAL INTELIGENTE", subtitle_style)]
    ]
    header_table = Table(header_data, colWidths=[532])
    header_table.setStyle(TableStyle([
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('LINEBELOW', (0,1), (-1,1), 2, SECONDARY),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("1. Comandos Principales", section_style))
    
    cmds_data = [
        [Paragraph("<b>/start</b>", body_style), Paragraph("Inicia el bot y reenvía este manual informativo actualizado.", body_style)],
        [Paragraph("<b>/comidas</b>", body_style), Paragraph("Visualiza el listado de comidas predeterminadas y descarga su plantilla en PDF.", body_style)],
        [Paragraph("<b>/presion</b>", body_style), Paragraph("Registra valores (Ej: <code>120,80,70</code>) o consulta el resumen mensual de presión (Ej: <code>2026-08</code>).", body_style)],
        [Paragraph("<b>/diario</b>", body_style), Paragraph("Consulta los consumos del día con agrupamiento inteligente y descarga de PDF detallado.", body_style)],
        [Paragraph("<b>/resumen</b>", body_style), Paragraph("Obtiene el reporte mensual con tabla comparativa de macronutrientes y recomendaciones de IA.", body_style)],
        [Paragraph("<b>/perfil</b>", body_style), Paragraph("Consulta o actualiza tus datos biométricos corporales específicos por mes.", body_style)],
    ]
    
    t_cmds = Table(cmds_data, colWidths=[90, 442])
    t_cmds.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_cmds)
    story.append(Spacer(1, 10))

    story.append(Paragraph("2. Métodos de Registro y Multiplicadores", section_style))
    
    input_data = [
        [Paragraph("<b>💬 Texto Libre y Plantillas:</b> Podés escribir tus alimentos de forma natural o utilizar plantillas rápidas con multiplicadores de porción directamente (Ej: <code>*PIZZAJM,4</code> o <code>*CHURRO,0.5</code>).", body_style)],
        [Paragraph("<b>🎤 Notas de Voz:</b> Grabá un audio dictando lo que comiste; el motor de transcripción procesará los datos automáticamente.", body_style)],
        [Paragraph("<b>📸 Fotografías:</b> Enviá una foto de tu plato para que la inteligencia artificial analice los componentes y calcule los macronutrientes.", body_style)]
    ]
    
    t_inputs = Table(input_data, colWidths=[532])
    t_inputs.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('LINEBELOW', (0,0), (-1,-2), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(KeepTogether([t_inputs]))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ==============================================================================================================================================
#                 FINAL                            COMANDO START                               FINAL
# ==============================================================================================================================================

# ==============================================================================================================================================
#               INICIO                    COMANDO RESUMEN     2026 08 23                        INICIO
# ==============================================================================================================================================

async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Manejador del comando /resumen.
    Muestra el menú de selección de mes solo si el peso del mes en curso está al día.
    """
    if not await _validar_peso_mes_actual(update, context, funcion_nombre="resumen"):
        return

    ahora = obtener_ahora_arg()
    mes_actual = ahora.strftime("%Y-%m")
    mes_anterior = (ahora.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Mes Actual", callback_data=f"resumen_mes_{mes_actual}")],
        [InlineKeyboardButton("📆 Mes Anterior", callback_data=f"resumen_mes_{mes_anterior}")],
        [InlineKeyboardButton("🗓️ Otro Mes", callback_data="resumen_mes_otro")]
    ])

    await update.message.reply_text(
        "📊 **Resumen Mensual:** Seleccioná la opción que querés consultar:", 
        reply_markup=keyboard, 
        parse_mode="Markdown"
    )


#                                                        RECOMENDACIÓN EXTENSA PARA PDF (~500 - 600 PALABRAS)
# ================================================================================================================================================================

def generar_recomendacion_ia(promedios: dict, metas: dict, biometria: dict = None) -> str:
    """
    Genera un informe nutricional detallado y extenso (~500-600 palabras)
    con diagnóstico integral, alimentos a incorporar y alimentos a evitar.
    """
    if biometria is None:
        biometria = {}

    peso_act = int(round(biometria.get('peso_actual', 0)))
    peso_id = int(round(biometria.get('peso_ideal', 0)))
    
    cal_r, cal_m = int(round(promedios.get('calorias', 0))), int(round(metas.get('calorias', 2000)))
    prot_r, prot_m = int(round(promedios.get('proteinas', 0))), int(round(metas.get('proteinas', 100)))
    gras_r, gras_m = int(round(promedios.get('grasas', 0))), int(round(metas.get('grasas', 55)))
    carb_r, carb_m = int(round(promedios.get('carbohidratos', 0))), int(round(metas.get('carbohidratos', 200)))
    fibr_r, fibr_m = int(round(promedios.get('fibras', 0))), int(round(metas.get('fibras', 25)))

    bloques = []

    # Seccion 1: Diagnostico
    bloques.append(
        "<b>1. DIAGNÓSTICO NUTRICIONAL INTEGRAL DEL MES</b>\n"
        f"Tras analizar minuciosamente tus registros diarios frente a los requerimientos teóricos calculados para tu perfil, "
        f"se observan tendencias clave en tu patron de alimentacion. En cuanto al balance energetico, registras un promedio "
        f"de <b>{cal_r} kcal/dia</b> frente a un objetivo de <b>{cal_m} kcal/dia</b>. "
        f"Al evaluar la distribucion de macronutrientes, tu ingesta proteica promedia <b>{prot_r}g</b> (meta: {prot_m}g), "
        f"las grasas alcanzan <b>{gras_r}g</b> (meta: {gras_m}g), los carbohidratos se ubican en <b>{carb_r}g</b> "
        f"(meta: {carb_m}g) y la fibra aporta <b>{fibr_r}g</b> (meta: {fibr_m}g). "
        f"Este perfil refleja desvíos específicos que requieren ajustes estratégicos para optimizar el metabolismo, mejorar la composición "
        f"corporal de forma progresiva y asegurar la saciedad sin comprometer el nivel de energía diario."
    )

    # Seccion 2: Analisis por Macronutriente
    lineas_analisis = ["<b>2. ANÁLISIS DE BRECHAS Y DESVÍOS ESPECÍFICOS</b>"]
    
    if cal_m > 0 and cal_r > cal_m * 1.1:
        lineas_analisis.append(f"• <b>Exceso Calórico:</b> Estás consumiendo un {int(round(((cal_r/cal_m)-1)*100))}% por encima de la meta. Es prioritario reducir la densidad calórica de los platos para no enlentecer la pérdida de peso.")
    elif cal_m > 0 and cal_r < cal_m * 0.85:
        lineas_analisis.append(f"• <b>Déficit Calórico Pronunciado:</b> Tu ingesta está un {int(round(((1-(cal_r/cal_m))*100)))}% por debajo. Ojo con restringir demasiado, ya que puede ralentizar el metabolismo y generar pérdida de masa muscular.")
    else:
        lineas_analisis.append("• <b>Calorías Normocalóricas/Equilibradas:</b> Tu consumo energético total se mantiene alineado con las metas planificadas.")

    if fibr_r < fibr_m * 0.85:
        lineas_analisis.append(f"• <b>Déficit de Fibras ({fibr_r}g vs {fibr_m}g):</b> La baja ingesta dificulta la salud intestinal, perjudica el control glucémico y reduce la saciedad a largo plazo.")
    else:
        lineas_analisis.append(f"• <b>Nivel Nutritivo de Fibra Óptimo:</b> Estás cubriendo adecuadamente la cuota de digestibilidad y salud microbiana.")

    if gras_r > gras_m * 1.15:
        lineas_analisis.append(f"• <b>Exceso de Grasas ({gras_r}g vs {gras_m}g):</b> Un aporte elevado de grasas (especialmente saturadas) suma calorías rápidamente sin aportar volumen ni saciedad duradera.")
    elif gras_r < gras_m * 0.8:
        lineas_analisis.append(f"• <b>Déficit de Grasas Saludables:</b> Requiere atención para mantener un perfil hormonal óptimo.")
    else:
        lineas_analisis.append(f"• <b>Balance de Grasas Adecuado:</b> Ingesta lipídica controlada dentro de los rangos meta.")

    if carb_r < carb_m * 0.85:
        lineas_analisis.append(f"• <b>Déficit de Carbohidratos Complejos ({carb_r}g vs {carb_m}g):</b> Esto puede ocasionar fatiga, bajo rendimiento físico y antojos de azúcares al final de la jornada.")
    elif carb_r > carb_m * 1.15:
        lineas_analisis.append(f"• <b>Exceso de Carbohidratos:</b> Es conveniente reemplazar carbohidratos refinados por opciones complejas de menor índice glucémico.")
    else:
        lineas_analisis.append(f"• <b>Nivel de Carbohidratos Estable:</b> Buen balance de hidratos para energía constante.")

    if prot_r < prot_m * 0.85:
        lineas_analisis.append(f"• <b>Déficit Proteico ({prot_r}g vs {prot_m}g):</b> Fundamental aumentar su presencia para preservar la masa magra y aumentar la termogénesis alimentaria.")

    bloques.append("\n".join(lineas_analisis))

    # Seccion 3: Alimentos Sugeridos (Incorporar)
    lineas_inc = ["<b>3. ALIMENTOS Y COMIDAS QUE DEBERÍAS INGERIR (PARA SUPLIR DÉFICITS)</b>"]
    if fibr_r < fibr_m * 0.85:
        lineas_inc.append("• <b>Para la Fibra:</b> Incorporá 1 porción diaria de legumbres (lentejas, garbanzos, porotos) en ensaladas o guisos magros. Sumá 1 a 2 cucharadas de semillas (chía o lino hidratadas) en tus desayunos, y consumí frutas enteras con cáscara (manzana, pera, frutos rojos).")
    if carb_r < carb_m * 0.85:
        lineas_inc.append("• <b>Para Carbohidratos Complejos:</b> Sumá fuentes de absorción lenta como avena integral, quinoa, arroz integral, batata, choclo o mandioca hervida. Te darán energía sostenida sin picos glucémicos.")
    if prot_r < prot_m * 0.85:
        lineas_inc.append("• <b>Para Proteínas Magras:</b> Priorizá pechuga de pollo/pavo, claras de huevo, atún al natural, cortes vacunos magros (peceto, cuadril, bola de lomo), queso blanco magro y yogur griego natural sin azúcar.")
    if len(lineas_inc) == 1:
        lineas_inc.append("• Mantené la variedad de vegetales de hoja verde, hortalizas multicolores y cereales integrales para sostener tus excelentes promedios.")
    bloques.append("\n".join(lineas_inc))

    # Seccion 4: Alimentos a Reducir/Omitir (Excesos)
    lineas_red = ["<b>4. ALIMENTOS Y COMIDAS QUE DEBERÍAS REDUCIR O EVITAR (PARA CORREGIR EXCESOS)</b>"]
    if gras_r > gras_m * 1.15:
        lineas_red.append("• <b>Grasas y Frituras:</b> Evitá carnes vacunas de corte graso (costilla, asado, entraña), fiambres, embutidos (chorizos, salchichas), aderezos industriales (mayonesa, salsa golf), frituras y manteca/crema. Reemplazalos por aceite de oliva en crudo (1 cucharadita) y cocciones al horno o plancha.")
    if carb_r > carb_m * 1.15 or (cal_m > 0 and cal_r > cal_m * 1.1):
        lineas_red.append("• <b>Ultraprocesados y Azúcares:</b> Reducí al mínimo productos de panadería refinados, galletitas dulces/saladas, gaseosas azucaradas, jugos industriales y harinas blancas refinadas.")
    if len(lineas_red) == 1:
        lineas_red.append("• Moderá el uso de aceites al cocinar y controlá las porciones de frutos secos o quesos duros para no sobrepasar la densidad calórica.")
    bloques.append("\n".join(lineas_red))

    # Seccion 5: Plan de Accion y Cierre
    bloques.append(
        "<b>5. RECOMENDACIÓN GENERAL Y ESTRATEGIA DE HÁBITOS</b>\n"
        "Para consolidar estos cambios, asegurá una ingesta de agua potable de al menos <b>2 a 2.5 litros diarios</b>. "
        "La hidratación adecuada optimiza la función renal, mejora el tránsito intestinal favorecido por la fibra y ayuda a "
        "diferenciar la sed real de la ansiedad. Organizá tus compras semanales en base a las fuentes proteicas magras y vegetales frescos "
        "sugeridos, garantizando platos estructurados con la regla del plato (50% vegetales, 25% proteína magra, 25% carbohidrato complejo)."
    )

    return "\n\n".join(bloques)


#                                                       RECOMENDACIÓN BREVE PARA PANTALLA (~100 PALABRAS)
# =============================================================================================================================================================================

def obtener_recomendacion_ia(resumen_texto: str) -> str:
    texto_fallback = (
        "Ajustá tu balance diario moderando las grasas saturadas e incrementando fibras con legumbres, "
        "semillas y vegetales frescos. Priorizá proteínas magras y carbohidratos complejos. "
        "¡Mantené la constancia y asegurá 2 litros de agua al día!"
    )

    if 'client_ai' not in globals() or not client_ai:
        return texto_fallback

    modelo = globals().get('GROQ_TEXTO', "llama-3.3-70b-versatile")
    prompt = (
        "Basado en el siguiente resumen nutricional, redactá una recomendación BREVE, DIRECTA Y MOTIVADORA "
        "de EXACTAMENTE 90 a 110 PALABRAS (no te pases de 120 palabras). "
        "Resumí los desvíos principales de fibra, grasas o carbohidratos y menciona 2 o 3 alimentos concretos a incorporar y a evitar:\n\n"
        f"{resumen_texto}"
    )

    try:
        response = client_ai.chat.completions.create(
            model=modelo,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200
        )
        res = response.choices[0].message.content.strip()
        return res if res else texto_fallback
    except Exception as e:
        print(f"⚠️ Warning: Falló obtener_recomendacion_ia para pantalla: {e}")
        return texto_fallback


#                                                                MOSTRAR RESUMEN MES (TELEGRAM HANDLER)
# ======================================================================================================================================================================

async def mostrar_resumen_mes(query_or_update, user_id, mes_str):
    try:
        df_datos = obtener_datos_usuario(user_id)
        
        if df_datos is None or df_datos.empty:
            txt = f"📊 No hay registros ingresados para el usuario `{user_id}`."
            if hasattr(query_or_update, 'edit_message_text'):
                await query_or_update.edit_message_text(txt, parse_mode="Markdown")
            else:
                await query_or_update.message.reply_text(txt, parse_mode="Markdown")
            return

        df_mes = df_datos[df_datos['Fecha'].astype(str).str.startswith(mes_str)] if 'Fecha' in df_datos.columns else pd.DataFrame()
        if df_mes.empty:
            txt = f"📊 No hay registros para el mes `{mes_str}`."
            if hasattr(query_or_update, 'edit_message_text'):
                await query_or_update.edit_message_text(txt, parse_mode="Markdown")
            else:
                await query_or_update.message.reply_text(txt, parse_mode="Markdown")
            return

        # --- LECTURA DE PERFIL DESDE GOOGLE SHEETS ---
        perfil_dict = {}
        try:
            gc = get_gspread_client()
            sh = gc.open(SPREADSHEET_NAME)
            ws_perfil = get_or_create_worksheet(sh, f"Perfil_{user_id}")
            registros_perfil = ws_perfil.get_all_records()

            if registros_perfil:
                for r in registros_perfil:
                    r_lower = {str(k).strip().lower(): v for k, v in r.items()}
                    val_mes = str(r_lower.get("mes", "")).strip()
                    if val_mes == str(mes_str).strip():
                        perfil_dict = r_lower
                        break
        except Exception as err_perfil:
            print(f"Error accediendo a Perfil_{user_id}: {err_perfil}")

        # Validamos campos mínimos indispensables para el cálculo
        campos_criticos = ['edad', 'altura', 'peso']
        if not perfil_dict or any(k not in perfil_dict or parse_raw_val(perfil_dict[k]) == 0 for k in campos_criticos):
            txt_incompleto = (
                f"⚠️ **Datos biométricos incompletos para el mes `{mes_str}`.**\n\n"
                f"No se ingresaron o están incompletos los datos de edad, altura o peso en tu perfil para este mes. "
                f"Por favor, completá tu perfil del mes para generar el resumen y el reporte PDF."
            )
            if hasattr(query_or_update, 'edit_message_text'):
                await query_or_update.edit_message_text(txt_incompleto, parse_mode="Markdown")
            else:
                await query_or_update.message.reply_text(txt_incompleto, parse_mode="Markdown")
            return

        # --- LLAMADA ÚNICA A LA FUNCIÓN CENTRALIZADA DE MÉTRICAS ---
        m = calcular_metricas_mensuales(df_mes, perfil_dict)

        dict_promedios = {
            'calorias': m['prom_cal'],
            'proteinas': m['prom_prot'],
            'grasas': m['prom_gras'],
            'carbohidratos': m['prom_carb'],
            'fibras': m['prom_fibr']
        }

        dict_metas = {
            'calorias': m['ideal_cal'],
            'proteinas': m['ideal_prot'],
            'grasas': m['ideal_gras'],
            'carbohidratos': m['ideal_carb'],
            'fibras': m['ideal_fibr']
        }

        dict_biometria = {
            'peso_actual': m['peso_actual'],
            'peso_ideal': m['peso_ideal'],
            'altura': m['altura'],
            'edad': m['edad']
        }

        recomendacion_pdf = generar_recomendacion_ia(dict_promedios, dict_metas, dict_biometria)

        prompt_para_ia_pantalla = (
            f"REPORTE NUTRICIONAL DEL MES ({mes_str}):\n"
            f"- Peso registrado: {m['peso_actual']} kg | Peso Objetivo Ponderado: {m['peso_referencia']} kg\n"
            f"- Cambio de peso estimado: {m['cambio_peso_kg']:+.1f} kg\n"
            f"CONSUMO PROMEDIO DIARIO ({m['dias_registrados']} días registrados):\n"
            f"- Calorías: {m['prom_cal']} kcal (Meta: {m['ideal_cal']} kcal)\n"
            f"- Proteínas: {m['prom_prot']} g (Meta: {m['ideal_prot']} g)\n"
            f"- Grasas: {m['prom_gras']} g (Meta: {m['ideal_gras']} g)\n"
            f"- Carbohidratos: {m['prom_carb']} g (Meta: {m['ideal_carb']} g)\n"
            f"- Fibras: {m['prom_fibr']} g (Meta: {m['ideal_fibr']} g)\n"
        )
        recomendacion_pantalla = obtener_recomendacion_ia(prompt_para_ia_pantalla)

        user_data_ref = getattr(query_or_update, 'user_data', None)
        if user_data_ref is None and hasattr(query_or_update, 'message') and hasattr(query_or_update.message, 'user_data'):
            user_data_ref = query_or_update.message.user_data

        if isinstance(user_data_ref, dict):
            user_data_ref['ultima_recomendacion_ia'] = recomendacion_pdf

        txt = (
            f"📊 **Reporte Nutricional Mensual ({mes_str}):**\n\n"
            f"• **Promedio Consumidas:** `{m['prom_cal']} kcal` / día\n"
            f"• **Promedio Quemadas:** `{m['prom_quem']} kcal` / día\n"
            f"• **Balance Neto Diario:** `{m['prom_bal_neto']} kcal` / día\n"
            f"• **Cambio Estimado de Peso:** `{m['cambio_peso_kg']:+.1f} kg` en el mes\n\n"
            f"• Días con registro: `{m['dias_registrados']}`\n"
            f"📈 **Promedio Diario vs. Objetivos (Ponderados 75/25):**\n"
            f"• **Calorías:** `{m['prom_cal']} kcal` / Meta: `{m['ideal_cal']} kcal`\n"
            f"• **Proteínas:** `{m['prom_prot']} g` / Meta: `{m['ideal_prot']} g`\n"
            f"• **Grasas:** `{m['prom_gras']} g` / Meta: `{m['ideal_gras']} g`\n"
            f"• **Carbohidratos:** `{m['prom_carb']} g` / Meta: `{m['ideal_carb']} g`\n"
            f"• **Fibras:** `{m['prom_fibr']} g` / Meta: `{m['ideal_fibr']} g`\n\n"
            f"🤖 **Recomendación de la IA:**\n"
            f"_{recomendacion_pantalla}_\n\n"
            f"📄 Podés descargar el reporte completo en PDF a continuación:"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📄 Descargar PDF Resumen Mensual", callback_data=f"descargar_pdf_resumen_{mes_str}")]
        ])

        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(txt, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(txt, parse_mode="Markdown")

    except Exception as e:
        error_txt = f"⚠️ Ocurrió un error al procesar el resumen: `{str(e)}`"
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(error_txt, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(error_txt, parse_mode="Markdown")

#                                                    GENERAR PDF RESUMEN BYTES (FORZADO DE REPORTE COMPLETO)
# ===================================================================================================================================================================

def generar_pdf_resumen_bytes(mes_str, df_mes, df_presion, perfil, tmb_val, recomendacion, user_id):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1E3A8A'), spaceAfter=4)
    sub_style = ParagraphStyle('SubTitle', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#2563EB'), spaceBefore=8, spaceAfter=4)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8, leading=11, textColor=colors.HexColor('#1E293B'))
    rec_style = ParagraphStyle('RecBody', parent=styles['Normal'], fontSize=8, leading=11, textColor=colors.HexColor('#0F172A'), spaceAfter=4)
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)

    story = [
        Paragraph(f"<b>Reporte Nutricional Mensual - {mes_str}</b>", title_style),
        Paragraph(f"<b>Usuario Telegram ID:</b> {user_id}", body_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=8)
    ]

    headers_h1 = ["Fecha", "Cal. Consumid.", "Cal. Quemad.", "Bal. Neto", "Proteinas (g)", "Grasas (g)", "Carbohidratos (g)", "Fibras (g)"]
    table_data_h1 = [[Paragraph(h, header_style) for h in headers_h1]]

    tot_cons, tot_quem, tot_prot, tot_gras, tot_carb, tot_fibr = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    if df_mes is not None and not df_mes.empty:
        fechas_unicas = sorted(df_mes['Fecha'].unique())

        for f in fechas_unicas:
            sub = df_mes[df_mes['Fecha'] == f]
            
            c_cons = float(sub[sub['Calorias'] > 0]['Calorias'].sum()) if 'Calorias' in sub.columns else 0.0
            c_quem = float(abs(sub[sub['Calorias'] < 0]['Calorias'].sum())) if 'Calorias' in sub.columns else 0.0
            b_neto = c_cons - c_quem
            
            prot = float(sub['Proteinas'].sum()) if 'Proteinas' in sub.columns else 0.0
            gras = float(sub['Grasas'].sum()) if 'Grasas' in sub.columns else 0.0
            carb = float(sub['Carbohidratos'].sum()) if 'Carbohidratos' in sub.columns else 0.0
            fibr = float(sub['Fibras'].sum()) if 'Fibras' in sub.columns else 0.0

            tot_cons += c_cons
            tot_quem += c_quem
            tot_prot += prot
            tot_gras += gras
            tot_carb += carb
            tot_fibr += fibr

            table_data_h1.append([
                Paragraph(str(f), body_style),
                Paragraph(f"{int(round(c_cons))} kcal", body_style),
                Paragraph(f"{int(round(c_quem))} kcal", body_style),
                Paragraph(f"{int(round(b_neto))} kcal", body_style),
                Paragraph(f"{int(round(prot))} g", body_style),
                Paragraph(f"{int(round(gras))} g", body_style),
                Paragraph(f"{int(round(carb))} g", body_style),
                Paragraph(f"{int(round(fibr))} g", body_style)
            ])
        
        tot_neto = tot_cons - tot_quem
        table_data_h1.append([
            Paragraph("<b>TOTAL MES</b>", body_style),
            Paragraph(f"<b>{int(round(tot_cons))} kcal</b>", body_style),
            Paragraph(f"<b>{int(round(tot_quem))} kcal</b>", body_style),
            Paragraph(f"<b>{int(round(tot_neto))} kcal</b>", body_style),
            Paragraph(f"<b>{int(round(tot_prot))} g</b>", body_style),
            Paragraph(f"<b>{int(round(tot_gras))} g</b>", body_style),
            Paragraph(f"<b>{int(round(tot_carb))} g</b>", body_style),
            Paragraph(f"<b>{int(round(tot_fibr))} g</b>", body_style)
        ])

        dias_activos = len(fechas_unicas) if len(fechas_unicas) > 0 else 1
        table_data_h1.append([
            Paragraph("<b>PROM. DIARIO</b>", body_style),
            Paragraph(f"<b>{int(round(tot_cons/dias_activos))} kcal</b>", body_style),
            Paragraph(f"<b>{int(round(tot_quem/dias_activos))} kcal</b>", body_style),
            Paragraph(f"<b>{int(round(tot_neto/dias_activos))} kcal</b>", body_style),
            Paragraph(f"<b>{int(round(tot_prot/dias_activos))} g</b>", body_style),
            Paragraph(f"<b>{int(round(tot_gras/dias_activos))} g</b>", body_style),
            Paragraph(f"<b>{int(round(tot_carb/dias_activos))} g</b>", body_style),
            Paragraph(f"<b>{int(round(tot_fibr/dias_activos))} g</b>", body_style)
        ])

    t1 = Table(table_data_h1, colWidths=[65, 75, 70, 70, 65, 60, 80, 55])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0, -2), (-1, -1), colors.HexColor('#F1F5F9'))
    ]))
    story.append(t1)

    story.append(PageBreak())
    story.append(Paragraph("<b>Análisis Metabólico y Tabla Comparativa de Macronutrientes</b>", title_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=8))

    # --- LLAMADA ÚNICA A LA FUNCIÓN CENTRALIZADA DE MÉTRICAS PARA EL PDF ---
    perfil_dict = perfil if isinstance(perfil, dict) else {}
    m = calcular_metricas_mensuales(df_mes, perfil_dict)

    table_comp = [
        [Paragraph("<b>Nutriente / Métrica</b>", header_style), Paragraph("<b>Promedio Diario Real (Mes)</b>", header_style), Paragraph("<b>Valor Ideal (Peso Ponderado 75/25)</b>", header_style)],
        [Paragraph("Calorías", body_style), Paragraph(f"{m['prom_cal']} kcal", body_style), Paragraph(f"{int(round(m['get_meta']))} kcal", body_style)],
        [Paragraph("Proteínas", body_style), Paragraph(f"{m['prom_prot']} g", body_style), Paragraph(f"{m['ideal_prot']} g", body_style)],
        [Paragraph("Grasas", body_style), Paragraph(f"{m['prom_gras']} g", body_style), Paragraph(f"{m['ideal_gras']} g", body_style)],
        [Paragraph("Carbohidratos", body_style), Paragraph(f"{m['prom_carb']} g", body_style), Paragraph(f"{m['ideal_carb']} g", body_style)],
        [Paragraph("Fibras", body_style), Paragraph(f"{m['prom_fibr']} g", body_style), Paragraph(f"{m['ideal_fibr']} g", body_style)]
    ]
    t_comp = Table(table_comp, colWidths=[150, 185, 185])
    t_comp.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    story.append(t_comp)
    story.append(Spacer(1, 8))

    story.append(Paragraph(f"• <b>PERFIL BASE ({mes_str}):</b> Peso Actual: {m['peso_actual']} kg | Peso Objetivo (75/25): {m['peso_referencia']} kg | Altura: {m['altura']} cm", body_style))
    story.append(Paragraph(f"• <b>DÉFICIT CALÓRICO DIARIO PROMEDIO:</b> {m['deficit_diario_real']} kcal / día", body_style))
    story.append(Paragraph(f"• <b>CAMBIO ESTIMADO DE PESO EN EL MES:</b> {m['cambio_peso_kg']:+.1f} kg", body_style))

    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>Recomendación Nutricional Personalizada y Plan de Acción (IA):</b>", sub_style))

    texto_final = recomendacion
    es_texto_corto = not isinstance(texto_final, str) or len(texto_final.strip()) < 1200 or "<b>1. DIAGNÓSTICO" not in texto_final

    if es_texto_corto:
        p_dict = {'calorias': m['prom_cal'], 'proteinas': m['prom_prot'], 'grasas': m['prom_gras'], 'carbohidratos': m['prom_carb'], 'fibras': m['prom_fibr']}
        m_dict = {'calorias': int(round(m['get_meta'])), 'proteinas': m['ideal_prot'], 'grasas': m['ideal_gras'], 'carbohidratos': m['ideal_carb'], 'fibras': m['ideal_fibr']}
        b_dict = {'peso_actual': m['peso_actual'], 'peso_ideal': m['peso_ideal'], 'altura': m['altura'], 'edad': m['edad']}
        
        if 'generar_recomendacion_ia' in globals():
            texto_final = generar_recomendacion_ia(p_dict, m_dict, b_dict)

    if isinstance(texto_final, str):
        for bloque in texto_final.strip().split('\n\n'):
            if bloque.strip():
                story.append(Paragraph(bloque.strip().replace('\n', '<br/>'), rec_style))
                story.append(Spacer(1, 4))

    doc.build(story)
    buffer.seek(0)
    return buffer

async def generar_y_enviar_pdf_resumen(query, user_id, mes_str, context):
    df_datos = obtener_datos_usuario(user_id)
    df_mes = df_datos[df_datos['Fecha'].astype(str).str.startswith(mes_str)] if not df_datos.empty and 'Fecha' in df_datos.columns else pd.DataFrame()
    
    df_presion = obtener_datos_presion(user_id)
    df_p_mes = df_presion[df_presion['Fecha_Dia'].str.startswith(mes_str)] if not df_presion.empty and 'Fecha_Dia' in df_presion.columns else pd.DataFrame()
    
    perfil = obtener_perfil_usuario(user_id, mes_target=mes_str)
    
    recomendacion = context.user_data.get('ultima_recomendacion_ia') if context and hasattr(context, 'user_data') else None
    
    if not recomendacion:
        dias_act = df_mes['Fecha'].nunique() if not df_mes.empty else 1
        p_act = parse_raw_val(perfil.get('Peso')) if perfil else 108.5
        p_id = parse_raw_val(perfil.get('Peso_ideal', perfil.get('Peso_Ideal', 75.0))) if perfil else 75.0
        p_ref = (p_act * 0.75) + (p_id * 0.25)
        
        tot_c = float(df_mes[df_mes['Calorias'] > 0]['Calorias'].sum()) if not df_mes.empty else 0
        prompt_ia = f"Resumen {mes_str}: Consumo diario {int(round(tot_c/dias_act))} kcal. Peso actual: {int(round(p_act))}kg, Meta ponderada: {int(round(p_ref))}kg. Da un consejo nutricional."
        recomendacion = obtener_recomendacion_ia(prompt_ia)

    tmb_val, _ = calcular_tmb_y_get(
        perfil.get('Peso', 108.5) if perfil else 108.5,
        perfil.get('Altura', 167.0) if perfil else 167.0,
        perfil.get('Edad', 64) if perfil else 64,
        perfil.get('GENERO', perfil.get('Genero', 'masculino')) if perfil else 'masculino',
        perfil.get('Ocupacion', 'jubilado') if perfil else 'jubilado'
    )

    pdf_bytes = generar_pdf_resumen_bytes(mes_str, df_mes, df_p_mes, perfil, tmb_val, recomendacion, user_id)
    
    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=pdf_bytes,
        filename=f"Reporte_Nutricional_{mes_str}.pdf"
    )

# ==================================================================================================================================================================================
#                   FINAL                                COMANDO RESUMEN                                           FINAL
# ===================================================================================================================================================================================

# ==================================================================================================================================================================================
#                   INICIO                         MODULO DE PRESION ARTERIAL (COMANDO, SHEETS Y PDF)                        INICIO
# ===================================================================================================================================================================================

def obtener_datos_presion(user_id):
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws = get_or_create_worksheet(sh, f"Presion_{user_id}")
        records = ws.get_all_records()
        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        for col in ['Alta', 'Baja', 'Pulsaciones']:
            if col in df.columns:
                df[col] = df[col].apply(parse_float_from_sheets)

        if 'Fecha_Dia' in df.columns:
            df['Fecha_Dia'] = df['Fecha_Dia'].astype(str).str.strip()

        if 'Nota' not in df.columns:
            df['Nota'] = ""

        return df
    except Exception:
        return pd.DataFrame()


def guardar_presion_en_sheets(user_id, alta, baja, pulsaciones, nota=""):
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    ws = get_or_create_worksheet(sh, f"Presion_{user_id}")
    ahora = obtener_ahora_arg()
    ws.append_row([
        ahora.strftime("%Y-%m-%d %H:%M:%S"), 
        ahora.strftime("%Y-%m-%d"), 
        to_sheet_int(alta), 
        to_sheet_int(baja), 
        to_sheet_int(pulsaciones) if pulsaciones is not None else 0,
        str(nota).strip()
    ])

def generar_pdf_presion_bytes(mes_str, df_presion, user_id):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1E3A8A'), spaceAfter=4)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor('#1E293B'))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8.5, leading=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)

    story = [
        Paragraph(f"<b>Detalle Diario de Presion Arterial - {mes_str}</b>", title_style),
        Paragraph(f"<b>Usuario Telegram ID:</b> {user_id}", body_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=10)
    ]

    if df_presion.empty:
        story.append(Paragraph("No hay registros de presion para este mes.", body_style))
    else:
        table_data = [[
            Paragraph("Fecha y Hora", header_style),
            Paragraph("Alta (mmHg)", header_style),
            Paragraph("Baja (mmHg)", header_style),
            Paragraph("Pulsaciones", header_style),
            Paragraph("Nota / Detalle", header_style)
        ]]

        for _, r in df_presion.iterrows():
            table_data.append([
                Paragraph(str(r.get('Fecha_Hora', '')), body_style),
                Paragraph(f"{r.get('Alta', 0):.0f}", body_style),
                Paragraph(f"{r.get('Baja', 0):.0f}", body_style),
                Paragraph(f"{r.get('Pulsaciones', 0):.0f}", body_style),
                Paragraph(str(r.get('Nota', '')), body_style)
            ])

        t = Table(table_data, colWidths=[110, 65, 65, 70, 190])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
        ]))
        story.append(t)

    doc.build(story)
    buffer.seek(0)
    return buffer

async def cmd_presion_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    raw_text = re.sub(r'^/pres\w*(@\w+)?', '', update.message.text, flags=re.IGNORECASE).strip()

    if not raw_text:
        await update.message.reply_text(
            "Ingresa o consulta un mes. Verificar que \n"
            "/presion no tenga acento. Ejemplos : \n\n"
            "• /presion 120,80,70, despues de caminar\n"
            "• /presion 120,80,70\n"
            "• /presion 120,80\n"
            "• /presion 2026-08", 
            parse_mode="Markdown"
        )
        return

    if re.match(r'^20\d{2}-\d{2}$', raw_text):
        await mostrar_resumen_presion_mes(update, user_id, raw_text)
        return

    parts = [p.strip() for p in raw_text.replace('/', ',').split(',') if p.strip()]
    if len(parts) == 1:
        parts = [p.strip() for p in raw_text.split(' ') if p.strip()]

    numeros = []
    texto_nota = []

    for part in parts:
        clean_part = part.replace(',', '.')
        try:
            val = float(clean_part)
            if len(numeros) < 3 and not texto_nota:
                numeros.append(val)
            else:
                texto_nota.append(part)
        except ValueError:
            texto_nota.append(part)

    if len(numeros) >= 2:
        alta = numeros[0]
        baja = numeros[1]
        pulsaciones = numeros[2] if len(numeros) > 2 else None
        nota = " ".join(texto_nota).strip()

        guardar_presion_en_sheets(user_id, alta, baja, pulsaciones, nota)

        pul_str = f" | Pulsaciones: `{pulsaciones}`" if pulsaciones is not None else ""
        nota_str = f"\nNota: `{nota}`" if nota else ""
        
        await update.message.reply_text(
            f"Presion registrada:\nAlta: `{alta}` | Baja: `{baja}`{pul_str}{nota_str}", 
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text(
        "Formato incorrecto. Uso: /presi 120,80,70, al despertar o /presi 120,80 o /presi 2026-08", 
        parse_mode="Markdown"
    )

async def mostrar_resumen_presion_mes(query_or_update, user_id, mes_str):
    df_presion = obtener_datos_presion(user_id)
    if df_presion.empty:
        txt = f"🩺 No hay registros de presion arterial para el usuario `{user_id}`."
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(txt, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(txt, parse_mode="Markdown")
        return

    df_p_mes = df_presion[df_presion['Fecha_Dia'].str.startswith(mes_str)] if 'Fecha_Dia' in df_presion.columns else pd.DataFrame()
    if df_p_mes.empty:
        txt = f"🩺 No hay registros de presion para el mes `{mes_str}`."
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(txt, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(txt, parse_mode="Markdown")
        return

    alta_prom = df_p_mes['Alta'].mean()
    baja_prom = df_p_mes['Baja'].mean()
    pul_prom = df_p_mes[df_p_mes['Pulsaciones'] > 0]['Pulsaciones'].mean() if 'Pulsaciones' in df_p_mes.columns else 0

    txt = (
        f"🩺 **Resumen de Presion Arterial ({mes_str}):**\n\n"
        f"• Mediciones registradas: `{len(df_p_mes)}`\n"
        f"• **Promedio Alta (Sistolica):** `{alta_prom:.1f} mmHg`\n"
        f"• **Promedio Baja (Diastolica):** `{baja_prom:.1f} mmHg`\n"
    )
    if pul_prom > 0:
        txt += f"• **Promedio Pulsaciones:** `{pul_prom:.1f} lpm`\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Descargar PDF Presion Diaria", callback_data=f"descargar_pdf_presion_{mes_str}")]
    ])

    if hasattr(query_or_update, 'edit_message_text'):
        await query_or_update.edit_message_text(txt, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await query_or_update.message.reply_text(txt, reply_markup=keyboard, parse_mode="Markdown")

async def generar_y_enviar_pdf_presion(query, user_id, mes_str, context):
    df_presion = obtener_datos_presion(user_id)
    df_p_mes = df_presion[df_presion['Fecha_Dia'].str.startswith(mes_str)] if not df_presion.empty and 'Fecha_Dia' in df_presion.columns else pd.DataFrame()
    
    pdf_bytes = generar_pdf_presion_bytes(mes_str, df_p_mes, user_id)
    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=pdf_bytes,
        filename=f"Presion_Arterial_{mes_str}.pdf"
    )        
        
# =========================================================================================================================================
#                  FINAL                          MODULO DE PRESION ARTERIAL (COMANDO, SHEETS Y PDF)                       FINAL
# =============================================================================================================================================

# ===============================================================================================================================================
#                    INICIO                                    COMANDO RECETAS                                           INICIO
# ================================================================================================================================================


async def cmd_cargar_receta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Envía un botón interactivo y enlace con el user_id para acceder
    a la calculadora e ingresar directamente la comida precargada.
    """
    user_id = update.effective_user.id
    # URL pública de tu app en Render o servidor
    web_app_url = f"https://telegram-bot-nutricion.onrender.com/calculadora?user_id={user_id}"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍳 Abrir Creador de Recetas", url=web_app_url)]
    ])
    
    mensaje = (
        f"👋 Hola! Usá el siguiente botón para calcular los valores nutricionales "
        f"de tu receta e ingresarla directamente en tu planilla personalizada (*Comidas_{user_id}*):"
    )
    
    await update.message.reply_text(mensaje, reply_markup=keyboard, parse_mode="Markdown")

# ==================================================================================================================================================================================
#                  FINAL                                       COMANDO RECETA                                               FINAL
# ===================================================================================================================================================================================

# =====================================================================================================================================================================
#                   INICIO                                    COMANDO DIARIO   2026 08 22                              INICIO
# =======================================================================================================================================================================

async def cmd_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Manejador del comando /diario.
    Muestra el menú de selección de fecha solo si el peso del mes en curso está al día.
    """
    # 1. Validación estricta del peso del mes actual (Si no está al día, envía aviso y cancela)
    if not await _validar_peso_mes_actual(update, context, funcion_nombre="reporte diario"):
        return

    # 2. Despliegue del menú si el peso está al día
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Hoy", callback_data="diario_hoy"), InlineKeyboardButton("📆 Ayer", callback_data="diario_ayer")],
        [InlineKeyboardButton("🗓️ Seleccionar Fecha", callback_data="diario_otro")]
    ])
    
    await update.message.reply_text(
        "📅 **Consulta de Diario:** Seleccioná qué día querés revisar:", 
        reply_markup=keyboard, 
        parse_mode="Markdown"
    )

async def mostrar_diario_fecha(update_or_query, user_id, fecha_str):
    """
    Función auxiliar para procesar y renderizar el reporte del diario agrupado por evento.
    """
    try:
        df = obtener_datos_usuario(user_id)
        df_diario = df[df['Fecha'] == fecha_str] if not df.empty else pd.DataFrame()

        if df_diario.empty:
            texto = f"⚠️ No se encontraron registros de ingestas para la fecha `{fecha_str}`."
            reply_markup = None
        else:
            # 1. Encabezado
            texto = f"📅 Registro del día {fecha_str}:\n\n"
            
            # 2. Agrupación por momento mantención del orden de aparición original
            momentos_vistos = []
            agrupado = {}
            
            for _, r in df_diario.iterrows():
                momento = str(r.get('Momento', '')).strip()
                alimento = str(r.get('Alimento', '')).strip()
                
                if momento not in agrupado:
                    agrupado[momento] = []
                    momentos_vistos.append(momento)
                if alimento:
                    agrupado[momento].append(alimento)

            # Formateo agrupado tipo listado bullet
            for m in momentos_vistos:
                items_str = ", ".join(agrupado[m])
                texto += f"• {m}: {items_str}\n"

            # 3. Totales y métricas nutricionales
            c_cons = df_diario[df_diario['Calorias'] > 0]['Calorias'].sum()
            c_quem = abs(df_diario[df_diario['Calorias'] < 0]['Calorias'].sum())
            b_neto = c_cons - c_quem
            
            p_tot = df_diario[df_diario['Calorias'] > 0]['Proteinas'].sum()
            g_tot = df_diario[df_diario['Calorias'] > 0]['Grasas'].sum()
            cb_tot = df_diario[df_diario['Calorias'] > 0]['Carbohidratos'].sum()
            f_tot = df_diario[df_diario['Calorias'] > 0]['Fibras'].sum()

            texto += f"\n🔥 Consumidas: {c_cons:.1f} kcal\n"
            texto += f"⚡ Quemadas: {c_quem:.1f} kcal\n"
            texto += f"⚖️ Balance Neto: {b_neto:.1f} kcal\n\n"
            texto += f"🥩 Prot: {p_tot:.1f}g | 🥑 Gras: {g_tot:.1f}g | 🍞 Carb: {cb_tot:.1f}g | 🌾 Fibr: {f_tot:.1f}g"

            keyboard = [[InlineKeyboardButton("📄 Descargar PDF", callback_data=f"descargar_pdf_diario_{fecha_str}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

        # Envíos dinámicos según el origen de llamada originales
        if hasattr(update_or_query, 'edit_message_text'):
            try:
                await update_or_query.edit_message_text(texto, reply_markup=reply_markup, parse_mode="Markdown")
            except Exception as ex:
                if "Message is not modified" not in str(ex):
                    raise ex
        elif hasattr(update_or_query, 'reply_text'):
            await update_or_query.reply_text(texto, reply_markup=reply_markup, parse_mode="Markdown")
        elif hasattr(update_or_query, 'message') and update_or_query.message:
            await update_or_query.message.reply_text(texto, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        if "Message is not modified" in str(e):
            return
            
        msg_err = f"❌ Error al consultar el diario para la fecha `{fecha_str}`: {e}"
        if hasattr(update_or_query, 'edit_message_text'):
            try:
                await update_or_query.edit_message_text(msg_err, parse_mode="Markdown")
            except Exception:
                pass
        elif hasattr(update_or_query, 'reply_text'):
            await update_or_query.reply_text(msg_err, parse_mode="Markdown")
        elif hasattr(update_or_query, 'message') and update_or_query.message:
            await update_or_query.message.reply_text(msg_err, parse_mode="Markdown")

def generar_pdf_diario_bytes(fecha_str, df_diario, user_id):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1E3A8A'), spaceAfter=4)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor('#1E293B'))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8.5, leading=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)

    story = [
        Paragraph(f"<b>Detalle Diario de Ingestas - {fecha_str}</b>", title_style),
        Paragraph(f"<b>Usuario Telegram ID:</b> {user_id}", body_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=10)
    ]

    if df_diario.empty:
        story.append(Paragraph("No hay registros para esta fecha.", body_style))
    else:
        table_data = [[
            Paragraph("Momento", header_style),
            Paragraph("Alimento / Detalle", header_style),
            Paragraph("Peso", header_style),
            Paragraph("Kcal", header_style),
            Paragraph("Prot", header_style),
            Paragraph("Gras", header_style),
            Paragraph("Carb", header_style),
            Paragraph("Fibr", header_style)
        ]]

        for _, r in df_diario.iterrows():
            table_data.append([
                Paragraph(str(r.get('Momento', '')), body_style),
                Paragraph(str(r.get('Alimento', '')), body_style),
                Paragraph(f"{r.get('Peso', 0):.1f}g", body_style),
                Paragraph(f"{r.get('Calorias', 0):.1f}", body_style),
                Paragraph(f"{r.get('Proteinas', 0):.1f}g", body_style),
                Paragraph(f"{r.get('Grasas', 0):.1f}g", body_style),
                Paragraph(f"{r.get('Carbohidratos', 0):.1f}g", body_style),
                Paragraph(f"{r.get('Fibras', 0):.1f}g", body_style)
            ])

        t = Table(table_data, colWidths=[70, 160, 45, 45, 45, 45, 45, 45])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
        ]))
        story.append(t)
        story.append(Spacer(1, 10))

        c_cons = df_diario[df_diario['Calorias'] > 0]['Calorias'].sum()
        c_quem = abs(df_diario[df_diario['Calorias'] < 0]['Calorias'].sum())
        b_neto = c_cons - c_quem
        story.append(Paragraph(f"• <b>Total Consumidas:</b> {c_cons:.1f} kcal", body_style))
        story.append(Paragraph(f"• <b>Total Quemadas:</b> {c_quem:.1f} kcal", body_style))
        story.append(Paragraph(f"• <b>Balance Neto:</b> {b_neto:.1f} kcal", body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer

# =====================================================================================================================================================================
#                   FINAL                                COMANDOS DIARIO                                     FINAL
# =====================================================================================================================================================================

# ========================================================================================================================================================================
#                   INICIO                               COMANDO PERFIL   2026 08 20                          INICIO
# =========================================================================================================================================================================

async def cmd_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw_text = update.message.text.replace('/perfil', '').strip()
    ahora = obtener_ahora_arg()
    mes_actual = ahora.strftime("%Y-%m")

    # CASO 1: Ingreso de peso (/perfil 82.5)
    if raw_text:
        try:
            texto_limpio = raw_text.split()[0].replace(',', '.')
            nuevo_peso = float(texto_limpio)
            
            # Se guardan el peso y el mes.
            guardar_perfil_en_sheets(user_id, nuevo_peso, mes_actual)
            
            # Recargar el perfil actualizado
            perfil_actualizado = obtener_perfil_usuario(user_id, mes_target=mes_actual)
            
            if perfil_actualizado:
                edad = parse_raw_val(perfil_actualizado.get('EDAD', perfil_actualizado.get('Edad', 64)))
                altura = parse_raw_val(perfil_actualizado.get('ALTURA', perfil_actualizado.get('Altura', 170)))
                genero = str(perfil_actualizado.get('GENERO', perfil_actualizado.get('Genero', 'masculino')))
                ocupacion = str(perfil_actualizado.get('OCUPACION', perfil_actualizado.get('Ocupacion', 'Jubilado')))
            else:
                edad, altura, genero, ocupacion = 200.0, 200.0, "masculino", "Jubilado"

            tmb, get_val = calcular_tmb_y_get(nuevo_peso, altura, edad, genero, ocupacion)
            
            await update.message.reply_text(
                f"✅ **Peso actualizado correctamente para el mes `{mes_actual}`:**\n\n"
                f"• Nuevo Peso: `{nuevo_peso:.1f}` kg\n"
                f"• **TMB Estimada:** `{tmb:.0f} kcal/día`\n"
                f"• **GET Estimado:** `{get_val:.0f} kcal/día`",
                parse_mode="Markdown"
            )
            return

        except ValueError:
            await update.message.reply_text("❌ Por favor, ingresá un número válido para el peso. Ejemplo: `/perfil 82.5`", parse_mode="Markdown")
            return
        except Exception as e:
            print(f"Error al procesar /perfil en Sheets: {e}")
            await update.message.reply_text(f"⚠️ Ocurrió un error al intentar guardar en la planilla: {e}", parse_mode="Markdown")
            return

    # CASO 2: Consulta (/perfil solo)
    try:
        perfil = obtener_perfil_usuario(user_id, mes_target=mes_actual)

        if perfil:
            peso = parse_raw_val(perfil.get('PESO', perfil.get('Peso')))
            altura = parse_raw_val(perfil.get('ALTURA', perfil.get('Altura')))
            edad = parse_raw_val(perfil.get('EDAD', perfil.get('Edad')))
            genero = str(perfil.get('GENERO', perfil.get('Genero', 'masculino')))
            ocupacion = str(perfil.get('OCUPACION', perfil.get('Ocupacion', 'Jubilado')))

            tmb, get_val = calcular_tmb_y_get(peso, altura, edad, genero, ocupacion)
            
            txt = (
                f"👤 **Perfil Biométrico Actual ({mes_actual}):**\n\n"
                f"• Edad: `{edad:.0f}` años\n"
                f"• Peso: `{peso:.1f}` kg\n"
                f"• Altura: `{altura:.1f}` cm\n"
                f"• Género: `{genero}`\n"
                f"• Ocupación: `{ocupacion}`\n"
                f"• **TMB Estimada:** `{tmb:.0f} kcal/día`\n"
                f"• **GET Estimado:** `{get_val:.0f} kcal/día`\n\n"
                f"📌 **Para actualizar tu peso mensual:**\n"
                f"`/perfil 82.5`"
            )
        else:
            txt = f"👤 **Perfil no registrado para este mes.** Podés cargar tu peso ejecutando:\n`/perfil 82.5`"

        await update.message.reply_text(txt, parse_mode="Markdown")
    except Exception as e:
        print(f"Error al consultar /perfil: {e}")
        await update.message.reply_text(f"⚠️ Ocurrió un error al leer tu perfil: {e}", parse_mode="Markdown")


def guardar_perfil_en_sheets(user_id, peso, mes=None, edad=None, altura=None, genero=None, ocupacion=None, *args, **kwargs):
    """
    Guarda/actualiza el peso del usuario manteniendo intactos los formatos 
    y valores de las columnas históricas (ALTURA, EDAD, Peso_ideal).
    Además, actualiza la celda 'Ultimo Mes Peso' en la pestaña 'usuarios'.
    """
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    ws = get_or_create_worksheet(sh, f"Perfil_{user_id}")
    ahora = obtener_ahora_arg()
    
    if not mes:
        mes = ahora.strftime("%Y-%m")
    
    records = ws.get_all_records()
    
    # Variables crudas para guardar directamente en el Excel
    edad_raw = edad if edad is not None else 64000
    altura_raw = altura if altura is not None else 172000
    genero_final = genero if genero is not None else "masculino"
    ocupacion_final = ocupacion if ocupacion is not None else "Jubilado"
    peso_ideal_final = ""
    fecha_cumple_str = ""
    fila_a_actualizar = None

    # 1. Recuperar valores existentes en la planilla exactamente como están guardados
    if records:
        ultimo_registro = records[-1]
        
        # Leemos el valor directo de la celda (ej: 172000 o 64000)
        if edad is None:
            edad_raw = ultimo_registro.get('EDAD', ultimo_registro.get('Edad', 64000))

        if altura is None:
            altura_raw = ultimo_registro.get('ALTURA', ultimo_registro.get('Altura', 172000))

        if genero is None:
            genero_final = str(ultimo_registro.get('GENERO', ultimo_registro.get('Genero', ultimo_registro.get('Sexo', 'masculino'))))
        
        if ocupacion is None:
            ocupacion_final = str(ultimo_registro.get('OCUPACION', ultimo_registro.get('Ocupacion', 'Jubilado')))
        
        peso_ideal_final = ultimo_registro.get('Peso_ideal', ultimo_registro.get('peso_ideal', ''))
        fecha_cumple_str = str(ultimo_registro.get('Cumple', ultimo_registro.get('cumple', ''))).strip()

        # Verificar si la fila del mes en curso ya existe
        for idx, row in enumerate(records, start=2):
            mes_en_fila = str(row.get('MES', row.get('Mes', ''))).strip()
            if mes_en_fila == str(mes):
                fila_a_actualizar = idx
                break

    # 2. Recalcular la edad automáticamente si cambió el año por el cumpleaños
    if fecha_cumple_str:
        try:
            if "-" in fecha_cumple_str:
                partes = fecha_cumple_str.split("-")
                fnac = datetime.strptime(fecha_cumple_str, "%Y-%m-%d") if len(partes[0]) == 4 else datetime.strptime(fecha_cumple_str, "%d-%m-%Y")
            elif "/" in fecha_cumple_str:
                fnac = datetime.strptime(fecha_cumple_str, "%d/%m/%Y")
            else:
                fnac = None

            if fnac:
                edad_calculada = ahora.year - fnac.year - ((ahora.month, ahora.day) < (fnac.month, fnac.day))
                if edad_calculada > 0:
                    edad_raw = to_sheet_int(edad_calculada)
        except Exception as e:
            print(f"Error al calcular edad desde Cumple ({fecha_cumple_str}): {e}")

    # 3. Armado de fila: Solo se aplica to_sheet_int al PESO ingresado nuevo
    nueva_fila = [
        str(edad_raw),                       # A: EDAD
        to_sheet_int(peso),                  # B: PESO (convertido a miles)
        str(altura_raw),                     # C: ALTURA
        str(genero_final),                   # D: GENERO
        str(ocupacion_final),                # E: OCUPACION
        str(mes),                            # F: MES
        ahora.strftime("%Y-%m-%d %H:%M:%S"), # G: Fecha_Actualiza
        str(peso_ideal_final),               # H: Peso_ideal
        str(fecha_cumple_str)                # I: Cumple
    ]

    # 4. Actualización en Perfil_USERID
    if fila_a_actualizar:
        ws.update(f"A{fila_a_actualizar}:I{fila_a_actualizar}", [nueva_fila])
    else:
        ws.append_row(nueva_fila)

    # 5. Actualizar la pestaña 'usuarios' con la columna 'Ultimo Mes Peso'
    try:
        ws_usuarios = sh.worksheet("Usuarios")
        
        # Leemos todos los registros para buscar al usuario de forma segura
        registros_usuarios = ws_usuarios.get_all_records()
        headers = ws_usuarios.row_values(1)
        
        # 1. Identificar columna objetivo de manera tolerante
        col_idx = None
        for idx, h in enumerate(headers, start=1):
            nombre_col = str(h).strip().lower()
            if nombre_col in ["ultimo mes peso", "ultimo_mes_peso", "ultimomespeso"]:
                col_idx = idx
                break
        
        if not col_idx:
            col_idx = 4  # Columna por defecto si no encuentra el encabezado

        # 2. Buscar la fila del usuario comparando enteros y strings contra varias claves posibles de ID
        fila_usuario = None
        for i, reg in enumerate(registros_usuarios, start=2): # start=2 porque la fila 1 es el encabezado
            id_reg = reg.get('ID') or reg.get('user_id') or reg.get('ID_USUARIO') or list(reg.values())[0]
            if str(id_reg).strip() == str(user_id).strip():
                fila_usuario = i
                break

        # 3. Si no se encontró por dict, buscar directamente recorriendo la primera columna
        if not fila_usuario:
            col_ids = ws_usuarios.col_values(1)
            for idx, val in enumerate(col_ids, start=1):
                if str(val).strip() == str(user_id).strip():
                    fila_usuario = idx
                    break

        # 4. Impactar el cambio usando formato de rango A1 de gspread
        if fila_usuario:
            from gspread.utils import rowcol_to_a1
            celda_a1 = rowcol_to_a1(fila_usuario, col_idx)
            
            ws_usuarios.update(celda_a1, [[str(mes)]])
            print(f"✅ Hoja usuarios actualizada: ID {user_id} -> Celda {celda_a1} = {mes}")
        else:
            print(f"⚠️ No se encontró el usuario {user_id} en la pestaña 'usuarios'.")
            
    except Exception as e:
        print(f"❌ Error crítico al actualizar la pestaña 'usuarios': {e}")


def obtener_perfil_usuario(user_id, mes_target=None):
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws = get_or_create_worksheet(sh, f"Perfil_{user_id}")
        records = ws.get_all_records()
        if not records:
            return None
        
        perfil_raw = None
        if mes_target:
            for r in reversed(records):
                m_val = str(r.get('MES', r.get('Mes', ''))).strip()
                if m_val == mes_target:
                    perfil_raw = r
                    break
        
        if not perfil_raw:
            perfil_raw = records[-1]
        
        perfil = {}
        for k, v in perfil_raw.items():
            k_upper = str(k).strip().upper()
            if k_upper == 'EDAD':
                perfil['Edad'] = parse_float_from_sheets(v)
            elif k_upper == 'PESO':
                perfil['Peso'] = parse_float_from_sheets(v)
            elif k_upper == 'ALTURA':
                perfil['Altura'] = parse_float_from_sheets(v)
            elif k_upper in ['GENERO', 'SEXO']:
                perfil['Sexo'] = str(v)
            elif k_upper == 'OCUPACION':
                perfil['Ocupacion'] = str(v)
            elif k_upper == 'MES':
                perfil['Mes'] = str(v)

        return perfil
    except Exception as e:
        print(f"Error obteniendo perfil del usuario {user_id}: {e}")
        return None

# ==================================================================================================================================================================
#                       FINAL                                       COMANDOS PERFIL                                                FINAL
# ===================================================================================================================================================================

# ====================================================================================================================================================================
#                      INICIO                                   OPERACIONES COMIDAS 2026-08-19                                    INICIO
# ====================================================================================================================================================================

def obtener_comidas_usuario(user_id):
    """
    Obtiene las comidas precargadas de la hoja 'Comidas_<user_id>'.
    Reemplaza a obtener_plantillas_comidas().
    """
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws = get_or_create_worksheet(sh, f"Comidas_{user_id}")
        records = ws.get_all_records()
        
        for p in records:
            # Normaliza los nombres de claves según las cabeceras de la planilla
            p['Nombre'] = p.get('Código / Nombre') or p.get('Nombre') or ''
            p['Descripcion'] = p.get('Descripción') or p.get('Descripcion') or p.get('Momento', '')
            
            for k in ['Peso', 'Calorias', 'Proteinas', 'Grasas', 'Carbohidratos', 'Fibras', 
                      'Peso (g x1000)', 'Calorías (x1000)', 'Proteínas (g x1000)', 
                      'Grasas (g x1000)', 'Carbohidratos (g x1000)', 'Fibras (g x1000)']:
                if k in p:
                    p[k] = parse_float_from_sheets(p[k])
                    
        return records
    except Exception as e:
        logger.error(f"Error al obtener comidas de Comidas_{user_id}: {e}")
        return []

async def cmd_comidas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    comidas = obtener_comidas_usuario(user_id)
    
    if not comidas:
        await update.message.reply_text(f"📋 No hay comidas predeterminadas registradas en la hoja 'Comidas_{user_id}'.")
        return

    txt = f"📋 <b>Listado de Comidas Predeterminadas (Comidas_{user_id}):</b>\n\n"
    
    for p in comidas:
        # Obtenemos los valores y limpiamos el símbolo § y etiquetas HTML
        nombre_raw = str(p.get('Nombre', ''))
        desc_raw = str(p.get('Descripcion') or p.get('Momento', ''))
        
        # Eliminamos el símbolo §, espacios sobrantes y caracteres de control HTML
        nombre = nombre_raw.replace('§', '').replace('<', '').replace('>', '').strip()
        descripcion = desc_raw.replace('§', '').replace('<', '').replace('>', '').strip()
        
        # Si la descripción quedó vacía o es igual al nombre, no la repetimos
        if descripcion and descripcion.lower() != nombre.lower():
            linea = f"• <b>{nombre}</b>: {descripcion}\n"
        else:
            linea = f"• <b>{nombre}</b>\n"
        
        # Control para no superar el límite de 4096 caracteres de Telegram
        if len(txt) + len(linea) > 4000:
            txt += "• <i>...y más comidas (ver detalle en el PDF adjunto).</i>\n"
            break
            
        txt += linea

    txt += "\n📄 Te adjuntamos el archivo en PDF completo con todos los macronutrientes a continuación."
    
    # 1. Enviar el texto limpio
    try:
        await update.message.reply_text(txt, parse_mode="HTML")
    except Exception as e:
        print(f"Error enviando texto de comidas: {e}")
        await update.message.reply_text("📋 Generando tu lista de comidas en PDF directamente...")

    # 2. Enviar el PDF
    try:
        pdf_bytes = generar_pdf_comidas_bytes(comidas)
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_bytes,
            filename=f"Comidas_{user_id}.pdf"
        )
    except Exception as e:
        print(f"Error generando PDF de comidas: {e}")
        await update.message.reply_text("❌ Ocurrió un error al generar el archivo PDF.")
        
def buscar_comida_precargada_exacta(user_id, texto_codigo):
    """
    Busca de forma estricta un código/nombre de comida ÚNICAMENTE en la pestaña 'Comidas_<user_id>'.
    Si NO la encuentra, devuelve None.
    """
    codigo_buscado = texto_codigo.strip().upper()
    comidas_usuario = obtener_comidas_usuario(user_id)

    for item in comidas_usuario:
        nombre_item = str(item.get('Nombre') or item.get('Código / Nombre') or '').strip().upper()
        if nombre_item == codigo_buscado:
            # Detectar valores con escala x1000 guardados desde la web/Sheets
            peso_raw = item.get('Peso (g x1000)', item.get('Peso', 0))
            cal_raw = item.get('Calorías (x1000)', item.get('Calorias', 0))
            prot_raw = item.get('Proteínas (g x1000)', item.get('Proteinas', 0))
            gras_raw = item.get('Grasas (x1000)', item.get('Grasas', 0))
            carb_raw = item.get('Carbohidratos (x1000)', item.get('Carbohidratos', 0))
            fibr_raw = item.get('Fibras (x1000)', item.get('Fibras', 0))

            # Si viene escalado x1000, desescalar dividiendo por 1000
            factor = 1000.0 if peso_raw > 5000 or cal_raw > 5000 else 1.0

            return {
                "nombre": item.get('Nombre') or item.get('Código / Nombre'),
                "descripcion": item.get('Descripción') or item.get('Descripcion') or '',
                "peso": float(peso_raw) / factor,
                "calorias": float(cal_raw) / factor,
                "proteinas": float(prot_raw) / factor,
                "grasas": float(gras_raw) / factor,
                "carbohidratos": float(carb_raw) / factor,
                "fibras": float(fibr_raw) / factor
            }

    return None

def analizar_con_groq(prompt_text):
    if not client_ai:
        raise Exception("GROQ_API_KEY no está configurada correctamente.")
    
    system_prompt = """Sos un nutricionista experto. Analizá el texto ingresado.
Devolvé EXCLUSIVAMENTE un JSON con este formato:
{
  "items": [
    {"alimento": "nombre", "peso": 0.0, "calorias": 0.0, "proteinas": 0.0, "grasas": 0.0, "carbohidratos": 0.0, "fibras": 0.0}
  ],
  "tipo": "Comida"
}"""

    response = client_ai.chat.completions.create(
        model=GROQ_TEXTO,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ],
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)
    
def analizar_imagen_con_groq(base64_image, user_caption=""):
    if not client_ai:
        raise Exception("GROQ_API_KEY no está configurada correctamente.")
    
    base_prompt = "Analizá esta imagen de comida/plato. Identificá los alimentos, estimá sus pesos en gramos y nutrientes. Respondé ÚNICAMENTE en formato JSON con la clave 'items' conteniendo alimento, peso, calorias, proteinas, grasas, carbohidratos, fibras."
    
    if user_caption.strip():
        prompt = f"{base_prompt}\n\nNota o aclaración enviada por el usuario sobre esta foto: '{user_caption.strip()}'"
    else:
        prompt = base_prompt

    response = client_ai.chat.completions.create(
        model=GROQ_FOTO,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
        ],
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

def generar_pdf_comidas_bytes(plantillas):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1E3A8A'))
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#1E293B'))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8.5, leading=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)

    story = [
        Paragraph("<b>LISTADO DE COMIDAS PREDETERMINADAS</b>", title_style),
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=12),
    ]

    if not plantillas:
        story.append(Paragraph("No hay comidas predeterminadas cargadas en la hoja 'Plantillas_Comidas'.", body_style))
    else:
        table_data = [[
            Paragraph("Nombre", header_style), 
            Paragraph("Descripción", header_style), 
            Paragraph("Peso (g)", header_style), 
            Paragraph("Kcal", header_style), 
            Paragraph("Prot (g)", header_style), 
            Paragraph("Gras (g)", header_style), 
            Paragraph("Carb (g)", header_style), 
            Paragraph("Fibr (g)", header_style)
        ]]
        
        for p in plantillas:
            table_data.append([
                Paragraph(str(p.get("Nombre", "")), body_style),
                Paragraph(str(p.get("Descripcion") or p.get("Momento", "")), body_style),
                Paragraph(f"{p.get('Peso', 0):.1f}", body_style),
                Paragraph(f"{p.get('Calorias', 0):.1f}", body_style),
                Paragraph(f"{p.get('Proteinas', 0):.1f}", body_style),
                Paragraph(f"{p.get('Grasas', 0):.1f}", body_style),
                Paragraph(f"{p.get('Carbohidratos', 0):.1f}", body_style),
                Paragraph(f"{p.get('Fibras', 0):.1f}", body_style)
            ])
        
        t = Table(table_data, colWidths=[100, 150, 45, 45, 45, 45, 45, 35])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4)
        ]))
        story.append(t)

    doc.build(story)
    buffer.seek(0)
    return buffer

# =======================================================================================================================================================
#                   FINAL                                   OPERACION COMIDAS                                           FINAL
# =======================================================================================================================================================
#========================================================================================================================================================
#                INICIO                             MANEJADORES HANDLE 2026 08 22                INICIO
#==============================================================================================================================================================

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🎙️ Procesando audio con IA...")
    try:
        file = await context.bot.get_file(update.message.voice.file_id)
        audio_bytes = await file.download_as_bytearray()
        
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.ogg"
        
        transcription = client_ai.audio.transcriptions.create(
            file=(audio_file.name, audio_file.read()),
            model= GROQ_AUDIO,
            response_format="text"
        )
        
        data = analizar_con_groq(transcription)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        await msg.edit_text(f"❌ Error al procesar audio: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📸 Analizando foto con Inteligencia Artificial...")
    try:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        base64_image = base64.b64encode(photo_bytes).decode('utf-8')
        
        user_caption = update.message.caption or ""
        
        data = analizar_imagen_con_groq(base64_image, user_caption)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        await msg.edit_text(f"❌ Error al procesar imagen: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    raw_text = update.message.text.strip() if update.message and update.message.text else ""

    if not raw_text:
        return


# ========================================================================================================
    # A. SI EL USUARIO PRESIONÓ "SELECCIONAR FECHA" EN /diario   2026 08 20
    # ==================================================================================================
    if context.user_data.get('awaiting_diario_custom_date'):
        fecha_parseada = None
        txt = raw_text.replace('/', '-').replace('.', '-')
        partes = txt.split('-')
        
        try:
            if len(partes) == 3:
                if len(partes[0]) == 4: # AAAA-MM-DD
                    fecha_parseada = f"{int(partes[0]):04d}-{int(partes[1]):02d}-{int(partes[2]):02d}"
                else: # DD-MM-AAAA
                    fecha_parseada = f"{int(partes[2]):04d}-{int(partes[1]):02d}-{int(partes[0]):02d}"
            elif len(partes) == 2: # DD-MM
                anio_actual = obtener_ahora_arg().year
                fecha_parseada = f"{anio_actual:04d}-{int(partes[1]):02d}-{int(partes[0]):02d}"
        except Exception:
            fecha_parseada = None

        msg_solic = context.user_data.pop('msg_solicitud_diario_fecha_id', None)
        if msg_solic:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_solic)
            except Exception:
                pass

        try:
            await update.message.delete()
        except Exception:
            pass

        if fecha_parseada:
            context.user_data['awaiting_diario_custom_date'] = False
            # Se envía update.message para asegurar respuesta directa
            await mostrar_diario_fecha(update.message, user_id, fecha_parseada)
            return
        else:
            msg_err = await update.message.reply_text("⚠️ Formato de fecha inválido. Ingrese nuevamente (Ej: `2026-08-15` o `15/08`):", parse_mode="Markdown")
            context.user_data['msg_solicitud_diario_fecha_id'] = msg_err.message_id
            return
            
    # =========================================================================
    # B. SI EL USUARIO PRESIONÓ "OTRO DÍA" EN EL MENÚ DE CONFIRMACIÓN DE INGESTA
    # =========================================================================
    if context.user_data.get('awaiting_custom_date'):
        fecha_parseada = None
        txt = raw_text.replace('/', '-').replace('.', '-')
        partes = txt.split('-')
        
        try:
            if len(partes) == 3:
                if len(partes[0]) == 4: # AAAA-MM-DD
                    fecha_parseada = f"{int(partes[0]):04d}-{int(partes[1]):02d}-{int(partes[2]):02d}"
                else: # DD-MM-AAAA
                    fecha_parseada = f"{int(partes[2]):04d}-{int(partes[1]):02d}-{int(partes[0]):02d}"
            elif len(partes) == 2: # DD-MM
                anio_actual = obtener_ahora_arg().year
                fecha_parseada = f"{anio_actual:04d}-{int(partes[1]):02d}-{int(partes[0]):02d}"
        except Exception:
            fecha_parseada = None

        msg_solic = context.user_data.pop('msg_solicitud_fecha_id', None)
        if msg_solic:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_solic)
            except Exception:
                pass

        try:
            await update.message.delete()
        except Exception:
            pass

        if fecha_parseada:
            context.user_data['pending_fecha'] = fecha_parseada
            context.user_data['awaiting_custom_date'] = False
            
            last_menu_msg_id = context.user_data.get('last_menu_msg_id')
            if last_menu_msg_id:
                try:
                    target_msg = await context.bot.get_message(chat_id=chat_id, message_id=last_menu_msg_id)
                    await render_confirmation_screen(target_msg, context)
                    return
                except Exception:
                    pass
            
            msg = await update.message.reply_text("📋 Actualizando menú...")
            context.user_data['last_menu_msg_id'] = msg.message_id
            await render_confirmation_screen(msg, context)
            return
        else:
            msg_err = await update.message.reply_text("⚠️ Formato de fecha inválido. Ingrese nuevamente (Ej: `2026-08-15` o `15/08`):", parse_mode="Markdown")
            context.user_data['msg_solicitud_fecha_id'] = msg_err.message_id
            return

    # =========================================================================
    # 0. DETECCIÓN DE ACTIVIDAD FÍSICA DIRECTA CON PREFIJO '#'
    # =========================================================================
    if raw_text.startswith('#'):
        contenido = raw_text[1:].strip()
        
        if ',' in contenido:
            partes = contenido.rsplit(',', 1)
            descripcion = partes[0].strip()
            try:
                kcal_ingresadas = float(re.sub(r'[^\d.]', '', partes[1].replace(',', '.')))
            except ValueError:
                kcal_ingresadas = 0.0
        else:
            descripcion = contenido
            kcal_ingresadas = 0.0

        calorias_finales = -abs(kcal_ingresadas) 

        item_actividad = {
            "alimento": descripcion,
            "peso": 0,
            "calorias": calorias_finales,
            "proteinas": 0,
            "grasas": 0,
            "carbohidratos": 0,
            "fibras": 0
        }

        context.user_data['pending_items'] = [item_actividad]
        context.user_data['pending_fecha'] = obtener_ahora_arg().strftime("%Y-%m-%d")
        context.user_data['pending_momento'] = 'Actividad'

        msg = await update.message.reply_text("🏃 Registrando actividad...")
        context.user_data['last_menu_msg_id'] = msg.message_id
        await render_confirmation_screen(msg, context)
        return

    # =========================================================================
    # 1. SI EL USUARIO PRESIONÓ "EDITAR" Y ESTÁ ENVIANDO LA CORRECCIÓN
    # =========================================================================
    if context.user_data.get('awaiting_edit_item_val'):
        idx = context.user_data.get('editing_item_idx')
        items = context.user_data.get('pending_items', [])

        if items and 0 <= idx < len(items):
            item_previo = items[idx]
            peso_previo = item_previo.get('peso', 0.0)

            msg_espera = await update.message.reply_text("⏳ Recalculando ítem con la IA...")
            try:
                prompt_edicion = (
                    f"El usuario quiere editar un alimento.\n"
                    f"Texto ingresado por el usuario: '{raw_text}'\n"
                    f"Si el usuario NO especificó un nuevo peso en gramos en su texto, "
                    f"DEBES usar exactamente este peso anterior: {peso_previo} gramos.\n"
                    f"Devolvé el JSON con los nutrientes recalculados para ese alimento y cantidad."
                )

                nuevo_analisis = analizar_con_groq(prompt_edicion)
                items_nuevos = nuevo_analisis.get('items', [])

                if items_nuevos:
                    items[idx] = items_nuevos[0]
                    context.user_data['pending_items'] = items
                    await msg_espera.delete()
                    try:
                        await update.message.delete()
                    except Exception:
                        pass
                else:
                    await msg_espera.edit_text("⚠️ No se pudieron interpretar los datos para actualizar el ítem.")

            except Exception as e:
                print(f"Error editando ítem: {e}")
                await msg_espera.edit_text(f"❌ Error al procesar la edición: {e}")

        context.user_data['awaiting_edit_item_val'] = False
        context.user_data.pop('editing_item_idx', None)

        last_menu_msg_id = context.user_data.get('last_menu_msg_id')
        if last_menu_msg_id:
            try:
                target_msg = await context.bot.get_message(chat_id=chat_id, message_id=last_menu_msg_id)
                await render_confirmation_screen(target_msg, context)
            except Exception:
                nuevo_menu_msg = await update.message.reply_text("📋 Actualizando menú...")
                context.user_data['last_menu_msg_id'] = nuevo_menu_msg.message_id
                await render_confirmation_screen(nuevo_menu_msg, context)
        else:
            await render_confirmation_screen(update, context)
        return


# =========================================================================
    # 2. COMIDAS PRECARGADAS EN PLANTILLAS DEL USUARIO (MENSAJES QUE EMPIEZAN CON *)
    # =========================================================================
    if raw_text.startswith('*'):
        contenido = raw_text[1:].strip()
        partes = [p.strip() for p in contenido.split(',')]
        nombre_plantilla = partes[0].upper()
        multiplicador = float(partes[1]) if len(partes) > 1 else 1.0

        plantillas = obtener_comidas_usuario(user_id)
        plantilla_encontrada = None
        for p in plantillas:
            nombre_item = str(p.get('Código / Nombre') or p.get('Nombre') or '').strip().upper()
            if nombre_item == nombre_plantilla:
                plantilla_encontrada = p
                break

        if plantilla_encontrada:
            p_base = parse_raw_val(plantilla_encontrada.get('Peso', 0))
            c_base = parse_raw_val(plantilla_encontrada.get('Calorias', 0))
            pr_base = parse_raw_val(plantilla_encontrada.get('Proteinas', 0))
            g_base = parse_raw_val(plantilla_encontrada.get('Grasas', 0))
            cb_base = parse_raw_val(plantilla_encontrada.get('Carbohidratos', 0))
            f_base = parse_raw_val(plantilla_encontrada.get('Fibras', 0))

            val_descripcion = None
            for k, v in plantilla_encontrada.items():
                if str(k).strip().lower() in ['descripcion', 'descripción']:
                    val_descripcion = v
                    break

            texto_base = str(val_descripcion).strip() if val_descripcion else str(plantilla_encontrada.get('Nombre', 'Comida')).strip()
            
            # Barremos por completo CUALQUIER símbolo § previo que estuviera guardado en la celda origen
            texto_base = texto_base.replace('§', '').strip()
            
            if texto_base.startswith('(x'):
                if ')' in texto_base:
                    texto_base = texto_base.split(')', 1)[1].strip()

            multiplicador_str = f"{int(multiplicador)}" if multiplicador.is_integer() else f"{multiplicador}"
            
            # Pantalla limpia sin símbolo raro ni multiplicadores extra
            nombre_pantalla = f"(x{multiplicador_str}) {texto_base}"
            
            # Excel con un ÚNICO símbolo § al final absoluto
            nombre_sheets = f"(x{multiplicador_str}) {texto_base} §"

            item_generado = {
                "alimento": nombre_sheets,
                "alimento_display": nombre_pantalla,
                "peso": p_base * multiplicador,
                "calorias": c_base * multiplicador,
                "proteinas": pr_base * multiplicador,
                "grasas": g_base * multiplicador,
                "carbohidratos": cb_base * multiplicador,
                "fibras": f_base * multiplicador,
                "multiplicador": multiplicador
            }
            
            data_json = {"items": [item_generado], "tipo": "Comida"}
            msg = await update.message.reply_text("⏳ Procesando comida predeterminada...")
            await procesar_y_mostrar_confirmacion(data_json, msg, context)
            return
        else:
            await update.message.reply_text(f"❌ No se encontró la comida `*{nombre_plantilla}` en tu planilla `Comidas_{user_id}`.", parse_mode="Markdown")
            return  
                                  
    # =========================================================================
    # 3. INGRESO DIRECTO DE COMIDA POR TEXTO LIBRE (IA)
    # =========================================================================
    msg = await update.message.reply_text("🤖 Analizando texto con Inteligencia Artificial...")
    try:
        data = analizar_con_groq(raw_text)
        items = data.get("items", [])

        total_calorias = sum(float(item.get("calorias", 0)) for item in items)
        total_peso = sum(float(item.get("peso", 0)) for item in items)

        if not items or (total_calorias == 0 and total_peso == 0):
            await msg.delete()
            return

        await procesar_y_mostrar_confirmacion(data, msg, context)

    except Exception as e:
        await msg.edit_text(f"❌ Error al procesar el texto: {e}")   

#=================================================================================================================================================

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    context.user_data['last_menu_msg_id'] = query.message.message_id

    if data.startswith("set_m_"):
        nuevo_momento = data.replace("set_m_", "")
        context.user_data['pending_momento'] = nuevo_momento
        await render_confirmation_screen(query, context)

    elif data == "set_d_hoy":
        context.user_data['pending_fecha'] = obtener_ahora_arg().strftime("%Y-%m-%d")
        await render_confirmation_screen(query, context)

    elif data == "set_d_ayer":
        context.user_data['pending_fecha'] = (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d")
        await render_confirmation_screen(query, context)

    elif data in ["set_d_otro", "set_d_custom"]:
        context.user_data['awaiting_custom_date'] = True
        msg_solic = await query.message.reply_text("📅 Ingresá la fecha deseada para la ingesta (Ej: `2026-08-15` o `15/08`):", parse_mode="Markdown")
        context.user_data['msg_solicitud_fecha_id'] = msg_solic.message_id

    elif data == "diario_otro":
        context.user_data['awaiting_diario_custom_date'] = True
        msg_solic = await query.message.reply_text("📅 Ingresá la fecha del diario que querés consultar (Ej: `2026-08-15` o `15/08`):", parse_mode="Markdown")
        context.user_data['msg_solicitud_diario_fecha_id'] = msg_solic.message_id

    elif data.startswith("edit_item_"):
        idx = int(data.replace("edit_item_", "")) - 1
        context.user_data['awaiting_edit_item_val'] = True
        context.user_data['editing_item_idx'] = idx
        await query.message.reply_text("✏️ Ingresá la nueva descripción o peso para este ítem:")

    elif data.startswith("del_item_"):
        idx = int(data.replace("del_item_", "")) - 1
        items = context.user_data.get('pending_items', [])
        if 0 <= idx < len(items):
            items.pop(idx)
            context.user_data['pending_items'] = items
        if not items:
            await query.edit_message_text("❌ Todos los ítems fueron eliminados.")
            context.user_data.pop('last_menu_msg_id', None)
        else:
            await render_confirmation_screen(query, context)

    elif data == "cancel_entry":
        context.user_data.pop('pending_items', None)
        context.user_data.pop('last_menu_msg_id', None)
        await query.edit_message_text("🗑️ Registro cancelado.")

    elif data == "confirm_save":
        items = context.user_data.get('pending_items', [])
        fecha = context.user_data.get('pending_fecha')
        momento = context.user_data.get('pending_momento')

        if items and fecha and momento:
            tipo_registro = "Actividad" if momento == "Actividad" else "Comida"
            
            guardar_en_sheets(user_id, items, fecha, momento, tipo=tipo_registro)
            
            if momento == "Actividad":
                txt_confirmacion = f"✅ **¡Actividad guardada exitosamente!**\n📅 `{fecha}`"
            else:
                txt_confirmacion = f"✅ **¡Ingesta guardada exitosamente!**\n📅 `{fecha}` | `{momento}`"

            await query.edit_message_text(txt_confirmacion, parse_mode="Markdown")
            context.user_data.pop('pending_items', None)
            context.user_data.pop('last_menu_msg_id', None)
        else:
            await query.edit_message_text("❌ No se encontraron datos para guardar.")

    elif data == "diario_hoy":
        fecha = obtener_ahora_arg().strftime("%Y-%m-%d")
        await mostrar_diario_fecha(query, user_id, fecha)

    elif data == "diario_ayer":
        fecha = (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d")
        await mostrar_diario_fecha(query, user_id, fecha)

    elif data.startswith("resumen_mes_20"):
        mes_str = data.replace("resumen_mes_", "")
        await mostrar_resumen_mes(query, user_id, mes_str)

    elif data.startswith("descargar_pdf_resumen_"):
        mes_str = data.replace("descargar_pdf_resumen_", "")
        await generar_y_enviar_pdf_resumen(query, user_id, mes_str, context)

    elif data.startswith("descargar_pdf_diario_"):
        fecha_str = data.replace("descargar_pdf_diario_", "")
        df = obtener_datos_usuario(user_id)
        df_diario = df[df['Fecha'] == fecha_str] if not df.empty else pd.DataFrame()
        pdf_bytes = generar_pdf_diario_bytes(fecha_str, df_diario, user_id)
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=pdf_bytes,
            filename=f"Diario_Ingestas_{fecha_str}.pdf"
        )

    elif data.startswith("descargar_pdf_presion_"):
        mes_str = data.replace("descargar_pdf_presion_", "")
        await generar_y_enviar_pdf_presion(query, user_id, mes_str, context)

#==============================================================================================================================================================
#                FINAL                                     MANEJADORES HANDLE                                    FINAL
#==============================================================================================================================================================

# =============================================================================================================================================================
#                    INICIO                                    MENSAJES PROGRAMADOS  2026 08 20                              INICIO
# ==============================================================================================================================================================

def extraer_val(texto: str) -> float:
    """
    Equivalente al VAL() de BASIC: busca el primer número (entero o decimal)
    en la cadena y lo devuelve como float. Si no halla números, retorna 0.0.
    """
    if not texto:
        return 0.0
    
    coincidencia = re.search(r'(\d+(?:[.,]\d+)?)', str(texto))
    if coincidencia:
        num_str = coincidencia.group(1).replace(',', '.')
        try:
            return float(num_str)
        except ValueError:
            return 0.0
    return 0.0

async def registrar_log_en_sheet(sh, contexto: str, detalle: str):
    """
    Registra errores en la pestaña 'Logs' de Google Sheets.
    """
    try:
        try:
            sheet_logs = sh.worksheet("Logs")
        except Exception:
            sheet_logs = sh.add_worksheet(title="Logs", rows="1000", cols="3")
            sheet_logs.append_row(["Fecha y Hora", "Contexto / Módulo", "Detalle del Error"])

        ahora_str = obtener_ahora_arg().strftime("%Y-%m-%d %H:%M:%S")
        sheet_logs.append_row([ahora_str, contexto, str(detalle)])
    except Exception as e_log:
        logger.error(f"Error secundario al intentar registrar en Logs: {e_log}")


def _verificar_aviso_peso(user_id: int, ahora_dt) -> str:
    """
    Verifica si el usuario actualizó su peso este mes comparando la cadena del texto
    guardada en 'Ultimo Mes Peso' (ejemplo: '2026-08').
    """
    DIA_INICIO_AVISO = 5
    if ahora_dt.day < DIA_INICIO_AVISO:
        return ""

    # Formato esperado: "2026-08"
    mes_actual_str = ahora_dt.strftime("%Y-%m")

    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        sheet_usuarios = sh.worksheet("Usuarios")
        registros = sheet_usuarios.get_all_records()

        for u in registros:
            raw_id = u.get("User ID")
            if raw_id and str(raw_id).strip() == str(user_id):
                # Extraer el valor y limpiar comillas simples o espacios
                val_celda = str(u.get("Ultimo Mes Peso") or u.get("Último Mes Peso") or "").strip()
                ultimo_mes = val_celda.replace("'", "")
                
                # Si la cadena coincide exacto con el mes en curso ("2026-08"), está al día
                if ultimo_mes == mes_actual_str:
                    return ""
                break
    except Exception as e:
        logger.error(f"Error al verificar peso para mensaje programado User {user_id}: {e}")

    # Notificación con el comando correcto
    return (
        "\n\n⚠️ **Recordatorio de Peso del Mes:**\n"
        "Aún no registraste tu peso correspondiente a este mes. "
        "Ten en cuenta que las funciones `/diario` y `/resumen` **quedarán pausadas** "
        "hasta que actualices tu peso usando `/perfil`PESO."
    )


async def ejecutar_recordatorio_comidas(context, momento: str):
    """
    Verifica y envía alertas de comidas pendientes y resumen semanal.
    - momento == 'manana': Revisa anteayer y ayer. Si es MARTES, genera y envía
                           el resumen semanal de la semana anterior (lunes a domingo pasados).
    - momento == 'tarde': Revisa ayer entero y hoy (Desayuno y Almuerzo).
    Incluye aviso automático de peso mensual si se está a partir del día 5 sin actualizar.
    """
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        
        sheet_usuarios = sh.worksheet("Usuarios")
        registros_usuarios = sheet_usuarios.get_all_records()
        
        usuarios_validos = []
        metas_usuarios = {} 
        
        for u in registros_usuarios:
            estado = str(u.get("Estado", "")).strip().lower()
            notif = str(u.get("Notificaciones", "")).strip().lower()
            raw_user_id = u.get("User ID")
            
            if estado == "activo" and notif in ["si", "sí"] and raw_user_id:
                try:
                    uid_int = int(raw_user_id)
                    usuarios_validos.append(uid_int)
                    metas_usuarios[uid_int] = {
                        "calorias_ideal": u.get("Calorias_Objetivo"),
                        "proteinas_ideal": u.get("Proteinas_Objetivo")
                    }
                except ValueError:
                    continue

    except Exception as e:
        logger.error(f"Error al acceder a la pestaña 'Usuarios': {e}")
        return

    # Cálculo de fechas con hora de Argentina
    ahora_dt = obtener_ahora_arg()
    hoy = ahora_dt.date() if hasattr(ahora_dt, "date") else ahora_dt
    ayer = hoy - timedelta(days=1)
    anteayer = hoy - timedelta(days=2)

    str_hoy = hoy.strftime("%Y-%m-%d")
    str_ayer = ayer.strftime("%Y-%m-%d")
    str_anteayer = anteayer.strftime("%Y-%m-%d")

    todas_comidas = ["Desayuno", "Almuerzo", "Merienda", "Cena"]

    # Identificar si es MARTES por la mañana (1 = Martes en Python)
    es_martes_manana = (hoy.weekday() == 1 and momento == 'manana')

    # Rango de la semana anterior (lunes a domingo pasados)
    if es_martes_manana:
        lunes_pasado = hoy - timedelta(days=8)
        fechas_semana_pasada = set(
            (lunes_pasado + timedelta(days=i)).strftime("%Y-%m-%d") 
            for i in range(7)
        )

    for user_id in usuarios_validos:
        try:
            nombre_hoja_usuario = f"User_{user_id}"
            sheet_usuario = sh.worksheet(nombre_hoja_usuario)
            registros_comidas = sheet_usuario.get_all_records()

            comidas_anteayer = set()
            comidas_ayer = set()
            comidas_hoy = set()

            calorias_totales = 0.0
            proteinas_totales = 0.0
            minutos_ejercicio = 0.0
            dias_con_registro = set()

            for reg in registros_comidas:
                fecha_reg = str(reg.get("Fecha", "")).strip()
                momento_actividad = str(reg.get("Momento/Actividad") or reg.get("Momento", "")).strip()
                momento_reg = momento_actividad.capitalize()

                if fecha_reg == str_anteayer:
                    comidas_anteayer.add(momento_reg)
                elif fecha_reg == str_ayer:
                    comidas_ayer.add(momento_reg)
                elif fecha_reg == str_hoy:
                    comidas_hoy.add(momento_reg)

                # -------------------------------------------------------------
                # ACUMULACIÓN PARA RESUMEN SEMANAL (MARTES MAÑANA)
                # -------------------------------------------------------------
                if es_martes_manana and fecha_reg in fechas_semana_pasada:
                    es_actividad = "actividad" in momento_actividad.lower() or "ejercicio" in momento_actividad.lower()

                    if es_actividad:
                        # Extraemos texto de Descripción o Momento/Actividad
                        desc = str(reg.get("Descripción") or reg.get("Descripcion") or momento_actividad)
                        # Aplica extracción tipo VAL()
                        minutos_ejercicio += extraer_val(desc)
                    else:
                        try:
                            val_cal = reg.get("Calorías (kcal)") or reg.get("Calorias") or 0
                            val_prot = reg.get("Proteínas (g)") or reg.get("Proteinas") or 0
                            
                            cal = float(str(val_cal).replace(",", ".")) if str(val_cal).strip() else 0.0
                            prot = float(str(val_prot).replace(",", ".")) if str(val_prot).strip() else 0.0
                            
                            if cal > 0 or prot > 0:
                                calorias_totales += cal
                                proteinas_totales += prot
                                dias_con_registro.add(fecha_reg)
                        except (ValueError, TypeError):
                            pass

            # Generar texto de aviso de peso (si aplica: día >= 5 y sin peso del mes)
            aviso_peso_str = _verificar_aviso_peso(user_id, ahora_dt)

            # -----------------------------------------------------------------
            # ENVÍO DEL RESUMEN SEMANAL CON GROQ (MARTES A LA MAÑANA)
            # -----------------------------------------------------------------
            if es_martes_manana:
                try:
                    cant_dias_reg = len(dias_con_registro) if len(dias_con_registro) > 0 else 7
                    prom_calorias = round(calorias_totales / cant_dias_reg, 1)
                    prom_proteinas = round(proteinas_totales / cant_dias_reg, 1)

                    perfil = obtener_perfil_usuario(user_id)
                    tmb_str = "No registrado"
                    get_str = "No registrado"

                    if perfil and perfil.get('Peso') and perfil.get('Altura') and perfil.get('Edad'):
                        tmb, get_val = calcular_tmb_y_get(
                            peso_actual=perfil.get('Peso'),
                            altura_cm=perfil.get('Altura'),
                            edad=perfil.get('Edad'),
                            genero=perfil.get('Sexo', 'masculino'),
                            actividad=perfil.get('Ocupacion', 'sedentario')
                        )
                        tmb_str = f"{int(tmb)} kcal"
                        get_str = f"{int(get_val)} kcal"

                    meta_cal = metas_usuarios.get(user_id, {}).get("calorias_ideal") or get_str
                    meta_prot = metas_usuarios.get(user_id, {}).get("proteinas_ideal") or "Consumo adecuado"

                    prompt_ia = (
                        f"Sos un coach nutricional y deportivo. Analizá los datos de la semana pasada (Lunes a Domingo) del usuario:\n\n"
                        f"- TMB: {tmb_str} | GET: {get_str}\n"
                        f"- Promedio Calorías: {prom_calorias} kcal/día (Días registrados: {cant_dias_reg}/7 | Meta: {meta_cal})\n"
                        f"- Promedio Proteínas: {prom_proteinas} g/día (Meta: {meta_prot})\n"
                        f"- Ejercicio acumulado: {int(minutos_ejercicio)} minutos (Meta ideal: 180 min).\n\n"
                        f"Redactá un resumen semanal motivador, amigable, claro y directo formateado en Markdown para Telegram con emojis."
                    )

                    evaluacion_ia = ""
                    if client_ai:
                        try:
                            respuesta_ia = client_ai.chat.completions.create(
                                model= GROQ_TEXTO,
                                messages=[{"role": "user", "content": prompt_ia}],
                                temperature=0.7,
                                max_tokens=400
                            )
                            evaluacion_ia = respuesta_ia.choices[0].message.content.strip()
                        except Exception as e_groq:
                            logger.error(f"Error Groq para {user_id}: {e_groq}")
                            await registrar_log_en_sheet(sh, f"Error Groq User {user_id}", e_groq)

                    if not evaluacion_ia:
                        evaluacion_ia = (
                            f"📊 **Promedios de la semana pasada ({cant_dias_reg} días registrados):**\n"
                            f"• **Calorías:** {prom_calorias} kcal/día (GET: {get_str})\n"
                            f"• **Proteínas:** {prom_proteinas} g/día\n"
                            f"• **Actividad:** {int(minutos_ejercicio)} / 180 min."
                        )

                    # Anexar el aviso de peso al resumen semanal
                    texto_resumen_final = f"🗓️ **RESUMEN DE TU SEMANA PASADA**\n\n{evaluacion_ia}{aviso_peso_str}"

                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=texto_resumen_final,
                        parse_mode="Markdown"
                    )
                    logger.info(f"Resumen semanal (Martes) enviado exitosamente a {user_id}")

                except Exception as e_resumen:
                    logger.error(f"Error en resumen semanal de {user_id}: {e_resumen}")
                    await registrar_log_en_sheet(sh, f"Error Resumen Martes User {user_id}", e_resumen)

            # -----------------------------------------------------------------
            # REVISIÓN HABITUAL DE COMIDAS PENDIENTES
            # -----------------------------------------------------------------
            faltantes = []
            if momento == 'manana':
                for c in todas_comidas:
                    if c not in comidas_anteayer:
                        faltantes.append(f"{c} de anteayer ({str_anteayer})")
                for c in todas_comidas:
                    if c not in comidas_ayer:
                        faltantes.append(f"{c} de ayer ({str_ayer})")

            elif momento == 'tarde':
                for c in todas_comidas:
                    if c not in comidas_ayer:
                        faltantes.append(f"{c} de ayer ({str_ayer})")
                if "Desayuno" not in comidas_hoy:
                    faltantes.append("Desayuno de hoy")
                if "Almuerzo" not in comidas_hoy:
                    faltantes.append("Almuerzo de hoy")

            # Si hay comidas faltantes O si hay un aviso de peso pendiente por ser día >= 5
            if faltantes or (not es_martes_manana and aviso_peso_str):
                mensaje_recordatorio = ""
                
                if faltantes:
                    lista_formateada = "\n• " + "\n• ".join(faltantes)
                    mensaje_recordatorio = (
                        f"📌 **Recordatorio de comidas pendientes:**\n"
                        f"{lista_formateada}\n\n"
                        f"Si ya las consumiste, podés registrarlas en cualquier momento."
                    )
                
                # Anexar aviso de peso si no se envió en el resumen del martes
                if not es_martes_manana and aviso_peso_str:
                    if mensaje_recordatorio:
                        mensaje_recordatorio += f"\n{aviso_peso_str}"
                    else:
                        mensaje_recordatorio = f"🔔 **Aviso del sistema:**{aviso_peso_str}"

                await context.bot.send_message(
                    chat_id=int(user_id), 
                    text=mensaje_recordatorio, 
                    parse_mode="Markdown"
                )
                logger.info(f"Recordatorio ({momento}) enviado exitosamente a {user_id}")

        except Exception as e:
            logger.error(f"Error procesando usuario {user_id}: {e}")
            await registrar_log_en_sheet(sh, f"Procesando User {user_id}", e)


# ==================================================================================================================================================================================
#                    FINAL                                    MENSAJES PROGRAMADOS                                        FINAL
# ==================================================================================================================================================================================


# ==================================================================================================================================================================================
#                   INICIO                                        MAIN EXECUTION  2026 08 20                                      INICIO
# ===================================================================================================================================================================================

async def job_recordatorio_manana(context):
    """Tarea programada para el recordatorio matutino con protección contra fallas."""
    try:
        await ejecutar_recordatorio_comidas(context, momento='manana')
    except Exception as e:
        logger.error(f"❌ Error en job_recordatorio_manana: {e}")

async def job_recordatorio_tarde(context):
    """Tarea programada para el recordatorio vespertino con protección contra fallas."""
    try:
        await ejecutar_recordatorio_comidas(context, momento='tarde')
    except Exception as e:
        logger.error(f"❌ Error en job_recordatorio_tarde: {e}")

def main():
    # Inicia el servidor Web Flask en un hilo independiente
    threading.Thread(target=run_flask, daemon=True).start()

    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN no configurado.")
        return

    # Construcción de la aplicación del bot de Telegram
    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    job_queue = app_bot.job_queue
    tz = pytz.timezone('America/Argentina/Buenos_Aires')

    # Configuración de notificaciones automáticas diarias
    if job_queue is not None:
        job_queue.run_daily(
            job_recordatorio_manana, 
            time=time(hour=19, minute=40, second=0, tzinfo=tz),
            name="recordatorio_comidas_manana"
        )

        job_queue.run_daily(
            job_recordatorio_tarde, 
            time=time(hour=16, minute=0, second=0, tzinfo=tz),
            name="recordatorio_comidas_tarde"
        )
    else:
        print("⚠️ Advertencia: job_queue no está disponible. Verifique que 'python-telegram-bot[job-queue]' esté instalado.")

    # Handlers de Comandos
    app_bot.add_handler(CommandHandler("start", cmd_start))
    app_bot.add_handler(CommandHandler("comidas", cmd_comidas))
    app_bot.add_handler(CommandHandler("perfil", cmd_perfil))
    app_bot.add_handler(CommandHandler("presion", cmd_presion_handler))
    app_bot.add_handler(CommandHandler("diario", cmd_diario))
    app_bot.add_handler(CommandHandler("resumen", cmd_resumen))
    app_bot.add_handler(CommandHandler("receta", cmd_cargar_receta))

    # Handlers de Mensajes y Consultas
    app_bot.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app_bot.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app_bot.add_handler(CallbackQueryHandler(handle_callback_query))

    print("🤖 Bot Nutricional iniciado correctamente en Telegram con tareas programadas...")
    
    # Inicio del bot en loop de eventos asíncrono
    app_bot.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

# ==================================================================================================================================================================================
#                                   FINAL                                        MAIN EXECUTION                                        FINAL
# ===================================================================================================================================================================================

