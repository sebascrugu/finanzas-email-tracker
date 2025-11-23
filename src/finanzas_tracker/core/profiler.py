"""
Performance profiling y query optimization tools.

Herramientas para:
- Detectar queries N+1
- Medir tiempo de queries
- Identificar queries lentas
- Sugerir optimizaciones
"""

import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable

from sqlalchemy import event
from sqlalchemy.engine import Engine

from finanzas_tracker.core.logging import get_logger


logger = get_logger(__name__)


@dataclass
class QueryStats:
    """Estadísticas de una query SQL."""

    query: str
    duration_ms: float
    count: int = 1
    avg_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    min_duration_ms: float = 0.0

    def update(self, duration_ms: float) -> None:
        """Actualiza stats con nueva ejecución."""
        self.count += 1
        self.max_duration_ms = max(self.max_duration_ms, duration_ms)
        self.min_duration_ms = min(self.min_duration_ms, duration_ms) if self.min_duration_ms > 0 else duration_ms
        total = (self.avg_duration_ms * (self.count - 1)) + duration_ms
        self.avg_duration_ms = total / self.count


class SQLProfiler:
    """
    Profiler de queries SQL para detectar problemas de performance.

    Funcionalidades:
    - Track de todas las queries ejecutadas
    - Detección de queries N+1
    - Queries lentas (> threshold)
    - Estadísticas agregadas
    - Sugerencias de optimización
    """

    def __init__(self, slow_query_threshold_ms: float = 100.0) -> None:
        """
        Inicializa el profiler.

        Args:
            slow_query_threshold_ms: Umbral para considerar query lenta (ms)
        """
        self.slow_query_threshold_ms = slow_query_threshold_ms
        self.queries: list[QueryStats] = []
        self.query_map: dict[str, QueryStats] = {}
        self.enabled = False
        self._start_time: float | None = None

    def start(self) -> None:
        """Inicia el profiling."""
        self.enabled = True
        self._start_time = time.time()
        self.queries = []
        self.query_map = {}
        logger.info("🔍 SQL Profiler iniciado")

    def stop(self) -> None:
        """Detiene el profiling."""
        self.enabled = False
        duration = time.time() - self._start_time if self._start_time else 0
        logger.info(
            f"🔍 SQL Profiler detenido - "
            f"{len(self.queries)} queries en {duration:.2f}s"
        )

    def record_query(self, query: str, duration_ms: float) -> None:
        """Registra una query ejecutada."""
        if not self.enabled:
            return

        # Normalizar query (remover valores específicos)
        normalized = self._normalize_query(query)

        if normalized in self.query_map:
            self.query_map[normalized].update(duration_ms)
        else:
            stats = QueryStats(
                query=normalized,
                duration_ms=duration_ms,
                avg_duration_ms=duration_ms,
                max_duration_ms=duration_ms,
                min_duration_ms=duration_ms,
            )
            self.query_map[normalized] = stats
            self.queries.append(stats)

        # Log queries lentas
        if duration_ms > self.slow_query_threshold_ms:
            logger.warning(
                f"🐌 SLOW QUERY ({duration_ms:.2f}ms): {query[:200]}"
            )

    def _normalize_query(self, query: str) -> str:
        """Normaliza query removiendo valores específicos."""
        # Simplificado: en producción usarías regex más sofisticado
        normalized = query.strip()

        # Remover valores en WHERE clauses
        import re
        normalized = re.sub(r"= '[^']*'", "= ?", normalized)
        normalized = re.sub(r"= \d+", "= ?", normalized)

        return normalized

    def get_slow_queries(self) -> list[QueryStats]:
        """Obtiene queries que excedieron el threshold."""
        return [
            q for q in self.queries
            if q.avg_duration_ms > self.slow_query_threshold_ms
        ]

    def get_n_plus_one_suspects(self) -> list[QueryStats]:
        """
        Detecta posibles queries N+1.

        Queries N+1: misma query ejecutada muchas veces (>10)
        """
        return [
            q for q in self.queries
            if q.count > 10
        ]

    def get_report(self) -> str:
        """Genera reporte de performance."""
        if not self.queries:
            return "No hay queries registradas"

        total_queries = sum(q.count for q in self.queries)
        total_time = sum(q.avg_duration_ms * q.count for q in self.queries)
        slow_queries = self.get_slow_queries()
        n_plus_one = self.get_n_plus_one_suspects()

        report = []
        report.append("=" * 80)
        report.append("SQL PERFORMANCE REPORT")
        report.append("=" * 80)
        report.append(f"\n📊 RESUMEN:")
        report.append(f"  • Total queries ejecutadas: {total_queries}")
        report.append(f"  • Queries únicas: {len(self.queries)}")
        report.append(f"  • Tiempo total: {total_time:.2f}ms")
        report.append(f"  • Queries lentas: {len(slow_queries)}")
        report.append(f"  • Posibles N+1: {len(n_plus_one)}")

        if slow_queries:
            report.append(f"\n🐌 TOP 5 QUERIES LENTAS:")
            for i, q in enumerate(sorted(slow_queries, key=lambda x: x.avg_duration_ms, reverse=True)[:5], 1):
                report.append(f"\n  {i}. {q.avg_duration_ms:.2f}ms avg ({q.count}x)")
                report.append(f"     {q.query[:150]}...")

        if n_plus_one:
            report.append(f"\n⚠️  POSIBLES N+1 QUERIES:")
            for i, q in enumerate(sorted(n_plus_one, key=lambda x: x.count, reverse=True)[:5], 1):
                report.append(f"\n  {i}. Ejecutada {q.count}x - {q.avg_duration_ms:.2f}ms avg")
                report.append(f"     {q.query[:150]}...")
                report.append(f"     💡 Sugerencia: Usa joinedload() o selectinload()")

        report.append("\n" + "=" * 80)

        return "\n".join(report)

    def print_report(self) -> None:
        """Imprime el reporte en consola."""
        print(self.get_report())


# Singleton global profiler
_profiler = SQLProfiler()


def enable_sql_profiling(engine: Engine, threshold_ms: float = 100.0) -> None:
    """
    Habilita profiling de queries SQL en un engine.

    Args:
        engine: SQLAlchemy engine
        threshold_ms: Umbral para queries lentas
    """
    _profiler.slow_query_threshold_ms = threshold_ms

    @event.listens_for(engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault("query_start_time", []).append(time.time())

    @event.listens_for(engine, "after_cursor_execute")
    def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total = time.time() - conn.info["query_start_time"].pop()
        duration_ms = total * 1000
        _profiler.record_query(statement, duration_ms)

    logger.info(f"✅ SQL Profiling habilitado (threshold: {threshold_ms}ms)")


@contextmanager
def profile_queries(print_report: bool = True):
    """
    Context manager para profiling de queries.

    Usage:
        with profile_queries():
            # tu código con queries
            pass

    Args:
        print_report: Si imprimir reporte al finalizar
    """
    _profiler.start()
    try:
        yield _profiler
    finally:
        _profiler.stop()
        if print_report:
            _profiler.print_report()


def profile_function(threshold_ms: float = 1000.0):
    """
    Decorator para perfilar funciones y medir tiempo de ejecución.

    Args:
        threshold_ms: Umbral para considerar función lenta

    Usage:
        @profile_function(threshold_ms=500)
        def my_slow_function():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start) * 1000
                if duration_ms > threshold_ms:
                    logger.warning(
                        f"🐌 SLOW FUNCTION: {func.__name__} took {duration_ms:.2f}ms "
                        f"(threshold: {threshold_ms}ms)"
                    )
                else:
                    logger.debug(f"⚡ {func.__name__} took {duration_ms:.2f}ms")

        return wrapper
    return decorator


# Helper para obtener el profiler global
def get_profiler() -> SQLProfiler:
    """Obtiene el profiler global."""
    return _profiler
