
# =============================================================================================================================================
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

from typing import Dict, Tuple, List, Optional, Any            
from urllib.parse import urlparse 
from datetime import datetime, date, timedelta, time
from google.oauth2.service_account import Credentials
from groq import Groq
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template_string, send_from_directory
from functools import wraps
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
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
    "Desayuno": (8, 11),
    "Almuerzo": (11, 16),
    "Merienda": (16, 20),
    "Cena": (20, 24)
}

load_dotenv()

# Estados de conversación para Perfil y Fecha personalizada
AWAITING_PROFILE_DATA, AWAITING_CUSTOM_DATE, AWAITING_RESUMEN_MES, AWAITING_EDIT_ITEM = range(4)

GROQ_TEXTO      = "openai/gpt-oss-120b"   # Generación principal
GROQ_FOTO       = "qwen/qwen3.8-27b"
GROQ_AUDIO      = "whisper-large-v3"

GROQ_REVISION_2   = "openai/gpt-oss-20b"    # Revisión principal
GROQ_REVISOR  = "qwen/qwen3.8-27b"      # Respaldo

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_SHEETS_KEY_PATH = os.getenv("GOOGLE_SHEETS_KEY_PATH", "credentials.json")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "Registro_Nutricional_Bot")
ARG_TZ = pytz.timezone('America/Argentina/Buenos_Aires')

# Estados del flujo de conversación (Actualizado con todos los pasos)
ING_TERMINOS, ING_IDIOMA, ING_PROFESIONAL, ING_NOMBRE, ING_EDAD, ING_SEXO, ING_ALTURA, ING_PESO, ING_MUNECA, ING_CUELLO, ING_OCUPACION, ING_CUMPLE, ING_RITMO = range(10, 23)

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
    <title id="title-app">IA NutriBot</title>
    <style>
        :root {
            --primary: #27ae60;
            --primary-dark: #219150;
            --secondary: #2c3e50;
            --bg-light: #f4f6f9;
            --text-color: #333;
        }
        
        html, body { 
            min-height: 100dvh; 
            margin: 0; 
            padding: 0; 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background-color: var(--bg-light); 
            color: var(--text-color); 
            display: flex;
            flex-direction: column;
        }
        
        /* Estilos dinámicos para PC (Fondo de nutrición aleatorio) */
        @media (min-width: 1024px) {
            body {
                background-size: cover;
                background-position: center;
                background-attachment: fixed;
                /* Capa semitransparente para que la lectura siga siendo perfecta */
                background-blend-mode: overlay;
                background-color: rgba(244, 246, 249, 0.92);
            }
        }
        
        header { 
            background: white; 
            box-shadow: 0 2px 5px rgba(0,0,0,0.05); 
            position: sticky;
            top: 0;
            z-index: 1000; 
        }
        .nav-container { max-width: 1100px; margin: auto; display: flex; justify-content: space-between; align-items: center; padding: 10px 20px; }
        .logo { font-size: 1.2rem; font-weight: bold; color: var(--primary); text-decoration: none; cursor: pointer; }
        .nav-links { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
        .nav-links a { text-decoration: none; color: var(--secondary); font-weight: 600; font-size: 0.82rem; transition: color 0.2s; cursor: pointer; }
        .nav-links a:hover, .nav-links a.active { color: var(--primary); }
        
        /* Estilo para los botones de banderas dinámicos */
        .lang-flags-container { display: flex; align-items: center; gap: 6px; margin-left: 10px; }
        .flag-btn { background: white; border: 1px solid #ccc; border-radius: 4px; padding: 3px 7px; font-size: 0.8rem; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; gap: 4px; font-weight: 600; color: var(--secondary); transition: all 0.2s; }
        .flag-btn:hover { border-color: var(--primary); background: #f0fdf4; }

        .content-wrapper { 
            max-width: 900px; 
            margin: 20px auto; 
            background: white; 
            padding: 25px; 
            border-radius: 12px; 
            box-shadow: 0 4px 15px rgba(0,0,0,0.05); 
            width: 90%; 
            box-sizing: border-box; 
            flex: 1;
        }

        .content-box { 
            background: #ffffff; 
            border: 1px solid #e2e8f0; 
            border-radius: 8px; 
            padding: 20px; 
            margin-top: 15px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.02); 
        }

        h1 { color: var(--secondary); margin-top: 0; font-size: 1.4rem; margin-bottom: 12px; }
        p { margin-bottom: 0; color: #444; font-size: 0.9rem; text-align: justify; line-height: 1.6; white-space: pre-line; }

        .article-content { overflow: hidden; }
        .newspaper-img {
            float: left; 
            width: 45%; 
            margin-right: 20px; 
            margin-bottom: 10px;
            background-color: #f8fafc;
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
        label { font-weight: bold; display: block; margin-top: 8px; margin-bottom: 2px; font-size: 0.85rem; }
        input[type="text"], input[type="number"], select, textarea { width: 100%; padding: 7px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; font-size: 0.85rem; }
        textarea { height: 70px; resize: vertical; }
        .row { display: flex; gap: 10px; }
        .col { flex: 1; }
        button.calc-btn { background-color: var(--primary); color: white; padding: 9px; border: none; border-radius: 4px; width: 100%; font-size: 0.9rem; font-weight: bold; cursor: pointer; margin-top: 12px; }
        button.calc-btn:hover { background-color: var(--primary-dark); }
        #loading { display: none; text-align: center; margin-top: 8px; font-style: italic; color: #7f8c8d; font-size: 0.85rem; }
        #resultado-section { display: none; margin-top: 15px; border-top: 2px solid #eee; padding-top: 8px; }
        table.calc-tbl { width: 100%; border-collapse: collapse; margin-top: 6px; font-size: 0.8rem; }
        table.calc-tbl th, table.calc-tbl td { border: 1px solid #ddd; padding: 5px; text-align: center; }
        table.calc-tbl th { background-color: #f2f2f2; }
        .btn-save { background-color: #8e44ad; margin-top: 8px; color: white; padding: 9px; border: none; border-radius: 4px; width: 100%; font-weight: bold; cursor: pointer; font-size: 0.85rem; }
        .btn-save:hover { background-color: #71368a; }
        .btn-copy { background-color: #2980b9; margin-top: 6px; color: white; padding: 9px; border: none; border-radius: 4px; width: 100%; font-weight: bold; cursor: pointer; font-size: 0.85rem; }
        .btn-copy:hover { background-color: #1f6391; }
        .user-badge { background: #e0f2fe; color: #0369a1; padding: 5px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; display: inline-block; margin-bottom: 8px; }

        footer { 
            background: var(--secondary); 
            color: white; 
            text-align: center; 
            padding: 18px 15px 35px 15px; 
            flex-shrink: 0;
            font-size: 0.8rem; 
            margin-top: auto;
        }
        .footer-links { 
            margin-bottom: 8px; 
            display: flex; 
            flex-wrap: wrap; 
            justify-content: center; 
            gap: 8px; 
        }
        .footer-link { 
            color: white; 
            text-decoration: none; 
            font-weight: 600; 
            padding: 6px 14px; 
            background: rgba(255,255,255,0.1); 
            border-radius: 4px; 
            font-size: 0.75rem; 
            transition: background 0.2s; 
            display: inline-block; 
            cursor: pointer; 
        }
        .footer-link:hover { background: rgba(255,255,255,0.2); }
        .footer-info { opacity: 0.8; font-size: 0.7rem; }
    </style>
</head>
<body>

<div id="loadingLang" style="display:none; position:fixed; top:20px; right:20px; background:#2c3e50; color:white; padding:10px 15px; border-radius:8px; z-index:9999; font-size:0.85rem; box-shadow: 0 4px 10px rgba(0,0,0,0.2);">
    ⏳ Cargando idioma...
</div>

<header>
    <div class="nav-container">
        <a class="logo" onclick="showSection('inicio')"><span data-var="01_logo">🤖 IA NutriBot</span></a>
        <div class="nav-links">
            <a id="nav-inicio" onclick="showSection('inicio')" class="active" data-var="01_menu_inicio">Inicio</a>
            <a id="nav-ingreso" onclick="showSection('ingreso')" data-var="01_menu_ingreso">Ingreso de Datos</a>
            <a id="nav-alta" onclick="showSection('alta')" data-var="01_menu_alta">El Alta</a>
            <a id="nav-comandos" onclick="showSection('comandos')" data-var="01_menu_comandos">Guía de Comandos</a>
            <a id="nav-faq" onclick="showSection('faq')" data-var="01_menu_faq">Preguntas Frecuentes</a>
            {% if user_id %}
            <a id="nav-calculadora" onclick="showSection('calculadora')" data-var="01_menu_calculadora">Calculadora Web</a>
            {% endif %}
            <!-- Contenedor dinámico de banderas y nombres de idiomas -->
            <div id="langFlagsContainer" class="lang-flags-container"></div>
        </div>
    </div>
</header>

<div class="content-wrapper">

    <!-- INICIO -->
    <div id="section-inicio" class="section-content active">
        <h1 data-var="01_titulo_inicio"></h1>
        <div class="content-box">
            <div class="article-content">
                <div class="newspaper-img">
                    <img src="{{ url_for('static', filename='foto1.png') }}" alt="Inicio" onerror="this.style.display='none'">
                    <div class="img-caption" data-var="01_cap_inicio"></div>
                </div>
                <p data-var="01_texto_inicio"></p>
            </div>
        </div>
    </div>

    <!-- INGRESO DE DATOS -->
    <div id="section-ingreso" class="section-content">
        <h1 data-var="01_titulo_ingreso"></h1>
        <div class="content-box">
            <div class="article-content">
                <div class="newspaper-img">
                    <img src="{{ url_for('static', filename='foto3.png') }}" alt="Ingreso" onerror="this.style.display='none'">
                    <div class="img-caption" data-var="01_cap_ingreso"></div>
                </div>
                <p data-var="01_texto_ingreso"></p>
            </div>
        </div>
    </div>

    <!-- EL ALTA -->
    <div id="section-alta" class="section-content">
        <h1 data-var="01_titulo_alta"></h1>
        <div class="content-box">
            <div class="article-content">
                <div class="newspaper-img">
                    <img src="{{ url_for('static', filename='foto2.png') }}" alt="Alta" onerror="this.style.display='none'">
                    <div class="img-caption" data-var="01_cap_alta"></div>
                </div>
                <p data-var="01_texto_alta"></p>
            </div>
        </div>
    </div>

    <!-- GUÍA DE COMANDOS -->
    <div id="section-comandos" class="section-content">
        <h1 data-var="01_titulo_comandos"></h1>
        <div class="content-box">
            <div class="article-content">
                <div class="newspaper-img">
                    <img src="{{ url_for('static', filename='foto4.png') }}" alt="Comandos" onerror="this.style.display='none'">
                    <div class="img-caption" data-var="01_cap_comandos"></div>
                </div>
                <p data-var="01_texto_comandos"></p>
            </div>
        </div>
    </div>

    <!-- PREGUNTAS FRECUENTES -->
    <div id="section-faq" class="section-content">
        <h1 data-var="01_titulo_faq"></h1>
        <div class="content-box">
            <p data-var="01_texto_faq"></p>
        </div>
    </div>

    {% if user_id %}
    <div id="section-calculadora" class="section-content">
        <div class="calculator-section">
            <h2 data-var="01_titulo_calc"></h2>
            <p data-var="01_desc_calc"></p>

            <div class="user-badge"><span data-var="01_user_conectado"></span>: {{ user_id }}</div>
            
            <div class="row">
                <div class="col" style="flex: 0.4;">
                    <label for="codigo"><span data-var="01_label_codigo"></span>:</label>
                    <input type="text" id="codigo" placeholder="Ej: PASCUALINAP" style="text-transform: uppercase;" oninput="this.value = this.value.toUpperCase()">
                </div>
                <div class="col">
                    <label for="descripcion"><span data-var="01_label_descripcion"></span>:</label>
                    <input type="text" id="descripcion" placeholder="Ej: Porción de pascualina de atún">
                </div>
            </div>

            <label for="recetaText"><span data-var="01_label_ingredientes"></span>:</label>
            <textarea id="recetaText" placeholder="Ej:&#10;1 kg de harina&#10;6 huevos&#10;200 g de manteca"></textarea>

            <div class="row">
                <div class="col">
                    <label for="tipoCalculo"><span data-var="01_label_criterio"></span>:</label>
                    <select id="tipoCalculo" onchange="toggleCriterio()">
                        <option value="porciones" data-var="01_opt_porciones"></option>
                        <option value="gramos" data-var="01_opt_gramos"></option>
                    </select>
                </div>
                <div class="col" id="colPorciones">
                    <label for="porciones"><span data-var="01_label_porciones"></span>:</label>
                    <input type="number" id="porciones" value="1" min="1">
                </div>
            </div>

            <button class="calc-btn" onclick="calcularReceta()"><span data-var="01_btn_calcular"></span></button>

            <div id="loading" data-var="01_loading_ia"></div>

            <div id="resultado-section">
                <h3 data-var="01_sub_fila_generada"></h3>
                <div style="overflow-x: auto;">
                    <table class="calc-tbl" id="tablaNutricional">
                        <thead>
                            <tr>
                                <th data-var="01_th_nombre"></th>
                                <th data-var="01_th_descripcion"></th>
                                <th data-var="01_th_peso"></th>
                                <th data-var="01_th_calorias"></th>
                                <th data-var="01_th_proteinas"></th>
                                <th data-var="01_th_grasas"></th>
                                <th data-var="01_th_carbohidratos"></th>
                                <th data-var="01_th_fibras"></th>
                            </tr>
                        </thead>
                        <tbody>
                        </tbody>
                    </table>
                </div>

                <button class="btn-save" onclick="guardarEnGoogleSheets()"><span data-var="01_btn_guardar"></span></button>
                <button class="btn-copy" onclick="copiarFilaExcel()"><span data-var="01_btn_copiar"></span></button>
            </div>
        </div>
    </div>
    {% endif %}

</div>

<footer>
    <div class="footer-links">
        <a onclick="reproducirAudioguia()" class="footer-link" data-var="01_btn_audioguia"></a>
        <a href="manual.pdf" target="_blank" class="footer-link" data-var="01_btn_manual"></a>
        <a href="https://instagram.com/ianutribot" target="_blank" class="footer-link" data-var="01_btn_instagram"></a>
        <a href="mailto:ianutribot@gmail.com" class="footer-link" data-var="01_btn_mail"></a>
    </div>
    <div class="footer-info" data-var="01_footer_rights"></div>
</footer>

<script>
    // Listado automático de imágenes de alta calidad de nutrición para PC (Fondo aleatorio)
    const fondosNutricion = [
        "https://images.unsplash.com/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=1920&q=80", // Ensalada fresca
        "https://images.unsplash.com/photo-1498837167922-ddd27525d352?auto=format&fit=crop&w=1920&q=80", // Verduras saludables
        "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=1920&q=80", // Bowl saludable
        "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=1920&q=80"  // Plato colorido fitness
    ];

    function aplicarFondoAleatorio() {
        if (window.innerWidth >= 1024) {
            const randomIndex = Math.floor(Math.random() * fondosNutricion.length);
            document.body.style.backgroundImage = `url('${fondosNutricion[randomIndex]}')`;
        }
    }

    let idiomaActual = 'en';

    async function cargarBanderasIdiomas() {
        try {
            const res = await fetch('/api/config-idiomas');
            const data = await res.json();
            const container = document.getElementById('langFlagsContainer');
            container.innerHTML = '';
            
            // data.idiomas debe traer objetos como: [{code: 'es', name: 'Español', flag: '🇪🇸'}, {code: 'en', name: 'English', flag: '🇺🇸'}]
            if (data.idiomas && Array.isArray(data.idiomas)) {
                data.idiomas.forEach(langObj => {
                    const btn = document.createElement('a');
                    btn.className = 'flag-btn';
                    btn.innerHTML = `${langObj.flag} ${langObj.name}`;
                    btn.onclick = () => cambiarIdioma(langObj.code);
                    container.appendChild(btn);
                });
            }
        } catch (e) {
            console.error("Error al cargar banderas de idiomas:", e);
        }
    }

    async function cambiarIdioma(lang) {
        try {
            idiomaActual = lang;
            const response = await fetch(`/api/traducciones?lang=${lang}`);
            if (!response.ok) throw new Error("No se pudieron cargar las traducciones.");
            const traducciones = await response.json();
            
            document.querySelectorAll('[data-var]').forEach(el => {
                const clave = el.getAttribute('data-var');
                if (traducciones[clave] !== undefined) {
                    el.innerText = traducciones[clave];
                }
            });
        } catch (err) {
            console.error("Error al cambiar idioma:", err);
        }
    }

    async function inicializarIdiomaWeb() {
        aplicarFondoAleatorio();
        await cargarBanderasIdiomas();

        const urlParams = new URLSearchParams(window.location.search);
        const userId = urlParams.get('user_id');

        if (userId) {
            try {
                const resUser = await fetch(`/api/usuario-idioma?user_id=${userId}`);
                const dataUser = await resUser.json();
                if (dataUser.lang) {
                    cambiarIdioma(dataUser.lang);
                    return;
                }
            } catch (e) {
                console.error("Error al obtener idioma de usuario:", e);
            }
        }

        await cambiarIdioma('en');
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
                // Obtenemos la audioguía dinámica correspondiente al idioma actual desde la API
                const response = await fetch(`/api/audioguia?lang=${idiomaActual}`);
                if (!response.ok) throw new Error("No se pudo cargar la audioguía para este idioma.");
                const data = await response.json();
                const textoGuia = data.guia;
                
                const langSpeech = idiomaActual === 'es' ? 'es-AR' : 'en-US';
                const utterance = new SpeechSynthesisUtterance(textoGuia);
                utterance.lang = langSpeech;
                utterance.rate = 1.0;
                window.speechSynthesis.speak(utterance);
            } catch (error) {
                alert("Error al reproducir la audioguía: " + error.message);
            }
        } else {
            alert("Tu navegador no soporta la función de lectura de voz.");
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

    const currentUserId = "{{ user_id }}";
    let ultimoResultadoCalculado = null;

    function toggleCriterio() {
        const tipo = document.getElementById('tipoCalculo').value;
        const colPorciones = document.getElementById('colPorciones');
        if (colPorciones) {
            colPorciones.style.display = (tipo === 'gramos') ? 'none' : 'block';
        }
    }

    async function calcularReceta() {
        if (!currentUserId) {
            alert("Acción no permitida para usuarios no registrados.");
            return;
        }

        const codigo = document.getElementById('codigo').value.trim();
        const descripcion = document.getElementById('descripcion').value.trim();
        const receta = document.getElementById('recetaText').value.trim();
        const tipoCalculo = document.getElementById('tipoCalculo').value;
        const porciones = document.getElementById('porciones').value;

        if (!codigo || !descripcion || !receta) {
            alert("Por favor completa el código, la descripción y los ingredientes.");
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
                    codigo, 
                    descripcion, 
                    receta, 
                    tipoCalculo, 
                    porciones: parseInt(porciones || 1) 
                })
            });

            const responseText = await response.text();

            if (responseText.trim().startsWith('<')) {
                console.error("Error del servidor (HTML):", responseText);
                alert("❌ El servidor falló (Código HTTP: " + response.status + "). Revisa los logs en el panel de Render.");
                return;
            }

            const data = JSON.parse(responseText);
            
            if (response.ok) {
                ultimoResultadoCalculado = data;
                const tbody = document.querySelector('#tablaNutricional tbody');
                tbody.innerHTML = `
                    <tr id="filaExcel">
                        <td>${data.nombre}</td>
                        <td>${data.descripcion}</td>
                        <td>${data.peso}</td>
                        <td>${data.calorias}</td>
                        <td>${data.proteinas}</td>
                        <td>${data.grasas}</td>
                        <td>${data.carbohidratos}</td>
                        <td>${data.fibras}</td>
                    </tr>
                `;
                document.getElementById('resultado-section').style.display = 'block';
            } else {
                alert("❌ Error al calcular: " + (data.error || "Intente nuevamente."));
            }
        } catch (err) {
            alert("❌ Error de procesamiento: " + err.message);
        } finally {
            document.getElementById('loading').style.display = 'none';
        }
    }

    async function guardarEnGoogleSheets() {
        if (!currentUserId) {
            alert("No hay ID de usuario asociado.");
            return;
        }
        if (!ultimoResultadoCalculado) {
            alert("Primero calculá la receta antes de guardar.");
            return;
        }

        try {
            const response = await fetch('/api/guardar-comida', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: currentUserId,
                    fila: ultimoResultadoCalculado
                })
            });

            const res = await response.json();
            if (response.ok) {
                if (res.codigo_guardado) {
                    ultimoResultadoCalculado.nombre = res.codigo_guardado;
                    const tdNombre = document.querySelector('#filaExcel td:first-child');
                    if (tdNombre) tdNombre.innerText = res.codigo_guardado;
                }
                alert("✅ ¡Éxito! " + res.message);
            } else {
                alert("❌ Error al guardar: " + (res.error || "Error desconocido."));
            }
        } catch (e) {
            alert("Error de conexión al intentar guardar.");
        }
    }

    function copiarFilaExcel() {
        const fila = document.getElementById('filaExcel');
        if (!fila) return;
        const celdas = Array.from(fila.querySelectorAll('td')).map(td => td.innerText);
        const textoCopiable = celdas.join('\\t');

        navigator.clipboard.writeText(textoCopiable).then(() => {
            alert("¡Fila copiada! Podés pegarla en tu Excel con Ctrl + V.");
        }).catch(err => {
            alert("Error al copiar al portapapeles.");
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
    """Endpoint que devuelve los idiomas disponibles con sus banderas para la barra superior."""
    try:
        # Aquí defines los idiomas que lee de tu base de datos o tabla multi
        idiomas_disponibles = [
            {"code": "es", "name": "Español", "flag": "🇪🇸"},
            {"code": "en", "name": "English", "flag": "🇺🇸"}
        ]
        return jsonify({"idiomas": idiomas_disponibles}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/audioguia', methods=['GET'])
def api_audioguia():
    """Endpoint para obtener la audioguía en formato texto según el idioma solicitado."""
    lang = request.args.get('lang', 'es')
    try:
        # Busca en la base de datos la variable 'guia' para el idioma correspondiente
        # (puedes adaptarlo a tu función obtener_traducciones_db o una específica para guías)
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
    lang = 'en'
    if user_id:
        try:
            lang = obtener_idioma_usuario(user_id)
        except Exception:
            pass
    return jsonify({"lang": lang}), 200

# =====================================================================================================================================
#              FINAL                                  PAGINA WEB (CALCULADORA UNICA)                        FINAL
# ======================================================================================================================================

# =============================================================================================================================================
#              INICIO                                   FUNCIONES SUPABASE                           INICIO
# =============================================================================================================================================

#                 INICIO                                     1  GOOGLE SHEETS                       INICIO
# =============================================================================================================================================
                
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

def _asegurar_tabla_y_conectar_migrar(tabla_nombre, df_muestra=None):
    """Función auxiliar para migración que recrea la tabla limpia."""
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
    """
    Crea o asegura la tabla en Supabase. Realiza una búsqueda insensible a mayúsculas/minúsculas 
    para reutilizar la tabla existente (sea minúscula o mayúscula) y evitar duplicados.
    """
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
                    "Peso_ideal" DOUBLE PRECISION,
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
                    "Altura" DOUBLE PRECISION,
                    "muneca" DOUBLE PRECISION,
                    "ocupacion" DOUBLE PRECISION,
                    "cumple" TEXT,
                    "profesional" TEXT
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

    return conn, cur


#              INICIO                     4 FUNCIONES BIOMETRIA Y FUNCIONES PRESION                       INICIO
# =============================================================================================================================================

def calcular_rango_actividad_fisica(peso_actual: float, peso_referencia: float) -> tuple[int, int]:
    """
    Calcula el rango recomendado de minutos de actividad física diaria (mínimo y máximo)
    según la lógica proporcional de sobrepeso (tope de 60 min con >=20% de exceso, sube hasta 90 min en el ideal).
    """
    min_minutos = 30  # Mínimo universal saludable
    
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

def aplicar_calibracion_reloj(factor_previo: float, get_reloj: float, tmb: float, max_variacion_pct: float = 0.10) -> float:
    """
    Calibra el factor de actividad usando el GET medido por un reloj inteligente,
    aplicando topes de seguridad relativos (porcentaje máximo de cambio) y absolutos.
    """
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
        
        cur.close()
        conn.close()
        
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

def obtener_perfil_usuario(user_id, mes_target=None):
    try:
        tabla_nombre = f"Perfil_{user_id}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="perfil")
        
        query = f"""
            SELECT "EDAD", "PESO", "ALTURA", "GENERO", "ocupacion", "MES", "Fecha_Actualizacion"
            FROM "{tabla_nombre}"
            ORDER BY id ASC
        """
        cur.execute(query)
        filas = cur.fetchall()
        
        if not filas:
            cur.close()
            conn.close()
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
                'Fecha_Actualizacion': fila[6]
            })
            
        cur.close()
        conn.close()
        
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
        
        perfil = {}
        peso_hallado = None

        for k, v in perfil_raw.items():
            k_upper = str(k).strip().upper()
            if k_upper == 'EDAD':
                val = float(v or 0)
                perfil['Edad'] = val
                perfil['edad'] = val
            elif k_upper == 'PESO':
                val = float(v or 0)
                peso_hallado = val if val > 0 else None
                perfil['Peso'] = val
                perfil['peso'] = val
                perfil['peso_actual'] = val
            elif k_upper == 'ALTURA':
                val = float(v or 0)
                perfil['Altura'] = val
                perfil['altura'] = val
            elif k_upper in ['PESO_IDEAL', 'PESO IDEAL']:
                val = float(v or 0)
                perfil['Peso_ideal'] = val
                perfil['peso_ideal'] = val
            elif k_upper in ['GENERO', 'SEXO']:
                perfil['Sexo'] = str(v).strip()
                perfil['genero'] = str(v).strip()
            elif k_upper == 'OCUPACION':
                val = float(v or 0)
                factor_final = val if val > 0 else 1.375
                perfil['Ocupacion'] = factor_final
                perfil['ocupacion'] = factor_final
                perfil['factor_actividad'] = factor_final
            elif k_upper == 'MES':
                perfil['Mes'] = str(v).strip()
                perfil['mes'] = str(v).strip()

        perfil['peso_pendiente'] = (peso_hallado is None or peso_hallado <= 0)
        return perfil
    except Exception as e:
        print(f"Error obteniendo perfil de Supabase para el usuario {user_id}: {e}")
        return None

def obtener_datos_presion_db(user_id):
    try:
        tabla_nombre = f"Presion_{user_id}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="presion")
        
        query = f"""
            SELECT "Fecha_Hora", "Fecha_Dia", "Alta", "Baja", "Pulsaciones", "Nota"
            FROM "{tabla_nombre}"
        """
        df = pd.read_sql(query, conn)
        
        cur.close()
        conn.close()
        
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
    conn = None
    cur = None
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
        
        try:
            conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="perfil")
            query_perfil = f'SELECT "MES", "PESO" FROM "{tabla_nombre}" ORDER BY id ASC'
            cur.execute(query_perfil)
            filas_perfil = cur.fetchall()
            
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
            
            # Cerramos el cursor de la consulta de pesos para abrir uno limpio o reutilizarlo en el update
            cur.close()
            conn.close()
        except Exception as e_delta:
            logger.error(f"Error calculando delta de peso dinámico en Supabase para User {user_id}: {e_delta}")
            delta_peso = 0.0
            if cur:
                try: cur.close()
                except: pass
            if conn:
                try: conn.close()
                except: pass

        gasto_diario_total = ingesta_diaria - ((delta_peso * 7700.0) / dias_registrados)
        factor_limpio = (gasto_diario_total - ejercicio_diario) / tmb_pura
        
        factor_limpio = max(1.20, min(1.85, factor_limpio))
        ocupacion_db = float(round(factor_limpio, 3))

        # Abrimos nueva conexión y cursor seguros para realizar el UPDATE
        try:
            conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="perfil")
            update_query = f"""
                UPDATE "{tabla_nombre}"
                SET "ocupacion" = %s
                WHERE "MES" = %s
            """
            cur.execute(update_query, (ocupacion_db, str(mes_anterior_str)))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as db_err:
            logger.error(f"No se pudo escribir el factor en la base de datos Supabase: {db_err}")
            if cur:
                try: cur.close()
                except: pass
            if conn:
                try: conn.close()
                except: pass

        return factor_limpio

    except Exception as e:
        logger.error(f"Error al calcular factor limpio del mes anterior en Supabase para User {user_id}: {e}")
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass
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
                if val is None:
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
            try:
                cur.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass
                                
def obtener_codigo_unico(tabla_nombre, codigo_base):
    try:
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comidas_precargadas")
        query = f'SELECT "Nombre" FROM "{tabla_nombre}"'
        cur.execute(query)
        filas = cur.fetchall()
        cur.close()
        conn.close()

        codigos_existentes = set(str(fila[0]).strip().upper() for fila in filas if fila[0] is not None)
    except Exception as e:
        logger.error(f"Error al obtener códigos existentes de Supabase para {tabla_nombre}: {e}")
        codigos_existentes = set()

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
    try:
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comidas_precargadas")
        
        query = f'DELETE FROM "{tabla_nombre}" WHERE UPPER(TRIM("Nombre")) = %s'
        cur.execute(query, (nombre_a_borrar.strip().upper(),))
        
        filas_afectadas = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        
        return filas_afectadas > 0
    except Exception as e:
        print(f"Error al eliminar comida precargada en Supabase para {user_id}: {e}")
        return False 

#                    INICIO                  6 FUNCIONES LECTURA PROFESIONALES                      INICIO
# =======================================================================================================================================

async def _verificar_y_obtener_profesional(update: Update):
    prof_id = str(update.effective_user.id).strip()
    try:
        conn, cur = _asegurar_tabla_y_conectar("Profesionales", tipo_tabla="profesionales")
        query = """
            SELECT "User ID"
            FROM "Profesionales"
        """
        cur.execute(query)
        filas = cur.fetchall()
        cur.close()
        conn.close()

        for fila in filas:
            id_p = str(fila[0] or "").split('.')[0].strip()
            if id_p == prof_id:
                return prof_id
    except Exception as e:
        logger.error(f"Error en _verificar_y_obtener_profesional: {e}")
    return None
    
def obtener_especialidad_profesional(prof_id):
    try:
        conn, cur = _asegurar_tabla_y_conectar("Profesionales", tipo_tabla="profesionales")
        query = """
            SELECT "User ID", "Especialidad"
            FROM "Profesionales"
        """
        cur.execute(query)
        filas = cur.fetchall()
        cur.close()
        conn.close()

        for fila in filas:
            id_p = str(fila[0] or "").split('.')[0].strip()
            if id_p == str(prof_id).strip():
                return str(fila[1] or "General").strip()
    except Exception as e:
        logger.error(f"Error en obtener_especialidad_profesional para {prof_id}: {e}")
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

def obtener_todos_usuarios() -> list:
    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        query = """
            SELECT "User ID", "Nombre", "Estado", "Ultimo Mes Peso", "Notificaciones", 
                   "Fecha Alta", "Sexo", "Altura", "muneca", "ocupacion", "cumple", "profesional"
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
                "Altura": fila[7],
                "muneca": fila[8],
                "ocupacion": fila[9],
                "cumple": fila[10],
                "profesional": fila[11]
            })
        return records
    except Exception as e:
        logger.error(f"Error al obtener usuarios de Supabase: {e}")
        return []

def obtener_registros_usuario(user_id: str) -> list:
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
        cur.close()
        conn.close()

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

def actualizar_estado_usuario(user_id: str, nuevo_estado: str):
    """Actualiza el estado de un usuario exclusivamente en Supabase (Bloque duplicado corregido)."""
    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        cur.execute("""
            UPDATE "Usuarios"
            SET "Estado" = %s
            WHERE "User ID" = %s
        """, (str(nuevo_estado), str(user_id)))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error al actualizar estado en Supabase para {user_id}: {e}")

def eliminar_registro_por_id(user_id, item_id):
    """Borra el registro exclusivamente de la tabla en Supabase."""
    try:
        tabla_nombre = f"User_{user_id}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comida")
        cur.execute(f'DELETE FROM "{tabla_nombre}" WHERE id = %s', (int(item_id),))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error al eliminar registro en Supabase para el usuario {user_id}: {e}")
        return False
    return True

def obtener_datos_usuario_general(user_id):
    """Obtiene los datos generales del usuario desde la tabla 'Usuarios'."""
    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        query = """
            SELECT "User ID", "ocupacion", "reloj_actualizado_mes"
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
                    "ocupacion": fila[1],
                    "reloj_actualizado_mes": fila[2]
                }
        return {}
    except Exception as e:
        logger.error(f"Error al obtener datos generales de usuario para {user_id}: {e}")
        return {}
        

#              INICIO                                  8 FUNCIONES GUARDAR                        INICIO
# =============================================================================================================================================

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
                float(item.get("peso", item.get("Peso (g)", 0))), 
                float(item.get("calorias", item.get("Calorías (kcal)", 0))), 
                float(item.get("proteinas", item.get("Proteínas (g)", 0))), 
                float(item.get("grasas", item.get("Grasas (g)", 0))), 
                float(item.get("carbohidratos", item.get("hidratos", item.get("Hidratos (g)", 0)))), 
                float(item.get("fibras", item.get("Fibras (g)", 0)))
            )
            cur.execute(query, valores)
            
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"🚨 ERROR REAL EN SUPABASE: {e}")
        logger.error(f"Error interno al duplicar ingesta en Supabase (User_{user_id}): {e}")
                
def guardar_comida_precargada_db(user_id, fila):
    """Guarda las comidas precargadas exclusivamente en Supabase."""
    codigo_original = fila.get('Nombre', fila.get('nombre', ''))
    
    tabla_nombre = f"Comidas_{user_id}"
    try:
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="comidas_precargadas")
        cur.execute(f'SELECT "Nombre" FROM "{tabla_nombre}"')
        filas = cur.fetchall()
        codigos_existentes = set(str(f[0]).strip().upper() for f in filas if f[0] is not None)
    except Exception:
        codigos_existentes = set()

    codigo_limpio = str(codigo_original).strip().upper()
    codigo_unico = codigo_limpio
    i = 1
    while codigo_unico in codigos_existentes:
        i += 1
        codigo_unico = f"{codigo_limpio}{i}"

    try:
        p_val = float(fila.get('Peso', fila.get('peso', 0)))
        c_val = float(fila.get('Calorias', fila.get('calorias', 0)))
        pr_val = float(fila.get('Proteinas', fila.get('proteinas', 0)))
        g_val = float(fila.get('Grasas', fila.get('grasas', 0)))
        h_val = float(fila.get('Carbohidratos', fila.get('carbohidratos', fila.get('Hidratos', 0))))
        f_val = float(fila.get('Fibras', fila.get('fibras', 0)))

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
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error al grabar Comida Precargada en Supabase (Comidas_{user_id}): {e}")
    
    return codigo_unico

def guardar_presion_db(user_id, alta, baja, pulsaciones=None, nota=""):
    """Guarda los registros de presión arterial exclusivamente en Supabase."""
    ahora = obtener_ahora_arg()

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
            float(alta), 
            float(baja), 
            float(pulsaciones) if pulsaciones is not None else 0.0, 
            str(nota).strip()
        )
        cur.execute(query, valores)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error al grabar Presión en Supabase (Presion_{user_id}): {e}")

def guardar_perfil_db(user_id, peso, mes=None, edad=None, altura=None, genero=None, ocupacion=None, *args, **kwargs):
    """Guarda y actualiza los datos del perfil y peso del usuario exclusivamente en Supabase."""
    ahora = obtener_ahora_arg()
    
    if not mes:
        mes = ahora.strftime("%Y-%m")

    try:
        tabla_nombre = f"Perfil_{user_id}"
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="perfil")
        
        cur.execute(f'SELECT id FROM "{tabla_nombre}" WHERE "MES" = %s', (str(mes),))
        fila_supa = cur.fetchone()
        
        peso_real = float(peso)
        if peso_real > 1000: peso_real /= 1000.0
        
        if fila_supa:
            cur.execute(f"""
                UPDATE "{tabla_nombre}"
                SET "PESO" = %s, "Fecha_Actualizacion" = %s
                WHERE "MES" = %s
            """, (peso_real, ahora.strftime("%Y-%m-%d"), str(mes)))
        else:
            cur.execute(f"""
                INSERT INTO "{tabla_nombre}" ("EDAD", "PESO", "ALTURA", "GENERO", "ocupacion", "MES", "Fecha_Actualizacion", "Peso_ideal", "Cumple")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(edad) if edad is not None else "64",
                peso_real,
                float(altura) if altura is not None else 1.72,
                str(genero) if genero else "M",
                float(ocupacion) if ocupacion is not None else 1.375,
                str(mes),
                ahora.strftime("%Y-%m-%d"),
                0.0,
                ""
            ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error al guardar perfil en Supabase (Perfil_{user_id}): {e}")

def guardar_ocupacion_db(user_id, nuevo_factor, mes_actual, reloj_actualizado=None):
    """Actualiza el factor de ocupación en la tabla Perfil_<user_id> y el control en Usuarios."""
    user_id_str = str(user_id).strip()
    mes_marca = str(reloj_actualizado) if reloj_actualizado else str(mes_actual)

    # 1. Actualizar en la tabla maestra 'Usuarios' (para el control de límite mensual del reloj)
    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        query_u = """
            UPDATE "Usuarios"
            SET "ocupacion" = %s, "reloj_actualizado_mes" = %s
            WHERE "User ID" = %s
        """
        cur.execute(query_u, (float(nuevo_factor), mes_marca, user_id_str))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error al actualizar la tabla Usuarios en Supabase para {user_id}: {e}")

    # 2. Actualizar en la tabla 'Perfil_<user_id>' (que es de donde el comando /perfil y las métricas leen la ocupación del mes)
    try:
        tabla_perfil = f"Perfil_{user_id}"
        conn_p, cur_p = _asegurar_tabla_y_conectar(tabla_perfil, tipo_tabla="perfil")
        
        # Intentar actualizar el registro del mes actual
        query_p = f"""
            UPDATE "{tabla_perfil}"
            SET "ocupacion" = %s
            WHERE "MES" = %s
        """
        cur_p.execute(query_p, (float(nuevo_factor), str(mes_actual)))
        
        # Si por alguna razón no existía una fila para este mes en la tabla de perfil, la insertamos
        if cur_p.rowcount == 0:
            cur_p.execute(f'SELECT id FROM "{tabla_perfil}" WHERE "MES" = %s', (str(mes_actual),))
            if not cur_p.fetchone():
                cur_p.execute(f"""
                    INSERT INTO "{tabla_perfil}" ("EDAD", "PESO", "ALTURA", "GENERO", "ocupacion", "MES", "Fecha_Actualizacion", "Peso_ideal", "Cumple")
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, ("64", 0.0, 167.0, "M", float(nuevo_factor), str(mes_actual), obtener_ahora_arg().strftime("%Y-%m-%d"), 0.0, ""))
            else:
                cur_p.execute(query_p, (float(nuevo_factor), str(mes_actual)))
                
        conn_p.commit()
        cur_p.close()
        conn_p.close()
    except Exception as e:
        logger.error(f"Error al actualizar la tabla Perfil_{user_id} en Supabase: {e}")

#              INICIO                       9  FUNCIONES MIGRAR FUNCIONES DESCARGAR                           INICIO
# =============================================================================================================================================

async def cmd_importar_tabla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando para importar/actualizar una tabla específica desde un archivo Excel en el servidor.
    Uso: /importar nombre_de_la_tabla
    El archivo Excel debe llamarse igual que la tabla (ej. multi.xlsx) o estar especificado.
    """
    user_id = update.effective_user.id
    
    if not context.args or len(context.args) == 0:
        await update.message.reply_text(
            "⚠️ Por favor, indica el nombre de la tabla a importar.\n"
            "Ejemplo: `/importar multi`",
            parse_mode="Markdown"
        )
        return

    nombre_tabla = context.args[0].strip()
    excel_path = f"{nombre_tabla}.xlsx"

    if not os.path.exists(excel_path):
        await update.message.reply_text(f"❌ No se encontró el archivo `{excel_path}` en el servidor de Render.", parse_mode="Markdown")
        return

    try:
        await update.message.reply_text(f"🔄 Leyendo `{excel_path}` y actualizando la tabla `{nombre_tabla}` en Supabase...", parse_mode="Markdown")
        
        df = pd.read_excel(excel_path)
        if df.empty:
            await update.message.reply_text(f"⚠️ El archivo `{excel_path}` está vacío.", parse_mode="Markdown")
            return

        # Limpiar nombres de columnas
        df.columns = [str(c).strip() for c in df.columns]

        # Conectar y recrear/actualizar la tabla limpia
        conn, cur = _asegurar_tabla_y_conectar_migrar(nombre_tabla, df_muestra=df)

        columnas = list(df.columns)
        cols_sql = ', '.join([f'"{c}"' for c in columnas])
        placeholders = ', '.join(['%s'] * len(columnas))
        
        query_insert = f"""
            INSERT INTO "{nombre_tabla}" ({cols_sql})
            VALUES ({placeholders})
        """

        filas_insertadas = 0
        for _, row in df.iterrows():
            valores = []
            for col in columnas:
                val = row[col]
                if pd.isna(val):
                    val = None
                else:
                    val = str(val).strip() # Asegurar que los textos se guarden limpios
                valores.append(val)

            cur.execute(query_insert, tuple(valores))
            filas_insertadas += 1

        conn.commit()
        cur.close()
        conn.close()

        await update.message.reply_text(f"✅ ¡Éxito! La tabla `{nombre_tabla}` fue actualizada con {filas_insertadas} registros.", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error al importar la tabla {nombre_tabla}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error al importar la tabla: `{e}`", parse_mode="Markdown")
        
async def cmd_migrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando temporal para migrar el archivo Excel local (Registro_Nutricional_Bot.xlsx) 
    hacia Supabase limpiando las fechas a formato YYYY-MM-DD y escalando las métricas numéricas.
    """
    try:
        await update.message.reply_text("🔄 Reiniciando tablas, limpiando fechas y migrando el Excel a Supabase...", parse_mode="Markdown")
        
        excel_path = 'Registro_Nutricional_Bot.xlsx'
        if not os.path.exists(excel_path):
            await update.message.reply_text(f"❌ No se encontró el archivo `{excel_path}` en el directorio del bot.", parse_mode="Markdown")
            return

        xls = pd.ExcelFile(excel_path)
        reporte = []

        columnas_a_escalar = {
            "Peso (g)", "Peso", "PESO", "Peso_ideal",
            "Calorías (kcal)", "Calorias",
            "Proteínas (g)", "Proteinas",
            "Grasas (g)", "Grasas",
            "Hidratos (g)", "Carbohidratos",
            "Fibras (g)", "Fibras",
            "EDAD", "ALTURA", "ocupacion", "muneca",
            "Alta", "Baja", "Pulsaciones"
        }

        for nombre_hoja in xls.sheet_names:
            nombre_tabla = nombre_hoja.strip()
            df = pd.read_excel(xls, sheet_name=nombre_hoja)
            
            if df.empty:
                reporte.append(f"⚠️ Hoja *{nombre_hoja}*: Omitida (vacía).")
                continue

            df.columns = [str(c).strip() for c in df.columns]

            try:
                conn, cur = _asegurar_tabla_y_conectar_migrar(nombre_tabla, df_muestra=df)
            except Exception as e:
                reporte.append(f"❌ Tabla *{nombre_tabla}*: Error al recrear tabla ({e}).")
                continue

            filas_insertadas = 0
            try:
                columnas = list(df.columns)
                cols_sql = ', '.join([f'"{c}"' for c in columnas])
                placeholders = ', '.join(['%s'] * len(columnas))
                
                query_insert = f"""
                    INSERT INTO "{nombre_tabla}" ({cols_sql})
                    VALUES ({placeholders})
                """

                for _, row in df.iterrows():
                    valores = []
                    for col in columnas:
                        val = row[col]
                        if pd.isna(val):
                            val = None
                        elif isinstance(val, (pd.Timestamp, datetime, date)):
                            val = pd.to_datetime(val).strftime("%Y-%m-%d")
                        elif isinstance(val, str) and ("/" in val or "-" in val) and len(val) >= 10:
                            try:
                                dt_parsed = pd.to_datetime(val)
                                if not pd.isna(dt_parsed):
                                    val = dt_parsed.strftime("%Y-%m-%d")
                            except Exception:
                                pass
                        elif isinstance(val, (int, float)) and col in columnas_a_escalar:
                            val = val / 1000.0
                        valores.append(val)

                    cur.execute(query_insert, tuple(valores))
                    filas_insertadas += 1

                conn.commit()
                reporte.append(f"✅ Tabla *{nombre_tabla}*: {filas_insertadas} registros migrados con fechas limpias.")

            except Exception as inner_e:
                conn.rollback()
                reporte.append(f"❌ Tabla *{nombre_tabla}*: Error en inserción ({inner_e}).")
            finally:
                cur.close()
                conn.close()

        mensaje_final = "📊 **Resultado de la Migración:**\n\n" + "\n".join(reporte)
        await update.message.reply_text(mensaje_final, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error crítico en migración local: {e}", exc_info=True)
        await update.message.reply_text(f"⚠️ Error general en la migración: {e}")
        
async def cmd_descargar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando genérico para descargar cualquier tabla de Supabase en formato Excel.
    Uso: /descargar nombre_de_la_tabla
    """
    user_id = update.effective_user.id
    
    # Verificar si el usuario proporcionó el nombre de la tabla
    if not context.args or len(context.args) == 0:
        await update.message.reply_text(
            "⚠️ Por favor, indica el nombre de la tabla que deseas descargar.\n"
            "Ejemplo: `/descargar textos_bot` o `/descargar Usuarios`",
            parse_mode="Markdown"
        )
        return

    nombre_tabla = context.args[0].strip()
    mensaje_espera = await update.message.reply_text(f"⏳ Consultando y preparando la tabla `{nombre_tabla}`...", parse_mode="Markdown")

    try:
        # Usamos tu función existente para conectar de forma segura
        conn, cur = _asegurar_tabla_y_conectar(nombre_tabla, tipo_tabla="comida") # tipo_tabla genérico para evitar fallos de creación si ya existe
        
        # Consultar todas las columnas y filas de la tabla solicitada
        query = f'SELECT * FROM "{nombre_tabla}"'
        df = pd.read_sql(query, conn)
        
        cur.close()
        conn.close()

        if df.empty:
            await mensaje_espera.edit_text(f"⚠️ La tabla `{nombre_tabla}` existe pero está vacía.", parse_mode="Markdown")
            return

        # Generar el archivo Excel en un buffer de memoria (BytesIO)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=nombre_tabla[:31]) # Excel limita los nombres de pestaña a 31 chars
        buffer.seek(0)

        # Enviar el archivo por Telegram
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
            f"❌ No se pudo descargar la tabla `{nombre_tabla}`.\n"
            f"Error: `{e}`\n\n"
            "Verifica que el nombre de la tabla esté bien escrito (es sensible a mayúsculas/minúsculas).",
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

def calcular_peso_ideal(sexo: str, altura_cm: float) -> float:
    if str(sexo).upper() in ['M', 'MASCULINO']:
        return (altura_cm - 100) - ((altura_cm - 150) / 4.0)
    else:
        return (altura_cm - 100) - ((altura_cm - 150) / 2.5)

def calcular_grasa_y_magra(sexo: str, altura_cm: float, cintura_cm: float, cuello_cm: float, peso_actual: float) -> tuple[float, float]:
    gen_clean = str(sexo).strip().lower()
    is_femenino = gen_clean in ["femenino", "f", "mujer", "female"]
    
    try:
        if is_femenino:
            gc = 495 / (1.29579 - 0.35004 * math.log10(max(1.0, cintura_cm - cuello_cm)) + 0.22100 * math.log10(max(1.0, altura_cm))) - 450
        else:
            gc = 495 / (1.03324 - 0.19077 * math.log10(max(1.0, cintura_cm - cuello_cm)) + 0.15456 * math.log10(max(1.0, altura_cm))) - 450
            
        gc = max(5.0, min(60.0, gc))
    except Exception:
        gc = 25.0

    masa_grasa = peso_actual * (gc / 100.0)
    masa_magra = peso_actual - masa_grasa
    
    return round(gc, 1), round(masa_magra, 1)

def calcular_peso_etapa(peso_actual: float, peso_ideal: float, ritmo_preferido: str = "moderado") -> float:
    if peso_actual <= peso_ideal:
        return round(peso_actual, 1)
    
    ritmo_clean = str(ritmo_preferido).strip().lower()
    if "tranquilo" in ritmo_clean or "lento" in ritmo_clean:
        factor_actual = 0.90
    elif "rapido" in ritmo_clean or "intenso" in ritmo_clean or "decidido" in ritmo_clean:
        factor_actual = 0.75
    else:
        factor_actual = 0.85
        
    factor_ideal = 1.0 - factor_actual
    peso_etapa = (peso_actual * factor_actual) + (peso_ideal * factor_ideal)
    return round(peso_etapa, 1)

def calcular_tmb_y_get(peso_actual: float, altura_cm: float, edad: int, genero: str = "masculino", actividad: float = 1.375, masa_magra: float = None, peso_ideal: float = None) -> tuple[float, float]:
    try:
        peso = float(peso_actual)
        altura = float(altura_cm)
        anios = int(edad)
    except (TypeError, ValueError):
        peso, altura, anios = 90.0, 170.0, 40

    if masa_magra is not None and masa_magra > 0:
        tmb = 370 + (21.6 * masa_magra)
    else:
        gen_clean = str(genero).strip().lower()
        if gen_clean in ["femenino", "f", "mujer", "female"]:
            tmb = (10.0 * peso) + (6.25 * altura) - (5.0 * anios) - 161.0
        else:
            tmb = (10.0 * peso) + (6.25 * altura) - (5.0 * anios) + 5.0

    get = tmb * float(actividad)
    return round(tmb, 2), round(get, 2)


async def _validar_peso_mes_actual(update: Update = None, context: ContextTypes.DEFAULT_TYPE = None, user_id: int = None) -> bool:
    uid = user_id or (update.effective_user.id if update else None)
    if not uid:
        return False

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
            ahora = obtener_ahora_arg() if 'obtener_ahora_arg' in globals() else datetime.now()
            
            formatos = [
                "%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y",
                "%Y-%m", "%m/%Y", "%Y-%m-%d",
                "%d/%m/%Y", "%Y-%m-%d"
            ]

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
                mes_str_iso = ahora.strftime("%Y-%m")
                mes_str_lat = ahora.strftime("%m/%Y")
                if mes_str_iso in fecha_str or mes_str_lat in fecha_str:
                    peso_valido = True
                    
    return peso_valido

    
#              INICIO                     FUNCIONES SOPORTE MULTILENGUAJE                   INICIO
# =============================================================================================================================================

def obtener_idioma_usuario(user_id):
    """Obtiene el idioma configurado para un usuario de Telegram desde Supabase[cite: 2]."""
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
    """Consulta la tabla 'multi' en Supabase y devuelve un diccionario con las traducciones[cite: 2]."""
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
    """Decorador limpio con avisos estándar adaptados en inglés[cite: 2]."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = str(update.effective_user.id).strip()
        encontrado = False
        esta_activo = True

        mensaje_no_registrado = (
            "⚠️ **You are not registered yet!**\n\n"
            "To use this command and access your nutrition plan, you need to sign up first.\n\n"
            "👉 Use the `/alta` or `/signup` command to create your profile in a couple of steps."
        )
        mensaje_deshabilitado = "❌ **Your account has been disabled due to inactivity or system removal. Please contact the bot administrator.**"

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
                    if estado_val in ['baja', 'suspendido', '3']:
                        esta_activo = False
                    break
        except Exception as e:
            logger.error(f"Error al verificar registro: {e}")

        if not encontrado:
            if update.message:
                await update.message.reply_text(mensaje_no_registrado, parse_mode="Markdown")
            elif update.callback_query:
                await update.callback_query.answer("⚠️ Registration required", show_alert=True)
                await update.callback_query.message.reply_text(mensaje_no_registrado, parse_mode="Markdown")
            return

        if not esta_activo:
            if update.message:
                await update.message.reply_text(mensaje_deshabilitado, parse_mode="Markdown")
            elif update.callback_query:
                await update.callback_query.answer("⚠️ Account disabled", show_alert=True)
                await update.callback_query.message.reply_text(mensaje_deshabilitado, parse_mode="Markdown")
            return

        return await func(update, context, *args, **kwargs)
    return wrapper

# =============================================================================================================================================
#              FINAL                          FUNCIONES AUXILIARES INTERNAS                  FINAL
# =============================================================================================================================================

# ======================================================================================================================================       
#                INICIO                       14 FUNCIONES IA GROQ                                      INICIO
# ======================================================================================================================================

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

        modelo = modelo_override or globals().get('GROQ_TEXTO', "llama-3.3-70b-versatile")
        
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
    """Obtiene el nombre completo del lenguaje para la IA desde la tabla Usuarios[cite: 4]."""
    if not user_id:
        return "Spanish"
    try:
        from FuncionesSupabaseMulti import _asegurar_tabla_y_conectar
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        cur.execute('SELECT "lenguajes" FROM "Usuarios" WHERE "User ID" = %s', (str(user_id),))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row[0]:
            return str(row[0]).strip()
    except Exception as e:
        logger.error(f"Error obteniendo lenguaje IA para {user_id}: {e}")
    return "Spanish"

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
        '  "parametro": "texto extraído de fecha/mes o vacío"\n'
        "}"
    )

    response = client_ai.chat.completions.create(
        model=globals().get('GROQ_TEXTO', "llama-3.3-70b-versatile"),
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
        
    # Mensaje de fallback mediante variable multilenguaje 02_
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    return traducciones.get("02_error_analisis_no_disponible", "⚠️ Nutritional analysis temporarily unavailable.")
    
async def generar_recomendacion_mensual_para_pdf(user_id: int, mes_str: str, df_mes, perfil: dict, m: dict, context=None) -> str:
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    msg_error_inf = traducciones.get("02_error_informe_ia", "<b>⚠️ Could not generate the audited AI report.</b>")
    msg_error_comp = traducciones.get("02_error_compilar_ia", "<b>⚠️ Error compiling the AI recommendation for the report.</b>")

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
    nombre = datos_usuario.get('nombre', 'Paciente')
    edad = datos_usuario.get('edad', 0)
    sexo = datos_usuario.get('sexo', 'M')
    altura = datos_usuario.get('altura', 0)
    peso = datos_usuario.get('peso', 0)
    peso_ideal = datos_usuario.get('peso_ideal', 0)
    peso_etapa = datos_usuario.get('peso_etapa', peso)
    get_calorias = datos_usuario.get('get', 2000)
    
    # 🟢 Capturamos el ritmo elegido por el usuario (tranquilo, moderado, intenso)
    ritmo_elegido = datos_usuario.get('ritmo', 'moderado')

    nombre_lenguaje = obtener_nombre_lenguaje_ia(user_id)
    dif_pct = ((peso - peso_ideal) / peso_ideal * 100) if peso_ideal > 0 else 0.0

    if dif_pct > 20:
        contexto_situacion = "El paciente presenta un sobrepeso considerable, por lo que el enfoque debe ser muy gradual, paciente y centrado en la adopción de hábitos sostenibles a largo plazo sin restricciones drásticas."
    elif dif_pct >= 8:
        contexto_situacion = "El paciente presenta un sobrepeso moderado (en torno al 10% por encima de su referencia de bienestar), ideal para estructurar un cambio de hábitos enfocado en porciones y constancia."
    elif dif_pct >= -5:
        contexto_situacion = "El paciente se encuentra en un rango de peso cercano a su meta o en zona de equilibrio, por lo que el foco estará en la optimización de la calidad nutricional y el mantenimiento."
    else:
        contexto_situacion = "El paciente presenta un peso corporal por debajo de su referencia teórica, por lo que el enfoque será de nutrición equilibrada y fortalecimiento saludable."

    prompt_ia = (
        f"Actúa como un médico nutricionista experto y muy empático. Contexto del paciente:\n"
        f"- Situación general: {contexto_situacion}\n"
        f"- Ritmo de trabajo seleccionado por el paciente: {ritmo_elegido.capitalize()}\n\n"
        f"Redacta un informe breve, cálido y motivador de bienvenida que incluya:\n"
        f"1. Una explicación empática y motivadora sobre por qué avanzamos paso a paso hacia nuestra primera meta intermedia, destacando que lo importante es el proceso y la salud sostenible, valorando específicamente la decisión del paciente de elegir un ritmo {ritmo_elegido}.\n"
        f"2. Recomendaciones generales y amables sobre el manejo de la alimentación diaria orientada a un equilibrio energético saludable, SIN MENCIONAR NÚMEROS, NI KILOS, NI GRAMOS, NI CALORÍAS en el texto de los consejos.\n"
        f"3. Pautas generales de actividad física complementaria (caminatas suaves, movilidad) y hábitos de hidratación acordes al ritmo elegido.\n"
        f"REQUISITO ESTRICTO: Mantén un tono sumamente humano, profesional, constructivo y generalizado. No des cifras de peso ni metas numéricas específicas en las recomendaciones.\n"
        f"IMPORTANTE: Redacta todo el informe estrictamente en el idioma {nombre_lenguaje}.\n"
        f"Cierra con un punto final y completa todas las ideas."
    )
    
    system_msg = "Eres un nutricionista clínico profesional, empático y motivador."
    prompt_auditor_base = (
        f"Actúa como un médico supervisor estricto y auditor de calidad. "
        f"Revisa el siguiente informe nutricional de bienvenida:\n\n"
        f"--- INFORME A EVALUAR ---\n{{informe_candidato}}\n-------------------------\n\n"
        f"Criterios de rechazo:\n"
        f"1. Si incluye números, kilos o calorías dentro de las recomendaciones del texto.\n"
        f"2. Si hay oraciones cortadas o truncadas al final.\n"
        f"Si el informe cumple perfectamente con todo, responde únicamente con la palabra 'OK'."
    )

    informe_ia = ""
    max_intentos = 3

    async def _llamar_ia_con_retry(p, tokens, temp, sys_p=None, mod_over=None, intentos_max=3):
        for it in range(1, intentos_max + 1):
            try:
                res = await asyncio.to_thread(
                    ejecutar_consulta_ia, 
                    prompt=p, 
                    max_tokens=tokens, 
                    temperature=temp, 
                    system_prompt=sys_p, 
                    modelo_override=mod_over
                )
                if res and res.strip():
                    return res
            except Exception as e:
                if it == intentos_max:
                    raise e
                await asyncio.sleep(2)
        return ""

    for intento in range(1, max_intentos + 1):
        try:
            texto_generado = await _llamar_ia_con_retry(
                prompt=prompt_ia, 
                max_tokens=600, 
                temperature=0.3, 
                sys_p=system_msg
            )
            
            if not texto_generado:
                continue

            modelo_rev = globals().get('GROQ_REVISION_2', 'openai/gpt-oss-20b')
            prompt_auditor_final = prompt_auditor_base.format(informe_candidato=texto_generado)
            
            veredicto = await _llamar_ia_con_retry(
                prompt=prompt_auditor_final, 
                max_tokens=100, 
                temperature=0.1, 
                sys_p=None,
                mod_over=modelo_rev
            )

            if veredicto and "OK" in veredicto.strip().upper() and "RECHAZ" not in veredicto.strip().upper():
                informe_ia = texto_generado
                break

        except Exception as err:
            logger.error(f"❌ Error en ciclo de informe inicial (Intento {intento}): {err}")

    if not informe_ia:
        informe_ia = (
            f"Hello {nombre}, welcome to your personalized nutrition plan. "
            "We have successfully configured your profile with initial metabolic parameters "
            "to guide you step-by-step toward your wellness goal."
        )

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
    
    story.append(Paragraph("<b>INITIAL NUTRITIONAL REPORT - PROFILE SETUP</b>", titulo_style))
    story.append(Spacer(1, 8))
    
    resumen_datos = (
        f"<b>Patient:</b> {nombre} | <b>Telegram ID:</b> `{datos_usuario.get('user_id')}`<br/>"
        f"<b>Age:</b> {edad} years | <b>Sex:</b> {sexo} | <b>Height:</b> {altura} cm<br/>"
        f"<b>Current Weight:</b> {peso} kg | <b>Theoretical Ideal Weight:</b> {peso_ideal} kg<br/>"
        f"<b>1st Stage Goal:</b> {peso_etapa} kg | <b>Chosen Pace:</b> {ritmo_elegido.capitalize()}<br/>"
        f"<b>Daily Targets:</b> ~{meta_cal} kcal | Proteins: ~{meta_prot}g | Fats: ~{meta_gras}g | Carbs: ~{meta_carb}g"
    )
    story.append(Paragraph(resumen_datos, sub_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph("<b>PLANNING AND INITIAL RECOMMENDATIONS</b>", styles['Heading2']))
    story.append(Spacer(1, 6))
    
    texto_formateado = informe_ia.replace('\n', '<br/>')
    story.append(Paragraph(texto_formateado, body_style))
    
    doc.build(story)
    pdf_buffer.seek(0)
    
    return informe_ia, pdf_buffer
        
async def obtener_recomendacion_ia(resumen_texto: str, es_semanal: bool = False, user_id=None):
    nombre_lenguaje = obtener_nombre_lenguaje_ia(user_id)

    if es_semanal:
        prompt = (
            f"Actúa como un coach nutricional breve y conciso. "
            f"Analiza este resumen semanal:\n{resumen_texto}\n\n"
            f"Escribe un solo párrafo corto de análisis general y 3 recomendaciones breves en puntos.\n"
            f"IMPORTANTE: Redacta la respuesta estrictamente en el idioma {nombre_lenguaje}."
        )
        max_t = 350
    else:
        prompt = (
            f"Actúa como un nutricionista clínico personal. "
            f"Analiza la siguiente información:\n{resumen_texto}\n\n"
            f"IMPORTANTE: Redacta la respuesta estrictamente en el idioma {nombre_lenguaje}."
        )
        max_t = 700

    system_msg = "Eres un nutricionista profesional y empático. Proporciona respuestas claras sin dejar oraciones inconclusas."
    res = ejecutar_consulta_ia(prompt, max_tokens=max_t, temperature=0.4, system_prompt=system_msg)
    
    if res:
        return res.replace("##", "").replace("###", "").strip()
        
    # Mensaje de fallback mediante variable multilenguaje 02_
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    return traducciones.get("02_error_analisis_no_disponible", "⚠️ Nutritional analysis temporarily unavailable.")

def analizar_imagen_con_groq(base64_image: str, user_caption: str = "") -> dict:
    client_ai = globals().get('client_ai')
    if not client_ai: return {"items": []}
    
    prompt = (
        f"Descripción del usuario: '{user_caption}'. "
        "Analiza esta foto de un plato de comida. "
        "Calcula el peso estimado en gramos, las calorías y los macronutrientes. "
        "REGLA ESTRICTA: Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin explicaciones ni saludos. "
        "El JSON debe tener exactamente esta estructura: "
        "{\"items\": [{\"alimento\": \"nombre\", \"peso\": 0.0, \"calorias\": 0.0, \"proteinas\": 0.0, \"grasas\": 0.0, \"carbohidratos\": 0.0, \"fibras\": 0.0}]}"
    )
    
    try:
        response = client_ai.chat.completions.create(
            model=globals().get('GROQ_FOTO', "qwen/qwen2.5-vl-7b-instruct"), # o el modelo visual que uses
            messages=[{
                "role": "user", 
                "content": [
                    {"type": "text", "text": prompt}, 
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }],
            temperature=0.0,
            max_tokens=400, # 👈 ESTO EVITA QUE SE VAYA DE TEMA Y SUPERE EL LÍMITE DE TOKENS
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"Error en análisis visual con Groq: {e}")
        return {"error": str(e)}
        
def detectar_codigo_con_groq(image_bytes: bytes, user_id=None) -> str:
    client_ai = globals().get('client_ai')
    if not client_ai:
        return ""

    encoded_image = base64.b64encode(image_bytes).decode('utf-8')
    data_url = f"data:image/jpeg;base64,{encoded_image}"

    prompt = (
        "Examina esta imagen en búsqueda de códigos de barras, texto impreso o códigos alfanuméricos de productos. "
        "Devuelve ÚNICAMENTE el código detectado en formato de texto plano. Si no encuentras ningún código o texto claro, responde exactamente con la palabra 'NUEVO'."
    )

    try:
        response = client_ai.chat.completions.create(
            model=globals().get('GROQ_FOTO', "qwen/qwen3.8-27b"),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": prompt}
                    ]
                }
            ],
            temperature=0.1,
            max_tokens=50
        )
        codigo = response.choices[0].message.content.strip()
        return "" if codigo.upper() == "NUEVO" else codigo
    except Exception as e:
        logger.error(f"Error detectando código en imagen: {e}")
        return ""

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
        t_reg_act = traducciones.get('bot_reg_actividad', "📝 <b>Registro de Actividad:</b>")
        t_fecha = traducciones.get('bot_label_fecha', "📅 Fecha")
        txt = f"{t_reg_act}\n{t_fecha}: `{fecha}`\n\n"
    else:
        t_conf_ing = traducciones.get('bot_conf_ingesta', "📝 <b>Confirmación de Ingesta:</b>")
        t_fecha = traducciones.get('bot_label_fecha', "📅 Fecha")
        t_momento = traducciones.get('bot_label_momento', "Momento")
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
            t_calorias = traducciones.get('bot_macro_calorias', "Calorías")
            t_proteinas = traducciones.get('bot_macro_proteinas', "Proteínas")
            t_grasas = traducciones.get('bot_macro_grasas', "Grasas tot.")
            t_fibras = traducciones.get('bot_macro_fibras', "Fibras")

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
            mark = "✅ " if nombre_momento.lower() == momento.lower() else ""
            m_buttons.append(InlineKeyboardButton(f"{mark}{etiqueta_visual}", callback_data=f"set_m_{nombre_momento}"))
        keyboard.append(m_buttons)

    es_plantilla = any('§' in item.get('alimento', item.get('nombre', '')) for item in items)

    if not es_plantilla:
        for idx, item in enumerate(items, start=1):
            nombre_corto = item.get('alimento', item.get('nombre', ''))[:10]
            keyboard.append([
                InlineKeyboardButton(f"#{idx} {nombre_corto}", callback_data=f"noop_{idx}"),
                InlineKeyboardButton("✏️", callback_data=f"edit_item_{idx}"),
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
        InlineKeyboardButton(f"{mark_hoy}{hoy_label}", callback_data="set_d_hoy"),
        InlineKeyboardButton(f"{mark_ayer}{ayer_label}", callback_data="set_d_ayer"),
        InlineKeyboardButton(f"{mark_otro}🗓️", callback_data="set_d_otro")
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

    fecha, momento_auto = obtener_momento_y_fecha_auto()
    
    if tipo == "Actividad":
        momento = "Actividad"
        for item in items:
            # 🟢 Forzar estrictamente el peso en 0 para que no guarde nada en la columna de Peso
            item["peso"] = 0
            
            # Asegurar que las calorías de la actividad sean negativas
            if item.get("calorias", 0) > 0:
                item["calorias"] = -abs(item["calorias"])
    else:
        momento = momento_auto

    context.user_data['pending_items'] = items
    context.user_data['pending_fecha'] = fecha
    context.user_data['pending_momento'] = momento

    await render_confirmation_screen(msg_obj, context)
    
#               MANEJADORES INDEPENDIENTES Y EXCLUSIVOS PARA CADA GRUPO DE BOTONES (CERO COMPARTIDOS)
# ======================================================================================================================================

@requiere_registro
async def callback_handler_actividades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # 🟢 CORREGIDO: Alineado a los prefijos estándar 'act_' para evitar fallos de enrutamiento
    if data in ["act_tipo_texto", "act_ind_texto"]:
        context.user_data['awaiting_activity_text'] = True
        msg_solic = await query.message.reply_text(
            "⌨️ Escribí la actividad (Ej: `50 minutos de caminata a velocidad moderada`):", parse_mode="Markdown"
        )
        context.user_data['msg_solicitud_activity_id'] = msg_solic.message_id
    elif data in ["act_tipo_audio", "act_ind_audio"]:
        context.user_data['awaiting_activity_voice'] = True
        await query.message.reply_text("🎙️ Enviá una nota de voz describiendo tu actividad física.", parse_mode="Markdown")
    elif data in ["act_cancelar", "act_ind_cancelar"]:
        context.user_data.pop('awaiting_activity_text', None)
        context.user_data.pop('awaiting_activity_voice', None)
        await query.edit_message_text("❌ Registro de actividad cancelado.")

@requiere_registro
async def callback_handler_momentos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    context.user_data['last_menu_msg_id'] = query.message.message_id
    
    if data.startswith("set_m_"):
        context.user_data['pending_momento'] = data.replace("set_m_", "")
        await render_confirmation_screen(query, context)
       
@requiere_registro
async def callback_handler_fechas_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    context.user_data['last_menu_msg_id'] = query.message.message_id

    if data == "set_d_hoy":
        context.user_data['pending_fecha'] = obtener_ahora_arg().strftime("%Y-%m-%d")
        await render_confirmation_screen(query, context)
    elif data == "set_d_ayer":
        context.user_data['pending_fecha'] = (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d")
        await render_confirmation_screen(query, context)
    elif data in ["set_d_otro", "set_d_custom"]:
        context.user_data['awaiting_custom_date'] = True
        msg = await query.message.reply_text("📅 Ingresá la fecha deseada para la ingesta (Ej: `2026-08-15` o `15/08`):", parse_mode="Markdown")
        context.user_data['msg_solicitud_fecha_id'] = msg.message_id
    elif data == "diario_hoy":
        await mostrar_diario_fecha(query, user_id, obtener_ahora_arg().strftime("%Y-%m-%d"))
    elif data == "diario_ayer":
        await mostrar_diario_fecha(query, user_id, (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d"))
    elif data == "diario_otro":
        context.user_data['awaiting_diario_custom_date'] = True
        msg = await query.message.reply_text("📅 Ingresá la fecha del diario que querés consultar (Ej: `2026-08-15` o `15/08`):", parse_mode="Markdown")
        context.user_data['msg_solicitud_diario_fecha_id'] = msg.message_id

@requiere_registro
async def callback_handler_editar_anular(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    context.user_data['last_menu_msg_id'] = query.message.message_id

    if data.startswith("edit_item_"):
        idx = int(data.replace("edit_item_", "")) - 1
        context.user_data.update({'awaiting_edit_item_val': True, 'editing_item_idx': idx})
        momento_actual = context.user_data.get('pending_momento', 'Comida')
        items = context.user_data.get('pending_items', [])
        es_codigo_barras = (0 <= idx < len(items) and items[idx].get('fuente') == "Open Food Facts")

        if momento_actual == 'Actividad':
            await query.message.reply_text("✏️ Ingresá el nuevo valor de calorías para la actividad (ej: `220`):", parse_mode="Markdown")
        elif es_codigo_barras:
            await query.message.reply_text("⚖️ Ingresá el **nuevo peso en gramos** para este producto (ej: `150`):", parse_mode="Markdown")
        else:
            await query.message.reply_text("✏️ Ingresá la nueva descripción y/o peso para este alimento:")
    elif data.startswith("del_item_"):
        idx = int(data.replace("del_item_", "")) - 1
        items = context.user_data.get('pending_items', [])
        if 0 <= idx < len(items): items.pop(idx)
        if not items:
            await query.edit_message_text("❌ Todos los ítems fueron eliminados.")
            context.user_data.pop('last_menu_msg_id', None)
        else:
            await render_confirmation_screen(query, context)

@requiere_registro
async def callback_handler_guardar_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    context.user_data['last_menu_msg_id'] = query.message.message_id

    if data == "cancel_entry":
        context.user_data.pop('pending_items', None)
        context.user_data.pop('last_menu_msg_id', None)
        await query.edit_message_text("🗑️ Registro cancelado.")
    elif data == "confirm_save":
        items = context.user_data.get('pending_items', [])
        fecha = context.user_data.get('pending_fecha')
        momento = context.user_data.get('pending_momento')

        if items and fecha and momento:
            tipo_registro = "Actividad" if momento == "Actividad" else "Comida"
            guardar_en_sheets(user_id, items, fecha, momento, tipo=tipo_registro)
            
            txt_conf = f"✅ **¡Actividad guardada exitosamente!**\n📅 `{fecha}`" if momento == "Actividad" else f"✅ **¡Ingesta guardada exitosamente!**\n📅 `{fecha}` | `{momento}`"
            await query.edit_message_text(txt_conf, parse_mode="Markdown")
            context.user_data.pop('pending_items', None)
            context.user_data.pop('last_menu_msg_id', None)
        else:
            await query.edit_message_text("❌ No se encontraron datos para guardar.")

@requiere_registro
async def callback_handler_eliminacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

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
        msg = await query.message.reply_text("📅 Ingresá la fecha que querés revisar (Ej: `2026-08-15` o `15/08`):", parse_mode="Markdown")
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
        await context.bot.send_document(chat_id=query.message.chat_id, document=pdf, filename=f"Diario_{f_str}.pdf")
    elif data.startswith("descargar_pdf_presion_"):
        mes_str = data.replace("descargar_pdf_presion_", "")
        df_p = obtener_datos_presion_db(user_id)
        pdf_p = generar_pdf_presion_bytes(mes_str, df_p[df_p['Fecha_Dia'].str.startswith(mes_str)] if not df_p.empty else pd.DataFrame(), user_id)
        await context.bot.send_document(chat_id=query.message.chat_id, document=pdf_p, filename=f"Presion_{mes_str}.pdf")
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
    
    txt_analizando = traducciones.get('bot_analizando_act', "🏃 Analizando actividad física y calculando calorías...")
    msg_espera = await update.message.reply_text(txt_analizando)
    try:
        res = analizar_con_groq(f"Actividad física: {raw_text}. Devuelve JSON con alimento y calorias.")
        items = res.get('items', [])
        kcal = float(items[0].get('calorias', 0)) if items else 0.0
        desc = str(items[0].get('alimento', raw_text)) if items else raw_text
        
        item_act = {"alimento": desc, "peso": 0, "calorias": -abs(kcal), "proteinas": 0, "grasas": 0, "carbohidratos": 0, "fibras": 0}
        
        context.user_data.update({'pending_items': [item_act], 'pending_fecha': obtener_ahora_arg().strftime("%Y-%m-%d"), 'pending_momento': 'Actividad'})
        await msg_espera.delete()
        
        txt_analizada = traducciones.get('bot_act_analizada', "📋 Actividad analizada:")
        msg_menu = await update.message.reply_text(txt_analizada)
        context.user_data['last_menu_msg_id'] = msg_menu.message_id
        await render_confirmation_screen(msg_menu, context)
    except Exception as e:
        txt_err = traducciones.get('bot_error_proc_act', "❌ Error al procesar actividad: {e}").format(e=e)
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
        txt_err_fec = traducciones.get('bot_error_fecha_inv', "⚠️ Formato de fecha inválido. Ingrese nuevamente (Ej: `2026-08-15` o `15/08`):")
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
        txt_err_fec = traducciones.get('bot_error_fecha_inv', "⚠️ Formato de fecha inválido. Ingrese nuevamente (Ej: `2026-08-15` o `15/08`):")
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
        txt_err_fec = traducciones.get('bot_error_fecha_inv', "⚠️ Formato de fecha inválido. Ingrese nuevamente (Ej: `2026-08-15` o `15/08`):")
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
        txt_act = traducciones.get('bot_actualizando', "⏳ Actualizando valores...")
        msg_espera = await update.message.reply_text(txt_act)
        try:
            if momento_actual == 'Actividad':
                nuevo_kcal = float(re.sub(r'[^\d.]', '', raw_text.replace(',', '.')))
                item_previo['calorias'] = -abs(nuevo_kcal)
            else:
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
            txt_err_ed = traducciones.get('bot_error_editar', "❌ Error al editar: {e}").format(e=e)
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

async def _sub_manejar_plantilla_comida(update, context, raw_text, user_id):
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
            "fibras": f_b * mult
        }
        txt_proc = traducciones.get('bot_proc_comida', "⏳ Procesando comida predeterminada...")
        msg = await update.message.reply_text(txt_proc)
        await procesar_y_mostrar_confirmacion({"items": [item_gen], "tipo": "Comida"}, msg, context)
    else:
        txt_err_noenc = traducciones.get('bot_error_comida_no_enc', f"❌ No se encontró la comida `*{nombre_plantilla}` en tu planilla `Comidas_{user_id}`.")
        await update.message.reply_text(txt_err_noenc, parse_mode="Markdown")
        
async def _sub_manejar_ingesta_libre_ia(update, context, raw_text):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    txt_analiz_ia = traducciones.get('bot_analizando_texto', "🤖 Analizando texto con Inteligencia Artificial...")
    msg = await update.message.reply_text(txt_analiz_ia)
    try:
        data = analizar_con_groq(raw_text)
        await procesar_y_mostrar_confirmacion(data, msg, context)
    except Exception as e:
        txt_err_ia = traducciones.get('bot_error_proc_texto', "❌ Error al procesar el texto: {e}").format(e=e)
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
        txt_err_aud = traducciones.get('bot_error_audio', "❌ Error al procesar el audio con IA: {e}").format(e=e)
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
    txt_act_aud = traducciones.get('bot_act_audio', "📋 Actividad analizada por audio:")
    msg_menu = await update.message.reply_text(txt_act_aud)
    context.user_data['last_menu_msg_id'] = msg_menu.message_id
    await render_confirmation_screen(msg_menu, context)
    
async def _sub_manejar_foto_plato_ia(update, context, base64_image, user_caption, msg):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    txt_analiz_plato = traducciones.get('bot_analizando_plato', "🤖 Analizando plato con Inteligencia Artificial...")
    await msg.edit_text(txt_analiz_plato)

    try:
        data = analizar_imagen_con_groq(base64_image, user_caption)
        
        # Si hubo un error o la respuesta viene vacía/con error de tokens
        if not data or "error" in data or not data.get("items"):
            raise Exception("Límite o error en respuesta visual.")
            
        await procesar_y_mostrar_confirmacion(data, msg, context)

    except Exception as e:
        logger.error(f"Error al procesar plato por imagen para usuario {user_id}: {e}")
        
        # Mensaje amigable multilenguaje cuando la foto falla
        txt_error_imagen = traducciones.get(
            'bot_error_imagen_fallida', 
            "⚠️ No se pudo procesar la imagen correctamente (límite de la IA superado).\n\n"
            "Por favor, ingresá la descripción de tu plato o alimento escribiéndola por **texto** o enviando una nota de **voz**."
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
        txt_fec_ing = traducciones.get('bot_solic_fecha_ingesta', "📅 Ingresá la fecha deseada para la ingesta (Ej: `2026-08-15` o `15/08`):")
        msg = await query.message.reply_text(txt_fec_ing, parse_mode="Markdown")
        context.user_data['msg_solicitud_fecha_id'] = msg.message_id
    elif data == "diario_hoy":
        await mostrar_diario_fecha(query, user_id, obtener_ahora_arg().strftime("%Y-%m-%d"))
    elif data == "diario_ayer":
        await mostrar_diario_fecha(query, user_id, (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d"))
    elif data == "diario_otro":
        context.user_data['awaiting_diario_custom_date'] = True
        txt_diar_cons = traducciones.get('bot_solic_diario_consulta', "📅 Ingresá la fecha del diario que querés consultar (Ej: `2026-08-15` o `15/08`):")
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

    if momento_actual == 'Actividad':
        txt_ed_kcal = traducciones.get('bot_edit_calorias', "✏️ Ingresá el nuevo valor de calorías para la actividad (ej: `220`):")
        await query.message.reply_text(txt_ed_kcal, parse_mode="Markdown")
    elif es_codigo_barras:
        txt_ed_peso = traducciones.get('bot_edit_peso_gr', "⚖️ Ingresá el **nuevo peso en gramos** para este producto (ej: `150`):")
        await query.message.reply_text(txt_ed_peso, parse_mode="Markdown")
    else:
        txt_ed_gen = traducciones.get('bot_edit_desc_peso', "✏️ Ingresá la nueva descripción y/o peso para este alimento:")
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
        txt_all_del = traducciones.get('bot_all_del', "❌ Todos los ítems fueron eliminados.")
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
    txt_canc = traducciones.get('bot_reg_canc', "🗑️ Registro cancelado.")
    await query.edit_message_text(txt_canc)

@requiere_registro
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
            txt_conf = traducciones.get('bot_save_act_exito', f"✅ **¡Actividad guardada exitosamente!**\n📅 `{fecha}`")
        else:
            txt_conf = traducciones.get('bot_save_meal_exito', f"✅ **¡Ingesta guardada exitosamente!**\n📅 `{fecha}` | `{momento}`")
            
        await query.edit_message_text(txt_conf, parse_mode="Markdown")
        context.user_data.pop('pending_items', None)
        context.user_data.pop('last_menu_msg_id', None)
    else:
        txt_nodat = traducciones.get('bot_no_data', "❌ No se encontraron datos para guardar.")
        await query.edit_message_text(txt_nodat)

# ======================================================================================================================================
#                FINAL                                     COMANDOS CONFIRMACION FUNCIONES BOTONES                        FINAL
# ======================================================================================================================================

# ==================================================================================================================================
#                    INICIO                 COMANDOS COMIDAS Y COMANDOS ACTIVIDAD                                   INCIO  DB OK
# ==================================================================================================================================

#              INICIO                     FUNCIONES COMIDAS                   INICIO
# =============================================================================================================================================

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
        
        nombre_alimento = product.get("product_name_es") or product.get("product_name") or "Producto desconocido"
        marca = product.get("brands", "")
        if marca:
            nombre_alimento = f"{nombre_alimento} ({marca})"

        return {
            "alimento": nombre_alimento,
            "peso": 100.0,
            "calorias": float(nutriments.get("energy-kcal_100g", nutriments.get("energy-kcal", 0.0) or 0.0)),
            "proteinas": float(nutriments.get("proteins_100g", 0.0) or 0.0),
            "grasas": float(nutriments.get("fat_100g", 0.0) or 0.0),
            "carbohidratos": float(nutriments.get("carbohydrates_100g", 0.0) or 0.0),
            "fibras": float(nutriments.get("fiber_100g", 0.0) or 0.0),
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

def construir_texto_listado_comidas(user_id, comidas):
    """
    Construye y retorna el texto en formato HTML con el listado de comidas del usuario sin el caracter '§'.
    """
    if not comidas:
        return f"📋 No hay comidas predeterminadas registradas en la hoja 'Comidas_{user_id}'."

    txt = f"📋 <b>Listado de Comidas Predeterminadas (Comidas_{user_id}):</b>\n\n"
    
    for p in comidas:
        nombre_raw = str(p.get('Nombre', ''))
        desc_raw = str(p.get('Descripcion') or p.get('Momento', ''))
        
        # 🟢 Eliminación estricta del caracter '§'
        nombre = nombre_raw.replace('§', '').replace('<', '').replace('>', '').strip()
        descripcion = desc_raw.replace('§', '').replace('<', '').replace('>', '').strip()
        
        if descripcion and descripcion.lower() != nombre.lower():
            linea = f"• <b>{nombre}</b>: {descripcion}\n"
        else:
            linea = f"• <b>{nombre}</b>\n"
        
        if len(txt) + len(linea) > 4000:
            txt += "• <i>...y más comidas (ver detalle en el PDF adjunto).</i>\n"
            break
            
        txt += linea
        
    return txt
 
def _garantizar_fila_mes_actual(user_id: int, ahora_dt) -> None:
    mes_actual_str = ahora_dt.strftime("%Y-%m")
    tabla_nombre = f"Perfil_{user_id}"

    try:
        conn, cur = _asegurar_tabla_y_conectar(tabla_nombre, tipo_tabla="perfil")
        
        cur.execute(f'SELECT id FROM "{tabla_nombre}" WHERE "MES" = %s', (str(mes_actual_str),))
        fila_existente = cur.fetchone()
        
        if fila_existente:
            cur.close()
            conn.close()
            return

        logger.info(f"Inicializando nueva fila mensual ({mes_actual_str}) para User {user_id} en Supabase...")

        cur.execute(f'SELECT "EDAD", "PESO", "ALTURA", "GENERO", "ocupacion", "Peso_ideal", "Cumple" FROM "{tabla_nombre}" ORDER BY id DESC LIMIT 1')
        ultima_fila = cur.fetchone()
        
        if ultima_fila:
            edad_val = ultima_fila[0] or "64"
            peso_val = ultima_fila[1] or 70.0
            altura_val = ultima_fila[2] or 1.70
            genero_val = ultima_fila[3] or "M"
            ocupacion_val = ultima_fila[4] or 1.375
            peso_ideal_val = ultima_fila[5] or 0.0
            cumple_val = ultima_fila[6] or ""
        else:
            edad_val = "64"
            peso_val = 70.0
            altura_val = 1.70
            genero_val = "M"
            ocupacion_val = 1.375
            peso_ideal_val = 0.0
            cumple_val = ""

        cur.execute(f"""
            INSERT INTO "{tabla_nombre}" ("EDAD", "PESO", "ALTURA", "GENERO", "ocupacion", "MES", "Fecha_Actualizacion", "Peso_ideal", "Cumple")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            str(edad_val),
            float(peso_val),
            float(altura_val),
            str(genero_val),
            float(ocupacion_val),
            str(mes_actual_str),
            ahora_dt.strftime("%Y-%m-%d"),
            float(peso_ideal_val),
            str(cumple_val)
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Fila del mes {mes_actual_str} creada exitosamente en Supabase para User {user_id}")

    except Exception as e:
        logger.error(f"Error al garantizar fila mensual en Supabase para User {user_id}: {e}")
        if 'cur' in locals() and cur:
            cur.close()
        if 'conn' in locals() and conn:
            conn.close()
   
#                      INICIO                               COMANDOS COMIDAS PRECARGADAS                              INICIO  DB OK
# =======================================================================================================================================
@requiere_registro
async def cmd_comidas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Obtener idioma y traducciones para el usuario
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
    comidas = obtener_comidas_usuario(user_id)
    
    if not comidas:
        msg_no_comidas = traducciones.get("bot_no_comidas_precargadas", f"📋 No hay comidas predeterminadas registradas en la hoja 'Comidas_{user_id}'.")
        await update.message.reply_text(msg_no_comidas)
        return

    txt = construir_texto_listado_comidas(user_id, comidas)
    msg_adjunto = traducciones.get("bot_adjunto_pdf_comidas", "\n📄 Te adjuntamos el archivo en PDF completo con todos los macronutrientes a continuación.")
    txt += msg_adjunto
    
    try:
        await update.message.reply_text(txt, parse_mode="HTML")
    except Exception as e:
        print(f"Error enviando texto de comidas: {e}")
        msg_generando = traducciones.get("bot_generando_pdf_comidas", "📋 Generando tu lista de comidas en PDF directamente...")
        await update.message.reply_text(msg_generando)

    try:
        pdf_bytes = generar_pdf_comidas_bytes(comidas, user_id)
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_bytes,
            filename=f"Comidas_{user_id}.pdf"
        )
    except Exception as e:
        print(f"Error generando PDF de comidas: {e}")
        msg_err_pdf = traducciones.get("bot_error_gen_pdf", "❌ Ocurrió un error al generar el archivo PDF.")
        await update.message.reply_text(msg_err_pdf)

@requiere_registro
async def cmd_borrar_comida(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Obtener idioma y traducciones para el usuario
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
    if context.args:
        nombre_a_borrar = " ".join(context.args).strip()
        
        comida_encontrada = buscar_comida_precargada_exacta(user_id, nombre_a_borrar)
        
        if not comida_encontrada:
            msg_no_enc = traducciones.get("bot_comida_no_encontrada", f"❌ No se encontró ninguna comida registrada con el nombre exacto: <b>{nombre_a_borrar}</b>.")
            await update.message.reply_text(
                msg_no_enc.format(nombre=nombre_a_borrar),
                parse_mode="HTML"
            )
            return
        
        exito = eliminar_comida_precargada_db(user_id, comida_encontrada['nombre'])
        
        if exito:
            msg_exito = traducciones.get("bot_comida_borrada_exito", f"✅ La comida <b>{comida_encontrada['nombre']}</b> ha sido eliminada exitosamente de tu planilla.")
            await update.message.reply_text(
                msg_exito.format(nombre=comida_encontrada['nombre']),
                parse_mode="HTML"
            )
        else:
            msg_err_db = traducciones.get("bot_error_db_borrar", f"❌ Hubo un error en la base de datos al intentar borrar <b>{comida_encontrada['nombre']}</b>.")
            await update.message.reply_text(
                msg_err_db.format(nombre=comida_encontrada['nombre']),
                parse_mode="HTML"
            )
        return

    comidas = obtener_comidas_usuario(user_id)
    
    if not comidas:
        msg_no_reg = traducciones.get("bot_no_comidas_borrar", f"📋 No hay comidas predeterminadas registradas para eliminar.")
        await update.message.reply_text(msg_no_reg)
        return

    txt = construir_texto_listado_comidas(user_id, comidas)
    msg_instruccion = traducciones.get("bot_como_borrar_comida", "\n🗑️ <b>¿Cómo borrar una comida?</b>\nCopiá el nombre exacto de la lista de arriba y escribí el comando de la siguiente forma:\n<code>/borrarcomida Nombre de la Comida</code>")
    txt += msg_instruccion
    
    try:
        await update.message.reply_text(txt, parse_mode="HTML")
    except Exception as e:
        print(f"Error enviando texto de borrado: {e}")
        msg_err_list = traducciones.get("bot_error_mostrar_listado", "📋 Ocurrió un error al mostrar el listado.")
        await update.message.reply_text(msg_err_list)

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

    t_titulo = traducciones.get("PDF_comidas_titulo", "LISTADO DE COMIDAS PREDETERMINADAS")

    story = [
        Paragraph(f"<b>{t_titulo}</b>", title_style),
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=12),
    ]

    if not plantillas:
        msg_vacio = traducciones.get("PDF_comidas_sin_reg", "No hay comidas predeterminadas cargadas en la hoja 'Plantillas_Comidas'.")
        story.append(Paragraph(msg_vacio, body_style))
    else:
        th_nombre = traducciones.get("PDF_comidas_th_nombre", "Nombre")
        th_desc = traducciones.get("PDF_comidas_th_desc", "Descripción")
        th_peso = traducciones.get("PDF_comidas_th_peso", "Peso (g)")
        th_kcal = traducciones.get("PDF_comidas_th_kcal", "Kcal")
        th_prot = traducciones.get("PDF_comidas_th_prot", "Prot (g)")
        th_gras = traducciones.get("PDF_comidas_th_gras", "Gras (g)")
        th_carb = traducciones.get("PDF_comidas_th_carb", "Carb (g)")
        th_fibr = traducciones.get("PDF_comidas_th_fibr", "Fibr (g)")

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
    
@requiere_registro
async def cmd_cargar_receta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
    web_app_url = f"https://telegram-bot-nutricion.onrender.com/?user_id={user_id}#calculadora"
    
    btn_text = traducciones.get("bot_btn_crear_receta", "🍳 Abrir Creador de Recetas")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_text, url=web_app_url)]
    ])
    
    msg_tmpl = traducciones.get("bot_msg_cargar_receta", "👋 ¡Hola! Usá el siguiente botón para calcular los valores nutricionales de tu receta e ingresarla directamente en tu planilla personalizada (*Comidas_{user_id}*):")
    mensaje = msg_tmpl.format(user_id=user_id)
    
    await update.message.reply_text(mensaje, reply_markup=keyboard, parse_mode="Markdown")
        
#                INICIO                             COMANDOS BARRA                                 INICIO DB OK
# ========================================================================================================================================

def detectar_y_leer_codigo_barras_ia(base64_image: str) -> str:
    """
    Envía la foto a la IA exclusivamente para que lea los números impresos 
    abajo del código de barras del producto.
    """
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
    
    # Obtener idioma y traducciones para el usuario
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
    msg_analizando = traducciones.get("bot_analizando_barra", "🔍 Analizando código de barras y verificando producto...")
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
            msg_prod_encontrado = traducciones.get("bot_producto_encontrado", "📋 Producto encontrado (valores calculados cada 100 g):")
            msg_menu = await message_obj.reply_text(msg_prod_encontrado)
            
            context.user_data['last_menu_msg_id'] = msg_menu.message_id
            context.user_data['pending_items'] = [item_procesado]
            context.user_data['pending_fecha'] = fecha_auto
            context.user_data['pending_momento'] = momento_auto
                
            await render_confirmation_screen(msg_menu, context)
        else:
            msg_no_enc = traducciones.get("bot_barra_no_encontrada", "⚠️ Código de barras no encontrado en la base de datos. Intentá ingresarlo como texto o foto.")
            await msg_espera.edit_text(msg_no_enc)
            
    except Exception as e:
        msg_err_gen = traducciones.get("bot_error_consulta_barra", "❌ Error al consultar el código: {e}").format(e=e)
        await msg_espera.edit_text(msg_err_gen)
        
@requiere_registro
async def cmd_barra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Obtener idioma y traducciones para el usuario
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
    args = context.args
    
    if not args:
        msg_solic_txt = traducciones.get("bot_solic_barra_num", "⌨️ Por favor, ingresá los números del código de barras con el comando /barra NUMERO:")
        msg_solic = await update.message.reply_text(
            msg_solic_txt,
            parse_mode="Markdown"
        )
        context.user_data['awaiting_barcode_input'] = True
        context.user_data['msg_solicitud_barcode_id'] = msg_solic.message_id
        return

    barcode_text = args[0].strip()
    await procesar_codigo_ingresado(update.message, context, barcode_text)
               

#                   INICIO                       COMANDO ELIMINAR INGESTAS ACTIVIDAD                         INICIO
# ======================================================================================================================================

@requiere_registro
async def cmd_eliminar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    context.user_data.pop('del_fecha', None)
    context.user_data.pop('del_momento', None)

    # 🟢 BOTONES UNIVERSALES (Sin texto, solo emojis/iconos fijos)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅", callback_data="del_d_hoy"), InlineKeyboardButton("📆", callback_data="del_d_ayer")],
        [InlineKeyboardButton("🗓️", callback_data="del_d_otro")]
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
    
    # 🟢 BOTONES UNIVERSALES CON FRANJAS HORARIAS E ICONOS (Igual que en los registros)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌅 08-11", callback_data="del_mom_Desayuno"), InlineKeyboardButton("☀️ 11-16", callback_data="del_mom_Almuerzo")],
        [InlineKeyboardButton("☕ 16-20", callback_data="del_mom_Merienda"), InlineKeyboardButton("🌙 20-00", callback_data="del_mom_Cena")],
        [InlineKeyboardButton("🏃 ⚡", callback_data="del_mom_Actividad")],
        [InlineKeyboardButton("🔙 📅", callback_data="del_cambiar_fecha")]
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
            [InlineKeyboardButton("🔙", callback_data="del_volver_momentos")]
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
            keyboard.append([
                InlineKeyboardButton(f"❌ {nombre_corto}", callback_data=f"del_reg_{item_id}")
            ])

    # Botón universal para borrar todo el momento y el de volver
    keyboard.append([InlineKeyboardButton("🗑️ ⚠️", callback_data="del_borrar_todo_momento")])
    keyboard.append([InlineKeyboardButton("🔙", callback_data="del_volver_momentos")])

    markup = InlineKeyboardMarkup(keyboard)
    try:
        await query.edit_message_text(txt, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        await query.message.reply_text(txt, reply_markup=markup, parse_mode="Markdown")
        
async def manejar_callback_eliminacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    if data == "del_d_hoy":
        context.user_data['del_fecha'] = obtener_ahora_arg().strftime("%Y-%m-%d")
        await mostrar_selector_momento_eliminar(query, context)

    elif data == "del_d_ayer":
        context.user_data['del_fecha'] = (obtener_ahora_arg() - timedelta(days=1)).strftime("%Y-%m-%d")
        await mostrar_selector_momento_eliminar(query, context)

    elif data == "del_d_otro":
        context.user_data['awaiting_del_custom_date'] = True
        msg_solic = await query.message.reply_text("📅 Ingresá la fecha que querés revisar (Ej: `2026-08-15` o `15/08`):", parse_mode="Markdown")
        context.user_data['msg_solicitud_del_fecha_id'] = msg_solic.message_id

    elif data.startswith("del_mom_"):
        momento = data.replace("del_mom_", "")
        context.user_data['del_momento'] = momento
        await render_pantalla_items_eliminar(query, user_id, context)

    elif data.startswith("del_reg_"):
        item_id = int(data.replace("del_reg_", ""))
        exito = eliminar_registro_por_id(user_id, item_id)
        
        if exito:
            await query.answer("🗑️ Ítem eliminado correctamente.", show_alert=False)
        else:
            await query.answer("⚠️ No se pudo eliminar el ítem.", show_alert=True)
            
        await render_pantalla_items_eliminar(query, user_id, context)

    elif data == "del_borrar_todo_momento":
        fecha = context.user_data.get('del_fecha')
        momento = context.user_data.get('del_momento')
        
        df = obtener_datos_usuario(user_id)
        if not df.empty and 'Fecha' in df.columns and 'Momento' in df.columns:
            df['Fecha_clean'] = df['Fecha'].astype(str).str.strip()
            df['Momento_clean'] = df['Momento'].astype(str).str.strip().str.lower()
            momento_busqueda = momento.strip().lower()

            if momento_busqueda == 'actividad':
                df_filtrado = df[(df['Fecha_clean'] == str(fecha).strip()) & (df['Momento_clean'].isin(['actividad', 'actividad física', 'ejercicio']))]
            else:
                df_filtrado = df[(df['Fecha_clean'] == str(fecha).strip()) & (df['Momento_clean'] == momento_busqueda)]

            for _, r in df_filtrado.iterrows():
                if 'id_registro' in r:
                    eliminar_reg_id = int(r['id_registro'])
                    eliminar_registro_por_id(user_id, eliminar_reg_id)
                    
        await query.answer("🗑️ Todos los registros de este momento fueron eliminados.", show_alert=True)
        await mostrar_selector_momento_eliminar(query, context)

    elif data in ["del_cambiar_fecha", "del_volver_momentos"]:
        await mostrar_selector_momento_eliminar(query, context)
        

#                INICIO                             MANEJADOR COMIDAS ACTIVIDAD                                 INICIO DB OK
# =====================================================================================================================================

@requiere_registro
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id, chat_id = update.effective_user.id, update.effective_chat.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    raw_text = update.message.text.strip() if update.message and update.message.text else ""
    if not raw_text: 
        return

    if context.user_data.get('awaiting_presion_nota'):
        context.user_data.pop('awaiting_presion_nota', None)
        datos_presion = context.user_data.pop('pending_presion_foto', None)

        if raw_text.lower() == "cancelar":
            txt_canc_presion = traducciones.get("bot_presion_cancelada", "❌ Registro de presión cancelado.")
            await update.message.reply_text(txt_canc_presion)
            return

        if datos_presion:
            alta = datos_presion.get("alta")
            baja = datos_presion.get("baja")
            pulsaciones = datos_presion.get("pulsaciones")
            nota = raw_text

            guardar_presion_db(user_id, alta, baja, pulsaciones, nota=nota)

            pul_txt = f" | Pulsaciones: `{pulsaciones:.0f} lpm`" if pulsaciones > 0 else ""
            await update.message.reply_text(
                f"✅ **¡Presión arterial registrada con éxito!**\n\n"
                f"• Presión Alta: `{alta:.0f} mmHg`\n"
                f"• Presión Baja: `{baja:.0f} mmHg`{pul_txt}\n"
                f"📝 Nota: `{nota}`",
                parse_mode="Markdown"
            )
        else:
            txt_exp_presion = traducciones.get("bot_presion_expirada", "⚠️ Los datos temporales de la presión expiraron.")
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

    msg = await update.message.reply_text("🤖 Analizando texto con Inteligencia Artificial...")
    try:
        data = analizar_con_groq(raw_text)
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
        await msg.edit_text(f"❌ Error al procesar el texto: {e}")

@requiere_registro
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
    txt_analizando_img = traducciones.get("bot_analizando_imagen", "📸 Analizando imagen...")
    msg = await update.message.reply_text(txt_analizando_img)
    try:
        photo_bytes = await (await update.message.photo[-1].get_file()).download_as_bytearray()
        base64_image = base64.b64encode(photo_bytes).decode('utf-8')
        user_caption = update.message.caption or ""
        
        res_presion = analizar_foto_presion_con_groq(base64_image)
        if res_presion.get("es_presion") and float(res_presion.get("alta", 0)) > 0:
            return await _sub_manejar_foto_presion(update, context, res_presion, msg)

        image_bytes = bytes(base64.b64decode(base64_image))
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        tiene_codigo_local = False
        if img is not None:
            detector = cv2.barcode.BarcodeDetector()
            retval, points = detector.detect(img)
            if retval:
                tiene_codigo_local = True

        if tiene_codigo_local:
            await msg.edit_text("🔍 Código de barras detectado. Leyendo números del envase...")
            codigo_leido = detectar_y_leer_codigo_barras_ia(base64_image)
            
            if codigo_leido and len(codigo_leido.strip()) >= 4:
                await msg.delete()
                return await procesar_codigo_ingresado(update.message, context, codigo_leido.strip())

        return await _sub_manejar_foto_plato_ia(update, context, base64_image, user_caption, msg)

    except Exception as e:
        await msg.edit_text(f"❌ Error al procesar imagen: {e}")

@requiere_registro
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = await update.message.reply_text("🎙️ Procesando audio con IA...")
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
            await msg.edit_text("⚠️ No se pudo entender el audio.")
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
        await msg.edit_text(f"❌ Error al procesar audio: {e}")
        
             
# =====================================================================================================================================
#                FINAL                               COMANDOS COMIDA COMANDOS ACTIVIDAD                           FINAL
# ======================================================================================================================================

# ======================================================================================================================================
#                   INICIO                                    COMANDOS INFORMES                                   INICIO  DB OK
# =====================================================================================================================================
#              INICIO                     FUNCIONES INFORMES                   INICIO
# =============================================================================================================================================

def calcular_metricas_mensuales(df_mes, perfil_dict):
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
    peso_actual = get_perfil_num(['Peso', 'peso', 'peso_actual', 'PESO'], 104.6)
    
    ocupacion = str(perfil_dict.get('Ocupacion') or perfil_dict.get('ocupacion') or perfil_dict.get('actividad', 'ligero')).strip()
    genero = str(perfil_dict.get('GENERO') or perfil_dict.get('Genero') or perfil_dict.get('genero', 'masculino')).strip()
    gen_clean = genero.lower()
    is_femenino = gen_clean in ["femenino", "f", "mujer", "female"]
    ritmo_usuario = str(perfil_dict.get('Ritmo') or perfil_dict.get('ritmo_preferido', 'moderado')).strip()

    peso_ideal_secreto = get_perfil_num(['peso_ideal_secreto', 'peso_ideal', 'Peso_Ideal'], 81.0)

    ritmo_clean = ritmo_usuario.lower()
    if "tranquilo" in ritmo_clean or "lento" in ritmo_clean:
        factor_actual = 0.90
    elif "rapido" in ritmo_clean or "intenso" in ritmo_clean or "decidido" in ritmo_clean:
        factor_actual = 0.75
    else:
        factor_actual = 0.85
    factor_ideal = 1.0 - factor_actual

    peso_etapa_calculado = (peso_actual * factor_actual) + (peso_ideal_secreto * factor_ideal)
    
    peso_referencia = round(peso_etapa_calculado, 1)
    peso_ideal_dinamico = peso_referencia  

    min_act = 30
    max_act = 60

    _, get_real = calcular_tmb_y_get(
        peso_actual=peso_actual, altura_cm=altura, edad=edad, genero=genero, actividad=ocupacion, peso_ideal=peso_ideal_dinamico
    )
    _, get_meta = calcular_tmb_y_get(
        peso_actual=peso_referencia, altura_cm=altura, edad=edad, genero=genero, actividad=ocupacion, peso_ideal=peso_ideal_dinamico
    )

    gasto_diario_total = get_real + prom_quem
    balance_diario = prom_cons - gasto_diario_total
    cambio_peso_kg = (balance_diario * dias_registrados) / 7700.0
    deficit_diario_real = -balance_diario

    if is_femenino:
        factor_proteina_min = 1.0
        factor_proteina_max = 1.2
        fibr_min = 25
    else:
        factor_proteina_min = 1.2
        factor_proteina_max = 1.5
        fibr_min = 30

    cal_max = int(round(get_meta))
    cal_min = max(1500, int(round(cal_max - 600)))

    prot_min = int(round(peso_referencia * factor_proteina_min))
    prot_max = int(round(peso_referencia * factor_proteina_max))

    gras_min = int(round((cal_min * 0.20) / 9.0))
    gras_max = int(round((cal_max * 0.30) / 9.0))

    carb_min = int(round((cal_min * 0.40) / 4.0))
    carb_max = int(round((cal_max * 0.55) / 4.0))

    fibr_min_val = fibr_min

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
        "act_min": min_act,
        "act_max": max_act,
        "cal_min": cal_min, "cal_max": cal_max,
        "prot_min": prot_min, "prot_max": prot_max,
        "gras_min": gras_min, "gras_max": gras_max,
        "carb_min": carb_min, "carb_max": carb_max,
        "fibr_min": fibr_min_val,
        "ideal_cal": cal_max,
        "ideal_prot": prot_max,
        "ideal_gras": gras_max,
        "ideal_carb": carb_max,
        "ideal_fibr": fibr_min_val,
        "peso_actual": round(float(peso_actual), 1),
        "peso_ideal": round(float(peso_ideal_dinamico), 1),
        "peso_referencia": round(float(peso_referencia), 1),
        "altura": round(float(altura), 1),
        "edad": edad,
        "get_meta": get_meta,
        "get_real": get_real,
        "deficit_diario_real": int(round(deficit_diario_real)),
        "cambio_peso_kg": cambio_peso_kg,
        "tot_cons": tot_cons_mes,
        "tot_quem": tot_quem_mes,
        "tot_prot": tot_prot,
        "tot_gras": tot_gras,
        "tot_carb": tot_carb,
        "tot_fibr": tot_fibr
    }

async def procesar_y_enviar_informe_mensual(context, user_id: int, chat_destino: int, mes_target: str, es_automatico_15: bool = False, forzar_envio: bool = False):
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    try:
        peso_ok = await _validar_peso_mes_actual(context=context, user_id=user_id)
        if not peso_ok and not forzar_envio:
            return False

        df_datos = obtener_datos_usuario(user_id) if 'obtener_datos_usuario' in globals() else pd.DataFrame()
        if df_datos.empty or 'Fecha' not in df_datos.columns:
            msg_nodata = traducciones.get("sup_inf_no_registros", "⚠️ Not enough records to generate the report.")
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
            msg_template = traducciones.get("sup_inf_sin_registros_periodo", "⚠️ No closed records found for the period {etiqueta_periodo}.")
            msg_closed = msg_template.format(etiqueta_periodo=etiqueta_periodo)
            await context.bot.send_message(chat_id=user_id, text=msg_closed)
            return False

        perfil = obtener_perfil_usuario(user_id, mes_target=mes_target) if 'obtener_perfil_usuario' in globals() else {}
        m = calcular_metricas_mensuales(df_filtrado, perfil) if 'calcular_metricas_mensuales' in globals() else {}
        conteo_frecuencias = analizar_frecuencia_alimentos_mes(user_id, mes_target) if 'analizar_frecuencia_alimentos_mes' in globals() else {}

        peso_actual_eval = float(m.get('peso_actual', 0))
        peso_referencia_eval = float(m.get('peso_referencia', 0))
        prompt_condicional = obtener_prompt_segun_objetivo_peso(peso_actual_eval, peso_referencia_eval) if 'obtener_prompt_segun_objetivo_peso' in globals() else None

        informe_ia = await generar_informe_mensual_auditado(
            context=context, 
            user_id=user_id, 
            mes_str=mes_target, 
            m=m, 
            frecuencias=conteo_frecuencias,
            prompt_condicional=prompt_condicional
        )

        if not informe_ia:
            informe_ia = traducciones.get("sup_inf_error_ia", "<b>⚠️ Could not generate the AI audited report after retries.</b>")

        recomendacion_pdf = (
            informe_ia
            .replace("<br>", "<br/>")
            .replace("<BR>", "<br/>")
        )

        df_presion = pd.DataFrame()
        tmb_val = perfil.get('tmb', 0) if isinstance(perfil, dict) else 0
        pdf_buffer = await asyncio.to_thread(
            generar_pdf_resumen_bytes,
            mes_target,
            df_filtrado,
            df_presion,
            perfil,
            tmb_val,
            recomendacion_pdf,
            user_id
        )
        return True
    except Exception as e:
        logger.error(f"Error in procesar_y_enviar_informe_mensual for {user_id}: {e}")
        return False
        
async def mostrar_resumen_presion_mes(query_or_update, user_id, mes_str):
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    df_presion = obtener_datos_presion_db(user_id)
    if df_presion.empty:
        # Mensaje informativo para el usuario convertido en variable
        txt = traducciones.get("sup_sin_presion_usuario", f"🩺 No blood pressure records found for user `{user_id}`.").format(user_id=user_id)
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(txt, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(txt, parse_mode="Markdown")
        return

    df_p_mes = df_presion[df_presion['Fecha_Dia'].str.startswith(mes_str)] if 'Fecha_Dia' in df_presion.columns else pd.DataFrame()
    if df_p_mes.empty:
        # Mensaje informativo para el usuario convertido en variable
        txt = traducciones.get("sup_sin_presion_mes", f"🩺 No blood pressure records found for the month `{mes_str}`.").format(mes_str=mes_str)
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(txt, parse_mode="Markdown")
        else:
            await query_or_update.message.reply_text(txt, parse_mode="Markdown")
        return

    alta_prom = df_p_mes['Alta'].mean()
    baja_prom = df_p_mes['Baja'].mean()
    pul_prom = df_p_mes[df_p_mes['Pulsaciones'] > 0]['Pulsaciones'].mean() if 'Pulsaciones' in df_p_mes.columns else 0

    titulo_resumen = traducciones.get("sup_resumen_presion_titulo", "🩺 <b>Blood Pressure Summary ({mes_str}):</b>").format(mes_str=mes_str)
    mediciones_reg = traducciones.get("sup_mediciones_registradas", "• Recorded measurements: `{count}`").format(count=len(df_p_mes))
    prom_alta = traducciones.get("sup_prom_alta", "• <b>Average High (Systolic):</b> `{alta:.1f} mmHg`").format(alta=alta_prom)
    prom_baja = traducciones.get("sup_prom_baja", "• <b>Average Low (Diastolic):</b> `{baja:.1f} mmHg`").format(baja=baja_prom)
    
    txt = f"{titulo_resumen}\n\n{mediciones_reg}\n{prom_alta}\n{prom_baja}\n"

    if pul_prom > 0:
        prom_pulso = traducciones.get("sup_prom_pulsaciones", "• <b>Average Pulse:</b> `{pul:.1f} bpm`").format(pul=pul_prom)
        txt += f"{prom_pulso}\n"

    btn_texto = traducciones.get("sup_btn_descargar_pdf_presion", "📄 Download Daily Pressure PDF")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_texto, callback_data=f"descargar_pdf_presion_{mes_str}")]
    ])

    if hasattr(query_or_update, 'edit_message_text'):
        await query_or_update.edit_message_text(txt, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await query_or_update.message.reply_text(txt, reply_markup=keyboard, parse_mode="Markdown")
        
def generar_pdf_presion_bytes(mes_str, df_presion, user_id):
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1E3A8A'), spaceAfter=4)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor('#1E293B'))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8.5, leading=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)

    t_titulo_tmpl = traducciones.get("PDF_presion_titulo", "Detalle Diario de Presion Arterial - {mes_str}")
    t_usr_tmpl = traducciones.get("PDF_presion_usuario_id", "**Usuario Telegram ID:** {user_id}")

    story = [
        Paragraph(f"<b>{t_titulo_tmpl.format(mes_str=mes_str)}</b>", title_style),
        Paragraph(t_usr_tmpl.format(user_id=user_id), body_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=10)
    ]

    if df_presion.empty:
        msg_vacio = traducciones.get("PDF_presion_sin_reg", "No hay registros de presion para este mes.")
        story.append(Paragraph(msg_vacio, body_style))
    else:
        th_fecha = traducciones.get("PDF_presion_th_fecha", "Fecha y Hora")
        th_alta = traducciones.get("PDF_presion_th_alta", "Alta (mmHg)")
        th_baja = traducciones.get("PDF_presion_th_baja", "Baja (mmHg)")
        th_pulso = traducciones.get("PDF_presion_th_pulso", "Pulsaciones")
        th_nota = traducciones.get("PDF_presion_th_nota", "Nota / Detalle")

        table_data = [[
            Paragraph(th_fecha, header_style),
            Paragraph(th_alta, header_style),
            Paragraph(th_baja, header_style),
            Paragraph(th_pulso, header_style),
            Paragraph(th_nota, header_style)
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
    
#                   INICIO                                    COMANDO DIA                                    INICIO  DB OK
# =====================================================================================================================================

@requiere_registro
async def cmd_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Manejador del comando /diario.
    Muestra el menú de selección de fecha con formato Día/Mes (DD/MM).
    """
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    # Obtenemos las etiquetas numéricas en formato Día/Mes (ej: 23/09)
    hoy_label = obtener_ahora_arg().strftime("%d/%m")
    ayer_label = (obtener_ahora_arg() - timedelta(days=1)).strftime("%d/%m")
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"📅 {hoy_label}", callback_data="diario_hoy"), 
            InlineKeyboardButton(f"📆 {ayer_label}", callback_data="diario_ayer")
        ],
        [
            InlineKeyboardButton("🗓️", callback_data="diario_otro")
        ]
    ])
    
    texto_titulo = traducciones.get("inf_diario_titulo", "📅 **Consulta de Diario:** Seleccioná qué día querés revisar:")
    
    await update.message.reply_text(
        texto_titulo, 
        reply_markup=keyboard, 
        parse_mode="Markdown"
    )
    
async def mostrar_diario_fecha(update_or_query, user_id, fecha_str):
    """
    Función auxiliar para procesar y renderizar el reporte del diario agrupado por evento.
    """
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    try:
        df = obtener_datos_usuario(user_id)
        df_diario = df[df['Fecha'].astype(str).str.strip() == str(fecha_str).strip()] if not df.empty and 'Fecha' in df.columns else pd.DataFrame()

        if df_diario.empty:
            msg_no_reg = traducciones.get("inf_diario_no_reg", "⚠️ No se encontraron registros de ingestas para la fecha `{fecha_str}`.")
            texto = msg_no_reg.format(fecha_str=fecha_str)
            reply_markup = None
        else:
            msg_reg_dia = traducciones.get("inf_diario_reg_dia", "📅 Registro del día {fecha_str}:\n\n")
            texto = msg_reg_dia.format(fecha_str=fecha_str)
            
            momentos_vistos = []
            agrupado = {}
            
            for _, r in df_diario.iterrows():
                momento = str(r.get('Momento', '')).strip()
                alimento = str(r.get('Alimento', '')).strip()
                
                if momento not in agrupado:
                    agrupado[momento] = []
                    momentos_vistos.append(momento)
                if alimento:
                    agrupado[momento].append(alimento)

            for m in momentos_vistos:
                items_str = ", ".join(agrupado[m])
                texto += f"• {m}: {items_str}\n"

            c_cons = df_diario[df_diario['Calorias'] > 0]['Calorias'].sum()
            c_quem = abs(df_diario[df_diario['Calorias'] < 0]['Calorias'].sum())
            b_neto = c_cons - c_quem
            
            p_tot = df_diario[df_diario['Calorias'] > 0]['Proteinas'].sum()
            g_tot = df_diario[df_diario['Calorias'] > 0]['Grasas'].sum()
            cb_tot = df_diario[df_diario['Calorias'] > 0]['Carbohidratos'].sum()
            f_tot = df_diario[df_diario['Calorias'] > 0]['Fibras'].sum()

            lbl_cons = traducciones.get("inf_diario_consumidas", "🔥 Consumidas:")
            lbl_quem = traducciones.get("inf_diario_quemadas", "⚡ Quemadas:")
            lbl_bal = traducciones.get("inf_diario_balance", "⚖️ Balance Neto:")
            
            texto += f"\n{lbl_cons} {c_cons:.1f} kcal\n"
            texto += f"{lbl_quem} {c_quem:.1f} kcal\n"
            texto += f"{lbl_bal} {b_neto:.1f} kcal\n\n"
            
            template_macros = traducciones.get("inf_diario_macronutrientes", "🥩 Prot: {p_tot:.1f}g | 🥑 Gras: {g_tot:.1f}g | 🍞 Carb: {cb_tot:.1f}g | 🌾 Fibr: {f_tot:.1f}g")
            texto += template_macros.format(p_tot=p_tot, g_tot=g_tot, cb_tot=cb_tot, f_tot=f_tot)

            btn_pdf_text = traducciones.get("inf_diario_btn_pdf", "📄 Descargar PDF")
            keyboard = [[InlineKeyboardButton(btn_pdf_text, callback_data=f"descargar_pdf_diario_{fecha_str}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

        # Manejo unificado y seguro para editar el mensaje del callback o responder uno nuevo
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
            
        msg_err_tmpl = traducciones.get("inf_diario_error", "❌ Error al consultar el diario para la fecha `{fecha_str}`: {e}")
        msg_err = msg_err_tmpl.format(fecha_str=fecha_str, e=e)
        
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
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1E3A8A'), spaceAfter=4)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor('#1E293B'))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8.5, leading=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)

    t_titulo_tmpl = traducciones.get("PDF_diario_titulo", "Detalle Diario de Ingestas - {fecha_str}")
    t_usr_tmpl = traducciones.get("PDF_diario_usuario_id", "**Usuario Telegram ID:** {user_id}")
    
    story = [
        Paragraph(f"<b>{t_titulo_tmpl.format(fecha_str=fecha_str)}</b>", title_style),
        Paragraph(t_usr_tmpl.format(user_id=user_id), body_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=10)
    ]

    if df_diario.empty:
        msg_vacio = traducciones.get("PDF_diario_sin_reg", "No hay registros para esta fecha.")
        story.append(Paragraph(msg_vacio, body_style))
    else:
        th_momento = traducciones.get("PDF_diario_th_momento", "Momento")
        th_alimento = traducciones.get("PDF_diario_th_alimento", "Alimento / Detalle")
        th_peso = traducciones.get("PDF_diario_th_peso", "Peso")
        th_kcal = traducciones.get("PDF_diario_th_kcal", "Kcal")
        th_prot = traducciones.get("PDF_diario_th_prot", "Prot")
        th_gras = traducciones.get("PDF_diario_th_gras", "Gras")
        th_carb = traducciones.get("PDF_diario_th_carb", "Carb")
        th_fibr = traducciones.get("PDF_diario_th_fibr", "Fibr")

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

        tot_cons_tpl = traducciones.get("PDF_diario_tot_consumidas", "• <b>Total Consumidas:</b> {c_cons:.1f} kcal")
        tot_quem_tpl = traducciones.get("PDF_diario_tot_quemadas", "• <b>Total Quemadas:</b> {c_quem:.1f} kcal")
        bal_neto_tpl = traducciones.get("PDF_diario_balance_neto", "• <b>Balance Neto:</b> {b_neto:.1f} kcal")

        story.append(Paragraph(tot_cons_tpl.format(c_cons=c_cons), body_style))
        story.append(Paragraph(tot_quem_tpl.format(c_quem=c_quem), body_style))
        story.append(Paragraph(bal_neto_tpl.format(b_neto=b_neto), body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer
    
#                 INICIO                            COMANDO SEMANA                             INICIO   DB OK
# ======================================================================================================================================

def _generar_texto_resumen_semanal(user_id, inicio_rango, fin_rango, etiqueta_periodo):
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
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
    act_min_val, act_max_val = calcular_rango_actividad_fisica(peso_act_val, peso_ref_val)

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

    prom_minutos_act = int(round(minutos_totales_actividad / 7.0))

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

    t_titulo = traducciones.get("inf_semana_titulo", "📅 **Resumen Nutricional Semanal:**")
    t_prom = traducciones.get("inf_semana_promedios", "📈 **Promedios vs. Rangos Saludables:**")
    
    cal_tpl = traducciones.get("inf_semana_calorias", "• Calorías: `{prom_cal} kcal` / Rango: `{cal_min} - {cal_max} kcal`").format(prom_cal=m.get('prom_cal', 0), cal_min=m.get('cal_min', 0), cal_max=m.get('cal_max', 0))
    prot_tpl = traducciones.get("inf_semana_proteinas", "• Proteínas: `{prom_prot} g` / Rango: `{prot_min} - {prot_max} g`").format(prom_prot=m.get('prom_prot', 0), prot_min=m.get('prot_min', 0), prot_max=m.get('prot_max', 0))
    gras_tpl = traducciones.get("inf_semana_grasas", "• Grasas: `{prom_gras} g` / Rango: `{gras_min} - {gras_max} g`").format(prom_gras=m.get('prom_gras', 0), gras_min=m.get('gras_min', 0), gras_max=m.get('gras_max', 0))
    carb_tpl = traducciones.get("inf_semana_carbohidratos", "• Carbohidratos: `{prom_carb} g` / Rango: `{carb_min} - {carb_max} g`").format(prom_carb=m.get('prom_carb', 0), carb_min=m.get('carb_min', 0), carb_max=m.get('carb_max', 0))
    fibr_tpl = traducciones.get("inf_semana_fibras", "• Fibras: `{prom_fibr} g` / Mínimo: `{fibr_min} g`").format(prom_fibr=m.get('prom_fibr', 0), fibr_min=m.get('fibr_min', 0))
    act_tpl = traducciones.get("inf_semana_actividad", "• Actividad Física: `{prom_minutos_act} min/día` / Rango: `{act_min} - {act_max} min/día`").format(prom_minutos_act=prom_minutos_act, act_min=act_min_val, act_max=act_max_val)

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
        pres_tpl = traducciones.get("inf_semana_presion", "• **Presión Arterial Promedio:** `{prom_alta}/{prom_baja} mmHg`").format(prom_alta=prom_alta, prom_baja=prom_baja)
        txt += f"{pres_tpl}\n"

    quem_tpl = traducciones.get("inf_semana_quemadas", "• **Calorías Quemadas (Promedio):** `{prom_quem} kcal/día`").format(prom_quem=m.get('prom_quem', 0))
    dias_tpl = traducciones.get("inf_semana_dias_eval", "• **Días Evaluados:** `{dias_reg}`").format(dias_reg=m.get('dias_registrados', 0))
    nota_txt = traducciones.get("inf_semana_nota", "_(Nota: Los rangos de actividad consideran impacto corporal; actividades como aquagym o natación no aplican restricciones de sobrepeso)._")

    txt += (
        f"\n{quem_tpl}\n"
        f"{dias_tpl}\n\n"
        f"{nota_txt}"
    )

    return txt, m
            
@requiere_registro
async def cmd_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    if not await _validar_peso_mes_actual(update=update, context=context):
        return

    try:
        msg_esp = traducciones.get("inf_semana_espera", "⏳ Procesando resumen nutricional...")
        msg_espera = await update.message.reply_text(msg_esp)

        tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
        ahora_arg = datetime.now(tz_arg)
        hoy = ahora_arg.date()
        dia_semana = ahora_arg.weekday()

        if dia_semana == 0:
            inicio_rango = hoy - timedelta(days=7)
            fin_rango = hoy - timedelta(days=1)
            etiqueta_periodo = "Semana Anterior (Lunes a Domingo)" if lang == 'es' else "Previous Week (Monday to Sunday)"
        else:
            inicio_rango = hoy - timedelta(days=dia_semana)
            fin_rango = hoy - timedelta(days=1)
            if lang == 'es':
                dias_espanol = {1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
                nombre_dia_ayer = dias_espanol.get(dia_semana - 1, "")
                etiqueta_periodo = f"Semana Actual (Lunes a {nombre_dia_ayer})"
            else:
                dias_ingles = {1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}
                nombre_dia_ayer = dias_ingles.get(dia_semana - 1, "")
                etiqueta_periodo = f"Current Week (Monday to {nombre_dia_ayer})"

        txt, _ = _generar_texto_resumen_semanal(user_id, inicio_rango, fin_rango, etiqueta_periodo)

        if not txt:
            msg_vacio = traducciones.get("inf_semana_sin_registros", "⚠️ No hay registros acumulados para los días transcurridos de este período.")
            await msg_espera.edit_text(msg_vacio)
            return

        await msg_espera.edit_text(txt, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en cmd_mensaje: {e}")
        if 'msg_espera' in locals():
            msg_err_tmpl = traducciones.get("inf_semana_error", "⚠️ Error al calcular resumen semanal: {e}")
            await msg_espera.edit_text(msg_err_tmpl.format(e=e))
                        
                     
#               INICIO                                COMANDO RESUMEN COMANDO MES                       INICIO DB OK
# ==========================================================================================================================================

@requiere_registro
async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

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
            [InlineKeyboardButton("🗓️", callback_data="resumen_mes_menu_otros")]
        ])
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📅 {label_mes_actual}", callback_data=f"resumen_mes_{mes_actual_iso}")],
            [InlineKeyboardButton(f"📆 {label_mes_anterior}", callback_data=f"resumen_mes_{mes_anterior_iso}")],
            [InlineKeyboardButton("🗓️", callback_data="resumen_mes_menu_otros")]
        ])

    texto_titulo = traducciones.get("inf_mes_titulo", "📊 **Resumen Mensual:** Seleccioná la opción que querés consultar:")
    await update.message.reply_text(
        texto_titulo, 
        reply_markup=keyboard, 
        parse_mode="Markdown"
    )
        
async def mostrar_resumen_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        user_id = query.from_user.id if query else update.effective_user.id
        lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
        traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

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
                
                btn_volver = traducciones.get("inf_mes_volver", "🔙 Volver")
                botones_meses.append([InlineKeyboardButton(btn_volver, callback_data="resumen_volver_menu")])
                
                texto_sel = traducciones.get("inf_mes_seleccion", "🗓️ **Seleccioná el mes que querés consultar:**")
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
                        [InlineKeyboardButton("🗓️", callback_data="resumen_mes_menu_otros")]
                    ])
                else:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(f"📅 {label_mes_actual}", callback_data=f"resumen_mes_{mes_actual_str}")],
                        [InlineKeyboardButton(f"📆 {label_mes_anterior}", callback_data=f"resumen_mes_{mes_anterior_iso}")],
                        [InlineKeyboardButton("🗓️", callback_data="resumen_mes_menu_otros")]
                    ])

                texto_titulo = traducciones.get("inf_mes_titulo", "📊 **Resumen Mensual:** Seleccioná la opción que querés consultar:")
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
            msg = traducciones.get("inf_mes_actual_restr", "⚠️ No se encuentra disponible el resumen del mes actual durante los primeros 7 días del mes.")
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
            msg_tpl = traducciones.get("inf_mes_sin_reg", "⚠️ No hay registros cargados para el mes `{mes_str}`.")
            msg = msg_tpl.format(mes_str=mes_str)
            if query:
                await query.edit_message_text(msg, parse_mode="Markdown")
            else:
                await update.message.reply_text(msg, parse_mode="Markdown")
            return

        perfil = obtener_perfil_usuario(user_id, mes_target=mes_str) if 'obtener_perfil_usuario' in globals() else {}
        m = calcular_metricas_mensuales(df_mes, perfil)

        minutos_mes_act = 0
        dias_activos_act = m.get('dias_registrados', 1) if m.get('dias_registrados', 1) > 0 else 1
        if not df_mes.empty and 'Momento' in df_mes.columns and 'Alimento' in df_mes.columns:
            for _, row in df_mes.iterrows():
                momento_str = str(row.get('Momento', '')).strip().lower()
                alimento_str = str(row.get('Alimento', '')).strip()
                cal_val = float(row.get('Calorias', 0) or 0)
                if cal_val < 0 or 'actividad' in momento_str or 'ejercicio' in momento_str or 'caminata' in momento_str:
                    match = re.match(r'^(\d+)', alimento_str)
                    if match:
                        minutos_mes_act += int(match.group(1))
        prom_minutos_mes_act = int(round(minutos_mes_act / dias_activos_act))

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
        texto_variacion_peso = f"`{cambio_peso_val:+.1f} kg`"

        template_enc = traducciones.get(
            "inf_mes_reporte_enc",
            "📊 **Reporte Nutricional Mensual ({mes_str}):**\n"
            "⚖️ Peso registrado: `{peso_reg} kg`\n\n"
            "• Consumidas: `{cons} kcal` | Quemadas: `{quem} kcal`\n"
            "• Balance Neto: `{neto} kcal/día`\n"
            "• Variación Est. de Peso: {var_peso} ({dias} días)\n\n"
            "📈 **Promedios vs. Rangos Saludables:**\n"
            "• Calorías: `{cons} kcal` / Rango: `{c_min} - {c_max} kcal`\n"
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
            act=prom_minutos_mes_act,
            act_min=act_min_val, act_max=act_max_val
        )

        pie_txt = traducciones.get("inf_mes_pie_pdf", "\n\n📄 Podés descargar el informe completo en PDF abajo:")
        txt_final = f"{encabezado_txt}{pie_txt}"

        btn_pdf_text = traducciones.get("inf_mes_btn_descargar", "📄 Descargar PDF Resumen Mensual")
        keyboard = [[InlineKeyboardButton(btn_pdf_text, callback_data=f"descargar_pdf_resumen_{mes_str}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if query:
            await query.edit_message_text(txt_final, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(txt_final, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en mostrar_resumen_mes: {e}", exc_info=True)
        msg_err_tmpl = traducciones.get("inf_mes_error_gral", "⚠️ Ocurrió un error al generar el resumen mensual: {e}")
        msg_err = msg_err_tmpl.format(e=e)
        if update.callback_query:
            await update.callback_query.edit_message_text(msg_err)
        else:
            await update.message.reply_text(msg_err)
                                                
def generar_pdf_resumen_bytes(mes_str, df_mes, df_presion, perfil, tmb_val, recomendacion, user_id):
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=14, textColor=colors.HexColor('#1E3A8A'), spaceAfter=4)
    sub_style = ParagraphStyle('SubTitle', parent=styles['Heading2'], fontSize=10, textColor=colors.HexColor('#2563EB'), spaceBefore=6, spaceAfter=2)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#1E293B'))
    rec_style = ParagraphStyle('RecBody', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#0F172A'), spaceAfter=1)
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=1)

    t_titulo_tmpl = traducciones.get("PDF_resumen_titulo", "Reporte Nutricional Mensual - {mes_str}")
    t_usr_tmpl = traducciones.get("PDF_resumen_usuario_id", "**Usuario Telegram ID:** {user_id}")

    story = [
        Paragraph(f"<b>{t_titulo_tmpl.format(mes_str=mes_str)}</b>", title_style),
        Paragraph(t_usr_tmpl.format(user_id=user_id), body_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=6)
    ]

    h_fecha = traducciones.get("PDF_resumen_th_fecha", "Fecha")
    h_cal_cons = traducciones.get("PDF_resumen_th_cal_cons", "Cal. Consumid.")
    h_cal_quem = traducciones.get("PDF_resumen_th_cal_quem", "Cal. Quemad.")
    h_bal_neto = traducciones.get("PDF_resumen_th_bal_neto", "Bal. Neto")
    h_prot = traducciones.get("PDF_resumen_th_proteinas", "Proteinas (g)")
    h_gras = traducciones.get("PDF_resumen_th_grasas", "Grasas (g)")
    h_carb = traducciones.get("PDF_resumen_th_carbs", "Carbohidratos (g)")
    h_fibr = traducciones.get("PDF_resumen_th_fibras", "Fibras (g)")

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

        lbl_tot = traducciones.get("PDF_resumen_total_mes", "TOTAL MES")
        lbl_prom = traducciones.get("PDF_resumen_prom_diario", "PROM. DIARIO")

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
    
    sub_analisis = traducciones.get("PDF_resumen_analisis_sub", "Análisis Metabólico y Tabla Comparativa de Macronutrientes (Rangos Saludables)")
    story.append(Paragraph(f"<b>{sub_analisis}</b>", title_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2563EB'), spaceAfter=6))

    perfil_dict = perfil if isinstance(perfil, dict) else {}
    m = calcular_metricas_mensuales(df_mes, perfil_dict)

    th_nutriente = traducciones.get("PDF_resumen_th_nutriente", "Nutriente / Métrica")
    th_prom_real = traducciones.get("PDF_resumen_th_prom_real", "Promedio Diario Real (Mes)")
    th_rango_salud = traducciones.get("PDF_resumen_th_rango_salud", "Rango / Mínimo Saludable")

    n_cal = traducciones.get("PDF_resumen_nutr_calorias", "Calorías")
    n_prot = traducciones.get("PDF_resumen_nutr_proteinas", "Proteínas")
    n_gras = traducciones.get("PDF_resumen_nutr_grasas", "Grasas")
    n_carb = traducciones.get("PDF_resumen_nutr_carbs", "Carbohidratos")
    n_fibr = traducciones.get("PDF_resumen_nutr_fibras", "Fibras")
    min_tpl = traducciones.get("PDF_resumen_minimo", "Mínimo {val} g")

    table_comp = [
        [Paragraph(f"<b>{th_nutriente}</b>", header_style), Paragraph(f"<b>{th_prom_real}</b>", header_style), Paragraph(f"<b>{th_rango_salud}</b>", header_style)],
        [Paragraph(n_cal, body_style), Paragraph(f"{m.get('prom_cal', 0)} kcal", body_style), Paragraph(f"{m.get('cal_min', 0)} - {m.get('cal_max', 0)} kcal", body_style)],
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

    p_perfil_tmpl = traducciones.get("PDF_resumen_perfil_reg", "• <b>PERFIL REGISTRADO EN EL MES ({mes_str}):</b> Peso Registrado: {peso_act_pdf} kg | Peso Objetivo de esta etapa : {peso_ref_pdf} kg |")
    p_def_tmpl = traducciones.get("PDF_resumen_deficit_diario", "• <b>DÉFICIT CALÓRICO DIARIO PROMEDIO:</b> {deficit} kcal / día")
    p_cambio_tmpl = traducciones.get("PDF_resumen_cambio_peso", "• <b>CAMBIO ESTIMADO DE PESO EN EL MES:</b> {cambio:+.1f} kg")
    p_act_tmpl = traducciones.get("PDF_resumen_act_fisica", "• <b>ACTIVIDAD FÍSICA PROMEDIO:</b> {act_minutos} min/día (Rango recomendado: {act_min} - {act_max} min/día)")
    p_nota_act = traducciones.get("PDF_resumen_nota_act", "<i>(Nota: Los rangos de actividad consideran impacto corporal; actividades de bajo impacto como aquagym, natación o yoga no aplican restricciones de sobrepeso).</i>")

    story.append(Paragraph(p_perfil_tmpl.format(mes_str=mes_str, peso_act_pdf=peso_act_pdf, peso_ref_pdf=peso_ref_pdf), body_style))
    story.append(Paragraph(p_def_tmpl.format(deficit=m.get('deficit_diario_real', 0)), body_style))
    story.append(Paragraph(p_cambio_tmpl.format(cambio=m.get('cambio_peso_kg', 0)), body_style))
    story.append(Paragraph(p_act_tmpl.format(act_minutos=m.get('prom_minutos_act', 0), act_min=m.get('act_min', 30), act_max=m.get('act_max', 60)), body_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph(p_nota_act, body_style))

    story.append(Spacer(1, 4))
    inf_nutr_lbl = traducciones.get("PDF_resumen_informe_nutr", "Informe Nutricional:")
    story.append(Paragraph(f"<b>{inf_nutr_lbl}</b>", sub_style))

    if isinstance(recomendacion, str) and recomendacion.strip():
        rec_limpia = recomendacion.strip().replace('""', '"')
        for bloque in rec_limpia.split('\n\n'):
            bloque_txt = bloque.strip()
            if bloque_txt:
                lineas_filtradas = [
                    linea for linea in bloque_txt.split('\n') 
                    if not linea.strip().startswith('|') and '|' not in linea
                ]
                bloque_sin_tablas = '<br/>'.join(lineas_filtradas).strip()
                
                if bloque_sin_tablas:
                    try:
                        story.append(Paragraph(bloque_sin_tablas, rec_style))
                        story.append(Spacer(1, 2))
                    except Exception:
                        texto_plano = re.sub('<[^<]+?>', '', bloque_sin_tablas)
                        story.append(Paragraph(texto_plano, rec_style))
                        story.append(Spacer(1, 2))

    doc.build(story)
    buffer.seek(0)
    return buffer
    
async def generar_y_enviar_pdf_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
    # 1. 🟢 Aviso inicial automático al usuario de que se está preparando el documento
    txt_aviso = traducciones.get("PDF_envio_aviso_inicial", "¡Recibido! Prepararemos el documento y cuando esté listo lo recibirá automáticamente. ⏳")
    await query.answer(txt_aviso, show_alert=True)
    
    txt_espera_tmpl = traducciones.get("PDF_envio_msg_espera", "🔄 **Generando reporte mensual...** Por favor aguarde unos momentos, le enviaremos el documento en cuanto esté listo.")
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
            txt_7dias = traducciones.get("PDF_envio_restr_7dias", "⚠️ No se encuentra disponible el reporte en PDF del mes actual durante los primeros 7 días del mes.")
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
            txt_sin_reg_tmpl = traducciones.get("PDF_envio_sin_reg_mes", "⚠️ No hay registros de días en el mes `{mes_str}` para generar el PDF.")
            await mensaje_espera.edit_text(txt_sin_reg_tmpl.format(mes_str=mes_str), parse_mode="Markdown")
            return

        perfil = obtener_perfil_usuario(user_id, mes_target=mes_str) if 'obtener_perfil_usuario' in globals() else {}
        df_presion = pd.DataFrame()
        tmb_val = perfil.get('tmb', 0) if isinstance(perfil, dict) else 0

        m = calcular_metricas_mensuales(df_mes, perfil)

        # 🟢 EXCLUSIVO MANUAL (SIN IA): Se define una nota estándar traducida
        recomendacion_pdf = traducciones.get("PDF_envio_nota_def", "Reporte mensual generado mediante métricas analíticas directas y cálculos puros del sistema.")

        pdf_buffer = await asyncio.to_thread(
            generar_pdf_resumen_bytes,
            mes_str,
            df_mes,
            df_presion,
            perfil,
            tmb_val,
            recomendacion_pdf,
            user_id
        )

        # 2. 🟢 Envío automático del PDF una vez finalizado el proceso
        caption_tmpl = traducciones.get("PDF_envio_exito_caption", "✅ ¡Su documento está listo! Reporte mensual auditado correspondiente a **{mes_str}**.")
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=pdf_buffer,
            filename=f"Reporte_Nutricional_{mes_str}.pdf",
            caption=caption_tmpl.format(mes_str=mes_str),
            parse_mode="Markdown"
        )
        
        try:
            await mensaje_espera.delete()
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Error al enviar PDF: {e}", exc_info=True)
        err_tmpl = traducciones.get("PDF_envio_error_gen", "⚠️ Error al procesar la descarga del PDF: {e}")
        await mensaje_espera.edit_text(err_tmpl.format(e=e))
        
#                INICIO                               MENSAJES PROGRAMADOS                          INICIO  
# ======================================================================================================================================

async def job_buenas_noches(context):
    """Envía un mensajito de buenas noches empático basado en lo que registró el usuario hoy."""
    try:
        registros_usuarios = obtener_todos_usuarios()
        if not registros_usuarios:
            return

        ahora_dt = obtener_ahora_arg()
        str_hoy = ahora_dt.strftime("%Y-%m-%d")

        for index, u in enumerate(registros_usuarios):
            try:
                estado_raw = str(u.get("Estado", u.get("estado", "0"))).strip().lower()
                notif = str(u.get("Notificaciones", "")).strip().lower()
                raw_user_id = u.get("User ID", u.get("user_id", ""))
                
                if not raw_user_id or estado_raw in ['baja', 'suspendido', '3'] or notif not in ["si", "sí"]:
                    continue
                
                user_id = int(str(raw_user_id).split('.')[0].strip())
                
                # Buscar si registró algo el día de hoy
                registros_u = obtener_registros_usuario(user_id)
                registros_hoy = [r for r in registros_u if str(r.get("Fecha", "")).strip() == str_hoy]
                
                # Si el usuario tuvo actividad hoy, le mandamos el cierre motivador
                if registros_hoy:
                    resumen_texto = ", ".join([f"{r.get('Momento/Actividad') or r.get('Momento', '')}: {r.get('Alimento/Detalle') or r.get('Alimento', '')}" for r in registros_hoy])
                    
                    prompt_noches = (
                        f"Actúa como un coach nutricional súper empático, cálido y amigable. "
                        f"Esto registró el usuario hoy: {resumen_texto}. "
                        f"Escríbete un mensaje de buenas noches brevísimo (máximo 2 o 3 líneas), recontra motivador, "
                        f"sin ningún regaño, destacando el esfuerzo del día y deseándole un buen descanso."
                    )
                    
                    mensaje_ia = ejecutar_consulta_ia(prompt_noches, max_tokens=150, temperature=0.5)
                    if mensaje_ia:
                        texto_final = f"🌙 **Buenas noches:**\n\n{mensaje_ia}"
                        await context.bot.send_message(chat_id=user_id, text=texto_final, parse_mode="Markdown")
                        
                        if index < len(registros_usuarios) - 1:
                            await asyncio.sleep(5)
            except Exception as e_user:
                logger.error(f"Error en buenas noches para usuario {u}: {e_user}")
    except Exception as e:
        logger.error(f"Error general en job_buenas_noches: {e}")
        
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

            df_presion = obtener_datos_presion_db(user_id) if 'obtener_datos_presion_db' in globals() else pd.DataFrame()
            
            tiene_medicion_reciente = False
            if not df_presion.empty and 'Fecha_Dia' in df_presion.columns:
                df_presion['Fecha_dt'] = pd.to_datetime(df_presion['Fecha_Dia'], errors='coerce')
                recientes = df_presion[df_presion['Fecha_dt'] >= pd.Timestamp(hace_siete_dias.date())]
                if not recientes.empty:
                    tiene_medicion_reciente = True

            if not tiene_medicion_reciente:
                mensaje = (
                    "🩺 **Recordatorio de Presión Arterial**\n\n"
                    "Hola. Notamos que todavía no registraste ninguna medición de presión arterial durante la semana pasada. "
                    "Te recordamos la importancia de mantener un control regular para tu seguimiento médico.\n\n"
                    "Podés registrarla cuando gustes usando el comando:\n"
                    "`/presi 120,80,70`\n\n"
                    "_Este es un aviso informativo y de acompañamiento, sin ninguna penalización._"
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

async def ejecutar_recordatorio_comidas(context, momento: str):
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
    comidas_principales = {"Almuerzo", "Cena"}
    
    es_lunes_manana = (hoy.weekday() == 0 and momento == 'manana')
    es_martes_manana = (hoy.weekday() == 1 and momento == 'manana')
    es_informe_mensual_pdf = (hoy.day in [5, 20] and momento == 'tarde')

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

            if es_lunes_manana:
                await _validar_peso_mes_actual(context=context, user_id=user_id)

                inicio_semana_pasada = hoy - timedelta(days=7)
                fin_semana_pasada = hoy - timedelta(days=1)

                registros_u = obtener_registros_usuario(user_id)

                dias_incompletos = []
                dias_validos_count = 0
                current_d = inicio_semana_pasada

                while current_d <= fin_semana_pasada:
                    str_d = current_d.strftime("%Y-%m-%d")
                    
                    comidas_del_dia = [
                        str(r.get("Momento/Actividad") or r.get("Momento", "")).capitalize() 
                        for r in registros_u 
                        if str(r.get("Fecha", "")).strip() == str_d 
                        and str(r.get("Momento/Actividad") or r.get("Momento", "")).capitalize() in todas_comidas
                    ]
                    
                    total_comidas = len(comidas_del_dia)
                    tiene_principal = any(c in comidas_principales for c in comidas_del_dia)
                    
                    if total_comidas >= 2 and tiene_principal:
                        dias_validos_count += 1
                    else:
                        dias_incompletos.append(str_d)
                    
                    current_d += timedelta(days=1)

                semana_completa = (dias_validos_count == 7)

                try:
                    actual_puntos = int(estado_raw) if estado_raw.isdigit() else 0
                except ValueError:
                    actual_puntos = 0

                if not semana_completa:
                    actual_puntos += 1
                    if actual_puntos >= 3:
                        actual_puntos = 3
                        actualizar_estado_usuario(user_id, "3")

                        await context.bot.send_message(
                            chat_id=user_id,
                            text=(
                                "Hola. Vimos que pasaron varias semanas sin actividad en el bot y por ahora pausamos tu seguimiento automático para no llenarte de avisos. "
                                "Cuando tengas ganas de retomar y ordenar tus hábitos de nuevo, simplemente escribinos o usá `/alta` para reactivar tu ficha. "
                                "¡Acá vamos a estar esperándote sin juzgar a nadie!"
                            ),
                            parse_mode="Markdown"
                        )
                        continue
                    else:
                        actualizar_estado_usuario(user_id, str(actual_puntos))

                        dias_str = ", ".join(dias_incompletos) if dias_incompletos else "varios días"
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=(
                                f"¡Hola! ☕ Notamos que la semana pasada se nos complicó un poquito el registro de las comidas ({dias_str}). "
                                f"¡No pasa nada! Los baches son totalmente normales y a todos nos pasa.\n\n"
                                f"Queremos acompañarte de la mejor manera, pero para que los reportes semanales salgan bien afinados necesitamos un mínimo de constancia. "
                                f"¿Te parece si arrancamos de nuevo hoy con toda la energía?"
                            ),
                            parse_mode="Markdown"
                        )
                else:
                    if actual_puntos > 0:
                        actual_puntos = 0
                        actualizar_estado_usuario(user_id, "0")

            if es_martes_manana:
                usuarios_actualizados = obtener_todos_usuarios()
                usuario_actual = next((u for u in usuarios_actualizados if str(u.get("User ID", u.get("user_id", ""))).split('.')[0].strip() == str(user_id)), {})
                current_estado_val = str(usuario_actual.get("Estado", usuario_actual.get("estado", "0"))).strip().lower()
                if current_estado_val == '3':
                    continue

                peso_ok = await _validar_peso_mes_actual(context=context, user_id=user_id)
                registros_u = obtener_registros_usuario(user_id)

                inicio_semana_pasada = hoy - timedelta(days=7)
                fin_semana_pasada = hoy - timedelta(days=1)
                dias_validos_count = 0
                dias_faltantes_detalle = []

                curr = inicio_semana_pasada
                while curr <= fin_semana_pasada:
                    str_c = curr.strftime("%Y-%m-%d")
                    
                    comidas_del_dia = [
                        str(r.get("Momento/Actividad") or r.get("Momento", "")).capitalize() 
                        for r in registros_u 
                        if str(r.get("Fecha", "")).strip() == str_c 
                        and str(r.get("Momento/Actividad") or r.get("Momento", "")).capitalize() in todas_comidas
                    ]
                    
                    total_comidas = len(comidas_del_dia)
                    tiene_principal = any(c in comidas_principales for c in comidas_del_dia)
                    
                    if total_comidas >= 2 and tiene_principal:
                        dias_validos_count += 1
                    else:
                        dias_faltantes_detalle.append(str_c)
                    curr += timedelta(days=1)

                semana_ok = (dias_validos_count == 7)

                if peso_ok and semana_ok:
                    try:
                        ahora_raw = obtener_ahora_arg()
                        if hasattr(ahora_raw, 'tzinfo') and ahora_raw.tzinfo is not None:
                            ahora_raw = ahora_raw.replace(tzinfo=None)
                        ahora_ts = pd.Timestamp(ahora_raw)

                        inicio_rango = (ahora_ts.floor('D') - pd.Timedelta(days=7)).date()
                        fin_rango = (ahora_ts.floor('D') - pd.Timedelta(seconds=1)).date()
                        etiqueta_periodo = "Semana Anterior (Lunes a Domingo)"

                        txt_resumen, m = _generar_texto_resumen_semanal(user_id, inicio_rango, fin_rango, etiqueta_periodo)

                        if txt_resumen and m:
                            await context.bot.send_message(chat_id=int(user_id), text=txt_resumen, parse_mode="Markdown")

                            prompt_semana = (
                                f"Actúa como un nutricionista clínico experto y constructivo. Analiza la evolución nutricional de la {etiqueta_periodo} "
                                f"comparando los promedios reales frente a los rangos saludables:\n\n"
                                f"PERFIL BIOMÉTRICO:\n"
                                f"- Edad: {m.get('edad', 'S/D')} años | Altura: {m.get('altura', 'S/D')} cm | Peso actual: {m.get('peso_actual', 'S/D')} kg\n\n"
                                f"DATOS DEL PERÍODO:\n"
                                f"- Días evaluados: {m.get('dias_registrados', 0)}\n"
                                f"- Calorías consumidas: {m.get('prom_cal', 0)} kcal/día (Rango saludable: {m.get('cal_min', 0)} - {m.get('cal_max', 0)} kcal)\n"
                                f"- Proteínas: {m.get('prom_prot', 0)} g/día (Rango saludable: {m.get('prot_min', 0)} - {m.get('prot_max', 0)} g)\n"
                                f"- Grasas: {m.get('prom_gras', 0)} g/día (Rango saludable: {m.get('gras_min', 0)} - {m.get('gras_max', 0)} g)\n"
                                f"- Carbohidratos: {m.get('prom_carb', 0)} g/día (Rango saludable: {m.get('carb_min', 0)} - {m.get('carb_max', 0)} g)\n"
                                f"- Fibra: {m.get('prom_fibr', 0)} g/día (Mínimo recomendado: {m.get('fibr_min', 0)} g)\n\n"
                                f"INSTRUCCIONES CLAVE:\n"
                                f"1. Si un valor se encuentra dentro del rango saludable, considéralo un comportamiento correcto y equilibrado; no lo señales como un error.\n"
                                f"2. Ten en cuenta que si el usuario está en proceso de descenso de peso, un consumo calórico dentro del rango inferior es correcto y esperado.\n"
                                f"3. Proporciona una devolución clara, motivadora y recomendaciones breves y prácticas para optimizar los hábitos en la semana entrante."
                            )

                            recomendacion = await obtener_recomendacion_ia(prompt_semana, es_semanal=True)

                            txt_ia = (
                                f"🤖 **Evaluación y Recomendaciones del Especialista:**\n"
                                f"{recomendacion}"
                            )

                            await context.bot.send_message(chat_id=int(user_id), text=txt_ia, parse_mode="Markdown")
                            logger.info(f"Resumen semanal y recomendación con IA enviados exitosamente a {user_id}")

                            if index < len(registros_usuarios) - 1:
                                await asyncio.sleep(60)

                    except Exception as e_ia:
                        logger.error(f"Error generando resumen semanal con IA para {user_id}: {e_ia}")
                else:
                    faltas_str = ", ".join(dias_faltantes_detalle) if dias_faltantes_detalle else "días de la semana pasada"
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=(
                            f"⚠️ **No se pudo emitir el resumen semanal**\n\n"
                            f"Motivo: Faltó registrar las ingestas correspondientes (se requieren al menos 2 comidas diarias con al menos una principal: Almuerzo o Cena) o el peso mensual obligatorio. "
                            f"Se detectaron registros insuficientes en los siguientes días: `{faltas_str}`.\n"
                            f"Ingresá tus comidas pendientes para retomar la normalidad en los próximos reportes."
                        ),
                        parse_mode="Markdown"
                    )

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
                mensaje_recordatorio = (
                    f"📌 **Recordatorio de comidas pendientes:**\n"
                    f"{lista_formateada}\n\n"
                    f"Si ya las consumiste, podés registrarlas en cualquier momento."
                )
                await context.bot.send_message(
                    chat_id=int(user_id), 
                    text=mensaje_recordatorio, 
                    parse_mode="Markdown"
                )
                logger.info(f"Recordatorio de comidas ({momento}) enviado a {user_id}")

        except Exception as e:
            logger.error(f"Error procesando usuario {user_id}: {e}")
                                 

# =============================================================================================================================================
#                    FINAL                                    COMANDOS INFORMES                                        FINAL
# =============================================================================================================================================

# =====================================================================================================================================
#                       INICIO                  COMANDOS INGRESOS                            INICIO
# ======================================================================================================================================

#                                   INICIO                  COMANDO ALTA DE USUARIO                                 INICIO
# ======================================================================================================================================

async def obtener_idiomas_disponibles_db():
    """Consulta dinámicamente las columnas de la tabla 'multi' en Supabase para ver qué idiomas están disponibles."""
    idiomas = ['en'] # Fallback base
    try:
        conn, cur = _asegurar_tabla_y_conectar("multi", tipo_tabla="comidas_precargadas")
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
              AND LOWER(table_name) = 'multi'
              AND LOWER(column_name) NOT IN ('id', 'variables')
        """)
        filas = cur.fetchall()
        cur.close()
        conn.close()
        if filas:
            idiomas = [str(f[0]).strip().lower() for f in filas if f[0]]
    except Exception as e:
        logger.error(f"Error al obtener idiomas disponibles de Supabase: {e}")
    return idiomas

async def cmd_ingreso_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Detección dinámica de idioma contra la base de datos
    tg_lang = update.effective_user.language_code # Ej: 'es-AR', 'pt-BR', 'en-US'
    idioma_detectado = 'en' # Por defecto si no coincide o no viene definido
    
    if tg_lang:
        codigo_base = tg_lang.split('-')[0].lower() # Extrae 'es', 'en', etc.
        idiomas_bd = await obtener_idiomas_disponibles_db()
        if codigo_base in idiomas_bd:
            idioma_detectado = codigo_base
            
    context.user_data['ing_idioma'] = idioma_detectado
    traducciones = obtener_traducciones_db(idioma_detectado) if 'obtener_traducciones_db' in globals() else {}

    estado_usr = _verificar_estado_usuario_en_hoja(user_id)
    
    if estado_usr is not None:
        estado_lower = estado_usr.lower()
        if estado_lower in ['inactivo', 'bloqueado', 'no', 'false', '0']:
            txt_bloq = traducciones.get('ing_error_usuario_deshabilitado', "❌ **Su usuario ha sido deshabilitado, contáctese con el administrador del bot.**")
            await update.message.reply_text(txt_bloq, parse_mode="Markdown")
            return ConversationHandler.END
        else:
            perfil_existente = obtener_perfil_usuario(user_id) if 'obtener_perfil_usuario' in globals() else {}
            nombre_usr = perfil_existente.get('nombre', 'Usuario') if perfil_existente else 'Usuario'
            txt_activo = traducciones.get('ing_cuenta_activa_aviso', 
                "ℹ️ **¡Ya tenés una cuenta activa, {nombre_usr}!**\n\n"
                "Tu ficha ya está registrada en el sistema con el ID `{user_id}`.\n"
                "Podés consultar o actualizar tu información en cualquier momento con el comando `/perfil`."
            ).format(nombre_usr=nombre_usr, user_id=user_id)
            await update.message.reply_text(txt_activo, parse_mode="Markdown")
            return ConversationHandler.END

    texto_advertencia = traducciones.get('ing_advertencia_legal', 
        "⚖️ **ADVERTENCIA LEGAL Y CONDICIONES DE USO**\n\n"
        "Este asistente es una herramienta de cálculo automatizado orientada a sumar y restar calorías, "
        "registrar ingestas y macronutrientes de forma práctica. **No posee un valor médico ni científico:** "
        "las recomendaciones emitidas son generadas por una Inteligencia Artificial de carácter generalizado.\n\n"
        "Todo seguimiento clínico o nutricional formal debe ser realizado exclusivamente por un profesional de la salud competente. "
        "Si decidís utilizar el bot de forma independiente, debés comprender que su función se limita estrictamente al balance cuantitativo "
        "de calorías y nutrientes, sin reemplazar la consulta médica.\n\n"
        "👉 *Para continuar con la apertura de tu cuenta y aceptar los términos, por favor presioná el botón de abajo:*"
    )

    btn_terminos_text = traducciones.get('btn_aceptar_terminos', "✅ He leído y acepto los términos")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_terminos_text, callback_data="aceptar_terminos_ok")]
    ])

    await update.message.reply_text(texto_advertencia, reply_markup=keyboard, parse_mode="Markdown")
    return ING_TERMINOS

def cmd_nueva_cuenta(datos_usuario):
    """
    Crea o actualiza el registro del usuario exclusivamente en Supabase.
    Estructura optimizada: la altura y ocupación se guardan dinámicamente en Perfil_<user_id>.
    """
    user_id = datos_usuario.get("user_id")
    nombre = datos_usuario.get("nombre")
    edad = int(datos_usuario.get("edad", 0))
    sexo = datos_usuario.get("sexo", "M")
    altura = float(datos_usuario.get("altura", 0))
    peso = float(datos_usuario.get("peso", 0))
    muneca = float(datos_usuario.get("muneca", 0))
    ocupacion = int(datos_usuario.get("ocupacion", 1375))
    cumple = datos_usuario.get("cumple", "")
    profesional = datos_usuario.get("profesional", "")

    mes_actual = datetime.now(ARG_TZ).strftime("%Y-%m")
    fecha_act = datetime.now(ARG_TZ).strftime("%Y-%m-%d")
    fecha_alta = datetime.now(ARG_TZ).strftime("%Y-%m-%d")

    # 1. Guardar perfil inicial en la tabla Perfil_<user_id> de Supabase (con peso, altura y ocupación evolutiva)
    try:
        tabla_perfil = f"Perfil_{user_id}"
        conn_p, cur_p = _asegurar_tabla_y_conectar(tabla_perfil, tipo_tabla="perfil")
        cur_p.execute(f"""
            INSERT INTO "{tabla_perfil}" ("EDAD", "PESO", "ALTURA", "GENERO", "ocupacion", "MES", "Fecha_Actualizacion", "Cumple")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            str(edad),
            peso,
            altura,
            str(sexo),
            float(ocupacion),
            str(mes_actual),
            str(fecha_act),
            str(cumple)
        ))
        conn_p.commit()
        cur_p.close()
        conn_p.close()
    except Exception as e:
        logger.error(f"Error al guardar perfil inicial en Supabase para {user_id}: {e}")

    # 2. Insertar o actualizar registro en la tabla maestra 'Usuarios' de Supabase (sin redundancias de altura/ocupación)
    try:
        conn_u, cur_u = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        query_usr = """
            INSERT INTO "Usuarios" ("User ID", "Nombre", "Estado", "Ultimo Mes Peso", "Notificaciones", "Fecha Alta", "Sexo", "muneca", "cumple", "profesional")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT ("User ID") DO UPDATE SET
                "Nombre" = EXCLUDED."Nombre",
                "Estado" = EXCLUDED."Estado",
                "Ultimo Mes Peso" = EXCLUDED."Ultimo Mes Peso",
                "Notificaciones" = EXCLUDED."Notificaciones",
                "Sexo" = EXCLUDED."Sexo",
                "muneca" = EXCLUDED."muneca",
                "cumple" = EXCLUDED."cumple",
                "profesional" = EXCLUDED."profesional"
        """
        valores_usr = (
            str(user_id),
            str(nombre),
            0,
            str(mes_actual),
            "Si",
            str(fecha_alta),
            str(sexo),
            float(muneca),
            str(cumple),
            str(profesional)
        )
        cur_u.execute(query_usr, valores_usr)
        conn_u.commit()
        cur_u.close()
        conn_u.close()
    except Exception as e:
        logger.error(f"Error al insertar en la tabla maestra 'Usuarios' de Supabase para el usuario {user_id}: {e}")
                            
def _verificar_estado_usuario_en_hoja(user_id):
    """Verifica si el usuario existe en Supabase y devuelve su estado o None."""
    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        query = 'SELECT "User ID", "Estado" FROM "Usuarios"'
        cur.execute(query)
        filas = cur.fetchall()
        cur.close()
        conn.close()
        
        for fila in filas:
            raw_id = fila[0]
            if raw_id and str(raw_id).split('.')[0].strip() == str(user_id).strip():
                estado_val = fila[1]
                return str(estado_val if estado_val is not None else "0").strip()
    except Exception as e:
        logger.error(f"Error al verificar estado de usuario en Supabase: {e}")
    return None
    
def _verificar_profesional_valido(prof_id_str):
    """Verifica si el ID del profesional existe en la tabla 'Profesionales' de Supabase."""
    try:
        conn, cur = _asegurar_tabla_y_conectar("Profesionales", tipo_tabla="profesionales")
        query = 'SELECT "User ID" FROM "Profesionales"'
        cur.execute(query)
        filas = cur.fetchall()
        cur.close()
        conn.close()
        
        for fila in filas:
            id_p = str(fila[0] or "").split('.')[0].strip()
            if id_p == str(prof_id_str).strip():
                return True
    except Exception as e:
        logger.error(f"Error al verificar profesionales en Supabase: {e}")
    return False

async def ing_aceptar_terminos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = context.user_data.get('ing_idioma', 'en')
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    if query.data == "aceptar_terminos_ok":
        txt_terminos_ok = traducciones.get('ing_terminos_aceptados_msg', 
            "✅ **Términos aceptados correctamente.**\n\n"
            "🔑 **Apertura de Ficha - Validación de Profesional**\n\n"
            "Para comenzar el registro, por favor ingresá el **ID de Telegram del profesional**:"
        )
        await query.edit_message_text(txt_terminos_ok, parse_mode="Markdown")
        return ING_PROFESIONAL
    return ING_TERMINOS

async def cmd_nuevo_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await cmd_ingreso_start(update, context)

async def ing_recibir_profesional(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prof_id = update.message.text.strip()
    lang = context.user_data.get('ing_idioma', 'en')
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
    loop = asyncio.get_running_loop()
    es_valido = await loop.run_in_executor(None, _verificar_profesional_valido, prof_id)
    
    if not es_valido:
        txt_err_prof = traducciones.get('ing_error_profesional_invalido', 
            "⚠️ **ID de profesional no válido**\n\n"
            "El número ingresado no figura en la lista de profesionales autorizados. "
            "Por favor, verificá el ID con tu profesional e intentalo nuevamente o escribí `/cancelar`."
        )
        await update.message.reply_text(txt_err_prof, parse_mode="Markdown")
        return ING_PROFESIONAL

    context.user_data['ing_profesional'] = prof_id
    txt_solic_nombre = traducciones.get('ing_solicitar_nombre', 
        "✅ **Profesional verificado correctamente.**\n\n"
        "📝 **Apertura de Ficha Nutricional**\n"
        "Por favor, indicá tu **Nombre y Apellido / Apodo**:"
    )
    await update.message.reply_text(txt_solic_nombre, parse_mode="Markdown")
    return ING_NOMBRE

async def ing_recibir_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.text.strip()
    lang = context.user_data.get('ing_idioma', 'en')
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    if len(nombre) < 2:
        txt_err_nom = traducciones.get('ing_error_nombre_valido', "⚠️ Por favor, ingresá un nombre válido.")
        await update.message.reply_text(txt_err_nom)
        return ING_NOMBRE
    
    context.user_data['ing_nombre'] = nombre
    txt_solic_edad = traducciones.get('ing_solicitar_edad', "Ingresá tu **edad** en años (ejemplo: `35`):")
    await update.message.reply_text(txt_solic_edad, parse_mode="Markdown")
    return ING_EDAD

async def ing_recibir_edad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    lang = context.user_data.get('ing_idioma', 'en')
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    if not txt.isdigit() or not (10 <= int(txt) <= 110):
        txt_err_edad = traducciones.get('ing_error_edad_valida', "⚠️ Por favor, ingresá una edad válida en números (ejemplo: `35`).")
        await update.message.reply_text(txt_err_edad)
        return ING_EDAD
    
    context.user_data['ing_edad'] = int(txt)
    
    btn_masc = traducciones.get('btn_sexo_masculino', "Masculino 👨")
    btn_fem = traducciones.get('btn_sexo_femenino', "Femenino 👩")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_masc, callback_data="sexo_M"),
         InlineKeyboardButton(btn_fem, callback_data="sexo_F")]
    ])
    txt_solic_sexo = traducciones.get('ing_solicitar_sexo', "Seleccioná tu **sexo biológico**:")
    await update.message.reply_text(txt_solic_sexo, reply_markup=keyboard, parse_mode="Markdown")
    return ING_SEXO

async def ing_recibir_sexo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get('ing_idioma', 'en')
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
    sexo = "M" if query.data == "sexo_M" else "F"
    context.user_data['ing_sexo'] = sexo
    
    sexo_str_label = traducciones.get('label_masculino', 'Masculino') if sexo == 'M' else traducciones.get('label_femenino', 'Femenino')
    txt_sexo_reg = traducciones.get('ing_sexo_registrado', 
        "Sexo registrado: *{sexo_label}*.\n\n"
        "Ahora ingresá tu **altura en centímetros** (ejemplo: `175` para 1,75 m):"
    ).format(sexo_label=sexo_str_label)

    await query.edit_message_text(txt_sexo_reg, parse_mode="Markdown")
    return ING_ALTURA

async def ing_recibir_altura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().replace(',', '.')
    lang = context.user_data.get('ing_idioma', 'en')
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    try:
        alt = float(txt)
        if not (100 <= alt <= 230): raise ValueError()
    except ValueError:
        txt_err_alt = traducciones.get('ing_error_altura_valida', "⚠️ Ingresá una altura válida en centímetros (ejemplo: `170`).")
        await update.message.reply_text(txt_err_alt)
        return ING_ALTURA

    context.user_data['ing_altura'] = alt
    txt_solic_peso = traducciones.get('ing_solicitar_peso', "Ingresá tu **peso actual en kg** (ejemplo: `82.5`):")
    await update.message.reply_text(txt_solic_peso, parse_mode="Markdown")
    return ING_PESO

async def ing_recibir_peso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().replace(',', '.')
    lang = context.user_data.get('ing_idioma', 'en')
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    try:
        peso = float(txt)
        if not (30 <= peso <= 300): raise ValueError()
    except ValueError:
        txt_err_peso = traducciones.get('ing_error_peso_valido', "⚠️ Ingresá un peso válido en kg (ejemplo: `75.4`).")
        await update.message.reply_text(txt_err_peso)
        return ING_PESO

    context.user_data['ing_peso'] = peso
    txt_solic_cintura = traducciones.get('ing_solicitar_cintura', 
        "Ingresá el **perímetro de tu cintura en cm** (ejemplo: `85`):\n"
        "_(Se utiliza junto con el cuello para calcular tu porcentaje de grasa)_"
    )
    await update.message.reply_text(txt_solic_cintura, parse_mode="Markdown")
    return ING_MUNECA

async def ing_recibir_muneca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().replace(',', '.')
    lang = context.user_data.get('ing_idioma', 'en')
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    try:
        cintura = float(txt)
        if not (50 <= cintura <= 200): raise ValueError()
    except ValueError:
        txt_err_cintura = traducciones.get('ing_error_cintura_valida', "⚠️ Ingresá un perímetro de cintura válido en cm (ejemplo: `85`).")
        await update.message.reply_text(txt_err_cintura, parse_mode="Markdown")
        return ING_MUNECA

    context.user_data['ing_cintura'] = cintura
    txt_solic_cuello = traducciones.get('ing_solicitar_cuello', 
        "Ingresá el **perímetro de tu cuello en cm** (ejemplo: `38`):\n"
        "_(Se utiliza junto con la cintura para calcular tu composición corporal)_"
    )
    await update.message.reply_text(txt_solic_cuello, parse_mode="Markdown")
    return ING_CUELLO

async def ing_recibir_cuello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().replace(',', '.')
    lang = context.user_data.get('ing_idioma', 'en')
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    try:
        cuello = float(txt)
        if not (20 <= cuello <= 60): raise ValueError()
    except ValueError:
        txt_err_cuello = traducciones.get('ing_error_cuello_valido', "⚠️ Ingresá un perímetro de cuello válido en cm (ejemplo: `38`).")
        await update.message.reply_text(txt_err_cuello, parse_mode="Markdown")
        return ING_CUELLO

    context.user_data['ing_cuello'] = cuello
    
    btn_ocup_1 = traducciones.get('btn_ocup_nivel_1', "🪑 Nivel 1")
    btn_ocup_2 = traducciones.get('btn_ocup_nivel_2', "🚶 Nivel 2")
    btn_ocup_3 = traducciones.get('btn_ocup_nivel_3', "🏃 Nivel 3")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_ocup_1, callback_data="ocup_1375")],
        [InlineKeyboardButton(btn_ocup_2, callback_data="ocup_1550")],
        [InlineKeyboardButton(btn_ocup_3, callback_data="ocup_1725")]
    ])
    
    texto_explicativo = traducciones.get('ing_texto_explicativo_ocupacion', 
        "Seleccioná tu **nivel de actividad u ocupación habitual** (sin considerar los ejercicios programados):\n\n"
        "• **Nivel 1 (🪑):** Actividad ligera / sedentario (persona sentada, oficina).\n"
        "• **Nivel 2 (🚶):** Actividad moderada (persona caminando, movimiento constante).\n"
        "• **Nivel 3 (🏃):** Actividad intensa (esfuerzo físico exigente)."
    )
    
    await update.message.reply_text(texto_explicativo, reply_markup=keyboard, parse_mode="Markdown")
    return ING_OCUPACION
        
async def ing_recibir_ocupacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get('ing_idioma', 'en')
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
    val_str = query.data.replace("ocup_", "")
    try:
        ocupacion = int(val_str)
    except ValueError:
        ocupacion = 1375
        
    context.user_data['ing_ocupacion'] = ocupacion
    
    txt_ocup_reg = traducciones.get('ing_ocupacion_registrada', 
        "Nivel de actividad registrado: {ocupacion}.\n\n"
        "Por último, ingresá tu **fecha de nacimiento** en formato `AAAA-MM-DD` (ejemplo: `1985-04-12`):"
    ).format(ocupacion=ocupacion)

    await query.edit_message_text(txt_ocup_reg, parse_mode="Markdown")
    return ING_CUMPLE

def clasificar_brecha_peso(peso_actual: float, peso_ideal: float) -> tuple[str, float, bool]:
    """
    Calcula la diferencia porcentual entre el peso actual y el peso ideal.
    Retorna: (nivel_desvio, porcentaje_diferencia, es_sobrepeso)
    Niveles: 'bajo', 'moderado', 'elevado'
    """
    if peso_ideal <= 0:
        return "moderado", 0.0, True

    diferencia_kg = peso_actual - peso_ideal
    es_sobrepeso = diferencia_kg >= 0
    porcentaje_dif = (abs(diferencia_kg) / peso_ideal) * 100

    if porcentaje_dif <= 15.0:
        nivel = "bajo"
    elif porcentaje_dif <= 30.0:
        nivel = "moderado"
    else:
        nivel = "elevado"

    return nivel, round(porcentaje_dif, 1), es_sobrepeso

def obtener_texto_evaluacion_ritmo(nivel: str, es_sobrepeso: bool, traducciones: dict) -> str:
    """
    Genera el mensaje descriptivo del nivel de desvío y la recomendación de ritmo 
    utilizando estrictamente variables multilenguaje.
    """
    if es_sobrepeso:
        if nivel == "bajo":
            desc_nivel = traducciones.get('eval_sobrepeso_bajo', "tu nivel de sobrepeso es bajo (estás muy cerca de tu meta)")
        elif nivel == "moderado":
            desc_nivel = traducciones.get('eval_sobrepeso_moderado', "tu nivel de sobrepeso es moderado")
        else:
            desc_nivel = traducciones.get('eval_sobrepeso_elevado', "tu nivel de sobrepeso es elevado")
    else:
        if nivel == "bajo":
            desc_nivel = traducciones.get('eval_deficit_bajo', "tu margen por debajo del peso de referencia es leve")
        elif nivel == "moderado":
            desc_nivel = traducciones.get('eval_deficit_moderado', "tu diferencia respecto al peso de referencia es moderada")
        else:
            desc_nivel = traducciones.get('eval_deficit_elevado', "tu diferencia respecto al peso de referencia es considerable")

    if nivel == "elevado":
        sugerencia = traducciones.get('sugerencia_ritmo_intenso', "💡 *Sugerencia basada en tus métricas:* Te recomendamos un ritmo **Intenso / Rápido** para un avance firme en esta etapa inicial.")
    elif nivel == "moderado":
        sugerencia = traducciones.get('sugerencia_ritmo_moderado', "💡 *Sugerencia basada en tus métricas:* Te recomendamos un ritmo **Moderado** (el más equilibrado y constante).")
    else:
        sugerencia = traducciones.get('sugerencia_ritmo_tranquilo', "💡 *Sugerencia basada en tus métricas:* Te recomendamos un ritmo **Tranquilo / Lento**, ideal para consolidar los últimos ajustes de forma sostenible.")

    titulo_eval = traducciones.get('titulo_evaluacion_corporal', "📊 Analizando tus perímetros corporales (cintura y cuello), detectamos que {desc_nivel}.")
    pregunta_ritmo = traducciones.get('pregunta_eleccion_ritmo', "Para organizar tu etapa de trabajo de manera realista y saludable, ¿qué ritmo preferís aplicar?")

    return (
        f"{titulo_eval.format(desc_nivel=desc_nivel)}\n\n"
        f"{sugerencia}\n\n"
        f"{pregunta_ritmo}"
    )

async def ing_recibir_cumple(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cumple_str = update.message.text.strip()
    user_id = update.effective_user.id
    lang = context.user_data.get('ing_idioma', 'en')
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    try:
        datetime.strptime(cumple_str, "%Y-%m-%d")
    except ValueError:
        txt_err_fec = traducciones.get('ing_error_fecha_invalida', "⚠️ Formato de fecha inválido. Usá el formato `AAAA-MM-DD` (ejemplo: `1990-08-25`).")
        await update.message.reply_text(txt_err_fec, parse_mode="Markdown")
        return ING_CUMPLE

    context.user_data['ing_datos_usuario_temp'] = {
        "user_id": user_id,
        "nombre": context.user_data.get('ing_nombre'),
        "edad": context.user_data.get('ing_edad'),
        "sexo": context.user_data.get('ing_sexo'),
        "altura": context.user_data.get('ing_altura'),
        "peso": context.user_data.get('ing_peso'),
        "muneca": context.user_data.get('ing_cintura'),
        "ocupacion": context.user_data.get('ing_ocupacion'),
        "cumple": cumple_str,
        "profesional": context.user_data.get('ing_profesional')
    }

    datos_temp = context.user_data['ing_datos_usuario_temp']
    peso_ideal_calc = round(calcular_peso_ideal(datos_temp["sexo"], datos_temp["altura"]), 1)
    nivel, porcentaje, es_sobrepeso = clasificar_brecha_peso(datos_temp["peso"], peso_ideal_calc)
    
    texto_evaluacion = obtener_texto_evaluacion_ritmo(nivel, es_sobrepeso, traducciones)

    btn_tranquilo = traducciones.get('btn_ritmo_tranquilo', "🟢 Tranquilo / Lento")
    btn_moderado = traducciones.get('btn_ritmo_moderado', "🟡 Moderado")
    btn_intenso = traducciones.get('btn_ritmo_intenso', "🔴 Intenso / Rápido")

    keyboard = [
        [InlineKeyboardButton(btn_tranquilo, callback_data="ritmo_tranquilo")],
        [InlineKeyboardButton(btn_moderado, callback_data="ritmo_moderado")],
        [InlineKeyboardButton(btn_intenso, callback_data="ritmo_intenso")]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    txt_exito_cumple = traducciones.get('ing_fecha_registrada_exito', "✅ **¡Fecha registrada con éxito!**\n\n{texto_evaluacion}").format(texto_evaluacion=texto_evaluacion)

    await update.message.reply_text(
        txt_exito_cumple,
        reply_markup=markup,
        parse_mode="Markdown"
    )
    
    return ING_RITMO

async def ing_recibir_ritmo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    lang = context.user_data.get('ing_idioma', 'en')
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    ritmo_seleccionado = query.data.replace("ritmo_", "")

    datos_usuario = context.user_data.get('ing_datos_usuario_temp', {})
    if not datos_usuario:
        txt_err_temp = traducciones.get('ing_error_datos_temp', "❌ Hubo un error en los datos temporales. Por favor, iniciá el registro nuevamente con `/ingreso`.")
        await query.edit_message_text(txt_err_temp)
        context.user_data.clear()
        return ConversationHandler.END

    datos_usuario["ritmo"] = ritmo_seleccionado
    datos_usuario["contextura"] = calcular_contextura(datos_usuario["sexo"], datos_usuario["altura"], datos_usuario["muneca"])
    datos_usuario["peso_ideal"] = round(calcular_peso_ideal(datos_usuario["sexo"], datos_usuario["altura"]), 1)
    datos_usuario["peso_etapa"] = calcular_peso_etapa(datos_usuario["peso"], datos_usuario["peso_ideal"])
    
    genero_str = "femenino" if str(datos_usuario["sexo"]).upper() in ["F", "FEMENINO", "MUJER"] else "masculino"
    tmb, get_calorias = calcular_tmb_y_get(
        peso_actual=datos_usuario["peso"], 
        altura_cm=datos_usuario["altura"], 
        edad=datos_usuario["edad"], 
        genero=genero_str, 
        actividad=datos_usuario["ocupacion"], 
        peso_ideal=datos_usuario["peso_ideal"]
    )
    datos_usuario["tmb"] = tmb
    datos_usuario["get"] = get_calorias
    
    txt_procesando = traducciones.get('ing_procesando_informe_ia', "✅ Ritmo seleccionado: *{ritmo_cap}*.\n\n⏳ *Creando planillas y redactando tu informe inicial personalizado con IA...*").format(ritmo_cap=ritmo_seleccionado.capitalize())

    await query.edit_message_text(
        txt_procesando,
        parse_mode="Markdown"
    )

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, cmd_nueva_cuenta, datos_usuario)

        _, pdf_buf = await procesar_informe_inicial_ia(datos_usuario)

        resumen_plantilla = traducciones.get('ing_resumen_cuenta_lista', 
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
            ritmo_cap=ritmo_seleccionado.capitalize(),
            tmb_rnd=round(tmb),
            get_rnd=round(get_calorias)
        )

        await query.message.reply_text(resumen_plantilla, parse_mode="Markdown")

        filename_pdf = f"Informe_Inicial_{datos_usuario['nombre'].replace(' ', '_')}.pdf"
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=pdf_buf,
            filename=filename_pdf
        )

    except Exception as e:
        logger.error(f"Error al inicializar cuenta o generar informe para {user_id}: {e}")
        txt_err_gen = traducciones.get('ing_error_proceso_general', "❌ Ocurrió un error al procesar el ingreso: {e}").format(e=e)
        await query.message.reply_text(txt_err_gen)

    context.user_data.clear()
    return ConversationHandler.END

#                     INICIO                         COMANDO START                          INICIO  2026 09 05
# =========================================================================================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    msg = traducciones.get('start_mensaje_bienvenida', 
        "👋 **¡Bienvenido a tu Bot Nutricional Personalizado!**\n\n"
        "Guía rápida de comandos e ingresos disponibles:\n\n"
        "📌 **Comandos Principales:**\n"
        "• `/alta`: Apertura de cuenta ingresando los datos.\n"
        "• `/barra`: Ingresa por código de barras un comestible.\n"
        "• `/borracomida`: Borra una comida de la Planilla.\n"
        "• `/comidas`: Planilla de comidas precargadas y PDF.\n"
        "• `/dia`: Ingestas del día, detalle nutricional y PDF.\n"
        "• `/eliminar`: Borra ingestas y actividades.\n"
        "• `/GET`: Actualiza GET por medio del reloj inteligente.\n"
        "• `/inicio`: Resumen de comandos y PDF del manual.\n"
        "• `/mes`: Reporte con estimación de peso y PDF.\n"
        "• `/perfil`: Actualizar de datos biométricos.\n"
        "• `/presi`: Registro y consulta de presión arterial.\n"
        "• `/receta`: Calculadora Web para registrar comidas.\n"
        "• `/semana`: Estadística semanal (calorías, fibras, etc.).\n\n"
        "📌 **Métodos de Registro:**\n"
        "• **Ingestas con IA:** 📝 Texto, 🎤 Notas de voz, 📸 Fotos.\n"
        "• **Modificación parcial:** por item \n"
        "    `DESCRIPCION` manteniendo el peso recalcula IA.\n"
        "    `DESCRIPCION,PESO` recalculo total por IA.\n"
        "    `,PESO` recalculo sin intervencion de IA\n"
        "• **Ingestas sin IA:** 📝 Comidas precargadas en planilla:\n"
        "    `*DESAYUNO`: menú completo\n"
        "    `*PIZZA (porción),4`: 4 porciones de pizza\n"
        "    `*TORTA (fracción x 100g),1.5`: 150 g de torta\n"
        "• **Actividad fisica con IA:** 📝 Texto, 🎤 Notas de voz.\n"
        "• **Modificación :** ingresar el nuevo valor de calorias\n\n"
        "📄 *A continuación te comparto el manual en PDF.*"
    )
    
    await update.message.reply_text(msg, parse_mode="Markdown")
    
    pdf_buf = generar_pdf_instrucciones_bytes(traducciones)
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=pdf_buf,
        filename="Manual_Bot_Nutricional.pdf"
    )    
 
def generar_pdf_instrucciones_bytes(traducciones: dict) -> io.BytesIO:
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
    
    PRIMARY = colors.HexColor('#1E293B')
    SECONDARY = colors.HexColor('#2563EB')
    TEXT_MAIN = colors.HexColor('#334155')
    BG_LIGHT = colors.HexColor('#F8FAFC')
    BG_CARD = colors.HexColor('#F1F5F9')
    BORDER_COLOR = colors.HexColor('#E2E8F0')

    title_style = ParagraphStyle(
        'DocTitle', parent=styles['Heading1'], 
        fontSize=18, leading=22, textColor=PRIMARY, fontName='Helvetica-Bold', spaceAfter=2
    )
    subtitle_style = ParagraphStyle(
        'DocSubTitle', parent=styles['Normal'], 
        fontSize=9.5, leading=12, textColor=SECONDARY, fontName='Helvetica-Bold', spaceAfter=8
    )
    section_style = ParagraphStyle(
        'DocSection', parent=styles['Heading2'], 
        fontSize=12, leading=15, textColor=PRIMARY, fontName='Helvetica-Bold', spaceBefore=4, spaceAfter=6
    )
    subsection_style = ParagraphStyle(
        'DocSubSection', parent=styles['Heading3'], 
        fontSize=9.5, leading=12, textColor=SECONDARY, fontName='Helvetica-Bold', spaceBefore=3, spaceAfter=2
    )
    
    body_style = ParagraphStyle(
        'DocBody', parent=styles['Normal'], 
        fontSize=9.5, leading=12, textColor=TEXT_MAIN, fontName='Helvetica'
    )
    body_bold = ParagraphStyle(
        'DocBodyBold', parent=body_style, fontName='Helvetica-Bold'
    )
    code_style = ParagraphStyle(
        'DocCode', parent=styles['Normal'], 
        fontSize=10, leading=13, textColor=PRIMARY, fontName='Courier-Bold'
    )
    body_bold_white = ParagraphStyle(
        'DocBodyBoldWhite', parent=styles['Normal'], 
        fontSize=9.5, leading=12, textColor=colors.white, fontName='Helvetica-Bold'
    )

    story = []

    def crear_encabezado():
        header_content = [
            [Paragraph(traducciones.get('pdf_titulo_principal', "GUÍA INTERACTIVA DEL BOT NUTRICIONAL"), title_style)],
            [Paragraph(traducciones.get('pdf_subtitulo_principal', "MANUAL INTEGRAL DE USUARIO • ASISTENTE PERSONAL INTELIGENTE"), subtitle_style)]
        ]
        t_header = Table(header_content, colWidths=[540])
        t_header.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('LINEBELOW', (0,1), (-1,1), 2, SECONDARY),
        ]))
        return t_header

    story.append(crear_encabezado())
    story.append(Spacer(1, 4))
    story.append(Paragraph(traducciones.get('pdf_sec_alta', "1. Alta al Sistema y Registro Inicial"), section_style))
    
    alta_data = [
        [Paragraph(traducciones.get('pdf_col_comando', "Comando / Campo"), body_bold_white), Paragraph(traducciones.get('pdf_col_descripcion', "Descripción Detallada y Formato de Uso"), body_bold_white)],
        [Paragraph("<b>/alta</b>", code_style), Paragraph(traducciones.get('pdf_desc_alta', "<b>Comando de Inicio de Registro:</b> Permite iniciar el proceso de apertura de cuenta y creación de ficha nutricional."), body_style)],
        [Paragraph(traducciones.get('pdf_lbl_prof', "<b>ID de Profesional</b>"), code_style), Paragraph(traducciones.get('pdf_desc_prof', "<b>Validación del Profesional:</b> Ingresar el ID de Telegram del profesional autorizado para asociar y validar la cuenta."), body_style)],
        [Paragraph(traducciones.get('pdf_lbl_nombre', "<b>Nombre y Apellido</b>"), code_style), Paragraph(traducciones.get('pdf_desc_nombre', "<b>Identificación:</b> Ingresar el nombre o apodo con el que figurará el paciente en el sistema (mínimo 2 caracteres)."), body_style)],
        [Paragraph(traducciones.get('pdf_lbl_edad', "<b>Edad</b>"), code_style), Paragraph(traducciones.get('pdf_desc_edad', "<b>Edad en años:</b> Ingresar un valor numérico válido entre 10 y 110 años."), body_style)],
        [Paragraph(traducciones.get('pdf_lbl_sexo', "<b>Sexo Biológico</b>"), code_style), Paragraph(traducciones.get('pdf_desc_sexo', "<b>Selección por Botón:</b> Elegir entre Masculino (M) o Femenino (F) mediante el teclado interactivo."), body_style)],
        [Paragraph(traducciones.get('pdf_lbl_altura', "<b>Altura</b>"), code_style), Paragraph(traducciones.get('pdf_desc_altura', "<b>Estatura en centímetros:</b> Ingresar altura en cm (ejemplo: <code>175</code> para 1,75 m, con un rango válido de 100 a 230 cm)."), body_style)],
        [Paragraph(traducciones.get('pdf_lbl_peso', "<b>Peso Actual</b>"), code_style), Paragraph(traducciones.get('pdf_desc_peso', "<b>Peso en kilogramos:</b> Ingresar el peso actual en kg (ejemplo: <code>82.5</code> kg, con un rango válido de 30 a 300 kg)."), body_style)],
        [Paragraph(traducciones.get('pdf_lbl_cintura', "<b>Cintura</b>"), code_style), Paragraph(traducciones.get('pdf_desc_cintura', "<b>Perímetro de la cintura:</b> Ingresar la medida en cm (ejemplo: <code>90</code> cm) para calcular la contextura corporal."), body_style)],
        [Paragraph(traducciones.get('pdf_lbl_cuello', "<b>Cuello</b>"), code_style), Paragraph(traducciones.get('pdf_desc_cuello', "<b>Perímetro del cuello:</b> Ingresar la medida en cm (ejemplo: <code>40</code> cm) para calcular la contextura corporal."), body_style)],
        [Paragraph(traducciones.get('pdf_lbl_ocupacion', "<b>Ocupación / Actividad</b>"), code_style), Paragraph(traducciones.get('pdf_desc_ocupacion', "<b>Nivel de Actividad:</b> Seleccionar mediante botones el nivel de actividad habitual (Sedentario/Ligero, Moderado o Intenso)."), body_style)],
        [Paragraph(traducciones.get('pdf_lbl_cumple', "<b>Fecha de Nacimiento</b>"), code_style), Paragraph(traducciones.get('pdf_desc_cumple', "<b>Cumpleaños:</b> Ingresar la fecha de nacimiento obligatoriamente en formato <code>AAAA-MM-DD</code> (ejemplo: <code>1985-04-12</code>)."), body_style)],
        [Paragraph(traducciones.get('pdf_lbl_intensidad', "<b>Intensidad</b>"), code_style), Paragraph(traducciones.get('pdf_desc_intensidad', "<b>Ritmo de avance:</b> Seleccionar el nivel de ritmo para la etapa (Tranquilo, Moderado o Intenso)."), body_style)],
        [Paragraph("<b>/cancelar</b>", code_style), Paragraph(traducciones.get('pdf_desc_cancelar', "<b>Cancelar Registro:</b> Permite abortar el proceso de alta en cualquier momento, limpiando los datos temporales."), body_style)]
    ]

    t_alta = Table(alta_data, colWidths=[130, 410])
    t_alta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT])
    ]))
    
    story.append(t_alta)
    story.append(PageBreak())

    story.append(crear_encabezado())
    story.append(Spacer(1, 4))
    story.append(Paragraph(traducciones.get('pdf_sec_metodos', "2. Métodos de Registro de Ingestas y Actividades"), section_style))

    story.append(Paragraph(traducciones.get('pdf_subsec_ia', "A. Con Intervención de IA (Texto, Voz e Imagen)"), subsection_style))
    
    registro_ia_data = [
        [Paragraph(traducciones.get('pdf_ia_texto', "<b>Texto Libre:</b> Escribí tus alimentos de forma natural detallando porciones. Detallá tu actividad física indicando tipo, duración e intensidad."), body_style)],
        [Paragraph(traducciones.get('pdf_ia_voz', "<b>Notas de Voz:</b> Dictá tu ingesta o actividad física en una nota de voz; la IA convertirá el audio a texto y procesará los datos nutricionales."), body_style)],
        [Paragraph(traducciones.get('pdf_ia_foto', "<b>Fotografías de Galería / Cámara:</b> Envía una foto del plato con o sin descripción aclaratoria."), body_style)],
        [Paragraph(traducciones.get('pdf_ia_edicion', "<b>Proceso de Edición y Confirmación de ingestas:</b><br/>• <b>Momento:</b> Desayuno, Almuerzo, Merienda o Cena.<br/>• <b>Edición parcial:</b> Seleccioná ítem por ítem enviando una <i>nueva descripción</i>, <i>,nuevo peso</i> o <i>nueva descripción,nuevo peso</i>.<br/>• <b>Fecha y Guardado:</b> Confirmá la fecha del consumo para asentar en tu planilla."), body_style)],
        [Paragraph(traducciones.get('pdf_ia_actividad', "<b>Proceso de Edición y Confirmación de actividades:</b><br/>• <b>Momento:</b> Actividad.<br/>• <b>Edición parcial:</b> Ingresar un nuevo valor de las calorías quemadas.<br/>• <b>Fecha y Guardado:</b> Confirmá para asentar en tu planilla."), body_style)]
    ]

    t_reg_ia = Table(registro_ia_data, colWidths=[540])
    t_reg_ia.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_reg_ia)
    story.append(Spacer(1, 4))

    story.append(Paragraph(traducciones.get('pdf_subsec_sin_ia', "B. Sin Intervención de IA (Comidas Precargadas)"), subsection_style))

    direct_data = [
        [Paragraph(traducciones.get('pdf_col_tipo_reg', "Tipo de Registro"), body_bold_white), Paragraph(traducciones.get('pdf_col_sintaxis', "Sintaxis"), body_bold_white), Paragraph(traducciones.get('pdf_col_ejemplos', "Ejemplos y Funcionamiento"), body_bold_white)],
        [
            Paragraph(traducciones.get('pdf_reg_plantilla', "<b>Plantilla de Comidas</b>"), body_style),
            Paragraph("<code>*CODIGO, CANTI</code>", code_style),
            Paragraph(traducciones.get('pdf_desc_plantilla', "• <code>*DESAYUNO,1</code> Ingresa 1 unidad.<br/>• <code>*PIZZA,4</code> Registra 4 porciones."), body_style)
        ],
        [
            Paragraph(traducciones.get('pdf_reg_barra', "<b>Código de barras</b>"), body_style),
            Paragraph("<code>/barra NUMERO</code>", code_style),
            Paragraph(traducciones.get('pdf_desc_barra', "• <code>/barra 7790742363107</code><br/>Ingresá el EAN del producto para consultar fracciones de 100 g."), body_style)
        ]
    ]

    t_direct = Table(direct_data, colWidths=[120, 130, 290])
    t_direct.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT])
    ]))
    story.append(t_direct)
    story.append(Spacer(1, 4))

    story.append(Paragraph(traducciones.get('pdf_sec_calc', "3. Calculadora Nutricional Web (/receta)"), section_style))
    story.append(Paragraph(traducciones.get('pdf_desc_calc', "Permite cargar recetas elaboradas o combinaciones de alimentos habituales directamente en tu planilla personal."), body_style))

    receta_data = [
        [
            Paragraph(traducciones.get('pdf_receta_ej1', "Ejemplo 1: Combinación (DESAYUNO)"), body_bold_white),
            Paragraph(traducciones.get('pdf_receta_ej2', "Ejemplo 2: Receta Elaborada (TORTA)"), body_bold_white)
        ],
        [
            Paragraph("• <b>Código:</b> <code>DESAYUNO</code><br/>• <b>Desc:</b> Desayuno tradicional.<br/>• <b>Criterio:</b> Porciones = 1.", body_style),
            Paragraph("• <b>Código:</b> <code>TORTA</code><br/>• <b>Desc:</b> Torta casera.<br/>• <b>Criterio:</b> Fracción de 100 g.", body_style)
        ]
    ]

    t_receta = Table(receta_data, colWidths=[270, 270])
    t_receta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('BACKGROUND', (0,1), (-1,1), BG_CARD),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR)
    ]))
    story.append(t_receta)
    story.append(PageBreak())

    story.append(crear_encabezado())
    story.append(Spacer(1, 4))
    story.append(Paragraph(traducciones.get('pdf_sec_cmds', "4. Comandos Principales del Sistema"), section_style))
    
    cmds_data = [
        [Paragraph(traducciones.get('pdf_col_cmd', "Comando"), body_bold_white), Paragraph(traducciones.get('pdf_col_desc_cmd', "Descripción Detallada y Formato de Uso"), body_bold_white)],
        [Paragraph("<b>/barra</b>", code_style), Paragraph(traducciones.get('pdf_cmd_barra', "<b>Código de barras:</b> Ingresa un código de barras y se presenta un comestible en fracciones de 100 g."), body_style)],
        [Paragraph("<b>/borracomida</b>", code_style), Paragraph(traducciones.get('pdf_cmd_borra', "<b>Borra una comida:</b> Permite la eliminación de una comida predeterminada."), body_style)],
        [Paragraph("<b>/comidas</b>", code_style), Paragraph(traducciones.get('pdf_cmd_comidas', "<b>Planilla de comidas:</b> Listado de comidas predeterminadas y descarga de PDF."), body_style)],
        [Paragraph("<b>/dia</b>", code_style), Paragraph(traducciones.get('pdf_cmd_dia', "<b>Resumen diario:</b> Muestra los consumos del día y descarga el PDF detallado."), body_style)],
        [Paragraph("<b>/eliminar</b>", code_style), Paragraph(traducciones.get('pdf_cmd_eliminar', "<b>Borrar registros:</b> Permite eliminar ingestas y actividades seleccionando el día."), body_style)],
        [Paragraph("<b>/GET</b>", code_style), Paragraph(traducciones.get('pdf_cmd_get', "<b>Gasto Energético Total:</b> Actualiza el GET mediante calorías base de 24 horas (ejemplo: <code>/GET 2150</code>)."), body_style)],
        [Paragraph("<b>/inicio</b>", code_style), Paragraph(traducciones.get('pdf_cmd_inicio', "<b>Guía principal:</b> Presenta la guía rápida de comandos e ingresos."), body_style)],
        [Paragraph("<b>/mes</b>", code_style), Paragraph(traducciones.get('pdf_cmd_mes', "<b>Resumen mensual:</b> Reporte mensual, calorías, estimación de peso y PDF completo."), body_style)],
        [Paragraph("<b>/perfil</b>", code_style), Paragraph(traducciones.get('pdf_cmd_perfil', "<b>Datos biométricos:</b> Muestra los datos corporales cargados en el sistema."), body_style)],
        [Paragraph("<b>/peso</b>", code_style), Paragraph(traducciones.get('pdf_cmd_peso', "<b>Actualización del peso:</b> Actualiza el peso registrado para el mes en curso."), body_style)],
        [Paragraph("<b>/presi</b>", code_style), Paragraph(traducciones.get('pdf_cmd_presi', "<b>Presión arterial:</b> Registro (<code>/presi ALTA,BAJA,PULSO,NOTA</code>) y consulta mensual (<code>/presi AAAA-MM</code>)."), body_style)],
        [Paragraph("<b>/receta</b>", code_style), Paragraph(traducciones.get('pdf_cmd_receta', "<b>Calculadora nutricional:</b> Acceso directo al módulo de recetas web."), body_style)],
        [Paragraph("<b>/semana</b>", code_style), Paragraph(traducciones.get('pdf_cmd_semana', "<b>Promedio semanal:</b> Estadística semanal de calorías, proteínas y macronutrientes."), body_style)],
        [Paragraph(traducciones.get('pdf_lbl_atajos', "Atajos"), code_style), Paragraph("<b>• /diario:</b> <code>/d</code><br/><b>• /semanal:</b> <code>/s</code><br/><b>• /mensual:</b> <code>/m</code>", body_style)]
    ]

    t_cmds = Table(cmds_data, colWidths=[110, 430])
    t_cmds.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT])
    ]))
    
    story.append(t_cmds)

    doc.build(story)
    buffer.seek(0)
    return buffer    

#                       INICIO                  COMANDO PERFIL Y GESTIÓN BIOMÉTRICA                    INICIO
# ======================================================================================================================================

@requiere_registro
async def cmd_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
    # 🔹 Limpieza dinámica: Soporta tanto /perfil como /peso de forma indistinta
    texto_mensaje = update.message.text.strip() if update.message and update.message.text else ""
    raw_text = texto_mensaje
    for cmd in ['/perfil', '/peso']:
        if texto_mensaje.lower().startswith(cmd):
            raw_text = texto_mensaje[len(cmd):].strip()
            break

    ahora = obtener_ahora_arg()
    mes_actual = ahora.strftime("%Y-%m")
    fecha_hoy = ahora.strftime("%Y-%m-%d")

    # 🔹 GARANTIZAR FILA DEL MES: Asegura que la estructura del mes actual exista en el histórico mensual
    if '_garantizar_fila_mes_actual' in globals():
        _garantizar_fila_mes_actual(user_id, ahora)

    # CASO 1: Ingreso rápido de peso mensual (/perfil 82.5 o /peso 82.5)
    if raw_text:
        try:
            texto_limpio = raw_text.split()[0].replace(',', '.')
            nuevo_peso = float(texto_limpio)
            
            # 1. Guardar en la tabla histórica mensual (Perfil_<user_id>) con su fecha de actualización
            guardar_perfil_db(user_id, nuevo_peso, mes_actual, fecha_actualizacion=fecha_hoy)
            
            # 2. Actualizar también el peso en la tabla maestra 'Usuarios' para mantenerlo sincronizado en ambos lados
            try:
                conn_u, cur_u = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
                cur_u.execute('UPDATE "Usuarios" SET "peso" = %s WHERE "User ID" = %s', (float(nuevo_peso), str(user_id)))
                conn_u.commit()
                cur_u.close()
                conn_u.close()
            except Exception as e_usr_peso:
                logger.error(f"Error al sincronizar peso en tabla Usuarios para {user_id}: {e_usr_peso}")

            perfil_actualizado = obtener_perfil_usuario(user_id, mes_target=mes_actual)
            
            if perfil_actualizado:
                edad = parse_raw_val(perfil_actualizado.get('EDAD', perfil_actualizado.get('Edad', 64)))
                altura = parse_raw_val(perfil_actualizado.get('ALTURA', perfil_actualizado.get('Altura', 170)))
                genero = str(perfil_actualizado.get('GENERO', perfil_actualizado.get('Genero', 'M')))
                ocupacion = parse_raw_val(perfil_actualizado.get('ocupacion', perfil_actualizado.get('OCUPACION', 1.375)))
            else:
                edad, altura, genero, ocupacion = 64.0, 170.0, "M", 1.375

            tmb, get_val = calcular_tmb_y_get(nuevo_peso, altura, edad, genero, ocupacion)
            
            txt_peso_act = traducciones.get('perfil_peso_actualizado_ok', 
                "✅ **Peso actualizado correctamente para el mes `{mes_actual}`:**\n\n"
                "• Nuevo Peso: `{nuevo_peso:.1f}` kg\n"
                "• Fecha de registro: `{fecha_hoy}`\n"
                "• **TMB Estimada:** `{tmb:.0f} kcal/día`\n"
                "• **GET Estimado:** `{get_val:.0f} kcal/día`"
            ).format(mes_actual=mes_actual, nuevo_peso=nuevo_peso, fecha_hoy=fecha_hoy, tmb=tmb, get_val=get_val)

            await update.message.reply_text(txt_peso_act, parse_mode="Markdown")
            return

        except ValueError:
            txt_err_num = traducciones.get('perfil_error_numero_valido', "❌ Por favor, ingresá un número válido para el peso. Ejemplo: `/peso 82.5` o `/perfil 82.5`")
            await update.message.reply_text(txt_err_num, parse_mode="Markdown")
            return
        except Exception as e:
            logger.error(f"Error al procesar /perfil o /peso: {e}")
            txt_err_gral = traducciones.get('perfil_error_guardar', "⚠️ Ocurrió un error al intentar guardar en la base de datos: {e}").format(e=e)
            await update.message.reply_text(txt_err_gral, parse_mode="Markdown")
            return

    # CASO 2: Consulta del Menú Interactivo de Perfil
    try:
        perfil = obtener_perfil_usuario(user_id, mes_target=mes_actual)
        datos_grales = obtener_datos_usuario_general(user_id) if 'obtener_datos_usuario_general' in globals() else {}

        if perfil:
            peso = parse_raw_val(perfil.get('PESO', perfil.get('Peso', 0)))
            altura = parse_raw_val(perfil.get('ALTURA', perfil.get('Altura', 0)))
            edad = parse_raw_val(perfil.get('EDAD', perfil.get('Edad', 0)))
            genero = str(perfil.get('GENERO', perfil.get('Genero', 'M')))
            ocupacion = parse_raw_val(perfil.get('ocupacion', perfil.get('OCUPACION', 1.375)))
            fecha_act_peso = perfil.get('Fecha_Actualizacion', 'S/D')

            cintura = datos_grales.get('cintura_cm', 'S/D')
            cuello = datos_grales.get('cuello_cm', 'S/D')
            ritmo = datos_grales.get('ritmo_preferido', 'moderado')
            profesional = datos_grales.get('profesional', 'S/D')
            idioma_usr = datos_grales.get('Idioma', lang)

            tmb, get_val = calcular_tmb_y_get(peso, altura, edad, genero, ocupacion)
            
            txt_perfil = (
                f"👤 **{traducciones.get('perfil_titulo_biometrico', 'Perfil Biométrico Actual')} ({mes_actual}):**\n\n"
                f"• {traducciones.get('perfil_lbl_edad', 'Edad')}: `{edad:.0f}` {traducciones.get('perfil_anos', 'años')}\n"
                f"• {traducciones.get('perfil_lbl_peso', 'Peso')}: `{peso:.1f}` kg *(Act: {fecha_act_peso})*\n"
                f"• {traducciones.get('perfil_lbl_altura', 'Altura')}: `{altura:.1f}` cm\n"
                f"• {traducciones.get('perfil_lbl_cintura', 'Cintura')}: `{cintura}` cm\n"
                f"• {traducciones.get('perfil_lbl_cuello', 'Cuello')}: `{cuello}` cm\n"
                f"• {traducciones.get('perfil_lbl_ritmo', 'Ritmo de avance')}: `{str(ritmo).capitalize()}`\n"
                f"• {traducciones.get('perfil_lbl_idioma', 'Idioma')}: `{str(idioma_usr).upper()}`\n"
                f"• {traducciones.get('perfil_lbl_profesional', 'ID Profesional')}: `{profesional}`\n\n"
                f"• **{traducciones.get('perfil_lbl_tmb', 'TMB Estimada')}:** `{tmb:.0f} kcal/día`\n"
                f"• **{traducciones.get('perfil_lbl_get', 'GET Estimado')}:** `{get_val:.0f} kcal/día`"
            )
        else:
            txt_perfil = traducciones.get('perfil_no_registrado', "👤 **Perfil no registrado para este mes.** Podés cargar tu peso ejecutando:\n`/peso 82.5`")

        # Menú interactivo con botones Inline
        keyboard = [
            [
                InlineKeyboardButton(traducciones.get('btn_edit_peso', "⚖️ Peso"), callback_data="edit_perfil_peso"),
                InlineKeyboardButton(traducciones.get('btn_edit_cintura', "📏 Cintura"), callback_data="edit_perfil_cintura")
            ],
            [
                InlineKeyboardButton(traducciones.get('btn_edit_cuello', "📐 Cuello"), callback_data="edit_perfil_cuello"),
                InlineKeyboardButton(traducciones.get('btn_edit_ritmo', "🎯 Ritmo"), callback_data="edit_perfil_ritmo")
            ],
            [
                InlineKeyboardButton(traducciones.get('btn_edit_idioma', "🌐 Idioma"), callback_data="edit_perfil_idioma"),
                InlineKeyboardButton(traducciones.get('btn_edit_prof', "🩺 Profesional"), callback_data="edit_perfil_prof")
            ]
        ]
        markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(txt_perfil, reply_markup=markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error al consultar perfil: {e}")
        txt_err_read = traducciones.get('perfil_error_lectura', "⚠️ Ocurrió un error al leer tu perfil: {e}").format(e=e)
        await update.message.reply_text(txt_err_read, parse_mode="Markdown")

#              CALLBACKS INTERACTIVOS PARA ACTUALIZACIÓN DE PARÁMETROS DEL PERFIL
# ======================================================================================================================================

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
        msg = await query.message.reply_text(traducciones.get('solic_nuevo_peso', "⚖️ Por favor, ingresá tu nuevo peso en kg (ej: `78.5`):"), parse_mode="Markdown")
        context.user_data['msg_solicitud_perfil_id'] = msg.message_id

    elif data == "edit_perfil_cintura":
        context.user_data['awaiting_edit_perfil_cintura'] = True
        msg = await query.message.reply_text(traducciones.get('solic_nueva_cintura', "📏 Por favor, ingresá el nuevo perímetro de tu cintura en cm (ej: `84`):"), parse_mode="Markdown")
        context.user_data['msg_solicitud_perfil_id'] = msg.message_id

    elif data == "edit_perfil_cuello":
        context.user_data['awaiting_edit_perfil_cuello'] = True
        msg = await query.message.reply_text(traducciones.get('solic_nuevo_cuello', "📐 Por favor, ingresá el nuevo perímetro de tu cuello en cm (ej: `37`):"), parse_mode="Markdown")
        context.user_data['msg_solicitud_perfil_id'] = msg.message_id

    elif data == "edit_perfil_ritmo":
        btn_tranquilo = traducciones.get('btn_ritmo_tranquilo', "🟢 Tranquilo / Lento")
        btn_moderado = traducciones.get('btn_ritmo_moderado', "🟡 Moderado")
        btn_intenso = traducciones.get('btn_ritmo_intenso', "🔴 Intenso / Rápido")
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(btn_tranquilo, callback_data="set_ritmo_tranquilo")],
            [InlineKeyboardButton(btn_moderado, callback_data="set_ritmo_moderado")],
            [InlineKeyboardButton(btn_intenso, callback_data="set_ritmo_intenso")]
        ])
        await query.message.reply_text(traducciones.get('solic_elegir_ritmo', "🎯 Seleccioná tu nuevo ritmo de avance deseado:"), reply_markup=keyboard, parse_mode="Markdown")

    elif data == "edit_perfil_idioma":
        # Carga dinámica de los idiomas disponibles consultando las columnas de la tabla 'multi'
        idiomas_disp = await obtener_idiomas_disponibles_db() if 'obtener_idiomas_disponibles_db' in globals() else ['es', 'en']
        b_list = []
        for i_code in idiomas_disp:
            b_list.append([InlineKeyboardButton(f"🌐 {i_code.upper()}", callback_data=f"set_lang_{i_code}")])
        markup_lang = InlineKeyboardMarkup(b_list)
        await query.message.reply_text(traducciones.get('solic_elegir_idioma', "🌐 Seleccioná tu idioma preferido:"), reply_markup=markup_lang, parse_mode="Markdown")

    elif data == "edit_perfil_prof":
        context.user_data['awaiting_edit_perfil_prof'] = True
        msg = await query.message.reply_text(traducciones.get('solic_nuevo_prof', "🩺 Por favor, ingresá el ID de Telegram de tu nuevo profesional:"), parse_mode="Markdown")
        context.user_data['msg_solicitud_perfil_id'] = msg.message_id

    elif data.startswith("set_ritmo_"):
        nuevo_ritmo = data.replace("set_ritmo_", "")
        actualizar_ritmo_usuario(user_id, nuevo_ritmo) if 'actualizar_ritmo_usuario' in globals() else None
        await query.edit_message_text(traducciones.get('perfil_ritmo_actualizado_ok', "✅ ¡Ritmo actualizado exitosamente a *{ritmo}*!").format(ritmo=nuevo_ritmo.capitalize()), parse_mode="Markdown")

    elif data.startswith("set_lang_"):
        nuevo_lang = data.replace("set_lang_", "")
        actualizar_idioma_usuario(user_id, nuevo_lang) if 'actualizar_idioma_usuario' in globals() else None
        await query.edit_message_text(traducciones.get('perfil_lang_actualizado_ok', "✅ ¡Idioma actualizado exitosamente a *{lang}*!").format(lang=nuevo_lang.upper()), parse_mode="Markdown")
        
#                       INICIO                  COMANDO PRESION                    INICIO
# ======================================================================================================================================
       
async def _sub_manejar_foto_presion(update, context, res_presion, msg):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}

    alta, baja, pulsaciones = float(res_presion.get("alta", 0)), float(res_presion.get("baja", 0)), float(res_presion.get("pulsaciones", 0))
    
    context.user_data['pending_presion_foto'] = {"alta": alta, "baja": baja, "pulsaciones": pulsaciones}

    t_pulso_etiqueta = traducciones.get('presi_foto_pulsaciones', 'Pulsaciones')
    pul_txt = f" | {t_pulso_etiqueta}: `{pulsaciones:.0f} lpm`" if pulsaciones > 0 else ""
    
    txt_tensio_detectado = traducciones.get('presi_foto_detectado', "🩺 **Tensiómetro detectado en la imagen:**")
    txt_alta = traducciones.get('presi_foto_alta', "• Presión Alta")
    txt_baja = traducciones.get('presi_foto_baja', "• Presión Baja")
    txt_opcion_nota = traducciones.get('presi_txt_elegir_opcion', "Seleccioná una opción para continuar:")

    # Textos de los botones traducidos desde la base de datos
    btn_agregar_nota = traducciones.get('btn_agregar_nota', "✏️ Agregar Nota")
    btn_guardar_sin = traducciones.get('btn_guardar_sin_nota', "💾 Guardar sin Nota")
    btn_cancelar = traducciones.get('btn_cancelar_operacion', "❌ Cancelar")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_agregar_nota, callback_data="presion_pedir_nota")],
        [InlineKeyboardButton(btn_guardar_sin, callback_data="presion_guardar_directo")],
        [InlineKeyboardButton(btn_cancelar, callback_data="cancelar_presion_foto")]
    ])

    await msg.edit_text(
        f"{txt_tensio_detectado}\n\n"
        f"• {txt_alta}: `{alta:.0f} mmHg`\n"
        f"• {txt_baja}: `{baja:.0f} mmHg`{pul_txt}\n\n"
        f"{txt_opcion_nota}",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
        
@requiere_registro
async def cmd_presion_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
    # Limpia tanto /presi como /presion (con o sin acento)
    raw_text = re.sub(r'^/(presio|presi|presion)\w*(@\w+)?', '', update.message.text, flags=re.IGNORECASE).strip()

    if not raw_text:
        txt_ayuda_presi = traducciones.get('presi_ayuda_formato', 
            "Ingresá o consultá un mes usando /presi. Ejemplos:\n\n"
            "• `/presi 120,80,70, después de caminar`\n"
            "• `/presi 120,80,70`\n"
            "• `/presi 120,80`\n"
            "• `/presi 2026-08`"
        )
        await update.message.reply_text(txt_ayuda_presi, parse_mode="Markdown")
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

        # Guarda consumiendo la capa de datos externa
        guardar_presion_db(user_id, alta, baja, pulsaciones, nota)

        t_pulsos_lbl = traducciones.get('presi_lbl_pulsaciones', 'Pulsaciones')
        t_nota_lbl = traducciones.get('presi_lbl_nota', 'Nota')

        pul_str = f" | {t_pulsos_lbl}: `{pulsaciones:.0f}`" if pulsaciones is not None else ""
        nota_str = f"\n{t_nota_lbl}: `{nota}`" if nota else ""
        
        txt_registrada = traducciones.get('presi_registrada_ok', "Presión registrada:\nAlta: `{alta:.0f}` | Baja: `{baja:.0f}`{pul_str}{nota_str}").format(
            alta=alta, baja=baja, pul_str=pul_str, nota_str=nota_str
        )
        
        await update.message.reply_text(txt_registrada, parse_mode="Markdown")
        return

    txt_error_formato = traducciones.get('presi_error_formato', "Formato incorrecto. Uso: /presi 120,80,70, al despertar o /presi 120,80 o /presi 2026-08")
    await update.message.reply_text(txt_error_formato, parse_mode="Markdown")
    
#                       INICIO                  COMANDO FACTOR DE ACTIVIDAD (RELOJ)                    INICIO
# ======================================================================================================================================

@requiere_registro
async def cmd_factor_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    
    raw_text = re.sub(r'^/(factor|fac|get)\w*(@\w+)?', '', update.message.text, flags=re.IGNORECASE).strip()

    ahora = obtener_ahora_arg()
    mes_actual = ahora.strftime("%Y-%m")

    info_usuario = obtener_datos_usuario_general(user_id) if 'obtener_datos_usuario_general' in globals() else obtener_perfil_usuario(user_id, mes_target=mes_actual)
    
    if info_usuario:
        mes_ultimo_cambio = str(info_usuario.get('reloj_actualizado_mes', '')).strip()
        if mes_ultimo_cambio == mes_actual:
            txt_limite_alcanzado = traducciones.get('get_error_limite_mensual', 
                "⏳ **Límite mensual alcanzado:**\n\n"
                "Ya utilizaste el reloj inteligente para calibrar tu gasto este mes. "
                "Para mantener la estabilidad del plan, solo se permite un ajuste por período."
            )
            await update.message.reply_text(txt_limite_alcanzado, parse_mode="Markdown")
            return

    if not raw_text:
        txt_ayuda_get = traducciones.get('get_ayuda_formato', 
            "Ingresá las calorías totales que registró tu reloj en 24 horas. Ejemplo:\n\n"
            "• `/GET 2150`"
        )
        await update.message.reply_text(txt_ayuda_get, parse_mode="Markdown")
        return

    try:
        calorias_reloj = float(raw_text.replace(',', '.'))
        if not (1000 <= calorias_reloj <= 6000):
            txt_err_rango = traducciones.get('get_error_rango_kcal', "⚠️ Ingresá un valor de calorías realista (entre 1000 y 6000 kcal).")
            await update.message.reply_text(txt_err_rango, parse_mode="Markdown")
            return

        perfil = obtener_perfil_usuario(user_id, mes_target=mes_actual)
        if not perfil:
            txt_err_noperfil = traducciones.get('get_error_sin_perfil', "❌ No se encontró tu perfil activo para este mes. Registrá tu peso primero con `/peso`.")
            await update.message.reply_text(txt_err_noperfil, parse_mode="Markdown")
            return

        peso = parse_raw_val(perfil.get('PESO', perfil.get('Peso', 70)))
        altura = parse_raw_val(perfil.get('ALTURA', perfil.get('Altura', 170)))
        edad = parse_raw_val(perfil.get('EDAD', perfil.get('Edad', 40)))
        genero = str(perfil.get('GENERO', perfil.get('Genero', 'masculino')))

        factor_anterior = parse_raw_val(perfil.get('OCUPACION', perfil.get('Ocupacion', 1.375)))
        if factor_anterior <= 0:
            factor_anterior = 1.375

        tmb, get_anterior = calcular_tmb_y_get(peso, altura, edad, genero, actividad=factor_anterior)
        
        if tmb <= 0:
            txt_err_tmb = traducciones.get('get_error_calculo_tmb', "❌ Error al calcular la TMB base.")
            await update.message.reply_text(txt_err_tmb, parse_mode="Markdown")
            return

        factor_crudo_reloj = round(calorias_reloj / tmb, 3)

        nuevo_factor = aplicar_calibracion_reloj(
            factor_previo=factor_anterior, 
            get_reloj=calorias_reloj, 
            tmb=tmb, 
            max_variacion_pct=0.10
        )

        _, get_nuevo = calcular_tmb_y_get(peso, altura, edad, genero, actividad=nuevo_factor)

        aviso_tope = ""
        if abs(nuevo_factor - factor_crudo_reloj) > 0.005:
            aviso_tope = traducciones.get('get_aviso_tope_seguridad', 
                "\n⚠️ *Nota de seguridad:* El valor del reloj se apartaba más del "
                "10% de tu tendencia habitual. Se aplicó un ajuste máximo permitido "
                "para proteger la estabilidad de tu plan.\n"
            )

        context.user_data['temp_nuevo_factor'] = nuevo_factor

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅", callback_data="confirmar_factor_si"),
                InlineKeyboardButton("❌", callback_data="confirmar_factor_no")
            ]
        ])

        msg_texto = traducciones.get('get_preview_calibracion', 
            "📊 **Calibración de Gasto Energético (Reloj):**\n\n"
            "• Calorías reportadas por el reloj: `{calorias_reloj:.0f} kcal`\n"
            "• TMB Base estimada: `{tmb:.0f} kcal`\n\n"
            "• **Gasto Diario Anterior:** `{get_anterior:.0f} kcal`\n"
            "• **Nuevo Gasto Diario Ajustado:** `{get_nuevo:.0f} kcal`\n\n"
            "{aviso_tope}"
            "¿Deseás actualizar tu gasto diario con este valor?"
        ).format(calorias_reloj=calorias_reloj, tmb=tmb, get_anterior=get_anterior, get_nuevo=get_nuevo, aviso_tope=aviso_tope)

        await update.message.reply_text(msg_texto, reply_markup=keyboard, parse_mode="Markdown")

    except ValueError:
        txt_err_val = traducciones.get('get_error_formato_numero', "❌ Formato incorrecto. Ingresá un número válido. Ejemplo: `/GET 2150`")
        await update.message.reply_text(txt_err_val, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error al previsualizar /factor para {user_id}: {e}")
        txt_err_gral = traducciones.get('get_error_proceso', "⚠️ Ocurrió un error al procesar la solicitud: {e}").format(e=e)
        await update.message.reply_text(txt_err_gral, parse_mode="Markdown")
                
async def callback_confirmar_factor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) if 'obtener_idioma_usuario' in globals() else 'en'
    traducciones = obtener_traducciones_db(lang) if 'obtener_traducciones_db' in globals() else {}
    data = query.data

    if data == "confirmar_factor_no":
        context.user_data.pop('temp_nuevo_factor', None)
        txt_canc_calib = traducciones.get('get_calibracion_cancelada', "🚫 Operación cancelada. No se modificó tu gasto energético.")
        await query.edit_message_text(txt_canc_calib, parse_mode="Markdown")
        return

    if data == "confirmar_factor_si":
        nuevo_factor_val = context.user_data.get('temp_nuevo_factor')
        
        if not nuevo_factor_val:
            txt_err_exp = traducciones.get('get_error_datos_expirados', "⚠️ Los datos temporales expiraron. Por favor, volvé a enviar el comando `/factor`.")
            await query.edit_message_text(txt_err_exp, parse_mode="Markdown")
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

            txt_exito_get = traducciones.get('get_calibracion_exito', 
                "✅ **¡Gasto energético actualizado con éxito!**\n\n"
                "• Nuevo Gasto Diario asignado: `{get_final:.0f} kcal`\n"
                "• Período actualizado: `{mes_actual}`\n"
                "• Estado: Calibración mensual registrada."
            ).format(get_final=get_final, mes_actual=mes_actual)

            await query.edit_message_text(txt_exito_get, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error al guardar el factor confirmado para {user_id}: {e}")
            txt_err_db = traducciones.get('get_error_guardar_db', "⚠️ Ocurrió un error al guardar en la base de datos: {e}").format(e=e)
            await query.edit_message_text(txt_err_db, parse_mode="Markdown")
        
        context.user_data.pop('temp_nuevo_factor', None)
        
       
# ======================================================================================================================================
#                       FINAL                        COMANDOS INGRESOS                                      FINAL
# ======================================================================================================================================

# =============================================================================================================================================
#                INICIO                            COMANDOS PROFESIONALES                             INICIO 
# =============================================================================================================================================

#                INICIO                            COMANDO PACIENTES                             INICIO 
# =============================================================================================================================================

async def cmd_pacientes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando para que el profesional vea el listado de sus pacientes y genere un reporte PDF avanzado (hasta 6 meses)."""
    prof_id = str(update.effective_user.id).strip()
    
    msg_espera = await update.message.reply_text("⏳ **Buscando pacientes y procesando historial clínico (hasta 6 meses)...**", parse_mode="Markdown")

    try:
        # 1. Validar e identificar especialidad del profesional usando la capa de abstracción
        especialidad_prof = obtener_especialidad_profesional(prof_id)

        if not especialidad_prof:
            await msg_espera.edit_text("⛔ **Acceso denegado:** Este comando es exclusivo para profesionales registrados.", parse_mode="Markdown")
            return

        # 2. Filtrar pacientes del médico usando la capa de abstracción
        pacientes_del_medico = obtener_pacientes_por_medico(prof_id)

        if not pacientes_del_medico:
            await msg_espera.edit_text("ℹ️ No tenés pacientes activos asignados en este momento.", parse_mode="Markdown")
            return

        # 3. Determinar los últimos 6 meses dinámicamente
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

        # 4. Generación de PDF avanzado (ReportLab)
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

        # Limpieza de caracteres especiales para el nombre del archivo adjunto
        esp_limpia = re.sub(r'[^\w\s]', '', especialidad_prof).replace(' ', '_')

        await msg_espera.delete()
        await update.message.reply_text(texto_reporte, parse_mode="Markdown")
        await update.message.reply_document(
            document=buffer,
            filename=f"Reporte_Clinico_{esp_limpia}_{ahora.strftime('%Y-%m')}.pdf",
            caption="📄 **Reporte clínico actualizado leyendo las columnas 'Alta' y 'Baja'.**",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error al generar listado de pacientes para el profesional {prof_id}: {e}")
        await msg_espera.edit_text(f"❌ Ocurrió un error al procesar el listado clínico: {e}")


#                    INICIO                                COMANDO INFORME MEDICO                                INICIO  
# =============================================================================================================================================

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

# ==========================================================================================================================================
#                    FINAL                      COMANDOS PROFESIONALES                               FINAL  
# ==========================================================================================================================================

# ==========================================================================================================================================
#                                   INICIO                                       MAIN                                       INICIO  
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

def main():
    threading.Thread(target=run_flask, daemon=True).start()

    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not configured.")
        return

    try:
        app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

        # 🟢 Conversación de Alta / Registro de Usuario
        app_bot.add_handler(conv_handler_ingreso)

        # 📌 Comandos Generales y Principales
        app_bot.add_handler(CommandHandler("start", cmd_start))
        app_bot.add_handler(CommandHandler("inicio", cmd_start))
        app_bot.add_handler(CommandHandler("comidas", cmd_comidas))
        app_bot.add_handler(CommandHandler("borracomida", cmd_borrar_comida))
        app_bot.add_handler(CommandHandler("barra", cmd_barra))
        app_bot.add_handler(CommandHandler("receta", cmd_cargar_receta))
        app_bot.add_handler(CommandHandler("eliminar", cmd_eliminar))
        app_bot.add_handler(CommandHandler("diario", cmd_diario))
        app_bot.add_handler(CommandHandler("dia", cmd_diario))
        app_bot.add_handler(CommandHandler("d", cmd_diario))
        app_bot.add_handler(CommandHandler("semana", cmd_mensaje))
        app_bot.add_handler(CommandHandler("semanal", cmd_mensaje))
        app_bot.add_handler(CommandHandler("s", cmd_mensaje))
        app_bot.add_handler(CommandHandler("mes", cmd_resumen))
        app_bot.add_handler(CommandHandler("mensual", cmd_resumen))
        app_bot.add_handler(CommandHandler("m", cmd_resumen))
        app_bot.add_handler(CommandHandler("perfil", cmd_perfil))
        app_bot.add_handler(CommandHandler("peso", cmd_perfil))
        app_bot.add_handler(CommandHandler("presi", cmd_presion_handler))
        app_bot.add_handler(CommandHandler("presion", cmd_presion_handler))
        app_bot.add_handler(CommandHandler("factor", cmd_factor_handler))
        app_bot.add_handler(CommandHandler("get", cmd_factor_handler))
        app_bot.add_handler(CommandHandler("migrar", cmd_migrar))
        app_bot.add_handler(CommandHandler("importar", cmd_importar_tabla))
        app_bot.add_handler(CommandHandler("descargar", cmd_descargar))
        app_bot.add_handler(CommandHandler("pacientes", cmd_pacientes))
        app_bot.add_handler(CommandHandler("informe", cmd_enviar_informe_actual))

        # 🎛️ Callback Query Handlers (Botones Interactivos)
        app_bot.add_handler(CallbackQueryHandler(ing_aceptar_terminos, pattern="^aceptar_terminos_ok$"))
        app_bot.add_handler(CallbackQueryHandler(callback_btn_momento, pattern="^set_m_"))
        app_bot.add_handler(CallbackQueryHandler(callback_btn_fechas_diario, pattern="^(set_d_|diario_)"))
        app_bot.add_handler(CallbackQueryHandler(callback_btn_editar_item, pattern="^edit_item_"))
        app_bot.add_handler(CallbackQueryHandler(callback_btn_anular_item, pattern="^del_item_"))
        app_bot.add_handler(CallbackQueryHandler(callback_btn_cancelar_registro, pattern="^cancel_entry$"))
        app_bot.add_handler(CallbackQueryHandler(callback_btn_guardar_registro, pattern="^confirm_save$"))
        app_bot.add_handler(CallbackQueryHandler(callback_handler_actividades, pattern="^act_"))
        app_bot.add_handler(CallbackQueryHandler(callback_handler_eliminacion, pattern="^del_"))
        app_bot.add_handler(CallbackQueryHandler(manejar_callback_eliminacion, pattern="^del_reg_|^del_borrar_todo_momento$"))
        app_bot.add_handler(CallbackQueryHandler(callback_handler_reportes_pdf, pattern="^(resumen_|descargar_pdf_|enviar_inf_)"))
        app_bot.add_handler(CallbackQueryHandler(callback_handler_editar_perfil, pattern="^(edit_perfil_|set_ritmo_|set_lang_)"))
        app_bot.add_handler(CallbackQueryHandler(callback_confirmar_factor, pattern="^confirmar_factor_"))

        # 📸 Mensajes Multimedia y Texto Libre
        app_bot.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        app_bot.add_handler(MessageHandler(filters.VOICE, handle_voice))
        app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # ⏰ Tareas Programadas (Job Queue)
        if app_bot.job_queue:
            app_bot.job_queue.run_daily(job_recordatorio_manana, time=time(hour=9, minute=0, tzinfo=ARG_TZ))
            app_bot.job_queue.run_daily(job_recordatorio_tarde, time=time(hour=19, minute=30, tzinfo=ARG_TZ))
            app_bot.job_queue.run_daily(job_buenas_noches, time=time(hour=22, minute=0, tzinfo=ARG_TZ))

        print("🤖 Bot iniciado exitosamente y escuchando eventos...")
        app_bot.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"❌ Error crítico al iniciar el bot: {e}", exc_info=True)
        raise e

if __name__ == "__main__":
    main()

# =============================================================================================================================================
#                                               FINAL MAIN EXECUTION                                                    FINAL
# =============================================================================================================================================



