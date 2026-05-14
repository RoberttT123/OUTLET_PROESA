import streamlit as st
import base64
import os

def get_logo_b64(path="assets/logo_proesa.png"):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return None


def render_nav(active_page: str = "inicio", inventario_df=None):
    """
    Renderiza la barra lateral de navegación.
    active_page: "inicio" | "registro"
    inventario_df: DataFrame del inventario (opcional)
    """

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@500&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

    /* Botón colapsar sidebar — ícono correcto */
    [data-testid="stSidebarContent"] {
    padding-top: 0rem !important;
    }

    /* Ajustar el contenedor de los elementos para que peguen arriba */
    [data-testid="stSidebarUserContent"] {
        padding-top: 0.5rem !important;
    }
    [data-testid="stSidebarCollapseButton"] button {
        background: transparent !important;
        border: none !important;
        color: #3A4A6A !important;
        transition: color 0.15s !important;
    }
    [data-testid="stSidebarCollapseButton"] button:hover {
        color: #8899BB !important;
        background: rgba(255,255,255,0.06) !important;
        border-radius: 6px !important;
    }
    [data-testid="stSidebarCollapseButton"] button span {
        font-family: 'Material Symbols Rounded' !important;
        font-size: 1.3rem !important;
        color: #3A4A6A !important;
    }
    

    /* Sidebar shell */
    [data-testid="stSidebar"] {
        background: #0F0F1E !important;
        border-right: 1px solid #1E1E35 !important;
        min-width: 240px !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        padding: 0 !important;
    }
    [data-testid="stSidebarNav"] { display: none !important; }



    /* Tipografía global sidebar */
    [data-testid="stSidebar"] *,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label {
        font-family: 'DM Sans', sans-serif !important;
        color: #B0BAD0 !important;
    }

    /* page_link: estado normal */
    [data-testid="stSidebar"] [data-testid="stPageLink"] {
        margin: 2px 12px !important;
        border-radius: 9px !important;
        overflow: hidden;
    }
    [data-testid="stSidebar"] [data-testid="stPageLink"] a {
        display: flex !important;
        align-items: center !important;
        padding: 0.55rem 0.9rem !important;
        border-radius: 9px !important;
        border-left: 3px solid transparent !important;
        font-size: 0.875rem !important;
        font-weight: 500 !important;
        color: #9AA3BA !important;
        text-decoration: none !important;
        background: transparent !important;
        transition: all 0.15s ease !important;
    }
    [data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {
        background: rgba(255,255,255,0.06) !important;
        color: #E0E6F0 !important;
        border-left-color: rgba(230,57,70,0.4) !important;
    }

    /* page_link: activo */
    [data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] {
        background: rgba(230,57,70,0.12) !important;
        border-left: 3px solid #E63946 !important;
        color: #FF7A84 !important;
        font-weight: 700 !important;
    }

    /* Métricas */
    [data-testid="stSidebar"] [data-testid="stMetric"] {
        background: rgba(255,255,255,0.035) !important;
        border: 1px solid #1E1E38 !important;
        border-radius: 10px !important;
        padding: 0.55rem 0.8rem !important;
    }
    [data-testid="stSidebar"] [data-testid="stMetricValue"] {
        color: #FFFFFF !important;
        font-family: 'DM Mono', monospace !important;
        font-size: 1.35rem !important;
        font-weight: 600 !important;
    }
    [data-testid="stSidebar"] [data-testid="stMetricLabel"] p {
        color: #556080 !important;
        font-size: 0.68rem !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        font-weight: 700 !important;
    }

    /* Botón Reset */
    [data-testid="stSidebar"] .stButton > button {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid #252540 !important;
        color: #8899BB !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        border-radius: 8px !important;
        width: 100% !important;
        padding: 0.5rem 1rem !important;
        transition: all 0.15s !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(230,57,70,0.1) !important;
        border-color: rgba(230,57,70,0.5) !important;
        color: #FF7A84 !important;
    }

    /* Divisores */
    [data-testid="stSidebar"] hr {
        border: none !important;
        border-top: 1px solid #1A1A32 !important;
        margin: 0.5rem 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    with st.sidebar:

        # Logo
# Logo Centrado y más arriba
        logo_b64 = get_logo_b64()
        if logo_b64:
            st.markdown(f"""
            <div style="padding: 0.1rem 1rem 1rem; /* Reducido de 1.4rem a 0.5rem */
                        border-bottom: 1px solid #1A1A32;
                        margin-bottom: 0.25rem;
                        text-align: center;">
                <img src="data:image/png;base64,{logo_b64}"
                     style="width: 85%; max-height: 150px; /* Un poco más grande */
                            object-fit: contain; margin: 0 auto;">
                <div style="margin-top: 0.6rem; font-size: 0.65rem; font-weight: 700;
                            text-transform: uppercase; letter-spacing: 2.5px; color: #3A4A6A;">
                    SISTEMA DE PEDIDOS
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Caso sin logo (texto centrado)
            st.markdown("""
            <div style="padding: 1.4rem 1rem 1rem;
                        border-bottom: 1px solid #1A1A32; 
                        margin-bottom: 0.25rem;
                        text-align: center;">
                <div style="font-size: 1.1rem; font-weight: 700; color: #FFFFFF;">
                    Outlet PROESA
                </div>
                <div style="font-size: 0.62rem; font-weight: 700; text-transform: uppercase;
                            letter-spacing: 2.5px; color: #3A4A6A; margin-top: 0.3rem;">
                    SISTEMA DE PEDIDOS
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Navegación
        st.markdown("""
        <div style="font-size:0.6rem; font-weight:800; text-transform:uppercase;
                    letter-spacing:2px; color:#2A3560;
                    padding:0.9rem 1.1rem 0.35rem;">
            NAVEGACIÓN
        </div>
        """, unsafe_allow_html=True)

        st.page_link("app.py",             label="📦  Panel de Control")
        st.page_link("pages/registro.py",  label="📝  Registro Manual")
        st.page_link("pages/dashboard.py", label="📊  Dashboard Consolidado")

        st.markdown("<hr style='margin:0.75rem 0'>", unsafe_allow_html=True)

        # Inventario stats
        if inventario_df is not None:
            st.markdown("""
            <div style="font-size:0.6rem; font-weight:800; text-transform:uppercase;
                        letter-spacing:2px; color:#2A3560;
                        padding:0.5rem 1.1rem 0.35rem;">
                INVENTARIO
            </div>
            """, unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            total   = len(inventario_df)
            agotado = int((inventario_df.iloc[:, 3] <= 0).sum())
            bajo    = int(((inventario_df.iloc[:, 3] > 0) & (inventario_df.iloc[:, 3] <= 5)).sum())

            col1.metric("Productos", f"{total:,}")
            col2.metric("Agotados",  agotado)

            if bajo > 0:
                st.markdown(f"""
                <div style="margin:0.4rem 0.75rem 0;
                            background:rgba(244,162,97,0.1);
                            border:1px solid rgba(244,162,97,0.25);
                            border-radius:8px; padding:0.45rem 0.75rem;
                            font-size:0.75rem; color:#C4823A !important;">
                    ⚠️  <strong style="color:#C4823A !important;">{bajo}</strong>
                    productos con stock bajo (≤5 ud.)
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<hr style='margin:0.75rem 0'>", unsafe_allow_html=True)

        # Gestión
        st.markdown("""
        <div style="font-size:0.6rem; font-weight:800; text-transform:uppercase;
                    letter-spacing:2px; color:#2A3560;
                    padding:0.5rem 1.1rem 0.35rem;">
            GESTIÓN
        </div>
        """, unsafe_allow_html=True)

        PATH_INV = "data/inventario_maestro.xlsx"
        if os.path.exists(PATH_INV):
            if st.button("🔄  Resetear para Nuevo Mes"):
                os.remove(PATH_INV)
                st.rerun()

        # Footer
        st.markdown("""
        <div style="margin-top:2.5rem; padding:1rem 1.1rem 1rem;
                    border-top:1px solid #141425; text-align:center;">
            <div style="font-size:0.65rem; color:#1E2440; line-height:1.7;">
                Outlet PROESA &nbsp;·&nbsp; v1.0<br>Trade Marketing
            </div>
        </div>
        """, unsafe_allow_html=True)