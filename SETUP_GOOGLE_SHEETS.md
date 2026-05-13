# 🔧 Guía de Configuración — Google Sheets

Esta guía te ayudará a configurar el sistema para usar Google Sheets como base de datos.

## ✅ Paso 1: Crear las Google Sheets

### 1.1 Inventario
1. Ve a [Google Sheets](https://sheets.google.com)
2. Crea una nueva hoja (botón "+ Crear")
3. Nómbrala: `Inventario_Outlet_PROESA`
4. En la primera fila, agrega estos encabezados:
   ```
   Línea | Código Producto | Nombre Producto | Stock | Precio Unitario | Empresa
   ```
5. **Copia la URL** de la barra de direcciones (sin `#gid=0` si está)

### 1.2 Pedidos
1. Crea otra Google Sheet: `Pedidos_Outlet_PROESA`
2. Primera fila con encabezados:
   ```
   Fecha | Código Empleado | Nombre Empleado | Código Producto | Nombre Producto | Cantidad | Precio Unitario | Subtotal | Estado
   ```
3. **Copia la URL**

### 1.3 (Opcional) Usar ambas hojas en un mismo archivo
- En lugar de 2 archivos, puedes tener 1 con 2 pestañas
- Crea ambas hojas en el mismo Google Sheets
- Las URLs serán iguales, solo cambia el nombre de la hoja

---

## 🔐 Paso 2: Obtener Credenciales de Google Cloud

### 2.1 Crear proyecto en Google Cloud Console
1. Ve a [Google Cloud Console](https://console.cloud.google.com)
2. **Crear un nuevo proyecto** (arriba a la derecha)
3. Dale un nombre: `Outlet PROESA`
4. Espera a que se cree

### 2.2 Habilitar Google Sheets API
1. Ve a "APIs y Servicios" → "Biblioteca"
2. Busca **"Google Sheets API"**
3. Haz clic en él
4. Presiona **"HABILITAR"**

### 2.3 Crear cuenta de servicio
1. Ve a "APIs y Servicios" → "Credenciales"
2. Haz clic en **"+ CREAR CREDENCIALES"**
3. Selecciona **"Cuenta de servicio"**
4. Llena el nombre: `outlet-proesa`
5. Click en "CREAR Y CONTINUAR"
6. Skip las opciones adicionales (click en "CONTINUAR")
7. Click en "LISTO"

### 2.4 Obtener la clave JSON
1. Ve a "Cuentas de Servicio" (en el menú izquierdo)
2. Haz clic en la cuenta que acabas de crear
3. Ve a la pestaña **"CLAVES"**
4. Haz clic en **"+ AGREGAR CLAVE"** → **"Crear clave nueva"**
5. Selecciona **"JSON"** → **"CREAR"**
6. Se descargará un archivo `proyecto-nombre.json`
7. **Guarda este archivo en tu proyecto** como `credentials.json`

---

## ⚙️ Paso 3: Configurar el Proyecto

### 3.1 Colocar credenciales
1. Copia el archivo `proyecto-nombre.json` descargado
2. Renómbralo a `credentials.json`
3. Colócalo en la raíz de tu proyecto (`PROYECTO_OUTLET/credentials.json`)

### 3.2 Crear `config.py`
1. Copia `config.example.py` a `config.py`
2. Llena las URLs:
   ```python
   INVENTARIO_SHEET_URL = "https://docs.google.com/spreadsheets/d/AQUI_TU_SHEET_ID/edit"
   PEDIDOS_SHEET_URL = "https://docs.google.com/spreadsheets/d/AQUI_TU_SHEET_ID/edit"
   ```

### 3.3 Compartir Google Sheets con la cuenta de servicio
1. Abre tu `credentials.json` en un editor de texto
2. Busca el campo `"client_email"` — copia ese email
3. Ve a tu Google Sheet del Inventario
4. Presiona **"Compartir"** (arriba a la derecha)
5. Pega el email de la cuenta de servicio
6. Dale permisos de **"Editor"**
7. Repite para la Google Sheet de Pedidos

---

## 🚀 Paso 4: Prueba Local

```bash
# Instala dependencias
pip install -r requirements.txt

# Corre la app
streamlit run app.py

# Ve a http://localhost:8501/pedido
# Prueba hacer un pedido
```

Si todo funciona, los pedidos deben aparecer en tu Google Sheet de Pedidos en tiempo real.

---

## ☁️ Paso 5: Desplegar en Streamlit Cloud

### 5.1 Con credenciales en Streamlit Secrets
En lugar de guardar `credentials.json` en el repo:

1. Ve a tu app en [Streamlit Cloud](https://share.streamlit.io)
2. Settings → **Secrets**
3. Pega el contenido de `credentials.json` así:
   ```toml
   [google_service_account]
   type = "service_account"
   project_id = "..."
   private_key_id = "..."
   private_key = "..."
   client_email = "..."
   client_id = "..."
   auth_uri = "..."
   token_uri = "..."
   auth_provider_x509_cert_url = "..."
   client_x509_cert_url = "..."
   ```
4. Copia todo tal como está en el JSON

---

## 🆘 Troubleshooting

**"Error: PERMISSION_DENIED"**
- Verifica que compartiste la Google Sheet con el email de `credentials.json`
- Asegúrate de que tiene permisos de "Editor"

**"Error: Worksheet not found"**
- Verifica que el nombre de la hoja (`INVENTARIO_HOJA_NAME`) coincida exactamente
- Las mayúsculas importan: "Inventario" ≠ "inventario"

**"No se descarga `credentials.json`"**
- Ve a Google Cloud Console → APIs y Servicios → Credenciales
- Haz clic en la Cuenta de Servicio
- Tab "CLAVES" → Crea una nueva si no existe

**En Streamlit Cloud: "No conectado a Google Sheets"**
- Verifica que los Secrets estén configurados correctamente
- Copia todo el JSON, no solo partes

---

## 📊 Estructura esperada de datos

### Inventario (Google Sheet)
| Línea | Código Producto | Nombre Producto | Stock | Precio Unitario | Empresa |
|-------|-----------------|-----------------|-------|-----------------|---------|
| 3M    | 110177          | LIMPIADOR DE BOTELLAS | 230 | 18.53 | PROESA |

### Pedidos (Google Sheet)
| Fecha | Código Empleado | Nombre Empleado | Código Producto | Nombre Producto | Cantidad | Precio Unitario | Subtotal | Estado |
|-------|-----------------|-----------------|-----------------|-----------------|----------|-----------------|----------|--------|
| 12/05/2026 10:30 | E0200491 | Andrea Chavez | 110177 | LIMPIADOR | 1 | 18.53 | 18.53 | Pendiente |

---

¿Preguntas? Revisa el README.md o los comentarios en el código.