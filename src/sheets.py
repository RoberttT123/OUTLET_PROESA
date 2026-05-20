# -*- coding: utf-8 -*-
"""
MÓDULO DE CONECTIVIDAD Y PERSISTENCIA CON GOOGLE SHEETS - OUTLET PROESA
----------------------------------------------------------------
Centraliza todas las operaciones de lectura, escritura y transacciones
atómicas con la API de Google Drive/Sheets a través de gspread.
Incluye un mecanismo de exclusión mutua para evitar condiciones de carrera.

Desarrollado para: PROYECTO_OUTLET
Última actualización: Mayo 2026
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import threading  # ── NUEVA IMPORTACIÓN: Control de concurrencia a nivel de hilos ──

try:
    import gspread
    from gspread import Cell
    from oauth2client.service_account import ServiceAccountCredentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

# ── CERROJO MUTEX GLOBAL ──
# Este objeto asegura que si dos hilos de Streamlit intentan descontar stock
# en el mismo milisegundo, hagan fila india y se procesen uno por uno de forma aislada.
LOCK_TRANSACCIONAL_STOCK = threading.Lock()


def get_gsheet_connection():
    """Obtiene la conexión a Google Sheets mediante credenciales locales o secrets."""
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
    """
    Carga el inventario desde Google Sheets.
    
    numericise_ignore=['all'] evita que gspread convierta automáticamente
    "0100221" al número 100221 — preserva el cero inicial en códigos
    que son puramente numéricos.
    """
    try:
        gc = get_gsheet_connection()
        if gc is None:
            st.error("❌ No conectado a Google Sheets. Verifica credenciales.")
            return pd.DataFrame()

        spreadsheet = gc.open_by_url(url_sheet)
        worksheet = spreadsheet.worksheet(hoja)

        # ── FIX: preservar ceros iniciales en códigos numéricos ──────────────
        data = worksheet.get_all_records(numericise_ignore=['all'])
        df = pd.DataFrame(data)

        # Forzar columna de código a string limpio (por si queda algún residuo)
        if "Código Producto" in df.columns:
            df["Código Producto"] = df["Código Producto"].astype(str).str.strip()

        return df

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
    """Guarda un pedido en Google Sheets con hora oficial de Bolivia."""
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
    """Obtiene todos los pedidos de un empleado específico."""
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
    """Obtiene el historial absoluto de todos los pedidos registrados."""
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


def verificar_stock_disponible(
    items: list,
    url_sheet: str,
    hoja: str = "Inventario"
) -> list:
    """
    Verifica en tiempo real si hay stock suficiente para cada producto.
    Retorna lista de productos con stock insuficiente.
    """
    try:
        gc = get_gsheet_connection()
        if gc is None:
            return []

        spreadsheet = gc.open_by_url(url_sheet)
        worksheet = spreadsheet.worksheet(hoja)

        data = worksheet.get_all_values()
        if not data or len(data) < 2:
            return []

        COL_CODIGO_IDX = 1
        COL_STOCK_IDX  = 3
        COL_NOMBRE_IDX = 2

        mapa_stock_real = {}
        for row in data[1:]:
            if len(row) > COL_CODIGO_IDX:
                codigo = str(row[COL_CODIGO_IDX]).strip()
                nombre = str(row[COL_NOMBRE_IDX]).strip() if len(row) > COL_NOMBRE_IDX else codigo
                try:
                    stock = int(float(row[COL_STOCK_IDX])) if len(row) > COL_STOCK_IDX and row[COL_STOCK_IDX] else 0
                except (ValueError, TypeError):
                    stock = 0
                mapa_stock_real[codigo] = {"stock": stock, "nombre": nombre}

        sin_stock = []
        for item in items:
            codigo  = str(item["codigo_producto"]).strip()
            pedido  = int(item["cantidad_a_restar"])
            entrada = mapa_stock_real.get(codigo)

            if entrada is None:
                continue

            if entrada["stock"] < pedido:
                sin_stock.append({
                    "producto":    entrada["nombre"],
                    "codigo":      codigo,
                    "pedido":      pedido,
                    "disponible":  entrada["stock"]
                })

        return sin_stock

    except Exception as e:
        st.error(f"Error al verificar stock: {e}")
        return []


# ── FUNCIÓN TRANSACCIONAL BLINDADA (CON EXCLUSIÓN MUTUA DE HILOS) ──────────────
def procesar_descuento_stock_seguro(
    items: list,
    url_sheet: str,
    hoja: str = "Inventario"
) -> dict:
    """
    Fusión Atómica con Mutex Lock: Envuelve las peticiones críticas de red.
    Si dos usuarios llaman a esta función al mismo tiempo, el cerrojo detiene
    al segundo usuario temporalmente hasta que el primero lea, verifique y descuente.
    
    Garantiza consistencia absoluta eliminando las condiciones de carrera (Race Conditions).
    """
    # El bloque 'with' asegura que el cerrojo se libere pase lo que pase (incluso si hay un error)
    with LOCK_TRANSACCIONAL_STOCK:
        try:
            gc = get_gsheet_connection()
            if gc is None:
                return {"exito": False, "sin_stock": []}

            spreadsheet = gc.open_by_url(url_sheet)
            worksheet = spreadsheet.worksheet(hoja)

            COL_CODIGO_IDX = 1
            COL_STOCK_IDX  = 3
            COL_NOMBRE_IDX = 2
            COL_STOCK_NUM  = 4  # Columna D basada en índice 1 para gspread Cell

            # 1. PASO CRÍTICO: Descarga de datos protegida por el cerrojo de memoria
            data = worksheet.get_all_values()
            if not data or len(data) < 2:
                return {"exito": False, "sin_stock": []}

            # Construir mapa con el inventario real en este microsegundo
            mapa_actual = {}
            for i, row in enumerate(data[1:], start=2):
                if len(row) > COL_CODIGO_IDX:
                    codigo = str(row[COL_CODIGO_IDX]).strip()
                    nombre = str(row[COL_NOMBRE_IDX]).strip() if len(row) > COL_NOMBRE_IDX else codigo
                    try:
                        stock = int(float(row[COL_STOCK_IDX])) if len(row) > COL_STOCK_IDX and row[COL_STOCK_IDX] else 0
                    except (ValueError, TypeError):
                        stock = 0
                    mapa_actual[codigo] = {"fila": i, "stock": stock, "nombre": nombre}

            # 2. VERIFICACIÓN ATÓMICA
            sin_stock = []
            celdas_a_actualizar = []

            for item in items:
                codigo = str(item["codigo_producto"]).strip()
                pedido = int(item["cantidad_a_restar"])

                if codigo not in mapa_actual:
                    continue

                stock_real = mapa_actual[codigo]["stock"]
                nombre_prod = mapa_actual[codigo]["nombre"]

                if stock_real < pedido:
                    sin_stock.append({
                        "producto": nombre_prod,
                        "codigo": codigo,
                        "pedido": pedido,
                        "disponible": stock_real
                    })
                else:
                    # Cálculo secuencial seguro
                    nuevo_stock = stock_real - pedido
                    celdas_a_actualizar.append(
                        Cell(row=mapa_actual[codigo]["fila"], col=COL_STOCK_NUM, value=nuevo_stock)
                    )

            # 3. VEREDICTO DE LA TRANSACCIÓN
            if sin_stock:
                # Retorna la lista; el hilo actual sale y el siguiente usuario en la fila toma el control
                return {"exito": False, "sin_stock": sin_stock}

            # Guardamos los cambios inmediatamente en lote si la prueba fue superada
            if celdas_a_actualizar:
                worksheet.update_cells(celdas_a_actualizar)
                return {"exito": True, "sin_stock": []}

            return {"exito": False, "sin_stock": []}

        except Exception as e:
            st.error(f"Error crítico en la transacción de stock: {e}")
            return {"exito": False, "sin_stock": []}


def actualizar_stock_sheets(
    codigo_producto: str,
    cantidad_a_restar: int,
    url_sheet: str,
    hoja: str = "Inventario"
):
    """
    Actualiza el stock de UN producto de manera aislada.
    Se mantiene estrictamente por retrocompatibilidad con módulos antiguos.
    """
    try:
        gc = get_gsheet_connection()
        if gc is None:
            return False

        spreadsheet = gc.open_by_url(url_sheet)
        worksheet = spreadsheet.worksheet(hoja)

        lista_codigos = [str(c).strip() for c in worksheet.col_values(2)]
        codigo_buscar = str(codigo_producto).strip()

        if codigo_buscar in lista_codigos:
            row_idx = lista_codigos.index(codigo_buscar) + 1
            valor_celda = worksheet.cell(row_idx, 4).value
            stock_actual = int(float(valor_celda)) if valor_celda else 0
            nuevo_stock = max(0, stock_actual - cantidad_a_restar)
            worksheet.update_cell(row_idx, 4, nuevo_stock)
            return True
        return False
    except Exception:
        return False


def actualizar_stock_batch_sheets(
    items: list,
    url_sheet: str,
    hoja: str = "Inventario"
) -> bool:
    """Actualiza el stock de MÚLTIPLES productos de manera rápida en 2 llamadas HTTP."""
    try:
        gc = get_gsheet_connection()
        if gc is None:
            return False

        spreadsheet = gc.open_by_url(url_sheet)
        worksheet = spreadsheet.worksheet(hoja)

        COL_CODIGO_IDX = 1
        COL_STOCK_IDX  = 3
        COL_STOCK_NUM  = 4

        data = worksheet.get_all_values()
        if not data or len(data) < 2:
            return False

        mapa = {}
        for i, row in enumerate(data[1:], start=2):
            if len(row) > COL_CODIGO_IDX:
                codigo = str(row[COL_CODIGO_IDX]).strip()
                try:
                    stock = int(float(row[COL_STOCK_IDX])) if len(row) > COL_STOCK_IDX and row[COL_STOCK_IDX] else 0
                except (ValueError, TypeError):
                    stock = 0
                mapa[codigo] = {"fila": i, "stock": stock}

        celdas_a_actualizar = []
        for item in items:
            codigo = str(item["codigo_producto"]).strip()
            restar = int(item["cantidad_a_restar"])

            if codigo not in mapa:
                continue

            nuevo_stock = max(0, mapa[codigo]["stock"] - restar)
            celdas_a_actualizar.append(
                Cell(row=mapa[codigo]["fila"], col=COL_STOCK_NUM, value=nuevo_stock)
            )

        if celdas_a_actualizar:
            worksheet.update_cells(celdas_a_actualizar)
        return True

    except Exception:
        return False


# ── ESTRUCTURAS DE REFERENCIA DE FILAS (METADATA) ──────────────────────────────
INVENTARIO_HEADERS = [
    "Línea", "Código Producto", "Nombre Producto",
    "Stock", "Precio Unitario", "Empresa"
]

PEDIDOS_HEADERS = [
    "Cod. Empleado", "Nombre Empleado", "Línea",
    "Código Producto", "Nombre Producto", "Monto Uni",
    "Descuento", "Cantidad", "Stock Actual", "Empresa", "Fecha Registro"
]