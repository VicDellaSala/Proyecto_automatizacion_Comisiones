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
        self.assertEqual(r['vendedor_freelance'], 'PERSONA FICTICIA')
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
    def test_variantes_jornada_tesoro_palabras_completas(self):
        from reglas_comisiones import identificar_jornada
        for texto in ['JORNADA TESORO CORO', 'JORNADA BANCO DEL TESORO',
                      'JORNADA BANCO TESORO', 'JORNADA TESORO',
                      ' jornada   tesoro localidad ficticia ']:
            self.assertIs(identificar_jornada('TESORO', texto), True)
            self.assertIsNot(identificar_jornada('OTRO BANCO', texto), True)
        for texto in ['BANCO TESORO', 'TESORO', 'PREJORNADA TESORO', 'JORNADA TESOROS']:
            self.assertIsNot(identificar_jornada('TESORO', texto), True)

    def test_alias_occidente_exacto_y_salida_canonica(self):
        self.assertEqual(normalizar_agente('  occidente '), 'REGION OCCIDENTE')
        for valor in ['AGENTE OCCIDENTE', 'OCCIDENTE NUEVO', 'OCCIDENTES']:
            self.assertIsNone(normalizar_agente(valor))
        for canal in ['OCCIDENTE', 'REGION OCCIDENTE']:
            base = self.base()
            base['CANAL'], base['ESTATUS CXC'] = canal, 'AL CONTADO'
            base['VENDEDOR AGENTE AUTORIZADO'] = ''
            r = self.aplicar(base).iloc[0]
            self.assertEqual(r['VENDEDOR AGENTE AUTORIZADO'], 'REGION OCCIDENTE')
            self.assertEqual(r['MONTO COMISION AGENTE AUTORIZADO $'], 25)
            self.assertEqual(r['MONTO TOTAL A PAGAR $'], 25)
            self.assertFalse(r['__REQUIERE_REVISION'])

    def test_jornada_coro_conserva_repartos_comodato(self):
        for equipo, total, agente in [('Castle', 20, 10), ('Zappy', 25, 15)]:
            base = self.base()
            base['BANCO'], base['CANAL'] = 'TESORO', 'CENTRO TIPO II'
            base['CANAL DE VENTA (JORNADA QUE PERTENECE)'] = 'JORNADA TESORO CORO'
            base['EQUIPO'], base['VENDEDOR AGENTE AUTORIZADO'] = equipo, ''
            r = self.aplicar(base).iloc[0]
            self.assertEqual(r['MONTO COMISION BANCO $'], 10)
            self.assertEqual(r['MONTO COMISION AGENTE AUTORIZADO $'], agente)
            self.assertEqual(r['MONTO TOTAL A PAGAR $'], total)
            self.assertEqual(r['__DIFERENCIA_CUADRE_COMISION'], 0)
            self.assertFalse(r['__REQUIERE_REVISION'])

    def base(self, origen='VENTAS_NUEVAS'):
        return pd.DataFrame({
            'EQUIPO': ['Castle Dynamo'], 'ESTATUS CXC': ['COMODATO'],
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

    def test_no_inventa_beneficiario_y_completa_maestro_vacio(self):
        base = self.base()
        base['VENDEDOR AGENTE AUTORIZADO'] = ['']
        final = self.aplicar(base)
        self.assertTrue(pd.isna(final.loc[0, 'MONTO TOTAL A PAGAR $']))
        self.assertEqual(final.loc[0, '__MONTO_PENDIENTE_ASIGNACION'], 20)
        self.assertEqual(final.loc[0, '__TOTAL_COMISION_CALCULADO'], 20)
        self.assertTrue(final.loc[0, '__REQUIERE_REVISION'])
        final = self.aplicar(self.base('COMISIONES'))
        self.assertEqual(final.loc[0, 'MONTO TOTAL A PAGAR $'], 20)
        self.assertFalse(final.loc[0, '__REQUIERE_REVISION'])

    def test_modalidad_cxc_y_ventas_normales(self):
        casos = [('COMODATO', 'Castle', '2026-08-01', 'Región Centro', 20),
                 ('COMODATO', 'Zappy', '2026-07-14', 'Región Centro', 20),
                 ('COMODATO', 'Zappy', '2026-07-15', 'Región Centro', 25),
                 ('COMODATO', 'Pinpagos', '2026-06-30', 'Región Centro', 10),
                 ('COMODATO', 'Pinpagos', '2026-07-01', 'Región Centro', 15),
                 *[('AL CONTADO', 'Castle', None, a, 25) for a in
                   ['Región Centro', 'Región Oriente', 'Región Occidente']],
                 ('AL CONTADO', 'Castle', None, 'Centro Tipo II', 50),
                 ('AL CONTADO', 'Castle', None, 'GranPro', 38.4),
                 ('AL CONTADO', 'Zappy', None, 'Virtualnet', 36)]
        for modo, equipo, fecha, agente, total in casos:
            with self.subTest(modo=modo, equipo=equipo, agente=agente):
                base = self.base()
                base['ESTATUS CXC'], base['EQUIPO'], base['FECHA'] = modo, equipo, fecha
                base['ESQUEMA COMERCIAL'] = 'CONTRADICTORIO'
                base['VENDEDOR AGENTE AUTORIZADO'], base['CANAL'] = '', agente
                r = self.aplicar(base).iloc[0]
                self.assertEqual(r['MONTO TOTAL A PAGAR $'], total)
                self.assertEqual(r['MONTO COMISION AGENTE AUTORIZADO $'], total)
                self.assertEqual(r['VENDEDOR AGENTE AUTORIZADO'], normalizar_agente(agente))
                self.assertEqual(r['__DIFERENCIA_CUADRE_COMISION'], 0)

    def test_vendedor_barra_desde_columna_original(self):
        for vendedor, valido in [(' Persona Ficticia / bancaribe ', True),
                                 ('Persona / Otro Banco', False), ('Persona / Bancaribe / Otro', False)]:
            base = self.base()
            base['CANAL'] = 'CREDICARDPOS'
            base['VENDEDOR AGENTE AUTORIZADO'] = ''
            base['VENDEDOR'] = vendedor
            r = self.aplicar(base).iloc[0]
            if valido:
                self.assertEqual(r['MONTO TOTAL A PAGAR $'], 20)
                self.assertEqual(r['MONTO COMISION BANCO $'], 10)
                self.assertEqual(r['MONTO COMISION VENDEDOR/FREELANCE $'], 10)
                self.assertEqual(r['VENDEDOR / FREELANCE'], 'PERSONA FICTICIA')
            else:
                self.assertTrue(r['__REQUIERE_REVISION'])
                self.assertTrue(pd.isna(r['MONTO TOTAL A PAGAR $']))

    def test_jornada_requiere_banco_y_canal(self):
        for canal, banco, esperado in [('Jornada Banco Tesoro', 'Tesoro', 10),
                                       (' jornada del tesoro ', 'Banco del Tesoro', 10),
                                       ('OFICINA', 'Tesoro', None),
                                       ('Jornada Banco Tesoro', 'Otro', 'revision'),
                                       ('JORNADA DESCONOCIDA', 'Tesoro', 'revision')]:
            base = self.base()
            base['BANCO'], base['CANAL DE VENTA (JORNADA QUE PERTENECE)'] = banco, canal
            r = self.aplicar(base).iloc[0]
            if esperado == 'revision':
                self.assertTrue(r['__REQUIERE_REVISION'])
                self.assertTrue(pd.isna(r['MONTO TOTAL A PAGAR $']))
            else:
                self.assertEqual(r['MONTO TOTAL A PAGAR $'], 20)
                self.assertEqual(r['MONTO COMISION BANCO $'], esperado)

    def test_no_sustituye_cxc_invalido_por_estatus_o_esquema(self):
        base = self.base()
        base['ESTATUS CXC'] = ''
        base['ESQUEMA COMERCIAL'] = base['ESTATUS'] = 'COMODATO'
        r = self.aplicar(base).iloc[0]
        self.assertTrue(r['__REQUIERE_REVISION'])
        self.assertTrue(pd.isna(r['MONTO TOTAL A PAGAR $']))

    def test_barra_con_rol_freelancer_y_revalidacion(self):
        base = self.base()
        base['VENDEDOR AGENTE AUTORIZADO'] = ''
        base['CANAL'] = 'FREELANCER'
        base['VENDEDOR'] = 'Persona Ficticia / Bancaribe'
        final = self.aplicar(base)
        self.assertEqual(final.loc[0, 'MONTO TOTAL A PAGAR $'], 20)
        repetido = self.aplicar(final)
        pd.testing.assert_frame_equal(final, repetido)

    def test_fallback_canal_no_depende_de_otras_columnas(self):
        casos = [('REGION CENTRO', 'AL CONTADO', 'Castle', 25),
                 ('REGION OCCIDENTE', 'AL CONTADO', 'Castle', 25),
                 ('REGION ORIENTE', 'AL CONTADO', 'Castle', 25),
                 ('CENTRO TIPO II', 'AL CONTADO', 'Castle', 50),
                 ('GRANPRO', 'AL CONTADO', 'Castle', 38.4),
                 ('VIRTUALNET', 'AL CONTADO', 'Zappy', 36),
                 ('VENEPOS', 'AL CONTADO', 'Castle', 38.4),
                 ('CANAL FICTICIO', 'COMODATO', 'Castle', 20)]
        for canal, modo, equipo, total in casos:
            with self.subTest(canal=canal):
                base = self.base()
                base['CANAL'], base['ESTATUS CXC'], base['EQUIPO'] = canal, modo, equipo
                base['VENDEDOR AGENTE AUTORIZADO'] = ''
                base['VENDEDOR'] = 'MULTITIENDA'
                base['CANAL DE VENTA (JORNADA QUE PERTENECE)'] = 'REGION ORIENTE'
                r = self.aplicar(base).iloc[0]
                self.assertEqual(r['VENDEDOR AGENTE AUTORIZADO'], canal)
                self.assertEqual(r['MONTO COMISION AGENTE AUTORIZADO $'], total)
                self.assertEqual(r['MONTO TOTAL A PAGAR $'], total)
                self.assertEqual(r['__DIFERENCIA_CUADRE_COMISION'], 0)

    def test_credicardpos_exacto_persona_y_bancaribe(self):
        for vendedor, total, banco in [('Persona Ficticia', 10, None),
                                      (' Persona Ficticia / bancaribe ', 20, 10)]:
            base = self.base()
            base['CANAL'] = ' credicardpos '
            base['VENDEDOR'] = vendedor
            base['VENDEDOR AGENTE AUTORIZADO'] = 'CREDICARDPOS'
            r = self.aplicar(base).iloc[0]
            self.assertEqual(r['VENDEDOR AGENTE AUTORIZADO'], '')
            self.assertEqual(r['MONTO COMISION VENDEDOR/FREELANCE $'], 10)
            self.assertEqual(r['MONTO COMISION BANCO $'], banco)
            self.assertEqual(r['MONTO TOTAL A PAGAR $'], total)
            self.assertEqual(r['__DIFERENCIA_CUADRE_COMISION'], 0)
            self.assertEqual(r['VENDEDOR / FREELANCE'].upper(), 'PERSONA FICTICIA')

    def test_credicardpos_en_otras_columnas_no_es_freelance(self):
        base = self.base()
        base['CANAL'] = 'REGION CENTRO'
        base['VENDEDOR'] = 'CREDICARDPOS'
        base['CANAL DE VENTA (JORNADA QUE PERTENECE)'] = 'CREDICARDPOS'
        base['VENDEDOR AGENTE AUTORIZADO'] = ''
        r = self.aplicar(base).iloc[0]
        self.assertEqual(r['VENDEDOR AGENTE AUTORIZADO'], 'REGION CENTRO')
        self.assertFalse(r['VENDEDOR / FREELANCE'])
        self.assertEqual(r['MONTO TOTAL A PAGAR $'], 20)

    def test_credicardpos_banco_desconocido_no_inventa(self):
        base = self.base()
        base['CANAL'], base['VENDEDOR'] = 'CREDICARDPOS', 'Persona Ficticia / Otra Persona'
        base['VENDEDOR AGENTE AUTORIZADO'] = ''
        r = self.aplicar(base).iloc[0]
        self.assertTrue(r['__REQUIERE_REVISION'])
        self.assertTrue(pd.isna(r['MONTO TOTAL A PAGAR $']))

    def test_jornada_tiene_precedencia_sobre_credicardpos(self):
        base = self.base()
        base['CANAL'] = 'CREDICARDPOS'
        base['BANCO'] = 'TESORO'
        base['CANAL DE VENTA (JORNADA QUE PERTENECE)'] = 'JORNADA BANCO TESORO'
        base['VENDEDOR'] = 'Persona Ficticia'
        r = self.aplicar(base).iloc[0]
        self.assertEqual(r['MONTO COMISION BANCO $'], 10)
        self.assertEqual(r['MONTO COMISION AGENTE AUTORIZADO $'], 10)
        self.assertEqual(r['MONTO TOTAL A PAGAR $'], 20)
        self.assertFalse(r['VENDEDOR / FREELANCE'])

    def test_canal_alias_con_credicardpos_no_es_freelancer(self):
        base = self.base()
        base['CANAL'] = 'CREDICARDPOSGRANPRO'
        base['ESTATUS CXC'] = 'AL CONTADO'
        base['VENDEDOR AGENTE AUTORIZADO'] = ''
        r = self.aplicar(base).iloc[0]
        self.assertEqual(r['MONTO TOTAL A PAGAR $'], 38.4)
        self.assertFalse(r['VENDEDOR / FREELANCE'])

    def test_credicardpos_sin_persona_no_inventa_nombre(self):
        for vendedor in ['', 'FREELANCE', 'BANCARIBE']:
            base = self.base()
            base['CANAL'], base['VENDEDOR'] = 'CREDICARDPOS', vendedor
            base['VENDEDOR AGENTE AUTORIZADO'] = ''
            r = self.aplicar(base).iloc[0]
            self.assertTrue(r['__REQUIERE_REVISION'])
            self.assertTrue(pd.isna(r['MONTO TOTAL A PAGAR $']))
            self.assertEqual(r['__TOTAL_COMISION_CALCULADO'], 10)

    def test_canal_venta_freelancer_no_clasifica(self):
        for canal, total in [('VENEPOS', 38.4), ('REGION OCCIDENTE', 25), ('REGION CENTRO', 25)]:
            base = self.base()
            base['CANAL'], base['ESTATUS CXC'] = canal, 'AL CONTADO'
            base['CANAL DE VENTA (JORNADA QUE PERTENECE)'] = 'FREELANCER'
            base['VENDEDOR'] = 'Persona Ficticia'
            base['VENDEDOR AGENTE AUTORIZADO'] = ''
            r = self.aplicar(base).iloc[0]
            self.assertEqual(r['VENDEDOR AGENTE AUTORIZADO'], canal)
            self.assertEqual(r['MONTO TOTAL A PAGAR $'], total)
            self.assertFalse(r['VENDEDOR / FREELANCE'])
            self.assertEqual(r['__DIFERENCIA_CUADRE_COMISION'], 0)

    def test_bancaribe_dos_personas_conserva_texto_completo(self):
        for canal in ['CREDICARDPOS', 'VENEPOS', 'REGION CENTRO']:
            base = self.base()
            base['CANAL'], base['BANCO'] = canal, ' bancaribe '
            base['VENDEDOR'] = ' Persona Ficticia A / Persona Ficticia B '
            base['VENDEDOR AGENTE AUTORIZADO'] = ''
            r = self.aplicar(base)
            self.assertEqual(r.loc[0, 'VENDEDOR / FREELANCE'], base.loc[0, 'VENDEDOR'])
            self.assertEqual(r.loc[0, 'VENDEDOR BANCO'], 'BANCARIBE')
            self.assertEqual(r.loc[0, 'MONTO COMISION BANCO $'], 10)
            self.assertEqual(r.loc[0, 'MONTO COMISION VENDEDOR/FREELANCE $'], 10)
            self.assertEqual(r.loc[0, 'MONTO TOTAL A PAGAR $'], 20)
            self.assertEqual(r.loc[0, '__DIFERENCIA_CUADRE_COMISION'], 0)
            pd.testing.assert_frame_equal(r, self.aplicar(r))

    def test_bancaribe_nombre_unico_es_agente(self):
        base = self.base()
        base['CANAL'], base['BANCO'] = 'VENEPOS', 'BANCARIBE'
        base['VENDEDOR'] = 'Persona Ficticia'
        base['CANAL DE VENTA (JORNADA QUE PERTENECE)'] = 'FREELANCER'
        base['VENDEDOR AGENTE AUTORIZADO'] = ''
        r = self.aplicar(base).iloc[0]
        self.assertEqual(r['VENDEDOR AGENTE AUTORIZADO'], 'VENEPOS')
        self.assertEqual(r['MONTO TOTAL A PAGAR $'], 20)
        self.assertFalse(r['VENDEDOR / FREELANCE'])
        self.assertFalse(r['VENDEDOR BANCO'])

    def test_barra_sin_bancaribe_ni_canal_credicardpos_es_normal(self):
        base = self.base()
        base['CANAL'], base['BANCO'] = 'REGION CENTRO', 'OTRO BANCO'
        base['VENDEDOR'] = 'Persona Ficticia A / Persona Ficticia B'
        base['VENDEDOR AGENTE AUTORIZADO'] = ''
        r = self.aplicar(base).iloc[0]
        self.assertEqual(r['VENDEDOR AGENTE AUTORIZADO'], 'REGION CENTRO')
        self.assertEqual(r['MONTO TOTAL A PAGAR $'], 20)
        self.assertFalse(r['VENDEDOR / FREELANCE'])

    def test_bancaribe_barra_incompleta_requiere_revision(self):
        for vendedor in ['Persona /', '/ Persona', 'Persona / Persona / Persona']:
            base = self.base()
            base['BANCO'], base['VENDEDOR'] = 'BANCARIBE', vendedor
            r = self.aplicar(base).iloc[0]
            self.assertTrue(r['__REQUIERE_REVISION'])
            self.assertTrue(pd.isna(r['MONTO TOTAL A PAGAR $']))

    def test_bancaribe_unico_credicardpos_no_inventa_agente(self):
        base = self.base()
        base['CANAL'], base['BANCO'] = 'CREDICARDPOS', 'BANCARIBE'
        base['VENDEDOR'], base['VENDEDOR AGENTE AUTORIZADO'] = 'Persona Ficticia', ''
        r = self.aplicar(base).iloc[0]
        self.assertFalse(r['VENDEDOR / FREELANCE'])
        self.assertNotEqual(r['VENDEDOR AGENTE AUTORIZADO'], 'CREDICARDPOS')
        self.assertTrue(r['__REQUIERE_REVISION'])
