import pandas as pd
import os

PATH_PEDIDOS = "data/consolidado_pedidos.xlsx"
PATH_INV_SISTEMA = "data/inventario_maestro.xlsx"

def limpiar_formato_latino(valor):
    """
    Convierte formatos como '1.933,50' (str) a 1933.50 (float)
    Punto = Miles, Coma = Decimales
    """
    if isinstance(valor, str):
        # 1. Quitamos el punto de miles: '1.933' -> '1933'
        valor = valor.replace('.', '')
        # 2. Cambiamos la coma decimal por punto para Python: '0,50' -> '0.50'
        valor = valor.replace(',', '.')
    return valor

def cargar_inventario(archivo):
    """Lee el Excel inicial y limpia los formatos de número."""
    df = pd.read_excel(archivo, sheet_name="Hoja1")
    
    # Limpiamos las columnas críticas (Stock en índice 3 y Precio en índice 4)
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
    # Columna 2 (índice 1) es el Código, Columna 4 (índice 3) es el Stock
    df.loc[df.iloc[:, 1] == codigo_producto, df.columns[3]] -= cantidad_restar
    df.to_excel(PATH_INV_SISTEMA, index=False)