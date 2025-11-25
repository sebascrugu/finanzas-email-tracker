#!/usr/bin/env python3
"""
Script para crear datos de prueba COMPLETOS que disparen TODAS las 25 alertas.

Crea un escenario estratégico con transacciones, tarjetas, presupuestos,
suscripciones y savings goals diseñados para activar cada tipo de alerta.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, date
from decimal import Decimal
from uuid import uuid4

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finanzas_tracker.core.database import get_session, engine, Base
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.models.card import Card
from finanzas_tracker.models.budget import Budget
from finanzas_tracker.models.savings_goal import SavingsGoal
from finanzas_tracker.models.subscription import Subscription
from finanzas_tracker.models.income import Income
from finanzas_tracker.models.category import Category, Subcategory
from finanzas_tracker.models.alert import Alert
from finanzas_tracker.models.enums import (
    TransactionType, CardType, BankName, Currency,
    IncomeType, RecurrenceFrequency
)

print("=" * 80)
print("🎯 CREANDO TEST DATA COMPREHENSIVO PARA 25 ALERTAS")
print("=" * 80)

# Initialize DB
print("\n📊 Inicializando base de datos...")
Base.metadata.create_all(engine)
print("✅ Base de datos lista")

with get_session() as session:
    # Limpiar data existente
    print("\n🗑️  Limpiando datos existentes...")
    session.query(Alert).delete()
    session.query(Transaction).delete()
    session.query(Budget).delete()
    session.query(Income).delete()
    session.query(SavingsGoal).delete()
    session.query(Subscription).delete()
    session.query(Card).delete()
    session.query(Profile).delete()
    session.commit()
    print("✅ Datos limpiados")

    # Crear profile
    print("\n👤 Creando perfil...")
    profile = Profile(
        email_outlook="test@finanzas.cr",
        nombre="Usuario de Prueba",
    )
    session.add(profile)
    session.commit()
    print(f"✅ Perfil creado: {profile.nombre}")

    # Obtener categorías (asumiendo que existen)
    print("\n📁 Obteniendo categorías...")
    categories = session.query(Subcategory).all()
    if not categories:
        print("⚠️  No hay categorías. Creando algunas básicas...")
        # Crear categoría padre
        cat_parent = Category(nombre="Gastos", tipo="gasto")
        session.add(cat_parent)
        session.commit()

        # Crear subcategorías
        subcat_names = ["Comida fuera", "Entretenimiento", "Transporte", "Supermercado"]
        for name in subcat_names:
            subcat = Subcategory(nombre=name, category_id=cat_parent.id)
            session.add(subcat)
        session.commit()
        categories = session.query(Subcategory).all()

    comida_fuera = next((c for c in categories if "comida" in c.nombre.lower() or "comer" in c.nombre.lower()), categories[0])
    entretenimiento = next((c for c in categories if "entret" in c.nombre.lower()), categories[1] if len(categories) > 1 else categories[0])
    transporte = next((c for c in categories if "trans" in c.nombre.lower()), categories[2] if len(categories) > 2 else categories[0])
    print(f"✅ Categorías obtenidas: {len(categories)}")

    today = date.today()
    month_start = date(today.year, today.month, 1)

    # ========================================================================
    # CREAR TARJETAS
    # ========================================================================
    print("\n💳 Creando tarjetas...")

    # Tarjeta 1: Alta utilización (90%) + pago due pronto + expira pronto
    card1 = Card(
        profile_id=profile.id,
        ultimos_4_digitos="1234",
        tipo=CardType.CREDIT,
        banco=BankName.BAC,
        marca="Visa",
        limite_credito=Decimal("500000"),
        current_balance=Decimal("450000"),  # 90% - HIGH_CREDIT_UTILIZATION
        activa=True,
        card_expiration_date=today + timedelta(days=20),  # CARD_EXPIRATION
    )

    # Tarjeta 2: Saldo alto para intereses
    card2 = Card(
        profile_id=profile.id,
        ultimos_4_digitos="5678",
        tipo=CardType.CREDIT,
        banco=BankName.POPULAR,
        marca="Mastercard",
        limite_credito=Decimal("300000"),
        current_balance=Decimal("250000"),  # Alto saldo - HIGH_INTEREST_PROJECTION
        interest_rate_annual=Decimal("45.00"),
        activa=True,
    )

    session.add_all([card1, card2])
    session.commit()
    print(f"✅ 2 tarjetas creadas")

    # ========================================================================
    # CREAR INGRESOS
    # ========================================================================
    print("\n💰 Creando ingresos...")

    # Salario mensual bajo (para SPENDING_EXCEEDS_INCOME)
    income1 = Income(
        profile_id=profile.id,
        tipo=IncomeType.SALARY,
        descripcion="Salario Noviembre",
        monto_original=Decimal("800000"),  # Bajo para que gastos excedan
        moneda_original=Currency.CRC,
        monto_crc=Decimal("800000"),
        fecha=month_start,
        es_recurrente=True,
        frecuencia=RecurrenceFrequency.MONTHLY,
        confirmado=True,
    )

    session.add(income1)
    session.commit()
    print(f"✅ Ingreso creado: ₡{income1.monto_crc:,.0f}")

    # ========================================================================
    # CREAR PRESUPUESTOS (nuevo schema por categoría/mes)
    # ========================================================================
    print("\n📊 Creando presupuestos...")

    budgets = [
        # Budget al 95% (BUDGET_80_PERCENT)
        Budget(
            profile_id=profile.id,
            category_id=comida_fuera.id,
            mes=month_start,
            amount_crc=Decimal("100000"),
            monto_limite=Decimal("100000"),
            notas="Presupuesto comida fuera",
        ),
        # Budget al 110% (BUDGET_100_PERCENT)
        Budget(
            profile_id=profile.id,
            category_id=entretenimiento.id,
            mes=month_start,
            amount_crc=Decimal("50000"),
            monto_limite=Decimal("50000"),
            notas="Presupuesto entretenimiento",
        ),
        # Budget bajo uso (BUDGET_UNDER_TARGET)
        Budget(
            profile_id=profile.id,
            category_id=transporte.id,
            mes=month_start,
            amount_crc=Decimal("80000"),
            monto_limite=Decimal("80000"),
            notas="Presupuesto transporte",
        ),
    ]

    session.add_all(budgets)
    session.commit()
    print(f"✅ {len(budgets)} presupuestos creados")

    # ========================================================================
    # CREAR SUBSCRIPCIONES
    # ========================================================================
    print("\n🔄 Creando suscripciones...")

    subscriptions = [
        # Renovación en 3 días (SUBSCRIPTION_RENEWAL)
        Subscription(
            profile_id=profile.id,
            comercio="Netflix",
            monto_promedio=Decimal("8500"),
            monto_min=Decimal("8500"),
            monto_max=Decimal("8500"),
            frecuencia_dias=30,
            primera_fecha_cobro=today - timedelta(days=60),
            ultima_fecha_cobro=today - timedelta(days=30),
            proxima_fecha_estimada=today + timedelta(days=3),
            occurrences_count=3,
            confidence_score=Decimal("95.0"),
            is_active=True,
            is_confirmed=True,
        ),
        # Renovación en 5 días
        Subscription(
            profile_id=profile.id,
            comercio="Spotify",
            monto_promedio=Decimal("6000"),
            monto_min=Decimal("6000"),
            monto_max=Decimal("6000"),
            frecuencia_dias=30,
            primera_fecha_cobro=today - timedelta(days=60),
            ultima_fecha_cobro=today - timedelta(days=30),
            proxima_fecha_estimada=today + timedelta(days=5),
            occurrences_count=3,
            confidence_score=Decimal("95.0"),
            is_active=True,
            is_confirmed=True,
        ),
    ]

    session.add_all(subscriptions)
    session.commit()
    print(f"✅ {len(subscriptions)} suscripciones creadas")

    # ========================================================================
    # CREAR SAVINGS GOALS
    # ========================================================================
    print("\n🎯 Creando metas de ahorro...")

    # Meta atrasada (SAVINGS_GOAL_BEHIND)
    goal1 = SavingsGoal(
        profile_id=profile.id,
        name="Viaje Europa",
        target_amount=Decimal("1000000"),
        current_amount=Decimal("200000"),  # Solo 20% cuando debería estar en 50%
        deadline=today + timedelta(days=180),  # 6 meses
        is_active=True,
        is_completed=False,
    )

    # Meta adelantada (SAVINGS_GOAL_AHEAD)
    goal2 = SavingsGoal(
        profile_id=profile.id,
        name="Emergencias",
        target_amount=Decimal("500000"),
        current_amount=Decimal("350000"),  # 70% cuando debería estar en 50%
        deadline=today + timedelta(days=180),
        is_active=True,
        is_completed=False,
    )

    # Meta cerca de milestone (SAVINGS_MILESTONE)
    goal3 = SavingsGoal(
        profile_id=profile.id,
        name="Carro",
        target_amount=Decimal("5000000"),
        current_amount=Decimal("495000"),  # Cerca de ₡500k milestone
        deadline=today + timedelta(days=365),
        is_active=True,
        is_completed=False,
    )

    session.add_all([goal1, goal2, goal3])
    session.commit()
    print(f"✅ 3 metas de ahorro creadas")

    # ========================================================================
    # CREAR TRANSACCIONES ESTRATÉGICAS
    # ========================================================================
    print("\n💸 Creando transacciones estratégicas...")

    transactions = []

    # 1. DUPLICATE_TRANSACTION: Dos transacciones idénticas
    dup_amount = Decimal("25000")
    for i in range(2):
        tx = Transaction(
            profile_id=profile.id,
            email_id=f"dup_{i}_{uuid4()}",
            banco=BankName.BAC,
            tipo_transaccion=TransactionType.PURCHASE,
            comercio="McDonald's",
            monto_original=dup_amount,
            moneda_original=Currency.CRC,
            monto_crc=dup_amount,
            fecha_transaccion=datetime.now(),
            subcategory_id=comida_fuera.id,
            card_id=card1.id,
        )
        transactions.append(tx)

    # 2. UNCATEGORIZED_TRANSACTIONS: Sin categoría
    tx_uncat = Transaction(
        profile_id=profile.id,
        email_id=f"uncat_{uuid4()}",
        banco=BankName.BAC,
        tipo_transaccion=TransactionType.PURCHASE,
        comercio="Tienda Desconocida",
        monto_original=Decimal("15000"),
        moneda_original=Currency.CRC,
        monto_crc=Decimal("15000"),
        fecha_transaccion=datetime.now(),
        subcategory_id=None,  # Sin categoría
    )
    transactions.append(tx_uncat)

    # 3. UNKNOWN_MERCHANT_ALERT: 10 transacciones con merchant desconocido
    for i in range(10):
        tx = Transaction(
            profile_id=profile.id,
            email_id=f"unknown_{i}_{uuid4()}",
            banco=BankName.POPULAR,
            tipo_transaccion=TransactionType.PURCHASE,
            comercio=f"UNKNOWN MERCHANT {i}",
            monto_original=Decimal("5000"),
            moneda_original=Currency.CRC,
            monto_crc=Decimal("5000"),
            fecha_transaccion=datetime.now() - timedelta(days=i),
            es_desconocida=True,
            subcategory_id=comida_fuera.id,
        )
        transactions.append(tx)

    # 4. RAPID_SPENDING: 15 transacciones en últimas 24 horas
    for i in range(15):
        tx = Transaction(
            profile_id=profile.id,
            email_id=f"rapid_{i}_{uuid4()}",
            banco=BankName.BAC,
            tipo_transaccion=TransactionType.PURCHASE,
            comercio=f"Compra Rápida {i}",
            monto_original=Decimal("8000"),
            moneda_original=Currency.CRC,
            monto_crc=Decimal("8000"),
            fecha_transaccion=datetime.now() - timedelta(hours=i),
            subcategory_id=entretenimiento.id,
            card_id=card1.id,
        )
        transactions.append(tx)

    # 5. Gastos que llevan budget al 95% (BUDGET_80_PERCENT)
    # Comida fuera: presupuesto ₡100k, gastar ₡95k
    for i in range(5):
        tx = Transaction(
            profile_id=profile.id,
            email_id=f"budget80_{i}_{uuid4()}",
            banco=BankName.BAC,
            tipo_transaccion=TransactionType.PURCHASE,
            comercio=f"Restaurante {i}",
            monto_original=Decimal("19000"),
            moneda_original=Currency.CRC,
            monto_crc=Decimal("19000"),
            fecha_transaccion=datetime.now() - timedelta(days=i+1),
            subcategory_id=comida_fuera.id,
        )
        transactions.append(tx)

    # 6. Gastos que exceden budget (BUDGET_100_PERCENT)
    # Entretenimiento: presupuesto ₡50k, gastar ₡55k
    for i in range(6):
        tx = Transaction(
            profile_id=profile.id,
            email_id=f"budget100_{i}_{uuid4()}",
            banco=BankName.POPULAR,
            tipo_transaccion=TransactionType.PURCHASE,
            comercio=f"Cine/Eventos {i}",
            monto_original=Decimal("9200"),
            moneda_original=Currency.CRC,
            monto_crc=Decimal("9200"),
            fecha_transaccion=datetime.now() - timedelta(days=i+2),
            subcategory_id=entretenimiento.id,
        )
        transactions.append(tx)

    # 7. Gastos bajos en transporte (BUDGET_UNDER_TARGET)
    # Solo gastar ₡60k de ₡80k (75%)
    for i in range(4):
        tx = Transaction(
            profile_id=profile.id,
            email_id=f"under_{i}_{uuid4()}",
            banco=BankName.BAC,
            tipo_transaccion=TransactionType.PURCHASE,
            comercio=f"Uber/Gas {i}",
            monto_original=Decimal("15000"),
            moneda_original=Currency.CRC,
            monto_crc=Decimal("15000"),
            fecha_transaccion=datetime.now() - timedelta(days=i+5),
            subcategory_id=transporte.id,
        )
        transactions.append(tx)

    # 8. SPENDING_EXCEEDS_INCOME: Gastos totales >₡800k (income mensual)
    # Ya tenemos ~₡400k, agregar ₡450k más
    for i in range(10):
        tx = Transaction(
            profile_id=profile.id,
            email_id=f"exceed_{i}_{uuid4()}",
            banco=BankName.BAC,
            tipo_transaccion=TransactionType.PURCHASE,
            comercio=f"Gasto Grande {i}",
            monto_original=Decimal("45000"),
            moneda_original=Currency.CRC,
            monto_crc=Decimal("45000"),
            fecha_transaccion=datetime.now() - timedelta(days=i+10),
            subcategory_id=comida_fuera.id,
        )
        transactions.append(tx)

    # 9. SPENDING_REDUCTION: Datos históricos mes pasado vs este mes
    # Mes pasado: ₡150k en comida fuera
    # Este mes: ₡95k (ya creado arriba) = 37% reducción
    last_month = today - timedelta(days=35)
    for i in range(8):
        tx = Transaction(
            profile_id=profile.id,
            email_id=f"history_{i}_{uuid4()}",
            banco=BankName.BAC,
            tipo_transaccion=TransactionType.PURCHASE,
            comercio=f"Restaurante Mes Pasado {i}",
            monto_original=Decimal("18750"),
            moneda_original=Currency.CRC,
            monto_crc=Decimal("18750"),
            fecha_transaccion=datetime(last_month.year, last_month.month, 15 + i),
            subcategory_id=comida_fuera.id,
        )
        transactions.append(tx)

    # 10. LOW_SAVINGS_WARNING: Bajo ahorro este mes
    # (Ya tenemos alto gasto, el ahorro será automáticamente bajo)

    # 11. EARLY_MONTH_DISCIPLINE: Bajo gasto primera semana
    # (Ya tenemos gastos distribuidos)

    session.add_all(transactions)
    session.commit()
    print(f"✅ {len(transactions)} transacciones creadas")

    # ========================================================================
    # RESUMEN
    # ========================================================================
    print("\n" + "=" * 80)
    print("✅ DATA DE PRUEBA CREADA EXITOSAMENTE!")
    print("=" * 80)
    print("\n📊 Resumen:")
    print(f"   • Profile: 1")
    print(f"   • Tarjetas: 2 (1 alta utilización, 1 alto interés)")
    print(f"   • Ingresos: 1 (₡800k mensual)")
    print(f"   • Presupuestos: {len(budgets)} (varios niveles de uso)")
    print(f"   • Suscripciones: {len(subscriptions)} (renovación próxima)")
    print(f"   • Savings Goals: 3 (atrasado, adelantado, milestone)")
    print(f"   • Transacciones: {len(transactions)} (estratégicas)")

    print("\n🎯 Alertas que deberían dispararse:")
    print("   Fase 1 (10):")
    print("   ✓ 1. Statement Upload Reminder")
    print("   ✓ 2. Credit Card Payment Due")
    print("   ✓ 3. Spending Exceeds Income")
    print("   ✓ 4. Budget 80% Reached")
    print("   ✓ 5. Budget 100% Exceeded")
    print("   ✓ 6. Subscription Renewal")
    print("   ✓ 7. Duplicate Transaction")
    print("   ✓ 8. High Interest Projection")
    print("   ✓ 9. Card Expiration")
    print("   ✓ 10. Uncategorized Transactions")

    print("\n   Fase 2 Negative (7):")
    print("   ✓ 11. Overdraft Projection")
    print("   ✓ 12. Low Savings Warning")
    print("   ✓ 13. Rapid Spending")
    print("   ✓ 14. High Credit Utilization")
    print("   ✓ 15. Savings Goal Behind")
    print("   ✓ 16. Unknown Merchant Alert")
    print("   ? 17. Subscription Price Increase (necesita data histórica)")

    print("\n   Fase 2 Positive (8):")
    print("   ✓ 18. Spending Reduction")
    print("   ✓ 19. Savings Milestone")
    print("   ? 20. Budget Streak (necesita meses históricos)")
    print("   ✓ 21. Budget Under Target")
    print("   ? 22. Category Improvement (necesita 3 meses históricos)")
    print("   ? 23. Zero Eating Out (si no gastó en comida fuera)")
    print("   ✓ 24. Savings Goal Ahead")
    print("   ✓ 25. Early Month Discipline")

    print("\n💡 Siguiente paso: Correr alert engine para ver resultados!")
    print("   python scripts/run_alert_engine.py")
    print("=" * 80)
