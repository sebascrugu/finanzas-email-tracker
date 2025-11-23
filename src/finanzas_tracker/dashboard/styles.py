"""
Sistema de estilos centralizado para el dashboard.

Proporciona estilos consistentes, animaciones y componentes UI reutilizables
para todas las páginas del dashboard.
"""

import streamlit as st


def inject_custom_css() -> None:
    """
    Inyecta CSS custom profesional en la página actual.

    Incluye:
    - Sistema de colores moderno
    - Animaciones suaves
    - Componentes estilizados (cards, buttons, alerts)
    - Responsive design
    - Microinteracciones
    """
    st.markdown(
        """
        <style>
        /* ============================================================
           VARIABLES DE COLOR - Paleta Profesional
           ============================================================ */
        :root {
            --primary: #667eea;
            --primary-dark: #5568d3;
            --primary-light: #f0f4ff;

            --success: #10b981;
            --success-dark: #059669;
            --success-light: #d1fae5;

            --warning: #f59e0b;
            --warning-dark: #d97706;
            --warning-light: #fef3c7;

            --danger: #ef4444;
            --danger-dark: #dc2626;
            --danger-light: #fee2e2;

            --info: #3b82f6;
            --info-dark: #2563eb;
            --info-light: #dbeafe;

            --gray-50: #f9fafb;
            --gray-100: #f3f4f6;
            --gray-200: #e5e7eb;
            --gray-300: #d1d5db;
            --gray-400: #9ca3af;
            --gray-500: #6b7280;
            --gray-600: #4b5563;
            --gray-700: #374151;
            --gray-800: #1f2937;
            --gray-900: #111827;

            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
        }

        /* ============================================================
           LAYOUT GENERAL
           ============================================================ */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1400px;
        }

        /* ============================================================
           METRIC CARDS - Diseño Moderno con Hover
           ============================================================ */
        div[data-testid="metric-container"] {
            background: white;
            border-radius: 16px;
            padding: 1.5rem 1.25rem;
            border: 1px solid var(--gray-100);
            box-shadow: var(--shadow-sm);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }

        div[data-testid="metric-container"]::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--primary), var(--primary-dark));
            transform: scaleX(0);
            transform-origin: left;
            transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        div[data-testid="metric-container"]:hover {
            box-shadow: var(--shadow-lg);
            transform: translateY(-4px);
            border-color: var(--gray-200);
        }

        div[data-testid="metric-container"]:hover::before {
            transform: scaleX(1);
        }

        div[data-testid="stMetricLabel"] {
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--gray-600);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }

        div[data-testid="stMetricValue"] {
            font-size: 2rem;
            font-weight: 800;
            color: var(--gray-900);
            line-height: 1.2;
        }

        div[data-testid="stMetricDelta"] {
            font-size: 0.875rem;
            font-weight: 500;
            margin-top: 0.5rem;
        }

        /* ============================================================
           BOTONES - Estilo Profesional
           ============================================================ */
        .stButton>button {
            border-radius: 12px;
            font-weight: 600;
            padding: 0.75rem 1.5rem;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            font-size: 0.95rem;
            border: none;
            box-shadow: var(--shadow-sm);
            letter-spacing: 0.025em;
        }

        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-md);
        }

        .stButton>button:active {
            transform: translateY(0);
            box-shadow: var(--shadow-sm);
        }

        /* Botón primario */
        .stButton>button[kind="primary"] {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: white;
        }

        .stButton>button[kind="primary"]:hover {
            background: linear-gradient(135deg, var(--primary-dark) 0%, var(--primary) 100%);
        }

        /* Botón secundario */
        .stButton>button[kind="secondary"] {
            background: white;
            border: 2px solid var(--gray-200);
            color: var(--gray-700);
        }

        .stButton>button[kind="secondary"]:hover {
            border-color: var(--primary);
            color: var(--primary);
        }

        /* ============================================================
           INPUTS Y FORMS - UX Mejorada
           ============================================================ */
        .stTextInput>div>div>input,
        .stNumberInput>div>div>input,
        .stSelectbox>div>div>select,
        .stTextArea>div>div>textarea {
            border-radius: 10px;
            border: 2px solid var(--gray-200);
            padding: 0.75rem 1rem;
            font-size: 0.95rem;
            transition: all 0.2s ease;
        }

        .stTextInput>div>div>input:focus,
        .stNumberInput>div>div>input:focus,
        .stSelectbox>div>div>select:focus,
        .stTextArea>div>div>textarea:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px var(--primary-light);
        }

        /* Labels mejorados */
        .stTextInput>label,
        .stNumberInput>label,
        .stSelectbox>label,
        .stTextArea>label {
            font-weight: 600;
            color: var(--gray-700);
            font-size: 0.9rem;
            margin-bottom: 0.5rem;
        }

        /* ============================================================
           PROGRESS BARS - Gradientes Modernos
           ============================================================ */
        .stProgress > div > div > div > div {
            background: linear-gradient(90deg, var(--success) 0%, var(--success-dark) 100%);
            border-radius: 10px;
            transition: all 0.3s ease;
        }

        /* ============================================================
           ALERTS - Diseño Card-like
           ============================================================ */
        .stAlert {
            border-radius: 12px;
            border: none;
            padding: 1.25rem 1.5rem;
            box-shadow: var(--shadow-sm);
        }

        .stAlert[data-baseweb="notification"][kind="info"] {
            background: var(--info-light);
            border-left: 4px solid var(--info);
        }

        .stAlert[data-baseweb="notification"][kind="success"] {
            background: var(--success-light);
            border-left: 4px solid var(--success);
        }

        .stAlert[data-baseweb="notification"][kind="warning"] {
            background: var(--warning-light);
            border-left: 4px solid var(--warning);
        }

        .stAlert[data-baseweb="notification"][kind="error"] {
            background: var(--danger-light);
            border-left: 4px solid var(--danger);
        }

        /* ============================================================
           EXPANDERS - Accordion Moderno
           ============================================================ */
        .streamlit-expanderHeader {
            background: var(--gray-50);
            border-radius: 10px;
            padding: 1rem 1.25rem;
            font-weight: 600;
            color: var(--gray-800);
            transition: all 0.2s ease;
            border: 1px solid var(--gray-100);
        }

        .streamlit-expanderHeader:hover {
            background: white;
            border-color: var(--primary);
            color: var(--primary);
        }

        .streamlit-expanderContent {
            border-radius: 0 0 10px 10px;
            padding: 1.25rem;
            border: 1px solid var(--gray-100);
            border-top: none;
        }

        /* ============================================================
           DATAFRAMES - Tabla Moderna
           ============================================================ */
        .stDataFrame {
            border-radius: 12px;
            overflow: hidden;
            box-shadow: var(--shadow);
        }

        /* ============================================================
           TABS - Diseño Clean
           ============================================================ */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
            background: transparent;
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 10px 10px 0 0;
            padding: 0.75rem 1.5rem;
            font-weight: 600;
            color: var(--gray-600);
            border: none;
            background: transparent;
            transition: all 0.2s ease;
        }

        .stTabs [data-baseweb="tab"]:hover {
            background: var(--gray-50);
            color: var(--gray-900);
        }

        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            background: white;
            color: var(--primary);
            border-bottom: 3px solid var(--primary);
        }

        /* ============================================================
           SIDEBAR - Minimalista
           ============================================================ */
        section[data-testid="stSidebar"] {
            background: var(--gray-50);
            border-right: 1px solid var(--gray-200);
        }

        section[data-testid="stSidebar"] .stSelectbox {
            background: white;
            border-radius: 10px;
            padding: 0.5rem;
        }

        /* ============================================================
           ANIMACIONES GLOBALES
           ============================================================ */
        @keyframes fadeIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateX(-10px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }

        @keyframes pulse {
            0%, 100% {
                opacity: 1;
            }
            50% {
                opacity: 0.8;
            }
        }

        /* Aplicar animación a elementos principales */
        .element-container {
            animation: fadeIn 0.5s ease-out;
        }

        /* ============================================================
           CHARTS - Bordes Redondeados
           ============================================================ */
        .stPlotlyChart,
        .element-container iframe {
            border-radius: 12px;
            box-shadow: var(--shadow-sm);
        }

        /* ============================================================
           HEADERS - Jerarquía Visual Clara
           ============================================================ */
        .main h1 {
            font-size: 2.5rem;
            font-weight: 800;
            color: var(--gray-900);
            margin-bottom: 1rem;
            line-height: 1.2;
        }

        .main h2 {
            font-size: 2rem;
            font-weight: 700;
            color: var(--gray-800);
            margin-top: 2rem;
            margin-bottom: 1rem;
        }

        .main h3 {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--gray-800);
            margin-top: 1.5rem;
            margin-bottom: 0.75rem;
        }

        .main h4 {
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--gray-700);
            margin-top: 1rem;
            margin-bottom: 0.5rem;
        }

        /* ============================================================
           DIVIDERS - Estilo Sutil
           ============================================================ */
        .main hr {
            margin: 2.5rem 0;
            border: none;
            border-top: 2px solid var(--gray-100);
        }

        /* ============================================================
           LOADING SPINNER - Personalizado
           ============================================================ */
        .stSpinner > div {
            border-color: var(--primary) var(--primary-light) var(--primary-light);
        }

        /* ============================================================
           TOAST NOTIFICATIONS (para futuro)
           ============================================================ */
        .stToast {
            border-radius: 12px;
            box-shadow: var(--shadow-xl);
        }

        /* ============================================================
           RESPONSIVE - Mobile First
           ============================================================ */
        @media (max-width: 768px) {
            .main .block-container {
                padding-top: 1rem;
                padding-left: 1rem;
                padding-right: 1rem;
            }

            div[data-testid="stMetricValue"] {
                font-size: 1.5rem;
            }

            .main h1 {
                font-size: 2rem;
            }

            .main h2 {
                font-size: 1.5rem;
            }
        }

        /* ============================================================
           UTILIDADES - Clases Helper
           ============================================================ */
        .text-center {
            text-align: center;
        }

        .text-muted {
            color: var(--gray-500);
        }

        .text-small {
            font-size: 0.875rem;
        }

        .font-weight-bold {
            font-weight: 700;
        }

        .mb-0 { margin-bottom: 0; }
        .mb-1 { margin-bottom: 0.5rem; }
        .mb-2 { margin-bottom: 1rem; }
        .mb-3 { margin-bottom: 1.5rem; }
        .mb-4 { margin-bottom: 2rem; }

        .mt-0 { margin-top: 0; }
        .mt-1 { margin-top: 0.5rem; }
        .mt-2 { margin-top: 1rem; }
        .mt-3 { margin-top: 1.5rem; }
        .mt-4 { margin-top: 2rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero_metric(
    value: str,
    label: str,
    subtitle: str | None = None,
    gradient: str = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
) -> None:
    """
    Renderiza una métrica hero con diseño destacado.

    Args:
        value: Valor principal a mostrar
        label: Etiqueta de la métrica
        subtitle: Subtítulo opcional
        gradient: Gradiente CSS para el fondo
    """
    subtitle_html = f"<p style='margin: 0; font-size: 1.1rem; opacity: 0.95;'>{subtitle}</p>" if subtitle else ""

    st.markdown(
        f"""
        <div style='
            text-align: center;
            padding: 3rem 2rem;
            background: {gradient};
            border-radius: 20px;
            margin: 2rem 0;
            box-shadow: 0 10px 40px rgba(102, 126, 234, 0.3);
            animation: fadeIn 0.6s ease-out;
        '>
            <p style='
                margin: 0 0 0.75rem 0;
                font-size: 0.95rem;
                text-transform: uppercase;
                letter-spacing: 2px;
                opacity: 0.9;
                color: white;
                font-weight: 600;
            '>
                {label}
            </p>
            <h1 style='
                color: white;
                font-size: 4rem;
                font-weight: 800;
                margin: 0;
                letter-spacing: -2px;
                line-height: 1;
            '>
                {value}
            </h1>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stat_card(
    icon: str,
    value: str,
    label: str,
    trend: str | None = None,
    trend_positive: bool = True,
    color: str = "primary",
) -> None:
    """
    Renderiza una tarjeta de estadística compacta.

    Args:
        icon: Emoji o icono
        value: Valor a mostrar
        label: Etiqueta
        trend: Tendencia opcional (ej: "+12%")
        trend_positive: Si la tendencia es positiva
        color: Color del tema (primary, success, warning, danger)
    """
    color_map = {
        "primary": "var(--primary)",
        "success": "var(--success)",
        "warning": "var(--warning)",
        "danger": "var(--danger)",
        "info": "var(--info)",
    }

    card_color = color_map.get(color, "var(--primary)")
    trend_color = "var(--success)" if trend_positive else "var(--danger)"
    trend_html = (
        f"<span style='color: {trend_color}; font-size: 0.875rem; font-weight: 600;'>{trend}</span>"
        if trend
        else ""
    )

    st.markdown(
        f"""
        <div style='
            background: white;
            border-radius: 16px;
            padding: 1.5rem;
            border-left: 4px solid {card_color};
            box-shadow: var(--shadow);
            transition: all 0.3s ease;
        ' onmouseover="this.style.transform='translateY(-4px)'; this.style.boxShadow='var(--shadow-lg)'"
           onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='var(--shadow)'">
            <div style='display: flex; align-items: center; gap: 1rem; margin-bottom: 0.75rem;'>
                <span style='font-size: 2rem;'>{icon}</span>
                <div>
                    <p style='margin: 0; color: var(--gray-600); font-size: 0.875rem; font-weight: 600; text-transform: uppercase;'>
                        {label}
                    </p>
                    <h3 style='margin: 0.25rem 0 0 0; color: var(--gray-900); font-size: 1.75rem; font-weight: 800;'>
                        {value}
                    </h3>
                </div>
            </div>
            {trend_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(title: str, subtitle: str | None = None, icon: str | None = None) -> None:
    """
    Renderiza un header de sección con estilo consistente.

    Args:
        title: Título de la sección
        subtitle: Subtítulo opcional
        icon: Emoji opcional
    """
    icon_html = f"<span style='margin-right: 0.5rem;'>{icon}</span>" if icon else ""
    subtitle_html = (
        f"<p style='color: var(--gray-500); font-size: 1.05rem; margin: 0.5rem 0 0 0;'>{subtitle}</p>"
        if subtitle
        else ""
    )

    st.markdown(
        f"""
        <div style='margin: 2.5rem 0 1.5rem 0;'>
            <h2 style='
                font-size: 1.75rem;
                font-weight: 700;
                color: var(--gray-900);
                margin: 0;
            '>
                {icon_html}{title}
            </h2>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
