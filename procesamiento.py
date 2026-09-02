import csv
import io
import re
import unicodedata
import zipfile

from copy import copy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from openpyxl import load_workbook
from reglas_comisiones import estandarizar_equipo

ALIASES = {
    "pertenencia": ["PERTENENCIA"],
    "afipos": ["AFIPOS", "AFI POS", "AFI_POS"],
    "afiliado": ["AFILIADO", "AFILIACION", "AFILIACIÓN", "COD AFILIADO", "CODIGO AFILIADO", "CÓDIGO AFILIADO", "NRO AFILIADO", "NUMERO AFILIADO"],
    "terminal": ["TERMINAL", "NRO TERMINAL", "NUMERO TERMINAL", "NÚMERO TERMINAL"],
    "serial": ["SERIAL", "SERIALES", "SERIAL EQUIPO", "SERIAL_EQUIPO"],
    "monto_tx": ["MONTO_TRANS_ACUM_MES", "MONTO TRANS ACUM MES", "MONTO_TRANSACCION_BS_ACUM_MES", "MONTO TRANSACCION BS ACUM MES", "MONTO_TRANS_BS_ACUM_MES", "MONTO TX", "MONTO_TX"],
    "concatenar": ["CONCATENAR", "CONCATENADO", "AFILIADO TERMINAL", "AFILIADO+TERMINAL"],
    "equipo": ["EQUIPO", "MODELO", "TIPO EQUIPO", "MODELO EQUIPO", "PRODUCTO"],
    "estatus": ["ESTATUS", "STATUS", "ESTADO", "PENDIENTE"],
    "canal": ["CANAL", "CANAL DE VENTAS", "CANAL DE VENTA", "CANAL DE VENTAS (JORNADA QUE PERTENECE)"],
    "vendedor": ["VENDEDOR", "VENDEDOR AGENTE AUTORIZADOS", "VENDEDOR AGENTE AUTORIZADO", "VENDEDOR/AGENTE AUTORIZADO"],
    "preafiliado": ["PRE AFILIADO", "PRE-AFILIADO", "PREAFILIADO", "PRE AFILIACION"],
    "ag_autorizado": ["AG AUTORIZADO", "AGENTE AUTORIZADO?", "ES AGENTE AUTORIZADO"],
    "access": ["ACCESS COMMERCE", "ACCESS COMERCE", "ACCESS"],
    "con_tx": ["CON TX", "CON_TX", "ESTADO TX", "ESTATUS TX"],
}

def normalizar_texto(valor):
    if valor is None:
        return ""
    if isinstance(valor, float) and pd.isna(valor):
        return ""
    texto = str(valor).strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\s+", " ", texto)
    return texto.upper()

def normalizar_nombre_columna(nombre):
    texto = normalizar_texto(nombre)
    texto = re.sub(r"[^A-Z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()

def buscar_columna(df, tipo):
    if df is None:
        return None
    aliases = {normalizar_nombre_columna(x) for x in ALIASES.get(tipo, [])}
    columnas = {col: normalizar_nombre_columna(col) for col in df.columns}
    for col, normalizada in columnas.items():
        if normalizada in aliases:
            return col
    for col, normalizada in columnas.items():
        for alias in aliases:
            if alias and (alias in normalizada or normalizada in alias):
                return col
    return None

def normalizar_identificador(valor):
    if valor is None or pd.isna(valor):
        return ""
    texto = str(valor).strip()
    if texto.upper() in {"N/A", "N/D", "NA", "ND", "NAN", "NONE", "-"}:
        return texto.upper()
    if re.fullmatch(r"\d+\.0+", texto):
        texto = texto.split(".")[0]
    texto = re.sub(r"\s+", "", texto)
    return texto

def normalizar_numero(valor):
    if valor is None or pd.isna(valor):
        return None
    texto = str(valor).strip()
    if texto == "" or texto.upper() in {"N/A", "N/D", "NA", "ND", "NAN", "-"}:
        return None
    texto = re.sub(r"[^0-9,\.\-]", "", texto)
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None

def crear_concatenar(afiliado, terminal):
    afiliado = normalizar_identificador(afiliado)
    terminal = normalizar_identificador(terminal)
    if not afiliado or not terminal:
        return ""
    return f"{afiliado}|{terminal}"

def valor_es_si(valor):
    return normalizar_texto(valor) in {"SI", "SÍ", "YES", "Y", "1", "TRUE", "X"}

def viernes_semana_actual():
    hoy = datetime.now(ZoneInfo("America/Caracas")).date()
    return hoy + timedelta(days=(4 - hoy.weekday()))

def leer_excel_general(archivo):
    archivo.seek(0)
    return pd.read_excel(archivo, dtype=str, engine="openpyxl")

def leer_excel_comisiones(archivo):
    archivo.seek(0)
    try:
        df = pd.read_excel(archivo, sheet_name="VENTAS", dtype=str, engine="openpyxl")
    except ValueError:
        raise ValueError("No encontré la hoja 'VENTAS' en el archivo de Comisiones.")
    df.attrs["hoja_origen"] = "VENTAS"
    return df

def detectar_csv(stream):
    posicion = stream.tell()
    muestra = stream.read(65536)
    stream.seek(posicion)
    encoding = "utf-8-sig"
    try:
        texto = muestra.decode(encoding)
    except UnicodeDecodeError:
        encoding = "latin-1"
        texto = muestra.decode(encoding, errors="replace")
    try:
        dialecto = csv.Sniffer().sniff(texto, delimiters=[",", ";", "\t", "|"])
        separador = dialecto.delimiter
    except csv.Error:
        separador = ";" if texto.count(";") > texto.count(",") else ","
    return encoding, separador

def extraer_serial_terminal(valor):
    texto = normalizar_identificador(valor)
    if not texto:
        return ""
    match = re.search(r"\d{5,}", texto)
    if match:
        return match.group(0)
    return re.split(r"[\s/|\\;,_-]+", texto)[0]

def procesar_csv_r34(stream, nombre, chunksize=100_000):
    stream.seek(0)
    encoding, separador = detectar_csv(stream)
    stream.seek(0)
    partes = []
    filas_leidas = 0
    filas_credicardpos = 0
    columnas_detectadas = None

    lector = pd.read_csv(
        stream,
        sep=separador,
        encoding=encoding,
        dtype=str,
        chunksize=chunksize,
        on_bad_lines="skip",
        low_memory=False,
    )

    for chunk in lector:
        filas_leidas += len(chunk)
        if columnas_detectadas is None:
            columnas_detectadas = {
                "pertenencia": buscar_columna(chunk, "pertenencia"),
                "afiliado": buscar_columna(chunk, "afiliado"),
                "terminal": buscar_columna(chunk, "terminal"),
                "serial": buscar_columna(chunk, "serial"),
                "monto_tx": buscar_columna(chunk, "monto_tx"),
                "afipos": buscar_columna(chunk, "afipos"),
            }
            if columnas_detectadas["pertenencia"] is None:
                raise ValueError(f"No se encontró PERTENENCIA en {nombre}.")

        col_pertenencia = columnas_detectadas["pertenencia"]
        mascara = chunk[col_pertenencia].map(normalizar_texto).eq("CREDICARDPOS")
        filtrado = chunk.loc[mascara].copy()
        filas_credicardpos += len(filtrado)

        if filtrado.empty:
            continue

        col_afiliado = columnas_detectadas["afiliado"]
        col_terminal = columnas_detectadas["terminal"]
        col_serial = columnas_detectadas["serial"]
        col_monto = columnas_detectadas["monto_tx"]

        filtrado["__AFILIADO"] = filtrado[col_afiliado].map(normalizar_identificador) if col_afiliado else ""
        filtrado["__TERMINAL"] = filtrado[col_terminal].map(normalizar_identificador) if col_terminal else ""
        filtrado["__SERIAL"] = filtrado[col_serial].map(normalizar_identificador) if col_serial else ""
        filtrado["__MONTO_TX"] = filtrado[col_monto].map(normalizar_numero) if col_monto else None
        filtrado["__SERIAL_TERMINAL"] = filtrado["__TERMINAL"].map(extraer_serial_terminal)
        filtrado["__CONCATENAR"] = [
            crear_concatenar(afi, ter)
            for afi, ter in zip(filtrado["__AFILIADO"], filtrado["__TERMINAL"])
        ]

        partes.append(
            filtrado[
                ["__AFILIADO", "__TERMINAL", "__SERIAL", "__SERIAL_TERMINAL", "__MONTO_TX", "__CONCATENAR"]
            ]
        )

    resultado = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(
        columns=["__AFILIADO", "__TERMINAL", "__SERIAL", "__SERIAL_TERMINAL", "__MONTO_TX", "__CONCATENAR"]
    )

    detalle = {
        "archivo": nombre,
        "filas_leidas": filas_leidas,
        "filas_credicardpos": filas_credicardpos,
    }
    return resultado, detalle

def procesar_r34(archivos_r34, chunksize=100_000):
    partes = []
    detalles = []
    for archivo in archivos_r34:
        archivo.seek(0)
        nombre = archivo.name.lower()

        if nombre.endswith(".zip"):
            datos = archivo.getvalue()
            with zipfile.ZipFile(io.BytesIO(datos)) as zf:
                csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                if not csvs:
                    raise ValueError(f"{archivo.name} no contiene ningún CSV.")
                for csv_interno in csvs:
                    with zf.open(csv_interno, "r") as stream:
                        df, detalle = procesar_csv_r34(
                            stream,
                            f"{archivo.name}::{csv_interno}",
                            chunksize
                        )
                        partes.append(df)
                        detalles.append(detalle)

        elif nombre.endswith(".csv"):
            df, detalle = procesar_csv_r34(archivo, archivo.name, chunksize)
            partes.append(df)
            detalles.append(detalle)

        else:
            raise ValueError(f"Formato no soportado para R34: {archivo.name}")

    r34 = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
    return r34, detalles

def preparar_comisiones(archivo_comisiones):
    df = leer_excel_comisiones(archivo_comisiones)
    df = df.dropna(how="all").copy()
    df["__ORIGEN"] = "COMISIONES"

    col_afiliado = buscar_columna(df, "afiliado")
    col_terminal = buscar_columna(df, "terminal")
    col_serial = buscar_columna(df, "serial")
    col_equipo = buscar_columna(df, "equipo")

    if col_afiliado is None:
        raise ValueError("En la hoja VENTAS no encontré la columna AFILIADO.")
    if col_terminal is None:
        raise ValueError("En la hoja VENTAS no encontré la columna TERMINAL.")

    df["__AFILIADO"] = df[col_afiliado].map(normalizar_identificador)
    df["__TERMINAL"] = df[col_terminal].map(normalizar_identificador)
    df["__SERIAL_COMISION"] = df[col_serial].map(normalizar_identificador) if col_serial else ""
    df["__EQUIPO_STD"] = df[col_equipo].map(estandarizar_equipo) if col_equipo else ""
    df["__CONCATENAR"] = [
        crear_concatenar(afi, ter)
        for afi, ter in zip(df["__AFILIADO"], df["__TERMINAL"])
    ]
    df["__ROW_ID"] = range(1, len(df) + 1)
    return df

def preparar_ventas(archivos_ventas):
    partes = []
    excluidas = []
    advertencias = []

    for archivo in archivos_ventas:
        df = leer_excel_general(archivo)
        df = df.dropna(how="all").copy()
        df["__ARCHIVO_ORIGEN"] = archivo.name

        col_afiliado = buscar_columna(df, "afiliado")
        col_terminal = buscar_columna(df, "terminal")
        col_equipo = buscar_columna(df, "equipo")
        col_pre = buscar_columna(df, "preafiliado")
        col_ag = buscar_columna(df, "ag_autorizado")

        if col_afiliado is None:
            raise ValueError(f"No encontré AFILIADO en {archivo.name}.")
        if col_terminal is None:
            raise ValueError(f"No encontré TERMINAL en {archivo.name}.")

        df["__AFILIADO"] = df[col_afiliado].map(normalizar_identificador)
        df["__TERMINAL"] = df[col_terminal].map(normalizar_identificador)
        df["__CONCATENAR"] = [
            crear_concatenar(afi, ter)
            for afi, ter in zip(df["__AFILIADO"], df["__TERMINAL"])
        ]
        df["__EQUIPO_STD"] = df[col_equipo].map(estandarizar_equipo) if col_equipo else ""
        df["__MOTIVO_EXCLUSION"] = ""

        mascara_terminal_0 = df["__TERMINAL"].isin({"0", "0.0"})
        df.loc[mascara_terminal_0, "__MOTIVO_EXCLUSION"] = "Terminal = 0 / No Simcard"

        if col_pre:
            mascara_pre = df[col_pre].map(
                lambda x: valor_es_si(x) or "PRE" in normalizar_texto(x)
            )
            df.loc[
                mascara_pre & df["__MOTIVO_EXCLUSION"].eq(""),
                "__MOTIVO_EXCLUSION"
            ] = "Pre-afiliado"

        if col_ag:
            mascara_ag = df[col_ag].map(valor_es_si)
            df.loc[
                mascara_ag & df["__MOTIVO_EXCLUSION"].eq(""),
                "__MOTIVO_EXCLUSION"
            ] = "AG Autorizado"
        else:
            advertencias.append(
                f"{archivo.name}: no encontré una columna explícita para identificar AG Autorizados."
            )

        excluidas.append(df[df["__MOTIVO_EXCLUSION"].ne("")].copy())
        partes.append(df[df["__MOTIVO_EXCLUSION"].eq("")].copy())

    ventas = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
    ventas_excluidas = pd.concat(excluidas, ignore_index=True) if excluidas else pd.DataFrame()

    if not ventas.empty:
        mascara_dup = ventas["__CONCATENAR"].ne("") & ventas.duplicated("__CONCATENAR", keep="first")
        duplicadas = ventas[mascara_dup].copy()
        ventas = ventas[~mascara_dup].copy()
    else:
        duplicadas = pd.DataFrame()

    return ventas, ventas_excluidas, duplicadas, advertencias

def crear_filas_nuevas(ventas_nuevas, comisiones):
    if ventas_nuevas.empty:
        return pd.DataFrame(columns=comisiones.columns)

    nuevas = pd.DataFrame(
        index=range(len(ventas_nuevas)),
        columns=comisiones.columns,
        dtype=object
    )

    for columna_destino in comisiones.columns:
        if str(columna_destino).startswith("__"):
            continue
        destino_normalizado = normalizar_nombre_columna(columna_destino)

        for columna_origen in ventas_nuevas.columns:
            if str(columna_origen).startswith("__"):
                continue
            origen_normalizado = normalizar_nombre_columna(columna_origen)
            if destino_normalizado == origen_normalizado:
                nuevas[columna_destino] = ventas_nuevas[columna_origen].values
                break

    tipos = ["afiliado", "terminal", "serial", "equipo", "canal", "vendedor"]

    for tipo in tipos:
        destino = buscar_columna(comisiones, tipo)
        origen = buscar_columna(ventas_nuevas, tipo)
        if destino and origen:
            nuevas[destino] = ventas_nuevas[origen].values

    col_estatus = buscar_columna(comisiones, "estatus")
    if col_estatus:
        nuevas[col_estatus] = "Pendiente"

    nuevas["__ORIGEN"] = "VENTAS_NUEVAS"
    nuevas["__AFILIADO"] = ventas_nuevas["__AFILIADO"].values
    nuevas["__TERMINAL"] = ventas_nuevas["__TERMINAL"].values
    nuevas["__CONCATENAR"] = ventas_nuevas["__CONCATENAR"].values
    nuevas["__EQUIPO_STD"] = ventas_nuevas["__EQUIPO_STD"].values

    col_serial_ventas = buscar_columna(ventas_nuevas, "serial")
    nuevas["__SERIAL_COMISION"] = (
        ventas_nuevas[col_serial_ventas].map(normalizar_identificador).values
        if col_serial_ventas else ""
    )
    return nuevas

def integrar_ventas(comisiones, ventas):
    claves_existentes = set(
        comisiones.loc[
            comisiones["__CONCATENAR"].ne(""),
            "__CONCATENAR"
        ].astype(str)
    )

    mascara_nueva = (
        ventas["__CONCATENAR"].ne("")
        & ~ventas["__CONCATENAR"].isin(claves_existentes)
    )

    ventas_nuevas = ventas[mascara_nueva].copy()
    ventas_existentes = ventas[~mascara_nueva].copy()
    nuevas_en_formato = crear_filas_nuevas(ventas_nuevas, comisiones)

    resultado = pd.concat(
        [comisiones, nuevas_en_formato],
        ignore_index=True,
        sort=False
    )
    resultado["__ROW_ID"] = range(1, len(resultado) + 1)
    return resultado, ventas_nuevas, ventas_existentes

def preparar_access(archivo_access):
    df = leer_excel_general(archivo_access)
    col_afiliado = buscar_columna(df, "afiliado")

    if col_afiliado is None:
        raise ValueError("No encontré AFILIADO en Access Commerce.")

    df["__AFILIADO"] = df[col_afiliado].map(normalizar_identificador)
    afiliados = set(
        df.loc[df["__AFILIADO"].ne(""), "__AFILIADO"].astype(str)
    )
    return df, afiliados

def crear_lookup_r34(r34):
    lookup = {}
    if r34.empty:
        return lookup

    for _, fila in r34.iterrows():
        clave = fila.get("__CONCATENAR", "")
        if not clave:
            continue

        actual = lookup.get(clave)
        if actual is None:
            lookup[clave] = fila.to_dict()
            continue

        monto_nuevo = fila.get("__MONTO_TX")
        monto_actual = actual.get("__MONTO_TX")

        if monto_nuevo is not None and not pd.isna(monto_nuevo):
            if (
                monto_actual is None
                or pd.isna(monto_actual)
                or float(monto_nuevo) > float(monto_actual)
            ):
                lookup[clave] = fila.to_dict()

    return lookup

def estado_transaccion(monto):
    if monto is None or pd.isna(monto):
        return "N/A"
    monto = float(monto)
    if monto > 1000:
        return "CON_TX"
    if 0.01 <= monto <= 999.99:
        return "C/P SIN TX"
    if monto == 0:
        return "SIN TX"
    if monto == 1000:
        return "REVISAR 1000"
    return "REVISAR"

def recalcular_comisiones(df, r34, afiliados_access):
    resultado = df.copy()
    lookup = crear_lookup_r34(r34)

    col_afiliado = buscar_columna(resultado, "afiliado")
    col_terminal = buscar_columna(resultado, "terminal")
    col_serial = buscar_columna(resultado, "serial")
    col_equipo = buscar_columna(resultado, "equipo")
    col_estatus = buscar_columna(resultado, "estatus")
    col_access = buscar_columna(resultado, "access")
    col_tx = buscar_columna(resultado, "con_tx")

    if col_afiliado:
        resultado["__AFILIADO"] = resultado[col_afiliado].map(normalizar_identificador)
    if col_terminal:
        resultado["__TERMINAL"] = resultado[col_terminal].map(normalizar_identificador)
    if col_serial:
        resultado["__SERIAL_COMISION"] = resultado[col_serial].map(normalizar_identificador)
    if col_equipo:
        resultado["__EQUIPO_STD"] = resultado[col_equipo].map(estandarizar_equipo)

    resultado["__CONCATENAR"] = [
        crear_concatenar(afi, ter)
        for afi, ter in zip(resultado["__AFILIADO"], resultado["__TERMINAL"])
    ]

    duplicado = (
        resultado["__CONCATENAR"].ne("")
        & resultado.duplicated("__CONCATENAR", keep=False)
    )

    montos = []
    seriales_r34 = []
    estados_tx = []
    access_lista = []
    aplica_lista = []
    motivos = []

    for idx, fila in resultado.iterrows():
        clave = fila.get("__CONCATENAR", "")
        equipo = estandarizar_equipo(fila.get("__EQUIPO_STD", ""))
        serial_comision = normalizar_identificador(fila.get("__SERIAL_COMISION", ""))
        razones = []

        if duplicado.loc[idx]:
            razones.append("Duplicado afiliado+terminal")

        registro_r34 = lookup.get(clave)

        if registro_r34 is None:
            monto = None
            serial_r34 = ""
            razones.append("No encontrado en R34")
        else:
            monto = registro_r34.get("__MONTO_TX")
            if equipo == "Pinpagos":
                serial_r34 = (
                    registro_r34.get("__SERIAL_TERMINAL", "")
                    or registro_r34.get("__SERIAL", "")
                )
            else:
                serial_r34 = registro_r34.get("__SERIAL", "")

        serial_r34 = normalizar_identificador(serial_r34)

        if serial_comision in {"N/A", "N/D", "NA", "ND"}:
            razones.append(f"Serial {serial_comision} requiere revisión AS400")
        elif serial_comision and serial_r34 and serial_comision != serial_r34:
            razones.append("Serial no coincide con R34")

        tx = estado_transaccion(monto)

        if equipo == "Pinpagos":
            access = "NO APLICA"
            aplica = tx == "CON_TX"
        else:
            access = "SI" if fila.get("__AFILIADO", "") in afiliados_access else "NO"
            aplica = tx == "CON_TX" and access == "SI"

        if tx in {"N/A", "REVISAR", "REVISAR 1000"}:
            razones.append(f"Estado TX: {tx}")

        montos.append(monto)
        seriales_r34.append(serial_r34)
        estados_tx.append(tx)
        access_lista.append(access)
        aplica_lista.append("SI" if aplica else "NO")
        motivos.append(" | ".join(dict.fromkeys(razones)))

    resultado["Monto_TX_R34"] = montos
    resultado["Serial_R34"] = seriales_r34
    resultado["Estado_TX"] = estados_tx
    resultado["Access_Commerce_Calculado"] = access_lista
    resultado["Aplica_Pago_Calculado"] = aplica_lista
    resultado["Motivo_Revision"] = motivos
    resultado["__REQUIERE_REVISION"] = resultado["Motivo_Revision"].astype(str).str.len() > 0

    if col_tx:
        resultado[col_tx] = resultado["Estado_TX"]
    if col_access:
        resultado[col_access] = resultado["Access_Commerce_Calculado"]
    if col_estatus:
        mascara_pago = resultado["Aplica_Pago_Calculado"] == "SI"
        resultado.loc[mascara_pago, col_estatus] = "Aplica Pago"

    return resultado

def procesar_todo(
    archivos_r34,
    archivos_ventas,
    archivo_comisiones,
    archivo_access,
    chunksize=100_000
):
    archivo_comisiones.seek(0)
    bytes_comisiones = archivo_comisiones.getvalue()

    r34, detalle_r34 = procesar_r34(archivos_r34, chunksize)
    comisiones = preparar_comisiones(archivo_comisiones)
    cantidad_original = len(comisiones)

    ventas, ventas_excluidas, ventas_duplicadas, advertencias = preparar_ventas(archivos_ventas)

    combinado, ventas_nuevas, ventas_existentes = integrar_ventas(
        comisiones,
        ventas
    )

    access_df, afiliados_access = preparar_access(archivo_access)
    final = recalcular_comisiones(combinado, r34, afiliados_access)

    return {
        "final": final,
        "r34": r34,
        "detalle_r34": detalle_r34,
        "ventas_nuevas": ventas_nuevas,
        "ventas_existentes": ventas_existentes,
        "ventas_excluidas": ventas_excluidas,
        "ventas_duplicadas": ventas_duplicadas,
        "advertencias": advertencias,
        "afiliados_access": afiliados_access,
        "cantidad_original": cantidad_original,
        "bytes_comisiones_original": bytes_comisiones,
    }

def columnas_originales(df):
    return [
        col
        for col in df.columns
        if not str(col).startswith("__")
        and col not in {
            "Monto_TX_R34",
            "Serial_R34",
            "Estado_TX",
            "Access_Commerce_Calculado",
            "Aplica_Pago_Calculado",
            "Motivo_Revision",
        }
    ]

def copiar_estilo_fila(ws, fila_origen, fila_destino, max_col):
    for col in range(1, max_col + 1):
        origen = ws.cell(row=fila_origen, column=col)
        destino = ws.cell(row=fila_destino, column=col)

        if origen.has_style:
            destino._style = copy(origen._style)
        if origen.number_format:
            destino.number_format = origen.number_format
        if origen.font:
            destino.font = copy(origen.font)
        if origen.fill:
            destino.fill = copy(origen.fill)
        if origen.border:
            destino.border = copy(origen.border)
        if origen.alignment:
            destino.alignment = copy(origen.alignment)
        if origen.protection:
            destino.protection = copy(origen.protection)

def generar_excel_resultado(resultados):
    datos_originales = resultados["bytes_comisiones_original"]
    wb = load_workbook(io.BytesIO(datos_originales))

    if "VENTAS" not in wb.sheetnames:
        raise ValueError("El archivo original ya no contiene la hoja VENTAS.")

    ws = wb["VENTAS"]
    final = resultados["final"].copy()
    columnas = columnas_originales(final)

    encabezados = {}
    for celda in ws[1]:
        if celda.value is not None:
            encabezados[str(celda.value)] = celda.column

    coincidencias_fila_1 = sum(1 for col in columnas if col in encabezados)
    fila_encabezado = 1

    if coincidencias_fila_1 < 3:
        mejor_fila = 1
        mejor_puntaje = -1

        for fila in range(1, min(ws.max_row, 10) + 1):
            valores = {
                str(ws.cell(row=fila, column=col).value): col
                for col in range(1, ws.max_column + 1)
                if ws.cell(row=fila, column=col).value is not None
            }
            puntaje = sum(1 for columna in columnas if columna in valores)
            if puntaje > mejor_puntaje:
                mejor_puntaje = puntaje
                mejor_fila = fila
                encabezados = valores

        fila_encabezado = mejor_fila

    primera_fila_datos = fila_encabezado + 1
    ultima_fila_existente = ws.max_row

    for fila in range(primera_fila_datos, ultima_fila_existente + 1):
        for col in range(1, ws.max_column + 1):
            ws.cell(row=fila, column=col).value = None

    fila_estilo = primera_fila_datos

    for indice, (_, registro) in enumerate(final.iterrows()):
        fila_excel = primera_fila_datos + indice

        if fila_excel != fila_estilo:
            copiar_estilo_fila(
                ws,
                fila_estilo,
                fila_excel,
                ws.max_column
            )

        for columna in columnas:
            if columna not in encabezados:
                continue

            numero_columna = encabezados[columna]
            valor = registro.get(columna)

            if pd.isna(valor):
                valor = None

            ws.cell(
                row=fila_excel,
                column=numero_columna
            ).value = valor

    salida = io.BytesIO()
    wb.save(salida)
    salida.seek(0)
    return salida.getvalue()

