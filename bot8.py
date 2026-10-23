
# ==============================================================================================================================================
#                                 INICIO                                   CABECERA 2026 09 05                                     INICIO
#                                  https://github.com/rosalexxi/telegram-bot-nutricion
#                                  https://dashboard.render.com/web/srv-d9lcifijnfac73a8q1eg/events
#                                  https://supabase.com/dashboard/project/xsheilmjewqcvhmyqlnx/editor/17944?schema=public
#                                  https://dashboard.uptimerobot.com/monitors
#                                  https://ttsmaker.com/
# ==============================================================================================================================================

import glob
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
import html  
import cv2
import numpy as np
import requests
import math
import urllib.request
import urllib.parse
import calendar
import subprocess
import google.generativeai as genai

from typing import Dict, Tuple, List, Optional, Any            
from urllib.parse import urlparse 
from datetime import datetime, date, timedelta, time
from dateutil.relativedelta import relativedelta
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
    genai.configure(api_key=GEMINI_API_KEY)

# Modelos actuales de Gemini API
MODELO_TEXTO = os.getenv(
    "MODELO_TEXTO", "gemini-3.8-flash"
)
MODELO_FOTO = os.getenv(
    "MODELO_FOTO", "gemini-3.8-flash"
)
MODELO_AUDIO = os.getenv(
    "MODELO_AUDIO", "gemini-3.8-flash"
)

# Respaldo y emergencia
MODELO_RESPALDO = os.getenv(
    "MODELO_RESPALDO", "gemini-3.6-flash"
)
MODELO_EMERGENCIA = "gemini-3.5-flash-lite"

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
                        <option value="gramos" data-var="_02_opt_gramos">Porción de 100 Gramos</option>
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

        prompt_ia = (
            f"Analiza la siguiente receta o listado de ingredientes: '{receta}'. "
            f"Desglósalo estrictamente **ítem por ítem**. Para cada ítem, calcula:\n"
            f"- El nombre del alimento ('alimento'), escrito en el idioma '{lang}'\n"
            f"- El peso estimado en gramos ('peso')\n"
            f"- Las calorías ('calorias')\n"
            f"- Las proteínas en gramos ('proteinas')\n"
            f"- Las grasas en gramos ('grasas')\n"
            f"- Los carbohidratos en gramos ('carbohidratos')\n"
            f"- Las fibras en gramos ('fibras')\n\n"
            f"REGLA MATEMÁTICA: Las calorías deben coincidir con la suma aproximada de (Proteínas*4) + (Carbohidratos*4) + (Grasas*9).\n"
            f"Devuelve ÚNICAMENTE un JSON con esta estructura exacta:\n"
            "{\"items\": [{\"alimento\": \"...\", \"peso\": 0.0, \"calorias\": 0.0, \"proteinas\": 0.0, \"grasas\": 0.0, \"carbohidratos\": 0.0, \"fibras\": 0.0}]}"
        )

        instruccion = "Eres un nutricionista clínico experto en análisis de recetas y desglose de macronutrientes."
        
        try:
            # Intento 1: Modelo principal (Flash)
            model = genai.GenerativeModel(MODELO_TEXTO, system_instruction=instruccion)
            response = model.generate_content(
                prompt_ia,
                generation_config={"response_mime_type": "application/json", "temperature": 0.1}
            )
            resultado_json = json.loads(response.text)
            
        except Exception as e_prin:
            logger.warning(f"⚠️ Falla en modelo principal Flash (Receta), activando respaldo: {e_prin}")
            # Intento 2: Modelo de contingencia (Pro)
            MODELO_RESPALDO = os.getenv("MODELO_RESPALDO", "gemini-1.5-pro")
            model_resp = genai.GenerativeModel(MODELO_RESPALDO, system_instruction=instruccion)
            response_resp = model_resp.generate_content(
                prompt_ia,
                generation_config={"response_mime_type": "application/json", "temperature": 0.1}
            )
            resultado_json = json.loads(response_resp.text)

        items = resultado_json.get("items", [])

        # Cálculos de porciones/gramos intactos
        if tipo_calculo == 'porciones' and porciones > 1:
            for item in items:
                for k in ['peso', 'calorias', 'proteinas', 'grasas', 'carbohidratos', 'fibras']:
                    item[k] = round(float(item.get(k, 0)) / porciones, 2)
        elif tipo_calculo == 'gramos':
            total_peso = sum(float(i.get('peso', 0)) for i in items)
            if total_peso > 0:
                factor = 100.0 / total_peso
                for item in items:
                    for k in ['peso', 'calorias', 'proteinas', 'grasas', 'carbohidratos', 'fibras']:
                        item[k] = round(float(item.get(k, 0)) * factor, 2)

        return jsonify({"nombre": codigo, "descripcion": descripcion, "items": items}), 200

    except Exception as e:
        logger.error(f"Error en api_calcular_receta: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
        
@app.route('/api/guardar-comida', methods=['POST'])
def api_guardar_comida():
    try:
        data = request.json
        user_id = data.get('user_id')
        fila = data.get('fila')

        if not user_id or not fila:
            return jsonify({"error": "Faltan datos de usuario o de la receta."}), 400

        # Llama a la función que ya tenés definida para guardar en Supabase
        codigo_guardado = guardar_comida_precargada_db(user_id, fila)

        return jsonify({
            "message": "Receta guardada exitosamente en tu base de datos.",
            "codigo_guardado": codigo_guardado
        }), 200

    except Exception as e:
        logger.error(f"Error en api_guardar_comida: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# =====================================================================================================================================
#              FINAL                                  PAGINA WEB (CALCULADORA UNICA)                  FINAL
# =====================================================================================================================================

# =============================================================================================================================================
#              INICIO                                   FUNCIONES SUPABASE                           INICIO
# =============================================================================================================================================

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
            msg_no_enc = traducciones.get("03_bot_excel_no_enc", "❌ No encuentro el archivo `{ruta_archivo}` en el servidor.").format(ruta_archivo=ruta_archivo)
            await update.message.reply_text(msg_no_enc, parse_mode="Markdown")
            return

        df = pd.read_excel(ruta_archivo)
        df.columns = [str(c).strip() for c in df.columns]

        # Buscar nombres reales de columnas 'variables' y 'ES' sin importar mayúsculas/minúsculas
        col_vars = next((c for c in df.columns if c.lower() == 'variables'), None)
        col_es = next((c for c in df.columns if c.upper() == 'ES'), None)

        if not col_vars or not col_es:
            msg_cols = traducciones.get("03_bot_excel_columnas", "❌ El archivo base debe tener columnas 'variables' y 'ES'.")
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

        msg_exito = traducciones.get(
            "03_bot_desarmar_exito", 
            "✅ **¡Archivo desarmado detectando todas las variables y corchetes!**\n\n1. Subilo a Google Drive, agregale las columnas de idiomas que quieras (`EN`, `IT`, etc.) y traducilo.\n2. La segunda pestaña (`diccionario_vars`) ahora indexa el 100% de las variables sin cortes.\n3. Cuando termines, mandámelo con `/armar`."
        )
        await update.message.reply_document(
            document=buffer_out,
            filename=nombre_salida,
            caption=msg_exito,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error en desarmar Excel: {e}", exc_info=True)
        msg_err_gen = traducciones.get("03_bot_err_gen", "❌ Error: `{e}`").format(e=e)
        await update.message.reply_text(msg_err_gen, parse_mode="Markdown")

# ---------------------------------------------------------------------------------------------------------------------------------------------
# COMANDO DE TELEGRAM: /armar (Lee el Excel desarmado directamente del servidor, restaura variables y sube a Supabase)
# CÓMO SE USA EN TELEGRAM: /armar
# ¿QUÉ HACE?:
#   1. Busca el archivo 'multi_desarmado.xlsx' (o el que corresponda) directamente en la carpeta del servidor.
#   2. Lee las solapas 'traduccion' y 'diccionario_vars'.
#   3. Reemplaza todos los códigos __VAR_XXXX__ por sus llaves {variable} o corchetes [variable] original.
#   4. Borra y vuelve a crear la tabla 'multi' en Supabase con la información limpia y traducida.
# ---------------------------------------------------------------------------------------------------------------------------------------------
async def cmd_armar_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if not es_administrador(user_id):
        return

    nombre_tabla = "multi"
    ruta_archivo = f"{nombre_tabla}_desarmado.xlsx"

    if not os.path.exists(ruta_archivo):
        msg_no_enc = traducciones.get("03_bot_armar_no_enc", "❌ No encuentro el archivo `{ruta_archivo}` en el servidor. Asegurate de haber subido el archivo traducido al repositorio o carpeta del bot.").format(ruta_archivo=ruta_archivo)
        await update.message.reply_text(msg_no_enc, parse_mode="Markdown")
        return

    msg_leyendo = traducciones.get("03_bot_armar_leyendo", "🔄 Leyendo del servidor, ensamblando traducciones y sincronizando Supabase...")
    mensaje_espera = await update.message.reply_text(msg_leyendo, parse_mode="Markdown")

    try:
        xls = pd.ExcelFile(ruta_archivo)
        sheets = xls.sheet_names

        if 'traduccion' not in sheets or 'diccionario_vars' not in sheets:
            msg_solapas = traducciones.get("03_bot_armar_solapas", "❌ El archivo en el servidor no tiene las solapas requeridas ('traduccion' y 'diccionario_vars').")
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

        # Regex tolerante a espacios, mayúsculas/minúsculas que Google Translate suele alterar (ej: __ var_0001 __)
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

                # 1. Restaurar todas las variables {var} y [var] aunque el traductor haya metido espacios o minúsculas
                texto = patron_restaurar.sub(restaurar_token, texto)
                # 2. Reparar saltos de línea '\ n' que Google Translate suele separar con espacio
                texto = re.sub(r'\\\s+n', r'\\n', texto)

                nueva_columna.append(texto)
            
            df_trad[col] = nueva_columna

        # Guardar copia limpia localmente como 'multi.xlsx'
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

        msg_exito = traducciones.get("03_bot_armar_exito", "🏆 **¡Traducción aplicada con éxito!**\nLa tabla `{nombre_tabla}` fue completamente reemplazada en Supabase con {filas_insertadas} registros procesados desde el servidor.").format(nombre_tabla=nombre_tabla, filas_insertadas=filas_insertadas)
        await mensaje_espera.edit_text(msg_exito, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error armando Excel desde el servidor: {e}", exc_info=True)
        msg_err_armar = traducciones.get("03_bot_armar_err", "❌ Error al ensamblar: `{e}`").format(e=e)
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
        msg_formato = traducciones.get("03_bot_subir_formato", "⚠️ Por favor, indica el nombre de la tabla a importar.\nEjemplo: `/subir multi`")
        await update.message.reply_text(msg_formato, parse_mode="Markdown")
        return

    nombre_tabla = context.args[0].strip()
    ruta_archivo = f"{nombre_tabla}.xlsx"

    if not os.path.exists(ruta_archivo):
        msg_no_enc = traducciones.get("03_bot_subir_no_enc", "❌ No encontré el archivo `{ruta_archivo}` en el servidor. Asegurate de haberlo subido al repositorio de GitHub.").format(ruta_archivo=ruta_archivo)
        await update.message.reply_text(msg_no_enc, parse_mode="Markdown")
        return

    msg_leyendo = traducciones.get("03_bot_subir_leyendo", "🔄 Leyendo `{ruta_archivo}` del servidor y reescribiendo la tabla `{nombre_tabla}` en Supabase...").format(ruta_archivo=ruta_archivo, nombre_tabla=nombre_tabla)
    mensaje_espera = await update.message.reply_text(msg_leyendo, parse_mode="Markdown")

    try:
        df = pd.read_excel(ruta_archivo)

        if df.empty:
            msg_vacio = traducciones.get("03_bot_subir_vacio", "⚠️ El archivo `{ruta_archivo}` está vacío.").format(ruta_archivo=ruta_archivo)
            await mensaje_espera.edit_text(msg_vacio, parse_mode="Markdown")
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

        msg_exito = traducciones.get("03_bot_subir_exito", "✅ ¡Éxito! La tabla `{nombre_tabla}` fue leída del servidor y sincronizada en Supabase con {filas_insertadas} registros.").format(nombre_tabla=nombre_tabla, filas_insertadas=filas_insertadas)
        await mensaje_espera.edit_text(msg_exito, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error al importar la tabla {nombre_tabla} desde el servidor: {e}", exc_info=True)
        msg_err = traducciones.get("03_bot_subir_err", "❌ Error al importar la tabla: `{e}`").format(e=e)
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
        msg_formato = traducciones.get("03_bot_descargar_formato", "⚠️ Por favor, indica el nombre de la tabla que deseas descargar.\nEjemplo: `/descargar textos_bot` o `/descargar Usuarios`")
        await update.message.reply_text(msg_formato, parse_mode="Markdown")
        return

    nombre_tabla = context.args[0].strip()
    msg_consultando = traducciones.get("03_bot_descargar_consultando", "⏳ Consultando y preparando la tabla `{nombre_tabla}`...").format(nombre_tabla=nombre_tabla)
    mensaje_espera = await update.message.reply_text(msg_consultando, parse_mode="Markdown")

    try:
        conn, cur = _asegurar_tabla_y_conectar(nombre_tabla, tipo_tabla="comida")
        query = f'SELECT * FROM "{nombre_tabla}"'
        df = pd.read_sql(query, conn)
        
        cur.close()
        conn.close()

        if df.empty:
            msg_vacia = traducciones.get("03_bot_descargar_vacia", "⚠️ La tabla `{nombre_tabla}` existe pero está vacía.").format(nombre_tabla=nombre_tabla)
            await mensaje_espera.edit_text(msg_vacia, parse_mode="Markdown")
            return

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=nombre_tabla[:31])
        buffer.seek(0)

        filename = f"{nombre_tabla}.xlsx"
        
        msg_exito = traducciones.get("03_bot_descargar_exito", "✅ Aquí tienes el respaldo de la tabla *{nombre_tabla}* ({len_df} registros).").format(nombre_tabla=nombre_tabla, len_df=len(df))
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
        msg_err = traducciones.get("03_bot_descargar_err", "❌ No se pudo descargar la tabla `{nombre_tabla}`.\nError: `{e}`").format(nombre_tabla=nombre_tabla, e=e)
        await mensaje_espera.edit_text(msg_err, parse_mode="Markdown")   

# =========================================================================================================================================
#              FINAL                            FUNCIONES SUPABASE                 FINAL
# ==========================================================================================================================================

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
    lang = obtener_idioma_usuario(uid) or '$1'
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
        await limpiar_teclado_anterior(update, context)
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
            
            df_datos = obtener_datos_usuario(user_id) 
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
    prompt = (
        "Analiza esta imagen. ¿Es la pantalla de un tensiómetro digital que muestra valores de presión arterial? "
        "Si es así, extrae los valores numéricos de la presión sistólica (Alta), diastólica (Baja) y las pulsaciones. "
        "Responde ÚNICAMENTE en formato JSON: {\"es_presion\": true/false, \"alta\": 0.0, \"baja\": 0.0, \"pulsaciones\": 0.0}"
    )
    try:
        model = genai.GenerativeModel(MODELO_FOTO)
        imagen_data = {"mime_type": "image/jpeg", "data": base64.b64decode(base64_image)}
        
        response = model.generate_content(
            [prompt, imagen_data],
            generation_config={"response_mime_type": "application/json", "temperature": 0.0}
        )
        return json.loads(response.text)
    except Exception: 
        return {"es_presion": False}
        
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
        model = genai.GenerativeModel(modelo_override or MODELO_TEXTO, system_instruction=system_prompt)
        response = model.generate_content(
            prompt,
            generation_config={"temperature": temperature, "max_output_tokens": max_tokens}
        )
        return response.text.strip() if response.text else ""
    except Exception as e:
        logger.error(f"⚠️ Error en ejecución de IA: {e}")
        return ""
        
def obtener_nombre_lenguaje_ia(user_id=None):
    """Obtiene el nombre completo del lenguaje para la IA desde la tabla Usuarios."""
    if not user_id:
        return "Español"
    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        # Se corrigió la consulta de la columna "lenguajes" a "Idioma"
        cur.execute('SELECT "Idioma" FROM "Usuarios" WHERE "User ID" = %s', (str(user_id),))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row[0]:
            return str(row[0]).strip()
    except Exception as e:
        logger.error(f"Error obteniendo lenguaje IA para {user_id}: {e}")
    return "Español"
    
def analizar_con_groq(prompt_text, user_id=None):
    nombre_lenguaje = obtener_nombre_lenguaje_ia(user_id)
    ahora = obtener_ahora_arg()
    fecha_hoy = ahora.strftime("%Y-%m-%d")
    mes_actual = ahora.strftime("%Y-%m")
    
    system_prompt = (
        f"Sos un asistente inteligente de salud. El usuario se comunica en su idioma ({nombre_lenguaje}). "
        f"La fecha de HOY es {fecha_hoy} y el mes actual es {mes_actual}. "
        f"Clasificá el texto en:\n"
        "1. COMIDA (alimentos/bebidas)\n"
        "2. ACTIVIDAD (ejercicio)\n"
        "3. INFORME_MENSUAL (extrae YYYY-MM en 'parametro')\n"
        "4. INFORME_SEMANAL\n"
        "5. INFORME_DIARIO (extrae YYYY-MM-DD en 'parametro')\n"
        "6. RECHAZO\n\n"
        "REGLA MATEMÁTICA PARA COMIDAS: Las calorías deben coincidir con la suma aproximada de (Proteínas*4) + (Carbohidratos*4) + (Grasas*9).\n"
        "Devolvé EXCLUSIVAMENTE un JSON con este formato exacto:\n"
        "{\"items\": [{\"alimento\": \"...\", \"peso\": 0.0, \"calorias\": 0.0, \"proteinas\": 0.0, \"grasas\": 0.0, \"carbohidratos\": 0.0, \"fibras\": 0.0}], "
        "\"tipo\": \"...\", \"parametro\": \"...\", \"momento\": \"...\", \"dia\": \"...\"}"
    )

    try:
        # Intento 1: Flash Latest
        model = genai.GenerativeModel(MODELO_TEXTO, system_instruction=system_prompt)
        response = model.generate_content(
            prompt_text,
            generation_config={"response_mime_type": "application/json", "temperature": 0.1}
        )
        texto_limpio = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(texto_limpio)
        
    except Exception as e_principal:
        logger.warning(f"⚠️ Falla en Intento 1 (Flash): {e_principal}")
        try:
            # Intento 2: Pro Latest
            model_respaldo = genai.GenerativeModel(MODELO_RESPALDO, system_instruction=system_prompt)
            response_respaldo = model_respaldo.generate_content(
                prompt_text,
                generation_config={"response_mime_type": "application/json", "temperature": 0.1}
            )
            texto_limpio = response_respaldo.text.replace('```json', '').replace('```', '').strip()
            return json.loads(texto_limpio)
            
        except Exception as e_respaldo:
            logger.warning(f"⚠️ Falla en Intento 2 (Pro): {e_respaldo}")
            try:
                # Intento 3: Modelo Clásico
                model_emerg = genai.GenerativeModel(MODELO_EMERGENCIA, system_instruction=system_prompt)
                response_emerg = model_emerg.generate_content(
                    prompt_text,
                    generation_config={"response_mime_type": "application/json", "temperature": 0.1}
                )
                texto_limpio = response_emerg.text.replace('```json', '').replace('```', '').strip()
                return json.loads(texto_limpio)
                
            except Exception as e_emergencia:
                logger.error(f"❌ Error crítico: Los tres modelos fallaron. {e_emergencia}")
                return {"items": [], "tipo": "Rechazo"}
                
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
        
    lang = obtener_idioma_usuario(user_id) or '$1'
    traducciones = obtener_traducciones_db(lang) or {}
    return traducciones.get("05_bot_err_analisis_nutricional", "El análisis nutricional no está disponible temporalmente.")
    
async def generar_recomendacion_mensual_para_pdf(user_id: int, mes_str: str, df_mes, perfil: dict, m: dict, context=None) -> str:
    lang = obtener_idioma_usuario(user_id) or '$1'
    traducciones = obtener_traducciones_db(lang) or {}

    msg_error_inf = traducciones.get("05_bot_err_generar_inf", "No se pudo generar el reporte auditado por la IA.")
    msg_error_comp = traducciones.get("05_bot_err_compilar_inf", "Error al compilar la recomendación de la IA para el reporte.")

    try:
        conteo_frecuencias = analizar_frecuencia_alimentos_mes(user_id, mes_str) or {}

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
    lang = obtener_idioma_usuario(user_id) or '$1'
    traducciones = obtener_traducciones_db(lang) or {}

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
    nombre_lenguaje = obtener_nombre_lenguaje_ia(user_id)

    system_prompt = (
        f"Sos un asistente inteligente de nutrición. El usuario se comunica en su idioma ({nombre_lenguaje}). "
        f"Determiná si la imagen corresponde claramente a un plato de comida o bebida.\n"
        f"REGLAS:\n"
        f"1. Si es comida, desglosá ítem por ítem en el JSON. Asumí porciones estándar si no hay referencia. Las calorías deben cuadrar matemáticamente con los macros.\n"
        f"2. Si es un paisaje, animal, objeto, factura, o escenario general borroso, clasificá como 'Rechazo' con 'items': [].\n"
        f"Devolvé EXCLUSIVAMENTE este JSON:\n"
        "{\"items\": [{\"alimento\": \"...\", \"peso\": 0.0, \"calorias\": 0.0, \"proteinas\": 0.0, \"grasas\": 0.0, \"carbohidratos\": 0.0, \"fibras\": 0.0}], \"tipo\": \"Comida\" o \"Rechazo\"}"
    )

    imagen_data = {"mime_type": "image/jpeg", "data": base64.b64decode(base64_image)}
    texto_instruccion = f"Analiza esta imagen y desglosa los alimentos en el formato JSON indicado. {system_prompt}"

    try:
        # Intento 1: Flash Latest
        model = genai.GenerativeModel(MODELO_FOTO)
        response = await asyncio.to_thread(
            model.generate_content,
            [texto_instruccion, imagen_data],
            generation_config={"response_mime_type": "application/json", "temperature": 0.1}
        )
        texto_limpio = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(texto_limpio)
        
    except Exception as e_prin:
        logger.warning(f"⚠️ Falla en Intento 1 (Flash Foto): {e_prin}")
        try:
            # Intento 2: Pro Latest
            model_resp = genai.GenerativeModel(MODELO_RESPALDO)
            response_resp = await asyncio.to_thread(
                model_resp.generate_content,
                [texto_instruccion, imagen_data],
                generation_config={"response_mime_type": "application/json", "temperature": 0.1}
            )
            texto_limpio = response_resp.text.replace('```json', '').replace('```', '').strip()
            return json.loads(texto_limpio)
            
        except Exception as e_resp:
            logger.warning(f"⚠️ Falla en Intento 2 (Pro Foto): {e_resp}")
            try:
                # Intento 3: Vision clásico
                model_emerg = genai.GenerativeModel(MODELO_FOTO_EMERGENCIA)
                response_emerg = await asyncio.to_thread(
                    model_emerg.generate_content,
                    [texto_instruccion, imagen_data]
                )
                texto_limpio = response_emerg.text.replace('```json', '').replace('```', '').strip()
                return json.loads(texto_limpio)
                
            except Exception as e_emergencia:
                logger.error(f"❌ Error crítico en visión: Todos los modelos fallaron. {e_emergencia}")
                return {"items": [], "tipo": "Rechazo"}
                
# =====================================================================================================================================
#                FINAL                          FUNCIONES IA GROQ                                     FINAL
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

    # 2. Formato HTML puro (sin markdown que rompa la pantalla)
    if momento == 'Actividad':
        t_reg_act = traducciones.get('06_bot_reg_actividad', "📝 <b>Registro de Actividad:</b>")
        t_fecha = traducciones.get('06_bot_label_fecha', "📅 Fecha")
        txt = f"{t_reg_act}\n{t_fecha}: <code>{fecha}</code>\n\n"
    else:
        t_conf_ing = traducciones.get('06_bot_conf_ingesta', "📝 <b>Confirmación de Ingesta:</b>")
        t_fecha = traducciones.get('06_bot_label_fecha', "📅 Fecha")
        t_momento = traducciones.get('06_bot_label_momento', "Momento")
        txt = f"{t_conf_ing}\n{t_fecha}: <code>{fecha}</code> | {t_momento}: <code>{momento}</code>\n\n"

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
            ("Desayuno", "🌅 08-11"),
            ("Almuerzo", "☀️ 11-16"),
            ("Merienda", "☕ 16-20"),
            ("Cena", "🌙 20-00")
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
    
    # --- EVITAMOS EL SILENCIO SI LA IA FALLA ---
    if not items or (total_calorias == 0 and tipo != "Actividad"):
        lang = obtener_idioma_usuario(msg_obj.chat_id) if hasattr(msg_obj, 'chat_id') and 'obtener_idioma_usuario' in globals() else 'es'
        traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
        
        txt_err = traducciones.get("06_bot_error_ia_vacio", "⚠️ No pude identificar alimentos o calorías válidas en tu texto. Por favor, sé más específico (ej: 'Comí 200g de pollo').")
        try: 
            await msg_obj.edit_text(txt_err)
        except Exception: 
            pass
        return
        
    magnitud_calorica = abs(total_calorias)
    # ... (El resto de la función sigue exactamente igual) ...
    limite_exceso = 1000 if tipo == "Actividad" else 2200

    if magnitud_calorica > limite_exceso:
        lang = obtener_idioma_usuario(msg_obj.chat_id) or '$1'
        traducciones = obtener_traducciones_db(lang) or {}
        
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
    lang = obtener_idioma_usuario(user_id) or '$1'
    traducciones = obtener_traducciones_db(lang) or {}

    if data == "presion_guardar_directo":
        datos_presion = context.user_data.pop('pending_presion_foto', None)
        context.user_data.pop('awaiting_presion_nota', None)
        
        if datos_presion:
            alta = float(datos_presion.get("alta", 0))
            baja = float(datos_presion.get("baja", 0))
            pulsaciones = float(datos_presion.get("pulsaciones", 0))
            
            guardar_presion_db(user_id, alta, baja, pulsaciones, nota="")
            
            lbl_pul = traducciones.get("09_presi_lbl_pulsaciones", "Pulsaciones")
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
        txt_pedir_nota = traducciones.get("06_bot_pedir_nota_presion", "✏️ Por favor, escribí la nota o detalle para este registro de presión (o escribí `cancelar` para anular):").replace('\\n', '\n')
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
    context.user_data.pop('awaiting_activity_text', None)
    try: await update.message.delete()
    except: pass
    
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}
    
    txt_analizando = traducciones.get("bot_analizando_actividad_ia", "🤖 Analizando actividad con IA...")
    msg_analizando = await update.message.reply_text(txt_analizando)
    
    try:
        data = await asyncio.to_thread(analizar_con_groq, f"Calcula el gasto calórico de esta actividad física: {raw_text}", user_id)
        if str(data.get("tipo", "")).upper() != "ACTIVIDAD":
            data["tipo"] = "Actividad"
        await procesar_y_mostrar_confirmacion(data, msg_analizando, context)
    except Exception as e:
        txt_err = traducciones.get("bot_err_procesar_actividad", "❌ Error al procesar actividad: {e}").format(e=e)
        await msg_analizando.edit_text(txt_err)
        
async def _sub_manejar_fecha_eliminacion(update, context, raw_text, chat_id):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or '$1'
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
    lang = obtener_idioma_usuario(user_id) or '$1'
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

async def _sub_manejar_fecha_personalizada_ingesta(update, context, raw_text, chat_id):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or '$1'
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
    
    if not items or item_index is None or item_index < 0 or item_index >= len(items):
        context.user_data.pop('awaiting_edit_item_val', None)
        context.user_data.pop('editing_item_idx', None)
        return

    item_actual = items[item_index]
    es_solo_numero = False
    try:
        nuevo_peso = float(raw_text.replace(',', '.').strip())
        es_solo_numero = True
    except ValueError:
        pass

    try: await update.message.delete()
    except: pass

    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    if es_solo_numero:
        peso_anterior = float(item_actual.get('peso', 1))
        if peso_anterior <= 0: peso_anterior = 1.0
        factor = nuevo_peso / peso_anterior
        item_actual['peso'] = nuevo_peso
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
        txt_reanalizando = traducciones.get("bot_reanalizando_desc_ia", "🤖 Re-analizando descripción con IA...")
        msg_analizando = await update.message.reply_text(txt_reanalizando)
        try:
            data = analizar_con_groq(raw_text)
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
            txt_err = traducciones.get("bot_err_reanalizar", "❌ Error al re-analizar: {e}").format(e=e)
            await msg_analizando.edit_text(txt_err)
            context.user_data.pop('awaiting_edit_item_val', None)
            context.user_data.pop('editing_item_idx', None)            

async def _sub_manejar_plantilla_comida(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_text, user_id):
    lang = obtener_idioma_usuario(user_id) or '$1'
    traducciones = obtener_traducciones_db(lang) or {}

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
    try:
        data = analizar_con_groq(transcription)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        user_id = update.effective_user.id
        lang = obtener_idioma_usuario(user_id) or '$1'
        traducciones = obtener_traducciones_db(lang) or {}
        txt_err_aud = traducciones.get('06_bot_error_audio', "❌ Error al procesar el audio con IA: {e}").format(e=e)
        logger.error(f"Error procesando voz de ingesta: {e}")
        await msg.edit_text(txt_err_aud)

async def _sub_manejar_voz_actividad(update, context, transcription, msg):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or '$1'
    traducciones = obtener_traducciones_db(lang) or {}

    context.user_data['awaiting_activity_voice'] = False
    perfil_biometrico = obtener_perfil_usuario(user_id)
    
    prompt_ia = f"El usuario realizó una actividad física descrita por voz. Transcripción: '{transcription}'. Calcula las calorías gastadas utilizando estrictamente su perfil biométrico: {perfil_biometrico}. Devolvé un JSON con los campos 'alimento' y 'calorias'."
    
    try:
        resultado_ia = await asyncio.to_thread(analizar_con_groq, prompt_ia, user_id)
    except Exception as e:
        txt_err = traducciones.get("bot_err_procesar_act_fisica", "❌ Error al procesar la actividad física: {e}").format(e=e)
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
    
async def _sub_manejar_foto_plato_ia(update, context, base64_image, user_caption, msg):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or '$1'
    traducciones = obtener_traducciones_db(lang) or {}

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
    lang = obtener_idioma_usuario(user_id) or '$1'
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
        
@requiere_registro
async def callback_btn_editar_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) or '$1'
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
    lang = obtener_idioma_usuario(user_id) or '$1'
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
    lang = obtener_idioma_usuario(user_id) or '$1'
    traducciones = obtener_traducciones_db(lang) or {}

    context.user_data.pop('pending_items', None)
    context.user_data.pop('last_menu_msg_id', None)
    txt_canc = traducciones.get('06_bot_reg_canc', "🗑️ Registro cancelado.")
    await query.edit_message_text(txt_canc)

async def callback_btn_guardar_registro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) or '$1'
    traducciones = obtener_traducciones_db(lang) or {}
    
    items = context.user_data.get('pending_items', [])
    fecha = context.user_data.get('pending_fecha')
    momento = context.user_data.get('pending_momento')

    if items and fecha and momento:
        tipo_registro = "Actividad" if momento == "Actividad" else "Comida"
        guardar_ingesta_db(user_id, items, fecha, momento, tipo=tipo_registro)
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


