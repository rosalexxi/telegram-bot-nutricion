import asyncio
import base64
from datetime import datetime, timedelta
import io
import json
import os
import re
from dotenv import load_dotenv
from openai import OpenAI
import pandas as pd
from PIL import Image
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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
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
# FUNCIONES AUXILIARES Y MANEJO DE EXCEL/PERFIL
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


def guardar_perfil_excel(user_id: int, datos: dict):
    excel_file = f"registros_{user_id}.xlsx"
    datos["Fecha_Actualizacion"] = datetime.now().strftime("%Y-%m-%d")
    df_perfil = pd.DataFrame([datos])

    if os.path.exists(excel_file):
        with pd.ExcelWriter(excel_file, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            df_perfil.to_excel(writer, sheet_name="Perfil", index=False)
    else:
        with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
            df_perfil.to_excel(writer, sheet_name="Perfil", index=False)


def obtener_perfil_excel(user_id: int) -> dict:
    excel_file = f"registros_{user_id}.xlsx"
    if not os.path.exists(excel_file):
        return None
    try:
        xls = pd.ExcelFile(excel_file)
        if "Perfil" in xls.sheet_names:
            df_perfil = pd.read_excel(xls, sheet_name="Perfil")
            if not df_perfil.empty:
                return df_perfil.iloc[0].to_dict()
    except Exception:
        return None
    return None


def validar_estado_perfil(user_id: int) -> tuple[bool, str]:
    perfil = obtener_perfil_excel(user_id)
    if not perfil:
        return False, "⚠️ **Perfil no configurado:** Para comenzar a ingresar comidas o ejercicios debés configurar tu perfil antropométrico.\n\nEscribí /perfil para comenzar."

    fecha_act_str = perfil.get("Fecha_Actualizacion")
    if not fecha_act_str:
        return False, "⚠️ **Perfil incompleto:** Debés actualizar tu perfil antes de continuar.\n\nEscribí /perfil para actualizar tus datos."

    try:
        fecha_act = datetime.strptime(str(fecha_act_str), "%Y-%m-%d")
        dias_transcurridos = (datetime.now() - fecha_act).days

        if dias_transcurridos > 30:
            return False, f"🕒 **Perfil desactualizado ({dias_transcurridos} días):** Pasó más de 1 mes desde tu último registro de peso/datos.\n\nPor favor, actualizá tus datos ejecutando /perfil para continuar cargando registros."
    except Exception:
        return False, "⚠️ Error al verificar la fecha del perfil. Por favor ejecutá /perfil nuevamente."

    return True, ""


def calcular_metabolismo(sexo, peso, altura, edad, ocupacion):
    if str(sexo).upper() in ["M", "MASCULINO", "HOMBRE"]:
        tmb = (10 * peso) + (6.25 * altura) - (5 * edad) + 5
    else:
        tmb = (10 * peso) + (6.25 * altura) - (5 * edad) - 161

    factores = {
        "sedentario": 1.2,
        "comerciante": 1.375,
        "activo": 1.55,
        "albañil": 1.725,
        "atleta": 1.9
    }

    factor_estandar = 1.2
    ocupacion_lower = str(ocupacion).lower()
    for clave, f_val in factores.items():
        if clave in ocupacion_lower:
            factor_estandar = f_val
            break

    # Enfoque prudente: reducción del extra de actividad al 50%
    gasto_extra_teorico = tmb * (factor_estandar - 1.0)
    gasto_extra_prudente = gasto_extra_teorico * 0.5

    get_prudente = tmb + gasto_extra_prudente

    return round(tmb, 1), round(get_prudente, 1)


# ==========================================
# GENERADOR DE PDF MENSUAL (2 PÁGINAS)
# ==========================================

def generar_pdf_mes(user_id: int, año: int, mes: int) -> io.BytesIO:
    excel_file = f"registros_{user_id}.xlsx"
    if not os.path.exists(excel_file):
        return None

    try:
        xls = pd.ExcelFile(excel_file)
        if "Registros" not in xls.sheet_names:
            return None
        df = pd.read_excel(xls, sheet_name="Registros")
    except Exception:
        return None

    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df_mes = df[(df["Fecha"].dt.year == año) & (df["Fecha"].dt.month == mes)]

    if df_mes.empty:
        return None

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

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle', parent=styles['Heading1'], fontSize=18, leading=22, textColor=colors.HexColor('#1E293B'), spaceAfter=12
    )

    nombre_meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_nombre = nombre_meses[mes - 1]

    # Página 1: Tabla Diaria
    story.append(Paragraph(f"<b>Reporte Nutricional Mensual - {mes_nombre} {año}</b>", title_style))
    story.append(Paragraph(f"Usuario Telegram ID: {user_id}", styles['Normal']))
    story.append(Spacer(1, 15))

    data_table = [["Fecha", "Cal. Consumid.", "Cal. Quemad.", "Bal. Neto", "Prot (g)", "Grasas (g)", "Carbs (g)"]]
    tot_cons, tot_quem, tot_prot, tot_fat, tot_carb = 0, 0, 0, 0, 0

    for item in resumen_diario:
        data_table.append([
            item["Fecha"], f"{item['Consumidas']} kcal", f"{item['Quemadas']} kcal",
            f"{item['Neto']} kcal", f"{item['Prot']} g", f"{item['Grasas']} g", f"{item['Carbs']} g"
        ])
        tot_cons += item["Consumidas"]
        tot_quem += item["Quemadas"]
        tot_prot += item["Prot"]
        tot_fat += item["Grasas"]
        tot_carb += item["Carbs"]

    cant_dias = len(resumen_diario) if len(resumen_diario) > 0 else 1

    data_table.append([
        "TOTAL MES", f"{round(tot_cons, 1)} kcal", f"{round(tot_quem, 1)} kcal",
        f"{round(tot_cons - tot_quem, 1)} kcal", f"{round(tot_prot, 1)} g", f"{round(tot_fat, 1)} g", f"{round(tot_carb, 1)} g"
    ])
    data_table.append([
        "PROM. DIARIO", f"{round(tot_cons / cant_dias, 1)} kcal", f"{round(tot_quem / cant_dias, 1)} kcal",
        f"{round((tot_cons - tot_quem) / cant_dias, 1)} kcal", f"{round(tot_prot / cant_dias, 1)} g",
        f"{round(tot_fat / cant_dias, 1)} g", f"{round(tot_carb / cant_dias, 1)} g"
    ])

    tabla = Table(data_table, colWidths=[70, 80, 80, 75, 60, 65, 65])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -3), colors.HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0, -2), (-1, -2), colors.HexColor('#E2E8F0')),
        ('FONTNAME', (0, -2), (-1, -2), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FEF08A')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    story.append(tabla)

    # Página 2: Datos Antropométricos y Estimación
    perfil = obtener_perfil_excel(user_id)
    if perfil:
        story.append(PageBreak())
        story.append(Paragraph(f"<b>Análisis Metabólico y Estimación Corporal</b>", title_style))
        story.append(Spacer(1, 10))

        sexo = perfil.get("Sexo", "M")
        edad = int(perfil.get("Edad", 30))
        peso = float(perfil.get("Peso_kg", 70))
        altura = float(perfil.get("Altura_cm", 170))
        ocupacion = str(perfil.get("Ocupacion", "Sedentario"))
        f_act = str(perfil.get("Fecha_Actualizacion", "No registrada"))

        tmb, get = calcular_metabolismo(sexo, peso, altura, edad, ocupacion)
        gasto_basal_total_mes = get * cant_dias
        balance_calorico_real = tot_cons - (gasto_basal_total_mes + tot_quem)
        gramos_estimados = balance_calorico_real / 7.5

        datos_perfil_table = [
            ["Dato Fisiológico", "Valor Registrado"],
            ["Última Actualización", f_act],
            ["Sexo", sexo],
            ["Edad", f"{edad} años"],
            ["Peso", f"{peso} kg"],
            ["Altura", f"{altura} cm"],
            ["Ocupación / Actividad", ocupacion],
            ["Metabolismo Basal (TMB)", f"{tmb} kcal / día"],
            ["Gasto Energético Conservador (GET)", f"{get} kcal / día"],
        ]

        t_perfil = Table(datos_perfil_table, colWidths=[200, 250])
        t_perfil.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t_perfil)
        story.append(Spacer(1, 20))

        story.append(Paragraph("<b>Resumen de Balance y Cambio Corporal Estimado:</b>", styles['Heading2']))
        story.append(Spacer(1, 10))

        resumen_meta_table = [
            ["Concepto", "Valor Mensual"],
            ["Total Calorías Consumidas (Comidas)", f"{round(tot_cons, 1)} kcal"],
            ["Total Gasto Basal + Ocupación (GET)", f"-{round(gasto_basal_total_mes, 1)} kcal ({cant_dias} días)"],
            ["Total Ejercicio Extra Registrado", f"-{round(tot_quem, 1)} kcal"],
            ["BALANCE CALÓRICO NETO REAL", f"{round(balance_calorico_real, 1)} kcal"],
            ["CAMBIO ESTIMADO DE PESO", f"{round(gramos_estimados / 1000, 2)} kg ({round(gramos_estimados, 1)} g)"]
        ]

        color_balance = colors.HexColor('#DC2626') if balance_calorico_real > 0 else colors.HexColor('#16A34A')
        t_resumen = Table(resumen_meta_table, colWidths=[230, 220])
        t_resumen.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('FONTNAME', (0, -2), (-1, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (1, -2), (1, -1), color_balance),
        ]))
        story.append(t_resumen)

    doc.build(story)
    buffer.seek(0)
    return buffer


# ==========================================
# COMANDOS Y FLUJOS PRINCIPALES
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    
    es_valido, msj_error = validar_estado_perfil(user_id)
    if not es_valido:
        await update.message.reply_text(f"¡Hola {user_name}! 👋\n\n{msj_error}", parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"¡Hola {user_name}! 👋\n\n"
            "• Mandame foto o texto de lo que comiste para registrarlo.\n"
            "• Escribí directamente tu ejercicio (Ej: *Caminata 45 min*).\n"
            "• Usá /resumen para descargar tu reporte mensual en PDF.\n"
            "• Usá /perfil para ver o actualizar tus datos.",
            parse_mode="Markdown"
        )


async def cmd_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_states[user_id] = "waiting_for_perfil_data"
    
    perfil_actual = obtener_perfil_excel(user_id)
    mensaje_actual = ""
    if perfil_actual:
        mensaje_actual = (
            f"📋 *Perfil actual registrado:*\n"
            f"• ÚLTIMA ACTUALIZACIÓN: {perfil_actual.get('Fecha_Actualizacion', 'No registrada')}\n"
            f"• Sexo: {perfil_actual.get('Sexo')}\n"
            f"• Edad: {perfil_actual.get('Edad')} años\n"
            f"• Peso: {perfil_actual.get('Peso_kg')} kg\n"
            f"• Altura: {perfil_actual.get('Altura_cm')} cm\n"
            f"• Ocupación: {perfil_actual.get('Ocupacion')}\n\n"
            "*(Ingresá los nuevos datos a continuación para actualizar tu perfil)*\n\n"
        )

    await update.message.reply_text(
        f"{mensaje_actual}"
        "👤 *Configuración de Perfil Nutricional*\n\n"
        "Ingresá tus datos separados por comas en el siguiente orden:\n"
        "`Sexo (M/F), Edad, Peso (kg), Altura (cm), Ocupación`\n\n"
        "📌 *Ejemplo:* `M, 38, 85, 178, Comerciante`",
        parse_mode="Markdown"
    )


async def procesar_actividad_directa(update: Update, context: ContextTypes.DEFAULT_TYPE, texto: str):
    user_id = update.message.from_user.id
    msg_espera = await update.message.reply_text("🏃 Estimando gasto calórico personalizado...")

    perfil = obtener_perfil_excel(user_id) or {}
    sexo = perfil.get("Sexo", "desconocido")
    edad = perfil.get("Edad", 30)
    peso = perfil.get("Peso_kg", 70)

    system_instruction = "You are a strict JSON generator. Do NOT think step-by-step. Do NOT output <think> tags. Output ONLY a valid JSON object."
    prompt = (
        f'El usuario realizó: "{texto}".\n'
        f'Biométricos del usuario: Sexo: {sexo}, Edad: {edad} años, Peso: {peso} kg.\n'
        'Calcula las calorías quemadas considerando su peso corporal real.\n'
        'Responde ÚNICAMENTE en JSON estricto: {"actividad": "Nombre", "duracion": "45 min", "calorias": 320}'
    )

    max_intentos = 3
    for intento in range(1, max_intentos + 1):
        try:
            response = groq_client.chat.completions.create(
                model=MODELO_GROQ,
                messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": prompt}],
                temperature=0.1, max_tokens=1000, timeout=45.0,
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
            break
        except Exception as e:
            if intento < max_intentos:
                await asyncio.sleep(2)
            else:
                await msg_espera.edit_text(f"❌ Error de conexión al estimar ejercicio ({type(e).__name__}). Volvé a intentarlo.")


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
    
    es_valido, msj_error = validar_estado_perfil(user_id)
    if not es_valido:
        await update.message.reply_text(msj_error, parse_mode="Markdown")
        return

    user_states.pop(user_id, None)
    msg_espera = await update.message.reply_text("🔍 Analizando plato...")

    photo_file = await update.message.photo[-1].get_file()
    photo_path = f"temp_{user_id}.jpg"
    await photo_file.download_to_drive(photo_path)

    # Compresión y reducción de resolución (PIL)
    try:
        with Image.open(photo_path) as img:
            img = img.convert("RGB")
            img.thumbnail((1024, 1024))
            img.save(photo_path, format="JPEG", quality=80, optimize=True)
    except Exception as img_err:
        print(f"Error comprimiendo imagen: {img_err}")

    base64_image = encode_image(photo_path)
    system_instruction = "You are a strict JSON generator. Do NOT think step-by-step. Output ONLY a valid JSON object."
    prompt = 'Analiza esta imagen e identifica sus alimentos. Responde ÚNICAMENTE con JSON: {"items": [{"alimento": "Pechuga", "peso_g": 150, "calorias": 240, "proteinas_g": 31, "grasas_g": 3.5, "hidratos_g": 0, "fibra_g": 0}]}'
    
    max_intentos = 3
    for intento in range(1, max_intentos + 1):
        try:
            response = groq_client.chat.completions.create(
                model=MODELO_GROQ,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]}
                ],
                temperature=0.1, max_tokens=4000, timeout=45.0,
            )
            items = parse_response_to_items(response.choices[0].message.content)
            user_pending_data[user_id] = {"tipo": "comida", "items": items, "momento": "No especificado"}
            await mostrar_resumen_y_botones(msg_espera, user_id, es_edicion=False)
            break
        except Exception as e:
            if intento < max_intentos:
                await asyncio.sleep(2)
            else:
                await msg_espera.edit_text(f"❌ Error de conexión al procesar imagen ({type(e).__name__}). Por favor, volvé a enviarla.")

    if os.path.exists(photo_path):
        os.remove(photo_path)


async def procesar_texto_comida(update: Update, context: ContextTypes.DEFAULT_TYPE, texto: str):
    user_id = update.message.from_user.id
    msg_espera = await update.message.reply_text("🔍 Procesando alimento...")

    system_instruction = "You are a strict JSON generator. Do NOT think step-by-step. Output ONLY a valid JSON object."
    prompt = f'El usuario comió: "{texto}". Responde ÚNICAMENTE con JSON: {{"items": [{{"alimento": "nombre", "peso_g": 0, "calorias": 0, "proteinas_g": 0, "grasas_g": 0, "hidratos_g": 0, "fibra_g": 0}}]}}'

    max_intentos = 3
    for intento in range(1, max_intentos + 1):
        try:
            response = groq_client.chat.completions.create(
                model=MODELO_GROQ,
                messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": prompt}],
                temperature=0.1, max_tokens=4000, timeout=45.0,
            )
            items = parse_response_to_items(response.choices[0].message.content)
            user_pending_data[user_id] = {"tipo": "comida", "items": items, "momento": "No especificado"}
            await mostrar_resumen_y_botones(msg_espera, user_id, es_edicion=False)
            break
        except Exception as e:
            if intento < max_intentos:
                await asyncio.sleep(2)
            else:
                await msg_espera.edit_text(f"❌ Error de conexión al procesar texto ({type(e).__name__}). Volvé a enviarlo.")


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
        xls = pd.ExcelFile(excel_file)
        if "Registros" in xls.sheet_names:
            df_existing = pd.read_excel(xls, sheet_name="Registros")
            df_final = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df_final = df_new
    else:
        df_final = df_new

    df_final["Fecha_dt"] = pd.to_datetime(df_final["Fecha"], errors="coerce")
    df_final = df_final.sort_values(by="Fecha_dt", ascending=True).drop(columns=["Fecha_dt"])

    if os.path.exists(excel_file):
        with pd.ExcelWriter(excel_file, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            df_final.to_excel(writer, sheet_name="Registros", index=False)
    else:
        with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
            df_final.to_excel(writer, sheet_name="Registros", index=False)

    user_pending_data.pop(user_id, None)
    user_states.pop(user_id, None)

    return f"💾 ¡Guardado y ordenado cronológicamente para la fecha *{fecha_str}*!"


# ==========================================
# MENÚ RESUMEN Y ENVÍO DE PDF
# ==========================================

async def resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    
    es_valido, msj_error = validar_estado_perfil(user_id)
    if not es_valido:
        await update.message.reply_text(msj_error, parse_mode="Markdown")
        return

    now = datetime.now()
    mes_actual_str = now.strftime("%Y-%m")
    primer_dia_mes_actual = now.replace(day=1)
    mes_pasado_dt = primer_dia_mes_actual - timedelta(days=1)
    mes_pasado_str = mes_pasado_dt.strftime("%Y-%m")

    keyboard = [
        [
            InlineKeyboardButton(f"📅 Mes Actual ({now.strftime('%m/%Y')})", callback_data=f"pdf_mes_{mes_actual_str}"),
            InlineKeyboardButton(f"📅 Mes Pasado ({mes_pasado_dt.strftime('%m/%Y')})", callback_data=f"pdf_mes_{mes_pasado_str}")
        ],
        [InlineKeyboardButton("🗓 Otro Mes (Escribir AAAA-MM)", callback_data="pdf_mes_otro")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text("📄 **¿De qué mes querés descargar el PDF?**", parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text("📄 **¿De qué mes querés descargar el PDF?**", parse_mode="Markdown", reply_markup=reply_markup)


async def enviar_pdf_usuario(target, user_id: int, año: int, mes: int):
    msg_espera = await (target.message.reply_text(f"⏳ Generando PDF de {mes:02d}/{año}...") if hasattr(target, "message") else target.reply_text(f"⏳ Generando PDF de {mes:02d}/{año}..."))
    
    pdf_buffer = generar_pdf_mes(user_id, año, mes)

    if pdf_buffer:
        nombre_archivo = f"Resumen_Nutricional_{año}_{mes:02d}.pdf"
        caption = f"📊 Acá tenés tu reporte en PDF de *{mes:02d}/{año}*."
        
        if hasattr(target, "message"):
            await target.message.reply_document(document=pdf_buffer, filename=nombre_archivo, caption=caption, parse_mode="Markdown")
        else:
            await target.reply_document(document=pdf_buffer, filename=nombre_archivo, caption=caption, parse_mode="Markdown")
            
        await msg_espera.delete()
    else:
        await msg_espera.edit_text(f"⚠️ No se encontraron registros guardados para **{mes:02d}/{año}**.")


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

    elif data.startswith("pdf_mes_"):
        opcion = data.replace("pdf_mes_", "")
        if opcion == "otro":
            user_states[user_id] = "waiting_for_pdf_month"
            await query.message.reply_text("🗓 Ingresá el año y mes en formato **AAAA-MM** (Ej: `2026-06`):")
        else:
            año, mes = map(int, opcion.split("-"))
            await enviar_pdf_usuario(query, user_id, año, mes)

    elif data == "cancel_save":
        user_pending_data.pop(user_id, None)
        user_states.pop(user_id, None)
        await query.edit_message_text("❌ Registro cancelado.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = user_states.get(user_id)
    text = update.message.text

    # ESTADO 1: CONFIGURACIÓN DE PERFIL
    if state == "waiting_for_perfil_data":
        partes = [p.strip() for p in text.split(",")]
        if len(partes) == 5:
            try:
                sexo = partes[0].upper()
                edad = int(partes[1])
                peso = float(partes[2])
                altura = float(partes[3])
                ocupacion = partes[4].capitalize()

                datos = {
                    "Sexo": sexo,
                    "Edad": edad,
                    "Peso_kg": peso,
                    "Altura_cm": altura,
                    "Ocupacion": ocupacion
                }
                guardar_perfil_excel(user_id, datos)
                user_states.pop(user_id, None)
                await update.message.reply_text("✅ ¡Perfil actualizado correctamente! Ya podés continuar registrando tus comidas y ejercicios.")
            except ValueError:
                await update.message.reply_text("⚠️ Error en los números. Asegurate de ingresar Edad, Peso y Altura como valores numéricos.")
        else:
            await update.message.reply_text("⚠️ Formato incorrecto. Ingresá los 5 datos separados por coma (Ej: `M, 38, 85, 178, Comerciante`).")
        return

    # VERIFICACIÓN DE CADUCIDAD (> 30 DÍAS)
    es_valido, msj_error = validar_estado_perfil(user_id)
    if not es_valido:
        await update.message.reply_text(msj_error, parse_mode="Markdown")
        return

    # ESTADOS SECUNDARIOS
    if state == "waiting_for_correction":
        current_data = user_pending_data.get(user_id, {}).get("items")
        if not current_data:
            await update.message.reply_text("No hay datos pendientes de edición.")
            user_states.pop(user_id, None)
            return

        msg_espera = await update.message.reply_text("🔄 Recalculando...")
        system_instruction = "You are a strict JSON generator. Do NOT think step-by-step. Output ONLY a valid JSON object."
        prompt = f'LISTA ACTUAL: {json.dumps(current_data, ensure_ascii=False)}\nCORRECCIÓN: "{text}"\nResponde ÚNICAMENTE con el JSON actualizado.'

        max_intentos = 3
        for intento in range(1, max_intentos + 1):
            try:
                response = groq_client.chat.completions.create(
                    model=MODELO_GROQ,
                    messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": prompt}],
                    temperature=0.1, max_tokens=4000, timeout=45.0,
                )
                updated_items = parse_response_to_items(response.choices[0].message.content)
                user_pending_data[user_id]["items"] = updated_items
                user_states.pop(user_id, None)
                await mostrar_resumen_y_botones(msg_espera, user_id, es_edicion=True)
                break
            except Exception as e:
                if intento < max_intentos:
                    await asyncio.sleep(2)
                else:
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

    elif state == "waiting_for_pdf_month":
        if re.match(r"^\d{4}-\d{2}$", text):
            user_states.pop(user_id, None)
            año, mes = map(int, text.split("-"))
            await enviar_pdf_usuario(update.message, user_id, año, mes)
        else:
            await update.message.reply_text("⚠️ Formato inválido. Usá **AAAA-MM** (Ej: `2026-05`).")

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
    app.add_handler(CommandHandler("perfil", cmd_perfil))
    app.add_handler(CommandHandler("resumen", resumen))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))

    print(f"🚀 Bot iniciado con Control de Caducidad de Perfil (30 días).")
    
    # Manejo de reconexión automática ante microcortes
    app.run_polling(poll_interval=1.0, timeout=30, drop_pending_updates=True)
