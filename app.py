import io
import json
import pandas as pd
import streamlit as st
import google.generativeai as genai
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
    # Historial de 4 semanas rodantes para visitas y pedidos
    "Visita_S4", "Pedido_S4", "Motivo_Pedido_S4",
    "Visita_S3", "Pedido_S3", "Motivo_Pedido_S3",
    "Visita_S2", "Pedido_S2", "Motivo_Pedido_S2",
    "Visita_S1", "Pedido_S1", "Motivo_Pedido_S1",
]

# Cargar Vendedores desde Supabase o usar valores por defecto
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
          {"Vendedor": "Dairo Bello", "Nro de Ruta": "Ruta 01"},
          {"Vendedor": "Jhony Moreno", "Nro de Ruta": "Ruta 02"},
      ])
  else:
    st.session_state["df_vendedores"] = pd.DataFrame([
        {"Vendedor": "Dairo Bello", "Nro de Ruta": "Ruta 01"},
        {"Vendedor": "Jhony Moreno", "Nro de Ruta": "Ruta 02"},
    ])

# Cargar Mercaderistas desde Supabase o usar valores por defecto
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

# Cargar Clientes desde Supabase al iniciar
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

# ==========================================
# PESTAÑAS PRINCIPALES (GENERAL Y RUTA DE VENDEDORES)
# ==========================================
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

    with st.form("form_cuadro_maestro"):
      edited_df = st.data_editor(
          st.session_state["df_clientes"],
          num_rows="dynamic",
          use_container_width=True,
          key="editor_clientes",
          hide_index=True,
          column_config={
              "Nro": st.column_config.NumberColumn("Nro", required=True),
              "Vendedor": st.column_config.SelectboxColumn("Vendedor", options=lista_vend_opciones, required=False),
              "Nro de Ruta (Ventas)": st.column_config.TextColumn("Nro de Ruta (Ventas)"),
              "Cliente": st.column_config.TextColumn("Cliente", required=True),
              "Ubicacion": st.column_config.TextColumn("Ubicacion"),
              "Semana 1": st.column_config.SelectboxColumn("Semana 1", options=["Sí", "No"]),
              "Semana 2": st.column_config.SelectboxColumn("Semana 2", options=["Sí", "No"]),
              "Día de Visita Semana 1": st.column_config.TextColumn("Día Visita S1"),
              "Día de Visita Semana 2": st.column_config.TextColumn("Día Visita S2"),
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
        df = edited_df.copy()
        if not df.empty:
          if len(df) > 1:
            ultima_fila = df.iloc[-1]
            cliente_val = ultima_fila.get("Cliente", "")
            if pd.isna(cliente_val) or str(cliente_val).strip() == "":
              fila_anterior = df.iloc[-2].copy()
              for col in df.columns:
                if col != "Cliente" and col != "Nro":
                  df.at[df.index[-1], col] = fila_anterior[col]
              try:
                df.at[df.index[-1], "Nro"] = int(fila_anterior["Nro"]) + 1
              except:
                pass

          df_v = st.session_state["df_vendedores"]
          df_m = st.session_state["df_mercaderistas"]

          for idx, row in df.iterrows():
            vendedor_actual = row.get("Vendedor")
            if pd.notna(vendedor_actual) and str(vendedor_actual).strip() != "":
              match_v = df_v[df_v["Vendedor"] == vendedor_actual]
              if not match_v.empty:
                df.at[idx, "Nro de Ruta (Ventas)"] = match_v.iloc[0]["Nro de Ruta"]

            merc_actual = row.get("Mercaderista")
            if pd.notna(merc_actual) and str(merc_actual).strip() != "":
              match_m = df_m[df_m["Mercaderista"] == merc_actual]
              if not match_m.empty:
                df.at[idx, "Nro de Ruta (Mercaderia)"] = match_m.iloc[0]["Nro de Ruta"]

        st.session_state["df_clientes"] = df
        guardar_en_base_de_datos(df)
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
      def generar_pdf(df):
        buffer = io.BytesIO()
        
        # Columnas que deseas excluir del PDF
        columnas_a_excluir = [
            "Visita_S4", "Pedido_S4", "Motivo_Pedido_S4",
            "Visita_S3", "Pedido_S3", "Motivo_Pedido_S3",
            "Visita_S2", "Pedido_S2", "Motivo_Pedido_S2",
            "Visita_S1", "Pedido_S1", "Motivo_Pedido_S1",
        ]
        
        # Filtrar el DataFrame para remover las columnas del historial y rellenar celdas vacías con "No aplica"
        df_pdf = df.drop(columns=[col for col in columnas_a_excluir if col in df.columns], errors="ignore")
        df_pdf = df_pdf.fillna("No aplica")
        df_pdf = df_pdf.replace(r"^\s*$", "No aplica", regex=True)

        doc = SimpleDocTemplate(
            buffer, 
            pagesize=landscape(letter), 
            rightMargin=15, 
            leftMargin=15, 
            topMargin=20, 
            bottomMargin=20
        )
        elements = []

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TitleStyle",
            parent=styles["Heading1"],
            fontSize=14,
            textColor=colors.HexColor("#1f4e78"),
            spaceAfter=12,
            alignment=1,
        )

        elements.append(Paragraph("Cuadro Maestro de Clientes y Rutas", title_style))
        elements.append(Spacer(1, 5))

        cell_style = ParagraphStyle(
            "CellStyle",
            parent=styles["Normal"],
            fontSize=6.5,
            leading=8,
            alignment=1,
        )
        
        header_style = ParagraphStyle(
            "HeaderStyle",
            parent=styles["Normal"],
            fontSize=6.5,
            leading=8,
            textColor=colors.whitesmoke,
            fontName="Helvetica-Bold",
            alignment=1,
        )

        data = []
        header_row = [Paragraph(str(col), header_style) for col in df_pdf.columns]
        data.append(header_row)

        for _, row in df_pdf.iterrows():
            row_data = [Paragraph(str(val), cell_style) for val in row.values]
            data.append(row_data)

        # Ancho total disponible en la hoja horizontal (letter landscape = 792 pt, menos márgenes 30 pt = 762 pt)
        # Distribuimos el ancho total proporcionalmente entre las columnas de df_pdf para que abarque más de la hoja
        ancho_total_disponible = 762
        num_columnas = len(df_pdf.columns)
        col_widths = [ancho_total_disponible / num_columnas] * num_columnas

        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C5E3B")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                ("TOPPADDING", (0, 0), (-1, 0), 5),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fdfdfd")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d0d0")),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
                ("TOPPADDING", (0, 1), (-1, -1), 4),
            ])
        )

        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

      pdf_data = generar_pdf(st.session_state["df_clientes"])
      st.download_button(
          label="📥 Descargar en Formato PDF",
          data=pdf_data,
          file_name="Cuadro_Maestro_Rutas.pdf",
          mime="application/pdf",
          use_container_width=True,
      )

with tab_ruta_vendedores:
    st.header("Seguimiento de Ruta de Vendedores")
    st.markdown("Filtra por vendedor, semana de trabajo y día de visita para gestionar el estatus actual de la semana.")

    df_seguimiento = st.session_state["df_clientes"].copy()
    
    # Asegurar columnas de historial
    for s_idx in [1, 2, 3, 4]:
        for c_field in [f"Visita_S{s_idx}", f"Pedido_S{s_idx}", f"Motivo_Pedido_S{s_idx}"]:
            if c_field not in df_seguimiento.columns:
                df_seguimiento[c_field] = ""

    vendedores_disponibles = sorted(list(set(df_seguimiento["Vendedor"].dropna().astype(str)) - {""}))
    
    if not vendedores_disponibles:
        st.warning("No hay vendedores registrados aún. Carga o ingresa información en el Cuadro Maestro primero.")
    else:
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            vendedor_seleccionado = st.selectbox("Seleccionar Vendedor", vendedores_disponibles, key="filtro_vendedor_ruta")
            
        with col_f2:
            semana_seleccionada = st.selectbox("Seleccionar Semana", ["Semana 1", "Semana 2"], key="filtro_semana_ruta")

        with col_f3:
            dias_opciones = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            dia_seleccionado = st.selectbox("Seleccionar Día de Visita", dias_opciones, key="filtro_dia_ruta")

        mask_vendedor = df_seguimiento["Vendedor"].astype(str).str.strip() == vendedor_seleccionado.strip()
        
        col_dia_filtro = "Día de Visita Semana 1" if semana_seleccionada == "Semana 1" else "Día de Visita Semana 2"
        mask_dia = df_seguimiento[col_dia_filtro].astype(str).str.contains(dia_seleccionado, case=False, na=False)
        
        df_filtrado = df_seguimiento[mask_vendedor & mask_dia].copy()

        if df_filtrado.empty:
            st.info(f"No se encontraron clientes asignados al vendedor **{vendedor_seleccionado}** para el día **{dia_seleccionado}** en la **{semana_seleccionada}**.")
        else:
            st.success(f"Se encontraron **{len(df_filtrado)}** clientes para esta ruta.")

            # Únicamente columnas de la semana actual en la tabla principal
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

            df_view = df_filtrado[cols_a_mostrar]

            with st.form("form_ruta_vendedores"):
                df_editado_ruta = st.data_editor(
                    df_view,
                    use_container_width=True,
                    num_rows="fixed",
                    key="editor_ruta_vendedores",
                    hide_index=True,
                    column_config={
                        "Nro": st.column_config.NumberColumn("Nro", disabled=True),
                        "Cliente": st.column_config.TextColumn("Cliente", disabled=True),
                        "Ubicacion": st.column_config.TextColumn("Ubicación", disabled=True),
                        "Nro de Ruta (Ventas)": st.column_config.TextColumn("Ruta", disabled=True),
                        "Visita_S1": st.column_config.SelectboxColumn("Visita S1 (Actual)", options=["Sí", "No"], required=True),
                        "Pedido_S1": st.column_config.SelectboxColumn("Pedido S1 (Actual)", options=["Sí", "No"], required=True),
                        "Motivo_Pedido_S1": st.column_config.TextColumn("Motivo S1 (Actual)"),
                    }
                )

                guardar_ruta_btn = st.form_submit_button("💾 Guardar y Desplazar Historial (4 Semanas)", type="primary", use_container_width=True)

                if guardar_ruta_btn:
                    for s_idx in [1, 2, 3, 4]:
                        for c_field in [f"Visita_S{s_idx}", f"Pedido_S{s_idx}", f"Motivo_Pedido_S{s_idx}"]:
                            if c_field not in st.session_state["df_clientes"].columns:
                                st.session_state["df_clientes"][c_field] = ""

                    for idx, row in df_editado_ruta.iterrows():
                        orig_idx = df_filtrado.index[df_editado_ruta.index.get_loc(idx)]
                        
                        # Rotación FIFO de 4 semanas
                        st.session_state["df_clientes"].loc[orig_idx, "Visita_S4"] = st.session_state["df_clientes"].loc[orig_idx, "Visita_S3"]
                        st.session_state["df_clientes"].loc[orig_idx, "Pedido_S4"] = st.session_state["df_clientes"].loc[orig_idx, "Pedido_S3"]
                        st.session_state["df_clientes"].loc[orig_idx, "Motivo_Pedido_S4"] = st.session_state["df_clientes"].loc[orig_idx, "Motivo_Pedido_S3"]

                        st.session_state["df_clientes"].loc[orig_idx, "Visita_S3"] = st.session_state["df_clientes"].loc[orig_idx, "Visita_S2"]
                        st.session_state["df_clientes"].loc[orig_idx, "Pedido_S3"] = st.session_state["df_clientes"].loc[orig_idx, "Pedido_S2"]
                        st.session_state["df_clientes"].loc[orig_idx, "Motivo_Pedido_S3"] = st.session_state["df_clientes"].loc[orig_idx, "Motivo_Pedido_S2"]

                        st.session_state["df_clientes"].loc[orig_idx, "Visita_S2"] = st.session_state["df_clientes"].loc[orig_idx, "Visita_S1"]
                        st.session_state["df_clientes"].loc[orig_idx, "Pedido_S2"] = st.session_state["df_clientes"].loc[orig_idx, "Pedido_S1"]
                        st.session_state["df_clientes"].loc[orig_idx, "Motivo_Pedido_S2"] = st.session_state["df_clientes"].loc[orig_idx, "Motivo_Pedido_S1"]

                        # Guardar los datos ingresados en S1
                        st.session_state["df_clientes"].loc[orig_idx, "Visita_S1"] = row["Visita_S1"]
                        st.session_state["df_clientes"].loc[orig_idx, "Pedido_S1"] = row["Pedido_S1"]
                        st.session_state["df_clientes"].loc[orig_idx, "Motivo_Pedido_S1"] = row["Motivo_Pedido_S1"]

                    guardar_en_base_de_datos(st.session_state["df_clientes"])
                    st.success("¡Estatus guardado! El historial rotativo de 4 semanas se ha actualizado correctamente.")
                    st.rerun()

            # SECCIÓN INFERIOR: Historial limpio y Detalle por cliente
            st.markdown("---")
            st.subheader("📋 Historial de Visitas y Motivos de Pedido (Últimas 4 Semanas)")
            st.markdown("Resumen general con la ubicación del cliente y desglose detallado por semana:")

            tabla_historial_data = []
            for _, row_h in df_filtrado.iterrows():
                tabla_historial_data.append({
                    "Cliente": row_h.get("Cliente", ""),
                    "Ubicación": row_h.get("Ubicacion", ""),
                    "S1 (Visita | Pedido)": f"Visita: {row_h.get('Visita_S1', 'No') or 'No'} | Pedido: {row_h.get('Pedido_S1', 'No') or 'No'}",
                    "S2 (Visita | Pedido)": f"Visita: {row_h.get('Visita_S2', 'No') or 'No'} | Pedido: {row_h.get('Pedido_S2', 'No') or 'No'}",
                    "S3 (Visita | Pedido)": f"Visita: {row_h.get('Visita_S3', 'No') or 'No'} | Pedido: {row_h.get('Pedido_S3', 'No') or 'No'}",
                    "S4 (Visita | Pedido)": f"Visita: {row_h.get('Visita_S4', 'No') or 'No'} | Pedido: {row_h.get('Pedido_S4', 'No') or 'No'}",
                })

            df_tabla_historial = pd.DataFrame(tabla_historial_data)
            
            st.dataframe(
                df_tabla_historial,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Cliente": st.column_config.TextColumn("Cliente"),
                    "Ubicación": st.column_config.TextColumn("Ubicación"),
                    "S1 (Visita | Pedido)": st.column_config.TextColumn("S1"),
                    "S2 (Visita | Pedido)": st.column_config.TextColumn("S2"),
                    "S3 (Visita | Pedido)": st.column_config.TextColumn("S3"),
                    "S4 (Visita | Pedido)": st.column_config.TextColumn("S4"),
                }
            )

            st.markdown("---")
            st.subheader("🔍 Motivo detallado por Cliente (Semana Actual)")
            
            # Crear una etiqueta única combinando el nombre del cliente y su ubicación para diferenciar duplicados
            df_filtrado["Cliente_Display"] = df_filtrado["Cliente"].astype(str) + " — Ubicación: " + df_filtrado["Ubicacion"].astype(str)
            clientes_opciones_display = df_filtrado["Cliente_Display"].tolist()

            if clientes_opciones_display:
                cliente_seleccionado_display = st.selectbox(
                    "Selecciona el cliente y su ubicación para ver el detalle y motivo del pedido (S1):", 
                    clientes_opciones_display, 
                    key="select_detalle_motivo_ubicacion"
                )
                
                cliente_row = df_filtrado[df_filtrado["Cliente_Display"] == cliente_seleccionado_display]
                if not cliente_row.empty:
                    motivo_s1 = cliente_row.iloc[0].get("Motivo_Pedido_S1", "")
                    ubicacion_cliente = cliente_row.iloc[0].get("Ubicacion", "")
                    
                    st.info(f"📍 **Ubicación:** {ubicacion_cliente if ubicacion_cliente else 'No especificada'}")
                    st.success(f"📝 **Motivo del Pedido (Semana 1):** {motivo_s1 if motivo_s1 else 'No se registró ningún motivo para esta semana.'}")
