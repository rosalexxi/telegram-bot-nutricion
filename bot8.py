import asyncio
import base64
from datetime import datetime, timedelta
import json
import os
import re
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
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
# CONFIGURACIÓN DE GOOGLE SHEETS
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
        headers = [
            "User_ID", "Fecha", "Tipo", "Momento/Actividad", 
            "Alimento/Detalle", "Peso (g)", "Calorías (kcal)", 
            "Proteínas (g)", "Grasas (g)", "Hidratos (g)"
        ]
        worksheet.append_row(headers)
    return worksheet


# ==========================================
# SERVIDOR WEB FALSO PARA RENDER
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
        </head>
        <body>
            <h1>🤖 Bot de Telegram de Nutrición Funcionando</h1>
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

def parse_response_to_items(raw_text: str) -> list:
    clean_text = extract_json(raw_text)
    if not clean_text:
        raise ValueError("El modelo no devolvió una respuesta utilizable.")
    try:
        data = json.loads(clean_text)
    except json.JSONDecodeError:
        try:
            fixed_text = clean_text.replace("'", '"')
            data = json.loads(fixed_text)
        except Exception:
            raise ValueError("No se pudo decodificar el JSON.")
    if isinstance(data, dict):
        for val in data.values():
            if isinstance(val, list):
                return val
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError("El formato extraído no contiene una lista válida.")


# ==========================================
# COMANDOS PRINCIPALES DE TELEGRAM
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.from_user.first_name
    await update.message.reply_text(
        f"¡Hola {user_name}! 👋\n\n"
        "• Mandame una foto de tu plato o un texto para analizarlo con IA.\n"
        "• Usá /actividad para registrar ejercicio físico.\n"
        "• Usá /resumen para ver el consumo del día."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_states.pop(user_id, None)
    msg_espera = await update.message.reply_text("🔍 Analizando plato con Groq...")
    
    try:
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        system_instruction = (
            "You are a strict JSON generator. Do NOT think step-by-step. "
            "Do NOT output <think> tags. Output ONLY a valid JSON object starting with '{' and ending with '}'."
        )
        prompt = """
        Analiza esta imagen e identifica sus alimentos.
        Responde ÚNICAMENTE con un JSON en formato estricto RFC 8259:
        {
          "items": [
            {"alimento": "Pechuga de pollo", "peso_g": 150, "calorias": 240, "proteinas_g": 31, "grasas_g": 3.5, "hidratos_g": 0}
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
        items = parse_response_to_items(response.choices[0].message.content)
        user_pending_data[user_id] = {"tipo": "comida", "items": items, "momento": "No especificado"}
        await mostrar_resumen_y_botones(msg_espera, user_id, es_edicion=False)
    except Exception as e:
        await msg_espera.edit_text(f"❌ Error al procesar la imagen: {str(e)}")

async def procesar_texto_comida(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    texto = update.message.text
    msg_espera = await update.message.reply_text("🔍 Procesando tu texto...")
    system_instruction = (
        "You are a strict JSON generator. Do NOT think step-by-step. "
        "Do NOT output <think> tags. Output ONLY a valid JSON object starting with '{' and ending with '}'."
    )
    prompt = f"""
    El usuario comió: "{texto}".
    Identifica alimentos y valores. Responde en JSON estricto:
    {{"items": [{{"alimento": "nombre", "peso_g": 0, "calorias": 0, "proteinas_g": 0, "grasas_g": 0, "hidratos_g": 0}}]}}
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
        items = parse_response_to_items(response.choices[0].message.content)
        user_pending_data[user_id] = {"tipo": "comida", "items": items, "momento": "No especificado"}
        await mostrar_resumen_y_botones(msg_espera, user_id, es_edicion=False)
    except Exception as e:
        await msg_espera.edit_text(f"❌ Error al interpretar el texto: {str(e)}")

async def mostrar_resumen_y_botones(message, user_id: int, es_edicion=False):
    data = user_pending_data[user_id]
    items = data["items"]
    reply_msg = "📊 *Análisis de los alimentos:*\n\n" if not es_edicion else "✏️ *Análisis actualizado:*\n\n"
    t_cal, t_prot, t_fat, t_carb = 0, 0, 0, 0
    for item in items:
        reply_msg += (
            f"• *{item.get('alimento', 'Alimento')}* ({item.get('peso_g', 0)}g):\n"
            f"  └ {item.get('calorias', 0)} kcal | P: {item.get('proteinas_g', 0)}g | G: {item.get('grasas_g', 0)}g | H: {item.get('hidratos_g', 0)}g\n"
        )
        t_cal += item.get("calorias", 0)
        t_prot += item.get("proteinas_g", 0)
        t_fat += item.get("grasas_g", 0)
        t_carb += item.get("hidratos_g", 0)

    reply_msg += (
        f"\n🔥 *Totales:* {round(t_cal, 1)} kcal\n"
        f"💪 Prot: {round(t_prot, 1)}g | 🥑 Grasas: {round(t_fat, 1)}g | 🍞 Hidratos: {round(t_carb, 1)}g\n\n"
        "¿Qué querés hacer?"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Confirmar", callback_data="ask_momento")],
        [InlineKeyboardButton("✏️ Editar", callback_data="edit_data")],
        [InlineKeyboardButton("❌ Descartar", callback_data="cancel_save")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if hasattr(message, "edit_text"):
        await message.edit_text(reply_msg, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await message.reply_text(reply_msg, parse_mode="Markdown", reply_markup=reply_markup)

async def cmd_actividad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_states.pop(user_id, None)
    keyboard = [
        [InlineKeyboardButton("🚶 Caminata", callback_data="act_Caminata"), InlineKeyboardButton("🏊 Aquagym", callback_data="act_Aquagym")],
        [InlineKeyboardButton("🚴 Bicicleta", callback_data="act_Bicicleta"), InlineKeyboardButton("🏋 Gimnasio", callback_data="act_Gimnasio")],
        [InlineKeyboardButton("✏ Otra", callback_data="act_Otra")],
    ]
    await update.message.reply_text("🏃 *¿Qué actividad física realizaste?*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_actividad_duracion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    texto = update.message.text
    actividad = user_pending_data.get(user_id, {}).get("actividad_nombre", "Ejercicio")
    msg_espera = await update.message.reply_text("🔄 Estimando calorías...")
    system_instruction = "You are a strict JSON generator. Do NOT think step-by-step. Output ONLY valid JSON."
    prompt = f'Actividad: "{actividad}", Duración: "{texto}". Estima calorías en JSON: {{"actividad": "{actividad}", "duracion": "{texto}", "calorias": 320}}'
    try:
        def _call_groq():
            return groq_client.chat.completions.create(
                model=MODELO_GROQ,
                messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1000,
                timeout=30.0,
            )

        response = await asyncio.to_thread(_call_groq)
        act_info = json.loads(extract_json(response.choices[0].message.content))
        user_pending_data[user_id] = {
            "tipo": "actividad",
            "actividad": act_info.get("actividad", actividad),
            "duracion": act_info.get("duracion", texto),
            "calorias": int(act_info.get("calorias", 0)),
        }
        user_states.pop(user_id, None)
        await mostrar_confirmacion_actividad(msg_espera, user_id)
    except Exception as e:
        await msg_espera.edit_text(f"❌ Error al estimar: {str(e)}")

async def mostrar_confirmacion_actividad(message, user_id: int):
    data = user_pending_data[user_id]
    reply_msg = f"🏃 *Actividad:* {data['actividad']}\n⏱ *Duración:* {data['duracion']}\n🔥 *Calorías estimadas:* {data['calorias']} kcal\n\n¿Querés aceptar o editar?"
    keyboard = [
        [InlineKeyboardButton("✅ Aceptar", callback_data="ask_date"), InlineKeyboardButton("✏ Editar", callback_data="edit_act_cal")],
        [InlineKeyboardButton("❌ Descartar", callback_data="cancel_save")],
    ]
    if hasattr(message, "edit_text"):
        await message.edit_text(reply_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await message.reply_text(reply_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

def _sync_guardar_sheets(user_id: int, fecha_str: str, pending: dict):
    client = get_gspread_client()
    spreadsheet = client.open_by_key(SPREADSHEET_KEY)
    worksheet = obtener_o_crear_hoja_usuario(spreadsheet, user_id)
    rows_to_append = []
    if pending["tipo"] == "comida":
        momento = pending.get("momento", "Sin especificar")
        for item in pending["items"]:
            rows_to_append.append([str(user_id), fecha_str, "Comida", momento, item.get("alimento", "Desconocido"), item.get("peso_g", 0), item.get("calorias", 0), item.get("proteinas_g", 0), item.get("grasas_g", 0), item.get("hidratos_g", 0)])
    elif pending["tipo"] == "actividad":
        rows_to_append.append([str(user_id), fecha_str, "Actividad Física", pending["actividad"], f"Duración: {pending['duracion']}", 0, -abs(pending["calorias"]), 0, 0, 0])
    for row in rows_to_append:
        worksheet.append_row(row)

async def guardar_en_google_sheets(user_id: int, fecha_str: str) -> str:
    pending = user_pending_data.get(user_id)
    if not pending:
        return "No hay datos pendientes."
    try:
        await asyncio.to_thread(_sync_guardar_sheets, user_id, fecha_str, pending)
        user_pending_data.pop(user_id, None)
        user_states.pop(user_id, None)
        return f"💾 ¡Guardado correctamente en tu Google Sheets para la fecha *{fecha_str}*!"
    except Exception as e:
        return f"❌ Error al guardar en Google Sheets: {str(e)}"

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "ask_momento":
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
            user_states[user_id] = "waiting_for_custom_date"
            await query.message.reply_text("📅 Ingresá la fecha en formato **AAAA-MM-DD** (Ej: `2026-03-15`):")
    elif data == "edit_data":
        user_states[user_id] = "waiting_for_correction"
        await query.message.reply_text("📝 Escribime las correcciones.")
    elif data == "edit_act_cal":
        user_states[user_id] = "waiting_for_cal_edit"
        await query.message.reply_text("✏️ Escribí el número de calorías (Ejemplo: `310`):")
    elif data.startswith("act_"):
        act_tipo = data.replace("act_", "")
        if act_tipo == "Otra":
            user_states[user_id] = "waiting_for_custom_act_name"
            await query.message.reply_text("✏️ Escribí el nombre de la actividad:")
        else:
            user_pending_data[user_id] = {"actividad_nombre": act_tipo}
            user_states[user_id] = "waiting_for_act_duration"
            await query.message.reply_text(f"⏱ ¿Cuánto tiempo duró *{act_tipo}*?", parse_mode="Markdown")
    elif data == "cancel_save":
        user_pending_data.pop(user_id, None)
        user_states.pop(user_id, None)
        await query.edit_message_text("❌ Registro cancelado.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = user_states.get(user_id)
    text = update.message.text

    if state == "waiting_for_correction":
        current_data = user_pending_data.get(user_id, {}).get("items")
        if not current_data:
            await update.message.reply_text("No hay datos pendientes.")
            user_states.pop(user_id, None)
            return
        msg_espera = await update.message.reply_text("🔄 Recalculando...")
        system_instruction = "You are a strict JSON generator. Output ONLY valid JSON."
        prompt = f'Datos actuales: {json.dumps(current_data)}. Corrección del usuario: "{text}". Ajusta los items y responde en JSON: {{"items": [{{"alimento": "nombre", "peso_g": 0, "calorias": 0, "proteinas_g": 0, "grasas_g": 0, "hidratos_g": 0}}]}}'
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
            user_pending_data[user_id]["items"] = parse_response_to_items(response.choices[0].message.content)
            user_states.pop(user_id, None)
            await mostrar_resumen_y_botones(msg_espera, user_id, es_edicion=True)
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    elif state == "waiting_for_custom_act_name":
        user_pending_data[user_id] = {"actividad_nombre": text}
        user_states[user_id] = "waiting_for_act_duration"
        await update.message.reply_text(f"⏱ ¿Cuánto tiempo de *{text}*?", parse_mode="Markdown")
    elif state == "waiting_for_act_duration":
        await handle_actividad_duracion(update, context)
    elif state == "waiting_for_cal_edit":
        if text.isdigit():
            user_pending_data[user_id]["calorias"] = int(text)
            user_states.pop(user_id, None)
            await mostrar_confirmacion_actividad(update.message, user_id)
        else:
            await update.message.reply_text("Ingresá un número válido.")
    elif state == "waiting_for_custom_date":
        if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
            await update.message.reply_text(await guardar_en_google_sheets(user_id, text), parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ Formato inválido (`AAAA-MM-DD`).")
    else:
        await procesar_texto_comida(update, context)

def _sync_obtener_resumen(user_id: int):
    client = get_gspread_client()
    worksheet = obtener_o_crear_hoja_usuario(client.open_by_key(SPREADSHEET_KEY), user_id)
    return worksheet.get_all_records()

async def resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    try:
        data = await asyncio.to_thread(_sync_obtener_resumen, user_id)
        if not data:
            await update.message.reply_text("📉 Todavía no tenés registros.")
            return
        df = pd.DataFrame(data)
        hoy = datetime.now().strftime("%Y-%m-%d")
        df["Fecha"] = df["Fecha"].astype(str)
        df_hoy = df[df["Fecha"] == hoy]
        if df_hoy.empty:
            await update.message.reply_text(f"📅 Sin registros para hoy ({hoy}).")
            return
        df_comida = df_hoy[df_hoy["Tipo"] == "Comida"]
        df_act = df_hoy[df_hoy["Tipo"] == "Actividad Física"]
        cal_ing = pd.to_numeric(df_comida["Calorías (kcal)"], errors="coerce").sum()
        cal_quem = abs(pd.to_numeric(df_act["Calorías (kcal)"], errors="coerce").sum())
        prot = pd.to_numeric(df_comida["Proteínas (g)"], errors="coerce").sum()
        fat = pd.to_numeric(df_comida["Grasas (g)"], errors="coerce").sum()
        carb = pd.to_numeric(df_comida["Hidratos (g)"], errors="coerce").sum()
        
        msg = f"📋 *Resumen diario ({hoy}):*\n\n🔥 Consumidas: {round(cal_ing, 1)} kcal\n🏃 Quemadas: {round(cal_quem, 1)} kcal\n⚖️ Balance: {round(cal_ing - cal_quem, 1)} kcal\n\n💪 Prot: {round(prot, 1)}g | 🥑 Grasas: {round(fat, 1)}g | 🍞 Hidratos: {round(carb, 1)}g"
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


# ==========================================
# INICIALIZACIÓN CON SERVIDOR WEB EMBEBIDO
# ==========================================

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_dummy_server, daemon=True)
    server_thread.start()
    print("🌐 Servidor web corriendo en segundo plano.")

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .read_timeout(30)
        .connect_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("actividad", cmd_actividad))
    app.add_handler(CommandHandler("resumen", resumen))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))

    print(f"🚀 Bot conectado a Google Sheets. Modelo: {MODELO_GROQ}")
    app.run_polling(drop_pending_updates=True)

