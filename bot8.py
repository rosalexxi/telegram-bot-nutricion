import os
import re
import io
import json
import base64
from datetime import datetime, date, timedelta, time
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
# FUNCIÓN AUXILIAR DE LIMPIEZA DE NÚMEROS
# ==========================================
def parse_float(val):
    """ Convierte cualquier valor (string con coma, entero, float) a float seguro. """
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip().replace(',', '.')
    try:
        return float(val_str)
    except ValueError:
        return 0.0

# ==========================================
# LÓGICA DE HORARIO Y FECHA AUTOMÁTICA
# ==========================================
def obtener_momento_y_fecha_auto():
    ahora = datetime.now()
    hora = me = ahora.time()
    fecha_obj = me = ahora.date()
    
    # De 00:00 a 02:00 pertenece a la cena del día anterior
    if time(0, 0) <= me < time(2, 0):
        fecha_obj = fecha_obj - timedelta(days=1)
        momento = "Cena"
    elif time(6, 0) <= me < time(10, 0):
        momento = "Desayuno"
    elif time(10, 0) <= me < time(12, 0):
        momento = "Colación"
    elif time(12, 0) <= me < time(15, 0):
        momento = "Almuerzo"
    elif time(15, 0) <= me < time(20, 0):
        momento = "Merienda"
    else: # 20:00 a 23:59
        momento = "Cena"
        
    return fecha_obj.strftime("%Y-%m-%d"), momento

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
            ws = spreadsheet.add_worksheet(title=title, rows="500", cols="10")
            ws.append_row(["Fecha", "Momento/Actividad", "Alimento/Detalle", "Peso (g)", "Calorías (kcal)", "Proteínas (g)", "Grasas (g)", "Hidratos (g)", "Fibras (g)"])
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
            fecha,
            momento,
            item.get("alimento", "Desconocido"),
            parse_float(item.get("peso", 0)),
            parse_float(item.get("calorias", 0)),
            parse_float(item.get("proteinas", 0)),
            parse_float(item.get("grasas", 0)),
            parse_float(item.get("carbohidratos", 0)),
            parse_float(item.get("fibras", 0))
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
            df['Fecha'] = df['Fecha'].astype(str)
            df = df[df['Fecha'].str.startswith(mes_str)]
            
            # PARSEO SEGURO REEMPLAZANDO COMAS POR PUNTOS
            for col in ['Peso', 'Calorias', 'Proteinas', 'Grasas', 'Carbohidratos', 'Fibras']:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
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
        parse_float(perfil_dict.get("edad", 0)),
        perfil_dict.get("sexo", ""),
        parse_float(perfil_dict.get("peso", 0)),
        parse_float(perfil_dict.get("altura", 0)),
        parse_float(perfil_dict.get("cintura", 0)),
        perfil_dict.get("ocupacion", ""),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ]
    ws_perfil.append_row(row_data)

def calcular_metabolismo(perfil):
    if not perfil:
        return None
    try:
        edad = parse_float(perfil.get("Edad", perfil.get("edad", 0)))
        sexo = str(perfil.get("Sexo", perfil.get("sexo", "M"))).upper()
        peso = parse_float(perfil.get("Peso_kg", perfil.get("peso", 0)))
        altura = parse_float(perfil.get("Altura_cm", perfil.get("altura", 0)))
        
        if sexo == "M":
            tmb = (10 * peso) + (6.25 * altura) - (5 * edad) + 5
        else:
            tmb = (10 * peso) + (6.25 * altura) - (5 * edad) - 161
            
        get_val = tmb * 1.2
        return {"tmb": round(tmb, 1), "get": round(get_val, 1)}
    except:
        return None

# ==========================================
# PROCESAMIENTO CON GROQ (IA)
# ==========================================
def analizar_con_groq(prompt_text):
    system_prompt = (
        "Sos un nutricionista y entrenador experto. Analizá el texto del usuario.\n"
        "REGLA CRÍTICA DE NUMEROS: Usá SIEMPRE el punto (.) como separador decimal (ej: 7.5 en lugar de 7,5).\n"
        "Si detectás actividad física o ejercicio, las calorías DEBEN tener signo negativo (ej: -300.0).\n"
        "Devolvé EXCLUSIVAMENTE un JSON válido con este formato:\n"
        "{\n"
        '  "items": [\n'
        '    {"alimento": "nombre o descripcion", "peso": 0.0, "calorias": 0.0, "proteinas": 0.0, "grasas": 0.0, "carbohidratos": 0.0, "fibras": 0.0}\n'
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

def analizar_imagen_con_groq(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    system_prompt = (
        "Identifica los alimentos o la comida en esta imagen y estima sus nutrientes y peso aproximado.\n"
        "REGLA CRÍTICA DE NUMEROS: Usá SIEMPRE el punto (.) como separador decimal (ej: 7.5 en lugar de 7,5).\n"
        "Devolvé EXCLUSIVAMENTE un JSON válido con esta estructura:\n"
        "{\n"
        '  "items": [\n'
        '    {"alimento": "nombre", "peso": 0.0, "calorias": 0.0, "proteinas": 0.0, "grasas": 0.0, "carbohidratos": 0.0, "fibras": 0.0}\n'
        '  ],\n'
        '  "tipo": "Comida"\n'
        "}"
    )
    
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
# COMANDOS BÁSICOS Y DIARIO AGRUPADO
# ==========================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 **¡Hola! Bienvenido a tu Bot de Registro Nutricional.**\n\n"
        "📌 **¿Qué podés hacer?**\n"
        "• Escribí, mandá notas de voz o fotos de tus comidas.\n"
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
    
    agrupado = df_fecha.groupby('Momento').agg({
        'Alimento': lambda x: ', '.join(x.astype(str)),
        'Peso': 'sum',
        'Calorias': 'sum',
        'Proteinas': 'sum',
        'Grasas': 'sum',
        'Carbohidratos': 'sum',
        'Fibras': 'sum'
    }).reset_index()

    res = f"📅 **Diario del día ({fecha_target}):**\n\n"
    tot_c = tot_p = tot_g = tot_h = tot_f = 0
    
    for _, r in agrupado.iterrows():
        p_gr = parse_float(r.get('Peso', 0))
        c = parse_float(r.get('Calorias', 0))
        p = parse_float(r.get('Proteinas', 0))
        g = parse_float(r.get('Grasas', 0))
        h = parse_float(r.get('Carbohidratos', 0))
        f = parse_float(r.get('Fibras', 0))
        
        tot_c += c; tot_p += p; tot_g += g; tot_h += h; tot_f += f
        res += f"• [{r.get('Momento', 'General')}] **{r.get('Alimento', 'Ítem')}** ({p_gr:.0f}g)\n"
        res += f"  └ {c:.0f} kcal | P: {p:.1f}g | G: {g:.1f}g | H: {h:.1f}g | Fib: {f:.1f}g\n"
        
    res += f"\n🔥 **Totales:** {tot_c:.0f} kcal\n"
    res += f"💪 Prot: {tot_p:.1f}g | 🥑 Grasas: {tot_g:.1f}g | 🍞 Carb: {tot_h:.1f}g | 🌾 Fib: {tot_f:.1f}g"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(res, parse_mode="Markdown")
    else:
        await update.message.reply_text(res, parse_mode="Markdown")

# ==========================================
# HANDLERS DE MENSAJES (TEXTO, FOTO, VOZ)
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

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🎙️ Escuchando nota de voz...")
    try:
        voice_file = await update.message.voice.get_file()
        voice_bytes = await voice_file.download_as_bytearray()
        
        audio_buffer = io.BytesIO(voice_bytes)
        audio_buffer.name = "audio.ogg"

        transcription = client_ai.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=audio_buffer,
            language="es"
        )
        
        texto_transcripto = transcription.text
        await msg.edit_text(f"🗣️ *Transcripción:* \"{texto_transcripto}\"\n⏳ Analizando...", parse_mode="Markdown")
        
        data = analizar_con_groq(texto_transcripto)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        await msg.edit_text(f"❌ Error al procesar el audio: {e}")

async def procesar_y_mostrar_confirmacion(data, msg, context):
    items = data.get("items", [])
    tipo = data.get("tipo", "Comida")
    
    if not items:
        await msg.edit_text("No pude identificar datos claros.")
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
    fecha = context.user_data.get('pending_fecha', date.today().strftime("%Y-%m-%d"))
    momento = context.user_data.get('pending_momento', 'Almuerzo')

    txt_res = f"📝 **Confirmación ({tipo}):**\n"
    txt_res += f"📅 **Fecha:** `{fecha}`\n"
    if tipo == "Comida":
        txt_res += f"🍽️ **Momento:** `{momento}`\n\n"
    else:
        txt_res += f"🏃 **Tipo:** Actividad Física\n\n"
        
    tot_c = tot_p = tot_g = tot_h = tot_f = 0
    
    for idx, item in enumerate(items):
        p_gr = parse_float(item.get('peso', 0))
        c = parse_float(item.get('calorias', 0))
        p = parse_float(item.get('proteinas', 0))
        g = parse_float(item.get('grasas', 0))
        h = parse_float(item.get('carbohidratos', 0))
        f = parse_float(item.get('fibras', 0))
        tot_c += c; tot_p += p; tot_g += g; tot_h += h; tot_f += f
        
        txt_res += f"**{idx+1}. {item['alimento']}** ({p_gr:.0f}g):\n"
        if c >= 0:
            txt_res += f"  └ {c:.0f} kcal | P: {p:.1f}g | G: {g:.1f}g | H: {h:.1f}g | Fib: {f:.1f}g\n"
        else:
            txt_res += f"  └ Calorías Quemadas: {abs(c):.0f} kcal\n"
        
    txt_res += f"\n🔥 **Total Calorías:** {tot_c:.0f} kcal\n"

    keyboard = []
    
    for idx, item in enumerate(items):
        keyboard.append([
            InlineKeyboardButton(f"✏️ Modificar #{idx+1} ({item['alimento'][:15]}...)", callback_data=f"edit_item_{idx}")
        ])

    if tipo == "Comida":
        keyboard.append([
            InlineKeyboardButton("🌅 Desayuno", callback_data="mom_Desayuno"),
            InlineKeyboardButton("☀️ Almuerzo", callback_data="mom_Almuerzo"),
            InlineKeyboardButton("☕ Merienda", callback_data="mom_Merienda"),
            InlineKeyboardButton("🌙 Cena", callback_data="mom_Cena")
        ])
        
    keyboard.append([
        InlineKeyboardButton("📅 Cambiar Fecha", callback_data="cambiar_fecha_confirm")
    ])
    keyboard.append([
        InlineKeyboardButton("❌ Anular", callback_data="cancel_entry"),
        InlineKeyboardButton("✅ Guardar Todo", callback_data="confirm_save")
    ])

    markup = InlineKeyboardMarkup(keyboard)

    if hasattr(msg_or_query, 'edit_message_text'):
        await msg_or_query.edit_message_text(txt_res, reply_markup=markup, parse_mode="Markdown")
    else:
        await msg_or_query.edit_text(txt_res, reply_markup=markup, parse_mode="Markdown")

# ==========================================
# CALLBACKS DE BOTONES EN TELEGRAM
# ==========================================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "confirm_save":
        user_id = query.from_user.id
        items = context.user_data.get('pending_items', [])
        tipo = context.user_data.get('pending_tipo', 'Comida')
        fecha = context.user_data.get('pending_fecha', date.today().strftime("%Y-%m-%d"))
        momento = context.user_data.get('pending_momento', 'Almuerzo')

        guardar_en_sheets(user_id, items, fecha, momento, tipo)
        await query.edit_message_text(f"✅ ¡Guardado con éxito en Google Sheets!\n📅 Fecha: `{fecha}`", parse_mode="Markdown")

    elif data == "cancel_entry":
        context.user_data.pop('pending_items', None)
        context.user_data.pop('pending_tipo', None)
        context.user_data.pop('pending_fecha', None)
        context.user_data.pop('pending_momento', None)
        await query.edit_message_text("🚫 **Registro anulado.** No se guardó nada.", parse_mode="Markdown")

    elif data.startswith("mom_"):
        context.user_data['pending_momento'] = data.split("_")[1]
        await render_confirmation_screen(query, context)

    elif data == "cambiar_fecha_confirm":
        await query.edit_message_text("✍️ Escribí la fecha en formato **AAAA-MM-DD** (ej: `2026-07-30`):", parse_mode="Markdown")
        context.user_data['esperando_fecha'] = True

    elif data == "diario_hoy":
        hoy_str = date.today().strftime("%Y-%m-%d")
        await consultar_diario_fecha(update, context, hoy_str)
        
    elif data == "diario_ayer":
        ayer_str = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        await consultar_diario_fecha(update, context, ayer_str)
        
    elif data == "diario_otrodia":
        await query.edit_message_text("✍️ Escribí la fecha a consultar en formato **AAAA-MM-DD** (ej: `2026-07-25`):", parse_mode="Markdown")
        context.user_data['esperando_fecha_diario'] = True

async def handle_text_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if context.user_data.get('esperando_fecha'):
        if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
            context.user_data['pending_fecha'] = text
            context.user_data['esperando_fecha'] = False
            msg = await update.message.reply_text("Actualizando...")
            await render_confirmation_screen(msg, context)
        else:
            await update.message.reply_text("❌ Formato incorrecto. Mandalo como `AAAA-MM-DD` (ej: `2026-07-30`).")
        return

    if context.user_data.get('esperando_fecha_diario'):
        if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
            context.user_data['esperando_fecha_diario'] = False
            await consultar_diario_fecha(update, context, text)
        else:
            await update.message.reply_text("❌ Formato incorrecto. Mandalo como `AAAA-MM-DD` (ej: `2026-07-25`).")
        return

    await handle_message(update, context)

# ==========================================
# GENERACIÓN DE PDF
# ==========================================
def generar_pdf_bytes(user_id, mes_str, df, perfil, metabol):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1E3A8A'), spaceAfter=8)
    sub_style = ParagraphStyle('SubTitle', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#2563EB'), spaceAfter=6)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8.5, leading=12)

    story = []

    # ----------------------------------------------------
    # HOJA 1: RESUMEN MENSUAL
    # ----------------------------------------------------
    story.append(Paragraph(f"<b>Reporte Nutricional Mensual - {mes_str}</b>", title_style))
    story.append(Paragraph(f"Usuario Telegram ID: {user_id}", body_style))
    story.append(Spacer(1, 10))

    tot_c_in = 0.0
    tot_c_out = 0.0

    if not df.empty and 'Fecha' in df.columns:
        df['Es_Ejercicio'] = df['Calorias'] < 0
        
        fechas_unicas = sorted(df['Fecha'].unique())
        table_data = [["Fecha", "Cal. Consumid.", "Cal. Quemad.", "Bal. Neto", "Prot (g)", "Grasas (g)", "Carbs (g)", "Fibras (g)"]]
        
        tot_p = tot_g = tot_h = tot_f = 0.0
        
        for f in fechas_unicas:
            sub = df[df['Fecha'] == f]
            
            comidas = sub[~sub['Es_Ejercicio']]
            ejercicios = sub[sub['Es_Ejercicio']]
            
            c_in = comidas['Calorias'].sum() if not comidas.empty else 0.0
            c_out = ejercicios['Calorias'].abs().sum() if not ejercicios.empty else 0.0
            
            bal_neto = c_in - c_out
            
            p = comidas['Proteinas'].sum() if not comidas.empty else 0.0
            g = comidas['Grasas'].sum() if not comidas.empty else 0.0
            h = comidas['Carbohidratos'].sum() if not comidas.empty else 0.0
            fib = comidas['Fibras'].sum() if not comidas.empty else 0.0
            
            tot_c_in += c_in
            tot_c_out += c_out
            tot_p += p
            tot_g += g
            tot_h += h
            tot_f += fib
            
            table_data.append([
                str(f),
                f"{c_in:.1f} kcal",
                f"-{c_out:.1f} kcal" if c_out > 0 else "0.0 kcal",
                f"{bal_neto:.1f} kcal",
                f"{p:.1f} g",
                f"{g:.1f} g",
                f"{h:.1f} g",
                f"{fib:.1f} g"
            ])
            
        dias_cnt = max(len(fechas_unicas), 1)
        
        table_data.append([
            "TOTAL MES",
            f"{tot_c_in:.1f} kcal",
            f"-{tot_c_out:.1f} kcal",
            f"{(tot_c_in - tot_c_out):.1f} kcal",
            f"{tot_p:.1f} g",
            f"{tot_g:.1f} g",
            f"{tot_h:.1f} g",
            f"{tot_f:.1f} g"
        ])
        
        table_data.append([
            "PROM. DIARIO",
            f"{(tot_c_in / dias_cnt):.1f} kcal",
            f"-{(tot_c_out / dias_cnt):.1f} kcal",
            f"{((tot_c_in - tot_c_out) / dias_cnt):.1f} kcal",
            f"{(tot_p / dias_cnt):.1f} g",
            f"{(tot_g / dias_cnt):.1f} g",
            f"{(tot_h / dias_cnt):.1f} g",
            f"{(tot_f / dias_cnt):.1f} g"
        ])
            
        t = Table(table_data, colWidths=[65, 75, 75, 75, 55, 55, 55, 55])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 7.5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BACKGROUND', (0,1), (-1,-3), colors.HexColor('#F8FAFC')),
            ('BACKGROUND', (0,-2), (-1,-1), colors.HexColor('#E2E8F0')),
            ('FONTNAME', (0,-2), (-1,-1), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ]))
        story.append(t)

    story.append(PageBreak())

    # ----------------------------------------------------
    # HOJA 2: ANÁLISIS METABÓLICO Y ESTIMACIÓN CORPORAL
    # ----------------------------------------------------
    story.append(Paragraph("<b>Análisis Metabólico y Estimación Corporal</b>", title_style))
    story.append(Spacer(1, 10))

    if perfil and metabol:
        p_sexo = perfil.get('Sexo', perfil.get('sexo', 'N/A'))
        p_edad = perfil.get('Edad', perfil.get('edad', 'N/A'))
        p_peso = perfil.get('Peso_kg', perfil.get('peso', 'N/A'))
        p_altura = perfil.get('Altura_cm', perfil.get('altura', 'N/A'))
        p_ocup = perfil.get('Ocupacion', perfil.get('ocupacion', 'N/A'))
        
        info_perfil = [
            ["Dato Fisiológico", "Valor Registrado"],
            ["Sexo", str(p_sexo)],
            ["Edad", f"{p_edad} años"],
            ["Peso", f"{p_peso} kg"],
            ["Altura", f"{p_altura} cm"],
            ["Ocupación / Actividad", str(p_ocup)],
            ["Metabolismo Basal (TMB)", f"{metabol['tmb']} kcal / día"],
            ["Gasto Energético Conservador (GET)", f"{metabol['get']} kcal / día"]
        ]
        
        t_perfil = Table(info_perfil, colWidths=[200, 250])
        t_perfil.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2563EB')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('FONTSIZE', (0,0), (-1,-1), 8.5),
        ]))
        story.append(t_perfil)
        story.append(Spacer(1, 15))

        story.append(Paragraph("<b>Resumen de Balance y Cambio Corporal Estimado:</b>", sub_style))
        
        dias_tot = max(df['Fecha'].nunique() if not df.empty else 1, 1)
        gasto_basal_actividad = metabol['get'] * dias_tot
        
        balance_real = tot_c_in - (gasto_basal_actividad + tot_c_out)
        cambio_peso_kg = balance_real / 7700

        info_balance = [
            ["Concepto", "Valor Mensual"],
            ["Total Calorías Consumidas (Ingesta Real)", f"{tot_c_in:.1f} kcal"],
            [f"Total Gasto Basal + Ocupación (GET) ({dias_tot} días)", f"-{gasto_basal_actividad:.1f} kcal"],
            ["Total Ejercicio Extra Registrado", f"-{tot_c_out:.1f} kcal"],
            ["BALANCE CALÓRICO NETO REAL", f"{balance_real:+.1f} kcal"],
            ["CAMBIO ESTIMADO DE PESO", f"{cambio_peso_kg:+.2f} kg ({cambio_peso_kg*1000:+.1f} g)"]
        ]
        
        t_bal = Table(info_balance, colWidths=[250, 200])
        t_bal.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTNAME', (0,-2), (-1,-1), 'Helvetica-Bold'),
            ('BACKGROUND', (0,-2), (-1,-1), colors.HexColor('#E2E8F0')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('FONTSIZE', (0,0), (-1,-1), 8.5),
        ]))
        story.append(t_bal)
    else:
        story.append(Paragraph("<i>No se pudo calcular la estimación metabólica porque no se ha completado el /perfil del usuario.</i>", body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer

async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mes_actual = date.today().strftime("%Y-%m")
    
    msg = await update.message.reply_text("📊 Generando el informe PDF...")
    
    df = obtener_datos_mes(user_id, mes_actual)
    perfil = obtener_perfil(user_id)
    metabol = calcular_metabolismo(perfil)
    
    if df.empty:
        await msg.edit_text("❌ No hay datos guardados en este mes para generar el PDF.")
        return
        
    pdf_buffer = generar_pdf_bytes(user_id, mes_actual, df, perfil, metabol)
    
    await update.message.reply_document(
        document=pdf_buffer,
        filename=f"Reporte_Nutricional_{mes_actual}.pdf",
        caption=f"📈 **Reporte Nutricional Mensual ({mes_actual})**"
    )
    await msg.delete()

# ==========================================
# CONVERSACIÓN Y CONFIGURACIÓN DE PERFIL
# ==========================================
async def start_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚙️ **Configuración de Perfil Corporal**\n\n1️⃣ ¿Cuál es tu **edad**? (ej: 28)")
    return EDAD

async def set_edad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['perfil_edad'] = update.message.text.strip()
    await update.message.reply_text("2️⃣ ¿Cuál es tu **sexo**? (M / F)")
    return SEXO

async def set_sexo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['perfil_sexo'] = update.message.text.strip().upper()
    await update.message.reply_text("3️⃣ ¿Cuál es tu **peso actual** en kg? (ej: 75.5)")
    return PESO

async def set_peso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['perfil_peso'] = update.message.text.strip()
    await update.message.reply_text("4️⃣ ¿Cuál es tu **altura** en cm? (ej: 175)")
    return ALTURA

async def set_altura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['perfil_altura'] = update.message.text.strip()
    await update.message.reply_text("5️⃣ ¿Cuál es la medida de tu **cintura** en cm? (opcional, si no tenés respondé 0):")
    return CINTURA

async def set_cintura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['perfil_cintura'] = update.message.text.strip()
    await update.message.reply_text("6️⃣ ¿Cuál es tu **ocupación o nivel de actividad diario habitual**? (ej: 'Trabajo de oficina sentado', 'Mozo de pie', 'Construcción')")
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
    
    await update.message.reply_text("✅ **¡Perfil guardado correctamente!** Ahora tus reportes incluirán estimación metabólica.")
    return ConversationHandler.END

async def cancel_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Configuración de perfil cancelada.")
    return ConversationHandler.END

# ==========================================
# MAIN Y RUN
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
        fallbacks=[CommandHandler('cancel', cancel_perfil)]
    )

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("diario", cmd_diario))
    application.add_handler(CommandHandler("resumen", cmd_resumen))
    application.add_handler(perfil_handler)
    
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_inputs))

    application.run_polling()

if __name__ == "__main__":
    main()
