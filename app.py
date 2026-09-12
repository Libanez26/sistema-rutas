import streamlit as st
from services.supabase_service import supabase, cargar_datos_maestros, guardar_todo_en_supabase
from views import cuadro_maestro, vendedores, despachos

# Configuración inicial de la página
st.set_page_config(
    page_title="Sistema Integral de Gestión de Rutas",
    page_icon="🚚",
    layout="wide"
)

# Inicializar variables de estado de sesión
if "usuario" not in st.session_state:
    st.session_state["usuario"] = None

# --- CONTROL DE AUTENTICACIÓN ---
if st.session_state["usuario"] is None:
    st.title("🔑 Sistema Integral de Gestión de Rutas")
    tab_login, tab_registro = st.tabs(["🔑 Iniciar Sesión", "📝 Registrarse"])
    
    with tab_login:
        st.subheader("Acceso al Sistema")
        correo = st.text_input("Correo electrónico", key="c_login")
        password = st.text_input("Contraseña", type="password", key="p_login")
        
        if st.button("Ingresar", type="primary"):
            if supabase:
                try:
                    res = supabase.auth.sign_in_with_password({"email": correo, "password": password})
                    st.session_state["usuario"] = res.user
                    st.success("¡Ingreso exitoso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al iniciar sesión: {e}")
            else:
                st.error("Supabase no está configurado correctamente en los st.secrets.")
                
    with tab_registro:
        st.subheader("Crear Cuenta Nueva")
        correo_r = st.text_input("Correo electrónico", key="c_reg")
        password_r = st.text_input("Contraseña", type="password", key="p_reg")
        
        if st.button("Registrarse"):
            if supabase:
                try:
                    supabase.auth.sign_up({"email": correo_r, "password": password_r})
                    st.success("¡Registro exitoso! Ya puedes iniciar sesión en la pestaña de al lado.")
                except Exception as e:
                    st.error(f"Error en el registro: {e}")
            else:
                st.error("Supabase no está configurado.")
    st.stop()

# --- BARRA LATERAL (USUARIO AUTENTICADO) ---
st.sidebar.title("Panel de Control")
if st.session_state["usuario"]:
    usuario_email = getattr(st.session_state["usuario"], "email", "Usuario")
    st.sidebar.write(f"👤 **Sesión:** {usuario_email}")
    
    if st.sidebar.button("🔄 Sincronizar con Supabase"):
        df_cli, df_v, df_m = cargar_datos_maestros()
        st.session_state["df_clientes"] = df_cli
        st.session_state["df_vendedores"] = df_v
        st.session_state["df_mercaderistas"] = df_m
        st.toast("¡Datos sincronizados desde Supabase!", icon="🔄")
        st.rerun()

    if st.sidebar.button("Cerrar Sesión", type="secondary"):
        st.session_state["usuario"] = None
        st.rerun()

# --- CARGAR DATOS INICIALES EN SESSION STATE ---
if "df_clientes" not in st.session_state or "df_vendedores" not in st.session_state:
    df_cli, df_v, df_m = cargar_datos_maestros()
    st.session_state["df_clientes"] = df_cli
    st.session_state["df_vendedores"] = df_v
    st.session_state["df_mercaderistas"] = df_m

# --- NAVEGACIÓN PRINCIPAL POR PESTAÑAS ---
tab_gen, tab_vend, tab_desp = st.tabs([
    "📊 Cuadro Maestro", 
    "🚚 Ruta de Vendedores", 
    "📦 Ruta de Despacho"
])

with tab_gen:
    cuadro_maestro.render()

with tab_vend:
    vendedores.render()

with tab_desp:
    despachos.render()
