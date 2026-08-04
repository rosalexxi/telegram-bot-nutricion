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

# ReportLab para PDF
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

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
    
def calcular_tmb_y_get(peso_actual, altura_cm, edad, genero="masculino", actividad="sedentario", contextura="grande"):
    # 1. Estimar el peso ideal base según altura y género (Fórmula de Devine adaptada)
    altura_m = altura_cm / 100.0
    
    if str(genero).lower() in ["femenino", "f", "mujer"]:
        peso_ideal_base = 45.5 + 2.3 * ((altura_cm / 2.54) - 60)
    else:
        peso_ideal_base = 50.0 + 2.3 * ((altura_cm / 2.54) - 60)
    
    if peso_ideal_base <= 0:
        peso_ideal_base = 22 * (altura_m ** 2)

    # 2. Ajustar el peso ideal según la contextura ósea (Grande +20% para un enfoque realista y sostenible)
    ctx = str(contextura).lower()
    if "peque" in ctx or "chica" in ctx:
        peso_ideal_referencia = peso_ideal_base * 0.90
    elif "mediana" in ctx:
        peso_ideal_referencia = peso_ideal_base
    else:  # Grande por defecto
        peso_ideal_referencia = peso_ideal_base * 1.20

    # 3. Tomar el promedio entre tu peso actual (con sobrepeso) y el peso ideal ajustado
    peso_efectivo = (peso_actual + peso_ideal_referencia) / 2.0
    
    # 4. Calcular TMB usando el peso efectivo
    if str(genero).lower() in ["femenino", "f", "mujer"]:
        tmb = 655 + (9.6 * peso_efectivo) + (1.8 * altura_cm) - (4.7 * edad)
    else:
        tmb = 66 + (13.7 * peso_efectivo) + (5 * altura_cm) - (6.8 * edad)
    
    # 5. Calcular GET según el nivel de actividad
    factores = {
        "sedentario": 1.2,
        "jubilado": 1.2,
        "ligero": 1.4,
        "moderado": 1.6,
        "intenso": 1.8
    }
    factor = factores.get(str(actividad).lower(), 1.2)
    get_val = tmb * factor
    
    # 6. Cálculo interno de las proteínas esperadas utilizando el peso efectivo
    proteinas_esperadas = peso_efectivo * 1.3
    
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

def guardar_perfil_en_sheets(user_id, edad, peso, altura, genero="masculino", ocupacion="Sedentario", mes=None):
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    ws = get_or_create_worksheet(sh, f"Perfil_{user_id}")
    ahora = obtener_ahora_arg()
    if not mes:
        mes = ahora.strftime("%Y-%m")
    
    ws.append_row([
        to_sheet_int(edad), 
        to_sheet_int(peso), 
        to_sheet_int(altura), 
        str(genero), 
        str(ocupacion), 
        str(mes), 
        ahora.strftime("%Y-%m-%d %H:%M:%S")
    ])

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
        model="qwen/qwen3.6-27b",  # <--- Modelo cambiado exclusivamente para visión
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
    # Márgenes equilibrados para un diseño más limpio (Aprox 1.5 cm)
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        rightMargin=40, 
        leftMargin=40, 
        topMargin=40, 
        bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    
    # Paleta de colores moderna
    PRIMARY = colors.HexColor('#0F172A')   # Slate 900 (Casi negro/azul profundo)
    SECONDARY = colors.HexColor('#2563EB') # Blue 600 (Azul moderno)
    TEXT_COLOR = colors.HexColor('#334155')# Slate 700 (Texto legible)
    BG_LIGHT = colors.HexColor('#F8FAFC')  # Slate 50 (Fondo sutil para cajas)
    BORDER_COLOR = colors.HexColor('#E2E8F0') # Slate 200

    # Estilos tipográficos refinados
    title_style = ParagraphStyle(
        'ModernTitle', 
        parent=styles['Heading1'], 
        fontSize=18, 
        leading=22, 
        textColor=PRIMARY, 
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'ModernSubtitle', 
        parent=styles['Normal'], 
        fontSize=10, 
        leading=14, 
        textColor=SECONDARY, 
        spaceAfter=15
    )
    section_style = ParagraphStyle(
        'ModernSection', 
        parent=styles['Heading2'], 
        fontSize=12, 
        leading=16, 
        textColor=PRIMARY, 
        spaceBefore=12, 
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'ModernBody', 
        parent=styles['Normal'], 
        fontSize=9, 
        leading=14, 
        textColor=TEXT_COLOR
    )
    
    story = []

    # Cabecera moderna con barra lateral simulada mediante tabla
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

    # Sección 1: Comandos Principales en una Tabla Estilizada
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

    # Sección 2: Entrada de Datos y Multiplicadores (Caja de destaque)
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

    # Compilación final del documento
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

    tot_cons = 0.0
    tot_quem = 0.0
    tot_prot = 0.0
    tot_gras = 0.0
    tot_carb = 0.0
    tot_fibr = 0.0

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

    edad = parse_raw_val(perfil.get('Edad')) if perfil else 0
    peso = parse_raw_val(perfil.get('Peso')) if perfil else 0
    altura = parse_raw_val(perfil.get('Altura')) if perfil else 0
    genero = str(perfil.get('Sexo', perfil.get('Genero', 'masculino'))) if perfil else 'masculino'
    actividad = str(perfil.get('Ocupacion', 'sedentario')) if perfil else 'sedentario'
    
    tmb, get_val = calcular_tmb_y_get(peso, altura, edad, genero, actividad)

    dias_activos = df_mes['Fecha'].nunique() if not df_mes.empty else 1
    get_total = get_val * dias_activos
    bal_calorico = tot_cons - get_total - tot_quem
    cambio_peso_kg = bal_calorico / 7700.0

    prot_rec = peso * 1.5 if peso > 0 else 90.0
    gras_rec = (get_val * 0.25) / 9.0
    carb_rec = (get_val * 0.50) / 4.0
    fibr_rec = 30.0

    prom_d_cons = (tot_cons / dias_activos) if dias_activos > 0 else 0
    prom_d_prot = (tot_prot / dias_activos) if dias_activos > 0 else 0
    prom_d_gras = (tot_gras / dias_activos) if dias_activos > 0 else 0
    prom_d_carb = (tot_carb / dias_activos) if dias_activos > 0 else 0
    prom_d_fibr = (tot_fibr / dias_activos) if dias_activos > 0 else 0

    table_comp = [
        [Paragraph("<b>Nutriente / Métrica</b>", header_style), Paragraph("<b>Promedio Diario Real (Mes)</b>", header_style), Paragraph("<b>Valor Recomendado / Objetivo</b>", header_style)],
        [Paragraph("Calorías", body_style), Paragraph(f"{prom_d_cons:.1f} kcal", body_style), Paragraph(f"{get_val:.1f} kcal (GET)", body_style)],
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

    story.append(Paragraph(f"• <b>PERFIL USADO PARA EL CÁLCULO ({mes_str}):</b> Edad: {edad:.0f} | Peso: {peso:.1f}kg | Altura: {altura:.1f}cm | Ocupación: {actividad}", body_style))
    story.append(Paragraph(f"• <b>BALANCE CALÓRICO NETO REAL:</b> {bal_calorico:.1f} kcal", body_style))
    story.append(Paragraph(f"• <b>CAMBIO ESTIMADO DE PESO:</b> {cambio_peso_kg:.2f} kg ({cambio_peso_kg*1000:.1f} g)", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Recomendación de la IA:</b>", sub_style))
    story.append(Paragraph(f"<i>{recomendacion}</i>", body_style))

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
        if mult != 1.0:
            txt += f"**{idx}. {item['alimento']}** ({peso_total:.1f}g) (x{mult}): `{cal_total:.1f} kcal`\n"
        else:
            txt += f"**{idx}. {item['alimento']}** ({peso_total:.1f}g): `{cal_total:.1f} kcal`\n"

    keyboard = []
    
    m_buttons = []
    for m in ["Desayuno", "Almuerzo", "Merienda", "Cena"]:
        mark = "✅ " if m.lower() == momento.lower() else ""
        m_buttons.append(InlineKeyboardButton(f"{mark}{m}", callback_data=f"set_m_{m}"))
    keyboard.append(m_buttons)

    for idx, item in enumerate(items):
        keyboard.append([
            InlineKeyboardButton(f"Item #{idx+1}: {item['alimento'][:15]}", callback_data="noop"),
            InlineKeyboardButton("✏️ Editar", callback_data=f"edit_item_{idx}"),
            InlineKeyboardButton("🗑️ Anular", callback_data=f"del_item_{idx}")
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
        "• `/comidas`: Visualiza el listado de comidas predeterminadas y descarga su PDF oficial.\n"
        "• `/presion`: Registra valores \n`/presion 120,80,70` registra alta,baja,pulso \n`/presion 120,80` omite pulso \n `/presion 2026-08` promedio mensual y PDF detallado .\n"
        "• `/diario`: Consulta los consumos del día con agrupamiento inteligente y PDF diario detallado.\n"
        "• `/resumen`: Genera el reporte mensual con la **Tabla Comparativa de Macronutrientes**, datos biométricos del mes y recomendaciones de IA. y PDF detallado\n"
        "• `/perfil`: Consulta o actualiza tus datos biométricos corporales y ocupación específicos por mes.\n\n"
        "📌 Ingreso de ingestas:\n\n"
        "• **Multiplicadores en Plantillas:\n** `*PIZZAJM`, `*PIZZAJM,1.5` o `*CHURRO,6` para ajustar porciones automáticamente sin pasar por IA.\n\n"
        "• Para ingresar una ingesta se puede enviar un texto, una imagen o un archivo de voz.\n"
        "• Al modificar se puede cambiar solo la comida manteniendo el peso o comida,peso . La IA va a calcular los nuevos valores.\n\n"
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

async def cmd_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw_text = update.message.text.replace('/perfil', '').strip()

    if raw_text:
        parts = [p.strip() for p in raw_text.replace('/', ',').replace(' ', ',').split(',') if p.strip()]
        if len(parts) >= 3:
            try:
                edad = float(parts[0].replace(',', '.'))
                peso = float(parts[1].replace(',', '.'))
                altura = float(parts[2].replace(',', '.'))
                genero = parts[3] if len(parts) > 3 else "masculino"
                ocupacion = parts[4] if len(parts) > 4 else "Jubilado"
                mes = parts[5] if len(parts) > 5 else obtener_ahora_arg().strftime("%Y-%m")

                guardar_perfil_en_sheets(user_id, edad, peso, altura, genero, ocupacion, mes)
                tmb, get_val = calcular_tmb_y_get(peso, altura, edad, genero, ocupacion)
                await update.message.reply_text(
                    f"✅ **Perfil actualizado correctamente para el mes `{mes}`:**\n"
                    f"• Edad: `{edad:.0f}` años\n• Peso: `{peso:.1f}` kg\n• Altura: `{altura:.1f}` cm\n"
                    f"• Género: `{genero}` | Ocupación: `{ocupacion}`\n"
                    f"• **TMB Estimada:** `{tmb:.0f} kcal/día`\n"
                    f"• **GET Estimado:** `{get_val:.0f} kcal/día`",
                    parse_mode="Markdown"
                )
                return
            except ValueError:
                await update.message.reply_text("❌ Error en los datos ingresados. Asegurate de usar números válidos.")
                return

    ahora_mes = obtener_ahora_arg().strftime("%Y-%m")
    perfil = obtener_perfil_usuario(user_id, mes_target=ahora_mes)
    if perfil:
        peso = parse_raw_val(perfil.get('Peso'))
        altura = parse_raw_val(perfil.get('Altura'))
        edad = parse_raw_val(perfil.get('Edad'))
        genero = str(perfil.get('Sexo', perfil.get('Genero', 'masculino')))
        ocupacion = str(perfil.get('Ocupacion', 'Jubilado'))
        mes = str(perfil.get('Mes', ahora_mes))

        tmb, get_val = calcular_tmb_y_get(peso, altura, edad, genero, ocupacion)
        txt = (
            f"👤 **Perfil Biométrico Actual ({mes}):**\n\n"
            f"• Edad: `{edad:.0f}` años\n"
            f"• Peso: `{peso:.1f}` kg\n"
            f"• Altura: `{altura:.1f}` cm\n"
            f"• Género: `{genero}`\n"
            f"• Ocupación: `{ocupacion}`\n"
            f"• **TMB Estimada:** `{tmb:.0f} kcal/día`\n"
            f"• **GET Estimado:** `{get_val:.0f} kcal/día`\n\n"
            f"Para actualizar tus datos envía:\n"
            f"`/perfil EDAD, PESO, ALTURA, GENERO, OCUPACION, MES`\n"
            f"(Ej: `/perfil 64, 82, 172, M, Jubilado, 2026-08`)"
        )
    else:
        txt = (
            "👤 **Perfil no registrado.** Para ingresar tus datos biométricos usá:\n"
            "`/perfil EDAD, PESO, ALTURA, GENERO, OCUPACION, MES`\n"
            "(Ej: `/perfil 64, 82, 172, M, Jubilado, 2026-08`)"
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
        if cmd == '/presion':
            await cmd_presion_handler(update, context)
        elif cmd == '/diario':
            await cmd_diario(update, context)
        elif cmd == '/resumen':
            await cmd_resumen(update, context)
        elif cmd == '/start':
            await cmd_start(update, context)
        elif cmd == '/comidas':
            await cmd_comidas(update, context)
        elif cmd == '/perfil':
            await cmd_perfil(update, context)
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
            
            # Modificación semántica: si el multiplicador es distinto de 1, se antepone al texto del alimento
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
        idx = int(data.replace("edit_item_", ""))
        context.user_data['editing_item_idx'] = idx
        context.user_data['awaiting_edit_item_val'] = True
        items = context.user_data.get('pending_items', [])
        item = items[idx]
        await query.edit_message_text(
            f"✏️ **Editando Ítem #{idx+1} ({item['alimento']}):**\n"
            f"Podés enviar solo el nuevo alimento (ej. `milanesa de pollo`) o el alimento y peso (ej. `milanesa de pollo, 250`).",
            parse_mode="Markdown"
        )

    elif data.startswith("del_item_"):
        idx = int(data.replace("del_item_", ""))
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
    df_presion = obtener_datos_presion(user_id)

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
    prom_neto = total_neto / dias_div

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

    prot_rec = peso * 1.5 if peso > 0 else 90.0
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

async def generar_y_enviar_pdf_resumen(query, user_id, mes_str, context):
    df = obtener_datos_usuario(user_id)
    perfil = obtener_perfil_usuario(user_id, mes_target=mes_str)
    df_presion = obtener_datos_presion(user_id)
    
    df_mes = df[df['Fecha'].str.startswith(mes_str)] if not df.empty else pd.DataFrame()
    
    tmb_val = 0
    if perfil:
        peso = parse_raw_val(perfil.get('Peso'))
        altura = parse_raw_val(perfil.get('Altura'))
        edad = parse_raw_val(perfil.get('Edad'))
        genero = str(perfil.get('Sexo', perfil.get('Genero', 'masculino')))
        actividad = str(perfil.get('Ocupacion', 'Jubilado'))
        tmb_val, _ = calcular_tmb_y_get(peso, altura, edad, genero, actividad)

    rec_ia = obtener_recomendacion_ia(f"Resumen del mes {mes_str} para usuario {user_id}")
    
    pdf_bytes = generar_pdf_resumen_bytes(mes_str, df_mes, df_presion, perfil, tmb_val, rec_ia, user_id)
    
    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=pdf_bytes,
        filename=f"Resumen_Nutricional_{mes_str}.pdf"
    )

# ==========================================
# MAIN
# ==========================================
def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN no configurado en variables de entorno.")

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("comidas", cmd_comidas))
    application.add_handler(CommandHandler("perfil", cmd_perfil))
    application.add_handler(CommandHandler("presion", cmd_presion_handler))
    application.add_handler(CommandHandler("diario", cmd_diario))
    application.add_handler(CommandHandler("resumen", cmd_resumen))
    
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))

    application.run_polling()

if __name__ == "__main__":
    main()
