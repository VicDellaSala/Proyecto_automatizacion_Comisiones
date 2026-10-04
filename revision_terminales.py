"""Paso 4 independiente. La evidencia nunca corrige identidades automáticamente."""
from copy import deepcopy
from hashlib import sha256
import pickle
import re

import pandas as pd

from procesamiento import (resolver_identidad_comisiones, crear_concatenar,
    columnas_publicas_comisiones, serial_r34_para_equipo, normalizar_nombre_columna)
from revision_manual import normalizar_serial, columna, _validar_ids, _revalidar


def _firma(resultados, estado, precios):
    return sha256(pickle.dumps((resultados['final'], resultados.get('r34'),
        resultados.get('afiliados_access'), estado, precios))).hexdigest()


def casos_terminales(resultados, estado=None):
    df = resultados['final']
    _validar_ids(df)
    identidad = resolver_identidad_comisiones(df)
    columnas = [identidad[k] for k in ('afiliado', 'terminal', 'serial')]
    if any(c is None for c in columnas):
        return []
    hechos = {}
    historicas = {}
    for _, fila in df.iterrows():
        afiliado, terminal, serial = (normalizar_serial(fila[c]) for c in columnas)
        dato = {'ID': fila['__ROW_ID'], 'Origen': fila['__ORIGEN'], 'AFILIADO': afiliado,
                'TERMINAL': terminal, 'SERIAL': serial, 'FECHA': fila.get('FECHA', '')}
        hechos[fila['__ROW_ID']] = dato
        if dato['Origen'] == 'COMISIONES' and afiliado:
            historicas.setdefault(afiliado, []).append(dato)
    referencias = {}
    for _, fila in resultados.get('r34', pd.DataFrame()).iterrows():
        historia = fila.get('__ES_HISTORIAL_TX', False)
        if pd.notna(historia) and bool(historia):
            continue
        afiliado = normalizar_serial(fila.get('__AFILIADO'))
        # Nunca interpretar TERMINAL (texto con serial) como número de terminal.
        terminal = normalizar_serial(fila.get('__TERMINAL_NUM'))
        serial = serial_r34_para_equipo(fila, None)
        if afiliado and terminal and terminal != '0' and serial:
            referencias.setdefault(afiliado, []).append({'ID': '', 'Origen': 'R34',
                'AFILIADO': afiliado, 'TERMINAL': terminal, 'SERIAL': serial,
                'FECHA': '', 'Año R34': fila.get('__ANO_R34'), 'Mes R34': fila.get('__MES_R34')})
    casos = []
    for row_id, actual in hechos.items():
        if actual['Origen'] != 'VENTAS_NUEVAS' or not actual['AFILIADO']:
            continue
        candidatas = [h for h in historicas.get(actual['AFILIADO'], [])
                      if h['TERMINAL'] and h['TERMINAL'] != actual['TERMINAL']]
        evidencia = [r for r in referencias.get(actual['AFILIADO'], [])
                     if r['SERIAL'] == actual['SERIAL']]
        if not candidatas and not any(r['TERMINAL'] != actual['TERMINAL'] for r in evidencia):
            continue
        firma = sha256(pickle.dumps((actual, candidatas, evidencia))).hexdigest()
        if (estado or {}).get('terminales_revisadas', {}).get(row_id) == firma:
            continue
        casos.append({'row_id': row_id, 'firma': firma, 'actual': actual,
                      'historicas': candidatas, 'r34': evidencia,
                      'serial_coincide': any(h['SERIAL'] == actual['SERIAL'] and actual['SERIAL'] for h in candidatas),
                      'terminales': sorted({h['TERMINAL'] for h in candidatas + evidencia
                                           if h['TERMINAL'] and h['TERMINAL'] != '0'})})
    return casos


def preparar_cambio_terminal(resultados, estado, row_id, terminal=None, *,
                             mantener=False, misma_venta=False, conservar_existente=None, precios=None):
    """Vista previa sin mutación. Colisiones requieren elegir una fila existente."""
    caso = next((c for c in casos_terminales(resultados, estado) if c['row_id'] == row_id), None)
    if caso is None:
        raise ValueError('La evidencia cambió o el caso ya no está pendiente. Revise de nuevo.')
    firma = _firma(resultados, estado, precios)
    nuevo, nuevo_estado = dict(resultados), deepcopy(estado)
    df = resultados['final'].copy(deep=True)
    idx = df.index[df['__ROW_ID'].eq(row_id)][0]
    identidad = resolver_identidad_comisiones(df)
    if mantener:
        nuevo_estado.setdefault('terminales_revisadas', {})[row_id] = caso['firma']
        nuevo['final'] = df
        return dict(resultados=nuevo, estado=nuevo_estado, firma=firma, cambios=[], eliminada=None)
    terminal = normalizar_serial(terminal)
    if not misma_venta:
        raise ValueError('Confirme expresamente que la evidencia corresponde a la misma venta/equipo.')
    if terminal not in caso['terminales'] or terminal == caso['actual']['TERMINAL']:
        raise ValueError('Seleccione una terminal distinta disponible en la evidencia.')
    col_estatus = columna(df, 'ESTATUS')
    if normalizar_serial(df.at[idx, col_estatus]) in {'PAGADO', 'DESINSTALADO'}:
        raise ValueError('Esta fila está protegida. El Paso 4 no modifica PAGADO ni DESINSTALADO.')
    clave = crear_concatenar(caso['actual']['AFILIADO'], terminal)
    claves = [crear_concatenar(f[identidad['afiliado']], f[identidad['terminal']]) for _, f in df.iterrows()]
    colisiones = df.loc[pd.Series(claves, index=df.index).eq(clave) & df['__ROW_ID'].ne(row_id)]
    cambios = [{'Campo': 'TERMINAL', 'Antes': caso['actual']['TERMINAL'], 'Después': terminal},
               {'Campo': 'CONCATENAR', 'Antes': crear_concatenar(caso['actual']['AFILIADO'], caso['actual']['TERMINAL']), 'Después': clave}]
    eliminada = None
    if not colisiones.empty:
        if len(colisiones) != 1 or conservar_existente not in colisiones['__ROW_ID'].tolist():
            raise ValueError('La nueva identidad ya existe. Seleccione explícitamente conservar esa fila y retirar solo la incorporación nueva; no se fusionan filas automáticamente.')
        # Nunca borrar ni recalcular un histórico por esta revisión.
        if colisiones.iloc[0]['__ORIGEN'] != 'COMISIONES':
            raise ValueError('La identidad colisiona con otra venta nueva. Requiere revisión individual; no se fusionan automáticamente.')
        df = df.drop(index=idx)
        eliminada = row_id
        nuevo_estado.setdefault('eliminadas', set()).add(row_id)
        nuevo_estado.setdefault('afectadas', set()).discard(row_id)
        cambios.append({'Campo': 'Fila nueva', 'Antes': str(row_id), 'Después': 'Retirar; conservar íntegra la fila histórica seleccionada'})
    else:
        for tipo, valor in (('terminal', terminal), ('concatenar', clave)):
            for c in columnas_publicas_comisiones(df, tipo):
                df[c] = df[c].astype(object)
                df.at[idx, c] = valor
        for c, valor in (('__TERMINAL', terminal), ('__CONCATENAR', clave)):
            if c not in df:
                df[c] = pd.Series(None, index=df.index, dtype=object)
            df[c] = df[c].astype(object)
            df.at[idx, c] = valor
        # No conservar TX calculados con la terminal anterior. La evidencia del
        # reporte sigue en __TX_VENTAS, con sus períodos; el motor existente
        # reconstruye los montos usando el nuevo cruce sin trasladar meses.
        originales = df.attrs.get('encabezados_comisiones', {})
        for c in df:
            nombre = normalizar_nombre_columna(originales.get(c, c))
            if re.fullmatch(r'MONTO TX .+', nombre) or nombre == 'CON TX':
                df[c] = df[c].astype(object)
                df.at[idx, c] = None
        if normalizar_serial(df.at[idx, col_estatus]) == 'APLICAPAGO':
            fechas_pago = [c for c in df if normalizar_nombre_columna(originales.get(c, c)) == 'FECHA DE PAGO']
            if fechas_pago:
                df[fechas_pago[0]] = df[fechas_pago[0]].astype(object)
                df.at[idx, fechas_pago[0]] = None
        df.at[idx, col_estatus] = 'Pendiente'
        df = _revalidar(df, {row_id}, resultados, precios, nuevo_estado)
        antes = resultados['final'].loc[idx]
        for c in df:
            if str(c).startswith('__'):
                continue
            a, b = antes.get(c, ''), df.at[idx, c]
            if str(a) != str(b) and c not in columnas_publicas_comisiones(df, 'terminal') + columnas_publicas_comisiones(df, 'concatenar'):
                cambios.append({'Campo': str(c), 'Antes': str(a), 'Después': str(b)})
        nuevo_estado.setdefault('afectadas', set()).add(row_id)
    nuevo['final'] = df
    restante = next((c for c in casos_terminales(nuevo) if c['row_id'] == row_id), None)
    nuevo_estado.setdefault('terminales_revisadas', {})[row_id] = restante['firma'] if restante else caso['firma']
    return dict(resultados=nuevo, estado=nuevo_estado, firma=firma, cambios=cambios, eliminada=eliminada)


def aplicar_cambio_terminal(resultados, estado, vista, precios=None):
    if vista['firma'] != _firma(resultados, estado, precios):
        raise ValueError('La vista previa quedó desactualizada. Revise nuevamente antes de aplicar.')
    return vista['resultados'], vista['estado']
