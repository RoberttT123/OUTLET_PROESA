import pandas as pd
import os
import streamlit as st

PATH_PEDIDOS = "data/consolidado_pedidos.xlsx"
PATH_INV_SISTEMA = "data/inventario_maestro.xlsx"
PATH_EMPLEADOS = "data/Empleado.xlsx"

def limpiar_formato_latino(valor):
    """
    Convierte formatos como '1.933,50' (str) a 1933.50 (float)
    Punto = Miles, Coma = Decimales
    """
    if isinstance(valor, str):
        valor = valor.replace('.', '')
        valor = valor.replace(',', '.')
    return valor

def cargar_inventario(archivo):
    """Lee el Excel inicial y limpia los formatos de número."""
    df = pd.read_excel(archivo, sheet_name="Inventario")    
    df.iloc[:, 3] = df.iloc[:, 3].apply(limpiar_formato_latino)
    df.iloc[:, 3] = pd.to_numeric(df.iloc[:, 3], errors='coerce').fillna(0)
    
    df.iloc[:, 4] = df.iloc[:, 4].apply(limpiar_formato_latino)
    df.iloc[:, 4] = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(0)
    
    return df

def guardar_inventario_maestro(df):
    """Crea el archivo permanente de inventario en la carpeta data."""
    if not os.path.exists("data"):
        os.makedirs("data")
    df.to_excel(PATH_INV_SISTEMA, index=False)

def guardar_pedido(df_nuevo):
    """Anexa un nuevo pedido al archivo consolidado."""
    if not os.path.exists(PATH_PEDIDOS):
        if not os.path.exists("data"):
            os.makedirs("data")
        df_nuevo.to_excel(PATH_PEDIDOS, index=False)
    else:
        existente = pd.read_excel(PATH_PEDIDOS)
        consolidado = pd.concat([existente, df_nuevo], ignore_index=True)
        consolidado.to_excel(PATH_PEDIDOS, index=False)

def actualizar_stock_inventario(codigo_producto, cantidad_restar):
    """
    Resta stock del inventario maestro. 
    Si cantidad_restar es negativa, suma stock (devolución).
    """
    df = pd.read_excel(PATH_INV_SISTEMA)
    df.loc[df.iloc[:, 1] == codigo_producto, df.columns[3]] -= cantidad_restar
    df.to_excel(PATH_INV_SISTEMA, index=False)


# ── NUEVAS FUNCIONES PARA GESTIÓN DE EMPLEADOS ──────────────────────────────

@st.cache_data(ttl=3600)
def cargar_empleados():
    """
    Carga el listado de empleados desde Empleado.xlsx
    Estructura: Empresa | Cod_Empleado | Persona | Regional
    """
    try:
        if not os.path.exists(PATH_EMPLEADOS):
            st.warning(f"⚠️ Archivo '{PATH_EMPLEADOS}' no encontrado.")
            return pd.DataFrame()
        
        df_emp = pd.read_excel(PATH_EMPLEADOS, sheet_name="Empleados")
        return df_emp
    except Exception as e:
        st.error(f"Error cargando empleados: {e}")
        return pd.DataFrame()


def obtener_datos_empleado(cod_empleado):
    """
    Busca un empleado por código y devuelve sus datos.
    
    Retorna:
        dict con claves: 'nombre', 'empresa', 'regional', 'encontrado'
        Si no encuentra: {'encontrado': False}
    """
    df_emp = cargar_empleados()
    
    if df_emp.empty:
        return {'encontrado': False, 'error': 'No se pudo cargar la lista de empleados'}
    
    # Buscar por código (flexible con espacios)
    df_emp['Cod_Empleado'] = df_emp['Cod_Empleado'].astype(str).str.strip().str.upper()
    
    empleado = df_emp[df_emp['Cod_Empleado'] == cod_empleado.strip().upper()]
    
    if empleado.empty:
        return {'encontrado': False}
    
    fila = empleado.iloc[0]
    
    return {
        'encontrado': True,
        'nombre': str(fila['Persona']).title() if 'Persona' in fila.index else '',
        'empresa': str(fila['Empresa']) if 'Empresa' in fila.index else '',
        'regional': str(fila['Regional']) if 'Regional' in fila.index else ''
    }


def validar_empleado(cod_empleado):
    """
    Valida si un código de empleado existe.
    
    Retorna: True si existe, False si no
    """
    datos = obtener_datos_empleado(cod_empleado)
    return datos.get('encontrado', False)