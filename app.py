# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import os
import base64
import re
from datetime import datetime

# Intentamos importar la configuración y conectores de la nube
try:
    from config import INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME
    from src.sheets import obtener_inventario_sheets, get_gsheet_connection
    USING_SHEETS = True
except ImportError:
    USING_SHEETS = False

try:
    from src.database import cargar_inventario, guardar_inventario_maestro
    from src.nav import render_nav
except ImportError as e:
    st.error(f"❌ Error crítico de configuración: {e}")
    st.stop()

st.set_page_config(
    page_title="Outlet PROESA",
    layout="wide",
    page_icon="📦",
    initial_sidebar_state="expanded"
)

PATH_INV_SISTEMA = "data/inventario_maestro.xlsx"
CACHE_TTL_SEGUNDOS = 300  # Los datos dinámicos de la nube se refrescan cada 5 minutos

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 0rem !important;
    margin-top: -20px;
}
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background: #F5F4F0; }
.hero-header {
    background: linear-gradient(135deg, #1A1A2E 0%, #16213E 60%, #0F3460 100%);
    border-radius: 16px; padding: 2rem 2.5rem; margin-bottom: 1.5rem;
    display: flex; align-items: center; gap: 1.5rem;
    box-shadow: 0 8px 32px rgba(26,26,46,0.18);
}
.hero-header h1 { color: #FFFFFF; font-size: 2rem; font-weight: 600; margin: 0; letter-spacing: -0.5px; }
.hero-header p  { color: #A8B2C8; margin: 0.25rem 0 0; font-size: 0.95rem; }
.hero-badge {
    background: #E63946; color: white;
    font-family: 'DM Mono', monospace; font-size: 0.7rem;
    padding: 3px 10px; border-radius: 20px; letter-spacing: 1px;
    margin-top: 0.5rem; display: inline-block;
}
.metric-card {
    background: #FFFFFF; border-radius: 12px; padding: 1.25rem 1.5rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06); border-left: 4px solid #1A1A2E; height: 100%;
}
.metric-card.accent { border-left-color: #E63946; }
.metric-card.green  { border-left-color: #2DC653; }
.metric-card.amber  { border-left-color: #F4A261; }
.metric-label { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; color: #888; margin-bottom: 0.4rem; }
.metric-value { font-size: 2rem; font-weight: 600; color: #1A1A2E; font-family: 'DM Mono', monospace; line-height: 1; }
.metric-sub   { font-size: 0.8rem; color: #AAA; margin-top: 0.3rem; }
[data-testid="stDataFrame"] { border-radius: 12px !important; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
.info-banner  { background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 10px; padding: 0.85rem 1.2rem; color: #1D4ED8; font-size: 0.88rem; margin-top: 1rem; }
.section-title { font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; color: #888; margin: 1.5rem 0 0.75rem; padding-bottom: 0.4rem; border-bottom: 2px solid #EBEBEB; }

/* ── Ocultar chrome de Streamlit ── */
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


@st.cache_data(show_spinner=False)
def get_logo_b64(path="assets/logo_proesa.png"):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return None

logo_b64 = get_logo_b64()
logo_html = (
    f'<img src="data:image/png;base64,{logo_b64}" style="height:150px;object-fit:contain;">'
    if logo_b64 else '<div style="font-size:2.2rem">📦</div>'
)
st.markdown(f"""
<div class="hero-header">
    {logo_html}
    <div>
        <h1>Outlet PROESA</h1>
        <p>Panel de Control e Inventario</p>
        <span class="hero-badge">SISTEMA EN VIVO</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ── PROCESADOR FILA POR FILA CON REPARACIÓN DE CRUCE DE COLUMNAS ──────
def sanitizar_matriz_inventario(df, s_col_idx=3, p_col_idx=4):
    nuevos_stocks = []
    nuevos_precios = []
    
    stock_col_name = df.columns[s_col_idx]
    precio_col_name = df.columns[p_col_idx]
    
    for idx, row in df.iterrows():
        val_stock = row[stock_col_name]
        val_precio = row[precio_col_name]
        
        es_fecha_precio = hasattr(val_precio, 'strftime') or re.match(r'^\d{4}-\d{2}-\d{2}', str(val_precio).strip())
        
        try:
            stock_str = str(val_stock).replace(',', '').strip()
            stock_float = float(stock_str)
        except Exception:
            stock_float = 0.0

        if es_fecha_precio and (0.0 < stock_float < 10.0):
            precio_final = stock_float
            if hasattr(val_precio, 'strftime'):
                stock_final = int(val_precio.day if val_precio.day > 5 else val_precio.month)
            else:
                partes = str(val_precio).strip().split('-')
                d = int(partes[2])
                m = int(partes[1])
                stock_final = int(d if d > 5 else m)
        else:
            if es_fecha_precio:
                if hasattr(val_precio, 'strftime'):
                    precio_final = float(f"{val_precio.month}.{val_precio.day:02d}")
                else:
                    partes = str(val_precio).strip().split('-')
                    precio_final = float(f"{int(partes[1])}.{int(partes[2]):02d}")
            else:
                try:
                    p_str = str(val_precio).upper().replace("BS", "").replace(',', '').strip()
                    precio_final = float(p_str)
                except Exception:
                    precio_final = 0.0
            
            try:
                s_str = str(val_stock).strip()
                if '.' in s_str and len(s_str.split('.')[1]) == 3:
                    s_str = s_str.replace('.', '')
                elif ',' in s_str and len(s_str.split(',')[1]) == 3:
                    s_str = s_str.replace(',', '')
                stock_final = int(float(s_str))
            except Exception:
                stock_final = 0

        if precio_final >= 1000.0:
            precio_final = precio_final / 100.0

        nuevos_stocks.append(stock_final)
        nuevos_precios.append(precio_final)
        
    df[stock_col_name] = nuevos_stocks
    df[precio_col_name] = nuevos_precios
    return df


# ── FUNCIÓN INTERNA OPTIMIZADA POR LOTES PARA LA NUBE ──
def escribir_inventario_sheets(url_sheet: str, hoja: str, df_nuevo: pd.DataFrame) -> bool:
    """Borra la hoja actual en Google Sheets y sube la nueva matriz en un lote rápido JSON."""
    try:
        gc = get_gsheet_connection()
        if gc is None:
            return False
        
        spreadsheet = gc.open_by_url(url_sheet)
        worksheet = spreadsheet.worksheet(hoja)
        
        df_copia = df_nuevo.copy()
        
        # Tipar estrictamente las columnas para remover objetos complejos de Pandas
        df_copia.iloc[:, 1] = df_copia.iloc[:, 1].astype(str).str.strip()
        df_copia.iloc[:, 3] = df_copia.iloc[:, 3].astype(int)
        df_copia.iloc[:, 4] = df_copia.iloc[:, 4].astype(float)
        
        cabeceras = df_copia.columns.tolist()
        
        # Formatear la matriz a tipos nativos de Python estándar
        filas = []
        for v in df_copia.fillna("").values.tolist():
            filas.append([str(x) if isinstance(x, (str, bool)) else x for x in v])
            
        matriz_completa = [cabeceras] + filas
        
        # 1. Limpiar hoja
        worksheet.clear()
        
        # 2. Inyección veloz por bloques mediante API v4 de Google Sheets
        num_filas = len(matriz_completa)
        num_columnas = len(cabeceras)
        letra_columna = chr(64 + num_columnas)
        rango_destino = f"A1:{letra_columna}{num_filas}"
        
        spreadsheet.values_update(
            f"{hoja}!{rango_destino}",
            params={'valueInputOption': 'USER_ENTERED'},
            body={'values': matriz_completa}
        )
        return True
    except Exception as e:
        st.error(f"Error crítico escribiendo en Google Sheets: {e}")
        return False


# ── CONTROLADOR DE PERSISTENCIA Y CACHÉ OPERATIVA ──
def _inventario_expirado() -> bool:
    ts = st.session_state.get('inv_cloud_timestamp')
    if ts is None:
        return True
    return (datetime.now() - ts).total_seconds() > CACHE_TTL_SEGUNDOS

def cargar_inventario_visto():
    if USING_SHEETS:
        try:
            df_cloud = obtener_inventario_sheets(INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME)
            if not df_cloud.empty:
                st.session_state.df_inventario_maestro = df_cloud
                st.session_state['inv_cloud_timestamp'] = datetime.now()
                return
        except Exception:
            pass
            
    if os.path.exists(PATH_INV_SISTEMA):
        st.session_state.df_inventario_maestro = pd.read_excel(PATH_INV_SISTEMA)
        st.session_state['inv_cloud_timestamp'] = datetime.now()
    else:
        st.session_state.df_inventario_maestro = None

if 'df_inventario_maestro' not in st.session_state or _inventario_expirado():
    cargar_inventario_visto()

df_inv = st.session_state.df_inventario_maestro

render_nav(active_page='inicio', inventario_df=df_inv)


# ── CONTROL DE CARGA COMPLETA (LOCAL + REPLICA A LA NUBE OPTIMIZADA) ──
st.markdown('<div class="section-title">Actualizar / Cargar Catálogo Maestro</div>', unsafe_allow_html=True)
archivo = st.file_uploader("Sube el Excel de inventario del mes (Hoja1) para reescribir la base local y Google Sheets:", type=["xlsx"], label_visibility="collapsed")

if archivo:
    # Contenedor dinámico exclusivo para que los spinners no dejen rastros colgados
    status_container = st.empty()
    
    with status_container.container():
        with st.spinner("Procesando y reparando matriz de datos Excel... ⚙️"):
            df_temp = cargar_inventario(archivo)
            df_sanitizado = sanitizar_matriz_inventario(df_temp.copy(), s_col_idx=3, p_col_idx=4)
            guardar_inventario_maestro(df_sanitizado)
            
            # Forzamos la carga directa en memoria RAM para el ciclo entrante
            st.session_state.df_inventario_maestro = df_sanitizado
            st.session_state['inv_cloud_timestamp'] = datetime.now()

    if USING_SHEETS:
        with status_container.container():
            with st.spinner("🚀 Sincronizando nuevo catálogo con Google Sheets en la nube..."):
                exito_nube = escribir_inventario_sheets(INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME, df_sanitizado)
                if exito_nube:
                    st.toast("¡Nube Sincronizada correctamente!", icon="✅")
                else:
                    st.warning("⚠️ Guardado localmente, pero falló la escritura directa en Google Sheets.")
                
    # Purgamos cachés antiguos de consultas
    st.cache_data.clear()
    
    # Destruimos visualmente el spinner del navegador
    status_container.empty()
    st.success("💥 ¡Catálogo maestro actualizado con éxito!")
    
    # Recarga total limpia de controles
    st.rerun()

if df_inv is None:
    st.warning("⚠️ No se ha detectado el Inventario Maestro. Por favor sube un archivo Excel para iniciar.")
    st.stop()


# Identificación de columnas operativas
stock_col   = df_inv.columns[3]
precio_col  = df_inv.columns[4]
empresa_col = df_inv.columns[5]

# Sanitización preventiva en caliente sobre los datos cargados en memoria
df_inv = sanitizar_matriz_inventario(df_inv, s_col_idx=3, p_col_idx=4)


# Cálculo dinámico de métricas consolidadas
total_prods = len(df_inv)
total_stock = int(pd.to_numeric(df_inv[stock_col], errors='coerce').fillna(0).sum())
valor_total = (pd.to_numeric(df_inv[stock_col], errors='coerce').fillna(0) * pd.to_numeric(df_inv[precio_col], errors='coerce').fillna(0.0)).sum()
sin_stock   = int((pd.to_numeric(df_inv[stock_col], errors='coerce').fillna(0) <= 0).sum())
n_empresas  = df_inv[empresa_col].nunique() if empresa_col in df_inv.columns else 1

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
        <div class="metric-value">Bs {valor_total:,.2f}</div>
        <div class="metric-sub">en {n_empresas} empresas</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

st.markdown('<div class="section-title">🔍 Catálogo de Productos</div>', unsafe_allow_html=True)

col_filtro, col_busqueda = st.columns([1, 2])
with col_filtro:
    opciones_emp = ["Todas"]
    if empresa_col in df_inv.columns:
        opciones_emp += sorted(df_inv[empresa_col].dropna().unique().tolist())
    filtro = st.selectbox("Empresa", opciones_emp, label_visibility="collapsed")
with col_busqueda:
    busqueda = st.text_input("Buscar producto...", placeholder="Escribe para filtrar por nombre o código...", label_visibility="collapsed")

df_mostrar = df_inv.copy()
if filtro != "Todas" and empresa_col in df_mostrar.columns:
    df_mostrar = df_mostrar[df_mostrar[empresa_col] == filtro]
if busqueda:
    nombre_col = df_inv.columns[2]
    cod_col = df_inv.columns[1]
    mascara = df_mostrar[nombre_col].astype(str).str.contains(busqueda, case=False, na=False)
    mascara |= df_mostrar[cod_col].astype(str).str.contains(busqueda, case=False, na=False)
    df_mostrar = df_mostrar[mascara]

def resaltar_stock(row):
    try:
        stock = float(row.iloc[3])
    except Exception:
        stock = 0
    if stock <= 0:
        return ['background-color: #FEE2E2'] * len(row)
    elif stock <= 5:
        return ['background-color: #FEF9C3'] * len(row)
    return [''] * len(row)

try:
    styled = df_mostrar.style.apply(resaltar_stock, axis=1).format({
        stock_col:  "{:,.0f}",
        precio_col: "Bs {:,.2f}"
    })
    st.dataframe(styled, use_container_width=True, height=420)
except Exception:
    st.dataframe(df_mostrar, use_container_width=True, height=420)

ts_label = st.session_state.get('inv_cloud_timestamp')
ts_str = ts_label.strftime("%H:%M:%S") if ts_label else "Ahora"

st.markdown(f"""
<div class="info-banner">
    📊 Mostrando <strong>{len(df_mostrar)}</strong> de <strong>{total_prods}</strong> productos (Sincronizado con la nube: {ts_str}).
    Las filas en <span style="background:#FEE2E2;padding:1px 5px;border-radius:3px">rojo</span> indican stock agotado,
    en <span style="background:#FEF9C3;padding:1px 5px;border-radius:3px">amarillo</span> stock bajo (≤5 unidades).
    👉 Ve a <strong>Registro</strong> en el menú lateral para ingresar pedidos.
</div>
""", unsafe_allow_html=True)