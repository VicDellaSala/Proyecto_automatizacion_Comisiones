import streamlit as st

from procesamiento import (
    procesar_todo,
    recalcular_comisiones,
    generar_excel_resultado,
)

from reglas_comisiones import PRECIOS_BASE

st.set_page_config(
    page_title="Automatización de Comisiones",
    page_icon="💰",
    layout="wide",
)

st.title("Automatización de Comisiones")
st.write("Carga los cuatro archivos necesarios para procesar las comisiones.")
st.divider()

st.subheader("1. Carga de archivos")
col1, col2 = st.columns(2)

with col1:
    archivos_r34 = st.file_uploader(
        "R34",
        type=["csv", "zip"],
        accept_multiple_files=True,
        help="Puedes subir el R34 comprimido en ZIP.",
    )

    archivos_ventas = st.file_uploader(
        "Reporte(s) de Ventas",
        type=["xlsx"],
        accept_multiple_files=True,
        help="Puedes subir uno o varios reportes de ventas.",
    )

with col2:
    archivo_comisiones = st.file_uploader(
        "Archivo de Comisiones",
        type=["xlsx"],
        help="La hoja utilizada será VENTAS.",
    )

    archivo_access = st.file_uploader(
        "Access Commerce",
        type=["xlsx"],
    )

st.divider()
st.subheader("2. Estado de carga")

if archivos_r34:
    st.success(f"R34 cargado: {len(archivos_r34)} archivo(s).")
    for archivo in archivos_r34:
        st.write(f"• {archivo.name} — {archivo.size / 1024 / 1024:.2f} MB")
else:
    st.warning("Falta R34.")

if archivos_ventas:
    st.success(f"Reportes de Ventas: {len(archivos_ventas)} archivo(s).")
    for archivo in archivos_ventas:
        st.write(f"• {archivo.name}")
else:
    st.warning("Falta Reporte de Ventas.")

if archivo_comisiones:
    st.success(f"Comisiones: {archivo_comisiones.name}")
    st.info("Se procesará únicamente la hoja VENTAS.")
else:
    st.warning("Falta archivo de Comisiones.")

if archivo_access:
    st.success(f"Access Commerce: {archivo_access.name}")
else:
    st.warning("Falta Access Commerce.")

st.divider()
st.subheader("3. Precios de equipos")

c1, c2, c3 = st.columns(3)

with c1:
    precio_castle = st.number_input(
        "Castle Dynamo",
        value=float(PRECIOS_BASE["Castle Dynamo"]),
        min_value=0.0,
        format="%.2f",
    )

with c2:
    precio_zappy = st.number_input(
        "Zappy S1MINI2",
        value=float(PRECIOS_BASE["Zappy S1MINI2"]),
        min_value=0.0,
        format="%.2f",
    )

with c3:
    precio_pinpagos = st.number_input(
        "Pinpagos",
        value=float(PRECIOS_BASE["Pinpagos"]),
        min_value=0.0,
        format="%.2f",
    )

st.session_state["precios"] = {
    "Castle Dynamo": precio_castle,
    "Zappy S1MINI2": precio_zappy,
    "Pinpagos": precio_pinpagos,
}

st.divider()
st.subheader("4. Procesamiento")

todos = (
    bool(archivos_r34)
    and bool(archivos_ventas)
    and archivo_comisiones is not None
    and archivo_access is not None
)

if todos:
    st.success("Todos los archivos están cargados.")

    if st.button(
        "Iniciar procesamiento",
        type="primary",
        use_container_width=True,
    ):
        try:
            with st.spinner(
                "Procesando R34, Ventas, Comisiones y Access Commerce..."
            ):
                resultados = procesar_todo(
                    archivos_r34=archivos_r34,
                    archivos_ventas=archivos_ventas,
                    archivo_comisiones=archivo_comisiones,
                    archivo_access=archivo_access,
                    chunksize=100_000,
                )

            st.session_state["resultados"] = resultados
            st.success("Procesamiento terminado.")

        except Exception as error:
            st.error("Ocurrió un error.")
            st.exception(error)
else:
    st.info("Carga los cuatro archivos.")

if "resultados" in st.session_state:
    resultados = st.session_state["resultados"]
    final = resultados["final"]

    st.divider()
    st.subheader("5. Resumen")

    original = resultados["cantidad_original"]
    nuevas = len(resultados["ventas_nuevas"])
    existentes = len(resultados["ventas_existentes"])
    excluidas = len(resultados["ventas_excluidas"])
    total_final = len(final)
    revision = int(final["__REQUIERE_REVISION"].sum())

    c1, c2, c3 = st.columns(3)
    c1.metric("Comisiones originales", original)
    c2.metric("Ventas nuevas agregadas", nuevas)
    c3.metric("Total final", total_final)

    c4, c5, c6 = st.columns(3)
    c4.metric("Ventas ya existentes", existentes)
    c5.metric("Ventas excluidas", excluidas)
    c6.metric("Revisión manual", revision)

    with st.expander("Detalle R34"):
        for detalle in resultados["detalle_r34"]:
            st.write(f"**{detalle['archivo']}**")
            st.write(f"Filas leídas: {detalle['filas_leidas']:,}")
            st.write(f"CredicardPos: {detalle['filas_credicardpos']:,}")

    if resultados["advertencias"]:
        with st.expander("Advertencias"):
            for aviso in resultados["advertencias"]:
                st.warning(aviso)

    st.divider()
    st.subheader("6. Revisión manual")

    problemas = final[
        final["__REQUIERE_REVISION"]
    ].copy()

    if problemas.empty:
        st.success("No hay filas pendientes de revisión.")
    else:
        st.write("Aquí solo aparecen las filas con algún problema.")
        st.write("Puedes modificar sus datos o marcar una fila para eliminar.")

        problemas.insert(0, "Eliminar", False)

        columnas_visibles = ["Eliminar"]

        for columna in final.columns:
            if not str(columna).startswith("__"):
                columnas_visibles.append(columna)

        columnas_visibles.append("__ROW_ID")

        editado = st.data_editor(
            problemas[columnas_visibles],
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            disabled=["__ROW_ID"],
            column_config={
                "Eliminar": st.column_config.CheckboxColumn("Eliminar"),
                "__ROW_ID": st.column_config.NumberColumn("ID interno"),
            },
            key="tabla_revision",
        )

        if st.button(
            "Aplicar cambios y revalidar",
            use_container_width=True
        ):
            base = resultados["final"].copy()

            ids_eliminar = set(
                editado.loc[
                    editado["Eliminar"] == True,
                    "__ROW_ID"
                ].tolist()
            )

            base = base[
                ~base["__ROW_ID"].isin(ids_eliminar)
            ].copy()

            conservar = editado[
                editado["Eliminar"] == False
            ].copy()

            conservar = conservar.drop(
                columns=["Eliminar"]
            )

            for _, fila in conservar.iterrows():
                row_id = fila["__ROW_ID"]
                mascara = base["__ROW_ID"] == row_id

                if not mascara.any():
                    continue

                for columna in conservar.columns:
                    if columna == "__ROW_ID":
                        continue

                    if columna in base.columns:
                        base.loc[
                            mascara,
                            columna
                        ] = fila[columna]

            recalculado = recalcular_comisiones(
                base,
                resultados["r34"],
                resultados["afiliados_access"],
            )

            resultados["final"] = recalculado
            st.session_state["resultados"] = resultados

            st.success("Cambios guardados.")
            st.rerun()

    st.divider()
    st.subheader("7. Archivo de Comisiones resultante")

    columnas_publicas = [
        columna
        for columna in final.columns
        if not str(columna).startswith("__")
        and columna not in {
            "Monto_TX_R34",
            "Serial_R34",
            "Estado_TX",
            "Access_Commerce_Calculado",
            "Aplica_Pago_Calculado",
            "Motivo_Revision",
        }
    ]

    st.dataframe(
        final[columnas_publicas].head(200),
        use_container_width=True,
    )

    st.caption(
        "Vista previa de las primeras 200 filas de la hoja VENTAS."
    )

    try:
        excel_final = generar_excel_resultado(resultados)

        st.download_button(
            "Descargar archivo de Comisiones actualizado",
            data=excel_final,
            file_name="Comisiones_Actualizadas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )

        st.success(
            "La descarga conserva el libro original y actualiza la hoja VENTAS."
        )

    except Exception as error:
        st.error("No se pudo preparar el Excel final.")
        st.exception(error)

