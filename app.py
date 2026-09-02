import streamlit as st

from procesamiento import (
    procesar_todo,
    recalcular_comisiones,
    generar_excel_resultado,
    VERSION_PROCESAMIENTO,
)

from reglas_comisiones import PRECIOS_BASE


VERSION_APP = "3.0"


st.set_page_config(
    page_title="Automatización de Comisiones",
    page_icon="💰",
    layout="wide",
)


# =========================================================
# LIMPIAR RESULTADOS DE VERSIONES ANTERIORES
# =========================================================

CLAVES_RESULTADO = {
    "final",
    "r34",
    "detalle_r34",
    "ventas_limpias",
    "ventas_nuevas",
    "ventas_existentes",
    "ventas_excluidas",
    "ventas_duplicadas",
    "advertencias",
    "afiliados_access",
    "cantidad_original",
    "bytes_comisiones_original",
    "hoja_comisiones",
    "mes_r34",
}


if (
    st.session_state.get(
        "version_app"
    )
    != VERSION_APP
):
    st.session_state.clear()

    st.session_state[
        "version_app"
    ] = VERSION_APP


if "resultados" in st.session_state:
    guardado = st.session_state[
        "resultados"
    ]

    if (
        not isinstance(
            guardado,
            dict
        )
        or not CLAVES_RESULTADO.issubset(
            guardado.keys()
        )
    ):
        del st.session_state[
            "resultados"
        ]


# =========================================================
# TÍTULO
# =========================================================

st.title(
    "Automatización de Comisiones"
)

st.write(
    "El archivo de Comisiones es la base maestra. "
    "El programa trabaja sobre su hoja VENTAS, "
    "agrega únicamente las ventas nuevas y conserva "
    "las demás hojas del libro."
)

st.caption(
    f"Versión del proyecto: {VERSION_APP}"
)

st.caption(
    f"Versión de procesamiento.py: {VERSION_PROCESAMIENTO}"
)

st.divider()


# =========================================================
# 1. CARGA
# =========================================================

st.subheader(
    "1. Carga de archivos"
)

col1, col2 = st.columns(
    2
)


with col1:
    archivos_r34 = st.file_uploader(
        "R34",
        type=[
            "csv",
            "zip",
        ],
        accept_multiple_files=True,
        help=(
            "Puedes subir el R34 comprimido "
            "en ZIP. Se procesa por bloques."
        ),
        key="r34_v3",
    )

    archivos_ventas = st.file_uploader(
        "Reporte(s) de Ventas",
        type=[
            "xlsx",
        ],
        accept_multiple_files=True,
        help=(
            "Puedes cargar uno o varios "
            "reportes de ventas."
        ),
        key="ventas_v3",
    )


with col2:
    archivo_comisiones = st.file_uploader(
        "Archivo de Comisiones",
        type=[
            "xlsx",
        ],
        help=(
            "El archivo real debe contener "
            "la hoja VENTAS."
        ),
        key="comisiones_v3",
    )

    archivo_access = st.file_uploader(
        "Access Commerce",
        type=[
            "xlsx",
        ],
        key="access_v3",
    )


st.divider()


# =========================================================
# 2. ESTADO
# =========================================================

st.subheader(
    "2. Estado de carga"
)


if archivos_r34:
    st.success(
        f"R34: {len(archivos_r34)} "
        f"archivo(s) cargado(s)."
    )

    for archivo in archivos_r34:
        st.write(
            f"• {archivo.name} — "
            f"{archivo.size / 1024 / 1024:.2f} MB"
        )
else:
    st.warning(
        "Falta R34."
    )


if archivos_ventas:
    st.success(
        f"Ventas: {len(archivos_ventas)} "
        f"archivo(s) cargado(s)."
    )

    for archivo in archivos_ventas:
        st.write(
            f"• {archivo.name}"
        )
else:
    st.warning(
        "Falta Reporte de Ventas."
    )


if archivo_comisiones is not None:
    st.success(
        f"Comisiones: "
        f"{archivo_comisiones.name}"
    )

    st.info(
        "La base de trabajo será "
        "la hoja VENTAS."
    )
else:
    st.warning(
        "Falta archivo de Comisiones."
    )


if archivo_access is not None:
    st.success(
        f"Access Commerce: "
        f"{archivo_access.name}"
    )
else:
    st.warning(
        "Falta Access Commerce."
    )


st.divider()


# =========================================================
# 3. PRECIOS
# =========================================================

st.subheader(
    "3. Precios de equipos"
)

st.caption(
    "Estos valores quedan fijos por defecto, "
    "pero pueden cambiarse para la corrida actual."
)

c1, c2, c3 = st.columns(
    3
)


with c1:
    precio_castle = st.number_input(
        "Castle Dynamo (USD)",
        min_value=0.0,
        value=float(
            PRECIOS_BASE[
                "Castle Dynamo"
            ]
        ),
        step=1.0,
        format="%.2f",
    )


with c2:
    precio_zappy = st.number_input(
        "Zappy S1MINI2 (USD)",
        min_value=0.0,
        value=float(
            PRECIOS_BASE[
                "Zappy S1MINI2"
            ]
        ),
        step=1.0,
        format="%.2f",
    )


with c3:
    precio_pinpagos = st.number_input(
        "Pinpagos (USD)",
        min_value=0.0,
        value=float(
            PRECIOS_BASE[
                "Pinpagos"
            ]
        ),
        step=1.0,
        format="%.2f",
    )


st.session_state[
    "precios"
] = {
    "Castle Dynamo":
        precio_castle,

    "Zappy S1MINI2":
        precio_zappy,

    "Pinpagos":
        precio_pinpagos,
}


st.divider()


# =========================================================
# 4. PROCESAR
# =========================================================

st.subheader(
    "4. Procesamiento"
)


todos_cargados = (
    bool(
        archivos_r34
    )
    and bool(
        archivos_ventas
    )
    and archivo_comisiones is not None
    and archivo_access is not None
)


if not todos_cargados:
    st.info(
        "Carga los cuatro tipos de archivos "
        "para iniciar."
    )

else:
    st.success(
        "Todos los archivos están cargados."
    )

    if st.button(
        "Iniciar procesamiento",
        type="primary",
        use_container_width=True,
    ):
        if "resultados" in st.session_state:
            del st.session_state[
                "resultados"
            ]

        try:
            with st.spinner(
                "Procesando R34 por bloques, "
                "cruzando Ventas, Comisiones "
                "y Access Commerce..."
            ):
                resultados = procesar_todo(
                    archivos_r34=
                        archivos_r34,

                    archivos_ventas=
                        archivos_ventas,

                    archivo_comisiones=
                        archivo_comisiones,

                    archivo_access=
                        archivo_access,

                    chunksize=
                        100_000,
                )

            faltantes = (
                CLAVES_RESULTADO
                - set(
                    resultados.keys()
                )
            )

            if faltantes:
                raise ValueError(
                    "Faltan datos internos: "
                    + ", ".join(
                        sorted(
                            faltantes
                        )
                    )
                )

            st.session_state[
                "resultados"
            ] = resultados

            st.success(
                "Procesamiento terminado."
            )

        except Exception as error:
            st.error(
                "Ocurrió un error durante "
                "el procesamiento."
            )

            st.exception(
                error
            )


# =========================================================
# 5. RESULTADOS
# =========================================================

if "resultados" in st.session_state:
    resultados = st.session_state[
        "resultados"
    ]

    final = resultados[
        "final"
    ]

    st.divider()

    st.subheader(
        "5. Resumen"
    )

    original = resultados[
        "cantidad_original"
    ]

    nuevas = len(
        resultados[
            "ventas_nuevas"
        ]
    )

    existentes = len(
        resultados[
            "ventas_existentes"
        ]
    )

    excluidas = len(
        resultados[
            "ventas_excluidas"
        ]
    )

    duplicadas = len(
        resultados[
            "ventas_duplicadas"
        ]
    )

    total_final = len(
        final
    )

    revision = (
        int(
            final[
                "__REQUIERE_REVISION"
            ]
            .fillna(False)
            .sum()
        )
        if "__REQUIERE_REVISION"
        in final.columns
        else 0
    )

    a, b, c = st.columns(
        3
    )

    a.metric(
        "Comisiones originales",
        original
    )

    b.metric(
        "Ventas nuevas agregadas",
        nuevas
    )

    c.metric(
        "Total final",
        total_final
    )

    d, e, f = st.columns(
        3
    )

    d.metric(
        "Ventas ya existentes",
        existentes
    )

    e.metric(
        "Ventas excluidas",
        excluidas
    )

    f.metric(
        "Revisión manual",
        revision
    )

    if duplicadas:
        st.info(
            f"Duplicados entre reportes "
            f"de Ventas: {duplicadas}"
        )

    st.write(
        f"Hoja de Comisiones utilizada: "
        f"**{resultados['hoja_comisiones']}**"
    )

    if resultados[
        "mes_r34"
    ]:
        st.write(
            f"Mes detectado en R34: "
            f"**{resultados['mes_r34']}**"
        )


    # =====================================================
    # DETALLE R34
    # =====================================================

    with st.expander(
        "Detalle del R34"
    ):
        for detalle in resultados[
            "detalle_r34"
        ]:
            st.write(
                f"**{detalle.get('archivo', '')}**"
            )

            st.write(
                f"Filas leídas: "
                f"{detalle.get('filas_leidas', 0):,}"
            )

            st.write(
                f"Filas cuya PERTENENCIA "
                f"contiene CredicardPos: "
                f"{detalle.get('filas_credicardpos', 0):,}"
            )

            if detalle.get(
                "mes_proceso"
            ):
                st.write(
                    f"MES_PROCESO: "
                    f"{detalle['mes_proceso']}"
                )

            st.divider()


    # =====================================================
    # ADVERTENCIAS
    # =====================================================

    if resultados[
        "advertencias"
    ]:
        with st.expander(
            "Advertencias"
        ):
            for aviso in resultados[
                "advertencias"
            ]:
                st.warning(
                    aviso
                )


    st.divider()


    # =====================================================
    # 6. REVISIÓN MANUAL
    # =====================================================

    st.subheader(
        "6. Revisión manual"
    )

    problemas = final[
        final[
            "__REQUIERE_REVISION"
        ].fillna(False)
    ].copy()

    if problemas.empty:
        st.success(
            "No hay filas pendientes "
            "de revisión manual."
        )

    else:
        st.write(
            "Solo aparecen filas pendientes "
            "que el programa no pudo resolver "
            "de forma segura."
        )

        st.write(
            "Puedes modificar sus celdas "
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

        # No mostramos columnas internas,
        # salvo el ID y el motivo de revisión.
        for columna in final.columns:
            if not str(
                columna
            ).startswith("__"):
                columnas_visibles.append(
                    columna
                )

        if "__MOTIVO_REVISION" in problemas.columns:
            columnas_visibles.append(
                "__MOTIVO_REVISION"
            )

        if "__ROW_ID" in problemas.columns:
            columnas_visibles.append(
                "__ROW_ID"
            )

        columnas_visibles = list(
            dict.fromkeys(
                columna
                for columna in columnas_visibles
                if columna in problemas.columns
            )
        )

        columnas_bloqueadas = [
            columna
            for columna in [
                "__ROW_ID",
                "__MOTIVO_REVISION",
            ]
            if columna in columnas_visibles
        ]

        tabla_revision = problemas[
            columnas_visibles
        ].copy()

        for columna in tabla_revision.columns:

            if columna == "Eliminar":
                continue

            if columna == "__ROW_ID":
                continue

            tabla_revision[
                columna
            ] = (
                tabla_revision[
                    columna
                ]
                .astype("string")
                .fillna("")
            )


        editado = st.data_editor(
            tabla_revision,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            disabled=
                columnas_bloqueadas,

            column_config={
                "Eliminar":
                    st.column_config.CheckboxColumn(
                        "Eliminar",
                        default=False,
                    ),

                "__ROW_ID":
                    st.column_config.NumberColumn(
                        "ID interno"
                    ),

                "__MOTIVO_REVISION":
                    st.column_config.TextColumn(
                        "Motivo de revisión"
                    ),
            },
            key="revision_v3",
        )

        if st.button(
            "Aplicar correcciones y revalidar",
            use_container_width=True,
        ):
            base = resultados[
                "final"
            ].copy()

            if "__ROW_ID" in editado.columns:
                ids_eliminar = set(
                    editado.loc[
                        editado[
                            "Eliminar"
                        ] == True,
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

            conservar = editado[
                editado[
                    "Eliminar"
                ] == False
            ].copy()

            conservar = conservar.drop(
                columns=[
                    "Eliminar"
                ]
            )

            if (
                "__ROW_ID"
                in conservar.columns
                and "__ROW_ID"
                in base.columns
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
                        if columna in {
                            "__ROW_ID",
                            "__MOTIVO_REVISION",
                        }:
                            continue

                        if columna in base.columns:
                            base.loc[
                                mascara,
                                columna
                            ] = fila[
                                columna
                            ]

            recalculado = recalcular_comisiones(
                base,
                resultados[
                    "r34"
                ],
                resultados[
                    "afiliados_access"
                ],
                mes_r34=
                    resultados[
                        "mes_r34"
                    ],
            )

            resultados[
                "final"
            ] = recalculado

            st.session_state[
                "resultados"
            ] = resultados

            st.success(
                "Correcciones aplicadas."
            )

            st.rerun()


    st.divider()


    # =====================================================
    # 7. VISTA PREVIA
    # =====================================================

    st.subheader(
        "7. Archivo de Comisiones resultante"
    )

    columnas_publicas = [
        columna
        for columna in final.columns
        if not str(
            columna
        ).startswith("__")
    ]

    vista_previa = final[
        columnas_publicas
    ].head(
        200
    ).copy()

    for columna in vista_previa.columns:

        vista_previa[
            columna
        ] = (
            vista_previa[
                columna
            ]
            .astype("string")
            .fillna("")
        )


    st.dataframe(
        vista_previa,
        hide_index=True,
        use_container_width=True,
    )

    st.caption(
        "Vista previa de las primeras "
        "200 filas. El Excel descargado "
        "conserva el libro original."
    )


    # =====================================================
    # 8. DESCARGA
    # =====================================================

    try:
        excel_final = generar_excel_resultado(
            resultados
        )

        st.download_button(
            "Descargar archivo de Comisiones actualizado",
            data=
                excel_final,

            file_name=
                "Comisiones_Actualizadas.xlsx",

            mime=(
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            ),

            type="primary",
            use_container_width=True,
        )

        st.success(
            "La descarga parte del mismo "
            "archivo de Comisiones y conserva "
            "las demás hojas."
        )

    except Exception as error:
        st.error(
            "No se pudo preparar "
            "el Excel final."
        )

        st.exception(
            error
        )


# =========================================================
# REINICIAR
# =========================================================

st.divider()

if st.button(
    "Limpiar resultados y comenzar otra vez",
    use_container_width=True,
):
    st.session_state.clear()

    st.session_state[
        "version_app"
    ] = VERSION_APP

    st.rerun()

