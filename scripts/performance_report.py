"""
Script para generar reporte de performance del sistema.

Analiza:
- Queries SQL ejecutadas
- Queries lentas
- Posibles N+1 queries
- Índices sugeridos
- Recomendaciones de optimización

Usage:
    poetry run python scripts/performance_report.py
"""

import sys
from pathlib import Path

# Agregar src al path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import engine, get_session, init_db
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.core.profiler import enable_sql_profiling, profile_queries
from finanzas_tracker.core.query_optimizer import query_optimizer
from finanzas_tracker.models.profile import Profile


logger = get_logger(__name__)


def run_sample_queries():
    """Ejecuta queries típicas para análisis."""
    logger.info("🔍 Ejecutando queries de muestra...")

    with get_session() as session:
        # Query 1: Get active profile (común en dashboard)
        profile = (
            session.query(Profile)
            .filter(Profile.es_activo == True)  # noqa: E712
            .first()
        )

        if not profile:
            logger.warning("No hay perfil activo para analizar")
            return

        logger.info(f"Perfil encontrado: {profile.nombre}")

        # Query 2: Get transactions (común - puede tener N+1)
        from finanzas_tracker.models.transaction import Transaction
        from datetime import date, timedelta

        cutoff = date.today() - timedelta(days=30)

        # SIN optimización (lazy loading)
        logger.info("Query SIN optimización (lazy loading)...")
        transactions = (
            session.query(Transaction)
            .filter(
                Transaction.profile_id == profile.id,
                Transaction.fecha_transaccion >= cutoff,
            )
            .limit(20)
            .all()
        )

        # Acceder a relaciones (esto causa N+1 si no hay joinedload)
        for t in transactions[:5]:
            _ = t.account  # Lazy load (N+1!)
            if t.subcategory:
                _ = t.subcategory.category  # Otro lazy load!

        # Query 3: Get accounts
        from finanzas_tracker.models.account import Account

        accounts = (
            session.query(Account)
            .filter(Account.profile_id == profile.id)
            .all()
        )

        logger.info(f"Cuentas encontradas: {len(accounts)}")

        # Query 4: Get incomes
        from finanzas_tracker.models.income import Income

        incomes = (
            session.query(Income)
            .filter(
                Income.profile_id == profile.id,
                Income.fecha >= cutoff,
            )
            .all()
        )

        logger.info(f"Ingresos encontrados: {len(incomes)}")


def generate_performance_report():
    """Genera reporte completo de performance."""
    print("\n" + "=" * 80)
    print("PERFORMANCE ANALYSIS REPORT")
    print("=" * 80)

    # 1. Inicializar BD
    init_db()

    # 2. Habilitar SQL profiling
    enable_sql_profiling(engine, threshold_ms=50.0)

    # 3. Ejecutar queries con profiling
    print("\n🔍 Analizando queries del sistema...")
    with profile_queries(print_report=False) as profiler:
        run_sample_queries()

    # 4. Imprimir reporte SQL
    print("\n")
    profiler.print_report()

    # 5. Sugerencias de índices
    print("\n" + "=" * 80)
    print("📊 ÍNDICES SUGERIDOS")
    print("=" * 80)

    suggestions = query_optimizer.suggest_indexes()

    missing = [s for s in suggestions if not s["existing"]]
    existing = [s for s in suggestions if s["existing"]]

    if existing:
        print(f"\n✅ Índices ya implementados ({len(existing)}):")
        for sug in existing:
            print(f"  • {sug['table']}.({', '.join(sug['columns'])})")
            print(f"    Razón: {sug['reason']}")

    if missing:
        print(f"\n⚠️  Índices faltantes (Priority: HIGH/MEDIUM) ({len(missing)}):")
        for sug in sorted(missing, key=lambda x: x["priority"]):
            priority_emoji = "🔴" if sug["priority"] == "HIGH" else "🟡"
            print(f"\n  {priority_emoji} {sug['table']}.({', '.join(sug['columns'])})")
            print(f"    Priority: {sug['priority']}")
            print(f"    Razón: {sug['reason']}")

        print("\n💡 Para agregar estos índices:")
        print("   poetry run alembic upgrade head")
    else:
        print("\n✅ Todos los índices recomendados ya están implementados")

    # 6. Tips de optimización
    print("\n" + "=" * 80)
    print("💡 TIPS DE OPTIMIZACIÓN")
    print("=" * 80)

    for tip in query_optimizer.get_optimization_tips():
        print(f"  {tip}")

    # 7. Generar código de migración (si hay índices faltantes)
    if missing:
        print("\n" + "=" * 80)
        print("🔧 CÓDIGO DE MIGRACIÓN (Alembic)")
        print("=" * 80)

        from finanzas_tracker.core.query_optimizer import create_missing_indexes_migration

        migration_code = create_missing_indexes_migration()
        print(f"\n{migration_code}")

    print("\n" + "=" * 80)
    print("FIN DEL REPORTE")
    print("=" * 80)


if __name__ == "__main__":
    try:
        generate_performance_report()
    except Exception as e:
        logger.error(f"Error generando reporte: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
