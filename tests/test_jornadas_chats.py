import io
import unittest
from zipfile import ZipFile
from unittest.mock import patch

import pandas as pd
from jornadas_chats import analizar_chats, proponer_jornadas, aplicar_chats
from test_revision_manual import resultados


def chat(texto):
    return [('chat.txt', texto.encode('utf-8'))]


def base():
    r = resultados()
    r['final']['BANCO'] = 'BANCO DEL TESORO'
    return r


class ChatsTests(unittest.TestCase):
    def test_texto_negrita_listas_rangos_edicion_y_zip(self):
        texto = ('14/10/2026, 9:00 a. m. - Persona ficticia: Alta\n'
                 'Afiliación: *101*\nTerminal: *1* <Se editó este mensaje.>\n'
                 '14/10/2026, 9:01 a. m. - Persona ficticia: Alta\n'
                 'Afiliado: 102\nTerminal: 2 al 4\n'
                 'Afiliado: 103\nTerminales: 1 y 3\n')
        b = io.BytesIO()
        with ZipFile(b, 'w') as z:
            z.writestr('../../chat.txt', texto)
            z.writestr('foto.jpg', b'no se procesa')
        e = analizar_chats([('chat.zip', b.getvalue())])
        self.assertEqual(e['pares'], {('101','1'),('102','2'),('102','3'),('102','4'),('103','1'),('103','3')})
        self.assertFalse(e['ambiguos'])

    def test_no_mezcla_mensajes_ni_solo_afiliado(self):
        e = analizar_chats(chat('1/10/2026, 9:00 - A: Afiliado: 101\n'
                               '1/10/2026, 9:01 - B: Terminal: 1\nAfiliado: 102\nTerminal: 2'))
        self.assertNotIn(('101','1'), e['pares'])
        self.assertIn('101', e['ambiguos'])
        r = base()
        self.assertEqual(proponer_jornadas(r, {}, e)[0]['decision'], 'Revisión manual')
        e = analizar_chats(chat('Afiliado: 101\nTerminal: 2'))
        self.assertEqual(proponer_jornadas(r, {}, e)[0]['decision'], 'No Jornada')

    def test_campos_ambiguos_y_ausencia_de_identidad(self):
        for campo in ('1 o 2', '1-3', '0', '3 al 1', '1\nTerminal: 2'):
            e = analizar_chats(chat('Afiliado: 101\nTerminal: '+campo))
            self.assertEqual(proponer_jornadas(base(), {}, e)[0]['decision'], 'Revisión manual')
        e = analizar_chats(chat('Afiliado: ilegible\nTerminal: 1\nAfiliado: 102\nTerminal: 1'))
        self.assertEqual(proponer_jornadas(base(), {}, e)[0]['decision'], 'Revisión manual')

    def test_plantilla_vacia_no_es_una_venta_ambigua(self):
        e=analizar_chats(chat('1/10/2026, 9:00 - A: Plantilla\nAfiliación:\nTerminal:\n'
                             '1/10/2026, 9:01 - B: Afiliado: 102\nTerminal: 1'))
        self.assertFalse(e['sin_identidad'])
        self.assertEqual(proponer_jornadas(base(),{},e)[0]['decision'],'No Jornada')

    def test_sin_chats_o_archivos_invalidos_no_clasifica_ausencia(self):
        for entradas in ([], chat(''), chat('Hola'), [('chat.zip',b'roto')], [('chat.txt',b'\xff')]):
            with self.assertRaises(ValueError):
                analizar_chats(entradas)
        with patch('jornadas_chats.LIMITE', 2):
            with self.assertRaises(ValueError):
                analizar_chats(chat('Afiliado: 101\nTerminal: 1'))

    def test_union_y_duplicados_sin_afectar_otros_pasos(self):
        e = analizar_chats(chat('Afiliado: 101\nTerminal: 1')*2)
        self.assertEqual(len(e['pares']), 1)
        r=base();antes=r['final'].copy(deep=True)
        nuevo, estado=aplicar_chats(r, {}, e)
        self.assertEqual(nuevo['final'].loc[1,'CANAL DE VENTA (JORNADA QUE PERTENECE)'], 'JORNADA BANCO DEL TESORO')
        self.assertEqual(nuevo['final'].loc[1,'MONTO COMISION BANCO $'],10)
        self.assertEqual(nuevo['final'].loc[1,'MONTO COMISION AGENTE AUTORIZADO $'],10)
        pd.testing.assert_frame_equal(r['final'],antes)
        for c in ('SERIAL','TERMINAL','CONCATENAR'):
            pd.testing.assert_series_equal(nuevo['final'][c],antes[c])
        for c in antes:
            a,b=antes.at[0,c],nuevo['final'].at[0,c]
            self.assertTrue((pd.isna(a) and pd.isna(b)) or a==b)
        self.assertFalse(proponer_jornadas(nuevo,estado,e))

    def test_no_jornada_solo_firma_decision_y_protege_estatus(self):
        e=analizar_chats(chat('Afiliado: 102\nTerminal: 1'))
        r=base();nuevo,estado=aplicar_chats(r,{},e)
        pd.testing.assert_frame_equal(r['final'],nuevo['final'])
        self.assertFalse(proponer_jornadas(nuevo,estado,e))
        for estatus in ('PAGADO','DESINSTALADO'):
            r['final'].loc[1,'ESTATUS']=estatus
            self.assertFalse(proponer_jornadas(r,{},e))

    def test_error_de_reparto_no_modifica_entrada(self):
        r=resultados(('A','B','C'),('COMISIONES','VENTAS_NUEVAS','VENTAS_NUEVAS'))
        r['final']['BANCO']='BANCO DEL TESORO'
        r['final'].loc[2,'ESTATUS CXC']='MODALIDAD NO DEFINIDA'
        antes=r['final'].copy(deep=True);estado={}
        with self.assertRaises(ValueError):
            aplicar_chats(r,estado,analizar_chats(chat('Afiliado: 101\nTerminal: 1\nAfiliado: 102\nTerminal: 1')))
        pd.testing.assert_frame_equal(r['final'],antes)
        self.assertEqual(estado,{})

    def test_interfaz_confirmacion_y_cambio_archivo(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest('Streamlit no disponible')
        a=io.BytesIO(b'Afiliado: 101\nTerminal: 1');a.name='chat.txt'
        b=io.BytesIO(b'Afiliado: 102\nTerminal: 1');b.name='otro.txt'
        source='''
import streamlit as st
from test_jornadas_chats import base
from jornadas_chats_ui import mostrar_chats
if 'resultados' not in st.session_state:
    st.session_state['resultados']=base()
mostrar_chats(st.session_state['resultados'],st.session_state.get('revision_nuevas',{}),None)
'''
        with patch('streamlit.file_uploader',return_value=[a]):
            at=AppTest.from_string(source).run()
            self.assertFalse(at.exception)
            self.assertTrue(at.button[0].disabled)
            at.checkbox[0].check().run()
            self.assertFalse(at.button[0].disabled)
        with patch('streamlit.file_uploader',return_value=[b]):
            at.run()
            self.assertFalse(at.checkbox[0].value)
            self.assertTrue(at.button[0].disabled)
            at.checkbox[0].check().run()
            at.button[0].click().run()
            self.assertFalse(at.exception)
            self.assertTrue(at.session_state['revision_nuevas']['decisiones'])
