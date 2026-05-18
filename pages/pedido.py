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
import sys
from datetime import datetime

# ==============================================================================
# 1. VALIDACIÓN EN CASCADA Y CARGA DE CONFIGURACIÓN CORPORATIVA
# ==============================================================================
try:
    from config import (
        INVENTARIO_SHEET_URL, 
        INVENTARIO_HOJA_NAME, 
        PEDIDOS_SHEET_URL, 
        PEDIDOS_HOJA_NAME
    )
    CONFIG_LOADED = True
except ImportError as imp_err:
    CONFIG_LOADED = False
    st.error(f"❌ Error Crítico de Infraestructura: Archivo `config.py` no fue localizado en la raíz.")
    st.info("Por favor, asegúrese de que el archivo de configuración exista and contenga las credenciales de Google Sheets.")
    st.stop()
except Exception as ex_cfg:
    CONFIG_LOADED = False
    st.error(f"❌ Error inesperado al leer `config.py`: {str(ex_cfg)}")
    st.stop()

# ==============================================================================
# 2. IMPORTACIÓN DE SERVICIOS API Y ADAPTADORES DE DATOS
# ==============================================================================
try:
    from src.sheets import (
        obtener_inventario_sheets,
        obtener_pedidos_empleado_sheets,
        guardar_pedido_sheets,
        actualizar_stock_batch_sheets,
    )
    from src.database import obtener_datos_empleado, validar_empleado
    from src.componentes import cargar_estilos_css, render_tarjeta_producto
except ImportError as imp_src:
    st.error(f"❌ Error de Dependencias Internas: No se pudieron cargar los módulos del directorio `src/`.")
    st.code(str(imp_src))
    st.stop()

# ==============================================================================
# 3. CONFIGURACIÓN E INICIALIZACIÓN DEL ENTORNO WEB
# ==============================================================================
try:
    st.set_page_config(
        page_title="Mi Pedido - Outlet PROESA",
        layout="wide",
        page_icon="🛒",
        initial_sidebar_state="collapsed"
    )
except Exception:
    # Captura fallos si st.set_page_config no es la primera llamada nativa
    pass

# Inyección de la hoja de estilos CSS unificada desde el módulo de componentes
try:
    cargar_estilos_css()
except Exception as ex_css:
    st.warning(f"⚠️ No se pudieron aplicar los estilos personalizados: {str(ex_css)}")

# ==============================================================================
# 4. GESTIÓN DE RECURSOS ESTÁTICOS (LOGO EMBEDDED)
# ==============================================================================
@st.cache_data(show_spinner=False)
def get_logo_b64(path: str = "assets/logo_proesa.png") -> str:
    """
    Lee una imagen local en binario y la convierte a una cadena Base64.
    Previene re-lecturas de disco redundantes optimizando la velocidad de rerun.
    """
    try:
        with open(path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
            return encoded_string
    except FileNotFoundError:
        return None
    except Exception:
        return None

# ==============================================================================
# 5. CONTROL DE CICLO DE VIDA Y ESTADO INTERNO (SESSION STATE)
# ==============================================================================
# Se definen las variables necesarias para mantener el estado a lo largo de la sesión.
estructura_estado_por_defecto = {
    'logged_in': False,
    'cod_emp': None,
    'nom_emp': None,
    'empresa': None,
    'regional': None,
    'carrito': [],
    'ultimo_rerun': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

for propiedad, valor_inicial in estructura_estado_por_defecto.items():
    if propiedad not in st.session_state:
        st.session_state[propiedad] = valor_inicial

# ==============================================================================
# 6. CAPA DE ABASTECIMIENTO DE DATOS E INDEXACIÓN OPTIMIZADA
# ==============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def ejecutar_carga_inventario_segura() -> pd.DataFrame:
    """
    Extrae los registros actualizados de la base de datos en Sheets.
    Implementa un Time-To-Live (TTL) de 5 minutos para balancear frescura de stock
    y consumo de cuotas de la API de Google.
    """
    try:
        dataframe_resultado = obtener_inventario_sheets(INVENTARIO_SHEET_URL, INVENTARIO_HOJA_NAME)
        if dataframe_resultado is None or dataframe_resultado.empty:
            return pd.DataFrame()
        return dataframe_resultado
    except Exception as ex_sheets:
        st.error(f"Falló la conexión con la base de datos de inventario: {str(ex_sheets)}")
        return pd.DataFrame()

# Orquestación de carga
df_inv = ejecutar_carga_inventario_segura()

if df_inv.empty:
    st.error("❌ Catálogo no disponible: La base de datos retornó un conjunto vacío o inaccesible.")
    st.info("Verifique su conexión a internet o los permisos de la URL en config.py.")
    st.stop()

@st.cache_data(show_spinner=False)
def construir_indice_maestro_productos(dimension_dataframe_hash: str) -> dict:
    """
    Genera una tabla Hash en memoria {Nombre_Producto -> Fila_Atributos}.
    Permite búsquedas y validaciones O(1) cuando el usuario manipula cantidades
    dentro del carrito de compras, anulanado búsquedas secuenciales en DataFrames.
    """
    try:
        dataframe_trabajo = df_inv.copy()
        
        # Mapeo dinámico de nombres de columnas para mitigar variaciones del archivo origen
        col_clave_nombre = "Nombre Producto" if "Nombre Producto" in dataframe_trabajo.columns else dataframe_trabajo.columns[2]
        
        indice_construido = {}
        for idx, fila in dataframe_trabajo.iterrows():
            nombre_llave = fila[col_clave_nombre]
            if pd.notna(nombre_llave):
                # Guardamos la serie de la fila mapeada con el nombre del producto como clave
                indice_construido[str(nombre_llave).strip()] = fila
                
        return indice_construido
    except Exception as ex_index:
        st.error(f"Fallo crítico al indexar catálogo: {str(ex_index)}")
        return {}

# El shape del dataframe actúa como trigger de actualización del caché del índice
indice_productos = construir_indice_maestro_productos(str(df_inv.shape))


# ==============================================================================
# ═════════════════════════════════════════════════════════════════════════════
# PANTALLA 1: ARQUITECTURA DE AUTENTICACIÓN Y CONTROL DE ACCESO
# ═════════════════════════════════════════════════════════════════════════════
# ==============================================================================
if not st.session_state.logged_in:
    logo_codificado = get_logo_b64()

    # Renderizado del bloque estructural Hero con diseño adaptativo inline
    st.markdown(f"""
    <div class="hero-login">
        {f'<img src="data:image/png;base64,{logo_codificado}" style="height:210px;width:auto;object-fit:contain;margin-top:-20px;margin-bottom:0px;">' if logo_codificado else ''}
        <h1 style="margin-top:0; font-family:\'DM Sans\', sans-serif;">Outlet PROESA</h1>
        <p style="margin-bottom:0; font-family:\'DM Sans\', sans-serif;">Sistema de Pedidos Internos para Empleados</p>
    </div>
    """, unsafe_allow_html=True)

    # Formulario estricto de captura para mitigar re-ejecuciones por pulsaciones de teclas involuntarias
    with st.form("contenedor_login_seguro"):
        st.subheader("🔑 Acceso al Sistema")
        codigo_ingresado = st.text_input(
            "Código Identificador de Empleado", 
            placeholder="Ej: E0200491",
            help="Consulte con su supervisor si desconoce su código interno."
        ).upper().strip()

        linea_espacio = st.markdown("<br>", unsafe_allow_html=True)

        if st.form_submit_button("🚀 Validar Credenciales", use_container_width=True):
            if codigo_ingresado:
                with st.spinner("Consultando registros de personal..."):
                    try:
                        datos_empleado = obtener_datos_empleado(codigo_ingresado)
                        
                        if datos_empleado and datos_empleado.get('encontrado'):
                            # Mutación controlada del Session State para autenticación exitosa
                            st.session_state.logged_in = True
                            st.session_state.cod_emp   = str(codigo_ingresado)
                            st.session_state.nom_emp   = str(datos_empleado.get('nombre', 'Empleado Sin Nombre'))
                            st.session_state.empresa   = str(datos_empleado.get('empresa', 'N/A'))
                            st.session_state.regional  = str(datos_empleado.get('regional', 'N/A'))
                            st.session_state.ultimo_rerun = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            st.success("✅ Acceso autorizado.")
                            st.rerun()
                        else:
                            st.error(f"❌ Código '{codigo_ingresado}' no registrado en la base de datos de personal.")
                    except Exception as ex_auth:
                        st.error(f"Error técnico durante la verificación de identidad: {str(ex_auth)}")
            else:
                st.error("⚠️ Entrada inválida: Debe ingresar un código de empleado para continuar.")


# ==============================================================================
# ═════════════════════════════════════════════════════════════════════════════
# PANTALLA 2: ENTORNO TRANSACCIONAL (SISTEMA DE PESTAÑAS TRIPLE - MOBILE FIRST)
# ═════════════════════════════════════════════════════════════════════════════
# ==============================================================================
else:
    logo_codificado = get_logo_b64()
    html_presentacion_logo = f'<img src="data:image/png;base64,{logo_codificado}" style="height:100px;object-fit:contain;">' if logo_codificado else "🛒"

    # Encabezado corporativo persistente (Fuera del fragmento de re-renderizado)
    st.markdown(f"""
    <div class="page-header">
        {html_presentacion_logo}
        <div>
            <h2 style="font-family:\'DM Sans\', sans-serif;">Tu Pedido</h2>
            <p style="font-family:\'DM Sans\', sans-serif;">👤 {st.session_state.nom_emp} · 🔖 {st.session_state.cod_emp} · 🏢 {st.session_state.empresa or 'PROESA'}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Servicio de aislamiento para la extracción de registros históricos
    @st.cache_data(ttl=120, show_spinner=False)
    def ejecutar_carga_historial_segura(codigo_trabajador: str) -> pd.DataFrame:
        """
        Extracción defensiva del historial de compras directo desde la API de Sheets.
        """
        try:
            df_historico = obtener_pedidos_empleado_sheets(codigo_trabajador, PEDIDOS_SHEET_URL, PEDIDOS_HOJA_NAME)
            if df_historico is None:
                return pd.DataFrame()
            return df_historico
        except Exception as ex_hist:
            st.warning(f"No se pudo sincronizar el historial transaccional: {str(ex_hist)}")
            return pd.DataFrame()

    # ──────────────────────────────────────────────────────────────────────────
    # FRAGMENT: Núcleo Transaccional Asíncrono Localizado
    # Evita la recarga costosa del Header HTML y Logo en cada adición de producto.
    # ──────────────────────────────────────────────────────────────────────────
    @st.fragment
    def render_catalogo_y_carrito():
        # Cálculo de métricas en tiempo real para retroalimentación en la pestaña
        total_unidades_carrito = sum(int(item.get('cantidad', 0)) for item in st.session_state.carrito)
        etiqueta_dinamica_carrito = f"🛒 Carrito ({total_unidades_carrito})" if total_unidades_carrito > 0 else "🛒 Carrito"
        
        # Despliegue de pestañas nativas unificadas para el bloqueo del scroll
        tab_catalogo, tab_carrito, tab_historial = st.tabs([
            "📦 Catálogo", 
            etiqueta_dinamica_carrito,
            "📋 Mis Pedidos"
        ])

        # Extracción segura de nombres de columnas del inventario
        col_nombre = "Nombre Producto" if "Nombre Producto" in df_inv.columns else df_inv.columns[2]
        col_codigo = "Código Producto" if "Código Producto" in df_inv.columns else df_inv.columns[1]
        col_stock  = "Stock"           if "Stock"           in df_inv.columns else df_inv.columns[3]
        col_precio = "Precio Unitario" if "Precio Unitario" in df_inv.columns else df_inv.columns[4]
        col_imagen = "Imagen"          if "Imagen"          in df_inv.columns else None

        # ── SUB-MÓDULO: PESTAÑA 1 - CATÁLOGO DINÁMICO EN TARJETAS ────────────
        with tab_catalogo:
            st.markdown('<div class="section-title">📦 Productos en Promoción</div>', unsafe_allow_html=True)

            filtro_busqueda = st.text_input(
                "Filtrar catálogo en tiempo real:",
                placeholder="Escriba palabras clave, marcas o códigos SKU...",
                key="control_busqueda_inventario"
            )

            # Algoritmo de filtrado vectorizado basado en máscaras lógicas booleanas
            if filtro_busqueda:
                expresion_busqueda = str(filtro_busqueda).strip()
                mascara_coincidencia = (
                    df_inv[col_nombre].str.contains(expresion_busqueda, case=False, na=False) |
                    df_inv[col_codigo].astype(str).str.contains(expresion_busqueda, case=False, na=False)
                )
                df_visualizacion = df_inv[mascara_coincidencia].head(8)
            else:
                df_visualizacion = df_inv.head(6)

            if df_visualizacion.empty:
                st.info("🔍 Ningún artículo del catálogo coincide con los criterios ingresados.")
            else:
                st.caption(f"Visualizando {len(df_visualizacion)} ítems disponibles para solicitud inmediata.")

                # Construcción geométrica de la cuadrícula de tarjetas (2 columnas por fila)
                for fila_bloque in range(0, len(df_visualizacion), 2):
                    columnas_grid = st.columns(2)
                    
                    for sub_columna in range(2):
                        indice_calculado = fila_bloque + sub_columna
                        if indice_calculado >= len(df_visualizacion):
                            break # Ruptura controlada si la lista es impar
                        
                        registro_producto = df_visualizacion.iloc[indice_calculado]
                        
                        try:
                            unidades_stock = int(float(registro_producto[col_stock]))
                            costo_unitario = float(registro_producto[col_precio])
                            sku_producto   = str(registro_producto[col_codigo])
                            nombre_completo = str(registro_producto[col_nombre]).strip()
                            
                            # Resolución de URL de imagen con fallback defensivo
                            enlace_imagen = registro_producto[col_imagen] if col_imagen and pd.notna(registro_producto[col_imagen]) else ""
                        except Exception:
                            continue

                        # Evaluación lógica del estado físico del stock
                        if unidades_stock <= 0:
                            bloque_badge_html = '<span class="stock-out">❌ Agotado en Planta</span>'
                            bloqueo_interaccion = True
                        elif unidades_stock <= 5:
                            bloque_badge_html = f'<span class="stock-warn">⚠️ Últimas {unidades_stock} ud.</span>'
                            bloqueo_interaccion = False
                        else:
                            bloque_badge_html = f'<span class="stock-ok">✅ {unidades_stock} Disponibles</span>'
                            bloqueo_interaccion = False

                        with columnas_grid[sub_columna]:
                            # Invocación de la interfaz HTML de la tarjeta desde componentes.py
                            render_tarjeta_producto(
                                codigo=sku_producto, 
                                nombre=nombre_completo, 
                                precio=costo_unitario, 
                                stock_badge=bloque_badge_html, 
                                url_foto=enlace_imagen
                            )
                            
                            # Renderizado de controladores nativos interactivos de Streamlit acoplados por debajo
                            if not bloqueo_interaccion:
                                cols_controles = st.columns([1, 1.3])
                                with cols_controles[0]:
                                    cantidad_seleccionada = st.number_input(
                                        "Cantidad", 
                                        min_value=1, 
                                        max_value=max(unidades_stock, 1),
                                        value=1, 
                                        step=1,
                                        key=f"input_num_{sku_producto}", 
                                        label_visibility="collapsed"
                                    )
                                with cols_controles[1]:
                                    if st.button("➕ Solicitar", key=f"btn_add_{sku_producto}", use_container_width=True):
                                        # Estructuración de datos del ítem transaccional
                                        st.session_state.carrito.append({
                                            "codigo_producto": sku_producto,
                                            "producto": nombre_completo,
                                            "cantidad": int(cantidad_seleccionada),
                                            "precio_unitario": costo_unitario,
                                            "subtotal": costo_unitario * int(cantidad_seleccionada)
                                        })
                                        st.rerun(scope="fragment")
                            else:
                                st.button("🚫 No Disponible", key=f"btn_disabled_{sku_producto}", disabled=True, use_container_width=True)
                            
                            st.markdown("<br>", unsafe_allow_html=True)

        # ── SUB-MÓDULO: PESTAÑA 2 - GESTIÓN DEL CARRITO TRANSACCIONAL ────────
        # ── SUB-MÓDULO: PESTAÑA 2 - EL CARRITO DE COMPRAS CLONADO ─────────────
        with tab_carrito:
            st.markdown('<div class="section-title">🛒 Carrito de Compras</div>', unsafe_allow_html=True)

            if st.session_state.carrito:
                # Importamos la subfunción estética de componentes
                from src.componentes import render_estructura_item_carrito

                # Envolvemos todos los ítems en el contenedor blanco de la captura
                st.markdown('<div class="contenedor-carrito">', unsafe_allow_html=True)
                
                for indice_posicion, item_carrito in enumerate(st.session_state.carrito):
                    datos_maestros_prod = indice_productos.get(item_carrito['producto'])
                    techo_stock_real = int(float(datos_maestros_prod[col_stock])) if datos_maestros_prod is not None else 999
                    enlace_foto = datos_maestros_prod[col_imagen] if datos_maestros_prod is not None and col_imagen in datos_maestros_prod else ""

                    # Layout de 3 columnas para encajar los controles interactivos de Streamlit sobre el diseño CSS
                    c_render, c_controles, c_eliminar = st.columns([2.5, 1.2, 0.4])

                    with c_render:
                        # Generamos la estructura base (Imagen, Título y Precio a la derecha)
                        html_esqueleto = render_estructura_item_carrito(
                            nombre=item_carrito['producto'],
                            precio_total=item_carrito['subtotal'],
                            url_foto=enlace_foto
                        )
                        st.markdown(f'<div class="item-carrito">{html_esqueleto}</div>', unsafe_allow_html=True)

                    with c_controles:
                        # Selector compacto imitando el "< 1 >" de tu captura
                        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
                        cantidad_modificada = st.number_input(
                            "Cant",
                            min_value=1,
                            max_value=techo_stock_real,
                            value=int(item_carrito['cantidad']),
                            step=1,
                            key=f"modificar_cant_key_{indice_posicion}",
                            label_visibility="collapsed"
                        )
                        
                        if int(cantidad_modificada) != int(item_carrito['cantidad']):
                            st.session_state.carrito[indice_posicion]['cantidad'] = int(cantidad_modificada)
                            st.session_state.carrito[indice_posicion]['subtotal'] = int(cantidad_modificada) * item_carrito['precio_unitario']
                            st.rerun(scope="fragment")

                    with c_eliminar:
                        # Botón basurero alineado a la derecha
                        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
                        if st.button("🗑️", key=f"btn_quitar_pos_{indice_posicion}", help="Eliminar producto"):
                            st.session_state.carrito.pop(indice_posicion)
                            st.rerun(scope="fragment")
                
                st.markdown('</div>', unsafe_allow_html=True) # Cierre del contenedor blanco

                # Cálculo consolidado final
                monto_total_pedido = sum(float(item['subtotal']) for item in st.session_state.carrito)
                
                # Render del total como en la imagen inferior
                st.markdown(f"""
                <hr style='border-color: #EBEBEB; margin: 1rem 0;'>
                <div class="carrito-total-clon">
                    <span class="label-total">Total:</span>
                    <span class="monto-total">Bs {monto_total_pedido:,.2f}</span>
                </div>
                """, unsafe_allow_html=True)

                if st.button("INICIAR COMPRE / ENVIAR PEDIDO", type="primary", use_container_width=True, key="btn_enviar_pedido_final_tabs"):
                    ejecutar_procesamiento_pedido_global()
            else:
                st.info("Tu carrito está vacío. Agrega productos desde la pestaña de Catálogo.")
        # ── SUB-MÓDULO: PESTAÑA 3 - HISTORIAL EXCLUSIVO DE PEDIDOS ANTERIORES ──
        with tab_historial:
            st.markdown('<div class="section-title">📋 Registro Histórico de Compras</div>', unsafe_allow_html=True)
            
            df_pedidos_pasados = ejecutar_carga_historial_segura(st.session_state.cod_emp)

            if df_pedidos_pasados is not None and not df_pedidos_pasados.empty:
                st.caption("Últimos artículos solicitados por su cuenta de empleado (Orden cronológico descendente):")
                
                # Inversión de índices nativos de Pandas para ubicar el último registro arriba del todo
                df_historico_invertido = df_pedidos_pasados.tail(10).iloc[::-1]
                
                for fila_id, datos_pedido_historico in df_historico_invertido.iterrows():
                    with st.container():
                        st.markdown(
                            f"📦 **{datos_pedido_historico.get('Nombre Producto', 'Artículo Corporativo')}**<br>"
                            f"🔢 Volumen solicitado: **{datos_pedido_historico.get('Cantidad', 0)} unidades**<br>"
                            f"📅 <small style='color:#777;'>Registrado en fecha: {datos_pedido_historico.get('Fecha Registro', 'N/A')}</small>", 
                            unsafe_allow_html=True
                        )
                        st.markdown("<hr style='margin:0.4rem 0; border-style: dashed; border-color:#E0E0E0;'>", unsafe_allow_html=True)
            else:
                st.info("No se registran transacciones previas asociadas a su código de empleado.")

    # ──────────────────────────────────────────────────────────────────────────
    # FUNCIÓN INTERNA TRANSACCIONAL DE DISPARO GLOBAL
    # Ejecutada fuera del fragmento para posibilitar limpiezas globales de caché y globos
    # ──────────────────────────────────────────────────────────────────────────
    def ejecutar_procesamiento_pedido_global():
        """
        Extrae los elementos actuales en el carrito, valida correspondencias de 
        columnas e inicia la persistencia secuencial e inyección Batch a Sheets.
        """
        if not st.session_state.carrito:
            st.error("No se puede procesar un carrito de compras vacío.")
            return

        items_preparados_hojas = []
        for item_actual in st.session_state.carrito:
            datos_matriz_fila = indice_productos.get(item_actual['producto'])
            if datos_matriz_fila is None:
                continue
            
            # Extracción robusta de índices alternativos para evitar quiebres de estructuras por Sheets
            idx_linea   = "Línea"          if "Línea"          in datos_matriz_fila.index else datos_matriz_fila.index[0]
            idx_codigo2 = "Código Producto" if "Código Producto" in datos_matriz_fila.index else datos_matriz_fila.index[1]
            idx_stock2  = "Stock"           if "Stock"          in datos_matriz_fila.index else datos_matriz_fila.index[3]
            idx_empresa = "Empresa"         if "Empresa"        in datos_matriz_fila.index else datos_matriz_fila.index[5]

            items_preparados_hojas.append({
                "codigo_producto": str(datos_matriz_fila[idx_codigo2]),
                "producto":        str(item_actual['producto']),
                "cantidad":        int(item_actual['cantidad']),
                "precio_unitario": float(item_actual['precio_unitario']),
                "linea":           str(datos_matriz_fila[idx_linea]),
                "descuento":       0,
                "stock_actual":    int(float(datos_matriz_fila[idx_stock2])),
                "empresa":         st.session_state.empresa or str(datos_matriz_fila[idx_empresa])
            })

        # Despliegue de estado de carga visual interactiva
        with st.status("Estableciendo conexión y procesando orden...", expanded=True) as componente_estado:
            try:
                st.write("📝 Escribiendo registro de transacciones en la nube...")
                resultado_guardado = guardar_pedido_sheets(
                    st.session_state.cod_emp,
                    st.session_state.nom_emp,
                    items_preparados_hojas,
                    PEDIDOS_SHEET_URL,
                    PEDIDOS_HOJA_NAME
                )
                if resultado_guardado:
                    st.write("📦 Ajustando niveles de inventario físico (Procesamiento Batch)...")
                    
                    # Ejecución del lote unificado para mitigación de sobrecarga HTTP
                    actualizar_stock_batch_sheets(
                        items=[{
                            "codigo_producto":  str(it["codigo_producto"]),
                            "cantidad_a_restar": int(it["cantidad"])
                        } for it in items_preparados_hojas],
                        url_sheet=INVENTARIO_SHEET_URL,
                        hoja=INVENTARIO_HOJA_NAME
                    )

                    # Limpieza integral de estructuras temporales post-venta exitosa
                    st.session_state.carrito = []
                    st.cache_data.clear() # Invalidación de caché para obligar recargas de stock fresco
                    
                    componente_estado.update(label="✅ Transacción Procesada Satisfactoriamente", state="complete")
                    
                    # 🚀 NOTIFICACIONES DE ÉXITO AÑADIDAS:
                    # 1. Notificación flotante móvil en la esquina inferior derecha
                    st.toast("🎉 ¡Tu pedido ha sido enviado con éxito!", icon="🛒")
                    
                    # 2. Mensaje de confirmación visual fijo sobre la interfaz
                    st.success("🎉 ¡Pedido registrado con éxito! El inventario ha sido actualizado de forma segura.")
                    
                    # Lanzamiento de globos festivos
                    st.balloons()
                    
                    # ⏳ Pausa de 1.5 segundos para que el usuario asimile el mensaje antes de borrar la pantalla
                    import time
                    time.sleep(1.5)
                    
                    st.rerun()
                else:
                    componente_estado.update(label="❌ Denegado: Falló la escritura de la orden.", state="error")
                    st.error("El servidor de Google Sheets rechazó la inserción del registro. Reintente.")
            except Exception as ex_proc:
                componente_estado.update(label="❌ Falla Crítica Operacional", state="error")
                st.error(f"Detalle técnico de la falla: {str(ex_proc)}")

    # Lanzamiento del componente estructurado
    render_catalogo_y_carrito()

    # ── PANEL DE CIERRE DE SESIÓN SEGURO DE LA APLICACIÓN ───────────────────
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("🚪 Finalizar Jornada / Cerrar Sesión", use_container_width=True, help="Limpia las credenciales temporales del navegador"):
        with st.spinner("Removiendo tokens de identidad temporales..."):
            for propiedad_estado in ['logged_in', 'cod_emp', 'nom_emp', 'empresa', 'regional', 'carrito']:
                if propiedad_estado == 'logged_in':
                    st.session_state[propiedad_estado] = False
                elif propiedad_estado == 'carrito':
                    st.session_state[propiedad_estado] = []
                else:
                    st.session_state[propiedad_estado] = None
            st.rerun()