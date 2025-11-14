"""Script para mostrar balance rápido del mes actual."""

import sys
from datetime import date
from pathlib import Path

# Agregar el directorio src al path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.income import Income
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.models.user import User

logger = get_logger(__name__)


def main() -> None:
    """Muestra el balance rápido del mes actual."""
    try:
        with get_session() as session:
            # Obtener usuario activo
            user = session.query(User).filter(User.activo == True).first()  # noqa: E712
            if not user:
                logger.error("❌ No hay usuario activo. Ejecuta 'make setup-user' primero.")
                return

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
                    Income.user_email == user.email,
                    Income.fecha >= primer_dia,
                    Income.fecha < proximo_mes,
                    Income.deleted_at.is_(None),
                )
                .all()
            )

            total_ingresos = sum(i.monto_crc for i in ingresos)

            # Gastos del mes (solo los que cuentan en presupuesto)
            gastos = (
                session.query(Transaction)
                .filter(
                    Transaction.user_email == user.email,
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
            print()
            logger.info("=" * 80)
            logger.info(f"📊 BALANCE DE {hoy.strftime('%B %Y').upper()}")
            logger.info("=" * 80)
            print()

            logger.info(f"💰 Ingresos:  ₡{total_ingresos:>15,.2f}")
            logger.info(f"💸 Gastos:    ₡{total_gastos:>15,.2f}")
            logger.info("   " + "─" * 76)

            if balance >= 0:
                logger.success(f"✅ Balance:   ₡{balance:>15,.2f} (POSITIVO)")
            else:
                logger.warning(f"⚠️  Balance:   ₡{balance:>15,.2f} (NEGATIVO)")

            print()

            # Calcular porcentaje gastado
            if total_ingresos > 0:
                porcentaje = (total_gastos / total_ingresos) * 100
                logger.info(f"📊 Has gastado el {porcentaje:.1f}% de tus ingresos")

                if porcentaje > 100:
                    logger.warning("⚠️  ¡Gastas más de lo que ingresas!")
                elif porcentaje > 90:
                    logger.warning("⚠️  ¡Cuidado! Ya gastaste más del 90%")
                elif porcentaje > 75:
                    logger.info("💡 Buen control, pero vigila tus gastos")
                else:
                    logger.success("✅ ¡Excelente control de gastos!")
            elif total_ingresos == 0 and total_gastos > 0:
                logger.warning("⚠️  Tienes gastos pero no ingresos registrados")
                logger.info("💡 Ejecuta 'make income' para registrar tus ingresos")
            elif total_ingresos == 0 and total_gastos == 0:
                logger.info("📭 No hay transacciones para este mes todavía")

            print()

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
