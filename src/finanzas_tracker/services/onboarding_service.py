"""
Servicio de Onboarding para nuevos usuarios.

Maneja el flujo de configuración inicial:
1. Registro de usuario
2. Subida de PDF (estado de cuenta)
3. Detección automática de cuentas/tarjetas
4. Confirmación y ajustes del usuario
5. Creación de presupuesto inicial
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.models import (
    Account,
    BillingCycle,
    Card,
    Profile,
    User,
)
from finanzas_tracker.models.enums import (
    AccountType,
    BankName,
    BillingCycleStatus,
    CardType,
    Currency,
)

logger = logging.getLogger(__name__)


class OnboardingStep(str, Enum):
    """Pasos del onboarding."""

    REGISTERED = "registered"  # Usuario creado
    PDF_UPLOADED = "pdf_uploaded"  # PDF procesado
    ACCOUNTS_CONFIRMED = "accounts_confirmed"  # Cuentas confirmadas
    CARDS_CONFIRMED = "cards_confirmed"  # Tarjetas confirmadas
    BUDGET_SET = "budget_set"  # Presupuesto configurado
    COMPLETED = "completed"  # Onboarding completo


@dataclass
class DetectedAccount:
    """Cuenta detectada del PDF."""

    numero_cuenta: str  # últimos 4 dígitos
    tipo: AccountType
    banco: BankName
    saldo: Decimal
    moneda: Currency = Currency.CRC
    nombre_sugerido: str = ""

    def to_dict(self) -> dict:
        """Convierte a diccionario para JSON."""
        return {
            "numero_cuenta": self.numero_cuenta,
            "tipo": self.tipo.value,
            "banco": self.banco.value,
            "saldo": float(self.saldo),
            "moneda": self.moneda.value,
            "nombre_sugerido": self.nombre_sugerido,
        }


@dataclass
class DetectedCard:
    """Tarjeta detectada del PDF."""

    ultimos_4_digitos: str
    marca: str | None  # VISA, Mastercard
    banco: BankName
    tipo_sugerido: CardType | None = None  # Si podemos inferir
    limite_credito: Decimal | None = None
    saldo_actual: Decimal | None = None
    fecha_corte: int | None = None  # día del mes
    fecha_pago: int | None = None  # día del mes

    def to_dict(self) -> dict:
        """Convierte a diccionario para JSON."""
        return {
            "ultimos_4_digitos": self.ultimos_4_digitos,
            "marca": self.marca,
            "banco": self.banco.value,
            "tipo_sugerido": self.tipo_sugerido.value if self.tipo_sugerido else None,
            "limite_credito": float(self.limite_credito) if self.limite_credito else None,
            "saldo_actual": float(self.saldo_actual) if self.saldo_actual else None,
            "fecha_corte": self.fecha_corte,
            "fecha_pago": self.fecha_pago,
        }


@dataclass
class OnboardingState:
    """Estado actual del onboarding de un usuario."""

    user_id: str
    profile_id: str | None = None
    current_step: OnboardingStep = OnboardingStep.REGISTERED
    detected_accounts: list[DetectedAccount] = field(default_factory=list)
    detected_cards: list[DetectedCard] = field(default_factory=list)
    pdf_processed: bool = False
    email_connected: bool = False
    transactions_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convierte a diccionario para JSON/API."""
        return {
            "user_id": self.user_id,
            "profile_id": self.profile_id,
            "current_step": self.current_step.value,
            "detected_accounts": [a.to_dict() for a in self.detected_accounts],
            "detected_cards": [c.to_dict() for c in self.detected_cards],
            "pdf_processed": self.pdf_processed,
            "email_connected": self.email_connected,
            "transactions_count": self.transactions_count,
            "progress_percent": self._calculate_progress(),
        }

    def _calculate_progress(self) -> int:
        """Calcula porcentaje de progreso."""
        steps = list(OnboardingStep)
        current_index = steps.index(self.current_step)
        return int((current_index / (len(steps) - 1)) * 100)


class OnboardingService:
    """
    Servicio para manejar el flujo de onboarding.

    Coordina:
    - Procesamiento de PDF para detectar cuentas/tarjetas
    - Creación de entidades confirmadas por el usuario
    - Estado del progreso de onboarding
    """

    def __init__(self, db: Session) -> None:
        """Inicializa el servicio."""
        self.db = db
        # Cache temporal de estados de onboarding (en producción usar Redis)
        self._states: dict[str, OnboardingState] = {}

    # =========================================================================
    # Estado del Onboarding
    # =========================================================================

    def start_onboarding(self, user_id: str) -> OnboardingState:
        """
        Inicia el proceso de onboarding para un usuario.

        Args:
            user_id: ID del usuario registrado

        Returns:
            Estado inicial del onboarding
        """
        state = OnboardingState(user_id=user_id)
        self._states[user_id] = state
        logger.info(f"Onboarding iniciado para usuario {user_id[:8]}...")
        return state

    def get_state(self, user_id: str) -> OnboardingState | None:
        """Obtiene el estado actual del onboarding."""
        return self._states.get(user_id)

    def update_step(self, user_id: str, step: OnboardingStep) -> OnboardingState | None:
        """Actualiza el paso actual del onboarding."""
        state = self._states.get(user_id)
        if state:
            state.current_step = step
            logger.info(f"Onboarding {user_id[:8]}... → {step.value}")
        return state

    # =========================================================================
    # Procesamiento de PDF
    # =========================================================================

    def process_pdf(
        self,
        user_id: str,
        pdf_content: bytes,
        banco: BankName = BankName.BAC,
    ) -> OnboardingState:
        """
        Procesa un PDF de estado de cuenta y extrae cuentas/tarjetas.

        Args:
            user_id: ID del usuario
            pdf_content: Contenido del PDF en bytes
            banco: Banco del estado de cuenta

        Returns:
            Estado actualizado con detecciones
        """
        state = self._states.get(user_id)
        if not state:
            state = self.start_onboarding(user_id)

        # Importar parser
        from finanzas_tracker.parsers.bac_pdf_parser import BACPDFParser

        if banco == BankName.BAC:
            parser = BACPDFParser()
            result = parser.parse_from_bytes(pdf_content)

            if result:
                # Extraer cuentas detectadas
                state.detected_accounts = self._extract_accounts_from_pdf(result, banco)

                # Extraer tarjetas detectadas
                state.detected_cards = self._extract_cards_from_pdf(result, banco)

                # Contar transacciones
                state.transactions_count = len(result.get("transactions", []))

                state.pdf_processed = True
                state.current_step = OnboardingStep.PDF_UPLOADED

                logger.info(
                    f"PDF procesado: {len(state.detected_accounts)} cuentas, "
                    f"{len(state.detected_cards)} tarjetas, "
                    f"{state.transactions_count} transacciones"
                )

                # Guardar transacciones en el estado para importación posterior
                state._pdf_transactions = result.get("transactions", [])
        else:
            logger.warning(f"Parser para {banco} no implementado en onboarding")

        return state

    def import_transactions_from_pdf(
        self,
        user_id: str,
        profile_id: str,
        fecha_base: date,
        importar_historicas: bool = True,
    ) -> dict:
        """
        Importa transacciones del PDF procesado.

        Las transacciones anteriores a fecha_base se marcan como históricas
        y no afectan el cálculo de patrimonio.

        Args:
            user_id: ID del usuario
            profile_id: ID del perfil
            fecha_base: Fecha límite para marcar como históricas
            importar_historicas: Si importar transacciones anteriores a fecha_base

        Returns:
            Diccionario con estadísticas de importación
        """
        from finanzas_tracker.models.transaction import Transaction
        from finanzas_tracker.models.enums import TransactionStatus
        from finanzas_tracker.services.internal_transfer_detector import InternalTransferDetector

        state = self._states.get(user_id)
        if not state or not hasattr(state, '_pdf_transactions'):
            return {"error": "No hay PDF procesado para este usuario"}

        transactions = state._pdf_transactions
        stats = {
            "total": len(transactions),
            "importadas": 0,
            "historicas": 0,
            "recientes": 0,
            "duplicadas": 0,
            "transferencias_internas": 0,
        }

        transfer_detector = InternalTransferDetector(self.db)

        for tx_data in transactions:
            fecha_tx = tx_data.get("fecha")
            if isinstance(fecha_tx, str):
                fecha_tx = datetime.strptime(fecha_tx, "%Y-%m-%d").date()

            es_historica = fecha_tx < fecha_base

            if es_historica and not importar_historicas:
                continue

            try:
                # Crear transacción
                transaction = Transaction(
                    profile_id=profile_id,
                    email_id=f"pdf_import_{user_id}_{tx_data.get('referencia', '')}_{fecha_tx}",
                    banco=tx_data.get("banco", "bac"),
                    comercio=tx_data.get("comercio", tx_data.get("descripcion", "")),
                    tipo_transaccion=tx_data.get("tipo", "compra"),
                    monto_original=Decimal(str(tx_data.get("monto", 0))),
                    monto_crc=Decimal(str(tx_data.get("monto_crc", tx_data.get("monto", 0)))),
                    moneda=tx_data.get("moneda", "CRC"),
                    fecha_transaccion=fecha_tx,
                    es_historica=es_historica,
                    estado=TransactionStatus.CONFIRMED.value if es_historica else TransactionStatus.PENDING.value,
                    referencia_banco=tx_data.get("referencia"),
                )

                self.db.add(transaction)
                self.db.flush()  # Para obtener el ID

                # Detectar transferencias internas
                if transfer_detector.es_transferencia_interna(transaction):
                    transfer_detector.procesar_pago_tarjeta(transaction, profile_id)
                    stats["transferencias_internas"] += 1

                stats["importadas"] += 1
                if es_historica:
                    stats["historicas"] += 1
                else:
                    stats["recientes"] += 1

            except Exception as e:
                if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                    stats["duplicadas"] += 1
                else:
                    logger.error(f"Error importando transacción: {e}")

        self.db.commit()

        logger.info(
            f"Importación completada: {stats['importadas']} transacciones "
            f"({stats['historicas']} históricas, {stats['recientes']} recientes)"
        )

        return stats

    def _extract_accounts_from_pdf(
        self,
        pdf_data: dict,
        banco: BankName,
    ) -> list[DetectedAccount]:
        """Extrae cuentas del resultado del parser."""
        accounts = []

        # Buscar en la sección de cuentas del PDF
        # El parser de BAC retorna info de cuenta en el header
        account_info = pdf_data.get("account_info", {})

        if account_info:
            # Cuenta principal del estado
            numero = account_info.get("account_number", "")[-4:] if account_info.get("account_number") else ""
            if numero:
                accounts.append(DetectedAccount(
                    numero_cuenta=numero,
                    tipo=AccountType.CHECKING,  # Asumir corriente por defecto
                    banco=banco,
                    saldo=Decimal(str(account_info.get("balance", 0))),
                    nombre_sugerido=f"Cuenta {banco.value.upper()} ***{numero}",
                ))

        # También buscar en transacciones si hay referencias a otras cuentas
        # TODO: Implementar detección más sofisticada

        return accounts

    def _extract_cards_from_pdf(
        self,
        pdf_data: dict,
        banco: BankName,
    ) -> list[DetectedCard]:
        """Extrae tarjetas del resultado del parser."""
        cards = []
        seen_cards: set[str] = set()

        # Buscar tarjetas en las transacciones
        transactions = pdf_data.get("transactions", [])

        for tx in transactions:
            # El parser guarda últimos 4 dígitos
            card_digits = tx.get("ultimos_4_digitos") or tx.get("card_last_4")
            if card_digits and card_digits not in seen_cards:
                seen_cards.add(card_digits)

                # Intentar inferir tipo de tarjeta
                # Si hay cargo de intereses, probablemente es crédito
                tx_type = tx.get("tipo", "")
                es_credito = tx_type in ["interes_cobrado", "pago_servicio"]

                cards.append(DetectedCard(
                    ultimos_4_digitos=card_digits,
                    marca=None,  # El parser no siempre lo tiene
                    banco=banco,
                    tipo_sugerido=CardType.CREDIT if es_credito else None,
                ))

        # También buscar en info del estado de cuenta
        card_info = pdf_data.get("card_info", {})
        if card_info:
            card_number = card_info.get("card_number", "")[-4:]
            if card_number and card_number not in seen_cards:
                cards.append(DetectedCard(
                    ultimos_4_digitos=card_number,
                    marca=card_info.get("brand"),
                    banco=banco,
                    tipo_sugerido=CardType.CREDIT,
                    limite_credito=Decimal(str(card_info.get("credit_limit", 0))) if card_info.get("credit_limit") else None,
                    saldo_actual=Decimal(str(card_info.get("balance", 0))) if card_info.get("balance") else None,
                    fecha_corte=card_info.get("cut_day"),
                    fecha_pago=card_info.get("due_day"),
                ))

        return cards

    # =========================================================================
    # Confirmación de Cuentas
    # =========================================================================

    def confirm_accounts(
        self,
        user_id: str,
        profile_id: str,
        confirmed_accounts: list[dict],
    ) -> list[Account]:
        """
        Crea las cuentas confirmadas por el usuario.

        Args:
            user_id: ID del usuario
            profile_id: ID del perfil
            confirmed_accounts: Lista de cuentas con datos confirmados/editados

        Returns:
            Lista de cuentas creadas
        """
        state = self._states.get(user_id)
        if not state:
            raise ValueError("No hay onboarding activo para este usuario")

        state.profile_id = profile_id
        created = []

        for acc_data in confirmed_accounts:
            account = Account(
                profile_id=profile_id,
                nombre=acc_data.get("nombre", f"Cuenta ***{acc_data['numero_cuenta']}"),
                banco=BankName(acc_data["banco"]),
                tipo=AccountType(acc_data["tipo"]),
                numero_cuenta=acc_data["numero_cuenta"],
                saldo=Decimal(str(acc_data["saldo"])),
                moneda=Currency(acc_data.get("moneda", "CRC")),
                es_cuenta_principal=acc_data.get("es_principal", False),
                incluir_en_patrimonio=True,
            )
            self.db.add(account)
            created.append(account)

        self.db.commit()
        for acc in created:
            self.db.refresh(acc)

        state.current_step = OnboardingStep.ACCOUNTS_CONFIRMED
        logger.info(f"Confirmadas {len(created)} cuentas para {user_id[:8]}...")

        return created

    # =========================================================================
    # Confirmación de Tarjetas
    # =========================================================================

    def confirm_cards(
        self,
        user_id: str,
        profile_id: str,
        confirmed_cards: list[dict],
    ) -> list[Card]:
        """
        Crea las tarjetas confirmadas por el usuario.

        Args:
            user_id: ID del usuario
            profile_id: ID del perfil
            confirmed_cards: Lista de tarjetas con datos confirmados/editados

        Returns:
            Lista de tarjetas creadas
        """
        state = self._states.get(user_id)
        if not state:
            raise ValueError("No hay onboarding activo para este usuario")

        created = []

        for card_data in confirmed_cards:
            card = Card(
                profile_id=profile_id,
                ultimos_4_digitos=card_data["ultimos_4_digitos"],
                tipo=CardType(card_data["tipo"]),
                banco=BankName(card_data["banco"]),
                marca=card_data.get("marca"),
                limite_credito=Decimal(str(card_data["limite_credito"])) if card_data.get("limite_credito") else None,
                fecha_corte=card_data.get("fecha_corte"),
                fecha_vencimiento=card_data.get("fecha_pago"),
                current_balance=Decimal(str(card_data.get("saldo_actual", 0))),
                interest_rate_annual=Decimal(str(card_data.get("tasa_interes", 52))),  # Default BAC
                minimum_payment_percentage=Decimal("10"),  # 10% típico
            )
            self.db.add(card)
            created.append(card)

        self.db.commit()

        # Crear ciclo de facturación inicial para tarjetas de crédito
        for card in created:
            self.db.refresh(card)
            if card.es_credito and card.fecha_corte:
                self._create_initial_billing_cycle(card)

        state.current_step = OnboardingStep.CARDS_CONFIRMED
        logger.info(f"Confirmadas {len(created)} tarjetas para {user_id[:8]}...")

        return created

    def _create_initial_billing_cycle(self, card: Card) -> BillingCycle | None:
        """Crea el ciclo de facturación inicial para una tarjeta."""
        from finanzas_tracker.services.card_service import CardService

        card_service = CardService(self.db)
        return card_service.create_next_cycle_for_card(card)

    # =========================================================================
    # Finalización
    # =========================================================================

    def complete_onboarding(
        self,
        user_id: str,
        fecha_base: date | None = None,
    ) -> OnboardingState | None:
        """
        Marca el onboarding como completado y establece patrimonio inicial.

        Args:
            user_id: ID del usuario
            fecha_base: Fecha base para el patrimonio (default: hoy)

        Returns:
            Estado final del onboarding
        """
        state = self._states.get(user_id)
        if not state or not state.profile_id:
            return state

        # Establecer patrimonio inicial usando PatrimonyService
        self._establecer_patrimonio_inicial(state.profile_id, fecha_base)

        state.current_step = OnboardingStep.COMPLETED
        logger.info(f"Onboarding completado para {user_id[:8]}...")
        return state

    def _establecer_patrimonio_inicial(
        self,
        profile_id: str,
        fecha_base: date | None = None,
    ) -> None:
        """
        Calcula y guarda el patrimonio inicial del usuario.

        Usa las cuentas y tarjetas confirmadas para calcular:
        - Total activos (saldos de cuentas)
        - Total deudas (saldos de tarjetas de crédito)
        - Patrimonio neto

        Args:
            profile_id: ID del perfil
            fecha_base: Fecha del snapshot inicial
        """
        from finanzas_tracker.services.patrimony_service import PatrimonyService

        patrimony_service = PatrimonyService(self.db)

        # Obtener cuentas
        accounts = self.db.execute(
            select(Account).where(
                Account.profile_id == profile_id,
                Account.deleted_at.is_(None),
                Account.incluir_en_patrimonio.is_(True),
            )
        ).scalars().all()

        # Obtener tarjetas de crédito con saldo
        cards = self.db.execute(
            select(Card).where(
                Card.profile_id == profile_id,
                Card.deleted_at.is_(None),
                Card.tipo == CardType.CREDIT,
            )
        ).scalars().all()

        # Preparar datos para el servicio de patrimonio
        saldos_cuentas = [
            {
                "cuenta_id": acc.id,
                "nombre": acc.nombre,
                "saldo": acc.saldo,
                "moneda": acc.moneda.value if hasattr(acc.moneda, 'value') else acc.moneda,
            }
            for acc in accounts
        ]

        deudas_tarjetas = [
            {
                "tarjeta_id": card.id,
                "ultimos_4": card.ultimos_4_digitos,
                "saldo": card.current_balance or Decimal("0"),
            }
            for card in cards
            if card.current_balance and card.current_balance > 0
        ]

        # Crear snapshot inicial
        snapshot = patrimony_service.establecer_patrimonio_inicial(
            profile_id=profile_id,
            saldos_cuentas=saldos_cuentas,
            deudas_tarjetas=deudas_tarjetas,
            fecha_base=fecha_base or date.today(),
        )

        logger.info(
            f"Patrimonio inicial establecido para {profile_id[:8]}...: "
            f"activos={snapshot.total_activos_crc:,.2f}, "
            f"deudas={snapshot.total_deudas_crc:,.2f}, "
            f"neto={snapshot.patrimonio_neto_crc:,.2f}"
        )

    def get_onboarding_summary(self, user_id: str) -> dict:
        """
        Obtiene un resumen del onboarding completado.

        Args:
            user_id: ID del usuario

        Returns:
            Resumen con cuentas, tarjetas y próximos pasos
        """
        state = self._states.get(user_id)
        if not state or not state.profile_id:
            return {"error": "Onboarding no encontrado"}

        # Contar entidades creadas
        accounts = self.db.execute(
            select(Account).where(
                Account.profile_id == state.profile_id,
                Account.deleted_at.is_(None),
            )
        ).scalars().all()

        cards = self.db.execute(
            select(Card).where(
                Card.profile_id == state.profile_id,
                Card.deleted_at.is_(None),
            )
        ).scalars().all()

        credit_cards = [c for c in cards if c.es_credito]

        return {
            "status": "completed" if state.current_step == OnboardingStep.COMPLETED else "in_progress",
            "progress_percent": state._calculate_progress(),
            "summary": {
                "cuentas_creadas": len(accounts),
                "tarjetas_creadas": len(cards),
                "tarjetas_credito": len(credit_cards),
                "transacciones_importadas": state.transactions_count,
            },
            "next_steps": self._get_next_steps(state, credit_cards),
        }

    def _get_next_steps(
        self,
        state: OnboardingState,
        credit_cards: list[Card],
    ) -> list[str]:
        """Genera sugerencias de próximos pasos."""
        steps = []

        if not state.email_connected:
            steps.append("📧 Conectar email para sync automático")

        if credit_cards:
            steps.append("💳 Revisar fechas de pago de tus tarjetas")

        steps.append("📊 Configurar tu presupuesto 50/30/20")
        steps.append("🎯 Crear tu primera meta de ahorro")

        return steps
