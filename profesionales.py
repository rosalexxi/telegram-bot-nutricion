
import io
import re
import logging
from datetime import timedelta
import pandas as pd

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Importamos todas las herramientas de base de datos y cálculos desde el motor central (bot8a.py)
from bot8a import (
    _asegurar_tabla_y_conectar,
    obtener_ahora_arg,
    obtener_perfil_usuario,
    calcular_peso_ideal,
    calcular_peso_etapa,
    calcular_tmb_y_get,
    obtener_ultimo_peso,
    obtener_datos_usuario,
    obtener_datos_presion_db,
     obtener_valores_clinicos_profesional,
    calcular_metricas_mensuales,
    procesar_y_enviar_informe_mensual
)

logger = logging.getLogger(__name__)
# =======================================================================================================================================
#                    INICIO                      FUNCIONES PROFESIONALES                     
# =======================================================================================================================================

def obtener_ultimo_perfil_dict(u_id):
    try:
        perfil = obtener_perfil_usuario(u_id)
        if perfil:
            return perfil
    except Exception as e:
        logger.error(f"Error en obtener_ultimo_perfil_dict para {u_id}: {e}")
    return {}


def obtener_promedio_calorias_mes_actual(u_id, ahora):
    calorias_str = "S/D"
    try:
        df_u = obtener_datos_usuario(u_id)
        if not df_u.empty and 'Fecha' in df_u.columns:
            mes_actual_str = ahora.strftime("%Y-%m")
            df_u['Mes_Filtro'] = df_u['Fecha'].astype(str).str.slice(0, 7)
            df_mes = df_u[df_u['Mes_Filtro'] == mes_actual_str]
            if not df_mes.empty and 'Calorias' in df_mes.columns:
                calorias_mes = [float(c) for c in df_mes['Calorias'] if float(c) > 0]
                if calorias_mes:
                    prom_cal = sum(calorias_mes) / len(calorias_mes)
                    calorias_str = f"{round(prom_cal)} kcal/día"
    except Exception as e:
        logger.error(f"Error en obtener_promedio_calorias_mes_actual para {u_id}: {e}")
    return calorias_str

def obtener_registros_presion(u_id):
    try:
        df_presion = obtener_datos_presion_db(u_id)
        if not df_presion.empty:
            return df_presion.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Error al obtener registros de presión en Supabase para {u_id}: {e}")
    return []

def obtener_ultima_presion(recs_presion_all):
    presion_str = "S/D"
    try:
        if recs_presion_all:
            ult_pres = recs_presion_all[-1]
            sys = ult_pres.get("Alta", ult_pres.get("Sistolica", ult_pres.get("sistólica", ult_pres.get("sistolica", ""))))
            dia = ult_pres.get("Baja", ult_pres.get("Diastolica", ult_pres.get("diastólica", ult_pres.get("diastolica", ""))))
            if sys and dia:
                presion_str = f"{sys}/{dia} mmHg"
    except Exception as e:
        logger.error(f"Error al formatear última presión: {e}")
    return presion_str
        
async def _verificar_y_obtener_profesional(update: Update):
    prof_id = str(update.effective_user.id).strip()
    conn = None
    cur = None
    try:
        conn, cur = _asegurar_tabla_y_conectar("Profesionales", tipo_tabla="profesionales")
        query = """
            SELECT "User ID"
            FROM "Profesionales"
        """
        cur.execute(query)
        filas = cur.fetchall()

        for fila in filas:
            id_p = str(fila[0] or "").split('.')[0].strip()
            if id_p == prof_id:
                return prof_id
    except Exception as e:
        logger.error(f"Error en _verificar_y_obtener_profesional: {e}")
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass
    return None

def obtener_especialidad_profesional(prof_id):
    conn = None
    cur = None
    try:
        conn, cur = _asegurar_tabla_y_conectar("Profesionales", tipo_tabla="profesionales")
        query = """
            SELECT "User ID", "Especialidad"
            FROM "Profesionales"
        """
        cur.execute(query)
        filas = cur.fetchall()

        for fila in filas:
            id_p = str(fila[0] or "").split('.')[0].strip()
            if id_p == str(prof_id).strip():
                return str(fila[1] or "General").strip()
    except Exception as e:
        logger.error(f"Error en obtener_especialidad_profesional para {prof_id}: {e}")
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass
    return None

def obtener_pacientes_por_medico(prof_id):
    pacientes = []
    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        query = """
            SELECT "User ID", "Nombre", "Estado", "profesional"
            FROM "Usuarios"
        """
        cur.execute(query)
        filas = cur.fetchall()
        cur.close()
        conn.close()

        for fila in filas:
            p_id = str(fila[3] or "").split('.')[0].strip()
            if p_id == str(prof_id).strip():
                u_id = str(fila[0] or "").split('.')[0].strip()
                nombre = fila[1] or "Sin Nombre"
                
                # Estado numérico: 3 es bloqueado/inactivo. 0, 1, 2, 10, etc., son válidos.
                try:
                    estado_int = int(fila[2]) if fila[2] is not None else 0
                except (ValueError, TypeError):
                    estado_int = 0

                # Si no está en estado 3 (bloqueado), se incluye en la lista del médico
                if estado_int != 3:
                    pacientes.append({"user_id": u_id, "nombre": nombre})
    except Exception as e:
        logger.error(f"Error en obtener_pacientes_por_medico para {prof_id}: {e}")
    return pacientes
  
# =======================================================================================================================================
#                    FINAL                      FUNCIONES PROFESIONALES                            FINAL
# =======================================================================================================================================

# =============================================================================================================================================
#                   INICIO                      COMANDOS PROFESIONALES                             INICIO 
# =============================================================================================================================================

async def callback_editar_valor_clinico_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los botones del menú de edición clínica y le pide el nuevo valor al médico."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data == "edit_val_volver":
        await query.edit_message_text("🔙 Operación finalizada.", parse_mode="Markdown")
        return

    # Mapeo de botones a campos en la base de datos
    mapa_campos = {
        "edit_val_calorias": ("calorias_max", "Calorías Máximas / GET (ej: 2100)"),
        "edit_val_proteinas": ("proteinas_max", "Proteínas Máximas en gramos (ej: 120)"),
        "edit_val_peso": ("peso_etapa", "Peso de Etapa en kg (ej: 80.5)")
    }

    if data in mapa_campos:
        campo_db, etiqueta = mapa_campos[data]
        context.user_data['campo_clinico_a_editar'] = campo_db
        
        await query.edit_message_text(
            f"✍️ **Modificar {etiqueta}**\n\n"
            "Por favor, escribí a continuación el nuevo valor numérico:",
            parse_mode="Markdown"
        )
        
async def procesar_cambio_valor_clinico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Captura el número escrito por el médico y actualiza la tabla de valores clínicos en Supabase."""
    campo_db = context.user_data.get('campo_clinico_a_editar')
    target_user_id = context.user_data.get('edit_medico_target_user')
    mes_actual = context.user_data.get('edit_medico_mes')

    if not campo_db or not target_user_id or not mes_actual:
        return False # No es una edición clínica activa, dejar pasar el mensaje

    texto_ingresado = update.message.text.strip().replace(',', '.')
    
    # Limpiar estado del contexto
    context.user_data.pop('campo_clinico_a_editar', None)

    try:
        nuevo_valor = float(texto_ingresado)
        
        # Conectar a Supabase y actualizar el registro clínico
        conn, cur = _asegurar_tabla_y_conectar("Valores_Clinicos_Profesional", tipo_tabla="comidas_precargadas")
        
        # Si es calorías, actualizamos un rango lógico (ej: min y max simétricos o ajustados)
        if campo_db == "calorias_max":
            cal_min = max(800.0, nuevo_valor - 300.0)
            cur.execute("""
                UPDATE "Valores_Clinicos_Profesional" 
                SET "calorias_min" = %s, "calorias_max" = %s, "get" = %s
                WHERE "user_id" = %s AND "mes" = %s
            """, (cal_min, nuevo_valor, nuevo_valor, str(target_user_id), str(mes_actual)))
        else:
            query_upd = f'UPDATE "Valores_Clinicos_Profesional" SET "{campo_db}" = %s WHERE "user_id" = %s AND "mes" = %s'
            cur.execute(query_upd, (nuevo_valor, str(target_user_id), str(mes_actual)))
            
        conn.commit()
        cur.close()
        conn.close()

        await update.message.reply_text(
            f"✅ **¡Valor clínico actualizado con éxito!**\n\n"
            f"• Paciente ID: `{target_user_id}`\n"
            f"• Período: `{mes_actual}`\n"
            f"• Nuevo valor registrado para `{campo_db}`: `{nuevo_valor}`",
            parse_mode="Markdown"
        )
        return True

    except ValueError:
        await update.message.reply_text("⚠️ Por favor, ingresá un número válido (ejemplo: `2100` o `85.5`).")
        return True
    except Exception as e:
        logger.error(f"Error al actualizar valor clínico en Supabase: {e}")
        await update.message.reply_text(f"❌ Ocurrió un error al actualizar la base de datos: {e}")
        return True
        
async def callback_gestion_solicitud_medico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la respuesta del médico al aceptar o rechazar la solicitud de un nuevo paciente."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    prof_id = str(query.from_user.id).strip()

    if not data.startswith("medico_aceptar_") and not data.startswith("medico_rechazar_"):
        return

    es_aceptacion = data.startswith("medico_aceptar_")
    target_user_id = data.replace("medico_aceptar_", "").replace("medico_rechazar_", "").strip()

    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        
        if es_aceptacion:
            # 1. Pasar el profesional pendiente a la columna oficial "profesional" y limpiar el pendiente
            cur.execute("""
                UPDATE "Usuarios" 
                SET "profesional" = %s, "profesional_pendiente" = NULL 
                WHERE "User ID" = %s
            """, (prof_id, str(target_user_id)))
            conn.commit()

            # 2. Generar automáticamente los valores clínicos iniciales para el mes actual en la tabla de Supabase
            ahora = obtener_ahora_arg()
            mes_actual = ahora.strftime("%Y-%m")
            
            # Consultar biometría del usuario para calcular valores base
            cur.execute('SELECT "Sexo", "cintura_cm", "cuello_cm", "cadera_cm" FROM "Usuarios" WHERE "User ID" = %s', (str(target_user_id),))
            fila_u = cur.fetchone()
            
            perfil_u = obtener_perfil_usuario(target_user_id, mes_target=mes_actual) or {}
            peso_u = float(perfil_u.get('PESO', perfil_u.get('Peso', 70)))
            altura_u = float(perfil_u.get('ALTURA', perfil_u.get('Altura', 170)))
            edad_u = int(perfil_u.get('EDAD', perfil_u.get('Edad', 40)))
            sexo_u = str(fila_u[0] if fila_u and fila_u[0] else perfil_u.get('GENERO', 'M'))
            
            # Calcular metas y macros iniciales
            peso_ideal = calcular_peso_ideal(sexo_u, altura_u, edad=edad_u)
            peso_etapa = calcular_peso_etapa(peso_u, peso_ideal, perfil_u.get('Ritmo', 'moderado'))
            tmb, get_val = calcular_tmb_y_get(peso_u, altura_u, edad_u, sexo_u, actividad=1.375)
            
            # Insertar en la tabla Valores_Clinicos_Profesional
            try:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS "Valores_Clinicos_Profesional" (
                        id SERIAL PRIMARY KEY,
                        "user_id" TEXT,
                        "prof_id" TEXT,
                        "mes" TEXT,
                        "tmb" DOUBLE PRECISION,
                        "get" DOUBLE PRECISION,
                        "peso_etapa" DOUBLE PRECISION,
                        "calorias_min" DOUBLE PRECISION,
                        "calorias_max" DOUBLE PRECISION,
                        "proteinas_min" DOUBLE PRECISION,
                        "proteinas_max" DOUBLE PRECISION,
                        "hidratos_min" DOUBLE PRECISION,
                        "hidratos_max" DOUBLE PRECISION,
                        "grasas_min" DOUBLE PRECISION,
                        "grasas_max" DOUBLE PRECISION,
                        "fibras_min" DOUBLE PRECISION
                    );
                """)
                cur.execute("""
                    INSERT INTO "Valores_Clinicos_Profesional" 
                    ("user_id", "prof_id", "mes", "tmb", "get", "peso_etapa", "calorias_min", "calorias_max", "proteinas_min", "proteinas_max", "hidratos_min", "hidratos_max", "grasas_min", "grasas_max", "fibras_min")
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    str(target_user_id), prof_id, mes_actual, tmb, get_val, peso_etapa,
                    get_val - 300, get_val, 80, 110, 150, 220, 45, 65, 25
                ))
                conn.commit()
            except Exception as e_vc:
                logger.error(f"Error al insertar valores clínicos iniciales: {e_vc}")

            cur.close()
            conn.close()

            # 3. Informar al médico y al paciente
            await query.edit_message_text(
                f"✅ **Paciente aceptado con éxito.**\n\n"
                f"El usuario con ID `{target_user_id}` ha sido vinculado oficialmente a su cuenta. "
                f"Se han generado sus valores clínicos iniciales para el período `{mes_actual}`. "
                f"Ya puede revisarlos o modificarlos desde el comando `/editar_valores`.",
                parse_mode="Markdown"
            )
            
            try:
                msg_paciente = "🩺 **¡Buenas noticias!** Tu profesional a cargo ha aceptado la supervisión de tu cuenta. Tu seguimiento clínico ya se encuentra activo."
                await context.bot.send_message(chat_id=int(target_user_id), text=msg_paciente, parse_mode="Markdown")
            except Exception as e_notif_pac:
                logger.error(f"No se pudo notificar la aceptación al paciente {target_user_id}: {e_notif_pac}")

        else:
            # Si el médico rechaza, limpiamos el campo pendiente pero dejamos el genérico activo en el usuario
            cur.execute("""
                UPDATE "Usuarios" 
                SET "profesional_pendiente" = NULL 
                WHERE "User ID" = %s
            """, (str(target_user_id),))
            conn.commit()
            cur.close()
            conn.close()

            await query.edit_message_text(
                f"❌ **Solicitud rechazada.**\nEl usuario con ID `{target_user_id}` continuará operando de forma autónoma con el sistema genérico.",
                parse_mode="Markdown"
            )
            
            try:
                msg_paciente = "ℹ️ Te informamos que tu solicitud de vinculación con el profesional ingresado no pudo ser procesada en este momento. Tu cuenta continúa operando de forma autónoma."
                await context.bot.send_message(chat_id=int(target_user_id), text=msg_paciente, parse_mode="Markdown")
            except Exception as e_notif_pac_rec:
                logger.error(f"No se pudo notificar el rechazo al paciente {target_user_id}: {e_notif_pac_rec}")

    except Exception as e:
        logger.error(f"Error crítico en gestión de solicitud médica para usuario {target_user_id}: {e}")
        await query.edit_message_text(f"❌ Ocurrió un error al procesar la respuesta: {e}")
        
async def cmd_editar_valores_clinicos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando para que el médico despliegue el menú de pacientes y seleccione 
    a cuál desea revisarle o modificarle los valores clínicos.
    Uso: /editar_valores
    """
    prof_id = str(update.effective_user.id).strip()
    
    # Validar si es profesional autorizado
    especialidad_prof = obtener_especialidad_profesional(prof_id)
    if not especialidad_prof:
        await update.message.reply_text("⛔ **Acceso denegado:** Este comando es exclusivo para profesionales registrados.", parse_mode="Markdown")
        return

    pacientes = obtener_pacientes_por_medico(prof_id)
    if not pacientes:
        await update.message.reply_text("📋 No tenés pacientes activos asignados en este momento.", parse_mode="Markdown")
        return

    # Armar teclado interactivo con el nombre y el ID del paciente
    keyboard = []
    for pac in pacientes:
        u_id = str(pac["user_id"])
        nombre = pac["nombre"]
        # Texto del botón claro: Nombre e ID
        btn_text = f"👤 {nombre} (ID: {u_id})"
        callback_data = f"edit_clinico_sel_{u_id}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎛️ **Panel de Modificación Clínica**\n\n"
        "Seleccioná el paciente cuyos valores de referencia deseas consultar o corregir:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    
async def callback_seleccionar_paciente_clinico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la selección del paciente y muestra sus valores clínicos actuales del mes."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not data.startswith("edit_clinico_sel_"):
        return

    target_user_id = data.replace("edit_clinico_sel_", "").strip()
    ahora = obtener_ahora_arg()
    mes_actual = ahora.strftime("%Y-%m")

    # Guardar en contexto para los siguientes pasos de edición
    context.user_data['edit_medico_target_user'] = target_user_id
    context.user_data['edit_medico_mes'] = mes_actual

    # Obtener valores actuales (si los hay en la tabla del profesional o los calculados)
    valores = obtener_valores_clinicos_profesional(target_user_id, mes_actual)

    if not valores:
        texto_valores = (
            f"⚠️ No se encontraron valores personalizados para el usuario `{target_user_id}` en el período `{mes_actual}`.\n"
            "Se están utilizando los valores estándar calculados por las fórmulas del sistema."
        )
    else:
        texto_valores = (
            f"📋 **Valores Clínicos Actuales ({mes_actual})**\n"
            f"👤 Paciente ID: `{target_user_id}`\n\n"
            f"• **TMB:** `{valores.get('tmb', 0)} kcal`\n"
            f"• **GET:** `{valores.get('get', 0)} kcal`\n"
            f"• **Peso Etapa:** `{valores.get('peso_etapa', 0)} kg`\n"
            f"• **Calorías Mín-Máx:** `{valores.get('calorias_min', 0)} - {valores.get('calorias_max', 0)} kcal`\n"
            f"• **Proteínas Mín-Máx:** `{valores.get('proteinas_min', 0)} - {valores.get('proteinas_max', 0)} g`\n"
            f"• **Hidratos Mín-Máx:** `{valores.get('hidratos_min', 0)} - {valores.get('hidratos_max', 0)} g`\n"
            f"• **Grasas Mín-Máx:** `{valores.get('grasas_min', 0)} - {valores.get('grasas_max', 0)} g`\n"
        )

    # Botones para que el médico elija qué modificar
    keyboard = [
        [InlineKeyboardButton("🔥 Modificar Calorías/GET", callback_data="edit_val_calorias")],
        [InlineKeyboardButton("🥩 Modificar Proteínas", callback_data="edit_val_proteinas")],
        [InlineKeyboardButton("⚖️ Modificar Peso de Etapa", callback_data="edit_val_peso")],
        [InlineKeyboardButton("🔙 Volver al Listado", callback_data="edit_val_volver")]
    ]
    
    await query.edit_message_text(texto_valores, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    
async def cmd_pacientes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando para que el profesional vea el listado de sus pacientes y genere un reporte PDF avanzado (hasta 6 meses con promedios mensuales)."""
    prof_id = str(update.effective_user.id).strip()
    
    msg_espera = await update.message.reply_text("⏳ **Buscando pacientes y procesando historial clínico (últimos 6 meses)...**", parse_mode="Markdown")

    try:
        especialidad_prof = obtener_especialidad_profesional(prof_id)

        if not especialidad_prof:
            await msg_espera.edit_text("⛔ **Acceso denegado:** Este comando es exclusivo para profesionales registrados.", parse_mode="Markdown")
            return

        pacientes_del_medico = obtener_pacientes_por_medico(prof_id)

        if not pacientes_del_medico:
            await msg_espera.edit_text("ℹ️ No tenés pacientes activos asignados en este momento.", parse_mode="Markdown")
            return

        ahora = obtener_ahora_arg()
        meses_a_evaluar = []
        for i in range(6):
            mes_calculado = ahora - timedelta(days=i * 30)
            m_str = mes_calculado.strftime("%Y-%m")
            if m_str not in meses_a_evaluar:
                meses_a_evaluar.append(m_str)
        meses_a_evaluar = sorted(list(set(meses_a_evaluar)))[-6:]

        texto_reporte = f"📋 **Listado de Pacientes Asignados**\n🩺 *Especialidad:* `{especialidad_prof}`\n\n"
        datos_para_pdf = []

        for pac in pacientes_del_medico:
            u_id = pac["user_id"]
            nombre = pac["nombre"]
            
            peso_raw = obtener_ultimo_peso(u_id)
            if isinstance(peso_raw, dict):
                peso_str = peso_raw.get("peso", peso_raw.get("fecha", "S/D"))
            else:
                peso_str = str(peso_raw) if peso_raw else "S/D"

            recs_presion_all = obtener_registros_presion(u_id)
            presion_str = obtener_ultima_presion(recs_presion_all)
            calorias_str = obtener_promedio_calorias_mes_actual(u_id, ahora)

            texto_reporte += (
                f"👤 **{nombre}** (ID: `{u_id}`)\n"
                f"• ⚖️ Peso: `{peso_str}`\n"
                f"• 🩸 Presión: `{presion_str}`\n"
                f"• 🔥 Prom. Calorías: `{calorias_str}`\n"
                "--------------------------------------------------\n"
            )

            historial_6m = []
            perfil_dict = obtener_ultimo_perfil_dict(u_id)
            
            df_u = obtener_datos_usuario(u_id) 
            if not df_u.empty and 'Fecha' in df_u.columns:
                df_u['Mes_Filtro'] = df_u['Fecha'].str.slice(0, 7)

            for m_str in meses_a_evaluar:
                prom_cons_m = 0
                prom_quem_m = 0
                prom_neto_m = 0
                prom_prot_m = 0
                prom_gras_m = 0
                prom_carb_m = 0
                prom_fibr_m = 0

                if not df_u.empty and 'Mes_Filtro' in df_u.columns:
                    df_m = df_u[df_u['Mes_Filtro'] == m_str]
                    if not df_m.empty:
                        metricas_m = calcular_metricas_mensuales(df_m, perfil_dict, user_id=u_id, mes_str=m_str)
                        prom_cons_m = metricas_m.get("prom_cal", 0)
                        prom_quem_m = metricas_m.get("prom_quem", 0)
                        prom_neto_m = metricas_m.get("prom_bal_neto", 0)
                        prom_prot_m = metricas_m.get("prom_prot", 0)
                        prom_gras_m = metricas_m.get("prom_gras", 0)
                        prom_carb_m = metricas_m.get("prom_carb", 0)
                        prom_fibr_m = metricas_m.get("prom_fibr", 0)

                historial_6m.append({
                    "mes": m_str,
                    "cal_cons": prom_cons_m,
                    "cal_quem": prom_quem_m,
                    "bal_neto": prom_neto_m,
                    "proteinas": prom_prot_m,
                    "grasas": prom_gras_m,
                    "carbohidratos": prom_carb_m,
                    "fibras": prom_fibr_m
                })

            datos_para_pdf.append({
                "nombre": nombre,
                "user_id": u_id,
                "historial": historial_6m
            })

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph(f"<b>Reporte Clínico Consolidado Promedio ({especialidad_prof})</b>", styles['Heading1']))
        elements.append(Paragraph(f"Generado el: {ahora.strftime('%Y-%m-%d')} | Historial de Promedios de los Últimos 6 Meses", styles['Normal']))
        elements.append(Spacer(1, 15))

        header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)
        body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#1E293B'), alignment=1)

        for d in datos_para_pdf:
            elements.append(Paragraph(f"<b>Paciente: {d['nombre']} (ID: {d['user_id']})</b>", styles['Heading2']))
            elements.append(Spacer(1, 4))
            
            hist_data = [[
                Paragraph("Mes", header_style),
                Paragraph("Cal. Consumid.", header_style),
                Paragraph("Cal. Quemad.", header_style),
                Paragraph("Bal. Neto", header_style),
                Paragraph("Proteínas (g)", header_style),
                Paragraph("Grasas (g)", header_style),
                Paragraph("Carbohidr. (g)", header_style),
                Paragraph("Fibras (g)", header_style)
            ]]

            for h in d["historial"]:
                hist_data.append([
                    Paragraph(h["mes"], body_style),
                    Paragraph(f"{h['cal_cons']} kcal", body_style),
                    Paragraph(f"{h['cal_quem']} kcal", body_style),
                    Paragraph(f"{h['bal_neto']} kcal", body_style),
                    Paragraph(f"{h['proteinas']} g", body_style),
                    Paragraph(f"{h['grasas']} g", body_style),
                    Paragraph(f"{h['carbohidratos']} g", body_style),
                    Paragraph(f"{h['fibras']} g", body_style)
                ])
            
            # Ancho total ajustado para la hoja tamaño carta (Letter = 612 pt de ancho - 40 pt de márgenes = 572 pt disponibles)
            t_hist = Table(hist_data, colWidths=[65, 75, 75, 70, 70, 70, 77, 70])
            t_hist.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2563EB")),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(t_hist)
            elements.append(Spacer(1, 15))

        doc.build(elements)
        buffer.seek(0)

        esp_limpia = re.sub(r'[^\w\s]', '', especialidad_prof).replace(' ', '_')

        await msg_espera.delete()
        await update.message.reply_text(texto_reporte, parse_mode="Markdown")
        await update.message.reply_document(
            document=buffer,
            filename=f"Reporte_Promedios_Clinicos_{esp_limpia}_{ahora.strftime('%Y-%m')}.pdf",
            caption="📄 **Reporte clínico mensual consolidado generado con éxito.**",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error al generar listado de pacientes para el profesional {prof_id}: {e}")
        await msg_espera.edit_text(f"❌ Ocurrió un error al procesar el listado clínico: {e}")

async def cmd_enviar_informe_actual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando para que el profesional seleccione un paciente de su lista y envíe el informe PDF.
    Uso: /informe
    """
    try:
        prof_id = await _verificar_y_obtener_profesional(update)
        if not prof_id:
            await update.message.reply_text("⛔ No tenés permisos para ejecutar este comando o no estás registrado como profesional.")
            return

        pacientes = obtener_pacientes_por_medico(prof_id)
        
        if not pacientes:
            await update.message.reply_text("📋 No tenés pacientes activos asignados en este momento.")
            return

        keyboard = []
        for pac in pacientes:
            callback_data = f"enviar_inf_{pac['user_id']}"
            keyboard.append([InlineKeyboardButton(f"👤 {pac['nombre']}", callback_data=callback_data)])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "📊 **Generación de Informe Médico**\nSeleccioná el paciente al que deseas enviarle el informe del período:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Error en cmd_enviar_informe_actual: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Ocurrió un error al procesar la solicitud del informe.")

async def callback_enviar_informe_paciente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 1: Muestra los promedios del paciente en pantalla y le da opciones al médico antes de enviar."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not data.startswith("enviar_inf_"):
        return

    target_user_id = data.replace("enviar_inf_", "").strip()
    ahora = obtener_ahora_arg()
    mes_actual = ahora.strftime("%Y-%m")

    # Guardar en contexto el paciente seleccionado
    context.user_data['informe_medico_target'] = target_user_id
    context.user_data['informe_medico_mes'] = mes_actual

    try:
        # Obtener datos y calcular métricas del mes actual para la previsualización
        df_u = obtener_datos_usuario(target_user_id) 
        perfil = obtener_perfil_usuario(target_user_id, mes_target=mes_actual) or {}
        
        if not df_u.empty and 'Fecha' in df_u.columns:
            df_u['Mes_Filtro'] = df_u['Fecha'].str.slice(0, 7)
            df_mes = df_u[df_u['Mes_Filtro'] == mes_actual]
        else:
            df_mes = pd.DataFrame()

        if df_mes.empty:
            resumen_txt = f"⚠️ El paciente con ID `{target_user_id}` no tiene registros cargados en el período actual (`{mes_actual}`).\n¿Desea enviarle el informe de todas formas?"
        else:
            m = calcular_metricas_mensuales(df_mes, perfil, user_id=target_user_id, mes_str=mes_actual)
            resumen_txt = (
                f"📋 **Previsualización de Informe Mensual ({mes_actual})**\n"
                f"👤 Paciente ID: `{target_user_id}`\n\n"
                f"• 🔥 Cal. Consumidas: `{m.get('prom_cal', 0)} kcal/día`\n"
                f"• ⚡ Cal. Quemadas: `{m.get('prom_quem', 0)} kcal/día`\n"
                f"• ⚖️ Balance Neto: `{m.get('prom_bal_neto', 0)} kcal/día`\n"
                f"• 🥩 Proteínas: `{m.get('prom_prot', 0)} g/día`\n"
                f"• 🥑 Grasas: `{m.get('prom_gras', 0)} g/día`\n"
                f"• 🍞 Carbohidratos: `{m.get('prom_carb', 0)} g/día`\n"
                f"• 🌾 Fibras: `{m.get('prom_fibr', 0)} g/día`\n\n"
                f"¿Cómo desea proceder con el envío?"
            )

        # Botones de decisión para el médico
        keyboard = [
            [InlineKeyboardButton("🚀 Enviar Directamente", callback_data=f"inf_dir_{target_user_id}")],
            [InlineKeyboardButton("✏️ Escribir Nota y Enviar", callback_data=f"inf_nota_{target_user_id}")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="inf_cancelar")]
        ]
        
        await query.edit_message_text(resumen_txt, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error al previsualizar informe para el paciente {target_user_id}: {e}")
        await query.edit_message_text(f"❌ Ocurrió un error al procesar la previsualización: {e}")


async def callback_acciones_informe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja las acciones de envío directo o solicitud de nota para el informe."""
    query = update.callback_query
    await query.answer()
    data = query.data
    prof_id = str(query.from_user.id).strip()

    if data.startswith("inf_dir_"):
        target_user_id = data.replace("inf_dir_", "").strip()
        mes_target = context.user_data.get('informe_medico_mes', obtener_ahora_arg().strftime("%Y-%m"))
        
        await query.edit_message_text(f"⏳ Generando y enviando informe al paciente `{target_user_id}`...", parse_mode="Markdown")
        
        try:
            exito = await procesar_y_enviar_informe_mensual(context, user_id=int(target_user_id), chat_destino=int(target_user_id), mes_target=mes_target, forzar_envio=True)
            
            if exito:
                # Notificar al paciente que su médico le envió una actualización
                await context.bot.send_message(chat_id=int(target_user_id), text="🩺 **Tu profesional a cargo te ha enviado una actualización de tu informe clínico mensual.**", parse_mode="Markdown")
                await query.edit_message_text(f"✅ **Informe enviado con éxito** al paciente con ID `{target_user_id}`.", parse_mode="Markdown")
            else:
                await query.edit_message_text(f"⚠️ No se pudo generar o enviar el informe al paciente `{target_user_id}` (quizás falten registros).", parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error en envío directo de informe por médico {prof_id}: {e}")
            await query.edit_message_text(f"❌ Error al enviar el informe: {e}")

    elif data.startswith("inf_nota_"):
        target_user_id = data.replace("inf_nota_", "").strip()
        context.user_data['esperando_nota_informe_para'] = target_user_id
        
        await query.edit_message_text(
            f"✅ Paciente seleccionado (ID: `{target_user_id}`).\n\n"
            "✍️ **Escribí a continuación la nota u observación médica** que querés adjuntar al informe:",
            parse_mode="Markdown"
        )

    elif data == "inf_cancelar":
        context.user_data.pop('informe_medico_target', None)
        context.user_data.pop('informe_medico_mes', None)
        await query.edit_message_text("❌ Operación cancelada.", parse_mode="Markdown")

async def procesar_texto_nota_informe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Captura la nota escrita por el médico, genera el informe y lo envía al paciente."""
    target_user_id = context.user_data.get('esperando_nota_informe_para')
    if not target_user_id:
        return False # No era una nota de informe, dejar pasar

    prof_id = str(update.effective_user.id).strip()
    nota_texto = update.message.text.strip()
    mes_target = context.user_data.get('informe_medico_mes', obtener_ahora_arg().strftime("%Y-%m"))
    
    # Limpiar estados del contexto
    context.user_data.pop('esperando_nota_informe_para', None)
    context.user_data.pop('informe_medico_target', None)
    context.user_data.pop('informe_medico_mes', None)

    try:
        msg_esp = await update.message.reply_text("⏳ **Generando informe con la nota médica adjunta...**", parse_mode="Markdown")
        
        exito = await procesar_y_enviar_informe_mensual(context, user_id=int(target_user_id), chat_destino=int(target_user_id), mes_target=mes_target, forzar_envio=True)
        
        if exito:
            # Enviar la nota personalizada del médico al paciente
            mensaje_paciente = f"🩺 **Nota de tu médico tratante:**\n\n\"{nota_texto}\""
            await context.bot.send_message(chat_id=int(target_user_id), text=mensaje_paciente, parse_mode="Markdown")
            
            await msg_esp.edit_text(f"✅ **Informe y nota médica enviados correctamente** al paciente con ID `{target_user_id}`.", parse_mode="Markdown")
        else:
            await msg_esp.edit_text(f"⚠️ No se pudo generar el informe para el paciente `{target_user_id}`.", parse_mode="Markdown")
        
        return True
    except Exception as e:
        logger.error(f"Error al enviar informe con nota desde el profesional {prof_id}: {e}")
        await update.message.reply_text(f"❌ Ocurrió un error al procesar el envío: {e}")
        return True





async def cmd_enviar_nota_paciente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando interactivo por botones para que el profesional seleccione al paciente 
    al que desea enviarle una nota o indicación médica.
    Uso: /nota o /enviar_nota
    """
    prof_id = str(update.effective_user.id).strip()
    
    especialidad_prof = obtener_especialidad_profesional(prof_id)
    if not especialidad_prof:
        await update.message.reply_text("⛔ **Acceso denegado:** Este comando es exclusivo para profesionales registrados.", parse_mode="Markdown")
        return

    pacientes = obtener_pacientes_por_medico(prof_id)
    if not pacientes:
        await update.message.reply_text("📋 No tenés pacientes activos asignados en este momento para enviarles notas.", parse_mode="Markdown")
        return

    # Armar teclado interactivo dinámico con los pacientes del médico
    keyboard = []
    for pac in pacientes:
        u_id = str(pac["user_id"])
        nombre = pac["nombre"]
        btn_text = f"👤 {nombre} (ID: {u_id})"
        callback_data = f"selec_nota_pac_{u_id}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📝 **Envío de Nota Médica**\n\n"
        "Seleccioná de la lista al paciente al que querés enviarle una indicación:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def callback_seleccionar_paciente_nota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la selección del paciente por botón para la nota y activa el estado de espera del mensaje."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not data.startswith("selec_nota_pac_"):
        return

    target_user_id = data.replace("selec_nota_pac_", "").strip()
    
    # Guardar el ID objetivo en el contexto del usuario para capturar su siguiente mensaje de texto
    context.user_data['esperando_texto_nota_para'] = target_user_id

    await query.edit_message_text(
        f"✅ Paciente seleccionado (ID: `{target_user_id}`).\n\n"
        "✍️ **Escribí a continuación el texto de la nota o indicación** que querés enviarle:",
        parse_mode="Markdown"
    )


async def procesar_texto_nota_medica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Captura el texto escrito por el médico tras haber seleccionado al paciente y se lo envía."""
    target_user_id = context.user_data.get('esperando_texto_nota_para')
    if not target_user_id:
        return False # No era una nota pendiente, dejar pasar a otros message handlers

    prof_id = str(update.effective_user.id).strip()
    nota_texto = update.message.text.strip()
    
    # Limpiar estado del contexto
    context.user_data.pop('esperando_texto_nota_para', None)

    especialidad_prof = obtener_especialidad_profesional(prof_id)

    try:
        mensaje_paciente = (
            f"🩺 **Indicación de tu médico tratante ({especialidad_prof}):**\n\n"
            f"\"{nota_texto}\""
        )
        
        await context.bot.send_message(chat_id=int(target_user_id), text=mensaje_paciente, parse_mode="Markdown")
        await update.message.reply_text(f"✅ **Nota enviada correctamente** al paciente con ID `{target_user_id}`.", parse_mode="Markdown")
        return True
    except Exception as e:
        logger.error(f"Error al enviar nota interactiva del profesional {prof_id} al paciente {target_user_id}: {e}")
        await update.message.reply_text(f"❌ Ocurrió un error al enviar la nota: {e}")
        return True


async def cmd_generar_manual_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /manual: Muestra por pantalla el resumen de comandos disponibles para el profesional 
    y adjunta el manual operativo oficial en PDF de 3 páginas.
    """
    prof_id = str(update.effective_user.id).strip()
    
    especialidad_prof = obtener_especialidad_profesional(prof_id)
    if not especialidad_prof:
        await update.message.reply_text("⛔ **Acceso denegado:** Este comando es exclusivo para profesionales registrados.", parse_mode="Markdown")
        return

    # 1. Enviar el resumen interactivo de comandos disponibles en pantalla
    resumen_comandos = (
        "🩺 **Panel de Control — Guía de Comandos Profesionales**\n\n"
        "• `/pacientes`: Genera un reporte clínico consolidado en PDF con el historial de los últimos 6 meses de tus pacientes.\n"
        "• `/informe`: Despliega un menú táctil para auditar y reenviar el informe mensual individual en PDF.\n"
        "• `/editar_valores`: Panel interactivo para consultar y corregir las metas clínicas (TMB, GET, macros, peso de etapa).\n"
        "• `/nota` (o `/enviar_nota`): Despliega los botones con tus pacientes para enviarles notas clínicas o directivas directas.\n"
        "• `/manual`: Muestra esta guía rápida y adjunta el manual completo en PDF.\n\n"
        "📄 *A continuación se adjunta el documento técnico operativo completo:*"
    )
    await update.message.reply_text(resumen_comandos, parse_mode="Markdown")

    # 2. Generar y enviar el PDF completo
    msg_espera = await update.message.reply_text("⏳ **Generando el manual operativo oficial de 3 páginas...**", parse_mode="Markdown")

    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=letter, 
            rightMargin=36, 
            leftMargin=36, 
            topMargin=36, 
            bottomMargin=36
        )
        
        styles = getSampleStyleSheet()
        c_primario = colors.HexColor('#1E3A8A')
        c_secundario = colors.HexColor('#2563EB')
        c_texto = colors.HexColor('#1E293B')
        c_fondo_tbl = colors.HexColor('#F8FAFC')
        
        title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20, textColor=c_primario, spaceAfter=4, alignment=1)
        subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=10, leading=13, textColor=c_secundario, spaceAfter=10, alignment=1)
        h1_style = ParagraphStyle('H1Style', parent=styles['Heading2'], fontSize=12, leading=15, textColor=c_primario, spaceBefore=8, spaceAfter=4)
        body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=8.5, leading=11.5, textColor=c_texto, spaceAfter=5)
        bullet_style = ParagraphStyle('BulletStyle', parent=styles['Normal'], fontSize=8.5, leading=11.5, textColor=c_texto, leftIndent=10, spaceAfter=3)
        
        story = []

        # PÁGINA 1
        story.append(Paragraph("<b>IA NutriBot — Sistema de Gestión y Supervisión Clínica</b>", title_style))
        story.append(Paragraph("<b>Manual Operativo y Especificaciones Técnicas para Profesionales</b>", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=1.2, color=c_secundario, spaceAfter=8))
        
        story.append(Paragraph("<b>1. Resumen de Ventajas y Propuesta de Valor</b>", h1_style))
        story.append(Paragraph("IA NutriBot combina la accesibilidad masiva de Telegram con una potente capa clínica de supervisión:", body_style))
        
        ventajas = [
            "<b>• Supremacía Clínica:</b> El bot respeta estrictamente los criterios del médico tratante por sobre las fórmulas matemáticas estándar.",
            "<b>• Protección del Tiempo Profesional:</b> Canales de salida <b>unidireccionales</b> (notas y recetas) para evitar saturación de consultas.",
            "<b>• Alertas de Desvío Automáticas:</b> Al cierre mensual, el sistema audita registros y reenvía una copia con alertas si el paciente sale de rango.",
            "<b>• Autogestión Segura:</b> Calibración mediante relojes inteligentes acotada estrictamente a partir del día 15 y con topes del 20%.",
            "<b>• Trazabilidad de 6 Meses:</b> Arquitectura robusta en Python y Supabase para almacenar historiales clínicos consolidados."
        ]
        for v in ventajas:
            story.append(Paragraph(v, bullet_style))
        
        story.append(PageBreak())

        # PÁGINA 2
        story.append(Paragraph("<b>2. Guía de Comandos y Funciones del Módulo Profesional</b>", h1_style))
        story.append(Paragraph("El profesional opera de forma directa mediante comandos de texto y menús interactivos táctiles:", body_style))
        
        tabla_funciones = [
            [Paragraph("<b>Comando</b>", ParagraphStyle('Th', parent=body_style, textColor=colors.white, fontName='Helvetica-Bold')), 
             Paragraph("<b>Descripción y Alcance Operativo</b>", ParagraphStyle('Th2', parent=body_style, textColor=colors.white, fontName='Helvetica-Bold'))],
            [Paragraph("<b>/pacientes</b>", body_style), Paragraph("Genera un reporte PDF clínico con el historial de los últimos 6 meses de todos los pacientes asignados.", body_style)],
            [Paragraph("<b>/informe</b>", body_style), Paragraph("Despliega botones interactivos con nombres e IDs para reenviar el informe mensual en PDF de manera individual.", body_style)],
            [Paragraph("<b>/editar_valores</b>", body_style), Paragraph("Panel táctil interactivo para visualizar metas actuales (TMB, GET, peso de etapa) y corregirlas al instante.", body_style)],
            [Paragraph("<b>/nota</b>", body_style), Paragraph("Despliega botones interactivos con tus pacientes para enviarles notas o indicaciones médicas directas.", body_style)],
            [Paragraph("<b>/manual</b>", body_style), Paragraph("Muestra el resumen de comandos en pantalla y adjunta el manual completo en PDF.", body_style)]
        ]
        
        t_func = Table(tabla_funciones, colWidths=[110, 430])
        t_func.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), c_primario),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_fondo_tbl]),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(t_func)
        
        story.append(PageBreak())




        # PÁGINA 3
        story.append(Paragraph("<b>3. Base de Datos: Valores_Clinicos_Profesional</b>", h1_style))
        story.append(Paragraph("La persistencia de los valores clínicos personalizados se administra mediante la siguiente estructura relacional:", body_style))
        
        tabla_db = [
            [Paragraph("<b>Columna SQL</b>", ParagraphStyle('Th3', parent=body_style, textColor=colors.white, fontName='Helvetica-Bold')), 
             Paragraph("<b>Tipo</b>", ParagraphStyle('Th4', parent=body_style, textColor=colors.white, fontName='Helvetica-Bold')),
             Paragraph("<b>Descripción del Parámetro Clínico</b>", ParagraphStyle('Th5', parent=body_style, textColor=colors.white, fontName='Helvetica-Bold'))],
            [Paragraph("`user_id` / `prof_id`", body_style), Paragraph("TEXT", body_style), Paragraph("Identificadores de Telegram vinculados.", body_style)],
            [Paragraph("`mes`", body_style), Paragraph("VARCHAR", body_style), Paragraph("Período de validez en formato `YYYY-MM`.", body_style)],
            [Paragraph("`tmb` / `get_val`", body_style), Paragraph("NUMERIC", body_style), Paragraph("Tasa metabólica basal y gasto energético total.", body_style)],
            [Paragraph("`peso_etapa`", body_style), Paragraph("NUMERIC", body_style), Paragraph("Meta de peso establecida para la etapa.", body_style)],
            [Paragraph("`calorias_min/max`", body_style), Paragraph("NUMERIC", body_style), Paragraph("Topes de control calórico permitidos.", body_style)],
            [Paragraph("`proteinas/hidratos/grasas`", body_style), Paragraph("NUMERIC", body_style), Paragraph("Rangos de macronutrientes asignados.", body_style)]
        ]
        
        t_db = Table(tabla_db, colWidths=[120, 70, 350])
        t_db.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), c_secundario),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_fondo_tbl]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_db)
        story.append(Spacer(1, 15))
        story.append(Paragraph("<b>Sistema Operativo:</b> 100% Sincronizado y Funcional (Módulos 08, 09 y 11)", ParagraphStyle('Firma', parent=body_style, textColor=colors.HexColor('#64748B'))))

        doc.build(story)
        buffer.seek(0)

        await msg_espera.delete()
        await update.message.reply_document(
            document=buffer,
            filename="Manual_Profesional_IA_NutriBot.pdf",
            caption="📄 **Aquí tenés el manual oficial completo en PDF.**",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error al generar el manual PDF para el profesional {prof_id}: {e}")
        await msg_espera.edit_text(f"❌ Ocurrió un error al generar el documento PDF: {e}")
        
# ==========================================================================================================================================
#                    FINAL                      COMANDOS PROFESIONALES                               FINAL  
# ==========================================================================================================================================


