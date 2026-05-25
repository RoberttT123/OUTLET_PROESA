# -*- coding: utf-8 -*-
"""
MÓDULO DE BASE DE DATOS LOCAL Y EMPLEADOS - OUTLET PROESA
----------------------------------------------------------
Gestiona:
  - Inventario maestro local (Excel)
  - Pedidos consolidados locales (Excel)
  - Carga de empleados desde Google Sheets con caché larga (2 h)
    y backoff exponencial anti-429

Desarrollado para: PROYECTO_OUTLET
Última actualización: Mayo 2026
"""

import os
import pandas as pd
import streamlit as st

PATH_PEDIDOS      = "data/consolidado_pedidos.xlsx"
PATH_INV_SISTEMA  = "data/inventario_maestro.xlsx"

try:
    from config import EMPLEADOS_SHEET_URL, EMPLEADOS_HOJA_NAME
    USING_SHEETS_EMP = True
except ImportError:
    USING_SHEETS_EMP = False


# ══════════════════════════════════════════════════════════════════════════════
# UTILIDADES LOCALES
# ══════════════════════════════════════════════════════════════════════════════
def limpiar_formato_latino(valor):
    """Convierte '1.933,50' (str) a 1933.50 (float): punto=miles, coma=decimal."""
    if isinstance(valor, str):
        valor = valor.replace(".", "").replace(",", ".")
    return valor


def cargar_inventario(archivo) -> pd.DataFrame:
    """
    Carga el archivo Excel subido, reconstruyendo las columnas de stock y
    precio como series numéricas limpias para evitar conflictos de tipo.
    """
    df = pd.read_excel(archivo, sheet_name=0)

    if df.shape[1] > 4:
        col_stock_name  = df.columns[3]
        col_precio_name = df.columns[4]

        serie_stock  = pd.to_numeric(df.iloc[:, 3], errors="coerce").fillna(0).astype(int)
        serie_precio = pd.to_numeric(df.iloc[:, 4], errors="coerce").fillna(0.0).astype(float)

        df = df.drop(columns=[col_stock_name, col_precio_name])
        df.insert(3, col_stock_name, serie_stock)
        df.insert(4, col_precio_name, serie_precio)

    return df


def guardar_inventario_maestro(df: pd.DataFrame) -> None:
    """Crea / sobreescribe el archivo permanente de inventario en data/."""
    if not os.path.exists("data"):
        os.makedirs("data")
    df.to_excel(PATH_INV_SISTEMA, index=False)


def guardar_pedido(df_nuevo: pd.DataFrame) -> None:
    """Anexa un nuevo pedido al archivo consolidado local."""
    if not os.path.exists(PATH_PEDIDOS):
        if not os.path.exists("data"):
            os.makedirs("data")
        df_nuevo.to_excel(PATH_PEDIDOS, index=False)
    else:
        existente   = pd.read_excel(PATH_PEDIDOS)
        consolidado = pd.concat([existente, df_nuevo], ignore_index=True)
        consolidado.to_excel(PATH_PEDIDOS, index=False)


def actualizar_stock_inventario(codigo_producto: str, cantidad_restar: int) -> None:
    """
    Resta stock del inventario maestro local.
    Si cantidad_restar es negativa, suma stock (devolución).
    """
    df = pd.read_excel(PATH_INV_SISTEMA)
    df.loc[df.iloc[:, 1] == codigo_producto, df.columns[3]] -= cantidad_restar
    df.to_excel(PATH_INV_SISTEMA, index=False)


# ══════════════════════════════════════════════════════════════════════════════
# EMPLEADOS — CARGA DESDE GOOGLE SHEETS
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=7200, show_spinner=False)   # 2 horas — empleados cambian poco
def cargar_empleados() -> pd.DataFrame:
    """
    Descarga la tabla COMPLETA de empleados en una sola llamada y la
    mantiene en caché 2 horas.  Con 30 usuarios simultáneos esto
    significa 1 lectura cada 2 horas, no 30 lecturas por minuto.

    Usa backoff exponencial (importado de src.sheets) para recuperarse
    automáticamente si la cuota 429 se dispara en el momento de la carga.
    """
    try:
        from src.sheets import get_gsheet_connection, _con_reintento
    except ImportError:
        st.error("❌ No se pudo importar src.sheets (get_gsheet_connection).")
        return pd.DataFrame()

    if not USING_SHEETS_EMP:
        st.error("❌ EMPLEADOS_SHEET_URL no definida en config.py.")
        return pd.DataFrame()

    try:
        gc = get_gsheet_connection()
        if gc is None:
            st.error("❌ No se pudo conectar a Google Sheets para cargar empleados.")
            return pd.DataFrame()

        spreadsheet = _con_reintento(gc.open_by_url, EMPLEADOS_SHEET_URL)
        worksheet   = _con_reintento(spreadsheet.worksheet, "Empleados")

        # numericise_ignore=['all'] evita que códigos como "E0200491" sean
        # malinterpretados como números en locales no-estándar.
        data   = _con_reintento(worksheet.get_all_records, numericise_ignore=["all"])
        df_emp = pd.DataFrame(data)

        if df_emp.empty:
            st.warning("⚠️ La hoja 'Empleados' está vacía.")
            return pd.DataFrame()

        df_emp["Cod_Empleado"] = (
            df_emp["Cod_Empleado"].astype(str).str.strip().str.upper()
        )
        return df_emp

    except Exception as e:
        # Mostramos el error — no lo silenciamos para facilitar diagnóstico
        st.error(f"Error cargando empleados desde Google Sheets: {e}")
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# EMPLEADOS — BÚSQUEDA Y VALIDACIÓN
# ══════════════════════════════════════════════════════════════════════════════
def obtener_datos_empleado(cod_empleado: str) -> dict:
    """
    Busca un empleado por código devolviendo sus datos.
    La tabla ya está en caché — no genera ninguna llamada de red adicional.

    Retorna dict con claves: encontrado, nombre, empresa, regional.
    """
    df_emp = cargar_empleados()

    if df_emp.empty:
        return {"encontrado": False, "error": "No se pudo cargar la lista de empleados"}

    cod_busqueda = str(cod_empleado).strip().upper()
    mascara      = df_emp["Cod_Empleado"] == cod_busqueda
    empleado     = df_emp[mascara]

    if empleado.empty:
        return {"encontrado": False}

    fila = empleado.iloc[0]
    return {
        "encontrado": True,
        "nombre":   str(fila.get("Persona", "")).title(),
        "empresa":  str(fila.get("Empresa", "")),
        "regional": str(fila.get("Regional", "")),
    }


def validar_empleado(cod_empleado: str) -> bool:
    """Valida si un código de empleado existe. True = existe."""
    return obtener_datos_empleado(cod_empleado).get("encontrado", False)