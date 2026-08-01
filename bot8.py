import openpyxl

# ==========================================
# CONSTANTES Y CONFIGURACIÓN
# ==========================================
FACTOR_ESCALA = 1000  # Factor para evitar problemas de coma regional en Excel


def buscar_comida_predeterminada(hoja_predeterminadas, nombre_ingresado):
    """
    Busca un alimento o plato en la hoja Comidas_Predeterminadas.
    NO utiliza atajos ni alias. Exige coincidencia exacta.
    
    Retorna un diccionario con los valores reales (divididos por 1000)
    o None si el comando/alimento no existe.
    """
    # Normalizamos el texto de búsqueda para evitar fallos por espacios o mayúsculas
    busqueda = str(nombre_ingresado).strip().lower()

    # Iteramos sobre las filas de la tabla (asumiendo encabezados en la fila 1)
    for fila in hoja_predeterminadas.iter_rows(min_row=2, values_only=True):
        codigo = fila[0]
        alimento = fila[1]

        if not alimento:
            continue

        # Comprobación de coincidencia exacta con la columna Alimento
        if str(alimento).strip().lower() == busqueda:
            return {
                "codigo": codigo,
                "alimento": alimento,
                "peso": (fila[2] or 0) / FACTOR_ESCALA,
                "calorias": (fila[3] or 0) / FACTOR_ESCALA,
                "proteinas": (fila[4] or 0) / FACTOR_ESCALA,
                "grasas": (fila[5] or 0) / FACTOR_ESCALA,
                "hidratos": (fila[6] or 0) / FACTOR_ESCALA,
                "fibras": (fila[7] or 0) / FACTOR_ESCALA,
            }

    # Si no coincide exactamente con nada, el programa desconoce el comando
    return None


def registrar_alimento_en_usuario(hoja_usuario, datos_alimento):
    """
    Guarda el alimento en la hoja del usuario multiplicando
    cada valor numérico por 1000 y convirtiéndolo a entero.
    """
    siguiente_fila = hoja_usuario.max_row + 1

    # Conversión e ingreso con factor 1000
    hoja_usuario.cell(row=siguiente_fila, column=1, value=datos_alimento["codigo"])
    hoja_usuario.cell(row=siguiente_fila, column=2, value=datos_alimento["alimento"])
    hoja_usuario.cell(row=siguiente_fila, column=3, value=int(round(datos_alimento["peso"] * FACTOR_ESCALA)))
    hoja_usuario.cell(row=siguiente_fila, column=4, value=int(round(datos_alimento["calorias"] * FACTOR_ESCALA)))
    hoja_usuario.cell(row=siguiente_fila, column=5, value=int(round(datos_alimento["proteinas"] * FACTOR_ESCALA)))
    hoja_usuario.cell(row=siguiente_fila, column=6, value=int(round(datos_alimento["grasas"] * FACTOR_ESCALA)))
    hoja_usuario.cell(row=siguiente_fila, column=7, value=int(round(datos_alimento["hidratos"] * FACTOR_ESCALA)))
    hoja_usuario.cell(row=siguiente_fila, column=8, value=int(round(datos_alimento["fibras"] * FACTOR_ESCALA)))


def procesar_comando_usuario(wb, entrada_usuario):
    """
    Función principal de procesamiento de comandos de entrada.
    """
    hoja_predeterminadas = wb["Comidas_Predeterminadas"]
    hoja_usuario = wb["Registro_Diario"]  # Ajustar al nombre de tu hoja de registro

    resultado = buscar_comida_predeterminada(hoja_predeterminadas, entrada_usuario)

    if resultado is None:
        print(f"Error: Comando o alimento '{entrada_usuario}' no reconocido.")
        return False

    # Si lo encuentra, registra convirtiendo al formato x1000
    registrar_alimento_en_usuario(hoja_usuario, resultado)
    
    print(f" Registrado con éxito: {resultado['alimento']}")
    print(f"   Valores Reales -> Peso: {resultado['peso']}g | Kcal: {resultado['calorias']} | Prot: {resultado['proteinas']}g")
    return True
