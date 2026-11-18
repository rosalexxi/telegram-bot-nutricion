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
    _asegurar_tabla_y_conectar,
    obtener_datos_usuario,
    obtener_ahora_arg,
    _CONTADOR_DIARIO_IA,
    MODELO_TEXTO, 
    MODELO_RESPALDO, 
    MODELO_EMERGENCIA, 
    registrar_curioso_preventa_db,
    notificar_fallo_modelo_admin
)
logger = logging.getLogger(__name__)

# Cargamos ambas API Keys (Groq como principal ultrarrápido y Gemini como respaldo infalible)
API_KEY_GROQ = os.getenv("GROQ_API_KEY")
API_KEY_GEMINI = os.getenv("GEMINI_API_KEY_AYUDA") or os.getenv("GEMINI_API_KEY")


def leer_manual_md(es_profesional: bool = False):
    """Si es profesional lee solo profesional.md; si es usuario lee solo manual.md."""
    if es_profesional:
        rutas = [os.path.join("static", "profesional.md"), "profesional.md"]
    else:
        rutas = [os.path.join("static", "manual.md"), "manual.md"]

    ruta_ok = next((r for r in rutas if os.path.exists(r)), None)
    if ruta_ok:
        try:
            with open(ruta_ok, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error al leer {ruta_ok}: {e}")

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

# ==========================================
# NUEVA FUNCIÓN: RECOPILADOR DE CONTEXTO DE USUARIO
# ==========================================
def obtener_contexto_para_ia(user_id):
    """
    Recopila de forma invisible el estado técnico, biométrico, plan activo y límites diarios
    reales desde Supabase para inyectarlos al prompt de la IA de soporte.
    """
    uid = str(user_id).strip()
    ahora = obtener_ahora_arg()
    mes_actual = ahora.strftime("%Y-%m")
    hoy_str = ahora.strftime("%Y-%m-%d")
    
    contexto = {
        "user_id": uid,
        "nombre": "Usuario",
        "estado": "Activo",
        "plan_activo": "basico",
        "limite_textos": 20,
        "limite_fotos": 10,
        "consultas_texto_hoy": 0,
        "fotos_hoy": 0,
        "calorias_hoy": 0.0,
        "peso_mes_actual_cargado": False,
        "dias_registrados_mes": 0,
        "fecha_alta": "",
        "vencimiento_suscripcion": "Gratuito / Sin fecha"
    }
    
    try:
        # 1. Datos básicos y plan activo desde la tabla Usuarios
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        cur.execute('SELECT "Nombre", "Estado", "Ultimo Mes Peso", "Fecha Alta", "vencimiento_suscripcion", "plan_activo" FROM "Usuarios" WHERE "User ID" = %s', (uid,))
        fila = cur.fetchone()
        if fila:
            contexto["nombre"] = str(fila[0] or "Usuario").strip()
            estado_val = str(fila[1] if fila[1] is not None else "0").strip().lower()
            if estado_val == '3':
                contexto["estado"] = "Suspendido / Fin de prueba (Estado 3)"
            elif estado_val in ['baja', 'suspendido']:
                contexto["estado"] = "Suspendido / Inactivo"
            else:
                contexto["estado"] = "Activo"
                
            ultimo_mes_peso = str(fila[2] or "").strip()
            if mes_actual in ultimo_mes_peso or ahora.strftime("%m/%Y") in ultimo_mes_peso:
                contexto["peso_mes_actual_cargado"] = True
                
            contexto["fecha_alta"] = str(fila[3] or "").strip()
            contexto["vencimiento_suscripcion"] = str(fila[4] or "Gratuito").strip()
            
            plan_db = str(fila[5]).strip().lower() if fila[5] else "basico"
            contexto["plan_activo"] = plan_db
            if "premium" in plan_db:
                contexto["limite_fotos"], contexto["limite_textos"] = 40, 80
            elif "intermedio" in plan_db:
                contexto["limite_fotos"], contexto["limite_textos"] = 20, 40
            elif "free" in plan_db:
                contexto["limite_fotos"], contexto["limite_textos"] = 0, 0
            else:
                contexto["limite_fotos"], contexto["limite_textos"] = 10, 20
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error recopilando contexto de usuario {uid} en ayuda.py: {e}")

    # 2. Límites diarios de IA reales desde la tabla Uso_IA_Diario en Supabase
    try:
        conn_ia, cur_ia = _asegurar_tabla_y_conectar("Uso_IA_Diario", tipo_tabla="uso_ia")
        cur_ia.execute('SELECT "fotos", "textos" FROM "Uso_IA_Diario" WHERE "user_id" = %s AND "fecha" = %s', (uid, hoy_str))
        consumo = cur_ia.fetchone()
        if consumo:
            contexto["fotos_hoy"] = int(consumo[0] or 0)
            contexto["consultas_texto_hoy"] = int(consumo[1] or 0)
        cur_ia.close()
        conn_ia.close()
    except Exception as e_ia:
        logger.error(f"Error leyendo Uso_IA_Diario para {uid} en ayuda.py: {e_ia}")

    # 3. Calorías acumuladas hoy y días registrados en el mes actual
    try:
        df_u = obtener_datos_usuario(uid)
        if not df_u.empty and 'Fecha' in df_u.columns:
            df_hoy = df_u[(df_u['Fecha'].astype(str).str.strip() == hoy_str) & (df_u['Calorias'] > 0)]
            contexto["calorias_hoy"] = float(df_hoy['Calorias'].sum())
            
            df_mes = df_u[df_u['Fecha'].astype(str).str.startswith(mes_actual)]
            if not df_mes.empty and 'Fecha' in df_mes.columns:
                contexto["dias_registrados_mes"] = int(df_mes['Fecha'].nunique())
    except Exception:
        pass

    # Formatear el bloque que lee la IA
    texto_resumen = (
        f"- Nombre/Apodo: {contexto['nombre']}\n"
        f"- Estado de cuenta: {contexto['estado']}\n"
        f"- Plan activo: {contexto['plan_activo'].upper()}\n"
        f"- Consultas de texto hoy: {contexto['consultas_texto_hoy']}/{contexto['limite_textos']} (Límite diario)\n"
        f"- Fotos enviadas hoy: {contexto['fotos_hoy']}/{contexto['limite_fotos']} (Límite diario)\n"
        f"- Calorías registradas hoy: {contexto['calorias_hoy']:.0f} kcal (Tope antispam 6000 kcal)\n"
        f"- Peso del mes actual cargado: {'Sí' if contexto['peso_mes_actual_cargado'] else 'No (Pendiente)'}\n"
        f"- Días con registros en el mes actual: {contexto['dias_registrados_mes']} días (Mínimo 10 para manual, 20 para automático)\n"
        f"- Fecha de alta: {contexto['fecha_alta']}\n"
        f"- Vencimiento de suscripción: {contexto['vencimiento_suscripcion']}"
    )
    return texto_resumen
    
# ==========================================
# ACTUALIZACIÓN DE SOLICITUD A IA CON CONTEXTO
# ==========================================

def solicitar_ai_rest(consulta, lang='es', contexto_usuario="", user_id=None):
    """
    Intenta responder primero con Groq incorporando el contexto técnico del usuario.
    Si el usuario figura en la tabla Profesionales, habilita también profesional.md.
    Si falla Groq, pasa automáticamente a Gemini REST.
    """
    es_prof = False
    especialidad_prof = ""

    if user_id:
        uid_str = str(user_id).split('.')[0].strip()
        if not contexto_usuario:
            contexto_usuario = obtener_contexto_para_ia(uid_str)

        conn_p = None
        cur_p = None
        try:
            conn_p, cur_p = _asegurar_tabla_y_conectar("Profesionales", tipo_tabla="profesionales")
            cur_p.execute('SELECT "User ID", "Especialidad" FROM "Profesionales"')
            for fila in cur_p.fetchall():
                if str(fila[0] or "").split('.')[0].strip() == uid_str:
                    es_prof = True
                    especialidad_prof = str(fila[1] or "General").strip()
                    break
        except Exception as e_p:
            logger.error(f"Error verificando si {uid_str} es profesional en ayuda.py: {e_p}")
        finally:
            if cur_p:
                try: cur_p.close()
                except Exception: pass
            if conn_p:
                try: conn_p.close()
                except Exception: pass

    manual_texto = leer_manual_md(es_profesional=es_prof)

    bloque_rol = ""

    if es_prof:
        bloque_tono_y_rol = (
            f"**ROL DEL USUARIO:** Estás hablando con un PROFESIONAL DE LA SALUD registrado (Especialidad: {especialidad_prof}).\n"
            "**TONO:** Adoptá un tono profesional, técnico, preciso, ejecutivo y respetuoso (tratándolo de 'usted' o con un 'vos' profesional y cordial, sin exceso de informalidad). "
            "Tenés habilitado el Manual Exclusivo para Profesionales además del Manual de Usuario para responderle dudas sobre "
            "gestión de pacientes, alertas, valores clínicos, informes, notas, anuncios y epicrisis.\n\n"
        )
    else:
        bloque_tono_y_rol = (
            "**ROL DEL USUARIO:** Estás hablando con un paciente/usuario final.\n"
            "**TONO:** Adoptá un tono empático, cálido, resolutivo y usá el 'vos' argentino (cercano y amigable).\n\n"
        )

    system_instruction = (
        "Sos el asistente de soporte técnico oficial de IA NutriBot. "
        f"REGLA DE IDIOMA ESTRICTA: El usuario habla el idioma con código ISO '{lang}'. "
        f"DEBES responder y traducir toda tu explicación ÚNICAMENTE al idioma '{lang}'.\n\n"
        f"{bloque_tono_y_rol}"
        "**DATOS Y ESTADO TÉCNICO ACTUAL DEL USUARIO:**\n"
        f"{contexto_usuario}\n\n"
        "**REGLA DE PERSONALIDAD Y PROACTIVIDAD:** Saludá siempre al usuario por su nombre. "
        "Si detectás que su problema o bloqueo está directamente relacionado con sus datos actuales (ej: límite diario de fotos alcanzado, "
        "falta de carga de peso mensual, cuenta suspendida en Estado 3, o exceso calórico diario), explicaselo proactivamente diciendo "
        "'Estuve revisando tu ficha y noté que...' (o adaptado al tono profesional si corresponde). No menciones estos datos internos si no tienen relación directa con su consulta.\n\n"
        "Tu única tarea es responder la consulta basándote en el manual y este contexto técnico. "
        "Sé claro, conciso y terminá tu respuesta directamente con la información técnica sin despedidas genéricas.\n\n"
        f"MANUAL OFICIAL:\n{manual_texto}"
    )

    if API_KEY_GROQ:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY_GROQ}"
        }
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
                    notificar_fallo_modelo_admin("Groq", modelo, "Ayuda (/h)", f"HTTP {response.status_code}: {response.text}")
            except Exception as e:
                logger.warning(f"Error de conexión con Groq ({modelo}): {e}")
                notificar_fallo_modelo_admin("Groq", modelo, "Ayuda (/h)", str(e))
            
    if API_KEY_GEMINI:
        return solicitar_ai_rest_Gemini(consulta, system_instruction)

    raise Exception("No se pudo responder ni con Groq ni con Gemini (verificar API Keys).")

# ==========================================
# ACTUALIZACIÓN DE PROCESAR AUDIO/MENSAJE AYUDA
# ==========================================

async def procesar_audio_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Recibe el audio (o texto) de ayuda, recopila el contexto del usuario y responde con voz y texto.
    """
    user_id = update.effective_user.id
    
    # --- AGREGAR ESTE CONTROL ---
    from bot8a import verificar_limite_diario_ia
    permitido, msg_limite = verificar_limite_diario_ia(user_id, tipo="texto")
    if not permitido:
        await update.message.reply_text(msg_limite, parse_mode="Markdown")
        return
    # ----------------------------

    lang = obtener_idioma_usuario(user_id) or 'es'

    traducciones = obtener_traducciones_db(lang) or {}

    msg_espera_txt = traducciones.get("09_ayuda_escuchando", "🎧 Escuchando tu consulta y revisando tu ficha...")
    msg_espera = await update.message.reply_text(msg_espera_txt, parse_mode="Markdown")

    try:
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

        # 1. Recopilamos todo el contexto técnico e histórico del usuario en segundo plano
        contexto_usuario = await asyncio.to_thread(obtener_contexto_para_ia, user_id)

        # 2. Consultamos la IA pasándole tanto la consulta como el contexto del usuario
        
        respuesta_ia = await asyncio.to_thread(solicitar_ai_rest, consulta_texto, lang, contexto_usuario, user_id)
        
        etiqueta_consulta = traducciones.get("09_ayuda_etiqueta_consulta", "Tu consulta")
        txt_cierre = traducciones.get("09_ayuda_cierre_h", "\n\n💡 *Para realizar otra consulta, volvé a enviar el comando /h o /soporte.*")
        
        respuesta_limpia = f"🗣️ *{etiqueta_consulta}:* _{consulta_texto}_\n\n" + respuesta_ia.replace("**", "*") + txt_cierre

        try:
            await msg_espera.edit_text(respuesta_limpia, parse_mode="Markdown")
        except Exception:
            await msg_espera.edit_text(respuesta_limpia.replace("*", "").replace("_", ""))

        try:
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
        "• `/planes`: Elegir el plan o promoción de pago vigente.\n"
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
