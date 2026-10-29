
import os
import io
import re
import pandas as pd
import logging
from telegram import Update
from telegram.ext import ContextTypes

# Importamos las herramientas de tu archivo central (bot8a.py)
from bot8a import _obtener_conexion_db, _asegurar_tabla_y_conectar, es_administrador

logger = logging.getLogger(__name__)

# =============================================================================================================================================
#              INICIO                              FUNCIONES ADMINISTRADOR                           INICIO
# =============================================================================================================================================

# ---------------------------------------------------------------------------------------------------------------------------------------------
# COMANDO DE TELEGRAM: /desarmar (PASO 1 para traducir el Excel afuera sin romper variables)
# CÓMO SE USA EN TELEGRAM: /desarmar
# ¿QUÉ HACE?:
#   1. Lee el archivo 'multi.xlsx' que está en el servidor (debe tener columnas 'variables' y 'ES').
#   2. Busca todo lo que esté entre llaves {variable} o corchetes [variable] y lo reemplaza por códigos (__VAR_0001__, etc.).
#   3. Te envía por Telegram un Excel llamado 'multi_desarmado.xlsx' con 2 pestañas:
#      - Pestaña 'traduccion': Lista para que la subas a Google Drive/Sheets y traduzcas con fórmulas GOOGLETRANSLATE.
#      - Pestaña 'diccionario_vars': Guarda qué significaba cada código __VAR_XXXX__ para poder rearmarlo después.
# ---------------------------------------------------------------------------------------------------------------------------------------------
async def cmd_desarmar_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if not es_administrador(user_id):
        return

    nombre_tabla = "multi"

    try:
        ruta_archivo = f"{nombre_tabla}.xlsx"
        if not os.path.exists(ruta_archivo):
            msg_no_enc = f"❌ No encuentro el archivo `{ruta_archivo}` en el servidor."
            await update.message.reply_text(msg_no_enc, parse_mode="Markdown")
            return

        df = pd.read_excel(ruta_archivo)
        df.columns = [str(c).strip() for c in df.columns]

        # Buscar nombres reales de columnas 'variables' y 'ES' sin importar mayúsculas/minúsculas
        col_vars = next((c for c in df.columns if c.lower() == 'variables'), None)
        col_es = next((c for c in df.columns if c.upper() == 'ES'), None)

        if not col_vars or not col_es:
            msg_cols = "❌ El archivo base debe tener columnas 'variables' y 'ES'."
            await update.message.reply_text(msg_cols, parse_mode="Markdown")
            return

        # Limpiar nombres de variables y dejar SOLO LA ÚLTIMA VERSIÓN si hay repetidas
        df[col_vars] = df[col_vars].astype(str).str.strip()
        df = df[df[col_vars].notna() & (df[col_vars] != "") & (df[col_vars].str.lower() != "nan")]
        df = df.drop_duplicates(subset=[col_vars], keep='last').reset_index(drop=True)

        mapa_variables = {}
        mapa_inverso = {}
        contador_var = 1
        textos_preparados = []

        # Función interna para reemplazar cada {var} o [var] de forma exacta sin colisiones
        def reemplazar_placeholder(match):
            nonlocal contador_var
            ph = match.group(0)
            if ph in mapa_inverso:
                return mapa_inverso[ph]
            token = f"__VAR_{contador_var:04d}__"
            mapa_variables[token] = ph
            mapa_inverso[ph] = token
            contador_var += 1
            return token

        patron_ph = re.compile(r'(\[[^\]\n]+\]|\{[^}\n]+\})')

        for _, row in df.iterrows():
            texto_es = str(row[col_es]) if pd.notna(row[col_es]) else ""
            if not texto_es.strip() or texto_es.strip().lower() == 'nan':
                textos_preparados.append("")
                continue

            texto_modificado = patron_ph.sub(reemplazar_placeholder, texto_es)
            textos_preparados.append(texto_modificado)

        df_hoja1 = pd.DataFrame()
        df_hoja1['variables'] = df[col_vars]
        df_hoja1['ES'] = textos_preparados

        lista_diccionario = [{"codigo": k, "variable_original": v} for k, v in mapa_variables.items()]
        df_hoja2 = pd.DataFrame(lista_diccionario)

        nombre_salida = f"{nombre_tabla}_desarmado.xlsx"
        
        buffer_out = io.BytesIO()
        with pd.ExcelWriter(buffer_out, engine='openpyxl') as writer:
            df_hoja1.to_excel(writer, index=False, sheet_name='traduccion')
            df_hoja2.to_excel(writer, index=False, sheet_name='diccionario_vars')
        buffer_out.seek(0)

        msg_exito = (
            "✅ **¡Archivo desarmado detectando todas las variables y corchetes!**\n\n"
            "1. Subilo a Google Drive, agregale las columnas de idiomas que quieras (`EN`, `IT`, etc.) y traducilo.\n"
            "2. La segunda pestaña (`diccionario_vars`) ahora indexa el 100% de las variables sin cortes.\n"
            "3. Cuando termines, mandámelo con `/armar`."
        )

        await update.message.reply_document(
            document=buffer_out,
            filename=nombre_salida,
            caption=msg_exito,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error en desarmar Excel: {e}", exc_info=True)
        msg_err_gen = f"❌ Error: `{e}`"
        await update.message.reply_text(msg_err_gen, parse_mode="Markdown")

# ---------------------------------------------------------------------------------------------------------------------------------------------
# COMANDO DE TELEGRAM: /armar (Lee el Excel desarmado directamente del servidor, restaura variables y sube a Supabase)
# CÓMO SE USA EN TELEGRAM: /armar  (o /armar agregar)
# ¿QUÉ HACE?:
#   1. Busca el archivo 'multi_desarmado.xlsx' directamente en la carpeta del servidor.
#   2. Lee las solapas 'traduccion' y 'diccionario_vars'.
#   3. Reemplaza todos los códigos __VAR_XXXX__ por sus llaves o corchetes originales.
#   4. Si se pasa el argumento "agregar", inserta los registros sin borrar la tabla. 
#      Si no se pasa, borra y recrea la tabla por completo como antes.
# ---------------------------------------------------------------------------------------------------------------------------------------------

async def cmd_armar_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if not es_administrador(user_id):
        return

    # Verificar si el usuario escribió /armar agregar
    modo_agregar = False
    if context.args and len(context.args) > 0:
        if context.args[0].strip().lower() == "agregar":
            modo_agregar = True

    nombre_tabla = "multi"
    ruta_archivo = f"{nombre_tabla}_desarmado.xlsx"

    if not os.path.exists(ruta_archivo):
        msg_no_enc = f"❌ No encuentro el archivo `{ruta_archivo}` en el servidor. Asegurate de haber subido el archivo traducido al repositorio o carpeta del bot."
        await update.message.reply_text(msg_no_enc, parse_mode="Markdown")
        return

    msg_leyendo = "🔄 Leyendo del servidor, ensamblando traducciones y sincronizando Supabase..."
    mensaje_espera = await update.message.reply_text(msg_leyendo, parse_mode="Markdown")

    try:
        xls = pd.ExcelFile(ruta_archivo)
        sheets = xls.sheet_names

        if 'traduccion' not in sheets or 'diccionario_vars' not in sheets:
            msg_solapas = "❌ El archivo en el servidor no tiene las solapas requeridas ('traduccion' y 'diccionario_vars')."
            await mensaje_espera.edit_text(msg_solapas, parse_mode="Markdown")
            return

        df_trad = pd.read_excel(ruta_archivo, sheet_name='traduccion')
        df_dict = pd.read_excel(ruta_archivo, sheet_name='diccionario_vars')

        df_trad.columns = [str(c).strip() for c in df_trad.columns]
        df_dict.columns = [str(c).strip() for c in df_dict.columns]

        # Eliminar columna 'id' si vino heredada de una descarga previa de Supabase
        cols_id = [c for c in df_trad.columns if c.lower() == 'id']
        if cols_id:
            df_trad = df_trad.drop(columns=cols_id)

        # Identificar explícitamente la columna 'variables' y quedarnos SOLO CON LA ÚLTIMA si hay repetidas
        col_vars = next((c for c in df_trad.columns if c.lower() == 'variables'), df_trad.columns[0])
        df_trad[col_vars] = df_trad[col_vars].astype(str).str.strip()
        df_trad = df_trad[df_trad[col_vars].notna() & (df_trad[col_vars] != "") & (df_trad[col_vars].str.lower() != "nan")]
        df_trad = df_trad.drop_duplicates(subset=[col_vars], keep='last').reset_index(drop=True)

        # Mapa de códigos por número ('0001' -> '{peso}') para tolerar alteraciones del traductor
        mapa_por_num = {}
        if not df_dict.empty and 'codigo' in df_dict.columns and 'variable_original' in df_dict.columns:
            for _, r_d in df_dict.iterrows():
                cod_str = str(r_d['codigo']).strip()
                orig_str = str(r_d['variable_original'])
                m_num = re.search(r'(\d{4})', cod_str)
                if m_num:
                    mapa_por_num[m_num.group(1)] = orig_str

        # Regex tolerante a espacios, mayúsculas/minúsculas que Google Translate suele alterar
        patron_restaurar = re.compile(r'_\s*_\s*VAR\s*_\s*(\d{4})\s*_\s*_', re.IGNORECASE)

        def restaurar_token(match):
            num_id = match.group(1)
            return mapa_por_num.get(num_id, match.group(0))

        columnas_idiomas = [c for c in df_trad.columns if c.lower() != col_vars.lower()]

        for col in columnas_idiomas:
            nueva_columna = []
            for _, val in df_trad[col].items():
                texto = str(val) if pd.notna(val) else ""
                if not texto.strip() or texto.strip().lower() == 'nan':
                    nueva_columna.append("")
                    continue

                texto = patron_restaurar.sub(restaurar_token, texto)
                texto = re.sub(r'\\\s+n', r'\\n', texto)

                nueva_columna.append(texto)
            
            df_trad[col] = nueva_columna

        # Guardar copia limpia localmente como 'multi.xlsx'
        ruta_archivo_local = f"{nombre_tabla}.xlsx"
        df_trad.to_excel(ruta_archivo_local, index=False)

        # Lógica según el modo:
        if modo_agregar:
            # Modo agregar: Nos conectamos sin hacer DROP, asegurando únicamente conexión estándar
            conn = _obtener_conexion_db()
            cur = conn.cursor()
        else:
            # Modo normal: Borra la tabla y la crea de cero
            conn, cur = _asegurar_tabla_y_conectar(nombre_tabla, df_muestra=df_trad)

        columnas = list(df_trad.columns)
        cols_sql = ', '.join([f'"{c}"' for c in columnas])
        placeholders = ', '.join(['%s'] * len(columnas))
        
        query_insert = f'INSERT INTO "{nombre_tabla}" ({cols_sql}) VALUES ({placeholders})'

        filas_insertadas = 0
        for _, row in df_trad.iterrows():
            valores = [None if pd.isna(row[col]) else str(row[col]).strip() for col in columnas]
            cur.execute(query_insert, tuple(valores))
            filas_insertadas += 1

        conn.commit()
        cur.close()
        conn.close()

        if modo_agregar:
            msg_exito = f"➕ **¡Bloque agregado con éxito!**\nSe añadieron {filas_insertadas} registros nuevos a la tabla `{nombre_tabla}` en Supabase sin borrar los anteriores."
        else:
            msg_exito = f"🏆 **¡Traducción aplicada con éxito!**\nLa tabla `{nombre_tabla}` fue completamente reemplazada en Supabase con {filas_insertadas} registros procesados desde el servidor."
        
        await mensaje_espera.edit_text(msg_exito, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error armando Excel desde el servidor: {e}", exc_info=True)
        msg_err_armar = f"❌ Error al ensamblar: `{e}`"
        await mensaje_espera.edit_text(msg_err_armar, parse_mode="Markdown")

# ---------------------------------------------------------------------------------------------------------------------------------------------
# COMANDO DE TELEGRAM: /subir (Pasa un archivo .xlsx que ya esté en GitHub/Servidor directo a Supabase)
# CÓMO SE USA EN TELEGRAM: /subir multi   (o el nombre de cualquier archivo .xlsx que hayas subido a GitHub)
# ¿QUÉ HACE?: Busca el archivo '<nombre>.xlsx' en la carpeta del servidor, borra la tabla en Supabase
#             y la vuelve a crear cargando todas las filas tal cual están en ese Excel (sin traducir ni modificar nada).
# ---------------------------------------------------------------------------------------------------------------------------------------------
async def cmd_subir(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if not es_administrador(user_id):
        return
    
    if not context.args or len(context.args) == 0:
        msg_formato = "⚠️ Por favor, indica el nombre de la tabla a importar.\nEjemplo: `/subir multi`"
        await update.message.reply_text(msg_formato, parse_mode="Markdown")
        return

    nombre_tabla = context.args[0].strip()
    ruta_archivo = f"{nombre_tabla}.xlsx"

    if not os.path.exists(ruta_archivo):
        msg_no_enc = f"❌ No encontré el archivo `{ruta_archivo}` en el servidor. Asegurate de haberlo subido al repositorio de GitHub."
        await update.message.reply_text(msg_no_enc, parse_mode="Markdown")
        return

    msg_leyendo = f"🔄 Leyendo `{ruta_archivo}` del servidor y reescribiendo la tabla `{nombre_tabla}` en Supabase..."
    mensaje_espera = await update.message.reply_text(msg_leyendo, parse_mode="Markdown")

    try:
        df = pd.read_excel(ruta_archivo)

        if df.empty:
            msg_vacio = f"⚠️ El archivo `{ruta_archivo}` está vacío."
            await mensaje_espera.edit_text(msg_vacio, parse_mode="Markdown")
            return

        df.columns = [str(c).strip() for c in df.columns]

        conn, cur = _asegurar_tabla_y_conectar(nombre_tabla, df_muestra=df)

        columnas = list(df.columns)
        cols_sql = ', '.join([f'"{c}"' for c in columnas])
        placeholders = ', '.join(['%s'] * len(columnas))
        
        query_insert = f'INSERT INTO "{nombre_tabla}" ({cols_sql}) VALUES ({placeholders})'

        filas_insertadas = 0
        for _, row in df.iterrows():
            valores = []
            for col in columnas:
                val = row[col]
                if pd.isna(val):
                    val = None
                else:
                    val = str(val).strip()
                valores.append(val)

            cur.execute(query_insert, tuple(valores))
            filas_insertadas += 1

        conn.commit()
        cur.close()
        conn.close()

        msg_exito = f"✅ ¡Éxito! La tabla `{nombre_tabla}` fue leída del servidor y sincronizada en Supabase con {filas_insertadas} registros."
        await mensaje_espera.edit_text(msg_exito, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error al importar la tabla {nombre_tabla} desde el servidor: {e}", exc_info=True)
        msg_err = f"❌ Error al importar la tabla: `{e}`"
        await mensaje_espera.edit_text(msg_err, parse_mode="Markdown")

# ---------------------------------------------------------------------------------------------------------------------------------------------
# COMANDO DE TELEGRAM: /descargar (Descarga cualquier tabla de Supabase a un archivo Excel)
# CÓMO SE USA EN TELEGRAM: /descargar multi   o   /descargar Usuarios
# ¿QUÉ HACE?: Consulta la tabla en vivo en Supabase, arma un archivo .xlsx en memoria y te lo envía por Telegram
#             para que lo tengas de backup o lo puedas revisar en tu PC.
# ---------------------------------------------------------------------------------------------------------------------------------------------
async def cmd_descargar(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if not es_administrador(user_id):
        return
    
    if not context.args or len(context.args) == 0:
        msg_formato = "⚠️ Por favor, indica el nombre de la tabla que deseas descargar.\nEjemplo: `/descargar textos_bot` o `/descargar Usuarios`"
        await update.message.reply_text(msg_formato, parse_mode="Markdown")
        return

    nombre_tabla = context.args[0].strip()
    msg_consultando = f"⏳ Consultando y preparando la tabla `{nombre_tabla}`..."
    mensaje_espera = await update.message.reply_text(msg_consultando, parse_mode="Markdown")

    try:
        conn, cur = _asegurar_tabla_y_conectar(nombre_tabla, tipo_tabla="comida")
        query = f'SELECT * FROM "{nombre_tabla}"'
        df = pd.read_sql(query, conn)
        
        cur.close()
        conn.close()

        if df.empty:
            msg_vacia = f"⚠️ La tabla `{nombre_tabla}` existe pero está vacía."
            await mensaje_espera.edit_text(msg_vacia, parse_mode="Markdown")
            return

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=nombre_tabla[:31])
        buffer.seek(0)

        filename = f"{nombre_tabla}.xlsx"
        
        msg_exito = f"✅ Aquí tienes el respaldo de la tabla *{nombre_tabla}* ({len(df)} registros)."
        await update.message.reply_document(
            document=buffer,
            filename=filename,
            caption=msg_exito,
            parse_mode="Markdown"
        )
        
        try:
            await mensaje_espera.delete()
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Error al descargar la tabla {nombre_tabla} para el usuario {user_id}: {e}", exc_info=True)
        msg_err = f"❌ No se pudo descargar la tabla `{nombre_tabla}`.\nError: `{e}`"
        await mensaje_espera.edit_text(msg_err, parse_mode="Markdown")   

# =========================================================================================================================================
#              FINAL                             FUNCIONES ADMINISTRADOR                                  FINAL
# ==========================================================================================================================================
