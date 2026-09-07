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
        panel.metric(titulos[paso] + ' para revisar (opcional)', len(casos[paso]))
    opciones = {1: {'Mantener / Validado': 'mantener', 'Marcar como DESINSTALADO': 'desinstalado',
                    'Eliminar fila': 'eliminar'},
                2: {'Usar serial de Comisiones': 'comisiones', 'Usar serial del R34': 'r34'},
                3: {'Está correcto / Mantener como no Jornada': 'mantener', 'Cambiar a Jornada': 'jornada'}}
    cambios_sin_aplicar = False
    for paso in (1, 2, 3):
        grupos_mostrados = set()
        st.subheader(f'PASO {paso} DE 3 — {titulos[paso]}')
        if not casos[paso]:
            st.success(vacios[paso])
        for caso in casos[paso]:
            if paso == 1:
                grupo = tuple(caso['relacionados'])
                if grupo in grupos_mostrados:
                    continue
                grupos_mostrados.add(grupo)
            row_id = caso['row_id']
            with st.expander(f'Venta NUEVA — ID {row_id}', expanded=True):
                st.dataframe(tabla_comisiones(resultados['final'], caso.get('relacionados', [row_id])),
                             hide_index=True, use_container_width=True)
                if paso == 1:
                    st.caption('Selecciona expresamente la fila histórica o nueva que quieres modificar.')
                if paso == 2:
                    st.write('SERIAL ACTUAL EN COMISIONES:', caso['serial'] or '(vacío)')
                    st.write('SERIAL ENCONTRADO EN R34:', ', '.join(caso['opciones']))
                    if caso.get('sin_fuente_confiable'):
                        st.warning('R34 contiene un registro sin fuente de serial exacta y confiable. Se conserva el serial de Comisiones por defecto.')
                key = f'revision_{paso}_{row_id}'
                opcion = st.selectbox('Decisión', list(opciones[paso]), key=key)
                accion = opciones[paso][opcion]
                if accion in {'mantener', 'comisiones'}:
                    continue
                cambios_sin_aplicar = True
                st.session_state.pop('excel_final_generado', None)
                serial, elegida = None, None
                if paso == 1:
                    origenes = resultados['final'].set_index('__ROW_ID')['__ORIGEN'].to_dict()
                    elegida = st.selectbox('¿Qué fila quieres marcar como DESINSTALADO?' if accion == 'desinstalado'
                                          else '¿Qué fila quieres eliminar?',
                        [None] + caso['relacionados'], key=key+'_fila',
                        format_func=lambda i: 'Selecciona una fila' if i is None else
                            f"ID {i} — {'NUEVA' if origenes[i] == 'VENTAS_NUEVAS' else 'HISTÓRICA'}")
                if paso == 2:
                    serial = st.selectbox('Serial R34 a utilizar',
                        [None] + list(caso['opciones']), key=key+'_serial',
                        format_func=lambda v: 'Selecciona un serial' if v is None else v)
                enviar = st.button('Aplicar cambio', key=key+'_aplicar',
                                   disabled=(paso == 1 and elegida is None) or (paso == 2 and serial is None))
                if enviar:
                    try:
                        nuevo, estado_nuevo = aplicar_decision(resultados, estado, paso, row_id,
                            opciones[paso][opcion], serial=serial, precios=precios, fila_elegida=elegida)
                    except ValueError as error:
                        st.error(str(error))
                    else:
                        st.session_state['resultados'] = nuevo
                        st.session_state['revision_nuevas'] = estado_nuevo
                        st.session_state.pop('excel_final_generado', None)
                        st.rerun()
    return cambios_sin_aplicar
