"""
Componentes UI reutilizables para el dashboard.

Proporciona componentes con mejor UX, validación en tiempo real,
tooltips contextuales y microinteracciones.
"""

from collections.abc import Callable
from decimal import Decimal

import streamlit as st


def validated_number_input(
    label: str,
    min_value: float | None = None,
    max_value: float | None = None,
    step: float | None = None,
    value: float | None = None,
    help_text: str | None = None,
    validator: Callable[[float], tuple[bool, str]] | None = None,
    key: str | None = None,
) -> float | None:
    """
    Input numérico con validación en tiempo real.

    Args:
        label: Etiqueta del campo
        min_value: Valor mínimo permitido
        max_value: Valor máximo permitido
        step: Incremento del campo
        value: Valor inicial
        help_text: Texto de ayuda
        validator: Función de validación custom (value) -> (valid, error_msg)
        key: Key única para el input

    Returns:
        Valor ingresado o None si es inválido
    """
    col1, col2 = st.columns([3, 1])

    with col1:
        input_value = st.number_input(
            label,
            min_value=min_value,
            max_value=max_value,
            step=step,
            value=value,
            help=help_text,
            key=key,
        )

    # Validación custom
    is_valid = True
    error_msg = ""

    if validator and input_value is not None:
        is_valid, error_msg = validator(input_value)

    with col2:
        if input_value is not None:
            if is_valid:
                st.markdown(
                    "<div style='padding-top: 1.8rem;'><span style='color: var(--success); "
                    "font-size: 1.5rem;'>✓</span></div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    "<div style='padding-top: 1.8rem;'><span style='color: var(--danger); "
                    "font-size: 1.5rem;'>✗</span></div>",
                    unsafe_allow_html=True,
                )

    if not is_valid and error_msg:
        st.error(f"❌ {error_msg}")
        return None

    return input_value


def validated_text_input(
    label: str,
    value: str = "",
    placeholder: str = "",
    max_length: int | None = None,
    validator: Callable[[str], tuple[bool, str]] | None = None,
    help_text: str | None = None,
    key: str | None = None,
) -> str | None:
    """
    Input de texto con validación en tiempo real.

    Args:
        label: Etiqueta del campo
        value: Valor inicial
        placeholder: Placeholder del campo
        max_length: Longitud máxima permitida
        validator: Función de validación custom (value) -> (valid, error_msg)
        help_text: Texto de ayuda
        key: Key única para el input

    Returns:
        Texto ingresado o None si es inválido
    """
    col1, col2 = st.columns([3, 1])

    with col1:
        input_value = st.text_input(
            label,
            value=value,
            placeholder=placeholder,
            max_chars=max_length,
            help=help_text,
            key=key,
        )

    # Validación
    is_valid = True
    error_msg = ""

    if input_value:
        if validator:
            is_valid, error_msg = validator(input_value)

    with col2:
        if input_value:
            if is_valid:
                st.markdown(
                    "<div style='padding-top: 1.8rem;'><span style='color: var(--success); "
                    "font-size: 1.5rem;'>✓</span></div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    "<div style='padding-top: 1.8rem;'><span style='color: var(--danger); "
                    "font-size: 1.5rem;'>✗</span></div>",
                    unsafe_allow_html=True,
                )

    if not is_valid and error_msg:
        st.error(f"❌ {error_msg}")
        return None

    return input_value if is_valid else None


def progress_bar_with_label(
    label: str,
    current: float | Decimal,
    target: float | Decimal,
    format_fn: Callable[[float], str] | None = None,
    color_thresholds: dict[float, str] | None = None,
) -> None:
    """
    Barra de progreso con etiqueta y colores dinámicos.

    Args:
        label: Etiqueta de la barra
        current: Valor actual
        target: Valor objetivo
        format_fn: Función para formatear valores (default: f"{x:,.0f}")
        color_thresholds: Dict de umbrales de color {threshold: color}
            Ejemplo: {0.5: "danger", 0.8: "warning", 1.0: "success"}
    """
    if format_fn is None:
        def format_fn(x) -> str:
            return f"₡{x:,.0f}"

    percentage = min((float(current) / float(target)) * 100, 100) if target > 0 else 0

    # Determinar color basado en thresholds
    color = "var(--primary)"
    if color_thresholds:
        for threshold, threshold_color in sorted(color_thresholds.items()):
            if percentage / 100 >= threshold:
                color_map = {
                    "success": "var(--success)",
                    "warning": "var(--warning)",
                    "danger": "var(--danger)",
                    "info": "var(--info)",
                    "primary": "var(--primary)",
                }
                color = color_map.get(threshold_color, "var(--primary)")

    st.markdown(
        f"""
        <div style='margin-bottom: 1.5rem;'>
            <div style='display: flex; justify-content: space-between; margin-bottom: 0.5rem;'>
                <span style='font-weight: 600; color: var(--gray-700);'>{label}</span>
                <span style='font-weight: 700; color: var(--gray-900);'>
                    {format_fn(float(current))} / {format_fn(float(target))}
                </span>
            </div>
            <div style='
                width: 100%;
                height: 12px;
                background: var(--gray-100);
                border-radius: 10px;
                overflow: hidden;
            '>
                <div style='
                    width: {percentage}%;
                    height: 100%;
                    background: linear-gradient(90deg, {color}, {color});
                    border-radius: 10px;
                    transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
                '></div>
            </div>
            <div style='
                text-align: right;
                margin-top: 0.25rem;
                font-size: 0.875rem;
                color: var(--gray-600);
                font-weight: 600;
            '>
                {percentage:.1f}%
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def info_card(
    title: str,
    content: str,
    icon: str = "ℹ️",
    color: str = "info",
    collapsible: bool = False,
) -> None:
    """
    Tarjeta informativa con diseño card-like.

    Args:
        title: Título de la tarjeta
        content: Contenido en markdown
        icon: Emoji o icono
        color: Color del tema (info, success, warning, danger)
        collapsible: Si la tarjeta es expandible
    """
    color_map = {
        "info": ("var(--info)", "var(--info-light)"),
        "success": ("var(--success)", "var(--success-light)"),
        "warning": ("var(--warning)", "var(--warning-light)"),
        "danger": ("var(--danger)", "var(--danger-light)"),
    }

    border_color, bg_color = color_map.get(color, color_map["info"])

    if collapsible:
        with st.expander(f"{icon} {title}"):
            st.markdown(content)
    else:
        st.markdown(
            f"""
            <div style='
                background: {bg_color};
                border-left: 4px solid {border_color};
                border-radius: 12px;
                padding: 1.25rem 1.5rem;
                margin: 1rem 0;
                box-shadow: var(--shadow-sm);
            '>
                <div style='
                    display: flex;
                    align-items: center;
                    gap: 0.75rem;
                    margin-bottom: 0.5rem;
                '>
                    <span style='font-size: 1.5rem;'>{icon}</span>
                    <h4 style='
                        margin: 0;
                        color: var(--gray-900);
                        font-size: 1.1rem;
                        font-weight: 700;
                    '>{title}</h4>
                </div>
                <div style='color: var(--gray-700); line-height: 1.6;'>
                    {content}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def metric_comparison(
    label: str,
    current_value: float | Decimal,
    previous_value: float | Decimal,
    format_fn: Callable[[float], str] | None = None,
    reverse_colors: bool = False,
) -> None:
    """
    Muestra comparación de métricas con cambio porcentual.

    Args:
        label: Etiqueta de la métrica
        current_value: Valor actual
        previous_value: Valor anterior
        format_fn: Función para formatear valores
        reverse_colors: Si True, inversión es buena (para gastos)
    """
    if format_fn is None:
        def format_fn(x) -> str:
            return f"₡{x:,.0f}"

    current = float(current_value)
    previous = float(previous_value)

    if previous > 0:
        change_pct = ((current - previous) / previous) * 100
        change_abs = current - previous
    else:
        change_pct = 0
        change_abs = current

    # Determinar color
    is_increase = change_pct > 0
    is_good = is_increase if not reverse_colors else not is_increase

    arrow = "↑" if is_increase else "↓"
    color = "var(--success)" if is_good else "var(--danger)"

    if abs(change_pct) < 0.1:  # Sin cambio significativo
        arrow = "→"
        color = "var(--gray-500)"

    st.markdown(
        f"""
        <div style='
            background: white;
            border-radius: 12px;
            padding: 1.25rem;
            box-shadow: var(--shadow);
            border: 1px solid var(--gray-100);
        '>
            <p style='
                margin: 0 0 0.5rem 0;
                font-size: 0.875rem;
                font-weight: 600;
                color: var(--gray-600);
                text-transform: uppercase;
            '>{label}</p>
            <h3 style='
                margin: 0 0 0.75rem 0;
                font-size: 2rem;
                font-weight: 800;
                color: var(--gray-900);
            '>{format_fn(current)}</h3>
            <div style='
                display: flex;
                align-items: center;
                gap: 0.5rem;
                font-size: 0.9rem;
            '>
                <span style='color: {color}; font-weight: 700; font-size: 1.1rem;'>
                    {arrow} {abs(change_pct):.1f}%
                </span>
                <span style='color: var(--gray-500);'>
                    vs período anterior
                </span>
            </div>
            <p style='
                margin: 0.5rem 0 0 0;
                font-size: 0.85rem;
                color: var(--gray-600);
            '>
                {format_fn(abs(change_abs))} {' más' if change_abs > 0 else ' menos'}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_badge(text: str, status: str = "info") -> str:
    """
    Genera un badge HTML para estados.

    Args:
        text: Texto del badge
        status: Tipo de estado (success, warning, danger, info, neutral)

    Returns:
        HTML del badge
    """
    color_map = {
        "success": ("var(--success)", "var(--success-light)"),
        "warning": ("var(--warning)", "var(--warning-light)"),
        "danger": ("var(--danger)", "var(--danger-light)"),
        "info": ("var(--info)", "var(--info-light)"),
        "neutral": ("var(--gray-600)", "var(--gray-100)"),
    }

    text_color, bg_color = color_map.get(status, color_map["neutral"])

    return f"""
        <span style='
            display: inline-block;
            background: {bg_color};
            color: {text_color};
            padding: 0.25rem 0.75rem;
            border-radius: 12px;
            font-size: 0.875rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.025em;
        '>{text}</span>
    """


def confirmation_dialog(
    message: str,
    confirm_text: str = "Confirmar",
    cancel_text: str = "Cancelar",
    key_prefix: str = "confirm",
) -> bool:
    """
    Muestra un diálogo de confirmación inline.

    Args:
        message: Mensaje de confirmación
        confirm_text: Texto del botón confirmar
        cancel_text: Texto del botón cancelar
        key_prefix: Prefijo para las keys de los botones

    Returns:
        True si confirmó, False si canceló
    """
    st.warning(f"⚠️ {message}")

    col1, col2, col3 = st.columns([1, 1, 3])

    with col1:
        if st.button(confirm_text, key=f"{key_prefix}_confirm", type="primary"):
            return True

    with col2:
        if st.button(cancel_text, key=f"{key_prefix}_cancel"):
            return False

    return False


def empty_state(
    icon: str,
    title: str,
    description: str,
    action_text: str | None = None,
    action_callback: Callable | None = None,
) -> None:
    """
    Muestra un estado vacío con diseño atractivo.

    Args:
        icon: Emoji grande
        title: Título del estado vacío
        description: Descripción
        action_text: Texto del botón de acción opcional
        action_callback: Callback del botón de acción
    """
    st.markdown(
        f"""
        <div style='
            text-align: center;
            padding: 4rem 2rem;
            background: var(--gray-50);
            border-radius: 16px;
            margin: 2rem 0;
        '>
            <div style='font-size: 4rem; margin-bottom: 1rem;'>{icon}</div>
            <h3 style='
                color: var(--gray-900);
                font-size: 1.5rem;
                font-weight: 700;
                margin-bottom: 0.5rem;
            '>{title}</h3>
            <p style='
                color: var(--gray-600);
                font-size: 1.05rem;
                margin-bottom: 2rem;
                max-width: 500px;
                margin-left: auto;
                margin-right: auto;
            '>{description}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if action_text and action_callback:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button(action_text, type="primary", use_container_width=True):
                action_callback()


def loading_skeleton(count: int = 3) -> None:
    """
    Muestra un skeleton loader mientras carga contenido.

    Args:
        count: Número de skeleton items a mostrar
    """
    for i in range(count):
        st.markdown(
            """
            <div style='
                background: linear-gradient(90deg, var(--gray-100) 25%, var(--gray-200) 50%, var(--gray-100) 75%);
                background-size: 200% 100%;
                animation: pulse 1.5s ease-in-out infinite;
                height: 60px;
                border-radius: 12px;
                margin-bottom: 1rem;
            '></div>
            """,
            unsafe_allow_html=True,
        )
