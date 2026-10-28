"""Evidencia textual de Jornada; no interpreta instrucciones de los chats."""
import re
from io import BytesIO
from zipfile import ZipFile, BadZipFile

from procesamiento import resolver_identidad_comisiones, normalizar_identificador
from reglas_comisiones import normalizar_texto
from revision_manual import incidencias, aplicar_decision, columna

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
    for caso in incidencias(df, resultados['r34'], estado.get('decisiones'))[3]:
        fila = df.loc[df['__ROW_ID'].eq(caso['row_id'])].iloc[0]
        if normalizar_texto(fila[columna(df, 'ESTATUS')]) in {'PAGADO', 'DESINSTALADO'}:
            continue
        a, t = (normalizar_identificador(fila[identidad[k]]) for k in ('afiliado', 'terminal'))
        if (a, t) in evidencia['pares']:
            decision = 'Jornada'
        elif not a or not t or a in evidencia['ambiguos'] or evidencia['sin_identidad']:
            decision = 'Revisión manual'
        else:
            decision = 'No Jornada'
        propuestas.append(dict(row_id=caso['row_id'], decision=decision))
    return propuestas


def aplicar_chats(resultados, estado, evidencia, precios=None):
    """Todo o nada: reutiliza las decisiones existentes y su validación de reparto."""
    nuevo, nuevo_estado = resultados, estado
    for propuesta in proponer_jornadas(resultados, estado, evidencia):
        if propuesta['decision'] == 'Revisión manual':
            continue
        try:
            nuevo, nuevo_estado = aplicar_decision(nuevo, nuevo_estado, 3, propuesta['row_id'],
                'jornada' if propuesta['decision'] == 'Jornada' else 'mantener', precios=precios)
        except ValueError as error:
            raise ValueError(f"Venta ID {propuesta['row_id']}: {error}") from None
    return nuevo, nuevo_estado
