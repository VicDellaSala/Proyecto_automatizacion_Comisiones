"""Carga opcional de evidencia para el Paso 3."""
import hashlib
import pickle
import streamlit as st

from jornadas_chats import analizar_chats, proponer_jornadas, aplicar_chats


def mostrar_chats(resultados, estado, precios):
    with st.expander('Resolver Jornada con chats de WhatsApp', expanded=False):
        st.caption('Opcional. Carga todos los chats relevantes: afiliado + terminal presentes = Jornada; '
                   'ausentes = No Jornada. Los mensajes ambiguos quedan para revisión manual. '
                   'Solo se aplican decisiones a ventas nuevas pendientes del Paso 3.')
        archivos = st.file_uploader('Chats de WhatsApp (TXT o ZIP)', type=['txt', 'zip'],
                                    accept_multiple_files=True, key='chats_jornada_archivos')
        if not archivos:
            return False
        entradas = [(a.name, a.getvalue()) for a in archivos]
        try:
            evidencia = analizar_chats(entradas)
            propuestas = proponer_jornadas(resultados, estado, evidencia)
        except ValueError as error:
            st.error(str(error))
            return False
        if not propuestas:
            st.info('No hay casos pendientes del Paso 3 para clasificar.')
            return False
        st.dataframe([{'ID venta nueva': p['row_id'], 'Decisión propuesta': p['decision']}
                      for p in propuestas], hide_index=True)
        st.write(' · '.join(f'{d}: {sum(p["decision"] == d for p in propuestas)}'
                           for d in ('Jornada', 'No Jornada', 'Revisión manual')))
        firma = hashlib.sha256(pickle.dumps((entradas, resultados['final'], resultados['r34'],
                                            estado, precios))).hexdigest()
        confirmado = st.checkbox('Revisé el resumen y cargué todos los chats relevantes',
                                  key='confirmar_chats_'+firma)
        if confirmado:
            st.session_state.pop('excel_final_generado', None)
        aplicables = any(p['decision'] != 'Revisión manual' for p in propuestas)
        if st.button('Aplicar decisiones de los chats', disabled=not confirmado or not aplicables,
                     key='aplicar_chats_jornada'):
            try:
                with st.spinner('Aplicando decisiones y validando repartos...'):
                    nuevo, nuevo_estado = aplicar_chats(resultados, estado, evidencia, precios)
            except ValueError as error:
                st.error('No se aplicó el lote. Resuelve el caso en revisión manual y vuelve a intentar. ' + str(error))
            else:
                st.session_state['resultados'] = nuevo
                st.session_state['revision_nuevas'] = nuevo_estado
                st.session_state.pop('excel_final_generado', None)
                st.rerun()
        return confirmado and aplicables
