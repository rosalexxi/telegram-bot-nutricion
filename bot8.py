import base64
from datetime import datetime, timedelta
import io
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

# Librerías para generación de PDF
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
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
# FUNCIONES AUXILIARES Y PARSEO ROBUSTO
# ==========================================

def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def extract_json(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<think>.*?(?:</think>|$)", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"^```\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)

    match_dict = re.search(r"(\{.*)", text, re.DOTALL)
    json_str = match_dict.group(1).strip() if match_dict else text.strip()

    json_str = re.sub(r",\s*$", "", json_str)
    if json_str.count('"') % 2 != 0:
        json_str += '"'

    open_brackets = json_str.count("[") - json_str.count("]")
    open_braces = json_str.count("{") - json_str.count("}")

    if open_braces > 0 and open_brackets > 0:
        json_str += "}" * open_braces + "]" + "}" * (open_braces - 1)
    else:
        json_str += "}" * max(0, open_braces)
        json_str += "]" * max(0, open_brackets)

    return json_str.strip()


def parse_response_to_items(raw_text: str) -> list:
    clean_text = extract_json(raw_text)
    if not clean_text:
        raise ValueError("El modelo no devolvió una respuesta utilizable.")

    try:
        data = json.loads(clean_text)
    except json.JSONDecodeError:
        fixed_text = clean_text.replace("'", '"')
        data = json.loads(fixed_text)

    if isinstance(data, dict):
        for val in data.values():
            if isinstance(val, list):
                return val
        return [data]

    if isinstance(data, list):
        return data

    raise ValueError("El formato extraído no es válido.")


# ==========================================
# GENERADOR DE PDF MENSUAL
# ==========================================

def generar_pdf_mes(user_id: int, año: int, mes: int) -> io.BytesIO:
    excel_file = f"registros_{user_id}.xlsx"
    if not os.path.exists(excel_file):
        return None

    df = pd.read_excel(excel_file)
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    
    # Filtrar por año y mes
    df_mes = df[(df["Fecha"].dt.year == año) & (df["Fecha"].dt.month == mes)]

    if df_mes.empty:
        return None

    # Agrupar por día
    resumen_diario = []
    for fecha_dt, group in df_mes.groupby(df_mes["Fecha"].dt.date):
        df_comida = group[group["Tipo"] == "Comida"]
        df_act = group[group["Tipo"] == "Actividad Física"]

        cal_ing = df_comida["Calorías (kcal)"].sum() if not df_comida.empty else 0
        cal_que = abs(df_act["Calorías (kcal)"].sum()) if not df_act.empty else 0
        balance = cal_ing - cal_que
        prot = df_comida["Proteínas (g)"].sum() if not df_comida.empty else 0
        fat = df_comida["Grasas (g)"].sum() if not df_comida.empty else 0
        carb = df_comida["Hidratos (g)"].sum() if not df_comida.empty else 0

        resumen_diario.append({
            "Fecha": fecha_dt.strftime("%Y-%m-%d"),
            "Consumidas": round(cal_ing, 1),
            "Quemadas": round(cal_que, 1),
            "Neto": round(balance, 1),
            "Prot": round(prot, 1),
            "Grasas": round(fat, 1),
            "Carbs": round(carb, 1),
        })

    # Crear el documento PDF en memoria
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=12
    )

    nombre_meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_nombre = nombre_meses[mes - 1]

    story.append(Paragraph(f"<b>Reporte Nutricional Mensual - {mes_nombre} {año}</b>", title_style))
    story.append(Paragraph(f"Usuario Telegram ID: {user_id}", styles['Normal']))
    story.append(Spacer(1, 15))

    # Encabezados de la tabla
    data_table = [["Fecha", "Cal. Consumid.", "Cal. Quemad.", "Bal. Neto", "Prot (g)", "Grasas (g)", "Carbs (g)"]]

    tot_cons, tot_quem, tot_prot, tot_fat, tot_carb = 0, 0, 0, 0, 0

    for item in resumen_diario:
        data_table.append([
            item["Fecha"],
            f"{item['Consumidas']} kcal",
            f"{item['Quemadas']} kcal",
            f"{item['Neto']} kcal",
            f"{item['Prot']} g",
            f"{item['Grasas']} g",
            f"{item['Carbs']} g"
        ])
        tot_cons += item["Consumidas"]
        tot_quem += item["Quemadas"]
        tot_prot += item["Prot"]
        tot_fat += item["Grasas"]
        tot_carb += item["Carbs"]

    # Fila de totales mensuales
    data_table.append([
        "TOTAL MES",
        f"{round(tot_cons, 1)} kcal",
        f"{round(tot_quem, 1)} kcal",
        f"{round(tot_cons - tot_quem, 1)} kcal",
        f"{round(tot_prot, 1)} g",
        f"{round(tot_fat, 1)} g",
        f"{round(tot_carb, 1)} g"
    ])

    # Estilo de la tabla
    tabla = Table(data_table, colWidths=[70, 80, 80, 75, 60, 65, 65])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -2), colors.HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E2E8F0')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))

    story.append(tabla)
    doc.build(story)
    buffer.seek(0)
    return buffer


# ==========================================
# COMANDOS Y FLUJOS
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.from_user.first_name
    await update.message.reply_text(
        f"¡Hola {user_name}! 👋\n\n"
        "• Mandame foto o texto de lo que comiste para registrarlo.\n"
        "• Escribí directamente tu ejercicio (Ej: *Caminata 45 min*, *Fútbol 1 hora*).\n"
        "• Usá /resumen para ver el balance diario.\n"
        "• Usá /pdf para descargar tu reporte mensual en PDF.",
        parse_mode="Markdown"
    )


async def procesar_actividad_directa(update: Update, context: ContextTypes.DEFAULT_TYPE, texto: str):
    user_id = update.message.from_user.id
    msg_espera = await update.message.reply_text("🏃 Estimando gasto calórico...")

    system_instruction = "You are a strict JSON generator. Do NOT think step-by-step. Do NOT output <think> tags. Output ONLY a valid JSON object."
    prompt = f"""
    El usuario realizó: "{texto}".
    Interpreta actividad, duración y calorías quemadas.
    Responde ÚNICAMENTE en JSON estricto:
    {{"actividad": "Nombre", "duracion": "45 min", "calorias": 320}}
    """
    try:
        response = groq_client.chat.completions.create(
            model=MODELO_GROQ,
            messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000,
            timeout=30.0,
        )
        act_info = json.loads(extract_json(response.choices[0].message.content))
        user_pending_data[user_id] = {
            "tipo": "actividad",
            "actividad": act_info.get("actividad", "Ejercicio"),
            "duracion": act_info.get("duracion", "No especificada"),
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
        [InlineKeyboardButton("✅ Aceptar", callback_data="ask_date"), InlineKeyboardButton("✏️ Editar", callback_data="edit_act_cal")],
        [InlineKeyboardButton("❌ Descartar", callback_data="cancel_save")],
    ]
    if hasattr(message, "edit_text"):
        await message.edit_text(reply_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await message.reply_text(reply_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_states.pop(user_id, None)
    msg_espera = await update.message.reply_text("🔍 Analizando plato...")

    photo_file = await update.message.photo[-1].get_file()
    photo_path = f"temp_{user_id}.jpg"
    await photo_file.download_to_drive(photo_path)

    try:
        base64_image = encode_image(photo_path)
        system_instruction = "You are a strict JSON generator. Do NOT think step-by-step. Output ONLY a valid JSON object."
        prompt = """
        Analiza esta imagen e identifica sus alimentos.
        Responde ÚNICAMENTE con JSON:
        {"items": [{"alimento": "Pechuga", "peso_g": 150, "calorias": 240, "proteinas_g": 31, "grasas_g": 3.5, "hidratos_g": 0, "fibra_g": 0}]}
        """
        response = groq_client.chat.completions.create(
            model=MODELO_GROQ,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]}
            ],
            temperature=0.1, max_tokens=4000, timeout=30.0,
        )
        items = parse_response_to_items(response.choices[0].message.content)
        user_pending_data[user_id] = {"tipo": "comida", "items": items, "momento": "No especificado"}
        await mostrar_resumen_y_botones(msg_espera, user_id, es_edicion=False)
    except Exception as e:
        await msg_espera.edit_text(f"❌ Error al procesar imagen: {str(e)}")
    finally:
        if os.path.exists(photo_path):
            os.remove(photo_path)


async def procesar_texto_comida(update: Update, context: ContextTypes.DEFAULT_TYPE, texto: str):
    user_id = update.message.from_user.id
    msg_espera = await update.message.reply_text("🔍 Procesando alimento...")

    system_instruction = "You are a strict JSON generator. Do NOT think step-by-step. Output ONLY a valid JSON object."
    prompt = f'El usuario comió: "{texto}". Responde ÚNICAMENTE con JSON: {{"items": [{{"alimento": "nombre", "peso_g": 0, "calorias": 0, "proteinas_g": 0, "grasas_g": 0, "hidratos_g": 0, "fibra_g": 0}}]}}'

    try:
        response = groq_client.chat.completions.create(
            model=MODELO_GROQ,
            messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=4000, timeout=30.0,
        )
        items = parse_response_to_items(response.choices[0].message.content)
        user_pending_data[user_id] = {"tipo": "comida", "items": items, "momento": "No especificado"}
        await mostrar_resumen_y_botones(msg_espera, user_id, es_edicion=False)
    except Exception as e:
        await msg_espera.edit_text(f"❌ Error al procesar texto: {str(e)}")


async def mostrar_resumen_y_botones(message, user_id: int, es_edicion=False):
    data = user_pending_data[user_id]
    items = data["items"]
    reply_msg = "📊 *Análisis de los alimentos:*\n\n" if not es_edicion else "✏️ *Análisis actualizado:*\n\n"
    t_cal, t_prot, t_fat, t_carb, t_fib = 0, 0, 0, 0, 0

    for item in items:
        reply_msg += f"• *{item.get('alimento', 'Alimento')}* ({item.get('peso_g', 0)}g): {item.get('calorias', 0)} kcal\n"
        t_cal += item.get("calorias", 0)
        t_prot += item.get("proteinas_g", 0)
        t_fat += item.get("grasas_g", 0)
        t_carb += item.get("hidratos_g", 0)
        t_fib += item.get("fibra_g", 0)

    reply_msg += f"\n🔥 *Totales:* {round(t_cal, 1)} kcal\n💪 P: {round(t_prot, 1)}g | 🥑 G: {round(t_fat, 1)}g | 🍞 H: {round(t_carb, 1)}g | 🌾 F: {round(t_fib, 1)}g\n\n¿Qué querés hacer?"
    keyboard = [
        [InlineKeyboardButton("✅ Confirmar", callback_data="ask_momento")],
        [InlineKeyboardButton("✏️ Editar", callback_data="edit_data")],
        [InlineKeyboardButton("❌ Descartar", callback_data="cancel_save")],
    ]
    if hasattr(message, "edit_text"):
        await message.edit_text(reply_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await message.reply_text(reply_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def pedir_momento_comida(query):
    keyboard = [
        [InlineKeyboardButton("🌅 Desayuno", callback_data="set_momento_Desayuno"), InlineKeyboardButton("☀️ Almuerzo", callback_data="set_momento_Almuerzo")],
        [InlineKeyboardButton("☕ Merienda", callback_data="set_momento_Merienda"), InlineKeyboardButton("🌙 Cena", callback_data="set_momento_Cena")],
        [InlineKeyboardButton("🍎 Snack", callback_data="set_momento_Snack")],
    ]
    await query.edit_message_text("🍽 *¿A qué momento corresponde esta comida?*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def pedir_fecha(query):
    keyboard = [
        [InlineKeyboardButton("📅 Hoy", callback_data="save_date_hoy"), InlineKeyboardButton("📅 Ayer", callback_data="save_date_ayer")],
        [InlineKeyboardButton("📅 Otra fecha", callback_data="save_date_otra")],
    ]
    await query.edit_message_text("📅 *¿A qué fecha corresponde este registro?*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


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
                "Alimento/Detalle": item.get("alimento", "Alimento"),
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
            "Proteínas (g)": 0, "Grasas (g)": 0, "Hidratos (g)": 0, "Fibra (g)": 0,
        })

    df_new = pd.DataFrame(rows)

    if os.path.exists(excel_file):
        df_existing = pd.read_excel(excel_file)
        if "Usuario" in df_existing.columns:
            df_existing = df_existing.drop(columns=["Usuario"])
        df_final = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_final = df_new

    # ORDENAR AUTOMÁTICAMENTE POR FECHA CRONOLÓGICA
    df_final["Fecha_dt"] = pd.to_datetime(df_final["Fecha"], errors="coerce")
    df_final = df_final.sort_values(by="Fecha_dt", ascending=True).drop(columns=["Fecha_dt"])

    df_final.to_excel(excel_file, index=False)
    user_pending_data.pop(user_id, None)
    user_states.pop(user_id, None)

    return f"💾 ¡Guardado y ordenado cronológicamente para la fecha *{fecha_str}*!"


# ==========================================
# RESUMEN SIMPLIFICADO Y COMANDO PDF
# ==========================================

async def resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    excel_file = f"registros_{user_id}.xlsx"

    if not os.path.exists(excel_file):
        await update.message.reply_text("📉 Todavía no tenés ningún registro guardado.")
        return

    keyboard = [
        [InlineKeyboardButton("📅 Ver Hoy", callback_data="resumen_date_hoy"), InlineKeyboardButton("📅 Ver Ayer", callback_data="resumen_date_ayer")],
        [InlineKeyboardButton("📅 Otra fecha", callback_data="resumen_date_otra")],
        [InlineKeyboardButton("📄 Descargar PDF Mensual", callback_data="get_pdf_mes")],
    ]
    await update.message.reply_text("📊 *¿Qué resumen querés consultar?*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def generar_reporte_resumen_simplificado(target_msg_or_query, user_id: int, fecha_str: str):
    excel_file = f"registros_{user_id}.xlsx"

    if not os.path.exists(excel_file):
        msg = "📉 Todavía no tenés ningún registro guardado."
        await (target_msg_or_query.edit_message_text(msg) if hasattr(target_msg_or_query, "edit_message_text") else target_msg_or_query.reply_text(msg))
        return

    try:
        df = pd.read_excel(excel_file)
        df["Fecha"] = df["Fecha"].astype(str)
        df_dia = df[df["Fecha"] == fecha_str]

        if df_dia.empty:
            msg = f"📅 No hay registros guardados para la fecha *{fecha_str}*."
            await (target_msg_or_query.edit_message_text(msg, parse_mode="Markdown") if hasattr(target_msg_or_query, "edit_message_text") else target_msg_or_query.reply_text(msg, parse_mode="Markdown"))
            return

        df_comida = df_dia[df_dia["Tipo"] == "Comida"]
        df_act = df_dia[df_dia["Tipo"] == "Actividad Física"]

        cal_ingresadas = df_comida["Calorías (kcal)"].sum() if not df_comida.empty else 0
        cal_quemadas = abs(df_act["Calorías (kcal)"].sum()) if not df_act.empty else 0
        prot = df_comida["Proteínas (g)"].sum() if not df_comida.empty else 0
        fat = df_comida["Grasas (g)"].sum() if not df_comida.empty else 0
        carb = df_comida["Hidratos (g)"].sum() if not df_comida.empty else 0

        # RESUMEN SIMPLIFICADO SIN DESGLOSE DE ALIMENTOS INDIVIDUALES
        msg = (
            f"📋 *Resumen del día ({fecha_str}):*\n\n"
            f"🔥 *Calorías Consumidas:* {round(cal_ingresadas, 1)} kcal\n"
            f"🏃 *Calorías Quemadas:* {round(cal_quemadas, 1)} kcal\n"
            f"⚖️ *Balance Neto:* {round(cal_ingresadas - cal_quemadas, 1)} kcal\n\n"
            f"💪 *Proteínas:* {round(prot, 1)}g\n"
            f"🥑 *Grasas:* {round(fat, 1)}g\n"
            f"🍞 *Hidratos:* {round(carb, 1)}g\n"
        )

        await (target_msg_or_query.edit_message_text(msg, parse_mode="Markdown") if hasattr(target_msg_or_query, "edit_message_text") else target_msg_or_query.reply_text(msg, parse_mode="Markdown"))

    except Exception as e:
        err = f"❌ Error al consultar el resumen: {str(e)}"
        await (target_msg_or_query.edit_message_text(err) if hasattr(target_msg_or_query, "edit_message_text") else target_msg_or_query.reply_text(err))


async def cmd_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    now = datetime.now()
    
    msg_espera = await update.message.reply_text("📄 Generando PDF del mes...")
    pdf_buffer = generar_pdf_mes(user_id, now.year, now.month)

    if pdf_buffer:
        await update.message.reply_document(
            document=pdf_buffer,
            filename=f"Resumen_Nutricional_{now.year}_{now.month:02d}.pdf",
            caption=f"📊 Acá tenés tu reporte en PDF de *{now.strftime('%B %Y')}*.",
            parse_mode="Markdown"
        )
        await msg_espera.delete()
    else:
        await msg_espera.edit_text("⚠️ No se encontraron registros para este mes.")


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
            await query.message.reply_text("📅 Ingresá la fecha en formato **AAAA-MM-DD** (Ej: `2026-07-28`):")

    elif data == "edit_data":
        user_states[user_id] = "waiting_for_correction"
        await query.message.reply_text("📝 Escribime las correcciones para la comida.")

    elif data == "edit_act_cal":
        user_states[user_id] = "waiting_for_cal_edit"
        await query.message.reply_text("✏️ Escribí el nuevo valor de calorías (Ej: `310`):")

    elif data.startswith("resumen_date_"):
        opcion = data.replace("resumen_date_", "")
        if opcion == "hoy":
            fecha = datetime.now().strftime("%Y-%m-%d")
            await generar_reporte_resumen_simplificado(query, user_id, fecha)
        elif opcion == "ayer":
            fecha = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            await generar_reporte_resumen_simplificado(query, user_id, fecha)
        elif opcion == "otra":
            user_states[user_id] = "waiting_for_resumen_date"
            await query.message.reply_text("📅 Ingresá la fecha en formato **AAAA-MM-DD** (Ej: `2026-07-28`):")

    elif data == "get_pdf_mes":
        now = datetime.now()
        pdf_buffer = generar_pdf_mes(user_id, now.year, now.month)
        if pdf_buffer:
            await query.message.reply_document(
                document=pdf_buffer,
                filename=f"Resumen_Nutricional_{now.year}_{now.month:02d}.pdf",
                caption=f"📊 Acá tenés tu reporte mensual en PDF.",
                parse_mode="Markdown"
            )
        else:
            await query.message.reply_text("⚠️ No tenés registros guardados para este mes.")

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

        msg_espera = await update.message.reply_text("🔄 Recalculando...")
        system_instruction = "You are a strict JSON generator. Do NOT think step-by-step. Output ONLY a valid JSON object."
        prompt = f'LISTA ACTUAL: {json.dumps(current_data, ensure_ascii=False)}\nCORRECCIÓN: "{text}"\nResponde ÚNICAMENTE con el JSON actualizado.'

        try:
            response = groq_client.chat.completions.create(
                model=MODELO_GROQ,
                messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": prompt}],
                temperature=0.1, max_tokens=4000, timeout=30.0,
            )
            updated_items = parse_response_to_items(response.choices[0].message.content)
            user_pending_data[user_id]["items"] = updated_items
            user_states.pop(user_id, None)
            await mostrar_resumen_y_botones(msg_espera, user_id, es_edicion=True)
        except Exception as e:
            await msg_espera.edit_text(f"❌ Error al procesar corrección: {str(e)}")

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
            await update.message.reply_text("⚠️ Formato inválido. Usá `AAAA-MM-DD` (Ej: `2026-07-28`).")

    elif state == "waiting_for_resumen_date":
        if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
            user_states.pop(user_id, None)
            await generar_reporte_resumen_simplificado(update.message, user_id, text)
        else:
            await update.message.reply_text("⚠️ Formato inválido. Usá `AAAA-MM-DD` (Ej: `2026-07-28`).")

    else:
        keywords_actividad = [
            "caminata", "camino", "caminar", "correr", "trotar", "trote",
            "bici", "bicicleta", "gimnasio", "gym", "aquagym", "natacion",
            "nadar", "futbol", "fútbol", "padel", "tenis", "basquet",
            "entreno", "ejercicio", "pesas", "funcional", "spinning", "crossfit"
        ]

        es_actividad = any(kw in text.lower() for kw in keywords_actividad)

        if es_actividad:
            await procesar_actividad_directa(update, context, text)
        else:
            await procesar_texto_comida(update, context, text)


# ==========================================
# INICIALIZACIÓN
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
    app.add_handler(CommandHandler("resumen", resumen))
    app.add_handler(CommandHandler("pdf", cmd_pdf))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))

    print(f"🚀 Bot iniciado con Resumen Simplificado y Generador de PDF Mensual.")
    app.run_polling()
