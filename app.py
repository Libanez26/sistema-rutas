import streamlit as st
import pandas as pd
from supabase import create_client, Client

# Configuración inicial de la página
st.set_page_config(
    page_title="Sistema Integral de Gestión de Rutas",
    page_icon="🚚",
    layout="wide"
)

# --- 1. CONFIGURACIÓN DE SUPABASE Y LOGÍSTICA ---
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

COLUMNITAS_CLIENTES = [
    "Nro", "Vendedor", "Nro de Ruta (Ventas)", "Cliente", "Ubicacion",
    "Semana 1", "Semana 2", "Día de Visita Semana 1", "Día de Visita Semana 2",
    "Tiempo de Despacho", "Mercaderia", "Mercaderista", "Nro de Ruta (Mercaderia)",
    "Tiempo de Mercaderia", "Día de Mercaderia Semana 1", "Día de Mercaderia Semana 2",
    "Visita_S4", "Pedido_S4", "Motivo_Pedido_S4",
    "Visita_S3", "Pedido_S3", "Motivo_Pedido_S3",
    "Visita_S2", "Pedido_S2", "Motivo_Pedido_S2",
    "Visita_S1", "Pedido_S1", "Motivo_Pedido_S1",
]

def cargar_datos_maestros():
    if not supabase:
        return pd.DataFrame(columns=COLUMNITAS_CLIENTES), pd.DataFrame(), pd.DataFrame()
    try:
        res_cli = supabase.table("clientes_rutas").select("*").execute()
        df_cli = pd.DataFrame(res_cli.data) if res_cli.data else pd.DataFrame(columns=COLUMNITAS_CLIENTES)
        if "id" in df_cli.columns:
            df_cli = df_cli.drop(columns=["id"])
        for col in COLUMNITAS_CLIENTES:
            if col not in df_cli.columns:
                df_cli[col] = ""
        df_cli = df_cli[COLUMNITAS_CLIENTES]

        res_v = supabase.table("personal_rutas").select("*").eq("tipo", "vendedor").execute()
        df_v = pd.DataFrame(res_v.data)[["Vendedor", "Nro de Ruta"]] if res_v.data else pd.DataFrame([
            {"Vendedor": "Jhony Moreno", "Nro de Ruta": "Ruta 01"},
        ])

        res_m = supabase.table("personal_rutas").select("*").eq("tipo", "mercaderista").execute()
        df_m = pd.DataFrame(res_m.data).rename(columns={"Vendedor": "Mercaderista"})[["Mercaderista", "Nro de Ruta"]] if res_m.data else pd.DataFrame([
            {"Mercaderista": "Yorsin Villanueva", "Nro de Ruta": "Ruta M-01"},
        ])

        return df_cli, df_v, df_m
    except Exception as e:
        return pd.DataFrame(columns=COLUMNITAS_CLIENTES), pd.DataFrame(), pd.DataFrame()

def guardar_todo_en_supabase(df_clientes, df_vendedores, df_mercaderistas):
    if not supabase:
        st.error("Supabase no configurado.")
        return False
    try:
        df_to_save = df_clientes.copy().fillna("")
        df_to_save = df_to_save[df_to_save["Cliente"].astype(str).str.strip() != ""]
        supabase.table("clientes_rutas").delete().neq("Nro", -999999).execute()
        if not df_to_save.empty:
            supabase.table("clientes_rutas").insert(df_to_save.to_dict(orient="records")).execute()

        supabase.table("personal_rutas").delete().neq("id", -999999).execute()
        registros = []
        for _, row in df_vendedores.dropna(subset=["Vendedor"]).iterrows():
            if str(row["Vendedor"]).strip():
                registros.append({"tipo": "vendedor", "Vendedor": str(row["Vendedor"]), "Nro de Ruta": str(row["Nro de Ruta"])})
        for _, row in df_mercaderistas.dropna(subset=["Mercaderista"]).iterrows():
            if str(row["Mercaderista"]).strip():
                registros.append({"tipo": "mercaderista", "Vendedor": str(row["Mercaderista"]), "Nro de Ruta": str(row["Nro de Ruta"])})
        
        if registros:
            supabase.table("personal_rutas").insert(registros).execute()
        
        st.toast("¡Cambios guardados con éxito en Supabase!", icon="✅")
        return True
    except Exception as e:
        st.error(f"Error al guardar: {e}")
        return False

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
        d_limpio = d_visita.lower()
        if d_limpio == "miercoles":
            d_limpio = "miércoles"
        elif d_limpio == "sabado":
            d_limpio = "sábado"

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
            dia_nombre = dias_habiles[idx_nuevo].capitalize()
            resultados_despacho.append(f"{dia_nombre} ({sig_semana})")
        else:
            dia_nombre = dias_habiles[idx_nuevo].capitalize()
            resultados_despacho.append(f"{dia_nombre} ({semana_actual})")

    return ", ".join(resultados_despacho) if resultados_despacho else "No asignado"

# --- 2. CONTROL DE AUTENTICACIÓN ---
if "usuario" not in st.session_state:
    st.session_state["usuario"] = None

if st.session_state["usuario"] is None:
    st.title("🔑 Sistema Integral de Gestión de Rutas")
    tab_login, tab_registro = st.tabs(["🔑 Iniciar Sesión", "📝 Registrarse"])
    
    with tab_login:
        correo = st.text_input("Correo electrónico", key="c_login")
        password = st.text_input("Contraseña", type="password", key="p_login")
        if st.button("Ingresar", type="primary"):
            if supabase:
                try:
                    res = supabase.auth.sign_in_with_password({"email": correo, "password": password})
                    st.session_state["usuario"] = res.user
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.error("Supabase no configurado.")
    with tab_registro:
        correo_r = st.text_input("Correo electrónico", key="c_reg")
        password_r = st.text_input("Contraseña", type="password", key="p_reg")
        if st.button("Registrarse"):
            if supabase:
                try:
                    supabase.auth.sign_up({"email": correo_r, "password": password_r})
                    st.success("¡Registro exitoso! Ya puedes iniciar sesión.")
                except Exception as e:
                    st.error(f"Error: {e}")
    st.stop()

st.sidebar.write(f"👤 **{getattr(st.session_state['usuario'], 'email', 'Usuario')}**")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state["usuario"] = None
    st.rerun()

# Cargar estado
if "df_clientes" not in st.session_state or "df_vendedores" not in st.session_state:
    df_cli, df_v, df_m = cargar_datos_maestros()
    st.session_state["df_clientes"] = df_cli
    st.session_state["df_vendedores"] = df_v
    st.session_state["df_mercaderistas"] = df_m

# --- 3. VISTAS PRINCIPALES ---
tab_gen, tab_vend, tab_desp = st.tabs(["📊 Cuadro Maestro", "🚚 Ruta de Vendedores", "📦 Ruta de Despacho"])

# VISTA 1: CUADRO MAESTRO
with tab_gen:
    st.header("📊 Cuadro Maestro - Gestión General")
    df = st.session_state["df_clientes"].copy()
    
    archivo_excel = st.file_uploader("Cargar Base de Datos Excel (.xlsx)", type=["xlsx"])
    if archivo_excel is not None:
        try:
            df_excel = pd.read_excel(archivo_excel)
            for col in COLUMNITAS_CLIENTES:
                if col not in df_excel.columns:
                    df_excel[col] = ""
            st.session_state["df_clientes"] = df_excel[COLUMNITAS_CLIENTES]
            guardar_todo_en_supabase(st.session_state["df_clientes"], st.session_state["df_vendedores"], st.session_state["df_mercaderistas"])
            st.success("¡Excel cargado y guardado!")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    df_editado = st.data_editor(df[COLUMNITAS_CLIENTES], num_rows="dynamic", use_container_width=True, key="ed_maestro")
    if st.button("💾 Guardar Cambios Maestro", type="primary"):
        st.session_state["df_clientes"] = df_editado
        guardar_todo_en_supabase(st.session_state["df_clientes"], st.session_state["df_vendedores"], st.session_state["df_mercaderistas"])
        st.rerun()

# VISTA 2: VENDEDORES
with tab_vend:
    st.header("🚚 Módulo de Vendedores")
    df = st.session_state["df_clientes"].copy()
    df_vendedores = st.session_state["df_vendedores"].copy()

    vendedores_disp = sorted(df["Vendedor"].dropna().unique().tolist()) if "Vendedor" in df.columns else []
    sel_v = st.selectbox("Seleccione Vendedor", ["Todos"] + vendedores_disp)
    df_view = df if sel_v == "Todos" else df[df["Vendedor"] == sel_v]

    cols_v = ["Nro", "Vendedor", "Nro de Ruta (Ventas)", "Cliente", "Ubicacion", "Semana 1", "Semana 2", "Día de Visita Semana 1", "Día de Visita Semana 2", "Pedido_S1", "Pedido_S2"]
    cols_exist = [c for c in cols_v if c in df_view.columns]
    
    df_v_edit = st.data_editor(df_view[cols_exist], use_container_width=True, key="ed_vend")
    if st.button("💾 Guardar Cambios Vendedores", type="primary"):
        for _, row in df_v_edit.iterrows():
            idx = df.index[df["Nro"] == row["Nro"]]
            if not idx.empty:
                for c in cols_exist:
                    df.at[idx[0], c] = row[c]
        st.session_state["df_clientes"] = df
        guardar_todo_en_supabase(st.session_state["df_clientes"], st.session_state["df_vendedores"], st.session_state["df_mercaderistas"])
        st.rerun()

# VISTA 3: DESPACHOS
with tab_desp:
    st.header("📦 Módulo de Logística y Despachos")
    df = st.session_state["df_clientes"].copy()
    if "Tiempo de Despacho" not in df.columns:
        df["Tiempo de Despacho"] = "24h"

    res_s1, res_s2 = [], []
    for _, row in df.iterrows():
        t = row.get("Tiempo de Despacho", "24h")
        res_s1.append(calcular_despacho_por_dia_y_semana(row.get("Día de Visita Semana 1", ""), "Semana 1", t))
        res_s2.append(calcular_despacho_por_dia_y_semana(row.get("Día de Visita Semana 2", ""), "Semana 2", t))
    
    df["Despacho Semana 1"] = res_s1
    df["Despacho Semana 2"] = res_s2

    cols_d = ["Nro", "Cliente", "Ubicacion", "Vendedor", "Tiempo de Despacho", "Día de Visita Semana 1", "Despacho Semana 1", "Día de Visita Semana 2", "Despacho Semana 2"]
    cols_d_exist = [c for c in cols_d if c in df.columns]
    st.dataframe(df[cols_d_exist], use_container_width=True, hide_index=True)
