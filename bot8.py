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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_SHEETS_KEY_PATH = os.getenv("GOOGLE_SHEETS_KEY_PATH", "credentials.json")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "Registro_Nutricional_Bot")

# Zona Horaria de Argentina
ARG_TZ = pytz.timezone('America/Argentina/Buenos_Aires')

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
# FUNCIONES AUXILIARES DE TRANSFORMACIÓN (x1000 / /1000)
# ==========================================
def parse_raw_val(val):
    """ Convierte cualquier dato a float puro de manera segura. """
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
    """ Convierte gramos/kcal a miligramos/unidades enteras (Multiplica x 1000 y redondea a entero). """
    num = parse_raw_val(val)
    return int(round(num * 1000))

def parse_float_from_sheets(val):
    """ Lee enteros desde la hoja de cálculo y los divide por 1000.0 para restaurar los decimales reales. """
    num = parse_raw_val(val)
    return num / 1000.0

# ==========================================
# LÓGICA DE HORARIO Y FECHA ARGENTINA
# ==========================================
def obtener_ahora_arg():
    return datetime.now(ARG_TZ)

def obtener_momento_y_fecha_auto():
    ahora = obtener_ahora_arg()
    hora = ahora.time()
    fecha_obj = ahora.date()
    
    # Rango de madrugada (00:00 a 02:00) asigna comida a la Cena del día anterior
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
            ws.append_row(["Mes_Anio", "Edad", "Sexo", "Peso_g", "Altura_mm", "Cintura_mm", "Ocupacion", "Fecha_Actualizacion"])
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
            to_sheet_int(item.get("peso", 0)),
            to_sheet_int(item.get("calorias", 0)),
            to_sheet_int(item.get("proteinas", 0)),
            to_sheet_int(item.get("grasas", 0)),
            to_sheet_int(item.get("carbohidratos", 0)),
            to_sheet_int(item.get("fibras", 0))
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
            df['Fecha_dt'] = pd.to_datetime(df['Fecha'], errors='coerce')
            df['Fecha'] = df['Fecha_dt'].dt.strftime('%Y-%m-%d').fillna(df['Fecha'].astype(str))
            df = df[df['Fecha'].str.startswith(mes_str)]
            
            for col in ['Peso', 'Calorias', 'Proteinas', 'Grasas', 'Carbohidratos', 'Fibras']:
                if col in df.columns:
                    df[col] = df[col].apply(parse_float_from_sheets)
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
        last_rec = df.iloc[-1].to_dict()
        
        perfil_clean = {}
        for k, v in last_rec.items():
            k_lower = str(k).lower()
            if any(x in k_lower for x in ['peso', 'altura', 'cintura']):
                perfil_clean[k] = parse_float_from_sheets(v)
            else:
                perfil_clean[k] = v
        return perfil_clean
    except Exception as e:
        print(f"Error al obtener perfil: {e}")
        return None

def guardar_perfil(user_id, perfil_dict):
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    ws_perfil = get_or_create_worksheet(sh, f"Perfil_{user_id}")
    mes_actual = obtener_ahora_arg().strftime("%Y-%m")
    
    row_data = [
        mes_actual,
        parse_raw_val(perfil_dict.get("edad", 0)),
        perfil_dict.get("sexo", ""),
        to_sheet_int(perfil_dict.get("peso", 0)),
        to_sheet_int(perfil_dict.get("altura", 0)),
        to_sheet_int(perfil_dict.get("cintura", 0)),
        perfil_dict.get("ocupacion", ""),
        obtener_ahora_arg().strftime("%Y-%m-%d %H:%M:%S")
    ]
    ws_perfil.append_row(row_data)

def calcular_metabolismo(perfil):
    if not perfil:
        return None
    try:
        edad = parse_raw_val(perfil.get("Edad", perfil.get("edad", 0)))
        sexo = str(perfil.get("Sexo", perfil.get("sexo", "M"))).upper()
        peso = parse_raw_val(perfil.get("Peso_kg", perfil.get("peso", perfil.get("Peso_g", 0))))
        altura = parse_raw_val(perfil.get("Altura_cm", perfil.get("altura", perfil.get("Altura_mm", 0))))
        
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
        "REGLAS CRÍTICAS DE PARSEO:\n"
        "1. Identifica las CANTIDADES Y UNIDADES indicadas.\n"
        "2. Devolvé los nutrientes en GRAMOS/KCAL estándar como números flotantes puros (ej: 7.5, 42.5).\n"
        "3. Usa el punto '.' como separador decimal.\n"
        "4. Si es ejercicio/actividad física, la caloría DEBE ser negativa (ej: -300.0).\n"
        "Devolvé EXCLUSIVAMENTE un JSON válido con este formato:\n"
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

def analizar_imagen_con_groq(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    system_prompt = (
        "Identifica los alimentos o la comida en esta imagen y estima sus nutrientes en gramos/kcal.\n"
        "REGLA CRÍTICA: Devolvé números flotantes puros usando punto decimal (.) (ej: 7.5, 42.5).\n"
        "Devolvé EXCLUSIVAMENTE un JSON con esta estructura:\n"
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
# GENERACIÓN DE PDF DE INSTRUCCIONES (/START)
# ==========================================
def generar_pdf_instrucciones_bytes():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=18, leading=22, textColor=colors.HexColor('#1E3A8A'), spaceAfter=4)
    subtitle_style = ParagraphStyle('DocSubtitle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#64748B'), spaceAfter=12)
    section_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontSize=12, leading=16, textColor=colors.HexColor('#2563EB'), spaceBefore=10, spaceAfter=6)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=9, leading=13, textColor=colors.HexColor('#1E293B'), spaceAfter=6)
    badge_style = ParagraphStyle('Badge', parent=styles['Normal'], fontSize=8.5, leading=12, textColor=colors.HexColor('#0F172A'))
    cell_user = ParagraphStyle('CellUser', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor('#1E3A8A'))
    cell_bot = ParagraphStyle('CellBot', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor('#065F46'))

    story = []

    story.append(Paragraph("<b>MANUAL DE USO PROFESIONAL</b>", title_style))
    story.append(Paragraph("<b>Asistente & Bot de Registro Nutricional e Inteligencia Artificial</b>", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=12))

    story.append(Paragraph("<b>1. Métodos de Registro Diario</b>", section_style))
    story.append(Paragraph("El bot está equipado con IA para interpretar lenguaje natural mediante tres medios directos:", body_style))
    story.append(Paragraph("• <b>Texto Directo:</b> Describí lo ingerido de manera detallada.", body_style))
    story.append(Paragraph("• <b>Notas de Voz:</b> Enviá un mensaje de voz describiendo tus comidas o rutinas de ejercicio.", body_style))
    story.append(Paragraph("• <b>Fotografía:</b> Sacá una foto clara de tu plato. La IA estimará la composición nutricional.", body_style))
    
    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>2. Buenas Prácticas: Marcas, Cantidades y Unidades</b>", section_style))
    story.append(Paragraph("Para evitar imprecisiones o que el sistema asuma cantidades unitarias por defecto, seguí estas pautas de ingreso:", body_style))

    mockup_data = [
        [Paragraph("📱 <b>SIMULACIÓN EN CELULAR: CÓMO INDICAR CANTIDADES</b>", ParagraphStyle('TitlePhone', parent=styles['Normal'], fontSize=9, textColor=colors.white, fontName="Helvetica-Bold"))],
        [Paragraph("❌ <b>Ingreso impreciso:</b> <i>'Comí galletitas'</i><br/>⚠️ <i>El sistema asumirá 1 sola unidad o un promedio indeterminado.</i>", cell_user)],
        [Paragraph("✅ <b>Ingreso óptimo:</b> <i>'Galletita Granix, 5 unidades'</i> o <i>'50g de galletitas Granix'</i><br/>🎯 <i>Permite calcular exactamente el gramaje y macronutrientes.</i>", cell_bot)],
        [Paragraph("💡 <b>Tip de corrección:</b> Si querés ajustar un registro enviado, podés usar los botones individuales ✏️ Editar en la pantalla de confirmación.", cell_user)]
    ]
    t_mockup = Table(mockup_data, colWidths=[520])
    t_mockup.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#FEF2F2')),
        ('BACKGROUND', (0,2), (-1,2), colors.HexColor('#ECFDF5')),
        ('BACKGROUND', (0,3), (-1,3), colors.HexColor('#F8FAFC')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
    ]))
    story.append(t_mockup)
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>3. Gestión de Fechas y Registro Madrugada</b>", section_style))
    story.append(Paragraph("• <b>Formato Estándar de Fecha:</b> Toda fecha introducida manualmente debe ser <b>AAAA-MM-DD</b> (ejemplo: <code>2026-07-30</code>).", body_style))
    story.append(Paragraph("• <b>Formato de Mes para Reportes:</b> Se ingresa como <b>AAAA-MM</b> (ejemplo: <code>2026-07</code>).", body_style))
    story.append(Paragraph("• <b>Regla de Madrugada:</b> Si registrás una comida entre las <b>00:00 y las 02:00 hs</b>, el bot la asociará automáticamente a la <b>Cena del día anterior</b>.", body_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>4. Comandos Principales de Control</b>", section_style))
    
    cmd_table_data = [
        [Paragraph("<b>Comando</b>", badge_style), Paragraph("<b>Función y Utilidad</b>", badge_style)],
        [Paragraph("<code>/start</code>", badge_style), Paragraph("Inicia el bot y reenvía este manual instructivo en formato PDF.", badge_style)],
        [Paragraph("<code>/diario</code>", badge_style), Paragraph("Despliega el menú de consulta diaria (Hoy, Ayer u Otro Día en formato AAAA-MM-DD).", badge_style)],
        [Paragraph("<code>/resumen</code>", badge_style), Paragraph("Abre el balance del mes con opción de descargar el Reporte PDF completo.", badge_style)],
        [Paragraph("<code>/perfil</code>", badge_style), Paragraph("Configura datos biométricos (edad, sexo, peso, altura, cintura, actividad) para calcular TMB y GET.", badge_style)]
    ]
    t_cmd = Table(cmd_table_data, colWidths=[100, 420])
    t_cmd.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E2E8F0')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_cmd)

    doc.build(story)
    buffer.seek(0)
    return buffer

# ==========================================
# COMANDOS BÁSICOS Y DIARIO
# ==========================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 **¡Hola! Bienvenido a tu Bot de Registro Nutricional.**\n\n"
        "📌 **¿Qué podés hacer?**\n"
        "• Escribí, mandá notas de voz o fotos de tus comidas.\n"
        "• Registrá actividad física (ej: *'Caminata 45 min 200 kcal'*).\n\n"
        "📌 **Comandos disponibles:**\n"
        "• /diario - Ver lo registrado (Hoy, Ayer u Otro día)\n"
        "• /resumen - Seleccionar mes para ver el informe y descargar PDF\n"
        "• /perfil - Configurar tus datos corporales y metabólicos\n\n"
        "📄 *Te adjuntamos la guía completa de uso en formato PDF.*"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
    
    pdf_buf = generar_pdf_instrucciones_bytes()
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=pdf_buf,
        filename="Guia_de_Uso_Bot_Nutricional.pdf",
        caption="📄 **Guía Completa de Instrucciones de Uso**"
    )

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
    tot_c = tot_p = tot_g = tot_h = tot_f = 0.0
    
    for _, r in agrupado.iterrows():
        p_gr = parse_raw_val(r.get('Peso', 0))
        c = parse_raw_val(r.get('Calorias', 0))
        p = parse_raw_val(r.get('Proteinas', 0))
        g = parse_raw_val(r.get('Grasas', 0))
        h = parse_raw_val(r.get('Carbohidratos', 0))
        f = parse_raw_val(r.get('Fibras', 0))
        
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
# MENÚ E INFORME RESUMEN MENSUAL
# ==========================================
async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 Este Mes", callback_data="resumen_estemes"),
            InlineKeyboardButton("📆 Otro Mes", callback_data="resumen_otromes")
        ]
    ])
    await update.message.reply_text("📊 ¿Qué mes querés consultar en el resumen?", reply_markup=keyboard)

async def mostrar_resumen_pantalla(update: Update, context: ContextTypes.DEFAULT_TYPE, mes_str):
    user_id = update.effective_user.id
    df = obtener_datos_mes(user_id, mes_str)
    
    keyboard_options = [
        [
            InlineKeyboardButton("📅 Este Mes", callback_data="resumen_estemes"),
            InlineKeyboardButton("📆 Otro Mes", callback_data="resumen_otromes")
        ]
    ]

    if df.empty:
        msg_empty = f"📊 No hay datos registrados para el mes `{mes_str}`."
        keyboard = InlineKeyboardMarkup(keyboard_options)
        if update.callback_query:
            await update.callback_query.edit_message_text(msg_empty, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await update.message.reply_text(msg_empty, reply_markup=keyboard, parse_mode="Markdown")
        return

    df['Es_Ejercicio'] = df['Calorias'] < 0
    comidas = df[~df['Es_Ejercicio']]
    ejercicios = df[df['Es_Ejercicio']]

    tot_c_in = comidas['Calorias'].sum()
    tot_c_out = ejercicios['Calorias'].abs().sum()
    tot_p = comidas['Proteinas'].sum()
    tot_g = comidas['Grasas'].sum()
    tot_h = comidas['Carbohidratos'].sum()
    tot_f = comidas['Fibras'].sum()

    dias_cnt = max(df['Fecha'].nunique(), 1)

    txt = f"📊 **Resumen Nutricional Mensual ({mes_str})**\n\n"
    txt += f"🗓️ **Días con registros:** {dias_cnt}\n"
    txt += f"📥 **Ingesta Total:** {tot_c_in:.0f} kcal (Prom: {tot_c_in/dias_cnt:.0f} kcal/día)\n"
    txt += f"🔥 **Gasto Ejercicio:** {tot_c_out:.0f} kcal\n"
    txt += f"⚖️ **Balance Calorías:** {tot_c_in - tot_c_out:.0f} kcal\n\n"
    txt += "🥗 **Macronutrientes Totales:**\n"
    txt += f"💪 Prot: {tot_p:.1f}g | 🥑 Grasas: {tot_g:.1f}g\n"
    txt += f"🍞 Carbs: {tot_h:.1f}g | 🌾 Fibras: {tot_f:.1f}g\n\n"

    perfil = obtener_perfil(user_id)
    metabol = calcular_metabolismo(perfil)
    if metabol:
        gasto_basal_total = metabol['get'] * dias_cnt
        bal_real = tot_c_in - (gasto_basal_total + tot_c_out)
        peso_est = bal_real / 7700
        txt += f"📐 **Estimación Corporal:**\n"
        txt += f"• Balance Neto Real: `{bal_real:+.0f} kcal`\n"
        txt += f"• Cambio de peso est.: `{peso_est:+.2f} kg` ({peso_est*1000:+.0f} g)\n"

    keyboard_options.append([InlineKeyboardButton("📄 Descargar PDF Completo", callback_data=f"pdf_{mes_str}")])
    keyboard = InlineKeyboardMarkup(keyboard_options)

    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update.message.reply_text(txt, reply_markup=keyboard, parse_mode="Markdown")

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
    context.user_data['confirm_msg_id'] = msg.message_id
    context.user_data['chat_id'] = msg.chat_id
        
    await render_confirmation_screen(msg, context)

async def render_confirmation_screen(msg_or_query, context):
    items = context.user_data.get('pending_items', [])
    tipo = context.user_data.get('pending_tipo', 'Comida')
    fecha = context.user_data.get('pending_fecha', obtener_ahora_arg().strftime("%Y-%m-%d"))
    momento = context.user_data.get('pending_momento', 'Almuerzo')

    if not items:
        txt_empty = "🚫 No quedan ítems en esta confirmación."
        markup_empty = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cerrar", callback_data="cancel_entry")]])
        if hasattr(msg_or_query, 'edit_message_text'):
            await msg_or_query.edit_message_text(txt_empty, reply_markup=markup_empty)
        else:
            await msg_or_query.edit_text(txt_empty, reply_markup=markup_empty)
        return

    txt_res = f"📝 **Confirmación ({tipo}):**\n"
    txt_res += f"📅 **Fecha:** `{fecha}`\n"
    if tipo == "Comida":
        txt_res += f"🍽️ **Momento:** `{momento}`\n\n"
    else:
        txt_res += f"🏃 **Tipo:** Actividad Física\n\n"
        
    tot_c = tot_p = tot_g = tot_h = tot_f = 0.0
    
    keyboard = []
    
    # 1. BOTONES DE EDICIÓN Y ELIMINACIÓN POR CADA ÍTEM
    for idx, item in enumerate(items):
        p_gr = parse_raw_val(item.get('peso', 0))
        c = parse_raw_val(item.get('calorias', 0))
        p = parse_raw_val(item.get('proteinas', 0))
        g = parse_raw_val(item.get('grasas', 0))
        h = parse_raw_val(item.get('carbohidratos', 0))
        f = parse_raw_val(item.get('fibras', 0))
        tot_c += c; tot_p += p; tot_g += g; tot_h += h; tot_f += f
        
        txt_res += f"**{idx+1}. {item['alimento']}** ({p_gr:.0f}g):\n"
        if c >= 0:
            txt_res += f"  └ {c:.0f} kcal | P: {p:.1f}g | G: {g:.1f}g | H: {h:.1f}g | Fib: {f:.1f}g\n"
        else:
            txt_res += f"  └ Calorías Quemadas: {abs(c):.0f} kcal\n"
            
        # Fila de botones para este ítem específico
        keyboard.append([
            InlineKeyboardButton(f"✏️ Edit #{idx+1}", callback_data=f"edit_item_{idx}"),
            InlineKeyboardButton(f"❌ Del #{idx+1}", callback_data=f"del_item_{idx}")
        ])
        
    txt_res += f"\n🔥 **Total Calorías:** {tot_c:.0f} kcal\n"

    # 2. BOTONES DE MOMENTO DE COMIDA
    if tipo == "Comida":
        keyboard.append([
            InlineKeyboardButton("🌅 Desayuno", callback_data="mom_Desayuno"),
            InlineKeyboardButton("☀️ Almuerzo", callback_data="mom_Almuerzo"),
            InlineKeyboardButton("☕ Merienda", callback_data="mom_Merienda"),
            InlineKeyboardButton("🌙 Cena", callback_data="mom_Cena")
        ])
        
    # 3. CONTROLES GENERALES
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
        fecha = context.user_data.get('pending_fecha', obtener_ahora_arg().strftime("%Y-%m-%d"))
        momento = context.user_data.get('pending_momento', 'Almuerzo')

        guardar_en_sheets(user_id, items, fecha, momento, tipo)
        
        # Limpiar estados temporales
        context.user_data.pop('pending_items', None)
        await query.edit_message_text(f"✅ ¡Guardado con éxito en Google Sheets!\n📅 Fecha: `{fecha}`", parse_mode="Markdown")

    elif data == "cancel_entry":
        context.user_data.pop('pending_items', None)
        context.user_data.pop('pending_tipo', None)
        context.user_data.pop('pending_fecha', None)
        context.user_data.pop('pending_momento', None)
        await query.edit_message_text("🚫 **Registro anulado.** No se guardó nada.", parse_mode="Markdown")

    elif data.startswith("edit_item_"):
        idx = int(data.split("_")[2])
        items = context.user_data.get('pending_items', [])
        if idx < len(items):
            item = items[idx]
            context.user_data['editing_item_idx'] = idx
            await query.edit_message_text(
                f"✏️ **Modificando:** {item['alimento']}\n\n"
                f"Escribí la nueva descripción/cantidad de este ítem (ej: *'150g'* o *'2 milanesas de 120g'*):",
                parse_mode="Markdown"
            )

    elif data.startswith("del_item_"):
        idx = int(data.split("_")[2])
        items = context.user_data.get('pending_items', [])
        if idx < len(items):
            items.pop(idx)
            context.user_data['pending_items'] = items
            await render_confirmation_screen(query, context)

    elif data.startswith("mom_"):
        context.user_data['pending_momento'] = data.split("_")[1]
        await render_confirmation_screen(query, context)

    elif data == "cambiar_fecha_confirm":
        await query.edit_message_text("✍️ Escribí la fecha en formato **AAAA-MM-DD** (ej: `2026-07-30`):", parse_mode="Markdown")
        context.user_data['esperando_fecha'] = True

    elif data == "diario_hoy":
        hoy_str = obtener_ahora_arg().strftime("%Y-%m-%d")
        await consultar_diario_fecha(update, context, hoy_str)
        
    elif data == "diario_ayer":
        ayer_str = (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d")
        await consultar_diario_fecha(update, context, ayer_str)
        
    elif data == "diario_otrodia":
        await query.edit_message_text("✍️ Escribí la fecha a consultar en formato **AAAA-MM-DD** (ej: `2026-07-25`):", parse_mode="Markdown")
        context.user_data['esperando_fecha_diario'] = True

    elif data == "resumen_estemes":
        mes_actual = obtener_ahora_arg().strftime("%Y-%m")
        await mostrar_resumen_pantalla(update, context, mes_actual)

    elif data == "resumen_otromes":
        await query.edit_message_text("✍️ Escribí el mes que querés consultar en formato **AAAA-MM** (ej: `2026-06`):", parse_mode="Markdown")
        context.user_data['esperando_mes_resumen'] = True

    elif data.startswith("pdf_"):
        mes_target = data.split("_")[1]
        user_id = query.from_user.id
        await query.edit_message_text("📄 Generando PDF del reporte...", parse_mode="Markdown")
        
        df = obtener_datos_mes(user_id, mes_target)
        perfil = obtener_perfil(user_id)
        metabol = calcular_metabolismo(perfil)
        
        pdf_buf = generar_pdf_bytes(user_id, mes_target, df, perfil, metabol)
        
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=pdf_buf,
            filename=f"Reporte_Nutricional_{mes_target}.pdf",
            caption=f"📈 **Reporte Nutricional PDF - {mes_target}**"
        )

# ==========================================
# MANEJO DE ENTRADAS DE TEXTO DE USUARIO
# ==========================================
async def handle_text_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # 1. MODIFICACIÓN DE ÍTEM INDIVIDUAL
    if 'editing_item_idx' in context.user_data:
        idx = context.user_data.pop('editing_item_idx')
        items = context.user_data.get('pending_items', [])
        
        if idx < len(items):
            msg = await update.message.reply_text("🔄 Recalculando ítem con IA...")
            try:
                # Re-analizar solo el ítem modificado
                nombre_orig = items[idx]['alimento']
                res = analizar_con_groq(f"{nombre_orig}: {text}")
                new_items = res.get("items", [])
                
                if new_items:
                    items[idx] = new_items[0]
                    context.user_data['pending_items'] = items
                await msg.delete()
            except Exception as e:
                await update.message.reply_text(f"❌ Error al recalcular: {e}")

            msg_confirm = await update.message.reply_text("Actualizando panel...")
            await render_confirmation_screen(msg_confirm, context)
            return

    # 2. CAMBIO DE FECHA
    if context.user_data.get('esperando_fecha'):
        if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
            context.user_data['pending_fecha'] = text
            context.user_data['esperando_fecha'] = False
            msg = await update.message.reply_text("Actualizando...")
            await render_confirmation_screen(msg, context)
        else:
            await update.message.reply_text("❌ Formato incorrecto. Mandalo como `AAAA-MM-DD` (ej: `2026-07-30`).")
        return

    # 3. OTRO DÍA DIARIO
    if context.user_data.get('esperando_fecha_diario'):
        if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
            context.user_data['esperando_fecha_diario'] = False
            await consultar_diario_fecha(update, context, text)
        else:
            await update.message.reply_text("❌ Formato incorrecto. Mandalo como `AAAA-MM-DD` (ej: `2026-07-25`).")
        return

    # 4. OTRO MES RESUMEN
    if context.user_data.get('esperando_mes_resumen'):
        if re.match(r'^\d{4}-\d{2}$', text):
            context.user_data['esperando_mes_resumen'] = False
            await mostrar_resumen_pantalla(update, context, text)
        else:
            await update.message.reply_text("❌ Formato incorrecto. Mandalo como `AAAA-MM` (ej: `2026-06`).")
        return

    await handle_message(update, context)

# ==========================================
# GENERACIÓN DE PDF MENSUAL
# ==========================================
def generar_pdf_bytes(user_id, mes_str, df, perfil, metabol):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1E3A8A'), spaceAfter=8)
    sub_style = ParagraphStyle('SubTitle', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#2563EB'), spaceAfter=6)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8.5, leading=12)

    story = []

    # HOJA 1: RESUMEN MENSUAL
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

    # HOJA 2: ANÁLISIS METABÓLICO Y ESTIMACIÓN CORPORAL
    story.append(Paragraph("<b>Análisis Metabólico y Estimación Corporal</b>", title_style))
    story.append(Spacer(1, 10))

    if perfil and metabol:
        p_sexo = perfil.get('Sexo', perfil.get('sexo', 'N/A'))
        p_edad = perfil.get('Edad', perfil.get('edad', 'N/A'))
        p_peso = perfil.get('Peso_kg', perfil.get('peso', perfil.get('Peso_g', 'N/A')))
        p_altura = perfil.get('Altura_cm', perfil.get('altura', perfil.get('Altura_mm', 'N/A')))
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
