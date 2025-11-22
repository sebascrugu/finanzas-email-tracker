"""Script para gestionar ingresos del usuario."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
import sys


# Agregar el directorio src al path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.enums import Currency, IncomeType, RecurrenceFrequency
from finanzas_tracker.models.income import Income
from finanzas_tracker.models.user import User
from finanzas_tracker.services.exchange_rate import ExchangeRateService


logger = get_logger(__name__)


def listar_ingresos(user_email: str) -> None:
    """
    Lista todos los ingresos activos del usuario.

    Args:
        user_email: Email del usuario
    """
    with get_session() as session:
        ingresos = (
            session.query(Income)
            .filter(Income.user_email == user_email, Income.deleted_at.is_(None))
            .order_by(Income.fecha_ingreso.desc())
            .all()
        )

        if not ingresos:
            logger.info(" No tienes ingresos registrados todavía")
            return

        logger.info(f"\n Tienes {len(ingresos)} ingreso(s) registrado(s):\n")

        for i, ingreso in enumerate(ingresos, 1):
            recurrente = "🔁" if ingreso.es_recurrente else ""
            logger.info(f"{i}. {recurrente} {ingreso.tipo.value.upper()}")
            logger.info(f"    {ingreso.monto_display}")
            logger.info(f"    {ingreso.fecha.strftime('%d/%m/%Y')}")
            logger.info(f"    {ingreso.descripcion}")

            if ingreso.es_recurrente and ingreso.frecuencia:
                logger.info(f"    {ingreso.frecuencia.value}")
                if ingreso.proximo_ingreso_esperado:
                    logger.info(
                        f"     Próximo: {ingreso.proximo_ingreso_esperado.strftime('%d/%m/%Y')}"
                    )

            logger.info("")


def calcular_proximo_ingreso_esperado(fecha_actual: date, frecuencia: RecurrenceFrequency) -> date:
    """
    Calcula la fecha del próximo ingreso según la frecuencia.

    Args:
        fecha_actual: Fecha del ingreso actual
        frecuencia: Frecuencia de recurrencia

    Returns:
        Fecha del próximo ingreso
    """
    if frecuencia == RecurrenceFrequency.DAILY:
        return fecha_actual + timedelta(days=1)
    if frecuencia == RecurrenceFrequency.WEEKLY:
        return fecha_actual + timedelta(weeks=1)
    if frecuencia == RecurrenceFrequency.BIWEEKLY:
        return fecha_actual + timedelta(weeks=2)
    if frecuencia == RecurrenceFrequency.MONTHLY:
        # Próximo mes, mismo día
        next_month = fecha_actual.month + 1
        year = fecha_actual.year
        if next_month > 12:
            next_month = 1
            year += 1
        try:
            return date(year, next_month, fecha_actual.day)
        except ValueError:
            # Si el día no existe en el próximo mes (ej: 31 de feb)
            # usar el último día del mes
            if next_month == 2:
                return date(year, next_month, 28)
            return date(year, next_month, 30)
    elif frecuencia == RecurrenceFrequency.BIMONTHLY:
        return calcular_proximo_ingreso_esperado(
            calcular_proximo_ingreso_esperado(fecha_actual, RecurrenceFrequency.MONTHLY),
            RecurrenceFrequency.MONTHLY,
        )
    elif frecuencia == RecurrenceFrequency.QUARTERLY:
        # 3 meses después
        months = fecha_actual.month + 3
        year = fecha_actual.year + (months - 1) // 12
        month = ((months - 1) % 12) + 1
        try:
            return date(year, month, fecha_actual.day)
        except ValueError:
            return date(year, month, 28)
    elif frecuencia == RecurrenceFrequency.SEMIANNUAL:
        # 6 meses después
        months = fecha_actual.month + 6
        year = fecha_actual.year + (months - 1) // 12
        month = ((months - 1) % 12) + 1
        try:
            return date(year, month, fecha_actual.day)
        except ValueError:
            return date(year, month, 28)
    elif frecuencia == RecurrenceFrequency.ANNUAL:
        try:
            return date(fecha_actual.year + 1, fecha_actual.month, fecha_actual.day)
        except ValueError:
            return date(fecha_actual.year + 1, fecha_actual.month, 28)
    else:
        # ONE_TIME
        return fecha_actual


def agregar_ingreso_interactivo(user_email: str) -> None:
    """
    Agrega un ingreso de forma interactiva.

    Args:
        user_email: Email del usuario
    """
    logger.info("\n" + "=" * 80)
    logger.info(" REGISTRAR NUEVO INGRESO")
    logger.info("=" * 80 + "\n")

    # Paso 1: Tipo de ingreso
    tipos = [
        ("1", IncomeType.SALARY, " Salario"),
        ("2", IncomeType.PENSION, " Pensión"),
        ("3", IncomeType.FREELANCE, "💻 Freelance"),
        ("4", IncomeType.SALE, "  Venta (ej: PS5, carro)"),
        ("5", IncomeType.INVESTMENT_RETURN, " Rendimiento inversión"),
        ("6", IncomeType.GIFT, " Regalo/Ayuda"),
        ("7", IncomeType.OTHER, " Otro"),
    ]

    for _num, _, _desc in tipos:
        pass

    while True:
        tipo_choice = input("\nElige el tipo (1-7): ").strip()
        tipo_map = {num: tipo for num, tipo, _ in tipos}
        if tipo_choice in tipo_map:
            tipo = tipo_map[tipo_choice]
            break

    # Paso 2: Monto y moneda
    while True:
        monto_str = input("\n Monto (ej: 500000 o 1000): ").strip()
        try:
            monto = Decimal(monto_str)
            if monto <= 0:
                continue
            break
        except:
            pass

    while True:
        moneda_choice = input("Moneda (1=CRC, 2=USD): ").strip()
        if moneda_choice == "1":
            moneda = Currency.CRC
            break
        if moneda_choice == "2":
            moneda = Currency.USD
            break

    # Paso 3: Fecha

    while True:
        fecha_choice = input("Elige opción (1-2): ").strip()
        if fecha_choice == "1":
            fecha_ingreso = date.today()
            break
        if fecha_choice == "2":
            fecha_str = input("Fecha (DD/MM/YYYY): ").strip()
            try:
                fecha_ingreso = datetime.strptime(fecha_str, "%d/%m/%Y").date()
                break
            except:
                pass
        else:
            pass

    # Paso 4: Descripción (requerida)
    while True:
        descripcion = input("\n Descripción (ej: 'Salario Nov 2025', 'Venta PS5'): ").strip()
        if descripcion:
            break

    # Paso 5: ¿Es recurrente?

    es_recurrente = False
    frecuencia = RecurrenceFrequency.ONE_TIME
    proximo_ingreso_esperado = None

    while True:
        rec_choice = input("Elige opción (1-2): ").strip()
        if rec_choice == "1":
            es_recurrente = True

            # Preguntar frecuencia
            frecuencias = [
                ("1", RecurrenceFrequency.WEEKLY, " Semanal"),
                ("2", RecurrenceFrequency.BIWEEKLY, "📆 Quincenal (cada 2 semanas)"),
                ("3", RecurrenceFrequency.MONTHLY, "🗓️  Mensual"),
                ("4", RecurrenceFrequency.QUARTERLY, " Trimestral"),
                ("5", RecurrenceFrequency.ANNUAL, " Anual"),
            ]

            for _num, _, _desc in frecuencias:
                pass

            while True:
                freq_choice = input("\nElige frecuencia (1-5): ").strip()
                freq_map = {num: freq for num, freq, _ in frecuencias}
                if freq_choice in freq_map:
                    frecuencia = freq_map[freq_choice]
                    proximo_ingreso_esperado = calcular_proximo_ingreso_esperado(
                        fecha_ingreso, frecuencia
                    )
                    break

            break
        if rec_choice == "2":
            break

    # Paso 7: Convertir a CRC si es USD
    tipo_cambio = None
    if moneda == Currency.USD:
        logger.info(f"\n Convirtiendo ${monto} USD a CRC...")
        exchange_service = ExchangeRateService()
        tipo_cambio = exchange_service.get_rate(fecha_ingreso)
        monto_crc = monto * Decimal(str(tipo_cambio))
        logger.info(f"   Tipo de cambio: ₡{tipo_cambio:.2f}")
        logger.info(f"   Monto en CRC: ₡{monto_crc:,.2f}")
    else:
        monto_crc = monto

    # Paso 6: Resumen y confirmación
    if moneda == Currency.USD:
        pass
    if es_recurrente:
        pass
    else:
        pass

    confirmar = input("\n¿Guardar este ingreso? (S/n): ").strip().lower()
    if confirmar == "n":
        logger.warning(" Ingreso cancelado")
        return

    # Paso 7: Guardar en base de datos
    try:
        with get_session() as session:
            nuevo_ingreso = Income(
                user_email=user_email,
                tipo=tipo,
                descripcion=descripcion,
                monto_original=monto,
                moneda_original=moneda,
                monto_crc=monto_crc,
                tipo_cambio_usado=Decimal(str(tipo_cambio)) if tipo_cambio else None,
                fecha=fecha_ingreso,
                es_recurrente=es_recurrente,
                frecuencia=frecuencia if es_recurrente else None,
                proximo_ingreso_esperado=proximo_ingreso_esperado if es_recurrente else None,
            )

            session.add(nuevo_ingreso)
            session.commit()

            logger.success("\n ¡Ingreso registrado exitosamente!")
            logger.info(f"   ID: {nuevo_ingreso.id[:8]}...")

    except Exception as e:
        logger.error(f" Error al guardar ingreso: {e}")
        raise


def mostrar_balance_mensual(user_email: str) -> None:
    """
    Muestra el balance del mes actual (ingresos vs gastos).

    Args:
        user_email: Email del usuario
    """
    from finanzas_tracker.models.transaction import Transaction

    with get_session() as session:
        # Mes actual
        hoy = date.today()
        primer_dia = date(hoy.year, hoy.month, 1)

        # Calcular próximo mes
        if hoy.month == 12:
            proximo_mes = date(hoy.year + 1, 1, 1)
        else:
            proximo_mes = date(hoy.year, hoy.month + 1, 1)

        # Ingresos del mes
        ingresos = (
            session.query(Income)
            .filter(
                Income.user_email == user_email,
                Income.fecha >= primer_dia,
                Income.fecha < proximo_mes,
                Income.deleted_at.is_(None),
            )
            .all()
        )

        total_ingresos = sum(i.monto_crc for i in ingresos)

        # Gastos del mes (solo transacciones que cuentan en presupuesto)
        gastos = (
            session.query(Transaction)
            .filter(
                Transaction.user_email == user_email,
                Transaction.fecha_transaccion >= primer_dia,
                Transaction.fecha_transaccion < proximo_mes,
                Transaction.deleted_at.is_(None),
                Transaction.excluir_de_presupuesto == False,  # noqa: E712
            )
            .all()
        )

        total_gastos = sum(g.monto_crc for g in gastos)
        balance = total_ingresos - total_gastos

        # Mostrar resultados
        logger.info("\n" + "=" * 80)
        logger.info(f" BALANCE DE {hoy.strftime('%B %Y').upper()}")
        logger.info("=" * 80 + "\n")

        logger.info(f" Ingresos:  ₡{total_ingresos:>15,.2f} ({len(ingresos)} registro(s))")
        logger.info(f" Gastos:    ₡{total_gastos:>15,.2f} ({len(gastos)} transacción(es))")
        logger.info("   " + "─" * 76)

        if balance >= 0:
            logger.success(f" Balance:   ₡{balance:>15,.2f} (POSITIVO)")
        else:
            logger.warning(f"  Balance:   ₡{balance:>15,.2f} (NEGATIVO)")

        logger.info("")

        # Calcular porcentaje gastado
        if total_ingresos > 0:
            porcentaje = (total_gastos / total_ingresos) * 100
            logger.info(f" Has gastado el {porcentaje:.1f}% de tus ingresos del mes")

            if porcentaje > 100:
                logger.warning("  ¡Estás gastando más de lo que ingresas!")
            elif porcentaje > 90:
                logger.warning("  ¡Cuidado! Ya gastaste más del 90%")
            elif porcentaje > 75:
                logger.info(" Estás en buen camino, pero controla tus gastos")
            else:
                logger.success(" ¡Excelente control de gastos!")

        logger.info("")


def menu_principal(user_email: str) -> None:
    """
    Muestra el menú principal de gestión de ingresos.

    Args:
        user_email: Email del usuario
    """
    while True:
        logger.info("\n" + "=" * 80)
        logger.info(" GESTIÓN DE INGRESOS")
        logger.info("=" * 80 + "\n")

        choice = input("Elige una opción (0-3): ").strip()

        if choice == "1":
            mostrar_balance_mensual(user_email)
        elif choice == "2":
            listar_ingresos(user_email)
        elif choice == "3":
            agregar_ingreso_interactivo(user_email)
        elif choice == "0":
            logger.info(" ¡Hasta luego!")
            break
        else:
            logger.warning(" Opción inválida. Intenta de nuevo.")


def main() -> None:
    """Función principal."""
    try:
        with get_session() as session:
            # Obtener usuario activo
            user = session.query(User).filter(User.activo == True).first()  # noqa: E712
            if not user:
                logger.error(" No hay usuario activo. Ejecuta 'make setup-user' primero.")
                return

            logger.info(f" Usuario: {user.nombre} ({user.email})")

        # Mostrar menú
        menu_principal(user.email)

    except KeyboardInterrupt:
        logger.warning("\n\n  Operación cancelada por el usuario")
    except Exception as e:
        logger.error(f"\n\n Error: {e}")
        raise


if __name__ == "__main__":
    main()
