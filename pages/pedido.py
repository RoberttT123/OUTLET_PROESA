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
    st.error("❌ Archivo `config.py` no encontrado. Copia `config.example.py` a `config.py` y llena las URLs.")
    st.stop()

from src.sheets import (
    obtener_inventario_sheets,
    obtener_pedidos_empleado_sheets,
    guardar_pedido_sheets
)

st.set_page_config(
    page_title="Mi Pedido - Outlet PROESA",
    layout="wide",
    page_icon="🛒",
    initial_sidebar_state="collapsed"
)

# ── ESTILOS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@500&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background: #F5F4F0; }

.hero-login {
    background: linear-gradient(135deg, #1A1A2E 0%, #0F3460 100%);
    border-radius: 20px;
    padding: 2.5rem;
    margin-bottom: 2rem;
    text-align: center;
    color: white;
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

#MainMenu, header, footer { visibility: hidden; }
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
    st.session_state.cod_emp = None
    st.session_state.nom_emp = None
    st.session_state.carrito = []

# ── CARGAR INVENTARIO ───────────────────────────────────────────────────────
@st.cache_data(ttl=300)  # Cache por 5 minutos
def cargar_inventario():
    return obtener_inventario_sheets(INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME)

df_inv = cargar_inventario()

if df_inv.empty:
    st.error("❌ No se pudo cargar el catálogo. Verifica la configuración de Google Sheets.")
    st.stop()

# ═════════════════════════════════════════════════════════════════════════════
# PANTALLA 1: LOGIN
# ═════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    logo_b64 = get_logo_b64()
    
    st.markdown(f"""
    <div class="hero-login">
        {'<img src="data:image/png;base64,' + logo_b64 + '" style="height:80px;object-fit:contain;margin-bottom:1rem;">' if logo_b64 else ''}
        <h1>Outlet PROESA</h1>
        <p>Sistema de Pedidos para Empleados</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        cod_inp = st.text_input("Código de Empleado", placeholder="Ej: E0200491")
        nom_inp = st.text_input("Nombre Completo", placeholder="Tu nombre y apellido")
        
        if st.form_submit_button("🚀 Continuar", use_container_width=True):
            if cod_inp and nom_inp:
                st.session_state.logged_in = True
                st.session_state.cod_emp = cod_inp.upper()
                st.session_state.nom_emp = nom_inp.title()
                st.rerun()
            else:
                st.error("⚠️ Completa ambos campos.")

# ═════════════════════════════════════════════════════════════════════════════
# PANTALLA 2: PEDIDOS
# ═════════════════════════════════════════════════════════════════════════════
else:
    logo_b64 = get_logo_b64()
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="height:52px;object-fit:contain;">' if logo_b64 else "🛒"
    
    st.markdown(f"""
    <div class="page-header">
        {logo_html}
        <div>
            <h2>Tu Pedido</h2>
            <p>👤 {st.session_state.nom_emp} · 🔖 {st.session_state.cod_emp}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_pedido, col_carrito = st.columns([2, 1], gap="medium")

    # ── COLUMNA 1: CATÁLOGO ──────────────────────────────────────────────────
    with col_pedido:
        st.markdown('<div class="section-title">📦 Catálogo de Productos</div>', unsafe_allow_html=True)

        busqueda = st.text_input("Busca un producto...", placeholder="Escribe el nombre o código")

        # Obtener nombres de productos
        if "Nombre Producto" in df_inv.columns:
            lista_prods = df_inv["Nombre Producto"].dropna().tolist()
        else:
            st.error("❌ Columna 'Nombre Producto' no encontrada en Google Sheets")
            st.stop()

        # Filtrar
        prods_filtrados = lista_prods
        if busqueda:
            prods_filtrados = [p for p in lista_prods if busqueda.lower() in p.lower()]

        if not prods_filtrados:
            st.info("No se encontraron productos.")
        else:
            for prod_nombre in prods_filtrados[:50]:  # Limit a 50 productos
                fila = df_inv[df_inv["Nombre Producto"] == prod_nombre].iloc[0]
                
                try:
                    stock = int(float(fila.get("Stock", 0)))
                    precio = float(fila.get("Precio Unitario", 0))
                    codigo = str(fila.get("Código Producto", "N/A"))
                except:
                    continue

                # Stock badge
                if stock <= 0:
                    stock_badge = '<span class="stock-out">❌ Agotado</span>'
                    disabled = True
                elif stock <= 5:
                    stock_badge = f'<span class="stock-warn">⚠️ Stock bajo: {stock}</span>'
                    disabled = False
                else:
                    stock_badge = f'<span class="stock-ok">✅ {stock} disponibles</span>'
                    disabled = False

                with st.container():
                    c1, c2, c3 = st.columns([2, 1.2, 0.8])
                    
                    with c1:
                        st.markdown(f"**{prod_nombre}**\n`{codigo}`")
                    with c2:
                        st.markdown(f"**Bs {precio:,.2f}**\n{stock_badge}", unsafe_allow_html=True)
                    with c3:
                        if not disabled:
                            cant = st.number_input("Qty", min_value=1, max_value=max(stock, 1), 
                                                 value=1, key=f"qty_{codigo}")
                            if st.button("➕", key=f"btn_{codigo}"):
                                st.session_state.carrito.append({
                                    "codigo_producto": codigo,
                                    "producto": prod_nombre,
                                    "cantidad": int(cant),
                                    "precio_unitario": precio,
                                    "subtotal": precio * int(cant)
                                })
                                st.toast(f"✅ Agregado")
                                st.rerun()

    # ── COLUMNA 2: CARRITO ───────────────────────────────────────────────────
    with col_carrito:
        st.markdown('<div class="section-title">🛒 Tu Carrito</div>', unsafe_allow_html=True)

        if st.session_state.carrito:
            for i, item in enumerate(st.session_state.carrito):
                col_info, col_del = st.columns([4, 1])
                
                with col_info:
                    st.markdown(f"""
                    **{item['producto']}**
                    
                    {item['cantidad']} × Bs {item['precio_unitario']:,.2f}
                    
                    **Bs {item['subtotal']:,.2f}**
                    """)
                
                with col_del:
                    if st.button("❌", key=f"del_{i}"):
                        st.session_state.carrito.pop(i)
                        st.rerun()

            total = sum(item['subtotal'] for item in st.session_state.carrito)
            st.markdown(f"""
            <div class="carrito-total">
                <div style="font-size:0.75rem;color:#A8B2C8;margin-bottom:0.3rem">TOTAL</div>
                <div style="font-size:2rem;font-weight:700;font-family:'DM Mono',monospace">Bs {total:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("✅ ENVIAR PEDIDO", type="primary", use_container_width=True):
                # Preparar items con todos los datos
                items_para_sheets = []
                for item in st.session_state.carrito:
                    fila = df_inv[df_inv["Nombre Producto"] == item['producto']].iloc[0]
                    items_para_sheets.append({
                        "codigo_producto": str(fila.get("Código Producto", fila.iloc[1])),
                        "producto": item['producto'],
                        "cantidad": item['cantidad'],
                        "precio_unitario": float(fila.get("Precio Unitario", fila.iloc[4])),
                        "linea": str(fila.get("Línea", fila.iloc[0])),
                        "descuento": 0,
                        "stock_actual": int(fila.get("Stock", fila.iloc[3])),
                        "empresa": str(fila.get("Empresa", fila.iloc[5]))
                    })
                
                if guardar_pedido_sheets(
                    st.session_state.cod_emp,
                    st.session_state.nom_emp,
                    items_para_sheets,
                    PEDIDOS_SHEET_URL,
                    PEDIDOS_HOJA_NAME
                ):
                    st.session_state.carrito = []
                    st.success("🎉 ¡Pedido enviado! Trade Marketing lo procesará pronto.")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("❌ Error al enviar pedido. Intenta nuevamente.")
        else:
            st.info("Tu carrito está vacío.\nAgrega productos a la izquierda.")

    # ── HISTORIAL ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-title">📋 Tus Pedidos Anteriores</div>', unsafe_allow_html=True)

    mis_pedidos = obtener_pedidos_empleado_sheets(
        st.session_state.cod_emp,
        PEDIDOS_SHEET_URL,
        PEDIDOS_HOJA_NAME
    )

    if not mis_pedidos.empty:
        for _, pedido in mis_pedidos.iterrows():
            estado_badge = "⏳ Pendiente" if pedido.get("Estado") == "Pendiente" else "✅ Confirmado"
            st.markdown(f"""
            📦 **{pedido.get('Nombre Producto', 'N/A')}** · {pedido.get('Cantidad', 0)} ud.
            
            📅 {pedido.get('Fecha', '')} — {estado_badge}
            """)
    else:
        st.info("No has hecho pedidos aún.")

    st.markdown("---")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.logged_in = False
        st.session_state.carrito = []
        st.rerun()