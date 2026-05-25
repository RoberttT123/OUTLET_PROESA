# -*- coding: utf-8 -*-
"""
MÓDULO DE CONECTIVIDAD Y PERSISTENCIA CON GOOGLE SHEETS - OUTLET PROESA
----------------------------------------------------------------
Centraliza todas las operaciones de lectura, escritura y transacciones
atómicas con la API de Google Drive/Sheets a través de gspread.
Incluye:
  - Backoff exponencial anti-429 (hasta 5 reintentos por llamada)
  - Mutex threading para descontar stock sin race conditions
  - Escritura de precios con value_input_option='RAW' (evita conversiones erróneas de locale)
  - Lectura con numericise_ignore=['all'] + parseo limpio en Python

Desarrollado para: PROYECTO_OUTLET
"""

import time
import random
import threading
from datetime import datetime

import streamlit as st
import pandas as pd
import pytz

try:
    import gspread
    from gspread import Cell
    from oauth2client.service_account import ServiceAccountCredentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

# ── CERROJO MUTEX GLOBAL ──────────────────────────────────────────────────────
LOCK_TRANSACCIONAL_STOCK = threading.Lock()


# ══════════════════════════════════════════════════════════════════════════════
# UTILIDAD: BACKOFF EXPONENCIAL ANTI-429
# ══════════════════════════════════════════════════════════════════════════════
def _con_reintento(fn, *args, reintentos: int = 5, **kwargs):
    """
    Ejecuta `fn(*args, **kwargs)` con reintentos automáticos ante cuotas
    agotadas (HTTP 429) o errores de rate-limit de Google Sheets.

    Espera: 2^intento + jitter(0-1.5 s) entre cada reintento.
    Lanza RuntimeError si se agotan todos los intentos.
    """
    for intento in range(reintentos):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            msg = str(e)
            es_quota = any(k in msg for k in ("429", "Quota", "quota", "RATE_LIMIT", "rate limit"))
            if es_quota and intento < reintentos - 1:
                espera = (2 ** intento) + random.uniform(0, 1.5)
                time.sleep(espera)
            else:
                raise
    raise RuntimeError(f"Límite de reintentos agotado tras {reintentos} intentos.")


# ══════════════════════════════════════════════════════════════════════════════
# CONEXIÓN
# ══════════════════════════════════════════════════════════════════════════════
def get_gsheet_connection():
    """Obtiene la conexión a Google Sheets mediante credenciales locales o secrets."""
    if not HAS_GSPREAD:
        return None
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        try:
            # Intenta primero con archivo local
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
            return gspread.authorize(creds)
        except FileNotFoundError:
            # Si no está, usa st.secrets (entorno de producción)
            creds_dict = st.secrets["google_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Error conectando a Google Sheets: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# INVENTARIO — LECTURA
# ══════════════════════════════════════════════════════════════════════════════
def obtener_inventario_sheets(url_sheet: str, hoja: str = "Inventario") -> pd.DataFrame:
    """
    Carga el inventario completo desde Google Sheets.

    numericise_ignore=['all'] evita que gspread auto-convierta códigos como
    "0100221" al número 100221 (pierde el cero inicial).
    """
    try:
        gc = get_gsheet_connection()
        if gc is None:
            st.error("❌ No conectado a Google Sheets. Verifica credenciales.")
            return pd.DataFrame()

        spreadsheet = _con_reintento(gc.open_by_url, url_sheet)
        worksheet   = _con_reintento(spreadsheet.worksheet, hoja)
        data        = _con_reintento(worksheet.get_all_records, numericise_ignore=["all"])

        df = pd.DataFrame(data)
        if "Código Producto" in df.columns:
            df["Código Producto"] = df["Código Producto"].astype(str).str.strip()
        return df

    except Exception as e:
        st.error(f"Error cargando inventario: {e}")
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# PEDIDOS — ESCRITURA
# ══════════════════════════════════════════════════════════════════════════════
def guardar_pedido_sheets(
    cod_emp: str,
    nom_emp: str,
    items_carrito: list,
    url_sheet: str,
    hoja: str = "Pedidos",
    timestamp: str = None
) -> bool:
    """
    Guarda un pedido en Google Sheets con hora oficial de Bolivia.

    Se usa value_input_option='RAW' para que Google Sheets almacene los 
    números exactamente como Python los genera (p.ej. 8.77), evitando 
    que el locale interprete erróneamente la puntuación.
    """
    if timestamp is None:
        tz_bo     = pytz.timezone("America/La_Paz")
        timestamp = datetime.now(tz_bo).strftime("%d/%m/%Y %H:%M:%S")

    try:
        gc = get_gsheet_connection()
        if gc is None:
            st.error("❌ No conectado a Google Sheets.")
            return False

        spreadsheet = _con_reintento(gc.open_by_url, url_sheet)
        worksheet   = _con_reintento(spreadsheet.worksheet, hoja)

        filas_a_agregar = []
        for item in items_carrito:
            precio = round(float(item.get("precio_unitario", 0)), 2)
            fila = [
                str(cod_emp),
                str(nom_emp),
                str(item.get("linea", "")),
                str(item.get("codigo_producto", "")),
                str(item["producto"]),
                precio,                             
                int(item.get("descuento", 0)),
                int(item["cantidad"]),
                int(item.get("stock_actual", 0)),
                str(item.get("empresa", "")),
                timestamp,
            ]
            filas_a_agregar.append(fila)

        _con_reintento(
            worksheet.append_rows,
            filas_a_agregar,
            value_input_option="RAW",
        )
        return True

    except Exception as e:
        st.error(f"Error guardando pedido: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# PEDIDOS — LECTURA (HISTORIAL)
# ══════════════════════════════════════════════════════════════════════════════
def _parsear_precio_seguro(valor) -> float:
    """
    Convierte cualquier representación de precio a float limpio.
    Soporta formatos locales e internacionales con precisión.
    """
    try:
        if pd.isna(valor):
            return 0.0
            
        s = str(valor).strip().replace(" ", "")
        if not s:
            return 0.0
            
        if "," in s and "." in s:
            # Detecta qué símbolo actúa como decimal basándose en su posición
            if s.rfind(",") > s.rfind("."):
                # Formato Latam: 1.234,56
                s = s.replace(".", "").replace(",", ".")
            else:
                # Formato US: 1,234.56
                s = s.replace(",", "")
        elif "," in s and "." not in s:
            # Solo coma: 8,77
            s = s.replace(",", ".")
            
        return float(s)
    except Exception:
        return 0.0


def obtener_pedidos_empleado_sheets(
    cod_emp: str,
    url_sheet: str,
    hoja: str = "Pedidos"
) -> pd.DataFrame:
    """
    Obtiene todos los pedidos de un empleado específico.
    """
    try:
        gc = get_gsheet_connection()
        if gc is None:
            return pd.DataFrame()

        spreadsheet = _con_reintento(gc.open_by_url, url_sheet)
        worksheet   = _con_reintento(spreadsheet.worksheet, hoja)
        data        = _con_reintento(worksheet.get_all_records, numericise_ignore=["all"])

        df = pd.DataFrame(data)
        if df.empty:
            return df

        col_cod = "Cod. Empleado"
        if col_cod not in df.columns:
            return pd.DataFrame()

        df_emp = df[df[col_cod].astype(str).str.strip() == str(cod_emp).strip()].copy()

        for col_precio in ("Monto Uni", "Precio Unitario"):
            if col_precio in df_emp.columns:
                df_emp[col_precio] = df_emp[col_precio].apply(_parsear_precio_seguro)

        if "Cantidad" in df_emp.columns:
            df_emp["Cantidad"] = pd.to_numeric(df_emp["Cantidad"], errors="coerce").fillna(0).astype(int)

        return df_emp

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

        spreadsheet = _con_reintento(gc.open_by_url, url_sheet)
        worksheet   = _con_reintento(spreadsheet.worksheet, hoja)
        data        = _con_reintento(worksheet.get_all_records, numericise_ignore=["all"])
        return pd.DataFrame(data)

    except Exception:
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# STOCK — VERIFICACIÓN EN TIEMPO REAL
# ══════════════════════════════════════════════════════════════════════════════
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

        spreadsheet = _con_reintento(gc.open_by_url, url_sheet)
        worksheet   = _con_reintento(spreadsheet.worksheet, hoja)
        data        = _con_reintento(worksheet.get_all_values)

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
                    "producto":   entrada["nombre"],
                    "codigo":     codigo,
                    "pedido":     pedido,
                    "disponible": entrada["stock"],
                })

        return sin_stock

    except Exception as e:
        st.error(f"Error al verificar stock: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# STOCK — TRANSACCIÓN ATÓMICA (MUTEX + BACKOFF)
# ══════════════════════════════════════════════════════════════════════════════
def procesar_descuento_stock_seguro(
    items: list,
    url_sheet: str,
    hoja: str = "Inventario"
) -> dict:
    """
    Lee el stock actual, verifica disponibilidad y descuenta en lote,
    todo dentro de un mutex threading para evitar race conditions.
    """
    with LOCK_TRANSACCIONAL_STOCK:
        try:
            gc = get_gsheet_connection()
            if gc is None:
                return {"exito": False, "sin_stock": []}

            spreadsheet = _con_reintento(gc.open_by_url, url_sheet)
            worksheet   = _con_reintento(spreadsheet.worksheet, hoja)
            data        = _con_reintento(worksheet.get_all_values)

            if not data or len(data) < 2:
                return {"exito": False, "sin_stock": []}

            COL_CODIGO_IDX = 1
            COL_STOCK_IDX  = 3
            COL_NOMBRE_IDX = 2
            COL_STOCK_NUM  = 4   # columna D en gspread (base 1)

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

            sin_stock             = []
            celdas_a_actualizar   = []

            for item in items:
                codigo = str(item["codigo_producto"]).strip()
                pedido = int(item["cantidad_a_restar"])

                if codigo not in mapa_actual:
                    continue

                stock_real  = mapa_actual[codigo]["stock"]
                nombre_prod = mapa_actual[codigo]["nombre"]

                if stock_real < pedido:
                    sin_stock.append({
                        "producto":   nombre_prod,
                        "codigo":     codigo,
                        "pedido":     pedido,
                        "disponible": stock_real,
                    })
                else:
                    nuevo_stock = stock_real - pedido
                    celdas_a_actualizar.append(
                        Cell(row=mapa_actual[codigo]["fila"], col=COL_STOCK_NUM, value=nuevo_stock)
                    )

            if sin_stock:
                return {"exito": False, "sin_stock": sin_stock}

            if celdas_a_actualizar:
                _con_reintento(worksheet.update_cells, celdas_a_actualizar)
                return {"exito": True, "sin_stock": []}

            return {"exito": False, "sin_stock": []}

        except Exception as e:
            st.error(f"Error crítico en la transacción de stock: {e}")
            return {"exito": False, "sin_stock": []}


# ══════════════════════════════════════════════════════════════════════════════
# STOCK — ACTUALIZACIÓN INDIVIDUAL (retrocompatibilidad)
# ══════════════════════════════════════════════════════════════════════════════
def actualizar_stock_sheets(
    codigo_producto: str,
    cantidad_a_restar: int,
    url_sheet: str,
    hoja: str = "Inventario"
) -> bool:
    """Actualiza el stock de UN producto de manera aislada."""
    try:
        gc = get_gsheet_connection()
        if gc is None:
            return False

        spreadsheet   = _con_reintento(gc.open_by_url, url_sheet)
        worksheet     = _con_reintento(spreadsheet.worksheet, hoja)
        lista_codigos = _con_reintento(worksheet.col_values, 2)
        codigo_buscar = str(codigo_producto).strip()

        if codigo_buscar in lista_codigos:
            row_idx     = lista_codigos.index(codigo_buscar) + 1
            valor_celda = _con_reintento(worksheet.cell, row_idx, 4)
            stock_actual = int(float(valor_celda.value)) if valor_celda.value else 0
            nuevo_stock  = max(0, stock_actual - cantidad_a_restar)
            _con_reintento(worksheet.update_cell, row_idx, 4, nuevo_stock)
            return True
        return False
    except Exception:
        return False


def actualizar_stock_batch_sheets(
    items: list,
    url_sheet: str,
    hoja: str = "Inventario"
) -> bool:
    """Actualiza el stock de MÚLTIPLES productos en 2 llamadas HTTP."""
    try:
        gc = get_gsheet_connection()
        if gc is None:
            return False

        spreadsheet = _con_reintento(gc.open_by_url, url_sheet)
        worksheet   = _con_reintento(spreadsheet.worksheet, hoja)
        data        = _con_reintento(worksheet.get_all_values)

        if not data or len(data) < 2:
            return False

        COL_CODIGO_IDX = 1
        COL_STOCK_IDX  = 3
        COL_STOCK_NUM  = 4

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
            _con_reintento(worksheet.update_cells, celdas_a_actualizar)
        return True

    except Exception:
        return False


# ── ESTRUCTURAS DE REFERENCIA ─────────────────────────────────────────────────
INVENTARIO_HEADERS = [
    "Línea", "Código Producto", "Nombre Producto",
    "Stock", "Precio Unitario", "Empresa"
]

PEDIDOS_HEADERS = [
    "Cod. Empleado", "Nombre Empleado", "Línea",
    "Código Producto", "Nombre Producto", "Monto Uni",
    "Descuento", "Cantidad", "Stock Actual", "Empresa", "Fecha Registro"
]