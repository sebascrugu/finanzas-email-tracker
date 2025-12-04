"""Parser de correos de BAC Credomatic."""

from datetime import datetime
import re
import unicodedata
from typing import Any

from bs4 import BeautifulSoup

from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.parsers.base_parser import BaseParser, ParsedTransaction
from finanzas_tracker.utils.parser_utils import ParserUtils


logger = get_logger(__name__)


def normalize_text(text: str) -> str:
    """Normaliza texto Unicode a forma NFC para comparaciones consistentes."""
    return unicodedata.normalize("NFC", text)


class BACParser(BaseParser):
    """
    Parser para correos de BAC Credomatic.

    Extrae información de transacciones desde correos HTML de BAC.
    """

    @property
    def bank_name(self) -> str:
        return "bac"

    def _handle_special_format(
        self, soup: BeautifulSoup, email_data: dict[str, Any]
    ) -> ParsedTransaction | str | None:
        """Maneja formatos especiales: retiro sin tarjeta, transferencias, pagos."""
        # Normalizar subject para manejar diferentes formas de Unicode (NFC vs NFD)
        subject = normalize_text(email_data.get("subject", "").lower())
        text = normalize_text(soup.get_text(separator=" ", strip=True).lower())
        
        # PRIMERO: Skip avisos de configuración silenciosamente (no son transacciones)
        # Esto DEBE ir primero para evitar falsos positivos con "transferencia" en el subject
        config_keywords = [
            "aviso bac", "activación", "activacion",
            "afiliación sinpe", "desafiliación sinpe",
            "afiliacion sinpe", "desafiliacion sinpe",
            "afiliación", "afiliacion", "desafiliación", "desafiliacion",
            "cambio de pin", "cambio de clave",
        ]
        if any(kw in subject for kw in config_keywords):
            logger.info(f"Aviso de configuración ignorado: {email_data.get('subject', '')[:50]}")
            return "SKIP"
        
        # Retiro sin tarjeta
        if "retiro sin tarjeta" in subject:
            return self._parse_retiro_sin_tarjeta(soup, email_data)
        
        # Pago de tarjeta de crédito
        if "notificación de pago" in subject or "comprobante de pago" in text:
            return self._parse_pago_tarjeta(soup, email_data)
        
        # Transferencia SINPE recibida (ingreso)
        if "sinpe" in subject and "recibió una transferencia" in text:
            return self._parse_transferencia_sinpe_recibida(soup, email_data)
        
        # Transferencia enviada (gasto)
        if "transferencia" in subject and "realizó una transferencia" in text:
            return self._parse_transferencia(soup, email_data)
        
        return None

    def _extract_comercio(self, soup: BeautifulSoup, subject: str) -> str:
        """Extrae el nombre del comercio del correo."""
        # Intentar desde la tabla HTML
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True)
                if "Comercio" in label:
                    return cells[1].get_text(strip=True)

        # Fallback: extraer del asunto
        match = re.search(r"Notificación de transacción\s+(.+?)\s+\d{2}-\d{2}-\d{4}", subject)
        if match:
            return match.group(1).strip()

        return "Desconocido"

    def _extract_ubicacion(self, soup: BeautifulSoup) -> str:
        """Extrae ciudad y país del correo."""
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True)
                if "Ciudad y país" in label or "Ciudad y pa" in label:
                    return cells[1].get_text(strip=True)
        return ""

    def _extract_fecha(self, soup: BeautifulSoup, email_data: dict[str, Any]) -> datetime:
        """
        Extrae la fecha de la transacción.

        Intenta primero desde el HTML, luego usa la fecha del correo.
        """
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True)
                if "Fecha:" in label:
                    fecha_str = cells[1].get_text(strip=True)
                    try:
                        return datetime.strptime(fecha_str, "%b %d, %Y, %H:%M")
                    except ValueError:
                        pass

        return self._get_email_date_fallback(email_data)

    def _extract_tipo_transaccion(self, soup: BeautifulSoup, subject: str) -> str:
        """Extrae el tipo de transacción."""
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True)
                if "Tipo de Transacción" in label or "Tipo de Transacci" in label:
                    return cells[1].get_text(strip=True)
        return "compra"

    def _extract_monto(self, soup: BeautifulSoup) -> str | None:
        """Extrae el monto de la transacción."""
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                label_text = cells[0].get_text(strip=True)
                if "Monto" in label_text or "monto" in label_text:
                    monto_text = cells[1].get_text(strip=True)
                    if monto_text:
                        return monto_text
        return None

    def _parse_retiro_sin_tarjeta(
        self,
        soup: BeautifulSoup,
        email_data: dict[str, Any],
    ) -> ParsedTransaction | None:
        """
        Parsea correos de retiro sin tarjeta (formato diferente).

        Args:
            soup: BeautifulSoup del HTML
            email_data: Datos del correo

        Returns:
            ParsedTransaction | None: Datos de la transacción o None
        """
        text = soup.get_text()

        # Extraer monto (formato: "Monto: 50,000.00 CRC")
        monto_match = re.search(r"Monto:\s*([\d,]+\.?\d*)\s*(CRC|USD)", text)
        if not monto_match:
            logger.warning("No se pudo extraer monto de retiro sin tarjeta")
            return None

        monto_str = monto_match.group(0)
        moneda, monto = ParserUtils.parse_monto(monto_str)

        # Validar
        validation_error = self._validate_transaction(monto, moneda, "retiro sin tarjeta")
        if validation_error:
            logger.warning(validation_error)
            return None

        # Extraer fecha
        fecha = self._extract_fecha_retiro(text, email_data)

        # Extraer lugar
        comercio, ciudad = self._extract_lugar_retiro(text)

        return {
            "email_id": email_data.get("id", ""),
            "banco": self.bank_name,
            "comercio": comercio,
            "monto_original": monto,
            "moneda_original": moneda,
            "tipo_transaccion": "retiro",
            "fecha_transaccion": fecha,
            "ciudad": ciudad,
            "pais": "Costa Rica",
        }

    def _extract_fecha_retiro(self, text: str, email_data: dict[str, Any]) -> datetime:
        """Extrae fecha de un correo de retiro sin tarjeta."""
        fecha_match = re.search(r"(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}:\d{2})", text)
        if fecha_match:
            fecha_str = f"{fecha_match.group(1)} {fecha_match.group(2)}"
            try:
                return datetime.strptime(fecha_str, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                pass
        return self._get_email_date_fallback(email_data)

    def _extract_lugar_retiro(self, text: str) -> tuple[str, str | None]:
        """
        Extrae lugar de retiro sin tarjeta.

        Returns:
            Tuple de (comercio, ciudad)
        """
        lugar_match = re.search(r"Lugar donde se retir[oó] el dinero:\s*([^\n]+)", text)
        comercio = "RETIRO SIN TARJETA"
        ciudad = None

        if lugar_match:
            lugar = lugar_match.group(1).strip()
            comercio = f"RETIRO SIN TARJETA - {lugar}"

            # Mapeo de lugares conocidos a ciudades
            city_mappings = {
                "TRES RIOS": "Tres Rios",
                "SAN JOSE": "San Jose",
                "HEREDIA": "Heredia",
                "CARTAGO": "Cartago",
                "ALAJUELA": "Alajuela",
            }
            lugar_upper = lugar.upper()
            for key, city in city_mappings.items():
                if key in lugar_upper:
                    ciudad = city
                    break

        return comercio, ciudad

    def _parse_transferencia(
        self,
        soup: BeautifulSoup,
        email_data: dict[str, Any],
    ) -> ParsedTransaction | None:
        """
        Parsea correos de transferencia local (SINPE y otras transferencias).

        Formato esperado:
            Estimado(a) {DESTINATARIO}:
            BAC Credomatic le comunica que {REMITENTE} realizó una transferencia
            electrónica a su cuenta N° *****{ULTIMOS_DIGITOS}.
            La transferencia se realizó el día {DD-MM-YYYY} a las {HH:MM:SS} horas;
            por un monto de {MONTO} CRC, por concepto de: {CONCEPTO}
            El número de referencia es {REFERENCIA}

        Args:
            soup: BeautifulSoup del HTML
            email_data: Datos del correo

        Returns:
            ParsedTransaction | None: Datos de la transacción o None
        """
        text = soup.get_text(separator=" ", strip=True)

        # Extraer monto (formato: "5.000,00 CRC" o "700.000,00 CRC")
        # El formato costarricense usa punto para miles y coma para decimales
        monto_match = re.search(
            r"monto de\s*([\d.,]+)\s*(CRC|USD)",
            text,
            re.IGNORECASE,
        )
        if not monto_match:
            logger.warning("No se pudo extraer monto de transferencia")
            return None

        monto_str = monto_match.group(1)
        moneda = monto_match.group(2).upper()

        # Convertir formato costarricense a número
        # "5.000,00" -> 5000.00
        # "700.000,00" -> 700000.00
        monto_clean = monto_str.replace(".", "").replace(",", ".")
        try:
            monto = float(monto_clean)
        except ValueError:
            logger.warning(f"No se pudo convertir monto: {monto_str}")
            return None

        # Validar
        validation_error = self._validate_transaction(monto, moneda, "transferencia")
        if validation_error:
            logger.warning(validation_error)
            return None

        # Extraer fecha (formato: "DD-MM-YYYY")
        fecha = self._extract_fecha_transferencia(text, email_data)

        # Extraer destinatario
        destinatario = self._extract_destinatario_transferencia(text)

        # Extraer concepto
        concepto = self._extract_concepto_transferencia(text)

        # Extraer referencia
        referencia = self._extract_referencia_transferencia(text)

        # Construir descripción del comercio
        comercio = self._build_comercio_transferencia(destinatario, concepto)

        return {
            "email_id": email_data.get("id", ""),
            "banco": self.bank_name,
            "comercio": comercio,
            "monto_original": monto,
            "moneda_original": moneda,
            "tipo_transaccion": "transferencia",
            "fecha_transaccion": fecha,
            "ciudad": None,
            "pais": "Costa Rica",
            "metadata": {
                "destinatario": destinatario,
                "concepto": concepto,
                "referencia": referencia,
            },
        }

    def _extract_fecha_transferencia(
        self, text: str, email_data: dict[str, Any]
    ) -> datetime:
        """Extrae fecha de una transferencia."""
        # Buscar patrón: "el día DD-MM-YYYY a las HH:MM:SS"
        fecha_match = re.search(
            r"el d[ií]a\s*(\d{2}-\d{2}-\d{4})\s*a las\s*(\d{2}:\d{2}:\d{2})",
            text,
            re.IGNORECASE,
        )
        if fecha_match:
            fecha_str = f"{fecha_match.group(1)} {fecha_match.group(2)}"
            try:
                return datetime.strptime(fecha_str, "%d-%m-%Y %H:%M:%S")
            except ValueError:
                pass
        return self._get_email_date_fallback(email_data)

    def _extract_destinatario_transferencia(self, text: str) -> str:
        """Extrae el nombre del destinatario de una transferencia."""
        # Buscar patrón: "Estimado(a) NOMBRE :"
        match = re.search(
            r"Estimado\(a\)\s+([A-Z_\s]+)\s*:",
            text,
            re.IGNORECASE,
        )
        if match:
            nombre = match.group(1).strip()
            # Limpiar underscores (SINPE usa _ en lugar de espacios)
            return nombre.replace("_", " ").strip()
        return "Destinatario desconocido"

    def _extract_concepto_transferencia(self, text: str) -> str:
        """Extrae el concepto/descripción de una transferencia."""
        # Buscar patrón: "por concepto de: CONCEPTO"
        match = re.search(
            r"por concepto de:\s*([^\n]+?)(?:\s*El n[uú]mero|\s*Muchas|\s*$)",
            text,
            re.IGNORECASE,
        )
        if match:
            concepto = match.group(1).strip()
            # Limpiar underscores
            concepto = concepto.replace("_", " ").strip()
            if concepto.lower() in ["sin descripcion", "sin descripción", ""]:
                return ""
            return concepto
        return ""

    def _extract_referencia_transferencia(self, text: str) -> str:
        """Extrae el número de referencia de una transferencia."""
        match = re.search(
            r"n[uú]mero de referencia es\s*(\d+)",
            text,
            re.IGNORECASE,
        )
        if match:
            return match.group(1)
        return ""

    def _build_comercio_transferencia(
        self, destinatario: str, concepto: str
    ) -> str:
        """Construye la descripción del comercio para una transferencia."""
        if concepto:
            return f"TRANSFERENCIA A {destinatario} - {concepto}"
        return f"TRANSFERENCIA A {destinatario}"

    def _parse_transferencia_sinpe_recibida(
        self,
        soup: BeautifulSoup,
        email_data: dict[str, Any],
    ) -> ParsedTransaction | None:
        """
        Parsea correos de transferencia SINPE recibida (ingresos).

        Formato esperado:
            BAC Credomatic le comunica que recibió una transferencia SINPE 
            con el número de referencia XXXX a su cuenta IBAN XXXX 
            por un monto de X,XXX.XX Colones por concepto XXXX, 
            la cual se aplicó correctamente el día DD/MM/YYYY a las HH:MM PM.

        Args:
            soup: BeautifulSoup del HTML
            email_data: Datos del correo

        Returns:
            ParsedTransaction | None: Datos de la transacción o None
        """
        text = soup.get_text(separator=" ", strip=True)

        # Extraer monto (formato: "4,000.00 Colones")
        monto_match = re.search(
            r"monto de\s*([\d,]+\.?\d*)\s*(Colones|CRC|Dólares|USD)",
            text,
            re.IGNORECASE,
        )
        if not monto_match:
            logger.warning("No se pudo extraer monto de SINPE recibido")
            return None

        monto_str = monto_match.group(1)
        moneda_raw = monto_match.group(2)
        
        # Normalizar moneda
        moneda = "CRC" if moneda_raw.lower() in ["colones", "crc"] else "USD"

        # Convertir formato (usa comas para miles, punto para decimales)
        monto_clean = monto_str.replace(",", "")
        try:
            monto = float(monto_clean)
        except ValueError:
            logger.warning(f"No se pudo convertir monto SINPE: {monto_str}")
            return None

        # Validar
        validation_error = self._validate_transaction(monto, moneda, "sinpe_recibido")
        if validation_error:
            logger.warning(validation_error)
            return None

        # Extraer fecha (formato: "DD/MM/YYYY a las HH:MM PM")
        fecha = self._extract_fecha_sinpe_recibido(text, email_data)

        # Extraer concepto
        concepto = self._extract_concepto_sinpe_recibido(text)

        # Extraer referencia
        referencia = self._extract_referencia_sinpe_recibido(text)

        # Construir descripción del comercio
        comercio = f"SINPE RECIBIDO - {concepto}" if concepto else "SINPE RECIBIDO"

        return {
            "email_id": email_data.get("id", ""),
            "banco": self.bank_name,
            "comercio": comercio,
            "monto_original": monto,
            "moneda_original": moneda,
            "tipo_transaccion": "ingreso",  # Esto es un INGRESO, no un gasto
            "fecha_transaccion": fecha,
            "ciudad": None,
            "pais": "Costa Rica",
            "metadata": {
                "tipo": "sinpe_recibido",
                "concepto": concepto,
                "referencia": referencia,
            },
        }

    def _extract_fecha_sinpe_recibido(
        self, text: str, email_data: dict[str, Any]
    ) -> datetime:
        """Extrae fecha de un SINPE recibido."""
        # Buscar patrón: "el día DD/MM/YYYY a las HH:MM PM"
        fecha_match = re.search(
            r"el d[ií]a\s*(\d{2}/\d{2}/\d{4})\s*a las\s*(\d{1,2}:\d{2})\s*(AM|PM)?",
            text,
            re.IGNORECASE,
        )
        if fecha_match:
            fecha_str = fecha_match.group(1)
            hora_str = fecha_match.group(2)
            am_pm = fecha_match.group(3)
            
            try:
                fecha = datetime.strptime(fecha_str, "%d/%m/%Y")
                hora_parts = hora_str.split(":")
                hora = int(hora_parts[0])
                minutos = int(hora_parts[1])
                
                # Ajustar por AM/PM
                if am_pm and am_pm.upper() == "PM" and hora < 12:
                    hora += 12
                elif am_pm and am_pm.upper() == "AM" and hora == 12:
                    hora = 0
                
                return fecha.replace(hour=hora, minute=minutos)
            except ValueError:
                pass
        return self._get_email_date_fallback(email_data)

    def _extract_concepto_sinpe_recibido(self, text: str) -> str:
        """Extrae el concepto de un SINPE recibido."""
        # Buscar patrón: "por concepto XXXX, la cual"
        match = re.search(
            r"por concepto\s+(.+?),?\s*la cual",
            text,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
        return ""

    def _extract_referencia_sinpe_recibido(self, text: str) -> str:
        """Extrae el número de referencia de un SINPE recibido."""
        match = re.search(
            r"n[uú]mero de referencia\s*(\d+)",
            text,
            re.IGNORECASE,
        )
        if match:
            return match.group(1)
        return ""

    def _parse_pago_tarjeta(
        self,
        soup: BeautifulSoup,
        email_data: dict[str, Any],
    ) -> ParsedTransaction | None:
        """
        Parsea correos de pago de tarjeta de crédito.

        Formato esperado:
            Comprobante de Pago de Tarjeta
            Tarjeta de Crédito
            Número: 3777-13**-****-6386
            Nombre: SEBASTIAN/CRUZ GUZMAN
            Monto del pago: 135,304.74 CRC
            Cuenta Origen
            Número: 966153959
            Nombre: SEBASTIAN ERNESTO CRUZ GUZMAN
            Monto del débito: 135,304.74 CRC
            Tipo de Cambio: 1.00
            Referencia: 4556
            Fecha de pago: 2025/11/28 08:18:46

        NOTA: Este NO es un gasto real, es una transferencia interna
        (de cuenta de débito a tarjeta de crédito). Los gastos reales
        ya fueron registrados cuando se hicieron las compras.

        Args:
            soup: BeautifulSoup del HTML
            email_data: Datos del correo

        Returns:
            ParsedTransaction | None: Datos de la transacción o None
        """
        text = soup.get_text(separator=" ", strip=True)

        # Extraer monto del pago (formato: "135,304.74 CRC")
        monto_match = re.search(
            r"Monto del pago:\s*([\d,]+\.?\d*)\s*(CRC|USD)",
            text,
            re.IGNORECASE,
        )
        if not monto_match:
            # Intentar formato alternativo
            monto_match = re.search(
                r"Monto del d[eé]bito:\s*([\d,]+\.?\d*)\s*(CRC|USD)",
                text,
                re.IGNORECASE,
            )
        
        if not monto_match:
            logger.warning("No se pudo extraer monto de pago de tarjeta")
            return None

        monto_str = monto_match.group(1)
        moneda = monto_match.group(2).upper()

        # Convertir formato (usa comas para miles, punto para decimales)
        monto_clean = monto_str.replace(",", "")
        try:
            monto = float(monto_clean)
        except ValueError:
            logger.warning(f"No se pudo convertir monto pago tarjeta: {monto_str}")
            return None

        # Validar
        validation_error = self._validate_transaction(monto, moneda, "pago_tarjeta")
        if validation_error:
            logger.warning(validation_error)
            return None

        # Extraer fecha (formato: "YYYY/MM/DD HH:MM:SS")
        fecha = self._extract_fecha_pago_tarjeta(text, email_data)

        # Extraer número de tarjeta (últimos 4 dígitos)
        tarjeta = self._extract_tarjeta_pago(text)

        # Extraer referencia
        referencia = self._extract_referencia_pago(text)

        # Construir descripción
        comercio = f"PAGO TARJETA DE CRÉDITO {tarjeta}"

        return {
            "email_id": email_data.get("id", ""),
            "banco": self.bank_name,
            "comercio": comercio,
            "monto_original": monto,
            "moneda_original": moneda,
            "tipo_transaccion": "pago_tarjeta",  # Tipo especial para pagos de TC
            "fecha_transaccion": fecha,
            "ciudad": None,
            "pais": "Costa Rica",
            "metadata": {
                "tipo": "pago_tarjeta_credito",
                "tarjeta": tarjeta,
                "referencia": referencia,
                "nota": "Pago interno de tarjeta de crédito - no es un gasto nuevo",
            },
        }

    def _extract_fecha_pago_tarjeta(
        self, text: str, email_data: dict[str, Any]
    ) -> datetime:
        """Extrae fecha de un pago de tarjeta."""
        # Buscar patrón: "Fecha de pago: YYYY/MM/DD HH:MM:SS"
        fecha_match = re.search(
            r"Fecha de pago:\s*(\d{4}/\d{2}/\d{2})\s+(\d{2}:\d{2}:\d{2})",
            text,
            re.IGNORECASE,
        )
        if fecha_match:
            fecha_str = f"{fecha_match.group(1)} {fecha_match.group(2)}"
            try:
                return datetime.strptime(fecha_str, "%Y/%m/%d %H:%M:%S")
            except ValueError:
                pass
        return self._get_email_date_fallback(email_data)

    def _extract_tarjeta_pago(self, text: str) -> str:
        """Extrae los últimos 4 dígitos de la tarjeta."""
        # Buscar patrón: "3777-13**-****-6386"
        match = re.search(
            r"N[uú]mero:\s*[\d*-]+(\d{4})",
            text,
            re.IGNORECASE,
        )
        if match:
            return f"****{match.group(1)}"
        return ""

    def _extract_referencia_pago(self, text: str) -> str:
        """Extrae la referencia del pago."""
        match = re.search(
            r"Referencia:\s*(\d+)",
            text,
            re.IGNORECASE,
        )
        if match:
            return match.group(1)
        return ""