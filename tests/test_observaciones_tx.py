import unittest
import io
from datetime import datetime
from unittest.mock import patch

import pandas as pd
from openpyxl import load_workbook

import procesamiento as p
from test_estructura_comisiones import maestro_ficticio


class ObservacionTests(unittest.TestCase):
    def test_reglas_confirmadas_y_pinpagos(self):
        casos = [
            ("CON_TX", "SI", "Castle Dynamo", None, "POR PAGAR"),
            ("CON_TX", "NO", "Castle Dynamo", None, "NO POSEE REGISTRO DE OPERADORES ACCESS COMERCES"),
            ("CON_TX", "SI", "Zappy S1MINI2", None, "POR PAGAR"),
            ("CON_TX", "NO APLICA", "Pinpagos", None, "POR PAGAR"),
            ("SIN TX", "SI", "Castle Dynamo", None, "NO CUMPLE EL CRITERIO DE PAGO"),
            ("C/P SIN TX", "NO", "Pinpagos", None, "NO CUMPLE EL CRITERIO DE PAGO"),
            ("N/A", "SI", "Castle Dynamo", None, "PENDIENTE POR VALIDAR"),
            ("N/D", "NO", "Pinpagos", None, "PENDIENTE POR VALIDAR"),
            ("CON_TX", "SI", "Castle Dynamo", "N/D", "PENDIENTE POR VALIDAR"),
            ("SIN TX", "NO", "Castle Dynamo", "N/A", "PENDIENTE POR VALIDAR"),
        ]
        for tx, access, equipo, validacion, esperado in casos:
            with self.subTest(tx=tx, access=access, equipo=equipo, validacion=validacion):
                self.assertEqual(p.calcular_observacion(tx, access, equipo, validacion), esperado)

    def test_no_inventa_observacion_para_reglas_pendientes(self):
        for tx in ["REVISAR 1000", "REVISAR", "DESINSTALADO", "", "OTRO"]:
            with self.subTest(tx=tx):
                self.assertEqual(p.calcular_observacion(tx, "SI", "Castle Dynamo"), "")

    def test_preserva_texto_historico_y_manual_literalmente(self):
        for actual in ["  Nota manual ficticia  ", "POR PAGAR", "PENDIENTE POR VALIDAR"]:
            with self.subTest(actual=actual):
                self.assertEqual(p.combinar_observacion(actual, "NO CUMPLE EL CRITERIO DE PAGO"), (actual, ""))

    def test_actualiza_solo_lo_generado_en_la_sesion(self):
        self.assertEqual(p.combinar_observacion("", "POR PAGAR"), ("POR PAGAR", "POR PAGAR"))
        self.assertEqual(p.combinar_observacion("POR PAGAR", "PENDIENTE POR VALIDAR", "POR PAGAR"),
                         ("PENDIENTE POR VALIDAR", "PENDIENTE POR VALIDAR"))
        self.assertEqual(p.combinar_observacion("Nota editada", "POR PAGAR", "PENDIENTE POR VALIDAR"), ("Nota editada", ""))
        self.assertEqual(p.combinar_observacion(pd.NA, "POR PAGAR"), ("POR PAGAR", "POR PAGAR"))


class NormalizarTxTests(unittest.TestCase):
    def test_variantes_equivalentes(self):
        grupos = {
            "CON_TX": ["CON TX", "CON_TX", " con tx ", "CON  TX"],
            "DESINSTALADO": ["DESINSTALADO", " desinstalado ", "DESINTALADO"],
            "N/A": ["N/A", "n / a", "N_A"],
            "N/D": ["N/D", "n / d", "N_D"],
            "SIN TX": ["SIN TX", "sin_tx", " sin  tx "],
            "C/P SIN TX": ["C/P SIN TX", "c / p sin_tx", "C_P_SIN_TX"],
            "REVISAR 1000": ["REVISAR 1000", " revisar_1000 ", "REVISAR  1000"],
        }
        for esperado, variantes in grupos.items():
            for variante in variantes:
                with self.subTest(variante=variante):
                    self.assertEqual(p.normalizar_estado_tx(variante), esperado)

    def test_no_fusiona_conceptos_y_conserva_desconocidos(self):
        for valor in ["N/A", "N/D", "SIN TX", "C/P SIN TX", "REVISAR 1000", "Estado especial"]:
            self.assertEqual(p.normalizar_estado_tx(valor), valor)
        for valor in [None, pd.NA, float('nan'), "", "   "]:
            self.assertEqual(p.normalizar_estado_tx(valor), "")

    def test_limites_numericos_sin_cambios(self):
        for monto, esperado in [(0, "SIN TX"), (0.01, "C/P SIN TX"), (1, "C/P SIN TX"),
                                (999.99, "C/P SIN TX"), (1000, "REVISAR 1000"),
                                (1000.01, "CON_TX"), (1500, "CON_TX")]:
            with self.subTest(monto=monto):
                self.assertEqual(p.estado_transaccion(monto), esperado)


class IntegracionObservacionTests(unittest.TestCase):
    def base(self):
        base = p.preparar_comisiones(maestro_ficticio())
        base.loc[0, 'OBSERVACION'] = None
        base['__ORIGEN'] = 'VENTAS_NUEVAS'
        base['OBSERVACION.1'] = 'Nota CXC ficticia'
        base.attrs['encabezados_comisiones']['OBSERVACION.1'] = 'OBSERVACION'
        return base

    def r34(self, monto=1500, serial='PRINCIPAL'):
        return pd.DataFrame({'__CONCATENAR': ['2221'], '__MONTO_TX': [monto], '__SERIAL_R34': [serial]})

    def test_observacion_no_modifica_estatus_fechas_o_cxc(self):
        casos = [(1500, {'222'}, 'POR PAGAR', 'Aplica Pago'),
                 (1500, set(), 'NO POSEE REGISTRO DE OPERADORES ACCESS COMERCES', 'Pendiente'),
                 (1, {'222'}, 'NO CUMPLE EL CRITERIO DE PAGO', 'Pendiente'),
                 (None, {'222'}, 'N/A - MONTO TX VACIO', 'Pendiente')]
        for monto, access, observacion, estatus in casos:
            with self.subTest(monto=monto, access=access):
                base = self.base()
                with patch.object(p, 'viernes_semana_actual', return_value=datetime(2026, 1, 2)):
                    with patch.object(p, 'actualizar_observaciones'):
                        sin_obs = p.recalcular_comisiones(base, self.r34(monto), access)
                    final = p.recalcular_comisiones(base, self.r34(monto), access)
                self.assertEqual(final.loc[0, 'OBSERVACION'], observacion)
                self.assertEqual(final.loc[0, 'ESTATUS'], estatus)
                pd.testing.assert_frame_equal(final[['ESTATUS', 'fecha de pago']], sin_obs[['ESTATUS', 'fecha de pago']])
                self.assertEqual(final.loc[0, 'OBSERVACION.1'], 'Nota CXC ficticia')

    def test_notas_historicas_no_se_reemplazan_incluso_con_na_nd(self):
        for monto, serial in [(1500, 'PRINCIPAL'), (1, 'PRINCIPAL'), (None, 'N/D')]:
            base = self.base()
            base['__ORIGEN'] = 'COMISIONES'
            base.loc[0, 'OBSERVACION'] = '  Nota histórica ficticia  '
            final = p.recalcular_comisiones(base, self.r34(monto, serial), {'222'})
            self.assertEqual(final.loc[0, 'OBSERVACION'], '  Nota histórica ficticia  ')
            if monto is None:
                self.assertTrue(final.loc[0, '__REQUIERE_REVISION'])

    def test_nd_con_tx_va_a_revision_sin_alterar_transicion_de_estatus(self):
        base = self.base()
        base.loc[0, 'SERIAL.1'] = 'N/D'
        final = p.recalcular_comisiones(base, self.r34(), {'222'})
        self.assertEqual(final.loc[0, 'OBSERVACION'], 'PENDIENTE POR VALIDAR')
        self.assertTrue(final.loc[0, '__REQUIERE_REVISION'])
        self.assertEqual(final.loc[0, 'ESTATUS'], 'Aplica Pago')

    def test_revalidacion_actualiza_automaticas_y_respeta_edicion_manual(self):
        base = self.base(); base['__ORIGEN'] = 'VENTAS_NUEVAS'
        final = p.recalcular_comisiones(base, self.r34(), {'222'})
        self.assertEqual(final.loc[0, 'OBSERVACION'], 'POR PAGAR')
        final.loc[0, 'AFILIADO.1'] = '333'
        final = p.recalcular_comisiones(final, self.r34(), {'222'})
        self.assertEqual(final.loc[0, 'OBSERVACION'], 'NO POSEE REGISTRO DE OPERADORES ACCESS COMERCES')
        self.assertEqual(final.loc[0, 'CON TX'], 'CON_TX')
        self.assertEqual(final.loc[0, 'ESTATUS'], 'Aplica Pago')
        self.assertTrue(final.loc[0, '__REQUIERE_REVISION'])
        final.loc[0, 'OBSERVACION'] = 'Corrección manual ficticia'
        final.loc[0, 'AFILIADO.1'] = '222'
        final = p.recalcular_comisiones(final, self.r34(), {'222'})
        self.assertEqual(final.loc[0, 'OBSERVACION'], 'Corrección manual ficticia')

    def test_normaliza_tx_historico_sin_abrir_filas_fuera_de_validacion(self):
        for estatus, tx, esperado in [('PAGADO', ' con tx ', 'CON_TX'),
                                     ('DESINSTALADO', 'DESINTALADO', 'DESINSTALADO')]:
            base = self.base()
            base.loc[0, 'ESTATUS'] = estatus
            base.loc[0, 'CON TX'] = tx
            final = p.recalcular_comisiones(base, self.r34(), {'222'})
            self.assertEqual(final.loc[0, 'CON TX'], esperado)
            self.assertEqual(final.loc[0, 'ESTATUS'], estatus)
            self.assertTrue(pd.isna(final.loc[0, 'OBSERVACION']))

    def test_sin_columna_tx_no_confunde_estatus(self):
        base = self.base().drop(columns=['CON TX'])
        final = p.recalcular_comisiones(base, self.r34(1), set())
        self.assertEqual(final.loc[0, 'ESTATUS'], 'Pendiente')

    def test_venta_nueva_pinpagos_sin_access(self):
        base = self.base()
        base.loc[0, '__ORIGEN'] = 'VENTAS_NUEVAS'
        base.loc[0, 'ESTATUS'] = ''
        base.loc[0, 'EQUIPO'] = 'Pinpagos'
        final = p.recalcular_comisiones(base, self.r34(), set())
        self.assertEqual(final.loc[0, 'OBSERVACION'], 'POR PAGAR')
        self.assertEqual(final.loc[0, '__ACCESS_CALCULADO'], 'NO APLICA')

    def test_1000_sigue_en_revision_sin_asumir_texto_de_pago(self):
        final = p.recalcular_comisiones(self.base(), self.r34(1000), {'222'})
        self.assertEqual(final.loc[0, 'CON TX'], 'REVISAR 1000')
        self.assertEqual(final.loc[0, 'OBSERVACION'], '')
        self.assertTrue(final.loc[0, '__REQUIERE_REVISION'])

    def test_exporta_observacion_y_tx_sin_cambiar_otras_hojas(self):
        archivo = maestro_ficticio()
        base = p.preparar_comisiones(archivo)
        base.loc[0, 'OBSERVACION'] = None
        base['__ORIGEN'] = 'VENTAS_NUEVAS'
        final = p.recalcular_comisiones(base, self.r34(), {'222'})
        salida = p.generar_excel_resultado({'final': final, 'bytes_comisiones_original': archivo.getvalue(),
                                           'hoja_comisiones': 'VENTAS', 'cantidad_original': 1})
        wb = load_workbook(io.BytesIO(salida))
        self.assertEqual(wb['VENTAS']['F2'].value, 'POR PAGAR')
        self.assertEqual(wb['VENTAS']['R2'].value, 'CON_TX')
        self.assertEqual(wb['OTRA']['A1'].value, '=1+1')
