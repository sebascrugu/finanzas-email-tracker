"""
Estrategia de sincronización inteligente de transacciones.

Inspirado en Plaid, Mint, Stripe - Nivel FAANG.

Flujo:
1. Onboarding: PDF más reciente + GAP de correos
2. Daily: Correos incrementales hasta próximo estado
3. Monthly: Nuevo PDF + GAP filling

Autor: Sebastian Cruz
Versión: 1.0.0
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, UTC
from decimal import Decimal
from typing import Literal

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.services.statement_email_service import StatementEmailService
from finanzas_tracker.services.email_fetcher import EmailFetcher
from finanzas_tracker.services.transaction_processor import TransactionProcessor


logger = get_logger(__name__)


SyncMode = Literal["onboarding", "daily", "monthly"]


@dataclass
class SyncResult:
    """Resultado de una sincronización."""

    success: bool
    mode: SyncMode
    pdf_transactions: int = 0
    email_transactions: int = 0
    total_transactions: int = 0
    next_sync_date: date | None = None
    next_statement_expected: date | None = None
    errors: list[str] | None = None


class SyncStrategy:
    """
    Estrategia inteligente de sincronización de transacciones.

    Características:
    - Gap filling automático
    - Detección de ciclo de estado de cuenta
    - Sincronización incremental
    - Optimización de llamadas a APIs
    """

    def __init__(self, profile_id: str) -> None:
        """Inicializa la estrategia para un perfil."""
        self.profile_id = profile_id
        self.statement_service = StatementEmailService()
        self.email_fetcher = EmailFetcher()
        self.processor = TransactionProcessor(auto_categorize=True)

        # Estado del perfil
        with get_session() as session:
            profile = session.get(Profile, profile_id)
            if not profile:
                raise ValueError(f"Profile {profile_id} not found")

            self.last_statement_date = profile.last_statement_date
            self.statement_cycle_days = profile.statement_cycle_days or 30
            self.last_sync_date = profile.last_sync_date

    def onboarding_sync(self) -> SyncResult:
        """
        Sincronización inicial inteligente en onboarding.

        Flujo:
        1. Buscar PDFs de últimos 90 días (3 ciclos)
        2. Procesar el MÁS RECIENTE
        3. Detectar ciclo de estado de cuenta
        4. Buscar correos para llenar GAP hasta HOY
        5. Guardar metadata de sync

        Returns:
            SyncResult con estadísticas
        """
        logger.info(f"🚀 Iniciando onboarding sync para profile {self.profile_id}")
        errors = []
        pdf_count = 0
        email_count = 0

        try:
            # 1. Buscar PDFs (último mes)
            logger.info("📄 Buscando estados de cuenta...")
            statements = self.statement_service.fetch_statement_emails(days_back=31)

            if statements:
                logger.info(f"✅ Encontrados {len(statements)} estados de cuenta")

                # 2. Procesar el más reciente
                latest = statements[0]
                logger.info(
                    f"📊 Procesando estado más reciente: {latest.received_date.strftime('%d/%m/%Y')}"
                )

                result = self.statement_service.process_statement(
                    latest,
                    profile_id=self.profile_id,
                    save_to_db=True,
                )

                if result.error:
                    errors.append(f"Error procesando PDF: {result.error}")
                else:
                    pdf_count = result.transactions_created
                    # Extraer fecha del statement_result.metadata
                    statement_date = (
                        result.statement_result.metadata.fecha_corte
                        if result.statement_result and result.statement_result.metadata
                        else date.today()
                    )

                    # 3. Detectar ciclo si hay múltiples estados
                    if len(statements) > 1:
                        prev_date = statements[1].received_date.date()
                        cycle = (latest.received_date.date() - prev_date).days
                        self.statement_cycle_days = cycle
                        logger.info(f"📅 Ciclo detectado: {cycle} días")

                    # 4. Gap filling: desde (fecha_corte - 5 días) hasta HOY
                    # El PDF tiene transacciones hasta fecha_corte
                    # Los correos cubren desde (fecha_corte - 5) para traslape
                    gap_start = statement_date - timedelta(days=5)
                    gap_end = date.today()

                    logger.info(
                        f"🔍 Buscando correos para llenar GAP: {gap_start} → {gap_end}"
                    )

                    emails = self._fetch_emails_in_range(gap_start, gap_end)

                    if emails:
                        logger.info(f"📬 Procesando {len(emails)} correos del GAP")
                        stats = self.processor.process_emails(emails, self.profile_id)
                        email_count = stats.get("procesados", 0)

                    # 5. Guardar metadata
                    self._update_sync_metadata(
                        last_statement_date=statement_date,
                        last_sync_date=date.today(),
                        statement_cycle_days=self.statement_cycle_days,
                    )

            else:
                # Fallback: solo correos si no hay PDFs
                # Buscar desde el 1er día del mes anterior hasta hoy
                # Ej: Hoy 7 Dic → buscar desde 1 Nov
                # Ej: Hoy 24 Sep → buscar desde 1 Ago
                hoy = date.today()
                if hoy.month == 1:
                    # Enero → buscar desde 1 Diciembre año anterior
                    primer_dia_mes_anterior = date(hoy.year - 1, 12, 1)
                else:
                    primer_dia_mes_anterior = date(hoy.year, hoy.month - 1, 1)
                
                dias_atras = (hoy - primer_dia_mes_anterior).days
                logger.warning(
                    f"📭 No se encontraron PDFs. Fallback: correos desde {primer_dia_mes_anterior.strftime('%d/%m/%Y')} ({dias_atras} días)"
                )
                
                emails = self.email_fetcher.fetch_all_emails(days_back=dias_atras)

                if emails:
                    logger.info(f"📬 Procesando {len(emails)} correos")
                    stats = self.processor.process_emails(emails, self.profile_id)
                    email_count = stats.get("procesados", 0)

                self._update_sync_metadata(
                    last_sync_date=date.today(),
                    statement_cycle_days=30,  # Asumir 30 días
                )

            # Calcular próximo estado esperado
            next_statement = None
            if self.last_statement_date:
                next_statement = self.last_statement_date + timedelta(
                    days=self.statement_cycle_days
                )

            logger.success(
                f"✅ Onboarding completado: {pdf_count} PDF + {email_count} correos"
            )

            return SyncResult(
                success=True,
                mode="onboarding",
                pdf_transactions=pdf_count,
                email_transactions=email_count,
                total_transactions=pdf_count + email_count,
                next_sync_date=date.today() + timedelta(days=1),
                next_statement_expected=next_statement,
                errors=errors if errors else None,
            )

        except Exception as e:
            logger.error(f"❌ Error en onboarding sync: {e}")
            return SyncResult(
                success=False,
                mode="onboarding",
                errors=[str(e)],
            )

    def daily_sync(self) -> SyncResult:
        """
        Sincronización diaria incremental.

        Lógica:
        - Si estamos ANTES del next_statement_date:
          → Buscar correos desde last_sync hasta HOY (incremental)

        - Si estamos DESPUÉS del next_statement_date:
          → Buscar nuevo PDF
          → Gap filling si es necesario

        Returns:
            SyncResult con estadísticas
        """
        logger.info(f"📅 Iniciando daily sync para profile {self.profile_id}")
        today = date.today()

        # Calcular fecha esperada del próximo estado
        next_statement = None
        if self.last_statement_date:
            next_statement = self.last_statement_date + timedelta(
                days=self.statement_cycle_days
            )

        # ¿Esperamos un nuevo estado de cuenta?
        if next_statement and today >= next_statement:
            logger.info("📄 Es momento de buscar nuevo estado de cuenta")
            return self._monthly_sync()

        # Sync incremental: solo correos desde última vez
        try:
            since_date = self.last_sync_date or (today - timedelta(days=1))
            logger.info(f"📬 Buscando correos desde {since_date}")

            emails = self._fetch_emails_in_range(since_date, today)

            email_count = 0
            if emails:
                logger.info(f"📬 Procesando {len(emails)} correos nuevos")
                stats = self.processor.process_emails(emails, self.profile_id)
                email_count = stats.get("procesados", 0)

            # Actualizar last_sync_date
            self._update_sync_metadata(last_sync_date=today)

            logger.success(f"✅ Daily sync completado: {email_count} transacciones")

            return SyncResult(
                success=True,
                mode="daily",
                email_transactions=email_count,
                total_transactions=email_count,
                next_sync_date=today + timedelta(days=1),
                next_statement_expected=next_statement,
            )

        except Exception as e:
            logger.error(f"❌ Error en daily sync: {e}")
            return SyncResult(
                success=False,
                mode="daily",
                errors=[str(e)],
            )

    def _monthly_sync(self) -> SyncResult:
        """
        Sincronización mensual cuando se espera nuevo estado de cuenta.

        Similar a onboarding pero más optimizado.
        """
        logger.info("📊 Iniciando monthly sync (nuevo estado de cuenta)")
        errors = []
        pdf_count = 0
        email_count = 0

        try:
            # Buscar nuevo estado (solo últimos 10 días)
            statements = self.statement_service.fetch_statement_emails(days_back=10)

            if statements:
                latest = statements[0]
                latest_date = latest.received_date.date()

                # Solo procesar si es más reciente que el anterior
                if (
                    not self.last_statement_date
                    or latest_date > self.last_statement_date
                ):
                    logger.info(f"🆕 Nuevo estado encontrado: {latest_date}")

                    result = self.statement_service.process_statement(
                        latest,
                        profile_id=self.profile_id,
                        save_to_db=True,
                    )

                    if not result.error:
                        pdf_count = result.transactions_created
                        # Extraer fecha del statement_result.metadata
                        statement_date = (
                            result.statement_result.metadata.fecha_corte
                            if result.statement_result and result.statement_result.metadata
                            else date.today()
                        )

                        # Gap filling desde último estado hasta nuevo estado
                        gap_start = self.last_statement_date or (
                            statement_date - timedelta(days=7)
                        )
                        gap_end = date.today()

                        logger.info(f"🔍 Gap filling: {gap_start} → {gap_end}")
                        emails = self._fetch_emails_in_range(gap_start, gap_end)

                        if emails:
                            stats = self.processor.process_emails(
                                emails, self.profile_id
                            )
                            email_count = stats.get("procesados", 0)

                        # Actualizar metadata
                        self._update_sync_metadata(
                            last_statement_date=statement_date,
                            last_sync_date=date.today(),
                        )

            # Si no hay nuevo PDF, hacer sync de correos normal
            else:
                logger.warning("📭 No se encontró nuevo estado. Sync de correos...")
                return self.daily_sync()

            next_statement = self.last_statement_date + timedelta(
                days=self.statement_cycle_days
            )

            logger.success(
                f"✅ Monthly sync completado: {pdf_count} PDF + {email_count} correos"
            )

            return SyncResult(
                success=True,
                mode="monthly",
                pdf_transactions=pdf_count,
                email_transactions=email_count,
                total_transactions=pdf_count + email_count,
                next_sync_date=date.today() + timedelta(days=1),
                next_statement_expected=next_statement,
                errors=errors if errors else None,
            )

        except Exception as e:
            logger.error(f"❌ Error en monthly sync: {e}")
            return SyncResult(
                success=False,
                mode="monthly",
                errors=[str(e)],
            )

    def _fetch_emails_in_range(
        self,
        start_date: date,
        end_date: date,
    ) -> list:
        """
        Busca correos en un rango de fechas específico.

        Args:
            start_date: Fecha inicial
            end_date: Fecha final

        Returns:
            Lista de correos encontrados
        """
        # Calcular días desde start_date hasta hoy
        days_back = (date.today() - start_date).days + 1

        # Fetch y filtrar por rango
        all_emails = self.email_fetcher.fetch_all_emails(days_back=days_back)

        # Filtrar por rango exacto
        # Los emails son dicts con 'receivedDateTime' como string ISO
        from datetime import datetime
        
        def get_email_date(email: dict) -> date:
            """Extrae fecha del email (dict de Microsoft Graph)."""
            received = email.get("receivedDateTime", "")
            if received:
                try:
                    return datetime.fromisoformat(received.replace("Z", "+00:00")).date()
                except (ValueError, AttributeError):
                    pass
            return date.today()
        
        filtered = [
            email
            for email in all_emails
            if start_date <= get_email_date(email) <= end_date
        ]

        logger.info(
            f"📬 Filtrados {len(filtered)}/{len(all_emails)} correos en rango {start_date} → {end_date}"
        )

        return filtered

    def _update_sync_metadata(
        self,
        last_statement_date: date | None = None,
        last_sync_date: date | None = None,
        statement_cycle_days: int | None = None,
    ) -> None:
        """Actualiza metadata de sincronización en el perfil."""
        with get_session() as session:
            profile = session.get(Profile, self.profile_id)
            if not profile:
                return

            if last_statement_date:
                profile.last_statement_date = last_statement_date
                self.last_statement_date = last_statement_date

            if last_sync_date:
                profile.last_sync_date = last_sync_date
                self.last_sync_date = last_sync_date

            if statement_cycle_days:
                profile.statement_cycle_days = statement_cycle_days
                self.statement_cycle_days = statement_cycle_days

            profile.updated_at = datetime.now(UTC)
            session.commit()

            logger.debug(f"💾 Metadata actualizada para profile {self.profile_id}")


# Singleton-like factory
def get_sync_strategy(profile_id: str) -> SyncStrategy:
    """Factory para obtener estrategia de sync."""
    return SyncStrategy(profile_id)


__all__ = ["SyncStrategy", "SyncResult", "get_sync_strategy"]
