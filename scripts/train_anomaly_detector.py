#!/usr/bin/env python3
"""Script para entrenar el detector de anomalías con datos históricos."""

import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datetime import datetime, timedelta

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.services.anomaly_detector import AnomalyDetectionService


logger = get_logger(__name__)


def main() -> None:
    """Entrena el detector de anomalías."""
    print("\n" + "=" * 70)
    print("🤖 ENTRENADOR DE DETECTOR DE ANOMALÍAS")
    print("=" * 70 + "\n")

    # 1. Seleccionar perfil
    with get_session() as session:
        profiles = session.query(Profile).filter(Profile.deleted_at.is_(None)).all()

        if not profiles:
            print("❌ No hay perfiles disponibles. Crea un perfil primero.")
            return

        print("Perfiles disponibles:\n")
        for i, profile in enumerate(profiles, 1):
            # Contar transacciones
            tx_count = (
                session.query(Transaction)
                .filter(
                    Transaction.profile_id == profile.id,
                    Transaction.deleted_at.is_(None),
                )
                .count()
            )
            print(f"  {i}. {profile.nombre} ({tx_count} transacciones)")

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

    # 2. Verificar datos disponibles
    print(f"\n📊 Analizando datos de '{profile.nombre}'...")

    with get_session() as session:
        # Contar transacciones por período
        six_months_ago = datetime.now() - timedelta(days=180)
        three_months_ago = datetime.now() - timedelta(days=90)
        one_month_ago = datetime.now() - timedelta(days=30)

        tx_6m = (
            session.query(Transaction)
            .filter(
                Transaction.profile_id == profile.id,
                Transaction.fecha_transaccion >= six_months_ago,
                Transaction.deleted_at.is_(None),
                Transaction.excluir_de_presupuesto == False,  # noqa: E712
            )
            .count()
        )

        tx_3m = (
            session.query(Transaction)
            .filter(
                Transaction.profile_id == profile.id,
                Transaction.fecha_transaccion >= three_months_ago,
                Transaction.deleted_at.is_(None),
                Transaction.excluir_de_presupuesto == False,  # noqa: E712
            )
            .count()
        )

        tx_1m = (
            session.query(Transaction)
            .filter(
                Transaction.profile_id == profile.id,
                Transaction.fecha_transaccion >= one_month_ago,
                Transaction.deleted_at.is_(None),
                Transaction.excluir_de_presupuesto == False,  # noqa: E712
            )
            .count()
        )

    print(f"\n📈 Transacciones disponibles:")
    print(f"  - Últimos 6 meses: {tx_6m}")
    print(f"  - Últimos 3 meses: {tx_3m}")
    print(f"  - Último mes: {tx_1m}")
    print()

    if tx_6m < 30:
        print(
            "⚠️  ADVERTENCIA: Tienes menos de 30 transacciones.\n"
            "   El modelo necesita al menos 30 transacciones para entrenar correctamente.\n"
            "   Procesa más correos primero usando 'make process'.\n"
        )
        response = input("¿Continuar de todas formas? (s/n): ")
        if response.lower() != "s":
            print("❌ Cancelado")
            return

    # 3. Entrenar modelo
    print("\n🔧 Entrenando modelo de detección de anomalías...\n")

    detector = AnomalyDetectionService()
    success = detector.train(profile_id=profile.id, min_transactions=30)

    if not success:
        print("❌ No se pudo entrenar el modelo (insuficientes datos)")
        return

    # 4. Mostrar estadísticas
    print("\n✅ Modelo entrenado exitosamente!\n")
    print("📊 Estadísticas del modelo:")
    print(f"  - Categorías conocidas: {len(detector.category_encoder)}")
    print(f"  - Categorías con estadísticas: {len(detector.category_stats)}")
    print()

    # Mostrar algunas categorías con stats
    print("Categorías aprendidas (top 5 por transacciones):\n")
    with get_session() as session:
        from collections import Counter

        transactions = (
            session.query(Transaction)
            .filter(
                Transaction.profile_id == profile.id,
                Transaction.deleted_at.is_(None),
                Transaction.subcategory_id.isnot(None),
            )
            .all()
        )

        cat_counts = Counter(t.subcategory_id for t in transactions)
        for cat_id, count in cat_counts.most_common(5):
            stats = detector.category_stats.get(cat_id, {})
            # Buscar el nombre
            tx = next((t for t in transactions if t.subcategory_id == cat_id), None)
            cat_name = tx.subcategory.nombre_completo if tx and tx.subcategory else cat_id[:8]

            if stats:
                print(
                    f"  - {cat_name}: {count} txs | "
                    f"Promedio: ₡{stats['mean']:,.0f} | "
                    f"Rango: ₡{stats['min']:,.0f} - ₡{stats['max']:,.0f}"
                )

    # 5. Opción de probar
    print("\n" + "=" * 70)
    print("🧪 Probar modelo con transacciones existentes")
    print("=" * 70 + "\n")

    response = input("¿Quieres probar el modelo con tus transacciones recientes? (s/n): ")

    if response.lower() == "s":
        print("\n🔍 Probando modelo con últimas 20 transacciones...\n")

        with get_session() as session:
            recent = (
                session.query(Transaction)
                .filter(
                    Transaction.profile_id == profile.id,
                    Transaction.deleted_at.is_(None),
                )
                .order_by(Transaction.fecha_transaccion.desc())
                .limit(20)
                .all()
            )

            anomalies_found = 0
            for tx in recent:
                result = detector.detect(tx)
                if result.is_anomaly:
                    anomalies_found += 1
                    print(
                        f"⚠️  {tx.fecha_transaccion.date()} | {tx.comercio[:30]:30} | "
                        f"₡{tx.monto_crc:>12,.0f} | {result.reason}"
                    )

            if anomalies_found == 0:
                print("✅ No se encontraron anomalías en las últimas 20 transacciones")
            else:
                print(f"\n⚠️  Se detectaron {anomalies_found} anomalías")

    print("\n" + "=" * 70)
    print("✅ ENTRENAMIENTO COMPLETADO")
    print("=" * 70)
    print("\nEl modelo se guardó en: data/anomaly_model.pkl")
    print("\nAhora cuando proceses correos nuevos, se detectarán automáticamente")
    print("las transacciones anómalas usando este modelo.\n")
    print("💡 Tip: Re-entrena el modelo cada mes para mejorar la precisión.\n")


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
