# -*- coding: utf-8 -*
"""
PUNTO DE ENTRADA - OUTLET PROESA
----------------------------------
...
"""

import streamlit as st

# ── Configuración global ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Outlet PROESA",
    layout="wide",
    page_icon="📦",
    initial_sidebar_state="expanded",
)

# ── INYECCIÓN GLOBAL PARA MARCA BLANCA (ELIMINAR LOGOS/FOOTER) ────────────────
st.markdown(
    """
    <style>
    header, .stAppHeader { visibility: hidden !important; display: none !important; }
    .stDecoration { display: none !important; }
    div[data-testid="stToolbar"] { visibility: hidden !important; display: none !important; }
    footer, div[data-testid="stFooter"] { visibility: hidden !important; display: none !important; }
    </style>
    """,
    unsafe_allow_html=True
)

# ── CSS global de navegación ──────────────────────────────────────────────────
try:
    from src.nav import inject_nav_css
    inject_nav_css()
except ImportError:
    pass

# ── Definición de rutas ───────────────────────────────────────────────────────
inicio = st.Page("pages/inicio.py", title="Inicio", icon="🏠")
dashboard = st.Page("pages/dashboard.py", title="Dashboard", icon="📊")
pedido    = st.Page("pages/pedido.py",    title="Mi Pedido", icon="🛒")

pg = st.navigation(
    {
        "Administración": [inicio, dashboard],
        "Empleados":      [pedido],
    },
    position="hidden",   # La navegación visual la gestiona src/nav.py
)

pg.run()