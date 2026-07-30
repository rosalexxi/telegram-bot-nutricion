import os
import re
import io
import json
import base64
import asyncio
from datetime import datetime, date, timedelta
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from groq import Groq
from dotenv import load_dotenv
import httpx
from flask import Flask, request, jsonify, render_template_string
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

# PDF ReportLab
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_SHEETS_KEY_PATH = os.getenv("GOOGLE_SHEETS_KEY_PATH", "credentials.json")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "Registro_Nutricional_Bot")

client_ai = Groq(api_key=GROQ_API_KEY)

# ==========================================
# SERVIDOR FLASK CON WEB APP INTERACTIVA
# ==========================================
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Estado del Bot Nutricional</title>
    <style>
        body { font-family: sans-serif; background: #f8fafc; padding: 40px; text-align: center; }
        .card { background: white; padding: 30px; border-radius: 12px; display: inline-block; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .status { color: #22c55e; font-weight: bold; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Bot Nutricional activo 🚀</h1>
        <p class="status">● En línea y funcionando</p>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==========================================
# BASE DE DATOS Y GOOGLE SHEETS
# ==========================================
EDAD, SEXO, PESO, ALTURA, CINTURA, OCUPACION = range(6)
EDIT_FOOD = 10

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
            ws = spreadsheet.add_worksheet(title=title, rows="200", cols="9")
            ws.append_row(["Fecha", "Momento", "Alimento/Ejercicio", "Calorias", "Proteinas_g", "Grasas_g", "Carbohidratos_g", "Fibras_g", "Observaciones"])
            return ws
        elif title.startswith("Perfil_"):
            ws = spreadsheet.add_worksheet(title=title, rows="100", cols="8")
            ws.append_row(["Mes", "Edad", "Sexo", "Peso_kg", "Altura_cm", "Cintura_cm", "Ocupacion", "Fecha_Actualizacion"])
            return ws
        else:
            return spreadsheet.add_worksheet(title=title, rows="100", cols="9")

def guardar_en_sheets(user_id, items, fecha, momento, observaciones=""):
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    ws = get_or_create_worksheet(sh, f"User_{user_id}")
    
    rows = []
    for item in items:
        rows.append([
            fecha,
            momento,
            item.get("alimento", "Desconocido"),
            float(item.get("calorias", 0)),
            float(item.get("proteinas", 0)),
            float(item.get("grasas", 0)),
            float(item.get("carbohidratos", 0)),
            float(item.get("fibras", 0)),
            observaciones
        ])
    if rows:
        ws.append_rows(rows)

def obtener_datos_mes(user_id, mes_str):
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws_user = get_or_create_worksheet(sh, f"User_{user_id}")
        records = ws_user.get_all_records()
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        if "Fecha" in df.columns and not df.empty:
            df['Fecha'] = df['Fecha'].astype(str)
            df = df[df['Fecha'].str.startswith(mes_str)]
        return df
    except Exception as e:
        print(f"Error al obtener datos: {e}")
        return pd.DataFrame()

def obtener_perfil(user_id, mes_str):
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws_perfil = get_or_create_worksheet(sh, f"Perfil_{user_id}")
        records = ws_perfil.get_all_records()
        if not records:
            return None
        df = pd.DataFrame(records)
        df_mes = df[df['Mes'] == mes_str]
        if not df_mes.empty:
            return df_mes.iloc[-1].to_dict()
        return df.iloc[-1].to_dict()
    except Exception as e:
        return None

def guardar_perfil(user_id, perfil_dict):
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    ws_perfil = get_or_create_worksheet(sh, f"Perfil_{user_id}")
    mes_actual = date.today().strftime("%Y-%m")
    records = ws_perfil.get_all_records()
    
    row_data = [
        mes_actual,
        perfil_dict.get("edad", ""),
        perfil_dict.get("sexo", ""),
        perfil_dict.get("peso", ""),
        perfil_dict.get("altura", ""),
        perfil_dict.get("cintura", ""),
        perfil_dict.get("ocupacion", ""),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ]
    
    if records:
        df = pd.DataFrame(records)
        if "Mes" in df.columns and mes_actual in df['Mes'].values:
            idx = df[df['Mes'] == mes_actual].index[-1] + 2
            ws_perfil.update(f"A{idx}:H{idx}", [row_data])
            return
            
    ws_perfil.append_row(row_data)

def calcular_metabolismo(perfil):
    if not perfil:
        return None
    try:
        edad = float(perfil.get("Edad", 0))
        sexo = str(perfil.get("Sexo", "M")).upper()
        peso = float(perfil.get("Peso_kg", 0))
        altura = float(perfil.get("Altura_cm", 0))
        
        if sexo == "M":
            tmb = (10 * peso) + (6.25 * altura) - (5 * edad) + 5
        else:
            tmb = (10 * peso) + (6.25 * altura) - (5 * edad) - 161
            
        get_val = tmb * 1.15
        return {"tmb": round(tmb, 1), "get": round(get_val, 1)}
    except:
        return None

# ==========================================
# PROCESAMIENTO CON GROQ (IA)
# ==========================================
def analizar_con_groq(prompt_text):
    system_prompt = (
        "Sos un nutricionista experto. Analizá el texto y extraé los alimentos o ejercicios.\n"
        "Devolvé EXCLUSIVAMENTE un JSON con este formato:\n"
        "{\n"
        '  "items": [\n'
        '    {"alimento": "nombre", "calorias": 0.0, "proteinas": 0.0, "grasas": 0.0, "carbohidratos": 0.0, "fibras": 0.0}\n'
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
        temperature=0.2,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

def analizar_imagen_con_groq(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    system_prompt = (
        "Identifica los alimentos en esta imagen y estima sus nutrientes.\n"
        "Devolvé EXCLUSIVAMENTE un JSON estructurado de esta manera:\n"
        "{\n"
        '  "items": [\n'
        '    {"alimento": "nombre estimativo", "calorias": 0.0, "proteinas": 0.0, "grasas": 0.0, "carbohidratos": 0.0, "fibras": 0.0}\n'
        '  ],\n'
        '  "tipo": "Comida"\n'
        "}"
    )
    
    response = client_ai.chat.completions.create(
        model="llama-3.2-11b-vision-preview",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": system_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
        ],
        temperature=0.2,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

# ==========================================
# COMANDOS BÁSICOS TELEGRAM (/start, /help, /diario)
# ==========================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 **¡Hola! Bienvenido a tu Bot de Registro Nutricional.**\n\n"
        "Podés utilizar el bot de las siguientes maneras:\n"
        "1️⃣ **Registrar comidas:** Escribí lo que comiste (ej: *'1 milanesa con ensalada y 1 manzana'*).\n"
        "2️⃣ **Enviar Foto:** Sacale una foto a tu plato de comida y enviámela.\n"
        "3️⃣ **Registrar Ejercicio:** Escribí la actividad (ej: *'Caminé 45 minutos'*).\n\n"
        "📌 **Comandos Disponibles:**\n"
        "• /perfil - Configurar tus datos biométricos\n"
        "• /diario - Ver lo que consumiste hoy\n"
        "• /resumen - Ver el balance mensual y descargar el informe en PDF"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)

async def cmd_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    fecha_hoy = date.today().strftime("%Y-%m-%d")
    mes_actual = date.today().strftime("%Y-%m")
    
    df = obtener_datos_mes(user_id, mes_actual)
    
    if df.empty or "Fecha" not in df.columns:
        await update.message.reply_text("📋 No tenés registros anotados en el día de hoy.")
        return
        
    df_hoy = df[df['Fecha'] == fecha_hoy]
    
    if df_hoy.empty:
        await update.message.reply_text(f"📋 No tenés registros anotados para hoy ({fecha_hoy}).")
        return
        
    res = f"📅 **Registro Diario de Hoy ({fecha_hoy}):**\n\n"
    tot_c = tot_p = tot_g = tot_h = tot_f = 0
    
    for _, r in df_hoy.iterrows():
        c = float(r.get('Calorias', 0))
        p = float(r.get('Proteinas_g', 0))
        g = float(r.get('Grasas_g', 0))
        h = float(r.get('Carbohidratos_g', 0))
        f = float(r.get('Fibras_g', 0))
        
        tot_c += c; tot_p += p; tot_g += g; tot_h += h; tot_f += f
        res += f"• [{r.get('Momento', 'General')}] **{r.get('Alimento/Ejercicio', 'Item')}**\n"
        res += f"  └ {c:.0f} kcal | P: {p:.1f}g | G: {g:.1f}g | H: {h:.1f}g | Fib: {f:.1f}g\n"
        
    res += f"\n🔥 **Totales del día:** {tot_c:.0f} kcal\n"
    res += f"💪 Prot: {tot_p:.1f}g | 🥑 Grasas: {tot_g:.1f}g | 🍞 Carb: {tot_h:.1f}g | 🌾 Fib: {tot_f:.1f}g"
    
    await update.message.reply_text(res, parse_mode="Markdown")

# ==========================================
# MANEJO DE MENSAJES Y FOTOS
# ==========================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    msg = await update.message.reply_text("⏳ Analizando tu registro...")
    
    try:
        data = analizar_con_groq(user_text)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        await msg.edit_text(f"❌ Ocurrió un error al procesar el mensaje: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📸 Analizando la imagen de tu comida...")
    try:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        data = analizar_imagen_con_groq(photo_bytes)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        await msg.edit_text(f"❌ No pude analizar la imagen correctamente: {e}")

async def procesar_y_mostrar_confirmacion(data, msg, context):
    items = data.get("items", [])
    tipo = data.get("tipo", "Comida")
    
    if not items:
        await msg.edit_text("No pude identificar alimentos ni ejercicios en tu envío.")
        return

    context.user_data['pending_items'] = items
    context.user_data['pending_tipo'] = tipo
    context.user_data['pending_fecha'] = date.today().strftime("%Y-%m-%d")
    context.user_data['pending_momento'] = "Almuerzo" if tipo == "Comida" else "Ejercicio"
    
    txt_res = f"📝 **Reconocimiento ({tipo}):**\n\n"
    tot_c = tot_p = tot_g = tot_h = tot_f = 0
    
    for item in items:
        c = item.get('calorias', 0)
        p = item.get('proteinas', 0)
        g = item.get('grasas', 0)
        h = item.get('carbohidratos', 0)
        f = item.get('fibras', 0)
        tot_c += c; tot_p += p; tot_g += g; tot_h += h; tot_f += f
        txt_res += f"• **{item['alimento']}**:\n  └ {c} kcal | P: {p}g | G: {g}g | H: {h}g | Fib: {f}g\n"
        
    txt_res += f"\n🔥 **Totales:** {tot_c} kcal\n"
    
    keyboard = [
        [
            InlineKeyboardButton("🌅 Desayuno", callback_data="mom_Desayuno"),
            InlineKeyboardButton("☀️ Almuerzo", callback_data="mom_Almuerzo"),
            InlineKeyboardButton("🌆 Merienda", callback_data="mom_Merienda")
        ],
        [
            InlineKeyboardButton("🌙 Cena", callback_data="mom_Cena"),
            InlineKeyboardButton("🍏 Colación", callback_data="mom_Colación"),
            InlineKeyboardButton("🏋️ Ejercicio", callback_data="mom_Ejercicio")
        ],
        [
            InlineKeyboardButton("📅 Hoy", callback_data="fec_hoy"),
            InlineKeyboardButton("⏮️ Ayer", callback_data="fec_ayer")
        ],
        [
            InlineKeyboardButton("✅ Confirmar y Guardar", callback_data="confirm_save"),
            InlineKeyboardButton("❌ Descartar", callback_data="cancel_save")
        ]
    ]
    
    await msg.edit_text(txt_res, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# ==========================================
# BOTONES E INTERACCIÓN DE CONFIRMACIÓN
# ==========================================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data.startswith("mom_"):
        momento = data.split("_")[1]
        context.user_data['pending_momento'] = momento
        await query.answer(f"Seleccionado: {momento}")
        
    elif data == "fec_hoy":
        context.user_data['pending_fecha'] = date.today().strftime("%Y-%m-%d")
        await query.answer("Fecha: Hoy")
        
    elif data == "fec_ayer":
        context.user_data['pending_fecha'] = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        await query.answer("Fecha: Ayer")
        
    elif data == "confirm_save":
        items = context.user_data.get('pending_items', [])
        fecha = context.user_data.get('pending_fecha', date.today().strftime("%Y-%m-%d"))
        momento = context.user_data.get('pending_momento', 'General')
        user_id = query.from_user.id
        
        if items:
            guardar_en_sheets(user_id, items, fecha, momento)
            await query.edit_message_text(f"✅ **¡Guardado exitosamente!**\n\n📅 Fecha: `{fecha}`\n🍽️ Momento: `{momento}`", parse_mode="Markdown")
        else:
            await query.edit_message_text("No había elementos pendientes para guardar.")
            
    elif data == "cancel_save":
        context.user_data.pop('pending_items', None)
        await query.edit_message_text("❌ Registro cancelado.")

# ==========================================
# /PERFIL (CONVERSACIÓN)
# ==========================================
async def start_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📐 Vamos a actualizar tu perfil biométrico.\n\nPor favor, ingresá tu **edad** en años (ej: `45`):", parse_mode="Markdown")
    return EDAD

async def set_edad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_edad'] = update.message.text.strip()
    await update.message.reply_text("👤 Ingresá tu **sexo** (`M` para masculino, `F` para femenino):", parse_mode="Markdown")
    return SEXO

async def set_sexo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_sexo'] = update.message.text.strip().upper()
    await update.message.reply_text("⚖️ Ingresá tu **peso actual en kg** (ej: `75.5`):", parse_mode="Markdown")
    return PESO

async def set_peso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_peso'] = update.message.text.strip()
    await update.message.reply_text("📏 Ingresá tu **altura en cm** (ej: `165`):", parse_mode="Markdown")
    return ALTURA

async def set_altura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_altura'] = update.message.text.strip()
    await update.message.reply_text("📐 Ingresá la medida de tu **cintura en cm** (ej: `85`):", parse_mode="Markdown")
    return CINTURA

async def set_cintura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_cintura'] = update.message.text.strip()
    await update.message.reply_text("💼 Ingresá tu **ocupación / nivel de actividad** (ej: `Oficina`, `Ama de casa`):", parse_mode="Markdown")
    return OCUPACION

async def set_ocupacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_ocupacion'] = update.message.text.strip()
    user_id = update.effective_user.id
    
    perfil = {
        "edad": context.user_data.get('p_edad'),
        "sexo": context.user_data.get('p_sexo'),
        "peso": context.user_data.get('p_peso'),
        "altura": context.user_data.get('p_altura'),
        "cintura": context.user_data.get('p_cintura'),
        "ocupacion": context.user_data.get('p_ocupacion')
    }
    
    guardar_perfil(user_id, perfil)
    await update.message.reply_text("✅ **¡Perfil biométrico actualizado exitosamente!**", parse_mode="Markdown")
    return ConversationHandler.END

async def cancel_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END

# ==========================================
# /RESUMEN Y PDF
# ==========================================
def generar_pdf_bytes(user_id, mes_str, df, perfil, metabol):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor('#1E3A8A'), spaceAfter=15)
    sub_style = ParagraphStyle('SubTitle', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#2563EB'), spaceAfter=10)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10, leading=14, spaceAfter=6)

    story = [Paragraph(f"<b>Reporte Nutricional Mensual - {mes_str}</b>", title_style), Spacer(1, 10)]
    
    if perfil and metabol:
        story.append(Paragraph("<b>1. Análisis Biométrico y Metabolismo</b>", sub_style))
        perfil_text = (
            f"<b>Sexo:</b> {perfil.get('Sexo', 'N/A')} | <b>Edad:</b> {perfil.get('Edad', 'N/A')} años | "
            f"<b>Peso:</b> {perfil.get('Peso_kg', 'N/A')} kg | <b>Altura:</b> {perfil.get('Altura_cm', 'N/A')} cm<br/>"
            f"<b>Medida Cintura:</b> {perfil.get('Cintura_cm', 'N/A')} cm | <b>Ocupación:</b> {perfil.get('Ocupacion', 'N/A')}<br/>"
            f"<b>Metabolismo Basal (TMB):</b> {metabol['tmb']} kcal/día<br/>"
            f"<b>Gasto Energético Total Conservador (GET):</b> {metabol['get']} kcal/día"
        )
        story.append(Paragraph(perfil_text, body_style))
        story.append(Spacer(1, 15))
        
    story.append(Paragraph("<b>2. Resumen de Ingesta y Balance</b>", sub_style))
    
    tot_cal = df['Calorias'].sum() if not df.empty and 'Calorias' in df.columns else 0
    tot_prot = df['Proteinas_g'].sum() if not df.empty and 'Proteinas_g' in df.columns else 0
    tot_gras = df['Grasas_g'].sum() if not df.empty and 'Grasas_g' in df.columns else 0
    tot_carb = df['Carbohidratos_g'].sum() if not df.empty and 'Carbohidratos_g' in df.columns else 0
    tot_fib = df['Fibras_g'].sum() if not df.empty and 'Fibras_g' in df.columns else 0
    dias_count = df['Fecha'].nunique() if not df.empty and 'Fecha' in df.columns else 1
    
    bal_text = (
        f"<b>Días Registrados:</b> {dias_count}<br/>"
        f"<b>Total Consumido:</b> {tot_cal:.1f} kcal<br/>"
        f"<b>Proteínas:</b> {tot_prot:.1f} g | <b>Grasas:</b> {tot_gras:.1f} g | <b>Carbohidratos:</b> {tot_carb:.1f} g | <b>Fibras:</b> {tot_fib:.1f} g"
    )
    story.append(Paragraph(bal_text, body_style))
    story.append(Spacer(1, 15))
    
    if not df.empty:
        story.append(Paragraph("<b>3. Desglose de Registros</b>", sub_style))
        table_data = [["Fecha", "Momento", "Descripción", "Kcal", "Prot", "Gras", "Carb", "Fib"]]
        
        for _, r in df.head(50).iterrows():
            table_data.append([
                str(r.get("Fecha", "")),
                str(r.get("Momento", ""))[:10],
                str(r.get("Alimento/Ejercicio", ""))[:20],
                f"{r.get('Calorias', 0):.0f}",
                f"{r.get('Proteinas_g', 0):.0f}",
                f"{r.get('Grasas_g', 0):.0f}",
                f"{r.get('Carbohidratos_g', 0):.0f}",
                f"{r.get('Fibras_g', 0):.0f}"
            ])
            
        t = Table(table_data, colWidths=[60, 55, 150, 40, 40, 40, 40, 40])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 8),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F3F4F6')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D1D5DB')),
            ('FONTSIZE', (0,1), (-1,-1), 8),
        ]))
        story.append(t)
        
    doc.build(story)
    buffer.seek(0)
    return buffer

async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mes_actual = date.today().strftime("%Y-%m")
    
    df = obtener_datos_mes(user_id, mes_actual)
    perfil = obtener_perfil(user_id, mes_actual)
    metabol = calcular_metabolismo(perfil)
    
    dias = df['Fecha'].nunique() if not df.empty and 'Fecha' in df.columns else 0
    tot_cal = df['Calorias'].sum() if not df.empty and 'Calorias' in df.columns else 0
    tot_prot = df['Proteinas_g'].sum() if not df.empty and 'Proteinas_g' in df.columns else 0
    tot_gras = df['Grasas_g'].sum() if not df.empty and 'Grasas_g' in df.columns else 0
    tot_carb = df['Carbohidratos_g'].sum() if not df.empty and 'Carbohidratos_g' in df.columns else 0
    tot_fib = df['Fibras_g'].sum() if not df.empty and 'Fibras_g' in df.columns else 0
    
    resumen_text = f"📊 **Reporte Nutricional Mensual ({mes_actual})**\n\n"
    resumen_text += f"📅 Días registrados: {dias}\n"
    resumen_text += f"🔥 Total consumido: {tot_cal:.0f} kcal\n"
    resumen_text += f"💪 Prot: {tot_prot:.0f}g | 🥑 Grasas: {tot_gras:.0f}g | 🍞 Carb: {tot_carb:.0f}g | 🌾 Fib: {tot_fib:.0f}g\n\n"
    
    if perfil and metabol:
        resumen_text += "—— **Análisis Metabólico** ——\n"
        resumen_text += f"👤 Sexo: {perfil.get('Sexo')} | Edad: {perfil.get('Edad')}a | Peso: {perfil.get('Peso_kg')}kg | Altura: {perfil.get('Altura_cm')}cm\n"
        resumen_text += f"🔥 Metabolismo Basal (TMB): {metabol['tmb']} kcal/día\n"
        resumen_text += f"⚡ Gasto Energético Conservador (GET): {metabol['get']} kcal/día\n\n"
        
        dias_calculo = dias if dias > 0 else 1
        gasto_total = metabol['get'] * dias_calculo
        balance = tot_cal - gasto_total
        cambio_peso = balance / 7700
        
        resumen_text += "📊 **Resumen de Balance y Cambio Corporal Estimado:**\n"
        resumen_text += f"• Total Consumido: {tot_cal:.0f} kcal\n"
        resumen_text += f"• Total Gasto ({dias_calculo} días): -{gasto_total:.1f} kcal\n"
        resumen_text += f"🔥 **BALANCE NETO:** {balance:.1f} kcal\n"
        resumen_text += f"⚖️ **CAMBIO ESTIMADO DE PESO:** {cambio_peso:.2f} kg\n"
    else:
        resumen_text += "\n💡 *Tip: Completá tu perfil con /perfil para ver tu balance metabólico.*"
        
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Descargar Reporte PDF", callback_data="generate_pdf")]
    ])
    
    await update.message.reply_text(resumen_text, parse_mode="Markdown", reply_markup=keyboard)

async def callback_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == "generate_pdf":
        await query.answer("Generando PDF...")
        await query.message.reply_text("📄 Preparando tu documento PDF...")
        
        user_id = query.from_user.id
        mes_actual = date.today().strftime("%Y-%m")
        df = obtener_datos_mes(user_id, mes_actual)
        perfil = obtener_perfil(user_id, mes_actual)
        metabol = calcular_metabolismo(perfil)
        
        pdf_bytes = generar_pdf_bytes(user_id, mes_actual, df, perfil, metabol)
        
        await query.message.reply_document(
            document=pdf_bytes,
            filename=f"Reporte_Nutricional_{mes_actual}.pdf",
            caption=f"📄 Aquí tienes tu reporte nutricional en PDF para {mes_actual}."
        )

# ==========================================
# MAIN
# ==========================================
def main():
    keep_alive()
    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    perfil_handler = ConversationHandler(
        entry_points=[CommandHandler("perfil", start_perfil)],
        states={
            EDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_edad)],
            SEXO: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_sexo)],
            PESO: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_peso)],
            ALTURA: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_altura)],
            CINTURA: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_cintura)],
            OCUPACION: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_ocupacion)],
        },
        fallbacks=[CommandHandler("cancelar", cancel_perfil)]
    )
    
    app_bot.add_handler(CommandHandler("start", cmd_start))
    app_bot.add_handler(CommandHandler("help", cmd_help))
    app_bot.add_handler(CommandHandler("diario", cmd_diario))
    app_bot.add_handler(CommandHandler("resumen", cmd_resumen))
    app_bot.add_handler(perfil_handler)
    
    app_bot.add_handler(CallbackQueryHandler(callback_pdf, pattern="^generate_pdf$"))
    app_bot.add_handler(CallbackQueryHandler(callback_handler, pattern="^(confirm_save|cancel_save|mom_|fec_)"))
    
    app_bot.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 Bot iniciado correctamente...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
