
#                                 INICIO                                   CABECERA 2026 09 05                                    INICIO
#                                  https://github.com/rosalexxi/telegram-bot-nutricion
#                                  https://dashboard.render.com/web/srv-d9lcifijnfac73a8q1eg/events
#                                  https://supabase.com/dashboard/project/xsheilmjewqcvhmyqlnx/editor/17944?schema=public
#                                  https://dashboard.uptimerobot.com/monitors
# ==============================================================================================================================================

import os
import re
import io
import json
import base64
import threading
import inspect
import logging
import unicodedata
import asyncio
import psycopg2  
import sys
import pytz
import pandas as pd
import gspread
import html  
import cv2
import numpy as np
import requests
import math
import urllib.request
import urllib.parse
import calendar

from deep_translator import GoogleTranslator
from openai import OpenAI
from typing import Dict, Tuple, List, Optional, Any            
from urllib.parse import urlparse 
from datetime import datetime, date, timedelta, time
from google.oauth2.service_account import Credentials
from groq import Groq

from flask import Flask, request, jsonify, render_template_string, send_from_directory, url_for
from functools import wraps
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
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

# Inicialización segura de OpenAI luego de cargar las variables de entorno
client = OpenAI() if os.getenv("OPENAI_API_KEY") else None

# Definición de franjas horarias (sin tildes)
FRANJAS_COMIDAS = {
    "Desayuno": (8, 11),
    "Almuerzo": (11, 16),
    "Merienda": (16, 20),
    "Cena": (20, 24)
}

# Estados de conversación para Perfil y Fecha personalizada
AWAITING_PROFILE_DATA, AWAITING_CUSTOM_DATE, AWAITING_RESUMEN_MES, AWAITING_EDIT_ITEM = range(4)

GROQ_TEXTO      = "openai/gpt-oss-120b"   # Generación principal
GROQ_FOTO       = "qwen/qwen3.8-27b"
GROQ_AUDIO      = "whisper-large-v3"

GROQ_REVISION_2 = "openai/gpt-oss-20b"    # Revisión principal
GROQ_REVISOR    = "qwen/qwen3.8-27b"      # Respaldo

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_SHEETS_KEY_PATH = os.getenv("GOOGLE_SHEETS_KEY_PATH", "credentials.json")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "Registro_Nutricional_Bot")
ARG_TZ = pytz.timezone('America/Argentina/Buenos_Aires')

# Patrón para detectar variables entre llaves
PATTERN_VARS = re.compile(r'\{[^}]+\}')

ADMIN_USER_ID = "7363062724"  # Reemplazá esto por tu número de ID de Telegram real

# 1. ESTADOS DE CONVERSACIÓN ACTUALIZADOS
ING_TERMINOS, ING_IDIOMA, ING_PROFESIONAL, ING_NOMBRE, ING_EDAD, ING_SEXO, ING_ALTURA, ING_PESO, ING_MUNECA, ING_CUELLO, ING_CADERA, ING_OCUPACION, ING_CUMPLE, ING_RITMO = range(10, 24)

if GROQ_API_KEY:
    client_ai = Groq(api_key=GROQ_API_KEY)
else:
    client_ai = None

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

# =====================================================================================================================================
#              INICIO                                  PAGINA WEB (CALCULADORA UNICA)                        INICIO  DB OK
# ======================================================================================================================================

HTML_CALCULADORA_RECETAS = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title id="title-app" data-var="_02_titulo_web">IA NutriBot</title>
    <style>
        :root {
            --primary: #27ae60;
            --primary-dark: #219150;
            --secondary: #2c3e50;
            --bg-light: #f4f6f9;
            --text-color: #2c3e50;
        }
        
        html, body { 
            min-height: 100dvh; 
            margin: 0; 
            padding: 0; 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            color: var(--text-color); 
            display: flex;
            flex-direction: column;
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            background-blend-mode: overlay;
            background-color: rgba(244, 246, 249, 0.85);
            transition: background-image 1.5s ease-in-out;
        }
        
        header { 
            background: rgba(255, 255, 255, 0.92); 
            backdrop-filter: blur(8px);
            box-shadow: 0 2px 8px rgba(0,0,0,0.06); 
            position: sticky;
            top: 0;
            z-index: 1000; 
            padding: 8px 15px;
        }
        .nav-container { max-width: 1100px; margin: auto; display: flex; flex-direction: column; gap: 6px; }
        
        /* Primer renglón: Logo y Títulos de navegación centrados */
        .nav-top-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
        .logo { font-size: 1.2rem; font-weight: bold; color: var(--primary); text-decoration: none; cursor: pointer; display: flex; align-items: center; gap: 5px; }
        
        .nav-links { display: flex; justify-content: center; align-items: center; gap: 8px; flex-wrap: wrap; flex: 1; }
        .nav-links a { text-decoration: none; color: var(--secondary); font-weight: 600; font-size: 0.8rem; transition: color 0.2s; cursor: pointer; padding: 4px 8px; border-radius: 4px; }
        .nav-links a:hover, .nav-links a.active { color: white; background-color: var(--primary); }

        /* Segundo renglón: Banderas 3D alineadas a la derecha */
        .nav-bottom-row { display: flex; justify-content: flex-end; align-items: center; gap: 8px; border-top: 1px solid rgba(0,0,0,0.06); padding-top: 6px; }
        .flag-btn { 
            background: transparent; 
            border: 2px solid transparent; 
            border-radius: 6px; 
            padding: 2px; 
            cursor: pointer; 
            text-decoration: none; 
            display: inline-flex; 
            align-items: center; 
            justify-content: center;
            transition: all 0.2s ease; 
        }
        .flag-btn:hover, .flag-btn.active-flag { 
            border-color: var(--primary); 
            background: rgba(39, 174, 96, 0.1); 
            transform: scale(1.12); 
        }
        .flag-icon-img {
            width: 34px;
            height: 24px;
            object-fit: contain;
            display: block;
            filter: drop-shadow(0 2px 3px rgba(0,0,0,0.2));
        }

        .content-wrapper { 
            max-width: 950px; 
            margin: 20px auto; 
            background: rgba(255, 255, 255, 0.40); 
            backdrop-filter: blur(6px);
            -webkit-backdrop-filter: blur(6px);
            padding: 25px; 
            border-radius: 12px; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.08); 
            border: 1px solid rgba(255, 255, 255, 0.4);
            width: 90%; 
            box-sizing: border-box; 
            flex: 1;
        }

        .content-box { 
            background: rgba(255, 255, 255, 0.55); 
            border: 1px solid rgba(226, 232, 240, 0.8); 
            border-radius: 8px; 
            padding: 22px; 
            margin-top: 15px; 
            box-shadow: 0 2px 6px rgba(0,0,0,0.02); 
        }

        h1 { color: var(--secondary); margin-top: 0; font-size: 1.5rem; margin-bottom: 12px; border-bottom: 2px solid var(--primary); padding-bottom: 6px; display: inline-block; }
        h2, h3 { color: var(--secondary); }
        p, li { color: #333; font-size: 0.95rem; line-height: 1.6; text-align: justify; }

        .article-content { overflow: hidden; }
        .newspaper-img {
            float: left; 
            width: 40%; 
            margin-right: 20px; 
            margin-bottom: 10px;
            background-color: rgba(248, 250, 252, 0.8);
            border: 2px dashed #cbd5e1;
            border-radius: 8px;
            padding: 6px;
            box-sizing: border-box;
        }
        .newspaper-img img {
            width: 100%;
            aspect-ratio: 4 / 3; 
            object-fit: cover;
            border-radius: 4px;
            display: block;
        }
        .img-caption {
            font-size: 0.75rem;
            color: #666;
            text-align: center;
            margin-top: 5px;
            font-style: italic;
        }

        .section-content { display: none; }
        .section-content.active { display: block; }

        .calculator-section { margin-top: 5px; }
        label { font-weight: bold; display: block; margin-top: 8px; margin-bottom: 2px; font-size: 0.85rem; color: #2c3e50; }
        
        input[type="text"], input[type="number"], select, textarea { 
            width: 100%; 
            padding: 8px; 
            border: 1px solid #cbd5e1; 
            border-radius: 4px; 
            box-sizing: border-box; 
            font-size: 0.85rem; 
            color: #333;
            background: rgba(255, 255, 255, 0.85);
        }
        textarea { height: 80px; resize: vertical; }
        
        .row { display: flex; gap: 10px; }
        .col { flex: 1; }
        
        button.calc-btn { background-color: var(--primary); color: white; padding: 10px; border: none; border-radius: 4px; width: 100%; font-size: 0.9rem; font-weight: bold; cursor: pointer; margin-top: 12px; }
        button.calc-btn:hover { background-color: var(--primary-dark); }
        
        #loading { display: none; text-align: center; margin-top: 8px; font-style: italic; color: #7f8c8d; font-size: 0.85rem; }
        #resultado-section { display: none; margin-top: 15px; border-top: 2px solid rgba(0,0,0,0.1); padding-top: 8px; }
        
        table.calc-tbl { width: 100%; border-collapse: collapse; margin-top: 6px; }
        table.calc-tbl th, table.calc-tbl td { border: 1px solid #cbd5e1; padding: 6px; text-align: center; vertical-align: middle; background: rgba(255, 255, 255, 0.6); }
        table.calc-tbl th { background-color: rgba(241, 245, 249, 0.9); font-weight: bold; font-size: 0.8rem; color: #1e293b; }
        
        table.calc-tbl tr.total-row { background-color: rgba(230, 244, 234, 0.9); font-weight: bold; font-size: 0.85rem; color: #065f46; }
        
        .editable-cell {
            width: 100%;
            padding: 4px;
            border: 1px solid transparent;
            background: transparent;
            text-align: center;
            font-size: 0.8rem;
            color: #1e293b;
            border-radius: 3px;
        }
        .editable-cell:hover, .editable-cell:focus {
            border-color: var(--primary);
            background: rgba(255, 255, 255, 0.95);
            outline: none;
        }

        .btn-save { background-color: #8e44ad; margin-top: 10px; color: white; padding: 10px; border: none; border-radius: 4px; width: 100%; font-weight: bold; cursor: pointer; font-size: 0.85rem; }
        .btn-save:hover { background-color: #71368a; }
        .btn-copy { background-color: #2980b9; margin-top: 6px; color: white; padding: 10px; border: none; border-radius: 4px; width: 100%; font-weight: bold; cursor: pointer; font-size: 0.85rem; }
        .btn-copy:hover { background-color: #1f6391; }
        
        .user-badge { background: rgba(224, 242, 254, 0.9); color: #0369a1; padding: 6px 10px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; display: inline-block; margin-bottom: 10px; }

        footer { 
            background: rgba(44, 62, 80, 0.92); 
            backdrop-filter: blur(5px);
            color: white; 
            text-align: center; 
            padding: 15px 20px 30px 20px; 
            flex-shrink: 0;
            font-size: 0.8rem; 
            margin-top: auto;
        }
        .footer-links { 
            margin-bottom: 10px; 
            display: flex; 
            flex-wrap: wrap; 
            justify-content: flex-start; 
            align-items: center;
            gap: 12px; 
        }
        .footer-link { 
            color: white; 
            text-decoration: none; 
            padding: 6px; 
            background: rgba(255,255,255,0.10); 
            border-radius: 8px; 
            transition: all 0.2s ease; 
            display: inline-flex; 
            align-items: center;
            justify-content: center;
            cursor: pointer; 
        }
        .footer-link:hover { 
            background: rgba(255,255,255,0.25); 
            transform: translateY(-2px) scale(1.08);
        }
        .footer-icon-img {
            width: 38px;
            height: 38px;
            object-fit: contain;
            display: block;
            filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
        }
        .footer-info { opacity: 0.85; font-size: 0.75rem; text-align: left; margin-top: 5px; }
    </style>
</head>
<body>

<div id="loadingLang" data-var="_02_loading_lang" style="display:none; position:fixed; top:20px; right:20px; background:#2c3e50; color:white; padding:10px 15px; border-radius:8px; z-index:9999; font-size:0.85rem; box-shadow: 0 4px 10px rgba(0,0,0,0.2);">
    ⏳ Cargando idioma...
</div>

<header>
    <div class="nav-container">
        <!-- Primer Renglón: Logo y Títulos de Secciones Centrados -->
        <div class="nav-top-row">
            <a class="logo" onclick="showSection('inicio')"><span data-var="_02_logo">🤖 IA NutriBot</span></a>
            <div class="nav-links">
                <a id="nav-inicio" onclick="showSection('inicio')" class="active" data-var="_02_menu_inicio">Inicio</a>
                <a id="nav-ingreso" onclick="showSection('ingreso')" data-var="_02_menu_ingreso">Ingreso</a>
                <a id="nav-alta" onclick="showSection('alta')" data-var="_02_menu_alta">Alta</a>
                <a id="nav-comandos" onclick="showSection('comandos')" data-var="_02_menu_comandos">Comandos</a>
                <a id="nav-faq" onclick="showSection('faq')" data-var="_02_menu_faq">FAQ</a>
                {% if user_id %}
                <a id="nav-calculadora" onclick="showSection('calculadora')" data-var="_02_menu_calculadora">Calculadora</a>
                {% endif %}
            </div>
        </div>
        <!-- Segundo Renglón: Banderas 3D alineadas a la derecha -->
        <div class="nav-bottom-row">
            <div id="langFlagsContainer" class="lang-flags-container" style="display: flex; gap: 8px; flex-wrap: wrap;"></div>
        </div>
    </div>
</header>

<div class="content-wrapper">

    <!-- Sección 1: Inicio -->
    <div id="section-inicio" class="section-content active">
        <h1 data-var="_02_titulo_inicio"></h1>
        <div class="content-box">
            <div class="article-content">
                <div class="newspaper-img">
                    <img src="{{ url_for('static', filename='foto1.png') }}" alt="Inicio" onerror="this.style.display='none'">
                    <div class="img-caption" data-var="_02_cap_inicio"></div>
                </div>
                <div data-var="_02_texto_inicio"></div>
            </div>
        </div>
    </div>

    <!-- Sección 2: Ingreso -->
    <div id="section-ingreso" class="section-content">
        <h1 data-var="_02_titulo_ingreso"></h1>
        <div class="content-box">
            <div class="article-content">
                <div class="newspaper-img">
                    <img src="{{ url_for('static', filename='foto3.png') }}" alt="Ingreso" onerror="this.style.display='none'">
                    <div class="img-caption" data-var="_02_cap_ingreso"></div>
                </div>
                <div data-var="_02_texto_ingreso"></div>
            </div>
        </div>
    </div>

    <!-- Sección 3: Alta -->
    <div id="section-alta" class="section-content">
        <h1 data-var="_02_titulo_alta"></h1>
        <div class="content-box">
            <div class="article-content">
                <div class="newspaper-img">
                    <img src="{{ url_for('static', filename='foto2.png') }}" alt="Alta" onerror="this.style.display='none'">
                    <div class="img-caption" data-var="_02_cap_alta"></div>
                </div>
                <div data-var="_02_texto_alta"></div>
            </div>
        </div>
    </div>

    <!-- Sección 4: Comandos -->
    <div id="section-comandos" class="section-content">
        <h1 data-var="_02_titulo_comandos"></h1>
        <div class="content-box">
            <div class="article-content">
                <div class="newspaper-img">
                    <img src="{{ url_for('static', filename='foto4.png') }}" alt="Comandos" onerror="this.style.display='none'">
                    <div class="img-caption" data-var="_02_cap_comandos"></div>
                </div>
                <div data-var="_02_texto_comandos"></div>
            </div>
        </div>
    </div>

    <!-- Sección 5: FAQ -->
    <div id="section-faq" class="section-content">
        <h1 data-var="_02_titulo_faq"></h1>
        <div class="content-box">
            <div data-var="_02_texto_faq"></div>
        </div>
    </div>

    <!-- Sección Calculadora Web -->
    {% if user_id %}
    <div id="section-calculadora" class="section-content">
        <div class="calculator-section">
            <h2 data-var="_02_titulo_calc">Calculadora Web</h2>
            <p data-var="_02_desc_calc">Herramienta avanzada para registrar y calcular recetas.</p>

            <div class="user-badge"><span data-var="_02_user_conectado">Usuario Conectado</span>: {{ user_id }}</div>
            
            <div class="row">
                <div class="col" style="flex: 0.4;">
                    <label for="codigo"><span data-var="_02_label_codigo">Código</span>:</label>
                    <input type="text" id="codigo" data-placeholder="_02_ph_codigo" placeholder="Ej: PASCUALINAP" style="text-transform: uppercase;" oninput="this.value = this.value.toUpperCase()">
                </div>
                <div class="col">
                    <label for="descripcion"><span data-var="_02_label_descripcion">Descripción</span>:</label>
                    <input type="text" id="descripcion" data-placeholder="_02_ph_descripcion" placeholder="Ej: Porción de pascualina de atún">
                </div>
            </div>

            <label for="recetaText"><span data-var="_02_label_ingredientes">Ingredientes y Cantidad</span>:</label>
            <textarea id="recetaText" data-placeholder="_02_ph_ingredientes" placeholder="Ej:&#10;1 kg de harina&#10;6 huevos&#10;200 g de manteca"></textarea>

            <div class="row">
                <div class="col">
                    <label for="tipoCalculo"><span data-var="_02_label_criterio">Criterio de División</span>:</label>
                    <select id="tipoCalculo" onchange="toggleCriterio()">
                        <option value="porciones" data-var="_02_opt_porciones">Porciones</option>
                        <option value="gramos" data-var="_02_opt_gramos">Gramos Totales</option>
                    </select>
                </div>
                <div class="col" id="colPorciones">
                    <label for="porciones"><span data-var="_02_label_porciones">Porciones</span>:</label>
                    <input type="number" id="porciones" value="1" min="1">
                </div>
            </div>

            <button class="calc-btn" onclick="calcularReceta()"><span data-var="_02_btn_calcular">✨ Calcular Fila con IA</span></button>

            <div id="loading" data-var="_02_loading_ia">Calculando macronutrientes...</div>

            <div id="resultado-section">
                <div style="overflow-x: auto;">
                    <table class="calc-tbl" id="tablaNutricional">
                        <thead>
                            <tr>
                                <th data-var="_02_th_nombre">Nombre</th>
                                <th data-var="_02_th_peso">⚖️ Peso (g)</th>
                                <th data-var="_02_th_calorias">🔥 Calorías</th>
                                <th data-var="_02_th_proteinas">🥩 Proteínas</th>
                                <th data-var="_02_th_grasas">🥑 Grasas</th>
                                <th data-var="_02_th_carbohidratos">🍞 Carbos</th>
                                <th data-var="_02_th_fibras">🌾 Fibras</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                        <tfoot>
                            <tr class="total-row" id="filaTotales">
                                <td><span data-var="_02_th_totales">Totales</span></td>
                                <td id="totPeso">0</td>
                                <td id="totCal">0</td>
                                <td id="totProt">0</td>
                                <td id="totGras">0</td>
                                <td id="totCarb">0</td>
                                <td id="totFibr">0</td>
                            </tr>
                        </tfoot>
                    </table>
                </div>

                <button class="btn-save" onclick="guardarEnGoogleSheets()"><span data-var="_02_btn_guardar">💾 Guardar Directamente en Planilla</span></button>
                <button class="btn-copy" onclick="copiarFilaExcel()"><span data-var="_02_btn_copiar">📋 Copiar Fila para Excel</span></button>
            </div>
        </div>
    </div>
    {% endif %}

</div>

<footer>
    <!-- Footer con imágenes PNG grandes alineadas a la izquierda -->
    <div class="footer-links">
        <a onclick="reproducirAudioguia()" class="footer-link" data-title="_02_title_audioguia" title="Audioguía">
            <img src="{{ url_for('static', filename='audioguia.png') }}" alt="Audioguía" class="footer-icon-img">
        </a>
        <a id="linkManual" href="#" target="_blank" class="footer-link" data-title="_02_title_manual" title="Manual (PDF)">
            <img src="{{ url_for('static', filename='manual.png') }}" alt="Manual" class="footer-icon-img">
        </a>
        <a href="https://instagram.com/ianutribot" target="_blank" class="footer-link" title="Instagram">
            <img src="{{ url_for('static', filename='instagram.png') }}" alt="Instagram" class="footer-icon-img">
        </a>
        <a href="https://twitter.com/ianutribot" target="_blank" class="footer-link" title="X (Twitter)">
            <img src="{{ url_for('static', filename='x.png') }}" alt="X" class="footer-icon-img">
        </a>
        <a href="https://tiktok.com/@ianutribot" target="_blank" class="footer-link" title="TikTok">
            <img src="{{ url_for('static', filename='tiktok.png') }}" alt="TikTok" class="footer-icon-img">
        </a>
        <a href="https://facebook.com/ianutribot" target="_blank" class="footer-link" title="Facebook">
            <img src="{{ url_for('static', filename='facebook.png') }}" alt="Facebook" class="footer-icon-img">
        </a>
        <a href="https://youtube.com/@ianutribot" target="_blank" class="footer-link" title="YouTube">
            <img src="{{ url_for('static', filename='youtube.png') }}" alt="YouTube" class="footer-icon-img">
        </a>
        <a href="mailto:ianutribot@gmail.com" class="footer-link" title="Mail">
            <img src="{{ url_for('static', filename='mail.png') }}" alt="Mail" class="footer-icon-img">
        </a>
    </div>
    <div class="footer-info" data-var="_02_footer_rights">© 2026 IA NutriBot - Todos los derechos reservados.</div>
</footer>

<script>
    const fondosNutricion = [
        "https://images.unsplash.com/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=1920&q=80",
        "https://images.unsplash.com/photo-1498837167922-ddd27525d352?auto=format&fit=crop&w=1920&q=80",
        "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=1920&q=80",
        "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=1920&q=80",
        "https://images.unsplash.com/photo-1490645935967-10de6ba17061?auto=format&fit=crop&w=1920&q=80",
        "https://images.unsplash.com/photo-1505253716362-afaea1d3d1af?auto=format&fit=crop&w=1920&q=80"
    ];

    function aplicarFondoAleatorioRotativo() {
        const randomIndex = Math.floor(Math.random() * fondosNutricion.length);
        document.body.style.backgroundImage = `url('${fondosNutricion[randomIndex]}')`;
    }

    let idiomasDisponiblesGlobal = [];
    let traduccionesGlobal = {};
    let idiomaActual = 'es';
    let nombreLargoActual = 'Español';
    const currentUserId = "{{ user_id }}";
    let itemsDesglosadosGlobal = [];

    // Función auxiliar para traducir alertas y mensajes en JS con respaldo (fallback)
    function t(clave, fallback) {
        return (traduccionesGlobal && traduccionesGlobal[clave] !== undefined) ? traduccionesGlobal[clave] : fallback;
    }

    async function cargarBanderasIdiomas() {
        try {
            const res = await fetch('/api/config-idiomas');
            const data = await res.json();
            const container = document.getElementById('langFlagsContainer');
            container.innerHTML = '';
            
            if (data.idiomas && Array.isArray(data.idiomas)) {
                idiomasDisponiblesGlobal = data.idiomas;
                data.idiomas.forEach(langObj => {
                    const code = langObj.code.toLowerCase();
                    const btn = document.createElement('a');
                    btn.className = 'flag-btn';
                    btn.id = `flag-btn-${code}`;
                    btn.title = langObj.name;
                    btn.onclick = () => cambiarIdioma(code);

                    // Imagen PNG con las 2 letras del idioma (ej: /static/es.png)
                    const img = document.createElement('img');
                    img.src = `/static/${code}.png`;
                    img.alt = code.toUpperCase();
                    img.className = 'flag-icon-img';
                    // Si la imagen aún no está subida, muestra el emoji o las siglas como respaldo
                    img.onerror = function() {
                        this.style.display = 'none';
                        btn.innerText = langObj.flag || code.toUpperCase();
                    };

                    btn.appendChild(img);
                    container.appendChild(btn);
                });
            }
        } catch (e) {
            console.error("Error al cargar banderas de idiomas:", e);
        }
    }

    async function cambiarIdioma(lang) {
        const loadingBox = document.getElementById('loadingLang');
        if (loadingBox) loadingBox.style.display = 'block';

        try {
            idiomaActual = lang.toLowerCase();
            document.documentElement.lang = idiomaActual;

            // Resaltar bandera activa
            document.querySelectorAll('.flag-btn').forEach(b => b.classList.remove('active-flag'));
            const activeFlag = document.getElementById(`flag-btn-${idiomaActual}`);
            if (activeFlag) activeFlag.classList.add('active-flag');
            
            const objLang = idiomasDisponiblesGlobal.find(i => i.code.toLowerCase() === idiomaActual);
            if (objLang && objLang.name) {
                nombreLargoActual = objLang.name;
            }

            const response = await fetch(`/api/traducciones?lang=${idiomaActual}`);
            if (!response.ok) throw new Error("No se pudieron cargar las traducciones.");
            const traducciones = await response.json();
            traduccionesGlobal = traducciones;
            
            // 1. Traducir contenido HTML (data-var)
            document.querySelectorAll('[data-var]').forEach(el => {
                const clave = el.getAttribute('data-var');
                if (traducciones[clave] !== undefined) {
                    el.innerHTML = traducciones[clave];
                }
            });

            // 2. Traducir placeholders de inputs/textareas (data-placeholder)
            document.querySelectorAll('[data-placeholder]').forEach(el => {
                const clave = el.getAttribute('data-placeholder');
                if (traducciones[clave] !== undefined) {
                    el.placeholder = traducciones[clave];
                }
            });

            // 3. Traducir tooltips/titles (data-title)
            document.querySelectorAll('[data-title]').forEach(el => {
                const clave = el.getAttribute('data-title');
                if (traducciones[clave] !== undefined) {
                    el.title = traducciones[clave];
                }
            });

            const linkManual = document.getElementById('linkManual');
            if (linkManual) {
                linkManual.href = `/static/${idiomaActual}.pdf`;
            }
        } catch (err) {
            console.error("Error al cambiar idioma:", err);
        } finally {
            if (loadingBox) loadingBox.style.display = 'none';
        }
    }

    async function inicializarIdiomaWeb() {
        aplicarFondoAleatorioRotativo();
        setInterval(aplicarFondoAleatorioRotativo, 30000);

        await cargarBanderasIdiomas();

        const urlParams = new URLSearchParams(window.location.search);
        const userId = urlParams.get('user_id');

        if (userId) {
            try {
                const resUser = await fetch(`/api/usuario-idioma?user_id=${userId}`);
                const dataUser = await resUser.json();
                if (dataUser.lang) {
                    await cambiarIdioma(dataUser.lang);
                    return;
                }
            } catch (e) {
                console.error("Error al obtener idioma de usuario:", e);
            }
        }

        await cambiarIdioma('es');
    }

    window.addEventListener('DOMContentLoaded', () => {
        inicializarIdiomaWeb();
        if (window.location.hash === '#calculadora') {
            showSection('calculadora');
        }
    });

    async function reproducirAudioguia() {
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
            try {
                const response = await fetch(`/api/audioguia?lang=${idiomaActual}`);
                if (!response.ok) throw new Error(t('_02_err_audioguia', "No se pudo cargar la audioguía."));
                const data = await response.json();
                
                const utterance = new SpeechSynthesisUtterance(data.guia);
                utterance.lang = idiomaActual;
                utterance.rate = 1.0;
                window.speechSynthesis.speak(utterance);
            } catch (error) {
                alert(t('_02_err_audioguia', "Error al reproducir la audioguía:") + " " + error.message);
            }
        } else {
            alert(t('_02_err_no_speech', "Tu navegador no soporta la función de lectura de voz."));
        }
    }

    function showSection(sectionId) {
        document.querySelectorAll('.section-content').forEach(el => {
            el.classList.remove('active');
        });
        document.querySelectorAll('.nav-links a').forEach(el => {
            el.classList.remove('active');
        });
        
        const targetSection = document.getElementById('section-' + sectionId);
        const targetNav = document.getElementById('nav-' + sectionId);
        
        if (targetSection) targetSection.classList.add('active');
        if (targetNav) targetNav.classList.add('active');
        
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function toggleCriterio() {
        const tipo = document.getElementById('tipoCalculo').value;
        const colPorciones = document.getElementById('colPorciones');
        if (colPorciones) {
            colPorciones.style.display = (tipo === 'gramos') ? 'none' : 'block';
        }
    }

    async function calcularReceta() {
        if (!currentUserId) {
            alert(t('_02_err_no_registrado', "Acción no permitida para usuarios no registrados."));
            return;
        }

        const codigo = document.getElementById('codigo').value.trim();
        const descripcion = document.getElementById('descripcion').value.trim();
        const receta = document.getElementById('recetaText').value.trim();
        const tipoCalculo = document.getElementById('tipoCalculo').value;
        const porciones = document.getElementById('porciones').value;

        if (!codigo || !descripcion || !receta) {
            alert(t('_02_err_campos_vacios', "Por favor completa el código, la descripción y los ingredientes."));
            return;
        }

        document.getElementById('loading').style.display = 'block';
        document.getElementById('resultado-section').style.display = 'none';

        try {
            const response = await fetch('/api/calcular-receta', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    user_id: currentUserId,
                    lang: idiomaActual,
                    codigo, 
                    descripcion, 
                    receta, 
                    tipoCalculo, 
                    porciones: parseInt(porciones || 1) 
                })
            });

            const responseText = await response.text();
            if (responseText.trim().startsWith('<')) {
                alert(t('_02_err_servidor', "❌ El servidor falló") + " (HTTP " + response.status + ").");
                return;
            }

            const data = JSON.parse(responseText);
            
            if (response.ok && data.items && Array.isArray(data.items)) {
                itemsDesglosadosGlobal = data.items;
                renderizarTablaEditable();
                document.getElementById('resultado-section').style.display = 'block';
            } else {
                alert(t('_02_err_calcular', "❌ Error al calcular:") + " " + (data.error || ""));
            }
        } catch (err) {
            alert(t('_02_err_procesamiento', "❌ Error de procesamiento:") + " " + err.message);
        } finally {
            document.getElementById('loading').style.display = 'none';
        }
    }

    function renderizarTablaEditable() {
        const tbody = document.querySelector('#tablaNutricional tbody');
        tbody.innerHTML = '';

        itemsDesglosadosGlobal.forEach((item, index) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><input type="text" class="editable-cell" value="${item.alimento || ''}" onchange="actualizarItem(${index}, 'alimento', this.value)"></td>
                <td><input type="number" step="any" class="editable-cell" value="${item.peso || 0}" onchange="actualizarItem(${index}, 'peso', this.value)"></td>
                <td><input type="number" step="any" class="editable-cell" value="${item.calorias || 0}" onchange="actualizarItem(${index}, 'calorias', this.value)"></td>
                <td><input type="number" step="any" class="editable-cell" value="${item.proteinas || 0}" onchange="actualizarItem(${index}, 'proteinas', this.value)"></td>
                <td><input type="number" step="any" class="editable-cell" value="${item.grasas || 0}" onchange="actualizarItem(${index}, 'grasas', this.value)"></td>
                <td><input type="number" step="any" class="editable-cell" value="${item.carbohidratos || 0}" onchange="actualizarItem(${index}, 'carbohidratos', this.value)"></td>
                <td><input type="number" step="any" class="editable-cell" value="${item.fibras || 0}" onchange="actualizarItem(${index}, 'fibras', this.value)"></td>
            `;
            tbody.appendChild(tr);
        });
        recalcularTotales();
    }

    function actualizarItem(index, campo, valor) {
        if (campo === 'alimento') {
            itemsDesglosadosGlobal[index][campo] = valor;
        } else {
            itemsDesglosadosGlobal[index][campo] = parseFloat(valor) || 0;
        }
        recalcularTotales();
    }

    function recalcularTotales() {
        let tPeso = 0, tCal = 0, tProt = 0, tGras = 0, tCarb = 0, tFibr = 0;

        itemsDesglosadosGlobal.forEach(item => {
            tPeso += parseFloat(item.peso) || 0;
            tCal += parseFloat(item.calorias) || 0;
            tProt += parseFloat(item.proteinas) || 0;
            tGras += parseFloat(item.grasas) || 0;
            tCarb += parseFloat(item.carbohidratos) || 0;
            tFibr += parseFloat(item.fibras) || 0;
        });

        document.getElementById('totPeso').innerText = Math.round(tPeso);
        document.getElementById('totCal').innerText = Math.round(tCal);
        document.getElementById('totProt').innerText = Math.round(tProt);
        document.getElementById('totGras').innerText = Math.round(tGras);
        document.getElementById('totCarb').innerText = Math.round(tCarb);
        document.getElementById('totFibr').innerText = Math.round(tFibr);
    }

    async function guardarEnGoogleSheets() {
        if (!currentUserId || itemsDesglosadosGlobal.length === 0) {
            alert(t('_02_err_sin_datos', "No hay datos calculados para guardar."));
            return;
        }

        const filaTotalConsolidada = {
            nombre: document.getElementById('codigo').value.trim(),
            descripcion: document.getElementById('descripcion').value.trim(),
            peso: parseFloat(document.getElementById('totPeso').innerText),
            calorias: parseFloat(document.getElementById('totCal').innerText),
            proteinas: parseFloat(document.getElementById('totProt').innerText),
            grasas: parseFloat(document.getElementById('totGras').innerText),
            carbohidratos: parseFloat(document.getElementById('totCarb').innerText),
            fibras: parseFloat(document.getElementById('totFibr').innerText)
        };

        try {
            const response = await fetch('/api/guardar-comida', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: currentUserId,
                    fila: filaTotalConsolidada
                })
            });

            const res = await response.json();
            if (response.ok) {
                if (res.codigo_guardado) {
                    filaTotalConsolidada.nombre = res.codigo_guardado;
                    document.getElementById('codigo').value = res.codigo_guardado;
                }
                alert(t('_02_msg_exito_guardar', "✅ ¡Éxito!") + " " + (res.message || ""));
            } else {
                alert(t('_02_err_guardar', "❌ Error al guardar:") + " " + (res.error || ""));
            }
        } catch (e) {
            alert(t('_02_err_conexion_guardar', "Error de conexión al intentar guardar."));
        }
    }

    function copiarFilaExcel() {
        const codigo = document.getElementById('codigo').value.trim();
        const descripcion = document.getElementById('descripcion').value.trim();
        const celdas = [
            codigo,
            descripcion,
            document.getElementById('totPeso').innerText,
            document.getElementById('totCal').innerText,
            document.getElementById('totProt').innerText,
            document.getElementById('totGras').innerText,
            document.getElementById('totCarb').innerText,
            document.getElementById('totFibr').innerText
        ];
        const textoCopiable = celdas.join('\\t');

        navigator.clipboard.writeText(textoCopiable).then(() => {
            alert(t('_02_msg_copiado', "¡Fila total copiada! Podés pegarla en tu Excel con Ctrl + V."));
        }).catch(err => {
            alert(t('_02_err_copiar', "Error al copiar al portapapeles."));
        });
    }
</script>

</body>
</html>
"""

@app.route('/', methods=['GET'])
def vista_calculadora():
    user_id = request.args.get('user_id', '')
    return render_template_string(HTML_CALCULADORA_RECETAS, user_id=user_id)


@app.route('/manual.pdf', methods=['GET'])
def servir_manual_pdf():
    try:
        return send_from_directory(directory=os.path.join(os.getcwd(), 'static'), path='manual.pdf', as_attachment=True)
    except Exception as e:
        return jsonify({"error": "No se encontró el archivo manual.pdf en la carpeta static."}), 404


@app.route('/api/config-idiomas', methods=['GET'])
def api_config_idiomas():
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
        row_lenguajes = dict_filas.get('lenguajes', {})
        row_banderas = dict_filas.get('banderas', {})

        idiomas_info = []
        for col in cols:
            idiomas_info.append({
                'code': col,
                'name': str(row_lenguajes.get(col, col.upper())).strip(),
                'flag': str(row_banderas.get(col, '🌐')).strip()
            })
        return jsonify({"idiomas": idiomas_info}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/audioguia', methods=['GET'])
def api_audioguia():
    lang = request.args.get('lang', 'es')
    try:
        traducciones = obtener_traducciones_db(lang)
        texto_guia = traducciones.get("guia", "Bienvenido a la audioguía del asistente nutricional.")
        return jsonify({"guia": texto_guia}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/traducciones', methods=['GET'])
def api_traducciones():
    lang = request.args.get('lang', 'en')
    try:
        traducciones = obtener_traducciones_db(lang)
        return jsonify(traducciones), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/usuario-idioma', methods=['GET'])
def api_usuario_idioma():
    user_id = request.args.get('user_id')
    lang = 'es'
    if user_id:
        try:
            lang = obtener_idioma_usuario(user_id)
        except Exception:
            pass
    return jsonify({"lang": lang}), 200


@app.route('/api/calcular-receta', methods=['POST'])
def api_calcular_receta():
    try:
        data = request.json
        codigo = data.get('codigo')
        descripcion = data.get('descripcion')
        receta = data.get('receta')
        tipo_calculo = data.get('tipoCalculo')
        porciones = int(data.get('porciones', 1))
        lang = data.get('lang', 'es')

        client_ai = globals().get('client_ai')
        if not client_ai:
            return jsonify({"error": "El cliente de IA no está configurado."}), 500

        prompt_ia = (
            f"Analiza la siguiente receta o listado de ingredientes: '{receta}'. "
            f"Desglósalo estrictamente **ítem por ítem** (ingrediente por ingrediente o componente por componente). "
            f"Para cada ítem, calcula de forma independiente y precisa:\n"
            f"- El nombre del alimento o ingrediente ('alimento'), escrito en el idioma correspondiente al código '{lang}'\n"
            f"- El peso estimado en gramos ('peso')\n"
            f"- Las calorías ('calorias')\n"
            f"- Las proteínas en gramos ('proteinas')\n"
            f"- Las grasas en gramos ('grasas')\n"
            f"- Los carbohidratos en gramos ('carbohidratos')\n"
            f"- Las fibras en gramos ('fibras')\n\n"
            f"REGLA ESTRICTA: Responde ÚNICAMENTE con un objeto JSON válido, sin textos adicionales, saludos ni explicaciones. "
            f"El JSON debe tener exactamente esta estructura:\n"
            "{\n"
            '  "items": [\n'
            '    {"alimento": "nombre del ingrediente", "peso": 0.0, "calorias": 0.0, "proteinas": 0.0, "grasas": 0.0, "carbohidratos": 0.0, "fibras": 0.0}\n'
            "  ]\n"
            "}"
        )

        response = client_ai.chat.completions.create(
            model=globals().get('GROQ_TEXTO', "llama-3.3-70b-versatile"),
            messages=[
                {"role": "system", "content": "Eres un nutricionista clínico experto en análisis de recetas y desglose de macronutrientes."},
                {"role": "user", "content": prompt_ia}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        resultado_json = json.loads(response.choices[0].message.content)
        items = resultado_json.get("items", [])

        if tipo_calculo == 'porciones' and porciones > 1:
            for item in items:
                item['peso'] = round(float(item.get('peso', 0)) / porciones, 2)
                item['calorias'] = round(float(item.get('calorias', 0)) / porciones, 2)
                item['proteinas'] = round(float(item.get('proteinas', 0)) / porciones, 2)
                item['grasas'] = round(float(item.get('grasas', 0)) / porciones, 2)
                item['carbohidratos'] = round(float(item.get('carbohidratos', 0)) / porciones, 2)
                item['fibras'] = round(float(item.get('fibras', 0)) / porciones, 2)

        return jsonify({
            "nombre": codigo,
            "descripcion": descripcion,
            "items": items
        }), 200

    except Exception as e:
        logger.error(f"Error en api_calcular_receta: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# =====================================================================================================================================
#              FINAL                                  PAGINA WEB (CALCULADORA UNICA)                  FINAL
# =====================================================================================================================================

# ======================================================================================================================================
#              INICIO                                   FUNCIONES SUPABASE                           INICIO
# ======================================================================================================================================

#                 INICIO                                     1  GOOGLE SHEETS                       INICIO
# ======================================================================================================================================
                
def to_sheet_int(val):
    num = parse_raw_val(val)
    return int(round(num * 1000))

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
            ws = spreadsheet.add_worksheet(title=title, rows="500", cols="6")
            ws.append_row(["Fecha_Hora", "Fecha_Dia", "Alta", "Baja", "Pulsaciones", "Nota"])
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

def get_user_worksheet(user_id):
    """Obtiene o crea una pestaña dinámica 'Comidas_<user_id>' dentro de la planilla."""
    gc = get_gspread_client()
    sh = gc.open(SPREADSHEET_NAME)
    
    sheet_name = f"Comidas_{user_id}"
    ws = get_or_create_worksheet(sh, sheet_name)
    
    if not ws.get_all_values():
        ws.append_row([
            "Código / Nombre", 
            "Descripción", 
            "Peso (g x1000)", 
            "Calorías (x1000)", 
            "Proteínas (g x1000)", 
            "Grasas (g x1000)", 
            "Carbohidratos (g x1000)", 
            "Fibras (g x1000)"
        ])
        
    return ws

#              INICIO                           2  FUNCIONES CONEXIONES                            INICIO
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
                    "ritmo_preferido" TEXT
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
        conn.commit()

    if tipo_tabla == "usuarios":
        try:
            cur.execute(f'ALTER TABLE "{tabla_real}" ADD COLUMN IF NOT EXISTS "cadera_cm" DOUBLE PRECISION;')
            conn.commit()
        except Exception:
            conn.rollback()

    return conn, cur


#              INICIO                     3 FUNCIONES CENTRALES DE ESCRITURA (CON MANEJO SEGURO)       INICIO
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
    
#              INICIO                     4 FUNCIONES BIOMETRIA Y FUNCIONES PRESION                       INICIO
# =============================================================================================================================================

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

def obtener_ultimo_perfil_dict(u_id):
    try:
        perfil = obtener_perfil_usuario(u_id)
        if perfil:
            return perfil
    except Exception as e:
        logger.error(f"Error en obtener_ultimo_perfil_dict para {u_id}: {e}")
    return {}
  
def _calcular_y_actualizar_factor_mes_anterior(user_id, mes_anterior_str, peso_fin_mes_override=None):
    try:
        df_datos = obtener_datos_usuario(user_id) if 'obtener_datos_usuario' in globals() else pd.DataFrame()
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

        perfil = obtener_perfil_usuario(user_id, mes_target=mes_anterior_str) if 'obtener_perfil_usuario' in globals() else {}
        
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

#              INICIO                     5  FUNCIONES LECTURA COMIDAS                         INICIO
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
                                
def obtener_codigo_unico(tabla_nombre, codigo_base):
    conn = None
    cur = None
    try:
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comidas_precargadas")
        query = f'SELECT "Nombre" FROM "{tabla_nombre}"'
        cur.execute(query)
        filas = cur.fetchall()

        codigos_existentes = set(str(fila[0]).strip().upper() for fila in filas if fila[0] is not None)
    except Exception as e:
        logger.error(f"Error al obtener códigos existentes de Supabase para {tabla_nombre}: {e}")
        codigos_existentes = set()
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass

    codigo_limpio = str(codigo_base).strip().upper()
    
    if codigo_limpio not in codigos_existentes:
        return codigo_limpio

    i = 1
    mientras_repetido = f"{codigo_limpio}{i}"
    while mientras_repetido in codigos_existentes:
        i += 1
        mientras_repetido = f"{codigo_limpio}{i}"
        
    return mientras_repetido   

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

#                    INICIO                  6 FUNCIONES LECTURA PROFESIONALES                      INICIO
# =======================================================================================================================================

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
                estado = fila[2] if fila[2] is not None else "Activo"
                if str(estado).lower() in ['activo', 'sí', 'si', 'true', '1']:
                    pacientes.append({"user_id": u_id, "nombre": nombre})
    except Exception as e:
        logger.error(f"Error en obtener_pacientes_por_medico para {prof_id}: {e}")
    return pacientes

#              INICIO                                  7 FUNCIONES USUARIOS                        INICIO
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

#              INICIO                                  8 FUNCIONES GUARDAR                        INICIO
# =============================================================================================================================================

def guardar_in_sheets_and_db(user_id, items, fecha, momento):
    pass # Mantiene compatibilidad

def guardar_en_sheets(user_id, items, fecha, momento, tipo="Comida"):
    """Guarda los registros de ingesta alimentaria de forma dual en Google Sheets (multiplicado por 1000) y Supabase."""
    try:
        gc = get_gspread_client()
        sh = gc.open(SPREADSHEET_NAME)
        ws = get_or_create_worksheet(sh, f"User_{user_id}")

        rows = []
        for item in items:
            rows.append([
                str(fecha),
                str(momento),
                item.get("alimento", item.get("Alimento/Detalle", "Desconocido")),
                to_sheet_int(item.get("peso", item.get("Peso (g)", 0))),
                to_sheet_int(item.get("calorias", item.get("Calorías (kcal)", 0))),
                to_sheet_int(item.get("proteinas", item.get("Proteínas (g)", 0))),
                to_sheet_int(item.get("grasas", item.get("Grasas (g)", 0))),
                to_sheet_int(item.get("carbohidratos", item.get("hidratos", item.get("Hidratos (g)", 0)))),
                to_sheet_int(item.get("fibras", item.get("Fibras (g)", 0)))
            ])
        if rows:
            ws.append_rows(rows)
    except Exception as e:
        print(f"⚠️ Error al guardar en Google Sheets para el usuario {user_id}: {e}")
        logger.error(f"Error al guardar en Google Sheets (User_{user_id}): {e}")

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
        print(f"🚨 ERROR REAL EN SUPABASE: {e}")
        logger.error(f"Error interno al duplicar ingesta en Supabase (User_{user_id}): {e}")
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass
                
def guardar_comida_precargada_db(user_id, fila):
    """Guarda las comidas precargadas exclusivamente en Supabase."""
    codigo_original = fila.get('Nombre', fila.get('nombre', ''))
    
    tabla_nombre = f"Comidas_{user_id}"
    conn = None
    cur = None
    try:
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comidas_precargadas")
        cur.execute(f'SELECT "Nombre" FROM "{tabla_nombre}"')
        filas = cur.fetchall()
        codigos_existentes = set(str(f[0]).strip().upper() for f in filas if f[0] is not None)
    except Exception:
        codigos_existentes = set()
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass

    codigo_limpio = str(codigo_original).strip().upper()
    codigo_unico = codigo_limpio
    i = 1
    while codigo_unico in codigos_existentes:
        i += 1
        codigo_unico = f"{codigo_limpio}{i}"

    try:
        p_val = float(fila.get('Peso', fila.get('peso', 0)) or 0.0)
        c_val = float(fila.get('Calorias', fila.get('calorias', 0)) or 0.0)
        pr_val = float(fila.get('Proteinas', fila.get('proteinas', 0)) or 0.0)
        g_val = float(fila.get('Grasas', fila.get('grasas', 0)) or 0.0)
        h_val = float(fila.get('Carbohidratos', fila.get('carbohidratos', fila.get('Hidratos', 0))) or 0.0)
        f_val = float(fila.get('Fibras', fila.get('fibras', 0)) or 0.0)

        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comidas_precargadas")
        query = f"""
            INSERT INTO "{tabla_nombre}" ("Nombre", "Descripcion", "Peso", "Calorias", "Proteinas", "Grasas", "Carbohidratos", "Fibras")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        valores = (
            str(codigo_unico), 
            str(fila.get('Descripcion', fila.get('descripcion', ''))), 
            p_val / 1000.0 if p_val > 1000 else p_val, 
            c_val / 1000.0 if c_val > 1000 else c_val, 
            pr_val / 1000.0 if pr_val > 1000 else pr_val, 
            g_val / 1000.0 if g_val > 1000 else g_val, 
            h_val / 1000.0 if h_val > 1000 else h_val, 
            f_val / 1000.0 if f_val > 1000 else f_val
        )
        cur.execute(query, valores)
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error al grabar Comida Precargada en Supabase (Comidas_{user_id}): {e}")
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass
    
    return codigo_unico

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
        cur_m.execute('SELECT variables, "{0}" FROM "multi"'.format(lang_usuario))
        filas_m = cur_m.fetchall()
        traducciones_msj = {row[0].strip().lower(): row[1] for row in filas_m if row[0] and row[1]}
        cur_m.close()
        conn_m.close()
    except Exception:
        pass

    def msg_t(clave, fallback):
        return traducciones_msj.get(clave, fallback)

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
        return {"error": True, "mensaje": "❌ Error al consultar la base de datos."}
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
            df_datos = obtener_datos_usuario(user_id) if 'obtener_datos_usuario' in globals() else pd.DataFrame()
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
            return {"error": True, "mensaje": msg_t("_03_peso_ya_registrado", msg_default)}
        
        _core_guardar_perfil_db(user_id, str(mes), {
            "EDAD": str(edad_val), "PESO": peso_ingresado, "peso_actual": peso_ingresado, 
            "ALTURA": altura_val, "GENERO": genero_val, "ocupacion": factor_previo, 
            "Fecha_Actualizacion": ahora.strftime("%Y-%m-%d")
        })
        _core_guardar_usuario_db(user_id, {"Ultimo Mes Peso": ahora.strftime("%Y-%m-%d")})
        
        msg_default = f"✅ **¡Peso base del mes registrado correctamente!**\n\n• Peso inicial ({mes}): `{peso_ingresado:.1f} kg`"
        template = msg_t("_03_peso_base_ok", msg_default)
        return {"error": False, "mensaje": template.format(mes=mes, peso=f"{peso_ingresado:.1f}")}

    elif 15 <= dia_actual <= 25:
        if dia_ultima_act >= 15:
            msg_default = "⚖️ Control quincenal ya registrado correctamente. Tu próximo ingreso estará habilitado a partir del día 26 para el cierre del mes."
            return {"error": True, "mensaje": msg_t("_03_control_quincenal_hecho", msg_default)}
        
        nuevo_factor = recalcular_factor_diluido(peso_base_mes, peso_ingresado)
        delta_peso = peso_ingresado - peso_base_mes
        
        _core_guardar_perfil_db(user_id, str(mes), {
            "peso_actual": peso_ingresado, "ocupacion": nuevo_factor, "Fecha_Actualizacion": ahora.strftime("%Y-%m-%d")
        })
        guardar_ocupacion_db(user_id, nuevo_factor, str(mes))
        
        msg_default = f"✅ **¡Control quincenal guardado y factor calibrado!**\n\n• Variación detectada: `{delta_peso:+.1f} kg`\n• Nuevo factor de actividad: `{nuevo_factor:.4f}`"
        template = msg_t("_03_control_quincenal_ok", msg_default)
        return {"error": False, "mensaje": template.format(variacion=f"{delta_peso:+.1f}", factor=f"{nuevo_factor:.4f}")}

    else: # dia_actual >= 26
        if dia_ultima_act >= 26:
            msg_default = "⚖️ Ya registraste tu peso de cierre de mes. El sistema ya preparó tu ficha para el mes que viene. Tu próximo pesaje se habilitará el día 15."
            return {"error": True, "mensaje": msg_t("_03_cierre_mes_hecho", msg_default)}
        
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
        template = msg_t("_03_cierre_mes_ok", msg_default)
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

#              INICIO                              FUNCIONES ADMINISTRADOR                           INICIO
# =============================================================================================================================================

# ---------------------------------------------------------------------------------------------------------------------------------------------
# FUNCIÓN INTERNA 1: _asegurar_tabla_y_conectar_migrar
# ¿QUÉ HACE?: Se conecta a Supabase, BORRA (DROP) la tabla indicada si ya existía y la vuelve a crear (CREATE) desde cero
#             usando exactamente los nombres de columnas que tenga el archivo Excel (DataFrame) que se le pase.
# ¿CUÁNDO SE USA?: La llaman automáticamente por detrás los comandos /traducir, /armar, /subir y /migrar.
# ---------------------------------------------------------------------------------------------------------------------------------------------
def _asegurar_tabla_y_conectar_migrar(tabla_nombre, df_muestra=None):
    conn = _obtener_conexion_db()
    cur = conn.cursor()
    cur.execute(f'DROP TABLE IF EXISTS "{tabla_nombre}" CASCADE;')
    conn.commit()
    
    if df_muestra is not None and not df_muestra.empty:
        cols_def = []
        for col in df_muestra.columns:
            cols_def.append(f'"{col}" TEXT')
        cols_sql = ", ".join(cols_def)
        cur.execute(f'CREATE TABLE "{tabla_nombre}" (id SERIAL PRIMARY KEY, {cols_sql});')
        conn.commit()
    return conn, cur

# ---------------------------------------------------------------------------------------------------------------------------------------------
# COMANDO DE TELEGRAM: /hablar (Generador de audios de voz con OpenAI)
# CÓMO SE USA EN TELEGRAM: 
#   /hablar M Hola, bienvenidos a IA NutriBot   (Para voz de Mujer - "nova")
#   /hablar H Hola, bienvenidos a IA NutriBot   (Para voz de Hombre - "alloy")
# ¿QUÉ HACE?: Convierte el texto que le escribas en un archivo de audio MP3 hablado con inteligencia artificial
#             y te lo envía al chat de Telegram como una nota de voz.
# ---------------------------------------------------------------------------------------------------------------------------------------------
async def cmd_hablar(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    if not es_administrador(user_id):
        msg_no_perm = "❌ No tenés permisos para ejecutar este comando."
        await update.message.reply_text(msg_no_perm)
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "⚠ Formato incorrecto. Usa:\n"
            "/hablar M [tu texto para voz de mujer]\n"
            "/hablar H [tu texto para voz de hombre]"
        )
        return

    genero = context.args[0].upper()
    texto_usuario = " ".join(context.args[1:])

    voz_mujer_defecto = os.getenv("VOZ_MUJER", "nova")
    voz_hombre_defecto = os.getenv("VOZ_HOMBRE", "alloy")

    if genero == "M":
        voz_elegida = voz_mujer_defecto
    elif genero == "H":
        voz_elegida = voz_hombre_defecto
    else:
        await update.message.reply_text("⚠️ Especifica 'M' para mujer o 'H' para hombre.")
        return

    output_path = "voz_temporal.mp3"

    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice=voz_elegida,
            input=texto_usuario
        )
        response.stream_to_file(output_path)

        with open(output_path, "rb") as audio_file:
            await update.message.reply_voice(voice=audio_file)

    except Exception as e:
        await update.message.reply_text(f"Hubo un error al generar la voz: {str(e)}")

    finally:
        if os.path.exists(output_path):
            os.remove(output_path)

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
        msg_no_perm = "❌ No tenés permisos para ejecutar este comando."
        await update.message.reply_text(msg_no_perm)
        return

    nombre_tabla = "multi"

    try:
        ruta_archivo = f"{nombre_tabla}.xlsx"
        if not os.path.exists(ruta_archivo):
            await update.message.reply_text(f"❌ No encuentro el archivo `{ruta_archivo}` en el servidor.", parse_mode="Markdown")
            return

        df = pd.read_excel(ruta_archivo)
        df.columns = [str(c).strip() for c in df.columns]

        if 'variables' not in df.columns or 'ES' not in df.columns:
            await update.message.reply_text("❌ El archivo base debe tener columnas 'variables' y 'ES'.", parse_mode="Markdown")
            return

        mapa_variables = {}
        contador_var = 1
        textos_preparados = []
        
        for idx, row in df.iterrows():
            texto_es = str(row['ES']) if pd.notna(row['ES']) else ""
            if not texto_es.strip() or texto_es.strip().lower() == 'nan':
                textos_preparados.append("")
                continue

            # Expresión regular robusta que evita saltos de línea y captura limpiamente entre llaves o corchetes
            placeholders = re.findall(r'(\[.*?\]|\{[^}\n]+\})', texto_es)
            texto_modificado = texto_es
            
            for ph in placeholders:
                token = None
                for t, original in mapa_variables.items():
                    if original == ph:
                        token = t
                        break
                if not token:
                    token = f"__VAR_{contador_var:04d}__"
                    mapa_variables[token] = ph
                    contador_var += 1
                
                texto_modificado = texto_modificado.replace(ph, token)
            
            textos_preparados.append(texto_modificado)

        df_hoja1 = pd.DataFrame()
        df_hoja1['variables'] = df['variables']
        df_hoja1['ES'] = textos_preparados

        lista_diccionario = [{"codigo": k, "variable_original": v} for k, v in mapa_variables.items()]
        df_hoja2 = pd.DataFrame(lista_diccionario)

        nombre_salida = f"{nombre_tabla}_desarmado.xlsx"
        
        buffer_out = io.BytesIO()
        with pd.ExcelWriter(buffer_out, engine='openpyxl') as writer:
            df_hoja1.to_excel(writer, index=False, sheet_name='traduccion')
            df_hoja2.to_excel(writer, index=False, sheet_name='diccionario_vars')
        buffer_out.seek(0)

        await update.message.reply_document(
            document=buffer_out,
            filename=nombre_salida,
            caption=(
                f"✅ **¡Archivo desarmado detectando todas las variables y corchetes!**\n\n"
                f"1. Subilo a Google Drive, agregale las columnas de idiomas que quieras (`EN`, `IT`, etc.) y traducilo.\n"
                f"2. La segunda pestaña (`diccionario_vars`) ahora indexa el 100% de las variables sin cortes.\n"
                f"3. Cuando termines, mandámelo con `/armar`."
            ),
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error en desarmar Excel: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: `{e}`", parse_mode="Markdown")

# ---------------------------------------------------------------------------------------------------------------------------------------------
# COMANDO DE TELEGRAM: /armar (Lee el Excel desarmado directamente del servidor, restaura variables y sube a Supabase)
# CÓMO SE USA EN TELEGRAM: /armar
# ¿QUÉ HACE?:
#   1. Busca el archivo 'multi_desarmado.xlsx' (o el que corresponda) directamente en la carpeta del servidor.
#   2. Lee las solapas 'traduccion' y 'diccionario_vars'.
#   3. Reemplaza todos los códigos __VAR_XXXX__ por sus llaves {variable} o corchetes [variable] originales.
#   4. Borra y vuelve a crear la tabla 'multi' en Supabase con la información limpia y traducida.
# ---------------------------------------------------------------------------------------------------------------------------------------------
async def cmd_armar_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    if not es_administrador(user_id):
        msg_no_perm = "❌ No tenés permisos para ejecutar este comando."
        await update.message.reply_text(msg_no_perm)
        return

    nombre_tabla = "multi"
    ruta_archivo = f"{nombre_tabla}_desarmado.xlsx"

    if not os.path.exists(ruta_archivo):
        await update.message.reply_text(
            f"❌ No encuentro el archivo `{ruta_archivo}` en el servidor. Asegurate de haber subido el archivo traducido al repositorio o carpeta del bot.",
            parse_mode="Markdown"
        )
        return

    mensaje_espera = await update.message.reply_text("🔄 Leyendo del servidor, ensamblando traducciones y sincronizando Supabase...", parse_mode="Markdown")

    try:
        # Leer el archivo Excel directamente desde el disco del servidor
        xls = pd.ExcelFile(ruta_archivo)
        sheets = xls.sheet_names

        if 'traduccion' not in sheets or 'diccionario_vars' not in sheets:
            await mensaje_espera.edit_text("❌ El archivo en el servidor no tiene las solapas requeridas ('traduccion' y 'diccionario_vars').", parse_mode="Markdown")
            return

        df_trad = pd.read_excel(ruta_archivo, sheet_name='traduccion')
        df_dict = pd.read_excel(ruta_archivo, sheet_name='diccionario_vars')

        df_trad.columns = [str(c).strip() for c in df_trad.columns]
        df_dict.columns = [str(c).strip() for c in df_dict.columns]

        mapa_variables = dict(zip(df_dict['codigo'], df_dict['variable_original']))
        columnas_idiomas = [c for c in df_trad.columns if c.upper() != 'VARIABLES']

        for col in columnas_idiomas:
            nueva_columna = []
            for idx, val in df_trad[col].items():
                texto = str(val) if pd.notna(val) else ""
                if not texto.strip() or texto.strip().lower() == 'nan':
                    nueva_columna.append("")
                    continue

                for codigo, original in mapa_variables.items():
                    texto = texto.replace(codigo, original)
                    texto = texto.replace(codigo.replace('__', '__ '), original)
                    texto = texto.replace(codigo.replace('__', ' __'), original)

                nueva_columna.append(texto)
            
            df_trad[col] = nueva_columna

        columna_clave = df_trad.columns[0]
        df_trad = df_trad.drop_duplicates(subset=[columna_clave], keep='last')

        # Guardar una copia limpia localmente como 'multi.xlsx'
        ruta_archivo_local = f"{nombre_tabla}.xlsx"
        df_trad.to_excel(ruta_archivo_local, index=False)

        # Conectar a Supabase, borrar la tabla vieja y crearla de cero con el nuevo DataFrame
        conn, cur = _asegurar_tabla_y_conectar_migrar(nombre_tabla, df_muestra=df_trad)

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

        await mensaje_espera.edit_text(
            f"🏆 **¡Traducción aplicada con éxito!**\n"
            f"La tabla `{nombre_tabla}` fue completamente reemplazada en Supabase con {filas_insertadas} registros procesados desde el servidor.",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error armando Excel desde el servidor: {e}", exc_info=True)
        await mensaje_espera.edit_text(f"❌ Error al ensamblar: `{e}`", parse_mode="Markdown")

# ---------------------------------------------------------------------------------------------------------------------------------------------
# COMANDO DE TELEGRAM: /subir (Pasa un archivo .xlsx que ya esté en GitHub/Servidor directo a Supabase)
# CÓMO SE USA EN TELEGRAM: /subir multi   (o el nombre de cualquier archivo .xlsx que hayas subido a GitHub)
# ¿QUÉ HACE?: Busca el archivo '<nombre>.xlsx' en la carpeta del servidor, borra la tabla en Supabase
#             y la vuelve a crear cargando todas las filas tal cual están en ese Excel (sin traducir ni modificar nada).
# ---------------------------------------------------------------------------------------------------------------------------------------------
async def cmd_subir(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    if not es_administrador(user_id):
        msg_no_perm = "❌ No tenés permisos para ejecutar este comando."
        await update.message.reply_text(msg_no_perm)
        return
    
    if not context.args or len(context.args) == 0:
        await update.message.reply_text(
            "⚠️ Por favor, indica el nombre de la tabla a importar.\nEjemplo: `/subir multi`",
            parse_mode="Markdown"
        )
        return

    nombre_tabla = context.args[0].strip()
    ruta_archivo = f"{nombre_tabla}.xlsx"

    if not os.path.exists(ruta_archivo):
        await update.message.reply_text(
            f"❌ No encontré el archivo `{ruta_archivo}` en el servidor. Asegurate de haberlo subido al repositorio de GitHub.",
            parse_mode="Markdown"
        )
        return

    mensaje_espera = await update.message.reply_text(
        f"🔄 Leyendo `{ruta_archivo}` del servidor y reescribiendo la tabla `{nombre_tabla}` en Supabase...", 
        parse_mode="Markdown"
    )

    try:
        df = pd.read_excel(ruta_archivo)

        if df.empty:
            await mensaje_espera.edit_text(f"⚠️ El archivo `{ruta_archivo}` está vacío.", parse_mode="Markdown")
            return

        df.columns = [str(c).strip() for c in df.columns]

        conn, cur = _asegurar_tabla_y_conectar_migrar(nombre_tabla, df_muestra=df)

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

        await mensaje_espera.edit_text(
            f"✅ ¡Éxito! La tabla `{nombre_tabla}` fue leída del servidor y sincronizada en Supabase con {filas_insertadas} registros.", 
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error al importar la tabla {nombre_tabla} desde el servidor: {e}", exc_info=True)
        await mensaje_espera.edit_text(f"❌ Error al importar la tabla: `{e}`", parse_mode="Markdown")

# ---------------------------------------------------------------------------------------------------------------------------------------------
# COMANDO DE TELEGRAM: /descargar (Descarga cualquier tabla de Supabase a un archivo Excel)
# CÓMO SE USA EN TELEGRAM: /descargar multi   o   /descargar Usuarios
# ¿QUÉ HACE?: Consulta la tabla en vivo en Supabase, arma un archivo .xlsx en memoria y te lo envía por Telegram
#             para que lo tengas de backup o lo puedas revisar en tu PC.
# ---------------------------------------------------------------------------------------------------------------------------------------------
async def cmd_descargar(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if not es_administrador(user_id):
        msg_no_perm = "❌ No tenés permisos para ejecutar este comando."
        await update.message.reply_text(msg_no_perm)
        return
    
    if not context.args or len(context.args) == 0:
        await update.message.reply_text(
            "⚠️ Por favor, indica el nombre de la tabla que deseas descargar.\nEjemplo: `/descargar textos_bot` o `/descargar Usuarios`",
            parse_mode="Markdown"
        )
        return

    nombre_tabla = context.args[0].strip()
    mensaje_espera = await update.message.reply_text(f"⏳ Consultando y preparando la tabla `{nombre_tabla}`...", parse_mode="Markdown")

    try:
        conn, cur = _asegurar_tabla_y_conectar(nombre_tabla, tipo_tabla="comida")
        query = f'SELECT * FROM "{nombre_tabla}"'
        df = pd.read_sql(query, conn)
        
        cur.close()
        conn.close()

        if df.empty:
            await mensaje_espera.edit_text(f"⚠️ La tabla `{nombre_tabla}` existe pero está vacía.", parse_mode="Markdown")
            return

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=nombre_tabla[:31])
        buffer.seek(0)

        filename = f"{nombre_tabla}.xlsx"
        await update.message.reply_document(
            document=buffer,
            filename=filename,
            caption=f"✅ Aquí tienes el respaldo de la tabla *{nombre_tabla}* ({len(df)} registros).",
            parse_mode="Markdown"
        )
        
        try:
            await mensaje_espera.delete()
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Error al descargar la tabla {nombre_tabla} para el usuario {user_id}: {e}", exc_info=True)
        await mensaje_espera.edit_text(
            f"❌ No se pudo descargar la tabla `{nombre_tabla}`.\nError: `{e}`",
            parse_mode="Markdown"
        )   
            
# =============================================================================================================================================
#              FINAL                            FUNCIONES SUPABASE                 FINAL
# =============================================================================================================================================

# =============================================================================================================================================
#              INICIO                         FUNCIONES AUXILIARES INTERNAS                  INICIO
# =============================================================================================================================================

#              INICIO                             FUNCIONES DE PARSING Y FECHAS                  INICIO
# =============================================================================================================================================

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

def parse_float_from_sheets(val):
    num = parse_raw_val(val)
    return num / 1000.0

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

def extraer_val(texto: str) -> float:
    if not texto:
        return 0.0
    coincidencia = re.search(r'(\d+(?:[.,]\d+)?)', str(texto))
    if coincidencia:
        try:
            return float(coincidencia.group(1).replace(',', '.'))
        except ValueError:
            return 0.0
    return 0.0

#              INICIO                     FUNCIONES BIOMETRICAS Y METRICAS                   INICIO
# =============================================================================================================================================

def calcular_contextura(sexo: str, altura_cm: float, muneca_cm: float):
    if muneca_cm <= 0: return "Mediana"
    r = altura_cm / muneca_cm
    if str(sexo).upper() in ['M', 'MASCULINO']:
        if r > 10.4: return "Pequeña"
        elif 9.6 <= r <= 10.4: return "Mediana"
        else: return "Grande"
    else:
        if r > 11.0: return "Pequeña"
        elif 10.1 <= r <= 11.0: return "Mediana"
        else: return "Grande"

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

# 8. CÁLCULO DE TMB Y GET (SCHOFIELD OMS EN NIÑOS, KATCH/MIFFLIN EN ADULTOS)
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

        try:
            factor_act = float(actividad)
            if factor_act > 10: factor_act /= 1000.0
        except (TypeError, ValueError):
            factor_act = 1.375

        calorias_crecimiento = 25.0
        get = (tmb * factor_act) + calorias_crecimiento
        return round(tmb, 2), round(get, 2)

    # --- ADULTOS (>= 18 AÑOS): KATCH-MCARDLE O MIFFLIN-ST JEOR ---
    if is_femenino:
        tmb_mifflin = (10.0 * peso) + (6.25 * altura) - (5.0 * anios) - 161.0
    else:
        tmb_mifflin = (10.0 * peso) + (6.25 * altura) - (5.0 * anios) + 5.0

    if masa_magra is None or masa_magra <= 1.0:
        bio = _obtener_biometria_encapsulada(sexo_arg=genero, altura_arg=altura, peso_arg=peso, edad_arg=anios)
        cint_eval = bio.get("cintura", 1.0)
        cuell_eval = bio.get("cuello", 1.0)
        cad_eval = cadera_cm if (cadera_cm is not None and float(cadera_cm) > 0) else bio.get("cadera", 0.0)

        if is_femenino:
            if cint_eval > 1.0 and cuell_eval > 1.0 and cad_eval > 1.0:
                _, masa_magra = calcular_grasa_y_magra(genero, altura, cint_eval, cuell_eval, peso, cadera_cm=cad_eval, edad=anios)
        else:
            if cint_eval > 1.0 and cuell_eval > 1.0 and cint_eval > cuell_eval:
                _, masa_magra = calcular_grasa_y_magra(genero, altura, cint_eval, cuell_eval, peso, edad=anios)

    if masa_magra is not None and masa_magra > 1.0:
        tmb = 370.0 + (21.6 * float(masa_magra))
    else:
        tmb = tmb_mifflin

    try:
        factor_act = float(actividad)
        if factor_act > 10:
            factor_act /= 1000.0
    except (TypeError, ValueError):
        factor_act = 1.375

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
    lang = obtener_idioma_usuario(uid) if 'obtener_idioma_usuario' in globals() else 'es'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
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
        cur.execute('SELECT "Idioma" FROM "Usuarios" WHERE "User ID" = %s', (str(user_id),))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row[0]:
            return str(row[0]).strip().lower()
    except Exception as e:
        logger.error(f"Error obteniendo idioma para {user_id}: {e}")
    return 'en'

def obtener_traducciones_db(lang):
    """Consulta la tabla 'multi' en Supabase y devuelve un diccionario con las traducciones."""
    traducciones = {}
    col_lang = "ES" if str(lang).strip().lower() == "es" else "EN"
    try:
        conn, cur = _asegurar_tabla_y_conectar("multi", tipo_tabla="comidas_precargadas")
        query = f'SELECT "variables", "{col_lang}" FROM "multi"'
        cur.execute(query)
        filas = cur.fetchall()
        cur.close()
        conn.close()

        for fila in filas:
            var_name = str(fila[0]).strip()
            var_text = str(fila[1] or "").strip()
            if var_name:
                traducciones[var_name] = var_text
    except Exception as e:
        logger.error(f"Error al obtener traducciones de Supabase para el idioma {lang}: {e}")
    return traducciones

def requiere_registro(func):
    """Decorador que verifica registro y bloquea usuarios en Estado 3 ofreciendo reactivación prorrateada."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = str(update.effective_user.id).strip()
        encontrado = False
        esta_activo = True
        estado_val = "0"
        
        # Obtener traducciones para el usuario
        lang = obtener_idioma_usuario(user_id)
        traducciones = obtener_traducciones_db(lang)

        mensaje_no_registrado = traducciones.get(
            "04_bot_no_registrado", 
            "⚠️ **¡Aún no estás registrado!**\n\n"
            "Para usar este comando y acceder a tu plan nutricional, primero debés registrarte.\n\n"
            "👉 Usá el comando `/alta` para crear tu perfil en un par de pasos."
        )
        
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
            )
            
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
#                INICIO                       14 FUNCIONES IA GROQ                                      INICIO
# ======================================================================================================================================


def analizar_frecuencia_alimentos_mes(df_o_user_id, cat_dict_o_mes=None, col_integrales=None, col_refinadas=None, otras_categorias=None):
    try:
        if isinstance(df_o_user_id, (int, str)) and isinstance(cat_dict_o_mes, str) and not isinstance(df_o_user_id, pd.DataFrame):
            user_id = int(df_o_user_id)
            mes_str = cat_dict_o_mes
            
            df_datos = obtener_datos_usuario(user_id) if 'obtener_datos_usuario' in globals() else pd.DataFrame()
            if df_datos.empty or 'Fecha' not in df_datos.columns:
                return {}
                
            df_datos['Fecha_dt'] = pd.to_datetime(df_datos['Fecha'], errors='coerce').dt.tz_localize(None).dt.normalize()
            inicio_periodo = pd.Timestamp(f"{mes_str}-01").normalize()
            fin_periodo = (inicio_periodo + pd.offsets.MonthEnd(0)).normalize()
            
            df_mes = df_datos[(df_datos['Fecha_dt'] >= inicio_periodo) & (df_datos['Fecha_dt'] <= fin_periodo)].copy()
            if df_mes.empty:
                return {}
                
            cat_dict = {'harinas_integrales': ['integral', 'salvado'], 'harinas_refinadas': ['blanca', 'refinada']}
        else:
            df_mes = df_o_user_id
            cat_dict = cat_dict_o_mes if isinstance(cat_dict_o_mes, dict) else {}

        if otras_categorias is None:
            otras_categorias = {}
            
        frecuencias = {cat: 0 for cat in cat_dict.keys()} if cat_dict else {}

        for _, row in df_mes.iterrows():
            texto_celda = str(row.get('Alimento', '')).strip().lower()
            if not texto_celda:
                continue

            es_integral = any(p in texto_celda for p in (col_integrales or ['integral', 'salvado', 'centeno', 'avena']))
            
            if es_integral:
                for cat_key in frecuencias.keys():
                    if 'integral' in cat_key:
                        frecuencias[cat_key] += 1
            else:
                if col_refinadas and any(p in texto_celda for p in col_refinadas):
                    for cat_key in frecuencias.keys():
                        if 'refinada' in cat_key or 'blanca' in cat_key:
                            frecuencias[cat_key] += 1

            for cat_nombre, palabras in otras_categorias.items():
                if any(p in texto_celda for p in palabras):
                    if cat_nombre not in frecuencias:
                        frecuencias[cat_nombre] = 0
                    frecuencias[cat_nombre] += 1

        return frecuencias
    except Exception as e:
        print(f"Error analizando frecuencias de alimentos: {e}")
        return {}

def calcular_porcentajes_harinas(frecuencias):
    key_int = next((k for k in frecuencias.keys() if 'integral' in k), None)
    key_ref = next((k for k in frecuencias.keys() if 'refinada' in k or 'blanca' in k), None)

    total_integrales = frecuencias.get(key_int, 0) if key_int else 0
    total_refinadas = frecuencias.get(key_ref, 0) if key_ref else 0
    total_harinas = total_integrales + total_refinadas
    
    if total_harinas > 0:
        porc_int = round((total_integrales / total_harinas) * 100)
        porc_ref = round((total_refinadas / total_harinas) * 100)
    else:
        porc_int, porc_ref = 0, 0
        
    return porc_int, porc_ref

def analizar_foto_presion_con_groq(base64_image: str) -> dict:
    client_ai = globals().get('client_ai')
    if not client_ai: return {"es_presion": False}
    prompt = "Analiza esta imagen. ¿Es la pantalla de un tensiómetro digital que muestra valores de presión arterial? Si es así, extrae los valores numéricos de la presión sistólica (Alta), diastólica (Baja) y las pulsaciones. Responde ÚNICAMENTE en formato JSON: {\"es_presion\": true/false, \"alta\": 0.0, \"baja\": 0.0, \"pulsaciones\": 0.0}"
    try:
        response = client_ai.chat.completions.create(
            model=globals().get('GROQ_FOTO', "qwen/qwen3.8-27b"),
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]}],
            temperature=0.0, response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception: return {"es_presion": False}
    
def obtener_prompt_segun_objetivo_peso(peso_actual, peso_referencia):
    if peso_referencia and peso_referencia > 0:
        dif_relativa = (peso_actual - peso_referencia) / peso_referencia
        
        if -0.10 <= dif_relativa <= 0.10:
            return (
                "ESTADO: MANTENIMIENTO / ESTABLE\n"
                "Instrucción para la IA: El usuario se encuentra dentro del rango de tolerancia del 10% respecto a su peso objetivo. "
                "El consumo calórico real y el ideal deben tender a la paridad. Analiza la estabilidad de los hábitos, la variedad de los grupos "
                "de alimentos y la distribución armónica de los macronutrientes. No sugieras cambios drásticos de peso."
            )
        elif peso_actual > peso_referencia:
            return (
                "ESTADO: DESCENSO DE PESO\n"
                "Instrucción para la IA: El usuario se encuentra en un régimen de descenso de peso con un déficit calórico deliberado. "
                "Una ingesta calórica menor al gasto ideal es el comportamiento esperado y correcto. No señales la diferencia calórica como un error "
                "o déficit involuntario ni recomiendes aumentar calorías para alcanzar el mantenimiento. Enfócate exclusivamente en la calidad nutricional, "
                "saciedad y densidad de los alimentos consumidos dentro del marco de restricción."
            )
        else:
            return (
                "ESTADO: ASCENSO / GANANCIA DE PESO\n"
                "Instrucción para la IA: El usuario se encuentra en un régimen de ganancia o ascenso de peso mediante un superávit calórico controlado. "
                "Una ingesta superior al gasto base es el comportamiento pretendido. Evalúa que el aporte extra de nutrientes esté respaldado por proteínas "
                "y carbohidratos de calidad, evitando alertar por un consumo calórico elevado."
            )
    else:
        return (
            "ESTADO: DESCENSO DE PESO\n"
            "Instrucción para la IA: Evalúa el informe priorizando la calidad de los nutrientes y hábitos saludables sin alterar los números duros ya calculados."
        )

def ejecutar_consulta_ia(prompt: str, max_tokens: int = 300, temperature: float = 0.4, system_prompt: str = None, modelo_override: str = None):
    try:
        client = globals().get('client_ai') or globals().get('groq_client')
        if not client:
            api_key = globals().get('GROQ_API_KEY') or os.getenv("GROQ_API_KEY")
            if not api_key:
                logger.error("⚠️ GROQ_API_KEY no configurada.")
                return ""
            from groq import Groq
            client = Groq(api_key=api_key)

        modelo = modelo_override or globals().get('GROQ_TEXTO', "openai/gpt-oss-120b")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=modelo,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        if response and response.choices:
            content = response.choices[0].message.content
            return content.strip() if content else ""
            
    except Exception as e:
        logger.error(f"⚠️ Error en ejecución de IA: {e}")
        
    return ""

def obtener_nombre_lenguaje_ia(user_id=None):
    """Obtiene el nombre completo del lenguaje para la IA desde la tabla Usuarios."""
    if not user_id:
        return "Español"
    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        cur.execute('SELECT "lenguajes" FROM "Usuarios" WHERE "User ID" = %s', (str(user_id),))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row[0]:
            return str(row[0]).strip()
    except Exception as e:
        logger.error(f"Error obteniendo lenguaje IA para {user_id}: {e}")
    return "Español"

def analizar_con_groq(prompt_text, user_id=None):
    client_ai = globals().get('client_ai')
    if not client_ai:
        raise Exception("GROQ_API_KEY is not properly configured.")
    
    nombre_lenguaje = obtener_nombre_lenguaje_ia(user_id)
    logger.info(f"🤖 IA analizando texto entrante (Idioma: {nombre_lenguaje}): '{prompt_text}'")

    system_prompt = (
        f"Sos un asistente inteligente de salud. El usuario se comunica en su idioma ({nombre_lenguaje}). "
        f"Analizá el texto ingresado por el usuario (el cual está redactado en {nombre_lenguaje}) y clasificalo estrictamente en una de estas categorías. "
        f"Debes procesar y responder con los nombres de alimentos/descripciones adaptados o interpretados correctamente según corresponda:\n"
        "1. COMIDA: Si el usuario menciona alimentos, platos o bebidas para ingerir.\n"
        "2. ACTIVIDAD: Si el usuario menciona cualquier tipo de ejercicio, deporte, movimiento físico o actividad en movimiento.\n"
        "3. INFORME_MENSUAL: Si el usuario pide el resumen, balance o informe del mes (ej: 'resumen mensual', 'del mes'). Extrae el mes mencionado en formato 'YYYY-MM' en el campo 'parametro' (si no menciona ninguno, déjalo vacío).\n"
        "4. INFORME_SEMANAL: Si el usuario pide el resumen o balance de la semana.\n"
        "5. INFORME_DIARIO: Si el usuario pide el resumen del día o lo que consumió hoy. Extrae la referencia temporal en el campo 'parametro'.\n"
        "6. RECHAZO: Si el usuario nombra objetos inanimados, productos de limpieza, ropa o cosas que no se comen ni se entrenan.\n\n"
        "REGLAS:\n"
        "- Si es COMIDA, desglósalo con pesos y calorías positivas.\n"
        "- Si el usuario menciona explícitamente el momento de la comida (ej: desayuno, almuerzo, merienda, cena), indícalo en el campo 'momento' (valores posibles: 'desayuno', 'almuerzo', 'merienda', 'cena', o null si no se menciona).\n"
        "- Si el usuario menciona el día (ej: ayer, hoy), indícalo en el campo 'dia' (valores posibles: 'hoy', 'ayer', o null si no se menciona).\n"
        "- Si es ACTIVIDAD:\n"
        "  * Calcula el tiempo total en minutos.\n"
        "  * El campo 'alimento' DEBE empezar obligatoriamente con el número de minutos seguido de un espacio y la descripción.\n"
        "  * El campo 'peso' debe ser estrictamente 0.0.\n"
        "  * Estima las calorías gastadas con valor positivo.\n"
        "- Si es INFORME_MENSUAL, INFORME_SEMANAL o INFORME_DIARIO, el campo 'items' debe ir vacío ([ ]).\n"
        "- Si es RECHAZO, devolvé la lista de 'items' vacía ([ ]).\n\n"
        "Devolvé EXCLUSIVAMENTE un JSON con este formato exacto:\n"
        "{\n"
        '  "items": [\n'
        '    {"alimento": "nombre o descripción", "peso": 0.0, "calorias": 0.0, "proteinas": 0.0, "grasas": 0.0, "carbohidratos": 0.0, "fibras": 0.0}\n'
        "  ],\n"
        '  "tipo": "Comida" o "Actividad" o "INFORME_MENSUAL" o "INFORME_SEMANAL" o "INFORME_DIARIO" o "Rechazo",\n'
        '  "parametro": "texto extraído de fecha/mes o vacío",\n'
        '  "momento": "desayuno" o "almuerzo" o "merienda" o "cena" o null,\n'
        '  "dia": "hoy" o "ayer" o null\n'
        "}"
    )

    response = client_ai.chat.completions.create(
        model=globals().get('GROQ_TEXTO', "openai/gpt-oss-120b"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ],
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    
    resultado_json = json.loads(response.choices[0].message.content)
    logger.info(f"🤖 IA respondió resultado: {resultado_json}")
    
    return resultado_json
    
async def generar_recomendacion_semanal_ia(m: dict, etiqueta_periodo: str, user_id=None):
    nombre_lenguaje = obtener_nombre_lenguaje_ia(user_id)

    prompt_semana = (
        f"Actúa como un nutricionista clínico experto, constructivo y equilibrado. "
        f"Analiza la evolución nutricional de la {etiqueta_periodo} basándote en los promedios reales frente a los rangos saludables:\n\n"
        f"DATOS DEL PERÍODO:\n"
        f"- Días evaluados: {m.get('dias_registrados', 0)}\n"
        f"- Calorías consumidas: {m.get('prom_cal', 0)} kcal/día (Rango saludable: {m.get('cal_min', 0)} - {m.get('cal_max', 0)} kcal)\n"
        f"- Proteínas: {m.get('prom_prot', 0)} g/día (Rango saludable: {m.get('prot_min', 0)} - {m.get('prot_max', 0)} g)\n"
        f"- Grasas: {m.get('prom_gras', 0)} g/día (Rango saludable: {m.get('gras_min', 0)} - {m.get('gras_max', 0)} g)\n"
        f"- Carbohidratos: {m.get('prom_carb', 0)} g/día (Rango saludable: {m.get('carb_min', 0)} - {m.get('carb_max', 0)} g)\n"
        f"- Fibra: {m.get('prom_fibr', 0)} g/día (Mínimo recomendado: {m.get('fibr_min', 0)} g)\n\n"
        f"INSTRUCCIONES CLAVE:\n"
        f"1. Si un valor se encuentra dentro del rango saludable, considéralo un comportamiento correcto y equilibrado; no lo señales como un error ni exijas correcciones drásticas en ese aspecto.\n"
        f"2. Concéntrate exclusivamente en desvíos significativos fuera de los rangos (por ejemplo, si la fibra o algún nutriente clave está muy por debajo del mínimo).\n"
        f"3. Proporciona una devolución clara, motivadora y recomendaciones breves y prácticas para optimizar los hábitos en la semana entrante.\n"
        f"IMPORTANTE: Redacta y responde toda la devolución final dirigida al usuario estrictamente en el idioma {nombre_lenguaje}."
    )
    
    try:
        recomendacion = await obtener_recomendacion_ia(prompt_semana, es_semanal=True, user_id=user_id)
        if recomendacion and recomendacion.strip():
            return recomendacion
    except Exception as e:
        logger.error(f"Error al generar recomendación semanal con IA: {e}")
        
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    return traducciones.get("05_bot_err_analisis_nutricional", "El análisis nutricional no está disponible temporalmente.")
    
async def generar_recomendacion_mensual_para_pdf(user_id: int, mes_str: str, df_mes, perfil: dict, m: dict, context=None) -> str:
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    msg_error_inf = traducciones.get("05_bot_err_generar_inf", "No se pudo generar el reporte auditado por la IA.")
    msg_error_comp = traducciones.get("05_bot_err_compilar_inf", "Error al compilar la recomendación de la IA para el reporte.")

    try:
        conteo_frecuencias = analizar_frecuencia_alimentos_mes(user_id, mes_str) if 'analizar_frecuencia_alimentos_mes' in globals() else {}

        peso_actual_eval = float(m.get('peso_actual', 0))
        peso_referencia_eval = float(m.get('peso_referencia', 0))
        prompt_condicional = obtener_prompt_segun_objetivo_peso(peso_actual_eval, peso_referencia_eval) if 'obtener_prompt_segun_objetivo_peso' in globals() else None

        informe_ia = await generar_informe_mensual_auditado(
            context=context, 
            user_id=user_id, 
            mes_str=mes_str, 
            m=m, 
            frecuencias=conteo_frecuencias, 
            prompt_condicional=prompt_condicional
        )
        
        if not informe_ia:
            informe_ia = f"<b>{msg_error_inf}</b>"

        return (
            informe_ia
            .replace("<br>", "<br/>")
            .replace("<BR>", "<br/>")
        )
    except Exception as e:
        logger.error(f"Error en generar_recomendacion_mensual_para_pdf para {user_id}: {e}")
        return f"<b>{msg_error_comp}</b>"
        
async def generar_informe_mensual_auditado(context, user_id, mes_str, m, frecuencias=None, prompt_condicional=None):
    if frecuencias is None:
        frecuencias = {}

    nombre_lenguaje = obtener_nombre_lenguaje_ia(user_id)
    porc_int, porc_ref = calcular_porcentajes_harinas(frecuencias) if 'calcular_porcentajes_harinas' in globals() else (0, 0)

    key_int = next((k for k in frecuencias.keys() if 'integral' in k), None)
    key_ref = next((k for k in frecuencias.keys() if 'refinada' in k or 'blanca' in k), None)
    total_integrales = frecuencias.get(key_int, 0) if key_int else 0
    total_refinadas = frecuencias.get(key_ref, 0) if key_ref else 0
    total_harinas = total_integrales + total_refinadas

    if total_harinas > 0:
        contexto_harinas_str = f"- Balance analítico de harinas del período: {porc_int}% de fuentes integrales ({total_integrales} registros) y {porc_ref}% de fuentes refinadas ({total_refinadas} registros). Ten muy en cuenta esta proporción exacta para tu evaluación."
    else:
        contexto_harinas_str = "- No se registran datos suficientes de harinas en este período."

    condicion_clinica = prompt_condicional if prompt_condicional else "Evalúa el informe priorizando la calidad de los nutrientes y hábitos saludables."
    frec_str = "\n".join([f"- {cat}: {cant} ingestas" for cat, cant in frecuencias.items()]) if frecuencias else "- No hay frecuencias registradas."

    prompt_1 = (
        f"Actúa como un nutricionista clínico experto y empático. Contexto clínico del paciente:\n{condicion_clinica}\n"
        f"{contexto_harinas_str}\n"
        f"Redacta un diagnóstico y análisis nutricional global puramente cualitativo del mes {mes_str}.\n"
        f"Frecuencia de consumo por grupos alimentarios:\n{frec_str}\n\n"
        f"INSTRUCCIONES ESTRICTAS:\n"
        f"1. PROHIBIDO incluir números, métricas, porcentajes, gramos, calorías, cálculos matemáticos o fórmulas (ni IMC, ni calorías consumidas, ni déficits, ni 'kcal', ni 'g').\n"
        f"2. Céntrate exclusivamente en consejos de hábitos, interpretación de patrones de conducta alimentaria y orientaciones prácticas sobre cómo mejorar la calidad de las ingestas de forma sencilla.\n"
        f"3. Mantén un tono sumamente humano, profesional, constructivo y directo (ni saludos ni introducciones).\n"
        f"4. IMPORTANTE: Redacta toda la respuesta estrictamente en el idioma {nombre_lenguaje}.\n"
        f"Cierra obligatoriamente con un punto final y completa todas las ideas sin cortar el texto."
    )

    prompt_2 = (
        f"Siguiendo con el caso anterior, redacta una lista numerada exactamente del 1 al 5 con alimentos o grupos de alimentos específicos que el paciente debería incorporar.\n"
        f"REQUISITO ESTRICTO: Escribí únicamente el nombre del alimento o categoría de forma directa (máximo 3 o 4 palabras por ítem), sin explicaciones, sin porciones en gramos, sin calorías y sin descripciones largas.\n"
        f"IMPORTANTE: Redacta los elementos estrictamente en el idioma {nombre_lenguaje}.\n"
        f"Cierra con un punto final."
    )

    prompt_3 = (
        f"Finalmente, redacta una lista numerada exactamente del 1 al 5 con alimentos o hábitos alimentarios a reducir o evitar.\n"
        f"REQUISITO ESTRICTO: Escribí únicamente el concepto de forma directa, sin explicaciones numéricas ni porcentajes, acompañado al final de un párrafo breve sobre estrategia de hidratación y hábitos sostenibles.\n"
        f"IMPORTANTE: Redacta todo estrictamente en el idioma {nombre_lenguaje}.\n"
        f"Cierra estrictamente con un punto final; no dejes ninguna oración inconclusa."
    )

    prompt_auditor_base = (
        f"Actúa como un médico supervisor estricto y auditor de calidad. "
        f"Revisa el siguiente informe nutricional:\n\n"
        f"--- INFORME A EVALUAR ---\n{{informe_completo}}\n-------------------------\n\n"
        f"Criterios de rechazo obligatorios:\n"
        f"1. Si incluye consejos ecológicos, de reciclaje, plásticos o electrodomésticos.\n"
        f"2. Si la sección 1 contiene números, gramos, calorías o fórmulas matemáticas (como IMC).\n"
        f"3. Si las listas de incorporar o reducir tienen más o menos de 5 elementos, o si hay texto truncado al final.\n"
        f"Si el informe cumple perfectamente con todo, responde únicamente con la palabra 'OK'."
    )

    max_intentos = 3 
    informe_candidato = None

    for intento_actual in range(1, max_intentos + 1):
        try:
            logger.info(f"Generando informe mensual auditado para usuario {user_id} (Intento {intento_actual}/{max_intentos})")

            texto_p1 = await asyncio.to_thread(ejecutar_consulta_ia, prompt=prompt_1, max_tokens=900, temperature=0.3)
            await asyncio.sleep(2)

            texto_p2 = await asyncio.to_thread(ejecutar_consulta_ia, prompt=prompt_2, max_tokens=400, temperature=0.3)
            await asyncio.sleep(2)

            texto_p3 = await asyncio.to_thread(ejecutar_consulta_ia, prompt=prompt_3, max_tokens=700, temperature=0.3)
            await asyncio.sleep(2)

            informe_candidato = (
                f"<b>1. DIAGNÓSTICO NUTRICIONAL GLOBAL</b><br/>{texto_p1}<br/><br/>"
                f"<b>2. ALIMENTOS A INCORPORAR</b><br/>{texto_p2}<br/><br/>"
                f"<b>3. ALIMENTOS A REDUCIR Y HÁBITOS</b><br/>{texto_p3}"
            )

            prompt_auditor_final = prompt_auditor_base.format(informe_completo=informe_candidato)
            modelo_rev = globals().get('GROQ_REVISOR', 'qwen/qwen3.8-27b')
            
            veredicto = await asyncio.to_thread(
                ejecutar_consulta_ia, 
                prompt=prompt_auditor_final, 
                max_tokens=100, 
                temperature=0.1, 
                modelo_override=modelo_rev
            )

            if not veredicto or veredicto.strip() == "":
                modelo_rev_2 = globals().get('GROQ_REVISION_2', 'openai/gpt-oss-20b')
                veredicto = await asyncio.to_thread(
                    ejecutar_consulta_ia, 
                    prompt=prompt_auditor_final, 
                    max_tokens=100, 
                    temperature=0.1, 
                    modelo_override=modelo_rev_2
                )

            veredicto_limpio = veredicto.strip().upper() if veredicto else ""

            if "OK" in veredicto_limpio and "RECHAZ" not in veredicto_limpio:
                return informe_candidato

        except Exception as e:
            logger.error(f"Error en intento {intento_actual} para usuario {user_id}: {e}")

        if intento_actual < max_intentos:
            await asyncio.sleep(5)

    return informe_candidato if informe_candidato else None

async def procesar_informe_inicial_ia(datos_usuario: dict) -> tuple[str, io.BytesIO]:
    user_id = datos_usuario.get('user_id')
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    nombre = datos_usuario.get('nombre', 'Paciente')
    edad = datos_usuario.get('edad', 0)
    sexo = datos_usuario.get('sexo', 'M')
    altura = datos_usuario.get('altura', 0)
    peso = datos_usuario.get('peso', 0)
    peso_ideal = datos_usuario.get('peso_ideal', 0)
    peso_etapa = datos_usuario.get('peso_etapa', peso)
    get_calorias = datos_usuario.get('get', 2000)
    profesional = str(datos_usuario.get('profesional', '')).strip()
    
    ritmo_elegido = str(datos_usuario.get('ritmo', 'moderado')).lower()

    if "tranquilo" in ritmo_elegido or "lento" in ritmo_elegido or "1" in ritmo_elegido:
        texto_orientacion = traducciones.get("05_bot_inf_gradual", "Has seleccionado un enfoque gradual. En esta etapa, el objetivo principal es que te familiarices con el registro de tus comidas sin estrés. No busques la perfección inmediata; concéntrate en observar tus porciones actuales, mantenerte hidratado y sumar un poco más de movimiento a tu rutina diaria. La constancia a largo plazo es más importante que la velocidad.")
    elif "intenso" in ritmo_elegido or "rapido" in ritmo_elegido or "rápido" in ritmo_elegido or "3" in ritmo_elegido:
        texto_orientacion = traducciones.get("05_bot_inf_exigente", "Has seleccionado un enfoque más exigente. Esta etapa requiere mayor disciplina en el control de las porciones y constancia en tu actividad física. Es fundamental que registres tus ingestas con precisión para asegurar que el déficit energético se mantenga dentro de los parámetros calculados. Escucha a tu cuerpo y prioriza el descanso.")
    else:
        texto_orientacion = traducciones.get("05_bot_inf_equilibrado", "Has seleccionado un enfoque equilibrado. Esta etapa busca un balance entre resultados y flexibilidad. El objetivo es que comiences a estructurar tus comidas principales, reduzcas los picoteos innecesarios y mantengas una actividad física regular. Es el ritmo ideal para construir hábitos sólidos.")

    get_val = float(get_calorias) if get_calorias > 0 else 2000.0
    factor_prot = 1.5 if str(sexo).upper() in ['M', 'MASCULINO'] else 1.2
    meta_cal = int(round(get_val * 0.85))
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
        t_ind_prof = traducciones.get("05_bot_pdf_indicaciones", "<i>(Aquí se incluirán las indicaciones específicas redactadas por tu especialista de cabecera en el próximo reporte clínico).</i>")
        story.append(Paragraph(f"<b>{t_espacio_prof}</b>", styles['Heading2']))
        story.append(Spacer(1, 6))
        story.append(Paragraph(t_ind_prof, indicaciones_style))
    else:
        t_orientacion = traducciones.get("05_bot_pdf_orientacion", "ℹ️ Orientación General del Sistema:")
        story.append(Paragraph(f"<b>{t_orientacion}</b>", styles['Heading2']))
        story.append(Spacer(1, 6))
        story.append(Paragraph(texto_orientacion, body_style))
    
    doc.build(story)
    pdf_buffer.seek(0)
    
    return texto_orientacion, pdf_buffer
           
async def obtener_recomendacion_ia(prompt: str, es_semanal: bool = False, user_id=None):
    """Función auxiliar para obtener recomendaciones de IA utilizando las variables globales de modelos."""
    try:
        # Seleccionamos el modelo global correspondiente de forma dinámica
        modelo = globals().get('GROQ_TEXTO', "openai/gpt-oss-120b")
        
        # Si quisieras diferenciar un modelo secundario o específico para semanales, 
        # puedes usar otra global (ej: GROQ_REVISION_2), pero lo ideal es mantener 
        # la consistencia con la constante global principal o la que prefieras.
        
        system_msg = "Eres un nutricionista clínico experto, empático y constructivo."
        
        # Llamamos a nuestra función central robusta que ya maneja clientes y reintentos
        respuesta = await asyncio.to_thread(
            ejecutar_consulta_ia,
            prompt=prompt,
            max_tokens=500,
            temperature=0.4,
            system_prompt=system_msg,
            modelo_override=modelo
        )
        
        return respuesta if respuesta else ""
        
    except Exception as e:
        logger.error(f"Error en obtener_recomendacion_ia: {e}")
        return ""

async def analizar_imagen_con_groq(base64_image: str, user_id=None):
    """Analiza una imagen general usando el modelo multimodal global con filtro de rechazo."""
    client = globals().get('client_ai') or globals().get('groq_client')
    if not client:
        api_key = globals().get('GROQ_API_KEY') or os.getenv("GROQ_API_KEY")
        if not api_key:
            logger.error("⚠️ GROQ_API_KEY no configurada para análisis de imagen.")
            return {"items": [], "tipo": "Rechazo"}
        from groq import Groq
        client = Groq(api_key=api_key)

    nombre_lenguaje = obtener_nombre_lenguaje_ia(user_id)
    modelo_foto = globals().get('GROQ_FOTO', "qwen/qwen3.8-27b")

    system_prompt = (
        f"Sos un asistente inteligente de nutrición y salud. El usuario se comunica en su idioma ({nombre_lenguaje}). "
        f"Analizá la imagen provista. Tu tarea es determinar si la imagen corresponde claramente a un plato de comida, bebida, menú o producto alimenticio individual para registrar una ingesta.\n\n"
        f"REGLAS DE CLASIFICACIÓN:\n"
        f"1. Si es comida, bebida o producto comestible, desglósalo ítem por ítem en el JSON con sus macronutrientes estimados y poné 'tipo': 'Comida'.\n"
        f"2. Si la imagen muestra paisajes, objetos inanimados, personas, animales, ropa, facturas de servicios o escenarios generales (como una parrilla gigante de restaurante, buffets masivos donde no se distingue un plato, o fotos borrosas/irrelevantes), debés clasificarla obligatoriamente como 'Rechazo' y dejar la lista de 'items' vacía ([]).\n\n"
        f"Devolvé EXCLUSIVAMENTE un JSON con este formato exacto:\n"
        "{\n"
        '  "items": [\n'
        '    {"alimento": "nombre del alimento en ' + nombre_lenguaje + '", "peso": 0.0, "calorias": 0.0, "proteinas": 0.0, "grasas": 0.0, "carbohidratos": 0.0, "fibras": 0.0}\n'
        "  ],\n"
        '  "tipo": "Comida" o "Rechazo"\n'
        "}"
    )

    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=modelo_foto,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": system_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        if response and response.choices:
            content = response.choices[0].message.content
            if content:
                return json.loads(content.strip())

    except Exception as e:
        logger.error(f"⚠️ Error analizando imagen con Groq: {e}")

    return {"items": [], "tipo": "Rechazo"}
            
def detectar_codigo_con_groq(contenido_entrada):
    """Detecta y extrae códigos de barras, QR o referencias numéricas usando la IA global."""
    try:
        client = globals().get('client_ai') or globals().get('groq_client')
        if not client:
            api_key = globals().get('GROQ_API_KEY') or os.getenv("GROQ_API_KEY")
            if not api_key:
                logger.error("⚠️ GROQ_API_KEY no configurada para detección de códigos.")
                return None
            from groq import Groq
            client = Groq(api_key=api_key)

        # Usamos el modelo global de texto principal o secundario para procesar la extracción
        modelo = globals().get('GROQ_REVISION_2', globals().get('GROQ_TEXTO', "openai/gpt-oss-120b"))

        system_prompt = (
            "Eres un asistente especializado en extracción de códigos numéricos, códigos de barras o referencias de productos. "
            "Analiza la entrada provista por el usuario y extrae únicamente el número de código de barras o identificación del producto. "
            "Devuelve exclusivamente un JSON con este formato exacto:\n"
            '{\n  "codigo": "numero_detectado_o_vacio"\n}'
        )

        response = client.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(contenido_entrada)}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )

        if response and response.choices:
            content = response.choices[0].message.content
            if content:
                resultado = json.loads(content.strip())
                return resultado.get("codigo")

    except Exception as e:
        logger.error(f"⚠️ Error detectando código con IA: {e}")

    return None

# =====================================================================================================================================
#                FINAL                          FUNCIONES IA GROQ                                     FINAL
# =====================================================================================================================================

# ======================================================================================================================================
#                  INICIO               COMANDOS CONFIRMACION FUNCIONES BOTONES                    INICIO
# ======================================================================================================================================

#                  INICIO               INTERFAZ Y RENDER DE CONFIRMACIÓN                      INICIO
# ======================================================================================================================================


async def render_confirmation_screen(msg_or_query, context):
    user_id = msg_or_query.from_user.id if hasattr(msg_or_query, 'from_user') and msg_or_query.from_user else (msg_or_query.message.from_user.id if hasattr(msg_or_query, 'message') and msg_or_query.message and hasattr(msg_or_query.message, 'from_user') and msg_or_query.message.from_user else None)
    lang = obtener_idioma_usuario(user_id) if user_id and 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    items = context.user_data.get('pending_items', [])
    fecha = context.user_data.get('pending_fecha', obtener_ahora_arg().strftime("%Y-%m-%d"))
    momento = context.user_data.get('pending_momento', 'Comida')

    if momento == 'Actividad':
        t_reg_act = traducciones.get('06_bot_reg_actividad', "📝 <b>Registro de Actividad:</b>")
        t_fecha = traducciones.get('06_bot_label_fecha', "📅 Fecha")
        txt = f"{t_reg_act}\n{t_fecha}: `{fecha}`\n\n"
    else:
        t_conf_ing = traducciones.get('06_bot_conf_ingesta', "📝 <b>Confirmación de Ingesta:</b>")
        t_fecha = traducciones.get('06_bot_label_fecha', "📅 Fecha")
        t_momento = traducciones.get('06_bot_label_momento', "Momento")
        txt = f"{t_conf_ing}\n{t_fecha}: `{fecha}` | {t_momento}: `{momento}`\n\n"

    for idx, item in enumerate(items, start=1):
        peso_total = item.get('peso', 0)
        cal_total = item.get('calorias', 0)
        prot_total = item.get('proteinas', 0)
        grasas_total = item.get('grasas', 0)
        fibras_total = item.get('fibras', 0)
        
        alimento_str = item.get('alimento_display') or item.get('alimento', item.get('nombre', ''))
        alimento_limpio = alimento_str.replace('§', '').strip()

        if momento == 'Actividad':
            txt += f"<b>{idx}. {alimento_limpio}</b>: `{cal_total:.1f} kcal`\n"
        else:
            t_calorias = traducciones.get('06_bot_macro_calorias', "Calorías")
            t_proteinas = traducciones.get('06_bot_macro_proteinas', "Proteínas")
            t_grasas = traducciones.get('06_bot_macro_grasas', "Grasas tot.")
            t_fibras = traducciones.get('06_bot_macro_fibras', "Fibras")

            txt += f"<b>{idx}. {alimento_limpio}</b> ({peso_total:.1f}g):\n"
            txt += f"   • {t_calorias}: `{cal_total:.1f} kcal`\n"
            txt += f"   • {t_proteinas}: `{prot_total:.1f} g`\n"
            txt += f"   • {t_grasas}: `{grasas_total:.1f} g`\n"
            txt += f"   • {t_fibras}: `{fibras_total:.1f} g`\n\n"

    keyboard = []
    
    if momento != 'Actividad':
        momentos_config = [
            ("Desayuno", "🌅 08-11"),
            ("Almuerzo", "☀️ 11-16"),
            ("Merienda", "☕ 16-20"),
            ("Cena", "🌙 20-00")
        ]
        
        m_buttons = []
        for nombre_momento, etiqueta_visual in momentos_config:
            # Estado al final para no romper el ancho de la botonera
            estado = "✅" if nombre_momento.lower() == momento.lower() else "⏰"
            m_buttons.append(InlineKeyboardButton(f"{etiqueta_visual} {estado}", callback_data=f"set_m_{nombre_momento}"))
        keyboard.append(m_buttons)

    for idx, item in enumerate(items, start=1):
        nombre_corto = item.get('alimento', item.get('nombre', ''))[:10]
        keyboard.append([
            InlineKeyboardButton(f"#{idx} {nombre_corto}", callback_data=f"noop_{idx}"),
            InlineKeyboardButton("📝", callback_data=f"edit_item_{idx}"),  # Cambiado a anotador
            InlineKeyboardButton("❌", callback_data=f"del_item_{idx}")
        ])

    hoy_str = obtener_ahora_arg().strftime("%Y-%m-%d")
    ayer_str = (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    hoy_label = obtener_ahora_arg().strftime("%d/%m")
    ayer_label = (obtener_ahora_arg() - timedelta(days=1)).strftime("%d/%m")
    
    mark_hoy = "✅ " if fecha == hoy_str else ""
    mark_ayer = "✅ " if fecha == ayer_str else ""
    mark_otro = "✅ " if fecha not in [hoy_str, ayer_str] else ""

    keyboard.append([
        InlineKeyboardButton(f"{mark_hoy}🗓️ {hoy_label}", callback_data="set_d_hoy"),
        InlineKeyboardButton(f"{mark_ayer}🗓️ {ayer_label}", callback_data="set_d_ayer"),
        InlineKeyboardButton(f"{mark_otro}📅✏️", callback_data="set_d_otro")  # Cambiado a calendario con lápiz
    ])

    keyboard.append([
        InlineKeyboardButton("🗑️", callback_data="cancel_entry"),
        InlineKeyboardButton("💾", callback_data="confirm_save")
    ])

    markup = InlineKeyboardMarkup(keyboard)

    if hasattr(msg_or_query, 'edit_message_text'):
        await msg_or_query.edit_message_text(txt, reply_markup=markup, parse_mode="Markdown")
    elif hasattr(msg_or_query, 'edit_text'):
        await msg_or_query.edit_text(txt, reply_markup=markup, parse_mode="Markdown")
    else:
        msg_id = context.user_data.get('last_menu_msg_id')
        chat_id = msg_or_query.effective_chat.id if hasattr(msg_or_query, 'effective_chat') else None
        
        editado = False
        if msg_id and chat_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=msg_id, text=txt, reply_markup=markup, parse_mode="Markdown"
                )
                editado = True
            except Exception:
                editado = False

        if not editado and hasattr(msg_or_query, 'message') and msg_or_query.message:
            nuevo_msg = await msg_or_query.message.reply_text(txt, reply_markup=markup, parse_mode="Markdown")
            context.user_data['last_menu_msg_id'] = nuevo_msg.message_id            

async def procesar_y_mostrar_confirmacion(data_json, msg_obj, context):

    items = data_json.get("items", [])
    tipo = data_json.get("tipo", "Comida")
    
    total_calorias = sum(float(item.get("calorias", 0)) for item in items)
    
    if not items or (total_calorias == 0 and tipo != "Actividad"):
        try: await msg_obj.delete()
        except Exception: pass
        return

    # 🛑 FILTRO DE CORDURA ANTI-LOCURAS / ERRORES DE TIPEO (Comida y Actividad)
    magnitud_calorica = abs(total_calorias)
    limite_exceso = 1000 if tipo == "Actividad" else 2200

    if magnitud_calorica > limite_exceso:
        lang = obtener_idioma_usuario(msg_obj.chat_id) if 'obtener_idioma_usuario' in globals() else 'es'
        traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
        
        if tipo == "Actividad":
            txt_exceso = traducciones.get(
                "06_bot_act_limite_superado",
                "⚠️ **Límite de actividad superado**\n\n"
                f"El gasto energético ingresado (`{magnitud_calorica:.0f} kcal`) supera el límite máximo permitido por registro (1.000 kcal).\n\n"
                "Si realizaste un entrenamiento muy extenso, podés dividirlo en dos registros separados (ej: turno mañana y turno tarde)."
            )
        else:
            txt_exceso = traducciones.get(
                "06_bot_comida_limite_superado",
                "⚠️ **Cantidad excesiva detectada**\n\n"
                f"El registro ingresado (`{magnitud_calorica:.0f} kcal`) supera el límite razonable para una sola ingesta.\n\n"
                "Por favor, ingresá las porciones individuales reales de tu plato."
            )
        
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
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    if data == "presion_guardar_directo":
        datos_presion = context.user_data.pop('pending_presion_foto', None)
        context.user_data.pop('awaiting_presion_nota', None)
        
        if datos_presion:
            alta = datos_presion.get("alta")
            baja = datos_presion.get("baja")
            pulsaciones = datos_presion.get("pulsaciones")
            
            guardar_presion_db(user_id, alta, baja, pulsaciones, nota="")
            
            pul_txt = f" | Pulsaciones: `{pulsaciones:.0f} lpm`" if pulsaciones > 0 else ""
            
            msg_base = traducciones.get(
                "06_bot_presion_exito", 
                "✅ **¡Presión arterial registrada con éxito!**\n\n• Presión Alta: `{alta:.0f} mmHg`\n• Presión Baja: `{baja:.0f} mmHg`{pul_txt}"
            )
            txt_exito = msg_base.format(alta=alta, baja=baja, pul_txt=pul_txt)
            
            await query.edit_message_text(txt_exito, parse_mode="Markdown")
        else:
            txt_expirada = traducciones.get("06_bot_presion_expirada", "⚠️ Los datos temporales de la presión expiraron.")
            await query.edit_message_text(txt_expirada)

    elif data == "presion_pedir_nota":
        context.user_data['awaiting_presion_nota'] = True
        txt_pedir_nota = traducciones.get("06_bot_pedir_nota_presion", "✏️ Por favor, escribí la nota o detalle para este registro de presión (o escribí `cancelar` para anular):")
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
                
@requiere_registro
async def callback_handler_actividades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    if data in ["act_tipo_texto", "act_ind_texto"]:
        context.user_data['awaiting_activity_text'] = True
        txt_escribir = traducciones.get("06_bot_escribir_actividad", "📝 Escribí la actividad (Ej: `50 minutos de caminata a velocidad moderada`):")
        msg_solic = await query.message.reply_text(txt_escribir, parse_mode="Markdown")
        context.user_data['msg_solicitud_activity_id'] = msg_solic.message_id
    elif data in ["act_tipo_audio", "act_ind_audio"]:
        context.user_data['awaiting_activity_voice'] = True
        txt_act_voz = traducciones.get('06_bot_act_voz', "🎤 Enviá una nota de voz describiendo tu actividad física.")
        await query.message.reply_text(txt_act_voz, parse_mode="Markdown")
    elif data in ["act_cancelar", "act_ind_cancelar"]:
        context.user_data.pop('awaiting_activity_text', None)
        context.user_data.pop('awaiting_activity_voice', None)
        txt_act_canc = traducciones.get('06_bot_act_cancelada', "❌ Registro de actividad cancelado.")
        await query.edit_message_text(txt_act_canc)

@requiere_registro
async def callback_handler_eliminacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    if data in ["del_cambiar_fecha", "del_volver_momentos"]:
        await mostrar_selector_momento_eliminar(query, context)
    elif data == "del_d_hoy":
        context.user_data['del_fecha'] = obtener_ahora_arg().strftime("%Y-%m-%d")
        await mostrar_selector_momento_eliminar(query, context)
    elif data == "del_d_ayer":
        context.user_data['del_fecha'] = (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d")
        await mostrar_selector_momento_eliminar(query, context)
    elif data == "del_d_otro":
        context.user_data['awaiting_del_custom_date'] = True
        txt_fecha_rev = traducciones.get("06_bot_ingresar_fecha_revision", "📅 Ingresá la fecha que querés revisar (Ej: `2026-08-15` o `15/08`):")
        msg = await query.message.reply_text(txt_fecha_rev, parse_mode="Markdown")
        context.user_data['msg_solicitud_del_fecha_id'] = msg.message_id
    elif data.startswith("del_mom_"):
        context.user_data['del_momento'] = data.replace("del_mom_", "")
        await render_pantalla_items_eliminar(query, user_id, context)
    elif data.startswith("del_reg_"):
        eliminar_registro_por_id(user_id, int(data.replace("del_reg_", "")))
        await render_pantalla_items_eliminar(query, user_id, context)
    elif data == "del_borrar_todo_momento":
        fecha, momento = context.user_data.get('del_fecha'), context.user_data.get('del_momento')
        df = obtener_datos_usuario(user_id)
        if not df.empty and 'Fecha' in df.columns and 'Momento' in df.columns:
            for _, r in df[(df['Fecha'] == fecha) & (df['Momento'].str.lower() == momento.lower())].iterrows():
                if 'id_registro' in r: eliminar_registro_por_id(user_id, int(r['id_registro']))
        await mostrar_selector_momento_eliminar(query, context)

@requiere_registro
async def callback_handler_reportes_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data.startswith("resumen_mes_") or data in ["resumen_volver_menu", "resumen_mes_menu_otros"]:
        await mostrar_resumen_mes(update, context)
    elif data.startswith("descargar_pdf_resumen_"):
        await generar_y_enviar_pdf_resumen(query, context)
    elif data.startswith("descargar_pdf_diario_"):
        f_str = data.replace("descargar_pdf_diario_", "")
        df = obtener_datos_usuario(user_id)
        pdf = generar_pdf_diario_bytes(f_str, df[df['Fecha'] == f_str] if not df.empty else pd.DataFrame(), user_id)
        await context.bot.send_document(chat_id=query.message.chat_id, document=pdf, filename=f"📄 D_{f_str}.pdf")
    elif data.startswith("descargar_pdf_presion_"):
        mes_str = data.replace("descargar_pdf_presion_", "")
        df_p = obtener_datos_presion_db(user_id)
        pdf_p = generar_pdf_presion_bytes(mes_str, df_p[df_p['Fecha_Dia'].str.startswith(mes_str)] if not df_p.empty else pd.DataFrame(), user_id)
        await context.bot.send_document(chat_id=query.message.chat_id, document=pdf_p, filename=f"📄 P_{mes_str}.pdf")
    elif data.startswith("enviar_inf_"):
        target_user_id = int(data.replace("enviar_inf_", ""))
        ahora = obtener_ahora_arg()
        mes_target = (ahora.replace(day=1) - timedelta(days=1)).strftime("%Y-%m") if ahora.day <= 7 else ahora.strftime("%Y-%m")
        await procesar_y_enviar_informe_mensual(context, target_user_id, target_user_id, mes_target, False, True)
        
#              INICIO                      FUNCIONES MANEJADORES MODULARIZADOS (NUEVOS)                   INICIO
# =====================================================================================================================================

async def _sub_manejar_texto_actividad(update, context, raw_text, chat_id):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    msg_solic = context.user_data.pop('msg_solicitud_activity_id', None)
    if msg_solic:
        try: await context.bot.delete_message(chat_id=chat_id, message_id=msg_solic)
        except Exception: pass
    try: await update.message.delete()
    except Exception: pass

    context.user_data['awaiting_activity_text'] = False
    
    txt_analizando = traducciones.get('06_bot_analizando_act', "🏃 Analizando actividad física y calculando calorías...")
    msg_espera = await update.message.reply_text(txt_analizando)
    try:
        res = analizar_con_groq(f"Actividad física: {raw_text}. Devuelve JSON con alimento y calorias.")
        items = res.get('items', [])
        kcal = float(items[0].get('calorias', 0)) if items else 0.0
        desc = str(items[0].get('alimento', raw_text)) if items else raw_text
        
        item_act = {"alimento": desc, "peso": 0, "calorias": -abs(kcal), "proteinas": 0, "grasas": 0, "carbohidratos": 0, "fibras": 0}
        
        context.user_data.update({'pending_items': [item_act], 'pending_fecha': obtener_ahora_arg().strftime("%Y-%m-%d"), 'pending_momento': 'Actividad'})
        await msg_espera.delete()
        
        txt_analizada = traducciones.get('06_bot_act_analizada', "📋 Actividad analizada:")
        msg_menu = await update.message.reply_text(txt_analizada)
        context.user_data['last_menu_msg_id'] = msg_menu.message_id
        await render_confirmation_screen(msg_menu, context)
    except Exception as e:
        txt_err = traducciones.get('06_bot_error_proc_act', "❌ Error al procesar actividad: {e}").format(e=e)
        await msg_espera.edit_text(txt_err)
                
async def _sub_manejar_fecha_eliminacion(update, context, raw_text, chat_id):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

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
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

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

async def _sub_manejar_fecha_personalizada_ingesta(update, context, raw_text, chat_id):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

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
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    idx = context.user_data.get('editing_item_idx')
    items = context.user_data.get('pending_items', [])
    momento_actual = context.user_data.get('pending_momento', 'Comida')

    if items and 0 <= idx < len(items):
        item_previo = items[idx]
        txt_act = traducciones.get('06_bot_actualizando', "⏳ Actualizando valores...")
        msg_espera = await update.message.reply_text(txt_act)
        
        try:
            if momento_actual == 'Actividad':
                nuevo_kcal = float(re.sub(r'[^\d.]', '', raw_text.replace(',', '.')))
                item_previo['calorias'] = -abs(nuevo_kcal)
                
            elif item_previo.get('es_plantilla'):
                # Es una comida precargada: solo multiplicamos unidades
                nuevo_mult = float(raw_text.replace(',', '.'))
                desc_base = item_previo['desc_base']
                mult_str = f"{int(nuevo_mult)}" if nuevo_mult.is_integer() else f"{nuevo_mult}"
                nueva_desc = f"{desc_base} x {mult_str}"
                
                item_previo.update({
                    "alimento": nueva_desc,
                    "alimento_display": nueva_desc,
                    "peso": item_previo['peso_base'] * nuevo_mult,
                    "calorias": item_previo['cal_base'] * nuevo_mult,
                    "proteinas": item_previo['prot_base'] * nuevo_mult,
                    "grasas": item_previo['gras_base'] * nuevo_mult,
                    "carbohidratos": item_previo['carb_base'] * nuevo_mult,
                    "fibras": item_previo['fibr_base'] * nuevo_mult
                })
                
            else:
                # Lógica normal para comidas ingresadas por IA
                peso_prev = float(item_previo.get('peso', 0))
                nuevo_p, nueva_d = peso_prev, item_previo.get('alimento', '')
                if ',' in raw_text:
                    p = raw_text.split(',', 1)
                    if p[0].strip(): nueva_d = p[0].strip()
                    if p[1].strip(): nuevo_p = float(re.sub(r'[^\d.]', '', p[1].replace(',', '.')))
                else:
                    try: nuevo_p = float(re.sub(r'[^\d.]', '', raw_text.replace(',', '.')))
                    except ValueError: nueva_d = raw_text

                factor = (nuevo_p / peso_prev) if peso_prev > 0 else 1.0
                item_previo.update({
                    "alimento": nueva_d, "alimento_display": nueva_d.replace('§', '').strip(), "peso": nuevo_p,
                    "calorias": float(item_previo.get('calorias', 0)) * factor, "proteinas": float(item_previo.get('proteinas', 0)) * factor,
                    "grasas": float(item_previo.get('grasas', 0)) * factor, "carbohidratos": float(item_previo.get('carbohidratos', 0)) * factor,
                    "fibras": float(item_previo.get('fibras', 0)) * factor
                })
                
            items[idx] = item_previo
            context.user_data['pending_items'] = items
            await msg_espera.delete()
            try: await update.message.delete()
            except Exception: pass
            
        except Exception as e:
            txt_err_ed = traducciones.get('06_bot_error_editar', "❌ Error al editar: {e}").format(e=e)
            await msg_espera.edit_text(txt_err_ed)

    context.user_data.update({'awaiting_edit_item_val': False})
    context.user_data.pop('editing_item_idx', None)
    
    last_id = context.user_data.get('last_menu_msg_id')
    if last_id:
        try:
            target = await context.bot.get_message(chat_id=chat_id, message_id=last_id)
            await render_confirmation_screen(target, context)
            return
        except Exception: pass
        
    await render_confirmation_screen(update, context)
    
async def _sub_manejar_plantilla_comida(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_text, user_id):
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    contenido = raw_text[1:].strip()
    partes = [p.strip() for p in contenido.split(',')]
    nombre_plantilla = partes[0].upper()
    mult = float(partes[1]) if len(partes) > 1 else 1.0

    plantillas = obtener_comidas_usuario(user_id)
    plantilla = next((p for p in plantillas if str(p.get('Nombre', '')).strip().upper() == nombre_plantilla), None)

    if plantilla:
        p_b, c_b, pr_b, g_b, cb_b, f_b = plantilla.get('Peso', 0), plantilla.get('Calorias', 0), plantilla.get('Proteinas', 0), plantilla.get('Grasas', 0), plantilla.get('Carbohidratos', 0), plantilla.get('Fibras', 0)
        
        desc_limpia = (plantilla.get('Descripcion') or plantilla.get('Nombre', 'Comida')).replace('§', '').strip()
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
        
async def _sub_manejar_ingesta_libre_ia(update, context, raw_text):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    txt_analiz_ia = traducciones.get('06_bot_analizando_texto', "🤖 Analizando texto con Inteligencia Artificial...")
    msg = await update.message.reply_text(txt_analiz_ia)
    try:
        data = analizar_con_groq(raw_text)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        txt_err_ia = traducciones.get('06_bot_error_proc_texto', "❌ Error al procesar el texto: {e}").format(e=e)
        await msg.edit_text(txt_err_ia)

def parsear_fecha_flexible(raw_text):
    txt = raw_text.replace('/', '-').replace('.', '-')
    partes = txt.split('-')
    try:
        if len(partes) == 3:
            if len(partes[0]) == 4: return f"{int(partes[0]):04d}-{int(partes[1]):02d}-{int(partes[2]):02d}"
            return f"{int(partes[2]):04d}-{int(partes[1]):02d}-{int(partes[0]):02d}"
        elif len(partes) == 2:
            return f"{obtener_ahora_arg().year:04d}-{int(partes[1]):02d}-{int(partes[0]):02d}"
    except Exception: pass
    return None

async def _sub_manejar_voz_ingesta(update, context, transcription, msg):
    try:
        data = analizar_con_groq(transcription)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        user_id = update.effective_user.id
        lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
        traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
        txt_err_aud = traducciones.get('06_bot_error_audio', "❌ Error al procesar el audio con IA: {e}").format(e=e)
        logger.error(f"Error procesando voz de ingesta: {e}")
        await msg.edit_text(txt_err_aud)

async def _sub_manejar_voz_actividad(update, context, transcription, msg):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    context.user_data['awaiting_activity_voice'] = False
    perfil_biometrico = obtener_perfil_usuario(user_id)
    
    prompt_ia = f"El usuario realizó una actividad física descrita por voz. Transcripción: '{transcription}'. Calcula las calorías gastadas utilizando estrictamente su perfil biométrico: {perfil_biometrico}. Devolvé un JSON con los campos 'alimento' y 'calorias'."
    resultado_ia = analizar_con_groq(prompt_ia)
    items_ia = resultado_ia.get('items', [])
    
    kcal_estimadas = float(items_ia[0].get('calorias', 0)) if items_ia else 0.0
    desc = str(items_ia[0].get('alimento', transcription)) if items_ia else transcription
    
    item_actividad = {"alimento": desc, "peso": 0, "calorias": -abs(kcal_estimadas), "proteinas": 0, "grasas": 0, "carbohidratos": 0, "fibras": 0}
    
    context.user_data.update({'pending_items': [item_actividad], 'pending_fecha': obtener_ahora_arg().strftime("%Y-%m-%d"), 'pending_momento': 'Actividad'})

    await msg.delete()
    txt_act_aud = traducciones.get('06_bot_act_audio', "📋 Actividad analizada por audio:")
    msg_menu = await update.message.reply_text(txt_act_aud)
    context.user_data['last_menu_msg_id'] = msg_menu.message_id
    await render_confirmation_screen(msg_menu, context)
    
async def _sub_manejar_foto_plato_ia(update, context, base64_image, user_caption, msg):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    txt_analiz_plato = traducciones.get('06_bot_analizando_plato', "🤖 Analizando imagen con Inteligencia Artificial...")
    await msg.edit_text(txt_analiz_plato)

    try:
        data = await analizar_imagen_con_groq(base64_image, user_id)
        
        tipo = str(data.get("tipo", "Comida")).strip().upper()
        items = data.get("items", [])

        # Si la IA determinó que no es comida o la lista está vacía
        if tipo == "RECHAZO" or not items:
            txt_rechazo = traducciones.get(
                '06_bot_foto_rechazada',
                "⚠️ **Imagen no reconocida como ingesta**\n\n"
                "La foto enviada no parece corresponder a un plato de comida o bebida individual. "
                "Por favor, envianos una foto clara de tu plato o escribí la descripción por texto."
            )
            await msg.edit_text(txt_rechazo, parse_mode="Markdown")
            return
            
        await procesar_y_mostrar_confirmacion(data, msg, context)

    except Exception as e:
        logger.error(f"Error al procesar plato por imagen para usuario {user_id}: {e}")
        
        txt_error_imagen = traducciones.get(
            '06_bot_error_imagen_fallida', 
            "⚠️ No se pudo procesar la imagen correctamente.\n\n"
            "Por favor, ingresá la descripción de tu plato escribiéndola por **texto** o enviando una nota de **voz**."
        )
        await msg.edit_text(txt_error_imagen, parse_mode="Markdown")
            
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
async def callback_btn_fechas_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
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
        
@requiere_registro
async def callback_btn_editar_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
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
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
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
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    context.user_data.pop('pending_items', None)
    context.user_data.pop('last_menu_msg_id', None)
    txt_canc = traducciones.get('06_bot_reg_canc', "🗑️ Registro cancelado.")
    await query.edit_message_text(txt_canc)

async def callback_btn_guardar_registro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
    items = context.user_data.get('pending_items', [])
    fecha = context.user_data.get('pending_fecha')
    momento = context.user_data.get('pending_momento')

    if items and fecha and momento:
        tipo_registro = "Actividad" if momento == "Actividad" else "Comida"
        guardar_en_sheets(user_id, items, fecha, momento, tipo=tipo_registro)
        
        if momento == "Actividad":
            txt_conf = traducciones.get('06_bot_save_act_exito', f"✅ **¡Actividad guardada exitosamente!**\n📅 `{fecha}`")
        else:
            txt_conf = traducciones.get('06_bot_save_meal_exito', f"✅ **¡Ingesta guardada exitosamente!**\n📅 `{fecha}` | `{momento}`")
            
        await query.edit_message_text(txt_conf, parse_mode="Markdown")
        context.user_data.pop('pending_items', None)
        context.user_data.pop('last_menu_msg_id', None)
    else:
        txt_nodat = traducciones.get('06_bot_no_data', "❌ No se encontraron datos para guardar.")
        await query.edit_message_text(txt_nodat)

# ======================================================================================================================================
#                FINAL                                     COMANDOS CONFIRMACION FUNCIONES BOTONES                        FINAL
# ======================================================================================================================================

# ==================================================================================================================================
#                    INICIO                 COMANDOS COMIDAS Y COMANDOS ACTIVIDAD                                   INCIO  DB OK
# ==================================================================================================================================

#              INICIO                     FUNCIONES COMIDAS                   INICIO
# =============================================================================================================================================

def consultar_codigo_barras(barcode: str) -> dict | bool:
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
        
        # 1. Extraemos los valores principales primero
        calorias = float(nutriments.get("energy-kcal_100g", nutriments.get("energy-kcal", 0.0) or 0.0))
        proteinas = float(nutriments.get("proteins_100g", 0.0) or 0.0)
        
        # 2. FILTRO ANTI-TABLAS VACÍAS: Si calorías y proteínas son cero, lo descartamos
        if calorias == 0.0 and proteinas == 0.0:
            return False
            
        # Si pasa el filtro, seguimos extrayendo el resto
        grasas = float(nutriments.get("fat_100g", 0.0) or 0.0)
        carbohidratos = float(nutriments.get("carbohydrates_100g", 0.0) or 0.0)
        fibras = float(nutriments.get("fiber_100g", 0.0) or 0.0)
        
        nombre_alimento = product.get("product_name_es") or product.get("product_name") or "Producto desconocido"
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

def procesar_foto_codigo_barras(base64_image: str) -> dict | bool:
    try:
        image_bytes = base64.b64decode(base64_image)
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            return False
            
        detector = cv2.barcode.BarcodeDetector()
        retval, decoded_info, decoded_type, points = detector.detectAndDecode(img)
        
        if retval and decoded_info:
            for barcode_text in decoded_info:
                if barcode_text and barcode_text.strip():
                    resultado_api = consultar_codigo_barras(barcode_text.strip())
                    if resultado_api:
                        return resultado_api
        return False
    except Exception as e:
        return False

def construir_texto_listado_comidas(user_id, comidas, traducciones=None):
    if traducciones is None:
        traducciones = {}
        
    msg_no_comidas_tpl = traducciones.get("07_bot_no_comidas_precargadas", f"📋 No hay comidas predeterminadas registradas en la hoja 'Comidas_{user_id}'.")
    if not comidas:
        return msg_no_comidas_tpl.format(user_id=user_id)

    msg_titulo_tpl = traducciones.get("07_bot_titulo_listado_comidas", "📋 <b>Listado de Comidas Predeterminadas (Comidas_{user_id}):</b>\n\n")
    txt = msg_titulo_tpl.format(user_id=user_id)
    
    for p in comidas:
        nombre_raw = str(p.get('Nombre', ''))
        desc_raw = str(p.get('Descripcion') or p.get('Momento', ''))
        
        nombre = nombre_raw.replace('§', '').replace('<', '').replace('>', '').strip()
        descripcion = desc_raw.replace('§', '').replace('<', '').replace('>', '').strip()
        
        if descripcion and descripcion.lower() != nombre.lower():
            linea = f"• <b>{nombre}</b>: {descripcion}\n"
        else:
            linea = f"• <b>{nombre}</b>\n"
        
        if len(txt) + len(linea) > 4000:
            msg_mas_comidas = traducciones.get("07_bot_mas_comidas_pdf", "• <i>...y más comidas (ver detalle en el PDF adjunto).</i>\n")
            txt += msg_mas_comidas
            break
            
        txt += linea
        
    return txt
 
# =======================================================================================================================================
@requiere_registro
async def cmd_comidas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
    comidas = obtener_comidas_usuario(user_id)
    
    if not comidas:
        msg_no_comidas = traducciones.get("07_bot_no_comidas_precargadas", f"📋 No hay comidas predeterminadas registradas en la hoja 'Comidas_{user_id}'.")
        await update.message.reply_text(msg_no_comidas.format(user_id=user_id))
        return

    txt = construir_texto_listado_comidas(user_id, comidas, traducciones)
    msg_adjunto = traducciones.get("07_bot_adjunto_pdf_comidas", "\n📄 Te adjuntamos el archivo en PDF completo con todos los macronutrientes a continuación.")
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
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

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
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
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
    client_ai = globals().get('client_ai')
    if not client_ai:
        return ""
    
    prompt = (
        "Analiza esta imagen de un producto comercial. Busca el código de barras y lee atentamente "
        "los números impresos justo debajo de él. "
        "Responde ÚNICAMENTE en formato JSON con la siguiente estructura exacta:\n"
        "{\n"
        '  "tiene_numeros": true/false,\n'
        '  "codigo_numerico": "escribe_aqui_solo_los_numeros_o_vacio"\n'
        "}"
    )
    try:
        response = client_ai.chat.completions.create(
            model=globals().get('GROQ_FOTO', "qwen/qwen3.8-27b"),
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        resultado = json.loads(response.choices[0].message.content)
        if resultado.get("tiene_numeros"):
            return str(resultado.get("codigo_numerico", "")).strip()
    except Exception as e:
        logger.error(f"Error en lectura IA de números de código de barras: {e}")    
    return ""

async def procesar_codigo_ingresado(message_obj, context, barcode_text: str):
    user_id = message_obj.from_user.id
    
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
    msg_analizando = traducciones.get("07_bot_analizando_barra", "🔍 Analizando código de barras y verificando producto...")
    msg_espera = await message_obj.reply_text(msg_analizando)
    
    try:
        resultado_api = consultar_codigo_barras(barcode_text)
        
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

            await msg_espera.delete()
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
    
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
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
    
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
    if context.args:
        nombre_a_borrar = " ".join(context.args).strip()
        
        comida_encontrada = buscar_comida_precargada_exacta(user_id, nombre_a_borrar)
        
        if not comida_encontrada:
            msg_no_enc = traducciones.get("07_bot_comida_no_encontrada", "❌ No se encontró ninguna comida registrada con el nombre exacto: <b>{nombre}</b>.")
            await update.message.reply_text(
                msg_no_enc.format(nombre=nombre_a_borrar),
                parse_mode="HTML"
            )
            return
        
        exito = eliminar_comida_precargada_db(user_id, comida_encontrada['nombre'])
        
        if exito:
            msg_exito = traducciones.get("07_bot_comida_borrada_exito", "✅ La comida <b>{nombre}</b> ha sido eliminada exitosamente de tu planilla.")
            await update.message.reply_text(
                msg_exito.format(nombre=comida_encontrada['nombre']),
                parse_mode="HTML"
            )
        else:
            msg_err_db = traducciones.get("07_bot_error_db_borrar", "❌ Hubo un error en la base de datos al intentar borrar <b>{nombre}</b>.")
            await update.message.reply_text(
                msg_err_db.format(nombre=comida_encontrada['nombre']),
                parse_mode="HTML"
            )
        return

    comidas = obtener_comidas_usuario(user_id)
    
    if not comidas:
        msg_no_reg = traducciones.get("07_bot_no_comidas_borrar", "📋 No hay comidas predeterminadas registradas para eliminar.")
        await update.message.reply_text(msg_no_reg)
        return

    txt = construir_texto_listado_comidas(user_id, comidas, traducciones)
    msg_instruccion = traducciones.get("07_bot_como_borrar_comida", "\n🗑️ <b>¿Cómo borrar una comida?</b>\nCopiá el nombre exacto de la lista de arriba y escribí el comando de la siguiente forma:\n<code>/borracomida Nombre de la Comida</code>")
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
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    context.user_data.pop('del_fecha', None)
    context.user_data.pop('del_momento', None)

    hoy_label = obtener_ahora_arg().strftime("%d/%m")
    ayer_label = (obtener_ahora_arg() - timedelta(days=1)).strftime("%d/%m")

    # 🟢 Actualizado con el icono 🔄🗓️ para selección de otra fecha
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"📅 {hoy_label}", callback_data="del_d_hoy"), 
            InlineKeyboardButton(f"📆 {ayer_label}", callback_data="del_d_ayer")
        ],
        [
            InlineKeyboardButton("🔄  🗓️", callback_data="del_d_otro")
        ]
    ])
    
    msg_txt = traducciones.get("bot_titulo_eliminar_ingestas", "🗑️ **Eliminación de Ingestas / Actividades:**\nSeleccioná el día que querés revisar:")
    await update.message.reply_text(
        msg_txt, 
        reply_markup=keyboard, 
        parse_mode="Markdown"
    )

async def mostrar_selector_momento_eliminar(query_or_msg, context):
    user_id = query_or_msg.from_user.id if hasattr(query_or_msg, 'from_user') else query_or_msg.message.chat_id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    if not context.user_data.get('del_fecha'):
        context.user_data['del_fecha'] = obtener_ahora_arg().strftime("%Y-%m-%d")
        
    fecha = context.user_data.get('del_fecha')
    
    # 🟢 Actualizado el botón de cambiar fecha con 🔄🗓️
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌅 08-11 ⏰", callback_data="del_mom_Desayuno"), InlineKeyboardButton("☀️ 11-16 ⏰", callback_data="del_mom_Almuerzo")],
        [InlineKeyboardButton("☕ 16-20 ⏰", callback_data="del_mom_Merienda"), InlineKeyboardButton("🌙 20-00 ⏰", callback_data="del_mom_Cena")],
        [InlineKeyboardButton("🏃 ⚡", callback_data="del_mom_Actividad")],
        [InlineKeyboardButton("🔄. 🗓️", callback_data="del_cambiar_fecha")]
    ])
    
    txt_tmpl = traducciones.get("bot_txt_sel_momento_del", "📅 Fecha seleccionada: `{fecha}`\n\nSeleccioná el momento o actividad que querés revisar para eliminar:")
    txt = txt_tmpl.format(fecha=fecha)
    
    if hasattr(query_or_msg, 'edit_message_text'):
        await query_or_msg.edit_message_text(txt, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await query_or_msg.message.reply_text(txt, reply_markup=keyboard, parse_mode="Markdown")
                
async def render_pantalla_items_eliminar(query, user_id, context):
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
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌", callback_data="del_salir_pantalla")]
        ])
        try:
            await query.edit_message_text(
                f"⚠️ No se encontraron registros para este momento en la fecha `{fecha}`.",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        except Exception:
            await query.message.reply_text(
                f"⚠️ No se encontraron registros para este momento en la fecha `{fecha}`.",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        return

    txt = f"🗑️ **Eliminar Registros**\n📅 Fecha: `{fecha}` | Momento: `{momento}`\n\n"
    
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
            # 🟢 Actualizado con el tacho de basura (🗑️) para el borrado individual
            keyboard.append([
                InlineKeyboardButton(f"🗑️ {nombre_corto}", callback_data=f"del_reg_{item_id}")
            ])

    # 🟢 Botón de la cruz ahora envía "del_salir_pantalla" en lugar de "del_borrar"
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
    
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
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
        try:
            await query.message.delete()
        except Exception:
            pass

    elif data in ["del_cambiar_fecha", "del_volver_momentos"]:
        await mostrar_selector_momento_eliminar(query, context)     

# =====================================================================================================================================

async def _sub_manejar_edicion_perfil_inputs(update, context, raw_text, chat_id):
    user_id = update.effective_user.id
    ahora = obtener_ahora_arg()
    mes_actual = ahora.strftime("%Y-%m")

    cambio_biometrico = False
    mensaje_exito = ""
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    if context.user_data.get('awaiting_edit_perfil_peso'):
        try:
            nuevo_val = float(raw_text.replace(',', '.'))
            # Delegamos a la función asíncrona usando hilos para no bloquear
            res_cal = await asyncio.to_thread(guardar_perfil_db, user_id, peso=nuevo_val, mes=mes_actual)
            if isinstance(res_cal, dict) and res_cal.get("error"):
                await update.message.reply_text(res_cal["mensaje"], parse_mode="Markdown")
            else:
                msg_ok = traducciones.get("07_bot_peso_actualizado", "✅ Peso actualizado a `{nuevo_val} kg`.").format(nuevo_val=nuevo_val)
                mensaje_exito = res_cal["mensaje"] if isinstance(res_cal, dict) and "mensaje" in res_cal else msg_ok
                cambio_biometrico = True
        except Exception as e:
            msg_err = traducciones.get("07_bot_valor_invalido", "❌ Valor inválido. Ingresá números.")
            await update.message.reply_text(msg_err)
        context.user_data['awaiting_edit_perfil_peso'] = False

    elif context.user_data.get('awaiting_edit_perfil_altura'):
        try:
            nuevo_val = float(raw_text.replace(',', '.'))
            # Usamos la función central segura envuelta en hilo
            await asyncio.to_thread(_core_guardar_perfil_db, user_id, mes_actual, {"ALTURA": nuevo_val})
            msg_ok = traducciones.get("07_bot_altura_actualizada", "✅ Altura actualizada a `{nuevo_val} cm`.").format(nuevo_val=nuevo_val)
            mensaje_exito = msg_ok
            cambio_biometrico = True
        except Exception as e:
            msg_err = traducciones.get("07_bot_valor_invalido", "❌ Valor inválido. Ingresá números.")
            await update.message.reply_text(msg_err)
        context.user_data['awaiting_edit_perfil_altura'] = False

    elif context.user_data.get('awaiting_edit_perfil_cintura'):
        try:
            nuevo_val = float(raw_text.replace(',', '.'))
            await asyncio.to_thread(_core_guardar_usuario_db, user_id, {"cintura_cm": nuevo_val})
            msg_ok = traducciones.get("07_bot_cintura_actualizada", "✅ Cintura actualizada a `{nuevo_val} cm`.").format(nuevo_val=nuevo_val)
            mensaje_exito = msg_ok
            cambio_biometrico = True
        except Exception as e:
            msg_err = traducciones.get("07_bot_valor_invalido", "❌ Valor inválido.")
            await update.message.reply_text(msg_err)
        context.user_data['awaiting_edit_perfil_cintura'] = False

    elif context.user_data.get('awaiting_edit_perfil_cuello'):
        try:
            nuevo_val = float(raw_text.replace(',', '.'))
            await asyncio.to_thread(_core_guardar_usuario_db, user_id, {"cuello_cm": nuevo_val})
            msg_ok = traducciones.get("07_bot_cuello_actualizado", "✅ Cuello actualizado a `{nuevo_val} cm`.").format(nuevo_val=nuevo_val)
            mensaje_exito = msg_ok
            cambio_biometrico = True
        except Exception as e:
            msg_err = traducciones.get("07_bot_valor_invalido", "❌ Valor inválido.")
            await update.message.reply_text(msg_err)
        context.user_data['awaiting_edit_perfil_cuello'] = False

    elif context.user_data.get('awaiting_edit_perfil_cadera'):
        try:
            nuevo_val = float(raw_text.replace(',', '.'))
            await asyncio.to_thread(_core_guardar_usuario_db, user_id, {"cadera_cm": nuevo_val})
            msg_ok = traducciones.get("07_bot_cadera_actualizada", "✅ Cadera actualizada a `{nuevo_val} cm`.").format(nuevo_val=nuevo_val)
            mensaje_exito = msg_ok
            cambio_biometrico = True
        except Exception as e:
            msg_err = traducciones.get("07_bot_valor_invalido", "❌ Valor inválido.")
            await update.message.reply_text(msg_err)
        context.user_data['awaiting_edit_perfil_cadera'] = False

    elif context.user_data.get('awaiting_edit_perfil_nombre'):
        try:
            nuevo_val = str(raw_text).strip()
            await asyncio.to_thread(_core_guardar_usuario_db, user_id, {"Nombre": nuevo_val})
            msg_ok = traducciones.get("07_bot_nombre_actualizado", "✅ Nombre actualizado a `{nuevo_val}`.").format(nuevo_val=nuevo_val)
            await update.message.reply_text(msg_ok, parse_mode="Markdown")
        except Exception as e:
            msg_err = traducciones.get("07_bot_valor_invalido", "❌ Valor inválido.")
            await update.message.reply_text(msg_err)
        context.user_data['awaiting_edit_perfil_nombre'] = False

    elif context.user_data.get('awaiting_edit_perfil_prof'):
        try:
            nuevo_val = str(raw_text).strip()
            await asyncio.to_thread(_core_guardar_usuario_db, user_id, {"profesional": nuevo_val})
            msg_ok = traducciones.get("07_bot_profesional_actualizado", "✅ Profesional actualizado a `{nuevo_val}`.").format(nuevo_val=nuevo_val)
            await update.message.reply_text(msg_ok, parse_mode="Markdown")
        except Exception as e:
            msg_err = traducciones.get("07_bot_valor_invalido", "❌ Valor inválido.")
            await update.message.reply_text(msg_err)
        context.user_data['awaiting_edit_perfil_prof'] = False

    # --- RECÁLCULO DINÁMICO INMEDIATO ---
    if cambio_biometrico and mensaje_exito:
        try:
            # Obtenemos los datos completos del usuario con la BD ya actualizada (en hilo asíncrono)
            perfil = await asyncio.to_thread(obtener_datos_completos_usuario, user_id, mes_target=mes_actual)
            
            if perfil:
                # Extraer métricas clave
                peso = parse_raw_val(perfil.get('PESO', perfil.get('Peso', 0)))
                altura = parse_raw_val(perfil.get('ALTURA', perfil.get('Altura', 0)))
                edad = parse_raw_val(perfil.get('EDAD', perfil.get('Edad', 0)))
                genero = str(perfil.get('GENERO', perfil.get('Sexo', 'M')))
                
                ocupacion = parse_raw_val(perfil.get('ocupacion', perfil.get('OCUPACION', 1.375)))
                if ocupacion > 10: ocupacion /= 1000.0
                
                cadera = perfil.get('cadera_cm', 0.0)
                ritmo = perfil.get('ritmo_preferido', 'moderado')

                # Recalcular metabolismo e ideal
                tmb, get_val = calcular_tmb_y_get(peso, altura, int(edad), genero, ocupacion, cadera_cm=cadera)
                peso_ideal = calcular_peso_ideal(genero, altura, edad=int(edad))
                peso_etapa = calcular_peso_etapa(peso, peso_ideal, ritmo)

                msg_recalculo = traducciones.get(
                    "07_bot_metricas_recalculadas",
                    "{mensaje_exito}\n\n🔄 **Nuevas métricas calculadas:**\n• TMB (Metabolismo Basal): `{tmb:.0f} kcal/día`\n• GET (Gasto Energético): `{get_val:.0f} kcal/día`\n• Meta / Peso Etapa: `{peso_etapa:.1f} kg`"
                )
                txt_recalculo = msg_recalculo.format(mensaje_exito=mensaje_exito, tmb=tmb, get_val=get_val, peso_etapa=peso_etapa)

                await update.message.reply_text(txt_recalculo, parse_mode="Markdown")
            else:
                await update.message.reply_text(mensaje_exito, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error recalculando métricas en vivo para {user_id}: {e}")
            await update.message.reply_text(mensaje_exito, parse_mode="Markdown")
                                                    
@requiere_registro
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id, chat_id = update.effective_user.id, update.effective_chat.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    raw_text = update.message.text.strip() if update.message and update.message.text else ""
    if not raw_text: 
        return

    estados_perfil = [
        'awaiting_edit_perfil_peso', 'awaiting_edit_perfil_altura', 
        'awaiting_edit_perfil_cintura', 'awaiting_edit_perfil_cuello', 
        'awaiting_edit_perfil_cadera', 'awaiting_edit_perfil_nombre', 
        'awaiting_edit_perfil_prof'
    ]
    
    if any(context.user_data.get(st) for st in estados_perfil):
        await _sub_manejar_edicion_perfil_inputs(update, context, raw_text, chat_id)
        return
        
    if context.user_data.get('awaiting_presion_nota'):
        context.user_data.pop('awaiting_presion_nota', None)
        datos_presion = context.user_data.pop('pending_presion_foto', None)

        if raw_text.lower() == "cancelar":
            txt_canc_presion = traducciones.get("07_bot_presion_cancelada", "❌ Registro de presión cancelado.")
            await update.message.reply_text(txt_canc_presion)
            return

        if datos_presion:
            alta = datos_presion.get("alta")
            baja = datos_presion.get("baja")
            pulsaciones = datos_presion.get("pulsaciones")
            nota = raw_text

            await asyncio.to_thread(guardar_presion_db, user_id, alta, baja, pulsaciones, nota=nota)

            pul_txt = f" | Pulsaciones: `{pulsaciones:.0f} lpm`" if pulsaciones > 0 else ""
            msg_presion_ok = traducciones.get(
                "07_bot_presion_registrada_ok",
                "✅ *¡Presión arterial registrada con éxito!*\n\n• Presión Alta: `{alta:.0f} mmHg`\n• Presión Baja: `{baja:.0f} mmHg`{pul_txt}\n📝 Nota: `{nota}`"
            )
            await update.message.reply_text(
                msg_presion_ok.format(alta=alta, baja=baja, pul_txt=pul_txt, nota=nota),
                parse_mode="Markdown"
            )
        else:
            txt_exp_presion = traducciones.get("07_bot_presion_expirada", "⚠️ Los datos temporales de la presión expiraron.")
            await update.message.reply_text(txt_exp_presion)
        return

    if context.user_data.get('awaiting_custom_date'):
        await _sub_manejar_fecha_personalizada_ingesta(update, context, raw_text, chat_id)
        return
    if context.user_data.get('awaiting_activity_text'):
        await _sub_manejar_texto_actividad(update, context, raw_text, chat_id)
        return
    if context.user_data.get('awaiting_del_custom_date'):
        await _sub_manejar_fecha_eliminacion(update, context, raw_text, chat_id)
        return
    if context.user_data.get('awaiting_diario_custom_date'):
        await _sub_manejar_fecha_diario(update, context, raw_text, chat_id)
        return
    if context.user_data.get('awaiting_edit_item_val'):
        await _sub_manejar_edicion_item(update, context, raw_text, chat_id)
        return
    if raw_text.startswith('*'):
        await _sub_manejar_plantilla_comida(update, context, raw_text, user_id)
        return

    msg_analizando_ia = traducciones.get("07_bot_analizando_texto_ia", "🤖 Analizando texto con Inteligencia Artificial...")
    msg = await update.message.reply_text(msg_analizando_ia)
    try:
        data = await asyncio.to_thread(analizar_con_groq, raw_text, user_id)
        tipo = str(data.get("tipo", "")).strip().upper()

        if tipo == "INFORME_MENSUAL":
            await msg.delete()
            param = str(data.get("parametro", "")).strip().lower()
            ahora = obtener_ahora_arg()
            mes_target = ahora.strftime("%Y-%m")
            
            if "pasado" in param or "anterior" in param:
                mes_target = (ahora.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
            elif "enero" in param: mes_target = f"{ahora.year}-01"
            elif "febrero" in param: mes_target = f"{ahora.year}-02"
            elif "marzo" in param: mes_target = f"{ahora.year}-03"
            elif "abril" in param: mes_target = f"{ahora.year}-04"
            elif "mayo" in param: mes_target = f"{ahora.year}-05"
            elif "junio" in param: mes_target = f"{ahora.year}-06"
            elif "julio" in param: mes_target = f"{ahora.year}-07"
            elif "agosto" in param: mes_target = f"{ahora.year}-08"
            elif "septiembre" in param or "setiembre" in param: mes_target = f"{ahora.year}-09"
            elif "octubre" in param: mes_target = f"{ahora.year}-10"
            elif "noviembre" in param: mes_target = f"{ahora.year}-11"
            elif "diciembre" in param: mes_target = f"{ahora.year}-12"
            elif len(param) >= 7:
                mes_target = param

            context.args = [mes_target]
            await mostrar_resumen_mes(update, context)
            return

        elif tipo == "INFORME_SEMANAL":
            await msg.delete()
            await cmd_mensaje(update, context)
            return

        elif tipo == "INFORME_DIARIO":
            await msg.delete()
            param = str(data.get("parametro", "")).strip().lower()
            
            tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
            hoy_arg = datetime.now(tz_arg).date()
            
            if "ayer" in param:
                fecha_objetivo = (hoy_arg - timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                fecha_parseada = parsear_fecha_flexible(param)
                fecha_objetivo = fecha_parseada if fecha_parseada else hoy_arg.strftime("%Y-%m-%d")

            await mostrar_diario_fecha(update.message, user_id, fecha_objetivo)
            return

        elif tipo == "RECHAZO":
            await msg.delete()
            return

        await procesar_y_mostrar_confirmacion(data, msg, context)

    except Exception as e:
        msg_err_proc = traducciones.get("07_bot_error_procesar_texto", "❌ Error al procesar el texto: {e}")
        await msg.edit_text(msg_err_proc.format(e=e))
        
@requiere_registro
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
    txt_analizando_img = traducciones.get("07_bot_analizando_imagen", "📸 Analizando imagen...")
    msg = await update.message.reply_text(txt_analizando_img)
    
    max_intentos = 2
    exito = False
    
    for intento in range(1, max_intentos + 1):
        try:
            # 1. Descargamos la foto de Telegram
            photo_bytes = await (await update.message.photo[-1].get_file()).download_as_bytearray()
            user_caption = update.message.caption or ""
            
            # 2. COMPRESIÓN Y REDIMENSIONAMIENTO CON OPENCV
            np_arr = np.frombuffer(photo_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            
            if img is not None:
                # Limitamos el lado más largo a 1024 píxeles para aligerar el peso
                h, w = img.shape[:2]
                max_dim = 1024
                if max(h, w) > max_dim:
                    scale = max_dim / float(max(h, w))
                    new_w = int(w * scale)
                    new_h = int(h * scale)
                    img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                
                # Comprimimos a JPEG con calidad del 80% (reduce el peso a unos pocos KB)
                success, encoded_img = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if success:
                    photo_bytes = encoded_img.tobytes()
            
            # 3. Convertimos a base64 la imagen ya optimizada
            base64_image = base64.b64encode(photo_bytes).decode('utf-8')
            
            # 4. Verificamos si es la foto de un tensiómetro
            res_presion = analizar_foto_presion_con_groq(base64_image)
            if res_presion.get("es_presion") and float(res_presion.get("alta", 0)) > 0:
                exito = True
                return await _sub_manejar_foto_presion(update, context, res_presion, msg)

            # 5. Verificamos si tiene código de barras localmente
            tiene_codigo_local = False
            if img is not None:
                detector = cv2.barcode.BarcodeDetector()
                retval, points = detector.detect(img)
                if retval:
                    tiene_codigo_local = True

            if tiene_codigo_local:
                txt_barra_det = traducciones.get("07_bot_barra_detectada", "🔍 Código de barras detectado. Leyendo números del envase...")
                await msg.edit_text(txt_barra_det)
                codigo_leido = detectar_y_leer_codigo_barras_ia(base64_image)
                
                if codigo_leido and len(codigo_leido.strip()) >= 4:
                    await msg.delete()
                    exito = True
                    return await procesar_codigo_ingresado(update.message, context, codigo_leido.strip())

            # 6. Procesamiento normal del plato de comida con la IA multimodal
            exito = True
            return await _sub_manejar_foto_plato_ia(update, context, base64_image, user_caption, msg)

        except Exception as e:
            logger.warning(f"⚠ Intento {intento}/{max_intentos} fallido al procesar imagen para usuario {user_id}: {e}")
            if intento < max_intentos:
                txt_reintento_tpl = traducciones.get("07_bot_reintento_foto", "⏳ Demora en el servidor (Intento {intento}), reintentando automáticamente...")
                await msg.edit_text(txt_reintento_tpl.format(intento=intento))
                await asyncio.sleep(2)
            else:
                break

    if not exito:
        txt_error_timeout = traducciones.get(
            "07_bot_error_timeout_foto", 
            "⚠ **Error al procesar la imagen.**\n\n"
            "Por favor, ingresá los datos o la descripción escribiéndola por **texto** o enviando una nota de **voz**."
        )
        await msg.edit_text(txt_error_timeout, parse_mode="Markdown")
        
@requiere_registro
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    msg_procesando_audio = traducciones.get("07_bot_procesando_audio_ia", "🎙️ Procesando audio con IA...")
    msg = await update.message.reply_text(msg_procesando_audio)
    try:
        file = await context.bot.get_file(update.message.voice.file_id)
        audio_file = io.BytesIO(await file.download_as_bytearray())
        audio_file.name = "audio.ogg"
        
        transcription_res = client_ai.audio.transcriptions.create(
            file=(audio_file.name, audio_file.read()),
            model=GROQ_AUDIO,
            response_format="text"
        )
        
        transcription = str(transcription_res).strip() if transcription_res else ""
        
        if not transcription:
            msg_audio_no_entendido = traducciones.get("07_bot_audio_no_entendido", "⚠️ No se pudo entender el audio.")
            await msg.edit_text(msg_audio_no_entendido)
            return

        if context.user_data.get('awaiting_activity_voice'):
            return await _sub_manejar_voz_actividad(update, context, transcription, msg)

        data = analizar_con_groq(transcription)
        tipo = str(data.get("tipo", "")).strip().upper()

        if tipo == "INFORME_MENSUAL":
            await msg.delete()
            param = str(data.get("parametro", "")).strip().lower()
            ahora = obtener_ahora_arg()
            mes_target = ahora.strftime("%Y-%m")
            
            if "pasado" in param or "anterior" in param:
                mes_target = (ahora.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
            elif "enero" in param: mes_target = f"{ahora.year}-01"
            elif "febrero" in param: mes_target = f"{ahora.year}-02"
            elif "marzo" in param: mes_target = f"{ahora.year}-03"
            elif "abril" in param: mes_target = f"{ahora.year}-04"
            elif "mayo" in param: mes_target = f"{ahora.year}-05"
            elif "junio" in param: mes_target = f"{ahora.year}-06"
            elif "julio" in param: mes_target = f"{ahora.year}-07"
            elif "agosto" in param: mes_target = f"{ahora.year}-08"
            elif "septiembre" in param or "setiembre" in param: mes_target = f"{ahora.year}-09"
            elif "octubre" in param: mes_target = f"{ahora.year}-10"
            elif "noviembre" in param: mes_target = f"{ahora.year}-11"
            elif "diciembre" in param: mes_target = f"{ahora.year}-12"
            elif len(param) >= 7:
                mes_target = param

            context.args = [mes_target]
            await mostrar_resumen_mes(update, context)
            return

        elif tipo == "INFORME_SEMANAL":
            await msg.delete()
            await cmd_mensaje(update, context)
            return

        elif tipo == "INFORME_DIARIO":
            await msg.delete()
            param = str(data.get("parametro", "")).strip().lower()
            tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
            hoy_arg = datetime.now(tz_arg).date()
            
            if "ayer" in param:
                fecha_objetivo = (hoy_arg - timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                fecha_parseada = parsear_fecha_flexible(param)
                fecha_objetivo = fecha_parseada if fecha_parseada else hoy_arg.strftime("%Y-%m-%d")

            await mostrar_diario_fecha(update.message, user_id, fecha_objetivo)
            return

        elif tipo == "RECHAZO":
            await msg.delete()
            return

        await _sub_manejar_voz_ingesta(update, context, transcription, msg)

    except Exception as e:
        logger.error(f"Error al procesar audio: {e}")
        msg_err_audio = traducciones.get("07_bot_error_procesar_audio", "❌ Error al procesar audio: {e}")
        await msg.edit_text(msg_err_audio.format(e=e))
        
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
        lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
        traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

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
    No utiliza IA para abaratar costos y acelerar el proceso.
    """
    ahora = obtener_ahora_arg()
    hoy_str = ahora.strftime("%Y-%m-%d")
    dia_actual = ahora.day

    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        cur.execute('SELECT "User ID", "Estado", "dias_inactivo" FROM "Usuarios" WHERE "Estado" NOT IN (\'3\', \'inactivo\', \'baja\')')
        usuarios_activos = cur.fetchall()

        for usr in usuarios_activos:
            user_id = str(usr[0]).strip()
            estado_actual = str(usr[1])
            dias_inact = int(usr[2] if usr[2] is not None else 0)

            u_lang = obtener_idioma_usuario(int(user_id)) if 'obtener_idioma_usuario' in globals() else 'es'
            u_trad = obtener_traducciones_db(u_lang) if 'obtener_traducciones_db' in globals() else {}

            # 1. VERIFICACIÓN DE CARGAS (Sistema de Strikes)
            tabla_perfil = f"Perfil_{user_id}"
            cargo_hoy = False
            try:
                cur.execute(f'SELECT COUNT(*) FROM "{tabla_perfil}" WHERE "Fecha_Actualizacion" = %s', (hoy_str,))
                if cur.fetchone()[0] > 0:
                    cargo_hoy = True
            except Exception:
                pass 

            if cargo_hoy:
                cur.execute('UPDATE "Usuarios" SET "dias_inactivo" = 0 WHERE "User ID" = %s', (user_id,))
            else:
                dias_inact += 1
                cur.execute('UPDATE "Usuarios" SET "dias_inactivo" = %s WHERE "User ID" = %s', (dias_inact, user_id))
                
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
                    cur.execute('UPDATE "Usuarios" SET "Estado" = %s WHERE "User ID" = %s', ('3', user_id))
                    msg_s3 = u_trad.get("10_strike_3", "❌ **Cuenta suspendida** por falta de registro consecutivo.\n\nEscribí cualquier comando (ej: `/dia`) para ver las opciones de reactivación.")
                    await context.bot.send_message(chat_id=int(user_id), text=msg_s3, parse_mode="Markdown")

            # 2. RECORDATORIOS DE PESAJE (Regla de las 3 Ventanas)
            if dia_actual == 15 and estado_actual != '3':
                msg_peso_15 = u_trad.get("10_aviso_peso_15", "⚖️ **Control Quincenal Habilitado**\n\nYa podés ingresar tu control de peso de mitad de mes para calibrar tu metabolismo.\n👉 Escribí `/peso [tu_peso]` (ej: `/peso 85`).")
                await context.bot.send_message(chat_id=int(user_id), text=msg_peso_15, parse_mode="Markdown")
            
            elif dia_actual == 26 and estado_actual != '3':
                msg_peso_26 = u_trad.get("10_aviso_peso_26", "⚖️ **Cierre de Mes Habilitado**\n\nSe habilitó el ingreso de tu peso final para cerrar el balance mensual y preparar tu próxima rutina.\n👉 Escribí `/peso [tu_peso]`.")
                await context.bot.send_message(chat_id=int(user_id), text=msg_peso_26, parse_mode="Markdown")

        conn.commit()
        cur.close()
        conn.close()
        logger.info("Rutina nocturna finalizada con éxito.")
    except Exception as e:
        logger.error(f"Error en rutina nocturna: {e}")

# =========================================================================
# 1. COMANDO /pagar (Menú dinámico de planes desde Supabase)
# =========================================================================
async def cmd_pagar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra al usuario los planes de pago disponibles de forma dinámica."""
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

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


# =========================================================================
# 2. MANEJADOR DE BOTONES DE PLANES (Callback Query)
# =========================================================================
async def boton_elegir_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id).strip()
    lang = obtener_idioma_usuario(int(user_id)) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

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
        await query.edit_message_text(msg_enviado_tpl.format(descripcion=descripcion, estrellas=estrellas), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error procesando la selección de plan para el usuario {user_id}: {e}")
        msg_err_proc = traducciones.get("10_pagar_error_proc", "❌ Ocurrió un error al procesar tu selección.")
        await query.edit_message_text(msg_err_proc)

# =========================================================================
# 3. COMANDO ADMINISTRATIVO /cobrar (Cobro Manual por ID y Estrellas)
# =========================================================================
async def cmd_forzar_cobro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando administrativo para emitir un cobro manual por cantidad de estrellas.
    Uso: /cobrar <user_id> <estrellas>
    """
    user_actual = update.effective_user.id
    lang = obtener_idioma_usuario(user_actual) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

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

# =========================================================================
# 4. PRE-CHECKOUT Y SUCCESSFUL PAYMENT HANDLERS
# =========================================================================
async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    user_id = str(update.effective_user.id).strip()
    lang = obtener_idioma_usuario(int(user_id)) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

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
            ).format(nuevo_vencimiento=nuevo_vencimiento)
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
            await update.message.reply_text(msg_pago_exito_tpl.format(total_estrellas_pagadas=total_estrellas_pagadas), parse_mode="Markdown")
            return

        # Lógica de Planes regulares
        plan_id = payload.replace("pago_", "").rsplit("_", 1)[0]

        conn_p, cur_p = _asegurar_tabla_y_conectar("Planes", tipo_tabla="planes")
        cur_p.execute('SELECT "dias" FROM "Planes" WHERE "plan_id" = %s', (plan_id,))
        resultado_plan = cur_p.fetchone()
        cur_p.close()
        conn_p.close()

        dias_a_sumar = resultado_plan[0] if resultado_plan else 30
        hoy = datetime.now().date()
        nuevo_vencimiento = (hoy + timedelta(days=dias_a_sumar)).strftime("%Y-%m-%d")

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
        await update.message.reply_text(msg_renov_exito_tpl.format(nuevo_vencimiento=nuevo_vencimiento), parse_mode="Markdown")
        logger.info(f"✅ Suscripción actualizada para usuario {user_id} mediante plan {plan_id} hasta {nuevo_vencimiento}.")

    except Exception as e:
        logger.error(f"❌ Error al procesar pago exitoso para {user_id}: {e}")
        msg_err_pago = traducciones.get("10_pago_error_ficha", "⚠️ El pago se realizó pero hubo un error al actualizar tu ficha.")
        await update.message.reply_text(msg_err_pago)

# =========================================================================
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
            
            u_lang = obtener_idioma_usuario(int(str(user_id).split('.')[0].strip())) if 'obtener_idioma_usuario' in globals() else 'en'
            u_trad = obtener_traducciones_db(u_lang) if 'obtener_traducciones_db' in globals() else {}

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

import io
import re
import asyncio
import logging
from datetime import datetime, timedelta
import pandas as pd
import pytz
import calendar

# --- Telegram ---
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

# --- ReportLab (PDF) ---
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, HRFlowable, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- Configuración del Logger ---
logger = logging.getLogger(__name__)

# --- IMPORTACIONES DE MÓDULOS INTERNOS ---
from FuncionesAuxiliares import (
    obtener_ahora_arg,
    obtener_idioma_usuario,
    obtener_traducciones_db,
    requiere_registro,
    parse_raw_val,
    parsear_fecha_flexible,
    calcular_peso_ideal,
    calcular_peso_etapa,
    calcular_tmb_y_get
)
from SupabaseModule import (
    obtener_datos_usuario,
    obtener_perfil_usuario,
    obtener_datos_presion_db,
    _validar_peso_mes_actual,
    obtener_todos_usuarios,
    obtener_registros_usuario,
    actualizar_estado_usuario,
    _asegurar_tabla_y_conectar,
    obtener_valores_clinicos_profesional
)

# ======================================================================================================================================
#                   INICIO                                    COMANDOS INFORMES                                   INICIO  DB OK
# =====================================================================================================================================

#                   INICIO                                    COMANDO DIA                                    INICIO  DB OK
# =====================================================================================================================================

@requiere_registro
async def cmd_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Manejador del comando /diario.
    Permite argumento para ir a un día directo del mes actual (ej: /diario 5).
    Muestra el menú de selección de fecha con formato Día/Mes (DD/MM).
    """
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

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
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

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
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

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
    
#                 INICIO                            COMANDO SEMANA                             INICIO   DB OK
# ======================================================================================================================================

def _generar_texto_resumen_semanal(user_id, inicio_rango, fin_rango, etiqueta_periodo):
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    df_datos = obtener_datos_usuario(user_id) if 'obtener_datos_usuario' in globals() else pd.DataFrame()

    if df_datos.empty or 'Fecha' not in df_datos.columns:
        return None, None

    df_datos['Fecha_dt'] = pd.to_datetime(df_datos['Fecha'], errors='coerce').dt.date
    df_semana = df_datos[(df_datos['Fecha_dt'] >= inicio_rango) & (df_datos['Fecha_dt'] <= fin_rango)].copy()

    if df_semana.empty:
        return None, None

    mes_target = inicio_rango.strftime("%Y-%m")
    perfil = obtener_perfil_usuario(user_id, mes_target=mes_target) if 'obtener_perfil_usuario' in globals() else {}
    m = calcular_metricas_mensuales(df_semana, perfil) if 'calcular_metricas_mensuales' in globals() else {}

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
        df_presion = obtener_datos_presion_db(user_id) if 'obtener_datos_presion_db' in globals() else pd.DataFrame()
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
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
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
        df_datos = obtener_datos_usuario(user_id) if 'obtener_datos_usuario' in globals() else pd.DataFrame()
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
        
        await msg_espera.edit_text(txt_informe, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en resumen semanal para {user_id}: {e}")
        msg_err_proc = traducciones.get("08_inf_semana_err_proc", "❌ Error al procesar tu resumen semanal.")
        await msg_espera.edit_text(msg_err_proc)
                             
#               INICIO                                COMANDO RESUMEN COMANDO MES                       INICIO DB OK
# ==========================================================================================================================================

def obtener_mensaje_variacion_peso(cambio_kg: float) -> str:
    """Devuelve un mensaje cualitativo según la variación de peso mensual estimada."""
    if abs(cambio_kg) <= 0.8:
        return "Prácticamente estable"
    elif 0.8 < cambio_kg <= 1.8:
        return "Pequeña variación hacia arriba"
    elif 1.8 < cambio_kg <= 3.0:
        return "Variación moderada hacia arriba"
    elif cambio_kg > 3.0:
        return "Variación importante hacia arriba"
    elif -1.8 <= cambio_kg < -0.8:
        return "Pequeña variación hacia abajo"
    elif -3.0 <= cambio_kg < -1.8:
        return "Variación moderada hacia abajo"
    else:
        return "Variación importante hacia abajo"

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

    edad = int(get_perfil_num(['Edad', 'edad'], 64))
    altura = get_perfil_num(['Altura', 'altura', 'ALTURA'], 167.5)
    peso_actual = get_perfil_num(['PESO', 'Peso', 'peso', 'peso_actual'], 104.6)
    
    ocupacion = str(perfil_dict.get('Ocupacion') or perfil_dict.get('ocupacion') or perfil_dict.get('actividad', 'ligero')).strip()
    genero = str(perfil_dict.get('GENERO') or perfil_dict.get('Genero') or perfil_dict.get('genero', 'masculino')).strip()
    gen_clean = genero.lower()
    is_femenino = gen_clean in ["femenino", "f", "mujer", "female"]
    ritmo_usuario = str(perfil_dict.get('Ritmo') or perfil_dict.get('ritmo_preferido', 'moderado')).strip()

    peso_ideal_secreto = calcular_peso_ideal(genero, altura)
    peso_etapa_calculado = calcular_peso_etapa(peso_actual, peso_ideal_secreto, ritmo_usuario)
    
    peso_referencia = round(peso_etapa_calculado, 1)
    peso_ideal_dinamico = peso_referencia  
    
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

    val_get_real = int(round(get_real))
    val_get_meta = int(round(get_meta))
    cal_min = min(val_get_real, val_get_meta)
    cal_max = max(val_get_real, val_get_meta)

    peso_min = min(float(peso_actual), float(peso_referencia))
    peso_max = max(float(peso_actual), float(peso_referencia))

    prot_min = int(round(peso_min * factor_proteina_min))
    prot_max = int(round(peso_max * factor_proteina_max))

    gras_min = int(round((cal_min * 0.20) / 9.0))
    gras_max = int(round((cal_max * 0.30) / 9.0))

    carb_min = int(round((cal_min * 0.40) / 4.0))
    carb_max = int(round((cal_max * 0.55) / 4.0))

    # --- SUPREMACÍA CLÍNICA: VERIFICAR SI TIENE VALORES DEL PROFESIONAL ---
    if user_id and mes_str:
        valores_prof = obtener_valores_clinicos_profesional(user_id, mes_str)
        if valores_prof:
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
        "cambio_peso_kg": cambio_peso_kg
    }
        
async def procesar_y_enviar_informe_mensual(context, user_id: int, chat_destino: int, mes_target: str, es_automatico_15: bool = False, forzar_envio: bool = False):
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    try:
        peso_ok = await _validar_peso_mes_actual(context=context, user_id=user_id)
        if not peso_ok and not forzar_envio:
            return False

        df_datos = obtener_datos_usuario(user_id) if 'obtener_datos_usuario' in globals() else pd.DataFrame()
        if df_datos.empty or 'Fecha' not in df_datos.columns:
            msg_nodata = traducciones.get("08_sup_inf_no_registros", "⚠️ Not enough records to generate the report.")
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
            etiqueta_periodo = f"Bi-weekly ({mes_target}: 1 to 14)" if lang == 'en' else f"Quincenal ({mes_target}: 1 al 14)"
        else:
            inicio_periodo = pd.Timestamp(f"{mes_target}-01").normalize()
            if mes_target == mes_actual_str:
                fin_periodo = ayer_ts
                etiqueta_periodo = f"Current month ongoing ({mes_target}: from 01 to {ayer_ts.strftime('%d/%m')})" if lang == 'en' else f"Mes Actual en curso ({mes_target}: del 01 al {ayer_ts.strftime('%d/%m')})"
            else:
                fin_periodo = (inicio_periodo + pd.offsets.MonthEnd(0)).normalize()
                etiqueta_periodo = f"Full Month ({mes_target})" if lang == 'en' else f"Mes Completo ({mes_target})"

        df_filtrado = df_datos[(df_datos['Fecha_dt'] >= inicio_periodo) & (df_datos['Fecha_dt'] <= fin_periodo)].copy()

        if df_filtrado.empty:
            msg_template = traducciones.get("08_sup_inf_sin_registros_periodo", "⚠️ No closed records found for the period {etiqueta_periodo}.")
            msg_closed = msg_template.format(etiqueta_periodo=etiqueta_periodo)
            await context.bot.send_message(chat_id=user_id, text=msg_closed)
            return False

        perfil = obtener_perfil_usuario(user_id, mes_target=mes_target) if 'obtener_perfil_usuario' in globals() else {}
        m = calcular_metricas_mensuales(df_filtrado, perfil, user_id=user_id, mes_str=mes_target) if 'calcular_metricas_mensuales' in globals() else {}

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
        await context.bot.send_document(
            chat_id=chat_destino,
            document=pdf_buffer,
            filename=f"Informe_Mensual_{mes_target}.pdf",
            caption=f"📊 **Reporte Mensual correspondiente a {mes_target}**",
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
                    motivo_desvio = f"Balance neto inferior al mínimo establecido ({bal_neto} kcal vs mín {c_min} kcal)"
                elif bal_neto > c_max:
                    desvio = True
                    motivo_desvio = f"Balance neto superior al máximo establecido ({bal_neto} kcal vs máx {c_max} kcal)"

                if desvio:
                    alerta_medico = (
                        f"⚠️ **ALERTA CLÍNICA DE DESVÍO**\n\n"
                        f"El paciente **{perfil.get('Nombre', user_id)}** (ID: `{user_id}`) ha presentado un desvío en su reporte mensual de `{mes_target}`:\n"
                        f"• *Motivo:* {motivo_desvio}\n\n"
                        f"Se adjunta copia del informe para su revisión."
                    )
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
                        
@requiere_registro
async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Manejador del comando /resumen.
    Permite argumento para ir directo a un mes del año actual (ej: /resumen 08).
    """
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

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
        lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
        traducciones = obtener_traducciones_db(lang) if 'obtener_idioma_usuario' in globals() else {}

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
                for i in range(1, 7):
                    mes_iter = (primer_dia_mes_actual - pd.DateOffset(months=i)).strftime("%Y-%m")
                    botones_meses.append([InlineKeyboardButton(f"🗓️ Período {mes_iter}", callback_data=f"resumen_mes_{mes_iter}")])
                
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

        df_datos = obtener_datos_usuario(user_id) if 'obtener_datos_usuario' in globals() else pd.DataFrame()
        
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

        perfil = obtener_perfil_usuario(user_id, mes_target=mes_str) if 'obtener_perfil_usuario' in globals() else {}
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
        texto_variacion_peso = f"`{obtener_mensaje_variacion_peso(cambio_peso_val)}`"

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
            "_(Nota: Reporte generado mediante métricas analíticas directas)._"
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
            act_min=act_min_val, act_max=act_max_val
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
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

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
    mensaje_variacion = obtener_mensaje_variacion_peso(cambio_val)
    story.append(Paragraph(p_cambio_tmpl.format(cambio_txt=mensaje_variacion), body_style))
    
    story.append(Paragraph(p_act_tmpl.format(act_minutos=m.get('prom_minutos_act', 0), act_min=m.get('act_min', 30), act_max=m.get('act_max', 60)), body_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph(p_nota_act, body_style))

    story.append(Spacer(1, 6))
    disclaimer_texto = traducciones.get(
        "08_PDF_resumen_disclaimer", 
        "<i>* Aclaración: La tendencia de peso indicada es una proyección matemática aproximada, calculada exclusivamente en base a los registros ingresados por el usuario en la plataforma. No posee exactitud ni validez clínica, ya que el resultado real depende de la precisión de dichas cargas y del metabolismo individual de cada paciente.</i>"
    )
    story.append(Paragraph(disclaimer_texto, body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer
        
async def generar_y_enviar_pdf_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
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

        df_datos = obtener_datos_usuario(user_id) if 'obtener_datos_usuario' in globals() else pd.DataFrame()
        
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

        perfil = obtener_perfil_usuario(user_id, mes_target=mes_str) if 'obtener_perfil_usuario' in globals() else {}
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
        comidas_del_dia = [
            str(r.get("Momento/Actividad") or r.get("Momento", "")).capitalize() 
            for r in registros 
            if str(r.get("Fecha", "")).strip() == str_d 
            and str(r.get("Momento/Actividad") or r.get("Momento", "")).capitalize() in todas_comidas
        ]
        if len(comidas_del_dia) >= 2 and any(c in comidas_principales for c in comidas_del_dia):
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

            lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
            traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

            df_presion = obtener_datos_presion_db(user_id) if 'obtener_datos_presion_db' in globals() else pd.DataFrame()
            
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
                )
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
                    u_lang = obtener_idioma_usuario(int(u_id_str)) if 'obtener_idioma_usuario' in globals() else 'es'
                    u_trad = obtener_traducciones_db(u_lang) if 'obtener_traducciones_db' in globals() else {}

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

            lang_u = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
            traducciones = obtener_traducciones_db(lang_u) if 'obtener_traducciones_db' in globals() else {}

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
                
                if dias_validos < 20:
                    actualizar_estado_usuario(str(user_id), "3")
                    
                    _, dias_en_mes = calendar.monthrange(hoy.year, hoy.month)
                    dias_restantes = dias_en_mes - hoy.day 
                    precio_base_estrellas = obtener_precio_plan_mensual() if 'obtener_precio_plan_mensual' in globals() else 100
                    estrellas_prorrateadas = int(round((precio_base_estrellas / dias_en_mes) * dias_restantes))
                    costo_usd_prorrateado = estrellas_prorrateadas * 0.02
                    
                    if 'facturar_saldo_del_mes' in globals():
                        await facturar_saldo_del_mes(context, user_id, dias_restantes, estrellas_prorrateadas)
                        
                    msg_fin = traducciones.get(
                        "08_notif_freemium_fin20",
                        "❌ **Período de prueba finalizado.**\nNo alcanzaste el objetivo mínimo de constancia (20 días) para mantener la cuenta gratuita y el seguimiento fue pausado.\n\nPara reactivarlo y usar el bot sin interrupciones hasta fin de mes, hemos emitido una factura proporcional por los días restantes (aprox. {costo_usd} USD / {estrellas} ⭐️).\n\nA fin de mes podrás elegir tu plan definitivo."
                    ).format(
                        costo_usd=f"{costo_usd_prorrateado:.2f}", 
                        estrellas=estrellas_prorrateadas
                    )
                    
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
            if momento == 'manana':
                for c in todas_comidas:
                    if c not in comidas_anteayer:
                        faltantes.append(f"{c} de anteayer ({str_anteayer})")
                for c in todas_comidas:
                    if c not in comidas_ayer:
                        faltantes.append(f"{c} de ayer ({str_ayer})")

            elif momento == 'tarde':
                for c in todas_comidas:
                    if c not in comidas_ayer:
                        faltantes.append(f"{c} de ayer ({str_ayer})")
                if "Desayuno" not in comidas_hoy:
                    faltantes.append("Desayuno de hoy")
                if "Almuerzo" not in comidas_hoy:
                    faltantes.append("Almuerzo de hoy")

            if faltantes:
                lista_formateada = "\n• " + "\n• ".join(faltantes)
                msg_recordatorio_comidas = traducciones.get(
                    "08_notif_recordatorio_comidas",
                    "📌 **Recordatorio de comidas pendientes:**\n{lista_formateada}\n\nSi ya las consumiste, podés registrarlas en cualquier momento."
                )
                await context.bot.send_message(
                    chat_id=int(user_id), 
                    text=msg_recordatorio_comidas.format(lista_formateada=lista_formateada), 
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

#                       INICIO                         COMANDO START                          INICIO  
# =========================================================================================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    msg = traducciones.get('09_start_mensaje_bienvenida', 
        "👋 *¡Bienvenido a tu Bot Nutricional Personalizado!*\n\n"
        "Guía rápida de comandos e ingresos disponibles:\n\n"
        "📌 *Comandos Principales:*\n"
        "• `/alta`: Apertura de cuenta ingresando los datos.\n"
        "• `/barra`: Ingresa por código de barras un comestible.\n"
        "• `/borracomida`: Borra una comida de la Planilla.\n"
        "• `/comidas`: Planilla de comidas precargadas y PDF.\n"
        "• `/diario`: Ingestas de un día específico (ej: `/diario 5`) y PDF.\n"
        "• `/eliminar`: Borra ingestas y actividades.\n"
        "• `/GET` o `/factor`: Actualiza GET por reloj inteligente (Disponible desde el día 15).\n"
        "• `/inicio`: Resumen de comandos y manual en PDF.\n"
        "• `/pago`: Elegir el plan o promoción de pago vigente.\n"
        "• `/perfil`: Actualización de datos biométricos.\n"
        "• `/peso`: Registro o control de peso mensual (ej: `/peso 82.5`).\n"
        "• `/presi`: Registro y consulta de presión arterial.\n"
        "• `/receta`: Calculadora Web para registrar comidas.\n"
        "• `/resumen`: Reporte mensual de calorías y PDF (ej: `/resumen 08`).\n"
        "• `/semana`: Estadística semanal (calorías, fibras, etc.).\n\n"
        "📌 *Métodos de Registro:*\n"
        "• *Ingestas con IA:* 📝 Texto, 🎤 Notas de voz, 📸 Fotos.\n"
        "• *Modificación parcial:* por item (`DESCRIPCION`, `DESCRIPCION,PESO`, `,PESO`).\n"
        "• *Ingestas sin IA:* 📝 Planilla (`*DESAYUNO,1`, `*PIZZA,4`).\n"
        "• *Presión arterial:* 📸 Fotos o comando manual (`/presi 120,80,70`).\n"
        "• *Actividad física:* 📝 Texto o 🎤 Notas de voz."
    )
    
    texto_final = msg.replace('<br>', '\n').replace('\\n', '\n')
    texto_final = re.sub(r'\n{2,}', '\n\n', texto_final)
    
    pdf_filename = f"{lang.upper()}.pdf"
    btn_manual_txt = traducciones.get('09_btn_descargar_manual', "📄 Descargar Manual Completo en PDF")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_manual_txt, callback_data=f"descargar_manual_{lang}")]
    ])
    
    try:
        await update.message.reply_text(texto_final, reply_markup=keyboard, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error de formato Markdown en /start: {e}")
        await update.message.reply_text(texto_final, reply_markup=keyboard)


#                       COMANDO ALTA Y FLUJO DE USUARIO CON INFORME IA
# =========================================================================================================================================

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

    idiomas_disp = await obtener_idiomas_disponibles_db()
    b_list = [[InlineKeyboardButton(f"{item['bandera']} {item['nombre']}", callback_data=f"set_lang_{item['codigo']}")] for item in idiomas_disp]
    
    await query.edit_message_text("🌐 Seleccioná tu **idioma preferido**:", reply_markup=InlineKeyboardMarkup(b_list), parse_mode="Markdown")
    return ING_IDIOMA

async def ing_recibir_cadera(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().replace(',', '.')
    try:
        cadera = float(txt)
        if not (60 <= cadera <= 200): raise ValueError()
    except ValueError:
        await update.message.reply_text("⚠️ Ingresá un perímetro de cadera válido en cm (ejemplo: `100`).", parse_mode="Markdown")
        return ING_CADERA

    context.user_data['ing_cadera'] = cadera

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Tranquilo / Lento", callback_data="ritmo_tranquilo")],
        [InlineKeyboardButton("🟡 Moderado", callback_data="ritmo_moderado")],
        [InlineKeyboardButton("🔴 Intenso / Rápido", callback_data="ritmo_intenso")]
    ])
    await update.message.reply_text(
        "Seleccioná el **ritmo para tu plan**. Esto define el déficit/superávit de tus calorías:\n"
        "• *🟢 Tranquilo (Cambios muy graduales, súper fácil de sostener).*\n"
        "• *🟡 Moderado (Equilibrio ideal entre resultados y adherencia).*\n"
        "• *🔴 Intenso (Exigente, para resultados más rápidos).*\n\n"
        "🎯 Seleccioná tu ritmo deseado:", 
        reply_markup=keyboard, parse_mode="Markdown"
    )
    return ING_RITMO

async def ing_recibir_idioma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['ing_idioma'] = query.data.replace("set_lang_", "")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🪑 Nivel 1 (Ligero)", callback_data="ocup_1.375")],
        [InlineKeyboardButton("🚶 Nivel 2 (Moderado)", callback_data="ocup_1.550")],
        [InlineKeyboardButton("🏃 Nivel 3 (Intenso)", callback_data="ocup_1.725")]
    ])
    
    texto_ocupacion = (
        "Seleccioná tu **nivel de movimiento diario** (el ejercicio deportivo se registra aparte):\n"
        "• *🪑 Ligero (Trabajo de oficina / Mayormente sentado).*\n"
        "• *🚶 Moderado (De pie muchas horas, ej: docentes, vendedores).*\n"
        "• *🏃 Intenso (Trabajo físico pesado, ej: albañilería, carga).*"
    )
    
    await query.edit_message_text(texto_ocupacion, reply_markup=keyboard, parse_mode="Markdown")
    return ING_OCUPACION

async def ing_recibir_ocupacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try: 
        context.user_data['ing_ocupacion'] = float(query.data.replace("ocup_", ""))
    except ValueError: 
        context.user_data['ing_ocupacion'] = 1.375
        
    await query.edit_message_text("Ingresá tu **peso actual en kg** (ejemplo: `82.5`):", parse_mode="Markdown")
    return ING_PESO

async def cmd_ingreso_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    idioma_detectado = 'es'
    context.user_data['ing_idioma'] = idioma_detectado
    traducciones = obtener_traducciones_db(idioma_detectado) if 'obtener_traducciones_db' in globals() else {}

    estado_usr = _verificar_estado_usuario_en_hoja(user_id)
    
    if estado_usr is not None:
        estado_lower = estado_usr.lower()
        
        if estado_lower == '3':
            mensaje_bloqueo = (
                "⚠️ **Tu período de prueba gratuito ha finalizado.**\n\n"
                "Para seguir usando todas las funciones del asistente, podés activar tu cuenta abonando los días que restan hasta fin de mes.\n\n"
                "Una vez abonado, volverás a tener acceso total y tu ciclo de facturación se alineará al día 1 del mes próximo."
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⭐ Activar mes en curso", callback_data="rescate_mensual")]
            ])
            await update.message.reply_text(mensaje_bloqueo, reply_markup=keyboard, parse_mode="Markdown")
            return ConversationHandler.END
            
        elif estado_lower in ['inactivo', 'bloqueado', 'no', 'false']:
            txt_bloq = traducciones.get('09_ing_error_usuario_deshabilitado', "❌ **Su usuario ha sido deshabilitado, contáctese con el administrador del bot.**")
            await update.message.reply_text(txt_bloq.replace('\\n', '\n'), parse_mode="Markdown")
            return ConversationHandler.END
        else:
            perfil_existente = obtener_perfil_usuario(user_id) if 'obtener_perfil_usuario' in globals() else {}
            nombre_usr = perfil_existente.get('nombre', 'Usuario') if perfil_existente else 'Usuario'
            txt_activo = traducciones.get('09_ing_cuenta_activa_aviso', 
                "ℹ **¡Ya tenés una cuenta activa, {nombre_usr}!**\n\n"
                "Tu ficha ya está registrada en el sistema con el ID `{user_id}`.\n"
                "Podés consultar o actualizar tu información en cualquier momento con el comando `/perfil`."
            ).format(nombre_usr=nombre_usr, user_id=user_id)
            await update.message.reply_text(txt_activo.replace('\\n', '\n'), parse_mode="Markdown")
            return ConversationHandler.END

    texto_advertencia = traducciones.get('09_ing_advertencia_legal', 
        "⚖️ **ADVERTENCIA LEGAL Y CONDICIONES DE USO**\n\n"
        "Este asistente es una herramienta de cálculo automatizado orientada a sumar y restar calorías, "
        "registrar ingestas y macronutrientes de forma práctica. **No posee un valor médico ni científico:** "
        "las recomendaciones emitidas son generadas de forma generalizada.\n\n"
        "👉 *Para continuar con la apertura de tu cuenta y aceptar los términos, por favor presioná el botón de abajo:*"
    )

    btn_terminos_text = traducciones.get('09_btn_aceptar_terminos', "✅ He leído y acepto los términos")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_terminos_text, callback_data="aceptar_terminos_ok")]
    ])

    await update.message.reply_text(texto_advertencia.replace('\\n', '\n'), reply_markup=keyboard, parse_mode="Markdown")
    return ING_TERMINOS

async def ing_aceptar_terminos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "aceptar_terminos_ok":
        txt_terminos_ok = (
            "✅ **Términos aceptados correctamente.**\n\n"
            "🔑 **Apertura de Ficha - Validación de Profesional**\n\n"
            "Para comenzar el registro, por favor ingresá el **ID de Telegram del profesional**.\n"
            "*(Si no tenés un profesional asignado y querés usar el asistente de forma independiente, ingresá 123456789)*:"
        )
        await query.edit_message_text(txt_terminos_ok, parse_mode="Markdown")
        return ING_PROFESIONAL
    return ING_TERMINOS

async def ing_recibir_profesional(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prof_id = update.message.text.strip()
    
    es_valido = False
    if prof_id == "123456789":
        es_valido = True
    else:
        loop = asyncio.get_running_loop()
        es_valido = await loop.run_in_executor(None, _verificar_profesional_valido, prof_id)
    
    if not es_valido:
        txt_err_prof = (
            "⚠️ **ID de profesional no válido**\n\n"
            "El número ingresado no figura en la lista de profesionales autorizados. "
            "Por favor, verificá el ID con tu profesional e intentalo nuevamente o escribí `/cancelar`."
        )
        await update.message.reply_text(txt_err_prof, parse_mode="Markdown")
        return ING_PROFESIONAL

    context.user_data['ing_profesional'] = prof_id
    txt_solic_nombre = (
        "✅ **Profesional verificado correctamente.**\n\n"
        "📝 **Apertura de Ficha Nutricional**\n"
        "Por favor, indicá tu **Nombre y Apellido / Apodo**:"
    )
    await update.message.reply_text(txt_solic_nombre, parse_mode="Markdown")
    return ING_NOMBRE

async def ing_recibir_cumple(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cumple_str = update.message.text.strip()
    try:
        datetime.strptime(cumple_str, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("⚠️ Formato de fecha inválido. Usá el formato `AAAA-MM-DD` (ejemplo: `1990-08-25`).", parse_mode="Markdown")
        return ING_CUMPLE

    context.user_data['ing_cumple'] = cumple_str
    edad_calculada = calcular_edad_desde_cumple(cumple_str) if 'calcular_edad_desde_cumple' in globals() else 30

    if edad_calculada < 18:
        context.user_data['ing_cintura'] = 0.0
        context.user_data['ing_cuello'] = 0.0
        context.user_data['ing_cadera'] = 0.0

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🟢 Tranquilo / Lento", callback_data="ritmo_tranquilo")],
            [InlineKeyboardButton("🟡 Moderado", callback_data="ritmo_moderado")],
            [InlineKeyboardButton("🔴 Intenso / Rápido", callback_data="ritmo_intenso")]
        ])
        await update.message.reply_text(
            f"👶 **Perfil pediátrico/juvenil detectado ({edad_calculada} años).**\n"
            "Se adaptarán los cálculos a los estándares pediátricos de la OMS sin requerir medidas corporales.\n\n"
            "Seleccioná el **ritmo para tu plan**. Esto define el déficit/superávit de tus calorías:\n"
            "• *🟢 Tranquilo (Cambios muy graduales, súper fácil de sostener).*\n"
            "• *🟡 Moderado (Equilibrio ideal entre resultados y adherencia).*\n"
            "• *🔴 Intenso (Exigente, para resultados más rápidos).*\n\n"
            "🎯 Seleccioná tu ritmo deseado:", 
            reply_markup=keyboard, 
            parse_mode="Markdown"
        )
        return ING_RITMO

    es_mujer = context.user_data.get('ing_sexo', 'M') == 'F'
    tip_cintura = (
        "📏 *Tip de medición: Medí en la parte más estrecha de tu torso, generalmente a medio camino entre las costillas inferiores y el ombligo.*"
        if es_mujer else
        "📏 *Tip de medición: Pasá la cinta métrica exactamente a la altura del ombligo, asegurándote de que esté horizontal y sin hundir el estómago.*"
    )
    
    await update.message.reply_text(f"Ingresá el **perímetro de tu cintura en cm** (ejemplo: `85`):\n\n{tip_cintura}", parse_mode="Markdown")
    return ING_MUNECA

async def ing_recibir_muneca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().replace(',', '.')
    try:
        cintura = float(txt)
        if not (50 <= cintura <= 200): raise ValueError()
    except ValueError:
        await update.message.reply_text("⚠️ Ingresá un perímetro de cintura válido en cm (ejemplo: `85`).", parse_mode="Markdown")
        return ING_MUNECA

    context.user_data['ing_cintura'] = cintura
    
    tip_cuello = "📐 *Tip de medición: Mirá al frente con los hombros relajados (no levantes ni bajes la cabeza). Colocá la cinta justo debajo de la nuez de Adán, lo más horizontal posible.*"
    await update.message.reply_text(f"Ingresá el **perímetro de tu cuello en cm** (ejemplo: `38`):\n\n{tip_cuello}", parse_mode="Markdown")
    return ING_CUELLO

async def ing_recibir_cuello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().replace(',', '.')
    try:
        cuello = float(txt)
        if not (20 <= cuello <= 60): raise ValueError()
    except ValueError:
        await update.message.reply_text("⚠️ Ingresá un perímetro de cuello válido en cm (ejemplo: `38`).", parse_mode="Markdown")
        return ING_CUELLO

    context.user_data['ing_cuello'] = cuello

    if context.user_data.get('ing_sexo', 'M') == 'F':
        tip_cadera = "📏 *Tip de medición: Juntá los pies y pasá la cinta por la parte más ancha de los glúteos y caderas, manteniéndola paralela al piso.*"
        await update.message.reply_text(f"Ingresá el **perímetro de tu cadera en cm** (ejemplo: `100`):\n\n{tip_cadera}", parse_mode="Markdown")
        return ING_CADERA

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Tranquilo / Lento", callback_data="ritmo_tranquilo")],
        [InlineKeyboardButton("🟡 Moderado", callback_data="ritmo_moderado")],
        [InlineKeyboardButton("🔴 Intenso / Rápido", callback_data="ritmo_intenso")]
    ])
    await update.message.reply_text(
        "Seleccioná el **ritmo para tu plan**. Esto define el déficit/superávit de tus calorías:\n"
        "• *🟢 Tranquilo (Cambios muy graduales, súper fácil de sostener).*\n"
        "• *🟡 Moderado (Equilibrio ideal entre resultados y adherencia).*\n"
        "• *🔴 Intenso (Exigente, para resultados más rápidos).*\n\n"
        "🎯 Seleccioná tu ritmo deseado:", 
        reply_markup=keyboard, parse_mode="Markdown"
    )
    return ING_RITMO

async def ing_recibir_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.text.strip()
    if len(nombre) < 2:
        await update.message.reply_text("⚠️ Por favor, ingresá un nombre válido.")
        return ING_NOMBRE
    
    context.user_data['ing_nombre'] = nombre
    
    btn_masc = "Masculino 👨"
    btn_fem = "Femenino 👩"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_masc, callback_data="sexo_M"),
         InlineKeyboardButton(btn_fem, callback_data="sexo_F")]
    ])
    await update.message.reply_text("Seleccioná tu **sexo biológico**:", reply_markup=keyboard, parse_mode="Markdown")
    return ING_SEXO

async def ing_recibir_sexo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sexo = "M" if query.data == "sexo_M" else "F"
    context.user_data['ing_sexo'] = sexo
    
    await query.edit_message_text("Ahora ingresá tu **fecha de nacimiento** en formato `AAAA-MM-DD` (ejemplo: `1985-04-12`):", parse_mode="Markdown")
    return ING_CUMPLE
    
async def ing_recibir_peso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().replace(',', '.')
    try:
        peso = float(txt)
        if not (30 <= peso <= 300): raise ValueError()
    except ValueError:
        await update.message.reply_text("⚠️ Ingresá un peso válido en kg (ejemplo: `75.4`).", parse_mode="Markdown")
        return ING_PESO

    context.user_data['ing_peso'] = peso
    await update.message.reply_text("Ingresá tu **altura en centímetros** (ejemplo: `175` para 1,75 m):", parse_mode="Markdown")
    return ING_ALTURA

async def ing_recibir_altura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().replace(',', '.')
    lang = context.user_data.get('ing_idioma', 'es')
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    try:
        alt = float(txt)
        if not (100 <= alt <= 230): raise ValueError()
    except ValueError:
        txt_err_alt = traducciones.get('09_ing_error_altura_valida', "⚠️ Ingresá una altura válida en centímetros (ejemplo: `170`).")
        await update.message.reply_text(txt_err_alt, parse_mode="Markdown")
        return ING_ALTURA

    context.user_data['ing_altura'] = alt
    user_id = update.effective_user.id

    datos_usuario = {
        "user_id": user_id,
        "nombre": context.user_data.get('ing_nombre'),
        "sexo": context.user_data.get('ing_sexo'),
        "cumple": context.user_data.get('ing_cumple'),
        "profesional": context.user_data.get('ing_profesional'),
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
        "✅ Datos completados.\n\n"
        "⏳ *Creando planillas y redactando tu informe inicial personalizado con IA...*"
    )
    msg_espera = await update.message.reply_text(txt_procesando, parse_mode="Markdown")

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, cmd_nuevo_usuario, datos_usuario)
        
        _, pdf_buf = await procesar_informe_inicial_ia(datos_usuario) if 'procesar_informe_inicial_ia' in globals() else (None, None)
        
        await msg_espera.delete()
        
        # Aclaración adicional si tiene médico asignado
        aviso_medico_alta = ""
        prof_ingresado = datos_usuario.get("profesional", "")
        if prof_ingresado and prof_ingresado != "123456789":
            aviso_medico_alta = "\n\n🩺 *Nota:* Estos valores iniciales fueron calculados automáticamente, pero tu médico tratante se contactará o ajustará tus metas si considera que es necesario."

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
        ) + aviso_medico_alta
        
        await update.message.reply_text(resumen_plantilla, parse_mode="Markdown")

        if pdf_buf:
            filename_pdf = f"Informe_Inicial_{datos_usuario['nombre'].replace(' ', '_')}.pdf"
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=pdf_buf,
                filename=filename_pdf
            )

        if prof_ingresado and prof_ingresado != "123456789":
            try:
                msg_prof = f"🩺 **Nuevo paciente registrado:** Se ha asociado a su seguimiento el usuario *{datos_usuario['nombre']}* (ID: `{user_id}`)."
                await context.bot.send_message(chat_id=int(prof_ingresado), text=msg_prof, parse_mode="Markdown")
            except Exception as e_prof:
                logger.error(f"No se pudo notificar al profesional {prof_ingresado}: {e_prof}")

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
    profesional = datos_usuario.get("profesional", "")
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
        cur_u.execute('SELECT COUNT(*) FROM "Usuarios" WHERE "User ID" = %s', (str(user_id),))
        existe = cur_u.fetchone()[0] > 0

        if existe:
            query_usr = """
                UPDATE "Usuarios" SET
                    "Nombre" = %s, "Estado" = %s, "Ultimo Mes Peso" = %s, "Notificaciones" = %s,
                    "Fecha Alta" = %s, "Sexo" = %s, "cumple" = %s, "profesional" = %s,
                    "cintura_cm" = %s, "cuello_cm" = %s, "cadera_cm" = %s, "ritmo_preferido" = %s, "Idioma" = %s
                WHERE "User ID" = %s
            """
            valores_usr = (nombre, 0, mes_actual, "Si", fecha_alta, sexo, cumple, profesional, cintura, cuello, cadera, ritmo, idioma, str(user_id))
        else:
            query_usr = """
                INSERT INTO "Usuarios" ("User ID", "Nombre", "Estado", "Ultimo Mes Peso", "Notificaciones", "Fecha Alta", "Sexo", "cumple", "profesional", "cintura_cm", "cuello_cm", "cadera_cm", "ritmo_preferido", "Idioma")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            valores_usr = (str(user_id), nombre, 0, mes_actual, "Si", fecha_alta, sexo, cumple, profesional, cintura, cuello, cadera, ritmo, idioma)

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
        
@requiere_registro
async def cmd_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
    ahora = obtener_ahora_arg()
    mes_actual = ahora.strftime("%Y-%m")

    if '_garantizar_fila_mes_actual' in globals():
        _garantizar_fila_mes_actual(user_id, ahora)

    try:
        perfil_completo = obtener_datos_completos_usuario(user_id, mes_target=mes_actual) if 'obtener_datos_completos_usuario' in globals() else obtener_perfil_usuario(user_id, mes_target=mes_actual)

        if perfil_completo:
            peso = parse_raw_val(perfil_completo.get('PESO', perfil_completo.get('Peso', 0)))
            altura = parse_raw_val(perfil_completo.get('ALTURA', perfil_completo.get('Altura', 0)))
            edad = parse_raw_val(perfil_completo.get('EDAD', perfil_completo.get('Edad', 0)))
            genero = str(perfil_completo.get('GENERO', perfil_completo.get('Sexo', 'M')))
            
            is_fem = genero.strip().upper() in ['F', 'FEMENINO', 'MUJER']
            es_adulto = (edad >= 18)

            ocupacion = parse_raw_val(perfil_completo.get('ocupacion', perfil_completo.get('OCUPACION', 1.375)))
            if ocupacion > 10: ocupacion = ocupacion / 1000.0
            
            fecha_act_peso = perfil_completo.get('Fecha_Actualizacion', 'No registrada')
            if fecha_act_peso == 'S/D' or not fecha_act_peso:
                fecha_act_peso = "No registrada"

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
                lineas_medidas += f"• Cintura: `{cintura:.1f}` cm\n• Cuello: `{cuello:.1f}` cm\n"
                if is_fem:
                    lineas_medidas += f"• Cadera: `{cadera:.1f}` cm\n"
            else:
                lineas_medidas = "• *Modalidad Pediátrica/Juvenil (Cálculo OMS sin circunferencias)*\n"

            alerta_medidas = ""
            if es_adulto:
                if cintura <= 1.0 or cuello <= 1.0 or (is_fem and cadera <= 1.0):
                    alerta_medidas = "\n⚠️ **Atención:** Tenés 18 años o más. Actualizá tus medidas con los botones de abajo para activar el cálculo de masa magra de alta precisión clínica.\n"

            txt_perfil = (
                f"👤 **{traducciones.get('09_perfil_titulo_biometrico', 'Perfil Biométrico Actual')} ({mes_actual}):**\n\n"
                f"• {traducciones.get('09_perfil_lbl_nombre', 'Nombre')}: `{nombre}`\n"
                f"• {traducciones.get('09_perfil_lbl_edad', 'Edad')}: `{edad:.0f}` {traducciones.get('09_perfil_anos', 'años')}\n"
                f"• {traducciones.get('09_perfil_lbl_peso', 'Peso')}: `{peso:.1f}` kg *(Act: {fecha_act_peso})*\n"
                f"• {traducciones.get('09_perfil_lbl_altura', 'Altura')}: `{altura:.1f}` cm\n"
                f"{lineas_medidas}"
                f"• {traducciones.get('09_perfil_lbl_ritmo', 'Ritmo de avance')}: `{str(ritmo).capitalize()}`\n"
                f"• {traducciones.get('09_perfil_lbl_idioma', 'Idioma')}: `{str(idioma_usr).upper()}`\n"
                f"• {traducciones.get('09_perfil_lbl_profesional', 'ID Profesional')}: `{profesional}`\n\n"
                f"• **{traducciones.get('09_perfil_lbl_tmb', 'TMB Estimada')}:** `{tmb:.0f} kcal/día`\n"
                f"• **{traducciones.get('09_perfil_lbl_get', 'GET Estimado')}:** `{get_val:.0f} kcal/día`\n"
                f"• **{traducciones.get('09_perfil_lbl_etapa', 'Meta / Peso de Etapa')}:** `{peso_etapa:.1f} kg`\n"
                f"{alerta_medidas}"
            )
        else:
            txt_perfil = traducciones.get('09_perfil_no_registrado', "👤 **Perfil no registrado para este mes.** Podés cargar tu peso ejecutando:\n`/peso 82.5`")

        keyboard = [
            [
                InlineKeyboardButton(traducciones.get('09_btn_edit_peso', "⚖️ Peso"), callback_data="edit_perfil_peso"),
                InlineKeyboardButton(traducciones.get('09_btn_edit_altura', "📏 Altura"), callback_data="edit_perfil_altura")
            ]
        ]

        if es_adulto:
            fila_cintas = [
                InlineKeyboardButton(traducciones.get('09_btn_edit_cintura', "📏 Cintura"), callback_data="edit_perfil_cintura"),
                InlineKeyboardButton(traducciones.get('09_btn_edit_cuello', "📐 Cuello"), callback_data="edit_perfil_cuello")
            ]
            keyboard.append(fila_cintas)
            if is_fem:
                keyboard.append([InlineKeyboardButton("📐 Cadera", callback_data="edit_perfil_cadera")])

        keyboard.extend([
            [
                InlineKeyboardButton(traducciones.get('09_btn_edit_ritmo', "🎯 Ritmo"), callback_data="edit_perfil_ritmo"),
                InlineKeyboardButton(traducciones.get('09_btn_edit_idioma', "🌐 Idioma"), callback_data="edit_perfil_idioma")
            ],
            [
                InlineKeyboardButton(traducciones.get('09_btn_edit_nombre', "👤 Nombre"), callback_data="edit_perfil_nombre"),
                InlineKeyboardButton(traducciones.get('09_btn_edit_prof', "🩺 Profesional"), callback_data="edit_perfil_prof")
            ]
        ])
        markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(txt_perfil, reply_markup=markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error al consultar perfil: {e}")
        txt_err_read = traducciones.get('09_perfil_error_lectura', "⚠️ Ocurrió un error al leer tu perfil: {e}").format(e=e)
        await update.message.reply_text(txt_err_read, parse_mode="Markdown")
        
async def cmd_cancelar_conversacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.message:
        await update.message.reply_text("❌ Operación cancelada.", parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Operación cancelada.", parse_mode="Markdown")
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
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    if data == "edit_perfil_peso":
        context.user_data['awaiting_edit_perfil_peso'] = True
        msg = await query.message.reply_text("⚖️ Por favor, ingresá tu nuevo peso en kg (ej: `78.5`):", parse_mode="Markdown")
        context.user_data['msg_solicitud_perfil_id'] = msg.message_id
    elif data == "edit_perfil_altura":
        context.user_data['awaiting_edit_perfil_altura'] = True
        msg = await query.message.reply_text("📏 Por favor, ingresá tu nueva altura en cm (ej: `175`):", parse_mode="Markdown")
        context.user_data['msg_solicitud_perfil_id'] = msg.message_id
    elif data == "edit_perfil_cintura":
        context.user_data['awaiting_edit_perfil_cintura'] = True
        msg = await query.message.reply_text("📏 Por favor, ingresá el nuevo perímetro de tu cintura en cm (ej: `84`):", parse_mode="Markdown")
        context.user_data['msg_solicitud_perfil_id'] = msg.message_id
    elif data == "edit_perfil_cuello":
        context.user_data['awaiting_edit_perfil_cuello'] = True
        msg = await query.message.reply_text("📐 Por favor, ingresá el nuevo perímetro de tu cuello en cm (ej: `37`):", parse_mode="Markdown")
        context.user_data['msg_solicitud_perfil_id'] = msg.message_id
    elif data == "edit_perfil_cadera":
        context.user_data['awaiting_edit_perfil_cadera'] = True
        msg = await query.message.reply_text("📐 Por favor, ingresá el nuevo perímetro de tu cadera en cm (ej: `104`):", parse_mode="Markdown")
        context.user_data['msg_solicitud_perfil_id'] = msg.message_id
    elif data == "edit_perfil_nombre":
        context.user_data['awaiting_edit_perfil_nombre'] = True
        msg = await query.message.reply_text("👤 Por favor, ingresá tu nuevo Nombre y Apellido:", parse_mode="Markdown")
        context.user_data['msg_solicitud_perfil_id'] = msg.message_id
    elif data == "edit_perfil_prof":
        context.user_data['awaiting_edit_perfil_prof'] = True
        msg = await query.message.reply_text("🩺 Por favor, ingresá el ID de Telegram de tu nuevo profesional:", parse_mode="Markdown")
        context.user_data['msg_solicitud_perfil_id'] = msg.message_id
    elif data == "edit_perfil_ritmo":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🟢 Tranquilo / Lento", callback_data="set_ritmo_1")],
            [InlineKeyboardButton("🟡 Moderado", callback_data="set_ritmo_2")],
            [InlineKeyboardButton("🔴 Intenso / Rápido", callback_data="set_ritmo_3")]
        ])
        await query.message.reply_text("🎯 Seleccioná tu nuevo ritmo de avance deseado:", reply_markup=keyboard, parse_mode="Markdown")
    elif data == "edit_perfil_idioma":
        idiomas_disp = await obtener_idiomas_disponibles_db() if 'obtener_idiomas_disponibles_db' in globals() else [{'codigo': 'es', 'nombre': 'Español', 'bandera': '🇪🇸'}, {'codigo': 'en', 'nombre': 'English', 'bandera': '🇺🇸'}]
        b_list = [[InlineKeyboardButton(f"{i['bandera']} {i['nombre']}", callback_data=f"set_lang_{i['codigo']}")] for i in idiomas_disp]
        await query.message.reply_text("🌐 Seleccioná tu idioma preferido:", reply_markup=InlineKeyboardMarkup(b_list), parse_mode="Markdown")
    elif data.startswith("set_ritmo_"):
        val_r = data.replace("set_ritmo_", "")
        ritmos_map = {"1": "tranquilo", "2": "moderado", "3": "intenso"}
        ritmo_txt = ritmos_map.get(val_r, "moderado")
        actualizar_ritmo_usuario(user_id, ritmo_txt)
        msg_ok = f"✅ ¡Ritmo actualizado exitosamente a *{ritmo_txt.capitalize()}*!"
        await query.edit_message_text(msg_ok, parse_mode="Markdown")
    elif data.startswith("set_lang_"):
        nuevo_lang = data.replace("set_lang_", "")
        actualizar_idioma_usuario(user_id, nuevo_lang)
        msg_ok = f"✅ ¡Idioma actualizado exitosamente a *{nuevo_lang.upper()}*!"
        await query.edit_message_text(msg_ok, parse_mode="Markdown")


#                       INICIO                        COMANDOS BIOMETRICOS                           INICIO
# ======================================================================================================================================

@requiere_registro
async def cmd_peso_rapido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

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
        perfil = obtener_perfil_usuario(user_id, mes_target=mes_actual) if 'obtener_perfil_usuario' in globals() else {}
        peso_base = parse_raw_val(perfil.get('PESO', perfil.get('Peso', 0))) if perfil else 0
        ultimo_informado = parse_raw_val(perfil.get('peso_actual', 0)) if perfil else 0
        
        if peso_base > 0:
            txt_actual = f"⚖️ **Peso base registrado ({mes_actual}):** `{peso_base:.1f} kg`\n"
            if ultimo_informado > 0 and ultimo_informado != peso_base:
                txt_actual += f"📊 **Último peso informado en el mes:** `{ultimo_informado:.1f} kg`\n"
            
            dia_actual = ahora.day
            if dia_actual <= 14:
                txt_actual += "\n⏳ *Tu próximo control de peso se habilitará a partir del día 15.*"
            elif 15 <= dia_actual <= 25:
                txt_actual += "\nPara ingresar tu control quincenal y calibrar tu factor, escribí:\n`/peso [nuevo_peso]` (ejemplo: `/peso 96`)"
            else:
                txt_actual += "\nPara ingresar tu peso de cierre de mes, escribí:\n`/peso [nuevo_peso]` (ejemplo: `/peso 96`)"
        else:
            txt_actual = "⚠️ No tenés un peso registrado para este mes.\n\nPara registrarlo, escribí:\n`/peso [tu_peso]` (ejemplo: `/peso 100`)"
        
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
        txt_err = "⚠️ Por favor, ingresá un peso válido en kg entre 30 y 300 (ejemplo: `/peso 82.5`)."
        await update.message.reply_text(txt_err, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error en cmd_peso_rapido para {user_id}: {e}")
        await update.message.reply_text(f"❌ Error al guardar el peso: {e}")
                                        
async def mostrar_resumen_presion_mes(query_or_update, user_id, mes_str):
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    df_presion = obtener_datos_presion_db(user_id)
    if df_presion.empty:
        txt = f"🩺 No se encontraron registros de presión para el usuario `{user_id}`."
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(txt, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(txt, parse_mode="Markdown")
        return

    df_p_mes = df_presion[df_presion['Fecha_Dia'].str.startswith(mes_str)] if 'Fecha_Dia' in df_presion.columns else pd.DataFrame()
    if df_p_mes.empty:
        txt = f"🩺 No se encontraron registros de presión para el mes `{mes_str}`."
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(txt, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(txt, parse_mode="Markdown")
        return

    alta_prom = df_p_mes['Alta'].mean()
    baja_prom = df_p_mes['Baja'].mean()
    pul_prom = df_p_mes[df_p_mes['Pulsaciones'] > 0]['Pulsaciones'].mean() if 'Pulsaciones' in df_p_mes.columns else 0

    titulo_resumen = f"🩺 <b>Resumen de Presión Arterial ({mes_str}):</b>"
    mediciones_reg = f"• Mediciones registradas: `{len(df_p_mes)}`"
    prom_alta = f"• <b>Promedio Alta (Sistólica):</b> `{alta_prom:.1f} mmHg`"
    prom_baja = f"• <b>Promedio Baja (Diastólica):</b> `{baja_prom:.1f} mmHg`"
    
    txt = f"{titulo_resumen}\n\n{mediciones_reg}\n{prom_alta}\n{prom_baja}\n"

    if pul_prom > 0:
        prom_pulso = f"• <b>Pulsaciones promedio:</b> `{pul_prom:.1f} lpm`"
        txt += f"{prom_pulso}\n"

    btn_texto = "📄 Descargar PDF de Presión"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_texto, callback_data=f"descargar_pdf_presion_{mes_str}")]
    ])

    if hasattr(query_or_update, 'edit_message_text'):
        await query_or_update.edit_message_text(txt, reply_markup=keyboard, parse_mode="HTML")
    else:
        await query_or_update.message.reply_text(txt, reply_markup=keyboard, parse_mode="HTML")
  
async def _sub_manejar_foto_presion(update, context, res_presion, msg):
    user_id = update.effective_user.id
    alta = float(res_presion.get("alta", 0))
    baja = float(res_presion.get("baja", 0))
    pulsaciones = float(res_presion.get("pulsaciones", 0))
    
    if not (70 <= alta <= 250) or not (40 <= baja <= 150) or (pulsaciones > 0 and not (30 <= pulsaciones <= 220)):
        txt_error_presion = (
            "⚠️ **Lectura de presión atípica o errónea**\n\n"
            f"Los valores detectados en la imagen (`{alta:.0f}/{baja:.0f} mmHg`) "
            "están fuera de los rangos biológicos lógicos.\n\n"
            "Por favor, registrala manualmente usando:\n`/presi [alta],[baja],[pulsaciones]` (ej: `/presi 120,80,75`)."
        )
        await msg.edit_text(txt_error_presion, parse_mode="Markdown")
        return

    context.user_data['pending_presion_foto'] = {"alta": alta, "baja": baja, "pulsaciones": pulsaciones}
    pul_txt = f" | Pulsaciones: `{pulsaciones:.0f} lpm`" if pulsaciones > 0 else ""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Agregar Nota", callback_data="presion_pedir_nota")],
        [InlineKeyboardButton("💾 Guardar sin Nota", callback_data="presion_guardar_directo")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_presion_foto")]
    ])

    mensaje_final = (
        f"🩺 **Tensiómetro detectado en la imagen:**\n\n"
        f"• Presión Alta: `{alta:.0f} mmHg`\n"
        f"• Presión Baja: `{baja:.0f} mmHg`{pul_txt}\n\n"
        f"Seleccioná una opción para continuar:"
    )
    await msg.edit_text(mensaje_final, reply_markup=keyboard, parse_mode="Markdown")
     
def generar_pdf_presion_bytes(mes_str, df_presion, user_id):
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1E3A8A'), spaceAfter=4)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor('#1E293B'))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8.5, leading=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)

    t_titulo_tmpl = traducciones.get("09_PDF_presion_titulo", "Detalle Diario de Presion Arterial - {mes_str}")
    t_usr_tmpl = traducciones.get("09_PDF_presion_usuario_id", "**Usuario Telegram ID:** {user_id}")

    story = [
        Paragraph(f"<b>{t_titulo_tmpl.format(mes_str=mes_str)}</b>", title_style),
        Paragraph(t_usr_tmpl.format(user_id=user_id), body_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=10)
    ]

    if df_presion.empty:
        msg_vacio = traducciones.get("09_PDF_presion_sin_reg", "No hay registros de presion para este mes.")
        story.append(Paragraph(msg_vacio, body_style))
    else:
        table_data = [[
            Paragraph("Fecha y Hora", header_style),
            Paragraph("Alta (mmHg)", header_style),
            Paragraph("Baja (mmHg)", header_style),
            Paragraph("Pulsaciones", header_style),
            Paragraph("Nota / Detalle", header_style)
        ]]

        for _, r in df_presion.iterrows():
            table_data.append([
                Paragraph(str(r.get('Fecha_Hora', '')), body_style),
                Paragraph(f"{r.get('Alta', 0):.0f}", body_style),
                Paragraph(f"{r.get('Baja', 0):.0f}", body_style),
                Paragraph(f"{r.get('Pulsaciones', 0):.0f}", body_style),
                Paragraph(str(r.get('Nota', '')), body_style)
            ])

        t = Table(table_data, colWidths=[110, 65, 65, 70, 190])
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

@requiere_registro
async def cmd_presion_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
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
            await update.message.reply_text("⚠️ No podés consultar un mes futuro.", parse_mode="Markdown")
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
        
        txt_registrada = f"Presión registrada:\nAlta: `{alta:.0f}` | Baja: `{baja:.0f}`{pul_str}{nota_str}"
        await update.message.reply_text(txt_registrada, parse_mode="Markdown")
        return

    await update.message.reply_text("Formato incorrecto. Uso: /presi 120,80,70, nota o /presi 08", parse_mode="Markdown")
    
@requiere_registro
async def cmd_factor_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'es'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
    ahora = obtener_ahora_arg()
    
    # --- RESTRICCIÓN TEMPORAL: Solo habilitado a partir del día 15 ---
    if ahora.day < 15:
        await update.message.reply_text(
            "⏳ **Calibración no disponible:** Para mantener la estabilidad de los cálculos, la calibración de gasto con reloj inteligente se habilita únicamente a partir del **día 15** de cada mes.",
            parse_mode="Markdown"
        )
        return

    mes_actual = ahora.strftime("%Y-%m")
    info_usuario = obtener_datos_usuario_general(user_id) if 'obtener_datos_usuario_general' in globals() else obtener_perfil_usuario(user_id, mes_target=mes_actual)
    
    # --- RESTRICCIÓN DE USO ÚNICO MENSUAL ---
    if info_usuario:
        mes_ultimo_cambio = str(info_usuario.get('reloj_actualizado_mes', '')).strip()
        if mes_ultimo_cambio == mes_actual:
            txt_limite_alcanzado = traducciones.get('09_get_error_limite_mensual', 
                "⏳ **Límite mensual alcanzado:**\n\n"
                "Ya utilizaste el reloj inteligente para calibrar tu gasto este mes. "
                "Para mantener la estabilidad del plan, solo se permite un ajuste por período."
            )
            await update.message.reply_text(txt_limite_alcanzado, parse_mode="Markdown")
            return

    raw_text = re.sub(r'^/(factor|fac|get)\w*(@\w+)?', '', update.message.text, flags=re.IGNORECASE).strip()

    if not raw_text:
        txt_ayuda_get = traducciones.get('09_get_ayuda_formato', 
            "Ingresá las calorías totales que registró tu reloj en 24 horas. Ejemplo:\n\n• `/GET 2150`"
        )
        await update.message.reply_text(txt_ayuda_get, parse_mode="Markdown")
        return

    try:
        calorias_reloj = float(raw_text.replace(',', '.'))
        
        # --- FILTRO DE SEGURIDAD ACOTADO (1000 a 4000 kcal) ---
        if not (1000 <= calorias_reloj <= 4000):
            await update.message.reply_text("⚠️ Ingresá un valor de calorías realista (entre 1000 y 4000 kcal).", parse_mode="Markdown")
            return

        perfil = obtener_perfil_usuario(user_id, mes_target=mes_actual)
        if not perfil:
            await update.message.reply_text("❌ No se encontró tu perfil activo para este mes. Registrá tu peso primero con `/peso`.", parse_mode="Markdown")
            return

        peso = parse_raw_val(perfil.get('PESO', perfil.get('Peso', 70)))
        altura = parse_raw_val(perfil.get('ALTURA', perfil.get('Altura', 170)))
        edad = parse_raw_val(perfil.get('EDAD', perfil.get('Edad', 40)))
        genero = str(perfil.get('GENERO', perfil.get('Genero', 'masculino')))

        factor_anterior = parse_raw_val(perfil.get('OCUPACION', perfil.get('Ocupacion', 1.375)))
        if factor_anterior <= 0: factor_anterior = 1.375

        tmb, get_anterior = calcular_tmb_y_get(peso, altura, edad, genero, actividad=factor_anterior)
        
        if tmb <= 0:
            await update.message.reply_text("❌ Error al calcular la TMB base.", parse_mode="Markdown")
            return

        # --- APLICAR TOLERANCIA MÁXIMA DEL 20% (0.20) ---
        nuevo_factor = aplicar_calibracion_reloj(
            factor_previo=factor_anterior, 
            get_reloj=calorias_reloj, 
            tmb=tmb, 
            max_variacion_pct=0.20
        )

        _, get_nuevo = calcular_tmb_y_get(peso, altura, edad, genero, actividad=nuevo_factor)

        aviso_tope = ""
        factor_crudo_reloj = round(calorias_reloj / tmb, 3)
        if abs(nuevo_factor - factor_crudo_reloj) > 0.005:
            aviso_tope = "\n⚠️ *Nota de seguridad:* El valor del reloj superaba el 20% de variación respecto a tu tendencia habitual. Se aplicó el tope máximo permitido del 20%.\n"

        context.user_data['temp_nuevo_factor'] = nuevo_factor

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅", callback_data="confirmar_factor_si"), InlineKeyboardButton("❌", callback_data="confirmar_factor_no")]
        ])

        msg_texto = (
            f"📊 **Calibración de Gasto Energético (Reloj):**\n\n"
            f"• Calorías reportadas por el reloj: `{calorias_reloj:.0f} kcal`\n"
            f"• TMB Base estimada: `{tmb:.0f} kcal`\n\n"
            f"• **Gasto Diario Anterior:** `{get_anterior:.0f} kcal`\n"
            f"• **Nuevo Gasto Diario Ajustado:** `{get_nuevo:.0f} kcal`\n\n"
            f"{aviso_tope}"
            f"¿Deseás actualizar tu gasto diario con este valor?"
        )
        await update.message.reply_text(msg_texto, reply_markup=keyboard, parse_mode="Markdown")

    except ValueError:
        await update.message.reply_text("❌ Formato incorrecto. Ingresá un número válido. Ejemplo: `/GET 2150`", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error al previsualizar /factor para {user_id}: {e}")
        await update.message.reply_text(f"⚠️ Ocurrió un error al procesar la solicitud: {e}", parse_mode="Markdown")
                
async def callback_confirmar_factor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "confirmar_factor_no":
        context.user_data.pop('temp_nuevo_factor', None)
        await query.edit_message_text("🚫 Operación cancelada. No se modificó tu gasto energético.", parse_mode="Markdown")
        return

    if data == "confirmar_factor_si":
        nuevo_factor_val = context.user_data.get('temp_nuevo_factor')
        if not nuevo_factor_val:
            await query.edit_message_text("⚠️ Los datos temporales expiraron. Por favor, volvé a enviar el comando `/factor`.", parse_mode="Markdown")
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

            txt_exito_get = (
                f"✅ **¡Gasto energético actualizado con éxito!**\n\n"
                f"• Nuevo Gasto Diario asignado: `{get_final:.0f} kcal`\n"
                f"• Período actualizado: `{mes_actual}`\n"
                f"• Estado: Calibración mensual registrada."
            )
            await query.edit_message_text(txt_exito_get, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error al guardar el factor confirmado para {user_id}: {e}")
            await query.edit_message_text(f"⚠ Ocurrió un error al guardar en la base de datos: {e}", parse_mode="Markdown")
        
        context.user_data.pop('temp_nuevo_factor', None)

# ======================================================================================================================================
#                       FINAL                        COMANDOS INGRESOS                                      FINAL
# ======================================================================================================================================

# =============================================================================================================================================
#                INICIO                            COMANDOS PROFESIONALES                             INICIO 
# =============================================================================================================================================

async def cmd_generar_manual_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando para que el profesional descargue el manual operativo y técnico de 3 páginas.
    Uso: /manual
    """
    prof_id = str(update.effective_user.id).strip()
    
    # Validar si es profesional autorizado
    especialidad_prof = obtener_especialidad_profesional(prof_id)
    if not especialidad_prof:
        await update.message.reply_text("⛔ **Acceso denegado:** Este comando es exclusivo para profesionales registrados.", parse_mode="Markdown")
        return

    msg_espera = await update.message.reply_text("⏳ **Generando el manual operativo oficial de 3 páginas...** Por favor aguarde.", parse_mode="Markdown")

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
        
        c_primario = colors.HexColor('#1E3A8A')  # Azul institucional
        c_secundario = colors.HexColor('#2563EB') # Azul brillante
        c_texto = colors.HexColor('#1E293B')     # Gris oscuro texto
        c_fondo_tbl = colors.HexColor('#F8FAFC')  # Fondo claro tabla
        
        title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20, textColor=c_primario, spaceAfter=4, alignment=1)
        subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=10, leading=13, textColor=c_secundario, spaceAfter=10, alignment=1)
        h1_style = ParagraphStyle('H1Style', parent=styles['Heading2'], fontSize=12, leading=15, textColor=c_primario, spaceBefore=8, spaceAfter=4)
        body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=8.5, leading=11.5, textColor=c_texto, spaceAfter=5)
        bullet_style = ParagraphStyle('BulletStyle', parent=styles['Normal'], fontSize=8.5, leading=11.5, textColor=c_texto, leftIndent=10, spaceAfter=3)
        
        story = []

        # =====================================================================
        # PÁGINA 1: PORTADA Y RESUMEN DE VENTAJAS
        # =====================================================================
        story.append(Paragraph("<b>IA NutriBot — Sistema de Gestión y Supervisión Clínica</b>", title_style))
        story.append(Paragraph("<b>Manual Operativo y Especificaciones Técnicas para Profesionales</b>", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=1.2, color=c_secundario, spaceAfter=8))
        
        story.append(Paragraph("<b>1. Resumen de Ventajas y Propuesta de Valor</b>", h1_style))
        story.append(Paragraph("IA NutriBot combina la accesibilidad masiva de Telegram con una potente capa clínica de supervisión. Sus fortalezas principales son:", body_style))
        
        ventajas = [
            "<b>• Supremacía Clínica:</b> El bot respeta estrictamente los criterios del médico tratante por sobre las fórmulas matemáticas estándar.",
            "<b>• Protección del Tiempo Profesional:</b> Canales de salida <b>unidireccionales</b> (notas y recetas) para evitar chats abiertos y saturación de consultas.",
            "<b>• Alertas de Desvío Automáticas:</b> Al cierre del ciclo mensual, el sistema audita registros y reenvía una copia con alertas si el paciente sale de rango.",
            "<b>• Autogestión Segura:</b> Calibración mediante relojes inteligentes acotada estrictamente a partir del día 15 y con topes del 20%.",
            "<b>• Trazabilidad de 6 Meses:</b> Arquitectura robusta en Python y Supabase para almacenar historiales clínicos consolidados."
        ]
        for v in ventajas:
            story.append(Paragraph(v, bullet_style))
        
        story.append(Spacer(1, 6))
        story.append(Paragraph("<b>2. Seguridad y Privacidad de Datos</b>", h1_style))
        story.append(Paragraph("La plataforma aísla el entorno del usuario general del panel médico. Los pacientes vinculados a un profesional tienen bloqueadas las modificaciones autónomas de peso y GET a mitad de mes.", body_style))
        
        story.append(PageBreak()) # Salto exacto a Página 2

        # =====================================================================
        # PÁGINA 2: GUÍA DE COMANDOS Y FUNCIONES
        # =====================================================================
        story.append(Paragraph("<b>3. Guía de Comandos y Funciones del Módulo Profesional</b>", h1_style))
        story.append(Paragraph("El profesional opera de forma directa mediante comandos de texto y menús interactivos táctiles:", body_style))
        
        tabla_funciones = [
            [Paragraph("<b>Comando</b>", ParagraphStyle('Th', parent=body_style, textColor=colors.white, fontName='Helvetica-Bold')), 
             Paragraph("<b>Descripción y Alcance Operativo</b>", ParagraphStyle('Th2', parent=body_style, textColor=colors.white, fontName='Helvetica-Bold'))],
            
            [Paragraph("<b>/pacientes</b>", body_style), 
             Paragraph("Genera un reporte PDF clínico con el historial de los últimos 6 meses (peso, calorías, macros y presión) de todos los pacientes asignados.", body_style)],
            
            [Paragraph("<b>/informe</b>", body_style), 
             Paragraph("Despliega botones interactivos con nombres e IDs de los pacientes para reenviar el informe mensual en PDF de manera individual.", body_style)],
            
            [Paragraph("<b>/editar_valores</b>", body_style), 
             Paragraph("Panel táctil interactivo. Permite visualizar las metas actuales del paciente (TMB, GET, peso de etapa) y corregirlas al instante en Supabase.", body_style)],
            
            [Paragraph("<b>/enviar_nota</b><br/><i>&lt;id&gt; &lt;texto&gt;</i>", body_style), 
             Paragraph("Envía directivas, ajustes dietarios o recetas directamente al chat privado del paciente de forma institucional y unidireccional.", body_style)]
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
        story.append(Spacer(1, 6))
        story.append(Paragraph("<b>4. Ciclo de Control Clínico</b>", h1_style))
        story.append(Paragraph("• <b>Alta:</b> El paciente ingresa el ID del médico al registrarse (`/alta`). El bot notifica al profesional.<br/>"
                               "• <b>Seguimiento:</b> Control quincenal estricto de restricciones y cumplimiento.<br/>"
                               "• <b>Cierre:</b> Auditoría mensual de desvíos y envío automático de alertas clínicas al médico.", body_style))
        
        story.append(PageBreak()) # Salto exacto a Página 3

        # =====================================================================
        # PÁGINA 3: ESPECIFICACIONES TÉCNICAS Y CIERRE
        # =====================================================================
        story.append(Paragraph("<b>5. Base de Datos: Valores_Clinicos_Profesional</b>", h1_style))
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
        story.append(Spacer(1, 10))
        
        story.append(Paragraph("<b>6. Conclusión del Proyecto</b>", h1_style))
        story.append(Paragraph("Con este desarrollo, IA NutriBot se consolida como una herramienta integral, equilibrando de forma óptima la autonomía del usuario con la rigurosidad del control médico profesional a distancia.", body_style))
        story.append(Spacer(1, 15))
        
        story.append(Paragraph("<b>Sistema Operativo:</b> 100% Sincronizado y Funcional (Módulos 08, 09 y 11)", ParagraphStyle('Firma', parent=body_style, textColor=colors.HexColor('#64748B'))))

        doc.build(story)
        buffer.seek(0)

        await msg_espera.delete()
        await update.message.reply_document(
            document=buffer,
            filename="Manual_Profesional_IA_NutriBot.pdf",
            caption="📄 **¡Aquí tenés el manual oficial de 3 páginas!** Explicación de funciones y ventajas del bot lista para compartir.",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error al generar el manual PDF para el profesional {prof_id}: {e}")
        await msg_espera.edit_text(f"❌ Ocurrió un error al generar el documento PDF: {e}")

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
    from SupabaseModule import obtener_valores_clinicos_profesional
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
    """Comando para que el profesional vea el listado de sus pacientes y genere un reporte PDF avanzado (hasta 6 meses)."""
    prof_id = str(update.effective_user.id).strip()
    
    msg_espera = await update.message.reply_text("⏳ **Buscando pacientes y procesando historial clínico (hasta 6 meses)...**", parse_mode="Markdown")

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
            
            peso_str = obtener_ultimo_peso(u_id)
            recs_presion_all = obtener_registros_presion(u_id)
            presion_str = obtener_ultima_presion(recs_presion_all)
            calorias_str = obtener_promedio_calorias_mes_actual(u_id, ahora)

            texto_reporte += (
                f"👤 **{nombre}** (ID: `{u_id}`)\n"
                f"⚖️ Peso: `{peso_str}` | 🩸 Presión: `{presion_str}`\n"
                f"🔥 Prom. Calorías: `{calorias_str}`\n"
                "--------------------------------------------------\n"
            )

            historial_6m = []
            perfil_dict = obtener_ultimo_perfil_dict(u_id)
            
            df_u = obtener_datos_usuario(u_id) if 'obtener_datos_usuario' in globals() else pd.DataFrame()
            if not df_u.empty and 'Fecha' in df_u.columns:
                df_u['Mes_Filtro'] = df_u['Fecha'].str.slice(0, 7)

            for m_str in meses_a_evaluar:
                prom_prot_m = 0
                prom_grasas_m = 0
                dias_m = 0
                prom_cal_m = 0

                if not df_u.empty and 'Mes_Filtro' in df_u.columns:
                    df_m = df_u[df_u['Mes_Filtro'] == m_str]
                    metricas_m = calcular_metricas_mensuales(df_m, perfil_dict)
                    prom_cal_m = metricas_m.get("prom_cal", 0)
                    prom_prot_m = metricas_m.get("prom_prot", 0)
                    prom_grasas_m = metricas_m.get("prom_grasas", metricas_m.get("prom_grasa", 0))
                    dias_m = metricas_m.get("dias_registrados", 0)

                presion_m_str = "S/D"
                presiones_mes = []
                for p in recs_presion_all:
                    f_pres = str(p.get("Fecha", p.get("fecha", p.get("Fecha_Hora", p.get("fecha_hora", "")))))
                    if m_str in f_pres:
                        s = p.get("Alta", p.get("Sistolica", p.get("sistólica", p.get("sistolica", ""))))
                        d = p.get("Baja", p.get("Diastolica", p.get("diastólica", p.get("diastolica", ""))))
                        if s and d:
                            presiones_mes.append(f"{s}/{d}")
                if presiones_mes:
                    presion_m_str = presiones_mes[-1]

                historial_6m.append({
                    "mes": m_str,
                    "prom_cal": prom_cal_m,
                    "prom_prot": prom_prot_m,
                    "prom_grasas": prom_grasas_m,
                    "presion": presion_m_str,
                    "dias": dias_m
                })

            datos_para_pdf.append({
                "nombre": nombre,
                "user_id": u_id,
                "historial": historial_6m
            })

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph(f"<b>Reporte Clínico Consolidado ({especialidad_prof})</b>", styles['Heading1']))
        elements.append(Paragraph(f"Generado el: {ahora.strftime('%Y-%m-%d')} | Período analizado: Últimos 6 meses", styles['Normal']))
        elements.append(Spacer(1, 15))

        elements.append(Paragraph("<b>Evolución Mensual por Paciente (Calorías, Proteínas, Grasas y Presión)</b>", styles['Heading2']))
        elements.append(Spacer(1, 10))

        for d in datos_para_pdf:
            elements.append(Paragraph(f"<b>Paciente: {d['nombre']} (ID: {d['user_id']})</b>", styles['Normal']))
            hist_data = [["Mes", "Calorías", "Proteínas", "Grasas", "Presión", "Días"]]
            for h in d["historial"]:
                hist_data.append([
                    h["mes"], 
                    f"{h['prom_cal']} kcal", 
                    f"{h['prom_prot']} g", 
                    f"{h['prom_grasas']} g", 
                    h["presion"], 
                    str(h["dias"])
                ])
            
            t_hist = Table(hist_data, colWidths=[80, 100, 95, 95, 102, 80])
            t_hist.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#F8F9F9")),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
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
            filename=f"Reporte_Clinico_{esp_limpia}_{ahora.strftime('%Y-%m')}.pdf",
            caption="📄 **Reporte clínico consolidado generado con éxito.**",
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
    """Manejador del botón para enviar el informe individual al paciente seleccionado por el médico."""
    query = update.callback_query
    await query.answer()
    
    prof_id = str(query.from_user.id).strip()
    data = query.data

    if not data.startswith("enviar_inf_"):
        return

    target_user_id = data.replace("enviar_inf_", "").strip()

    try:
        await query.edit_message_text(f"⏳ Generando y enviando informe al paciente `{target_user_id}`...", parse_mode="Markdown")
        
        # Lógica para reeenviar el informe mensual actual al paciente desde el profesional
        msg_notificacion = "🩺 **Tu profesional a cargo te ha enviado una actualización de tu informe clínico mensual.**"
        await context.bot.send_message(chat_id=int(target_user_id), text=msg_notificacion, parse_mode="Markdown")
        
        await query.edit_message_text(f"✅ **Informe enviado con éxito** al paciente con ID `{target_user_id}`.", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error al enviar informe individual desde el profesional {prof_id} al usuario {target_user_id}: {e}")
        await query.edit_message_text(f"❌ No se pudo enviar el informe al paciente: {e}")


async def cmd_enviar_nota_paciente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando para que el profesional envíe una nota o indicación médica directa al chat del paciente.
    Uso: /enviar_nota <user_id> <mensaje>
    """
    prof_id = str(update.effective_user.id).strip()
    
    especialidad_prof = obtener_especialidad_profesional(prof_id)
    if not especialidad_prof:
        await update.message.reply_text("⛔ No tenés permisos para ejecutar este comando.")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ **Uso incorrecto.**\n"
            "Formato correcto: `/enviar_nota <user_id> <tu mensaje o indicación>`\n"
            "Ejemplo: `/enviar_nota 123456789 Reducir el consumo de sodio en las próximas dos semanas.`",
            parse_mode="Markdown"
        )
        return

    target_user_id = context.args[0].strip()
    nota_texto = " ".join(context.args[1:]).strip()

    try:
        # Validar que el paciente pertenezca a este médico
        pacientes_medico = obtener_pacientes_por_medico(prof_id)
        es_su_paciente = any(str(p["user_id"]) == target_user_id for p in pacientes_medico)

        if not es_su_paciente:
            await update.message.reply_text("⛔ El ID ingresado no corresponde a ninguno de tus pacientes activos.")
            return

        mensaje_paciente = (
            f"🩺 **Indicación de tu médico tratante ({especialidad_prof}):**\n\n"
            f"\"{nota_texto}\""
        )
        
        await context.bot.send_message(chat_id=int(target_user_id), text=mensaje_paciente, parse_mode="Markdown")
        await update.message.reply_text(f"✅ Nota enviada correctamente al paciente con ID `{target_user_id}`.", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error al enviar nota del profesional {prof_id} al paciente {target_user_id}: {e}")
        await update.message.reply_text(f"❌ Ocurrió un error al enviar la nota: {e}")

# ==========================================================================================================================================
#                    FINAL                      COMANDOS PROFESIONALES                               FINAL  
# ==========================================================================================================================================

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
        ING_TERMINOS: [CallbackQueryHandler(ing_aceptar_terminos, pattern="^aceptar_terminos_ok$")],
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
                callback=lambda ctx: proceso_masivo_cobros(ctx),
                when=time(hour=0, minute=5, second=0, tzinfo=tz),
                day=1,
                name="facturacion_masiva_dia_1"
            )
        else:
            print("⚠️ Warning: job_queue is not available.")
       
        app_bot.add_handler(conv_handler_ingreso)

        # ==================================PROFESIONALES===============================================
        app_bot.add_handler(CommandHandler(["pacientes"], cmd_pacientes))[cite: 3]
        app_bot.add_handler(CommandHandler(["informe"], cmd_enviar_informe_actual))[cite: 3]
        app_bot.add_handler(CommandHandler(["nota"], cmd_enviar_nota_paciente))
        app_bot.add_handler(CommandHandler(["valores"], cmd_editar_valores_clinicos))[cite: 3]
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

        # =================================FACTURACIÓN Y PAGOS (TELEGRAM STARS)======================
        app_bot.add_handler(CommandHandler(["pagar", "pay"], cmd_pagar))
        app_bot.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
        app_bot.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))

        # =================================ADMINISTRADOR============================================
        app_bot.add_handler(CommandHandler("cobrar", cmd_forzar_cobro))
        app_bot.add_handler(CommandHandler(["descargar","bajar"], cmd_descargar))
        app_bot.add_handler(CommandHandler(["cargar","subir"], cmd_subir))
        app_bot.add_handler(CommandHandler("desarmar", cmd_desarmar_excel))
        app_bot.add_handler(CommandHandler("armar", cmd_armar_excel))
        app_bot.add_handler(CommandHandler("hablar", cmd_hablar))

        # =================================CALLBACK QUERY HANDLERS====================================
        app_bot.add_handler(CallbackQueryHandler(callback_handler_presion_foto, pattern="^presion_"))
        app_bot.add_handler(CallbackQueryHandler(callback_handler_presion_foto, pattern="^cancelar_presion_foto$"))
        app_bot.add_handler(CallbackQueryHandler(ing_aceptar_terminos, pattern="^aceptar_terminos_ok$"))
        app_bot.add_handler(CallbackQueryHandler(callback_confirmar_factor, pattern="^confirmar_factor_"))
        app_bot.add_handler(CallbackQueryHandler(mostrar_resumen_mes, pattern="^resumen_mes_"))
        app_bot.add_handler(CallbackQueryHandler(generar_y_enviar_pdf_resumen, pattern="^(descargar_pdf_resumen_|pdf_mes_)"))
        
        # Enrutadores para el módulo profesional (listados, informes y edición por botones)[cite: 3]
        app_bot.add_handler(CallbackQueryHandler(callback_enviar_informe_paciente, pattern="^enviar_inf_"))[cite: 3]
        app_bot.add_handler(CallbackQueryHandler(callback_seleccionar_paciente_clinico, pattern="^edit_clinico_sel_"))[cite: 3]
        
        app_bot.add_handler(CallbackQueryHandler(boton_elegir_plan, pattern="^comprar_"))

        app_bot.add_handler(CallbackQueryHandler(callback_btn_momento, pattern="^set_m_"))
        app_bot.add_handler(CallbackQueryHandler(callback_btn_fechas_diario, pattern="^(set_d_|diario_)"))
        app_bot.add_handler(CallbackQueryHandler(callback_btn_editar_item, pattern="^edit_item_"))
        app_bot.add_handler(CallbackQueryHandler(callback_btn_anular_item, pattern="^del_item_"))
        app_bot.add_handler(CallbackQueryHandler(callback_btn_cancelar_registro, pattern="^cancel_entry$"))
        app_bot.add_handler(CallbackQueryHandler(callback_btn_guardar_registro, pattern="^confirm_save$"))        
       
        app_bot.add_handler(CallbackQueryHandler(manejar_callback_eliminacion, pattern="^del_(d_|mom_|reg_|borrar)"))
        app_bot.add_handler(CallbackQueryHandler(manejar_callback_eliminacion, pattern="^del_"))

        app_bot.add_handler(CallbackQueryHandler(callback_handler_editar_perfil, pattern="^(edit_perfil_|set_ritmo_|set_ocup_|set_lang_)"))

        # =================================MESSAGE HANDLERS===========================================
        app_bot.add_handler(MessageHandler(filters.VOICE, handle_voice))
        app_bot.add_handler(MessageHandler(filters.PHOTO, handle_photo))
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


