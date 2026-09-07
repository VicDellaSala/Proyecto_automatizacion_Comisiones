import streamlit as st

from procesamiento import (
    procesar_todo,
    generar_excel_resultado,
    VERSION_PROCESAMIENTO,
)

from reglas_comisiones import PRECIOS_BASE
from revision_manual import preparar_descarga


VERSION_APP = "5.0-REVISION-NUEVAS"


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
    "columna_afiliado_access",
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

        st.session_state.pop("excel_final_generado", None)

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
                    precios=st.session_state["precios"],
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

            st.session_state["revision_nuevas"] = {}
            st.session_state.pop("excel_final_generado", None)
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

    d, e = st.columns(2)

    d.metric(
        "Ventas ya existentes",
        existentes
    )

    e.metric(
        "Ventas excluidas",
        excluidas
    )

    st.metric(
        "Filas con coincidencia verificada en Access",
        int(final["__ACCESS_CALCULADO"].eq("SI").sum()),
    )
    st.caption(
        f"Columna de Access utilizada: {resultados['columna_afiliado_access']}. "
        "El contador verifica el archivo cargado por afiliado; excluye Pinpagos. "
        "Los valores históricos de filas no pendientes se conservan en el libro."
    )

    if "__REGLA_COMISION" in final.columns:
        with st.expander("Cálculo y cuadre de comisiones"):
            detalle_comisiones = final[[
                "__ROW_ID", "__REGLA_COMISION", "__TOTAL_COMISION_CALCULADO",
                "__MONTO_PENDIENTE_ASIGNACION", "__DIFERENCIA_CUADRE_COMISION",
                "__ADVERTENCIA_COMISION",
            ]].rename(columns={
                "__ROW_ID": "ID interno", "__REGLA_COMISION": "Regla aplicada",
                "__TOTAL_COMISION_CALCULADO": "Total según regla (USD)",
                "__MONTO_PENDIENTE_ASIGNACION": "Pendiente de beneficiario (USD)",
                "__DIFERENCIA_CUADRE_COMISION": "Componentes menos total (USD)",
                "__ADVERTENCIA_COMISION": "Revisión de comisión",
            })
            st.dataframe(detalle_comisiones.astype("string").fillna(""), hide_index=True, use_container_width=True)
            st.caption("Los importes históricos se conservan. Las diferencias requieren revisión; "
                       "las filas sin importes se completan cuando la regla y los beneficiarios están definidos.")

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
                f"Filas con PERTENENCIA "
                f"en la lista permitida: "
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


    from revision_ui import mostrar_revision
    pendientes_manuales = mostrar_revision(resultados, st.session_state["precios"])

# =====================================================
# 8. PREPARAR Y DESCARGAR EXCEL
# =====================================================

st.subheader(
    "GENERAR / DESCARGAR EXCEL FINAL"
)

st.info(
    "Para ahorrar memoria, el Excel final "
    "solo se prepara cuando pulses el botón."
)


if "resultados" not in st.session_state:
    st.stop()

if pendientes_manuales:
    st.session_state.pop("excel_final_generado", None)
    st.warning("Debes completar las revisiones manuales pendientes de las ventas nuevas antes de generar el Excel.")
    st.stop()

if "excel_final_generado" not in st.session_state:

    if st.button(
        "Generar Excel final",
        type="primary",
        use_container_width=True,
    ):

        try:

            with st.spinner(
                "Preparando el archivo de Comisiones..."
            ):

                resultados = preparar_descarga(resultados, st.session_state.get("revision_nuevas", {}),
                                                precios=st.session_state["precios"])
                st.session_state["resultados"] = resultados
                excel_final = generar_excel_resultado(
                    resultados
                )

                st.session_state[
                    "excel_final_generado"
                ] = excel_final

            st.success(
                "Archivo preparado correctamente."
            )

            st.rerun()

        except Exception as error:

            st.error(
                "No se pudo preparar el Excel final."
            )

            st.exception(
                error
            )


if "excel_final_generado" in st.session_state:

    st.success(
        "El archivo está listo para descargar."
    )

    st.download_button(
        "Descargar archivo de Comisiones actualizado",
        data=st.session_state[
            "excel_final_generado"
        ],
        file_name="Comisiones_Actualizadas.xlsx",
        mime=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),
        type="primary",
        use_container_width=True,
    )

    if st.button(
        "Volver a preparar el archivo",
        use_container_width=True,
    ):

        del st.session_state[
            "excel_final_generado"
        ]

        st.rerun()
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

