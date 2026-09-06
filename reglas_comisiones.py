import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import pandas as pd


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


# Tarifas y equivalencias confirmadas. Los patrones de agentes son completos,
# nunca búsquedas de subcadenas en nombres de personas u otras organizaciones.
AGENTES_16 = frozenset({'GRANPRO', 'MULTITIENDA', 'INV TPOS', 'POSMARACAY',
                       'POSMGTA', 'VENEPOS', 'VIRTUALNET'})
TARIFAS_CONTADO = {'CENTRO TIPO II': Decimal('50'), 'REGION CENTRO': Decimal('25'),
                   'REGION ORIENTE': Decimal('25'), 'REGION OCCIDENTE': Decimal('25')}


def _texto(valor):
    return '' if valor is None or pd.isna(valor) else str(valor).strip()


def _beneficiario(valor):
    texto = _texto(valor)
    if normalizar_texto(texto) in {'', '-', 'N/A', 'N/D', 'NA', 'ND', 'NONE', 'NAN'}:
        return ''
    return texto


def normalizar_agente(valor):
    texto = normalizar_texto(_texto(valor))
    aliases = {'CREDICARDPOSGRANPRO': 'GRANPRO', 'INVERSIONES TPOS': 'INV TPOS'}
    if texto in aliases:
        return aliases[texto]
    if texto in AGENTES_16 or texto in TARIFAS_CONTADO:
        return texto
    for agente in ('POSMGTA', 'POSMARACAY'):
        if re.fullmatch(agente + r'\s*\d+(?:\s+C\.?A\.?)?', texto):
            return agente
    return None


def _fecha_tarifa(valor):
    if valor is None or pd.isna(valor):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    for formato in ('%d/%m/%Y', '%Y-%m-%d', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(str(valor).strip(), formato).date()
        except ValueError:
            pass
    return None


def _dinero(valor):
    try:
        numero = Decimal(str(valor))
        if not numero.is_finite() or numero < 0:
            raise ValueError
        return numero.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Monto inválido; requiere revisión.') from None


def validar_cuadre(monto_banco, monto_freelance, monto_agente, monto_total):
    """Diferencia = suma de componentes - total; nunca modifica el total."""
    try:
        suma = sum((_dinero(v) if _texto(v) not in {'', '-'} else Decimal('0')
                    for v in (monto_banco, monto_freelance, monto_agente)), Decimal('0'))
        total = _dinero(monto_total)
    except ValueError:
        return dict(diferencia=None, requiere_revision=True, advertencia='Cuadre: montos incompletos o inválidos.')
    diferencia = suma - total
    return dict(diferencia=float(diferencia), requiere_revision=diferencia != 0,
                advertencia=f'Descuadre: componentes - total = {diferencia:.2f} USD.' if diferencia else '')


def calcular_tarifa(equipo, modalidad, fecha, canal='', precios=None):
    """Total por modalidad; la distribución y sus excepciones se evalúan aparte."""
    equipo = estandarizar_equipo(_texto(equipo))
    modalidad = normalizar_texto(_texto(modalidad))
    if not equipo:
        raise ValueError('Falta identificar el equipo.')
    if modalidad == 'COMODATO':
        fecha = _fecha_tarifa(fecha)
        if fecha is None:
            raise ValueError('FECHA de la venta vacía o inválida; no se asigna tarifa.')
        if equipo == 'Zappy S1MINI2':
            posterior = fecha >= date(2026, 7, 15)
            total = Decimal('25' if posterior else '20')
            regla = f"Comodato - Zappy - FECHA {'>=' if posterior else '<'} 15/07/2026"
        elif equipo == 'Pinpagos':
            posterior = fecha >= date(2026, 7, 1)
            total = Decimal('15' if posterior else '10')
            regla = f"Comodato - Pinpagos - FECHA {'>=' if posterior else '<'} 01/07/2026"
        else:
            total, regla = Decimal('20'), 'Comodato - equipo distinto de Zappy/Pinpagos'
    elif modalidad == 'AL CONTADO':
        agente = normalizar_agente(canal)
        if agente in TARIFAS_CONTADO:
            total, regla = TARIFAS_CONTADO[agente], f'Al Contado - {agente}'
        elif agente in AGENTES_16:
            precio = _dinero((PRECIOS_BASE if precios is None else precios).get(equipo))
            total = (precio * Decimal('.16')).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
            regla = f'Al Contado - {agente} - 16% de {equipo} {precio:.2f} USD'
        else:
            raise ValueError('Agente/canal de Al Contado sin equivalencia confirmada.')
    else:
        raise ValueError('Modalidad sin regla confirmada.')
    return total, f'{regla} - {total:.2f} USD'


def _banco(valor):
    return {'BANCO DEL TESORO': 'BANCO DEL TESORO', 'TESORO': 'BANCO DEL TESORO',
            'BANCARIBE': 'BANCARIBE'}.get(normalizar_texto(_texto(valor)))


def calcular_comision(*, equipo, modalidad, fecha, canal='', banco='', es_jornada=None,
                       vendedor_banco='', vendedor_freelance='', vendedor_agente='', precios=None,
                       es_freelance=False):
    """Devuelve componentes, regla y revisión sin depender de TX/Access/ESTATUS.

    Los beneficiarios proceden de roles explícitos; no se infiere una persona
    a partir de un nombre libre ni se inventa el beneficiario llamado «Equipo».
    """
    r = dict(vendedor_banco=_beneficiario(vendedor_banco), vendedor_freelance=_beneficiario(vendedor_freelance),
             vendedor_agente=_beneficiario(vendedor_agente), monto_banco=None, monto_freelance=None,
             monto_agente=None, monto_total=None, monto_pendiente_asignacion=0.0,
             regla_aplicada='', advertencia='', requiere_revision=False, diferencia=None)
    avisos = []
    try:
        modo = normalizar_texto(_texto(modalidad))
        equipo = estandarizar_equipo(_texto(equipo))
        if modo not in {'COMODATO', 'AL CONTADO'}:
            raise ValueError('Modalidad sin regla confirmada.')
        if modo == 'COMODATO' and _fecha_tarifa(fecha) is None:
            raise ValueError('FECHA de la venta vacía o inválida; no se asigna tarifa.')
        if '/' in r['vendedor_freelance']:
            partes = [s.strip() for s in r['vendedor_freelance'].split('/')]
            if len(partes) != 2 or not partes[0] or _banco(partes[1]) != 'BANCARIBE':
                raise ValueError('Freelancer/banco sin reparto confirmado.')
            if r['vendedor_banco'] and _banco(r['vendedor_banco']) != 'BANCARIBE':
                raise ValueError('Bancos contradictorios en el reparto de freelance.')
            r['vendedor_freelance'], r['vendedor_banco'] = partes[0], 'BANCARIBE'
        if r['vendedor_freelance'] or es_freelance:
            if r['vendedor_agente'] or es_jornada is True:
                raise ValueError('Combinación de freelance con agente/jornada no definida.')
            r['monto_freelance'] = 10.0
            if r['vendedor_banco']:
                if _banco(r['vendedor_banco']) != 'BANCARIBE':
                    raise ValueError('Banco de freelance sin reparto confirmado.')
                r['monto_banco'], total = 10.0, Decimal('20')
                regla = 'Freelancer + Bancaribe - Freelance 10 + Banco 10 - Total 20 USD'
            else:
                total, regla = Decimal('10'), 'Freelancer solo - 10 USD'
            if not r['vendedor_freelance']:
                r['monto_pendiente_asignacion'] = r['monto_freelance']
                avisos.append('Beneficiario freelance pendiente de asignar: 10.00 USD.')
        else:
            canal_tarifa = normalizar_agente(canal)
            agente_tarifa = normalizar_agente(r['vendedor_agente'])
            if modo == 'AL CONTADO' and canal_tarifa and agente_tarifa and canal_tarifa != agente_tarifa:
                raise ValueError('Agente y canal indican tarifas diferentes; confirmar asignación.')
            total, regla = calcular_tarifa(equipo, modo, fecha, canal_tarifa or agente_tarifa or canal, precios)
            banco_jornada = _banco(r['vendedor_banco']) or _banco(banco)
            if banco_jornada == 'BANCO DEL TESORO' and es_jornada is None:
                raise ValueError('Confirmar JORNADA u OFICINA para Banco del Tesoro.')
            if es_jornada is True:
                if banco_jornada != 'BANCO DEL TESORO':
                    raise ValueError('Jornada de banco sin reparto confirmado.')
                if r['vendedor_banco'] and _banco(r['vendedor_banco']) != 'BANCO DEL TESORO':
                    raise ValueError('Beneficiario bancario incompatible con Jornada del Tesoro.')
                r['vendedor_banco'] = r['vendedor_banco'] or 'BANCO DEL TESORO'
                monto_banco = Decimal('7.50') if modo == 'COMODATO' and equipo == 'Pinpagos' else Decimal('10')
                # Excepción confirmada exclusiva de Comodato, incluso antes del corte.
                if modo == 'COMODATO' and equipo == 'Zappy S1MINI2':
                    total = Decimal('25')
                    regla = 'Comodato - excepción Zappy en Jornada BT - 25 USD'
                if total < monto_banco:
                    raise ValueError('La tarifa total no cubre el componente bancario confirmado.')
                r['monto_banco'] = float(monto_banco)
                r['monto_agente'] = float(total - monto_banco)
                regla += f' | Jornada BT - Banco {monto_banco:.2f} + Agente {total - monto_banco:.2f} - Total {total:.2f} USD'
            else:
                if r['vendedor_banco']:
                    raise ValueError('Reparto bancario fuera de jornada sin regla confirmada.')
                r['monto_agente'] = float(total)
            if not r['vendedor_agente']:
                r['monto_pendiente_asignacion'] = r['monto_agente']
                avisos.append(f"Beneficiario comercial pendiente de asignar: {r['monto_agente']:.2f} USD.")
        r['monto_total'], r['regla_aplicada'] = float(total), regla
        cuadre = validar_cuadre(r['monto_banco'], r['monto_freelance'], r['monto_agente'], r['monto_total'])
        r['diferencia'] = cuadre['diferencia']
        if cuadre['advertencia']:
            avisos.append(cuadre['advertencia'])
    except ValueError as error:
        # El mensaje nunca contiene identificadores ni nombres de personas.
        r.update(monto_banco=None, monto_freelance=None, monto_agente=None, monto_total=None)
        avisos.append(str(error))
    r['advertencia'] = ' | '.join(avisos)
    r['requiere_revision'] = bool(avisos)
    return r


def aplicar_motor_comisiones(df, precios=None):
    """Completa nuevas sin importes; audita históricos sin reemplazarlos.

    Toda tarifa/distribución reside en este módulo. Los encabezados originales
    permiten distinguir FECHA de otras fechas y conservar el orden del maestro.
    """
    resultado = df.copy()
    originales = df.attrs.get('encabezados_comisiones', {})

    def columna(*nombres):
        nombres = {normalizar_texto(n) for n in nombres}
        encontradas = [c for c in df.columns if not str(c).startswith('__')
                       and normalizar_texto(originales.get(c, c)) in nombres]
        if len(encontradas) > 1:
            raise ValueError('Comisiones: encabezado de distribución ambiguo; confirmar columna.')
        return encontradas[0] if encontradas else None

    destinos = {
        'vendedor_banco': columna('VENDEDOR BANCO'),
        'monto_banco': columna('MONTO COMISION BANCO $'),
        'vendedor_freelance': columna('VENDEDOR / FREELANCE'),
        'monto_freelance': columna('MONTO COMISION VENDEDOR/FREELANCE $'),
        'vendedor_agente': columna('VENDEDOR AGENTE AUTORIZADO'),
        'monto_agente': columna('MONTO COMISION AGENTE AUTORIZADO $'),
        'monto_total': columna('MONTO TOTAL A PAGAR $'),
    }
    if not any(destinos.values()):
        return resultado  # Compatibilidad con maestros sin bloque de comisiones.
    if not all(destinos.values()):
        raise ValueError('Comisiones: falta parte del bloque de distribución; no se reconstruirá el libro.')
    entradas = dict(equipo=columna('EQUIPO'), modalidad=columna('ESQUEMA COMERCIAL', 'DECONTADO / FINANCIAMIENTO'),
                    fecha=columna('FECHA'), banco=columna('BANCO'))
    canales = [columna('CANAL'), columna('CANAL DE VENTA (JORNADA QUE PERTENECE)')]
    vendedor = columna('VENDEDOR')
    montos = ['monto_banco', 'monto_freelance', 'monto_agente', 'monto_total']
    for nombre in ('__REGLA_COMISION', '__ADVERTENCIA_COMISION'):
        resultado[nombre] = ''
    for nombre in ('__TOTAL_COMISION_CALCULADO', '__DIFERENCIA_CUADRE_COMISION', '__MONTO_PENDIENTE_ASIGNACION'):
        resultado[nombre] = pd.Series(None, index=resultado.index, dtype=object)
    if '__MOTIVO_REVISION' not in resultado:
        resultado['__MOTIVO_REVISION'] = ''
    if '__REQUIERE_REVISION' not in resultado:
        resultado['__REQUIERE_REVISION'] = False
    for idx, fila in df.iterrows():
        datos = {k: fila.get(c) if c else None for k, c in entradas.items()}
        for k in ('vendedor_banco', 'vendedor_freelance', 'vendedor_agente'):
            datos[k] = _beneficiario(fila[destinos[k]])
        contextos = [_texto(fila.get(c)) for c in canales if c]
        tarifas = {a for v in contextos + [datos['vendedor_agente']]
                   if (a := normalizar_agente(v))}
        datos['canal'] = next(iter(tarifas)) if len(tarifas) == 1 else ''
        datos['es_jornada'] = True if any(normalizar_texto(v) in {'JORNADA', 'JORNADA BANCO DEL TESORO'}
                                           for v in contextos) else None
        # Un rol FREELANCER explícito permite usar su vendedor; un nombre libre no.
        datos['es_freelance'] = any(normalizar_texto(v) == 'FREELANCER' for v in contextos)
        if not datos['vendedor_freelance'] and datos['es_freelance']:
            datos['vendedor_freelance'] = _beneficiario(fila.get(vendedor)) if vendedor else ''
        r = calcular_comision(**datos, precios=precios)
        avisos = [r['advertencia']] if r['advertencia'] else []
        if len(tarifas) > 1:
            avisos.append('Canales/agente con equivalencias diferentes; confirmar tarifa.')
        vacios = all(_texto(fila[destinos[k]]) == '' for k in montos)
        es_nueva = fila.get('__ORIGEN') == 'VENTAS_NUEVAS'
        if es_nueva and vacios and not avisos:
            for k, c in destinos.items():
                resultado.at[idx, c] = r[k]
            diferencia = r['diferencia']
        else:
            observado = validar_cuadre(*(fila[destinos[k]] for k in montos))
            diferencia = observado['diferencia']
            if observado['advertencia']:
                avisos.append(observado['advertencia'])
            if r['monto_total'] is not None and not vacios:
                try:
                    coincide = all((_dinero(fila[destinos[k]]) if _texto(fila[destinos[k]]) not in {'', '-'} else Decimal('0'))
                                   == (_dinero(r[k]) if r[k] is not None else Decimal('0')) for k in montos)
                    if not coincide:
                        avisos.append('Importes existentes difieren de la regla confirmada; se conservan para revisión.')
                except ValueError:
                    avisos.append('Importes existentes inválidos; se conservan para revisión.')
        advertencia = ' | '.join(dict.fromkeys(a for bloque in avisos for a in bloque.split(' | ') if a))
        resultado.at[idx, '__REGLA_COMISION'] = r['regla_aplicada']
        resultado.at[idx, '__TOTAL_COMISION_CALCULADO'] = r['monto_total']
        resultado.at[idx, '__MONTO_PENDIENTE_ASIGNACION'] = r['monto_pendiente_asignacion']
        resultado.at[idx, '__DIFERENCIA_CUADRE_COMISION'] = diferencia
        resultado.at[idx, '__ADVERTENCIA_COMISION'] = advertencia
        anteriores = [s for s in _texto(resultado.at[idx, '__MOTIVO_REVISION']).split(' | ')
                      if s and not s.startswith('Comisión: ')]
        nuevos = ['Comisión: ' + s for s in advertencia.split(' | ') if s]
        resultado.at[idx, '__MOTIVO_REVISION'] = ' | '.join(anteriores + nuevos)
        resultado.at[idx, '__REQUIERE_REVISION'] = bool(anteriores or nuevos)
    return resultado

