# 🛒 Outlet PROESA — Sistema de Pedidos

Sistema de gestión de pedidos con interfaz pública para empleados y dashboard para Trade Marketing.

## 📋 Estructura

```
PROYECTO_OUTLET/
├── app.py                      # Panel principal (Trade Marketing)
├── pages/
│   ├── registro.py            # Registro manual de pedidos
│   ├── pedido.py              # Interfaz pública para empleados
│   └── dashboard.py           # Dashboard consolidado
├── src/
│   ├── database.py            # Funciones de BD (Excel)
│   ├── logic.py               # Lógica de validación
│   ├── nav.py                 # Componente de navegación
│   └── sheets.py              # Funciones para Google Sheets (futuro)
├── data/
│   ├── inventario_maestro.xlsx        # Catálogo
│   ├── consolidado_pedidos.xlsx       # Pedidos manuales
│   └── pedidos_empleados.json         # Pedidos de empleados (Self-Service)
├── assets/
│   └── logo_proesa.png        # Logo de PROESA
└── requirements.txt           # Dependencias
```

## 🚀 Para Deployar en Streamlit Cloud

### 1. Crear repositorio en GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git push origin main
```

### 2. Ir a https://streamlit.io/cloud
- Haz sign up con tu cuenta
- Elige "New app"
- Selecciona tu repositorio y rama `main`
- Elige `app.py` como archivo principal
- Click en "Deploy"

### 3. Compartir el link público
Streamlit te dará un URL como:
```
https://tu-proyecto-outlet.streamlit.app
```

Comparte este link en el grupo de WhatsApp. Los empleados pueden:
- Ir a `/pedido` para hacer sus propios pedidos
- Los Trade Marketing van a `/` para el panel completo

## 🔑 Acceso

### Empleados (Público)
- **URL:** `https://tu-proyecto-outlet.streamlit.app/pedido`
- Login simple: Código Empleado + Nombre
- Pueden ver catálogo, hacer pedidos, editar pedidos previos
- Los pedidos se guardan en `data/pedidos_empleados.json`

### Trade Marketing (Privado — por ahora sin contraseña, agregar después)
- **URL:** `https://tu-proyecto-outlet.streamlit.app/` (panel principal)
- Acceso a: Panel, Registro Manual, Dashboard Consolidado
- Pueden ver todos los pedidos (manuales + empleados)

## 📝 Flujo de Trabajo

### Empleado:
1. Recibe link del grupo de WhatsApp
2. Entra a `/pedido`
3. Ingresa Código + Nombre
4. Selecciona productos y cantidad
5. Envía pedido
6. El pedido aparece en `pedidos_empleados.json`

### Trade Marketing:
1. Carga catálogo mensual en `app.py` (Excel)
2. Usa `/registro` para ingresar pedidos manuales o ver pedidos de empleados
3. Usa `/dashboard` para consolidado de todo
4. Exporta a CSV/Excel para facturación

## 🔄 Migración a Google Sheets (Futuro)

En lugar de `pedidos_empleados.json`, se puede guardar directamente en Google Sheets:

1. Crear credenciales en Google Cloud
2. Conectar con `gspread` o `google-auth`
3. Los pedidos se sincronizan en tiempo real
4. Trade Marketing ve todo actualizado automáticamente

## 📊 Variables de Entorno (Opcional para Google Sheets)

Si usas Google Sheets, agregar en Streamlit Cloud Secrets:

```toml
# .streamlit/secrets.toml (local)
[google_sheets]
GOOGLE_SHEETS_URL = "https://docs.google.com/spreadsheets/d/xxx"
SHEET_NAME = "Pedidos"

# En Streamlit Cloud: Settings > Secrets > Pega lo anterior
```

## ⚡ Performance Tips

- El Excel del inventario se carga en memoria (rápido)
- Los JSON de pedidos se usan para sincronización
- Para >10k pedidos, migra a Google Sheets

## 🆘 Troubleshooting

**"No se encuentra inventario maestro"**
- Verifica que `data/inventario_maestro.xlsx` existe

**"Error al guardar pedido"**
- Verifica permisos en carpeta `data/`
- En Streamlit Cloud, los datos persisten en la carpeta de la app

**"Empleados ven mensaje de 'Catálogo no disponible'"**
- Sube el Excel a través de `app.py` primero
- O copia `inventario_maestro.xlsx` a tu repositorio

## 📞 Soporte

Para agregar contraseñas, webhooks a WhatsApp, o migrar a Google Sheets, contáctame.