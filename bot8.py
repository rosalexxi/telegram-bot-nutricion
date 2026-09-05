

# =============================================================================================================================================
#                                 INICIO                                   CABECERA 2026 09 05                                    INICIO
#                                  https://github.com/rosalexxi/telegram-bot-nutricion
#                                  https://dashboard.render.com/web/srv-d9lcifijnfac73a8q1eg/events
#                                  https://supabase.com/dashboard/project/xsheilmjewqcvhmyqlnx/editor/17944?schema=public
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
import psycopg2  
import sys
import pytz
import pandas as pd
import gspread


from typing import Dict, Tuple, List, Optional, Any            
from urllib.parse import urlparse 
from datetime import datetime, date, timedelta, time
from google.oauth2.service_account import Credentials
from groq import Groq
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template_string
from functools import wraps
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
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
GROQ_FOTO = "qwen/qwen3.8-27b"
GROQ_AUDIO = "whisper-large-v3"
GROQ_REVISION = "openai/gpt-oss-20b"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_SHEETS_KEY_PATH = os.getenv("GOOGLE_SHEETS_KEY_PATH", "credentials.json")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "Registro_Nutricional_Bot")
ARG_TZ = pytz.timezone('America/Argentina/Buenos_Aires')

# Estados del flujo de conversación
ING_PROFESIONAL, ING_NOMBRE, ING_EDAD, ING_SEXO, ING_ALTURA, ING_PESO, ING_MUNECA, ING_OCUPACION, ING_CUMPLE = range(10, 19)

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
#              INICIO                                  PAGINA WEB (CALCULADORA UNICA)                        INICIO  DB OK
# ======================================================================================================================================

app = Flask(__name__)

HTML_CALCULADORA_RECETAS = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generador de Comidas Precargadas - Bot Nutricional</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 30px; background-color: #f4f6f9; color: #333; }
        .container { max-width: 850px; margin: auto; background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
        h2 { color: #2c3e50; text-align: center; }
        label { font-weight: bold; display: block; margin-top: 15px; margin-bottom: 5px; }
        input[type="text"], input[type="number"], select, textarea { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; }
        textarea { height: 100px; resize: vertical; }
        .row { display: flex; gap: 15px; }
        .col { flex: 1; }
        button { background-color: #27ae60; color: white; padding: 12px; border: none; border-radius: 5px; width: 100%; font-size: 16px; font-weight: bold; cursor: pointer; margin-top: 20px; transition: background 0.2s; }
        button:hover { background-color: #219150; }
        button:disabled { background-color: #95a5a6; cursor: not-allowed; }
        #loading { display: none; text-align: center; margin-top: 15px; font-style: italic; color: #7f8c8d; }
        #resultado-section { display: none; margin-top: 25px; border-top: 2px solid #eee; padding-top: 15px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
        th { background-color: #f2f2f2; }
        .btn-save { background-color: #8e44ad; margin-top: 15px; }
        .btn-save:hover { background-color: #71368a; }
        .btn-copy { background-color: #2980b9; margin-top: 10px; }
        .btn-copy:hover { background-color: #1f6391; }
        .user-badge { background: #e0f2fe; color: #0369a1; padding: 6px 12px; border-radius: 6px; font-size: 13px; font-weight: bold; display: inline-block; margin-bottom: 15px; }
        .error-user { background: #fee2e2; color: #991b1b; padding: 12px; border-radius: 6px; margin-bottom: 15px; font-weight: bold; border-left: 4px solid #dc2626; }
    </style>
</head>
<body>

<div class="container">
    {% if user_id %}
        <div class="user-badge">👤 Usuario conectado: {{ user_id }} (Pestaña: Comidas_{{ user_id }})</div>
    {% else %}
        <div class="error-user">⚠️ Atención: Acceso anónimo detectado. No se pueden realizar consultas a la IA ni guardar en planillas. Por favor, accedé mediante el link personalizado enviado por el bot de Telegram.</div>
    {% endif %}

    <h2>🍳 Generador de Comidas Precargadas</h2>
    
    <div class="row">
        <div class="col" style="flex: 0.4;">
            <label for="codigo">Código / Nombre (Columna A):</label>
            <input type="text" id="codigo" placeholder="Ej: PASCUALINAP" style="text-transform: uppercase;" {% if not user_id %}disabled{% endif %}>
        </div>
        <div class="col">
            <label for="descripcion">Descripción de la Comida (Columna B):</label>
            <input type="text" id="descripcion" placeholder="Ej: Porción de pascualina de atún o torta de chocolate" {% if not user_id %}disabled{% endif %}>
        </div>
    </div>

    <label for="recetaText">Ingredientes y Cantidades (Receta Completa):</label>
    <textarea id="recetaText" placeholder="Ej:&#10;1 kg de harina&#10;6 huevos&#10;200 g de manteca&#10;300 g de azúcar" {% if not user_id %}disabled{% endif %}></textarea>

    <div class="row">
        <div class="col">
            <label for="tipoCalculo">Criterio de División:</label>
            <select id="tipoCalculo" onchange="toggleCriterio()" {% if not user_id %}disabled{% endif %}>
                <option value="porciones">Dividir por cantidad de Porciones</option>
                <option value="gramos">Dividir de a 100 gramos (Fracción fija 100g)</option>
            </select>
        </div>
        <div class="col" id="colPorciones">
            <label for="porciones">Cantidad de Porciones:</label>
            <input type="number" id="porciones" value="1" min="1" {% if not user_id %}disabled{% endif %}>
        </div>
    </div>

    <button onclick="calcularReceta()" {% if not user_id %}disabled title="Acceso restringido a usuarios registrados vía Telegram"{% endif %}>✨ Calcular Fila con IA</button>

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
    if (!currentUserId) {
        alert("Acción no permitida para usuarios no registrados.");
        return;
    }

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
                user_id: currentUserId,
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
        alert("No hay ID de usuario asociado.");
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

@app.route('/', methods=['GET'])
def vista_calculadora():
    """Renderiza la calculadora de recetas como única página principal, recibiendo el user_id por URL."""
    user_id = request.args.get('user_id', '')
    return render_template_string(HTML_CALCULADORA_RECETAS, user_id=user_id)


@app.route('/api/calcular-receta', methods=['POST'])
def api_calcular_receta():
    """Procesa los datos con Groq validando obligatoriamente que venga un user_id válido."""
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        # Seguridad extra en backend: Bloquear si no hay user_id (evita consumo anónimo de tokens)
        if not user_id:
            return jsonify({"error": "Acceso denegado. Se requiere un usuario válido de Telegram para usar la IA."}), 403

        if not client_ai:
            return jsonify({"error": "GROQ_API_KEY no está configurada en el servidor."}), 500

        codigo_nombre = data.get('codigo', '').strip().upper()
        descripcion = data.get('descripcion', '').strip()
        receta = data.get('receta', '').strip()
        tipo_calculo = data.get('tipoCalculo', 'porciones')  
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
            factor = 100.0 / peso_tot if peso_tot > 0 else 1.0
            peso_unitario = 100.0
            cal_unitario = cal_tot * factor
            prot_unitario = prot_tot * factor
            gras_unitario = gras_tot * factor
            carb_unitario = carb_tot * factor
            fibr_unitario = fibr_tot * factor
            desc_final = f"{descripcion} porcion 100 g"
        else:
            div = porciones if porciones > 0 else 1
            peso_unitario = peso_tot / div
            cal_unitario = cal_tot / div
            prot_unitario = prot_tot / div
            gras_unitario = gras_tot / div
            carb_unitario = carb_tot / div
            fibr_unitario = fibr_tot / div
            desc_final = f"{descripcion} porcion {int(round(peso_unitario))} g"

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
    """Guarda la fila calculada validando el usuario."""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        fila = data.get('fila')

        if not user_id or not fila:
            return jsonify({"error": "Faltan parámetros obligatorios (user_id o fila)."}), 400

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
#                 INICIO                           GOOGLE SHEETS OPERACIONES  2026 09 05                          INICIO
# =============================================================================================================================================

# ---------------------------------------------------------------------------------------------------------------------------------------------
# 1. CLIENTES Y CONEXIÓN BASE (VAN PRIMERO)
# ---------------------------------------------------------------------------------------------------------------------------------------------
def _obtener_conexion_db():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise Exception("DATABASE_URL no está configurada en las variables de entorno.")
    # Se agrega sslmode='require' para que Supabase acepte la conexión de seguridad
    if "?" in db_url:
        if "sslmode" not in db_url:
            db_url += "&sslmode=require"
    else:
        db_url += "?sslmode=require"
    return psycopg2.connect(db_url)

def _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comida"):
    conn = _obtener_conexion_db()
    cur = conn.cursor()

    if tipo_tabla == "comida":
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tabla_nombre} (
                id SERIAL PRIMARY KEY,
                "Fecha" TEXT,
                "Momento/Actividad" TEXT,
                "Alimento/Detalle" TEXT,
                "Peso (g)" DOUBLE PRECISION,
                "Calorías (kcal)" DOUBLE PRECISION,
                "Proteínas (g)" DOUBLE PRECISION,
                "Grasas (g)" DOUBLE PRECISION,
                "Hidratos (g)" DOUBLE PRECISION,
                "Fibras (g)" DOUBLE PRECISION
            );
        """)
    elif tipo_tabla == "comidas_precargadas":
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tabla_nombre} (
                id SERIAL PRIMARY KEY,
                "Nombre" TEXT,
                "Descripcion" TEXT,
                "Peso" DOUBLE PRECISION,
                "Calorias" DOUBLE PRECISION,
                "Proteinas" DOUBLE PRECISION,
                "Grasas" DOUBLE PRECISION,
                "Carbohidratos" DOUBLE PRECISION,
                "Fibras" DOUBLE PRECISION
            );
        """)
    elif tipo_tabla == "presion":
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tabla_nombre} (
                id SERIAL PRIMARY KEY,
                "Fecha_Hora" TEXT,
                "Fecha_Dia" TEXT,
                "Alta" DOUBLE PRECISION,
                "Baja" DOUBLE PRECISION,
                "Pulsaciones" DOUBLE PRECISION,
                "Nota" TEXT
            );
        """)
    elif tipo_tabla == "perfil":
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tabla_nombre} (
                id SERIAL PRIMARY KEY,
                "EDAD" TEXT,
                "PESO" DOUBLE PRECISION,
                "ALTURA" DOUBLE PRECISION,
                "GENERO" TEXT,
                ocupacion DOUBLE PRECISION,
                mes TEXT UNIQUE,
                fecha_actualizacion TEXT,
                "Peso_ideal" DOUBLE PRECISION,
                "Cumple" TEXT
            );
        """)

    conn.commit()
    return conn, cur
        
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

def _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comida"):
    conn = _obtener_conexion_db()
    cur = conn.cursor()

    if tipo_tabla == "comida":
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tabla_nombre} (
                id SERIAL PRIMARY KEY,
                "Fecha" TEXT,
                "Momento/Actividad" TEXT,
                "Alimento/Detalle" TEXT,
                "Peso (g)" DOUBLE PRECISION,
                "Calorías (kcal)" DOUBLE PRECISION,
                "Proteínas (g)" DOUBLE PRECISION,
                "Grasas (g)" DOUBLE PRECISION,
                "Hidratos (g)" DOUBLE PRECISION,
                "Fibras (g)" DOUBLE PRECISION
            );
        """)
    elif tipo_tabla == "comidas_precargadas":
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tabla_nombre} (
                id SERIAL PRIMARY KEY,
                "Nombre" TEXT,
                "Descripcion" TEXT,
                "Peso" DOUBLE PRECISION,
                "Calorias" DOUBLE PRECISION,
                "Proteinas" DOUBLE PRECISION,
                "Grasas" DOUBLE PRECISION,
                "Carbohidratos" DOUBLE PRECISION,
                "Fibras" DOUBLE PRECISION
            );
        """)
    elif tipo_tabla == "presion":
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tabla_nombre} (
                id SERIAL PRIMARY KEY,
                "Fecha_Hora" TEXT,
                "Fecha_Dia" TEXT,
                "Alta" DOUBLE PRECISION,
                "Baja" DOUBLE PRECISION,
                "Pulsaciones" DOUBLE PRECISION,
                "Nota" TEXT
            );
        """)
    elif tipo_tabla == "perfil":
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tabla_nombre} (
                id SERIAL PRIMARY KEY,
                "EDAD" TEXT,
                "PESO" DOUBLE PRECISION,
                "ALTURA" DOUBLE PRECISION,
                "GENERO" TEXT,
                ocupacion DOUBLE PRECISION,
                mes TEXT UNIQUE,
                fecha_actualizacion TEXT,
                "Peso_ideal" DOUBLE PRECISION,
                "Cumple" TEXT
            );
        """)

    conn.commit()
    return conn, cur
    
def _calcular_y_actualizar_factor_mes_anterior(user_id, sheet_perfil, mes_anterior_str, peso_fin_mes_override=None):
    """
    Calcula el factor del mes anterior extrayendo los promedios reales de ingesta 
    y ejercicio, calculando el delta de peso real durante el mes y actualizando 
    el resultado en la hoja Perfil de Google Sheets.
    """
    try:
        df_datos = obtener_datos_usuario(user_id) if 'obtener_datos_usuario' in globals() else pd.DataFrame()
        if df_datos.empty or 'Fecha' not in df_datos.columns:
            return None

        df_mes = df_datos[df_datos['Fecha'].astype(str).str.startswith(mes_anterior_str)].copy()
        if df_mes.empty:
            return None

        dias_registrados = df_mes['Fecha'].nunique()
        if dias_registrados == 0:
            dias_registrados = 1

        tot_cons_mes = float(df_mes[df_mes['Calorias'] > 0]['Calorias'].sum()) if 'Calorias' in df_mes.columns else 0.0
        tot_quem_mes = float(abs(df_mes[df_mes['Calorias'] < 0]['Calorias'].sum())) if 'Calorias' in df_mes.columns else 0.0

        ingesta_diaria = tot_cons_mes / dias_registrados
        ejercicio_diario = tot_quem_mes / dias_registrados

        # Obtención segura del perfil desde Google Sheets
        perfil = obtener_perfil_usuario(user_id, mes_target=mes_anterior_str) if 'obtener_perfil_usuario' in globals() else {}
        
        peso_actual = float(perfil.get('Peso', perfil.get('peso', 108400)))
        if peso_actual > 1000: peso_actual /= 1000.0
        
        altura = float(perfil.get('Altura', perfil.get('altura', 167000)))
        if altura > 1000: altura /= 1000.0
        
        edad = int(perfil.get('Edad', perfil.get('edad', 64)))
        genero = str(perfil.get('GENERO', perfil.get('genero', 'M'))).strip()

        tmb_pura, _ = calcular_tmb_y_get(
            peso_actual=peso_actual, altura_cm=altura, edad=edad, genero=genero, actividad=1.0
        )
        if tmb_pura <= 0:
            tmb_pura = 1813.0

        delta_peso = 0.0
        try:
            if sheet_perfil is not None:
                records_p = sheet_perfil.get_all_records()
                pesos_por_mes = {}
                for r in records_p:
                    m_val = str(r.get('MES', r.get('Mes', ''))).strip()
                    p_val = r.get('PESO', r.get('Peso', 0))
                    if m_val and p_val:
                        try:
                            p_num = float(str(p_val).replace(',', '.'))
                            if p_num > 1000: p_num /= 1000.0
                            pesos_por_mes[m_val] = p_num
                        except ValueError:
                            pass
                
                meses_ordenados = sorted(pesos_por_mes.keys())
                if mes_anterior_str in meses_ordenados:
                    peso_inicio_mes = pesos_por_mes[mes_anterior_str]
                    
                    if peso_fin_mes_override is not None:
                        peso_fin_mes = float(peso_fin_mes_override)
                        if peso_fin_mes > 1000: peso_fin_mes /= 1000.0
                        delta_peso = peso_fin_mes - peso_inicio_mes
                    else:
                        idx_actual = meses_ordenados.index(mes_anterior_str)
                        if idx_actual + 1 < len(meses_ordenados):
                            mes_siguiente = meses_ordenados[idx_actual + 1]
                            peso_fin_mes = pesos_por_mes[mes_siguiente]
                            delta_peso = peso_fin_mes - peso_inicio_mes
                        else:
                            delta_peso = 0.0
        except Exception as e_delta:
            logger.error(f"Error calculando delta de peso dinámico para User {user_id}: {e_delta}")
            delta_peso = 0.0

        gasto_diario_total = ingesta_diaria - ((delta_peso * 7700.0) / dias_registrados)
        factor_limpio = (gasto_diario_total - ejercicio_diario) / tmb_pura
        
        factor_limpio = max(1.20, min(1.85, factor_limpio))
        ocupacion_sheet = int(round(factor_limpio * 1000))

        try:
            if sheet_perfil is not None:
                # BÚSQUEDA SEGURA: Se busca estrictamente en la columna F (MES)
                cell = sheet_perfil.find(str(mes_anterior_str), in_column=6)
                if cell:
                    fila_encontrada = cell.row
                    sheet_perfil.update_cell(fila_encontrada, 5, ocupacion_sheet) # Columna E es ocupación (5)
                    logger.info(f"Ocupación del mes {mes_anterior_str} recalculada y actualizada a {ocupacion_sheet} en la fila {fila_encontrada}")
                else:
                    logger.warning(f"No se encontró el mes {mes_anterior_str} en la columna F de la hoja Perfil.")
        except Exception as sheet_err:
            logger.error(f"No se pudo escribir el factor en la hoja de Google Sheets: {sheet_err}")

        return factor_limpio

    except Exception as e:
        logger.error(f"Error al calcular factor limpio del mes anterior para User {user_id}: {e}")
        return None
                        
        
def obtener_perfil_usuario(user_id, mes_target=None):
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws = get_or_create_worksheet(sh, f"Perfil_{user_id}")
        records = ws.get_all_records()
        if not records:
            return None
        
        perfil_raw = None

        # Si viene un mes (ej: "2026-05"), buscamos la fila que coincida en la columna MES
        if mes_target:
            target_clean = str(mes_target).strip()
            for r in records:
                m_val = str(r.get('MES', r.get('Mes', r.get('mes', '')))).strip()
                # Corta a 7 caracteres por si Google Sheets devuelve fecha completa YYYY-MM-DD
                if m_val.startswith(target_clean):
                    perfil_raw = r
                    break
        
        # Si no se especificó mes o no se encontró esa fila, toma la última por defecto
        if not perfil_raw:
            perfil_raw = records[-1]
        
        perfil = {}
        peso_hallado = None

        for k, v in perfil_raw.items():
            k_upper = str(k).strip().upper()
            
            if k_upper == 'EDAD':
                val = parse_float_from_sheets(v)
                val_norm = val / 1000.0 if val > 1000 else val
                perfil['Edad'] = val_norm
                perfil['edad'] = val_norm
            elif k_upper == 'PESO':
                val = parse_float_from_sheets(v)
                val_norm = val / 1000.0 if val > 1000 else val
                peso_hallado = val_norm
                # Guardamos todas las variantes de nombre de clave posible
                perfil['Peso'] = val_norm
                perfil['peso'] = val_norm
                perfil['peso_actual'] = val_norm
            elif k_upper == 'ALTURA':
                val = parse_float_from_sheets(v)
                val_norm = val / 1000.0 if val > 1000 else val
                perfil['Altura'] = val_norm
                perfil['altura'] = val_norm
            elif k_upper in ['PESO_IDEAL', 'PESO IDEAL']:
                val = parse_float_from_sheets(v)
                val_norm = val / 1000.0 if val > 1000 else val
                perfil['Peso_ideal'] = val_norm
                perfil['peso_ideal'] = val_norm
            elif k_upper in ['GENERO', 'SEXO']:
                perfil['Sexo'] = str(v).strip()
                perfil['genero'] = str(v).strip()
            elif k_upper == 'OCUPACION':
                # Procesa el número (ej: 1400 -> 1.4)
                val = parse_float_from_sheets(v)
                val_norm = (val / 1000.0) if val > 1000 else val
                # Si por alguna razón vino en 0 o vacío, asigna por defecto 1.
                factor_final = val_norm if val_norm > 0 else 1.375
                
                perfil['Ocupacion'] = factor_final
                perfil['ocupacion'] = factor_final
                perfil['factor_actividad'] = factor_final
            elif k_upper == 'MES':
                perfil['Mes'] = str(v).strip()
                perfil['mes'] = str(v).strip()

        # Marca si el peso de ese mes aún no se ingresó (está pendiente)
        perfil['peso_pendiente'] = (peso_hallado is None or peso_hallado <= 0)

        return perfil
    except Exception as e:
        print(f"Error obteniendo perfil del usuario {user_id}: {e}")
        return None

def obtener_perfil_usuario_supa(user_id, mes_target=None):
    """
    Versión para Supabase de obtener_perfil_usuario.
    Lee directamente de la tabla 'perfil_{user_id}' en PostgreSQL y devuelve un diccionario
    con los datos antropométricos del usuario para el mes especificado (o el último disponible).
    """
    try:
        tabla_nombre = f"perfil_{user_id}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="perfil")
        
        query = f"""
            SELECT "EDAD", "PESO", "ALTURA", "GENERO", "OCUPACION", "MES", "Fecha_Actualizacion"
            FROM {tabla_nombre}
            ORDER BY id ASC
        """
        
        cur.execute(query)
        filas = cur.fetchall()
        
        if not filas:
            cur.close()
            conn.close()
            return None
            
        records = []
        for fila in filas:
            records.append({
                'EDAD': fila[0],
                'PESO': fila[1],
                'ALTURA': fila[2],
                'GENERO': fila[3],
                'OCUPACION': fila[4],
                'MES': fila[5],
                'Fecha_Actualizacion': fila[6]
            })
            
        cur.close()
        conn.close()
        
        perfil_raw = None

        if mes_target:
            target_clean = str(mes_target).strip()
            for r in records:
                m_val = str(r.get('MES', '')).strip()
                if m_val.startswith(target_clean):
                    perfil_raw = r
                    break
        
        if not perfil_raw:
            perfil_raw = records[-1]
        
        perfil = {}
        peso_hallado = None

        for k, v in perfil_raw.items():
            k_upper = str(k).strip().upper()
            
            if k_upper == 'EDAD':
                val = float(v or 0)
                perfil['Edad'] = val
                perfil['edad'] = val
            elif k_upper == 'PESO':
                val = float(v or 0)
                peso_hallado = val if val > 0 else None
                perfil['Peso'] = val
                perfil['peso'] = val
                perfil['peso_actual'] = val
            elif k_upper == 'ALTURA':
                val = float(v or 0)
                perfil['Altura'] = val
                perfil['altura'] = val
            elif k_upper in ['PESO_IDEAL', 'PESO IDEAL']:
                val = float(v or 0)
                perfil['Peso_ideal'] = val
                perfil['peso_ideal'] = val
            elif k_upper in ['GENERO', 'SEXO']:
                perfil['Sexo'] = str(v).strip()
                perfil['genero'] = str(v).strip()
            elif k_upper == 'OCUPACION':
                val = float(v or 0)
                factor_final = val if val > 0 else 1.375
                perfil['Ocupacion'] = factor_final
                perfil['ocupacion'] = factor_final
                perfil['factor_actividad'] = factor_final
            elif k_upper == 'MES':
                perfil['Mes'] = str(v).strip()
                perfil['mes'] = str(v).strip()

        perfil['peso_pendiente'] = (peso_hallado is None or peso_hallado <= 0)

        return perfil
    except Exception as e:
        print(f"Error obteniendo perfil de Supabase para el usuario {user_id}: {e}")
        return None
        
def requiere_registro(func):
    """Decorador que valida que el user_id de Telegram exista y no esté dado de baja en la hoja 'Usuarios'."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = str(update.effective_user.id).strip()
        encontrado = False
        esta_activo = True  # Por defecto asumimos activo si pasa las validaciones de baja

        mensaje_no_registrado = (
            "⚠️ **¡Aún no estás registrado!**\n\n"
            "Para poder utilizar este comando y acceder a tu plan nutricional, "
            "primero necesitás darte de alta en el sistema.\n\n"
            "👉 Usá el comando `/ingreso` o `/nuevo` para crear tu ficha en un par de pasos."
        )
        mensaje_deshabilitado = "❌ **Su usuario ha sido deshabilitado debido a inactividad o baja del sistema, contáctese con el administrador del bot.**"

        try:
            # Consultar la pestaña general "Usuarios"
            gc = get_gspread_client()
            sh = gc.open(SPREADSHEET_NAME)
            ws_usuarios = sh.worksheet("Usuarios")
            records = ws_usuarios.get_all_records()

            # Buscar si el ID de Telegram está en la columna "User ID" y comprobar su estado
            for r in records:
                id_hoja = str(r.get("User ID", r.get("user_id", ""))).split('.')[0].strip()
                if id_hoja == user_id:
                    encontrado = True
                    # Verificamos la columna "Estado"
                    estado_val = str(r.get("Estado", r.get("estado", "0"))).strip().lower()
                    
                    # Si el estado indica baja explícita o superó los avisos (ej. "3" o "baja")
                    if estado_val in ['baja', 'suspendido', '3']:
                        esta_activo = False
                    break
        except Exception as e:
            print(f"Error al verificar registro y estado en Usuarios: {e}")

        if not encontrado:
            if update.message:
                await update.message.reply_text(mensaje_no_registrado, parse_mode="Markdown")
            elif update.callback_query:
                await update.callback_query.answer("⚠️ Registro requerido", show_alert=True)
                await update.callback_query.message.reply_text(mensaje_no_registrado, parse_mode="Markdown")
            return

        if not esta_activo:
            if update.message:
                await update.message.reply_text(mensaje_deshabilitado, parse_mode="Markdown")
            elif update.callback_query:
                await update.callback_query.answer("⚠️ Usuario deshabilitado", show_alert=True)
                await update.callback_query.message.reply_text(mensaje_deshabilitado, parse_mode="Markdown")
            return

        return await func(update, context, *args, **kwargs)
    return wrapper
    
    
# ---------------------------------------------------------------------------------------------------------------------------------------------
# 1. FUNCIÓN DE CONEXIÓN Y CREACIÓN DE TABLAS (CON LOS NOMBRES EXACTOS DEL EXCEL)
# ---------------------------------------------------------------------------------------------------------------------------------------------

def _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comida"):
    conn = _obtener_conexion_db()
    cur = conn.cursor()

    if tipo_tabla == "comida":
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tabla_nombre} (
                id SERIAL PRIMARY KEY,
                "Fecha" TEXT,
                "Momento/Actividad" TEXT,
                "Alimento/Detalle" TEXT,
                "Peso (g)" DOUBLE PRECISION,
                "Calorías (kcal)" DOUBLE PRECISION,
                "Proteínas (g)" DOUBLE PRECISION,
                "Grasas (g)" DOUBLE PRECISION,
                "Hidratos (g)" DOUBLE PRECISION,
                "Fibras (g)" DOUBLE PRECISION
            );
        """)
    elif tipo_tabla == "comidas_precargadas":
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tabla_nombre} (
                id SERIAL PRIMARY KEY,
                "Nombre" TEXT,
                "Descripcion" TEXT,
                "Peso" DOUBLE PRECISION,
                "Calorias" DOUBLE PRECISION,
                "Proteinas" DOUBLE PRECISION,
                "Grasas" DOUBLE PRECISION,
                "Carbohidratos" DOUBLE PRECISION,
                "Fibras" DOUBLE PRECISION
            );
        """)
    elif tipo_tabla == "presion":
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tabla_nombre} (
                id SERIAL PRIMARY KEY,
                "Fecha_Hora" TEXT,
                "Fecha_Dia" TEXT,
                "Alta" DOUBLE PRECISION,
                "Baja" DOUBLE PRECISION,
                "Pulsaciones" DOUBLE PRECISION,
                "Nota" TEXT
            );
        """)
    elif tipo_tabla == "perfil":
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tabla_nombre} (
                id SERIAL PRIMARY KEY,
                "EDAD" TEXT,
                "PESO" DOUBLE PRECISION,
                "ALTURA" DOUBLE PRECISION,
                "GENERO" TEXT,
                "OCUPACION" DOUBLE PRECISION,
                "MES" TEXT,
                "Fecha_Actualizacion" TEXT
            );
        """)

    conn.commit()
    return conn, cur

# ---------------------------------------------------------------------------------------------------------------------------------------------
# 3. OPERACIONES DE PERSISTENCIA Y REGISTRO (ESCRITURA) - CORREGIDAS AL 100% CON EL EXCEL Y LA CONEXIÓN CORRECTA A SUPABASE
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
            item.get("alimento", item.get("Alimento/Detalle", "Desconocido")),
            to_sheet_int(item.get("peso", item.get("Peso (g)", 0))),
            to_sheet_int(item.get("calorias", item.get("Calorías (kcal)", 0))),
            to_sheet_int(item.get("proteinas", item.get("Proteínas (g)", 0))),
            to_sheet_int(item.get("grasas", item.get("Grasas (g)", 0))),
            to_sheet_int(item.get("carbohidratos", item.get("hidratos", item.get("Hidratos (g)", 0)))),
            to_sheet_int(item.get("fibras", item.get("Fibras (g)", 0)))
        ])
    if rows:
        ws.append_rows(rows)

    # Espejo simultáneo en Supabase
    try:
        tabla_nombre = f"user_{user_id}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comida")
        
        for item in items:
            query = f"""
                INSERT INTO {tabla_nombre} ("Fecha", "Momento/Actividad", "Alimento/Detalle", "Peso (g)", "Calorías (kcal)", "Proteínas (g)", "Grasas (g)", "Hidratos (g)", "Fibras (g)")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            valores = (
                str(fecha), 
                str(momento), 
                str(item.get("alimento", item.get("Alimento/Detalle", "Desconocido"))), 
                float(item.get("peso", item.get("Peso (g)", 0))), 
                float(item.get("calorias", item.get("Calorías (kcal)", 0))), 
                float(item.get("proteinas", item.get("Proteínas (g)", 0))), 
                float(item.get("grasas", item.get("Grasas (g)", 0))), 
                float(item.get("carbohidratos", item.get("hidratos", item.get("Hidratos (g)", 0)))), 
                float(item.get("fibras", item.get("Fibras (g)", 0)))
            )
            cur.execute(query, valores)
            
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error interno al duplicar ingesta en Supabase (User_{user_id}): {e}")

def guardar_comida_precargada_db(user_id, fila):
    ws = get_user_worksheet(user_id)
    codigo_original = fila.get('Nombre', fila.get('nombre', ''))
    codigo_unico = obtener_codigo_unico(ws, codigo_original)

    nueva_fila = [
        codigo_unico,
        fila.get('Descripcion', fila.get('descripcion', '')),
        fila.get('Peso', fila.get('peso', 0)),
        fila.get('Calorias', fila.get('calorias', 0)),
        fila.get('Proteinas', fila.get('proteinas', 0)),
        fila.get('Grasas', fila.get('grasas', 0)),
        fila.get('Carbohidratos', fila.get('carbohidratos', fila.get('Hidratos', 0))),
        fila.get('Fibras', fila.get('fibras', 0))
    ]
    
    ws.append_row(nueva_fila)

    try:
        tabla_nombre = f"comidas_{user_id}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comidas_precargadas")

        p_val = float(fila.get('Peso', fila.get('peso', 0)))
        c_val = float(fila.get('Calorias', fila.get('calorias', 0)))
        pr_val = float(fila.get('Proteinas', fila.get('proteinas', 0)))
        g_val = float(fila.get('Grasas', fila.get('grasas', 0)))
        h_val = float(fila.get('Carbohidratos', fila.get('carbohidratos', fila.get('Hidratos', 0))))
        f_val = float(fila.get('Fibras', fila.get('fibras', 0)))

        query = f"""
            INSERT INTO {tabla_nombre} ("Nombre", "Descripcion", "Peso", "Calorias", "Proteinas", "Grasas", "Carbohidratos", "Fibras")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        valores = (
            str(codigo_unico), 
            str(fila.get('Descripcion', fila.get('descripcion', ''))), 
            p_val / 1000.0 if p_val > 1000 else p_val, 
            c_val / 1000.0 if c_val > 1000 else c_val, 
            pr_val / 1000.0 if pr_val > 1000 else pr_val, 
            g_val / 1000.0 if g_val > 1000 else g_val, 
            h_val / 1000.0 if h_val > 1000 else h_val, 
            f_val / 1000.0 if f_val > 1000 else f_val
        )
        cur.execute(query, valores)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error interno al grabar Comida Precargada en Supabase (Comidas_{user_id}): {e}")
    return codigo_unico

def guardar_presion_db(user_id, alta, baja, pulsaciones=None, nota=""):
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    ws = get_or_create_worksheet(sh, f"Presion_{user_id}")
    ahora = obtener_ahora_arg()
    
    val_pul = int(pulsaciones * 1000) if pulsaciones is not None else 0

    ws.append_row([
        ahora.strftime("%Y-%m-%d %H:%M:%S"), 
        ahora.strftime("%Y-%m-%d"), 
        int(alta * 1000) if alta < 250 else int(alta), 
        int(baja * 1000) if baja < 150 else int(baja), 
        val_pul,
        str(nota).strip()
    ])

    try:
        tabla_nombre = f"presion_{user_id}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="presion")

        query = f"""
            INSERT INTO {tabla_nombre} ("Fecha_Hora", "Fecha_Dia", "Alta", "Baja", "Pulsaciones", "Nota")
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        valores = (
            ahora.strftime("%Y-%m-%d %H:%M:%S"), 
            ahora.strftime("%Y-%m-%d"), 
            float(alta), 
            float(baja), 
            float(pulsaciones) if pulsaciones is not None else 0.0, 
            str(nota).strip()
        )
        cur.execute(query, valores)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error interno al grabar Presión en Supabase (Presion_{user_id}): {e}")
        
def guardar_perfil_db(user_id, peso, mes=None, edad=None, altura=None, genero=None, ocupacion=None, *args, **kwargs):
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    ws = get_or_create_worksheet(sh, f"Perfil_{user_id}")
    ahora = obtener_ahora_arg()
    
    if not mes:
        mes = ahora.strftime("%Y-%m")
    
    records = ws.get_all_records()
    fila_a_actualizar = None

    if records:
        for idx, row in enumerate(records, start=2):
            mes_en_fila = str(row.get('MES', row.get('Mes', ''))).strip()
            if mes_en_fila == str(mes):
                fila_a_actualizar = idx
                break

    peso_nuevo_sheet = to_sheet_int(peso)

    if fila_a_actualizar:
        peso_actual_en_celda = str(ws.cell(fila_a_actualizar, 2).value).strip()
        if peso_actual_en_celda == str(peso_nuevo_sheet):
            print(f"📌 El peso {peso} ya estaba registrado para el mes {mes}. No se reescribe nada.")
            return

        ws.update(f"B{fila_a_actualizar}", [[peso_nuevo_sheet]])
        ws.update(f"G{fila_a_actualizar}", [[ahora.strftime("%Y-%m-%d %H:%M:%S")]])
        ocupacion_final_para_usuarios = ws.cell(fila_a_actualizar, 5).value

    else:
        if len(records) >= 1:
            ultimo_reg_previo = records[-1]
            mes_anterior_str = str(ultimo_reg_previo.get('MES', ultimo_reg_previo.get('Mes', ''))).strip()
            
            if mes_anterior_str:
                _calcular_y_actualizar_factor_mes_anterior(user_id, ws, mes_anterior_str, peso_fin_mes_override=peso)

        records_actualizados = ws.get_all_records()
        
        valores_ocupacion = []
        for row in records_actualizados:
            val_ocu = row.get('ocupacion') or row.get('Ocupacion') or row.get('OCUPACION')
            if val_ocu:
                try:
                    num_val = float(str(val_ocu).replace(',', '.'))
                    if num_val > 100:
                        num_val = num_val / 1000.0
                    valores_ocupacion.append(num_val)
                except ValueError:
                    pass
        
        if valores_ocupacion:
            ultimos_tres = valores_ocupacion[-3:]
            promedio_ocupacion = sum(ultimos_tres) / len(ultimos_tres)
            ocupacion_calculada = int(round(promedio_ocupacion * 1000)) if promedio_ocupacion < 10 else int(round(promedio_ocupacion))
        else:
            ocupacion_calculada = ocupacion if ocupacion is not None else 1684

        ultimo_registro = records_actualizados[-1] if records_actualizados else {}
        edad_raw = ultimo_registro.get('EDAD', ultimo_registro.get('Edad', 64000))
        altura_raw = ultimo_registro.get('ALTURA', ultimo_registro.get('Altura', 172000))
        genero_final = str(ultimo_registro.get('GENERO', ultimo_registro.get('Genero', 'M')))
        peso_ideal_final = ultimo_registro.get('Peso_ideal', ultimo_registro.get('peso_ideal', ''))
        fecha_cumple_str = str(ultimo_registro.get('Cumple', ultimo_registro.get('cumple', ''))).strip()

        nueva_fila = [
            str(edad_raw),
            peso_nuevo_sheet,
            str(altura_raw),
            str(genero_final),
            str(ocupacion_calculada),
            str(mes),
            ahora.strftime("%Y-%m-%d %H:%M:%S"),
            str(peso_ideal_final),
            str(fecha_cumple_str)
        ]
        ws.append_row(nueva_fila)
        ocupacion_final_para_usuarios = ocupacion_calculada

    try:
        ws_usuarios = sh.worksheet("Usuarios")
        registros_usuarios = ws_usuarios.get_all_records()
        headers = ws_usuarios.row_values(1)
        
        col_idx_mes = 4
        col_idx_ocu = 10 

        for idx, h in enumerate(headers, start=1):
            h_lower = str(h).strip().lower()
            if h_lower in ["ultimo mes peso", "ultimo_mes_peso", "ultimomespeso"]:
                col_idx_mes = idx
            elif h_lower in ["ocupacion", "ocupación"]:
                col_idx_ocu = idx

        fila_usuario = None
        for i, reg in enumerate(registros_usuarios, start=2):
            id_reg = reg.get('ID') or reg.get('user_id') or reg.get('User ID') or list(reg.values())[0]
            if str(id_reg).strip() == str(user_id).strip():
                fila_usuario = i
                break

        if fila_usuario:
            from gspread.utils import rowcol_to_a1
            celda_mes_a1 = rowcol_to_a1(fila_usuario, col_idx_mes)
            fecha_usuarios_str = f"{str(mes)[:7]}-01"
            ws_usuarios.update(celda_mes_a1, [[fecha_usuarios_str]])

            celda_ocu_a1 = rowcol_to_a1(fila_usuario, col_idx_ocu)
            ws_usuarios.update(celda_ocu_a1, [[ocupacion_final_para_usuarios]])
            
    except Exception as e:
        print(f"❌ Error crítico al actualizar la pestaña 'Usuarios': {e}")

    # Espejo y creación automática de tabla en Supabase
    try:
        tabla_nombre = f"perfil_{user_id}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="perfil")
        
        cur.execute(f'SELECT id FROM {tabla_nombre} WHERE "MES" = %s', (str(mes),))
        fila_supa = cur.fetchone()
        
        peso_real = float(peso)
        if peso_real > 1000: peso_real /= 1000.0
        
        if fila_supa:
            cur.execute(f"""
                UPDATE {tabla_nombre}
                SET "PESO" = %s, "Fecha_Actualizacion" = %s
                WHERE "MES" = %s
            """, (peso_real, ahora.strftime("%Y-%m-%d %H:%M:%S"), str(mes)))
        else:
            edad_val = parse_float_from_sheets(edad_raw) if 'edad_raw' in locals() else 64.0
            altura_val = parse_float_from_sheets(altura_raw) if 'altura_raw' in locals() else 1.72
            ocupacion_val = (ocupacion_calculada / 1000.0) if ocupacion_calculada > 100 else ocupacion_calculada
            
            cur.execute(f"""
                INSERT INTO {tabla_nombre} ("EDAD", "PESO", "ALTURA", "GENERO", "OCUPACION", "MES", "Fecha_Actualizacion", "Peso_ideal", "Cumple")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(edad_raw) if 'edad_raw' in locals() else "64",
                peso_real,
                altura_val,
                str(genero_final) if 'genero_final' in locals() else "M",
                float(ocupacion_val),
                str(mes),
                ahora.strftime("%Y-%m-%d %H:%M:%S"),
                parse_float_from_sheets(peso_ideal_final) if 'peso_ideal_final' in locals() and peso_ideal_final else 0.0,
                str(fecha_cumple_str) if 'fecha_cumple_str' in locals() else ""
            ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error al duplicar perfil en Supabase (perfil_{user_id}): {e}")                                               
        
# ---------------------------------------------------------------------------------------------------------------------------------------------
# 4. OPERACIONES DE PERSISTENCIA Y REGISTRO (LECTURA)
# ---------------------------------------------------------------------------------------------------------------------------------------------

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

def obtener_datos_usuario_supa(user_id):
    """
    Versión para Supabase de obtener_datos_usuario.
    Lee directamente de la tabla 'user_{user_id}' en PostgreSQL y devuelve un DataFrame
    con los mismos nombres de columnas estandarizados ('Fecha', 'Momento', 'Alimento', 
    'Peso', 'Calorias', 'Proteinas', 'Grasas', 'Carbohidratos', 'Fibras').
    """
    try:
        tabla_nombre = f"user_{user_id}"
        # Aseguramos que la tabla exista y conectamos
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comida")
        
        query = f"""
            SELECT "Fecha", "Momento/Actividad", "Alimento/Detalle", 
                   "Peso (g)", "Calorías (kcal)", "Proteínas (g)", 
                   "Grasas (g)", "Hidratos (g)", "Fibras (g)"
            FROM {tabla_nombre}
        """
        
        # Leemos directo a un DataFrame de pandas usando la conexión activa
        df = pd.read_sql(query, conn)
        
        cur.close()
        conn.close()
        
        if df.empty:
            return pd.DataFrame()
        
        # Mapeo de columnas idéntico al que hace la función original de Sheets
        col_map = {
            'Fecha': 'Fecha',
            'Momento/Actividad': 'Momento',
            'Alimento/Detalle': 'Alimento',
            'Peso (g)': 'Peso',
            'Calorías (kcal)': 'Calorias',
            'Proteínas (g)': 'Proteinas',
            'Grasas (g)': 'Grasas',
            'Hidratos (g)': 'Carbohidratos',
            'Fibras (g)': 'Fibras'
        }
        
        df = df.rename(columns=col_map)
        
        if "Fecha" in df.columns and not df.empty:
            df['Fecha'] = df['Fecha'].astype(str).str.strip()
            for col in ['Peso', 'Calorias', 'Proteinas', 'Grasas', 'Carbohidratos', 'Fibras']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
                else:
                    df[col] = 0.0
                    
        return df
    except Exception as e:
        print(f"Error al obtener datos de Supabase para el usuario {user_id}: {e}")
        return pd.DataFrame()
        
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

def obtener_datos_presion_db_supa(user_id):
    """
    Versión para Supabase de obtener_datos_presion_db.
    Lee directamente de la tabla 'presion_{user_id}' en PostgreSQL y devuelve un DataFrame
    con los registros de presión arterial del usuario.
    """
    try:
        tabla_nombre = f"presion_{user_id}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="presion")
        
        query = f"""
            SELECT "Fecha_Hora", "Fecha_Dia", "Alta", "Baja", "Pulsaciones", "Nota"
            FROM {tabla_nombre}
        """
        
        df = pd.read_sql(query, conn)
        
        cur.close()
        conn.close()
        
        if df.empty:
            return pd.DataFrame()

        for col in ['Alta', 'Baja', 'Pulsaciones']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                # En Supabase los valores se guardan limpios, por lo que no es necesario dividir por 1000.

        if 'Fecha_Dia' in df.columns:
            df['Fecha_Dia'] = df['Fecha_Dia'].astype(str).str.strip()

        if 'Nota' not in df.columns:
            df['Nota'] = ""

        return df
    except Exception as e:
        logger.error(f"Error al obtener datos de presión de Supabase (presion_{user_id}): {e}")
        return pd.DataFrame()
        
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


def obtener_comidas_usuario_supa(user_id):
    """
    Versión para Supabase de obtener_comidas_usuario.
    Lee directamente de la tabla 'comidas_{user_id}' en PostgreSQL y devuelve una lista de diccionarios
    con las comidas precargadas del usuario.
    """
    try:
        tabla_nombre = f"comidas_{user_id}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comidas_precargadas")
        
        query = f"""
            SELECT "Nombre", "Descripcion", "Peso", "Calorias", "Proteinas", "Grasas", "Carbohidratos", "Fibras"
            FROM {tabla_nombre}
        """
        
        cur.execute(query)
        filas = cur.fetchall()
        
        records = []
        for fila in filas:
            records.append({
                'Nombre': fila[0],
                'Descripcion': fila[1],
                'Peso': float(fila[2] or 0),
                'Calorias': float(fila[3] or 0),
                'Proteinas': float(fila[4] or 0),
                'Grasas': float(fila[5] or 0),
                'Carbohidratos': float(fila[6] or 0),
                'Fibras': float(fila[7] or 0)
            })
            
        cur.close()
        conn.close()
        
        for p in records:
            p['Nombre'] = p.get('Nombre', '')
            p['Descripcion'] = p.get('Descripcion', '')
            
        return records
    except Exception as e:
        logger.error(f"Error al obtener comidas de Supabase (comidas_{user_id}): {e}")
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

# ======================================================================================================================================
#                    FINAL                              GOOGLE SHEETS OPERACIONES                      FINAL
# =======================================================================================================================================

# =============================================================================================================================================
#                       INICIO                     FUNCIONES AUXILIARES Y FORMATO                                   INICIO  
# =============================================================================================================================================

# ---------------------------------------------------------------------------------------------------------------------------------------------
# 1. PARSEO DE DATOS Y FECHAS (VAN PRIMERO POR SER UTILIZADOS EN OTRAS FUNCIONES)
# ---------------------------------------------------------------------------------------------------------------------------------------------

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

def calcular_contextura(sexo: str, altura_cm: float, muneca_cm: float) -> str:
    """Calcula la contextura física según la relación Altura / Muñeca."""
    if muneca_cm <= 0: return "Mediana"
    r = altura_cm / muneca_cm
    if str(sexo).upper() in ['M', 'MASCULINO']:
        if r > 10.4: return "Pequeña"
        elif 9.6 <= r <= 10.4: return "Mediana"
        else: return "Grande"
    else:
        if r > 11.0: return "Pequeña"
        elif 10.1 <= r <= 11.0: return "Mediana"
        else: return "Grande"

def calcular_peso_ideal(sexo: str, altura_cm: float) -> float:
    """Estimación de peso ideal mediante fórmula de Lorentz."""
    if str(sexo).upper() in ['M', 'MASCULINO']:
        return (altura_cm - 100) - ((altura_cm - 150) / 4.0)
    else:
        return (altura_cm - 100) - ((altura_cm - 150) / 2.5)

def calcular_peso_etapa(peso_actual: float, peso_ideal: float) -> float:
    """Calcula el peso objetivo prudente para la primera etapa (75% actual + 25% ideal)."""
    return round((peso_actual * 0.75) + (peso_ideal * 0.25), 1)
    
def calcular_tmb_y_get(peso_actual, altura_cm, edad, genero: str = "masculino", actividad = 1375, peso_ideal = None) -> tuple[float, float]:
    """
    Calcula TMB (Mifflin-St Jeor) y GET (Gasto Energético Total).
    Procesa números enteros (*1000) o strings/floats numéricos de forma tolerante.
    """
    def _parse_num(val, default):
        if val is None:
            return default
        try:
            # Si viene como string, normaliza comas y limpia espacios
            return float(str(val).replace(',', '.').strip())
        except (ValueError, TypeError):
            return default

    try:
        # 1. Obtención segura como float
        p_num = _parse_num(peso_actual, 70000.0)
        a_num = _parse_num(altura_cm, 170.0)
        e_num = _parse_num(edad, 30.0)
        act_num = _parse_num(actividad, 1375.0)

        # 2. Conversiones a escala real
        peso = p_num / 1000.0 if p_num > 1000 else p_num
        
        # Si la altura viene en cm o *1000
        altura = a_num / 1000.0 if a_num > 1000 else a_num
        
        años = int(e_num / 1000.0) if e_num > 1000 else int(e_num)
        
        # 3. Factor de Actividad: si es 1480 o 1500 pasa a 1.48 o 1.50; si ya era 1.48 se respeta
        factor_actividad = act_num / 1000.0 if act_num > 100 else act_num

        if factor_actividad <= 0:
            factor_actividad = 1.375

    except Exception as e:
        print(f"ERROR en calcular_tmb_y_get: {e}")
        peso, altura, años, factor_actividad = 70.0, 170.0, 30, 1.375

    gen_clean = str(genero).strip().lower()

    # Mifflin-St Jeor
    if gen_clean in ["femenino", "f", "mujer", "female"]:
        tmb = (10.0 * peso) + (6.25 * altura) - (5.0 * años) - 161.0
    else:
        tmb = (10.0 * peso) + (6.25 * altura) - (5.0 * años) + 5.0

    get = tmb * factor_actividad
    return round(tmb, 2), round(get, 2)
        
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
        "peso_actual": round(float(peso_actual), 1),
        "peso_ideal": round(float(peso_ideal), 1),
        "peso_referencia": round(float(peso_referencia), 1),
        "altura": round(float(altura), 1),
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

def obtener_categorias_diccionario(sh):
    """
    Lee la pestaña 'Categorias_Comida' y devuelve un diccionario {categoria: [lista_de_palabras_clave]}.
    """
    try:
        ws = get_or_create_worksheet(sh, "Categorias_Comida")
        records = ws.get_all_records()
        if not records:
            return {}
        
        df_cat = pd.DataFrame(records)
        cat_dict = {}
        for col in df_cat.columns:
            cat_nombre = str(col).strip().lower()
            # Filtra valores no vacíos
            palabras = [str(x).strip().lower() for x in df_cat[col].dropna().tolist() if str(x).strip()]
            if palabras:
                cat_dict[cat_nombre] = palabras
        return cat_dict
    except Exception as e:
        print(f"Error al leer Categorias_Comida: {e}")
        return {}

def analizar_frecuencia_alimentos_mes(user_id: int, mes_target: str = None) -> dict:
    """
    Analiza la frecuencia de consumo de cada grupo alimentario en el mes.
    Aplica la regla de exclusión celda por celda para harinas integrales vs refinadas.
    """
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        
        # 1. Cargar el diccionario de palabras clave por categoría
        cat_dict = obtener_categorias_diccionario(sh)
        if not cat_dict:
            return {}

        # 2. Obtener los registros del diario del usuario
        df = obtener_datos_usuario(user_id)
        if df.empty or 'Fecha' not in df.columns or 'Alimento' not in df.columns:
            return {}

        # 3. Filtrar por el mes deseado (ej: "2026-08")
        if not mes_target:
            ahora = obtener_ahora_arg()
            mes_target = ahora.strftime("%Y-%m")
        
        df['Mes_Filtro'] = df['Fecha'].str.slice(0, 7)
        df_mes = df[df['Mes_Filtro'] == str(mes_target).strip()].copy()
        
        if df_mes.empty:
            return {}

        # Identificar qué clave en el Excel representa cada grupo
        col_integrales = None
        col_refinadas = None
        otras_categorias = {}

        for cat_key, palabras in cat_dict.items():
            if 'integral' in cat_key:
                col_integrales = palabras
            elif 'refinada' in cat_key or 'blanca' in cat_key:
                col_refinadas = palabras
            else:
                otras_categorias[cat_key] = palabras

        # Diccionario acumulador de conteos
        frecuencias = {cat: 0 for cat in cat_dict.keys()}

        # 4. Procesamiento CELDA POR CELDA
        for _, row in df_mes.iterrows():
            texto_celda = str(row.get('Alimento', '')).strip().lower()
            if not texto_celda:
                continue

            # A. Regla de Harinas / Integrales
            es_integral = any(p in texto_celda for p in (col_integrales or ['integral', 'salvado']))
            
            if es_integral:
                # Suma a la categoría integral
                for cat_key in cat_dict.keys():
                    if 'integral' in cat_key:
                        frecuencias[cat_key] += 1
                # Excluye explícitamente de harinas refinadas
            else:
                # Si no fue integral, verifica si es harina refinada/blanca
                if col_refinadas and any(p in texto_celda for p in col_refinadas):
                    for cat_key in cat_dict.keys():
                        if 'refinada' in cat_key or 'blanca' in cat_key:
                            frecuencias[cat_key] += 1

            # B. Evaluación independiente del resto de categorías (Carnes, Pollo, Pescado, Verduras, Lácteos, etc.)
            for cat_nombre, palabras in otras_categorias.items():
                if any(p in texto_celda for p in palabras):
                    frecuencias[cat_nombre] += 1

        return frecuencias

    except Exception as e:
        print(f"Error analizando frecuencias de alimentos para user {user_id}: {e}")
        return {}
            
# ---------------------------------------------------------------------------------------------------------------------------------------------
# 3. INTEGRACIÓN CON IA (GROQ)
# ---------------------------------------------------------------------------------------------------------------------------------------------

async def procesar_informe_inicial_ia(datos_usuario: dict) -> tuple[str, io.BytesIO]:
    """
    Consulta a Groq con reintentos automáticos, audita el informe con el modelo de revisión 
    para garantizar calidad y evitar textos truncados, y compila el PDF de bienvenida.
    """
    nombre = datos_usuario.get('nombre')
    edad = datos_usuario.get('edad')
    sexo = datos_usuario.get('sexo')
    altura = datos_usuario.get('altura')
    peso = datos_usuario.get('peso')
    contextura = datos_usuario.get('contextura')
    peso_ideal = datos_usuario.get('peso_ideal')
    peso_etapa = datos_usuario.get('peso_etapa')
    tmb = datos_usuario.get('tmb')
    get_calorias = datos_usuario.get('get')

    # 1. Construcción del prompt clínico para el informe inicial
    prompt_ia = (
        f"Actúa como un médico nutricionista experto. Analiza el perfil del paciente:\n"
        f"- Nombre: {nombre}, Edad: {edad} años, Sexo: {sexo}\n"
        f"- Altura: {altura} cm, Peso Actual: {peso} kg\n"
        f"- Contextura ósea: {contextura}, Peso Ideal Teórico: {peso_ideal} kg\n"
        f"- Peso Objetivo para la 1ra Etapa (ponderado prudente 75/25): {peso_etapa} kg\n"
        f"- Gasto Basal (TMB): {tmb} kcal, Gasto Energético Total (GET): {get_calorias} kcal\n\n"
        f"Redacta un informe breve y motivador de bienvenida que incluya:\n"
        f"1. Una explicación clara y empática de por qué en esta primera etapa apuntamos a un peso objetivo intermedio ({peso_etapa} kg) en lugar de exigir el peso ideal final de golpe.\n"
        f"2. Una recomendación general sobre el manejo de la dieta y calorías diarias orientada a un déficit saludable basado en su GET.\n"
        f"3. Pautas generales de actividad física complementaria (caminatas, movilidad).\n"
        f"Mantén un tono profesional, cálido y alentador sin dejar oraciones inconclusas."
    )
    
    system_msg = "Eres un nutricionista clínico profesional y empático."
    prompt_auditor_base = (
        f"Actúa como un médico supervisor estricto y auditor de calidad. "
        f"Revisa el siguiente informe nutricional de bienvenida:\n\n"
        f"--- INFORME A EVALUAR ---\n{{informe_candidato}}\n-------------------------\n\n"
        f"INSTRUCCIONES DE AUDITORÍA:\n"
        f"1. Verifica que el texto sea coherente, empático, completo (sin cortes ni oraciones truncadas) y estrictamente profesional.\n"
        f"2. Si el informe está perfecto y listo para entregar, responde únicamente comenzando con la palabra 'OK'.\n"
        f"3. Si encuentras errores, oraciones inconclusas o falta de redacción, responde comenzando con la palabra 'RECHAZADO' indicando qué corregir."
    )

    informe_ia = ""
    max_intentos = 3

    # Función interna de reintentos rápidos para proteger las peticiones de red
    async def _llamar_ia_con_retry(p, tokens, temp, sys_p=None, mod_over=None, intentos_max=3):
        for it in range(1, intentos_max + 1):
            try:
                res = await asyncio.to_thread(
                    ejecutar_consulta_ia, 
                    prompt=p, 
                    max_tokens=tokens, 
                    temperature=temp, 
                    system_prompt=sys_p, 
                    modelo_override=mod_over
                )
                if res and res.strip():
                    return res
            except Exception as e:
                print(f"⚠️ Fallo en intento IA {it}/{intentos_max}: {e}")
                if it == intentos_max:
                    raise e
                await asyncio.sleep(2)
        return ""

    # Bucle principal de generación y auditoría cruzada
    for intento in range(1, max_intentos + 1):
        try:
            # 1. Generación del texto candidato
            texto_generado = await _llamar_ia_con_retry(
                prompt=prompt_ia, 
                max_tokens=600, 
                temperature=0.3, 
                system_prompt=system_msg
            )
            
            if not texto_generado:
                continue

            # 2. Instancia y consulta al Modelo Revisor
            prompt_auditor_final = prompt_auditor_base.format(informe_candidato=texto_generado)
            modelo_rev = globals().get('GROQ_REVISION', 'openai/gpt-oss-20b')
            
            veredicto = await _llamar_ia_con_retry(
                prompt=prompt_auditor_final, 
                max_tokens=150, 
                temperature=0.1, 
                modelo_override=modelo_rev
            )

            if veredicto and veredicto.strip().upper().startswith("OK"):
                informe_ia = texto_generado
                break
            else:
                motivo = veredicto.strip() if veredicto else "Sin respuesta"
                print(f"🔄 Revisor rechazó el informe inicial en el intento {intento}. Motivo: {motivo}")

        except Exception as err:
            print(f"❌ Error en ciclo de informe inicial (Intento {intento}): {err}")

    # Fallback por seguridad si se agotaran los intentos
    if not informe_ia:
        informe_ia = "Estimado paciente, le damos la bienvenida a su plan nutricional personalizado. Su ficha ha sido configurada correctamente con los parámetros metabólicos iniciales."

    # 3. Compilación del informe aprobado en formato PDF con ReportLab
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer, 
        pagesize=letter, 
        rightMargin=36, 
        leftMargin=36, 
        topMargin=36, 
        bottomMargin=36
    )
    story = []
    
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle(
        'TituloInforme', 
        parent=styles['Heading1'], 
        fontSize=15, 
        leading=18, 
        alignment=1, 
        textColor=colors.HexColor('#1b4f72')
    )
    sub_style = ParagraphStyle(
        'SubInforme', 
        parent=styles['Normal'], 
        fontSize=10, 
        leading=14, 
        textColor=colors.HexColor('#566573')
    )
    body_style = ParagraphStyle(
        'CuerpoInforme', 
        parent=styles['Normal'], 
        fontSize=10, 
        leading=15, 
        textColor=colors.HexColor('#2c3e50')
    )
    
    story.append(Paragraph("<b>INFORME NUTRICIONAL INICIAL - APERTURA DE FICHA</b>", titulo_style))
    story.append(Spacer(1, 10))
    
    resumen_datos = (
        f"<b>Paciente:</b> {nombre} | <b>ID Telegram:</b> `{datos_usuario.get('user_id')}`<br/>"
        f"<b>Edad:</b> {edad} años | <b>Sexo:</b> {sexo} | <b>Altura:</b> {altura} cm<br/>"
        f"<b>Peso Actual:</b> {peso} kg | <b>Contextura:</b> {contextura} | <b>Peso Ideal:</b> {peso_ideal} kg<br/>"
        f"<b>Objetivo Etapa 1:</b> {peso_etapa} kg | <b>TMB:</b> {round(tmb)} kcal | <b>GET:</b> {round(get_calorias)} kcal"
    )
    story.append(Paragraph(resumen_datos, sub_style))
    story.append(Spacer(1, 15))
    story.append(Paragraph("<b>EVALUACIÓN Y PLANIFICACIÓN INICIAL</b>", styles['Heading2']))
    story.append(Spacer(1, 8))
    
    # Reemplazo seguro de saltos de línea para compatibilidad con HTML de ReportLab
    texto_formateado = informe_ia.replace('\n', '<br/>')
    story.append(Paragraph(texto_formateado, body_style))
    
    doc.build(story)
    pdf_buffer.seek(0)
    
    return informe_ia, pdf_buffer
        
async def generar_informe_mensual_auditado(context, user_id, mes_str, m, frecuencias=None):
    """
    Función independiente para generar el informe mensual auditado usando la función centralizada.
    """
    if frecuencias is None:
        frecuencias = {}

    frec_str = "\n".join([f"- {cat}: {cant} ingestas" for cat, cant in frecuencias.items()]) if frecuencias else "- No hay frecuencias registradas."

    prompt_1 = (
        f"Actúa como un nutricionista clínico experto. A partir de los siguientes datos estadísticos ya calculados, "
        f"redacta un diagnóstico nutricional profundo del mes {mes_str}:\n"
        f"- Calorías promedio: {m.get('prom_cal', 0)} kcal (Meta: {m.get('ideal_cal', 0)} kcal)\n"
        f"- Proteínas: {m.get('prom_prot', 0)} g (Meta: {m.get('ideal_prot', 0)} g)\n"
        f"- Grasas: {m.get('prom_gras', 0)} g (Meta: {m.get('ideal_gras', 0)} g)\n"
        f"- Carbohidratos: {m.get('prom_carb', 0)} g (Meta: {m.get('ideal_carb', 0)} g)\n"
        f"- Fibras: {m.get('prom_fibr', 0)} g (Meta: {m.get('ideal_fibr', 0)} g)\n"
        f"Frecuencia de grupos alimentarios:\n{frec_str}\n"
        f"No pongas números falsos, céntrate en el análisis clínico global."
    )

    prompt_2 = (
        f"Siguiendo con el caso anterior, redacta una lista numerada del 1 al 10 con alimentos "
        f"específicos y accesibles que el paciente debería incorporar para corregir sus desvíos de macronutrientes."
    )

    prompt_3 = (
        f"Finalmente, detalla una lista numerada del 1 al 10 con alimentos o hábitos a reducir o evitar, "
        f"junto con una estrategia breve sobre consumo de agua y hábitos sostenibles."
    )

    prompt_auditor_base = (
        f"Actúa como un médico supervisor estricto y auditor de calidad. "
        f"Revisa el siguiente informe nutricional compuesto por tres secciones:\n\n"
        f"--- INFORME A EVALUAR ---\n{{informe_completo}}\n-------------------------\n\n"
        f"INSTRUCCIONES DE AUDITORÍA:\n"
        f"1. Verifica que el texto sea coherente, empático, sin contradicciones y estrictamente profesional.\n"
        f"2. Si el informe está perfecto y listo para entregar, responde únicamente comenzando con la palabra 'OK'.\n"
        f"3. Si encuentras errores lógicos, datos cruzados o incoherencias, responde comenzando con la palabra 'RECHAZADO' seguido del motivo."
    )

    max_intentos = 10
    for intento_actual in range(1, max_intentos + 1):
        try:
            logger.info(f"Generando informe mensual auditado para usuario {user_id} (Intento {intento_actual}/{max_intentos})")

            # Paso 1: Bloque General (Usa GROQ_TEXTO por defecto)
            texto_p1 = await asyncio.to_thread(ejecutar_consulta_ia, prompt=prompt_1, max_tokens=600, temperature=0.3)
            await asyncio.sleep(60)

            # Paso 2: Alimentos a incorporar
            texto_p2 = await asyncio.to_thread(ejecutar_consulta_ia, prompt=prompt_2, max_tokens=600, temperature=0.3)
            await asyncio.sleep(60)

            # Paso 3: Alimentos a evitar y hábitos
            texto_p3 = await asyncio.to_thread(ejecutar_consulta_ia, prompt=prompt_3, max_tokens=600, temperature=0.3)
            await asyncio.sleep(60)

            # Unimos las partes en formato HTML limpio para el PDF
            informe_candidato = (
                f"<b>1. DIAGNÓSTICO NUTRICIONAL GLOBAL</b><br/>{texto_p1}<br/><br/>"
                f"<b>2. ALIMENTOS A INCORPORAR</b><br/>{texto_p2}<br/><br/>"
                f"<b>3. ALIMENTOS A REDUCIR Y HÁBITOS</b><br/>{texto_p3}"
            )

            # Paso 4: Instancia del Modelo Revisor (Usa GROQ_REVISION explícitamente)
            prompt_auditor_final = prompt_auditor_base.format(informe_completo=informe_candidato)
            modelo_rev = globals().get('GROQ_REVISION', 'openai/gpt-oss-20b')
            
            veredicto = await asyncio.to_thread(
                ejecutar_consulta_ia, 
                prompt=prompt_auditor_final, 
                max_tokens=200, 
                temperature=0.1, 
                modelo_override=modelo_rev
            )

            if veredicto and veredicto.strip().upper().startswith("OK"):
                logger.info(f"¡Informe mensual aprobado por el modelo revisor en el intento {intento_actual} para el usuario {user_id}!")
                return informe_candidato
            else:
                motivo_rechazo = veredicto.strip() if veredicto else "Respuesta vacía del revisor"
                logger.warning(f"Revisor rechazó el informe en el intento {intento_actual}. Motivo: {motivo_rechazo}")

        except Exception as e:
            logger.error(f"Error en intento {intento_actual} para usuario {user_id}: {e}")

        if intento_actual < max_intentos:
            await asyncio.sleep(60)

    # Puerta de salida si se agotan los 10 intentos -> Notificamos al médico tratante
    logger.error(f"Se agotaron los {max_intentos} intentos para generar el informe mensual del usuario {user_id}. Notificando al médico.")
    
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        sheet_usuarios = sh.worksheet("Usuarios")
        registros_usuarios = sheet_usuarios.get_all_records()
        
        medico_id = None
        for u in registros_usuarios:
            if str(u.get("User ID", "")).strip() == str(user_id):
                medico_id = u.get("Medico ID") or u.get("Médico ID") or u.get("Medico_ID")
                break

        if medico_id:
            mensaje_medico = (
                f"⚠️ **Alerta de Sistema / Error Técnico**\n"
                f"Estimado profesional, el paciente con ID `{user_id}` no pudo recibir su informe nutricional quincenal automático correspondiente al período `{mes_str}` debido a un inconveniente técnico persistente en los servidores de IA tras 10 reintentos.\n\n"
                f"🛠️ **Acción sugerida:** Utilice el comando exclusivo para reenviar el informe cuando el servicio se normalice."
            )
            await context.bot.send_message(chat_id=int(medico_id), text=mensaje_medico, parse_mode="Markdown")
    except Exception as err_medico:
        logger.error(f"No se pudo notificar al médico del usuario {user_id}: {err_medico}")

    return None

def ejecutar_consulta_ia(prompt: str, max_tokens: int = 300, temperature: float = 0.4, system_prompt: str = None, modelo_override: str = None) -> str:
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

        # Selecciona el modelo pasado por argumento o el predeterminado de globals
        modelo = modelo_override or globals().get('GROQ_TEXTO', "llama-3.3-70b-versatile")
        
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
        
async def obtener_recomendacion_ia(resumen_texto: str, es_semanal: bool = False) -> str:
    """
    Adaptador de compatibilidad para llamadas antiguas que usaban 'obtener_recomendacion_ia'.
    Redirige la consulta a la nueva lógica centralizada o mantiene un comportamiento simple si se prefiere.
    """
    if es_semanal:
        prompt = (
            f"Actúa como un coach nutricional breve y conciso. "
            f"Analiza este resumen semanal:\n{resumen_texto}\n\n"
            f"Escribe un solo párrafo corto de análisis general y 3 recomendaciones breves en puntos."
        )
        max_t = 350
    else:
        # Para el mensual viejo, si aún se llama en alguna parte suelta
        prompt = (
            f"Actúa como un nutricionista clínico personal. "
            f"Analiza la siguiente información:\n{resumen_texto}"
        )
        max_t = 700

    system_msg = "Eres un nutricionista profesional y empático. Proporciona respuestas claras sin dejar oraciones inconclusas."
    
    # Llama a tu única función centralizada de IA
    res = ejecutar_consulta_ia(prompt, max_tokens=max_t, temperature=0.4, system_prompt=system_msg)
    
    if res:
        return res.replace("##", "").replace("###", "").strip()
        
    return "⚠️ No se pudo obtener el análisis nutricional en este momento."


# ---------------------------------------------------------------------------------------------------------------------------------------------
# 4. FUNCIONES DE LOGGING Y COMPONENTES DE INTERFAZ TELEGRAM
# ---------------------------------------------------------------------------------------------------------------------------------------------

async def _verificar_y_obtener_profesional(update: Update) -> str:
    """
    Función auxiliar para validar que quien ejecuta el comando sea un profesional registrado.
    Retorna el ID del profesional en formato string si es válido, o None en caso contrario.
    """
    prof_id = str(update.effective_user.id).strip()
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws_prof = sh.worksheet("Profesionales")
        recs_prof = ws_prof.get_all_records()
        for rp in recs_prof:
            id_p = str(rp.get("User ID", rp.get("user_id", ""))).split('.')[0].strip()
            if id_p == prof_id:
                return prof_id
    except Exception:
        pass
    return None
    
async def procesar_y_enviar_informe_mensual(context, user_id: int, mes_target: str, es_automatico_15: bool = False, forzar_envio: bool = False):
    """
    Función unificada para generar y enviar el informe periódico con IA:
    - Si es el envío automático del día 15: procesa estrictamente del día 1 al 14 (fecha -1 respecto al envío).
    - Si es una solicitud manual del profesional: procesa el mes seleccionado completo (si ya pasó) 
      o hasta ayer (fecha -1) si es el mes en curso, ya que el día actual no está completo.
    """
    try:
        peso_ok = await _validar_peso_mes_actual(context=context, user_id=user_id)
        if not peso_ok and not forzar_envio:
            return False

        df_datos = obtener_datos_usuario(user_id) if 'obtener_datos_usuario' in globals() else pd.DataFrame()
        if df_datos.empty or 'Fecha' not in df_datos.columns:
            await context.bot.send_message(chat_id=user_id, text="⚠️ No hay registros suficientes para generar el informe.")
            return False

        df_datos['Fecha_dt'] = pd.to_datetime(df_datos['Fecha'], errors='coerce').dt.tz_localize(None)
        
        ahora_arg = obtener_ahora_arg()[cite: 4]
        if hasattr(ahora_arg, 'tzinfo') and ahora_arg.tzinfo is not None:
            ahora_arg = ahora_arg.replace(tzinfo=None)
        
        hoy_ts = pd.Timestamp(ahora_arg).floor('D')[cite: 4]
        ayer_ts = hoy_ts - pd.Timedelta(days=1)
        mes_actual_str = hoy_ts.strftime("%Y-%m")

        # Determinación de rangos aplicando el criterio de fecha -1 para períodos en curso
        if es_automatico_15:
            inicio_periodo = pd.Timestamp(f"{mes_target}-01")
            # El día 15 se envía el informe, por lo que el último día cerrado es el 14 (ayer respecto al envío)
            fin_periodo = pd.Timestamp(f"{mes_target}-14")
            etiqueta_periodo = f"Quincenal ({mes_target}: 1 al 14)"
            df_filtrado = df_datos[(df_datos['Fecha_dt'] >= inicio_periodo) & (df_datos['Fecha_dt'] <= fin_periodo)].copy()
        else:
            inicio_periodo = pd.Timestamp(f"{mes_target}-01")
            if mes_target == mes_actual_str:
                # Si es el mes actual, filtramos hasta ayer (fecha -1) para evitar datos incompletos del día corriente
                fin_periodo = ayer_ts
                etiqueta_periodo = f"Mes Actual en curso ({mes_target}: hasta el {ayer_ts.strftime('%d/%m')})"
            else:
                # Si es un mes pasado, toma el último día calendario de ese mes
                fin_periodo = pd.Timestamp(inicio_periodo) + pd.offsets.MonthEnd(0)
                etiqueta_periodo = f"Mes Completo ({mes_target})"

            df_filtrado = df_datos[(df_datos['Fecha_dt'] >= inicio_periodo) & (df_datos['Fecha_dt'] <= fin_periodo)].copy()

        if df_filtrado.empty:
            await context.bot.send_message(chat_id=user_id, text=f"⚠️ No se encontraron registros cerrados para el período {etiqueta_periodo}.")
            return False

        perfil = obtener_perfil_usuario(user_id, mes_target=mes_target) if 'obtener_perfil_usuario' in globals() else {}
        m = calcular_metricas_mensuales(df_filtrado, perfil) if 'calcular_metricas_mensuales' in globals() else {}
        conteo_frecuencias = analizar_frecuencia_alimentos_mes(user_id, mes_target) if 'analizar_frecuencia_alimentos_mes' in globals() else {}

        informe_ia = await generar_informe_mensual_auditado(
            context, 
            user_id, 
            mes_target, 
            m, 
            conteo_frecuencias
        )

        if not informe_ia:
            informe_ia = "<b>⚠️ No se pudo generar el informe auditado mediante IA tras los reintentos.</b>"

        txt_mensual = (
            f"📊 **Informe Nutricional ({etiqueta_periodo}):**\n"
            f"⚖️ *Peso registrado: `{m.get('peso_actual', 0)} kg`*\n\n"
            f"• Calorías Promedio: `{m.get('prom_cal', 0)} kcal` (Meta: `{m.get('ideal_cal', 0)} kcal`)\n"
            f"• Días Registrados: `{m.get('dias_registrados', 0)}`\n\n"
            f"🤖 **Análisis Nutricional Profundo:**\n"
            f"{informe_ia}"
        )

        await context.bot.send_message(chat_id=int(user_id), text=txt_mensual, parse_mode="HTML")
        logger.info(f"Informe periódico ({etiqueta_periodo}) enviado exitosamente a {user_id}")
        return True

    except Exception as e:
        logger.error(f"Error en procesar_y_enviar_informe_mensual para {user_id}: {e}")
        return False
                
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

#                                          VALIDACIÓN CENTRALIZADA DE PESO
# =============================================================================================================================================

async def _validar_peso_mes_actual(update: Update = None, context: ContextTypes.DEFAULT_TYPE = None, user_id: int = None) -> bool:
    """
    Verifica si el usuario registró su peso en el mes en curso.
    - Si NO lo registró: envía un aviso genérico y retorna False.
    - Si LO registró: retorna True.
    Acepta invocaciones por Update (comandos/botón) o por user_id directo (Jobs automáticos).
    """
    uid = user_id or (update.effective_user.id if update else None)
    if not uid:
        return False

    try:
        ultimo_registro = obtener_ultimo_peso(uid) if 'obtener_ultimo_peso' in globals() else None
    except Exception as e:
        if 'log_error' in globals():
            await log_error("validar_peso_mes_actual", e, user_id=uid)
        ultimo_registro = None

    peso_valido = False

    if ultimo_registro:
        fecha_val = (
            ultimo_registro.get("fecha") or 
            ultimo_registro.get("Ultimo Mes Peso") or 
            ultimo_registro.get("MES") or 
            ""
        )
        fecha_str = str(fecha_val).strip()

        if fecha_str:
            ahora = obtener_ahora_arg() if 'obtener_ahora_arg' in globals() else datetime.now()
            
            formatos = [
                "%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y",
                "%Y-%m", "%m/%Y", "%Y-%m-%d %H:%M:%S",
                "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M"
            ]

            fecha_dt = None
            for fmt in formatos:
                try:
                    fecha_dt = datetime.strptime(fecha_str, fmt)
                    break
                except ValueError:
                    continue

            if fecha_dt:
                if fecha_dt.year == ahora.year and fecha_dt.month == ahora.month:
                    peso_valido = True
            else:
                mes_str_iso = ahora.strftime("%Y-%m")
                mes_str_lat = ahora.strftime("%m/%Y")
                if mes_str_iso in fecha_str or mes_str_lat in fecha_str:
                    peso_valido = True

    if not peso_valido:
        msg_generico = (
            "⚠️ **Actualización de peso requerida:**\n\n"
            "Para procesar tu solicitud y generar los informes (semanales y mensuales), "
            "es necesario que cargues tu peso correspondiente al mes en curso.\n\n"
            "Por favor, actualizalo desde el menú `/perfil` (Opción PESO)."
        )

        if update and update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(msg_generico, parse_mode="Markdown")
        elif update and update.message:
            await update.message.reply_text(msg_generico, parse_mode="Markdown")
        elif context and uid:
            await context.bot.send_message(chat_id=uid, text=msg_generico, parse_mode="Markdown")

        return False

    return True
    
# =====================================================================================================================================
#                FINAL                        FUNCIONES AUXILIARES Y FORMATO                                      FINAL
# ======================================================================================================================================

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
#                 INICIO                            COMANDO SEMANA                                  INICIO   DB OK
# ======================================================================================================================================

@requiere_registro
async def cmd_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Manejador del comando /mensaje (semanal).
    Analiza los días transcurridos de la semana actual (o semana anterior si es lunes) en castellano,
    agregando promedio de presión arterial, minutos totales de actividad y calorías de ejercicio.
    """
    # 1. Validación centralizada desde Auxiliares
    if not await _validar_peso_mes_actual(update=update, context=context):
        return

    try:
        user_id = update.effective_user.id
        msg_espera = await update.message.reply_text("⏳ Procesando resumen nutricional...")

        df_datos = obtener_datos_usuario(user_id) if 'obtener_datos_usuario' in globals() else pd.DataFrame()

        if df_datos.empty or 'Fecha' not in df_datos.columns:
            await msg_espera.edit_text("⚠️ No hay información de comidas registradas.")
            return

        df_datos['Fecha_dt'] = pd.to_datetime(df_datos['Fecha'])
        ahora = pd.Timestamp.now()
        dia_semana = ahora.weekday()  # 0: Lunes, 1: Martes...

        dias_espanol = {
            0: "Lunes", 1: "Martes", 2: "Miércoles", 
            3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"
        }

        # Lunes: toma la semana anterior completa (7 días)
        if dia_semana == 0:
            inicio_rango = ahora.floor('D') - pd.Timedelta(days=7)
            fin_rango = ahora.floor('D') - pd.Timedelta(seconds=1)
            etiqueta_periodo = "Semana Anterior (Lunes a Domingo)"
        else:
            # Martes en adelante: Desde el lunes hasta el día anterior a las 23:59:59
            inicio_rango = ahora.floor('D') - pd.Timedelta(days=dia_semana)
            fin_rango = ahora.floor('D') - pd.Timedelta(seconds=1)
            nombre_dia_actual = dias_espanol.get(dia_semana, "")
            etiqueta_periodo = f"Semana Actual (Lunes a {nombre_dia_actual})"

        df_semana = df_datos[(df_datos['Fecha_dt'] >= inicio_rango) & (df_datos['Fecha_dt'] <= fin_rango)].copy()

        if df_semana.empty:
            await msg_espera.edit_text("⚠️ No hay registros acumulados para los días transcurridos de esta semana.")
            return

        mes_target = inicio_rango.strftime("%Y-%m")
        perfil = obtener_perfil_usuario(user_id, mes_target=mes_target) if 'obtener_perfil_usuario' in globals() else {}
        m = calcular_metricas_mensuales(df_semana, perfil) if 'calcular_metricas_mensuales' in globals() else {}

        # --- CÁLCULO DE MINUTOS DE ACTIVIDAD Y CALORÍAS GASTADAS ---
        minutos_totales_actividad = 0
        if 'Momento' in df_semana.columns and 'Alimento' in df_semana.columns:
            for _, row in df_semana.iterrows():
                momento_str = str(row.get('Momento', '')).strip().lower()
                alimento_str = str(row.get('Alimento', '')).strip()
                # Detectar filas de actividad (donde Caloria < 0 o Momento/Actividad indica ejercicio)
                cal_val = float(row.get('Calorias', 0) or 0)
                if cal_val < 0 or 'actividad' in momento_str or 'ejercicio' in momento_str or 'caminata' in momento_str:
                    # Extraer el número inicial de minutos (ej: "45 caminata...")
                    match = re.match(r'^(\d+)', alimento_str)
                    if match:
                        minutos_totales_actividad += int(match.group(1))

        # --- CÁLCULO DE PROMEDIO DE PRESIÓN ARTERIAL EN EL RANGO ---
        prom_alta, prom_baja = None, None
        try:
            df_presion = obtener_datos_presion_db(user_id) if 'obtener_datos_presion_db' in globals() else pd.DataFrame()
            if not df_presion.empty and 'Fecha_Dia' in df_presion.columns:
                df_presion['Fecha_Dia_dt'] = pd.to_datetime(df_presion['Fecha_Dia'], errors='coerce')
                df_presion_semana = df_presion[
                    (df_presion['Fecha_Dia_dt'] >= inicio_rango) & 
                    (df_presion['Fecha_Dia_dt'] <= fin_rango)
                ]
                if not df_presion_semana.empty:
                    prom_alta = round(df_presion_semana['Alta'].mean())
                    prom_baja = round(df_presion_semana['Baja'].mean())
        except Exception as e_presion:
            logger.error(f"Error al calcular presión semanal: {e_presion}")

        # Construcción del texto de salida enriquecido
        txt = (
            f"📅 **Resumen Nutricional Semanal:**\n"
            f"ℹ️ *{etiqueta_periodo}*\n\n"
            f"• **Promedio Calorías:** `{m.get('prom_cal', 0)} kcal` / Meta: `{m.get('ideal_cal', 0)} kcal`\n"
            f"• **Proteínas:** `{m.get('prom_prot', 0)} g` / Meta: `{m.get('ideal_prot', 0)} g`\n"
            f"• **Grasas:** `{m.get('prom_gras', 0)} g` / Meta: `{m.get('ideal_gras', 0)} g`\n"
            f"• **Carbohidratos:** `{m.get('prom_carb', 0)} g` / Meta: `{m.get('ideal_carb', 0)} g`\n"
            f"• **Fibras:** `{m.get('prom_fibr', 0)} g` / Meta: `{m.get('ideal_fibr', 0)} g`\n"
        )

        if prom_alta is not None and prom_baja is not None:
            txt += f"• **Presión Arterial Promedio:** `{prom_alta}/{prom_baja} mmHg`\n"

        txt += (
            f"• **Actividad Física:** `{minutos_totales_actividad} minutos` totales\n"
            f"• **Calorías Quemadas (Promedio):** `{m.get('prom_quem', 0)} kcal/día`\n"
            f"• **Días Evaluados:** `{m.get('dias_registrados', 0)}`"
        )

        await msg_espera.edit_text(txt, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en cmd_mensaje: {e}")
        if 'msg_espera' in locals():
            await msg_espera.edit_text(f"⚠️ Error al calcular resumen semanal: {e}")

# ======================================================================================================================================
#                      FINAL                        COMANDO SEMANA                                          FINAL
# ======================================================================================================================================

# =====================================================================================================================================
#                       INICIO                  COMANDO INGRESO (ALTA DE USUARIO)                               INICIO
# ======================================================================================================================================

def cmd_nueva_cuenta(datos_usuario):
    """
    Crea la hoja de perfil, presión y comidas del usuario en Google Sheets,
    crea automáticamente las tablas correspondientes en Supabase si no existen,
    e inserta su registro en la hoja 'Usuarios' y en Supabase con estado inicial 0.
    """
    user_id = datos_usuario.get("user_id")
    nombre = datos_usuario.get("nombre")
    edad = int(datos_usuario.get("edad", 0))
    sexo = datos_usuario.get("sexo", "M")
    altura = float(datos_usuario.get("altura", 0))
    peso = float(datos_usuario.get("peso", 0))
    muneca = float(datos_usuario.get("muneca", 0))
    ocupacion = int(datos_usuario.get("ocupacion", 1375))
    peso_ideal = float(datos_usuario.get("peso_ideal", 0))
    cumple = datos_usuario.get("cumple", "")
    profesional = datos_usuario.get("profesional", "")

    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)

    # 1. Crear hoja Perfil_<user_id> y rellenar la primera fila de datos en Google Sheets
    nombre_hoja_perfil = f"Perfil_{user_id}"
    try:
        ws_perfil = sh.worksheet(nombre_hoja_perfil)
    except gspread.exceptions.WorksheetNotFound:
        ws_perfil = sh.add_worksheet(title=nombre_hoja_perfil, rows=100, cols=10)
        cabeceras_perfil = ["EDAD", "PESO", "ALTURA", "GENERO", "OCUPACION", "MES", "Fecha_Actualizacion", "Peso_ideal", "Cumple"]
        ws_perfil.append_row(cabeceras_perfil)

    mes_actual = datetime.now(ARG_TZ).strftime("%Y-%m")
    fecha_act = datetime.now(ARG_TZ).strftime("%Y-%m-%d %H:%M:%S")

    fila_perfil = [
        int(edad),
        int(round(peso * 1000)),
        int(round(altura * 1000)),
        str(sexo),
        int(ocupacion),
        str(mes_actual),
        str(fecha_act),
        int(round(peso_ideal * 1000)),
        str(cumple)
    ]
    ws_perfil.append_row(fila_perfil)

    # 2. Crear hojas adicionales si corresponde (Presión y Comidas) en Google Sheets
    try:
        sh.add_worksheet(title=f"Presion_{user_id}", rows=100, cols=10)
    except Exception:
        pass

    try:
        sh.add_worksheet(title=f"Comidas_{user_id}", rows=100, cols=10)
    except Exception:
        pass

    # 3. Agregar fila en la hoja 'Usuarios' con estado inicial 0 (activo)
    ws_usuarios = sh.worksheet("Usuarios")
    fecha_alta = datetime.now(ARG_TZ).strftime("%Y-%m-%d")
    
    nueva_fila_usuario = [
        str(user_id),
        str(nombre),
        0,  # Estado inicial 0 (activo según la nueva lógica de control de compromiso)
        str(mes_actual),
        "Si",
        str(fecha_alta),
        str(sexo),
        int(round(altura)),
        float(muneca),
        int(ocupacion),
        str(cumple),
        str(profesional)
    ]
    ws_usuarios.append_row(nueva_fila_usuario)

    # 4. Asegurar la creación de tablas en Supabase si no existen e insertar datos iniciales
    try:
        _asegurar_tabla_y_conectar(f"user_{user_id}", tipo_tabla="comida")
        _asegurar_tabla_y_conectar(f"comidas_{user_id}", tipo_tabla="comidas_precargadas")
        _asegurar_tabla_y_conectar(f"presion_{user_id}", tipo_tabla="presion")
        conn_p, cur_p = _asegurar_tabla_y_conectar(f"perfil_{user_id}", tipo_tabla="perfil")

        query_perfil = f"""
            INSERT INTO perfil_{user_id} ("EDAD", "PESO", "ALTURA", "GENERO", "OCUPACION", "MES", "Fecha_Actualizacion", "Peso_ideal", "Cumple")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        valores_perfil = (
            str(edad),
            float(peso),
            float(altura),
            str(sexo),
            float(ocupacion),
            str(mes_actual),
            str(fecha_act),
            float(peso_ideal),
            str(cumple)
        )
        cur_p.execute(query_perfil, valores_perfil)
        conn_p.commit()
        cur_p.close()
        conn_p.close()
    except Exception as e:
        logger.error(f"Error al crear tablas en Supabase para el nuevo usuario {user_id}: {e}")
                    
def _verificar_estado_usuario_en_hoja(user_id):
    """Verifica si el usuario existe en la hoja 'Usuarios' y devuelve su estado o None."""
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws_usuarios = sh.worksheet("Usuarios")
        records = ws_usuarios.get_all_records()
        for r in records:
            id_hoja = str(r.get("User ID", r.get("user_id", ""))).split('.')[0].strip()
            if id_hoja == str(user_id).strip():
                for k, v in r.items():
                    if str(k).strip().lower() in ['estado', 'status', 'activo', 'activa']:
                        return str(v).strip()
                return "Activo"
    except Exception as e:
        logger.error(f"Error al verificar estado de usuario: {e}")
    return None

def _verificar_profesional_valido(prof_id_str):
    """Verifica si el ID del profesional existe en la hoja 'Profesionales'."""
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws_prof = sh.worksheet("Profesionales")
        records = ws_prof.get_all_records()
        for r in records:
            id_hoja = str(r.get("User ID", r.get("user_id", ""))).split('.')[0].strip()
            if id_hoja == str(prof_id_str).strip():
                return True
    except Exception as e:
        logger.error(f"Error al verificar hoja Profesionales: {e}")
    return False

async def cmd_ingreso_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # --- VERIFICACIÓN DE USUARIO EXISTENTE Y ESTADO ---
    estado_usr = _verificar_estado_usuario_en_hoja(user_id)
    
    if estado_usr is not None:
        estado_lower = estado_usr.lower()
        if estado_lower in ['inactivo', 'bloqueado', 'no', 'false', '0']:
            await update.message.reply_text(
                "❌ **Su usuario ha sido deshabilitado, contáctese con el administrador del bot.**",
                parse_mode="Markdown"
            )
            return ConversationHandler.END
        else:
            perfil_existente = obtener_perfil_usuario(user_id) if 'obtener_perfil_usuario' in globals() else {}
            nombre_usr = perfil_existente.get('nombre', 'Usuario') if perfil_existente else 'Usuario'
            await update.message.reply_text(
                f"ℹ️ **¡Ya tenés una cuenta activa, {nombre_usr}!**\n\n"
                f"Tu ficha ya está registrada en el sistema con el ID `{user_id}`.\n"
                "Podés consultar o actualizar tu información en cualquier momento con el comando `/perfil`.",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

    # --- SI NO EXISTE, LO PRIMERO ES INGRESAR EL ID DEL PROFESIONAL ---
    await update.message.reply_text(
        "🔑 **Apertura de Ficha - Validación de Profesional**\n\n"
        "Para comenzar el registro, por favor ingresá el **ID de Telegram del profesional**:",
        parse_mode="Markdown"
    )
    return ING_PROFESIONAL

async def cmd_nuevo_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await cmd_ingreso_start(update, context)

async def ing_recibir_profesional(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prof_id = update.message.text.strip()
    
    loop = asyncio.get_running_loop()
    es_valido = await loop.run_in_executor(None, _verificar_profesional_valido, prof_id)
    
    if not es_valido:
        await update.message.reply_text(
            "⚠️ **ID de profesional no válido**\n\n"
            "El número ingresado no figura en la lista de profesionales autorizados. "
            "Por favor, verificá el ID con tu profesional e intentalo nuevamente o escribí `/cancelar`.",
            parse_mode="Markdown"
        )
        return ING_PROFESIONAL

    context.user_data['ing_profesional'] = prof_id
    await update.message.reply_text(
        "✅ **Profesional verificado correctamente.**\n\n"
        "📝 **Apertura de Ficha Nutricional**\n"
        "Por favor, indicá tu **Nombre y Apellido / Apodo**:",
        parse_mode="Markdown"
    )
    return ING_NOMBRE

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
        [InlineKeyboardButton("Sedentario / Ligero (1.375)", callback_data="ocup_1375")],
        [InlineKeyboardButton("Moderado (1.550)", callback_data="ocup_1550")],
        [InlineKeyboardButton("Intenso / Trabajo Físico (1.725)", callback_data="ocup_1725")]
    ])
    await update.message.reply_text("Seleccioná tu **nivel de actividad u ocupación habitual**:", reply_markup=keyboard, parse_mode="Markdown")
    return ING_OCUPACION

async def ing_recibir_ocupacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    val_str = query.data.replace("ocup_", "")
    try:
        ocupacion = int(val_str)
    except ValueError:
        ocupacion = 1375
        
    context.user_data['ing_ocupacion'] = ocupacion
    
    await query.edit_message_text(
        f"Nivel de actividad registrado: *{ocupacion}*.\n\n"
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
    datos_usuario = {
        "user_id": user_id,
        "nombre": context.user_data.get('ing_nombre'),
        "edad": context.user_data.get('ing_edad'),
        "sexo": context.user_data.get('ing_sexo'),
        "altura": context.user_data.get('ing_altura'),
        "peso": context.user_data.get('ing_peso'),
        "muneca": context.user_data.get('ing_muneca'),
        "ocupacion": context.user_data.get('ing_ocupacion'),
        "cumple": cumple_str,
        "profesional": context.user_data.get('ing_profesional')
    }
    
    # Cálculos antropométricos y metabólicos previos
    datos_usuario["contextura"] = calcular_contextura(datos_usuario["sexo"], datos_usuario["altura"], datos_usuario["muneca"])
    datos_usuario["peso_ideal"] = round(calcular_peso_ideal(datos_usuario["sexo"], datos_usuario["altura"]), 1)
    datos_usuario["peso_etapa"] = calcular_peso_etapa(datos_usuario["peso"], datos_usuario["peso_ideal"])
    
    genero_str = "femenino" if str(datos_usuario["sexo"]).upper() in ["F", "FEMENINO", "MUJER"] else "masculino"
    tmb, get_calorias = calcular_tmb_y_get(
        peso_actual=datos_usuario["peso"], 
        altura_cm=datos_usuario["altura"], 
        edad=datos_usuario["edad"], 
        genero=genero_str, 
        actividad=datos_usuario["ocupacion"], 
        peso_ideal=datos_usuario["peso_ideal"]
    )
    datos_usuario["tmb"] = tmb
    datos_usuario["get"] = get_calorias
    
    msg_espera = await update.message.reply_text(
        "✅ **¡Datos procesados!**\n\n"
        "⏳ *Creando planillas en Google Sheets y redactando tu informe clínico inicial con IA...*",
        parse_mode="Markdown"
    )

    try:
        loop = asyncio.get_running_loop()
        # 1. Guardar la cuenta en la hoja de cálculo
        await loop.run_in_executor(None, cmd_nueva_cuenta, datos_usuario)

        # 2. Generar informe con IA y compilar PDF
        _, pdf_buf = await procesar_informe_inicial_ia(datos_usuario)

        # 3. Enviar resumen por chat y adjuntar el documento
        resumen = (
            "🎉 **¡Tu cuenta y planillas están listas!**\n\n"
            f"👤 **Paciente:** {datos_usuario['nombre']} | **ID:** `{user_id}`\n"
            f"⚖️ **Peso Actual:** `{datos_usuario['peso']} kg` ➔ **Objetivo Etapa 1:** `{datos_usuario['peso_etapa']} kg`\n"
            f"🔥 **TMB:** `{round(tmb)} kcal` | **GET:** `{round(get_calorias)} kcal`\n\n"
            "📄 *Te hemos enviado tu informe nutricional inicial detallado en formato PDF.*"
        )
        await msg_espera.edit_text(resumen, parse_mode="Markdown")

        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buf,
            filename=f"Informe_Inicial_{datos_usuario['nombre'].replace(' ', '_')}.pdf"
        )

    except Exception as e:
        logger.error(f"Error al inicializar cuenta o generar informe para {user_id}: {e}")
        await msg_espera.edit_text(f"❌ Ocurrió un error al procesar el ingreso: {e}")

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
        ING_PROFESIONAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ing_recibir_profesional)],
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
#                FINAL                        COMANDO INGRESO (ALTA DE USUARIO)               FINAL
# ======================================================================================================================================

#========================================================================================================================================
#                     INICIO                         COMANDO START                          INICIO  2026 09 05
# =========================================================================================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 **¡Bienvenido a tu Bot Nutricional Personalizado!**\n\n"
        "Guía rápida de comandos e ingestas disponibles:\n\n"
        "📌 **Comandos Principales:**\n"
        "• `/inicio`: Resumen de los comando y PDF del manual.\n"
        "• `/nuevo`: Apertura de cuenta ingresando los datos.\n"
        "• `/presi`: Registro y consulta de presión arterial.\n"
        "  `  /presi 120,80,70,nota` (Completo)\n"
        "  `  /presi 120,80,70` (Sin nota)\n"
        "  `  /presi 120,80` (Solo presión)\n"
        "  `  /presi AAAA-MM` Promedio mensual y PDF.\n"
        "• `/diario`: Ingestas del día detalle nutricional y PDF.\n"
        "• `/semanal`: Estadística semanal (calorías, proteínas, etc).\n"
        "• `/mensual`: Reporte mensual con estimación de peso, macronutrientes y descarga reporte PDF.\n"
        "• `/perfil`: Consulta de datos biométricos.\n"
        "• `/peso`: `/peso 90` Actualiza el peso del mes.\n"
        "• `/eliminar`: Borra ingestas o actividades seleccionando el dia.\n"
        "• `/comidas`: Listado de comidas predetecargadas y PDF.\n"
        "• `/receta`: Calculadora Web para registrar comidas.\n\n"
        "📌 **Métodos de Registro:**\n"
        "• **Con IA:** Texto libre, Notas de voz 🎤 o Fotos de platos 📸.\n"
        "• **Modificación parcial:** Editar por item manteniendo peso (`DESCRIPCION`) o recalculando (`DESCRIPCION,PESO`).\n"
        "• **Sin IA (Plantillas):** `*DESAYUNO,1`, `*PIZZA (porcion),4` o `*TORTA (fraccion x 100g),1.5` (multiplicadores por porción/unidad).\n"
        "• **Actividad Física:** `# MINUTOS DESCRIPCION, CALORIAS` (Ej: `# 45 min caminata, 250 cal`).\n\n"
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
            Paragraph("Presenta la guía rápida con opción de descargar este manual en formato PDF.", body_style)
        ],
        [
            Paragraph("<b>/ingreso</b><br/>/nuevo<br/>/alta<br/>/registrar<br/>/nuevo_usuario", code_style), 
            Paragraph("<b>Comando de Inicio de Registro:</b> Permite iniciar el proceso de apertura de cuenta y creación de ficha nutricional paso a paso.", body_style)
        ],
        [
            Paragraph("<b>ID de Profesional</b>", code_style), 
            Paragraph("<b>Validación del Profesional:</b> Ingresar el ID de Telegram del profesional autorizado para asociar y validar la cuenta.", body_style)
        ],
        [
            Paragraph("<b>Nombre y Apellido</b>", code_style), 
            Paragraph("<b>Identificación:</b> Ingresar el nombre completo o apodo con el que figurará el paciente en el sistema (mínimo 2 caracteres).", body_style)
        ],
        [
            Paragraph("<b>Edad</b>", code_style), 
            Paragraph("<b>Edad en años:</b> Ingresar un valor numérico válido entre 10 y 110 años.", body_style)
        ],
        [
            Paragraph("<b>Sexo Biológico</b>", code_style), 
            Paragraph("<b>Selección por Botón:</b> Elegir entre Masculino (👨) o Femenino (👩) mediante el teclado interactivo para los cálculos antropométricos.", body_style)
        ],
        [
            Paragraph("<b>Altura</b>", code_style), 
            Paragraph("<b>Estatura en centímetros:</b> Ingresar la altura en cm (ejemplo: <code>175</code> para 1,75 m, con un rango válido de 100 a 230 cm).", body_style)
        ],
        [
            Paragraph("<b>Peso Actual</b>", code_style), 
            Paragraph("<b>Peso en kilogramos:</b> Ingresar el peso actual (ejemplo: <code>82.5</code> kg, con un rango válido de 30 a 300 kg).", body_style)
        ],
        [
            Paragraph("<b>Muñeca</b>", code_style), 
            Paragraph("<b>Perímetro de muñeca:</b> Ingresar la medida en cm (ejemplo: <code>16.5</code> cm) para calcular automáticamente la contextura ósea.", body_style)
        ],
        [
            Paragraph("<b>Ocupación / Actividad</b>", code_style), 
            Paragraph("<b>Nivel de Actividad:</b> Seleccionar mediante botones el nivel de actividad habitual. Esta selección no incluye la actividad física, la cual se registra en forma independiente en la planilla (Sedentario/Ligero, Moderado o Intenso).", body_style)
        ],
        [
            Paragraph("<b>Fecha de Nacimiento</b>", code_style), 
            Paragraph("<b>Cumpleaños:</b> Ingresar la fecha de nacimiento obligatoriamente en formato <code>AAAA-MM-DD</code> (ejemplo: <code>1985-04-12</code>).", body_style)
        ],
        [
            Paragraph("<b>/cancelar</b>", code_style), 
            Paragraph("<b>Cancelar Registro:</b> Permite abortar el proceso de alta en cualquier momento, limpiando los datos temporales almacenados.", body_style)
        ], # <--- ¡ACÁ FALTABA LA COMA QUE CAUSABA EL ERROR DE SINTAXIS!
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
            Paragraph("<b>/semana</b>", code_style), 
            Paragraph("Estadística de la semana mostrando el resumen de calorías, proteínas, actividad física y macronutrientes.<br/>"
                      "El corte se realiza de lunes a domingo. Los lunes muestra la semana cerrada; de martes a domingo muestra la semana en curso.", body_style)
        ],
        [
            Paragraph("<b>/mes</b>", code_style), 
            Paragraph("Selección del mes de consulta. Presenta reporte mensual, resumen calórico, estimación de cambio de peso, tabla de macronutrientes y descarga de informe diario completo.", body_style)
        ],
        [
            Paragraph("<b>/perfil</b>", code_style), 
            Paragraph("<code>/perfil</code> Muestra los datos biométricos corporales cargados en el sistema.", body_style)
        ],
        [
            Paragraph("<b>/peso</b>", code_style), 
            Paragraph("<code>/peso PESO</code> Actualiza el peso registrado para el mes en curso.", body_style)
        ],
        [
            Paragraph("<b>/receta</b>", code_style), 
            Paragraph("Acceso directo a la <i>Calculadora Nutricional Web</i> para cargar recetas complejas o combinaciones de alimentos en la planilla personal.", body_style)
        ],
        [
            Paragraph("<b>Atajos</b>", code_style), 
            Paragraph("<b>• /diario:</b> <code>/d</code><br/>"
                      "<b>• /semanal:</b> <code>/s</code><br/>"
                      "<b>• /mensual:</b> <code>/m</code>", body_style)
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
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT])
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
                  "• <code>*Descripción:</code> Descripción de la receta o detalle de los componentes de una ingesta guardada.<br/>"
                  "• <code>*Criterio:</code> Criterio a utilizar si la receta fue cargada en fracciones de 100g o porciones.<br/><br/>", body_style),
        Spacer(1, 4)
    ]))

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
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('BACKGROUND', (0,1), (-1,1), BG_CARD),
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
#               INICIO                           COMANDO RESUMEN                             INICIO DB OK
# ==============================================================================================================================================

@requiere_registro
async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Manejador del comando /resumen.
    Muestra el menú de selección de mes solo si el peso del mes en curso está al día.
    """
    if not await _validar_peso_mes_actual(update, context):
        return

    ahora = obtener_ahora_arg()
    mes_actual = ahora.strftime("%Y-%m")
    mes_anterior = (ahora.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Mes Actual", callback_data=f"resumen_mes_{mes_actual}")],
        [InlineKeyboardButton("📆 Mes Anterior", callback_data=f"resumen_mes_{mes_anterior}")],
        [InlineKeyboardButton("🗓️ Otro Mes", callback_data="resumen_mes_menu_otros")]
    ])

    await update.message.reply_text(
        "📊 **Resumen Mensual:** Seleccioná la opción que querés consultar:", 
        reply_markup=keyboard, 
        parse_mode="Markdown"
    )

# =============================================================================================================================================

async def mostrar_resumen_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        user_id = update.effective_user.id

        ahora = obtener_ahora_arg()
        mes_actual_str = ahora.strftime("%Y-%m")

        mes_str = None
        if query and query.data:
            await query.answer()
            cb_data = query.data

            if cb_data == "resumen_mes_menu_otros":
                botones_meses = []
                primer_dia_mes_actual = ahora.replace(day=1)
                for i in range(1, 7):
                    mes_iter = (primer_dia_mes_actual - pd.DateOffset(months=i)).strftime("%Y-%m")
                    botones_meses.append([InlineKeyboardButton(f"🗓️ Período {mes_iter}", callback_data=f"resumen_mes_{mes_iter}")])
                
                botones_meses.append([InlineKeyboardButton("🔙 Volver", callback_data="resumen_volver_menu")])
                
                await query.edit_message_text(
                    "🗓️ **Seleccioná el mes que querés consultar:**", 
                    reply_markup=InlineKeyboardMarkup(botones_meses),
                    parse_mode="Markdown"
                )
                return

            elif cb_data == "resumen_volver_menu":
                mes_anterior_str = (ahora.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📅 Mes Actual", callback_data=f"resumen_mes_{mes_actual_str}")],
                    [InlineKeyboardButton("📆 Mes Anterior", callback_data=f"resumen_mes_{mes_anterior_str}")],
                    [InlineKeyboardButton("🗓️ Otro Mes", callback_data="resumen_mes_menu_otros")]
                ])
                await query.edit_message_text(
                    "📊 **Resumen Mensual:** Seleccioná la opción que querés consultar:", 
                    reply_markup=keyboard, 
                    parse_mode="Markdown"
                )
                return

            elif cb_data.startswith("resumen_mes_"):
                mes_str = cb_data.replace("resumen_mes_", "")

        elif context.args:
            mes_str = context.args[0]

        if not mes_str:
            mes_str = mes_actual_str

        if mes_str == mes_actual_str:
            if not await _validar_peso_mes_actual(update, context):
                return

        df_datos = obtener_datos_usuario(user_id) if 'obtener_datos_usuario' in globals() else pd.DataFrame()
        
        if not df_datos.empty and 'Fecha' in df_datos.columns:
            df_datos['Fecha_dt'] = pd.to_datetime(df_datos['Fecha'])
            hoy_comienzo = pd.Timestamp.now().floor('D')
            
            if mes_str == mes_actual_str:
                df_mes = df_datos[
                    (df_datos['Fecha'].astype(str).str.startswith(mes_str)) & 
                    (df_datos['Fecha_dt'] < hoy_comienzo)
                ].copy()
            else:
                df_mes = df_datos[df_datos['Fecha'].astype(str).str.startswith(mes_str)].copy()
        else:
            df_mes = pd.DataFrame()

        if df_mes.empty:
            msg = f"⚠️ No hay registros cargados para el mes `{mes_str}`."
            if query:
                await query.edit_message_text(msg, parse_mode="Markdown")
            else:
                await update.message.reply_text(msg, parse_mode="Markdown")
            return

        perfil = obtener_perfil_usuario(user_id, mes_target=mes_str) or {}
        m = calcular_metricas_mensuales(df_mes, perfil)

        def _fmt(val, dec=0):
            try:
                num = float(val)
                return f"{num:.{dec}f}" if dec > 0 else f"{int(round(num))}"
            except (ValueError, TypeError):
                return "0"

        if mes_str == mes_actual_str:
            resumen_texto_base = (
                f"Peso actual: {_fmt(m.get('peso_actual', 0), 1)} kg (Meta: {_fmt(m.get('peso_referencia', 0), 1)} kg). "
                f"Calorías promedio: {_fmt(m.get('prom_cal', 0))} kcal (Meta: {_fmt(m.get('ideal_cal', 0))} kcal). "
                f"Proteínas: {_fmt(m.get('prom_prot', 0))} g. Grasas: {_fmt(m.get('prom_gras', 0))} g. Fibra: {_fmt(m.get('prom_fibr', 0))} g."
            )
            # Reutiliza la función centralizada que ya vive en ConsultasIA.py
            recomendacion_pantalla = await obtener_recomendacion_ia(resumen_texto_base, es_semanal=False)
        else:
            recomendacion_pantalla = (
                "📌 *Este reporte corresponde a un período mensual ya finalizado. "
                "Las métricas presentadas son el registro histórico consolidado del mes.*"
            )

        encabezado_txt = (
            f"📊 **Reporte Nutricional Mensual ({mes_str}):**\n"
            f"⚖️ *Peso registrado: `{_fmt(m.get('peso_actual', 0), 1)} kg`*\n\n"
            f"• Consumidas: `{_fmt(m.get('prom_cal', 0))} kcal` | Quemadas: `{_fmt(m.get('prom_quem', 0))} kcal`\n"
            f"• Balance Neto: `{_fmt(m.get('prom_bal_neto', 0))} kcal/día`\n"
            f"• Camb. Est. Peso: `{float(m.get('cambio_peso_kg', 0)):+.1f} kg` ({m.get('dias_registrados', 0)} días)\n\n"
            f"📈 **Promedios vs. Objetivos:**\n"
            f"• Calorías: `{_fmt(m.get('prom_cal', 0))}` / `{_fmt(m.get('ideal_cal', 0))} kcal`\n"
            f"• Proteínas: `{_fmt(m.get('prom_prot', 0))}` / `{_fmt(m.get('ideal_prot', 0))} g`\n"
            f"• Grasas: `{_fmt(m.get('prom_gras', 0))}` / `{_fmt(m.get('ideal_gras', 0))} g`\n"
            f"• Carbs: `{_fmt(m.get('prom_carb', 0))}` / `{_fmt(m.get('ideal_carb', 0))} g`\n"
            f"• Fibras: `{_fmt(m.get('prom_fibr', 0))}` / `{_fmt(m.get('ideal_fibr', 0))} g`\n\n"
            f"🤖 **Análisis Nutricional:**\n"
        )
        
        pie_txt = f"\n\n📄 Podés descargar el informe completo en PDF abajo:"

        espacio_disponible = 3900 - len(encabezado_txt) - len(pie_txt)
        if len(recomendacion_pantalla) > espacio_disponible:
            recomendacion_pantalla = recomendacion_pantalla[:espacio_disponible - 3] + "..."

        txt_final = f"{encabezado_txt}{recomendacion_pantalla}{pie_txt}"

        keyboard = [[InlineKeyboardButton("📄 Descargar PDF Resumen Mensual", callback_data=f"descargar_pdf_resumen_{mes_str}")]]
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

    peso_act_pdf = round(float(m.get('peso_actual', 0)), 1)
    peso_ref_pdf = round(float(m.get('peso_referencia', 0)), 1)

    story.append(Paragraph(f"• <b>PERFIL REGISTRADO EN EL MES ({mes_str}):</b> Peso Registrado: {peso_act_pdf} kg | Peso Objetivo (75/25): {peso_ref_pdf} kg | Altura: {m['altura']} cm", body_style))
    story.append(Paragraph(f"• <b>DÉFICIT CALÓRICO DIARIO PROMEDIO:</b> {m['deficit_diario_real']} kcal / día", body_style))
    story.append(Paragraph(f"• <b>CAMBIO ESTIMADO DE PESO EN EL MES:</b> {m['cambio_peso_kg']:+.1f} kg", body_style))

    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>Informe Nutricional Mensual:</b>", sub_style))

    if isinstance(recomendacion, str) and recomendacion.strip():
        rec_limpia = recomendacion.strip()
        rec_limpia = rec_limpia.replace('""', '"').replace('"', '')

        for bloque in rec_limpia.split('\n\n'):
            bloque_txt = bloque.strip()
            if bloque_txt:
                bloque_formateado = bloque_txt.replace('\n', '<br/>')
                
                if bloque_formateado.count('<b>') > bloque_formateado.count('</b>'):
                    bloque_formateado += '</b>'

                try:
                    story.append(Paragraph(bloque_formateado, rec_style))
                    story.append(Spacer(1, 2))
                except Exception:
                    texto_plano = re.sub('<[^<]+?>', '', bloque_formateado)
                    story.append(Paragraph(texto_plano, rec_style))
                    story.append(Spacer(1, 2))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ======================================================================================================================================

async def generar_y_enviar_pdf_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Generando PDF... ⏳")

    try:
        user_id = query.from_user.id
        cb_val = query.data
        for prefix in ["descargar_pdf_resumen_", "pdf_mes_"]:
            if cb_val.startswith(prefix):
                cb_val = cb_val.replace(prefix, "")
        mes_str = cb_val

        ahora = obtener_ahora_arg()
        mes_actual_str = ahora.strftime("%Y-%m")

        if mes_str == mes_actual_str:
            if not await _validar_peso_mes_actual(update, context):
                return

        df_datos = obtener_datos_usuario(user_id) if 'obtener_datos_usuario' in globals() else pd.DataFrame()
        
        if not df_datos.empty and 'Fecha' in df_datos.columns:
            df_datos['Fecha_dt'] = pd.to_datetime(df_datos['Fecha'])
            hoy_comienzo = pd.Timestamp.now().floor('D')
            
            if mes_str == mes_actual_str:
                df_mes = df_datos[
                    (df_datos['Fecha'].astype(str).str.startswith(mes_str)) & 
                    (df_datos['Fecha_dt'] < hoy_comienzo)
                ].copy()
            else:
                df_mes = df_datos[df_datos['Fecha'].astype(str).str.startswith(mes_str)].copy()
        else:
            df_mes = pd.DataFrame()

        if df_mes.empty:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"⚠️ No hay registros de días en el mes `{mes_str}` para generar el PDF.",
                parse_mode="Markdown"
            )
            return

        perfil = obtener_perfil_usuario_db(user_id, mes_target=mes_str) if 'obtener_perfil_usuario_db' in globals() else {}
        df_presion = pd.DataFrame()
        tmb_val = perfil.get('tmb', 0) if isinstance(perfil, dict) else 0

        if mes_str == mes_actual_str:
            m = calcular_metricas_mensuales(df_mes, perfil)
            conteo_frecuencias = analizar_frecuencia_alimentos_mes(user_id, mes_str) if 'analizar_frecuencia_alimentos_mes' in globals() else {}

            # Conectado directamente al nuevo motor auditado de 10 intentos en ConsultasIA.py
            recomendacion_pdf = await generar_informe_mensual_auditado(
                context, 
                user_id, 
                mes_str, 
                m, 
                conteo_frecuencias
            )
            
            if not recomendacion_pdf:
                recomendacion_pdf = "<b>⚠️ No se pudo generar el informe auditado mediante IA tras los reintentos.</b>"
        else:
            recomendacion_pdf = (
                "<b>INFORME HISTÓRICO CONSOLIDADO:</b><br/>"
                "Este reporte PDF corresponde a un período mensual finalizado. "
                "Los datos presentados reflejan el balance metabólico exacto y los promedios registrados durante dicho mes."
            )

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

        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=pdf_buffer,
            filename=f"Reporte_Nutricional_{mes_str}.pdf",
            caption=f"📄 Reporte mensual correspondiente a **{mes_str}**.",
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
    Envía un botón interactivo y enlace con el user_id apuntando directamente
    a la página principal (calculadora) para ingresar la comida precargada.
    """
    user_id = update.effective_user.id
    # URL apuntando a la raíz ya que ahora la calculadora es la única página
    web_app_url = f"https://telegram-bot-nutricion.onrender.com/?user_id={user_id}"
    
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
#                   INICIO                                    COMANDO DIARIO                                    INICIO  DB OK
# =====================================================================================================================================

@requiere_registro
async def cmd_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Manejador del comando /diario.
    Muestra el menú de selección de fecha solo si el peso del mes en curso está al día.
    """
    # Usá exactamente la misma signatura de llamada que en cmd_mensaje
    #if not await _validar_peso_mes_actual(update=update, context=context):
    #    return
    # Despliegue del menú si el peso está al día

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
#                   INICIO                               COMANDO PERFIL                                  INICIO  DB OK
# ======================================================================================================================================

@requiere_registro
async def cmd_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # 🔹 Limpieza dinámica: Soporta tanto /perfil como /peso de forma indistinta
    texto_mensaje = update.message.text.strip()
    raw_text = texto_mensaje
    for cmd in ['/perfil', '/peso']:
        if texto_mensaje.lower().startswith(cmd):
            raw_text = texto_mensaje[len(cmd):].strip()
            break

    ahora = obtener_ahora_arg()
    mes_actual = ahora.strftime("%Y-%m")

    # 🔹 GARANTIZAR FILA DEL MES: Asegura que la estructura del mes actual exista
    # antes de realizar cualquier lectura o escritura de peso/perfil.
    if '_garantizar_fila_mes_actual' in globals():
        _garantizar_fila_mes_actual(user_id, ahora)

    # CASO 1: Ingreso de peso (/perfil 82.5 o /peso 82.5)
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
            await update.message.reply_text("❌ Por favor, ingresá un número válido para el peso. Ejemplo: `/peso 82.5` o `/perfil 82.5`", parse_mode="Markdown")
            return
        except Exception as e:
            print(f"Error al procesar /perfil o /peso en Sheets: {e}")
            await update.message.reply_text(f"⚠️ Ocurrió un error al intentar guardar en la planilla: {e}", parse_mode="Markdown")
            return

    # CASO 2: Consulta (/perfil solo o /peso solo)
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
                f"`/peso 82.5` o `/perfil 82.5`"
            )
        else:
            txt = f"👤 **Perfil no registrado para este mes.** Podés cargar tu peso ejecutando:\n`/peso 82.5`"

        await update.message.reply_text(txt, parse_mode="Markdown")
    except Exception as e:
        print(f"Error al consultar perfil: {e}")
        await update.message.reply_text(f"⚠️ Ocurrió un error al leer tu perfil: {e}", parse_mode="Markdown")

# ======================================================================================================================================
#                       FINAL                                       COMANDOS PERFIL                                      FINAL
# ======================================================================================================================================

# ======================================================================================================================================
#                      INICIO                                   OPERACIONES COMIDAS                               INICIO  DB OK
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
#                INICIO                                   MANEJADORES HANDLE                                  INICIO DB OK
#=========================================================================================================================================

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

#==============================================================================================================================

@requiere_registro
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    context.user_data['last_menu_msg_id'] = query.message.message_id

    # 🆕 Interceptor exclusivo para los botones del menú de eliminación
    if data.startswith(("del_reg_", "del_mom_", "ejecutar_del_fila_")):
        await manejar_callback_eliminacion(query, user_id, data, context)
        return

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
#                FINAL                                 MANEJADORES HANDLE                       FINAL
#===================================================================================================================================

# ======================================================================================================================================
#                INICIO                               MENSAJES PROGRAMADOS                          INICIO  
# ======================================================================================================================================

async def recordatorio_lunes_presion(context):
    """
    Job programado para los lunes: verifica si el usuario registró al menos
    una medición de presión arterial en la última semana. Si no hay registros,
    envía un recordatorio amistoso sin ningún tipo de sanción o penalización.
    """
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws_usuarios = sh.worksheet("Usuarios")
        records = ws_usuarios.get_all_records()

        ahora = obtener_ahora_arg()
        hace_siete_dias = ahora - timedelta(days=7)

        for r in records:
            user_id_raw = r.get("User ID", r.get("user_id", ""))
            if not user_id_raw:
                continue
            
            user_id = str(user_id_raw).split('.')[0].strip()
            estado_val = str(r.get("Estado", r.get("estado", "Activo"))).strip().lower()
            
            # Si ya está dado de baja o suspendido (3), no enviar recordatorio de presión
            if estado_val in ['baja', 'suspendido', '3']:
                continue
            
            if estado_val not in ['activo', 'sí', 'si', 'true', '1'] and not estado_val.isdigit():
                continue

            df_presion = obtener_datos_presion_db(user_id) if 'obtener_datos_presion_db' in globals() else pd.DataFrame()
            
            tiene_medicion_reciente = False
            if not df_presion.empty and 'Fecha_Dia' in df_presion.columns:
                df_presion['Fecha_dt'] = pd.to_datetime(df_presion['Fecha_Dia'], errors='coerce')
                recientes = df_presion[df_presion['Fecha_dt'] >= pd.Timestamp(hace_siete_dias.date())]
                if not recientes.empty:
                    tiene_medicion_reciente = True

            if not tiene_medicion_reciente:
                mensaje = (
                    "🩺 **Recordatorio de Presión Arterial**\n\n"
                    "Hola. Notamos que todavía no registraste ninguna medición de presión arterial durante la semana pasada. "
                    "Te recordamos la importancia de mantener un control regular para tu seguimiento médico.\n\n"
                    "Podés registrarla cuando gustes usando el comando:\n"
                    "`/presi 120,80,70`\n\n"
                    "_Este es un aviso informativo y de acompañamiento, sin ninguna penalización._"
                )
                try:
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=mensaje,
                        parse_mode="Markdown"
                    )
                except Exception as ex_send:
                    logger.error(f"No se pudo enviar el recordatorio de presión al usuario {user_id}: {ex_send}")

    except Exception as e:
        logger.error(f"Error en la ejecución del recordatorio semanal de presión: {e}")


async def ejecutar_recordatorio_comidas(context, momento: str):
    """
    Verifica y envía alertas de comidas pendientes, evalúa el cumplimiento semanal de ingestas 
    (lunes y martes) aplicando el sistema de penalizaciones y suspensión, y emite informes periódicos.
    """
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        
        sheet_usuarios = sh.worksheet("Usuarios")
        registros_usuarios = sheet_usuarios.get_all_records()
        
    except Exception as e:
        logger.error(f"Error al acceder a la pestaña 'Usuarios': {e}")
        return

    ahora_dt = obtener_ahora_arg()
    hoy = ahora_dt.date() if hasattr(ahora_dt, "date") else ahora_dt
    ayer = hoy - timedelta(days=1)
    anteayer = hoy - timedelta(days=2)

    str_hoy = hoy.strftime("%Y-%m-%d")
    str_ayer = ayer.strftime("%Y-%m-%d")
    str_anteayer = anteayer.strftime("%Y-%m-%d")

    todas_comidas = ["Desayuno", "Almuerzo", "Merienda", "Cena"]
    
    es_lunes_manana = (hoy.weekday() == 0 and momento == 'manana')
    es_martes_manana = (hoy.weekday() == 1 and momento == 'manana')
    es_dia_15_tarde = (hoy.day in [15, 30] and momento == 'tarde')
    es_dia_15_manana = (hoy.day in [15, 30] and momento == 'manana')

    if es_lunes_manana:
        await recordatorio_lunes_presion(context)

    # Identificar la columna Estado y User ID para actualizaciones precisas
    col_estado_idx = None
    col_userid_idx = None
    header_row = sheet_usuarios.row_values(1)
    for idx_h, h_name in enumerate(header_row, start=1):
        h_lower = h_name.strip().lower()
        if h_lower in ['estado', 'status']:
            col_estado_idx = idx_h
        elif h_lower in ['user id', 'user_id']:
            col_userid_idx = idx_h

    for index, u in enumerate(registros_usuarios):
        try:
            estado_raw = str(u.get("Estado", u.get("estado", "0"))).strip().lower()
            notif = str(u.get("Notificaciones", "")).strip().lower()
            raw_user_id = u.get("User ID", u.get("user_id", ""))
            
            if not raw_user_id:
                continue
            
            try:
                user_id = int(str(raw_user_id).split('.')[0].strip())
            except ValueError:
                continue

            # Si ya está suspendido o dado de baja (estado '3', 'baja', 'suspendido'), no procesar más
            if estado_raw in ['baja', 'suspendido', '3']:
                continue

            if notif not in ["si", "sí"]:
                continue

            row_index = index + 2  # Fila en Google Sheets (considerando cabecera)

            # 1. LÓGICA DE LOS LUNES: Validar peso y evaluar la semana anterior (Lunes a Domingo)
            if es_lunes_manana:
                await _validar_peso_mes_actual(context=context, user_id=user_id)

                inicio_semana_pasada = hoy - timedelta(days=7)
                fin_semana_pasada = hoy - timedelta(days=1)

                nombre_hoja_usuario = f"User_{user_id}"
                try:
                    ws_u = sh.worksheet(nombre_hoja_usuario)
                    registros_u = ws_u.get_all_records()
                except Exception:
                    registros_u = []

                # Evaluar día por día la semana pasada
                dias_incompletos = []
                dias_validos_count = 0
                current_d = inicio_semana_pasada

                while current_d <= fin_semana_pasada:
                    str_d = current_d.strftime("%Y-%m-%d")
                    # Contar comidas principales registradas en este día
                    comidas_dia = sum(
                        1 for r in registros_u 
                        if str(r.get("Fecha", "")).strip() == str_d 
                        and str(r.get("Momento/Actividad") or r.get("Momento", "")).capitalize() in todas_comidas
                    )
                    
                    # Se requieren al menos 2 comidas principales para que el día cuente
                    if comidas_dia >= 2:
                        dias_validos_count += 1
                    else:
                        dias_incompletos.append(str_d)
                    
                    current_d += timedelta(days=1)

                # La semana es completa si los 7 días cumplieron con el mínimo de 2 comidas
                semana_completa = (dias_validos_count == 7)

                # Obtener valor numérico actual del estado
                try:
                    actual_puntos = int(estado_raw) if estado_raw.isdigit() else 0
                except ValueError:
                    actual_puntos = 0

                if not semana_completa:
                    actual_puntos += 1
                    if actual_puntos >= 3:
                        actual_puntos = 3
                        # Suspensión definitiva
                        try:
                            if col_estado_idx and col_userid_idx:
                                sheet_usuarios.update_cell(row_index, col_estado_idx, "3")
                        except Exception as e_upd:
                            logger.error(f-f"Error al actualizar estado de suspensión para {user_id}: {e_upd}")

                        await context.bot.send_message(
                            chat_id=user_id,
                            text="❌ **Su usuario ha sido dado de baja / suspendido** por acumular tres semanas consecutivas sin registro completo de ingestas. Ya no podrá registrar más comidas ni recibir resúmenes.",
                            parse_mode="Markdown"
                        )
                        continue  # Saltear procesamiento posterior para este usuario dado de baja
                    else:
                        # Actualizar puntos de penalización en la hoja
                        try:
                            if col_estado_idx:
                                sheet_usuarios.update_cell(row_index, col_estado_idx, str(actual_puntos))
                        except Exception as e_upd:
                            logger.error(f"Error al actualizar advertencias para {user_id}: {e_upd}")

                        dias_str = ", ".join(dias_incompletos) if dias_incompletos else "varios días"
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=(
                                f"⚠️ **Aviso de Ingesta Incompleta (Semana Pasada)**\n\n"
                                f"Notamos que la semana pasada no se completaron los registros mínimos de comidas ({dias_str}). "
                                f"Acumulás una advertencia (Estado actual: {actual_puntos}/3).\n"
                                f"Recordá que al llegar a 3 semanas consecutivas sin registrar, el usuario quedará suspendido."
                            ),
                            parse_mode="Markdown"
                        )
                else:
                    # Si completó la semana correctamente, podemos reiniciar el contador a 0 o dejarlo activo
                    if actual_puntos > 0:
                        actual_puntos = 0
                        try:
                            if col_estado_idx:
                                sheet_usuarios.update_cell(row_index, col_estado_idx, "0")
                        except Exception as e_upd:
                            logger.error(f"Error al restablecer estado para {user_id}: {e_upd}")

            # 2. LÓGICA DE LOS MARTES: Emitir resumen semanal o aviso de falta de registros
            if es_martes_manana:
                # Releer estado actualizado por si cambió el lunes
                current_estado_val = str(sheet_usuarios.cell(row_index, col_estado_idx).value if col_estado_idx else "0").strip().lower()
                if current_estado_val == '3':
                    continue

                peso_ok = await _validar_peso_mes_actual(context=context, user_id=user_id)
                
                # Verificamos si la semana anterior estuvo completa de comidas
                nombre_hoja_usuario = f"User_{user_id}"
                ws_u = sh.worksheet(nombre_hoja_usuario)
                registros_u = ws_u.get_all_records()

                inicio_semana_pasada = hoy - timedelta(days=7)
                fin_semana_pasada = hoy - timedelta(days=1)
                dias_validos_count = 0
                dias_faltantes_detalle = []

                curr = inicio_semana_pasada
                while curr <= fin_semana_pasada:
                    str_c = curr.strftime("%Y-%m-%d")
                    c_count = sum(
                        1 for r in registros_u 
                        if str(r.get("Fecha", "")).strip() == str_c 
                        and str(r.get("Momento/Actividad") or r.get("Momento", "")).capitalize() in todas_comidas
                    )
                    if c_count >= 2:
                        dias_validos_count += 1
                    else:
                        dias_faltantes_detalle.append(str_c)
                    curr += timedelta(days=1)

                semana_ok = (dias_validos_count == 7)

                if peso_ok and semana_ok:
                    # Si está todo OK, se emite el resumen semanal con IA
                    try:
                        df_datos = obtener_datos_usuario(user_id) if 'obtener_datos_usuario' in globals() else pd.DataFrame()
                        if not df_datos.empty and 'Fecha' in df_datos.columns:
                            df_datos['Fecha_dt'] = pd.to_datetime(df_datos['Fecha'], errors='coerce').dt.tz_localize(None)
                            
                            ahora_raw = obtener_ahora_arg()
                            if hasattr(ahora_raw, 'tzinfo') and ahora_raw.tzinfo is not None:
                                ahora_raw = ahora_raw.replace(tzinfo=None)
                            ahora_ts = pd.Timestamp(ahora_raw)

                            inicio_rango = ahora_ts.floor('D') - pd.Timedelta(days=7)
                            fin_rango = ahora_ts.floor('D') - pd.Timedelta(seconds=1)
                            etiqueta_periodo = "Semana Anterior (Lunes a Domingo)"

                            df_semana = df_datos[(df_datos['Fecha_dt'] >= inicio_rango) & (df_datos['Fecha_dt'] <= fin_rango)].copy()
                            
                            if not df_semana.empty:
                                mes_target = inicio_rango.strftime("%Y-%m")
                                perfil = obtener_perfil_usuario(user_id, mes_target=mes_target) if 'obtener_perfil_usuario' in globals() else {}
                                m = calcular_metricas_mensuales(df_semana, perfil) if 'calcular_metricas_mensuales' in globals() else {}

                                prompt_semana = (
                                    f"Actúa como un nutricionista clínico experto. Proporcioná una devolución amplia, precisa y detallada "
                                    f"sobre la evolución nutricional de la {etiqueta_periodo}:\n\n"
                                    f"DATOS REEVALUADOS:\n"
                                    f"- Días evaluados: {m.get('dias_registrados', 0)}\n"
                                    f"- Calorías consumidas: {m.get('prom_cal', 0)} kcal/día (Meta: {m.get('ideal_cal', 0)} kcal)\n"
                                    f"- Proteínas: {m.get('prom_prot', 0)} g/día (Meta: {m.get('ideal_prot', 0)} g)\n"
                                    f"- Grasas: {m.get('prom_gras', 0)} g/día (Meta: {m.get('ideal_gras', 0)} g)\n"
                                    f"- Carbohidratos: {m.get('prom_carb', 0)} g/día (Meta: {m.get('ideal_carb', 0)} g)\n"
                                    f"- Fibra: {m.get('prom_fibr', 0)} g/día (Meta: {m.get('ideal_fibr', 0)} g)\n\n"
                                    f"INSTRUCCIONES:\n"
                                    f"Analizá en profundidad los desvíos numéricos de cada macronutriente. "
                                    f"Si hubo exceso de grasas o déficit de proteínas, señalalo con claridad y recomendá alimentos "
                                    f"específicos accesibles para corregirlo durante los próximos días."
                                )

                                recomendacion = await asyncio.to_thread(obtener_recomendacion_ia, prompt_semana)

                                txt = (
                                    f"📅 **Informe Nutricional Semanal con IA:**\n"
                                    f"ℹ️ *{etiqueta_periodo}*\n\n"
                                    f"• **Promedio Calorías:** `{m.get('prom_cal', 0)} kcal` / Meta: `{m.get('ideal_cal', 0)} kcal`\n"
                                    f"• **Proteínas:** `{m.get('prom_prot', 0)} g` / Meta: `{m.get('ideal_prot', 0)} g`\n"
                                    f"• **Grasas:** `{m.get('prom_gras', 0)} g` / Meta: `{m.get('ideal_gras', 0)} g`\n"
                                    f"• **Carbohidratos:** `{m.get('prom_carb', 0)} g` / Meta: `{m.get('ideal_carb', 0)} g`\n"
                                    f"• **Fibras:** `{m.get('prom_fibr', 0)} g` / Meta: `{m.get('ideal_fibr', 0)} g`\n"
                                    f"• **Días Evaluados:** `{m.get('dias_registrados', 0)}`\n\n"
                                    f"🤖 **Evaluación y Recomendaciones del Especialista:**\n"
                                    f"{recomendacion}"
                                )

                                await context.bot.send_message(chat_id=int(user_id), text=txt, parse_mode="Markdown")
                                logger.info(f"Resumen semanal con IA enviado exitosamente a {user_id}")

                                if index < len(registros_usuarios) - 1:
                                    await asyncio.sleep(60)

                    except Exception as e_ia:
                        logger.error(f"Error generando resumen semanal con IA para {user_id}: {e_ia}")
                else:
                    # Aviso de que no se puede emitir el resumen por falta de registros o peso
                    faltas_str = ", ".join(dias_faltantes_detalle) if dias_faltantes_detalle else "días de la semana pasada"
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=(
                            f"⚠️ **No se pudo emitir el resumen semanal**\n\n"
                            f"Motivo: Faltó registrar las ingestas correspondientes o el peso mensual obligatorio. "
                            f"Se detectaron registros insuficientes en los siguientes días: `{faltas_str}`.\n"
                            f"Ingresá tus comidas pendientes para retomar la normalidad en los próximos reportes."
                        ),
                        parse_mode="Markdown"
                    )

            # 3. Envío automático del resumen/informe mensual con IA (Días 15 y 30 a la tarde)
            if es_dia_15_tarde:
                peso_ok = await _validar_peso_mes_actual(context=context, user_id=user_id)
                if peso_ok:
                    try:
                        mes_actual_str = hoy.strftime("%Y-%m")
                        df_datos = obtener_datos_usuario(user_id) if 'obtener_datos_usuario' in globals() else pd.DataFrame()
                        
                        if not df_datos.empty and 'Fecha' in df_datos.columns:
                            df_datos['Fecha_dt'] = pd.to_datetime(df_datos['Fecha'])
                            df_mes = df_datos[df_datos['Fecha'].astype(str).str.startswith(mes_actual_str)].copy()
                            
                            if not df_mes.empty:
                                perfil = obtener_perfil_usuario(user_id, mes_target=mes_actual_str) if 'obtener_perfil_usuario' in globals() else {}
                                m = calcular_metricas_mensuales(df_mes, perfil) if 'calcular_metricas_mensuales' in globals() else {}
                                conteo_frecuencias = analizar_frecuencia_alimentos_mes(user_id, mes_actual_str) if 'analizar_frecuencia_alimentos_mes' in globals() else {}

                                informe_ia = await generar_informe_mensual_auditado(
                                    context, 
                                    user_id, 
                                    mes_actual_str, 
                                    m, 
                                    conteo_frecuencias
                                )

                                if not informe_ia:
                                    informe_ia = "<b>⚠️ No se pudo generar el informe auditado mediante IA tras los reintentos.</b>"

                                txt_mensual = (
                                    f"📊 **Informe Periódico Automático ({mes_actual_str}):**\n"
                                    f"⚖️ *Peso registrado: `{m.get('peso_actual', 0)} kg`*\n\n"
                                    f"• Calorías Promedio: `{m.get('prom_cal', 0)} kcal` (Meta: `{m.get('ideal_cal', 0)} kcal`)\n"
                                    f"• Días Registrados: `{m.get('dias_registrados', 0)}`\n\n"
                                    f"🤖 **Análisis Nutricional Profundo:**\n"
                                    f"{informe_ia}"
                                )

                                await context.bot.send_message(chat_id=int(user_id), text=txt_mensual, parse_mode="HTML")
                                logger.info(f"Informe periódico enviado exitosamente a {user_id}")

                                if index < len(registros_usuarios) - 1:
                                    await asyncio.sleep(60)

                    except Exception as e_mensual:
                        logger.error(f"Error generando informe periódico para {user_id}: {e_mensual}")

            # 4. Recordatorio habitual de comidas pendientes (mañana y tarde)
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

            if faltantes:
                lista_formateada = "\n• " + "\n• ".join(faltantes)
                mensaje_recordatorio = (
                    f"📌 **Recordatorio de comidas pendientes:**\n"
                    f"{lista_formateada}\n\n"
                    f"Si ya las consumiste, podés registrarlas en cualquier momento."
                )
                await context.bot.send_message(
                    chat_id=int(user_id), 
                    text=mensaje_recordatorio, 
                    parse_mode="Markdown"
                )
                logger.info(f"Recordatorio de comidas ({momento}) enviado a {user_id}")

        except Exception as e:
            logger.error(f"Error procesando usuario {user_id}: {e}")
            if 'registrar_log_en_sheet' in globals():
                await registrar_log_en_sheet(sh, f"Procesando User {user_id}", e)

# =============================================================================================================================================
#                    FINAL                                    MENSAJES PROGRAMADOS                                        FINAL
# =============================================================================================================================================


# =====================================================================================================================================
#                INICIO                               COMANDO ELIMINAR                          INICIO  
# ======================================================================================================================================

async def actualizar_menu_filtro_eliminacion(query, context):
    f = context.user_data.get('del_filtro_fecha')
    m = context.user_data.get('del_filtro_momento')
    keyboard = [
        [InlineKeyboardButton("📅 Hoy", callback_data="del_reg_hoy"), InlineKeyboardButton("📅 Ayer", callback_data="del_reg_ayer"), InlineKeyboardButton("📅 Otro Día", callback_data="del_reg_otro")],
        [InlineKeyboardButton("☕ Desayuno", callback_data="del_mom_Desayuno"), InlineKeyboardButton("🍽️ Almuerzo", callback_data="del_mom_Almuerzo")],
        [InlineKeyboardButton("🫖 Merienda", callback_data="del_mom_Merienda"), InlineKeyboardButton("🌙 Cena", callback_data="del_mom_Cena")],
        [InlineKeyboardButton("🔍 Ver Registros", callback_data="del_reg_mostrar")]
    ]
    await query.edit_message_text(
        "🗑️ **Eliminar o Corregir Registro Pasado**\n\n"
        f"• Fecha seleccionada: `{f}`\n"
        f"• Momento seleccionado: `{m}`\n\n"
        "Usá los botones para cambiar los filtros o tocá *Ver Registros*:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
async def mostrar_registros_para_eliminar(query, user_id, context):
    fecha = context.user_data.get('del_filtro_fecha')
    momento = context.user_data.get('del_filtro_momento')
    
    # Lectura directa desde Google Sheets
    df = obtener_datos_usuario(user_id)
    
    if df.empty:
        await query.edit_message_text("❌ No tenés registros cargados en tu planilla.")
        return

    # Filtramos por Fecha y Momento exacto
    df_filtrado = df[(df['Fecha'] == fecha) & (df['Momento'].str.strip().str.lower() == momento.lower())]

    if df_filtrado.empty:
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="del_reg_volver")]]
        await query.edit_message_text(
            f"⚠️ No se encontraron registros para el **{fecha}** en **{momento}**.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    txt = f"🗑️ **Registros encontrados ({fecha} - {momento}):**\n\n"
    keyboard_buttons = []

    for idx, row in df_filtrado.iterrows():
        alimento = row.get('Alimento', 'Sin detalle')
        calorias = row.get('Calorias', 0)
        txt += f"• **{alimento}** ({calorias:.0f} kcal)\n"
        
        # El índice real en la hoja de Google Sheets (fila 1 = encabezados, filas de datos empiezan en 2)
        keyboard_buttons.append([
            InlineKeyboardButton(f"❌ Borrar: {str(alimento)[:20]}...", callback_data=f"ejecutar_del_fila_{idx+2}")
        ])

    keyboard_buttons.append([InlineKeyboardButton("🔙 Volver", callback_data="del_reg_volver")])
    
    await query.edit_message_text(
        txt, 
        reply_markup=InlineKeyboardMarkup(keyboard_buttons), 
        parse_mode="Markdown"
    )

async def manejar_callback_eliminacion(query, user_id, data, context):
    """Manejador lógico para los callbacks del menú de eliminación."""
    if data == "del_reg_hoy":
        context.user_data['del_filtro_fecha'] = obtener_ahora_arg().strftime("%Y-%m-%d")
        await actualizar_menu_filtro_eliminacion(query, context)

    elif data == "del_reg_ayer":
        context.user_data['del_filtro_fecha'] = (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d")
        await actualizar_menu_filtro_eliminacion(query, context)

    elif data == "del_reg_otro":
        context.user_data['awaiting_del_custom_date'] = True
        await query.message.reply_text("📅 Ingresá la fecha que querés revisar (Ej: `2026-08-25`):", parse_mode="Markdown")

    elif data.startswith("del_mom_"):
        context.user_data['del_filtro_momento'] = data.replace("del_mom_", "")
        await actualizar_menu_filtro_eliminacion(query, context)

    elif data == "del_reg_mostrar" or data == "del_reg_volver":
        await mostrar_registros_para_eliminar(query, user_id, context)

    elif data.startswith("ejecutar_del_fila_"):
        fila_idx = int(data.replace("ejecutar_del_fila_", ""))
        
        # Eliminación directa en la planilla de Google Sheets
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws = sh.worksheet(f"User_{user_id}")
        ws.delete_rows(fila_idx)
        
        await query.answer("✅ Registro eliminado correctamente de la planilla.")
        await mostrar_registros_para_eliminar(query, user_id, context)

async def cmd_eliminar_ingesta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 1: Solicita al usuario el día y momento del registro que desea eliminar."""
    keyboard = [
        [
            InlineKeyboardButton("📅 Hoy", callback_data="del_reg_hoy"),
            InlineKeyboardButton("📅 Ayer", callback_data="del_reg_ayer"),
            InlineKeyboardButton("📅 Otro Día", callback_data="del_reg_otro")
        ],
        [
            InlineKeyboardButton("☕ Desayuno", callback_data="del_mom_Desayuno"),
            InlineKeyboardButton("🍽️ Almuerzo", callback_data="del_mom_Almuerzo")
        ],
        [
            InlineKeyboardButton("🫖 Merienda", callback_data="del_mom_Merienda"),
            InlineKeyboardButton("🌙 Cena", callback_data="del_mom_Cena")
        ],
        [
            InlineKeyboardButton("🔍 Ver Registros", callback_data="del_reg_mostrar")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Inicializamos valores temporales en user_data
    context.user_data['del_filtro_fecha'] = obtener_ahora_arg().strftime("%Y-%m-%d")
    context.user_data['del_filtro_momento'] = "Almuerzo"

    await update.message.reply_text(
        "🗑️ **Eliminar o Corregir Registro Pasado**\n\n"
        f"• Fecha seleccionada: `{context.user_data['del_filtro_fecha']}`\n"
        f"• Momento seleccionado: `{context.user_data['del_filtro_momento']}`\n\n"
        "Usá los botones para cambiar los filtros o tocá *Ver Registros*:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# =====================================================================================================================================
#                FINAL                               COMANDO ELIMINAR                          FINAL
# ======================================================================================================================================

# =============================================================================================================================================
#                    INICIO                                    COMANDO PACIENTES                                       INICIO
# =============================================================================================================================================

async def cmd_pacientes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando para que el profesional vea el listado de sus pacientes y genere un reporte PDF avanzado (hasta 6 meses)."""
    msg_espera = await update.message.reply_text("⏳ **Buscando pacientes y procesando historial clínico (hasta 6 meses)...**", parse_mode="Markdown")

    # Validación utilizando la función auxiliar existente
    prof_id = await _verificar_y_obtener_profesional(update)
    if not prof_id:
        await msg_espera.edit_text("⛔ **Acceso denegado:** Este comando es exclusivo para profesionales registrados.", parse_mode="Markdown")
        return

    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        
        # Obtener la especialidad del profesional desde la hoja 'Profesionales'
        especialidad_prof = "General"
        try:
            ws_prof = sh.worksheet("Profesionales")
            recs_prof = ws_prof.get_all_records()
            for rp in recs_prof:
                id_p = str(rp.get("User ID", rp.get("user_id", ""))).split('.')[0].strip()
                if id_p == prof_id:
                    especialidad_prof = str(rp.get("Especialidad", rp.get("especialidad", "General"))).strip()
                    break
        except Exception:
            pass

        # Filtrar pacientes del médico
        ws_usuarios = sh.worksheet("Usuarios")
        records_usuarios = ws_usuarios.get_all_records()

        pacientes_del_medico = []
        for r in records_usuarios:
            p_id = str(r.get("profesional", r.get("Profesional", ""))).split('.')[0].strip()
            if p_id == prof_id:
                u_id = str(r.get("User ID", r.get("user_id", ""))).split('.')[0].strip()
                nombre = r.get("Nombre", r.get("nombre", "Sin Nombre"))
                estado = r.get("Estado", r.get("estado", "Activo"))
                if estado.lower() in ['activo', 'sí', 'si', 'true', '1']:
                    pacientes_del_medico.append({"user_id": u_id, "nombre": nombre})

        if not pacientes_del_medico:
            await msg_espera.edit_text("ℹ️ No tenés pacientes activos asignados en este momento.", parse_mode="Markdown")
            return

        # 3. Determinar los últimos 6 meses dinámicamente
        ahora = obtener_ahora_arg()
        meses_a_evaluar = []
        for i in range(6):
            mes_calculado = ahora - timedelta(days=i * 30)
            m_str = mes_calculado.strftime("%Y-%m")
            if m_str not in meses_a_evaluar:
                meses_a_evaluar.append(m_str)
        meses_a_evaluar = sorted(list(set(meses_a_evaluar)))[-6:]

        texto_reporte = f"📋 **Listado de Pacientes Asignados**\n🩺 *Especialidad:* `{especialidad_prof}`\n\n"
        datos_para_pdf = []

        nombres_hojas = [ws.title for ws in sh.worksheets()]

        for pac in pacientes_del_medico:
            u_id = pac["user_id"]
            nombre = pac["nombre"]
            peso_str = "S/D"
            presion_str = "S/D"
            calorias_str = "S/D"

            try:
                ws_perfil = sh.worksheet(f"Perfil_{u_id}")
                recs_perfil = ws_perfil.get_all_records()
                if recs_perfil:
                    ultimo_p = recs_perfil[-1]
                    p_val = parse_raw_val(ultimo_p.get("PESO", ultimo_p.get("peso", 0)))
                    if p_val > 0:
                        peso_str = f"{p_val / 1000:.1f} kg" if p_val > 300 else f"{p_val} kg"
            except Exception:
                pass

            # Búsqueda flexible de la hoja de Presión
            recs_presion_all = []
            hoja_presion_nombre = next((h for h in nombres_hojas if h.lower() in [f"presion_{u_id}".lower(), f"presión_{u_id}".lower()]), None)
            if hoja_presion_nombre:
                try:
                    ws_p = sh.worksheet(hoja_presion_nombre)
                    recs_presion_all = ws_p.get_all_records()
                    if recs_presion_all:
                        ult_pres = recs_presion_all[-1]
                        sys = ult_pres.get("Alta", ult_pres.get("Sistolica", ult_pres.get("sistónica", ult_pres.get("sistolica", ""))))
                        dia = ult_pres.get("Baja", ult_pres.get("Diastolica", ult_pres.get("diastólica", ult_pres.get("diastolica", ""))))
                        if sys and dia:
                            presion_str = f"{sys}/{dia} mmHg"
                except Exception:
                    pass

            try:
                ws_comidas = sh.worksheet(f"Comidas_{u_id}")
                recs_comidas = ws_comidas.get_all_records()
                calorias_mes = []
                mes_actual_str = ahora.strftime("%Y-%m")
                for c in recs_comidas:
                    fecha_comida = str(c.get("Fecha", c.get("fecha", "")))
                    if mes_actual_str in fecha_comida:
                        cal = parse_raw_val(c.get("Calorias", c.get("calorias", 0)))
                        if cal > 0: calorias_mes.append(cal)
                if calorias_mes:
                    prom_cal = sum(calorias_mes) / len(calorias_mes)
                    calorias_str = f"{round(prom_cal)} kcal/día"
            except Exception:
                pass

            texto_reporte += (
                f"👤 **{nombre}** (ID: `{u_id}`)\n"
                f"⚖️ Peso: `{peso_str}` | 🩸 Presión: `{presion_str}`\n"
                f"🔥 Prom. Calorías: `{calorias_str}`\n"
                "--------------------------------------------------\n"
            )

            # Recopilar métricas históricas de hasta 6 meses
            historial_6m = []
            perfil_dict = recs_perfil[-1] if 'recs_perfil' in locals() and recs_perfil else {}

            for m_str in meses_a_evaluar:
                df_u = obtener_datos_usuario(u_id) if 'obtener_datos_usuario' in globals() else pd.DataFrame()
                prom_prot_m = 0
                prom_grasas_m = 0
                dias_m = 0
                prom_cal_m = 0

                if not df_u.empty and 'Fecha' in df_u.columns:
                    df_u['Mes_Filtro'] = df_u['Fecha'].str.slice(0, 7)
                    df_m = df_u[df_u['Mes_Filtro'] == m_str]
                    metricas_m = calcular_metricas_mensuales(df_m, perfil_dict)
                    prom_cal_m = metricas_m.get("prom_cal", 0)
                    prom_prot_m = metricas_m.get("prom_prot", 0)
                    prom_grasas_m = metricas_m.get("prom_grasas", metricas_m.get("prom_grasa", 0))
                    dias_m = metricas_m.get("dias_registrados", 0)

                presion_m_str = "S/D"
                presiones_mes = []
                for p in recs_presion_all:
                    f_pres = str(p.get("Fecha", p.get("fecha", p.get("Fecha_Hora", p.get("fecha_hora", "")))))
                    if m_str in f_pres:
                        s = p.get("Alta", p.get("Sistolica", p.get("sistónica", p.get("sistolica", ""))))
                        d = p.get("Baja", p.get("Diastolica", p.get("diastólica", p.get("diastolica", ""))))
                        if s and d:
                            presiones_mes.append(f"{s}/{d}")
                if presiones_mes:
                    presion_m_str = presiones_mes[-1]

                historial_6m.append({
                    "mes": m_str,
                    "prom_cal": prom_cal_m,
                    "prom_prot": prom_prot_m,
                    "prom_grasas": prom_grasas_m,
                    "presion": presion_m_str,
                    "dias": dias_m
                })

            datos_para_pdf.append({
                "nombre": nombre,
                "user_id": u_id,
                "historial": historial_6m
            })

        # 4. Generación de PDF avanzado
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph(f"<b>Reporte Clínico Consolidado ({especialidad_prof})</b>", styles['Heading1']))
        elements.append(Paragraph(f"Generado el: {ahora.strftime('%Y-%m-%d %H:%M')} | Período analizado: Últimos 6 meses", styles['Normal']))
        elements.append(Spacer(1, 15))

        elements.append(Paragraph("<b>Evolución Mensual por Paciente (Calorías, Proteínas, Grasas y Presión)</b>", styles['Heading2']))
        elements.append(Spacer(1, 10))

        for d in datos_para_pdf:
            elements.append(Paragraph(f"<b>Paciente: {d['nombre']} (ID: {d['user_id']})</b>", styles['Normal']))
            hist_data = [["Mes", "Calorías", "Proteínas", "Grasas", "Presión", "Días"]]
            for h in d["historial"]:
                hist_data.append([
                    h["mes"], 
                    f"{h['prom_cal']} kcal", 
                    f"{h['prom_prot']} g", 
                    f"{h['prom_grasas']} g", 
                    h["presion"], 
                    str(h["dias"])
                ])
            
            t_hist = Table(hist_data, colWidths=[80, 100, 95, 95, 102, 80])
            t_hist.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#F8F9F9")),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
            ]))
            elements.append(t_hist)
            elements.append(Spacer(1, 15))

        doc.build(elements)
        buffer.seek(0)

        await msg_espera.delete()
        await update.message.reply_text(texto_reporte, parse_mode="Markdown")
        await update.message.reply_document(
            document=buffer,
            filename=f"Reporte_Clinico_{especialidad_prof}_{ahora.strftime('%Y-%m')}.pdf",
            caption="📄 **Reporte clínico actualizado leyendo las columnas 'Alta' y 'Baja'.**",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error al generar listado de pacientes para el profesional {prof_id}: {e}")
        await msg_espera.edit_text(f"❌ Ocurrió un error al procesar el listado clínico: {e}")

# =============================================================================================================================================
#                    FINAL                                    COMANDO PACIENTES                                 FINAL
# =============================================================================================================================================

# =============================================================================================================================================
#                    INICIO                                    COMANDO INFORME                                 INICIO  
# =============================================================================================================================================

async def cmd_enviar_informe_actual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando exclusivo para el profesional: 
    Envía manualmente el resumen del mes actual (hasta ayer) al paciente indicado.
    Uso: /enviar_informe <user_id>
    """
    prof_id = await _verificar_y_obtener_profesional(update)
    if not prof_id:
        await update.message.reply_text("⛔ **Acceso denegado:** Este comando es exclusivo para profesionales registrados.", parse_mode="Markdown")
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ Debes indicar el ID del paciente.\n"
            "Uso correcto: `/enviar_informe <user_id>`", 
            parse_mode="Markdown"
        )
        return

    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ El ID de usuario ingresado debe ser un número entero válido.")
        return

    ahora_arg = obtener_ahora_arg()
    if hasattr(ahora_arg, 'tzinfo') and ahora_arg.tzinfo is not None:
        ahora_arg = ahora_arg.replace(tzinfo=None)
    
    mes_actual_str = ahora_arg.strftime("%Y-%m")

    msg_espera = await update.message.reply_text(
        f"⏳ Procesando informe del mes actual para el paciente `{target_user_id}`...", 
        parse_mode="Markdown"
    )

    exito = await procesar_y_enviar_informe_mensual(
        context=context,
        user_id=target_user_id,
        mes_target=mes_actual_str,
        es_automatico_15=False,
        forzar_envio=True
    )

    await msg_espera.delete()
    if exito:
        await update.message.reply_text(
            f"✅ El informe nutricional del mes actual fue enviado con éxito al paciente `{target_user_id}`.", 
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"❌ No se pudo completar el envío para el usuario `{target_user_id}`. "
            f"Revisá si tiene registros cargados en el mes o consulta los logs.", 
            parse_mode="Markdown"
        )

# =============================================================================================================================================
#                    FINAL                                    COMANDO INFORME                                 FINAL  
# =============================================================================================================================================

# =============================================================================================================================================
#                    INICIO                                     MAIN EXECUTION                                  INICIO  
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
    	
    app_bot.add_handler(CommandHandler(["pacientes"], cmd_pacientes))
    app_bot.add_handler(CommandHandler(["start","inicio"], cmd_start))
    app_bot.add_handler(CommandHandler(["comidas", "comida"], cmd_comidas))
    app_bot.add_handler(CommandHandler(["perfil", "peso"], cmd_perfil))
    app_bot.add_handler(CommandHandler(["presion", "presi", "presio"], cmd_presion_handler))  
    app_bot.add_handler(CommandHandler(["diario", "dia", "d"], cmd_diario))
    app_bot.add_handler(CommandHandler(["resumen", "mes", "mensual", "m"], cmd_resumen))
    app_bot.add_handler(CommandHandler(["mensaje", "semana", "semanal", "s"], cmd_mensaje))
    app_bot.add_handler(CommandHandler(["receta", "planilla"], cmd_cargar_receta))
    app_bot.add_handler(CommandHandler("eliminar", cmd_eliminar_ingesta))
    app_bot.add_handler(CommandHandler("informe", cmd_enviar_informe_actual))
    app_bot.add_handler(CommandHandler(["ingreso", "nuevo"], cmd_nueva_cuenta))
    

    # --- HANDLERS DE BOTONES INTERACTIVOS (CALLBACKS PANTALLA Y PDF) ---
    app_bot.add_handler(CallbackQueryHandler(mostrar_resumen_mes, pattern="^resumen_mes_"))
    app_bot.add_handler(CallbackQueryHandler(generar_y_enviar_pdf_resumen, pattern="^(descargar_pdf_resumen_|pdf_mes_)"))
    
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




