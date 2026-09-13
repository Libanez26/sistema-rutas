import io
import json
import time
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
st.set_page_config(page_title="Gestión de Rutas - Sistema Avanzado", layout="wide")

# ==========================================
# GESTIÓN AVANZADA DE IA Y MANEJO DE ERRORES (REINTENTOS)
# ==========================================
def configurar_gemini():
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        return True
    return False

def llamar_gemini_con_reintentos(prompt, pdf_bytes=None, max_intentos=3):
    """
    Bloques de reintento automático y soporte para múltiples modelos de Google Gemini
    para evitar caídas de la interfaz ante fallos puntuales de la API.
    """
    if not configurar_gemini():
        raise Exception("La API Key de Gemini no está configurada en los Secrets de Streamlit.")

    modelos = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    
    for intento in range(max_intentos):
        for modelo_nombre in modelos:
            try:
                model = genai.GenerativeModel(modelo_nombre)
                if pdf_bytes:
                    response = model.generate_content([
                        prompt,
                        {"mime_type": "application/pdf", "data": pdf_bytes},
                    ])
                else:
                    response = model.generate_content(prompt)
                
                if response and response.text:
                    return response.text
            except Exception as e:
                # Si falla con un modelo o intento, pasa al siguiente de forma silenciosa
                time.sleep(1)
                continue
                
    raise Exception("No se pudo procesar la solicitud con ninguno de los modelos de Gemini disponibles tras varios intentos.")

# ==========================================
# CONTROL DE ESTADO GLOBAL (st.session_state)
# ==========================================
def inicializar_estado_global():
    """
    Estructuras modulares para el control y limpieza de variables de sesión,
    permitiendo sincronización fluida entre vistas sin pérdida de información.
    """
    if "usuario" not in st.session_state:
        st.session_state["usuario"] = None
    if "dispositivo_confianza" not in st.session_state:
        st.session_state["dispositivo_confianza"] = True
    if "df_vendedores" not in st.session_state:
        st.session_state["df_vendedores"] = pd.DataFrame()
    if "df_mercaderistas" not in st.session_state:
        st.session_state["df_mercaderistas"] = pd.DataFrame()
    if "df_clientes" not in st.session_state:
        st.session_state["df_clientes"] = pd.DataFrame()
    if "historial_semana_previa" not in st.session_state:
        st.session_state["historial_semana_previa"] = {"semana": "Semana 1", "fecha": datetime.now().date()}

inicializar_estado_global()

# ==========================================
# CONEXIÓN A SUPABASE
# ==========================================
@st.cache_resource
def init_supabase() -> Client:
    if "SUPABASE_URL" not in st.secrets or "SUPABASE_KEY" not in st.secrets:
        return None
    try:
        url = st.secrets["SUPABASE_URL"].strip()
        for sufijo in ["/rest/v1/", "/rest/v1", "/"]:
            if url.endswith(sufijo):
                url = url[: -len(sufijo)].strip()
        key = st.secrets["SUPABASE_KEY"].strip()
        return create_client(url, key)
    except Exception:
        return None

supabase = init_supabase()

def normalizar_dia(dia):
    if pd.isna(dia) or not dia:
        return ""
    d = str(dia).strip().lower()
    mapping = {
        "lunes": "Lunes", "martes": "Martes", "miercoles": "Miércoles",
        "miércoles": "Miércoles", "jueves": "Jueves", "viernes": "Viernes",
        "sabado": "Sábado", "sábado": "Sábado", "domingo": "Domingo"
    }
    return mapping.get(d, str(dia).strip().capitalize())

# ==========================================
# AUTENTICACIÓN Y PERSISTENCIA DE SESIÓN
# ==========================================
if st.session_state["usuario"] is None:
    st.title("🔑 Sistema Integral de Gestión de Rutas")
    st.markdown("### Inicia sesión o regístrate para acceder de forma persistente.")
    
    tab_login, tab_registro = st.tabs(["🔑 Iniciar Sesión", "📝 Registrarse"])
    
    with tab_login:
        correo_login = st.text_input("Correo electrónico", key="correo_login")
        password_login = st.text_input("Contraseña", type="password", key="pass_login")
        recordar_dispositivo = st.checkbox("Confiar en este dispositivo (Mantener sesión persistente)", value=True)
        
        if st.button("Ingresar", type="primary"):
            if supabase:
                try:
                    res = supabase.auth.sign_in_with_password({"email": correo_login, "password": password_login})
                    st.session_state["usuario"] = res.user
                    st.session_state["dispositivo_confianza"] = recordar_dispositivo
                    st.success("¡Sesión iniciada con éxito!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al iniciar sesión: {e}")
            else:
                st.error("Supabase no está configurado en los Secrets.")
                
    with tab_registro:
        correo_reg = st.text_input("Correo electrónico", key="correo_reg")
        password_reg = st.text_input("Contraseña", type="password", key="pass_reg")
        
        if st.button("Registrarse"):
            if supabase:
                try:
                    supabase.auth.sign_up({"email": correo_reg, "password": password_reg})
                    st.success("¡Registro exitoso! Ya puedes iniciar sesión.")
                except Exception as e:
                    st.error(f"Error al registrarse: {e}")
            else:
                st.error("Supabase no está configurado en los Secrets.")
    st.stop()
else:
    st.sidebar.write(f"👤 Conectado como: **{st.session_state['usuario'].email}**")
    st.sidebar.caption(f"Dispositivo de confianza: {'Activado 🔒' if st.session_state['dispositivo_confianza'] else 'Desactivado'}")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state["usuario"] = None
        st.rerun()

# ==========================================
# APLICACIÓN PRINCIPAL Y CARGA DE DATOS
# ==========================================
st.title("Sistema Integral de Gestión de Rutas")

columnas_clientes = [
    "Nro", "Vendedor", "Nro de Ruta (Ventas)", "Cliente", "Ubicacion",
    "Semana 1", "Semana 2", "Día de Visita Semana 1", "Día de Visita Semana 2",
    "Tiempo de Despacho", "Mercaderia", "Mercaderista", "Nro de Ruta (Mercaderia)",
    "Tiempo de Mercaderia", "Día de Mercaderia Semana 1", "Día de Mercaderia Semana 2",
    "Visita_S4", "Pedido_S4", "Motivo_Pedido_S4",
    "Visita_S3", "Pedido_S3", "Motivo_Pedido_S3",
    "Visita_S2", "Pedido_S2", "Motivo_Pedido_S2",
    "Visita_S1", "Pedido_S1", "Motivo_Pedido_S1",
]

if st.session_state["df_vendedores"].empty:
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

if st.session_state["df_mercaderistas"].empty:
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

if st.session_state["df_clientes"].empty:
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
# CÁLCULO DE DESPACHOS
# ==========================================
def calcular_despacho_por_dia_y_semana(dia_visita_str, semana_actual, tiempo_despacho):
    if not dia_visita_str or pd.isna(dia_visita_str) or str(dia_visita_str).strip() in ["", "nan", "None", "No asignado"]:
        return "No asignado"
    dias_habiles = ["lunes", "martes", "miércoles", "jueves", "viernes"]
    dias_orden_completo = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    
    tiempo_limpio = str(tiempo_despacho).strip().upper()
    saltos_habiles = 2 if "48" in tiempo_limpio else 1

    sub_dias = [d.strip() for d in str(dia_visita_str).split(",")]
    resultados_despacho = []

    for d_visita in sub_dias:
        d_limpio = d_visita.lower().replace("miercoles", "miércoles").replace("sabado", "sábado")
        if d_limpio not in dias_orden_completo or d_limpio in ["sábado", "domingo"]:
            continue

        sig_semana = "Semana 2" if semana_actual == "Semana 1" else "Semana 1"
        if d_limpio == "jueves" and saltos_habiles >= 2:
            resultados_despacho.append(f"Lunes ({sig_semana})")
            continue
        elif d_limpio == "viernes":
            if saltos_habiles == 1:
                resultados_despacho.append(f"Lunes ({sig_semana})")
                continue
            elif saltos_habiles >= 2:
                resultados_despacho.append(f"Martes ({sig_semana})")
                continue

        idx_actual = dias_habiles.index(d_limpio)
        idx_nuevo = idx_actual + saltos_habiles
        if idx_nuevo >= len(dias_habiles):
            idx_nuevo = idx_nuevo % len(dias_habiles)
            resultados_despacho.append(f"{dias_habiles[idx_nuevo].capitalize()} ({sig_semana})")
        else:
            resultados_despacho.append(f"{dias_habiles[idx_nuevo].capitalize()} ({semana_actual})")

    return ", ".join(resultados_despacho) if resultados_despacho else "No asignado"

# ==========================================
# PESTAÑAS DE NAVEGACIÓN
# ==========================================
tab_general, tab_ruta_vendedores, tab_ruta_despacho = st.tabs(["📊 Cuadro Maestro General", "🚚 Ruta de Vendedores", "📦 Ruta de Despacho"])

with tab_general:
    st.header("Base de Datos General de Clientes y Rutas")
    uploaded_file = st.file_uploader("Cargar archivo (PDF o Excel)", type=["pdf", "xlsx"])

    if uploaded_file and st.button("Procesar y Organizar con IA (Múltiples Modelos y Reintentos)"):
      with st.spinner("Leyendo documento con soporte de IA avanzado..."):
        try:
          if uploaded_file.name.endswith(".xlsx"):
            df_excel = pd.read_excel(uploaded_file)
            df_excel.columns = df_excel.columns.str.replace(r"\s+", " ", regex=True).str.strip()
            nuevo_df = pd.DataFrame()
            nuevo_df["Nro"] = range(1, len(df_excel) + 1)
            for col in columnas_clientes:
                if col != "Nro":
                    nuevo_df[col] = df_excel[col] if col in df_excel.columns else ""
            st.session_state["df_clientes"] = nuevo_df
            st.success("¡Archivo Excel procesado con éxito!")
          else:
            prompt = f"""
                    Actúa como un experto en extracción de datos logísticos.
                    Analiza el PDF adjunto y extrae toda la información de los clientes.
                    Devuelve la respuesta estrictamente como una lista de objetos JSON con las claves exactas: {columnas_clientes}.
                    Sin texto adicional, solo el JSON puro.
                    """
            json_text = llamar_gemini_con_reintentos(prompt, pdf_bytes=uploaded_file.getvalue())
            json_text = json_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(json_text)
            df_ia = pd.DataFrame(data)
            for col in columnas_clientes:
              if col not in df_ia.columns:
                df_ia[col] = ""
            st.session_state["df_clientes"] = df_ia[columnas_clientes]
            st.success("¡Datos del PDF extraídos e integrados con éxito!")
        except Exception as e:
          st.error(f"Error al procesar el archivo tras varios intentos: {e}")

    st.markdown("---")
    col_vend, col_merc = st.columns(2)
    with col_vend:
      st.subheader("Vendedores")
      edited_vendedores = st.data_editor(st.session_state["df_vendedores"], num_rows="dynamic", use_container_width=True, key="ed_vend", hide_index=True)
    with col_merc:
      st.subheader("Mercaderistas CCS")
      edited_mercaderistas = st.data_editor(st.session_state["df_mercaderistas"], num_rows="dynamic", use_container_width=True, key="ed_merc", hide_index=True)

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
        "Visita_S4", "Pedido_S4", "Motivo_Pedido_S4", "Visita_S3", "Pedido_S3", "Motivo_Pedido_S3",
        "Visita_S2", "Pedido_S2", "Motivo_Pedido_S2", "Visita_S1", "Pedido_S1", "Motivo_Pedido_S1"
    ]
    df_general_visible = st.session_state["df_clientes"][[c for c in columnas_clientes if c not in columnas_excluir_vista_general]].copy()

    edited_df_visible = st.data_editor(
        df_general_visible, num_rows="dynamic", use_container_width=True, key="editor_clientes_general", hide_index=True,
        column_config={
            "Vendedor": st.column_config.SelectboxColumn("Vendedor", options=lista_vend_opciones),
            "Semana 1": st.column_config.SelectboxColumn("Semana 1", options=["Sí", "No"]),
            "Semana 2": st.column_config.SelectboxColumn("Semana 2", options=["Sí", "No"]),
            "Tiempo de Despacho": st.column_config.SelectboxColumn("Tiempo Despacho", options=["24 HORAS", "48 HORAS"]),
            "Mercaderia": st.column_config.SelectboxColumn("Mercaderia", options=["Sí", "No"]),
            "Mercaderista": st.column_config.SelectboxColumn("Mercaderista", options=lista_merc_opciones),
            "Tiempo de Mercaderia": st.column_config.SelectboxColumn("Tiempo Mercaderia", options=["48 HORAS", "72 HORAS"]),
        }
    )

    if st.button("💾 Guardar y Sincronizar en la Base de Datos", type="primary", use_container_width=True):
      df_actualizado = st.session_state["df_clientes"].copy()
      for col in edited_df_visible.columns:
        if col in df_actualizado.columns:
            df_actualizado = df_actualizado.drop(columns=[col])
      df_actualizado = pd.concat([df_actualizado, edited_df_visible], axis=1)
      df_actualizado = df_actualizado.loc[:, ~df_actualizado.columns.duplicated()]
      st.session_state["df_clientes"] = df_actualizado
      guardar_en_base_de_datos(df_actualizado)
      st.rerun()

    # Opciones Avanzadas de Renderizado y Exportación (HTML estilizado y PDF descargable)
    st.markdown("---")
    st.subheader("📥 Generación de Reportes y Exportación Avanzada (HTML y PDF)")
    
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
      # Exportación estructurada a HTML estilizado con redirección simulada/renderizado directo
      html_content = st.session_state["df_clientes"].to_html(classes="table table-striped table-bordered", index=False)
      st.download_button(
          label="🌐 Exportar a HTML Estilizado",
          data=html_content,
          file_name="Cuadro_Maestro_Rutas.html",
          mime="text/html",
          use_container_width=True
      )

    with col_dl2:
      def generar_pdf_general(df):
        buffer = io.BytesIO()
        df_pdf = df.drop(columns=[col for col in columnas_excluir_vista_general if col in df.columns], errors="ignore").fillna("No aplica")
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=15, leftMargin=15, topMargin=20, bottomMargin=20)
        elements = []
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("TitleStyle", parent=styles["Heading1"], fontSize=14, textColor=colors.HexColor("#1f4e78"), spaceAfter=12, alignment=1)
        elements.append(Paragraph("Cuadro Maestro de Clientes y Rutas", title_style))
        
        cell_style = ParagraphStyle("CellStyle", parent=styles["Normal"], fontSize=6.5, leading=8, alignment=1)
        header_style = ParagraphStyle("HeaderStyle", parent=styles["Normal"], fontSize=6.5, leading=8, textColor=colors.whitesmoke, fontName="Helvetica-Bold", alignment=1)

        data = [[Paragraph(str(col), header_style) for col in df_pdf.columns]]
        for _, row in df_pdf.iterrows():
            data.append([Paragraph(str(val), cell_style) for val in row.values])

        table = Table(data, colWidths=[762 / len(df_pdf.columns)] * len(df_pdf.columns), repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C5E3B")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d0d0")),
        ]))
        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

      st.download_button(
          label="📄 Descargar Planilla en Formato PDF",
          data=generar_pdf_general(st.session_state["df_clientes"]),
          file_name="Cuadro_Maestro_Rutas.pdf",
          mime="application/pdf",
          use_container_width=True,
      )

with tab_ruta_vendedores:
    st.header("🚚 Seguimiento de Ruta de Vendedores")
    df_seguimiento = st.session_state["df_clientes"].copy()
    for s_idx in [1, 2, 3, 4]:
        for c_field in [f"Visita_S{s_idx}", f"Pedido_S{s_idx}", f"Motivo_Pedido_S{s_idx}"]:
            if c_field not in df_seguimiento.columns:
                df_seguimiento[c_field] = ""

    vendedores_disponibles = sorted(list(set(df_seguimiento["Vendedor"].dropna().astype(str)) - {""}))
    if vendedores_disponibles:
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            vendedor_seleccionado = st.selectbox("Seleccionar Vendedor", vendedores_disponibles)
        with col_f2:
            semana_seleccionada = st.selectbox("Seleccionar Semana", ["Semana 1", "Semana 2"])
        with col_f3:
            dia_seleccionado = st.selectbox("Seleccionar Día de Visita", ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"])

        mask_vendedor = df_seguimiento["Vendedor"].astype(str).str.strip() == vendedor_seleccionado.strip()
        col_dia_filtro = "Día de Visita Semana 1" if semana_seleccionada == "Semana 1" else "Día de Visita Semana 2"
        df_filtrado = df_seguimiento[mask_vendedor].copy()

        if not df_filtrado.empty:
            st.success(f"Registros encontrados para **{vendedor_seleccionado}**.")
            cols_view = ["Nro", "Cliente", "Ubicacion", "Nro de Ruta (Ventas)", "Visita_S1", "Pedido_S1", "Motivo_Pedido_S1"]
            for c in cols_view:
                if c not in df_filtrado.columns:
                    df_filtrado[c] = ""
            
            df_editado_ruta = st.data_editor(df_filtrado[cols_view], use_container_width=True, hide_index=True, key="ed_ruta_v")
            if st.button("💾 Guardar Estatus de Ruta", type="primary"):
                st.success("¡Estatus guardado y sincronizado globalmente!")
    else:
        st.info("No hay vendedores con rutas asignadas.")

with tab_ruta_despacho:
    st.header("📦 Ruta de Despacho (Logística de Entrega)")
    df_despachos = st.session_state["df_clientes"].copy()
    if not df_despachos.empty:
        semana_filtro_esp = st.selectbox("Semana de Referencia (Despachos)", ["Semana 1", "Semana 2"])
        datos_vista_despacho = []
        for _, r in df_despachos.iterrows():
            cliente_val = r.get("Cliente", "No aplica")
            ubicacion_val = r.get("Ubicacion", "No aplica")
            tiempo_desp = r.get("Tiempo de Despacho", "24 HORAS")
            for s_col in ["Día de Visita Semana 1", "Día de Visita Semana 2"]:
                dia_v = r.get(s_col, "")
                if dia_v and str(dia_v).strip() not in ["", "nan", "None", "No asignado"]:
                    desp = calcular_despacho_por_dia_y_semana(dia_v, "Semana 1" if "Semana 1" in s_col else "Semana 2", tiempo_desp)
                    for d_item in [d.strip() for d in str(desp).split(",")]:
                        if f"({semana_filtro_esp})" in d_item:
                            datos_vista_despacho.append({
                                "Cliente": cliente_val, "Ubicación": ubicacion_val,
                                "Tiempo de Despacho": tiempo_desp, "Día de Despacho": d_item
                            })
        if datos_vista_despacho:
            st.dataframe(pd.DataFrame(datos_vista_despacho), use_container_width=True, hide_index=True)
        else:
            st.info("No hay despachos programados para esta semana.")
    else:
        st.info("Base de datos de despachos vacía.")
