import streamlit as st
import pandas as pd
import google.generativeai as genai
import json

# Configuración inicial de la página
st.set_page_config(page_title="Gestión de Rutas - Lácteos Ananké", layout="wide")

st.title("Sistema Integral de Gestión de Rutas - Lácteos Ananké")

# Configurar API de Gemini
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Error: La API Key de Gemini no está configurada en los Secrets de Streamlit.")

# ==========================================
# 1. ESTADOS DE SESIÓN (CATÁLOGOS Y BASE DE DATOS)
# ==========================================

if "df_vendedores" not in st.session_state:
    st.session_state["df_vendedores"] = pd.DataFrame([
        {"Vendedor": "Dairo Bello", "Nro de Ruta": "Ruta 01"},
        {"Vendedor": "Jhony Moreno", "Nro de Ruta": "Ruta 02"}
    ])

if "df_mercaderistas" not in st.session_state:
    st.session_state["df_mercaderistas"] = pd.DataFrame([
        {"Mercaderista": "Carlos Pérez", "Nro de Ruta": "Ruta M-01"},
        {"Mercaderista": "Ana Gómez", "Nro de Ruta": "Ruta M-02"}
    ])

# Columnas exactas sincronizadas con tu esquema
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
# INTERFAZ PRINCIPAL EN UNA SOLA VISTA
# ==========================================

st.header("Base de Datos General de Clientes y Rutas")
st.markdown("Sube tu archivo Excel de rutas para cargar toda la información completa de forma automática.")

uploaded_file = st.file_uploader("Cargar archivo (PDF o Excel)", type=["pdf", "xlsx"])

if uploaded_file and st.button("Procesar y Organizar con IA"):
    with st.spinner("Leyendo documento y estructurando todos los datos..."):
        try:
            if uploaded_file.name.endswith('.xlsx'):
                # Leemos directamente todas las columnas del Excel
                df_excel = pd.read_excel(uploaded_file)
                
                # Mapeo inteligente para asegurarnos que cada columna del Excel caiga en su lugar exacto
                nuevo_df = pd.DataFrame()
                nuevo_df["Nro"] = range(1, len(df_excel) + 1)
                
                # Buscamos columnas parecidas en el Excel subido o dejamos vacío si no están
                col_map = {
                    'Vendedor': 'Vendedor',
                    'Nro de Ruta': 'Nro de Ruta (Ventas)',
                    'Cliente': 'Cliente',
                    'Ubicacion ': 'Ubicacion',
                    'Ubicacion': 'Ubicacion',
                    'Semana 1': 'Semana 1',
                    'Semana 2': 'Semana 2',
                    'Tiempo de Despacho': 'Tiempo de Despacho',
                    'Mercaderia ': 'Mercaderia',
                    'Mercaderia': 'Mercaderia',
                    'Mercaderista': 'Mercaderista',
                    'Nro de Ruta Mercaderista ': 'Nro de Ruta (Mercaderia)',
                    'Nro de Ruta Mercaderista': 'Nro de Ruta (Mercaderia)',
                    'Tiempo de Mercaderia': 'Tiempo de Mercaderia'
                }
                
                for col_target in columnas_clientes:
                    if col_target == "Nro":
                        continue
                    # Buscar si alguna columna del excel coincide
                    encontrada = False
                    for orig, dest in col_map.items():
                        if dest == col_target and orig in df_excel.columns:
                            nuevo_df[col_target] = df_excel[orig]
                            encontrada = True
                            break
                    if not encontrada:
                        # Revisar por coincidencia exacta de nombre
                        if col_target in df_excel.columns:
                            nuevo_df[col_target] = df_excel[col_target]
                        else:
                            nuevo_df[col_target] = ""

                st.session_state["df_clientes"] = nuevo_df
                st.success("¡Archivo Excel cargado con todos sus datos y columnas correctamente!")
            else:
                model = genai.GenerativeModel('gemini-2.5-flash')
                prompt = f"""
                Actúa como un experto en extracción de datos logísticos.
                Analiza el PDF adjunto y extrae toda la información de los clientes (vendedor, rutas, ubicación, días, tiempos, mercaderista).
                Devuelve la respuesta estrictamente como una lista de objetos JSON con las claves exactas: {columnas_clientes}.
                No incluyas explicaciones ni texto adicional, solo el JSON puro.
                """
                response = model.generate_content([
                    prompt, 
                    {"mime_type": "application/pdf", "data": uploaded_file.getvalue()}
                ])
                json_text = response.text.replace("```json", "").replace("```", "").strip()
                data = json.loads(json_text)
                df_ia = pd.DataFrame(data)
                
                for col in columnas_clientes:
                    if col not in df_ia.columns:
                        df_ia[col] = ""
                        
                st.session_state["df_clientes"] = df_ia[columnas_clientes]
                st.success("¡Datos del PDF extraídos correctamente!")
        except Exception as e:
            st.error(f"Error al procesar el archivo: {e}")

st.markdown("---")

# Sección superior para gestionar Vendedores y Mercaderistas
col_vend, col_merc = st.columns(2)

with col_vend:
    st.subheader("Gestión de Vendedores")
    st.session_state["df_vendedores"] = st.data_editor(
        st.session_state["df_vendedores"],
        num_rows="dynamic",
        use_container_width=True,
        key="editor_vendedores_inline"
    )

with col_merc:
    st.subheader("Gestión de Mercaderistas")
    st.session_state["df_mercaderistas"] = st.data_editor(
        st.session_state["df_mercaderistas"],
        num_rows="dynamic",
        use_container_width=True,
        key="editor_mercaderistas_inline"
    )

st.markdown("---")
st.subheader("Cuadro Maestro de Clientes")

lista_vend_opciones = st.session_state["df_vendedores"]["Vendedor"].dropna().tolist()
lista_merc_opciones = st.session_state["df_mercaderistas"]["Mercaderista"].dropna().tolist()
dias_semana_opciones = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]

df_actual = st.session_state["df_clientes"]
edited_df = st.data_editor(
    df_actual,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Vendedor": st.column_config.SelectboxColumn("Vendedor", options=lista_vend_opciones, required=False),
        "Nro de Ruta (Ventas)": st.column_config.TextColumn("Nro de Ruta (Ventas)"),
        "Cliente": st.column_config.TextColumn("Cliente", required=True),
        "Ubicacion": st.column_config.TextColumn("Ubicacion"),
        "Semana 1": st.column_config.SelectboxColumn("Semana 1", options=["Sí", "No", "Si"]),
        "Semana 2": st.column_config.SelectboxColumn("Semana 2", options=["Sí", "No", "Si"]),
        "Día de Visita Semana 1": st.column_config.TextColumn("Día Visita S1"),
        "Día de Visita Semana 2": st.column_config.TextColumn("Día Visita S2"),
        "Tiempo de Despacho": st.column_config.SelectboxColumn("Tiempo Despacho", options=["24 HORAS", "48 HORAS", "24h", "48h"]),
        "Mercaderia": st.column_config.SelectboxColumn("Mercaderia", options=["Sí", "No", "Si"]),
        "Mercaderista": st.column_config.SelectboxColumn("Mercaderista", options=lista_merc_opciones, required=False),
        "Nro de Ruta (Mercaderia)": st.column_config.TextColumn("Nro de Ruta (Mercaderia)"),
        "Tiempo de Mercaderia": st.column_config.SelectboxColumn("Tiempo Mercaderia", options=["48 HORAS", "72 HORAS", "48h", "72h"]),
        "Día de Mercaderia Semana 1": st.column_config.TextColumn("Día Merc. S1"),
        "Día de Mercaderia Semana 2": st.column_config.TextColumn("Día Merc. S2")
    }
)

st.session_state["df_clientes"] = edited_df
