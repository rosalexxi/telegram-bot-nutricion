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

ARG_TZ = pytz.timezone('America/Argentina/Buenos_Aires')
client_ai = Groq(api_key=GROQ_API_KEY)

app = Flask(__name__)

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
            ws = spreadsheet.add_worksheet(title=title, rows="500", cols="10")
            ws.append_row(["Fecha", "Momento/Actividad", "Alimento/Detalle", "Peso (g)", "Calorías (kcal)", "Proteínas (g)", "Grasas (g)", "Hidratos (g)", "Fibras (g)"])
            return ws
        elif title.startswith("Presion_"):
            ws = spreadsheet.add_worksheet(title=title, rows="200", cols="5")
            ws.append_row(["Fecha_Hora", "Fecha_Dia", "Alta", "Baja", "Pulsaciones"])
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

def obtener_datos_dia(user_id, fecha_str):
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
            df = df[df['Fecha'] == fecha_str]
            for col in ['Peso', 'Calorias', 'Proteinas', 'Grasas', 'Carbohidratos', 'Fibras']:
                if col in df.columns:
                    df[col] = df[col].apply(parse_float_from_sheets)
                else:
                    df[col] = 0.0
        return df
    except Exception as e:
        print(f"Error al obtener datos: {e}")
        return pd.DataFrame()

# ==========================================
# PROCESAMIENTO IA (TEXTO, VOZ Y FOTO)
# ==========================================
def analizar_con_groq(prompt_text):
    system_prompt = (
        "Sos un nutricionista experto. Analizá el texto ingresado.\n"
        "Devolvé EXCLUSIVAMENTE un JSON con este formato:\n"
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

def analizar_imagen_con_groq(base64_image):
    prompt = "Analizá esta imagen de comida/plato. Identificá los alimentos, estimá sus pesos en gramos y nutrientes. Respondé ÚNICAMENTE en formato JSON con la clave 'items' conteniendo alimento, peso, calorias, proteinas, grasas, carbohidratos, fibras."
    response = client_ai.chat.completions.create(
        model="llama-3.2-11b-vision-preview",
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
# PDF COMPLETO DE INSTRUCCIONES
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
        Paragraph("• <b>/comidas</b>: Muestra las comidas predeterminadas y descarga el catálogo PDF.", body_style),
        Paragraph("• <b>/presion</b>: Permite ingresar datos de presión arterial directamente (Ej: <code>/presion 12,75,65</code>) o abriendo el menú interactivo.", body_style),
        Paragraph("• <b>/diario</b>: Consulta lo ingerido hoy, ayer o seleccioná una fecha específica.", body_style),
        Paragraph("• <b>/resumen</b>: Muestra estadísticas mensuales, promedios de macronutrientes y estimación de TMB.", body_style),
        Paragraph("• <b>/perfil</b>: Configura tus datos biométricos.", body_style),
        Paragraph("<b>2. Entrada por Voz, Foto y Texto</b>", section_style),
        Paragraph("• <b>Texto:</b> Escribí libremente lo que comiste (Ej: <i>2 huevos revueltos con 1 tostada</i>).", body_style),
        Paragraph("• <b>Voz:</b> Enviá un mensaje de voz describiendo tu comida.", body_style),
        Paragraph("• <b>Foto:</b> Enviá una foto de tu plato para que la IA estime los gramos y nutrientes.", body_style),
    ]
    doc.build(story)
    buffer.seek(0)
    return buffer

# ==========================================
# HANDLERS DE TELEGRAM
# ==========================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "👋 **Bienvenido a tu Bot Nutricional.**\n\nConsultá el manual adjunto con el detalle completo de comandos."
    await update.message.reply_text(msg, parse_mode="Markdown")
    pdf_buf = generar_pdf_instrucciones_bytes()
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=pdf_buf,
        filename="Manual_Bot_Nutricional.pdf"
    )

async def cmd_presion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace('/presion', '').strip()
    if text:
        parts = [p.strip() for p in text.replace('/', ',').split(',') if p.strip()]
        if len(parts) == 3:
            guardar_presion_en_sheets(update.effective_user.id, parts[0], parts[1], parts[2])
            await update.message.reply_text(f"✅ **Presión guardada:** Alta: `{parts[0]}` | Baja: `{parts[1]}` | Pulsaciones: `{parts[2]}`", parse_mode="Markdown")
            return
    await update.message.reply_text("🩺 Ingresá la presión en formato `Alta,Baja,Pulsaciones` (Ej: `120,80,70`):")

async def cmd_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Hoy", callback_data="diario_hoy"), InlineKeyboardButton("📆 Ayer", callback_data="diario_ayer")]
    ])
    await update.message.reply_text("📅 **Seleccioná qué día querés consultar:**", reply_markup=keyboard, parse_mode="Markdown")

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
    msg = await update.message.reply_text("📸 Analizando foto con IA...")
    try:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        base64_image = base64.b64encode(photo_bytes).decode('utf-8')
        
        data = analizar_imagen_con_groq(base64_image)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        await msg.edit_text(f"❌ Error al procesar imagen: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text.strip()
    clean_text = raw_text.replace('*', '').strip()
    
    if clean_text.startswith('/'):
        await update.message.reply_text("❌ Comando no reconocido. Revisa la lista con /comidas.")
        return

    msg = await update.message.reply_text("⏳ Analizando texto con IA...")
    try:
        data = analizar_con_groq(clean_text)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}")

async def procesar_y_mostrar_confirmacion(data, msg, context):
    items = data.get("items", [])
    tipo = data.get("tipo", "Comida")
    fecha_auto, momento_auto = obtener_momento_y_fecha_auto()
    
    context.user_data['pending_items'] = items
    context.user_data['pending_tipo'] = tipo
    context.user_data['pending_fecha'] = fecha_auto
    context.user_data['pending_momento'] = momento_auto
    await render_confirmation_screen(msg, context)

async def render_confirmation_screen(msg_or_query, context):
    items = context.user_data.get('pending_items', [])
    fecha = context.user_data.get('pending_fecha')
    momento = context.user_data.get('pending_momento')

    txt = f"📝 **Confirmar Registro:**\n📅 Fecha: `{fecha}` | Momento: `{momento}`\n\n"
    for item in items:
        txt += f"• **{item['alimento']}** ({item.get('peso',0)}g): `{item.get('calorias',0)} kcal`\n"

    keyboard = [
        [InlineKeyboardButton("✅ Guardar", callback_data="confirm_save"), InlineKeyboardButton("❌ Cancelar", callback_data="cancel_entry")],
        [InlineKeyboardButton("🍽️ Cambiar Momento", callback_data="change_momento")]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    if hasattr(msg_or_query, 'edit_message_text'):
        await msg_or_query.edit_message_text(txt, reply_markup=markup, parse_mode="Markdown")
    else:
        await msg_or_query.edit_text(txt, reply_markup=markup, parse_mode="Markdown")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "confirm_save":
        user_id = query.from_user.id
        guardar_en_sheets(user_id, context.user_data.get('pending_items', []), context.user_data.get('pending_fecha'), context.user_data.get('pending_momento'))
        await query.edit_message_text("✅ ¡Registro guardado exitosamente en Google Sheets!")

    elif data == "cancel_entry":
        await query.edit_message_text("🚫 Registro cancelado.")

    elif data == "diario_hoy":
        fecha = obtener_ahora_arg().strftime("%Y-%m-%d")
        df = obtener_datos_dia(query.from_user.id, fecha)
        if df.empty:
            await query.edit_message_text(f"📅 No hay registros para hoy (`{fecha}`).", parse_mode="Markdown")
        else:
            txt = f"📅 **Registro de Hoy ({fecha}):**\n\n"
            for _, r in df.iterrows():
                txt += f"• **{r['Momento']}**: {r['Alimento']} ({r['Peso']:.0f}g) -> `{r['Calorias']:.0f} kcal`\n"
            await query.edit_message_text(txt, parse_mode="Markdown")

    elif data == "diario_ayer":
        fecha = (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d")
        df = obtener_datos_dia(query.from_user.id, fecha)
        if df.empty:
            await query.edit_message_text(f"📅 No hay registros para ayer (`{fecha}`).", parse_mode="Markdown")
        else:
            txt = f"📅 **Registro de Ayer ({fecha}):**\n\n"
            for _, r in df.iterrows():
                txt += f"• **{r['Momento']}**: {r['Alimento']} ({r['Peso']:.0f}g) -> `{r['Calorias']:.0f} kcal`\n"
            await query.edit_message_text(txt, parse_mode="Markdown")

    elif data == "change_momento":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Desayuno", callback_data="set_m_Desayuno"), InlineKeyboardButton("Almuerzo", callback_data="set_m_Almuerzo")],
            [InlineKeyboardButton("Merienda", callback_data="set_m_Merienda"), InlineKeyboardButton("Cena", callback_data="set_m_Cena")]
        ])
        await query.edit_message_text("Seleccioná el momento de la comida:", reply_markup=keyboard)

    elif data.startswith("set_m_"):
        nuevo_m = data.replace("set_m_", "")
        context.user_data['pending_momento'] = nuevo_m
        await render_confirmation_screen(query, context)

# ==========================================
# MAIN
# ==========================================
def main():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("presion", cmd_presion))
    application.add_handler(CommandHandler("diario", cmd_diario))
    
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))

    application.run_polling()

if __name__ == "__main__":
    main()
