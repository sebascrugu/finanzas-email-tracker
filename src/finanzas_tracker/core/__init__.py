"""Módulo core con funcionalidades fundamentales del proyecto."""

# Performance & Profiling
from finanzas_tracker.core.profiler import (
    SQLProfiler,
    enable_sql_profiling,
    get_profiler,
    profile_function,
    profile_queries,
)
from finanzas_tracker.core.query_optimizer import (
    QueryOptimizer,
    batch_load_subcategories,
    create_missing_indexes_migration,
    get_profile_with_full_context,
    get_transactions_with_relations,
    query_optimizer,
)


__all__ = [
    # Profiling
    "SQLProfiler",
    "enable_sql_profiling",
    "get_profiler",
    "profile_function",
    "profile_queries",
    # Query Optimization
    "QueryOptimizer",
    "query_optimizer",
    "get_transactions_with_relations",
    "get_profile_with_full_context",
    "batch_load_subcategories",
    "create_missing_indexes_migration",
]
