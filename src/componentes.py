# -*- coding: utf-8 -*-
"""
MÓDULO DE COMPONENTES VISUALES Y ESTILOS - OUTLET PROESA
----------------------------------------------------------------
Este archivo centraliza la capa de presentación de la aplicación.
Inyecta el diseño CSS corporativo y construye las tarjetas de productos
y elementos del carrito en formato HTML interpretado.

Desarrollado para: PROYECTO_OUTLET
Última actualización: Mayo 2026
"""

import streamlit as st

def cargar_estilos_css():
    """
    Inyecta los estilos CSS globales y de la interfaz del carrito.
    Configura tipografías, geometría adaptativa Mobile-First, y oculta
    los componentes por defecto de la interfaz de desarrollo de Streamlit.
    """
    st.markdown("""
    <style>
    /* ── IMPORTACIÓN DE FUENTES CORPORATIVAS ── */
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@500&display=swap');

    /* ── CONFIGURACIÓN DEL LIENZO GLOBAL ── */
    html, body, [class*="css"] { 
        font-family: 'DM Sans', sans-serif; 
    }
    
    .stApp { 
        background: #F5F4F0; 
    }
    
    /* Optimización de márgenes y paddings para pantallas móviles */
    .block-container {
        padding-top: 0.2rem !important;
        padding-bottom: 0rem !important;
    }

    /* ── ENTORNO DE INICIO DE SESIÓN (HERO LOGIN) ── */
    .hero-login {
        background: linear-gradient(135deg, #1A1A2E 0%, #0F3460 100%);
        border-radius: 20px;
        padding: 2.5rem 2.5rem;
        margin-bottom: 2rem;
        text-align: center;
        color: white;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 140px;
        box-shadow: 0 10px 25px rgba(15, 52, 96, 0.2);
    }
    
    .hero-login h1 {
        font-size: 2.2rem;
        font-weight: 700;
        margin: 0 0 0.5rem;
    }
    
    .hero-login p {
        font-size: 1rem;
        opacity: 0.9;
        margin: 0;
    }

    /* ── ENCABEZADO DE LA APLICACIÓN PRINCIPAL (HEADER) ── */
    .page-header {
        background: white;
        border-radius: 16px;
        padding: 1.5rem 2rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        display: flex;
        align-items: center;
        gap: 1rem;
        border-top: 4px solid #E63946;
    }
    
    .page-header h2 { 
        color: #1A1A2E; 
        font-size: 1.5rem; 
        margin: 0; 
    }
    
    .page-header p { 
        color: #888; 
        margin: 0.2rem 0 0; 
        font-size: 0.9rem;
    }

    /* ── SEPARADORES Y TÍTULOS DE SECCIÓN ── */
    .section-title {
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        color: #AAA;
        margin: 1.5rem 0 0.5rem;
        padding-bottom: 0.4rem;
        border-bottom: 2px solid #EBEBEB;
    }

    /* ── DISEÑO CLONADO DEL CARRITO (ESTILO E-COMMERCE MÓVIL) ── */
    .contenedor-carrito {
        background: white;
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.04);
        margin-bottom: 1rem;
    }

    .item-carrito-flex {
        display: flex;
        align-items: center;
        gap: 1rem;
        width: 100%;
    }

    .item-carrito-img {
        width: 65px;
        height: 65px;
        background: #FAFAFA;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0.2rem;
        flex-shrink: 0;
        border: 1px solid #EBEBEB;
    }
    
    .item-carrito-img img {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
    }

    .item-carrito-detalles {
        flex-grow: 1;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    
    .item-carrito-titulo {
        font-size: 0.95rem;
        font-weight: 600;
        color: #2B423B;
        margin: 0 0 2px 0;
        line-height: 1.2rem;
    }

    .item-carrito-precio {
        font-size: 1.1rem;
        font-weight: 700;
        color: #0A3225;
        text-align: right;
        font-family: 'DM Mono', monospace;
        white-space: nowrap;
    }

    /* Resumen inferior del totalizado */
    .carrito-total-clon {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1.5rem 0.5rem;
        font-family: 'DM Sans', sans-serif;
    }
    
    .carrito-total-clon .label-total {
        font-size: 1.3rem;
        font-weight: 700;
        color: #0A3225;
    }
    
    .carrito-total-clon .monto-total {
        font-size: 1.6rem;
        font-weight: 700;
        color: #0A3225;
        font-family: 'DM Mono', monospace;
    }

    /* ── MAQUETACIÓN DE TARJETAS DEL CATÁLOGO (GRID) ── */
    .card-producto {
        background: white;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.5rem;
        box-shadow: 0 4px 10px rgba(0,0,0,0.03);
        border: 1px solid #EBEBEB;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        height: 100%;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    .card-producto:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 15px rgba(0,0,0,0.06);
    }
    
    .card-img-container {
        text-align: center;
        padding: 0.5rem;
        background: #FAFAFA;
        border-radius: 8px;
        margin-bottom: 0.8rem;
        height: 120px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .card-img-container img { 
        height: 110px; 
        max-width: 100%; 
        object-fit: contain; 
    }

    /* ── BADGES DE ESTADO DE INVENTARIO (STOCK) ── */
    .stock-ok { background: #D1FAE5; color: #065F46; border-radius: 20px; padding: 4px 12px; font-size: 0.75rem; font-weight: 600; display: inline-block; }
    .stock-warn { background: #FEF9C3; color: #854D0E; border-radius: 20px; padding: 4px 12px; font-size: 0.75rem; font-weight: 600; display: inline-block; }
    .stock-out { background: #FEE2E2; color: #991B1B; border-radius: 20px; padding: 4px 12px; font-size: 0.75rem; font-weight: 600; display: inline-block; }

    /* ── REMOCIÓN DE ELEMENTOS NATIVOS DE STREAMLIT (UI CLEANUP) ── */
    #MainMenu, header, footer { visibility: hidden; }
    .stAppViewContainer footer { display: none !important; }
    footer { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    .reportview-container footer { display: none !important; }
    [data-testid="stToolbar"] { display: none !important; }
    .stDeployButton { display: none !important; }
    div[data-testid="stAppViewContainer"] > footer { display: none !important; }
    
    /* Forzar diseño alineado en los selectores numéricos */
    div[data-testid="stNumberInput"] {
        margin-top: 0px !important;
    }
    </style>
    """, unsafe_allow_html=True)


def render_tarjeta_producto(codigo: str, nombre: str, precio: float, stock_badge: str, url_foto: str):
    """
    Construye y renderiza el bloque HTML correspondiente a la tarjeta del catálogo.
    Usa st.markdown de forma directa para asegurar su interpretación en el DOM.
    """
    if not url_foto or not isinstance(url_foto, str) or url_foto.strip() == "":
        url_final = "https://images.unsplash.com/photo-1544476915-ed1370594142?w=150"
    else:
        url_final = url_foto

    html_tarjeta = f"""
    <div class="card-producto">
        <div class="card-img-container">
            <img src="{url_final}" alt="{nombre}">
        </div>
        <div style="min-height: 50px;">
            <span style="font-size:0.75rem; color:#888; font-family:'DM Mono', monospace; display:block; margin-bottom:1px;">
                SKU: {codigo}
            </span>
            <h4 style="margin: 0px 0 3px 0; font-size:0.95rem; font-weight:600; line-height:1.2rem; color:#1A1A2E;">
                {nombre}
            </h4>
        </div>
        <div style="margin-top: auto; padding-top: 5px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <span style="font-size:1.15rem; font-weight:700; color:#1A1A2E; font-family:'DM Mono', monospace;">
                    Bs {precio:,.2f}
                </span>
            </div>
            <div style="margin-bottom: 2px;">
                {stock_badge}
            </div>
        </div>
    </div>
    """
    st.markdown(html_tarjeta, unsafe_allow_html=True)


def render_estructura_item_carrito(nombre: str, precio_total: float, url_foto: str):
    """
    Construye el segmento de la estructura interna del item del carrito 
    (Imagen, Título y Precio a la derecha) alineado con flexbox.
    Retorna la cadena HTML lista para ser renderizada en conjunto con los inputs de control.
    """
    if not url_foto or not isinstance(url_foto, str) or url_foto.strip() == "":
        url_final = "https://images.unsplash.com/photo-1544476915-ed1370594142?w=150"
    else:
        url_final = url_foto

    html_item = f"""
    <div class="item-carrito-flex">
        <div class="item-carrito-img">
            <img src="{url_final}" alt="{nombre}">
        </div>
        <div class="item-carrito-detalles">
            <h4 class="item-carrito-titulo">{nombre}</h4>
        </div>
        <div class="item-carrito-precio">
            Bs {precio_total:,.2f}
        </div>
    </div>
    """
    return html_item