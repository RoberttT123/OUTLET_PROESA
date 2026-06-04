# -*- coding: utf-8 -*-
"""
PUNTO DE ENTRADA - OUTLET PROESA
----------------------------------
Solo gestiona configuración global y definición de rutas.
No contiene lógica de negocio ni contenido visual propio.

P�ginas administración : inicio, dashboard, registro
P�ginas empleados      : pedido

NOTA: Requiere Streamlit >= 1.36.0 para st.navigation() y st.Page().
"""

import streamlit as st

# ── Configuración global ──────────────────────────────────────────────────────
# set_page_config debe estar UNA SOLA VEZ en toda la app.
# Eliminarlo de cualquier page individual donde estuviera antes.
st.set_page_config(
    page_title="Outlet PROESA",
    layout="wide",
    page_icon="📦",
    initial_sidebar_state="expanded",
)

# ── CSS global de navegación ──────────────────────────────────────────────────
try:
    from src.nav import inject_nav_css
    inject_nav_css()
except ImportError:
    pass

# ── Definición de rutas ───────────────────────────────────────────────────────
inicio    = st.Page("pages/inicio.py",    title="Inicio",    icon="🏠", default=True)
dashboard = st.Page("pages/dashboard.py", title="Dashboard", icon="📊")
registro  = st.Page("pages/registro.py",  title="Registro",  icon="📝")
pedido    = st.Page("pages/pedido.py",    title="Mi Pedido", icon="🛒")

pg = st.navigation(
    {
        "Administración": [inicio, dashboard, registro],
        "Empleados":      [pedido],
    },
    position="hidden",   # La navegación visual la gestiona src/nav.py
)

pg.run()