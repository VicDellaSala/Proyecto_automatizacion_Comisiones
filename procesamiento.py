import csv
import io
import re
import unicodedata
import zipfile

from datetime import datetime
from datetime import timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from reglas_comisiones import (
    estandarizar_equipo,
)


# =========================================================
# NOMBRES POSIBLES DE COLUMNAS
# =========================================================

ALIASES = {

    "pertenencia": [
        "PERTENENCIA",
    ],

    "afipos": [
        "AFIPOS",
        "AFI POS",
        "AFI_POS",
    ],

    "afiliado": [
        "AFILIADO",
        "AFILIACION",
        "AFILIACIÓN",
        "COD AFILIADO",
        "CODIGO AFILIADO",
        "CÓDIGO AFILIADO",
        "NUMERO AFILIADO",
        "NRO AFILIADO",
    ],

    "terminal": [
        "TERMINAL",
        "NRO TERMINAL",
        "NUMERO TERMINAL",
        "NÚMERO TERMINAL",
    ],

    "serial": [
        "SERIAL",
        "SERIALES",
        "SERIAL EQUIPO",
        "SERIAL_EQUIPO",
    ],

    "monto_tx": [
        "MONTO_TRANS_ACUM_MES",
        "MONTO TRANS ACUM MES",
        "MONTO_TRANSACCION_BS_ACUM_MES",
        "MONTO TRANSACCION BS ACUM MES",
        "MONTO_TRANS_BS_ACUM_MES",
        "MONTO TX",
        "MONTO_TX",
    ],

    "concatenar": [
        "CONCATENAR",
        "CONCATENADO",
        "AFILIADO TERMINAL",
        "AFILIADO+TERMINAL",
    ],

    "equipo": [
        "EQUIPO",
        "MODELO",
        "TIPO EQUIPO",
        "MODELO EQUIPO",
        "PRODUCTO",
    ],

    "estatus": [
        "PENDIENTE",
        "ESTATUS",
        "STATUS",
        "ESTADO",
    ],

    "canal": [
        "CANAL DE VENTAS",
        "CANAL DE VENTA",
        "CANAL DE VENTAS (JORNADA QUE PERTENECE)",
        "CANAL",
        "REGION",
        "REGIÓN",
    ],

    "vendedor_agente": [
        "VENDEDOR AGENTE AUTORIZADOS",
        "VENDEDOR AGENTE AUTORIZADO",
        "VENDEDOR/AGENTE AUTORIZADO",
        "VENDEDOR",
        "AGENTE AUTORIZADO",
    ],

    "preafiliado": [
        "PRE AFILIADO",
        "PRE-AFILIADO",
        "PREAFILIADO",
        "PRE AFILIACION",
        "PRE-AFILIACION",
    ],

    "ag_autorizado_flag": [
        "AG AUTORIZADO",
        "AGENTE AUTORIZADO?",
        "ES AGENTE AUTORIZADO",
    ],

    "access": [
        "ACCESS COMMERCE",
        "ACCESS COMERCE",
        "ACCESS",
        "AFILIADO ACCESS",
    ],

    "con_tx": [
        "CON TX",
        "CON_TX",
        "ESTADO TX",
        "ESTATUS TX",
    ],

}


# =========================================================
# NORMALIZAR TEXTO
# =========================================================

def normalizar_texto(valor):

    if valor is None:
        return ""

    if (
        isinstance(valor, float)
        and pd.isna(valor)
    ):
        return ""

    texto = str(
        valor
    ).strip()

    texto = unicodedata.normalize(
        "NFKD",
        texto
    )

    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.upper()


# =========================================================
# NORMALIZAR NOMBRE DE COLUMNA
# =========================================================

def normalizar_nombre_columna(
    nombre
):

    texto = normalizar_texto(
        nombre
    )

    texto = re.sub(
        r"[^A-Z0-9]+",
        " ",
        texto
    )

    return re.sub(
        r"\s+",
        " ",
        texto
    ).strip()


# =========================================================
# BUSCAR COLUMNA AUTOMÁTICAMENTE
# =========================================================

def buscar_columna(
    df,
    tipo
):

    if df is None:
        return None

    if len(
        df.columns
    ) == 0:
        return None

    alias_norm = {
        normalizar_nombre_columna(x)
        for x in ALIASES.get(
            tipo,
            []
        )
    }

    columnas_norm = {
        col: normalizar_nombre_columna(
            col
        )
        for col in df.columns
    }

    # Primero coincidencia exacta

    for col, norm in columnas_norm.items():

        if norm in alias_norm:
            return col

    # Luego coincidencia parcial

    for col, norm in columnas_norm.items():

        for alias in alias_norm:

            if not alias:
                continue

            if (
                alias in norm
                or norm in alias
            ):
                return col

    return None


# =========================================================
# NORMALIZAR IDENTIFICADORES
# =========================================================

def normalizar_identificador(
    valor
):

    if valor is None:
        return ""

    if pd.isna(
        valor
    ):
        return ""

    texto = str(
        valor
    ).strip()

    if texto.upper() in {
        "N/A",
        "N/D",
        "NA",
        "ND",
        "NAN",
        "NONE",
        "-"
    }:
        return texto.upper()

    # Excel puede convertir IDs:
    # 123456 -> 123456.0

    if re.fullmatch(
        r"\d+\.0+",
        texto
    ):
        texto = texto.split(
            "."
        )[0]

    texto = re.sub(
        r"\s+",
        "",
        texto
    )

    return texto


# =========================================================
# NORMALIZAR MONTOS
# =========================================================

def normalizar_numero(
    valor
):

    if valor is None:
        return None

    if pd.isna(
        valor
    ):
        return None

    texto = str(
        valor
    ).strip()

    texto = texto.replace(
        " ",
        ""
    )

    if (
        texto == ""
        or texto.upper()
        in {
            "N/A",
            "N/D",
            "NA",
            "ND",
            "-",
            "NAN"
        }
    ):
        return None

    texto = re.sub(
        r"[^0-9,\.\-]",
        "",
        texto
    )

    # Ejemplo:
    # 1.234,56
    # 1,234.56

    if (
        "," in texto
        and "." in texto
    ):

        if (
            texto.rfind(",")
            >
            texto.rfind(".")
        ):

            texto = (
                texto
                .replace(
                    ".",
                    ""
                )
                .replace(
                    ",",
                    "."
                )
            )

        else:

            texto = texto.replace(
                ",",
                ""
            )

    elif "," in texto:

        texto = (
            texto
            .replace(
                ".",
                ""
            )
            .replace(
                ",",
                "."
            )
        )

    try:

        return float(
            texto
        )

    except ValueError:

        return None


# =========================================================
# CONCATENAR AFILIADO + TERMINAL
# =========================================================

def crear_concatenar(
    afiliado,
    terminal
):

    afiliado = normalizar_identificador(
        afiliado
    )

    terminal = normalizar_identificador(
        terminal
    )

    if (
        not afiliado
        or not terminal
    ):
        return ""

    return (
        f"{afiliado}|{terminal}"
    )


# =========================================================
# VALORES SÍ / NO
# =========================================================

def valor_es_si(
    valor
):

    texto = normalizar_texto(
        valor
    )

    return texto in {
        "SI",
        "SÍ",
        "YES",
        "Y",
        "1",
        "TRUE",
        "X",
    }


# =========================================================
# VIERNES DE LA SEMANA ACTUAL
# =========================================================

def viernes_semana_actual():

    hoy = datetime.now(
        ZoneInfo(
            "America/Caracas"
        )
    ).date()

    viernes = hoy + timedelta(
        days=(
            4
            -
            hoy.weekday()
        )
    )

    return viernes


# =========================================================
# LEER EXCEL
# =========================================================

def leer_excel(
    archivo
):

    archivo.seek(
        0
    )

    return pd.read_excel(
        archivo,
        dtype=str,
        engine="openpyxl",
    )


# =========================================================
# DETECTAR FORMATO DEL CSV
# =========================================================

def detectar_encoding_y_separador(
    stream
):

    posicion = stream.tell()

    muestra = stream.read(
        65536
    )

    stream.seek(
        posicion
    )

    if isinstance(
        muestra,
        str
    ):

        texto = muestra
        encoding = None

    else:

        encoding = "utf-8-sig"

        try:

            texto = muestra.decode(
                encoding
            )

        except UnicodeDecodeError:

            encoding = "latin-1"

            texto = muestra.decode(
                encoding,
                errors="replace",
            )

    try:

        dialecto = csv.Sniffer().sniff(
            texto,
            delimiters=[
                ",",
                ";",
                "\t",
                "|",
            ]
        )

        separador = (
            dialecto.delimiter
        )

    except csv.Error:

        if (
            texto.count(";")
            >
            texto.count(",")
        ):

            separador = ";"

        else:

            separador = ","

    return (
        encoding,
        separador,
    )


# =========================================================
# SERIAL PINPAGOS DESDE TERMINAL
# =========================================================

def extraer_serial_desde_terminal(
    valor
):

    texto = normalizar_identificador(
        valor
    )

    if not texto:
        return ""

    # Primero busca un bloque numérico largo

    match = re.search(
        r"\d{5,}",
        texto
    )

    if match:
        return match.group(
            0
        )

    # Si no, toma lo que esté
    # antes del primer separador.

    return re.split(
        r"[\s/|\\;,_-]+",
        texto
    )[0]


# =========================================================
# PROCESAR UN CSV DEL R34
# =========================================================

def procesar_stream_r34(
    stream,
    nombre_origen,
    chunksize=100_000,
):

    stream.seek(
        0
    )

    encoding, separador = (
        detectar_encoding_y_separador(
            stream
        )
    )

    stream.seek(
        0
    )

    partes = []

    info = {

        "archivo":
            nombre_origen,

        "filas_leidas":
            0,

        "filas_credicardpos":
            0,
    }

    advertencias = []

    lector = pd.read_csv(

        stream,

        sep=separador,

        encoding=encoding,

        dtype=str,

        chunksize=chunksize,

        on_bad_lines="skip",

        low_memory=False,

    )

    columnas_detectadas = None

    for chunk in lector:

        info[
            "filas_leidas"
        ] += len(
            chunk
        )

        # Detectamos las columnas una sola vez

        if columnas_detectadas is None:

            columnas_detectadas = {

                "pertenencia":
                    buscar_columna(
                        chunk,
                        "pertenencia",
                    ),

                "afipos":
                    buscar_columna(
                        chunk,
                        "afipos",
                    ),

                "afiliado":
                    buscar_columna(
                        chunk,
                        "afiliado",
                    ),

                "terminal":
                    buscar_columna(
                        chunk,
                        "terminal",
                    ),

                "serial":
                    buscar_columna(
                        chunk,
                        "serial",
                    ),

                "monto_tx":
                    buscar_columna(
                        chunk,
                        "monto_tx",
                    ),

            }

            if (
                columnas_detectadas[
                    "pertenencia"
                ]
                is None
            ):

                raise ValueError(
                    f"No encontré la columna "
                    f"PERTENENCIA en "
                    f"{nombre_origen}."
                )

            if (
                columnas_detectadas[
                    "monto_tx"
                ]
                is None
            ):

                advertencias.append(

                    f"{nombre_origen}: "
                    f"no encontré la columna "
                    f"del monto transado."

                )

        # =================================================
        # SOLO CREDICARDPOS
        # =================================================

        col_pertenencia = (
            columnas_detectadas[
                "pertenencia"
            ]
        )

        mascara = (
            chunk[
                col_pertenencia
            ]
            .map(
                normalizar_texto
            )
            .eq(
                "CREDICARDPOS"
            )
        )

        filtrado = (
            chunk.loc[
                mascara
            ]
            .copy()
        )

        info[
            "filas_credicardpos"
        ] += len(
            filtrado
        )

        if filtrado.empty:
            continue

        col_afiliado = (
            columnas_detectadas[
                "afiliado"
            ]
        )

        col_terminal = (
            columnas_detectadas[
                "terminal"
            ]
        )

        col_serial = (
            columnas_detectadas[
                "serial"
            ]
        )

        col_monto = (
            columnas_detectadas[
                "monto_tx"
            ]
        )

        col_afipos = (
            columnas_detectadas[
                "afipos"
            ]
        )

        # =================================================
        # CAMPOS INTERNOS
        # =================================================

        if col_afiliado:

            filtrado[
                "__AFILIADO"
            ] = filtrado[
                col_afiliado
            ].map(
                normalizar_identificador
            )

        else:

            filtrado[
                "__AFILIADO"
            ] = ""

        if col_terminal:

            filtrado[
                "__TERMINAL"
            ] = filtrado[
                col_terminal
            ].map(
                normalizar_identificador
            )

        else:

            filtrado[
                "__TERMINAL"
            ] = ""

        if col_serial:

            filtrado[
                "__SERIAL"
            ] = filtrado[
                col_serial
            ].map(
                normalizar_identificador
            )

        else:

            filtrado[
                "__SERIAL"
            ] = ""

        if col_monto:

            filtrado[
                "__MONTO_TX"
            ] = filtrado[
                col_monto
            ].map(
                normalizar_numero
            )

        else:

            filtrado[
                "__MONTO_TX"
            ] = None

        if col_afipos:

            filtrado[
                "__AFIPOS"
            ] = filtrado[
                col_afipos
            ].astype(
                str
            ).str.strip()

        else:

            filtrado[
                "__AFIPOS"
            ] = ""

        # Pinpagos:
        # guardamos un serial candidato
        # proveniente del TERMINAL.

        filtrado[
            "__SERIAL_DESDE_TERMINAL"
        ] = filtrado[
            "__TERMINAL"
        ].map(
            extraer_serial_desde_terminal
        )

        filtrado[
            "__CONCATENAR"
        ] = [

            crear_concatenar(
                afiliado,
                terminal
            )

            for afiliado, terminal
            in zip(

                filtrado[
                    "__AFILIADO"
                ],

                filtrado[
                    "__TERMINAL"
                ],

            )
        ]

        filtrado[
            "__ORIGEN_R34"
        ] = nombre_origen

        # Para no guardar 600 MB
        # en memoria solo dejamos
        # lo que necesitamos.

        mantener = [

            "__AFILIADO",

            "__TERMINAL",

            "__SERIAL",

            "__MONTO_TX",

            "__AFIPOS",

            "__SERIAL_DESDE_TERMINAL",

            "__CONCATENAR",

            "__ORIGEN_R34",

        ]

        partes.append(
            filtrado[
                mantener
            ]
        )

    if partes:

        resultado = pd.concat(
            partes,
            ignore_index=True,
        )

    else:

        resultado = pd.DataFrame(

            columns=[

                "__AFILIADO",

                "__TERMINAL",

                "__SERIAL",

                "__MONTO_TX",

                "__AFIPOS",

                "__SERIAL_DESDE_TERMINAL",

                "__CONCATENAR",

                "__ORIGEN_R34",

            ]

        )

    return (
        resultado,
        info,
        advertencias,
    )


# =========================================================
# PROCESAR R34 COMPLETO
# =========================================================

def procesar_r34(
    archivos_r34,
    chunksize=100_000,
):

    resultados = []

    detalles = []

    advertencias = []

    for archivo in archivos_r34:

        nombre = (
            archivo.name.lower()
        )

        archivo.seek(
            0
        )

        # =================================================
        # ZIP
        # =================================================

        if nombre.endswith(
            ".zip"
        ):

            contenido = (
                archivo.getvalue()
            )

            with zipfile.ZipFile(
                io.BytesIO(
                    contenido
                )
            ) as zf:

                csvs = [

                    nombre_interno

                    for nombre_interno
                    in zf.namelist()

                    if (
                        nombre_interno
                        .lower()
                        .endswith(
                            ".csv"
                        )
                    )

                    and not (
                        nombre_interno
                        .startswith(
                            "__MACOSX/"
                        )
                    )

                ]

                if not csvs:

                    raise ValueError(

                        f"El ZIP "
                        f"{archivo.name} "
                        f"no contiene ningún CSV."

                    )

                for nombre_csv in csvs:

                    with zf.open(
                        nombre_csv,
                        "r"
                    ) as stream:

                        (
                            df,
                            info,
                            avisos,
                        ) = procesar_stream_r34(

                            stream,

                            (
                                f"{archivo.name}"
                                f"::{nombre_csv}"
                            ),

                            chunksize,

                        )

                        resultados.append(
                            df
                        )

                        detalles.append(
                            info
                        )

                        advertencias.extend(
                            avisos
                        )

        # =================================================
        # CSV DIRECTO
        # =================================================

        elif nombre.endswith(
            ".csv"
        ):

            (
                df,
                info,
                avisos,
            ) = procesar_stream_r34(

                archivo,

                archivo.name,

                chunksize,

            )

            resultados.append(
                df
            )

            detalles.append(
                info
            )

            advertencias.extend(
                avisos
            )

        else:

            raise ValueError(

                f"Formato de R34 "
                f"no soportado: "
                f"{archivo.name}"

            )

    if resultados:

        r34 = pd.concat(

            resultados,

            ignore_index=True,

        )

    else:

        r34 = pd.DataFrame()

    return (
        r34,
        detalles,
        advertencias,
    )


# =========================================================
# PREPARAR VENTAS
# =========================================================

def preparar_ventas(
    archivos_ventas
):

    partes = []

    excluidas = []

    advertencias = []

    for archivo in archivos_ventas:

        df = leer_excel(
            archivo
        )

        df[
            "__ARCHIVO_ORIGEN"
        ] = archivo.name

        col_afiliado = buscar_columna(
            df,
            "afiliado"
        )

        col_terminal = buscar_columna(
            df,
            "terminal"
        )

        col_concatenar = buscar_columna(
            df,
            "concatenar"
        )

        col_equipo = buscar_columna(
            df,
            "equipo"
        )

        col_pre = buscar_columna(
            df,
            "preafiliado"
        )

        col_ag_flag = buscar_columna(
            df,
            "ag_autorizado_flag"
        )

        # =================================================
        # AFILIADO
        # =================================================

        if col_afiliado:

            df[
                "__AFILIADO"
            ] = df[
                col_afiliado
            ].map(
                normalizar_identificador
            )

        else:

            df[
                "__AFILIADO"
            ] = ""

        # =================================================
        # TERMINAL
        # =================================================

        if col_terminal:

            df[
                "__TERMINAL"
            ] = df[
                col_terminal
            ].map(
                normalizar_identificador
            )

        else:

            df[
                "__TERMINAL"
            ] = ""

        # =================================================
        # CONCATENAR
        # =================================================

        if col_concatenar:

            existente = df[
                col_concatenar
            ].map(
                normalizar_identificador
            )

            creado = [

                crear_concatenar(
                    afiliado,
                    terminal
                )

                for afiliado, terminal
                in zip(

                    df[
                        "__AFILIADO"
                    ],

                    df[
                        "__TERMINAL"
                    ],

                )

            ]

            df[
                "__CONCATENAR"
            ] = [

                e if e else c

                for e, c
                in zip(
                    existente,
                    creado
                )

            ]

        else:

            df[
                "__CONCATENAR"
            ] = [

                crear_concatenar(
                    afiliado,
                    terminal
                )

                for afiliado, terminal
                in zip(

                    df[
                        "__AFILIADO"
                    ],

                    df[
                        "__TERMINAL"
                    ],

                )

            ]

        # =================================================
        # EQUIPO
        # =================================================

        if col_equipo:

            df[
                "__EQUIPO_STD"
            ] = df[
                col_equipo
            ].map(
                estandarizar_equipo
            )

        else:

            df[
                "__EQUIPO_STD"
            ] = ""

        df[
            "__MOTIVO_EXCLUSION"
        ] = ""

        # =================================================
        # TERMINAL = 0 / NO SIMCARD
        # =================================================

        mascara_terminal_0 = (
            df[
                "__TERMINAL"
            ]
            .isin(
                {
                    "0",
                    "0.0",
                }
            )
        )

        df.loc[

            mascara_terminal_0,

            "__MOTIVO_EXCLUSION"

        ] = (
            "Terminal = 0 / No Simcard"
        )

        # =================================================
        # PRE-AFILIADOS
        # =================================================

        if col_pre:

            mascara_pre = df[
                col_pre
            ].map(

                lambda x:

                valor_es_si(x)

                or (
                    "PRE"
                    in normalizar_texto(
                        x
                    )
                )

            )

            df.loc[

                mascara_pre

                & (
                    df[
                        "__MOTIVO_EXCLUSION"
                    ]
                    == ""
                ),

                "__MOTIVO_EXCLUSION"

            ] = "Pre-afiliado"

        # =================================================
        # AGENTES AUTORIZADOS
        # =================================================
        #
        # Aquí soy conservador:
        # solo se elimina automáticamente si existe
        # una columna explícita que diga que es
        # Agente Autorizado.
        #
        # No voy a eliminar por simplemente encontrar
        # un nombre en vendedor porque esa regla todavía
        # puede necesitar ajuste.
        # =================================================

        if col_ag_flag:

            mascara_ag = df[
                col_ag_flag
            ].map(
                valor_es_si
            )

            df.loc[

                mascara_ag

                & (
                    df[
                        "__MOTIVO_EXCLUSION"
                    ]
                    == ""
                ),

                "__MOTIVO_EXCLUSION"

            ] = (
                "Venta AG Autorizado"
            )

        else:

            advertencias.append(

                f"{archivo.name}: "
                f"no encontré una columna "
                f"explícita para identificar "
                f"ventas de AG Autorizados. "
                f"No se eliminaron automáticamente."

            )

        # =================================================
        # SEPARAR
        # =================================================

        excl = df[

            df[
                "__MOTIVO_EXCLUSION"
            ]
            != ""

        ].copy()

        ok = df[

            df[
                "__MOTIVO_EXCLUSION"
            ]
            == ""

        ].copy()

        excluidas.append(
            excl
        )

        partes.append(
            ok
        )

    # =====================================================
    # UNIR VARIOS MESES
    # =====================================================

    if partes:

        ventas = pd.concat(

            partes,

            ignore_index=True,

        )

    else:

        ventas = pd.DataFrame()

    if excluidas:

        ventas_excluidas = pd.concat(

            excluidas,

            ignore_index=True,

        )

    else:

        ventas_excluidas = pd.DataFrame()

    # =====================================================
    # DUPLICADOS ENTRE LOS REPORTES SUBIDOS
    # =====================================================

    if (
        not ventas.empty
        and "__CONCATENAR"
        in ventas.columns
    ):

        ventas[
            "__DUPLICADO_ENTRE_VENTAS"
        ] = (

            ventas.duplicated(
                "__CONCATENAR",
                keep="first"
            )

            & ventas[
                "__CONCATENAR"
            ].ne(
                ""
            )

        )

        duplicadas = ventas[

            ventas[
                "__DUPLICADO_ENTRE_VENTAS"
            ]

        ].copy()

        ventas = ventas[

            ~ventas[
                "__DUPLICADO_ENTRE_VENTAS"
            ]

        ].copy()

    else:

        duplicadas = pd.DataFrame()

    return (

        ventas,

        ventas_excluidas,

        duplicadas,

        advertencias,

    )


# =========================================================
# PREPARAR COMISIONES
# =========================================================

def preparar_comisiones(
    archivo_comisiones
):

    df = leer_excel(
        archivo_comisiones
    )

    df[
        "__ORIGEN"
    ] = (
        "COMISIONES"
    )

    df[
        "__ROW_ID"
    ] = range(
        1,
        len(df) + 1
    )

    col_afiliado = buscar_columna(
        df,
        "afiliado"
    )

    col_terminal = buscar_columna(
        df,
        "terminal"
    )

    col_concatenar = buscar_columna(
        df,
        "concatenar"
    )

    col_serial = buscar_columna(
        df,
        "serial"
    )

    col_equipo = buscar_columna(
        df,
        "equipo"
    )

    if col_afiliado:

        df[
            "__AFILIADO"
        ] = df[
            col_afiliado
        ].map(
            normalizar_identificador
        )

    else:

        df[
            "__AFILIADO"
        ] = ""

    if col_terminal:

        df[
            "__TERMINAL"
        ] = df[
            col_terminal
        ].map(
            normalizar_identificador
        )

    else:

        df[
            "__TERMINAL"
        ] = ""

    if col_serial:

        df[
            "__SERIAL_COMISION"
        ] = df[
            col_serial
        ].map(
            normalizar_identificador
        )

    else:

        df[
            "__SERIAL_COMISION"
        ] = ""

    if col_equipo:

        df[
            "__EQUIPO_STD"
        ] = df[
            col_equipo
        ].map(
            estandarizar_equipo
        )

    else:

        df[
            "__EQUIPO_STD"
        ] = ""

    # =====================================================
    # CONCATENAR
    # =====================================================

    if col_concatenar:

        existente = df[
            col_concatenar
        ].map(
            normalizar_identificador
        )

        creado = [

            crear_concatenar(
                afiliado,
                terminal
            )

            for afiliado, terminal
            in zip(

                df[
                    "__AFILIADO"
                ],

                df[
                    "__TERMINAL"
                ],

            )

        ]

        df[
            "__CONCATENAR"
        ] = [

            e if e else c

            for e, c
            in zip(
                existente,
                creado
            )

        ]

    else:

        df[
            "__CONCATENAR"
        ] = [

            crear_concatenar(
                afiliado,
                terminal
            )

            for afiliado, terminal
            in zip(

                df[
                    "__AFILIADO"
                ],

                df[
                    "__TERMINAL"
                ],

            )

        ]

    return df


# =========================================================
# COPIAR VENTAS NUEVAS AL FORMATO COMISIONES
# =========================================================

def copiar_ventas_a_plantilla(
    ventas_nuevas,
    comisiones
):

    if ventas_nuevas.empty:

        return pd.DataFrame(
            columns=comisiones.columns
        )

    nuevos = pd.DataFrame(

        index=ventas_nuevas.index,

        columns=comisiones.columns,

        dtype=object,

    )

    campos = [

        "afiliado",

        "terminal",

        "concatenar",

        "serial",

        "equipo",

        "canal",

        "vendedor_agente",

        "estatus",

    ]

    for tipo in campos:

        destino = buscar_columna(
            comisiones,
            tipo
        )

        origen = buscar_columna(
            ventas_nuevas,
            tipo
        )

        if (
            destino
            and origen
        ):

            nuevos[
                destino
            ] = ventas_nuevas[
                origen
            ].values

    nuevos[
        "__ORIGEN"
    ] = (
        "VENTAS_NUEVAS"
    )

    nuevos[
        "__AFILIADO"
    ] = ventas_nuevas[
        "__AFILIADO"
    ].values

    nuevos[
        "__TERMINAL"
    ] = ventas_nuevas[
        "__TERMINAL"
    ].values

    nuevos[
        "__CONCATENAR"
    ] = ventas_nuevas[
        "__CONCATENAR"
    ].values

    nuevos[
        "__EQUIPO_STD"
    ] = ventas_nuevas[
        "__EQUIPO_STD"
    ].values

    col_serial = buscar_columna(
        ventas_nuevas,
        "serial"
    )

    if col_serial:

        nuevos[
            "__SERIAL_COMISION"
        ] = ventas_nuevas[
            col_serial
        ].map(
            normalizar_identificador
        ).values

    else:

        nuevos[
            "__SERIAL_COMISION"
        ] = ""

    col_estatus = buscar_columna(
        comisiones,
        "estatus"
    )

    if col_estatus:

        nuevos[
            col_estatus
        ] = "Pendiente"

    return nuevos


# =========================================================
# AGREGAR SOLO VENTAS NUEVAS
# =========================================================

def integrar_ventas(
    comisiones,
    ventas
):

    if ventas.empty:

        return (

            comisiones.copy(),

            pd.DataFrame(),

            pd.DataFrame(),

        )

    claves_existentes = set(

        comisiones.loc[

            comisiones[
                "__CONCATENAR"
            ].ne(
                ""
            ),

            "__CONCATENAR",

        ].astype(
            str
        )

    )

    mascara_nueva = (

        ventas[
            "__CONCATENAR"
        ].ne(
            ""
        )

        & ~ventas[
            "__CONCATENAR"
        ].isin(
            claves_existentes
        )

    )

    ventas_nuevas = ventas[

        mascara_nueva

    ].copy()

    ventas_ya_existentes = ventas[

        ~mascara_nueva

    ].copy()

    nuevos = copiar_ventas_a_plantilla(

        ventas_nuevas,

        comisiones,

    )

    combinado = pd.concat(

        [
            comisiones,
            nuevos,
        ],

        ignore_index=True,

        sort=False,

    )

    combinado[
        "__ROW_ID"
    ] = range(
        1,
        len(combinado) + 1
    )

    return (

        combinado,

        ventas_nuevas,

        ventas_ya_existentes,

    )


# =========================================================
# ACCESS COMMERCE
# =========================================================

def preparar_access(
    archivo_access
):

    df = leer_excel(
        archivo_access
    )

    col_afiliado = buscar_columna(
        df,
        "afiliado"
    )

    if col_afiliado is None:

        raise ValueError(

            "No encontré una columna "
            "de AFILIADO/AFILIACIÓN "
            "en Access Commerce."

        )

    df[
        "__AFILIADO"
    ] = df[
        col_afiliado
    ].map(
        normalizar_identificador
    )

    afiliados = set(

        df.loc[

            df[
                "__AFILIADO"
            ].ne(
                ""
            ),

            "__AFILIADO",

        ].astype(
            str
        )

    )

    return (
        df,
        afiliados,
    )


# =========================================================
# CREAR LOOKUP DEL R34
# =========================================================

def crear_lookup_r34(
    r34
):

    if r34.empty:
        return {}

    lookup = {}

    for _, row in r34.iterrows():

        clave = row.get(
            "__CONCATENAR",
            ""
        )

        if not clave:
            continue

        monto = row.get(
            "__MONTO_TX"
        )

        actual = lookup.get(
            clave
        )

        if actual is None:

            lookup[
                clave
            ] = row.to_dict()

            continue

        monto_actual = actual.get(
            "__MONTO_TX"
        )

        # Si existen varias filas,
        # conservamos la de mayor monto.

        if (
            monto is not None
            and not pd.isna(
                monto
            )
        ):

            if (
                monto_actual is None
                or pd.isna(
                    monto_actual
                )
                or float(
                    monto
                )
                >
                float(
                    monto_actual
                )
            ):

                lookup[
                    clave
                ] = row.to_dict()

    return lookup


# =========================================================
# ESTADO TRANSACCIÓN
# =========================================================

def estado_transaccion(
    monto
):

    if (
        monto is None
        or pd.isna(
            monto
        )
    ):

        return "N/A"

    monto = float(
        monto
    )

    # Según la regla documentada:
    # +1.000 = CON_TX

    if monto > 1000:

        return "CON_TX"

    # 0.01 hasta 999.99

    if (
        0.01
        <= monto
        <= 999.99
    ):

        return "C/P SIN TX"

    # 0

    if monto == 0:

        return "SIN TX"

    # 1000 exactos no está definido
    # claramente en la guía.
    # Lo mandamos a revisar,
    # no inventamos una regla.

    if monto == 1000:

        return "REVISAR 1000"

    return "REVISAR"


# =========================================================
# RECALCULAR CRUCES Y VALIDACIONES
# =========================================================

def recalcular_comisiones(
    df,
    r34,
    afiliados_access,
):

    resultado = df.copy()

    lookup = crear_lookup_r34(
        r34
    )

    # =====================================================
    # COLUMNAS DEL ARCHIVO DE COMISIONES
    # =====================================================

    col_afiliado = buscar_columna(
        resultado,
        "afiliado"
    )

    col_terminal = buscar_columna(
        resultado,
        "terminal"
    )

    col_serial = buscar_columna(
        resultado,
        "serial"
    )

    col_equipo = buscar_columna(
        resultado,
        "equipo"
    )

    col_estatus = buscar_columna(
        resultado,
        "estatus"
    )

    col_access_original = buscar_columna(
        resultado,
        "access"
    )

    col_con_tx_original = buscar_columna(
        resultado,
        "con_tx"
    )

    # =====================================================
    # REFRESCAR INFORMACIÓN INTERNA
    # =====================================================

    if col_afiliado:

        resultado[
            "__AFILIADO"
        ] = resultado[
            col_afiliado
        ].map(
            normalizar_identificador
        )

    if col_terminal:

        resultado[
            "__TERMINAL"
        ] = resultado[
            col_terminal
        ].map(
            normalizar_identificador
        )

    if col_serial:

        resultado[
            "__SERIAL_COMISION"
        ] = resultado[
            col_serial
        ].map(
            normalizar_identificador
        )

    if col_equipo:

        resultado[
            "__EQUIPO_STD"
        ] = resultado[
            col_equipo
        ].map(
            estandarizar_equipo
        )

    resultado[
        "__CONCATENAR"
    ] = [

        crear_concatenar(
            afiliado,
            terminal
        )

        for afiliado, terminal
        in zip(

            resultado[
                "__AFILIADO"
            ],

            resultado[
                "__TERMINAL"
            ],

        )

    ]

    # =====================================================
    # DUPLICADOS
    # =====================================================

    duplicados = (

        resultado[
            "__CONCATENAR"
        ].ne(
            ""
        )

        & resultado.duplicated(
            "__CONCATENAR",
            keep=False
        )

    )

    lista_monto = []

    lista_serial_r34 = []

    lista_serial_terminal = []

    lista_coincide = []

    lista_tx = []

    lista_access = []

    lista_aplica_pago = []

    lista_motivos = []

    # =====================================================
    # REVISAR FILA POR FILA
    # =====================================================

    for idx, row in resultado.iterrows():

        clave = row.get(
            "__CONCATENAR",
            ""
        )

        equipo = estandarizar_equipo(

            row.get(
                "__EQUIPO_STD",
                ""
            )

        )

        serial_comision = (
            normalizar_identificador(

                row.get(
                    "__SERIAL_COMISION",
                    ""
                )

            )
        )

        registro_r34 = lookup.get(
            clave
        )

        razones = []

        # =================================================
        # DUPLICADO
        # =================================================

        if duplicados.loc[
            idx
        ]:

            razones.append(
                "Duplicado afiliado+terminal"
            )

        # =================================================
        # FALTA CLAVE
        # =================================================

        if not clave:

            razones.append(
                "Falta afiliado o terminal"
            )

        # =================================================
        # N/A y N/D
        # =================================================

        if serial_comision in {
            "N/A",
            "N/D",
            "NA",
            "ND",
        }:

            razones.append(

                f"Serial "
                f"{serial_comision} "
                f"requiere revisión AS400"

            )

        # =================================================
        # CRUCE R34
        # =================================================

        if registro_r34 is None:

            monto = None

            serial_r34 = ""

            serial_terminal = ""

            coincide = (
                "SIN COINCIDENCIA R34"
            )

            razones.append(
                "No encontrado en R34"
            )

        else:

            monto = registro_r34.get(
                "__MONTO_TX"
            )

            serial_r34 = (
                normalizar_identificador(

                    registro_r34.get(
                        "__SERIAL",
                        ""
                    )

                )
            )

            serial_terminal = (
                normalizar_identificador(

                    registro_r34.get(
                        "__SERIAL_DESDE_TERMINAL",
                        ""
                    )

                )
            )

            # =============================================
            # PINPAGOS
            # =============================================

            if equipo == "Pinpagos":

                serial_referencia = (

                    serial_terminal
                    or
                    serial_r34

                )

            else:

                serial_referencia = (
                    serial_r34
                )

            if (
                not serial_comision
                or serial_comision
                in {
                    "N/A",
                    "N/D",
                    "NA",
                    "ND",
                }
            ):

                coincide = "REVISAR"

            elif (
                serial_referencia
                and serial_comision
                == serial_referencia
            ):

                coincide = "SI"

            elif serial_referencia:

                coincide = "NO"

                razones.append(
                    "Serial no coincide con R34"
                )

            else:

                coincide = (
                    "SIN SERIAL R34"
                )

                razones.append(
                    "R34 sin serial utilizable"
                )

        # =================================================
        # TRANSACCIONES
        # =================================================

        tx = estado_transaccion(
            monto
        )

        if tx in {
            "N/A",
            "REVISAR",
            "REVISAR 1000",
        }:

            razones.append(
                f"Estado de transacción: {tx}"
            )

        # =================================================
        # ACCESS COMMERCE
        # =================================================

        if equipo == "Pinpagos":

            # ***************
            # REGLA ESPECIAL CONFIRMADA:
            #
            # PINPAGOS NO TIENE ACCESS COMMERCE.
            #
            # Si está CON_TX, puede aplicar pago.
            # ***************

            access = "NO APLICA"

            paga = (
                tx == "CON_TX"
            )

        else:

            if (
                row.get(
                    "__AFILIADO",
                    ""
                )
                in afiliados_access
            ):

                access = "SI"

            else:

                access = "NO"

            paga = (

                tx == "CON_TX"

                and access == "SI"

            )

        lista_monto.append(
            monto
        )

        lista_serial_r34.append(
            serial_r34
        )

        lista_serial_terminal.append(
            serial_terminal
        )

        lista_coincide.append(
            coincide
        )

        lista_tx.append(
            tx
        )

        lista_access.append(
            access
        )

        if paga:

            lista_aplica_pago.append(
                "SI"
            )

        else:

            lista_aplica_pago.append(
                "NO"
            )

        lista_motivos.append(

            " | ".join(

                dict.fromkeys(
                    razones
                )

            )

        )

    # =====================================================
    # RESULTADOS
    # =====================================================

    resultado[
        "Monto_TX_R34"
    ] = lista_monto

    resultado[
        "Serial_R34"
    ] = lista_serial_r34

    resultado[
        "Serial_Terminal_R34"
    ] = lista_serial_terminal

    resultado[
        "Coincide_Serial_R34"
    ] = lista_coincide

    resultado[
        "Estado_TX"
    ] = lista_tx

    resultado[
        "Access_Commerce"
    ] = lista_access

    resultado[
        "Aplica_Pago_Calculado"
    ] = lista_aplica_pago

    resultado[
        "Fecha_Pago_Viernes"
    ] = [

        viernes_semana_actual()
        if aplica == "SI"
        else None

        for aplica
        in lista_aplica_pago

    ]

    resultado[
        "Motivo_Revision"
    ] = lista_motivos

    resultado[
        "__REQUIERE_REVISION"
    ] = (

        resultado[
            "Motivo_Revision"
        ]
        .astype(
            str
        )
        .str.len()
        > 0

    )

    # =====================================================
    # ACTUALIZAR COLUMNAS ORIGINALES
    # =====================================================

    if col_con_tx_original:

        resultado[
            col_con_tx_original
        ] = resultado[
            "Estado_TX"
        ]

    if col_access_original:

        resultado[
            col_access_original
        ] = resultado[
            "Access_Commerce"
        ]

    # =====================================================
    # CAMBIAR ESTATUS A APLICA PAGO
    # =====================================================

    if col_estatus:

        mascara_paga = (

            resultado[
                "Aplica_Pago_Calculado"
            ]
            == "SI"

        )

        resultado.loc[

            mascara_paga,

            col_estatus

        ] = "Aplica Pago"

    return resultado


# =========================================================
# PROCESO GENERAL
# =========================================================

def procesar_todo(

    archivos_r34,

    archivos_ventas,

    archivo_comisiones,

    archivo_access,

    chunksize=100_000,

):

    # =====================================================
    # R34
    # =====================================================

    (
        r34,
        detalle_r34,
        avisos_r34,
    ) = procesar_r34(

        archivos_r34,

        chunksize,

    )

    # =====================================================
    # VENTAS
    # =====================================================

    (
        ventas,
        ventas_excluidas,
        ventas_duplicadas,
        avisos_ventas,
    ) = preparar_ventas(

        archivos_ventas

    )

    # =====================================================
    # COMISIONES
    # =====================================================

    comisiones = preparar_comisiones(
        archivo_comisiones
    )

    # =====================================================
    # ACCESS
    # =====================================================

    (
        access_df,
        afiliados_access,
    ) = preparar_access(
        archivo_access
    )

    # =====================================================
    # VENTAS NUEVAS
    # =====================================================

    (
        combinado,
        ventas_nuevas,
        ventas_ya_existentes,
    ) = integrar_ventas(

        comisiones,

        ventas,

    )

    # =====================================================
    # R34 + ACCESS + VALIDACIONES
    # =====================================================

    final = recalcular_comisiones(

        combinado,

        r34,

        afiliados_access,

    )

    return {

        "final":
            final,

        "r34":
            r34,

        "detalle_r34":
            detalle_r34,

        "access_df":
            access_df,

        "afiliados_access":
            afiliados_access,

        "ventas_limpias":
            ventas,

        "ventas_nuevas":
            ventas_nuevas,

        "ventas_ya_existentes":
            ventas_ya_existentes,

        "ventas_excluidas":
            ventas_excluidas,

        "ventas_duplicadas":
            ventas_duplicadas,

        "advertencias":
            avisos_r34
            +
            avisos_ventas,

    }


# =========================================================
# QUITAR COLUMNAS INTERNAS
# =========================================================

def limpiar_columnas_internas(
    df
):

    if df is None:

        return pd.DataFrame()

    if df.empty:

        return df.copy()

    columnas = [

        col

        for col in df.columns

        if not str(
            col
        ).startswith(
            "__"
        )

    ]

    return df[
        columnas
    ].copy()


# =========================================================
# GENERAR EXCEL FINAL
# =========================================================

def generar_excel_resultado(
    resultados
):

    salida = io.BytesIO()

    final = limpiar_columnas_internas(

        resultados[
            "final"
        ]

    )

    revision = limpiar_columnas_internas(

        resultados[
            "final"
        ][

            resultados[
                "final"
            ][
                "__REQUIERE_REVISION"
            ]

        ].copy()

    )

    with pd.ExcelWriter(

        salida,

        engine="openpyxl",

    ) as writer:

        final.to_excel(

            writer,

            sheet_name=
                "Comisiones_Procesadas",

            index=False,

        )

        revision.to_excel(

            writer,

            sheet_name=
                "Revision_Manual",

            index=False,

        )

        limpiar_columnas_internas(

            resultados[
                "ventas_nuevas"
            ]

        ).to_excel(

            writer,

            sheet_name=
                "Ventas_Nuevas",

            index=False,

        )

        limpiar_columnas_internas(

            resultados[
                "ventas_ya_existentes"
            ]

        ).to_excel(

            writer,

            sheet_name=
                "Ventas_Ya_Existentes",

            index=False,

        )

        limpiar_columnas_internas(

            resultados[
                "ventas_excluidas"
            ]

        ).to_excel(

            writer,

            sheet_name=
                "Ventas_Excluidas",

            index=False,

        )

        limpiar_columnas_internas(

            resultados[
                "ventas_duplicadas"
            ]

        ).to_excel(

            writer,

            sheet_name=
                "Duplicados_Ventas",

            index=False,

        )

    salida.seek(
        0
    )

    return salida.getvalue()