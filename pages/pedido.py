# -*- coding: utf-8 -*-
"""
MÓDULO DE INTERFAZ DE USUARIO Y GESTIÓN DE PEDIDOS - OUTLET PROESA
----------------------------------------------------------------
Controla el flujo de login de empleados, despliegue del catálogo de productos,
gestión dinámica del carrito de compras con control de concurrencia in situ,
y persistencia segura y atómica de pedidos en Google Sheets.

Desarrollado para: PROYECTO_OUTLET
Última actualización: Mayo 2026
"""

import streamlit as st
import pandas as pd
import base64
from datetime import datetime

# ==============================================================================
# 1. CONFIGURACIÓN EXTERNA DE HOJAS DE CÁLCULO
# ==============================================================================
try:
    from config import (
        INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME,
        PEDIDOS_SHEET_URL,    PEDIDOS_HOJA_NAME
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
    st.error("❌ Error cargando los módulos esenciales desde el directorio `src/`.")
    st.code(str(e))
    st.stop()

# Configuración de página nativa de Streamlit
try:
    st.set_page_config(
        page_title="Mi Pedido - Outlet PROESA",
        layout="wide",
        page_icon="🛒",
        initial_sidebar_state="collapsed"
    )
except Exception:
    pass

# Aplicación de la hoja de estilos global del proyecto
try:
    cargar_estilos_css()
except Exception as e:
    st.warning(f"⚠️ Estilos CSS base no aplicados: {e}")

# Inyección de estilos CSS extras para emular pestañas nativas usando st.radio horizontal
st.markdown("""
<style>
/* ── Hacer que st.radio horizontal parezca exactamente st.tabs ── */
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

/* Configuración del estado activo de la pestaña */
div[data-testid="stRadio"] label[data-checked="true"] {
    color: #1A1A2E !important;
    font-weight: 600 !important;
    border-bottom: 3px solid #E63946 !important;
}

/* Ocultación de los elementos de radio nativos del navegador */
div[data-testid="stRadio"] [data-testid="stWidgetLabel"] { display: none !important; }
div[data-testid="stRadio"] span[data-testid="stMarkdownContainer"] p { margin: 0; }
div[data-testid="stRadio"] div[data-baseweb="radio"] > div:first-child { display: none !important; }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# 2. PROCESAMIENTO MULTIMEDIA (LOGO EMPRESARIAL)
# ==============================================================================
@st.cache_data(show_spinner=False)
def get_logo_b64(path="assets/logo_proesa.png"):
    """Codifica la imagen del logo local a Base64 para inyección HTML segura."""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None


# ==============================================================================
# 3. INICIALIZACIÓN DEL SESSION STATE DEL USUARIO
# ==============================================================================
defaults = {
    'logged_in': False, 
    'cod_emp': None, 
    'nom_emp': None,
    'empresa': None,    
    'regional': None, 
    'carrito': [],
    'tab_idx': 0,       # Índices: 0 = Catálogo, 1 = Carrito, 2 = Historial
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ==============================================================================
# 4. FUNCIONES DE PARSEO ROBUSTO (Compatibilidad estricta con Sheets stringified)
# ==============================================================================
def _parse_stock(v) -> int:
    """Parsea de forma segura valores de stock evitando rupturas por comas o flotantes."""
    try:
        return max(0, int(float(str(v).strip().replace(',', ''))))
    except Exception:
        return 0

def _parse_precio(v) -> float:
    """Parsea de forma segura valores monetarios de productos."""
    try:
        return float(str(v).strip().replace(',', '.'))
    except Exception:
        return 0.0


# ==============================================================================
# 5. CARGA DE DATOS CENTRALIZADA E INDEXACIÓN
# ==============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def cargar_inventario():
    """Descarga de forma segura el DataFrame de inventario actual desde la API."""
    try:
        df = obtener_inventario_sheets(INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME)
        return df if df is not None and not df.empty else pd.DataFrame()
    except Exception as e:
        st.error(f"Error cargando inventario: {e}")
        return pd.DataFrame()

@st.cache_data(show_spinner=False)
def construir_indice(shape_key):
    """Construye un mapa de búsqueda en memoria basado en el Nombre del Producto."""
    col = "Nombre Producto" if "Nombre Producto" in df_inv.columns else df_inv.columns[2]
    return {str(r[col]).strip(): r for _, r in df_inv.iterrows() if pd.notna(r[col])}


# Ejecución de la carga de datos inicial
df_inv = cargar_inventario()
if df_inv.empty:
    st.error("❌ Catálogo de inventario no disponible. Revisa la conectividad de red o config.py.")
    st.stop()

# Generación del índice rápido de consulta
indice_productos = construir_indice(str(df_inv.shape))

# Mapeo dinámico y posicional de columnas del inventario
COL_NOMBRE = "Nombre Producto" if "Nombre Producto" in df_inv.columns else df_inv.columns[2]
COL_CODIGO = "Código Producto" if "Código Producto" in df_inv.columns else df_inv.columns[1]
COL_STOCK  = "Stock"           if "Stock"           in df_inv.columns else df_inv.columns[3]
COL_PRECIO = "Precio Unitario" if "Precio Unitario" in df_inv.columns else df_inv.columns[4]
COL_LINEA  = "Línea"           if "Línea"           in df_inv.columns else df_inv.columns[0]
COL_EMP    = "Empresa"         if "Empresa"         in df_inv.columns else df_inv.columns[5]
COL_IMAGEN = "Imagen"          if "Imagen"          in df_inv.columns else None


# ==============================================================================
# PANTALLA 1: PORTAL DE ACCESO Y LOGIN DE EMPLEADOS
# ==============================================================================
if not st.session_state.logged_in:
    logo = get_logo_b64()
    html_logo = f'<img src="data:image/png;base64,{logo}" style="height:210px;width:auto;object-fit:contain;margin-top:-20px;">' if logo else ''
    
    st.markdown(f"""
    <div class="hero-login">
        {html_logo}
        <h1 style="margin-top:0;">Outlet PROESA</h1>
        <p style="margin-bottom:0;">Sistema de Pedidos Internos para Empleados</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        st.subheader("🔑 Acceso al Sistema")
        cod = st.text_input(
            "Código de Empleado", placeholder="Ej: E0200491",
            help="Consulte con su supervisor asignado si desconoce su código corporativo o de planilla."
        ).upper().strip()
        st.markdown("<br>", unsafe_allow_html=True)

        if st.form_submit_button("🚀 Validar Credenciales", use_container_width=True):
            if cod:
                with st.spinner("Consultando registros de personal..."):
                    try:
                        datos = obtener_datos_empleado(cod)
                        if datos and datos.get('encontrado'):
                            st.session_state.logged_in = True
                            st.session_state.cod_emp   = cod
                            st.session_state.nom_emp   = datos.get('nombre', 'Empleado')
                            st.session_state.empresa   = datos.get('empresa', 'N/A')
                            st.session_state.regional  = datos.get('regional', 'N/A')
                            st.success("✅ Acceso autorizado.")
                            st.rerun()
                        else:
                            st.error(f"❌ Código '{cod}' no registrado en la base de datos de la empresa.")
                    except Exception as e:
                        st.error(f"Error en verificación: {e}")
            else:
                st.error("⚠️ Por favor, ingresa tu código de empleado para continuar.")


# ==============================================================================
# PANTALLA 2: ENTORNO PRINCIPAL DE PEDIDOS DE COMPRA
# ==============================================================================
else:
    # ── VERIFICACIÓN RE-RUN: Lanzar toast de éxito guardado en memoria antes de dibujar la UI ──
    if "lanzar_toast_exito" in st.session_state and st.session_state["lanzar_toast_exito"]:
        st.toast("🎉 ¡Tu pedido fue enviado con éxito!", icon="🛒")
        del st.session_state["lanzar_toast_exito"]

    logo = get_logo_b64()
    html_header_media = f'<img src="data:image/png;base64,{logo}" style="height:100px;object-fit:contain;">' if logo else "🛒"
    
    st.markdown(f"""
    <div class="page-header">
        {html_header_media}
        <div>
            <h2>Tu Pedido</h2>
            <p>👤 {st.session_state.nom_emp} · 🔖 {st.session_state.cod_emp} · 🏢 {st.session_state.empresa or 'PROESA'}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    @st.cache_data(ttl=120, show_spinner=False)
    def cargar_historial(cod):
        """Carga el historial de compras del empleado directamente desde Sheets."""
        try:
            df = obtener_pedidos_empleado_sheets(cod, PEDIDOS_SHEET_URL, PEDIDOS_HOJA_NAME)
            return df if df is not None else pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    # ── FUNCIÓN TRANSACCIONAL GLOBAL PERFECCIONADA ──
    def ejecutar_envio_transaccional(items):
        """
        Envía de forma segura el lote del pedido a procesar.
        Maneja bloqueos lógicos de concurrencia y despliega notificaciones instantáneas si falla.
        """
        if "mensaje_colision" in st.session_state:
            del st.session_state["mensaje_colision"]

        with st.status("Procesando tu pedido...", expanded=True) as estado:
            try:
                st.write("🔍 Verificando disponibilidad y reservando stock en tiempo real...")
                
                formato_items = [{"codigo_producto": i["codigo_producto"], "cantidad_a_restar": i["cantidad"]} for i in items]
                transaccion = procesar_descuento_stock_seguro(
                    items=formato_items,
                    url_sheet=INVENTARIO_SHEET_URL,
                    hoja=INVENTARIO_HOJA_NAME
                )
                
                # CONTROL DE FRACASO: Concurrencia detectada, otra persona ganó las unidades antes
                if not transaccion["exito"]:
                    estado.update(label="⚠️ Pedido rechazado por falta de stock.", state="error")
                    
                    detalles = []
                    for p in transaccion["sin_stock"]:
                        detalles.append(
                            f"• **{p['producto']}**: Solicitaste {p['pedido']} ud., pero otra persona finalizó su pedido un instante antes y agotó el stock disponible (Stock actual: {p['disponible']} ud.)."
                        )
                    
                    st.session_state["mensaje_colision"] = "\n".join(detalles)
                    
                    # Notificación flotante de error instantánea (No requiere rerun, se renderiza in situ)
                    st.toast("⚠️ Error: No se pudo enviar el pedido. ¡Se agotó el stock!", icon="❌")
                    return False

                # CONTROL DE ÉXITO: El stock ya está apartado en la nube, escribimos el log de auditoría
                st.write("📝 Guardando el registro oficial del pedido...")
                ok = guardar_pedido_sheets(
                    st.session_state.cod_emp, st.session_state.nom_emp,
                    items, PEDIDOS_SHEET_URL, PEDIDOS_HOJA_NAME
                )
                
                if ok:
                    st.session_state.carrito = []
                    st.session_state.tab_idx = 0
                    st.cache_data.clear()
                    
                    # Guardamos la bandera de éxito para que el toast sobreviva de forma limpia al rerun
                    st.session_state["lanzar_toast_exito"] = True
                    estado.update(label="✅ ¡Pedido procesado con éxito!", state="complete")
                    return True
                else:
                    estado.update(label="❌ Error al escribir el registro físico del pedido.", state="error")
                    st.error("El stock fue apartado correctamente pero la fila de control falló. Contacta al administrador.")
                    return False

            except Exception as e:
                estado.update(label="❌ Error inesperado.", state="error")
                st.error(f"Detalle de excepción: {e}")
                return False


    # ──────────────────────────────────────────────────────────────────────────
    # FRAGMENT CENTRAL DE OPERACIONES (CATÁLOGO / CARRITO / HISTORIAL)
    # ──────────────────────────────────────────────────────────────────────────
    @st.fragment
    def render_pedido():
        total_uds = sum(int(i.get('cantidad', 0)) for i in st.session_state.carrito)
        label_c   = f"🛒 Carrito ({total_uds})" if total_uds > 0 else "🛒 Carrito"
        opciones  = ["📦 Catálogo", label_c, "📋 Mis Pedidos"]

        # Control del sistema de pestañas móvil-friendly mediante radio button
        tab_sel = st.radio(
            "tabs_nav",
            opciones,
            index=int(st.session_state.tab_idx),
            horizontal=True,
            label_visibility="collapsed",
            key="radio_tabs_nav"
        )
        st.session_state.tab_idx = opciones.index(tab_sel)

        # ══════════════════════════════════════════════════════════════════════
        # TAB 0 — CATÁLOGO DE PRODUCTOS EN PROMOCIÓN
        # ══════════════════════════════════════════════════════════════════════
        if st.session_state.tab_idx == 0:
            st.markdown('<div class="section-title">📦 Productos en Promoción</div>', unsafe_allow_html=True)

            filtro = st.text_input(
                "Filtrar catálogo:",
                placeholder="Palabras clave, marcas o códigos SKU...",
                key="busqueda_catalogo"
            )

            if filtro:
                expr    = str(filtro).strip()
                mascara = (
                    df_inv[COL_NOMBRE].astype(str).str.contains(expr, case=False, na=False) |
                    df_inv[COL_CODIGO].astype(str).str.strip().str.contains(expr, case=False, na=False)
                )
                df_vista = df_inv[mascara].head(8)
            else:
                df_vista = df_inv.head(6)

            if df_vista.empty:
                st.info("🔍 Ningún artículo coincide con los criterios de búsqueda introducidos.")
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
                            imagen = reg[COL_IMAGEN] if COL_IMAGEN and pd.notna(reg[COL_IMAGEN]) else ""
                        except Exception as e:
                            st.caption(f"⚠️ Error renderizando fila {idx}: {e}")
                            continue

                        # Lógica visual dinámica para Badges de inventario
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
                                precio=precio, stock_badge=badge, url_foto=imagen
                            )
                            if not bloqueado:
                                c_num, c_btn = st.columns([1, 1.3])
                                with c_num:
                                    cant = st.number_input(
                                        "Cant", min_value=1, max_value=max(stock, 1),
                                        value=1, step=1,
                                        key=f"qty_{codigo}", label_visibility="collapsed"
                                    )
                                with c_btn:
                                    if st.button("➕ Solicitar", key=f"add_{codigo}", use_container_width=True):
                                        st.session_state.carrito.append({
                                            "codigo_producto": codigo,
                                            "producto":        nombre,
                                            "cantidad":        int(cant),
                                            "precio_unitario": precio,
                                            "subtotal":        precio * int(cant),
                                        })
                                        st.session_state.tab_idx = 0
                                        st.rerun(scope="fragment")
                            else:
                                st.button("🚫 No Disponible", key=f"dis_{codigo}",
                                          disabled=True, use_container_width=True)
                            st.markdown("<br>", unsafe_allow_html=True)

        # ══════════════════════════════════════════════════════════════════════
        # TAB 1 — CARRITO DE COMPRAS CON ADAPTACIÓN DE STOCK EN CALIENTE
        # ══════════════════════════════════════════════════════════════════════
        elif st.session_state.tab_idx == 1:
            st.markdown('<div class="section-title">🛒 Carrito de Compras</div>', unsafe_allow_html=True)

            # Renderizado de la alerta roja fija arriba en el carrito
            if "mensaje_colision" in st.session_state:
                st.error("### 🚫 No se pudo enviar tu pedido por falta de existencias")
                st.markdown(st.session_state["mensaje_colision"])
                st.info("💡 Sugerencia: Por favor, reduce la cantidad en el selector o remueve el producto agotado para poder procesar el resto de tus artículos.")
                st.markdown("<hr style='border-color:#E63946; margin:1.5rem 0;'>", unsafe_allow_html=True)

            if not st.session_state.carrito:
                st.info("Tu carrito está vacío. Agrega productos desde el Catálogo principal.")
            else:
                from src.componentes import render_estructura_item_carrito
                st.markdown('<div class="contenedor-carrito">', unsafe_allow_html=True)

                for pos, item in enumerate(st.session_state.carrito):
                    datos   = indice_productos.get(item['producto'])
                    s_max   = _parse_stock(datos[COL_STOCK]) if datos is not None else 999
                    foto    = datos[COL_IMAGEN] if datos is not None and COL_IMAGEN and COL_IMAGEN in datos else ""

                    # Adaptación de control de concurrencia visual in-situ
                    cantidad_guardada = int(item['cantidad'])
                    if cantidad_guardada > s_max:
                        cantidad_guardada = max(1, s_max)
                        st.session_state.carrito[pos]['cantidad'] = cantidad_guardada
                        st.session_state.carrito[pos]['subtotal'] = cantidad_guardada * item['precio_unitario']
                        st.warning(f"⚠️ El stock de **{item['producto']}** disminuyó en la base de datos central. Se reajustó automáticamente al máximo disponible actual ({s_max} ud.).")

                    c_info, c_cant, c_del = st.columns([2.5, 1.2, 0.4])

                    with c_info:
                        html_item = render_estructura_item_carrito(
                            nombre=item['producto'],
                            precio_total=item['subtotal'],
                            url_foto=foto
                        )
                        st.markdown(f'<div class="item-carrito">{html_item}</div>', unsafe_allow_html=True)

                    with c_cant:
                        st.markdown("<div style='margin-top:15px'></div>", unsafe_allow_html=True)
                        nueva_cant = st.number_input(
                            "Cant", min_value=1, max_value=max(s_max, 1),
                            value=cantidad_guardada, step=1,
                            key=f"cant_{pos}", label_visibility="collapsed"
                        )
                        if int(nueva_cant) != int(item['cantidad']):
                            st.session_state.carrito[pos]['cantidad'] = int(nueva_cant)
                            st.session_state.carrito[pos]['subtotal'] = int(nueva_cant) * item['precio_unitario']
                            st.session_state.tab_idx = 1
                            st.rerun(scope="fragment")

                    with c_del:
                        st.markdown("<div style='margin-top:15px'></div>", unsafe_allow_html=True)
                        if st.button("🗑️", key=f"del_{pos}", help="Eliminar ítem del carrito"):
                            st.session_state.carrito.pop(pos)
                            st.session_state.tab_idx = 1
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

                # Compilación de la estructura para el envío masivo
                lista_envio = []
                for item in st.session_state.carrito:
                    fila = indice_productos.get(item['producto'])
                    if fila is None:
                        continue
                    lista_envio.append({
                        "codigo_producto": str(fila[COL_CODIGO]),
                        "producto":        str(item['producto']),
                        "cantidad":        int(item['cantidad']),
                        "precio_unitario": float(item['precio_unitario']),
                        "linea":           str(fila[COL_LINEA]),
                        "descuento":       0,
                        "stock_actual":    _parse_stock(fila[COL_STOCK]),
                        "empresa":         st.session_state.empresa or str(fila[COL_EMP])
                    })

                if st.button("REALIZAR PEDIDO", type="primary", use_container_width=True, key="btn_enviar"):
                    if lista_envio:
                        exito = ejecutar_envio_transaccional(lista_envio)
                        if exito:
                            st.rerun()

        # ══════════════════════════════════════════════════════════════════════
        # TAB 2 — HISTORIAL DE COMPRAS REGISTRADAS
        # ══════════════════════════════════════════════════════════════════════
        elif st.session_state.tab_idx == 2:
            st.markdown('<div class="section-title">📋 Registro Histórico de Compras</div>', unsafe_allow_html=True)
            df_hist = cargar_historial(st.session_state.cod_emp)
            if df_hist is not None and not df_hist.empty:
                st.caption("Últimos artículos solicitados (Ordenados de forma cronológica descendente):")
                for _, p in df_hist.tail(10).iloc[::-1].iterrows():
                    st.markdown(
                        f"📦 **{p.get('Nombre Producto','N/A')}**<br>"
                        f"🔢 **{p.get('Cantidad', 0)} unidades**<br>"
                        f"📅 <small style='color:#777'>{p.get('Fecha Registro','N/A')}</small>",
                        unsafe_allow_html=True
                    )
                    st.markdown("<hr style='margin:0.4rem 0;border-style:dashed;border-color:#E0E0E0;'>",
                                unsafe_allow_html=True)
            else:
                st.info("No se registran transacciones previas vinculadas a su cuenta corporativa.")

    # Renderizar el entorno reactivo
    render_pedido()

    # ── CIERRE DE SESIÓN SEGURO ──
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        for k in ['logged_in','cod_emp','nom_emp','empresa','regional','carrito','tab_idx']:
            st.session_state[k] = False if k == 'logged_in' else ([] if k == 'carrito' else (0 if k == 'tab_idx' else None))
        if "mensaje_colision" in st.session_state:
            del st.session_state["mensaje_colision"]
        if "lanzar_toast_exito" in st.session_state:
            del st.session_state["lanzar_toast_exito"]
        st.rerun()