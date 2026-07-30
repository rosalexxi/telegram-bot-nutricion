import os
import re
import io
import json
import asyncio
from datetime import datetime, date
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import openai
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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_SHEETS_KEY_PATH = os.getenv("GOOGLE_SHEETS_KEY_PATH", "credentials.json")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "Registro_Nutricional")

client_ai = openai.OpenAI(api_key=OPENAI_API_KEY)

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
    <title>Calculadora Nutricional & Estado del Bot</title>
    <style>
        :root {
            --primary: #2563eb;
            --bg: #f8fafc;
            --card: #ffffff;
            --text: #0f172a;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
        }
        .container {
            max-width: 600px;
            width: 100%;
        }
        .card {
            background: var(--card);
            padding: 24px;
            border-radius: 16px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background-color: #dcfce7;
            color: #166534;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 600;
        }
        .status-dot {
            width: 8px;
            height: 8px;
            background-color: #22c55e;
            border-radius: 50%;
        }
        h1 { font-size: 1.5rem; margin-top: 12px; margin-bottom: 8px; }
        p { color: #64748b; font-size: 0.95rem; line-height: 1.5; }
        .input-group {
            display: flex;
            gap: 8px;
            margin-top: 16px;
        }
        input[type="text"] {
            flex: 1;
            padding: 12px 16px;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            font-size: 1rem;
            outline: none;
        }
        input[type="text"]:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.2);
        }
        button {
            background-color: var(--primary);
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }
        button:hover { background-color: #1d4ed8; }
        button:disabled { background-color: #94a3b8; cursor: not-allowed; }
        .result-box {
            margin-top: 20px;
            padding-top: 16px;
            border-top: 1px solid #e2e8f0;
            display: none;
        }
        .macro-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
            gap: 10px;
            margin-top: 12px;
        }
        .macro-card {
            background: #f1f5f9;
            padding: 12px;
            border-radius: 8px;
            text-align: center;
        }
        .macro-val { font-size: 1.2rem; font-weight: bold; color: var(--primary); }
        .macro-lbl { font-size: 0.75rem; color: #64748b; text-transform: uppercase; }
        .item-list { list-style: none; padding: 0; margin-top: 12px; }
        .item-list li {
            padding: 8px 0;
            border-bottom: 1px dashed #e2e8f0;
            display: flex;
            justify-content: space-between;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="status-badge">
                <div class="status-dot"></div>
                Bot de Telegram En Línea
            </div>
            <h1>🔍 Consultor Nutricional Rápido</h1>
            <p>Ingresá cualquier combinación de alimentos para consultar sus datos nutricionales estimativos de inmediato.</p>
            
            <div class="input-group">
                <input type="text" id="foodInput" placeholder="Ej: Big Mac con papas medianas y cola diet">
                <button id="searchBtn" onclick="consultarComida()">Consultar</button>
            </div>

            <div id="resultBox" class="result-box">
                <h3>📊 Desglose Estimado</h3>
                <ul id="itemList" class="item-list"></ul>
                
                <div class="macro-grid">
                    <div class="macro-card">
                        <div id="totalKcal" class="macro-val">0</div>
                        <div class="macro-lbl">Calorías</div>
                    </div>
                    <div class="macro-card">
                        <div id="totalProt" class="macro-val">0g</div>
                        <div class="macro-lbl">Proteínas</div>
                    </div>
                    <div class="macro-card">
                        <div id="totalGras" class="macro-val">0g</div>
                        <div class="macro-lbl">Grasas</div>
                    </div>
                    <div class="macro-card">
                        <div id="totalCarb" class="macro-val">0g</div>
                        <div class="macro-lbl">Carbohidratos</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        async function consultarComida() {
            const input = document.getElementById('foodInput').value.trim();
            const btn = document.getElementById('searchBtn');
            const resultBox = document.getElementById('resultBox');
            
            if (!input) return;

            btn.disabled = true;
            btn.innerText = "Calculando...";

            try {
                const response = await fetch('/api/consultar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: input })
                });

                const data = await response.json();
                
                if (data.items) {
                    const itemList = document.getElementById('itemList');
                    itemList.innerHTML = '';
                    
                    let totC = 0, totP = 0, totG = 0, totH = 0;
                    
                    data.items.forEach(item => {
                        totC += item.calorias || 0;
                        totP += item.proteinas || 0;
                        totG += item.grasas || 0;
                        totH += item.carbohidratos || 0;
                        
                        const li = document.createElement('li');
                        li.innerHTML = `<span><b>${item.alimento}</b></span> <span>${item.calorias} kcal</span>`;
                        itemList.appendChild(li);
                    });

                    document.getElementById('totalKcal').innerText = totC.toFixed(0);
                    document.getElementById('totalProt').innerText = totP.toFixed(1) + 'g';
                    document.getElementById('totalGras').innerText = totG.toFixed(1) + 'g';
                    document.getElementById('totalCarb').innerText = totH.toFixed(1) + 'g';

                    resultBox.style.display = 'block';
                }
            } catch (err) {
                alert('Error al consultar los datos. Intentá nuevamente.');
            } finally {
                btn.disabled = false;
                btn.innerText = "Consultar";
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/consultar', methods=['POST'])
def api_consultar():
    data = request.get_json()
    query = data.get('query', '')
    if not query:
        return jsonify({'error': 'Consulta vacía'}), 400
    
    try:
        res = analizar_con_gpt(query)
        return jsonify(res)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==========================================
# CÓDIGO DEL BOT DE TELEGRAM
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
            ws = spreadsheet.add_worksheet(title=title, rows="100", cols="10")
            ws.append_row(["Fecha", "Comida", "Calorias", "Proteinas_g", "Grasas_g", "Carbohidratos_g", "Fibras_g", "Cintura_cm", "Tipo", "Observaciones"])
            return ws
        elif title.startswith("Perfil_"):
            ws = spreadsheet.add_worksheet(title=title, rows="100", cols="8")
            ws.append_row(["Mes", "Edad", "Sexo", "Peso_kg", "Altura_cm", "Cintura_cm", "Ocupacion", "Fecha_Actualizacion"])
            return ws
        else:
            return spreadsheet.add_worksheet(title=title, rows="100", cols="10")

def guardar_en_sheets(user_id, items, tipo="Comida", observaciones=""):
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    ws = get_or_create_worksheet(sh, f"User_{user_id}")
    fecha_hoy = date.today().strftime("%Y-%m-%d")
    
    rows = []
    for item in items:
        rows.append([
            fecha_hoy,
            item.get("alimento", "Desconocido"),
            float(item.get("calorias", 0)),
            float(item.get("proteinas", 0)),
            float(item.get("grasas", 0)),
            float(item.get("carbohidratos", 0)),
            float(item.get("fibras", 0)),
            "",
            tipo,
            observaciones
        ])
    if rows:
        ws.append_rows(rows)

def obtener_datos_mes(user_id, mes_str):
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

def obtener_perfil(user_id, mes_str):
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

# --- CONVERSACIÓN /PERFIL ---
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
    await update.message.reply_text("💼 Ingresá tu **ocupación / nivel de actividad** (ej: `Ama de casa`, `Oficina`, `Moderada`):", parse_mode="Markdown")
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

# --- PROCESAMIENTO CON GPT ---
def analizar_con_gpt(prompt_text, image_bytes=None):
    system_prompt = (
        "Sos un nutricionista y experto en análisis de alimentos. Tu tarea es analizar el texto o la imagen dada y extraer los ítems.\n"
        "Debes responder ÚNICA Y EXCLUSIVAMENTE con un JSON válido con la siguiente estructura:\n"
        "{\n"
        '  "items": [\n'
        '    {"alimento": "nombre", "calorias": 0.0, "proteinas": 0.0, "grasas": 0.0, "carbohidratos": 0.0, "fibras": 0.0}\n'
        '  ],\n'
        '  "tipo": "Comida" o "Ejercicio"\n'
        "}\n"
        "Si es un ejercicio o gasto calórico, pon las calorías como un número POSITIVO en la estructura, pero indica tipo='Ejercicio'.\n"
        "Si no se especifica fibra o macros, estimálos razonablemente."
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    
    if image_bytes:
        import base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt_text or "Analiza esta comida/ejercicio:"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        })
    else:
        messages.append({"role": "user", "content": prompt_text})
        
    response = client_ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.2,
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    msg = await update.message.reply_text("⏳ Analizando tu registro...")
    
    try:
        data = analizar_con_gpt(user_text)
        items = data.get("items", [])
        tipo = data.get("tipo", "Comida")
        
        if not items:
            await msg.edit_text("No pude identificar alimentos ni ejercicios en tu mensaje.")
            return

        context.user_data['pending_items'] = items
        context.user_data['pending_tipo'] = tipo
        
        txt_res = f"📝 **Reconocimiento de {tipo}:**\n\n"
        tot_c = tot_p = tot_g = tot_h = tot_f = 0
        keyboard = []
        
        for idx, item in enumerate(items):
            c = item.get('calorias', 0)
            p = item.get('proteinas', 0)
            g = item.get('grasas', 0)
            h = item.get('carbohidratos', 0)
            f = item.get('fibras', 0)
            tot_c += c; tot_p += p; tot_g += g; tot_h += h; tot_f += f
            
            txt_res += f"• **{item['alimento']}**:\n  └ {c} kcal | P: {p}g | G: {g}g | H: {h}g | Fib: {f}g\n"
            keyboard.append([InlineKeyboardButton(f"✏️ Editar {item['alimento']}", callback_data=f"edit_{idx}")])
            
        txt_res += f"\n🔥 **Totales:** {tot_c} kcal\n💪 Prot: {tot_p}g | 🥑 Grasas: {tot_g}g | 🍞 Carb: {tot_h}g | 🌾 Fib: {tot_f}g\n"
        txt_res += "\n¿Deseas confirmar este registro?"
        
        keyboard.append([InlineKeyboardButton("✅ Confirmar", callback_data="confirm_save")])
        keyboard.append([InlineKeyboardButton("❌ Descartar", callback_data="cancel_save")])
        
        await msg.edit_text(txt_res, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await msg.edit_text(f"❌ Ocurrió un error al procesar el mensaje: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📸 Analizando la imagen enviada...")
    
    try:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        caption = update.message.caption or ""
        data = analizar_con_gpt(caption, bytes(photo_bytes))
        items = data.get("items", [])
        tipo = data.get("tipo", "Comida")
        
        if not items:
            await msg.edit_text("No pude reconocer ningún alimento o ejercicio en la foto.")
            return

        context.user_data['pending_items'] = items
        context.user_data['pending_tipo'] = tipo
        
        txt_res = f"🍽️ **Reconocimiento de Alimento:**\n\n"
        tot_c = tot_p = tot_g = tot_h = tot_f = 0
        keyboard = []
        
        for idx, item in enumerate(items):
            c = item.get('calorias', 0)
            p = item.get('proteinas', 0)
            g = item.get('grasas', 0)
            h = item.get('carbohidratos', 0)
            f = item.get('fibras', 0)
            tot_c += c; tot_p += p; tot_g += g; tot_h += h; tot_f += f
            
            txt_res += f"• **{item['alimento']}**:\n  └ {c} kcal | P: {p}g | G: {g}g | H: {h}g | Fib: {f}g\n"
            keyboard.append([InlineKeyboardButton(f"✏️ Editar {item['alimento']}", callback_data=f"edit_{idx}")])
            
        txt_res += f"\n🔥 **Totales:** {tot_c} kcal\n💪 Prot: {tot_p}g | 🥑 Grasas: {tot_g}g | 🍞 Carb: {tot_h}g | 🌾 Fib: {tot_f}g\n"
        txt_res += "\n¿Deseas confirmar este registro?"
        
        keyboard.append([InlineKeyboardButton("✅ Confirmar", callback_data="confirm_save")])
        keyboard.append([InlineKeyboardButton("❌ Descartar", callback_data="cancel_save")])
        
        await msg.edit_text(txt_res, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await msg.edit_text(f"❌ Error procesando la foto: {e}")

# --- MANEJO DE EDICIÓN Y CONFIRMACIÓN ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "confirm_save":
        items = context.user_data.get('pending_items', [])
        tipo = context.user_data.get('pending_tipo', 'Comida')
        user_id = query.from_user.id
        
        if items:
            guardar_en_sheets(user_id, items, tipo=tipo)
            await query.edit_message_text(f"✅ ¡Guardado correctamente en tu hoja para la fecha {date.today().strftime('%Y-%m-%d')}!")
        else:
            await query.edit_message_text("No había elementos pendientes para guardar.")
            
    elif data == "cancel_save":
        context.user_data.pop('pending_items', None)
        await query.edit_message_text("❌ Registro descartado.")
        
    elif data.startswith("edit_"):
        idx = int(data.split("_")[1])
        context.user_data['editing_index'] = idx
        items = context.user_data.get('pending_items', [])
        item = items[idx]
        
        await query.message.reply_text(
            f"✏️ Ingresá la corrección para **{item['alimento']}**.\n\n"
            f"Escribí únicamente lo que quieras corregir (ej: `Pescado con salsa`, `150g` o `200 kcal`).",
            parse_mode="Markdown"
        )
        return EDIT_FOOD

async def receive_food_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    idx = context.user_data.get('editing_index')
    items = context.user_data.get('pending_items', [])
    
    if idx is not None and idx < len(items):
        item_previo = items[idx]
        prompt = f"El alimento detectado era '{item_previo['alimento']}' ({item_previo['calorias']} kcal). El usuario corrigió diciendo: '{text}'. Actualiza los datos manteniendo los campos no modificados."
        res = analizar_con_gpt(prompt)
        new_items = res.get("items", [])
        if new_items:
            items[idx] = new_items[0]
            await update.message.reply_text(f"✏️ Actualizado: **{items[idx]['alimento']}** ({items[idx]['calorias']} kcal).", parse_mode="Markdown")
        
    txt_res = f"📝 **Registro Actualizado:**\n\n"
    tot_c = tot_p = tot_g = tot_h = tot_f = 0
    keyboard = []
    
    for i, item in enumerate(items):
        c = item.get('calorias', 0)
        p = item.get('proteinas', 0)
        g = item.get('grasas', 0)
        h = item.get('carbohidratos', 0)
        f = item.get('fibras', 0)
        tot_c += c; tot_p += p; tot_g += g; tot_h += h; tot_f += f
        
        txt_res += f"• **{item['alimento']}**:\n  └ {c} kcal | P: {p}g | G: {g}g | H: {h}g | Fib: {f}g\n"
        keyboard.append([InlineKeyboardButton(f"✏️ Editar {item['alimento']}", callback_data=f"edit_{i}")])
        
    txt_res += f"\n🔥 **Totales:** {tot_c} kcal\n💪 Prot: {tot_p}g | 🥑 Grasas: {tot_g}g | 🍞 Carb: {tot_h}g | 🌾 Fib: {tot_f}g\n"
    txt_res += "\n¿Deseas confirmar este registro?"
    
    keyboard.append([InlineKeyboardButton("✅ Confirmar", callback_data="confirm_save")])
    keyboard.append([InlineKeyboardButton("❌ Descartar", callback_data="cancel_save")])
    
    await update.message.reply_text(txt_res, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

# --- RESUMEN Y GENERACIÓN DE PDF ---
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
    dias_count = df['Fecha'].nunique() if not df.empty and 'Fecha' in df.columns else 1
    
    bal_text = (
        f"<b>Días Registrados:</b> {dias_count}<br/>"
        f"<b>Total Consumido:</b> {tot_cal:.1f} kcal<br/>"
        f"<b>Proteínas:</b> {tot_prot:.1f} g | <b>Grasas:</b> {tot_gras:.1f} g | <b>Carbohidratos:</b> {tot_carb:.1f} g"
    )
    story.append(Paragraph(bal_text, body_style))
    story.append(Spacer(1, 15))
    
    if not df.empty:
        story.append(Paragraph("<b>3. Desglose de Registros</b>", sub_style))
        table_data = [["Fecha", "Tipo", "Descripción", "Kcal", "Prot(g)", "Gras(g)", "Carb(g)"]]
        
        for _, r in df.head(40).iterrows():
            table_data.append([
                str(r.get("Fecha", "")),
                str(r.get("Tipo", "Comida")),
                str(r.get("Comida", ""))[:25],
                f"{r.get('Calorias', 0):.0f}",
                f"{r.get('Proteinas_g', 0):.0f}",
                f"{r.get('Grasas_g', 0):.0f}",
                f"{r.get('Carbohidratos_g', 0):.0f}"
            ])
            
        t = Table(table_data, colWidths=[65, 55, 180, 50, 50, 50, 50])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
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
    
    resumen_text = f"📊 **Reporte Nutricional Mensual ({mes_actual})**\n\n"
    resumen_text += f"📅 Días registrados: {dias}\n"
    resumen_text += f"🔥 Total consumido: {tot_cal:.0f} kcal\n"
    resumen_text += f"💪 Prot: {tot_prot:.0f}g | 🥑 Grasas: {tot_gras:.0f}g | 🍞 Carb: {tot_carb:.0f}g\n\n"
    
    if perfil and metabol:
        resumen_text += "—— **Análisis Metabólico y Estimación Corporal** ——\n"
        resumen_text += f"👤 Sexo: {perfil.get('Sexo')} | Edad: {perfil.get('Edad')}a | Peso: {perfil.get('Peso_kg')}kg | Altura: {perfil.get('Altura_cm')}cm\n"
        resumen_text += f"📐 Medida de Cintura: {perfil.get('Cintura_cm')} cm\n"
        resumen_text += f"🔥 Metabolismo Basal (TMB): {metabol['tmb']} kcal/día\n"
        resumen_text += f"⚡ Gasto Energético Conservador (GET): {metabol['get']} kcal/día\n\n"
        
        dias_calculo = dias if dias > 0 else 1
        gasto_total = metabol['get'] * dias_calculo
        balance = tot_cal - gasto_total
        cambio_peso = balance / 7700
        
        resumen_text += "📊 **Resumen de Balance y Cambio Corporal Estimado:**\n"
        resumen_text += f"• Total Consumido: {tot_cal:.0f} kcal\n"
        resumen_text += f"• Total Gasto Basal + Ocupación ({dias_calculo} días): -{gasto_total:.1f} kcal\n"
        resumen_text += f"🔥 **BALANCE CALÓRICO NETO REAL:** {balance:.1f} kcal\n"
        resumen_text += f"⚖️ **CAMBIO ESTIMADO DE PESO:** {cambio_peso:.2f} kg ({cambio_peso*1000:.1f} g)\n"
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
            caption=f"📄 Aquí tienes tu reporte nutricional completo en PDF para {mes_actual}."
        )

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
    
    edit_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(callback_handler, pattern="^edit_")],
        states={
            EDIT_FOOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_food_edit)]
        },
        fallbacks=[CommandHandler("cancelar", cancel_perfil)]
    )
    
    app_bot.add_handler(perfil_handler)
    app_bot.add_handler(edit_handler)
    
    app_bot.add_handler(CommandHandler("resumen", cmd_resumen))
    app_bot.add_handler(CallbackQueryHandler(callback_pdf, pattern="^generate_pdf$"))
    app_bot.add_handler(CallbackQueryHandler(callback_handler, pattern="^(confirm_save|cancel_save)$"))
    
    app_bot.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 Bot iniciado correctamente...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
