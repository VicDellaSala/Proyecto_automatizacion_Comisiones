import io
import unittest
import pandas as pd

from procesamiento import extraer_serial_terminal_r34, serial_r34_para_equipo, procesar_csv_r34, recalcular_comisiones
from revision_manual import incidencias
from test_revision_manual import resultados


class FuenteSerialTests(unittest.TestCase):
    def test_prefijo_inequivoco_sin_buscar_en_medio(self):
        for texto in ['123456789012 equipo ficticio', '000123456789012 [001] POS', '  123456789012']:
            self.assertEqual(extraer_serial_terminal_r34(texto), '123456789012')
        for texto in ['POS 123456789012', 'ABC123456789012', '123456789012ABC',
                      '1.23457E+11', '000000000000', 123456789012.0]:
            self.assertEqual(extraer_serial_terminal_r34(texto), '')

    def test_prioridad_comun_y_fallback_exacto(self):
        for equipo in ['Castle Dynamo', 'Zappy S1MINI2', 'Pinpagos']:
            self.assertEqual(serial_r34_para_equipo({'TERMINAL':'000123456789012 [001] POS',
                '__SERIAL_R34':'123457000000','__SERIAL_R34_ORIGINAL':'1,23457E+11'},equipo),'123456789012')
            self.assertEqual(serial_r34_para_equipo({'TERMINAL':'POS SIN PREFIJO',
                '__SERIAL_R34':'123456789012.0'},equipo),'123456789012')
            self.assertEqual(serial_r34_para_equipo({'__SERIAL_TERMINAL_R34':'123456789012',
                '__SERIAL_R34':'1,23457E+11'},equipo),'123456789012')

    def test_original_redondeado_no_se_confunde_con_expansion(self):
        for original in ['1,23457E+11',' 1.23457 E+11 ', 123456789012.0, '1.1E-2']:
            registro={'TERMINAL':'POS 123456789012', '__SERIAL_R34':'123457000000',
                      '__SERIAL_R34_ORIGINAL':original}
            self.assertEqual(serial_r34_para_equipo(registro,'Castle Dynamo'),'')
            r=resultados(('A','123456789012'))
            r['r34']=pd.DataFrame([dict(registro,__CONCATENAR='1011')])
            self.assertFalse(incidencias(r['final'],r['r34'])[2])

    def test_csv_textual_preserva_evidencia_y_comparte_resultado(self):
        csv=('PERTENENCIA;AFIPOS;SERIAL;TERMINAL;MONTO_TRANS_BS_ACUM_MES;MES_PROCESO;ANO_PROCESO\n'
             'CREDICARDPOS;1011;1,23457E+11;000123456789012 [001] POS;2000;8;2026\n')
        r34,_=procesar_csv_r34(io.BytesIO(csv.encode()),'ficticio.csv',chunksize=1)
        self.assertEqual(r34.iloc[0]['__SERIAL_R34_ORIGINAL'],'1,23457E+11')
        self.assertEqual(serial_r34_para_equipo(r34.iloc[0],'Castle Dynamo'),'123456789012')
        for equipo in ['Castle Dynamo','Zappy S1MINI2','Pinpagos']:
            r=resultados(('A','123456789012'));r['final'].loc[1,'EQUIPO']=equipo
            self.assertFalse(incidencias(r['final'],r34)[2])
            r['final']['__ANO_REPORTE']=2026;r['final']['__MES_REPORTE']=8
            final=recalcular_comisiones(r['final'],r34,set())
            self.assertEqual(final.iloc[1]['__SERIAL_R34_COMPARADO'],'123456789012')
