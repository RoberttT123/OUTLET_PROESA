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

st.set_page_config(
    page_title="Mi Pedido - Outlet PROESA",
    layout="wide",
    page_icon="🛒",
    initial_sidebar_state="collapsed"
)

# ── ESTILOS REFORZADOS PARA OCULTAR STREAMLIT ───────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@500&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background: #F5F4F0; }

/* Ajuste de contenedor principal */
.block-container {
    padding-top: 0.2rem !important;
    padding-bottom: 0rem !important;
}

/* OCULTAR ELEMENTOS DE STREAMLIT TOTALMENTE */
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden !important;}
footer:after { content:''; display:none !important; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
.stDeployButton { display: none !important; }

/* Selector agresivo para el footer en Streamlit Cloud */
div[data-testid="stAppViewContainer"] > footer { display: none !important; }
div[class^="st-emotion-cache"] footer { display: none !important; }

/* Estilos de la App */
.hero-login {
    background: linear-gradient(135deg, #1A1A2E 0%, #0F3460 100%);
    border-radius: 20px;
    padding: 2.5rem 2.5rem;
    margin-bottom: 2rem;
    text-align: center;
    color: white;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 140px;
}
.hero-login h1 {
    font-size: 2.2rem;
    font-weight: 700;
    margin: 0 0 0.5rem;
}

.login-form {
    background: white;
    border-radius: 16px;
    padding: 2rem;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    max-width: 400px;
    margin: 0 auto;
}

.page-header {
    background: white;
    border-radius: 16px;
    padding: 1.5rem 2rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    display: flex;
    align-items: center;
    gap: 1rem;
    border-top: 4px solid #E63946;
}
.page-header h2 { color: #1A1A2E; font-size: 1.5rem; margin: 0; }
.page-header p { color: #888; margin: 0.2rem 0 0; }

.section-title {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #AAA;
    margin: 1.5rem 0 0.5rem;
    padding-bottom: 0.4rem;
    border-bottom: 2px solid #EBEBEB;
}

.carrito-total {
    background: #1A1A2E;
    color: white;
    border-radius: 12px;
    padding: 1.5rem;
    margin: 1.5rem 0;
    text-align: center;
}

.stock-ok { background: #D1FAE5; color: #065F46; border-radius: 20px; padding: 3px 12px; font-size: 0.75rem; font-weight: 600; }
.stock-warn { background: #FEF9C3; color: #854D0E; border-radius: 20px; padding: 3px 12px; font-size: 0.75rem; }
.stock-out { background: #FEE2E2; color: #991B1B; border-radius: 20px; padding: 3px 12px; font-size: 0.75rem; }

.emp-info {
    background: #F0F7FF;
    border: 1px solid #BFDBFE;
    border-radius: 10px;
    padding: 1rem;
    margin: 1rem 0;
    font-size: 0.9rem;
}
</style>
""", unsafe_allow_html=True)

# ── LOGO ────────────────────────────────────────────────────────────────────
def get_logo_b64(path="assets/logo_proesa.png"):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return None

# ── SESSION STATE ───────────────────────────────────────────────────────────
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'cod_emp' not in st.session_state:
    st.session_state.cod_emp = None
if 'nom_emp' not in st.session_state:
    st.session_state.nom_emp = None
if 'empresa' not in st.session_state:
    st.session_state.empresa = None
if 'regional' not in st.session_state:
    st.session_state.regional = None
if 'carrito' not in st.session_state:
    st.session_state.carrito = []

# ── CARGAR INVENTARIO ───────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def cargar_inventario():
    return obtener_inventario_sheets(INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME)

df_inv = cargar_inventario()

if df_inv.empty:
    st.error("❌ No se pudo cargar el catálogo.")
    st.stop()

# ═════════════════════════════════════════════════════════════════════════════
# PANTALLA 1: LOGIN
# ═════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    logo_b64 = get_logo_b64()
    
    st.markdown(f"""
    <div class="hero-login">
        {f'<img src="data:image/png;base64,{logo_b64}" style="height:210px; width:auto; object-fit:contain; margin-top:-20px; margin-bottom:0px;">' if logo_b64 else ''}
        <h1 style="margin-top:0;">Outlet PROESA</h1>
        <p style="margin-bottom:0;">Sistema de Pedidos para Empleados</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        cod_inp = st.text_input("Código de Empleado", placeholder="Ej: E0200491").upper().strip()
        
        if st.form_submit_button("🚀 Validar Código", use_container_width=True):
            if cod_inp:
                datos = obtener_datos_empleado(cod_inp)
                if datos.get('encontrado'):
                    st.session_state.logged_in = True
                    st.session_state.cod_emp = cod_inp
                    st.session_state.nom_emp = datos['nombre']
                    st.session_state.empresa = datos['empresa']
                    st.session_state.regional = datos['regional']
                    st.rerun()
                else:
                    st.error(f"❌ Código '{cod_inp}' no encontrado.")
            else:
                st.error("⚠️ Ingresa tu código de empleado.")

# ═════════════════════════════════════════════════════════════════════════════
# PANTALLA 2: PEDIDOS
# ═════════════════════════════════════════════════════════════════════════════
else:
    logo_b64 = get_logo_b64()
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="height:100px;object-fit:contain;">' if logo_b64 else "🛒"
    
    st.markdown(f"""
    <div class="page-header">
        {logo_html}
        <div>
            <h2>Tu Pedido</h2>
            <p>👤 {st.session_state.nom_emp} · 🔖 {st.session_state.cod_emp} · 🏢 {st.session_state.empresa or 'N/A'}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_pedido, col_carrito = st.columns([2, 1], gap="medium")

    # ── COLUMNA 1: CATÁLOGO ──────────────────────────────────────────────────
    with col_pedido:
        st.markdown('<div class="section-title">📦 Catálogo de Productos</div>', unsafe_allow_html=True)
        busqueda = st.text_input("Busca un producto...", placeholder="Escribe el nombre o código")

        if "Nombre Producto" in df_inv.columns:
            lista_prods = df_inv["Nombre Producto"].dropna().tolist()
        else:
            st.error("❌ Columna 'Nombre Producto' no encontrada")
            st.stop()

        if busqueda:
            prods_filtrados = []
            for prod_nombre in lista_prods:
                fila_prod = df_inv[df_inv["Nombre Producto"] == prod_nombre].iloc[0]
                codigo = str(fila_prod["Código Producto"] if "Código Producto" in fila_prod.index else fila_prod.iloc[1])
                if busqueda.lower() in prod_nombre.lower() or busqueda.lower() in codigo.lower():
                    prods_filtrados.append(prod_nombre)
        else:
            prods_filtrados = lista_prods

        if not prods_filtrados:
            st.info("No se encontraron productos.")
        else:
            for prod_nombre in prods_filtrados[:5]:  
                fila = df_inv[df_inv["Nombre Producto"] == prod_nombre].iloc[0]
                try:
                    stock = int(float(fila["Stock"] if "Stock" in fila.index else fila.iloc[3]))
                    precio = float(fila["Precio Unitario"] if "Precio Unitario" in fila.index else fila.iloc[4])
                    codigo = str(fila["Código Producto"] if "Código Producto" in fila.index else fila.iloc[1])
                except: continue

                stock_badge = f'<span class="stock-ok">✅ {stock}</span>' if stock > 0 else '<span class="stock-out">❌ Agotado</span>'
                
                with st.container():
                    c1, c2, c3 = st.columns([2, 1.2, 0.8])
                    with c1: st.markdown(f"**{prod_nombre}**\n`{codigo}`")
                    with c2: st.markdown(f"**Bs {precio:,.2f}**\n{stock_badge}", unsafe_allow_html=True)
                    with c3:
                        if stock > 0:
                            cant = st.number_input("Cant", min_value=1, max_value=stock, value=1, key=f"qty_{codigo}")
                            if st.button("➕", key=f"btn_{codigo}"):
                                st.session_state.carrito.append({
                                    "codigo_producto": codigo, "producto": prod_nombre,
                                    "cantidad": int(cant), "precio_unitario": precio, "subtotal": precio * int(cant)
                                })
                                st.rerun()

    # ── COLUMNA 2: CARRITO ───────────────────────────────────────────────────
    with col_carrito:
        st.markdown('<div class="section-title">🛒 Tu Carrito</div>', unsafe_allow_html=True)
        if st.session_state.carrito:
            for i, item in enumerate(st.session_state.carrito):
                ci, cd = st.columns([4, 1])
                with ci: st.markdown(f"**{item['producto']}**\n{item['cantidad']} x Bs {item['precio_unitario']:,.2f} = **Bs {item['subtotal']:,.2f}**")
                with cd:
                    if st.button("❌", key=f"del_{i}"):
                        st.session_state.carrito.pop(i)
                        st.rerun()

            total = sum(item['subtotal'] for item in st.session_state.carrito)
            st.markdown(f'<div class="carrito-total">TOTAL<br><span style="font-size:2rem">Bs {total:,.2f}</span></div>', unsafe_allow_html=True)

            if st.button("✅ ENVIAR PEDIDO", type="primary", use_container_width=True):
                items_para_sheets = []
                for item in st.session_state.carrito:
                    fila = df_inv[df_inv["Nombre Producto"] == item['producto']].iloc[0]
                    items_para_sheets.append({
                        "codigo_producto": item['codigo_producto'], "producto": item['producto'],
                        "cantidad": item['cantidad'], "precio_unitario": item['precio_unitario'],
                        "linea": str(fila["Línea"] if "Línea" in fila.index else fila.iloc[0]),
                        "descuento": 0, "stock_actual": int(fila["Stock"] if "Stock" in fila.index else fila.iloc[3]),
                        "empresa": st.session_state.empresa or "PROESA"
                    })
                
                if guardar_pedido_sheets(st.session_state.cod_emp, st.session_state.nom_emp, items_para_sheets, PEDIDOS_SHEET_URL, PEDIDOS_HOJA_NAME):
                    for item in items_para_sheets:
                        actualizar_stock_sheets(item['codigo_producto'], item['cantidad'], INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME)
                    st.session_state.carrito = []
                    st.cache_data.clear()
                    st.success("🎉 ¡Pedido enviado!")
                    st.balloons()
                    st.rerun()
        else:
            st.info("Carrito vacío.")

    # ── HISTORIAL ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-title">📋 Tus Pedidos Anteriores</div>', unsafe_allow_html=True)
    mis_pedidos = obtener_pedidos_empleado_sheets(st.session_state.cod_emp, PEDIDOS_SHEET_URL, PEDIDOS_HOJA_NAME)
    if not mis_pedidos.empty:
        for _, p in mis_pedidos.tail(5).iterrows():
            st.markdown(f"📦 **{p.get('Nombre Producto', 'N/A')}** · {p.get('Cantidad', 0)} ud. · 📅 {p.get('Fecha Registro', '')}")
    else: st.info("Sin historial.")

    st.markdown("---")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.logged_in = False
        st.session_state.carrito = []
        st.rerun()