import re
import unicodedata


PRECIOS_BASE = {
    "Castle Dynamo": 240.0,
    "Zappy S1MINI2": 225.0,
    "Pinpagos": 104.0,
}


def normalizar_texto(valor):
    if valor is None:
        return ""

    texto = str(valor).strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    texto = re.sub(r"\s+", " ", texto)
    return texto.upper()


def estandarizar_equipo(valor):
    texto = normalizar_texto(valor)

    if not texto:
        return ""

    if (
        "PINPAGO" in texto
        or "PIN PAGO" in texto
        or "EQUIPO K" in texto
    ):
        return "Pinpagos"

    if (
        "ZAPPY" in texto
        or "SAPPY" in texto
        or "S1MINI2" in texto
        or "S1 MINI 2" in texto
    ):
        return "Zappy S1MINI2"

    if (
        "CASTLE" in texto
        or "CASTTLE" in texto
        or "DYNAMO" in texto
    ):
        return "Castle Dynamo"

    return str(valor).strip()


def obtener_precio_equipo(equipo, precios=None):
    if precios is None:
        precios = PRECIOS_BASE

    equipo = estandarizar_equipo(equipo)
    return float(precios.get(equipo, 0.0))


def calcular_16_por_ciento(equipo, precios=None):
    precio = obtener_precio_equipo(
        equipo,
        precios
    )

    return round(
        precio * 0.16,
        2
    )


def requiere_access_commerce(equipo):
    """
    Regla confirmada:
    Pinpagos NO utiliza Access Commerce.
    Castle Dynamo y Zappy S1MINI2 sí.
    """
    equipo = estandarizar_equipo(equipo)
    return equipo != "Pinpagos"

