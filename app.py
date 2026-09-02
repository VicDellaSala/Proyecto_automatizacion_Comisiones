import streamlit as st

from procesamiento import (
    procesar_todo,
    recalcular_comisiones,
    generar_excel_resultado,
)

from reglas_comisiones import PRECIOS_BASE


# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================

st.set_page_config(
    page_title="Automatización de Comisiones",
    page_icon="💰",
    layout="wide",
)


# =========================================================
# LIMPIAR RESULTADOS VIEJOS DE VERSIONES ANTERIORES
# =========================================================

CLAVES_RESULTADO_ACTUAL = {
    "final",
    "r34",
    "detalle_r34",
    "ventas_nuevas",
    "ventas_existentes",
    "ventas_excluidas",
    "ventas_duplicadas",
    "advertencias",
    "afiliados_access",
    "cantidad_original",
    "bytes_comisiones_original",
}

if "resultados" in st.session_state:

    resultados_guardados = st.session_state["resultados"]

    if (
        not isinstance(resultados_guardados, dict)
        or not CLAVES_RESULTADO_ACTUAL.issubset(
            resultados_guardados.keys()
        )
    ):
        del st.session_state["resultados"]


# =========================================================
# ENCABEZADO
# =========================================================

st.title("Automatización de Comisiones")

st.write(
    "Carga los cuatro archivos necesarios para procesar las comisiones."
)

st.caption(
    "El archivo de Comisiones es la base maestra. "
    "El programa trabaja sobre la hoja VENTAS y agrega allí únicamente "
    "las ventas nuevas."
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
            "Puedes subir el R34 como CSV o comprimido en ZIP. "
            "También se admiten varias partes."
        ),
        key="uploader_r34",
    )

    archivos_ventas = st.file_uploader(
        "Reporte(s) de Ventas",
        type=["xlsx"],
        accept_multiple_files=True,
        help=(
            "Puedes subir uno o varios reportes de ventas "
            "de distintos meses."
        ),
        key="uploader_ventas",
    )


with col2:

    archivo_comisiones = st.file_uploader(
        "Archivo de Comisiones",
        type=["xlsx"],
        help=(
            "Este es el archivo maestro. "
            "El programa utilizará la hoja VENTAS."
        ),
        key="uploader_comisiones",
    )

    archivo_access = st.file_uploader(
        "Access Commerce",
        type=["xlsx"],
        help="Archivo utilizado para validar afiliados de Access Commerce.",
        key="uploader_access",
    )


st.divider()


# =========================================================
# 2. ESTADO DE CARGA
# =========================================================

st.subheader("2. Estado de carga")


if archivos_r34:

    st.success(
        f"R34 cargado: {len(archivos_r34)} archivo(s)."
    )

    for archivo in archivos_r34:

        st.write(
            f"• {archivo.name} — "
            f"{archivo.size / 1024 / 1024:.2f} MB"
        )

else:

    st.warning("Falta cargar el R34.")


if archivos_ventas:

    st.success(
        f"Reportes de Ventas cargados: "
        f"{len(archivos_ventas)} archivo(s)."
    )

    for archivo in archivos_ventas:
        st.write(f"• {archivo.name}")

else:

    st.warning(
        "Falta cargar al menos un Reporte de Ventas."
    )


if archivo_comisiones is not None:

    st.success(
        f"Archivo de Comisiones cargado: "
        f"{archivo_comisiones.name}"
    )

    st.info(
        "Se procesará la hoja VENTAS del archivo de Comisiones."
    )

else:

    st.warning(
        "Falta cargar el archivo de Comisiones."
    )


if archivo_access is not None:

    st.success(
        f"Access Commerce cargado: "
        f"{archivo_access.name}"
    )

else:

    st.warning(
        "Falta cargar Access Commerce."
    )


st.divider()


# =========================================================
# 3. PRECIOS DE EQUIPOS
# =========================================================

st.subheader("3. Precios de equipos")

st.write(
    "Estos precios quedan cargados por defecto, "
    "pero puedes modificarlos antes de cada procesamiento."
)

c1, c2, c3 = st.columns(3)


with c1:

    precio_castle = st.number_input(
        "Castle Dynamo (USD)",
        value=float(
            PRECIOS_BASE["Castle Dynamo"]
        ),
        min_value=0.0,
        step=1.0,
        format="%.2f",
    )


with c2:

    precio_zappy = st.number_input(
        "Zappy S1MINI2 (USD)",
        value=float(
            PRECIOS_BASE["Zappy S1MINI2"]
        ),
        min_value=0.0,
        step=1.0,
        format="%.2f",
    )


with c3:

    precio_pinpagos = st.number_input(
        "Pinpagos (USD)",
        value=float(
            PRECIOS_BASE["Pinpagos"]
        ),
        min_value=0.0,
        step=1.0,
        format="%.2f",
    )


st.session_state["precios"] = {
    "Castle Dynamo": precio_castle,
    "Zappy S1MINI2": precio_zappy,
    "Pinpagos": precio_pinpagos,
}


st.divider()


# =========================================================
# 4. PROCESAMIENTO
# =========================================================

st.subheader("4. Procesamiento")


todos_cargados = (
    bool(archivos_r34)
    and bool(archivos_ventas)
    and archivo_comisiones is not None
    and archivo_access is not None
)


if not todos_cargados:

    st.info(
        "Carga los cuatro tipos de archivos "
        "para habilitar el procesamiento."
    )

else:

    st.success(
        "Todos los archivos necesarios están cargados."
    )

    if st.button(
        "Iniciar procesamiento",
        type="primary",
        use_container_width=True,
    ):

        # Evitamos mezclar una corrida nueva
        # con resultados guardados de una versión anterior.
        if "resultados" in st.session_state:
            del st.session_state["resultados"]

        try:

            with st.spinner(
                "Procesando R34 por bloques, "
                "revisando Ventas, Comisiones y Access Commerce..."
            ):

                resultados = procesar_todo(
                    archivos_r34=archivos_r34,
                    archivos_ventas=archivos_ventas,
                    archivo_comisiones=archivo_comisiones,
                    archivo_access=archivo_access,
                    chunksize=100_000,
                )

            if not isinstance(resultados, dict):

                raise ValueError(
                    "procesar_todo() no devolvió "
                    "el resultado esperado."
                )

            faltantes = (
                CLAVES_RESULTADO_ACTUAL
                - set(resultados.keys())
            )

            if faltantes:

                raise ValueError(
                    "El procesamiento terminó, pero faltan "
                    "estos datos internos: "
                    + ", ".join(sorted(faltantes))
                )

            st.session_state["resultados"] = resultados

            st.success(
                "Procesamiento terminado correctamente."
            )

        except Exception as error:

            st.error(
                "Ocurrió un error durante el procesamiento."
            )

            st.exception(error)


# =========================================================
# 5. RESUMEN
# =========================================================

if "resultados" in st.session_state:

    resultados = st.session_state["resultados"]


    # Protección adicional por si Streamlit conserva
    # un estado viejo después de un deploy.
    if not CLAVES_RESULTADO_ACTUAL.issubset(
        resultados.keys()
    ):

        st.warning(
            "Se detectaron resultados guardados "
            "de una versión anterior."
        )

        if st.button(
            "Limpiar resultados antiguos",
            use_container_width=True,
        ):

            del st.session_state["resultados"]
            st.rerun()

        st.stop()


    final = resultados["final"]

    st.divider()

    st.subheader("5. Resumen")


    original = resultados.get(
        "cantidad_original",
        0
    )

    nuevas = len(
        resultados.get(
            "ventas_nuevas",
            []
        )
    )

    existentes = len(
        resultados.get(
            "ventas_existentes",
            []
        )
    )

    excluidas = len(
        resultados.get(
            "ventas_excluidas",
            []
        )
    )

    duplicadas = len(
        resultados.get(
            "ventas_duplicadas",
            []
        )
    )

    total_final = len(final)


    if "__REQUIERE_REVISION" in final.columns:

        revision = int(
            final[
                "__REQUIERE_REVISION"
            ].fillna(False).sum()
        )

    else:

        revision = 0


    fila1_col1, fila1_col2, fila1_col3 = st.columns(3)

    fila1_col1.metric(
        "Comisiones originales",
        original
    )

    fila1_col2.metric(
        "Ventas nuevas agregadas",
        nuevas
    )

    fila1_col3.metric(
        "Total final",
        total_final
    )


    fila2_col1, fila2_col2, fila2_col3 = st.columns(3)

    fila2_col1.metric(
        "Ventas ya existentes",
        existentes
    )

    fila2_col2.metric(
        "Ventas excluidas",
        excluidas
    )

    fila2_col3.metric(
        "Revisión manual",
        revision
    )


    if duplicadas > 0:

        st.info(
            f"Duplicados detectados entre los reportes cargados: "
            f"{duplicadas}"
        )


    # =====================================================
    # DETALLE R34
    # =====================================================

    with st.expander("Detalle del R34"):

        detalles = resultados.get(
            "detalle_r34",
            []
        )

        if not detalles:

            st.write(
                "No hay detalle disponible del R34."
            )

        for detalle in detalles:

            st.write(
                f"**{detalle.get('archivo', 'R34')}**"
            )

            st.write(
                f"Filas leídas: "
                f"{detalle.get('filas_leidas', 0):,}"
            )

            st.write(
                f"Filas CredicardPos: "
                f"{detalle.get('filas_credicardpos', 0):,}"
            )

            st.divider()


    # =====================================================
    # ADVERTENCIAS
    # =====================================================

    advertencias = resultados.get(
        "advertencias",
        []
    )

    if advertencias:

        with st.expander("Advertencias"):

            for aviso in advertencias:
                st.warning(aviso)


    st.divider()


    # =====================================================
    # 6. REVISIÓN MANUAL
    # =====================================================

    st.subheader("6. Revisión manual")


    if "__REQUIERE_REVISION" not in final.columns:

        st.warning(
            "La tabla todavía no contiene "
            "el indicador interno de revisión."
        )

    else:

        problemas = final[
            final[
                "__REQUIERE_REVISION"
            ].fillna(False)
        ].copy()


        if problemas.empty:

            st.success(
                "No hay filas pendientes de revisión manual."
            )

        else:

            st.write(
                "Aquí aparecen únicamente las filas "
                "que necesitan revisión."
            )

            st.write(
                "Puedes corregir celdas directamente "
                "o marcar una fila para eliminarla."
            )

            problemas.insert(
                0,
                "Eliminar",
                False
            )


            columnas_visibles = [
                "Eliminar"
            ]

            for columna in final.columns:

                if not str(
                    columna
                ).startswith("__"):

                    columnas_visibles.append(
                        columna
                    )


            if "__ROW_ID" in problemas.columns:

                columnas_visibles.append(
                    "__ROW_ID"
                )


            # Evitamos columnas repetidas por seguridad.
            columnas_visibles = list(
                dict.fromkeys(
                    columnas_visibles
                )
            )


            columnas_visibles = [
                columna
                for columna in columnas_visibles
                if columna in problemas.columns
            ]


            columnas_bloqueadas = []

            if "__ROW_ID" in columnas_visibles:
                columnas_bloqueadas.append(
                    "__ROW_ID"
                )


            editado = st.data_editor(
                problemas[
                    columnas_visibles
                ],
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
                disabled=columnas_bloqueadas,
                column_config={
                    "Eliminar":
                        st.column_config.CheckboxColumn(
                            "Eliminar",
                            help=(
                                "Marca esta opción si la fila "
                                "debe eliminarse."
                            ),
                            default=False,
                        ),

                    "__ROW_ID":
                        st.column_config.NumberColumn(
                            "ID interno",
                            help=(
                                "Identificador interno del programa. "
                                "No modificar."
                            ),
                        ),
                },
                key="tabla_revision",
            )


            if st.button(
                "Aplicar correcciones y revalidar",
                use_container_width=True,
            ):

                base = resultados[
                    "final"
                ].copy()


                # =========================================
                # ELIMINAR FILAS
                # =========================================

                if "__ROW_ID" in editado.columns:

                    ids_eliminar = set(
                        editado.loc[
                            editado["Eliminar"] == True,
                            "__ROW_ID"
                        ].tolist()
                    )

                    if ids_eliminar:

                        base = base[
                            ~base[
                                "__ROW_ID"
                            ].isin(
                                ids_eliminar
                            )
                        ].copy()


                # =========================================
                # APLICAR MODIFICACIONES
                # =========================================

                conservar = editado[
                    editado["Eliminar"] == False
                ].copy()

                conservar = conservar.drop(
                    columns=["Eliminar"]
                )


                if (
                    "__ROW_ID" in conservar.columns
                    and "__ROW_ID" in base.columns
                ):

                    for _, fila in conservar.iterrows():

                        row_id = fila[
                            "__ROW_ID"
                        ]

                        mascara = (
                            base[
                                "__ROW_ID"
                            ]
                            == row_id
                        )

                        if not mascara.any():
                            continue


                        for columna in conservar.columns:

                            if columna == "__ROW_ID":
                                continue

                            if columna in base.columns:

                                base.loc[
                                    mascara,
                                    columna
                                ] = fila[
                                    columna
                                ]


                # =========================================
                # REVALIDAR
                # =========================================

                recalculado = recalcular_comisiones(
                    base,
                    resultados["r34"],
                    resultados["afiliados_access"],
                )

                resultados[
                    "final"
                ] = recalculado

                st.session_state[
                    "resultados"
                ] = resultados

                st.success(
                    "Correcciones aplicadas y datos revalidados."
                )

                st.rerun()


    st.divider()


    # =====================================================
    # 7. VISTA PREVIA DEL ARCHIVO FINAL
    # =====================================================

    st.subheader(
        "7. Archivo de Comisiones resultante"
    )

    st.write(
        "La base sigue siendo el archivo de Comisiones. "
        "Las ventas nuevas se agregan dentro de esa misma estructura."
    )


    columnas_internas_o_auxiliares = {
        "Monto_TX_R34",
        "Serial_R34",
        "Estado_TX",
        "Access_Commerce_Calculado",
        "Aplica_Pago_Calculado",
        "Motivo_Revision",
    }


    columnas_publicas = [
        columna
        for columna in final.columns
        if (
            not str(
                columna
            ).startswith("__")
            and columna
            not in columnas_internas_o_auxiliares
        )
    ]


    st.dataframe(
        final[
            columnas_publicas
        ].head(200),
        use_container_width=True,
        hide_index=True,
    )


    st.caption(
        "Vista previa de las primeras 200 filas."
    )


    # =====================================================
    # DESCARGAR MISMO LIBRO DE COMISIONES ACTUALIZADO
    # =====================================================

    try:

        excel_final = generar_excel_resultado(
            resultados
        )

        st.download_button(
            "Descargar archivo de Comisiones actualizado",
            data=excel_final,
            file_name="Comisiones_Actualizadas.xlsx",
            mime=(
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            ),
            type="primary",
            use_container_width=True,
        )

        st.success(
            "El archivo descargado parte del libro original "
            "de Comisiones y actualiza su hoja VENTAS."
        )

    except Exception as error:

        st.error(
            "No se pudo preparar el Excel final."
        )

        st.exception(error)


# =========================================================
# REINICIO MANUAL
# =========================================================

st.divider()

if st.button(
    "Limpiar resultados y comenzar otra vez",
    use_container_width=True,
):

    if "resultados" in st.session_state:
        del st.session_state["resultados"]

    st.rerun()