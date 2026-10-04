"""Presentación del Paso 4; no modifica los controles existentes."""
import streamlit as st
import pandas as pd
from revision_terminales import casos_terminales, preparar_cambio_terminal, aplicar_cambio_terminal


def mostrar_terminales(resultados, estado, precios):
    st.subheader('PASO 4 DE 4 — Terminal Ventas vs Comisiones')
    st.caption('Los históricos son referencia protegida. Se usa el serial vigente tras el Paso 2. Una diferencia no demuestra que sea la misma venta ni un correctivo.')
    casos = casos_terminales(resultados, estado)
    st.metric('Terminales por revisar', len(casos))
    if not casos:
        st.success('No hay diferencias de terminal pendientes con la evidencia disponible para las ventas nuevas.')
    seleccion_sin_aplicar = False
    for caso in casos:
        key = f"terminales_{caso['row_id']}_{caso['firma']}"
        with st.expander(f"Venta NUEVA — ID {caso['row_id']}", expanded=True):
            tabla = pd.DataFrame([caso['actual'], *caso['historicas'], *caso['r34']])
            tabla['Origen'] = tabla['Origen'].replace({'VENTAS_NUEVAS': 'VENTAS — NUEVA (SERIAL VIGENTE)',
                                                       'COMISIONES': 'COMISIONES — HISTÓRICA'})
            st.dataframe(tabla.astype('string').fillna(''), hide_index=True)
            if not caso['serial_coincide'] and caso['historicas']:
                st.warning('También difiere el serial. Estas son posibles coincidencias del afiliado; confirme la misma venta antes de corregir.')
            accion = st.selectbox('Decisión de terminal', ['Pendiente / Sin cambios',
                'Mantener terminal actual / Son registros distintos', 'Revisar otra terminal'], key=key)
            if accion == 'Pendiente / Sin cambios':
                continue
            seleccion_sin_aplicar = True
            st.session_state.pop('excel_final_generado', None)
            terminal, misma, conservar = None, False, None
            mantener = accion.startswith('Mantener')
            if not mantener:
                terminal = st.selectbox('Terminal respaldada por la evidencia',
                    [None] + [t for t in caso['terminales'] if t != caso['actual']['TERMINAL']], key=key+'_terminal')
                misma = st.checkbox('Confirmo que corresponde a la misma venta/equipo', key=key+'_misma')
                coincidencias = [h for h in caso['historicas'] if h['TERMINAL'] == terminal]
                if coincidencias:
                    st.warning('Esta identidad ya existe. No se sobrescribirá el histórico. Puede conservarlo íntegro y retirar explícitamente la fila nueva.')
                    conservar = st.selectbox('Fila histórica a conservar (retirar la incorporación nueva)',
                        [None] + [h['ID'] for h in coincidencias], key=key+'_conservar')
                if terminal is None or not misma:
                    continue
            try:
                vista = preparar_cambio_terminal(resultados, estado, caso['row_id'], terminal,
                    mantener=mantener, misma_venta=misma, conservar_existente=conservar, precios=precios)
            except ValueError as error:
                st.warning(str(error))
                continue
            if vista['cambios']:
                st.write('Cambios que se aplicarán únicamente al confirmar:')
                st.dataframe(vista['cambios'], hide_index=True)
            confirmar = st.checkbox('He revisado y confirmo estos cambios',
                key=f'{key}_confirmar_{vista["firma"]}_{terminal}_{conservar}_{mantener}')
            if st.button('Aplicar decisión de terminal', key=key+'_aplicar', disabled=not confirmar):
                nuevo, nuevo_estado = aplicar_cambio_terminal(resultados, estado, vista, precios)
                st.session_state['resultados'] = nuevo
                st.session_state['revision_nuevas'] = nuevo_estado
                st.session_state.pop('excel_final_generado', None)
                st.rerun()
    return seleccion_sin_aplicar
