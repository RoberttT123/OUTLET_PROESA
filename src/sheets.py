import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

try:
    import gspread
    from gspread.utils import rowcol_to_a1
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
    """Guarda un pedido en Google Sheets con hora de Bolivia."""
    if timestamp is None:
        tz_bo = pytz.timezone('America/La_Paz')
        timestamp = datetime.now(tz_bo).strftime("%d/%m/%Y %H:%M:%S")

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
                cod_emp,
                nom_emp,
                item.get('linea', ''),
                item.get('codigo_producto', ''),
                item['producto'],
                item.get('precio_unitario', 0),
                item.get('descuento', 0),
                item['cantidad'],
                item.get('stock_actual', 0),
                item.get('empresa', ''),
                timestamp
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

    except Exception:
        return pd.DataFrame()


def obtener_todos_pedidos_sheets(
    url_sheet: str,
    hoja: str = "Pedidos"
) -> pd.DataFrame:
    """Obtiene todos los pedidos."""
    try:
        gc = get_gsheet_connection()
        if gc is None:
            return pd.DataFrame()

        spreadsheet = gc.open_by_url(url_sheet)
        worksheet = spreadsheet.worksheet(hoja)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)

    except Exception:
        return pd.DataFrame()


def actualizar_stock_sheets(
    codigo_producto: str,
    cantidad_a_restar: int,
    url_sheet: str,
    hoja: str = "Inventario"
):
    """
    Actualiza el stock de UN producto (se mantiene por compatibilidad).
    Para múltiples productos usa actualizar_stock_batch_sheets().
    """
    try:
        gc = get_gsheet_connection()
        if gc is None:
            return False

        spreadsheet = gc.open_by_url(url_sheet)
        worksheet = spreadsheet.worksheet(hoja)

        lista_codigos = worksheet.col_values(2)

        if codigo_producto in lista_codigos:
            row_idx = lista_codigos.index(codigo_producto) + 1
            valor_celda = worksheet.cell(row_idx, 4).value
            stock_actual = int(float(valor_celda)) if valor_celda else 0
            nuevo_stock = max(0, stock_actual - cantidad_a_restar)
            worksheet.update_cell(row_idx, 4, nuevo_stock)
            return True
        else:
            st.error(f"Cod {codigo_producto} no encontrado en Inventario.")
            return False

    except Exception as e:
        st.error(f"Error al actualizar stock en la nube: {e}")
        return False


def actualizar_stock_batch_sheets(
    items: list,
    url_sheet: str,
    hoja: str = "Inventario"
) -> bool:
    """
    Actualiza el stock de MÚLTIPLES productos en una sola llamada HTTP.

    Parámetros
    ----------
    items : list[dict]
        Lista de dicts con keys:
            - "codigo_producto"  (str)
            - "cantidad_a_restar" (int)
    url_sheet : str
        URL de la Google Sheet.
    hoja : str
        Nombre de la hoja de inventario.

    Por qué es más rápido
    ---------------------
    La función original hace 3 llamadas HTTP por producto:
        col_values() + cell() + update_cell() × N productos

    Esta función hace 2 llamadas HTTP en total sin importar cuántos productos:
        get_all_values() × 1  +  batch_update() × 1
    """
    try:
        gc = get_gsheet_connection()
        if gc is None:
            return False

        spreadsheet = gc.open_by_url(url_sheet)
        worksheet = spreadsheet.worksheet(hoja)

        # 1 sola lectura: traer toda la hoja de una vez
        data = worksheet.get_all_values()
        if not data:
            return False

        # La columna B (índice 1) es Código Producto
        # La columna D (índice 3) es Stock
        COL_CODIGO = 1
        COL_STOCK  = 3

        # Construir mapa codigo → (row_idx, stock_actual) para acceso O(1)
        mapa = {}
        for row_idx, row in enumerate(data[1:], start=2):  # start=2 por el header
            if len(row) > COL_CODIGO:
                codigo = str(row[COL_CODIGO]).strip()
                stock  = int(float(row[COL_STOCK])) if len(row) > COL_STOCK and row[COL_STOCK] else 0
                mapa[codigo] = {"row_idx": row_idx, "stock_actual": stock}

        # Preparar todas las actualizaciones en memoria
        updates = []
        for item in items:
            codigo = str(item["codigo_producto"]).strip()
            restar = int(item["cantidad_a_restar"])

            if codigo not in mapa:
                st.warning(f"⚠️ Código {codigo} no encontrado en inventario.")
                continue

            nuevo_stock = max(0, mapa[codigo]["stock_actual"] - restar)
            celda = rowcol_to_a1(mapa[codigo]["row_idx"], COL_STOCK + 1)  # +1: gspread es 1-based
            updates.append({"range": celda, "values": [[nuevo_stock]]})

        # 1 sola escritura: mandar todos los cambios juntos
        if updates:
            worksheet.batch_update(updates)

        return True

    except Exception as e:
        st.error(f"Error al actualizar stock en lote: {e}")
        return False


# ── Estructura de referencia ─────────────────────────────────────────────────
INVENTARIO_HEADERS = [
    "Línea", "Código Producto", "Nombre Producto",
    "Stock", "Precio Unitario", "Empresa"
]

PEDIDOS_HEADERS = [
    "Cod. Empleado", "Nombre Empleado", "Línea",
    "Código Producto", "Nombre Producto", "Monto Uni",
    "Descuento", "Cantidad", "Stock Actual", "Empresa", "Fecha Registro"
]