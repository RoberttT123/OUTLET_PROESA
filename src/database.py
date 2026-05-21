import pandas as pd
import os
import streamlit as st

PATH_PEDIDOS = "data/consolidado_pedidos.xlsx"
PATH_INV_SISTEMA = "data/inventario_maestro.xlsx"

# Importar config para Google Sheets
try:
    from config import EMPLEADOS_SHEET_URL, EMPLEADOS_HOJA_NAME
    USING_SHEETS_EMP = True
except ImportError:
    USING_SHEETS_EMP = False

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
    """
    Carga el archivo Excel subido, asegurando que los tipos de datos
    no rompan la estructura interna de Pandas reconstruyendo las series.
    """
    import pandas as pd
    
    # 1. Leer el archivo Excel manteniendo el formato de origen
    df = pd.read_excel(archivo, sheet_name=0)
    
    # Aseguramos que el DataFrame tenga suficientes columnas antes de operar
    if df.shape[1] > 4:
        # Obtenemos los nombres originales de las columnas para no perderlos
        col_stock_name = df.columns[3]
        col_precio_name = df.columns[4]
        
        # SOLUCIÓN REDONDA: Convertimos a serie numérica limpia independientemente de la original
        serie_stock = pd.to_numeric(df.iloc[:, 3], errors='coerce').fillna(0).astype(int)
        serie_precio = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(0.0).astype(float)
        
        # Eliminamos las columnas viejas que causan el conflicto de tipo rígido
        columnas = list(df.columns)
        df = df.drop(columns=[col_stock_name, col_precio_name])
        
        # Insertamos las series numéricas limpias exactamente en las mismas posiciones
        df.insert(3, col_stock_name, serie_stock)
        df.insert(4, col_precio_name, serie_precio)
        
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

@st.cache_data(ttl=7200)  # Cache por 2 horas (empleados cambian menos)
def cargar_empleados():
    """
    Carga el listado de empleados desde Google Sheets
    Lee de la hoja "Empleados" en la misma Google Sheet
    Estructura esperada: Empresa | Cod_Empleado | Persona | Regional
    """
    try:
        # Importar aquí para evitar circular imports
        from src.sheets import get_gsheet_connection
        from config import EMPLEADOS_SHEET_URL
        
        gc = get_gsheet_connection()
        if gc is None:
            st.error("❌ No se pudo conectar a Google Sheets para cargar empleados")
            return pd.DataFrame()
        
        spreadsheet = gc.open_by_url(EMPLEADOS_SHEET_URL)
        
        # Intenta leer hoja "Empleados"
        try:
            worksheet = spreadsheet.worksheet("Empleados")
            data = worksheet.get_all_records()
            df_emp = pd.DataFrame(data)
            
            if df_emp.empty:
                st.warning("⚠️ La hoja 'Empleados' está vacía")
                return pd.DataFrame()
            
            # Normalizar códigos de empleado al cargar
            df_emp['Cod_Empleado'] = df_emp['Cod_Empleado'].astype(str).str.strip().str.upper()
            return df_emp
            
        except Exception as e:
            st.error(f"❌ No se encontró la hoja 'Empleados' en Google Sheets: {e}")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Error cargando empleados desde Google Sheets: {e}")
        return pd.DataFrame()


def obtener_datos_empleado(cod_empleado):
    """
    Busca un empleado por código y devuelve sus datos.
    Optimizado para búsqueda rápida.
    
    Retorna:
        dict con claves: 'nombre', 'empresa', 'regional', 'encontrado'
        Si no encuentra: {'encontrado': False}
    """
    df_emp = cargar_empleados()
    
    if df_emp.empty:
        return {'encontrado': False, 'error': 'No se pudo cargar la lista de empleados'}
    
    # Búsqueda directa sin conversiones innecesarias
    cod_busqueda = cod_empleado.strip().upper()
    
    # Usar .loc para búsqueda O masking booleano (más rápido que isin)
    mascara = df_emp['Cod_Empleado'] == cod_busqueda
    empleado = df_emp[mascara]
    
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