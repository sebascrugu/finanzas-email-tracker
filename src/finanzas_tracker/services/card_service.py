"""
Servicio para gestión de tarjetas de crédito y ciclos de facturación.

Este servicio maneja:
- Consulta y gestión de tarjetas
- Ciclos de facturación (crear, cerrar, consultar)
- Registro de pagos
- Cálculo de deuda y proyecciones de intereses
- Alertas de vencimiento
"""

from datetime import date, timedelta
from decimal import Decimal
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.models.billing_cycle import BillingCycle
from finanzas_tracker.models.card import Card
from finanzas_tracker.models.card_payment import CardPayment
from finanzas_tracker.models.enums import (
    BillingCycleStatus,
    CardPaymentType,
    CardType,
)


logger = logging.getLogger(__name__)


class CardService:
    """
    Servicio para gestión de tarjetas de crédito y ciclos de facturación.

    Maneja la lógica de negocio para:
    - Crear y cerrar ciclos de facturación
    - Registrar pagos a tarjetas
    - Calcular deuda actual y proyecciones
    - Generar alertas de vencimiento
    """

    def __init__(self, db: Session) -> None:
        """Inicializa el servicio con la sesión de base de datos."""
        self.db = db

    # =========================================================================
    # Tarjetas
    # =========================================================================

    def get_card(self, card_id: str) -> Card | None:
        """Obtiene una tarjeta por ID."""
        stmt = select(Card).where(
            Card.id == card_id,
            Card.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_cards_by_profile(
        self,
        profile_id: str,
        tipo: CardType | None = None,
    ) -> list[Card]:
        """
        Obtiene todas las tarjetas de un perfil.

        Args:
            profile_id: ID del perfil
            tipo: Filtrar por tipo (débito/crédito)

        Returns:
            Lista de tarjetas activas
        """
        stmt = select(Card).where(
            Card.profile_id == profile_id,
            Card.deleted_at.is_(None),
        )

        if tipo:
            stmt = stmt.where(Card.tipo == tipo)

        stmt = stmt.order_by(Card.created_at.desc())

        return list(self.db.execute(stmt).scalars().all())

    def get_credit_cards(self, profile_id: str) -> list[Card]:
        """Obtiene solo las tarjetas de crédito de un perfil."""
        return self.get_cards_by_profile(profile_id, tipo=CardType.CREDIT)

    # =========================================================================
    # Ciclos de Facturación
    # =========================================================================

    def get_billing_cycle(self, cycle_id: str) -> BillingCycle | None:
        """Obtiene un ciclo de facturación por ID."""
        stmt = select(BillingCycle).where(
            BillingCycle.id == cycle_id,
            BillingCycle.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_current_cycle(self, card_id: str) -> BillingCycle | None:
        """Obtiene el ciclo actual (abierto) de una tarjeta."""
        stmt = select(BillingCycle).where(
            BillingCycle.card_id == card_id,
            BillingCycle.status == BillingCycleStatus.OPEN,
            BillingCycle.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_pending_cycles(self, card_id: str) -> list[BillingCycle]:
        """
        Obtiene ciclos pendientes de pago (cerrados o parciales).

        Args:
            card_id: ID de la tarjeta

        Returns:
            Lista de ciclos pendientes ordenados por fecha de pago
        """
        stmt = (
            select(BillingCycle)
            .where(
                BillingCycle.card_id == card_id,
                BillingCycle.status.in_(
                    [
                        BillingCycleStatus.CLOSED,
                        BillingCycleStatus.PARTIAL,
                        BillingCycleStatus.OVERDUE,
                    ]
                ),
                BillingCycle.deleted_at.is_(None),
            )
            .order_by(BillingCycle.fecha_pago.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_cycles_by_card(
        self,
        card_id: str,
        limit: int = 12,
    ) -> list[BillingCycle]:
        """
        Obtiene los últimos ciclos de una tarjeta.

        Args:
            card_id: ID de la tarjeta
            limit: Número máximo de ciclos a retornar

        Returns:
            Lista de ciclos ordenados por fecha de corte (más reciente primero)
        """
        stmt = (
            select(BillingCycle)
            .where(
                BillingCycle.card_id == card_id,
                BillingCycle.deleted_at.is_(None),
            )
            .order_by(BillingCycle.fecha_corte.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def create_cycle(
        self,
        card_id: str,
        fecha_inicio: date,
        fecha_corte: date,
        fecha_pago: date,
        saldo_anterior: Decimal = Decimal("0.00"),
    ) -> BillingCycle:
        """
        Crea un nuevo ciclo de facturación.

        Args:
            card_id: ID de la tarjeta
            fecha_inicio: Primer día del período
            fecha_corte: Fecha de corte
            fecha_pago: Fecha límite de pago
            saldo_anterior: Saldo arrastrado del ciclo anterior

        Returns:
            Ciclo creado
        """
        cycle = BillingCycle(
            card_id=card_id,
            fecha_inicio=fecha_inicio,
            fecha_corte=fecha_corte,
            fecha_pago=fecha_pago,
            saldo_anterior=saldo_anterior,
            status=BillingCycleStatus.OPEN,
        )

        self.db.add(cycle)
        self.db.commit()
        self.db.refresh(cycle)

        logger.info(f"Ciclo creado: {cycle.id} para tarjeta {card_id[:8]}...")
        return cycle

    def create_next_cycle_for_card(self, card: Card) -> BillingCycle | None:
        """
        Crea el próximo ciclo basado en la configuración de la tarjeta.

        Usa fecha_corte y fecha_vencimiento del Card para calcular
        las fechas del próximo ciclo.

        Args:
            card: Tarjeta de crédito

        Returns:
            Nuevo ciclo o None si no es tarjeta de crédito
        """
        if not card.es_credito or not card.fecha_corte:
            return None

        today = date.today()
        dia_corte = card.fecha_corte
        dia_pago = card.fecha_vencimiento or (dia_corte + 13)  # ~13 días después

        # Calcular fechas del ciclo actual
        if today.day <= dia_corte:
            # Estamos antes del corte de este mes
            fecha_corte = date(today.year, today.month, min(dia_corte, 28))
            # Inicio es el día después del corte del mes anterior
            prev_month = today.replace(day=1) - timedelta(days=1)
            fecha_inicio = date(
                prev_month.year,
                prev_month.month,
                min(dia_corte + 1, 28),
            )
        else:
            # Estamos después del corte, crear ciclo del próximo mes
            next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
            fecha_corte = date(next_month.year, next_month.month, min(dia_corte, 28))
            fecha_inicio = date(today.year, today.month, dia_corte + 1)

        # Fecha de pago
        if dia_pago > dia_corte:
            # Pago en el mismo mes que el corte
            fecha_pago = date(fecha_corte.year, fecha_corte.month, min(dia_pago, 28))
        else:
            # Pago en el mes siguiente
            next_month = (fecha_corte.replace(day=28) + timedelta(days=4)).replace(day=1)
            fecha_pago = date(next_month.year, next_month.month, min(dia_pago, 28))

        # Ver si hay saldo pendiente del ciclo anterior
        pending = self.get_pending_cycles(card.id)
        saldo_anterior = sum((c.saldo_pendiente for c in pending), Decimal("0"))

        return self.create_cycle(
            card_id=card.id,
            fecha_inicio=fecha_inicio,
            fecha_corte=fecha_corte,
            fecha_pago=fecha_pago,
            saldo_anterior=saldo_anterior,
        )

    def close_cycle(self, cycle_id: str) -> BillingCycle | None:
        """
        Cierra un ciclo (pasó la fecha de corte).

        Calcula total a pagar y pago mínimo.

        Args:
            cycle_id: ID del ciclo

        Returns:
            Ciclo actualizado o None si no existe
        """
        cycle = self.get_billing_cycle(cycle_id)
        if not cycle:
            return None

        cycle.cerrar_ciclo()
        self.db.commit()
        self.db.refresh(cycle)

        logger.info(f"Ciclo {cycle_id[:8]}... cerrado. " f"Total: ₡{cycle.total_a_pagar:,.0f}")
        return cycle

    def add_purchase_to_cycle(
        self,
        cycle_id: str,
        monto: Decimal,
    ) -> BillingCycle | None:
        """
        Agrega una compra al total del período.

        Args:
            cycle_id: ID del ciclo
            monto: Monto de la compra

        Returns:
            Ciclo actualizado
        """
        cycle = self.get_billing_cycle(cycle_id)
        if not cycle or cycle.status != BillingCycleStatus.OPEN:
            return None

        cycle.total_periodo += monto
        self.db.commit()
        self.db.refresh(cycle)

        return cycle

    # =========================================================================
    # Pagos
    # =========================================================================

    def register_payment(
        self,
        card_id: str,
        monto: Decimal,
        fecha_pago: date | None = None,
        billing_cycle_id: str | None = None,
        tipo: CardPaymentType | None = None,
        referencia: str | None = None,
        notas: str | None = None,
    ) -> CardPayment:
        """
        Registra un pago a la tarjeta.

        Args:
            card_id: ID de la tarjeta
            monto: Monto pagado
            fecha_pago: Fecha del pago (default: hoy)
            billing_cycle_id: ID del ciclo (opcional)
            tipo: Tipo de pago (auto-detectado si no se especifica)
            referencia: Referencia bancaria
            notas: Notas adicionales

        Returns:
            Pago registrado
        """
        if fecha_pago is None:
            fecha_pago = date.today()

        # Si hay ciclo, actualizar su monto pagado
        cycle = None
        if billing_cycle_id:
            cycle = self.get_billing_cycle(billing_cycle_id)
            if cycle:
                cycle.registrar_pago(monto)

        # Auto-detectar tipo si no se especifica
        if tipo is None and cycle:
            if monto >= cycle.total_a_pagar:
                tipo = CardPaymentType.FULL
            elif monto <= cycle.pago_minimo:
                tipo = CardPaymentType.MINIMUM
            else:
                tipo = CardPaymentType.PARTIAL
        elif tipo is None:
            tipo = CardPaymentType.PARTIAL

        payment = CardPayment(
            card_id=card_id,
            billing_cycle_id=billing_cycle_id,
            monto=monto,
            tipo=tipo,
            fecha_pago=fecha_pago,
            referencia=referencia,
            notas=notas,
        )

        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)

        logger.info(f"Pago registrado: ₡{monto:,.0f} a tarjeta {card_id[:8]}... " f"({tipo.value})")
        return payment

    def get_payments_by_card(
        self,
        card_id: str,
        limit: int = 50,
    ) -> list[CardPayment]:
        """Obtiene los últimos pagos de una tarjeta."""
        stmt = (
            select(CardPayment)
            .where(CardPayment.card_id == card_id)
            .order_by(CardPayment.fecha_pago.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_payments_by_cycle(self, cycle_id: str) -> list[CardPayment]:
        """Obtiene los pagos de un ciclo específico."""
        stmt = (
            select(CardPayment)
            .where(CardPayment.billing_cycle_id == cycle_id)
            .order_by(CardPayment.fecha_pago.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    # =========================================================================
    # Cálculos y Proyecciones
    # =========================================================================

    def calculate_total_debt(self, card_id: str) -> Decimal:
        """
        Calcula la deuda total de una tarjeta.

        Incluye todos los ciclos pendientes + ciclo actual.

        Args:
            card_id: ID de la tarjeta

        Returns:
            Deuda total en colones
        """
        total = Decimal("0.00")

        # Ciclo actual
        current = self.get_current_cycle(card_id)
        if current:
            total += current.total_periodo + current.saldo_anterior

        # Ciclos pendientes
        pending = self.get_pending_cycles(card_id)
        for cycle in pending:
            total += cycle.saldo_pendiente

        return total

    def calculate_interest_projection(
        self,
        card_id: str,
        meses: int = 1,
    ) -> dict:
        """
        Proyecta intereses si solo se paga el mínimo.

        Args:
            card_id: ID de la tarjeta
            meses: Meses a proyectar

        Returns:
            Dict con proyección de intereses y saldo
        """
        card = self.get_card(card_id)
        if not card or not card.interest_rate_annual:
            return {"error": "Tarjeta no encontrada o sin tasa de interés"}

        deuda_actual = self.calculate_total_debt(card_id)
        tasa_mensual = card.interest_rate_annual / Decimal("12") / Decimal("100")
        pago_minimo_pct = card.minimum_payment_percentage or Decimal("10")

        saldo = deuda_actual
        total_intereses = Decimal("0.00")
        historial: list[dict[str, float | int]] = []

        for mes in range(1, meses + 1):
            interes = (saldo * tasa_mensual).quantize(Decimal("0.01"))
            total_intereses += interes

            pago_minimo = (saldo * pago_minimo_pct / 100).quantize(Decimal("0.01"))
            saldo = saldo + interes - pago_minimo

            historial.append(
                {
                    "mes": mes,
                    "saldo_inicial": float(
                        deuda_actual if mes == 1 else historial[-1]["saldo_final"]
                    ),
                    "interes": float(interes),
                    "pago_minimo": float(pago_minimo),
                    "saldo_final": float(saldo),
                }
            )

        return {
            "deuda_inicial": float(deuda_actual),
            "tasa_mensual": float(tasa_mensual * 100),
            "meses_proyectados": meses,
            "total_intereses": float(total_intereses),
            "saldo_final": float(saldo),
            "historial": historial,
        }

    # =========================================================================
    # Alertas
    # =========================================================================

    def get_upcoming_payments(
        self,
        profile_id: str,
        dias: int = 7,
    ) -> list[dict]:
        """
        Obtiene los pagos que vencen en los próximos días.

        Args:
            profile_id: ID del perfil
            dias: Días a considerar (default: 7)

        Returns:
            Lista de alertas con información del vencimiento
        """
        cards = self.get_credit_cards(profile_id)
        alertas = []
        hoy = date.today()
        limite = hoy + timedelta(days=dias)

        for card in cards:
            pending = self.get_pending_cycles(card.id)
            for cycle in pending:
                if hoy <= cycle.fecha_pago <= limite:
                    dias_restantes = (cycle.fecha_pago - hoy).days
                    alertas.append(
                        {
                            "card_id": card.id,
                            "card_nombre": card.nombre_display,
                            "cycle_id": cycle.id,
                            "fecha_pago": cycle.fecha_pago.isoformat(),
                            "dias_restantes": dias_restantes,
                            "monto_pendiente": float(cycle.saldo_pendiente),
                            "pago_minimo": float(cycle.pago_minimo),
                            "es_urgente": dias_restantes <= 3,
                        }
                    )

        return sorted(alertas, key=lambda x: x["dias_restantes"])

    def get_overdue_cycles(self, profile_id: str) -> list[dict]:
        """
        Obtiene los ciclos vencidos (pasó la fecha de pago).

        Args:
            profile_id: ID del perfil

        Returns:
            Lista de ciclos vencidos con información
        """
        cards = self.get_credit_cards(profile_id)
        vencidos = []

        for card in cards:
            pending = self.get_pending_cycles(card.id)
            for cycle in pending:
                if cycle.esta_vencido:
                    # Marcar como vencido si no lo está ya
                    if cycle.status != BillingCycleStatus.OVERDUE:
                        cycle.marcar_vencido()
                        self.db.commit()

                    dias_vencido = (date.today() - cycle.fecha_pago).days
                    vencidos.append(
                        {
                            "card_id": card.id,
                            "card_nombre": card.nombre_display,
                            "cycle_id": cycle.id,
                            "fecha_pago": cycle.fecha_pago.isoformat(),
                            "dias_vencido": dias_vencido,
                            "monto_pendiente": float(cycle.saldo_pendiente),
                            "interes_estimado": float(
                                cycle.saldo_pendiente
                                * (card.interest_rate_annual or Decimal("52"))
                                / Decimal("365")
                                * dias_vencido
                                / 100
                            ),
                        }
                    )

        return sorted(vencidos, key=lambda x: x["dias_vencido"], reverse=True)

    # =========================================================================
    # Resumen de Tarjeta
    # =========================================================================

    def get_card_summary(self, card_id: str) -> dict | None:
        """
        Obtiene un resumen completo del estado de una tarjeta.

        Args:
            card_id: ID de la tarjeta

        Returns:
            Dict con resumen o None si no existe
        """
        card = self.get_card(card_id)
        if not card:
            return None

        current_cycle = self.get_current_cycle(card_id)
        pending_cycles = self.get_pending_cycles(card_id)
        total_debt = self.calculate_total_debt(card_id)
        recent_payments = self.get_payments_by_card(card_id, limit=5)

        # Calcular disponible
        disponible = None
        if card.limite_credito:
            disponible = card.limite_credito - total_debt

        # Próximo pago
        next_payment = None
        if pending_cycles:
            cycle = pending_cycles[0]
            next_payment = {
                "fecha": cycle.fecha_pago.isoformat(),
                "dias_restantes": (cycle.fecha_pago - date.today()).days,
                "monto": float(cycle.saldo_pendiente),
                "pago_minimo": float(cycle.pago_minimo),
            }

        return {
            "tarjeta": {
                "id": card.id,
                "nombre": card.nombre_display,
                "tipo": card.tipo.value,
                "banco": card.banco.value,
                "limite": float(card.limite_credito) if card.limite_credito else None,
            },
            "deuda_total": float(total_debt),
            "disponible": float(disponible) if disponible else None,
            "porcentaje_usado": (
                float(total_debt / card.limite_credito * 100) if card.limite_credito else None
            ),
            "ciclo_actual": {
                "id": current_cycle.id,
                "periodo": f"{current_cycle.fecha_inicio} - {current_cycle.fecha_corte}",
                "total_periodo": float(current_cycle.total_periodo),
            }
            if current_cycle
            else None,
            "proximo_pago": next_payment,
            "ciclos_pendientes": len(pending_cycles),
            "ultimos_pagos": [
                {
                    "fecha": p.fecha_pago.isoformat(),
                    "monto": float(p.monto),
                    "tipo": p.tipo.value,
                }
                for p in recent_payments
            ],
        }
