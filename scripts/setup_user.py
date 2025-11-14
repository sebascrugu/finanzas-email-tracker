"""Script para configurar un nuevo usuario del sistema."""

from datetime import date
from decimal import Decimal
from pathlib import Path
import sys

# Agregar el directorio src al path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session, init_db
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.budget import Budget
from finanzas_tracker.models.card import Card
from finanzas_tracker.models.user import User
from finanzas_tracker.utils.seed_categories import seed_categories

logger = get_logger(__name__)


def setup_user() -> None:
    """
    Configura un nuevo usuario en el sistema.

    Solicita:
    - Email y nombre
    - Salario mensual
    - Distribución de presupuesto (50/30/20 o personalizado)
    - Tarjetas bancarias
    """
    logger.info("=" * 80)
    logger.info("👤 SETUP DE USUARIO")
    logger.info("=" * 80)
    logger.info("")

    # Inicializar BD y categorías
    init_db()
    seed_categories()
    logger.info("")

    # Solicitar información del usuario
    logger.info("📋 INFORMACIÓN PERSONAL:")
    logger.info("")

    email = input("📧 Email (Outlook/Hotmail): ").strip()
    nombre = input("👤 Nombre completo: ").strip()

    logger.info("")
    logger.info("💰 CONFIGURACIÓN DE PRESUPUESTO:")
    logger.info("")
    logger.info("💡 Tip: Usa tu salario NETO (después de deducciones)")
    logger.info("    Ejemplo: Si te depositan ₡280,000, ese es tu NETO")
    logger.info("")

    salario_str = input("💵 Salario mensual NETO (lo que te depositan): ₡").strip()
    salario = Decimal(salario_str.replace(",", ""))

    logger.info("")
    logger.info("📊 REGLA 50/30/20 (Obligatoria):")
    logger.info("")
    logger.info("  ✅ 50% Necesidades → ₡{:,.0f}".format(salario * Decimal("0.50")))
    logger.info("     (Transporte, trabajo, servicios básicos)")
    logger.info("")
    logger.info("  ✅ 30% Gustos → ₡{:,.0f}".format(salario * Decimal("0.30")))
    logger.info("     (Comida fuera, entretenimiento, shopping)")
    logger.info("")
    logger.info("  ✅ 20% Ahorros → ₡{:,.0f}".format(salario * Decimal("0.20")))
    logger.info("     (Ahorro regular, emergencias, metas)")
    logger.info("")

    # Obligatorio: usar 50/30/20
    pct_necesidades = Decimal("50.00")
    pct_gustos = Decimal("30.00")
    pct_ahorros = Decimal("20.00")

    logger.info("")
    logger.info("💳 TARJETAS BANCARIAS:")
    logger.info("")
    logger.info("Registra tus tarjetas (necesario para detectar uso de crédito)")
    logger.info("")

    cards = []
    while True:
        ultimos_4 = input("Últimos 4 dígitos de la tarjeta (Enter para terminar): ").strip()
        if not ultimos_4:
            break

        tipo = input("Tipo (debito/credito): ").strip().lower()
        if tipo not in ["debito", "credito"]:
            logger.error("Tipo debe ser 'debito' o 'credito'")
            continue

        banco = input("Banco (bac/popular): ").strip().lower()
        if banco not in ["bac", "popular"]:
            logger.error("Banco debe ser 'bac' o 'popular'")
            continue

        alias = input("Alias opcional (ej: 'Tarjeta principal'): ").strip() or None

        cards.append(
            {
                "ultimos_4_digitos": ultimos_4,
                "tipo": tipo,
                "banco": banco,
                "alias": alias,
            }
        )
        logger.success(f"✅ Tarjeta ****{ultimos_4} agregada")
        logger.info("")

    # Guardar en base de datos
    logger.info("")
    logger.info("💾 Guardando configuración...")
    logger.info("")

    try:
        with get_session() as session:
            # Crear usuario
            user = User(
                email=email,
                nombre=nombre,
                activo=True,
            )
            session.add(user)
            session.flush()

            # Crear presupuesto inicial
            budget = Budget(
                user_email=user.email,
                salario_mensual=salario,
                fecha_inicio=date.today(),
                fecha_fin=None,  # Presupuesto actual
                porcentaje_necesidades=pct_necesidades,
                porcentaje_gustos=pct_gustos,
                porcentaje_ahorros=pct_ahorros,
                notas="Presupuesto inicial",
            )
            session.add(budget)

            # Crear tarjetas
            for card_data in cards:
                card = Card(
                    user_email=user.email,
                    **card_data,
                )
                session.add(card)

            session.commit()

            logger.success("=" * 80)
            logger.success("✅ USUARIO CONFIGURADO EXITOSAMENTE")
            logger.success("=" * 80)
            logger.info("")
            logger.info(f"👤 Usuario: {nombre} ({email})")
            logger.info(f"💰 Salario: ₡{salario:,.0f}")
            logger.info(f"📊 Distribución: {pct_necesidades}% / {pct_gustos}% / {pct_ahorros}%")
            logger.info("")
            logger.info("💵 Presupuestos mensuales:")
            logger.info(f"  💰 Necesidades: ₡{budget.monto_necesidades:,.0f}")
            logger.info(f"  🎮 Gustos: ₡{budget.monto_gustos:,.0f}")
            logger.info(f"  💎 Ahorros: ₡{budget.monto_ahorros:,.0f}")
            logger.info("")
            logger.info(f"💳 Tarjetas registradas: {len(cards)}")
            logger.info("")
            logger.info("🎯 PRÓXIMOS PASOS:")
            logger.info("  1. make process  → Procesar transacciones de correos")
            logger.info("  2. make run-dashboard  → Ver dashboard interactivo")
            logger.info("")

    except Exception as e:
        logger.error(f"❌ Error guardando configuración: {e}")
        raise


def main() -> None:
    """Función principal."""
    try:
        setup_user()
    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  Setup cancelado por el usuario")
    except Exception as e:
        logger.error(f"\n\n❌ Error en setup: {e}")
        raise


if __name__ == "__main__":
    main()
