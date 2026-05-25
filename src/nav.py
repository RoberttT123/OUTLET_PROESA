import streamlit as st
import pandas as pd
import base64
import os


@st.cache_data(show_spinner=False)
def get_logo_b64(path="assets/logo_proesa.png"):
    """Carga el logo UNA sola vez y lo cachea para toda la sesión."""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return None


@st.cache_data(show_spinner=False)
def _calcular_stats_inventario(df: pd.DataFrame) -> dict:
    """
    Calcula stats del inventario cacheados por contenido del DataFrame.
    @st.cache_data hashea el DataFrame automáticamente — solo recalcula
    si los datos cambiaron. NO accede a st.session_state (no permitido
    dentro de funciones cacheadas).
    """
    try:
        stock_num = pd.to_numeric(
            df.iloc[:, 3].astype(str).str.replace(",", "", regex=False).str.strip(),
            errors="coerce",
        ).fillna(0)
        return {
            "total":   len(df),
            "agotado": int((stock_num <= 0).sum()),
            "bajo":    int(((stock_num > 0) & (stock_num <= 5)).sum()),
        }
    except Exception:
        return {"total": len(df), "agotado": 0, "bajo": 0}


def render_nav(active_page: str = "inicio", inventario_df=None):
    """
    Renderiza la barra lateral de navegación.
    active_page : "inicio" | "registro" | "dashboard"
    inventario_df : DataFrame del inventario (opcional)

    NOTA: el bloque CSS debe re-inyectarse en cada render porque Streamlit
    reconstruye la página completa en cada rerun. El flag de session_state
    fue eliminado — era la causa de que la sidebar desapareciera.
    """

    # ── CSS: se inyecta en cada render (requerido por Streamlit) ─────────────
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@500&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

    [data-testid="stSidebarContent"] { padding-top: 0rem !important; }
    [data-testid="stSidebarUserContent"] { padding-top: 0.5rem !important; }

    [data-testid="stSidebarCollapseButton"] button {
        background: transparent !important; border: none !important;
        color: #3A4A6A !important; transition: color 0.15s !important;
    }
    [data-testid="stSidebarCollapseButton"] button:hover {
        color: #8899BB !important;
        background: rgba(255,255,255,0.06) !important;
        border-radius: 6px !important;
    }
    [data-testid="stSidebarCollapseButton"] button span {
        font-family: 'Material Symbols Rounded' !important;
        font-size: 1.3rem !important; color: #3A4A6A !important;
    }

    [data-testid="stSidebar"] {
        background: #0F0F1E !important;
        border-right: 1px solid #1E1E35 !important;
        min-width: 240px !important;
    }
    [data-testid="stSidebar"] > div:first-child { padding: 0 !important; }
    [data-testid="stSidebarNav"] { display: none !important; }

    [data-testid="stSidebar"] *,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label {
        font-family: 'DM Sans', sans-serif !important;
        color: #B0BAD0 !important;
    }

    [data-testid="stSidebar"] [data-testid="stPageLink"] {
        margin: 2px 12px !important; border-radius: 9px !important; overflow: hidden;
    }
    [data-testid="stSidebar"] [data-testid="stPageLink"] a {
        display: flex !important; align-items: center !important;
        padding: 0.55rem 0.9rem !important; border-radius: 9px !important;
        border-left: 3px solid transparent !important;
        font-size: 0.875rem !important; font-weight: 500 !important;
        color: #9AA3BA !important; text-decoration: none !important;
        background: transparent !important; transition: all 0.15s ease !important;
    }
    [data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {
        background: rgba(255,255,255,0.06) !important;
        color: #E0E6F0 !important;
        border-left-color: rgba(230,57,70,0.4) !important;
    }
    [data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] {
        background: rgba(230,57,70,0.12) !important;
        border-left: 3px solid #E63946 !important;
        color: #FF7A84 !important; font-weight: 700 !important;
    }

    [data-testid="stSidebar"] [data-testid="stMetric"] {
        background: rgba(255,255,255,0.035) !important;
        border: 1px solid #1E1E38 !important;
        border-radius: 10px !important; padding: 0.55rem 0.8rem !important;
    }
    [data-testid="stSidebar"] [data-testid="stMetricValue"] {
        color: #FFFFFF !important;
        font-family: 'DM Mono', monospace !important;
        font-size: 1.35rem !important; font-weight: 600 !important;
    }
    [data-testid="stSidebar"] [data-testid="stMetricLabel"] p {
        color: #556080 !important; font-size: 0.68rem !important;
        text-transform: uppercase !important; letter-spacing: 1px !important;
        font-weight: 700 !important;
    }

    [data-testid="stSidebar"] .stButton > button {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid #252540 !important; color: #8899BB !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.82rem !important; font-weight: 500 !important;
        border-radius: 8px !important; width: 100% !important;
        padding: 0.5rem 1rem !important; transition: all 0.15s !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(230,57,70,0.1) !important;
        border-color: rgba(230,57,70,0.5) !important; color: #FF7A84 !important;
    }

    [data-testid="stSidebar"] hr {
        border: none !important; border-top: 1px solid #1A1A32 !important;
        margin: 0.5rem 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    with st.sidebar:

        # ── LOGO (cacheado en disco, no toca disco en reruns) ────────────────
        logo_b64 = get_logo_b64()
        if logo_b64:
            st.markdown(f"""
            <div style="padding:0.1rem 1rem 1rem;border-bottom:1px solid #1A1A32;
                        margin-bottom:0.25rem;text-align:center;">
                <img src="data:image/png;base64,{logo_b64}"
                     style="width:85%;max-height:150px;object-fit:contain;margin:0 auto;">
                <div style="margin-top:0.6rem;font-size:0.65rem;font-weight:700;
                            text-transform:uppercase;letter-spacing:2.5px;color:#3A4A6A;">
                    SISTEMA DE PEDIDOS
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="padding:1.4rem 1rem 1rem;border-bottom:1px solid #1A1A32;
                        margin-bottom:0.25rem;text-align:center;">
                <div style="font-size:1.1rem;font-weight:700;color:#FFFFFF;">Outlet PROESA</div>
                <div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;
                            letter-spacing:2.5px;color:#3A4A6A;margin-top:0.3rem;">
                    SISTEMA DE PEDIDOS
                </div>
            </div>
            """, unsafe_allow_html=True)

        # ── NAVEGACIÓN ───────────────────────────────────────────────────────
        st.markdown("""
        <div style="font-size:0.6rem;font-weight:800;text-transform:uppercase;
                    letter-spacing:2px;color:#2A3560;padding:0.9rem 1.1rem 0.35rem;">
            NAVEGACIÓN
        </div>
        """, unsafe_allow_html=True)

        st.page_link("app.py",             label="📦  Panel de Control")
        st.page_link("pages/registro.py",  label="📝  Registro Manual")
        st.page_link("pages/dashboard.py", label="📊  Dashboard Consolidado")

        st.markdown("<hr style='margin:0.75rem 0'>", unsafe_allow_html=True)

        # ── STATS DE INVENTARIO (cacheados por contenido del df) ─────────────
        df_stats = inventario_df if inventario_df is not None \
                   else st.session_state.get("df_inventario_maestro")

        if df_stats is not None and not df_stats.empty:
            stats = _calcular_stats_inventario(df_stats)

            st.markdown("""
            <div style="font-size:0.6rem;font-weight:800;text-transform:uppercase;
                        letter-spacing:2px;color:#2A3560;padding:0.5rem 1.1rem 0.35rem;">
                INVENTARIO
            </div>
            """, unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            col1.metric("Productos", f"{stats['total']:,}")
            col2.metric("Agotados",  stats["agotado"])

            if stats["bajo"] > 0:
                st.markdown(f"""
                <div style="margin:0.4rem 0.75rem 0;
                            background:rgba(244,162,97,0.1);
                            border:1px solid rgba(244,162,97,0.25);
                            border-radius:8px;padding:0.45rem 0.75rem;
                            font-size:0.75rem;color:#C4823A !important;">
                    ⚠️ <strong style="color:#C4823A !important;">{stats['bajo']}</strong>
                    productos con stock bajo (≤5 ud.)
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<hr style='margin:0.75rem 0'>", unsafe_allow_html=True)

        # ── GESTIÓN ──────────────────────────────────────────────────────────
        st.markdown("""
        <div style="font-size:0.6rem;font-weight:800;text-transform:uppercase;
                    letter-spacing:2px;color:#2A3560;padding:0.5rem 1.1rem 0.35rem;">
            GESTIÓN
        </div>
        """, unsafe_allow_html=True)

        if os.path.exists("data/inventario_maestro.xlsx"):
            if st.button("🔄  Resetear para Nuevo Mes"):
                try:
                    os.remove("data/inventario_maestro.xlsx")
                except Exception:
                    pass
                for key in ["df_inventario_maestro", "inv_cloud_timestamp"]:
                    st.session_state.pop(key, None)
                st.cache_data.clear()
                st.rerun()

        # ── FOOTER ───────────────────────────────────────────────────────────
        st.markdown("""
        <div style="margin-top:2.5rem;padding:1rem 1.1rem 1rem;
                    border-top:1px solid #141425;text-align:center;">
            <div style="font-size:0.65rem;color:#1E2440;line-height:1.7;">
                Outlet PROESA &nbsp;·&nbsp; v1.0<br>Trade Marketing
            </div>
        </div>
        """, unsafe_allow_html=True)