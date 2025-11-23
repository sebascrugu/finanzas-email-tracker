"""Servicio de reconciliación de estados de cuenta PDF."""

import base64
import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import anthropic
from sqlalchemy import and_

from finanzas_tracker.config.settings import settings
from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.core.retry import retry_on_anthropic_error
from finanzas_tracker.models.bank_statement import BankStatement
from finanzas_tracker.models.enums import BankName, Currency, TransactionType
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.schemas.reconciliation import (
    MatchResult,
    ParsedPDFTransaction,
    ReconciliationReport,
    ReconciliationSummary,
)
from finanzas_tracker.services.categorizer import TransactionCategorizer
from finanzas_tracker.services.duplicate_detector import DuplicateDetectorService

logger = get_logger(__name__)


class PDFReconciliationService:
    """
    Servicio de reconciliación de estados de cuenta PDF.

    Workflow completo:
    1. Upload PDF → Extract text + tables con Claude Vision
    2. Parse transactions del PDF
    3. Match con transacciones existentes (emails) usando fuzzy matching
    4. Categorizar transacciones nuevas con AI
    5. Generar reporte de reconciliación con insights
    6. Guardar en base de datos

    Use cases:
    - Validar que todas las transacciones del banco están en el sistema
    - Detectar correos no recibidos o perdidos
    - Identificar discrepancias entre correos y estado oficial
    - Completar el historial de transacciones
    """

    def __init__(self) -> None:
        """Inicializa el servicio de reconciliación."""
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.duplicate_detector = DuplicateDetectorService()
        self.categorizer = TransactionCategorizer()
        logger.info("PDFReconciliationService inicializado")

    # ========================================================================
    # MAIN WORKFLOW
    # ========================================================================

    def process_bank_statement(
        self,
        pdf_content: bytes,
        profile_id: str,
        banco: BankName,
        fecha_corte: date | None = None,
        pdf_filename: str = "statement.pdf",
    ) -> ReconciliationReport:
        """
        Procesa un estado de cuenta PDF completo.

        Args:
            pdf_content: Contenido del PDF en bytes
            profile_id: ID del perfil
            banco: Banco del estado de cuenta
            fecha_corte: Fecha de corte (opcional, se extrae del PDF)
            pdf_filename: Nombre del archivo PDF

        Returns:
            ReconciliationReport con resultados completos

        Raises:
            ValueError: Si el PDF es inválido o no se puede procesar
        """
        logger.info(
            f"🔄 Iniciando reconciliación de estado de cuenta - "
            f"Banco: {banco.value}, Archivo: {pdf_filename}"
        )

        # Calcular hash del PDF para detectar duplicados
        pdf_hash = self._calculate_pdf_hash(pdf_content)

        # Verificar si ya procesamos este PDF
        with get_session() as session:
            existing = (
                session.query(BankStatement)
                .filter(
                    and_(
                        BankStatement.profile_id == profile_id,
                        BankStatement.pdf_hash == pdf_hash,
                        BankStatement.deleted_at.is_(None),
                    )
                )
                .first()
            )

            if existing:
                logger.warning(f"⚠️  PDF ya procesado anteriormente: {existing.id}")
                raise ValueError(
                    f"Este estado de cuenta ya fue procesado el "
                    f"{existing.created_at.strftime('%Y-%m-%d %H:%M')}"
                )

        # Crear registro de statement (en estado 'processing')
        statement = self._create_statement_record(
            profile_id=profile_id,
            banco=banco,
            pdf_filename=pdf_filename,
            pdf_hash=pdf_hash,
            fecha_corte=fecha_corte,
        )

        try:
            # 1. Extraer transacciones del PDF con Claude Vision
            logger.info("📄 Extrayendo transacciones del PDF con Claude Vision...")
            pdf_data = self._extract_transactions_from_pdf(pdf_content, banco)

            # Actualizar statement con datos extraídos
            statement.cuenta_iban = pdf_data.get("cuenta_iban", "")
            statement.fecha_corte = pdf_data.get("fecha_corte", fecha_corte or date.today())
            statement.periodo = pdf_data.get("periodo", "")
            statement.saldo_inicial = Decimal(str(pdf_data.get("saldo_inicial", 0)))
            statement.saldo_final = Decimal(str(pdf_data.get("saldo_final", 0)))
            statement.total_debitos = Decimal(str(pdf_data.get("total_debitos", 0)))
            statement.total_creditos = Decimal(str(pdf_data.get("total_creditos", 0)))

            # Parse transactions
            pdf_transactions = self._parse_pdf_transactions(pdf_data["transactions"])
            logger.info(f"✅ Extraídas {len(pdf_transactions)} transacciones del PDF")

            # 2. Obtener transacciones del período desde emails
            email_transactions = self._get_email_transactions_for_period(
                profile_id=profile_id,
                banco=banco,
                start_date=pdf_data.get("periodo_inicio"),
                end_date=pdf_data.get("fecha_corte", fecha_corte or date.today()),
            )
            logger.info(f"📧 Encontradas {len(email_transactions)} transacciones en emails")

            # 3. Hacer matching
            logger.info("🔍 Matcheando transacciones PDF vs Emails...")
            matches = self._match_transactions(pdf_transactions, email_transactions)

            # 4. Generar reporte
            logger.info("📊 Generando reporte de reconciliación...")
            report = self._build_reconciliation_report(
                statement_id=statement.id,
                profile_id=profile_id,
                banco=banco.value,
                fecha_corte=statement.fecha_corte,
                cuenta_iban=statement.cuenta_iban,
                pdf_transactions=pdf_transactions,
                email_transactions=email_transactions,
                matches=matches,
                raw_pdf_data=pdf_data,
            )

            # 5. Guardar resultados
            statement.total_transactions_pdf = report.summary.total_pdf_transactions
            statement.matched_count = report.summary.matched_count
            statement.missing_in_emails_count = report.summary.missing_in_emails
            statement.missing_in_statement_count = report.summary.missing_in_statement
            statement.discrepancies_count = report.summary.discrepancies
            statement.reconciliation_report = report.to_dict()
            statement.mark_as_completed()

            with get_session() as session:
                session.add(statement)
                session.commit()

            logger.success(
                f"✅ Reconciliación completada exitosamente!\n"
                f"   - Matched: {report.summary.matched_count}/{report.summary.total_pdf_transactions}\n"
                f"   - Missing in emails: {report.summary.missing_in_emails}\n"
                f"   - Discrepancies: {report.summary.discrepancies}\n"
                f"   - Status: {report.summary.status.upper()}"
            )

            return report

        except Exception as e:
            # Marcar statement como failed
            statement.mark_as_failed(str(e))
            with get_session() as session:
                session.add(statement)
                session.commit()

            logger.error(f"❌ Error procesando estado de cuenta: {e}")
            raise

    # ========================================================================
    # PDF EXTRACTION (Claude Vision)
    # ========================================================================

    @retry_on_anthropic_error(max_attempts=3, max_wait=16)
    def _extract_transactions_from_pdf(
        self, pdf_content: bytes, banco: BankName
    ) -> dict[str, Any]:
        """
        Extrae transacciones del PDF usando Claude Vision API.

        Args:
            pdf_content: Contenido del PDF en bytes
            banco: Banco del estado de cuenta

        Returns:
            Dict con:
            - cuenta_iban: IBAN de la cuenta
            - fecha_corte: Fecha de corte
            - periodo: Período (ej: "Octubre 2025")
            - saldo_inicial: Saldo inicial
            - saldo_final: Saldo final
            - total_debitos: Total de débitos
            - total_creditos: Total de créditos
            - transactions: Lista de transacciones
        """
        # Encode PDF a base64
        pdf_base64 = base64.b64encode(pdf_content).decode("utf-8")

        # Prompt específico según banco
        prompt = self._build_extraction_prompt(banco)

        logger.debug("Llamando a Claude Vision API...")
        message = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",  # Sonnet para mejor extracción
            max_tokens=8000,
            temperature=0,  # Determinístico para extracción
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_base64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )

        # Parse JSON response
        response_text = message.content[0].text  # type: ignore[union-attr]

        # Limpiar si viene con markdown
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        try:
            result = json.loads(response_text)
            logger.debug(f"✅ Extraídas {len(result.get('transactions', []))} transacciones del PDF")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando respuesta de Claude: {e}")
            logger.debug(f"Respuesta: {response_text[:500]}")
            raise ValueError(f"No se pudo parsear respuesta de Claude: {e}")

    def _build_extraction_prompt(self, banco: BankName) -> str:
        """Construye el prompt para extracción según el banco."""
        if banco == BankName.BAC:
            return """Eres un experto en análisis de estados de cuenta de BAC Credomatic (Costa Rica).

Extrae TODA la información del estado de cuenta y devuelve un JSON estructurado.

INFORMACIÓN A EXTRAER:

1. **Metadata del estado**:
   - cuenta_iban: IBAN completo (ej: "CR72 0102 0000 9661 5395 99")
   - fecha_corte: Fecha de corte en formato YYYY-MM-DD
   - periodo: Descripción del período (ej: "Octubre 2025")
   - periodo_inicio: Primera fecha de transacción (YYYY-MM-DD)
   - saldo_inicial: Saldo inicial del período
   - saldo_final: Saldo al corte
   - total_debitos: Total de débitos
   - total_creditos: Total de créditos

2. **Transacciones**: Extrae TODAS las transacciones listadas. Para cada una:
   - fecha: YYYY-MM-DD
   - referencia: Número de referencia
   - concepto: Descripción completa (comercio/concepto)
   - tipo: "debito" o "credito"
   - monto: Monto como número decimal (SIN formato, solo dígitos y punto)

FORMATO DE SALIDA (JSON válido):
```json
{
  "cuenta_iban": "CR72 0102 0000 9661 5395 99",
  "fecha_corte": "2025-10-31",
  "periodo": "Octubre 2025",
  "periodo_inicio": "2025-10-01",
  "saldo_inicial": 0.00,
  "saldo_final": 120000.42,
  "total_debitos": 338642.91,
  "total_creditos": 460242.82,
  "transactions": [
    {
      "fecha": "2025-09-27",
      "referencia": "093006688",
      "concepto": "COMPASS RUTA 32 RUTA 2",
      "tipo": "debito",
      "monto": 150.00
    },
    {
      "fecha": "2025-10-03",
      "referencia": "406495639",
      "concepto": "TEF DE: 948198684",
      "tipo": "credito",
      "monto": 7014.00
    }
  ]
}
```

REGLAS IMPORTANTES:
- Extrae TODAS las transacciones, no omitas ninguna
- Los montos deben ser números (sin símbolos ni comas)
- Las fechas en formato YYYY-MM-DD
- No normalices los nombres de comercios, déjalos tal cual
- Si una transacción tiene varios conceptos, únelos con espacio
- Responde SOLO con JSON válido, sin markdown ni explicaciones"""

        elif banco == BankName.POPULAR:
            return """Eres un experto en análisis de estados de cuenta del Banco Popular (Costa Rica).

[Similar prompt adaptado para Banco Popular...]
"""

        else:
            return """Eres un experto en análisis de estados de cuenta bancarios.

Extrae toda la información del estado de cuenta en formato JSON...
"""

    def _parse_pdf_transactions(
        self, raw_transactions: list[dict[str, Any]]
    ) -> list[ParsedPDFTransaction]:
        """
        Convierte las transacciones crudas del PDF a ParsedPDFTransaction.

        Args:
            raw_transactions: Lista de transacciones del JSON de Claude

        Returns:
            Lista de ParsedPDFTransaction
        """
        parsed = []

        for idx, raw in enumerate(raw_transactions):
            try:
                # Parse fecha
                fecha_str = raw.get("fecha")
                if isinstance(fecha_str, str):
                    fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
                else:
                    fecha = fecha_str

                # Determinar tipo de transacción
                tipo_raw = raw.get("tipo", "debito").lower()
                concepto = raw.get("concepto", "").upper()

                # Clasificar tipo de transacción
                if "SINPE" in concepto or "TEF" in concepto or "TRANSFERENCIA" in concepto:
                    tipo_transaccion = TransactionType.TRANSFERENCIA
                elif "RETIRO" in concepto or "ATM" in concepto or "CAJERO" in concepto:
                    tipo_transaccion = TransactionType.RETIRO
                elif "PAGO" in concepto or "SERVICIO" in concepto:
                    tipo_transaccion = TransactionType.PAGO_SERVICIO
                else:
                    tipo_transaccion = TransactionType.COMPRA

                # Determinar moneda (por ahora CRC por defecto)
                # TODO: Detectar USD si el estado lo especifica
                moneda = Currency.CRC

                parsed_tx = ParsedPDFTransaction(
                    fecha=fecha,
                    referencia=raw.get("referencia", ""),
                    comercio=raw.get("concepto", "Desconocido"),
                    tipo_transaccion=tipo_transaccion,
                    monto=Decimal(str(raw.get("monto", 0))),
                    moneda=moneda,
                    row_number=idx + 1,
                    raw_text=json.dumps(raw, ensure_ascii=False),
                )

                parsed.append(parsed_tx)

            except (ValueError, KeyError, TypeError) as e:
                logger.warning(f"Error parseando transacción #{idx + 1}: {e}")
                logger.debug(f"Raw data: {raw}")
                continue

        return parsed

    # ========================================================================
    # MATCHING ALGORITHM
    # ========================================================================

    def _match_transactions(
        self,
        pdf_transactions: list[ParsedPDFTransaction],
        email_transactions: list[Transaction],
    ) -> list[MatchResult]:
        """
        Hace fuzzy matching entre transacciones del PDF y emails.

        Algoritmo:
        1. Para cada tx del PDF, buscar mejores candidatos en emails
        2. Calcular similarity score (comercio + monto + fecha)
        3. Clasificar por confianza (high/medium/low/no_match)

        Args:
            pdf_transactions: Transacciones extraídas del PDF
            email_transactions: Transacciones existentes en el sistema

        Returns:
            Lista de MatchResult con todos los resultados
        """
        matches = []

        for pdf_tx in pdf_transactions:
            # Buscar candidatos similares
            candidates = self._find_matching_candidates(pdf_tx, email_transactions)

            if not candidates:
                # No match encontrado
                matches.append(
                    MatchResult(
                        pdf_transaction=pdf_tx,
                        email_transaction=None,
                        match_score=0.0,
                        match_confidence="no_match",
                        match_reasons=["No se encontró ninguna transacción similar"],
                        status="missing_in_email",
                    )
                )
                continue

            # Tomar el mejor candidato
            best_candidate = candidates[0]
            email_tx = best_candidate["transaction"]
            score = best_candidate["score"]
            reasons = best_candidate["reasons"]

            # Determinar confianza
            if score >= 90:
                confidence = "high"
            elif score >= 70:
                confidence = "medium"
            else:
                confidence = "low"

            # Verificar discrepancias
            has_discrepancy, disc_type, disc_details = self._check_discrepancy(pdf_tx, email_tx)

            status = "discrepancy" if has_discrepancy else "matched"

            matches.append(
                MatchResult(
                    pdf_transaction=pdf_tx,
                    email_transaction=email_tx,
                    match_score=score,
                    match_confidence=confidence,
                    match_reasons=reasons,
                    status=status,
                    has_discrepancy=has_discrepancy,
                    discrepancy_type=disc_type,
                    discrepancy_details=disc_details,
                )
            )

        return matches

    def _find_matching_candidates(
        self, pdf_tx: ParsedPDFTransaction, email_transactions: list[Transaction]
    ) -> list[dict[str, Any]]:
        """
        Encuentra candidatos para matching usando scoring similar a DuplicateDetectorService.

        Returns:
            Lista ordenada de candidatos (mejores primero) con score y razones
        """
        candidates = []

        for email_tx in email_transactions:
            score = 0.0
            reasons = []

            # 1. Comparar comercio (requisito mínimo)
            comercio_pdf = pdf_tx.comercio.upper().strip()
            comercio_email = email_tx.comercio.upper().strip()

            # Fuzzy matching de comercio
            if comercio_pdf == comercio_email:
                score += 30
                reasons.append(f"Comercio exacto: {comercio_pdf}")
            elif comercio_pdf in comercio_email or comercio_email in comercio_pdf:
                score += 25
                reasons.append(f"Comercio similar: {comercio_pdf} ≈ {comercio_email}")
            else:
                # No es el mismo comercio, skip
                continue

            # 2. Comparar montos
            monto_pdf = float(pdf_tx.monto)
            monto_email = float(email_tx.monto_crc)

            if abs(monto_pdf - monto_email) < 0.01:
                score += 40
                reasons.append(f"Monto exacto: ₡{monto_pdf:,.2f}")
            else:
                diff_pct = abs(monto_pdf - monto_email) / max(monto_pdf, monto_email) * 100
                if diff_pct <= 1:
                    score += 30
                    reasons.append(f"Monto muy similar (diferencia {diff_pct:.1f}%)")
                elif diff_pct <= 5:
                    score += 20
                    reasons.append(f"Monto similar (diferencia {diff_pct:.1f}%)")
                else:
                    # Diferencia muy grande
                    continue

            # 3. Comparar fechas
            fecha_pdf = pdf_tx.fecha
            fecha_email = (
                email_tx.fecha_transaccion.date()
                if hasattr(email_tx.fecha_transaccion, "date")
                else email_tx.fecha_transaccion
            )

            days_diff = abs((fecha_pdf - fecha_email).days)

            if days_diff == 0:
                score += 30
                reasons.append(f"Misma fecha: {fecha_pdf}")
            elif days_diff == 1:
                score += 20
                reasons.append(f"Fechas consecutivas ({fecha_pdf} y {fecha_email})")
            elif days_diff <= 3:
                score += 10
                reasons.append(f"Fechas cercanas (diferencia: {days_diff} días)")

            # Normalizar a 100
            normalized_score = min(score / 1.0, 100.0)

            if normalized_score >= 50:  # Mínimo 50% para considerar candidato
                candidates.append(
                    {"transaction": email_tx, "score": normalized_score, "reasons": reasons}
                )

        # Ordenar por score (mejor primero)
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates

    def _check_discrepancy(
        self, pdf_tx: ParsedPDFTransaction, email_tx: Transaction
    ) -> tuple[bool, str | None, str | None]:
        """
        Verifica si hay discrepancias entre transacción del PDF y email.

        Returns:
            (has_discrepancy, discrepancy_type, details)
        """
        # Verificar monto
        monto_pdf = float(pdf_tx.monto)
        monto_email = float(email_tx.monto_crc)

        if abs(monto_pdf - monto_email) > 1.0:  # Diferencia > ₡1
            diff = monto_pdf - monto_email
            return (
                True,
                "amount",
                f"Diferencia de ₡{diff:,.2f} (PDF: ₡{monto_pdf:,.2f}, Email: ₡{monto_email:,.2f})",
            )

        # Verificar fecha (más de 3 días de diferencia)
        fecha_pdf = pdf_tx.fecha
        fecha_email = (
            email_tx.fecha_transaccion.date()
            if hasattr(email_tx.fecha_transaccion, "date")
            else email_tx.fecha_transaccion
        )
        days_diff = abs((fecha_pdf - fecha_email).days)

        if days_diff > 3:
            return (
                True,
                "date",
                f"Diferencia de {days_diff} días (PDF: {fecha_pdf}, Email: {fecha_email})",
            )

        return (False, None, None)

    # ========================================================================
    # HELPERS
    # ========================================================================

    def _get_email_transactions_for_period(
        self,
        profile_id: str,
        banco: BankName,
        start_date: date | None,
        end_date: date,
    ) -> list[Transaction]:
        """Obtiene transacciones de emails para el período."""
        # Si no hay start_date, usar 30 días antes del corte
        if not start_date:
            from datetime import timedelta

            start_date = end_date - timedelta(days=35)

        with get_session() as session:
            transactions = (
                session.query(Transaction)
                .filter(
                    and_(
                        Transaction.profile_id == profile_id,
                        Transaction.banco == banco,
                        Transaction.fecha_transaccion >= start_date,
                        Transaction.fecha_transaccion <= end_date,
                        Transaction.deleted_at.is_(None),
                    )
                )
                .all()
            )

            # Expunge para uso fuera de la sesión
            for tx in transactions:
                session.expunge(tx)

            return transactions

    def _build_reconciliation_report(
        self,
        statement_id: str,
        profile_id: str,
        banco: str,
        fecha_corte: date,
        cuenta_iban: str,
        pdf_transactions: list[ParsedPDFTransaction],
        email_transactions: list[Transaction],
        matches: list[MatchResult],
        raw_pdf_data: dict[str, Any],
    ) -> ReconciliationReport:
        """Construye el reporte de reconciliación."""
        # Clasificar matches
        matched = [m for m in matches if m.status == "matched"]
        missing_in_emails = [
            m.pdf_transaction for m in matches if m.status == "missing_in_email"
        ]
        discrepancies = [m for m in matches if m.status == "discrepancy"]

        # Encontrar transacciones en emails que no están en PDF
        matched_email_ids = {m.email_transaction.id for m in matched if m.email_transaction}
        missing_in_statement = [tx for tx in email_transactions if tx.id not in matched_email_ids]

        # Calcular summary
        total_monto_pdf = sum(tx.monto for tx in pdf_transactions)
        total_monto_emails = sum(tx.monto_crc for tx in email_transactions)

        summary = ReconciliationSummary(
            total_pdf_transactions=len(pdf_transactions),
            total_email_transactions=len(email_transactions),
            matched_count=len(matched),
            matched_high_confidence=len([m for m in matched if m.match_confidence == "high"]),
            matched_medium_confidence=len([m for m in matched if m.match_confidence == "medium"]),
            matched_low_confidence=len([m for m in matched if m.match_confidence == "low"]),
            missing_in_emails=len(missing_in_emails),
            missing_in_statement=len(missing_in_statement),
            discrepancies=len(discrepancies),
            total_monto_pdf=total_monto_pdf,
            total_monto_emails=total_monto_emails,
            difference=total_monto_pdf - total_monto_emails,
        )

        report = ReconciliationReport(
            statement_id=statement_id,
            profile_id=profile_id,
            banco=banco,
            fecha_corte=fecha_corte,
            cuenta_iban=cuenta_iban,
            processed_at=datetime.now(UTC),
            summary=summary,
            matched_transactions=matched,
            missing_in_emails=missing_in_emails,
            missing_in_statement=missing_in_statement,
            discrepancies=discrepancies,
            raw_pdf_data=raw_pdf_data,
        )

        return report

    def _calculate_pdf_hash(self, pdf_content: bytes) -> str:
        """Calcula hash SHA-256 del PDF."""
        return hashlib.sha256(pdf_content).hexdigest()

    def _create_statement_record(
        self,
        profile_id: str,
        banco: BankName,
        pdf_filename: str,
        pdf_hash: str,
        fecha_corte: date | None,
    ) -> BankStatement:
        """Crea el registro inicial de BankStatement."""
        statement = BankStatement(
            profile_id=profile_id,
            banco=banco,
            cuenta_iban="",  # Se llenará después de extraer del PDF
            fecha_corte=fecha_corte or date.today(),
            periodo="",  # Se llenará después
            pdf_filename=pdf_filename,
            pdf_hash=pdf_hash,
            saldo_inicial=Decimal("0"),
            saldo_final=Decimal("0"),
            total_debitos=Decimal("0"),
            total_creditos=Decimal("0"),
            processing_status="processing",
        )

        with get_session() as session:
            session.add(statement)
            session.commit()
            session.refresh(statement)
            session.expunge(statement)

        return statement


# Singleton instance
pdf_reconciliation_service = PDFReconciliationService()
