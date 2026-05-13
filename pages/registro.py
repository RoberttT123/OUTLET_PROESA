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

# Importar funciones de BD según la configuración
if USING_SHEETS:
    from src.sheets import (
        obtener_inventario_sheets,
        obtener_todos_pedidos_sheets,
        guardar_pedido_sheets
    )
    actualizar_stock_sheets = None  # TODO: implementar
else:
    from src.database import guardar_pedido, actualizar_stock_inventario
    PATH_INV_SISTEMA = "data/inventario_maestro.xlsx"
    PATH_PEDIDOS = "data/consolidado_pedidos.xlsx"

st.set_page_config(page_title="Registro de Pedidos", layout="wide", page_icon="📝")

# ── INICIALIZACIÓN DEL CARRITO ──────────────────────────────────────────────
if 'carrito' not in st.session_state:
    st.session_state.carrito = []

# ── ESTILOS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

.stApp { background: #F5F4F0; }

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

.carrito-item {
    background: #FFFFFF;
    border-radius: 10px;
    padding: 1rem;
    margin-bottom: 0.5rem;
    border-left: 3px solid #E63946;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}

#MainMenu, header, footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── VERIFICACIÓN Y CARGA DE DATOS ───────────────────────────────────────────
if USING_SHEETS:
    @st.cache_data(ttl=300)
    def cargar_inventario():
        return obtener_inventario_sheets(INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME)
    
    df_inv = cargar_inventario()
    if df_inv.empty:
        st.error("❌ No se pudo cargar el inventario de Google Sheets.")
        st.stop()
else:
    if not os.path.exists(PATH_INV_SISTEMA):
        st.error("⚠️ No se ha detectado el Inventario Maestro.")
        st.stop()
    df_inv = pd.read_excel(PATH_INV_SISTEMA)

render_nav(active_page='registro', inventario_df=df_inv)

# ── LOGO ────────────────────────────────────────────────────────────────────
def get_logo_b64(path="assets/logo_proesa.png"):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return None

# ── HEADER ──────────────────────────────────────────────────────────────────
logo_b64 = get_logo_b64()
logo_html = (
    f'<img src="data:image/png;base64,{logo_b64}" style="height:100px;object-fit:contain;">'
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
        st.markdown('<div class="section-title">Datos del Empleado</div>', unsafe_allow_html=True)

        with st.form("registro_operativo"):
            c1, c2 = st.columns(2)
            cod_emp = c1.text_input("Código de Empleado", placeholder="Ej: EMP-001")
            nom_emp = c2.text_input("Nombre Completo", placeholder="Nombre y apellido")

            st.markdown('<div class="section-title">Selección de Producto</div>', unsafe_allow_html=True)

            # Obtener lista de productos según estructura
            if "Nombre Producto" in df_inv.columns:
                lista_prods = df_inv["Nombre Producto"].dropna().tolist()
            elif len(df_inv.columns) > 2:
                lista_prods = df_inv.iloc[:, 2].dropna().tolist()
            else:
                lista_prods = []

            prod_sel = st.selectbox(
                "Producto",
                options=lista_prods,
                index=None,
                placeholder="Escribe para filtrar...",
                label_visibility="collapsed"
            )

            cant = st.number_input("Cantidad a pedir", min_value=1, step=1, value=1)

            # BOTÓN PARA AÑADIR AL CARRITO
            btn_col1, btn_col2 = st.columns([2, 1])
            with btn_col1:
                btn_agregar = st.form_submit_button("➕ Añadir al Carrito", use_container_width=True)

            if btn_agregar:
                if prod_sel and cod_emp and nom_emp:
                    # Buscar fila del producto
                    if "Nombre Producto" in df_inv.columns:
                        fila_p = df_inv[df_inv["Nombre Producto"] == prod_sel].iloc[0]
                    else:
                        fila_p = df_inv[df_inv.iloc[:, 2] == prod_sel].iloc[0]
                    
                    # Obtener stock (flexible para diferentes columnas)
                    stock_col = "Stock" if "Stock" in df_inv.columns else df_inv.columns[3]
                    stock_actual = fila_p[stock_col]
                    
                    # Validar stock considerando lo que ya está en el carrito
                    cant_en_carrito = sum(item['cantidad'] for item in st.session_state.carrito if item['producto'] == prod_sel)
                    
                    if validar_stock(cant + cant_en_carrito, stock_actual):
                        st.session_state.carrito.append({
                            "producto": prod_sel,
                            "cantidad": int(cant),
                            "fila_data": fila_p,
                            "subtotal": float(fila_p.iloc[4]) * int(cant) if len(fila_p) > 4 else 0
                        })
                        st.toast(f"✅ Agregado: {prod_sel}")
                        st.rerun()
                    else:
                        st.error(f"❌ Stock insuficiente. Solo quedan **{int(stock_actual)}** unidades.")
                else:
                    st.warning("⚠️ Completa todos los campos.")

        # --- VISUALIZACIÓN DEL CARRITO ---
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

            # BOTÓN FINALIZAR TODO EL PEDIDO
            if st.button("✅  CONFIRMAR Y ENVIAR TODO EL PEDIDO", type="primary", use_container_width=True):
                if cod_emp and nom_emp:
                    try:
                        if USING_SHEETS:
                            # Preparar items para Google Sheets
                            items_para_sheets = []
                            for item in st.session_state.carrito:
                                fila = item['fila_data']
                                codigo_prod = str(fila.get("Código Producto", fila.iloc[1]) if hasattr(fila, 'get') else fila.iloc[1])
                                precio_unit = float(fila.get("Precio Unitario", fila.iloc[4]) if hasattr(fila, 'get') else fila.iloc[4])
                                linea = str(fila.get("Línea", fila.iloc[0]) if hasattr(fila, 'get') else fila.iloc[0])
                                empresa = str(fila.get("Empresa", fila.iloc[5]) if hasattr(fila, 'get') else fila.iloc[5])
                                stock = int(fila.get("Stock", fila.iloc[3]) if hasattr(fila, 'get') else fila.iloc[3])
                                
                                items_para_sheets.append({
                                    "codigo_producto": codigo_prod,
                                    "producto": item['producto'],
                                    "cantidad": item['cantidad'],
                                    "precio_unitario": precio_unit,
                                    "linea": linea,
                                    "descuento": 0,
                                    "stock_actual": stock,
                                    "empresa": empresa
                                })
                            
                            if guardar_pedido_sheets(cod_emp, nom_emp, items_para_sheets, PEDIDOS_SHEET_URL, PEDIDOS_HOJA_NAME):
                                st.session_state.carrito = []
                                st.success(f"✅ Pedido guardado para: {nom_emp}")
                                st.rerun()
                            else:
                                st.error("❌ Error al guardar pedido en Google Sheets")
                        else:
                            # Usar Excel local
                            for item in st.session_state.carrito:
                                nueva_fila = preparar_fila_pedido(cod_emp, nom_emp, item['fila_data'], item['cantidad'])
                                guardar_pedido(nueva_fila)
                                actualizar_stock_inventario(item['fila_data'].iloc[1], item['cantidad'])
                            
                            st.session_state.carrito = []
                            st.success(f"✅ Pedido guardado para: {nom_emp}")
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                else:
                    st.error("⚠️ Faltan datos del empleado (Nombre o Código).")

    # ── Panel lateral informativo ──────────────────────────────────────────
    with col_info:
        st.markdown('<div class="section-title">Vista Previa del Producto</div>', unsafe_allow_html=True)

        if prod_sel:
            if "Nombre Producto" in df_inv.columns:
                fila_preview = df_inv[df_inv["Nombre Producto"] == prod_sel].iloc[0]
            else:
                fila_preview = df_inv[df_inv.iloc[:, 2] == prod_sel].iloc[0]
            
            # Obtener datos con flexibilidad
            stock_col = "Stock" if "Stock" in df_inv.columns else df_inv.columns[3]
            precio_col = "Precio Unitario" if "Precio Unitario" in df_inv.columns else df_inv.columns[4]
            codigo_col = "Código Producto" if "Código Producto" in df_inv.columns else df_inv.columns[1]
            linea_col = "Línea" if "Línea" in df_inv.columns else df_inv.columns[0]
            empresa_col = "Empresa" if "Empresa" in df_inv.columns else df_inv.columns[5]
            
            stock_prev = int(fila_preview[stock_col])
            precio_prev = float(fila_preview[precio_col])
            codigo_prev = fila_preview[codigo_col]
            linea_prev = fila_preview[linea_col]
            empresa_prev = fila_preview[empresa_col]

            if stock_prev <= 0:
                stock_badge = f'<span class="stock-out">⛔ Agotado</span>'
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

            # Total estimado
            if cant and cant > 0:
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
        df_p = obtener_todos_pedidos_sheets(PEDIDOS_SHEET_URL, PEDIDOS_HOJA_NAME)
    else:
        if os.path.exists(PATH_PEDIDOS):
            df_p = pd.read_excel(PATH_PEDIDOS)
        else:
            df_p = pd.DataFrame()

    if not df_p.empty:
        total_pedidos = len(df_p)
        total_unidades = int(df_p["Cantidad"].sum()) if "Cantidad" in df_p.columns else 0
        
        st.markdown(f"""
        <div style="margin:1rem 0 1.25rem">
            <div class="stat-pill">📋 {total_pedidos} <span>pedidos</span></div>
            <div class="stat-pill">📦 {total_unidades:,} <span>unidades</span></div>
        </div>
        """, unsafe_allow_html=True)

        # Herramienta de corrección
        with st.expander("🗑️  Herramienta de Corrección — Eliminar Registro"):
            st.warning("Al eliminar un registro, las unidades se **devolverán automáticamente** al inventario.")

            id_a_borrar = st.selectbox(
                "Registro a anular:",
                options=df_p.index,
                format_func=lambda x: (
                    f"#{x}  |  {df_p.loc[x, 'Nombre Empleado']}  →  "
                    f"{df_p.loc[x, 'Nombre Producto']}  ({df_p.loc[x, 'Cantidad']} un.)"
                )
            )

            if st.button("🗑️ Confirmar eliminación"):
                if not USING_SHEETS:
                    cod_prod_borrar = df_p.loc[id_a_borrar, "Código Producto"]
                    cant_borrar = df_p.loc[id_a_borrar, "Cantidad"]
                    actualizar_stock_inventario(cod_prod_borrar, -cant_borrar)
                    df_p_nuevo = df_p.drop(id_a_borrar)
                    df_p_nuevo.to_excel(PATH_PEDIDOS, index=False)
                    st.success(f"Registro eliminado. Stock restaurado.")
                else:
                    st.info("⚠️ Para eliminar registros de Google Sheets, hazlo manualmente en la hoja.")
                st.rerun()

        # Mostrar tabla de pedidos
        st.dataframe(df_p, use_container_width=True, height=400)

        # Botón de descarga
        try:
            csv = df_p.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"Pedidos_{datetime.now().strftime('%d_%m_%Y')}.csv",
                mime="text/csv"
            )
        except:
            pass

    else:
        st.info("No hay pedidos registrados en el historial.")