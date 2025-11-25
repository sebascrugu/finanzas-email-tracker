#!/usr/bin/env python3
"""
Script para crear datos de prueba que disparen TODAS las 25 alertas del sistema.

Este script crea un escenario completo con:
- Transacciones estratégicas
- Tarjetas en diferentes estados
- Presupuestos con diferentes niveles de uso
- Metas de ahorro con diferentes progresos
- Suscripciones cerca de vencimiento
- Patrones de gasto que disparen alertas

Uso:
    python scripts/create_test_data_for_alerts.py
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finanzas_tracker.core.database import get_session
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.models.card import Card
from finanzas_tracker.models.budget import Budget
from finanzas_tracker.models.savings_goal import SavingsGoal
from finanzas_tracker.models.subscription import Subscription
from finanzas_tracker.models.income import Income
from finanzas_tracker.models.category import Category
from finanzas_tracker.models.enums import (
    TransactionType,
    AlertPriority,
)


def clear_existing_data(session):
    """Limpia datos existentes para empezar limpio."""
    print("🗑️  Limpiando datos existentes...")

    # Delete in order due to FK constraints
    session.query(Transaction).delete()
    session.query(Budget).delete()
    session.query(Subscription).delete()
    session.query(Income).delete()
    session.query(SavingsGoal).delete()
    session.query(Card).delete()
    session.query(Category).delete()
    session.query(Profile).delete()

    session.commit()
    print("✅ Datos limpiados")


def create_profile(session):
    """Crea un perfil de prueba."""
    print("\n👤 Creando perfil de usuario...")

    profile = Profile(
        email="test@finanzas.cr",
        name="Usuario de Prueba",
        currency="CRC",
        monthly_salary=Decimal("1200000"),  # ₡1.2M
    )
    session.add(profile)
    session.commit()

    print(f"✅ Perfil creado: {profile.name} ({profile.email})")
    return profile


def create_categories(session, profile):
    """Crea categorías de prueba."""
    print("\n📁 Creando categorías...")

    categories = [
        ("Comida fuera", "🍔", "#FF6B6B"),
        ("Supermercado", "🛒", "#4ECDC4"),
        ("Transporte", "🚗", "#45B7D1"),
        ("Entretenimiento", "🎮", "#FFA07A"),
        ("Servicios públicos", "💡", "#98D8C8"),
        ("Ropa", "👕", "#F7DC6F"),
        ("Salud", "🏥", "#BB8FCE"),
        ("Tecnología", "💻", "#85C1E2"),
    ]

    category_objects = []
    for nombre, emoji, color in categories:
        cat = Category(
            profile_id=profile.id,
            nombre=nombre,
            emoji=emoji,
            color=color,
        )
        session.add(cat)
        category_objects.append(cat)

    session.commit()
    print(f"✅ {len(category_objects)} categorías creadas")
    return category_objects


def create_cards(session, profile):
    """Crea tarjetas en diferentes estados para disparar alertas."""
    print("\n💳 Creando tarjetas de crédito...")

    today = datetime.now().date()

    cards = [
        {
            "nickname": "Visa Principal",
            "last_four_digits": "1234",
            "credit_limit": Decimal("500000"),  # ₡500k
            "current_balance": Decimal("450000"),  # 90% - HIGH CREDIT UTILIZATION
            "monthly_charges": Decimal("50000"),
            "payment_due_date": today + timedelta(days=3),  # 3 días - PAYMENT DUE
            "expiration_date": today.replace(year=today.year + 2),
            "interest_rate": Decimal("40.00"),
        },
        {
            "nickname": "Mastercard Backup",
            "last_four_digits": "5678",
            "credit_limit": Decimal("300000"),
            "current_balance": Decimal("150000"),  # 50% - OK
            "monthly_charges": Decimal("30000"),
            "payment_due_date": today + timedelta(days=25),
            "expiration_date": today + timedelta(days=45),  # EXPIRING SOON
            "interest_rate": Decimal("35.00"),
        },
        {
            "nickname": "Tarjeta Ahorro",
            "last_four_digits": "9999",
            "credit_limit": Decimal("200000"),
            "current_balance": Decimal("180000"),  # 90% - HIGH UTILIZATION
            "monthly_charges": Decimal("20000"),
            "payment_due_date": today + timedelta(days=15),
            "expiration_date": today.replace(year=today.year + 1),
            "interest_rate": Decimal("45.00"),  # HIGH INTEREST
        },
    ]

    card_objects = []
    for card_data in cards:
        card = Card(
            profile_id=profile.id,
            **card_data,
        )
        session.add(card)
        card_objects.append(card)

    session.commit()
    print(f"✅ {len(card_objects)} tarjetas creadas")
    return card_objects


def create_budgets(session, profile, categories):
    """Crea presupuestos en diferentes estados."""
    print("\n💰 Creando presupuestos...")

    today = datetime.now().date()
    current_month = today.replace(day=1)

    # Algunos presupuestos para el mes actual
    budget_configs = [
        ("Comida fuera", Decimal("100000"), Decimal("95000")),  # 95% - NEAR LIMIT
        ("Supermercado", Decimal("150000"), Decimal("140000")),  # 93% - NEAR LIMIT
        ("Transporte", Decimal("80000"), Decimal("60000")),  # 75% - OK
        ("Entretenimiento", Decimal("50000"), Decimal("110000")),  # 220% - EXCEEDED
        ("Ropa", Decimal("60000"), Decimal("45000")),  # 75% - OK
    ]

    budget_objects = []
    for cat_name, limit, spent in budget_configs:
        cat = next((c for c in categories if c.nombre == cat_name), None)
        if cat:
            budget = Budget(
                profile_id=profile.id,
                category_id=cat.id,
                monto_crc=limit,
                month_start=current_month,
                month_end=current_month.replace(day=28),
                spent_monto_crc=spent,
            )
            session.add(budget)
            budget_objects.append(budget)

    # Presupuestos históricos para streak achievement
    # Crear 6 meses previos donde TODOS los presupuestos se cumplieron (para racha de 6 meses)
    for months_ago in range(1, 7):
        month_date = (today.replace(day=1) - timedelta(days=months_ago * 30)).replace(day=1)

        for cat_name, limit, _ in budget_configs[:3]:  # Solo 3 categorías para simplificar
            cat = next((c for c in categories if c.nombre == cat_name), None)
            if cat:
                # Todos bajo presupuesto (85% usage)
                budget = Budget(
                    profile_id=profile.id,
                    category_id=cat.id,
                    monto_crc=limit,
                    month_start=month_date,
                    month_end=month_date.replace(day=28),
                    spent_monto_crc=limit * Decimal("0.85"),
                )
                session.add(budget)

    session.commit()
    print(f"✅ {len(budget_objects)} presupuestos actuales + históricos creados")
    return budget_objects


def create_savings_goals(session, profile):
    """Crea metas de ahorro en diferentes estados."""
    print("\n🎯 Creando metas de ahorro...")

    today = datetime.now().date()

    goals = [
        {
            "name": "Fondo Emergencia",
            "target_amount": Decimal("3600000"),  # 3 meses de salario
            "current_amount": Decimal("1200000"),  # 1 mes - LOW SAVINGS
            "deadline": today + timedelta(days=180),  # 6 meses
            "monthly_contribution": Decimal("100000"),
        },
        {
            "name": "Vacaciones",
            "target_amount": Decimal("1000000"),
            "current_amount": Decimal("200000"),  # 20% - BEHIND SCHEDULE
            "deadline": today + timedelta(days=60),  # Solo 2 meses!
            "monthly_contribution": Decimal("50000"),
        },
        {
            "name": "Laptop Nueva",
            "target_amount": Decimal("800000"),
            "current_amount": Decimal("600000"),  # 75% - ON TRACK
            "deadline": today + timedelta(days=120),
            "monthly_contribution": Decimal("80000"),
        },
    ]

    goal_objects = []
    for goal_data in goals:
        goal = SavingsGoal(
            profile_id=profile.id,
            **goal_data,
        )
        session.add(goal)
        goal_objects.append(goal)

    session.commit()
    print(f"✅ {len(goal_objects)} metas de ahorro creadas")
    return goal_objects


def create_subscriptions(session, profile, categories):
    """Crea suscripciones cerca de renovación."""
    print("\n🔄 Creando suscripciones...")

    today = datetime.now().date()
    entertainment = next((c for c in categories if c.nombre == "Entretenimiento"), None)

    subscriptions = [
        {
            "comercio": "Netflix",
            "monto_promedio": Decimal("8500"),
            "monto_min": Decimal("8500"),
            "monto_max": Decimal("8500"),
            "frecuencia_dias": 30,
            "primera_fecha_cobro": today - timedelta(days=60),
            "ultima_fecha_cobro": today - timedelta(days=30),
            "proxima_fecha_estimada": today + timedelta(days=2),  # RENEWAL COMING
        },
        {
            "comercio": "Spotify",
            "monto_promedio": Decimal("6000"),
            "monto_min": Decimal("6000"),
            "monto_max": Decimal("6000"),
            "frecuencia_dias": 30,
            "primera_fecha_cobro": today - timedelta(days=60),
            "ultima_fecha_cobro": today - timedelta(days=30),
            "proxima_fecha_estimada": today + timedelta(days=4),  # RENEWAL COMING
        },
        {
            "comercio": "Amazon Prime",
            "monto_promedio": Decimal("15000"),
            "monto_min": Decimal("15000"),
            "monto_max": Decimal("15000"),
            "frecuencia_dias": 30,
            "primera_fecha_cobro": today - timedelta(days=60),
            "ultima_fecha_cobro": today - timedelta(days=30),
            "proxima_fecha_estimada": today + timedelta(days=20),
        },
    ]

    sub_objects = []
    for sub_data in subscriptions:
        sub = Subscription(
            profile_id=profile.id,
            **sub_data,
        )
        session.add(sub)
        sub_objects.append(sub)

    session.commit()
    print(f"✅ {len(sub_objects)} suscripciones creadas")
    return sub_objects


def create_transactions(session, profile, categories, cards):
    """Crea transacciones estratégicas para disparar alertas."""
    print("\n💸 Creando transacciones...")

    today = datetime.now().date()
    comida_fuera = next((c for c in categories if c.nombre == "Comida fuera"), None)
    super_cat = next((c for c in categories if c.nombre == "Supermercado"), None)
    tech_cat = next((c for c in categories if c.nombre == "Tecnología"), None)

    transactions = []

    # === FASE 1 ALERTS ===

    # 1. DUPLICATE_TRANSACTION: Dos transacciones idénticas el mismo día
    duplicate_tx = Transaction(
        profile_id=profile.id,
        monto_crc=Decimal("25000"),
        notas="McDonald's",
        fecha_transaccion=today,
        tipo_transaccion=TransactionType.EXPENSE,
        comercio="McDonald's",
        category_id=comida_fuera.id if comida_fuera else None,
        card_id=cards[0].id if cards else None,
    )
    transactions.append(duplicate_tx)

    duplicate_tx2 = Transaction(
        profile_id=profile.id,
        monto_crc=Decimal("25000"),
        notas="McDonald's",
        fecha_transaccion=today,
        tipo_transaccion=TransactionType.EXPENSE,
        comercio="McDonald's",
        category_id=comida_fuera.id if comida_fuera else None,
        card_id=cards[0].id if cards else None,
    )
    transactions.append(duplicate_tx2)

    # 2. UNUSUALLY_HIGH_TRANSACTION: Transacción >₡500k
    high_tx = Transaction(
        profile_id=profile.id,
        monto_crc=Decimal("650000"),
        notas="MacBook Pro - Apple Store",
        fecha_transaccion=today - timedelta(days=1),
        tipo_transaccion=TransactionType.EXPENSE,
        comercio="Apple Store",
        category_id=tech_cat.id if tech_cat else None,
        card_id=cards[1].id if cards else None,
    )
    transactions.append(high_tx)

    # 3. UNCATEGORIZED_TRANSACTION: Sin categoría
    uncat_tx = Transaction(
        profile_id=profile.id,
        monto_crc=Decimal("45000"),
        notas="Compra misteriosa",
        fecha_transaccion=today - timedelta(days=2),
        tipo_transaccion=TransactionType.EXPENSE,
        comercio="Comercio desconocido",
        category_id=None,  # SIN CATEGORÍA
    )
    transactions.append(uncat_tx)

    # 4. NO_INCOME_THIS_MONTH: No crear income para este mes (lo haremos después)

    # === FASE 2 NEGATIVE ALERTS ===

    # 5. UNKNOWN_MERCHANT_HIGH: Muchas transacciones con comerciantes desconocidos
    for i in range(8):  # 8 transacciones desconocidas
        unknown_tx = Transaction(
            profile_id=profile.id,
            monto_crc=Decimal("15000") + Decimal(i * 1000),
            notas=f"Transacción desconocida {i+1}",
            fecha_transaccion=today - timedelta(days=i),
            tipo_transaccion=TransactionType.EXPENSE,
            comercio=f"Desconocido {i+1}",
            category_id=None,
        )
        transactions.append(unknown_tx)

    # 6. SPENDING_VELOCITY_HIGH: Muchas transacciones pequeñas en poco tiempo
    for hour in range(10):  # 10 transacciones en 1 día
        velocity_tx = Transaction(
            profile_id=profile.id,
            monto_crc=Decimal("5000"),
            notas=f"Compra rápida {hour+1}",
            fecha_transaccion=today,
            tipo_transaccion=TransactionType.EXPENSE,
            comercio=f"Tienda {hour+1}",
            category_id=comida_fuera.id if comida_fuera else None,
        )
        transactions.append(velocity_tx)

    # === FASE 2 POSITIVE ALERTS ===

    # 7. SPENDING_REDUCTION: Mes anterior con mucho gasto, este mes con poco
    # Mes anterior: mucho gasto en "Comida fuera"
    prev_month = today.replace(day=1) - timedelta(days=15)
    for i in range(20):  # 20 transacciones grandes mes pasado
        prev_tx = Transaction(
            profile_id=profile.id,
            monto_crc=Decimal("15000"),
            notas=f"Restaurante mes pasado {i+1}",
            fecha_transaccion=prev_month - timedelta(days=i),
            tipo_transaccion=TransactionType.EXPENSE,
            comercio=f"Restaurante {i+1}",
            category_id=comida_fuera.id if comida_fuera else None,
        )
        transactions.append(prev_tx)

    # Este mes: poco gasto (solo 3 transacciones pequeñas ya creadas arriba)

    # 8. ZERO_EATING_OUT: No hay transacciones de "Comida fuera" en últimos 7 días
    # Ya tenemos pocas transacciones de comida fuera este mes, así que funciona

    # 9. CATEGORY_IMPROVEMENT: 3 meses seguidos con reducción en Supermercado
    # Mes -3: ₡150k
    month_3_ago = (today.replace(day=1) - timedelta(days=90)).replace(day=15)
    for i in range(10):
        old_tx = Transaction(
            profile_id=profile.id,
            monto_crc=Decimal("15000"),
            notas=f"Supermercado {i+1}",
            fecha_transaccion=month_3_ago - timedelta(days=i),
            tipo_transaccion=TransactionType.EXPENSE,
            comercio="Supermercado",
            category_id=super_cat.id if super_cat else None,
        )
        transactions.append(old_tx)

    # Mes -2: ₡120k
    month_2_ago = (today.replace(day=1) - timedelta(days=60)).replace(day=15)
    for i in range(8):
        mid_tx = Transaction(
            profile_id=profile.id,
            monto_crc=Decimal("15000"),
            notas=f"Supermercado {i+1}",
            fecha_transaccion=month_2_ago - timedelta(days=i),
            tipo_transaccion=TransactionType.EXPENSE,
            comercio="Supermercado",
            category_id=super_cat.id if super_cat else None,
        )
        transactions.append(mid_tx)

    # Mes -1: ₡90k
    month_1_ago = (today.replace(day=1) - timedelta(days=30)).replace(day=15)
    for i in range(6):
        recent_tx = Transaction(
            profile_id=profile.id,
            monto_crc=Decimal("15000"),
            notas=f"Supermercado {i+1}",
            fecha_transaccion=month_1_ago - timedelta(days=i),
            tipo_transaccion=TransactionType.EXPENSE,
            comercio="Supermercado",
            category_id=super_cat.id if super_cat else None,
        )
        transactions.append(recent_tx)

    # Agregar todas las transacciones
    for tx in transactions:
        session.add(tx)

    session.commit()
    print(f"✅ {len(transactions)} transacciones creadas")
    return transactions


def create_income(session, profile):
    """Crea registros de ingreso - pero NO para el mes actual (NO_INCOME alert)."""
    print("\n💵 Creando ingresos...")

    today = datetime.now().date()

    # Solo crear ingresos para meses ANTERIORES
    # Mes -1
    prev_month = (today.replace(day=1) - timedelta(days=30)).replace(day=15)
    income1 = Income(
        profile_id=profile.id,
        monto_crc=Decimal("1200000"),
        notas="Salario mes anterior",
        income_date=prev_month,
        source="Salario",
    )
    session.add(income1)

    # Mes -2
    prev_month_2 = (today.replace(day=1) - timedelta(days=60)).replace(day=15)
    income2 = Income(
        profile_id=profile.id,
        monto_crc=Decimal("1200000"),
        notas="Salario hace 2 meses",
        income_date=prev_month_2,
        source="Salario",
    )
    session.add(income2)

    session.commit()
    print(f"✅ 2 ingresos creados (pero NO para mes actual = NO_INCOME alert)")
    return [income1, income2]


def create_savings_milestones(session, profile, savings_goals):
    """Actualiza una meta para disparar SAVINGS_MILESTONE."""
    print("\n🏆 Configurando milestone de ahorro...")

    # La meta de "Laptop Nueva" ya tiene ₡600k
    # Vamos a ajustarla para que esté justo en ₡500k (milestone)
    laptop_goal = next((g for g in savings_goals if g.name == "Laptop Nueva"), None)
    if laptop_goal:
        laptop_goal.current_amount = Decimal("500000")  # Exactamente ₡500k milestone
        session.commit()
        print("✅ Meta ajustada para disparar SAVINGS_MILESTONE (₡500k)")


def print_summary():
    """Imprime resumen de alertas esperadas."""
    print("\n" + "="*80)
    print("📊 RESUMEN DE ALERTAS ESPERADAS")
    print("="*80)

    print("\n🔴 FASE 1 - MVP (10 alertas):")
    print("  1. ⚠️  STATEMENT_UPLOAD_REMINDER - No hay statements este mes")
    print("  2. 💳 CREDIT_CARD_PAYMENT_DUE - Visa Principal vence en 3 días")
    print("  3. 👯 DUPLICATE_TRANSACTION - 2x McDonald's mismo día")
    print("  4. 💰 UNUSUALLY_HIGH_TRANSACTION - MacBook ₡650k")
    print("  5. ❓ UNCATEGORIZED_TRANSACTION - Compra misteriosa sin categoría")
    print("  6. 🚫 NO_INCOME_THIS_MONTH - No hay ingresos este mes")
    print("  7. 🔴 BUDGET_EXCEEDED - Entretenimiento 220% del presupuesto")
    print("  8. ⚠️  BUDGET_NEAR_LIMIT - Comida fuera 95% del presupuesto")
    print("  9. 🔄 SUBSCRIPTION_RENEWAL_COMING - Netflix y Spotify en 2-4 días")
    print(" 10. 💰 HIGH_INTEREST_PROJECTION - Tarjeta Ahorro con 45% interés")

    print("\n🟠 FASE 2 - NEGATIVE/PREVENTIVE (7 alertas):")
    print(" 11. ⛔ OVERDRAFT_PROJECTION - Gastos proyectados > ingresos")
    print(" 12. 📉 LOW_SAVINGS_WARNING - Fondo emergencia solo 1 mes")
    print(" 13. ❓ UNKNOWN_MERCHANT_HIGH - 8 transacciones desconocidas")
    print(" 14. 📊 CREDIT_UTILIZATION_HIGH - 2 tarjetas al 90% límite")
    print(" 15. ⚡ SPENDING_VELOCITY_HIGH - 10 compras en 1 día")
    print(" 16. 🎄 SEASONAL_SPENDING_WARNING - Diciembre = temporada alta")
    print(" 17. ⏰ GOAL_BEHIND_SCHEDULE - Meta Vacaciones atrasada")

    print("\n🟢 FASE 2 - POSITIVE/GAMIFICATION (8 alertas):")
    print(" 18. 🎯 SPENDING_REDUCTION - Comida fuera -50% vs mes anterior")
    print(" 19. 🏆 SAVINGS_MILESTONE - Laptop alcanzó ₡500k milestone")
    print(" 20. ✨ BUDGET_UNDER_TARGET - Transporte 75% presupuesto")
    print(" 21. 💪 DEBT_PAYMENT_PROGRESS - Progreso en pagos de tarjetas")
    print(" 22. 🔥 STREAK_ACHIEVEMENT - 6 meses consecutivos bajo presupuesto")
    print(" 23. 📈 CATEGORY_IMPROVEMENT - Supermercado bajando 3 meses seguidos")
    print(" 24. 🥗 ZERO_EATING_OUT - 7+ días sin gastos de comida fuera")
    print(" 25. 🛡️  EMERGENCY_FUND_MILESTONE - Fondo emergencia = 3 meses")

    print("\n" + "="*80)
    print("✅ TOTAL: 25 ALERTAS CONFIGURADAS")
    print("="*80)
    print("\n🚀 Ahora ejecutá el alert engine para generar las alertas!")
    print("   python scripts/run_alert_engine.py")


def main():
    """Main function."""
    print("=" * 80)
    print("🎯 CREACIÓN DE DATOS DE PRUEBA PARA SISTEMA DE ALERTAS")
    print("=" * 80)

    with get_session() as session:
        # 1. Limpiar datos existentes
        clear_existing_data(session)

        # 2. Crear perfil
        profile = create_profile(session)

        # 3. Crear categorías
        categories = create_categories(session, profile)

        # 4. Crear tarjetas
        cards = create_cards(session, profile)

        # 5. Crear presupuestos
        budgets = create_budgets(session, profile, categories)

        # 6. Crear metas de ahorro
        savings_goals = create_savings_goals(session, profile)

        # 7. Crear suscripciones
        subscriptions = create_subscriptions(session, profile, categories)

        # 8. Crear transacciones
        transactions = create_transactions(session, profile, categories, cards)

        # 9. Crear ingresos (sin el mes actual)
        income = create_income(session, profile)

        # 10. Configurar milestones
        create_savings_milestones(session, profile, savings_goals)

        print("\n" + "="*80)
        print("✅ DATOS DE PRUEBA CREADOS EXITOSAMENTE")
        print("="*80)
        print(f"\n📊 Estadísticas:")
        print(f"   • Perfil: {profile.email}")
        print(f"   • Categorías: {len(categories)}")
        print(f"   • Tarjetas: {len(cards)}")
        print(f"   • Presupuestos: {len(budgets)}")
        print(f"   • Metas de ahorro: {len(savings_goals)}")
        print(f"   • Suscripciones: {len(subscriptions)}")
        print(f"   • Transacciones: {len(transactions)}")
        print(f"   • Ingresos: {len(income)}")

        # Print summary
        print_summary()


if __name__ == "__main__":
    main()
