"""Parser para estados de cuenta PDF de BAC Credomatic.

Extrae transacciones de los PDFs mensuales de BAC usando pdfplumber.
Más eficiente que Claude Vision para documentos estructurados.

Usa posiciones de caracteres para distinguir columnas de débito/crédito.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from typing import Any

import pdfplumber

from finanzas_tracker.core.logging import get_logger


logger = get_logger(__name__)

# Constantes de posición de columnas (basado en análisis de PDFs reales)
# Posiciones X aproximadas en el PDF
COL_REFERENCIA_START = 50
COL_FECHA_START = 140
COL_CONCEPTO_START = 190
COL_DEBITO_START = 480
COL_CREDITO_START = 550
# Para transacciones con solo 1 monto, necesitamos saber si está en débito o crédito
# Los montos de débito terminan alrededor de x=520, los de crédito empiezan en x=559+
COL_CREDITO_THRESHOLD = 555  # Si el monto empieza después de x=555, es crédito


@dataclass
class BACTransaction:
    """Transacción extraída de un estado de cuenta BAC."""

    referencia: str
    fecha: date
    concepto: str
    monto: Decimal
    tipo: str  # "debito" o "credito"
    cuenta_iban: str
    moneda: str  # "CRC" o "USD"

    # Campos derivados
    comercio_normalizado: str | None = None
    es_transferencia: bool = False
    es_sinpe: bool = False
    es_interes: bool = False


@dataclass
class BACStatementMetadata:
    """Metadata del estado de cuenta."""

    nombre_titular: str
    fecha_corte: date
    email: str | None = None
    cuentas: list[dict] = field(default_factory=list)


@dataclass
class BACStatementResult:
    """Resultado del parsing de un estado de cuenta."""

    metadata: BACStatementMetadata
    transactions: list[BACTransaction]
    source_file: str
    pages_processed: int
    errors: list[str] = field(default_factory=list)


class BACPDFParser:
    """Parser para estados de cuenta PDF de BAC Credomatic."""

    # Patrones regex compilados para eficiencia
    # La fecha puede estar en la misma línea o en la siguiente
    FECHA_CORTE_PATTERN = re.compile(r"Fecha de corte:\s*(\d{2}/\w{3}/\d{2})")
    FECHA_CORTE_PATTERN_ALT = re.compile(r"^(\d{2}/[A-Z]{3}/\d{2})$", re.MULTILINE)
    NOMBRE_PATTERN = re.compile(r"^([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+)$", re.MULTILINE)
    EMAIL_PATTERN = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
    IBAN_PATTERN = re.compile(r"Cuenta IBAN:\s*(CR\d{2}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{2})")
    MONEDA_PATTERN = re.compile(r"Moneda:\s*(COLONES|DOLARES)")

    # Patrón para líneas de transacción
    # Formato: REFERENCIA  FECHA  CONCEPTO  [DEBITO]  [CREDITO]
    TRANSACTION_PATTERN = re.compile(
        r"^(\d{9})\s+"  # Referencia (9 dígitos)
        r"(\w{3}/\d{2})\s+"  # Fecha (MES/DÍA)
        r"(.+?)\s+"  # Concepto
        r"([\d,]+\.\d{2})?\s*"  # Débito (opcional)
        r"([\d,]+\.\d{2})?$"  # Crédito (opcional)
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
        self._current_year: int | None = None
        self._current_iban: str | None = None
        self._current_moneda: str = "CRC"

    def parse(self, pdf_path: str | Path) -> BACStatementResult:
        """
        Parsea un estado de cuenta PDF de BAC.

        Args:
            pdf_path: Ruta al archivo PDF

        Returns:
            BACStatementResult con metadata, transacciones y errores
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

        logger.info(f"Parseando PDF: {pdf_path.name}")

        transactions: list[BACTransaction] = []
        errors: list[str] = []
        metadata: BACStatementMetadata | None = None

        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Extraer metadata de la primera página
                first_page_text = pdf.pages[0].extract_text() or ""
                metadata = self._extract_metadata(first_page_text)

                # Extraer año del corte para construir fechas completas
                self._current_year = metadata.fecha_corte.year

                # Procesar todas las páginas usando extracción por posición
                for i, page in enumerate(pdf.pages):
                    # Primero extraer contexto (IBAN, moneda) del texto
                    page_text = page.extract_text() or ""
                    self._update_context_from_text(page_text)

                    # Luego extraer transacciones usando posiciones de caracteres
                    page_txns = self._extract_transactions_by_position(page, i + 1)
                    transactions.extend(page_txns)

                logger.info(
                    f"✅ Extraídas {len(transactions)} transacciones de {len(pdf.pages)} páginas"
                )

                return BACStatementResult(
                    metadata=metadata,
                    transactions=transactions,
                    source_file=str(pdf_path),
                    pages_processed=len(pdf.pages),
                    errors=errors,
                )

        except Exception as e:
            logger.error(f"Error parseando PDF {pdf_path}: {e}")
            raise

    def _update_context_from_text(self, text: str) -> None:
        """Actualiza contexto (IBAN, moneda) del texto de la página."""
        # Detectar cambio de cuenta/moneda
        if iban_match := self.IBAN_PATTERN.search(text):
            self._current_iban = iban_match.group(1).replace(" ", "")

        if moneda_match := self.MONEDA_PATTERN.search(text):
            moneda_raw = moneda_match.group(1)
            self._current_moneda = "USD" if "DOLAR" in moneda_raw.upper() else "CRC"

    def _extract_transactions_by_position(self, page: Any, page_num: int) -> list[BACTransaction]:
        """
        Extrae transacciones usando posiciones de caracteres para detectar columnas.

        El PDF tiene columnas fijas:
        - Referencia: x ~50-90
        - Fecha: x ~140-175
        - Concepto: x ~190-480
        - Débitos: x ~480-550
        - Créditos: x >550
        """
        transactions: list[BACTransaction] = []
        chars = page.chars

        if not chars:
            return transactions

        # Agrupar caracteres por línea (posición Y)
        lines_by_y: dict[int, list[dict]] = {}
        for char in chars:
            y_key = int(char["top"])
            if y_key not in lines_by_y:
                lines_by_y[y_key] = []
            lines_by_y[y_key].append(char)

        # Procesar cada línea
        for y in sorted(lines_by_y.keys()):
            line_chars = sorted(lines_by_y[y], key=lambda c: c["x0"])
            txn = self._parse_line_by_position(line_chars)
            if txn:
                transactions.append(txn)

        return transactions

    def _parse_line_by_position(self, chars: list[dict]) -> BACTransaction | None:
        """Parsea una línea de caracteres en una transacción usando posiciones."""
        if not chars:
            return None

        # Reconstruir texto por zonas de columna
        referencia_chars = []
        fecha_chars = []
        concepto_chars = []
        monto_debito_chars = []
        monto_credito_chars = []

        for c in chars:
            x = c["x0"]
            text = c["text"]

            if x < COL_FECHA_START:
                referencia_chars.append(text)
            elif x < COL_CONCEPTO_START:
                fecha_chars.append(text)
            elif x < COL_DEBITO_START:
                concepto_chars.append(text)
            elif x < COL_CREDITO_THRESHOLD:
                monto_debito_chars.append(text)
            else:
                monto_credito_chars.append(text)

        referencia = "".join(referencia_chars).strip()
        fecha_str = "".join(fecha_chars).strip()
        concepto = "".join(concepto_chars).strip()
        monto_debito_str = "".join(monto_debito_chars).strip()
        monto_credito_str = "".join(monto_credito_chars).strip()

        # Validar que sea una transacción (referencia de 9 dígitos)
        if not re.match(r"^\d{9}$", referencia):
            return None

        # Validar fecha (formato MES/DIA)
        if not re.match(r"^[A-Z]{3}/\d{2}$", fecha_str):
            return None

        fecha = self._parse_fecha_transaccion(fecha_str)
        if not fecha:
            return None

        # Parsear montos
        monto_debito = self._parse_monto(monto_debito_str) if monto_debito_str else Decimal(0)
        monto_credito = self._parse_monto(monto_credito_str) if monto_credito_str else Decimal(0)

        # Determinar tipo y monto
        if monto_debito > 0 and monto_credito == 0:
            monto = monto_debito
            tipo = "debito"
        elif monto_credito > 0 and monto_debito == 0:
            monto = monto_credito
            tipo = "credito"
        elif monto_debito > 0 and monto_credito > 0:
            # Raro: ambas columnas tienen valor - usar la mayor
            if monto_debito >= monto_credito:
                monto = monto_debito
                tipo = "debito"
            else:
                monto = monto_credito
                tipo = "credito"
        else:
            return None

        if monto <= 0:
            return None

        return self._create_transaction(
            referencia=referencia,
            fecha=fecha,
            concepto=concepto,
            monto=monto,
            tipo=tipo,
        )

    def _extract_metadata(self, text: str) -> BACStatementMetadata:
        """Extrae metadata del encabezado del estado de cuenta."""
        # Fecha de corte - puede estar en la misma línea o en línea separada
        fecha_corte = date.today()
        if match := self.FECHA_CORTE_PATTERN.search(text):
            fecha_corte = self._parse_fecha_corte(match.group(1))
        elif match := self.FECHA_CORTE_PATTERN_ALT.search(text):
            # Formato alternativo: fecha en línea separada después de "Fecha de corte:"
            fecha_corte = self._parse_fecha_corte(match.group(1))

        # Nombre del titular (primera línea en mayúsculas después de la fecha)
        nombre = "Desconocido"
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            # Buscar nombre (línea en mayúsculas con al menos 2 palabras)
            if (
                line
                and line.isupper()
                and len(line.split()) >= 2
                and not any(x in line for x in ["RESUMEN", "TIPO", "PRODUCTO", "CUENTA", "TOTAL"])
            ):
                nombre = line.title()  # Convertir a Title Case
                break

        # Email
        email = None
        if match := self.EMAIL_PATTERN.search(text):
            email = match.group(1)

        return BACStatementMetadata(
            nombre_titular=nombre,
            fecha_corte=fecha_corte,
            email=email,
        )

    def _parse_fecha_corte(self, fecha_str: str) -> date:
        """Parsea fecha de corte formato '31/OCT/25'."""
        try:
            parts = fecha_str.split("/")
            dia = int(parts[0])
            mes = self.MESES.get(parts[1].upper(), 1)
            año = 2000 + int(parts[2])
            return date(año, mes, dia)
        except (ValueError, IndexError, KeyError):
            logger.warning(f"No se pudo parsear fecha de corte: {fecha_str}")
            return date.today()

    def _extract_transactions_from_page(
        self, text: str, page_num: int
    ) -> tuple[list[BACTransaction], list[str]]:
        """Extrae transacciones de una página."""
        transactions: list[BACTransaction] = []
        errors: list[str] = []

        lines = text.split("\n")

        for i, line in enumerate(lines):
            line = line.strip()

            # Detectar cambio de cuenta/moneda
            if iban_match := self.IBAN_PATTERN.search(line):
                self._current_iban = iban_match.group(1).replace(" ", "")

            if moneda_match := self.MONEDA_PATTERN.search(line):
                moneda_raw = moneda_match.group(1)
                self._current_moneda = "USD" if "DOLAR" in moneda_raw.upper() else "CRC"

            # Intentar parsear como transacción
            txn = self._parse_transaction_line(line)
            if txn:
                transactions.append(txn)

        return transactions, errors

    def _parse_transaction_line(self, line: str) -> BACTransaction | None:
        """
        Intenta parsear una línea como transacción.

        Formato esperado:
        093006688 SEP/27 COMPASS RUTA 32 RUTA 2 150.00
        406495639 OCT/03 TEF DE: 948198684 7,014.00
        """
        # Ignorar líneas que claramente no son transacciones
        if not line or len(line) < 20:
            return None

        skip_patterns = [
            "FECHA",
            "CONCEPTO",
            "DÉBITOS",
            "CRÉDITOS",
            "SERVICIO AL CLIENTE",
            "SALDO",
            "TOTAL",
            "ÚLTIMA",
            "Cuenta IBAN",
            "Moneda:",
            "Tasas",
            "Nombre:",
            "Nomenclatura",
            "CUADRO",
            "https://",
            "Banco BAC",
            "ACTIVA",
            "Marca:",
            "SINPE Móvil",
            "No tiene celulares",
        ]
        if any(skip in line for skip in skip_patterns):
            return None

        # Parsear con regex
        match = self.TRANSACTION_PATTERN.match(line)
        if not match:
            # Intento alternativo: formato más flexible
            return self._parse_transaction_flexible(line)

        referencia = match.group(1)
        fecha_str = match.group(2)
        concepto = match.group(3).strip()
        debito_str = match.group(4)
        credito_str = match.group(5)

        # Parsear fecha
        fecha = self._parse_fecha_transaccion(fecha_str)
        if not fecha:
            return None

        # Determinar monto y tipo
        monto: Decimal
        tipo: str

        if debito_str and not credito_str:
            monto = self._parse_monto(debito_str)
            tipo = "debito"
        elif credito_str and not debito_str:
            monto = self._parse_monto(credito_str)
            tipo = "credito"
        elif debito_str and credito_str:
            # Ambos tienen valor - raro pero posible
            # Usar el que no sea cero
            monto_debito = self._parse_monto(debito_str)
            monto_credito = self._parse_monto(credito_str)
            if monto_debito > 0:
                monto = monto_debito
                tipo = "debito"
            else:
                monto = monto_credito
                tipo = "credito"
        else:
            return None

        if monto <= 0:
            return None

        # Crear transacción
        return self._create_transaction(
            referencia=referencia,
            fecha=fecha,
            concepto=concepto,
            monto=monto,
            tipo=tipo,
        )

    def _parse_transaction_flexible(self, line: str) -> BACTransaction | None:
        """Parsing más flexible para líneas que no matchean el regex exacto."""
        # Patrón: empieza con 9 dígitos
        if not re.match(r"^\d{9}\s", line):
            return None

        parts = line.split()
        if len(parts) < 4:
            return None

        referencia = parts[0]

        # Buscar fecha (formato MES/DIA)
        fecha_idx = -1
        for i, part in enumerate(parts[1:], 1):
            if re.match(r"^[A-Z]{3}/\d{2}$", part):
                fecha_idx = i
                break

        if fecha_idx < 0:
            return None

        fecha = self._parse_fecha_transaccion(parts[fecha_idx])
        if not fecha:
            return None

        # El concepto está entre la fecha y los montos
        # Los montos están al final (números con comas y punto)
        montos = []
        concepto_parts = []

        for part in parts[fecha_idx + 1 :]:
            if re.match(r"^[\d,]+\.\d{2}$", part):
                montos.append(part)
            elif not montos:  # Solo agregar al concepto si no hemos visto montos
                concepto_parts.append(part)

        if not concepto_parts or not montos:
            return None

        concepto = " ".join(concepto_parts)
        monto = self._parse_monto(montos[0])

        # Determinar tipo basado en posición o concepto
        tipo = self._inferir_tipo(concepto, len(montos))

        if monto <= 0:
            return None

        return self._create_transaction(
            referencia=referencia,
            fecha=fecha,
            concepto=concepto,
            monto=monto,
            tipo=tipo,
        )

    def _inferir_tipo(self, concepto: str, num_montos: int) -> str:
        """Infiere si es débito o crédito basado en el concepto."""
        concepto_upper = concepto.upper()

        # Créditos típicos
        creditos = ["TEF DE:", "SINPE MOVIL", "DTR SINPE", "DEPOSITO", "INTERESES"]
        if any(c in concepto_upper for c in creditos):
            # SINPE MOVIL puede ser envío o recepción
            if "TEF DE:" in concepto_upper:
                return "credito"
            # Los intereses son créditos
            if "INTERESES" in concepto_upper:
                return "credito"

        # Débitos típicos
        debitos = ["TEF A :", "COMPASS", "COMPRA", "PAGO", "COBRO", "RETIRO"]
        if any(d in concepto_upper for d in debitos):
            return "debito"

        # Default: si hay solo un monto, probablemente es débito
        return "debito"

    def _create_transaction(
        self,
        referencia: str,
        fecha: date,
        concepto: str,
        monto: Decimal,
        tipo: str,
    ) -> BACTransaction:
        """Crea una transacción con campos derivados."""
        concepto_upper = concepto.upper()

        # Detectar tipos especiales
        es_transferencia = "TEF " in concepto_upper
        es_sinpe = "SINPE" in concepto_upper
        es_interes = "INTERES" in concepto_upper

        # Normalizar comercio
        comercio_normalizado = self._normalizar_comercio(concepto)

        return BACTransaction(
            referencia=referencia,
            fecha=fecha,
            concepto=concepto,
            monto=monto,
            tipo=tipo,
            cuenta_iban=self._current_iban or "",
            moneda=self._current_moneda,
            comercio_normalizado=comercio_normalizado,
            es_transferencia=es_transferencia,
            es_sinpe=es_sinpe,
            es_interes=es_interes,
        )

    def _normalizar_comercio(self, concepto: str) -> str:
        """Normaliza el nombre del comercio para mejor categorización."""
        # Remover prefijos comunes
        concepto = re.sub(r"^(TEF DE:|TEF A :)\s*", "", concepto)
        concepto = re.sub(r"^(DTR SINPE|SINPE MOVIL)\s*", "SINPE ", concepto)

        # Mapeo de comercios conocidos
        normalizaciones = {
            "COMPASS": "Peajes Compass",
            "UBER": "Uber",
            "UBER EATS": "Uber Eats",
            "MCDONALDS": "McDonald's",
            "WALMART": "Walmart",
            "AUTOMERCADO": "Auto Mercado",
            "PRICESMART": "PriceSmart",
            "ROBERT BOSCH SERVICE SOLUTIONS": "Bosch (Salario)",
        }

        concepto_upper = concepto.upper()
        for key, value in normalizaciones.items():
            if key in concepto_upper:
                return value

        return concepto.strip()

    def _parse_fecha_transaccion(self, fecha_str: str) -> date | None:
        """Parsea fecha de transacción formato 'MES/DIA'."""
        try:
            parts = fecha_str.split("/")
            mes = self.MESES.get(parts[0].upper())
            if not mes:
                return None
            dia = int(parts[1])
            año = self._current_year or date.today().year

            # Ajustar año si el mes es mayor que el mes de corte
            # (transacciones de diciembre en estado de enero)
            return date(año, mes, dia)
        except (ValueError, IndexError):
            return None

    def _parse_monto(self, monto_str: str) -> Decimal:
        """Parsea string de monto a Decimal."""
        try:
            # Remover comas de miles
            clean = monto_str.replace(",", "")
            return Decimal(clean)
        except (InvalidOperation, ValueError):
            return Decimal("0")

    def parse_directory(self, directory: str | Path) -> list[BACStatementResult]:
        """
        Parsea todos los PDFs en un directorio.

        Args:
            directory: Ruta al directorio con PDFs

        Returns:
            Lista de resultados de parsing
        """
        directory = Path(directory)
        results = []

        pdf_files = sorted(directory.glob("*.pdf"))
        logger.info(f"Encontrados {len(pdf_files)} PDFs en {directory}")

        for pdf_file in pdf_files:
            try:
                result = self.parse(pdf_file)
                results.append(result)
            except Exception as e:
                logger.error(f"Error procesando {pdf_file.name}: {e}")
                results.append(
                    BACStatementResult(
                        metadata=BACStatementMetadata(
                            nombre_titular="Error",
                            fecha_corte=date.today(),
                        ),
                        transactions=[],
                        source_file=str(pdf_file),
                        pages_processed=0,
                        errors=[str(e)],
                    )
                )

        total_txns = sum(len(r.transactions) for r in results)
        logger.info(f"✅ Total: {total_txns} transacciones de {len(results)} archivos")

        return results
