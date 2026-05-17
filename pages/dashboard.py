import streamlit as st
import pandas as pd
import base64
import os
from datetime import datetime

st.set_page_config(page_title="Dashboard General - PROESA", layout="wide", page_icon="📊")

try:
    from config import (
        INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME,
        PEDIDOS_SHEET_URL, PEDIDOS_HOJA_NAME
    )
    from src.sheets import obtener_inventario_sheets, obtener_todos_pedidos_sheets
    from src.nav import render_nav
    CONFIG_LOADED = True
except ImportError as e:
    st.error(f"❌ Error de configuración: {e}")
    st.stop()

# ── ESTILOS ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; margin-top: -20px; }
    .stMetric { background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); border-left: 5px solid #E63946; }
    .main-title { color: #1A1A2E; font-weight: 700; font-size: 2.2rem; margin-bottom: 0.5rem; }
    .subtitle   { color: #6B7280; margin-bottom: 2rem; }
    #MainMenu, header, footer { visibility: hidden; }
    .stAppViewContainer footer { display: none !important; }
    footer { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stToolbar"] { display: none !important; }
    .stDeployButton { display: none !important; }
</style>
""", unsafe_allow_html=True)


# ── DATOS: session_state como caché compartida entre páginas ─────────────────
#
# El flujo es:
#   1ª visita → no hay datos en session_state → carga de Sheets (~2-3 seg)
#   Navegación de vuelta → datos ya en session_state → instantáneo
#
# El botón "Actualizar" borra el session_state y fuerza una recarga fresca.

CACHE_TTL_SEGUNDOS = 300  # 5 minutos entre recargas automáticas

def _datos_expirados() -> bool:
    """Devuelve True si los datos son más viejos que CACHE_TTL_SEGUNDOS."""
    ts = st.session_state.get('dashboard_timestamp')
    if ts is None:
        return True
    return (datetime.now() - ts).total_seconds() > CACHE_TTL_SEGUNDOS

def cargar_datos():
    """Carga inventario y pedidos de Sheets y los guarda en session_state."""
    with st.spinner("Cargando datos..."):
        inv     = obtener_inventario_sheets(INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME)
        pedidos = obtener_todos_pedidos_sheets(PEDIDOS_SHEET_URL, PEDIDOS_HOJA_NAME)
        st.session_state['df_inv_dashboard']    = inv
        st.session_state['df_pedidos_dashboard'] = pedidos
        st.session_state['dashboard_timestamp']  = datetime.now()

# Cargar solo si no hay datos o si expiraron
if 'df_pedidos_dashboard' not in st.session_state or _datos_expirados():
    cargar_datos()

df_inv    = st.session_state['df_inv_dashboard']
df_pedidos = st.session_state['df_pedidos_dashboard']

# Compartir el inventario con otras páginas (app.py, registro.py)
if 'df_inventario_maestro' not in st.session_state and not df_inv.empty:
    st.session_state['df_inventario_maestro'] = df_inv

render_nav(active_page='dashboard', inventario_df=df_inv)

# ── ENCABEZADO ───────────────────────────────────────────────────────────────
st.markdown('<h1 class="main-title">📊 Panel de Control General</h1>', unsafe_allow_html=True)

ts = st.session_state.get('dashboard_timestamp')
if ts:
    st.markdown(
        f'<p class="subtitle">Análisis en tiempo real · '
        f'<span style="font-size:0.8rem;color:#9CA3AF">Actualizado: {ts.strftime("%H:%M:%S")}</span></p>',
        unsafe_allow_html=True
    )

if df_pedidos.empty:
    st.info("ℹ️ No se encontraron pedidos registrados en Google Sheets.")
    st.stop()

# ── KPIs ─────────────────────────────────────────────────────────────────────
st.markdown("### Resumen de Operaciones")
m1, m2, m3, m4 = st.columns(4)

df_pedidos['Cantidad']  = pd.to_numeric(df_pedidos['Cantidad'],  errors='coerce').fillna(0)
df_pedidos['Monto Uni'] = pd.to_numeric(df_pedidos['Monto Uni'], errors='coerce').fillna(0)
df_pedidos['Subtotal']  = df_pedidos['Monto Uni'] * df_pedidos['Cantidad']
df_inv['Stock']         = pd.to_numeric(df_inv['Stock'],         errors='coerce').fillna(0)

with m1:
    st.metric("Total Pedidos",    f"{len(df_pedidos):,}")
with m2:
    st.metric("Unidades Movidas", f"{int(df_pedidos['Cantidad'].sum()):,} ud.")
with m3:
    st.metric("Facturación Est.", f"Bs {df_pedidos['Subtotal'].sum():,.2f}")
with m4:
    criticos = len(df_inv[df_inv['Stock'] < 5])
    st.metric("Alertas Stock", f"{criticos} SKU", delta="- Crítico" if criticos > 0 else "OK")

st.markdown("---")

# ── FILTROS ───────────────────────────────────────────────────────────────────
st.markdown("### 🔍 Filtros de Búsqueda")
c_f1, c_f2, c_f3 = st.columns([1, 1, 2])

with c_f1:
    opciones_emp   = df_pedidos['Empresa'].unique().tolist() if 'Empresa' in df_pedidos.columns else []
    emp_sel        = st.multiselect("Filtrar por Empresa:", opciones_emp, default=opciones_emp)
with c_f2:
    opciones_linea = df_pedidos['Línea'].unique().tolist() if 'Línea' in df_pedidos.columns else []
    linea_sel      = st.multiselect("Filtrar por Línea:", opciones_linea, default=opciones_linea)
with c_f3:
    busqueda = st.text_input("Buscar por Empleado o Producto:", placeholder="Ej: Juan Perez / Coca Cola")

df_filtrado = df_pedidos.copy()
if emp_sel:
    df_filtrado = df_filtrado[df_filtrado['Empresa'].isin(emp_sel)]
if linea_sel:
    df_filtrado = df_filtrado[df_filtrado['Línea'].isin(linea_sel)]
if busqueda:
    df_filtrado = df_filtrado[
        df_filtrado['Nombre Empleado'].str.contains(busqueda, case=False, na=False) |
        df_filtrado['Nombre Producto'].str.contains(busqueda, case=False, na=False)
    ]

# ── TABLA ─────────────────────────────────────────────────────────────────────
st.markdown("### 📋 Historial Consolidado")
st.dataframe(
    df_filtrado,
    use_container_width=True,
    height=450,
    column_config={
        "Subtotal":        st.column_config.NumberColumn(format="Bs %.2f"),
        "Monto Uni":       st.column_config.NumberColumn(format="Bs %.2f"),
        "Fecha Registro":  st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm")
    }
)

# ── GRÁFICOS ──────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📈 Análisis de Demanda")
g1, g2 = st.columns(2)

with g1:
    st.write("**Top 5 Productos más Solicitados**")
    top_prods = df_pedidos.groupby('Nombre Producto')['Cantidad'].sum().sort_values(ascending=False).head(5)
    st.bar_chart(top_prods)
with g2:
    st.write("**Pedidos por Línea de Negocio**")
    if 'Línea' in df_pedidos.columns:
        st.bar_chart(df_pedidos.groupby('Línea').size())

# ── EXPORTACIÓN ───────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📥 Reportes")
exp_col1, exp_col2, exp_col3 = st.columns([1, 1, 2])

with exp_col1:
    if st.button("🔄 Actualizar Datos Ahora", use_container_width=True):
        # Borrar session_state del dashboard para forzar recarga fresca
        for k in ['df_inv_dashboard', 'df_pedidos_dashboard', 'dashboard_timestamp']:
            st.session_state.pop(k, None)
        st.rerun()

with exp_col2:
    csv = df_filtrado.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📥 Descargar CSV",
        data=csv,
        file_name=f"Reporte_Consolidado_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True
    )

with exp_col3:
    st.info("💡 Los datos se actualizan automáticamente cada 5 minutos o al presionar el botón.")

st.markdown("""
<div style="text-align:center;color:#9CA3AF;margin-top:3rem;font-size:0.8rem;">
    Sistema de Gestión Outlet PROESA v2.0 - Trade Marketing Dashboard
</div>
""", unsafe_allow_html=True)