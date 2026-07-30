import os
import re
import io
import json
import base64
from datetime import datetime, date, timedelta
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from groq import Groq
from dotenv import load_dotenv
from flask import Flask
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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_SHEETS_KEY_PATH = os.getenv("GOOGLE_SHEETS_KEY_PATH", "credentials.json")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "Registro_Nutricional_Bot")

client_ai = Groq(api_key=GROQ_API_KEY)

# ==========================================
# SERVIDOR FLASK (KEEP ALIVE)
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Nutricional Activo 🚀"

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
            ws = spreadsheet.add_worksheet(title=title, rows="500", cols="12")
            ws.append_row(["User_ID", "Fecha", "Tipo", "Momento/Actividad", "Alimento/Detalle", "Peso (g)", "Calorías (kcal)", "Proteínas (g)", "Grasas (g)", "Hidratos (g)", "Fibras (g)"])
            return ws
        elif title.startswith("Perfil"):
            ws = spreadsheet.add_worksheet(title=title, rows="100", cols="8")
            ws.append_row(["Mes_Anio", "Edad", "Sexo", "Peso_kg", "Altura_cm", "Cintura_cm", "Ocupacion", "Fecha_Actualizacion"])
            return ws
        else:
            return spreadsheet.add_worksheet(title=title, rows="100", cols="10")

def guardar_en_sheets(user_id, items, fecha, momento, tipo="Comida"):
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    
    try:
        ws = get_or_create_worksheet(sh, f"User_{user_id}")
    except:
        ws = sh.sheet1

    rows = []
    for item in items:
        rows.append([
            str(user_id),
            fecha,
            tipo,
            momento,
            item.get("alimento", "Desconocido"),
            float(item.get("peso", 0)),
            float(item.get("calorias", 0)),
            float(item.get("proteinas", 0)),
            float(item.get("grasas", 0)),
            float(item.get("carbohidratos", 0)),
            float(item.get("fibras", 0))
        ])
    if rows:
        ws.append_rows(rows)

def obtener_datos_mes(user_id, mes_str):
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        
        try:
            ws = sh.worksheet(f"User_{user_id}")
        except:
            ws = sh.sheet1

        records = ws.get_all_records()
        if not records:
            return pd.DataFrame()
        
        df = pd.DataFrame(records)
        
        # Mapeo universal de columnas
        col_map = {}
        for c in df.columns:
            c_lower = c.lower()
            if 'fecha' in c_lower: col_map[c] = 'Fecha'
            elif 'momento' in c_lower or 'actividad' in c_lower: col_map[c] = 'Momento'
            elif 'alimento' in c_lower or 'detalle' in c_lower: col_map[c] = 'Alimento'
            elif 'calor' in c_lower: col_map[c] = 'Calorias'
            elif 'prote' in c_lower: col_map[c] = 'Proteinas'
            elif 'grasa' in c_lower: col_map[c] = 'Grasas'
            elif 'hidrat' in c_lower or 'carbo' in c_lower: col_map[c] = 'Carbohidratos'
            elif 'fibra' in c_lower: col_map[c] = 'Fibras'
            elif 'tipo' in c_lower: col_map[c] = 'Tipo'

        df = df.rename(columns=col_map)
        
        if "Fecha" in df.columns and not df.empty:
            df['Fecha'] = df['Fecha'].astype(str)
            df = df[df['Fecha'].str.startswith(mes_str)]
            
            for col in ['Calorias', 'Proteinas', 'Grasas', 'Carbohidratos', 'Fibras']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                else:
                    df[col] = 0.0
                    
        return df
    except Exception as e:
        print(f"Error al obtener datos: {e}")
        return pd.DataFrame()

def obtener_perfil(user_id):
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        
        try:
            ws = sh.worksheet(f"Perfil_{user_id}")
        except:
            try:
                ws = sh.worksheet("Perfil")
            except:
                return None
                
        records = ws.get_all_records()
        if not records:
            return None
            
        df = pd.DataFrame(records)
        
        if "User_ID" in df.columns:
            df_user = df[df["User_ID"].astype(str) == str(user_id)]
            if not df_user.empty:
                return df_user.iloc[-1].to_dict()
                
        return df.iloc[-1].to_dict()
    except Exception as e:
        print(f"Error al obtener perfil: {e}")
        return None

def guardar_perfil(user_id, perfil_dict):
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    ws_perfil = get_or_create_worksheet(sh, f"Perfil_{user_id}")
    mes_actual = date.today().strftime("%Y-%m")
    
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
    ws_perfil.append_row(row_data)

def calcular_metabolismo(perfil):
    if not perfil:
        return None
    try:
        edad = float(perfil.get("Edad", perfil.get("edad", 0)))
        sexo = str(perfil.get("Sexo", perfil.get("sexo", "M"))).upper()
        peso = float(perfil.get("Peso_kg", perfil.get("peso", 0)))
        altura = float(perfil.get("Altura_cm", perfil.get("altura", 0)))
        
        if sexo == "M":
            tmb = (10 * peso) + (6.25 * altura) - (5 * edad) + 5
        else:
            tmb = (10 * peso) + (6.25 * altura) - (5 * edad) - 161
            
        get_val = tmb * 1.2  # Factor de actividad sedentaria / diario base
        return {"tmb": round(tmb, 1), "get": round(get_val, 1)}
    except:
        return None

# ==========================================
# PROCESAMIENTO CON GROQ (IA)
# ==========================================
def analizar_con_groq(prompt_text):
    system_prompt = (
        "Sos un nutricionista y entrenador experto. Analizá el texto del usuario.\n"
        "Devolvé EXCLUSIVAMENTE un JSON válido con este formato:\n"
        "{\n"
        '  "items": [\n'
        '    {"alimento": "nombre o descripcion", "peso": 0.0, "calorias": 0.0, "proteinas": 0.0, "grasas": 0.0, "carbohidratos": 0.0, "fibras": 0.0}\n'
        '  ],\n'
        '  "tipo": "Comida" o "Ejercicio"\n'
        "}"
    )
    
    # Modelo ultrarrápido y confiable para Texto
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

def analizar_imagen_con_groq(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    system_prompt = (
        "Identifica los alimentos o la comida en esta imagen y estima sus nutrientes y peso aproximado.\n"
        "Devolvé EXCLUSIVAMENTE un JSON válido con esta estructura:\n"
        "{\n"
        '  "items": [\n'
        '    {"alimento": "nombre", "peso": 0.0, "calorias": 0.0, "proteinas": 0.0, "grasas": 0.0, "carbohidratos": 0.0, "fibras": 0.0}\n'
        '  ],\n'
        '  "tipo": "Comida"\n'
        "}"
    )
    
    # Exclusivo para imágenes (Qwen Vision)
    response = client_ai.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": system_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
        ],
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

# ==========================================
# COMANDOS BÁSICOS
# ==========================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 **¡Hola! Bienvenido a tu Bot de Registro Nutricional.**\n\n"
        "📌 **¿Qué podés hacer?**\n"
        "• Escribí o mandá fotos de tus comidas.\n"
        "• Registrá actividad física (ej: *'Entrenamiento gym 45 min 300 kcal'*).\n\n"
        "📌 **Comandos:**\n"
        "• /diario - Ver lo registrado (Hoy, Ayer o Buscar fecha)\n"
        "• /resumen - Informe mensual y descargar PDF completo\n"
        "• /perfil - Configurar o actualizar datos corporales"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 Hoy", callback_data="diario_hoy"),
            InlineKeyboardButton("⏮️ Ayer", callback_data="diario_ayer"),
            InlineKeyboardButton("📆 Otro Día", callback_data="diario_otrodia")
        ]
    ])
    await update.message.reply_text("📋 ¿Qué fecha querés consultar?", reply_markup=keyboard)

async def consultar_diario_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE, fecha_target):
    user_id = update.effective_user.id
    df = obtener_datos_mes(user_id, fecha_target[:7])
    
    if df.empty or "Fecha" not in df.columns or df[df['Fecha'] == fecha_target].empty:
        msg = f"📋 No tenés registros anotados para el día `{fecha_target}`."
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text(msg, parse_mode="Markdown")
        return
        
    df_fecha = df[df['Fecha'] == fecha_target]
    res = f"📅 **Diario del día ({fecha_target}):**\n\n"
    tot_c = tot_p = tot_g = tot_h = tot_f = 0
    
    for _, r in df_fecha.iterrows():
        c = float(r.get('Calorias', 0))
        p = float(r.get('Proteinas', 0))
        g = float(r.get('Grasas', 0))
        h = float(r.get('Carbohidratos', 0))
        f = float(r.get('Fibras', 0))
        
        tot_c += c; tot_p += p; tot_g += g; tot_h += h; tot_f += f
        res += f"• [{r.get('Momento', 'General')}] **{r.get('Alimento', 'Ítem')}**\n"
        res += f"  └ {c:.0f} kcal | P: {p:.1f}g | G: {g:.1f}g | H: {h:.1f}g | Fib: {f:.1f}g\n"
        
    res += f"\n🔥 **Totales:** {tot_c:.0f} kcal\n"
    res += f"💪 Prot: {tot_p:.1f}g | 🥑 Grasas: {tot_g:.1f}g | 🍞 Carb: {tot_h:.1f}g | 🌾 Fib: {tot_f:.1f}g"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(res, parse_mode="Markdown")
    else:
        await update.message.reply_text(res, parse_mode="Markdown")

# ==========================================
# GESTIÓN DE INTERACCIÓN Y PANTALLA UNIFICADA
# ==========================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    msg = await update.message.reply_text("⏳ Procesando...")
    try:
        data = analizar_con_groq(user_text)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        await msg.edit_text(f"❌ Error al interpretar el texto: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📸 Analizando plato con IA...")
    try:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        data = analizar_imagen_con_groq(photo_bytes)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        await msg.edit_text(f"❌ Error al analizar la imagen: {e}")

async def procesar_y_mostrar_confirmacion(data, msg, context):
    items = data.get("items", [])
    tipo = data.get("tipo", "Comida")
    
    if not items:
        await msg.edit_text("No pude identificar datos claros.")
        return

    context.user_data['pending_items'] = items
    context.user_data['pending_tipo'] = tipo
    if 'pending_fecha' not in context.user_data:
        context.user_data['pending_fecha'] = date.today().strftime("%Y-%m-%d")
    
    if tipo == "Comida":
        if 'pending_momento' not in context.user_data or context.user_data['pending_momento'] == "Ejercicio":
            context.user_data['pending_momento'] = "Almuerzo"
    else:
        context.user_data['pending_momento'] = "Ejercicio"
        
    await render_confirmation_screen(msg, context)

async def render_confirmation_screen(msg_or_query, context):
    items = context.user_data.get('pending_items', [])
    tipo = context.user_data.get('pending_tipo', 'Comida')
    fecha = context.user_data.get('pending_fecha', date.today().strftime("%Y-%m-%d"))
    momento = context.user_data.get('pending_momento', 'Almuerzo')

    txt_res = f"📝 **Confirmación ({tipo}):**\n"
    txt_res += f"📅 **Fecha:** `{fecha}`\n"
    if tipo == "Comida":
        txt_res += f"🍽️ **Momento Actual:** `{momento}`\n\n"
    else:
        txt_res += f"🏃 **Tipo:** Actividad Física\n\n"
        
    tot_c = tot_p = tot_g = tot_h = tot_f = 0
    
    for item in items:
        c = float(item.get('calorias', 0))
        p = float(item.get('proteinas', 0))
        g = float(item.get('grasas', 0))
        h = float(item.get('carbohidratos', 0))
        f = float(item.get('fibras', 0))
        tot_c += c; tot_p += p; tot_g += g; tot_h += h; tot_f += f
        
        txt_res += f"• **{item['alimento']}**:\n"
        if tipo == "Comida":
            txt_res += f"  └ {c:.0f} kcal | P: {p:.1f}g | G: {g:.1f}g | H: {h:.1f}g | Fib: {f:.1f}g\n"
        else:
            txt_res += f"  └ Calorías Quemadas: {c:.0f} kcal\n"
        
    txt_res += f"\n🔥 **Total Calorías:** {tot_c:.0f} kcal\n"

    keyboard = []
    
    # Teclado de Selección de Momento (Solo en Comidas)
    if tipo == "Comida":
        keyboard.append([
            InlineKeyboardButton("🌅 Desayuno", callback_data="mom_Desayuno"),
            InlineKeyboardButton("☀️ Almuerzo", callback_data="mom_Almuerzo"),
            InlineKeyboardButton("🌆 Merienda", callback_data="mom_Merienda")
        ])
        keyboard.append([
            InlineKeyboardButton("🌙 Cena", callback_data="mom_Cena"),
            InlineKeyboardButton("🍏 Colación", callback_data="mom_Colación")
        ])
    
    # Teclado de Fechas (Para Comida y Ejercicio)
    keyboard.append([
        InlineKeyboardButton("📅 Hoy", callback_data="fec_hoy"),
        InlineKeyboardButton("⏮️ Ayer", callback_data="fec_ayer"),
        InlineKeyboardButton("📆 Otro Día", callback_data="fec_otrodia")
    ])
    
    # Botones de Acción Final
    keyboard.append([
        InlineKeyboardButton("✏️ Modificar", callback_data="edit_manual"),
        InlineKeyboardButton("✅ Confirmar Guardado", callback_data="confirm_save"),
        InlineKeyboardButton("❌ Descartar", callback_data="cancel_save")
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if hasattr(msg_or_query, 'edit_text'):
        await msg_or_query.edit_text(txt_res, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await msg_or_query.edit_message_text(txt_res, parse_mode="Markdown", reply_markup=reply_markup)

# ==========================================
# CALLBACK HANDLER DE BOTONES
# ==========================================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data.startswith("mom_"):
        context.user_data['pending_momento'] = data.split("_")[1]
        await render_confirmation_screen(query, context)
        
    elif data == "fec_hoy":
        context.user_data['pending_fecha'] = date.today().strftime("%Y-%m-%d")
        await render_confirmation_screen(query, context)
        
    elif data == "fec_ayer":
        context.user_data['pending_fecha'] = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        await render_confirmation_screen(query, context)

    elif data == "fec_otrodia":
        await query.message.reply_text("📆 Ingresá la fecha en formato `YYYY-MM-DD` (ej: `2026-07-20`):", parse_mode="Markdown")
        context.user_data['waiting_for'] = 'custom_date'
        
    elif data == "edit_manual":
        await query.message.reply_text("✏️ Escribí el texto corregido del alimento/ejercicio y sus valores (ej: *'1 ensalada césar 350 kcal 20g proteina'*):", parse_mode="Markdown")
        context.user_data['waiting_for'] = 'edit_text'

    elif data == "diario_hoy":
        await consultar_diario_fecha(update, context, date.today().strftime("%Y-%m-%d"))

    elif data == "diario_ayer":
        await consultar_diario_fecha(update, context, (date.today() - timedelta(days=1)).strftime("%Y-%m-%d"))

    elif data == "diario_otrodia":
        await query.message.reply_text("📆 Ingresá la fecha a consultar (`YYYY-MM-DD`):", parse_mode="Markdown")
        context.user_data['waiting_for'] = 'diario_custom_date'

    elif data.startswith("resumen_mes_"):
        mes = data.replace("resumen_mes_", "")
        await mostrar_resumen_mes(update, context, mes)
        
    elif data == "confirm_save":
        items = context.user_data.get('pending_items', [])
        fecha = context.user_data.get('pending_fecha', date.today().strftime("%Y-%m-%d"))
        momento = context.user_data.get('pending_momento', 'General')
        tipo = context.user_data.get('pending_tipo', 'Comida')
        user_id = query.from_user.id
        
        if items:
            guardar_en_sheets(user_id, items, fecha, momento, tipo)
            await query.edit_message_text(f"✅ **¡Guardado Exitosamente!**\n\n📅 Fecha: `{fecha}`\n🍽️ Momento/Actividad: `{momento}`", parse_mode="Markdown")
            context.user_data.clear()
        else:
            await query.edit_message_text("No había elementos para guardar.")
            
    elif data == "cancel_save":
        context.user_data.clear()
        await query.edit_message_text("❌ Registro cancelado.")

async def handle_custom_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waiting = context.user_data.get('waiting_for')
    text = update.message.text.strip()

    if waiting == 'custom_date':
        if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
            context.user_data['pending_fecha'] = text
            context.user_data.pop('waiting_for', None)
            msg = await update.message.reply_text("✅ Fecha actualizada.")
            await render_confirmation_screen(msg, context)
        else:
            await update.message.reply_text("⚠️ Formato inválido. Debe ser `YYYY-MM-DD` (ej: `2026-07-28`).")

    elif waiting == 'diario_custom_date':
        if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
            context.user_data.pop('waiting_for', None)
            await consultar_diario_fecha(update, context, text)
        else:
            await update.message.reply_text("⚠️ Formato inválido. Debe ser `YYYY-MM-DD` (ej: `2026-07-28`).")

    elif waiting == 'edit_text':
        msg = await update.message.reply_text("⏳ Actualizando valores...")
        context.user_data.pop('waiting_for', None)
        data = analizar_con_groq(text)
        await procesar_y_mostrar_confirmacion(data, msg, context)

    else:
        await handle_message(update, context)

# ==========================================
# REPORTES Y PDF EN 2 HOJAS COMPLETAS
# ==========================================
async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mes_actual = date.today().strftime("%Y-%m")
    mes_anterior = (date.today().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"📅 Este Mes ({mes_actual})", callback_data=f"resumen_mes_{mes_actual}"),
            InlineKeyboardButton(f"⏮️ Mes Anterior ({mes_anterior})", callback_data=f"resumen_mes_{mes_anterior}")
        ]
    ])
    await update.message.reply_text("📊 Seleccioná el período a consultar:", reply_markup=keyboard)

async def mostrar_resumen_mes(update: Update, context: ContextTypes.DEFAULT_TYPE, mes_str):
    query = update.callback_query
    user_id = query.from_user.id
    
    df = obtener_datos_mes(user_id, mes_str)
    perfil = obtener_perfil(user_id)
    metabol = calcular_metabolismo(perfil)
    
    df_comida = df[df['Tipo'] == 'Comida'] if not df.empty and 'Tipo' in df.columns else df
    dias = df_comida['Fecha'].nunique() if not df_comida.empty and 'Fecha' in df_comida.columns else 0
    
    tot_cal = df_comida['Calorias'].sum() if not df_comida.empty and 'Calorias' in df_comida.columns else 0
    tot_prot = df_comida['Proteinas'].sum() if not df_comida.empty and 'Proteinas' in df_comida.columns else 0
    tot_gras = df_comida['Grasas'].sum() if not df_comida.empty and 'Grasas' in df_comida.columns else 0
    tot_carb = df_comida['Carbohidratos'].sum() if not df_comida.empty and 'Carbohidratos' in df_comida.columns else 0
    
    resumen_text = f"📊 **Resumen Mensual ({mes_str})**\n\n"
    resumen_text += f"📅 Días registrados: {dias}\n"
    resumen_text += f"🔥 Consumo Total: {tot_cal:.0f} kcal\n"
    resumen_text += f"💪 Prot: {tot_prot:.0f}g | 🥑 Grasas: {tot_gras:.0f}g | 🍞 Carb: {tot_carb:.0f}g\n\n"
    
    if perfil and metabol:
        resumen_text += f"🔥 TMB Basal: {metabol['tmb']} kcal/día\n"
        resumen_text += f"⚡ GET Gasto Total Est.: {metabol['get']} kcal/día\n"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Descargar PDF (2 Hojas Completo)", callback_data=f"genpdf_{mes_str}")]
    ])
    
    await query.edit_message_text(resumen_text, parse_mode="Markdown", reply_markup=keyboard)

def generar_pdf_bytes(user_id, mes_str, df, perfil, metabol):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1E3A8A'), spaceAfter=10)
    sub_style = ParagraphStyle('SubTitle', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#2563EB'), spaceAfter=8)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=9, leading=13)

    story = []

    # ----------------------------------------------------
    # HOJA 1: RESUMEN DIARIO PASO A PASO
    # ----------------------------------------------------
    story.append(Paragraph(f"<b>Reporte Nutricional Mensual - {mes_str} (Hoja 1: Desglose Diario)</b>", title_style))
    story.append(Spacer(1, 10))

    if not df.empty and 'Fecha' in df.columns:
        df_comidas = df[df['Tipo'] == 'Comida'] if 'Tipo' in df.columns else df
        df_diario = df_comidas.groupby('Fecha').agg({
            'Calorias': 'sum',
            'Proteinas': 'sum',
            'Grasas': 'sum',
            'Carbohidratos': 'sum',
            'Fibras': 'sum'
        }).reset_index().sort_values('Fecha')

        table_data = [["Fecha", "Kcal Ingesta", "Prot (g)", "Grasas (g)", "Carb (g)", "Fibras (g)"]]
        for _, r in df_diario.iterrows():
            table_data.append([
                str(r['Fecha']),
                f"{r['Calorias']:.0f}",
                f"{r['Proteinas']:.1f}",
                f"{r['Grasas']:.1f}",
                f"{r['Carbohidratos']:.1f}",
                f"{r['Fibras']:.1f}"
            ])
            
        t = Table(table_data, colWidths=[80, 80, 70, 70, 70, 70])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 8),
            ('BOTTOMPADDING', (0,0), (-1,0), 5),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F8FAFC')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('FONTSIZE', (0,1), (-1,-1), 8),
        ]))
        story.append(t)

    # SALTO DE PÁGINA OBLIGATORIO
    story.append(PageBreak())

    # ----------------------------------------------------
    # HOJA 2: TOTALES, PROMEDIOS Y ESTIMACIÓN METABÓLICA
    # ----------------------------------------------------
    story.append(Paragraph(f"<b>Reporte Nutricional Mensual - {mes_str} (Hoja 2: Análisis y Balance)</b>", title_style))
    story.append(Spacer(1, 10))

    df_comida = df[df['Tipo'] == 'Comida'] if not df.empty and 'Tipo' in df.columns else df
    df_ejercicio = df[df['Tipo'] == 'Ejercicio'] if not df.empty and 'Tipo' in df.columns else pd.DataFrame()

    dias_count = df_comida['Fecha'].nunique() if not df_comida.empty and 'Fecha' in df_comida.columns else 1
    dias_count = max(dias_count, 1)

    tot_cal = df_comida['Calorias'].sum() if not df_comida.empty else 0
    tot_prot = df_comida['Proteinas'].sum() if not df_comida.empty else 0
    tot_gras = df_comida['Grasas'].sum() if not df_comida.empty else 0
    tot_carb = df_comida['Carbohidratos'].sum() if not df_comida.empty else 0
    tot_ejercicio = df_ejercicio['Calorias'].sum() if not df_ejercicio.empty else 0

    prom_cal = tot_cal / dias_count
    prom_prot = tot_prot / dias_count
    prom_gras = tot_gras / dias_count
    prom_carb = tot_carb / dias_count

    story.append(Paragraph("<b>1. Totales Acumulados y Promedios Diarios</b>", sub_style))
    
    summary_data = [
        ["Métrica", "Total Mensual", "Promedio Diario"],
        ["Calorías Ingeridas", f"{tot_cal:.0f} kcal", f"{prom_cal:.0f} kcal/día"],
        ["Proteínas", f"{tot_prot:.1f} g", f"{prom_prot:.1f} g/día"],
        ["Grasas", f"{tot_gras:.1f} g", f"{prom_gras:.1f} g/día"],
        ["Carbohidratos", f"{tot_carb:.1f} g", f"{prom_carb:.1f} g/día"],
        ["Gasto Ejercicio Reg.", f"{tot_ejercicio:.0f} kcal", f"{(tot_ejercicio/dias_count):.0f} kcal/día"]
    ]
    
    ts = Table(summary_data, colWidths=[150, 150, 150])
    ts.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2563EB')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))
    story.append(ts)
    story.append(Spacer(1, 15))

    story.append(Paragraph("<b>2. Estimación de Cambio de Peso Corporal</b>", sub_style))
    
    if perfil and metabol:
        p_sexo = perfil.get('Sexo', perfil.get('sexo', 'N/A'))
        p_edad = perfil.get('Edad', perfil.get('edad', 'N/A'))
        p_peso = perfil.get('Peso_kg', perfil.get('peso', 'N/A'))
        p_altura = perfil.get('Altura_cm', perfil.get('altura', 'N/A'))
        
        gasto_basal_actividad = metabol['get'] * dias_count
        gasto_total_con_ejercicio = gasto_basal_actividad + tot_ejercicio
        balance = tot_cal - gasto_total_con_ejercicio
        cambio_peso = balance / 7700  # 7700 kcal equivalen aprox a 1 kg de grasa

        info_meta = (
            f"• <b>Perfil del Usuario:</b> {p_sexo} | {p_edad} años | {p_peso} kg | {p_altura} cm<br/>"
            f"• <b>Tasa Metabólica Basal (TMB):</b> {metabol['tmb']} kcal/día<br/>"
            f"• <b>Gasto Base + Actividad Diaria:</b> {gasto_basal_actividad:.0f} kcal ({dias_count} días)<br/>"
            f"• <b>Gasto Extra por Ejercicio:</b> {tot_ejercicio:.0f} kcal<br/>"
            f"• <b>GASTO TOTAL ESTIMADO:</b> {gasto_total_con_ejercicio:.0f} kcal<br/>"
            f"• <b>INGESTA TOTAL CONSUMIDA:</b> {tot_cal:.0f} kcal<br/><br/>"
            f"🔥 <b>BALANCE CALÓRICO NETO:</b> {balance:+.0f} kcal<br/>"
            f"⚖️ <b>VARIACIÓN ESTIMADA DE PESO:</b> <b>{cambio_peso:+.2f} kg</b>"
        )
        story.append(Paragraph(info_meta, body_style))
    else:
        story.append(Paragraph("<i>No se pudo calcular la estimación metabólica porque no se ha completado el /perfil del usuario.</i>", body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer

async def callback_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data.startswith("genpdf_"):
        mes_str = query.data.replace("genpdf_", "")
        await query.answer("Generando PDF...")
        await query.message.reply_text(f"📄 Generando PDF en 2 hojas para {mes_str}...")
        
        user_id = query.from_user.id
        df = obtener_datos_mes(user_id, mes_str)
        perfil = obtener_perfil(user_id)
        metabol = calcular_metabolismo(perfil)
        
        pdf_bytes = generar_pdf_bytes(user_id, mes_str, df, perfil, metabol)
        
        await query.message.reply_document(
            document=pdf_bytes,
            filename=f"Reporte_Nutricional_{mes_str}.pdf",
            caption=f"📄 Reporte Completo de 2 Hojas ({mes_str})."
        )

# ==========================================
# CONVERSACIÓN /PERFIL
# ==========================================
async def start_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📐 Configuración de perfil.\n\nIngresá tu **edad** en años:", parse_mode="Markdown")
    return EDAD

async def set_edad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_edad'] = update.message.text.strip()
    await update.message.reply_text("👤 Ingresá tu **sexo** (`M` / `F`):", parse_mode="Markdown")
    return SEXO

async def set_sexo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_sexo'] = update.message.text.strip().upper()
    await update.message.reply_text("⚖️ Ingresá tu **peso en kg** (ej: `75.5`):", parse_mode="Markdown")
    return PESO

async def set_peso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_peso'] = update.message.text.strip()
    await update.message.reply_text("📏 Ingresá tu **altura en cm** (ej: `170`):", parse_mode="Markdown")
    return ALTURA

async def set_altura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_altura'] = update.message.text.strip()
    await update.message.reply_text("📐 Ingresá la medida de tu **cintura en cm**:", parse_mode="Markdown")
    return CINTURA

async def set_cintura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_cintura'] = update.message.text.strip()
    await update.message.reply_text("💼 Ingresá tu **ocupación / actividad principal**:", parse_mode="Markdown")
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
    await update.message.reply_text("✅ **¡Perfil biométrico actualizado con éxito!**", parse_mode="Markdown")
    return ConversationHandler.END

async def cancel_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END

# ==========================================
# INICIO Y LISTENERS
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
    app_bot.add_handler(CommandHandler("diario", cmd_diario))
    app_bot.add_handler(CommandHandler("resumen", cmd_resumen))
    app_bot.add_handler(perfil_handler)
    
    app_bot.add_handler(CallbackQueryHandler(callback_pdf, pattern="^genpdf_"))
    app_bot.add_handler(CallbackQueryHandler(callback_handler, pattern="^(confirm_save|cancel_save|mom_|fec_|diario_|resumen_mes_|edit_manual)"))
    
    app_bot.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_inputs))
    
    print("🚀 Bot iniciado correctamente...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
