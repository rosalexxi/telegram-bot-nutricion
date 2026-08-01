import os
import re
import io
import json
import base64
from datetime import datetime, date, timedelta, time
import pytz
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from groq import Groq
from dotenv import load_dotenv
from flask import Flask, request, render_template_string
from threading import Thread

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

# Zona Horaria de Argentina
ARG_TZ = pytz.timezone('America/Argentina/Buenos_Aires')

client_ai = Groq(api_key=GROQ_API_KEY)

# ==========================================
# SERVIDOR FLASK (WEB SERVICE PARA RENDER & CONSULTA)
# ==========================================
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Consulta Nutricional - Bot Nutricional</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f6f9; margin: 40px; }
        .container { max-width: 600px; background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin: auto; }
        h2 { color: #1E3A8A; }
        input[type="text"] { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
        button { background-color: #2563EB; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; width: 100%; font-size: 16px; }
        button:hover { background-color: #1D4ED8; }
        .result { margin-top: 20px; background: #EFF6FF; padding: 15px; border-radius: 5px; border-left: 4px solid #2563EB; }
        pre { font-size: 14px; white-space: pre-wrap; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🥗 Consulta de Desglose Nutricional</h2>
        <form method="POST">
            <label for="alimento"><b>Ingresá un alimento o plato:</b></label>
            <input type="text" id="alimento" name="alimento" placeholder="Ej: 200g de pechuga de pollo a la plancha" required value="{{ alimento }}">
            <button type="submit">Consultar Nutrientes</button>
        </form>

        {% if resultado %}
        <div class="result">
            <h3>Resultado del Análisis:</h3>
            <pre>{{ resultado }}</pre>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def home():
    resultado = None
    alimento = ""
    if request.method == 'POST':
        alimento = request.form.get('alimento', '')
        if alimento:
            try:
                res = analizar_con_groq(alimento)
                items = res.get("items", [])
                out = []
                for item in items:
                    out.append(f"• Alimento: {item.get('alimento')}\n"
                               f"  - Peso: {item.get('peso')} g\n"
                               f"  - Calorías: {item.get('calorias')} kcal\n"
                               f"  - Proteínas: {item.get('proteinas')} g\n"
                               f"  - Grasas: {item.get('grasas')} g\n"
                               f"  - Carbohidratos: {item.get('carbohidratos')} g\n"
                               f"  - Fibras: {item.get('fibras')} g")
                resultado = "\n\n".join(out)
            except Exception as e:
                resultado = f"Error al procesar: {e}"
    return render_template_string(HTML_TEMPLATE, resultado=resultado, alimento=alimento)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==========================================
# FUNCIONES AUXILIARES DE TRANSFORMACIÓN (x1000 / /1000)
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
    """ Multiplica x1000 para corregir el formato regional. """
    num = parse_raw_val(val)
    return int(round(num * 1000))

def parse_float_from_sheets(val):
    """ Divide por 1000.0 al leer desde la planilla. """
    num = parse_raw_val(val)
    return num / 1000.0

# ==========================================
# HORARIOS Y FECHAS
# ==========================================
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

# ==========================================
# CONEXIÓN Y OPERACIONES CON GOOGLE SHEETS
# ==========================================
EDAD, SEXO, PESO, ALTURA, CINTURA, OCUPACION = range(6)
PRESION_INPUT = range(1)

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
            ws = spreadsheet.add_worksheet(title=title, rows="500", cols="10")
            ws.append_row(["Fecha", "Momento/Actividad", "Alimento/Detalle", "Peso (g)", "Calorías (kcal)", "Proteínas (g)", "Grasas (g)", "Hidratos (g)", "Fibras (g)"])
            return ws
        elif title.startswith("Perfil"):
            ws = spreadsheet.add_worksheet(title=title, rows="100", cols="8")
            ws.append_row(["Mes_Anio", "Edad", "Sexo", "Peso_g", "Altura_mm", "Cintura_mm", "Ocupacion", "Fecha_Actualizacion"])
            return ws
        elif title.startswith("Presion_"):
            ws = spreadsheet.add_worksheet(title=title, rows="200", cols="5")
            ws.append_row(["Fecha_Hora", "Fecha_Dia", "Alta", "Baja", "Pulsaciones"])
            return ws
        elif title == "Comidas_Predeterminadas":
            ws = spreadsheet.add_worksheet(title=title, rows="200", cols="8")
            ws.append_row(["Codigo", "Alimento", "Peso (g)", "Calorias (kcal)", "Proteinas (g)", "Grasas (g)", "Hidratos (g)", "Fibras (g)"])
            return ws
        else:
            return spreadsheet.add_worksheet(title=title, rows="100", cols="10")

def guardar_en_sheets(user_id, items, fecha, momento, tipo="Comida"):
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    ws = get_or_create_worksheet(sh, f"User_{user_id}")

    rows = []
    for item in items:
        rows.append([
            fecha,
            momento,
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
    fecha_hora = ahora.strftime("%Y-%m-%d %H:%M:%S")
    fecha_dia = ahora.strftime("%Y-%m-%d")
    
    ws.append_row([fecha_hora, fecha_dia, alta, baja, pulsaciones])

def obtener_promedio_presion_mes(user_id, mes_str):
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws = get_or_create_worksheet(sh, f"Presion_{user_id}")
        records = ws.get_all_records()
        if not records:
            return None
        
        df = pd.DataFrame(records)
        if df.empty or 'Fecha_Dia' not in df.columns:
            return None
            
        df = df[df['Fecha_Dia'].astype(str).str.startswith(mes_str)]
        if df.empty:
            return None
            
        prom_alta = df['Alta'].apply(parse_raw_val).mean()
        prom_baja = df['Baja'].apply(parse_raw_val).mean()
        prom_pul = df['Pulsaciones'].apply(parse_raw_val).mean()
        
        return {"alta": round(prom_alta, 1), "baja": round(prom_baja, 1), "pulsaciones": round(prom_pul, 1), "tomas": len(df)}
    except Exception as e:
        print(f"Error al obtener presión: {e}")
        return None

def obtener_datos_mes(user_id, mes_str):
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
            df['Fecha_dt'] = pd.to_datetime(df['Fecha'], errors='coerce')
            df['Fecha'] = df['Fecha_dt'].dt.strftime('%Y-%m-%d').fillna(df['Fecha'].astype(str))
            df = df[df['Fecha'].str.startswith(mes_str)]
            
            for col in ['Peso', 'Calorias', 'Proteinas', 'Grasas', 'Carbohidratos', 'Fibras']:
                if col in df.columns:
                    df[col] = df[col].apply(parse_float_from_sheets)
                else:
                    df[col] = 0.0
                    
        return df
    except Exception as e:
        print(f"Error al obtener datos: {e}")
        return pd.DataFrame()

def obtener_perfil_historico(user_id, mes_str):
    """ Busca en la hoja Perfil_{user_id} el valor biométrico correspondiente al mes del resumen. """
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws = get_or_create_worksheet(sh, f"Perfil_{user_id}")
        records = ws.get_all_records()
        if not records:
            return None
            
        df = pd.DataFrame(records)
        if df.empty:
            return None

        df_mes = df[df['Mes_Anio'].astype(str) == mes_str]
        
        if df_mes.empty:
            # Si no hay del mes exacto, busca el último registro disponible hasta ese mes
            df_mes = df[df['Mes_Anio'].astype(str) <= mes_str]
            if df_mes.empty:
                last_rec = df.iloc[-1].to_dict()
            else:
                last_rec = df_mes.iloc[-1].to_dict()
        else:
            last_rec = df_mes.iloc[-1].to_dict()

        perfil_clean = {}
        for k, v in last_rec.items():
            k_lower = str(k).lower()
            if any(x in k_lower for x in ['peso', 'altura', 'cintura']):
                perfil_clean[k] = parse_float_from_sheets(v)
            else:
                perfil_clean[k] = v
        return perfil_clean
    except Exception as e:
        print(f"Error al obtener perfil histórico: {e}")
        return None

def guardar_perfil(user_id, perfil_dict):
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    ws_perfil = get_or_create_worksheet(sh, f"Perfil_{user_id}")
    mes_actual = obtener_ahora_arg().strftime("%Y-%m")
    
    row_data = [
        mes_actual,
        parse_raw_val(perfil_dict.get("edad", 0)),
        perfil_dict.get("sexo", ""),
        to_sheet_int(perfil_dict.get("peso", 0)),
        to_sheet_int(perfil_dict.get("altura", 0)),
        to_sheet_int(perfil_dict.get("cintura", 0)),
        perfil_dict.get("ocupacion", ""),
        obtener_ahora_arg().strftime("%Y-%m-%d %H:%M:%S")
    ]
    ws_perfil.append_row(row_data)

def calcular_metabolismo(perfil):
    if not perfil:
        return None
    try:
        edad = parse_raw_val(perfil.get("Edad", perfil.get("edad", 0)))
        sexo = str(perfil.get("Sexo", perfil.get("sexo", "M"))).upper()
        peso = parse_raw_val(perfil.get("Peso_kg", perfil.get("peso", perfil.get("Peso_g", 0))))
        altura = parse_raw_val(perfil.get("Altura_cm", perfil.get("altura", perfil.get("Altura_mm", 0))))
        
        if sexo == "M":
            tmb = (10 * peso) + (6.25 * altura) - (5 * edad) + 5
        else:
            tmb = (10 * peso) + (6.25 * altura) - (5 * edad) - 161
            
        get_val = tmb * 1.2
        return {"tmb": round(tmb, 1), "get": round(get_val, 1)}
    except:
        return None

def buscar_comida_predeterminada(alimento_buscado):
    """ Busca en la planilla un alimento exacto registrado en la columna Alimento """
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws = get_or_create_worksheet(sh, "Comidas_Predeterminadas")
        records = ws.get_all_records()
        if not records:
            return None

        norm_target = re.sub(r'\s+', ' ', str(alimento_buscado)).strip().lower()
        items_encontrados = []
        
        for r in records:
            alimento_sheet = str(r.get("Alimento", "")).strip().lower()
            codigo_sheet = str(r.get("Codigo", "")).strip().lower()
            
            if alimento_sheet == norm_target or codigo_sheet == norm_target:
                items_encontrados.append({
                    "alimento": str(r.get("Alimento", "Predeterminado")),
                    "peso": parse_float_from_sheets(r.get("Peso (g)", r.get("Peso", 0))),
                    "calorias": parse_float_from_sheets(r.get("Calorias (kcal)", r.get("Calorias", 0))),
                    "proteinas": parse_float_from_sheets(r.get("Proteinas (g)", r.get("Proteinas", 0))),
                    "grasas": parse_float_from_sheets(r.get("Grasas (g)", r.get("Grasas", 0))),
                    "carbohidratos": parse_float_from_sheets(r.get("Hidratos (g)", r.get("Carbohidratos", 0))),
                    "fibras": parse_float_from_sheets(r.get("Fibras (g)", r.get("Fibras", 0)))
                })

        return items_encontrados if items_encontrados else None
    except Exception as e:
        print(f"Error al consultar comidas predeterminadas: {e}")
        return None

# ==========================================
# PROCESAMIENTO IA (GROQ)
# ==========================================
def analizar_con_groq(prompt_text):
    system_prompt = (
        "Sos un nutricionista y entrenador experto. Analizá el texto del usuario.\n"
        "REGLAS CRÍTICAS DE PARSEO:\n"
        "1. Identifica las CANTIDADES Y UNIDADES indicadas.\n"
        "2. Devolvé los nutrientes en GRAMOS/KCAL estándar como números flotantes puros (ej: 7.5, 42.5).\n"
        "3. Usa el punto '.' como separador decimal.\n"
        "4. Si es ejercicio/actividad física, la caloría DEBE ser negativa (ej: -300.0).\n"
        "Devolvé EXCLUSIVAMENTE un JSON válido con este formato:\n"
        "{\n"
        '  "items": [\n'
        '    {"alimento": "nombre", "peso": 0.0, "calorias": 0.0, "proteinas": 0.0, "grasas": 0.0, "carbohidratos": 0.0, "fibras": 0.0}\n'
        '  ],\n'
        '  "tipo": "Comida" o "Ejercicio"\n'
        "}"
    )
    
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

def generar_recomendacion_nutricional(perfil, proms_diarios):
    prompt = f"""
    Como nutricionista profesional, analizá los siguientes datos diarios promedio alcanzados por un paciente este mes:
    - Edad: {perfil.get('Edad', 'N/A')} años | Sexo: {perfil.get('Sexo', 'N/A')} | Peso: {perfil.get('Peso_kg', perfil.get('peso', 'N/A'))} kg
    - Ingesta calórica promedio diaria: {proms_diarios['calorias']:.0f} kcal
    - Proteínas promedio diarias: {proms_diarios['proteinas']:.1f} g
    - Grasas promedio diarias: {proms_diarios['grasas']:.1f} g
    - Carbohidratos promedio diarios: {proms_diarios['carbohidratos']:.1f} g
    - Fibras promedio diarias: {proms_diarios['fibras']:.1f} g

    Evaluá brevemente si los macronutrientes están equilibrados para una persona con estos datos biométricos.
    Si consume demasiados hidratos, pocas proteínas, etc., dales una sugerencia concisa de qué comidas reforzar o ajustar para equilibrar la dieta. Redactá un párrafo breve y constructivo (máximo 120 palabras).
    """
    try:
        response = client_ai.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return "No se pudo generar la recomendación personalizada."

# ==========================================
# GENERACIÓN DE PDFS (INSTRUCCIONES / COMIDAS / RESUMEN)
# ==========================================
def generar_pdf_instrucciones_bytes():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=18, leading=22, textColor=colors.HexColor('#1E3A8A'), spaceAfter=4)
    subtitle_style = ParagraphStyle('DocSubtitle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#64748B'), spaceAfter=12)
    section_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontSize=12, leading=16, textColor=colors.HexColor('#2563EB'), spaceBefore=10, spaceAfter=6)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=9, leading=13, textColor=colors.HexColor('#1E293B'), spaceAfter=6)
    badge_style = ParagraphStyle('Badge', parent=styles['Normal'], fontSize=8.5, leading=12, textColor=colors.HexColor('#0F172A'))

    story = []
    story.append(Paragraph("<b>MANUAL DE USO COMPLETO Y PROFESIONAL</b>", title_style))
    story.append(Paragraph("<b>Asistente & Bot de Registro Nutricional e Inteligencia Artificial</b>", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=12))

    story.append(Paragraph("<b>1. Registro de Comidas y Ejercicio</b>", section_style))
    story.append(Paragraph("• <b>Carga Directa:</b> Ingresá un alimento que exista en tu planilla <i>Comidas_Predeterminadas</i> para cargarlo sin IA.", body_style))
    story.append(Paragraph("• <b>Lector Inteligente con IA:</b> Podés escribir textos detallados, enviar audios de voz o sacar fotos a tus platos.", body_style))
    story.append(Paragraph("• <b>Control de Presión Arterial:</b> Usá el comando <code>/presion</code> e ingresá tus datos en formato Alta, Baja, Pulsaciones (ej: <code>120,80,72</code>).", body_style))

    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>2. Comandos Principales del Sistema</b>", section_style))
    
    cmd_table_data = [
        [Paragraph("<b>Comando</b>", badge_style), Paragraph("<b>Descripción y Función</b>", badge_style)],
        [Paragraph("<code>/start</code>", badge_style), Paragraph("Inicia el bot y reenvía este manual en formato PDF.", badge_style)],
        [Paragraph("<code>/comidas</code>", badge_style), Paragraph("Lista las comidas prediseñadas en la planilla y genera un PDF descargable.", badge_style)],
        [Paragraph("<code>/presion</code>", badge_style), Paragraph("Registra la toma de presión (sistólica, diastólica y pulsaciones) con fecha y hora.", badge_style)],
        [Paragraph("<code>/diario</code>", badge_style), Paragraph("Consulta lo ingerido el día de hoy, ayer u otra fecha.", badge_style)],
        [Paragraph("<code>/resumen</code>", badge_style), Paragraph("Muestra el informe mensual, comparativa de macronutrientes, presión arterial y descarga el reporte PDF.", badge_style)],
        [Paragraph("<code>/perfil</code>", badge_style), Paragraph("Configura o actualiza tus datos corporales históricos.", badge_style)]
    ]
    t_cmd = Table(cmd_table_data, colWidths=[100, 420])
    t_cmd.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E2E8F0')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_cmd)

    doc.build(story)
    buffer.seek(0)
    return buffer

def generar_pdf_comidas_bytes():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1E3A8A'), spaceAfter=10)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8.5, leading=12)

    story = [Paragraph("<b>Catálogo de Comidas Predeterminadas</b>", title_style)]
    
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws = get_or_create_worksheet(sh, "Comidas_Predeterminadas")
        records = ws.get_all_records()
        
        if records:
            table_data = [["Código", "Alimento", "Peso (g)", "Kcal", "Prot (g)", "Grasas (g)", "Carbs (g)", "Fibra (g)"]]
            for r in records:
                table_data.append([
                    str(r.get("Codigo", "")),
                    str(r.get("Alimento", "")),
                    f"{parse_float_from_sheets(r.get('Peso (g)', 0)):.0f}",
                    f"{parse_float_from_sheets(r.get('Calorias (kcal)', 0)):.0f}",
                    f"{parse_float_from_sheets(r.get('Proteinas (g)', 0)):.1f}",
                    f"{parse_float_from_sheets(r.get('Grasas (g)', 0)):.1f}",
                    f"{parse_float_from_sheets(r.get('Hidratos (g)', 0)):.1f}",
                    f"{parse_float_from_sheets(r.get('Fibras (g)', 0)):.1f}"
                ])
            t = Table(table_data, colWidths=[65, 140, 50, 50, 50, 50, 50, 50])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2563EB')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('ALIGN', (2,0), (-1,-1), 'CENTER')
            ]))
            story.append(t)
        else:
            story.append(Paragraph("No hay comidas predeterminadas registradas.", body_style))
    except Exception as e:
        story.append(Paragraph(f"Error al obtener planilla: {e}", body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ==========================================
# COMANDOS DE TELEGRAM
# ==========================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 **¡Hola, Juan Carlos! Bienvenido a tu Bot Nutricional Personalizado.**\n\n"
        "📌 **Funciones disponibles:**\n"
        "• **/comidas**: Ver el listado de comidas predeterminadas y descargar PDF.\n"
        "• **/presion**: Registrar mediciones de presión arterial (sistólica, diastólica y pulsaciones).\n"
        "• **/diario**: Consultar consumos del día u otra fecha.\n"
        "• **/resumen**: Obtener el resumen mensual con cálculo histórico de TMB, promedio de presión y recomendaciones de IA.\n"
        "• **/perfil**: Actualizar datos biométricos corporales.\n\n"
        "📄 *Te adjuntamos el manual de instrucciones actualizado en PDF.*"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
    
    pdf_buf = generar_pdf_instrucciones_bytes()
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=pdf_buf,
        filename="Guia_de_Uso_Bot_Nutricional.pdf",
        caption="📄 **Manual Completo de Instrucciones**"
    )

async def cmd_comidas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws = get_or_create_worksheet(sh, "Comidas_Predeterminadas")
        records = ws.get_all_records()

        if not records:
            await update.message.reply_text("📋 No se encontraron comidas en la hoja `Comidas_Predeterminadas`.")
            return

        msg = "📋 **Listado de Comidas Predeterminadas Registradas:**\n\n"
        alimentos_vistas = set()
        for r in records:
            alim = str(r.get('Alimento', '')).strip()
            if alim and alim not in alimentos_vistas:
                alimentos_vistas.add(alim)
                p = parse_float_from_sheets(r.get('Peso (g)', 0))
                c = parse_float_from_sheets(r.get('Calorias (kcal)', 0))
                msg += f"• **{alim}** ({p:.0f}g) -> `{c:.0f} kcal`\n"

        await update.message.reply_text(msg, parse_mode="Markdown")

        pdf_buf = generar_pdf_comidas_bytes()
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buf,
            filename="Comidas_Predeterminadas.pdf",
            caption="📄 **Catálogo PDF de Comidas Predeterminadas**"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error al consultar la lista: {e}")

# ==========================================
# REGISTRO DE PRESIÓN ARTERIAL (/PRESION)
# ==========================================
async def start_presion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace('/presion', '').strip()
    if text:
        parts = [p.strip() for p in text.split(',')]
        if len(parts) == 3:
            alta, baja, pul = parts[0], parts[1], parts[2]
            guardar_presion_en_sheets(update.effective_user.id, alta, baja, pul)
            await update.message.reply_text(f"✅ **Presión registrada:** Alta: {alta} | Baja: {baja} | Pulsaciones: {pul}")
            return ConversationHandler.END
    
    await update.message.reply_text("🩺 Por favor, ingresá las 3 medidas separadas por coma (Ej: `120,80,72` para Alta, Baja y Pulsaciones):")
    return PRESION_INPUT

async def set_presion_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    parts = [p.strip() for p in text.split(',')]
    if len(parts) == 3:
        alta, baja, pul = parts[0], parts[1], parts[2]
        guardar_presion_en_sheets(update.effective_user.id, alta, baja, pul)
        await update.message.reply_text(f"✅ **Presión registrada:** Alta: {alta} | Baja: {baja} | Pulsaciones: {pul}")
    else:
        await update.message.reply_text("❌ Formato inválido. Deben ser 3 valores separados por coma (ej: `120,80,72`).")
    return ConversationHandler.END

# ==========================================
# MOSTRAR RESUMEN MENSUAL Y EVALUACIÓN
# ==========================================
async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 Este Mes", callback_data="resumen_estemes"),
            InlineKeyboardButton("📆 Otro Mes", callback_data="resumen_otromes")
        ]
    ])
    await update.message.reply_text("📊 ¿Qué mes querés consultar en el resumen?", reply_markup=keyboard)

async def mostrar_resumen_pantalla(update: Update, context: ContextTypes.DEFAULT_TYPE, mes_str):
    user_id = update.effective_user.id
    df = obtener_datos_mes(user_id, mes_str)
    
    if df.empty:
        await update.message.reply_text(f"📊 No hay datos registrados para el mes `{mes_str}`.", parse_mode="Markdown")
        return

    df['Es_Ejercicio'] = df['Calorias'] < 0
    comidas = df[~df['Es_Ejercicio']]
    ejercicios = df[df['Es_Ejercicio']]

    tot_c_in = comidas['Calorias'].sum()
    tot_c_out = ejercicios['Calorias'].abs().sum()
    tot_p = comidas['Proteinas'].sum()
    tot_g = comidas['Grasas'].sum()
    tot_h = comidas['Carbohidratos'].sum()
    tot_f = comidas['Fibras'].sum()

    dias_cnt = max(df['Fecha'].nunique(), 1)
    proms_diarios = {
        'calorias': tot_c_in / dias_cnt,
        'proteinas': tot_p / dias_cnt,
        'grasas': tot_g / dias_cnt,
        'carbohidratos': tot_h / dias_cnt,
        'fibras': tot_f / dias_cnt
    }

    txt = f"📊 **Resumen Nutricional Mensual ({mes_str})**\n\n"
    txt += f"🗓️ **Días con registros:** {dias_cnt}\n"
    txt += f"📥 **Consumo Total:** {tot_c_in:.0f} kcal (Prom: {proms_diarios['calorias']:.0f} kcal/día)\n"
    txt += f"🔥 **Gasto Ejercicio:** {tot_c_out:.0f} kcal\n\n"
    
    txt += "🥗 **Promedio Diario de Macronutrientes:**\n"
    txt += f"• 💪 Proteínas: `{proms_diarios['proteinas']:.1f} g/día`\n"
    txt += f"• 🥑 Grasas: `{proms_diarios['grasas']:.1f} g/día`\n"
    txt += f"• 🍞 Carbohidratos: `{proms_diarios['carbohidratos']:.1f} g/día`\n"
    txt += f"• 🌾 Fibras: `{proms_diarios['fibras']:.1f} g/día`\n\n"

    # Presión Arterial del mes
    presion_prom = obtener_promedio_presion_mes(user_id, mes_str)
    if presion_prom:
        txt += f"🩺 **Presión Arterial Promedio ({presion_prom['tomas']} tomas):**\n"
        txt += f"• Alta/Baja: `{presion_prom['alta']:.0f} / {presion_prom['baja']:.0f}` | Pulsaciones: `{presion_prom['pulsaciones']:.0f} bpm`\n\n"

    # Pérdida de Peso con Gasto Basal Histórico del mes
    perfil_hist = obtener_perfil_historico(user_id, mes_str)
    if perfil_hist:
        metabol = calcular_metabolismo(perfil_hist)
        if metabol:
            gasto_basal_total = metabol['get'] * dias_cnt
            bal_real = tot_c_in - (gasto_basal_total + tot_c_out)
            peso_est = bal_real / 7700
            txt += "📐 **Estimación Corporal Histórica del Mes:**\n"
            txt += f"• TMB Aplicada: `{metabol['tmb']} kcal/día` (Peso del mes: {perfil_hist.get('Peso_kg', perfil_hist.get('peso', 'N/A'))} kg)\n"
            txt += f"• Balance Neto Real: `{bal_real:+.0f} kcal`\n"
            txt += f"• Estimación descenso/aumento: `{peso_est:+.2f} kg` ({peso_est*1000:+.0f} g)\n\n"

        # Consejo personalizado de IA
        recom = generar_recomendacion_nutricional(perfil_hist, proms_diarios)
        txt += f"💡 **Evaluación y Consejo Nutricional (IA):**\n_{recom}_\n"

    if update.callback_query:
        await update.callback_query.edit_message_text(txt, parse_mode="Markdown")
    else:
        await update.message.reply_text(txt, parse_mode="Markdown")

# ==========================================
# MANEJO DE ENTRADAS GENERALES
# ==========================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    
    # Búsqueda en comidas predeterminadas
    items_pred = buscar_comida_predeterminada(user_text)
    if items_pred:
        msg = await update.message.reply_text("⚡ Alimento detectado en planilla predeterminada...")
        data = {"items": items_pred, "tipo": "Comida"}
        await procesar_y_mostrar_confirmacion(data, msg, context)
        return

    # Si no está en predeterminadas y parece comando o no existe
    if user_text.startswith('/') or user_text.startswith('*'):
        await update.message.reply_text("❌ Comando o alimento no reconocido. Revisa la lista con /comidas.")
        return

    # Interpretación general con IA
    msg = await update.message.reply_text("⏳ Analizando con IA...")
    try:
        data = analizar_con_groq(user_text)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        await msg.edit_text(f"❌ Error al interpretar: {e}")

async def procesar_y_mostrar_confirmacion(data, msg, context):
    items = data.get("items", [])
    tipo = data.get("tipo", "Comida")
    if not items:
        await msg.edit_text("No se detectaron alimentos válidos.")
        return

    fecha_auto, momento_auto = obtener_momento_y_fecha_auto()
    context.user_data['pending_items'] = items
    context.user_data['pending_tipo'] = tipo
    context.user_data['pending_fecha'] = fecha_auto
    context.user_data['pending_momento'] = momento_auto if tipo == "Comida" else "Ejercicio"
    await render_confirmation_screen(msg, context)

async def render_confirmation_screen(msg_or_query, context):
    items = context.user_data.get('pending_items', [])
    tipo = context.user_data.get('pending_tipo', 'Comida')
    fecha = context.user_data.get('pending_fecha', obtener_ahora_arg().strftime("%Y-%m-%d"))
    momento = context.user_data.get('pending_momento', 'Almuerzo')

    txt_res = f"📝 **Confirmar Registro ({tipo}):**\n📅 Fecha: `{fecha}` | Momento: `{momento}`\n\n"
    tot_c = 0.0
    for idx, item in enumerate(items):
        c = parse_raw_val(item.get('calorias', 0))
        tot_c += c
        txt_res += f"• **{item['alimento']}** ({item.get('peso',0)}g): {c:.0f} kcal\n"
        
    keyboard = [
        [InlineKeyboardButton("✅ Guardar Todo", callback_data="confirm_save"), InlineKeyboardButton("❌ Cancelar", callback_data="cancel_entry")]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    if hasattr(msg_or_query, 'edit_message_text'):
        await msg_or_query.edit_message_text(txt_res, reply_markup=markup, parse_mode="Markdown")
    else:
        await msg_or_query.edit_text(txt_res, reply_markup=markup, parse_mode="Markdown")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "confirm_save":
        user_id = query.from_user.id
        items = context.user_data.get('pending_items', [])
        tipo = context.user_data.get('pending_tipo', 'Comida')
        fecha = context.user_data.get('pending_fecha', obtener_ahora_arg().strftime("%Y-%m-%d"))
        momento = context.user_data.get('pending_momento', 'Almuerzo')

        guardar_en_sheets(user_id, items, fecha, momento, tipo)
        context.user_data.pop('pending_items', None)
        await query.edit_message_text(f"✅ ¡Guardado en Google Sheets con exito!")

    elif data == "cancel_entry":
        context.user_data.pop('pending_items', None)
        await query.edit_message_text("🚫 Registro cancelado.")

    elif data == "resumen_estemes":
        mes_actual = obtener_ahora_arg().strftime("%Y-%m")
        await mostrar_resumen_pantalla(update, context, mes_actual)

# ==========================================
# CONFIGURACIÓN DE PERFIL CORPORAL
# ==========================================
async def start_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚙️ **Configuración de Perfil Corporal**\n\n1️⃣ ¿Cuál es tu **edad**?")
    return EDAD

async def set_edad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['perfil_edad'] = update.message.text.strip()
    await update.message.reply_text("2️⃣ ¿Sexo? (M / F)")
    return SEXO

async def set_sexo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['perfil_sexo'] = update.message.text.strip().upper()
    await update.message.reply_text("3️⃣ ¿Peso actual en kg?")
    return PESO

async def set_peso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['perfil_peso'] = update.message.text.strip()
    await update.message.reply_text("4️⃣ ¿Altura en cm?")
    return ALTURA

async def set_altura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['perfil_altura'] = update.message.text.strip()
    await update.message.reply_text("5️⃣ ¿Cintura en cm?")
    return CINTURA

async def set_cintura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['perfil_cintura'] = update.message.text.strip()
    await update.message.reply_text("6️⃣ ¿Ocupación o nivel de actividad diario?")
    return OCUPACION

async def set_ocupacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['perfil_ocupacion'] = update.message.text.strip()
    user_id = update.effective_user.id
    
    perfil_dict = {
        "edad": context.user_data.get('perfil_edad'),
        "sexo": context.user_data.get('perfil_sexo'),
        "peso": context.user_data.get('perfil_peso'),
        "altura": context.user_data.get('perfil_altura'),
        "cintura": context.user_data.get('perfil_cintura'),
        "ocupacion": context.user_data.get('perfil_ocupacion')
    }
    
    guardar_perfil(user_id, perfil_dict)
    await update.message.reply_text("✅ ¡Perfil actualizado correctamente!")
    return ConversationHandler.END

# ==========================================
# MAIN
# ==========================================
def main():
    keep_alive()
    
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    perfil_handler = ConversationHandler(
        entry_points=[CommandHandler('perfil', start_perfil)],
        states={
            EDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_edad)],
            SEXO: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_sexo)],
            PESO: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_peso)],
            ALTURA: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_altura)],
            CINTURA: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_cintura)],
            OCUPACION: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_ocupacion)],
        },
        fallbacks=[]
    )

    presion_handler = ConversationHandler(
        entry_points=[CommandHandler('presion', start_presion)],
        states={
            PRESION_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_presion_input)]
        },
        fallbacks=[]
    )

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("comidas", cmd_comidas))
    application.add_handler(CommandHandler("resumen", cmd_resumen))
    application.add_handler(perfil_handler)
    application.add_handler(presion_handler)
    
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == "__main__":
    main()
