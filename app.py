import streamlit as st
import pandas as pd
import os
import base64
from src.database import cargar_inventario, guardar_inventario_maestro
from src.nav import render_nav

def get_logo_b64(path="assets/logo_proesa.png"):
    """Devuelve el logo como string base64 para usarlo en HTML."""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return None

st.set_page_config(page_title="Outlet PROESA", layout="wide", page_icon="📦")

PATH_INV_SISTEMA = "data/inventario_maestro.xlsx"

# ── ESTILOS GLOBALES ────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

/* Fondo principal */
.stApp {
    background: #F5F4F0;
}

/* Sidebar — estilos gestionados por src/nav.py */

/* Encabezado hero */
.hero-header {
    background: linear-gradient(135deg, #1A1A2E 0%, #16213E 60%, #0F3460 100%);
    border-radius: 16px;
    padding: 2rem 2.5rem;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    gap: 1.5rem;
    box-shadow: 0 8px 32px rgba(26,26,46,0.18);
}
.hero-header h1 {
    color: #FFFFFF;
    font-size: 2rem;
    font-weight: 600;
    margin: 0;
    letter-spacing: -0.5px;
}
.hero-header p {
    color: #A8B2C8;
    margin: 0.25rem 0 0;
    font-size: 0.95rem;
}
.hero-badge {
    background: #E63946;
    color: white;
    font-family: 'DM Mono', monospace;
    font-size: 0.7rem;
    padding: 3px 10px;
    border-radius: 20px;
    letter-spacing: 1px;
    margin-top: 0.5rem;
    display: inline-block;
}

/* Tarjetas de métricas */
.metric-card {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    border-left: 4px solid #1A1A2E;
    height: 100%;
}
.metric-card.accent { border-left-color: #E63946; }
.metric-card.green  { border-left-color: #2DC653; }
.metric-card.amber  { border-left-color: #F4A261; }

.metric-label {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #888;
    margin-bottom: 0.4rem;
}
.metric-value {
    font-size: 2rem;
    font-weight: 600;
    color: #1A1A2E;
    font-family: 'DM Mono', monospace;
    line-height: 1;
}
.metric-sub {
    font-size: 0.8rem;
    color: #AAA;
    margin-top: 0.3rem;
}

/* Sección de filtros */
.filter-bar {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 1rem 1.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* Tabla */
[data-testid="stDataFrame"] {
    border-radius: 12px !important;
    overflow: hidden;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}

/* Selectbox y widgets */
.stSelectbox > div > div {
    border-radius: 8px !important;
    border-color: #DDD !important;
    background: #FAFAFA !important;
}

/* Alerta personalizada */
.info-banner {
    background: #EFF6FF;
    border: 1px solid #BFDBFE;
    border-radius: 10px;
    padding: 0.85rem 1.2rem;
    color: #1D4ED8;
    font-size: 0.88rem;
    margin-top: 1rem;
}

/* Chip de empresa */
.empresa-chip {
    display: inline-block;
    background: #F0F0F5;
    color: #444;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 0.75rem;
    font-weight: 500;
    margin: 1px;
}

/* Uploader */
[data-testid="stFileUploadDropzone"] {
    background: #FAFAFA !important;
    border: 2px dashed #C8C8D0 !important;
    border-radius: 12px !important;
}

/* Título de sección */
.section-title {
    font-size: 0.85rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #888;
    margin: 1.5rem 0 0.75rem;
    padding-bottom: 0.4rem;
    border-bottom: 2px solid #EBEBEB;
}

/* Ocultar header por defecto de streamlit */
#MainMenu, header, footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── HEADER HERO ─────────────────────────────────────────────────────────────
logo_b64 = get_logo_b64()
logo_html = (
    f'<img src="data:image/png;base64,{logo_b64}" style="height:128px;object-fit:contain;">'
    if logo_b64
    else '<div style="font-size:2.2rem">📦</div>'
)
st.markdown(f"""
<div class="hero-header">
    {logo_html}
    <div>
        <h1>Outlet PROESA</h1>
        <p>Panel de Control e Inventario</p>
        <span class="hero-badge">SISTEMA ACTIVO</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ── LÓGICA DE CARGA ──────────────────────────────────────────────────────────
if os.path.exists(PATH_INV_SISTEMA):
    df_inv = pd.read_excel(PATH_INV_SISTEMA)
else:
    df_inv = None

render_nav(active_page='inicio', inventario_df=df_inv)

if df_inv is None:
    st.warning("⚠️ No se ha detectado el Inventario Maestro.")
    st.markdown('<div class="section-title">Cargar Excel del mes</div>', unsafe_allow_html=True)
    archivo = st.file_uploader("Sube el Excel del mes (Hoja1)", type=["xlsx"], label_visibility="collapsed")
    if archivo:
        df_temp = cargar_inventario(archivo)
        guardar_inventario_maestro(df_temp)
        st.success("✅ Inventario cargado con éxito.")
        st.rerun()
    st.stop()


# ── MÉTRICAS ─────────────────────────────────────────────────────────────────
stock_col = df_inv.columns[3]
precio_col = df_inv.columns[4]
empresa_col = df_inv.columns[5]

total_prods   = len(df_inv)
total_stock   = int(df_inv[stock_col].sum())
valor_total   = df_inv[stock_col].mul(df_inv[precio_col]).sum()
sin_stock     = int((df_inv[stock_col] <= 0).sum())
n_empresas    = df_inv[empresa_col].nunique()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Productos</div>
        <div class="metric-value">{total_prods}</div>
        <div class="metric-sub">ítems en catálogo</div>
    </div>""", unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card green">
        <div class="metric-label">Stock Total</div>
        <div class="metric-value">{total_stock:,}</div>
        <div class="metric-sub">unidades disponibles</div>
    </div>""", unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card accent">
        <div class="metric-label">Sin Stock</div>
        <div class="metric-value">{sin_stock}</div>
        <div class="metric-sub">productos agotados</div>
    </div>""", unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card amber">
        <div class="metric-label">Valor Inventario</div>
        <div class="metric-value">Bs {valor_total:,.0f}</div>
        <div class="metric-sub">en {n_empresas} empresas</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ── CATÁLOGO ─────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🔍 Catálogo de Productos</div>', unsafe_allow_html=True)

col_filtro, col_busqueda = st.columns([1, 2])
with col_filtro:
    empresas = ["Todas"] + sorted(df_inv[empresa_col].dropna().unique().tolist())
    filtro = st.selectbox("Empresa", empresas, label_visibility="collapsed")
with col_busqueda:
    busqueda = st.text_input("Buscar producto...", placeholder="Escribe para filtrar por nombre...", label_visibility="collapsed")

df_mostrar = df_inv.copy()
if filtro != "Todas":
    df_mostrar = df_mostrar[df_mostrar[empresa_col] == filtro]
if busqueda:
    nombre_col = df_inv.columns[2]
    df_mostrar = df_mostrar[df_mostrar[nombre_col].str.contains(busqueda, case=False, na=False)]

# Resaltar filas con stock bajo
def resaltar_stock(row):
    stock = row.iloc[3]
    if stock <= 0:
        return ['background-color: #FEE2E2'] * len(row)
    elif stock <= 5:
        return ['background-color: #FEF9C3'] * len(row)
    return [''] * len(row)

try:
    styled = df_mostrar.style.apply(resaltar_stock, axis=1).format({
        stock_col: "{:,.0f}",
        precio_col: "Bs {:,.2f}"
    })
    st.dataframe(styled, use_container_width=True, height=420)
except Exception:
    st.dataframe(df_mostrar, use_container_width=True, height=420)

st.markdown(f"""
<div class="info-banner">
    📊 Mostrando <strong>{len(df_mostrar)}</strong> de <strong>{total_prods}</strong> productos.
    Las filas en <span style="background:#FEE2E2;padding:1px 5px;border-radius:3px">rojo</span> indican stock agotado,
    en <span style="background:#FEF9C3;padding:1px 5px;border-radius:3px">amarillo</span> stock bajo (≤5 unidades).
    👉 Ve a <strong>Registro</strong> en el menú lateral para ingresar pedidos.
</div>
""", unsafe_allow_html=True)