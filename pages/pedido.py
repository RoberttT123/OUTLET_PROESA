# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import base64
from datetime import datetime

# ==============================================================================
# 1. CONFIGURACIÓN
# ==============================================================================
try:
    from config import (
        INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME,
        PEDIDOS_SHEET_URL,    PEDIDOS_HOJA_NAME
    )
except ImportError:
    st.error("❌ Archivo `config.py` no encontrado.")
    st.stop()

try:
    from src.sheets import (
        obtener_inventario_sheets,
        obtener_pedidos_empleado_sheets,
        guardar_pedido_sheets,
        actualizar_stock_batch_sheets,
        verificar_stock_disponible,
    )
    from src.database import obtener_datos_empleado, validar_empleado
    from src.componentes import cargar_estilos_css, render_tarjeta_producto
except ImportError as e:
    st.error("❌ Error cargando módulos de `src/`.")
    st.code(str(e))
    st.stop()

try:
    st.set_page_config(
        page_title="Mi Pedido - Outlet PROESA",
        layout="wide",
        page_icon="🛒",
        initial_sidebar_state="collapsed"
    )
except Exception:
    pass

try:
    cargar_estilos_css()
except Exception as e:
    st.warning(f"⚠️ Estilos no aplicados: {e}")

# CSS extra: tabs via radio button (igual visual que st.tabs, funciona en mobile)
st.markdown("""
<style>
/* ── Hacer que st.radio horizontal parezca exactamente st.tabs ── */
div[data-testid="stRadio"] {
    border-bottom: 1px solid #e6e6e6;
    margin-bottom: 1.2rem;
    padding-bottom: 0;
}
div[data-testid="stRadio"] > div[role="radiogroup"] {
    gap: 0 !important;
    flex-wrap: nowrap !important;
    overflow-x: auto;
}
div[data-testid="stRadio"] label {
    padding: 0.55rem 1.1rem !important;
    margin: 0 !important;
    border-radius: 0 !important;
    border-bottom: 3px solid transparent !important;
    color: #888 !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    background: transparent !important;
    white-space: nowrap !important;
    cursor: pointer !important;
    transition: color 0.15s;
}
div[data-testid="stRadio"] label:hover { color: #1A1A2E !important; }
/* Pestaña activa */
div[data-testid="stRadio"] label[data-checked="true"] {
    color: #1A1A2E !important;
    font-weight: 600 !important;
    border-bottom: 3px solid #E63946 !important;
}
/* Ocultar círculo del radio */
div[data-testid="stRadio"] [data-testid="stWidgetLabel"] { display: none !important; }
div[data-testid="stRadio"] span[data-testid="stMarkdownContainer"] p { margin: 0; }
div[data-testid="stRadio"] div[data-baseweb="radio"] > div:first-child { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. LOGO
# ==============================================================================
@st.cache_data(show_spinner=False)
def get_logo_b64(path="assets/logo_proesa.png"):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None

# ==============================================================================
# 3. SESSION STATE
# ==============================================================================
defaults = {
    'logged_in': False, 'cod_emp': None, 'nom_emp': None,
    'empresa': None,    'regional': None, 'carrito': [],
    'tab_idx': 0,       # 0=Catálogo  1=Carrito  2=Historial
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==============================================================================
# 4. PARSEO ROBUSTO (numericise_ignore=['all'] → todo llega como string)
# ==============================================================================
def _parse_stock(v) -> int:
    try:
        return max(0, int(float(str(v).strip().replace(',', ''))))
    except Exception:
        return 0

def _parse_precio(v) -> float:
    try:
        return float(str(v).strip().replace(',', '.'))
    except Exception:
        return 0.0

# ==============================================================================
# 5. INVENTARIO E ÍNDICE
# ==============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def cargar_inventario():
    try:
        df = obtener_inventario_sheets(INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME)
        return df if df is not None and not df.empty else pd.DataFrame()
    except Exception as e:
        st.error(f"Error cargando inventario: {e}")
        return pd.DataFrame()

@st.cache_data(show_spinner=False)
def construir_indice(shape_key):
    col = "Nombre Producto" if "Nombre Producto" in df_inv.columns else df_inv.columns[2]
    return {str(r[col]).strip(): r for _, r in df_inv.iterrows() if pd.notna(r[col])}

df_inv = cargar_inventario()
if df_inv.empty:
    st.error("❌ Catálogo no disponible. Verifica la conexión o config.py.")
    st.stop()

indice_productos = construir_indice(str(df_inv.shape))

# Nombres de columnas
COL_NOMBRE = "Nombre Producto" if "Nombre Producto" in df_inv.columns else df_inv.columns[2]
COL_CODIGO = "Código Producto" if "Código Producto" in df_inv.columns else df_inv.columns[1]
COL_STOCK  = "Stock"           if "Stock"           in df_inv.columns else df_inv.columns[3]
COL_PRECIO = "Precio Unitario" if "Precio Unitario" in df_inv.columns else df_inv.columns[4]
COL_LINEA  = "Línea"           if "Línea"           in df_inv.columns else df_inv.columns[0]
COL_EMP    = "Empresa"         if "Empresa"         in df_inv.columns else df_inv.columns[5]
COL_IMAGEN = "Imagen"          if "Imagen"          in df_inv.columns else None


# ==============================================================================
# PANTALLA 1: LOGIN
# ==============================================================================
if not st.session_state.logged_in:
    logo = get_logo_b64()
    
    # CORRECCIÓN SINTAXIS 1: Procesar el HTML del logo afuera del f-string principal
    html_logo = f'<img src="data:image/png;base64,{logo}" style="height:210px;width:auto;object-fit:contain;margin-top:-20px;">' if logo else ''
    
    st.markdown(f"""
    <div class="hero-login">
        {html_logo}
        <h1 style="margin-top:0;">Outlet PROESA</h1>
        <p style="margin-bottom:0;">Sistema de Pedidos Internos para Empleados</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        st.subheader("🔑 Acceso al Sistema")
        cod = st.text_input(
            "Código de Empleado", placeholder="Ej: E0200491",
            help="Consulte con su supervisor si desconoce su código."
        ).upper().strip()
        st.markdown("<br>", unsafe_allow_html=True)

        if st.form_submit_button("🚀 Validar Credenciales", use_container_width=True):
            if cod:
                with st.spinner("Consultando registros..."):
                    try:
                        datos = obtener_datos_empleado(cod)
                        if datos and datos.get('encontrado'):
                            st.session_state.logged_in = True
                            st.session_state.cod_emp   = cod
                            st.session_state.nom_emp   = datos.get('nombre', 'Empleado')
                            st.session_state.empresa   = datos.get('empresa', 'N/A')
                            st.session_state.regional  = datos.get('regional', 'N/A')
                            st.success("✅ Acceso autorizado.")
                            st.rerun()
                        else:
                            st.error(f"❌ Código '{cod}' no registrado.")
                    except Exception as e:
                        st.error(f"Error en verificación: {e}")
            else:
                st.error("⚠️ Ingresa tu código de empleado.")


# ==============================================================================
# PANTALLA 2: PEDIDOS
# ==============================================================================
else:
    logo = get_logo_b64()
    
    # CORRECCIÓN SINTAXIS 2: Procesar el componente visual del header antes
    html_header_media = f'<img src="data:image/png;base64,{logo}" style="height:100px;object-fit:contain;">' if logo else "🛒"
    
    st.markdown(f"""
    <div class="page-header">
        {html_header_media}
        <div>
            <h2>Tu Pedido</h2>
            <p>👤 {st.session_state.nom_emp} · 🔖 {st.session_state.cod_emp} · 🏢 {st.session_state.empresa or 'PROESA'}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    @st.cache_data(ttl=120, show_spinner=False)
    def cargar_historial(cod):
        try:
            df = obtener_pedidos_empleado_sheets(cod, PEDIDOS_SHEET_URL, PEDIDOS_HOJA_NAME)
            return df if df is not None else pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    # ──────────────────────────────────────────────────────────────────────────
    # FRAGMENT principal
    # ──────────────────────────────────────────────────────────────────────────
    @st.fragment
    def render_pedido():
        total_uds = sum(int(i.get('cantidad', 0)) for i in st.session_state.carrito)
        label_c   = f"🛒 Carrito ({total_uds})" if total_uds > 0 else "🛒 Carrito"
        opciones  = ["📦 Catálogo", label_c, "📋 Mis Pedidos"]

        # ── st.radio estilizado como tabs ─────────────────────────────────────
        tab_sel = st.radio(
            "tabs_nav",
            opciones,
            index=int(st.session_state.tab_idx),
            horizontal=True,
            label_visibility="collapsed",
            key="radio_tabs_nav"
        )
        st.session_state.tab_idx = opciones.index(tab_sel)

        # ══════════════════════════════════════════════════════════════════════
        # TAB 0 — CATÁLOGO
        # ══════════════════════════════════════════════════════════════════════
        if st.session_state.tab_idx == 0:
            st.markdown('<div class="section-title">📦 Productos en Promoción</div>', unsafe_allow_html=True)

            filtro = st.text_input(
                "Filtrar catálogo:",
                placeholder="Palabras clave, marcas o códigos SKU...",
                key="busqueda_catalogo"
            )

            if filtro:
                expr    = str(filtro).strip()
                mascara = (
                    df_inv[COL_NOMBRE].astype(str).str.contains(expr, case=False, na=False) |
                    df_inv[COL_CODIGO].astype(str).str.strip().str.contains(expr, case=False, na=False)
                )
                df_vista = df_inv[mascara].head(8)
            else:
                df_vista = df_inv.head(6)

            if df_vista.empty:
                st.info("🔍 Ningún artículo coincide con los criterios.")
            else:
                st.caption(f"Visualizando {len(df_vista)} ítems disponibles.")

                for bloque in range(0, len(df_vista), 2):
                    cols = st.columns(2)
                    for j in range(2):
                        idx = bloque + j
                        if idx >= len(df_vista):
                            break
                        reg = df_vista.iloc[idx]

                        try:
                            stock  = _parse_stock(reg[COL_STOCK])
                            precio = _parse_precio(reg[COL_PRECIO])
                            codigo = str(reg[COL_CODIGO]).strip()
                            nombre = str(reg[COL_NOMBRE]).strip()
                            imagen = reg[COL_IMAGEN] if COL_IMAGEN and pd.notna(reg[COL_IMAGEN]) else ""
                        except Exception as e:
                            st.caption(f"⚠️ Error fila {idx}: {e}")
                            continue

                        if stock <= 0:
                            badge     = '<span class="stock-out">❌ Agotado</span>'
                            bloqueado = True
                        elif stock <= 5:
                            badge     = f'<span class="stock-warn">⚠️ Últimas {stock} ud.</span>'
                            bloqueado = False
                        else:
                            badge     = f'<span class="stock-ok">✅ {stock} Disponibles</span>'
                            bloqueado = False

                        with cols[j]:
                            render_tarjeta_producto(
                                codigo=codigo, nombre=nombre,
                                precio=precio, stock_badge=badge, url_foto=imagen
                            )
                            if not bloqueado:
                                c_num, c_btn = st.columns([1, 1.3])
                                with c_num:
                                    cant = st.number_input(
                                        "Cant", min_value=1, max_value=max(stock, 1),
                                        value=1, step=1,
                                        key=f"qty_{codigo}", label_visibility="collapsed"
                                    )
                                with c_btn:
                                    if st.button("➕ Solicitar", key=f"add_{codigo}", use_container_width=True):
                                        st.session_state.carrito.append({
                                            "codigo_producto": codigo,
                                            "producto":        nombre,
                                            "cantidad":        int(cant),
                                            "precio_unitario": precio,
                                            "subtotal":        precio * int(cant),
                                        })
                                        st.session_state.tab_idx = 0
                                        st.rerun(scope="fragment")
                            else:
                                st.button("🚫 No Disponible", key=f"dis_{codigo}",
                                          disabled=True, use_container_width=True)
                            st.markdown("<br>", unsafe_allow_html=True)

        # ══════════════════════════════════════════════════════════════════════
        # TAB 1 — CARRITO
        # ══════════════════════════════════════════════════════════════════════
        elif st.session_state.tab_idx == 1:
            st.markdown('<div class="section-title">🛒 Carrito de Compras</div>', unsafe_allow_html=True)

            if not st.session_state.carrito:
                st.info("Tu carrito está vacío. Agrega productos desde el Catálogo.")
            else:
                from src.componentes import render_estructura_item_carrito
                st.markdown('<div class="contenedor-carrito">', unsafe_allow_html=True)

                for pos, item in enumerate(st.session_state.carrito):
                    datos   = indice_productos.get(item['producto'])
                    s_max   = _parse_stock(datos[COL_STOCK]) if datos is not None else 999
                    foto    = datos[COL_IMAGEN] if datos is not None and COL_IMAGEN and COL_IMAGEN in datos else ""

                    c_info, c_cant, c_del = st.columns([2.5, 1.2, 0.4])

                    with c_info:
                        html_item = render_estructura_item_carrito(
                            nombre=item['producto'],
                            precio_total=item['subtotal'],
                            url_foto=foto
                        )
                        st.markdown(f'<div class="item-carrito">{html_item}</div>', unsafe_allow_html=True)

                    with c_cant:
                        st.markdown("<div style='margin-top:15px'></div>", unsafe_allow_html=True)
                        nueva_cant = st.number_input(
                            "Cant", min_value=1, max_value=s_max,
                            value=int(item['cantidad']), step=1,
                            key=f"cant_{pos}", label_visibility="collapsed"
                        )
                        if int(nueva_cant) != int(item['cantidad']):
                            st.session_state.carrito[pos]['cantidad'] = int(nueva_cant)
                            st.session_state.carrito[pos]['subtotal'] = int(nueva_cant) * item['precio_unitario']
                            st.session_state.tab_idx = 1
                            st.rerun(scope="fragment")

                    with c_del:
                        st.markdown("<div style='margin-top:15px'></div>", unsafe_allow_html=True)
                        if st.button("🗑️", key=f"del_{pos}", help="Eliminar"):
                            st.session_state.carrito.pop(pos)
                            st.session_state.tab_idx = 1
                            st.rerun(scope="fragment")

                st.markdown('</div>', unsafe_allow_html=True)

                total = sum(float(i['subtotal']) for i in st.session_state.carrito)
                st.markdown(f"""
                <hr style='border-color:#EBEBEB;margin:1rem 0;'>
                <div class="carrito-total-clon">
                    <span class="label-total">Total:</span>
                    <span class="monto-total">Bs {total:,.2f}</span>
                </div>
                """, unsafe_allow_html=True)

                if st.button("REALIZAR PEDIDO", type="primary",
                             use_container_width=True, key="btn_enviar"):
                    enviar_pedido()

        # ══════════════════════════════════════════════════════════════════════
        # TAB 2 — HISTORIAL
        # ══════════════════════════════════════════════════════════════════════
        elif st.session_state.tab_idx == 2:
            st.markdown('<div class="section-title">📋 Registro Histórico de Compras</div>', unsafe_allow_html=True)
            df_hist = cargar_historial(st.session_state.cod_emp)
            if df_hist is not None and not df_hist.empty:
                st.caption("Últimos artículos solicitados (orden cronológico descendente):")
                for _, p in df_hist.tail(10).iloc[::-1].iterrows():
                    st.markdown(
                        f"📦 **{p.get('Nombre Producto','N/A')}**<br>"
                        f"🔢 **{p.get('Cantidad', 0)} unidades**<br>"
                        f"📅 <small style='color:#777'>{p.get('Fecha Registro','N/A')}</small>",
                        unsafe_allow_html=True
                    )
                    st.markdown("<hr style='margin:0.4rem 0;border-style:dashed;border-color:#E0E0E0;'>",
                                unsafe_allow_html=True)
            else:
                st.info("No se registran transacciones previas en su cuenta.")

    # ──────────────────────────────────────────────────────────────────────────
    # ENVÍO DEL PEDIDO
    # ──────────────────────────────────────────────────────────────────────────
    def enviar_pedido():
        if not st.session_state.carrito:
            st.error("El carrito está vacío.")
            return

        items = []
        for item in st.session_state.carrito:
            fila = indice_productos.get(item['producto'])
            if fila is None:
                continue
            items.append({
                "codigo_producto": str(fila[COL_CODIGO]),
                "producto":        str(item['producto']),
                "cantidad":        int(item['cantidad']),
                "precio_unitario": float(item['precio_unitario']),
                "linea":           str(fila[COL_LINEA]),
                "descuento":       0,
                "stock_actual":    _parse_stock(fila[COL_STOCK]),
                "empresa":         st.session_state.empresa or str(fila[COL_EMP])
            })

        with st.status("Procesando tu pedido...", expanded=True) as estado:
            try:
                st.write("🔍 Verificando disponibilidad en tiempo real...")
                sin_stock = verificar_stock_disponible(
                    items=[{"codigo_producto": i["codigo_producto"],
                            "cantidad_a_restar": i["cantidad"]} for i in items],
                    url_sheet=INVENTARIO_SHEET_URL,
                    hoja=INVENTARIO_HOJA_NAME
                )
                if sin_stock:
                    estado.update(label="⚠️ Stock insuficiente.", state="error")
                    for p in sin_stock:
                        st.error(
                            f"❌ **{p['producto']}** — "
                            f"Pediste {p['pedido']} ud. pero solo quedan {p['disponible']}."
                        )
                    st.warning("Ajusta las cantidades en el carrito e intenta de nuevo.")
                    return

                st.write("📝 Registrando pedido...")
                ok = guardar_pedido_sheets(
                    st.session_state.cod_emp, st.session_state.nom_emp,
                    items, PEDIDOS_SHEET_URL, PEDIDOS_HOJA_NAME
                )
                if ok:
                    st.write("📦 Actualizando stock...")
                    actualizar_stock_batch_sheets(
                        items=[{"codigo_producto": i["codigo_producto"],
                                "cantidad_a_restar": i["cantidad"]} for i in items],
                        url_sheet=INVENTARIO_SHEET_URL, hoja=INVENTARIO_HOJA_NAME
                    )
                    st.session_state.carrito  = []
                    st.session_state.tab_idx  = 0
                    st.cache_data.clear()
                    estado.update(label="✅ ¡Pedido procesado con éxito!", state="complete")
                    st.toast("🎉 ¡Tu pedido fue enviado con éxito!", icon="🛒")
                    st.rerun()
                else:
                    estado.update(label="❌ Falló el registro.", state="error")
                    st.error("Google Sheets rechazó la inserción. Intenta de nuevo.")

            except Exception as e:
                estado.update(label="❌ Error inesperado.", state="error")
                st.error(f"Detalle: {e}")

    render_pedido()

    # ── Cerrar sesión ─────────────────────────────────────────────────────────
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        for k in ['logged_in','cod_emp','nom_emp','empresa','regional','carrito','tab_idx']:
            st.session_state[k] = False if k == 'logged_in' else ([] if k == 'carrito' else (0 if k == 'tab_idx' else None))
        st.rerun()