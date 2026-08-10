import os
import re
import io
import json
import base64
import threading
import inspect
import logging
import unicodedata

from datetime import datetime, date, timedelta, time
import pytz
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from groq import Groq
from dotenv import load_dotenv
from flask import Flask, request, render_template_string

# ReportLab para PDF
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

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

logger = logging.getLogger(__name__)

# Definición de franjas horarias (sin tildes)
FRANJAS_COMIDAS = {
    "Desayuno": (6, 11),
    "Almuerzo": (11, 16),
    "Merienda": (16, 19),
    "Cena": (19, 24)
}

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_SHEETS_KEY_PATH = os.getenv("GOOGLE_SHEETS_KEY_PATH", "credentials.json")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "Registro_Nutricional_Bot")

ARG_TZ = pytz.timezone('America/Argentina/Buenos_Aires')

if GROQ_API_KEY:
    client_ai = Groq(api_key=GROQ_API_KEY)
else:
    client_ai = None

# =======================================================================
#                               PAGINA WEB
# =======================================================================

# Servidor Flask para Web Service en Render con Interfaz Interactiva
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Nutricional - Interfaz Web</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 40px; }
        .container { max-width: 650px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        h1 { color: #2563eb; font-size: 24px; margin-bottom: 8px; }
        p.subtitle { color: #64748b; margin-top: 0; margin-bottom: 24px; font-size: 14px; }
        .status-badge { display: inline-block; background: #dcfce7; color: #166534; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; margin-bottom: 20px; }
        textarea { width: 100%; height: 100px; padding: 12px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; resize: vertical; box-sizing: border-box; }
        textarea:focus { outline: none; border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,0.1); }
        button { background: #2563eb; color: white; border: none; padding: 12px 24px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; margin-top: 12px; transition: background 0.2s; }
        button:hover { background: #1d4ed8; }
        .result-box { margin-top: 24px; background: #f1f5f9; padding: 16px; border-radius: 8px; border-left: 4px solid #2563eb; white-space: pre-wrap; font-size: 14px; }
        .error-box { background: #fee2e2; border-left-color: #dc2626; color: #991b1b; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Bot Nutricional - Consultas AI</h1>
        <p class="subtitle">Desglose instantáneo de nutrientes mediante Inteligencia Artificial.</p>
        <div class="status-badge">● Bot Nutricional activo y funcionando</div>
        
        <form method="POST">
            <label for="comida" style="display:block; font-weight:600; margin-bottom:8px; font-size:14px;">Describí tu comida libre:</label>
            <textarea name="comida" id="comida" placeholder="Ej: BigMac con fritas, coca regular, ensalada césar y helado...">{{ query_text or '' }}</textarea>
            <br>
            <button type="submit">Consultar Nutrientes con IA</button>
        </form>

        {% if resultado %}
            <div class="result-box">
                <strong>Desglose nutricional estimado:</strong><br><br>
                {{ resultado }}
            </div>
        {% elif error %}
            <div class="result-box error-box">
                <strong>Error:</strong> {{ error }}
            </div>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def health_check():
    resultado = None
    error = None
    query_text = ""
    if request.method == 'POST':
        query_text = request.form.get('comida', '').strip()
        if query_text:
            try:
                data = analizar_con_groq(query_text)
                items = data.get("items", [])
                res_lines = []
                tot_cal = 0
                tot_prot = 0
                tot_gras = 0
                tot_carb = 0
                tot_fibr = 0
                for it in items:
                    c = parse_raw_val(it.get('calorias', 0))
                    p = parse_raw_val(it.get('proteinas', 0))
                    g = parse_raw_val(it.get('grasas', 0))
                    cb = parse_raw_val(it.get('carbohidratos', 0))
                    f = parse_raw_val(it.get('fibras', 0))
                    tot_cal += c
                    tot_prot += p
                    tot_gras += g
                    tot_carb += cb
                    tot_fibr += f
                    res_lines.append(f"• {it.get('alimento')} ({it.get('peso',0)}g): {c:.1f} kcal | Prot: {p:.1f}g | Gras: {g:.1f}g | Carb: {cb:.1f}g | Fibr: {f:.1f}g")
                
                res_lines.append(f"\n---\nTOTALES: {tot_cal:.1f} kcal | Prot: {tot_prot:.1f}g | Gras: {tot_gras:.1f}g | Carb: {tot_carb:.1f}g | Fibr: {tot_fibr:.1f}g")
                resultado = "\n".join(res_lines)
            except Exception as e:
                error = str(e)
    return render_template_string(HTML_TEMPLATE, resultado=resultado, error=error, query_text=query_text)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# Estados de conversación para Perfil y Fecha personalizada
AWAITING_PROFILE_DATA, AWAITING_CUSTOM_DATE, AWAITING_RESUMEN_MES, AWAITING_EDIT_ITEM = range(4)

# =========================================================================
#                 FUNCIONES AUXILIARES Y FORMATO
# ==========================================================================
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
    return num / 1000.0

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
    
def calcular_proteina_sugerida(user_id=123456789):
    try:
        ahora_mes = obtener_ahora_arg().strftime("%Y-%m")
        perfil = obtener_perfil_usuario(user_id=user_id, mes_target=ahora_mes)
        if not perfil:
            peso = 75.0
            peso_ideal = 75.0
        else:
            peso = parse_raw_val(perfil.get('Peso', 75.0))
            peso_ideal = parse_raw_val(perfil.get('Peso_Ideal', perfil.get('Peso_ideal', peso)))
            if peso_ideal <= 0:
                peso_ideal = peso * 0.85
    except Exception:
        peso = 75.0
        peso_ideal = 75.0

    peso_efectivo = (peso + peso_ideal) / 2.0
    return peso_efectivo
    
def calcular_tmb_y_get(peso_actual, altura_cm, edad, genero="masculino", actividad="sedentario", contextura="grande", peso_ideal=None):
    peso_actual = parse_raw_val(peso_actual)
    peso_ideal_val = parse_raw_val(peso_ideal)

    if peso_ideal_val <= 0:
        peso_ideal_val = peso_actual * 0.85

    peso_efectivo = (peso_actual + peso_ideal_val) / 2.0

    if str(genero).lower() in ["femenino", "f", "mujer"]:
        tmb = 655 + (9.6 * peso_efectivo) + (1.8 * altura_cm) - (4.7 * edad)
    else:
        tmb = 66 + (13.7 * peso_efectivo) + (5 * altura_cm) - (6.8 * edad)

    factores = {
        "sedentario": 1.2,
        "jubilado": 1.2,
        "ligero": 1.375,
        "moderado": 1.55,
        "intenso": 1.725
    }
    factor = factores.get(str(actividad).lower(), 1.2)
    get_val = tmb * factor

    return tmb, get_val
    
# =======================================================================
#                          GOOGLE SHEETS OPERACIONES
# ========================================================================
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
            ws = spreadsheet.add_worksheet(title=title, rows="1000", cols="10")
            ws.append_row(["Fecha", "Momento/Actividad", "Alimento/Detalle", "Peso (g)", "Calorías (kcal)", "Proteínas (g)", "Grasas (g)", "Hidratos (g)", "Fibras (g)"])
            return ws
        elif title.startswith("Presion_"):
            ws = spreadsheet.add_worksheet(title=title, rows="500", cols="5")
            ws.append_row(["Fecha_Hora", "Fecha_Dia", "Alta", "Baja", "Pulsaciones"])
            return ws
        elif title.startswith("Perfil_"):
            ws = spreadsheet.add_worksheet(title=title, rows="100", cols="7")
            ws.append_row(["EDAD", "PESO", "ALTURA", "GENERO", "OCUPACION", "MES", "Fecha_Actualizacion"])
            return ws
        elif title == "Plantillas_Comidas":
            ws = spreadsheet.add_worksheet(title=title, rows="100", cols="8")
            ws.append_row(["Nombre", "Descripcion", "Peso", "Calorias", "Proteinas", "Grasas", "Carbohidratos", "Fibras"])
            return ws
        else:
            return spreadsheet.add_worksheet(title=title, rows="200", cols="10")

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
    ws.append_row([
        ahora.strftime("%Y-%m-%d %H:%M:%S"), 
        ahora.strftime("%Y-%m-%d"), 
        to_sheet_int(alta), 
        to_sheet_int(baja), 
        to_sheet_int(pulsaciones) if pulsaciones is not None else 0
    ])

# ===============================================================================================================
#                     COMANDOS PERFIL
# ===============================================================================================================

async def cmd_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw_text = update.message.text.replace('/perfil', '').strip()
    ahora = obtener_ahora_arg()
    mes_actual = ahora.strftime("%Y-%m")

    # CASO 1: Ingreso de peso (/perfil 82.5)
    if raw_text:
        try:
            texto_limpio = raw_text.split()[0].replace(',', '.')
            nuevo_peso = float(texto_limpio)
            
            # Se guardan el peso y el mes. La función tolera más parámetros si vinieran de otro lado.
            guardar_perfil_en_sheets(user_id, nuevo_peso, mes_actual)
            
            # Recargar el perfil actualizado
            perfil_actualizado = obtener_perfil_usuario(user_id, mes_target=mes_actual)
            
            if perfil_actualizado:
                edad = parse_raw_val(perfil_actualizado.get('EDAD', perfil_actualizado.get('Edad', 64)))
                altura = parse_raw_val(perfil_actualizado.get('ALTURA', perfil_actualizado.get('Altura', 170)))
                genero = str(perfil_actualizado.get('GENERO', perfil_actualizado.get('Genero', 'masculino')))
                ocupacion = str(perfil_actualizado.get('OCUPACION', perfil_actualizado.get('Ocupacion', 'Jubilado')))
            else:
                edad, altura, genero, ocupacion = 200.0, 200.0, "masculino", "Jubilado"

            tmb, get_val = calcular_tmb_y_get(nuevo_peso, altura, edad, genero, ocupacion)
            
            await update.message.reply_text(
                f"✅ **Peso actualizado correctamente para el mes `{mes_actual}`:**\n\n"
                f"• Nuevo Peso: `{nuevo_peso:.1f}` kg\n"
                f"• **TMB Estimada:** `{tmb:.0f} kcal/día`\n"
                f"• **GET Estimado:** `{get_val:.0f} kcal/día`",
                parse_mode="Markdown"
            )
            return

        except ValueError:
            await update.message.reply_text("❌ Por favor, ingresá un número válido para el peso. Ejemplo: `/perfil 82.5`", parse_mode="Markdown")
            return
        except Exception as e:
            print(f"Error al procesar /perfil en Sheets: {e}")
            await update.message.reply_text(f"⚠️ Ocurrió un error al intentar guardar en la planilla: {e}", parse_mode="Markdown")
            return

    # CASO 2: Consulta (/perfil solo)
    try:
        perfil = obtener_perfil_usuario(user_id, mes_target=mes_actual)

        if perfil:
            peso = parse_raw_val(perfil.get('PESO', perfil.get('Peso')))
            altura = parse_raw_val(perfil.get('ALTURA', perfil.get('Altura')))
            edad = parse_raw_val(perfil.get('EDAD', perfil.get('Edad')))
            genero = str(perfil.get('GENERO', perfil.get('Genero', 'masculino')))
            ocupacion = str(perfil.get('OCUPACION', perfil.get('Ocupacion', 'Jubilado')))

            tmb, get_val = calcular_tmb_y_get(peso, altura, edad, genero, ocupacion)
            
            txt = (
                f"👤 **Perfil Biométrico Actual ({mes_actual}):**\n\n"
                f"• Edad: `{edad:.0f}` años\n"
                f"• Peso: `{peso:.1f}` kg\n"
                f"• Altura: `{altura:.1f}` cm\n"
                f"• Género: `{genero}`\n"
                f"• Ocupación: `{ocupacion}`\n"
                f"• **TMB Estimada:** `{tmb:.0f} kcal/día`\n"
                f"• **GET Estimado:** `{get_val:.0f} kcal/día`\n\n"
                f"📌 **Para actualizar tu peso mensual:**\n"
                f"`/perfil 82.5`"
            )
        else:
            txt = f"👤 **Perfil no registrado para este mes.** Podés cargar tu peso ejecutando:\n`/perfil 82.5`"

        await update.message.reply_text(txt, parse_mode="Markdown")
    except Exception as e:
        print(f"Error al consultar /perfil: {e}")
        await update.message.reply_text(f"⚠️ Ocurrió un error al leer tu perfil: {e}", parse_mode="Markdown")

def guardar_perfil_en_sheets(user_id, peso, mes=None, edad=None, altura=None, genero=None, ocupacion=None, *args, **kwargs):
    """
    Guarda/actualiza el peso del usuario manteniendo intactos los formatos 
    y valores de las columnas históricas (ALTURA, EDAD, Peso_ideal) sin volver a multiplicarlos.
    """
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    ws = get_or_create_worksheet(sh, f"Perfil_{user_id}")
    ahora = obtener_ahora_arg()
    
    if not mes:
        mes = ahora.strftime("%Y-%m")
    
    records = ws.get_all_records()
    
    # Variables crudas para guardar directamente en el Excel
    edad_raw = edad if edad is not None else 64000
    altura_raw = altura if altura is not None else 172000
    genero_final = genero if genero is not None else "masculino"
    ocupacion_final = ocupacion if ocupacion is not None else "Jubilado"
    peso_ideal_final = ""
    fecha_cumple_str = ""
    fila_a_actualizar = None

    # 1. Recuperar valores existentes en la planilla exactamente como están guardados
    if records:
        ultimo_registro = records[-1]
        
        # Leemos el valor directo de la celda (ej: 172000 o 64000)
        if edad is None:
            edad_raw = ultimo_registro.get('EDAD', ultimo_registro.get('Edad', 64000))

        if altura is None:
            altura_raw = ultimo_registro.get('ALTURA', ultimo_registro.get('Altura', 172000))

        if genero is None:
            genero_final = str(ultimo_registro.get('GENERO', ultimo_registro.get('Genero', ultimo_registro.get('Sexo', 'masculino'))))
        
        if ocupacion is None:
            ocupacion_final = str(ultimo_registro.get('OCUPACION', ultimo_registro.get('Ocupacion', 'Jubilado')))
        
        peso_ideal_final = ultimo_registro.get('Peso_ideal', ultimo_registro.get('peso_ideal', ''))
        fecha_cumple_str = str(ultimo_registro.get('Cumple', ultimo_registro.get('cumple', ''))).strip()

        # Verificar si la fila del mes en curso ya existe
        for idx, row in enumerate(records, start=2):
            mes_en_fila = str(row.get('MES', row.get('Mes', ''))).strip()
            if mes_en_fila == str(mes):
                fila_a_actualizar = idx
                break

    # 2. Recalcular la edad automáticamente si cambió el año por el cumpleaños
    if fecha_cumple_str:
        try:
            if "-" in fecha_cumple_str:
                partes = fecha_cumple_str.split("-")
                fnac = datetime.strptime(fecha_cumple_str, "%Y-%m-%d") if len(partes[0]) == 4 else datetime.strptime(fecha_cumple_str, "%d-%m-%Y")
            elif "/" in fecha_cumple_str:
                fnac = datetime.strptime(fecha_cumple_str, "%d/%m/%Y")
            else:
                fnac = None

            if fnac:
                edad_calculada = ahora.year - fnac.year - ((ahora.month, ahora.day) < (fnac.month, fnac.day))
                if edad_calculada > 0:
                    # Si se recalculó la edad en años reales, aplicamos to_sheet_int
                    edad_raw = to_sheet_int(edad_calculada)
        except Exception as e:
            print(f"Error al calcular edad desde Cumple ({fecha_cumple_str}): {e}")

    # 3. Armado de fila: Solo se aplica to_sheet_int al PESO ingresado nuevo
    nueva_fila = [
        str(edad_raw),                       # A: EDAD (se respeta el valor leído)
        to_sheet_int(peso),                  # B: PESO (se convierte a miles)
        str(altura_raw),                     # C: ALTURA (se respeta el valor leído)
        str(genero_final),                   # D: GENERO
        str(ocupacion_final),                # E: OCUPACION
        str(mes),                            # F: MES
        ahora.strftime("%Y-%m-%d %H:%M:%S"),  # G: Fecha_Actualiza
        str(peso_ideal_final),               # H: Peso_ideal
        str(fecha_cumple_str)                # I: Cumple
    ]

    # 4. Actualización en Sheets
    if fila_a_actualizar:
        ws.update(f"A{fila_a_actualizar}:I{fila_a_actualizar}", [nueva_fila])
    else:
        ws.append_row(nueva_fila)

    # 5. Actualizar la pestaña usuarios
    try:
        ws_usuarios = sh.worksheet("usuarios")
        cell = ws_usuarios.find(str(user_id))
        if cell:
            headers = ws_usuarios.row_values(1)
            col_idx = (headers.index("Ultimo Mes Peso") + 1) if "Ultimo Mes Peso" in headers else 4
            ws_usuarios.update_cell(cell.row, col_idx, str(mes))
    except Exception as e:
        print(f"Error al actualizar la pestaña usuarios: {e}")

def obtener_perfil_usuario(user_id, mes_target=None):
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws = get_or_create_worksheet(sh, f"Perfil_{user_id}")
        records = ws.get_all_records()
        if not records:
            return None
        
        perfil_raw = None
        if mes_target:
            for r in reversed(records):
                m_val = str(r.get('MES', r.get('Mes', ''))).strip()
                if m_val == mes_target:
                    perfil_raw = r
                    break
        
        if not perfil_raw:
            perfil_raw = records[-1]
        
        perfil = {}
        for k, v in perfil_raw.items():
            k_upper = str(k).strip().upper()
            if k_upper == 'EDAD':
                perfil['Edad'] = parse_float_from_sheets(v)
            elif k_upper == 'PESO':
                perfil['Peso'] = parse_float_from_sheets(v)
            elif k_upper == 'ALTURA':
                perfil['Altura'] = parse_float_from_sheets(v)
            elif k_upper in ['GENERO', 'SEXO']:
                perfil['Sexo'] = str(v)
            elif k_upper == 'OCUPACION':
                perfil['Ocupacion'] = str(v)
            elif k_upper == 'MES':
                perfil['Mes'] = str(v)

        return perfil
    except Exception as e:
        print(f"Error obteniendo perfil del usuario {user_id}: {e}")
        return None

def obtener_datos_usuario(user_id):
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
            for col in ['Peso', 'Calorias', 'Proteinas', 'Grasas', 'Carbohidratos', 'Fibras']:
                if col in df.columns:
                    df[col] = df[col].apply(parse_float_from_sheets)
                else:
                    df[col] = 0.0
        return df
    except Exception as e:
        print(f"Error al obtener datos del usuario {user_id}: {e}")
        return pd.DataFrame()

# =========================================================================================================================
#               DATOS PLANILLAS
# ============================================================================================================================

def obtener_datos_presion(user_id):
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws = get_or_create_worksheet(sh, f"Presion_{user_id}")
        records = ws.get_all_records()
        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        for col in ['Alta', 'Baja', 'Pulsaciones']:
            if col in df.columns:
                df[col] = df[col].apply(parse_float_from_sheets)

        if 'Fecha_Dia' in df.columns:
            df['Fecha_Dia'] = df['Fecha_Dia'].astype(str).str.strip()

        return df
    except Exception:
        return pd.DataFrame()

def obtener_plantillas_comidas():
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws = get_or_create_worksheet(sh, "Plantillas_Comidas")
        records = ws.get_all_records()
        
        for p in records:
            for k in ['Peso', 'Calorias', 'Proteinas', 'Grasas', 'Carbohidratos', 'Fibras']:
                if k in p:
                    p[k] = parse_float_from_sheets(p[k])
                    
        return records
    except Exception:
        return []

# ====================================================================
#               PROCESAMIENTO IA (TEXTO, VOZ Y FOTO)
# ========================================================================
def analizar_con_groq(prompt_text):
    if not client_ai:
        raise Exception("GROQ_API_KEY no está configurada correctamente.")
    
    system_prompt = """Sos un nutricionista experto. Analizá el texto ingresado.
Devolvé EXCLUSIVAMENTE un JSON con este formato:
{
  "items": [
    {"alimento": "nombre", "peso": 0.0, "calorias": 0.0, "proteinas": 0.0, "grasas": 0.0, "carbohidratos": 0.0, "fibras": 0.0}
  ],
  "tipo": "Comida"
}"""

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
    if not client_ai:
        raise Exception("GROQ_API_KEY no está configurada correctamente.")
    prompt = "Analizá esta imagen de comida/plato. Identificá los alimentos, estimá sus pesos en gramos y nutrientes. Respondé ÚNICAMENTE en formato JSON con la clave 'items' conteniendo alimento, peso, calorias, proteinas, grasas, carbohidratos, fibras."
    response = client_ai.chat.completions.create(
        model="qwen/qwen3.6-27b",
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

async def cmd_comidas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plantillas = obtener_plantillas_comidas()
    if not plantillas:
        await update.message.reply_text("📋 No hay comidas predeterminadas registradas en la hoja 'Plantillas_Comidas'.")
        return

    txt = "📋 **Listado de Comidas Predeterminadas:**\n\n"
    for p in plantillas:
        nombre = p.get('Nombre', '')
        descripcion = p.get('Descripcion') or p.get('Momento', '')
        txt += f"• **{nombre}**: {descripcion}\n"

    txt += "\n📄 Te adjuntamos el archivo en PDF completo con todos los macronutrientes a continuación."
    await update.message.reply_text(txt, parse_mode="Markdown")

    pdf_bytes = generar_pdf_comidas_bytes(plantillas)
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=pdf_bytes,
        filename="Comidas_Predeterminadas.pdf"
    )

async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ahora = obtener_ahora_arg()
    mes_actual = ahora.strftime("%Y-%m")
    mes_anterior = (ahora.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Mes Actual", callback_data=f"resumen_mes_{mes_actual}")],
        [InlineKeyboardButton("📆 Mes Anterior", callback_data=f"resumen_mes_{mes_anterior}")],
        [InlineKeyboardButton("🗓️ Otro Mes", callback_data="resumen_mes_otro")]
    ])

    await update.message.reply_text("📊 **Resumen Mensual:** Seleccioná la opción que querés consultar:", reply_markup=keyboard, parse_mode="Markdown")

# =================================================================
#                 GENERADORES DE PDF
# ==================================================================

def generar_pdf_instrucciones_bytes():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    PRIMARY = colors.HexColor('#0F172A')
    SECONDARY = colors.HexColor('#2563EB')
    TEXT_COLOR = colors.HexColor('#334155')
    BG_LIGHT = colors.HexColor('#F8FAFC')
    BORDER_COLOR = colors.HexColor('#E2E8F0')

    title_style = ParagraphStyle('ModernTitle', parent=styles['Heading1'], fontSize=18, leading=22, textColor=PRIMARY, spaceAfter=4)
    subtitle_style = ParagraphStyle('ModernSubtitle', parent=styles['Normal'], fontSize=10, leading=14, textColor=SECONDARY, spaceAfter=15)
    section_style = ParagraphStyle('ModernSection', parent=styles['Heading2'], fontSize=12, leading=16, textColor=PRIMARY, spaceBefore=12, spaceAfter=6)
    body_style = ParagraphStyle('ModernBody', parent=styles['Normal'], fontSize=9, leading=14, textColor=TEXT_COLOR)
    
    story = []

    header_data = [
        [Paragraph("🤖 Guía Interactiva del Bot Nutricional", title_style)],
        [Paragraph("MANUAL DE USUARIO • ASISTENTE PERSONAL INTELIGENTE", subtitle_style)]
    ]
    header_table = Table(header_data, colWidths=[532])
    header_table.setStyle(TableStyle([
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('LINEBELOW', (0,1), (-1,1), 2, SECONDARY),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("1. Comandos Principales", section_style))
    
    cmds_data = [
        [Paragraph("<b>/start</b>", body_style), Paragraph("Inicia el bot y reenvía este manual informativo actualizado.", body_style)],
        [Paragraph("<b>/comidas</b>", body_style), Paragraph("Visualiza el listado de comidas predeterminadas y descarga su plantilla en PDF.", body_style)],
        [Paragraph("<b>/presion</b>", body_style), Paragraph("Registra valores (Ej: <code>120,80,70</code>) o consulta el resumen mensual de presión (Ej: <code>2026-08</code>).", body_style)],
        [Paragraph("<b>/diario</b>", body_style), Paragraph("Consulta los consumos del día con agrupamiento inteligente y descarga de PDF detallado.", body_style)],
        [Paragraph("<b>/resumen</b>", body_style), Paragraph("Obtiene el reporte mensual con tabla comparativa de macronutrientes y recomendaciones de IA.", body_style)],
        [Paragraph("<b>/perfil</b>", body_style), Paragraph("Consulta o actualiza tus datos biométricos corporales específicos por mes.", body_style)],
    ]
    
    t_cmds = Table(cmds_data, colWidths=[90, 442])
    t_cmds.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_cmds)
    story.append(Spacer(1, 10))

    story.append(Paragraph("2. Métodos de Registro y Multiplicadores", section_style))
    
    input_data = [
        [Paragraph("<b>💬 Texto Libre y Plantillas:</b> Podés escribir tus alimentos de forma natural o utilizar plantillas rápidas con multiplicadores de porción directamente (Ej: <code>*PIZZAJM,4</code> o <code>*CHURRO,0.5</code>).", body_style)],
        [Paragraph("<b>🎤 Notas de Voz:</b> Grabá un audio dictando lo que comiste; el motor de transcripción procesará los datos automáticamente.", body_style)],
        [Paragraph("<b>📸 Fotografías:</b> Enviá una foto de tu plato para que la inteligencia artificial analice los componentes y calcule los macronutrientes.", body_style)]
    ]
    
    t_inputs = Table(input_data, colWidths=[532])
    t_inputs.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('LINEBELOW', (0,0), (-1,-2), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(KeepTogether([t_inputs]))

    doc.build(story)
    buffer.seek(0)
    return buffer

def generar_pdf_comidas_bytes(plantillas):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1E3A8A'))
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#1E293B'))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8.5, leading=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)

    story = [
        Paragraph("<b>LISTADO DE COMIDAS PREDETERMINADAS</b>", title_style),
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=12),
    ]

    if not plantillas:
        story.append(Paragraph("No hay comidas predeterminadas cargadas en la hoja 'Plantillas_Comidas'.", body_style))
    else:
        table_data = [[
            Paragraph("Nombre", header_style), 
            Paragraph("Descripción", header_style), 
            Paragraph("Peso (g)", header_style), 
            Paragraph("Kcal", header_style), 
            Paragraph("Prot (g)", header_style), 
            Paragraph("Gras (g)", header_style), 
            Paragraph("Carb (g)", header_style), 
            Paragraph("Fibr (g)", header_style)
        ]]
        
        for p in plantillas:
            table_data.append([
                Paragraph(str(p.get("Nombre", "")), body_style),
                Paragraph(str(p.get("Descripcion") or p.get("Momento", "")), body_style),
                Paragraph(f"{p.get('Peso', 0):.1f}", body_style),
                Paragraph(f"{p.get('Calorias', 0):.1f}", body_style),
                Paragraph(f"{p.get('Proteinas', 0):.1f}", body_style),
                Paragraph(f"{p.get('Grasas', 0):.1f}", body_style),
                Paragraph(f"{p.get('Carbohidratos', 0):.1f}", body_style),
                Paragraph(f"{p.get('Fibras', 0):.1f}", body_style)
            ])
        
        t = Table(table_data, colWidths=[100, 150, 45, 45, 45, 45, 45, 35])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4)
        ]))
        story.append(t)

    doc.build(story)
    buffer.seek(0)
    return buffer

def generar_pdf_diario_bytes(fecha_str, df_diario, user_id):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1E3A8A'), spaceAfter=4)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor('#1E293B'))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8.5, leading=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)

    story = [
        Paragraph(f"<b>Detalle Diario de Ingestas - {fecha_str}</b>", title_style),
        Paragraph(f"<b>Usuario Telegram ID:</b> {user_id}", body_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=10)
    ]

    if df_diario.empty:
        story.append(Paragraph("No hay registros para esta fecha.", body_style))
    else:
        table_data = [[
            Paragraph("Momento", header_style),
            Paragraph("Alimento / Detalle", header_style),
            Paragraph("Peso", header_style),
            Paragraph("Kcal", header_style),
            Paragraph("Prot", header_style),
            Paragraph("Gras", header_style),
            Paragraph("Carb", header_style),
            Paragraph("Fibr", header_style)
        ]]

        for _, r in df_diario.iterrows():
            table_data.append([
                Paragraph(str(r.get('Momento', '')), body_style),
                Paragraph(str(r.get('Alimento', '')), body_style),
                Paragraph(f"{r.get('Peso', 0):.1f}g", body_style),
                Paragraph(f"{r.get('Calorias', 0):.1f}", body_style),
                Paragraph(f"{r.get('Proteinas', 0):.1f}g", body_style),
                Paragraph(f"{r.get('Grasas', 0):.1f}g", body_style),
                Paragraph(f"{r.get('Carbohidratos', 0):.1f}g", body_style),
                Paragraph(f"{r.get('Fibras', 0):.1f}g", body_style)
            ])

        t = Table(table_data, colWidths=[70, 160, 45, 45, 45, 45, 45, 45])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
        ]))
        story.append(t)
        story.append(Spacer(1, 10))

        c_cons = df_diario[df_diario['Calorias'] > 0]['Calorias'].sum()
        c_quem = abs(df_diario[df_diario['Calorias'] < 0]['Calorias'].sum())
        b_neto = c_cons - c_quem
        story.append(Paragraph(f"• <b>Total Consumidas:</b> {c_cons:.1f} kcal", body_style))
        story.append(Paragraph(f"• <b>Total Quemadas:</b> {c_quem:.1f} kcal", body_style))
        story.append(Paragraph(f"• <b>Balance Neto:</b> {b_neto:.1f} kcal", body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer

def generar_pdf_presion_bytes(mes_str, df_presion, user_id):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1E3A8A'), spaceAfter=4)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor('#1E293B'))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8.5, leading=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)

    story = [
        Paragraph(f"<b>Detalle Diario de Presión Arterial - {mes_str}</b>", title_style),
        Paragraph(f"<b>Usuario Telegram ID:</b> {user_id}", body_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=10)
    ]

    if df_presion.empty:
        story.append(Paragraph("No hay registros de presión para este mes.", body_style))
    else:
        table_data = [[
            Paragraph("Fecha y Hora", header_style),
            Paragraph("Alta (mmHg)", header_style),
            Paragraph("Baja (mmHg)", header_style),
            Paragraph("Pulsaciones (lpm)", header_style)
        ]]

        for _, r in df_presion.iterrows():
            table_data.append([
                Paragraph(str(r.get('Fecha_Hora', '')), body_style),
                Paragraph(f"{r.get('Alta', 0):.0f}", body_style),
                Paragraph(f"{r.get('Baja', 0):.0f}", body_style),
                Paragraph(f"{r.get('Pulsaciones', 0):.0f}", body_style)
            ])

        t = Table(table_data, colWidths=[180, 100, 100, 120])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
        ]))
        story.append(t)

    doc.build(story)
    buffer.seek(0)
    return buffer

# ================================================================
#                  INTERFAZ Y RENDER DE CONFIRMACIÓN
# =================================================================

async def render_confirmation_screen(msg_or_query, context):
    items = context.user_data.get('pending_items', [])
    fecha = context.user_data.get('pending_fecha', obtener_ahora_arg().strftime("%Y-%m-%d"))
    momento = context.user_data.get('pending_momento', 'Comida')

    txt = f"📝 **Confirmación de Ingesta:**\n📅 Fecha: `{fecha}` | Momento: `{momento}`\n\n"
    for idx, item in enumerate(items, start=1):
        mult = item.get('multiplicador', 1.0)
        peso_total = item.get('peso', 0)
        cal_total = item.get('calorias', 0)
        
        alimento_str = item.get('alimento', item.get('nombre', ''))
        alimento_limpio = alimento_str.replace('§', '').strip()

        if mult != 1.0:
            txt += f"**{idx}. {alimento_limpio}** ({peso_total:.1f}g) (x{mult}): `{cal_total:.1f} kcal`\n"
        else:
            txt += f"**{idx}. {alimento_limpio}** ({peso_total:.1f}g): `{cal_total:.1f} kcal`\n"

    keyboard = []
    
    m_buttons = []
    for m in ["Desayuno", "Almuerzo", "Merienda", "Cena"]:
        mark = "✅ " if m.lower() == momento.lower() else ""
        m_buttons.append(InlineKeyboardButton(f"{mark}{m}", callback_data=f"set_m_{m}"))
    keyboard.append(m_buttons)

    es_plantilla = any('§' in item.get('alimento', item.get('nombre', '')) for item in items)

    if not es_plantilla:
        for idx, item in enumerate(items, start=1):
            nombre_corto = item.get('alimento', item.get('nombre', ''))[:10]
            keyboard.append([
                InlineKeyboardButton(f"#{idx} {nombre_corto}", callback_data=f"noop_{idx}"),
                InlineKeyboardButton("✏️ Editar", callback_data=f"edit_item_{idx}"),
                InlineKeyboardButton("❌ Anular", callback_data=f"del_item_{idx}")
            ])

    hoy_str = obtener_ahora_arg().strftime("%Y-%m-%d")
    ayer_str = (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d")
    mark_hoy = "✅ " if fecha == hoy_str else ""
    mark_ayer = "✅ " if fecha == ayer_str else ""
    mark_otro = "✅ " if fecha not in [hoy_str, ayer_str] else ""

    keyboard.append([
        InlineKeyboardButton(f"{mark_hoy}Hoy", callback_data="set_d_hoy"),
        InlineKeyboardButton(f"{mark_ayer}Ayer", callback_data="set_d_ayer"),
        InlineKeyboardButton(f"{mark_otro}Otro Día", callback_data="set_d_otro")
    ])

    keyboard.append([
        InlineKeyboardButton("🗑️ ELIMINAR TODO", callback_data="cancel_entry"),
        InlineKeyboardButton("💾 GUARDAR", callback_data="confirm_save")
    ])

    markup = InlineKeyboardMarkup(keyboard)

    # -----------------------------------------------------------------
    # ACTUALIZACIÓN EN PANTALLA
    # -----------------------------------------------------------------
    if hasattr(msg_or_query, 'edit_message_text'):
        # Si la llamada viene de presionar un botón Inline
        await msg_or_query.edit_message_text(txt, reply_markup=markup, parse_mode="Markdown")
    else:
        # Si viene desde un mensaje de texto/edición
        msg_id = context.user_data.get('last_menu_msg_id')
        chat_id = msg_or_query.effective_chat.id if hasattr(msg_or_query, 'effective_chat') else None

        editado = False
        if msg_id and chat_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=txt,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
                editado = True
            except Exception as e:
                logger.error(f"Error al editar tarjeta existente: {e}")
                editado = False

        if not editado and hasattr(msg_or_query, 'message') and msg_or_query.message:
            nuevo_msg = await msg_or_query.message.reply_text(txt, reply_markup=markup, parse_mode="Markdown")
            context.user_data['last_menu_msg_id'] = nuevo_msg.message_id
            
async def procesar_y_mostrar_confirmacion(data_json, msg_obj, context):
    items = data_json.get("items", [])
    if not items:
        await msg_obj.edit_text("❌ No se pudieron detectar alimentos en la consulta.")
        return

    fecha, momento = obtener_momento_y_fecha_auto()
    context.user_data['pending_items'] = items
    context.user_data['pending_fecha'] = fecha
    context.user_data['pending_momento'] = momento

    await render_confirmation_screen(msg_obj, context)

# ===============================================================================
#                 HANDLERS DE TELEGRAM
# =================================================================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 ¡Hola! Bienvenido a tu Bot Nutricional Personalizado.\n\n"
        "📌 Funciones y Comandos Disponibles:\n\n"
        "• `/comidas`: Visualiza listado y descarga PDF.\n"
        "• `/presion 120,80,70` registra alta, baja, pulso.\n"
        "• `/presion 120,80` omite pulso.\n"
        "• `/presion 2026-08` promedio mensual y PDF.\n"
        "• `/diario`: Ingestas del día y PDF detallado.\n"
        "• `/resumen`: Reporte mensual con IA y PDF.\n"
        "• `/actividad caminata,200 cal`: Guardar en excel.\n"
        "• `/actividadia aquagym,50 min`: Guarda por IA.\n"
        "• `/perfil`: Consulta o carga datos biométricos.\n"
        "• `/perfil 90 kg`: Actualiza el peso del mes.\n\n"
        "📌 Ingreso de ingestas:\n\n"
        "• **Del listado precargado:**\n"
        "  `*PIZZAJM` ingresa una unidad de la comida.\n"
        "  `*PIZZAJM,1.5` o `*CHURRO,6` ingresa la cantidad.\n\n"
        "• **Ingreso por IA:**\n"
        "  Texto, Imagen, Voz (descripción, cantidad o peso).\n"
        "• **Modificación:**\n"
        "  Ingresar `COMIDA` se conserva el peso y vuelve a la IA.\n"
        "  Ingresar `COMIDA,PESO` nuevos valores vuelve a la IA.\n\n"
        "📄 Te adjuntamos el manual de instrucciones actualizado en PDF."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
    pdf_buf = generar_pdf_instrucciones_bytes()
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=pdf_buf,
        filename="Manual_Bot_Nutricional.pdf"
    )

# ===============================================================================
#                 ACTIVIDAD EJERCICIOS
# =================================================================================

async def cmd_actividad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto = update.message.text.replace('/actividad', '').strip()
    
    if not texto:
        await update.message.reply_text(
            "⚠️ Por favor ingresá la actividad y las calorías.\nEjemplo: `/actividad caminata, 250 cal`",
            parse_mode="Markdown"
        )
        return

    parte_calorias = texto.split(',')[-1] if ',' in texto else texto
    solo_numeros = re.sub(r'\D', '', parte_calorias)

    if solo_numeros:
        calorias_pos = float(solo_numeros)
    else:
        todos_los_numeros = re.findall(r'\d+', texto)
        if todos_los_numeros:
            calorias_pos = float(todos_los_numeros[-1])
        else:
            await update.message.reply_text(
                "❌ No se detectaron las calorías. Recordá indicar un número ej: `250 cal`.",
                parse_mode="Markdown"
            )
            return

    # Extraemos el nombre limpio de la actividad
    actividad_nombre = texto.split(',')[0].strip() if ',' in texto else texto.strip()

    # Enviamos el mensaje inicial y renderizamos la tarjeta con 2 botones (Confirmar / Anular)
    msg = await update.message.reply_text("⏳ Procesando registro de actividad...")
    await render_tarjeta_actividad(msg, context, actividad_nombre, int(calorias_pos), mostrar_editar=False)
    
# =================================================================================

async def render_tarjeta_actividad(target_msg, context, actividad_nombre, calorias, mostrar_editar=True):
    """Renderiza o actualiza la tarjeta de confirmación de actividad física."""
    context.user_data['pending_actividad'] = {
        'nombre': actividad_nombre,
        'calorias': calorias
    }

    # Selecciona la botonera según el flujo (IA = 3 botones, Manual = 2 botones)
    if mostrar_editar:
        fila_botones = [
            InlineKeyboardButton("✅ Guardar", callback_data="act_save"),
            InlineKeyboardButton("✏️ Editar", callback_data="act_edit"),
            InlineKeyboardButton("🗑️ Borrar", callback_data="act_cancel")
        ]
    else:
        fila_botones = [
            InlineKeyboardButton("✅ Confirmar", callback_data="act_save"),
            InlineKeyboardButton("❌ Anular", callback_data="act_cancel")
        ]

    keyboard = [fila_botones]
    reply_markup = InlineKeyboardMarkup(keyboard)

    txt = (
        f"🏃 **Actividad detectada:** {actividad_nombre}\n"
        f"🔥 **Gasto estimado:** -{calorias} kcal\n\n"
        f"¿Deseás registrar este ejercicio en tu diario?"
    )

    if hasattr(target_msg, 'edit_text'):
        await target_msg.edit_text(txt, parse_mode="Markdown", reply_markup=reply_markup)
    elif hasattr(target_msg, 'edit_message_text'):
        await target_msg.edit_message_text(txt, parse_mode="Markdown", reply_markup=reply_markup)

# =================================================================================
        
async def actividad_ia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto = update.message.text.replace('/actividadia', '').strip()

    if not texto:
        await update.message.reply_text(
            "⚠️ Por favor ingresá la actividad para calcular.\nEjemplo: `/actividadia jugué al fútbol 1 hora`",
            parse_mode="Markdown"
        )
        return

    msg = await update.message.reply_text("🤖 Estimando gasto calórico con IA...")

    try:
        prompt_actividad = (
            f"El usuario realizó la siguiente actividad física: '{texto}'. "
            "Calcula/estima el gasto calórico probable en calorías enteras (valor positivo). "
            "Responde strictly en formato JSON con la siguiente estructura: "
            '{"actividad": "Nombre breve y claro de la actividad", "calorias": 250}'
        )

        chat_completion = client_ai.chat.completions.create(
            messages=[
                {"role": "system", "content": "Sos un asistente experto en ciencias del deporte y nutrición."},
                {"role": "user", "content": prompt_actividad}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            response_format={"type": "json_object"}
        )

        respuesta = json.loads(chat_completion.choices[0].message.content)
        actividad_nombre = respuesta.get("actividad", texto)
        calorias_estimadas = abs(int(respuesta.get("calorias", 0)))

        # Llama a render_tarjeta_actividad con 3 botones por defecto (Guardar, Editar, Borrar)
        await render_tarjeta_actividad(msg, context, actividad_nombre, calorias_estimadas)

    except Exception as e:
        print(f"Error procesando actividad con IA: {e}")
        await msg.edit_text(f"❌ Error al procesar la actividad con IA: {e}")
        
# =================================================================================

async def mostrar_diario_fecha(query_or_update, user_id, fecha_str):
    df = obtener_datos_usuario(user_id)
    
    if df.empty:
        txt = f"📅 No hay registros ingresados para el usuario `{user_id}`."
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(txt, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(txt, parse_mode="Markdown")
        return

    df_diario = df[df['Fecha'] == fecha_str]
    
    if df_diario.empty:
        txt = f"📅 **Registro del día {fecha_str}:**\n\nNo hay registros guardados para este día."
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(txt, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(txt, parse_mode="Markdown")
        return

    momentos_dict = {}
    for _, row in df_diario.iterrows():
        momento = str(row.get("Momento", "General")).strip()
        concepto = str(row.get("Alimento", "")).strip()
        
        if me := momento.title():
            momento = me

        if momento not in momentos_dict:
            momentos_dict[momento] = []
        if concepto:
            momentos_dict[momento].append(concepto)

    lineas_desglose = []
    for momento, ítems in momentos_dict.items():
        cadena_ítems = ", ".join(ítems)
        lineas_desglose.append(f"• {momento}: {cadena_ítems}")

    tot_cons = df_diario[df_diario['Calorias'] > 0]['Calorias'].sum()
    tot_quem = abs(df_diario[df_diario['Calorias'] < 0]['Calorias'].sum())
    bal_neto = tot_cons - tot_quem

    resumen_msg = (
        f"📅 **Registro del día {fecha_str}:**\n\n"
        + "\n".join(lineas_desglose) + "\n\n"
        f"🖥️ **Consumidas:** {tot_cons:.0f} kcal\n"
        f"🔥 **Quemadas:** {tot_quem:.0f} kcal\n"
        f"⚖️ **Balance Neto:** {bal_neto:.0f} kcal"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Descargar PDF del Diario", callback_data=f"descargar_pdf_diario_{fecha_str}")]
    ])

    if hasattr(query_or_update, 'edit_message_text'):
        await query_or_update.edit_message_text(resumen_msg, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await query_or_update.message.reply_text(resumen_msg, reply_markup=keyboard, parse_mode="Markdown")
        

async def cmd_presion_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw_text = update.message.text.replace('/presion', '').strip()
    
    if not raw_text:
        await update.message.reply_text(
            "🩺 Ingresá la presión o consultá un mes. Ejemplos:\n"
            "• `/presion 120,80,70`\n"
            "• `/presion 120,80`\n"
            "• `/presion 2026-08`", 
            parse_mode="Markdown"
        )
        return

    if re.match(r'^20\d{2}-\d{2}$', raw_text):
        await mostrar_resumen_presion_mes(update, user_id, raw_text)
        return

    parts = [p.strip() for p in raw_text.replace('/', ',').replace(' ', ',').split(',') if p.strip()]
    if len(parts) >= 2:
        alta = float(parts[0])
        baja = float(parts[1])
        pulsaciones = float(parts[2]) if len(parts) > 2 else None
        guardar_presion_en_sheets(user_id, alta, baja, pulsaciones)
        pul_str = f" | Pulsaciones: `{pulsaciones}`" if pulsaciones is not None else ""
        await update.message.reply_text(f"✅ **Presión registrada:**\nAlta: `{alta}` | Baja: `{baja}`{pul_str}", parse_mode="Markdown")
        return
    else:
        await update.message.reply_text("❌ Formato incorrecto. Uso: `/presion 120,80,70` o `/presion 120,80` o `/presion 2026-08`", parse_mode="Markdown")

async def mostrar_resumen_presion_mes(query_or_update, user_id, mes_str):
    df_presion = obtener_datos_presion(user_id)
    if df_presion.empty:
        txt = f"🩺 No hay registros de presión arterial para el usuario `{user_id}`."
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(txt, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(txt, parse_mode="Markdown")
        return

    df_p_mes = df_presion[df_presion['Fecha_Dia'].str.startswith(mes_str)] if 'Fecha_Dia' in df_presion.columns else pd.DataFrame()
    if df_p_mes.empty:
        txt = f"🩺 No hay registros de presión para el mes `{mes_str}`."
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(txt, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(txt, parse_mode="Markdown")
        return

    alta_prom = df_p_mes['Alta'].mean()
    baja_prom = df_p_mes['Baja'].mean()
    pul_prom = df_p_mes[df_p_mes['Pulsaciones'] > 0]['Pulsaciones'].mean() if 'Pulsaciones' in df_p_mes.columns else 0

    txt = (
        f"🩺 **Resumen de Presión Arterial ({mes_str}):**\n\n"
        f"• Mediciones registradas: `{len(df_p_mes)}`\n"
        f"• **Promedio Alta (Sistólica):** `{alta_prom:.1f} mmHg`\n"
        f"• **Promedio Baja (Diastólica):** `{baja_prom:.1f} mmHg`\n"
    )
    if pul_prom > 0:
        txt += f"• **Promedio Pulsaciones:** `{pul_prom:.1f} lpm`\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Descargar PDF Presión Diaria", callback_data=f"descargar_pdf_presion_{mes_str}")]
    ])

    if hasattr(query_or_update, 'edit_message_text'):
        await query_or_update.edit_message_text(txt, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await query_or_update.message.reply_text(txt, reply_markup=keyboard, parse_mode="Markdown")

async def generar_y_enviar_pdf_presion(query, user_id, mes_str, context):
    df_presion = obtener_datos_presion(user_id)
    df_p_mes = df_presion[df_presion['Fecha_Dia'].str.startswith(mes_str)] if not df_presion.empty and 'Fecha_Dia' in df_presion.columns else pd.DataFrame()
    
    pdf_bytes = generar_pdf_presion_bytes(mes_str, df_p_mes, user_id)
    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=pdf_bytes,
        filename=f"Presion_Arterial_{mes_str}.pdf"
    )

async def cmd_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Hoy", callback_data="diario_hoy"), InlineKeyboardButton("📆 Ayer", callback_data="diario_ayer")],
        [InlineKeyboardButton("🗓️ Seleccionar Fecha", callback_data="diario_otro")]
    ])
    await update.message.reply_text("📅 **Consulta de Diario:** Seleccioná qué día querés revisar:", reply_markup=keyboard, parse_mode="Markdown")

#===============================================================================================
#                       MANEJADORES HADNLE
#===============================================================================================

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
    msg = await update.message.reply_text("📸 Analizando foto con Inteligencia Artificial...")
    try:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        base64_image = base64.b64encode(photo_bytes).decode('utf-8')
        
        data = analizar_imagen_con_groq(base64_image)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        await msg.edit_text(f"❌ Error al procesar imagen: {e}")

#===============================================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw_text = update.message.text.strip() if update.message and update.message.text else ""

    if not raw_text:
        return

    # =========================================================================
    # 1.a. SI EL USUARIO PRESIONÓ "EDITAR" EN UN ALIMENTO / COMIDA
    # =========================================================================
    if context.user_data.get('awaiting_edit_item_val'):
        idx = context.user_data.get('editing_item_idx')
        items = context.user_data.get('pending_items', [])

        if items is not None and 0 <= idx < len(items):
            item_previo = items[idx]
            peso_previo = item_previo.get('peso', 0.0)

            msg_espera = await update.message.reply_text("⏳ Recalculando alimento con la IA...")
            try:
                prompt_edicion = (
                    f"El usuario quiere editar un alimento.\n"
                    f"Texto ingresado por el usuario: '{raw_text}'\n"
                    f"Si el usuario NO especificó un nuevo peso en gramos en su texto, "
                    f"DEBES usar exactamente este peso anterior: {peso_previo} gramos.\n"
                    f"Devolvé el JSON con los nutrientes recalculados para ese alimento y cantidad."
                )

                nuevo_analisis = analizar_con_groq(prompt_edicion)
                items_nuevos = nuevo_analisis.get('items', [])

                if items_nuevos:
                    items[idx] = items_nuevos[0]
                    context.user_data['pending_items'] = items
                    
                    try:
                        await update.message.delete()  # Limpia el mensaje con el texto enviado por el usuario
                    except Exception:
                        pass

                    context.user_data['awaiting_edit_item_val'] = False
                    context.user_data.pop('editing_item_idx', None)

                    await render_confirmation_screen(msg_espera, context)
                    return
                else:
                    await msg_espera.edit_text("⚠️ No se pudieron interpretar los datos para actualizar el ítem.")

            except Exception as e:
                print(f"Error editando ítem: {e}")
                await msg_espera.edit_text(f"❌ Error al procesar la edición: {e}")

        context.user_data['awaiting_edit_item_val'] = False
        context.user_data.pop('editing_item_idx', None)
        return

    # =========================================================================
    # 1.b. SI EL USUARIO PRESIONÓ "EDITAR" EN UNA ACTIVIDAD FÍSICA
    # =========================================================================
    if context.user_data.get('awaiting_edit_act_val'):
        act_pending = context.user_data.get('pending_actividad', {})
        act_nombre = act_pending.get('nombre', 'Actividad')

        msg_espera = await update.message.reply_text("⏳ Recalculando actividad física...")

        try:
            # 1. Intentar ver si el usuario ingresó un valor directo en calorías (ej: "300 cal" o "300")
            limpio = raw_text.lower().replace("calorias", "").replace("cal", "").replace("kcal", "").strip()
            
            if limpio.isdigit():
                nuevas_calorias = int(limpio)
            else:
                # 2. Si ingresó texto con duración/detalle (ej: "45 min" o "carrera intensa 30 min"), consultamos a la IA
                prompt_recalculo = (
                    f"El usuario está editando una actividad física previamente registrada como '{act_nombre}'. "
                    f"Nueva especificación dada por el usuario: '{raw_text}'. "
                    "Calcula/estima el nuevo gasto calórico en calorías enteras positivas. "
                    "Responde strictly en formato JSON: "
                    '{"actividad": "Nombre breve de la actividad", "calorias": 250}'
                )

                chat_completion = client_ai.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "Sos un asistente experto en ciencias del deporte y nutrición."},
                        {"role": "user", "content": prompt_recalculo}
                    ],
                    model="llama-3.3-70b-versatile",
                    temperature=0.2,
                    response_format={"type": "json_object"}
                )

                respuesta = json.loads(chat_completion.choices[0].message.content)
                act_nombre = respuesta.get("actividad", act_nombre)
                nuevas_calorias = abs(int(respuesta.get("calorias", 0)))

            try:
                await update.message.delete()  # Limpia el texto ingresado por el usuario
            except Exception:
                pass

            context.user_data['awaiting_edit_act_val'] = False
            # Llama a render_tarjeta_actividad con 3 botones (mostrar_editar=True por defecto)
            await render_tarjeta_actividad(msg_espera, context, act_nombre, nuevas_calorias)
            return

        except Exception as e:
            print(f"Error reeditando actividad: {e}")
            await msg_espera.edit_text(f"❌ Error al recalcular la actividad: {e}")

        context.user_data['awaiting_edit_act_val'] = False
        return

    # =========================================================================
    # 2. COMIDAS PRECARGADAS EN PLANTILLAS (MENSAJES QUE EMPIEZAN CON *)
    # =========================================================================
    if raw_text.startswith('*'):
        contenido = raw_text[1:].strip()
        partes = [p.strip() for p in contenido.split(',')]
        nombre_plantilla = partes[0].upper()
        multiplicador = float(partes[1]) if len(partes) > 1 else 1.0

        plantillas = obtener_plantillas_comidas()
        plantilla_encontrada = None
        for p in plantillas:
            if str(p.get('Nombre', '')).strip().upper() == nombre_plantilla:
                plantilla_encontrada = p
                break

        if plantilla_encontrada:
            p_base = parse_raw_val(plantilla_encontrada.get('Peso', 0))
            c_base = parse_raw_val(plantilla_encontrada.get('Calorias', 0))
            pr_base = parse_raw_val(plantilla_encontrada.get('Proteinas', 0))
            g_base = parse_raw_val(plantilla_encontrada.get('Grasas', 0))
            cb_base = parse_raw_val(plantilla_encontrada.get('Carbohidratos', 0))
            f_base = parse_raw_val(plantilla_encontrada.get('Fibras', 0))

            val_descripcion = None
            for k, v in plantilla_encontrada.items():
                if str(k).strip().lower() in ['descripcion', 'descripción']:
                    val_descripcion = v
                    break

            texto_final = str(val_descripcion).strip() if val_descripcion else str(plantilla_encontrada.get('Nombre', 'Comida')).strip()

            if texto_final:
                texto_final = texto_final[:-1].strip()

            item_generado = {
                "alimento": texto_final,
                "peso": p_base * multiplicador,
                "calorias": c_base * multiplicador,
                "proteinas": pr_base * multiplicador,
                "grasas": g_base * multiplicador,
                "carbohidratos": cb_base * multiplicador,
                "fibras": f_base * multiplicador,
                "multiplicador": multiplicador
            }
            
            data_json = {"items": [item_generado], "tipo": "Comida"}
            msg = await update.message.reply_text("⏳ Procesando comida predeterminada...")
            await procesar_y_mostrar_confirmacion(data_json, msg, context)
            return
        else:
            await update.message.reply_text(f"❌ No se encontró la plantilla `*{nombre_plantilla}`.", parse_mode="Markdown")
            return

    # =========================================================================
    # 3. INGRESO DIRECTO DE COMIDA POR TEXTO LIBRE (IA)
    # =========================================================================
    msg = await update.message.reply_text("🤖 Analizando texto con Inteligencia Artificial...")
    try:
        data = analizar_con_groq(raw_text)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        await msg.edit_text(f"❌ Error al procesar el texto: {e}")

#===============================================================================================

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data.startswith("set_m_"):
        nuevo_momento = data.replace("set_m_", "")
        context.user_data['pending_momento'] = nuevo_momento
        await render_confirmation_screen(query, context)

    elif data == "set_d_hoy":
        context.user_data['pending_fecha'] = obtener_ahora_arg().strftime("%Y-%m-%d")
        await render_confirmation_screen(query, context)

    elif data == "set_d_ayer":
        context.user_data['pending_fecha'] = (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d")
        await render_confirmation_screen(query, context)

    elif data.startswith("edit_item_"):
        idx = int(data.replace("edit_item_", "")) - 1
        context.user_data['awaiting_edit_item_val'] = True
        context.user_data['editing_item_idx'] = idx
        await query.message.reply_text("✏️ Ingresá la nueva descripción o peso para este ítem:")

    elif data.startswith("del_item_"):
        idx = int(data.replace("del_item_", "")) - 1
        items = context.user_data.get('pending_items', [])
        if 0 <= idx < len(items):
            items.pop(idx)
            context.user_data['pending_items'] = items
        if not items:
            await query.edit_message_text("❌ Todos los ítems fueron eliminados.")
        else:
            await render_confirmation_screen(query, context)

    elif data == "cancel_entry":
        context.user_data.pop('pending_items', None)
        await query.edit_message_text("🗑️ Registro cancelado.")

    elif data == "confirm_save":
        items = context.user_data.get('pending_items', [])
        fecha = context.user_data.get('pending_fecha')
        momento = context.user_data.get('pending_momento')

        if items and fecha and momento:
            guardar_en_sheets(user_id, items, fecha, momento)
            await query.edit_message_text(f"✅ **¡Ingesta guardada exitosamente!**\n📅 `{fecha}` | `{momento}`", parse_mode="Markdown")
            context.user_data.pop('pending_items', None)
        else:
            await query.edit_message_text("❌ No se encontraron datos para guardar.")

    elif data == "diario_hoy":
        fecha = obtener_ahora_arg().strftime("%Y-%m-%d")
        await mostrar_diario_fecha(query, user_id, fecha)

    elif data == "diario_ayer":
        fecha = (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d")
        await mostrar_diario_fecha(query, user_id, fecha)

    elif data.startswith("resumen_mes_20"):
        mes_str = data.replace("resumen_mes_", "")
        await mostrar_resumen_mes(query, user_id, mes_str)

    elif data.startswith("descargar_pdf_resumen_"):
        mes_str = data.replace("descargar_pdf_resumen_", "")
        await generar_y_enviar_pdf_resumen(query, user_id, mes_str, context)

    elif data.startswith("descargar_pdf_diario_"):
        fecha_str = data.replace("descargar_pdf_diario_", "")
        df = obtener_datos_usuario(user_id)
        df_diario = df[df['Fecha'] == fecha_str] if not df.empty else pd.DataFrame()
        pdf_bytes = generar_pdf_diario_bytes(fecha_str, df_diario, user_id)
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=pdf_bytes,
            filename=f"Diario_Ingestas_{fecha_str}.pdf"
        )

    elif data.startswith("descargar_pdf_presion_"):
        mes_str = data.replace("descargar_pdf_presion_", "")
        await generar_y_enviar_pdf_presion(query, user_id, mes_str, context)

    elif data.startswith("save_act_"):
        partes = data.replace("save_act_", "").split("_")
        calorias = float(partes[0])
        actividad = partes[1] if len(partes) > 1 else "Actividad Física"
        
        calorias_neg = -abs(calorias)
        fecha_actual = obtener_ahora_arg().strftime("%Y-%m-%d")

        items = [{
            "alimento": f"Ejercicio: {actividad}",
            "peso": 0.0,
            "calorias": calorias_neg,
            "proteinas": 0.0,
            "grasas": 0.0,
            "carbohidratos": 0.0,
            "fibras": 0.0
        }]

        guardar_en_sheets(user_id, items, fecha_actual, "Actividad Física", tipo="Actividad")
        await query.edit_message_text(
            f"✅ **Actividad física registrada con éxito:**\n"
            f"• Actividad: `{actividad}`\n"
            f"• Gasto: `{calorias_neg:.0f} kcal`",
            parse_mode="Markdown"
        )

    elif data == "cancel_act":
        await query.edit_message_text("❌ Registro de actividad cancelado.")

# ===========================================================================
#               PANTALLA Y PDF RESUMEN MES
# ===========================================================================

# ==============================================================================
# 1. RECOMENDACIÓN EXTENSA PARA PDF (~500 - 600 PALABRAS)
# ================================================================================

def generar_recomendacion_ia(promedios: dict, metas: dict, biometria: dict = None) -> str:
    """
    Genera un informe nutricional detallado y extenso (~500-600 palabras)
    con diagnóstico integral, alimentos a incorporar y alimentos a evitar.
    """
    if biometria is None:
        biometria = {}

    peso_act = biometria.get('peso_actual', 0.0)
    peso_id = biometria.get('peso_ideal', 0.0)
    
    cal_r, cal_m = promedios.get('calorias', 0), metas.get('calorias', 2000)
    prot_r, prot_m = promedios.get('proteinas', 0), metas.get('proteinas', 100)
    gras_r, gras_m = promedios.get('grasas', 0), metas.get('grasas', 55)
    carb_r, carb_m = promedios.get('carbohidratos', 0), metas.get('carbohidratos', 200)
    fibr_r, fibr_m = promedios.get('fibras', 0), metas.get('fibras', 25)

    bloques = []

    # Seccion 1: Diagnostico
    bloques.append(
        "<b>1. DIAGNÓSTICO NUTRICIONAL INTEGRAL DEL MES</b>\n"
        f"Tras analizar minuciosamente tus registros diarios frente a los requerimientos teóricos calculados para tu perfil, "
        f"se observan tendencias clave en tu patron de alimentacion. En cuanto al balance energetico, registras un promedio "
        f"de <b>{cal_r:.0f} kcal/dia</b> frente a un objetivo de <b>{cal_m:.0f} kcal/dia</b>. "
        f"Al evaluar la distribucion de macronutrientes, tu ingesta proteica promedia <b>{prot_r:.1f}g</b> (meta: {prot_m:.1f}g), "
        f"las grasas alcanzan <b>{gras_r:.1f}g</b> (meta: {gras_m:.1f}g), los carbohidratos se ubican en <b>{carb_r:.1f}g</b> "
        f"(meta: {carb_m:.1f}g) y la fibra aporta <b>{fibr_r:.1f}g</b> (meta: {fibr_m:.1f}g). "
        f"Este perfil refleja desvíos específicos que requieren ajustes estratégicos para optimizar el metabolismo, mejorar la composición "
        f"corporal de forma progresiva y asegurar la saciedad sin comprometer el nivel de energía diario."
    )

    # Seccion 2: Analisis por Macronutriente
    lineas_analisis = ["<b>2. ANÁLISIS DE BRECHAS Y DESVÍOS ESPECÍFICOS</b>"]
    
    # Calorias
    if cal_r > cal_m * 1.1:
        lineas_analisis.append(f"• <b>Exceso Calórico:</b> Estás consumiendo un {((cal_r/cal_m)-1)*100:.1f}% por encima de la meta. Es prioritario reducir la densidad calórica de los platos para no enlentecer la pérdida de peso.")
    elif cal_r < cal_m * 0.85:
        lineas_analisis.append(f"• <b>Déficit Calórico Pronunciado:</b> Tu ingesta está un {((1-(cal_r/cal_m))*100):.1f}% por debajo. Ojo con restringir demasiado, ya que puede ralentizar el metabolismo y generar pérdida de masa muscular.")
    else:
        lineas_analisis.append("• <b>Calorías Normocalóricas/Equilibradas:</b> Tu consumo energético total se mantiene alineado con las metas planificadas.")

    # Fibra
    if fibr_r < fibr_m * 0.85:
        lineas_analisis.append(f"• <b>Déficit de Fibras ({fibr_r:.1f}g vs {fibr_m:.1f}g):</b> La baja ingesta dificulta la salud intestinal, perjudica el control glucémico y reduce la saciedad a largo plazo.")
    else:
        lineas_analisis.append(f"• <b>Nivel Nutritivo de Fibra Óptimo:</b> Estás cubriendo adecuadamente la cuota de digestibilidad y salud microbiana.")

    # Grasas
    if gras_r > gras_m * 1.15:
        lineas_analisis.append(f"• <b>Exceso de Grasas ({gras_r:.1f}g vs {gras_m:.1f}g):</b> Un aporte elevado de grasas (especialmente saturadas) suma calorías rápidamente sin aportar volumen ni saciedad duradera.")
    elif gras_r < gras_m * 0.8:
        lineas_analisis.append(f"• <b>Déficit de Grasas Saludables:</b> Requiere atención para mantener un perfil hormonal óptimo.")
    else:
        lineas_analisis.append(f"• <b>Balance de Grasas Adecuado:</b> Ingesta lipídica controlada dentro de los rangos meta.")

    # Carbohidratos
    if carb_r < carb_m * 0.85:
        lineas_analisis.append(f"• <b>Déficit de Carbohidratos Complejos ({carb_r:.1f}g vs {carb_m:.1f}g):</b> Esto puede ocasionar fatiga, bajo rendimiento físico y antojos de azúcares al final de la jornada.")
    elif carb_r > carb_m * 1.15:
        lineas_analisis.append(f"• <b>Exceso de Carbohidratos:</b> Es conveniente reemplazar carbohidratos refinados por opciones complejas de menor índice glucémico.")
    else:
        lineas_analisis.append(f"• <b>Nivel de Carbohidratos Estable:</b> Buen balance de hidratos para energía constante.")

    # Proteinas
    if prot_r < prot_m * 0.85:
        lineas_analisis.append(f"• <b>Déficit Proteico ({prot_r:.1f}g vs {prot_m:.1f}g):</b> Fundamental aumentar su presencia para preservar la masa magra y aumentar la termogénesis alimentaria.")

    bloques.append("\n".join(lineas_analisis))

    # Seccion 3: Alimentos Sugeridos (Incorporar)
    lineas_inc = ["<b>3. ALIMENTOS Y COMIDAS QUE DEBERÍAS INGERIR (PARA SUPLIR DÉFICITS)</b>"]
    if fibr_r < fibr_m * 0.85:
        lineas_inc.append("• <b>Para la Fibra:</b> Incorporá 1 porción diaria de legumbres (lentejas, garbanzos, porotos) en ensaladas o guisos magros. Sumá 1 a 2 cucharadas de semillas (chía o lino hidratadas) en tus desayunos, y consumí frutas enteras con cáscara (manzana, pera, frutos rojos).")
    if carb_r < carb_m * 0.85:
        lineas_inc.append("• <b>Para Carbohidratos Complejos:</b> Sumá fuentes de absorción lenta como avena integral, quinoa, arroz integral, batata, choclo o mandioca hervida. Te darán energía sostenida sin picos glucémicos.")
    if prot_r < prot_m * 0.85:
        lineas_inc.append("• <b>Para Proteínas Magras:</b> Priorizá pechuga de pollo/pavo, claras de huevo, atún al natural, cortes vacunos magros (peceto, cuadril, bola de lomo), queso blanco magro y yogur griego natural sin azúcar.")
    if len(lineas_inc) == 1:
        lineas_inc.append("• Mantené la variedad de vegetales de hoja verde, hortalizas multicolores y cereales integrales para sostener tus excelentes promedios.")
    bloques.append("\n".join(lineas_inc))

    # Seccion 4: Alimentos a Reducir/Omitir (Excesos)
    lineas_red = ["<b>4. ALIMENTOS Y COMIDAS QUE DEBERÍAS REDUCIR O EVITAR (PARA CORREGIR EXCESOS)</b>"]
    if gras_r > gras_m * 1.15:
        lineas_red.append("• <b>Grasas y Frituras:</b> Evitá carnes vacunas de corte graso (costilla, asado, entraña), fiambres, embutidos (chorizos, salchichas), aderezos industriales (mayonesa, salsa golf), frituras y manteca/crema. Reemplazalos por aceite de oliva en crudo (1 cucharadita) y cocciones al horno o plancha.")
    if carb_r > carb_m * 1.15 or cal_r > cal_m * 1.1:
        lineas_red.append("• <b>Ultraprocesados y Azúcares:</b> Reducí al mínimo productos de panadería refinados, galletitas dulces/saladas, gaseosas azucaradas, jugos industriales y harinas blancas refinadas.")
    if len(lineas_red) == 1:
        lineas_red.append("• Moderá el uso de aceites al cocinar y controlá las porciones de frutos secos o quesos duros para no sobrepasar la densidad calórica.")
    bloques.append("\n".join(lineas_red))

    # Seccion 5: Plan de Accion y Cierre
    bloques.append(
        "<b>5. RECOMENDACIÓN GENERAL Y ESTRATEGIA DE HÁBITOS</b>\n"
        "Para consolidar estos cambios, asegurá una ingesta de agua potable de al menos <b>2 a 2.5 litros diarios</b>. "
        "La hidratación adecuada optimiza la función renal, mejora el tránsito intestinal favorecido por la fibra y ayuda a "
        "diferenciar la sed real de la ansiedad. Organizá tus compras semanales en base a las fuentes proteicas magras y vegetales frescos "
        "sugeridos, garantizando platos estructurados con la regla del plato (50% vegetales, 25% proteína magra, 25% carbohidrato complejo)."
    )

    return "\n\n".join(bloques)

# =========================================================================
# 2. RECOMENDACIÓN BREVE PARA PANTALLA (~100 PALABRAS)
# =========================================================================

def obtener_recomendacion_ia(resumen_texto: str) -> str:
    if 'client_ai' not in globals() or not client_ai:
        return (
            "Ajustá tu balance diario moderando las grasas saturadas e incrementando fibras con legumbres, "
            "semillas y vegetales frescos. Priorizá proteínas magras y carbohidratos complejos. "
            "¡Mantené la constancia y asegurá 2 litros de agua al día!"
        )
    
    prompt = (
        "Basado en el siguiente resumen nutricional, redactá una recomendación BREVE, DIRECTA Y MOTIVADORA "
        "de EXACTAMENTE 90 a 110 PALABRAS (no te pases de 120 palabras). "
        "Resumí los desvíos principales de fibra, grasas o carbohidratos y menciona 2 o 3 alimentos concretos a incorporar y a evitar:\n\n"
        f"{resumen_texto}"
    )

    try:
        response = client_ai.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return (
            "Ajustá tu balance diario moderando las grasas saturadas e incrementando fibras con legumbres, "
            "semillas y vegetales frescos. Priorizá proteínas magras y carbohidratos complejos. "
            "¡Mantené la constancia y asegurá 2 litros de agua al día!"
        )

# ========================================================================
# 3. MOSTRAR RESUMEN MES (TELEGRAM HANDLER)
# ========================================================================

async def mostrar_resumen_mes(query_or_update, user_id, mes_str):
    try:
        df_datos = obtener_datos_usuario(user_id)
        
        if df_datos is None or df_datos.empty:
            txt = f"📊 No hay registros ingresados para el usuario `{user_id}`."
            if hasattr(query_or_update, 'edit_message_text'):
                await query_or_update.edit_message_text(txt, parse_mode="Markdown")
            else:
                await query_or_update.message.reply_text(txt, parse_mode="Markdown")
            return

        df_mes = df_datos[df_datos['Fecha'].astype(str).str.startswith(mes_str)] if 'Fecha' in df_datos.columns else pd.DataFrame()
        if df_mes.empty:
            txt = f"📊 No hay registros para el mes `{mes_str}`."
            if hasattr(query_or_update, 'edit_message_text'):
                await query_or_update.edit_message_text(txt, parse_mode="Markdown")
            else:
                await query_or_update.message.reply_text(txt, parse_mode="Markdown")
            return

        dias_registrados = df_mes['Fecha'].nunique()
        if dias_registrados == 0:
            dias_registrados = 1

        tot_cons_mes = df_mes[df_mes['Calorias'] > 0]['Calorias'].sum() if 'Calorias' in df_mes.columns else 0.0
        tot_quem_mes = abs(df_mes[df_mes['Calorias'] < 0]['Calorias'].sum()) if 'Calorias' in df_mes.columns else 0.0

        prom_cons = tot_cons_mes / dias_registrados
        prom_quem = tot_quem_mes / dias_registrados
        prom_bal_neto = prom_cons - prom_quem
        
        tot_prot = df_mes['Proteinas'].sum() if 'Proteinas' in df_mes.columns else 0.0
        tot_gras = df_mes['Grasas'].sum() if 'Grasas' in df_mes.columns else 0.0
        tot_carb = df_mes['Carbohidratos'].sum() if 'Carbohidratos' in df_mes.columns else 0.0
        tot_fibr = df_mes['Fibras'].sum() if 'Fibras' in df_mes.columns else 0.0

        prom_cal = tot_cons_mes / dias_registrados
        prom_prot = tot_prot / dias_registrados
        prom_gras = tot_gras / dias_registrados
        prom_carb = tot_carb / dias_registrados
        prom_fibr = tot_fibr / dias_registrados

        # --- LECTURA DE DATOS BIOMÉTRICOS SIN VALORES POR DEFECTO ---
        edad = None
        altura = None
        peso_mes_especifico = None
        peso_ideal_base = None
        genero = "M"

        try:
            gc = get_gspread_client()
            sh = gc.open(SPREADSHEET_NAME)
            ws_perfil = get_or_create_worksheet(sh, f"Perfil_{user_id}")
            registros_perfil = ws_perfil.get_all_records()

            if registros_perfil:
                perfil_mes = None
                for r in registros_perfil:
                    r_lower = {str(k).strip().lower(): v for k, v in r.items()}
                    val_mes = str(r_lower.get("mes", "")).strip()
                    if val_mes == str(mes_str).strip():
                        perfil_mes = r_lower
                        break

                if perfil_mes:
                    def parse_val_strict(v):
                        try:
                            n = parse_float_from_sheets(v)
                            if n == 0:
                                return None
                            return n / 1000.0 if n > 500 else n
                        except:
                            return None

                    v_edad = perfil_mes.get("edad")
                    edad = int(parse_val_strict(v_edad)) if parse_val_strict(v_edad) else None
                    altura = parse_val_strict(perfil_mes.get("altura"))
                    peso_mes_especifico = parse_val_strict(perfil_mes.get("peso"))
                    
                    p_ideal_raw = perfil_mes.get("peso_ideal") or perfil_mes.get("peso ideal")
                    peso_ideal_base = parse_val_strict(p_ideal_raw)
                    
                    gen_raw = perfil_mes.get("genero")
                    if gen_raw:
                        genero = str(gen_raw).strip().upper()

        except Exception as err_perfil:
            print(f"Error accediendo a Perfil_{user_id}: {err_perfil}")

        # Validación estricta: si falta alguno de los parámetros biométricos, no se procesa ni llama al PDF
        if None in (edad, altura, peso_mes_especifico, peso_ideal_base):
            txt_incompleto = (
                f"⚠️ **Datos biométricos incompletos para el mes `{mes_str}`.**\n\n"
                f"No se ingresaron o están incompletos los datos de edad, altura, peso o peso ideal en tu perfil para este mes. "
                f"Por favor, completá tu perfil del mes para generar el resumen y el reporte PDF."
            )
            if hasattr(query_or_update, 'edit_message_text'):
                await query_or_update.edit_message_text(txt_incompleto, parse_mode="Markdown")
            else:
                await query_or_update.message.reply_text(txt_incompleto, parse_mode="Markdown")
            return

        peso_promedio = (peso_mes_especifico + peso_ideal_base) / 2.0

        if genero == "M":
            tmb = (10 * peso_promedio) + (6.25 * altura) - (5 * edad) + 5
        else:
            tmb = (10 * peso_promedio) + (6.25 * altura) - (5 * edad) - 161

        factor_act = 1.2
        get_meta = tmb * factor_act

        ideal_cal = round(get_meta)
        ideal_prot = round(peso_promedio * 1.5, 1)
        ideal_gras = round((get_meta * 0.25) / 9, 1)
        ideal_carb = round((get_meta * 0.50) / 4, 1)
        ideal_fibr = 25.0

        dict_promedios = {
            'calorias': prom_cal,
            'proteinas': prom_prot,
            'grasas': prom_gras,
            'carbohidratos': prom_carb,
            'fibras': prom_fibr
        }

        dict_metas = {
            'calorias': ideal_cal,
            'proteinas': ideal_prot,
            'grasas': ideal_gras,
            'carbohidratos': ideal_carb,
            'fibras': ideal_fibr
        }

        dict_biometria = {
            'peso_actual': peso_mes_especifico,
            'peso_ideal': peso_ideal_base,
            'altura': altura,
            'edad': edad
        }

        # Genera la recomendación extensa (~500-600 palabras) para el PDF
        recomendacion_pdf = generar_recomendacion_ia(dict_promedios, dict_metas, dict_biometria)

        # Genera la recomendación corta (~100 palabras) para pantalla
        str_contexto_peso = (
            f"- Peso registrado en el mes {mes_str}: {peso_mes_especifico:.1f} kg\n"
            f"- Peso Meta Progresivo objetivo del mes: {peso_promedio:.1f} kg\n"
        )
        prompt_para_ia_pantalla = (
            f"REPORTE NUTRICIONAL DEL MES ({mes_str}):\n"
            f"{str_contexto_peso}"
            f"CONSUMO PROMEDIO DIARIO ({dias_registrados} días registrados):\n"
            f"- Calorías: {prom_cal:.0f} kcal (Meta: {ideal_cal:.0f} kcal)\n"
            f"- Proteínas: {prom_prot:.1f} g (Meta: {ideal_prot:.1f} g)\n"
            f"- Grasas: {prom_gras:.1f} g (Meta: {ideal_gras:.1f} g)\n"
            f"- Carbohidratos: {prom_carb:.1f} g (Meta: {ideal_carb:.1f} g)\n"
            f"- Fibras: {prom_fibr:.1f} g (Meta: {ideal_fibr:.1f} g)\n"
        )
        recomendacion_pantalla = obtener_recomendacion_ia(prompt_para_ia_pantalla)

        # Guarda la recomendación extensa en context.user_data para que la recupere el PDF
        if hasattr(query_or_update, 'user_data'):
            query_or_update.user_data['ultima_recomendacion_ia'] = recomendacion_pdf

        txt = (
            f"📊 **Reporte Nutricional Mensual ({mes_str}):**\n\n"
            f"• **Promedio Consumidas:** `{prom_cons:.0f} kcal` / día\n"
            f"• **Promedio Quemadas:** `{prom_quem:.0f} kcal` / día\n"
            f"• **Balance Neto Diario:** `{prom_bal_neto:.0f} kcal` / día\n\n"
            f"• Días con registro: `{dias_registrados}`\n"
            f"📈 **Promedio Diario vs. Objetivos:**\n"
            f"• **Calorías:** `{prom_cal:.0f} kcal` / Meta: `{ideal_cal:.0f} kcal`\n"
            f"• **Proteínas:** `{prom_prot:.1f} g` / Meta: `{ideal_prot:.1f} g`\n"
            f"• **Grasas:** `{prom_gras:.1f} g` / Meta: `{ideal_gras:.1f} g`\n"
            f"• **Carbohidratos:** `{prom_carb:.1f} g` / Meta: `{ideal_carb:.1f} g`\n"
            f"• **Fibras:** `{prom_fibr:.1f} g` / Meta: `{ideal_fibr:.1f} g`\n\n"
            f"🤖 **Recomendación de la IA:**\n"
            f"{recomendacion_pantalla}\n\n"
            f"📄 Podés descargar el reporte completo en PDF a continuación:"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📄 Descargar PDF Resumen Mensual", callback_data=f"descargar_pdf_resumen_{mes_str}")]
        ])

        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(txt, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(txt, reply_markup=keyboard, parse_mode="Markdown")

    except Exception as e:
        error_txt = f"⚠️ Ocurrió un error al procesar el resumen: `{str(e)}`"
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(error_txt, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(error_txt, parse_mode="Markdown")
            

# ======================================================================
#      GENERAR PDF RESUMEN BYTES (FORZADO DE REPORTE COMPLETO)
# ====================================================================

def generar_pdf_resumen_bytes(mes_str, df_mes, df_presion, perfil, tmb_val, recomendacion, user_id):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1E3A8A'), spaceAfter=4)
    sub_style = ParagraphStyle('SubTitle', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#2563EB'), spaceBefore=8, spaceAfter=4)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8, leading=11, textColor=colors.HexColor('#1E293B'))
    rec_style = ParagraphStyle('RecBody', parent=styles['Normal'], fontSize=8, leading=11, textColor=colors.HexColor('#0F172A'), spaceAfter=4)
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)

    story = [
        Paragraph(f"<b>Reporte Nutricional Mensual - {mes_str}</b>", title_style),
        Paragraph(f"<b>Usuario Telegram ID:</b> {user_id}", body_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=8)
    ]

    headers_h1 = ["Fecha", "Cal. Consumid.", "Cal. Quemad.", "Bal. Neto", "Proteinas (g)", "Grasas (g)", "Carbohidratos (g)", "Fibras (g)"]
    table_data_h1 = [[Paragraph(h, header_style) for h in headers_h1]]

    tot_cons, tot_quem, tot_prot, tot_gras, tot_carb, tot_fibr = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    if df_mes is not None and not df_mes.empty:
        fechas_unicas = sorted(df_mes['Fecha'].unique())
        dias_con_registro = len(fechas_unicas)

        for f in fechas_unicas:
            sub = df_mes[df_mes['Fecha'] == f]
            
            c_cons = sub[sub['Calorias'] > 0]['Calorias'].sum() if 'Calorias' in sub.columns else 0.0
            c_quem = abs(sub[sub['Calorias'] < 0]['Calorias'].sum()) if 'Calorias' in sub.columns else 0.0
            b_neto = c_cons - c_quem
            
            prot = float(sub['Proteinas'].sum()) if 'Proteinas' in sub.columns else 0.0
            gras = float(sub['Grasas'].sum()) if 'Grasas' in sub.columns else 0.0
            carb = float(sub['Carbohidratos'].sum()) if 'Carbohidratos' in sub.columns else 0.0
            fibr = float(sub['Fibras'].sum()) if 'Fibras' in sub.columns else 0.0

            tot_cons += c_cons
            tot_quem += c_quem
            tot_prot += prot
            tot_gras += gras
            tot_carb += carb
            tot_fibr += fibr

            table_data_h1.append([
                Paragraph(str(f), body_style),
                Paragraph(f"{c_cons:.1f} kcal", body_style),
                Paragraph(f"{c_quem:.1f} kcal", body_style),
                Paragraph(f"{b_neto:.1f} kcal", body_style),
                Paragraph(f"{prot:.1f} g", body_style),
                Paragraph(f"{gras:.1f} g", body_style),
                Paragraph(f"{carb:.1f} g", body_style),
                Paragraph(f"{fibr:.1f} g", body_style)
            ])
        
        tot_neto = tot_cons - tot_quem
        table_data_h1.append([
            Paragraph("<b>TOTAL MES</b>", body_style),
            Paragraph(f"<b>{tot_cons:.1f} kcal</b>", body_style),
            Paragraph(f"<b>{tot_quem:.1f} kcal</b>", body_style),
            Paragraph(f"<b>{tot_neto:.1f} kcal</b>", body_style),
            Paragraph(f"<b>{tot_prot:.1f} g</b>", body_style),
            Paragraph(f"<b>{tot_gras:.1f} g</b>", body_style),
            Paragraph(f"<b>{tot_carb:.1f} g</b>", body_style),
            Paragraph(f"<b>{tot_fibr:.1f} g</b>", body_style)
        ])

        div = dias_con_registro if dias_con_registro > 0 else 1
        table_data_h1.append([
            Paragraph("<b>PROM. DIARIO</b>", body_style),
            Paragraph(f"<b>{(tot_cons/div):.1f} kcal</b>", body_style),
            Paragraph(f"<b>{(tot_quem/div):.1f} kcal</b>", body_style),
            Paragraph(f"<b>{(tot_neto/div):.1f} kcal</b>", body_style),
            Paragraph(f"<b>{(tot_prot/div):.1f} g</b>", body_style),
            Paragraph(f"<b>{(tot_gras/div):.1f} g</b>", body_style),
            Paragraph(f"<b>{(tot_carb/div):.1f} g</b>", body_style),
            Paragraph(f"<b>{(tot_fibr/div):.1f} g</b>", body_style)
        ])

    t1 = Table(table_data_h1, colWidths=[65, 75, 70, 70, 65, 60, 80, 55])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0, -2), (-1, -1), colors.HexColor('#F1F5F9'))
    ]))
    story.append(t1)

    story.append(PageBreak())
    story.append(Paragraph("<b>Análisis Metabólico y Tabla Comparativa de Macronutrientes</b>", title_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=8))

    # --- DATOS BIOMÉTRICOS Y METABÓLICOS ---
    def _parse_val(v, default):
        try:
            val_str = str(v).replace(',', '.').strip()
            n = float(val_str)
            if n == 0: return default
            return n / 1000.0 if n > 500 else n
        except:
            return default

    perfil_dict = perfil if isinstance(perfil, dict) else {}
    edad = int(_parse_val(perfil_dict.get('Edad', perfil_dict.get('edad')), 64))
    peso_actual = _parse_val(perfil_dict.get('Peso', perfil_dict.get('peso')), 108.5)
    altura = _parse_val(perfil_dict.get('Altura', perfil_dict.get('altura')), 172.0)
    
    p_ideal_raw = perfil_dict.get('Peso_ideal') or perfil_dict.get('peso_ideal') or perfil_dict.get('Peso Ideal')
    peso_ideal_excel = _parse_val(p_ideal_raw, 75.0)

    peso_ideal_promedio = (peso_actual + peso_ideal_excel) / 2.0 if peso_actual > 0 else peso_ideal_excel

    genero = str(perfil_dict.get('Genero', perfil_dict.get('genero', perfil_dict.get('Sexo', 'M')))).strip().upper()
    if genero == "M":
        tmb_calc = (10 * peso_ideal_promedio) + (6.25 * altura) - (5 * edad) + 5
    else:
        tmb_calc = (10 * peso_ideal_promedio) + (6.25 * altura) - (5 * edad) - 161

    get_ideal = tmb_calc * 1.2
    dias_activos = df_mes['Fecha'].nunique() if (df_mes is not None and not df_mes.empty) else 1

    get_total_ideal = get_ideal * dias_activos
    bal_calorico = tot_cons - get_total_ideal - tot_quem
    cambio_peso_kg = bal_calorico / 7700.0

    prot_rec = round(peso_ideal_promedio * 1.5, 1)
    gras_rec = round((get_ideal * 0.25) / 9.0, 1)
    carb_rec = round((get_ideal * 0.50) / 4.0, 1)
    fibr_rec = 25.0

    prom_d_cons = (tot_cons / dias_activos) if dias_activos > 0 else 0
    prom_d_prot = (tot_prot / dias_activos) if dias_activos > 0 else 0
    prom_d_gras = (tot_gras / dias_activos) if dias_activos > 0 else 0
    prom_d_carb = (tot_carb / dias_activos) if dias_activos > 0 else 0
    prom_d_fibr = (tot_fibr / dias_activos) if dias_activos > 0 else 0

    table_comp = [
        [Paragraph("<b>Nutriente / Métrica</b>", header_style), Paragraph("<b>Promedio Diario Real (Mes)</b>", header_style), Paragraph("<b>Valor Ideal (Peso Promedio)</b>", header_style)],
        [Paragraph("Calorías", body_style), Paragraph(f"{prom_d_cons:.1f} kcal", body_style), Paragraph(f"{get_ideal:.1f} kcal (GET)", body_style)],
        [Paragraph("Proteínas", body_style), Paragraph(f"{prom_d_prot:.1f} g", body_style), Paragraph(f"{prot_rec:.1f} g", body_style)],
        [Paragraph("Grasas", body_style), Paragraph(f"{prom_d_gras:.1f} g", body_style), Paragraph(f"{gras_rec:.1f} g", body_style)],
        [Paragraph("Carbohidratos", body_style), Paragraph(f"{prom_d_carb:.1f} g", body_style), Paragraph(f"{carb_rec:.1f} g", body_style)],
        [Paragraph("Fibras", body_style), Paragraph(f"{prom_d_fibr:.1f} g", body_style), Paragraph(f"{fibr_rec:.1f} g", body_style)]
    ]
    t_comp = Table(table_comp, colWidths=[150, 185, 185])
    t_comp.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    story.append(t_comp)
    story.append(Spacer(1, 8))

    story.append(Paragraph(f"• <b>PERFIL BASE ({mes_str}):</b> Peso Actual: {peso_actual:.1f} kg | Peso Ideal Calculado (Promedio): {peso_ideal_promedio:.1f} kg | Altura: {altura:.1f} cm", body_style))
    story.append(Paragraph(f"• <b>BALANCE CALÓRICO NETO PROYECTADO:</b> {bal_calorico:.1f} kcal", body_style))
    story.append(Paragraph(f"• <b>CAMBIO ESTIMADO DE PESO EN EL MES:</b> {cambio_peso_kg:.2f} kg ({cambio_peso_kg*1000:.1f} g)", body_style))

    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>Recomendación Nutricional Personalizada y Plan de Acción (IA):</b>", sub_style))

    # --- REEMPLAZO FORZADO: EVALÚA ESTRUCTURA DE SECCIONES O LONGITUD DE 1200 CARACTERES ---
    texto_final = recomendacion
    es_texto_corto = not isinstance(texto_final, str) or len(texto_final.strip()) < 1200 or "<b>1. DIAGNÓSTICO" not in texto_final

    if es_texto_corto:
        p_dict = {'calorias': prom_d_cons, 'proteinas': prom_d_prot, 'grasas': prom_d_gras, 'carbohidratos': prom_d_carb, 'fibras': prom_d_fibr}
        m_dict = {'calorias': get_ideal, 'proteinas': prot_rec, 'grasas': gras_rec, 'carbohidratos': carb_rec, 'fibras': fibr_rec}
        b_dict = {'peso_actual': peso_actual, 'peso_ideal': peso_ideal_excel, 'altura': altura, 'edad': edad}
        
        if 'generar_recomendacion_ia' in globals():
            texto_final = generar_recomendacion_ia(p_dict, m_dict, b_dict)
        else:
            lineas = [
                "<b>1. DIAGNÓSTICO NUTRICIONAL INTEGRAL DEL MES</b>",
                f"Tras analizar minuciosamente tus registros diarios frente a los requerimientos teóricos calculados para tu perfil, se observan tendencias clave en tu patrón de alimentación. En cuanto al balance energético, registras un promedio de <b>{prom_d_cons:.0f} kcal/día</b> frente a un objetivo de <b>{get_ideal:.0f} kcal/día</b>. Al evaluar la distribución de macronutrientes, tu ingesta proteica promedia <b>{prom_d_prot:.1f}g</b> (meta: {prot_rec:.1f}g), las grasas alcanzan <b>{prom_d_gras:.1f}g</b> (meta: {gras_rec:.1f}g), los carbohidratos se ubican en <b>{prom_d_carb:.1f}g</b> (meta: {carb_rec:.1f}g) y la fibra aporta <b>{prom_d_fibr:.1f}g</b> (meta: {fibr_rec:.1f}g). Este perfil refleja desvíos específicos que requieren ajustes estratégicos para optimizar el metabolismo, mejorar la composición corporal de forma progresiva y asegurar la saciedad sin comprometer el nivel de energía diario.",
                "\n<b>2. ANÁLISIS DE BRECHAS Y DESVÍOS ESPECÍFICOS</b>"
            ]
            if prom_d_cons > get_ideal * 1.1:
                lineas.append(f"• <b>Exceso Calórico:</b> Estás consumiendo un {((prom_d_cons/get_ideal)-1)*100:.1f}% por encima de la meta. Es prioritario reducir la densidad calórica de los platos.")
            elif prom_d_cons < get_ideal * 0.85:
                lineas.append(f"• <b>Déficit Calórico Pronunciado:</b> Tu ingesta está un {((1-(prom_d_cons/get_ideal))*100):.1f}% por debajo de lo recomendado.")
            
            if prom_d_fibr < fibr_rec * 0.85:
                lineas.append(f"• <b>Déficit de Fibras ({prom_d_fibr:.1f}g vs {fibr_rec:.1f}g):</b> La baja ingesta dificulta la salud intestinal, perjudica el control glucémico y reduce la saciedad a largo plazo.")
            if prom_d_gras > gras_rec * 1.15:
                lineas.append(f"• <b>Exceso de Grasas ({prom_d_gras:.1f}g vs {gras_rec:.1f}g):</b> Un aporte elevado de grasas suma calorías rápidamente sin aportar volumen ni saciedad duradera.")
            if prom_d_prot < prot_rec * 0.85:
                lineas.append(f"• <b>Déficit Proteico ({prom_d_prot:.1f}g vs {prot_rec:.1f}g):</b> Fundamental aumentar su presencia para preservar la masa magra y aumentar la termogénesis alimentaria.")

            lineas.append("\n<b>3. ALIMENTOS Y COMIDAS QUE DEBERÍAS INGERIR (PARA SUPLIR DÉFICITS)</b>")
            if prom_d_fibr < fibr_rec * 0.85:
                lineas.append("• <b>Para la Fibra:</b> Incorporá 1 porción diaria de legumbres (lentejas, garbanzos, porotos) en ensaladas o guisos magros. Sumá 1 a 2 cucharadas de semillas (chía o lino hidratadas) en tus desayunos, y consumí frutas enteras con cáscara (manzana, pera, frutos rojos).")
            if prom_d_prot < prot_rec * 0.85:
                lineas.append("• <b>Para Proteínas Magras:</b> Priorizá pechuga de pollo/pavo, claras de huevo, atún al natural, cortes vacunos magros (peceto, cuadril, bola de lomo), queso blanco magro y yogur griego natural sin azúcar.")

            lineas.append("\n<b>4. ALIMENTOS Y COMIDAS QUE DEBERÍAS REDUCIR O EVITAR (PARA CORREGIR EXCESOS)</b>")
            if prom_d_gras > gras_rec * 1.15:
                lineas.append("• <b>Grasas y Frituras:</b> Evitá carnes vacunas de corte graso (costilla, asado, entraña), fiambres, embutidos (chorizos, salchichas), aderezos industriales (mayonesa, salsa golf), frituras y manteca/crema. Reemplazalos por aceite de oliva en crudo (1 cucharadita) y cocciones al horno o plancha.")

            lineas.append("\n<b>5. RECOMENDACIÓN GENERAL Y ESTRATEGIA DE HÁBITOS</b>\nPara consolidar estos cambios, asegurá una ingesta de agua potable de al menos <b>2 a 2.5 litros diarios</b>. La hidratación adecuada optimiza la función renal, mejora el tránsito intestinal favorecido por la fibra y ayuda a diferenciar la sed real de la ansiedad. Organizá tus compras semanales en base a las fuentes proteicas magras y vegetales frescos sugeridos.")
            
            texto_final = "\n\n".join(lineas)

    # Renderizado en ReportLab
    if isinstance(texto_final, str):
        for bloque in texto_final.strip().split('\n\n'):
            if bloque.strip():
                story.append(Paragraph(bloque.strip().replace('\n', '<br/>'), rec_style))
                story.append(Spacer(1, 4))

    doc.build(story)
    buffer.seek(0)
    return buffer



async def generar_y_enviar_pdf_resumen(query, user_id, mes_str, context):
    df_datos = obtener_datos_usuario(user_id)
    df_mes = df_datos[df_datos['Fecha'].astype(str).str.startswith(mes_str)] if not df_datos.empty and 'Fecha' in df_datos.columns else pd.DataFrame()
    
    df_presion = obtener_datos_presion(user_id)
    df_p_mes = df_presion[df_presion['Fecha_Dia'].str.startswith(mes_str)] if not df_presion.empty and 'Fecha_Dia' in df_presion.columns else pd.DataFrame()
    
    perfil = obtener_perfil_usuario(user_id, mes_target=mes_str)
    
    recomendacion = context.user_data.get('ultima_recomendacion_ia') if context and hasattr(context, 'user_data') else None
    
    if not recomendacion:
        dias_act = df_mes['Fecha'].nunique() if not df_mes.empty else 1
        p_act = parse_raw_val(perfil.get('Peso')) if perfil else 108.5
        p_id = parse_raw_val(perfil.get('Peso_ideal', perfil.get('Peso_Ideal', 75.0))) if perfil else 75.0
        p_prom = (p_act + p_id) / 2.0
        
        tot_c = df_mes[df_mes['Calorias'] > 0]['Calorias'].sum() if not df_mes.empty else 0
        prompt_ia = f"Resumen {mes_str}: Consumo diario {(tot_c/dias_act):.0f} kcal. Peso actual: {p_act:.1f}kg, Meta intermedia: {p_prom:.1f}kg. Da un consejo nutricional."
        recomendacion = obtener_recomendacion_ia(prompt_ia)

    tmb_val, _ = calcular_tmb_y_get(
        perfil.get('Peso', 108.5) if perfil else 108.5,
        perfil.get('Altura', 172.0) if perfil else 172.0,
        perfil.get('Edad', 64) if perfil else 64,
        perfil.get('Sexo', 'M') if perfil else 'M',
        perfil.get('Ocupacion', 'sedentario') if perfil else 'sedentario'
    )

    pdf_bytes = generar_pdf_resumen_bytes(mes_str, df_mes, df_p_mes, perfil, tmb_val, recomendacion, user_id)
    
    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=pdf_bytes,
        filename=f"Reporte_Nutricional_{mes_str}.pdf"
    )

# =====================================================================
# 4. GENERAR MENSAJES RECORDATORIOS AUTOMATICOS
# =====================================================================

async def ejecutar_recordatorio_comidas(context, momento: str):
    """
    Función consolidada para verificar y enviar alertas de comidas pendientes.
    - momento == 'manana': Revisa ayer (1 día atrás) y anteayer (2 días atrás).
    - momento == 'tarde': Revisa ayer entero y hoy (Desayuno y Almuerzo).
    """
    try:
        # 1. Leer usuarios desde la pestaña central 'Usuarios'
        sheet_usuarios = sheet_spreadsheet.worksheet("Usuarios")
        registros_usuarios = sheet_usuarios.get_all_records()
        
        usuarios_validos = []
        for u in registros_usuarios:
            estado = str(u.get("Estado", "")).strip().lower()
            notif = str(u.get("Notificaciones", "")).strip().lower()
            user_id = u.get("User ID")
            
            # Valida estado activo y notificaciones habilitadas (acepta 'si' o 'sí')
            if estado == "activo" and notif in ["si", "sí"] and user_id:
                usuarios_validos.append(user_id)

    except Exception as e:
        logger.error(f"Error al acceder a la pestaña 'Usuarios': {e}")
        return

    # Cálculo de fechas utilizando la hora local de Argentina
    hoy = obtener_ahora_arg()
    ayer = hoy - timedelta(days=1)
    anteayer = hoy - timedelta(days=2)

    str_hoy = hoy.strftime("%Y-%m-%d")
    str_ayer = ayer.strftime("%Y-%m-%d")
    str_anteayer = anteayer.strftime("%Y-%m-%d")

    todas_comidas = ["Desayuno", "Almuerzo", "Merienda", "Cena"]

    # 2. Procesar cada usuario activo
    for user_id in usuarios_validos:
        try:
            # Nombre de la pestaña individual del usuario
            nombre_hoja_usuario = f"User_{user_id}"
            sheet_usuario = sheet_spreadsheet.worksheet(nombre_hoja_usuario)
            registros_comidas = sheet_usuario.get_all_records()

            comidas_anteayer = set()
            comidas_ayer = set()
            comidas_hoy = set()

            # Clasificar los registros del usuario leyendo la columna 'Momento/Actividad'
            for reg in registros_comidas:
                fecha_reg = str(reg.get("Fecha", "")).strip()
                momento_reg = str(reg.get("Momento/Actividad", "")).strip().capitalize()

                if fecha_reg == str_anteayer:
                    comidas_anteayer.add(momento_reg)
                elif fecha_reg == str_ayer:
                    comidas_ayer.add(momento_reg)
                elif fecha_reg == str_hoy:
                    comidas_hoy.add(momento_reg)

            faltantes = []

            # -----------------------------------------------------------------
            # REVISIÓN SEGÚN EL MOMENTO DE LA EJECUCIÓN
            # -----------------------------------------------------------------
            if momento == 'manana':
                # Revisa Anteayer (2 días atrás)
                for c in todas_comidas:
                    if c not in comidas_anteayer:
                        faltantes.append(f"{c} de anteayer ({str_anteayer})")

                # Revisa Ayer (1 día atrás)
                for c in todas_comidas:
                    if c not in comidas_ayer:
                        faltantes.append(f"{c} de ayer ({str_ayer})")

            elif momento == 'tarde':
                # Revisa Ayer entero
                for c in todas_comidas:
                    if c not in comidas_ayer:
                        faltantes.append(f"{c} de ayer ({str_ayer})")

                # Revisa Hoy (hasta el almuerzo)
                if "Desayuno" not in comidas_hoy:
                    faltantes.append("Desayuno de hoy")
                if "Almuerzo" not in comidas_hoy:
                    faltantes.append("Almuerzo de hoy")

            # 3. Enviar mensaje por Telegram si existen faltantes
            if faltantes:
                lista_formateada = "\n• " + "\n• ".join(faltantes)
                mensaje = (
                    f"📌 **Recordatorio de comidas pendientes:**\n"
                    f"{lista_formateada}\n\n"
                    f"Si ya las consumiste, podés registrarlas en cualquier momento."
                )
                await context.bot.send_message(
                    chat_id=user_id, 
                    text=mensaje, 
                    parse_mode="Markdown"
                )
                logger.info(f"Recordatorio ({momento}) enviado a {user_id}")

        except Exception as e:
            logger.error(f"Error procesando recordatorio para usuario {user_id} en {nombre_hoja_usuario}: {e}")    
# ========================================================================
#                      MAIN EXECUTION
# =================================================================


# --- FUNCIONES WRAPPER PARA LA JOBQUEUE ---
async def job_recordatorio_manana(context):
    """Tarea programada para las 09:00 hs"""
    await ejecutar_recordatorio_comidas(context, momento='manana')

async def job_recordatorio_tarde(context):
    """Tarea programada para las 16:00 hs"""
    await ejecutar_recordatorio_comidas(context, momento='tarde')

def main():
    # Hilo secundario para mantener el servidor web (Flask) activo
    threading.Thread(target=run_flask, daemon=True).start()

    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN no configurado.")
        return

    # Inicialización de la aplicación de Telegram
    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # --- CONFIGURACIÓN DE TAREAS PROGRAMADAS (JOB QUEUE) ---
    job_queue = app_bot.job_queue
    tz = pytz.timezone('America/Argentina/Buenos_Aires')

    # Recordatorio Mañana: 09:00 hs todos los días
    job_queue.run_daily(
        job_recordatorio_manana, 
        time=time(hour=9, minute=0, second=0, tzinfo=tz),
        name="recordatorio_comidas_manana"
    )

    # Recordatorio Tarde: 16:00 hs todos los días
    job_queue.run_daily(
        job_recordatorio_tarde, 
        time=time(hour=16, minute=0, second=0, tzinfo=tz),
        name="recordatorio_comidas_tarde"
    )

    # --- HANDLERS DE COMANDOS ---
    app_bot.add_handler(CommandHandler("start", cmd_start))
    app_bot.add_handler(CommandHandler("comidas", cmd_comidas))
    app_bot.add_handler(CommandHandler("actividad", cmd_actividad))
    app_bot.add_handler(CommandHandler("actividadia", actividad_ia))
    app_bot.add_handler(CommandHandler("perfil", cmd_perfil))
    app_bot.add_handler(CommandHandler("presion", cmd_presion_handler))
    app_bot.add_handler(CommandHandler("diario", cmd_diario))
    app_bot.add_handler(CommandHandler("resumen", cmd_resumen))

    # --- HANDLERS DE MENSAJES Y CALLBACKS ---
    app_bot.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app_bot.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app_bot.add_handler(CallbackQueryHandler(handle_callback_query))

    print("🤖 Bot Nutricional iniciado correctamente en Telegram con tareas programadas (09:00 hs y 16:00 hs)...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
