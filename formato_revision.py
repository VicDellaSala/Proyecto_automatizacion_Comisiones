"""Cambios XML puntuales para decisiones manuales, sin reconstruir el XLSX."""
from copy import deepcopy
import io
import re
import xml.etree.ElementTree as ET
from openpyxl.formula.translate import Translator

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def _serializar(raiz, original):
    # Excel puede referenciar prefijos en mc:Ignorable aunque no haya elementos
    # que los usen. ElementTree no debe eliminar esas declaraciones.
    namespaces = []
    for evento, dato in ET.iterparse(io.BytesIO(original), events=('start-ns', 'start')):
        if evento == 'start':
            break
        namespaces.append(dato)
        prefijo, uri = dato
        ET.register_namespace('compat_'+prefijo if re.fullmatch(r'ns\d+', prefijo) else prefijo, uri)
    salida = ET.tostring(raiz, encoding='utf-8', xml_declaration=True)
    for prefijo, uri in namespaces:
        atributo = 'xmlns:'+prefijo if prefijo else 'xmlns'
        if (atributo+'=').encode() not in salida:
            raiz.set(atributo, uri)
    return ET.tostring(raiz, encoding='utf-8', xml_declaration=True)


def conservar_filas_originales(xml, final, cantidad):
    if '__FILA_EXCEL_ORIGINAL' not in final:
        return xml, cantidad
    fuentes = final.loc[final['__ORIGEN'].eq('COMISIONES'), '__FILA_EXCEL_ORIGINAL'].tolist()
    if fuentes == list(range(2, cantidad+2)):
        return xml, cantidad
    raiz = ET.fromstring(xml)
    datos = raiz.find(NS+'sheetData')
    filas = {int(r.get('r')): r for r in datos}
    for numero, fila in filas.items():
        if 2 <= numero <= cantidad+1:
            datos.remove(fila)
    for destino, fuente in enumerate(fuentes, 2):
        fila = deepcopy(filas[int(fuente)])
        fila.set('r', str(destino))
        for celda in fila:
            origen = celda.get('r')
            nuevo = ''.join(c for c in origen if c.isalpha()) + str(destino)
            formula = celda.find(NS+'f')
            if formula is not None and formula.text:
                formula.text = Translator('='+formula.text, origin=origen).translate_formula(nuevo)[1:]
            celda.set('r', nuevo)
        datos.append(fila)
    datos[:] = sorted(datos, key=lambda r: int(r.get('r')))
    return _serializar(raiz, xml), len(fuentes)


def aplicar_rojo(xml, estilos, final):
    if '__ROJO_MANUAL' not in final or not final['__ROJO_MANUAL'].fillna(False).any():
        return xml, None
    raiz, style = ET.fromstring(xml), ET.fromstring(estilos)
    fonts, xfs = style.find(NS+'fonts'), style.find(NS+'cellXfs')
    fuentes, formatos = {}, {}
    filas_rojas = {i+2 for i, v in enumerate(final['__ROJO_MANUAL'].fillna(False)) if v}
    for fila in raiz.find(NS+'sheetData'):
        if int(fila.get('r')) not in filas_rojas:
            continue
        for celda in fila:
            previo = int(celda.get('s', '0'))
            if previo not in formatos:
                formato = deepcopy(xfs[previo])
                font_id = int(formato.get('fontId', '0'))
                if font_id not in fuentes:
                    font = deepcopy(fonts[font_id])
                    for color in list(font.findall(NS+'color')):
                        font.remove(color)
                    ET.SubElement(font, NS+'color', {'rgb': 'FFFF0000'})
                    # Reutilizar una fuente roja equivalente cuando ya exista.
                    encoded = ET.tostring(font)
                    existente = next((i for i, f in enumerate(fonts) if ET.tostring(f) == encoded), None)
                    fuentes[font_id] = len(fonts) if existente is None else existente
                    if existente is None:
                        fonts.append(font)
                formato.set('fontId', str(fuentes[font_id]))
                formato.set('applyFont', '1')
                formatos[previo] = len(xfs)
                xfs.append(formato)
            celda.set('s', str(formatos[previo]))
    fonts.set('count', str(len(fonts))); xfs.set('count', str(len(xfs)))
    return (_serializar(raiz, xml), _serializar(style, estilos))
