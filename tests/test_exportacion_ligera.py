import io
import unittest
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
from unittest.mock import patch

from exportacion_ligera import copiar_vinculo_sin_cache, NS
from test_estructura_comisiones import maestro_ficticio
import procesamiento as p


def vinculo(prefijo=''):
    tag = lambda n: prefijo+n
    xmlns = 'xmlns:m' if prefijo else 'xmlns'
    return (f'<{tag("externalLink")} {xmlns}="{NS}" xmlns:r="urn:relations">'
            f'<{tag("externalBook")} r:id="rId1"><{tag("sheetNames")}>'
            f'<{tag("sheetName")} val="R34 ficticio"/></{tag("sheetNames")}>'
            f'<{tag("definedNames")}><{tag("definedName")} name="Prueba" refersTo="Hoja!$A$1"/>'
            f'</{tag("definedNames")}><{tag("sheetDataSet")}><{tag("sheetData")} sheetId="0">'
            f'<{tag("row")} r="1"><{tag("cell")} r="A1"><{tag("v")}>123</{tag("v")}>'
            f'</{tag("cell")}></{tag("row")}></{tag("sheetData")}></{tag("sheetDataSet")}>'
            f'</{tag("externalBook")}></{tag("externalLink")}>').encode()


class ExportacionLigeraTests(unittest.TestCase):
    def test_cache_unicamente_y_namespaces(self):
        for prefijo in ('', 'm:'):
            entrada=vinculo(prefijo);salida=io.BytesIO()
            copiar_vinculo_sin_cache(io.BytesIO(entrada),salida)
            esperado=ET.fromstring(entrada)
            book=esperado.find('{'+NS+'}externalBook')
            book.remove(book.find('{'+NS+'}sheetDataSet'))
            self.assertEqual(ET.tostring(ET.fromstring(salida.getvalue())),ET.tostring(esperado))

    def test_lectura_acotada_y_cache_grande(self):
        class SoloBloques(io.BytesIO):
            def read(self,n=-1):
                if n<0 or n>64*1024:raise AssertionError('Lectura no acotada')
                return super().read(n)
        entrada=vinculo().replace(b'<v>123</v>',b'<v>'+b'1'*2_000_000+b'</v>')
        salida=io.BytesIO();copiar_vinculo_sin_cache(SoloBloques(entrada),salida)
        self.assertLess(len(salida.getvalue()),1000)

    def test_sin_cache_y_otro_tipo_de_vinculo(self):
        entrada=f'<externalLink xmlns="{NS}"><ddeLink ddeService="Prueba" ddeTopic="Tema"/></externalLink>'.encode()
        salida=io.BytesIO();copiar_vinculo_sin_cache(io.BytesIO(entrada),salida)
        self.assertEqual(ET.tostring(ET.fromstring(entrada)),ET.tostring(ET.fromstring(salida.getvalue())))

    def test_xml_invalido_y_dtd_no_generan_salida_valida(self):
        for entrada in (b'<externalLink>', b'<!DOCTYPE x [<!ENTITY a "x">]><x/>'):
            with self.assertRaises(ValueError):
                copiar_vinculo_sin_cache(io.BytesIO(entrada),io.BytesIO())

    def test_exportador_conserva_todas_las_otras_partes(self):
        archivo=maestro_ficticio();datos=io.BytesIO()
        with ZipFile(archivo) as original,ZipFile(datos,'w',ZIP_DEFLATED) as z:
            for info in original.infolist():z.writestr(info,original.read(info))
            for i in (1,2):
                z.writestr(f'xl/externalLinks/externalLink{i}.xml',vinculo())
                z.writestr(f'xl/externalLinks/_rels/externalLink{i}.xml.rels',b'<Relationships/>')
        final=p.preparar_comisiones(io.BytesIO(datos.getvalue()))
        resultados={'bytes_comisiones_original':datos.getvalue(),'hoja_comisiones':'VENTAS',
                    'cantidad_original':1,'final':final}
        # Comparar con la misma exportación sin el filtro: incluye VENTAS,
        # fórmulas/resultados, hojas, estilos, filtros y relaciones.
        with patch('exportacion_ligera.copiar_vinculo_sin_cache',side_effect=lambda a,b:b.write(a.read())):
            anterior=p.generar_excel_resultado(resultados)
        nuevo=p.generar_excel_resultado(resultados)
        with ZipFile(io.BytesIO(anterior)) as a,ZipFile(io.BytesIO(nuevo)) as b:
            self.assertIsNone(b.testzip())
            self.assertEqual(a.namelist(),b.namelist())
            for nombre in a.namelist():
                if nombre in ('xl/externalLinks/externalLink1.xml','xl/externalLinks/externalLink2.xml'):
                    self.assertNotIn(b'sheetDataSet',b.read(nombre))
                else:self.assertEqual(a.read(nombre),b.read(nombre),nombre)
