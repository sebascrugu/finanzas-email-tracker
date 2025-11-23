"""Schemas para reconciliación de estados de cuenta."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from finanzas_tracker.models.enums import Currency, TransactionType
from finanzas_tracker.models.transaction import Transaction


@dataclass
class ParsedPDFTransaction:
    """
    Transacción parseada de un PDF de estado de cuenta.

    Esta es una representación temporal antes de convertirla
    a un Transaction model completo.
    """

    # Datos básicos extraídos del PDF
    fecha: date
    referencia: str
    comercio: str
    tipo_transaccion: TransactionType
    monto: Decimal
    moneda: Currency

    # Metadata
    row_number: int  # Número de fila en el PDF para debugging
    raw_text: str | None = None  # Texto crudo del PDF para referencia

    def __str__(self) -> str:
        """String representation."""
        return (
            f"{self.fecha.strftime('%Y-%m-%d')} | "
            f"{self.comercio[:30]:30} | "
            f"{self.moneda.value} {self.monto:>12,.2f} | "
            f"{self.tipo_transaccion.value}"
        )


@dataclass
class MatchResult:
    """
    Resultado del matching entre una transacción del PDF y una del sistema.

    Representa un match encontrado con su nivel de confianza y razones.
    """

    pdf_transaction: ParsedPDFTransaction
    email_transaction: Transaction | None
    match_score: float  # 0-100
    match_confidence: str  # 'high', 'medium', 'low', 'no_match'
    match_reasons: list[str]
    status: str  # 'matched', 'missing_in_email', 'discrepancy'

    # Discrepancias (si existen)
    has_discrepancy: bool = False
    discrepancy_type: str | None = None  # 'amount', 'date', 'merchant'
    discrepancy_details: str | None = None

    @property
    def is_high_confidence(self) -> bool:
        """True si el match es de alta confianza (≥90%)."""
        return self.match_score >= 90

    @property
    def needs_review(self) -> bool:
        """True si necesita revisión manual."""
        return self.has_discrepancy or self.match_score < 70

    def __str__(self) -> str:
        """String representation."""
        status_emoji = {
            "matched": "✅",
            "missing_in_email": "⚠️",
            "discrepancy": "💰",
        }
        emoji = status_emoji.get(self.status, "❓")
        return (
            f"{emoji} {self.pdf_transaction.comercio[:30]:30} | "
            f"Score: {self.match_score:5.1f}% | "
            f"{self.match_confidence}"
        )


@dataclass
class ReconciliationSummary:
    """Resumen estadístico de la reconciliación."""

    total_pdf_transactions: int
    total_email_transactions: int

    # Matching stats
    matched_count: int
    matched_high_confidence: int
    matched_medium_confidence: int
    matched_low_confidence: int

    # Discrepancies
    missing_in_emails: int
    missing_in_statement: int
    discrepancies: int

    # Montos
    total_monto_pdf: Decimal
    total_monto_emails: Decimal
    difference: Decimal

    @property
    def match_percentage(self) -> float:
        """Porcentaje de transacciones que matchearon."""
        if self.total_pdf_transactions == 0:
            return 0.0
        return (self.matched_count / self.total_pdf_transactions) * 100

    @property
    def is_perfect_match(self) -> bool:
        """True si la reconciliación es perfecta."""
        return (
            self.missing_in_emails == 0
            and self.missing_in_statement == 0
            and self.discrepancies == 0
            and abs(self.difference) < Decimal("0.01")
        )

    @property
    def status(self) -> str:
        """
        Estado general de la reconciliación.

        Returns:
            - 'perfect': 100% reconciliado
            - 'good': >90% reconciliado
            - 'needs_review': <90% o con discrepancias importantes
        """
        if self.is_perfect_match:
            return "perfect"
        if self.match_percentage >= 90 and self.discrepancies <= 2:
            return "good"
        return "needs_review"

    def __str__(self) -> str:
        """String representation."""
        return f"""
Reconciliation Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PDF Transactions:   {self.total_pdf_transactions:>4}
Email Transactions: {self.total_email_transactions:>4}

Matched:           {self.matched_count:>4} ({self.match_percentage:.1f}%)
  - High conf:     {self.matched_high_confidence:>4}
  - Medium conf:   {self.matched_medium_confidence:>4}
  - Low conf:      {self.matched_low_confidence:>4}

Missing in emails: {self.missing_in_emails:>4}
Missing in PDF:    {self.missing_in_statement:>4}
Discrepancies:     {self.discrepancies:>4}

Total PDF:         ₡{self.total_monto_pdf:>12,.2f}
Total Emails:      ₡{self.total_monto_emails:>12,.2f}
Difference:        ₡{self.difference:>12,.2f}

Status: {self.status.upper()}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


@dataclass
class ReconciliationReport:
    """
    Reporte completo de reconciliación de un estado de cuenta.

    Este es el output principal del servicio de reconciliación.
    """

    # Metadata
    statement_id: str
    profile_id: str
    banco: str
    fecha_corte: date
    cuenta_iban: str
    processed_at: datetime

    # Resumen
    summary: ReconciliationSummary

    # Matches
    matched_transactions: list[MatchResult]
    missing_in_emails: list[ParsedPDFTransaction]
    missing_in_statement: list[Transaction]
    discrepancies: list[MatchResult]

    # Análisis AI (opcional)
    ai_insights: str | None = None
    ai_recommendations: list[str] | None = None

    # Raw data para debugging
    raw_pdf_data: dict[str, Any] | None = None

    @property
    def needs_attention(self) -> bool:
        """True si hay cosas que requieren atención del usuario."""
        return (
            len(self.missing_in_emails) > 0
            or len(self.missing_in_statement) > 0
            or len(self.discrepancies) > 0
        )

    def to_dict(self) -> dict[str, Any]:
        """Convierte el reporte a diccionario para storage."""
        return {
            "statement_id": self.statement_id,
            "profile_id": self.profile_id,
            "banco": self.banco,
            "fecha_corte": self.fecha_corte.isoformat(),
            "cuenta_iban": self.cuenta_iban,
            "processed_at": self.processed_at.isoformat(),
            "summary": {
                "total_pdf_transactions": self.summary.total_pdf_transactions,
                "total_email_transactions": self.summary.total_email_transactions,
                "matched_count": self.summary.matched_count,
                "matched_high_confidence": self.summary.matched_high_confidence,
                "matched_medium_confidence": self.summary.matched_medium_confidence,
                "matched_low_confidence": self.summary.matched_low_confidence,
                "missing_in_emails": self.summary.missing_in_emails,
                "missing_in_statement": self.summary.missing_in_statement,
                "discrepancies": self.summary.discrepancies,
                "total_monto_pdf": float(self.summary.total_monto_pdf),
                "total_monto_emails": float(self.summary.total_monto_emails),
                "difference": float(self.summary.difference),
                "match_percentage": self.summary.match_percentage,
                "status": self.summary.status,
            },
            "matched_count": len(self.matched_transactions),
            "missing_in_emails_count": len(self.missing_in_emails),
            "missing_in_statement_count": len(self.missing_in_statement),
            "discrepancies_count": len(self.discrepancies),
            "ai_insights": self.ai_insights,
            "ai_recommendations": self.ai_recommendations,
        }

    def __str__(self) -> str:
        """String representation."""
        return f"""
╔═══════════════════════════════════════════════════════════════╗
║           REPORTE DE RECONCILIACIÓN - {self.banco.upper()}                ║
╚═══════════════════════════════════════════════════════════════╝

📅 Fecha de corte: {self.fecha_corte.strftime('%Y-%m-%d')}
🏦 Cuenta: {self.cuenta_iban}
⏰ Procesado: {self.processed_at.strftime('%Y-%m-%d %H:%M:%S')}

{str(self.summary)}

{'⚠️  REQUIERE ATENCIÓN' if self.needs_attention else '✅ TODO EN ORDEN'}
"""
