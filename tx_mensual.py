"""Períodos y diagnósticos TX. No contiene tarifas ni decisiones de pago."""
import re
import math
from datetime import datetime
import pandas as pd

MESES = ('ENERO FEBRERO MARZO ABRIL MAYO JUNIO JULIO AGOSTO SEPTIEMBRE OCTUBRE NOVIEMBRE DICIEMBRE').split()


def periodo(valor):
    if valor is None or pd.isna(valor):
        return None
    if isinstance(valor, (datetime, pd.Timestamp)):
        return valor.year, valor.month
    texto = str(valor).strip().upper()
    for mes, nombre in enumerate(MESES, 1):
        if re.search(r'\b' + nombre + r'\b', texto):
            ano = re.search(r'\b(20\d{2})\b', texto)
            return (int(ano[1]), mes) if ano else None
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:[ T].*)?|\d{1,2}/\d{1,2}/\d{4}', texto):
        fecha = pd.to_datetime(texto, dayfirst=not bool(re.match(r'^\d{4}-', texto)), errors='coerce')
        if not pd.isna(fecha):
            return fecha.year, fecha.month
    return None


def periodo_fila(fila):
    try:
        ano, mes = int(fila.get('__ANO_REPORTE')), int(fila.get('__MES_REPORTE'))
        if 1 <= mes <= 12 and 1 <= ano <= 9999:
            return ano, mes
    except (ValueError, TypeError, OverflowError):
        pass
    return periodo(fila.get('MES DE CIERRE'))


def numero_tx(valor):
    if valor is None or pd.isna(valor) or not str(valor).strip():
        return None, 'MONTO_TX_VACIO'
    texto = str(valor).strip()
    if texto == '-':
        return 0.0, ''
    # No rescatar dígitos de texto corrupto.
    if not re.fullmatch(r'[+-]?\d+(?:[.,]\d+)*', texto):
        return None, 'MONTO_TX_INVALIDO'
    if ',' in texto and '.' in texto:
        decimal, miles = (',', '.') if texto.rfind(',') > texto.rfind('.') else ('.', ',')
        entero, fraccion = texto.rsplit(decimal, 1)
        if not re.fullmatch(r'[+-]?\d{1,3}(?:' + re.escape(miles) + r'\d{3})+', entero):
            return None, 'MONTO_TX_INVALIDO'
        texto = entero.replace(miles, '') + '.' + fraccion
    else:
        texto = texto.replace(',', '.')
    try:
        numero = float(texto)
        return (numero, '') if math.isfinite(numero) else (None, 'MONTO_TX_INVALIDO')
    except ValueError:
        return None, 'MONTO_TX_INVALIDO'


def preparar_periodos_ventas(df, nombre):
    from procesamiento import normalizar_nombre_columna
    columnas = {normalizar_nombre_columna(c): c for c in df.columns}
    fecha = columnas.get('FECHA REPORTE')
    periodos = [periodo(v) for v in df[fecha]] if fecha else [None] * len(df)
    df['__ANO_REPORTE'] = [p[0] if p else None for p in periodos]
    df['__MES_REPORTE'] = [p[1] if p else None for p in periodos]
    historia = []
    for (_, fila), principal in zip(df.iterrows(), periodos):
        montos = {}
        for sufijo in ('', ' 1'):
            col = columnas.get('MONTO TRANS ACUM BS MES' + sufijo)
            if col is None:
                continue
            if principal is None:
                continue
            ano, mes = principal
            if sufijo:
                ano, mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
            montos[(ano, mes)] = numero_tx(fila[col])
        historia.append(montos)
    df['__DIAGNOSTICO_PERIODO'] = ['' if p else 'PERIODO_REPORTE_NO_DISPONIBLE' for p in periodos]
    df['__TX_VENTAS'] = historia
    return df


def unir_historial_ventas(df):
    # Preservar períodos antes de la deduplicación de ventas.
    historias = {}
    filas = sorted((fila for _, fila in df.iterrows()), key=lambda f: periodo_fila(f) or (0, 0))
    for fila in filas:
        destino = historias.setdefault(fila['__CONCATENAR'], {})
        for p, monto in fila['__TX_VENTAS'].items():
            if monto[0] is not None or p not in destino:
                destino[p] = monto
    df['__TX_VENTAS'] = [dict(historias[k]) for k in df['__CONCATENAR']]


def registro_periodo(lookup, fila):
    clave = fila.get('__CONCATENAR', '')
    if any(isinstance(k, tuple) for k in lookup):
        p = periodo_fila(fila)
        return lookup.get((clave, *p)) if p else None
    # Compatibilidad con estructuras internas antiguas sin metadatos de período.
    if periodo_fila(fila):
        return None
    return lookup.get(clave)


def aplicar_historial(df, lookup):
    from procesamiento import normalizar_nombre_columna
    resultado = df.copy()
    resultado.attrs = df.attrs.copy()
    periodos = set()
    por_clave = {}
    for k in lookup:
        if isinstance(k, tuple):
            por_clave.setdefault(k[0], set()).add(k[1:])
    for _, fila in df.iterrows():
        hist = fila.get('__TX_VENTAS')
        if isinstance(hist, dict):
            periodos.update(hist)
        principal = periodo_fila(fila)
        if principal and fila.get('__ORIGEN') == 'VENTAS_NUEVAS':
            periodos.add(principal)
        periodos.update(por_clave.get(fila.get('__CONCATENAR'), set()))
    por_mes = {}
    for ano, mes in periodos:
        por_mes.setdefault(mes, set()).add(ano)
    for _, fila in df.iterrows():
        viejo = periodo(fila.get('MES DE CIERRE'))
        if viejo:
            col = 'MONTO TX ' + MESES[viejo[1]-1]
            if col in df and numero_tx(fila.get(col))[0] is not None and viejo[1] in por_mes:
                por_mes[viejo[1]].add(viejo[0])
    if any(len(anos) > 1 for anos in por_mes.values()):
        raise ValueError('TX: el maestro sin año en los encabezados no permite representar el mismo mes de dos años.')
    nuevas = dict(df.attrs.get('columnas_tx_nuevas', {}))
    originales = dict(df.attrs.get('encabezados_comisiones', {}))
    resultado.attrs.setdefault('columnas_antes_tx', [c for c in df if not str(c).startswith('__')])
    for ano, mes in sorted(periodos):
        nombre = 'MONTO TX ' + MESES[mes - 1]
        candidatas = [c for c in resultado if normalizar_nombre_columna(originales.get(c, c)) == nombre]
        if len(candidatas) > 1:
            raise ValueError('TX: columna mensual duplicada en el maestro.')
        if not candidatas:
            bloque = [(i, MESES.index(str(c)[9:]) + 1) for i, c in enumerate(resultado.columns)
                      if str(c).startswith('MONTO TX ') and str(c)[9:] in MESES]
            descendente = len(bloque) > 1 and bloque[0][1] > bloque[1][1]
            posicion = next((i for i, m in bloque if (m < mes if descendente else m > mes)),
                            bloque[-1][0] + 1 if bloque else len(resultado.columns))
            resultado.insert(posicion, nombre, pd.Series(None, index=resultado.index, dtype=object))
            nuevas[nombre] = nombre
            originales[nombre] = nombre
    resultado.attrs['columnas_tx_nuevas'] = nuevas
    resultado.attrs['encabezados_comisiones'] = originales
    diagnosticos = []
    for idx, fila in resultado.iterrows():
        diferencias = {}
        hist = fila.get('__TX_VENTAS')
        hist = hist if isinstance(hist, dict) else {}
        principal = periodo_fila(fila)
        if principal or hist or fila.get("__CONCATENAR") in por_clave:
            for ano, mes in sorted(periodos):
                nombre = 'MONTO TX ' + MESES[mes - 1]
                col = next(c for c in resultado if normalizar_nombre_columna(originales.get(c, c)) == nombre)
                venta, _ = hist.get((ano, mes), (None, ''))
                registro = lookup.get((fila.get('__CONCATENAR'), ano, mes))
                monto = registro.get('__MONTO_TX') if registro is not None else None
                if monto is not None and not pd.isna(monto):
                    resultado.at[idx, col] = monto
                    if venta is not None and monto != venta:
                        diferencias[(ano, mes)] = {'ventas': venta, 'r34': monto, 'diferencia': monto - venta}
                elif venta is not None:
                    resultado.at[idx, col] = venta
        diagnosticos.append(diferencias)
    resultado['__DIFERENCIA_TX_FUENTES'] = diagnosticos
    return resultado


def estado_historial(fila, monto_r34=None):
    from procesamiento import normalizar_nombre_columna
    valores = [numero_tx(v) for c, v in fila.items() if re.fullmatch(r'MONTO TX (?:' + '|'.join(MESES) + ')', normalizar_nombre_columna(c))]
    if monto_r34 is not None:
        valores.append(numero_tx(monto_r34))
    montos = [v for v, e in valores if v is not None]
    if any(v > 1000 for v in montos): return 'CON_TX'
    if any(v == 1000 for v in montos): return 'REVISAR 1000'
    if any(0.01 <= v <= 999.99 for v in montos): return 'C/P SIN TX'
    if montos and all(v == 0 for v in montos): return 'SIN TX'
    if montos: return 'REVISAR'
    return 'N/A'


def validar_periodo_r34(ano, mes):
    try:
        a, m = float(ano), float(mes)
        if a.is_integer() and m.is_integer() and 1 <= a <= 9999 and 1 <= m <= 12:
            return int(a), int(m)
    except (TypeError, ValueError, OverflowError):
        pass
    return None


class PeriodoR34Requerido(ValueError):
    def __init__(self, archivos):
        self.archivos = archivos
        super().__init__('Hay registros R34 sin año/mes válido. Indica el período únicamente para esos registros.')
