import os
import logging
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Configuración básica de logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot de Nutrición Activo 🍏"

# --- FUNCIÓN DE MANUAL REDISEÑADO CON REPORTLAB ---
def generar_pdf_manual(ruta_archivo):
    doc = SimpleDocTemplate(ruta_archivo, pagesize=letter,
                            rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elementos = []
    
    styles = getSampleStyleSheet()
    
    estilo_titulo = ParagraphStyle(
        'TituloModerno',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor("#1A5276"),
        spaceAfter=15,
        alignment=1
    )
    
    estilo_sub = ParagraphStyle(
        'SubModerno',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor("#2E86C1"),
        spaceBefore=12,
        spaceAfter=6
    )
    
    estilo_texto = ParagraphStyle(
        'TextoModerno',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor("#333333"),
        spaceAfter=6,
        leading=14
    )

    elementos.append(Paragraph("<b>📖 GUÍA VISUAL - BOT NUTRICIONAL 🍏</b>", estilo_titulo))
    elementos.append(Paragraph("¡Bienvenido a tu asistente de nutrición y salud! Aquí tienes el paso a paso súper resumido para usarlo sin vueltas.", estilo_texto))
    elementos.append(Spacer(1, 10))

    elementos.append(Paragraph("🚀 1. Comandos Principales", estilo_sub))
    
    comandos_data = [
        [Paragraph("<b>/start</b>", estilo_texto), Paragraph("🤖 Inicia el bot y reenvía este manual actualizado.", estilo_texto)],
        [Paragraph("<b>/comidas</b>", estilo_texto), Paragraph("📜 Muestra la lista de platos predeterminados y el PDF.", estilo_texto)],
        [Paragraph("<b>/presion</b>", estilo_texto), Paragraph("🩺 Registra presión (Ej: <i>/presion 120,80</i>) o ve el resumen.", estilo_texto)],
        [Paragraph("<b>/diario</b>", estilo_texto), Paragraph("📅 Consulta consumos del día con su reporte detallado.", estilo_texto)],
        [Paragraph("<b>/resumen</b>", estilo_texto), Paragraph("📊 Estadísticas mensuales de macronutrientes y TMB.", estilo_texto)],
        [Paragraph("<b>/perfil</b>", estilo_texto), Paragraph("⚙️ Actualiza tus datos corporales y métricas.", estilo_texto)]
    ]
    
    t_comandos = Table(comandos_data, colWidths=[90, 410])
    t_comandos.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EBF5FB")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#AED6F1"))
    ]))
    elementos.append(t_comandos)
    elementos.append(Spacer(1, 15))

    elementos.append(Paragraph("✍️ 2. Entrada de Datos y Multiplicadores", estilo_sub))
    
    datos_data = [
        [Paragraph("<b>⌨️ Texto Directo</b>", estilo_texto), Paragraph("Escribe tu plato o usa plantillas con multiplicadores.<br/><i>Ejemplos:</i> <b>*PIZZAJM, 4</b> o <b>*CHURRO, 0.5</b>", estilo_texto)],
        [Paragraph("<b>🎤 Voz y 📷 Foto</b>", estilo_texto), Paragraph("Mándale un audio contando lo que comiste o una foto directa de tu plato para que la IA lo analice.", estilo_texto)]
    ]
    
    t_datos = Table(datos_data, colWidths=[110, 390])
    t_datos.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EAFAF1")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#A9DFBF"))
    ]))
    elementos.append(t_datos)

    doc.build(elementos)

# --- LÓGICA DE PROCESAMIENTO DE EDICIÓN Y MULTIPLICADORES ---

def procesar_entrada_usuario(texto_usuario, peso_anterior_item):
    """
    Maneja las dos opciones de edición:
    1. Solo nombre: Mantiene el peso anterior y recalcula con IA.
    2. Nombre, peso_nuevo: Recalcula todo con la descripción y el nuevo peso.
    """
    texto_usuario = texto_usuario.strip()
    if "," in texto_usuario:
        partes = [p.strip() for p in texto_usuario.split(",", 1)]
        nuevo_nombre = partes[0]
        try:
            nuevo_peso = float(partes[1].replace("g", "").replace("gramos", "").strip().replace(",", "."))
        except ValueError:
            return None, None, "❌ Formato de peso inválido. Usá por ejemplo: Milanesa de carne, 150"
        return nuevo_nombre, nuevo_peso, "ok"
    else:
        nuevo_nombre = texto_usuario
        nuevo_peso = peso_anterior_item  # Mantiene el gramaje previo
        return nuevo_nombre, nuevo_peso, "ok"

def procesar_multiplicador_precargado(texto_input):
    """
    Interpreta correctamente multiplicadores enteros o decimales (ej: 4 o 0.5)
    en comandas con asterisco como *churro, 0.5 o *pizzajm,4
    """
    texto_input = texto_input.strip()
    if texto_input.startswith("*"):
        texto_input = texto_input[1:].strip()
    
    if "," in texto_input:
        partes = [p.strip() for p in texto_input.split(",", 1)]
        nombre_plato = partes[0]
        try:
            multiplicador = float(partes[1].replace(",", "."))
        except ValueError:
            multiplicador = 1.0
        return nombre_plato, multiplicador
    return texto_input, 1.0

# --- HANDLERS Y CONFIGURACIÓN DEL BOT ---

async def cmd_presion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🩺 Comando de presión recibido correctamente.")

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("No se encontró la variable TELEGRAM_TOKEN en el entorno.")
        return

    application = ApplicationBuilder().token(token).build()
    
    # Registro de comandos corregidos (sin tildes)
    application.add_handler(CommandHandler("presion", cmd_presion))

    # Iniciar servidor web y bot
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
