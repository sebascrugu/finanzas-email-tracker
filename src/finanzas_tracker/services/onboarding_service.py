"""Servicio de Onboarding Wizard."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.card import Card
from finanzas_tracker.models.enums import BankName, CardType, IncomeType, RecurrenceFrequency
from finanzas_tracker.models.income import Income
from finanzas_tracker.models.onboarding_progress import OnboardingProgress
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.services.card_detection_service import card_detection_service

logger = get_logger(__name__)


class OnboardingService:
    """
    Servicio de Onboarding Wizard.

    Orquesta el flujo completo de configuración inicial del usuario:
    1. Bienvenida
    2. Crear Perfil
    3. Conectar Email (Microsoft Graph)
    4. Reconciliar Estado de Cuenta PDF (opcional pero recomendado)
    5. Auto-detectar Tarjetas
    6. Configurar Ingreso
    7. Primera Importación

    Features:
    - Persistencia de progreso (puede pausar y continuar)
    - Skip automático si ya está configurado
    - Integración con CardDetectionService y PDFReconciliationService
    - Validaciones en cada paso
    """

    def __init__(self) -> None:
        """Inicializa el servicio de onboarding."""
        logger.info("OnboardingService inicializado")

    # ========================================================================
    # GESTIÓN DE PROGRESO
    # ========================================================================

    def get_or_create_progress(self, email: str) -> OnboardingProgress:
        """
        Obtiene o crea el progreso de onboarding para un email.

        Args:
            email: Email del usuario

        Returns:
            OnboardingProgress existente o nuevo
        """
        with get_session() as session:
            # Buscar progreso existente
            stmt = select(OnboardingProgress).where(OnboardingProgress.email == email)
            progress = session.execute(stmt).scalar_one_or_none()

            if progress:
                logger.info(
                    f"Progreso de onboarding encontrado: {email} "
                    f"(paso {progress.current_step}, {progress.progress_percentage:.1f}%)"
                )
                return progress

            # Crear nuevo progreso
            progress = OnboardingProgress(
                id=str(uuid4()),
                email=email,
                current_step=1,
                is_completed=False,
            )

            session.add(progress)
            session.commit()
            session.refresh(progress)

            logger.info(f"✅ Nuevo progreso de onboarding creado para: {email}")
            return progress

    def update_progress(
        self,
        email: str,
        current_step: int | None = None,
        **step_updates: Any,
    ) -> OnboardingProgress:
        """
        Actualiza el progreso del onboarding.

        Args:
            email: Email del usuario
            current_step: Paso actual (1-7)
            **step_updates: Actualizaciones adicionales (profile_id, etc.)

        Returns:
            OnboardingProgress actualizado
        """
        with get_session() as session:
            progress = session.execute(
                select(OnboardingProgress).where(OnboardingProgress.email == email)
            ).scalar_one()

            if current_step is not None:
                progress.current_step = current_step

            # Actualizar campos adicionales
            for key, value in step_updates.items():
                if hasattr(progress, key):
                    setattr(progress, key, value)

            progress.last_activity_at = datetime.now(UTC)

            session.commit()
            session.refresh(progress)

            return progress

    def mark_step_completed(
        self, email: str, step: int, **data: Any
    ) -> OnboardingProgress:
        """
        Marca un paso como completado.

        Args:
            email: Email del usuario
            step: Número de paso (1-7)
            **data: Datos adicionales del paso

        Returns:
            OnboardingProgress actualizado
        """
        with get_session() as session:
            progress = session.execute(
                select(OnboardingProgress).where(OnboardingProgress.email == email)
            ).scalar_one()

            # Marcar paso como completado
            progress.mark_step_completed(step)

            # Avanzar al siguiente paso
            if step < 7:
                progress.current_step = step + 1

            # Actualizar datos adicionales
            for key, value in data.items():
                if hasattr(progress, key):
                    setattr(progress, key, value)

            session.commit()
            session.refresh(progress)

            logger.info(f"✅ Paso {step} completado para {email}")
            return progress

    def should_skip_onboarding(self, email: str) -> tuple[bool, str | None]:
        """
        Determina si debe saltar el onboarding.

        Args:
            email: Email del usuario

        Returns:
            Tuple (should_skip, profile_id)
        """
        with get_session() as session:
            # Buscar progreso completado
            progress = session.execute(
                select(OnboardingProgress).where(OnboardingProgress.email == email)
            ).scalar_one_or_none()

            if progress and progress.can_skip_onboarding:
                logger.info(f"⏭️ Saltando onboarding para {email} (ya completado)")
                return True, progress.profile_id

            # Buscar perfil existente con ese email
            profile = session.execute(
                select(Profile).where(Profile.email_outlook == email)
            ).scalar_one_or_none()

            if profile:
                logger.info(f"⏭️ Saltando onboarding para {email} (perfil existente)")
                return True, profile.id

            return False, None

    # ========================================================================
    # PASO 2: CREAR PERFIL
    # ========================================================================

    def create_profile(
        self,
        email: str,
        nombre: str,
        icono: str | None = None,
        descripcion: str | None = None,
    ) -> Profile:
        """
        Crea un perfil en el paso 2 del onboarding.

        Args:
            email: Email de Outlook
            nombre: Nombre del perfil
            icono: Emoji opcional
            descripcion: Descripción opcional

        Returns:
            Profile creado
        """
        with get_session() as session:
            # Verificar si ya existe
            existing = session.execute(
                select(Profile).where(Profile.email_outlook == email)
            ).scalar_one_or_none()

            if existing:
                logger.info(f"Perfil ya existe para {email}, retornando existente")
                return existing

            # Crear nuevo perfil
            profile = Profile(
                id=str(uuid4()),
                email_outlook=email.lower().strip(),
                nombre=nombre.strip(),
                icono=icono or "👤",
                descripcion=descripcion,
                es_activo=True,
                activo=True,
            )

            session.add(profile)
            session.commit()
            session.refresh(profile)

            # Actualizar progreso con profile_id
            self.mark_step_completed(email, 2, profile_id=profile.id)

            logger.info(f"✅ Perfil creado: {nombre} ({email})")
            return profile

    # ========================================================================
    # PASO 5: AUTO-DETECTAR TARJETAS
    # ========================================================================

    def auto_detect_cards(
        self, email: str, days_back: int = 30
    ) -> list[dict[str, Any]]:
        """
        Auto-detecta tarjetas desde correos.

        Args:
            email: Email de Outlook
            days_back: Días hacia atrás para escanear

        Returns:
            Lista de tarjetas detectadas
        """
        logger.info(f"🔍 Auto-detectando tarjetas para {email}...")

        try:
            detected_cards = card_detection_service.detect_cards_from_emails(
                email_address=email,
                days_back=days_back,
            )

            # Actualizar progreso
            self.update_progress(email, detected_cards_count=len(detected_cards))

            logger.info(f"✅ {len(detected_cards)} tarjeta(s) detectada(s)")
            return detected_cards

        except Exception as e:
            logger.error(f"Error al detectar tarjetas: {e}", exc_info=True)
            return []

    def create_cards_from_detected(
        self,
        email: str,
        profile_id: str,
        selected_cards: list[dict[str, Any]],
    ) -> list[Card]:
        """
        Crea tarjetas desde las detectadas.

        Args:
            email: Email del usuario
            profile_id: ID del perfil
            selected_cards: Lista de tarjetas seleccionadas/confirmadas por el usuario
                Format: [{"last_digits": "1234", "banco": BankName.BAC,
                         "tipo": CardType.DEBIT, "etiqueta": "Personal"}]

        Returns:
            Lista de tarjetas creadas
        """
        created_cards = []

        with get_session() as session:
            for card_data in selected_cards:
                # Verificar si ya existe
                existing = (
                    session.query(Card)
                    .filter(
                        Card.profile_id == profile_id,
                        Card.banco == card_data["banco"],
                        Card.ultimos_digitos == card_data["last_digits"],
                    )
                    .first()
                )

                if existing:
                    logger.info(
                        f"Tarjeta ya existe: {card_data['banco'].value} "
                        f"{card_data['last_digits']}"
                    )
                    created_cards.append(existing)
                    continue

                # Crear nueva tarjeta
                card = Card(
                    profile_id=profile_id,
                    banco=card_data["banco"],
                    tipo=card_data.get("tipo", CardType.DEBIT),
                    ultimos_digitos=card_data["last_digits"],
                    etiqueta=card_data.get("etiqueta"),
                    activa=True,
                )

                session.add(card)
                created_cards.append(card)

                logger.info(
                    f"✅ Tarjeta creada: {card.banco.value} {card.ultimos_digitos}"
                )

            session.commit()

            # Marcar paso 5 completado
            self.mark_step_completed(email, 5)

        return created_cards

    # ========================================================================
    # PASO 6: CONFIGURAR INGRESO
    # ========================================================================

    def create_initial_income(
        self,
        email: str,
        profile_id: str,
        monto: Decimal,
        frecuencia: RecurrenceFrequency = RecurrenceFrequency.MONTHLY,
        nombre: str = "Salario",
        tipo: IncomeType = IncomeType.SALARY,
    ) -> Income:
        """
        Crea el ingreso inicial en el paso 6.

        Args:
            email: Email del usuario
            profile_id: ID del perfil
            monto: Monto del ingreso
            frecuencia: Frecuencia (mensual, quincenal, etc.)
            nombre: Nombre del ingreso
            tipo: Tipo de ingreso

        Returns:
            Income creado
        """
        with get_session() as session:
            income = Income(
                id=str(uuid4()),
                profile_id=profile_id,
                nombre=nombre,
                monto_crc=monto,
                tipo_ingreso=tipo,
                es_recurrente=True,
                frecuencia=frecuencia,
                fecha_inicio=datetime.now(UTC).date(),
                activo=True,
            )

            session.add(income)
            session.commit()
            session.refresh(income)

            # Marcar paso 6 completado
            self.mark_step_completed(email, 6)

            logger.info(
                f"✅ Ingreso inicial creado: {nombre} - ₡{monto:,.0f} ({frecuencia.value})"
            )
            return income

    # ========================================================================
    # PASO 7: PRIMERA IMPORTACIÓN
    # ========================================================================

    def complete_onboarding(
        self, email: str, imported_count: int | None = None
    ) -> OnboardingProgress:
        """
        Completa el onboarding.

        Args:
            email: Email del usuario
            imported_count: Número de transacciones importadas

        Returns:
            OnboardingProgress finalizado
        """
        with get_session() as session:
            progress = session.execute(
                select(OnboardingProgress).where(OnboardingProgress.email == email)
            ).scalar_one()

            # Marcar como completado
            progress.is_completed = True
            progress.completed_at = datetime.now(UTC)
            progress.current_step = 7
            progress.mark_step_completed(7)

            if imported_count is not None:
                progress.imported_transactions_count = imported_count

            session.commit()
            session.refresh(progress)

            logger.info(f"🎉 Onboarding completado para {email}!")
            return progress

    # ========================================================================
    # PASO 3.5: PDF RECONCILIATION
    # ========================================================================

    def update_pdf_reconciliation_progress(
        self,
        email: str,
        bank_statement_id: str,
        reconciliation_summary: dict[str, Any],
        transactions_added: int,
    ) -> OnboardingProgress:
        """
        Actualiza el progreso con datos de reconciliación PDF.

        Args:
            email: Email del usuario
            bank_statement_id: ID del BankStatement creado
            reconciliation_summary: Resumen de la reconciliación
            transactions_added: Número de transacciones agregadas

        Returns:
            OnboardingProgress actualizado
        """
        with get_session() as session:
            progress = session.execute(
                select(OnboardingProgress).where(OnboardingProgress.email == email)
            ).scalar_one()

            # Actualizar campos de PDF reconciliation
            progress.bank_statement_uploaded = True
            progress.bank_statement_id = bank_statement_id
            progress.reconciliation_completed = True
            progress.reconciliation_summary = reconciliation_summary
            progress.transactions_added_from_pdf = transactions_added
            progress.last_activity_at = datetime.now(UTC)

            session.commit()
            session.refresh(progress)

            logger.info(
                f"✅ PDF reconciliation actualizado para {email}: "
                f"{transactions_added} transacciones agregadas"
            )
            return progress

    # ========================================================================
    # UTILIDADES
    # ========================================================================

    def reset_onboarding(self, email: str) -> None:
        """
        Resetea el onboarding (para testing o re-configuración).

        Args:
            email: Email del usuario
        """
        with get_session() as session:
            progress = session.execute(
                select(OnboardingProgress).where(OnboardingProgress.email == email)
            ).scalar_one_or_none()

            if progress:
                session.delete(progress)
                session.commit()
                logger.info(f"🔄 Onboarding reseteado para {email}")


# Singleton instance
onboarding_service = OnboardingService()
