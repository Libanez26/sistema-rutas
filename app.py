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
                df_excel = pd.read_excel(uploaded_file)
                
                # Limpiar espacios en blanco en los nombres de las columnas del Excel
                df_excel.columns = df_excel.columns.str.strip()
                
                nuevo_df = pd.DataFrame()
                nuevo_df["Nro"] = range(1, len(df_excel) + 1)
                
                # Mapeo exacto considerando posibles variaciones de nombres con o sin espacios
                col_map = {
                    'Vendedor': 'Vendedor',
                    'Nro de Ruta': 'Nro de Ruta (Ventas)',
                    'Cliente': 'Cliente',
                    'Ubicacion': 'Ubicacion',
                    'Semana 1': 'Semana 1',
                    'Semana 2': 'Semana 2',
                    'Tiempo de Despacho': 'Tiempo de Despacho',
                    'Mercaderia': 'Mercaderia',
                    'Mercaderista': 'Mercaderista',
                    'Nro de Ruta Mercaderista': 'Nro de Ruta (Mercaderia)',
                    'Tiempo de Mercaderia': 'Tiempo de Mercaderia',
                    'Día de Visita Semana 1': 'Día de Visita Semana 1',
                    'Día de Visita Semana 2': 'Día de Visita Semana 2',
                    'Día de Mercaderia Semana 1': 'Día de Mercaderia Semana 1',
                    'Día de Mercaderia Semana 2': 'Día de Mercaderia Semana 2'
                }
                
                for col_target in columnas_clientes:
                    if col_target == "Nro":
                        continue
                    
                    encontrada = False
                    for orig, dest in col_map.items():
                        if dest == col_target and orig in df_excel.columns:
                            # Limpiar strings de espacios sobrantes en los datos si es texto
                            val = df_excel[orig]
                            if val.dtype == object:
                                val = val.astype(str).str.strip()
                                val = val.replace({'nan': '', 'None': ''})
                            nuevo_df[col_target] = val
                            encontrada = True
                            break
                    
                    if not encontrada:
                        if col_target in df_excel.columns:
                            val = df_excel[col_target]
                            if val.dtype == object:
                                val = val.astype(str).str.strip()
                                val = val.replace({'nan': '', 'None': ''})
                            nuevo_df[col_target] = val
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
        "Semana 1": st.column_config.SelectboxColumn("Semana 1", options=["Sí", "No"]),
        "Semana 2": st.column_config.SelectboxColumn("Semana 2", options=["Sí", "No"]),
        # Configurados como texto libre para permitir escribir o seleccionar varios días (ej. "Lunes, Jueves")
        "Día de Visita Semana 1": st.column_config.TextColumn("Día Visita S1"),
        "Día de Visita Semana 2": st.column_config.TextColumn("Día Visita S2"),
        "Tiempo de Despacho": st.column_config.SelectboxColumn("Tiempo Despacho", options=["24 HORAS", "48 HORAS"]),
        "Mercaderia": st.column_config.SelectboxColumn("Mercaderia", options=["Sí", "No"]),
        "Mercaderista": st.column_config.SelectboxColumn("Mercaderista", options=lista_merc_opciones, required=False),
        "Nro de Ruta (Mercaderia)": st.column_config.TextColumn("Nro de Ruta (Mercaderia)"),
        "Tiempo de Mercaderia": st.column_config.SelectboxColumn("Tiempo Mercaderia", options=["48 HORAS", "72 HORAS"]),
        "Día de Mercaderia Semana 1": st.column_config.TextColumn("Día Merc. S1"),
        "Día de Mercaderia Semana 2": st.column_config.TextColumn("Día Merc. S2")
    }
)

# Copiar formato de la última fila si se agrega una nueva
if len(edited_df) > len(df_actual) and len(df_actual) > 0:
    ultima_fila_original = df_actual.iloc[-1].copy()
    for idx in range(len(df_actual), len(edited_df)):
        if pd.isna(edited_df.loc[idx, "Cliente"]) or edited_df.loc[idx, "Cliente"] == "":
            edited_df.loc[idx, "Semana 1"] = ultima_fila_original.get("Semana 1", "Sí")
            edited_df.loc[idx, "Semana 2"] = ultima_fila_original.get("Semana 2", "Sí")
            edited_df.loc[idx, "Tiempo de Despacho"] = ultima_fila_original.get("Tiempo de Despacho", "24 HORAS")
            edited_df.loc[idx, "Mercaderia"] = ultima_fila_original.get("Mercaderia", "Sí")

st.session_state["df_clientes"] = edited_df
