import re
import unicodedata


# =========================================================
# PRECIOS BASE DE LOS EQUIPOS
# =========================================================

PRECIOS_BASE = {
    "Castle Dynamo": 240.0,
    "Zappy S1MINI2": 225.0,
    "Pinpagos": 104.0,
}


# =========================================================
# NORMALIZACIÓN
# =========================================================

def _normalizar_texto(valor):

    if valor is None:
        return ""

    texto = str(valor).strip()

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
# EQUIPOS
# =========================================================

def estandarizar_equipo(valor):

    texto = _normalizar_texto(valor)

    if not texto:
        return ""

    # PINPAGOS
    if (
        "PINPAGO" in texto
        or "PIN PAGO" in texto
        or "EQUIPO K" in texto
    ):
        return "Pinpagos"

    # ZAPPY
    if (
        "ZAPPY" in texto
        or "SAPPY" in texto
        or "S1MINI2" in texto
        or "S1 MINI 2" in texto
    ):
        return "Zappy S1MINI2"

    # CASTLE
    if (
        "CASTLE" in texto
        or "CASTTLE" in texto
        or "DYNAMO" in texto
    ):
        return "Castle Dynamo"

    # Si todavía no reconocemos el nombre,
    # conservamos el original para poder revisarlo.

    return str(valor).strip()


# =========================================================
# PRECIO DEL EQUIPO
# =========================================================

def precio_equipo(
    equipo,
    precios=None
):

    precios = precios or PRECIOS_BASE

    equipo = estandarizar_equipo(
        equipo
    )

    return float(
        precios.get(
            equipo,
            0.0
        )
    )


# =========================================================
# 16% DEL EQUIPO
# =========================================================

def comision_16_por_ciento(
    equipo,
    precios=None
):

    precio = precio_equipo(
        equipo,
        precios
    )

    return round(
        precio * 0.16,
        2
    )


# =========================================================
# ACCESS COMMERCE
# =========================================================

def requiere_access_commerce(equipo):

    """
    Regla especial:

    Pinpagos NO trabaja con Access Commerce.

    Por lo tanto:
    - Pinpagos solamente depende de CON_TX.
    - Castle Dynamo y Zappy S1MINI2 sí deben
      revisarse contra Access Commerce.
    """

    equipo = estandarizar_equipo(
        equipo
    )

    return equipo != "Pinpagos"