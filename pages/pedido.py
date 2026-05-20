# -*- coding: utf-8 -*-
"""
SISTEMA DE CONTROL DE PEDIDOS - OUTLET PROESA
----------------------------------------------------------------
Archivo Principal de la Aplicación: pedido.py
Lógica de Negocio, Gestión de Estado Multitendencia y Fragmentación de UI.

Arquitectura: Model-View-Controller adaptado para Streamlit.
Enfoque de Renderizado: Mobile-First mediante Pestañas (Tabs) e interfaces Grid.
Última Revisión Corporativa: Mayo 2026
"""

import streamlit as st
import pandas as pd
import base64
from datetime import datetime

# ==============================================================================
# 1. CONFIGURACIÓN CORPORATIVA
# ==============================================================================
try:
    from config import (
        INVENTARIO_SHEET_URL,
        INVENTARIO_HOJA_NAME,
        PEDIDOS_SHEET_URL,
        PEDIDOS_HOJA_NAME
    )
except ImportError as imp_err:
    st.error("❌ Error Crítico: Archivo `config.py` no encontrado.")
    st.stop()
except Exception as ex_cfg:
    st.error(f"❌ Error inesperado al leer `config.py`: {str(ex_cfg)}")
    st.stop()

# ==============================================================================
# 2. IMPORTACIÓN DE SERVICIOS
# ==============================================================================
try:
    from src.sheets import (
        obtener_inventario_sheets,
        obtener_pedidos_empleado_sheets,
        guardar_pedido_sheets,
        actualizar_stock_batch_sheets,
        verificar_stock_disponible,
    )
    from src.database import obtener_datos_empleado, validar_empleado
    from src.componentes import cargar_estilos_css, render_tarjeta_producto
except ImportError as imp_src:
    st.error("❌ Error de Dependencias Internas: No se pudieron cargar los módulos de `src/`.")
    st.code(str(imp_src))
    st.stop()

# ==============================================================================
# 3. CONFIGURACIÓN DE PÁGINA Y ESTILOS
# ==============================================================================
try:
    st.set_page_config(
        page_title="Mi Pedido - Outlet PROESA",
        layout="wide",
        page_icon="🛒",
        initial_sidebar_state="collapsed"
    )
except Exception:
    pass

try:
    cargar_estilos_css()
except Exception as ex_css:
    st.warning(f"⚠️ No se pudieron aplicar los estilos: {str(ex_css)}")

# ==============================================================================
# 4. LOGO
# ==============================================================================
@st.cache_data(show_spinner=False)
def get_logo_b64(path: str = "assets/logo_proesa.png") -> str:
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None

# ==============================================================================
# 5. SESSION STATE
# ==============================================================================
defaults = {
    'logged_in':   False,
    'cod_emp':     None,
    'nom_emp':     None,
    'empresa':     None,
    'regional':    None,
    'carrito':     [],
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==============================================================================
# 6. HELPERS DE PARSEO ROBUSTO
#    Con numericise_ignore=['all'] en sheets.py, Stock y Precio llegan
#    como strings. Estas funciones los convierten de forma segura.
# ==============================================================================
def _parse_stock(valor) -> int:
    """Convierte cualquier representación de stock a int. Retorna 0 si falla."""
    try:
        return int(float(str(valor).strip().replace(',', '')))
    except (ValueError, TypeError):
        return 0

def _parse_precio(valor) -> float:
    """Convierte cualquier representación de precio a float. Retorna 0.0 si falla."""
    try:
        return float(str(valor).strip().replace(',', '.'))
    except (ValueError, TypeError):
        return 0.0

# ==============================================================================
# 7. CARGA DE INVENTARIO E ÍNDICE
# ==============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def ejecutar_carga_inventario_segura() -> pd.DataFrame:
    try:
        df = obtener_inventario_sheets(INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME)
        return df if df is not None and not df.empty else pd.DataFrame()
    except Exception as e:
        st.error(f"Falló la conexión con el inventario: {str(e)}")
        return pd.DataFrame()

df_inv = ejecutar_carga_inventario_segura()

if df_inv.empty:
    st.error("❌ Catálogo no disponible.")
    st.info("Verifique su conexión o los permisos de la URL en config.py.")
    st.stop()

@st.cache_data(show_spinner=False)
def construir_indice_maestro(shape_key: str) -> dict:
    col = "Nombre Producto" if "Nombre Producto" in df_inv.columns else df_inv.columns[2]
    return {
        str(fila[col]).strip(): fila
        for _, fila in df_inv.iterrows()
        if pd.notna(fila[col])
    }

indice_productos = construir_indice_maestro(str(df_inv.shape))


# ==============================================================================
# ══════════════════════════════════════════════════════════════════════════════
# PANTALLA 1: LOGIN
# ══════════════════════════════════════════════════════════════════════════════
# ==============================================================================
if not st.session_state.logged_in:
    logo_codificado = get_logo_b64()

    st.markdown(f"""
    <div class="hero-login">
        {f'<img src="data:image/png;base64,{logo_codificado}" style="height:210px;width:auto;object-fit:contain;margin-top:-20px;margin-bottom:0px;">' if logo_codificado else ''}
        <h1 style="margin-top:0;">Outlet PROESA</h1>
        <p style="margin-bottom:0;">Sistema de Pedidos Internos para Empleados</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("contenedor_login_seguro"):
        st.subheader("🔑 Acceso al Sistema")
        codigo_ingresado = st.text_input(
            "Código Identificador de Empleado",
            placeholder="Ej: E0200491",
            help="Consulte con su supervisor si desconoce su código interno."
        ).upper().strip()

        st.markdown("<br>", unsafe_allow_html=True)

        if st.form_submit_button("🚀 Validar Credenciales", use_container_width=True):
            if codigo_ingresado:
                with st.spinner("Consultando registros de personal..."):
                    try:
                        datos = obtener_datos_empleado(codigo_ingresado)
                        if datos and datos.get('encontrado'):
                            st.session_state.logged_in = True
                            st.session_state.cod_emp   = str(codigo_ingresado)
                            st.session_state.nom_emp   = str(datos.get('nombre', 'Empleado'))
                            st.session_state.empresa   = str(datos.get('empresa', 'N/A'))
                            st.session_state.regional  = str(datos.get('regional', 'N/A'))
                            st.success("✅ Acceso autorizado.")
                            st.rerun()
                        else:
                            st.error(f"❌ Código '{codigo_ingresado}' no registrado.")
                    except Exception as e:
                        st.error(f"Error durante la verificación: {str(e)}")
            else:
                st.error("⚠️ Ingresa un código de empleado para continuar.")


# ==============================================================================
# ══════════════════════════════════════════════════════════════════════════════
# PANTALLA 2: SISTEMA DE PEDIDOS (TABS)
# ══════════════════════════════════════════════════════════════════════════════
# ==============================================================================
else:
    logo_codificado   = get_logo_b64()
    html_logo         = f'<img src="data:image/png;base64,{logo_codificado}" style="height:100px;object-fit:contain;">' if logo_codificado else "🛒"

    st.markdown(f"""
    <div class="page-header">
        {html_logo}
        <div>
            <h2>Tu Pedido</h2>
            <p>👤 {st.session_state.nom_emp} · 🔖 {st.session_state.cod_emp} · 🏢 {st.session_state.empresa or 'PROESA'}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    @st.cache_data(ttl=120, show_spinner=False)
    def ejecutar_carga_historial_segura(cod: str) -> pd.DataFrame:
        try:
            df = obtener_pedidos_empleado_sheets(cod, PEDIDOS_SHEET_URL, PEDIDOS_HOJA_NAME)
            return df if df is not None else pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    # ──────────────────────────────────────────────────────────────────────────
    # FRAGMENT: Catálogo + Carrito + Historial
    # ──────────────────────────────────────────────────────────────────────────
    @st.fragment
    def render_catalogo_y_carrito():
        # ── Pestañas nativas + JS para mantener la pestaña activa ────────────
        # st.tabs se ve igual en desktop y mobile.
        # El JS auto-cliquea la pestaña correcta después de cada rerun,
        # evitando que siempre vuelva al índice 0 al editar/eliminar del carrito.
        if 'tab_activa' not in st.session_state:
            st.session_state.tab_activa = 'catalogo'

        total_uds     = sum(int(i.get('cantidad', 0)) for i in st.session_state.carrito)
        label_carrito = f"🛒 Carrito ({total_uds})" if total_uds > 0 else "🛒 Carrito"

        tab_catalogo, tab_carrito, tab_historial = st.tabs([
            "📦 Catálogo", label_carrito, "📋 Mis Pedidos"
        ])

        # JS: auto-seleccionar la pestaña guardada en session_state
        _tab_idx = {'catalogo': 0, 'carrito': 1, 'historial': 2}
        _idx = _tab_idx.get(st.session_state.tab_activa, 0)
        st.components.v1.html(f"""
        <script>
        setTimeout(function() {{
            var tabs = window.parent.document.querySelectorAll('button[role="tab"]');
            if (tabs && tabs.length > {_idx}) {{
                tabs[{_idx}].click();
            }}
        }}, 80);
        </script>
        """, height=0)

        # Columnas del inventario
        col_nombre = "Nombre Producto" if "Nombre Producto" in df_inv.columns else df_inv.columns[2]
        col_codigo = "Código Producto" if "Código Producto" in df_inv.columns else df_inv.columns[1]
        col_stock  = "Stock"           if "Stock"           in df_inv.columns else df_inv.columns[3]
        col_precio = "Precio Unitario" if "Precio Unitario" in df_inv.columns else df_inv.columns[4]
        col_imagen = "Imagen"          if "Imagen"          in df_inv.columns else None

        # ── TAB 1: CATÁLOGO ───────────────────────────────────────────────────
        with tab_catalogo:
            if True:
                st.markdown('<div class="section-title">📦 Productos en Promoción</div>', unsafe_allow_html=True)

            filtro = st.text_input(
                "Filtrar catálogo en tiempo real:",
                placeholder="Palabras clave, marcas o códigos SKU...",
                key="control_busqueda_inventario"
            )

            if filtro:
                expr = str(filtro).strip()
                mascara = (
                    df_inv[col_nombre].astype(str).str.contains(expr, case=False, na=False) |
                    df_inv[col_codigo].astype(str).str.strip().str.contains(expr, case=False, na=False)
                )
                df_vista = df_inv[mascara].head(8)
            else:
                df_vista = df_inv.head(6)

            if df_vista.empty:
                st.info("🔍 Ningún artículo coincide con los criterios ingresados.")
            else:
                st.caption(f"Visualizando {len(df_vista)} ítems disponibles.")

                for fila_bloque in range(0, len(df_vista), 2):
                    cols_grid = st.columns(2)

                    for sub_col in range(2):
                        idx = fila_bloque + sub_col
                        if idx >= len(df_vista):
                            break

                        reg = df_vista.iloc[idx]

                        # ── PARSEO ROBUSTO ─────────────────────────────────────
                        # Con numericise_ignore=['all'], Stock y Precio son strings.
                        # _parse_stock y _parse_precio los convierten de forma segura.
                        try:
                            stock  = _parse_stock(reg[col_stock])
                            precio = _parse_precio(reg[col_precio])
                            codigo = str(reg[col_codigo]).strip()
                            nombre = str(reg[col_nombre]).strip()
                            imagen = reg[col_imagen] if col_imagen and pd.notna(reg[col_imagen]) else ""
                        except Exception as e:
                            # Mostrar aviso en vez de saltar silenciosamente
                            st.caption(f"⚠️ Error al cargar producto en fila {idx}: {e}")
                            continue

                        if stock <= 0:
                            badge    = '<span class="stock-out">❌ Agotado en Planta</span>'
                            bloqueado = True
                        elif stock <= 5:
                            badge    = f'<span class="stock-warn">⚠️ Últimas {stock} ud.</span>'
                            bloqueado = False
                        else:
                            badge    = f'<span class="stock-ok">✅ {stock} Disponibles</span>'
                            bloqueado = False

                        with cols_grid[sub_col]:
                            render_tarjeta_producto(
                                codigo=codigo,
                                nombre=nombre,
                                precio=precio,
                                stock_badge=badge,
                                url_foto=imagen
                            )

                            if not bloqueado:
                                c_num, c_btn = st.columns([1, 1.3])
                                with c_num:
                                    cantidad = st.number_input(
                                        "Cantidad",
                                        min_value=1,
                                        max_value=max(stock, 1),
                                        value=1,
                                        step=1,
                                        key=f"input_num_{codigo}",
                                        label_visibility="collapsed"
                                    )
                                with c_btn:
                                    if st.button("➕ Solicitar", key=f"btn_add_{codigo}", use_container_width=True):
                                        st.session_state.carrito.append({
                                            "codigo_producto": codigo,
                                            "producto":        nombre,
                                            "cantidad":        int(cantidad),
                                            "precio_unitario": precio,
                                            "subtotal":        precio * int(cantidad)
                                        })
                                        st.rerun(scope="fragment")
                            else:
                                st.button("🚫 No Disponible", key=f"btn_dis_{codigo}", disabled=True, use_container_width=True)

                            st.markdown("<br>", unsafe_allow_html=True)

        # ── TAB 2: CARRITO ────────────────────────────────────────────────────
        with tab_carrito:
            if True:
                st.markdown('<div class="section-title">🛒 Carrito de Compras</div>', unsafe_allow_html=True)

            if st.session_state.carrito:
                from src.componentes import render_estructura_item_carrito

                st.markdown('<div class="contenedor-carrito">', unsafe_allow_html=True)

                for pos, item in enumerate(st.session_state.carrito):
                    datos_prod   = indice_productos.get(item['producto'])
                    # ── PARSEO ROBUSTO también en el carrito ──────────────────
                    stock_max    = _parse_stock(datos_prod[col_stock]) if datos_prod is not None else 999
                    foto         = datos_prod[col_imagen] if datos_prod is not None and col_imagen and col_imagen in datos_prod else ""

                    c_render, c_cnt, c_del = st.columns([2.5, 1.2, 0.4])

                    with c_render:
                        html_item = render_estructura_item_carrito(
                            nombre=item['producto'],
                            precio_total=item['subtotal'],
                            url_foto=foto
                        )
                        st.markdown(f'<div class="item-carrito">{html_item}</div>', unsafe_allow_html=True)

                    with c_cnt:
                        st.markdown("<div style='margin-top:15px'></div>", unsafe_allow_html=True)
                        nueva_cant = st.number_input(
                            "Cant",
                            min_value=1,
                            max_value=stock_max,
                            value=int(item['cantidad']),
                            step=1,
                            key=f"cant_carrito_{pos}",
                            label_visibility="collapsed"
                        )
                        if int(nueva_cant) != int(item['cantidad']):
                            st.session_state.carrito[pos]['cantidad'] = int(nueva_cant)
                            st.session_state.carrito[pos]['subtotal'] = int(nueva_cant) * item['precio_unitario']
                            st.session_state.tab_activa = 'carrito'  # quedarse en carrito
                            st.rerun(scope="fragment")

                    with c_del:
                        st.markdown("<div style='margin-top:15px'></div>", unsafe_allow_html=True)
                        if st.button("🗑️", key=f"del_{pos}", help="Eliminar"):
                            st.session_state.carrito.pop(pos)
                            st.session_state.tab_activa = 'carrito'  # quedarse en carrito
                            st.rerun(scope="fragment")

                st.markdown('</div>', unsafe_allow_html=True)

                total = sum(float(i['subtotal']) for i in st.session_state.carrito)
                st.markdown(f"""
                <hr style='border-color:#EBEBEB;margin:1rem 0;'>
                <div class="carrito-total-clon">
                    <span class="label-total">Total:</span>
                    <span class="monto-total">Bs {total:,.2f}</span>
                </div>
                """, unsafe_allow_html=True)

                if st.button("REALIZAR PEDIDO", type="primary", use_container_width=True, key="btn_enviar_pedido"):
                    ejecutar_procesamiento_pedido_global()
            else:
                st.info("Tu carrito está vacío. Agrega productos desde la pestaña Catálogo.")

        # ── TAB 3: HISTORIAL ──────────────────────────────────────────────────
        with tab_historial:
            if True:
                st.markdown('<div class="section-title">📋 Registro Histórico de Compras</div>', unsafe_allow_html=True)

            df_hist = ejecutar_carga_historial_segura(st.session_state.cod_emp)

            if df_hist is not None and not df_hist.empty:
                st.caption("Últimos artículos solicitados (orden cronológico descendente):")
                for _, pedido in df_hist.tail(10).iloc[::-1].iterrows():
                    st.markdown(
                        f"📦 **{pedido.get('Nombre Producto','Artículo')}**<br>"
                        f"🔢 **{pedido.get('Cantidad', 0)} unidades**<br>"
                        f"📅 <small style='color:#777'>{pedido.get('Fecha Registro','N/A')}</small>",
                        unsafe_allow_html=True
                    )
                    st.markdown("<hr style='margin:0.4rem 0;border-style:dashed;border-color:#E0E0E0;'>", unsafe_allow_html=True)
            else:
                st.info("No se registran transacciones previas en su cuenta.")

    # ──────────────────────────────────────────────────────────────────────────
    # FUNCIÓN DE ENVÍO (fuera del fragment para poder hacer st.rerun() global)
    # ──────────────────────────────────────────────────────────────────────────
    def ejecutar_procesamiento_pedido_global():
        if not st.session_state.carrito:
            st.error("No se puede procesar un carrito vacío.")
            return

        col_stock  = "Stock"           if "Stock"           in df_inv.columns else df_inv.columns[3]
        col_linea  = "Línea"           if "Línea"           in df_inv.columns else df_inv.columns[0]
        col_codigo = "Código Producto" if "Código Producto" in df_inv.columns else df_inv.columns[1]
        col_emp    = "Empresa"         if "Empresa"         in df_inv.columns else df_inv.columns[5]

        # Preparar items
        items = []
        for item in st.session_state.carrito:
            fila = indice_productos.get(item['producto'])
            if fila is None:
                continue
            items.append({
                "codigo_producto": str(fila[col_codigo]),
                "producto":        str(item['producto']),
                "cantidad":        int(item['cantidad']),
                "precio_unitario": float(item['precio_unitario']),
                "linea":           str(fila[col_linea]),
                "descuento":       0,
                # ── PARSEO ROBUSTO al preparar el envío ───────────────────────
                "stock_actual":    _parse_stock(fila[col_stock]),
                "empresa":         st.session_state.empresa or str(fila[col_emp])
            })

        with st.status("Procesando tu pedido...", expanded=True) as estado:
            try:
                # ── VERIFICACIÓN ANTI-COLISIÓN ─────────────────────────────────
                # Lee el stock fresco de Sheets (sin caché) y verifica que
                # ningún producto haya sido agotado por otro empleado simultáneo.
                st.write("🔍 Verificando disponibilidad en tiempo real...")
                sin_stock = verificar_stock_disponible(
                    items=[{"codigo_producto": i["codigo_producto"], "cantidad_a_restar": i["cantidad"]} for i in items],
                    url_sheet=INVENTARIO_SHEET_URL,
                    hoja=INVENTARIO_HOJA_NAME
                )

                if sin_stock:
                    estado.update(label="⚠️ Stock insuficiente en algunos productos.", state="error")
                    for prod in sin_stock:
                        st.error(
                            f"❌ **{prod['producto']}** — "
                            f"Pediste {prod['pedido']} ud. pero solo quedan {prod['disponible']} disponibles."
                        )
                    st.warning("Por favor ajusta las cantidades en el carrito y vuelve a intentarlo.")
                    return

                # ── GUARDAR PEDIDO ─────────────────────────────────────────────
                st.write("📝 Registrando pedido...")
                guardado = guardar_pedido_sheets(
                    st.session_state.cod_emp,
                    st.session_state.nom_emp,
                    items,
                    PEDIDOS_SHEET_URL,
                    PEDIDOS_HOJA_NAME
                )

                if guardado:
                    # ── ACTUALIZAR STOCK (batch) ───────────────────────────────
                    st.write("📦 Ajustando niveles de inventario...")
                    actualizar_stock_batch_sheets(
                        items=[{"codigo_producto": i["codigo_producto"], "cantidad_a_restar": i["cantidad"]} for i in items],
                        url_sheet=INVENTARIO_SHEET_URL,
                        hoja=INVENTARIO_HOJA_NAME
                    )

                    st.session_state.carrito = []
                    st.cache_data.clear()
                    estado.update(label="✅ ¡Pedido procesado con éxito!", state="complete")
                    st.toast("🎉 ¡Tu pedido fue enviado con éxito!", icon="🛒")
                    st.rerun()
                else:
                    estado.update(label="❌ Falló el registro del pedido.", state="error")
                    st.error("Google Sheets rechazó la inserción. Intenta de nuevo.")

            except Exception as e:
                estado.update(label="❌ Error inesperado.", state="error")
                st.error(f"Detalle del error: {str(e)}")

    # Lanzar fragment
    render_catalogo_y_carrito()

    # ── CERRAR SESIÓN ─────────────────────────────────────────────────────────
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("🚪 Cerrar Sesión", use_container_width=True, help="Limpia las credenciales de la sesión"):
        for k in ['logged_in', 'cod_emp', 'nom_emp', 'empresa', 'regional', 'carrito']:
            st.session_state[k] = False if k == 'logged_in' else ([] if k == 'carrito' else None)
        st.rerun()