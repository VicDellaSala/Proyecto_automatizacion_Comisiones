"""Carga inicial opcional y resumen de Jornada por chats."""
import streamlit as st


def invalidar_resultados_chats():
    for clave in ('resultados', 'revision_nuevas', 'excel_final_generado'):
        st.session_state.pop(clave, None)


def cargar_chats():
    archivos = st.file_uploader('Chats de Jornada Tesoro (opcional: TXT o ZIP)',
        type=['txt', 'zip'], accept_multiple_files=True, key='chats_jornada_archivos',
        on_change=invalidar_resultados_chats)
    st.caption('Carga todos los chats relevantes. Al iniciar el procesamiento: afiliado + terminal '
               'en los mensajes = Jornada; ausentes = No Jornada. Los casos ambiguos o con '
               'reparto incompleto quedan en revisión manual sin detener los demás.')
    return archivos


def mostrar_chats(resultados, estado, precios):
    resumen = resultados.get('resumen_chats')
    if resumen is None:
        return False
    with st.expander('Resultado de los chats cargados al inicio', expanded=True):
        if not resumen:
            st.info('No había ventas nuevas pendientes de Jornada para clasificar.')
            return False
        st.write(' · '.join(f'{d}: {sum(p["Resultado"] == d for p in resumen)}'
                           for d in ('Jornada', 'No Jornada', 'Revisión manual')))
        st.dataframe(resumen, hide_index=True)
        if any(p['Resultado'] == 'Revisión manual' for p in resumen):
            st.warning('Los casos pendientes se conservaron sin cambios. Puedes resolverlos abajo; '
                       'las demás decisiones ya se aplicaron.')
    return False
