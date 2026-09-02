import streamlit as st

from procesamiento import (
    generar_excel_resultado,
    procesar_todo,
    recalcular_comisiones,
)

from reglas_comisiones import (
    PRECIOS_BASE,
)


# =========================================================
# CONFIGURACIÓN
# =========================================================

st.set_page_config(

    page_title=
        "Automatización de Comisiones",

    page_icon=
        "💰",

    layout=
        "wide",

)


# =========================================================
# TÍTULO
# =========================================================

st.title(
    "Automatización de Comisiones"
)

st.write(

    "Carga los archivos necesarios "
    "y ejecuta el procesamiento."

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
            "Puedes cargar el R34 "
            "en CSV, ZIP o varias partes."
        ),

    )

    archivos_ventas = st.file_uploader(

        "Reporte(s) de Ventas",

        type=[
            "xlsx",
        ],

        accept_multiple_files=True,

        help=(
            "Puedes cargar uno "
            "o varios meses."
        ),

    )


with col2:

    archivo_comisiones = st.file_uploader(

        "Archivo de Comisiones",

        type=[
            "xlsx",
        ],

    )

    archivo_access = st.file_uploader(

        "Access Commerce",

        type=[
            "xlsx",
        ],

    )


st.divider()


# =========================================================
# 2. ESTADO
# =========================================================

st.subheader(
    "2. Estado de carga"
)


# R34

if archivos_r34:

    st.success(

        f"R34 cargado. "
        f"Archivos recibidos: "
        f"{len(archivos_r34)}"

    )

    for archivo in archivos_r34:

        st.write(

            f"• {archivo.name} — "
            f"{archivo.size / (1024 * 1024):.2f} MB"

        )

else:

    st.warning(
        "Falta cargar el R34."
    )


# VENTAS

if archivos_ventas:

    st.success(

        f"Reportes de ventas "
        f"cargados: "
        f"{len(archivos_ventas)}"

    )

    for archivo in archivos_ventas:

        st.write(

            f"• {archivo.name} — "
            f"{archivo.size / (1024 * 1024):.2f} MB"

        )

else:

    st.warning(

        "Falta cargar al menos "
        "un Reporte de Ventas."

    )


# COMISIONES

if archivo_comisiones is not None:

    st.success(

        f"Archivo de Comisiones cargado: "
        f"{archivo_comisiones.name} — "
        f"{archivo_comisiones.size / (1024 * 1024):.2f} MB"

    )

else:

    st.warning(

        "Falta cargar el "
        "Archivo de Comisiones."

    )


# ACCESS

if archivo_access is not None:

    st.success(

        f"Access Commerce cargado: "
        f"{archivo_access.name} — "
        f"{archivo_access.size / (1024 * 1024):.2f} MB"

    )

else:

    st.warning(
        "Falta cargar Access Commerce."
    )


st.divider()


# =========================================================
# 3. PRECIOS
# =========================================================

st.subheader(
    "3. Configuración de precios"
)

st.caption(

    "Son los precios base. "
    "Puedes modificarlos "
    "para cada procesamiento."

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
    "precios_equipos"
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
# 4. PROCESAMIENTO
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

    and (
        archivo_comisiones
        is not None
    )

    and (
        archivo_access
        is not None
    )

)


if not todos_cargados:

    st.info(

        "Carga los cuatro tipos "
        "de archivos para habilitar "
        "el procesamiento."

    )


else:

    st.success(

        "Todos los archivos "
        "necesarios están cargados."

    )

    if st.button(

        "Iniciar procesamiento",

        type="primary",

        use_container_width=True,

    ):

        try:

            with st.spinner(

                "Procesando R34 por bloques, "
                "limpiando ventas y realizando cruces..."

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

            st.session_state[
                "resultados"
            ] = resultados

            st.success(

                "Procesamiento inicial "
                "completado."

            )

        except Exception as e:

            st.error(
                "Ocurrió un error durante "
                "el procesamiento."
            )

            st.exception(
                e
            )


# =========================================================
# 5. RESULTADOS
# =========================================================

if (
    "resultados"
    in st.session_state
):

    resultados = st.session_state[
        "resultados"
    ]

    final = resultados[
        "final"
    ]

    st.divider()

    st.subheader(
        "5. Resumen del procesamiento"
    )


    total = len(
        final
    )


    if (
        "__REQUIERE_REVISION"
        in final.columns
    ):

        revision = int(

            final[
                "__REQUIERE_REVISION"
            ].sum()

        )

    else:

        revision = 0


    nuevas = len(

        resultados[
            "ventas_nuevas"
        ]

    )


    excluidas = len(

        resultados[
            "ventas_excluidas"
        ]

    )


    ya_existentes = len(

        resultados[
            "ventas_ya_existentes"
        ]

    )


    m1, m2, m3, m4, m5 = st.columns(
        5
    )


    m1.metric(
        "Comisiones",
        total
    )

    m2.metric(
        "Ventas nuevas",
        nuevas
    )

    m3.metric(
        "Ya existentes",
        ya_existentes
    )

    m4.metric(
        "Ventas excluidas",
        excluidas
    )

    m5.metric(
        "Revisión manual",
        revision
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

                f"*{detalle['archivo']}*"

            )

            st.write(

                f"Filas leídas: "
                f"{detalle['filas_leidas']:,}"

            )

            st.write(

                f"Filas CredicardPos: "
                f"{detalle['filas_credicardpos']:,}"

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
        ]

    ].copy()


    if problemas.empty:

        st.success(

            "No hay registros marcados "
            "para revisión manual."

        )


    else:

        st.write(

            "Puedes modificar directamente "
            "las celdas que necesites."

        )

        st.write(

            "También puedes marcar "
            "*Eliminar* si una fila "
            "no debe continuar."

        )


        # Casilla de eliminar

        problemas.insert(

            0,

            "Eliminar",

            False

        )


        # Columnas visibles

        columnas_mostrar = [
            "Eliminar"
        ]


        for col in final.columns:

            if not str(
                col
            ).startswith(
                "__"
            ):

                columnas_mostrar.append(
                    col
                )


        # Necesitamos el ID interno
        # para saber qué fila modificar.

        columnas_mostrar.append(
            "__ROW_ID"
        )


        columnas_mostrar = [

            c

            for c
            in columnas_mostrar

            if c
            in problemas.columns

        ]


        editado = st.data_editor(

            problemas[
                columnas_mostrar
            ],

            use_container_width=True,

            hide_index=True,

            num_rows="fixed",

            disabled=[
                "__ROW_ID"
            ],

            column_config={

                "Eliminar":

                    st.column_config.CheckboxColumn(

                        "Eliminar",

                        help=(
                            "Marca para borrar "
                            "esta fila."
                        ),

                        default=False,

                    ),

                "__ROW_ID":

                    st.column_config.NumberColumn(

                        "ID interno",

                        help=(
                            "No modificar."
                        ),

                    ),

            },

            key=
                "editor_revision",

        )


        # =================================================
        # APLICAR CAMBIOS
        # =================================================

        if st.button(

            "Aplicar correcciones y revalidar",

            use_container_width=True,

        ):

            base = resultados[
                "final"
            ].copy()


            # =============================================
            # ELIMINAR FILAS MARCADAS
            # =============================================

            ids_eliminar = set(

                editado.loc[

                    editado[
                        "Eliminar"
                    ]
                    == True,

                    "__ROW_ID",

                ].tolist()

            )


            base = base[

                ~base[
                    "__ROW_ID"
                ].isin(
                    ids_eliminar
                )

            ].copy()


            # =============================================
            # FILAS MODIFICADAS
            # =============================================

            editado_sin_eliminar = (

                editado[

                    editado[
                        "Eliminar"
                    ]
                    == False

                ]

                .drop(

                    columns=[
                        "Eliminar"
                    ]

                )

            )


            for _, fila in (
                editado_sin_eliminar
                .iterrows()
            ):

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


                for col in (

                    editado_sin_eliminar
                    .columns

                ):

                    if (
                        col
                        == "__ROW_ID"
                    ):

                        continue


                    if col in base.columns:

                        base.loc[

                            mascara,

                            col

                        ] = fila[
                            col
                        ]


            # =============================================
            # REVALIDAR
            # =============================================

            recalculado = (

                recalcular_comisiones(

                    base,

                    resultados[
                        "r34"
                    ],

                    resultados[
                        "afiliados_access"
                    ],

                )

            )


            resultados[
                "final"
            ] = recalculado


            st.session_state[
                "resultados"
            ] = resultados


            st.success(

                "Cambios aplicados "
                "y datos revalidados."

            )


            st.rerun()


    st.divider()


    # =====================================================
    # 7. RESULTADO FINAL
    # =====================================================

    st.subheader(
        "7. Resultado"
    )


    vista = resultados[
        "final"
    ].copy()


    columnas_publicas = [

        col

        for col
        in vista.columns

        if not str(
            col
        ).startswith(
            "__"
        )

    ]


    st.dataframe(

        vista[
            columnas_publicas
        ].head(
            200
        ),

        use_container_width=True,

    )


    st.caption(

        "La vista previa muestra "
        "las primeras 200 filas."

    )


    # =====================================================
    # EXCEL
    # =====================================================

    excel = generar_excel_resultado(
        resultados
    )


    st.download_button(

        "Descargar Excel procesado",

        data=
            excel,

        file_name=
            "Comisiones_Procesadas.xlsx",

        mime=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),

        type="primary",

        use_container_width=True,

    )


    st.info(

        "Esta versión prueba: R34 grande, "
        "ventas, cruces, seriales, "
        "transacciones, Access Commerce, "
        "regla especial de Pinpagos "
        "y revisión manual."

    )