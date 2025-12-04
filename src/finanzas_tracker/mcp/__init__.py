"""
MCP Server para Finanzas Tracker CR.

Este módulo implementa un servidor MCP (Model Context Protocol)
usando FastMCP para integrar Finanzas Tracker con Claude Desktop.

Herramientas disponibles:

Nivel 1 - Consultas Básicas:
- get_transactions: Consultar transacciones con filtros
- get_spending_summary: Resumen agrupado por categoría/comercio
- get_top_merchants: Comercios donde más gastas

Nivel 2 - Análisis:
- search_transactions: Búsqueda semántica con embeddings
- get_monthly_comparison: Comparación mes actual vs anterior

Nivel 3 - Coaching (DIFERENCIADOR):
- budget_coaching: Coaching financiero personalizado con IA
- savings_opportunities: Encuentra dónde puedes ahorrar
- cashflow_prediction: Predice tu flujo de efectivo
- spending_alert: Detecta patrones problemáticos
- goal_advisor: Asesor de metas de ahorro
"""

from finanzas_tracker.mcp.server import main, mcp, run_server


__all__ = ["mcp", "run_server", "main"]
