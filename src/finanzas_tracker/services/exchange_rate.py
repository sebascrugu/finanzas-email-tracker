"""Servicio para obtener tipos de cambio USD a CRC."""

from datetime import date, datetime
from typing import ClassVar

import requests

from finanzas_tracker.config.settings import settings
from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.exchange_rate_cache import ExchangeRateCache


logger = get_logger(__name__)


class ExchangeRateService:
    """
    Servicio para obtener tipos de cambio históricos de USD a CRC.

    Implementa cache-aside pattern con dos niveles de caché:
    1. Cache en memoria (dict) - ~1ms de latencia
    2. Cache persistente en DB (SQLite) - ~5ms de latencia
    3. API externa si no existe cache - ~500ms de latencia

    Fuentes de exchange rates (en orden de prioridad):
    1. Ministerio de Hacienda de Costa Rica (API oficial)
    2. exchangerate.host (API gratuita internacional)
    3. Tipo de cambio configurado (fallback final)

    Benefits:
    - 100x reducción en latencia (500ms → 5ms después del primer fetch)
    - Cost optimization: 1 API call por fecha (vs N calls por cada transacción)
    - Persistencia: Cache sobrevive entre sesiones de la aplicación
    - Reliability: Multiple fallback sources
    """

    # Cache de tipos de cambio en memoria {fecha: rate}
    _cache: ClassVar[dict[str, float]] = {}

    def __init__(self) -> None:
        """Inicializa el servicio de tipos de cambio."""
        self.default_rate = settings.usd_to_crc_rate
        logger.info("ExchangeRateService inicializado")

    def get_rate(self, transaction_date: date | datetime | str) -> float:
        """
        Obtiene el tipo de cambio USD a CRC para una fecha específica.

        Implementa cache-aside pattern con dos niveles:
        1. Cache en memoria (más rápido, ~1ms)
        2. Cache persistente en DB (rápido, ~5ms)
        3. API externa si no existe cache (~500ms)

        Args:
            transaction_date: Fecha de la transacción (date, datetime, o string ISO)

        Returns:
            float: Tipo de cambio USD a CRC para esa fecha

        Example:
            >>> service = ExchangeRateService()
            >>> rate = service.get_rate("2025-11-04")
            >>> print(f"Tipo de cambio: ₡{rate:.2f}")
        """
        # Normalizar fecha
        if isinstance(transaction_date, datetime):
            target_date = transaction_date.date()
            date_str = target_date.isoformat()
        elif isinstance(transaction_date, date):
            target_date = transaction_date
            date_str = target_date.isoformat()
        else:
            date_str = str(transaction_date)
            target_date = date.fromisoformat(date_str)

        # Nivel 1: Verificar cache en memoria
        if date_str in self._cache:
            logger.debug(f"Cache hit (memory) para {date_str}: ₡{self._cache[date_str]:.2f}")
            return self._cache[date_str]

        # Nivel 2: Verificar cache en base de datos
        with get_session() as session:
            cached_entry = ExchangeRateCache.get_by_date(session, target_date)
            if cached_entry:
                rate = float(cached_entry.rate)
                # Guardar en cache de memoria para próximas consultas
                self._cache[date_str] = rate
                logger.debug(
                    f"Cache hit (DB) para {date_str}: ₡{rate:.2f} " f"(source: {cached_entry.source})"
                )
                return rate

        # Nivel 3: No está en cache, obtener de API externa
        rate, source = self._get_rate_from_apis(date_str)

        # Guardar en ambos caches (memoria + DB)
        if rate:
            self._cache[date_str] = rate
            with get_session() as session:
                ExchangeRateCache.save_rate(session, target_date, rate, source)
                session.commit()
            logger.info(f"Tipo de cambio para {date_str}: ₡{rate:.2f} (source: {source})")
            return rate

        # Fallback: usar tipo de cambio configurado y guardarlo
        logger.warning(
            f"No se pudo obtener tipo de cambio para {date_str}, "
            f"usando default: ₡{self.default_rate:.2f}"
        )
        self._cache[date_str] = self.default_rate
        with get_session() as session:
            ExchangeRateCache.save_rate(session, target_date, self.default_rate, "default")
            session.commit()
        return self.default_rate

    def _get_rate_from_apis(self, date_str: str) -> tuple[float | None, str]:
        """
        Intenta obtener el tipo de cambio de múltiples APIs.

        Args:
            date_str: Fecha en formato ISO (YYYY-MM-DD)

        Returns:
            tuple[float | None, str]: (Tipo de cambio, fuente) o (None, "") si falla
        """
        # Intentar API del Ministerio de Hacienda de Costa Rica (oficial, gratuita)
        rate = self._get_from_hacienda_cr(date_str)
        if rate:
            return rate, "hacienda_cr"

        # Fallback: Intentar exchangerate-api.com
        rate = self._get_from_exchangerate_api(date_str)
        if rate:
            return rate, "exchangerate_api"

        return None, ""

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

        except requests.RequestException as e:
            logger.debug(f"Error de red obteniendo de Hacienda CR: {e}")
        except (KeyError, ValueError, TypeError) as e:
            logger.debug(f"Error parseando respuesta de Hacienda CR: {e}")

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

        except requests.RequestException as e:
            logger.debug(f"Error de red obteniendo de exchangerate.host: {e}")
        except (KeyError, ValueError, TypeError) as e:
            logger.debug(f"Error parseando respuesta de exchangerate.host: {e}")

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
