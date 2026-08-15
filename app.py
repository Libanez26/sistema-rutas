import streamlit as st
import pandas as pd
import google.generativeai as genai
import json

# Configuración inicial de la página
st.set_page_config(page_title="Gestión de Rutas - Lácteos Ananké", layout="wide")

st.title("🚚 Sistema Integral de Gestión de Rutas - Lácteos Ananké")

# Configurar API de Gemini
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Error: La API Key de Gemini no está configurada en los Secrets de Streamlit.")

# ==========================================
# 1. ESTADOS DE SESIÓN (CATÁLOGOS Y BASE DE DATOS)
# ==========================================

# Catálogo de Vendedores y sus Rutas
if "df_vendedores" not in st.session_state:
    st.session_state["df_vendedores"] = pd.DataFrame([
        {"Vendedor": "Dairo Bello", "Nro de Ruta": "Ruta 01"},
        {"Vendedor": "Jhony Moreno", "Nro de Ruta": "Ruta 02"}
    ])

# Catálogo de Mercaderistas y sus Rutas
if "df_mercaderistas" not in st.session_state:
    st.session_state["df_mercaderistas"] = pd.DataFrame([
        {"Mercaderista": "Carlos Pérez", "Nro de Ruta": "Ruta M-01"},
        {"Mercaderista": "Ana Gómez", "Nro de Ruta": "Ruta M-02"}
    ])

# Encabezados exactos solicitados para la Base de Datos de Clientes
columnas_clientes = [
    "Nro",
    "Vendedor",
    "Nro de Ruta (Ventas)",
    "Cliente",
    "Ubicacion",
    "Semana 1",
    "Semana 2",
    "Día de Visita Semana 1",
    "Día de Visita Semana 2",
    "Tiempo de Despacho",
    "Mercaderia",
    "Mercaderista",
    "Nro de Ruta (Mercaderia)",
    "Tiempo de Mercaderia",
    "Día de Mercaderia Semana 1",
    "Día de Mercaderia Semana 2"
]

if "df_clientes" not in st.session_state:
    st.session_state["df_clientes"] = pd.DataFrame(columns=columnas_clientes)

# ==========================================
# 2. NAVEGACIÓN POR PESTAÑAS
# ==========================================
tab_db, tab_vendedores, tab_mercaderistas = st.tabs([
    "📋 Base de Datos de Clientes", 
    "👥 Gestión de Vendedores", 
    "🛒 Gestión de Mercaderistas"
])

# ==========================================
# PESTAÑA 1: BASE DE DATOS DE CLIENTES
# ==========================================
with tab_db:
    st.header("Base de Datos General de Clientes y Rutas")
    st.markdown("Sube un archivo PDF o Excel con las rutas. La Inteligencia Artificial se encargará de extraer y ordenar los datos automáticamente bajo los parámetros establecidos.")

    uploaded_file = st.file_uploader("Cargar archivo (PDF o Excel)", type=["pdf", "xlsx"])
    
    if uploaded_file and st.button("🤖 Procesar y Organizar con IA"):
        with st.spinner("Leyendo documento y estructurando datos..."):
            try:
                if uploaded_file.name.endswith('.xlsx'):
                    df_excel = pd.read_excel(uploaded_file)
                    if "Nro" not in df_excel.columns:
                        df_excel.insert(0, "Nro", range(1, len(df_excel) + 1))
                    
                    # Asegurar que existan todas las columnas requeridas
                    for col in columnas_clientes:
                        if col not in df_excel.columns:
                            df_excel[col] = ""
                            
                    st.session_state["df_clientes"] = df_excel[columnas_clientes]
                    st.success("¡Archivo Excel cargado con éxito!")
                else:
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    prompt = f"""
                    Actúa como un experto en extracción de datos logísticos.
                    Analiza el PDF adjunto y extrae la información de los clientes respetando estrictamente el orden en el que aparecen.
                    Devuelve la respuesta estrictamente como una lista de objetos JSON.
                    Cada objeto debe tener estas claves exactas para los campos informativos iniciales: 
                    "Nro", "Cliente", "Ubicacion", "Día de Visita Semana 1", "Día de Visita Semana 2". 
                    Para las demás columnas del esquema deja valores por defecto vacíos o predeterminados si no aplican.
                    Esquema completo de columnas esperado: {columnas_clientes}.
                    No incluyas explicaciones ni texto adicional, solo el JSON puro.
                    """
                    response = model.generate_content([
                        prompt, 
                        {"mime_type": "application/pdf", "data": uploaded_file.getvalue()}
                    ])
                    json_text = response.text.replace("```json", "").replace("```", "").strip()
                    data = json.loads(json_text)
                    df_ia = pd.DataFrame(data)
                    
                    # Rellenar columnas faltantes si es necesario
                    for col in columnas_clientes:
                        if col not in df_ia.columns:
                            df_ia[col] = ""
                            
                    st.session_state["df_clientes"] = df_ia[columnas_clientes]
                    st.success("¡Datos del PDF extraídos e integrados correctamente!")
            except Exception as e:
                st.error(f"Error al procesar el archivo: {e}")

    st.markdown("---")
    st.subheader("Cuadro Maestro Editable")
    
    # Obtener listas actualizadas para los menús desplegables de la tabla
    lista_vend_opciones = st.session_state["df_vendedores"]["Vendedor"].dropna().tolist()
    lista_merc_opciones = st.session_state["df_mercaderistas"]["Mercaderista"].dropna().tolist()
    dias_semana_opciones = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]

    # Editor de datos principal con restricciones de listas desplegables
    st.session_state["df_clientes"] = st.data_editor(
        st.session_state["df_clientes"],
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Vendedor": st.column_config.SelectboxColumn("Vendedor", options=lista_vend_opciones, required=False),
            "Nro de Ruta (Ventas)": st.column_config.TextColumn("Nro de Ruta (Ventas)"),
            "Cliente": st.column_config.TextColumn("Cliente", required=True),
            "Ubicacion": st.column_config.TextColumn("Ubicacion"),
            "Semana 1": st.column_config.SelectboxColumn("Semana 1", options=["Sí", "No"]),
            "Semana 2": st.column_config.SelectboxColumn("Semana 2", options=["Sí", "No"]),
            "Día de Visita Semana 1": st.column_config.SelectboxColumn("Día Visita S1", options=dias_semana_opciones),
            "Día de Visita Semana 2": st.column_config.SelectboxColumn("Día Visita S2", options=dias_semana_opciones),
            "Tiempo de Despacho": st.column_config.SelectboxColumn("Tiempo Despacho", options=["24 HORAS", "48 HORAS"]),
            "Mercaderia": st.column_config.SelectboxColumn("Mercaderia", options=["Sí", "No"]),
            "Mercaderista": st.column_config.SelectboxColumn("Mercaderista", options=lista_merc_opciones, required=False),
            "Nro de Ruta (Mercaderia)": st.column_config.TextColumn("Nro de Ruta (Mercaderia)"),
            "Tiempo de Mercaderia": st.column_config.SelectboxColumn("Tiempo Mercaderia", options=["48 HORAS", "72 HORAS"]),
            "Día de Mercaderia Semana 1": st.column_config.SelectboxColumn("Día Merc. S1", options=dias_semana_opciones),
            "Día de Mercaderia Semana 2": st.column_config.SelectboxColumn("Día Merc. S2", options=dias_semana_opciones)
        }
    )

# ==========================================
# PESTAÑA 2: GESTIÓN DE VENDEDORES
# ==========================================
with tab_vendedores:
    st.header("👥 Apartado de Vendedores y Números de Ruta")
    st.markdown("Aquí puedes agregar, editar o eliminar los vendedores activos de la empresa y asignarles su respectivo número de ruta.")
    
    st.session_state["df_vendedores"] = st.data_editor(
        st.session_state["df_vendedores"],
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Vendedor": st.column_config.TextColumn("Nombre del Vendedor", required=True),
            "Nro de Ruta": st.column_config.TextColumn("Número de Ruta Asignado", required=True)
        },
        key="editor_vendedores"
    )

# ==========================================
# PESTAÑA 3: GESTIÓN DE MERCADERISTAS
# ==========================================
with tab_mercaderistas:
    st.header("🛒 Apartado de Mercaderistas y Números de Ruta")
    st.markdown("Aquí puedes administrar los mercaderistas y asociarlos a su respectivo número de ruta de distribución.")
    
    st.session_state["df_mercaderistas"] = st.data_editor(
        st.session_state["df_mercaderistas"],
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Mercaderista": st.column_config.TextColumn("Nombre del Mercaderista", required=True),
            "Nro de Ruta": st.column_config.TextColumn("Número de Ruta Asignado", required=True)
        },
        key="editor_mercaderistas"
    )
