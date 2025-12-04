#!/usr/bin/env python
"""
🧪 Simulación Completa: Usuario Nuevo en Finanzas Tracker CR

Este script simula el flujo completo de un usuario costarricense que:
1. Se registra en la app
2. Configura sus cuentas bancarias
3. Agrega sus tarjetas de crédito
4. Registra inversiones
5. Crea metas de ahorro
6. Importa transacciones del mes
7. Recibe notificaciones de tarjetas

Datos basados en un perfil típico de clase media en Costa Rica.
"""

import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

# Agregar src al path
sys.path.insert(0, "src")

from finanzas_tracker.core.database import get_session
from finanzas_tracker.models import (
    Profile,
    User,
    Card,
    Account,
    Investment,
    Goal,
    Transaction,
    BillingCycle,
    Category,
)
from finanzas_tracker.models.enums import (
    BankName,
    TransactionType,
    CardType,
    AccountType,
    InvestmentType,
    GoalStatus,
    BillingCycleStatus,
    Currency,
)
from finanzas_tracker.services import CardNotificationService
from sqlalchemy import select


def print_header(text: str):
    """Imprime un header bonito."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def print_step(step: int, text: str):
    """Imprime un paso."""
    print(f"\n📌 Paso {step}: {text}")
    print("-" * 40)


def run_simulation():
    """Ejecuta la simulación completa."""
    
    print_header("🇨🇷 SIMULACIÓN: Nuevo Usuario en Finanzas Tracker CR")
    print(f"Fecha: {date.today()}")
    print(f"Usuario: Sebastián Cruz (tico promedio clase media)")
    
    with get_session() as db:
        # ================================================================
        # PASO 1: Crear perfil de usuario
        # ================================================================
        print_step(1, "Crear perfil de usuario")
        
        # Buscar si ya existe
        existing = db.execute(
            select(Profile).where(Profile.nombre == "Sebastián Simulación")
        ).scalar_one_or_none()
        
        if existing:
            profile = existing
            print(f"   ✅ Perfil ya existe: {profile.id}")
        else:
            profile = Profile(
                id=str(uuid4()),
                nombre="Sebastián Simulación",
                email_outlook="sebas.simulacion@outlook.com",
            )
            db.add(profile)
            db.flush()
            print(f"   ✅ Perfil creado: {profile.id}")
            print(f"   📧 Email: {profile.email_outlook}")
            print(f"   💰 Salario: ₡1,200,000 (típico clase media)")
        
        # ================================================================
        # PASO 2: Configurar cuentas bancarias
        # ================================================================
        print_step(2, "Configurar cuentas bancarias")
        
        cuentas_data = [
            {
                "nombre": "Corriente BAC",
                "banco": BankName.BAC,
                "tipo": AccountType.CHECKING,
                "numero_cuenta": "***4521",
                "saldo": Decimal("485000"),
                "moneda": Currency.CRC,
            },
            {
                "nombre": "Ahorro BAC",
                "banco": BankName.BAC,
                "tipo": AccountType.SAVINGS,
                "numero_cuenta": "***7890",
                "saldo": Decimal("1250000"),
                "moneda": Currency.CRC,
            },
            {
                "nombre": "Cuenta USD BAC",
                "banco": BankName.BAC,
                "tipo": AccountType.CHECKING,
                "numero_cuenta": "***1234",
                "saldo": Decimal("850"),
                "moneda": Currency.USD,
            },
        ]
        
        cuentas_creadas = []
        for cuenta_info in cuentas_data:
            # Verificar si ya existe
            existing_account = db.execute(
                select(Account).where(
                    Account.profile_id == profile.id,
                    Account.nombre == cuenta_info["nombre"],
                )
            ).scalar_one_or_none()
            
            if existing_account:
                cuentas_creadas.append(existing_account)
                print(f"   ✅ {cuenta_info['nombre']}: ya existe")
            else:
                cuenta = Account(
                    profile_id=profile.id,
                    **cuenta_info,
                )
                db.add(cuenta)
                cuentas_creadas.append(cuenta)
                saldo = cuenta_info["saldo"]
                moneda = "₡" if cuenta_info["moneda"] == Currency.CRC else "$"
                print(f"   ✅ {cuenta_info['nombre']}: {moneda}{saldo:,.0f}")
        
        db.flush()
        
        # ================================================================
        # PASO 3: Agregar tarjetas de crédito
        # ================================================================
        print_step(3, "Agregar tarjetas de crédito")
        
        tarjetas_data = [
            {
                "alias": "VISA Signature BAC",
                "banco": BankName.BAC,
                "tipo": CardType.CREDIT,
                "ultimos_4_digitos": "5678",
                "limite_credito": Decimal("2000000"),
                "current_balance": Decimal("127500"),
                "fecha_corte": 15,
                "fecha_vencimiento": 28,
                "interest_rate_annual": Decimal("52.0"),
                "minimum_payment_percentage": Decimal("10.0"),
            },
            {
                "alias": "Mastercard BAC",
                "banco": BankName.BAC,
                "tipo": CardType.CREDIT,
                "ultimos_4_digitos": "9012",
                "limite_credito": Decimal("1500000"),
                "current_balance": Decimal("45000"),
                "fecha_corte": 20,
                "fecha_vencimiento": 5,
                "interest_rate_annual": Decimal("48.0"),
                "minimum_payment_percentage": Decimal("10.0"),
            },
            {
                "alias": "Débito BAC",
                "banco": BankName.BAC,
                "tipo": CardType.DEBIT,
                "ultimos_4_digitos": "4521",
            },
        ]
        
        tarjetas_creadas = []
        for tarjeta_info in tarjetas_data:
            nombre = tarjeta_info.get("alias", "Tarjeta")
            existing_card = db.execute(
                select(Card).where(
                    Card.profile_id == profile.id,
                    Card.ultimos_4_digitos == tarjeta_info["ultimos_4_digitos"],
                )
            ).scalar_one_or_none()
            
            if existing_card:
                tarjetas_creadas.append(existing_card)
                print(f"   ✅ {nombre}: ya existe")
            else:
                tarjeta = Card(
                    profile_id=profile.id,
                    **tarjeta_info,
                )
                db.add(tarjeta)
                tarjetas_creadas.append(tarjeta)
                
                if tarjeta_info["tipo"] == CardType.CREDIT:
                    limite = tarjeta_info.get("limite_credito", 0)
                    balance = tarjeta_info.get("current_balance", 0)
                    print(f"   💳 {nombre}: ₡{balance:,.0f} / ₡{limite:,.0f}")
                else:
                    print(f"   💳 {nombre}: Débito")
        
        db.flush()
        
        # ================================================================
        # PASO 4: Crear ciclos de facturación
        # ================================================================
        print_step(4, "Crear ciclos de facturación actuales")
        
        today = date.today()
        
        for tarjeta in tarjetas_creadas:
            if tarjeta.tipo != CardType.CREDIT:
                continue
            
            # Verificar si ya existe ciclo
            existing_cycle = db.execute(
                select(BillingCycle).where(
                    BillingCycle.card_id == tarjeta.id,
                    BillingCycle.fecha_corte >= today.replace(day=1),
                )
            ).scalar_one_or_none()
            
            if existing_cycle:
                print(f"   ✅ Ciclo {tarjeta.alias}: ya existe")
                continue
            
            # Calcular fechas del ciclo actual
            dia_corte = tarjeta.fecha_corte or 15
            dia_pago = tarjeta.fecha_vencimiento or 28
            
            # Fecha de corte de este mes
            try:
                fecha_corte = date(today.year, today.month, dia_corte)
            except ValueError:
                fecha_corte = date(today.year, today.month, 28)
            
            # Fecha de inicio (corte del mes anterior)
            if today.month == 1:
                fecha_inicio = date(today.year - 1, 12, dia_corte)
            else:
                try:
                    fecha_inicio = date(today.year, today.month - 1, dia_corte)
                except ValueError:
                    fecha_inicio = date(today.year, today.month - 1, 28)
            
            # Fecha de pago
            if dia_pago < dia_corte:
                # Pago es el mes siguiente
                if today.month == 12:
                    fecha_pago = date(today.year + 1, 1, dia_pago)
                else:
                    fecha_pago = date(today.year, today.month + 1, dia_pago)
            else:
                fecha_pago = date(today.year, today.month, dia_pago)
            
            ciclo = BillingCycle(
                card_id=tarjeta.id,
                fecha_inicio=fecha_inicio,
                fecha_corte=fecha_corte,
                fecha_pago=fecha_pago,
                total_periodo=tarjeta.current_balance or Decimal("0"),
                total_a_pagar=tarjeta.current_balance or Decimal("0"),
                pago_minimo=(tarjeta.current_balance or Decimal("0")) * Decimal("0.10"),
                status=BillingCycleStatus.CLOSED if today > fecha_corte else BillingCycleStatus.OPEN,
            )
            db.add(ciclo)
            
            dias_para_pago = (fecha_pago - today).days
            print(f"   📅 {tarjeta.alias}:")
            print(f"      Corte: {fecha_corte} | Pago: {fecha_pago} ({dias_para_pago} días)")
            print(f"      Total: ₡{ciclo.total_a_pagar:,.0f} | Mínimo: ₡{ciclo.pago_minimo:,.0f}")
        
        db.flush()
        
        # ================================================================
        # PASO 5: Agregar inversiones
        # ================================================================
        print_step(5, "Agregar inversiones")
        
        inversiones_data = [
            {
                "nombre": "CDP BAC 6 meses",
                "tipo": InvestmentType.CDP,
                "institucion": "BAC Credomatic",
                "monto_principal": Decimal("3000000"),
                "rendimiento_acumulado": Decimal("45000"),
                "tasa_interes_anual": Decimal("0.065"),  # 6.5%
                "fecha_inicio": date(2025, 6, 15),
                "fecha_vencimiento": date(2025, 12, 15),
                "moneda": Currency.CRC,
            },
            {
                "nombre": "CDP Popular 1 año",
                "tipo": InvestmentType.CDP,
                "institucion": "Banco Popular",
                "monto_principal": Decimal("2000000"),
                "rendimiento_acumulado": Decimal("130000"),
                "tasa_interes_anual": Decimal("0.0725"),  # 7.25%
                "fecha_inicio": date(2025, 1, 10),
                "fecha_vencimiento": date(2026, 1, 10),
                "moneda": Currency.CRC,
            },
        ]
        
        for inv_info in inversiones_data:
            existing_inv = db.execute(
                select(Investment).where(
                    Investment.profile_id == profile.id,
                    Investment.nombre == inv_info["nombre"],
                )
            ).scalar_one_or_none()
            
            if existing_inv:
                print(f"   ✅ {inv_info['nombre']}: ya existe")
            else:
                inversion = Investment(
                    profile_id=profile.id,
                    **inv_info,
                )
                db.add(inversion)
                monto_actual = inv_info["monto_principal"] + inv_info["rendimiento_acumulado"]
                rendimiento = inv_info["rendimiento_acumulado"]
                tasa = inv_info["tasa_interes_anual"] * 100
                print(f"   📈 {inv_info['nombre']}:")
                print(f"      Monto: ₡{monto_actual:,.0f} (+₡{rendimiento:,.0f})")
                print(f"      Tasa: {tasa:.2f}% | Vence: {inv_info['fecha_vencimiento']}")
        
        db.flush()
        
        # ================================================================
        # PASO 6: Crear metas de ahorro
        # ================================================================
        print_step(6, "Crear metas de ahorro")
        
        metas_data = [
            {
                "nombre": "Fondo de Emergencia",
                "descripcion": "3 meses de gastos (₡2.4M)",
                "monto_objetivo": Decimal("2400000"),
                "monto_actual": Decimal("1250000"),
                "fecha_objetivo": date(2026, 6, 1),
                "estado": GoalStatus.ACTIVA,
            },
            {
                "nombre": "Mundial 2026 ⚽",
                "descripcion": "Viaje a ver la Sele en USA",
                "monto_objetivo": Decimal("5000000"),
                "monto_actual": Decimal("4100000"),
                "fecha_objetivo": date(2026, 6, 15),
                "estado": GoalStatus.ACTIVA,
            },
            {
                "nombre": "Marchamo 2026",
                "descripcion": "Marchamo del carro",
                "monto_objetivo": Decimal("380000"),
                "monto_actual": Decimal("0"),
                "fecha_objetivo": date(2025, 12, 31),
                "estado": GoalStatus.ACTIVA,
            },
        ]
        
        for meta_info in metas_data:
            existing_goal = db.execute(
                select(Goal).where(
                    Goal.profile_id == profile.id,
                    Goal.nombre == meta_info["nombre"],
                )
            ).scalar_one_or_none()
            
            if existing_goal:
                print(f"   ✅ {meta_info['nombre']}: ya existe")
            else:
                meta = Goal(
                    profile_id=profile.id,
                    **meta_info,
                )
                db.add(meta)
                progreso = (meta_info["monto_actual"] / meta_info["monto_objetivo"]) * 100
                barra = "█" * int(progreso / 10) + "░" * (10 - int(progreso / 10))
                print(f"   🎯 {meta_info['nombre']}:")
                print(f"      {barra} {progreso:.0f}%")
                print(f"      ₡{meta_info['monto_actual']:,.0f} / ₡{meta_info['monto_objetivo']:,.0f}")
        
        db.flush()
        
        # ================================================================
        # PASO 7: Agregar transacciones del mes
        # ================================================================
        print_step(7, "Importar transacciones de noviembre 2025")
        
        # Obtener categorías
        categorias = {
            cat.nombre: cat.id 
            for cat in db.execute(select(Category)).scalars().all()
        }
        
        transacciones_data = [
            # Ingresos
            {"fecha": date(2025, 11, 1), "desc": "Salario Noviembre", "monto": 1200000, "tipo": "CREDITO", "cat": "Salario"},
            {"fecha": date(2025, 11, 15), "desc": "Freelance diseño web", "monto": 150000, "tipo": "CREDITO", "cat": "Otros Ingresos"},
            
            # Necesidades (50%)
            {"fecha": date(2025, 11, 2), "desc": "Alquiler apartamento", "monto": 350000, "tipo": "DEBITO", "cat": "Vivienda"},
            {"fecha": date(2025, 11, 3), "desc": "Automercado semanal", "monto": 45000, "tipo": "DEBITO", "cat": "Supermercado"},
            {"fecha": date(2025, 11, 5), "desc": "ICE electricidad", "monto": 28000, "tipo": "DEBITO", "cat": "Servicios"},
            {"fecha": date(2025, 11, 5), "desc": "Kolbi internet + celular", "monto": 35000, "tipo": "DEBITO", "cat": "Servicios"},
            {"fecha": date(2025, 11, 8), "desc": "Gasolina Delta", "monto": 25000, "tipo": "DEBITO", "cat": "Transporte"},
            {"fecha": date(2025, 11, 10), "desc": "Walmart compras", "monto": 52000, "tipo": "DEBITO", "cat": "Supermercado"},
            {"fecha": date(2025, 11, 12), "desc": "Farmacia Fischel", "monto": 15000, "tipo": "DEBITO", "cat": "Salud"},
            {"fecha": date(2025, 11, 15), "desc": "CCSS cuota obrero", "monto": 48000, "tipo": "DEBITO", "cat": "Salud"},
            {"fecha": date(2025, 11, 18), "desc": "Gasolina Total", "monto": 22000, "tipo": "DEBITO", "cat": "Transporte"},
            {"fecha": date(2025, 11, 20), "desc": "PriceSmart mensual", "monto": 85000, "tipo": "DEBITO", "cat": "Supermercado"},
            {"fecha": date(2025, 11, 25), "desc": "AyA agua", "monto": 12000, "tipo": "DEBITO", "cat": "Servicios"},
            
            # Gustos (30%)
            {"fecha": date(2025, 11, 4), "desc": "Spotify Premium", "monto": 7500, "tipo": "DEBITO", "cat": "Entretenimiento"},
            {"fecha": date(2025, 11, 4), "desc": "Netflix", "monto": 9000, "tipo": "DEBITO", "cat": "Entretenimiento"},
            {"fecha": date(2025, 11, 7), "desc": "Uber Eats McDonald's", "monto": 12000, "tipo": "DEBITO", "cat": "Restaurantes"},
            {"fecha": date(2025, 11, 9), "desc": "Cine Cinépolis", "monto": 15000, "tipo": "DEBITO", "cat": "Entretenimiento"},
            {"fecha": date(2025, 11, 11), "desc": "Café Britt", "monto": 8500, "tipo": "DEBITO", "cat": "Restaurantes"},
            {"fecha": date(2025, 11, 14), "desc": "Amazon Prime", "monto": 8000, "tipo": "DEBITO", "cat": "Entretenimiento"},
            {"fecha": date(2025, 11, 16), "desc": "Almuerzo Nuestra Tierra", "monto": 18000, "tipo": "DEBITO", "cat": "Restaurantes"},
            {"fecha": date(2025, 11, 19), "desc": "Uber viaje Escazú", "monto": 5500, "tipo": "DEBITO", "cat": "Transporte"},
            {"fecha": date(2025, 11, 22), "desc": "Zara ropa", "monto": 45000, "tipo": "DEBITO", "cat": "Compras"},
            {"fecha": date(2025, 11, 24), "desc": "Bar con amigos", "monto": 25000, "tipo": "DEBITO", "cat": "Entretenimiento"},
            {"fecha": date(2025, 11, 28), "desc": "Rappi sushi", "monto": 22000, "tipo": "DEBITO", "cat": "Restaurantes"},
            
            # Ahorros (20%)
            {"fecha": date(2025, 11, 5), "desc": "Ahorro automático", "monto": 150000, "tipo": "DEBITO", "cat": "Ahorro"},
            {"fecha": date(2025, 11, 20), "desc": "Aporte meta Mundial", "monto": 100000, "tipo": "DEBITO", "cat": "Ahorro"},
        ]
        
        txn_count = 0
        for i, txn_info in enumerate(transacciones_data):
            # Crear email_id único para la simulación
            email_id = f"SIM_{profile.id[:8]}_{txn_info['fecha'].isoformat()}_{i}"
            
            # Verificar si ya existe
            existing_txn = db.execute(
                select(Transaction).where(
                    Transaction.email_id == email_id,
                )
            ).scalar_one_or_none()
            
            if existing_txn:
                continue
            
            tipo = TransactionType.SINPE if txn_info["tipo"] == "CREDITO" else TransactionType.PURCHASE
            
            txn = Transaction(
                profile_id=profile.id,
                email_id=email_id,
                fecha_transaccion=datetime.combine(txn_info["fecha"], datetime.min.time()),
                comercio=txn_info["desc"],
                monto_original=Decimal(str(txn_info["monto"])),
                monto_crc=Decimal(str(txn_info["monto"])),
                moneda_original=Currency.CRC,
                tipo_transaccion=tipo,
                banco=BankName.BAC,
                card_id=tarjetas_creadas[0].id if tarjetas_creadas else None,
            )
            db.add(txn)
            txn_count += 1
        
        db.flush()
        print(f"   ✅ {txn_count} transacciones importadas")
        
        # Calcular totales
        ingresos = sum(t["monto"] for t in transacciones_data if t["tipo"] == "CREDITO")
        gastos = sum(t["monto"] for t in transacciones_data if t["tipo"] == "DEBITO")
        print(f"\n   📊 Resumen Noviembre:")
        print(f"      Ingresos: ₡{ingresos:,.0f}")
        print(f"      Gastos:   ₡{gastos:,.0f}")
        print(f"      Balance:  ₡{ingresos - gastos:,.0f}")
        
        # ================================================================
        # PASO 8: Verificar notificaciones
        # ================================================================
        print_step(8, "Verificar notificaciones de tarjetas")
        
        notif_service = CardNotificationService(db)
        notifications = notif_service.get_all_pending_notifications(profile.id)
        
        if notifications:
            print(f"   🔔 {len(notifications)} notificaciones pendientes:\n")
            for notif in notifications:
                icon = "🔴" if notif.priority == "urgent" else "🟡" if notif.priority == "high" else "🔵"
                print(f"   {icon} {notif.title}")
                print(f"      {notif.message}")
                if notif.days_until_due is not None:
                    print(f"      Días para pago: {notif.days_until_due}")
                print()
        else:
            print("   ✅ No hay notificaciones urgentes")
        
        # ================================================================
        # PASO 9: Calcular patrimonio
        # ================================================================
        print_step(9, "Calcular patrimonio neto")
        
        # Sumar cuentas
        total_cuentas_crc = sum(
            c.saldo for c in cuentas_creadas 
            if c.moneda == Currency.CRC
        )
        total_cuentas_usd = sum(
            c.saldo for c in cuentas_creadas 
            if c.moneda == Currency.USD
        )
        
        # Sumar inversiones
        inversiones_db = db.execute(
            select(Investment).where(Investment.profile_id == profile.id)
        ).scalars().all()
        total_inv = sum(
            (i.monto_principal + i.rendimiento_acumulado) for i in inversiones_db
        )
        
        # Sumar deudas (tarjetas crédito)
        total_deuda = sum(
            t.current_balance or 0 
            for t in tarjetas_creadas 
            if t.tipo == CardType.CREDIT
        )
        
        # Tipo de cambio aproximado
        tipo_cambio = Decimal("515")
        total_usd_en_crc = total_cuentas_usd * tipo_cambio
        
        patrimonio_neto = total_cuentas_crc + total_usd_en_crc + total_inv - total_deuda
        
        print(f"\n   💰 PATRIMONIO NETO: ₡{patrimonio_neto:,.0f}")
        print(f"\n   Desglose:")
        print(f"   ├── 🏦 Cuentas CRC: ₡{total_cuentas_crc:,.0f}")
        print(f"   ├── 💵 Cuentas USD: ${total_cuentas_usd:,.0f} (₡{total_usd_en_crc:,.0f})")
        print(f"   ├── 📈 Inversiones: ₡{total_inv:,.0f}")
        print(f"   └── 💳 Deudas:     -₡{total_deuda:,.0f}")
        
        # ================================================================
        # Commit final
        # ================================================================
        db.commit()
        
        print_header("✅ SIMULACIÓN COMPLETADA")
        print(f"""
   Usuario: {profile.nombre}
   Profile ID: {profile.id}
   
   📊 Resumen:
   ├── Cuentas: {len(cuentas_creadas)}
   ├── Tarjetas: {len(tarjetas_creadas)}
   ├── Inversiones: {len(inversiones_db)}
   ├── Metas: {len(metas_data)}
   └── Transacciones: {txn_count}
   
   💰 Patrimonio Neto: ₡{patrimonio_neto:,.0f}
   
   🎯 Próximo paso: Abrir Streamlit y ver el dashboard
      poetry run streamlit run src/finanzas_tracker/dashboard/app.py
        """)


if __name__ == "__main__":
    run_simulation()
