"""Servicio de normalización de comercios (merchants)."""

from decimal import Decimal
import re

from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.merchant import Merchant, MerchantVariant


logger = get_logger(__name__)


class MerchantNormalizationService:
    """
    Servicio para normalizar nombres de comercios.

    Convierte "SUBWAY MOMENTUM" → Merchant "Subway"
    Crea/actualiza MerchantVariant automáticamente
    """

    # Palabras comunes a remover para normalización
    NOISE_WORDS = [
        "MOMENTUM",
        "AMERICA FREE ZO",
        "SUPERCENTER",
        "ESCAZU",
        "SAN JOSE",
        "HEREDIA",
        "CARTAGO",
        "ALAJUELA",
        "ZONA FRANCA",
        "MALL",
        "PLAZA",
        "CENTRO COMERCIAL",
        "CC",
    ]

    # Patrones para limpieza
    CLEANUP_PATTERNS = [
        r"\s+",  # Múltiples espacios → uno solo
        r"[^\w\s]",  # Caracteres especiales
    ]

    def __init__(self) -> None:
        """Inicializa el servicio."""

    def normalize_merchant_name(self, raw_name: str) -> str:
        """
        Normaliza el nombre del comercio removiendo noise words y limpiando.

        Args:
            raw_name: Nombre como aparece en el correo (ej: "SUBWAY MOMENTUM")

        Returns:
            Nombre normalizado (ej: "Subway")

        Examples:
            >>> service = MerchantNormalizationService()
            >>> service.normalize_merchant_name("SUBWAY MOMENTUM")
            'Subway'
            >>> service.normalize_merchant_name("WALMART SUPERCENTER")
            'Walmart'
        """
        # Convertir a mayúsculas para comparación
        normalized = raw_name.upper().strip()

        # Remover noise words
        for noise in self.NOISE_WORDS:
            normalized = normalized.replace(noise, "")

        # Limpiar caracteres especiales
        for pattern in self.CLEANUP_PATTERNS:
            normalized = re.sub(pattern, " ", normalized)

        # Limpiar espacios extras
        normalized = " ".join(normalized.split())

        # Capitalizar primera letra de cada palabra
        return normalized.title()

    def find_or_create_merchant(
        self,
        session,
        raw_name: str,
        ciudad: str | None = None,
        pais: str = "Costa Rica",
    ) -> Merchant:
        """
        Busca o crea un merchant basado en el nombre raw.

        Args:
            session: Sesión de SQLAlchemy
            raw_name: Nombre como aparece en el correo
            ciudad: Ciudad del comercio
            pais: País del comercio

        Returns:
            Merchant encontrado o creado

        Process:
            1. Busca si existe un MerchantVariant con ese nombre raw → retorna el Merchant
            2. Si no, normaliza el nombre
            3. Busca si existe un Merchant con ese nombre normalizado → retorna
            4. Si no, crea nuevo Merchant + MerchantVariant
        """
        # 1. Buscar por nombre raw exacto
        variant = (
            session.query(MerchantVariant).filter(MerchantVariant.nombre_raw == raw_name).first()
        )

        if variant:
            logger.debug(f"Merchant encontrado por variante: {variant.merchant.nombre_normalizado}")
            return variant.merchant

        # 2. Normalizar nombre
        nombre_normalizado = self.normalize_merchant_name(raw_name)

        # 3. Buscar por nombre normalizado
        merchant = (
            session.query(Merchant)
            .filter(Merchant.nombre_normalizado == nombre_normalizado)
            .first()
        )

        if merchant:
            logger.debug(f"Merchant encontrado por nombre normalizado: {nombre_normalizado}")

            # Crear nueva variante si no existe
            self._create_variant(session, merchant, raw_name, ciudad, pais)

            return merchant

        # 4. Crear nuevo merchant + variante
        logger.info(f"Creando nuevo merchant: {nombre_normalizado} (raw: {raw_name})")

        merchant = Merchant(
            nombre_normalizado=nombre_normalizado,
            categoria_principal="Sin categorizar",
            tipo_negocio="retail",
        )
        session.add(merchant)
        session.flush()  # Para obtener el ID

        # Crear variante
        self._create_variant(session, merchant, raw_name, ciudad, pais)

        return merchant

    def _create_variant(
        self,
        session,
        merchant: Merchant,
        raw_name: str,
        ciudad: str | None,
        pais: str,
    ) -> MerchantVariant:
        """Crea una nueva variante si no existe."""
        # Verificar que no exista ya
        existing = (
            session.query(MerchantVariant).filter(MerchantVariant.nombre_raw == raw_name).first()
        )

        if existing:
            return existing

        variant = MerchantVariant(
            merchant_id=merchant.id,
            nombre_raw=raw_name,
            ciudad=ciudad,
            pais=pais,
            confianza_match=Decimal("1.0"),  # 100% confianza (match exacto)
        )
        session.add(variant)
        session.flush()

        logger.debug(f"Variante creada: {raw_name} → {merchant.nombre_normalizado}")

        return variant

    def update_merchant_metadata(
        self,
        session,
        merchant: Merchant,
        categoria: str | None = None,
        subcategoria: str | None = None,
        tipo_negocio: str | None = None,
        que_vende: str | None = None,
    ) -> None:
        """
        Actualiza metadata de un merchant.

        Útil para enriquecer información después de la creación inicial.
        """
        if categoria:
            merchant.categoria_principal = categoria
        if subcategoria:
            merchant.subcategoria = subcategoria
        if tipo_negocio:
            merchant.tipo_negocio = tipo_negocio
        if que_vende:
            merchant.que_vende = que_vende

        session.flush()
        logger.info(f"Metadata actualizada para: {merchant.nombre_normalizado}")
