import streamlit as st
import pandas as pd

def render():
    st.header("🚚 Módulo de Gestión y Seguimiento de Vendedores")
    st.markdown("Consulta y filtrado de rutas comerciales, días de visita por semana y control de pedidos.")

    # Validar si existen datos en la sesión
    if "df_clientes" not in st.session_state or st.session_state["df_clientes"].empty:
        st.warning("No hay datos cargados en el Cuadro Maestro. Por favor, cargue o registre información primero.")
        return

    df = st.session_state["df_clientes"].copy()
    df_vendedores = st.session_state["df_vendedores"].copy()

    # --- BARRA LATERAL DE FILTROS ESPECÍFICOS ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Filtros de Vendedores")

    # Lista única de vendedores disponibles
    vendedores_disponibles = sorted(df["Vendedor"].dropna().unique().tolist())
    vendedor_seleccionado = st.sidebar.selectbox("Seleccione Vendedor", ["Todos"] + vendedores_disponibles)

    # Filtrar rutas según el vendedor escogido
    if vendedor_seleccionado != "Todos":
        df_filtrado_rutas = df[df["Vendedor"] == vendedor_seleccionado]
    else:
        df_filtrado_rutas = df

    rutas_disponibles = sorted(df_filtrado_rutas["Nro de Ruta (Ventas)"].dropna().unique().tolist())
    ruta_seleccionada = st.sidebar.selectbox("Seleccione Ruta", ["Todas"] + rutas_disponibles)

    # Aplicar filtros al DataFrame principal de la vista
    df_view = df.copy()
    if vendedor_seleccionado != "Todos":
        df_view = df_view[df_view["Vendedor"] == vendedor_seleccionado]
    if ruta_seleccionada != "Todas":
        df_view = df_view[df_view["Nro de Ruta (Ventas)"] == ruta_seleccionada]

    # --- MÉTRICAS RÁPIDAS ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Clientes en Ruta", len(df_view))
    with col2:
        st.metric("Vendedor Activo", vendedor_seleccionado if vendedor_seleccionado != "Todos" else "Varios")
    with col3:
        st.metric("Ruta Seleccionada", ruta_seleccionada if ruta_seleccionada != "Todas" else "Todas")

    st.markdown("---")

    # --- PESTAÑAS DE VISTA ---
    tab_tabla, tab_gestion_personal = st.tabs(["📋 Listado y Visitas", "👥 Gestión de Personal y Rutas"])

    with tab_tabla:
        st.subheader("Planificación de Visitas y Historial de Pedidos")
        
        if df_view.empty:
            st.info("No se encontraron registros con los filtros seleccionados.")
        else:
            # Seleccionar columnas clave para mostrar de forma limpia
            columnas_mostrar = [
                "Nro", "Vendedor", "Nro de Ruta (Ventas)", "Cliente", "Ubicacion",
                "Semana 1", "Semana 2", "Día de Visita Semana 1", "Día de Visita Semana 2",
                "Pedido_S1", "Pedido_S2", "Pedido_S3", "Pedido_S4"
            ]
            
            # Asegurar que existan las columnas en el df
            cols_disponibles = [c for c in columnas_mostrar if c in df_view.columns]
            
            # Editor de datos interactivo para actualizar estados de visitas o notas rápidas de pedidos
            df_editado = st.data_editor(
                df_view[cols_disponibles],
                num_rows="fixed",
                use_container_width=True,
                key="editor_vendedores_tabla"
            )

            # Botón para sincronizar cambios realizados en la vista hacia la base de datos general
            if st.button("💾 Guardar Cambios de Pedidos/Visitas", type="primary"):
                # Actualizar el dataframe global con los cambios hechos en el editor
                for idx, row in df_editado.iterrows():
                    original_idx = df.index[df["Nro"] == row["Nro"]]
                    if not original_idx.empty:
                        for col in cols_disponibles:
                            df.at[original_idx[0], col] = row[col]
                
                st.session_state["df_clientes"] = df
                
                # Guardar automáticamente en Supabase
                from services.supabase_service import guardar_todo_en_supabase
                guardar_todo_en_supabase(
                    st.session_state["df_clientes"],
                    st.session_state["df_vendedores"],
                    st.session_state["df_mercaderistas"]
                )
                st.rerun()

    with tab_gestion_personal:
        st.subheader("Asignación de Vendedores y sus Rutas")
        st.markdown("Agregue o modifique el personal de ventas autorizado.")

        df_v_edit = st.data_editor(
            df_vendedores,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_personal_vendedores"
        )

        if st.button("💾 Guardar Personal de Ventas"):
            st.session_state["df_vendedores"] = df_v_edit
            from services.supabase_service import guardar_todo_en_supabase
            guardar_todo_en_supabase(
                st.session_state["df_clientes"],
                st.session_state["df_vendedores"],
                st.session_state["df_mercaderistas"]
            )
            st.rerun()
