import streamlit as st
import pandas as pd
import json
import google.generativeai as genai
from services.supabase_service import guardar_todo_en_supabase, COLUMNITAS_CLIENTES

def render():
    st.header("📊 Cuadro Maestro - Gestión General de Clientes y Rutas")
    st.markdown("Administre la base de datos central, realice cargas masivas desde Excel o procese documentos PDF con Inteligencia Artificial.")

    # Validar si existen datos en la sesión
    if "df_clientes" not in st.session_state:
        st.session_state["df_clientes"] = pd.DataFrame(columns=COLUMNITAS_CLIENTES)

    df = st.session_state["df_clientes"].copy()

    # --- ACCIONES SUPERIORES: CARGA MASIVA Y CONFIGURACIÓN DE IA ---
    with st.expander("📂 Opciones de Carga Masiva y Procesamiento Inteligente (Excel / PDF)", expanded=False):
        col_excel, col_pdf = st.columns(2)

        with col_excel:
            st.subheader("Cargar Base de Datos Excel")
            archivo_excel = st.file_uploader("Subir archivo .xlsx", type=["xlsx"], key="upl_excel_maestro")
            if archivo_excel is not None:
                try:
                    df_excel = pd.read_excel(archivo_excel)
                    st.success(f"¡Excel cargado con éxito! Filas encontradas: {len(df_excel)}")
                    if st.button("Reemplazar Cuadro Maestro con este Excel"):
                        # Mapear columnas si es necesario o asegurar columnas clave
                        for col in COLUMNITAS_CLIENTES:
                            if col not in df_excel.columns:
                                df_excel[col] = ""
                        st.session_state["df_clientes"] = df_excel[COLUMNITAS_CLIENTES]
                        guardar_todo_en_supabase(
                            st.session_state["df_clientes"],
                            st.session_state["df_vendedores"],
                            st.session_state["df_mercaderistas"]
                        )
                        st.rerun()
                except Exception as e:
                    st.error(f"Error al leer el Excel: {e}")

        with col_pdf:
            st.subheader("Procesar PDF con Gemini AI")
            api_key_input = st.text_input("Clave API de Gemini (opcional si está en secrets)", type="password", key="gemini_key_input")
            archivo_pdf = st.file_uploader("Subir reporte o documento PDF", type=["pdf"], key="upl_pdf_maestro")
            
            if st.button("🤖 Procesar PDF con IA", type="primary") and archivo_pdf:
                # Determinar API Key
                api_key = api_key_input if api_key_input else st.secrets.get("GEMINI_API_KEY", "")
                if not api_key:
                    st.error("Por favor, configure su API Key de Gemini en los secrets o en el campo de texto.")
                else:
                    try:
                        genai.configure(api_key=api_key)
                        with st.spinner("Leyendo y extrayendo información estructurada con IA..."):
                            # Guardar temporalmente el PDF subido
                            bytes_pdf = archivo_pdf.read()
                            
                            # Usar gemini-2.5-flash para procesar el documento
                            model = genai.GenerativeModel("gemini-2.5-flash")
                            prompt = (
                                "Analiza este documento PDF de rutas o clientes y extrae la información en un formato JSON "
                                "que contenga una lista de objetos con las siguientes llaves exactas: "
                                "Nro, Vendedor, Nro de Ruta (Ventas), Cliente, Ubicacion, Semana 1, Semana 2, "
                                "Día de Visita Semana 1, Día de Visita Semana 2, Tiempo de Despacho, Mercaderia, Mercaderista. "
                                "Devuelve estrictamente el JSON válido sin texto adicional."
                            )
                            
                            # Subir archivo mediante la API genai o pasar bytes si soporta
                            # Para simplificar en Streamlit, usamos parte de contenido multimodal
                            response = model.generate_content([
                                prompt,
                                {"mime_type": "application/pdf", "data": bytes_pdf}
                            ])
                            
                            texto_respuesta = response.text.strip()
                            if "```json" in texto_respuesta:
                                texto_respuesta = texto_respuesta.split("```json")[1].split("```")[0].strip()
                            elif "```" in texto_respuesta:
                                texto_respuesta = texto_respuesta.split("```")[1].split("```")[0].strip()
                            
                            datos_extraidos = json.loads(texto_respuesta)
                            df_nuevo_ia = pd.DataFrame(datos_extraidos)
                            
                            # Fusionar con el dataframe actual
                            st.session_state["df_clientes"] = pd.concat([df, df_nuevo_ia], ignore_index=True)
                            guardar_todo_en_supabase(
                                st.session_state["df_clientes"],
                                st.session_state["df_vendedores"],
                                st.session_state["df_mercaderistas"]
                            )
                            st.success("¡Documento procesado e integrado exitosamente al Cuadro Maestro!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error procesando el PDF con IA: {e}")

    st.markdown("---")

    # --- FILTROS RÁPIDOS DE BÚSQUEDA EN EL CUADRO MAESTRO ---
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        busqueda_cliente = st.text_input("🔍 Buscar por Cliente o Ubicación", "")
    with col_f2:
        vendedores_filtro = ["Todos"] + sorted(df["Vendedor"].dropna().unique().tolist()) if "Vendedor" in df.columns else ["Todos"]
        sel_v = st.selectbox("Filtrar por Vendedor", vendedores_filtro)
    with col_f3:
        st.metric("Total Registros Maestros", len(df))

    df_filtrado = df.copy()
    if busqueda_cliente:
        mask = df_filtrado.astype(str).apply(lambda x: x.str.contains(busqueda_cliente, case=False, na=False)).any(axis=1)
        df_filtrado = df_filtrado[mask]
    if sel_v != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Vendedor"] == sel_v]

    st.subheader("Edición Directa de Datos Maestros")
    st.markdown("Modifique celdas directamente en la tabla o agregue nuevas filas según sea necesario.")

    # Asegurar que todas las columnas existan
    for col in COLUMNITAS_CLIENTES:
        if col not in df_filtrado.columns:
            df_filtrado[col] = ""

    df_editado = st.data_editor(
        df_filtrado[COLUMNITAS_CLIENTES],
        num_rows="dynamic",
        use_container_width=True,
        key="editor_cuadro_maestro_general"
    )

    # Botón principal de guardado
    col_b1, col_b2 = st.columns([1, 4])
    with col_b1:
        if st.button("💾 Guardar Cambios Maestro", type="primary"):
            # Actualizar el dataframe global combinando los cambios del editor
            st.session_state["df_clientes"] = df_editado
            guardar_todo_en_supabase(
                st.session_state["df_clientes"],
                st.session_state["df_vendedores"],
                st.session_state["df_mercaderistas"]
            )
            st.rerun()
