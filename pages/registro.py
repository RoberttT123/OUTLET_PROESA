# -*- coding: utf-8 -*-
"""
REGISTRO DE PEDIDOS - OUTLET PROESA
--------------------------------------
Gestión de pedidos y consulta del historial para el equipo de administración.

NOTA: set_page_config e inject_nav_css están en app.py.
      No llamar st.set_page_config() desde aquí.

CORRECCIONES APLICADAS:
  - [FIX 1] Rollback automático de stock si guardar_pedido_sheets falla
  - [FIX 2] cargar_inventario.clear() en lugar de st.cache_data.clear() global
  - [FIX 3] Parseo de precios sin heurísticas de división peligrosas
"""

import streamlit as st
import pandas as pd
import os
import re
import base64
from datetime import datetime

# ── Configuración de conectividad ─────────────────────────────────────────────
try:
    from config import (
        INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME,
        PEDIDOS_SHEET_URL,    PEDIDOS_HOJA_NAME,
    )
    USING_SHEETS = True
except ImportError:
    USING_SHEETS = False

try:
    from src.nav import render_nav
    from src.logic import validar_stock, preparar_fila_pedido
    from src.database import obtener_datos_empleado, validar_empleado
except ImportError as e:
    st.error("❌ Error cargando módulos esenciales del núcleo `src/`.")
    st.code(str(e))
    st.stop()

if USING_SHEETS:
    try:
        from src.sheets import (
            obtener_inventario_sheets,
            obtener_todos_pedidos_sheets,
            guardar_pedido_sheets,
            procesar_descuento_stock_seguro,
            restaurar_stock_sheets,          # [FIX 1] Para rollback automático
        )
    except ImportError as e:
        st.error("❌ Error importando funciones desde `src/sheets.py`.")
        st.code(str(e))
        st.stop()
else:
    from src.database import guardar_pedido, actualizar_stock_inventario

# ── Session state inicial ─────────────────────────────────────────────────────
defaults = {
    "carrito":           [],
    "emp_validado":      False,
    "cod_emp_validado":  None,
    "nom_emp_validado":  None,
    "empresa_validada":  None,
    "regional_validada": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Estilos de página ─────────────────────────────────────────────────────────
st.markdown("""
<style>
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
.stApp { background: #F5F4F0; }
.block-container { padding-top: 0.2rem !important; padding-bottom: 0rem !important; }
.page-header {
    background: #FFFFFF; border-radius: 16px; padding: 1.5rem 2rem;
    margin-bottom: 1.5rem; box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    display: flex; align-items: center; gap: 1rem; border-top: 4px solid #E63946;
}
.page-header h2 { color: #1A1A2E; font-size: 1.5rem; font-weight: 600; margin: 0; }
.page-header p  { color: #888; margin: 0.2rem 0 0; font-size: 0.9rem; }
.prod-info-box {
    background: #F0F7FF; border: 1px solid #BFDBFE;
    border-radius: 10px; padding: 1rem 1.25rem; margin: 0.75rem 0;
}
.prod-info-box .label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px; color: #60A5FA; font-weight: 700; }
.prod-info-box .value { font-size: 1.1rem; font-weight: 600; color: #1D4ED8; }
.stock-ok   { background: #D1FAE5; color: #065F46; border-radius: 20px; padding: 3px 12px; font-size: 0.8rem; font-weight: 600; display: inline-block; }
.stock-warn { background: #FEF9C3; color: #854D0E; border-radius: 20px; padding: 3px 12px; font-size: 0.8rem; font-weight: 600; display: inline-block; }
.stock-out  { background: #FEE2E2; color: #991B1B; border-radius: 20px; padding: 3px 12px; font-size: 0.8rem; font-weight: 600; display: inline-block; }
.section-title {
    font-size: 0.78rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1.5px; color: #AAA; margin: 1.5rem 0 0.5rem;
    padding-bottom: 0.4rem; border-bottom: 2px solid #EBEBEB;
}
.stat-pill {
    display: inline-flex; align-items: center; gap: 0.4rem;
    background: #FFFFFF; border-radius: 20px; padding: 0.4rem 1rem;
    box-shadow: 0 1px 6px rgba(0,0,0,0.08); font-size: 0.85rem;
    font-weight: 600; color: #1A1A2E; margin-right: 0.5rem; margin-bottom: 0.5rem;
}
.emp-info-card {
    background: #F0F7FF; border: 1px solid #BFDBFE;
    border-radius: 10px; padding: 1rem; margin-bottom: 1rem;
}
.carrito-item {
    background: #FFFFFF; border-radius: 10px; padding: 1rem;
    margin-bottom: 0.5rem; border-left: 3px solid #E63946;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
#MainMenu                      { display: none !important; }
footer                         { display: none !important; }
[data-testid="stDecoration"]   { display: none !important; }
[data-testid="stToolbar"]      { display: none !important; }
.stDeployButton                { display: none !important; }
[data-testid="stStatusWidget"] { display: none !important; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PARSEO SEGURO DE PRECIOS
# [FIX 3] Reemplaza el heurístico "si >= 1000 → /100" que distorsionaba
# precios legítimos (p.ej. Bs 1.500 pasaba a Bs 15,00).
# ══════════════════════════════════════════════════════════════════════════════
def _parsear_precio_str(val) -> float:
    try:
        s = str(val).upper().replace("BS", "").replace(" ", "").strip()
        if not s or s in ("NAN", "NONE", ""):
            return 0.0
        # Formato latino: 1.500,00 → punto=miles, coma=decimal
        if re.match(r'^\d{1,3}(\.\d{3})+(,\d+)?$', s):
            s = s.replace(".", "").replace(",", ".")
        elif "," in s and "." not in s:
            s = s.replace(",", ".")   # 8,77 → 8.77
        else:
            s = s.replace(",", "")    # quitar comas de miles formato US
        return float(s)
    except Exception:
        return 0.0


# ══════════════════════════════════════════════════════════════════════════════
# CARGA DE INVENTARIO
# ══════════════════════════════════════════════════════════════════════════════
if USING_SHEETS:
    @st.cache_data(ttl=60, show_spinner=False)
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
    df_inv = pd.read_excel(
        "data/inventario_maestro.xlsx",
        dtype={"Código Producto": str, "Stock": str, "Precio Unitario": str},
    )

COL_NOMBRE  = "Nombre Producto" if "Nombre Producto" in df_inv.columns else df_inv.columns[2]
COL_CODIGO  = "Código Producto" if "Código Producto" in df_inv.columns else df_inv.columns[1]
COL_STOCK   = "Stock"           if "Stock"           in df_inv.columns else df_inv.columns[3]
COL_PRECIO  = "Precio Unitario" if "Precio Unitario" in df_inv.columns else df_inv.columns[4]
COL_LINEA   = "Línea"           if "Línea"           in df_inv.columns else df_inv.columns[0]
COL_EMPRESA = "Empresa"         if "Empresa"         in df_inv.columns else df_inv.columns[5]


def sanitizar_matriz_inventario_registro(df):
    nuevos_stocks  = []
    nuevos_precios = []
    for idx, row in df.iterrows():
        # Precio — parseo seguro sin heurísticas de división
        nuevos_precios.append(_parsear_precio_str(str(row[COL_PRECIO])))
        # Stock
        try:
            s_str = str(row[COL_STOCK]).strip().replace(",", "")
            if "." in s_str and len(s_str.split(".")[1]) == 3:
                s_str = s_str.replace(".", "")
            stock_final = int(float(s_str))
        except Exception:
            stock_final = 0
        nuevos_stocks.append(stock_final)
    df[COL_STOCK]  = nuevos_stocks
    df[COL_PRECIO] = nuevos_precios
    return df


df_inv = sanitizar_matriz_inventario_registro(df_inv)

render_nav(active_page="registro", inventario_df=df_inv)


def construir_indice(df):
    return {str(row[COL_NOMBRE]).strip(): row for _, row in df.iterrows() if pd.notna(row[COL_NOMBRE])}

indice_productos = construir_indice(df_inv)


# ── Logo y encabezado ─────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def get_logo_b64(path="assets/logo_proesa.png"):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None

logo_b64  = get_logo_b64()
logo_html = (
    f'<img src="data:image/png;base64,{logo_b64}" style="height:150px;object-fit:contain;">'
    if logo_b64 else '<div style="font-size:2.2rem">📝</div>'
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


# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_form, tab_historial = st.tabs(["🛒  Nuevo Pedido", "📊  Historial"])


with tab_form:
    col_form, col_info = st.columns([3, 2], gap="large")

    with col_form:
        st.markdown('<div class="section-title">Validación de Empleado</div>', unsafe_allow_html=True)

        with st.form("validar_empleado_form"):
            cod_inp = st.text_input(
                "Código de Empleado", placeholder="Ej: E0200491",
                value="" if not st.session_state.emp_validado
                else (st.session_state.cod_emp_validado or ""),
            ).upper().strip()

            if st.form_submit_button("✅ Validar Empleado", use_container_width=True):
                if cod_inp:
                    datos = obtener_datos_empleado(cod_inp)
                    if datos.get("encontrado"):
                        st.session_state.emp_validado      = True
                        st.session_state.cod_emp_validado  = cod_inp
                        st.session_state.nom_emp_validado  = datos["nombre"]
                        st.session_state.empresa_validada  = datos["empresa"]
                        st.session_state.regional_validada = datos["regional"]
                        st.success(f"✅ Empleado encontrado: {datos['nombre']}")
                        st.rerun()
                    else:
                        st.error(f"❌ Código '{cod_inp}' no encontrado.")
                else:
                    st.error("⚠️ Ingresa un código de empleado.")

        if st.session_state.emp_validado:
            st.markdown(f"""
            <div class="emp-info-card">
                <strong>✅ Empleado Validado</strong><br><small>
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

            st.markdown('<div class="section-title">Selección de Producto</div>', unsafe_allow_html=True)

            with st.form("registro_operativo"):
                busqueda_prod = st.text_input(
                    "Busca un producto...", placeholder="Escribe el nombre o código para filtrar"
                )
                if busqueda_prod:
                    mascara = (
                        df_inv[COL_NOMBRE].astype(str).str.contains(busqueda_prod, case=False, na=False)
                        | df_inv[COL_CODIGO].astype(str).str.strip().str.contains(busqueda_prod, case=False, na=False)
                    )
                    prods_filtrados = df_inv[mascara][COL_NOMBRE].dropna().tolist()
                else:
                    prods_filtrados = df_inv[COL_NOMBRE].dropna().tolist()

                prod_sel = st.selectbox(
                    "Producto", options=prods_filtrados, index=None,
                    placeholder="Escribe para filtrar...", label_visibility="collapsed",
                )
                cant = st.number_input("Cantidad a pedir", min_value=1, step=1, value=1)

                btn_col1, _ = st.columns([2, 1])
                with btn_col1:
                    btn_agregar = st.form_submit_button("➕ Añadir al Carrito", use_container_width=True)

                if btn_agregar:
                    if prod_sel:
                        fila_p = indice_productos.get(str(prod_sel).strip())
                        if fila_p is not None:
                            stock_actual   = int(fila_p[COL_STOCK])
                            item_existente = next(
                                (i for i in st.session_state.carrito if i["producto"] == prod_sel), None
                            )
                            cant_previa = item_existente["cantidad"] if item_existente else 0
                            cant_total  = cant + cant_previa

                            if validar_stock(cant_total, stock_actual):
                                precio_unit = float(fila_p[COL_PRECIO])
                                if item_existente:
                                    item_existente["cantidad"] = int(cant_total)
                                    item_existente["subtotal"] = precio_unit * int(cant_total)
                                else:
                                    st.session_state.carrito.append({
                                        "producto":  prod_sel,
                                        "cantidad":  int(cant),
                                        "fila_data": fila_p,
                                        "subtotal":  precio_unit * int(cant),
                                    })
                                st.toast(f"🛒 Carrito actualizado: {prod_sel}")
                                st.rerun()
                            else:
                                st.error(f"❌ Stock insuficiente. Solo quedan **{stock_actual}** unidades.")
                    else:
                        st.warning("⚠️ Selecciona un producto.")

            if st.session_state.carrito:
                st.markdown('<div class="section-title">Tu Pedido Actual</div>', unsafe_allow_html=True)

                for i, item in enumerate(st.session_state.carrito):
                    with st.container():
                        fila_item   = indice_productos.get(item["producto"])
                        stock_max   = int(fila_item[COL_STOCK])   if fila_item is not None else 99
                        precio_unit = float(fila_item[COL_PRECIO]) if fila_item is not None else 0.0

                        c_prod, c_cant, c_price, c_del = st.columns([2.5, 1.2, 1.5, 0.5])
                        c_prod.markdown(f"**{item['producto']}**\n`Bs {precio_unit:,.2f} c/u`")

                        with c_cant:
                            nueva_cant = st.number_input(
                                "Cantidad", min_value=1, max_value=max(stock_max, 1),
                                value=int(item["cantidad"]), step=1,
                                key=f"edit_cant_{i}", label_visibility="collapsed",
                            )
                            if nueva_cant != item["cantidad"]:
                                st.session_state.carrito[i]["cantidad"] = nueva_cant
                                st.session_state.carrito[i]["subtotal"] = nueva_cant * precio_unit
                                st.rerun()

                        c_price.markdown(f"**Bs {item['subtotal']:,.2f}**")
                        if c_del.button("❌", key=f"del_{i}", use_container_width=True):
                            st.session_state.carrito.pop(i)
                            st.rerun()

                st.write("---")
                monto_total = sum(item["subtotal"] for item in st.session_state.carrito)
                st.markdown(f"### Total Pedido: Bs {monto_total:,.2f}")

                if st.button("✅  CONFIRMAR Y ENVIAR TODO EL PEDIDO", type="primary", use_container_width=True):
                    try:
                        if USING_SHEETS:
                            items_para_sheets = []
                            for item in st.session_state.carrito:
                                fila = item["fila_data"]
                                items_para_sheets.append({
                                    "codigo_producto": str(fila[COL_CODIGO]),
                                    "producto":        item["producto"],
                                    "cantidad":        int(item["cantidad"]),
                                    "precio_unitario": float(fila[COL_PRECIO]),
                                    "linea":           str(fila[COL_LINEA]),
                                    "descuento":       0,
                                    "stock_actual":    int(fila[COL_STOCK]),
                                    "empresa":         st.session_state.empresa_validada or str(fila[COL_EMPRESA]),
                                })

                            with st.status("Procesando pedido...", expanded=True) as status:
                                st.write("🔍 Verificando disponibilidad en tiempo real...")
                                transaccion = procesar_descuento_stock_seguro(
                                    items=[{
                                        "codigo_producto": i["codigo_producto"],
                                        "cantidad_a_restar": i["cantidad"],
                                    } for i in items_para_sheets],
                                    url_sheet=INVENTARIO_SHEET_URL,
                                    hoja=INVENTARIO_HOJA_NAME,
                                )

                                if not transaccion["exito"]:
                                    status.update(label="⚠️ Stock insuficiente.", state="error")
                                    for p in transaccion["sin_stock"]:
                                        st.error(
                                            f"❌ **{p['producto']}** — "
                                            f"Pediste {p['pedido']} ud. pero solo quedan {p['disponible']}."
                                        )
                                    st.warning("Ajusta las cantidades e intenta de nuevo.")
                                else:
                                    st.write("📝 Guardando en el registro...")
                                    guardado = guardar_pedido_sheets(
                                        st.session_state.cod_emp_validado,
                                        st.session_state.nom_emp_validado,
                                        items_para_sheets,
                                        PEDIDOS_SHEET_URL,
                                        PEDIDOS_HOJA_NAME,
                                    )
                                    if guardado:
                                        st.session_state.carrito = []
                                        # [FIX 2] Solo invalida el inventario cacheado,
                                        # sin afectar a empleados activos en otras sesiones.
                                        cargar_inventario.clear()
                                        status.update(
                                            label="✅ ¡Pedido enviado y stock actualizado!",
                                            state="complete",
                                        )
                                        st.toast("🎉 ¡Pedido registrado con éxito!", icon="✅")
                                        st.rerun()
                                    else:
                                        # [FIX 1] ROLLBACK: el stock ya fue descontado
                                        # pero el guardado falló. Lo restauramos.
                                        st.write("⏪ Revirtiendo reserva de stock...")
                                        restaurar_stock_sheets(
                                            items=[{
                                                "codigo_producto": i["codigo_producto"],
                                                "cantidad_a_restar": i["cantidad"],
                                            } for i in items_para_sheets],
                                            url_sheet=INVENTARIO_SHEET_URL,
                                            hoja=INVENTARIO_HOJA_NAME,
                                        )
                                        status.update(label="❌ Error al guardar.", state="error")
                                        st.error(
                                            "El stock fue restaurado automáticamente. "
                                            "Intenta de nuevo en unos segundos."
                                        )
                        else:
                            with st.status("Guardando pedido...", expanded=True) as status:
                                st.write("📝 Escribiendo en archivo local...")
                                for item in st.session_state.carrito:
                                    nueva_fila = preparar_fila_pedido(
                                        st.session_state.cod_emp_validado,
                                        st.session_state.nom_emp_validado,
                                        item["fila_data"], item["cantidad"],
                                    )
                                    guardar_pedido(nueva_fila)
                                    actualizar_stock_inventario(item["fila_data"].iloc[1], item["cantidad"])
                                st.session_state.carrito = []
                                status.update(label="✅ Pedido guardado.", state="complete")
                                st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error en el proceso: {str(e)}")

        else:
            st.info("👆 Valida un empleado para comenzar a registrar pedidos.")

    with col_info:
        st.markdown('<div class="section-title">Vista Previa del Producto</div>', unsafe_allow_html=True)

        if st.session_state.emp_validado and "prod_sel" in locals() and prod_sel:
            fila_preview = indice_productos.get(str(prod_sel).strip())
            if fila_preview is not None:
                stock_prev   = int(fila_preview[COL_STOCK])
                precio_prev  = float(fila_preview[COL_PRECIO])
                codigo_prev  = fila_preview[COL_CODIGO]
                linea_prev   = fila_preview[COL_LINEA]
                empresa_prev = fila_preview[COL_EMPRESA]

                if stock_prev <= 0:
                    stock_badge = '<span class="stock-out">⛔ Agotado</span>'
                elif stock_prev <= 5:
                    stock_badge = f'<span class="stock-warn">⚠️ Stock bajo: {stock_prev} ud.</span>'
                else:
                    stock_badge = f'<span class="stock-ok">✅ En stock: {stock_prev} ud.</span>'

                st.markdown(f"""
                <div class="prod-info-box"><div class="label">Código</div><div class="value">{codigo_prev}</div></div>
                <div class="prod-info-box"><div class="label">Línea</div><div class="value" style="font-size:0.95rem">{linea_prev}</div></div>
                <div class="prod-info-box"><div class="label">Empresa</div><div class="value" style="font-size:0.95rem">{empresa_prev}</div></div>
                <div class="prod-info-box"><div class="label">Precio Unitario</div><div class="value">Bs {precio_prev:,.2f}</div></div>
                <div style="margin-top:0.75rem">{stock_badge}</div>
                """, unsafe_allow_html=True)

                if "cant" in locals() and cant and cant > 0:
                    total_est = cant * precio_prev
                    st.markdown(f"""
                    <div style="background:#1A1A2E;color:white;border-radius:10px;
                                padding:1rem 1.25rem;margin-top:0.75rem">
                        <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:1px;
                                    color:#A8B2C8;margin-bottom:0.3rem">Total estimado</div>
                        <div style="font-size:1.6rem;font-weight:700;">Bs {total_est:,.2f}</div>
                        <div style="font-size:0.78rem;color:#A8B2C8;margin-top:0.2rem">
                            {int(cant)} ud. × Bs {precio_prev:,.2f}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background:#F9F9F9;border:2px dashed #DDD;border-radius:12px;
                        padding:2rem;text-align:center;color:#BBB;">
                <div style="font-size:2rem;margin-bottom:0.5rem">🔍</div>
                <div style="font-size:0.9rem">Selecciona un producto<br>para ver su detalle</div>
            </div>
            """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB HISTORIAL
# ══════════════════════════════════════════════════════════════════════════════
with tab_historial:
    if USING_SHEETS:
        @st.cache_data(ttl=60, show_spinner=False)
        def _cargar_historial_completo():
            return obtener_todos_pedidos_sheets(PEDIDOS_SHEET_URL, PEDIDOS_HOJA_NAME)
        df_p = _cargar_historial_completo()
    else:
        path_p = "data/consolidado_pedidos.xlsx"
        df_p   = pd.read_excel(path_p) if os.path.exists(path_p) else pd.DataFrame()

    if not df_p.empty:
        total_pedidos = len(df_p)

        col_monto_historial    = (
            "Monto Uni" if "Monto Uni" in df_p.columns
            else ("Precio Unitario" if "Precio Unitario" in df_p.columns else None)
        )
        col_cantidad_historial = "Cantidad"        if "Cantidad"        in df_p.columns else df_p.columns[7]
        col_codigo_historial   = "Código Producto" if "Código Producto" in df_p.columns else df_p.columns[3]

        if col_monto_historial:
            df_p[col_monto_historial] = pd.to_numeric(
                df_p[col_monto_historial], errors="coerce"
            ).fillna(0.0)

            precios_maestros = {
                str(row[COL_CODIGO]).strip(): float(row[COL_PRECIO])
                for _, row in df_inv.iterrows() if pd.notna(row[COL_CODIGO])
            }

            def normalizar_precio_historial(row):
                codigo_p       = str(row.get(col_codigo_historial, "")).strip()
                precio_guardado = row[col_monto_historial]
                if codigo_p in precios_maestros:
                    return precios_maestros[codigo_p]
                return _parsear_precio_str(str(precio_guardado))

            df_p[col_monto_historial] = df_p.apply(normalizar_precio_historial, axis=1)

        total_unidades = int(
            pd.to_numeric(df_p[col_cantidad_historial], errors="coerce").fillna(0).sum()
        )

        st.markdown(f"""
        <div style="margin:1rem 0 1.25rem">
            <div class="stat-pill">📋 {total_pedidos} pedidos</div>
            <div class="stat-pill">📦 {total_unidades:,} unidades</div>
        </div>
        """, unsafe_allow_html=True)

        config_columnas = {}
        if col_monto_historial:
            config_columnas[col_monto_historial] = st.column_config.NumberColumn(
                col_monto_historial, format="Bs %.2f"
            )

        st.dataframe(df_p, use_container_width=True, height=400, column_config=config_columnas)

        try:
            csv = df_p.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"Pedidos_{datetime.now().strftime('%d_%m_%Y')}.csv",
                mime="text/csv",
            )
        except Exception:
            pass
    else:
        st.info("No hay pedidos registrados en el historial.")