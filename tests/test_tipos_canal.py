import unittest
from unittest.mock import patch
import pandas as pd

from test_revision_manual import resultados
from revision_manual import _revalidar, aplicar_decision
from reglas_comisiones import normalizar_canal, aplicar_motor_comisiones


class TiposCanalTests(unittest.TestCase):
    def test_fecha_y_monto_mixto_preservan_historico(self):
        r=resultados();df=r['final']
        df['FECHA DE ARCHIVO']=pd.to_datetime(['2026-01-01',None])
        df['MONTO COMISION BANCO $']=pd.Series(['=1+1',None],dtype=object)
        def recalcular(parte,*args,**kwargs):
            parte['FECHA DE ARCHIVO']='2026-08-01'
            parte['MONTO COMISION BANCO $']=10
            return parte
        with patch('revision_manual.recalcular_comisiones',side_effect=recalcular):
            out=_revalidar(df,{1001},r,None,{})
        self.assertEqual(out.loc[0,'MONTO COMISION BANCO $'],'=1+1')
        self.assertEqual(out.loc[1,'MONTO COMISION BANCO $'],10)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(out['FECHA DE ARCHIVO']))
        self.assertEqual(out.loc[0,'FECHA DE ARCHIVO'],df.loc[0,'FECHA DE ARCHIVO'])

    def test_revalidar_asigna_tipos_sin_tocar_otras_filas(self):
        r=resultados();df=r['final']
        df['__MONTO_TX_R34']=[11.0,12.0]
        df['VENDEDOR BANCO']=float('nan')
        df['MONTO COMISION BANCO $']=float('nan')
        def recalcular(parte,*args,**kwargs):
            self.assertEqual(list(parte['__ROW_ID']),[1001])
            parte['__MONTO_TX_R34']=pd.Series([None],index=parte.index,dtype=object)
            parte['VENDEDOR BANCO']='BANCO DEL TESORO'
            parte['MONTO COMISION BANCO $']=10.0
            parte['MONTO TOTAL A PAGAR $']=25.0
            return parte
        with patch('revision_manual.recalcular_comisiones',side_effect=recalcular):
            out=_revalidar(df,{1001},r,None,{})
        self.assertEqual(out.loc[1,'VENDEDOR BANCO'],'BANCO DEL TESORO')
        self.assertEqual(out.loc[1,'MONTO COMISION BANCO $'],10)
        self.assertEqual(out.loc[1,'MONTO TOTAL A PAGAR $'],25)
        self.assertTrue(pd.isna(out.loc[1,'__MONTO_TX_R34']))
        self.assertTrue(pd.api.types.is_numeric_dtype(out['__MONTO_TX_R34']))
        self.assertTrue(pd.api.types.is_numeric_dtype(out['MONTO COMISION BANCO $']))
        pd.testing.assert_frame_equal(out.iloc[:1],df.iloc[:1],check_dtype=False)

    def test_oficina_jornada_con_vendedores_float_vacios(self):
        r=resultados();r['final']['BANCO']='TESORO'
        for c in ['VENDEDOR BANCO','VENDEDOR / FREELANCE']:
            r['final'][c]=float('nan')
        r['final']['__MONTO_TX_R34']=[2000.0,float('nan')]
        out,_=aplicar_decision(r,{},3,1001,'jornada')
        fila=out['final'].iloc[1]
        self.assertEqual(fila['VENDEDOR BANCO'],'BANCO DEL TESORO')
        self.assertEqual(fila['MONTO COMISION BANCO $'],10)
        self.assertEqual(fila['MONTO TOTAL A PAGAR $'],20)
        self.assertTrue(pd.api.types.is_numeric_dtype(out['final']['MONTO TOTAL A PAGAR $']))

    def test_canal_canonico_antes_motor_solo_salida_nueva(self):
        for valor,canon,total in [('OCCIDENTE','REGION OCCIDENTE',25),('REGION OCCIDENTE','REGION OCCIDENTE',25),
                ('ORIENTE','REGION ORIENTE',25),('REGION ORIENTE','REGION ORIENTE',25),
                ('CENTRO','REGION CENTRO',25),('REGION CENTRO','REGION CENTRO',25),
                (' centro  tipo ii ','CENTRO TIPO II',50),('venepos','VENEPOS',38.4)]:
            self.assertEqual(normalizar_canal(valor),canon)
            r=resultados();df=r['final'];df['CANAL']=valor;df['ESTATUS CXC']='AL CONTADO'
            df['VENDEDOR AGENTE AUTORIZADO']=valor
            df.loc[1,'MONTO COMISION AGENTE AUTORIZADO $']=None
            df.loc[1,'MONTO TOTAL A PAGAR $']=None
            out=aplicar_motor_comisiones(df)
            self.assertEqual(out.loc[1,'CANAL'],canon)
            self.assertEqual(out.loc[1,'VENDEDOR AGENTE AUTORIZADO'],canon)
            self.assertEqual(out.loc[1,'MONTO TOTAL A PAGAR $'],total)
            self.assertEqual(out.loc[0,'CANAL'],valor)
            self.assertEqual(out.loc[0,'VENDEDOR AGENTE AUTORIZADO'],valor)
            pd.testing.assert_series_equal(out['CANAL DE VENTA (JORNADA QUE PERTENECE)'],df['CANAL DE VENTA (JORNADA QUE PERTENECE)'])
        self.assertEqual(normalizar_canal('CENTRO ESPECIAL'),'CENTRO ESPECIAL')

    def test_credicardpos_conserva_freelancer(self):
        r=resultados();df=r['final'];df.loc[1,'CANAL']=' credicardpos '
        df.loc[1,'VENDEDOR AGENTE AUTORIZADO']=''
        df.loc[1,'MONTO COMISION AGENTE AUTORIZADO $']=None
        df.loc[1,'MONTO TOTAL A PAGAR $']=None
        out=aplicar_motor_comisiones(df)
        self.assertEqual(out.loc[1,'CANAL'],'CREDICARDPOS')
        self.assertEqual(out.loc[1,'MONTO COMISION VENDEDOR/FREELANCE $'],10)
        self.assertEqual(out.loc[1,'VENDEDOR AGENTE AUTORIZADO'],'')
