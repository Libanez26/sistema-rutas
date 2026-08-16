import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import io
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from supabase import create_client, Client

# Configuración inicial de la página
st.set_page_config(page_title="Gestión de Rutas - Lácteos Ananké", layout="wide")

st.title("Sistema Integral de Gestión de Rutas - Lácteos Ananké")

# Configurar API de Gemini
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Error: La API Key de Gemini no está configurada en los Secrets de Streamlit.")

# ==========================================
# CONEXIÓN A SUPABASE
# ==========================================
@st.cache_resource
def init_supabase() -> Client:
    if "supabase" in st.secrets:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    return None

supabase = init_supabase()

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
        {"Mercaderista": "Yorsin Villanueva", "Nro de Ruta": "Ruta M-01"},
        {"Mercaderista": "José Pire", "Nro de Ruta": "Ruta M-02"}
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

# Cargar datos desde Supabase al iniciar (Ordenados para evitar que se pierdan o alteren)
if "df_clientes" not in st.session_state:
    if supabase:
        try:
            response = supabase.table("clientes_ananke").select("*").execute()
            data_db = response.data
            if data_db:
                df_temp = pd.DataFrame(data_db)
                if "id" in df_temp.columns:
                    df_temp = df_temp.drop(columns=["id"])
                
                for col in columnas_clientes:
                    if col not in df_temp.columns:
                        df_temp[col] = ""
                st.session_state["df_clientes"] = df_temp[columnas_clientes]
            else:
                st.session_state["df_clientes"] = pd.DataFrame(columns=columnas_clientes)
        except Exception as e:
            st.warning(f"Aviso de carga desde Supabase: {e}")
            st.session_state["df_clientes"] = pd.DataFrame(columns=columnas_clientes)
    else:
        st.session_state["df_clientes"] = pd.DataFrame(columns=columnas_clientes)

# Función de guardado inteligente con Upsert (Preserva datos anteriores y actualiza sin borrar de más)
# Función segura para guardar en Supabase (Borra e inserta todo el bloque actualizado)
def guardar_en_supabase():
    if supabase:
        try:
            df_to_save = st.session_state["df_clientes"].copy()
            df_to_save = df_to_save.fillna("")
            
            # Solo enviar filas que tengan al menos el nombre del cliente escrito
            df_to_save = df_to_save[df_to_save["Cliente"].astype(str).str.strip() != ""]
            
            records = df_to_save.to_dict(orient="records")
            
            # Limpiar registros previos en la tabla y reinsertar los actuales
            supabase.table("clientes_ananke").delete().neq("Nro", -999999).execute()
            
            if records:
                supabase.table("clientes_ananke").insert(records).execute()
                
            st.toast("¡Sincronizado con Supabase correctamente!", icon="☁️")
        except Exception as e:
            st.error(f"Error al guardar en Supabase: {e}")

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
                
                df_excel.columns = df_excel.columns.str.replace(r'\s+', ' ', regex=True).str.strip()
                
                nuevo_df = pd.DataFrame()
                nuevo_df["Nro"] = range(1, len(df_excel) + 1)
                
                for col in df_excel.select_dtypes(include=['object']).columns:
                    df_excel[col] = df_excel[col].astype(str).str.strip()
                    df_excel[col] = df_excel[col].replace({'nan': '', 'None': ''})

                mapping_cols = {
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
                    'Tiempo de Mercaderia': 'Tiempo de Mercaderia'
                }
                
                for col_target in columnas_clientes:
                    if col_target == "Nro":
                        continue
                    
                    encontrada = False
                    for orig, dest in mapping_cols.items():
                        if dest == col_target and orig in df_excel.columns:
                            nuevo_df[col_target] = df_excel[orig]
                            encontrada = True
                            break
                    
                    if not encontrada:
                        match_encontrado = False
                        for col_excel in df_excel.columns:
                            col_limpia = ' '.join(col_excel.split())
                            target_limpia = ' '.join(col_target.split())
                            if col_limpia.lower() == target_limpia.lower():
                                nuevo_df[col_target] = df_excel[col_excel]
                                match_encontrado = True
                                break
                        
                        if not match_encontrado:
                            if col_target in df_excel.columns:
                                nuevo_df[col_target] = df_excel[col_target]
                            else:
                                nuevo_df[col_target] = ""

                for c in ["Semana 1", "Semana 2", "Mercaderia"]:
                    if c in nuevo_df.columns:
                        nuevo_df[c] = nuevo_df[c].replace({"Si": "Sí", "si": "Sí", "SI": "Sí", "no": "No", "NO": "No"})

                st.session_state["df_clientes"] = nuevo_df
                guardar_en_supabase()
                st.success("¡Archivo Excel cargado y sincronizado en Supabase con éxito!")
            else:
                model = genai.GenerativeModel('gemini-2.5-flash')
                prompt = f"""
                Actúa como un experto en extracción de datos logísticos.
                Analiza el PDF adjunto y extrae toda la información de los clientes.
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
                guardar_en_supabase()
                st.success("¡Datos del PDF extraídos y sincronizados en Supabase con éxito!")
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
    st.subheader("Gestión de Mercaderistas CCS")
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

# Función callback para heredar filas nuevas y autocompletar rutas
def procesar_herencia():
    df = st.session_state["df_clientes"]
    
    if len(df) > 1 and (pd.isna(df.iloc[-1]["Cliente"]) or df.iloc[-1]["Cliente"] == ""):
        fila_anterior = df.iloc[-2].copy()
        for col in df.columns:
            if col != "Cliente" and col != "Nro":
                st.session_state["df_clientes"].at[df.index[-1], col] = fila_anterior[col]
        st.session_state["df_clientes"].at[df.index[-1], "Nro"] = fila_anterior["Nro"] + 1

    df_v = st.session_state["df_vendedores"]
    df_m = st.session_state["df_mercaderistas"]
    
    for idx, row in df.iterrows():
        vendedor_actual = row["Vendedor"]
        if pd.notna(vendedor_actual) and vendedor_actual != "":
            match_v = df_v[df_v["Vendedor"] == vendedor_actual]
            if not match_v.empty:
                ruta_v = match_v.iloc[0]["Nro de Ruta"]
                if row["Nro de Ruta (Ventas)"] != ruta_v:
                    st.session_state["df_clientes"].at[idx, "Nro de Ruta (Ventas)"] = ruta_v
        
        merc_actual = row["Mercaderista"]
        if pd.notna(merc_actual) and merc_actual != "":
            match_m = df_m[df_m["Mercaderista"] == merc_actual]
            if not match_m.empty:
                ruta_m = match_m.iloc[0]["Nro de Ruta"]
                if row["Nro de Ruta (Mercaderia)"] != ruta_m:
                    st.session_state["df_clientes"].at[idx, "Nro de Ruta (Mercaderia)"] = ruta_m

df_actual = st.session_state["df_clientes"]

edited_df = st.data_editor(
    df_actual,
    num_rows="dynamic",
    use_container_width=True,
    key="editor_clientes",
    on_change=procesar_herencia,
    column_config={
        "Nro": st.column_config.NumberColumn("Nro", required=True),
        "Vendedor": st.column_config.SelectboxColumn("Vendedor", options=lista_vend_opciones, required=False),
        "Nro de Ruta (Ventas)": st.column_config.TextColumn("Nro de Ruta (Ventas)"),
        "Cliente": st.column_config.TextColumn("Cliente", required=True),
        "Ubicacion": st.column_config.TextColumn("Ubicacion"),
        "Semana 1": st.column_config.SelectboxColumn("Semana 1", options=["Sí", "No"]),
        "Semana 2": st.column_config.SelectboxColumn("Semana 2", options=["Sí", "No"]),
        "Día de Visita Semana 1": st.column_config.TextColumn("Día Visita S1 (Ej. Lunes, Miércoles)"),
        "Día de Visita Semana 2": st.column_config.TextColumn("Día Visita S2 (Ej. Martes, Jueves)"),
        "Tiempo de Despacho": st.column_config.SelectboxColumn("Tiempo Despacho", options=["24 HORAS", "48 HORAS", "24h", "48h"]),
        "Mercaderia": st.column_config.SelectboxColumn("Mercaderia", options=["Sí", "No"]),
        "Mercaderista": st.column_config.SelectboxColumn("Mercaderista", options=lista_merc_opciones, required=False),
        "Nro de Ruta (Mercaderia)": st.column_config.TextColumn("Nro de Ruta (Mercaderia)"),
        "Tiempo de Mercaderia": st.column_config.SelectboxColumn("Tiempo Mercaderia", options=["48 HORAS", "72 HORAS", "48h", "72h"]),
        "Día de Mercaderia Semana 1": st.column_config.TextColumn("Día Merc. S1"),
        "Día de Mercaderia Semana 2": st.column_config.TextColumn("Día Merc. S2")
    }
)

st.session_state["df_clientes"] = edited_df

# Botón explícito de guardado manual para asegurar persistencia permanente
if st.button("💾 Guardar Cambios en la Base de Datos", type="primary", use_container_width=True):
    guardar_en_supabase()

# ==========================================
# OPCIONES DE DESCARGA (EXCEL Y PDF)
# ==========================================

st.markdown("---")
st.subheader("Opciones de Descarga del Cuadro Maestro")

col_dl1, col_dl2 = st.columns(2)

# 1. Botón para descargar en Excel
with col_dl1:
    output_excel = io.BytesIO()
    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
        st.session_state["df_clientes"].to_excel(writer, index=False, sheet_name='Base de Datos')
    excel_data = output_excel.getvalue()
    
    st.download_button(
        label="📥 Descargar en Formato Excel (.xlsx)",
        data=excel_data,
        file_name="Cuadro_Maestro_Rutas_Ananke.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

# 2. Botón para descargar en PDF
with col_dl2:
    def generar_pdf(df):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
        elements = []
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=14,
            textColor=colors.HexColor('#1f4e78'),
            spaceAfter=10,
            alignment=1
        )
        
        elements.append(Paragraph("Cuadro Maestro de Clientes y Rutas - Lácteos Ananké", title_style))
        elements.append(Spacer(1, 10))
        
        df_str = df.astype(str)
        data = [df_str.columns.tolist()] + df_str.values.tolist()
        
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4e78')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
        ]))
        
        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    if not st.session_state["df_clientes"].empty:
        pdf_data = generar_pdf(st.session_state["df_clientes"])
        st.download_button(
            label="📄 Descargar en Formato PDF",
            data=pdf_data,
            file_name="Cuadro_Maestro_Rutas_Ananke.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    else:
        st.button("📄 Descargar en Formato PDF (Vacío)", disabled=True, use_container_width=True)
