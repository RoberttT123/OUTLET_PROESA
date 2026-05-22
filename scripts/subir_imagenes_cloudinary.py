# -*- coding: utf-8 -*-
"""
SCRIPT DE MIGRACIÓN CONTROLADA A CLOUDINARY - OUTLET PROESA
----------------------------------------------------------------
Lee las imágenes de WhatsApp, las vincula con su SKU mediante un CSV
de mapeo y las sube de forma masiva y ordenada a Cloudinary.
"""

import os
import pandas as pd
import cloudinary
import cloudinary.uploader

# 1. Configuración de credenciales (Reemplaza con tus datos de Cloudinary)
cloudinary.config(
    cloud_name = "TU_CLOUD_NAME",
    api_key = "TU_API_KEY",
    api_secret = "TU_API_SECRET",
    secure = True
)

CARPETA_LOCAL = "imagenes_productos"
ARCHIVO_MAPEO = "mapeo_imagenes.csv"
PRESET_NAME = "outlet_preset"  # Asegúrate de tenerlo configurado como 'Signed'

def iniciar_migración_estructurada():
    # Validaciones iniciales de entorno
    if not os.path.exists(ARCHIVO_MAPEO):
        print(f"❌ No se encontró el archivo de mapeo '{ARCHIVO_MAPEO}' en la raíz.")
        return
        
    if not os.path.exists(CARPETA_LOCAL):
        print(f"❌ La carpeta '{CARPETA_LOCAL}' no existe.")
        return

    # Cargar matriz de relación Archivo -> SKU
    try:
        df_mapeo = pd.read_csv(ARCHIVO_MAPEO)
    except Exception as e:
        print(f"❌ Error al leer el archivo de mapeo: {e}")
        return

    print(f"🚀 Iniciando subida de {len(df_mapeo)} imágenes mapeadas a Cloudinary...\n")

    for idx, fila in df_mapeo.iterrows():
        nombre_archivo = str(fila['archivo_original']).strip()
        sku_codigo = str(fila['sku']).strip()
        
        ruta_completa = os.path.join(CARPETA_LOCAL, nombre_archivo)
        
        # Verificar que el archivo de WhatsApp realmente exista en la carpeta
        if not os.path.exists(ruta_completa):
            print(f"⚠️ Saltado: El archivo '{nombre_archivo}' no existe en '{CARPETA_LOCAL}'.")
            continue

        try:
            print(f"📤 Subiendo '{nombre_archivo}' asignándole el SKU: {sku_codigo}...")
            
            # Subida y renombrado en caliente
            respuesta = cloudinary.uploader.upload(
                ruta_completa,
                folder = "productos",
                public_id = sku_codigo,      # El nombre en Cloudinary será el SKU (ej: A001)
                upload_preset = PRESET_NAME,
                overwrite = True,
                resource_type = "image"
            )
            
            print(f"✅ Vinculado con éxito. URL: {respuesta.get('secure_url')}\n")
            
        except Exception as e:
            print(f"❌ Error al procesar el ítem {nombre_archivo}: {str(e)}\n")

    print("🏁 Proceso de migración masiva finalizado.")

if __name__ == "__main__":
    iniciar_migración_estructurada()