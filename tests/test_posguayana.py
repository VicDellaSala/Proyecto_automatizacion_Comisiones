"""Cobertura de POSGUAYANA con datos exclusivamente ficticios."""
import unittest
from datetime import date

import pandas as pd

import reglas_comisiones as r
import separador_pagos as p
from procesamiento import estandarizar_textos_salida
from test_separador_pagos import fila, libro, salidas, salida, valores


class PosguayanaTests(unittest.TestCase):
    def calcular(self, canal='POSGUAYANA', **cambios):
        datos = dict(equipo='Castle Dynamo', modalidad='AL CONTADO',
                     fecha=date(2026, 8, 1), canal=canal,
                     vendedor_agente=r.normalizar_agente(canal))
        datos.update(cambios)
        return r.calcular_comision(**datos)

    def test_aliases_exactos_y_no_aproximados(self):
        for canal in ('POSGUAYANA', 'POSGUAYANA 26'):
            self.assertEqual(r.normalizar_agente(canal), 'POSGUAYANA')
            self.assertEqual(r.normalizar_canal(canal), 'POSGUAYANA')
        for canal in ('POSGUAYANA26', 'POSGUAYANA 27', 'OTRO POSGUAYANA', 'POSGUAYANA 26 CA'):
            self.assertIsNone(r.normalizar_agente(canal))
            self.assertEqual(r.normalizar_canal(canal), canal)
            self.assertTrue(self.calcular(canal)['requiere_revision'])

    def test_contado_ambos_aliases_y_precio_configurable(self):
        for canal in ('POSGUAYANA', 'POSGUAYANA 26'):
            for equipo, precios, esperado in (
                ('Castle Dynamo', None, 38.4), ('Zappy S1MINI2', None, 36),
                ('Castle Dynamo', {'Castle Dynamo': 250}, 40),
            ):
                with self.subTest(canal=canal, equipo=equipo, precios=precios):
                    resultado = self.calcular(canal, equipo=equipo, precios=precios)
                    self.assertEqual(resultado['monto_agente'], esperado)
                    self.assertEqual(resultado['monto_total'], esperado)
                    self.assertFalse(resultado['requiere_revision'])
                    self.assertEqual(resultado['monto_total'],
                                     self.calcular('GRANPRO', equipo=equipo, precios=precios)['monto_total'])

    def test_comodato_conserva_equipo_y_corte(self):
        for equipo, fecha, esperado in (
            ('Castle Dynamo', date(2026, 8, 1), 20),
            ('Zappy S1MINI2', date(2026, 7, 14), 20),
            ('Zappy S1MINI2', date(2026, 7, 15), 25),
        ):
            resultado = self.calcular(equipo=equipo, modalidad='COMODATO', fecha=fecha)
            self.assertEqual(resultado['monto_agente'], esperado)
            self.assertFalse(resultado['requiere_revision'])

    def test_pinpagos_y_repartos_existentes(self):
        for modalidad in ('AL CONTADO', 'COMODATO'):
            normal = self.calcular(equipo='Pinpagos', modalidad=modalidad)
            self.assertEqual(normal['monto_total'], 15)
            tesoro = self.calcular(equipo='Pinpagos', modalidad=modalidad,
                                   banco='BANCO DEL TESORO', es_jornada=True)
            self.assertEqual((tesoro['monto_banco'], tesoro['monto_agente']), (7.5, 7.5))
            bancaribe = self.calcular(equipo='Pinpagos', modalidad=modalidad,
                banco='BANCARIBE', vendedor_agente='', vendedor_freelance='Persona ficticia / BANCARIBE')
            self.assertEqual((bancaribe['monto_banco'], bancaribe['monto_freelance']), (7.5, 7.5))
            for resultado in (normal, tesoro, bancaribe):
                self.assertFalse(resultado['requiere_revision'])
        tesoro = self.calcular(banco='BANCO DEL TESORO', es_jornada=True)
        self.assertEqual((tesoro['monto_banco'], tesoro['monto_agente'], tesoro['monto_total']),
                         (10, 28.4, 38.4))

    def test_motor_y_textos_visibles_canonicos(self):
        for canal in ('POSGUAYANA', 'POSGUAYANA 26'):
            datos = fila(CANAL=canal, ESTATUS='Pendiente', **{'ESTATUS CXC': 'AL CONTADO', '__ORIGEN': 'VENTAS_NUEVAS'})
            for par in p.PARES.values():
                for campo in par:
                    datos[campo] = None
            datos['MONTO TOTAL A PAGAR $'] = None
            resultado = r.aplicar_motor_comisiones(pd.DataFrame([datos]))
            self.assertEqual(resultado.at[0, 'MONTO COMISION AGENTE AUTORIZADO $'], 38.4)
            self.assertEqual(resultado.at[0, 'VENDEDOR AGENTE AUTORIZADO'], 'POSGUAYANA')
            self.assertEqual(resultado.at[0, 'CANAL'], 'POSGUAYANA')
        original = pd.DataFrame([fila(CANAL='POSGUAYANA 26', EQUIPO='Castle Dynamo',
                                     **{'VENDEDOR AGENTE AUTORIZADO': 'POSGUAYANA 26'})])
        esperado = original.copy(deep=True)
        esperado[['CANAL', 'VENDEDOR AGENTE AUTORIZADO']] = 'POSGUAYANA'
        pd.testing.assert_frame_equal(estandarizar_textos_salida(original), esperado)

    def test_separador_un_archivo_dos_aliases_y_estructura_identica(self):
        filas = [fila(CANAL=canal, **{'SERIAL': 'PRIMERO FICTICIO', 'SERIAL.1': '000123456789012'})
                 for canal in ('POSGUAYANA', 'POSGUAYANA 26')]
        resultado, libros = salidas(libro(filas))
        self.assertEqual(len(p.AGENTES), 12)
        self.assertEqual(resultado.archivos_generados, 1)
        self.assertEqual(list(libros), ['Pago de comisiones POSGUAYANA 18-09-2026.xlsx'])
        s = salida(libros, 'POSGUAYANA')
        self.assertEqual(next(iter(libros.values())).sheetnames, ['VENTAS'])
        self.assertEqual(len(valores(s)), 2)
        self.assertTrue(all(v['SERIAL'] == '000123456789012' for v in valores(s)))
        headers = [c.value for c in s[1]]
        self.assertEqual(len(headers), 30)
        self.assertEqual(headers.count('SERIAL'), 1)
        self.assertEqual([h for h in headers if h != 'SERIAL'],
                         [*p.BASE_SALIDA, *p.PARES['AGENTES AUTORIZADOS'], 'CON TX', 'ACCESS COMMERCE'])
        _, referencia = salidas(libro([dict(f, CANAL='GRANPRO') for f in filas]))
        otro = salida(referencia, 'GRANPRO')
        self.assertEqual(s.auto_filter.ref, otro.auto_filter.ref)
        self.assertEqual(s.dimensions, otro.dimensions)
        for fila_a, fila_b in zip(s, otro):
            for a, b in zip(fila_a, fila_b):
                self.assertEqual(a._style, b._style)
                if a.column != headers.index('CANAL') + 1:
                    self.assertEqual(a.value, b.value)
        for wb in [*libros.values(), *referencia.values()]:
            wb.close()
