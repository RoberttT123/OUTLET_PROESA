# -*- coding: utf-8 -*-
"""
MÓDULO DE INTERFAZ DE USUARIO Y GESTIÓN DE PEDIDOS - OUTLET PROESA
----------------------------------------------------------------
Desarrollado para: PROYECTO_OUTLET
Última actualización: Mayo 2026
"""

import streamlit as st
import pandas as pd
import base64
import json
from datetime import datetime, date, timedelta

# ==============================================================================
# 1. IMPORTS
# ==============================================================================
try:
    from config import (
        INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME,
        PEDIDOS_SHEET_URL,    PEDIDOS_HOJA_NAME,
    )
except ImportError:
    st.error("❌ Archivo `config.py` no encontrado en la raíz del proyecto.")
    st.stop()

try:
    from src.sheets import (
        obtener_inventario_sheets,
        obtener_pedidos_empleado_sheets,
        guardar_pedido_sheets,
        procesar_descuento_stock_seguro,
        verificar_stock_disponible,
    )
    from src.database import obtener_datos_empleado, validar_empleado
    from src.componentes import cargar_estilos_css, render_tarjeta_producto
except ImportError as e:
    st.error("❌ Error cargando módulos esenciales desde `src/`.")
    st.code(str(e))
    st.stop()

# ==============================================================================
# 2. PAGE CONFIG Y CSS
# ==============================================================================
try:
    st.set_page_config(
        page_title="Mi Pedido - Outlet PROESA",
        layout="wide",
        page_icon="🛒",
        initial_sidebar_state="collapsed",
    )
except Exception:
    pass

try:
    cargar_estilos_css()
except Exception as e:
    st.warning(f"⚠️ Estilos CSS base no aplicados: {e}")

st.markdown("""
<style>
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
div[data-testid="stRadio"] label[data-checked="true"] {
    color: #1A1A2E !important;
    font-weight: 600 !important;
    border-bottom: 3px solid #E63946 !important;
}
div[data-testid="stRadio"] [data-testid="stWidgetLabel"] { display: none !important; }
div[data-testid="stRadio"] span[data-testid="stMarkdownContainer"] p { margin: 0; }
div[data-testid="stRadio"] div[data-baseweb="radio"] > div:first-child { display: none !important; }

.alerta-stock-container {
    background-color: #FFF5F5;
    border-left: 4px solid #E63946;
    border-radius: 6px;
    padding: 1.2rem;
    margin-top: 1.2rem;
    box-shadow: 0 2px 4px rgba(230, 57, 70, 0.05);
}
.alerta-stock-titulo  { color: #E63946; font-size: 1.05rem; font-weight: 600; margin-bottom: 0.6rem; }
.alerta-stock-lista   { color: #4A4A4A; font-size: 0.92rem; line-height: 1.4; margin-bottom: 0.8rem; padding-left: 1.1rem; }
.alerta-stock-sugerencia {
    color: #666; font-size: 0.88rem;
    border-top: 1px dashed #F3C6C9; padding-top: 0.6rem;
}

/* ── Fila de producto dentro del expander ── */
.prod-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.55rem 0.2rem;
    border-bottom: 1px solid #F0F0F0;
}
.prod-row:last-child { border-bottom: none; }
.prod-nombre { font-size: 0.88rem; color: #1A1A2E; font-weight: 500; flex: 1; }
.prod-qty    { font-size: 0.82rem; color: #666; margin: 0 1rem; white-space: nowrap; }
.prod-total  { font-size: 0.9rem; font-weight: 700; color: #E63946; white-space: nowrap; }

/* ── Chip de resumen en el expander ── */
.chip {
    display: inline-block;
    background: #F0F4FF;
    color: #1A1A2E;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 2px 10px;
    border-radius: 20px;
    margin-left: 0.5rem;
}
.chip-red { background: #FFF0F0; color: #E63946; }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# 3. LOGO
# ==============================================================================
@st.cache_data(show_spinner=False)
def get_logo_b64(path="assets/logo_proesa.png"):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None


# ==============================================================================
# 4. SESSION STATE
# ==============================================================================
defaults = {
    "logged_in":  False,
    "cod_emp":    None,
    "nom_emp":    None,
    "empresa":    None,
    "regional":   None,
    "carrito":    [],
    "tab_idx":    0,
    "toast_msg":  None,
    "toast_icon": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ==============================================================================
# 5. PARSEO ROBUSTO
# ==============================================================================
def _parse_stock(v) -> int:
    try:
        return max(0, int(float(str(v).strip().replace(",", ""))))
    except Exception:
        return 0

def _parse_precio(v) -> float:
    try:
        return float(str(v).strip().replace(",", "."))
    except Exception:
        return 0.0

def _parsear_fecha(valor_str: str) -> date | None:
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(valor_str).strip(), fmt).date()
        except Exception:
            pass
    return None

def _etiqueta_relativa(d: date) -> str:
    """Devuelve etiqueta legible para una fecha (Hoy, Ayer, día de semana, o fecha)."""
    hoy  = date.today()
    diff = (hoy - d).days
    if diff == 0:
        return "Hoy"
    if diff == 1:
        return "Ayer"
    if diff < 7:
        dias = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
        return dias[d.weekday()]
    return d.strftime("%d/%m/%Y")


# ==============================================================================
# 6. INVENTARIO E ÍNDICE
# ==============================================================================
@st.cache_data(ttl=600, show_spinner=False)
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
    st.error("❌ Catálogo no disponible. Revisa la conectividad o config.py.")
    st.stop()

indice_productos = construir_indice(str(df_inv.shape))

COL_NOMBRE = "Nombre Producto" if "Nombre Producto" in df_inv.columns else df_inv.columns[2]
COL_CODIGO = "Código Producto" if "Código Producto" in df_inv.columns else df_inv.columns[1]
COL_STOCK  = "Stock"           if "Stock"           in df_inv.columns else df_inv.columns[3]
COL_PRECIO = "Precio Unitario" if "Precio Unitario" in df_inv.columns else df_inv.columns[4]
COL_LINEA  = "Línea"           if "Línea"           in df_inv.columns else df_inv.columns[0]
COL_EMP    = "Empresa"         if "Empresa"         in df_inv.columns else df_inv.columns[5]


# ==============================================================================
# VERIFICACIÓN: OUTLET ACTIVO
# Si el administrador desactivó el outlet desde inicio.py, se bloquea
# el acceso completo antes de mostrar cualquier pantalla a los empleados.
# ==============================================================================
def _outlet_activo() -> bool:
    try:
        with open("data/outlet_estado.json", "r", encoding="utf-8") as f:
            return json.load(f).get("activo", True)
    except Exception:
        return True   # Sin archivo → activo por defecto

if not _outlet_activo():
    logo = get_logo_b64()
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #1A1A2E 0%, #0F3460 100%);
        border-radius: 20px;
        padding: 3rem 2.5rem;
        margin: 2rem auto;
        max-width: 520px;
        text-align: center;
        color: white;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    ">
        {f'<img src="data:image/png;base64,{logo}" style="height:120px;object-fit:contain;margin-bottom:1.5rem;">' if logo else '<div style="font-size:3rem;margin-bottom:1rem;">📦</div>'}
        <div style="font-size:2.5rem;margin-bottom:0.75rem;">🔒</div>
        <h2 style="margin:0 0 0.75rem;font-size:1.6rem;font-weight:700;">
            Outlet Cerrado
        </h2>
        <p style="opacity:0.85;font-size:1rem;margin:0 0 0.5rem;">
            El período de pedidos ha finalizado por el momento.
        </p>
        <p style="opacity:0.6;font-size:0.85rem;margin:0;">
            Consulta con tu supervisor para más información.
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ==============================================================================
# PANTALLA 1: LOGIN
# ==============================================================================
if not st.session_state.logged_in:
    logo = get_logo_b64()
    st.markdown(f"""
    <div class="hero-login">
        {f'<img src="data:image/png;base64,{logo}" style="height:210px;width:auto;object-fit:contain;margin-top:-20px;">' if logo else ""}
        <h1 style="margin-top:0;">Outlet PROESA</h1>
        <p style="margin-bottom:0;">Sistema de Pedidos Internos para Empleados</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        st.subheader("🔑 Acceso al Sistema")
        cod = st.text_input(
            "Código de Empleado",
            placeholder="Ej: E0200491",
            help="Consulte con su supervisor si desconoce su código corporativo.",
        ).upper().strip()
        st.markdown("<br>", unsafe_allow_html=True)

        if st.form_submit_button("🚀 Validar Credenciales", use_container_width=True):
            if cod:
                with st.spinner("Consultando registros de personal..."):
                    try:
                        datos = obtener_datos_empleado(cod)
                        if datos and datos.get("encontrado"):
                            st.session_state.logged_in = True
                            st.session_state.cod_emp   = cod
                            st.session_state.nom_emp   = datos.get("nombre", "Empleado")
                            st.session_state.empresa   = datos.get("empresa", "N/A")
                            st.session_state.regional  = datos.get("regional", "N/A")
                            st.success("✅ Acceso autorizado.")
                            st.rerun()
                        else:
                            st.error(f"❌ Código '{cod}' no registrado en la base de datos.")
                    except Exception as e:
                        st.error(f"Error en verificación: {e}")
            else:
                st.error("⚠️ Ingresa tu código de empleado para continuar.")


# ==============================================================================
# PANTALLA 2: PEDIDOS
# ==============================================================================
else:
    if st.session_state.get("lanzar_toast_exito"):
        st.toast("🎉 ¡Tu pedido fue enviado con éxito!", icon="🛒")
        del st.session_state["lanzar_toast_exito"]

    if st.session_state.get("toast_msg"):
        st.toast(st.session_state["toast_msg"], icon=st.session_state.get("toast_icon", "🛒"))
        st.session_state["toast_msg"]  = None
        st.session_state["toast_icon"] = None

    logo = get_logo_b64()
    st.markdown(f"""
    <div class="page-header">
        {f'<img src="data:image/png;base64,{logo}" style="height:100px;object-fit:contain;">' if logo else "🛒"}
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

    # ── FUNCIÓN TRANSACCIONAL ────────────────────────────────────────────────
    def ejecutar_envio_transaccional(items):
        if "lista_productos_colision" in st.session_state:
            del st.session_state["lista_productos_colision"]

        with st.status("Procesando tu pedido...", expanded=True) as estado:
            try:
                st.write("🔍 Verificando disponibilidad y reservando stock...")
                transaccion = procesar_descuento_stock_seguro(
                    items=[{
                        "codigo_producto":   i["codigo_producto"],
                        "cantidad_a_restar": i["cantidad"],
                    } for i in items],
                    url_sheet=INVENTARIO_SHEET_URL,
                    hoja=INVENTARIO_HOJA_NAME,
                )

                if not transaccion["exito"]:
                    estado.update(label="⚠️ Pedido rechazado por falta de stock.", state="error")
                    detalles_html = ""
                    for p in transaccion["sin_stock"]:
                        detalles_html += (
                            f"<li><b>{p['producto']}</b>: Solicitaste {p['pedido']} ud., "
                            f"pero el stock actual bajo a <b>{p['disponible']} ud.</b></li>"
                        )
                    st.session_state["lista_productos_colision"] = detalles_html
                    st.toast("⚠️ No se pudo enviar el pedido: stock agotado.", icon="❌")
                    st.cache_data.clear()
                    st.rerun()
                    return False

                st.write("📝 Guardando el registro oficial del pedido...")
                ok = guardar_pedido_sheets(
                    st.session_state.cod_emp,
                    st.session_state.nom_emp,
                    items,
                    PEDIDOS_SHEET_URL,
                    PEDIDOS_HOJA_NAME,
                )
                if ok:
                    st.session_state.carrito = []
                    st.session_state.tab_idx = 0
                    st.cache_data.clear()
                    st.session_state["lanzar_toast_exito"] = True
                    estado.update(label="✅ ¡Pedido procesado con éxito!", state="complete")
                    st.rerun()
                    return True
                else:
                    estado.update(label="❌ Error al escribir el registro.", state="error")
                    st.error("El stock fue apartado pero falló la escritura. Contacta al administrador.")
                    return False

            except Exception as e:
                estado.update(label="❌ Error inesperado.", state="error")
                st.error(f"Detalle: {e}")
                return False

    # ── FRAGMENT CENTRAL ─────────────────────────────────────────────────────
    @st.fragment
    def render_pedido():
        total_uds = sum(int(i.get("cantidad", 0)) for i in st.session_state.carrito)
        label_c   = f"🛒 Carrito ({total_uds})" if total_uds > 0 else "🛒 Carrito"
        opciones  = ["📦 Catálogo", label_c, "📋 Mis Pedidos"]

        tab_sel = st.radio(
            "tabs_nav", opciones,
            index=int(st.session_state.tab_idx),
            horizontal=True,
            label_visibility="collapsed",
            key="radio_tabs_nav",
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
                key="busqueda_catalogo",
            )

            if filtro:
                expr    = str(filtro).strip()
# DESPUÉS ✅
                mascara = (
                    df_inv[COL_NOMBRE].astype(str).str.contains(expr, case=False, na=False, regex=False)
                    | df_inv[COL_CODIGO].astype(str).str.strip().str.contains(expr, case=False, na=False, regex=False)
                )
                df_vista = df_inv[mascara]
            else:
                df_vista = df_inv

            if df_vista.empty:
                st.info("🔍 Ningún artículo coincide con los criterios introducidos.")
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
                                precio=precio, stock_badge=badge,
                            )
                            if not bloqueado:
                                c_num, c_btn = st.columns([1, 1.3])
                                with c_num:
                                    # Sin max_value para validar en el backend
                                    cant = st.number_input(
                                        "Cant", min_value=1, value=1, step=1,
                                        key=f"qty_{idx}_{codigo}",
                                        label_visibility="collapsed",
                                    )
                                with c_btn:
                                    if st.button("➕ Solicitar", key=f"add_{idx}_{codigo}", use_container_width=True):
                                        # Validación de stock en Python
                                        if int(cant) > stock:
                                            st.session_state["toast_msg"]  = f"⚠️ Solo hay {stock} unidades disponibles"
                                            st.session_state["toast_icon"] = "🚫"
                                            st.rerun(scope="fragment")
                                        else:
                                            item_existente = next(
                                                (i for i in st.session_state.carrito if i["codigo_producto"] == codigo),
                                                None,
                                            )
                                            if item_existente:
                                                nueva_cant = item_existente["cantidad"] + int(cant)
                                                if nueva_cant > stock:
                                                    st.session_state["toast_msg"]  = f"⚠️ Alcanzaste el límite de stock ({stock} ud.)"
                                                    st.session_state["toast_icon"] = "🚫"
                                                else:
                                                    st.session_state["toast_msg"]  = f"🔄 Cantidad de '{nombre}' actualizada en el carrito"
                                                    st.session_state["toast_icon"] = "🛒"
                                                    item_existente["cantidad"] = nueva_cant
                                                    item_existente["subtotal"] = nueva_cant * precio
                                            else:
                                                st.session_state.carrito.append({
                                                    "codigo_producto": codigo,
                                                    "producto":        nombre,
                                                    "cantidad":        int(cant),
                                                    "precio_unitario": precio,
                                                    "subtotal":        precio * int(cant),
                                                })
                                                st.session_state["toast_msg"]  = f"¡'{nombre}' agregado al carrito!"
                                                st.session_state["toast_icon"] = "🛒"
                                            
                                            st.session_state.tab_idx = 0
                                            st.rerun(scope="fragment")
                            else:
                                st.button("🚫 No Disponible", key=f"dis_{idx}_{codigo}",
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
                    datos = indice_productos.get(item["producto"])
                    s_max = _parse_stock(datos[COL_STOCK]) if datos is not None else 999

                    cantidad_guardada = int(item["cantidad"])
                    
                    if cantidad_guardada > s_max:
                        st.warning(f"⚠️ Atención: Has solicitado **{cantidad_guardada} ud.** de **{item['producto']}**, pero el stock actual bajó a **{s_max} ud.** Ajusta la cantidad.")

                    c_info, c_cant, c_del = st.columns([2.5, 1.2, 0.4])
                    with c_info:
                        html_item = render_estructura_item_carrito(
                            nombre=item["producto"],
                            precio_total=item["subtotal"],
                        )
                        st.markdown(f'<div class="item-carrito">{html_item}</div>', unsafe_allow_html=True)
                    with c_cant:
                        st.markdown("<div style='margin-top:15px'></div>", unsafe_allow_html=True)
                        
                        # Usamos el código del producto para la key
                        nueva_cant = st.number_input(
                            "Cant", min_value=1,
                            value=cantidad_guardada, step=1,
                            key=f"cant_cart_{item['codigo_producto']}", label_visibility="collapsed",
                        )
                        if int(nueva_cant) != int(item["cantidad"]):
                            st.session_state.carrito[pos]["cantidad"] = int(nueva_cant)
                            st.session_state.carrito[pos]["subtotal"] = int(nueva_cant) * item["precio_unitario"]
                            st.session_state.tab_idx = 1
                            st.rerun(scope="fragment")
                    with c_del:
                        st.markdown("<div style='margin-top:15px'></div>", unsafe_allow_html=True)
                        if st.button("🗑️", key=f"del_{item['codigo_producto']}", help="Eliminar ítem"):
                            st.session_state.carrito.pop(pos)
                            st.session_state.tab_idx = 1
                            st.rerun(scope="fragment")

                st.markdown("</div>", unsafe_allow_html=True)
                total = sum(float(i["subtotal"]) for i in st.session_state.carrito)
                st.markdown(f"""
                <hr style='border-color:#EBEBEB;margin:1rem 0;'>
                <div class="carrito-total-clon">
                    <span class="label-total">Total:</span>
                    <span class="monto-total">Bs {total:,.2f}</span>
                </div>
                """, unsafe_allow_html=True)

                lista_envio = []
                for item in st.session_state.carrito:
                    fila = indice_productos.get(item["producto"])
                    if fila is None:
                        continue
                    lista_envio.append({
                        "codigo_producto": str(fila[COL_CODIGO]),
                        "producto":        str(item["producto"]),
                        "cantidad":        int(item["cantidad"]),
                        "precio_unitario": float(item["precio_unitario"]),
                        "linea":           str(fila[COL_LINEA]),
                        "descuento":       0,
                        "stock_actual":    _parse_stock(fila[COL_STOCK]),
                        "empresa":         st.session_state.empresa or str(fila[COL_EMP]),
                    })

                if st.button("REALIZAR PEDIDO", type="primary",
                             use_container_width=True, key="btn_enviar"):
                    
                    st.session_state.pop("lista_productos_colision", None)
                    
                    if lista_envio:
                        lista_procesar = [i for i in lista_envio if i["cantidad"] <= i["stock_actual"]]
                        excesos        = [i for i in lista_envio if i["cantidad"] > i["stock_actual"]]
                        
                        if lista_procesar:
                            ejecutar_envio_transaccional(lista_procesar)
                            
                            if excesos:
                                codigos_excedidos = [e["codigo_producto"] for e in excesos]
                                st.session_state.carrito = [
                                    item for item in st.session_state.carrito 
                                    if item["codigo_producto"] in codigos_excedidos
                                ]
                                
                                st.session_state["lista_productos_colision"] = "".join(
                                    f"<li><b>{i['producto']}</b>: pediste <b>{i['cantidad']} ud.</b> "
                                    f"pero el stock bajó a <b>{i['stock_actual']} ud.</b></li>"
                                    for i in excesos
                                )
                                st.session_state["alerta_tipo"] = "parcial"
                                st.session_state["toast_msg"]  = "✅ Pedido procesado parcialmente"
                                st.session_state["toast_icon"] = "⚠️"
                            else:
                                pass # ejecutar_envio_transaccional maneja la limpieza si todo fue exitoso
                                
                            st.rerun(scope="fragment")
                            
                        else:
                            st.session_state["lista_productos_colision"] = "".join(
                                f"<li><b>{i['producto']}</b>: pediste <b>{i['cantidad']} ud.</b> "
                                f"pero el stock bajó a <b>{i['stock_actual']} ud.</b></li>"
                                for i in excesos
                            )
                            st.session_state["alerta_tipo"] = "total"
                            st.rerun(scope="fragment")

                if "lista_productos_colision" in st.session_state:
                    es_parcial = st.session_state.get("alerta_tipo") == "parcial"
                    
                    titulo = "⚠️ Pedido procesado parcialmente" if es_parcial else "🚫 No se pudo procesar tu pedido"
                    color_borde = "#FFB020" if es_parcial else "#FF3B30"
                    mensaje_extra = (
                        "Los demás productos fueron enviados con éxito. Los siguientes artículos "
                        "se quedaron en tu carrito porque superaron el stock disponible:"
                    ) if es_parcial else (
                        "Ninguno de los artículos pudo procesarse por falta de existencias:"
                    )
                    
                    st.markdown(f"""
                    <div class="alerta-stock-container" style="border-left-color: {color_borde};">
                        <div class="alerta-stock-titulo">{titulo}</div>
                        <div style="font-size: 0.9rem; margin-bottom: 8px;">{mensaje_extra}</div>
                        <ul class="alerta-stock-lista">{st.session_state["lista_productos_colision"]}</ul>
                        <div class="alerta-stock-sugerencia">
                            💡 <b>Sugerencia:</b> Ajusta la cantidad de los productos restantes para poder enviarlos.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        # ══════════════════════════════════════════════════════════════════════
        # TAB 2 — HISTORIAL: acordeón por fecha, sin imágenes
        # ══════════════════════════════════════════════════════════════════════
        elif st.session_state.tab_idx == 2:
            st.markdown('<div class="section-title">📋 Mis Pedidos</div>', unsafe_allow_html=True)

            df_hist = cargar_historial(st.session_state.cod_emp)

            if df_hist is None or df_hist.empty:
                st.info("No se registran transacciones previas en su cuenta.")
            else:
                col_monto = next(
                    (c for c in ("Precio Unitario", "Monto Uni") if c in df_hist.columns),
                    None,
                )

                df_h = df_hist.copy()
                df_h["_fecha_obj"] = df_h.get("Fecha Registro", pd.Series(dtype=str)).apply(
                    lambda v: _parsear_fecha(str(v))
                )
                df_h = df_h.sort_values("_fecha_obj", ascending=False, na_position="last")

                fechas_unicas = df_h["_fecha_obj"].dropna().unique()

                total_productos = len(df_h)
                total_bs = 0.0
                if col_monto:
                    for _, r in df_h.iterrows():
                        try:
                            p = float(r[col_monto]) if pd.notna(r[col_monto]) else 0.0
                            q = int(r.get("Cantidad", 0))
                            total_bs += p * q
                        except Exception:
                            pass

                st.markdown(f"""
                <div style="background:#F8F9FF;border-radius:10px;padding:0.8rem 1.1rem;
                            margin-bottom:1rem;display:flex;gap:2rem;flex-wrap:wrap;">
                    <div>
                        <div style="font-size:0.7rem;color:#888;text-transform:uppercase;
                                    letter-spacing:1px;font-weight:600;">Total pedidos</div>
                        <div style="font-size:1.4rem;font-weight:700;color:#1A1A2E;">
                            {total_productos} productos
                        </div>
                    </div>
                    <div>
                        <div style="font-size:0.7rem;color:#888;text-transform:uppercase;
                                    letter-spacing:1px;font-weight:600;">Monto total</div>
                        <div style="font-size:1.4rem;font-weight:700;color:#E63946;">
                            Bs {total_bs:,.2f}
                        </div>
                    </div>
                    <div>
                        <div style="font-size:0.7rem;color:#888;text-transform:uppercase;
                                    letter-spacing:1px;font-weight:600;">Días con pedidos</div>
                        <div style="font-size:1.4rem;font-weight:700;color:#1A1A2E;">
                            {len(fechas_unicas)}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                for fecha_obj in fechas_unicas:
                    df_dia = df_h[df_h["_fecha_obj"] == fecha_obj]

                    n_prods   = len(df_dia)
                    total_dia = 0.0
                    if col_monto:
                        for _, r in df_dia.iterrows():
                            try:
                                p = float(r[col_monto]) if pd.notna(r[col_monto]) else 0.0
                                q = int(r.get("Cantidad", 0))
                                total_dia += p * q
                            except Exception:
                                pass

                    etiqueta  = _etiqueta_relativa(fecha_obj)
                    fecha_fmt = fecha_obj.strftime("%d/%m/%Y")
                    es_primero = (fecha_obj == fechas_unicas[0])

                    label_exp = (
                        f"📅 {etiqueta}  —  {fecha_fmt}"
                        f"   ·   {n_prods} producto{'s' if n_prods != 1 else ''}"
                        f"   ·   Bs {total_dia:,.2f}"
                    )

                    with st.expander(label_exp, expanded=es_primero):
                        h1, h2, h3, h4 = st.columns([3.5, 1, 1.3, 1.3])
                        h1.markdown("**Producto**")
                        h2.markdown("**Cant.**")
                        h3.markdown("**P. Unit.**")
                        h4.markdown("**Subtotal**")
                        st.markdown(
                            "<hr style='margin:0.3rem 0 0.5rem;border-color:#E8E8E8;'>",
                            unsafe_allow_html=True,
                        )

                        for _, row in df_dia.iterrows():
                            nombre_p = str(row.get("Nombre Producto", "N/A"))
                            cantidad = int(row.get("Cantidad", 0))
                            precio_u = 0.0
                            if col_monto and pd.notna(row.get(col_monto)):
                                try:
                                    precio_u = float(row[col_monto])
                                except Exception:
                                    precio_u = 0.0
                            subtotal = precio_u * cantidad

                            c1, c2, c3, c4 = st.columns([3.5, 1, 1.3, 1.3])
                            c1.markdown(f"<span style='font-size:0.87rem'>{nombre_p}</span>", unsafe_allow_html=True)
                            c2.markdown(f"<span style='font-size:0.87rem;color:#555'>{cantidad} ud.</span>", unsafe_allow_html=True)
                            c3.markdown(f"<span style='font-size:0.87rem;color:#555'>Bs {precio_u:,.2f}</span>", unsafe_allow_html=True)
                            c4.markdown(f"<span style='font-size:0.9rem;font-weight:700;color:#E63946'>Bs {subtotal:,.2f}</span>", unsafe_allow_html=True)
                            st.markdown(
                                "<hr style='margin:0.25rem 0;border-color:#F4F4F4;'>",
                                unsafe_allow_html=True,
                            )

                        st.markdown(
                            f"<div style='text-align:right;padding-top:0.3rem;"
                            f"font-size:0.9rem;color:#888;'>"
                            f"Total del día: "
                            f"<strong style='color:#1A1A2E;font-size:1rem;'>Bs {total_dia:,.2f}</strong>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

        # ── Toast pendiente ───────────────────────────────────────────────────
        if st.session_state.get("toast_msg"):
            st.toast(st.session_state["toast_msg"], icon=st.session_state.get("toast_icon", "🛒"))
            st.session_state["toast_msg"]  = None
            st.session_state["toast_icon"] = None

    render_pedido()

    # ── CERRAR SESIÓN ─────────────────────────────────────────────────────────
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        for k in ["logged_in", "cod_emp", "nom_emp", "empresa", "regional", "carrito", "tab_idx"]:
            st.session_state[k] = False if k == "logged_in" else ([] if k == "carrito" else (0 if k == "tab_idx" else None))
        for extra in ["lista_productos_colision", "lanzar_toast_exito", "toast_msg", "toast_icon"]:
            st.session_state.pop(extra, None)
        st.rerun()