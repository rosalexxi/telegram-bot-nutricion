import base64
from datetime import datetime, timedelta
import json
import os
import re
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
# FUNCIONES AUXILIARES Y PARSEO ROBUSTO
# ==========================================

def encode_image(image_path: str) -> str:
    """Convierte la imagen descargada a formato base64 para Groq."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def extract_json(text: str) -> str:
    """
    Extrae el objeto JSON raíz completo { ... }, manejando corchetes
    y llaves internas correctamente sin cortar la lista de alimentos.
    """
    if not text:
        return ""

    # 1. Eliminar bloques de razonamiento interno <think>...</think>
    text = re.sub(r"<think>.*?(?:</think>|$)", "", text, flags=re.DOTALL).strip()

    # 2. Eliminar bloques markdown ```json ... ```
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"^```\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)

    # 3. Extraer el bloque que empieza en la primera '{' y termina en la última '}'
    start_idx = text.find("{")
    end_idx = text.rfind("}")

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        return text[start_idx : end_idx + 1].strip()

    return text.strip()


def parse_response_to_items(raw_text: str) -> list:
    """Procesa el texto recibido de la API e intenta convertirlo en lista de items."""
    clean_text = extract_json(raw_text)

    if not clean_text:
        raise ValueError(
            f"El modelo no devolvió una respuesta utilizable.\nTexto recibido: {raw_text[:100]}"
        )

    try:
        data = json.loads(clean_text)
    except json.JSONDecodeError:
        try:
            fixed_text = clean_text.replace("'", '"')
            data = json.loads(fixed_text)
        except Exception:
            raise ValueError(
                f"No se pudo decodificar el JSON. Texto extraído:\n{clean_text[:150]}"
            )

    if isinstance(data, dict):
        for val in data.values():
            if isinstance(val, list):
                return val
        return [data]

    if isinstance(data, list):
        return data

    raise ValueError("El formato extraído no contiene una lista de alimentos válida.")


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


# ==========================================
# PROCESAMIENTO DE IMAGEN Y TEXTO CON GROQ
# ==========================================

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_states.pop(user_id, None)

    msg_espera = await update.message.reply_text("🔍 Analizando plato con Groq...")

    photo_file = await update.message.photo[-1].get_file()
    photo_path = f"temp_{user_id}.jpg"
    await photo_file.download_to_drive(photo_path)

    try:
        base64_image = encode_image(photo_path)

        system_instruction = (
            "You are a strict JSON generator. Do NOT think step-by-step. "
            "Do NOT output <think> tags. Output ONLY a valid JSON object starting with '{' and ending with '}'."
        )

        prompt = """
        Analiza esta imagen e identifica sus alimentos.
        Responde ÚNICAMENTE con un JSON en formato estricto RFC 8259.
        Sé conciso con los nombres de los alimentos.

        Ejemplo del formato esperado:
        {
          "items": [
            {"alimento": "Pechuga de pollo", "peso_g": 150, "calorias": 240, "proteinas_g": 31, "grasas_g": 3.5, "hidratos_g": 0, "fibra_g": 0}
          ]
        }
        """

        response = groq_client.chat.completions.create(
            model=MODELO_GROQ,
            messages=[
                {"role": "system", "content": system_instruction},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                    ],
                },
            ],
            temperature=0.1,
            max_tokens=4000,
            timeout=30.0,
        )

        raw_text = response.choices[0].message.content
        items = parse_response_to_items(raw_text)

        user_pending_data[user_id] = {
            "tipo": "comida",
            "items": items,
            "momento": "No especificado",
        }
        await mostrar_resumen_y_botones(msg_espera, user_id, es_edicion=False)

    except Exception as e:
        await msg_espera.edit_text(f"❌ Error al procesar la imagen: {str(e)}")
    finally:
        if os.path.exists(photo_path):
            os.remove(photo_path)


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
    Identifica los alimentos y estima sus valores nutricionales.
    Responde ÚNICAMENTE con un JSON estricto usando comillas dobles:
    {{
      "items": [
        {{"alimento": "nombre", "peso_g": 0, "calorias": 0, "proteinas_g": 0, "grasas_g": 0, "hidratos_g": 0, "fibra_g": 0}}
      ]
    }}
    """

    try:
        response = groq_client.chat.completions.create(
            model=MODELO_GROQ,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=4000,
            timeout=30.0,
        )

        raw_text = response.choices[0].message.content
        items = parse_response_to_items(raw_text)

        user_pending_data[user_id] = {
            "tipo": "comida",
            "items": items,
            "momento": "No especificado",
        }
        await mostrar_resumen_y_botones(msg_espera, user_id, es_edicion=False)

    except Exception as e:
        await msg_espera.edit_text(f"❌ Error al interpretar el texto: {str(e)}")


async def mostrar_resumen_y_botones(message, user_id: int, es_edicion=False):
    data = user_pending_data[user_id]
    items = data["items"]

    reply_msg = (
        f"📊 *Análisis de los alimentos:*\n\n"
        if not es_edicion
        else f"✏️ *Análisis actualizado:*\n\n"
    )
    t_cal, t_prot, t_fat, t_carb, t_fib = 0, 0, 0, 0, 0

    for item in items:
        reply_msg += (
            f"• *{item.get('alimento', 'Alimento')}* ({item.get('peso_g', 0)}g):\n"
            f"  └ {item.get('calorias', 0)} kcal | P: {item.get('proteinas_g', 0)}g | G: {item.get('grasas_g', 0)}g | H: {item.get('hidratos_g', 0)}g | F: {item.get('fibra_g', 0)}g\n"
        )
        t_cal += item.get("calorias", 0)
        t_prot += item.get("proteinas_g", 0)
        t_fat += item.get("grasas_g", 0)
        t_carb += item.get("hidratos_g", 0)
        t_fib += item.get("fibra_g", 0)

    reply_msg += (
        f"\n🔥 *Totales:* {round(t_cal, 1)} kcal\n"
        f"💪 Prot: {round(t_prot, 1)}g | 🥑 Grasas: {round(t_fat, 1)}g\n"
        f"🍞 Hidratos: {round(t_carb, 1)}g | 🌾 Fibra: {round(t_fib, 1)}g\n\n"
        "¿Qué querés hacer?"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Confirmar", callback_data="ask_momento")],
        [InlineKeyboardButton("✏️ Editar", callback_data="edit_data")],
        [InlineKeyboardButton("❌ Descartar", callback_data="cancel_save")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if hasattr(message, "edit_text"):
        await message.edit_text(
            reply_msg, parse_mode="Markdown", reply_markup=reply_markup
        )
    else:
        await message.reply_text(
            reply_msg, parse_mode="Markdown", reply_markup=reply_markup
        )


# ==========================================
# MÓDULO DE ACTIVIDAD FÍSICA
# ==========================================

async def cmd_actividad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_states.pop(user_id, None)

    keyboard = [
        [
            InlineKeyboardButton("🚶 Caminata", callback_data="act_Caminata"),
            InlineKeyboardButton("🏊 Aquagym", callback_data="act_Aquagym"),
        ],
        [
            InlineKeyboardButton("🚴 Bicicleta", callback_data="act_Bicicleta"),
            InlineKeyboardButton("🏋 Gimnasio", callback_data="act_Gimnasio"),
        ],
        [InlineKeyboardButton("✏ Otra", callback_data="act_Otra")],
    ]
    await update.message.reply_text(
        "🏃 *¿Qué actividad física realizaste?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_actividad_duracion(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.message.from_user.id
    texto = update.message.text
    actividad = user_pending_data.get(user_id, {}).get("actividad_nombre", "Ejercicio")

    msg_espera = await update.message.reply_text("🔄 Estimando calorías...")

    system_instruction = (
        "You are a strict JSON generator. Do NOT think step-by-step. "
        "Do NOT output <think> tags. Output ONLY a valid JSON object starting with '{' and ending with '}'."
    )

    prompt = f"""
    Actividad física: "{actividad}".
    Duración: "{texto}".
    Estima las calorías quemadas.
    Responde strictly en formato JSON con comillas dobles:
    {{"actividad": "{actividad}", "duracion": "{texto}", "calorias": 320}}
    """

    try:
        response = groq_client.chat.completions.create(
            model=MODELO_GROQ,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1000,
            timeout=30.0,
        )

        clean_text = extract_json(response.choices[0].message.content)
        act_info = json.loads(clean_text)

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

    reply_msg = (
        f"🏃 *Actividad:* {data['actividad']}\n"
        f"⏱ *Duración:* {data['duracion']}\n"
        f"🔥 *Calorías estimadas:* {data['calorias']} kcal\n\n"
        "¿Querés aceptar o editar?"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Aceptar", callback_data="ask_date"),
            InlineKeyboardButton("✏ Editar", callback_data="edit_act_cal"),
        ],
        [InlineKeyboardButton("❌ Descartar", callback_data="cancel_save")],
    ]

    if hasattr(message, "edit_text"):
        await message.edit_text(
            reply_msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        await message.reply_text(
            reply_msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


# ==========================================
# PREGUNTAS INTERACTIVAS Y GUARDADO EXCEL
# ==========================================

async def pedir_momento_comida(query):
    keyboard = [
        [
            InlineKeyboardButton("🌅 Desayuno", callback_data="set_momento_Desayuno"),
            InlineKeyboardButton("☀️ Almuerzo", callback_data="set_momento_Almuerzo"),
        ],
        [
            InlineKeyboardButton("☕ Merienda", callback_data="set_momento_Merienda"),
            InlineKeyboardButton("🌙 Cena", callback_data="set_momento_Cena"),
        ],
        [InlineKeyboardButton("🍎 Snack", callback_data="set_momento_Snack")],
    ]
    await query.edit_message_text(
        "🍽 *¿A qué momento corresponde esta comida?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def pedir_fecha(query):
    keyboard = [
        [
            InlineKeyboardButton("📅 Hoy", callback_data="save_date_hoy"),
            InlineKeyboardButton("📅 Ayer", callback_data="save_date_ayer"),
        ],
        [InlineKeyboardButton("📅 Otra fecha", callback_data="save_date_otra")],
    ]
    await query.edit_message_text(
        "📅 *¿A qué fecha corresponde este registro?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def guardar_en_excel(user_id: int, fecha_str: str) -> str:
    excel_file = f"registros_{user_id}.xlsx"
    pending = user_pending_data.get(user_id)

    if not pending:
        return "No hay datos pendientes."

    rows = []
    if pending["tipo"] == "comida":
        momento = pending.get("momento", "Sin especificar")
        for item in pending["items"]:
            rows.append({
                "Fecha": fecha_str,
                "Tipo": "Comida",
                "Momento/Actividad": momento,
                "Alimento/Detalle": item.get("alimento", "Alimento desconocido"),
                "Peso (g)": item.get("peso_g", 0),
                "Calorías (kcal)": item.get("calorias", 0),
                "Proteínas (g)": item.get("proteinas_g", 0),
                "Grasas (g)": item.get("grasas_g", 0),
                "Hidratos (g)": item.get("hidratos_g", 0),
                "Fibra (g)": item.get("fibra_g", 0),
            })
    elif pending["tipo"] == "actividad":
        rows.append({
            "Fecha": fecha_str,
            "Tipo": "Actividad Física",
            "Momento/Actividad": pending["actividad"],
            "Alimento/Detalle": f"Duración: {pending['duracion']}",
            "Peso (g)": 0,
            "Calorías (kcal)": -abs(pending["calorias"]),
            "Proteínas (g)": 0,
            "Grasas (g)": 0,
            "Hidratos (g)": 0,
            "Fibra (g)": 0,
        })

    df_new = pd.DataFrame(rows)

    if os.path.exists(excel_file):
        df_existing = pd.read_excel(excel_file)
        if "Usuario" in df_existing.columns:
            df_existing = df_existing.drop(columns=["Usuario"])
        df_final = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_final = df_new

    df_final.to_excel(excel_file, index=False)
    user_pending_data.pop(user_id, None)
    user_states.pop(user_id, None)

    return f"💾 ¡Guardado correctamente en tu Excel (`{excel_file}`) para la fecha *{fecha_str}*!"


# ==========================================
# MANEJADORES DE BOTONES Y TEXTO
# ==========================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    if data == "ask_momento":
        await pedir_momento_comida(query)

    elif data.startswith("set_momento_"):
        momento = data.replace("set_momento_", "")
        if user_id in user_pending_data:
            user_pending_data[user_id]["momento"] = momento
        await pedir_fecha(query)

    elif data == "ask_date":
        await pedir_fecha(query)

    elif data.startswith("save_date_"):
        opcion = data.replace("save_date_", "")
        if opcion == "hoy":
            fecha = datetime.now().strftime("%Y-%m-%d")
            res = await guardar_en_excel(user_id, fecha)
            await query.edit_message_text(res, parse_mode="Markdown")
        elif opcion == "ayer":
            fecha = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            res = await guardar_en_excel(user_id, fecha)
            await query.edit_message_text(res, parse_mode="Markdown")
        elif opcion == "otra":
            user_states[user_id] = "waiting_for_custom_date"
            await query.message.reply_text(
                "📅 Ingresá la fecha en formato **AAAA-MM-DD** (Ej: `2026-03-15`):"
            )

    elif data == "edit_data":
        user_states[user_id] = "waiting_for_correction"
        await query.message.reply_text(
            "📝 Escribime las correcciones.\nEjemplo: *'180 g de milanesa de pescado al horno, 150 g de papa hervida y 1 huevo'*"
        )

    elif data == "edit_act_cal":
        user_states[user_id] = "waiting_for_cal_edit"
        await query.message.reply_text(
            "✏️ Escribí el número de calorías (Ejemplo: `310`):"
        )

    elif data.startswith("act_"):
        act_tipo = data.replace("act_", "")
        if act_tipo == "Otra":
            user_states[user_id] = "waiting_for_custom_act_name"
            await query.message.reply_text("✏️ Escribí el nombre de la actividad:")
        else:
            user_pending_data[user_id] = {"actividad_nombre": act_tipo}
            user_states[user_id] = "waiting_for_act_duration"
            await query.message.reply_text(
                f"⏱ ¿Cuánto tiempo duró *{act_tipo}*? (Ejemplo: `45 min`):",
                parse_mode="Markdown",
            )

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
            await update.message.reply_text("No hay datos pendientes de edición.")
            user_states.pop(user_id, None)
            return

        try:
            msg_espera = await update.message.reply_text(
                "🔄 Recalculando con tus correcciones..."
            )
        except Exception:
            msg_espera = update.message

        system_instruction = (
            "You are a strict JSON generator. Do NOT think step-by-step. "
            "Do NOT output <think> tags. Output ONLY a valid JSON object starting with '{' and ending with '}'."
        )

        prompt = f"""
        El usuario está corrigiendo un registro de alimentos.
        
        NUEVA DESCRIPCIÓN DEL USUARIO CON LOS ALIMENTOS Y PESOS:
        "{text}"

        INSTRUCCIONES OBLIGATORIAS:
        1. Desglosa TODOS los alimentos mencionados por el usuario en items individuales (por ejemplo: milanesa, papa, huevo).
        2. Calcula o estima los nutrientes para CADA uno de los alimentos descritos.
        3. Genera un JSON estricto con la lista completa. NO omitas ningún ingrediente mencionado.

        Formato esperado:
        {{
          "items": [
            {{"alimento": "Milanesa de pescado", "peso_g": 180, "calorias": 340, "proteinas_g": 29, "grasas_g": 16, "hidratos_g": 20, "fibra_g": 2}},
            {{"alimento": "Papa hervida", "peso_g": 150, "calorias": 130, "proteinas_g": 3, "grasas_g": 0.2, "hidratos_g": 30, "fibra_g": 3}},
            {{"alimento": "Huevo hervido", "peso_g": 50, "calorias": 78, "proteinas_g": 6.3, "grasas_g": 5.3, "hidratos_g": 0.6, "fibra_g": 0}}
          ]
        }}
        """
        try:
            response = groq_client.chat.completions.create(
                model=MODELO_GROQ,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=4000,
                timeout=30.0,
            )
            raw_text = response.choices[0].message.content
            updated_items = parse_response_to_items(raw_text)

            user_pending_data[user_id]["items"] = updated_items
            user_states.pop(user_id, None)
            await mostrar_resumen_y_botones(msg_espera, user_id, es_edicion=True)

        except Exception as e:
            if hasattr(msg_espera, "edit_text"):
                await msg_espera.edit_text(
                    f"❌ Error al procesar la corrección: {str(e)}"
                )
            else:
                await update.message.reply_text(
                    f"❌ Error al procesar la corrección: {str(e)}"
                )

    elif state == "waiting_for_custom_act_name":
        user_pending_data[user_id] = {"actividad_nombre": text}
        user_states[user_id] = "waiting_for_act_duration"
        await update.message.reply_text(
            f"⏱ ¿Cuánto tiempo realizaste de *{text}*? (Ej: `45 min`):",
            parse_mode="Markdown",
        )

    elif state == "waiting_for_act_duration":
        await handle_actividad_duracion(update, context)

    elif state == "waiting_for_cal_edit":
        if text.isdigit():
            user_pending_data[user_id]["calorias"] = int(text)
            user_states.pop(user_id, None)
            await mostrar_confirmacion_actividad(update.message, user_id)
        else:
            await update.message.reply_text("Por favor ingresá solo un número válido.")

    elif state == "waiting_for_custom_date":
        if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
            res = await guardar_en_excel(user_id, text)
            await update.message.reply_text(res, parse_mode="Markdown")
        else:
            await update.message.reply_text(
                "⚠️ Formato inválido. Usá `AAAA-MM-DD` (Ej: `2026-03-15`)."
            )

    else:
        await procesar_texto_comida(update, context)


async def resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    excel_file = f"registros_{user_id}.xlsx"

    if not os.path.exists(excel_file):
        await update.message.reply_text("📉 Todavía no tenés ningún registro guardado.")
        return

    try:
        df = pd.read_excel(excel_file)
        hoy = datetime.now().strftime("%Y-%m-%d")
        df_hoy = df[df["Fecha"] == hoy]

        if df_hoy.empty:
            await update.message.reply_text(
                f"📅 No hay registros guardados para hoy ({hoy})."
            )
            return

        df_comida = df_hoy[df_hoy["Tipo"] == "Comida"]
        df_act = df_hoy[df_hoy["Tipo"] == "Actividad Física"]

        cal_ingresadas = df_comida["Calorías (kcal)"].sum()
        cal_quemadas = abs(df_act["Calorías (kcal)"].sum())
        prot = df_comida["Proteínas (g)"].sum()
        fat = df_comida["Grasas (g)"].sum()
        carb = df_comida["Hidratos (g)"].sum()
        fib = df_comida["Fibra (g)"].sum()

        msg = f"📋 *Resumen diario ({hoy}):*\n\n"

        if not df_comida.empty:
            msg += "🍽 *Comidas:*\n"
            for _, row in df_comida.iterrows():
                msg += f"• [{row['Momento/Actividad']}] *{row['Alimento/Detalle']}*: {row['Peso (g)']}g | {row['Calorías (kcal)']} kcal\n"

        if not df_act.empty:
            msg += "\n🏃 *Actividad Física:*\n"
            for _, row in df_act.iterrows():
                msg += f"• *{row['Momento/Actividad']}* ({row['Alimento/Detalle']}): -{abs(row['Calorías (kcal)'])} kcal\n"

        msg += f"\n🔥 *Calorías Consumidas:* {round(cal_ingresadas, 1)} kcal\n"
        msg += f"🏃 *Calorías Quemadas:* {round(cal_quemadas, 1)} kcal\n"
        msg += f"⚖️ *Balance Neto:* {round(cal_ingresadas - cal_quemadas, 1)} kcal\n\n"
        msg += f"💪 Proteínas: {round(prot, 1)}g | 🥑 Grasas: {round(fat, 1)}g\n"
        msg += f"🍞 Hidratos: {round(carb, 1)}g | 🌾 Fibra: {round(fib, 1)}g\n"

        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Error al leer el Excel: {str(e)}")


# ==========================================
# INICIALIZACIÓN DE TELEGRAM
# ==========================================

if __name__ == "__main__":
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

    print(f"🚀 Bot iniciado correctamente. Modelo: {MODELO_GROQ}")
    app.run_polling()
