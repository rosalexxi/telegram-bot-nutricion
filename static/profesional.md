# IA NutriBot: Ecosistema de Supervisión Clínica y Gestión Automatizada

*Documento Confidencial y Exclusivo para Profesionales de la Salud*

El seguimiento nutricional tradicional enfrenta dos problemas críticos: la falta de adherencia del paciente y la saturación del profesional a través de consultas informales por WhatsApp. **IA NutriBot** transforma radicalmente esta dinámica. Hemos desarrollado una plataforma de asistencia basada en Inteligencia Artificial que opera de forma nativa dentro de Telegram, diseñada para automatizar la captura de datos del paciente, proteger el tiempo del profesional y respaldar el trabajo administrativo ante prepagas y obras sociales.

La herramienta convierte el smartphone del paciente en un diario alimentario de precisión y le entrega al profesional un panel de control consolidado, eliminando la necesidad de cálculos manuales y planillas de Excel.

### 1. Propuesta de Valor y Beneficios Clave

* **Supremacía Clínica Absoluta:** La inteligencia artificial asiste en el cálculo, pero el criterio del profesional rige el sistema. Cualquier valor de requerimiento calórico (GET, TMB) o macronutriente configurado por el profesional reemplaza automáticamente a las fórmulas estándar del bot.
* **Comunicación Unidireccional (Fin del "WhatsApp personal"):** IA NutriBot permite enviar indicaciones directas al teléfono del paciente, pero bloquea las respuestas informales hacia el profesional. Se mantiene la autoridad clínica y se recupera el tiempo personal, ordenando la relación médico-paciente.
* **Monitoreo Pasivo y Alertas Tempranas:** No es necesario revisar cientos de planillas a diario. El bot audita continuamente los balances netos de sus pacientes. Si un paciente consume por debajo de su mínimo o excede su máximo establecido, el sistema envía una alerta automática y directa al teléfono del profesional.
* **Burocracia y Facturación Resueltas:** El sistema genera documentación con formato de historia clínica (epicrisis) en segundos, lista para ser firmada y presentada ante obras sociales o prepagas para justificar y monetizar el seguimiento.

### 2. Dinámica del Panel de Control

El ecosistema se gestiona de forma intuitiva mediante comandos rápidos y botones táctiles interactivos en su propia aplicación de Telegram, sin requerir la instalación de software externo.

El profesional cuenta con herramientas para:
* **Control Clínico y Metas:** Personalizar rangos nutricionales y escanear en tiempo real (Triage) a los pacientes que presentan desvíos.
* **Gestión de Pacientes:** Generar reportes consolidados semestrales en PDF y auditar los cierres mensuales de cada paciente antes de que los reciban.
* **Comunicación Inteligente:** Enviar indicaciones médicas privadas (unidireccionales) o lanzar anuncios masivos a toda su cartera simultáneamente.
* **Documentación Oficial:** Emitir resúmenes de historia clínica en formato de texto editable, ideales para incorporar su membrete y presentar en prepagas.

### 3. Implementación y Privacidad

El alta de pacientes está diseñada para eliminar barreras de fricción. Cuando un paciente inicia su registro en IA NutriBot, simplemente ingresa el **ID de Profesional** que usted le proporcionará.

Usted recibirá una notificación instantánea con los datos biométricos iniciales del paciente (peso, altura) y la opción de **Aceptar o Rechazar** la supervisión. Al aceptar, el sistema generará los rangos base iniciales y el paciente quedará vinculado de forma confidencial a su panel de control. Todo el procesamiento de datos se realiza resguardando el anonimato del usuario y focalizándose estrictamente en la métrica biométrica.

IA NutriBot no reemplaza el criterio del especialista; lo potencia, automatizando el desgaste operativo para que usted pueda enfocarse exclusivamente en la toma de decisiones clínicas.

---

### 4. Glosario de Comandos Profesionales (Quick Reference)

* **`/valores`**: Despliega el panel interactivo para ajustar manualmente las metas clínicas del paciente (TMB, GET, macronutrientes y peso objetivo).
* **`/alertas`**: Ejecuta un escáner en vivo y reporta únicamente a los pacientes con desvíos (exceso calórico, déficit o inactividad).
* **`/pacientes`**: Genera un PDF con el historial clínico consolidado (últimos 6 meses) de toda su cartera de pacientes.
* **`/informe`**: Permite auditar y enviar el reporte mensual individual a un paciente, con opción de adjuntar observaciones médicas.
* **`/nota`**: Envía indicaciones o correcciones de dieta a un paciente de forma unidireccional (sin respuesta).
* **`/anuncio`** (o `/notageneral`): Envía un mensaje masivo a todos los pacientes activos simultáneamente.
* **`/epicrisis`** (o `/obrasocial`): Genera un resumen de historia clínica editable en Markdown (.md, compatible con Word) para prepagas y obras sociales.
* **`/manual`**: Muestra este resumen en pantalla y adjunta el manual operativo completo en PDF.

---

# 🍏 GUÍA DE USUARIO — IA NUTRIBOT

Asistente nutricional con Inteligencia Artificial que funciona 100% dentro de Telegram, sin instalaciones, contraseñas, correos, DNI ni tarjetas.

## 🌟 Principales Ventajas
* **Privacidad:** Registro anónimo vinculado solo al ID de Telegram y datos biométricos (puede usarse un apodo).
* **Carga Inteligente:** Calcula calorías, proteínas, hidratos, grasas y fibras desde foto, audio o texto.
* **Salud y Actividad:** Registro de actividad física y presión arterial con reportes en PDF.
* **Cálculos de Precisión:** Usa fórmulas validadas (método Marina de EE.UU. para adultos con cuello, cintura y cadera en mujeres).
* **Seguimiento Profesional:** Permite vincular el ID de Telegram del médico o nutricionista al darse de alta.

# 🍽️ 1. MÉTODOS DE REGISTRO DE INGESTAS

## 📸 A. Ingreso con IA: Foto, Audio o Texto
Cuantos más detalles se den a la IA, más exacto es el cálculo.
* **Por Foto:** Enviar foto del plato acompañada idealmente de una breve descripción (ej: empanadas al horno o fritas, relleno, caseras o compradas, peso si se conoce).
  * ⚠️ **Múltiples fotos:** Si se envían varias fotos juntas en simultáneo (ej: 5 fotos), el bot procesa cada una descontando 5 unidades del cupo diario de fotos con IA, pero cada imagen sobrescribe la memoria temporal (`pending_items`). Al tocar Guardar (💾) **solo se guarda la última foto analizada**. Si se intenta guardar un cartel anterior, responderá *"❌ No se encontraron datos para guardar"*. Enviar siempre las fotos de a una.
* **Por Audio:** Dictar naturalmente qué se comió y las cantidades.
* **Por Texto:** Escribir de forma coloquial (ej: "2 huevos revueltos con 1 tostada integral y café con leche").

## 🏷️ B. Código de Barras y Empaques
* **Código de barras:** Enviar foto del código o escribir `/barra [número]`. Si existe en la base internacional, muestra valores cada 100g para ajustar la porción.
* **Frente del envase:** Si el código no figura, enviar foto del frente del paquete donde se vea el producto y peso neto para que la IA lo calcule.

## 🚀 C. Comidas Precargadas (`*CODIGO`)
Las recetas guardadas en la planilla personal se registran al instante sin IA enviando `*` seguido del código (ej: `*desayuno` o `*pizza`).

## ✍️ D. Ingreso Manual (Sin IA — `/menu` o `/ingesta`)
Registro manual ilimitado con 4 datos separados por coma:
`/menu [Descripción], [Peso en g], [Calorías], [Proteínas en g]` (ej: `/menu 2 Tostadas con mermelada, 100, 250, 5`).
* La descripción requiere mínimo 10 caracteres; se puede poner `0` en valores desconocidos.
* No incluye botón de editar (📝): si hay error, tocar ❌ y reenviar.

# 💻 2. CALCULADORA NUTRICIONAL WEB (`/receta`)

El comando `/receta` genera un enlace web personal (expira en 1 hora) para calcular y guardar recetas caseras:
* **Código / Nombre:** Clave corta (ej: `TORTA`). Si ya existe (ej: `DESAYUNO5`), asigna el correlativo automático (`DESAYUNO6`) sin borrar el anterior.
* **Descripción:** Usar palabras claras (pollo, carne, integral, etc.) para las estadísticas mensuales.
* **Ingredientes y Cantidades:** Lista detallada con cantidades exactas.
* **División:** Por cantidad de porciones o en fracciones de 100 gramos.
* **Ingreso Manual (Sin IA):** Botón "Ingreso Manual de Totales (Sin IA)" para cargar peso y macros a mano en la tabla sin gastar IA.
* **Consultar planilla (`/comidas`):** Muestra todas las recetas guardadas y permite descargarlas en PDF.

# ✏️ 3. CORRECCIONES Y GESTIÓN
* **Borrar ingestas/actividades (`/eliminar`):** Menú interactivo por Día y Momento para eliminar registros uno por uno.
* **Borrar recetas precargadas (`/borracomida`):** Elimina permanentemente una receta de la planilla personal.

# 📊 4. INFORMES Y ESTADÍSTICAS
* **Diario (`/dia`):** Detalle por comida de cualquier fecha (hoy, ayer u otra) + descarga en PDF.
* **Semanal (`/semana`):**
  * *Automático:* Llega los martes si la semana previa tiene los 7 días completos (día válido = al menos 1 comida principal + 1 secundaria, o 2 principales).
  * *Manual:* De martes a domingo muestra la semana en curso; los lunes resume la semana anterior completa.
* **Mensual (`/mes`):**
  * *Automático:* Se emite los días 20 (parcial) y 5 del mes siguiente (cierre), requiriendo mínimo 20 días válidos.
  * *Manual:* Antes del día 10 del mes actual no aparece el botón del mes en curso (requiere mínimo 10 días de registro).
* **Presión Arterial (`/presi`):** Permite cargar tomas manuales o consultar promedios mensuales con PDF detallado día por día.

# 🏃‍♂️ 5. SALUD, ACTIVIDAD FÍSICA Y PESO
* **Presión por foto:** Enviar foto del tensiómetro digital; la IA lee máxima, mínima y pulso y permite Guardar, Cancelar o agregar Nota.
* **Actividad Física:**
  * *Con IA:* Enviar texto o audio indicando tiempo (minutos), ejercicio e intensidad. La IA estima calorías según biometría y permite editar antes de guardar.
  * *Manual (`/actividad`):* Menú guiado que pide minutos, calorías y descripción (rechaza valores ilógicos por seguridad).
  * *Historial (`/actividad mes`):* Muestra el promedio de minutos diarios (dividido por el total de días del mes) y genera PDF.
* **Actualización Mensual del Peso (`/perfil`):** Requisito mensual habilitado únicamente entre el **día 25 y el día 5** del mes siguiente. Si no se actualiza, se puede seguir cargando comidas, pero se pausan los reportes de evolución hasta cargarlo.

# 🔔 6. MONITOREO PROACTIVO
* **Ingestas faltantes:** Revisa dos veces al día (mañana: últimos 2 días; tarde: hoy y ayer) y avisa si falta alguna comida principal en las últimas 48 horas.
* **Presión semanal:** Si no hubo mediciones la semana previa, envía un recordatorio preventivo.

# 🚀 7. ALTA Y GLOSARIO DE COMANDOS

## Alta (`/alta`)
Configuración única: aceptar términos, ingresar apodo, fecha de nacimiento, medidas (altura, peso, cuello, cintura y cadera en mujeres), **nivel de actividad laboral diaria** (sin contar el gimnasio/deporte, que se carga aparte) e intensidad del plan (Liviano, Moderado, Fuerte). Modificable luego con `/perfil`.

## Comandos Principales
* `/alta`: Registro inicial.
* `/perfil`: Ver y actualizar biometría y parámetros.
* `/dia`, `/semana`, `/mes`: Reportes nutricionales y PDFs.
* `/presi`: Cargar o consultar presión arterial (PDF).
* `/barra`: Ingreso manual de código de barras.
* `/menu` (o `/ingesta`): Carga manual de comidas sin IA.
* `/actividad`: Carga manual o resumen mensual de ejercicio (PDF).
* `/eliminar` / `/borracomida`: Borrar registros o recetas precargadas.
* `/comidas` / `/receta`: Ver planilla personal o abrir calculadora web.
* `/planes`: Ver o ampliar planes de suscripción.
* `/x`: Cancelar cualquier acción en curso.
* `/ayuda`, `/soporte` o `/h`: Guía, manual PDF y soporte técnico con IA (texto o voz).

# ⭐ 8. PLANES Y LÍMITES DIARIOS DE IA

El cupo diario regula fotos, audios, textos libres, códigos de barras, calculadora web con IA y soporte `/h`:
* **Plan Free (Sin IA):** 0 fotos / 0 textos IA por día. Registros manuales ilimitados (`/menu`, `/actividad`, `/presi`, `*CODIGO`, calculadora manual).
* **Plan Básico:** 10 fotos y 20 textos/audios por día.
* **Plan Intermedio:** 20 fotos y 40 textos/audios por día.
* **Plan Premium:** 40 fotos y 80 textos/audios por día.

*Nota:* Las consultas a `/h` o `/soporte` descuentan del cupo de textos. Al llegar al límite, siguen activos todos los comandos manuales o se puede ampliar el plan con `/planes`.
