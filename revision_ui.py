"""Presentación de los tres controles, sin reglas de comisión."""
import streamlit as st
from revision_manual import incidencias, aplicar_decision, tabla_comisiones


def mostrar_revision(resultados, precios):
    estado = st.session_state.setdefault('revision_nuevas', {})
    casos = incidencias(resultados['final'], resultados['r34'], estado.get('decisiones'))
    st.subheader('REVISIÓN MANUAL DE VENTAS NUEVAS')
    st.metric('Ventas nuevas de esta corrida', int(resultados['final']['__ORIGEN'].eq('VENTAS_NUEVAS').sum()))
    titulos = {1: 'Seriales repetidos', 2: 'Serial Comisiones vs R34', 3: 'Banco del Tesoro no Jornada'}
    vacios = {1: '✓ Seriales repetidos revisados: no hay casos pendientes en ventas nuevas.',
              2: '✓ Seriales R34 revisados: no hay diferencias pendientes en ventas nuevas.',
              3: '✓ Tesoro revisado: no hay ventas nuevas pendientes de validar como Jornada.'}
    for panel, paso in zip(st.columns(3), (1, 2, 3)):
        panel.metric(titulos[paso] + ' pendientes', len(casos[paso]))
    opciones = {1: {'Mantener / Validado': 'mantener', 'Marcar como DESINSTALADO': 'desinstalado',
                    'Eliminar fila NUEVA': 'eliminar'},
                2: {'Usar serial de Comisiones': 'comisiones', 'Usar serial del R34': 'r34'},
                3: {'Está correcto / Mantener como no Jornada': 'mantener', 'Cambiar a Jornada': 'jornada'}}
    for paso in (1, 2, 3):
        st.subheader(f'PASO {paso} DE 3 — {titulos[paso]}')
        if not casos[paso]:
            st.success(vacios[paso])
        for caso in casos[paso]:
            row_id = caso['row_id']
            with st.expander(f'Venta NUEVA — ID {row_id}', expanded=True):
                st.dataframe(tabla_comisiones(resultados['final'], caso.get('relacionados', [row_id])),
                             hide_index=True, use_container_width=True)
                if paso == 1:
                    st.caption('Las históricas se muestran como referencia. La acción solo afecta a la nueva indicada en este caso.')
                if paso == 2:
                    st.write('SERIAL ACTUAL EN COMISIONES:', caso['serial'] or '(vacío)')
                    st.write('SERIAL ENCONTRADO EN R34:', ', '.join(caso['opciones']))
                with st.form(f'revision_{paso}_{row_id}'):
                    opcion = st.selectbox('Decisión', list(opciones[paso]))
                    serial = None
                    if paso == 2:
                        serial = st.selectbox('Serial R34 a utilizar (si eliges R34)',
                                              ['Selecciona un serial'] + list(caso['opciones']))
                    enviar = st.form_submit_button('Aplicar decisión')
                if enviar:
                    try:
                        nuevo, estado_nuevo = aplicar_decision(resultados, estado, paso, row_id,
                            opciones[paso][opcion], serial=serial, precios=precios)
                    except ValueError as error:
                        st.error(str(error))
                    else:
                        st.session_state['resultados'] = nuevo
                        st.session_state['revision_nuevas'] = estado_nuevo
                        st.session_state.pop('excel_final_generado', None)
                        st.rerun()
    return any(casos.values())
