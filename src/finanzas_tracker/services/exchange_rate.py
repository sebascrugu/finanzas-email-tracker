"""Servicio para obtener tipos de cambio USD a CRC."""

from datetime import date, datetime
from typing import ClassVar

import requests

from finanzas_tracker.config.settings import settings
from finanzas_tracker.core.logging import get_logger

logger = get_logger(__name__)


class ExchangeRateService:
    """
    Servicio para obtener tipos de cambio históricos de USD a CRC.

    Soporta múltiples fuentes con fallback automático:
    1. Cache local (para evitar requests repetidos)
    2. exchangerate-api.com (gratuita, confiable)
    3. frankfurter.app (gratuita, sin autenticación)
    4. Tipo de cambio configurado (fallback final)
    """

    # Cache de tipos de cambio {fecha: rate}
    _cache: ClassVar[dict[str, float]] = {}

    def __init__(self) -> None:
        """Inicializa el servicio de tipos de cambio."""
        self.default_rate = settings.usd_to_crc_rate
        logger.info("ExchangeRateService inicializado")

    def get_rate(self, transaction_date: date | datetime | str) -> float:
        """
        Obtiene el tipo de cambio USD a CRC para una fecha específica.

        Args:
            transaction_date: Fecha de la transacción (date, datetime, o string ISO)

        Returns:
            float: Tipo de cambio USD a CRC para esa fecha

        Example:
            >>> service = ExchangeRateService()
            >>> rate = service.get_rate("2025-11-04")
            >>> print(f"Tipo de cambio: ₡{rate:.2f}")
        """
        # Normalizar fecha a string
        if isinstance(transaction_date, datetime):
            date_str = transaction_date.date().isoformat()
        elif isinstance(transaction_date, date):
            date_str = transaction_date.isoformat()
        else:
            date_str = str(transaction_date)

        # Verificar cache
        if date_str in self._cache:
            logger.debug(f"Tipo de cambio en cache para {date_str}: ₡{self._cache[date_str]:.2f}")
            return self._cache[date_str]

        # Intentar obtener de APIs externas
        rate = self._get_rate_from_apis(date_str)

        # Guardar en cache
        if rate:
            self._cache[date_str] = rate
            logger.info(f"Tipo de cambio para {date_str}: ₡{rate:.2f}")
            return rate

        # Fallback: usar tipo de cambio configurado
        logger.warning(
            f"No se pudo obtener tipo de cambio para {date_str}, "
            f"usando default: ₡{self.default_rate:.2f}"
        )
        return self.default_rate

    def _get_rate_from_apis(self, date_str: str) -> float | None:
        """
        Intenta obtener el tipo de cambio de múltiples APIs.

        Args:
            date_str: Fecha en formato ISO (YYYY-MM-DD)

        Returns:
            float | None: Tipo de cambio o None si falla
        """
        # Intentar API del Ministerio de Hacienda de Costa Rica (oficial, gratuita)
        rate = self._get_from_hacienda_cr(date_str)
        if rate:
            return rate

        # Fallback: Intentar exchangerate-api.com
        rate = self._get_from_exchangerate_api(date_str)
        if rate:
            return rate

        return None

    def _get_from_hacienda_cr(self, date_str: str) -> float | None:
        """
        Obtiene el tipo de cambio de la API del Ministerio de Hacienda de Costa Rica.

        Esta es la API oficial del gobierno de Costa Rica.
        - Gratuita y sin registro
        - Actualización diaria
        - Datos históricos confiables
        - Fuente: https://api.hacienda.go.cr

        Args:
            date_str: Fecha en formato ISO (YYYY-MM-DD)

        Returns:
            float | None: Tipo de cambio de venta o None si falla
        """
        try:
            # API del Ministerio de Hacienda de Costa Rica
            url = "https://api.hacienda.go.cr/indicadores/tc/dolar/historico"
            params = {
                "d": date_str,  # Fecha inicio
                "h": date_str,  # Fecha fin (mismo día)
            }
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                # La respuesta es un array con los datos del día
                if data and len(data) > 0:
                    # Usar el tipo de cambio de venta (más común para compras)
                    rate = float(data[0].get("venta", 0))
                    if rate > 0:
                        logger.debug(f"Tipo de cambio de Hacienda CR: ₡{rate:.2f}")
                        return rate

        except Exception as e:
            logger.debug(f"Error obteniendo de Hacienda CR: {e}")

        return None

    def _get_from_exchangerate_api(self, date_str: str) -> float | None:
        """
        Obtiene el tipo de cambio de exchangerate.host.

        Esta API es gratuita y proporciona tipos de cambio históricos.
        Sin límites estrictos en plan gratuito.

        Args:
            date_str: Fecha en formato ISO

        Returns:
            float | None: Tipo de cambio o None si falla
        """
        try:
            # exchangerate.host - API gratuita y confiable
            url = f"https://api.exchangerate.host/{date_str}"
            params = {
                "base": "USD",
                "symbols": "CRC",
            }
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                # Verificar si la respuesta es exitosa
                if data.get("success", False) and "rates" in data and "CRC" in data["rates"]:
                    rate = float(data["rates"]["CRC"])
                    logger.debug(f"Tipo de cambio de exchangerate.host: ₡{rate:.2f}")
                    return rate

        except Exception as e:
            logger.debug(f"Error obteniendo de exchangerate.host: {e}")

        return None

    def convert_usd_to_crc(
        self,
        amount_usd: float,
        transaction_date: date | datetime | str,
    ) -> float:
        """
        Convierte un monto de USD a CRC usando el tipo de cambio histórico.

        Args:
            amount_usd: Monto en dólares
            transaction_date: Fecha de la transacción

        Returns:
            float: Monto en colones

        Example:
            >>> service = ExchangeRateService()
            >>> colones = service.convert_usd_to_crc(25.00, "2025-11-04")
            >>> print(f"₡{colones:,.2f}")  # ₡13,250.00
        """
        rate = self.get_rate(transaction_date)
        amount_crc = amount_usd * rate
        logger.debug(
            f"Conversión: ${amount_usd:.2f} USD x ₡{rate:.2f} = " f"₡{amount_crc:,.2f} CRC"
        )
        return amount_crc

    def clear_cache(self) -> None:
        """Limpia el cache de tipos de cambio."""
        self._cache.clear()
        logger.info("Cache de tipos de cambio limpiado")

    def get_cache_size(self) -> int:
        """Retorna el tamaño del cache."""
        return len(self._cache)


# Singleton para uso global
exchange_rate_service = ExchangeRateService()
