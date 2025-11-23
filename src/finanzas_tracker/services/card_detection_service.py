"""Servicio de auto-detección de tarjetas desde correos bancarios."""

import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.card import Card
from finanzas_tracker.models.enums import BankName, CardType
from finanzas_tracker.parsers.bac_parser import BACParser
from finanzas_tracker.parsers.popular_parser import PopularParser
from finanzas_tracker.services.email_fetcher import EmailFetcher

logger = get_logger(__name__)


class CardDetectionService:
    """
    Servicio de Auto-Detección de Tarjetas.

    Escanea correos bancarios de los últimos días y detecta automáticamente:
    - Números de tarjeta únicos (últimos 4 dígitos)
    - Banco asociado (BAC, Popular)
    - Tipo de tarjeta (débito/crédito) basado en patrones
    - Frecuencia de uso

    Perfecto para el onboarding wizard.
    """

    def __init__(self) -> None:
        """Inicializa el servicio de detección."""
        self.email_fetcher = EmailFetcher()
        self.bac_parser = BACParser()
        self.popular_parser = PopularParser()
        logger.info("CardDetectionService inicializado")

    def detect_cards_from_emails(
        self,
        email_address: str,
        days_back: int = 30,
    ) -> list[dict[str, Any]]:
        """
        Detecta tarjetas automáticamente desde correos.

        Args:
            email_address: Email de Outlook donde buscar correos
            days_back: Días hacia atrás para buscar (default: 30)

        Returns:
            Lista de tarjetas detectadas con información:
            - last_digits: Últimos 4 dígitos
            - banco: BankName (bac/popular)
            - tipo_sugerido: CardType (débito/crédito)
            - confidence: Nivel de confianza de la sugerencia (0-100)
            - transaction_count: Número de transacciones encontradas
            - first_seen: Primera vez que se vio
            - last_seen: Última vez que se vio
            - sample_merchants: Ejemplos de comercios
        """
        logger.info(
            f"🔍 Iniciando auto-detección de tarjetas para {email_address} "
            f"(últimos {days_back} días)"
        )

        # Obtener correos bancarios
        emails = self._fetch_bank_emails(email_address, days_back)

        if not emails:
            logger.info("No se encontraron correos bancarios")
            return []

        # Detectar tarjetas desde correos
        detected_cards = self._analyze_emails_for_cards(emails)

        logger.info(
            f"✅ Detección completa: {len(detected_cards)} tarjeta(s) detectada(s)"
        )

        return detected_cards

    def _fetch_bank_emails(
        self, email_address: str, days_back: int
    ) -> list[dict[str, Any]]:
        """Obtiene correos bancarios de los últimos días."""
        try:
            # Construir filtro de fechas
            start_date = datetime.now(UTC) - timedelta(days=days_back)

            # Buscar correos de BAC
            bac_emails = self.email_fetcher.fetch_emails(
                user_email=email_address,
                days_back=days_back,
                sender_filter="notificaciones@baccredomatic.com",
            )

            # Buscar correos de Popular
            popular_emails = self.email_fetcher.fetch_emails(
                user_email=email_address,
                days_back=days_back,
                sender_filter="notificaciones@bancopopular.fi.cr",
            )

            all_emails = bac_emails + popular_emails

            logger.info(
                f"📧 Correos obtenidos: {len(bac_emails)} BAC + "
                f"{len(popular_emails)} Popular = {len(all_emails)} total"
            )

            return all_emails

        except Exception as e:
            logger.error(f"Error al obtener correos: {e}")
            return []

    def _analyze_emails_for_cards(self, emails: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Analiza correos y extrae información de tarjetas."""
        # Diccionario para agrupar por tarjeta
        card_data: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "transaction_count": 0,
                "merchants": [],
                "first_seen": None,
                "last_seen": None,
                "debit_indicators": 0,
                "credit_indicators": 0,
            }
        )

        for email in emails:
            try:
                # Determinar parser según sender
                sender = email.get("sender", "").lower()
                parser = None
                banco = None

                if "baccredomatic" in sender:
                    parser = self.bac_parser
                    banco = BankName.BAC
                elif "bancopopular" in sender:
                    parser = self.popular_parser
                    banco = BankName.POPULAR
                else:
                    continue

                # Parsear transacción
                parsed = parser.parse(email)

                if not parsed or not parsed.tarjeta:
                    continue

                # Extraer últimos 4 dígitos
                last_digits = self._extract_last_digits(parsed.tarjeta)

                if not last_digits:
                    continue

                # Clave única: banco + últimos 4 dígitos
                card_key = f"{banco.value}_{last_digits}"

                # Agregar información
                card_data[card_key]["transaction_count"] += 1
                card_data[card_key]["banco"] = banco
                card_data[card_key]["last_digits"] = last_digits

                # Agregar comercio (máximo 5 ejemplos)
                if len(card_data[card_key]["merchants"]) < 5 and parsed.comercio:
                    if parsed.comercio not in card_data[card_key]["merchants"]:
                        card_data[card_key]["merchants"].append(parsed.comercio)

                # Fechas
                fecha = parsed.fecha or datetime.now(UTC)
                if (
                    not card_data[card_key]["first_seen"]
                    or fecha < card_data[card_key]["first_seen"]
                ):
                    card_data[card_key]["first_seen"] = fecha

                if (
                    not card_data[card_key]["last_seen"]
                    or fecha > card_data[card_key]["last_seen"]
                ):
                    card_data[card_key]["last_seen"] = fecha

                # Indicadores de tipo de tarjeta
                self._analyze_card_type_indicators(parsed, card_data[card_key])

            except Exception as e:
                logger.warning(f"Error al procesar correo: {e}")
                continue

        # Convertir a lista y sugerir tipo de tarjeta
        detected_cards = []
        for card_key, data in card_data.items():
            tipo_sugerido, confidence = self._suggest_card_type(data)

            detected_cards.append(
                {
                    "last_digits": data["last_digits"],
                    "banco": data["banco"],
                    "tipo_sugerido": tipo_sugerido,
                    "confidence": confidence,
                    "transaction_count": data["transaction_count"],
                    "first_seen": data["first_seen"].isoformat() if data["first_seen"] else None,
                    "last_seen": data["last_seen"].isoformat() if data["last_seen"] else None,
                    "sample_merchants": data["merchants"],
                }
            )

        # Ordenar por más usado
        detected_cards.sort(key=lambda x: x["transaction_count"], reverse=True)

        return detected_cards

    def _extract_last_digits(self, tarjeta_str: str) -> str | None:
        """Extrae los últimos 4 dígitos de una tarjeta."""
        # Buscar cualquier secuencia de 4 dígitos
        matches = re.findall(r"\d{4}", tarjeta_str)

        if matches:
            # Usar los últimos 4 dígitos encontrados
            return matches[-1]

        return None

    def _analyze_card_type_indicators(
        self, parsed_transaction: Any, card_data: dict
    ) -> None:
        """Analiza indicadores para determinar tipo de tarjeta."""
        # Indicadores de débito
        debit_keywords = [
            "debito",
            "débito",
            "cuenta",
            "retiro cajero",
            "atm",
            "cash withdrawal",
        ]

        # Indicadores de crédito
        credit_keywords = [
            "credito",
            "crédito",
            "credit",
            "cuotas",
            "diferido",
        ]

        # Analizar en comercio y tipo de transacción
        text = f"{parsed_transaction.comercio} {parsed_transaction.tipo_transaccion}".lower()

        for keyword in debit_keywords:
            if keyword in text:
                card_data["debit_indicators"] += 1

        for keyword in credit_keywords:
            if keyword in text:
                card_data["credit_indicators"] += 1

    def _suggest_card_type(self, card_data: dict) -> tuple[CardType, int]:
        """
        Sugiere tipo de tarjeta basado en indicadores.

        Returns:
            Tuple de (CardType, confidence 0-100)
        """
        debit_count = card_data.get("debit_indicators", 0)
        credit_count = card_data.get("credit_indicators", 0)

        # Si no hay indicadores claros, asumir débito con baja confianza
        if debit_count == 0 and credit_count == 0:
            return CardType.DEBIT, 30

        # Si hay indicadores
        total = debit_count + credit_count

        if debit_count > credit_count:
            confidence = int((debit_count / total) * 100)
            return CardType.DEBIT, min(confidence, 90)
        else:
            confidence = int((credit_count / total) * 100)
            return CardType.CREDIT, min(confidence, 90)

    def create_detected_cards(
        self,
        profile_id: str,
        detected_cards: list[dict[str, Any]],
        user_confirmations: dict[str, dict[str, Any]] | None = None,
    ) -> list[Card]:
        """
        Crea tarjetas en la base de datos desde las detectadas.

        Args:
            profile_id: ID del perfil
            detected_cards: Lista de tarjetas detectadas
            user_confirmations: Dict con confirmaciones/ediciones del usuario
                Format: {last_digits: {"tipo": CardType, "label": str}}

        Returns:
            Lista de tarjetas creadas
        """
        created_cards = []

        with get_session() as session:
            for detected in detected_cards:
                last_digits = detected["last_digits"]

                # Verificar si ya existe
                existing = (
                    session.query(Card)
                    .filter(
                        Card.profile_id == profile_id,
                        Card.banco == detected["banco"],
                        Card.ultimos_digitos == last_digits,
                    )
                    .first()
                )

                if existing:
                    logger.info(
                        f"Tarjeta ya existe: {detected['banco'].value} {last_digits}"
                    )
                    continue

                # Obtener confirmación del usuario o usar sugerencia
                if user_confirmations and last_digits in user_confirmations:
                    card_type = user_confirmations[last_digits].get(
                        "tipo", detected["tipo_sugerido"]
                    )
                    label = user_confirmations[last_digits].get("label")
                else:
                    card_type = detected["tipo_sugerido"]
                    label = None

                # Crear tarjeta
                card = Card(
                    profile_id=profile_id,
                    banco=detected["banco"],
                    tipo=card_type,
                    ultimos_digitos=last_digits,
                    etiqueta=label,
                    activa=True,
                )

                session.add(card)
                created_cards.append(card)

                logger.info(
                    f"✅ Tarjeta creada: {detected['banco'].value} {last_digits} "
                    f"({card_type.value})"
                )

            session.commit()

        return created_cards


# Singleton instance
card_detection_service = CardDetectionService()
