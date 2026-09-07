"""Tres controles de ventas nuevas, con decisiones ligadas a IDs y evidencia."""
from copy import deepcopy
from itertools import repeat

import pandas as pd

from procesamiento import (resolver_identidad_comisiones, normalizar_identificador,
    columna_observacion_comisiones, columnas_publicas_comisiones, recalcular_comisiones, serial_r34_para_equipo)
from reglas_comisiones import normalizar_texto, identificar_jornada, estandarizar_equipo, validar_cuadre


def normalizar_serial(valor):
    texto = normalizar_identificador(valor).upper()
    return '' if texto in {'', 'N/A', 'N/D', 'NA', 'ND', 'NONE', 'NAN', '-'} else texto


def columna(df, nombre):
    originales = df.attrs.get('encabezados_comisiones', {})
    opciones = [c for c in df if normalizar_texto(originales.get(c, c)) == nombre]
    if len(opciones) != 1:
        raise ValueError('Revisión: falta una columna inequívoca de ' + nombre)
    return opciones[0]


def _validar_ids(df):
    if '__ROW_ID' not in df or '__ORIGEN' not in df or df['__ROW_ID'].isna().any() or df['__ROW_ID'].duplicated().any():
        raise ValueError('Revisión: faltan identificadores estables únicos y origen.')


def incidencias(df, r34, decisiones=None):
    _validar_ids(df)
    decisiones = decisiones or {}
    identidad = resolver_identidad_comisiones(df)
    seriales = df[identidad['serial']].map(normalizar_serial)
    nuevas = df['__ORIGEN'].eq('VENTAS_NUEVAS')
    grupos = {}
    for idx, serial in seriales.items():
        if serial:
            grupos.setdefault(serial, []).append(df.at[idx, '__ROW_ID'])
    candidatos = {}
    claves_nuevas = set(df.loc[nuevas, identidad['concatenar']].map(normalizar_serial))
    if not r34.empty:
        terminales = r34['__SERIAL_TERMINAL_R34'] if '__SERIAL_TERMINAL_R34' in r34 else repeat('')
        for clave, serial, terminal, terminal_original, serial_original in zip(r34['__CONCATENAR'], r34['__SERIAL_R34'],
                terminales, r34['TERMINAL'] if 'TERMINAL' in r34 else repeat(''),
                r34['__SERIAL_R34_ORIGINAL'] if '__SERIAL_R34_ORIGINAL' in r34 else repeat(None)):
            clave = normalizar_serial(clave)
            if clave and clave in claves_nuevas:
                registro = {'__SERIAL_R34': serial, '__SERIAL_TERMINAL_R34': terminal}
                if 'TERMINAL' in r34:
                    registro['TERMINAL'] = terminal_original
                if '__SERIAL_R34_ORIGINAL' in r34:
                    registro['__SERIAL_R34_ORIGINAL'] = serial_original
                candidatos.setdefault(clave, set()).add(serial_r34_para_equipo(registro, None))
    banco_col = columna(df, 'BANCO')
    jornada_col = columna(df, 'CANAL DE VENTA (JORNADA QUE PERTENECE)')
    casos = {1: [], 2: [], 3: []}

    def agregar(paso, row_id, firma, **datos):
        if decisiones.get((paso, row_id)) != firma:
            casos[paso].append(dict(row_id=row_id, firma=firma, **datos))

    for idx, fila in df.loc[nuevas].iterrows():
        row_id, serial = fila['__ROW_ID'], seriales.at[idx]
        relacionados = grupos.get(serial, [])
        if serial and len(relacionados) > 1:
            agregar(1, row_id, (serial, tuple(relacionados)), relacionados=relacionados)
        clave = normalizar_serial(fila[identidad['concatenar']])
        opciones = set()
        for valor in candidatos.get(clave, []):
            if normalizado := normalizar_serial(valor):
                opciones.add(normalizado)
        opciones = tuple(sorted(opciones))
        sin_fuente = '' in candidatos.get(clave, set())
        if sin_fuente or (opciones and (len(opciones) > 1 or serial not in opciones)):
            agregar(2, row_id, (clave, serial, opciones, sin_fuente), serial=serial, opciones=opciones,
                    sin_fuente_confiable=sin_fuente)
        banco, contexto = fila[banco_col], fila[jornada_col]
        if normalizar_texto(banco) in {'TESORO', 'BANCO DEL TESORO'} and identificar_jornada(banco, contexto) is not True:
            agregar(3, row_id, (normalizar_texto(banco), normalizar_texto(contexto)))
    return casos


def _revalidar(df, ids, resultados, precios, estado):
    mascara = df['__ROW_ID'].isin(ids) & df['__ORIGEN'].eq('VENTAS_NUEVAS')
    if not mascara.any():
        return df
    entrada = df.loc[mascara].copy()
    originales = df.attrs.get('encabezados_comisiones', {})
    textos = {'VENDEDOR BANCO', 'VENDEDOR / FREELANCE', 'VENDEDOR AGENTE AUTORIZADO',
              'OBSERVACION', 'CANAL', 'CANAL DE VENTA (JORNADA QUE PERTENECE)',
              '__REGLA_COMISION', '__ADVERTENCIA_COMISION', '__MOTIVO_REVISION'}
    for c in entrada:
        if normalizar_texto(originales.get(c, c)) in textos and pd.api.types.is_numeric_dtype(entrada[c].dtype):
            entrada[c] = entrada[c].astype(object)
    parte = recalcular_comisiones(entrada, resultados['r34'],
        resultados['afiliados_access'], mes_r34=resultados.get('mes_r34'), precios=precios)
    salida = df.copy()
    numericas = {'MONTO COMISION BANCO $', 'MONTO COMISION VENDEDOR/FREELANCE $',
                 'MONTO COMISION AGENTE AUTORIZADO $', 'MONTO TOTAL A PAGAR $',
                 '__MONTO_TX_R34', '__TOTAL_COMISION_CALCULADO',
                 '__DIFERENCIA_CUADRE_COMISION', '__MONTO_PENDIENTE_ASIGNACION'}
    fechas = {'FECHA', 'FECHA DE PAGO', 'FECHA DE ARCHIVO', 'FECHA DE SOLICITUD RECIBIDA'}
    for c in parte:
        valores = parte[c]
        nombre = normalizar_texto(originales.get(c, c))
        if c in salida:
            anteriores = salida.loc[parte.index, c]
            iguales = anteriores.eq(valores).fillna(False) | (anteriores.isna() & valores.isna())
            if iguales.all():
                continue  # No tocar columnas que el recálculo no cambió.
        if c not in salida:
            salida[c] = pd.Series(None, index=salida.index, dtype=object)
        if nombre in numericas:
            valores = pd.to_numeric(valores, errors='coerce').astype('float64')
            existentes = pd.to_numeric(salida[c], errors='coerce')
            mixtos = salida[c].notna() & existentes.isna()
            # Fórmulas y marcas históricas se conservan como contenido mixto.
            salida[c] = salida[c].astype(object) if mixtos.any() else existentes.astype('float64')
        elif nombre in fechas or pd.api.types.is_datetime64_any_dtype(valores.dtype):
            valores = pd.to_datetime(valores, errors='coerce')
            existentes = pd.to_datetime(salida[c], errors='coerce')
            mixtos = salida[c].notna() & existentes.isna()
            salida[c] = salida[c].astype(object) if mixtos.any() else existentes
        elif pd.api.types.is_bool_dtype(valores.dtype):
            if not pd.api.types.is_bool_dtype(salida[c].dtype):
                salida[c] = salida[c].astype('boolean')
                valores = valores.astype('boolean')
        else:
            # Texto, identificadores y campos realmente mixtos, sin coerción global.
            if not (isinstance(salida[c].dtype, pd.StringDtype)
                    and valores.map(lambda v: isinstance(v, str) or pd.isna(v)).all()):
                salida[c] = salida[c].astype(object)
        salida.loc[parte.index, c] = valores
    obs = columna_observacion_comisiones(salida)
    for row_id, texto in estado.get('observaciones', {}).items():
        m = salida['__ROW_ID'].eq(row_id)
        salida.loc[m, obs] = texto
    return salida


def aplicar_decision(resultados, estado, paso, row_id, accion, serial=None, precios=None, fila_elegida=None):
    """Transacción; paso 1 permite actuar en la fila relacionada elegida."""
    estado = deepcopy(estado)
    decisiones = estado.setdefault('decisiones', {})
    df = resultados['final'].copy()
    if accion == 'eliminar' and '__FILA_EXCEL_ORIGINAL' not in df:
        df['__FILA_EXCEL_ORIGINAL'] = pd.Series(None, index=df.index, dtype=object)
        historicas = df['__ORIGEN'].eq('COMISIONES')
        df.loc[historicas, '__FILA_EXCEL_ORIGINAL'] = list(range(2, 2+int(historicas.sum())))
    casos = incidencias(df, resultados['r34'], decisiones)
    caso = next((c for c in casos.get(paso, []) if c['row_id'] == row_id), None)
    if caso is None:
        raise ValueError('El caso ya no está pendiente o no corresponde a una venta nueva.')
    idx = df.index[df['__ROW_ID'].eq(row_id)][0]
    objetivo = row_id
    if paso == 1 and accion in {'eliminar', 'desinstalado'}:
        objetivo = row_id if fila_elegida is None else fila_elegida
        if objetivo not in caso['relacionados']:
            raise ValueError('La fila elegida no pertenece al grupo duplicado.')
        idx = df.index[df['__ROW_ID'].eq(objetivo)][0]
    permitidas = {1: {'eliminar', 'desinstalado', 'mantener'},
                  2: {'comisiones', 'r34'}, 3: {'mantener', 'jornada'}}
    if accion not in permitidas[paso]:
        raise ValueError('Acción no válida para este paso.')
    if accion == 'eliminar':
        df = df.drop(index=idx)
        estado.setdefault('eliminadas', set()).add(objetivo)
    elif accion == 'desinstalado':
        df.at[idx, columna_observacion_comisiones(df)] = 'DESINSTALADO'
        estado.setdefault('observaciones', {})[objetivo] = 'DESINSTALADO'
        df.loc[idx, '__ROJO_MANUAL'] = True
    elif accion == 'r34':
        serial = normalizar_serial(serial)
        if serial not in caso['opciones']:
            raise ValueError('Selecciona explícitamente un serial disponible en R34.')
        for c in columnas_publicas_comisiones(df, 'serial'):
            df.at[idx, c] = serial
        estado.setdefault('seriales', {})[row_id] = serial
        df = _revalidar(df, {row_id}, resultados, precios, estado)
    elif accion == 'jornada':
        df.at[idx, columna(df, 'CANAL DE VENTA (JORNADA QUE PERTENECE)')] = 'JORNADA BANCO DEL TESORO'
        # El usuario autorizó sustituir el reparto de esta nueva fila. El motor
        # preserva importes existentes; vaciamos solo sus salidas antes de llamarlo.
        for nombre in ['VENDEDOR BANCO', 'VENDEDOR / FREELANCE', 'MONTO COMISION BANCO $',
                       'MONTO COMISION VENDEDOR/FREELANCE $', 'MONTO COMISION AGENTE AUTORIZADO $',
                       'MONTO TOTAL A PAGAR $']:
            df.at[idx, columna(df, nombre)] = None
        df = _revalidar(df, {row_id}, resultados, precios, estado)
        total = columna(df, 'MONTO TOTAL A PAGAR $')
        cuadre = validar_cuadre(*(df.at[idx, columna(df, n)] for n in
            ['MONTO COMISION BANCO $', 'MONTO COMISION VENDEDOR/FREELANCE $',
             'MONTO COMISION AGENTE AUTORIZADO $', 'MONTO TOTAL A PAGAR $']))
        if pd.isna(df.at[idx, total]) or cuadre['requiere_revision']:
            raise ValueError('El motor no pudo completar un reparto de Jornada válido; la decisión no se aplicó.')
        estado.setdefault('jornadas', set()).add(row_id)
    if accion in {'r34', 'jornada'}:
        estado.setdefault('afectadas', set()).add(row_id)
    # Firmar la evidencia posterior: una nueva colisión invalida decisiones viejas.
    posterior = incidencias(df, resultados['r34'])
    vigente = next((c for c in posterior[paso] if c['row_id'] == row_id), None)
    decisiones[(paso, row_id)] = vigente['firma'] if vigente else caso['firma']
    nuevo = dict(resultados, final=df)
    return nuevo, estado


def preparar_descarga(resultados, estado, precios=None):
    df = _revalidar(resultados['final'], estado.get('afectadas', set()), resultados, precios, estado)
    for _, fila in df[df['__ROW_ID'].isin(estado.get('afectadas', set()))].iterrows():
        cuadre = validar_cuadre(*(fila[columna(df, n)] for n in
            ['MONTO COMISION BANCO $', 'MONTO COMISION VENDEDOR/FREELANCE $',
             'MONTO COMISION AGENTE AUTORIZADO $', 'MONTO TOTAL A PAGAR $']))
        if cuadre['requiere_revision']:
            raise ValueError('Una venta nueva modificada no tiene un cuadre válido; no se generó el Excel.')
    return dict(resultados, final=df)


def tabla_comisiones(df, ids):
    """Datos del maestro únicamente, con el bloque operativo sin ambigüedad."""
    identidad = resolver_identidad_comisiones(df)
    columnas = list(dict.fromkeys(c for c in identidad.values() if c))
    originales = df.attrs.get('encabezados_comisiones', {})
    nombres = {'FECHA', 'ESTATUS', 'ESTATUS CXC', 'CANAL', 'VENDEDOR', 'BANCO', 'CON TX',
               'CANAL DE VENTA (JORNADA QUE PERTENECE)', 'VENDEDOR BANCO', 'VENDEDOR / FREELANCE',
               'VENDEDOR AGENTE AUTORIZADO', 'MONTO COMISION BANCO $',
               'MONTO COMISION VENDEDOR/FREELANCE $', 'MONTO COMISION AGENTE AUTORIZADO $',
               'MONTO TOTAL A PAGAR $'}
    columnas += [c for c in df if normalizar_texto(originales.get(c, c)) in nombres and c not in columnas]
    columnas.insert(columnas.index(columna(df, 'ESTATUS'))+1, columna_observacion_comisiones(df))
    filas = df[df['__ROW_ID'].isin(ids)]
    tabla = filas[columnas].copy().astype('string').fillna('')
    tabla.insert(0, 'Origen', filas['__ORIGEN'].map(lambda v: 'NUEVA' if v == 'VENTAS_NUEVAS' else 'HISTÓRICA'))
    tabla.insert(0, 'ID', filas['__ROW_ID'])
    return tabla
