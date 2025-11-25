#!/usr/bin/env python3
"""
Script para ejecutar el Alert Engine y generar todas las alertas.

Este script:
1. Ejecuta el AlertEngine.evaluate_all_alerts()
2. Muestra las alertas generadas
3. Provee estadísticas

Uso:
    python scripts/run_alert_engine.py
"""

import sys
from pathlib import Path
from collections import Counter

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finanzas_tracker.models.database import get_session
from finanzas_tracker.models.user_profile import UserProfile
from finanzas_tracker.models.alert import Alert
from finanzas_tracker.services.alert_engine import AlertEngine
from finanzas_tracker.models.enums import AlertType, AlertPriority


def clear_existing_alerts(session):
    """Limpia alertas existentes."""
    print("🗑️  Limpiando alertas existentes...")
    count = session.query(Alert).delete()
    session.commit()
    print(f"✅ {count} alertas eliminadas")


def run_alert_engine(session, profile):
    """Ejecuta el alert engine."""
    print(f"\n🔄 Ejecutando Alert Engine para {profile.email}...")

    engine = AlertEngine()
    alerts = engine.evaluate_all_alerts(profile.id)

    print(f"✅ {len(alerts)} alertas generadas!")
    return alerts


def display_alerts_by_priority(alerts):
    """Muestra alertas organizadas por prioridad."""
    print("\n" + "="*80)
    print("📋 ALERTAS GENERADAS (por prioridad)")
    print("="*80)

    # Group by priority
    priority_groups = {
        AlertPriority.CRITICAL: [],
        AlertPriority.HIGH: [],
        AlertPriority.MEDIUM: [],
        AlertPriority.LOW: [],
    }

    for alert in alerts:
        priority_groups[alert.priority].append(alert)

    # Display each priority group
    priority_emojis = {
        AlertPriority.CRITICAL: "🔴",
        AlertPriority.HIGH: "🟠",
        AlertPriority.MEDIUM: "🟡",
        AlertPriority.LOW: "🟢",
    }

    for priority in [AlertPriority.CRITICAL, AlertPriority.HIGH, AlertPriority.MEDIUM, AlertPriority.LOW]:
        group = priority_groups[priority]
        if group:
            print(f"\n{priority_emojis[priority]} {priority.value.upper()} ({len(group)} alertas):")
            print("-" * 80)
            for alert in group:
                print(f"   {alert.emoji} {alert.title}")
                if alert.description:
                    # Truncate long descriptions
                    desc = alert.description[:100] + "..." if len(alert.description) > 100 else alert.description
                    print(f"      {desc}")
                print()


def display_alerts_by_type(alerts):
    """Muestra alertas organizadas por tipo."""
    print("\n" + "="*80)
    print("📊 ALERTAS POR TIPO")
    print("="*80)

    type_counter = Counter(alert.alert_type for alert in alerts)

    # Phase 1 alerts
    phase1_types = [
        AlertType.STATEMENT_UPLOAD_REMINDER,
        AlertType.CREDIT_CARD_PAYMENT_DUE,
        AlertType.DUPLICATE_TRANSACTION,
        AlertType.UNUSUALLY_HIGH_TRANSACTION,
        AlertType.UNCATEGORIZED_TRANSACTION,
        AlertType.NO_INCOME_THIS_MONTH,
        AlertType.BUDGET_EXCEEDED,
        AlertType.BUDGET_NEAR_LIMIT,
        AlertType.SUBSCRIPTION_RENEWAL_COMING,
        AlertType.HIGH_INTEREST_PROJECTION,
    ]

    print("\n🔴 FASE 1 - MVP:")
    for alert_type in phase1_types:
        count = type_counter.get(alert_type, 0)
        status = "✅" if count > 0 else "❌"
        print(f"   {status} {alert_type.value}: {count}")

    # Phase 2 negative alerts
    phase2_negative_types = [
        AlertType.OVERDRAFT_PROJECTION,
        AlertType.LOW_SAVINGS_WARNING,
        AlertType.UNKNOWN_MERCHANT_HIGH,
        AlertType.CREDIT_UTILIZATION_HIGH,
        AlertType.SPENDING_VELOCITY_HIGH,
        AlertType.SEASONAL_SPENDING_WARNING,
        AlertType.GOAL_BEHIND_SCHEDULE,
    ]

    print("\n🟠 FASE 2 - NEGATIVE/PREVENTIVE:")
    for alert_type in phase2_negative_types:
        count = type_counter.get(alert_type, 0)
        status = "✅" if count > 0 else "❌"
        print(f"   {status} {alert_type.value}: {count}")

    # Phase 2 positive alerts
    phase2_positive_types = [
        AlertType.SPENDING_REDUCTION,
        AlertType.SAVINGS_MILESTONE,
        AlertType.BUDGET_UNDER_TARGET,
        AlertType.DEBT_PAYMENT_PROGRESS,
        AlertType.STREAK_ACHIEVEMENT,
        AlertType.CATEGORY_IMPROVEMENT,
        AlertType.ZERO_EATING_OUT,
        AlertType.EMERGENCY_FUND_MILESTONE,
    ]

    print("\n🟢 FASE 2 - POSITIVE/GAMIFICATION:")
    for alert_type in phase2_positive_types:
        count = type_counter.get(alert_type, 0)
        status = "✅" if count > 0 else "❌"
        print(f"   {status} {alert_type.value}: {count}")


def display_statistics(alerts):
    """Muestra estadísticas generales."""
    print("\n" + "="*80)
    print("📈 ESTADÍSTICAS")
    print("="*80)

    total = len(alerts)
    critical = len([a for a in alerts if a.priority == AlertPriority.CRITICAL])
    high = len([a for a in alerts if a.priority == AlertPriority.HIGH])
    medium = len([a for a in alerts if a.priority == AlertPriority.MEDIUM])
    low = len([a for a in alerts if a.priority == AlertPriority.LOW])

    dismissed = len([a for a in alerts if a.is_dismissed])
    active = len([a for a in alerts if not a.is_dismissed])

    print(f"\n📊 Por Prioridad:")
    print(f"   🔴 Critical: {critical}")
    print(f"   🟠 High: {high}")
    print(f"   🟡 Medium: {medium}")
    print(f"   🟢 Low: {low}")
    print(f"   📦 TOTAL: {total}")

    print(f"\n📋 Por Estado:")
    print(f"   ✅ Activas: {active}")
    print(f"   ❌ Descartadas: {dismissed}")

    # Phase coverage
    phase1_count = len([a for a in alerts if a.alert_type.value in [
        "statement_upload_reminder", "credit_card_payment_due", "duplicate_transaction",
        "unusually_high_transaction", "uncategorized_transaction", "no_income_this_month",
        "budget_exceeded", "budget_near_limit", "subscription_renewal_coming",
        "high_interest_projection"
    ]])
    phase2_negative_count = len([a for a in alerts if a.alert_type.value in [
        "overdraft_projection", "low_savings_warning", "unknown_merchant_high",
        "credit_utilization_high", "spending_velocity_high", "seasonal_spending_warning",
        "goal_behind_schedule"
    ]])
    phase2_positive_count = len([a for a in alerts if a.alert_type.value in [
        "spending_reduction", "savings_milestone", "budget_under_target",
        "debt_payment_progress", "streak_achievement", "category_improvement",
        "zero_eating_out", "emergency_fund_milestone"
    ]])

    print(f"\n🎯 Por Fase:")
    print(f"   Fase 1 (MVP): {phase1_count}/10")
    print(f"   Fase 2 (Negative): {phase2_negative_count}/7")
    print(f"   Fase 2 (Positive): {phase2_positive_count}/8")

    coverage = ((phase1_count + phase2_negative_count + phase2_positive_count) / 25) * 100
    print(f"\n📊 Cobertura Total: {coverage:.1f}% ({phase1_count + phase2_negative_count + phase2_positive_count}/25 tipos)")


def main():
    """Main function."""
    print("=" * 80)
    print("🚀 EJECUTANDO ALERT ENGINE")
    print("=" * 80)

    with get_session() as session:
        # Get profile
        profile = session.query(UserProfile).first()
        if not profile:
            print("❌ Error: No se encontró ningún perfil.")
            print("   Ejecutá primero: python scripts/create_test_data_for_alerts.py")
            return

        print(f"👤 Perfil: {profile.name} ({profile.email})")

        # Clear existing alerts
        clear_existing_alerts(session)

        # Run alert engine
        alerts = run_alert_engine(session, profile)

        if not alerts:
            print("\n⚠️  No se generaron alertas.")
            return

        # Display results
        display_alerts_by_priority(alerts)
        display_alerts_by_type(alerts)
        display_statistics(alerts)

        print("\n" + "="*80)
        print("✅ ALERT ENGINE COMPLETADO")
        print("="*80)
        print("\n🎨 Ahora podés ver las alertas en el dashboard:")
        print("   streamlit run src/finanzas_tracker/dashboard/app.py")
        print("\n📱 Navegá a la página 'Alertas' para verlas en acción!")


if __name__ == "__main__":
    main()
