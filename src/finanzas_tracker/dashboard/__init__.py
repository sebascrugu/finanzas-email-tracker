"""Dashboard de Streamlit para visualización de transacciones."""

# Exportar estilos y componentes UI para fácil importación
from finanzas_tracker.dashboard.styles import (
    inject_custom_css,
    render_hero_metric,
    render_section_header,
    render_stat_card,
)
from finanzas_tracker.dashboard.ui_components import (
    confirmation_dialog,
    empty_state,
    info_card,
    loading_skeleton,
    metric_comparison,
    progress_bar_with_label,
    status_badge,
    validated_number_input,
    validated_text_input,
)


__all__ = [
    # Estilos
    "inject_custom_css",
    "render_hero_metric",
    "render_section_header",
    "render_stat_card",
    # Componentes UI
    "validated_number_input",
    "validated_text_input",
    "progress_bar_with_label",
    "info_card",
    "metric_comparison",
    "status_badge",
    "confirmation_dialog",
    "empty_state",
    "loading_skeleton",
]
