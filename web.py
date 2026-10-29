from flask import render_template_string, request, jsonify, send_from_directory
import os
import json
import logging
import google.generativeai as genai

# Importamos la instancia de Flask y las funciones necesarias del núcleo
from bot8a import (
    app, 
    logger, 
    _asegurar_tabla_y_conectar, 
    obtener_traducciones_db, 
    obtener_idioma_usuario, 
    guardar_comida_precargada_db,
    MODELO_TEXTO, 
    MODELO_RESPALDO, 
    MODELO_EMERGENCIA
)

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
            min-height: 100dvh; margin: 0; padding: 0; 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            color: var(--text-color); display: flex; flex-direction: column;
            background-size: cover; background-position: center; background-attachment: fixed;
            background-blend-mode: overlay; background-color: rgba(244, 246, 249, 0.85);
            transition: background-image 1.5s ease-in-out;
        }
        
        header { 
            background: rgba(255, 255, 255, 0.95); box-shadow: 0 2px 8px rgba(0,0,0,0.1); 
            position: sticky; top: 0; z-index: 1000; padding: 10px 15px;
        }
        
        .nav-container { max-width: 1100px; margin: auto; display: flex; flex-direction: column; gap: 8px; }
        
        /* Fila 1: Logo Izquierda, Título Centro */
        .nav-row-1 { display: flex; justify-content: center; align-items: center; position: relative; }
        .logo-img { width: 36px; height: 36px; border-radius: 50%; position: absolute; left: 0; object-fit: contain; }
        .site-title { font-size: 1.4rem; font-weight: bold; color: var(--primary); margin: 0; }

        /* Fila 2: Índice a la izquierda (con scroll horizontal en celulares) */
        .nav-row-2 { 
            display: flex; justify-content: flex-start; align-items: center; gap: 8px; 
            overflow-x: auto; white-space: nowrap; padding-bottom: 4px; 
        }
        .nav-row-2::-webkit-scrollbar { height: 4px; }
        .nav-row-2::-webkit-scrollbar-thumb { background: var(--primary); border-radius: 4px; }
        .nav-row-2 a { text-decoration: none; color: var(--secondary); font-weight: 600; font-size: 0.9rem; padding: 6px 10px; border-radius: 4px; cursor: pointer; transition: background-color 0.2s; }
        .nav-row-2 a:hover, .nav-row-2 a.active { background-color: var(--primary); color: white; }

        /* Fila 3: Banderas a la derecha */
        .nav-row-3 { display: flex; justify-content: flex-end; align-items: center; gap: 8px; border-top: 1px solid rgba(0,0,0,0.06); padding-top: 6px; }
        
        .flag-btn { 
            background: transparent; border: 2px solid transparent; border-radius: 6px; 
            padding: 2px; cursor: pointer; text-decoration: none; display: inline-flex; 
            align-items: center; justify-content: center; transition: all 0.2s ease; 
        }
        .flag-btn:hover, .flag-btn.active-flag { 
            border-color: var(--primary); background: rgba(39, 174, 96, 0.1); transform: scale(1.12); 
        }
        .flag-icon-img { width: 34px; height: 24px; object-fit: contain; display: block; filter: drop-shadow(0 2px 3px rgba(0,0,0,0.2)); }

        .content-wrapper { 
            max-width: 950px; margin: 20px auto; background: rgba(255, 255, 255, 0.40); 
            backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
            padding: 25px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); 
            border: 1px solid rgba(255, 255, 255, 0.4); width: 90%; box-sizing: border-box; flex: 1;
        }

        .content-box { 
            background: rgba(255, 255, 255, 0.65); border: 1px solid rgba(226, 232, 240, 0.8); 
            border-radius: 8px; padding: 25px; box-shadow: 0 2px 6px rgba(0,0,0,0.02); margin-bottom: 20px;
        }

        /* Clases de texto para las páginas de contenido */
        .page-title { color: var(--primary); text-align: center; margin-top: 0; text-transform: uppercase; font-size: 1.5rem; }
        .page-subtitle { text-align: center; color: var(--secondary); margin-bottom: 15px; font-weight: normal; }
        .page-divider { border: 0; border-top: 1px solid rgba(0,0,0,0.1); margin: 15px 0; }
        .page-footer { text-align: center; color: var(--primary); margin-top: 25px; }
        .page-bullet { margin-bottom: 12px; line-height: 1.6; color: #333; font-size: 0.95rem; text-align: justify; }

        .section-content { display: none; }
        .section-content.active { display: block; }

        .calculator-section { margin-top: 5px; }
        label { font-weight: bold; display: block; margin-top: 8px; margin-bottom: 2px; font-size: 0.85rem; color: #2c3e50; }
        input[type="text"], input[type="number"], select, textarea { 
            width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; box-sizing: border-box; 
            font-size: 0.85rem; color: #333; background: rgba(255, 255, 255, 0.85);
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
        
        .editable-cell { width: 100%; padding: 4px; border: 1px solid transparent; background: transparent; text-align: center; font-size: 0.8rem; color: #1e293b; border-radius: 3px; }
        .editable-cell:hover, .editable-cell:focus { border-color: var(--primary); background: rgba(255, 255, 255, 0.95); outline: none; }

        .btn-save { background-color: #8e44ad; margin-top: 10px; color: white; padding: 10px; border: none; border-radius: 4px; width: 100%; font-weight: bold; cursor: pointer; font-size: 0.85rem; }
        .btn-save:hover { background-color: #71368a; }
        .btn-copy { background-color: #2980b9; margin-top: 6px; color: white; padding: 10px; border: none; border-radius: 4px; width: 100%; font-weight: bold; cursor: pointer; font-size: 0.85rem; }
        .btn-copy:hover { background-color: #1f6391; }
        
        .user-badge { background: rgba(224, 242, 254, 0.9); color: #0369a1; padding: 6px 10px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; display: inline-block; margin-bottom: 10px; }

        footer { 
            background: rgba(44, 62, 80, 0.92); backdrop-filter: blur(5px); color: white; 
            text-align: center; padding: 15px 20px 30px 20px; flex-shrink: 0; font-size: 0.8rem; margin-top: auto;
        }
        .footer-links { margin-bottom: 10px; display: flex; flex-wrap: wrap; justify-content: flex-start; align-items: center; gap: 12px; }
        .footer-link { color: white; text-decoration: none; padding: 6px; background: rgba(255,255,255,0.10); border-radius: 8px; transition: all 0.2s ease; display: inline-flex; align-items: center; justify-content: center; cursor: pointer; }
        .footer-link:hover { background: rgba(255,255,255,0.25); transform: translateY(-2px) scale(1.08); }
        .footer-icon-img { width: 38px; height: 38px; object-fit: contain; display: block; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3)); }
        .footer-info { opacity: 0.85; font-size: 0.75rem; text-align: left; margin-top: 5px; }
       
        @media (max-width: 500px) {
            .footer-links { 
                gap: 4px; /* Reduce el espacio entre logos */
                justify-content: center; 
            }
            .footer-link { 
                padding: 4px; /* Reduce el cuadro transparente de fondo */
            }
            .footer-icon-img { 
                width: 24px;  /* Achica el logo visualmente */
                height: 24px; 
            }
        }        
    
    </style>
</head>
<body>

<div id="loadingLang" data-var="_02_loading_lang" style="display:none; position:fixed; top:20px; right:20px; background:#2c3e50; color:white; padding:10px 15px; border-radius:8px; z-index:9999; font-size:0.85rem; box-shadow: 0 4px 10px rgba(0,0,0,0.2);">
    ⏳ Cargando idioma...
</div>

<header>
    <div class="nav-container">
        <!-- Renglón 1: Logo y Título -->
        <div class="nav-row-1">
            <img src="{{ url_for('static', filename='logo.png') }}" class="logo-img" alt="Logo" onerror="this.style.display='none'">
            <h1 class="site-title" data-var="_02_titulo_web">IA NutriBot</h1>
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
        <!-- Renglón 3: Banderas -->
        <div class="nav-row-3" id="langFlagsContainer"></div>
    </div>
</header>

<div class="content-wrapper">
    <!-- INICIO -->
    <div id="section-inicio" class="section-content active">
        <div class="content-box">
            <h2 class="page-title"><b data-var="_02_inicio_tit">BIENVENIDO A IA NUTRIBOT</b></h2>
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
            <h2 class="page-title"><b data-var="_02_ingreso_tit">INGRESO DE COMIDAS</b></h2>
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
            <h2 class="page-title"><b data-var="_02_salud_tit">SALUD, ACTIVIDAD Y PERFIL</b></h2>
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
            <h2 class="page-title"><b data-var="_02_info_tit">INFORMES, ESTADÍSTICAS Y CONTROL</b></h2>
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
            <h2 class="page-title"><b data-var="_02_pre_tit">COMIDAS PRECARGADAS Y CALCULADORA WEB</b></h2>
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
            <h2 class="page-title"><b data-var="_02_alta_tit">ALTA DE USUARIO Y PERFIL BIOMÉTRICO</b></h2>
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
            <h2 class="page-title"><b data-var="_02_cmd_tit">GUÍA COMPLETA DE COMANDOS</b></h2>
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
            <h2 class="page-title"><b data-var="_02_faq_tit">PREGUNTAS FRECUENTES (FAQ)</b></h2>
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
            <h2 class="page-title"><b data-var="_02_leg_tit">TÉRMINOS Y CONDICIONES</b></h2>
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
    <div class="footer-links">
        <a onclick="reproducirAudioguia()" class="footer-link" data-title="_02_title_audioguia" title="Audioguía">
            <img src="{{ url_for('static', filename='audioguia.png') }}" alt="Audioguía" class="footer-icon-img" onerror="this.outerHTML='<span style=\'font-size:24px; line-height:1;\'>🎧</span>'">
        </a>
        <a id="linkManual" href="#" target="_blank" class="footer-link" data-title="_02_title_manual" title="Manual (PDF)">
            <img src="{{ url_for('static', filename='manual.png') }}" alt="Manual" class="footer-icon-img" onerror="this.outerHTML='<span style=\'font-size:24px; line-height:1;\'>📖</span>'">
        </a>
        <a href="https://instagram.com/ianutribot" target="_blank" class="footer-link" title="Instagram">
            <img src="{{ url_for('static', filename='instagram.png') }}" alt="Instagram" class="footer-icon-img" onerror="this.outerHTML='<span style=\'font-size:24px; line-height:1;\'>📷</span>'">
        </a>
        <a href="https://twitter.com/ianutribot" target="_blank" class="footer-link" title="X (Twitter)">
            <img src="{{ url_for('static', filename='x.png') }}" alt="X" class="footer-icon-img" onerror="this.outerHTML='<span style=\'font-size:24px; line-height:1;\'>✖️</span>'">
        </a>
        <a href="https://tiktok.com/@ianutribot" target="_blank" class="footer-link" title="TikTok">
            <img src="{{ url_for('static', filename='tiktok.png') }}" alt="TikTok" class="footer-icon-img" onerror="this.outerHTML='<span style=\'font-size:24px; line-height:1;\'>🎵</span>'">
        </a>
        <a href="https://facebook.com/ianutribot" target="_blank" class="footer-link" title="Facebook">
            <img src="{{ url_for('static', filename='facebook.png') }}" alt="Facebook" class="footer-icon-img" onerror="this.outerHTML='<span style=\'font-size:24px; line-height:1;\'>📘</span>'">
        </a>
        <a href="https://youtube.com/@ianutribot" target="_blank" class="footer-link" title="YouTube">
            <img src="{{ url_for('static', filename='youtube.png') }}" alt="YouTube" class="footer-icon-img" onerror="this.outerHTML='<span style=\'font-size:24px; line-height:1;\'>▶️</span>'">
        </a>
        <a href="mailto:ianutribot@gmail.com" class="footer-link" title="Mail">
            <img src="{{ url_for('static', filename='mail.png') }}" alt="Mail" class="footer-icon-img" onerror="this.outerHTML='<span style=\'font-size:24px; line-height:1;\'>✉️</span>'">
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

#              INICIO                                  PÁGINA DE TÉRMINOS Y ALTA (WEB APP TRADUCIBLE)                   INICIO
# =====================================================================================================================================

HTML_TERMINOS_ALTA = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title data-var="_02_leg_tit">Términos y Condiciones - IA NutriBot</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root {
            --primary: #27ae60;
            --primary-dark: #219150;
            --secondary: #2c3e50;
            --bg-color: #f4f6f9;
            --text-color: #2c3e50;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            min-height: 100vh;
            box-sizing: border-box;
        }
        .container {
            max-width: 600px;
            margin: auto;
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        h2 {
            color: var(--primary);
            text-align: center;
            margin-top: 0;
        }
        .terms-box {
            max-height: 250px;
            overflow-y: auto;
            border: 1px solid #cbd5e1;
            padding: 15px;
            border-radius: 6px;
            background: #fafafa;
            font-size: 0.9rem;
            line-height: 1.5;
            margin-bottom: 20px;
        }
        .btn-accept {
            background-color: var(--primary);
            color: white;
            border: none;
            padding: 12px;
            width: 100%;
            border-radius: 6px;
            font-size: 1rem;
            font-weight: bold;
            cursor: pointer;
            transition: background 0.2s;
        }
        .btn-accept:hover {
            background-color: var(--primary-dark);
        }
        #loading {
            display: none;
            text-align: center;
            margin-top: 10px;
            font-style: italic;
            color: #7f8c8d;
        }
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
    <button class="btn-accept" id="btnAccept" onclick="aceptarTerminos()">✅ He leído y acepto los términos</button>
    <div id="loading">Registrando datos y conectando con el bot...</div>
</div>

<script>
    let tg = window.Telegram.WebApp;
    tg.expand();

    // Cargar idioma del usuario automáticamente al abrir la Web App
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
        
        // Capturar zona horaria exacta y ubicación
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
            console.log("No se pudo obtener geolocalización por IP.");
        }

        const urlParams = new URLSearchParams(window.location.search);
        const userId = urlParams.get('user_id');

        try {
            let response = await fetch('/api/guardar-terminos', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    pais: pais,
                    ciudad: ciudad,
                    zona_horaria: tz
                })
            });

            if (response.ok) {
                if (tg && tg.sendData) {
                    tg.sendData("aceptado");
                    tg.close();
                } else {
                    alert("Términos aceptados con éxito. Volvé a Telegram para continuar.");
                }
            } else {
                alert("Hubo un error al registrar la aceptación. Por favor, intentá de nuevo.");
                document.getElementById('loading').style.display = 'none';
            }
        } catch (err) {
            alert("Error de conexión: " + err.message);
            document.getElementById('loading').style.display = 'none';
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
        data = request.json
        user_id = data.get('user_id')
        pais = data.get('pais', 'Desconocido')
        ciudad = data.get('ciudad', 'Desconocida')
        zona_horaria = data.get('zona_horaria', 'America/Argentina/Buenos_Aires')

        if not user_id:
            return jsonify({"error": "Falta user_id"}), 400

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

        return jsonify({"message": "Términos guardados y ubicación registrada correctamente."}), 200
    except Exception as e:
        logger.error(f"Error en api_guardar_terminos: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

#              FINAL                                   PÁGINA DE TÉRMINOS Y ALTA (WEB APP TRADUCIBLE)                   FINAL
# =====================================================================================================================================

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
        codigo = data.get("codigo")
        descripcion = data.get("descripcion")
        receta = data.get("receta")
        tipo_calculo = data.get("tipoCalculo")
        porciones = int(data.get("porciones", 1))
        lang = data.get("lang", "es")

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
            resultado_json = json.loads(response.text)
            
        except Exception as e_prin:
            logger.warning(f"⚠️ Falla Principal Web ({MODELO_TEXTO}): {e_prin}. Pasando a Respaldo...")
            try:
                model_resp = genai.GenerativeModel(MODELO_RESPALDO, system_instruction=instruccion)
                response_resp = model_resp.generate_content(prompt_ia, generation_config=config_gen)
                resultado_json = json.loads(response_resp.text)
                
            except Exception as e_resp:
                logger.warning(f"⚠️ Falla Respaldo Web ({MODELO_RESPALDO}): {e_resp}. Pasando a Emergencia...")
                try:
                    model_emer = genai.GenerativeModel(MODELO_EMERGENCIA, system_instruction=instruccion)
                    response_emer = model_emer.generate_content(prompt_ia, generation_config=config_gen)
                    resultado_json = json.loads(response_emer.text)
                    
                except Exception as e_emer:
                    logger.error(f"❌ Fallaron todos los modelos web: {e_emer}")
                    return jsonify({"error": "No se pudo conectar con los servidores de Inteligencia Artificial."}), 500

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
        user_id = data.get('user_id')
        fila = data.get('fila')

        if not user_id or not fila:
            return jsonify({"error": "Faltan datos de usuario o de la receta."}), 400

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


