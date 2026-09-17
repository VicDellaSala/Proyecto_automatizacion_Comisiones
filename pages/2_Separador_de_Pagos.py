"""Página independiente: recibe únicamente el Excel final de Comisiones."""
import hashlib

import streamlit as st

from separador_pagos import AVISO_REGIONAL, ErrorSeparador, GRUPOS, separar_pagos, viernes_misma_semana


st.set_page_config(page_title='Separador de Pagos', page_icon='📁', layout='wide')
st.sidebar.page_link('app.py', label='Procesamiento de Comisiones')
st.sidebar.page_link('pages/2_Separador_de_Pagos.py', label='Separador de Pagos')
st.title('Separador de Pagos')
st.write('Sube el Excel final de Comisiones. Se separan todas las filas que correspondan a cada beneficiario, sin filtrar por fechas ni estatus.')
st.caption('Se conservan los valores finales y sus formatos; no se recalculan comisiones. TASA y BS. quedan vacíos.')
fecha = viernes_misma_semana()
st.info(f'Fecha para los nombres: {fecha:%d-%m-%Y}. Solo identifica los archivos; no filtra las ventas. Sábado y domingo se usa el viernes anterior.')
archivo = st.file_uploader('Excel final de Comisiones — hoja VENTAS', type=['xlsx'], key='pagos_archivo')
if archivo is None:
    st.session_state.pop('pagos_resultado', None)
else:
    datos = archivo.getvalue()
    clave = (hashlib.sha256(datos).hexdigest(), fecha.isoformat(), 'columnas-permitidas-29')
    guardado = st.session_state.get('pagos_resultado')
    if guardado and guardado[0] != clave:
        st.session_state.pop('pagos_resultado', None)
    if st.button('Generar archivos de pago', type='primary'):
        st.session_state.pop('pagos_resultado', None)
        try:
            with st.spinner('Separando beneficiarios y conservando formatos…'):
                resultado = separar_pagos(datos)
            st.session_state['pagos_resultado'] = (clave, resultado)
        except ErrorSeparador as error:
            st.error(str(error))
        except Exception:
            st.error('No se pudo generar el ZIP. Revise la estructura del archivo XLSX.')
    guardado = st.session_state.get('pagos_resultado')
    if guardado:
        resultado = guardado[1]
        for grupo in GRUPOS:
            st.subheader(grupo)
            st.dataframe([{'Beneficiario': r['Beneficiario'], 'Registros': r['Registros']}
                          for r in resultado.resumen if r['Grupo'] == grupo], hide_index=True, use_container_width=True)
        for motivo, cantidad in resultado.advertencias.items():
            st.warning(f'{motivo}: {cantidad}. Revise estos casos antes de distribuir los pagos.')
            if motivo == AVISO_REGIONAL and resultado.casos_regionales_por_revisar:
                st.subheader('CASOS REGIONALES POR REVISAR')
                st.dataframe(resultado.casos_regionales_por_revisar, hide_index=True, use_container_width=True)
        st.metric('Total de archivos generados', resultado.archivos_generados)
        if resultado.archivos_generados:
            st.download_button('Descargar todos los pagos (ZIP)', resultado.contenido_zip,
                               file_name=resultado.nombre_zip, mime='application/zip')
        else:
            st.info('No hay filas para los beneficiarios configurados. No se generan Excel vacíos.')
