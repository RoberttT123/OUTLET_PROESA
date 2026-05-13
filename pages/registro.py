import streamlit as st
import pandas as pd
import os
import base64
from datetime import datetime
from src.database import guardar_pedido, actualizar_stock_inventario
from src.logic import validar_stock, preparar_fila_pedido
from src.nav import render_nav

def get_logo_b64(path="assets/logo_proesa.png"):
    """Devuelve el logo como string base64 para usarlo en HTML."""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return None

st.set_page_config(page_title="Registro de Pedidos", layout="wide", page_icon="📝")

PATH_INV_SISTEMA = "data/inventario_maestro.xlsx"
PATH_PEDIDOS     = "data/consolidado_pedidos.xlsx"

# ── INICIALIZACIÓN DEL CARRITO (Memoria temporal) ──────────────────────────
if 'carrito' not in st.session_state:
    st.session_state.carrito = []

# ── ESTILOS (Mantenidos intactos) ──────────────────────────────────────────
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

#MainMenu, header, footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── VERIFICACIÓN ─────────────────────────────────────────────────────────────
if not os.path.exists(PATH_INV_SISTEMA):
    st.error("⚠️ No se ha detectado el Inventario Maestro.")
    st.stop()

df_inv = pd.read_excel(PATH_INV_SISTEMA)
render_nav(active_page='registro', inventario_df=df_inv)

# ── HEADER ───────────────────────────────────────────────────────────────────
logo_b64 = get_logo_b64()
logo_html = (
    f'<img src="data:image/png;base64,{logo_b64}" style="height:52px;object-fit:contain;">'
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

tab_form, tab_historial = st.tabs(["🛒  Nuevo Pedido", "📊  Historial"])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — NUEVO PEDIDO CON CARRITO
# ════════════════════════════════════════════════════════════════════════════
with tab_form:
    col_form, col_info = st.columns([3, 2], gap="large")

    with col_form:
        st.markdown('<div class="section-title">Datos del Empleado</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        cod_emp = c1.text_input("Código de Empleado", placeholder="Ej: EMP-001")
        nom_emp = c2.text_input("Nombre Completo", placeholder="Nombre y apellido")

        st.markdown('<div class="section-title">Selección de Producto</div>', unsafe_allow_html=True)
        
        lista_prods = df_inv.iloc[:, 2].dropna().tolist()
        prod_sel = st.selectbox(
            "Producto",
            options=lista_prods,
            index=None,
            placeholder="Escribe para filtrar...",
            label_visibility="collapsed"
        )
        cant = st.number_input("Cantidad a pedir", min_value=1, step=1, value=1)

        # BOTÓN PARA AÑADIR AL CARRITO
        if st.button("➕ Añadir al Carrito", use_container_width=True):
            if prod_sel:
                fila_p = df_inv[df_inv.iloc[:, 2] == prod_sel].iloc[0]
                stock_actual = fila_p.iloc[3]
                
                # Validar stock considerando lo que ya está en el carrito
                cant_en_carrito = sum(item['cantidad'] for item in st.session_state.carrito if item['producto'] == prod_sel)
                
                if validar_stock(cant + cant_en_carrito, stock_actual):
                    st.session_state.carrito.append({
                        "producto": prod_sel,
                        "cantidad": int(cant),
                        "fila_data": fila_p,
                        "subtotal": float(fila_p.iloc[4]) * int(cant)
                    })
                    st.toast(f"✅ Agregado: {prod_sel}")
                else:
                    st.error(f"❌ Stock insuficiente. Solo quedan **{int(stock_actual)}** unidades.")
            else:
                st.warning("⚠️ Selecciona un producto antes de añadir.")

        # --- VISUALIZACIÓN DEL CARRITO ---
        if st.session_state.carrito:
            st.markdown('<div class="section-title">Tu Pedido Actual</div>', unsafe_allow_html=True)
            
            for i, item in enumerate(st.session_state.carrito):
                with st.container():
                    c_prod, c_cant, c_price, c_del = st.columns([3, 1, 1.5, 0.5])
                    c_prod.write(f"**{item['producto']}**")
                    c_cant.write(f"{item['cantidad']} ud.")
                    c_price.write(f"Bs {item['subtotal']:,.2f}")
                    if c_del.button("❌", key=f"del_{i}"):
                        st.session_state.carrito.pop(i)
                        st.rerun()

            st.write("---")
            monto_total_carrito = sum(item['subtotal'] for item in st.session_state.carrito)
            st.markdown(f"### Total Pedido: Bs {monto_total_carrito:,.2f}")

            # BOTÓN FINALIZAR TODO EL PEDIDO
            if st.button("✅  CONFIRMAR Y ENVIAR TODO EL PEDIDO", type="primary", use_container_width=True):
                if cod_emp and nom_emp:
                    # Procesar cada item del carrito
                    for item in st.session_state.carrito:
                        nueva_fila = preparar_fila_pedido(cod_emp, nom_emp, item['fila_data'], item['cantidad'])
                        guardar_pedido(nueva_fila)
                        actualizar_stock_inventario(item['fila_data'].iloc[1], item['cantidad'])
                    
                    st.session_state.carrito = [] # Limpiar carrito
                    st.success("🎉 ¡Pedido completo registrado con éxito!")
                    st.rerun()
                else:
                    st.error("⚠️ Faltan datos del empleado (Nombre o Código).")

    # ── Panel lateral informativo ──────────────────────────────────────────
    with col_info:
        st.markdown('<div class="section-title">Vista Previa del Producto</div>', unsafe_allow_html=True)
        if prod_sel:
            fila_preview = df_inv[df_inv.iloc[:, 2] == prod_sel].iloc[0]
            stock_prev   = int(fila_preview.iloc[3])
            precio_prev  = float(fila_preview.iloc[4])
            
            if stock_prev <= 0: stock_badge = f'<span class="stock-out">⛔ Agotado</span>'
            elif stock_prev <= 5: stock_badge = f'<span class="stock-warn">⚠️ Stock bajo: {stock_prev} ud.</span>'
            else: stock_badge = f'<span class="stock-ok">✅ En stock: {stock_prev} ud.</span>'

            st.markdown(f"""
            <div class="prod-info-box">
                <div class="label">Código</div><div class="value">{fila_preview.iloc[1]}</div>
            </div>
            <div class="prod-info-box">
                <div class="label">Precio Unitario</div><div class="value">Bs {precio_prev:,.2f}</div>
            </div>
            <div style="margin-top:0.75rem">{stock_badge}</div>
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
    if os.path.exists(PATH_PEDIDOS):
        df_p = pd.read_excel(PATH_PEDIDOS)
        if not df_p.empty:
            total_pedidos  = len(df_p)
            total_unidades = int(df_p["Cantidad"].sum()) if "Cantidad" in df_p.columns else 0
            
            st.markdown(f"""
            <div style="margin:1rem 0 1.25rem">
                <div class="stat-pill">📋 {total_pedidos} <span>registros</span></div>
                <div class="stat-pill">📦 {total_unidades:,} <span>unidades</span></div>
            </div>
            """, unsafe_allow_html=True)

            # Herramienta de corrección
            with st.expander("🗑️  Herramienta de Corrección — Eliminar Registro"):
                id_a_borrar = st.selectbox("Registro a anular:", options=df_p.index,
                    format_func=lambda x: f"#{x} | {df_p.loc[x, 'Nombre Empleado']} → {df_p.loc[x, 'Nombre Producto']}")
                
                if st.button("🗑️ Confirmar eliminación"):
                    cod_prod_borrar = df_p.loc[id_a_borrar, "Código Producto"]
                    cant_borrar     = df_p.loc[id_a_borrar, "Cantidad"]
                    actualizar_stock_inventario(cod_prod_borrar, -cant_borrar)
                    df_p_nuevo = df_p.drop(id_a_borrar)
                    df_p_nuevo.to_excel(PATH_PEDIDOS, index=False)
                    st.success("Registro eliminado y stock restaurado.")
                    st.rerun()

            st.dataframe(df_p, use_container_width=True, height=400)
        else:
            st.info("No hay pedidos registrados.")
    else:
        st.warning("El archivo de pedidos no existe aún.")  