import streamlit as st
import pandas as pd
from utils.logistica import calcular_despacho_por_dia_y_semana

def render():
    st.header("📦 Módulo de Logística y Despachos")
    st.markdown("Cálculo automatizado de entregas, programación por rutas de despacho y control de tiempos.")

    # Validar si existen datos en la sesión
    if "df_clientes" not in st.session_state or st.session_state["df_clientes"].empty:
        st.warning("No hay datos cargados en el Cuadro Maestro. Por favor, cargue o registre información primero.")
        return

    df = st.session_state["df_clientes"].copy()

    # Asegurar que las columnas clave existan y recalcular dinámicamente el despacho para garantizar precisión
    if "Tiempo de Despacho" not in df.columns:
        df["Tiempo de Despacho"] = "24h"

    # Calcular columna de despacho automatizada para Semana 1 y Semana 2
    resultados_despacho_s1 = []
    resultados_despacho_s2 = []

    for _, row in df.iterrows():
        tiempo = row.get("Tiempo de Despacho", "24h")
        
        # Semana 1
        visita_s1 = row.get("Día de Visita Semana 1", "")
        desp_s1 = calcular_despacho_por_dia_y_semana(visita_s1, "Semana 1", tiempo)
        resultados_despacho_s1.append(desp_s1)

        # Semana 2
        visita_s2 = row.get("Día de Visita Semana 2", "")
        desp_s2 = calcular_despacho_por_dia_y_semana(visita_s2, "Semana 2", tiempo)
        resultados_despacho_s2.append(desp_s2)

    df["Despacho Programado Semana 1"] = resultados_despacho_s1
    df["Despacho Programado Semana 2"] = resultados_despacho_s2

    # --- FILTROS DE DESPACHO EN BARRA LATERAL ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Filtros de Despachos")
    
    # Filtrar por tiempo de despacho
    tiempos_disponibles = sorted(df["Tiempo de Despacho"].dropna().unique().tolist())
    tiempo_seleccionado = st.sidebar.selectbox("Filtrar por Tiempo", ["Todos"] + tiempos_disponibles)

    if tiempo_seleccionado != "Todos":
        df_view = df[df["Tiempo de Despacho"] == tiempo_seleccionado]
    else:
        df_view = df.copy()

    # --- MÉTRICAS DE LOGÍSTICA ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Entregas Programadas", len(df_view))
    with col2:
        entregas_24h = len(df_view[df_view["Tiempo de Despacho"].astype(str).str.contains("24", case=False, na=False)])
        st.metric("Despachos en 24h", entregas_24h)
    with col3:
        entregas_48h = len(df_view[df_view["Tiempo de Despacho"].astype(str).str.contains("48", case=False, na=False)])
        st.metric("Despachos en 48h", entregas_48h)

    st.markdown("---")

    # --- PESTAÑAS DE VISUALIZACIÓN ---
    tab_cronograma, tab_personal_despacho = st.tabs(["🚚 Cronograma de Despachos", "👥 Gestión de Despachadores"])

    with tab_cronograma:
        st.subheader("Matriz de Despachos Automáticos (Semana 1 y Semana 2)")
        st.markdown("El sistema calcula de forma inteligente el día exacto de entrega considerando las reglas de 24h/48h y saltos de semana.")

        if df_view.empty:
            st.info("No hay registros para mostrar con los filtros seleccionados.")
        else:
            columnas_despacho_mostrar = [
                "Nro", "Cliente", "Ubicacion", "Vendedor", "Tiempo de Despacho",
                "Día de Visita Semana 1", "Despacho Programado Semana 1",
                "Día de Visita Semana 2", "Despacho Programado Semana 2"
            ]
            cols_disp = [c for c in columnas_despacho_mostrar if c in df_view.columns]

            st.dataframe(df_view[cols_disp], use_container_width=True, hide_index=True)

            # Botón de exportación rápida o reporte
            col_exp1, col_exp2 = st.columns([1, 4])
            with col_exp1:
                # Convertir a CSV para descarga directa
                csv_data = df_view[cols_disp].to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar Cronograma CSV",
                    data=csv_data,
                    file_name="cronograma_despachos.csv",
                    mime="text/csv"
                )

    with tab_personal_despacho:
        st.subheader("Asignación de Personal de Despacho y Rutas")
        
        # Simular o manejar DataFrame de personal de despacho si estuviera en la sesión
        if "df_despachadores" not in st.session_state:
            st.session_state["df_despachadores"] = pd.DataFrame([
                {"Despachador": "Carlos Pérez", "Ruta de Despacho": "Ruta D-01", "Zona": "Hatillo / Baruta"},
                {"Despachador": "Luis Rodríguez", "Ruta de Despacho": "Ruta D-02", "Zona": "Libertador / Centro"}
            ])

        df_d_edit = st.data_editor(
            st.session_state["df_despachadores"],
            num_rows="dynamic",
            use_container_width=True,
            key="editor_personal_despacho"
        )

        if st.button("💾 Guardar Personal de Despachos"):
            st.session_state["df_despachadores"] = df_d_edit
            st.toast("¡Personal de despacho actualizado con éxito!", icon="✅")
