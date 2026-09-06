import unittest
from datetime import date
import pandas as pd

from reglas_comisiones import calcular_comision, normalizar_agente, validar_cuadre


class MotorComisionesTests(unittest.TestCase):
    def calcular(self, **cambios):
        datos = dict(equipo='Castle Dynamo', modalidad='Comodato', fecha=date(2026, 8, 1),
                     vendedor_agente='Agente ficticio')
        datos.update(cambios)
        return calcular_comision(**datos)

    def test_comodato_y_cortes_inclusivos(self):
        for equipo, fecha, total in [
            ('Castle Dynamo', date(2026, 1, 1), 20), ('Otro POS', date(2026, 1, 1), 20),
            ('Sappy', date(2026, 7, 14), 20), ('Zappy S1MINI2', date(2026, 7, 15), 25),
            ('Pinpagos', date(2026, 6, 30), 10), ('Pinpagos', date(2026, 7, 1), 15),
        ]:
            with self.subTest(equipo=equipo, fecha=fecha):
                r = self.calcular(equipo=equipo, fecha=fecha)
                self.assertEqual(r['monto_total'], total)
                self.assertEqual(r['monto_agente'], total)
                self.assertFalse(r['requiere_revision'])
                self.assertTrue(r['regla_aplicada'])

    def test_fecha_invalida_no_inventa_tarifa(self):
        for fecha in [None, '', '31/02/2026', 0]:
            for equipo in ['Castle Dynamo', 'Zappy S1MINI2', 'Pinpagos']:
                r = self.calcular(fecha=fecha, equipo=equipo)
                self.assertIsNone(r['monto_total'])
                self.assertTrue(r['requiere_revision'])

    def test_alias_explicitos_y_negativos(self):
        for valor, esperado in [('CREDICARDPOSGRANPRO', 'GRANPRO'), ('INVERSIONES TPOS', 'INV TPOS'),
                                ('Posmgta26 CA', 'POSMGTA'), ('POSMGTA 123', 'POSMGTA'),
                                ('PosMaracay26', 'POSMARACAY'), (' región centro ', 'REGION CENTRO')]:
            self.assertEqual(normalizar_agente(valor), esperado)
        for valor in ['OTRO GRANPRO', 'GRANPRO AJENO', 'POSMGTA123OTRO', 'MULTITIENDA NUEVA', '']:
            self.assertIsNone(normalizar_agente(valor))

    def test_contado_tarifas_y_precios_editables(self):
        for canal, total in [('Centro Tipo II', 50), ('Región Centro', 25), ('Región Oriente', 25),
                             ('Región Occidente', 25), ('GranPro', 38.4), ('Multitienda', 38.4),
                             ('Inv TPOS', 38.4), ('PosMaracay', 38.4), ('PosMGTA', 38.4),
                             ('VenePos', 38.4), ('Virtualnet', 38.4)]:
            r = self.calcular(modalidad='Al Contado', canal=canal)
            self.assertEqual(r['monto_total'], total)
        r = self.calcular(modalidad='Al Contado', canal='GranPro', precios={'Castle Dynamo': 250})
        self.assertEqual(r['monto_total'], 40)
        self.assertTrue(self.calcular(modalidad='Al Contado', canal='No definido')['requiere_revision'])
        self.assertTrue(self.calcular(modalidad='Al Contado', canal='GranPro', equipo='No definido')['requiere_revision'])

    def test_jornadas(self):
        for equipo, fecha, banco, agente in [
            ('Castle Dynamo', date(2026, 8, 1), 10, 10),
            ('Zappy S1MINI2', date(2026, 7, 1), 10, 15),
            ('Pinpagos', date(2026, 6, 30), 7.5, 2.5),
            ('Pinpagos', date(2026, 7, 1), 7.5, 7.5),
        ]:
            r = self.calcular(equipo=equipo, fecha=fecha, banco='Banco del Tesoro', es_jornada=True)
            self.assertEqual((r['monto_banco'], r['monto_agente'], r['monto_total']), (banco, agente, banco+agente))
            self.assertFalse(r['requiere_revision'])

    def test_zappy_contado_prevalece_sobre_fijo_comodato(self):
        r = self.calcular(equipo='Zappy S1MINI2', modalidad='Al Contado', canal='GranPro',
                          banco='Banco del Tesoro', es_jornada=True)
        self.assertEqual((r['monto_banco'], r['monto_agente'], r['monto_total']), (10, 26, 36))

    def test_beneficiario_y_jornada_ambiguos(self):
        r = self.calcular(vendedor_agente='')
        self.assertTrue(r['requiere_revision'])
        self.assertEqual(r['monto_pendiente_asignacion'], 20)
        self.assertEqual(r['vendedor_agente'], '')
        self.assertTrue(self.calcular(banco='Banco del Tesoro')['requiere_revision'])
        self.assertTrue(self.calcular(banco='Otro banco', es_jornada=True)['requiere_revision'])
        for vacio in ['N/A', 'N/D', '-', None]:
            r = self.calcular(vendedor_agente=vacio)
            self.assertTrue(r['requiere_revision'])
            self.assertEqual(r['monto_pendiente_asignacion'], 20)
            self.assertEqual(r['vendedor_agente'], '')

    def test_freelance_bancaribe_y_bancos_no_definidos(self):
        r = self.calcular(vendedor_agente='', vendedor_freelance='Persona ficticia')
        self.assertEqual((r['monto_freelance'], r['monto_total']), (10, 10))
        r = self.calcular(vendedor_agente='', vendedor_freelance='Persona ficticia / Bancaribe')
        self.assertEqual((r['monto_banco'], r['monto_freelance'], r['monto_total']), (10, 10, 20))
        self.assertEqual(r['vendedor_freelance'], 'Persona ficticia')
        self.assertTrue(self.calcular(vendedor_agente='', vendedor_freelance='Persona ficticia / Otro banco')['requiere_revision'])
        self.assertTrue(self.calcular(vendedor_freelance='Persona ficticia')['requiere_revision'])

    def test_freelance_identificado_por_rol_sin_nombre(self):
        r = self.calcular(vendedor_agente='', es_freelance=True)
        self.assertEqual(r['monto_total'], 10)
        self.assertEqual(r['monto_pendiente_asignacion'], 10)
        self.assertTrue(r['requiere_revision'])
        self.assertEqual(r['vendedor_freelance'], '')

    def test_bancaribe_en_columnas_separadas(self):
        r = self.calcular(vendedor_agente='', vendedor_freelance='Persona ficticia', vendedor_banco='Bancaribe')
        self.assertEqual((r['monto_banco'], r['monto_freelance'], r['monto_total']), (10, 10, 20))
        self.assertFalse(r['requiere_revision'])

    def test_jornada_contado_por_region_y_precision(self):
        for equipo, canal, total in [('Zappy S1MINI2', 'Región Centro', 25),
                                     ('Castle Dynamo', 'Centro Tipo II', 50),
                                     ('Pinpagos', 'GranPro', 16.64)]:
            r = self.calcular(equipo=equipo, modalidad='Al Contado', canal=canal,
                              banco='Banco del Tesoro', es_jornada=True)
            self.assertEqual(r['monto_total'], total)
            self.assertEqual(r['monto_banco'], 10)
            self.assertEqual(r['monto_agente'], round(total-10, 2))
            self.assertFalse(r['requiere_revision'])

    def test_cuadre_exacto_y_diferencia(self):
        r = validar_cuadre(10, None, 15, 20)
        self.assertTrue(r['requiere_revision'])
        self.assertEqual(r['diferencia'], 5)
        self.assertFalse(validar_cuadre(.1, .2, None, .3)['requiere_revision'])
        self.assertTrue(validar_cuadre(None, None, None, None)['requiere_revision'])
        self.assertTrue(validar_cuadre('texto', 0, 0, 20)['requiere_revision'])


class AplicacionMotorTests(unittest.TestCase):
    def base(self, origen='VENTAS_NUEVAS'):
        return pd.DataFrame({
            'EQUIPO': ['Castle Dynamo'], 'ESQUEMA COMERCIAL': ['COMODATO'],
            'FECHA': [date(2026, 8, 1)], 'VENDEDOR AGENTE AUTORIZADO': ['Agente ficticio'],
            'MONTO COMISION AGENTE AUTORIZADO $': [None],
            'VENDEDOR BANCO': [None], 'MONTO COMISION BANCO $': [None],
            'VENDEDOR / FREELANCE': [None], 'MONTO COMISION VENDEDOR/FREELANCE $': [None],
            'MONTO TOTAL A PAGAR $': [None], '__ORIGEN': [origen],
            'ESTATUS': ['Pendiente'], 'CON TX': ['SIN TX'], 'OBSERVACION': ['Nota ficticia'],
            'ACCESS COMMERCE': ['NO'], '__MOTIVO_REVISION': [''], '__REQUIERE_REVISION': [False],
        })

    def aplicar(self, df):
        from reglas_comisiones import aplicar_motor_comisiones
        return aplicar_motor_comisiones(df)

    def test_completa_nueva_sin_modificar_otras_reglas(self):
        base = self.base()
        final = self.aplicar(base)
        self.assertEqual(final.loc[0, 'MONTO TOTAL A PAGAR $'], 20)
        self.assertEqual(final.loc[0, 'MONTO COMISION AGENTE AUTORIZADO $'], 20)
        for col in ['ESTATUS', 'CON TX', 'OBSERVACION', 'ACCESS COMMERCE']:
            pd.testing.assert_series_equal(final[col], base[col])
        self.assertTrue(final.loc[0, '__REGLA_COMISION'])

    def test_historico_no_se_corrige_silenciosamente(self):
        base = self.base('COMISIONES')
        base['MONTO COMISION BANCO $'] = [10]
        base['MONTO COMISION AGENTE AUTORIZADO $'] = [15]
        base['MONTO TOTAL A PAGAR $'] = [20]
        final = self.aplicar(base)
        self.assertEqual(final.loc[0, 'MONTO TOTAL A PAGAR $'], 20)
        self.assertEqual(final.loc[0, 'MONTO COMISION AGENTE AUTORIZADO $'], 15)
        self.assertEqual(final.loc[0, '__DIFERENCIA_CUADRE_COMISION'], 5)
        self.assertTrue(final.loc[0, '__REQUIERE_REVISION'])

    def test_no_inventa_beneficiario_ni_completa_historico_vacio(self):
        base = self.base()
        base['VENDEDOR AGENTE AUTORIZADO'] = ['']
        final = self.aplicar(base)
        self.assertTrue(pd.isna(final.loc[0, 'MONTO TOTAL A PAGAR $']))
        self.assertEqual(final.loc[0, '__MONTO_PENDIENTE_ASIGNACION'], 20)
        self.assertTrue(final.loc[0, '__REQUIERE_REVISION'])
        final = self.aplicar(self.base('COMISIONES'))
        self.assertTrue(pd.isna(final.loc[0, 'MONTO TOTAL A PAGAR $']))
        self.assertTrue(final.loc[0, '__REQUIERE_REVISION'])
