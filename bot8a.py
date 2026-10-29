
# ==============================================================================================================================================
#                                 INICIO                                   CABECERA 2026 09 05                                    INICIO
#                                  https://github.com/rosalexxi/telegram-bot-nutricion
#                                  https://dashboard.render.com/web/srv-d9lcifijnfac73a8q1eg/events
#                                  https://supabase.com/dashboard/project/xsheilmjewqcvhmyqlnx/editor/17944?schema=public
#                                  https://dashboard.uptimerobot.com/monitors
#                                  https://ttsmaker.com/
# ==============================================================================================================================================

import os
import re
import io
import json
import base64
import threading
import inspect
import logging
import asyncio
import psycopg2  
import sys
import pytz
import pandas as pd
import html  
import cv2
import numpy as np
import requests
import math
import calendar
import time as time_mod
import google.generativeai as genai

from typing import Dict, Tuple, List, Optional, Any            
from urllib.parse import urlparse 
from datetime import datetime, date, timedelta, time
from dateutil.relativedelta import relativedelta
from flask import Flask, request, jsonify, render_template_string, send_from_directory, url_for
from functools import wraps
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, WebAppInfo
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    PreCheckoutQueryHandler,
    ConversationHandler
)

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# Definición de franjas horarias (sin tildes)
FRANJAS_COMIDAS = {
    "Desayuno": (8, 11),
    "Almuerzo": (11, 16),
    "Merienda": (16, 20),
    "Cena": (20, 24)
}

# Estados de conversación para Perfil y Fecha personalizada
AWAITING_PROFILE_DATA, AWAITING_CUSTOM_DATE, AWAITING_RESUMEN_MES, AWAITING_EDIT_ITEM = range(4)

# 1. ESTADOS DE CONVERSACIÓN ACTUALIZADOS
ING_TERMINOS, ING_IDIOMA, ING_PROFESIONAL, ING_NOMBRE, ING_EDAD, ING_SEXO, ING_ALTURA, ING_PESO, ING_MUNECA, ING_CUELLO, ING_CADERA, ING_OCUPACION, ING_CUMPLE, ING_RITMO = range(10, 24)

# Configuración de Entorno
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ARG_TZ = pytz.timezone('America/Argentina/Buenos_Aires')
PATTERN_VARS = re.compile(r'\{[^}]+\}')
ADMIN_USER_ID = "7363062724"  # Reemplazá esto por tu número de ID de Telegram real

# ==========================================
# INICIALIZACIÓN DE GEMINI Y MODELOS
# ==========================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY, transport="rest")
    
MODELO_TEXTO = "gemini-3.1-flash-lite"
MODELO_FOTO = "gemini-3.8-flash"  
MODELO_AUDIO = "gemini-3.1-flash-lite"
MODELO_RESPALDO = "gemini-3-flash-preview"
MODELO_EMERGENCIA = "gemini-3.5-flash-lite"
MODELO_FOTO_EMERGENCIA = "gemini-3.5-flash-lite"

# ==========================================
# ÚNICA INSTANCIA DE FLASK PARA TODO EL BOT
# ==========================================
app = Flask(__name__)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# =====================================================================================================================================
#                FINAL                                   CABECERA                                       FINAL
# =====================================================================================================================================

# =============================================================================================================================================
#              INICIO                                   FUNCIONES SUPABASE                           INICIO
# =============================================================================================================================================
#              INICIO                                   FUNCIONES CONEXIONES                            
# =============================================================================================================================================

def _obtener_conexion_db():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise Exception("DATABASE_URL no está configurada en las variables de entorno.")
    if "?" in db_url:
        if "sslmode" not in db_url:
            db_url += "&sslmode=require"
    else:
        db_url += "?sslmode=require"
    return psycopg2.connect(db_url)

def _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comida"):
    conn = _obtener_conexion_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
          AND LOWER(table_name) = LOWER(%s)
    """, (tabla_nombre,))
    row = cur.fetchone()

    if row:
        tabla_real = row[0]
    else:
        tabla_real = tabla_nombre

        if tipo_tabla == "comida":
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS "{tabla_real}" (
                    id SERIAL PRIMARY KEY,
                    "Fecha" TEXT,
                    "Momento/Actividad" TEXT,
                    "Alimento/Detalle" TEXT,
                    "Peso (g)" DOUBLE PRECISION,
                    "Calorías (kcal)" DOUBLE PRECISION,
                    "Proteínas (g)" DOUBLE PRECISION,
                    "Grasas (g)" DOUBLE PRECISION,
                    "Hidratos (g)" DOUBLE PRECISION,
                    "Fibras (g)" DOUBLE PRECISION
                );
            """)
        elif tipo_tabla == "perfil":
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS "{tabla_real}" (
                    id SERIAL PRIMARY KEY,
                    "EDAD" TEXT,
                    "PESO" DOUBLE PRECISION,
                    "ALTURA" DOUBLE PRECISION,
                    "GENERO" TEXT,
                    "ocupacion" DOUBLE PRECISION,
                    "MES" TEXT,
                    "Fecha_Actualizacion" TEXT,
                    "Cumple" TEXT
                );
            """)
        elif tipo_tabla == "presion":
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS "{tabla_real}" (
                    id SERIAL PRIMARY KEY,
                    "Fecha_Hora" TEXT,
                    "Fecha_Dia" TEXT,
                    "Alta" DOUBLE PRECISION,
                    "Baja" DOUBLE PRECISION,
                    "Pulsaciones" DOUBLE PRECISION,
                    "Nota" TEXT
                );
            """)
        elif tipo_tabla == "comidas_precargadas":
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS "{tabla_real}" (
                    id SERIAL PRIMARY KEY,
                    "Nombre" TEXT,
                    "Descripcion" TEXT,
                    "Peso" DOUBLE PRECISION,
                    "Calorias" DOUBLE PRECISION,
                    "Proteinas" DOUBLE PRECISION,
                    "Grasas" DOUBLE PRECISION,
                    "Carbohidratos" DOUBLE PRECISION,
                    "Fibras" DOUBLE PRECISION
                );
            """)
        elif tipo_tabla == "usuarios":
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS "{tabla_real}" (
                    id SERIAL PRIMARY KEY,
                    "User ID" TEXT UNIQUE,
                    "Nombre" TEXT,
                    "Estado" INTEGER,
                    "Ultimo Mes Peso" TEXT,
                    "Notificaciones" TEXT,
                    "Fecha Alta" TEXT,
                    "Sexo" TEXT,
                    "cumple" TEXT,
                    "profesional" TEXT,
                    "reloj_actualizado_mes" TEXT,
                    "Idioma" TEXT,
                    "cintura_cm" DOUBLE PRECISION,
                    "cuello_cm" DOUBLE PRECISION,
                    "cadera_cm" DOUBLE PRECISION,
                    "ritmo_preferido" TEXT,
                    "dias_inactivo" INTEGER DEFAULT 0,
                    "plan_preferido" TEXT,
                    "vencimiento_suscripcion" TEXT,
                    "saldo_estrellas" INTEGER DEFAULT 0,
                    "profesional_pendiente" TEXT
                );
            """)
        elif tipo_tabla == "categorias_comida":
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS "{tabla_real}" (
                    id SERIAL PRIMARY KEY,
                    "Carne Vacuna" TEXT,
                    "Pollo" TEXT,
                    "Cerdo" TEXT,
                    "Pescado" TEXT,
                    "Lacteos" TEXT,
                    "Verduras" TEXT,
                    "Frutas" TEXT,
                    "Harinas Refinadas" TEXT,
                    "Harinas Integrales" TEXT
                );
            """)
        elif tipo_tabla == "profesionales":
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS "{tabla_real}" (
                    id SERIAL PRIMARY KEY,
                    "User ID" TEXT,
                    "Nombre" TEXT,
                    "Especialidad" TEXT
                );
            """)
        elif tipo_tabla == "planes":
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS "{tabla_real}" (
                    id SERIAL PRIMARY KEY,
                    "plan_id" TEXT UNIQUE,
                    "descripcion" TEXT,
                    "estrellas" INTEGER,
                    "meses" INTEGER DEFAULT 1,
                    "activo" BOOLEAN DEFAULT TRUE
                );
            """)
        conn.commit()

    if tipo_tabla == "usuarios":
        try:
            cur.execute(f'ALTER TABLE "{tabla_real}" ADD COLUMN IF NOT EXISTS "cadera_cm" DOUBLE PRECISION;')
            cur.execute(f'ALTER TABLE "{tabla_real}" ADD COLUMN IF NOT EXISTS "dias_inactivo" INTEGER DEFAULT 0;')
            cur.execute(f'ALTER TABLE "{tabla_real}" ADD COLUMN IF NOT EXISTS "plan_preferido" TEXT;')
            cur.execute(f'ALTER TABLE "{tabla_real}" ADD COLUMN IF NOT EXISTS "vencimiento_suscripcion" TEXT;')
            cur.execute(f'ALTER TABLE "{tabla_real}" ADD COLUMN IF NOT EXISTS "saldo_estrellas" INTEGER DEFAULT 0;')
            cur.execute(f'ALTER TABLE "{tabla_real}" ADD COLUMN IF NOT EXISTS "profesional_pendiente" TEXT;')
            conn.commit()
        except Exception:
            conn.rollback()

    return conn, cur
    
#              INICIO                           FUNCIONES CENTRALES DE ESCRITURA 
# =============================================================================================================================================

def _core_guardar_usuario_db(user_id, campos_a_actualizar: dict):
    """
    Función central única para actualizar la tabla 'Usuarios' en Supabase de forma segura.
    Normaliza valores nulos o vacíos antes de enviarlos.
    """
    user_id_str = str(user_id).strip()
    conn = None
    cur = None
    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        
        set_clauses = []
        valores = []
        for col, val in campos_a_actualizar.items():
            # Normalización defensiva de nulos
            if val is None or (isinstance(val, float) and pd.isna(val)):
                val = 0.0 if "cm" in col.lower() else ""
            set_clauses.append(f'"{col}" = %s')
            valores.append(val)
            
        valores.append(user_id_str)
        query = f'UPDATE "Usuarios" SET {", ".join(set_clauses)} WHERE "User ID" = %s'
        
        cur.execute(query, tuple(valores))
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error en la función central _core_guardar_usuario_db para User {user_id}: {e}")
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass

def _core_guardar_perfil_db(user_id, mes, datos_perfil: dict):
    """
    Función central única para insertar o actualizar registros en la tabla Perfil_<user_id>
    con cierre garantizado de conexiones (Context/Finally) y normalización de nulos.
    """
    tabla_nombre = f"Perfil_{user_id}"
    conn = None
    cur = None
    try:
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="perfil")
        cur.execute(f'ALTER TABLE "{tabla_nombre}" ADD COLUMN IF NOT EXISTS "peso_actual" DOUBLE PRECISION;')
        conn.commit()

        cur.execute(f'SELECT id FROM "{tabla_nombre}" WHERE "MES" = %s', (str(mes),))
        fila_existente = cur.fetchone()

        # Normalización defensiva de datos numéricos y strings para evitar NaN/None
        datos_limpios = {}
        for k, v in datos_perfil.items():
            if v is None or (isinstance(v, float) and pd.isna(v)):
                datos_limpios[k] = 0.0 if k in ["PESO", "peso_actual", "ALTURA", "ocupacion"] else ""
            else:
                datos_limpios[k] = v

        if fila_existente:
            set_clauses = []
            valores = []
            for col, val in datos_limpios.items():
                set_clauses.append(f'"{col}" = %s')
                valores.append(val)
            
            valores.append(str(mes))
            query = f'UPDATE "{tabla_nombre}" SET {", ".join(set_clauses)} WHERE "MES" = %s'
            cur.execute(query, tuple(valores))
        else:
            datos_limpios.setdefault("EDAD", "64")
            datos_limpios.setdefault("PESO", 0.0)
            datos_limpios.setdefault("peso_actual", 0.0)
            datos_limpios.setdefault("ALTURA", 170.0)
            datos_limpios.setdefault("GENERO", "M")
            datos_limpios.setdefault("ocupacion", 1.375)
            datos_limpios.setdefault("Fecha_Actualizacion", "")
            datos_limpios.setdefault("Cumple", "")
            
            columnas = list(datos_limpios.keys())
            columnas.append("MES")
            
            placeholders = ["%s"] * len(columnas)
            cols_sql = ', '.join([f'"{c}"' for c in columnas])
            vals_sql = ', '.join(placeholders)
            
            valores = [datos_limpios[k] for k in datos_limpios.keys()]
            valores.append(str(mes))
            
            query = f'INSERT INTO "{tabla_nombre}" ({cols_sql}) VALUES ({vals_sql})'
            cur.execute(query, tuple(valores))

        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error en la función central _core_guardar_perfil_db para Perfil_{user_id}: {e}")
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass
    
#              INICIO                              FUNCIONES USUARIOS                       
# =============================================================================================================================================

def obtener_valores_clinicos_profesional(user_id, mes_str):
    """Consulta la tabla Valores_Clinicos_Profesional en Supabase para un usuario y mes específico."""
    try:
        conn, cur = _asegurar_tabla_y_conectar("Valores_Clinicos_Profesional", tipo_tabla="comidas_precargadas")
        query = """
            SELECT tmb, get, peso_etapa, calorias_min, calorias_max, 
                   proteinas_min, proteinas_max, hidratos_min, hidratos_max, 
                   grasas_min, grasas_max, fibras_min
            FROM "Valores_Clinicos_Profesional"
            WHERE "user_id" = %s AND "mes" = %s
            ORDER BY id DESC LIMIT 1
        """
        cur.execute(query, (str(user_id).strip(), str(mes_str).strip()))
        fila = cur.fetchone()
        cur.close()
        conn.close()

        if fila:
            return {
                "tmb": float(fila[0] or 0),
                "get": float(fila[1] or 0),
                "peso_etapa": float(fila[2] or 0),
                "calorias_min": float(fila[3] or 0),
                "calorias_max": float(fila[4] or 0),
                "proteinas_min": float(fila[5] or 0),
                "proteinas_max": float(fila[6] or 0),
                "hidratos_min": float(fila[7] or 0),
                "hidratos_max": float(fila[8] or 0),
                "grasas_min": float(fila[9] or 0),
                "grasas_max": float(fila[10] or 0),
                "fibras_min": float(fila[11] or 0)
            }
    except Exception as e:
        logger.error(f"Error obteniendo valores clínicos del profesional para {user_id}: {e}")
    
    return None
    
def obtener_datos_usuario(user_id):
    conn = None
    cur = None
    try:
        tabla_nombre = f"User_{user_id}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comida")
        
        query = f"""
            SELECT id, "Fecha", "Momento/Actividad", "Alimento/Detalle", 
                   "Peso (g)", "Calorías (kcal)", "Proteínas (g)", 
                   "Grasas (g)", "Hidratos (g)", "Fibras (g)"
            FROM "{tabla_nombre}"
        """
        df = pd.read_sql(query, conn)
        
        if df.empty:
            return pd.DataFrame()
        
        col_map = {
            'id': 'id_registro',
            'Fecha': 'Fecha',
            'Momento/Actividad': 'Momento',
            'Alimento/Detalle': 'Alimento',
            'Peso (g)': 'Peso',
            'Calorías (kcal)': 'Calorias',
            'Proteínas (g)': 'Proteinas',
            'Grasas (g)': 'Grasas',
            'Hidratos (g)': 'Carbohidratos',
            'Fibras (g)': 'Fibras'
        }
        
        df = df.rename(columns=col_map)
        if "Fecha" in df.columns and not df.empty:
            df['Fecha'] = df['Fecha'].astype(str).str.strip()
            for col in ['Peso', 'Calorias', 'Proteinas', 'Grasas', 'Carbohidratos', 'Fibras']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
                else:
                    df[col] = 0.0
                    
        return df
    except Exception as e:
        print(f"Error al obtener datos de Supabase para el usuario {user_id}: {e}")
        return pd.DataFrame()
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass

def obtener_datos_completos_usuario(user_id, mes_target=None):
    datos_completos = {}
    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        query = """
            SELECT "User ID", "Nombre", "Sexo", "cumple", "profesional", "cintura_cm", 
                   "cuello_cm", "cadera_cm", "ritmo_preferido", "Idioma" 
            FROM "Usuarios"
        """
        cur.execute(query)
        filas = cur.fetchall()
        cur.close()
        conn.close()

        fila_usuario = None
        user_id_str = str(user_id).strip()
        for fila in filas:
            raw_id = fila[0]
            if raw_id and str(raw_id).split('.')[0].strip() == user_id_str:
                fila_usuario = fila
                break

        if fila_usuario:
            datos_completos.update({
                'Nombre': str(fila_usuario[1] or 'S/D'),
                'Sexo': str(fila_usuario[2] or 'S/D'),
                'cumple': str(fila_usuario[3] or 'S/D'),
                'profesional': str(fila_usuario[4] or 'S/D'),
                'cintura_cm': float(fila_usuario[5] or 0.0),
                'cuello_cm': float(fila_usuario[6] or 0.0),
                'cadera_cm': float(fila_usuario[7] or 0.0),
                'ritmo_preferido': str(fila_usuario[8] or '2'),
                'Idioma': str(fila_usuario[9] or 'es')
            })
    except Exception as e:
        logger.error(f"Error obteniendo datos fijos de Usuarios: {e}")

    perfil_mes = obtener_perfil_usuario(user_id, mes_target=mes_target)
    if perfil_mes:
        datos_completos.update(perfil_mes)

    return datos_completos if datos_completos else None
        
def obtener_perfil_usuario(user_id, mes_target=None):
    conn = None
    cur = None
    try:
        tabla_nombre = f"Perfil_{user_id}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="perfil")

        cur.execute(f'ALTER TABLE "{tabla_nombre}" ADD COLUMN IF NOT EXISTS "peso_actual" DOUBLE PRECISION;')
        conn.commit()
        
        query = f"""
            SELECT "EDAD", "PESO", "ALTURA", "GENERO", "ocupacion", "MES", "Fecha_Actualizacion", "peso_actual"
            FROM "{tabla_nombre}"
            ORDER BY id ASC
        """
        cur.execute(query)
        filas = cur.fetchall()
        
        if not filas:
            return None
            
        records = []
        for fila in filas:
            records.append({
                'EDAD': fila[0], 
                'PESO': fila[1], 
                'ALTURA': fila[2],
                'GENERO': fila[3], 
                'ocupacion': fila[4], 
                'MES': fila[5],
                'Fecha_Actualizacion': fila[6],
                'peso_actual_col': fila[7]
            })
            
        ritmo_usr = "moderado"
        try:
            cur.execute('SELECT "ritmo_preferido" FROM "Usuarios" WHERE "User ID" = %s', (str(user_id).strip(),))
            row_u = cur.fetchone()
            if row_u and row_u[0]:
                ritmo_usr = str(row_u[0]).strip()
        except Exception:
            pass

        perfil_raw = None
        if mes_target:
            target_clean = str(mes_target).strip()
            for r in records:
                m_val = str(r.get('MES', '')).strip()
                if m_val.startswith(target_clean):
                    perfil_raw = r
                    break
        
        if not perfil_raw:
            perfil_raw = records[-1]
        
        perfil = {
            'Ritmo': ritmo_usr,
            'ritmo_preferido': ritmo_usr
        }
        peso_hallado = None

        for k, v in perfil_raw.items():
            k_upper = str(k).strip().upper()
            if k_upper == 'EDAD':
                val = float(v or 0)
                perfil['Edad'] = val
                perfil['edad'] = val
            elif k_upper == 'PESO':
                val = float(v or 0)
                if val > 1000: val /= 1000.0
                peso_hallado = val if val > 0 else None
                perfil['Peso'] = val
                perfil['peso'] = val
                perfil['PESO'] = val
                perfil['peso_actual'] = val
            elif k_upper == 'PESO_ACTUAL_COL':
                val = float(v or 0)
                if val > 1000: val /= 1000.0
                perfil['ultimo_peso_informado'] = val if val > 0 else (peso_hallado or 0.0)
            elif k_upper == 'ALTURA':
                val = float(v or 0)
                if val > 1000: val /= 1000.0
                perfil['Altura'] = val
                perfil['altura'] = val
            elif k_upper in ['GENERO', 'SEXO']:
                perfil['Sexo'] = str(v).strip()
                perfil['genero'] = str(v).strip()
            elif k_upper == 'OCUPACION':
                val = float(v or 0)
                if val > 10: val /= 1000.0
                factor_final = val if val > 0 else 1.375
                perfil['Ocupacion'] = factor_final
                perfil['ocupacion'] = factor_final
                perfil['factor_actividad'] = factor_final
            elif k_upper == 'MES':
                perfil['Mes'] = str(v).strip()
                perfil['mes'] = str(v).strip()
            elif k_upper == 'FECHA_ACTUALIZACION':
                perfil['Fecha_Actualizacion'] = str(v or '').strip()

        perfil['peso_pendiente'] = (peso_hallado is None or peso_hallado <= 0)
        return perfil
    except Exception as e:
        print(f"Error obteniendo perfil de Supabase para el usuario {user_id}: {e}")
        return None
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass
                

#              INICIO                             FUNCIONES LECTURA COMIDAS                         
# =============================================================================================================================================

def obtener_comidas_usuario(user_id):
    conn = None
    cur = None
    try:
        tabla_nombre = f"Comidas_{user_id}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comidas_precargadas")
        
        query = f"""
            SELECT "Nombre", "Descripcion", "Peso", "Calorias", "Proteinas", "Grasas", "Carbohidratos", "Fibras"
            FROM "{tabla_nombre}"
        """
        cur.execute(query)
        filas = cur.fetchall()
        
        records = []
        for fila in filas:
            def parse_val(val):
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    return 0.0
                if isinstance(val, (int, float)):
                    return float(val)
                val_str = str(val).strip().replace(',', '.')
                if not val_str:
                    return 0.0
                try:
                    return float(val_str)
                except ValueError:
                    return 0.0

            records.append({
                'Nombre': str(fila[0] or '').strip(), 
                'Descripcion': str(fila[1] or '').strip(),
                'Peso': parse_val(fila[2]), 
                'Calorias': parse_val(fila[3]),
                'Proteinas': parse_val(fila[4]), 
                'Grasas': parse_val(fila[5]), 
                'Carbohidratos': parse_val(fila[6]), 
                'Fibras': parse_val(fila[7])
            })
            
        return records
    except Exception as e:
        print(f"ERROR CRÍTICO en obtener_comidas_usuario para {user_id}: {e}")
        logger.error(f"Error al obtener comidas de Supabase: {e}")
        return []
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass
                                
def eliminar_comida_precargada_db(user_id, nombre_a_borrar):
    """Elimina una comida precargada de la tabla 'Comidas_<user_id>' en Supabase de forma exacta."""
    tabla_nombre = f"Comidas_{user_id}"
    conn = None
    cur = None
    try:
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comidas_precargadas")
        
        query = f'DELETE FROM "{tabla_nombre}" WHERE UPPER(TRIM("Nombre")) = %s'
        cur.execute(query, (nombre_a_borrar.strip().upper(),))
        
        filas_afectadas = cur.rowcount
        conn.commit()
        
        return filas_afectadas > 0
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error al eliminar comida precargada en Supabase para {user_id}: {e}")
        return False 
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass

    
#              INICIO                                   FUNCIONES USUARIOS                        
# =============================================================================================================================================

def _garantizar_fila_mes_actual(user_id: int, ahora_dt) -> bool:
    mes_actual_str = ahora_dt.strftime("%Y-%m")
    tabla_nombre = f"Perfil_{user_id}"

    conn = None
    cur = None
    try:
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="perfil")
        cur.execute(f'ALTER TABLE "{tabla_nombre}" ADD COLUMN IF NOT EXISTS "peso_actual" DOUBLE PRECISION;')
        conn.commit()
        
        # Si la fila ya la generó el día 26 del mes pasado, no hace nada
        cur.execute(f'SELECT id FROM "{tabla_nombre}" WHERE "MES" = %s', (str(mes_actual_str),))
        fila_existente = cur.fetchone()
        if fila_existente:
            return False

        # Si el usuario es nuevo o se saltó el día 26, hereda la última fila
        cur.execute(f'SELECT "EDAD", "PESO", "ALTURA", "GENERO", "ocupacion", "Cumple", "peso_actual" FROM "{tabla_nombre}" ORDER BY id DESC LIMIT 1')
        ultima_fila = cur.fetchone()
        
        if ultima_fila:
            edad_val = str(ultima_fila[0] or "64")
            peso_heredado = float(ultima_fila[6] if ultima_fila[6] and float(ultima_fila[6]) > 0 else (ultima_fila[1] or 70.0))
            if peso_heredado > 1000: peso_heredado /= 1000.0
            altura_val = float(ultima_fila[2] or 170.0)
            genero_val = str(ultima_fila[3] or "M")
            ocupacion_val = float(ultima_fila[4] or 1.375)
            cumple_val = str(ultima_fila[5] or "")
        else:
            edad_val, peso_heredado, altura_val, genero_val, ocupacion_val, cumple_val = "64", 70.0, 170.0, "M", 1.375, ""

        if cur: cur.close()
        if conn: conn.close()

        _core_guardar_perfil_db(user_id, str(mes_actual_str), {
            "EDAD": str(edad_val),
            "PESO": float(peso_heredado),
            "peso_actual": float(peso_heredado),
            "ALTURA": float(altura_val),
            "GENERO": str(genero_val),
            "ocupacion": float(ocupacion_val),
            "Fecha_Actualizacion": "",
            "Cumple": str(cumple_val)
        })

        return True

    except Exception as e:
        logger.error(f"Error al garantizar fila mensual en Supabase para User {user_id}: {e}")
        return False
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass
                            
def obtener_todos_usuarios() -> list:
    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        query = """
            SELECT "User ID", "Nombre", "Estado", "Ultimo Mes Peso", "Notificaciones", 
                   "Fecha Alta", "Sexo", "cumple", "profesional", "reloj_actualizado_mes", 
                   "Idioma", "cintura_cm", "cuello_cm", "ritmo_preferido"
            FROM "Usuarios"
        """
        cur.execute(query)
        filas = cur.fetchall()
        cur.close()
        conn.close()

        records = []
        for fila in filas:
            records.append({
                "User ID": fila[0],
                "Nombre": fila[1],
                "Estado": fila[2],
                "Ultimo Mes Peso": fila[3],
                "Notificaciones": fila[4],
                "Fecha Alta": fila[5],
                "Sexo": fila[6],
                "cumple": fila[7],
                "profesional": fila[8],
                "reloj_actualizado_mes": fila[9],
                "Idioma": fila[10],
                "cintura_cm": fila[11],
                "cuello_cm": fila[12],
                "ritmo_preferido": fila[13]
            })
        return records
    except Exception as e:
        logger.error(f"Error al obtener usuarios de Supabase: {e}")
        return []
        
def obtener_registros_usuario(user_id: str) -> list:
    conn = None
    cur = None
    try:
        tabla_nombre = f"User_{user_id}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comida")
        query = f"""
            SELECT "Fecha", "Momento/Actividad", "Alimento/Detalle", 
                   "Peso (g)", "Calorías (kcal)", "Proteínas (g)", 
                   "Grasas (g)", "Hidratos (g)", "Fibras (g)"
            FROM "{tabla_nombre}"
        """
        cur.execute(query)
        filas = cur.fetchall()

        records = []
        for fila in filas:
            records.append({
                "Fecha": fila[0],
                "Momento/Actividad": fila[1],
                "Alimento/Detalle": fila[2],
                "Peso (g)": fila[3],
                "Calorías (kcal)": fila[4],
                "Proteínas (g)": fila[5],
                "Grasas (g)": fila[6],
                "Hidratos (g)": fila[7],
                "Fibras (g)": fila[8]
            })
        return records
    except Exception as e:
        logger.error(f"Error al obtener registros de usuario en Supabase para {user_id}: {e}")
        return []
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass

def actualizar_estado_usuario(user_id: str, nuevo_estado: str):
    """Actualiza el estado de un usuario delegando en la función central."""
    _core_guardar_usuario_db(user_id, {"Estado": str(nuevo_estado)})

def eliminar_registro_por_id(user_id, item_id):
    """Borra el registro exclusivamente de la tabla en Supabase."""
    conn = None
    cur = None
    try:
        tabla_nombre = f"User_{user_id}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comida")
        cur.execute(f'DELETE FROM "{tabla_nombre}" WHERE id = %s', (int(item_id),))
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error al eliminar registro en Supabase para el usuario {user_id}: {e}")
        return False
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass
    return True


def obtener_datos_usuario_general(user_id):
    """Obtiene los datos generales del usuario desde la tabla 'Usuarios'."""
    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        query = """
            SELECT "User ID", "reloj_actualizado_mes"
            FROM "Usuarios"
        """
        cur.execute(query)
        filas = cur.fetchall()
        cur.close()
        conn.close()

        user_id_str = str(user_id).strip()
        for fila in filas:
            raw_id = fila[0]
            if raw_id and str(raw_id).split('.')[0].strip() == user_id_str:
                return {
                    "user_id": fila[0],
                    "ocupacion": 1.375,
                    "reloj_actualizado_mes": fila[1]
                }
        return {}
    except Exception as e:
        logger.error(f"Error al obtener datos generales de usuario para {user_id}: {e}")
        return {}

#              INICIO                                   FUNCIONES GUARDAR                        
# =============================================================================================================================================

def guardar_ingesta_db(user_id, items, fecha, momento, tipo="Comida"):
    """Guarda los registros de ingesta alimentaria exclusivamente en Supabase."""
    conn = None
    cur = None
    try:
        tabla_nombre = f"User_{user_id}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comida")
        
        for item in items:
            query = f"""
                INSERT INTO "{tabla_nombre}" ("Fecha", "Momento/Actividad", "Alimento/Detalle", "Peso (g)", "Calorías (kcal)", "Proteínas (g)", "Grasas (g)", "Hidratos (g)", "Fibras (g)")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            valores = (
                str(fecha), 
                str(momento), 
                str(item.get("alimento", item.get("Alimento/Detalle", "Desconocido"))), 
                float(item.get("peso", item.get("Peso (g)", 0)) or 0.0), 
                float(item.get("calorias", item.get("Calorías (kcal)", 0)) or 0.0), 
                float(item.get("proteinas", item.get("Proteínas (g)", 0)) or 0.0), 
                float(item.get("grasas", item.get("Grasas (g)", 0)) or 0.0), 
                float(item.get("carbohidratos", item.get("hidratos", item.get("Hidratos (g)", 0))) or 0.0), 
                float(item.get("fibras", item.get("Fibras (g)", 0)) or 0.0)
            )
            cur.execute(query, valores)
            
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error interno al guardar ingesta en Supabase (User_{user_id}): {e}")
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass
            
def guardar_comida_precargada_db(user_id, fila):
    """Guarda en Supabase adaptándose a las mayúsculas/minúsculas de la tabla existente."""
    codigo_original = fila.get('Nombre', fila.get('nombre', ''))
    tabla_nombre = f"Comidas_{user_id}"
    conn = None
    cur = None
    try:
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comidas_precargadas")
        
        # Nombre real de la tabla
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND LOWER(table_name) = LOWER(%s)", (tabla_nombre,))
        row_t = cur.fetchone()
        tabla_real = row_t[0] if row_t else tabla_nombre

        # Nombres reales de columnas
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", (tabla_real,))
        cols_db = {r[0].lower(): r[0] for r in cur.fetchall()}
        
        col_nom = cols_db.get('nombre', cols_db.get('código / nombre', 'Nombre'))
        col_desc = cols_db.get('descripcion', cols_db.get('descripción', cols_db.get('descripcic', 'Descripcion')))
        col_peso = cols_db.get('peso', cols_db.get('peso (g)', 'Peso'))
        col_cal = cols_db.get('calorias', cols_db.get('calorías', 'Calorias'))
        col_prot = cols_db.get('proteinas', cols_db.get('proteínas', 'Proteinas'))
        col_gras = cols_db.get('grasas', 'Grasas')
        col_carb = cols_db.get('carbohidratos', cols_db.get('hidratos', cols_db.get('carbohidr', 'Carbohidratos')))
        col_fibr = cols_db.get('fibras', 'Fibras')

        query_sel = f'SELECT "{col_nom}" FROM "{tabla_real}"'
        cur.execute(query_sel)
        codigos_existentes = set(str(f[0]).strip().upper() for f in cur.fetchall() if f[0] is not None)

        codigo_limpio = str(codigo_original).strip().upper()
        codigo_unico = codigo_limpio
        i = 1
        while codigo_unico in codigos_existentes:
            i += 1
            codigo_unico = f"{codigo_limpio}{i}"

        p_val = float(fila.get('Peso', fila.get('peso', 0)) or 0.0)
        c_val = float(fila.get('Calorias', fila.get('calorias', 0)) or 0.0)
        pr_val = float(fila.get('Proteinas', fila.get('proteinas', 0)) or 0.0)
        g_val = float(fila.get('Grasas', fila.get('grasas', 0)) or 0.0)
        h_val = float(fila.get('Carbohidratos', fila.get('carbohidratos', fila.get('Hidratos', 0))) or 0.0)
        f_val = float(fila.get('Fibras', fila.get('fibras', 0)) or 0.0)

        query = f"""
            INSERT INTO "{tabla_real}" ("{col_nom}", "{col_desc}", "{col_peso}", "{col_cal}", "{col_prot}", "{col_gras}", "{col_carb}", "{col_fibr}")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        # --- AQUÍ QUITAMOS LA DIVISIÓN DESTRUCTORA POR 1000 ---
        valores = (
            str(codigo_unico), 
            str(fila.get('Descripcion', fila.get('descripcion', ''))), 
            p_val, 
            c_val, 
            pr_val, 
            g_val, 
            h_val, 
            f_val
        )
        cur.execute(query, valores)
        conn.commit()
        return codigo_unico
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error al grabar Comida Precargada en Supabase (Comidas_{user_id}): {e}")
        return str(codigo_original)
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass
            
def guardar_presion_db(user_id, alta, baja, pulsaciones=None, nota=""):
    """Guarda los registros de presión arterial exclusivamente en Supabase."""
    ahora = obtener_ahora_arg()
    conn = None
    cur = None

    try:
        tabla_nombre = f"Presion_{user_id}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="presion")

        query = f"""
            INSERT INTO "{tabla_nombre}" ("Fecha_Hora", "Fecha_Dia", "Alta", "Baja", "Pulsaciones", "Nota")
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        valores = (
            ahora.strftime("%Y-%m-%d"), 
            ahora.strftime("%Y-%m-%d"), 
            float(alta or 0.0), 
            float(baja or 0.0), 
            float(pulsaciones) if pulsaciones is not None else 0.0, 
            str(nota or "").strip()
        )
        cur.execute(query, valores)
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error al grabar Presión en Supabase (Presion_{user_id}): {e}")
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass

def guardar_perfil_db(user_id, peso, mes=None, edad=None, altura=None, genero=None, ocupacion=None, *args, **kwargs):
    ahora = obtener_ahora_arg()
    dia_actual = ahora.day
    mes_actual_str = ahora.strftime("%Y-%m")
    if not mes:
        mes = mes_actual_str

    peso_ingresado = float(peso or 0.0)
    if peso_ingresado > 1000:
        peso_ingresado /= 1000.0

    # --- Obtener idioma del usuario para las respuestas multilenguaje ---
    lang_usuario = 'es'
    try:
        conn_l, cur_l = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        cur_l.execute('SELECT "Idioma" FROM "Usuarios" WHERE "User ID" = %s', (str(user_id).strip(),))
        row_l = cur_l.fetchone()
        if row_l and row_l[0]:
            lang_usuario = str(row_l[0]).strip().lower()
        cur_l.close()
        conn_l.close()
    except Exception:
        pass

    # Obtener traducciones de la tabla 'multi' de forma segura
    traducciones_msj = {}
    try:
        conn_m, cur_m = _asegurar_tabla_y_conectar("multi", tipo_tabla="comidas_precargadas")
        cur_m.execute('SELECT variables, "{0}" FROM "multi"'.format(lang_usuario.upper()))
        filas_m = cur_m.fetchall()
        traducciones_msj = {row[0].strip().lower(): row[1] for row in filas_m if row[0] and row[1]}
        cur_m.close()
        conn_m.close()
    except Exception:
        pass

    def msg_t(clave, fallback):
        return traducciones_msj.get(clave.lower(), fallback)

    conn = None
    cur = None
    try:
        tabla_nombre = f"Perfil_{user_id}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="perfil")
        cur.execute(f'ALTER TABLE "{tabla_nombre}" ADD COLUMN IF NOT EXISTS "peso_actual" DOUBLE PRECISION;')
        conn.commit()

        cur.execute(f'SELECT "EDAD", "ALTURA", "GENERO", "ocupacion", "PESO", "peso_actual", "Fecha_Actualizacion" FROM "{tabla_nombre}" WHERE "MES" = %s', (str(mes),))
        fila_previa = cur.fetchone()
        
        fecha_act_ant = str(fila_previa[6] or "").strip() if fila_previa else ""
        dia_ultima_act = 0
        if fecha_act_ant:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
                try:
                    dia_ultima_act = datetime.strptime(fecha_act_ant, fmt).day
                    break
                except ValueError:
                    continue
                    
    except Exception as e:
        logger.error(f"Error preliminar en guardar_perfil_db para {user_id}: {e}")
        return {"error": True, "mensaje": msg_t("03_bot_err_db", "❌ Error al consultar la base de datos.")}
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass

    edad_val = int(float(edad)) if edad is not None else (int(float(fila_previa[0])) if fila_previa and fila_previa[0] else 64)
    altura_val = float(altura) if altura is not None else (float(fila_previa[1]) if fila_previa and fila_previa[1] else 170.0)
    if altura_val > 1000: altura_val /= 1000.0
    genero_val = str(genero) if genero else (str(fila_previa[2]) if fila_previa and fila_previa[2] else "M")
    
    factor_previo = float(ocupacion) if ocupacion is not None else (float(fila_previa[3]) if fila_previa and fila_previa[3] else 1.375)
    if factor_previo > 10: factor_previo /= 1000.0

    peso_base_mes = float(fila_previa[4]) if fila_previa and fila_previa[4] else 0.0
    if peso_base_mes > 1000: peso_base_mes /= 1000.0

    # --- Función interna para recalcular factor ---
    def recalcular_factor_diluido(peso_base, peso_nuevo_ingreso):
        try:
            df_datos = obtener_datos_usuario(user_id) 
            if df_datos.empty or 'Fecha' not in df_datos.columns:
                return factor_previo
                
            df_mes = df_datos[df_datos['Fecha'].astype(str).str.startswith(str(mes))].copy()
            if df_mes.empty:
                return factor_previo
                
            dias_registrados = df_mes['Fecha'].nunique()
            if dias_registrados < 1:
                return factor_previo

            delta_peso = peso_nuevo_ingreso - peso_base
            tot_cons_mes = float(df_mes[df_mes['Calorias'] > 0]['Calorias'].sum()) if 'Calorias' in df_mes.columns else 0.0
            tot_quem_mes = float(abs(df_mes[df_mes['Calorias'] < 0]['Calorias'].sum())) if 'Calorias' in df_mes.columns else 0.0

            prom_cons = tot_cons_mes / dias_registrados
            prom_quem = tot_quem_mes / dias_registrados

            tmb_pura, _ = calcular_tmb_y_get(peso_actual=peso_base, altura_cm=altura_val, edad=edad_val, genero=genero_val, actividad=1.0)
            if tmb_pura <= 0: tmb_pura = 1813.0

            balance_diario_objetivo = (delta_peso * 7700.0) / dias_registrados
            get_real_necesario = prom_cons - prom_quem - balance_diario_objetivo
            
            factor_calculado = get_real_necesario / tmb_pura
            factor_calculado_acotado = max(0.50, min(5.00, factor_calculado))

            d_trans = min(30, max(1, dia_actual))
            peso_nw = d_trans
            peso_prv = 30 - d_trans
            
            factor_ponderado = ((factor_calculado_acotado * peso_nw) + (factor_previo * peso_prv)) / 30.0
            return round(factor_ponderado, 6)
        except Exception as err:
            logger.error(f"Error recalculando factor: {err}")
            return factor_previo

    # --- REGLA DE LAS 3 VENTANAS ---
    if dia_actual <= 14:
        if peso_base_mes > 0:
            msg_default = "⚖️ Ya tenemos registrado tu peso base del mes. Para que la tendencia sea real y no refleje retención de líquidos, podrás ingresar tu próximo control a partir del día 15."
            return {"error": True, "mensaje": msg_t("03_peso_ya_registrado", msg_default)}
        
        _core_guardar_perfil_db(user_id, str(mes), {
            "EDAD": str(edad_val), "PESO": peso_ingresado, "peso_actual": peso_ingresado, 
            "ALTURA": altura_val, "GENERO": genero_val, "ocupacion": factor_previo, 
            "Fecha_Actualizacion": ahora.strftime("%Y-%m-%d")
        })
        _core_guardar_usuario_db(user_id, {"Ultimo Mes Peso": ahora.strftime("%Y-%m-%d")})
        
        msg_default = f"✅ **¡Peso base del mes registrado correctamente!**\n\n• Peso inicial ({mes}): `{peso_ingresado:.1f} kg`"
        template = msg_t("03_peso_base_ok", msg_default)
        return {"error": False, "mensaje": template.format(mes=mes, peso=f"{peso_ingresado:.1f}")}

    elif 15 <= dia_actual <= 25:
        if dia_ultima_act >= 15:
            msg_default = "⚖️ Control quincenal ya registrado correctamente. Tu próximo ingreso estará habilitado a partir del día 26 para el cierre del mes."
            return {"error": True, "mensaje": msg_t("03_control_quincenal_hecho", msg_default)}
        
        nuevo_factor = recalcular_factor_diluido(peso_base_mes, peso_ingresado)
        delta_peso = peso_ingresado - peso_base_mes
        
        _core_guardar_perfil_db(user_id, str(mes), {
            "peso_actual": peso_ingresado, "ocupacion": nuevo_factor, "Fecha_Actualizacion": ahora.strftime("%Y-%m-%d")
        })
        guardar_ocupacion_db(user_id, nuevo_factor, str(mes))
        
        msg_default = f"✅ **¡Control quincenal guardado y factor calibrado!**\n\n• Variación detectada: `{delta_peso:+.1f} kg`\n• Nuevo factor de actividad: `{nuevo_factor:.4f}`"
        template = msg_t("03_control_quincenal_ok", msg_default)
        return {"error": False, "mensaje": template.format(variacion=f"{delta_peso:+.1f}", factor=f"{nuevo_factor:.4f}")}

    else: # dia_actual >= 26
        if dia_ultima_act >= 26:
            msg_default = "⚖️ Ya registraste tu peso de cierre de mes. El sistema ya preparó tu ficha para el mes que viene. Tu próximo pesaje se habilitará el día 15."
            return {"error": True, "mensaje": msg_t("03_cierre_mes_hecho", msg_default)}
        
        nuevo_factor = recalcular_factor_diluido(peso_base_mes, peso_ingresado)
        
        # 1. Actualiza mes actual con el balance final
        _core_guardar_perfil_db(user_id, str(mes), {
            "peso_actual": peso_ingresado, "ocupacion": nuevo_factor, "Fecha_Actualizacion": ahora.strftime("%Y-%m-%d")
        })
        guardar_ocupacion_db(user_id, nuevo_factor, str(mes))
        
        # 2. Crea/Pre-carga silenciosamente el mes siguiente
        mes_proximo_dt = ahora.replace(day=28) + timedelta(days=5)
        mes_proximo_str = mes_proximo_dt.strftime("%Y-%m")
        _core_guardar_perfil_db(user_id, mes_proximo_str, {
            "EDAD": str(edad_val), "PESO": peso_ingresado, "peso_actual": peso_ingresado, 
            "ALTURA": altura_val, "GENERO": genero_val, "ocupacion": nuevo_factor, 
            "Fecha_Actualizacion": ahora.strftime("%Y-%m-%d")
        })
        
        _core_guardar_usuario_db(user_id, {"Ultimo Mes Peso": ahora.strftime("%Y-%m-%d")})
        
        msg_default = f"✅ **¡Cierre de mes registrado impecable!**\n\nEl balance del período se ha consolidado y ya configuramos automáticamente tu perfil base para el inicio del próximo mes con `{peso_ingresado:.1f} kg`."
        template = msg_t("03_cierre_mes_ok", msg_default)
        return {"error": False, "mensaje": template.format(peso=f"{peso_ingresado:.1f}")}
                                                         
def guardar_ocupacion_db(user_id, nuevo_factor, mes_actual, reloj_actualizado=None):
    """Actualiza el factor de ocupación en la tabla Perfil_<user_id> y el control en Usuarios."""
    user_id_str = str(user_id).strip()
    mes_marca = str(reloj_actualizado) if reloj_actualizado else str(mes_actual)

    _core_guardar_usuario_db(user_id_str, {
        "ocupacion": float(nuevo_factor or 1.375),
        "reloj_actualizado_mes": mes_marca
    })

    _core_guardar_perfil_db(user_id, str(mes_actual), {
        "ocupacion": float(nuevo_factor or 1.375)
    })

# =============================================================================================================================================
#              FINAL                                   FUNCIONES SUPABASE                           FINAL
# =============================================================================================================================================

# =============================================================================================================================================
#              INICIO                         FUNCIONES AUXILIARES INTERNAS                  INICIO
# =============================================================================================================================================
#              INICIO                             FUNCIONES DE PARSING Y FECHAS                  INICIO
# =============================================================================================================================================

async def animar_carga(msg_obj, traducciones=None):
    if traducciones is None: traducciones = {}
    textos = [
        traducciones.get("03_anim_1", "🔍 Identificando ingredientes y porciones en la imagen..."),
        traducciones.get("03_anim_2", "⚖️ Separando proteínas, carbohidratos y grasas..."),
        traducciones.get("03_anim_3", "🧮 Ajustando cálculos matemáticos de calorías..."),
        traducciones.get("03_anim_4", "⚙️ Generando el informe nutricional..."),
        traducciones.get("03_anim_5", "📝 Ya casi lo tenemos...")
    ]
    i = 0
    try:
        while True:
            # Espera 8 segundos entre cada mensaje
            await asyncio.sleep(6)
            try:
                await msg_obj.edit_text(textos[i])
            except Exception:
                pass # Si Telegram chilla por la red, pasa al siguiente
            # Avanza al siguiente texto (y vuelve a empezar si se acaban)
            i = (i + 1) % len(textos)
    except asyncio.CancelledError:
        # Esto se ejecuta silenciosamente cuando frenamos la animación
        pass

def es_administrador(user_id) -> bool:
    """Verifica si el ID de usuario corresponde al administrador."""
    if not ADMIN_USER_ID:
        return False
    return str(user_id).strip() == str(ADMIN_USER_ID).strip()

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

def obtener_ahora_arg():
    return datetime.now(pytz.timezone('America/Argentina/Buenos_Aires'))
    
def obtener_momento_y_fecha_auto():
    ahora = obtener_ahora_arg()
    hora = ahora.time()
    fecha_obj = ahora.date()
    
    if time(0, 0) <= hora < time(4, 0):
        fecha_obj = fecha_obj - timedelta(days=1)
        momento = "Cena"
    elif time(4, 0) <= hora < time(11, 0):
        momento = "Desayuno"
    elif time(11, 0) <= hora < time(16, 0):
        momento = "Almuerzo"
    elif time(16, 0) <= hora < time(20, 0):
        momento = "Merienda"
    else:
        momento = "Cena"        
    return fecha_obj.strftime("%Y-%m-%d"), momento

#              INICIO                     FUNCIONES BIOMETRICAS Y METRICAS                   INICIO
# =============================================================================================================================================

def calcular_metricas_mensuales(df_mes, perfil_dict, user_id=None, mes_str=None):
    if df_mes is not None and not df_mes.empty and 'Fecha' in df_mes.columns:
        todas_comidas = {"Desayuno", "Almuerzo", "Merienda", "Cena"}
        comidas_principales = {"Almuerzo", "Cena"}
        dias_validos_filtrados = []
        
        for fecha, grupo in df_mes.groupby('Fecha'):
            comidas_del_dia = [
                str(r.get("Momento/Actividad") or r.get("Momento", "")).capitalize() 
                for _, r in grupo.iterrows()
                if str(r.get("Momento/Actividad") or r.get("Momento", "")).capitalize() in todas_comidas
            ]
            
            total_comidas = len(comidas_del_dia)
            tiene_principal = any(c in comidas_principales for c in comidas_del_dia)
            
            if total_comidas >= 2 and tiene_principal:
                dias_validos_filtrados.append(fecha)
                
        df_mes = df_mes[df_mes['Fecha'].isin(dias_validos_filtrados)]

    dias_registrados = df_mes['Fecha'].nunique() if (df_mes is not None and not df_mes.empty) else 1
    if dias_registrados == 0:
        dias_registrados = 1

    tot_cons_mes = float(df_mes[df_mes['Calorias'] > 0]['Calorias'].sum()) if df_mes is not None and 'Calorias' in df_mes.columns else 0.0
    tot_quem_mes = float(abs(df_mes[df_mes['Calorias'] < 0]['Calorias'].sum())) if df_mes is not None and 'Calorias' in df_mes.columns else 0.0

    minutos_totales_actividad = 0
    if df_mes is not None and not df_mes.empty and 'Momento' in df_mes.columns and 'Alimento' in df_mes.columns:
        for _, row in df_mes.iterrows():
            momento_str = str(row.get('Momento', '')).strip().lower()
            alimento_str = str(row.get('Alimento', '')).strip()
            cal_val = float(row.get('Calorias', 0) or 0)
            if cal_val < 0 or 'actividad' in momento_str or 'ejercicio' in momento_str or 'caminata' in momento_str:
                match = re.match(r'^(\d+)', alimento_str)
                if match:
                    minutos_totales_actividad += int(match.group(1))

    prom_minutos_act = int(round(minutos_totales_actividad / dias_registrados))

    prom_cons = tot_cons_mes / dias_registrados
    prom_quem = tot_quem_mes / dias_registrados
    prom_bal_neto = prom_cons - prom_quem

    tot_prot = float(df_mes['Proteinas'].sum()) if df_mes is not None and 'Proteinas' in df_mes.columns else 0.0
    tot_gras = float(df_mes['Grasas'].sum()) if df_mes is not None and 'Grasas' in df_mes.columns else 0.0
    tot_carb = float(df_mes['Carbohidratos'].sum()) if df_mes is not None and 'Carbohidratos' in df_mes.columns else 0.0
    tot_fibr = float(df_mes['Fibras'].sum()) if df_mes is not None and 'Fibras' in df_mes.columns else 0.0

    prom_cal = int(round(prom_cons))
    prom_prot = int(round(tot_prot / dias_registrados))
    prom_gras = int(round(tot_gras / dias_registrados))
    prom_carb = int(round(tot_carb / dias_registrados))
    prom_fibr = int(round(tot_fibr / dias_registrados))

    perfil_dict = perfil_dict if isinstance(perfil_dict, dict) else {}
    
    def get_perfil_num(key_list, default):
        for k in key_list:
            if k in perfil_dict and perfil_dict[k] is not None:
                val = parse_raw_val(perfil_dict[k])
                if val != 0.0:
                    return val
        return default

    edad = int(get_perfil_num(['Edad', 'edad', 'EDAD'], 64))
    altura = get_perfil_num(['Altura', 'altura', 'ALTURA'], 167.5)
    peso_actual = get_perfil_num(['PESO', 'Peso', 'peso', 'peso_actual'], 104.6)
    
    ocupacion = perfil_dict.get('Ocupacion') or perfil_dict.get('ocupacion') or perfil_dict.get('actividad', 1.375)
    genero = str(perfil_dict.get('GENERO') or perfil_dict.get('Genero') or perfil_dict.get('Sexo') or perfil_dict.get('genero', 'masculino')).strip()
    gen_clean = genero.lower()
    is_femenino = gen_clean in ["femenino", "f", "mujer", "female"]
    ritmo_usuario = str(perfil_dict.get('Ritmo') or perfil_dict.get('ritmo_preferido', 'moderado')).strip()

    # 1. Calculamos Peso Ideal y Peso de Etapa (promedio ponderado entre actual e ideal)
    peso_ideal_secreto = calcular_peso_ideal(genero, altura, edad=edad)
    peso_etapa_calculado = calcular_peso_etapa(peso_actual, peso_ideal_secreto, ritmo_usuario)
    
    peso_referencia = round(peso_etapa_calculado, 1)
    peso_ideal_dinamico = peso_referencia  
    
    # 2. Calculamos el GET del peso actual (para el balance real de variación de peso)
    #    y el GET correspondiente al peso de etapa
    _, get_real = calcular_tmb_y_get(
        peso_actual=peso_actual, altura_cm=altura, edad=edad, genero=genero, actividad=ocupacion, peso_ideal=peso_ideal_dinamico
    )
    _, get_meta = calcular_tmb_y_get(
        peso_actual=peso_referencia, altura_cm=altura, edad=edad, genero=genero, actividad=ocupacion, peso_ideal=peso_ideal_dinamico
    )

    balance_diario = prom_cons - (get_real + prom_quem)
    cambio_peso_kg = (balance_diario * dias_registrados) / 7700.0

    if is_femenino:
        factor_proteina_min = 1.0
        factor_proteina_max = 1.2
        fibr_min = 25
    else:
        factor_proteina_min = 1.2
        factor_proteina_max = 1.5
        fibr_min = 30

    # 3. Definición del Rango Calórico Saludable basado en el Peso de Etapa:
    #    Si el peso_referencia (etapa) es menor al peso_actual, proyectamos las calorías
    #    en proporción directa al peso de etapa para garantizar el descenso hacia esa meta.
    if peso_actual > 0 and peso_referencia < peso_actual:
        cal_etapa_objetivo = get_real * (peso_referencia / peso_actual)
        cal_min = int(round(min(cal_etapa_objetivo, get_meta) - 50))
        cal_max = int(round(max(cal_etapa_objetivo, get_meta) + 50))
        # Si la diferencia entre cal_min y cal_max quedó muy estrecha, aseguramos al menos 150 kcal de banda
        if (cal_max - cal_min) < 150:
            centro = int(round(cal_etapa_objetivo))
            cal_min = centro - 100
            cal_max = centro + 50
    else:
        # Si ya está en su peso ideal (peso_actual == peso_referencia), damos margen de mantenimiento (+/- 100 kcal)
        val_get_meta = int(round(get_meta))
        cal_min = val_get_meta - 100
        cal_max = val_get_meta + 100

    # 4. Macronutrientes calculados directamente sobre el peso de etapa y su rango calórico
    prot_min = int(round(float(peso_referencia) * factor_proteina_min))
    prot_max = int(round(float(peso_referencia) * factor_proteina_max))

    gras_min = int(round((cal_min * 0.20) / 9.0))
    gras_max = int(round((cal_max * 0.30) / 9.0))

    carb_min = int(round((cal_min * 0.40) / 4.0))
    carb_max = int(round((cal_max * 0.55) / 4.0))

    # --- SUPREMACÍA CLÍNICA: VERIFICAR SI TIENE VALORES DEL PROFESIONAL ---
    valores_personalizados = False
    if user_id and mes_str:
        valores_prof = obtener_valores_clinicos_profesional(user_id, mes_str)
        if valores_prof:
            valores_personalizados = True
            cal_min = int(valores_prof.get("calorias_min", cal_min))
            cal_max = int(valores_prof.get("calorias_max", cal_max))
            prot_min = int(valores_prof.get("proteinas_min", prot_min))
            prot_max = int(valores_prof.get("proteinas_max", prot_max))
            carb_min = int(valores_prof.get("hidratos_min", carb_min))
            carb_max = int(valores_prof.get("hidratos_max", carb_max))
            gras_min = int(valores_prof.get("grasas_min", gras_min))
            gras_max = int(valores_prof.get("grasas_max", gras_max))
            fibr_min = int(valores_prof.get("fibras_min", fibr_min))
            if valores_prof.get("peso_etapa", 0) > 0:
                peso_referencia = float(valores_prof.get("peso_etapa"))

    return {
        "dias_registrados": dias_registrados,
        "prom_cal": prom_cal,
        "prom_quem": int(round(prom_quem)),
        "prom_bal_neto": int(round(prom_bal_neto)),
        "prom_prot": prom_prot,
        "prom_gras": prom_gras,
        "prom_carb": prom_carb,
        "prom_fibr": prom_fibr,
        "prom_minutos_act": prom_minutos_act,
        "cal_min": cal_min, "cal_max": cal_max,
        "prot_min": prot_min, "prot_max": prot_max,
        "gras_min": gras_min, "gras_max": gras_max,
        "carb_min": carb_min, "carb_max": carb_max,
        "fibr_min": fibr_min,
        "peso_actual": round(float(peso_actual), 1),
        "peso_referencia": round(float(peso_referencia), 1),
        "cambio_peso_kg": cambio_peso_kg,
        "valores_personalizados": valores_personalizados
    }
     
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

def calcular_rango_actividad_fisica(peso_actual: float, peso_referencia: float) -> tuple[int, int]:
    min_minutos = 30  
    if peso_referencia <= 0:
        return min_minutos, 60

    exceso_pct = max(0.0, (peso_actual - peso_referencia) / peso_referencia)

    if exceso_pct >= 0.20:
        max_minutos = 60
    elif exceso_pct <= 0.0:
        max_minutos = 90
    else:
        max_minutos = int(90 - (exceso_pct / 0.20) * 30)
        max_minutos = max(60, min(90, max_minutos))

    return min_minutos, max_minutos

def calcular_edad_desde_cumple(cumple_str: str) -> int:
    try:
        nacimiento = datetime.strptime(cumple_str, "%Y-%m-%d")
        ahora = obtener_ahora_arg()
        edad = ahora.year - nacimiento.year - ((ahora.month, ahora.day) < (nacimiento.month, nacimiento.day))
        return max(10, edad)
    except Exception:
        return 64

def aplicar_calibracion_reloj(factor_previo: float, get_reloj: float, tmb: float, max_variacion_pct: float = 0.10) -> float:
    if tmb <= 0 or get_reloj <= 0:
        return factor_previo if factor_previo and factor_previo > 0 else 1.375

    factor_crudo = get_reloj / tmb
    factor_crudo = max(1.1, min(2.0, factor_crudo))

    if factor_previo and factor_previo > 0:
        limite_inferior = factor_previo * (1.0 - max_variacion_pct)
        limite_superior = factor_previo * (1.0 + max_variacion_pct)
        factor_final = max(limite_inferior, min(limite_superior, factor_crudo))
    else:
        factor_final = factor_crudo

    return round(factor_final, 4)
        
def _obtener_biometria_encapsulada(sexo_arg=None, altura_arg=None, peso_arg=None, edad_arg=None):
    datos = {
        "sexo": str(sexo_arg or "M").strip(),
        "altura": float(altura_arg or 1.0),
        "peso": float(peso_arg or 1.0),
        "edad": int(float(edad_arg or 1)),
        "cintura": 1.0,
        "cuello": 1.0,
        "cadera": 0.0
    }
    if datos["altura"] > 1000:
        datos["altura"] /= 1000.0
    if datos["peso"] > 1000:
        datos["peso"] /= 1000.0

    uid = None
    try:
        frame = inspect.currentframe()
        while frame:
            locs = frame.f_locals
            for clave in ('user_id', 'uid', 'u_id', 'target_user_id'):
                if clave in locs and locs[clave] is not None:
                    val_id = str(locs[clave]).split('.')[0].strip()
                    if val_id.isdigit():
                        uid = val_id
                        break
            if uid:
                break
            frame = frame.f_back
    except Exception:
        uid = None
    finally:
        del frame

    if not uid:
        return datos

    try:
        conn = _obtener_conexion_db()
        cur = conn.cursor()

        cur.execute(
            'SELECT "cintura_cm", "cuello_cm", "cadera_cm", "Sexo", "cumple" FROM "Usuarios" WHERE "User ID" = %s LIMIT 1',
            (str(uid),)
        )
        fila_u = cur.fetchone()
        if fila_u:
            if fila_u[0] is not None:
                datos["cintura"] = float(fila_u[0] or 1.0)
            if fila_u[1] is not None:
                datos["cuello"] = float(fila_u[1] or 1.0)
            if fila_u[2] is not None:
                datos["cadera"] = float(fila_u[2] or 0.0)
            if not sexo_arg and fila_u[3]:
                datos["sexo"] = str(fila_u[3]).strip()
            if not edad_arg and fila_u[4] and 'calcular_edad_desde_cumple' in globals():
                datos["edad"] = calcular_edad_desde_cumple(str(fila_u[4]).strip())

        if datos["peso"] <= 1.0 or datos["altura"] <= 1.0 or datos["edad"] <= 1:
            tabla_perfil = f"Perfil_{uid}"
            cur.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND LOWER(table_name) = LOWER(%s)
            """, (tabla_perfil,))
            t_row = cur.fetchone()
            if t_row:
                cur.execute(f'SELECT "EDAD", "PESO", "ALTURA", "GENERO" FROM "{t_row[0]}" ORDER BY id DESC LIMIT 1')
                fila_p = cur.fetchone()
                if fila_p:
                    if (not edad_arg or datos["edad"] <= 1) and fila_p[0]:
                        datos["edad"] = int(float(fila_p[0]))
                    if (not peso_arg or datos["peso"] <= 1.0) and fila_p[1]:
                        p_db = float(fila_p[1])
                        datos["peso"] = p_db / 1000.0 if p_db > 1000 else p_db
                    if (not altura_arg or datos["altura"] <= 1.0) and fila_p[2]:
                        a_db = float(fila_p[2])
                        datos["altura"] = a_db / 1000.0 if a_db > 1000 else a_db
                    if not sexo_arg and fila_p[3]:
                        datos["sexo"] = str(fila_p[3]).strip()

        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error en _obtener_biometria_encapsulada para {uid}: {e}")

    return datos

# 6. ESTIMACIÓN DE GRASA Y MASA MAGRA (MARINA EE.UU. EXCLUSIVA ADULTOS)
def calcular_grasa_y_magra(sexo: str, altura_cm: float, cintura_cm: float, cuello_cm: float, peso_actual: float, cadera_cm: float = None, edad: int = 30) -> tuple[Optional[float], Optional[float]]:
    if edad is not None and edad < 18:
        return None, None

    gen_clean = str(sexo).strip().lower()
    is_femenino = gen_clean in ["femenino", "f", "mujer", "female", "chica", "niña"]
    
    try:
        alt = max(50.0, float(altura_cm))
        cint = float(cintura_cm)
        cuell = float(cuello_cm)

        if is_femenino:
            if cadera_cm is None or float(cadera_cm) <= 1.0:
                return None, None
            cad = float(cadera_cm)
            diff = cint + cad - cuell
            if diff <= 1.0:
                return None, None
            densidad = 1.29579 - (0.35004 * math.log10(diff)) + (0.22100 * math.log10(alt))
            gc = (495.0 / densidad) - 450.0
        else:
            diff = cint - cuell
            if diff <= 1.0:
                return None, None
            densidad = 1.0324 - (0.19077 * math.log10(diff)) + (0.15456 * math.log10(alt))
            gc = (495.0 / densidad) - 450.0
            
        gc = max(4.0, min(65.0, gc))
        masa_grasa = float(peso_actual) * (gc / 100.0)
        masa_magra = float(peso_actual) - masa_grasa
        return round(gc, 1), round(masa_magra, 1)

    except Exception as e:
        logger.error(f"Error en calcular_grasa_y_magra: {e}")
        return None, None

# 7. PESO IDEAL (OMS PEDIÁTRICO, IMC 22 PARA < 1.50 M Y LORENTZ/MAGRA ADULTOS)
def calcular_peso_ideal(sexo: str, altura_cm: float, edad: int = None) -> float:
    bio = _obtener_biometria_encapsulada(sexo_arg=sexo, altura_arg=altura_cm, edad_arg=edad)
    gen_clean = str(bio["sexo"]).strip().lower()
    is_femenino = gen_clean in ["femenino", "f", "mujer", "female", "chica", "niña"]
    alt = bio["altura"]
    anios = int(bio.get("edad", 30))
    alt_m = alt / 100.0

    # 1. Pediátrico (< 18 años): Tablas OMS Mediana (P50)
    if anios < 18:
        imc_p50 = 15.5 + max(0, anios - 3) * (5.5 / 14.0) if not is_femenino else 15.3 + max(0, anios - 3) * (5.7 / 14.0)
        peso_pediatrico = imc_p50 * (alt_m ** 2)
        return round(max(12.0, peso_pediatrico), 1)

    # 2. Adultos < 1.50 m: IMC 22 objetivo (anula el fallo de Lorentz)
    if alt < 150.0:
        peso_base = 22.0 * (alt_m ** 2)
        return round(max(35.0, peso_base), 1)

    # 3. Adultos >= 1.50 m: Lorentz de respaldo + Composición corporal si hay medidas
    if not is_femenino:
        peso_lorentz = (alt - 100.0) - ((alt - 150.0) / 4.0)
    else:
        peso_lorentz = (alt - 100.0) - ((alt - 150.0) / 2.5)

    cintura = bio["cintura"]
    cuello = bio["cuello"]
    cadera = bio.get("cadera", 0.0)
    peso_act = bio["peso"]

    if cintura > 1.0 and cuello > 1.0 and peso_act > 1.0:
        if is_femenino and cadera > 1.0:
            _, masa_magra = calcular_grasa_y_magra(bio["sexo"], alt, cintura, cuello, peso_act, cadera_cm=cadera, edad=anios)
        elif not is_femenino and cintura > cuello:
            _, masa_magra = calcular_grasa_y_magra(bio["sexo"], alt, cintura, cuello, peso_act, edad=anios)
        else:
            masa_magra = None

        if masa_magra is not None and masa_magra > 1.0:
            tramo_edad = max(0.0, (anios - 30.0) * 0.12)
            grasa_objetivo_pct = (24.0 + tramo_edad) if is_femenino else (16.0 + tramo_edad)
            grasa_objetivo_pct = min(33.0 if is_femenino else 25.0, grasa_objetivo_pct)

            peso_por_composicion = masa_magra / (1.0 - (grasa_objetivo_pct / 100.0))
            peso_final = (peso_por_composicion * 0.65) + (peso_lorentz * 0.35)
            return round(max(40.0, peso_final), 1)

    return round(max(40.0, peso_lorentz), 1)

def obtener_datos_presion_db(user_id):
    conn = None
    cur = None
    try:
        tabla_nombre = f"Presion_{user_id}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="presion")
        
        query = f"""
            SELECT "Fecha_Hora", "Fecha_Dia", "Alta", "Baja", "Pulsaciones", "Nota"
            FROM "{tabla_nombre}"
        """
        df = pd.read_sql(query, conn)
        
        if df.empty:
            return pd.DataFrame()

        for col in ['Alta', 'Baja', 'Pulsaciones']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        if 'Fecha_Dia' in df.columns:
            df['Fecha_Dia'] = df['Fecha_Dia'].astype(str).str.strip()

        if 'Nota' not in df.columns:
            df['Nota'] = ""

        return df
    except Exception as e:
        logger.error(f"Error al obtener datos de presión de Supabase: {e}")
        return pd.DataFrame()
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass
        
def obtener_ultimo_peso(user_id: int) -> dict:
    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        query = """
            SELECT "User ID", "Ultimo Mes Peso", "Notificaciones"
            FROM "Usuarios"
        """
        cur.execute(query)
        filas = cur.fetchall()
        cur.close()
        conn.close()

        for fila in filas:
            raw_id = fila[0]
            if raw_id and str(raw_id).split('.')[0].strip() == str(user_id).strip():
                fecha_peso = fila[1]
                if fecha_peso:
                    return {"fecha": str(fecha_peso).strip()}
                    
        return None
    except Exception as e:
        logger.error(f"Error en obtener_ultimo_peso para User {user_id}: {e}")
        return None
          
def _calcular_y_actualizar_factor_mes_anterior(user_id, mes_anterior_str, peso_fin_mes_override=None):
    try:
        df_datos = obtener_datos_usuario(user_id) 
        if df_datos.empty or 'Fecha' not in df_datos.columns:
            return None

        df_mes = df_datos[df_datos['Fecha'].astype(str).str.startswith(mes_anterior_str)].copy()
        if df_mes.empty:
            return None

        dias_registrados = df_mes['Fecha'].nunique()
        if dias_registrados == 0:
            dias_registrados = 1

        tot_cons_mes = float(df_mes[df_mes['Calorias'] > 0]['Calorias'].sum()) if 'Calorias' in df_mes.columns else 0.0
        tot_quem_mes = float(abs(df_mes[df_mes['Calorias'] < 0]['Calorias'].sum())) if 'Calorias' in df_mes.columns else 0.0

        ingesta_diaria = tot_cons_mes / dias_registrados
        ejercicio_diario = tot_quem_mes / dias_registrados

        perfil = obtener_perfil_usuario(user_id, mes_target=mes_anterior_str) or {}
        
        peso_actual = float(perfil.get('Peso', perfil.get('peso', 108.5)))
        if peso_actual > 1000: peso_actual /= 1000.0
        
        altura = float(perfil.get('Altura', perfil.get('altura', 1.72)))
        if altura > 1000: altura /= 1000.0
        
        edad = int(perfil.get('Edad', perfil.get('edad', 64)))
        genero = str(perfil.get('GENERO', perfil.get('genero', 'M'))).strip()

        tmb_pura, _ = calcular_tmb_y_get(
            peso_actual=peso_actual, altura_cm=altura, edad=edad, genero=genero, actividad=1.0
        )
        if tmb_pura <= 0:
            tmb_pura = 1813.0

        delta_peso = 0.0
        tabla_nombre = f"Perfil_{user_id}"
        
        conn_p = None
        cur_p = None
        try:
            conn_p, cur_p = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="perfil")
            query_perfil = f'SELECT "MES", "PESO" FROM "{tabla_nombre}" ORDER BY id ASC'
            cur_p.execute(query_perfil)
            filas_perfil = cur_p.fetchall()
            
            pesos_por_mes = {}
            for fila in filas_perfil:
                m_val = str(fila[0] or "").strip()
                p_val = fila[1]
                if m_val and p_val is not None:
                    try:
                        p_num = float(str(p_val).replace(',', '.'))
                        if p_num > 1000: p_num /= 1000.0
                        pesos_por_mes[m_val] = p_num
                    except ValueError:
                        pass
            
            meses_ordenados = sorted(pesos_por_mes.keys())
            if mes_anterior_str in meses_ordenados:
                peso_inicio_mes = pesos_por_mes[mes_anterior_str]
                
                if peso_fin_mes_override is not None:
                    peso_fin_mes = float(peso_fin_mes_override)
                    if peso_fin_mes > 1000: peso_fin_mes /= 1000.0
                    delta_peso = peso_fin_mes - peso_inicio_mes
                else:
                    idx_actual = meses_ordenados.index(mes_anterior_str)
                    if idx_actual + 1 < len(meses_ordenados):
                        mes_siguiente = meses_ordenados[idx_actual + 1]
                        peso_fin_mes = pesos_por_mes[mes_siguiente]
                        delta_peso = peso_fin_mes - peso_inicio_mes
                    else:
                        delta_peso = 0.0
        except Exception as e_delta:
            logger.error(f"Error calculando delta de peso dinámico en Supabase para User {user_id}: {e_delta}")
            delta_peso = 0.0
        finally:
            if cur_p:
                try: cur_p.close()
                except: pass
            if conn_p:
                try: conn_p.close()
                except: pass

        gasto_diario_total = ingesta_diaria - ((delta_peso * 7700.0) / dias_registrados)
        factor_limpio = (gasto_diario_total - ejercicio_diario) / tmb_pura
        
        factor_limpio = max(1.20, min(1.85, factor_limpio))
        ocupacion_db = float(round(factor_limpio, 3))

        _core_guardar_perfil_db(user_id, str(mes_anterior_str), {
            "ocupacion": ocupacion_db
        })

        return factor_limpio

    except Exception as e:
        logger.error(f"Error al calcular factor limpio del mes anterior en Supabase para User {user_id}: {e}")
        return None               

def calcular_peso_etapa(peso_actual: float, peso_ideal: float, ritmo_preferido: str = "moderado") -> float:
    if peso_actual <= peso_ideal:
        return round(peso_actual, 1)
    
    ritmo_clean = str(ritmo_preferido).strip().lower()
    if "tranquilo" in ritmo_clean or "lento" in ritmo_clean or ritmo_clean == "1":
        factor_actual = 0.90
    elif "rapido" in ritmo_clean or "intenso" in ritmo_clean or "decidido" in ritmo_clean or ritmo_clean == "3":
        factor_actual = 0.75
    else:
        factor_actual = 0.85
        
    factor_ideal = 1.0 - factor_actual
    peso_etapa = (peso_actual * factor_actual) + (peso_ideal * factor_ideal)
    return round(peso_etapa, 1)

# 8. CÁLCULO DE TMB Y GET (SCHOFIELD OMS EN NIÑOS, KATCH/MIFFLIN AJUSTADO EN ADULTOS)
def calcular_tmb_y_get(peso_actual: float, altura_cm: float, edad: int, genero: str = "masculino", actividad: float = 1.375, masa_magra: float = None, peso_ideal: float = None, cadera_cm: float = None) -> tuple[float, float]:
    try:
        peso = float(peso_actual)
        if peso > 1000: 
            peso /= 1000.0
            
        altura = float(altura_cm)
        if altura < 3.0:
            altura *= 100.0  # Corrige metros a centímetros
        elif altura > 500.0:
            altura /= 10.0   # Corrige milímetros a centímetros

        anios = int(float(edad))
    except (TypeError, ValueError):
        peso, altura, anios = 1.0, 1.0, 1

    gen_clean = str(genero).strip().lower()
    is_femenino = gen_clean in ["femenino", "f", "mujer", "female", "chica", "niña"]

    try:
        factor_act = float(actividad)
        if factor_act > 10:
            factor_act /= 1000.0
        if factor_act <= 0:
            factor_act = 1.375
    except (TypeError, ValueError):
        factor_act = 1.375

    # --- PEDIATRÍA (< 18 AÑOS): SCHOFIELD / OMS CON DEPÓSITO DE CRECIMIENTO ---
    if anios < 18:
        if is_femenino:
            if anios < 10:
                tmb = (22.500 * peso) + 499.0
            else:
                tmb = (13.384 * peso) + 692.6
        else:
            if anios < 10:
                tmb = (22.706 * peso) + 504.3
            else:
                tmb = (17.686 * peso) + 658.2

        calorias_crecimiento = 25.0
        get = (tmb * factor_act) + calorias_crecimiento
        return round(tmb, 2), round(get, 2)

    # --- ADULTOS (>= 18 AÑOS): KATCH-MCARDLE + AJUSTE DINÁMICO POR PESO EVALUADO ---
    if is_femenino:
        tmb_mifflin = (10.0 * peso) + (6.25 * altura) - (5.0 * anios) - 161.0
    else:
        tmb_mifflin = (10.0 * peso) + (6.25 * altura) - (5.0 * anios) + 5.0

    if masa_magra is None or masa_magra <= 1.0:
        # Buscamos los datos biométricos reales del usuario en la base de datos (sin pisar su peso real)
        bio = _obtener_biometria_encapsulada(sexo_arg=genero, altura_arg=altura, peso_arg=None, edad_arg=anios)
        cint_eval = bio.get("cintura", 1.0)
        cuell_eval = bio.get("cuello", 1.0)
        cad_eval = cadera_cm if (cadera_cm is not None and float(cadera_cm) > 0) else bio.get("cadera", 0.0)
        peso_real_db = bio.get("peso", 0.0)
        if peso_real_db <= 1.0:
            peso_real_db = peso

        # Calculamos la masa magra real de la persona en base a su peso real y sus circunferencias actuales
        masa_magra_real = None
        if is_femenino:
            if cint_eval > 1.0 and cuell_eval > 1.0 and cad_eval > 1.0:
                _, masa_magra_real = calcular_grasa_y_magra(genero, altura, cint_eval, cuell_eval, peso_real_db, cadera_cm=cad_eval, edad=anios)
        else:
            if cint_eval > 1.0 and cuell_eval > 1.0 and cint_eval > cuell_eval:
                _, masa_magra_real = calcular_grasa_y_magra(genero, altura, cint_eval, cuell_eval, peso_real_db, edad=anios)

        if masa_magra_real is not None and masa_magra_real > 1.0:
            # Si estamos calculando para un peso distinto al real (ej: peso_etapa o peso_ideal),
            # ajustamos la masa libre de grasa considerando que de cada kg de diferencia de peso,
            # ~75% es tejido adiposo y ~25% es componente magro/hídrico de sostén:
            diferencia_peso = peso - peso_real_db
            masa_magra = max(25.0, masa_magra_real + (diferencia_peso * 0.25))

    if masa_magra is not None and masa_magra > 1.0:
        tmb_katch = 370.0 + (21.6 * float(masa_magra))
        # Combinamos Katch-McArdle (precisión por composición magra) con Mifflin (impacto del peso total a trasladar)
        tmb = (tmb_katch * 0.70) + (tmb_mifflin * 0.30)
    else:
        tmb = tmb_mifflin

    get = tmb * factor_act
    return round(tmb, 2), round(get, 2)
     
async def _validar_peso_mes_actual(update: Update = None, context: ContextTypes.DEFAULT_TYPE = None, user_id: int = None) -> bool:
    uid = user_id or (update.effective_user.id if update else None)
    if not uid:
        return False

    ahora = obtener_ahora_arg() if 'obtener_ahora_arg' in globals() else datetime.now()
    mes_actual_str = ahora.strftime("%Y-%m")
    mes_anterior_str = (ahora.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    fecha_hoy_str = ahora.strftime("%Y-%m-%d")

    # 1. Garantizar fila del mes actual (si no existía y había peso post-día 24, ya lo migra y valida)
    if '_garantizar_fila_mes_actual' in globals():
        autovalidado = _garantizar_fila_mes_actual(uid, ahora)
        if autovalidado:
            return True

    # 2. Verificar en Usuarios si ya figura actualizado en el mes actual
    try:
        ultimo_registro = obtener_ultimo_peso(uid) if 'obtener_ultimo_peso' in globals() else None
    except Exception as e:
        logger.error(f"Error en validar_peso_mes_actual para User {uid}: {e}")
        ultimo_registro = None

    peso_valido = False

    if ultimo_registro:
        fecha_val = (
            ultimo_registro.get("fecha") or  
            ultimo_registro.get("Ultimo Mes Peso") or  
            ultimo_registro.get("MES") or  
            ""
        )
        fecha_str = str(fecha_val).strip()

        if fecha_str:
            formatos = ["%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%Y-%m", "%m/%Y"]
            fecha_dt = None
            for fmt in formatos:
                try:
                    fecha_dt = datetime.strptime(fecha_str, fmt)
                    break
                except ValueError:
                    continue

            if fecha_dt:
                if fecha_dt.year == ahora.year and fecha_dt.month == ahora.month:
                    peso_valido = True
            else:
                if mes_actual_str in fecha_str or ahora.strftime("%m/%Y") in fecha_str:
                    peso_valido = True

    if peso_valido:
        return True

    # 3. Si aún no figura validado este mes, verificamos en Perfil_<uid> si en el mes anterior se cargó peso después del día 24
    try:
        tabla_nombre = f"Perfil_{uid}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="perfil")
        cur.execute(f'ALTER TABLE "{tabla_nombre}" ADD COLUMN IF NOT EXISTS "peso_actual" DOUBLE PRECISION;')
        conn.commit()

        cur.execute(f"""
            SELECT "PESO", "peso_actual", "Fecha_Actualizacion"
            FROM "{tabla_nombre}"
            WHERE "MES" = %s
            ORDER BY id DESC LIMIT 1
        """, (str(mes_anterior_str),))
        fila_ant = cur.fetchone()
        cur.close()
        conn.close()

        if fila_ant:
            peso_base_ant = float(fila_ant[0] or 0.0)
            if peso_base_ant > 1000: peso_base_ant /= 1000.0
            peso_act_ant = float(fila_ant[1] or 0.0)
            if peso_act_ant > 1000: peso_act_ant /= 1000.0
            fecha_act_ant = str(fila_ant[2] or "").strip()

            dia_act = 0
            if fecha_act_ant:
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
                    try:
                        dia_act = datetime.strptime(fecha_act_ant, fmt).day
                        break
                    except ValueError:
                        continue

            peso_heredado = peso_act_ant if peso_act_ant > 0 else peso_base_ant
            if dia_act > 24 and peso_heredado > 0:
                factor_nuevo = None
                if '_calcular_y_actualizar_factor_mes_anterior' in globals():
                    factor_nuevo = _calcular_y_actualizar_factor_mes_anterior(
                        uid, mes_anterior_str, peso_fin_mes_override=peso_heredado
                    )

                conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="perfil")
                if factor_nuevo and factor_nuevo > 0:
                    cur.execute(f"""
                        UPDATE "{tabla_nombre}"
                        SET "PESO" = %s, "peso_actual" = %s, "ocupacion" = %s, "Fecha_Actualizacion" = %s
                        WHERE "MES" = %s
                    """, (peso_heredado, peso_heredado, float(factor_nuevo), fecha_hoy_str, str(mes_actual_str)))
                else:
                    cur.execute(f"""
                        UPDATE "{tabla_nombre}"
                        SET "PESO" = %s, "peso_actual" = %s, "Fecha_Actualizacion" = %s
                        WHERE "MES" = %s
                    """, (peso_heredado, peso_heredado, fecha_hoy_str, str(mes_actual_str)))
                conn.commit()
                cur.close()
                conn.close()

                conn_u, cur_u = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
                cur_u.execute('UPDATE "Usuarios" SET "Ultimo Mes Peso" = %s WHERE "User ID" = %s', (fecha_hoy_str, str(uid)))
                conn_u.commit()
                cur_u.close()
                conn_u.close()

                if factor_nuevo and factor_nuevo > 0:
                    guardar_ocupacion_db(uid, factor_nuevo, mes_actual_str)

                return True
    except Exception as e_post24:
        logger.error(f"Error verificando peso post-día 24 para {uid}: {e_post24}")

    # 4. Si no hay peso en el mes actual ni posterior al día 24 del mes pasado, solicitar el peso al usuario
    lang = obtener_idioma_usuario(uid) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    msg_falta_peso = traducciones.get(
        "04_bot_solic_peso_mensual",
        "⚖️ **Actualización de Peso Mensual Requerida**\n\n"
        "Para continuar con tus reportes de este nuevo mes, por favor ingresá tu peso actual ejecutando:\n"
        "`/peso [tu_peso]` (ejemplo: `/peso 82.5`)"
    ).replace('\\n', '\n')

    try:
        if update and update.message:
            await update.message.reply_text(msg_falta_peso, parse_mode="Markdown")
        elif update and update.callback_query:
            await update.callback_query.message.reply_text(msg_falta_peso, parse_mode="Markdown")
        elif context and hasattr(context, 'bot'):
            await context.bot.send_message(chat_id=int(uid), text=msg_falta_peso, parse_mode="Markdown")
    except Exception as e_msg:
        logger.error(f"No se pudo enviar aviso de peso mensual a {uid}: {e_msg}")

    return False       
    
#              INICIO                     FUNCIONES SOPORTE MULTILENGUAJE                   INICIO
# =============================================================================================================================================

def obtener_idioma_usuario(user_id):
    """Obtiene el idioma configurado para un usuario de Telegram desde Supabase."""
    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        cur.execute('SELECT "Idioma" FROM "Usuarios" WHERE "User ID" = %s', (str(user_id).strip(),))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row[0]:
            return str(row[0]).strip().lower()
    except Exception as e:
        logger.error(f"Error obteniendo idioma para {user_id}: {e}")
    return 'es'

def obtener_traducciones_db(lang):
    """Consulta la tabla 'multi' en Supabase dinámicamente para cualquier idioma cargado."""
    traducciones = {}
    lang_clean = str(lang or "es").strip().lower()
    try:
        conn, cur = _asegurar_tabla_y_conectar("multi", tipo_tabla="comidas_precargadas")
        
        # Obtenemos los nombres exactos de las columnas reales en Supabase (para evitar errores de mayúsculas/minúsculas)
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND LOWER(table_name) = 'multi'
        """)
        columnas_reales = {row[0].strip().lower(): row[0] for row in cur.fetchall() if row[0]}
        
        col_var_real = columnas_reales.get('variables', 'variables')
        # Busca el idioma pedido; si no existe esa columna, cae a 'es' o 'en'
        col_lang_real = (
            columnas_reales.get(lang_clean) or 
            columnas_reales.get('es') or 
            columnas_reales.get('en')
        )

        if not col_lang_real:
            cur.close()
            conn.close()
            return traducciones

        query = f'SELECT "{col_var_real}", "{col_lang_real}" FROM "multi"'
        cur.execute(query)
        filas = cur.fetchall()
        cur.close()
        conn.close()

        for fila in filas:
            var_name = str(fila[0] or "").strip()
            var_text = str(fila[1] or "").strip()
            if var_name and var_text:
                # Guardamos la clave tanto original como en minúsculas por seguridad
                traducciones[var_name] = var_text
                traducciones[var_name.lower()] = var_text
    except Exception as e:
        logger.error(f"Error al obtener traducciones de Supabase para el idioma {lang}: {e}")
    return traducciones

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

async def procesar_y_enviar_informe_mensual(context, user_id: int, chat_destino: int, mes_target: str, es_automatico_15: bool = False, forzar_envio: bool = False):
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    try:
        peso_ok = await _validar_peso_mes_actual(context=context, user_id=user_id)
        if not peso_ok and not forzar_envio:
            return False

        df_datos = obtener_datos_usuario(user_id) 
        if df_datos.empty or 'Fecha' not in df_datos.columns:
            msg_nodata = traducciones.get("08_sup_inf_no_registros", "⚠️ No hay suficientes registros para generar el reporte.")
            await context.bot.send_message(chat_id=user_id, text=msg_nodata)
            return False

        df_datos['Fecha_dt'] = pd.to_datetime(df_datos['Fecha'], errors='coerce').dt.tz_localize(None).dt.normalize()
        
        ahora_arg = obtener_ahora_arg()
        if hasattr(ahora_arg, 'tzinfo') and ahora_arg.tzinfo is not None:
            ahora_arg = ahora_arg.replace(tzinfo=None)
        
        hoy_ts = pd.Timestamp(ahora_arg).normalize()
        ayer_ts = hoy_ts - pd.Timedelta(days=1)
        mes_actual_str = hoy_ts.strftime("%Y-%m")

        if es_automatico_15:
            inicio_periodo = pd.Timestamp(f"{mes_target}-01").normalize()
            fin_periodo = pd.Timestamp(f"{mes_target}-14").normalize()
            etiqueta_tmpl = traducciones.get("08_sup_inf_periodo_quincenal", "Quincenal ({mes_target}: 1 al 14)")
            etiqueta_periodo = etiqueta_tmpl.format(mes_target=mes_target)
        else:
            inicio_periodo = pd.Timestamp(f"{mes_target}-01").normalize()
            if mes_target == mes_actual_str:
                fin_periodo = ayer_ts
                etiqueta_tmpl = traducciones.get("08_sup_inf_periodo_mes_actual", "Mes Actual en curso ({mes_target}: del 01 al {ayer_ts})")
                etiqueta_periodo = etiqueta_tmpl.format(mes_target=mes_target, ayer_ts=ayer_ts.strftime('%d/%m'))
            else:
                fin_periodo = (inicio_periodo + pd.offsets.MonthEnd(0)).normalize()
                etiqueta_tmpl = traducciones.get("08_sup_inf_periodo_mes_completo", "Mes Completo ({mes_target})")
                etiqueta_periodo = etiqueta_tmpl.format(mes_target=mes_target)

        df_filtrado = df_datos[(df_datos['Fecha_dt'] >= inicio_periodo) & (df_datos['Fecha_dt'] <= fin_periodo)].copy()

        if df_filtrado.empty:
            msg_template = traducciones.get("08_sup_inf_sin_registros_periodo", "⚠️ No se encontraron registros cerrados para el período {etiqueta_periodo}.")
            msg_closed = msg_template.format(etiqueta_periodo=etiqueta_periodo)
            await context.bot.send_message(chat_id=user_id, text=msg_closed)
            return False

        perfil = obtener_perfil_usuario(user_id, mes_target=mes_target) or {}
        m = calcular_metricas_mensuales(df_filtrado, perfil, user_id=user_id, mes_str=mes_target) or {}

        df_presion = pd.DataFrame()
        tmb_val = perfil.get('tmb', 0) if isinstance(perfil, dict) else 0
        pdf_buffer = await asyncio.to_thread(
            generar_pdf_resumen_bytes,
            mes_target,
            df_filtrado,
            df_presion,
            perfil,
            tmb_val,
            user_id
        )
        
        # Envío del informe al usuario
        cap_tmpl = traducciones.get("08_sup_inf_caption_reporte", "📊 **Reporte Mensual correspondiente a {mes_target}**")
        caption_txt = cap_tmpl.format(mes_target=mes_target)
        
        await context.bot.send_document(
            chat_id=chat_destino,
            document=pdf_buffer,
            filename=f"Informe_Mensual_{mes_target}.pdf",
            caption=caption_txt,
            parse_mode="Markdown"
        )

        # --- ALERTA CLÍNICA AUTOMÁTICA AL PROFESIONAL SI TIENE MÉDICO ASIGNADO ---
        prof_asignado = str(perfil.get("profesional", "")).strip() if isinstance(perfil, dict) else ""
        if not prof_asignado:
            # Intentar buscar el profesional desde la tabla de usuarios
            try:
                conn_u, cur_u = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
                cur_u.execute('SELECT "profesional" FROM "Usuarios" WHERE "User ID" = %s', (str(user_id),))
                fila_prof = cur_u.fetchone()
                cur_u.close(); conn_u.close()
                if fila_prof and fila_prof[0]:
                    prof_asignado = str(fila_prof[0]).split('.')[0].strip()
            except Exception:
                pass

        if prof_asignado and prof_asignado != "123456789":
            try:
                # Verificar desvío respecto a los rangos clínicos
                bal_neto = m.get("prom_bal_neto", 0)
                c_min = m.get("cal_min", 0)
                c_max = m.get("cal_max", 0)
                
                desvio = False
                motivo_desvio = ""
                if bal_neto < c_min:
                    desvio = True
                    m_inferior_tmpl = traducciones.get("08_sup_inf_motivo_inf", "Balance neto inferior al mínimo establecido ({bal_neto} kcal vs mín {c_min} kcal)")
                    motivo_desvio = m_inferior_tmpl.format(bal_neto=bal_neto, c_min=c_min)
                elif bal_neto > c_max:
                    desvio = True
                    m_superior_tmpl = traducciones.get("08_sup_inf_motivo_sup", "Balance neto superior al máximo establecido ({bal_neto} kcal vs máx {c_max} kcal)")
                    motivo_desvio = m_superior_tmpl.format(bal_neto=bal_neto, c_max=c_max)

                if desvio:
                    alerta_tmpl = traducciones.get(
                        "08_sup_inf_alerta_medico",
                        "⚠️ **ALERTA CLÍNICA DE DESVÍO**\n\nEl paciente **{nombre_paciente}** (ID: `{user_id}`) ha presentado un desvío en su reporte mensual de `{mes_target}`:\n• *Motivo:* {motivo_desvio}\n\nSe adjunta copia del informe para su revisión."
                    )
                    alerta_medico = alerta_tmpl.format(
                        nombre_paciente=perfil.get('Nombre', user_id),
                        user_id=user_id,
                        mes_target=mes_target,
                        motivo_desvio=motivo_desvio
                    ).replace('\\n', '\n')
                    
                    pdf_buffer.seek(0)
                    await context.bot.send_message(chat_id=int(prof_asignado), text=alerta_medico, parse_mode="Markdown")
                    pdf_buffer.seek(0)
                    await context.bot.send_document(
                        chat_id=int(prof_asignado),
                        document=pdf_buffer,
                        filename=f"Alerta_Paciente_{user_id}_{mes_target}.pdf"
                    )
            except Exception as e_medico:
                logger.error(f"Error al enviar alerta clínica al profesional {prof_asignado} para el usuario {user_id}: {e_medico}")

        return True
    except Exception as e:
        logger.error(f"Error in procesar_y_enviar_informe_mensual for {user_id}: {e}")
        return False
   
async def limpiar_teclado_anterior(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Elimina los botones del menú anterior si el usuario inicia una nueva acción."""
    chat_id = update.effective_chat.id if update.effective_chat else None
    if not chat_id:
        return
        
    last_msg_id = context.user_data.pop('last_menu_msg_id', None)
    if last_msg_id:
        try:
            # Editamos el mensaje pasándole reply_markup=None para borrar solo los botones
            await context.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=last_msg_id,
                reply_markup=None
            )
        except Exception:
            pass # Falla silenciosa si el mensaje fue borrado a mano por el usuario o es muy viejo
   
def requiere_registro(func):
    """Decorador que verifica registro y bloquea usuarios en Estado 3 ofreciendo reactivación prorrateada."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if 'limpiar_teclado_anterior' in globals():
            await limpiar_teclado_anterior(update, context)
            
        user_id = str(update.effective_user.id).strip()
        encontrado = False
        esta_activo = True
        estado_val = "0"
        
        lang = obtener_idioma_usuario(user_id) or 'es'
        traducciones = obtener_traducciones_db(lang) or {}

        mensaje_no_registrado = traducciones.get(
            "04_bot_no_registrado", 
            "⚠️ **¡Aún no estás registrado!**\n\n"
            "Para usar este comando y acceder a tu plan nutricional, primero debés registrarte.\n\n"
            "👉 Usá el comando `/alta` para crear tu perfil en un par de pasos."
        ).replace('\\n', '\n')        
        
        mensaje_deshabilitado = traducciones.get(
            "04_bot_deshabilitado", 
            "❌ **Tu cuenta ha sido deshabilitada por inactividad o eliminación del sistema. Por favor, contactá al administrador.**"
        )

        try:
            conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
            cur.execute('SELECT "User ID", "Estado" FROM "Usuarios"')
            filas = cur.fetchall()
            cur.close()
            conn.close()

            for fila in filas:
                raw_id = fila[0]
                if raw_id and str(raw_id).split('.')[0].strip() == user_id:
                    encontrado = True
                    estado_val = str(fila[1] if fila[1] is not None else "0").strip().lower()
                    
                    if estado_val in ['baja', 'suspendido']:
                        esta_activo = False
                    break
        except Exception as e:
            logger.error(f"Error al verificar registro y pagos en decorador: {e}")

        if not encontrado:
            txt_alert_reg = traducciones.get("04_bot_alert_reg", "⚠️ Registro requerido")
            if update.message:
                await update.message.reply_text(mensaje_no_registrado, parse_mode="Markdown")
            elif update.callback_query:
                await update.callback_query.answer(txt_alert_reg, show_alert=True)
                await update.callback_query.message.reply_text(mensaje_no_registrado, parse_mode="Markdown")
            return

        if not esta_activo:
            txt_alert_disabled = traducciones.get("04_bot_alert_disabled", "⚠️ Cuenta deshabilitada")
            if update.message:
                await update.message.reply_text(mensaje_deshabilitado, parse_mode="Markdown")
            elif update.callback_query:
                await update.callback_query.answer(txt_alert_disabled, show_alert=True)
                await update.callback_query.message.reply_text(mensaje_deshabilitado, parse_mode="Markdown")
            return

        if estado_val == '3':
            mensaje_bloqueo = traducciones.get(
                "04_bot_prueba_fin",
                "⚠️ **Tu período de prueba gratuito ha finalizado.**\n\n"
                "Para seguir usando todas las funciones del asistente, podés activar tu cuenta abonando los días que restan hasta fin de mes.\n\n"
                "Una vez abonado, volverás a tener acceso total y tu ciclo de facturación se alineará al día 1 del mes próximo."
            ).replace('\\n', '\n')

            txt_btn_activar = traducciones.get("04_bot_btn_activar_mes", "⭐ Activar mes en curso")
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(txt_btn_activar, callback_data="rescate_mensual")]
            ])
            
            txt_alert_susp = traducciones.get("04_bot_alert_susp", "⚠️ Cuenta suspendida")
            
            if update.message:
                await update.message.reply_text(mensaje_bloqueo, reply_markup=keyboard, parse_mode="Markdown")
            elif update.callback_query:
                await update.callback_query.answer(txt_alert_susp, show_alert=True)
                await update.callback_query.message.reply_text(mensaje_bloqueo, reply_markup=keyboard, parse_mode="Markdown")
            return

        return await func(update, context, *args, **kwargs)
    return wrapper
    
# =============================================================================================================================================
#              FINAL                          FUNCIONES AUXILIARES INTERNAS                  FINAL
# =============================================================================================================================================

# ======================================================================================================================================       
#                INICIO                       14 FUNCIONES IA                                      INICIO
# ======================================================================================================================================

async def ejecutar_consulta_ia(
    prompt: str,
    max_tokens: int = 1500,
    temperature: float = 0.4,
    system_prompt: str = None,
    modelo_override: str = None,
):
  modelo_a_usar = modelo_override or MODELO_TEXTO
  configuracion_gen = {
      "temperature": temperature,
      "max_output_tokens": max_tokens,
  }

  for intento in range(1, 3):
    try:
      model = genai.GenerativeModel(
          modelo_a_usar, system_instruction=system_prompt
      )
      response = await asyncio.to_thread(
          model.generate_content, prompt, generation_config=configuracion_gen
      )
      if response and response.text:
        return response.text.strip()
    except Exception as e_prin:
      logger.warning(
          f"⚠️ Intento {intento} fallido con modelo principal"
          f" ({modelo_a_usar}): {e_prin}"
      )
      if intento < 2:
        await asyncio.sleep(1)

  if not modelo_override:
    try:
      logger.info(f"🔄 Activando modelo de respaldo: {MODELO_RESPALDO}")
      model_resp = genai.GenerativeModel(
          MODELO_RESPALDO, system_instruction=system_prompt
      )
      response_resp = await asyncio.to_thread(
          model_resp.generate_content, prompt, generation_config=configuracion_gen
      )
      if response_resp and response_resp.text:
        return response_resp.text.strip()
    except Exception as e_resp:
      logger.warning(
          f"⚠️ Falla en modelo de respaldo ({MODELO_RESPALDO}): {e_resp}"
      )

    try:
      logger.info(f"🚨 Activando modelo de emergencia: {MODELO_EMERGENCIA}")
      model_emer = genai.GenerativeModel(
          MODELO_EMERGENCIA, system_instruction=system_prompt
      )
      response_emer = await asyncio.to_thread(
          model_emer.generate_content, prompt, generation_config=configuracion_gen
      )
      if response_emer and response_emer.text:
        return response_emer.text.strip()
    except Exception as e_emer:
      logger.error(
          f"❌ Error crítico en ejecutar_consulta_ia: Todos los modelos"
          f" fallaron. {e_emer}"
      )

  return ""
  
def obtener_nombre_lenguaje_ia(user_id=None):
    # Obtiene el nombre completo del lenguaje para la IA desde la tabla Usuarios.
    if not user_id:
        return "Español"
    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        cur.execute('SELECT "Idioma" FROM "Usuarios" WHERE "User ID" = %s', (str(user_id),))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row[0]:
            return str(row[0]).strip()
    except Exception as e:
        logger.error(f"Error obteniendo lenguaje IA para {user_id}: {e}")
    return "Español"
    
async def analizar_con_ia(prompt_text, user_id=None, msg_obj=None):
    nombre_lenguaje = obtener_idioma_usuario(user_id) or "es"
    ahora = obtener_ahora_arg()
    fecha_hoy = ahora.strftime("%Y-%m-%d")
    mes_actual = ahora.strftime("%Y-%m")

    system_prompt = (
        f"Sos un asistente inteligente de salud. Idioma: {nombre_lenguaje}. "
        f"La fecha de HOY es {fecha_hoy} y el mes actual es {mes_actual}.\n"
        f"Clasificá el texto ingresado en SOLO TRES opciones:\n"
        "1. COMIDA (alimentos/bebidas)\n"
        "2. ACTIVIDAD (ejercicio)\n"
        "3. RECHAZO (cualquier otra cosa ajena al registro)\n\n"
        "REGLA ANTI-SPAM: Si el usuario ingresa alimentos ficticios, combinaciones absurdas (ej: 'piedras con mayonesa') o cantidades humanamente imposibles de ingerir en una sola comida (ej: '50 pizzas', '20 litros de bebida'), clasificalo inmediatamente como RECHAZO.\n\n"
        "REGLA MATEMÁTICA PARA COMIDAS: Calorías = (Proteínas*4) + (Carbohidratos*4) + (Grasas*9). Ajustá los valores para que la ecuación sea perfecta.\n"
        "Devolvé EXCLUSIVAMENTE un JSON estricto según estas reglas:\n"
        "SI ES COMIDA: {\"tipo\": \"Comida\", \"items\": [{\"alimento\": \"...\", \"peso\": 0, \"calorias\": 0, \"proteinas\": 0, \"grasas\": 0, \"carbohidratos\": 0, \"fibras\": 0}]}\n"
        "SI ES ACTIVIDAD: {\"tipo\": \"Actividad\", \"items\": [{\"alimento\": \"[MINUTOS] min [DETALLE COMPLETO]\", \"peso\": 0, \"calorias\": -0, \"proteinas\": 0, \"grasas\": 0, \"carbohidratos\": 0, \"fibras\": 0}]} "
        "(REGLA OBLIGATORIA PARA ACTIVIDAD: El campo 'alimento' DEBE empezar SIEMPRE con los minutos en número seguidos de 'min' y mantener todo el detalle del texto original sin resumir. Ejemplo: '50 min caminata en el parque recorriendo 3000 metros').\n"
        "SI ES RECHAZO: {\"tipo\": \"Rechazo\"}"
    )

    configuracion_gen = {"response_mime_type": "application/json", "temperature": 0.1}

    try:
        model = genai.GenerativeModel(MODELO_TEXTO, system_instruction=system_prompt)
        response = await asyncio.to_thread(model.generate_content, prompt_text, generation_config=configuracion_gen)
        texto_limpio = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(texto_limpio)
        
    except Exception as e_prin:
        logger.warning(f"⚠️ Falla Principal ({MODELO_TEXTO}): {e_prin}. Pasando a Respaldo...")
        if msg_obj:
            try: await msg_obj.edit_text("⚠️ Main server busy. Switching to backup server...")
            except Exception: pass
            
        try:
            model_resp = genai.GenerativeModel(MODELO_RESPALDO, system_instruction=system_prompt)
            response_resp = await asyncio.to_thread(model_resp.generate_content, prompt_text, generation_config=configuracion_gen)
            texto_limpio = response_resp.text.replace("```json", "").replace("```", "").strip()
            return json.loads(texto_limpio)
            
        except Exception as e_resp:
            logger.warning(f"⚠️ Falla Respaldo ({MODELO_RESPALDO}): {e_resp}. Pasando a Emergencia...")
            if msg_obj:
                try: await msg_obj.edit_text("⚠️ Retrying connection with emergency server...")
                except Exception: pass
                
            try:
                model_emer = genai.GenerativeModel(MODELO_EMERGENCIA, system_instruction=system_prompt)
                response_emer = await asyncio.to_thread(model_emer.generate_content, prompt_text, generation_config=configuracion_gen)
                texto_limpio = response_emer.text.replace("```json", "").replace("```", "").strip()
                return json.loads(texto_limpio)
                
            except Exception as e_emer:
                logger.error(f"❌ Fallaron todos los modelos de texto: {e_emer}")
                return {"items": [], "tipo": "Error_IA"}
                
async def analizar_imagen_con_ia(base64_image: str, user_id=None, msg_obj=None):
    nombre_lenguaje = obtener_idioma_usuario(user_id) or "es"
    ahora = obtener_ahora_arg()
    fecha_hoy = ahora.strftime("%Y-%m-%d")
    mes_actual = ahora.strftime("%Y-%m")

    system_prompt = (
        f"Sos un software analítico clínico y bromatológico. Idioma: ({nombre_lenguaje}).\n"
        f"La fecha de HOY es {fecha_hoy} y el mes actual es {mes_actual}.\n"
        f"Analizá la imagen y determiná si corresponde a un TENSIÓMETRO DIGITAL, a un PLATO DE COMIDA/BEBIDA, o a NINGUNO, y actuá según estas reglas:\n\n"
        f"1. SI ES UN TENSIÓMETRO: Extraé la presión sistólica (alta), diastólica (baja) y las pulsaciones. El campo 'tipo' debe ser 'Presion'.\n"
        f"2. SI ES COMIDA: Aplicá CERO INVENCIÓN. Identificá los alimentos basándote en tablas oficiales (ej. USDA). REGLA MATEMÁTICA ESTRICTA: Las calorías deben coincidir exactamente con la fórmula (Proteínas * 4) + (Carbohidratos * 4) + (Grasas * 9). Ajustá los valores en silencio hasta que la ecuación sea matemáticamente perfecta. El campo 'tipo' debe ser 'Comida'.\n"
        f"3. SI ES OTRA COSA (paisajes, animales, personas u objetos ajenos): El campo 'tipo' debe ser 'Rechazo'.\n\n"
        f"Devolvé EXCLUSIVAMENTE un JSON con esta estructura exacta:\n"
        '{"tipo": "...", "alta": 0.0, "baja": 0.0, "pulsaciones": 0.0, "items": [{"alimento": "...", "peso": 0.0, "calorias": 0.0, "proteinas": 0.0, "grasas": 0.0, "carbohidratos": 0.0, "fibras": 0.0}]}'
    )

    imagen_data = {"mime_type": "image/jpeg", "data": base64.b64decode(base64_image)}
    prompt_usuario = "Realiza el desglose científico de esta imagen según las directrices establecidas."
    configuracion_gen = {"response_mime_type": "application/json", "temperature": 0.0}

    try:
        model = genai.GenerativeModel(MODELO_FOTO, system_instruction=system_prompt)
        response = await asyncio.to_thread(model.generate_content, [prompt_usuario, imagen_data], generation_config=configuracion_gen)
        texto_limpio = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(texto_limpio)
        
    except Exception as e_prin:
        logger.warning(f"⚠️ Falla Principal Foto ({MODELO_FOTO}): {e_prin}. Pasando a Respaldo...")
        # Eliminamos el msg_obj.edit_text para que no interrumpa la animación visual del usuario
        
        try:
            model_resp = genai.GenerativeModel(MODELO_RESPALDO, system_instruction=system_prompt)
            response_resp = await asyncio.to_thread(model_resp.generate_content, [prompt_usuario, imagen_data], generation_config=configuracion_gen)
            texto_limpio = response_resp.text.replace("```json", "").replace("```", "").strip()
            return json.loads(texto_limpio)
            
        except Exception as e_resp:
            logger.warning(f"⚠️ Falla Respaldo Foto ({MODELO_RESPALDO}): {e_resp}. Pasando a Emergencia...")
            # Eliminamos el msg_obj.edit_text acá también
            
            try:
                model_emerg = genai.GenerativeModel(MODELO_FOTO_EMERGENCIA, system_instruction=system_prompt)
                response_emerg = await asyncio.to_thread(model_emerg.generate_content, [prompt_usuario, imagen_data], generation_config=configuracion_gen)
                texto_limpio = response_emerg.text.replace("```json", "").replace("```", "").strip()
                return json.loads(texto_limpio)
                
            except Exception as e_emer:
                logger.error(f"❌ Fallaron todos los modelos de foto: {e_emer}")
                return {"items": [], "tipo": "Error_IA"}
                
# =====================================================================================================================================
#                    FINAL                          FUNCIONES IA                                     FINAL
# =====================================================================================================================================

# ======================================================================================================================================
#                  INICIO               COMANDOS CONFIRMACION FUNCIONES BOTONES                    INICIO
# ======================================================================================================================================
#                  INICIO               INTERFAZ Y RENDER DE CONFIRMACIÓN                      INICIO
# ======================================================================================================================================

async def render_confirmation_screen(msg_or_query, context):
    # 1. Extracción segura del chat_id y user_id
    chat_id = None
    user_id = None
    
    if hasattr(msg_or_query, 'chat') and msg_or_query.chat:
        chat_id = msg_or_query.chat.id
    elif hasattr(msg_or_query, 'message') and msg_or_query.message and msg_or_query.message.chat:
        chat_id = msg_or_query.message.chat.id

    if hasattr(msg_or_query, 'from_user') and msg_or_query.from_user and not msg_or_query.from_user.is_bot:
        user_id = msg_or_query.from_user.id
    elif hasattr(msg_or_query, 'message') and msg_or_query.message and msg_or_query.message.from_user and not msg_or_query.message.from_user.is_bot:
        user_id = msg_or_query.message.from_user.id
    else:
        user_id = chat_id # Fallback de emergencia

    if not chat_id:
        logger.error("No se pudo extraer chat_id en render_confirmation_screen")
        return

    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    items = context.user_data.get('pending_items', [])
    fecha = context.user_data.get('pending_fecha', obtener_ahora_arg().strftime("%Y-%m-%d"))
    momento = context.user_data.get('pending_momento', 'Comida')
    
    # Traducción del momento para visualización
    momento_display = traducciones.get(f'06_bot_momento_{momento.lower()}', momento)

    # 2. Formato HTML puro (sin markdown que rompa la pantalla)
    if momento == 'Actividad':
        t_reg_act = traducciones.get('06_bot_reg_actividad', "📝 <b>Registro de Actividad:</b>")
        t_fecha = traducciones.get('06_bot_label_fecha', "📅 Fecha")
        txt = f"{t_reg_act}\n{t_fecha}: <code>{fecha}</code>\n\n"
    else:
        t_conf_ing = traducciones.get('06_bot_conf_ingesta', "📝 <b>Confirmación de Ingesta:</b>")
        t_fecha = traducciones.get('06_bot_label_fecha', "📅 Fecha")
        t_momento = traducciones.get('06_bot_label_momento', "Momento")
        txt = f"{t_conf_ing}\n{t_fecha}: <code>{fecha}</code> | {t_momento}: <code>{momento_display}</code>\n\n"

    for idx, item in enumerate(items, start=1):
        peso_total = item.get('peso', 0)
        cal_total = item.get('calorias', 0)
        prot_total = item.get('proteinas', 0)
        grasas_total = item.get('grasas', 0)
        fibras_total = item.get('fibras', 0)
        
        alimento_str = item.get('alimento_display') or item.get('alimento', item.get('nombre', ''))
        alimento_limpio = alimento_str.replace('§', '').replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;').strip()

        if momento == 'Actividad':
            txt += f"<b>{idx}. {alimento_limpio}</b>: <code>{cal_total:.1f} kcal</code>\n"
        else:
            t_calorias = traducciones.get('06_bot_macro_calorias', "Calorías")
            t_proteinas = traducciones.get('06_bot_macro_proteinas', "Proteínas")
            t_grasas = traducciones.get('06_bot_macro_grasas', "Grasas tot.")
            t_fibras = traducciones.get('06_bot_macro_fibras', "Fibras")

            txt += f"<b>{idx}. {alimento_limpio}</b> ({peso_total:.1f}g):\n"
            txt += f"   • {t_calorias}: <code>{cal_total:.1f} kcal</code>\n"
            txt += f"   • {t_proteinas}: <code>{prot_total:.1f} g</code>\n"
            txt += f"   • {t_grasas}: <code>{grasas_total:.1f} g</code>\n"
            txt += f"   • {t_fibras}: <code>{fibras_total:.1f} g</code>\n\n"

    keyboard = []
    
    if momento != 'Actividad':
        momentos_config = [
            ("Desayuno", traducciones.get("06_bot_btn_desayuno", "🌅 08-11")),
            ("Almuerzo", traducciones.get("06_bot_btn_almuerzo", "☀️ 11-16")),
            ("Merienda", traducciones.get("06_bot_btn_merienda", "☕ 16-20")),
            ("Cena", traducciones.get("06_bot_btn_cena", "🌙 20-00"))
        ]
        m_buttons = []
        for nombre_momento, etiqueta_visual in momentos_config:
            estado = "✅" if nombre_momento.lower() == momento.lower() else "⏰"
            m_buttons.append(InlineKeyboardButton(f"{etiqueta_visual} {estado}", callback_data=f"set_m_{nombre_momento}"))
        keyboard.append(m_buttons)

    for idx, item in enumerate(items, start=1):
        nombre_corto = item.get('alimento', item.get('nombre', ''))[:10]
        keyboard.append([
            InlineKeyboardButton(f"#{idx} {nombre_corto}", callback_data=f"noop_{idx}"),
            InlineKeyboardButton("📝", callback_data=f"edit_item_{idx}"),
            InlineKeyboardButton("❌", callback_data=f"del_item_{idx}")
        ])

    ahora_arg = obtener_ahora_arg() if 'obtener_ahora_arg' in globals() else datetime.now()
    hoy_str = ahora_arg.strftime("%Y-%m-%d")
    ayer_str = (ahora_arg - timedelta(days=1)).strftime("%Y-%m-%d")
    
    hoy_label = ahora_arg.strftime("%d/%m")
    ayer_label = (ahora_arg - timedelta(days=1)).strftime("%d/%m")
    
    mark_hoy = "✅ " if fecha == hoy_str else ""
    mark_ayer = "✅ " if fecha == ayer_str else ""
    mark_otro = "✅ " if fecha not in [hoy_str, ayer_str] else ""

    keyboard.append([
        InlineKeyboardButton(f"{mark_hoy}🗓️ {hoy_label}", callback_data="set_d_hoy"),
        InlineKeyboardButton(f"{mark_ayer}🗓️ {ayer_label}", callback_data="set_d_ayer"),
        InlineKeyboardButton(f"{mark_otro}📅✏️", callback_data="set_d_otro")
    ])

    keyboard.append([
        InlineKeyboardButton("🗑️", callback_data="cancel_entry"),
        InlineKeyboardButton("💾", callback_data="confirm_save")
    ])

    markup = InlineKeyboardMarkup(keyboard)

    # 3. Despliegue seguro con reporte de errores para que nunca más falle en silencio
    is_callback = hasattr(msg_or_query, 'message') and msg_or_query.message is not None

    if is_callback:
        try:
            await msg_or_query.edit_message_text(txt, reply_markup=markup, parse_mode="HTML")
            return
        except Exception:
            pass

    if hasattr(msg_or_query, 'edit_text'):
        try:
            await msg_or_query.edit_text(txt, reply_markup=markup, parse_mode="HTML")
            context.user_data['last_menu_msg_id'] = msg_or_query.message_id
            return
        except Exception as e:
            logger.error(f"Fallo edit_text en render_confirmation_screen: {e}")

    if chat_id:
        msg_id = context.user_data.get('last_menu_msg_id')
        if msg_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=msg_id, text=txt, reply_markup=markup, parse_mode="HTML"
                )
                return
            except Exception:
                pass

        try:
            nuevo_msg = await context.bot.send_message(chat_id=chat_id, text=txt, reply_markup=markup, parse_mode="HTML")
            context.user_data['last_menu_msg_id'] = nuevo_msg.message_id
        except Exception as e:
            logger.error(f"Fallo send_message en render_confirmation_screen: {e}")
            
async def procesar_y_mostrar_confirmacion(data_json, msg_obj, context):
    items = data_json.get("items", [])
    tipo = str(data_json.get("tipo", "Comida")).strip().capitalize()
    total_calorias = sum(float(item.get("calorias", 0)) for item in items)
    
    # Extraemos el user_id del objeto mensaje para poder hacer las validaciones
    user_id = msg_obj.chat_id if hasattr(msg_obj, 'chat_id') else (msg_obj.chat.id if hasattr(msg_obj, 'chat') else None)
    lang = obtener_idioma_usuario(user_id) if user_id and 'obtener_idioma_usuario' in globals() else 'es'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    # --- EVITAMOS EL SILENCIO SI LA IA FALLA ---
    if not items or (total_calorias == 0 and tipo != "Actividad"):
        txt_err = traducciones.get("06_bot_error_ia_vacio", "⚠️ No pude identificar alimentos o calorías válidas en tu texto. Por favor, sé más específico (ej: 'Comí 200g de pollo').")
        try: 
            await msg_obj.edit_text(txt_err)
        except Exception: 
            pass
        return
        
    magnitud_calorica = abs(total_calorias)
    limite_exceso = 1000 if tipo == "Actividad" else 2200

    if magnitud_calorica > limite_exceso:
        if tipo == "Actividad":
            txt_exceso = traducciones.get(
                "06_bot_act_limite_superado",
                "⚠️ **Límite de actividad superado**\n\n"
                f"El gasto energético ingresado (`{magnitud_calorica:.0f} kcal`) supera el límite máximo permitido por registro (1.000 kcal).\n\n"
                "Si realizaste un entrenamiento muy extenso, podés dividirlo en dos registros separados (ej: turno mañana y turno tarde)."
            ).replace('\\n', '\n')
        else:
            txt_exceso = traducciones.get(
                "06_bot_comida_limite_superado",
                "⚠️ **Cantidad excesiva detectada**\n\n"
                f"El registro ingresado (`{magnitud_calorica:.0f} kcal`) supera el límite razonable para una sola ingesta.\n\n"
                "Por favor, ingresá las porciones individuales reales de tu plato."
            ).replace('\\n', '\n')

        await msg_obj.edit_text(txt_exceso, parse_mode="Markdown")
        return

    # 1. Obtener valores base por defecto (automáticos)
    fecha_auto, momento_auto = obtener_momento_y_fecha_auto()
    
    # 2. Verificar si la IA extrajo un momento en el JSON y actualizarlo
    momento_informado = data_json.get("momento")
    if momento_informado:
        momento = str(momento_informado).strip().capitalize()
    else:
        momento = momento_auto

    # 3. Verificar si la IA extrajo un día ("hoy", "ayer" o una fecha específica) en el JSON
    dia_informado = data_json.get("dia") or data_json.get("fecha")
    if dia_informado:
        dia_str = str(dia_informado).strip().lower()
        if dia_str == "hoy":
            fecha = obtener_ahora_arg().strftime("%Y-%m-%d")
        elif dia_str == "ayer":
            fecha = (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            fecha_parseada = parsear_fecha_flexible(dia_str)
            fecha = fecha_parseada if fecha_parseada else fecha_auto
    else:
        fecha = fecha_auto

    # --- NUEVO FILTRO: TOPE DIARIO DE 6000 KCAL (ANTI-SPAM) ---
    if tipo != "Actividad" and user_id:
        try:
            df_user = obtener_datos_usuario(user_id)
            if not df_user.empty and 'Fecha' in df_user.columns:
                df_dia = df_user[(df_user['Fecha'].astype(str).str.strip() == fecha) & (df_user['Calorias'] > 0)]
                calorias_acumuladas = df_dia['Calorias'].sum()
                
                if (calorias_acumuladas + magnitud_calorica) > 6000:
                    txt_spam = traducciones.get(
                        "06_bot_limite_diario_spam",
                        "⛔ **Límite calórico diario excedido**\n\n"
                        f"Ya llevás registradas `{calorias_acumuladas:.0f} kcal` consumidas para la fecha `{fecha}`. "
                        f"Sumar este nuevo registro supera el límite de seguridad establecido de 6.000 kcal diarias.\n\n"
                        "Por favor, revisá tus ingresos previos con `/diario` o ajustá las cantidades."
                    ).replace('\\n', '\n')
                    
                    await msg_obj.edit_text(txt_spam, parse_mode="Markdown")
                    return
        except Exception as e:
            logger.error(f"Error al verificar tope diario anti-spam para {user_id}: {e}")

    if tipo == "Actividad":
        momento = "Actividad"
        for item in items:
            item["peso"] = 0
            if item.get("calorias", 0) > 0:
                item["calorias"] = -abs(item["calorias"])

    context.user_data['pending_items'] = items
    context.user_data['pending_fecha'] = fecha
    context.user_data['pending_momento'] = momento

    await render_confirmation_screen(msg_obj, context)
    
    
#               MANEJADORES INDEPENDIENTES Y EXCLUSIVOS PARA CADA GRUPO DE BOTONES (CERO COMPARTIDOS)
# ======================================================================================================================================

async def callback_handler_presion_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    if data == "presion_guardar_directo":
        datos_presion = context.user_data.pop('pending_presion_foto', None)
        context.user_data.pop('awaiting_presion_nota', None)
        
        if datos_presion:
            alta = float(datos_presion.get("alta", 0))
            baja = float(datos_presion.get("baja", 0))
            pulsaciones = float(datos_presion.get("pulsaciones", 0))
            
            guardar_presion_db(user_id, alta, baja, pulsaciones, nota="")
            
            lbl_pul = traducciones.get("06_bot_presi_lbl_pulsaciones", "Pulsaciones")
            pul_txt = f" | {lbl_pul}: `{pulsaciones:.0f} lpm`" if pulsaciones > 0 else ""
            
            msg_base = traducciones.get(
                "06_bot_presion_exito", 
                "✅ **¡Presión arterial registrada con éxito!**\n\n• Presión Alta: `{alta} mmHg`\n• Presión Baja: `{baja} mmHg`{pul_txt}"
            ).replace('\\n', '\n').replace("{alta:.0f}", "{alta}").replace("{baja:.0f}", "{baja}")
            
            txt_exito = msg_base.format(alta=f"{alta:.0f}", baja=f"{baja:.0f}", pul_txt=pul_txt)
            await query.edit_message_text(txt_exito, parse_mode="Markdown")
        else:
            txt_expirada = traducciones.get("06_bot_presion_expirada", "⚠️ Los datos temporales de la presión expiraron.")
            await query.edit_message_text(txt_expirada)

    elif data == "presion_pedir_nota":
        context.user_data['awaiting_presion_nota'] = True
        txt_pedir_nota = traducciones.get("06_bot_pedir_nota_presion", "✏️ Por favor, escribí la nota o detalle para este registro de presión (o escribí `/x` para anular):").replace('\\n', '\n')
        await query.message.reply_text(txt_pedir_nota, parse_mode="Markdown")
        try:
            await query.message.delete()
        except Exception:
            pass

    elif data == "cancelar_presion_foto":
        context.user_data.pop('pending_presion_foto', None)
        context.user_data.pop('awaiting_presion_nota', None)
        txt_canc = traducciones.get("06_bot_presion_cancelada", "❌ Registro de presión cancelado.")
        await query.edit_message_text(txt_canc)
                
        
#              INICIO                      FUNCIONES MANEJADORES MODULARIZADOS (NUEVOS)                   INICIO
# =====================================================================================================================================

async def _sub_manejar_texto_actividad(update, context, raw_text, chat_id):
    context.user_data.pop('awaiting_activity_text', None)
    try: await update.message.delete()
    except: pass
    
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    
    txt_analizando = traducciones.get("06_bot_analizando_actividad_ia", "🤖 Analizando actividad con IA...")
    msg_analizando = await update.message.reply_text(txt_analizando)
    
    try:
        data = await analizar_con_ia(f"Calcula el gasto calórico de esta actividad física: {raw_text}", user_id)
        if str(data.get("tipo", "")).upper() != "ACTIVIDAD":
            data["tipo"] = "Actividad"
        await procesar_y_mostrar_confirmacion(data, msg_analizando, context)
    except Exception as e:
        txt_err = traducciones.get("06_bot_err_procesar_actividad", "❌ Error al procesar actividad: {e}").format(e=e)
        await msg_analizando.edit_text(txt_err)
              
async def _sub_manejar_fecha_personalizada_ingesta(update, context, raw_text, chat_id):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    fecha_parseada = parsear_fecha_flexible(raw_text)
    msg_solic = context.user_data.pop('msg_solicitud_fecha_id', None)
    if msg_solic:
        try: await context.bot.delete_message(chat_id=chat_id, message_id=msg_solic)
        except Exception: pass
    try: await update.message.delete()
    except Exception: pass

    if fecha_parseada:
        context.user_data.update({'pending_fecha': fecha_parseada, 'awaiting_custom_date': False})
        last_id = context.user_data.get('last_menu_msg_id')
        if last_id:
            try:
                target = await context.bot.get_message(chat_id=chat_id, message_id=last_id)
                await render_confirmation_screen(target, context)
                return
            except Exception: pass
        await render_confirmation_screen(update, context)
    else:
        txt_err_fec = traducciones.get('06_bot_error_fecha_inv', "⚠️ Formato de fecha inválido. Ingrese nuevamente (Ej: `2026-08-15` o `15/08`):")
        msg_err = await update.message.reply_text(txt_err_fec, parse_mode="Markdown")
        context.user_data['msg_solicitud_fecha_id'] = msg_err.message_id

async def _sub_manejar_edicion_item(update, context, raw_text, chat_id):
    item_index = context.user_data.get('editing_item_idx')
    items = context.user_data.get('pending_items', [])
    momento_actual = context.user_data.get('pending_momento', 'Comida')
    
    if not items or item_index is None or item_index < 0 or item_index >= len(items):
        context.user_data.pop('awaiting_edit_item_val', None)
        context.user_data.pop('editing_item_idx', None)
        return

    item_actual = items[item_index]
    es_plantilla = item_actual.get('es_plantilla', False)
    es_solo_numero = False
    
    try:
        nuevo_valor = float(raw_text.replace(',', '.').strip())
        es_solo_numero = True
    except ValueError:
        pass

    try: await update.message.delete()
    except: pass

    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    
    def_comida_text = traducciones.get('06_bot_def_comida', 'Comida')

    if es_solo_numero:
        if momento_actual == 'Actividad':
            # --- SOLUCIÓN 1 Y 2: REEMPLAZO DIRECTO Y TOPE PARA ACTIVIDADES ---
            if nuevo_valor > 1000:
                txt_exceso = traducciones.get(
                    "06_bot_act_limite_superado",
                    "⚠️ **Límite de actividad superado**\n\nEl gasto energético ingresado supera el límite máximo permitido por registro (1.000 kcal)."
                ).replace('\\n', '\n')
                msg = await context.bot.send_message(chat_id=chat_id, text=txt_exceso, parse_mode="Markdown")
                await asyncio.sleep(4)
                try: await msg.delete()
                except: pass
                return  # Cortamos acá para que el usuario ingrese un número lógico

            item_actual['calorias'] = -abs(nuevo_valor)
            item_actual['peso'] = 0
            item_actual['proteinas'] = 0
            item_actual['grasas'] = 0
            item_actual['carbohidratos'] = 0
            item_actual['fibras'] = 0
            
        elif es_plantilla:
            mult = nuevo_valor
            
            # --- TOPE DE SEGURIDAD PARA COMIDAS (PLANTILLAS) ---
            if item_actual.get('cal_base', 0) * mult > 2200:
                txt_exceso = traducciones.get("06_bot_comida_limite_superado", "⚠️ **Cantidad excesiva detectada**\n\nEl registro supera el límite razonable (2.200 kcal).").replace('\\n', '\n')
                msg = await context.bot.send_message(chat_id=chat_id, text=txt_exceso, parse_mode="Markdown")
                await asyncio.sleep(4)
                try: await msg.delete()
                except: pass
                return
            
            desc_base = item_actual.get('desc_base', def_comida_text)
            mult_str = f"{int(mult)}" if mult.is_integer() else f"{mult}"
            descripcion_final = f"{desc_base} x {mult_str}"
            
            item_actual['alimento'] = descripcion_final
            item_actual['alimento_display'] = descripcion_final
            item_actual['peso'] = item_actual.get('peso_base', 0) * mult
            item_actual['calorias'] = item_actual.get('cal_base', 0) * mult
            item_actual['proteinas'] = item_actual.get('prot_base', 0) * mult
            item_actual['grasas'] = item_actual.get('gras_base', 0) * mult
            item_actual['carbohidratos'] = item_actual.get('carb_base', 0) * mult
            item_actual['fibras'] = item_actual.get('fibr_base', 0) * mult
        else:
            peso_anterior = float(item_actual.get('peso', 1))
            if peso_anterior <= 0: peso_anterior = 1.0
            factor = nuevo_valor / peso_anterior
            
            # --- TOPE DE SEGURIDAD PARA COMIDAS (POR GRAMOS) ---
            if float(item_actual.get('calorias', 0)) * factor > 2200:
                txt_exceso = traducciones.get("06_bot_comida_limite_superado", "⚠️ **Cantidad excesiva detectada**\n\nEl registro supera el límite razonable (2.200 kcal).").replace('\\n', '\n')
                msg = await context.bot.send_message(chat_id=chat_id, text=txt_exceso, parse_mode="Markdown")
                await asyncio.sleep(4)
                try: await msg.delete()
                except: pass
                return

            item_actual['peso'] = nuevo_valor
            item_actual['calorias'] = float(item_actual.get('calorias', 0)) * factor
            item_actual['proteinas'] = float(item_actual.get('proteinas', 0)) * factor
            item_actual['grasas'] = float(item_actual.get('grasas', 0)) * factor
            item_actual['carbohidratos'] = float(item_actual.get('carbohidratos', 0)) * factor
            item_actual['fibras'] = float(item_actual.get('fibras', 0)) * factor
        
        context.user_data['pending_items'][item_index] = item_actual
        context.user_data.pop('awaiting_edit_item_val', None)
        context.user_data.pop('editing_item_idx', None)
        await render_confirmation_screen(update, context)
    else:
        txt_reanalizando = traducciones.get("06_bot_reanalizando_desc_ia", "🤖 Re-analizando descripción con IA...")
        msg_analizando = await update.message.reply_text(txt_reanalizando)
        try:
            data = await analizar_con_ia(raw_text, user_id)
            nuevos_items = data.get("items", [])
            if nuevos_items:
                nuevo_item = nuevos_items[0]
                item_actual['alimento'] = nuevo_item.get('alimento', raw_text)
                item_actual['alimento_display'] = nuevo_item.get('alimento', raw_text)
                item_actual['peso'] = float(nuevo_item.get('peso', 0))
                item_actual['calorias'] = float(nuevo_item.get('calorias', 0))
                item_actual['proteinas'] = float(nuevo_item.get('proteinas', 0))
                item_actual['grasas'] = float(nuevo_item.get('grasas', 0))
                item_actual['carbohidratos'] = float(nuevo_item.get('carbohidratos', 0))
                item_actual['fibras'] = float(nuevo_item.get('fibras', 0))
                context.user_data['pending_items'][item_index] = item_actual
            
            context.user_data.pop('awaiting_edit_item_val', None)
            context.user_data.pop('editing_item_idx', None)
            try: await msg_analizando.delete()
            except: pass
            await render_confirmation_screen(update, context)
            
        except Exception as e:
            txt_err = traducciones.get("06_bot_err_reanalizar", "❌ Error al re-analizar: {e}").format(e=e)
            await msg_analizando.edit_text(txt_err)
            context.user_data.pop('awaiting_edit_item_val', None)
            context.user_data.pop('editing_item_idx', None)
                                    
async def _sub_manejar_plantilla_comida(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_text, user_id):
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    contenido = raw_text[1:].strip()
    partes = [p.strip() for p in contenido.split(',')]
    nombre_plantilla = partes[0].upper()
    mult = float(partes[1]) if len(partes) > 1 else 1.0

    plantillas = obtener_comidas_usuario(user_id)
    plantilla = next((p for p in plantillas if str(p.get('Nombre', '')).strip().upper() == nombre_plantilla), None)

    if plantilla:
        p_b, c_b, pr_b, g_b, cb_b, f_b = plantilla.get('Peso', 0), plantilla.get('Calorias', 0), plantilla.get('Proteinas', 0), plantilla.get('Grasas', 0), plantilla.get('Carbohidratos', 0), plantilla.get('Fibras', 0)
        
        def_comida_text = traducciones.get('06_bot_def_comida', 'Comida')
        desc_limpia = (plantilla.get('Descripcion') or plantilla.get('Nombre', def_comida_text)).replace('§', '').strip()
        mult_str = f"{int(mult)}" if mult.is_integer() else f"{mult}"
        
        descripcion_final = f"{desc_limpia} x {mult_str}"
        
        item_gen = {
            "alimento": descripcion_final, 
            "alimento_display": descripcion_final,
            "peso": p_b * mult, 
            "calorias": c_b * mult, 
            "proteinas": pr_b * mult,
            "grasas": g_b * mult, 
            "carbohidratos": cb_b * mult, 
            "fibras": f_b * mult,
            # Etiquetas internas ocultas para edición:
            "es_plantilla": True,
            "desc_base": desc_limpia,
            "peso_base": p_b,
            "cal_base": c_b,
            "prot_base": pr_b,
            "gras_base": g_b,
            "carb_base": cb_b,
            "fibr_base": f_b
        }
        
        txt_proc = traducciones.get('06_bot_proc_comida', "⏳ Procesando comida predeterminada...")
        msg = await update.message.reply_text(txt_proc)
        await procesar_y_mostrar_confirmacion({"items": [item_gen], "tipo": "Comida"}, msg, context)
    else:
        # Buscamos la traducción y si no existe, usamos un texto por defecto seguro
        mensaje_base = traducciones.get('06_bot_error_comida_no_enc')
        if not mensaje_base or not str(mensaje_base).strip():
            mensaje_base = "❌ No se encontró la comida `*{nombre}` en tu planilla `Comidas_{user_id}`."
            
        try:
            txt_err_noenc = mensaje_base.format(nombre=nombre_plantilla, user_id=user_id)
        except Exception:
            txt_err_noenc = f"❌ No se encontró la comida `*{nombre_plantilla}` en tu planilla `Comidas_{user_id}`."
            
        await update.message.reply_text(txt_err_noenc, parse_mode="Markdown")
        
def parsear_fecha_flexible(raw_text):
    txt = str(raw_text).replace('/', '-').replace('.', '-').strip()
    partes = txt.split('-')
    try:
        ahora = obtener_ahora_arg()
        if len(partes) == 3:
            if len(partes[0]) == 4: return f"{int(partes[0]):04d}-{int(partes[1]):02d}-{int(partes[2]):02d}"
            return f"{int(partes[2]):04d}-{int(partes[1]):02d}-{int(partes[0]):02d}"
        elif len(partes) == 2:
            return f"{ahora.year:04d}-{int(partes[1]):02d}-{int(partes[0]):02d}"
        elif len(partes) == 1 and partes[0].isdigit():
            return f"{ahora.year:04d}-{ahora.month:02d}-{int(partes[0]):02d}"
    except Exception: pass
    return None
    
async def _sub_manejar_voz_ingesta(update, context, transcription, msg):
    user_id = update.effective_user.id
    try:
        data = await analizar_con_ia(transcription, user_id)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        lang = obtener_idioma_usuario(user_id) or 'es'
        traducciones = obtener_traducciones_db(lang) or {}
        txt_err_aud = traducciones.get('06_bot_error_audio', "❌ Error al procesar el audio con IA: {e}").format(e=e)
        logger.error(f"Error procesando voz de ingesta: {e}")
        await msg.edit_text(txt_err_aud)

async def _sub_manejar_voz_actividad(update, context, transcription, msg):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    context.user_data['awaiting_activity_voice'] = False
    perfil_biometrico = obtener_perfil_usuario(user_id)
    
    prompt_ia = f"El usuario realizó una actividad física descrita por voz. Transcripción: '{transcription}'. Calcula las calorías gastadas utilizando estrictamente su perfil biométrico: {perfil_biometrico}. Devolvé un JSON con los campos 'alimento' y 'calorias'."
    
    try:
        resultado_ia = await analizar_con_ia(prompt_ia, user_id)
    except Exception as e:
        txt_err = traducciones.get("06_bot_err_procesar_act_fisica", "❌ Error al procesar la actividad física: {e}").format(e=e)
        await msg.edit_text(txt_err)
        return

    items_ia = resultado_ia.get('items', [])
    kcal_estimadas = float(items_ia[0].get('calorias', 0)) if items_ia else 0.0
    desc = str(items_ia[0].get('alimento', transcription)) if items_ia else transcription
    
    item_actividad = {"alimento": desc, "peso": 0, "calorias": -abs(kcal_estimadas), "proteinas": 0, "grasas": 0, "carbohidratos": 0, "fibras": 0}
    context.user_data.update({'pending_items': [item_actividad], 'pending_fecha': obtener_ahora_arg().strftime("%Y-%m-%d"), 'pending_momento': 'Actividad'})

    try: await msg.delete()
    except: pass

    txt_act_aud = traducciones.get('06_bot_act_audio', "📋 Actividad analizada por audio:")
    msg_menu = await update.message.reply_text(txt_act_aud)
    context.user_data['last_menu_msg_id'] = msg_menu.message_id
    await render_confirmation_screen(msg_menu, context)

#                INICIO                                      FUNCIONES BOTONES                        FINAL
# ======================================================================================================================================

@requiere_registro
async def callback_btn_momento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['last_menu_msg_id'] = query.message.message_id
    context.user_data['pending_momento'] = query.data.replace("set_m_", "")
    await render_confirmation_screen(query, context)
     
@requiere_registro
async def callback_btn_editar_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    context.user_data['last_menu_msg_id'] = query.message.message_id

    idx = int(data.replace("edit_item_", "")) - 1
    context.user_data.update({'awaiting_edit_item_val': True, 'editing_item_idx': idx})
    
    momento_actual = context.user_data.get('pending_momento', 'Comida')
    items = context.user_data.get('pending_items', [])
    
    es_codigo_barras = (0 <= idx < len(items) and items[idx].get('fuente') == "Open Food Facts")
    es_plantilla = (0 <= idx < len(items) and items[idx].get('es_plantilla') == True)

    if momento_actual == 'Actividad':
        txt_ed_kcal = traducciones.get('06_bot_edit_calorias', "✏️ Ingresá el nuevo valor de calorías para la actividad (ej: `220`):")
        await query.message.reply_text(txt_ed_kcal, parse_mode="Markdown")
    elif es_codigo_barras:
        txt_ed_peso = traducciones.get('06_bot_edit_peso_gr', "⚖️ Ingresá el **nuevo peso en gramos** para este producto (ej: `150`):")
        await query.message.reply_text(txt_ed_peso, parse_mode="Markdown")
    elif es_plantilla:
        txt_ed_plantilla = traducciones.get('06_bot_edit_unidades', "✏️ Ingresá la **nueva cantidad de unidades** (ej: `2` o `1.5`):")
        await query.message.reply_text(txt_ed_plantilla, parse_mode="Markdown")
    else:
        txt_ed_gen = traducciones.get('06_bot_edit_desc_peso', "✏️ Ingresá la nueva descripción y/o peso para este alimento:")
        await query.message.reply_text(txt_ed_gen)
        
@requiere_registro
async def callback_btn_anular_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    context.user_data['last_menu_msg_id'] = query.message.message_id

    idx = int(data.replace("del_item_", "")) - 1
    items = context.user_data.get('pending_items', [])
    if 0 <= idx < len(items):
        items.pop(idx)
    
    if not items:
        txt_all_del = traducciones.get('06_bot_all_del', "❌ Todos los ítems fueron eliminados.")
        await query.edit_message_text(txt_all_del)
        context.user_data.pop('last_menu_msg_id', None)
    else:
        await render_confirmation_screen(query, context)

@requiere_registro
async def callback_btn_cancelar_registro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    context.user_data.pop('pending_items', None)
    context.user_data.pop('last_menu_msg_id', None)
    txt_canc = traducciones.get('06_bot_reg_canc', "🗑️ Registro cancelado.")
    await query.edit_message_text(txt_canc)

async def callback_btn_guardar_registro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    
    items = context.user_data.get('pending_items', [])
    fecha = context.user_data.get('pending_fecha')
    momento = context.user_data.get('pending_momento')
    
    momento_display = traducciones.get(f'06_bot_momento_{momento.lower()}', momento) if momento else ""

    if items and fecha and momento:
        tipo_registro = "Actividad" if momento == "Actividad" else "Comida"
        guardar_ingesta_db(user_id, items, fecha, momento, tipo=tipo_registro)

        # Limpiamos los datos pendientes inmediatamente después de guardar
        context.user_data.pop('pending_items', None)
        context.user_data.pop('last_menu_msg_id', None)

        if momento == "Actividad":
            plantilla = traducciones.get('06_bot_save_act_exito', "✅ **¡Actividad guardada exitosamente!**\n📅 `{fecha}`")
            try:
                txt_conf = plantilla.format(fecha=fecha).replace('\\n', '\n')
            except Exception:
                txt_conf = f"✅ **¡Actividad guardada exitosamente!**\n📅 `{fecha}`"
        else:
            plantilla = traducciones.get('06_bot_save_meal_exito', "✅ **¡Ingesta guardada exitosamente!**\n📅 `{fecha}` | `{momento_display}`")
            try:
                txt_conf = plantilla.format(fecha=fecha, momento_display=momento_display, momento=momento_display).replace('\\n', '\n')
            except Exception:
                txt_conf = f"✅ **¡Ingesta guardada exitosamente!**\n📅 `{fecha}` | `{momento_display}`"

        try:
            # Al editar el texto sin pasar reply_markup, borra los botones y muestra el aviso
            await query.edit_message_text(txt_conf, parse_mode="Markdown")
        except Exception:
            # Respaldo en texto plano por si algún símbolo rompe el Markdown
            await query.edit_message_text(txt_conf.replace('*', '').replace('`', ''))
    else:
        txt_nodat = traducciones.get('06_bot_no_data', "❌ No se encontraron datos para guardar.")
        await query.edit_message_text(txt_nodat)


# ======================================================================================================================================
#                    FINAL                 COMANDOS CONFIRMACION FUNCIONES BOTONES                     FINAL
# ======================================================================================================================================


