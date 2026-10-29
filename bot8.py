
#===============================================================================================================
#           VERIFICAR ERRORES ANTES DE SUBIR   python3 -m py_compile bot8a.py administrador.py profesionales.py bot8.py
#           REEMPLAZAR DESDE LINEA DE COMANDOS  sed -i "s/or '\$1'/or 'es'/g" bot8.py bot8a.py   sed -i "s/STRING_A_REEMPLAZAR/STRING_REEMPLAZO/g" ARCHIVO1 ARCHIVO2
#===============================================================================================================

from bot8a import *

from administrador import (
    cmd_desarmar_excel,
    cmd_armar_excel,
    cmd_subir,
    cmd_descargar
)

from profesionales import (
    cmd_pacientes,
    cmd_enviar_informe_actual,
    cmd_enviar_nota_paciente,
    cmd_editar_valores_clinicos,
    cmd_generar_manual_pdf,
    callback_editar_valor_clinico_menu,
    callback_gestion_solicitud_medico,
    callback_seleccionar_paciente_clinico,
    callback_enviar_informe_paciente,
    callback_acciones_informe,
    callback_seleccionar_paciente_nota,
    procesar_cambio_valor_clinico,
    procesar_texto_nota_informe,
    procesar_texto_nota_medica
)

@requiere_registro
async def callback_handler_reportes_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    if data.startswith("resumen_mes_") or data in ["resumen_volver_menu", "resumen_mes_menu_otros"]:
        await mostrar_resumen_mes(update, context)
    elif data.startswith("descargar_pdf_resumen_"):
        await generar_y_enviar_pdf_resumen(query, context)
    elif data.startswith("descargar_pdf_diario_"):
        f_str = data.replace("descargar_pdf_diario_", "")
        df = obtener_datos_usuario(user_id)
        pdf = generar_pdf_diario_bytes(f_str, df[df['Fecha'] == f_str] if not df.empty else pd.DataFrame(), user_id)
        prefijo_d = traducciones.get('06_bot_pdf_diario_prefijo', 'D_')
        await context.bot.send_document(chat_id=query.message.chat_id, document=pdf, filename=f"📄 {prefijo_d}{f_str}.pdf")
    elif data.startswith("descargar_pdf_presion_"):
        mes_str = data.replace("descargar_pdf_presion_", "")
        df_p = obtener_datos_presion_db(user_id)
        pdf_p = generar_pdf_presion_bytes(mes_str, df_p[df_p['Fecha_Dia'].str.startswith(mes_str)] if not df_p.empty else pd.DataFrame(), user_id)
        prefijo_p = traducciones.get('06_bot_pdf_presion_prefijo', 'P_')
        await context.bot.send_document(chat_id=query.message.chat_id, document=pdf_p, filename=f"📄 {prefijo_p}{mes_str}.pdf")
    elif data.startswith("enviar_inf_"):
        target_user_id = int(data.replace("enviar_inf_", ""))
        ahora = obtener_ahora_arg()
        mes_target = (ahora.replace(day=1) - timedelta(days=1)).strftime("%Y-%m") if ahora.day <= 7 else ahora.strftime("%Y-%m")
        await procesar_y_enviar_informe_mensual(context, target_user_id, target_user_id, mes_target, False, True)

async def _sub_manejar_fecha_eliminacion(update, context, raw_text, chat_id):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    fecha_parseada = parsear_fecha_flexible(raw_text)
    msg_solic = context.user_data.pop('msg_solicitud_del_fecha_id', None)
    if msg_solic:
        try: await context.bot.delete_message(chat_id=chat_id, message_id=msg_solic)
        except Exception: pass
    try: await update.message.delete()
    except Exception: pass

    if fecha_parseada:
        context.user_data.update({'del_fecha': fecha_parseada, 'awaiting_del_custom_date': False})
        class DummyQuery:
            def __init__(self, msg): self.message = msg
            async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
                await self.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        await mostrar_selector_momento_eliminar(DummyQuery(update.message), context)
    else:
        txt_err_fec = traducciones.get('06_bot_error_fecha_inv', "⚠️ Formato de fecha inválido. Ingrese nuevamente (Ej: `2026-08-15` o `15/08`):")
        msg_err = await update.message.reply_text(txt_err_fec, parse_mode="Markdown")
        context.user_data['msg_solicitud_del_fecha_id'] = msg_err.message_id

async def _sub_manejar_fecha_diario(update, context, raw_text, chat_id):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    fecha_parseada = parsear_fecha_flexible(raw_text)
    msg_solic = context.user_data.pop('msg_solicitud_diario_fecha_id', None)
    if msg_solic:
        try: await context.bot.delete_message(chat_id=chat_id, message_id=msg_solic)
        except Exception: pass
    try: await update.message.delete()
    except Exception: pass

    if fecha_parseada:
        context.user_data['awaiting_diario_custom_date'] = False
        await mostrar_diario_fecha(update.message, update.effective_user.id, fecha_parseada)
    else:
        txt_err_fec = traducciones.get('06_bot_error_fecha_inv', "⚠️ Formato de fecha inválido. Ingrese nuevamente (Ej: `2026-08-15` o `15/08`):")
        msg_err = await update.message.reply_text(txt_err_fec, parse_mode="Markdown")
        context.user_data['msg_solicitud_diario_fecha_id'] = msg_err.message_id

@requiere_registro
async def callback_btn_fechas_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    context.user_data['last_menu_msg_id'] = query.message.message_id

    if data == "set_d_hoy":
        context.user_data['pending_fecha'] = obtener_ahora_arg().strftime("%Y-%m-%d")
        await render_confirmation_screen(query, context)
    elif data == "set_d_ayer":
        context.user_data['pending_fecha'] = (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d")
        await render_confirmation_screen(query, context)
    elif data in ["set_d_otro", "set_d_custom"]:
        context.user_data['awaiting_custom_date'] = True
        txt_fec_ing = traducciones.get('06_bot_solic_fecha_ingesta', "📅 ✏️ Ingresá la fecha deseada para la ingesta (Ej: `2026-08-15` o `15/08`):")
        msg = await query.message.reply_text(txt_fec_ing, parse_mode="Markdown")
        context.user_data['msg_solicitud_fecha_id'] = msg.message_id
    elif data == "diario_hoy":
        await mostrar_diario_fecha(query, user_id, obtener_ahora_arg().strftime("%Y-%m-%d"))
    elif data == "diario_ayer":
        await mostrar_diario_fecha(query, user_id, (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d"))
    elif data == "diario_otro":
        context.user_data['awaiting_diario_custom_date'] = True
        txt_diar_cons = traducciones.get('06_bot_solic_diario_consulta', "🗓️ Ingresá la fecha del diario que querés consultar (Ej: `2026-08-15` o `15/08`):")
        msg = await query.message.reply_text(txt_diar_cons, parse_mode="Markdown")
        context.user_data['msg_solicitud_diario_fecha_id'] = msg.message_id

# ==================================================================================================================================
#                  INICIO                 COMANDOS COMIDAS Y COMANDOS ACTIVIDAD                       INICIO  
# ==================================================================================================================================
#                  INICIO                     FUNCIONES COMIDAS                                       INICIO
# =============================================================================================================================================

def consultar_codigo_barras(barcode: str, txt_desconocido="Producto desconocido") -> dict | bool:
    url = f"https://world.openfoodfacts.org/api/v2/product/{barcode.strip()}.json"
    headers = {"User-Agent": "BotNutricionTelegram/1.0 (contacto@tudominio.com)"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return False
            
        data = response.json()
        if data.get("status") != 1:
            return False
            
        product = data.get("product", {})
        nutriments = product.get("nutriments", {})
        
        calorias = float(nutriments.get("energy-kcal_100g", nutriments.get("energy-kcal", 0.0) or 0.0))
        proteinas = float(nutriments.get("proteins_100g", 0.0) or 0.0)
        grasas = float(nutriments.get("fat_100g", 0.0) or 0.0)
        carbohidratos = float(nutriments.get("carbohydrates_100g", 0.0) or 0.0)
        fibras = float(nutriments.get("fiber_100g", 0.0) or 0.0)
        
        # Validación estricta de coherencia: Si falta la caloría o los macros principales, se rechaza
        if calorias <= 0.0 or (proteinas == 0.0 and grasas == 0.0 and carbohidratos == 0.0):
            return False
            
        nombre_alimento = product.get("product_name_es") or product.get("product_name") or txt_desconocido
        marca = product.get("brands", "")
        if marca:
            nombre_alimento = f"{nombre_alimento} ({marca})"

        return {
            "alimento": nombre_alimento,
            "peso": 100.0,
            "calorias": calorias,
            "proteinas": proteinas,
            "grasas": grasas,
            "carbohidratos": carbohidratos,
            "fibras": fibras,
            "fuente": "Open Food Facts"
        }
    except Exception as e:
        logger.error(f"⚠️ Error al consultar el código de barras {barcode}: {e}")
        return False
        
def construir_texto_listado_comidas(user_id, comidas, traducciones=None):
    if traducciones is None:
        traducciones = {}
        
    if not comidas:
        return traducciones.get("07_bot_no_comidas_precargadas", "📋 No tenés comidas predeterminadas registradas en tu lista.")

    txt = traducciones.get("07_bot_titulo_listado_comidas", "📋 <b>Listado de Comidas Predeterminadas:</b>\n\n")
    
    for p in comidas:
        nombre_raw = str(p.get('Nombre', ''))
        desc_raw = str(p.get('Descripcion') or p.get('Momento', ''))
        
        nombre = nombre_raw.replace('§', '').replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;').strip()
        descripcion = desc_raw.replace('§', '').replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;').strip()
        
        if descripcion and descripcion.lower() != nombre.lower():
            linea = f"• <b>{nombre}</b>: {descripcion}\n"
        else:
            linea = f"• <b>{nombre}</b>\n"
        
        if len(txt) + len(linea) > 4000:
            txt += traducciones.get("07_bot_mas_comidas_pdf", "• <i>...y más comidas (ver detalle en el PDF adjunto).</i>\n")
            break
            
        txt += linea
        
    return txt
    
# =======================================================================================================================================
@requiere_registro
async def cmd_comidas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    
    comidas = obtener_comidas_usuario(user_id)
    
    if not comidas:
        msg_no_comidas = traducciones.get("07_bot_no_comidas_precargadas", "📋 No tenés comidas predeterminadas registradas en tu lista.")
        await update.message.reply_text(msg_no_comidas)
        return

    txt = construir_texto_listado_comidas(user_id, comidas, traducciones)
    msg_adjunto = traducciones.get("07_bot_adjunto_pdf_comidas", "\n📄 Te adjuntamos el archivo en PDF completo con todos los macronutrientes a continuación.").replace('\\n', '\n')

    txt += msg_adjunto
    
    try:
        await update.message.reply_text(txt, parse_mode="HTML")
    except Exception as e:
        print(f"Error enviando texto de comidas: {e}")
        msg_generando = traducciones.get("07_bot_generando_pdf_comidas", "📋 Generando tu lista de comidas en PDF directamente...")
        await update.message.reply_text(msg_generando)

    try:
        pdf_bytes = generar_pdf_comidas_bytes(comidas, user_id)
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_bytes,
            filename=f"C_{user_id}.pdf"
        )
    except Exception as e:
        print(f"Error generando PDF de comidas: {e}")
        msg_err_pdf = traducciones.get("07_bot_error_gen_pdf", "❌ Ocurrió un error al generar el archivo PDF.")
        await update.message.reply_text(msg_err_pdf)
        
def buscar_comida_precargada_exacta(user_id, texto_codigo):
    codigo_buscado = texto_codigo.strip().upper()
    comidas_usuario = obtener_comidas_usuario(user_id)

    for item in comidas_usuario:
        nombre_item = str(item.get('Nombre') or item.get('Código / Nombre') or '').strip().upper()
        if nombre_item == codigo_buscado:
            return {
                "nombre": item.get('Nombre') or item.get('Código / Nombre'),
                "descripcion": item.get('Descripción') or item.get('Descripcion') or '',
                "peso": float(item.get('Peso', 0)),
                "calorias": float(item.get('Calorias', 0)),
                "proteinas": float(item.get('Proteinas', 0)),
                "grasas": float(item.get('Grasas', 0)),
                "carbohidratos": float(item.get('Carbohidratos', 0)),
                "fibras": float(item.get('Fibras', 0))
            }

    return None
    
def generar_pdf_comidas_bytes(plantillas, user_id=None):
    lang = obtener_idioma_usuario(user_id) if user_id and 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) or {}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1E3A8A'))
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#1E293B'))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8.5, leading=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)

    t_titulo = traducciones.get("07_PDF_comidas_titulo", "LISTADO DE COMIDAS PREDETERMINADAS")

    story = [
        Paragraph(f"<b>{t_titulo}</b>", title_style),
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=12),
    ]

    if not plantillas:
        msg_vacio = traducciones.get("07_PDF_comidas_sin_reg", "No hay comidas predeterminadas cargadas en la hoja 'Plantillas_Comidas'.")
        story.append(Paragraph(msg_vacio, body_style))
    else:
        th_nombre = traducciones.get("07_PDF_comidas_th_nombre", "Nombre")
        th_desc = traducciones.get("07_PDF_comidas_th_desc", "Descripción")
        th_peso = traducciones.get("07_PDF_comidas_th_peso", "Peso (g)")
        th_kcal = traducciones.get("07_PDF_comidas_th_kcal", "Kcal")
        th_prot = traducciones.get("07_PDF_comidas_th_prot", "Prot (g)")
        th_gras = traducciones.get("07_PDF_comidas_th_gras", "Gras (g)")
        th_carb = traducciones.get("07_PDF_comidas_th_carb", "Carb (g)")
        th_fibr = traducciones.get("07_PDF_comidas_th_fibr", "Fibr (g)")

        table_data = [[
            Paragraph(th_nombre, header_style), 
            Paragraph(th_desc, header_style), 
            Paragraph(th_peso, header_style), 
            Paragraph(th_kcal, header_style), 
            Paragraph(th_prot, header_style), 
            Paragraph(th_gras, header_style), 
            Paragraph(th_carb, header_style), 
            Paragraph(th_fibr, header_style)
        ]]
        
        for p in plantillas:
            nombre_limpio = str(p.get("Nombre", "")).replace('§', '').strip()
            desc_limpia = str(p.get("Descripcion") or p.get("Momento", "")).replace('§', '').strip()

            table_data.append([
                Paragraph(nombre_limpio, body_style),
                Paragraph(desc_limpia, body_style),
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

@requiere_registro
async def cmd_cargar_receta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    
    web_app_url = f"https://ianutribot.com/?user_id={user_id}#calculadora"
    
    btn_text = traducciones.get("07_bot_btn_crear_receta", "🍳 Abrir Creador de Recetas")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_text, url=web_app_url)]
    ])
    
    msg_tmpl = traducciones.get("07_bot_msg_cargar_receta", "👋 ¡Hola! Usá el siguiente botón para calcular los valores nutricionales de tu receta e ingresarla directamente en tu planilla personalizada:")
    mensaje = msg_tmpl.format(user_id=user_id)
    
    await update.message.reply_text(mensaje, reply_markup=keyboard)
            
# ========================================================================================================================================

def detectar_y_leer_codigo_barras_ia(base64_image: str) -> str:
    prompt = (
        "Analiza esta imagen de un producto comercial. Busca el código de barras"
        " y lee atentamente los números impresos debajo. Responde ÚNICAMENTE en"
        ' formato JSON:\n{"tiene_numeros": true/false, "codigo_numerico":'
        ' "escribe_aqui_solo_los_numeros_o_vacio"}'
    )

    imagen_data = {"mime_type": "image/jpeg", "data": base64.b64decode(base64_image)}
    configuracion_gen = {"response_mime_type": "application/json", "temperature": 0.0}

    try:
        model = genai.GenerativeModel(MODELO_FOTO)
        response = model.generate_content([prompt, imagen_data], generation_config=configuracion_gen)
        texto_limpio = response.text.replace("```json", "").replace("```", "").strip()
        resultado = json.loads(texto_limpio)
        if resultado.get("tiene_numeros"): return str(resultado.get("codigo_numerico", "")).strip()
        return ""
    except Exception as e_prin:
        logger.warning(f"⚠️ Falla Principal Código Barras ({MODELO_FOTO}): {e_prin}")

    try:
        model_respaldo = genai.GenerativeModel(MODELO_RESPALDO)
        response_respaldo = model_respaldo.generate_content([prompt, imagen_data], generation_config=configuracion_gen)
        texto_limpio = response_respaldo.text.replace("```json", "").replace("```", "").strip()
        resultado = json.loads(texto_limpio)
        if resultado.get("tiene_numeros"): return str(resultado.get("codigo_numerico", "")).strip()
    except Exception as e_respaldo:
        logger.warning(f"⚠️ Falla Respaldo Código Barras ({MODELO_RESPALDO}): {e_respaldo}")

    try:
        model_emerg = genai.GenerativeModel(MODELO_FOTO_EMERGENCIA)
        response_emerg = model_emerg.generate_content([prompt, imagen_data], generation_config=configuracion_gen)
        texto_limpio = response_emerg.text.replace("```json", "").replace("```", "").strip()
        resultado = json.loads(texto_limpio)
        if resultado.get("tiene_numeros"): return str(resultado.get("codigo_numerico", "")).strip()
    except Exception as e_emergencia:
        logger.error(f"❌ Error crítico en código de barras. Fallaron todos: {e_emergencia}")

    return ""
  
async def procesar_codigo_ingresado(message_obj, context, barcode_text: str):
    user_id = message_obj.from_user.id
    
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    
    msg_analizando = traducciones.get("07_bot_analizando_barra", "🔍 Analizando código de barras y verificando producto...")
    msg_espera = await message_obj.reply_text(msg_analizando)
    
    try:
        txt_desconocido = traducciones.get("07_bot_producto_desconocido", "Producto desconocido")
        
        resultado_api = await asyncio.to_thread(consultar_codigo_barras, barcode_text, txt_desconocido)
        
        if resultado_api:
            item_procesado = {
                "alimento": resultado_api['alimento'],
                "alimento_display": resultado_api['alimento'],
                "peso": resultado_api['peso'],
                "calorias": resultado_api['calorias'],
                "proteinas": resultado_api['proteinas'],
                "grasas": resultado_api['grasas'],
                "carbohidratos": resultado_api['carbohidratos'],
                "fibras": resultado_api['fibras'],
                "fuente": "Open Food Facts"
            }

            fecha_auto, momento_auto = obtener_momento_y_fecha_auto()

            try: await msg_espera.delete()
            except: pass

            msg_prod_encontrado = traducciones.get("07_bot_producto_encontrado", "📋 Producto encontrado (valores calculados cada 100 g):")
            msg_menu = await message_obj.reply_text(msg_prod_encontrado)
            
            context.user_data['last_menu_msg_id'] = msg_menu.message_id
            context.user_data['pending_items'] = [item_procesado]
            context.user_data['pending_fecha'] = fecha_auto
            context.user_data['pending_momento'] = momento_auto
                
            await render_confirmation_screen(msg_menu, context)
        else:
            msg_no_enc = traducciones.get("07_bot_barra_no_encontrada", "⚠️ Código de barras no encontrado en la base de datos. Intentá ingresarlo como texto o foto.")
            await msg_espera.edit_text(msg_no_enc)
            
    except Exception as e:
        msg_err_gen = traducciones.get("07_bot_error_consulta_barra", "❌ Error al consultar el código: {e}").format(e=e)
        await msg_espera.edit_text(msg_err_gen)

@requiere_registro
async def cmd_barra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    
    args = context.args
    
    if not args:
        msg_solic_txt = traducciones.get("07_bot_solic_barra_num", "⌨️ Por favor, ingresá los números del código de barras con el comando /barra NUMERO:")
        msg_solic = await update.message.reply_text(
            msg_solic_txt,
            parse_mode="Markdown"
        )
        context.user_data['awaiting_barcode_input'] = True
        context.user_data['msg_solicitud_barcode_id'] = msg_solic.message_id
        return

    barcode_text = args[0].strip()
    await procesar_codigo_ingresado(update.message, context, barcode_text)
               

# ======================================================================================================================================

@requiere_registro
async def cmd_borrar_comida(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    
    if context.args:
        nombre_a_borrar = " ".join(context.args).strip()
        
        comida_encontrada = buscar_comida_precargada_exacta(user_id, nombre_a_borrar)
        
        if not comida_encontrada:
            msg_no_enc = traducciones.get("07_bot_comida_no_encontrada", "❌ No se encontró ninguna comida registrada con el nombre exacto: <b>{nombre}</b>.")
            await update.message.reply_text(
                msg_no_enc.replace("{nombre}", nombre_a_borrar),
                parse_mode="HTML"
            )
            return
        
        exito = eliminar_comida_precargada_db(user_id, comida_encontrada['nombre'])
        
        if exito:
            msg_exito = traducciones.get("07_bot_comida_borrada_exito", "✅ La comida <b>{nombre}</b> ha sido eliminada exitosamente de tu planilla.")
            await update.message.reply_text(
                msg_exito.replace("{nombre}", comida_encontrada['nombre']),
                parse_mode="HTML"
            )
        else:
            msg_err_db = traducciones.get("07_bot_error_db_borrar", "❌ Hubo un error en la base de datos al intentar borrar <b>{nombre}</b>.")
            await update.message.reply_text(
                msg_err_db.replace("{nombre}", comida_encontrada['nombre']),
                parse_mode="HTML"
            )
        return

    comidas = obtener_comidas_usuario(user_id)
    
    if not comidas:
        msg_no_reg = traducciones.get("07_bot_no_comidas_borrar", "📋 No hay comidas predeterminadas registradas para eliminar.")
        await update.message.reply_text(msg_no_reg)
        return

    txt = construir_texto_listado_comidas(user_id, comidas, traducciones)

    msg_instruccion = traducciones.get("07_bot_como_borrar_comida", "\n🗑️ <b>¿Cómo borrar una comida?</b>\nCopiá el nombre exacto de la lista de arriba y escribí el comando de la siguiente forma:\n<code>/borracomida Nombre de la Comida</code>").replace('\\n', '\n')
    txt += msg_instruccion
    
    try:
        await update.message.reply_text(txt, parse_mode="HTML")
    except Exception as e:
        print(f"Error enviando texto de borrado: {e}")
        msg_err_list = traducciones.get("07_bot_error_mostrar_listado", "📋 Ocurrió un error al mostrar el listado.")
        await update.message.reply_text(msg_err_list)
        
@requiere_registro
async def cmd_eliminar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    context.user_data.pop('del_fecha', None)
    context.user_data.pop('del_momento', None)

    hoy_label = obtener_ahora_arg().strftime("%d/%m")
    ayer_label = (obtener_ahora_arg() - timedelta(days=1)).strftime("%d/%m")

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"📅 {hoy_label}", callback_data="del_d_hoy"), 
            InlineKeyboardButton(f"📆 {ayer_label}", callback_data="del_d_ayer")
        ],
        [
            InlineKeyboardButton("🔄  🗓️", callback_data="del_d_otro")
        ]
    ])
    
    msg_txt = traducciones.get("07_bot_titulo_eliminar_ingestas", "🗑️ **Eliminación de Ingestas / Actividades:**\nSeleccioná el día que querés revisar:").replace('\\n', '\n')
    await update.message.reply_text(
        msg_txt, 
        reply_markup=keyboard, 
        parse_mode="Markdown"
    )

async def mostrar_selector_momento_eliminar(query_or_msg, context):
    user_id = query_or_msg.from_user.id if hasattr(query_or_msg, 'from_user') else query_or_msg.message.chat_id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    if not context.user_data.get('del_fecha'):
        context.user_data['del_fecha'] = obtener_ahora_arg().strftime("%Y-%m-%d")
        
    fecha = context.user_data.get('del_fecha')
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌅 08-11 ⏰", callback_data="del_mom_Desayuno"), InlineKeyboardButton("☀️ 11-16 ⏰", callback_data="del_mom_Almuerzo")],
        [InlineKeyboardButton("☕ 16-20 ⏰", callback_data="del_mom_Merienda"), InlineKeyboardButton("🌙 20-00 ⏰", callback_data="del_mom_Cena")],
        [InlineKeyboardButton("🏃 ⚡", callback_data="del_mom_Actividad")],
        [InlineKeyboardButton("🔄. 🗓️", callback_data="del_cambiar_fecha")]
    ])
    
    txt_tmpl = traducciones.get("07_bot_txt_sel_momento_del", "📅 Fecha seleccionada: `{fecha}`\n\nSeleccioná el momento o actividad que querés revisar para eliminar:")
    txt = txt_tmpl.format(fecha=fecha).replace('\\n', '\n')
    
    if hasattr(query_or_msg, 'edit_message_text'):
        await query_or_msg.edit_message_text(txt, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await query_or_msg.message.reply_text(txt, reply_markup=keyboard, parse_mode="Markdown")
                
async def render_pantalla_items_eliminar(query, user_id, context):
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    fecha = context.user_data.get('del_fecha', obtener_ahora_arg().strftime("%Y-%m-%d"))
    momento = context.user_data.get('del_momento', 'Desayuno')

    df = obtener_datos_usuario(user_id)
    if df.empty or 'Fecha' not in df.columns or 'Momento' not in df.columns:
        items_momento = []
    else:
        df['Fecha_clean'] = df['Fecha'].astype(str).str.strip()
        df['Momento_clean'] = df['Momento'].astype(str).str.strip().str.lower()
        momento_busqueda = momento.strip().lower()
        if momento_busqueda == 'actividad':
            df_sub = df[(df['Fecha_clean'] == str(fecha).strip()) & (df['Momento_clean'].isin(['actividad', 'actividad física', 'ejercicio']))]
        else:
            df_sub = df[(df['Fecha_clean'] == str(fecha).strip()) & (df['Momento_clean'] == momento_busqueda)]
        items_momento = df_sub.to_dict(orient='records')

    if not items_momento:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌", callback_data="del_salir_pantalla")]])
        txt_vacio = traducciones.get("07_bot_del_no_registros_momento", "⚠️ No se encontraron registros para este momento en la fecha `{fecha}`.").format(fecha=fecha)
        try:
            await query.edit_message_text(txt_vacio, reply_markup=keyboard, parse_mode="Markdown")
        except Exception:
            await query.message.reply_text(txt_vacio, reply_markup=keyboard, parse_mode="Markdown")
        return

    txt_titulo = traducciones.get("07_bot_del_titulo_eliminar_registros", "🗑️ **Eliminar Registros**\n📅 Fecha: `{fecha}` | Momento: `{momento}`\n\n").format(fecha=fecha, momento=momento)
    txt = txt_titulo.replace('\\n', '\n')
    
    for idx, item in enumerate(items_momento, start=1):
        alimento = str(item.get('Alimento', 'Desconocido'))
        peso = float(item.get('Peso', 0))
        calorias = float(item.get('Calorias', 0))
        if momento.lower() == 'actividad':
            txt += f"**{idx}. {alimento}**: `{calorias:.1f} kcal`\n"
        else:
            txt += f"**{idx}. {alimento}** ({peso:.1f}g): `{calorias:.1f} kcal`\n"

    keyboard = []
    for item in items_momento:
        item_id = item.get('id_registro')
        nombre_corto = str(item.get('Alimento', ''))[:18]
        if item_id is not None:
            keyboard.append([InlineKeyboardButton(f"🗑️ {nombre_corto}", callback_data=f"del_reg_{item_id}")])

    keyboard.append([InlineKeyboardButton("❌", callback_data="del_salir_pantalla")])
    markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(txt, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        await query.message.reply_text(txt, reply_markup=markup, parse_mode="Markdown")
                
@requiere_registro
async def manejar_callback_eliminacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    
    if data == "del_d_hoy":
        context.user_data['del_fecha'] = obtener_ahora_arg().strftime("%Y-%m-%d")
        await mostrar_selector_momento_eliminar(query, context)

    elif data == "del_d_ayer":
        context.user_data['del_fecha'] = (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d")
        await mostrar_selector_momento_eliminar(query, context)

    elif data == "del_d_otro":
        context.user_data['awaiting_del_custom_date'] = True
        msg_solic_fecha = traducciones.get("07_bot_solic_fecha_custom", "📅 Ingresá la fecha que querés revisar (Ej: `2026-08-15` or `15/08`):")
        msg_solic = await query.message.reply_text(msg_solic_fecha, parse_mode="Markdown")
        context.user_data['msg_solicitud_del_fecha_id'] = msg_solic.message_id

    elif data.startswith("del_mom_"):
        momento = data.replace("del_mom_", "")
        context.user_data['del_momento'] = momento
        await render_pantalla_items_eliminar(query, user_id, context)

    elif data.startswith("del_reg_"):
        item_id = int(data.replace("del_reg_", ""))
        exito = eliminar_registro_por_id(user_id, item_id)
        
        if exito:
            msg_item_ok = traducciones.get("07_bot_item_eliminado_ok", "🗑️ Ítem eliminado correctamente.")
            await query.answer(msg_item_ok, show_alert=False)
        else:
            msg_item_err = traducciones.get("07_bot_item_eliminado_err", "⚠️ No se pudo eliminar el ítem.")
            await query.answer(msg_item_err, show_alert=True)
            
        await render_pantalla_items_eliminar(query, user_id, context)

    elif data == "del_salir_pantalla":
        txt_canc = traducciones.get("07_bot_del_operacion_finalizada", "❌ Operación de eliminación finalizada.")
        try:
            await query.edit_message_text(txt_canc, parse_mode="Markdown")
        except Exception:
            try: await query.message.delete()
            except: pass 

    elif data in ["del_cambiar_fecha", "del_volver_momentos"]:
        await mostrar_selector_momento_eliminar(query, context)     

# =====================================================================================================================================

async def _sub_manejar_edicion_perfil_inputs(update, context, raw_text, chat_id):
    user_id = update.effective_user.id
    ahora = obtener_ahora_arg()
    mes_actual = ahora.strftime("%Y-%m")

    cambio_biometrico = False
    mensaje_exito = ""
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    if context.user_data.get('awaiting_edit_perfil_peso'):
        try:
            nuevo_val = float(raw_text.replace(',', '.'))
            res_cal = await asyncio.to_thread(guardar_perfil_db, user_id, peso=nuevo_val, mes=mes_actual)
            if isinstance(res_cal, dict) and res_cal.get("error"):
                await update.message.reply_text(res_cal["mensaje"], parse_mode="Markdown")
            else:
                msg_ok = traducciones.get("07_bot_peso_actualizado", "✅ Peso actualizado a `{nuevo_val} kg`.").format(nuevo_val=nuevo_val)
                mensaje_exito = res_cal["mensaje"] if isinstance(res_cal, dict) and "mensaje" in res_cal else msg_ok
                cambio_biometrico = True
        except Exception:
            msg_err = traducciones.get("07_bot_valor_invalido", "❌ Valor inválido. Ingresá números.")
            await update.message.reply_text(msg_err)
        context.user_data['awaiting_edit_perfil_peso'] = False

    elif context.user_data.get('awaiting_edit_perfil_altura'):
        try:
            nuevo_val = float(raw_text.replace(',', '.'))
            await asyncio.to_thread(_core_guardar_perfil_db, user_id, mes_actual, {"ALTURA": nuevo_val})
            mensaje_exito = traducciones.get("07_bot_altura_actualizada", "✅ Altura actualizada a `{nuevo_val} cm`.").format(nuevo_val=nuevo_val)
            cambio_biometrico = True
        except Exception:
            msg_err = traducciones.get("07_bot_valor_invalido", "❌ Valor inválido. Ingresá números.")
            await update.message.reply_text(msg_err)
        context.user_data['awaiting_edit_perfil_altura'] = False

    elif context.user_data.get('awaiting_edit_perfil_cintura'):
        try:
            nuevo_val = float(raw_text.replace(',', '.'))
            await asyncio.to_thread(_core_guardar_usuario_db, user_id, {"cintura_cm": nuevo_val})
            mensaje_exito = traducciones.get("07_bot_cintura_actualizada", "✅ Cintura actualizada a `{nuevo_val} cm`.").format(nuevo_val=nuevo_val)
            cambio_biometrico = True
        except Exception:
            msg_err = traducciones.get("07_bot_valor_invalido", "❌ Valor inválido.")
            await update.message.reply_text(msg_err)
        context.user_data['awaiting_edit_perfil_cintura'] = False

    elif context.user_data.get('awaiting_edit_perfil_cuello'):
        try:
            nuevo_val = float(raw_text.replace(',', '.'))
            await asyncio.to_thread(_core_guardar_usuario_db, user_id, {"cuello_cm": nuevo_val})
            mensaje_exito = traducciones.get("07_bot_cuello_actualizado", "✅ Cuello actualizado a `{nuevo_val} cm`.").format(nuevo_val=nuevo_val)
            cambio_biometrico = True
        except Exception:
            msg_err = traducciones.get("07_bot_valor_invalido", "❌ Valor inválido.")
            await update.message.reply_text(msg_err)
        context.user_data['awaiting_edit_perfil_cuello'] = False

    elif context.user_data.get('awaiting_edit_perfil_cadera'):
        try:
            nuevo_val = float(raw_text.replace(',', '.'))
            await asyncio.to_thread(_core_guardar_usuario_db, user_id, {"cadera_cm": nuevo_val})
            mensaje_exito = traducciones.get("07_bot_cadera_actualizada", "✅ Cadera actualizada a `{nuevo_val} cm`.").format(nuevo_val=nuevo_val)
            cambio_biometrico = True
        except Exception:
            msg_err = traducciones.get("07_bot_valor_invalido", "❌ Valor inválido.")
            await update.message.reply_text(msg_err)
        context.user_data['awaiting_edit_perfil_cadera'] = False

    elif context.user_data.get('awaiting_edit_perfil_nombre'):
        try:
            nuevo_val = str(raw_text).strip()
            await asyncio.to_thread(_core_guardar_usuario_db, user_id, {"Nombre": nuevo_val})
            msg_ok = traducciones.get("07_bot_nombre_actualizado", "✅ Nombre actualizado a `{nuevo_val}`.").format(nuevo_val=nuevo_val)
            await update.message.reply_text(msg_ok.replace('\\n', '\n'), parse_mode="Markdown")
        except Exception:
            msg_err = traducciones.get("07_bot_valor_invalido", "❌ Valor inválido.")
            await update.message.reply_text(msg_err)
        context.user_data['awaiting_edit_perfil_nombre'] = False

    elif context.user_data.get('awaiting_edit_perfil_prof'):
        try:
            nuevo_val = str(raw_text).strip()
            await asyncio.to_thread(_core_guardar_usuario_db, user_id, {"profesional": nuevo_val})
            msg_ok = traducciones.get("07_bot_profesional_actualizado", "✅ Profesional actualizado a `{nuevo_val}`.").format(nuevo_val=nuevo_val)
            await update.message.reply_text(msg_ok.replace('\\n', '\n'), parse_mode="Markdown")
        except Exception:
            msg_err = traducciones.get("07_bot_valor_invalido", "❌ Valor inválido.")
            await update.message.reply_text(msg_err)
        context.user_data['awaiting_edit_perfil_prof'] = False

    # --- RECÁLCULO DINÁMICO INMEDIATO ---
    if cambio_biometrico and mensaje_exito:
        try:
            perfil = await asyncio.to_thread(obtener_datos_completos_usuario, user_id, mes_target=mes_actual)
            
            if perfil:
                peso = parse_raw_val(perfil.get('PESO', perfil.get('Peso', 0)))
                altura = parse_raw_val(perfil.get('ALTURA', perfil.get('Altura', 0)))
                edad = parse_raw_val(perfil.get('EDAD', perfil.get('Edad', 0)))
                genero = str(perfil.get('GENERO', perfil.get('Sexo', 'M')))
                
                ocupacion = parse_raw_val(perfil.get('ocupacion', perfil.get('OCUPACION', 1.375)))
                if ocupacion > 10: ocupacion /= 1000.0
                
                cadera = perfil.get('cadera_cm', 0.0)
                ritmo = perfil.get('ritmo_preferido', 'moderado')

                tmb, get_val = calcular_tmb_y_get(peso, altura, int(edad), genero, ocupacion, cadera_cm=cadera)
                peso_ideal = calcular_peso_ideal(genero, altura, edad=int(edad))
                peso_etapa = calcular_peso_etapa(peso, peso_ideal, ritmo)

                msg_recalculo = traducciones.get(
                    "07_bot_metricas_recalculadas",
                    "{mensaje_exito}\n\n🔄 **Nuevas métricas calculadas:**\n• TMB (Metabolismo Basal): `{tmb} kcal/día`\n• GET (Gasto Energético): `{get_val} kcal/día`\n• Meta / Peso Etapa: `{peso_etapa} kg`"
                ).replace('\\n', '\n')
                
                # Reemplazamos formatos complejos si quedaron en la base de datos vieja
                msg_recalculo = msg_recalculo.replace("{tmb:.0f}", "{tmb}").replace("{get_val:.0f}", "{get_val}").replace("{peso_etapa:.1f}", "{peso_etapa}")
                
                txt_recalculo = msg_recalculo.format(
                    mensaje_exito=mensaje_exito, 
                    tmb=f"{tmb:.0f}", 
                    get_val=f"{get_val:.0f}", 
                    peso_etapa=f"{peso_etapa:.1f}"
                )

                await update.message.reply_text(txt_recalculo, parse_mode="Markdown")
            else:
                await update.message.reply_text(mensaje_exito.replace('\\n', '\n'), parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error recalculando métricas en vivo para {user_id}: {e}")
            await update.message.reply_text(mensaje_exito.replace('\\n', '\n'), parse_mode="Markdown")

@requiere_registro
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id, chat_id = update.effective_user.id, update.effective_chat.id
    lang = obtener_idioma_usuario(user_id) or "es"
    traducciones = obtener_traducciones_db(lang) or {}

    raw_text = update.message.text.strip() if update.message and update.message.text else ""
    if not raw_text:
        return

    # --- 1. INTERCEPTOR EDICIÓN VALORES CLÍNICOS (Médicos) ---
    if context.user_data.get("campo_clinico_a_editar"):
        if await procesar_cambio_valor_clinico(update, context): return

    # --- 2. INTERCEPTOR DE NOTAS MÉDICAS (Médicos) ---
    if context.user_data.get("esperando_texto_nota_para") or context.user_data.get("esperando_nota_informe_para"):
        if "esperando_nota_informe_para" in context.user_data:
            if await procesar_texto_nota_informe(update, context): return
        else:
            if await procesar_texto_nota_medica(update, context): return

    # --- 3. EDICIÓN DE PERFIL (Usuarios) ---
    estados_perfil = [
        "awaiting_edit_perfil_peso", "awaiting_edit_perfil_altura",
        "awaiting_edit_perfil_cintura", "awaiting_edit_perfil_cuello",
        "awaiting_edit_perfil_cadera", "awaiting_edit_perfil_nombre",
        "awaiting_edit_perfil_prof"
    ]
    if any(context.user_data.get(st) for st in estados_perfil):
        await _sub_manejar_edicion_perfil_inputs(update, context, raw_text, chat_id)
        return

    # --- 4. PRESIÓN ARTERIAL ---
    if context.user_data.get("awaiting_presion_nota"):
        context.user_data.pop("awaiting_presion_nota", None)
        datos_presion = context.user_data.pop("pending_presion_foto", None)
        
        if raw_text.lower() == "cancelar":
            await update.message.reply_text(traducciones.get("07_bot_presion_cancelada", "❌ Registro de presión cancelado."))
            return
            
        if datos_presion:
            alta, baja, pulsaciones = datos_presion.get("alta"), datos_presion.get("baja"), datos_presion.get("pulsaciones")
            await asyncio.to_thread(guardar_presion_db, user_id, alta, baja, pulsaciones, nota=raw_text)
            
            lbl_pul = traducciones.get("07_bot_presi_lbl_pulsaciones", "Pulsaciones")
            pul_txt = f" | {lbl_pul}: `{pulsaciones:.0f} lpm`" if pulsaciones > 0 else ""
            msg_presion_ok = traducciones.get("07_bot_presion_registrada_ok", "✅ *¡Presión arterial registrada con éxito!*\n\n• Presión Alta: `{alta:.0f} mmHg`\n• Presión Baja: `{baja:.0f} mmHg`{pul_txt}\n📝 Nota: `{nota}`").replace("\\n", "\n")
            await update.message.reply_text(msg_presion_ok.format(alta=alta, baja=baja, pul_txt=pul_txt, nota=raw_text), parse_mode="Markdown")
        else:
            await update.message.reply_text(traducciones.get("07_bot_presion_expirada", "⚠️ Los datos temporales expiraron."))
        return

    # --- 5. EDICIÓN DE FECHAS, ÍTEMS Y ACTIVIDADES ---
    if context.user_data.get("awaiting_custom_date"):
        await _sub_manejar_fecha_personalizada_ingesta(update, context, raw_text, chat_id)
        return
    if context.user_data.get("awaiting_activity_text"):
        await _sub_manejar_texto_actividad(update, context, raw_text, chat_id)
        return
    if context.user_data.get("awaiting_del_custom_date"):
        await _sub_manejar_fecha_eliminacion(update, context, raw_text, chat_id)
        return
    if context.user_data.get("awaiting_diario_custom_date"):
        await _sub_manejar_fecha_diario(update, context, raw_text, chat_id)
        return
    if context.user_data.get("awaiting_edit_item_val"):
        await _sub_manejar_edicion_item(update, context, raw_text, chat_id)
        return
    if raw_text.startswith("*"):
        await _sub_manejar_plantilla_comida(update, context, raw_text, user_id)
        return
    if context.user_data.get("awaiting_barcode_input"):
        context.user_data.pop("awaiting_barcode_input", None)
        msg_solic = context.user_data.pop("msg_solicitud_barcode_id", None)
        if msg_solic:
            try: await context.bot.delete_message(chat_id=chat_id, message_id=msg_solic)
            except Exception: pass
        await procesar_codigo_ingresado(update.message, context, raw_text)
        return

    # --- 6. ANÁLISIS DE TEXTO LIBRE CON IA ---
    msg_analizando_ia = traducciones.get("07_bot_analizando_texto_ia", "🤖 Analizando texto con Inteligencia Artificial...")
    msg = await update.message.reply_text(msg_analizando_ia)
    
    try:
        data = await analizar_con_ia(raw_text, user_id, msg_obj=msg)
        tipo = str(data.get("tipo", "")).strip().upper()

        if tipo == "ERROR_IA":
            msg_err_ia = traducciones.get("07_bot_error_ia_texto", "⚠️ No se pudo conectar con la Inteligencia Artificial. Por favor, reintentá en unos segundos.")
            await msg.edit_text(msg_err_ia)
            return

        if tipo == "RECHAZO":
            try: await msg.delete()
            except Exception: pass
            return

        # Seguro idéntico para texto: si es actividad y la IA devolvió una sola palabra, corregimos el formato con los minutos adelante
        if tipo == "ACTIVIDAD" and data.get("items"):
            for item in data["items"]:
                alim = str(item.get("alimento", "")).strip()
                if not re.match(r'^\d+', alim) or len(alim.split()) <= 2:
                    m_min = re.search(r'(\d+)\s*(?:minutos|minuto|min|m\b|horas|hora|hs|h\b)', raw_text, re.IGNORECASE)
                    if m_min:
                        num_val = int(m_min.group(1))
                        if 'hora' in m_min.group(0).lower() or 'h' in m_min.group(0).lower():
                            num_val *= 60
                        resto = raw_text[:m_min.start()].strip() + " " + raw_text[m_min.end():].strip()
                        resto = re.sub(r'^(de|por|durante)\s+', '', resto, flags=re.IGNORECASE).strip()
                        resto = re.sub(r'\s+', ' ', resto).strip()
                        item["alimento"] = f"{num_val} min {resto}" if resto else f"{num_val} min {alim}"

        await procesar_y_mostrar_confirmacion(data, msg, context)

    except Exception as e:
        msg_err_proc = traducciones.get("07_bot_error_procesar_texto", "❌ Error al procesar el texto: {e}")
        try: await msg.edit_text(msg_err_proc.format(e=e))
        except Exception: pass
        
@requiere_registro
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or "es"
    traducciones = obtener_traducciones_db(lang) or {}

    txt_analizando_img = traducciones.get("07_bot_analizando_imagen", "📸 Analizando imagen...")
    # Este es el ÚNICO mensaje inicial estático que verá el usuario
    msg = await update.message.reply_text(txt_analizando_img)

    try:
        photo_bytes_originales = await (await update.message.photo[-1].get_file()).download_as_bytearray()
        np_arr = np.frombuffer(photo_bytes_originales, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        tiene_codigo_local = False
        if img is not None:
            detector = cv2.barcode.BarcodeDetector()
            retval, points = detector.detect(img)
            if retval: tiene_codigo_local = True

        # COMPRESIÓN OPTIMIZADA PARA IA (Mantiene nitidez en textos y pantallas)
        if img is not None:
            h, w = img.shape[:2]
            max_dim = 1280  # Límite superior de seguridad (Telegram suele mandar como mucho 1280px)
            if max(h, w) > max_dim:
                scale = max_dim / float(max(h, w))
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            
            # Calidad 90 evita artefactos de compresión alrededor de las letras
            success, encoded_img = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            photo_bytes_comprimidos = encoded_img.tobytes() if success else photo_bytes_originales
        else:
            photo_bytes_comprimidos = photo_bytes_originales
        
        base64_image = base64.b64encode(photo_bytes_comprimidos).decode("utf-8")

        if tiene_codigo_local:
            try: await msg.edit_text(traducciones.get("07_bot_barra_detectada", "🔍 Código de barras detectado. Leyendo números..."))
            except Exception: pass
            
            codigo_leido = await asyncio.to_thread(detectar_y_leer_codigo_barras_ia, base64_image)
            if codigo_leido and len(codigo_leido.strip()) >= 4:
                try: await msg.delete()
                except Exception: pass
                return await procesar_codigo_ingresado(update.message, context, codigo_leido.strip())
            else:
                try: await msg.edit_text(traducciones.get("07_bot_error_barra_ilegible", "⚠️ No se pudieron leer los números del código de barras. Por favor, ingresalo como texto."))
                except Exception: pass
                return
        
        # 1. ARRANCAMOS EL MOTOR DE ANIMACIÓN EN PARALELO
        tarea_animacion = asyncio.create_task(animar_carga(msg, traducciones))
        try:
            # 2. LA IA TRABAJA MIENTRAS LA ANIMACIÓN GIRA
            data = await analizar_imagen_con_ia(base64_image, user_id, msg_obj=msg)
        finally:
            # 3. APENAS TERMINA LA IA, APAGAMOS LA ANIMACIÓN SÍ O SÍ
            tarea_animacion.cancel()
            
        tipo = str(data.get("tipo", "")).strip().upper()

        if tipo == "ERROR_IA":
            await msg.edit_text(traducciones.get('07_bot_error_imagen_fallida', "⚠️ No se pudo conectar con la Inteligencia Artificial. Reintentá en unos segundos."), parse_mode="Markdown")
            return
            
        elif tipo == "RECHAZO" or not tipo:
            await msg.edit_text(traducciones.get('07_bot_foto_rechazada', "⚠️ **Imagen no reconocida**\nLa foto no corresponde a un plato de comida o tensiómetro."), parse_mode="Markdown")
            return
            
        elif tipo == "PRESION" or tipo == "PRESIÓN":
            return await _sub_manejar_foto_presion(update, context, data, msg)
            
        else:
            return await procesar_y_mostrar_confirmacion(data, msg, context)

    except Exception as e:
        logger.warning(f"⚠️ Falla crítica procesando imagen para usuario {user_id}: {e}")
        try: await msg.edit_text(traducciones.get("07_bot_error_timeout_foto", "⚠️ **Error al procesar la imagen.** Por favor, ingresá los datos por texto o voz."), parse_mode="Markdown")
        except Exception: pass
        
@requiere_registro
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or "es"
    traducciones = obtener_traducciones_db(lang) or {}

    txt_escuchando = traducciones.get("07_bot_escuchando_audio", "🎙️ Escuchando y procesando audio...")
    msg = await update.message.reply_text(txt_escuchando)
    
    try:
        file = await context.bot.get_file(update.message.voice.file_id)
        audio_bytes = await file.download_as_bytearray()
        ahora = obtener_ahora_arg()
        
        system_prompt = (
            f"Sos un asistente nutricional inteligente. Idioma: {lang}.\n"
            f"La fecha de HOY es {ahora.strftime('%Y-%m-%d')} y el mes actual es {ahora.strftime('%Y-%m')}.\n"
            f"Escuchá el audio y realizá DOS tareas simultáneas:\n"
            f"1. Transcribí exactamente lo que dijo el usuario en el campo 'transcripcion'. ¡Este campo es obligatorio SIEMPRE!\n"
            f"2. Clasificá la intención y generá un JSON estricto según estas reglas:\n\n"
            f"REGLA ANTI-SPAM: Si el usuario menciona alimentos ficticios, combinaciones absurdas (ej: 'piedras con mayonesa') o cantidades humanamente imposibles de ingerir en una sola comida (ej: '50 pizzas', '20 litros de bebida'), clasificá la intención directamente como RECHAZO.\n\n"
            f"SI ES COMIDA: {{\"transcripcion\": \"...\", \"tipo\": \"Comida\", \"items\": [{{\"alimento\": \"...\", \"peso\": 0, \"calorias\": 0, \"proteinas\": 0, \"grasas\": 0, \"carbohidratos\": 0, \"fibras\": 0}}]}} (Ajustá calorías = Prot*4 + Carb*4 + Grasas*9)\n"
            f"SI ES ACTIVIDAD FISICA: {{\"transcripcion\": \"...\", \"tipo\": \"Actividad\", \"items\": [{{\"alimento\": \"[MINUTOS] min [DETALLE COMPLETO SIN RESUMIR]\", \"peso\": 0, \"calorias\": -0}}]}} "
            f"(REGLA CRÍTICA DE ACTIVIDAD: El campo 'alimento' DEBE empezar SIEMPRE con el número de minutos seguido de 'min' y conservar todos los detalles dichos por el usuario. Ejemplo: si dice 'caminata de 50 minutos en el parque recorriendo 3000 metros', 'alimento' DEBE ser exactamente '50 min caminata en el parque recorriendo 3000 metros'. PROHIBIDO resumir a una sola palabra).\n"
            f"SI ES RESUMEN MENSUAL: {{\"transcripcion\": \"...\", \"tipo\": \"INFORME_MENSUAL\", \"parametro\": \"YYYY-MM\"}}\n"
            f"SI ES RESUMEN DIARIO: {{\"transcripcion\": \"...\", \"tipo\": \"INFORME_DIARIO\", \"parametro\": \"YYYY-MM-DD\"}}\n"
            f"SI ES RESUMEN SEMANAL: {{\"transcripcion\": \"...\", \"tipo\": \"INFORME_SEMANAL\"}}\n"
            f"SI ES RECHAZO: {{\"transcripcion\": \"...\", \"tipo\": \"RECHAZO\"}}"
        )

        audio_data = {"mime_type": "audio/ogg", "data": bytes(audio_bytes)}
        configuracion_gen = {"response_mime_type": "application/json", "temperature": 0.1}
        payload_ia = ["Procesá este audio:", audio_data]

        try:
            model = genai.GenerativeModel(MODELO_AUDIO, system_instruction=system_prompt)
            resp = await asyncio.to_thread(model.generate_content, payload_ia, generation_config=configuracion_gen)
            data = json.loads(resp.text.replace("```json", "").replace("```", "").strip())
        except Exception as e_prin:
            logger.warning(f"⚠️ Falla Principal Audio ({MODELO_AUDIO}): {e_prin}. Pasando a Respaldo...")
            msg_ocupado = traducciones.get("07_bot_audio_servidor_ocupado", "⚠️ Servidor de audio ocupado. Cambiando a servidor de respaldo...")
            try: await msg.edit_text(msg_ocupado)
            except Exception: pass
            
            try:
                model_resp = genai.GenerativeModel(MODELO_RESPALDO, system_instruction=system_prompt)
                resp_resp = await asyncio.to_thread(model_resp.generate_content, payload_ia, generation_config=configuracion_gen)
                data = json.loads(resp_resp.text.replace("```json", "").replace("```", "").strip())
            except Exception as e_resp:
                logger.warning(f"⚠️ Falla Respaldo Audio ({MODELO_RESPALDO}): {e_resp}. Pasando a Emergencia...")
                msg_emerg = traducciones.get("07_bot_audio_servidor_emergencia", "⚠️ Reintentando conexión con servidor de emergencia...")
                try: await msg.edit_text(msg_emerg)
                except Exception: pass
                
                try:
                    model_emer = genai.GenerativeModel(MODELO_EMERGENCIA, system_instruction=system_prompt)
                    resp_emer = await asyncio.to_thread(model_emer.generate_content, payload_ia, generation_config=configuracion_gen)
                    data = json.loads(resp_emer.text.replace("```json", "").replace("```", "").strip())
                except Exception as e_emer:
                    logger.error(f"❌ Fallaron todos los modelos de audio: {e_emer}")
                    msg_error_conex = traducciones.get("07_bot_audio_error_conexion", "⚠️ **Error de conexión.** Todos los servidores fallaron. Por favor, reintentá más tarde.")
                    await msg.edit_text(msg_error_conex, parse_mode="Markdown")
                    return

        transcription = data.get("transcripcion", "")
        tipo = str(data.get("tipo", "")).strip().upper()

        if context.user_data.get("awaiting_edit_item_val"):
            try: await msg.delete()
            except Exception: pass
            await _sub_manejar_edicion_item(update, context, transcription, update.effective_chat.id)
            return

        if context.user_data.get("awaiting_activity_voice"):
            return await _sub_manejar_voz_actividad(update, context, transcription, msg)

        if tipo == "ERROR_IA" or not transcription:
            msg_no_entendido = traducciones.get("07_bot_audio_no_entendido", "⚠️ No se pudo procesar su archivo de audio o el volumen no es el adecuado. Por favor, vuelva a grabarlo o ingrese los datos por texto.")
            await msg.edit_text(msg_no_entendido)
            return

        if tipo == "INFORME_MENSUAL":
            try: await msg.delete()
            except Exception: pass
            param = str(data.get("parametro", "")).strip()
            mes_target = param[:7] if param and re.match(r"^20\d{2}-\d{2}", param) else ahora.strftime("%Y-%m")
            context.args = [mes_target]
            await mostrar_resumen_mes(update, context)
            return

        elif tipo == "INFORME_SEMANAL":
            try: await msg.delete()
            except Exception: pass
            await cmd_mensaje(update, context)
            return

        elif tipo == "INFORME_DIARIO":
            try: await msg.delete()
            except Exception: pass
            param = str(data.get("parametro", "")).strip()
            fecha_objetivo = param[:10] if param and re.match(r"^20\d{2}-\d{2}-\d{2}", param) else ahora.strftime("%Y-%m-%d")
            await mostrar_diario_fecha(update.message if update.message else update.callback_query, user_id, fecha_objetivo)
            return

        elif tipo == "RECHAZO":
            msg_rechazado = traducciones.get("07_bot_audio_rechazado", "⚠️ El audio no corresponde a un registro nutricional o comando válido.")
            await msg.edit_text(msg_rechazado)
            return

        # Seguro para garantizar formato: "XX min detalle completo" en Actividades
        if tipo == "ACTIVIDAD" and data.get("items"):
            for item in data["items"]:
                alim = str(item.get("alimento", "")).strip()
                # Si la IA no empezó con un número o resumió a 1 o 2 palabras, lo armamos desde la transcripción
                if not re.match(r'^\d+', alim) or len(alim.split()) <= 2:
                    m_min = re.search(r'(\d+)\s*(?:minutos|minuto|min|m\b|horas|hora|hs|h\b)', transcription, re.IGNORECASE)
                    if m_min:
                        num_val = int(m_min.group(1))
                        if 'hora' in m_min.group(0).lower() or 'h' in m_min.group(0).lower():
                            num_val *= 60
                        # Quitamos la frase del tiempo del medio para pasarla adelante limpia
                        resto = (transcription[:m_min.start()] + transcription[m_min.end():]).strip()
                        resto = re.sub(r'\b(de|por|durante)\s*$', '', transcription[:m_min.start()], flags=re.IGNORECASE).strip() + " " + re.sub(r'^\s*(de|por|durante)\b', '', transcription[m_min.end():], flags=re.IGNORECASE).strip()
                        resto = re.sub(r'\s+', ' ', resto).strip()
                        item["alimento"] = f"{num_val} min {resto}" if resto else f"{num_val} min {alim}"

        await procesar_y_mostrar_confirmacion(data, msg, context)

    except Exception as e:
        logger.error(f"Error al procesar audio: {e}")
        txt_err = traducciones.get("07_bot_error_procesar_audio", "❌ Error al procesar audio: {e}").format(e=e)
        try: await msg.edit_text(txt_err)
        except Exception: pass
                    
# =====================================================================================================================================
#                FINAL                               COMANDOS COMIDA COMANDOS ACTIVIDAD                           FINAL
# ======================================================================================================================================

# =============================================================================================================================================
#                INICIO                            COMANDOS FACTURACION                             INICIO 
# =============================================================================================================================================

async def facturar_saldo_del_mes(context: ContextTypes.DEFAULT_TYPE, user_id: int, dias_restantes: int, estrellas_prorrateadas: int):
    """
    Emite una factura prorrateada el día 20 para los usuarios que no cumplieron 
    con el mínimo de registros y pasaron a Estado 3.
    """
    try:
        lang = obtener_idioma_usuario(user_id) or 'es'
        traducciones = obtener_traducciones_db(lang) or {}

        titulo_factura = traducciones.get("10_factura_rescate_titulo", "Regularización de Cuenta")
        desc_tpl = traducciones.get("10_factura_rescate_desc", "Abono proporcional correspondiente a los {dias_restantes} días restantes del mes en curso.")
        item_desc_tpl = traducciones.get("10_factura_rescate_item", "Activación prorrateada ({dias_restantes} días)")

        descripcion_item = item_desc_tpl.format(dias_restantes=dias_restantes)
        precios = [LabeledPrice(descripcion_item, estrellas_prorrateadas)]
        
        payload_transaccion = f"rescate_mensual_{user_id}"

        await context.bot.send_invoice(
            chat_id=int(user_id),
            title=titulo_factura,
            description=desc_tpl.format(dias_restantes=dias_restantes),
            payload=payload_transaccion,
            provider_token="",
            currency="XTR",
            prices=precios,
            start_parameter="rescate_prorrateo"
        )
        logger.info(f"Factura prorrateada del día 20 enviada con éxito al usuario {user_id} por {estrellas_prorrateadas} estrellas.")
    except Exception as e:
        logger.error(f"Error al enviar la factura prorrateada al usuario {user_id}: {e}")
        
async def rutina_nocturna_revision(context: ContextTypes.DEFAULT_TYPE):
    """
    Se ejecuta de madrugada. Revisa inactividad (strikes) y manda avisos de pesaje.
    """
    ahora = obtener_ahora_arg()
    hoy_str = ahora.strftime("%Y-%m-%d")
    dia_actual = ahora.day

    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        cur.execute('SELECT "User ID", "Estado", "dias_inactivo" FROM "Usuarios" WHERE "Estado" NOT IN (\'3\', \'inactivo\', \'baja\')')
        usuarios_activos = cur.fetchall()
        cur.close()
        conn.close()

        for usr in usuarios_activos:
            user_id = str(usr[0]).split('.')[0].strip()
            estado_actual = str(usr[1])
            dias_inact = int(usr[2] if usr[2] is not None else 0)

            u_lang = obtener_idioma_usuario(int(user_id)) or 'es'
            u_trad = obtener_traducciones_db(u_lang) or {}

            # 1. VERIFICACIÓN DE CARGAS (Sistema de Strikes) en la tabla real de ingestas
            cargo_hoy = False
            try:
                conn_u, cur_u = _asegurar_tabla_y_conectar(f"User_{user_id}", tipo_tabla="comida")
                cur_u.execute(f'SELECT COUNT(*) FROM "User_{user_id}" WHERE "Fecha" = %s', (hoy_str,))
                if cur_u.fetchone()[0] > 0:
                    cargo_hoy = True
                cur_u.close()
                conn_u.close()
            except Exception:
                pass 

            conn_u, cur_u = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
            if cargo_hoy:
                cur_u.execute('UPDATE "Usuarios" SET "dias_inactivo" = 0 WHERE "User ID" = %s', (user_id,))
            else:
                dias_inact += 1
                cur_u.execute('UPDATE "Usuarios" SET "dias_inactivo" = %s WHERE "User ID" = %s', (dias_inact, user_id))
                
                # Strike 1
                if dias_inact == 1:
                    msg_s1 = u_trad.get("10_strike_1", "⚠️ **Aviso de sistema:** Notamos que hoy no registraste comidas. Recordá que el plan requiere carga diaria para mantener la cuenta activa.")
                    await context.bot.send_message(chat_id=int(user_id), text=msg_s1, parse_mode="Markdown")
                # Strike 2
                elif dias_inact == 2:
                    msg_s2 = u_trad.get("10_strike_2", "⏳ **Último aviso:** Llevás 2 días sin registrar. Si mañana no se detecta actividad, tu cuenta pasará a estado suspendido.")
                    await context.bot.send_message(chat_id=int(user_id), text=msg_s2, parse_mode="Markdown")

                # Strike 3 (Guillotina)
                elif dias_inact >= 3:
                    cur_u.execute('UPDATE "Usuarios" SET "Estado" = %s WHERE "User ID" = %s', ('3', user_id))
                    msg_s3 = u_trad.get("10_strike_3", "❌ **Cuenta suspendida** por falta de registro consecutivo.\n\nEscribí cualquier comando (ej: `/dia`) para ver las opciones de reactivación.").replace('\\n', '\n')
                    await context.bot.send_message(chat_id=int(user_id), text=msg_s3, parse_mode="Markdown")

            conn_u.commit()
            cur_u.close()
            conn_u.close()

            # 2. RECORDATORIOS DE PESAJE (Regla de las 3 Ventanas)
            if dia_actual == 15 and estado_actual != '3':
                msg_peso_15 = u_trad.get("10_aviso_peso_15", "⚖️ **Control Quincenal Habilitado**\n\nYa podés ingresar tu control de peso de mitad de mes para calibrar tu metabolismo.\n👉 Escribí `/peso [tu_peso]` (ej: `/peso 85`).").replace('\\n', '\n')
                await context.bot.send_message(chat_id=int(user_id), text=msg_peso_15, parse_mode="Markdown")
            
            elif dia_actual == 26 and estado_actual != '3':
                msg_peso_26 = u_trad.get("10_aviso_peso_26", "⚖️ **Cierre de Mes Habilitado**\n\nSe habilitó el ingreso de tu peso final para cerrar el balance mensual y preparar tu próxima rutina.\n👉 Escribí `/peso [tu_peso]`.").replace('\\n', '\n')
                await context.bot.send_message(chat_id=int(user_id), text=msg_peso_26, parse_mode="Markdown")

        logger.info("Rutina nocturna finalizada con éxito.")
    except Exception as e:
        logger.error(f"Error en rutina nocturna: {e}")

# 1. COMANDO /pagar (Menú dinámico de planes desde Supabase)
# =========================================================================
async def cmd_pagar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra al usuario los planes de pago disponibles de forma dinámica."""
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    try:
        conn, cur = _asegurar_tabla_y_conectar("Planes", tipo_tabla="planes")
        cur.execute('SELECT "plan_id", "descripcion", "estrellas" FROM "Planes" WHERE "activo" = TRUE')
        planes = cur.fetchall()
        cur.close()
        conn.close()

        if not planes:
            msg_sin_planes = traducciones.get("10_pagar_sin_planes", "⚠️ No hay planes de pago disponibles en este momento.")
            await update.message.reply_text(msg_sin_planes)
            return

        keyboard = []
        for plan in planes:
            plan_id, descripcion_db, estrellas = plan[0], plan[1], plan[2]
            nombre_plan = traducciones.get(str(plan_id).strip(), descripcion_db)
            keyboard.append([InlineKeyboardButton(f"{nombre_plan} ({estrellas} ⭐)", callback_data=f"comprar_{plan_id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        msg_titulo = traducciones.get("10_pagar_titulo", "⭐ **Seleccioná el plan con el que deseás abonar o renovar tu suscripción:**")
        await update.message.reply_text(
            msg_titulo,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error al cargar planes dinámicos para /pagar: {e}")
        msg_error = traducciones.get("10_pagar_error_carga", "❌ Ocurrió un error al cargar las opciones de pago.")
        await update.message.reply_text(msg_error)

# 2. MANEJADOR DE BOTONES DE PLANES (Callback Query)
# =========================================================================
async def boton_elegir_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id).strip()
    lang = obtener_idioma_usuario(int(user_id)) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    data = query.data
    
    # Lógica de rescate prorrateado para Estado 3
    if data == "rescate_mensual":
        try:
            conn, cur = _asegurar_tabla_y_conectar("Planes", tipo_tabla="planes")
            cur.execute('SELECT "estrellas" FROM "Planes" WHERE "plan_id" = %s', ('1_mes',))
            plan_base = cur.fetchone()
            cur.close()
            conn.close()

            estrellas_mes = plan_base[0] if plan_base else 250
            
            hoy = datetime.now()
            dias_en_mes = calendar.monthrange(hoy.year, hoy.month)[1]
            dias_restantes = dias_en_mes - hoy.day + 1
            
            estrellas_prorrateo = math.floor((estrellas_mes / dias_en_mes) * dias_restantes)
            
            item_desc_rescate = traducciones.get("10_rescate_item_desc", "Activación hasta fin de mes ({dias_restantes} días)").format(dias_restantes=dias_restantes)
            precios = [LabeledPrice(item_desc_rescate, estrellas_prorrateo)]
            
            titulo_rescate = traducciones.get("10_rescate_inv_titulo", "Activación de Cuenta")
            desc_rescate = traducciones.get("10_rescate_inv_desc", "Abono prorrateado para habilitar la cuenta hasta el último día del mes actual.")

            await context.bot.send_invoice(
                chat_id=int(user_id),
                title=titulo_rescate,
                description=desc_rescate,
                payload=f"rescate_mensual_{user_id}",
                provider_token="",
                currency="XTR",
                prices=precios,
                start_parameter="rescate"
            )
            msg_gen_fact = traducciones.get("10_rescate_factura_generada", "✅ Se generó la factura por **{estrellas_prorrateo} Estrellas** para reactivar tu cuenta.").format(estrellas_prorrateo=estrellas_prorrateo)
            await query.edit_message_text(msg_gen_fact, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error generando rescate mensual para {user_id}: {e}")
            msg_err_act = traducciones.get("10_rescate_error_act", "❌ Error al procesar la activación.")
            await query.edit_message_text(msg_err_act)
        return

    if not data.startswith("comprar_"):
        return

    plan_id = data.replace("comprar_", "")

    try:
        conn, cur = _asegurar_tabla_y_conectar("Planes", tipo_tabla="planes")
        cur.execute('SELECT "descripcion", "estrellas" FROM "Planes" WHERE "plan_id" = %s', (plan_id,))
        plan = cur.fetchone()
        cur.close()
        conn.close()

        if not plan:
            msg_no_disp = traducciones.get("10_pagar_plan_no_disp", "❌ El plan seleccionado ya no está disponible.")
            await query.edit_message_text(msg_no_disp)
            return

        descripcion_db, estrellas = plan[0], plan[1]
        descripcion = traducciones.get(str(plan_id).strip(), descripcion_db)

        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        cur.execute('UPDATE "Usuarios" SET "plan_preferido" = %s WHERE "User ID" = %s', (plan_id, user_id))
        conn.commit()
        cur.close()
        conn.close()

        precios = [LabeledPrice(descripcion, estrellas)]
        payload_transaccion = f"pago_{plan_id}_{user_id}"

        desc_factura_tpl = traducciones.get("10_pagar_factura_desc", "Suscripción - {descripcion}")
        await context.bot.send_invoice(
            chat_id=int(user_id),
            title=descripcion,
            description=desc_factura_tpl.format(descripcion=descripcion),
            payload=payload_transaccion,
            provider_token="",
            currency="XTR",
            prices=precios,
            start_parameter=f"pay_{plan_id}"
        )
        
        msg_enviado_tpl = traducciones.get("10_pagar_enviado", "✅ Has seleccionado: **{descripcion} ({estrellas} Estrellas)**.\nTe hemos enviado la factura para abonar en el chat.")
        await query.edit_message_text(msg_enviado_tpl.format(descripcion=descripcion, estrellas=estrellas).replace('\\n', '\n'), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error procesando la selección de plan para el usuario {user_id}: {e}")
        msg_err_proc = traducciones.get("10_pagar_error_proc", "❌ Ocurrió un error al procesar tu selección.")
        await query.edit_message_text(msg_err_proc)

# 3. COMANDO ADMINISTRATIVO /cobrar (Cobro Manual por ID y Estrellas)
# =========================================================================
async def cmd_forzar_cobro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando administrativo para emitir un cobro manual por cantidad de estrellas.
    Uso: /cobrar <user_id> <estrellas>
    """
    user_actual = update.effective_user.id
    lang = obtener_idioma_usuario(user_actual) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    if not es_administrador(user_actual):
        msg_no_perm = traducciones.get("10_cobrar_no_perm", "❌ No tenés permisos para ejecutar este comando.")
        await update.message.reply_text(msg_no_perm)
        return

    if not context.args or len(context.args) < 2:
        msg_uso_inc = traducciones.get(
            "10_cobrar_uso_incorrecto",
            "⚠️ Uso incorrecto.\nUso correcto: `/cobrar <user_id> <estrellas>`"
        )
        await update.message.reply_text(msg_uso_inc, parse_mode="Markdown")
        return

    target_user_id = context.args[0].strip()
    try:
        cantidad_estrellas = int(context.args[1].strip())
    except ValueError:
        msg_num_inv = traducciones.get("10_cobrar_num_invalido", "❌ La cantidad de estrellas debe ser un número entero válido.")
        await update.message.reply_text(msg_num_inv)
        return

    titulo_manual_tpl = traducciones.get("10_cobrar_titulo_manual", "Pago Especial / Manual ({cantidad_estrellas} Estrellas)")
    precios = [LabeledPrice(titulo_manual_tpl.format(cantidad_estrellas=cantidad_estrellas), cantidad_estrellas)]
    payload_transaccion = f"pago_manual_{target_user_id}"

    try:
        msg_aviso_adm = traducciones.get("10_cobrar_aviso_adm", "🔔 **Aviso de Facturación Administrativa:** Se ha generado una solicitud de pago especial:")
        await context.bot.send_message(chat_id=int(target_user_id), text=msg_aviso_adm, parse_mode="Markdown")
        
        desc_manual = traducciones.get("10_cobrar_desc_manual", "Factura administrativa personalizada.")
        await context.bot.send_invoice(
            chat_id=int(target_user_id),
            title=traducciones.get("10_cobrar_titulo_factura", "Pago Especial / Manual"),
            description=desc_manual,
            payload=payload_transaccion,
            provider_token="",
            currency="XTR",
            prices=precios,
            start_parameter="manual_pago"
        )
        
        msg_exito_adm_tpl = traducciones.get("10_cobrar_exito_adm", "✅ Factura manual por `{cantidad_estrellas}` estrellas enviada con éxito al usuario `{target_user_id}`.")
        await update.message.reply_text(msg_exito_adm_tpl.format(cantidad_estrellas=cantidad_estrellas, target_user_id=target_user_id))

    except Exception as e:
        logger.error(f"Error al enviar factura manual al usuario {target_user_id}: {e}")
        msg_err_envio_tpl = traducciones.get("10_cobrar_error_envio", "❌ Error al enviar la factura: {e}")
        await update.message.reply_text(msg_err_envio_tpl.format(e=e))

# 4. PRE-CHECKOUT Y SUCCESSFUL PAYMENT HANDLERS
# =========================================================================
async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    user_id = str(update.effective_user.id).strip()
    lang = obtener_idioma_usuario(int(user_id)) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    payload = payment.invoice_payload
    total_estrellas_pagadas = payment.total_amount

    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")

        # Lógica del pago de rescate prorrateado
        if payload.startswith("rescate_mensual_"):
            hoy = datetime.now().date()
            ultimo_dia_mes = calendar.monthrange(hoy.year, hoy.month)[1]
            nuevo_vencimiento = hoy.replace(day=ultimo_dia_mes).strftime("%Y-%m-%d")

            cur.execute(
                'UPDATE "Usuarios" SET "vencimiento_suscripcion" = %s, "Estado" = %s WHERE "User ID" = %s',
                (nuevo_vencimiento, "10", user_id)
            )
            conn.commit()
            cur.close()
            conn.close()

            msg_rescate_exito = traducciones.get(
                "10_pago_exito_rescate",
                "⭐ **¡Cuenta reactivada con éxito!**\n\nTu acceso ha sido restaurado y tu ciclo de facturación se ha ajustado para el {nuevo_vencimiento}.\nYa podés seguir utilizando todos los comandos."
            ).format(nuevo_vencimiento=nuevo_vencimiento).replace('\\n', '\n')

            await update.message.reply_text(msg_rescate_exito, parse_mode="Markdown")
            return

        # Lógica de pago manual
        if "pago_manual" in payload:
            cur.execute(
                'UPDATE "Usuarios" SET "saldo_estrellas" = COALESCE("saldo_estrellas", 0) + %s WHERE "User ID" = %s',
                (total_estrellas_pagadas, user_id)
            )
            conn.commit()
            cur.close()
            conn.close()

            msg_pago_exito_tpl = traducciones.get(
                "10_pago_exito_manual",
                "⭐ **¡Pago recibido con éxito!**\n\nSe han acreditado `{total_estrellas_pagadas}` estrellas a tu saldo."
            )
            await update.message.reply_text(msg_pago_exito_tpl.format(total_estrellas_pagadas=total_estrellas_pagadas).replace('\\n', '\n'), parse_mode="Markdown")

            return

        # Lógica de Planes regulares
        plan_id = payload.replace("pago_", "").rsplit("_", 1)[0]

        conn_p, cur_p = _asegurar_tabla_y_conectar("Planes", tipo_tabla="planes")
        # ¡CAMBIO CLAVE! Ahora leemos "meses" en lugar de "dias"
        cur_p.execute('SELECT "meses" FROM "Planes" WHERE "plan_id" = %s', (plan_id,))
        resultado_plan = cur_p.fetchone()
        cur_p.close()
        conn_p.close()

        # Si por algún motivo no encuentra el plan, asumimos 1 mes por defecto
        meses_a_sumar = int(resultado_plan[0]) if resultado_plan else 1
        hoy = datetime.now().date()
        
        # ¡LA MAGIA DE RELATIVEDELTA! Suma meses reales, cayendo en el día exacto de vencimiento
        nuevo_vencimiento = (hoy + relativedelta(months=meses_a_sumar)).strftime("%Y-%m-%d")

        cur.execute(
            'UPDATE "Usuarios" SET "vencimiento_suscripcion" = %s, "plan_preferido" = NULL, "Estado" = %s WHERE "User ID" = %s',
            (nuevo_vencimiento, "10", user_id)
        )
        conn.commit()
        cur.close()
        conn.close()

        msg_renov_exito_tpl = traducciones.get(
            "10_pago_exito_plan",
            "⭐ **¡Suscripción renovada con éxito!**\n\nTu acceso se encuentra activo hasta el **{nuevo_vencimiento}**."
        )
        await update.message.reply_text(msg_renov_exito_tpl.format(nuevo_vencimiento=nuevo_vencimiento).replace('\\n', '\n'), parse_mode="Markdown")
        logger.info(f"✅ Suscripción actualizada para usuario {user_id} mediante plan {plan_id} hasta {nuevo_vencimiento}.")

    except Exception as e:
        logger.error(f"❌ Error al procesar pago exitoso para {user_id}: {e}")
        msg_err_pago = traducciones.get("10_pago_error_ficha", "⚠️ El pago se realizó pero hubo un error al actualizar tu ficha.")
        await update.message.reply_text(msg_err_pago)
# 5. PROCESO MASIVO DE FACTURACIÓN AUTOMÁTICA
# =========================================================================
async def proceso_masivo_cobros(context: ContextTypes.DEFAULT_TYPE):
    """Proceso periódico que emite facturas considerando el plan preferido o 1 mes por defecto."""
    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        cur.execute('SELECT "User ID", "plan_preferido" FROM "Usuarios"')
        usuarios = cur.fetchall()
        
        conn_p, cur_p = _asegurar_tabla_y_conectar("Planes", tipo_tabla="planes")
        cur_p.execute('SELECT "plan_id", "descripcion", "estrellas" FROM "Planes"')
        planes_dict = {row[0]: {"descripcion": row[1], "estrellas": row[2]} for row in cur_p.fetchall()}
        cur_p.close()
        conn_p.close()

        for user in usuarios:
            user_id, plan_preferido = user[0], user[1]
            
            u_lang = obtener_idioma_usuario(int(str(user_id).split('.')[0].strip())) or 'es'
            u_trad = obtener_traducciones_db(u_lang) or {}

            plan_a_facturar = plan_preferido if plan_preferido in planes_dict else "1_mes"
            datos_plan = planes_dict.get(plan_a_facturar, planes_dict.get("1_mes"))

            if not datos_plan:
                continue

            descripcion_db = datos_plan["descripcion"]
            estrellas = datos_plan["estrellas"]
            descripcion_plan = u_trad.get(str(plan_a_facturar).strip(), descripcion_db)

            precios = [LabeledPrice(descripcion_plan, estrellas)]
            payload_transaccion = f"pago_{plan_a_facturar}_{user_id}"

            desc_auto_tpl = u_trad.get("10_factura_auto_desc", "Renovación automática - {descripcion}")
            try:
                await context.bot.send_invoice(
                    chat_id=int(str(user_id).split('.')[0].strip()),
                    title=descripcion_plan,
                    description=desc_auto_tpl.format(descripcion=descripcion_plan),
                    payload=payload_transaccion,
                    provider_token="",
                    currency="XTR",
                    prices=precios,
                    start_parameter=f"auto_{plan_a_facturar}"
                )
                logger.info(f"Factura automática enviada a {user_id} por plan {plan_a_facturar}")
            except Exception as ex:
                logger.error(f"No se pudo enviar factura automática a {user_id}: {ex}")
                
            await asyncio.sleep(2)

        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error en el proceso masivo de cobros: {e}")
        
# =============================================================================================================================================
#                FINAL                            COMANDOS FACTURACION                             FINAL 
# =============================================================================================================================================

# ======================================================================================================================================
#                   INICIO                                    COMANDOS INFORMES                                   INICIO  DB OK
# =====================================================================================================================================
#                       INICIO                         COMANDO START                          INICIO  
# =========================================================================================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    msg = traducciones.get('09_start_mensaje_bienvenida', 
        "👋 *¡Bienvenido a tu Bot Nutricional Personalizado!*\n\n"
        "Guía rápida de comandos e ingresos disponibles:\n\n"
        "📌 *Comandos Principales:*\n"
        "• `/alta`: Apertura de cuenta ingresando los datos.\n"
        "• `/barra`: Ingresa por código de barras un comestible.\n"
        "• `/borracomida`: Borra una comida de la Planilla.\n"
        "• `/comidas`: Planilla de comidas precargadas y PDF.\n"
        "• `/diario`: Ingestas seleccionando por teclado y PDF.\n"
        "• `/eliminar`: Borra ingestas y actividades.\n"
        "• `/GET`: Actualiza GET por reloj inteligente .\n"
        "• `/inicio`: Resumen de comandos y manual en PDF.\n"
        "• `/pago`: Elegir el plan o promoción de pago vigente.\n"
        "• `/perfil`: Actualización de datos biométricos.\n"
        "• `/peso`: Registro o control de peso mensual \n"
        "• `/presi`: Registro y consulta de presión arterial.\n"
        "• `/receta`: Calculadora Web para registrar comidas.\n"
        "• `/resumen`: Reporte mensual de calorías y PDF .\n"
        "• `/semana`: Estadística semanal (calorías, fibras, etc.).\n\n"
        "• `/x`: Cancelar comando.\n\n"
        "📌 *Métodos de Registro y consultas directas:*\n"
        "• *Ingestas con IA:*  📝 Texto, 🎤 Audio, 📸 Foto.\n"
        "• *Ingestas con IA:*  📸 Foto de un código de barras\n"
        "• *Ingestas sin IA:*  📝 Planilla precargada *COMIDA.\n"
        "• *Presión arterial:* 📸 Foto del tensiómetro digital\n"
        "• *Actividad física:* 📝 Texto o 🎤 Audio.\n"
        "• *Resumen diario:*   🎤 Audio: Consumos del dia 5. \n"
        "• *Resumen semanal:*  🎤 Audio: Detalle de la semana \n"
        "• *Resumen mensual:*  🎤 Audio: resumen de agosto. \n\n"
    )
    
    texto_final = msg.replace('<br>', '\n').replace('\\n', '\n')
    texto_final = re.sub(r'\n{2,}', '\n\n', texto_final)
    
    btn_manual_txt = traducciones.get('09_btn_descargar_manual', "📄 Descargar Manual Completo en PDF")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_manual_txt, callback_data=f"descargar_manual_user_{lang}")]
    ])
    
    try:
        await update.message.reply_text(texto_final, reply_markup=keyboard, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error de formato Markdown en /start: {e}")
        await update.message.reply_text(texto_final, reply_markup=keyboard)
        
async def callback_descargar_manual_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    lang_code = query.data.replace("descargar_manual_user_", "").strip().upper()
    pdf_filename = f"{lang_code}.pdf"
    
    if not os.path.exists(pdf_filename):
        pdf_filename = "ES.pdf"
        
    try:
        if os.path.exists(pdf_filename):
            txt_caption = traducciones.get("09_manual_usuario_caption", "📄 **Manual de Usuario**")
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=open(pdf_filename, 'rb'),
                filename=pdf_filename,
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

#                   INICIO                                    COMANDO DIA COMNADO DIARIO                            INICIO  DB OK
# =====================================================================================================================================

@requiere_registro
async def cmd_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Manejador del comando /diario.
    Permite argumento para ir a un día directo del mes actual (ej: /diario 5).
    Muestra el menú de selección de fecha con formato Día/Mes (DD/MM).
    """
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    if context.args:
        dia_str = context.args[0]
        if dia_str.isdigit():
            dia_int = int(dia_str)
            ahora = obtener_ahora_arg()
            if 1 <= dia_int <= ahora.day:
                fecha_str = f"{ahora.year}-{ahora.month:02d}-{dia_int:02d}"
                await mostrar_diario_fecha(update, user_id, fecha_str)
                return

    hoy_label = obtener_ahora_arg().strftime("%d/%m")
    ayer_label = (obtener_ahora_arg() - timedelta(days=1)).strftime("%d/%m")
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"📅 {hoy_label}", callback_data="diario_hoy"), 
            InlineKeyboardButton(f"📆 {ayer_label}", callback_data="diario_ayer")
        ],
        [
            InlineKeyboardButton("🔄 📅", callback_data="diario_otro")
        ]
    ])
    
    texto_titulo = traducciones.get("08_inf_diario_titulo", "📅 **Consulta de Diario:** Seleccioná qué día querés revisar:")
    
    await update.message.reply_text(
        texto_titulo, 
        reply_markup=keyboard, 
        parse_mode="Markdown"
    )
    
async def mostrar_diario_fecha(update_or_query, user_id, fecha_str):
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    try:
        df = obtener_datos_usuario(user_id)
        df_diario = df[df['Fecha'].astype(str).str.strip() == str(fecha_str).strip()] if not df.empty and 'Fecha' in df.columns else pd.DataFrame()

        if df_diario.empty:
            msg_no_reg = traducciones.get("08_inf_diario_no_reg", "⚠️ No se encontraron registros de ingestas para la fecha `{fecha_str}`.")
            texto = msg_no_reg.format(fecha_str=fecha_str)
            reply_markup = None
        else:
            msg_reg_dia_tpl = traducciones.get("08_inf_diario_reg_dia", "📅 Registro del día {fecha_str}:\n\n")
            texto = msg_reg_dia_tpl.format(fecha_str=fecha_str)
            
            agrupado = {}
            for _, r in df_diario.iterrows():
                momento = str(r.get('Momento', '')).strip().capitalize()
                alimento = str(r.get('Alimento', '')).strip()
                
                if momento not in agrupado:
                    agrupado[momento] = []
                if alimento:
                    agrupado[momento].append(alimento)

            orden_momentos = [
                ("Desayuno", traducciones.get("08_inf_diario_momento_desayuno", "Desayuno")),
                ("Almuerzo", traducciones.get("08_inf_diario_momento_almuerzo", "Almuerzo")),
                ("Merienda", traducciones.get("08_inf_diario_momento_merienda", "Merienda")),
                ("Cena", traducciones.get("08_inf_diario_momento_cena", "Cena")),
                ("Actividad", traducciones.get("08_inf_diario_momento_actividad", "Actividad Física"))
            ]

            for clave_ingles, etiqueta_mostrada in orden_momentos:
                items_encontrados = []
                for k_momento, lista_alimentos in agrupado.items():
                    if clave_ingles.lower() in k_momento.lower():
                        items_encontrados.extend(lista_alimentos)
                
                if items_encontrados:
                    items_str = ", ".join(items_encontrados)
                    texto += f"• {etiqueta_mostrada}: {items_str}\n"

            c_cons = df_diario[df_diario['Calorias'] > 0]['Calorias'].sum()
            c_quem = abs(df_diario[df_diario['Calorias'] < 0]['Calorias'].sum())
            b_neto = c_cons - c_quem
            
            p_tot = df_diario[df_diario['Calorias'] > 0]['Proteinas'].sum()
            g_tot = df_diario[df_diario['Calorias'] > 0]['Grasas'].sum()
            cb_tot = df_diario[df_diario['Calorias'] > 0]['Carbohidratos'].sum()
            f_tot = df_diario[df_diario['Calorias'] > 0]['Fibras'].sum()

            lbl_cons = traducciones.get("08_inf_diario_consumidas", "🔥 Consumidas:")
            lbl_quem = traducciones.get("08_inf_diario_quemadas", "⚡ Quemadas:")
            lbl_bal = traducciones.get("08_inf_diario_balance", "⚖️ Balance Neto:")
            
            texto += f"\n{lbl_cons} {c_cons:.1f} kcal\n"
            texto += f"{lbl_quem} {c_quem:.1f} kcal\n"
            texto += f"{lbl_bal} {b_neto:.1f} kcal\n\n"
            
            template_macros = traducciones.get("08_inf_diario_macronutrientes", "🥩 Prot: {p_tot:.1f}g | 🥑 Gras: {g_tot:.1f}g | 🍞 Carb: {cb_tot:.1f}g | 🌾 Fibr: {f_tot:.1f}g")
            texto += template_macros.format(p_tot=p_tot, g_tot=g_tot, cb_tot=cb_tot, f_tot=f_tot)

            btn_pdf_text = traducciones.get("08_inf_diario_btn_pdf", "📄 Descargar PDF")
            keyboard = [[InlineKeyboardButton(btn_pdf_text, callback_data=f"descargar_pdf_diario_{fecha_str}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

        texto = texto.replace('\\n', '\n')

        if hasattr(update_or_query, 'edit_message_text'):
            try:
                await update_or_query.edit_message_text(texto, reply_markup=reply_markup, parse_mode="Markdown")
            except Exception as ex:
                if "Message is not modified" not in str(ex):
                    await update_or_query.message.reply_text(texto, reply_markup=reply_markup, parse_mode="Markdown")
        elif hasattr(update_or_query, 'reply_text'):
            await update_or_query.reply_text(texto, reply_markup=reply_markup, parse_mode="Markdown")
        elif hasattr(update_or_query, 'message') and update_or_query.message:
            await update_or_query.message.reply_text(texto, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        if "Message is not modified" in str(e):
            return
            
        msg_err_tmpl = traducciones.get("08_inf_diario_error", "❌ Error al consultar el diario para la fecha `{fecha_str}`: {e}")
        msg_err = msg_err_tmpl.format(fecha_str=fecha_str, e=e).replace('\\n', '\n')
        
        if hasattr(update_or_query, 'edit_message_text'):
            try:
                await update_or_query.edit_message_text(msg_err, parse_mode="Markdown")
            except Exception:
                pass
        elif hasattr(update_or_query, 'reply_text'):
            await update_or_query.reply_text(msg_err, parse_mode="Markdown")
        elif hasattr(update_or_query, 'message') and update_or_query.message:
            await update_or_query.message.reply_text(msg_err, parse_mode="Markdown")


def generar_pdf_diario_bytes(fecha_str, df_diario, user_id):
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1E3A8A'), spaceAfter=4)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor('#1E293B'))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8.5, leading=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)

    t_titulo_tmpl = traducciones.get("08_PDF_diario_titulo", "Detalle Diario de Ingestas - {fecha_str}")
    t_usr_tmpl = traducciones.get("08_PDF_diario_usuario_id", "**Usuario Telegram ID:** {user_id}")
    
    story = [
        Paragraph(f"<b>{t_titulo_tmpl.format(fecha_str=fecha_str)}</b>", title_style),
        Paragraph(t_usr_tmpl.format(user_id=user_id), body_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=10)
    ]

    if df_diario.empty:
        msg_vacio = traducciones.get("08_PDF_diario_sin_reg", "No hay registros para esta fecha.")
        story.append(Paragraph(msg_vacio, body_style))
    else:
        th_momento = traducciones.get("08_PDF_diario_th_momento", "Momento")
        th_alimento = traducciones.get("08_PDF_diario_th_alimento", "Alimento / Detalle")
        th_peso = traducciones.get("08_PDF_diario_th_peso", "Peso")
        th_kcal = traducciones.get("08_PDF_diario_th_kcal", "Kcal")
        th_prot = traducciones.get("08_PDF_diario_th_prot", "Prot")
        th_gras = traducciones.get("08_PDF_diario_th_gras", "Gras")
        th_carb = traducciones.get("08_PDF_diario_th_carb", "Carb")
        th_fibr = traducciones.get("08_PDF_diario_th_fibr", "Fibr")

        table_data = [[
            Paragraph(th_momento, header_style),
            Paragraph(th_alimento, header_style),
            Paragraph(th_peso, header_style),
            Paragraph(th_kcal, header_style),
            Paragraph(th_prot, header_style),
            Paragraph(th_gras, header_style),
            Paragraph(th_carb, header_style),
            Paragraph(th_fibr, header_style)
        ]]

        mapa_momentos = {
            "desayuno": traducciones.get("08_inf_diario_momento_desayuno", "Desayuno"),
            "almuerzo": traducciones.get("08_inf_diario_momento_almuerzo", "Almuerzo"),
            "merienda": traducciones.get("08_inf_diario_momento_merienda", "Merienda"),
            "cena": traducciones.get("08_inf_diario_momento_cena", "Cena"),
            "actividad": traducciones.get("08_inf_diario_momento_actividad", "Actividad Física")
        }

        def obtener_orden_momento(momento_val):
            m_str = str(momento_val).strip().lower()
            if "desayuno" in m_str: return 1
            if "almuerzo" in m_str: return 2
            if "merienda" in m_str: return 3
            if "cena" in m_str: return 4
            return 5

        df_diario = df_diario.copy()
        df_diario['orden_temp'] = df_diario['Momento'].apply(obtener_orden_momento)
        df_ordenado = df_diario.sort_values('orden_temp')

        for _, r in df_ordenado.iterrows():
            momento_raw = str(r.get('Momento', '')).strip().lower()
            momento_traducido = momento_raw.capitalize()
            for k, v in mapa_momentos.items():
                if k in momento_raw:
                    momento_traducido = v
                    break

            table_data.append([
                Paragraph(momento_traducido, body_style),
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

        tot_cons_tpl = traducciones.get("08_PDF_diario_tot_consumidas", "• <b>Total Consumidas:</b> {c_cons:.1f} kcal")
        tot_quem_tpl = traducciones.get("08_PDF_diario_tot_quemadas", "• <b>Total Quemadas:</b> {c_quem:.1f} kcal")
        bal_neto_tpl = traducciones.get("08_PDF_diario_balance_neto", "• <b>Balance Neto:</b> {b_neto:.1f} kcal")

        story.append(Paragraph(tot_cons_tpl.format(c_cons=c_cons), body_style))
        story.append(Paragraph(tot_quem_tpl.format(c_quem=c_quem), body_style))
        story.append(Paragraph(bal_neto_tpl.format(b_neto=b_neto), body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer
    
async def generar_y_enviar_pdf_diario_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    txt_alerta = traducciones.get("08_pdf_diario_generando_alerta", "Generando PDF del día... ⏳")
    await query.answer(txt_alerta)
    
    cb_data = query.data
    fecha_str = cb_data.replace("descargar_pdf_diario_", "").strip()
    
    df = obtener_datos_usuario(user_id)
    df_diario = df[df['Fecha'].astype(str).str.strip() == str(fecha_str).strip()] if not df.empty and 'Fecha' in df.columns else pd.DataFrame()
    pdf_buffer = generar_pdf_diario_bytes(fecha_str, df_diario, user_id)
    
    txt_caption = traducciones.get("08_pdf_diario_caption", "📄 Detalle Diario de Ingestas - {fecha_str}").format(fecha_str=fecha_str)
    
    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=pdf_buffer,
        filename=f"Diario_{fecha_str}.pdf",
        caption=txt_caption,
        parse_mode="Markdown"
    )
    
#                 INICIO                            COMANDO SEMANA                             INICIO   DB OK
# ======================================================================================================================================

def _generar_texto_resumen_semanal(user_id, inicio_rango, fin_rango, etiqueta_periodo):
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    df_datos = obtener_datos_usuario(user_id) 

    if df_datos.empty or 'Fecha' not in df_datos.columns:
        return None, None

    df_datos['Fecha_dt'] = pd.to_datetime(df_datos['Fecha'], errors='coerce').dt.date
    df_semana = df_datos[(df_datos['Fecha_dt'] >= inicio_rango) & (df_datos['Fecha_dt'] <= fin_rango)].copy()

    if df_semana.empty:
        return None, None

    mes_target = inicio_rango.strftime("%Y-%m")
    perfil = obtener_perfil_usuario(user_id, mes_target=mes_target) or {}
    m = calcular_metricas_mensuales(df_semana, perfil) or {}

    peso_act_val = float(m.get('peso_actual', 0))
    peso_ref_val = float(m.get('peso_referencia', 0))
    if 'calcular_rango_actividad_fisica' in globals():
        act_min_val, act_max_val = calcular_rango_actividad_fisica(peso_act_val, peso_ref_val)
    else:
        act_min_val, act_max_val = 30, 60

    dias_efectivos = df_semana['Fecha_dt'].nunique()
    if dias_efectivos <= 0:
        dias_efectivos = 1

    minutos_totales_actividad = 0
    if 'Momento' in df_semana.columns and 'Alimento' in df_semana.columns:
        for _, row in df_semana.iterrows():
            momento_str = str(row.get('Momento', '')).strip().lower()
            alimento_str = str(row.get('Alimento', '')).strip()
            cal_val = float(row.get('Calorias', 0) or 0)
            if cal_val < 0 or 'actividad' in momento_str or 'ejercicio' in momento_str or 'caminata' in momento_str:
                match = re.match(r'^(\d+)', alimento_str)
                if match:
                    minutos_totales_actividad += int(match.group(1))

    prom_minutos_act = int(round(minutos_totales_actividad / dias_efectivos))

    prom_alta, prom_baja = None, None
    try:
        df_presion = obtener_datos_presion_db(user_id) 
        if not df_presion.empty and 'Fecha_Dia' in df_presion.columns:
            df_presion['Fecha_Dia_dt'] = pd.to_datetime(df_presion['Fecha_Dia'], errors='coerce').dt.date
            df_presion_semana = df_presion[
                (df_presion['Fecha_Dia_dt'] >= inicio_rango) & 
                (df_presion['Fecha_Dia_dt'] <= fin_rango)
            ]
            if not df_presion_semana.empty:
                prom_alta = round(df_presion_semana['Alta'].mean())
                prom_baja = round(df_presion_semana['Baja'].mean())
    except Exception as e_presion:
        logger.error(f"Error al calcular presión semanal: {e_presion}")

    t_titulo = traducciones.get("08_inf_semana_titulo", "📅 **Resumen Nutricional Semanal:**")
    t_prom = traducciones.get("08_inf_semana_promedios", "📈 **Promedios vs. Rangos Saludables:**")
   
    val_neto_sem = m.get('prom_bal_neto', m.get('prom_cal', 0) - m.get('prom_quem', 0))
    cal_tpl = traducciones.get("08_inf_semana_calorias", "• Balance Neto: `{prom_cal} kcal` / Rango: `{cal_min} - {cal_max} kcal`").format(prom_cal=val_neto_sem, cal_min=m.get('cal_min', 0), cal_max=m.get('cal_max', 0))   
   
    prot_tpl = traducciones.get("08_inf_semana_proteinas", "• Proteínas: `{prom_prot} g` / Rango: `{prot_min} - {prot_max} g`").format(prom_prot=m.get('prom_prot', 0), prot_min=m.get('prot_min', 0), prot_max=m.get('prot_max', 0))
    gras_tpl = traducciones.get("08_inf_semana_grasas", "• Grasas: `{prom_gras} g` / Rango: `{gras_min} - {gras_max} g`").format(prom_gras=m.get('prom_gras', 0), gras_min=m.get('gras_min', 0), gras_max=m.get('gras_max', 0))
    carb_tpl = traducciones.get("08_inf_semana_carbohidratos", "• Carbohidratos: `{prom_carb} g` / Rango: `{carb_min} - {carb_max} g`").format(prom_carb=m.get('prom_carb', 0), carb_min=m.get('carb_min', 0), carb_max=m.get('carb_max', 0))
    fibr_tpl = traducciones.get("08_inf_semana_fibras", "• Fibras: `{prom_fibr} g` / Mínimo: `{fibr_min} g`").format(prom_fibr=m.get('prom_fibr', 0), fibr_min=m.get('fibr_min', 0))
    act_tpl = traducciones.get("08_inf_semana_actividad", "• Actividad Física: `{prom_minutos_act} min/día` / Rango: `{act_min} - {act_max} min/día`").format(prom_minutos_act=prom_minutos_act, act_min=act_min_val, act_max=act_max_val)

    txt = (
        f"{t_titulo}\n"
        f"ℹ️ *{etiqueta_periodo}*\n\n"
        f"{t_prom}\n"
        f"{cal_tpl}\n"
        f"{prot_tpl}\n"
        f"{gras_tpl}\n"
        f"{carb_tpl}\n"
        f"{fibr_tpl}\n"
        f"{act_tpl}\n"
    )
    if prom_alta is not None and prom_baja is not None:
        pres_tpl = traducciones.get("08_inf_semana_presion", "• **Presión Arterial Promedio:** `{prom_alta}/{prom_baja} mmHg`").format(prom_alta=prom_alta, prom_baja=prom_baja)
        txt += f"{pres_tpl}\n"

    quem_tpl = traducciones.get("08_inf_semana_quemadas", "• **Calorías Quemadas (Promedio):** `{prom_quem} kcal/día`").format(prom_quem=m.get('prom_quem', 0))
    dias_tpl = traducciones.get("08_inf_semana_dias_eval", "• **Días Evaluados:** `{dias_reg}`").format(dias_reg=m.get('dias_registrados', 0))
    nota_txt = traducciones.get("08_inf_semana_nota", "_(Nota: Los rangos de actividad consideran impacto corporal; actividades como aquagym o natación no aplican restricciones de sobrepeso)._")

    txt += (
        f"\n{quem_tpl}\n"
        f"{dias_tpl}\n\n"
        f"{nota_txt}"
    )

    return txt, m
            
@requiere_registro
async def cmd_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    
    msg_proc = traducciones.get("08_inf_semana_proc", "⏳ Procesando tu estadística semanal...")
    msg_espera = await update.message.reply_text(msg_proc, parse_mode="Markdown")
    
    ahora = obtener_ahora_arg()
    if ahora.weekday() == 0:
        inicio_sem = ahora - timedelta(days=7)
        fin_sem = ahora - timedelta(days=1)
    else:
        inicio_sem = ahora - timedelta(days=ahora.weekday())
        fin_sem = ahora - timedelta(days=1)
        
    inicio_str = inicio_sem.strftime("%Y-%m-%d")
    fin_str = fin_sem.strftime("%Y-%m-%d")

    try:
        df_datos = obtener_datos_usuario(user_id) 
        if df_datos.empty or 'Fecha' not in df_datos.columns:
            msg_sin_dat = traducciones.get("08_inf_semana_sin_dat", "⚠️ No hay datos registrados entre el {inicio_str} y el {fin_str}.").format(inicio_str=inicio_str, fin_str=fin_str)
            await msg_espera.edit_text(msg_sin_dat)
            return
            
        df_sem = df_datos[(df_datos['Fecha'] >= inicio_str) & (df_datos['Fecha'] <= fin_str)]
        dias_validos = df_sem['Fecha'].nunique()
        
        if dias_validos == 0:
            msg_sin_ing = traducciones.get("08_inf_semana_sin_ing", "⚠️ No se encontraron ingestas en el período ({inicio_str} a {fin_str}).").format(inicio_str=inicio_str, fin_str=fin_str)
            await msg_espera.edit_text(msg_sin_ing)
            return

        tot_cal = df_sem[df_sem['Calorias'] > 0]['Calorias'].sum()
        tot_quem = abs(df_sem[df_sem['Calorias'] < 0]['Calorias'].sum())
        
        prom_cal = tot_cal / dias_validos
        prom_quem = tot_quem / dias_validos
        balance = prom_cal - prom_quem

        prom_prot = df_sem['Proteinas'].sum() / dias_validos if 'Proteinas' in df_sem.columns else 0
        prom_gras = df_sem['Grasas'].sum() / dias_validos if 'Grasas' in df_sem.columns else 0
        prom_carb = df_sem['Carbohidratos'].sum() / dias_validos if 'Carbohidratos' in df_sem.columns else 0
        prom_fibr = df_sem['Fibras'].sum() / dias_validos if 'Fibras' in df_sem.columns else 0

        minutos_totales_actividad = 0
        if 'Momento' in df_sem.columns and 'Alimento' in df_sem.columns:
            for _, row in df_sem.iterrows():
                momento_str = str(row.get('Momento', '')).strip().lower()
                alimento_str = str(row.get('Alimento', '')).strip()
                cal_val = float(row.get('Calorias', 0) or 0)
                if cal_val < 0 or 'actividad' in momento_str or 'ejercicio' in momento_str or 'caminata' in momento_str:
                    match = re.match(r'^(\d+)', alimento_str)
                    if match:
                        minutos_totales_actividad += int(match.group(1))

        prom_minutos_act = int(round(minutos_totales_actividad / dias_validos))

        msg_plantilla = traducciones.get(
            "08_inf_semana_plantilla",
            "📊 **Resumen Semanal** ({inicio_str} al {fin_str})\n"
            "🗓️ Días efectivos evaluados: `{dias_validos}`\n\n"
            "🔥 Consumo Promedio: `{prom_cal:.0f} kcal/día`\n"
            "⚡ Quema Promedio: `{prom_quem:.0f} kcal/día`\n"
            "⚖️ Balance Neto Promedio: `{balance:.0f} kcal/día`\n\n"
            "🥩 Proteínas: `{prom_prot:.1f} g/día`\n"
            "🥑 Grasas: `{prom_gras:.1f} g/día`\n"
            "🍞 Carbohidratos: `{prom_carb:.1f} g/día`\n"
            "🌾 Fibras: `{prom_fibr:.1f} g/día`\n"
            "🏃 Actividad Física: `{prom_minutos_act} min/día`\n\n"
            "💡 _Recordá mantener tus registros al día para mayor precisión._"
        )
        
        txt_informe = msg_plantilla.format(
            inicio_str=inicio_str, fin_str=fin_str, dias_validos=dias_validos,
            prom_cal=prom_cal, prom_quem=prom_quem, balance=balance,
            prom_prot=prom_prot, prom_gras=prom_gras, prom_carb=prom_carb,
            prom_fibr=prom_fibr, prom_minutos_act=prom_minutos_act
        )
        
        # Corrección clave para reemplazar los \n en texto plano por saltos reales de Telegram
        txt_informe = txt_informe.replace('\\n', '\n')
        
        await msg_espera.edit_text(txt_informe, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en resumen semanal para {user_id}: {e}")
        msg_err_proc = traducciones.get("08_inf_semana_err_proc", "❌ Error al procesar tu resumen semanal.")
        await msg_espera.edit_text(msg_err_proc)        
#               INICIO                                COMANDO RESUMEN COMANDO MES                       INICIO DB OK
# ==========================================================================================================================================

def obtener_mensaje_variacion_peso(cambio_kg: float, traducciones: dict = None) -> str:
    """Devuelve un mensaje cualitativo según la variación de peso mensual estimada."""
    if traducciones is None:
        traducciones = {}

    if abs(cambio_kg) <= 0.8:
        return traducciones.get("08_inf_var_peso_estable", "Prácticamente estable")
    elif 0.8 < cambio_kg <= 1.8:
        return traducciones.get("08_inf_var_peso_peq_arriba", "Pequeña variación hacia arriba")
    elif 1.8 < cambio_kg <= 3.0:
        return traducciones.get("08_inf_var_peso_mod_arriba", "Variación moderada hacia arriba")
    elif cambio_kg > 3.0:
        return traducciones.get("08_inf_var_peso_imp_arriba", "Variación importante hacia arriba")
    elif -1.8 <= cambio_kg < -0.8:
        return traducciones.get("08_inf_var_peso_peq_abajo", "Pequeña variación hacia abajo")
    elif -3.0 <= cambio_kg < -1.8:
        return traducciones.get("08_inf_var_peso_mod_abajo", "Variación moderada hacia abajo")
    else:
        return traducciones.get("08_inf_var_peso_imp_abajo", "Variación importante hacia abajo")
                        
@requiere_registro
async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Manejador del comando /resumen.
    Permite argumento para ir directo a un mes del año actual (ej: /resumen 08).
    """
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    if context.args:
        mes_str = context.args[0]
        if len(mes_str) <= 2 and mes_str.isdigit():
            mes_int = int(mes_str)
            if 1 <= mes_int <= 12:
                ahora = obtener_ahora_arg()
                if mes_int > ahora.month:
                    msg_futuro = traducciones.get("08_inf_mes_futuro", "⚠️ No se puede consultar un mes futuro.")
                    await update.message.reply_text(msg_futuro)
                    return
                mes_formateado = f"{ahora.year}-{mes_int:02d}"
                context.args = [mes_formateado]
                await mostrar_resumen_mes(update, context)
                return

    if not await _validar_peso_mes_actual(update, context):
        return

    ahora = obtener_ahora_arg()
    mes_actual_iso = ahora.strftime("%Y-%m")
    mes_anterior_iso = (ahora.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    
    label_mes_actual = ahora.strftime("%m/%Y")
    label_mes_anterior = (ahora.replace(day=1) - timedelta(days=1)).strftime("%m/%Y")
    
    dia_actual = ahora.day

    if 1 <= dia_actual <= 7:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📅 {label_mes_anterior}", callback_data=f"resumen_mes_{mes_anterior_iso}")],
            [InlineKeyboardButton("🔄 📅", callback_data="resumen_mes_menu_otros")]
        ])
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📅 {label_mes_actual}", callback_data=f"resumen_mes_{mes_actual_iso}")],
            [InlineKeyboardButton(f"📆 {label_mes_anterior}", callback_data=f"resumen_mes_{mes_anterior_iso}")],
            [InlineKeyboardButton("🔄 📅", callback_data="resumen_mes_menu_otros")]
        ])

    texto_titulo = traducciones.get("08_inf_mes_titulo", "📊 **Resumen Mensual:** Seleccioná la opción que querés consultar:")
    await update.message.reply_text(
        texto_titulo, 
        reply_markup=keyboard, 
        parse_mode="Markdown"
    )
        
async def mostrar_resumen_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        user_id = query.from_user.id if query else update.effective_user.id
        lang = obtener_idioma_usuario(user_id) or 'es'
        traducciones = obtener_traducciones_db(lang) or {}

        ahora = obtener_ahora_arg()
        mes_actual_str = ahora.strftime("%Y-%m")
        dia_actual = ahora.day

        mes_str = None
        if query and query.data:
            await query.answer()
            cb_data = query.data

            if cb_data == "resumen_mes_menu_otros":
                botones_meses = []
                primer_dia_mes_actual = ahora.replace(day=1)
                btn_periodo_tmpl = traducciones.get("08_inf_mes_btn_periodo", "🗓️ Período {mes_iter}")
                
                for i in range(1, 7):
                    mes_iter = (primer_dia_mes_actual - pd.DateOffset(months=i)).strftime("%Y-%m")
                    botones_meses.append([InlineKeyboardButton(btn_periodo_tmpl.format(mes_iter=mes_iter), callback_data=f"resumen_mes_{mes_iter}")])
                
                btn_volver = traducciones.get("08_inf_mes_volver", "🔙 Volver")
                botones_meses.append([InlineKeyboardButton(btn_volver, callback_data="resumen_volver_menu")])
                
                texto_sel = traducciones.get("08_inf_mes_seleccion", "🗓️ **Seleccioná el mes que querés consultar:**")
                await query.edit_message_text(
                    texto_sel, 
                    reply_markup=InlineKeyboardMarkup(botones_meses),
                    parse_mode="Markdown"
                )
                return

            elif cb_data == "resumen_volver_menu":
                mes_anterior_iso = (ahora.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
                label_mes_actual = ahora.strftime("%m/%Y")
                label_mes_anterior = (ahora.replace(day=1) - timedelta(days=1)).strftime("%m/%Y")
                
                if 1 <= dia_actual <= 7:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(f"📅 {label_mes_anterior}", callback_data=f"resumen_mes_{mes_anterior_iso}")],
                        [InlineKeyboardButton("🔄 📅", callback_data="resumen_mes_menu_otros")]
                    ])
                else:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(f"📅 {label_mes_actual}", callback_data=f"resumen_mes_{mes_actual_str}")],
                        [InlineKeyboardButton(f"📆 {label_mes_anterior}", callback_data=f"resumen_mes_{mes_anterior_iso}")],
                        [InlineKeyboardButton("🔄 📅", callback_data="resumen_mes_menu_otros")]
                    ])

                texto_titulo = traducciones.get("08_inf_mes_titulo", "📊 **Resumen Mensual:** Seleccioná la opción que querés consultar:")
                await query.edit_message_text(
                    texto_titulo, 
                    reply_markup=keyboard, 
                    parse_mode="Markdown"
                )
                return

            elif cb_data.startswith("resumen_mes_"):
                mes_str = cb_data.replace("resumen_mes_", "")

        elif context.args:
            mes_str = context.args[0]

        if not mes_str:
            mes_str = mes_actual_str

        if mes_str == mes_actual_str and 1 <= dia_actual <= 7:
            msg = traducciones.get("08_inf_mes_actual_restr", "⚠️ No se encuentra disponible el resumen del mes actual durante los primeros 7 días del mes.")
            if query:
                await query.edit_message_text(msg, parse_mode="Markdown")
            else:
                await update.message.reply_text(msg, parse_mode="Markdown")
            return

        if mes_str == mes_actual_str:
            if not await _validar_peso_mes_actual(update, context):
                return

        df_datos = obtener_datos_usuario(user_id) 
        
        if not df_datos.empty and 'Fecha' in df_datos.columns:
            df_datos['Fecha_dt'] = pd.to_datetime(df_datos['Fecha'], errors='coerce')
            hoy_comienzo = pd.Timestamp.now().floor('D')
            
            if mes_str == mes_actual_str:
                df_mes = df_datos[
                    (df_datos['Fecha'].astype(str).str.startswith(mes_str)) & 
                    (df_datos['Fecha_dt'] < hoy_comienzo)
                ].copy()
            else:
                df_mes = df_datos[df_datos['Fecha'].astype(str).str.startswith(mes_str)].copy()
        else:
            df_mes = pd.DataFrame()

        if df_mes.empty:
            msg_tpl = traducciones.get("08_inf_mes_sin_reg", "⚠️ No hay registros cargados para el mes `{mes_str}`.")
            msg = msg_tpl.format(mes_str=mes_str)
            if query:
                await query.edit_message_text(msg, parse_mode="Markdown")
            else:
                await update.message.reply_text(msg, parse_mode="Markdown")
            return

        perfil = obtener_perfil_usuario(user_id, mes_target=mes_str) or {}
        m = calcular_metricas_mensuales(df_mes, perfil, user_id=user_id, mes_str=mes_str)

        peso_act_val = float(m.get('peso_actual', 0))
        peso_ref_val = float(m.get('peso_referencia', 0))
        if 'calcular_rango_actividad_fisica' in globals():
            act_min_val, act_max_val = calcular_rango_actividad_fisica(peso_act_val, peso_ref_val)
        else:
            act_min_val, act_max_val = 30, 60

        def _fmt(val, dec=0):
            try:
                num = float(val)
                return f"{num:.{dec}f}" if dec > 0 else f"{int(round(num))}"
            except (ValueError, TypeError):
                return "0"

        cambio_peso_val = float(m.get('cambio_peso_kg', 0))
        texto_variacion_peso = f"`{obtener_mensaje_variacion_peso(cambio_peso_val, traducciones)}`"

        # --- DEFINIR TEXTO ACLARATORIO ---
        es_personalizado = m.get('valores_personalizados', False)
        id_prof = str(perfil.get('profesional', '123456789')).strip()
        
        if es_personalizado:
            nota_sistema = traducciones.get("08_inf_mes_nota_pers", "👨‍⚕️ _Nota Clínica: Las metas y rangos de macronutrientes de este reporte han sido personalizados, revisados y aprobados por tu profesional a cargo._")
        elif id_prof != "123456789" and id_prof != "S/D" and id_prof != "":
            nota_sistema = traducciones.get("08_inf_mes_nota_prof_pend", "🤖 _Nota del Sistema: Tu profesional aún no ha personalizado las metas de este mes. Los rangos mostrados fueron calculados automáticamente por el motor clínico del bot._")
        else:
            nota_sistema = traducciones.get("08_inf_mes_nota_auto", "🤖 _Nota del Sistema: Reporte generado mediante métricas analíticas directas y algoritmos automatizados._")

        template_enc = traducciones.get(
            "08_inf_mes_reporte_enc",
            "📊 **Reporte Nutricional Mensual ({mes_str}):**\n"
            "⚖️ Peso registrado: `{peso_reg} kg`\n\n"
            "• Consumidas: `{cons} kcal` | Quemadas: `{quem} kcal`\n"
            "• Balance Neto: `{neto} kcal/día`\n"
            "• Variación Est. de Peso: {var_peso} ({dias} días)\n\n"
            "📈 **Promedios vs. Rangos Saludables:**\n"
            "• Balance Neto: `{neto} kcal` / Rango: `{c_min} - {c_max} kcal`\n"
            "• Proteínas: `{prot} g` / Rango: `{p_min} - {p_max} g`\n"
            "• Grasas: `{gras} g` / Rango: `{g_min} - {g_max} g`\n"
            "• Carbs: `{carb} g` / Rango: `{cb_min} - {cb_max} g`\n"
            "• Fibras: `{fibr} g` / Mínimo: `{f_min} g`\n"
            "• Actividad Física: `{act} min/día` / Rango: `{act_min} - {act_max} min/día`\n\n"
            "{nota_sistema}"
        )

        encabezado_txt = template_enc.format(
            mes_str=mes_str,
            peso_reg=_fmt(m.get('peso_actual', 0), 1),
            cons=_fmt(m.get('prom_cal', 0)),
            quem=_fmt(m.get('prom_quem', 0)),
            neto=_fmt(m.get('prom_bal_neto', 0)),
            var_peso=texto_variacion_peso,
            dias=m.get('dias_registrados', 0),
            c_min=m.get('cal_min', 0), c_max=m.get('cal_max', 0),
            prot=_fmt(m.get('prom_prot', 0)),
            p_min=m.get('prot_min', 0), p_max=m.get('prot_max', 0),
            gras=_fmt(m.get('prom_gras', 0)),
            g_min=m.get('gras_min', 0), g_max=m.get('gras_max', 0),
            carb=_fmt(m.get('prom_carb', 0)),
            cb_min=m.get('carb_min', 0), cb_max=m.get('carb_max', 0),
            fibr=_fmt(m.get('prom_fibr', 0)),
            f_min=m.get('fibr_min', 0),
            act=m.get('prom_minutos_act', 0),
            act_min=act_min_val, act_max=act_max_val,
            nota_sistema=nota_sistema  # <--- INYECTAMOS LA NOTA ACÁ
        )

        pie_txt = traducciones.get("08_inf_mes_pie_pdf", "\n\n📄 Podés descargar el informe completo en PDF abajo:")
        
        txt_final = f"{encabezado_txt}{pie_txt}".replace('\\n', '\n')

        btn_pdf_text = traducciones.get("08_inf_mes_btn_descargar", "📄 Descargar PDF Resumen Mensual")
        keyboard = [[InlineKeyboardButton(btn_pdf_text, callback_data=f"descargar_pdf_resumen_{mes_str}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if query:
            await query.edit_message_text(txt_final, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(txt_final, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en mostrar_resumen_mes: {e}", exc_info=True)
        msg_err_tmpl = traducciones.get("08_inf_mes_error_gral", "⚠️ Ocurrió un error al generar el resumen mensual: {e}")
        msg_err = msg_err_tmpl.format(e=e).replace('\\n', '\n')
        if update.callback_query:
            await update.callback_query.edit_message_text(msg_err)
        else:
            await update.message.reply_text(msg_err)
                                            
def generar_pdf_resumen_bytes(mes_str, df_mes, df_presion, perfil, tmb_val, user_id):
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=14, textColor=colors.HexColor('#1E3A8A'), spaceAfter=4)
    sub_style = ParagraphStyle('SubTitle', parent=styles['Heading2'], fontSize=10, textColor=colors.HexColor('#2563EB'), spaceBefore=6, spaceAfter=2)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#1E293B'))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)

    t_titulo_tmpl = traducciones.get("08_PDF_resumen_titulo", "Reporte Nutricional Mensual - {mes_str}")
    t_usr_tmpl = traducciones.get("08_PDF_resumen_usuario_id", "**Usuario Telegram ID:** {user_id}")

    story = [
        Paragraph(f"<b>{t_titulo_tmpl.format(mes_str=mes_str)}</b>", title_style),
        Paragraph(t_usr_tmpl.format(user_id=user_id), body_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=6)
    ]

    h_fecha = traducciones.get("08_PDF_resumen_th_fecha", "Fecha")
    h_cal_cons = traducciones.get("08_PDF_resumen_th_cal_cons", "Cal. Consumid.")
    h_cal_quem = traducciones.get("08_PDF_resumen_th_cal_quem", "Cal. Quemad.")
    h_bal_neto = traducciones.get("08_PDF_resumen_th_bal_neto", "Bal. Neto")
    h_prot = traducciones.get("08_PDF_resumen_th_proteinas", "Proteinas (g)")
    h_gras = traducciones.get("08_PDF_resumen_th_grasas", "Grasas (g)")
    h_carb = traducciones.get("08_PDF_resumen_th_carbs", "Carbohidratos (g)")
    h_fibr = traducciones.get("08_PDF_resumen_th_fibras", "Fibras (g)")

    headers_h1 = [h_fecha, h_cal_cons, h_cal_quem, h_bal_neto, h_prot, h_gras, h_carb, h_fibr]
    table_data_h1 = [[Paragraph(h, header_style) for h in headers_h1]]

    tot_cons, tot_quem, tot_prot, tot_gras, tot_carb, tot_fibr = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    if df_mes is not None and not df_mes.empty:
        fechas_unicas = sorted(df_mes['Fecha'].unique())

        for f in fechas_unicas:
            sub = df_mes[df_mes['Fecha'] == f]
            
            c_cons = float(sub[sub['Calorias'] > 0]['Calorias'].sum()) if 'Calorias' in sub.columns else 0.0
            c_quem = float(abs(sub[sub['Calorias'] < 0]['Calorias'].sum())) if 'Calorias' in sub.columns else 0.0
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
                Paragraph(f"{int(round(c_cons))} kcal", body_style),
                Paragraph(f"{int(round(c_quem))} kcal", body_style),
                Paragraph(f"{int(round(b_neto))} kcal", body_style),
                Paragraph(f"{int(round(prot))} g", body_style),
                Paragraph(f"{int(round(gras))} g", body_style),
                Paragraph(f"{int(round(carb))} g", body_style),
                Paragraph(f"{int(round(fibr))} g", body_style)
            ])
        
        tot_neto = tot_cons - tot_quem
        dias_activos = len(fechas_unicas) if len(fechas_unicas) > 0 else 1

        lbl_tot = traducciones.get("08_PDF_resumen_total_mes", "TOTAL MES")
        lbl_prom = traducciones.get("08_PDF_resumen_prom_diario", "PROM. DIARIO")

        table_data_h1.append([
            Paragraph(f"<b>{lbl_tot}</b>", body_style),
            Paragraph(f"<b>{int(round(tot_cons))} kcal</b>", body_style),
            Paragraph(f"<b>{int(round(tot_quem))} kcal</b>", body_style),
            Paragraph(f"<b>{int(round(tot_neto))} kcal</b>", body_style),
            Paragraph(f"<b>{int(round(tot_prot))} g</b>", body_style),
            Paragraph(f"<b>{int(round(tot_gras))} g</b>", body_style),
            Paragraph(f"<b>{int(round(tot_carb))} g</b>", body_style),
            Paragraph(f"<b>{int(round(tot_fibr))} g</b>", body_style)
        ])

        table_data_h1.append([
            Paragraph(f"<b>{lbl_prom}</b>", body_style),
            Paragraph(f"<b>{int(round(tot_cons/dias_activos))} kcal</b>", body_style),
            Paragraph(f"<b>{int(round(tot_quem/dias_activos))} kcal</b>", body_style),
            Paragraph(f"<b>{int(round(tot_neto/dias_activos))} kcal</b>", body_style),
            Paragraph(f"<b>{int(round(tot_prot/dias_activos))} g</b>", body_style),
            Paragraph(f"<b>{int(round(tot_gras/dias_activos))} g</b>", body_style),
            Paragraph(f"<b>{int(round(tot_carb/dias_activos))} g</b>", body_style),
            Paragraph(f"<b>{int(round(tot_fibr/dias_activos))} g</b>", body_style)
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
    
    sub_analisis = traducciones.get("08_PDF_resumen_analisis_sub", "Análisis Metabólico y Tabla Comparativa de Macronutrientes (Rangos Saludables)")
    story.append(Paragraph(f"<b>{sub_analisis}</b>", title_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=6))

    perfil_dict = perfil if isinstance(perfil, dict) else {}
    m = calcular_metricas_mensuales(df_mes, perfil_dict, user_id=user_id, mes_str=mes_str)

    th_nutriente = traducciones.get("08_PDF_resumen_th_nutriente", "Nutriente / Métrica")
    th_prom_real = traducciones.get("08_PDF_resumen_th_prom_real", "Promedio Diario Real (Mes)")
    th_rango_salud = traducciones.get("08_PDF_resumen_th_rango_salud", "Rango / Mínimo Saludable")

    n_cal = traducciones.get("08_PDF_resumen_nutr_calorias", "Balance Neto (kcal)")
    n_prot = traducciones.get("08_PDF_resumen_nutr_proteinas", "Proteínas")
    n_gras = traducciones.get("08_PDF_resumen_nutr_grasas", "Grasas")
    n_carb = traducciones.get("08_PDF_resumen_nutr_carbs", "Carbohidratos")
    n_fibr = traducciones.get("08_PDF_resumen_nutr_fibras", "Fibras")
    min_tpl = traducciones.get("08_PDF_resumen_minimo", "Mínimo {val} g")

    table_comp = [
        [Paragraph(f"<b>{th_nutriente}</b>", header_style), Paragraph(f"<b>{th_prom_real}</b>", header_style), Paragraph(f"<b>{th_rango_salud}</b>", header_style)],
        [Paragraph(n_cal, body_style), Paragraph(f"{m.get('prom_bal_neto', 0)} kcal", body_style), Paragraph(f"{m.get('cal_min', 0)} - {m.get('cal_max', 0)} kcal", body_style)],
        [Paragraph(n_prot, body_style), Paragraph(f"{m.get('prom_prot', 0)} g", body_style), Paragraph(f"{m.get('prot_min', 0)} - {m.get('prot_max', 0)} g", body_style)],
        [Paragraph(n_gras, body_style), Paragraph(f"{m.get('prom_gras', 0)} g", body_style), Paragraph(f"{m.get('gras_min', 0)} - {m.get('gras_max', 0)} g", body_style)],
        [Paragraph(n_carb, body_style), Paragraph(f"{m.get('prom_carb', 0)} g", body_style), Paragraph(f"{m.get('carb_min', 0)} - {m.get('carb_max', 0)} g", body_style)],
        [Paragraph(n_fibr, body_style), Paragraph(f"{m.get('prom_fibr', 0)} g", body_style), Paragraph(min_tpl.format(val=m.get('fibr_min', 0)), body_style)]
    ]
    t_comp = Table(table_comp, colWidths=[150, 185, 185])
    t_comp.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    story.append(t_comp)
    story.append(Spacer(1, 4))

    peso_act_pdf = round(float(m.get('peso_actual', 0)), 1)
    peso_ref_pdf = round(float(m.get('peso_referencia', 0)), 1)

    p_perfil_tmpl = traducciones.get("08_PDF_resumen_perfil_reg", "• <b>PERFIL REGISTRADO EN EL MES ({mes_str}):</b> Peso Registrado: {peso_act_pdf} kg | Peso Objetivo de esta etapa : {peso_ref_pdf} kg |")
    p_cambio_tmpl = traducciones.get("08_PDF_resumen_cambio_peso", "• <b>TENDENCIA ESTIMADA DE PESO:</b> {cambio_txt}")
    p_act_tmpl = traducciones.get("08_PDF_resumen_act_fisica", "• <b>ACTIVIDAD FÍSICA PROMEDIO:</b> {act_minutos} min/día (Rango recomendado: {act_min} - {act_max} min/día)")
    p_nota_act = traducciones.get("08_PDF_resumen_nota_act", "<i>(Nota: Los rangos de actividad consideran impacto corporal; actividades de bajo impacto como aquagym, natación o yoga no aplican restricciones de sobrepeso).</i>")

    story.append(Paragraph(p_perfil_tmpl.format(mes_str=mes_str, peso_act_pdf=peso_act_pdf, peso_ref_pdf=peso_ref_pdf), body_style))
    
    cambio_val = float(m.get('cambio_peso_kg', 0))
    mensaje_variacion = obtener_mensaje_variacion_peso(cambio_val, traducciones)
    story.append(Paragraph(p_cambio_tmpl.format(cambio_txt=mensaje_variacion), body_style))
    
    story.append(Paragraph(p_act_tmpl.format(act_minutos=m.get('prom_minutos_act', 0), act_min=m.get('act_min', 30), act_max=m.get('act_max', 60)), body_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph(p_nota_act, body_style))

    story.append(Spacer(1, 6))
    
    # --- NUEVA LÓGICA DE DISCLAIMER ---
    es_personalizado = m.get('valores_personalizados', False)
    id_prof = str(perfil_dict.get('profesional', '123456789')).strip()
    
    if es_personalizado:
        nota_pdf = traducciones.get("08_pdf_resumen_nota_pers", "<i>👨‍⚕️ <b>Nota Clínica:</b> Las metas y rangos de macronutrientes de este reporte han sido analizados, personalizados y aprobados explícitamente por tu profesional a cargo, reemplazando el cálculo estándar.</i>")
    elif id_prof != "123456789" and id_prof != "S/D" and id_prof != "":
        nota_pdf = traducciones.get("08_pdf_resumen_nota_prof_pend", "<i>🤖 <b>Nota del Sistema:</b> Tu profesional a cargo aún no ha personalizado las metas para este período. Los rangos mostrados han sido calculados de forma automática por el motor clínico del asistente (Fórmulas estandarizadas).</i>")
    else:
        nota_pdf = traducciones.get("08_pdf_resumen_nota_auto", "<i>🤖 <b>Nota del Sistema:</b> Reporte generado mediante métricas analíticas directas y cálculos automatizados. La tendencia de peso indicada es una proyección matemática aproximada calculada en base a tus registros.</i>")

    story.append(Paragraph(nota_pdf, body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer
    
async def generar_y_enviar_pdf_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    
    txt_aviso = traducciones.get("08_PDF_envio_aviso_inicial", "¡Recibido! Prepararemos el documento y cuando esté listo lo recibirá automáticamente. ⏳")
    await query.answer(txt_aviso, show_alert=True)
    
    txt_espera_tmpl = traducciones.get("08_PDF_envio_msg_espera", "🔄 **Generando reporte mensual...** Por favor aguarde unos momentos, le enviaremos el documento en cuanto esté listo.")
    mensaje_espera = await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=txt_espera_tmpl,
        parse_mode="Markdown"
    )

    try:
        cb_val = query.data
        for prefix in ["descargar_pdf_resumen_", "pdf_mes_"]:
            if cb_val.startswith(prefix):
                cb_val = cb_val.replace(prefix, "")
        mes_str = cb_val

        ahora = obtener_ahora_arg()
        mes_actual_str = ahora.strftime("%Y-%m")
        dia_actual = ahora.day

        if mes_str == mes_actual_str and 1 <= dia_actual <= 7:
            txt_7dias = traducciones.get("08_PDF_envio_restr_7dias", "⚠️ No se encuentra disponible el reporte en PDF del mes actual durante los primeros 7 días del mes.")
            await mensaje_espera.edit_text(txt_7dias)
            return

        if mes_str == mes_actual_str:
            if not await _validar_peso_mes_actual(update, context):
                await mensaje_espera.delete()
                return

        df_datos = obtener_datos_usuario(user_id) 
        
        if not df_datos.empty and 'Fecha' in df_datos.columns:
            df_datos['Fecha_dt'] = pd.to_datetime(df_datos['Fecha'])
            hoy_comienzo = pd.Timestamp.now().floor('D')
            
            if mes_str == mes_actual_str:
                df_mes = df_datos[
                    (df_datos['Fecha'].astype(str).str.startswith(mes_str)) & 
                    (df_datos['Fecha_dt'] < hoy_comienzo)
                ].copy()
            else:
                df_mes = df_datos[df_datos['Fecha'].astype(str).str.startswith(mes_str)].copy()
        else:
            df_mes = pd.DataFrame()

        if df_mes.empty:
            txt_sin_reg_tmpl = traducciones.get("08_PDF_envio_sin_reg_mes", "⚠️ No hay registros de días en el mes `{mes_str}` para generar el PDF.")
            await mensaje_espera.edit_text(txt_sin_reg_tmpl.format(mes_str=mes_str), parse_mode="Markdown")
            return

        perfil = obtener_perfil_usuario(user_id, mes_target=mes_str) or {}
        df_presion = pd.DataFrame()
        tmb_val = perfil.get('tmb', 0) if isinstance(perfil, dict) else 0

        m = calcular_metricas_mensuales(df_mes, perfil, user_id=user_id, mes_str=mes_str)

        pdf_buffer = await asyncio.to_thread(
            generar_pdf_resumen_bytes,
            mes_str,
            df_mes,
            df_presion,
            perfil,
            tmb_val,
            user_id
        )

        caption_tmpl = traducciones.get("08_PDF_envio_exito_caption", "✅ ¡Su documento está listo! Reporte mensual auditado correspondiente a **{mes_str}**.")
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=pdf_buffer,
            filename=f"M_{mes_str}.pdf",
            caption=caption_tmpl.format(mes_str=mes_str),
            parse_mode="Markdown"
        )
        
        try:
            await mensaje_espera.delete()
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Error al enviar PDF: {e}", exc_info=True)
        err_tmpl = traducciones.get("08_PDF_envio_error_gen", "⚠️ Error al procesar la descarga del PDF: {e}")
        await mensaje_espera.edit_text(err_tmpl.format(e=e))
                
#               INICIO                               MENSAJES PROGRAMADOS                          INICIO  
# ======================================================================================================================================

def evaluar_dias_validos(registros, fecha_inicio, fecha_fin):
    validos = 0
    todas_comidas = {"Desayuno", "Almuerzo", "Merienda", "Cena"}
    comidas_principales = {"Almuerzo", "Cena"}
    
    curr = fecha_inicio
    while curr <= fecha_fin:
        str_d = curr.strftime("%Y-%m-%d")
        comidas_del_dia = []
        calorias_del_dia = 0.0
        
        for r in registros:
            if str(r.get("Fecha", "")).strip() == str_d:
                momento = str(r.get("Momento/Actividad") or r.get("Momento", "")).capitalize()
                cal_val = float(r.get("Calorías (kcal)", r.get("Calorias", 0.0)) or 0.0)
                
                if momento in todas_comidas:
                    comidas_del_dia.append(momento)
                    # Sumamos solo las calorías positivas (ingestas, no actividades)
                    if cal_val > 0:
                        calorias_del_dia += cal_val
                        
        # Condición estricta: Al menos 2 comidas, 1 principal, y superar las 600 kcal diarias
        if len(comidas_del_dia) >= 2 and any(c in comidas_principales for c in comidas_del_dia):
            if calorias_del_dia >= 600.0:
                validos += 1
                
        curr += timedelta(days=1)
    return validos

async def recordatorio_lunes_presion(context):
    try:
        records = obtener_todos_usuarios()
        if not records:
            return

        ahora = obtener_ahora_arg()
        hace_siete_dias = ahora - timedelta(days=7)

        for r in records:
            user_id_raw = r.get("User ID", r.get("user_id", ""))
            if not user_id_raw:
                continue
            
            user_id = str(user_id_raw).split('.')[0].strip()
            estado_val = str(r.get("Estado", r.get("estado", "Activo"))).strip().lower()
            
            if estado_val in ['baja', 'suspendido', '3']:
                continue
            
            if estado_val not in ['activo', 'sí', 'si', 'true', '1'] and not estado_val.isdigit():
                continue

            lang = obtener_idioma_usuario(user_id) or 'es'
            traducciones = obtener_traducciones_db(lang) or {}

            df_presion = obtener_datos_presion_db(user_id) 
            
            tiene_medicion_reciente = False
            if not df_presion.empty and 'Fecha_Dia' in df_presion.columns:
                df_presion['Fecha_dt'] = pd.to_datetime(df_presion['Fecha_Dia'], errors='coerce')
                recientes = df_presion[df_presion['Fecha_dt'] >= pd.Timestamp(hace_siete_dias.date())]
                if not recientes.empty:
                    tiene_medicion_reciente = True

            if not tiene_medicion_reciente:
                mensaje = traducciones.get(
                    "08_notif_recordatorio_presion",
                    "🩺 **Recordatorio de Presión Arterial**\n\nHola. Notamos que todavía no registraste ninguna medición de presión arterial durante la semana pasada. Te recordamos la importancia de mantener un control regular para tu seguimiento médico.\n\nPodés registrarla cuando gustes usando el comando:\n`/presi 120,80,70`"
                ).replace('\\n', '\n')           

                try:
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=mensaje,
                        parse_mode="Markdown"
                    )
                except Exception as ex_send:
                    logger.error(f"No se pudo enviar el recordatorio de presión al usuario {user_id}: {ex_send}")

    except Exception as e:
        logger.error(f"Error en la ejecución del recordatorio semanal de presión: {e}")

async def ejecutar_recordatorio_comidas(context: ContextTypes.DEFAULT_TYPE, momento: str):
    registros_usuarios = obtener_todos_usuarios()
    if not registros_usuarios:
        return

    ahora_dt = obtener_ahora_arg()
    hoy = ahora_dt.date() if hasattr(ahora_dt, "date") else ahora_dt
    ayer = hoy - timedelta(days=1)
    anteayer = hoy - timedelta(days=2)

    str_hoy = hoy.strftime("%Y-%m-%d")
    str_ayer = ayer.strftime("%Y-%m-%d")
    str_anteayer = anteayer.strftime("%Y-%m-%d")

    todas_comidas = ["Desayuno", "Almuerzo", "Merienda", "Cena"]
    
    es_lunes_manana = (hoy.weekday() == 0 and momento == 'manana')
    es_martes_manana = (hoy.weekday() == 1 and momento == 'manana')
    es_informe_mensual_pdf = (hoy.day in [5, 20] and momento == 'tarde')
    
    es_primer_dia_mes = (hoy.day == 1 and momento == 'manana')
    es_dia_5 = (hoy.day == 5 and momento == 'tarde')
    es_dia_20 = (hoy.day == 20 and momento == 'tarde')

    if es_primer_dia_mes and 'proceso_masivo_cobros' in globals():
        await proceso_masivo_cobros(context)

    if es_dia_5 or es_dia_20:
        try:
            conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
            mes_actual_prefix = hoy.strftime("%Y-%m")
            cur.execute('SELECT "User ID", "vencimiento_suscripcion" FROM "Usuarios" WHERE "vencimiento_suscripcion" LIKE %s', (f"{mes_actual_prefix}%",))
            usuarios_vencen = cur.fetchall()
            cur.close()
            conn.close()

            for u_ven in usuarios_vencen:
                u_id_str = str(u_ven[0]).split('.')[0].strip()
                try:
                    u_lang = obtener_idioma_usuario(int(u_id_str)) or 'es'
                    u_trad = obtener_traducciones_db(u_lang) or {}

                    if es_dia_5:
                        mensaje = u_trad.get(
                            "08_inf_venc_dia5", 
                            "🔔 **Aviso de Suscripción:** Te recordamos que tu plan actual vence a finales de este mes. Podés verificar las opciones de renovación o elegir una promoción ingresando al comando `/pagar`."
                        )
                    else:
                        mensaje = u_trad.get(
                            "08_inf_venc_dia20", 
                            "📢 **Próxima Facturación:** Te recordamos que a fin de mes se emitirá la factura para renovar tu suscripción. Si deseás cambiar de plan o elegir alguna de nuestras promociones especiales, podés seleccionarla usando el comando `/pagar`."
                        )

                    await context.bot.send_message(
                        chat_id=int(u_id_str),
                        text=mensaje,
                        parse_mode="Markdown"
                    )
                    await asyncio.sleep(2)
                except Exception as e_aviso:
                    logger.error(f"No se pudo enviar el aviso de facturación al usuario {u_id_str}: {e_aviso}")
        except Exception as ex_aviso_gral:
            logger.error(f"Error procesando los avisos dirigidos de facturación (Día 5/20): {ex_aviso_gral}")

    if es_lunes_manana:
        await recordatorio_lunes_presion(context)

    for index, u in enumerate(registros_usuarios):
        try:
            estado_raw = str(u.get("Estado", u.get("estado", "0"))).strip().lower()
            notif = str(u.get("Notificaciones", "")).strip().lower()
            raw_user_id = u.get("User ID", u.get("user_id", ""))
            
            if not raw_user_id:
                continue
            
            try:
                user_id = int(str(raw_user_id).split('.')[0].strip())
            except ValueError:
                continue

            if estado_raw in ['baja', 'suspendido', '3']:
                continue

            if notif not in ["si", "sí"]:
                continue

            lang_u = obtener_idioma_usuario(user_id) or 'es'
            traducciones = obtener_traducciones_db(lang_u) or {}

            if es_dia_5:
                inicio_check = hoy - timedelta(days=14)
                fin_check = hoy
                registros_u = obtener_registros_usuario(user_id)
                dias_validos = evaluar_dias_validos(registros_u, inicio_check, fin_check)
                dias_evaluados = (fin_check - inicio_check).days + 1
                faltas = dias_evaluados - dias_validos
                
                if faltas >= 5:
                    msg_aviso = traducciones.get(
                        "08_notif_freemium_aviso5",
                        "⚠️ **Aviso de uso gratuito:** Te recordamos que para mantener la beca de uso 100% gratuito de la plataforma, necesitás registrar tus comidas al menos 20 días al mes. De los últimos 15 días, faltó el registro en {faltas} días. ¡Ponete al día para no perder el beneficio!"
                    ).format(faltas=faltas)
                    await context.bot.send_message(chat_id=user_id, text=msg_aviso, parse_mode="Markdown")

            if es_dia_20:
                inicio_check = hoy - timedelta(days=29)
                fin_check = hoy
                registros_u = obtener_registros_usuario(user_id)
                dias_validos = evaluar_dias_validos(registros_u, inicio_check, fin_check)
                
                # --- NUEVA LÓGICA: AUDITORÍA DE CALIDAD CLÍNICA (FILTRO ANTI-TROLL) ---
                promedio_irreal = False
                promedio_calorico = 0
                if dias_validos > 0:
                    calorias_totales = sum(
                        float(r.get("Calorías (kcal)", r.get("Calorias", 0))) 
                        for r in registros_u 
                        if r.get("Fecha") and inicio_check <= datetime.strptime(r["Fecha"].strip(), "%Y-%m-%d").date() <= fin_check and float(r.get("Calorías (kcal)", r.get("Calorias", 0))) > 0
                    )
                    promedio_calorico = calorias_totales / dias_validos
                    if promedio_calorico < 1000 or promedio_calorico > 4000:
                        promedio_irreal = True
                
                if dias_validos < 20 or promedio_irreal:
                    actualizar_estado_usuario(str(user_id), "3")
                    
                    _, dias_en_mes = calendar.monthrange(hoy.year, hoy.month)
                    dias_restantes = dias_en_mes - hoy.day 
                    precio_base_estrellas = obtener_precio_plan_mensual() if 'obtener_precio_plan_mensual' in globals() else 100
                    estrellas_prorrateadas = int(round((precio_base_estrellas / dias_en_mes) * dias_restantes))
                    costo_usd_prorrateado = estrellas_prorrateadas * 0.02
                    
                    if 'facturar_saldo_del_mes' in globals():
                        await facturar_saldo_del_mes(context, user_id, dias_restantes, estrellas_prorrateadas)
                    
                    if promedio_irreal and dias_validos >= 20:
                        msg_fin = traducciones.get(
                            "08_notif_freemium_fin20_irreal",
                            "❌ **Seguimiento pausado.**\n\nHemos detectado un patrón de registros anómalos o irreales en tus ingestas (promedio diario de `{promedio_calorico:.0f} kcal`, fuera del rango vital permitido). Tu plan gratuito ha sido cancelado para mantener la integridad del sistema.\n\nPara reactivarlo y usar el bot sin interrupciones hasta fin de mes, hemos emitido una factura proporcional por los días restantes (aprox. {costo_usd} USD / {estrellas} ⭐️)."
                        ).format(
                            promedio_calorico=promedio_calorico,
                            costo_usd=f"{costo_usd_prorrateado:.2f}", 
                            estrellas=estrellas_prorrateadas
                        ).replace('\\n', '\n')
                    else:
                        msg_fin = traducciones.get(
                            "08_notif_freemium_fin20",
                            "❌ **Período de prueba finalizado.**\nNo alcanzaste el objetivo mínimo de constancia (20 días) para mantener la cuenta gratuita y el seguimiento fue pausado.\n\nPara reactivarlo y usar el bot sin interrupciones hasta fin de mes, hemos emitido una factura proporcional por los días restantes (aprox. {costo_usd} USD / {estrellas} ⭐️).\n\nA fin de mes podrás elegir tu plan definitivo."
                        ).format(
                            costo_usd=f"{costo_usd_prorrateado:.2f}", 
                            estrellas=estrellas_prorrateadas
                        ).replace('\\n', '\n') 

                    await context.bot.send_message(chat_id=user_id, text=msg_fin, parse_mode="Markdown")
                    continue

            if es_lunes_manana:
                await _validar_peso_mes_actual(context=context, user_id=user_id)

            if es_martes_manana:
                peso_ok = await _validar_peso_mes_actual(context=context, user_id=user_id)
                if peso_ok:
                    try:
                        ahora_raw = obtener_ahora_arg()
                        if hasattr(ahora_raw, 'tzinfo') and ahora_raw.tzinfo is not None:
                            ahora_raw = ahora_raw.replace(tzinfo=None)
                        ahora_ts = pd.Timestamp(ahora_raw)

                        inicio_rango = (ahora_ts.floor('D') - pd.Timedelta(days=7)).date()
                        fin_rango = (ahora_ts.floor('D') - pd.Timedelta(seconds=1)).date()
                        etiqueta_periodo = traducciones.get("08_notif_etiqueta_semana", "Semana Anterior (Lunes a Domingo)")

                        txt_resumen, m = _generar_texto_resumen_semanal(user_id, inicio_rango, fin_rango, etiqueta_periodo)

                        if txt_resumen and m:
                            await context.bot.send_message(chat_id=int(user_id), text=txt_resumen, parse_mode="Markdown")
                            logger.info(f"Resumen semanal enviado exitosamente a {user_id}")

                        if index < len(registros_usuarios) - 1:
                            await asyncio.sleep(60)
                    except Exception as e_ia:
                        logger.error(f"Error generando resumen semanal para {user_id}: {e_ia}")

            if es_informe_mensual_pdf:
                peso_ok = await _validar_peso_mes_actual(context=context, user_id=user_id)
                if peso_ok:
                    try:
                        if hoy.day == 5:
                            primer_dia_mes_actual = hoy.replace(day=1)
                            ultimo_dia_mes_anterior = primer_dia_mes_actual - timedelta(days=1)
                            mes_target_str = ultimo_dia_mes_anterior.strftime("%Y-%m")
                            es_auto_15 = False
                        else:
                            mes_target_str = hoy.strftime("%Y-%m")
                            es_auto_15 = True

                        exito_envio = await procesar_y_enviar_informe_mensual(
                            context=context,
                            user_id=user_id,
                            chat_destino=user_id,
                            mes_target=mes_target_str,
                            es_automatico_15=es_auto_15,
                            forzar_envio=True
                        )

                        if exito_envio:
                            logger.info(f"Informe automático en PDF del período {mes_target_str} enviado exitosamente a {user_id}")

                        if index < len(registros_usuarios) - 1:
                            await asyncio.sleep(60)

                    except Exception as e_mensual:
                        logger.error(f"Error generando informe automático en PDF para {user_id}: {e_mensual}", exc_info=True)

            registros_comidas = obtener_registros_usuario(user_id)

            comidas_anteayer = set()
            comidas_ayer = set()
            comidas_hoy = set()

            for reg in registros_comidas:
                fecha_reg = str(reg.get("Fecha", "")).strip()
                momento_actividad = str(reg.get("Momento/Actividad") or reg.get("Momento", "")).strip()
                momento_reg = momento_actividad.capitalize()

                if fecha_reg == str_anteayer:
                    comidas_anteayer.add(momento_reg)
                elif fecha_reg == str_ayer:
                    comidas_ayer.add(momento_reg)
                elif fecha_reg == str_hoy:
                    comidas_hoy.add(momento_reg)

            faltantes = []
            
            # Textos para los días
            txt_de_anteayer = traducciones.get("08_notif_de_anteayer", "de anteayer")
            txt_de_ayer = traducciones.get("08_notif_de_ayer", "de ayer")
            txt_de_hoy = traducciones.get("08_notif_de_hoy", "de hoy")
            
            # Función para traducir el nombre del momento (Desayuno, Almuerzo, etc)
            def traducir_momento(m):
                mapa = {
                    "Desayuno": traducciones.get("08_inf_diario_momento_desayuno", "Desayuno"),
                    "Almuerzo": traducciones.get("08_inf_diario_momento_almuerzo", "Almuerzo"),
                    "Merienda": traducciones.get("08_inf_diario_momento_merienda", "Merienda"),
                    "Cena": traducciones.get("08_inf_diario_momento_cena", "Cena")
                }
                return mapa.get(m, m)

            if momento == 'manana':
                for c in todas_comidas:
                    if c not in comidas_anteayer:
                        faltantes.append(f"{traducir_momento(c)} {txt_de_anteayer} ({str_anteayer})")
                for c in todas_comidas:
                    if c not in comidas_ayer:
                        faltantes.append(f"{traducir_momento(c)} {txt_de_ayer} ({str_ayer})")

            elif momento == 'tarde':
                for c in todas_comidas:
                    if c not in comidas_ayer:
                        faltantes.append(f"{traducir_momento(c)} {txt_de_ayer} ({str_ayer})")
                if "Desayuno" not in comidas_hoy:
                    faltantes.append(f"{traducir_momento('Desayuno')} {txt_de_hoy}")
                if "Almuerzo" not in comidas_hoy:
                    faltantes.append(f"{traducir_momento('Almuerzo')} {txt_de_hoy}")

            if faltantes:
                lista_formateada = "\n• " + "\n• ".join(faltantes)

                msg_recordatorio_comidas = traducciones.get(
                    "08_notif_recordatorio_comidas",
                    "📌 **Recordatorio de comidas pendientes:**\n{lista_formateada}\n\nSi ya las consumiste, podés registrarlas en cualquier momento."
                )
                await context.bot.send_message(
                    chat_id=int(user_id), 
                    text=msg_recordatorio_comidas.format(lista_formateada=lista_formateada).replace('\\n', '\n'), 
                    parse_mode="Markdown"
                )

                logger.info(f"Recordatorio de comidas ({momento}) enviado a {user_id}")

        except Exception as e:
            logger.error(f"Error procesando usuario {user_id}: {e}")
              
# ======================================================================================================================================
#                   FINAL                                    COMANDOS INFORMES                                   FINAL
# =====================================================================================================================================

# =====================================================================================================================================
#                       INICIO                  COMANDOS INGRESOS                            INICIO
# =====================================================================================================================================        
#                       COMANDO ALTA Y FLUJO DE USUARIO CON INFORME IA
# =========================================================================================================================================

async def procesar_informe_inicial(datos_usuario: dict) -> tuple[str, io.BytesIO]:
    user_id = datos_usuario.get('user_id')
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    nombre = datos_usuario.get('nombre', 'Paciente')
    edad = int(datos_usuario.get('edad', 30))
    sexo = datos_usuario.get('sexo', 'M')
    altura = float(datos_usuario.get('altura', 170.0))
    peso = float(datos_usuario.get('peso', 70.0))
    peso_ideal = float(datos_usuario.get('peso_ideal', peso))
    peso_etapa = float(datos_usuario.get('peso_etapa', peso))
    ocupacion = float(datos_usuario.get('ocupacion', 1.375))
    cadera = float(datos_usuario.get('cadera', 0.0))
    get_calorias = float(datos_usuario.get('get', 2000.0))
    profesional = str(datos_usuario.get('profesional', '')).strip()
    
    ritmo_elegido = str(datos_usuario.get('ritmo', 'moderado')).lower()

    if "tranquilo" in ritmo_elegido or "lento" in ritmo_elegido or "1" in ritmo_elegido:
        texto_orientacion = traducciones.get("05_bot_inf_gradual", "Has seleccionado un enfoque gradual...")
    elif "intenso" in ritmo_elegido or "rapido" in ritmo_elegido or "rápido" in ritmo_elegido or "3" in ritmo_elegido:
        texto_orientacion = traducciones.get("05_bot_inf_exigente", "Has seleccionado un enfoque más exigente...")
    else:
        texto_orientacion = traducciones.get("05_bot_inf_equilibrado", "Has seleccionado un enfoque equilibrado...")

    # Calculamos el gasto energético y el objetivo calórico en base al PESO DE ETAPA
    genero_str = "femenino" if str(sexo).upper() in ["F", "FEMENINO", "MUJER"] else "masculino"
    _, get_etapa = calcular_tmb_y_get(
        peso_actual=peso_etapa,
        altura_cm=altura,
        edad=edad,
        genero=genero_str,
        actividad=ocupacion,
        cadera_cm=cadera
    )

    get_val = float(get_calorias) if get_calorias > 0 else float(get_etapa)
    if peso > 0 and peso_etapa < peso:
        # Las calorías objetivo acompañan exactamente la proporción del peso de etapa elegido
        cal_proporcional = get_val * (peso_etapa / peso)
        meta_cal = int(round((cal_proporcional + get_etapa) / 2.0))
    else:
        meta_cal = int(round(get_etapa))

    factor_prot = 1.5 if str(sexo).upper() in ['M', 'MASCULINO'] else 1.2
    meta_prot = int(round(peso_etapa * factor_prot))
    meta_gras = int(round((meta_cal * 0.25) / 9.0))
    meta_carb = int(round((meta_cal * 0.50) / 4.0))

    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle('TituloInforme', parent=styles['Heading1'], fontSize=14, leading=16, alignment=1, textColor=colors.HexColor('#1b4f72'))
    sub_style = ParagraphStyle('SubInforme', parent=styles['Normal'], fontSize=9, leading=13, textColor=colors.HexColor('#566573'))
    body_style = ParagraphStyle('CuerpoInforme', parent=styles['Normal'], fontSize=10, leading=15, textColor=colors.HexColor('#2c3e50'))
    indicaciones_style = ParagraphStyle('Indicaciones', parent=styles['Normal'], fontSize=10, leading=15, textColor=colors.HexColor('#0b5345'), spaceBefore=10)

    t_titulo = traducciones.get("05_bot_pdf_titulo_inicial", "INFORME NUTRICIONAL INICIAL - CONFIGURACIÓN DE PERFIL")
    story.append(Paragraph(f"<b>{t_titulo}</b>", titulo_style))
    story.append(Spacer(1, 8))
    
    t_pac = traducciones.get("05_bot_pdf_paciente", "Paciente")
    t_edad = traducciones.get("05_bot_pdf_edad", "Edad")
    t_anios = traducciones.get("05_bot_pdf_anios", "años")
    t_sexo_lbl = traducciones.get("05_bot_pdf_sexo", "Sexo")
    t_altura = traducciones.get("05_bot_pdf_altura", "Altura")
    t_peso_act = traducciones.get("05_bot_pdf_peso_act", "Peso Actual")
    t_peso_ideal_lbl = traducciones.get("05_bot_pdf_peso_ideal", "Peso Teórico Ideal")
    t_meta = traducciones.get("05_bot_pdf_meta", "Meta Etapa 1")
    t_ritmo = traducciones.get("05_bot_pdf_ritmo", "Ritmo")
    t_obj = traducciones.get("05_bot_pdf_obj_diarios", "Objetivos Diarios")
    t_prot = traducciones.get("05_bot_pdf_prot", "Proteínas")
    t_grasas = traducciones.get("05_bot_pdf_grasas", "Grasas")
    t_carbos = traducciones.get("05_bot_pdf_carbos", "Carbos")

    resumen_datos = (
        f"<b>{t_pac}:</b> {nombre} | <b>ID:</b> `{datos_usuario.get('user_id')}`<br/>"
        f"<b>{t_edad}:</b> {edad} {t_anios} | <b>{t_sexo_lbl}:</b> {sexo} | <b>{t_altura}:</b> {altura} cm<br/>"
        f"<b>{t_peso_act}:</b> {peso} kg | <b>{t_peso_ideal_lbl}:</b> {peso_ideal} kg<br/>"
        f"<b>{t_meta}:</b> {peso_etapa} kg | <b>{t_ritmo}:</b> {ritmo_elegido.capitalize()}<br/>"
        f"<b>{t_obj}:</b> ~{meta_cal} kcal | {t_prot}: ~{meta_prot}g | {t_grasas}: ~{meta_gras}g | {t_carbos}: ~{meta_carb}g"
    )
    story.append(Paragraph(resumen_datos, sub_style))
    story.append(Spacer(1, 15))
    
    if profesional and profesional != "123456789":
        t_espacio_prof = traducciones.get("05_bot_pdf_espacio_prof", "👨‍⚕️ Espacio Reservado para tu Profesional:")
        t_ind_prof = traducciones.get("05_bot_pdf_indicaciones", "<i>(Aquí se incluirán las indicaciones específicas...)</i>")
        story.append(Paragraph(f"<b>{t_espacio_prof}</b>", styles['Heading2']))
        story.append(Spacer(1, 6))
        story.append(Paragraph(t_ind_prof, indicaciones_style))
    else:
        t_orientacion = traducciones.get("05_bot_pdf_orientacion", "ℹ️ Orientación General del Sistema:")
        story.append(Paragraph(f"<b>{t_orientacion}</b>", styles['Heading2']))
        story.append(Spacer(1, 6))
        story.append(Paragraph(texto_orientacion, body_style))

    story.append(Spacer(1, 10))
    t_tit_cond = traducciones.get("05_bot_pdf_condiciones_titulo", "<b>Condiciones de Mantenimiento del Plan Gratuito:</b>")
    t_txt_cond = traducciones.get(
        "05_bot_pdf_condiciones_plan", 
        "Para conservar el beneficio del plan gratuito sin costo, el sistema requiere constancia: deberás registrar tus ingestas al menos 12 días por cada período quincenal. "
        "Esto otorga un margen de flexibilidad de hasta 3 días libres por quincena. Si la auditoría automática detecta 4 o más días sin registros en una misma quincena, "
        "el beneficio gratuito se suspenderá y se requerirá pasar a un plan de pago para continuar."
    )
    story.append(Paragraph(t_tit_cond, styles['Heading2']))
    story.append(Spacer(1, 4))
    story.append(Paragraph(t_txt_cond, body_style))
    
    doc.build(story)
    pdf_buffer.seek(0)
    
    return texto_orientacion, pdf_buffer
    
def _verificar_estado_usuario_en_hoja(user_id):
    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        cur.execute('SELECT "Estado" FROM "Usuarios" WHERE "User ID" = %s', (str(user_id),))
        fila = cur.fetchone()
        cur.close()
        conn.close()
        
        if fila is not None:
            estado = fila[0]
            if estado is None:
                return "0"
            return str(estado).strip()
        return None
    except Exception as e:
        logger.error(f"Error al verificar estado del usuario {user_id}: {e}")
        return None

def _verificar_profesional_valido(prof_id):
    prof_limpio = str(prof_id).strip()
    try:
        conn, cur = _asegurar_tabla_y_conectar("Profesionales", tipo_tabla="profesionales")
        cur.execute('SELECT "User ID" FROM "Profesionales"')
        filas = cur.fetchall()
        cur.close()
        conn.close()

        for fila in filas:
            id_db = str(fila[0] or "").split('.')[0].strip()
            if id_db == prof_limpio:
                return True
        return False
    except Exception as e:
        logger.error(f"Error al verificar profesional {prof_id}: {e}")
        return False

async def obtener_idiomas_disponibles_db():
    idiomas_info = []
    try:
        conn, cur = _asegurar_tabla_y_conectar("multi", tipo_tabla="comidas_precargadas")
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_schema = 'public' AND LOWER(table_name) = 'multi' AND LOWER(column_name) NOT IN ('id', 'variables')
        """)
        cols = [f[0].strip().lower() for f in cur.fetchall() if f[0]]

        cur.execute('SELECT * FROM "multi"')
        filas = cur.fetchall()
        colnames = [desc[0].strip().lower() for desc in cur.description]
        cur.close(); conn.close()

        dict_filas = {str(dict(zip(colnames, fila)).get('variables', '')).strip().lower(): dict(zip(colnames, fila)) for fila in filas}
        row_lenguajes, row_banderas = dict_filas.get('lenguajes', {}), dict_filas.get('banderas', {})

        for col in cols:
            idiomas_info.append({
                'codigo': col,
                'nombre': str(row_lenguajes.get(col, col.upper())).strip(),
                'bandera': str(row_banderas.get(col, '🌐')).strip()
            })
    except Exception as e:
        logger.error(f"Error tabla multi (idiomas): {e}")
        idiomas_info = [{'codigo': 'es', 'nombre': 'Español', 'bandera': '🇪🇸'}, {'codigo': 'en', 'nombre': 'English', 'bandera': '🇺🇸'}]
    return idiomas_info

async def ing_recibir_ritmo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['ing_ritmo'] = query.data.replace("ritmo_", "")
    
    user_id = query.from_user.id
    lang = context.user_data.get('ing_idioma', 'es')
    traducciones = obtener_traducciones_db(lang) or {}

    idiomas_disp = await obtener_idiomas_disponibles_db()
    b_list = [[InlineKeyboardButton(f"{item['bandera']} {item['nombre']}", callback_data=f"set_lang_{item['codigo']}")] for item in idiomas_disp]
    
    txt_idioma = traducciones.get("09_ing_selecciona_idioma", "🌐 Seleccioná tu **idioma preferido**:")
    await query.edit_message_text(txt_idioma, reply_markup=InlineKeyboardMarkup(b_list), parse_mode="Markdown")
    return ING_IDIOMA

async def ing_recibir_cadera(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('ing_idioma', 'es')
    traducciones = obtener_traducciones_db(lang) or {}
    
    txt = update.message.text.strip().replace(',', '.')
    try:
        cadera = float(txt)
        if not (60 <= cadera <= 200): raise ValueError()
    except ValueError:
        txt_err = traducciones.get("09_ing_err_cadera_valida", "⚠️ Ingresá un perímetro de cadera válido en cm (ejemplo: `100`).")
        await update.message.reply_text(txt_err, parse_mode="Markdown")
        return ING_CADERA

    context.user_data['ing_cadera'] = cadera

    btn_r1 = traducciones.get('09_btn_ritmo_tranquilo', "🟢 Tranquilo / Lento")
    btn_r2 = traducciones.get('09_btn_ritmo_moderado', "🟡 Moderado")
    btn_r3 = traducciones.get('09_btn_ritmo_intenso', "🔴 Intenso / Rápido")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_r1, callback_data="ritmo_tranquilo")],
        [InlineKeyboardButton(btn_r2, callback_data="ritmo_moderado")],
        [InlineKeyboardButton(btn_r3, callback_data="ritmo_intenso")]
    ])
    
    txt_ritmo = traducciones.get("09_ing_selecciona_ritmo", "Seleccioná el **ritmo para tu plan**. Esto define el déficit/superávit de tus calorías:\n• *🟢 Tranquilo (Cambios muy graduales, súper fácil de sostener).*\n• *🟡 Moderado (Equilibrio ideal entre resultados y adherencia).*\n• *🔴 Intenso (Exigente, para resultados más rápidos).*\n\n🎯 Seleccioná tu ritmo deseado:").replace('\\n', '\n')
    await update.message.reply_text(txt_ritmo, reply_markup=keyboard, parse_mode="Markdown")
    return ING_RITMO

async def ing_recibir_idioma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    nuevo_idioma = query.data.replace("set_lang_", "")
    context.user_data['ing_idioma'] = nuevo_idioma
    traducciones = obtener_traducciones_db(nuevo_idioma) or {}

    btn_nivel1 = traducciones.get("09_ing_btn_nivel_1", "🪑 Nivel 1 (Ligero)")
    btn_nivel2 = traducciones.get("09_ing_btn_nivel_2", "🚶 Nivel 2 (Moderado)")
    btn_nivel3 = traducciones.get("09_ing_btn_nivel_3", "🏃 Nivel 3 (Intenso)")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_nivel1, callback_data="ocup_1.375")],
        [InlineKeyboardButton(btn_nivel2, callback_data="ocup_1.550")],
        [InlineKeyboardButton(btn_nivel3, callback_data="ocup_1.725")]
    ])
    
    texto_ocupacion = traducciones.get("09_ing_selecciona_movimiento", "Seleccioná tu **nivel de movimiento diario** (el ejercicio deportivo se registra aparte):\n• *🪑 Ligero (Trabajo de oficina / Mayormente sentado).*\n• *🚶 Moderado (De pie muchas horas, ej: docentes, vendedores).*\n• *🏃 Intenso (Trabajo físico pesado, ej: albañilería, carga).*").replace('\\n', '\n')
    
    await query.edit_message_text(texto_ocupacion, reply_markup=keyboard, parse_mode="Markdown")
    return ING_OCUPACION

async def ing_recibir_ocupacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get('ing_idioma', 'es')
    traducciones = obtener_traducciones_db(lang) or {}
    
    try: 
        context.user_data['ing_ocupacion'] = float(query.data.replace("ocup_", ""))
    except ValueError: 
        context.user_data['ing_ocupacion'] = 1.375
        
    txt_peso = traducciones.get("09_ing_ingresa_peso", "Ingresá tu **peso actual en kg** (ejemplo: `82.5`):")
    await query.edit_message_text(txt_peso, parse_mode="Markdown")
    return ING_PESO

async def cmd_ingreso_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    idioma_detectado = obtener_idioma_usuario(user_id) or 'es'
    context.user_data['ing_idioma'] = idioma_detectado
    traducciones = obtener_traducciones_db(idioma_detectado) or {}

    estado_usr = _verificar_estado_usuario_en_hoja(user_id)
    
    if estado_usr is not None:
        estado_lower = estado_usr.lower()
        if estado_lower == '3':
            mensaje_bloqueo = traducciones.get("09_ing_prueba_finalizada", "⚠️ **Tu período de prueba gratuito ha finalizado.**\n\nPara seguir usando todas las funciones del asistente, podés activar tu cuenta abonando los días que restan hasta fin de mes.\n\nUna vez abonado, volverás a tener acceso total y tu ciclo de facturación se alineará al día 1 del mes próximo.").replace('\\n', '\n')
            txt_btn_act = traducciones.get("09_ing_btn_activar_mes", "⭐ Activar mes en curso")
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(txt_btn_act, callback_data="rescate_mensual")]])
            await update.message.reply_text(mensaje_bloqueo, reply_markup=keyboard, parse_mode="Markdown")
            return ConversationHandler.END
            
        elif estado_lower in ['inactivo', 'bloqueado', 'no', 'false']:
            txt_bloq = traducciones.get('09_ing_error_usuario_deshabilitado', "❌ **Su usuario ha sido deshabilitado, contáctese con el administrador del bot.**")
            await update.message.reply_text(txt_bloq.replace('\\n', '\n'), parse_mode="Markdown")
            return ConversationHandler.END
        else:
            perfil_existente = obtener_perfil_usuario(user_id) or {}
            nombre_usr = perfil_existente.get('nombre', 'Usuario') if perfil_existente else 'Usuario'
            txt_activo = traducciones.get('09_ing_cuenta_activa_aviso', 
                "ℹ **¡Ya tenés una cuenta activa, {nombre_usr}!**\n\nTu ficha ya está registrada en el sistema con el ID `{user_id}`.\nPodés consultar o actualizar tu información en cualquier momento con el comando `/perfil`."
            ).format(nombre_usr=nombre_usr, user_id=user_id)
            await update.message.reply_text(txt_activo.replace('\\n', '\n'), parse_mode="Markdown")
            return ConversationHandler.END

    texto_advertencia = traducciones.get('09_ing_advertencia_legal', 
        "⚖️ **TÉRMINOS Y CONDICIONES DE USO**\n\nPara continuar con la apertura de tu cuenta, por favor hacé clic en el botón de abajo para leer las condiciones y aceptar los términos en nuestra plataforma:"
    )
    btn_terminos_text = traducciones.get('09_btn_aceptar_terminos', "✅ Leer y Aceptar Términos")
    
    # Aquí configuramos la URL de tu Web App desplegada en Flask (ej: https://tu-sitio.onrender.com/terminos)
    url_webapp = f"https://ianutribot.com/terminos?user_id={user_id}"
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(btn_terminos_text, web_app=WebAppInfo(url=url_webapp))]])
    await update.message.reply_text(texto_advertencia.replace('\\n', '\n'), reply_markup=keyboard, parse_mode="Markdown")
    return ING_TERMINOS

async def ing_aceptar_terminos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('ing_idioma', 'es')
    traducciones = obtener_traducciones_db(lang) or {}

    # Verificamos si la señal viene de la Web App o de un mensaje de texto con los datos devueltos
    if update.effective_message and update.effective_message.web_app_data:
        data_web = update.effective_message.web_app_data.data
        if "aceptado" in data_web:
            txt_terminos_ok = traducciones.get("09_ing_terminos_ok", "✅ **Términos aceptados correctamente.**\n\n🔑 **Apertura de Ficha - Validación de Profesional**\n\nPara comenzar el registro, por favor ingresá el **ID de Telegram del profesional**.\n*(Si no tenés un profesional asignado y querés usar el asistente de forma independiente, ingresá 123456789)*:").replace('\\n', '\n')
            await update.message.reply_text(txt_terminos_ok, parse_mode="Markdown")
            return ING_PROFESIONAL
            
    # Si por alguna razón entra mal o cancela, se mantiene en el estado
    return ING_TERMINOS
    
async def ing_recibir_profesional(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prof_id = update.message.text.strip()
    lang = context.user_data.get('ing_idioma', 'es')
    traducciones = obtener_traducciones_db(lang) or {}
    
    es_valido = False
    if prof_id == "123456789":
        es_valido = True
        context.user_data['ing_profesional_oficial'] = "123456789"
        context.user_data['ing_profesional_pendiente'] = None
    else:
        loop = asyncio.get_running_loop()
        es_valido = await loop.run_in_executor(None, _verificar_profesional_valido, prof_id)
        if es_valido:
            context.user_data['ing_profesional_oficial'] = "123456789"
            context.user_data['ing_profesional_pendiente'] = prof_id
    
    if not es_valido:
        txt_err_prof = traducciones.get("09_ing_err_prof_invalido", "⚠️ **ID de profesional no válido**\n\nEl número ingresado no figura en la lista de profesionales autorizados. Por favor, verificá el ID con tu profesional e intentalo nuevamente o escribí `/cancelar`.").replace('\\n', '\n')
        await update.message.reply_text(txt_err_prof, parse_mode="Markdown")
        return ING_PROFESIONAL

    txt_solic_nombre = traducciones.get("09_ing_solicita_nombre", "✅ **Profesional verificado correctamente.**\n\n📝 **Apertura de Ficha Nutricional**\nPor favor, indicá tu **Nombre y Apellido / Apodo**:").replace('\\n', '\n')
    await update.message.reply_text(txt_solic_nombre, parse_mode="Markdown")
    return ING_NOMBRE
    
async def ing_recibir_cumple(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cumple_str = update.message.text.strip()
    lang = context.user_data.get('ing_idioma', 'es')
    traducciones = obtener_traducciones_db(lang) or {}

    try:
        datetime.strptime(cumple_str, "%Y-%m-%d")
    except ValueError:
        txt_err_fec = traducciones.get("09_ing_err_fecha_cumple", "⚠️ Formato de fecha inválido. Usá el formato `AAAA-MM-DD` (ejemplo: `1990-08-25`).")
        await update.message.reply_text(txt_err_fec, parse_mode="Markdown")
        return ING_CUMPLE

    context.user_data['ing_cumple'] = cumple_str
    edad_calculada = calcular_edad_desde_cumple(cumple_str) if 'calcular_edad_desde_cumple' in globals() else 30

    if edad_calculada < 18:
        context.user_data['ing_cintura'] = 0.0
        context.user_data['ing_cuello'] = 0.0
        context.user_data['ing_cadera'] = 0.0

        btn_r1 = traducciones.get('09_btn_ritmo_tranquilo', "🟢 Tranquilo / Lento")
        btn_r2 = traducciones.get('09_btn_ritmo_moderado', "🟡 Moderado")
        btn_r3 = traducciones.get('09_btn_ritmo_intenso', "🔴 Intenso / Rápido")
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(btn_r1, callback_data="ritmo_tranquilo")],
            [InlineKeyboardButton(btn_r2, callback_data="ritmo_moderado")],
            [InlineKeyboardButton(btn_r3, callback_data="ritmo_intenso")]
        ])
        
        txt_ped_tpl = traducciones.get("09_ing_perfil_pediatrico_ritmo", "👶 **Perfil pediátrico/juvenil detectado ({edad_calculada} años).**\nSe adaptarán los cálculos a los estándares pediátricos de la OMS sin requerir medidas corporales.\n\nSeleccioná el **ritmo para tu plan**. Esto define el déficit/superávit de tus calorías:\n• *🟢 Tranquilo (Cambios muy graduales, súper fácil de sostener).*\n• *🟡 Moderado (Equilibrio ideal entre resultados y adherencia).*\n• *🔴 Intenso (Exigente, para resultados más rápidos).*\n\n🎯 Seleccioná tu ritmo deseado:")
        txt_ped = txt_ped_tpl.format(edad_calculada=edad_calculada).replace('\\n', '\n')
        await update.message.reply_text(txt_ped, reply_markup=keyboard, parse_mode="Markdown")
        return ING_RITMO

    es_mujer = context.user_data.get('ing_sexo', 'M') == 'F'
    if es_mujer:
        tip_cintura = traducciones.get("09_ing_tip_cintura_fem", "📏 *Tip de medición: Medí en la parte más estrecha de tu torso, generalmente a medio camino entre las costillas inferiores y el ombligo.*")
    else:
        tip_cintura = traducciones.get("09_ing_tip_cintura_masc", "📏 *Tip de medición: Pasá la cinta métrica exactamente a la altura del ombligo, asegurándote de que esté horizontal y sin hundir el estómago.*")
        
    txt_cint_tpl = traducciones.get("09_ing_ingresa_cintura", "Ingresá el **perímetro de tu cintura en cm** (ejemplo: `85`):\n\n{tip_cintura}")
    await update.message.reply_text(txt_cint_tpl.format(tip_cintura=tip_cintura).replace('\\n', '\n'), parse_mode="Markdown")
    return ING_MUNECA

async def ing_recibir_muneca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().replace(',', '.')
    lang = context.user_data.get('ing_idioma', 'es')
    traducciones = obtener_traducciones_db(lang) or {}
    
    try:
        cintura = float(txt)
        if not (50 <= cintura <= 200): raise ValueError()
    except ValueError:
        txt_err_cin = traducciones.get("09_ing_err_cintura_valida", "⚠️ Ingresá un perímetro de cintura válido en cm (ejemplo: `85`).")
        await update.message.reply_text(txt_err_cin, parse_mode="Markdown")
        return ING_MUNECA

    context.user_data['ing_cintura'] = cintura

    tip_cuello = traducciones.get("09_ing_tip_cuello", "📐 *Tip de medición: Mirá al frente con los hombros relajados (no levantes ni bajes la cabeza). Colocá la cinta justo debajo de la nuez de Adán, lo más horizontal posible.*")
    
    txt_cue_tpl = traducciones.get("09_ing_ingresa_cuello", "Ingresá el **perímetro de tu cuello en cm** (ejemplo: `38`):\n\n{tip_cuello}")
    await update.message.reply_text(txt_cue_tpl.format(tip_cuello=tip_cuello).replace('\\n', '\n'), parse_mode="Markdown")
    return ING_CUELLO

async def ing_recibir_cuello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().replace(',', '.')
    lang = context.user_data.get('ing_idioma', 'es')
    traducciones = obtener_traducciones_db(lang) or {}

    try:
        cuello = float(txt)
        if not (20 <= cuello <= 60): raise ValueError()
    except ValueError:
        txt_err_cue = traducciones.get("09_ing_err_cuello_valido", "⚠️ Ingresá un perímetro de cuello válido en cm (ejemplo: `38`).")
        await update.message.reply_text(txt_err_cue, parse_mode="Markdown")
        return ING_CUELLO

    context.user_data['ing_cuello'] = cuello

    if context.user_data.get('ing_sexo', 'M') == 'F':

        tip_cadera = traducciones.get("09_ing_tip_cadera", "📏 *Tip de medición: Juntá los pies y pasá la cinta por la parte más ancha de los glúteos y caderas, manteniéndola paralela al piso.*")
        txt_cad_tpl = traducciones.get("09_ing_ingresa_cadera", "Ingresá el **perímetro de tu cadera en cm** (ejemplo: `100`):\n\n{tip_cadera}")
        await update.message.reply_text(txt_cad_tpl.format(tip_cadera=tip_cadera).replace('\\n', '\n'), parse_mode="Markdown")
        return ING_CADERA

    btn_r1 = traducciones.get('09_btn_ritmo_tranquilo', "🟢 Tranquilo / Lento")
    btn_r2 = traducciones.get('09_btn_ritmo_moderado', "🟡 Moderado")
    btn_r3 = traducciones.get('09_btn_ritmo_intenso', "🔴 Intenso / Rápido")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_r1, callback_data="ritmo_tranquilo")],
        [InlineKeyboardButton(btn_r2, callback_data="ritmo_moderado")],
        [InlineKeyboardButton(btn_r3, callback_data="ritmo_intenso")]
    ])
    
    txt_ritmo = traducciones.get("09_ing_selecciona_ritmo", "Seleccioná el **ritmo para tu plan**. Esto define el déficit/superávit de tus calorías:\n• *🟢 Tranquilo (Cambios muy graduales, súper fácil de sostener).*\n• *🟡 Moderado (Equilibrio ideal entre resultados y adherencia).*\n• *🔴 Intenso (Exigente, para resultados más rápidos).*\n\n🎯 Seleccioná tu ritmo deseado:").replace('\\n', '\n')
    await update.message.reply_text(txt_ritmo, reply_markup=keyboard, parse_mode="Markdown")
    return ING_RITMO

async def ing_recibir_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.text.strip()
    lang = context.user_data.get('ing_idioma', 'es')
    traducciones = obtener_traducciones_db(lang) or {}

    if len(nombre) < 2:
        txt_err_nom = traducciones.get("09_ing_err_nombre_valido", "⚠️ Por favor, ingresá un nombre válido.")
        await update.message.reply_text(txt_err_nom)
        return ING_NOMBRE
    
    context.user_data['ing_nombre'] = nombre
    
    btn_masc = traducciones.get("09_ing_btn_masculino", "Masculino 👨")
    btn_fem = traducciones.get("09_ing_btn_femenino", "Femenino 👩")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_masc, callback_data="sexo_M"),
         InlineKeyboardButton(btn_fem, callback_data="sexo_F")]
    ])
    
    txt_sex = traducciones.get("09_ing_selecciona_sexo", "Seleccioná tu **sexo biológico**:")
    await update.message.reply_text(txt_sex, reply_markup=keyboard, parse_mode="Markdown")
    return ING_SEXO

async def ing_recibir_sexo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get('ing_idioma', 'es')
    traducciones = obtener_traducciones_db(lang) or {}

    sexo = "M" if query.data == "sexo_M" else "F"
    context.user_data['ing_sexo'] = sexo
    
    txt_fec = traducciones.get("09_ing_ingresa_cumple", "Ahora ingresá tu **fecha de nacimiento** en formato `AAAA-MM-DD` (ejemplo: `1985-04-12`):")
    await query.edit_message_text(txt_fec, parse_mode="Markdown")
    return ING_CUMPLE
    
async def ing_recibir_peso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().replace(',', '.')
    lang = context.user_data.get('ing_idioma', 'es')
    traducciones = obtener_traducciones_db(lang) or {}

    try:
        peso = float(txt)
        if not (30 <= peso <= 300): raise ValueError()
    except ValueError:
        txt_err_peso = traducciones.get("09_ing_err_peso_valido", "⚠️ Ingresá un peso válido en kg (ejemplo: `75.4`).")
        await update.message.reply_text(txt_err_peso, parse_mode="Markdown")
        return ING_PESO

    context.user_data['ing_peso'] = peso
    
    txt_alt = traducciones.get("09_ing_ingresa_altura", "Ingresá tu **altura en centímetros** (ejemplo: `175` para 1,75 m):")
    await update.message.reply_text(txt_alt, parse_mode="Markdown")
    return ING_ALTURA
    
async def ing_recibir_altura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().replace(',', '.')
    lang = context.user_data.get('ing_idioma', 'es')
    traducciones = obtener_traducciones_db(lang) or {}

    try:
        alt = float(txt)
        if not (100 <= alt <= 230): raise ValueError()
    except ValueError:
        txt_err_alt = traducciones.get('09_ing_error_altura_valida', "⚠️ Ingresá una altura válida en centímetros (ejemplo: `170`).")
        await update.message.reply_text(txt_err_alt, parse_mode="Markdown")
        return ING_ALTURA

    context.user_data['ing_altura'] = alt
    user_id = update.effective_user.id

    prof_oficial = context.user_data.get('ing_profesional_oficial', '123456789')
    prof_pendiente = context.user_data.get('ing_profesional_pendiente', None)

    datos_usuario = {
        "user_id": user_id,
        "nombre": context.user_data.get('ing_nombre'),
        "sexo": context.user_data.get('ing_sexo'),
        "cumple": context.user_data.get('ing_cumple'),
        "profesional": prof_oficial,
        "profesional_pendiente": prof_pendiente,
        "cintura": context.user_data.get('ing_cintura', 0.0),
        "cuello": context.user_data.get('ing_cuello', 0.0),
        "cadera": context.user_data.get('ing_cadera', 0.0),
        "ritmo": context.user_data.get('ing_ritmo', 'moderado'),
        "idioma": lang,
        "ocupacion": context.user_data.get('ing_ocupacion', 1.375),
        "peso": context.user_data.get('ing_peso'),
        "altura": context.user_data.get('ing_altura')
    }

    datos_usuario["edad"] = calcular_edad_desde_cumple(datos_usuario["cumple"]) if 'calcular_edad_desde_cumple' in globals() else 40
    datos_usuario["peso_ideal"] = round(calcular_peso_ideal(datos_usuario["sexo"], datos_usuario["altura"], edad=datos_usuario["edad"]), 1)
    datos_usuario["peso_etapa"] = calcular_peso_etapa(datos_usuario["peso"], datos_usuario["peso_ideal"], datos_usuario["ritmo"]) if 'calcular_peso_etapa' in globals() else datos_usuario["peso"]
    
    genero_str = "femenino" if str(datos_usuario["sexo"]).upper() in ["F", "FEMENINO", "MUJER"] else "masculino"
    tmb, get_calorias = calcular_tmb_y_get(
        peso_actual=datos_usuario["peso"], 
        altura_cm=datos_usuario["altura"], 
        edad=datos_usuario["edad"], 
        genero=genero_str, 
        actividad=datos_usuario["ocupacion"],
        cadera_cm=datos_usuario["cadera"]
    )

    datos_usuario["tmb"] = tmb
    datos_usuario["get"] = get_calorias

    ritmo_cap = str(datos_usuario["ritmo"]).capitalize()
    txt_procesando = traducciones.get('09_ing_procesando_informe_ia', 
        "✅ Datos completados.\n\n⏳ *Creando planillas y redactando tu informe inicial personalizado con IA...*"
    )
    msg_espera = await update.message.reply_text(txt_procesando, parse_mode="Markdown")

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, cmd_nuevo_usuario, datos_usuario)
        
        _, pdf_buf = await procesar_informe_inicial(datos_usuario) if 'procesar_informe_inicial' in globals() else (None, None)
        
        await msg_espera.delete()
        
        aviso_medico_alta = ""
        if prof_pendiente and prof_pendiente != "123456789":
            aviso_medico_alta = "\n\n🩺 *Nota:* Se ha enviado una solicitud a tu médico tratante para que audite y confirme tu seguimiento. Tu cuenta ya se encuentra activa de forma autónoma."

        resumen_plantilla = traducciones.get('09_ing_resumen_cuenta_lista', 
            "🎉 **¡Tu cuenta y planillas están listas!**\n\n"
            "👤 **Paciente:** {nombre} | **ID:** `{user_id}`\n"
            "⚖️ **Peso Actual:** `{peso} kg` ➔ **Objetivo Etapa 1:** `{peso_etapa} kg`\n"
            "🎯 **Ritmo Elegido:** `{ritmo_cap}`\n"
            "🔥 **TMB:** `{tmb_rnd} kcal` | **GET:** `{get_rnd} kcal`\n\n"
            "📄 *Te hemos enviado tu informe nutricional inicial detallado en formato PDF ajustado a tu ritmo.*"
        ).format(
            nombre=datos_usuario['nombre'],
            user_id=user_id,
            peso=datos_usuario['peso'],
            peso_etapa=datos_usuario['peso_etapa'],
            ritmo_cap=ritmo_cap,
            tmb_rnd=round(tmb),
            get_rnd=round(get_calorias)
        ).replace('\\n', '\n')

        # NUEVO: Agregamos el aviso corto del plan gratuito a continuación
        aviso_plan_corto = traducciones.get(
            '09_ing_aviso_plan_gratuito',
            "\n\n🎁 **Tu Plan Actual: Gratuito**\n"
            "Para conservar este beneficio, tu único compromiso es la constancia: debés registrar tus ingestas un mínimo de **12 días por quincena** (tenés 3 días libres). Si acumulás 4 días de inactividad, el plan gratuito se desactiva."
        ).replace('\\n', '\n')

        mensaje_final_completo = resumen_plantilla + aviso_plan_corto + aviso_medico_alta
        await update.message.reply_text(mensaje_final_completo, parse_mode="Markdown")

        if pdf_buf:
            filename_pdf = f"I_{user_id}.pdf"
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=pdf_buf,
                filename=filename_pdf
            )

        if prof_pendiente and prof_pendiente != "123456789":
            try:
                btn_med_aceptar = traducciones.get("09_ing_btn_medico_aceptar", "✅ Aceptar Paciente")
                btn_med_rechazar = traducciones.get("09_ing_btn_medico_rechazar", "❌ Rechazar")
                
                keyboard_medico = InlineKeyboardMarkup([
                    [InlineKeyboardButton(btn_med_aceptar, callback_data=f"medico_aceptar_{user_id}")],
                    [InlineKeyboardButton(btn_med_rechazar, callback_data=f"medico_rechazar_{user_id}")]
                ])
                
                msg_solicitud_tpl = traducciones.get(
                    "09_ing_msg_solicitud_medico", 
                    "🩺 **Nueva Solicitud de Seguimiento Clínico**\n\nEl usuario **{nombre}** (ID: `{user_id}`) ha solicitado que usted sea su profesional a cargo y supervise su plan nutricional.\n\n• ⚖️ Peso Inicial: `{peso} kg`\n• 📏 Altura: `{altura} cm`\n\n¿Desea aceptar la supervisión de este paciente?"
                )
                msg_solicitud = msg_solicitud_tpl.format(
                    nombre=datos_usuario['nombre'],
                    user_id=user_id,
                    peso=datos_usuario['peso'],
                    altura=datos_usuario['altura']
                ).replace('\\n', '\n')
                
                await context.bot.send_message(
                    chat_id=int(prof_pendiente), 
                    text=msg_solicitud, 
                    reply_markup=keyboard_medico, 
                    parse_mode="Markdown"
                )
            except Exception as e_prof:
                logger.error(f"No se pudo enviar la solicitud de supervisión al profesional {prof_pendiente}: {e_prof}")

    except Exception as e:
        logger.error(f"Error al registrar cuenta final o PDF para {user_id}: {e}")
        txt_err_gen = traducciones.get('09_ing_error_proceso_general', "❌ Ocurrió un error al procesar el ingreso: {e}").format(e=e)
        await update.message.reply_text(txt_err_gen, parse_mode="Markdown")

    context.user_data.clear()
    return ConversationHandler.END
    
def cmd_nuevo_usuario(datos_usuario):
    user_id = datos_usuario.get("user_id")
    nombre = datos_usuario.get("nombre")
    sexo = datos_usuario.get("sexo", "M")
    cumple = datos_usuario.get("cumple", "")
    profesional = datos_usuario.get("profesional", "123456789")
    profesional_pendiente = datos_usuario.get("profesional_pendiente", None)
    cintura = float(datos_usuario.get("cintura", 0))
    cuello = float(datos_usuario.get("cuello", 0))
    cadera = float(datos_usuario.get("cadera", 0))
    ritmo = datos_usuario.get("ritmo", "moderado")
    idioma = str(datos_usuario.get("idioma", "ES")).upper()
    ocupacion = float(datos_usuario.get("ocupacion", 1.375))
    peso = float(datos_usuario.get("peso", 0))
    altura = float(datos_usuario.get("altura", 0))

    edad = calcular_edad_desde_cumple(cumple)
    mes_actual = datetime.now(ARG_TZ).strftime("%Y-%m")
    fecha_alta = datetime.now(ARG_TZ).strftime("%Y-%m-%d")

    try:
        conn_u, cur_u = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        
        # Asegurar que exista la columna profesional_pendiente por seguridad
        try:
            cur_u.execute('ALTER TABLE "Usuarios" ADD COLUMN IF NOT EXISTS "profesional_pendiente" TEXT;')
            conn_u.commit()
        except Exception:
            conn_u.rollback()

        cur_u.execute('SELECT COUNT(*) FROM "Usuarios" WHERE "User ID" = %s', (str(user_id),))
        existe = cur_u.fetchone()[0] > 0

        if existe:
            query_usr = """
                UPDATE "Usuarios" SET
                    "Nombre" = %s, "Estado" = %s, "Ultimo Mes Peso" = %s, "Notificaciones" = %s,
                    "Fecha Alta" = %s, "Sexo" = %s, "cumple" = %s, "profesional" = %s,
                    "profesional_pendiente" = %s, "cintura_cm" = %s, "cuello_cm" = %s, 
                    "cadera_cm" = %s, "ritmo_preferido" = %s, "Idioma" = %s
                WHERE "User ID" = %s
            """
            valores_usr = (nombre, 0, mes_actual, "Si", fecha_alta, sexo, cumple, profesional, profesional_pendiente, cintura, cuello, cadera, ritmo, idioma, str(user_id))
        else:
            query_usr = """
                INSERT INTO "Usuarios" ("User ID", "Nombre", "Estado", "Ultimo Mes Peso", "Notificaciones", "Fecha Alta", "Sexo", "cumple", "profesional", "profesional_pendiente", "cintura_cm", "cuello_cm", "cadera_cm", "ritmo_preferido", "Idioma")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            valores_usr = (str(user_id), nombre, 0, mes_actual, "Si", fecha_alta, sexo, cumple, profesional, profesional_pendiente, cintura, cuello, cadera, ritmo, idioma)

        cur_u.execute(query_usr, valores_usr)
        conn_u.commit()
        cur_u.close()
        conn_u.close()
    except Exception as e:
        logger.error(f"Error alta tabla Usuarios: {e}")

    try:
        tabla_perfil = f"Perfil_{user_id}"
        conn_p, cur_p = _asegurar_tabla_y_conectar(tabla_perfil, tipo_tabla="perfil")
        cur_p.execute(f"""
            INSERT INTO "{tabla_perfil}" ("EDAD", "PESO", "ALTURA", "GENERO", "ocupacion", "MES", "Fecha_Actualizacion", "Cumple")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (str(edad), peso, altura, sexo, ocupacion, mes_actual, fecha_alta, cumple))
        conn_p.commit()
        cur_p.close()
        conn_p.close()
    except Exception as e:
        logger.error(f"Error alta tabla Perfil: {e}")

#                       INICIO                        COMANDOS PERFIL                           INICIO
# ======================================================================================================================================
        
# ======================================================================================================================================
#                       INICIO                        COMANDOS PERFIL (CORREGIDO)                   INICIO
# ======================================================================================================================================
        
@requiere_registro
async def cmd_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    
    ahora = obtener_ahora_arg()
    mes_actual = ahora.strftime("%Y-%m")

    if '_garantizar_fila_mes_actual' in globals():
        _garantizar_fila_mes_actual(user_id, ahora)

    try:
        perfil_completo = obtener_datos_completos_usuario(user_id, mes_target=mes_actual) if 'obtener_datos_completos_usuario' in globals() else obtener_perfil_usuario(user_id, mes_target=mes_actual)

        # Etiquetas traducibles (se usan tanto en el texto como en los botones)
        lbl_nombre = traducciones.get('09_perfil_lbl_nombre', 'Nombre')
        lbl_edad = traducciones.get('09_perfil_lbl_edad', 'Edad')
        lbl_peso = traducciones.get('09_perfil_lbl_peso', 'Peso')
        lbl_altura = traducciones.get('09_perfil_lbl_altura', 'Altura')
        lbl_cintura = traducciones.get('09_perfil_lbl_cintura', 'Cintura')
        lbl_cuello = traducciones.get('09_perfil_lbl_cuello', 'Cuello')
        lbl_cadera = traducciones.get('09_perfil_lbl_cadera', 'Cadera')
        lbl_ritmo = traducciones.get('09_perfil_lbl_ritmo', 'Ritmo')
        lbl_idioma = traducciones.get('09_perfil_lbl_idioma', 'Idioma')
        lbl_prof = traducciones.get('09_perfil_lbl_profesional', 'Profesional')

        if perfil_completo:
            peso = parse_raw_val(perfil_completo.get('PESO', perfil_completo.get('Peso', 0)))
            altura = parse_raw_val(perfil_completo.get('ALTURA', perfil_completo.get('Altura', 0)))
            edad = parse_raw_val(perfil_completo.get('EDAD', perfil_completo.get('Edad', 0)))
            genero = str(perfil_completo.get('GENERO', perfil_completo.get('Sexo', 'M')))
            
            is_fem = genero.strip().upper() in ['F', 'FEMENINO', 'MUJER']
            es_adulto = (edad >= 18)

            ocupacion = parse_raw_val(perfil_completo.get('ocupacion', perfil_completo.get('OCUPACION', 1.375)))
            if ocupacion > 10: ocupacion = ocupacion / 1000.0
            
            txt_no_reg = traducciones.get('09_perfil_fecha_no_reg', 'No registrada')
            fecha_act_peso = perfil_completo.get('Fecha_Actualizacion', txt_no_reg)
            if fecha_act_peso == 'S/D' or not fecha_act_peso:
                fecha_act_peso = txt_no_reg

            nombre = perfil_completo.get('Nombre', 'S/D')
            cintura = perfil_completo.get('cintura_cm', 0.0)
            cuello = perfil_completo.get('cuello_cm', 0.0)
            cadera = perfil_completo.get('cadera_cm', 0.0)
            ritmo = perfil_completo.get('ritmo_preferido', 'moderado')
            profesional = perfil_completo.get('profesional', 'S/D')
            idioma_usr = perfil_completo.get('Idioma', lang)

            tmb, get_val = calcular_tmb_y_get(peso, altura, int(edad), genero, ocupacion, cadera_cm=cadera)
            peso_ideal = calcular_peso_ideal(genero, altura, edad=int(edad))
            peso_etapa = calcular_peso_etapa(peso, peso_ideal, ritmo)

            lineas_medidas = ""
            if es_adulto:
                lineas_medidas += f"• 📏 {lbl_cintura}: `{cintura:.1f}` cm\n• 📐 {lbl_cuello}: `{cuello:.1f}` cm\n"
                if is_fem:
                    lineas_medidas += f"• 📐 {lbl_cadera}: `{cadera:.1f}` cm\n"
            else:
                txt_pediatrico = traducciones.get('09_perfil_mod_pediatrica', 'Modalidad Pediátrica/Juvenil (Cálculo OMS sin circunferencias)')
                lineas_medidas = f"• *{txt_pediatrico}*\n"

            alerta_medidas = ""
            if es_adulto:
                if cintura <= 1.0 or cuello <= 1.0 or (is_fem and cadera <= 1.0):
                    txt_alerta_med = traducciones.get(
                        '09_perfil_alerta_medidas',
                        "⚠️ **Atención:** Tenés 18 años o más. Actualizá tus medidas con los botones de abajo para activar el cálculo de masa magra de alta precisión clínica."
                    )
                    alerta_medidas = f"\n{txt_alerta_med}\n"

            lbl_tmb = traducciones.get('09_perfil_lbl_tmb', 'TMB Estimada')
            lbl_get = traducciones.get('09_perfil_lbl_get', 'GET Estimado')
            lbl_meta = traducciones.get('09_perfil_lbl_meta', 'Meta / Peso de Etapa')
            lbl_act = traducciones.get('09_perfil_lbl_act', 'Act')

            txt_perfil = (
                f"👤 **{traducciones.get('09_perfil_titulo_biometrico', 'Perfil Biométrico Actual')} ({mes_actual}):**\n\n"
                f"• 👤 {lbl_nombre}: `{nombre}`\n"
                f"• 🎯 {lbl_edad}: `{edad:.0f}` {traducciones.get('09_perfil_anos', 'años')}\n"
                f"• ⚖️ {lbl_peso}: `{peso:.1f}` kg *({lbl_act}: {fecha_act_peso})*\n"
                f"• 📏 {lbl_altura}: `{altura:.1f}` cm\n"
                f"{lineas_medidas}"
                f"• 🎯 {lbl_ritmo}: `{str(ritmo).capitalize()}`\n"
                f"• 🌐 {lbl_idioma}: `{str(idioma_usr).upper()}`\n"
                f"• 🩺 {lbl_prof}: `{profesional}`\n\n"
                f"• 🔥 **{lbl_tmb}:** `{tmb:.0f} kcal/día`\n"
                f"• ⚡ **{lbl_get}:** `{get_val:.0f} kcal/día`\n"
                f"• 🎯 **{lbl_meta}:** `{peso_etapa:.1f} kg`\n"
                f"{alerta_medidas}"
            )
        else:
            txt_perfil = traducciones.get('09_perfil_no_registrado', "👤 **Perfil no registrado para este mes.** Podés cargar tu peso ejecutando:\n`/peso 82.5`")

        # Botonera clara con Ícono + Nombre traducido
        keyboard = [
            [
                InlineKeyboardButton(f"⚖️ {lbl_peso}", callback_data="edit_perfil_peso"),
                InlineKeyboardButton(f"📏 {lbl_altura}", callback_data="edit_perfil_altura")
            ]
        ]

        if es_adulto:
            fila_cintas = [
                InlineKeyboardButton(f"📏 {lbl_cintura}", callback_data="edit_perfil_cintura"),
                InlineKeyboardButton(f"📐 {lbl_cuello}", callback_data="edit_perfil_cuello")
            ]
            keyboard.append(fila_cintas)
            if is_fem:
                keyboard.append([InlineKeyboardButton(f"📐 {lbl_cadera}", callback_data="edit_perfil_cadera")])

        keyboard.extend([
            [
                InlineKeyboardButton(f"🎯 {lbl_ritmo}", callback_data="edit_perfil_ritmo"),
                InlineKeyboardButton(f"🌐 {lbl_idioma}", callback_data="edit_perfil_idioma")
            ],
            [
                InlineKeyboardButton(f"👤 {lbl_nombre}", callback_data="edit_perfil_nombre"),
                InlineKeyboardButton(f"🩺 {lbl_prof}", callback_data="edit_perfil_prof")
            ]
        ])
        markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(txt_perfil.replace('\\n', '\n'), reply_markup=markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error al consultar perfil: {e}")
        txt_err_read = traducciones.get('09_perfil_error_lectura', "⚠️ Ocurrió un error al leer tu perfil: {e}").format(e=e)
        await update.message.reply_text(txt_err_read, parse_mode="Markdown")
        
async def cmd_cancelar_conversacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    
    user_id = update.effective_user.id if update.effective_user else None
    lang = obtener_idioma_usuario(user_id) if user_id else 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    
    txt_cancelada = traducciones.get("09_bot_operacion_cancelada", "❌ Operación cancelada.")

    if update.message:
        await update.message.reply_text(txt_cancelada, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(txt_cancelada, parse_mode="Markdown")
    return ConversationHandler.END
    
def actualizar_ritmo_usuario(user_id, nuevo_ritmo):
    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        cur.execute('UPDATE "Usuarios" SET "ritmo_preferido" = %s WHERE "User ID" = %s', (str(nuevo_ritmo), str(user_id)))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error al actualizar ritmo para {user_id}: {e}")

def actualizar_idioma_usuario(user_id, nuevo_idioma):
    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        cur.execute('UPDATE "Usuarios" SET "Idioma" = %s WHERE "User ID" = %s', (str(nuevo_idioma), str(user_id)))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error al actualizar idioma para {user_id}: {e}")


@requiere_registro
async def callback_handler_editar_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    if data == "edit_perfil_peso":
        context.user_data['awaiting_edit_perfil_peso'] = True
        msg = await query.message.reply_text(traducciones.get('09_solic_peso', "⚖️ Por favor, ingresá tu nuevo peso en kg (ej: `78.5`):"), parse_mode="Markdown")
        context.user_data['msg_solicitud_perfil_id'] = msg.message_id
    elif data == "edit_perfil_altura":
        context.user_data['awaiting_edit_perfil_altura'] = True
        msg = await query.message.reply_text(traducciones.get('09_solic_altura', "📏 Por favor, ingresá tu nueva altura en cm (ej: `175`):"), parse_mode="Markdown")
        context.user_data['msg_solicitud_perfil_id'] = msg.message_id
    elif data == "edit_perfil_cintura":
        context.user_data['awaiting_edit_perfil_cintura'] = True
        msg = await query.message.reply_text(traducciones.get('09_solic_cintura', "📏 Por favor, ingresá el nuevo perímetro de tu cintura en cm (ej: `84`):"), parse_mode="Markdown")
        context.user_data['msg_solicitud_perfil_id'] = msg.message_id
    elif data == "edit_perfil_cuello":
        context.user_data['awaiting_edit_perfil_cuello'] = True
        msg = await query.message.reply_text(traducciones.get('09_solic_cuello', "📐 Por favor, ingresá el nuevo perímetro de tu cuello en cm (ej: `37`):"), parse_mode="Markdown")
        context.user_data['msg_solicitud_perfil_id'] = msg.message_id
    elif data == "edit_perfil_cadera":
        context.user_data['awaiting_edit_perfil_cadera'] = True
        msg = await query.message.reply_text(traducciones.get('09_solic_cadera', "📐 Por favor, ingresá el nuevo perímetro de tu cadera en cm (ej: `104`):"), parse_mode="Markdown")
        context.user_data['msg_solicitud_perfil_id'] = msg.message_id
    elif data == "edit_perfil_nombre":
        context.user_data['awaiting_edit_perfil_nombre'] = True
        msg = await query.message.reply_text(traducciones.get('09_solic_nombre', "👤 Por favor, ingresá tu nuevo Nombre y Apellido:"), parse_mode="Markdown")
        context.user_data['msg_solicitud_perfil_id'] = msg.message_id
    elif data == "edit_perfil_prof":
        context.user_data['awaiting_edit_perfil_prof'] = True
        msg = await query.message.reply_text(traducciones.get('09_solic_prof', "🩺 Por favor, ingresá el ID de Telegram de tu nuevo profesional:"), parse_mode="Markdown")
        context.user_data['msg_solicitud_perfil_id'] = msg.message_id
    elif data == "edit_perfil_ritmo":
        btn_r1 = traducciones.get('09_btn_ritmo_tranquilo', "🟢 Tranquilo / Lento")
        btn_r2 = traducciones.get('09_btn_ritmo_moderado', "🟡 Moderado")
        btn_r3 = traducciones.get('09_btn_ritmo_intenso', "🔴 Intenso / Rápido")
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(btn_r1, callback_data="set_ritmo_1")],
            [InlineKeyboardButton(btn_r2, callback_data="set_ritmo_2")],
            [InlineKeyboardButton(btn_r3, callback_data="set_ritmo_3")]
        ])
        await query.message.reply_text(traducciones.get('09_solic_ritmo', "🎯 Seleccioná tu nuevo ritmo de avance deseado:"), reply_markup=keyboard, parse_mode="Markdown")
    elif data == "edit_perfil_idioma":
        idiomas_disp = await obtener_idiomas_disponibles_db() if 'obtener_idiomas_disponibles_db' in globals() else [{'codigo': 'es', 'nombre': 'Español', 'bandera': '🇪🇸'}, {'codigo': 'en', 'nombre': 'English', 'bandera': '🇺🇸'}]
        b_list = [[InlineKeyboardButton(f"{i['bandera']} {i['nombre']}", callback_data=f"set_lang_{i['codigo']}")] for i in idiomas_disp]
        await query.message.reply_text(traducciones.get('09_solic_idioma', "🌐 Seleccioná tu idioma preferido:"), reply_markup=InlineKeyboardMarkup(b_list), parse_mode="Markdown")
    elif data.startswith("set_ritmo_"):
        val_r = data.replace("set_ritmo_", "")
        ritmos_map = {"1": "tranquilo", "2": "moderado", "3": "intenso"}
        ritmo_txt = ritmos_map.get(val_r, "moderado")
        actualizar_ritmo_usuario(user_id, ritmo_txt)
        msg_ok = traducciones.get('09_ritmo_actualizado_ok', "✅ ¡Ritmo actualizado exitosamente a *{ritmo}*!").format(ritmo=ritmo_txt.capitalize())
        await query.edit_message_text(msg_ok, parse_mode="Markdown")
    elif data.startswith("set_lang_"):
        nuevo_lang = data.replace("set_lang_", "")
        actualizar_idioma_usuario(user_id, nuevo_lang)
        trad_nuevas = obtener_traducciones_db(nuevo_lang) if 'obtener_traducciones_db' in globals() else traducciones
        msg_ok = trad_nuevas.get('09_idioma_actualizado_ok', "✅ ¡Idioma actualizado exitosamente a *{lang}*!").format(lang=nuevo_lang.upper())
        await query.edit_message_text(msg_ok, parse_mode="Markdown")
        
#                       INICIO                        COMANDOS BIOMETRICOS                           INICIO
# ======================================================================================================================================

@requiere_registro
async def cmd_peso_rapido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    texto_mensaje = update.message.text.strip() if update.message and update.message.text else ""
    raw_text = ""
    for cmd in ['/peso', '/weight']:
        if texto_mensaje.lower().startswith(cmd):
            raw_text = texto_mensaje[len(cmd):].strip()
            break

    ahora = obtener_ahora_arg()
    mes_actual = ahora.strftime("%Y-%m")

    if '_garantizar_fila_mes_actual' in globals():
        _garantizar_fila_mes_actual(user_id, ahora)

    if not raw_text:
        perfil = obtener_perfil_usuario(user_id, mes_target=mes_actual) or {}
        peso_base = parse_raw_val(perfil.get('PESO', perfil.get('Peso', 0))) if perfil else 0
        ultimo_informado = parse_raw_val(perfil.get('peso_actual', 0)) if perfil else 0
        
        if peso_base > 0:
            txt_peso_base = traducciones.get('09_peso_base_reg', "⚖️ **Peso base registrado ({mes}):** `{peso:.1f} kg`").format(mes=mes_actual, peso=peso_base)
            txt_actual = f"{txt_peso_base}\n"
            if ultimo_informado > 0 and ultimo_informado != peso_base:
                txt_ult_inf = traducciones.get('09_peso_ult_inf', "📊 **Último peso informado en el mes:** `{peso:.1f} kg`").format(peso=ultimo_informado)
                txt_actual += f"{txt_ult_inf}\n"
            
            dia_actual = ahora.day
            if dia_actual <= 14:
                txt_prox = traducciones.get('09_peso_prox_quincena', "\n⏳ *Tu próximo control de peso se habilitará a partir del día 15.*")
                txt_actual += txt_prox
            elif 15 <= dia_actual <= 25:
                txt_ing_quinc = traducciones.get('09_peso_ingreso_quincenal', "\nPara ingresar tu control quincenal y calibrar tu factor, escribí:\n`/peso [nuevo_peso]` (ejemplo: `/peso 96`)")
                txt_actual += txt_ing_quinc
            else:
                txt_ing_cierre = traducciones.get('09_peso_ingreso_cierre', "\nPara ingresar tu peso de cierre de mes, escribí:\n`/peso [nuevo_peso]` (ejemplo: `/peso 96`)")
                txt_actual += txt_ing_cierre
        else:
            txt_actual = traducciones.get('09_peso_no_registrado', "⚠️ No tenés un peso registrado para este mes.\n\nPara registrarlo, escribí:\n`/peso [tu_peso]` (ejemplo: `/peso 100`)")
        
        await update.message.reply_text(txt_actual.replace('\\n', '\n'), parse_mode="Markdown")
        return

    try:
        texto_limpio = raw_text.split()[0].replace(',', '.')
        nuevo_peso = float(texto_limpio)
        
        if not (30 <= nuevo_peso <= 300):
            raise ValueError()

        res_cal = guardar_perfil_db(user_id, peso=nuevo_peso, mes=mes_actual)
        await update.message.reply_text(res_cal["mensaje"], parse_mode="Markdown")

    except ValueError:
        txt_err = traducciones.get('09_peso_error_valido', "⚠️ Por favor, ingresá un peso válido en kg entre 30 y 300 (ejemplo: `/peso 82.5`).")
        await update.message.reply_text(txt_err, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error en cmd_peso_rapido para {user_id}: {e}")
        txt_err_guardar = traducciones.get('09_peso_error_guardar', "❌ Error al guardar el peso: {e}").format(e=e)
        await update.message.reply_text(txt_err_guardar)
                                      
async def mostrar_resumen_presion_mes(query_or_update, user_id, mes_str):
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    df_presion = obtener_datos_presion_db(user_id)
    if df_presion.empty:
        txt = traducciones.get('09_presi_sin_registros_usr', "🩺 No se encontraron registros de presión para el usuario `{user_id}`.").format(user_id=user_id)
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(txt, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(txt, parse_mode="Markdown")
        return

    df_p_mes = df_presion[df_presion['Fecha_Dia'].str.startswith(mes_str)] if 'Fecha_Dia' in df_presion.columns else pd.DataFrame()
    if df_p_mes.empty:
        txt = traducciones.get('09_presi_sin_registros_mes', "🩺 No se encontraron registros de presión para el mes `{mes}`.").format(mes=mes_str)
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(txt, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(txt, parse_mode="Markdown")
        return

    alta_prom = df_p_mes['Alta'].mean()
    baja_prom = df_p_mes['Baja'].mean()
    pul_prom = df_p_mes[df_p_mes['Pulsaciones'] > 0]['Pulsaciones'].mean() if 'Pulsaciones' in df_presion.columns else 0

    titulo_resumen = traducciones.get('09_presi_resumen_titulo', "🩺 <b>Resumen de Presión Arterial ({mes}):</b>").format(mes=mes_str)
    mediciones_reg = traducciones.get('09_presi_mediciones_reg', "• Mediciones registradas: `{cant}`").format(cant=len(df_p_mes))
    prom_alta = traducciones.get('09_presi_prom_alta', "• <b>Promedio Alta (Sistólica):</b> `{alta:.1f} mmHg`").format(alta=alta_prom)
    prom_baja = traducciones.get('09_presi_prom_baja', "• <b>Promedio Baja (Diastólica):</b> `{baja:.1f} mmHg`").format(baja=baja_prom)
    
    txt = f"{titulo_resumen}\n\n{mediciones_reg}\n{prom_alta}\n{prom_baja}\n"

    if pul_prom > 0:
        prom_pulso = traducciones.get('09_presi_prom_pulso', "• <b>Pulsaciones promedio:</b> `{pul:.1f} lpm`").format(pul=pul_prom)
        txt += f"{prom_pulso}\n"

    btn_texto = traducciones.get('09_btn_descargar_pdf_presi', "📄 Descargar PDF de Presión")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_texto, callback_data=f"descargar_pdf_presion_{mes_str}")]
    ])

    if hasattr(query_or_update, 'edit_message_text'):
        await query_or_update.edit_message_text(txt, reply_markup=keyboard, parse_mode="HTML")
    else:
        await query_or_update.message.reply_text(txt, reply_markup=keyboard, parse_mode="HTML")
  
async def _sub_manejar_foto_presion(update, context, res_presion, msg):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    alta = float(res_presion.get("alta", 0))
    baja = float(res_presion.get("baja", 0))
    pulsaciones = float(res_presion.get("pulsaciones", 0))
    
    if not (70 <= alta <= 250) or not (40 <= baja <= 150) or (pulsaciones > 0 and not (30 <= pulsaciones <= 220)):
        txt_error_presion = traducciones.get(
            '09_presi_foto_err_rango',
            "⚠️ **Lectura de presión atípica o errónea**\n\n"
            "Los valores detectados en la imagen (`{alta:.0f}/{baja:.0f} mmHg`) "
            "están fuera de los rangos biológicos lógicos.\n\n"
            "Por favor, registrala manualmente usando:\n`/presi [alta],[baja],[pulsaciones]` (ej: `/presi 120,80,75`)."
        ).format(alta=alta, baja=baja)
        await msg.edit_text(txt_error_presion.replace('\\n', '\n'), parse_mode="Markdown")
        return

    context.user_data['pending_presion_foto'] = {"alta": alta, "baja": baja, "pulsaciones": pulsaciones}
    lbl_pul = traducciones.get('09_presi_lbl_pulsaciones', 'Pulsaciones')
    pul_txt = f" | {lbl_pul}: `{pulsaciones:.0f} lpm`" if pulsaciones > 0 else ""
    
    btn_nota = traducciones.get('09_btn_presi_agregar_nota', "✏️ Agregar Nota")
    btn_guardar = traducciones.get('09_btn_presi_guardar_directo', "💾 Guardar sin Nota")
    btn_cancelar = traducciones.get('09_btn_cancelar', "❌ Cancelar")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_nota, callback_data="presion_pedir_nota")],
        [InlineKeyboardButton(btn_guardar, callback_data="presion_guardar_directo")],
        [InlineKeyboardButton(btn_cancelar, callback_data="cancelar_presion_foto")]
    ])

    mensaje_final = traducciones.get(
        '09_presi_foto_detectada',
        "🩺 **Tensiómetro detectado en la imagen:**\n\n"
        "• Presión Alta: `{alta:.0f} mmHg`\n"
        "• Presión Baja: `{baja:.0f} mmHg`{pul_txt}\n\n"
        "Seleccioná una opción para continuar:"
    ).format(alta=alta, baja=baja, pul_txt=pul_txt)
    await msg.edit_text(mensaje_final.replace('\\n', '\n'), reply_markup=keyboard, parse_mode="Markdown")

def generar_pdf_presion_bytes(mes_str, df_p_mes, user_id):
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1E3A8A'), spaceAfter=4)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.HexColor('#1E293B'))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=9, leading=11, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)

    t_titulo = traducciones.get("09_PDF_presi_titulo", f"Reporte de Presión Arterial - {mes_str}")
    t_usr = traducciones.get("09_PDF_presi_usuario", f"<b>Usuario Telegram ID:</b> {user_id}")

    story = [
        Paragraph(f"<b>{t_titulo}</b>", title_style),
        Paragraph(t_usr, body_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=10)
    ]

    if df_p_mes is None or df_p_mes.empty:
        msg_vacio = traducciones.get("09_PDF_presi_sin_reg", "No hay registros de presión para este período.")
        story.append(Paragraph(msg_vacio, body_style))
    else:
        th_fecha = traducciones.get("09_PDF_presi_th_fecha", "Fecha/Hora")
        th_alta = traducciones.get("09_PDF_presi_th_alta", "Alta (SYS)")
        th_baja = traducciones.get("09_PDF_presi_th_baja", "Baja (DIA)")
        th_pul = traducciones.get("09_PDF_presi_th_pul", "Pulso (lpm)")
        th_nota = traducciones.get("09_PDF_presi_th_nota", "Nota")

        table_data = [[
            Paragraph(th_fecha, header_style),
            Paragraph(th_alta, header_style),
            Paragraph(th_baja, header_style),
            Paragraph(th_pul, header_style),
            Paragraph(th_nota, header_style)
        ]]

        alta_sum = 0
        baja_sum = 0
        pulso_sum = 0
        pulso_count = 0

        for _, r in df_p_mes.iterrows():
            alta = float(r.get('Alta', 0))
            baja = float(r.get('Baja', 0))
            pulso = float(r.get('Pulsaciones', 0))
            
            alta_sum += alta
            baja_sum += baja
            if pulso > 0:
                pulso_sum += pulso
                pulso_count += 1

            fecha_hora = str(r.get('Fecha_Hora', r.get('Fecha_Dia', ''))).strip()
            nota = str(r.get('Nota', '')).strip()

            table_data.append([
                Paragraph(fecha_hora, body_style),
                Paragraph(f"{alta:.0f}", body_style),
                Paragraph(f"{baja:.0f}", body_style),
                Paragraph(f"{pulso:.0f}" if pulso > 0 else "-", body_style),
                Paragraph(nota, body_style)
            ])

        t = Table(table_data, colWidths=[120, 70, 70, 70, 220])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
        ]))
        story.append(t)
        story.append(Spacer(1, 15))

        total_regs = len(df_p_mes)
        prom_alta = alta_sum / total_regs
        prom_baja = baja_sum / total_regs
        prom_pulso = pulso_sum / pulso_count if pulso_count > 0 else 0

        txt_prom_tit = traducciones.get("09_PDF_presi_resumen_promedios", "<b>Promedios del mes:</b>")
        txt_prom_alta = traducciones.get("09_PDF_presi_resumen_alta", "• Presión Alta (Sistólica): {prom_alta:.1f} mmHg").format(prom_alta=prom_alta)
        txt_prom_baja = traducciones.get("09_PDF_presi_resumen_baja", "• Presión Baja (Diastólica): {prom_baja:.1f} mmHg").format(prom_baja=prom_baja)
        
        story.append(Paragraph(txt_prom_tit, body_style))
        story.append(Paragraph(txt_prom_alta, body_style))
        story.append(Paragraph(txt_prom_baja, body_style))
        
        if prom_pulso > 0:
            txt_prom_pulso = traducciones.get("09_PDF_presi_resumen_pulso", "• Pulsaciones: {prom_pulso:.1f} lpm").format(prom_pulso=prom_pulso)
            story.append(Paragraph(txt_prom_pulso, body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer
    
async def generar_y_enviar_pdf_presion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    await query.answer(traducciones.get('09_presi_generando_pdf', "Generando PDF de presión... ⏳"))
    
    cb_data = query.data
    mes_str = cb_data.replace("descargar_pdf_presion_", "").strip()
    
    df_presion = obtener_datos_presion_db(user_id)
    df_p_mes = df_presion[df_presion['Fecha_Dia'].str.startswith(mes_str)] if not df_presion.empty and 'Fecha_Dia' in df_presion.columns else pd.DataFrame()
    
    pdf_buffer = generar_pdf_presion_bytes(mes_str, df_p_mes, user_id)
    
    caption_txt = traducciones.get('09_presi_pdf_caption', "🩺 Reporte de Presión Arterial - Período {mes}").format(mes=mes_str)
    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=pdf_buffer,
        filename=f"P_{user_id}.pdf",
        caption=caption_txt,
        parse_mode="Markdown"
    )
    
@requiere_registro
async def cmd_presion_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    
    raw_text = re.sub(r'^/(presio|presi|presion)\w*(@\w+)?', '', update.message.text, flags=re.IGNORECASE).strip()

    if not raw_text:
        txt_ayuda_presi = traducciones.get('09_presi_ayuda_formato', 
            "Ingresá o consultá presión usando /presi. Ejemplos:\n\n"
            "• `/presi 120,80,70, después de caminar`\n"
            "• `/presi 120,80,70`\n"
            "• `/presi 120,80`\n"
            "• `/presi 08` (consulta promedio del mes de agosto del año actual)"
        ).replace('\\n', '\n')
        
        await update.message.reply_text(txt_ayuda_presi, parse_mode="Markdown")
        return

    if raw_text.isdigit() and 1 <= int(raw_text) <= 12:
        mes_int = int(raw_text)
        ahora = obtener_ahora_arg()
        if mes_int <= ahora.month:
            mes_str = f"{ahora.year}-{mes_int:02d}"
            await mostrar_resumen_presion_mes(update, user_id, mes_str)
            return
        else:
            txt_futuro = traducciones.get('09_presi_error_futuro', "⚠️ No podés consultar un mes futuro.")
            await update.message.reply_text(txt_futuro, parse_mode="Markdown")
            return

    if re.match(r'^20\d{2}-\d{2}$', raw_text):
        await mostrar_resumen_presion_mes(update, user_id, raw_text)
        return

    parts = [p.strip() for p in raw_text.replace('/', ',').split(',') if p.strip()]
    if len(parts) == 1:
        parts = [p.strip() for p in raw_text.split(' ') if p.strip()]

    numeros = []
    texto_nota = []

    for part in parts:
        clean_part = part.replace(',', '.')
        try:
            val = float(clean_part)
            if len(numeros) < 3 and not texto_nota:
                numeros.append(val)
            else:
                texto_nota.append(part)
        except ValueError:
            texto_nota.append(part)

    if len(numeros) >= 2:
        alta = numeros[0]
        baja = numeros[1]
        pulsaciones = numeros[2] if len(numeros) > 2 else None
        nota = " ".join(texto_nota).strip()

        guardar_presion_db(user_id, alta, baja, pulsaciones, nota)

        pul_str = f" | Pulsaciones: `{pulsaciones:.0f}`" if pulsaciones is not None else ""
        nota_str = f"\nNota: `{nota}`" if nota else ""
        
        # --- EL FIX DEL CARTEL ESTÁ ACÁ ---
        msg_bruto = traducciones.get('09_presi_registrada_ok', "✅ Presión registrada:\nAlta: `{alta} mmHg` | Baja: `{baja} mmHg`{pul}{nota}")
        # Limpiamos formatos restrictivos por si el traductor metió :.0f para que no crashee
        msg_limpio = msg_bruto.replace("{alta:.0f}", "{alta}").replace("{baja:.0f}", "{baja}")
        
        txt_reg_ok = msg_limpio.format(
            alta=f"{alta:.0f}", 
            baja=f"{baja:.0f}", 
            pul=pul_str, 
            nota=nota_str
        ).replace('\\n', '\n')
        
        await update.message.reply_text(txt_reg_ok, parse_mode="Markdown")
        return

    txt_err_formato = traducciones.get('09_presi_error_formato', "Formato incorrecto. Uso: `/presi 120,80,70, nota` o `/presi 08`")
    await update.message.reply_text(txt_err_formato, parse_mode="Markdown")
   
@requiere_registro
async def cmd_factor_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        cur.execute('SELECT "profesional" FROM "Usuarios" WHERE "User ID" = %s', (str(user_id),))
        resultado = cur.fetchone()
        cur.close()
        conn.close()

        if resultado:
            prof_val = str(resultado[0]).strip().lower() if resultado[0] else ""
            if prof_val and prof_val not in ['none', 'no', 'ninguno', 'null', 'nan', '0']:
                msg_bloqueo = traducciones.get("09_get_bloqueo_medico", "👨‍⚕️ <b>Acción denegada:</b> Tenés un profesional asignado. Por favor, contactalo directamente para realizar modificaciones en tu plan.")
                await update.message.reply_text(msg_bloqueo, parse_mode="HTML")
                return
    except Exception as e:
        logger.error(f"Error consultando profesional en /get para {user_id}: {e}")

    ahora = obtener_ahora_arg()
    
    if ahora.day < 15:
        txt_nodisp = traducciones.get("09_get_calibracion_no_disp", "⏳ **Calibración no disponible:** Para mantener la estabilidad de los cálculos, la calibración de gasto con reloj inteligente se habilita únicamente a partir del **día 15** de cada mes.")
        await update.message.reply_text(txt_nodisp, parse_mode="Markdown")
        return

    mes_actual = ahora.strftime("%Y-%m")
    info_usuario = obtener_datos_usuario_general(user_id) if 'obtener_datos_usuario_general' in globals() else obtener_perfil_usuario(user_id, mes_target=mes_actual)
    
    if info_usuario:
        mes_ultimo_cambio = str(info_usuario.get('reloj_actualizado_mes', '')).strip()
        if mes_ultimo_cambio == mes_actual:
            txt_limite_alcanzado = traducciones.get('09_get_error_limite_mensual', "⏳ **Límite mensual alcanzado:**\n\nYa utilizaste el reloj inteligente para calibrar tu gasto este mes. Para mantener la estabilidad del plan, solo se permite un ajuste por período.")
            await update.message.reply_text(txt_limite_alcanzado.replace('\\n', '\n'), parse_mode="Markdown")
            return

    raw_text = re.sub(r'^/(factor|fac|get)\w*(@\w+)?', '', update.message.text, flags=re.IGNORECASE).strip()

    if not raw_text:
        txt_ayuda_get = traducciones.get('09_get_ayuda_formato', "Ingresá las calorías totales que registró tu reloj en 24 horas. Ejemplo:\n\n• `/GET 2150`")
        await update.message.reply_text(txt_ayuda_get.replace('\\n', '\n'), parse_mode="Markdown")
        return

    try:
        calorias_reloj = float(raw_text.replace(',', '.'))
        if not (1000 <= calorias_reloj <= 4000):
            txt_err_real = traducciones.get("09_get_err_calorias_realistas", "⚠️ Ingresá un valor de calorías realista (entre 1000 y 4000 kcal).")
            await update.message.reply_text(txt_err_real, parse_mode="Markdown")
            return

        perfil = obtener_perfil_usuario(user_id, mes_target=mes_actual)
        if not perfil:
            txt_err_perfil = traducciones.get("09_get_err_perfil_inactivo", "❌ No se encontró tu perfil activo para este mes. Registrá tu peso primero con `/peso`.")
            await update.message.reply_text(txt_err_perfil, parse_mode="Markdown")
            return

        peso = parse_raw_val(perfil.get('PESO', perfil.get('Peso', 70)))
        altura = parse_raw_val(perfil.get('ALTURA', perfil.get('Altura', 170)))
        edad = parse_raw_val(perfil.get('EDAD', perfil.get('Edad', 40)))
        genero = str(perfil.get('GENERO', perfil.get('Genero', 'masculino')))
        factor_anterior = parse_raw_val(perfil.get('OCUPACION', perfil.get('Ocupacion', 1.375)))
        if factor_anterior <= 0: factor_anterior = 1.375

        tmb, get_anterior = calcular_tmb_y_get(peso, altura, edad, genero, actividad=factor_anterior)
        if tmb <= 0:
            txt_err_tmb = traducciones.get("09_get_err_tmb_base", "❌ Error al calcular la TMB base.")
            await update.message.reply_text(txt_err_tmb, parse_mode="Markdown")
            return

        nuevo_factor = aplicar_calibracion_reloj(factor_previo=factor_anterior, get_reloj=calorias_reloj, tmb=tmb, max_variacion_pct=0.20)
        _, get_nuevo = calcular_tmb_y_get(peso, altura, edad, genero, actividad=nuevo_factor)

        aviso_tope = ""
        factor_crudo_reloj = round(calorias_reloj / tmb, 3)
        if abs(nuevo_factor - factor_crudo_reloj) > 0.005:
            aviso_tope = traducciones.get("09_get_nota_seguridad_tope", "\n⚠️ *Nota de seguridad:* El valor del reloj superaba el 20% de variación respecto a tu tendencia habitual. Se aplicó el tope máximo permitido del 20%.\n").replace('\\n', '\n')

        context.user_data['temp_nuevo_factor'] = nuevo_factor
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅", callback_data="confirmar_factor_si"), InlineKeyboardButton("❌", callback_data="confirmar_factor_no")]])

        msg_texto_tpl = traducciones.get("09_get_resumen_calibracion", "📊 **Calibración de Gasto Energético (Reloj):**\n\n• Calorías reportadas por el reloj: `{calorias_reloj:.0f} kcal`\n• TMB Base estimada: `{tmb:.0f} kcal`\n\n• **Gasto Diario Anterior:** `{get_anterior:.0f} kcal`\n• **Nuevo Gasto Diario Ajustado:** `{get_nuevo:.0f} kcal`\n\n{aviso_tope}¿Deseás actualizar tu gasto diario con este valor?")
        msg_texto = msg_texto_tpl.replace("{calorias_reloj:.0f}", "{calorias_reloj}").replace("{tmb:.0f}", "{tmb}").replace("{get_anterior:.0f}", "{get_anterior}").replace("{get_nuevo:.0f}", "{get_nuevo}")
        
        await update.message.reply_text(msg_texto.format(calorias_reloj=f"{calorias_reloj:.0f}", tmb=f"{tmb:.0f}", get_anterior=f"{get_anterior:.0f}", get_nuevo=f"{get_nuevo:.0f}", aviso_tope=aviso_tope).replace('\\n', '\n'), reply_markup=keyboard, parse_mode="Markdown")

    except ValueError:
        txt_formato = traducciones.get("09_get_err_formato", "❌ Formato incorrecto. Ingresá un número válido. Ejemplo: `/GET 2150`")
        await update.message.reply_text(txt_formato, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error al previsualizar /factor para {user_id}: {e}")
        txt_proc = traducciones.get("09_get_err_procesar", "⚠️ Ocurrió un error al procesar la solicitud: {e}").format(e=e)
        await update.message.reply_text(txt_proc, parse_mode="Markdown")

async def callback_confirmar_factor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    data = query.data

    if data == "confirmar_factor_no":
        context.user_data.pop('temp_nuevo_factor', None)
        txt_canc = traducciones.get("09_get_operacion_cancelada", "🚫 Operación cancelada. No se modificó tu gasto energético.")
        await query.edit_message_text(txt_canc, parse_mode="Markdown")
        return

    if data == "confirmar_factor_si":
        nuevo_factor_val = context.user_data.get('temp_nuevo_factor')
        if not nuevo_factor_val:
            txt_exp = traducciones.get("09_get_datos_expirados", "⚠️ Los datos temporales expiraron. Por favor, volvé a enviar el comando `/factor`.")
            await query.edit_message_text(txt_exp, parse_mode="Markdown")
            return

        ahora = obtener_ahora_arg()
        mes_actual = ahora.strftime("%Y-%m")

        try:
            guardar_ocupacion_db(user_id, nuevo_factor_val, mes_actual, reloj_actualizado=mes_actual)
            perfil = obtener_perfil_usuario(user_id, mes_target=mes_actual)
            peso = parse_raw_val(perfil.get('PESO', perfil.get('Peso', 70))) if perfil else 70
            altura = parse_raw_val(perfil.get('ALTURA', perfil.get('Altura', 170))) if perfil else 170
            edad = parse_raw_val(perfil.get('EDAD', perfil.get('Edad', 40))) if perfil else 40
            genero = str(perfil.get('GENERO', perfil.get('Genero', 'masculino'))) if perfil else 'masculino'
            
            _, get_final = calcular_tmb_y_get(peso, altura, edad, genero, actividad=nuevo_factor_val)

            txt_exito_tpl = traducciones.get("09_get_exito_actualizado", "✅ **¡Gasto energético actualizado con éxito!**\n\n• Nuevo Gasto Diario asignado: `{get_final:.0f} kcal`\n• Período actualizado: `{mes_actual}`\n• Estado: Calibración mensual registrada.")
            txt_exito = txt_exito_tpl.replace("{get_final:.0f}", "{get_final}").format(get_final=f"{get_final:.0f}", mes_actual=mes_actual).replace('\\n', '\n')
            
            await query.edit_message_text(txt_exito, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error al guardar el factor confirmado para {user_id}: {e}")
            txt_err_db = traducciones.get("09_get_err_guardar_db", "⚠ Ocurrió un error al guardar en la base de datos: {e}").format(e=e)
            await query.edit_message_text(txt_err_db, parse_mode="Markdown")
        
        context.user_data.pop('temp_nuevo_factor', None)
        
# ======================================================================================================================================
#                       FINAL                        COMANDOS INGRESOS                                      FINAL
# ======================================================================================================================================

# ==========================================================================================================================================
#                                   INICIO                                       MAIN                                   INICIO  
# ==========================================================================================================================================

async def job_recordatorio_manana(context):
    """Tarea programada para el recordatorio matutino con protección contra fallas."""
    try:
        await ejecutar_recordatorio_comidas(context, momento='manana')
    except Exception as e:
        logger.error(f"❌ Error in job_recordatorio_manana: {e}")

async def job_recordatorio_tarde(context):
    """Tarea programada para el recordatorio vespertino con protección contra fallas."""
    try:
        await ejecutar_recordatorio_comidas(context, momento='tarde')
    except Exception as e:
        logger.error(f"❌ Error in job_recordatorio_tarde: {e}")

# 13. REGISTRO EN EL CONVERSATIONHANDLER (MAIN)
conv_handler_ingreso = ConversationHandler(
    entry_points=[CommandHandler(["alta", "register", "nuevo_usuario"], cmd_ingreso_start)],
    states={

        ING_TERMINOS: [MessageHandler(filters.StatusUpdate.WEB_APP_DATA, ing_aceptar_terminos), CallbackQueryHandler(ing_aceptar_terminos, pattern="^aceptar_terminos_ok$")],
        ING_PROFESIONAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ing_recibir_profesional)],
        ING_NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ing_recibir_nombre)],
        ING_SEXO: [CallbackQueryHandler(ing_recibir_sexo, pattern="^sexo_")],
        ING_ALTURA: [MessageHandler(filters.TEXT & ~filters.COMMAND, ing_recibir_altura)],
        ING_PESO: [MessageHandler(filters.TEXT & ~filters.COMMAND, ing_recibir_peso)],
        ING_MUNECA: [MessageHandler(filters.TEXT & ~filters.COMMAND, ing_recibir_muneca)],
        ING_CUELLO: [MessageHandler(filters.TEXT & ~filters.COMMAND, ing_recibir_cuello)],
        ING_CADERA: [MessageHandler(filters.TEXT & ~filters.COMMAND, ing_recibir_cadera)],
        ING_OCUPACION: [CallbackQueryHandler(ing_recibir_ocupacion, pattern="^ocup_")],
        ING_CUMPLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ing_recibir_cumple)],
        ING_RITMO: [CallbackQueryHandler(ing_recibir_ritmo, pattern="^ritmo_")],
        ING_IDIOMA: [CallbackQueryHandler(ing_recibir_idioma, pattern="^set_lang_")]
    },
    fallbacks=[CommandHandler("cancelar", cmd_cancelar_conversacion)]
)

def main():
    threading.Thread(target=run_flask, daemon=True).start()

    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not configured.")
        return

    try:
        app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        job_queue = app_bot.job_queue
        tz = pytz.timezone('America/Argentina/Buenos_Aires')

        if job_queue is not None:
            job_queue.run_daily(
                job_recordatorio_manana, 
                time=time(hour=9, minute=0, second=0, tzinfo=tz),
                name="recordatorio_comidas_manana"
            )
            job_queue.run_daily(
                job_recordatorio_tarde, 
                time=time(hour=18, minute=0, second=0, tzinfo=tz),
                name="recordatorio_comidas_tarde"
            )
            
            job_queue.run_daily(
                rutina_nocturna_revision,
                time=time(hour=3, minute=0, second=0, tzinfo=tz),
                name="rutina_nocturna_revision"
            )

            job_queue.run_monthly(
	            callback=proceso_masivo_cobros,
	            when=time(hour=0, minute=5, second=0, tzinfo=tz),
	            day=1,
	            name="facturacion_masiva_dia_1"
	        )        
        else:
            print("⚠️ Warning: job_queue is not available.")
       
        app_bot.add_handler(conv_handler_ingreso)

        # Callbacks y captura de texto para notas médicas interactivas
        app_bot.add_handler(CallbackQueryHandler(callback_seleccionar_paciente_nota, pattern="^selec_nota_pac_"))
        app_bot.add_handler(CallbackQueryHandler(generar_y_enviar_pdf_diario_callback, pattern="^descargar_pdf_diario_"))
        app_bot.add_handler(CallbackQueryHandler(generar_y_enviar_pdf_presion, pattern="^descargar_pdf_presion_"))
        app_bot.add_handler(CallbackQueryHandler(callback_seleccionar_paciente_clinico, pattern="^edit_clinico_sel_"))
        app_bot.add_handler(CallbackQueryHandler(callback_acciones_informe, pattern="^(inf_dir_|inf_nota_|inf_cancelar)"))        
        
        # ==================================PROFESIONALES===============================================
        app_bot.add_handler(CommandHandler(["pacientes"], cmd_pacientes))
        app_bot.add_handler(CommandHandler(["informe"], cmd_enviar_informe_actual))
        app_bot.add_handler(CommandHandler(["nota"], cmd_enviar_nota_paciente))
        app_bot.add_handler(CommandHandler(["valores"], cmd_editar_valores_clinicos))
        app_bot.add_handler(CommandHandler(["manual", "documentacion"], cmd_generar_manual_pdf))
        
        # =================================INGRESOS Y CONSULTAS MANUALES============================================
        app_bot.add_handler(CommandHandler(["start", "inicio"], cmd_start))
        app_bot.add_handler(CommandHandler(["comidas","c","meals","food"], cmd_comidas))
        app_bot.add_handler(CommandHandler(["perfil", "profile"], cmd_perfil))
        app_bot.add_handler(CommandHandler(["receta", "recipe"], cmd_cargar_receta))
        app_bot.add_handler(CommandHandler(["get", "GET", "factor"], cmd_factor_handler))
        app_bot.add_handler(CommandHandler(["eliminar", "delete"], cmd_eliminar))
        app_bot.add_handler(CommandHandler(["borracomida", "delmeal"], cmd_borrar_comida))
        app_bot.add_handler(CommandHandler(["peso", "weight"], cmd_peso_rapido))        
        app_bot.add_handler(CommandHandler(["presion", "presi", "p", "pressure"], cmd_presion_handler))  
        app_bot.add_handler(CommandHandler(["dia", "d", "day"], cmd_diario))
        app_bot.add_handler(CommandHandler(["mes", "m", "month"], cmd_resumen))
        app_bot.add_handler(CommandHandler(["semana", "s", "w", "week"], cmd_mensaje))
        app_bot.add_handler(CommandHandler(["barra", "barcode"], cmd_barra))
        app_bot.add_handler(CommandHandler(["cancelar", "exit", "x"], cmd_cancelar_conversacion))
        
        # =================================FACTURACIÓN Y PAGOS (TELEGRAM STARS)======================
        app_bot.add_handler(CommandHandler(["pagar", "pay"], cmd_pagar))
        app_bot.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))

        # =================================ADMINISTRADOR============================================
        app_bot.add_handler(CommandHandler("cobrar", cmd_forzar_cobro))
        app_bot.add_handler(CommandHandler(["descargar","bajar"], cmd_descargar))
        app_bot.add_handler(CommandHandler(["cargar","subir"], cmd_subir))
        app_bot.add_handler(CommandHandler("desarmar", cmd_desarmar_excel))
        app_bot.add_handler(CommandHandler("armar", cmd_armar_excel))

        # =================================CALLBACK QUERY HANDLERS====================================
        
        app_bot.add_handler(CallbackQueryHandler(mostrar_resumen_mes, pattern="^resumen_(mes_|volver_menu)"))
        app_bot.add_handler(CallbackQueryHandler(boton_elegir_plan, pattern="^(comprar_|rescate_mensual)"))
        app_bot.add_handler(CallbackQueryHandler(manejar_callback_eliminacion, pattern="^del_(d_|mom_|reg_|borrar|salir|cambiar_fecha|volver_momentos)"))
        
        
        
        app_bot.add_handler(CallbackQueryHandler(callback_handler_presion_foto, pattern="^presion_"))
        app_bot.add_handler(CallbackQueryHandler(callback_handler_presion_foto, pattern="^cancelar_presion_foto$"))
        app_bot.add_handler(CallbackQueryHandler(ing_aceptar_terminos, pattern="^aceptar_terminos_ok$"))
        app_bot.add_handler(CallbackQueryHandler(callback_confirmar_factor, pattern="^confirmar_factor_"))
        app_bot.add_handler(CallbackQueryHandler(generar_y_enviar_pdf_resumen, pattern="^(descargar_pdf_resumen_|pdf_mes_)"))
        app_bot.add_handler(CallbackQueryHandler(callback_editar_valor_clinico_menu, pattern="^(edit_val_calorias|edit_val_proteinas|edit_val_peso|edit_val_volver)$"))
        
        # Enrutadores para el módulo profesional (listados, informes y edición por botones)
        app_bot.add_handler(CallbackQueryHandler(callback_enviar_informe_paciente, pattern="^enviar_inf_"))
        app_bot.add_handler(CallbackQueryHandler(callback_descargar_manual_usuario, pattern="^descargar_manual_user_"))        

        app_bot.add_handler(CallbackQueryHandler(callback_btn_momento, pattern="^set_m_"))
        app_bot.add_handler(CallbackQueryHandler(callback_btn_fechas_diario, pattern="^(set_d_|diario_)"))
        app_bot.add_handler(CallbackQueryHandler(callback_btn_editar_item, pattern="^edit_item_"))
        app_bot.add_handler(CallbackQueryHandler(callback_btn_anular_item, pattern="^del_item_"))
        app_bot.add_handler(CallbackQueryHandler(callback_btn_cancelar_registro, pattern="^cancel_entry$"))
        app_bot.add_handler(CallbackQueryHandler(callback_btn_guardar_registro, pattern="^confirm_save$"))        

        app_bot.add_handler(CallbackQueryHandler(callback_gestion_solicitud_medico, pattern="^medico_(aceptar|rechazar)_"))
        app_bot.add_handler(CallbackQueryHandler(callback_handler_editar_perfil, pattern="^(edit_perfil_|set_ritmo_|set_ocup_|set_lang_)"))

        # =================================MESSAGE HANDLERS===========================================

        app_bot.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
        app_bot.add_handler(MessageHandler(filters.VOICE, handle_voice))
        app_bot.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        
        # ÚNICO HANDLER DE TEXTO: El jefe absoluto que rutea todo internamente en handle_message
        app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("Nutrition Bot successfully started on Telegram with scheduled tasks...")
        app_bot.run_polling(drop_pending_updates=True)

    except Exception as e:
        logger.critical(f"❌ Critical error starting bot in main(): {e}", exc_info=True)
        raise e

if __name__ == "__main__":
    main()

# =============================================================================================================================================
#                                               FINAL MAIN EXECUTION                                                    FINAL
# =============================================================================================================================================

