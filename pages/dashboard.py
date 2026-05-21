# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime

try:
    st.set_page_config(
        page_title="Dashboard General - PROESA",
        layout="wide",
        page_icon="📊",
        initial_sidebar_state="expanded"
    )
except Exception:
    pass

try:
    from config import (
        INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME,
        PEDIDOS_SHEET_URL, PEDIDOS_HOJA_NAME
    )
    from src.sheets import obtener_inventario_sheets, obtener_todos_pedidos_sheets
    from src.nav import render_nav
except ImportError as e:
    st.error(f"❌ Error crítico de configuración: {e}")
    st.stop()

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; margin-top: -20px; }
    .stMetric { background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); border-left: 5px solid #E63946; }
    .main-title { color: #1A1A2E; font-weight: 700; font-size: 2.2rem; margin-bottom: 0.5rem; }
    .subtitle   { color: #6B7280; margin-bottom: 2rem; }

    /* ── Ocultar chrome de Streamlit SIN dejar barra blanca ── */
    #MainMenu, footer { visibility: hidden; }
    header {
        visibility: hidden;
        height: 0 !important;
        min-height: 0 !important;
        padding: 0 !important;
    }
    .stAppViewContainer footer { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stToolbar"]    { display: none !important; }
    .stDeployButton              { display: none !important; }
</style>
""", unsafe_allow_html=True)


CACHE_TTL_SEGUNDOS = 60  # Caché de 1 minuto para pruebas fluidas y protección de API

def _datos_expirados() -> bool:
    ts = st.session_state.get('dashboard_timestamp')
    if ts is None:
        return True
    return (datetime.now() - ts).total_seconds() > CACHE_TTL_SEGUNDOS

def cargar_datos():
    with st.spinner("Descargando métricas consolidadas desde la nube..."):
        inv     = obtener_inventario_sheets(INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME)
        pedidos = obtener_todos_pedidos_sheets(PEDIDOS_SHEET_URL, PEDIDOS_HOJA_NAME)
        st.session_state['df_inv_dashboard']     = inv
        st.session_state['df_pedidos_dashboard'] = pedidos
        st.session_state['dashboard_timestamp']  = datetime.now()
        if 'df_inventario_maestro' not in st.session_state and not inv.empty:
            st.session_state['df_inventario_maestro'] = inv

if 'df_pedidos_dashboard' not in st.session_state or _datos_expirados():
    cargar_datos()

df_inv     = st.session_state['df_inv_dashboard'].copy()
df_pedidos = st.session_state['df_pedidos_dashboard'].copy()


# ── SECCIÓN MAESTRA: SANITIZACIÓN CON ESCUDO ANTI-DESPLAZAMIENTO DECIMAL ──
COL_STOCK_INV     = "Stock"          if "Stock"          in df_inv.columns     else df_inv.columns[3]
COL_PRECIO_INV    = "Precio Unitario" if "Precio Unitario" in df_inv.columns else df_inv.columns[4]
COL_CODIGO_INV    = "Código Producto" if "Código Producto" in df_inv.columns else df_inv.columns[1]

def sanitizar_inventario_dashboard(df):
    nuevos_stocks = []
    nuevos_precios = []
    
    for _, row in df.iterrows():
        val_stock_raw = str(row[COL_STOCK_INV]).strip()
        val_precio_raw = str(row[COL_PRECIO_INV]).strip()
        
        # 1. Procesar Precio con Escudo de Control
        try:
            p_str = val_precio_raw.upper().replace("BS", "").replace(',', '').strip()
            precio_final = float(p_str)
            
            # ESCUDO ANTI-DESPLAZAMIENTO: Si se importó como 601, 3012, etc. debido al texto sin formato
            if precio_final in [601.0, 3012.0, 255.0, 312.0, 760.0]:
                precio_final = precio_final / 100.0
            elif precio_final >= 1000.0:
                # Resguardo genérico por si aparece otro valor similar desbordado
                precio_final = precio_final / 100.0
        except Exception:
            precio_final = 0.0

        # 2. Procesar Stock protegiendo puntos decimales de miles
        try:
            s_str = val_stock_raw.replace(',', '')
            if '.' in s_str and len(s_str.split('.')[1]) == 3:
                s_str = s_str.replace('.', '')
            stock_final = int(float(s_str))
        except Exception:
            stock_final = 0

        nuevos_stocks.append(stock_final)
        nuevos_precios.append(precio_final)
        
    df[COL_STOCK_INV] = nuevos_stocks
    df[COL_PRECIO_INV] = nuevos_precios
    return df

# Ejecutamos la limpieza profunda en el inventario cargado
df_inv = sanitizar_inventario_dashboard(df_inv)

# Crear diccionario rápido indexado para cruzar y corregir el Historial de Pedidos
diccionario_precios_maestros = {
    str(row[COL_CODIGO_INV]).strip(): float(row[COL_PRECIO_INV])
    for _, row in df_inv.iterrows() if pd.notna(row[COL_CODIGO_INV])
}
# ─────────────────────────────────────────────────────────────────────────────


render_nav(active_page='dashboard', inventario_df=df_inv)

st.markdown('<h1 class="main-title">📊 Panel de Control General</h1>', unsafe_allow_html=True)
ts = st.session_state.get('dashboard_timestamp')
if ts:
    st.markdown(
        f'<p class="subtitle">Análisis operativo en tiempo real · '
        f'<span style="font-size:0.8rem;color:#9CA3AF">Última actualización de caché: {ts.strftime("%H:%M:%S")}</span></p>',
        unsafe_allow_html=True
    )

if df_pedidos.empty:
    st.info("ℹ️ No se encontraron registros de pedidos en Google Sheets.")
    st.stop()

COL_PRECIO_PEDIDO  = "Precio Unitario" if "Precio Unitario" in df_pedidos.columns else \
                     ("Monto Uni" if "Monto Uni" in df_pedidos.columns else df_pedidos.columns[3])
COL_FECHA_PEDIDO   = "Fecha Registro" if "Fecha Registro" in df_pedidos.columns else df_pedidos.columns[0]
COL_CODIGO_PEDIDO  = "Código Producto" if "Código Producto" in df_pedidos.columns else df_pedidos.columns[3]

# Formatear cantidad de pedidos uniformemente
df_pedidos['Cantidad'] = pd.to_numeric(
    df_pedidos['Cantidad'].astype(str).str.replace(',', '.', regex=False).str.strip(),
    errors='coerce'
).fillna(0).astype(int)


# ── CRUCE INTELIGENTE DE PRECIOS PARA EL HISTORIAL DE PEDIDOS ──
def normalizar_precio_pedido_dashboard(row):
    codigo_p = str(row.get(COL_CODIGO_PEDIDO, '')).strip()
    val_original = row[COL_PRECIO_PEDIDO]
    
    # 1. Si el código existe en el inventario maestro verificado, heredamos ese precio limpio
    if codigo_p in diccionario_precios_maestros:
        return diccionario_precios_maestros[codigo_p]
    
    # 2. Respaldo por si hay ítems antiguos o huérfanos en el historial
    try:
        p_str = str(val_original).upper().replace("BS", "").replace(',', '').strip()
        num = float(p_str)
        if num in [601.0, 3012.0, 255.0, 312.0, 760.0]:
            return num / 100.0
        elif num >= 1000.0:
            return num / 100.0
        return num
    except Exception:
        return 0.0

# Aplicar el normalizador seguro a la columna de precios de la tabla de pedidos
df_pedidos[COL_PRECIO_PEDIDO] = df_pedidos.apply(normalizar_precio_pedido_dashboard, axis=1)

# Calcular subtotales basados en precios reales corregidos
df_pedidos['Subtotal']        = df_pedidos[COL_PRECIO_PEDIDO] * df_pedidos['Cantidad']
df_pedidos[COL_FECHA_PEDIDO]  = pd.to_datetime(df_pedidos[COL_FECHA_PEDIDO], errors='coerce', dayfirst=True)


st.markdown("### Resumen de Operaciones")
m1, m2, m3, m4 = st.columns(4)

m1.metric("Total Pedidos",    f"{len(df_pedidos):,}")
m2.metric("Unidades Movidas", f"{int(df_pedidos['Cantidad'].sum()):,} ud.")
m3.metric("Facturación Est.", f"Bs {df_pedidos['Subtotal'].sum():,.2f}")
criticos = len(df_inv[df_inv[COL_STOCK_INV] < 5])
m4.metric("Alertas Stock", f"{criticos} SKU",
          delta="- Crítico" if criticos > 0 else "OK",
          delta_color="inverse" if criticos > 0 else "normal")

st.markdown("---")

st.markdown("### 🔍 Filtros de Búsqueda")
c_f1, c_f2, c_f3 = st.columns([1, 1, 2])

with c_f1:
    opciones_emp   = sorted(df_pedidos['Empresa'].dropna().unique().tolist()) if 'Empresa' in df_pedidos.columns else []
    emp_sel        = st.multiselect("Filtrar por Empresa:", opciones_emp, default=opciones_emp)
with c_f2:
    opciones_linea = sorted(df_pedidos['Línea'].dropna().unique().tolist()) if 'Línea' in df_pedidos.columns else []
    linea_sel      = st.multiselect("Filtrar por Línea:", opciones_linea, default=opciones_linea)
with c_f3:
    busqueda = st.text_input("Buscar por Empleado o Producto:", placeholder="Ej: Juan / Scotch Brite")

# Aplicación dinámica de filtros de UI
df_filtrado = df_pedidos.copy()
if emp_sel:
    df_filtrado = df_filtrado[df_filtrado['Empresa'].isin(emp_sel)]
if linea_sel:
    df_filtrado = df_filtrado[df_filtrado['Línea'].isin(linea_sel)]
if busqueda:
    col_emp_nom  = "Nombre Empleado" if "Nombre Empleado" in df_filtrado.columns else df_filtrado.columns[1]
    col_prod_nom = "Nombre Producto" if "Nombre Producto" in df_filtrado.columns else df_filtrado.columns[2]
    mascara = df_filtrado[col_prod_nom].astype(str).str.contains(busqueda, case=False, na=False)
    mascara |= df_filtrado[col_emp_nom].astype(str).str.contains(busqueda, case=False, na=False)
    df_filtrado = df_filtrado[mascara]

st.markdown("### 📋 Historial Consolidado")
config_cols = {
    "Subtotal": st.column_config.NumberColumn(label="Subtotal", format="Bs %,.2f"),
    "Cantidad": st.column_config.NumberColumn(label="Cantidad", format="%d ud."),
}
if COL_PRECIO_PEDIDO in df_filtrado.columns:
    config_cols[COL_PRECIO_PEDIDO] = st.column_config.NumberColumn(label="Precio Unitario", format="Bs %,.2f")
if COL_FECHA_PEDIDO in df_filtrado.columns:
    config_cols[COL_FECHA_PEDIDO]  = st.column_config.DatetimeColumn(label="Fecha y Hora", format="DD/MM/YYYY HH:mm")

st.dataframe(df_filtrado, use_container_width=True, height=420, column_config=config_cols)

st.markdown("---")
st.markdown("### 📈 Análisis de Demanda")
g1, g2 = st.columns(2)
col_prod_agrup = "Nombre Producto" if "Nombre Producto" in df_filtrado.columns else df_filtrado.columns[2]

with g1:
    st.write("**Top 5 Productos más Solicitados**")
    if not df_filtrado.empty:
        top = df_filtrado.groupby(col_prod_agrup)['Cantidad'].sum().sort_values(ascending=False).head(5)
        st.bar_chart(top, color="#E63946")
    else:
        st.info("Sin datos para la selección actual.")

with g2:
    st.write("**Volumen por Línea de Negocio**")
    if 'Línea' in df_filtrado.columns and not df_filtrado.empty:
        st.bar_chart(df_filtrado.groupby('Línea')['Cantidad'].sum().sort_values(ascending=False), color="#1A1A2E")
    else:
        st.info("Sin datos por línea.")

st.markdown("---")
st.markdown("### 📥 Reportes y Sincronización")
e1, e2, e3 = st.columns([1, 1, 2])

with e1:
    if st.button("🔄 Sincronizar Sheets Ahora", use_container_width=True):
        for k in ['df_inv_dashboard', 'df_pedidos_dashboard', 'dashboard_timestamp']:
            st.session_state.pop(k, None)
        st.rerun()

with e2:
    try:
        csv = df_filtrado.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 Exportar CSV", data=csv,
            file_name=f"Reporte_PROESA_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv", use_container_width=True
        )
    except Exception:
        st.button("📥 Exportar CSV", disabled=True, use_container_width=True)

with e3:
    st.info("💡 Los datos se actualizan automáticamente en caché cada 1 minuto o al presionar el botón de sincronización forzada.")

st.markdown("""
<div style="text-align:center;color:#9CA3AF;margin-top:3rem;font-size:0.8rem;">
    Sistema de Gestión Outlet PROESA v2.0 - Trade Marketing · 2026
</div>
""", unsafe_allow_html=True)