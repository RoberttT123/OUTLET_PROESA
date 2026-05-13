import streamlit as st
import pandas as pd
from datetime import datetime

try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False


def get_gsheet_connection():
    """Obtiene la conexión a Google Sheets."""
    try:
        if HAS_GSPREAD:
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
            try:
                creds = ServiceAccountCredentials.from_json_keyfile_name(
                    "credentials.json", scope
                )
                return gspread.authorize(creds)
            except FileNotFoundError:
                try:
                    creds_dict = st.secrets["google_service_account"]
                    creds = ServiceAccountCredentials.from_json_keyfile_dict(
                        creds_dict, scope
                    )
                    return gspread.authorize(creds)
                except:
                    return None
        return None
    except Exception as e:
        st.error(f"Error conectando a Google Sheets: {e}")
        return None


def obtener_inventario_sheets(url_sheet: str, hoja: str = "Inventario"):
    """Carga el inventario desde Google Sheets."""
    try:
        gc = get_gsheet_connection()
        if gc is None:
            st.error("❌ No conectado a Google Sheets. Verifica credenciales.")
            return pd.DataFrame()
        
        spreadsheet = gc.open_by_url(url_sheet)
        worksheet = spreadsheet.worksheet(hoja)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    
    except Exception as e:
        st.error(f"Error cargando inventario: {e}")
        return pd.DataFrame()


def guardar_pedido_sheets(
    cod_emp: str,
    nom_emp: str,
    items_carrito: list,
    url_sheet: str,
    hoja: str = "Pedidos",
    timestamp: str = None
):
    """Guarda un pedido en Google Sheets con la estructura personalizada."""
    if timestamp is None:
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    try:
        gc = get_gsheet_connection()
        if gc is None:
            st.error("❌ No conectado a Google Sheets.")
            return False
        
        spreadsheet = gc.open_by_url(url_sheet)
        worksheet = spreadsheet.worksheet(hoja)
        
        filas_a_agregar = []
        for item in items_carrito:
            fila = [
                cod_emp,                           # Cod. Empleado
                nom_emp,                           # Nombre Empleado
                item.get('linea', ''),             # Línea
                item.get('codigo_producto', ''),   # Código Producto
                item['producto'],                  # Nombre Producto
                item.get('precio_unitario', 0),    # Monto Uni
                item.get('descuento', 0),          # Descuento
                item['cantidad'],                  # Cantidad
                item.get('stock_actual', 0),       # Stock Actual
                item.get('empresa', ''),           # Empresa
                timestamp                          # Fecha Registro
            ]
            filas_a_agregar.append(fila)
        
        worksheet.append_rows(filas_a_agregar)
        return True
    
    except Exception as e:
        st.error(f"Error guardando pedido: {e}")
        return False


def obtener_pedidos_empleado_sheets(
    cod_emp: str,
    url_sheet: str,
    hoja: str = "Pedidos"
) -> pd.DataFrame:
    """Obtiene todos los pedidos de un empleado."""
    try:
        gc = get_gsheet_connection()
        if gc is None:
            return pd.DataFrame()
        
        spreadsheet = gc.open_by_url(url_sheet)
        worksheet = spreadsheet.worksheet(hoja)
        data = worksheet.get_all_records()
        
        df = pd.DataFrame(data)
        if df.empty:
            return df
        return df[df.get('Cod. Empleado', '') == cod_emp]
    
    except Exception as e:
        return pd.DataFrame()


def obtener_todos_pedidos_sheets(
    url_sheet: str,
    hoja: str = "Pedidos"
) -> pd.DataFrame:
    """Obtiene todos los pedidos (para Trade Marketing)."""
    try:
        gc = get_gsheet_connection()
        if gc is None:
            return pd.DataFrame()
        
        spreadsheet = gc.open_by_url(url_sheet)
        worksheet = spreadsheet.worksheet(hoja)
        data = worksheet.get_all_records()
        
        return pd.DataFrame(data)
    
    except Exception as e:
        return pd.DataFrame()
def actualizar_stock_sheets(codigo_producto: str, cantidad_a_restar: int, url_sheet: str, hoja: str = "Inventario"):
    """
    Busca un producto por código y resta la cantidad del stock en Google Sheets.
    """
    try:
        gc = get_gsheet_connection()
        if gc is None: return False
        
        spreadsheet = gc.open_by_url(url_sheet)
        worksheet = spreadsheet.worksheet(hoja)
        
        # 1. Buscar la columna de 'Código Producto' (suponiendo que es la B / índice 2)
        # y la columna de 'Stock' (suponiendo que es la D / índice 4)
        lista_codigos = worksheet.col_values(2) # Columna B
        
        if codigo_producto in lista_codigos:
            # Encontrar el índice de la fila (gspread usa base 1)
            row_idx = lista_codigos.index(codigo_producto) + 1
            
            # 2. Obtener el valor actual del stock (Columna D es la 4)
            stock_actual = int(worksheet.cell(row_idx, 4).value)
            nuevo_stock = stock_actual - cantidad_a_restar
            
            # 3. Actualizar la celda con el nuevo valor
            worksheet.update_cell(row_idx, 4, nuevo_stock)
            return True
        else:
            st.error(f"Cod {codigo_producto} no encontrado en Inventario.")
            return False
            
    except Exception as e:
        st.error(f"Error al actualizar stock en la nube: {e}")
        return False


# Headers esperados
INVENTARIO_HEADERS = [
    "Línea", "Código Producto", "Nombre Producto", 
    "Stock", "Precio Unitario", "Empresa"
]

PEDIDOS_HEADERS = [
    "Cod. Empleado", "Nombre Empleado", "Línea",
    "Código Producto", "Nombre Producto", "Monto Uni",
    "Descuento", "Cantidad", "Stock Actual", "Empresa", "Fecha Registro"
]