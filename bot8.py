import asyncio
import base64
from datetime import datetime, timedelta
import json
import os
import re
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import BytesIO

from dotenv import load_dotenv
from openai import OpenAI
import pandas as pd
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import gspread
from google.oauth2.service_account import Credentials

# ReportLab para generar el PDF de ayuda al vuelo
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

groq_client = OpenAI(
    api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1"
)

MODELO_GROQ = "qwen/qwen3.6-27b"

user_pending_data = {}
user_states = {}

# ==========================================
# CONFIGURACIÓN DE GOOGLE SHEETS (GSPREAD)
# ==========================================
SPREADSHEET_KEY = "19je2itfFPZqs2YMZcs_MTa7m0ejw_ZuBn_VwVwKCjf4"

def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_json_str = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if creds_json_str:
        creds_dict = json.loads(creds_json_str)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    else:
        creds = Credentials.from_service_account_file("credenciales.json", scopes=scopes)
    return gspread.authorize(creds)

def obtener_o_crear_hoja_usuario(sheet, user_id):
    sheet_name = f"User_{user_id}"
    try:
        worksheet = sheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=sheet_name, rows=1000, cols=10)
        # Se elimina User_ID y Tipo; Se agrega Fibras (g) y Cintura (cm)
        headers = [
            "Fecha", "Momento/Actividad", "Alimento/Detalle", 
            "Peso (g)", "Calorías (kcal)", "Proteínas (g)", 
            "Grasas (g)", "Hidratos (g)", "Fibras (g)", "Cintura (cm)"
        ]
        worksheet.append_row(headers)
    return worksheet

def obtener_o_crear_hoja_perfil(sheet, user_id):
    sheet_name = f"Perfil_{user_id}"
    try:
        worksheet = sheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=sheet_name, rows=100, cols=8)
        headers = ["Mes_Anio", "Fecha_Actualizacion", "Sexo", "Edad", "Peso_kg", "Altura_cm", "Cintura_cm", "Ocupacion"]
        worksheet.append_row(headers)
    return worksheet

# ==========================================
# SERVIDOR WEB PARA RENDER
# ==========================================
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Bot de Nutrición Activo</title>
            <meta charset="utf-8">
            <style>
                body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; background-color: #f4f4f9; color: #333; }
                h1 { color: #2e7d32; }
                .card { background: white; padding: 20px; border-radius: 8px; display: inline-block; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>🤖 Bot de Telegram de Nutrición</h1>
                <p>El servicio web y el bot se encuentran funcionando correctamente en línea.</p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html_content.encode("utf-8"))

    def log_message(self, format, *args):
        return

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# ==========================================
# FUNCIONES AUXILIARES Y PARSEO
# ==========================================

def extract_json(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<think>.*?(?:</think>|$)", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"^```\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        return text[start_idx : end_idx + 1].strip()
    return text.strip()

def parse_response_to_json(raw_text: str):
    clean_text = extract_json(raw_text)
    if not clean_text:
        raise ValueError("El modelo no devolvió una respuesta utilizable.")
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        fixed_text = clean_text.replace("'", '"')
        return json.loads(fixed_text)

# ==========================================
# CÁLCULOS METABÓLICOS Y BIOMÉTRICOS
# ==========================================

def calcular_metabolismo(sexo, edad, peso, altura, ocupacion):
    # Fórmula de Harris-Benedict revisada o Mifflin-St Jeor
    if str(sexo).upper().startswith("M"):
        tmb = (10 * peso) + (6.25 * altura) - (5 * edad) + 5
    else:
        tmb = (10 * peso) + (6.25 * altura) - (5 * edad) - 161

    # Factor de ocupación / actividad basal
    act = str(ocupacion).lower()
    if "ama de casa" in act or "sedentaria" in act or "oficina" in act:
        factor = 1.1
    elif "moderada" in act or "de pie" in act:
        factor = 1.2
    else:
        factor = 1.15

    get = tmb * factor
    return round(tmb, 1), round(get, 1)

def verificar_biometricos_30_dias(user_id: int) -> bool:
    """Retorna True si los datos están vigentes (menos de 30 días), False si expiraron o no existen."""
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(SPREADSHEET_KEY)
        worksheet = obtener_o_crear_hoja_perfil(sheet, user_id)
        records = worksheet.get_all_records()
        if not records:
            return False
        
        # Obtener el último registro
        ultimo = records[-1]
        fecha_str = str(ultimo.get("Fecha_Actualizacion", ""))
        if not fecha_str:
            return False
        
        fecha_act = datetime.strptime(fecha_str, "%Y-%m-%d")
        if (datetime.now() - fecha_act).days > 30:
            return False
        return True
    except Exception:
        return False

# ==========================================
# COMANDOS PRINCIPALES DE TELEGRAM
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.from_user.first_name
    await update.message.reply_text(
        f"¡Hola {user_name}! 👋\n\n"
        "• Enviame un texto o foto de lo que comiste o el ejercicio que realizaste.\n"
        "• La IA identificará automáticamente de qué se trata.\n"
        "• Usá /diario para consultar el resumen de un día.\n"
        "• Usá /resumen para el reporte mensual e informe metabólico.\n"
        "• Usá /perfil para actualizar tus datos biométricos.\n"
        "• Usá /help para ver la ayuda y descargar la guía."
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ayuda_texto = (
        "ℹ️ *Guía Rápida de Uso del Bot*\n\n"
        "1️⃣ *Registrar Comida o Ejercicio:* Solo enviá un mensaje con texto (ej. 'Milanesa con ensalada' o 'Corrí 30 min') o una foto. La IA lo detectará automáticamente.\n"
        "2️⃣ *Edición:* Si registrás una comida compuesta, podrás modificar los gramos o calorías de cada ingrediente antes de guardar.\n"
        "3️⃣ *Selección de fecha:* Siempre podrás elegir registrar para *Hoy*, *Ayer* u *Otra fecha*.\n"
        "4️⃣ *Resumen Diario (/diario):* Consultá el balance diario de cualquier fecha.\n"
        "5️⃣ *Resumen Mensual (/resumen):* Obtené el balance del mes con análisis del gasto basal y peso estimado.\n"
        "6️⃣ *Perfil (/perfil):* Mantené tus datos actualizados (requerido cada 30 días)."
    )
    keyboard = [[InlineKeyboardButton("📥 Descargar Guía en PDF", callback_data="download_help_pdf")]]
    await update.message.reply_text(ayuda_texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    client = get_gspread_client()
    sheet = client.open_by_key(SPREADSHEET_KEY)
    worksheet = obtener_o_crear_hoja_perfil(sheet, user_id)
    records = worksheet.get_all_records()

    if records:
        u = records[-1]
        msg = (
            f"👤 *Tus Datos Biométricos Actuales:*\n\n"
            f"• **Sexo:** {u.get('Sexo')}\n"
            f"• **Edad:** {u.get('Edad')} años\n"
            f"• **Peso:** {u.get('Peso_kg')} kg\n"
            f"• **Altura:** {u.get('Altura_cm')} cm\n"
            f"• **Cintura:** {u.get('Cintura_cm')} cm\n"
            f"• **Ocupación/Actividad:** {u.get('Ocupacion')}\n"
            f"• **Última Actualización:** {u.get('Fecha_Actualizacion')}\n\n"
            "¿Deseas actualizar tus datos biométricos?"
        )
    else:
        msg = "⚠️ Aún no tenés datos biométricos cargados. Por favor, actualizalos para poder calcular tu balance metabólico."

    keyboard = [[InlineKeyboardButton("✏️ Actualizar Perfil", callback_data="iniciar_perfil")]]
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not verificar_biometricos_30_dias(user_id):
        await update.message.reply_text("⚠️ Sus datos biométricos tienen más de 30 días de antigüedad o no han sido registrados. Por favor use /perfil para actualizarlos antes de continuar.")
        return

    user_states.pop(user_id, None)
    msg_espera = await update.message.reply_text("🔍 Analizando imagen con IA...")
    
    try:
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        system_instruction = "You are a strict JSON generator. Do NOT think step-by-step. Output ONLY a valid JSON object."
        prompt = """
        Analiza esta imagen e identifica los alimentos o plato presentado.
        Responde ÚNICAMENTE con un JSON en formato estricto:
        {
          "tipo": "comida",
          "items": [
            {"alimento": "Pechuga de pollo", "peso_g": 150, "calorias": 240, "proteinas_g": 31, "grasas_g": 3.5, "hidratos_g": 0, "fibras_g": 0}
          ]
        }
        """

        def _call_groq():
            return groq_client.chat.completions.create(
                model=MODELO_GROQ,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]},
                ],
                temperature=0.1,
                max_tokens=4000,
                timeout=30.0,
            )

        response = await asyncio.to_thread(_call_groq)
        parsed = parse_response_to_json(response.choices[0].message.content)
        items = parsed.get("items", [])
        user_pending_data[user_id] = {"tipo": "comida", "items": items, "momento": "No especificado"}
        await mostrar_resumen_y_botones(msg_espera, user_id)
    except Exception as e:
        await msg_espera.edit_text(f"❌ Error al procesar la imagen: {str(e)}")

async def procesar_texto_inteligente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not verificar_biometricos_30_dias(user_id):
        await update.message.reply_text("⚠️ Sus datos biométricos tienen más de 30 días de antigüedad o no han sido registrados. Por favor use /perfil para actualizarlos antes de registrar datos.")
        return

    texto = update.message.text
    msg_espera = await update.message.reply_text("🔍 Interpretando tu texto...")

    system_instruction = "You are a strict JSON generator. Output ONLY a valid JSON object."
    prompt = f"""
    El usuario ingresó el siguiente texto: "{texto}".
    Determina si se trata de una COMIDA o de EJERCICIO/ACTIVIDAD FÍSICA.
    
    Si es COMIDA, responde en JSON con la lista de componentes (si es comida compuesta como 'milanesa con fritas', separa cada ingrediente):
    {{
      "tipo": "comida",
      "items": [
        {{"alimento": "Milanesa", "peso_g": 180, "calorias": 320, "proteinas_g": 25, "grasas_g": 12, "hidratos_g": 15, "fibras_g": 1}},
        {{"alimento": "Papas fritas", "peso_g": 150, "calorias": 400, "proteinas_g": 4, "grasas_g": 20, "hidratos_g": 48, "fibras_g": 3}}
      ]
    }}

    Si es EJERCICIO / ACTIVIDAD FÍSICA, responde en JSON:
    {{
      "tipo": "actividad",
      "actividad": "Caminata",
      "duracion": "30 min",
      "calorias": 150
    }}
    """

    try:
        def _call_groq():
            return groq_client.chat.completions.create(
                model=MODELO_GROQ,
                messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=4000,
                timeout=30.0,
            )

        response = await asyncio.to_thread(_call_groq)
        parsed = parse_response_to_json(response.choices[0].message.content)
        
        if parsed.get("tipo") == "actividad":
            user_pending_data[user_id] = {
                "tipo": "actividad",
                "actividad": parsed.get("actividad", "Ejercicio"),
                "duracion": parsed.get("duracion", "30 min"),
                "calorias": int(parsed.get("calorias", 0))
            }
            await mostrar_confirmacion_actividad(msg_espera, user_id)
        else:
            items = parsed.get("items", [])
            user_pending_data[user_id] = {"tipo": "comida", "items": items, "momento": "No especificado"}
            await mostrar_resumen_y_botones(msg_espera, user_id)
    except Exception as e:
        await msg_espera.edit_text(f"❌ Error al interpretar el texto: {str(e)}")

async def mostrar_resumen_y_botones(message, user_id: int):
    data = user_pending_data[user_id]
    items = data["items"]
    reply_msg = "🍽 *Reconocimiento de Alimento:*\n\n"
    t_cal, t_prot, t_fat, t_carb, t_fib = 0, 0, 0, 0, 0
    
    keyboard = []
    for idx, item in enumerate(items):
        alimento = item.get("alimento", "Item")
        peso = item.get("peso_g", 0)
        cal = item.get("calorias", 0)
        reply_msg += (
            f"• *{alimento}* ({peso}g):\n"
            f"  └ {cal} kcal | P: {item.get('proteinas_g', 0)}g | G: {item.get('grasas_g', 0)}g | H: {item.get('hidratos_g', 0)}g | Fib: {item.get('fibras_g', 0)}g\n"
        )
        t_cal += cal
        t_prot += item.get("proteinas_g", 0)
        t_fat += item.get("grasas_g", 0)
        t_carb += item.get("hidratos_g", 0)
        t_fib += item.get("fibras_g", 0)
        
        # Botón individual para editar cada componente si es comida compuesta
        keyboard.append([InlineKeyboardButton(f"✏️ Editar {alimento}", callback_data=f"edit_item_{idx}")])

    reply_msg += (
        f"\n🔥 *Totales:* {round(t_cal, 1)} kcal\n"
        f"💪 Prot: {round(t_prot, 1)}g | 🥑 Grasas: {round(t_fat, 1)}g | 🍞 Carb: {round(t_carb, 1)}g | 🌾 Fib: {round(t_fib, 1)}g\n\n"
        "¿Deseas confirmar este registro?"
    )

    keyboard.append([InlineKeyboardButton("✅ Confirmar", callback_data="ask_momento")])
    keyboard.append([InlineKeyboardButton("❌ Descartar", callback_data="cancel_save")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    if hasattr(message, "edit_text"):
        await message.edit_text(reply_msg, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await message.reply_text(reply_msg, parse_mode="Markdown", reply_markup=reply_markup)

async def mostrar_confirmacion_actividad(message, user_id: int):
    data = user_pending_data[user_id]
    reply_msg = (
        f"🏃 *Actividad Detectada:*\n\n"
        f"• **Ejercicio:** {data['actividad']}\n"
        f"• **Duración:** {data['duracion']}\n"
        f"• **Calorías Estimadas:** {data['calorias']} kcal\n\n"
        "¿Deseas confirmar el registro?"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Confirmar", callback_data="ask_date")],
        [InlineKeyboardButton("✏️ Editar Calorías", callback_data="edit_act_cal")],
        [InlineKeyboardButton("❌ Descartar", callback_data="cancel_save")],
    ]
    if hasattr(message, "edit_text"):
        await message.edit_text(reply_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await message.reply_text(reply_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# ==========================================
# GUARDADO EN SHEETS
# ==========================================

def _sync_guardar_sheets(user_id: int, fecha_str: str, pending: dict):
    client = get_gspread_client()
    spreadsheet = client.open_by_key(SPREADSHEET_KEY)
    worksheet = obtener_o_crear_hoja_usuario(spreadsheet, user_id)
    
    # Obtener medida de cintura del mes si está disponible en perfil
    perfil_ws = obtener_o_crear_hoja_perfil(spreadsheet, user_id)
    p_records = perfil_ws.get_all_records()
    cintura = p_records[-1].get("Cintura_cm", "") if p_records else ""

    rows_to_append = []
    if pending["tipo"] == "comida":
        momento = pending.get("momento", "Sin especificar")
        for item in pending["items"]:
            # Formato: ["Fecha", "Momento/Actividad", "Alimento/Detalle", "Peso (g)", "Calorías (kcal)", "Proteínas (g)", "Grasas (g)", "Hidratos (g)", "Fibras (g)", "Cintura (cm)"]
            rows_to_append.append([
                fecha_str, momento, item.get("alimento", "Desconocido"), 
                item.get("peso_g", 0), item.get("calorias", 0), 
                item.get("proteinas_g", 0), item.get("grasas_g", 0), 
                item.get("hidratos_g", 0), item.get("fibras_g", 0), cintura
            ])
    elif pending["tipo"] == "actividad":
        rows_to_append.append([
            fecha_str, pending["actividad"], f"Duración: {pending['duracion']}", 
            0, -abs(pending["calorias"]), 0, 0, 0, 0, cintura
        ])
    for row in rows_to_append:
        worksheet.append_row(row)

async def guardar_en_google_sheets(user_id: int, fecha_str: str) -> str:
    pending = user_pending_data.get(user_id)
    if not pending:
        return "No hay datos pendientes para guardar."
    try:
        await asyncio.to_thread(_sync_guardar_sheets, user_id, fecha_str, pending)
        user_pending_data.pop(user_id, None)
        user_states.pop(user_id, None)
        return f"💾 ¡Guardado correctamente en tu hoja para la fecha *{fecha_str}*!"
    except Exception as e:
        return f"❌ Error al guardar en Google Sheets: {str(e)}"

# ==========================================
# REPORTES Y RESÚMENES (DIARIO / MENSUAL)
# ==========================================

def _sync_obtener_registros(user_id: int):
    client = get_gspread_client()
    worksheet = obtener_o_crear_hoja_usuario(client.open_by_key(SPREADSHEET_KEY), user_id)
    return worksheet.get_all_records()

def _sync_obtener_perfil(user_id: int):
    client = get_gspread_client()
    worksheet = obtener_o_crear_hoja_perfil(client.open_by_key(SPREADSHEET_KEY), user_id)
    return worksheet.get_all_records()

async def diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📅 Hoy", callback_data="diario_hoy"), InlineKeyboardButton("📅 Ayer", callback_data="diario_ayer")],
        [InlineKeyboardButton("📅 Otra fecha", callback_data="diario_otra")],
    ]
    await update.message.reply_text("📋 *¿De qué día querés consultar el diario?*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def generar_reporte_diario(user_id: int, fecha_str: str) -> str:
    data = await asyncio.to_thread(_sync_obtener_registros, user_id)
    if not data:
        return "📉 Todavía no tenés registros."
    df = pd.DataFrame(data)
    df["Fecha"] = df["Fecha"].astype(str)
    df_filtrado = df[df["Fecha"] == fecha_str]
    if df_filtrado.empty:
        return f"📅 Sin registros cargados para la fecha *{fecha_str}*."

    # Separar comidas y ejercicios segun calorias
    df["Calorías (kcal)"] = pd.to_numeric(df_filtrado["Calorías (kcal)"], errors="coerce").fillna(0)
    df_comida = df_filtrado[df_filtrado["Calorías (kcal)"] > 0]
    df_act = df_filtrado[df_filtrado["Calorías (kcal)"] < 0]

    cal_ing = df_comida["Calorías (kcal)"].sum()
    cal_quem = abs(df_act["Calorías (kcal)"].sum())
    prot = pd.to_numeric(df_comida["Proteínas (g)"], errors="coerce").sum()
    fat = pd.to_numeric(df_comida["Grasas (g)"], errors="coerce").sum()
    carb = pd.to_numeric(df_comida["Hidratos (g)"], errors="coerce").sum()
    fib = pd.to_numeric(df_comida["Fibras (g)"], errors="coerce").sum()

    return (
        f"📋 *Resumen Diario ({fecha_str}):*\n\n"
        f"🔥 Consumidas: {round(cal_ing, 1)} kcal\n"
        f"🏃 Ejercicio extra: {round(cal_quem, 1)} kcal\n"
        f"⚖️ Balance ingesta/ejercicio: {round(cal_ing - cal_quem, 1)} kcal\n\n"
        f"💪 Prot: {round(prot, 1)}g | 🥑 Grasas: {round(fat, 1)}g | 🍞 Carb: {round(carb, 1)}g | 🌾 Fib: {round(fib, 1)}g"
    )

async def resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📆 Este Mes", callback_data="resumen_este_mes")],
        [InlineKeyboardButton("📆 Otro Mes", callback_data="resumen_otro_mes")],
    ]
    await update.message.reply_text("📊 *¿Qué resumen mensual deseas consultar?*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def generar_reporte_mensual(user_id: int, mes_anio_str: str) -> str:
    # Obtener registros de consumo
    data = await asyncio.to_thread(_sync_obtener_registros, user_id)
    if not data:
        return "📉 Todavía no tenés registros."
    
    df = pd.DataFrame(data)
    df["Fecha"] = df["Fecha"].astype(str)
    df_filtrado = df[df["Fecha"].str.startswith(mes_anio_str)]
    
    if df_filtrado.empty:
        return f"📆 Sin registros para el mes *{mes_anio_str}*."

    df_filtrado["Calorías (kcal)"] = pd.to_numeric(df_filtrado["Calorías (kcal)"], errors="coerce").fillna(0)
    df_comida = df_filtrado[df_filtrado["Calorías (kcal)"] > 0]
    df_act = df_filtrado[df_filtrado["Calorías (kcal)"] < 0]

    cal_ing = df_comida["Calorías (kcal)"].sum()
    cal_ejercicio = abs(df_act["Calorías (kcal)"].sum())
    prot = pd.to_numeric(df_comida["Proteínas (g)"], errors="coerce").sum()
    fat = pd.to_numeric(df_comida["Grasas (g)"], errors="coerce").sum()
    carb = pd.to_numeric(df_comida["Hidratos (g)"], errors="coerce").sum()

    dias_registrados = df_filtrado["Fecha"].nunique()

    # Buscar perfil correspondiente al mes o ultimo disponible
    perfiles = await asyncio.to_thread(_sync_obtener_perfil, user_id)
    p_match = None
    for p in perfiles:
        if p.get("Mes_Anio") == mes_anio_str:
            p_match = p
            break
    if not p_match and perfiles:
        p_match = perfiles[-1]

    sec_metabolica = ""
    if p_match:
        try:
            sexo = p_match.get("Sexo", "F")
            edad = float(p_match.get("Edad", 30))
            peso = float(p_match.get("Peso_kg", 70))
            altura = float(p_match.get("Altura_cm", 165))
            ocupacion = p_match.get("Ocupacion", "Ama de casa")
            cintura = p_match.get("Cintura_cm", "N/A")

            tmb, get = calcular_metabolismo(sexo, edad, peso, altura, ocupacion)
            total_get_mes = get * dias_registrados
            
            # Balance Net Real = Consumo - Total GET - Ejercicio Extra
            balance_neto = cal_ing - total_get_mes - cal_ejercicio
            
            # Estimación cambio peso (1 kg grasa ≈ 7500 kcal)
            cambio_kg = balance_neto / 7500.0
            cambio_g = cambio_kg * 1000.0

            signo = "+" if cambio_kg > 0 else ""
            
            sec_metabolica = (
                f"\n\n─── *Análisis Metabólico y Estimación Corporal* ───\n"
                f"👤 Sexo: {sexo} | Edad: {int(edad)}a | Peso: {peso}kg | Altura: {altura}cm\n"
                f"📏 Medida de Cintura: {cintura} cm\n"
                f"🔥 Metabolismo Basal (TMB): {tmb} kcal/día\n"
                f"⚡ Gasto Energético Conservador (GET): {get} kcal/día\n\n"
                f"📊 *Resumen de Balance y Cambio Corporal Estimado:*\n"
                f"• Total Consumido: {round(cal_ing, 1)} kcal\n"
                f"• Total Gasto Basal + Ocupación ({dias_registrados} días): -{round(total_get_mes, 1)} kcal\n"
                f"• Total Ejercicio Extra: -{round(cal_ejercicio, 1)} kcal\n"
                f"🔥 *BALANCE CALÓRICO NETO REAL:* {round(balance_neto, 1)} kcal\n"
                f"⚖️ *CAMBIO ESTIMADO DE PESO:* {signo}{round(cambio_kg, 2)} kg ({signo}{round(cambio_g, 1)} g)"
            )
        except Exception as e:
            sec_metabolica = f"\n\n⚠️ No se pudo calcular el análisis metabólico completo: {str(e)}"
    else:
        sec_metabolica = "\n\n⚠️ Cargá tus datos biométricos con /perfil para ver la hoja de estimación corporal."

    return (
        f"📊 *Reporte Nutricional Mensual ({mes_anio_str})*\n\n"
        f"🗓 Días registrados: {dias_registrados}\n"
        f"🔥 Total consumido: {round(cal_ing, 1)} kcal\n"
        f"💪 Prot: {round(prot, 1)}g | 🥑 Grasas: {round(fat, 1)}g | 🍞 Carb: {round(carb, 1)}g"
        f"{sec_metabolica}"
    )

# ==========================================
# GENERADOR DE PDF DE AYUDA
# ==========================================

def generar_pdf_guia() -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle("TitleStyle", parent=styles["Heading1"], fontSize=18, leading=22, textColor="#2e7d32")
    body_style = ParagraphStyle("BodyStyle", parent=styles["Normal"], fontSize=11, leading=15)
    
    story = [
        Paragraph("Manual de Uso - Bot Nutricional de Telegram", title_style),
        Spacer(1, 15),
        Paragraph("<b>1. Registro de Comidas y Ejercicio:</b><br/>Podés escribir de forma directa lo que comiste o el ejercicio realizado (ej: 'Milanesa con ensalada' o 'Caminé 45 minutos') o bien enviar una foto de tu plato. El bot clasificará automáticamente la entrada.", body_style),
        Spacer(1, 10),
        Paragraph("<b>2. Edición de Alimentos Compuestos:</b><br/>Si ingresás un plato compuesto, el bot te desglosará cada alimento y te permitirá modificar el peso en gramos o calorías, recalculando los valores automáticamente.", body_style),
        Spacer(1, 10),
        Paragraph("<b>3. Registro por Fechas:</b><br/>Al confirmar una comida o ejercicio, podrás indicar si corresponde a 'Hoy', 'Ayer' o a 'Otra fecha' específica en formato AAAA-MM-DD.", body_style),
        Spacer(1, 10),
        Paragraph("<b>4. Resumen Diario (/diario):</b><br/>Muestra el detalle consumido y quemado en un día determinado.", body_style),
        Spacer(1, 10),
        Paragraph("<b>5. Resumen Mensual (/resumen):</b><br/>Ofrece una visión integral del mes calculando tu Metabolismo Basal (TMB), Gasto Energético Total (GET) y la estimación de cambio de peso corporal.", body_style),
        Spacer(1, 10),
        Paragraph("<b>6. Perfil Biométrico (/perfil):</b><br/>Permite actualizar datos de edad, peso, altura, cintura y ocupación. Es requisito actualizarlo cada 30 días.", body_style),
    ]
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# ==========================================
# MANEJADOR DE BOTONES (CALLBACK QUERIES)
# ==========================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    # --- AYUDA Y PDF ---
    if data == "download_help_pdf":
        pdf_buffer = await asyncio.to_thread(generar_pdf_guia)
        await query.message.reply_document(document=pdf_buffer, filename="Guia_Funcionamiento_Bot.pdf", caption="📄 Aquí tenés la guía detallada de funcionamiento.")

    # --- FLUJO DE DIARIO ---
    elif data == "diario_hoy":
        fecha = datetime.now().strftime("%Y-%m-%d")
        await query.edit_message_text(await generar_reporte_diario(user_id, fecha), parse_mode="Markdown")
    elif data == "diario_ayer":
        fecha = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        await query.edit_message_text(await generar_reporte_diario(user_id, fecha), parse_mode="Markdown")
    elif data == "diario_otra":
        user_states[user_id] = "waiting_for_diario_custom_date"
        await query.edit_message_text("📅 Ingresá la fecha en formato **AAAA-MM-DD** (ej: `2026-07-15`):", parse_mode="Markdown")

    # --- FLUJO DE RESUMEN MENSUAL ---
    elif data == "resumen_este_mes":
        mes_actual = datetime.now().strftime("%Y-%m")
        await query.edit_message_text(await generar_reporte_mensual(user_id, mes_actual), parse_mode="Markdown")
    elif data == "resumen_otro_mes":
        user_states[user_id] = "waiting_for_resumen_custom_month"
        await query.edit_message_text("📆 Ingresá el mes a consultar en formato **AAAA-MM** (ej: `2026-06`):", parse_mode="Markdown")

    # --- REGISTRO DE MOMENTO Y FECHA ---
    elif data == "ask_momento":
        keyboard = [
            [InlineKeyboardButton("🌅 Desayuno", callback_data="set_momento_Desayuno"), InlineKeyboardButton("☀️ Almuerzo", callback_data="set_momento_Almuerzo")],
            [InlineKeyboardButton("☕ Merienda", callback_data="set_momento_Merienda"), InlineKeyboardButton("🌙 Cena", callback_data="set_momento_Cena")],
            [InlineKeyboardButton("🍎 Snack", callback_data="set_momento_Snack")],
        ]
        await query.edit_message_text("🍽 *¿A qué momento corresponde esta comida?*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("set_momento_"):
        momento = data.replace("set_momento_", "")
        if user_id in user_pending_data:
            user_pending_data[user_id]["momento"] = momento
        keyboard = [
            [InlineKeyboardButton("📅 Hoy", callback_data="save_date_hoy"), InlineKeyboardButton("📅 Ayer", callback_data="save_date_ayer")],
            [InlineKeyboardButton("📅 Otra fecha", callback_data="save_date_otra")],
        ]
        await query.edit_message_text("📅 *¿A qué fecha corresponde este registro?*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == "ask_date":
        keyboard = [
            [InlineKeyboardButton("📅 Hoy", callback_data="save_date_hoy"), InlineKeyboardButton("📅 Ayer", callback_data="save_date_ayer")],
            [InlineKeyboardButton("📅 Otra fecha", callback_data="save_date_otra")],
        ]
        await query.edit_message_text("📅 *¿A qué fecha corresponde este registro?*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("save_date_"):
        opcion = data.replace("save_date_", "")
        if opcion == "hoy":
            fecha = datetime.now().strftime("%Y-%m-%d")
            await query.edit_message_text(await guardar_en_google_sheets(user_id, fecha), parse_mode="Markdown")
        elif opcion == "ayer":
            fecha = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            await query.edit_message_text(await guardar_en_google_sheets(user_id, fecha), parse_mode="Markdown")
        elif opcion == "otra":
            user_states[user_id] = "waiting_for_custom_save_date"
            await query.message.reply_text("📅 Ingresá la fecha en formato **AAAA-MM-DD** (ej: `2026-07-15`):")

    # --- EDICIÓN DE COMPONENTES DE COMIDA Y EJERCICIO ---
    elif data.startswith("edit_item_"):
        idx = int(data.replace("edit_item_", ""))
        user_pending_data[user_id]["editing_item_idx"] = idx
        user_states[user_id] = "waiting_for_item_weight"
        item_name = user_pending_data[user_id]["items"][idx].get("alimento", "alimento")
        await query.message.reply_text(f"✏️ Ingresá el nuevo peso en gramos para *{item_name}* (o enviá `peso, calorias` ej: `200, 350`):", parse_mode="Markdown")
    elif data == "edit_act_cal":
        user_states[user_id] = "waiting_for_act_cal_edit"
        await query.message.reply_text("✏️ Ingresá el nuevo número de calorías quemadas (ej: `250`):")

    # --- FLUJO DE PERFIL BIOMÉTRICO ---
    elif data == "iniciar_perfil":
        user_states[user_id] = "perfil_sexo"
        keyboard = [[InlineKeyboardButton("Femenino", callback_data="p_sexo_F"), InlineKeyboardButton("Masculino", callback_data="p_sexo_M")]]
        await query.message.reply_text("👤 Seleccioná tu sexo:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("p_sexo_"):
        sexo = "F" if "F" in data else "M"
        user_pending_data[user_id] = {"perfil_temp": {"Sexo": sexo}}
        user_states[user_id] = "perfil_edad"
        await query.edit_message_text("🎂 Ingresá tu edad en años (ej: `45`):")

    elif data == "cancel_save":
        user_pending_data.pop(user_id, None)
        user_states.pop(user_id, None)
        await query.edit_message_text("❌ Operación cancelada.")

# ==========================================
# MANEJADOR DE TEXTO COMPLETO Y ESTADOS
# ==========================================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = user_states.get(user_id)
    text = update.message.text.strip()

    # --- ESTADOS DEL PERFIL BIOMÉTRICO ---
    if state == "perfil_edad":
        if text.isdigit():
            user_pending_data[user_id]["perfil_temp"]["Edad"] = int(text)
            user_states[user_id] = "perfil_peso"
            await update.message.reply_text("⚖️ Ingresá tu peso actual en kg (ej: `75.5`):")
        else:
            await update.message.reply_text("⚠️ Por favor ingresá un número entero válido para la edad.")
    elif state == "perfil_peso":
        try:
            peso = float(text.replace(",", "."))
            user_pending_data[user_id]["perfil_temp"]["Peso_kg"] = peso
            user_states[user_id] = "perfil_altura"
            await update.message.reply_text("📏 Ingresá tu altura en cm (ej: `165`):")
        except ValueError:
            await update.message.reply_text("⚠️ Ingresá un número válido para el peso.")
    elif state == "perfil_altura":
        try:
            altura = float(text.replace(",", "."))
            user_pending_data[user_id]["perfil_temp"]["Altura_cm"] = altura
            user_states[user_id] = "perfil_cintura"
            await update.message.reply_text("📐 Ingresá la medida de tu cintura en cm (ej: `85`):")
        except ValueError:
            await update.message.reply_text("⚠️ Ingresá un número válido para la altura.")
    elif state == "perfil_cintura":
        try:
            cintura = float(text.replace(",", "."))
            user_pending_data[user_id]["perfil_temp"]["Cintura_cm"] = cintura
            user_states[user_id] = "perfil_ocupacion"
            await update.message.reply_text("💼 Ingresá tu ocupación / nivel de actividad (ej: `Ama de casa`, `Oficina`, `Moderada`):")
        except ValueError:
            await update.message.reply_text("⚠️ Ingresá un número válido para la medida de la cintura.")
    elif state == "perfil_ocupacion":
        p_data = user_pending_data.get(user_id, {}).get("perfil_temp", {})
        p_data["Ocupacion"] = text
        mes_anio = datetime.now().strftime("%Y-%m")
        fecha_actual = datetime.now().strftime("%Y-%m-%d")

        # Guardar / Sobreescribir registro del mes en hoja Perfil
        client = get_gspread_client()
        sheet = client.open_by_key(SPREADSHEET_KEY)
        p_sheet = obtener_o_crear_hoja_perfil(sheet, user_id)
        records = p_sheet.get_all_records()

        # Buscar si ya existe fila para el mismo mes
        row_to_update = None
        for idx, row in enumerate(records, start=2): # +2 por la cabecera
            if row.get("Mes_Anio") == mes_anio:
                row_to_update = idx
                break

        nueva_fila = [mes_anio, fecha_actual, p_data["Sexo"], p_data["Edad"], p_data["Peso_kg"], p_data["Altura_cm"], p_data["Cintura_cm"], p_data["Ocupacion"]]
        
        if row_to_update:
            p_sheet.update(f"A{row_to_update}:H{row_to_update}", [nueva_fila])
        else:
            p_sheet.append_row(nueva_fila)

        user_states.pop(user_id, None)
        user_pending_data.pop(user_id, None)
        await update.message.reply_text("✅ *¡Perfil biométrico actualizado exitosamente!*", parse_mode="Markdown")

    # --- EDICIÓN MANUAL DE PESO/CALORÍAS DE ALIMENTO ---
    elif state == "waiting_for_item_weight":
        idx = user_pending_data[user_id].get("editing_item_idx")
        item = user_pending_data[user_id]["items"][idx]
        peso_orig = item.get("peso_g", 1) or 1
        
        if "," in text:
            parts = text.split(",")
            nuevo_peso = float(parts[0].strip())
            nuevas_cal = float(parts[1].strip())
            factor = nuevo_peso / peso_orig
        else:
            nuevo_peso = float(text)
            factor = nuevo_peso / peso_orig
            nuevas_cal = round(item.get("calorias", 0) * factor, 1)

        # Recalcular valores proporcionales
        item["peso_g"] = round(nuevo_peso, 1)
        item["calorias"] = round(nuevas_cal, 1)
        item["proteinas_g"] = round(item.get("proteinas_g", 0) * factor, 1)
        item["grasas_g"] = round(item.get("grasas_g", 0) * factor, 1)
        item["hidratos_g"] = round(item.get("hidratos_g", 0) * factor, 1)
        item["fibras_g"] = round(item.get("fibras_g", 0) * factor, 1)

        user_states.pop(user_id, None)
        msg_espera = await update.message.reply_text("🔄 Recalculando alimento...")
        await mostrar_resumen_y_botones(msg_espera, user_id)

    elif state == "waiting_for_act_cal_edit":
        if text.isdigit():
            user_pending_data[user_id]["calorias"] = int(text)
            user_states.pop(user_id, None)
            msg_espera = await update.message.reply_text("🔄 Actualizando ejercicio...")
            await mostrar_confirmacion_actividad(msg_espera, user_id)
        else:
            await update.message.reply_text("⚠️ Ingresá un número válido para las calorías.")

    # --- FECHAS PERSONALIZADAS ---
    elif state == "waiting_for_custom_save_date":
        if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
            await update.message.reply_text(await guardar_en_google_sheets(user_id, text), parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ Formato inválido (`AAAA-MM-DD`). Reintentá:")
    elif state == "waiting_for_diario_custom_date":
        if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
            user_states.pop(user_id, None)
            await update.message.reply_text(await generar_reporte_diario(user_id, text), parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ Formato inválido (`AAAA-MM-DD`). Reintentá:")
    elif state == "waiting_for_resumen_custom_month":
        if re.match(r"^\d{4}-\d{2}$", text):
            user_states.pop(user_id, None)
            await update.message.reply_text(await generar_reporte_mensual(user_id, text), parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ Formato inválido (`AAAA-MM`). Reintentá:")

    else:
        # Procesamiento genérico mediante IA
        await procesar_texto_inteligente(update, context)

# ==========================================
# INICIALIZACIÓN PRINCIPAL DEL BOT
# ==========================================

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_dummy_server, daemon=True)
    server_thread.start()
    print("🌐 Servidor web de Render corriendo en segundo plano.")

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .read_timeout(30)
        .connect_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("perfil", cmd_perfil))
    app.add_handler(CommandHandler("diario", diario))
    app.add_handler(CommandHandler("resumen", resumen))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))

    print(f"🚀 Bot iniciado y actualizado correctamente. Modelo: {MODELO_GROQ}")
    app.run_polling(drop_pending_updates=True)
