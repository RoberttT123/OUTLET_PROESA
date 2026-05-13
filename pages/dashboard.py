import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from src.nav import render_nav

st.set_page_config(page_title="Dashboard de Pedidos", layout="wide", page_icon="📊")

PATH_PEDIDOS_XLSX = "data/consolidado_pedidos.xlsx"
PATH_PEDIDOS_JSON = "data/pedidos_empleados.json"
PATH_INV = "data/inventario_maestro.xlsx"

# ── Verificaciones ──────────────────────────────────────────────────────────
if not os.path.exists(PATH_INV):
    st.error("⚠️ Inventario no disponible")
    st.stop()

df_inv = pd.read_excel(PATH_INV)
render_nav(active_page='dashboard', inventario_df=df_inv)

st.title("📊 Dashboard de Pedidos")
st.write("Vista consolidada: pedidos manuales + pedidos de empleados")

# ── Cargar datos ────────────────────────────────────────────────────────────
# Pedidos manuales (Excel)
pedidos_manuales = pd.DataFrame()
if os.path.exists(PATH_PEDIDOS_XLSX):
    pedidos_manuales = pd.read_excel(PATH_PEDIDOS_XLSX)
    pedidos_manuales['fuente'] = 'Manual (Trade Marketing)'

# Pedidos de empleados (JSON)
pedidos_empleados = []
if os.path.exists(PATH_PEDIDOS_JSON):
    try:
        with open(PATH_PEDIDOS_JSON, "r", encoding="utf-8") as f:
            pedidos_json = json.load(f)
            # Convertir a DataFrame
            for pedido in pedidos_json:
                for item in pedido['items']:
                    pedidos_empleados.append({
                        'Fecha Registro': pedido['fecha'],
                        'Código Empleado': pedido['cod_emp'],
                        'Nombre Empleado': pedido['nom_emp'],
                        'Código Producto': item['codigo'],
                        'Nombre Producto': item['producto'],
                        'Cantidad': item['cantidad'],
                        'Monto Uni': item['precio'],
                        'Empresa': 'PROESA',
                        'fuente': 'Empleado (Self-Service)',
                        'pedido_id': pedido['id'],
                        'estado': pedido.get('estado', 'Pendiente')
                    })
    except:
        pass

if pedidos_empleados:
    df_empleados = pd.DataFrame(pedidos_empleados)
else:
    df_empleados = pd.DataFrame()

# ── Consolidar ──────────────────────────────────────────────────────────────
if not pedidos_manuales.empty and not df_empleados.empty:
    # Alinear columnas
    cols_comunes = ['Código Empleado', 'Nombre Empleado', 'Código Producto', 
                    'Nombre Producto', 'Cantidad', 'Monto Uni', 'Fecha Registro', 'fuente']
    pedidos_manuales['estado'] = 'Registrado'
    pedidos_manuales['pedido_id'] = pedidos_manuales.index.astype(str)
    
    df_consolidado = pd.concat([
        pedidos_manuales[cols_comunes + ['estado', 'pedido_id']],
        df_empleados[cols_comunes + ['estado', 'pedido_id']]
    ], ignore_index=True)
elif not pedidos_manuales.empty:
    df_consolidado = pedidos_manuales.copy()
elif not df_empleados.empty:
    df_consolidado = df_empleados.copy()
else:
    df_consolidado = pd.DataFrame()

# ── Métricas ────────────────────────────────────────────────────────────────
if not df_consolidado.empty:
    col1, col2, col3, col4 = st.columns(4)
    
    total_registros = len(df_consolidado)
    total_unidades = int(df_consolidado['Cantidad'].sum()) if 'Cantidad' in df_consolidado.columns else 0
    total_monto = df_consolidado['Monto Uni'].mul(df_consolidado['Cantidad']).sum() if 'Monto Uni' in df_consolidado.columns else 0
    
    manuales = len(df_consolidado[df_consolidado['fuente'] == 'Manual (Trade Marketing)']) if 'fuente' in df_consolidado.columns else 0
    empleados = len(df_consolidado[df_consolidado['fuente'] == 'Empleado (Self-Service)']) if 'fuente' in df_consolidado.columns else 0
    
    col1.metric("📋 Total Registros", total_registros)
    col2.metric("📦 Total Unidades", f"{total_unidades:,}")
    col3.metric("💰 Monto Total", f"Bs {total_monto:,.2f}")
    col4.metric("👥 Manuales vs Empleados", f"{manuales} vs {empleados}")

    st.markdown("---")

    # ── Filtros ─────────────────────────────────────────────────────────────
    col_filtro1, col_filtro2, col_filtro3 = st.columns(3)
    
    with col_filtro1:
        fuentes = st.multiselect(
            "Filtrar por fuente:",
            options=df_consolidado['fuente'].unique() if 'fuente' in df_consolidado.columns else [],
            default=df_consolidado['fuente'].unique() if 'fuente' in df_consolidado.columns else []
        )
    
    with col_filtro2:
        estados = st.multiselect(
            "Filtrar por estado:",
            options=df_consolidado['estado'].unique() if 'estado' in df_consolidado.columns else [],
            default=df_consolidado['estado'].unique() if 'estado' in df_consolidado.columns else []
        )
    
    with col_filtro3:
        busqueda = st.text_input("Buscar producto o empleado:")

    # Aplicar filtros
    df_filtrado = df_consolidado.copy()
    
    if fuentes:
        df_filtrado = df_filtrado[df_filtrado['fuente'].isin(fuentes)]
    
    if estados:
        df_filtrado = df_filtrado[df_filtrado['estado'].isin(estados)]
    
    if busqueda:
        df_filtrado = df_filtrado[
            (df_filtrado['Nombre Producto'].str.contains(busqueda, case=False, na=False)) |
            (df_filtrado['Nombre Empleado'].str.contains(busqueda, case=False, na=False))
        ]

    # ── Tabla ───────────────────────────────────────────────────────────────
    st.markdown("### 📋 Detalle de Pedidos")
    st.dataframe(df_filtrado, use_container_width=True, height=500)

    # ── Exportar ────────────────────────────────────────────────────────────
    st.markdown("---")
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        csv = df_consolidado.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 Descargar CSV (Consolidado)",
            data=csv,
            file_name=f"Pedidos_Consolidado_{datetime.now().strftime('%d_%m_%Y')}.csv",
            mime="text/csv"
        )
    
    with col_exp2:
        # Exportar a Excel
        with pd.ExcelWriter(f"temp_export.xlsx", engine='openpyxl') as writer:
            df_consolidado.to_excel(writer, sheet_name="Todos los Pedidos", index=False)
        
        with open(f"temp_export.xlsx", "rb") as f:
            st.download_button(
                label="📥 Descargar Excel (Consolidado)",
                data=f.read(),
                file_name=f"Pedidos_Consolidado_{datetime.now().strftime('%d_%m_%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

else:
    st.info("No hay pedidos registrados aún.")