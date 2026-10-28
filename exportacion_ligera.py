"""Elimina solo la caché de datos de libros externos, en streaming."""
from xml.parsers import expat
from xml.sax.saxutils import XMLGenerator


NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


def copiar_vinculo_sin_cache(origen, destino):
    """Conserva nombres, relaciones y metadatos; no toca fórmulas del workbook.

    sheetDataSet es la copia local de las celdas del libro externo. Sus datos
    pueden volver a descargarse si el usuario actualiza los vínculos en Excel.
    No se construye un árbol XML ni se acumulan las filas descartadas.
    """
    parser = expat.ParserCreate()
    escritor = XMLGenerator(destino, encoding='utf-8', short_empty_elements=True)
    pila, espacios = [], [{}]
    omitir = 0

    def inicio(nombre, atributos):
        nonlocal omitir
        actual = espacios[-1].copy()
        for clave, valor in atributos.items():
            if clave == 'xmlns':
                actual[''] = valor
            elif clave.startswith('xmlns:'):
                actual[clave[6:]] = valor
        prefijo, _, local = nombre.rpartition(':')
        identidad = (actual.get(prefijo, ''), local)
        es_cache = (pila == [(NS, 'externalLink'), (NS, 'externalBook')]
                    and identidad == (NS, 'sheetDataSet'))
        pila.append(identidad)
        espacios.append(actual)
        if omitir or es_cache:
            omitir += 1
        else:
            escritor.startElement(nombre, atributos)

    def fin(nombre):
        nonlocal omitir
        if omitir:
            omitir -= 1
        else:
            escritor.endElement(nombre)
        pila.pop()
        espacios.pop()

    def texto(valor):
        if not omitir:
            escritor.characters(valor)

    def rechazar_dtd(*args):
        raise ValueError('No se admite DTD en vínculos externos del XLSX.')

    parser.StartElementHandler = inicio
    parser.EndElementHandler = fin
    parser.CharacterDataHandler = texto
    parser.StartDoctypeDeclHandler = rechazar_dtd
    parser.ProcessingInstructionHandler = lambda nombre, valor: (
        escritor.processingInstruction(nombre, valor) if not omitir else None)
    escritor.startDocument()
    try:
        while bloque := origen.read(64 * 1024):
            parser.Parse(bloque, False)
        parser.Parse(b'', True)
    except expat.ExpatError:
        raise ValueError('No se pudo validar el XML de un vínculo externo; no se generó el Excel.') from None
    escritor.endDocument()
