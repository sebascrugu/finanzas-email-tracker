"""
Servicio de Sincronización en Background.

Ejecuta tareas periódicas:
- Sincronizar emails cada X horas
- Verificar vencimientos de tarjetas
- Actualizar tipos de cambio
- Cerrar ciclos de facturación vencidos
"""

from collections.abc import Callable
from datetime import date, datetime
import logging
import threading

from sqlalchemy import select

from finanzas_tracker.core.database import SessionLocal
from finanzas_tracker.models import BillingCycle, Profile
from finanzas_tracker.models.enums import BillingCycleStatus


logger = logging.getLogger(__name__)


class SyncScheduler:
    """
    Scheduler simple para tareas en background.

    En producción usar APScheduler, Celery, o similar.
    Esta implementación es para desarrollo/demo.
    """

    def __init__(self) -> None:
        """Inicializa el scheduler."""
        self._running = False
        self._thread: threading.Thread | None = None
        self._tasks: dict[str, dict] = {}

    def add_task(
        self,
        name: str,
        func: Callable,
        interval_seconds: int,
        run_immediately: bool = False,
    ) -> None:
        """
        Agrega una tarea al scheduler.

        Args:
            name: Nombre único de la tarea
            func: Función a ejecutar
            interval_seconds: Intervalo entre ejecuciones
            run_immediately: Si ejecutar al iniciar
        """
        self._tasks[name] = {
            "func": func,
            "interval": interval_seconds,
            "last_run": None if run_immediately else datetime.now(),
        }
        logger.info(f"Tarea '{name}' registrada (cada {interval_seconds}s)")

    def start(self) -> None:
        """Inicia el scheduler en un thread separado."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("🔄 Scheduler iniciado")

    def stop(self) -> None:
        """Detiene el scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("🛑 Scheduler detenido")

    def _run_loop(self) -> None:
        """Loop principal del scheduler."""
        import time

        while self._running:
            now = datetime.now()

            for name, task in self._tasks.items():
                last_run = task["last_run"]
                interval = task["interval"]

                if last_run is None or (now - last_run).total_seconds() >= interval:
                    try:
                        logger.debug(f"Ejecutando tarea '{name}'...")
                        task["func"]()
                        task["last_run"] = now
                    except Exception as e:
                        logger.error(f"Error en tarea '{name}': {e}")

            time.sleep(60)  # Revisar cada minuto


# Instancia global del scheduler
scheduler = SyncScheduler()


# =============================================================================
# Tareas de Sincronización
# =============================================================================


def sync_emails_task() -> None:
    """
    Tarea: Sincronizar emails de bancos.

    Busca nuevos emails y parsea transacciones.
    """
    logger.info("📧 Sincronizando emails...")

    with SessionLocal() as db:
        # Obtener perfiles con email conectado
        profiles = db.execute(select(Profile).where(Profile.deleted_at.is_(None))).scalars().all()

        for profile in profiles:
            try:
                # Aquí iría la lógica de sync
                # Por ahora solo log
                logger.debug(f"Sync para perfil {profile.id[:8]}...")
            except Exception as e:
                logger.error(f"Error sync perfil {profile.id[:8]}: {e}")

    logger.info("✅ Sync de emails completado")


def check_billing_cycles_task() -> None:
    """
    Tarea: Verificar y actualizar ciclos de facturación.

    - Cierra ciclos que pasaron la fecha de corte
    - Marca como vencidos los que pasaron fecha de pago
    - Crea nuevos ciclos para el siguiente período
    """
    logger.info("💳 Verificando ciclos de facturación...")

    today = date.today()

    with SessionLocal() as db:
        # 1. Ciclos abiertos que pasaron fecha de corte → Cerrar
        open_cycles = (
            db.execute(
                select(BillingCycle).where(
                    BillingCycle.status == BillingCycleStatus.OPEN,
                    BillingCycle.fecha_corte < today,
                    BillingCycle.deleted_at.is_(None),
                )
            )
            .scalars()
            .all()
        )

        for cycle in open_cycles:
            cycle.cerrar_ciclo()
            logger.info(f"Ciclo {cycle.id[:8]} cerrado (corte: {cycle.fecha_corte})")

        # 2. Ciclos cerrados/parciales que pasaron fecha de pago → Vencidos
        pending_cycles = (
            db.execute(
                select(BillingCycle).where(
                    BillingCycle.status.in_(
                        [
                            BillingCycleStatus.CLOSED,
                            BillingCycleStatus.PARTIAL,
                        ]
                    ),
                    BillingCycle.fecha_pago < today,
                    BillingCycle.deleted_at.is_(None),
                )
            )
            .scalars()
            .all()
        )

        for cycle in pending_cycles:
            if not cycle.esta_pagado:
                cycle.marcar_vencido()
                logger.warning(f"Ciclo {cycle.id[:8]} VENCIDO (pago: {cycle.fecha_pago})")

        db.commit()

    logger.info("✅ Verificación de ciclos completada")


def check_card_alerts_task() -> None:
    """
    Tarea: Generar alertas de vencimiento de tarjetas.

    Notifica cuando:
    - Faltan 3 días para fecha de pago
    - Faltan 1 día para fecha de pago
    - Es el día de pago
    """
    logger.info("🔔 Verificando alertas de tarjetas...")

    today = date.today()
    alert_days = [3, 1, 0]  # Días antes del vencimiento

    with SessionLocal() as db:
        # Obtener ciclos pendientes
        pending = (
            db.execute(
                select(BillingCycle).where(
                    BillingCycle.status.in_(
                        [
                            BillingCycleStatus.CLOSED,
                            BillingCycleStatus.PARTIAL,
                        ]
                    ),
                    BillingCycle.deleted_at.is_(None),
                )
            )
            .scalars()
            .all()
        )

        alerts = []
        for cycle in pending:
            days_until = (cycle.fecha_pago - today).days

            if days_until in alert_days:
                alert = {
                    "cycle_id": cycle.id,
                    "card_id": cycle.card_id,
                    "days_until": days_until,
                    "amount": float(cycle.saldo_pendiente),
                    "due_date": str(cycle.fecha_pago),
                    "urgency": "high" if days_until <= 1 else "medium",
                }
                alerts.append(alert)
                logger.warning(
                    f"⚠️ ALERTA: Tarjeta {cycle.card_id[:8]} vence en {days_until} días "
                    f"(₡{cycle.saldo_pendiente:,.0f})"
                )

        # En producción, aquí enviaríamos notificaciones
        # Por ahora solo loggeamos
        if alerts:
            logger.info(f"Generadas {len(alerts)} alertas de vencimiento")

    logger.info("✅ Verificación de alertas completada")


def update_exchange_rate_task() -> None:
    """
    Tarea: Actualizar tipo de cambio USD/CRC.

    Consulta fuente externa y actualiza caché.
    """
    from datetime import date

    logger.info("💱 Actualizando tipo de cambio...")

    try:
        from finanzas_tracker.services.exchange_rate import exchange_rate_service

        rate = exchange_rate_service.get_rate(date.today())
        logger.info(f"Tipo de cambio: ₡{rate}/USD")
    except Exception as e:
        logger.error(f"Error actualizando tipo de cambio: {e}")

    logger.info("✅ Tipo de cambio actualizado")


def process_statement_emails_task() -> None:
    """
    Tarea: Buscar y procesar estados de cuenta de correos.

    Busca correos con PDFs de estados de cuenta BAC,
    los descarga, parsea y guarda en la base de datos.

    Note:
        Esta tarea requiere un profile_id configurado.
        Por ahora solo logguea un warning si no está disponible.
    """
    logger.info("📧 Buscando estados de cuenta por email...")

    try:
        from finanzas_tracker.services.statement_email_service import statement_email_service

        # TODO: Obtener profile_id desde configuración o contexto del scheduler
        # Por ahora, solo buscamos sin guardar en BD
        statements = statement_email_service.fetch_statement_emails(days_back=7)

        if statements:
            logger.info(f"📄 {len(statements)} estados de cuenta encontrados")
            logger.warning(
                "⚠️ Para procesar estados de cuenta automáticamente, "
                "configure profile_id en el scheduler"
            )
        else:
            logger.debug("No hay estados de cuenta nuevos")

    except Exception as e:
        logger.error(f"Error procesando estados de cuenta: {e}")

    logger.info("✅ Verificación de estados de cuenta completada")


# =============================================================================
# Configuración del Scheduler
# =============================================================================


def setup_scheduler() -> SyncScheduler:
    """
    Configura el scheduler con todas las tareas.

    Returns:
        Scheduler configurado
    """
    # Sync emails cada 6 horas
    scheduler.add_task(
        name="sync_emails",
        func=sync_emails_task,
        interval_seconds=6 * 60 * 60,  # 6 horas
        run_immediately=False,
    )

    # Verificar ciclos cada hora
    scheduler.add_task(
        name="check_billing_cycles",
        func=check_billing_cycles_task,
        interval_seconds=60 * 60,  # 1 hora
        run_immediately=True,
    )

    # Alertas de tarjetas cada 6 horas
    scheduler.add_task(
        name="check_card_alerts",
        func=check_card_alerts_task,
        interval_seconds=6 * 60 * 60,  # 6 horas
        run_immediately=True,
    )

    # Tipo de cambio cada 12 horas
    scheduler.add_task(
        name="update_exchange_rate",
        func=update_exchange_rate_task,
        interval_seconds=12 * 60 * 60,  # 12 horas
        run_immediately=True,
    )

    # Procesar estados de cuenta por email cada 4 horas
    scheduler.add_task(
        name="process_statement_emails",
        func=process_statement_emails_task,
        interval_seconds=4 * 60 * 60,  # 4 horas
        run_immediately=False,  # No al inicio, esperar primer intervalo
    )

    return scheduler


def start_background_tasks() -> None:
    """Inicia todas las tareas en background."""
    setup_scheduler()
    scheduler.start()


def stop_background_tasks() -> None:
    """Detiene todas las tareas en background."""
    scheduler.stop()
