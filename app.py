import io
import json
import time
import pandas as pd
import streamlit as st
import google.generativeai as genai
from datetime import datetime, timedelta
from supabase import create_client, Client

# Configuración inicial de la página
st.set_page_config(page_title="Gestión Integral de Rutas", layout="wide")

# ==========================================
# GESTIÓN AVANZADA DE IA Y MANEJO DE ERRORES
# ==========================================
def configurar_gemini():
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        return True
    return False

def llamar_gemini_con_reintentos(prompt, pdf_bytes=None, max_intentos=3):
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
            except Exception:
                time.sleep(1)
                continue
                
    raise Exception("No se pudo procesar la solicitud con ninguno de los modelos de Gemini disponibles tras varios intentos.")

# ==========================================
# CONTROL DE ESTADO GLOBAL (st.session_state)
# ==========================================
def inicializar_estado_global():
    if "usuario" not in st.session_state:
        st.session_state["usuario"] = None
    if "dispositivo_confianza" not in st.session_state:
        st.session_state["dispositivo_confianza"] = True
    if "df_vendedores" not in st.session_state:
        st.session_state["df_vendedores"] = pd.DataFrame()
    if "df_mercaderistas" not in st.session_state:
        st.session_state["df_mercaderistas"] = pd.DataFrame()
    if "df_tiempos" not in st.session_state:
        st.session_state["df_tiempos"] = pd.DataFrame()
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
    """
    Corrige errores ortográficos, mayúsculas, tildes y variaciones 
    en los días de la semana (ej: miercoles -> Miércoles).
    """
    if pd.isna(dia) or not dia:
        return ""
    
    # Limpiar posibles días múltiples separados por coma (ej: "Lunes, miercoles")
    sub_dias = [d.strip() for d in str(dia).split(",")]
    dias_corregidos = []
    
    mapping = {
        "lunes": "Lunes", 
        "martes": "Martes", 
        "miercoles": "Miércoles", "miércoles": "Miércoles", 
        "jueves": "Jueves", 
        "viernes": "Viernes"
    }
    
    for d in sub_dias:
        d_limpio = d.lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
        # Mapeo flexible eliminando tildes para comparar sin errores
        if "lunes" in d_limpio:
            dias_corregidos.append("Lunes")
        elif "martes" in d_limpio:
            dias_corregidos.append("Martes")
        elif "mierc" in d_limpio or "mierc" in d_limpio:
            dias_corregidos.append("Miércoles")
        elif "jueves" in d_limpio:
            dias_corregidos.append("Jueves")
        elif "viernes" in d_limpio:
            dias_corregidos.append("Viernes")
        else:
            # Si viene otro valor, intentar formatearlo limpio
            mapped = mapping.get(d.lower(), d.strip().capitalize())
            if mapped in ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]:
                dias_corregidos.append(mapped)
                
    return ", ".join(dias_corregidos) if dias_corregidos else str(dia).strip()

def normalizar_tiempo_despacho(val):
    if pd.isna(val) or not val:
        return "24 horas"
    s = str(val).strip().lower()
    if "24" in s:
        return "24 horas"
    elif "48" in s:
        return "48 horas"
    elif "72" in s:
        return "72 horas"
    return str(val).strip().capitalize()

# ==========================================
# GESTIÓN DE AUTENTICACIÓN
# ==========================================
if st.session_state["usuario"] is None:
    st.title("🔑 Sistema Integral de Gestión de Rutas")
    st.markdown("### Inicia sesión o regístrate para acceder a la plataforma.")
    
    tab_login, tab_registro = st.tabs(["🔑 Iniciar Sesión", "📝 Registrarse"])
    
    with tab_login:
        st.subheader("Acceso a tu cuenta")
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
                st.error("Supabase não está configurado correctamente en los Secrets.")
                
    with tab_registro:
        st.subheader("Crear una cuenta nueva")
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
# APLICACIÓN PRINCIPAL
# ==========================================
st.title("Sistema Integral de Gestión de Rutas")

columnas_clientes = [
    "Nro", "Vendedor", "Nro de Ruta (Ventas)", "Cliente", "Ubicacion",
    "Semana 1", "Semana 2", "Día de Visita Semana 1", "Día de Visita Semana 2",
    "Tiempo de Despacho", "Mercaderia", "Mercaderista", "Nro de Ruta (Mercaderia)",
    "Día de Mercaderia Semana 1", "Día de Mercaderia Semana 2",
    "Visita_S1", "Pedido_S1", "Motivo_Pedido_S1",
    "Visita_S2", "Pedido_S2", "Motivo_Pedido_S2"
]

# Carga de personal y tiempos
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

if st.session_state["df_tiempos"].empty:
  if supabase:
    try:
      res_t = supabase.table("personal_rutas").select("*").eq("tipo", "tiempo_despacho").execute()
      if res_t.data:
        st.session_state["df_tiempos"] = pd.DataFrame(res_t.data).rename(columns={"Vendedor": "Tiempo de Despacho"})[["Tiempo de Despacho"]]
      else:
        raise Exception()
    except:
      st.session_state["df_tiempos"] = pd.DataFrame([
          {"Tiempo de Despacho": "24 horas"},
          {"Tiempo de Despacho": "48 horas"},
      ])
  else:
    st.session_state["df_tiempos"] = pd.DataFrame([
        {"Tiempo de Despacho": "24 horas"},
        {"Tiempo de Despacho": "48 horas"},
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
            df_temp[col] = False if ("Visita_" in col or "Pedido_" in col) else ""
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

      for _, row in st.session_state["df_tiempos"].dropna(subset=["Tiempo de Despacho"]).iterrows():
        if str(row["Tiempo de Despacho"]).strip() != "":
          registros_personal.append({"tipo": "tiempo_despacho", "Vendedor": str(row["Tiempo de Despacho"]), "Nro de Ruta": ""})

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
    
    t_norm = normalizar_tiempo_despacho(tiempo_despacho)
    saltos_habiles = 2 if "48" in t_norm else (3 if "72" in t_norm else 1)

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

# Pestañas de la aplicación
tab_general, tab_ruta_vendedores, tab_ruta_despacho = st.tabs(["📊 Cuadro Maestro General", "🚚 Ruta de Vendedores", "📦 Ruta de Despacho"])

with tab_general:
    st.header("Base de Datos General de Clientes y Rutas")
    st.markdown("Sube tu archivo Excel o PDF para procesar la información de forma automatizada.")

    uploaded_file = st.file_uploader("Cargar archivo (PDF o Excel)", type=["pdf", "xlsx"])

    if uploaded_file and st.button("Procesar y Organizar con IA"):
      with st.spinner("Leyendo documento con soporte de IA avanzado..."):
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
                "Día de Visita Semana 1": "Día de Visita Semana 1",
                "Día de Visita Semana 2": "Día de Visita Semana 2",
                "Día de Mercaderia Semana 1": "Día de Mercaderia Semana 1",
                "Día de Mercaderia Semana 2": "Día de Mercaderia Semana 2",
            }

            base_cols_maestro = [c for c in columnas_clientes if not c.startswith("Visita_") and not c.startswith("Pedido_") and not c.startswith("Motivo_")]
            for col_target in base_cols_maestro:
              if col_target not in nuevo_df.columns:
                nuevo_df[col_target] = ""
              if col_target == "Nro":
                continue

              encontrada = False
              for orig, dest in mapping_cols.items():
                if dest == col_target and orig in df_excel.columns:
                  nuevo_df[col_target] = df_excel[orig]
                  encontrada = True
                  break

              if not encontrada:
                for col_excel in df_excel.columns:
                  if " ".join(col_excel.split()).lower() == " ".join(col_target.split()).lower():
                    nuevo_df[col_target] = df_excel[col_excel]
                    break

            # Normalizar automáticamente tildes y errores en días de visita al cargar Excel
            for col_d in ["Día de Visita Semana 1", "Día de Visita Semana 2", "Día de Mercaderia Semana 1", "Día de Mercaderia Semana 2"]:
                if col_d in nuevo_df.columns:
                    nuevo_df[col_d] = nuevo_df[col_d].apply(normalizar_dia)

            if "Tiempo de Despacho" in nuevo_df.columns:
                nuevo_df["Tiempo de Despacho"] = nuevo_df["Tiempo de Despacho"].apply(normalizar_tiempo_despacho)

            for c in ["Semana 1", "Semana 2", "Mercaderia"]:
              if c in nuevo_df.columns:
                nuevo_df[c] = nuevo_df[c].replace({"Si": "Sí", "si": "Sí", "SI": "Sí", "no": "No", "NO": "No"})

            for c in columnas_clientes:
                if c not in nuevo_df.columns:
                    nuevo_df[c] = False if ("Visita_" in c or "Pedido_" in c) else ""

            st.session_state["df_clientes"] = nuevo_df[columnas_clientes]
            st.success("¡Archivo Excel procesado con éxito y normalizado!")
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
                df_ia[col] = False if ("Visita_" in col or "Pedido_" in col) else ""
            st.session_state["df_clientes"] = df_ia[columnas_clientes]
            st.success("¡Datos del PDF extraídos e integrados con éxito!")
        except Exception as e:
          st.error(f"Error al procesar el archivo tras varios intentos: {e}")

    st.markdown("---")

    with st.expander("👁️ Configuración de Vendedores, Mercaderistas y Tiempos de Despacho (Ocultar / Mostrar)", expanded=True):
        col_vend, col_merc, col_tiem = st.columns(3)
        
        with col_vend:
          st.subheader("Vendedores")
          edited_vendedores = st.data_editor(st.session_state["df_vendedores"], num_rows="dynamic", use_container_width=True, key="editor_vendedores_inline", hide_index=True)

        with col_merc:
          st.subheader("Mercaderistas CCS")
          edited_mercaderistas = st.data_editor(st.session_state["df_mercaderistas"], num_rows="dynamic", use_container_width=True, key="editor_mercaderistas_inline", hide_index=True)

        with col_tiem:
          st.subheader("Tiempos de Despacho")
          edited_tiempos = st.data_editor(st.session_state["df_tiempos"], num_rows="dynamic", use_container_width=True, key="editor_tiempos_inline", hide_index=True)

        if st.button("💾 Guardar Cambios de Personal y Tiempos", use_container_width=True):
          st.session_state["df_vendedores"] = edited_vendedores
          st.session_state["df_mercaderistas"] = edited_mercaderistas
          st.session_state["df_tiempos"] = edited_tiempos
          guardar_en_base_de_datos(st.session_state["df_clientes"])
          st.rerun()

    st.markdown("---")
    st.subheader("Cuadro Maestro de Clientes")
    
    texto_busqueda = st.text_input("🔍 Búsqueda rápida (Ctrl+B / Escribe cliente, mercaderista, ruta...):", placeholder="Ej: Ruta 01, La Muralla, Yorsin, Caracas...")

    lista_vend_opciones = st.session_state["df_vendedores"]["Vendedor"].dropna().tolist()
    lista_merc_opciones = st.session_state["df_mercaderistas"]["Mercaderista"].dropna().tolist()
    
    lista_tiempos_opciones = []
    if not st.session_state["df_tiempos"].empty and "Tiempo de Despacho" in st.session_state["df_tiempos"].columns:
        lista_tiempos_opciones = sorted(list(set(st.session_state["df_tiempos"]["Tiempo de Despacho"].dropna().astype(str)) - {""}))
    if not lista_tiempos_opciones:
        lista_tiempos_opciones = ["24 horas", "48 horas"]

    base_cols_maestro = [c for c in columnas_clientes if not c.startswith("Visita_") and not c.startswith("Pedido_") and not c.startswith("Motivo_")]
    df_general_visible = st.session_state["df_clientes"][[c for c in base_cols_maestro if c in st.session_state["df_clientes"].columns]].copy()

    if texto_busqueda:
        mask_busqueda = df_general_visible.astype(str).apply(lambda row: row.str.contains(texto_busqueda, case=False, na=False).any(), axis=1)
        df_general_visible = df_general_visible[mask_busqueda]
        st.caption(f"Mostrando **{len(df_general_visible)}** resultados coincidentes con la búsqueda.")

    with st.form("form_cuadro_maestro"):
      edited_df_visible = st.data_editor(
          df_general_visible, num_rows="dynamic", use_container_width=True, key="editor_clientes_general", hide_index=True,
          column_config={
              "Nro": st.column_config.NumberColumn("Nro", required=True),
              "Vendedor": st.column_config.SelectboxColumn("Vendedor", options=lista_vend_opciones),
              "Semana 1": st.column_config.SelectboxColumn("Semana 1", options=["Sí", "No"]),
              "Semana 2": st.column_config.SelectboxColumn("Semana 2", options=["Sí", "No"]),
              "Tiempo de Despacho": st.column_config.SelectboxColumn("Tiempo Despacho", options=lista_tiempos_opciones),
              "Mercaderia": st.column_config.SelectboxColumn("Mercaderia", options=["Sí", "No"]),
              "Mercaderista": st.column_config.SelectboxColumn("Mercaderista", options=lista_merc_opciones),
          }
      )

      submitted = st.form_submit_button("💾 Guardar y Sincronizar en la Base de Datos", type="primary", use_container_width=True)

      if submitted:
        df_actualizado = st.session_state["df_clientes"].copy()
        
        for col_c in columnas_clientes:
            if col_c not in df_actualizado.columns:
                df_actualizado[col_c] = False if ("Visita_" in col_c or "Pedido_" in col_c) else ""

        if texto_busqueda:
            for idx, row in edited_df_visible.iterrows():
                nro_cliente = row.get("Nro")
                match_orig = df_actualizado[df_actualizado["Nro"] == nro_cliente]
                if not match_orig.empty:
                    orig_idx = match_orig.index[0]
                    for col in edited_df_visible.columns:
                        # Aplicar normalización de días si se edita alguna columna de días
                        if "Día" in col:
                            df_actualizado.at[orig_idx, col] = normalizar_dia(row[col])
                        else:
                            df_actualizado.at[orig_idx, col] = row[col]
        else:
            for col in edited_df_visible.columns:
              if "Día" in col:
                  df_actualizado[col] = edited_df_visible[col].apply(normalizar_dia)
              else:
                  df_actualizado[col] = edited_df_visible[col]

        if not df_actualizado.empty:
          if len(df_actualizado) > 1 and not texto_busqueda:
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
                  df_actualizado.at[idx, "Mercaderista"] = df_m.iloc[pos_vendedor]["Mercaderista"]
                  df_actualizado.at[idx, "Nro de Ruta (Mercaderia)"] = df_m.iloc[pos_vendedor]["Nro de Ruta"]

        st.session_state["df_clientes"] = df_actualizado[columnas_clientes]
        guardar_en_base_de_datos(st.session_state["df_clientes"])
        st.rerun()

    st.markdown("---")
    st.subheader("📥 Descargar Reporte en Excel")
    
    df_exportar = st.session_state["df_clientes"][[c for c in columnas_clientes if c in st.session_state["df_clientes"].columns]].copy()
    
    output_excel = io.BytesIO()
    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
      df_exportar.to_excel(writer, index=False, sheet_name="Cuadro Maestro")
      
    st.download_button(
        label="📥 Descargar Cuadro Maestro (.xlsx)",
        data=output_excel.getvalue(),
        file_name="Cuadro_Maestro_Rutas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

with tab_ruta_vendedores:
    st.header("🚚 Seguimiento de Ruta de Vendedores")
    df_seguimiento = st.session_state["df_clientes"].copy()
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        semana_seleccionada = st.selectbox("Seleccionar Semana", ["Semana 1", "Semana 2"])
    with col_f2:
        # Selector limitado estrictamente de Lunes a Viernes
        dia_seleccionado = st.selectbox("Seleccionar Día de Visita", ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"])

    vendedores_disponibles = sorted(list(set(df_seguimiento["Vendedor"].dropna().astype(str)) - {""}))
    
    if vendedores_disponibles:
        st.markdown("---")
        cols_vendedores = st.columns(len(vendedores_disponibles))
        
        for idx, vendedor in enumerate(vendedores_disponibles):
            with cols_vendedores[idx]:
                st.subheader(f"👤 {vendedor}")
                
                mask_v = df_seguimiento["Vendedor"].astype(str).str.strip() == vendedor.strip()
                df_v_filtrado = df_seguimiento[mask_v].copy()
                
                s_num = "1" if semana_seleccionada == "Semana 1" else "2"
                col_visita_campo = f"Día de Visita Semana {s_num}"
                col_visita_estatus = f"Visita_S{s_num}"
                col_pedido_estatus = f"Pedido_S{s_num}"
                col_motivo_estatus = f"Motivo_Pedido_S{s_num}"
                
                # Normalizar registros de días para asegurar coincidencia con o sin tildes
                if col_visita_campo in df_v_filtrado.columns:
                    df_v_filtrado[col_visita_campo] = df_v_filtrado[col_visita_campo].apply(normalizar_dia)
                
                if col_visita_campo in df_v_filtrado.columns and dia_seleccionado:
                    df_v_filtrado = df_v_filtrado[
                        df_v_filtrado[col_visita_campo].astype(str).str.contains(dia_seleccionado, case=False, na=False)
                    ]
                
                cols_view = ["Nro", "Cliente", "Ubicacion", col_visita_estatus, col_pedido_estatus, col_motivo_estatus]
                for c in cols_view:
                    if c not in df_v_filtrado.columns:
                        df_v_filtrado[c] = False if ("Visita_" in c or "Pedido_" in c) else ""
                
                for c in [col_visita_estatus, col_pedido_estatus]:
                    df_v_filtrado[c] = df_v_filtrado[c].fillna(False).astype(bool)
                for c in [col_motivo_estatus]:
                    df_v_filtrado[c] = df_v_filtrado[c].fillna("").astype(str)

                # Editor interactivo configurado con checkboxes para estatus y texto libre para el motivo
                df_editado_col = st.data_editor(
                    df_v_filtrado[cols_view], 
                    use_container_width=True, 
                    hide_index=True, 
                    key=f"ed_vendedor_{idx}_{semana_seleccionada}_{dia_seleccionado}",
                    column_config={
                        col_visita_estatus: st.column_config.CheckboxColumn("¿Visitado?", default=False),
                        col_pedido_estatus: st.column_config.CheckboxColumn("¿Pedido?", default=False),
                        col_motivo_estatus: st.column_config.TextColumn("Motivo / Observación", default=""),
                    }
                )
                
                if st.button(f"💾 Guardar {vendedor}", key=f"btn_guardar_{idx}_{semana_seleccionada}_{dia_seleccionado}", use_container_width=True):
                    for r_idx, row_edit in df_editado_col.iterrows():
                        nro_val = row_edit.get("Nro")
                        match_global = st.session_state["df_clientes"][st.session_state["df_clientes"]["Nro"] == nro_val]
                        if not match_global.empty:
                            g_idx = match_global.index[0]
                            for col_chk in [col_visita_estatus, col_pedido_estatus, col_motivo_estatus]:
                                if col_chk not in st.session_state["df_clientes"].columns:
                                    st.session_state["df_clientes"][col_chk] = False if ("Visita_" in col_chk or "Pedido_" in col_chk) else ""
                            
                            st.session_state["df_clientes"].at[g_idx, col_visita_estatus] = row_edit[col_visita_estatus]
                            st.session_state["df_clientes"].at[g_idx, col_pedido_estatus] = row_edit[col_pedido_estatus]
                            st.session_state["df_clientes"].at[g_idx, col_motivo_estatus] = row_edit[col_motivo_estatus]
                    
                    guardar_en_base_de_datos(st.session_state["df_clientes"])
                    st.success(f"¡Ruta de {vendedor} guardada con éxito!")
                    st.rerun()
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
            tiempo_desp = r.get("Tiempo de Despacho", "24 horas")
            for s_col in ["Día de Visita Semana 1", "Día de Visita Semana 2"]:
                dia_v = r.get(s_col, "")
                if dia_v and str(dia_v).strip() not in ["", "nan", "None", "No asignado"]:
                    desp = calcular_despacho_por_dia_y_semana(dia_v, "Semana 1" if "Semana 1" in s_col else "Semana 2", tiempo_desp>
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
