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
import asyncio

from datetime import datetime, date, timedelta, time
import pytz
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from groq import Groq
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template_string
from functools import wraps

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
    "Desayuno": (8, 10),
    "Almuerzo": (12, 15),
    "Merienda": (17, 19),
    "Cena": (20, 24)
}

load_dotenv()

# Estados de conversación para Perfil y Fecha personalizada
AWAITING_PROFILE_DATA, AWAITING_CUSTOM_DATE, AWAITING_RESUMEN_MES, AWAITING_EDIT_ITEM = range(4)

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

# INSTANCIA DE FLASK (Necesaria antes de definir run_flask y las rutas)
app = Flask(__name__)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


# =====================================================================================================================================
#                FINAL                                   CABECERA                                       FINAL
# =====================================================================================================================================

# =====================================================================================================================================
#              INICIO                                  PAGINA WEB    2026 08 27                        INICIO  DB OK
# ======================================================================================================================================

app = Flask(__name__)

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
    """Guarda la fila calculada delegando completamente el acceso a datos."""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        fila = data.get('fila')

        if not user_id or not fila:
            return jsonify({"error": "Faltan parámetros obligatorios (user_id o fila)."}), 400

        # Llamada pura: La interfaz web solo pasa los datos y recibe el resultado
        codigo_unico = guardar_comida_precargada_db(user_id, fila)
        
        codigo_original = fila.get('nombre', '')
        msg_extra = f" con el código asignado '{codigo_unico}'" if codigo_unico != codigo_original else ""
        
        return jsonify({
            "status": "ok", 
            "codigo_guardado": codigo_unico,
            "message": f"Comida agregada en pestaña Comidas_{user_id}{msg_extra}."
        }), 200

    except Exception as e:
        logger.error(f"Error al guardar en Google Sheets: {e}")
        return jsonify({"error": str(e)}), 500

# =============================================================================================================================================
#                    FINAL                                   PAGINA WEB                                     FINAL
# =============================================================================================================================================

# ========================================================================================================================================
#                 INICIO                           GOOGLE SHEETS OPERACIONES                                      INICIO
# =============================================================================================================================================

# ---------------------------------------------------------------------------------------------------------------------------------------------
# 1. CLIENTES Y CONEXIÓN BASE (VAN PRIMERO)
# ---------------------------------------------------------------------------------------------------------------------------------------------

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

def get_user_worksheet(user_id):
    """
    Obtiene o crea una pestaña dinámica 'Comidas_<user_id>' dentro de la planilla.
    """
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    
    sheet_name = f"Comidas_{user_id}"
    ws = get_or_create_worksheet(sh, sheet_name)
    
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

# ---------------------------------------------------------------------------------------------------------------------------------------------
# 2. CONSULTAS Y DECORADORES DE USUARIO
# ---------------------------------------------------------------------------------------------------------------------------------------------

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

def requiere_registro(func):
    """Decorador que valida que el usuario figure registrado."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = str(update.effective_user.id).strip()
        perfil = obtener_perfil_usuario(update.effective_user.id) if 'obtener_perfil_usuario' in globals() else None
        
        # 1. Convertir si es un DataFrame de pandas
        if hasattr(perfil, 'to_dict'):
            perfil = perfil.to_dict(orient='records')[0] if not perfil.empty else {}

        es_valido = False

        if isinstance(perfil, dict) and perfil:
            # 2. Buscar el ID considerando el espacio ("User ID") y variantes
            id_encontrado = None
            for key in ['User ID', 'user_id', 'User_ID', 'ID', 'id', 'Telegram_ID']:
                if key in perfil and perfil[key] is not None:
                    id_encontrado = str(perfil[key]).split('.')[0].strip()
                    break

            # 3. Validar coincidencia de ID o existencia de perfil cargado
            if id_encontrado and id_encontrado == user_id:
                es_valido = True
            elif any(k in perfil for k in ['Nombre', 'Estado', 'Edad', 'Peso', 'Altura']):
                es_valido = True

        if not es_valido:
            mensaje_bloqueo = (
                "⚠️ **¡Aún no estás registrado!**\n\n"
                "Para poder utilizar este comando y acceder a tu plan nutricional, "
                "primero necesitás darte de alta en el sistema.\n\n"
                "👉 Usá el comando `/ingreso` o `/nuevo` para crear tu ficha en un par de pasos."
            )
            if update.message:
                await update.message.reply_text(mensaje_bloqueo, parse_mode="Markdown")
            elif update.callback_query:
                await update.callback_query.answer("⚠️ Registro requerido", show_alert=True)
                await update.callback_query.message.reply_text(mensaje_bloqueo, parse_mode="Markdown")
            return

        return await func(update, context, *args, **kwargs)
    return wrapper
    
    
# ---------------------------------------------------------------------------------------------------------------------------------------------
# 3. OPERACIONES DE PERSISTENCIA Y REGISTRO (LECTURA Y ESCRITURA)
# ---------------------------------------------------------------------------------------------------------------------------------------------

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

def guardar_comida_precargada_db(user_id, fila):
    ws = get_user_worksheet(user_id)
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
    return codigo_unico

def crear_nueva_cuenta_usuario_db(datos: dict):
    user_id = datos['user_id']
    ahora = datetime.now(ARG_TZ)
    mes_actual = ahora.strftime("%Y-%m")
    fecha_hoy = ahora.strftime("%Y-%m-%d")
    fecha_hora_str = ahora.strftime("%Y-%m-%d %H:%M:%S")

    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)

    # 1. Registro en Usuarios
    ws_usuarios = get_or_create_worksheet(sh, 'Usuarios')
    ws_usuarios.append_row([str(user_id), datos['nombre'], 'Activo', mes_actual, 'Si', fecha_hoy])

    # 2. Pestaña Perfil
    ws_perfil = get_or_create_worksheet(sh, f"Perfil_{user_id}")
    ws_perfil.append_row([
        int(datos['edad'] * 1000),
        int(datos['peso'] * 1000),
        int(datos['altura'] * 1000),
        datos['sexo'],
        datos['ocupacion'],
        mes_actual,
        fecha_hora_str,
        int(datos['peso_ideal'] * 1000),
        datos['cumple']
    ])

    # 3. Pestañas Diario, Presion y Comidas
    get_or_create_worksheet(sh, f"User_{user_id}")
    get_or_create_worksheet(sh, f"Presion_{user_id}")
    
    ws_comidas = get_or_create_worksheet(sh, f"Comidas_{user_id}")
    ws_comidas.append_row([
        'DESAYUNO',
        'Taza de leche descremada 2 tostada o 6 galletitas agua con queso blanco light y mermelada o dulce de leche §',
        340000, 332000, 14000, 7800, 49400, 2200
    ])

def obtener_datos_presion_db(user_id):
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
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                if (df[col] > 1000).any():
                    df[col] = df[col] / 1000.0

        if 'Fecha_Dia' in df.columns:
            df['Fecha_Dia'] = df['Fecha_Dia'].astype(str).str.strip()

        if 'Nota' not in df.columns:
            df['Nota'] = ""

        return df
    except Exception:
        return pd.DataFrame()

def guardar_presion_db(user_id, alta, baja, pulsaciones=None, nota=""):
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    ws = get_or_create_worksheet(sh, f"Presion_{user_id}")
    ahora = obtener_ahora_arg()
    
    val_pul = int(pulsaciones * 1000) if pulsaciones is not None else 0

    ws.append_row([
        ahora.strftime("%Y-%m-%d %H:%M:%S"), 
        ahora.strftime("%Y-%m-%d"), 
        int(alta * 1000), 
        int(baja * 1000), 
        val_pul,
        str(nota).strip()
    ])

def guardar_perfil_db(user_id, peso, mes=None, edad=None, altura=None, genero=None, ocupacion=None, *args, **kwargs):
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    ws = get_or_create_worksheet(sh, f"Perfil_{user_id}")
    ahora = obtener_ahora_arg()
    
    if not mes:
        mes = ahora.strftime("%Y-%m")
    
    records = ws.get_all_records()
    
    edad_raw = edad if edad is not None else 64000
    altura_raw = altura if altura is not None else 172000
    genero_final = genero if genero is not None else "masculino"
    ocupacion_final = ocupacion if ocupacion is not None else "Jubilado"
    peso_ideal_final = ""
    fecha_cumple_str = ""
    fila_a_actualizar = None

    if records:
        ultimo_registro = records[-1]
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

        for idx, row in enumerate(records, start=2):
            mes_en_fila = str(row.get('MES', row.get('Mes', ''))).strip()
            if mes_en_fila == str(mes):
                fila_a_actualizar = idx
                break

    nueva_fila = [
        str(edad_raw),
        to_sheet_int(peso),
        str(altura_raw),
        str(genero_final),
        str(ocupacion_final),
        str(mes),
        ahora.strftime("%Y-%m-%d %H:%M:%S"),
        str(peso_ideal_final),
        str(fecha_cumple_str)
    ]

    if fila_a_actualizar:
        ws.update(f"A{fila_a_actualizar}:I{fila_a_actualizar}", [nueva_fila])
    else:
        ws.append_row(nueva_fila)

    try:
        ws_usuarios = sh.worksheet("Usuarios")
        registros_usuarios = ws_usuarios.get_all_records()
        headers = ws_usuarios.row_values(1)
        
        col_idx = 4
        for idx, h in enumerate(headers, start=1):
            if str(h).strip().lower() in ["ultimo mes peso", "ultimo_mes_peso", "ultimomespeso"]:
                col_idx = idx
                break

        fila_usuario = None
        for i, reg in enumerate(registros_usuarios, start=2):
            id_reg = reg.get('ID') or reg.get('user_id') or reg.get('User ID') or list(reg.values())[0]
            if str(id_reg).strip() == str(user_id).strip():
                fila_usuario = i
                break

        if fila_usuario:
            from gspread.utils import rowcol_to_a1
            celda_a1 = rowcol_to_a1(fila_usuario, col_idx)
            ws_usuarios.update(celda_a1, [[str(mes)]])
    except Exception as e:
        print(f"❌ Error crítico al actualizar la pestaña 'usuarios': {e}")

def obtener_comidas_usuario(user_id):
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws = get_or_create_worksheet(sh, f"Comidas_{user_id}")
        records = ws.get_all_records()
        
        for p in records:
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

def extraer_val(texto: str) -> float:
    if not texto:
        return 0.0
    coincidencia = re.search(r'(\d+(?:[.,]\d+)?)', str(texto))
    if coincidencia:
        try:
            return float(coincidencia.group(1).replace(',', '.'))
        except ValueError:
            return 0.0
    return 0.0

async def registrar_log_en_sheet(sh, contexto: str, detalle: str):
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

# ======================================================================================================================================
#                    FINAL                              GOOGLE SHEETS OPERACIONES                      FINAL
# =======================================================================================================================================

# =============================================================================================================================================
#                       INICIO                     FUNCIONES AUXILIARES Y FORMATO                                   INICIO  
# =============================================================================================================================================

# ---------------------------------------------------------------------------------------------------------------------------------------------
# 1. PARSEO DE DATOS Y FECHAS (VAN PRIMERO POR SER UTILIZADOS EN OTRAS FUNCIONES)
# ---------------------------------------------------------------------------------------------------------------------------------------------

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
    elif time(10, 0) <= hora < time(13, 0):
        momento = "Colación"
    elif time(13, 0) <= hora < time(15, 0):
        momento = "Almuerzo"
    elif time(15, 0) <= hora < time(17, 0):
        momento = "Colación"
    elif time(17, 0) <= hora < time(20, 0):
        momento = "Merienda"
    else:
        momento = "Cena"
        
    return fecha_obj.strftime("%Y-%m-%d"), momento

# ---------------------------------------------------------------------------------------------------------------------------------------------
# 2. CÁLCULOS BIOMÉTRICOS Y MÉTRICAS
# ---------------------------------------------------------------------------------------------------------------------------------------------

def calcular_tmb_y_get(peso_actual: float, altura_cm: float, edad: int, genero: str = "masculino", actividad: str = "jubilado", peso_ideal: float = None) -> tuple[float, float]:
    """Calcula TMB (Mifflin-St Jeor) y GET (Gasto Energético Total)."""
    peso = float(peso_actual) if peso_actual and peso_actual > 0 else 70.0
    altura = float(altura_cm) if altura_cm and altura_cm > 0 else 170.0
    años = int(edad) if edad and edad > 0 else 40

    gen_clean = str(genero).strip().lower()
    if gen_clean in ["femenino", "f", "mujer", "female"]:
        tmb = (10.0 * peso) + (6.25 * altura) - (5.0 * años) - 161.0
    else:
        tmb = (10.0 * peso) + (6.25 * altura) - (5.0 * años) + 5.0

    act_clean = str(actividad).strip().lower()

    if any(k in act_clean for k in ["sedentario", "escritorio", "oficina", "jubilado", "reposo"]):
        factor_actividad = 1.2
    elif any(k in act_clean for k in ["ligero", "pie", "docente", "vendedor", "caminar"]):
        factor_actividad = 1.40
    elif any(k in act_clean for k in ["moderado", "mozo", "limpieza", "deporte"]):
        factor_actividad = 1.60
    elif any(k in act_clean for k in ["intenso", "construccion", "atleta", "fuerza"]):
        factor_actividad = 1.75
    elif any(k in act_clean for k in ["muy intenso", "cargador", "alto rendimiento"]):
        factor_actividad = 1.9
    else:
        factor_actividad = 1.40

    get = tmb * factor_actividad
    return tmb, get

def calcular_metricas_mensuales(df_mes, perfil_dict):
    """Procesa todos los cálculos mensuales garantizando consistencia y exactitud metabólica."""
    dias_registrados = df_mes['Fecha'].nunique() if (df_mes is not None and not df_mes.empty) else 1
    if dias_registrados == 0:
        dias_registrados = 1

    # 1. Sumatorias mensuales de consumo y ejercicio
    tot_cons_mes = float(df_mes[df_mes['Calorias'] > 0]['Calorias'].sum()) if df_mes is not None and 'Calorias' in df_mes.columns else 0.0
    tot_quem_mes = float(abs(df_mes[df_mes['Calorias'] < 0]['Calorias'].sum())) if df_mes is not None and 'Calorias' in df_mes.columns else 0.0

    # 2. Promedios diarios
    prom_cons = tot_cons_mes / dias_registrados
    prom_quem = tot_quem_mes / dias_registrados
    prom_bal_neto = prom_cons - prom_quem

    # 3. Macronutrientes totales
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

    # 4. Extracción de datos biométricos
    edad = int(get_perfil_num(['Edad', 'edad'], 64))
    altura = get_perfil_num(['Altura', 'altura'], 167.0)
    peso_actual = get_perfil_num(['Peso', 'peso'], 108.5)
    peso_ideal = get_perfil_num(['Peso_ideal', 'peso_ideal', 'Peso Ideal'], 75.0)
    
    genero = str(perfil_dict.get('GENERO') or perfil_dict.get('Genero') or perfil_dict.get('genero', 'masculino')).strip()
    ocupacion = str(perfil_dict.get('Ocupacion') or perfil_dict.get('ocupacion') or perfil_dict.get('actividad', 'ligero')).strip()

    # Peso de referencia (solo usado para definir las metas ideales de macros)
    peso_referencia = (peso_actual * 0.75) + (peso_ideal * 0.25)

    # 5. GASTO BASE REAL: Se calcula sobre el PESO ACTUAL REAL del organismo
    _, get_real = calcular_tmb_y_get(
        peso_actual=peso_actual, altura_cm=altura, edad=edad, genero=genero, actividad=ocupacion, peso_ideal=peso_ideal
    )

    # 6. GASTO META: Se calcula sobre el peso ponderado para fijar los objetivos de consumo
    _, get_meta = calcular_tmb_y_get(
        peso_actual=peso_referencia, altura_cm=altura, edad=edad, genero=genero, actividad=ocupacion, peso_ideal=peso_ideal
    )

    # --- CÁLCULO CORREGIDO DE DÉFICIT Y CAMBIO DE PESO ---
    # Gasto Total = GET Real (peso actual) + Ejercicio registrado
    gasto_diario_total = get_real + prom_quem

    # Balance diario: Consumidas menos Gastadas
    # Ej: Si consume 2282 y gasta 2683, balance_diario = -401 kcal (Déficit de 401)
    balance_diario = prom_cons - gasto_diario_total

    # Cambio de peso: Balance negativo representa descenso (-kg)
    cambio_peso_kg = (balance_diario * dias_registrados) / 7700.0
    deficit_diario_real = -balance_diario
    # ----------------------------------------------------

    # 7. Definición de Objetivos Ideales (Metas)
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
        "get_real": get_real,
        "deficit_diario_real": int(round(deficit_diario_real)),
        "cambio_peso_kg": cambio_peso_kg,
        "tot_cons": tot_cons_mes,
        "tot_quem": tot_quem_mes,
        "tot_prot": tot_prot,
        "tot_gras": tot_gras,
        "tot_carb": tot_carb,
        "tot_fibr": tot_fibr
    }
    
# ---------------------------------------------------------------------------------------------------------------------------------------------
# 3. INTEGRACIÓN CON IA (GROQ)
# ---------------------------------------------------------------------------------------------------------------------------------------------

def ejecutar_consulta_ia(prompt: str, max_tokens: int = 300, temperature: float = 0.4, system_prompt: str = None) -> str:
    """Función centralizada para consultas a la API de Groq."""
    try:
        client = globals().get('client_ai') or globals().get('groq_client')
        if not client:
            api_key = globals().get('GROQ_API_KEY') or os.getenv("GROQ_API_KEY")
            if not api_key:
                logger.error("⚠️ GROQ_API_KEY no configurada.")
                return ""
            from groq import Groq
            client = Groq(api_key=api_key)

        modelo = globals().get('GROQ_TEXTO', "llama-3.3-70b-versatile")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=modelo,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        if response and response.choices:
            content = response.choices[0].message.content
            return content.strip() if content else ""
            
    except Exception as e:
        logger.error(f"⚠️ Error en ejecución de IA: {e}")
        
    return ""

def obtener_recomendacion_ia(resumen_texto: str, es_semanal: bool = False) -> str:
    """Genera el análisis nutricional apoyándose en la función centralizada de IA."""
    if es_semanal:
        prompt = f"""
        Actúa como un coach nutricional breve y conciso.
        Analiza este resumen semanal:
        {resumen_texto}

        REGLAS OBLIGATORIAS:
        1. Escribe UN solo párrafo corto de análisis general (máximo 50 palabras).
        2. Agrega solo 3 recomendaciones breves en puntos (-).
        3. Extensión TOTAL máxima: 120 palabras.
        4. NO USES NUMERALES (##).
        5. Cierra siempre la última oración con punto final.
        """
        max_t = 350
    else:
        prompt = f"""
        Actúa como un nutricionista clínico personal realizando un análisis mensual completo.
        Analiza la información de tu paciente:
        {resumen_texto}

        REGLAS OBLIGATORIAS:
        1. PROHIBIDO REPETIR CIFRAS O METAS NUMÉRICAS.
        2. NO USES NUMERALES (##).
        3. Redacta 2 párrafos fluidos enfocados en saciedad, energía y recuperación.
        4. Cierra siempre la última oración con punto final.
        """
        max_t = 700

    system_msg = "Eres un nutricionista profesional y empático. Proporciona respuestas claras sin dejar oraciones inconclusas."
    res = ejecutar_consulta_ia(prompt, max_tokens=max_t, temperature=0.4, system_prompt=system_msg)
    
    if res:
        return res.replace("##", "").replace("###", "").strip()
        
    return "⚠️ No se pudo obtener el análisis nutricional en este momento."

# ---------------------------------------------------------------------------------------------------------------------------------------------
# 4. FUNCIONES DE LOGGING Y COMPONENTES DE INTERFAZ TELEGRAM
# ---------------------------------------------------------------------------------------------------------------------------------------------

async def log_error(contexto: str, excepcion: Exception, user_id: int = None):
    """Registra errores en consola y en Google Sheets."""
    mensaje_consola = f"Error en [{contexto}]"
    if user_id:
        mensaje_consola += f" - User ID: {user_id}"
    mensaje_consola += f": {excepcion}"

    logger.error(mensaje_consola)

    try:
        ctx_str = f"ERROR | {contexto}" + (f" (User {user_id})" if user_id else "")
        if 'registrar_log_en_sheet' in globals():
            await registrar_log_en_sheet(contexto=ctx_str, detalle=str(excepcion))
    except Exception as e_sheet:
        logger.error(f"Fallo secundario: No se pudo escribir el error en Google Sheets: {e_sheet}")

async def mostrar_diario_fecha(query_or_update, user_id, fecha_str):
    df = obtener_datos_usuario(user_id)
    responder = query_or_update.edit_message_text if hasattr(query_or_update, 'edit_message_text') else query_or_update.message.reply_text

    if df.empty or df[df['Fecha'] == fecha_str].empty:
        txt = f"📅 **Registro del día {fecha_str}:**\n\nNo hay registros guardados para este día."
        await responder(txt, parse_mode="Markdown")
        return

    df_diario = df[df['Fecha'] == fecha_str]
    momentos_dict = {}
    
    for _, row in df_diario.iterrows():
        momento = str(row.get("Momento", "General")).strip().title()
        concepto = str(row.get("Alimento", "")).strip()
        if concepto:
            momentos_dict.setdefault(momento, []).append(concepto)

    lineas_desglose = [f"• {m}: {', '.join(items)}" for m, items in momentos_dict.items()]
    tot_cons = df_diario[df_diario['Calorias'] > 0]['Calorias'].sum()
    tot_quem = abs(df_diario[df_diario['Calorias'] < 0]['Calorias'].sum())

    resumen_msg = (
        f"📅 **Registro del día {fecha_str}:**\n\n"
        + "\n".join(lineas_desglose) + "\n\n"
        f"🖥️ **Consumidas:** {tot_cons:.0f} kcal\n"
        f"🔥 **Quemadas:** {tot_quem:.0f} kcal\n"
        f"⚖️ **Balance Neto:** {tot_cons - tot_quem:.0f} kcal"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Descargar PDF del Diario", callback_data=f"descargar_pdf_diario_{fecha_str}")]
    ])

    await responder(resumen_msg, reply_markup=keyboard, parse_mode="Markdown")

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

# =============================================================================================================================================
#                FINAL                        FUNCIONES AUXILIARES Y FORMATO                                      FINAL
# =============================================================================================================================================

# ======================================================================================================================================
#                  INICIO                        INTERFAZ Y RENDER DE CONFIRMACIÓN                      INICIO  DB OK
# ======================================================================================================================================

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
    
# ======================================================================================================================================
#                  FINAL                        INTERFAZ Y RENDER DE CONFIRMACIÓN                      FINAL
# =====================================================================================================================================

# ======================================================================================================================================
#                 INICIO                            COMANDO MENSAJE SEMANAL  2026 08 23                  INICIO   DB OK
# =====================================================================================================================================

@requiere_registro
async def cmd_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        msg_espera = await update.message.reply_text("⏳ Analizando los días transcurridos con IA...")

        df_datos = obtener_datos_usuario(user_id) if 'obtener_datos_usuario' in globals() else pd.DataFrame()

        if df_datos.empty or 'Fecha' not in df_datos.columns:
            await msg_espera.edit_text("⚠️ No hay información de comidas registradas.")
            return

        df_datos['Fecha_dt'] = pd.to_datetime(df_datos['Fecha'])
        ahora = pd.Timestamp.now()
        dia_semana = ahora.weekday()  # 0: Lunes, 1: Martes, 2: Miércoles, 3: Jueves...

        # Lunes: toma la semana anterior completa (7 días)
        if dia_semana == 0:
            inicio_rango = ahora.floor('D') - pd.Timedelta(days=7)
            fin_rango = ahora.floor('D') - pd.Timedelta(seconds=1)
            etiqueta_periodo = "Semana Anterior (Lunes a Domingo)"
        else:
            # Martes en adelante: Desde el lunes hasta el día anterior a las 23:59:59
            inicio_rango = ahora.floor('D') - pd.Timedelta(days=dia_semana)
            fin_rango = ahora.floor('D') - pd.Timedelta(seconds=1)
            etiqueta_periodo = f"Semana Actual (Lunes a {ahora.strftime('%A')})"

        df_semana = df_datos[(df_datos['Fecha_dt'] >= inicio_rango) & (df_datos['Fecha_dt'] <= fin_rango)].copy()

        if df_semana.empty:
            await msg_espera.edit_text(f"⚠️ No hay registros acumulados para los días transcurridos de esta semana.")
            return

        perfil = obtener_perfil_usuario(user_id) if 'obtener_perfil_usuario' in globals() else {}
        m = calcular_metricas_mensuales(df_semana, perfil) if 'calcular_metricas_mensuales' in globals() else {}

        prompt_semana = (
            f"DATOS SEMANALES:\n"
            f"- Días evaluados: {m.get('dias_registrados', 0)}\n"
            f"- Consumo medio: {m.get('prom_cal', 0)} kcal/día (Objetivo: {m.get('ideal_cal', 0)} kcal)\n"
            f"- Proteínas: {m.get('prom_prot', 0)} g (Objetivo: {m.get('ideal_prot', 0)} g)\n"
            f"- Grasas: {m.get('prom_gras', 0)} g (Objetivo: {m.get('ideal_gras', 0)} g)\n"
            f"- Carbohidratos: {m.get('prom_carb', 0)} g (Objetivo: {m.get('ideal_carb', 0)} g)\n"
            f"- Fibra: {m.get('prom_fibr', 0)} g (Objetivo: {m.get('ideal_fibr', 0)} g)\n"
        )

        recomendacion = await asyncio.to_thread(obtener_recomendacion_ia, prompt_semana)

        txt = (
            f"📅 **Resumen Nutricional Semanal:**\n"
            f"• **Promedio diario consumido:** `{m.get('prom_cal', 0)} kcal` / Meta: `{m.get('ideal_cal', 0)} kcal`\n"
            f"• **Proteínas:** `{m.get('prom_prot', 0)} g` / Meta: `{m.get('ideal_prot', 0)} g`\n"
            f"• **Días Evaluados:** `{m.get('dias_registrados', 0)}`\n\n"
            f"🤖 **Análisis Nutricional:**\n"
            f"{recomendacion}"
        )

        await msg_espera.edit_text(txt, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en cmd_mensaje: {e}")
        if 'msg_espera' in locals():
            await msg_espera.edit_text(f"⚠️ Error al calcular resumen semanal: {e}")

                        
# ========================================================================================================================================
#                      FINAL                        COMANDO MENSAJE SEMANAL                    FINAL
# =======================================================================================================================================

# =====================================================================================================================================
#                       INICIO                  COMANDO INGRESO (ALTA DE USUARIO)                               INICIO
# ======================================================================================================================================

# Estados del flujo de conversación
ING_NOMBRE, ING_EDAD, ING_SEXO, ING_ALTURA, ING_PESO, ING_MUNECA, ING_OCUPACION, ING_CUMPLE = range(10, 18)

def calcular_contextura(sexo: str, altura_cm: float, muneca_cm: float) -> str:
    """Calcula la contextura física según la relación Altura / Muñeca."""
    if muneca_cm <= 0: return "Mediana"
    r = altura_cm / muneca_cm
    if sexo.upper() == 'M':
        if r > 10.4: return "Pequeña"
        elif 9.6 <= r <= 10.4: return "Mediana"
        else: return "Grande"
    else:
        if r > 11.0: return "Pequeña"
        elif 10.1 <= r <= 11.0: return "Mediana"
        else: return "Grande"

def calcular_peso_ideal(sexo: str, altura_cm: float) -> float:
    """Estimación de peso ideal mediante fórmula de Lorentz."""
    if sexo.upper() == 'M':
        return (altura_cm - 100) - ((altura_cm - 150) / 4.0)
    else:
        return (altura_cm - 100) - ((altura_cm - 150) / 2.5)

async def cmd_ingreso_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # --- VERIFICACIÓN DE USUARIO EXISTENTE ---
    perfil_existente = obtener_perfil_usuario(user_id) if 'obtener_perfil_usuario' in globals() else {}
    
    if perfil_existente and perfil_existente.get('nombre'):
        nombre_usr = perfil_existente.get('nombre', 'Usuario')
        await update.message.reply_text(
            f"ℹ️ **¡Ya tenés una cuenta activa, {nombre_usr}!**\n\n"
            f"Tu ficha ya está registrada en el sistema con el ID `{user_id}`.\n"
            "Podés consultar o actualizar tu información en cualquier momento con el comando `/perfil`.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    # --- SI NO EXISTE, INICIA LA SOLICITUD DE DATOS ---
    await update.message.reply_text(
        "📝 **Apertura de Ficha Nutricional**\n\n"
        "Vamos a registrar tus datos biométricos para inicializar tu cuenta.\n"
        "Por favor, indicá tu **Nombre y Apellido / Apodo**:",
        parse_mode="Markdown"
    )
    return ING_NOMBRE

async def cmd_nuevo_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await cmd_ingreso_start(update, context)

async def ing_recibir_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.text.strip()
    if len(nombre) < 2:
        await update.message.reply_text("⚠️ Por favor, ingresá un nombre válido.")
        return ING_NOMBRE
    
    context.user_data['ing_nombre'] = nombre
    await update.message.reply_text("Ingresá tu **edad** en años (ejemplo: `35`):", parse_mode="Markdown")
    return ING_EDAD

async def ing_recibir_edad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if not txt.isdigit() or not (10 <= int(txt) <= 110):
        await update.message.reply_text("⚠️ Por favor, ingresá una edad válida en números (ejemplo: `35`).")
        return ING_EDAD
    
    context.user_data['ing_edad'] = int(txt)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Masculino 👨", callback_data="sexo_M"),
         InlineKeyboardButton("Femenino 👩", callback_data="sexo_F")]
    ])
    await update.message.reply_text("Seleccioná tu **sexo biológico**:", reply_markup=keyboard, parse_mode="Markdown")
    return ING_SEXO

async def ing_recibir_sexo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    sexo = "M" if query.data == "sexo_M" else "F"
    context.user_data['ing_sexo'] = sexo
    
    await query.edit_message_text(
        f"Sexo registrado: *{'Masculino' if sexo == 'M' else 'Femenino'}*.\n\n"
        "Ahora ingresá tu **altura en centímetros** (ejemplo: `175` para 1,75 m):",
        parse_mode="Markdown"
    )
    return ING_ALTURA

async def ing_recibir_altura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().replace(',', '.')
    try:
        alt = float(txt)
        if not (100 <= alt <= 230): raise ValueError()
    except ValueError:
        await update.message.reply_text("⚠️ Ingresá una altura válida en centímetros (ejemplo: `170`).")
        return ING_ALTURA

    context.user_data['ing_altura'] = alt
    await update.message.reply_text("Ingresá tu **peso actual en kg** (ejemplo: `82.5`):", parse_mode="Markdown")
    return ING_PESO

async def ing_recibir_peso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().replace(',', '.')
    try:
        peso = float(txt)
        if not (30 <= peso <= 300): raise ValueError()
    except ValueError:
        await update.message.reply_text("⚠️ Ingresá un peso válido en kg (ejemplo: `75.4`).")
        return ING_PESO

    context.user_data['ing_peso'] = peso
    await update.message.reply_text(
        "Ingresá el **diámetro/perímetro de tu muñeca en cm** (ejemplo: `16.5`):\n"
        "_(Se utiliza para calcular tu contextura ósea)_",
        parse_mode="Markdown"
    )
    return ING_MUNECA

async def ing_recibir_muneca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().replace(',', '.')
    try:
        muneca = float(txt)
        if not (10 <= muneca <= 30): raise ValueError()
    except ValueError:
        await update.message.reply_text("⚠️ Ingresá un perímetro de muñeca válido en cm (ejemplo: `17`).")
        return ING_MUNECA

    context.user_data['ing_muneca'] = muneca
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Sedentario / Ligero", callback_data="ocup_ligero")],
        [InlineKeyboardButton("Moderado (Ejercicio 3x/sem)", callback_data="ocup_moderado")],
        [InlineKeyboardButton("Intenso / Trabajo Físico", callback_data="ocup_intenso")]
    ])
    await update.message.reply_text("Seleccioná tu **nivel de actividad u ocupación habitual**:", reply_markup=keyboard, parse_mode="Markdown")
    return ING_OCUPACION

async def ing_recibir_ocupacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    ocupacion = query.data.replace("ocup_", "")
    context.user_data['ing_ocupacion'] = ocupacion
    
    await query.edit_message_text(
        f"Nivel de actividad: *{ocupacion.capitalize()}*.\n\n"
        "Por último, ingresá tu **fecha de nacimiento** en formato `AAAA-MM-DD` (ejemplo: `1985-04-12`):",
        parse_mode="Markdown"
    )
    return ING_CUMPLE

async def ing_recibir_cumple(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cumple_str = update.message.text.strip()
    try:
        datetime.strptime(cumple_str, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("⚠️ Formato de fecha inválido. Usá el formato `AAAA-MM-DD` (ejemplo: `1990-08-25`).", parse_mode="Markdown")
        return ING_CUMPLE

    user_id = update.effective_user.id
    nombre = context.user_data.get('ing_nombre')
    edad = context.user_data.get('ing_edad')
    sexo = context.user_data.get('ing_sexo')
    altura = context.user_data.get('ing_altura')
    peso = context.user_data.get('ing_peso')
    muneca = context.user_data.get('ing_muneca')
    ocupacion = context.user_data.get('ing_ocupacion')
    
    contextura = calcular_contextura(sexo, altura, muneca)
    peso_ideal = round(calcular_peso_ideal(sexo, altura), 1)
    
    msg_espera = await update.message.reply_text("⏳ **Creando tu ficha e inicializando tus planillas...**", parse_mode="Markdown")

    datos_usuario = {
        "user_id": user_id,
        "nombre": nombre,
        "edad": edad,
        "sexo": sexo,
        "altura": altura,
        "peso": peso,
        "muneca": muneca,
        "contextura": contextura,
        "ocupacion": ocupacion,
        "peso_ideal": peso_ideal,
        "cumple": cumple_str
    }

    try:
        # Ejecución asíncrona segura sin bloquear el hilo principal de Telegram
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, crear_nueva_cuenta_usuario_db, datos_usuario)

        resumen = (
            "✅ **¡Ficha y planillas creadas exitosamente!**\n\n"
            f"👤 **Nombre:** {nombre} | **ID:** `{user_id}`\n"
            f"🎂 **Edad:** `{edad} años` | 🚻 **Sexo:** `{sexo}`\n"
            f"📏 **Altura:** `{altura} cm` | ⚖️ **Peso:** `{peso} kg`\n"
            f"📐 **Muñeca:** `{muneca} cm` → **Contextura:** `{contextura}`\n"
            f"🎯 **Peso Ideal Calculado:** `{peso_ideal} kg`\n\n"
            "🎉 Ya podés usar todos los comandos del bot (`/diario`, `/comidas`, `/presi`, etc.)."
        )
        await msg_espera.edit_text(resumen, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error al crear cuenta para {user_id}: {e}")
        await msg_espera.edit_text(f"❌ Ocurrió un error al inicializar las planillas: {e}")

    context.user_data.clear()
    return ConversationHandler.END

async def ing_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Registro cancelado. Podés volver a iniciar con `/ingreso` o `/nuevo` cuando quieras.")
    context.user_data.clear()
    return ConversationHandler.END

# Objeto Handler exportable para registrar en main.py
conv_handler_ingreso = ConversationHandler(
    entry_points=[CommandHandler(['ingreso', 'nuevo', 'alta', 'registrar', 'nuevo_usuario'], cmd_ingreso_start)],
    states={
        ING_NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ing_recibir_nombre)],
        ING_EDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, ing_recibir_edad)],
        ING_SEXO: [CallbackQueryHandler(ing_recibir_sexo, pattern="^sexo_")],
        ING_ALTURA: [MessageHandler(filters.TEXT & ~filters.COMMAND, ing_recibir_altura)],
        ING_PESO: [MessageHandler(filters.TEXT & ~filters.COMMAND, ing_recibir_peso)],
        ING_MUNECA: [MessageHandler(filters.TEXT & ~filters.COMMAND, ing_recibir_muneca)],
        ING_OCUPACION: [CallbackQueryHandler(ing_recibir_ocupacion, pattern="^ocup_")],
        ING_CUMPLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ing_recibir_cumple)],
    },
    fallbacks=[CommandHandler('cancelar', ing_cancelar)]
)

# =====================================================================================================================================
#                FINAL                                  COMANDO INGRESO (ALTA DE USUARIO)               FINAL
# ======================================================================================================================================
# ========================================================================================================================================
#                     INICIO                         COMANDO START 2026 08 27                 INICIO  DB OK
# =========================================================================================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 **¡Bienvenido a tu Bot Nutricional Personalizado!**\n\n"
        "Guía rápida de comandos e ingestas disponibles:\n\n"
        "📌 **Comandos Principales:**\n"
        "• `/start`: Inicia el bot, apertura/reinicio de cuenta y reenvío de este manual.\n"
        "• `/comidas`: Visualiza listado de comidas predeterminadas y descarga su plantilla PDF.\n"
        "• `/presi`: Registro y consulta de presión arterial.\n"
        "  `  /presi 120,80,70,nota` (Completo) | `/presi 120,80,70` (Sin nota) | `1/presi 20,80` (Solo presión)\n"
        "  `  /presi AAAA-MM` Consulta promedio mensual y descarga reporte PDF.\n"
        "• `/diario`: Ingestas del día con desglose nutricional por comida y PDF.\n"
        "• `/semanal`: Estadística de la semana pasada (calorías, proteínas, actividad física y consejo IA).\n"
        "• `/mensual`: Reporte mensual con estimación de peso, macronutrientes, IA y PDF.\n"
        "• `/perfil`: Consulta de datos biométricos | `/perfil 90` Actualiza el peso del mes.\n"
        "• `/receta`: Acceso a la Calculadora Web para registrar platos y recetas complejas.\n\n"
        "📌 **Métodos de Registro:**\n"
        "• **Con IA:** Texto libre, Notas de voz 🎤 o Fotos de platos 📸.\n"
        "• **Modificación parcial:** Editar por item manteniendo peso (`DESCRIPCION`) o recalculando (`DESCRIPCION,PESO`).\n"
        "• **Sin IA (Plantillas):** `*DESAYUNO,1`, `*PIZZA (porcion),4` o `*TORTA (fraccion x 100g),1.5` (multiplicadores por porción/unidad).\n"
        "• **Actividad Física:** `# MINUTOS DESCRIPCION, CALORIAS` (Ej: `# 45 minutos caminata, 250`).\n\n"
        "📄 *Te adjuntamos el Manual de Usuario completo en formato PDF.*"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
    
    # Generación y envío del documento PDF mejorado
    pdf_buf = generar_pdf_instrucciones_bytes()
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=pdf_buf,
        filename="Manual_Bot_Nutricional.pdf"
    )

def generar_pdf_instrucciones_bytes() -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        rightMargin=36, 
        leftMargin=36, 
        topMargin=36, 
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    # Paleta de colores ejecutiva y refinada
    PRIMARY = colors.HexColor('#1E293B')      # Slate 800 - Encabezados principales
    SECONDARY = colors.HexColor('#2563EB')    # Blue 600 - Destacados y acentos
    TEXT_MAIN = colors.HexColor('#334155')    # Slate 700 - Texto de lectura
    TEXT_MUTED = colors.HexColor('#64748B')   # Slate 500 - Subtítulos
    BG_LIGHT = colors.HexColor('#F8FAFC')     # Slate 50 - Fondo alternado
    BG_CARD = colors.HexColor('#F1F5F9')      # Slate 100 - Cajas de código / ejemplos
    BORDER_COLOR = colors.HexColor('#E2E8F0') # Slate 200 - Líneas de tabla

    # Estilos tipográficos
    title_style = ParagraphStyle(
        'DocTitle', parent=styles['Heading1'], 
        fontSize=18, leading=22, textColor=PRIMARY, fontName='Helvetica-Bold', spaceAfter=2
    )
    subtitle_style = ParagraphStyle(
        'DocSubTitle', parent=styles['Normal'], 
        fontSize=9.5, leading=12, textColor=SECONDARY, fontName='Helvetica-Bold', spaceAfter=8
    )
    section_style = ParagraphStyle(
        'DocSection', parent=styles['Heading2'], 
        fontSize=12, leading=15, textColor=PRIMARY, fontName='Helvetica-Bold', spaceBefore=10, spaceAfter=5
    )
    subsection_style = ParagraphStyle(
        'DocSubSection', parent=styles['Heading3'], 
        fontSize=10, leading=13, textColor=SECONDARY, fontName='Helvetica-Bold', spaceBefore=5, spaceAfter=3
    )
    body_style = ParagraphStyle(
        'DocBody', parent=styles['Normal'], 
        fontSize=8.5, leading=11.5, textColor=TEXT_MAIN, fontName='Helvetica'
    )
    body_bold = ParagraphStyle(
        'DocBodyBold', parent=body_style, fontName='Helvetica-Bold'
    )
    code_style = ParagraphStyle(
        'DocCode', parent=styles['Normal'], 
        fontSize=8, leading=11, textColor=PRIMARY, fontName='Courier-Bold'
    )

    story = []

    # --- ENCABEZADO PRINCIPAL ---
    header_content = [
        [Paragraph("🤖 GUÍA INTERACTIVA DEL BOT NUTRICIONAL", title_style)],
        [Paragraph("MANUAL INTEGRAL DE USUARIO • ASISTENTE PERSONAL INTELIGENTE", subtitle_style)]
    ]
    t_header = Table(header_content, colWidths=[540])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LINEBELOW', (0,1), (-1,1), 2, SECONDARY),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 6))

    # --- SECCIÓN 1: COMANDOS PRINCIPALES ---
    story.append(Paragraph("1. Comandos Principales del Sistema", section_style))
    
    cmds_data = [
        [Paragraph("Comando", body_bold), Paragraph("Descripción Detallada y Formato de Uso", body_bold)],
        [
            Paragraph("<b>/inicio</b>", code_style), 
            Paragraph("Primer ingreso. Solicita datos personales para la apertura de cuenta. Ya con la cuenta abierta presenta la guía rápida con opción de descargar este manual PDF.", body_style)
        ],
        [
            Paragraph("<b>/comidas</b>", code_style), 
            Paragraph("Visualiza el listado de comidas predeterminadas guardadas en tu planilla personal y descarga la plantilla en PDF.", body_style)
        ],
        [
            Paragraph("<b>/presi</b>", code_style), 
            Paragraph("<b>• Carga:</b> <code>/presi ALTA,BAJA,PULSO,NOTA</code> (Registra presión, pulso y nota en planilla).<br/>"
                      "<b>• Opciones cortas:</b> <code>/presi ALTA,BAJA,PULSO</code> o <code>/presi ALTA,BAJA</code> (omite nota y pulso).<br/>"
                      "<b>• Consulta:</b> <code>/presi AAAA-MM</code> Promedio del mes e informe PDF detallado.", body_style)
        ],
        [
            Paragraph("<b>/diario</b>", code_style), 
            Paragraph("Permite seleccionar el día de consulta. Muestra por pantalla los consumos del día y descarga el PDF detallado con todas las ingestas.", body_style)
        ],
        [
            Paragraph("<b>/semanal</b>", code_style), 
            Paragraph("Estadística de la semana pasada (resumen de calorías, proteínas, actividad física y consejo IA). "
                      "El corte se realiza de lunes a domingo. Los lunes muestra la semana cerrada; de martes a domingo muestra la semana en curso.", body_style)
        ],
        [
            Paragraph("<b>/mensual</b>", code_style), 
            Paragraph("Selección del mes de consulta. Presenta reporte mensual, resumen calórico, estimación de cambio de peso, tabla de macronutrientes y descarga de informe diario completo con recomendaciones de IA.", body_style)
        ],
        [
            Paragraph("<b>/perfil</b>", code_style), 
            Paragraph("<b>• Consulta:</b> <code>/perfil</code> Muestra los datos biométricos corporales cargados en el sistema.<br/>"
                      "<b>• Actualización:</b> <code>/perfil 90</code> Actualiza el peso registrado para el mes en curso.", body_style)
        ],
        [
            Paragraph("<b>/receta</b>", code_style), 
            Paragraph("Acceso directo a la <i>Calculadora Nutricional Web</i> para cargar recetas complejas o combinaciones de alimentos en la planilla personal.", body_style)
        ],
        [
            Paragraph("<b>atajos</b>", code_style), 
            Paragraph("<b>•/diario</b> <code>//d</code>.<br/>"
                      "<b>•/semanal</b> <code>//s</code>.<br/>"
                      "<b>•/mensual</b> <code>//m</code>.<br/>", body_style)
        ],
    ]

    t_cmds = Table(cmds_data, colWidths=[90, 450])
    t_cmds.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), SECONDARY),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT])
    ]))
    
    # Textos de cabecera en blanco
    cmds_data[0][0].style.textColor = colors.white
    cmds_data[0][1].style.textColor = colors.white

    story.append(t_cmds)
    story.append(Spacer(1, 8))

    # --- SECCIÓN 2: MÉTODOS DE REGISTRO ---
    story.append(Paragraph("2. Métodos de Registro de Ingestas y Actividades", section_style))

    story.append(Paragraph("A. Con Intervención de IA (Texto, Voz e Imagen)", subsection_style))
    
    registro_ia_data = [
        [
            Paragraph("<b>💬 Texto Libre:</b> Escribí tus alimentos de forma natural detallando porciones (Ej: <i>'2 huevos revueltos con 1 tostada integral y café'</i>).", body_style)
        ],
        [
            Paragraph("<b>🎤 Notas de Voz:</b> Dictá tu ingesta en una nota de voz; la IA convertirá el audio a texto y procesará los datos nutricionales.", body_style)
        ],
        [
            Paragraph("<b>📸 Fotografías de Galería / Cámara:</b> Envía una foto del plato con o sin descripción aclaratoria (Ej: <i>'Milanesa casera de pollo al horno'</i>).", body_style)
        ],
        [
            Paragraph("<b>⚙️ Proceso de Edición y Confirmación:</b><br/>"
                      "• <b>Momento:</b> Desayuno, Almuerzo, Merienda o Cena.<br/>"
                      "• <b>Edición parcial:</b> Seleccioná ítem por ítem enviando una <i>nueva descripción</i> (mantiene peso) o <i>descripción y peso</i> (recalcula completo).<br/>"
                      "• <b>Fecha y Guardado:</b> Confirmá la fecha del consumo para asentar en tu planilla.", body_style)
        ]
    ]

    t_reg_ia = Table(registro_ia_data, colWidths=[540])
    t_reg_ia.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_reg_ia)
    story.append(Spacer(1, 6))

    story.append(Paragraph("B. Sin Intervención de IA (Comidas Precargadas y Actividades)", subsection_style))

    direct_data = [
        [Paragraph("Tipo de Registro", body_bold), Paragraph("Sintaxis", body_bold), Paragraph("Ejemplos y Funcionamiento", body_bold)],
        [
            Paragraph("<b>Plantilla de Comidas</b>", body_style),
            Paragraph("<code>*CODIGO, CANTI</code>", code_style),
            Paragraph("• <code>*DESAYUNO,1</code> Ingresa 1 unidad de la comida seleccionada.<br/>"
                      "• <code>*PIZZA,4</code> Registra 4 porciones de la plantilla.<br/>"
                      "• <code>*TORTA,3</code> Ingresa 3 porciones (si la receta base fue cargada en fracciones de 100g, equivale a 300g).", body_style)
        ],
        [
            Paragraph("<b>Actividad Física</b>", body_style),
            Paragraph("<code># MINUTOS DESCRIPCION, CALORIAS</code>", code_style),
            Paragraph("• <code># 45 minutos caminata al aire libre, 250 calorias</code><br/>"
                      "• <code># 60 minutos aquagym, 450 calorias</code><br/>"
                      "Graba directamente el tiempo y el gasto calórico en la planilla.", body_style)
        ]
    ]

    t_direct = Table(direct_data, colWidths=[110, 160, 270])
    t_direct.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT]) # Corregido: se eliminó colors.black
    ]))
    
    direct_data[0][0].style.textColor = colors.white
    direct_data[0][1].style.textColor = colors.white
    direct_data[0][2].style.textColor = colors.white

    story.append(t_direct)
    story.append(Spacer(1, 8))

# --- SECCIÓN 3: CALCULADORA WEB DE RECETAS ---
    story.append(KeepTogether([
        Paragraph("3. Calculadora Nutricional Web (/receta)", section_style),
        Paragraph("Permite cargar recetas elaboradas o combinaciones de alimentos habituales directamente en tu planilla personal.", body_style),
        Paragraph("• <code>*Código/Nombre:</code> Código identificatorio para buscar la receta cargada en la planilla utilizando * .<br/>"
                  "• <code>*Descripción:</code> Descripcion de la receta o detalle de los componentes de una ingesta guardada.<br/>"
                  "• <code>*Criterio:</code> Criterio a utilizar si la receta fue cargada en fracciones de 100g o porciones.<br/><br/>", body_style),
        Spacer(1, 4)
    ]))

    # Definimos estilos con texto blanco para el encabezado oscuro
    header_example_style = ParagraphStyle(
        'HeaderExampleStyle', parent=body_bold, textColor=colors.white
    )

    receta_data = [
        [
            Paragraph("Ejemplo 1: Combinación de ingestas (DESAYUNO)", header_example_style),
            Paragraph("Ejemplo 2: Receta Elaborada (TORTA)", header_example_style)
        ],
        [
            Paragraph("• <b>Código/Nombre:</b> <code>DESAYUNO</code><br/>"
                      "• <b>Descripción:</b> Desayuno tradicional completo con tostadas, queso y mermelada.<br/>"
                      "• <b>Ingredientes:</b> 1 taza café con leche, 2 tostadas finas pan integral, 20g mermelada bajas calorías, 20g queso crema light.<br/>"
                      "• <b>Criterio:</b> Por porciones = 1.", body_style),
            Paragraph("• <b>Código/Nombre:</b> <code>TORTA</code><br/>"
                      "• <b>Descripción:</b> Torta matera fácil.<br/>"
                      "• <b>Ingredientes:</b> 1/2 taza aceite girasol, 1 taza leche, 2 tazas harina leudante, 1 pizca sal, 2 huevos, 1 taza azúcar.<br/>"
                      "• <b>Criterio:</b> Fracción de 100 g.", body_style)
        ]
    ]

    t_receta = Table(receta_data, colWidths=[270, 270])
    t_receta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),  # Fondo oscuro (igual al de la Sección 2)
        ('BACKGROUND', (0,1), (-1,1), BG_CARD),  # Fondo claro para el contenido
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR)
    ]))
    
    story.append(t_receta)

    doc.build(story)
    buffer.seek(0)
    return buffer

# ==============================================================================================================================================
#                 FINAL                            COMANDO START                               FINAL
# ==============================================================================================================================================

# ==============================================================================================================================================
#               INICIO                      COMANDO RESUMEN     2026 08 27                        INICIO  DB OK
# ==============================================================================================================================================

@requiere_registro
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
# =============================================================================================================================================

def generar_recomendacion_ia(promedios: dict, metas: dict, biometria: dict = None) -> str:
    """
    Envía los datos biométricos y promedios mensuales a Groq para que redacte
    un informe nutricional completo de 500-600 palabras con estructura HTML para PDF.
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

    prompt_pdf = f"""
    Actúa como un nutricionista clínico experto. Analiza el siguiente resumen mensual de un paciente y redacta un informe extenso y profesional de entre 500 y 600 palabras.

    DATOS DEL PACIENTE:
    - Peso actual: {peso_act} kg | Peso objetivo: {peso_id} kg

    PROMEDIOS DIARIOS CONSUMIDOS VS METAS OBJETIVO:
    - Calorías: {cal_r} kcal (Meta: {cal_m} kcal)
    - Proteínas: {prot_r} g (Meta: {prot_m} g)
    - Grasas: {gras_r} g (Meta: {gras_m} g)
    - Carbohidratos: {carb_r} g (Meta: {carb_m} g)
    - Fibra: {fibr_r} g (Meta: {fibr_m} g)

    ESTRUCTURA Y FORMATO DE LA RESPUESTA:
    Usa etiquetas HTML básicas (<b>, <br/>) para dar formato. El informe DEBE dividirse en exactamente estas 5 secciones encabezadas en negrita:

    <b>1. DIAGNÓSTICO NUTRICIONAL INTEGRAL DEL MES</b>
    (Análisis profundo del balance energético global y el cumplimiento del perfil).

    <b>2. ANÁLISIS DE BRECHAS Y DESVÍOS ESPECÍFICOS</b>
    (Puntos bala con • evaluando déficit o exceso de cada macronutriente y fibra con respecto a las metas).

    <b>3. ALIMENTOS Y COMIDAS QUE DEBERÍAS INGERIR (PARA SUPLIR DÉFICITS)</b>
    (Recomendaciones concretas de alimentos para los nutrientes faltantes).

    <b>4. ALIMENTOS Y COMIDAS QUE DEBERÍAS REDUCIR O EVITAR (PARA CORREGIR EXCESOS)</b>
    (Lista de alimentos a moderar o eliminar según las grasas/carbohidratos consumidos).

    <b>5. RECOMENDACIÓN GENERAL Y ESTRATEGIA DE HÁBITOS</b>
    (Estrategias sobre consumo de agua, distribución de platos y hábitos sostenibles).

    REGLA STRICTA: Devuelve ÚNICAMENTE el texto del informe formateado en HTML sin incluir mensajes adicionales, saludos ni introducciones fuera del informe.
    """

    # Hacemos la llamada a Groq pasando max_tokens=1200 para dar espacio a las 600 palabras
    
    respuesta = ejecutar_consulta_ia(prompt=prompt_pdf, max_tokens=1200, temperature=0.5)
    
    if respuesta:
        return respuesta

    return "<b>⚠️ No se pudo generar la recomendación mediante IA en este momento.</b>"    

#                                                       MOSTRAR EL RESUMEN DEL MES POR PANTALLA
# =============================================================================================================================================


async def mostrar_resumen_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Muestra el reporte del mes ignorando el día en curso (hasta ayer 23:59:59)
    y previene cortes por el límite de caracteres de Telegram.
    """
    try:
        query = update.callback_query
        user_id = update.effective_user.id

        mes_str = None
        if query and query.data:
            await query.answer()
            if query.data.startswith("resumen_mes_"):
                mes_str = query.data.replace("resumen_mes_", "")
        elif context.args:
            mes_str = context.args[0]

        if not mes_str or mes_str == "otro":
            ahora = obtener_ahora_arg()
            mes_str = ahora.strftime("%Y-%m")

        df_datos = obtener_datos_usuario(user_id)
        
        if not df_datos.empty and 'Fecha' in df_datos.columns:
            df_datos['Fecha_dt'] = pd.to_datetime(df_datos['Fecha'])
            
            # FILTRO CRÍTICO: Registros del mes seleccionado hasta AYER a las 23:59:59
            hoy_comienzo = pd.Timestamp.now().floor('D')
            df_mes = df_datos[
                (df_datos['Fecha'].astype(str).str.startswith(mes_str)) & 
                (df_datos['Fecha_dt'] < hoy_comienzo)
            ].copy()
        else:
            df_mes = pd.DataFrame()

        if df_mes.empty:
            msg = f"⚠️ No hay registros cerrados de días anteriores para el mes `{mes_str}`."
            if query:
                await query.edit_message_text(msg, parse_mode="Markdown")
            else:
                await update.message.reply_text(msg, parse_mode="Markdown")
            return

        perfil = obtener_perfil_usuario(user_id, mes_target=mes_str) if 'obtener_perfil_usuario' in globals() else {}
        m = calcular_metricas_mensuales(df_mes, perfil)

        prompt_para_ia_pantalla = (
            f"REPORTE NUTRICIONAL DEL MES ({mes_str}):\n"
            f"- Días cerrados evaluados: {m['dias_registrados']}\n"
            f"- Consumo promedio: {m['prom_cal']} kcal/día (Meta: {m['ideal_cal']} kcal)\n"
            f"- Proteínas: {m['prom_prot']} g (Meta: {m['ideal_prot']} g)\n"
            f"- Grasas: {m['prom_gras']} g (Meta: {m['ideal_gras']} g)\n"
            f"- Carb: {m['prom_carb']} g (Meta: {m['ideal_carb']} g)\n"
            f"- Fibra: {m['prom_fibr']} g (Meta: {m['ideal_fibr']} g)\n"
        )
        
        recomendacion_pantalla = await asyncio.to_thread(obtener_recomendacion_ia, prompt_para_ia_pantalla)

        encabezado_txt = (
            f"📊 **Reporte Nutricional Mensual ({mes_str}):**\n"
            f"ℹ️ *Calculado sobre días cerrados (excluye hoy)*\n\n"
            f"• **Promedio Consumidas:** `{m['prom_cal']} kcal` / día\n"
            f"• **Promedio Quemadas:** `{m['prom_quem']} kcal` / día\n"
            f"• **Balance Neto Diario:** `{m['prom_bal_neto']} kcal` / día\n"
            f"• **Cambio Estimado de Peso:** `{m['cambio_peso_kg']:+.1f} kg` en el mes\n\n"
            f"• Días evaluados: `{m['dias_registrados']}`\n"
            f"📈 **Promedio Diario vs. Objetivos:**\n"
            f"• **Calorías:** `{m['prom_cal']} kcal` / Meta: `{m['ideal_cal']} kcal`\n"
            f"• **Proteínas:** `{m['prom_prot']} g` / Meta: `{m['ideal_prot']} g`\n"
            f"• **Grasas:** `{m['prom_gras']} g` / Meta: `{m['ideal_gras']} g`\n"
            f"• **Carbohidratos:** `{m['prom_carb']} g` / Meta: `{m['ideal_carb']} g`\n"
            f"• **Fibras:** `{m['prom_fibr']} g` / Meta: `{m['ideal_fibr']} g`\n\n"
            f"🤖 **Análisis Nutricional:**\n"
        )
        
        pie_txt = f"\n\n📄 Podés descargar el reporte completo en PDF a continuación:"

        # LÍMITE DE TELEGRAM: Cortar recomendación si supera los 4000 caracteres totales
        espacio_disponible = 3900 - len(encabezado_txt) - len(pie_txt)
        if len(recomendacion_pantalla) > espacio_disponible:
            recomendacion_pantalla = recomendacion_pantalla[:espacio_disponible - 3] + "..."

        txt_final = f"{encabezado_txt}{recomendacion_pantalla}{pie_txt}"

        keyboard = [[InlineKeyboardButton("📄 Descargar PDF Resumen Mensual", callback_data=f"pdf_mes_{mes_str}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if query:
            await query.edit_message_text(txt_final, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(txt_final, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en mostrar_resumen_mes: {e}")
        msg_err = f"⚠️ Ocurrió un error al generar el resumen mensual: {e}"
        if update.callback_query:
            await update.callback_query.edit_message_text(msg_err)
        else:
            await update.message.reply_text(msg_err)


#                                                    GENERAR PDF RESUMEN BYTES (FORZADO DE REPORTE COMPLETO)
# ======================================================================================================================================

def generar_pdf_resumen_bytes(mes_str, df_mes, df_presion, perfil, tmb_val, recomendacion, user_id):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=14, textColor=colors.HexColor('#1E3A8A'), spaceAfter=4)
    sub_style = ParagraphStyle('SubTitle', parent=styles['Heading2'], fontSize=10, textColor=colors.HexColor('#2563EB'), spaceBefore=6, spaceAfter=2)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#1E293B'))
    rec_style = ParagraphStyle('RecBody', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#0F172A'), spaceAfter=1)
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)

    story = [
        Paragraph(f"<b>Reporte Nutricional Mensual - {mes_str}</b>", title_style),
        Paragraph(f"<b>Usuario Telegram ID:</b> {user_id}", body_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=6)
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
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=6))

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
    story.append(Spacer(1, 4))

    story.append(Paragraph(f"• <b>PERFIL BASE ({mes_str}):</b> Peso Actual: {m['peso_actual']} kg | Peso Objetivo (75/25): {m['peso_referencia']} kg | Altura: {m['altura']} cm", body_style))
    story.append(Paragraph(f"• <b>DÉFICIT CALÓRICO DIARIO PROMEDIO:</b> {m['deficit_diario_real']} kcal / día", body_style))
    story.append(Paragraph(f"• <b>CAMBIO ESTIMADO DE PESO EN EL MES:</b> {m['cambio_peso_kg']:+.1f} kg", body_style))

    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>Recomendación Nutricional Personalizada y Plan de Acción (IA):</b>", sub_style))

    # --- LISTA AMPLIADA DE ALIMENTOS (10 REGLONES CADA UNA - SIN ESPACIOS EXCESIVOS) ---
    alimentos_ingerir = [
        "<b>1. ALIMENTOS Y COMIDAS QUE DEBERÍAS INGERIR (10 OPCIONES SUGERIDAS)</b>",
        "- Pechuga de pollo, pavo o pescados blancos (merluza, merluza negra, pollo sin piel).",
        "- Pescados grasos saludables (salmón, atún, sardinas) por su aporte de omega 3.",
        "- Huevos enteros o claras de huevo (alto valor biológico y saciedad).",
        "- Legumbres variadas (lentejas, garbanzos, porotos negros, arvejas).",
        "- Avena integral, quinoa, arroz integral y cebada perlada.",
        "- Batata, papa hervida/al horno o choclo como fuente de energía limpia.",
        "- Verduras de hoja verde (espinaca, acelga, rúcula, lechuga).",
        "- Vegetales crucíferos (brócoli, coliflor, repollo de Bruselas).",
        "- Frutas frescas bajas en azúcar (manzana verde, pera, frutos rojos, frutillas).",
        "- Frutos secos y semillas (almendras, nueces, chía, lino) en porciones controladas."
    ]

    alimentos_reducir = [
        "<b>2. ALIMENTOS Y COMIDAS QUE DEBERÍAS REDUCIR O EVITAR (10 OPCIONES A CONTROLAR)</b>",
        "- Ultraprocesados, snacks industriales y papas fritas de paquete.",
        "- Fiambres, embutidos y carnes procesadas altas en sodio y grasas saturadas.",
        "- Cortes de carne vacina o de cerdo con alto contenido graso visibile.",
        "- Bebidas azucaradas, gaseosas comunes y jugos industriales.",
        "- Aderezos comerciales hipercalóricos (mayonesa común, salsas compradas).",
        "- Harinas refinadas, pan blanco, galletitas dulces y bizcochitos.",
        "- Productos de pastelería, facturas, tartas comerciales y empanadas fritas.",
        "- Lácteos enteros con alto porcentaje graso (quesos duros estacionados, crema).",
        "- Comidas rápidas (hamburguesas comerciales, frituras en abundante aceite).",
        "- Bebidas alcohólicas por su aporte de calorías vacías."
    ]

    # Incorporar recomendación general
    if isinstance(recomendacion, str) and recomendacion.strip():
        for bloque in recomendacion.strip().split('\n\n'):
            if bloque.strip():
                story.append(Paragraph(bloque.strip().replace('\n', '<br/>'), rec_style))
                story.append(Spacer(1, 2))

    story.append(Spacer(1, 4))

    # Renderizar listas de 10 alimentos compactas sin saltos de línea innecesarios
    for item in alimentos_ingerir:
        story.append(Paragraph(item, rec_style))
    
    story.append(Spacer(1, 4))
    
    for item in alimentos_reducir:
        story.append(Paragraph(item, rec_style))

    doc.build(story)
    buffer.seek(0)
    return buffer
    
    
async def generar_y_enviar_pdf_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Generando PDF... ⏳")

    try:
        user_id = query.from_user.id
        mes_str = query.data.replace("pdf_mes_", "")

        # 1. Obtener datos y filtrar el día actual (solo días cerrados hasta ayer a las 23:59:59)
        df_datos = obtener_datos_usuario(user_id) if 'obtener_datos_usuario' in globals() else pd.DataFrame()
        
        if not df_datos.empty and 'Fecha' in df_datos.columns:
            df_datos['Fecha_dt'] = pd.to_datetime(df_datos['Fecha'])
            hoy_comienzo = pd.Timestamp.now().floor('D')
            df_mes = df_datos[
                (df_datos['Fecha'].astype(str).str.startswith(mes_str)) & 
                (df_datos['Fecha_dt'] < hoy_comienzo)
            ].copy()
        else:
            df_mes = pd.DataFrame()

        if df_mes.empty:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"⚠️ No hay registros de días cerrados en el mes `{mes_str}` para generar el PDF.",
                parse_mode="Markdown"
            )
            return

        # 2. Cargar dependencias adicionales del reporte
        perfil = obtener_perfil_usuario(user_id, mes_target=mes_str) if 'obtener_perfil_usuario' in globals() else {}
        df_presion = pd.DataFrame()  # O la llamada correspondiente a la presión del usuario
        tmb_val = perfil.get('tmb', 0) if isinstance(perfil, dict) else 0

        # 3. Generar la recomendación extensa de IA para el PDF
        prompt_para_pdf = f"Genera un análisis nutricional clínico extenso para el reporte PDF del mes {mes_str}."
        recomendacion_pdf = await asyncio.to_thread(obtener_recomendacion_ia, prompt_para_pdf) if 'obtener_recomendacion_ia' in globals() else ""

        # 4. Generar el PDF directamente en buffer de memoria mediante la función indicada
        pdf_buffer = await asyncio.to_thread(
            generar_pdf_resumen_bytes,
            mes_str,
            df_mes,
            df_presion,
            perfil,
            tmb_val,
            recomendacion_pdf,
            user_id
        )

        # 5. Enviar el documento directamente desde el buffer de memoria a Telegram
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=pdf_buffer,
            filename=f"Reporte_Nutricional_{mes_str}.pdf",
            caption=f"📄 Reporte mensual completo correspondiente a **{mes_str}** (días cerrados).",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error al enviar PDF: {e}")
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"⚠️ Error al procesar la descarga del PDF: {e}"
        )
                
# ======================================================================================================================================
#                   FINAL                                COMANDO RESUMEN                                           FINAL
# ======================================================================================================================================

# ======================================================================================================================================
#                   INICIO                               COMANDO PRESION                                          INICIO  DB OK
# ======================================================================================================================================

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

@requiere_registro
async def cmd_presion_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Limpia tanto /presi como /presion (con o sin acento)
    raw_text = re.sub(r'^/(presio|presi|presion)\w*(@\w+)?', '', update.message.text, flags=re.IGNORECASE).strip()

    if not raw_text:
        await update.message.reply_text(
            "Ingresa o consulta un mes usando /presi. Ejemplos:\n\n"
            "• /presi 120,80,70, después de caminar\n"
            "• /presi 120,80,70\n"
            "• /presi 120,80\n"
            "• /presi 2026-08", 
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

        # Guarda consumiendo la capa de datos externa
        guardar_presion_db(user_id, alta, baja, pulsaciones, nota)

        pul_str = f" | Pulsaciones: `{pulsaciones:.0f}`" if pulsaciones is not None else ""
        nota_str = f"\nNota: `{nota}`" if nota else ""
        
        await update.message.reply_text(
            f"Presión registrada:\nAlta: `{alta:.0f}` | Baja: `{baja:.0f}`{pul_str}{nota_str}", 
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text(
        "Formato incorrecto. Uso: /presi 120,80,70, al despertar o /presi 120,80 o /presi 2026-08", 
        parse_mode="Markdown"
    )


async def mostrar_resumen_presion_mes(query_or_update, user_id, mes_str):
    # Consulta la capa de datos externa
    df_presion = obtener_datos_presion_db(user_id)
    if df_presion.empty:
        txt = f"🩺 No hay registros de presión arterial para el usuario `{user_id}`."
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(txt, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(txt, parse_mode="Markdown")
        return

    df_p_mes = df_presion[df_presion['Fecha_Dia'].str.startswith(mes_str)] if 'Fecha_Dia' in df_presion.columns else pd.DataFrame()
    if df_p_mes.empty:
        txt = f"🩺 No hay registros de presión para el mes `{mes_str}`."
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(txt, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(txt, parse_mode="Markdown")
        return

    alta_prom = df_p_mes['Alta'].mean()
    baja_prom = df_p_mes['Baja'].mean()
    pul_prom = df_p_mes[df_p_mes['Pulsaciones'] > 0]['Pulsaciones'].mean() if 'Pulsaciones' in df_p_mes.columns else 0

    txt = (
        f"🩺 **Resumen de Presión Arterial ({mes_str}):**\n\n"
        f"• Mediciones registradas: `{len(df_p_mes)}`\n"
        f"• **Promedio Alta (Sistólica):** `{alta_prom:.1f} mmHg`\n"
        f"• **Promedio Baja (Diastólica):** `{baja_prom:.1f} mmHg`\n"
    )
    if pul_prom > 0:
        txt += f"• **Promedio Pulsaciones:** `{pul_prom:.1f} lpm`\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Descargar PDF Presión Diaria", callback_data=f"descargar_pdf_presion_{mes_str}")]
    ])

    if hasattr(query_or_update, 'edit_message_text'):
        await query_or_update.edit_message_text(txt, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await query_or_update.message.reply_text(txt, reply_markup=keyboard, parse_mode="Markdown")


async def generar_y_enviar_pdf_presion(query, user_id, mes_str, context):
    # Consulta la capa de datos externa
    df_presion = obtener_datos_presion_db(user_id)
    df_p_mes = df_presion[df_presion['Fecha_Dia'].str.startswith(mes_str)] if not df_presion.empty and 'Fecha_Dia' in df_presion.columns else pd.DataFrame()
    
    pdf_bytes = generar_pdf_presion_bytes(mes_str, df_p_mes, user_id)
    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=pdf_bytes,
        filename=f"Presion_Arterial_{mes_str}.pdf"
    )        
        
# =========================================================================================================================================
#                  FINAL                                MODULO DE PRESION ARTERIAL                            FINAL
# =========================================================================================================================================

# ==================================================================================================================================
#                    INICIO                                    COMANDO RECETAS                                   INCIO  DB OK
# ==================================================================================================================================

@requiere_registro
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

# ======================================================================================================================================
#                  FINAL                                       COMANDO RECETA                                        FINAL
# =========================================================================================================================================

# ======================================================================================================================================
#                   INICIO                                    COMANDO DIARIO   2026 08 22                         INICIO  DB OK
# =====================================================================================================================================

@requiere_registro
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

# =======================================================================================================================================
#                   FINAL                                COMANDOS DIARIO                                     FINAL
# =====================================================================================================================================

# =====================================================================================================================================
#                   INICIO                               COMANDO PERFIL   2026 08 20                          INICIO  DB OK
# ======================================================================================================================================

@requiere_registro
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
            
            # Se guardan el peso y el mes en la capa de datos
            guardar_perfil_db(user_id, nuevo_peso, mes_actual)
            
            # Recargar el perfil actualizado desde la capa de datos
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

# ======================================================================================================================================
#                       FINAL                                       COMANDOS PERFIL                                      FINAL
# ======================================================================================================================================

# ======================================================================================================================================
#                      INICIO                                   OPERACIONES COMIDAS 2026-08-19                          INICIO  DB OK
# =======================================================================================================================================

@requiere_registro
async def cmd_comidas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    comidas = obtener_comidas_usuario(user_id)
    
    if not comidas:
        await update.message.reply_text(f"📋 No hay comidas predeterminadas registradas en la hoja 'Comidas_{user_id}'.")
        return

    txt = f"📋 <b>Listado de Comidas Predeterminadas (Comidas_{user_id}):</b>\n\n"
    
    for p in comidas:
        nombre_raw = str(p.get('Nombre', ''))
        desc_raw = str(p.get('Descripcion') or p.get('Momento', ''))
        
        nombre = nombre_raw.replace('§', '').replace('<', '').replace('>', '').strip()
        descripcion = desc_raw.replace('§', '').replace('<', '').replace('>', '').strip()
        
        if descripcion and descripcion.lower() != nombre.lower():
            linea = f"• <b>{nombre}</b>: {descripcion}\n"
        else:
            linea = f"• <b>{nombre}</b>\n"
        
        if len(txt) + len(linea) > 4000:
            txt += "• <i>...y más comidas (ver detalle en el PDF adjunto).</i>\n"
            break
            
        txt += linea

    txt += "\n📄 Te adjuntamos el archivo en PDF completo con todos los macronutrientes a continuación."
    
    try:
        await update.message.reply_text(txt, parse_mode="HTML")
    except Exception as e:
        print(f"Error enviando texto de comidas: {e}")
        await update.message.reply_text("📋 Generando tu lista de comidas en PDF directamente...")

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
            peso_raw = item.get('Peso (g x1000)', item.get('Peso', 0))
            cal_raw = item.get('Calorías (x1000)', item.get('Calorias', 0))
            prot_raw = item.get('Proteínas (g x1000)', item.get('Proteinas', 0))
            gras_raw = item.get('Grasas (x1000)', item.get('Grasas', 0))
            carb_raw = item.get('Carbohidratos (x1000)', item.get('Carbohidratos', 0))
            fibr_raw = item.get('Fibras (x1000)', item.get('Fibras', 0))

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

# ======================================================================================================================================
#                   FINAL                                   OPERACION COMIDAS                                      FINAL
# ======================================================================================================================================

#=========================================================================================================================================
#                INICIO                             MANEJADORES HANDLE 2026 08 22                                  INICIO DB OK
#=========================================================================================================================================


#====================================================================================================================================
#                FINAL                                     MANEJADORES HANDLE                                    FINAL
#===================================================================================================================================

@requiere_registro
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

@requiere_registro
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

@requiere_registro
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    raw_text = update.message.text.strip() if update.message and update.message.text else ""

    if not raw_text:
        return

    # A. SI EL USUARIO PRESIONÓ "SELECCIONAR FECHA" EN /diario
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
            await mostrar_diario_fecha(update.message, user_id, fecha_parseada)
            return
        else:
            msg_err = await update.message.reply_text("⚠️ Formato de fecha inválido. Ingrese nuevamente (Ej: `2026-08-15` o `15/08`):", parse_mode="Markdown")
            context.user_data['msg_solicitud_diario_fecha_id'] = msg_err.message_id
            return
            
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
            texto_base = texto_base.replace('§', '').strip()
            
            if texto_base.startswith('(x'):
                if ')' in texto_base:
                    texto_base = texto_base.split(')', 1)[1].strip()

            multiplicador_str = f"{int(multiplicador)}" if multiplicador.is_integer() else f"{multiplicador}"
            
            nombre_pantalla = f"(x{multiplicador_str}) {texto_base}"
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

#==============================================================================================================================

@requiere_registro
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

#====================================================================================================================================
#                FINAL                                     MANEJADORES HANDLE                                    FINAL
#===================================================================================================================================

# =====================================================================================================================================
#                INICIO                               MENSAJES PROGRAMADOS 2026 08 26                         INICIO  DB OK
# ======================================================================================================================================

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
    - momento == 'manana': Revisa anteayer y ayer. Si es MARTES, dispara
      el resumen semanal de la semana anterior mediante la función unificada.
    - momento == 'tarde': Revisa ayer entero y hoy (Desayuno y Almuerzo).
      Incluye aviso automático de peso mensual si se está a partir del día 5 sin actualizar.
    """
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        
        sheet_usuarios = sh.worksheet("Usuarios")
        registros_usuarios = sheet_usuarios.get_all_records()
        
        usuarios_validos = []
        
        for u in registros_usuarios:
            estado = str(u.get("Estado", "")).strip().lower()
            notif = str(u.get("Notificaciones", "")).strip().lower()
            raw_user_id = u.get("User ID")
            
            if estado == "activo" and notif in ["si", "sí"] and raw_user_id:
                try:
                    uid_int = int(raw_user_id)
                    usuarios_validos.append(uid_int)
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

    # Identificar si es MARTES por la mañana (1 = Martes en Python: Lunes=0, Martes=1)
    es_martes_manana = (hoy.weekday() == 1 and momento == 'manana')

    for user_id in usuarios_validos:
        try:
            # -----------------------------------------------------------------
            # 1. ENVÍO AUTOMÁTICO DEL RESUMEN SEMANAL (MARTES A LA MAÑANA)
            # -----------------------------------------------------------------
            if es_martes_manana:
                # Llamamos directamente a la función unificada enviando el reporte completo
                await enviar_resumen_semanal_usuario(context, user_id, semana_actual=False)

            # -----------------------------------------------------------------
            # 2. REVISIÓN HABITUAL DE COMIDAS PENDIENTES
            # -----------------------------------------------------------------
            nombre_hoja_usuario = f"User_{user_id}"
            sheet_usuario = sh.worksheet(nombre_hoja_usuario)
            registros_comidas = sheet_usuario.get_all_records()

            comidas_anteayer = set()
            comidas_ayer = set()
            comidas_hoy = set()

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

            # Generar texto de aviso de peso (si aplica: día >= 5 y sin peso del mes)
            aviso_peso_str = _verificar_aviso_peso(user_id, ahora_dt)

            # Si hay comidas faltantes O si hay un aviso de peso pendiente
            if faltantes or (not es_martes_manana and aviso_peso_str):
                mensaje_recordatorio = ""
                
                if faltantes:
                    lista_formateada = "\n• " + "\n• ".join(faltantes)
                    mensaje_recordatorio = (
                        f"📌 **Recordatorio de comidas pendientes:**\n"
                        f"{lista_formateada}\n\n"
                        f"Si ya las consumiste, podés registrarlas en cualquier momento."
                    )
                
                # Anexar aviso de peso si no es martes por la mañana (ya que el resumen semanal lo incluye)
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

# =============================================================================================================================================
#                    FINAL                                    MENSAJES PROGRAMADOS                                        FINAL
# =============================================================================================================================================

# =============================================================================================================================================
#                    INICIO                                 MAIN EXECUTION 2026 08 27                                 INICIO  DB OK
# =============================================================================================================================================

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
            time=time(hour=9, minute=0, second=0, tzinfo=tz),
            name="recordatorio_comidas_manana"
        )

        job_queue.run_daily(
            job_recordatorio_tarde, 
            time=time(hour=18, minute=0, second=0, tzinfo=tz),
            name="recordatorio_comidas_tarde"
        )
    else:
        print("⚠️ Advertencia: job_queue no está disponible. Verifique que 'python-telegram-bot[job-queue]' esté instalado.")

    # --- HANDLER CONVERSACIONAL (ALTA Y REGISTRO DE NUEVO USUARIO) ---
    app_bot.add_handler(conv_handler_ingreso)

    # --- HANDLERS DE COMANDOS ---
    	
    app_bot.add_handler(CommandHandler(["comidas", "comida"], cmd_comidas))
    app_bot.add_handler(CommandHandler(["perfil", "peso"], cmd_perfil))
    app_bot.add_handler(CommandHandler(["presion", "presi", "presio"], cmd_presion_handler))  
    app_bot.add_handler(CommandHandler(["diario", "dia", "d"], cmd_diario))
    app_bot.add_handler(CommandHandler(["resumen", "mes", "mensual", "m"], cmd_resumen))
    app_bot.add_handler(CommandHandler(["mensaje", "semana", "semanal", "s"], cmd_mensaje))
    app_bot.add_handler(CommandHandler(["receta", "planilla"], cmd_cargar_receta))

    # --- HANDLERS DE BOTONES INTERACTIVOS (CALLBACKS PANTALLA Y PDF) ---
    app_bot.add_handler(CallbackQueryHandler(mostrar_resumen_mes, pattern="^resumen_mes_"))
    app_bot.add_handler(CallbackQueryHandler(generar_y_enviar_pdf_resumen, pattern="^pdf_mes_"))

    # --- HANDLERS DE MENSAJES Y CONSULTAS ---
    app_bot.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app_bot.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Callback genérico (debe ir al final de los CallbackQueryHandler)
    app_bot.add_handler(CallbackQueryHandler(handle_callback_query))

    print("🤖 Bot Nutricional iniciado correctamente en Telegram con tareas programadas...")
    
    # Inicio del bot en loop de eventos asíncrono
    app_bot.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

# =============================================================================================================================================
#                                                   FINAL MAIN EXECUTION                                                    FINAL
# =============================================================================================================================================




