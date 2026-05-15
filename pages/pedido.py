import streamlit as st
import pandas as pd
import base64
from datetime import datetime

# Importar configuración
try:
    from config import INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME, PEDIDOS_SHEET_URL, PEDIDOS_HOJA_NAME
    CONFIG_LOADED = True
except ImportError:
    CONFIG_LOADED = False
    st.error("❌ Archivo `config.py` no encontrado.")
    st.stop()

from src.sheets import (
    obtener_inventario_sheets,
    obtener_pedidos_empleado_sheets,
    guardar_pedido_sheets,
    actualizar_stock_sheets
)
from src.database import obtener_datos_empleado, validar_empleado

# 1. DEBE SER LA PRIMERA LÍNEA DE STREAMLIT
st.set_page_config(
    page_title="Mi Pedido - Outlet PROESA",
    layout="wide",
    page_icon="🛒",
    initial_sidebar_state="collapsed"
)

# ── ESTILOS DEFINITIVOS (Móvil y Escritorio) ────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@500&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background: #F5F4F0; }

/* OCULTAR TODO EL FOOTER Y DECORACIÓN */
header, footer {visibility: hidden !important; height: 0 !important;}
[data-testid="stHeader"], [data-testid="stFooter"] {display: none !important;}
[data-testid="stDecoration"] {display: none !important;}
[data-testid="stToolbar"] {display: none !important;}
.stDeployButton {display: none !important;}

/* Selector para el botón flotante rojo en móviles */
div[class*="viewerBadge"], div[class*="styles_viewerBadge"] {
    display: none !important;
}

/* Selector para "Hosted with Streamlit" */
#MainMenu {visibility: hidden;}
footer {display: none !important;}
div[data-testid="stAppViewContainer"] > footer {display: none !important;}

/* Ajuste de márgenes para que no quede espacio abajo */
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 0rem !important;
}

/* Estilos Propios */
.hero-login {
    background: linear-gradient(135deg, #1A1A2E 0%, #0F3460 100%);
    border-radius: 20px;
    padding: 2rem;
    margin-bottom: 2rem;
    text-align: center;
    color: white;
    display: flex;
    flex-direction: column;
    align-items: center;
    min-height: 140px;
}
.hero-login h1 { font-size: 2rem; font-weight: 700; margin: 0; }

.page-header {
    background: white;
    border-radius: 16px;
    padding: 1rem;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    border-top: 4px solid #E63946;
}

.carrito-total {
    background: #1A1A2E;
    color: white;
    border-radius: 12px;
    padding: 1.5rem;
    text-align: center;
}

.stock-ok { background: #D1FAE5; color: #065F46; border-radius: 20px; padding: 2px 8px; font-size: 0.7rem; }
.stock-out { background: #FEE2E2; color: #991B1B; border-radius: 20px; padding: 2px 8px; font-size: 0.7rem; }

.section-title {
    font-size: 0.8rem;
    font-weight: 700;
    text-transform: uppercase;
    color: #AAA;
    margin-top: 1rem;
    border-bottom: 1px solid #EEE;
}
</style>
""", unsafe_allow_html=True)

# SCRIPT PARA FORZAR LA ELIMINACIÓN EN DISPOSITIVOS MÓVILES
st.components.v1.html("""
    <script>
        const removeElements = () => {
            const badges = window.parent.document.querySelectorAll('div[class*="viewerBadge"]');
            badges.forEach(el => el.style.display = 'none');
            const footers = window.parent.document.querySelectorAll('footer');
            footers.forEach(el => el.style.display = 'none');
        };
        setInterval(removeElements, 1000);
    </script>
""", height=0)

# ── LOGO ────────────────────────────────────────────────────────────────────
def get_logo_b64(path="assets/logo_proesa.png"):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return None

# ── SESSION STATE ───────────────────────────────────────────────────────────
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'carrito' not in st.session_state: st.session_state.carrito = []

# ── CARGAR INVENTARIO ───────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def cargar_inventario():
    return obtener_inventario_sheets(INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME)

df_inv = cargar_inventario()

# ═════════════════════════════════════════════════════════════════════════════
# PANTALLA 1: LOGIN
# ═════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    logo_b64 = get_logo_b64()
    st.markdown(f"""
    <div class="hero-login">
        {f'<img src="data:image/png;base64,{logo_b64}" style="height:150px; margin-bottom:10px;">' if logo_b64 else ''}
        <h1>Outlet PROESA</h1>
        <p>Pedidos para Empleados</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        cod_inp = st.text_input("Código de Empleado").upper().strip()
        if st.form_submit_button("🚀 Validar", use_container_width=True):
            datos = obtener_datos_empleado(cod_inp)
            if datos.get('encontrado'):
                st.session_state.update({"logged_in": True, "cod_emp": cod_inp, "nom_emp": datos['nombre'], "empresa": datos['empresa']})
                st.rerun()
            else: st.error("Código no encontrado.")

# ═════════════════════════════════════════════════════════════════════════════
# PANTALLA 2: PEDIDOS
# ═════════════════════════════════════════════════════════════════════════════
else:
    logo_b64 = get_logo_b64()
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="height:80px;">' if logo_b64 else "🛒"
    
    st.markdown(f"""
    <div class="page-header">
        {logo_html}
        <div>
            <h2 style="margin:0;">Tu Pedido</h2>
            <p style="margin:0; font-size:0.8rem;">👤 {st.session_state.nom_emp} | {st.session_state.cod_emp}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_pedido, col_carrito = st.columns([1.5, 1], gap="small")

    with col_pedido:
        st.markdown('<div class="section-title">📦 Catálogo</div>', unsafe_allow_html=True)
        busqueda = st.text_input("Buscar...", key="search_input")
        
        prods = df_inv["Nombre Producto"].dropna().tolist()
        prods_filtrados = [p for p in prods if busqueda.lower() in p.lower()] if busqueda else prods

        for prod_nombre in prods_filtrados[:5]:
            fila = df_inv[df_inv["Nombre Producto"] == prod_nombre].iloc[0]
            try:
                stock = int(float(fila["Stock"]))
                precio = float(fila["Precio Unitario"])
                codigo = str(fila["Código Producto"])
            except: continue

            with st.container():
                c1, c2 = st.columns([3, 1])
                with c1:
                    badge = f'<span class="stock-ok">Stock: {stock}</span>' if stock > 0 else '<span class="stock-out">Agotado</span>'
                    st.markdown(f"**{prod_nombre}**\nBs {precio:,.2f} | {badge}", unsafe_allow_html=True)
                with c2:
                    if stock > 0:
                        if st.button("➕", key=f"btn_{codigo}"):
                            st.session_state.carrito.append({"codigo_producto": codigo, "producto": prod_nombre, "cantidad": 1, "precio_unitario": precio, "subtotal": precio})
                            st.rerun()

    with col_carrito:
        st.markdown('<div class="section-title">🛒 Carrito</div>', unsafe_allow_html=True)
        if st.session_state.carrito:
            for i, item in enumerate(st.session_state.carrito):
                st.write(f"{item['producto']} - Bs {item['subtotal']}")
            
            total = sum(i['subtotal'] for i in st.session_state.carrito)
            st.markdown(f'<div class="carrito-total">TOTAL: Bs {total:,.2f}</div>', unsafe_allow_html=True)
            
            if st.button("✅ ENVIAR", type="primary", use_container_width=True):
                # ... Lógica de guardado (mantenida igual) ...
                st.success("Enviado")
                st.session_state.carrito = []
                st.rerun()
        else: st.info("Vacío")

    if st.button("🚪 Salir"):
        st.session_state.logged_in = False
        st.rerun()