#!/usr/bin/env python3
"""Script para detectar suscripciones recurrentes en transacciones existentes."""

import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.subscription import Subscription
from finanzas_tracker.services.subscription_detector import subscription_detector


logger = get_logger(__name__)


def main() -> None:
    """Detecta suscripciones recurrentes."""
    print("\n" + "=" * 70)
    print("🔍 DETECTOR DE SUSCRIPCIONES RECURRENTES")
    print("=" * 70 + "\n")

    # 1. Seleccionar perfil
    with get_session() as session:
        profiles = session.query(Profile).filter(Profile.activo == True).all()  # noqa: E712

        if not profiles:
            print("❌ No hay perfiles disponibles. Crea un perfil primero.")
            return

        print("Perfiles disponibles:\n")
        for i, profile in enumerate(profiles, 1):
            print(f"  {i}. {profile.nombre_completo}")

        print()
        try:
            choice = int(input("Selecciona un perfil (número): "))
            if choice < 1 or choice > len(profiles):
                print("❌ Opción inválida")
                return
            profile = profiles[choice - 1]
        except (ValueError, KeyboardInterrupt):
            print("\n❌ Cancelado")
            return

    # 2. Detectar suscripciones
    print(f"\n🔍 Analizando transacciones de '{profile.nombre}'...\n")
    print("Buscando patrones de cobros recurrentes en los últimos 6 meses...")
    print("(mismo comercio + monto similar + frecuencia regular)\n")

    detected = subscription_detector.detect_all_subscriptions(profile.id, months_back=6)

    if not detected:
        print("ℹ️  No se detectaron suscripciones recurrentes.\n")
        print("💡 Tip: Necesitas al menos 2 cobros del mismo servicio para detectar un patrón.\n")
        return

    # 3. Mostrar suscripciones detectadas
    print(f"\n{'='*70}")
    print(f"✅ SUSCRIPCIONES DETECTADAS: {len(detected)}")
    print(f"{'='*70}\n")

    for i, sub in enumerate(detected, 1):
        # sub es DetectionResult
        proxima = sub.ultima_fecha + __import__('datetime').timedelta(days=sub.frecuencia_dias)

        # Determinar frecuencia display
        if sub.frecuencia_dias <= 7:
            freq_display = "Semanal"
        elif sub.frecuencia_dias <= 15:
            freq_display = "Quincenal"
        elif sub.frecuencia_dias <= 35:
            freq_display = "Mensual"
        else:
            freq_display = f"{sub.frecuencia_dias} días"

        print(f"{i}. {sub.comercio}")
        if sub.monto_min == sub.monto_max:
            print(f"   Monto: ₡{sub.monto_promedio:,.2f}")
        else:
            print(f"   Monto: ₡{sub.monto_promedio:,.2f} (rango: ₡{sub.monto_min:,.0f} - ₡{sub.monto_max:,.0f})")
        print(f"   Frecuencia: ~{sub.frecuencia_dias} días ({freq_display})")
        print(f"   Cobros detectados: {sub.occurrences}")
        print(f"   Última vez: {sub.ultima_fecha.strftime('%d/%m/%Y')}")
        print(f"   Próximo estimado: {proxima.strftime('%d/%m/%Y')}")
        print(f"   Confianza: {sub.confidence:.1f}%")
        print()

    # 4. Preguntar si quiere guardar en DB
    print(f"{'='*70}")
    response = input("\n¿Guardar estas suscripciones en la base de datos? (s/n): ")

    if response.lower() != "s":
        print("❌ Cancelado - no se guardó nada")
        return

    # 5. Sincronizar con DB
    print("\n💾 Guardando suscripciones...\n")

    stats = subscription_detector.sync_subscriptions_to_db(profile.id)

    # 6. Mostrar resultado
    print("\n" + "=" * 70)
    print("✅ DETECCIÓN COMPLETADA")
    print("=" * 70 + "\n")

    print(f"📊 Estadísticas:")
    print(f"  • Nuevas suscripciones: {stats['created']}")
    print(f"  • Actualizadas: {stats['updated']}")
    print(f"  • Desactivadas: {stats['deactivated']}")
    print(f"  • Total detectado: {stats['total_detected']}")
    print()

    # 7. Mostrar suscripciones activas en DB
    print("📋 Suscripciones activas guardadas:\n")

    with get_session() as session:
        active_subs = (
            session.query(Subscription)
            .filter(
                Subscription.profile_id == profile.id,
                Subscription.is_active == True,  # noqa: E712
                Subscription.deleted_at.is_(None),
            )
            .order_by(Subscription.monto_promedio.desc())
            .all()
        )

        total_mensual = sum(
            sub.monto_promedio for sub in active_subs if sub.frecuencia_dias <= 35
        )

        for i, sub in enumerate(active_subs, 1):
            days_until = sub.dias_hasta_proximo_cobro
            status_emoji = "🔜" if sub.esta_proxima else "✅"

            print(f"{status_emoji} {sub.comercio}")
            print(f"     ₡{sub.monto_promedio:,.0f} cada {sub.frecuencia_dias} días")

            if days_until > 0:
                print(f"     Próximo cobro en {days_until} días")
            elif days_until == 0:
                print(f"     Próximo cobro HOY")
            else:
                print(f"     ⚠️  Vencida hace {abs(days_until)} días")

            print()

        print(f"{'='*70}")
        print(f"\n💰 Total mensual aproximado: ₡{total_mensual:,.0f}\n")

    # 8. Tips finales
    print("💡 Tips:")
    print("  • Las suscripciones se actualizan automáticamente al procesar correos")
    print("  • Puedes ver todas tus suscripciones en el dashboard")
    print("  • Re-ejecuta este script mensualmente para actualizar\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelado por el usuario")
        sys.exit(1)
    except Exception as e:
        logger.exception("Error inesperado")
        print(f"\n❌ Error: {e}")
        sys.exit(1)
