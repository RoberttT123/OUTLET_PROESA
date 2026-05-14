import streamlit as st
import pandas as pd
import os
import base64
from datetime import datetime

# ── CONFIGURACIÓN DE PÁGINA ──────────────────────────────────────────────────
st.set_page_config(page_title="Dashboard General - PROESA", layout="wide", page_icon="📊")

# ── IMPORTACIONES DE CONFIGURACIÓN Y NAVEGACIÓN ──────────────────────────────
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

# ── ESTILOS PERSONALIZADOS (UI/UX) ───────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .stMetric {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        border-left: 5px solid #E63946;
    }
    .main-title {
        color: #1A1A2E;
        font-weight: 700;
        font-size: 2.2rem;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        color: #6B7280;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# ── CARGA DE DATOS DESDE GOOGLE SHEETS ───────────────────────────────────────
@st.cache_data(ttl=60) # El dashboard se actualiza cada 1 minuto
def cargar_datos_dashboard():
    inv = obtener_inventario_sheets(INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME)
    pedidos = obtener_todos_pedidos_sheets(PEDIDOS_SHEET_URL, PEDIDOS_HOJA_NAME)
    return inv, pedidos

df_inv, df_pedidos = cargar_datos_dashboard()

# Renderizar navegación
render_nav(active_page='dashboard', inventario_df=df_inv)

# ── ENCABEZADO ───────────────────────────────────────────────────────────────
st.markdown('<h1 class="main-title">📊 Panel de Control General</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Análisis en tiempo real de inventarios y pedidos consolidados en la nube.</p>', unsafe_allow_html=True)

if df_pedidos.empty:
    st.info("ℹ️ No se encontraron pedidos registrados en Google Sheets.")
    st.stop()

# ── MÉTRICAS CLAVE (KPIs) ─────────────────────────────────────────────────────
st.markdown("### Resumen de Operaciones")
m1, m2, m3, m4 = st.columns(4)

with m1:
    total_p = len(df_pedidos)
    st.metric("Total Pedidos", f"{total_p:,}")

with m2:
    # Asegurar que cantidad sea numérica
    df_pedidos['Cantidad'] = pd.to_numeric(df_pedidos['Cantidad'], errors='coerce').fillna(0)
    total_u = int(df_pedidos['Cantidad'].sum())
    st.metric("Unidades Movidas", f"{total_u:,} ud.")

with m3:
    # Cálculo de monto total (Precio * Cantidad)
    df_pedidos['Monto Uni'] = pd.to_numeric(df_pedidos['Monto Uni'], errors='coerce').fillna(0)
    df_pedidos['Subtotal'] = df_pedidos['Monto Uni'] * df_pedidos['Cantidad']
    total_bs = df_pedidos['Subtotal'].sum()
    st.metric("Facturación Est.", f"Bs {total_bs:,.2f}")

with m4:
    # Stock Crítico (productos con menos de 5 unidades)
    df_inv['Stock'] = pd.to_numeric(df_inv['Stock'], errors='coerce').fillna(0)
    criticos = len(df_inv[df_inv['Stock'] < 5])
    st.metric("Alertas Stock", f"{criticos} SKU", delta="- Crítico" if criticos > 0 else "OK")

st.markdown("---")

# ── SECCIÓN DE FILTROS AVANZADOS ─────────────────────────────────────────────
st.markdown("### 🔍 Filtros de Búsqueda")
c_f1, c_f2, c_f3 = st.columns([1, 1, 2])

with c_f1:
    # Filtro por Línea/Empresa si existen en el DF
    opciones_emp = df_pedidos['Empresa'].unique().tolist() if 'Empresa' in df_pedidos.columns else []
    emp_sel = st.multiselect("Filtrar por Empresa:", opciones_emp, default=opciones_emp)

with c_f2:
    # Filtro por Línea
    opciones_linea = df_pedidos['Línea'].unique().tolist() if 'Línea' in df_pedidos.columns else []
    linea_sel = st.multiselect("Filtrar por Línea:", opciones_linea, default=opciones_linea)

with c_f3:
    busqueda = st.text_input("Buscar por Nombre de Empleado o Producto:", placeholder="Ej: Juan Perez / Coca Cola")

# Aplicar Lógica de Filtros
df_filtrado = df_pedidos.copy()

if emp_sel:
    df_filtrado = df_filtrado[df_filtrado['Empresa'].isin(emp_sel)]
if linea_sel:
    df_filtrado = df_filtrado[df_filtrado['Línea'].isin(linea_sel)]
if busqueda:
    df_filtrado = df_filtrado[
        (df_filtrado['Nombre Empleado'].str.contains(busqueda, case=False, na=False)) |
        (df_filtrado['Nombre Producto'].str.contains(busqueda, case=False, na=False))
    ]

# ── TABLA DE DATOS CONSOLIDADA ────────────────────────────────────────────────
st.markdown("### 📋 Historial Consolidado (Google Sheets)")
st.dataframe(
    df_filtrado, 
    use_container_width=True, 
    height=450,
    column_config={
        "Subtotal": st.column_config.NumberColumn(format="Bs %.2f"),
        "Monto Uni": st.column_config.NumberColumn(format="Bs %.2f"),
        "Fecha Registro": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm")
    }
)

# ── ANÁLISIS GRÁFICO RÁPIDO ──────────────────────────────────────────────────
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
        linea_dist = df_pedidos.groupby('Línea').size()
        st.bar_chart(linea_dist)

# ── EXPORTACIÓN DE DATOS ─────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📥 Reportes")
exp_col1, exp_col2, exp_col3 = st.columns([1, 1, 2])

with exp_col1:
    # Botón para refrescar datos manualmente
    if st.button("🔄 Actualizar Datos Ahora", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

with exp_col2:
    # Descarga CSV
    csv = df_filtrado.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📥 Descargar CSV",
        data=csv,
        file_name=f"Reporte_Consolidado_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True
    )

with exp_col3:
    st.info("💡 Los datos mostrados corresponden a la hoja de cálculo en tiempo real de Google Sheets.")

# Pie de página
st.markdown("""
<div style="text-align: center; color: #9CA3AF; margin-top: 3rem; font-size: 0.8rem;">
    Sistema de Gestión Outlet PROESA v2.0 - Trade Marketing Dashboard
</div>
""", unsafe_allow_html=True)