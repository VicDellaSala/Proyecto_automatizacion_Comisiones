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
        # Un mensaje sin identidad no convierte a todos los ausentes en ambiguos.
        self.assertTrue(e['sin_identidad'])
        self.assertEqual(proponer_jornadas(base(), {}, e)[0]['decision'], 'No Jornada')

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
        r=resultados(('A','B','C','D'),('COMISIONES','VENTAS_NUEVAS','VENTAS_NUEVAS','VENTAS_NUEVAS'))
        r['final']['BANCO']='BANCO DEL TESORO'
        r['final'].loc[2,'ESTATUS CXC']='MODALIDAD NO DEFINIDA'
        antes=r['final'].copy(deep=True);estado={}
        from revision_manual import _revalidar
        with patch('jornadas_chats._revalidar', wraps=_revalidar) as recalcular:
            nuevo,estado_nuevo=aplicar_chats(r,estado,analizar_chats(chat('Afiliado: 101\nTerminal: 1\nAfiliado: 102\nTerminal: 1\nAfiliado: 103\nTerminal: 1')))
            self.assertEqual(recalcular.call_count,1)
        pd.testing.assert_frame_equal(r['final'],antes)
        self.assertEqual(estado,{})
        self.assertEqual(nuevo['final'].loc[1,'CANAL DE VENTA (JORNADA QUE PERTENECE)'],'JORNADA BANCO DEL TESORO')
        for c in antes:
            a,b=antes.at[2,c],nuevo['final'].at[2,c]
            self.assertTrue((pd.isna(a) and pd.isna(b)) or a==b)
        self.assertEqual([p['Resultado'] for p in nuevo['resumen_chats']],['Jornada','Revisión manual','Jornada'])
        self.assertEqual(estado_nuevo['afectadas'],{1001,1003})
        pendientes=proponer_jornadas(nuevo,estado_nuevo,analizar_chats(chat('Afiliado: 102\nTerminal: 1')))
        self.assertEqual([p['row_id'] for p in pendientes],[1002])

    def test_sin_coincidencia_no_recalcula_ni_inspecciona_r34(self):
        r=base();e=analizar_chats(chat('Afiliado: 999\nTerminal: 1'))
        with patch('jornadas_chats._revalidar') as recalcular, patch('revision_manual.incidencias',side_effect=AssertionError('No recorrer R34')):
            nuevo,estado=aplicar_chats(r,{},e)
        recalcular.assert_not_called()
        pd.testing.assert_frame_equal(r['final'],nuevo['final'])
        self.assertEqual(nuevo['resumen_chats'][0]['Resultado'],'No Jornada')

    def test_app_carga_chats_con_los_cuatro_archivos(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest('Streamlit no disponible')
        from pathlib import Path
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run()
        self.assertFalse(at.exception)
        labels=[x.proto.label for x in at.get('file_uploader')]
        self.assertEqual(len(labels),5)
        self.assertIn('Chats de Jornada Tesoro (opcional: TXT o ZIP)',labels)

    def test_cambio_de_chats_invalida_resultado_y_descarga(self):
        from jornadas_chats_ui import invalidar_resultados_chats
        estado={'resultados':1,'revision_nuevas':2,'excel_final_generado':3,'precios':4}
        with patch('jornadas_chats_ui.st.session_state',estado):
            invalidar_resultados_chats()
        self.assertEqual(estado,{'precios':4})

    def test_interfaz_carga_inicial_y_resumen_sin_reaplicar(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest('Streamlit no disponible')
        a=io.BytesIO(b'Afiliado: 101\nTerminal: 1');a.name='chat.txt'
        b=io.BytesIO(b'Afiliado: 102\nTerminal: 1');b.name='otro.txt'
        source='''
import streamlit as st
from test_jornadas_chats import base
from jornadas_chats_ui import mostrar_chats, cargar_chats
from jornadas_chats import analizar_chats, aplicar_chats
archivos=cargar_chats()
if 'resultados' not in st.session_state:
    st.session_state['resultados']=base()
if st.button('Procesar'):
    r,e=aplicar_chats(base(),{},analizar_chats([(a.name,a.getvalue()) for a in archivos]))
    st.session_state['resultados']=r
    st.session_state['revision_nuevas']=e
mostrar_chats(st.session_state['resultados'],st.session_state.get('revision_nuevas',{}),None)
'''
        with patch('streamlit.file_uploader',return_value=[a]):
            at=AppTest.from_string(source).run()
            self.assertFalse(at.exception)
            at.button[0].click().run()
            self.assertFalse(at.exception)
            self.assertEqual(at.session_state['resultados']['resumen_chats'][0]['Resultado'],'Jornada')
            self.assertEqual(len(at.button),1)
        with patch('streamlit.file_uploader',return_value=[b]):
            at.button[0].click().run()
            self.assertFalse(at.exception)
            self.assertEqual(at.session_state['resultados']['resumen_chats'][0]['Resultado'],'No Jornada')
            self.assertTrue(at.session_state['revision_nuevas']['decisiones'])
