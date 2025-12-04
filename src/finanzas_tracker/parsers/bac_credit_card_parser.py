"""Parser para estados de cuenta de TARJETAS DE CRÉDITO BAC.

Extrae transacciones de los PDFs mensuales de tarjetas de crédito.
Diferente al bac_pdf_parser.py que es para cuentas bancarias.

Formato de tarjeta de crédito:
- Página 1: Resumen (titular, tarjeta, montos)
- Página 2: Info de la tarjeta, fechas, límites
- Página 3+: Transacciones por sección (compras, intereses, seguros)
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re

import pdfplumber

from finanzas_tracker.core.logging import get_logger


logger = get_logger(__name__)


@dataclass
class CreditCardTransaction:
    """Transacción extraída de un estado de cuenta de tarjeta de crédito."""

    referencia: str
    fecha: date
    concepto: str
    lugar: str | None
    moneda: str  # "CRC" o "USD"
    monto_crc: Decimal
    monto_usd: Decimal
    tipo: str  # "compra", "pago", "interes", "seguro", "cargo"
    tarjeta_ultimos_4: str


@dataclass
class CreditCardMetadata:
    """Metadata del estado de cuenta de tarjeta."""

    nombre_titular: str
    tarjeta_marca: str  # VISA, MASTERCARD, AMERICAN EXPRESS
    tarjeta_ultimos_4: str
    fecha_corte: date
    fecha_pago_minimo: date
    fecha_pago_contado: date
    limite_credito_usd: Decimal
    saldo_disponible_usd: Decimal
    pago_minimo_crc: Decimal
    pago_contado_crc: Decimal
    cuenta_iban_colones: str | None = None
    cuenta_iban_dolares: str | None = None


@dataclass
class CreditCardStatementResult:
    """Resultado del parsing de un estado de cuenta de tarjeta."""

    metadata: CreditCardMetadata
    transactions: list[CreditCardTransaction]
    source_file: str
    pages_processed: int
    total_compras_crc: Decimal = Decimal("0")
    total_compras_usd: Decimal = Decimal("0")
    total_intereses: Decimal = Decimal("0")
    total_seguros: Decimal = Decimal("0")
    errors: list[str] = field(default_factory=list)


class BACCreditCardParser:
    """Parser para estados de cuenta de tarjetas de crédito BAC."""

    # Patrones regex
    NOMBRE_PATTERN = re.compile(r"^([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+)$", re.MULTILINE)
    FECHA_CORTE_PATTERN = re.compile(r"Fecha de corte:\s*(\d{1,2}-[A-Z]{3}-\d{2})")
    FECHA_PAGO_PATTERN = re.compile(
        r"Fecha límite pago (?:mínimo|de contado):\s*(\d{1,2}-[A-Z]{3}-\d{2})"
    )
    LIMITE_PATTERN = re.compile(r"Límite de crédito:\s*USD\s*([\d,]+\.?\d*)")
    DISPONIBLE_PATTERN = re.compile(r"Saldo disponible:\s*USD\s*([\d,]+\.?\d*)")
    IBAN_CRC_PATTERN = re.compile(
        r"Cuenta IBAN colones:\s*(CR\d{2}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{2})"
    )
    IBAN_USD_PATTERN = re.compile(
        r"Cuenta IBAN dólares:\s*(CR\d{2}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{2})"
    )
    TARJETA_PATTERN = re.compile(r"\*{11}(\d{4})")
    MARCA_PATTERN = re.compile(r"(VISA|MASTERCARD|AMERICAN EXPRESS)")

    # Patrón para transacciones de compras
    # Formato: REFERENCIA  FECHA  CONCEPTO  LUGAR  MONEDA  MONTO_CRC  [MONTO_USD]
    COMPRA_PATTERN = re.compile(
        r"(\d{12})\s+"  # Referencia (12 dígitos)
        r"(\d{1,2}-[A-Z]{3}-\d{2})\s+"  # Fecha
        r"(.+?)\s+"  # Concepto
        r"((?:[A-Z][a-z]+\s*)+|CRC|USD)\s+"  # Lugar o moneda
        r"([\d,]+\.\d{2})"  # Monto
    )

    # Meses en español
    MESES = {
        "ENE": 1,
        "FEB": 2,
        "MAR": 3,
        "ABR": 4,
        "MAY": 5,
        "JUN": 6,
        "JUL": 7,
        "AGO": 8,
        "SEP": 9,
        "OCT": 10,
        "NOV": 11,
        "DIC": 12,
    }

    def __init__(self) -> None:
        """Inicializa el parser."""
        logger.info("BACCreditCardParser inicializado")

    def parse(self, pdf_path: str | Path) -> CreditCardStatementResult:
        """
        Parsea un estado de cuenta de tarjeta de crédito.

        Args:
            pdf_path: Ruta al archivo PDF

        Returns:
            CreditCardStatementResult con metadata y transacciones
        """
        pdf_path = Path(pdf_path)
        logger.info(f"Parseando estado de tarjeta: {pdf_path.name}")

        transactions: list[CreditCardTransaction] = []
        errors: list[str] = []
        metadata = None

        with pdfplumber.open(pdf_path) as pdf:
            # Extraer texto de todas las páginas
            all_text = ""
            for page in pdf.pages:
                text = page.extract_text() or ""
                all_text += text + "\n"

            # Extraer metadata de páginas 1 y 2
            metadata = self._extract_metadata(all_text)

            # Extraer transacciones de página 3 en adelante
            for i, page in enumerate(pdf.pages):
                if i < 2:  # Saltar páginas 1 y 2 (índice 0 y 1)
                    continue

                text = page.extract_text() or ""
                page_txns = self._extract_transactions(
                    text,
                    metadata.tarjeta_ultimos_4 if metadata else "0000",
                    metadata.fecha_corte.year if metadata else 2025,
                )
                transactions.extend(page_txns)

        # Calcular totales
        total_compras_crc = sum(t.monto_crc for t in transactions if t.tipo == "compra")
        total_compras_usd = sum(t.monto_usd for t in transactions if t.tipo == "compra")
        total_intereses = sum(t.monto_crc for t in transactions if t.tipo == "interes")
        total_seguros = sum(t.monto_crc for t in transactions if t.tipo == "seguro")

        logger.info(f"✅ Extraídas {len(transactions)} transacciones de tarjeta")

        return CreditCardStatementResult(
            metadata=metadata,
            transactions=transactions,
            source_file=str(pdf_path),
            pages_processed=len(pdf.pages) if "pdf" in dir() else 0,
            total_compras_crc=total_compras_crc,
            total_compras_usd=total_compras_usd,
            total_intereses=total_intereses,
            total_seguros=total_seguros,
            errors=errors,
        )

    def _extract_metadata(self, text: str) -> CreditCardMetadata:
        """Extrae metadata del estado de cuenta."""

        # Nombre titular (primera línea que parece nombre)
        nombre_match = self.NOMBRE_PATTERN.search(text)
        nombre = nombre_match.group(1).strip() if nombre_match else "DESCONOCIDO"

        # Tarjeta
        tarjeta_match = self.TARJETA_PATTERN.search(text)
        tarjeta_ultimos_4 = tarjeta_match.group(1) if tarjeta_match else "0000"

        # Marca
        marca_match = self.MARCA_PATTERN.search(text)
        marca = marca_match.group(1) if marca_match else "DESCONOCIDA"

        # Fecha de corte
        fecha_corte = date.today()
        corte_match = self.FECHA_CORTE_PATTERN.search(text)
        if corte_match:
            fecha_corte = self._parse_fecha(corte_match.group(1))

        # Fechas de pago
        fecha_pago = fecha_corte
        pago_matches = self.FECHA_PAGO_PATTERN.findall(text)
        if pago_matches:
            fecha_pago = self._parse_fecha(pago_matches[0])

        # Límite y disponible
        limite_usd = Decimal("0")
        limite_match = self.LIMITE_PATTERN.search(text)
        if limite_match:
            limite_usd = self._parse_monto(limite_match.group(1))

        disponible_usd = Decimal("0")
        disponible_match = self.DISPONIBLE_PATTERN.search(text)
        if disponible_match:
            disponible_usd = self._parse_monto(disponible_match.group(1))

        # Pagos (buscar en primera página)
        pago_minimo = Decimal("0")
        pago_contado = Decimal("0")

        # Buscar patrón de pagos en la primera línea de resumen
        pago_pattern = re.search(
            r"(\d[\d,]*\.\d{2})\s+(\d[\d,]*\.\d{2})\s*$", text[:1000], re.MULTILINE
        )
        if pago_pattern:
            pago_minimo = self._parse_monto(pago_pattern.group(1))
            pago_contado = self._parse_monto(pago_pattern.group(2))

        # IBANs
        iban_crc = None
        iban_crc_match = self.IBAN_CRC_PATTERN.search(text)
        if iban_crc_match:
            iban_crc = iban_crc_match.group(1).replace(" ", "")

        iban_usd = None
        iban_usd_match = self.IBAN_USD_PATTERN.search(text)
        if iban_usd_match:
            iban_usd = iban_usd_match.group(1).replace(" ", "")

        return CreditCardMetadata(
            nombre_titular=nombre,
            tarjeta_marca=marca,
            tarjeta_ultimos_4=tarjeta_ultimos_4,
            fecha_corte=fecha_corte,
            fecha_pago_minimo=fecha_pago,
            fecha_pago_contado=fecha_pago,
            limite_credito_usd=limite_usd,
            saldo_disponible_usd=disponible_usd,
            pago_minimo_crc=pago_minimo,
            pago_contado_crc=pago_contado,
            cuenta_iban_colones=iban_crc,
            cuenta_iban_dolares=iban_usd,
        )

    def _extract_transactions(
        self,
        text: str,
        tarjeta_4: str,
        year: int,
    ) -> list[CreditCardTransaction]:
        """Extrae transacciones de una página."""

        transactions: list[CreditCardTransaction] = []

        # Detectar sección actual basándose en encabezados del PDF
        # Por defecto es compra si estamos en página de transacciones
        current_section = "compra"

        # Marcar secciones según encabezados que aparezcan ANTES de las transacciones
        text_lower = text.lower()

        # Buscar líneas que parecen transacciones
        lines = text.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detectar cambios de sección (los encabezados del PDF)
            line_lower = line.lower()
            if "detalle de compras" in line_lower or "b) detalle" in line_lower:
                current_section = "compra"
                continue
            if "detalle de intereses" in line_lower or "c) detalle de intereses" in line_lower:
                current_section = "interes"
                continue
            if "detalle de otros cargos" in line_lower or "d) detalle" in line_lower:
                current_section = "cargo"
                continue
            if "productos y servicios" in line_lower or "e) detalle" in line_lower:
                current_section = "seguro"
                continue
            if "detalle de pago" in line_lower or "a) detalle" in line_lower:
                current_section = "pago"
                continue

            # Saltar encabezados y texto informativo
            if any(
                skip in line
                for skip in [
                    "N. Referencia",
                    "Concepto/Descripción",
                    "Transacción",
                    "No se registran",
                    "Total por concepto",
                    "Saldos al corte",
                    "Monto en colones",
                    "colones",
                    "dólares",
                    "TARJETA DE CREDITO",
                    "Total de compras",
                    "Total de intereses",
                ]
            ):
                continue

            # Intentar parsear como transacción
            txn = self._parse_transaction_line(line, current_section, tarjeta_4, year)
            if txn:
                transactions.append(txn)

        return transactions

    def _parse_transaction_line(
        self,
        line: str,
        section: str,
        tarjeta_4: str,
        year: int,
    ) -> CreditCardTransaction | None:
        """Intenta parsear una línea como transacción."""

        # Patrón para compras: REF FECHA CONCEPTO [LUGAR] [MONEDA] MONTO
        # Ejemplo: 110124844620 1-NOV-25 AL PUNTO CARNICERIA CRC 9,670.00

        # Buscar referencia al inicio (12 dígitos)
        ref_match = re.match(r"^(\d{12})\s+", line)
        if not ref_match:
            return None

        referencia = ref_match.group(1)
        rest = line[ref_match.end() :]

        # Buscar fecha
        fecha_match = re.match(r"(\d{1,2}-[A-Z]{3}-\d{2})\s+", rest)
        if not fecha_match:
            return None

        fecha = self._parse_fecha(fecha_match.group(1), year)
        rest = rest[fecha_match.end() :]

        # Buscar monto al final
        monto_match = re.search(r"([\d,]+\.\d{2})(?:\s+([\d,]+\.\d{2}))?$", rest)
        if not monto_match:
            return None

        monto1 = self._parse_monto(monto_match.group(1))
        monto2 = self._parse_monto(monto_match.group(2)) if monto_match.group(2) else Decimal("0")

        # El resto es concepto + lugar
        concepto_lugar = rest[: monto_match.start()].strip()

        # Detectar moneda (CRC o USD al final del concepto)
        moneda = "CRC"
        if concepto_lugar.endswith(" USD"):
            moneda = "USD"
            concepto_lugar = concepto_lugar[:-4].strip()
        elif concepto_lugar.endswith(" CRC"):
            concepto_lugar = concepto_lugar[:-4].strip()

        # Separar concepto y lugar (el lugar suele estar al final en mayúsculas/minúsculas)
        lugar = None
        parts = concepto_lugar.rsplit(" ", 2)
        if len(parts) >= 2:
            # Verificar si las últimas palabras son un lugar
            possible_lugar = parts[-1]
            if possible_lugar and possible_lugar[0].isupper() and len(possible_lugar) > 2:
                lugar = possible_lugar
                concepto = " ".join(parts[:-1])
            else:
                concepto = concepto_lugar
        else:
            concepto = concepto_lugar

        # Determinar montos CRC y USD
        if moneda == "USD":
            monto_usd = monto1
            monto_crc = monto2 if monto2 > 0 else Decimal("0")
        else:
            monto_crc = monto1
            monto_usd = monto2 if monto2 > 0 else Decimal("0")

        return CreditCardTransaction(
            referencia=referencia,
            fecha=fecha,
            concepto=concepto,
            lugar=lugar,
            moneda=moneda,
            monto_crc=monto_crc,
            monto_usd=monto_usd,
            tipo=section,
            tarjeta_ultimos_4=tarjeta_4,
        )

    def _parse_fecha(self, fecha_str: str, default_year: int | None = None) -> date:
        """Parsea fecha en formato DD-MMM-YY."""
        try:
            parts = fecha_str.split("-")
            dia = int(parts[0])
            mes = self.MESES.get(parts[1].upper(), 1)

            if len(parts[2]) == 2:
                año = 2000 + int(parts[2])
            else:
                año = int(parts[2])

            return date(año, mes, dia)
        except Exception:
            return date.today() if default_year is None else date(default_year, 1, 1)

    def _parse_monto(self, monto_str: str) -> Decimal:
        """Parsea monto con comas y punto decimal."""
        try:
            clean = monto_str.replace(",", "").strip()
            return Decimal(clean)
        except (InvalidOperation, ValueError):
            return Decimal("0")


__all__ = [
    "BACCreditCardParser",
    "CreditCardTransaction",
    "CreditCardMetadata",
    "CreditCardStatementResult",
]
