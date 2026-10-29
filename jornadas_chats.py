"""Evidencia textual de Jornada; no interpreta instrucciones de los chats."""
import re
from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile, BadZipFile

import pandas as pd

from procesamiento import resolver_identidad_comisiones, normalizar_identificador
from reglas_comisiones import normalizar_texto, identificar_jornada, validar_cuadre
from revision_manual import _revalidar, columna

LIMITE = 20 * 1024 * 1024
INICIO = re.compile(r'(?m)^\[?\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}[^\n]*?(?: - |\] )')
AFILIADO = re.compile(r'\bAFILI(?:ACION|ADO)\s*[:#.-]?\s*(\d+)\b')
TERMINAL = re.compile(r'\bTERMINAL(?:ES)?[ \t]*[:#.-]?[ \t]*([^\r\n]*)')


def leer_chats(archivos):
    """Recibe (nombre, bytes). No extrae ZIP al disco ni carga adjuntos."""
    textos = []
    total = 0
    for nombre, contenido in archivos:
        if nombre.lower().endswith('.txt'):
            partes = [contenido]
        elif nombre.lower().endswith('.zip'):
            try:
                with ZipFile(BytesIO(contenido)) as z:
                    infos = [i for i in z.infolist() if not i.is_dir() and i.filename.lower().endswith('.txt')]
                    if not infos:
                        raise ValueError('El ZIP no contiene chats TXT.')
                    if total + sum(i.file_size for i in infos) > LIMITE:
                        raise ValueError('Los chats superan el límite de 20 MB de texto.')
                    partes = [z.read(i) for i in infos]
            except (BadZipFile, RuntimeError, NotImplementedError):
                raise ValueError('No se pudo leer el ZIP de chats.') from None
        else:
            raise ValueError('Carga únicamente archivos TXT o ZIP de WhatsApp.')
        for parte in partes:
            total += len(parte)
            if total > LIMITE:
                raise ValueError('Los chats superan el límite de 20 MB de texto.')
            try:
                texto = parte.decode('utf-8-sig')
            except UnicodeDecodeError:
                raise ValueError('El chat debe estar exportado como texto UTF-8 legible.') from None
            textos.append(texto)
    return textos


def analizar_chats(archivos):
    pares, ambiguos = set(), set()
    sin_identidad = False
    registros = 0
    textos = leer_chats(archivos)
    if not textos:
        raise ValueError('Carga chats antes de clasificar las ventas.')
    for texto in textos:
        # Se conserva el salto de línea para no mezclar campos o registros.
        texto = '\n'.join(normalizar_texto(linea) for linea in texto.splitlines())
        texto = re.sub(r'[*_~`\u200e\u200f]', '', texto)
        for mensaje in INICIO.split(texto):
            afiliados = list(AFILIADO.finditer(mensaje))
            etiquetas = list(re.finditer(r'\bAFILI(?:ACION|ADO)\b', mensaje))
            if len(etiquetas) > len(afiliados) and any(m[1].strip() for m in TERMINAL.finditer(mensaje)):
                sin_identidad = True
            if not afiliados:
                continue
            for i, afiliado in enumerate(afiliados):
                registros += 1
                a = normalizar_identificador(afiliado[1])
                bloque = mensaje[afiliado.end():afiliados[i+1].start() if i+1<len(afiliados) else len(mensaje)]
                campos = list(TERMINAL.finditer(bloque))
                if len(campos) != 1 or re.search(r'\bAFILI(?:ACION|ADO)\b', bloque):
                    ambiguos.add(a)
                    continue
                campo = re.sub(r'\s*<SE EDITO ESTE MENSAJE\.?>', '', campos[0][1]).strip()
                rango = re.fullmatch(r'(\d{1,3})\s+AL\s+(\d{1,3})', campo)
                if rango and 0 < int(rango[1]) <= int(rango[2]) <= 999:
                    terminales = [str(n) for n in range(int(rango[1]), int(rango[2])+1)]
                elif re.fullmatch(r'\d{1,3}(?:\s*(?:Y|,|/|&)\s*\d{1,3})*', campo):
                    terminales = re.findall(r'\d+', campo)
                else:
                    ambiguos.add(a)
                    continue
                if any(int(t) == 0 for t in terminales):
                    ambiguos.add(a)
                    continue
                pares.update((a, normalizar_identificador(t)) for t in terminales)
    if not registros:
        raise ValueError('No se encontraron registros de afiliación legibles; no se clasificará por ausencia.')
    return dict(pares=pares, ambiguos=ambiguos, sin_identidad=sin_identidad)


def proponer_jornadas(resultados, estado, evidencia):
    df = resultados['final']
    identidad = resolver_identidad_comisiones(df)
    propuestas = []
    banco_col = columna(df, 'BANCO')
    jornada_col = columna(df, 'CANAL DE VENTA (JORNADA QUE PERTENECE)')
    estatus_col = columna(df, 'ESTATUS')
    # Paso 3 depende de la venta y del chat, no necesita recorrer el R34.
    for _, fila in df.loc[df['__ORIGEN'].eq('VENTAS_NUEVAS')].iterrows():
        banco, contexto = fila[banco_col], fila[jornada_col]
        firma = (normalizar_texto(banco), normalizar_texto(contexto))
        row_id = fila['__ROW_ID']
        if (firma[0] not in {'TESORO', 'BANCO DEL TESORO'}
                or identificar_jornada(banco, contexto) is True
                or estado.get('decisiones', {}).get((3, row_id)) == firma
                or normalizar_texto(fila[estatus_col]) in {'PAGADO', 'DESINSTALADO'}):
            continue
        a, t = (normalizar_identificador(fila[identidad[k]]) for k in ('afiliado', 'terminal'))
        if (a, t) in evidencia['pares']:
            decision = 'Jornada'
        elif not a or not t or a in evidencia['ambiguos']:
            decision = 'Revisión manual'
        else:
            decision = 'No Jornada'
        propuestas.append(dict(row_id=row_id, decision=decision, firma=firma))
    return propuestas


def aplicar_chats(resultados, estado, evidencia, precios=None):
    """Un recálculo para todas las Jornadas; cada reparto se valida por separado."""
    propuestas = proponer_jornadas(resultados, estado, evidencia)
    nuevo_estado = deepcopy(estado)
    decisiones = nuevo_estado.setdefault('decisiones', {})
    original = resultados['final']
    trabajo = original.copy(deep=True)
    ids = {p['row_id'] for p in propuestas if p['decision'] == 'Jornada'}
    jornada_col = columna(original, 'CANAL DE VENTA (JORNADA QUE PERTENECE)')
    montos = [columna(original, n) for n in ('MONTO COMISION BANCO $',
              'MONTO COMISION VENDEDOR/FREELANCE $', 'MONTO COMISION AGENTE AUTORIZADO $',
              'MONTO TOTAL A PAGAR $')]
    if ids:
        mascara = trabajo['__ROW_ID'].isin(ids)
        trabajo.loc[mascara, jornada_col] = 'JORNADA BANCO DEL TESORO'
        # Las mismas salidas que limpia la decisión manual de Jornada.
        for c in montos + [columna(original, 'VENDEDOR BANCO'), columna(original, 'VENDEDOR / FREELANCE')]:
            trabajo.loc[mascara, c] = None
        trabajo = _revalidar(trabajo, ids, resultados, precios, nuevo_estado)
    final = original.copy(deep=True)
    aceptadas = set()
    resumen = []
    por_id = trabajo.set_index('__ROW_ID', drop=False)
    for propuesta in propuestas:
        row_id, decision = propuesta['row_id'], propuesta['decision']
        motivo = ''
        if decision == 'Jornada':
            fila = por_id.loc[row_id]
            cuadre = validar_cuadre(*(fila[c] for c in montos))
            if pd.isna(fila[montos[-1]]) or cuadre['requiere_revision']:
                decision = 'Revisión manual'
                motivo = fila.get('__ADVERTENCIA_COMISION', '') or 'Reparto de Jornada incompleto.'
            else:
                aceptadas.add(row_id)
                decisiones[(3, row_id)] = (propuesta['firma'][0], 'JORNADA BANCO DEL TESORO')
        elif decision == 'No Jornada':
            decisiones[(3, row_id)] = propuesta['firma']
        else:
            motivo = 'Afiliado o terminal incompletos/ambiguos en la evidencia.'
        resumen.append({'ID venta nueva': row_id, 'Resultado': decision, 'Motivo': motivo})
    # Copiar solo filas aceptadas: ni los fallos ni los históricos se modifican.
    mascara = final['__ROW_ID'].isin(aceptadas)
    if aceptadas:
        for c in trabajo:
            if c not in final:
                final[c] = pd.Series(None, index=final.index, dtype=object)
            actuales, valores = final.loc[mascara, c], trabajo.loc[mascara, c]
            if (actuales.eq(valores).fillna(False) | (actuales.isna() & valores.isna())).all():
                continue
            final[c] = final[c].astype(object)
            final.loc[mascara, c] = valores
        final.attrs.update(trabajo.attrs)
        nuevo_estado.setdefault('afectadas', set()).update(aceptadas)
        nuevo_estado.setdefault('jornadas', set()).update(aceptadas)
    return dict(resultados, final=final, resumen_chats=resumen), nuevo_estado
