import os
import re
import logging
import requests
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# En la línea 10 de ayuda.py, agregá MODELO_EMERGENCIA al import:
from bot8a import (
    obtener_idioma_usuario, 
    obtener_traducciones_db, 
    MODELO_TEXTO, 
    MODELO_RESPALDO, 
    MODELO_EMERGENCIA, 
    registrar_curioso_preventa_db
)

logger = logging.getLogger(__name__)

# Cargamos ambas API Keys (Groq como principal ultrarrápido y Gemini como respaldo infalible)
API_KEY_GROQ = os.getenv("GROQ_API_KEY")
API_KEY_GEMINI = os.getenv("GEMINI_API_KEY_AYUDA") or os.getenv("GEMINI_API_KEY")

MANUAL_MARKDOWN = """
# 🍏 BIENVENIDO A IA NUTRIBOT
La forma más simple, rápida y segura de llevar el control de tu alimentación.
IA NutriBot revoluciona la forma en que registrás tus hábitos diarios. Diseñado para funcionar de manera intuitiva y sin fricciones, este asistente con Inteligencia Artificial te acompaña paso a paso, gestionando tus registros nutricionales directamente desde tu chat.

## 🌟 ¿Por qué elegir IA NutriBot? (Principales Ventajas)
* **Privacidad y Cero Datos Personales:** Tu tranquilidad es prioridad. El sistema se vincula a tu ID de Telegram sin pedirte un registro tradicional, contraseñas, ni correos electrónicos. Tampoco te solicitaremos documento de identidad, tarjetas de crédito ni información sensible. El alta se realiza únicamente con tus datos biométricos para los cálculos, y podés configurar un apodo en tu perfil.
* **Facilidad Total (Cero instalaciones):** Olvidate de descargar e instalar aplicaciones pesadas que piden permisos invasivos. IA NutriBot funciona 100% dentro de tu cuenta de Telegram.
* **Carga Inteligente y Natural:** Chau a las interminables listas de ingredientes. Para registrar tus comidas solo necesitás enviar una foto de tu plato, un mensaje de audio o un texto simple. La IA se encarga de analizar los alimentos y calcular automáticamente las calorías, fibras, hidratos, proteínas y grasas.
* **Control Integral de Salud y Actividad:** Cuenta con un módulo específico para registrar de forma rápida tu desgaste físico diario y llevar un seguimiento detallado de tu presión arterial. Toda esta información te permite generar resúmenes descargables en PDF.
* **Registro y Evolución Automática:** Toda tu información se guarda de forma segura para generar tu historial sin que tengas que anotar nada a mano. Además, el sistema genera informes de evolución automáticos (semanales y mensuales) que recibirás directamente en tu chat, incluyendo estimaciones de variación de peso.
* **Cálculos de Precisión Internacional:** Para procesar tus requerimientos, el sistema utiliza fórmulas validadas internacionalmente, como el método de la Marina de los Estados Unidos. Exclusivo para personas mayores de edad, el cálculo toma medidas corporales exactas como el cuello, la cintura y (en el caso de las mujeres) la cadera, garantizando estimaciones de máxima precisión científica.
* **Seguimiento Profesional Integrado:** Si realizás un tratamiento, podés ingresar el ID de Telegram de tu médico o nutricionista al registrarte. Esto le permitirá a tu profesional realizar un seguimiento de tu evolución al instante y de forma remota.

# 🍽️ 1. MÉTODOS DE REGISTRO DE INGESTAS
La Inteligencia Artificial a tu servicio para un registro natural y ultrarrápido. Para ingresar tus comidas diarias no necesitás navegar por menús complicados; el sistema está diseñado para entenderte de forma coloquial y procesar los datos nutricionales al instante.

## 📸 A. Ingreso Coloquial: Foto, Audio o Texto
La regla de oro es simple: cuantos más detalles le des a la IA, más exactos serán los cálculos.
* **Por Fotografía:** Podés enviar una foto directa de tu plato. Aunque la IA cuenta con un excelente reconocimiento visual, te recomendamos acompañar la imagen con una breve descripción en el mismo mensaje.
  * *Ejemplo práctico:* Si mandás una foto de empanadas, aclarale si son al horno o fritas, si el relleno es de carne, pollo o pescado, y si son caseras o compradas en rotisería. Si además conocés el peso exacto de tu porción, agregalo al texto para que el cálculo sea perfecto.
* **Por Nota de Voz:** Dictá tu ingesta mediante un audio. Hablá de forma completamente natural, detallando los alimentos y las cantidades estimadas o porciones. La IA convertirá automáticamente el audio a texto y procesará los datos nutricionales.
* **Por Texto Libre:** Escribí lo que comiste de forma coloquial, como si se lo contaras a un amigo (ejemplo: "2 huevos revueltos con 1 tostada integral y una taza de café con leche").

## 🏷️ B. Escaneo de Código de Barras o Empaques
¿Compraste un producto envasado? Tenés dos formas muy sencillas de registrarlo:
* **Foto al código de barras:** Enviá la foto del código de barras (o ingresá el número manualmente) y el sistema consultará la base de datos internacional. Si el fabricante cargó la información, te presentará el desglose por cada 100 gramos para que ajustes la porción exacta que vas a consumir.
* **Foto al frente del producto:** Si el código de barras no figura en la base de datos, ¡no hace falta que escribas todo a mano! Simplemente sacale una foto al frente del envase (por ejemplo, el frente de una lata de duraznos donde se vea claramente el producto y el peso neto impreso). La IA analizará la imagen y determinará los valores nutricionales automáticamente.

## 🚀 C. Registro Rápido con Planillas Precargadas
Si tenés comidas que repetís con frecuencia, no hace falta que se lo dictes a la IA cada mañana. El bot cuenta con un sistema donde podés guardar tus propias recetas o combinaciones habituales en una planilla personal precargada.
* Una vez que guardaste esa combinación bajo un código corto (por ejemplo, "desayuno"), registrarla te tomará un segundo.
* Solo tenés que enviarle al bot un asterisco (*) seguido del código de tu comida (ejemplo: *desayuno o *pizza).
* El sistema cargará todo tu plato al instante directamente a tu registro, sin necesidad de que la Inteligencia Artificial procese el texto.

# 💻 2. LA CALCULADORA NUTRICIONAL WEB
Creá, dividí y guardá tus propias recetas en tu base de datos personal. Si preparás platos elaborados con varios ingredientes (como una tarta, una pizza o una ensalada especial), no es necesario que calcules todo a mano. IA NutriBot cuenta con un módulo web interactivo para procesar tus recetas caseras y guardarlas para usarlas cuando quieras.
Para ingresar, simplemente enviá el comando **/receta** en tu chat de Telegram. El bot te responderá con un enlace web único y personalizado, vinculado exclusivamente a tu usuario.
Una vez dentro de la calculadora web, vas a completar los siguientes campos:
* **Código / Nombre:** Elegí un nombre corto con el que vas a invocar esta receta en el futuro (por ejemplo, DESAYUNO o TORTA).
  * *Carga inteligente:* Si utilizás una palabra clave que ya tenías registrada previamente (por ejemplo, si ya existía un DESAYUNO5), el sistema no borrará tu receta anterior, sino que le asignará correlativamente el siguiente número de forma automática (DESAYUNO6).
* **Descripción de la Comida:** Este es un texto libre de apoyo para que recuerdes de qué se trata el plato. Es fundamental utilizar palabras descriptivas claras (especificando si es pollo, carne, cerdo, pan integral, etc.). El sistema utiliza estas palabras clave para procesar correctamente tu resumen mensual y brindarte estadísticas precisas.
* **Ingredientes y Cantidades:** Detallá la lista completa de los componentes de tu receta, acompañados obligatoriamente de su cantidad exacta. (Ejemplo: 1 taza de café con leche, 2 tostadas de pan integral, 20g de mermelada).
* **Criterio de División (Porciones o Gramos):** Una vez que ingresás el total de la receta, el sistema te permite elegir cómo querés guardarla para su consumo:
  * *Dividir por cantidad de porciones:* Ideal para comidas como una pizza o una tarta entera. Simplemente indicá en cuántas porciones la cortaste y el sistema calculará los valores exactos de cada porción.
  * *Dividir de a 100 gramos:* Ideal para bizcochuelos o preparaciones por peso.

## 📋 Consultá tu Planilla Personal
Todas las recetas que guardes desde la calculadora web quedarán indexadas en tu cuenta para que las registres rápidamente con un asterisco (*) más el código. Si en algún momento querés ver la lista completa de todas las comidas que tenés guardadas, simplemente enviá el comando **/comidas** en el chat. El bot te dará acceso al detalle de tu planilla personalizada y te permitirá descargarla completa en formato PDF.

# ✏️ 3. CORRECCIONES Y GESTIÓN DE REGISTROS
Todos nos equivocamos, pero IA NutriBot es 100% flexible. Si ingresaste una comida en una fecha equivocada, o si guardaste una receta que ya no vas a usar y querés limpiar tu lista, el sistema cuenta con comandos específicos para corregir cualquier detalle al instante, sin complicaciones.

## 🗑️ A. Cómo borrar Ingestas o Actividades Físicas
Si te equivocaste al cargar tu desayuno de hoy, o si anotaste una actividad física en un día incorrecto, podés solucionarlo fácilmente con el comando **/eliminar**. Este comando te permite borrar registros de ingestas y actividades físicas de fechas pasadas mediante un menú totalmente interactivo:
1. Escribí **/eliminar** en el chat.
2. El bot te mostrará botones en pantalla para que selecciones primero el **Día**.
3. Luego, te pedirá que selecciones el **Momento** (por ejemplo, Almuerzo).
4. El sistema te presentará en pantalla el detalle exacto de todo lo que cargaste en ese momento específico.
5. Con un simple botón, vas a poder eliminar los ingresos uno por uno (de a una ingesta o actividad a la vez) para no borrar nada por accidente.
6. ¡Listo! Una vez borrado, podés volver a cargar tu comida de forma correcta.

## 🧹 B. Cómo limpiar tu lista de Comidas Precargadas
A medida que uses la Calculadora Nutricional, vas a ir guardando tus propias recetas con códigos personalizados. Si alguna de esas recetas te quedó mal calculada, si ya no la preparás más, o si simplemente querés que no te moleste en tu lista, podés borrarla de tu base de datos personal.
Para esto existe el comando **/borracomida**.
* Al utilizarlo, el sistema elimina permanentemente esa comida o receta predeterminada que hayas guardado previamente en tu planilla personal, manteniendo tu lista ordenada y actualizada solo con lo que realmente consumís.

# 📊 4. INFORMES, ESTADÍSTICAS Y CONTROL
Visualizá tu evolución con resúmenes detallados y reportes automáticos. IA NutriBot no solo acumula y guarda tus datos de forma segura, sino que los organiza para que entiendas tu progreso sin tener que hacer cuentas matemáticas. El sistema cuenta con reportes que llegan solos a tu chat y consultas manuales para cuando quieras ver tus números al instante.

## 📅 A. Reportes Nutricionales de Ingestas
**1. Reporte Diario (Comando /dia)**
Mientras que los informes semanales y mensuales te dan totales y promedios, el comando **/dia** te da el detalle fino.
* Podés elegir el día que quieras (hoy, ayer u otra fecha anterior) y el bot te mostrará exactamente qué comida ingresaste en las cuatro comidas principales.
* Además, genera un reporte específico en PDF con todo el detalle de tus alimentos para que lo descargues.

**2. Reporte Semanal (Comando /semana)**
* **Automático:** Se emite y envía a tu chat de forma automática todos los martes, siempre y cuando la semana anterior cuente con los 7 días completos de registro. Para que el día se considere válido, debe tener cargada al menos una comida principal y una secundaria, o bien dos comidas principales.
* **Manual:** Si solicitás este comando de martes a domingo, te mostrará en pantalla el avance de tu semana en curso. Si lo solicitás un lunes, el sistema entenderá que la semana ya cerró y te resumirá la semana anterior completa.

**3. Reporte Mensual (Comando /mes)**
* **Automático:** El bot lo emite de manera automática dos veces por mes: los días 20 (corte parcial) y los días 5 del mes siguiente (corte final). Condición importante: para que el reporte mensual automático se genere, es requisito indispensable contar con al menos 20 días de registros válidos en ese mes.
* **Manual:** Al pedirlo manualmente, el bot despliega botones interactivos para que elijas el mes exacto que querés consultar.
  * *Atención con los primeros días del mes:* Si solicitás este reporte antes del día 10 del mes en curso, el botón de ese mes no aparecerá en pantalla. Por ejemplo, si lo pedís el 2 de noviembre, el sistema te mostrará los botones de octubre, septiembre y una opción para buscar meses anteriores. Esto se debe a que un resumen mensual con menos de 10 días de registro no cuenta con los datos suficientes para evaluar tu evolución.

## ❤️ B. Reportes de Salud y Presión Arterial
Si utilizás el bot para llevar un control de tu tensión, también tenés acceso a un reporte exclusivo de salud para compartir con tu médico de cabecera.

**Control de Presión (Comando /presi)**
Además de usar este comando para registrar nuevas mediciones de forma manual, sirve para consultar tu historial.
* Al realizar una consulta mensual (ingresando el año y el mes), el bot te mostrará en pantalla el promedio de tus mediciones de ese periodo.
* Lo más importante: te dará la opción de descargar un PDF detallado con todas las tomas exactas día por día.

# 🏃‍♂️ 5. SALUD Y ACTIVIDAD FÍSICA
La Inteligencia Artificial también calcula tu gasto calórico y lee tus mediciones médicas. IA NutriBot no solo gestiona tus comidas, sino que integra de forma inteligente tus métricas de salud y tu desgaste físico diario. Al igual que con las ingestas, el registro es natural, rápido y sin estructuras rígidas.

## ❤️ A. Registro de Presión Arterial
Además del ingreso manual tradicional (escribiendo los valores), IA NutriBot ofrece una función inteligente mucho más directa:
* **Foto al tensiómetro:** Simplemente sacale una foto a la pantalla de tu tensiómetro digital y enviala al chat.
* **Lectura Automática:** La Inteligencia Artificial leerá los números automáticamente (presión máxima, mínima y pulso) y te los presentará ordenados en la pantalla.
* **Confirmación:** Allí tendrás botones interactivos para **Guardar** el registro, **Cancelar** (si hubo algún error en la lectura de la foto) o agregar una **Nota** aclaratoria (por ejemplo, "medición después de caminar") antes de asentar los datos en tu historial mensual.

## 🚴 B. Registro e Historial de Actividad Física
Para cargar tu deporte o desgaste físico del día, IA NutriBot te ofrece dos caminos: dejar que la Inteligencia Artificial estime tu gasto (con opción a corregirlo), o ingresar vos mismo el valor exacto si ya lo conocés. Además, contás con una herramienta para descargar todos tus entrenamientos del mes.

**1. Carga Inteligente (Con cálculo de la IA)**
Si preferís que el sistema estime las calorías por vos, podés hacerlo de forma natural.
* **Por Texto o Voz libre:** Mandá un audio o un mensaje de texto directamente al chat contándole a la IA qué ejercicio hiciste.
* **La regla para un cálculo exacto:** Asegurate de indicarle siempre el tiempo (minutos de duración), el tipo de ejercicio y la intensidad del mismo.
* **Cálculo Biométrico y Edición:** La IA cruzará esos datos con tus parámetros físicos personales y calculará tu gasto calórico aproximado. Antes de guardarlo, el sistema te mostrará un menú rápido en pantalla; allí podrás validar el cálculo propuesto por la IA o editar el valor manualmente si considerás que fue mayor o menor, dándote siempre el control final.

**2. Carga Manual Exacta (Menú Interactivo)**
¿Ya usás un reloj inteligente o una aplicación de fitness y sabés exactamente cuántas calorías gastaste? Podés hacer un registro manual directo, salteando por completo el análisis de la IA, mediante un menú guiado.
* **Comando /actividad:** Simplemente enviá el comando **/actividad** solo en el chat.
* El bot desplegará un menú interactivo que te irá pidiendo los datos paso a paso. Primero te solicitará los minutos de duración, luego las calorías consumidas, y finalmente una breve descripción del ejercicio.
* **Control lógico de seguridad:** Al igual que en todos los registros, el sistema cuenta con una validación interna automática. Si ingresás valores ilógicos por error de tipeo (como 10.000 calorías), el sistema rechazará la carga para proteger la exactitud de tu historial.

**3. Cómo consultar tu Historial Mensual y descargar el PDF**
Así como podés ver tus reportes de presión arterial, es clave tener un historial de cuánto te moviste en el mes.
* **Comando /actividad mes:** Al enviar este comando, el bot desplegará un menú interactivo para que selecciones el mes que querés consultar.
* **Promedio Mensual en Pantalla:** El sistema te presentará en pantalla un dato clave: el promedio de minutos diarios de actividad. Este promedio se calcula dividiendo el total de minutos de ejercicio realizados por la cantidad total de días del mes (no solo por los días que entrenaste). Esto te permite evaluar de forma realista si estás cumpliendo tu objetivo mensual de movimiento.
* **Detalle en PDF:** Además del resumen en pantalla, vas a tener la opción de descargar un archivo PDF con el detalle exacto, día por día, de todos tus entrenamientos de ese mes.

## ⚖️ C. Actualización Mensual del Peso (Comando /peso)
IA NutriBot funciona en base a tu peso actual para realizar sus cálculos metabólicos de precisión. Por este motivo, es un requisito actualizar tu peso todos los meses utilizando el comando **/peso** seguido del valor (por ejemplo: **/peso 75.5**).
* **¿Qué pasa si me olvido de actualizarlo a principio de mes?** El sistema no te bloqueará: vas a poder seguir registrando tus comidas, tus actividades y usar el comando diario sin problemas. Sin embargo, la emisión de tus reportes de evolución quedará temporalmente suspendida. El informe semanal no se enviará y los reportes mensuales del mes en curso tampoco se generarán hasta que actualices este dato clave.
* **Flexibilidad de carga (La regla del día 25):** Sabemos que pesarse exactamente el día 1 o 2 de cada mes puede ser incómodo. Por eso, el bot cuenta con un sistema inteligente de flexibilidad: si actualizás tu peso a partir del día 25 del mes anterior, el sistema lo tomará automáticamente como válido para todo el mes siguiente. ¡No hace falta que vuelvas a la balanza justo el día 1!

# 🔔 6. MONITOREO PROACTIVO Y AVISOS AUTOMÁTICOS
Un asistente que te ayuda a mantener la constancia sin invadir tu rutina. Para que tus estadísticas sean exactas, la constancia en el registro es fundamental. IA NutriBot no espera a que te equivoques o te olvides; trabaja de fondo para ayudarte a mantener tu historial completo mediante un sistema de recordatorios amigables y automáticos.

## 🍽️ A. Control de Ingestas Faltantes
A veces el día a día nos supera y es normal olvidarse de anotar una comida. Para que no pierdas el hilo, el bot realiza un relevamiento automático de tu actividad dos veces al día:
* Por la mañana: Evalúa tus registros de los dos días anteriores completos.
* Por la tarde: Evalúa el día en curso y el día anterior.
Si el sistema detecta que te falta cargar alguna de las cuatro comidas principales (desayuno, almuerzo, merienda o cena) en esas últimas 48 horas, te enviará un recordatorio proactivo directamente a tu chat (por ejemplo: *"Falta registrar la cena del día de ayer"*). Así podrás actualizar tu planilla a tiempo y evitar baches en tus reportes.

## ❤️ B. Recordatorio Semanal de Presión Arterial
Tomarse la presión arterial regularmente es un excelente hábito para prevenir problemas de salud y llevar un control preventivo.
* **Aviso Preventivo:** Una vez por semana, el bot evalúa tu historial reciente. Si nota que no realizaste ningún control de presión arterial durante la semana pasada, te enviará un mensaje recordatorio.
* No es obligatorio hacerlo, pero el sistema te incentiva a mantener esta buena costumbre para que, si tu médico te lo pide, tengas siempre a mano un historial mensual completo.

# 🚀 7. ALTA, CONFIGURACIÓN Y GLOSARIO DE COMANDOS
El proceso de alta es el único paso en todo IA NutriBot que te va a tomar un par de minutos. Es una configuración que se hace una sola vez. A partir de ahí, todas tus cargas diarias, consultas y comandos se resolverán en cuestión de segundos.

## A. Cómo configurar tu perfil (Comando /alta)
Para comenzar a usar el sistema por primera vez, enviá el comando **/alta** y el asistente te irá guiando paso a paso:
* **Términos y Condiciones:** El primer paso será leer y aceptar las condiciones de uso del sistema.
* **Datos Básicos y Biométricos:** El bot te pedirá un apodo o nombre (con ingresar dos letras es suficiente, no tiene ninguna importancia ni requiere ser tu nombre real) y tu fecha de nacimiento o edad. Luego, te solicitará tus medidas corporales para aplicar las fórmulas internacionales: altura, peso actual, cuello, cintura (y cadera en el caso de las mujeres).
* **Nivel de Actividad Diaria (¡Muy importante!):** Este es un punto clave para la exactitud del cálculo. El sistema te preguntará por tu nivel de actividad laboral o de rutina diaria, excluyendo el deporte.
  * *Ejemplo 1:* Un oficinista que trabaja sentado todo el día, pero va 5 veces por semana al gimnasio, debe elegir actividad Sedentaria. El entrenamiento en el gimnasio se carga aparte utilizando el módulo de actividad física.
  * *Ejemplo 2:* Un albañil o un repartidor que no va al gimnasio, pero tiene un trabajo de alto desgaste físico diario, no es sedentario y debe seleccionar un nivel de actividad mayor.
* **Intensidad del Plan:** Finalmente, el sistema te pedirá que definas la intensidad de tu objetivo (Liviano, Moderado o Fuerte). En base a esta elección, el bot calculará y te propondrá los pesos objetivo para cada etapa de tu evolución.
Una vez completados estos pasos, tu cuenta quedará activa. Si en el futuro necesitás revisar o actualizar tu configuración, podés hacerlo enviando el comando **/perfil**.

## 📖 B. Glosario Rápido de Comandos del Bot
Esta guía resume brevemente la función principal de cada comando disponible en el sistema. Está diseñada como referencia rápida.
* **/alta:** Proceso inicial para configurar tus datos biométricos. Es el único paso que toma unos minutos; luego el sistema funciona en segundos. Es 100% sin pedir datos personales sensibles.
* **/perfil:** Pantalla interactiva que muestra tus datos biométricos actuales y los parámetros configurados en tu cuenta. Contiene el menú para actualizarlos.
* **/peso:** Comando de acceso rápido para la actualización mensual del peso, dato fundamental para los cálculos del bot.
* **/dia:** Muestra el resumen de calorías y macros del día solicitado. Permite descargar un reporte detallado en PDF de las ingestas registradas.
* **/semana:** Muestra el balance detallado y el resumen nutricional correspondiente a los días pasados de la semana. Ideal para evaluar los resultados generales del período previo.
* **/mes:** Muestra el balance consolidado del mes solicitado y evalúa el cumplimiento del objetivo mensual de registros. Es el reporte clave para revisar tu constancia a largo plazo.
* **/presi:** Permite registrar manualmente la medición de la presión arterial o solicitar el reporte de un mes específico, generando un informe en PDF.
* **/barra:** Permite ingresar de forma manual los números del código de barras de un producto para registrarlo rápidamente en el sistema.
* **/actividad:** Despliega un menú guiado para registrar actividad física de forma manual, o calcular el promedio mensual y descargar el resumen en PDF al usar /actividad mes.
* **/eliminar:** Permite borrar cualquier registro mediante botones interactivos, seleccionando previamente el día y el momento correspondiente.
* **/comidas:** Muestra en pantalla las comidas guardadas en las planillas precargadas y permite descargar un archivo PDF con dicho listado.
* **/receta:** Genera un acceso a la calculadora web para crear recetas personalizadas y registrar preparaciones habituales de forma rápida.
* **/borracomida:** Elimina permanentemente una comida o receta predeterminada que hayas guardado en tu planilla personal, manteniendo tu lista ordenada.
* **/x:** Comando comodín que te permite cancelar cualquier acción o registro en curso que estés realizando con el bot.
* **/ayuda:** Muestra en pantalla un resumen completo y compacto (ideal para leer desde el celular) con el listado y la descripción de todas las funciones del bot. Además, funciona como tu **asistente de soporte técnico virtual**: si escribís el comando seguido de tu consulta (por ejemplo, "/ayuda ¿cómo elimino una comida?"), la Inteligencia Artificial consultará este manual internamente y te responderá la duda al instante. Desde este comando también podés descargar este manual completo en formato PDF (en el idioma en que tengas configurado el bot).

## ⚠️ ADVERTENCIA MÉDICA IMPORTANTE
IA NutriBot es una herramienta avanzada de cálculo automatizado orientada a sumar y restar calorías de forma práctica. El asistente no emite consejos, dietas ni recomendaciones médicas. Su función se limita estrictamente a brindar información y estimaciones cuantitativas basadas en tablas internacionales de nutrición. Todo seguimiento clínico o nutricional formal debe ser realizado exclusivamente por un profesional de la salud competente.
"""
def transcribir_audio_groq(audio_bytes: bytes) -> str:
    """
    Transcribe el audio de Telegram usando Whisper en Groq (aislado del motor de comidas).
    """
    if not API_KEY_GROQ:
        raise Exception("GROQ_API_KEY no configurada para transcribir audio de ayuda.")

    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {API_KEY_GROQ}"}
    files = {
        "file": ("consulta.ogg", bytes(audio_bytes), "audio/ogg")
    }
    data = {
        "model": "whisper-large-v3-turbo",
        "language": "es",
        "response_format": "json"
    }
    response = requests.post(url, headers=headers, files=files, data=data, timeout=15)
    if response.status_code == 200:
        return response.json().get("text", "").strip()
    else:
        logger.warning(f"Error transcribiendo audio en Groq Ayuda: {response.text}")
        raise Exception("Fallo en transcripción de audio de ayuda")

def solicitar_ai_rest(consulta, lang='es'):
    """
    Intenta responder primero con Groq (modelos actualizados).
    Si Groq no está configurado o falla, pasa automáticamente a Gemini REST.
    """
    system_instruction = (
        "Sos el asistente de soporte técnico oficial de IA NutriBot. "
        f"REGLA DE IDIOMA ESTRICTA: El usuario habla el idioma con código ISO '{lang}'. "
        f"DEBES responder y traducir toda tu explicación ÚNICAMENTE al idioma '{lang}'. No uses palabras en español si el idioma no es español.\n"
        "Tu única tarea es responder la consulta del usuario basándote EXCLUSIVAMENTE en el siguiente manual. "
        "Si la respuesta no está en el manual, indicá amablemente que contacte al soporte técnico o al administrador. "
        "Sé claro, conciso, amable y utilizá un tono coloquial. "
        "Usá formato simple (negritas con un solo asterisco *texto* y viñetas con •), sin inventar comandos ni funciones.\n"
        "REGLA DE CIERRE: NO agregues frases de despedida genéricas (como 'Estaré aquí para ayudarte' o 'Cualquier otra duda me avisas'). Termina tu respuesta directamente con la información técnica.\n\n"
        f"MANUAL OFICIAL:\n{MANUAL_MARKDOWN}"
    )

    # 1. INTENTO CON GROQ (Si existe GROQ_API_KEY)
    if API_KEY_GROQ:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY_GROQ}"
        }
        # Modelos vigentes en Groq
        modelos_groq = [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant"
        ]
        
        for modelo in modelos_groq:
            payload = {
                "model": modelo,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": consulta}
                ],
                "temperature": 0.2
            }
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    return data['choices'][0]['message']['content']
                else:
                    logger.warning(f"Fallo en API Groq Ayuda con modelo {modelo}: {response.text}")
            except Exception as e:
                logger.warning(f"Error de conexión con Groq ({modelo}): {e}")

    # 2. RESPALDO AUTOMÁTICO CON GEMINI REST
    if API_KEY_GEMINI:
        return solicitar_ai_rest_Gemini(consulta, system_instruction)

    raise Exception("No se pudo responder ni con Groq ni con Gemini (verificar API Keys).")

async def procesar_audio_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Recibe el audio desviado desde bot8.py cuando el usuario está en modo /ayuda,
    lo transcribe y responde la duda con el manual.
    """
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    msg_espera_txt = traducciones.get("09_ayuda_escuchando", "🎧 Escuchando tu consulta y buscando en el manual...")
    msg_espera = await update.message.reply_text(msg_espera_txt, parse_mode="Markdown")

    try:
        file = await context.bot.get_file(update.message.voice.file_id)
        audio_bytes = await file.download_as_bytearray()

        # 1. Transcribimos el audio en Groq
        consulta_texto = await asyncio.to_thread(transcribir_audio_groq, audio_bytes)
        if not consulta_texto:
            msg_error_audio = traducciones.get("09_ayuda_error_audio", "⚠️ No pude escuchar bien el audio. Intentá de nuevo o escribí tu consulta.")
            await msg_espera.edit_text(msg_error_audio)
            return

        # 2. Consultamos el manual con el texto transcripto PASANDO EL IDIOMA
        respuesta_ia = await asyncio.to_thread(solicitar_ai_rest, consulta_texto, lang)
        
        etiqueta_consulta = traducciones.get("09_ayuda_etiqueta_consulta", "Tu consulta")
        txt_cierre = traducciones.get("09_ayuda_cierre_h", "\n\n💡 *Para realizar otra consulta, volvé a enviar el comando /h o /soporte.*")
        
        respuesta_limpia = f"🗣️ *{etiqueta_consulta}:* _{consulta_texto}_\n\n" + respuesta_ia.replace("**", "*") + txt_cierre

        try:
            await msg_espera.edit_text(respuesta_limpia, parse_mode="Markdown")
        except Exception:
            await msg_espera.edit_text(respuesta_limpia.replace("*", "").replace("_", ""))

    except Exception as e:
        logger.error(f"Error procesando audio en /ayuda: {e}")
        msg_error_procesar = traducciones.get("09_ayuda_error_procesar_audio", "❌ Ocurrió un error al procesar el audio de ayuda. Intentá escribiendo `/h tu consulta`.")
        await msg_espera.edit_text(msg_error_procesar)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la guía estática y el botón de descarga del manual en PDF, unificando /start y /ayuda."""
    user = update.effective_user
    user_id = user.id
    
    # Capturamos al curioso apenas pisa el bot
    nombre_tg = user.first_name or ""
    username_tg = f"@{user.username}" if user.username else ""
    await asyncio.to_thread(registrar_curioso_preventa_db, user_id, nombre_tg, username_tg, "cmd_start")
    
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    # Usamos directamente la variable de ayuda que ya está unificada
    texto_ayuda = traducciones.get('09_ayuda_mensaje_guia', 
        "👋 *¡Guía rápida de comandos e ingresos disponibles!*\n\n"
        "📌 *Comandos Principales:*\n"
        "• `/actividad`: Promedio del mes. Informe en PDF.\n"
        "• `/alta`: Apertura de cuenta ingresando los datos.\n"
        "• `/ayuda`: Resumen de comandos y manual en PDF.\n"
        "• `/barra`: Ingresa por código de barras un comestible.\n"
        "• `/borracomida`: Borra una comida de la Planilla.\n"
        "• `/comidas`: Planilla de comidas pre-cargadas y PDF.\n"
        "• `/dia`: Ingestas seleccionando por teclado y PDF.\n"
        "• `/eliminar`: Borra ingestas y actividades.\n"
        "• `/mes`: Reporte mensual de calorías y PDF.\n"
        "• `/pago`: Elegir el plan o promoción de pago vigente.\n"
        "• `/perfil`: Actualización de datos biométricos.\n"
        "• `/peso`: Registro o control de peso mensual.\n"
        "• `/presi`: Registro y consulta de presión arterial.\n"
        "• `/receta`: Calculadora Web para registrar comidas.\n"
        "• `/semana`: Estadística semanal (calorías, fibras, etc.).\n\n"
        "• `/h`: Consular el manual a la IA.\n"
        "• `/x`: Cancelar último comando.\n\n"
        "📌 *Métodos de Registro y consultas directas:*\n"
        "• *Ingestas con IA:* 📝 Texto, 🎤 Audio, 📸 Foto.\n"
        "• *Ingestas con IA:* 📸 Foto de un código de barras.\n"
        "• *Ingestas sin IA:* 📝 Planilla precargada .\n"
        "• *Presión arterial:* 📸 Foto del tensiómetro digital.\n"
        "• *Actividad física:* 📝 Texto o 🎤 Audio.\n"
        "🤖 *Asistente Virtual Inteligente:*\n"
        "Si tenés una duda técnica sobre cómo usar el bot, preguntame directamente escribiendo el comando `/h` seguido de tu consulta.\n"
        "👉 *Ejemplo:* `/h ¿cómo borro un desayuno?`\n\n"
        "📄 También podés descargar el manual completo en PDF acá abajo:"
    ).replace('\\n', '\n')
    
    import re
    texto_final = re.sub(r'\n{2,}', '\n\n', texto_ayuda)
    
    btn_manual_txt = traducciones.get('09_btn_descargar_manual', "📄 Descargar Manual Completo en PDF")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_manual_txt, callback_data=f"descargar_manual_user_{lang}")]
    ])
    
    await update.message.reply_text(texto_final, reply_markup=keyboard, parse_mode="Markdown")

async def callback_descargar_manual_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    # Convertimos a minúsculas para igualar el formato de la carpeta static (ej: static/es.pdf)
    lang_code = query.data.replace("descargar_manual_user_", "").strip().lower()
    pdf_filename = f"{lang_code}.pdf"
    
    # Buscamos primero en static/ y luego en la raíz como respaldo
    rutas_posibles = [
        os.path.join("static", pdf_filename),
        pdf_filename,
        os.path.join("static", "es.pdf"),
        "es.pdf",
        os.path.join("static", "manual.pdf")
    ]
    
    ruta_encontrada = next((r for r in rutas_posibles if os.path.exists(r)), None)
        
    try:
        if ruta_encontrada:
            txt_caption = traducciones.get("09_manual_usuario_caption", "📄 **Manual de Usuario**")
            with open(ruta_encontrada, 'rb') as f_pdf:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=f_pdf,
                    filename=f"Manual_IA_NutriBot_{lang_code.upper()}.pdf",
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
        
def solicitar_ai_rest_Gemini(consulta, system_instruction):
    """
    Respaldo aislado por REST API a Google Gemini usando exclusivamente la línea 3.x definida en bot8a.py.
    """
    modelos_gemini = [MODELO_TEXTO, MODELO_RESPALDO, MODELO_EMERGENCIA]
    
    payload = {
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"parts": [{"text": consulta}]}],
        "generationConfig": {"temperature": 0.2}
    }

    for mod in modelos_gemini:
        if not mod:
            continue
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={API_KEY_GEMINI}"
        try:
            response = requests.post(url, json=payload, timeout=15)
            if response.status_code == 200:
                data = response.json()
                return data['candidates'][0]['content']['parts'][0]['text']
            else:
                logger.warning(f"Error en API Gemini Ayuda ({mod}): {response.text}")
        except Exception as e:
            logger.warning(f"Excepción en API Gemini Ayuda ({mod}): {e}")

    raise Exception("Fallo en todos los modelos de respaldo de Google Gemini")
    
async def cmd_soporte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Activa de inmediato la bandera de escucha/texto exclusivo para hablar con la IA de soporte."""
    user_id = update.effective_user.id
    lang = obtener_idioma_usuario(user_id) or 'es'
    traducciones = obtener_traducciones_db(lang) or {}

    # Activamos la bandera exclusiva
    context.user_data['esperando_consulta_ayuda'] = True

    msg_bienvenida = traducciones.get('09_soporte_bienvenida', 
        "🤖 **Asistente de Soporte Técnico IA NutriBot**\n\n"
        "🎙️ **Grabá un mensaje de audio** contándome tu duda o **escribila acá abajo**.\n"
        "Te responderé al instante basándome en el manual oficial.\n\n"
        "*(Si querés salir de este modo sin consultar nada, escribí `/x`)*"
    ).replace('\\n', '\n')

    await update.message.reply_text(msg_bienvenida, parse_mode="Markdown")

    
