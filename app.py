import io
import json
import pandas as pd
import streamlit as st
import google.generativeai as genai
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import landscape, letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from supabase import create_client, Client

# Configuración inicial de la página
st.set_page_config(page_title="Gestión de Rutas", layout="wide")

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
  if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
    url = st.secrets["SUPABASE_URL"].strip()
    for sufijo in ["/rest/v1/", "/rest/v1", "/"]:
      if url.endswith(sufijo):
        url = url[: -len(sufijo)].strip()
    key = st.secrets["SUPABASE_KEY"].strip()
    return create_client(url, key)
  return None

supabase = init_supabase()

def normalizar_dia(dia):
    if pd.isna(dia) or not dia:
        return ""
    d = str(dia).strip().lower()
    mapping = {
        "lunes": "Lunes",
        "martes": "Martes",
        "miercoles": "Miércoles",
        "miércoles": "Miércoles",
        "jueves": "Jueves",
        "viernes": "Viernes",
        "sabado": "Sábado",
        "sábado": "Sábado",
        "domingo": "Domingo"
    }
    return mapping.get(d, str(dia).strip().capitalize())

# ==========================================
# GESTIÓN DE AUTENTICACIÓN
# ==========================================
if "usuario" not in st.session_state:
    st.session_state["usuario"] = None

if st.session_state["usuario"] is None:
    st.title("🔑 Sistema Integral de Gestión de Rutas")
    st.markdown("### Inicia sesión o regístrate para acceder a la plataforma.")
    
    tab_login, tab_registro = st.tabs(["🔑 Iniciar Sesión", "📝 Registrarse"])
    
    with tab_login:
        st.subheader("Acceso a tu cuenta")
        correo_login = st.text_input("Correo electrónico", key="correo_login")
        password_login = st.text_input("Contraseña", type="password", key="pass_login")
        
        if st.button("Ingresar", type="primary"):
            if supabase:
                try:
                    res = supabase.auth.sign_in_with_password({"email": correo_login, "password": password_login})
                    st.session_state["usuario"] = res.user
                    st.success("¡Sesión iniciada con éxito!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al iniciar sesión: {e}")
            else:
                st.error("Supabase no está configurado correctamente en los Secrets.")
                
    with tab_registro:
        st.subheader("Crear una cuenta nueva")
        correo_reg = st.text_input("Correo electrónico", key="correo_reg")
        password_reg = st.text_input("Contraseña", type="password", key="pass_reg")
        
        if st.button("Registrarse"):
            if supabase:
                try:
                    res = supabase.auth.sign_up({"email": correo_reg, "password": password_reg})
                    st.success("¡Registro exitoso! Ya puedes iniciar sesión.")
                except Exception as e:
                    st.error(f"Error al registrarse: {e}")
            else:
                st.error("Supabase no está configurado correctamente en los Secrets.")
                
    st.stop()
else:
    st.sidebar.write(f"👤 Conectado como: **{st.session_state['usuario'].email}**")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state["usuario"] = None
        st.rerun()

# ==========================================
# APLICACIÓN PRINCIPAL
# ==========================================
st.title("Sistema Integral de Gestión de Rutas")

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
    "Día de Mercaderia Semana 2",
    "Visita_S4", "Pedido_S4", "Motivo_Pedido_S4",
    "Visita_S3", "Pedido_S3", "Motivo_Pedido_S3",
    "Visita_S2", "Pedido_S2", "Motivo_Pedido_S2",
    "Visita_S1", "Pedido_S1", "Motivo_Pedido_S1",
]

if "df_vendedores" not in st.session_state:
  if supabase:
    try:
      res_v = supabase.table("personal_rutas").select("*").eq("tipo", "vendedor").execute()
      if res_v.data:
        st.session_state["df_vendedores"] = pd.DataFrame(res_v.data)[["Vendedor", "Nro de Ruta"]]
      else:
        raise Exception()
    except:
      st.session_state["df_vendedores"] = pd.DataFrame([
          {"Vendedor": "Jhony Moreno", "Nro de Ruta": "Ruta 01"},
          {"Vendedor": "Dairo Bello", "Nro de Ruta": "Ruta 02"},
          {"Vendedor": "Ventas Directas", "Nro de Ruta": "Ventas"},
      ])
  else:
    st.session_state["df_vendedores"] = pd.DataFrame([
        {"Vendedor": "Jhony Moreno", "Nro de Ruta": "Ruta 01"},
        {"Vendedor": "Dairo Bello", "Nro de Ruta": "Ruta 02"},
        {"Vendedor": "Ventas Directas", "Nro de Ruta": "Ventas"},
    ])

if "df_mercaderistas" not in st.session_state:
  if supabase:
    try:
      res_m = supabase.table("personal_rutas").select("*").eq("tipo", "mercaderista").execute()
      if res_m.data:
        st.session_state["df_mercaderistas"] = pd.DataFrame(res_m.data).rename(columns={"Vendedor": "Mercaderista"})[["Mercaderista", "Nro de Ruta"]]
      else:
        raise Exception()
    except:
      st.session_state["df_mercaderistas"] = pd.DataFrame([
          {"Mercaderista": "Yorsin Villanueva", "Nro de Ruta": "Ruta M-01"},
          {"Mercaderista": "José Pire", "Nro de Ruta": "Ruta M-02"},
      ])
  else:
    st.session_state["df_mercaderistas"] = pd.DataFrame([
        {"Mercaderista": "Yorsin Villanueva", "Nro de Ruta": "Ruta M-01"},
        {"Mercaderista": "José Pire", "Nro de Ruta": "Ruta M-02"},
    ])

if "df_clientes" not in st.session_state:
  if supabase:
    try:
      response = supabase.table("clientes_rutas").select("*").execute()
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
    except:
      st.session_state["df_clientes"] = pd.DataFrame(columns=columnas_clientes)
  else:
    st.session_state["df_clientes"] = pd.DataFrame(columns=columnas_clientes)

def guardar_en_base_de_datos(df):
  if supabase:
    try:
      df_to_save = df.copy().fillna("")
      df_to_save = df_to_save[df_to_save["Cliente"].astype(str).str.strip() != ""]
      supabase.table("clientes_rutas").delete().neq("Nro", -999999).execute()
      if not df_to_save.empty:
        supabase.table("clientes_rutas").insert(df_to_save.to_dict(orient="records")).execute()

      supabase.table("personal_rutas").delete().neq("id", -999999).execute()
      
      registros_personal = []
      for _, row in st.session_state["df_vendedores"].dropna(subset=["Vendedor"]).iterrows():
        if str(row["Vendedor"]).strip() != "":
          registros_personal.append({"tipo": "vendedor", "Vendedor": str(row["Vendedor"]), "Nro de Ruta": str(row["Nro de Ruta"])})
          
      for _, row in st.session_state["df_mercaderistas"].dropna(subset=["Mercaderista"]).iterrows():
        if str(row["Mercaderista"]).strip() != "":
          registros_personal.append({"tipo": "mercaderista", "Vendedor": str(row["Mercaderista"]), "Nro de Ruta": str(row["Nro de Ruta"])})

      if registros_personal:
        supabase.table("personal_rutas").insert(registros_personal).execute()

      st.success("¡Cambios guardados en la base de datos correctamente!")
    except Exception as e:
      st.error(f"Error al guardar en Supabase: {e}")

tab_general, tab_ruta_vendedores = st.tabs(["📊 Cuadro Maestro General", "🚚 Ruta de Vendedores"])

with tab_general:
    st.header("Base de Datos General de Clientes y Rutas")
    st.markdown("Sube tu archivo Excel de rutas para cargar toda la información completa de forma automática.")

    uploaded_file = st.file_uploader("Cargar archivo (PDF o Excel)", type=["pdf", "xlsx"])

    if uploaded_file and st.button("Procesar y Organizar con IA"):
      with st.spinner("Leyendo documento y estructurando todos los datos..."):
        try:
          if uploaded_file.name.endswith(".xlsx"):
            df_excel = pd.read_excel(uploaded_file)
            df_excel.columns = df_excel.columns.str.replace(r"\s+", " ", regex=True).str.strip()

            nuevo_df = pd.DataFrame()
            nuevo_df["Nro"] = range(1, len(df_excel) + 1)

            for col in df_excel.select_dtypes(include=["object"]).columns:
              df_excel[col] = df_excel[col].astype(str).str.strip()
              df_excel[col] = df_excel[col].replace({"nan": "", "None": ""})

            mapping_cols = {
                "Vendedor": "Vendedor",
                "Nro de Ruta": "Nro de Ruta (Ventas)",
                "Cliente": "Cliente",
                "Ubicacion": "Ubicacion",
                "Semana 1": "Semana 1",
                "Semana 2": "Semana 2",
                "Tiempo de Despacho": "Tiempo de Despacho",
                "Mercaderia": "Mercaderia",
                "Mercaderista": "Mercaderista",
                "Nro de Ruta Mercaderista": "Nro de Ruta (Mercaderia)",
                "Tiempo de Mercaderia": "Tiempo de Mercaderia",
                "Día de Visita Semana 1": "Día de Visita Semana 1",
                "Día de Visita Semana 2": "Día de Visita Semana 2",
                "Día de Mercaderia Semana 1": "Día de Mercaderia Semana 1",
                "Día de Mercaderia Semana 2": "Día de Mercaderia Semana 2",
            }

            for col_target in columnas_clientes:
              if col_target not in df_excel.columns and col_target not in nuevo_df.columns:
                nuevo_df[col_target] = ""
                continue
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
                  col_limpia = " ".join(col_excel.split())
                  target_limpia = " ".join(col_target.split())
                  if col_limpia.lower() == target_limpia.lower():
                    nuevo_df[col_target] = df_excel[col_excel]
                    match_encontrado = True
                    break

                if not match_encontrado:
                  if col_target in df_excel.columns:
                    nuevo_df[col_target] = df_excel[col_target]
                  else:
                    if col_target not in nuevo_df.columns:
                      nuevo_df[col_target] = ""

            for c in ["Semana 1", "Semana 2", "Mercaderia"]:
              if c in nuevo_df.columns:
                nuevo_df[c] = nuevo_df[c].replace({"Si": "Sí", "si": "Sí", "SI": "Sí", "no": "No", "NO": "No"})

            st.session_state["df_clientes"] = nuevo_df
            st.success("¡Archivo Excel cargado con éxito en la vista previa! Presiona 'Guardar Cambios' para enviarlo a la base de datos.")
          else:
            model = genai.GenerativeModel("gemini-2.5-flash")
            prompt = f"""
                    Actúa como un experto en extracción de datos logísticos.
                    Analiza el PDF adjunto y extrae toda la información de los clientes.
                    Devuelve la respuesta estrictamente como una lista de objetos JSON con las claves exactas: {columnas_clientes}.
                    No incluyas explicaciones ni texto adicional, solo el JSON puro.
                    """
            response = model.generate_content([
                prompt,
                {"mime_type": "application/pdf", "data": uploaded_file.getvalue()},
            ])
            json_text = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(json_text)
            df_ia = pd.DataFrame(data)

            for col in columnas_clientes:
              if col not in df_ia.columns:
                df_ia[col] = ""

            st.session_state["df_clientes"] = df_ia[columnas_clientes]
            st.success("¡Datos del PDF extraídos con éxito en la vista previa! Presiona 'Guardar Cambios' para enviarlos a la base de datos.")
        except Exception as e:
          st.error(f"Error al procesar el archivo: {e}")

    st.markdown("---")

    col_vend, col_merc = st.columns(2)

    with col_vend:
      st.subheader("Vendedores")
      edited_vendedores = st.data_editor(
          st.session_state["df_vendedores"],
          num_rows="dynamic",
          use_container_width=True,
          key="editor_vendedores_inline",
          hide_index=True,
      )

    with col_merc:
      st.subheader("Mercaderistas CCS")
      edited_mercaderistas = st.data_editor(
          st.session_state["df_mercaderistas"],
          num_rows="dynamic",
          use_container_width=True,
          key="editor_mercaderistas_inline",
          hide_index=True,
      )

    if st.button("💾 Guardar Cambios de Personal", use_container_width=True):
      st.session_state["df_vendedores"] = edited_vendedores
      st.session_state["df_mercaderistas"] = edited_mercaderistas
      guardar_en_base_de_datos(st.session_state["df_clientes"])
      st.rerun()

    st.markdown("---")
    st.subheader("Cuadro Maestro de Clientes")

    lista_vend_opciones = st.session_state["df_vendedores"]["Vendedor"].dropna().tolist()
    lista_merc_opciones = st.session_state["df_mercaderistas"]["Mercaderista"].dropna().tolist()

    columnas_excluir_vista_general = [
        "Visita_S4", "Pedido_S4", "Motivo_Pedido_S4",
        "Visita_S3", "Pedido_S3", "Motivo_Pedido_S3",
        "Visita_S2", "Pedido_S2", "Motivo_Pedido_S2",
        "Visita_S1", "Pedido_S1", "Motivo_Pedido_S1",
    ]
    columnas_para_mostrar_general = [c for c in columnas_clientes if c not in columnas_excluir_vista_general]

    df_general_visible = st.session_state["df_clientes"][columnas_para_mostrar_general].copy()

    with st.form("form_cuadro_maestro"):
      edited_df_visible = st.data_editor(
          df_general_visible,
          num_rows="dynamic",
          use_container_width=True,
          key="editor_clientes_general",
          hide_index=True,
          column_config={
              "Nro": st.column_config.NumberColumn("Nro", required=True),
              "Vendedor": st.column_config.SelectboxColumn("Vendedor", options=lista_vend_opciones, required=False),
              "Nro de Ruta (Ventas)": st.column_config.TextColumn("Nro de Ruta (Ventas)"),
              "Cliente": st.column_config.TextColumn("Cliente", required=True),
              "Ubicacion": st.column_config.TextColumn("Ubicacion"),
              "Semana 1": st.column_config.SelectboxColumn("Semana 1", options=["Sí", "No"]),
              "Semana 2": st.column_config.SelectboxColumn("Semana 2", options=["Sí", "No"]),
              "Día de Visita Semana 1": st.column_config.TextColumn("Día Visita S1 (Ej: Lunes, Jueves)"),
              "Día de Visita Semana 2": st.column_config.TextColumn("Día Visita S2 (Ej: Lunes, Jueves)"),
              "Tiempo de Despacho": st.column_config.SelectboxColumn("Tiempo Despacho", options=["24 HORAS", "48 HORAS", "24h", "48h"]),
              "Mercaderia": st.column_config.SelectboxColumn("Mercaderia", options=["Sí", "No"]),
              "Mercaderista": st.column_config.SelectboxColumn("Mercaderista", options=lista_merc_opciones, required=False),
              "Nro de Ruta (Mercaderia)": st.column_config.TextColumn("Nro de Ruta (Mercaderia)"),
              "Tiempo de Mercaderia": st.column_config.SelectboxColumn("Tiempo Mercaderia", options=["48 HORAS", "72 HORAS", "48h", "72h"]),
              "Día de Mercaderia Semana 1": st.column_config.TextColumn("Día Merc. S1"),
              "Día de Mercaderia Semana 2": st.column_config.TextColumn("Día Merc. S2"),
          },
      )

      submitted = st.form_submit_button("💾 Guardar y Conectar Rutas en la Base de Datos", type="primary", use_container_width=True)

      if submitted:
        df_actualizado = st.session_state["df_clientes"].copy()
        
        for col in edited_df_visible.columns:
          df_actualizado[col] = edited_df_visible[col]

        if not df_actualizado.empty:
          if len(df_actualizado) > 1:
            ultima_fila = df_actualizado.iloc[-1]
            cliente_val = ultima_fila.get("Cliente", "")
            if pd.isna(cliente_val) or str(cliente_val).strip() == "":
              fila_anterior = df_actualizado.iloc[-2].copy()
              for col in df_actualizado.columns:
                if col != "Cliente" and col != "Nro":
                  df_actualizado.at[df_actualizado.index[-1], col] = fila_anterior[col]
              try:
                df_actualizado.at[df_actualizado.index[-1], "Nro"] = int(fila_anterior["Nro"]) + 1
              except:
                pass

          df_v = st.session_state["df_vendedores"]
          df_m = st.session_state["df_mercaderistas"]

          for idx, row in df_actualizado.iterrows():
            vendedor_actual = row.get("Vendedor")
            if pd.notna(vendedor_actual) and str(vendedor_actual).strip() != "":
              match_v = df_v[df_v["Vendedor"].astype(str).str.strip() == str(vendedor_actual).strip()]
              if not match_v.empty:
                df_actualizado.at[idx, "Nro de Ruta (Ventas)"] = match_v.iloc[0]["Nro de Ruta"]
                
                pos_vendedor = match_v.index[0]
                if pos_vendedor < len(df_m):
                  mercaderista_asignado = df_m.iloc[pos_vendedor]["Mercaderista"]
                  ruta_mercaderia_asignada = df_m.iloc[pos_vendedor]["Nro de Ruta"]
                  
                  merc_actual_fila = row.get("Mercaderista")
                  if pd.isna(merc_actual_fila) or str(merc_actual_fila).strip() == "":
                    df_actualizado.at[idx, "Mercaderista"] = mercaderista_asignado
                    df_actualizado.at[idx, "Nro de Ruta (Mercaderia)"] = ruta_mercaderia_asignada
                  else:
                    match_m = df_m[df_m["Mercaderista"].astype(str).str.strip() == str(merc_actual_fila).strip()]
                    if not match_m.empty:
                      df_actualizado.at[idx, "Nro de Ruta (Mercaderia)"] = match_m.iloc[0]["Nro de Ruta"]

        st.session_state["df_clientes"] = df_actualizado
        guardar_en_base_de_datos(df_actualizado)
        st.rerun()

    st.markdown("---")
    st.subheader("Opciones de Descarga del Cuadro Maestro")

    col_dl1, col_dl2 = st.columns(2)

    with col_dl1:
      output_excel = io.BytesIO()
      with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
        st.session_state["df_clientes"].to_excel(writer, index=False, sheet_name="Base de Datos")
      excel_data = output_excel.getvalue()

      st.download_button(
          label="📥 Descargar en Formato Excel (.xlsx)",
          data=excel_data,
          file_name="Cuadro_Maestro_Rutas.xlsx",
          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          use_container_width=True,
      )

    with col_dl2:
      def generar_pdf_general(df):
        buffer = io.BytesIO()
        columnas_a_excluir = [
            "Visita_S4", "Pedido_S4", "Motivo_Pedido_S4",
            "Visita_S3", "Pedido_S3", "Motivo_Pedido_S3",
            "Visita_S2", "Pedido_S2", "Motivo_Pedido_S2",
            "Visita_S1", "Pedido_S1", "Motivo_Pedido_S1",
        ]
        df_pdf = df.drop(columns=[col for col in columnas_a_excluir if col in df.columns], errors="ignore")
        df_pdf = df_pdf.fillna("No aplica").replace(r"^\s*$", "No aplica", regex=True)

        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=15, leftMargin=15, topMargin=20, bottomMargin=20)
        elements = []
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("TitleStyle", parent=styles["Heading1"], fontSize=14, textColor=colors.HexColor("#1f4e78"), spaceAfter=12, alignment=1)
        elements.append(Paragraph("Cuadro Maestro de Clientes y Rutas", title_style))
        elements.append(Spacer(1, 5))

        cell_style = ParagraphStyle("CellStyle", parent=styles["Normal"], fontSize=6.5, leading=8, alignment=1)
        header_style = ParagraphStyle("HeaderStyle", parent=styles["Normal"], fontSize=6.5, leading=8, textColor=colors.whitesmoke, fontName="Helvetica-Bold", alignment=1)

        data = [[Paragraph(str(col), header_style) for col in df_pdf.columns]]
        for _, row in df_pdf.iterrows():
            data.append([Paragraph(str(val), cell_style) for val in row.values])

        ancho_total_disponible = 762
        num_columnas = len(df_pdf.columns)
        table = Table(data, colWidths=[ancho_total_disponible / num_columnas] * num_columnas, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C5E3B")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fdfdfd")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d0d0")),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
            ("TOPPADDING", (0, 1), (-1, -1), 4),
        ]))
        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

      pdf_data = generar_pdf_general(st.session_state["df_clientes"])
      st.download_button(
          label="📥 Descargar en Formato PDF",
          data=pdf_data,
          file_name="Cuadro_Maestro_Rutas.pdf",
          mime="application/pdf",
          use_container_width=True,
      )

with tab_ruta_vendedores:
    st.header("Seguimiento de Ruta de Vendedores")
    st.markdown("Filtra por vendedor, semana de trabajo y día de visita para gestionar el estatus actual de la semana en formato de tabla limpia y compacta.")

    df_seguimiento = st.session_state["df_clientes"].copy()
    
    for s_idx in [1, 2, 3, 4]:
        for c_field in [f"Visita_S{s_idx}", f"Pedido_S{s_idx}", f"Motivo_Pedido_S{s_idx}"]:
            if c_field not in df_seguimiento.columns:
                df_seguimiento[c_field] = ""

    vendedores_disponibles = sorted(list(set(df_seguimiento["Vendedor"].dropna().astype(str)) - {""}))
    
    if not vendedores_disponibles:
        st.warning("No hay vendedores registrados aún. Carga o ingresa información en el Cuadro Maestro primero.")
    else:
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        
        with col_f1:
            vendedor_seleccionado = st.selectbox("Seleccionar Vendedor", vendedores_disponibles, key="filtro_vendedor_ruta")
            
        with col_f2:
            fecha_gestion = st.date_input("Fecha de Gestión", value=datetime.now().date(), key="filtro_fecha_gestion")
            num_iso_semana = fecha_gestion.isocalendar()[1]
            semana_calculada_auto = "Semana 1" if num_iso_semana % 2 != 0 else "Semana 2"

        with col_f3:
            semana_seleccionada = st.selectbox("Seleccionar Semana", ["Semana 1", "Semana 2"], key="filtro_semana_ruta")

        with col_f4:
            dias_opciones = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            dia_seleccionado = st.selectbox("Seleccionar Día de Visita", dias_opciones, key="filtro_dia_ruta")

        if "historial_semana_previa" not in st.session_state:
            st.session_state["historial_semana_previa"] = {
                "semana": semana_seleccionada,
                "fecha": fecha_gestion
            }

        semana_anterior_reg = st.session_state["historial_semana_previa"]["semana"]
        fecha_anterior_reg = st.session_state["historial_semana_previa"]["fecha"]

        diferencia_dias = (fecha_gestion - fecha_anterior_reg).days
        if 5 <= diferencia_dias <= 10 and semana_seleccionada == semana_anterior_reg:
            st.warning(f"⚠️ Estás seleccionando la misma **{semana_seleccionada}** habiendo avanzado una semana en el calendario (Fecha: {fecha_gestion.strftime('%d/%m/%Y')}). ¿Estás seguro de mantener esta semana?")
            if st.button("Sí, confirmar cambio/mantener semana"):
                st.session_state["historial_semana_previa"] = {"semana": semana_seleccionada, "fecha": fecha_gestion}
                st.rerun()
        elif diferencia_dias > 10 and semana_seleccionada == semana_anterior_reg:
            st.warning(f"⚠️ Han pasado varios días y sigues en la **{semana_seleccionada}**. ¿Seguro que quieres mantener esta semana y no avanzar?")
            if st.button("Sí, confirmar"):
                st.session_state["historial_semana_previa"] = {"semana": semana_seleccionada, "fecha": fecha_gestion}
                st.rerun()
        else:
            st.session_state["historial_semana_previa"] = {"semana": semana_seleccionada, "fecha": fecha_gestion}

        # ==========================================
        # BOTÓN DE DESCARGA PDF DE RUTA (MATRICIAL)
        # ==========================================
        def generar_pdf_matriz_vendedor(df_todos, vendedor_filtro):
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=15, leftMargin=15, topMargin=20, bottomMargin=20)
            elements = []
            styles = getSampleStyleSheet()

            title_style = ParagraphStyle("TitleStyle", parent=styles["Heading1"], fontSize=12, textColor=colors.HexColor("#1f4e78"), spaceAfter=8, alignment=1)
            section_style = ParagraphStyle("SectionStyle", parent=styles["Heading2"], fontSize=10, textColor=colors.HexColor("#2C5E3B"), spaceBefore=6, spaceAfter=4, alignment=0)
            
            cell_style = ParagraphStyle("CellStyle", parent=styles["Normal"], fontSize=6, leading=7.5, alignment=1)
            header_style = ParagraphStyle("HeaderStyle", parent=styles["Normal"], fontSize=6.5, leading=8, textColor=colors.whitesmoke, fontName="Helvetica-Bold", alignment=1)
            
            dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

            elements.append(Paragraph(f"REPORTE DE RUTAS POR VENDEDOR: {vendedor_filtro.upper()}", title_style))

            df_vend_subset = df_todos[df_todos["Vendedor"].astype(str).str.strip() == vendedor_filtro.strip()].copy()
            match_v_reg = st.session_state["df_vendedores"][st.session_state["df_vendedores"]["Vendedor"].astype(str).str.strip() == vendedor_filtro.strip()]
            nro_ruta_str = match_v_reg.iloc[0]["Nro de Ruta"] if not match_v_reg.empty else "Ruta"

            for sem_nombre, col_dia_campo in [("SEMANA 1", "Día de Visita Semana 1"), ("SEMANA 2", "Día de Visita Semana 2")]:
                elements.append(Paragraph(f"{sem_nombre}", section_style))
                
                matriz_dias = {dia: [] for dia in dias_semana}
                
                for _, r_row in df_vend_subset.iterrows():
                    c_dia_val = normalizar_dia(r_row.get(col_dia_campo, ""))
                    cli_nombre = str(r_row.get("Cliente", ""))
                    cli_ubi = str(r_row.get("Ubicacion", ""))
                    
                    if c_dia_val in matriz_dias and cli_nombre and cli_nombre.lower() != "nan":
                        texto_celda = f"{cli_nombre} - {cli_ubi}" if cli_ubi and cli_ubi.lower() != "nan" else cli_nombre
                        matriz_dias[c_dia_val].append(texto_celda)

                max_filas = max([len(v) for v in matriz_dias.values()] or [1])
                
                headers = [Paragraph(f"#", header_style)] + [Paragraph(d.upper(), header_style) for d in dias_semana]
                tabla_data = [headers]

                for i in range(max_filas):
                    fila_cells = [Paragraph(str(i + 1), cell_style)]
                    for d in dias_semana:
                        lista_clientes_dia = matriz_dias[d]
                        val_txt = lista_clientes_dia[i] if i < len(lista_clientes_dia) else ""
                        fila_cells.append(Paragraph(val_txt, cell_style))
                    tabla_data.append(fila_cells)

                t = Table(tabla_data, colWidths=[22] + [(762 - 22) / 5] * 5, repeatRows=1)
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C5E3B")),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fdfdfd")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d0d0")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                ]))
                elements.append(t)
                elements.append(Spacer(1, 8))

            doc.build(elements)
            buffer.seek(0)
            return buffer.getvalue()

        col_dl_rutas_1, col_dl_rutas_2 = st.columns([2, 3])
        with col_dl_rutas_1:
            pdf_bytes_ruta = generar_pdf_matriz_vendedor(df_seguimiento, vendedor_seleccionado)
            st.download_button(
                label=f"📥 Descargar PDF Ruta ({vendedor_seleccionado})",
                data=pdf_bytes_ruta,
                file_name=f"Ruta_{vendedor_seleccionado.replace(' ', '_')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        st.markdown("---")

        mask_vendedor = df_seguimiento["Vendedor"].astype(str).str.strip() == vendedor_seleccionado.strip()
        col_dia_filtro = "Día de Visita Semana 1" if semana_seleccionada == "Semana 1" else "Día de Visita Semana 2"
        
        def coincide_dia(texto_celda, dia_buscado):
            if pd.isna(texto_celda) or not texto_celda:
                return False
            celda_limpia = str(texto_celda).lower()
            dia_limpio = str(dia_buscado).lower()
            return dia_limpio in celda_limpia or (dia_limpio == "miercoles" and "miércoles" in celda_limpia) or (dia_limpio == "sabado" and "sábado" in celda_limpia)

        mask_dia = df_seguimiento[col_dia_filtro].apply(lambda x: coincide_dia(x, dia_seleccionado))
        df_filtrado = df_seguimiento[mask_vendedor & mask_dia].copy()

        if df_filtrado.empty:
            st.info(f"No se encontraron clientes asignados al vendedor **{vendedor_seleccionado}** para el día **{dia_seleccionado}** en la **{semana_seleccionada}**.")
        else:
            st.success(f"Se encontraron **{len(df_filtrado)}** clientes para esta ruta.")

            cols_a_mostrar = [
                "Nro",
                "Cliente",
                "Ubicacion",
                "Nro de Ruta (Ventas)",
                "Visita_S1", 
                "Pedido_S1", 
                "Motivo_Pedido_S1"
            ]
            
            for c in cols_a_mostrar:
                if c not in df_filtrado.columns:
                    df_filtrado[c] = ""

            df_view = df_filtrado[cols_a_mostrar].copy()

            for col_bool in ["Visita_S1", "Pedido_S1"]:
                if col_bool in df_view.columns:
                    df_view[col_bool] = df_view[col_bool].apply(
                        lambda x: True if str(x).strip().lower() in ["sí", "si", "true", "1", "verdadero"] else False
                    )

            with st.form("form_ruta_vendedores"):
                df_editado_ruta = st.data_editor(
                    df_view,
                    use_container_width=True,
                    num_rows="fixed",
                    key="editor_ruta_vendedores_tabla",
                    hide_index=True,
                    column_config={
                        "Nro": st.column_config.NumberColumn("Nro", disabled=True, width="small"),
                        "Cliente": st.column_config.TextColumn("Cliente", disabled=True, width="medium"),
                        "Ubicacion": st.column_config.TextColumn("Ubicación", disabled=True, width="medium"),
                        "Nro de Ruta (Ventas)": st.column_config.TextColumn("Ruta", disabled=True, width="small"),
                        "Visita_S1": st.column_config.CheckboxColumn("¿Visita S1?", default=False),
                        "Pedido_S1": st.column_config.CheckboxColumn("¿Pedido S1?", default=False),
                        "Motivo_Pedido_S1": st.column_config.TextColumn("Motivo / Observación S1", width="large"),
                    }
                )

                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    guardar_ruta_btn = st.form_submit_button("💾 Guardar y Desplazar Historial", type="primary", use_container_width=True)
                with col_b2:
                    limpiar_semana_btn = st.form_submit_button("🔄 Limpiar Datos en Pantalla", use_container_width=True)

                if guardar_ruta_btn:
                    for s_idx in [1, 2, 3, 4]:
                        for c_field in [f"Visita_S{s_idx}", f"Pedido_S{s_idx}", f"Motivo_Pedido_S{s_idx}"]:
                            if c_field not in st.session_state["df_clientes"].columns:
                                st.session_state["df_clientes"][c_field] = ""

                    for idx, row in df_editado_ruta.iterrows():
                        orig_idx = df_filtrado.index[df_editado_ruta.index.get_loc(idx)]
                        
                        val_visita_str = "Sí" if row["Visita_S1"] else "No"
                        val_pedido_str = "Sí" if row["Pedido_S1"] else "No"

                        st.session_state["df_clientes"].loc[orig_idx, "Visita_S4"] = st.session_state["df_clientes"].loc[orig_idx, "Visita_S3"]
                        st.session_state["df_clientes"].loc[orig_idx, "Pedido_S4"] = st.session_state["df_clientes"].loc[orig_idx, "Pedido_S3"]
                        st.session_state["df_clientes"].loc[orig_idx, "Motivo_Pedido_S4"] = st.session_state["df_clientes"].loc[orig_idx, "Motivo_Pedido_S3"]

                        st.session_state["df_clientes"].loc[orig_idx, "Visita_S3"] = st.session_state["df_clientes"].loc[orig_idx, "Visita_S2"]
                        st.session_state["df_clientes"].loc[orig_idx, "Pedido_S3"] = st.session_state["df_clientes"].loc[orig_idx, "Pedido_S2"]
                        st.session_state["df_clientes"].loc[orig_idx, "Motivo_Pedido_S3"] = st.session_state["df_clientes"].loc[orig_idx, "Motivo_Pedido_S2"]

                        st.session_state["df_clientes"].loc[orig_idx, "Visita_S2"] = st.session_state["df_clientes"].loc[orig_idx, "Visita_S1"]
                        st.session_state["df_clientes"].loc[orig_idx, "Pedido_S2"] = st.session_state["df_clientes"].loc[orig_idx, "Pedido_S1"]
                        st.session_state["df_clientes"].loc[orig_idx, "Motivo_Pedido_S2"] = st.session_state["df_clientes"].loc[orig_idx, "Motivo_Pedido_S1"]

                        st.session_state["df_clientes"].loc[orig_idx, "Visita_S1"] = val_visita_str
                        st.session_state["df_clientes"].loc[orig_idx, "Pedido_S1"] = val_pedido_str
                        st.session_state["df_clientes"].loc[orig_idx, "Motivo_Pedido_S1"] = row["Motivo_Pedido_S1"]

                    guardar_en_base_de_datos(st.session_state["df_clientes"])
                    st.success("¡Estatus guardado y historial refrescado correctamente!")
                    st.rerun()

                if limpiar_semana_btn:
                    for idx, _ in df_editado_ruta.iterrows():
                        orig_idx = df_filtrado.index[df_editado_ruta.index.get_loc(idx)]
                        st.session_state["df_clientes"].loc[orig_idx, ["Visita_S1", "Pedido_S1", "Motivo_Pedido_S1"]] = ""
                    guardar_en_base_de_datos(st.session_state["df_clientes"])
                    st.success("¡Datos de la Semana 1 limpiados con éxito!")
                    st.rerun()

            st.markdown("---")
            st.subheader("📋 Historial de Visitas y Pedidos (Últimas 4 Semanas)")
            
            tabla_historial_data = []
            for _, row_h in df_filtrado.iterrows():
                tabla_historial_data.append({
                    "Ver Detalle": False,
                    "Cliente": row_h.get("Cliente", "No aplica") or "No aplica",
                    "Ubicación": row_h.get("Ubicacion", "No aplica") or "No aplica",
                    "Visita S1": row_h.get("Visita_S1", "No aplica") or "No aplica",
                    "Pedido S1": row_h.get("Pedido_S1", "No aplica") or "No aplica",
                    "Visita S2": row_h.get("Visita_S2", "No aplica") or "No aplica",
                    "Pedido S2": row_h.get("Pedido_S2", "No aplica") or "No aplica",
                    "Visita S3": row_h.get("Visita_S3", "No aplica") or "No aplica",
                    "Pedido S3": row_h.get("Pedido_S3", "No aplica") or "No aplica",
                    "Visita S4": row_h.get("Visita_S4", "No aplica") or "No aplica",
                    "Pedido S4": row_h.get("Pedido_S4", "No aplica") or "No aplica",
                })

            df_tabla_historial = pd.DataFrame(tabla_historial_data)
            df_tabla_historial = df_tabla_historial.fillna("No aplica").replace(r"^\s*$", "No aplica", regex=True)
            
            df_historial_editado = st.data_editor(
                df_tabla_historial,
                use_container_width=True,
                hide_index=True,
                key="editor_tabla_historial_checkboxes",
                column_config={
                    "Ver Detalle": st.column_config.CheckboxColumn("Ver Detalle", default=False, required=True),
                    "Cliente": st.column_config.TextColumn("Cliente"),
                    "Ubicación": st.column_config.TextColumn("Ubicación"),
                    "Visita S1": st.column_config.TextColumn("Visita S1"),
                    "Pedido S1": st.column_config.TextColumn("Pedido S1"),
                    "Visita S2": st.column_config.TextColumn("Visita S2"),
                    "Pedido S2": st.column_config.TextColumn("Pedido S2"),
                    "Visita S3": st.column_config.TextColumn("Visita S3"),
                    "Pedido S3": st.column_config.TextColumn("Pedido S3"),
                    "Visita S4": st.column_config.TextColumn("Visita S4"),
                    "Pedido S4": st.column_config.TextColumn("Pedido S4"),
                }
            )

            # Botón de borrar historial para el vendedor filtrado
            if st.button("🗑️ Borrar Historial de las 4 Semanas (Clientes Filtrados)", type="secondary"):
                for idx, _ in df_filtrado.iterrows():
                    st.session_state["df_clientes"].loc[idx, [
                        "Visita_S1", "Pedido_S1", "Motivo_Pedido_S1",
                        "Visita_S2", "Pedido_S2", "Motivo_Pedido_S2",
                        "Visita_S3", "Pedido_S3", "Motivo_Pedido_S3",
                        "Visita_S4", "Pedido_S4", "Motivo_Pedido_S4"
                    ]] = ""
                guardar_en_base_de_datos(st.session_state["df_clientes"])
                st.success("¡Historial de las 4 semanas borrado con éxito para este vendedor!")
                st.rerun()

            clientes_seleccionados_checkbox = df_historial_editado[df_historial_editado["Ver Detalle"] == True]

            if not clientes_seleccionados_checkbox.empty:
                st.markdown("---")
                st.subheader("📑 Expediente y Motivo Detallado de Clientes Seleccionados")
                
                for _, sel_row in clientes_seleccionados_checkbox.iterrows():
                    nombre_cli = sel_row["Cliente"]
                    ubicacion_cli = sel_row["Ubicación"]

                    match_orig = df_filtrado[(df_filtrado["Cliente"] == nombre_cli) & (df_filtrado["Ubicacion"] == ubicacion_cli)]
                    if not match_orig.empty:
                        c_data = match_orig.iloc[0]
                        ruta_cli = c_data.get("Nro de Ruta (Ventas)", "No aplica")
                        if not ruta_cli or str(ruta_cli).lower() in ["nan", "none", ""]:
                            ruta_cli = "No aplica"

                        with st.container():
                            st.markdown(f"#### 🏢 Cliente: **{nombre_cli}**")
                            col_info1, col_info2 = st.columns(2)
                            with col_info1:
                                st.markdown(f"📍 **Ubicación:** {ubicacion_cli}")
                            with col_info2:
                                st.markdown(f"🚚 **Nro de Ruta:** {ruta_cli}")

                            def limpiar_val(val, default="No aplica"):
                                if pd.isna(val) or str(val).strip() in ["", "nan", "None", "none"]:
                                    return default
                                return str(val)

                            detalle_semanas_rows = [
                                {"Semana": "Semana 1 (Actual)", "Visita": limpiar_val(c_data.get("Visita_S1"), "No"), "Pedido": limpiar_val(c_data.get("Pedido_S1"), "No"), "Motivo / Observación": limpiar_val(c_data.get("Motivo_Pedido_S1"), "No aplica")},
                                {"Semana": "Semana 2", "Visita": limpiar_val(c_data.get("Visita_S2"), "No"), "Pedido": limpiar_val(c_data.get("Pedido_S2"), "No"), "Motivo / Observación": limpiar_val(c_data.get("Motivo_Pedido_S2"), "No aplica")},
                                {"Semana": "Semana 3", "Visita": limpiar_val(c_data.get("Visita_S3"), "No"), "Pedido": limpiar_val(c_data.get("Pedido_S3"), "No"), "Motivo / Observación": limpiar_val(c_data.get("Motivo_Pedido_S3"), "No aplica")},
                                {"Semana": "Semana 4", "Visita": limpiar_val(c_data.get("Visita_S4"), "No"), "Pedido": limpiar_val(c_data.get("Pedido_S4"), "No"), "Motivo / Observación": limpiar_val(c_data.get("Motivo_Pedido_S4"), "No aplica")},
                            ]
                            
                            df_detalle_cliente = pd.DataFrame(detalle_semanas_rows)
                            df_detalle_cliente = df_detalle_cliente.fillna("No aplica").replace(r"^\s*$", "No aplica", regex=True)
                            
                            st.dataframe(
                                df_detalle_cliente,
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "Semana": st.column_config.TextColumn("Período / Semana", width="medium"),
                                    "Visita": st.column_config.TextColumn("¿Visitado?", width="small"),
                                    "Pedido": st.column_config.TextColumn("¿Hubo Pedido?", width="small"),
                                    "Motivo / Observación": st.column_config.TextColumn("Motivo Detallado", width="large"),
                                }
                            )
                            st.markdown("---")
