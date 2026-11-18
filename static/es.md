# Manual de Usuario: IA NutriBot

*La forma más simple, rápida y segura de llevar el control de tu alimentación.*

IA NutriBot revoluciona la forma en que registrás tus hábitos diarios. Diseñado para funcionar de manera intuitiva y sin fricciones, este asistente impulsado por inteligencia artificial te acompaña paso a paso, gestionando tus registros nutricionales directamente desde Telegram.

## Ventajas Principales

* **Privacidad total y anonimato garantizado:** Tu tranquilidad es nuestra prioridad. No solicitamos registro tradicional, contraseñas, correos electrónicos, documentos de identidad ni datos bancarios. El alta se realiza únicamente con tus medidas biométricas y podés utilizar un seudónimo.
* **Cero instalaciones:** Olvidate de descargar aplicaciones pesadas o aceptar permisos invasivos. IA NutriBot funciona al 100% dentro de tu cuenta de Telegram.
* **Carga inteligente y natural:** Despedite de las interminables listas de ingredientes. Para registrar tus comidas solo necesitás enviar una foto de tu plato, un mensaje de audio o un texto simple. La IA analiza los alimentos y calcula automáticamente calorías, fibras, hidratos, proteínas y grasas.
* **Flexibilidad manual sin límites:** Además de las herramientas con IA, contás con comandos manuales para registrar tus comidas, actividades físicas y presión arterial en cualquier momento y sin consumir cuota de inteligencia artificial.
* **Registro y evolución automática:** Tu información se almacena de forma segura para generar tu historial sin anotaciones manuales. El sistema genera informes de evolución automáticos (semanales y mensuales) que recibirás en tu chat, incluyendo estimaciones de variación de peso.
* **Cálculos de precisión internacional:** Utilizamos fórmulas validadas internacionalmente, como el método de la Marina de los Estados Unidos. Exclusivo para personas mayores de edad, el cálculo toma medidas corporales exactas (cuello, cintura y, en el caso de las mujeres, cadera) para garantizar estimaciones de máxima precisión científica.
* **Seguimiento profesional integrado:** Si te encontrás bajo tratamiento, podés ingresar el ID de Telegram de tu médico o nutricionista al registrarte. Esto le permitirá al profesional monitorear tu evolución al instante y de forma remota.

> **Advertencia Médica Importante:** IA NutriBot es una herramienta avanzada de cálculo automatizado orientada al seguimiento calórico práctico. El asistente no emite diagnósticos, dietas ni recomendaciones médicas. Su función se limita estrictamente a brindar estimaciones cuantitativas basadas en tablas internacionales de nutrición. Todo seguimiento clínico o nutricional debe ser realizado exclusivamente por un profesional de la salud matriculado y competente.

---

## 1. Métodos de Registro de Ingestas

La inteligencia artificial está a tu servicio para un registro natural y ultrarrápido, complementado con opciones manuales para que siempre tengas el control total de tus registros.

### A. Ingreso Coloquial: Foto, Audio o Texto (Con IA)

La regla de oro es simple: cuantos más detalles le proporciones a la IA, más exactos serán los cálculos.

* **Por fotografía:** Enviá una foto directa de tu plato. Aunque la IA cuenta con un excelente reconocimiento visual, recomendamos acompañar la imagen con una breve descripción.
  * *Ejemplo:* Al enviar una foto de empanadas, aclará si son al horno o fritas, el tipo de relleno y si son de elaboración casera o industrial. Si conocés el peso exacto de la porción, agregalo para una precisión perfecta.
* **Por nota de voz:** Dictá tu ingesta mediante un audio de forma completamente natural, detallando los alimentos y las cantidades estimadas o porciones. La IA convertirá el audio a texto y procesará los datos.
* **Por texto libre:** Escribí lo que consumiste de forma descriptiva. *Ejemplo: "Dos huevos revueltos con una tostada integral y una taza de café con leche".*

### B. Escaneo de Códigos de Barras o Empaques

Si consumís un producto envasado, tenés dos opciones rápidas para registrarlo:

* **Foto al código de barras:** Enviá la foto del código de barras (o ingresá la numeración manualmente con `/barra`) para que el sistema consulte la base de datos internacional. Si la información está disponible, presentará el desglose por cada 100 gramos para que ajustes la porción consumida.
* **Foto frontal del producto:** Si el código no figura en la base de datos, simplemente tomá una foto del frente del envase donde se lea claramente el producto y el peso neto. La IA analizará la imagen y extraerá los valores nutricionales automáticamente.

### C. Registro Rápido con Planillas Precargadas (Sin IA)

Para aquellas comidas que repetís con frecuencia, el bot permite guardar tus propias combinaciones en una planilla personal.

* Una vez guardada la combinación bajo un código corto (por ejemplo, `desayuno`), registrarla toma un segundo.
* Solo debés enviar un asterisco (`*`) seguido del código (ejemplo: `*desayuno` o `*pizza`).
* El sistema cargará el plato al instante en tu registro diario sin necesidad de procesamiento por IA.

### D. Ingreso Manual de Ingestas (Sin IA — Comando `/menu`)

Si preferís cargar tus datos manualmente o utilizás el Plan Free, podés registrar cualquier comida de forma ilimitada mediante el comando **`/menu`** (también funciona con `/ingesta`).

* **Formato exacto:** Debés ingresar 4 datos separados por comas:
  `/menu [Descripción], [Peso en g], [Calorías], [Proteínas en g]`
  * *Ejemplo:* `/menu 2 Tostadas con mermelada, 100, 250, 5`
* **Condiciones:** La descripción debe tener al menos 10 caracteres. Si desconocés alguno de los valores numéricos, podés colocar `0`.
* Al enviarlo, se abrirá la pantalla de confirmación para elegir fecha y momento del día antes de guardar.

---

## 2. La Calculadora Nutricional Web

IA NutriBot cuenta con un módulo web interactivo para procesar tus recetas caseras elaboradas con múltiples ingredientes y guardarlas para uso futuro. Para acceder, enviá el comando **`/receta`**. El bot responderá con un enlace web único y personalizado, vinculado exclusivamente a tu usuario (por seguridad, el enlace expira luego de 1 hora), donde deberás completar:

* **Código / Nombre:** Elegí una palabra clave corta para invocar la receta (ej. `TORTA`). Si utilizás una palabra ya registrada, el sistema asignará un número correlativo automáticamente (ej. `TORTA2`).
* **Descripción de la comida:** Un texto de apoyo utilizando palabras clave claras (pollo, carne, cerdo, pan integral) que el sistema utilizará para procesar correctamente tu resumen mensual y estadísticas.
* **Ingredientes y cantidades:** Detallá la lista completa de componentes acompañados de su cantidad exacta.
* **Criterio de división:** Seleccioná cómo deseás fraccionar la receta para su consumo:
  * **Por porciones:** Ideal para preparaciones enteras (pizzas, tartas). Indicá en cuántas porciones se dividió y el sistema calculará los valores exactos de cada una.
  * **Cada 100 gramos:** Ideal para bizcochuelos o preparaciones por peso.
* **Ingreso Manual de Totales (Sin IA):** Si preferís no utilizar inteligencia artificial o ya conocés los valores de tu preparación, podés presionar el botón **"Ingreso Manual de Totales (Sin IA)"**. Esto habilita la tabla editable en cero para que cargues a mano el peso y los macronutrientes y guardes la receta en tu planilla personal.
* **Consulta de planilla personal:** Para ver la lista completa de comidas guardadas, enviá el comando **`/comidas`**. Podrás visualizar el detalle y descargar la planilla completa en formato PDF.

---

## 3. Correcciones y Gestión de Registros

El sistema es 100% flexible y permite corregir ingresos erróneos o limpiar tu base de datos personal fácilmente.

### A. Eliminación de Ingestas o Actividades Físicas

Si ingresaste un dato en una fecha o momento incorrecto, utilizá el comando **`/eliminar`**:

1. Escribí `/eliminar` en el chat.
2. El bot mostrará botones interactivos para seleccionar el **Día** y el **Momento** (por ejemplo, *Almuerzo* o *Actividad*).
3. Se desplegará el detalle exacto de lo cargado en ese segmento.
4. Podrás eliminar los ingresos uno por uno para evitar borrados accidentales y volver a realizar la carga correcta.

### B. Limpieza de Comidas Precargadas

Si una receta guardada ya no es de utilidad o deseás actualizarla, utilizá el comando **`/borracomida`**. Este comando elimina permanentemente las preparaciones predeterminadas de tu planilla personal, manteniendo tu lista ordenada exclusivamente con lo que consumís.

---

## 4. Informes, Estadísticas y Control

Visualizá tu evolución mediante resúmenes detallados y reportes automáticos, sin necesidad de realizar cálculos manuales.

### A. Reportes Nutricionales de Ingestas

* **Reporte Diario (`/dia`):** Muestra el detalle fino de las cuatro comidas principales de un día específico (hoy, ayer u otra fecha) y genera un reporte en PDF para descargar.
* **Reporte Semanal (`/semana`):** Se emite de forma automática todos los martes. Si se solicita manualmente entre martes y domingo, muestra el avance de la semana en curso; si se solicita un lunes, resume la semana anterior completa.
* **Reporte Mensual (`/mes`):** Se genera automáticamente los días 20 (corte parcial) y 5 del mes siguiente (corte final). Al solicitarlo manualmente, despliega botones para elegir el mes a consultar. *(Nota: Si se solicita antes del día 10 del mes en curso, el botón de ese mes no aparecerá por falta de datos suficientes para evaluar la evolución).*

### B. Reportes de Salud y Presión Arterial

* **Control de Presión (`/presi`):** Además de registrar nuevas mediciones, permite consultar el historial. Al realizar una consulta mensual (por ejemplo, `/presi 08`), muestra el promedio del período y ofrece la opción de descargar un PDF detallado con todas las tomas diarias.

---

## 5. Salud y Actividad Física

IA NutriBot integra de forma inteligente tus métricas de salud y tu desgaste físico diario.

### A. Registro de Presión Arterial

* **Carga manual:** Ingresando los valores directamente por texto mediante `/presi` (ejemplo: `/presi 120,80,70, después de caminar`).
* **Lectura automática (Fotografía):** Tomale una foto a la pantalla de tu tensiómetro digital. La IA leerá la presión máxima, mínima y el pulso automáticamente. El sistema te solicitará confirmar, cancelar o agregar una nota aclaratoria antes de asentar los datos.

### B. Registro e Historial de Actividad Física

* **Carga inteligente (Cálculo de la IA):** Enviá un texto o audio indicando el tipo de ejercicio, la duración en minutos y la intensidad. La IA cruzará estos datos con tus parámetros físicos para estimar el gasto calórico. Podrás validar o editar este valor antes de guardarlo.
* **Carga manual exacta (Sin IA):** Si utilizás un reloj inteligente y conocés las calorías exactas, enviá el comando **`/actividad`**. El sistema desplegará un menú guiado solicitando los minutos, las calorías quemadas y una breve descripción.
* **Historial mensual:** Desde el mismo menú de `/actividad`, enviando `/actividad mes` o seguido del número de mes (ej. `/actividad 10` para octubre), podrás visualizar el promedio mensual en pantalla y descargar el detalle completo en PDF.

### C. Actualización Mensual del Peso y Datos Biométricos (`/perfil`)

Para mantener la precisión de los cálculos metabólicos, es requisito actualizar tu peso mensualmente desde el panel interactivo del comando **`/perfil`**.

* **Ventana de actualización:** Para evitar que fluctuaciones aisladas distorsionen tu diagnóstico mensual, los datos biométricos (peso, altura y medidas corporales) se habilitan para su edición únicamente entre el **día 25 de cada mes y el día 5 del mes siguiente**.
* Si actualizás tu peso a partir del día 25, el sistema lo tomará automáticamente como válido para el ciclo del mes siguiente.
* Si olvidás actualizarlo, podrás seguir registrando tus comidas y actividades con normalidad, pero la emisión de tus reportes de evolución quedará pausada hasta que ingreses tu nuevo peso.

---

## 6. Monitoreo Proactivo y Avisos Automáticos

IA NutriBot trabaja en segundo plano para ayudarte a mantener la constancia en tus registros mediante recordatorios amigables.

* **Control de Ingestas Faltantes:** El sistema evalúa tu actividad dos veces al día. Si detecta la falta de alguna de las cuatro comidas principales en las últimas 48 horas, enviará un recordatorio proactivo *(ej. "Falta registrar la cena del día de ayer")*.
* **Recordatorio Semanal de Presión Arterial:** Una vez por semana, el bot evalúa tu historial. Si no registraste controles en la semana previa, te enviará un aviso preventivo para incentivar el hábito y mantener un historial completo.

---

## 7. Planes y Límites Diarios de Inteligencia Artificial

Todos los registros manuales (`/menu`, `/actividad`, `/presi`, comidas precargadas con `*CODIGO` e ingreso manual en la calculadora web) son siempre ilimitados. El uso diario de las herramientas impulsadas por **Inteligencia Artificial** (fotos de platos, códigos de barras, tensiómetros, audios, textos libres, calculadora web con IA y soporte `/h`) varía según el plan activo en tu cuenta:

| Plan | Fotos con IA por día | Textos / Audios con IA por día | Registros Manuales |
| :--- | :---: | :---: | :---: |
| **Plan Free (Sin IA)** | 0 | 0 | Ilimitados |
| **Plan Básico** | 10 | 20 | Ilimitados |
| **Plan Intermedio** | 20 | 40 | Ilimitados |
| **Plan Premium** | 40 | 80 | Ilimitados |

Si alcanzás tu límite diario de IA, podrás continuar registrando manualmente sin interrupciones, esperar a la renovación del día siguiente o actualizar tu plan en cualquier momento mediante el comando **`/planes`**.

---

## Glosario Rápido de Comandos

### Configuración, Perfil y Planes
* **`/alta`:** Proceso de registro inicial anónimo. Solicita datos biométricos (cintura, cuello, cadera en mujeres, peso, altura y fecha de nacimiento) para realizar cálculos de alta precisión.
* **`/perfil`:** Muestra tus datos biométricos y parámetros configurados, permitiendo actualizar tu peso, medidas, apodo, idioma, ritmo y profesional mediante un menú interactivo.
* **`/planes`:** Muestra los planes de suscripción vigentes para activar o ampliar tus límites diarios de Inteligencia Artificial.

### Reportes y Seguimiento
* **`/dia`:** Muestra el resumen de calorías y macronutrientes del día solicitado, con opción a descarga en PDF.
* **`/semana`:** Presenta el balance detallado y resumen nutricional de los días transcurridos de la semana.
* **`/mes`:** Exhibe el balance consolidado del mes solicitado y evalúa el cumplimiento de los objetivos, con descarga en PDF.
* **`/presi`:** Registra la presión arterial de forma manual o solicita el reporte mensual en PDF.

### Registro y Gestión de Alimentos y Actividad
* **`/menu`** (o `/ingesta`): Registra una ingesta alimentaria de forma 100% manual (sin consumir IA), indicando descripción, peso, calorías y proteínas separados por comas.
* **`/barra`:** Permite ingresar manualmente la numeración de un código de barras.
* **`/actividad`:** Registra actividad física manualmente o solicita el resumen mensual detallado y su PDF utilizando `/actividad mes`.
* **`/eliminar`:** Borra registros específicos de ingestas o actividades mediante botones interactivos.
* **`/comidas`:** Muestra las recetas guardadas en las planillas precargadas y permite descargarlas en PDF.
* **`/receta`:** Genera un enlace web temporal para crear y guardar recetas personalizadas (con IA o carga manual).
* **`/borracomida`:** Elimina permanentemente una comida o receta guardada en tu planilla personal.

### Ayuda y Soporte
* **`/ayuda`** (o `/start`): Despliega un resumen completo con los comandos disponibles y el botón para descargar este manual en PDF.
* **`/h`** (o `/soporte`): Activa el asistente virtual de soporte técnico por texto o nota de voz *(descuenta del cupo diario de textos con IA)*.
* **`/x`** (o `/cancelar`): Cancela inmediatamente cualquier operación o proceso en curso.
