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
from flask import Flask

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

# Servidor Flask para Web Service en Render
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot Nutricional activo y funcionando.", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# Estados de conversación para Perfil y Fecha personalizada
AWAITING_PROFILE_DATA, AWAITING_CUSTOM_DATE, AWAITING_RESUMEN_MES = range(3)

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
    return num / 1000.0 if num > 5000 else num

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

def calcular_tmb(peso, altura, edad, genero="masculino"):
    # Fórmula de Harris-Benedict
    if genero.lower() in ["femenino", "f", "mujer"]:
        return 655 + (9.6 * peso) + (1.8 * altura) - (4.7 * edad)
    return 66 + (13.7 * peso) + (5 * altura) - (6.8 * edad)

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
            ws = spreadsheet.add_worksheet(title=title, rows="10", cols="5")
            ws.append_row(["Edad", "Peso", "Altura", "Genero", "Fecha_Actualizacion"])
            return ws
        elif title == "Plantillas_Comidas":
            ws = spreadsheet.add_worksheet(title=title, rows="100", cols="8")
            ws.append_row(["Nombre", "Momento", "Peso", "Calorias", "Proteinas", "Grasas", "Carbohidratos", "Fibras"])
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
    ws.append_row([ahora.strftime("%Y-%m-%d %H:%M:%S"), ahora.strftime("%Y-%m-%d"), alta, baja, pulsaciones])

def guardar_perfil_en_sheets(user_id, edad, peso, altura, genero="masculino"):
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    ws = get_or_create_worksheet(sh, f"Perfil_{user_id}")
    ahora = obtener_ahora_arg()
    ws.append_row([edad, peso, altura, genero, ahora.strftime("%Y-%m-%d %H:%M:%S")])

def obtener_perfil_usuario(user_id):
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws = get_or_create_worksheet(sh, f"Perfil_{user_id}")
        records = ws.get_all_records()
        if not records:
            return None
        return records[-1] # Devolver la última actualización
    except Exception:
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
        return pd.DataFrame(records)
    except Exception:
        return pd.DataFrame()

def obtener_plantillas_comidas():
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws = get_or_create_worksheet(sh, "Plantillas_Comidas")
        return ws.get_all_records()
    except Exception:
        return []

# ==========================================
# PROCESAMIENTO IA (TEXTO, VOZ Y FOTO)
# ==========================================
def analizar_con_groq(prompt_text):
    if not client_ai:
        raise Exception("GROQ_API_KEY no está configurada correctamente.")
    system_prompt = (
        "Sos un nutricionista experto. Analizá el texto ingresado.\n"
        "Devolvé EXCLUSIVAMENTE un JSON con este formato:\n"
        "{\n"
        '  "items": [\n'
        '    {"alimento": "nombre", "peso": 0.0, "calorias": 0.0, "proteinas": 0.0, "grasas": 0.0, "carbohidratos": 0.0, "fibras": 0.0}\n'
        '  ],\n'
        '  "tipo": "Comida"\n'
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
    prompt = f"Basado en este resumen de ingesta mensual y métricas del paciente, da una recomendación nutricional breve, profesional y motivadora (máximo 4 oraciones):\n\n{resumen_texto}"
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
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1E3A8A'))
    section_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#2563EB'), spaceBefore=8)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8.5, leading=12, textColor=colors.HexColor('#1E293B'))

    story = [
        Paragraph("<b>MANUAL DE USO COMPLETO - BOT NUTRICIONAL</b>", title_style),
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=8),
        Paragraph("<b>1. Comandos Principales</b>", section_style),
        Paragraph("• <b>/start</b>: Inicia el bot y reenvía este PDF informativo.", body_style),
        Paragraph("• <b>/comidas</b>: Ver listado de comidas predeterminadas y plantilla en PDF.", body_style),
        Paragraph("• <b>/presion</b>: Registrar mediciones de presión arterial (Ej: <code>/presion 120,80,70</code>).", body_style),
        Paragraph("• <b>/diario</b>: Consultar consumos del día u otra fecha.", body_style),
        Paragraph("• <b>/resumen</b>: Obtener el resumen mensual con cálculo de TMB, presión y recomendaciones.", body_style),
        Paragraph("• <b>/perfil</b>: Actualizar o consultar datos biométricos corporales.", body_style),
        Paragraph("<b>2. Entrada de Datos</b>", section_style),
        Paragraph("• <b>Texto:</b> Ingresá libremente tus alimentos o nombrá una plantilla predeterminada (Ej: <code>*DESAYUNO</code>).", body_style),
        Paragraph("• <b>Voz:</b> Grabá un audio describiendo lo consumido.", body_style),
        Paragraph("• <b>Foto:</b> Enviá una foto de tu plato para análisis con inteligencia artificial.", body_style),
    ]
    doc.build(story)
    buffer.seek(0)
    return buffer

def generar_pdf_comidas_bytes(plantillas):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1E3A8A'))
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.HexColor('#1E293B'))

    story = [
        Paragraph("<b>LISTADO DE COMIDAS PREDETERMINADAS</b>", title_style),
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=12),
    ]

    if not plantillas:
        story.append(Paragraph("No hay comidas predeterminadas cargadas en la hoja 'Plantillas_Comidas'.", body_style))
    else:
        table_data = [["Nombre", "Momento", "Peso (g)", "Kcal", "Prot (g)", "Gras (g)", "Carb (g)", "Fibr (g)"]]
        for p in plantillas:
            table_data.append([
                str(p.get("Nombre", "")),
                str(p.get("Momento", "")),
                str(p.get("Peso", "")),
                str(p.get("Calorias", "")),
                str(p.get("Proteinas", "")),
                str(p.get("Grasas", "")),
                str(p.get("Carbohidratos", "")),
                str(p.get("Fibras", ""))
            ])
        
        t = Table(table_data, colWidths=[90, 65, 50, 50, 50, 50, 50, 50])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
        ]))
        story.append(t)

    doc.build(story)
    buffer.seek(0)
    return buffer

def generar_pdf_resumen_bytes(mes_str, df_mes, df_presion, perfil, tmb_val, recomendacion):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1E3A8A'))
    sub_style = ParagraphStyle('SubTitle', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#2563EB'), spaceBefore=8)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=9, leading=13, textColor=colors.HexColor('#1E293B'))

    total_kcal = df_mes['Calorias'].sum() if not df_mes.empty else 0
    dias_activos = df_mes['Fecha'].nunique() if not df_mes.empty else 0
    prom_diario = total_kcal / dias_activos if dias_activos > 0 else 0

    story = [
        Paragraph(f"<b>RESUMEN NUTRICIONAL Y SALUD - MES {mes_str}</b>", title_style),
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=10),
        Paragraph("<b>Datos Biométricos y TMB</b>", sub_style)
    ]

    if perfil:
        story.append(Paragraph(f"• Edad: {perfil.get('Edad', 'N/A')} años | Peso: {perfil.get('Peso', 'N/A')} kg | Altura: {perfil.get('Altura', 'N/A')} cm", body_style))
        story.append(Paragraph(f"• <b>Tasa de Metabolismo Basal (TMB):</b> {tmb_val:.0f} kcal/día", body_style))
    else:
        story.append(Paragraph("• Perfil biométrico no configurado. Usá /perfil para registrar tus datos.", body_style))

    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>Consumo Nutricional del Mes</b>", sub_style))
    story.append(Paragraph(f"• Días Activos Registrados: {dias_activos}", body_style))
    story.append(Paragraph(f"• Calorías Totales Acumuladas: {total_kcal:.0f} kcal", body_style))
    story.append(Paragraph(f"• Promedio Diario: {prom_diario:.0f} kcal/día", body_style))

    if not df_presion.empty:
        story.append(Spacer(1, 8))
        story.append(Paragraph("<b>Presión Arterial Registrada</b>", sub_style))
        alta_prom = df_presion['Alta'].apply(parse_raw_val).mean()
        baja_prom = df_presion['Baja'].apply(parse_raw_val).mean()
        pul_prom = df_presion['Pulsaciones'].apply(parse_raw_val).mean()
        story.append(Paragraph(f"• Promedio Presión: {alta_prom:.0f}/{baja_prom:.0f} mmHg | Pulsaciones Promedio: {pul_prom:.0f} bpm", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Recomendación de Inteligencia Artificial</b>", sub_style))
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
        txt += f"**{idx}. {item['alimento']}** ({item.get('peso',0)}g): `{item.get('calorias',0)} kcal`\n"

    keyboard = []
    
    # Fila 1: Selección de Momento
    m_buttons = []
    for m in ["Desayuno", "Almuerzo", "Merienda", "Cena"]:
        mark = "✅ " if m.lower() == momento.lower() else ""
        m_buttons.append(InlineKeyboardButton(f"{mark}{m}", callback_data=f"set_m_{m}"))
    keyboard.append(m_buttons)

    # Filas de Items
    for idx, item in enumerate(items):
        keyboard.append([
            InlineKeyboardButton(f"Item #{idx+1}", callback_data="noop"),
            InlineKeyboardButton("🗑️ Anular", callback_data=f"del_item_{idx}")
        ])

    # Fila de Días
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

    # Fila final
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
        "📌 Funciones disponibles:\n"
        "• /comidas: Ver el listado de comidas predeterminadas y descargar PDF.\n"
        "• /presion: Registrar mediciones de presión arterial (sistólica, diastólica y pulsaciones).\n"
        "• /diario: Consultar consumos del día u otra fecha.\n"
        "• /resumen: Obtener el resumen mensual con cálculo histórico de TMB, promedio de presión y recomendaciones de IA.\n"
        "• /perfil: Actualizar datos biométricos corporales.\n\n"
        "📄 Te adjuntamos el manual de instrucciones actualizado en PDF."
    )
    await update.message.reply_text(msg)
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
        txt += f"• **{p.get('Nombre')}** ({p.get('Momento')}): `{p.get('Calorias')} kcal` | `{p.get('Peso')}g`\n"

    txt += "\n📄 Te adjuntamos el archivo en PDF a continuación."
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
                edad = int(parts[0])
                peso = float(parts[1].replace(',', '.'))
                altura = float(parts[2].replace(',', '.'))
                genero = parts[3] if len(parts) > 3 else "masculino"
                guardar_perfil_en_sheets(user_id, edad, peso, altura, genero)
                tmb = calcular_tmb(peso, altura, edad, genero)
                await update.message.reply_text(
                    f"✅ **Perfil actualizado correctamente:**\n"
                    f"• Edad: `{edad}` años\n• Peso: `{peso}` kg\n• Altura: `{altura}` cm\n"
                    f"• **TMB Calculada:** `{tmb:.0f} kcal/día`",
                    parse_mode="Markdown"
                )
                return
            except ValueError:
                await update.message.reply_text("❌ Error en los datos ingresados. Asegurate de usar números válidos.")
                return

    perfil = obtener_perfil_usuario(user_id)
    if perfil:
        tmb = calcular_tmb(parse_raw_val(perfil.get('Peso')), parse_raw_val(perfil.get('Altura')), parse_raw_val(perfil.get('Edad')), str(perfil.get('Genero','masculino')))
        txt = (
            f"👤 **Perfil Biométrico Actual:**\n\n"
            f"• Edad: `{perfil.get('Edad')}` años\n"
            f"• Peso: `{perfil.get('Peso')}` kg\n"
            f"• Altura: `{perfil.get('Altura')}` cm\n"
            f"• Genero: `{perfil.get('Genero', 'masculino')}`\n"
            f"• **TMB Estimada:** `{tmb:.0f} kcal/día`\n\n"
            f"Para actualizar tus datos envía:\n`/perfil EDAD, PESO, ALTURA, GENERO` (Ej: `/perfil 64, 110, 172, masculino`)"
        )
    else:
        txt = "👤 **Perfil no registrado.** Para ingresar tus datos biométricos usá:\n`/perfil EDAD, PESO, ALTURA, GENERO` (Ej: `/perfil 64, 110, 172, masculino`)"

    await update.message.reply_text(txt, parse_mode="Markdown")

async def cmd_presion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw_text = update.message.text.replace('/presion', '').strip()
    
    if raw_text:
        parts = [p.strip() for p in raw_text.replace('/', ',').replace(' ', ',').split(',') if p.strip()]
        if len(parts) >= 3:
            guardar_presion_en_sheets(user_id, parts[0], parts[1], parts[2])
            await update.message.reply_text(f"✅ **Presión registrada:**\nAlta: `{parts[0]}` | Baja: `{parts[1]}` | Pulsaciones: `{parts[2]}`", parse_mode="Markdown")
            return
        else:
            await update.message.reply_text("❌ Formato incorrecto. Uso: `/presion 120,80,70` o `/presion 12,75,65`", parse_mode="Markdown")
            return

    await update.message.reply_text("🩺 Ingresá la presión con el comando seguido de los valores. Ejemplo:\n`/presion 120,80,70`", parse_mode="Markdown")

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
    msg = await update.message.reply_text("📸 Analizando foto con Qwen Vision...")
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

    # Procesar fecha ingresada manualmente para Diario o Confirmación
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

    # 1. EVALUACIÓN DE COMANDOS EXPLÍCITOS
    if raw_text.startswith('/'):
        cmd = raw_text.split()[0].lower()
        if cmd == '/presion':
            await cmd_presion(update, context)
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

    # 2. EVALUACIÓN DE PLANTILLAS Y PLANTILLA DIRECTA (*DESAYUNO, ETC)
    plantillas = obtener_plantillas_comidas()
    clean_text = raw_text.replace('*', '').strip().upper()

    # Buscar coincidencia exacta con nombre de plantilla
    coincidencia = None
    if plantillas:
        for p in plantillas:
            if str(p.get("Nombre", "")).strip().upper() == clean_text:
                coincidencia = p
                break

    if coincidencia:
        fecha_auto, momento_auto = obtener_momento_y_fecha_auto()
        item = {
            "alimento": coincidencia.get("Nombre"),
            "peso": parse_raw_val(coincidencia.get("Peso")),
            "calorias": parse_raw_val(coincidencia.get("Calorias")),
            "proteinas": parse_raw_val(coincidencia.get("Proteinas")),
            "grasas": parse_raw_val(coincidencia.get("Grasas")),
            "carbohidratos": parse_raw_val(coincidencia.get("Carbohidratos")),
            "fibras": parse_raw_val(coincidencia.get("Fibras"))
        }
        context.user_data['pending_items'] = [item]
        context.user_data['pending_tipo'] = "Comida"
        context.user_data['pending_fecha'] = fecha_auto
        context.user_data['pending_momento'] = coincidencia.get("Momento", momento_auto)
        
        msg = await update.message.reply_text("🔍 Plantilla localizada con éxito...")
        await render_confirmation_screen(msg, context)
        return

    # SI EMPIEZA CON * Y NO SE ENCONTRÓ EN EL EXCEL, SE DESCARTA EL INGRESO
    if raw_text.startswith('*'):
        await update.message.reply_text(f"❌ La plantilla `{raw_text}` no fue encontrada en Excel. Registro descartado.", parse_mode="Markdown")
        return

    # 3. PROCESAR CON IA SI NO FUE PLANTILLA
    msg = await update.message.reply_text("⏳ Analizando alimento con IA...")
    try:
        data = analizar_con_groq(raw_text)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        await msg.edit_text(f"❌ Error al procesar el texto: {e}")

async def procesar_y_mostrar_confirmacion(data, msg, context):
    items = data.get("items", [])
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

    elif data == "resumen_mes_otro":
        await query.edit_message_text("🗓️ Por favor enviá el mes que querés consultar en formato `YYYY-MM` (Ej: `2026-07`):", parse_mode="Markdown")
        context.user_data['awaiting_resumen_date'] = True

    elif data.startswith("resumen_mes_"):
        mes_str = data.replace("resumen_mes_", "")
        await mostrar_resumen_mes(query, user_id, mes_str)

    elif data.startswith("descargar_pdf_resumen_"):
        mes_str = data.replace("descargar_pdf_resumen_", "")
        await generar_y_enviar_pdf_resumen(query, user_id, mes_str, context)

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
            total_kcal = df_filtrado['Calorias'].sum()
            for _, r in df_filtrado.iterrows():
                txt += f"• **{r.get('Momento','Comida')}**: {r.get('Alimento','Item')} ({r.get('Peso',0):.0f}g) -> `{r.get('Calorias',0):.0f} kcal`\n"
            txt += f"\n🔥 **Total Calorías:** `{total_kcal:.0f} kcal`"

    if hasattr(query_or_update, 'edit_message_text'):
        await query_or_update.edit_message_text(txt, parse_mode="Markdown")
    else:
        await query_or_update.message.reply_text(txt, parse_mode="Markdown")

async def mostrar_resumen_mes(query_or_update, user_id, mes_str):
    df = obtener_datos_usuario(user_id)
    perfil = obtener_perfil_usuario(user_id)
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

    total_kcal = df_mes['Calorias'].sum()
    dias_activos = df_mes['Fecha'].nunique()
    prom_diario = total_kcal / dias_activos if dias_activos > 0 else 0

    tmb_val = 0
    if perfil:
        tmb_val = calcular_tmb(parse_raw_val(perfil.get('Peso')), parse_raw_val(perfil.get('Altura')), parse_raw_val(perfil.get('Edad')), str(perfil.get('Genero','masculino')))

    txt = f"📊 **Resumen Mensual Completo ({mes_str}):**\n\n"
    txt += f"• **Días registrados:** `{dias_activos}`\n"
    txt += f"• **Calorías Totales:** `{total_kcal:.0f} kcal`\n"
    txt += f"• **Promedio Diario:** `{prom_diario:.0f} kcal/día`\n"
    
    if tmb_val > 0:
        txt += f"• **TMB Estimada:** `{tmb_val:.0f} kcal/día`\n"

    if not df_presion.empty:
        df_p_mes = df_presion[df_presion['Fecha_Dia'].str.startswith(mes_str)] if 'Fecha_Dia' in df_presion.columns else pd.DataFrame()
        if not df_p_mes.empty:
            alta_prom = df_p_mes['Alta'].apply(parse_raw_val).mean()
            baja_prom = df_p_mes['Baja'].apply(parse_raw_val).mean()
            txt += f"• **Presión Promedio:** `{alta_prom:.0f}/{baja_prom:.0f} mmHg`\n"

    resumen_para_ia = f"Mes: {mes_str}, Dias activos: {dias_activos}, Promedio diario: {prom_diario:.0f} kcal, TMB: {tmb_val:.0f} kcal"
    rec_ia = obtener_recomendacion_ia(resumen_para_ia)
    txt += f"\n💡 **Recomendación IA:**\n_{rec_ia}_"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Descargar PDF Resumen", callback_data=f"descargar_pdf_resumen_{mes_str}")]
    ])

    if hasattr(query_or_update, 'edit_message_text'):
        await query_or_update.edit_message_text(txt, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await query_or_update.message.reply_text(txt, reply_markup=keyboard, parse_mode="Markdown")

async def generar_y_enviar_pdf_resumen(query, user_id, mes_str, context):
    df = obtener_datos_usuario(user_id)
    perfil = obtener_perfil_usuario(user_id)
    df_presion = obtener_datos_presion(user_id)
    
    df_mes = df[df['Fecha'].str.startswith(mes_str)] if not df.empty else pd.DataFrame()
    
    tmb_val = 0
    if perfil:
        tmb_val = calcular_tmb(parse_raw_val(perfil.get('Peso')), parse_raw_val(perfil.get('Altura')), parse_raw_val(perfil.get('Edad')), str(perfil.get('Genero','masculino')))

    rec_ia = obtener_recomendacion_ia(f"Resumen del mes {mes_str} para usuario {user_id}")
    
    pdf_bytes = generar_pdf_resumen_bytes(mes_str, df_mes, df_presion, perfil, tmb_val, rec_ia)
    
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

    # Iniciar Flask en hilo separado para Render
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Iniciar bot de Telegram
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("comidas", cmd_comidas))
    application.add_handler(CommandHandler("perfil", cmd_perfil))
    application.add_handler(CommandHandler("presion", cmd_presion))
    application.add_handler(CommandHandler("diario", cmd_diario))
    application.add_handler(CommandHandler("resumen", cmd_resumen))
    
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))

    application.run_polling()

if __name__ == "__main__":
    main()
