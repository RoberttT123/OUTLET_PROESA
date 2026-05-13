import pandas as pd
from datetime import datetime

def validar_stock(cantidad_pedida, stock_actual):
    """
    Compara la cantidad solicitada contra el stock disponible.
    Ambos deben ser tratados como números.
    """
    try:
        return float(cantidad_pedida) <= float(stock_actual)
    except:
        return False

def preparar_fila_pedido(cod_emp, nom_emp, fila_prod, cantidad):
    """
    Construye el DataFrame de una fila con la estructura 
    requerida para el reporte final de Trade Marketing.
    """
    return pd.DataFrame([{
        "Cod. Empleado": cod_emp,
        "Nombre Empleado": nom_emp,
        "Línea": fila_prod.iloc[0],
        "Código Producto": fila_prod.iloc[1],
        "Nombre Producto": fila_prod.iloc[2],
        "Monto Uni": fila_prod.iloc[4],
        "Descuento": 0,
        "Cantidad": cantidad,
        "Stock Actual": fila_prod.iloc[3],
        "Empresa": fila_prod.iloc[5],
        "Fecha Registro": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    }])