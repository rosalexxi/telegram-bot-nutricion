from flask import render_template_string, request, jsonify, send_from_directory
import os
import json
import logging
import google.generativeai as genai
import time
import requests

# Importamos la instancia de Flask y las funciones necesarias del núcleo
from bot8a import	 (
    app, 
    logger, 
    _asegurar_tabla_y_conectar, 
    obtener_traducciones_db, 
    obtener_idioma_usuario, 
    guardar_comida_precargada_db,
    registrar_evento_web_db,   
    MODELO_TEXTO, 
    MODELO_RESPALDO, 
    MODELO_EMERGENCIA
)

# =====================================================================================================================================
#              INICIO                                  PAGINA WEB (CALCULADORA UNICA)                        INICIO
# ======================================================================================================================================

HTML_CALCULADORA_RECETAS = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title id="title-app">IA NutriBot</title>

    <!-- Fuente Moderna de Google -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <!-- SweetAlert2 para Notificaciones Modernas -->
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    
    <style>
        :root {
            --primary: #27ae60;
            --primary-dark: #219150;
            --primary-gradient: linear-gradient(135deg, #27ae60 0%, #219150 100%);
            --secondary: #1e293b;
            --bg-light: #f8fafc;
            --text-main: #334155;
            --text-muted: #64748b;
            --border-light: #e2e8f0;
        }
        
        html, body { 
            min-height: 100dvh; margin: 0; padding: 0; 
            font-family: 'Inter', sans-serif; 
            color: var(--text-main); display: flex; flex-direction: column;
            background-size: cover; background-position: center; background-attachment: fixed;
            background-blend-mode: overlay; background-color: rgba(244, 246, 249, 0.90);
            transition: background-image 1.5s ease-in-out;
        }
        
        header { 
            background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px);
            box-shadow: 0 4px 15px -3px rgba(0,0,0,0.05); 
            position: sticky; top: 0; z-index: 1000; padding: 15px 20px;
        }
        
        .nav-container { max-width: 1100px; margin: auto; display: flex; flex-direction: column; gap: 12px; }
        
        /* Fila 1: Logo Izquierda, Título Centro */
        .nav-row-1 { display: flex; justify-content: center; align-items: center; position: relative; }
        .logo-img { width: 42px; height: 42px; border-radius: 50%; position: absolute; left: 0; object-fit: contain; }
        .site-title { font-size: 1.5rem; font-weight: 700; color: var(--primary); margin: 0; letter-spacing: -0.5px;}

        /* Fila 2: Índice a la izquierda (con scroll horizontal en celulares) */
        .nav-row-2 { 
            display: flex; justify-content: flex-start; align-items: center; gap: 8px; 
            overflow-x: auto; white-space: nowrap; padding-bottom: 5px; 
        }
        .nav-row-2::-webkit-scrollbar { height: 4px; }
        .nav-row-2::-webkit-scrollbar-thumb { background: var(--primary); border-radius: 4px; }
        .nav-row-2 a { text-decoration: none; color: var(--text-muted); font-weight: 600; font-size: 0.9rem; padding: 8px 12px; border-radius: 8px; cursor: pointer; transition: all 0.2s ease; border-bottom: 2px solid transparent;}
        .nav-row-2 a:hover { color: var(--primary); background-color: rgba(39, 174, 96, 0.05); }
        .nav-row-2 a.active { color: var(--primary); border-bottom: 2px solid var(--primary); background-color: rgba(39, 174, 96, 0.08); }

        /* Fila 3: Telegram y Banderas */
        .nav-row-3 { display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border-light); padding-top: 10px; }
        
        .telegram-link {
            display: inline-flex; align-items: center; gap: 8px; text-decoration: none;
            color: var(--primary); font-weight: 600; font-size: 0.85rem;
            background: rgba(39, 174, 96, 0.1); padding: 6px 14px; border-radius: 20px;
            transition: all 0.2s ease;
        }
        .telegram-link:hover { background: var(--primary); color: white; transform: translateY(-2px); box-shadow: 0 4px 10px rgba(39,174,96,0.2); }
        .tg-icon-img { width: 18px; height: 18px; object-fit: contain; }

        .flag-btn { 
            background: transparent; border: 2px solid transparent; border-radius: 6px; 
            padding: 3px; cursor: pointer; text-decoration: none; display: inline-flex; 
            align-items: center; justify-content: center; transition: all 0.2s ease; 
        }
        .flag-btn:hover, .flag-btn.active-flag { 
            background: rgba(39, 174, 96, 0.1); transform: scale(1.1); 
        }
        .flag-icon-img { width: 28px; height: 20px; object-fit: cover; display: block; border-radius: 3px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }

        /* Contenedores Principales */
        .content-wrapper { 
            max-width: 950px; margin: 30px auto; background: rgba(255, 255, 255, 0.7); 
            backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
            padding: 30px; border-radius: 20px; box-shadow: 0 10px 30px -5px rgba(0,0,0,0.1); 
            border: 1px solid rgba(255, 255, 255, 0.5); width: 92%; box-sizing: border-box; flex: 1;
        }

        .content-box { 
            background: #ffffff; border-radius: 16px; padding: 30px; 
            box-shadow: 0 4px 15px -3px rgba(0,0,0,0.05); margin-bottom: 20px;
        }

        /* Textos y Secciones */
        .page-title { color: var(--secondary); text-align: center; margin-top: 0; font-size: 1.6rem; font-weight: 700; letter-spacing: -0.5px;}
        .page-subtitle { text-align: center; color: var(--text-muted); margin-bottom: 20px; font-weight: 400; font-size: 1rem; }
        .page-divider { border: 0; border-top: 1px solid var(--border-light); margin: 20px 0; }
        .page-footer { text-align: center; color: var(--primary); margin-top: 30px; font-weight: 600;}
        .page-bullet { margin-bottom: 15px; line-height: 1.7; color: var(--text-main); font-size: 0.95rem; }
        .page-bullet b { color: var(--secondary); }

        /* Animación de pestañas */
        .section-content { display: none; }
        .section-content.active { display: block; animation: fadeIn 0.4s ease forwards; }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Calculadora */
        .calculator-section { margin-top: 5px; }
        label { font-weight: 600; display: block; margin-top: 15px; margin-bottom: 6px; font-size: 0.85rem; color: var(--secondary); text-transform: uppercase; letter-spacing: 0.5px;}
        
        input[type="text"], input[type="number"], select, textarea { 
            width: 100%; padding: 12px 15px; border: 1px solid transparent; border-radius: 8px; box-sizing: border-box; 
            font-size: 0.9rem; color: var(--text-main); background: #f1f5f9; font-family: 'Inter', sans-serif;
            transition: all 0.2s ease;
        }
        input:focus, select:focus, textarea:focus {
            outline: none; background: #ffffff; border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(39, 174, 96, 0.15);
        }
        textarea { height: 100px; resize: vertical; }
        
        .row { display: flex; gap: 15px; flex-wrap: wrap;}
        .col { flex: 1 1 200px; }
        
        button.calc-btn { 
            background: var(--primary-gradient); color: white; padding: 14px; border: none; 
            border-radius: 8px; width: 100%; font-size: 1rem; font-weight: 600; cursor: pointer; 
            margin-top: 20px; transition: transform 0.2s, box-shadow 0.2s; 
        }
        button.calc-btn:hover { transform: translateY(-2px); box-shadow: 0 8px 15px rgba(39,174,96,0.3); }
        
        /* Spinner de carga */
        #loading { display: none; text-align: center; margin-top: 20px; padding: 20px; }
        .spinner { border: 3px solid rgba(0,0,0,0.1); width: 34px; height: 34px; border-radius: 50%; border-left-color: var(--primary); animation: spin 1s linear infinite; display: inline-block; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .loading-text { display: block; margin-top: 10px; color: var(--text-muted); font-size: 0.9rem; font-weight: 500;}

        #resultado-section { display: none; margin-top: 25px; border-top: 1px solid var(--border-light); padding-top: 15px; }
        
        table.calc-tbl { width: 100%; border-collapse: collapse; margin-top: 10px; border-radius: 8px; overflow: hidden; border: 1px solid var(--border-light); }
        table.calc-tbl th, table.calc-tbl td { border-bottom: 1px solid var(--border-light); padding: 10px; text-align: center; vertical-align: middle; background: #ffffff; }
        table.calc-tbl th { background-color: #f8fafc; font-weight: 600; font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px;}
        table.calc-tbl th:first-child, table.calc-tbl td:first-child { text-align: left; }
        table.calc-tbl tr:last-child td { border-bottom: none; }
        table.calc-tbl tr.total-row { background-color: #f0fdf4; font-weight: 700; font-size: 0.85rem; color: #166534; border-top: 2px solid #bbf7d0;}
        
        .editable-cell { width: 100%; padding: 8px; border: 1px solid transparent; background: transparent; text-align: inherit; font-size: 0.85rem; color: var(--text-main); border-radius: 6px; transition: background 0.2s;}
        .editable-cell:hover, .editable-cell:focus { background: #f1f5f9; outline: none; }

        .btn-save { background-color: #8b5cf6; margin-top: 15px; color: white; padding: 12px; border: none; border-radius: 8px; width: 100%; font-weight: 600; cursor: pointer; font-size: 0.9rem; transition: background 0.2s;}
        .btn-save:hover { background-color: #7c3aed; }
        .btn-copy { background-color: #3b82f6; margin-top: 10px; color: white; padding: 12px; border: none; border-radius: 8px; width: 100%; font-weight: 600; cursor: pointer; font-size: 0.9rem; transition: background 0.2s;}
        .btn-copy:hover { background-color: #2563eb; }
        
        .user-badge { background: #e0f2fe; color: #0284c7; padding: 8px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; display: inline-block; margin-bottom: 10px; border: 1px solid #bae6fd;}

        footer { 
            background: rgba(30, 41, 59, 0.95); backdrop-filter: blur(10px); color: white; 
            text-align: center; padding: 25px 20px; flex-shrink: 0; font-size: 0.85rem; margin-top: auto;
        }
        .footer-links { margin-bottom: 15px; display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: 15px; }
        .footer-link { padding: 8px; border-radius: 12px; transition: all 0.2s ease; display: inline-flex; align-items: center; justify-content: center; cursor: pointer; }
        .footer-link:hover { background: rgba(255,255,255,0.1); transform: translateY(-3px); }
        .footer-icon-img { width: 28px; height: 28px; object-fit: contain; display: block; opacity: 0.85; transition: opacity 0.2s;}
        .footer-link:hover .footer-icon-img { opacity: 1; }
        .footer-info { opacity: 0.7; font-size: 0.8rem; }
       
        @media (max-width: 600px) {
            .content-wrapper { padding: 15px; width: 95%; margin: 15px auto;}
            .content-box { padding: 20px; }
            .nav-row-3 { flex-direction: column-reverse; gap: 10px; align-items: stretch; }
            .telegram-link { justify-content: center; }
            #langFlagsContainer { justify-content: center; }
        }        
    </style>
</head>
<body>

<div id="loadingLang" data-var="_02_loading_lang" style="display:none; position:fixed; top:20px; right:20px; background:#1e293b; color:white; padding:12px 20px; border-radius:30px; z-index:9999; font-size:0.85rem; font-weight:600; box-shadow: 0 10px 25px rgba(0,0,0,0.2);">
    ⏳ Cargando idioma...
</div>

<header>
    <div class="nav-container">

        <!-- Renglón 1: Logo y Título -->
        <div class="nav-row-1" style="justify-content: flex-start; padding-left: 10px;">
            <a href="https://t.me/mi_control_dieta_bot" target="_blank" style="display: flex; align-items: center; text-decoration: none;">
                <img src="{{ url_for('static', filename='logo.png') }}" class="logo-img" alt="Logo" onerror="this.style.display='none'" style="position: relative; margin-right: 15px;">
                <h1 class="site-title" data-var="_02_titulo_web">IA NutriBot</h1>
            </a>
        </div>

        <!-- Renglón 2: Índice de páginas -->
        <div class="nav-row-2" id="nav-links">
            <a id="nav-inicio" onclick="showSection('inicio')" class="active" data-var="_02_menu_inicio">Inicio</a>
            <a id="nav-ingreso" onclick="showSection('ingreso')" data-var="_02_menu_ingreso">Ingreso</a>
            <a id="nav-salud" onclick="showSection('salud')" data-var="_02_menu_salud">Salud y Perfil</a>
            <a id="nav-informes" onclick="showSection('informes')" data-var="_02_menu_informes">Informes</a>
            <a id="nav-calculadora_info" onclick="showSection('calculadora_info')" data-var="_02_menu_calculadora_info">Precargadas</a>
            <a id="nav-alta" onclick="showSection('alta')" data-var="_02_menu_alta">Alta</a>
            <a id="nav-comandos" onclick="showSection('comandos')" data-var="_02_menu_comandos">Comandos</a>
            <a id="nav-faq" onclick="showSection('faq')" data-var="_02_menu_faq">FAQ</a>
            <a id="nav-terminos" onclick="showSection('terminos')" data-var="_02_menu_terminos">Legal</a>
            {% if user_id %}
            <a id="nav-calculadora" onclick="showSection('calculadora')" data-var="_02_menu_calculadora">Calculadora Web</a>
            {% endif %}
        </div>

        <!-- Renglón 3: Telegram y Banderas -->
        <div class="nav-row-3">
            <a href="https://t.me/mi_control_dieta_bot" target="_blank" class="telegram-link">
                <img src="{{ url_for('static', filename='telegram.png') }}" alt="Telegram" class="tg-icon-img" onerror="this.outerHTML='<span style=\'font-size:18px;\'>✈️</span>'">
                <span>Telegram</span>
            </a>
            <div id="langFlagsContainer" style="display:flex; gap:8px;"></div>
        </div>
    </div>
</header>

<div class="content-wrapper">
    <!-- INICIO -->
    <div id="section-inicio" class="section-content active">
        <div class="content-box">
            <h2 class="page-title"><span data-var="_02_inicio_tit">BIENVENIDO A IA NUTRIBOT</span></h2>
            <h4 class="page-subtitle" data-var="_02_inicio_sub">La forma más simple, rápida y segura de llevar el control de tu alimentación.</h4>
            <hr class="page-divider">
            <p class="page-bullet" data-var="_02_inicio_b1">⭐ <b>Facilidad total:</b> Olvidate de instalar apps con permisos para acceder a tus datos personales. IA NutriBot funciona 100% dentro de tu Telegram. No necesitas descargar ni instalar ninguna aplicación extra.</p>
            <p class="page-bullet" data-var="_02_inicio_b2">⭐ <b>Privacidad y rapidez:</b> Es totalmente anónimo. No te pedimos registros, ni contraseñas para que puedas ingresar. Te das de alta unicamente con tus datos biometricos.</p>
            <p class="page-bullet" data-var="_02_inicio_b3">⭐ <b>Carga inteligente:</b> Olvídate de buscar ingredientes a mano. Para ingresar tus comidas solo necesitas enviar foto, audio o texto. IA NutriBot se encarga del resto calcula calorias, fibras, hidratos, grasas, etc.</p>
            <p class="page-bullet" data-var="_02_inicio_b4">⭐ <b>Registro automático:</b> Toda tu información se guarda de forma segura en una base de datos para llevar tu historial sin que tengas que anotar nada.</p>
            <p class="page-bullet" data-var="_02_inicio_b5">⭐ <b>Evolución constante:</b> Genera informes automáticos semanales y 2 veces por mes el resumen mensual con la estimación de variación de peso que vas a recibir directamente en tu Telegram.</p>
            <h3 class="page-footer" data-var="_02_inicio_foot">¡Nunca fue tan fácil llevar tu control nutricional!</h3>
        </div>
    </div>

    <!-- INGRESO -->
    <div id="section-ingreso" class="section-content">
        <div class="content-box">
            <h2 class="page-title"><span data-var="_02_ingreso_tit">INGRESO DE COMIDAS</span></h2>
            <h4 class="page-subtitle" data-var="_02_ingreso_sub">Todas las opciones para registrar tu alimentación de manera fácil, rápida y segura.</h4>
            <hr class="page-divider">
            <p class="page-bullet" data-var="_02_ingreso_b1">⭐ <b>Por Foto:</b> Solo envía una imagen de tu celu o una foto de tu plato y la Inteligencia Artificial hará el cálculo.</p>
            <p class="page-bullet" data-var="_02_ingreso_b2">⭐ <b>Por Audio:</b> Háblale coloquialmente a IA NutriBot te va a entender y extraer los valores de tus comidas. Por ejemplo decile "Café con leche con 2 medialunas" ¡El bot lo procesa al instante!</p>
            <p class="page-bullet" data-var="_02_ingreso_b3">⭐ <b>Por Texto:</b> Simplemente escribe contando qué comiste. El bot te va a presentar un menú interactivo para confirmar, modificar y seleccionar la fecha y el momento de la ingesta.</p>
            <p class="page-bullet" data-var="_02_ingreso_b4">⭐ <b>Por Código de Barras:</b> Le podes enviar una foto del código del producto que vas a consumir. IA NutriBot calculará automáticamente sus valores nutricionales y te los presenta en pantalla.</p>
            <p class="page-bullet" data-var="_02_ingreso_b5">⭐ <b>Con Planilla Precargada:</b> Si buscas exactitud en tus calculos nutricionales tenes a tu disposición la calculadora de recetas para calcular los valores exactos ingresando los ingredientes de una comida, y cargarla en tu planilla personalizada.</p>
            <p class="page-bullet" data-var="_02_ingreso_b6">⭐ <b>Totalmente Editable:</b> ¿Necesitas hacer un ajuste? Cualquier registro que hagas es 100% editable, tanto en la descripción del alimento como en su peso o cantidad.</p>
            <p class="page-bullet" data-var="_02_ingreso_b7">⭐ <b>Corrección de errores:</b> Si por error cargaste mal una comida el sistema te permite mediante un menu interactivo solucionar el error!</p>
            <h3 class="page-footer" data-var="_02_ingreso_foot">¡Empieza ahora mismo enviando tu primera comida!</h3>
        </div>
    </div>

    <!-- SALUD -->
    <div id="section-salud" class="section-content">
        <div class="content-box">
            <h2 class="page-title"><span data-var="_02_salud_tit">SALUD, ACTIVIDAD Y PERFIL</span></h2>
            <h4 class="page-subtitle" data-var="_02_salud_sub">Lleva un registro integral de tu bienestar y mantén tus datos siempre al día.</h4>
            <hr class="page-divider">
            <p class="page-bullet" data-var="_02_salud_b1">⭐ <b>Presión Arterial:</b> Registra tus mediciones escribiendo los valores manualmente o, de forma mucho más directa, enviando una foto de un tensiómetro digital. ¡IA NutriBot leerá los números automáticamente!</p>
            <p class="page-bullet" data-var="_02_salud_b2">⭐ <b>Actividades Físicas:</b> Olvídate de estructuras y comandos fijos. Solo manda un mensaje de texto o audio contándole qué ejercicio hiciste y por cuánto tiempo. Ia NutrBot lo interpretará y calculará tu gasto calórico al instante teniendo en cuenta tus datos biometricos y se incorporan a tu base de datos.</p>
            <p class="page-bullet" data-var="_02_salud_b3">⭐ <b>Valores Biométricos:</b> Tu cuerpo cambia y tus datos también. Puedes actualizar tu peso, medidas y cualquier otro parámetro utilizando el menú interactivo.</p>
            <p class="page-bullet" data-var="_02_salud_b4">⭐ <b>Seguimiento profesional:</b> Ingresando el ID de tu medico, va a poder realizar el seguimiento de tu evolucion al instante.</p>
            <h3 class="page-footer" data-var="_02_salud_foot">¡El control de tu salud ahora la tendrás en la palma de tu mano!</h3>
        </div>
    </div>

    <!-- INFORMES -->
    <div id="section-informes" class="section-content">
        <div class="content-box">
            <h2 class="page-title"><span data-var="_02_info_tit">INFORMES, ESTADÍSTICAS Y CONTROL</span></h2>
            <h4 class="page-subtitle" data-var="_02_info_sub">Visualiza tu progreso con resúmenes detallados y mantén tu registro siempre al día.</h4>
            <hr class="page-divider">
            <p class="page-bullet" data-var="_02_info_b1">⭐ <b>Historial Seguro:</b> El bot acumula y guarda automáticamente todos tus datos, creando un historial completo sin que tengas que anotar nada.</p>
            <p class="page-bullet" data-var="_02_info_b2">⭐ <b>Control de Ingestas Faltantes:</b> Si te olvidas de cargar alguna de las cuatro comidas principales, no hay problema. El bot realiza un relevamiento automático dos veces al día sobre tus últimas 48 horas y te avisa para que mantengas tu registro completo.</p>
            <p class="page-bullet" data-var="_02_info_b3">⭐ <b>Informes Automáticos:</b> Sin que tengas que pedirlo, el sistema te enviará periódicamente tu resumen de evolución: dos informes mensuales y un informe semanal los dias martes.</p>
            <p class="page-bullet" data-var="_02_info_b4">⭐ <b>Descargas Manuales a Demanda:</b> ¿Quieres ver tus números en este instante? Puedes solicitar y descargar tus estadísticas de comidas en cualquier momento, eligiendo el formato diario, semanal o mensual.</p>
            <p class="page-bullet" data-var="_02_info_b5">⭐ <b>Consultas Naturales:</b> Puedes preguntarle a la IA en cualquier momento como si fuera un amigo. Manda un audio diciendo "¿Qué comí hoy?" o "¿Qué cené el 15 de agosto?" y el bot buscará en tu historial al instante.</p>
            <p class="page-bullet" data-var="_02_info_b6">⭐ <b>Resumen de Presión Arterial:</b> También tienes la opción de acceder de forma manual al reporte mensual de todas tus mediciones de presión, ideal para compartirlo con tu médico.</p>
            <h3 class="page-footer" data-var="_02_info_foot">¡Toda tu evolución nutricional la recibís en tu Telegram en PDF!</h3>
        </div>
    </div>

    <!-- PRECARGADAS -->
    <div id="section-calculadora_info" class="section-content">
        <div class="content-box">
            <h2 class="page-title"><span data-var="_02_pre_tit">COMIDAS PRECARGADAS Y CALCULADORA WEB</span></h2>
            <h4 class="page-subtitle" data-var="_02_pre_sub">Guarda tus recetas favoritas y agiliza tus registros diarios con nuestras herramientas avanzadas.</h4>
            <hr class="page-divider">
            <p class="page-bullet" data-var="_02_pre_b1">⭐ <b>Calculadora Nutricional Web:</b> Accede a nuestro módulo web interactivo exclusivo para registrar tus propias recetas caseras (como una pizza o una torta) o tus combinaciones de alimentos habituales.</p>
            <p class="page-bullet" data-var="_02_pre_b2">⭐ <b>Cálculo Inteligente por Porciones:</b> Desde la calculadora, ingresas todos los ingredientes de tu preparación y le indicas si quieres dividirla por porciones o por fracciones de 100 gramos. IA NutriBot desglosará automáticamente las calorías y macronutrientes.</p>
            <p class="page-bullet" data-var="_02_pre_b3">⭐ <b>Guardado Directo:</b> Una vez que la calculadora te muestra el desglose, puedes confirmar los valores y guardarlos directamente en tu planilla personal con un código único. ¡Así de fácil quedará indexada para usarla siempre que quieras!</p>
            <p class="page-bullet" data-var="_02_pre_b4">⭐ <b>Comidas Precargadas:</b> Si ya tienes una receta o combinación guardada en tu base de datos (por ejemplo, tu desayuno habitual), puedes registrarla rápidamente. Solo envíale al bot un asterisco (*) seguido del código de la comida y la cantidad. Luego, podrás confirmar o modificar el momento, el día y las porciones.</p>
            <h3 class="page-footer" data-var="_02_pre_foot">¡Exactitud y rapidez para tu salud!</h3>
        </div>
    </div>

    <!-- ALTA -->
    <div id="section-alta" class="section-content">
        <div class="content-box">
            <h2 class="page-title"><span data-var="_02_alta_tit">ALTA DE USUARIO Y PERFIL BIOMÉTRICO</span></h2>
            <h4 class="page-subtitle" data-var="_02_alta_sub">Un proceso rapidísimo, 100% anónimo y diseñado exclusivamente para la exactitud de tus resultados.</h4>
            <hr class="page-divider">
            <p class="page-bullet" data-var="_02_alta_b1">⭐ <b>Privacidad Total:</b> No te pedimos documento, ni correo electrónico, ni tarjetas de crédito, ni ningún dato personal sensible. Solo necesitas ingresar un nombre para tu ficha, pero puedes usar un apodo o simplemente poner dos letras si lo prefieres</p>
            <p class="page-bullet" data-var="_02_alta_b2">⭐ <b>Datos Estrictamente Biométricos:</b> Las medidas corporales que te solicitamos en el alta (como tu altura, peso, perímetro de cintura y cuello) son esenciales únicamente para comprender tu contextura física real y garantizar la exactitud de tu plan.</p>
            <p class="page-bullet" data-var="_02_alta_b3">⭐ <b>Cálculos de Precisión:</b> Para procesar tus requerimientos utilizamos fórmulas validadas internacionalmente, como el método de la Marina de los Estados Unidos, asegurando la mayor precisión científica en la estimación de tu masa magra.</p>
            <p class="page-bullet" data-var="_02_alta_b4">⭐ <b>Tu Peso de Etapa:</b> Gracias a la exactitud de estos datos biométricos iniciales, IA NutriBot calcula de forma correcta tu "peso de etapa": un objetivo saludable, realista y a tu medida que te acompañará en tu evolución.</p>
            <h3 class="page-footer" data-var="_02_alta_foot">¿Ya estas listo para iniciar un camino saludable?</h3>
        </div>
    </div>

    <!-- COMANDOS -->
    <div id="section-comandos" class="section-content">
        <div class="content-box">
            <h2 class="page-title"><span data-var="_02_cmd_tit">GUÍA COMPLETA DE COMANDOS</span></h2>
            <h4 class="page-subtitle" data-var="_02_cmd_sub">Accede rápidamente a todas las funciones y estadísticas del bot escribiendo estos comandos en el chat.</h4>
            <hr class="page-divider">
            <p class="page-bullet" data-var="_02_cmd_b1">⭐ <b>/alta:</b> Inicia el proceso de apertura y configuración de tu cuenta ingresando tus datos biométricos iniciales.</p>
            <p class="page-bullet" data-var="_02_cmd_b2">⭐ <b>/barra:</b> Desglosa la información nutricional de un producto comestible ingresando su código de barras.</p>
            <p class="page-bullet" data-var="_02_cmd_b3">⭐ <b>/borracomida:</b> Elimina comidas o recetas predeterminadas que hayas guardado previamente en tu planilla personal.</p>
            <p class="page-bullet" data-var="_02_cmd_b4">⭐ <b>/comidas:</b> Muestra tu planilla de comidas precargadas y te permite descargar la lista completa en formato PDF.</p>
            <p class="page-bullet" data-var="_02_cmd_b5">⭐ <b>/dia:</b> Presenta tus ingestas de un dia específico mediante un teclado interactivo y genera un reporte específico en PDF.</p>
            <p class="page-bullet" data-var="_02_cmd_b6">⭐ <b>/eliminar:</b> Te permite borrar registros de ingestas y actividades físicas de fechas pasadas mediante un menu interactivo.</p>
            <p class="page-bullet" data-var="_02_cmd_b7">⭐ <b>/GET:</b> Calibra y actualiza tu Gasto Energético Total utilizando los datos de un reloj inteligente.</p>
            <p class="page-bullet" data-var="_02_cmd_b8">⭐ <b>/inicio:</b> Muestra la guía rápida de uso, el resumen principal de comandos y te da acceso al manual en PDF.</p>
            <p class="page-bullet" data-var="_02_cmd_b9">⭐ <b>/mes:</b> Genera tu reporte mensual detallado de calorías y macronutrientes, listo para descargar en PDF.</p>
            <p class="page-bullet" data-var="_02_cmd_b10">⭐ <b>/pago:</b> Te permite elegir tu plan de suscripción y acceder a las promociones de pago vigentes.</p>
            <p class="page-bullet" data-var="_02_cmd_b11">⭐ <b>/perfil:</b> Abre un menú interactivo para la actualización de tus datos biométricos y ajustes de cuenta.</p>
            <p class="page-bullet" data-var="_02_cmd_b12">⭐ <b>/peso:</b> Inicia el registro o el control periódico de tu evolución de peso mensual.</p>
            <p class="page-bullet" data-var="_02_cmd_b13">⭐ <b>/presi:</b> Herramienta para registrar nuevas mediciones y consultar tu historial de presión arterial.</p>
            <p class="page-bullet" data-var="_02_cmd_b14">⭐ <b>/receta:</b> Abre el acceso a la Calculadora Web interactiva para registrar y guardar tus propias comidas elaboradas.</p>
            <p class="page-bullet" data-var="_02_cmd_b15">⭐ <b>/semana:</b> Muestra en pantalla tus estadísticas nutricionales semanales (calorías, fibras, proteínas, etc.).</p>
            <p class="page-bullet" data-var="_02_cmd_b16">⭐ <b>/x:</b> Cancela inmediatamente cualquier comando o proceso que esté en curso.</p>
        </div>
    </div>

    <!-- FAQ -->
    <div id="section-faq" class="section-content">
        <div class="content-box">
            <h2 class="page-title"><span data-var="_02_faq_tit">PREGUNTAS FRECUENTES (FAQ)</span></h2>
            <h4 class="page-subtitle" data-var="_02_faq_sub">Respuestas rápidas a las dudas más comunes sobre el uso de IA NutriBot.</h4>
            <hr class="page-divider">
            <p class="page-bullet" data-var="_02_faq_b1">⭐ <b>¿Necesito instalar alguna aplicación nueva?</b><br>No, IA NutriBot funciona 100% dentro de tu Telegram. No requieres descargar otras aplicaciones pesadas, ni crear cuentas con contraseñas o correos electrónicos.</p>
            <p class="page-bullet" data-var="_02_faq_b2">⭐ <b>¿Cómo calculo una receta casera?</b><br>Desde el menú /receta podés ingresar todos los ingredientes de tu preparación, dividirla por porciones o gramos, y guardarla con un código único para registrarla rápidamente en el futuro.</p>
            <p class="page-bullet" data-var="_02_faq_b3">⭐ <b>¿Qué pasa si me olvido de registrar una comida?</b><br>¡No te preocupes! IA NutriBot hace un relevamiento automático dos veces al día revisando tus últimas 48 horas, y te enviará un recordatorio amigable si nota que te falta cargar alguna ingesta principal.</p>
            <p class="page-bullet" data-var="_02_faq_b4">⭐ <b>¿Están seguros mis datos personales?</b><br>Absolutamente. El uso del bot es totalmente anónimo. No te pedimos documento de identidad ni tarjetas de crédito para operar. Los únicos datos que importan son tus medidas biométricas para asegurar la precisión de tu plan.</p>
            <p class="page-bullet" data-var="_02_faq_b5">⭐ <b>¿Puedo corregir una comida que aparece en la pantalla?</b><br>Sí, es 100% editable. El sistema te permite modificar tanto la descripción de lo que comiste como el peso o la cantidad de las porciones.</p>
            <p class="page-bullet" data-var="_02_faq_b6">⭐ <b>¿El bot me puede generar un plan de dieta?</b><br>Absolutamente NO. Los profesionales de la salud son los únicos autorizados a realizar planes alimenticios. IA NutriBot es un asistente nutricional que extrae los datos de tus comidas, los guarda en forma ordenada y te brinda los informes para que tu medico los pueda evaluar.</p>
        </div>
    </div>

    <!-- TERMINOS -->
    <div id="section-terminos" class="section-content">
        <div class="content-box">
            <h2 class="page-title"><span data-var="_02_leg_tit">TÉRMINOS Y CONDICIONES</span></h2>
            <h4 class="page-subtitle" data-var="_02_leg_sub">Información importante sobre el uso de IA NutriBot y el manejo de tus datos.</h4>
            <hr class="page-divider">
            <p class="page-bullet" data-var="_02_leg_b1">⭐ <b>Naturaleza de la Herramienta:</b> IA NutriBot es exclusivamente una herramienta de cálculo automatizado orientada a sumar y restar calorías, así como a registrar ingestas y macronutrientes de forma práctica.</p>
            <p class="page-bullet" data-var="_02_leg_b2">⭐ <b>Ausencia de Valor Médico:</b> Este asistente no posee un valor médico ni científico. Las recomendaciones y cálculos emitidos son generados de forma generalizada y probabilística. En ningún caso, el uso de este bot sustituye la consulta, diagnóstico o tratamiento de un profesional de la salud o nutricionista matriculado.</p>
            <p class="page-bullet" data-var="_02_leg_b3">⭐ <b>Privacidad y Datos Personales:</b> El uso de IA NutriBot es totalmente anónimo. No se requiere, ni se almacena, información de identidad personal como número de documento, correo electrónico o datos financieros. Solo se conservan tus datos biométricos (edad, altura, peso, medidas corporales) con el único fin de realizar los cálculos nutricionales.</p>
            <p class="page-bullet" data-var="_02_leg_b4">⭐ <b>Responsabilidad del Usuario:</b> Al presionar "Aceptar" al inicio del alta, el usuario comprende y acepta que la información cargada y las decisiones tomadas en base a los resúmenes del bot son bajo su propia responsabilidad. La herramienta se provee "tal cual es", para asistir en la organización diaria, sin garantías expresas sobre resultados físicos o de salud.</p>
        </div>
    </div>

    <!-- Sección Calculadora Web -->
    {% if user_id %}
    <div id="section-calculadora" class="section-content">
        <div class="content-box calculator-section">
            <h2 class="page-title" data-var="_02_titulo_calc">Calculadora Web</h2>
            <p class="page-subtitle" data-var="_02_desc_calc">Herramienta avanzada para registrar y calcular recetas.</p>

            <div class="user-badge"><span data-var="_02_user_conectado">Usuario Conectado</span>: {{ user_id }}</div>
            
            <div class="row">
                <div class="col">
                    <label for="codigo"><span data-var="_02_label_codigo">Código</span>:</label>
                    <input type="text" id="codigo" data-placeholder="_02_ph_codigo" placeholder="Ej: PASCUALINAP" style="text-transform: uppercase;" oninput="this.value = this.value.toUpperCase()">
                </div>
                <div class="col" style="flex: 2;">
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

            <div id="loading">
                <div class="spinner"></div><br>
                <span class="loading-text" data-var="_02_loading_ia">Calculando macronutrientes con IA...</span>
            </div>

            <div id="resultado-section">
                <div style="overflow-x: auto;">
                    <table class="calc-tbl" id="tablaNutricional">
                        <thead>
                            <tr>
                                <th data-var="_02_th_nombre" style="text-align:left;">Nombre</th>
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
                                <td style="text-align:left;"><span data-var="_02_th_totales">Totales</span></td>
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
    <div class="footer-links">
        <a onclick="reproducirAudioguia()" class="footer-link" data-title="_02_title_audioguia" title="Audioguía">
            <img src="{{ url_for('static', filename='audioguia.png') }}" alt="Audioguía" class="footer-icon-img" onerror="this.outerHTML='<span style=\'font-size:24px;\'>🎧</span>'">
        </a>
        <a id="linkManual" href="#" target="_blank" class="footer-link" data-title="_02_title_manual" title="Manual (PDF)">
            <img src="{{ url_for('static', filename='manual.png') }}" alt="Manual" class="footer-icon-img" onerror="this.outerHTML='<span style=\'font-size:24px;\'>📖</span>'">
        </a>
        <a href="https://instagram.com/ianutribot" target="_blank" class="footer-link" title="Instagram">
            <img src="{{ url_for('static', filename='instagram.png') }}" alt="Instagram" class="footer-icon-img" onerror="this.outerHTML='<span style=\'font-size:24px;\'>📷</span>'">
        </a>
        <a href="https://twitter.com/ianutribot" target="_blank" class="footer-link" title="X (Twitter)">
            <img src="{{ url_for('static', filename='x.png') }}" alt="X" class="footer-icon-img" onerror="this.outerHTML='<span style=\'font-size:24px;\'>✖️</span>'">
        </a>
        <a href="https://tiktok.com/@ianutribot" target="_blank" class="footer-link" title="TikTok">
            <img src="{{ url_for('static', filename='tiktok.png') }}" alt="TikTok" class="footer-icon-img" onerror="this.outerHTML='<span style=\'font-size:24px;\'>🎵</span>'">
        </a>
        <a href="https://facebook.com/ianutribot" target="_blank" class="footer-link" title="Facebook">
            <img src="{{ url_for('static', filename='facebook.png') }}" alt="Facebook" class="footer-icon-img" onerror="this.outerHTML='<span style=\'font-size:24px;\'>📘</span>'">
        </a>
        <a href="https://youtube.com/@ianutribot" target="_blank" class="footer-link" title="YouTube">
            <img src="{{ url_for('static', filename='youtube.png') }}" alt="YouTube" class="footer-icon-img" onerror="this.outerHTML='<span style=\'font-size:24px;\'>▶️</span>'">
        </a>
        <a href="mailto:ianutribot@gmail.com" class="footer-link" title="Mail">
            <img src="{{ url_for('static', filename='mail.png') }}" alt="Mail" class="footer-icon-img" onerror="this.outerHTML='<span style=\'font-size:24px;\'>✉️</span>'">
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
    const tokenSeguro = "{{ token_seguro }}"; // AGREGAR ESTA LÍNEA
    let itemsDesglosadosGlobal = [];

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

                    const img = document.createElement('img');
                    img.src = `/static/${code}.png`;
                    img.alt = code.toUpperCase();
                    img.className = 'flag-icon-img';
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
            
            document.querySelectorAll('[data-var]').forEach(el => {
                const clave = el.getAttribute('data-var');
                if (traducciones[clave] !== undefined) {
                    el.innerHTML = traducciones[clave];
                }
            });

            document.querySelectorAll('[data-placeholder]').forEach(el => {
                const clave = el.getAttribute('data-placeholder');
                if (traducciones[clave] !== undefined) {
                    el.placeholder = traducciones[clave];
                }
            });

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

    let geoDatosVisitante = { pais: 'Desconocido', ciudad: 'Desconocida' };

    async function registrarEstadisticaWeb() {
        try {
            await fetch('/api/registrar-visita', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(geoDatosVisitante)
            });
        } catch (e) {
            console.error("Error registrando visita:", e);
        }
    }    
    
    window.addEventListener('DOMContentLoaded', () => {
        inicializarIdiomaWeb();
        registrarEstadisticaWeb();
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
                Swal.fire({ icon: 'error', title: 'Oops...', text: t('_02_err_audioguia', "Error al reproducir la audioguía:") + " " + error.message });
            }
        } else {

            Swal.fire({ icon: 'warning', title: t('_02_title_atencion', 'Atención'), text: t('_02_err_no_speech', "Tu navegador no soporta la función de lectura de voz.") });
        }
    }

    function showSection(sectionId) {
        document.querySelectorAll('.section-content').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.nav-row-2 a').forEach(el => el.classList.remove('active'));
        
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
        
            Swal.fire({ icon: 'warning', title: t('_02_title_atencion', 'Atención'), text: t('_02_err_no_registrado', "Acción no permitida para usuarios no registrados.") });
            return;
        }

        const codigo = document.getElementById('codigo').value.trim();
        const descripcion = document.getElementById('descripcion').value.trim();
        const receta = document.getElementById('recetaText').value.trim();
        const tipoCalculo = document.getElementById('tipoCalculo').value;
        const porciones = document.getElementById('porciones').value;

        if (!codigo || !descripcion || !receta) {

            Swal.fire({ icon: 'info', title: t('_02_title_vacios', 'Campos Vacíos'), text: t('_02_err_campos_vacios', "Por favor completa el código, la descripción y los ingredientes.") });
            return;
        }

        document.getElementById('loading').style.display = 'block';
        document.getElementById('resultado-section').style.display = 'none';

        try {
            const response = await fetch('/api/calcular-receta', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    token: tokenSeguro,  // <- CORRECCIÓN
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
                Swal.fire({ icon: 'error', title: 'Error del Servidor', text: t('_02_err_servidor', "El servidor falló") + " (HTTP " + response.status + ")." });
                return;
            }

            const data = JSON.parse(responseText);
            
            if (response.ok && data.items && Array.isArray(data.items)) {
                itemsDesglosadosGlobal = data.items;
                renderizarTablaEditable();
                document.getElementById('resultado-section').style.display = 'block';
            } else {
                Swal.fire({ icon: 'error', title: 'Error', text: t('_02_err_calcular', "Error al calcular:") + " " + (data.error || "") });
            }
        } catch (err) {
            Swal.fire({ icon: 'error', title: 'Error de Red', text: t('_02_err_procesamiento', "Error de procesamiento:") + " " + err.message });
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
                <td style="text-align:left;"><input type="text" class="editable-cell" value="${item.alimento || ''}" onchange="actualizarItem(${index}, 'alimento', this.value)"></td>
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
        // Cambiar currentUserId por tokenSeguro en la validación
        if (!tokenSeguro || itemsDesglosadosGlobal.length === 0) {
            Swal.fire({ icon: 'warning', title: 'Atención', text: t('_02_err_sin_datos', "No hay datos calculados o tu sesión expiró.") });
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
                    token: tokenSeguro, // REEMPLAZAR user_id POR token
                    fila: filaTotalConsolidada
                })
            });

            // ... el resto de la función sigue igual ...
            const res = await response.json();
            if (response.ok) {
                if (res.codigo_guardado) {
                    filaTotalConsolidada.nombre = res.codigo_guardado;
                    document.getElementById('codigo').value = res.codigo_guardado;
                }

                Swal.fire({ icon: 'success', title: t('_02_title_guardado', 'Guardado'), text: t('_02_msg_exito_guardar', "¡Éxito!") + " " + (res.message || "") });
            } else {
                Swal.fire({ icon: 'error', title: 'Error', text: t('_02_err_guardar', "Error al guardar:") + " " + (res.error || "") });
            }
        } catch (e) {
            Swal.fire({ icon: 'error', title: 'Error de Red', text: t('_02_err_conexion_guardar', "Error de conexión al intentar guardar.") });
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
            Swal.fire({ icon: 'success', title: 'Copiado', text: t('_02_msg_copiado', "¡Fila total copiada! Podés pegarla en tu Excel con Ctrl + V.") });
        }).catch(err => {
            Swal.fire({ icon: 'error', title: 'Error', text: t('_02_err_copiar', "Error al copiar al portapapeles.") });
        });
    }
</script>
</body>
</html>
"""

#              INICIO                                  PÁGINA DE TÉRMINOS Y ALTA (WEB APP TRADUCIBLE)                   INICIO
# =====================================================================================================================================

HTML_TERMINOS_ALTA = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title data-var="_02_leg_tit">Términos y Condiciones - IA NutriBot</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root {
            --primary: #27ae60;
            --primary-dark: #219150;
            --secondary: #1e293b;
            --bg-color: #f8fafc;
            --text-color: #334155;
            --border-light: #e2e8f0;
        }
        body {
            font-family: 'Inter', sans-serif;
            background: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            min-height: 100vh;
            box-sizing: border-box;
            align-items: center;
            justify-content: center;
        }
        .container {
            max-width: 600px;
            width: 100%;
            background: white;
            padding: 30px;
            border-radius: 16px;
            box-shadow: 0 10px 25px -5px rgba(0,0,0,0.1);
        }
        h2 {
            color: var(--primary);
            text-align: center;
            margin-top: 0;
            font-weight: 700;
            letter-spacing: -0.5px;
        }
        .terms-box {
            max-height: 280px;
            overflow-y: auto;
            border: 1px solid var(--border-light);
            padding: 20px;
            border-radius: 12px;
            background: #fcfcfc;
            font-size: 0.95rem;
            line-height: 1.6;
            margin-bottom: 25px;
        }
        .terms-box::-webkit-scrollbar { width: 6px; }
        .terms-box::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
        
        .btn-accept {
            background: linear-gradient(135deg, #27ae60 0%, #219150 100%);
            color: white;
            border: none;
            padding: 14px;
            width: 100%;
            border-radius: 8px;
            font-size: 1.05rem;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn-accept:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 15px rgba(39,174,96,0.3);
        }
        
        #loading {
            display: none; text-align: center; margin-top: 20px;
        }
        .spinner { border: 3px solid rgba(0,0,0,0.1); width: 28px; height: 28px; border-radius: 50%; border-left-color: var(--primary); animation: spin 1s linear infinite; display: inline-block; vertical-align: middle; margin-right: 10px;}
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
<div class="container">
    <h2 data-var="_02_leg_tit">⚖️ Términos y Condiciones</h2>
    <div class="terms-box">
        <p data-var="_02_leg_b1">⭐ <b>Naturaleza de la Herramienta:</b> IA NutriBot es exclusivamente una herramienta de cálculo automatizado orientada a sumar y restar calorías, así como a registrar ingestas y macronutrientes de forma práctica.</p>
        <p data-var="_02_leg_b2">⭐ <b>Ausencia de Valor Médico:</b> Este asistente no posee un valor médico ni científico. Las recomendaciones y cálculos emitidos son generados de forma generalizada y probabilística. En ningún caso, el uso de este bot sustituye la consulta, diagnóstico o tratamiento de un profesional de la salud o nutricionista matriculado.</p>
        <p data-var="_02_leg_b3">⭐ <b>Privacidad y Datos Personales:</b> El uso de IA NutriBot es totalmente anónimo. No se requiere, ni se almacena, información de identidad personal como número de documento, correo electrónico o datos financieros. Solo se conservan tus datos biométricos y de ubicación (país, ciudad, zona horaria) con el único fin de realizar los cálculos nutricionales.</p>
        <p data-var="_02_leg_b4">⭐ <b>Responsabilidad del Usuario:</b> Al presionar "Aceptar" al inicio del alta, el usuario comprende y acepta que la información cargada y las decisiones tomadas en base a los resúmenes del bot son bajo su propia responsabilidad.</p>
    </div>

    <button class="btn-accept" id="btnAccept" onclick="aceptarTerminos()" data-var="_02_leg_btn_aceptar">✅ He leído y acepto los términos</button>
    <div id="loading">
        <div class="spinner"></div><span data-var="_02_leg_loading" style="color:#64748b; font-weight:500;">Registrando datos y conectando...</span>
    </div>
</div>

<script>
    let tg = window.Telegram.WebApp;
    tg.expand();

    async function inicializarTraduccionWebApp() {
        const urlParams = new URLSearchParams(window.location.search);
        const userId = urlParams.get('user_id');
        let lang = 'es';

        if (userId) {
            try {
                const resUser = await fetch(`/api/usuario-idioma?user_id=${userId}`);
                const dataUser = await resUser.json();
                if (dataUser.lang) {
                    lang = dataUser.lang.toLowerCase();
                }
            } catch (e) {
                console.error("Error al obtener idioma:", e);
            }
        }

        try {
            const response = await fetch(`/api/traducciones?lang=${lang}`);
            if (response.ok) {
                const traducciones = await response.json();
                document.querySelectorAll('[data-var]').forEach(el => {
                    const clave = el.getAttribute('data-var');
                    if (traducciones[clave] !== undefined) {
                        el.innerHTML = traducciones[clave];
                    }
                });
            }
        } catch (err) {
            console.error("Error al aplicar traducciones en Web App:", err);
        }
    }

    window.addEventListener('DOMContentLoaded', inicializarTraduccionWebApp);

    async function aceptarTerminos() {
        document.getElementById('loading').style.display = 'block';
        document.getElementById('btnAccept').style.display = 'none';

        let tz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'America/Argentina/Buenos_Aires';
        let pais = 'Desconocido';
        let ciudad = 'Desconocida';

        try {
            let resGeo = await fetch('https://ipapi.co/json/');
            if (resGeo.ok) {
                let dataGeo = await resGeo.json();
                pais = dataGeo.country_name || dataGeo.country || 'Desconocido';
                ciudad = dataGeo.city || 'Desconocida';
            }
        } catch (e) {
            console.log("Bloqueado por el navegador.");
        }

        let payload = JSON.stringify({
            status: "aceptado",
            pais: pais,
            ciudad: ciudad,
            zona_horaria: tz
        });

        if (tg && tg.sendData) {
            tg.sendData(payload);
            tg.close();
        } else {
            Swal.fire({icon: 'success', title: '¡Listo!', text: 'Términos aceptados con éxito. Volvé a Telegram para continuar.'});
        }
    }
</script>

</body>
</html>
"""

@app.route('/terminos', methods=['GET'])
def vista_terminos():
    return render_template_string(HTML_TERMINOS_ALTA)

@app.route('/api/guardar-terminos', methods=['POST'])
def api_guardar_terminos():
    try:
        data = request.json or {}
        user_id = data.get('user_id')
        pais = data.get('pais', 'Desconocido')
        ciudad = data.get('ciudad', 'Desconocida')
        zona_horaria = data.get('zona_horaria', 'America/Argentina/Buenos_Aires')

        lang = obtener_idioma_usuario(user_id) if user_id else 'es'
        traducciones = obtener_traducciones_db(lang) or {}

        if not user_id:
            err_msg = traducciones.get("02_api_err_falta_id", "Falta user_id")
            return jsonify({"error": err_msg}), 400

        try:
            conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
            cur.execute("""
                UPDATE "Usuarios" 
                SET "pais" = %s, "ciudad" = %s, "zona_horaria" = %s 
                WHERE "User ID" = %s
            """, (pais, ciudad, zona_horaria, str(user_id)))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as db_err:
            logger.error(f"Error actualizando país/zona horaria en DB para {user_id}: {db_err}")
            try:
                conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
                cur.execute('ALTER TABLE "Usuarios" ADD COLUMN IF NOT EXISTS "pais" TEXT;')
                cur.execute('ALTER TABLE "Usuarios" ADD COLUMN IF NOT EXISTS "ciudad" TEXT;')
                cur.execute('ALTER TABLE "Usuarios" ADD COLUMN IF NOT EXISTS "zona_horaria" TEXT;')
                conn.commit()
                cur.execute("""
                    UPDATE "Usuarios" 
                    SET "pais" = %s, "ciudad" = %s, "zona_horaria" = %s 
                    WHERE "User ID" = %s
                """, (pais, ciudad, zona_horaria, str(user_id)))
                conn.commit()
                cur.close()
                conn.close()
            except Exception as inner_err:
                logger.error(f"Error crítico al alterar tabla y guardar datos de alta: {inner_err}")

        ok_msg = traducciones.get("02_api_msg_terminos_ok", "Términos guardados y ubicación registrada correctamente.")
        return jsonify({"message": ok_msg}), 200
    except Exception as e:
        logger.error(f"Error en api_guardar_terminos: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
        
#              FINAL                                   PÁGINA DE TÉRMINOS Y ALTA (WEB APP TRADUCIBLE)                   FINAL
# =====================================================================================================================================

import time

def validar_token_y_obtener_usuario(token):
    """Busca el token en la BD y verifica que no esté vencido. Devuelve el user_id o None."""
    if not token:
        return None
    try:
        conn, cur = _asegurar_tabla_y_conectar("Usuarios", tipo_tabla="usuarios")
        cur.execute('SELECT "User ID", "expiracion_token" FROM "Usuarios" WHERE "token_calculadora" = %s', (token,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row and row[1]:
            expiracion = float(row[1])
            if expiracion > time.time():  # Si el tiempo actual es menor a la expiración, es válido
                return str(row[0]).strip()
    except Exception as e:
        logger.error(f"Error validando token: {e}")
    return None

@app.route('/', methods=['GET'])
def vista_calculadora():
    # En lugar de leer el user_id directo, leemos el token de seguridad
    token = request.args.get('token', '')
    user_id = validar_token_y_obtener_usuario(token)
    
    # Renderizamos la plantilla (si user_id es None, Jinja ocultará la calculadora sola)
    return render_template_string(HTML_CALCULADORA_RECETAS, user_id=user_id, token_seguro=token)
    
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
        token = data.get("token")
        
        # Validación estricta mediante token
        user_id = validar_token_y_obtener_usuario(token)
        if not user_id:
            return jsonify({"error": "Sesión expirada o inválida. Generá un nuevo link desde Telegram."}), 403
            
        codigo = data.get("codigo")
        descripcion = data.get("descripcion")
        receta = data.get("receta")
        tipo_calculo = data.get("tipoCalculo")
        porciones = int(data.get("porciones", 1))
        lang = data.get("lang", "es")
        
        traducciones = obtener_traducciones_db(lang) or {}

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
            "REGLA MATEMÁTICA: Las calorías deben coincidir con la suma aproximada de (Proteínas*4) + (Carbohidratos*4) + (Grasas*9).\n"
            "Devuelve ÚNICAMENTE un JSON con esta estructura exacta:\n"
            '{"items": [{"alimento": "...", "peso": 0.0, "calorias": 0.0, "proteinas": 0.0, "grasas": 0.0, "carbohidratos": 0.0, "fibras": 0.0}]}'
        )

        instruccion = "Eres un nutricionista clínico experto en análisis de recetas y desglose de macronutrientes."
        config_gen = {"response_mime_type": "application/json", "temperature": 0.1}

        resultado_json = None

        try:
            model = genai.GenerativeModel(MODELO_TEXTO, system_instruction=instruccion)
            response = model.generate_content(prompt_ia, generation_config=config_gen)
            texto_limpio = response.text.replace("```json", "").replace("```", "").strip()
            resultado_json = json.loads(texto_limpio)
            
        except Exception as e_prin:
            logger.warning(f"⚠️ Falla Principal Web ({MODELO_TEXTO}): {e_prin}. Pasando a Respaldo...")
            try:
                model_resp = genai.GenerativeModel(MODELO_RESPALDO, system_instruction=instruccion)
                response_resp = model_resp.generate_content(prompt_ia, generation_config=config_gen)
                texto_limpio = response_resp.text.replace("```json", "").replace("```", "").strip()
                resultado_json = json.loads(texto_limpio)
                
            except Exception as e_resp:
                logger.warning(f"⚠️ Falla Respaldo Web ({MODELO_RESPALDO}): {e_resp}. Pasando a Emergencia...")
                try:
                    model_emer = genai.GenerativeModel(MODELO_EMERGENCIA, system_instruction=instruccion)
                    response_emer = model_emer.generate_content(prompt_ia, generation_config=config_gen)
                    texto_limpio = response_emer.text.replace("```json", "").replace("```", "").strip()
                    resultado_json = json.loads(texto_limpio)                 
                except Exception as e_emer:
                    logger.error(f"❌ Fallaron todos los modelos web: {e_emer}")
                    err_msg = traducciones.get("02_api_err_ia_fallo", "No se pudo conectar con los servidores de Inteligencia Artificial.")
                    return jsonify({"error": err_msg}), 500

        items = resultado_json.get("items", [])

        if tipo_calculo == "porciones" and porciones > 1:
            for item in items:
                for k in ["peso", "calorias", "proteinas", "grasas", "carbohidratos", "fibras"]:
                    item[k] = round(float(item.get(k, 0)) / porciones, 2)
        elif tipo_calculo == "gramos":
            total_peso = sum(float(i.get("peso", 0)) for i in items)
            if total_peso > 0:
                factor = 100.0 / total_peso
                for item in items:
                    for k in ["peso", "calorias", "proteinas", "grasas", "carbohidratos", "fibras"]:
                        item[k] = round(float(item.get(k, 0)) * factor, 2)

        return jsonify({"nombre": codigo, "descripcion": descripcion, "items": items}), 200

    except Exception as e:
        logger.error(f"Error crítico en api_calcular_receta: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
            
@app.route('/api/guardar-comida', methods=['POST'])
def api_guardar_comida():
    try:
        data = request.json
        token = data.get("token")
        fila = data.get('fila')
        
        # Validación estricta mediante token
        user_id = validar_token_y_obtener_usuario(token)
        if not user_id or not fila:
            return jsonify({"error": "Sesión expirada o faltan datos de la receta."}), 403

        lang = obtener_idioma_usuario(user_id) if user_id else 'es'
        traducciones = obtener_traducciones_db(lang) or {}

        codigo_guardado = guardar_comida_precargada_db(user_id, fila)

        ok_msg = traducciones.get("02_api_msg_receta_guardada", "Receta guardada exitosamente en tu base de datos.")
        return jsonify({
            "message": ok_msg,
            "codigo_guardado": codigo_guardado
        }), 200

    except Exception as e:
        logger.error(f"Error en api_guardar_comida: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

def obtener_geo_ip(request_obj):
    ip = request_obj.headers.get('X-Forwarded-For', request_obj.remote_addr)
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()
    
    if not ip or ip == '127.0.0.1':
        return 'Desconocido', 'Desconocida'
        
    try:
        res = requests.get(f"http://ip-api.com/json/{ip}", timeout=3)
        if res.status_code == 200:
            data = res.json()
            return data.get("country", "Desconocido"), data.get("city", "Desconocida")
    except:
        pass
    return 'Desconocido', 'Desconocida'

@app.route('/api/registrar-visita', methods=['POST'])
def api_registrar_visita():
    try:
        data = request.get_json(force=True, silent=True) or {}
        pais = data.get('pais', 'Desconocido')
        ciudad = data.get('ciudad', 'Desconocida')
        
        if pais == 'Desconocido':
            pais_srv, ciudad_srv = obtener_geo_ip(request)
            if pais_srv != 'Desconocido':
                pais = pais_srv
                ciudad = ciudad_srv

        registrar_evento_web_db(pais, ciudad, es_click_telegram=False)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Error en api_registrar_visita: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/registrar-click-telegram', methods=['POST'])
def api_registrar_click_telegram():
    try:
        data = request.get_json(force=True, silent=True) or {}
        pais = data.get('pais', 'Desconocido')
        ciudad = data.get('ciudad', 'Desconocida')
        
        if pais == 'Desconocido':
            pais_srv, ciudad_srv = obtener_geo_ip(request)
            if pais_srv != 'Desconocido':
                pais = pais_srv
                ciudad = ciudad_srv

        registrar_evento_web_db(pais, ciudad, es_click_telegram=True)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Error en api_registrar_click_telegram: {e}")
        return jsonify({"error": str(e)}), 500
        
# =====================================================================================================================================
#              FINAL                                  PAGINA WEB (CALCULADORA UNICA)                  FINAL
# =====================================================================================================================================
