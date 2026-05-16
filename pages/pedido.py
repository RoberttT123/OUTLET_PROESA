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
    actualizar_stock_batch_sheets,   # ← función batch nueva (ver sheets_additions.py)
)
from src.database import obtener_datos_empleado, validar_empleado

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
.block-container {
    padding-top: 0.2rem !important;
    padding-bottom: 0rem !important;
}
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

#MainMenu, header, footer { visibility: hidden; }
.stAppViewContainer footer { display: none !important; }
footer { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }
.reportview-container footer { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
.stDeployButton { display: none !important; }
div[data-testid="stAppViewContainer"] > footer { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ── LOGO ────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def get_logo_b64(path="assets/logo_proesa.png"):
    """Carga el logo una sola vez y lo cachea para no releerlo en cada rerun."""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return None

# ── SESSION STATE ───────────────────────────────────────────────────────────
defaults = {
    'logged_in': False,
    'cod_emp': None,
    'nom_emp': None,
    'empresa': None,
    'regional': None,
    'carrito': [],
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ── CARGAR INVENTARIO (cacheado 5 min) ──────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def cargar_inventario():
    return obtener_inventario_sheets(INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME)

df_inv = cargar_inventario()

if df_inv.empty:
    st.error("❌ No se pudo cargar el catálogo.")
    st.stop()

# ── PRE-PROCESAR INVENTARIO UNA SOLA VEZ ────────────────────────────────────
# Construir índice nombre→fila para búsquedas O(1) en lugar de filtrar el df
# cada vez que se muestra un producto.
@st.cache_data(show_spinner=False)
def construir_indice(df_hash):
    """Devuelve dict {nombre: fila_dict} para acceso instantáneo."""
    df = df_inv.copy()
    col_nombre = "Nombre Producto" if "Nombre Producto" in df.columns else df.columns[2]
    col_codigo = "Código Producto" if "Código Producto" in df.columns else df.columns[1]
    indice = {}
    for _, row in df.iterrows():
        nombre = row[col_nombre]
        if pd.notna(nombre):
            indice[nombre] = row
    return indice

# Usamos el shape como proxy de hash para el cache
indice_productos = construir_indice(str(df_inv.shape))


# ═════════════════════════════════════════════════════════════════════════════
# PANTALLA 1: LOGIN
# ═════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    logo_b64 = get_logo_b64()

    st.markdown(f"""
    <div class="hero-login">
        {f'<img src="data:image/png;base64,{logo_b64}" style="height:210px;width:auto;object-fit:contain;margin-top:-20px;margin-bottom:0px;">' if logo_b64 else ''}
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
                    st.session_state.cod_emp   = cod_inp
                    st.session_state.nom_emp   = datos['nombre']
                    st.session_state.empresa   = datos['empresa']
                    st.session_state.regional  = datos['regional']
                    st.rerun()
                else:
                    st.error(f"❌ Código '{cod_inp}' no encontrado. Verifica tu código de empleado.")
            else:
                st.error("⚠️ Ingresa tu código de empleado.")


# ═════════════════════════════════════════════════════════════════════════════
# PANTALLA 2: PEDIDOS  (todo envuelto en @st.fragment)
# El header/logo/estilos quedan fuera y NO se recargan al agregar al carrito.
# ═════════════════════════════════════════════════════════════════════════════
else:
    # El header se renderiza UNA vez y no vuelve a ejecutarse dentro del fragment
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

    # ──────────────────────────────────────────────────────────────────────────
    # FRAGMENT: catálogo + carrito
    # st.rerun(scope="fragment") solo rerenderiza ESTE bloque, no toda la página.
    # El header, estilos y logo de arriba NO se vuelven a ejecutar.
    # ──────────────────────────────────────────────────────────────────────────
    @st.fragment
    def render_catalogo_y_carrito():
        col_pedido, col_carrito = st.columns([2, 1], gap="medium")

        # ── COLUMNA 1: CATÁLOGO ──────────────────────────────────────────────
        with col_pedido:
            st.markdown('<div class="section-title">📦 Catálogo de Productos</div>', unsafe_allow_html=True)

            busqueda = st.text_input(
                "Busca un producto...",
                placeholder="Escribe el nombre o código para filtrar"
            )

            col_nombre = "Nombre Producto" if "Nombre Producto" in df_inv.columns else df_inv.columns[2]
            col_codigo = "Código Producto" if "Código Producto" in df_inv.columns else df_inv.columns[1]
            col_stock  = "Stock"           if "Stock"           in df_inv.columns else df_inv.columns[3]
            col_precio = "Precio Unitario" if "Precio Unitario" in df_inv.columns else df_inv.columns[4]

            # Filtrado vectorizado: una sola operación sobre todo el df
            if busqueda:
                mascara = (
                    df_inv[col_nombre].str.contains(busqueda, case=False, na=False) |
                    df_inv[col_codigo].astype(str).str.contains(busqueda, case=False, na=False)
                )
                df_filtrado = df_inv[mascara].head(5)
            else:
                df_filtrado = df_inv.head(5)

            if df_filtrado.empty:
                st.info("No se encontraron productos con ese nombre.")
            else:
                st.caption(f"Mostrando {len(df_filtrado)} productos · escribe para filtrar")

                for _, fila in df_filtrado.iterrows():
                    try:
                        stock  = int(float(fila[col_stock]))
                        precio = float(fila[col_precio])
                        codigo = str(fila[col_codigo])
                        nombre = fila[col_nombre]
                    except Exception:
                        continue

                    if stock <= 0:
                        stock_badge = '<span class="stock-out">❌ Agotado</span>'
                        disabled = True
                    else:
                        stock_badge = f'<span class="stock-ok">✅ {stock} disponibles</span>'
                        disabled = False

                    with st.container():
                        c1, c2, c3 = st.columns([2, 1.2, 0.8])
                        with c1:
                            st.markdown(f"**{nombre}**\n`{codigo}`")
                        with c2:
                            st.markdown(f"**Bs {precio:,.2f}**\n{stock_badge}", unsafe_allow_html=True)
                        with c3:
                            if not disabled:
                                cant = st.number_input(
                                    "Cant", min_value=1, max_value=max(stock, 1),
                                    value=1, key=f"qty_{codigo}"
                                )
                                if st.button("➕", key=f"btn_{codigo}"):
                                    st.session_state.carrito.append({
                                        "codigo_producto": codigo,
                                        "producto": nombre,
                                        "cantidad": int(cant),
                                        "precio_unitario": precio,
                                        "subtotal": precio * int(cant)
                                    })
                                    # ✅ Solo rerenderiza el fragment, NO toda la página
                                    st.rerun(scope="fragment")

        # ── COLUMNA 2: CARRITO ───────────────────────────────────────────────
        with col_carrito:
            st.markdown('<div class="section-title">🛒 Tu Carrito</div>', unsafe_allow_html=True)

            if st.session_state.carrito:
                for i, item in enumerate(st.session_state.carrito):
                    col_info, col_del = st.columns([4, 1])

                    with col_info:
                        st.markdown(
                            f"**{item['producto']}**\n\n"
                            f"{item['cantidad']} × Bs {item['precio_unitario']:,.2f}\n\n"
                            f"**Bs {item['subtotal']:,.2f}**"
                        )
                    with col_del:
                        if st.button("❌", key=f"del_{i}"):
                            st.session_state.carrito.pop(i)
                            st.rerun(scope="fragment")  # ✅ Solo el fragment

                total = sum(item['subtotal'] for item in st.session_state.carrito)
                st.markdown(f"""
                <div class="carrito-total">
                    <div style="font-size:0.75rem;color:#A8B2C8;margin-bottom:0.3rem">TOTAL</div>
                    <div style="font-size:2rem;font-weight:700;font-family:'DM Mono',monospace">Bs {total:,.2f}</div>
                </div>
                """, unsafe_allow_html=True)

                if st.button("✅ ENVIAR PEDIDO", type="primary", use_container_width=True):
                    _enviar_pedido()

            else:
                st.info("Tu carrito está vacío.\nAgrega productos a la izquierda.")

    # ──────────────────────────────────────────────────────────────────────────
    # FUNCIÓN: enviar pedido (fuera del fragment para poder hacer st.rerun() global)
    # ──────────────────────────────────────────────────────────────────────────
    def _enviar_pedido():
        items_para_sheets = []
        for item in st.session_state.carrito:
            fila = indice_productos.get(item['producto'])
            if fila is None:
                continue
            col_linea   = "Línea"          if "Línea"          in fila.index else fila.index[0]
            col_codigo2 = "Código Producto" if "Código Producto" in fila.index else fila.index[1]
            col_stock2  = "Stock"           if "Stock"          in fila.index else fila.index[3]
            col_empresa = "Empresa"         if "Empresa"        in fila.index else fila.index[5]

            items_para_sheets.append({
                "codigo_producto": str(fila[col_codigo2]),
                "producto":        item['producto'],
                "cantidad":        item['cantidad'],
                "precio_unitario": item['precio_unitario'],
                "linea":           str(fila[col_linea]),
                "descuento":       0,
                "stock_actual":    int(fila[col_stock2]),
                "empresa":         st.session_state.empresa or str(fila[col_empresa])
            })

        # ── FEEDBACK VISUAL mientras se procesa ─────────────────────────────
        with st.status("Procesando tu pedido...", expanded=True) as status:
            st.write("📝 Registrando pedido...")
            exito = guardar_pedido_sheets(
                st.session_state.cod_emp,
                st.session_state.nom_emp,
                items_para_sheets,
                PEDIDOS_SHEET_URL,
                PEDIDOS_HOJA_NAME
            )

            if exito:
                st.write("📦 Actualizando stock en la nube...")
                # ✅ UNA sola llamada HTTP en lugar de N llamadas secuenciales
                actualizar_stock_batch_sheets(
                    items=[{
                        "codigo_producto":  i["codigo_producto"],
                        "cantidad_a_restar": i["cantidad"]
                    } for i in items_para_sheets],
                    url_sheet=INVENTARIO_SHEET_URL,
                    hoja=INVENTARIO_HOJA_NAME
                )

                st.session_state.carrito = []
                st.cache_data.clear()
                status.update(label="✅ ¡Pedido enviado con éxito!", state="complete")
                st.balloons()
                st.rerun()
            else:
                status.update(label="❌ Error al enviar pedido.", state="error")
                st.error("No se pudo guardar el pedido. Intenta de nuevo.")

    # Llamar al fragment
    render_catalogo_y_carrito()

    # ── HISTORIAL ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-title">📋 Tus Pedidos Anteriores</div>', unsafe_allow_html=True)

    @st.cache_data(ttl=120, show_spinner=False)
    def _cargar_historial(cod_emp):
        return obtener_pedidos_empleado_sheets(cod_emp, PEDIDOS_SHEET_URL, PEDIDOS_HOJA_NAME)

    mis_pedidos = _cargar_historial(st.session_state.cod_emp)

    if not mis_pedidos.empty:
        for _, pedido in mis_pedidos.tail(5).iterrows():
            st.markdown(
                f"📦 **{pedido.get('Nombre Producto', 'N/A')}** · {pedido.get('Cantidad', 0)} ud.\n\n"
                f"📅 {pedido.get('Fecha Registro', '')}"
            )
    else:
        st.info("No has hecho pedidos aún.")

    st.markdown("---")
    if st.button("🚪 Cerrar Sesión"):
        for key in ['logged_in', 'cod_emp', 'nom_emp', 'empresa', 'regional', 'carrito']:
            st.session_state[key] = False if key == 'logged_in' else ([] if key == 'carrito' else None)
        st.rerun()