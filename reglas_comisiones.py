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
    aliases = {'CREDICARDPOSGRANPRO': 'GRANPRO', 'INVERSIONES TPOS': 'INV TPOS',
               'OCCIDENTE': 'REGION OCCIDENTE', 'ORIENTE': 'REGION ORIENTE',
               'CENTRO': 'REGION CENTRO', 'POSMGTA25': 'POSMGTA',
               'POSMGTA25 CA': 'POSMGTA'}
    if texto in aliases:
        return aliases[texto]
    if texto in AGENTES_16 or texto in TARIFAS_CONTADO:
        return texto
    for agente in ('POSMARACAY',):
        if re.fullmatch(agente + r'\s*\d+(?:\s+C\.?A\.?)?', texto):
            return agente
    return None


def normalizar_canal(valor):
    """Canal comercial canónico; nunca interpreta la columna de Jornada."""
    return normalizar_agente(valor) or normalizar_texto(_texto(valor))


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


def separar_vendedor_banco(valor):
    """La barra indica persona/banco; solo Bancaribe tiene reparto confirmado."""
    partes = [normalizar_texto(p) for p in _texto(valor).split('/')]
    if len(partes) != 2 or not _beneficiario(partes[0]) or partes[1] != 'BANCARIBE':
        raise ValueError('Vendedor/banco sin reparto confirmado; requiere revisión.')
    return partes[0], 'BANCARIBE'


def identificar_jornada(banco, canal):
    texto = normalizar_texto(_texto(canal))
    if re.search(r'\bJORNADA\b', texto) and re.search(r'\bTESORO\b', texto):
        return True if _banco(banco) == 'BANCO DEL TESORO' else None
    if not texto or re.search(r'\bJORNADA\b', texto):
        return None
    return False


def calcular_comision(*, equipo, modalidad, fecha, canal='', banco='', es_jornada=None,
                       vendedor_banco='', vendedor_freelance='', vendedor_agente='', precios=None,
                       es_freelance=False, conservar_vendedor_completo=False):
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
        freelance_sin_reparto = (es_freelance and normalizar_canal(canal) == 'CREDICARDPOS'
                                 and es_jornada is not True and not conservar_vendedor_completo)
        if freelance_sin_reparto:
            r['vendedor_freelance'] = str(vendedor_freelance) if _beneficiario(vendedor_freelance) else ''
            r['vendedor_banco'] = ''
        elif conservar_vendedor_completo:
            r['vendedor_freelance'] = str(vendedor_freelance)
            partes = r['vendedor_freelance'].split('/')
            if (_banco(banco) != 'BANCARIBE' or len(partes) != 2
                    or not all(_beneficiario(p) for p in partes)):
                raise ValueError('Bancaribe: se necesitan dos componentes de VENDEDOR válidos.')
            r['vendedor_banco'] = 'BANCARIBE'
        elif '/' in r['vendedor_freelance']:
            persona, banco_persona = separar_vendedor_banco(r['vendedor_freelance'])
            if r['vendedor_banco'] and _banco(r['vendedor_banco']) != 'BANCARIBE':
                raise ValueError('Bancos contradictorios en el reparto de freelance.')
            r['vendedor_freelance'], r['vendedor_banco'] = persona, banco_persona
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
                avisos.append(f"Beneficiario no identificado: {r['monto_agente']:.2f} USD pendientes de asignar.")
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
    """Completa filas sin importes; audita importes existentes sin reemplazarlos.

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
    entradas = dict(equipo=columna('EQUIPO'), modalidad=columna('ESTATUS CXC'),
                    fecha=columna('FECHA'), banco=columna('BANCO'))
    canales = [columna('CANAL'), columna('CANAL DE VENTA (JORNADA QUE PERTENECE)')]
    vendedor = columna('VENDEDOR')
    agente_origen = columna('AGENTE AUTORIZADO')
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
        fila = fila.copy()
        if canales[0]:
            fila[canales[0]] = normalizar_canal(fila[canales[0]])
            if fila.get('__ORIGEN') == 'VENTAS_NUEVAS':
                resultado.at[idx, canales[0]] = fila[canales[0]]
                agente_actual = _beneficiario(fila[destinos['vendedor_agente']])
                if agente_actual:
                    resultado.at[idx, destinos['vendedor_agente']] = normalizar_agente(agente_actual) or agente_actual
        datos = {k: fila.get(c) if c else None for k, c in entradas.items()}
        for k in ('vendedor_banco', 'vendedor_freelance', 'vendedor_agente'):
            datos[k] = _beneficiario(fila[destinos[k]])
        contextos = [_texto(fila.get(c)) for c in canales if c]
        vendedor_original = _beneficiario(fila.get(vendedor)) if vendedor else ''
        candidatos = contextos + [vendedor_original]
        if agente_origen:
            candidatos.append(_beneficiario(fila.get(agente_origen)))
        # Solo nombres/alias de agentes confirmados, nunca personas libres ni oficinas.
        agentes = {normalizar_agente(v): v for v in candidatos if normalizar_agente(v)}
        if (not datos['vendedor_agente'] and not datos['vendedor_freelance']
                and len(agentes) == 1 and '/' not in vendedor_original
                and not any(normalizar_texto(v) == 'FREELANCER' for v in contextos)):
            datos['vendedor_agente'] = next(iter(agentes.values()))
        tarifas = {a for v in contextos + [datos['vendedor_agente']]
                   if (a := normalizar_agente(v))}
        tarifas.update(agentes)
        datos['canal'] = next(iter(tarifas)) if len(tarifas) == 1 else ''
        contexto_jornada = _texto(fila.get(canales[1])) if canales[1] else ''
        datos['es_jornada'] = identificar_jornada(datos['banco'], contexto_jornada)
        # Un rol FREELANCER explícito permite usar su vendedor; un nombre libre no.
        datos['es_freelance'] = any(normalizar_texto(v) == 'FREELANCER' for v in contextos)
        if datos['es_jornada'] is not True:
            canal_normal = _beneficiario(fila.get(canales[0])) if canales[0] else ''
            credicardpos = normalizar_texto(canal_normal) == 'CREDICARDPOS'
            es_bancaribe = _banco(datos['banco']) == 'BANCARIBE'
            bancaribe_compartido = es_bancaribe and '/' in vendedor_original
            datos['es_freelance'] = bancaribe_compartido or credicardpos
            # CANAL define el beneficiario normal; VENDEDOR y la columna de
            # Jornada no compiten con él ni aportan una tarifa alternativa.
            # Las columnas de salida no clasifican la venta: pueden contener
            # un reparto anterior que ahora deba auditarse.
            datos['vendedor_freelance'] = ''
            datos['vendedor_banco'] = ''
            datos['vendedor_agente'] = '' if datos['es_freelance'] or credicardpos else canal_normal
            if not canal_normal and not datos['es_freelance']:
                datos['vendedor_agente'] = _beneficiario(fila[destinos['vendedor_agente']])
            if bancaribe_compartido:
                datos['vendedor_freelance'] = str(fila[vendedor])
                datos['vendedor_banco'] = 'BANCARIBE'
                datos['conservar_vendedor_completo'] = True
            datos['canal'] = canal_normal
            tarifas = set()
        if not datos['vendedor_freelance'] and datos['es_freelance']:
            datos['vendedor_freelance'] = str(fila[vendedor]) if vendedor and _beneficiario(fila.get(vendedor)) else ''
            if (datos['es_jornada'] is not True and credicardpos
                    and (_banco(datos['vendedor_freelance']) or normalizar_texto(datos['vendedor_freelance'])
                         in {'FREELANCE', 'FREELANCER', 'CREDICARDPOS'})):
                datos['vendedor_freelance'] = ''  # Banco/rol no identifica una persona.
        error_vendedor = ''
        if ('/' in vendedor_original and not datos.get('conservar_vendedor_completo')
                and not (datos['es_jornada'] is not True and credicardpos)
                and (datos['es_jornada'] is True or datos['es_freelance'])):
            try:
                persona, banco_persona = separar_vendedor_banco(vendedor_original)
                if (datos['vendedor_freelance'] and normalizar_texto(datos['vendedor_freelance']) not in
                        {persona, normalizar_texto(vendedor_original)}
                        or datos['vendedor_banco'] and _banco(datos['vendedor_banco']) != banco_persona):
                    raise ValueError('Beneficiarios contradictorios con VENDEDOR; requiere revisión.')
                datos['vendedor_freelance'], datos['vendedor_banco'] = persona, banco_persona
            except ValueError as error:
                error_vendedor = str(error)
        r = calcular_comision(**datos, precios=precios)
        avisos = [r['advertencia']] if r['advertencia'] else []
        if error_vendedor:
            avisos.append(error_vendedor)
            r.update(monto_total=None, monto_agente=None, monto_banco=None, monto_freelance=None)
        if re.search(r'\bJORNADA\b', normalizar_texto(contexto_jornada)) and datos['es_jornada'] is not True:
            avisos.append('Jornada/banco sin identificación inequívoca; requiere revisión.')
        if len(tarifas) > 1:
            avisos.append('Canales/agente con equivalencias diferentes; confirmar tarifa.')
        vacios = all(_texto(fila[destinos[k]]) == '' for k in montos)
        if vacios and not avisos:
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

