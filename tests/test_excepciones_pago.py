import unittest
import pandas as pd
import procesamiento as p
from reglas_comisiones import calcular_comision, requiere_access_para_venta, aplicar_motor_comisiones
from test_revision_manual import resultados

class ExcepcionesTests(unittest.TestCase):
    def test_pinpagos_tarifa_independiente(self):
        for modalidad in ['COMODATO','AL CONTADO']:
            for fecha in [None,'2026-06-01','2026-09-01']:
                for canal in ['REGION CENTRO','GRANPRO']:
                    r=calcular_comision(equipo='Pinpagos',modalidad=modalidad,fecha=fecha,canal=canal,
                        vendedor_agente=canal,es_jornada=False,precios={'Pinpagos':999})
                    self.assertEqual(r['monto_total'],15)
                    self.assertEqual(r['monto_agente'],15)

    def test_pinpagos_repartos(self):
        for modalidad in ['COMODATO','AL CONTADO']:
            for banco,jornada in [('TESORO',True),('BANCARIBE',False)]:
                r=calcular_comision(equipo='Pinpagos',modalidad=modalidad,fecha=None,
                    banco=banco,es_jornada=jornada,canal='REGION CENTRO',
                    vendedor_agente='REGION CENTRO' if jornada else '',
                    vendedor_freelance='' if jornada else 'Persona A / Persona B',
                    conservar_vendedor_completo=not jornada)
                self.assertEqual(r['monto_total'],15)
                self.assertEqual(r['monto_banco'],7.5)
                self.assertEqual(r['monto_agente'] if jornada else r['monto_freelance'],7.5)

    def test_exenciones_access_solo_casos_confirmados(self):
        for banco,vendedor,contexto,exento in [('TESORO','Persona','JORNADA BANCO TESORO',True),
            ('TESORO','Persona','OFICINA',False),('BANCARIBE','Persona A / Persona B','OFICINA',True),
            ('BANCARIBE','Persona','OFICINA',False),('OTRO','Persona / BANCARIBE','OFICINA',False),
            ('BANCARIBE','Persona /','OFICINA',False)]:
            b=resultados()['final'].iloc[[1]].copy()
            b['BANCO']=banco;b['VENDEDOR']=vendedor;b['CANAL DE VENTA (JORNADA QUE PERTENECE)']=contexto
            b['MONTO TX SEPTIEMBRE']=2000;b['__MES_REPORTE']=9;b['__ANO_REPORTE']=2026
            b['OBSERVACION']=''
            self.assertEqual(requiere_access_para_venta(b.iloc[0]),not exento)
            comparados=[]
            for access in [set(),{'101'}]:
                o=p.recalcular_comisiones(b,pd.DataFrame(),access)
                esperado=exento or bool(access)
                self.assertEqual(o.iloc[0]['__APLICA_PAGO_CALCULADO'],'SI' if esperado else 'NO')
                self.assertEqual(o.iloc[0]['OBSERVACION'],'POR PAGAR' if esperado else 'NO POSEE REGISTRO DE OPERADORES ACCESS COMERCES')
                comparados.append(o[[c for c in o if c.startswith('MONTO COMISION') or c=='MONTO TOTAL A PAGAR $']])
            pd.testing.assert_frame_equal(comparados[0],comparados[1])

    def test_alias_real_r34_anterior(self):
        import io
        csv='PERTENENCIA;AFIPOS;SERIAL;MONTO_TRANS_BS_ACUM_MES;MONTO_TRANS_BS_ACUM_MES_1;ANO_PROCESO;MES_PROCESO\nCREDICARDPOS;1011;FICTICIO;300;1500;2026;9\n'
        r,_=p.procesar_csv_r34(io.BytesIO(csv.encode()),'ficticio.csv')
        lookup=p.crear_lookup_r34(r)
        self.assertEqual(lookup[('1011',2026,8)]['__MONTO_TX'],1500)
        self.assertEqual(lookup[('1011',2026,9)]['__MONTO_TX'],300)

    def test_pinpendiente_actualiza_total_pagado_preserva(self):
        b=resultados()['final'];b['EQUIPO']='Pinpagos';b['MONTO COMISION AGENTE AUTORIZADO $']=10;b['MONTO TOTAL A PAGAR $']=10
        b.loc[0,'ESTATUS']='PAGADO'
        o=aplicar_motor_comisiones(b)
        self.assertEqual(o.loc[0,'MONTO TOTAL A PAGAR $'],10)
        self.assertEqual(o.loc[1,'MONTO TOTAL A PAGAR $'],15)

    def test_pinpagos_total_conocido_reparto_ambiguo_no_se_inventa(self):
        b=resultados()['final'].iloc[[1]].copy();b['EQUIPO']='Pinpagos';b['BANCO']='TESORO'
        b['CANAL DE VENTA (JORNADA QUE PERTENECE)']='JORNADA SIN IDENTIFICAR'
        b['MONTO COMISION BANCO $']=10;b['MONTO COMISION AGENTE AUTORIZADO $']=10;b['MONTO TOTAL A PAGAR $']=20
        o=aplicar_motor_comisiones(b).iloc[0]
        self.assertEqual(o['MONTO TOTAL A PAGAR $'],15)
        self.assertTrue(pd.isna(o['MONTO COMISION BANCO $']))
        self.assertTrue(pd.isna(o['MONTO COMISION AGENTE AUTORIZADO $']))
        self.assertTrue(o['__REQUIERE_REVISION'])
        self.assertEqual(o['__MONTO_PENDIENTE_ASIGNACION'],15)
