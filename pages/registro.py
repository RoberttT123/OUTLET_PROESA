import streamlit as st
import pandas as pd
import os
import base64
from datetime import datetime

# Importar configuración
try:
    from config import INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME, PEDIDOS_SHEET_URL, PEDIDOS_HOJA_NAME
    USING_SHEETS = True
except ImportError:
    USING_SHEETS = False

from src.nav import render_nav
from src.logic import validar_stock, preparar_fila_pedido
from src.database import obtener_datos_empleado, validar_empleado

# Importar funciones de BD según la configuración
if USING_SHEETS:
    from src.sheets import (
        obtener_inventario_sheets,
        obtener_todos_pedidos_sheets,
        guardar_pedido_sheets,
        actualizar_stock_batch_sheets,   # ← función batch nueva (ver sheets_additions.py)
    )
else:
    from src.database import guardar_pedido, actualizar_stock_inventario
    PATH_INV_SISTEMA = "data/inventario_maestro.xlsx"
    PATH_PEDIDOS     = "data/consolidado_pedidos.xlsx"

st.set_page_config(page_title="Registro de Pedidos", layout="wide", page_icon="📝")

# ── INICIALIZACIÓN DEL SESSION STATE ────────────────────────────────────────
defaults = {
    'carrito':          [],
    'emp_validado':     False,
    'cod_emp_validado': None,
    'nom_emp_validado': None,
    'empresa_validada': None,
    'regional_validada': None,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ── ESTILOS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

.stApp { background: #F5F4F0; }
.block-container {
    padding-top: 0.2rem !important;
    padding-bottom: 0rem !important;
}
.page-header {
    background: #FFFFFF;
    border-radius: 16px;
    padding: 1.5rem 2rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    display: flex;
    align-items: center;
    gap: 1rem;
    border-top: 4px solid #E63946;
}
.page-header h2 {
    color: #1A1A2E;
    font-size: 1.5rem;
    font-weight: 600;
    margin: 0;
}
.page-header p { color: #888; margin: 0.2rem 0 0; font-size: 0.9rem; }

.prod-info-box {
    background: #F0F7FF;
    border: 1px solid #BFDBFE;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin: 0.75rem 0;
}
.prod-info-box .label {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #60A5FA;
    font-weight: 700;
}
.prod-info-box .value {
    font-size: 1.1rem;
    font-weight: 600;
    color: #1D4ED8;
    font-family: 'DM Mono', monospace;
}

.stock-ok   { background: #D1FAE5; color: #065F46; border-radius: 20px; padding: 3px 12px; font-size: 0.8rem; font-weight: 600; display: inline-block; }
.stock-warn { background: #FEF9C3; color: #854D0E; border-radius: 20px; padding: 3px 12px; font-size: 0.8rem; font-weight: 600; display: inline-block; }
.stock-out  { background: #FEE2E2; color: #991B1B; border-radius: 20px; padding: 3px 12px; font-size: 0.8rem; font-weight: 600; display: inline-block; }

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

.stat-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: #FFFFFF;
    border-radius: 20px;
    padding: 0.4rem 1rem;
    box-shadow: 0 1px 6px rgba(0,0,0,0.08);
    font-size: 0.85rem;
    font-weight: 600;
    color: #1A1A2E;
    margin-right: 0.5rem;
    margin-bottom: 0.5rem;
}

.emp-info-card {
    background: #F0F7FF;
    border: 1px solid #BFDBFE;
    border-radius: 10px;
    padding: 1rem;
    margin-bottom: 1rem;
}

.carrito-item {
    background: #FFFFFF;
    border-radius: 10px;
    padding: 1rem;
    margin-bottom: 0.5rem;
    border-left: 3px solid #E63946;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
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

# ── VERIFICACIÓN Y CARGA DE DATOS ───────────────────────────────────────────
if USING_SHEETS:
    @st.cache_data(ttl=300, show_spinner=False)
    def cargar_inventario():
        return obtener_inventario_sheets(INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME)

    df_inv = cargar_inventario()
    if df_inv.empty:
        st.error("❌ No se pudo cargar el inventario de Google Sheets.")
        st.stop()
else:
    if not os.path.exists("data/inventario_maestro.xlsx"):
        st.error("⚠️ No se ha detectado el Inventario Maestro.")
        st.stop()
    df_inv = pd.read_excel("data/inventario_maestro.xlsx")

render_nav(active_page='registro', inventario_df=df_inv)

# ── PRE-CALCULAR COLUMNAS UNA SOLA VEZ ──────────────────────────────────────
COL_NOMBRE  = "Nombre Producto"  if "Nombre Producto"  in df_inv.columns else df_inv.columns[2]
COL_CODIGO  = "Código Producto"  if "Código Producto"  in df_inv.columns else df_inv.columns[1]
COL_STOCK   = "Stock"            if "Stock"            in df_inv.columns else df_inv.columns[3]
COL_PRECIO  = "Precio Unitario"  if "Precio Unitario"  in df_inv.columns else df_inv.columns[4]
COL_LINEA   = "Línea"            if "Línea"            in df_inv.columns else df_inv.columns[0]
COL_EMPRESA = "Empresa"          if "Empresa"          in df_inv.columns else df_inv.columns[5]

# Índice nombre→fila para búsqueda O(1) sin filtrar el df cada vez
@st.cache_data(show_spinner=False)
def construir_indice(_shape_key):
    return {row[COL_NOMBRE]: row for _, row in df_inv.iterrows() if pd.notna(row[COL_NOMBRE])}

indice_productos = construir_indice(str(df_inv.shape))

# ── LOGO ────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def get_logo_b64(path="assets/logo_proesa.png"):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return None

# ── HEADER ──────────────────────────────────────────────────────────────────
logo_b64 = get_logo_b64()
logo_html = (
    f'<img src="data:image/png;base64,{logo_b64}" style="height:150px;object-fit:contain;">'
    if logo_b64
    else '<div style="font-size:2.2rem">📝</div>'
)
st.markdown(f"""
<div class="page-header">
    {logo_html}
    <div>
        <h2>Registro de Movimientos</h2>
        <p>Gestiona pedidos y consulta el historial de operaciones</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ── TABS ────────────────────────────────────────────────────────────────────
tab_form, tab_historial = st.tabs(["🛒  Nuevo Pedido", "📊  Historial"])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — NUEVO PEDIDO CON CARRITO
# ════════════════════════════════════════════════════════════════════════════
with tab_form:
    col_form, col_info = st.columns([3, 2], gap="large")

    with col_form:
        st.markdown('<div class="section-title">Validación de Empleado</div>', unsafe_allow_html=True)

        # ── FORM PARA VALIDAR EMPLEADO ──────────────────────────────────────
        with st.form("validar_empleado_form"):
            cod_inp = st.text_input(
                "Código de Empleado",
                placeholder="Ej: E0200491",
                value="" if not st.session_state.emp_validado else st.session_state.cod_emp_validado
            ).upper().strip()

            if st.form_submit_button("✅ Validar Empleado", use_container_width=True):
                if cod_inp:
                    datos = obtener_datos_empleado(cod_inp)
                    if datos.get('encontrado'):
                        st.session_state.emp_validado      = True
                        st.session_state.cod_emp_validado  = cod_inp
                        st.session_state.nom_emp_validado  = datos['nombre']
                        st.session_state.empresa_validada  = datos['empresa']
                        st.session_state.regional_validada = datos['regional']
                        st.success(f"✅ Empleado encontrado: {datos['nombre']}")
                        st.rerun()
                    else:
                        st.error(f"❌ Código '{cod_inp}' no encontrado en la base de datos.")
                else:
                    st.error("⚠️ Ingresa un código de empleado.")

        # ── DATOS DEL EMPLEADO VALIDADO ──────────────────────────────────────
        if st.session_state.emp_validado:
            st.markdown(f"""
            <div class="emp-info-card">
                <strong>✅ Empleado Validado</strong><br>
                <small>
                👤 <strong>{st.session_state.nom_emp_validado or 'N/A'}</strong><br>
                🏢 Empresa: <strong>{st.session_state.empresa_validada or 'N/A'}</strong><br>
                🌍 Regional: <strong>{st.session_state.regional_validada or 'N/A'}</strong><br>
                🔖 Código: <strong>{st.session_state.cod_emp_validado or 'N/A'}</strong>
                </small>
            </div>
            """, unsafe_allow_html=True)

            if st.button("🔄 Cambiar Empleado"):
                st.session_state.emp_validado = False
                st.session_state.carrito      = []
                st.rerun()

            # ── SELECCIÓN DE PRODUCTOS ──────────────────────────────────────
            st.markdown('<div class="section-title">Selección de Producto</div>', unsafe_allow_html=True)

            with st.form("registro_operativo"):
                busqueda_prod = st.text_input(
                    "Busca un producto...",
                    placeholder="Escribe el nombre o código para filtrar"
                )

                # ✅ Filtrado vectorizado: una sola pasada sobre el df completo
                if busqueda_prod:
                    mascara = (
                        df_inv[COL_NOMBRE].str.contains(busqueda_prod, case=False, na=False) |
                        df_inv[COL_CODIGO].astype(str).str.contains(busqueda_prod, case=False, na=False)
                    )
                    prods_filtrados = df_inv[mascara][COL_NOMBRE].dropna().tolist()
                else:
                    prods_filtrados = df_inv[COL_NOMBRE].dropna().tolist()

                prod_sel = st.selectbox(
                    "Producto",
                    options=prods_filtrados,
                    index=None,
                    placeholder="Escribe para filtrar...",
                    label_visibility="collapsed"
                )

                cant = st.number_input("Cantidad a pedir", min_value=1, step=1, value=1)

                btn_col1, _ = st.columns([2, 1])
                with btn_col1:
                    btn_agregar = st.form_submit_button("➕ Añadir al Carrito", use_container_width=True)

                if btn_agregar:
                    if prod_sel:
                        # ✅ Acceso O(1) por índice en lugar de filtrar el df
                        fila_p = indice_productos.get(prod_sel)
                        if fila_p is not None:
                            stock_actual     = fila_p[COL_STOCK]
                            cant_en_carrito  = sum(
                                i['cantidad'] for i in st.session_state.carrito
                                if i['producto'] == prod_sel
                            )

                            if validar_stock(cant + cant_en_carrito, stock_actual):
                                precio_unit = float(fila_p[COL_PRECIO]) if pd.notna(fila_p[COL_PRECIO]) else 0
                                st.session_state.carrito.append({
                                    "producto":  prod_sel,
                                    "cantidad":  int(cant),
                                    "fila_data": fila_p,
                                    "subtotal":  precio_unit * int(cant)
                                })
                                st.toast(f"✅ Agregado: {prod_sel}")
                                st.rerun()
                            else:
                                st.error(f"❌ Stock insuficiente. Solo quedan **{int(stock_actual)}** unidades.")
                    else:
                        st.warning("⚠️ Selecciona un producto.")

            # ── VISUALIZACIÓN DEL CARRITO ────────────────────────────────────
            if st.session_state.carrito:
                st.markdown('<div class="section-title">Tu Pedido Actual</div>', unsafe_allow_html=True)

                for i, item in enumerate(st.session_state.carrito):
                    with st.container():
                        c_prod, c_cant, c_price, c_del = st.columns([3, 1, 1.5, 0.5])
                        c_prod.write(f"**{item['producto']}**")
                        c_cant.write(f"{item['cantidad']} ud.")
                        c_price.write(f"Bs {item['subtotal']:,.2f}")
                        if c_del.button("❌", key=f"del_{i}", use_container_width=True):
                            st.session_state.carrito.pop(i)
                            st.rerun()

                st.write("---")
                monto_total_carrito = sum(item['subtotal'] for item in st.session_state.carrito)
                st.markdown(f"### Total Pedido: Bs {monto_total_carrito:,.2f}")

                # ── BOTÓN ENVIAR PEDIDO ──────────────────────────────────────
                if st.button("✅  CONFIRMAR Y ENVIAR TODO EL PEDIDO", type="primary", use_container_width=True):
                    try:
                        if USING_SHEETS:
                            # Preparar items
                            items_para_sheets = []
                            for item in st.session_state.carrito:
                                fila = item['fila_data']
                                items_para_sheets.append({
                                    "codigo_producto": str(fila[COL_CODIGO]),
                                    "producto":        item['producto'],
                                    "cantidad":        item['cantidad'],
                                    "precio_unitario": float(fila[COL_PRECIO]),
                                    "linea":           str(fila[COL_LINEA]),
                                    "descuento":       0,
                                    "stock_actual":    int(fila[COL_STOCK]),
                                    "empresa":         st.session_state.empresa_validada or str(fila[COL_EMPRESA])
                                })

                            # ✅ Feedback visual mientras se procesa
                            with st.status("Procesando pedido...", expanded=True) as status:
                                st.write("📝 Guardando en el registro...")
                                guardado = guardar_pedido_sheets(
                                    st.session_state.cod_emp_validado,
                                    st.session_state.nom_emp_validado,
                                    items_para_sheets,
                                    PEDIDOS_SHEET_URL,
                                    PEDIDOS_HOJA_NAME
                                )

                                if guardado:
                                    st.write("📦 Actualizando stock...")
                                    # ✅ UNA sola llamada HTTP en vez de N secuenciales
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
                                    status.update(label="✅ ¡Pedido enviado y stock actualizado!", state="complete")
                                    st.rerun()
                                else:
                                    status.update(label="❌ Error al guardar el pedido.", state="error")
                                    st.error("❌ Error al guardar pedido en Google Sheets")

                        else:
                            # Modo local (sin Sheets)
                            with st.status("Guardando pedido...", expanded=True) as status:
                                st.write("📝 Escribiendo en archivo local...")
                                for item in st.session_state.carrito:
                                    nueva_fila = preparar_fila_pedido(
                                        st.session_state.cod_emp_validado,
                                        st.session_state.nom_emp_validado,
                                        item['fila_data'],
                                        item['cantidad']
                                    )
                                    guardar_pedido(nueva_fila)
                                    actualizar_stock_inventario(item['fila_data'].iloc[1], item['cantidad'])

                                st.session_state.carrito = []
                                status.update(label=f"✅ Pedido guardado para: {st.session_state.nom_emp_validado}", state="complete")
                                st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error en el proceso: {str(e)}")

        else:
            st.info("👆 Valida un empleado para comenzar a registrar pedidos.")

    # ── PANEL LATERAL: VISTA PREVIA DEL PRODUCTO ────────────────────────────
    with col_info:
        st.markdown('<div class="section-title">Vista Previa del Producto</div>', unsafe_allow_html=True)

        if st.session_state.emp_validado and 'prod_sel' in locals() and prod_sel:
            # ✅ Acceso O(1) por índice
            fila_preview = indice_productos.get(prod_sel)

            if fila_preview is not None:
                stock_prev  = int(fila_preview[COL_STOCK])
                precio_prev = float(fila_preview[COL_PRECIO])
                codigo_prev = fila_preview[COL_CODIGO]
                linea_prev  = fila_preview[COL_LINEA]
                empresa_prev= fila_preview[COL_EMPRESA]

                if stock_prev <= 0:
                    stock_badge = '<span class="stock-out">⛔ Agotado</span>'
                elif stock_prev <= 5:
                    stock_badge = f'<span class="stock-warn">⚠️ Stock bajo: {stock_prev} ud.</span>'
                else:
                    stock_badge = f'<span class="stock-ok">✅ En stock: {stock_prev} ud.</span>'

                st.markdown(f"""
                <div class="prod-info-box">
                    <div class="label">Código</div>
                    <div class="value">{codigo_prev}</div>
                </div>
                <div class="prod-info-box">
                    <div class="label">Línea</div>
                    <div class="value" style="font-size:0.95rem">{linea_prev}</div>
                </div>
                <div class="prod-info-box">
                    <div class="label">Empresa</div>
                    <div class="value" style="font-size:0.95rem">{empresa_prev}</div>
                </div>
                <div class="prod-info-box">
                    <div class="label">Precio Unitario</div>
                    <div class="value">Bs {precio_prev:,.2f}</div>
                </div>
                <div style="margin-top:0.75rem">{stock_badge}</div>
                """, unsafe_allow_html=True)

                if 'cant' in locals() and cant and cant > 0:
                    total_est = cant * precio_prev
                    st.markdown(f"""
                    <div style="background:#1A1A2E;color:white;border-radius:10px;padding:1rem 1.25rem;margin-top:0.75rem">
                        <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:1px;color:#A8B2C8;margin-bottom:0.3rem">Total estimado</div>
                        <div style="font-size:1.6rem;font-weight:700;font-family:'DM Mono',monospace">Bs {total_est:,.2f}</div>
                        <div style="font-size:0.78rem;color:#A8B2C8;margin-top:0.2rem">{int(cant)} ud. × Bs {precio_prev:,.2f}</div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background:#F9F9F9;border:2px dashed #DDD;border-radius:12px;padding:2rem;text-align:center;color:#BBB;">
                <div style="font-size:2rem;margin-bottom:0.5rem">🔍</div>
                <div style="font-size:0.9rem">Selecciona un producto<br>para ver su detalle</div>
            </div>
            """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — HISTORIAL
# ════════════════════════════════════════════════════════════════════════════
with tab_historial:
    if USING_SHEETS:
        @st.cache_data(ttl=120, show_spinner=False)
        def _cargar_historial_completo():
            return obtener_todos_pedidos_sheets(PEDIDOS_SHEET_URL, PEDIDOS_HOJA_NAME)
        df_p = _cargar_historial_completo()
    else:
        if os.path.exists("data/consolidado_pedidos.xlsx"):
            df_p = pd.read_excel("data/consolidado_pedidos.xlsx")
        else:
            df_p = pd.DataFrame()

    if not df_p.empty:
        total_pedidos  = len(df_p)
        total_unidades = int(df_p["Cantidad"].sum()) if "Cantidad" in df_p.columns else 0

        st.markdown(f"""
        <div style="margin:1rem 0 1.25rem">
            <div class="stat-pill">📋 {total_pedidos} <span>pedidos</span></div>
            <div class="stat-pill">📦 {total_unidades:,} <span>unidades</span></div>
        </div>
        """, unsafe_allow_html=True)

        st.dataframe(df_p, use_container_width=True, height=400)

        try:
            csv = df_p.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"Pedidos_{datetime.now().strftime('%d_%m_%Y')}.csv",
                mime="text/csv"
            )
        except Exception:
            pass
    else:
        st.info("No hay pedidos registrados en el historial.")