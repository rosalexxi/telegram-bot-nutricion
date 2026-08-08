import os
import re
import io
import json
import base64
import threading
from datetime import datetime, date, timedelta, time
import pytz
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from groq import Groq
from dotenv import load_dotenv
from flask import Flask, request, render_template_string

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

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_SHEETS_KEY_PATH = os.getenv("GOOGLE_SHEETS_KEY_PATH", "credentials.json")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "Registro_Nutricional_Bot")

ARG_TZ = pytz.timezone('America/Argentina/Buenos_Aires')

if GROQ_API_KEY:
    client_ai = Groq(api_key=GROQ_API_KEY)
else:
    client_ai = None

# Servidor Flask para Web Service en Render con Interfaz Interactiva
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
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def health_check():
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
    return render_template_string(HTML_TEMPLATE, resultado=resultado, error=error, query_text=query_text)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# Estados de conversación para Perfil y Fecha personalizada
AWAITING_PROFILE_DATA, AWAITING_CUSTOM_DATE, AWAITING_RESUMEN_MES, AWAITING_EDIT_ITEM = range(4)

# ==========================================
# FUNCIONES AUXILIARES Y FORMATO
# ==========================================
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
    
def calcular_proteina_sugerida(user_id=123456789):
    try:
        ahora_mes = obtener_ahora_arg().strftime("%Y-%m")
        perfil = obtener_perfil_usuario(user_id=user_id, mes_target=ahora_mes)
        if not perfil:
            peso, altura, genero, contextura = 75.0, 170.0, "masculino", "mediana"
        else:
            peso = parse_raw_val(perfil.get('Peso', 75.0))
            altura = parse_raw_val(perfil.get('Altura', 170.0))
            genero = str(perfil.get('Sexo', perfil.get('Genero', 'masculino')))
            contextura = str(perfil.get('Contextura', 'mediana'))
    except Exception:
        peso, altura, genero, contextura = 75.0, 170.0, "masculino", "mediana"

    altura_m = altura / 100.0
    
    if str(genero).lower() in ["femenino", "f", "mujer"]:
        peso_ideal_base = 45.5 + 2.3 * ((altura / 2.54) - 60)
    else:
        peso_ideal_base = 50.0 + 2.3 * ((altura / 2.54) - 60)
        
    if peso_ideal_base <= 0:
        peso_ideal_base = 22 * (altura_m ** 2)

    ctx = str(contextura).lower()
    if "peque" in ctx or "chica" in ctx:
        peso_ideal_ref = peso_ideal_base * 0.90
    elif "mediana" in ctx:
        peso_ideal_ref = peso_ideal_base
    else:
        peso_ideal_ref = peso_ideal_base * 1.20

    peso_efectivo = (peso + peso_ideal_ref) / 2.0
    return peso_efectivo * 1.3

def calcular_tmb_y_get(peso_actual, altura_cm, edad, genero="masculino", actividad="sedentario", contextura="grande"):
    altura_m = altura_cm / 100.0
    
    if str(genero).lower() in ["femenino", "f", "mujer"]:
        peso_ideal_base = 45.5 + 2.3 * ((altura_cm / 2.54) - 60)
    else:
        peso_ideal_base = 50.0 + 2.3 * ((altura_cm / 2.54) - 60)
    
    if peso_ideal_base <= 0:
        peso_ideal_base = 22 * (altura_m ** 2)

    ctx = str(contextura).lower()
    if "peque" in ctx or "chica" in ctx:
        peso_ideal_referencia = peso_ideal_base * 0.90
    elif "mediana" in ctx:
        peso_ideal_referencia = peso_ideal_base
    else:
        peso_ideal_referencia = peso_ideal_base * 1.20

    peso_efectivo = (peso_actual + peso_ideal_referencia) / 2.0
    
    if str(genero).lower() in ["femenino", "f", "mujer"]:
        tmb = 655 + (9.6 * peso_efectivo) + (1.8 * altura_cm) - (4.7 * edad)
    else:
        tmb = 66 + (13.7 * peso_efectivo) + (5 * altura_cm) - (6.8 * edad)
    
    factores = {
        "sedentario": 1.2,
        "jubilado": 1.2,
        "ligero": 1.375,
        "moderado": 1.55,
        "intenso": 1.725
    }
    factor = factores.get(str(actividad).lower(), 1.2)
    get_val = tmb * factor
    
    return tmb, get_val

# ==========================================
# GOOGLE SHEETS OPERACIONES
# ==========================================
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
            ws = spreadsheet.add_worksheet(title=title, rows="500", cols="5")
            ws.append_row(["Fecha_Hora", "Fecha_Dia", "Alta", "Baja", "Pulsaciones"])
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

def guardar_presion_en_sheets(user_id, alta, baja, pulsaciones):
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    ws = get_or_create_worksheet(sh, f"Presion_{user_id}")
    ahora = obtener_ahora_arg()
    ws.append_row([
        ahora.strftime("%Y-%m-%d %H:%M:%S"), 
        ahora.strftime("%Y-%m-%d"), 
        to_sheet_int(alta), 
        to_sheet_int(baja), 
        to_sheet_int(pulsaciones) if pulsaciones is not None else 0
    ])

def guardar_perfil_en_sheets(user_id, edad, peso, altura, genero="masculino", ocupacion="Sedentario", mes=None, reescribir=True):
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    ws = get_or_create_worksheet(sh, f"Perfil_{user_id}")
    ahora = obtener_ahora_arg()
    if not mes:
        mes = ahora.strftime("%Y-%m")
    
    nueva_fila = [
        to_sheet_int(edad), 
        to_sheet_int(peso), 
        to_sheet_int(altura), 
        str(genero), 
        str(ocupacion), 
        str(mes), 
        ahora.strftime("%Y-%m-%d %H:%M:%S")
    ]

    fila_a_actualizar = None

    if reescribir:
        records = ws.get_all_records()
        for idx, row in enumerate(records, start=2):
            mes_en_fila = str(row.get('Mes', row.get(list(row.keys())[5], ''))).strip()
            if mes_en_fila == str(mes):
                fila_a_actualizar = idx
                break

    if fila_a_actualizar:
        ws.update(f"A{fila_a_actualizar}:G{fila_a_actualizar}", [nueva_fila])
    else:
        ws.append_row(nueva_fila)

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

        return df
    except Exception:
        return pd.DataFrame()

def obtener_plantillas_comidas():
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws = get_or_create_worksheet(sh, "Plantillas_Comidas")
        records = ws.get_all_records()
        
        for p in records:
            for k in ['Peso', 'Calorias', 'Proteinas', 'Grasas', 'Carbohidratos', 'Fibras']:
                if k in p:
                    p[k] = parse_float_from_sheets(p[k])
                    
        return records
    except Exception:
        return []

# ==========================================
# PROCESAMIENTO IA (TEXTO, VOZ Y FOTO)
# ==========================================
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
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ],
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)
    
def analizar_imagen_con_groq(base64_image):
    if not client_ai:
        raise Exception("GROQ_API_KEY no está configurada correctamente.")
    prompt = "Analizá esta imagen de comida/plato. Identificá los alimentos, estimá sus pesos en gramos y nutrientes. Respondé ÚNICAMENTE en formato JSON con la clave 'items' conteniendo alimento, peso, calorias, proteinas, grasas, carbohidratos, fibras."
    response = client_ai.chat.completions.create(
        model="qwen/qwen3.6-27b",
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

def obtener_recomendacion_ia(resumen_texto):
    if not client_ai:
        return "No se pudo obtener recomendación de IA (API Key no configurada)."
    
    prompt = f"Basado en este resumen mensual y métricas del paciente, da una recomendación nutricional breve, profesional y motivadora (máximo 4 oraciones):\n\n{resumen_texto}"

    try:
        response = client_ai.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Mantené una dieta equilibrada rica en fibra y agua, ajustando las porciones según tu actividad diaria."

# ==========================================
# GENERADORES DE PDF
# ==========================================

def generar_pdf_instrucciones_bytes():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        rightMargin=40, 
        leftMargin=40, 
        topMargin=40, 
        bottomMargin=40
    )
    
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

def generar_pdf_presion_bytes(mes_str, df_presion, user_id):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1E3A8A'), spaceAfter=4)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor('#1E293B'))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8.5, leading=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)

    story = [
        Paragraph(f"<b>Detalle Diario de Presión Arterial - {mes_str}</b>", title_style),
        Paragraph(f"<b>Usuario Telegram ID:</b> {user_id}", body_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=10)
    ]

    if df_presion.empty:
        story.append(Paragraph("No hay registros de presión para este mes.", body_style))
    else:
        table_data = [[
            Paragraph("Fecha y Hora", header_style),
            Paragraph("Alta (mmHg)", header_style),
            Paragraph("Baja (mmHg)", header_style),
            Paragraph("Pulsaciones (lpm)", header_style)
        ]]

        for _, r in df_presion.iterrows():
            table_data.append([
                Paragraph(str(r.get('Fecha_Hora', '')), body_style),
                Paragraph(f"{r.get('Alta', 0):.0f}", body_style),
                Paragraph(f"{r.get('Baja', 0):.0f}", body_style),
                Paragraph(f"{r.get('Pulsaciones', 0):.0f}", body_style)
            ])

        t = Table(table_data, colWidths=[180, 100, 100, 120])
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

def generar_pdf_resumen_bytes(mes_str, df_mes, df_presion, perfil, tmb_val, recomendacion, user_id):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1E3A8A'), spaceAfter=4)
    sub_style = ParagraphStyle('SubTitle', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#2563EB'), spaceBefore=6, spaceAfter=4)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8, leading=11, textColor=colors.HexColor('#1E293B'))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)

    story = [
        Paragraph(f"<b>Reporte Nutricional Mensual - {mes_str}</b>", title_style),
        Paragraph(f"<b>Usuario Telegram ID:</b> {user_id}", body_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=8)
    ]

    headers_h1 = ["Fecha", "Cal. Consumid.", "Cal. Quemad.", "Bal. Neto", "Proteinas (g)", "Grasas (g)", "Carbohidratos (g)", "Fibras (g)"]
    table_data_h1 = [[Paragraph(h, header_style) for h in headers_h1]]

    tot_cons, tot_quem, tot_prot, tot_gras, tot_carb, tot_fibr = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    if not df_mes.empty:
        fechas_unicas = sorted(df_mes['Fecha'].unique())
        dias_con_registro = len(fechas_unicas)

        for f in fechas_unicas:
            sub = df_mes[df_mes['Fecha'] == f]
            
            c_cons = sub[sub['Calorias'] > 0]['Calorias'].sum()
            c_quem = abs(sub[sub['Calorias'] < 0]['Calorias'].sum())
            b_neto = c_cons - c_quem
            
            prot = float(sub['Proteinas'].sum())
            gras = float(sub['Grasas'].sum())
            carb = float(sub['Carbohidratos'].sum())
            fibr = float(sub['Fibras'].sum())

            tot_cons += c_cons
            tot_quem += c_quem
            tot_prot += prot
            tot_gras += gras
            tot_carb += carb
            tot_fibr += fibr

            table_data_h1.append([
                Paragraph(str(f), body_style),
                Paragraph(f"{c_cons:.1f} kcal", body_style),
                Paragraph(f"{c_quem:.1f} kcal", body_style),
                Paragraph(f"{b_neto:.1f} kcal", body_style),
                Paragraph(f"{prot:.1f} g", body_style),
                Paragraph(f"{gras:.1f} g", body_style),
                Paragraph(f"{carb:.1f} g", body_style),
                Paragraph(f"{fibr:.1f} g", body_style)
            ])
        
        tot_neto = tot_cons - tot_quem
        table_data_h1.append([
            Paragraph("<b>TOTAL MES</b>", body_style),
            Paragraph(f"<b>{tot_cons:.1f} kcal</b>", body_style),
            Paragraph(f"<b>{tot_quem:.1f} kcal</b>", body_style),
            Paragraph(f"<b>{tot_neto:.1f} kcal</b>", body_style),
            Paragraph(f"<b>{tot_prot:.1f} g</b>", body_style),
            Paragraph(f"<b>{tot_gras:.1f} g</b>", body_style),
            Paragraph(f"<b>{tot_carb:.1f} g</b>", body_style),
            Paragraph(f"<b>{tot_fibr:.1f} g</b>", body_style)
        ])

        div = dias_con_registro if dias_con_registro > 0 else 1
        table_data_h1.append([
            Paragraph("<b>PROM. DIARIO</b>", body_style),
            Paragraph(f"<b>{(tot_cons/div):.1f} kcal</b>", body_style),
            Paragraph(f"<b>{(tot_quem/div):.1f} kcal</b>", body_style),
            Paragraph(f"<b>{(tot_neto/div):.1f} kcal</b>", body_style),
            Paragraph(f"<b>{(tot_prot/div):.1f} g</b>", body_style),
            Paragraph(f"<b>{(tot_gras/div):.1f} g</b>", body_style),
            Paragraph(f"<b>{(tot_carb/div):.1f} g</b>", body_style),
            Paragraph(f"<b>{(tot_fibr/div):.1f} g</b>", body_style)
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
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=10))

    # --- EXTRACCIÓN DE DATOS BIOMÉTRICOS Y OBTENCIÓN DEL PESO IDEAL DE EXCEL ---
    edad = parse_raw_val(perfil.get('Edad')) if perfil else 0
    peso_actual = parse_raw_val(perfil.get('Peso')) if perfil else 0
    altura = parse_raw_val(perfil.get('Altura')) if perfil else 0
    genero = str(perfil.get('Sexo', perfil.get('Genero', 'masculino'))) if perfil else 'masculino'
    actividad = str(perfil.get('Ocupacion', 'sedentario')) if perfil else 'sedentario'
    
    # Recuperación directa desde Excel / Perfil (Si no existe, utiliza el peso actual por fallback)
    peso_ideal = parse_raw_val(perfil.get('Peso_Ideal', perfil.get('PesoIdeal', peso_actual))) if perfil else peso_actual
    if peso_ideal <= 0:
        peso_ideal = peso_actual

    # --- CÁLCULO DE VALORES IDEALES (Basado 100% en Peso Ideal) ---
    tmb_ideal, get_ideal = calcular_tmb_y_get(peso_ideal, altura, edad, genero, actividad)

    dias_activos = df_mes['Fecha'].nunique() if not df_mes.empty else 1
    get_total_ideal = get_ideal * dias_activos
    bal_calorico = tot_cons - get_total_ideal - tot_quem
    cambio_peso_kg = bal_calorico / 7700.0

    # Macronutrientes sugeridos según Peso Ideal
    prot_rec = peso_ideal * 1.6 if peso_ideal > 0 else 90.0  # 1.6g por kg de Peso Ideal
    gras_rec = (get_ideal * 0.25) / 9.0                      # 25% de calorías en grasa
    carb_rec = (get_ideal * 0.50) / 4.0                      # 50% de calorías en carbohidratos
    fibr_rec = 30.0

    # Promedios reales registrados
    prom_d_cons = (tot_cons / dias_activos) if dias_activos > 0 else 0
    prom_d_prot = (tot_prot / dias_activos) if dias_activos > 0 else 0
    prom_d_gras = (tot_gras / dias_activos) if dias_activos > 0 else 0
    prom_d_carb = (tot_carb / dias_activos) if dias_activos > 0 else 0
    prom_d_fibr = (tot_fibr / dias_activos) if dias_activos > 0 else 0

    # --- RE-EVALUACIÓN CON LA IA DE FORMA ENCAPSULADA ---
    try:
        prompt_ia = f"""
        Actúa como un médico nutricionista evaluando el resumen mensual de un paciente.
        Compara los promedios diarios consumidos contra los OBJETIVOS IDEALES calculados según su Peso Ideal:
        
        DATOS PACIENTE:
        - Peso Actual: {peso_actual:.1f} kg | Peso Ideal (Objetivo): {peso_ideal:.1f} kg
        - Altura: {altura:.1f} cm | Edad: {edad:.0f} años | Actividad: {actividad}
        
        VALORES DIARIOS REALES VS IDEALES:
        - Calorías: Real {prom_d_cons:.1f} kcal vs Ideal {get_ideal:.1f} kcal
        - Proteínas: Real {prom_d_prot:.1f} g vs Ideal {prot_rec:.1f} g
        - Grasas: Real {prom_d_gras:.1f} g vs Ideal {gras_rec:.1f} g
        - Carbohidratos: Real {prom_d_carb:.1f} g vs Ideal {carb_rec:.1f} g
        - Fibras: Real {prom_d_fibr:.1f} g vs Ideal {fibr_rec:.1f} g
        
        Redacta una recomendación médica/nutricional breve (máximo 4-5 líneas) analizando si debe subir/bajar nutrientes o ajustar calorías para acercarse a su peso ideal.
        """
        
        # Llamada a Groq/IA dentro de la función sin tocar el resto del programa
        res_ia = client_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt_ia}],
            temperature=0.3,
            max_tokens=300
        )
        recomendacion_actualizada = res_ia.choices[0].message.content.strip()
    except Exception:
        # Si no se puede contactar a la IA en el momento, usa la recomendación recibida por parámetro
        recomendacion_actualizada = recomendacion

    # --- CONSTRUCCIÓN DE LA TABLA COMPARATIVA CON VALORES IDEALES ---
    table_comp = [
        [Paragraph("<b>Nutriente / Métrica</b>", header_style), Paragraph("<b>Promedio Diario Real (Mes)</b>", header_style), Paragraph("<b>Valor Ideal (Peso Objetivo)</b>", header_style)],
        [Paragraph("Calorías", body_style), Paragraph(f"{prom_d_cons:.1f} kcal", body_style), Paragraph(f"{get_ideal:.1f} kcal (GET)", body_style)],
        [Paragraph("Proteínas", body_style), Paragraph(f"{prom_d_prot:.1f} g", body_style), Paragraph(f"{prot_rec:.1f} g", body_style)],
        [Paragraph("Grasas", body_style), Paragraph(f"{prom_d_gras:.1f} g", body_style), Paragraph(f"{gras_rec:.1f} g", body_style)],
        [Paragraph("Carbohidratos", body_style), Paragraph(f"{prom_d_carb:.1f} g", body_style), Paragraph(f"{carb_rec:.1f} g", body_style)],
        [Paragraph("Fibras", body_style), Paragraph(f"{prom_d_fibr:.1f} g", body_style), Paragraph(f"{fibr_rec:.1f} g", body_style)]
    ]
    t_comp = Table(table_comp, colWidths=[150, 185, 185])
    t_comp.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    story.append(t_comp)
    story.append(Spacer(1, 12))

    story.append(Paragraph(f"• <b>PERFIL BASE ({mes_str}):</b> Peso Actual: {peso_actual:.1f} kg | Peso Ideal Registrado: {peso_ideal:.1f} kg | Altura: {altura:.1f} cm", body_style))
    story.append(Paragraph(f"• <b>BALANCE CALÓRICO NETO PROYECTADO:</b> {bal_calorico:.1f} kcal", body_style))
    story.append(Paragraph(f"• <b>CAMBIO ESTIMADO DE PESO EN EL MES:</b> {cambio_peso_kg:.2f} kg ({cambio_peso_kg*1000:.1f} g)", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Recomendación Nutricional Personalizada (IA):</b>", sub_style))
    story.append(Paragraph(f"<i>{recomendacion_actualizada}</i>", body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ==========================================
# INTERFAZ Y RENDER DE CONFIRMACIÓN
# ==========================================

async def render_confirmation_screen(msg_or_query, context):
    items = context.user_data.get('pending_items', [])
    fecha = context.user_data.get('pending_fecha')
    momento = context.user_data.get('pending_momento')

    txt = f"📝 **Confirmación de Ingesta:**\n📅 Fecha: `{fecha}` | Momento: `{momento}`\n\n"
    for idx, item in enumerate(items, start=1):
        mult = item.get('multiplicador', 1.0)
        peso_total = item.get('peso', 0)
        cal_total = item.get('calorias', 0)
        
        alimento_str = item.get('alimento', item.get('nombre', ''))
        alimento_limpio = alimento_str.replace('§', '').strip()

        if mult != 1.0:
            txt += f"**{idx}. {alimento_limpio}** ({peso_total:.1f}g) (x{mult}): `{cal_total:.1f} kcal`\n"
        else:
            txt += f"**{idx}. {alimento_limpio}** ({peso_total:.1f}g): `{cal_total:.1f} kcal`\n"

    keyboard = []
    
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
    else:
        await msg_or_query.edit_text(txt, reply_markup=markup, parse_mode="Markdown")

# ==========================================
# HANDLERS DE TELEGRAM
# ==========================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 ¡Hola! Bienvenido a tu Bot Nutricional Personalizado.\n\n"
        "📌 Funciones y Comandos Disponibles:\n\n"
        "• `/comidas`: Visualiza listado y descarga PDF.\n"
        "• `/presion 120,80,70` registra alta, baja, pulso.\n"
        "• `/presion 120,80` omite pulso.\n"
        "• `/presion 2026-08` promedio mensual y PDF.\n"
        "• `/diario`: Ingestas del día y PDF detallado.\n"
        "• `/resumen`: Reporte mensual con IA y PDF.\n"
        "• `/actividad caminata,200 cal`: Guardar en exel.\n"
        "• `/actividadia aquagym,50 min`:Guarda por IA.\n"
        "• `/perfil`: Consulta o carga datos biométricos.\n"
        "• `/perfil,90 kg`: Actualiza el peso del mes.\n\n"
        "📌 Ingreso de ingestas:\n\n"
        "• **Del listado precargado:**\n"
        "  `*PIZZAJM` ingresa una unidad de la comida.\n"
        "  `*PIZZAJM,1.5` o `*CHURRO,6` ingresa la cantidad.\n\n"
        "• **Ingreso por IA:**\n"
        "  Texto, Imagen, Voz (descripción, cantidad o peso).\n"
        "• **Modificación:**\n"
        "  Ingresar `COMIDA` se conserva el peso y vuelve a la IA.\n"
        "  Ingresar `COMIDA,PESO` nuevos valores vuelve a la IA.\n\n"
        "📄 Te adjuntamos el manual de instrucciones actualizado en PDF."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
    pdf_buf = generar_pdf_instrucciones_bytes()
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=pdf_buf,
        filename="Manual_Bot_Nutricional.pdf"
    )

async def cmd_comidas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plantillas = obtener_plantillas_comidas()
    if not plantillas:
        await update.message.reply_text("📋 No hay comidas predeterminadas registradas en la hoja 'Plantillas_Comidas'.")
        return

    txt = "📋 **Listado de Comidas Predeterminadas:**\n\n"
    for p in plantillas:
        nombre = p.get('Nombre', '')
        descripcion = p.get('Descripcion') or p.get('Momento', '')
        txt += f"• **{nombre}**: {descripcion}\n"

    txt += "\n📄 Te adjuntamos el archivo en PDF completo con todos los macronutrientes a continuación."
    await update.message.reply_text(txt, parse_mode="Markdown")

    pdf_bytes = generar_pdf_comidas_bytes(plantillas)
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=pdf_bytes,
        filename="Comidas_Predeterminadas.pdf"
    )

async def cmd_actividad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto = update.message.text.replace('/actividad', '').strip()
    
    if not texto:
        await update.message.reply_text(
            "⚠️ Por favor ingresá la actividad y las calorías.\nEjemplo: `/actividad caminata, 250 cal`",
            parse_mode="Markdown"
        )
        return

    parte_calorias = texto.split(',')[-1] if ',' in texto else texto
    solo_numeros = re.sub(r'\D', '', parte_calorias)

    if solo_numeros:
        calorias_pos = float(solo_numeros)
    else:
        todos_los_numeros = re.findall(r'\d+', texto)
        if todos_los_numeros:
            calorias_pos = float(todos_los_numeros[-1])
        else:
            await update.message.reply_text(
                "❌ No se detectaron las calorías. Recordá indicar un número ej: `250 cal`.",
                parse_mode="Markdown"
            )
            return

    calorias_neg = -abs(calorias_pos)
    fecha_actual = obtener_ahora_arg().strftime("%Y-%m-%d")

    items = [{
        "alimento": texto,
        "peso": 0.0,
        "calorias": calorias_neg,
        "proteinas": 0.0,
        "grasas": 0.0,
        "carbohidratos": 0.0,
        "fibras": 0.0
    }]

    guardar_en_sheets(user_id, items, fecha_actual, "Actividad Física", tipo="Actividad")

    await update.message.reply_text(
        f"✅ **Actividad física registrada:**\n"
        f"• Detalle: `{texto}`\n"
        f"• Calorías: `{calorias_neg:.0f} kcal`",
        parse_mode="Markdown"
    )
    
async def actividad_ia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Función encapsulada para registrar actividad física con IA.
    Gestiona el cálculo inicial, botones (Guardar, Editar, Anular)
    y permite editar solo duración/calorías sin re-escribir la actividad.
    """
    # -------------------------------------------------------------------------
    # CASO 1: El usuario presiona uno de los botones (CallbackQuery)
    # -------------------------------------------------------------------------
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        accion = query.data

        estado_local = context.user_data.get('actividad_ia_pendiente')

        if not estado_local:
            await query.edit_message_text("⚠️ Esta interacción ha expirado o ya fue procesada.")
            return

        if accion == "act_guardar":
            fecha_auto, _ = obtener_momento_y_fecha_auto()
            item = {
                "alimento": f"Actividad: {estado_local['actividad']}",
                "peso": 0.0,
                "calorias": estado_local['calorias'],
                "proteinas": 0.0,
                "grasas": 0.0,
                "carbohidratos": 0.0,
                "fibras": 0.0
            }
            try:
                guardar_en_sheets([item], "Actividad", fecha_auto, "Actividad Física")
                await query.edit_message_text(
                    f"✅ **¡Actividad Guardada con éxito!**\n\n"
                    f"🏃 {estado_local['actividad']}: `{estado_local['calorias']:.1f} kcal`",
                    parse_mode="Markdown"
                )
            except Exception as err:
                await query.edit_message_text(f"❌ Error al guardar en Sheets: {err}")

            context.user_data.pop('actividad_ia_pendiente', None)

        elif accion == "act_anular":
            await query.edit_message_text("🚫 Registro de actividad cancelado.")
            context.user_data.pop('actividad_ia_pendiente', None)

        elif accion == "act_editar":
            # Guardamos cuál es la actividad activa para no perder el nombre
            act_actual = estado_local['actividad']
            await query.edit_message_text(
                f"✏️ **Edición de Actividad: {act_actual}**\n\n"
                f"Ingresá únicamente la nueva duración o calorías usando el comando.\n\n"
                f"Ejemplos:\n"
                f"• `/actividadia 20 min` (recalcula por tiempo)\n"
                f"• `/actividadia 200 cal` (fija las calorías en -200)",
                parse_mode="Markdown"
            )

        return

    # -------------------------------------------------------------------------
    # CASO 2: Invocación del comando por mensaje (/actividadia ...)
    # -------------------------------------------------------------------------
    if not update.message:
        return

    raw_text = update.message.text.replace('/actividadia', '').replace('/actividad_ia', '').strip()

    if not raw_text:
        await update.message.reply_text(
            "⚠️ Por favor ingresá la actividad y duración.\nEjemplo: `/actividadia aquagym 50 min`",
            parse_mode="Markdown"
        )
        return

    # Revisar si hay una actividad previa guardada en memoria para reusar el nombre
    estado_previo = context.user_data.get('actividad_ia_pendiente')
    actividad_guardada = estado_previo.get('actividad') if estado_previo else None

    # Detectar si el usuario ingresó solo calorías directas (ej: "200 cal", "-200 kcal", "250")
    import re
    es_solo_calorias = False
    calorias_directas = 0.0

    # Patrón para detectar si el texto es puramente un número o número + cal/kcal
    match_cal = re.match(r'^[\s\-]*(\d+(?:\.\d+)?)\s*(?:cal|kcal)?$', raw_text, re.IGNORECASE)
    
    if match_cal and "min" not in raw_text.lower():
        es_solo_calorias = True
        calorias_directas = -abs(float(match_cal.group(1)))

    # Caso A: Se ingresaron calorías directas y existía una actividad previa
    if es_solo_calorias and actividad_guardada:
        actividad_nombre = actividad_guardada
        calorias_val = calorias_directas
    else:
        # Caso B: Se ingresaron minutos o una actividad nueva completa -> Consulta a IA
        msg = await update.message.reply_text("⏳ Calculando gasto calórico con IA...")

        # Si el usuario solo puso un número/minutos (ej: "20 min") y había una actividad previa, armamos la frase completa
        if actividad_guardada and not any(c.isalpha() for c in raw_text.replace("min", "").strip()):
            texto_para_ia = f"{actividad_guardada} {raw_text}"
        else:
            texto_para_ia = raw_text

        try:
            if not client_ai:
                await msg.edit_text("❌ Error: API Key de GROQ no configurada.")
                return

            system_prompt = """Sos un asistente deportivo experto.
Analizá el texto de la actividad física y calculá el gasto calórico como un número NEGATIVO.
Devolvé EXCLUSIVAMENTE un JSON válido con este formato:
{
  "actividad": "Nombre de la actividad",
  "calorias": -250.0
}"""

            response = client_ai.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": texto_para_ia}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            datos = json.loads(response.choices[0].message.content)
            # Si ya teníamos un nombre de actividad, lo preservamos; si no, usamos el de la IA
            actividad_nombre = actividad_guardada if actividad_guardada else datos.get("actividad", raw_text)
            calorias_val = float(datos.get("calorias", 0.0))

            if calorias_val > 0:
                calorias_val = -calorias_val

            # Borrar mensaje temporal de carga
            await msg.delete()

        except Exception as e:
            await msg.edit_text(f"❌ Error al procesar con IA: {e}")
            return

    # Guardar estado actualizado en memoria
    context.user_data['actividad_ia_pendiente'] = {
        "actividad": actividad_nombre,
        "calorias": calorias_val
    }

    # Mostrar la vista interactiva con los 3 botones
    texto = (
        f"🏃 **Actividad Física Detectada**\n\n"
        f"• **Detalle:** {actividad_nombre}\n"
        f"• **Calorías:** `{calorias_val:.1f} kcal`\n\n"
        f"¿Qué deseás hacer?"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💾 GUARDAR", callback_data="act_guardar"),
            InlineKeyboardButton("✏️ EDITAR", callback_data="act_editar"),
        ],
        [
            InlineKeyboardButton("❌ ANULAR", callback_data="act_anular")
        ]
    ])

    await update.message.reply_text(texto, reply_markup=keyboard, parse_mode="Markdown")
    
async def actividad_ia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Función para registrar actividad física con IA.
    Gestiona el cálculo inicial, botones (Guardar, Editar, Anular)
    y permite editar solo duración/calorías sin re-escribir la actividad.
    """
    # -------------------------------------------------------------------------
    # CASO 1: El usuario presiona uno de los botones (CallbackQuery)
    # -------------------------------------------------------------------------
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        accion = query.data
        user_id = query.from_user.id

        estado_local = context.user_data.get('actividad_ia_pendiente')

        if not estado_local:
            await query.edit_message_text("⚠️ Esta interacción ha expirado o ya fue procesada.")
            return

        if accion == "act_guardar":
            fecha_auto, _ = obtener_momento_y_fecha_auto()
            item = {
                "alimento": f"Actividad: {estado_local['actividad']}",
                "peso": 0.0,
                "calorias": estado_local['calorias'],
                "proteinas": 0.0,
                "grasas": 0.0,
                "carbohidratos": 0.0,
                "fibras": 0.0
            }
            try:
                # Modificación: Se pasa el user_id en la posición correctas
                guardar_en_sheets(user_id, [item], fecha_auto, "Actividad Física", tipo="Actividad")
                await query.edit_message_text(
                    f"✅ **¡Actividad Guardada con éxito!**\n\n"
                    f"🏃 {estado_local['actividad']}: `{estado_local['calorias']:.1f} kcal`",
                    parse_mode="Markdown"
                )
            except Exception as err:
                await query.edit_message_text(f"❌ Error al guardar en Sheets: {err}")

            context.user_data.pop('actividad_ia_pendiente', None)

        elif accion == "act_anular":
            await query.edit_message_text("🚫 Registro de actividad cancelado.")
            context.user_data.pop('actividad_ia_pendiente', None)

        elif accion == "act_editar":
            act_actual = estado_local['actividad']
            await query.edit_message_text(
                f"✏️ **Edición de Actividad: {act_actual}**\n\n"
                f"Ingresá únicamente la nueva duración o calorías usando el comando.\n\n"
                f"Ejemplos:\n"
                f"• `/actividadia 20 min` (recalcula por tiempo)\n"
                f"• `/actividadia 200 cal` (fija las calorías en -200)",
                parse_mode="Markdown"
            )

        return

    # -------------------------------------------------------------------------
    # CASO 2: Invocación del comando por mensaje (/actividadia ...)
    # -------------------------------------------------------------------------
    if not update.message:
        return

    raw_text = update.message.text.replace('/actividadia', '').replace('/actividad_ia', '').strip()

    if not raw_text:
        await update.message.reply_text(
            "⚠️ Por favor ingresá la actividad y duración.\nEjemplo: `/actividadia aquagym 50 min`",
            parse_mode="Markdown"
        )
        return

    estado_previo = context.user_data.get('actividad_ia_pendiente')
    actividad_guardada = estado_previo.get('actividad') if estado_previo else None

    es_solo_calorias = False
    calorias_directas = 0.0

    match_cal = re.match(r'^[\s\-]*(\d+(?:\.\d+)?)\s*(?:cal|kcal)?$', raw_text, re.IGNORECASE)
    
    if match_cal and "min" not in raw_text.lower():
        es_solo_calorias = True
        calorias_directas = -abs(float(match_cal.group(1)))

    if es_solo_calorias and actividad_guardada:
        actividad_nombre = actividad_guardada
        calorias_val = calorias_directas
    else:
        msg = await update.message.reply_text("⏳ Calculando gasto calórico con IA...")

        if actividad_guardada and not any(c.isalpha() for c in raw_text.replace("min", "").strip()):
            texto_para_ia = f"{actividad_guardada} {raw_text}"
        else:
            texto_para_ia = raw_text

        try:
            if not client_ai:
                await msg.edit_text("❌ Error: API Key de GROQ no configurada.")
                return

            system_prompt = """Sos un asistente deportivo experto.
Analizá el texto de la actividad física y calculá el gasto calórico como un número NEGATIVO.
Devolvé EXCLUSIVAMENTE un JSON válido con este formato:
{
  "actividad": "Nombre de la actividad",
  "calorias": -250.0
}"""

            response = client_ai.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": texto_para_ia}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            datos = json.loads(response.choices[0].message.content)
            actividad_nombre = actividad_guardada if actividad_guardada else datos.get("actividad", raw_text)
            calorias_val = float(datos.get("calorias", 0.0))

            if calorias_val > 0:
                calorias_val = -calorias_val

            await msg.delete()

        except Exception as e:
            await msg.edit_text(f"❌ Error al procesar con IA: {e}")
            return

    context.user_data['actividad_ia_pendiente'] = {
        "actividad": actividad_nombre,
        "calorias": calorias_val
    }

    texto = (
        f"🏃 **Actividad Física Detectada**\n\n"
        f"• **Detalle:** {actividad_nombre}\n"
        f"• **Calorías:** `{calorias_val:.1f} kcal`\n\n"
        f"¿Qué deseás hacer?"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💾 GUARDAR", callback_data="act_guardar"),
            InlineKeyboardButton("✏️ EDITAR", callback_data="act_editar"),
        ],
        [
            InlineKeyboardButton("❌ ANULAR", callback_data="act_anular")
        ]
    ])

    await update.message.reply_text(texto, reply_markup=keyboard, parse_mode="Markdown")    
        
async def cmd_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw_text = update.message.text.replace('/perfil', '').strip()
    ahora = obtener_ahora_arg()
    mes_actual = ahora.strftime("%Y-%m")

    def verificar_alerta_30_dias(uid):
        try:
            gc = get_gspread_client()
            sh = gc.open(SPREADSHEET_NAME)
            ws = get_or_create_worksheet(sh, f"Perfil_{uid}")
            records = ws.get_all_records()
            if not records:
                return False
            
            ultimo_registro = records[-1]
            fecha_act_str = str(ultimo_registro.get('Fecha_Actualizacion', '')).strip()
            if fecha_act_str:
                fecha_act = datetime.strptime(fecha_act_str[:10], "%Y-%m-%d").date()
                diferencia_dias = (ahora.date() - fecha_act).days
                return diferencia_dias > 30
        except Exception:
            pass
        return False

    if raw_text:
        parts = [p.strip() for p in raw_text.replace('/', ',').replace(' ', ',').split(',') if p.strip()]
        
        if len(parts) == 1:
            try:
                nuevo_peso = float(parts[0].replace(',', '.'))
                perfil_existente = obtener_perfil_usuario(user_id, mes_target=mes_actual)
                
                if perfil_existente:
                    edad = parse_raw_val(perfil_existente.get('Edad', 64))
                    altura = parse_raw_val(perfil_existente.get('Altura', 170))
                    genero = str(perfil_existente.get('Sexo', perfil_existente.get('Genero', 'masculino')))
                    ocupacion = str(perfil_existente.get('Ocupacion', 'Jubilado'))
                else:
                    edad, altura, genero, ocupacion = 64.0, 170.0, "masculino", "Jubilado"

                guardar_perfil_en_sheets(user_id, edad, nuevo_peso, altura, genero, ocupacion, mes_actual, reescribir=True)
                tmb, get_val = calcular_tmb_y_get(nuevo_peso, altura, edad, genero, ocupacion)
                
                await update.message.reply_text(
                    f"✅ **Peso actualizado correctamente para el mes `{mes_actual}`:**\n"
                    f"• Nuevo Peso: `{nuevo_peso:.1f}` kg\n"
                    f"• **TMB Estimada:** `{tmb:.0f} kcal/día`\n"
                    f"• **GET Estimado:** `{get_val:.0f} kcal/día`",
                    parse_mode="Markdown"
                )
                return
            except ValueError:
                await update.message.reply_text("❌ Formato de peso inválido. Usá por ejemplo: `/perfil 82.5`", parse_mode="Markdown")
                return

        elif len(parts) >= 3:
            try:
                edad = float(parts[0].replace(',', '.'))
                peso = float(parts[1].replace(',', '.'))
                altura = float(parts[2].replace(',', '.'))
                genero = parts[3] if len(parts) > 3 else "masculino"
                ocupacion = parts[4] if len(parts) > 4 else "Jubilado"
                
                guardar_perfil_en_sheets(user_id, edad, peso, altura, genero, ocupacion, mes_actual, reescribir=True)
                tmb, get_val = calcular_tmb_y_get(peso, altura, edad, genero, ocupacion)
                
                await update.message.reply_text(
                    f"✅ **Perfil registrado/actualizado para el mes `{mes_actual}`:**\n"
                    f"• Edad: `{edad:.0f}` años\n• Peso: `{peso:.1f}` kg\n• Altura: `{altura:.1f}` cm\n"
                    f"• Género: `{genero}` | Ocupación: `{ocupacion}`\n"
                    f"• **TMB Estimada:** `{tmb:.0f} kcal/día`\n"
                    f"• **GET Estimado:** `{get_val:.0f} kcal/día`",
                    parse_mode="Markdown"
                )
                return
            except ValueError:
                await update.message.reply_text("❌ Error en los datos ingresados. Asegurate de usar números válidos.", parse_mode="Markdown")
                return

    perfil = obtener_perfil_usuario(user_id, mes_target=mes_actual)
    alerta_30_dias = verificar_alerta_30_dias(user_id)
    
    advertencia_txt = ""
    if alerta_30_dias:
        advertencia_txt = "\n⚠️ **ADVERTENCIA:** Han pasado más de 30 días desde tu último registro de peso. Te sugerimos actualizarlo con `/perfil [PESO]`.\n"

    if perfil:
        peso = parse_raw_val(perfil.get('Peso'))
        altura = parse_raw_val(perfil.get('Altura'))
        edad = parse_raw_val(perfil.get('Edad'))
        genero = str(perfil.get('Sexo', perfil.get('Genero', 'masculino')))
        ocupacion = str(perfil.get('Ocupacion', 'Jubilado'))

        tmb, get_val = calcular_tmb_y_get(peso, altura, edad, genero, ocupacion)
        txt = (
            f"{advertencia_txt}"
            f"👤 **Perfil Biométrico Actual ({mes_actual}):**\n\n"
            f"• Edad: `{edad:.0f}` años\n"
            f"• Peso: `{peso:.1f}` kg\n"
            f"• Altura: `{altura:.1f}` cm\n"
            f"• Género: `{genero}`\n"
            f"• Ocupación: `{ocupacion}`\n"
            f"• **TMB Estimada:** `{tmb:.0f} kcal/día`\n"
            f"• **GET Estimado:** `{get_val:.0f} kcal/día`\n\n"
            f"📌 **Para actualizar solo tu peso mensual:**\n"
            f"`/perfil 82.5`\n\n"
            f"📌 **Para actualizar todos los datos:**\n"
            f"`/perfil EDAD, PESO, ALTURA, GENERO, OCUPACION`"
        )
    else:
        txt = (
            f"{advertencia_txt}"
            f"👤 **Perfil no registrado para este mes.** Para ingresar tus datos usá:\n"
            f"`/perfil EDAD, PESO, ALTURA, GENERO, OCUPACION`\n"
            f"(Ej: `/perfil 64, 82, 172, M, Jubilado`)"
        )

    await update.message.reply_text(txt, parse_mode="Markdown")

async def cmd_presion_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw_text = update.message.text.replace('/presion', '').strip()
    
    if not raw_text:
        await update.message.reply_text(
            "🩺 Ingresá la presión o consultá un mes. Ejemplos:\n"
            "• `/presion 120,80,70`\n"
            "• `/presion 120,80`\n"
            "• `/presion 2026-08`", 
            parse_mode="Markdown"
        )
        return

    if re.match(r'^20\d{2}-\d{2}$', raw_text):
        await mostrar_resumen_presion_mes(update, user_id, raw_text)
        return

    parts = [p.strip() for p in raw_text.replace('/', ',').replace(' ', ',').split(',') if p.strip()]
    if len(parts) >= 2:
        alta = float(parts[0])
        baja = float(parts[1])
        pulsaciones = float(parts[2]) if len(parts) > 2 else None
        guardar_presion_en_sheets(user_id, alta, baja, pulsaciones)
        pul_str = f" | Pulsaciones: `{pulsaciones}`" if pulsaciones is not None else ""
        await update.message.reply_text(f"✅ **Presión registrada:**\nAlta: `{alta}` | Baja: `{baja}`{pul_str}", parse_mode="Markdown")
        return
    else:
        await update.message.reply_text("❌ Formato incorrecto. Uso: `/presion 120,80,70` o `/presion 120,80` o `/presion 2026-08`", parse_mode="Markdown")

async def mostrar_resumen_presion_mes(query_or_update, user_id, mes_str):
    df_presion = obtener_datos_presion(user_id)
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
    df_presion = obtener_datos_presion(user_id)
    df_p_mes = df_presion[df_presion['Fecha_Dia'].str.startswith(mes_str)] if not df_presion.empty and 'Fecha_Dia' in df_presion.columns else pd.DataFrame()
    
    pdf_bytes = generar_pdf_presion_bytes(mes_str, df_p_mes, user_id)
    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=pdf_bytes,
        filename=f"Presion_Arterial_{mes_str}.pdf"
    )

async def cmd_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Hoy", callback_data="diario_hoy"), InlineKeyboardButton("📆 Ayer", callback_data="diario_ayer")],
        [InlineKeyboardButton("🗓️ Seleccionar Fecha", callback_data="diario_otro")]
    ])
    await update.message.reply_text("📅 **Consulta de Diario:** Seleccioná qué día querés revisar:", reply_markup=keyboard, parse_mode="Markdown")

async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ahora = obtener_ahora_arg()
    mes_actual = ahora.strftime("%Y-%m")
    mes_anterior = (ahora.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Mes Actual", callback_data=f"resumen_mes_{mes_actual}")],
        [InlineKeyboardButton("📆 Mes Anterior", callback_data=f"resumen_mes_{mes_anterior}")],
        [InlineKeyboardButton("🗓️ Otro Mes", callback_data="resumen_mes_otro")]
    ])

    await update.message.reply_text("📊 **Resumen Mensual:** Seleccioná la opción que querés consultar:", reply_markup=keyboard, parse_mode="Markdown")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🎙️ Procesando audio con IA...")
    try:
        file = await context.bot.get_file(update.message.voice.file_id)
        audio_bytes = await file.download_as_bytearray()
        
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.ogg"
        
        transcription = client_ai.audio.transcriptions.create(
            file=(audio_file.name, audio_file.read()),
            model="whisper-large-v3",
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
        
        data = analizar_imagen_con_groq(base64_image)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        await msg.edit_text(f"❌ Error al procesar imagen: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw_text = update.message.text.strip()

    if context.user_data.get('awaiting_edit_item_val'):
        context.user_data['awaiting_edit_item_val'] = False
        idx = context.user_data.get('editing_item_idx')
        items = context.user_data.get('pending_items', [])
        if 0 <= idx < len(items):
            try:
                parts = [p.strip() for p in raw_text.split(',') if p.strip()]
                item_actual = items[idx]
                
                if len(parts) == 1:
                    nuevo_alimento = parts[0]
                    peso_actual = item_actual.get('peso', 100)
                    prompt_ia = f"{nuevo_alimento}, {peso_actual}g"
                    data_ia = analizar_con_groq(prompt_ia)
                    nuevo_item = data_ia.get("items", [{}])[0]
                    
                    items[idx]['alimento'] = nuevo_item.get('alimento', nuevo_alimento)
                    items[idx]['peso'] = parse_raw_val(nuevo_item.get('peso', peso_actual))
                    items[idx]['calorias'] = parse_raw_val(nuevo_item.get('calorias', 0))
                    items[idx]['proteinas'] = parse_raw_val(nuevo_item.get('proteinas', 0))
                    items[idx]['grasas'] = parse_raw_val(nuevo_item.get('grasas', 0))
                    items[idx]['carbohidratos'] = parse_raw_val(nuevo_item.get('carbohidratos', 0))
                    items[idx]['fibras'] = parse_raw_val(nuevo_item.get('fibras', 0))
                    items[idx]['multiplicador'] = 1.0

                elif len(parts) == 2:
                    nuevo_alimento = parts[0]
                    nuevo_peso = parse_raw_val(parts[1].replace('g', '').strip())
                    prompt_ia = f"{nuevo_alimento}, {nuevo_peso}g"
                    data_ia = analizar_con_groq(prompt_ia)
                    nuevo_item = data_ia.get("items", [{}])[0]

                    items[idx]['alimento'] = nuevo_item.get('alimento', nuevo_alimento)
                    items[idx]['peso'] = nuevo_peso
                    items[idx]['calorias'] = parse_raw_val(nuevo_item.get('calorias', 0))
                    items[idx]['proteinas'] = parse_raw_val(nuevo_item.get('proteinas', 0))
                    items[idx]['grasas'] = parse_raw_val(nuevo_item.get('grasas', 0))
                    items[idx]['carbohidratos'] = parse_raw_val(nuevo_item.get('carbohidratos', 0))
                    items[idx]['fibras'] = parse_raw_val(nuevo_item.get('fibras', 0))
                    items[idx]['multiplicador'] = 1.0

                else:
                    items[idx]['alimento'] = parts[0]
                    if len(parts) > 1: items[idx]['peso'] = float(parts[1].replace('g', '').strip())
                    if len(parts) > 2: items[idx]['calorias'] = float(parts[2])
                    if len(parts) > 3: items[idx]['proteinas'] = float(parts[3])
                    if len(parts) > 4: items[idx]['grasas'] = float(parts[4])
                    if len(parts) > 5: items[idx]['carbohidratos'] = float(parts[5])
                    if len(parts) > 6: items[idx]['fibras'] = float(parts[6])
                    items[idx]['multiplicador'] = 1.0

                context.user_data['pending_items'] = items
                msg = await update.message.reply_text("✅ Ítem actualizado correctamente.")
                await render_confirmation_screen(msg, context)
                return
            except Exception as e:
                await update.message.reply_text(f"❌ Error al procesar la edición: {e}. Usá: `Nuevo alimento` o `Nuevo alimento, peso`", parse_mode="Markdown")
                return

    if context.user_data.get('awaiting_diario_date'):
        context.user_data['awaiting_diario_date'] = False
        await mostrar_diario_fecha(update, user_id, raw_text)
        return

    if context.user_data.get('awaiting_resumen_date'):
        context.user_data['awaiting_resumen_date'] = False
        await mostrar_resumen_mes(update, user_id, raw_text)
        return

    if context.user_data.get('awaiting_date'):
        context.user_data['awaiting_date'] = False
        context.user_data['pending_fecha'] = raw_text
        await render_confirmation_screen(update.message, context)
        return

    if raw_text.startswith('/'):
        cmd = raw_text.split()[0].lower()
        
        if cmd == '/start':
            await cmd_start(update, context)
        elif cmd == '/comidas':
            await cmd_comidas(update, context)
        elif cmd == '/diario':
            await cmd_diario(update, context)
        elif cmd == '/resumen':
            await cmd_resumen(update, context)
        elif cmd == '/perfil':
            await cmd_perfil(update, context)
        elif cmd.startswith('/presi'):
            await cmd_presion_handler(update, context)
        elif cmd == '/actividad':
            await cmd_actividad(update, context)
        elif cmd in ['/actividadia', '/actividad_ia']:
            await cmd_actividad_ia(update, context)
        else:
            await update.message.reply_text("❌ Comando no reconocido.")
        return

    if raw_text.startswith('*'):
        parts = [p.strip() for p in raw_text.split(',') if p.strip()]
        plantilla_nombre = parts[0].replace('*', '').strip().upper()
        multiplicador = 1.0
        if len(parts) > 1:
            try:
                multiplicador = float(parts[1].replace(',', '.'))
            except ValueError:
                multiplicador = 1.0

        plantillas = obtener_plantillas_comidas()
        coincidencia = None
        if plantillas:
            for p in plantillas:
                if str(p.get("Nombre", "")).strip().upper() == plantilla_nombre:
                    coincidencia = p
                    break
                    
        if coincidencia:
            fecha_auto, momento_auto = obtener_momento_y_fecha_auto()
            alimento_desc = coincidencia.get("Descripcion") or coincidencia.get("Nombre")
            
            if multiplicador != 1.0:
                alimento_final = f"{multiplicador:g} {alimento_desc}"
            else:
                alimento_final = alimento_desc

            item = {
                "alimento": alimento_final,
                "multiplicador": multiplicador,
                "peso": parse_raw_val(coincidencia.get("Peso")) * multiplicador,
                "calorias": parse_raw_val(coincidencia.get("Calorias")) * multiplicador,
                "proteinas": parse_raw_val(coincidencia.get("Proteinas")) * multiplicador,
                "grasas": parse_raw_val(coincidencia.get("Grasas")) * multiplicador,
                "carbohidratos": parse_raw_val(coincidencia.get("Carbohidratos")) * multiplicador,
                "fibras": parse_raw_val(coincidencia.get("Fibras")) * multiplicador
            }
            context.user_data['pending_items'] = [item]
            context.user_data['pending_tipo'] = "Comida"
            context.user_data['pending_fecha'] = fecha_auto
            context.user_data['pending_momento'] = momento_auto
            
            msg = await update.message.reply_text("⚡ Plantilla cargada directamente (sin IA)...")
            await render_confirmation_screen(msg, context)
            return
        else:
            await update.message.reply_text(f"❌ La plantilla `{raw_text}` no fue encontrada en Excel. Registro descartado.", parse_mode="Markdown")
            return

    msg = await update.message.reply_text("⏳ Analizando alimento con IA...")
    try:
        data = analizar_con_groq(raw_text)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        await msg.edit_text(f"❌ Error al procesar el texto: {e}")

async def procesar_y_mostrar_confirmacion(data, msg, context):
    items = data.get("items", [])
    for it in items:
        if "multiplicador" not in it:
            it["multiplicador"] = 1.0
    fecha_auto, momento_auto = obtener_momento_y_fecha_auto()
    
    context.user_data['pending_items'] = items
    context.user_data['pending_tipo'] = "Comida"
    context.user_data['pending_fecha'] = fecha_auto
    context.user_data['pending_momento'] = momento_auto
    await render_confirmation_screen(msg, context)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "noop":
        return

    elif data == "confirm_save":
        items = context.user_data.get('pending_items', [])
        fecha = context.user_data.get('pending_fecha')
        momento = context.user_data.get('pending_momento')
        
        if not items:
            await query.edit_message_text("❌ No hay ítems para guardar.")
            return

        guardar_en_sheets(user_id, items, fecha, momento)
        await query.edit_message_text(f"✅ **¡Registro guardado correctamente!**\n📅 Fecha: `{fecha}` | Momento: `{momento}`\nTotal ítems: {len(items)}", parse_mode="Markdown")

    elif data == "cancel_entry":
        context.user_data.pop('pending_items', None)
        await query.edit_message_text("🚫 Registro cancelado y eliminado.")

    elif data.startswith("set_m_"):
        nuevo_m = data.replace("set_m_", "")
        context.user_data['pending_momento'] = nuevo_m
        await render_confirmation_screen(query, context)

    elif data == "set_d_hoy":
        context.user_data['pending_fecha'] = obtener_ahora_arg().strftime("%Y-%m-%d")
        await render_confirmation_screen(query, context)

    elif data == "set_d_ayer":
        context.user_data['pending_fecha'] = (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d")
        await render_confirmation_screen(query, context)

    elif data == "set_d_otro":
        await query.edit_message_text("📅 Por favor, escribí la fecha deseada en formato `YYYY-MM-DD` (Ej: `2026-08-01`):", parse_mode="Markdown")
        context.user_data['awaiting_date'] = True

    elif data.startswith("edit_item_"):
        idx = int(data.replace("edit_item_", "")) - 1
        items = context.user_data.get('pending_items', [])
        
        if 0 <= idx < len(items):
            context.user_data['editing_item_idx'] = idx
            context.user_data['awaiting_edit_item_val'] = True
            item = items[idx]
            await query.edit_message_text(
                f"✏️ **Editando Ítem #{idx+1} ({item['alimento']}):**\n"
                f"Podés enviar solo el nuevo alimento (ej. `milanesa de pollo`) o el alimento y peso (ej. `milanesa de pollo, 250`).",
                parse_mode="Markdown"
            )

    elif data.startswith("del_item_"):
        idx = int(data.replace("del_item_", "")) - 1
        items = context.user_data.get('pending_items', [])
        if 0 <= idx < len(items):
            items.pop(idx)
            context.user_data['pending_items'] = items
        await render_confirmation_screen(query, context)

    elif data == "diario_hoy":
        fecha = obtener_ahora_arg().strftime("%Y-%m-%d")
        await mostrar_diario_fecha(query, user_id, fecha)

    elif data == "diario_ayer":
        fecha = (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d")
        await mostrar_diario_fecha(query, user_id, fecha)

    elif data == "diario_otro":
        await query.edit_message_text("📆 Por favor enviá la fecha que querés consultar en formato `YYYY-MM-DD`:", parse_mode="Markdown")
        context.user_data['awaiting_diario_date'] = True

    elif data.startswith("descargar_pdf_diario_"):
        fecha_str = data.replace("descargar_pdf_diario_", "")
        await generar_y_enviar_pdf_diario(query, user_id, fecha_str, context)

    elif data == "resumen_mes_otro":
        await query.edit_message_text("🗓️ Por favor enviá el mes que querés consultar en formato `YYYY-MM` (Ej: `2026-07`):", parse_mode="Markdown")
        context.user_data['awaiting_resumen_date'] = True

    elif data.startswith("resumen_mes_"):
        mes_str = data.replace("resumen_mes_", "")
        await mostrar_resumen_mes(query, user_id, mes_str)

    elif data.startswith("descargar_pdf_resumen_"):
        mes_str = data.replace("descargar_pdf_resumen_", "")
        await generar_y_enviar_pdf_resumen(query, user_id, mes_str, context)

    elif data.startswith("descargar_pdf_presion_"):
        mes_str = data.replace("descargar_pdf_presion_", "")
        await generar_y_enviar_pdf_presion(query, user_id, mes_str, context)

async def mostrar_diario_fecha(query_or_update, user_id, fecha_str):
    df = obtener_datos_usuario(user_id)
    if df.empty:
        txt = f"📂 No hay registros cargados para el usuario `{user_id}`."
    else:
        df_filtrado = df[df['Fecha'] == fecha_str]
        if df_filtrado.empty:
            txt = f"📅 No hay registros para la fecha `{fecha_str}`."
        else:
            txt = f"📅 **Registro del día {fecha_str}:**\n\n"
            
            c_cons = df_filtrado[df_filtrado['Calorias'] > 0]['Calorias'].sum()
            c_quem = abs(df_filtrado[df_filtrado['Calorias'] < 0]['Calorias'].sum())
            b_neto = c_cons - c_quem
            
            momentos_orden = ["Desayuno", "Colación", "Almuerzo", "Merienda", "Cena"]
            agrupados = {}
            for _, r in df_filtrado.iterrows():
                m = r.get('Momento', 'Comida')
                alim = r.get('Alimento', 'Item')
                if m not in agrupados:
                    agrupados[m] = []
                agrupados[m].append(alim)

            for m in momentos_orden:
                if m in agrupados:
                    items_str = ", ".join(agrupados[m])
                    txt += f"• **{m}**: {items_str}\n"

            for m, items_list in agrupados.items():
                if m not in momentos_orden:
                    items_str = ", ".join(items_list)
                    txt += f"• **{m}**: {items_str}\n"
            
            txt += f"\n📥 **Consumidas:** `{c_cons:.0f} kcal`"
            txt += f"\n🔥 **Quemadas:** `{c_quem:.0f} kcal`"
            txt += f"\n⚖️ **Balance Neto:** `{b_neto:.0f} kcal`"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Descargar PDF del Diario", callback_data=f"descargar_pdf_diario_{fecha_str}")]
    ])

    if hasattr(query_or_update, 'edit_message_text'):
        await query_or_update.edit_message_text(txt, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await query_or_update.message.reply_text(txt, reply_markup=keyboard, parse_mode="Markdown")

async def generar_y_enviar_pdf_diario(query, user_id, fecha_str, context):
    df = obtener_datos_usuario(user_id)
    df_diario = df[df['Fecha'] == fecha_str] if not df.empty else pd.DataFrame()
    
    pdf_bytes = generar_pdf_diario_bytes(fecha_str, df_diario, user_id)
    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=pdf_bytes,
        filename=f"Diario_{fecha_str}.pdf"
    )

async def mostrar_resumen_mes(query_or_update, user_id, mes_str):
    df = obtener_datos_usuario(user_id)
    perfil = obtener_perfil_usuario(user_id, mes_target=mes_str)

    if df.empty:
        txt = f"📂 No hay registros cargados para la cuenta del usuario `{user_id}`."
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(txt, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(txt, parse_mode="Markdown")
        return

    df_mes = df[df['Fecha'].str.startswith(mes_str)]
    if df_mes.empty:
        txt = f"📊 No hay registros cargados para el mes `{mes_str}`."
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(txt, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(txt, parse_mode="Markdown")
        return

    dias_activos = df_mes['Fecha'].nunique()
    dias_div = dias_activos if dias_activos > 0 else 1

    total_cons = df_mes[df_mes['Calorias'] > 0]['Calorias'].sum()
    total_quem = abs(df_mes[df_mes['Calorias'] < 0]['Calorias'].sum())
    total_neto = total_cons - total_quem

    total_prot = df_mes['Proteinas'].sum()
    total_gras = df_mes['Grasas'].sum()
    total_carb = df_mes['Carbohidratos'].sum()
    total_fibr = df_mes['Fibras'].sum()

    prom_cons = total_cons / dias_div
    prom_quem = total_quem / dias_div

    prom_prot = total_prot / dias_div
    prom_gras = total_gras / dias_div
    prom_carb = total_carb / dias_div
    prom_fibr = total_fibr / dias_div

    tmb_val = 0
    get_val = 0
    peso = 0
    if perfil:
        peso = parse_raw_val(perfil.get('Peso'))
        altura = parse_raw_val(perfil.get('Altura'))
        edad = parse_raw_val(perfil.get('Edad'))
        genero = str(perfil.get('Sexo', perfil.get('Genero', 'masculino')))
        actividad = str(perfil.get('Ocupacion', 'Jubilado'))
        tmb_val, get_val = calcular_tmb_y_get(peso, altura, edad, genero, actividad)

    prot_rec = calcular_proteina_sugerida(user_id=user_id) if peso > 0 else 90.0
    gras_rec = (get_val * 0.25) / 9.0 if get_val > 0 else 60.0
    carb_rec = (get_val * 0.50) / 4.0 if get_val > 0 else 250.0
    fibr_rec = 30.0

    txt = f"📊 **Resumen Mensual y Tabla Comparativa ({mes_str}):**\n\n"
    txt += f"• **Días registrados:** `{dias_activos}`\n\n"
    txt += "📋 **Tabla Comparativa (Promedios Reales vs Recomendados):**\n"
    txt += f"• **Calorías:** `{prom_cons:.0f} kcal` vs `{get_val:.0f} kcal` (GET)\n"
    txt += f"• **Proteínas:** `{prom_prot:.1f} g` vs `{prot_rec:.1f} g`\n"
    txt += f"• **Grasas:** `{prom_gras:.1f} g` vs `{gras_rec:.1f} g`\n"
    txt += f"• **Carbohidratos:** `{prom_carb:.1f} g` vs `{carb_rec:.1f} g`\n"
    txt += f"• **Fibras:** `{prom_fibr:.1f} g` vs `{fibr_rec:.1f} g`\n\n"

    resumen_para_ia = f"Mes: {mes_str}, Dias activos: {dias_activos}, Promedios reales: Kcal Consumidas={prom_cons:.0f}, Kcal Quemadas={prom_quem:.0f}, Prot={prom_prot:.1f}g, Gras={prom_gras:.1f}g, Carb={prom_carb:.1f}g, Fibr={prom_fibr:.1f}g. GET estimado: {get_val:.0f} kcal"
    rec_ia = obtener_recomendacion_ia(resumen_para_ia)
    txt += f"💡 **Recomendación IA:**\n_{rec_ia}_"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Descargar PDF Resumen", callback_data=f"descargar_pdf_resumen_{mes_str}")]
    ])

    if hasattr(query_or_update, 'edit_message_text'):
        await query_or_update.edit_message_text(txt, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await query_or_update.message.reply_text(txt, reply_markup=keyboard, parse_mode="Markdown")


async def generar_y_enviar_pdf_resumen(update, context, mes_str, df_mes, df_presion, perfil, tmb_val, rec_ia, user_id):
    """
    Calcula el peso ideal progresivo (promedio entre peso actual y la meta fija del Excel)
    y genera/envía el reporte PDF nutricional mensual al usuario.
    """
    query = update.callback_query if update.callback_query else None
    chat_id = query.message.chat_id if query else update.effective_chat.id

    # --- LÓGICA DE PESO IDEAL PROGRESIVO ---
    # 1. Obtiene la meta fija grabada en la columna 'Peso_ideal' de Google Sheets
    raw_meta = parse_raw_val(
        perfil.get('Peso_ideal') or perfil.get('Peso Ideal') or perfil.get('peso_ideal') or 0
    )

    # 2. Si el valor ingresado viene como 75000 (sin punto decimal), lo convierte automáticamente a 75.0 kg
    if raw_meta > 200:
        raw_meta /= 1000.0

    # 3. Obtiene el peso actual del perfil para el mes
    peso_act = parse_raw_val(perfil.get('Peso', perfil.get('peso', 0)))

    # 4. Asigna como 'Peso_Ideal' el promedio dinámico entre el Peso Actual y la Meta del Excel
    if raw_meta > 0 and peso_act > 0:
        perfil['Peso_Ideal'] = round((peso_act + raw_meta) / 2.0, 1)
    else:
        perfil['Peso_Ideal'] = raw_meta or peso_act

    # --- GENERACIÓN DEL ARCHIVO PDF EN MEMORIA ---
    pdf_bytes = generar_pdf_resumen_bytes(
        mes_str, df_mes, df_presion, perfil, tmb_val, rec_ia, user_id
    )

    # --- ENVÍO DEL DOCUMENTO VÍA TELEGRAM ---
    await context.bot.send_document(
        chat_id=chat_id,
        document=pdf_bytes,
        filename=f"Resumen_Nutricional_{mes_str}.pdf"
    )
    
    
# ==========================================
# INICIALIZACIÓN
# ==========================================
def main():
    if TELEGRAM_TOKEN:
        # Iniciar Flask en hilo secundario
        threading.Thread(target=run_flask, daemon=True).start()
        
        # Iniciar Bot Telegram
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

        application.add_handler(CommandHandler("start", cmd_start))
        application.add_handler(CommandHandler("comidas", cmd_comidas))
        application.add_handler(CommandHandler("diario", cmd_diario))
        application.add_handler(CommandHandler("resumen", cmd_resumen))
        application.add_handler(CommandHandler("perfil", cmd_perfil))
        application.add_handler(CommandHandler("presion", cmd_presion_handler))
        application.add_handler(CommandHandler("actividad", cmd_actividad))
        application.add_handler(CommandHandler("actividadia", actividad_ia))
        application.add_handler(CommandHandler("actividad_ia", actividad_ia))

        application.add_handler(MessageHandler(filters.VOICE, handle_voice))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Manejador específico para los botones de actividad IA
        application.add_handler(CallbackQueryHandler(actividad_ia, pattern="^act_"))
        
        # Manejador general de callbacks
        application.add_handler(CallbackQueryHandler(handle_callback))

        application.run_polling()
    else:
        # Si no hay token de Telegram, corre únicamente como servidor Flask
        run_flask()

if __name__ == '__main__':
    main()
    
    
    
