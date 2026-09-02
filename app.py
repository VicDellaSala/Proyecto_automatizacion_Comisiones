import streamlit as st

st.set_page_config(
    page_title="Automatización de Comisiones",
    page_icon="💰",
    layout="wide"
)

# =========================================================
# TÍTULO
# =========================================================

st.title("Automatización de Comisiones")

st.write(
    "Carga los archivos necesarios para iniciar el procesamiento de comisiones."
)

st.divider()

# =========================================================
# 1. CARGA DE ARCHIVOS
# =========================================================

st.subheader("1. Carga de archivos")

col1, col2 = st.columns(2)

with col1:

    archivos_r34 = st.file_uploader(
        "R34",
        type=["csv", "zip"],
        accept_multiple_files=True,
        help=(
            "Puedes cargar el R34 en formato CSV o ZIP. "
            "También puedes cargar varias partes si el archivo fue dividido."
        )
    )

    archivos_ventas = st.file_uploader(
        "Reporte(s) de Ventas",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        help="Puedes cargar uno o varios reportes de ventas."
    )

with col2:

    archivo_comisiones = st.file_uploader(
        "Archivo de Comisiones",
        type=["xlsx", "xls"],
        help="Carga el archivo principal de comisiones."
    )

    archivo_access = st.file_uploader(
        "Access Commerce",
        type=["xlsx", "xls"],
        help="Carga el archivo de Access Commerce."
    )

st.divider()

# =========================================================
# 2. ESTADO DE CARGA
# =========================================================

st.subheader("2. Estado de carga")

# -------------------------
# R34
# -------------------------

if archivos_r34:

    st.success(
        f"R34 cargado correctamente. Archivos recibidos: {len(archivos_r34)}"
    )

    for archivo in archivos_r34:

        tamano_mb = archivo.size / (1024 * 1024)

        st.write(
            f"• {archivo.name} — {tamano_mb:.2f} MB"
        )

else:

    st.warning("Falta cargar el R34.")

# -------------------------
# VENTAS
# -------------------------

if archivos_ventas:

    st.success(
        f"Reportes de ventas cargados: {len(archivos_ventas)}"
    )

    for archivo in archivos_ventas:

        tamano_mb = archivo.size / (1024 * 1024)

        st.write(
            f"• {archivo.name} — {tamano_mb:.2f} MB"
        )

else:

    st.warning(
        "Falta cargar al menos un Reporte de Ventas."
    )

# -------------------------
# COMISIONES
# -------------------------

if archivo_comisiones is not None:

    tamano_mb = archivo_comisiones.size / (1024 * 1024)

    st.success(
        f"Archivo de Comisiones cargado: "
        f"{archivo_comisiones.name} — {tamano_mb:.2f} MB"
    )

else:

    st.warning(
        "Falta cargar el Archivo de Comisiones."
    )

# -------------------------
# ACCESS COMMERCE
# -------------------------

if archivo_access is not None:

    tamano_mb = archivo_access.size / (1024 * 1024)

    st.success(
        f"Access Commerce cargado: "
        f"{archivo_access.name} — {tamano_mb:.2f} MB"
    )

else:

    st.warning(
        "Falta cargar Access Commerce."
    )

st.divider()

# =========================================================
# 3. CONFIGURACIÓN DE PRECIOS
# =========================================================

st.subheader("3. Configuración de precios")

st.write(
    "Estos son los precios predeterminados de los equipos. "
    "Puedes modificarlos antes de realizar cada procesamiento."
)

col1, col2, col3 = st.columns(3)

with col1:

    precio_castle = st.number_input(
        "Castle Dynamo (USD)",
        min_value=0.0,
        value=240.0,
        step=1.0,
        format="%.2f"
    )

with col2:

    precio_zappy = st.number_input(
        "Zappy S1MINI2 (USD)",
        min_value=0.0,
        value=225.0,
        step=1.0,
        format="%.2f"
    )

with col3:

    precio_pinpagos = st.number_input(
        "Pinpagos (USD)",
        min_value=0.0,
        value=104.0,
        step=1.0,
        format="%.2f"
    )

# Guardamos los precios en un diccionario.
# Más adelante reglas_comisiones.py utilizará estos valores.

precios_equipos = {
    "Castle Dynamo": precio_castle,
    "Zappy S1MINI2": precio_zappy,
    "Pinpagos": precio_pinpagos
}

with st.expander("Ver precios que utilizará el programa"):

    st.write(
        f"Castle Dynamo: ${precio_castle:.2f}"
    )

    st.write(
        f"Zappy S1MINI2: ${precio_zappy:.2f}"
    )

    st.write(
        f"Pinpagos: ${precio_pinpagos:.2f}"
    )

st.divider()

# =========================================================
# 4. REVISIÓN MANUAL
# =========================================================

st.subheader("4. Revisión manual")

st.info(
    "Cuando el programa detecte seriales incorrectos, N/A, N/D, "
    "canales dudosos, duplicados u otros casos que necesiten "
    "verificación, aparecerán aquí en una tabla editable."
)

st.write(
    "Desde esta sección podrás modificar directamente los datos "
    "o marcar una fila para eliminarla antes de generar el archivo final."
)

st.caption(
    "Esta función se activará cuando programemos las validaciones."
)

st.divider()

# =========================================================
# 5. COMPROBACIÓN GENERAL
# =========================================================

st.subheader("5. Preparación del procesamiento")

todos_cargados = (
    bool(archivos_r34)
    and bool(archivos_ventas)
    and archivo_comisiones is not None
    and archivo_access is not None
)

if todos_cargados:

    st.success(
        "Todos los archivos necesarios están cargados."
    )

    st.write(
        "El sistema está listo para iniciar el procesamiento."
    )

    if st.button(
        "Iniciar procesamiento",
        type="primary",
        use_container_width=True
    ):

        st.info(
            "Los archivos fueron recibidos correctamente. "
            "En el siguiente paso conectaremos este botón con "
            "procesamiento.py para limpiar y cruzar la información."
        )

else:

    st.warning(
        "Todavía faltan archivos para poder iniciar el procesamiento."
    )

    faltantes = []

    if not archivos_r34:
        faltantes.append("R34")

    if not archivos_ventas:
        faltantes.append("Reporte(s) de Ventas")

    if archivo_comisiones is None:
        faltantes.append("Archivo de Comisiones")

    if archivo_access is None:
        faltantes.append("Access Commerce")

    if faltantes:

        st.write("Archivos pendientes:")

        for faltante in faltantes:
            st.write(f"• {faltante}")