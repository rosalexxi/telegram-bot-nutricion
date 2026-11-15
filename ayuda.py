import os
import re
import io
import logging
import requests
import asyncio
from gtts import gTTS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot8a import (
    obtener_idioma_usuario, 
    obtener_traducciones_db, 
    MODELO_TEXTO, 
    MODELO_RESPALDO, 
    MODELO_EMERGENCIA, 
    registrar_curioso_preventa_db
)

logger = logging.getLogger(__name__)

# Cargamos ambas API Keys (Groq como principal ultrarrápido y Gemini como respaldo infalible)
API_KEY_GROQ = os.getenv("GROQ_API_KEY")
API_KEY_GEMINI = os.getenv("GEMINI_API_KEY_AYUDA") or os.getenv("GEMINI_API_KEY")


def leer_manual_md():
    """Lee el contenido del manual.md desde la carpeta static."""
    ruta = os.path.join("static", "manual.md")
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error al leer el archivo manual.md: {e}")
        return "El manual no se encuentra disponible en este momento."


def generar_audio_memoria(texto: str, lang: str = 'es'):
    """
    Toma el texto limpio, lo convierte a voz usando gTTS y lo devuelve como un buffer de bytes.
    """
    # Limpiamos asteriscos, guiones, numerales, etc.
    texto_limpio = re.sub(r'[*_`#]+', '', texto)
    # Limpiamos emojis y símbolos raros para que la voz no falle
    texto_limpio = re.sub(r'[^\w\s,.:;?!\-áéíóúÁÉÍÓÚñÑüÜ]', ' ', texto_limpio)
    # Colapsamos los espacios múltiples
    texto_limpio = re.sub(r'\s+', ' ', texto_limpio).strip()
    
    # gTTS utiliza códigos de 2 letras (es, en, pt, etc)
    lang_code = lang[:2].lower()
    if lang_code not in ['es', 'en', 'pt', 'fr', 'it', 'de']:
        lang_code = 'es'
        
    tts = gTTS(text=texto_limpio, lang=lang_code, slow=False)
    buffer = io.BytesIO()
    tts.write_to_fp(buffer)
    buffer.seek(0)
    
    return buffer


def transcribir_audio_groq(audio_bytes: bytes) -> str:
    """
    Transcribe el audio de Telegram usando Whisper en Groq (aislado del motor de comidas).
    """
    if not API_KEY_GROQ:
        raise Exception("GROQ_API_KEY no configurada para transcribir audio de ayuda.")

    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {API_KEY_GROQ}"}
    files = {
        "file": ("consulta.ogg", bytes(audio_bytes), "audio/ogg")
    }
    data = {
        "model": "whisper-large-v3-turbo",
        "language": "es",
        "response_format": "json"
    }
    response = requests.post(url, headers=headers, files=files, data=data, timeout=15)
    if response.status_code == 200:
        return response.json().get("text", "").strip()
    else:
        logger.warning(f"Error transcribiendo audio en Groq Ayuda: {response.text}")
        raise Exception("Fallo en transcripción de audio de ayuda")

def solicitar_ai_rest(consulta, lang='es'):
    """
    Intenta responder primero con Groq (modelos actualizados).
    Si Groq no está configurado o falla, pasa automáticamente a Gemini REST.
    """
    manual_texto = leer_manual_md()
    
    system_instruction = (
        "Sos el asistente de soporte técnico oficial de IA NutriBot. "
        f"REGLA DE IDIOMA ESTRICTA: El usuario habla el idioma con código ISO '{lang}'. "
        f"DEBES responder y traducir toda tu explicación ÚNICAMENTE al idioma '{lang}'. No uses palabras en español si el idioma no es español.\n"
        "Tu única tarea es responder la consulta del usuario basándote EXCLUSIVAMENTE en el siguiente manual. "
        "Si la respuesta no está en el manual, indicá amablemente que contacte al soporte técnico o al administrador. "
        "Sé claro, conciso, amable y utilizá un tono coloquial. "
        "Usá formato simple (negritas con un solo asterisco *texto* y viñetas con •), sin inventar comandos ni funciones.\n"
        "REGLA DE CIERRE: NO agregues frases de despedida genéricas (como 'Estaré aquí para ayudarte' o 'Cualquier otra duda me avisas'). Termina tu respuesta directamente con la información técnica.\n\n"
        f"MANUAL OFICIAL:\n{manual_texto}"
    )

    # 1. INTENTO CON GROQ (Si existe GROQ_API_KEY)
    if API_KEY_GROQ:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY_GROQ}"
        }
        # Modelos vigentes en Groq

        modelos_groq = [
            "openai/gpt-oss-120b",
            "qwen/qwen3.8-27b",
            "openai/gpt-oss-20b"
        ]
        
        for modelo in modelos_groq:
            payload = {
                "model": modelo,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": consulta}
                ],
                "temperature": 0.2
            }
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    return data['choices'][0]['message']['content']
                else:
                    logger.warning(f"Fallo en API Groq Ayuda con modelo {modelo}: {response.text}")
            except Exception as e:
                logger.warning(f"Error de conexión con Groq ({modelo}): {e}")

    # 2. RESPALDO AUTOMÁTICO CON GEMINI REST
    if API_KEY_GEMINI:
        return solicitar_ai_rest_Gemini(consulta, system_instruction)

    raise Exception("No se pudo responder ni con Groq ni con Gemini (verificar API Keys).")

async def procesar_audio_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Recibe el audio (o texto) desviado desde bot8.py cuando el usuario está en modo /ayuda,
    lo transcribe, responde la duda con el manual y genera un audio de respuesta.
    """
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    msg_espera_txt = traducciones.get("09_ayuda_escuchando", "🎧 Escuchando tu consulta y buscando en el manual...")
    msg_espera = await update.message.reply_text(msg_espera_txt, parse_mode="Markdown")

    try:
        # Extraemos el texto a consultar (sea dictado por voz o tipeado si la bandera estaba activa)
        if update.message.voice:
            file = await context.bot.get_file(update.message.voice.file_id)
            audio_bytes = await file.download_as_bytearray()
            consulta_texto = await asyncio.to_thread(transcribir_audio_groq, audio_bytes)
        else:
            consulta_texto = update.message.text.strip()

        if not consulta_texto:
            msg_error_audio = traducciones.get("09_ayuda_error_audio", "⚠️ No pude procesar la consulta. Intentá de nuevo.")
            await msg_espera.edit_text(msg_error_audio)
            return

        # 2. Consultamos el manual con el texto (PASANDO EL IDIOMA)
        respuesta_ia = await asyncio.to_thread(solicitar_ai_rest, consulta_texto, lang)
        
        etiqueta_consulta = traducciones.get("09_ayuda_etiqueta_consulta", "Tu consulta")
        txt_cierre = traducciones.get("09_ayuda_cierre_h", "\n\n💡 *Para realizar otra consulta, volvé a enviar el comando /h o /soporte.*")
        
        respuesta_limpia = f"🗣️ *{etiqueta_consulta}:* _{consulta_texto}_\n\n" + respuesta_ia.replace("**", "*") + txt_cierre

        # Enviamos el texto editado
        try:
            await msg_espera.edit_text(respuesta_limpia, parse_mode="Markdown")
        except Exception:
            await msg_espera.edit_text(respuesta_limpia.replace("*", "").replace("_", ""))

        # 3. Generamos y enviamos el audio con la respuesta limpia de la IA
        try:
            # Procesamos el audio de la IA en un hilo secundario para no frenar el bot
            audio_buffer = await asyncio.to_thread(generar_audio_memoria, respuesta_ia, lang)
            await context.bot.send_voice(chat_id=user_id, voice=audio_buffer)
        except Exception as e_audio:
            logger.error(f"Error generando o enviando el audio de la IA: {e_audio}")

    except Exception as e:
        logger.error(f"Error procesando consulta en /ayuda: {e}")
        msg_error_procesar = traducciones.get("09_ayuda_error_procesar_audio", "❌ Ocurrió un error al procesar tu consulta de ayuda.")
        await msg_espera.edit_text(msg_error_procesar)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la guía estática y el botón de descarga del manual en PDF, unificando /start y /ayuda."""
    user = update.effective_user
    user_id = user.id
    
    # Capturamos al curioso apenas pisa el bot
    nombre_tg = user.first_name or ""
    username_tg = f"@{user.username}" if user.username else ""
    await asyncio.to_thread(registrar_curioso_preventa_db, user_id, nombre_tg, username_tg, "cmd_start")
    
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    # Usamos directamente la variable de ayuda que ya está unificada
    texto_ayuda = traducciones.get('09_ayuda_mensaje_guia', 
        "👋 *¡Guía rápida de comandos e ingresos disponibles!*\n\n"
        "📌 *Comandos Principales:*\n"
        "• `/actividad`: Promedio del mes. Informe en PDF.\n"
        "• `/alta`: Apertura de cuenta ingresando los datos.\n"
        "• `/ayuda`: Resumen de comandos y manual en PDF.\n"
        "• `/barra`: Ingresa por código de barras un comestible.\n"
        "• `/borracomida`: Borra una comida de la Planilla.\n"
        "• `/comidas`: Planilla de comidas pre-cargadas y PDF.\n"
        "• `/dia`: Ingestas seleccionando por teclado y PDF.\n"
        "• `/eliminar`: Borra ingestas y actividades.\n"
        "• `/mes`: Reporte mensual de calorías y PDF.\n"
        "• `/pago`: Elegir el plan o promoción de pago vigente.\n"
        "• `/perfil`: Actualización de datos biométricos.\n"
        "• `/presi`: Registro y consulta de presión arterial.\n"
        "• `/receta`: Calculadora Web para registrar comidas.\n"
        "• `/semana`: Estadística semanal (calorías, fibras, etc.).\n\n"
        "• `/h`: Consultar el manual a la IA.\n"
        "• `/x`: Cancelar último comando.\n\n"
        "📌 *Métodos de Registro y consultas directas:*\n"
        "• *Ingestas con IA:* 📝 Texto, 🎤 Audio, 📸 Foto.\n"
        "• *Ingestas con IA:* 📸 Foto de un código de barras.\n"
        "• *Ingestas sin IA:* 📝 Planilla precargada .\n"
        "• *Presión arterial:* 📸 Foto del tensiómetro digital.\n"
        "• *Actividad física:* 📝 Texto o 🎤 Audio.\n"
        "🤖 *Asistente Virtual Inteligente:*\n"
        "Si tenés una duda técnica sobre cómo usar el bot, preguntame directamente escribiendo el comando `/h` seguido de tu consulta.\n"
        "👉 *Ejemplo:* `/h ¿cómo borro un desayuno?`\n\n"
        "📄 También podés descargar el manual completo en PDF acá abajo:"
    ).replace('\\n', '\n')
    
    import re
    texto_final = re.sub(r'\n{2,}', '\n\n', texto_ayuda)
    
    btn_manual_txt = traducciones.get('09_btn_descargar_manual', "📄 Descargar Manual Completo en PDF")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_manual_txt, callback_data=f"descargar_manual_user_{lang}")]
    ])
    
    await update.message.reply_text(texto_final, reply_markup=keyboard, parse_mode="Markdown")

async def callback_descargar_manual_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    # Convertimos a minúsculas para igualar el formato de la carpeta static (ej: static/es.pdf)
    lang_code = query.data.replace("descargar_manual_user_", "").strip().lower()
    pdf_filename = f"{lang_code}.pdf"
    
    # Buscamos primero en static/ y luego en la raíz como respaldo
    rutas_posibles = [
        os.path.join("static", pdf_filename),
        pdf_filename,
        os.path.join("static", "es.pdf"),
        "es.pdf",
        os.path.join("static", "manual.pdf")
    ]
    
    ruta_encontrada = next((r for r in rutas_posibles if os.path.exists(r)), None)
        
    try:
        if ruta_encontrada:
            txt_caption = traducciones.get("09_manual_usuario_caption", "📄 **Manual de Usuario**")
            with open(ruta_encontrada, 'rb') as f_pdf:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=f_pdf,
                    filename=f"Manual_IA_NutriBot_{lang_code.upper()}.pdf",
                    caption=txt_caption,
                    parse_mode="Markdown"
                )
        else:
            txt_err = traducciones.get("09_manual_err_no_encontrado", "⚠️ El archivo `{pdf_filename}` no se encuentra en el servidor.").format(pdf_filename=pdf_filename)
            await query.message.reply_text(txt_err, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error enviando el manual de usuario en PDF: {e}")
        txt_envio = traducciones.get("09_manual_err_envio", "❌ Ocurrió un error al intentar enviar el manual.")
        await query.message.reply_text(txt_envio)
        
def solicitar_ai_rest_Gemini(consulta, system_instruction):
    """
    Respaldo aislado por REST API a Google Gemini usando exclusivamente la línea 3.x definida en bot8a.py.
    """
    modelos_gemini = [MODELO_TEXTO, MODELO_RESPALDO, MODELO_EMERGENCIA]
    
    payload = {
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"parts": [{"text": consulta}]}],
        "generationConfig": {"temperature": 0.2}
    }

    for mod in modelos_gemini:
        if not mod:
            continue
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={API_KEY_GEMINI}"
        try:
            response = requests.post(url, json=payload, timeout=15)
            if response.status_code == 200:
                data = response.json()
                return data['candidates'][0]['content']['parts'][0]['text']
            else:
                logger.warning(f"Error en API Gemini Ayuda ({mod}): {response.text}")
        except Exception as e:
            logger.warning(f"Excepción en API Gemini Ayuda ({mod}): {e}")

    raise Exception("Fallo en todos los modelos de respaldo de Google Gemini")
    
async def cmd_soporte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Activa de inmediato la bandera de escucha/texto exclusivo para hablar con la IA de soporte."""
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    # Activamos la bandera exclusiva
    context.user_data['esperando_consulta_ayuda'] = True

    msg_bienvenida = traducciones.get('09_soporte_bienvenida', 
        "🤖 **Asistente de Soporte Técnico IA NutriBot**\n\n"
        "🎙️ **Grabá un mensaje de audio** contándome tu duda o **escribila acá abajo**.\n"
        "Te responderé al instante con texto y voz basándome en el manual oficial.\n\n"
        "*(Si querés salir de este modo sin consultar nada, escribí `/x`)*"
    ).replace('\\n', '\n')

    await update.message.reply_text(msg_bienvenida, parse_mode="Markdown")
