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
    filters
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

# Servidor Flask para Web Service en Render
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
                tot_cal = tot_prot = tot_gras = tot_carb = tot_fibr = 0
                for it in items:
                    c = parse_raw_val(it.get('calorias', 0))
                    p = parse_raw_val(it.get('proteinas', 0))
                    g = parse_raw_val(it.get('grasas', 0))
                    cb = parse_raw_val(it.get('carbohidratos', 0))
                    f = parse_raw_val(it.get('fibras', 0))
                    tot_cal += c; tot_prot += p; tot_gras += g; tot_carb += cb; tot_fibr += f
                    res_lines.append(f"• {it.get('alimento')} ({it.get('peso',0)}g): {c:.1f} kcal | Prot: {p:.1f}g | Gras: {g:.1f}g | Carb: {cb:.1f}g | Fibr: {f:.1f}g")
                
                res_lines.append(f"\n---\nTOTALES: {tot_cal:.1f} kcal | Prot: {tot_prot:.1f}g | Gras: {tot_gras:.1f}g | Carb: {tot_carb:.1f}g | Fibr: {tot_fibr:.1f}g")
                resultado = "\n".join(res_lines)
            except Exception as e:
                error = str(e)
    return render_template_string(HTML_TEMPLATE, resultado=resultado, error=error, query_text=query_text)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

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

def calcular_tmb_y_get(peso_actual, altura_cm, edad, genero="masculino", actividad="sedentario", contextura="grande", peso_ideal=None):
    peso_actual = parse_raw_val(peso_actual)
    peso_ideal_val = parse_raw_val(peso_ideal)

    if peso_ideal_val <= 0:
        peso_ideal_val = peso_actual

    peso_efectivo = (peso_actual + peso_ideal_val) / 2.0

    if str(genero).lower() in ["femenino", "f", "mujer"]:
        tmb = 655 + (9.6 * peso_efectivo) + (1.8 * altura_cm) - (4.7 * edad)
    else:
        tmb = 66 + (13.7 * peso_efectivo) + (5 * altura_cm) - (6.8 * edad)

    factores = {"sedentario": 1.2, "jubilado": 1.2, "ligero": 1.375, "moderado": 1.55, "intenso": 1.725}
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
            str(fecha), str(momento), item.get("alimento", "Desconocido"),
            to_sheet_int(item.get("peso", 0)), to_sheet_int(item.get("calorias", 0)),
            to_sheet_int(item.get("proteinas", 0)), to_sheet_int(item.get("grasas", 0)),
            to_sheet_int(item.get("carbohidratos", 0)), to_sheet_int(item.get("fibras", 0))
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
    
    nueva_fila = [to_sheet_int(edad), to_sheet_int(peso), to_sheet_int(altura), str(genero), str(ocupacion), str(mes), ahora.strftime("%Y-%m-%d %H:%M:%S")]
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
            if k_upper == 'EDAD': perfil['Edad'] = parse_float_from_sheets(v)
            elif k_upper == 'PESO': perfil['Peso'] = parse_float_from_sheets(v)
            elif k_upper == 'ALTURA': perfil['Altura'] = parse_float_from_sheets(v)
            elif k_upper in ['GENERO', 'SEXO']: perfil['Sexo'] = str(v)
            elif k_upper == 'OCUPACION': perfil['Ocupacion'] = str(v)
            elif k_upper == 'MES': perfil['Mes'] = str(v)
            elif k_upper in ['PESO_IDEAL', 'PESOIDEAL']: perfil['Peso_Ideal'] = parse_float_from_sheets(v)

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

# ==========================================
# GENERADORES DE PDF
# ==========================================

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
    
    story = [
        Table([[Paragraph("🤖 Guía Interactiva del Bot Nutricional", title_style)], [Paragraph("MANUAL DE USUARIO • ASISTENTE PERSONAL INTELIGENTE", subtitle_style)]], colWidths=[532]),
        Spacer(1, 10),
        Paragraph("1. Comandos Principales", section_style)
    ]
    
    cmds_data = [
        [Paragraph("<b>/start</b>", body_style), Paragraph("Inicia el bot y reenvía este manual informativo actualizado.", body_style)],
        [Paragraph("<b>/comidas</b>", body_style), Paragraph("Visualiza el listado de comidas predeterminadas y descarga su plantilla en PDF.", body_style)],
        [Paragraph("<b>/presion</b>", body_style), Paragraph("Registra valores (Ej: <code>120,80,70</code>) o consulta el resumen mensual de presión (Ej: <code>2026-08</code>).", body_style)],
        [Paragraph("<b>/diario</b>", body_style), Paragraph("Consulta los consumos del día con agrupamiento inteligente y descarga de PDF detallado.", body_style)],
        [Paragraph("<b>/resumen</b>", body_style), Paragraph("Obtiene el reporte mensual con tabla comparativa de macronutrientes y recomendaciones de IA.", body_style)],
        [Paragraph("<b>/perfil</b>", body_style), Paragraph("Consulta o actualiza tus datos biométricos corporales específicos por mes.", body_style)],
    ]
    t_cmds = Table(cmds_data, colWidths=[90, 442])
    t_cmds.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), BG_LIGHT), ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR), ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR)]))
    story.append(t_cmds)

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

    story = [Paragraph("<b>LISTADO DE COMIDAS PREDETERMINADAS</b>", title_style), HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=12)]

    if plantillas:
        table_data = [[Paragraph("Nombre", header_style), Paragraph("Descripción", header_style), Paragraph("Peso (g)", header_style), Paragraph("Kcal", header_style), Paragraph("Prot (g)", header_style), Paragraph("Gras (g)", header_style), Paragraph("Carb (g)", header_style), Paragraph("Fibr (g)", header_style)]]
        for p in plantillas:
            table_data.append([
                Paragraph(str(p.get("Nombre", "")), body_style), Paragraph(str(p.get("Descripcion") or p.get("Momento", "")), body_style),
                Paragraph(f"{p.get('Peso', 0):.1f}", body_style), Paragraph(f"{p.get('Calorias', 0):.1f}", body_style),
                Paragraph(f"{p.get('Proteinas', 0):.1f}", body_style), Paragraph(f"{p.get('Grasas', 0):.1f}", body_style),
                Paragraph(f"{p.get('Carbohidratos', 0):.1f}", body_style), Paragraph(f"{p.get('Fibras', 0):.1f}", body_style)
            ])
        t = Table(table_data, colWidths=[100, 150, 45, 45, 45, 45, 45, 35])
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')), ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1'))]))
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

    story = [Paragraph(f"<b>Detalle Diario de Ingestas - {fecha_str}</b>", title_style), Paragraph(f"<b>Usuario Telegram ID:</b> {user_id}", body_style), HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=10)]

    if not df_diario.empty:
        table_data = [[Paragraph("Momento", header_style), Paragraph("Alimento / Detalle", header_style), Paragraph("Peso", header_style), Paragraph("Kcal", header_style), Paragraph("Prot", header_style), Paragraph("Gras", header_style), Paragraph("Carb", header_style), Paragraph("Fibr", header_style)]]
        for _, r in df_diario.iterrows():
            table_data.append([
                Paragraph(str(r.get('Momento', '')), body_style), Paragraph(str(r.get('Alimento', '')), body_style),
                Paragraph(f"{r.get('Peso', 0):.1f}g", body_style), Paragraph(f"{r.get('Calorias', 0):.1f}", body_style),
                Paragraph(f"{r.get('Proteinas', 0):.1f}g", body_style), Paragraph(f"{r.get('Grasas', 0):.1f}g", body_style),
                Paragraph(f"{r.get('Carbohidratos', 0):.1f}g", body_style), Paragraph(f"{r.get('Fibras', 0):.1f}g", body_style)
            ])
        t = Table(table_data, colWidths=[70, 160, 45, 45, 45, 45, 45, 45])
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')), ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1'))]))
        story.append(t)

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

    story = [Paragraph(f"<b>Detalle Diario de Presión Arterial - {mes_str}</b>", title_style), Paragraph(f"<b>Usuario Telegram ID:</b> {user_id}", body_style), HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=10)]

    if not df_presion.empty:
        table_data = [[Paragraph("Fecha y Hora", header_style), Paragraph("Alta (mmHg)", header_style), Paragraph("Baja (mmHg)", header_style), Paragraph("Pulsaciones (lpm)", header_style)]]
        for _, r in df_presion.iterrows():
            table_data.append([Paragraph(str(r.get('Fecha_Hora', '')), body_style), Paragraph(f"{r.get('Alta', 0):.0f}", body_style), Paragraph(f"{r.get('Baja', 0):.0f}", body_style), Paragraph(f"{r.get('Pulsaciones', 0):.0f}", body_style)])
        t = Table(table_data, colWidths=[180, 100, 100, 120])
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')), ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1'))]))
        story.append(t)

    doc.build(story)
    buffer.seek(0)
    return buffer

def generar_pdf_resumen_bytes(mes_str, df_mes, df_presion, perfil, tmb_val, recomendacion, user_id):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1E3A8A'), spaceAfter=4)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8, leading=11, textColor=colors.HexColor('#1E293B'))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)

    story = [Paragraph(f"<b>Reporte Nutricional Mensual - {mes_str}</b>", title_style), Paragraph(f"<b>Usuario Telegram ID:</b> {user_id}", body_style), HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=8)]

    headers_h1 = ["Fecha", "Cal. Consumid.", "Cal. Quemad.", "Bal. Neto", "Proteinas (g)", "Grasas (g)", "Carbohidratos (g)", "Fibras (g)"]
    table_data_h1 = [[Paragraph(h, header_style) for h in headers_h1]]

    if not df_mes.empty:
        fechas_unicas = sorted(df_mes['Fecha'].unique())
        for f in fechas_unicas:
            sub = df_mes[df_mes['Fecha'] == f]
            c_cons = sub[sub['Calorias'] > 0]['Calorias'].sum()
            c_quem = abs(sub[sub['Calorias'] < 0]['Calorias'].sum())
            b_neto = c_cons - c_quem
            table_data_h1.append([
                Paragraph(str(f), body_style), Paragraph(f"{c_cons:.1f} kcal", body_style),
                Paragraph(f"{c_quem:.1f} kcal", body_style), Paragraph(f"{b_neto:.1f} kcal", body_style),
                Paragraph(f"{sub['Proteinas'].sum():.1f} g", body_style), Paragraph(f"{sub['Grasas'].sum():.1f} g", body_style),
                Paragraph(f"{sub['Carbohidratos'].sum():.1f} g", body_style), Paragraph(f"{sub['Fibras'].sum():.1f} g", body_style)
            ])

    t1 = Table(table_data_h1, colWidths=[65, 75, 70, 70, 65, 60, 80, 55])
    t1.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')), ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1'))]))
    story.append(t1)

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
        alimento_str = item.get('alimento', item.get('nombre', '')).replace('§', '').strip()

        if mult != 1.0:
            txt += f"**{idx}. {alimento_str}** ({peso_total:.1f}g) (x{mult}): `{cal_total:.1f} kcal`\n"
        else:
            txt += f"**{idx}. {alimento_str}** ({peso_total:.1f}g): `{cal_total:.1f} kcal`\n"

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
        "📌 Funciones y Comandos Disponibles:\n"
        "• `/comidas`: Visualiza listado y descarga PDF.\n"
        "• `/presion 120,80,70`: Registra presión.\n"
        "• `/diario`: Ingestas del día y PDF.\n"
        "• `/resumen`: Reporte mensual e IA.\n"
        "• `/perfil`: Consulta o carga datos biométricos.\n"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
    pdf_buf = generar_pdf_instrucciones_bytes()
    await context.bot.send_document(chat_id=update.effective_chat.id, document=pdf_buf, filename="Manual_Bot_Nutricional.pdf")

async def cmd_comidas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plantillas = obtener_plantillas_comidas()
    if not plantillas:
        await update.message.reply_text("📋 No hay comidas predeterminadas registradas.")
        return

    txt = "📋 **Listado de Comidas Predeterminadas:**\n\n"
    for p in plantillas:
        txt += f"• **{p.get('Nombre', '')}**: {p.get('Descripcion') or p.get('Momento', '')}\n"

    await update.message.reply_text(txt, parse_mode="Markdown")
    pdf_bytes = generar_pdf_comidas_bytes(plantillas)
    await context.bot.send_document(chat_id=update.effective_chat.id, document=pdf_bytes, filename="Comidas_Predeterminadas.pdf")

async def cmd_actividad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto = update.message.text.replace('/actividad', '').strip()
    if not texto:
        await update.message.reply_text("⚠️ Por favor ingresá la actividad. Ejemplo: `/actividad caminata, 250 cal`", parse_mode="Markdown")
        return

    parte_calorias = texto.split(',')[-1] if ',' in texto else texto
    solo_numeros = re.sub(r'\D', '', parte_calorias)
    if not solo_numeros:
        await update.message.reply_text("❌ No se detectaron las calorías.", parse_mode="Markdown")
        return

    calorias_neg = -abs(float(solo_numeros))
    fecha_actual = obtener_ahora_arg().strftime("%Y-%m-%d")
    items = [{"alimento": texto, "peso": 0.0, "calorias": calorias_neg, "proteinas": 0.0, "grasas": 0.0, "carbohidratos": 0.0, "fibras": 0.0}]
    guardar_en_sheets(user_id, items, fecha_actual, "Actividad Física", tipo="Actividad")
    await update.message.reply_text(f"✅ Actividad registrada: `{texto}` ({calorias_neg:.0f} kcal)", parse_mode="Markdown")

async def actividad_ia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not client_ai:
        await update.message.reply_text("❌ Groq API Key no configurada.")
        return

    texto_input = update.message.text.replace('/actividadia', '').replace('/actividad_ia', '').strip()
    if not texto_input:
        await update.message.reply_text("⚠️ Ejemplo: `/actividadia caminata rápida 45 min`", parse_mode="Markdown")
        return

    msg_espera = await update.message.reply_text("⏳ Analizando actividad física con IA...")
    try:
        prompt = f"El usuario realizó: '{texto_input}'. Estima el gasto calórico. Respondé JSON: {{\"actividad\": \"Nombre\", \"calorias\": 250}}"
        chat_completion = client_ai.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        respuesta = json.loads(chat_completion.choices[0].message.content)
        actividad_nombre = respuesta.get("actividad", texto_input)
        calorias = abs(int(respuesta.get("calorias", 0)))

        keyboard = [[
            InlineKeyboardButton("✅ Guardar", callback_data=f"save_act_{calorias}_{actividad_nombre[:15]}"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel_act")
        ]]
        await msg_espera.edit_text(f"🏃 **Actividad:** {actividad_nombre}\n🔥 **Gasto:** -{calorias} kcal", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await msg_espera.edit_text("❌ Error al procesar la actividad.")

cmd_actividad_ia = actividad_ia

async def cmd_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Hoy", callback_data="diario_hoy"), InlineKeyboardButton("📆 Ayer", callback_data="diario_ayer")],
        [InlineKeyboardButton("🗓️ Seleccionar Fecha", callback_data="diario_otro")]
    ])
    await update.message.reply_text("📅 **Consulta de Diario:** Seleccioná una opción:", reply_markup=keyboard, parse_mode="Markdown")

async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ahora = obtener_ahora_arg()
    mes_actual = ahora.strftime("%Y-%m")
    mes_anterior = (ahora.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Mes Actual", callback_data=f"resumen_mes_{mes_actual}")],
        [InlineKeyboardButton("📆 Mes Anterior", callback_data=f"resumen_mes_{mes_anterior}")],
        [InlineKeyboardButton("🗓️ Otro Mes", callback_data="resumen_mes_otro")]
    ])
    await update.message.reply_text("📊 **Resumen Mensual:** Seleccioná la opción:", reply_markup=keyboard, parse_mode="Markdown")

async def cmd_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw_text = update.message.text.replace('/perfil', '').strip()
    mes_actual = obtener_ahora_arg().strftime("%Y-%m")

    if raw_text:
        try:
            nuevo_peso = float(raw_text.replace(',', '.'))
            perfil = obtener_perfil_usuario(user_id, mes_target=mes_actual) or {}
            edad = parse_raw_val(perfil.get('Edad', 64))
            altura = parse_raw_val(perfil.get('Altura', 170))
            genero = str(perfil.get('Sexo', 'masculino'))
            ocupacion = str(perfil.get('Ocupacion', 'Jubilado'))
            guardar_perfil_en_sheets(user_id, edad, nuevo_peso, altura, genero, ocupacion, mes_actual)
            await update.message.reply_text(f"✅ Peso actualizado a `{nuevo_peso}` kg.", parse_mode="Markdown")
            return
        except ValueError:
            pass

    perfil = obtener_perfil_usuario(user_id, mes_target=mes_actual)
    if perfil:
        await update.message.reply_text(f"👤 **Perfil:**\n• Peso: `{perfil.get('Peso')}` kg\n• Altura: `{perfil.get('Altura')}` cm", parse_mode="Markdown")
    else:
        await update.message.reply_text("👤 Perfil no registrado. Usá: `/perfil EDAD, PESO, ALTURA, GENERO, OCUPACION`", parse_mode="Markdown")

async def cmd_presion_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw_text = update.message.text.replace('/presion', '').strip()
    if not raw_text:
        await update.message.reply_text("🩺 Uso: `/presion 120,80,70` o `/presion 2026-08`", parse_mode="Markdown")
        return
    parts = [p.strip() for p in raw_text.split(',') if p.strip()]
    if len(parts) >= 2:
        guardar_presion_en_sheets(user_id, float(parts[0]), float(parts[1]), float(parts[2]) if len(parts) > 2 else None)
        await update.message.reply_text("✅ Presión registrada exitosamente.", parse_mode="Markdown")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🎙️ Procesando audio con IA...")
    try:
        file = await context.bot.get_file(update.message.voice.file_id)
        audio_bytes = await file.download_as_bytearray()
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.ogg"
        transcription = client_ai.audio.transcriptions.create(file=(audio_file.name, audio_file.read()), model="whisper-large-v3", response_format="text")
        data = analizar_con_groq(transcription)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        await msg.edit_text(f"❌ Error al procesar audio: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📸 Analizando foto con IA...")
    try:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        data = analizar_imagen_con_groq(base64.b64encode(photo_bytes).decode('utf-8'))
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        await msg.edit_text(f"❌ Error al procesar imagen: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw_text = update.message.text.strip()

    if raw_text.startswith('/'):
        cmd = raw_text.split()[0].lower()
        if cmd == '/start': await cmd_start(update, context)
        elif cmd == '/comidas': await cmd_comidas(update, context)
        elif cmd == '/diario': await cmd_diario(update, context)
        elif cmd == '/resumen': await cmd_resumen(update, context)
        elif cmd == '/perfil': await cmd_perfil(update, context)
        elif cmd.startswith('/presi'): await cmd_presion_handler(update, context)
        elif cmd == '/actividad': await cmd_actividad(update, context)
        elif cmd in ['/actividadia', '/actividad_ia']: await cmd_actividad_ia(update, context)
        return

    msg = await update.message.reply_text("⏳ Analizando alimento con IA...")
    try:
        data = analizar_con_groq(raw_text)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        await msg.edit_text(f"❌ Error al procesar texto: {e}")

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

# ==========================================
# CALLBACK HANDLER (BOTONES INTERACTIVOS)
# ==========================================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "confirm_save":
        items = context.user_data.get('pending_items', [])
        fecha = context.user_data.get('pending_fecha')
        momento = context.user_data.get('pending_momento')
        tipo = context.user_data.get('pending_tipo', 'Comida')
        
        if items:
            guardar_en_sheets(user_id, items, fecha, momento, tipo)
            await query.edit_message_text("✅ **¡Ingesta guardada exitosamente en Google Sheets!**", parse_mode="Markdown")
            context.user_data.clear()
        else:
            await query.edit_message_text("⚠️ No había items para guardar.")

    elif data == "cancel_entry":
        context.user_data.clear()
        await query.edit_message_text("❌ Registro cancelado y descartado.")

    elif data.startswith("set_m_"):
        context.user_data['pending_momento'] = data.replace("set_m_", "")
        await render_confirmation_screen(query, context)

    elif data == "set_d_hoy":
        context.user_data['pending_fecha'] = obtener_ahora_arg().strftime("%Y-%m-%d")
        await render_confirmation_screen(query, context)

    elif data == "set_d_ayer":
        context.user_data['pending_fecha'] = (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d")
        await render_confirmation_screen(query, context)

    elif data.startswith("save_act_"):
        parts = data.split("_")
        cal = float(parts[2])
        act_nombre = "_".join(parts[3:])
        fecha = obtener_ahora_arg().strftime("%Y-%m-%d")
        items = [{"alimento": act_nombre, "peso": 0, "calorias": -cal, "proteinas": 0, "grasas": 0, "carbohidratos": 0, "fibras": 0}]
        guardar_en_sheets(user_id, items, fecha, "Actividad Física", tipo="Actividad")
        await query.edit_message_text(f"✅ Actividad registrada: **{act_nombre}** (-{cal:.0f} kcal)", parse_mode="Markdown")

    elif data == "cancel_act":
        await query.edit_message_text("❌ Registro de actividad cancelado.")

# ==========================================
# INICIALIZACIÓN DEL BOT Y FLASK
# ==========================================
if __name__ == '__main__':
    # Iniciar servidor Flask en hilo secundario
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Configuración de Telegram Bot
    if TELEGRAM_TOKEN:
        app_telegram = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

        app_telegram.add_handler(CommandHandler("start", cmd_start))
        app_telegram.add_handler(CommandHandler("comidas", cmd_comidas))
        app_telegram.add_handler(CommandHandler("diario", cmd_diario))
        app_telegram.add_handler(CommandHandler("resumen", cmd_resumen))
        app_telegram.add_handler(CommandHandler("perfil", cmd_perfil))
        app_telegram.add_handler(CommandHandler("presion", cmd_presion_handler))
        app_telegram.add_handler(CommandHandler("actividad", cmd_actividad))
        app_telegram.add_handler(CommandHandler("actividadia", cmd_actividad_ia))
        
        app_telegram.add_handler(MessageHandler(filters.VOICE, handle_voice))
        app_telegram.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        app_telegram.add_handler(CallbackQueryHandler(callback_handler))

        print("🤖 Bot de Telegram en ejecución...")
        app_telegram.run_polling()
    else:
        print("⚠️ TELEGRAM_BOT_TOKEN no está definido. El bot de Telegram no fue iniciado.")
