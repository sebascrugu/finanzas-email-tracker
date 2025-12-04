"""Detector de suscripciones y pagos recurrentes.

Analiza transacciones para detectar patrones de pagos
recurrentes como Netflix, Spotify, gimnasios, etc.
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum
from statistics import mean, stdev

from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.models.transaction import Transaction


logger = logging.getLogger(__name__)


class SubscriptionFrequency(str, Enum):
    """Frecuencia de suscripción."""
    
    WEEKLY = "semanal"
    BIWEEKLY = "quincenal"
    MONTHLY = "mensual"
    BIMONTHLY = "bimestral"
    QUARTERLY = "trimestral"
    SEMIANNUAL = "semestral"
    ANNUAL = "anual"


@dataclass
class DetectedSubscription:
    """Suscripción detectada automáticamente."""
    
    comercio: str
    comercio_normalizado: str
    monto_promedio: Decimal
    monto_min: Decimal
    monto_max: Decimal
    frecuencia: SubscriptionFrequency
    dias_promedio_entre_cobros: float
    ultimo_cobro: date
    primer_cobro: date
    cantidad_cobros: int
    confianza: int  # 0-100
    transaccion_ids: list[str] = field(default_factory=list)
    variacion_monto: float = 0.0  # Porcentaje de variación
    
    def to_dict(self) -> dict:
        """Convierte a diccionario para JSON."""
        return {
            "comercio": self.comercio,
            "comercio_normalizado": self.comercio_normalizado,
            "monto_promedio": float(self.monto_promedio),
            "monto_min": float(self.monto_min),
            "monto_max": float(self.monto_max),
            "frecuencia": self.frecuencia.value,
            "dias_promedio_entre_cobros": self.dias_promedio_entre_cobros,
            "ultimo_cobro": self.ultimo_cobro.isoformat(),
            "primer_cobro": self.primer_cobro.isoformat(),
            "cantidad_cobros": self.cantidad_cobros,
            "confianza": self.confianza,
            "variacion_monto": self.variacion_monto,
        }


class SubscriptionDetector:
    """Detecta suscripciones/pagos recurrentes en transacciones."""

    # Patrones conocidos de suscripciones
    KNOWN_SUBSCRIPTIONS: dict[str, str] = {
        r"NETFLIX": "Netflix",
        r"SPOTIFY": "Spotify",
        r"AMAZON\s*PRIME": "Amazon Prime",
        r"DISNEY\s*\+?": "Disney+",
        r"HBO\s*MAX": "HBO Max",
        r"APPLE\s*(MUSIC|TV|ONE|ICLOUD)": "Apple Services",
        r"GOOGLE\s*(ONE|PLAY|STORAGE)": "Google Services",
        r"MICROSOFT\s*365": "Microsoft 365",
        r"YOUTUBE\s*PREMIUM": "YouTube Premium",
        r"TWITCH": "Twitch",
        r"CRUNCHYROLL": "Crunchyroll",
        r"CANVA": "Canva",
        r"ADOBE": "Adobe",
        r"DROPBOX": "Dropbox",
        r"SLACK": "Slack",
        r"ZOOM": "Zoom",
        r"GYM|GIMNASIO|FITNESS": "Gimnasio",
        r"PLANET\s*FITNESS": "Planet Fitness",
        r"SMART\s*FIT": "Smart Fit",
        r"UBER\s*ONE": "Uber One",
        r"RAPPI\s*PRIME": "Rappi Prime",
        r"PLAYSTATION": "PlayStation Plus",
        r"XBOX": "Xbox Game Pass",
        r"NINTENDO": "Nintendo Online",
        r"CHATGPT|OPENAI": "OpenAI",
        r"CLAUDE|ANTHROPIC": "Anthropic",
    }

    # Rangos de días para cada frecuencia
    FREQUENCY_RANGES: dict[SubscriptionFrequency, tuple[int, int]] = {
        SubscriptionFrequency.WEEKLY: (5, 9),
        SubscriptionFrequency.BIWEEKLY: (12, 17),
        SubscriptionFrequency.MONTHLY: (25, 35),
        SubscriptionFrequency.BIMONTHLY: (55, 70),
        SubscriptionFrequency.QUARTERLY: (85, 100),
        SubscriptionFrequency.SEMIANNUAL: (170, 200),
        SubscriptionFrequency.ANNUAL: (350, 380),
    }

    def __init__(self, db: Session) -> None:
        """Inicializa el detector.

        Args:
            db: Sesión de base de datos SQLAlchemy.
        """
        self.db = db

    def detectar_suscripciones(
        self,
        profile_id: str,
        meses_atras: int = 6,
        min_ocurrencias: int = 2,
    ) -> list[DetectedSubscription]:
        """
        Detecta suscripciones en las transacciones del usuario.

        Criterios:
        - Mismo comercio (normalizado)
        - Monto similar (±10%)
        - Frecuencia regular (semanal, mensual, anual)
        - Al menos min_ocurrencias cobros

        Args:
            profile_id: ID del perfil.
            meses_atras: Meses de historial a analizar.
            min_ocurrencias: Mínimo de cobros para considerar suscripción.

        Returns:
            Lista de suscripciones detectadas ordenadas por confianza.
        """
        fecha_inicio = date.today() - timedelta(days=meses_atras * 30)
        
        # Obtener transacciones del período
        stmt = select(Transaction).where(
            Transaction.profile_id == profile_id,
            Transaction.fecha_transaccion >= fecha_inicio,
            Transaction.deleted_at.is_(None),
            Transaction.es_transferencia_interna.is_(False),
        ).order_by(Transaction.fecha_transaccion)
        
        transacciones = list(self.db.execute(stmt).scalars().all())
        
        # Agrupar por comercio normalizado
        grupos = self._agrupar_por_comercio(transacciones)
        
        # Analizar cada grupo
        suscripciones = []
        for comercio_norm, txs in grupos.items():
            if len(txs) >= min_ocurrencias:
                sub = self._analizar_grupo(comercio_norm, txs)
                if sub:
                    suscripciones.append(sub)
        
        # Ordenar por confianza descendente
        suscripciones.sort(key=lambda x: x.confianza, reverse=True)
        
        logger.info(
            f"Detectadas {len(suscripciones)} posibles suscripciones "
            f"para profile {profile_id[:8]}..."
        )
        
        return suscripciones

    def detectar_conocidas(
        self,
        profile_id: str,
        meses_atras: int = 3,
    ) -> list[DetectedSubscription]:
        """
        Detecta suscripciones de servicios conocidos (Netflix, Spotify, etc).

        Usa patrones predefinidos para mayor precisión.

        Args:
            profile_id: ID del perfil.
            meses_atras: Meses de historial a analizar.

        Returns:
            Lista de suscripciones conocidas encontradas.
        """
        fecha_inicio = date.today() - timedelta(days=meses_atras * 30)
        
        stmt = select(Transaction).where(
            Transaction.profile_id == profile_id,
            Transaction.fecha_transaccion >= fecha_inicio,
            Transaction.deleted_at.is_(None),
        ).order_by(Transaction.fecha_transaccion)
        
        transacciones = list(self.db.execute(stmt).scalars().all())
        
        # Buscar patrones conocidos
        encontradas: dict[str, list[Transaction]] = defaultdict(list)
        
        for tx in transacciones:
            comercio = tx.comercio.upper() if tx.comercio else ""
            for patron, nombre in self.KNOWN_SUBSCRIPTIONS.items():
                if re.search(patron, comercio):
                    encontradas[nombre].append(tx)
                    break
        
        # Convertir a DetectedSubscription
        suscripciones = []
        for nombre, txs in encontradas.items():
            if len(txs) >= 1:  # Incluso con 1 ocurrencia si es conocida
                sub = self._analizar_grupo(nombre, txs, es_conocida=True)
                if sub:
                    suscripciones.append(sub)
        
        return suscripciones

    def get_proximo_cobro(
        self,
        suscripcion: DetectedSubscription,
    ) -> date:
        """
        Estima la fecha del próximo cobro.

        Args:
            suscripcion: Suscripción detectada.

        Returns:
            Fecha estimada del próximo cobro.
        """
        dias = int(suscripcion.dias_promedio_entre_cobros)
        return suscripcion.ultimo_cobro + timedelta(days=dias)

    def get_gasto_mensual_suscripciones(
        self,
        suscripciones: list[DetectedSubscription],
    ) -> Decimal:
        """
        Calcula el gasto mensual total en suscripciones.

        Args:
            suscripciones: Lista de suscripciones.

        Returns:
            Total mensual estimado.
        """
        total = Decimal("0")
        
        for sub in suscripciones:
            # Convertir a mensual según frecuencia
            monto = sub.monto_promedio
            
            if sub.frecuencia == SubscriptionFrequency.WEEKLY:
                monto = monto * Decimal("4.33")  # ~4.33 semanas/mes
            elif sub.frecuencia == SubscriptionFrequency.BIWEEKLY:
                monto = monto * Decimal("2.17")
            elif sub.frecuencia == SubscriptionFrequency.BIMONTHLY:
                monto = monto / Decimal("2")
            elif sub.frecuencia == SubscriptionFrequency.QUARTERLY:
                monto = monto / Decimal("3")
            elif sub.frecuencia == SubscriptionFrequency.SEMIANNUAL:
                monto = monto / Decimal("6")
            elif sub.frecuencia == SubscriptionFrequency.ANNUAL:
                monto = monto / Decimal("12")
            
            total += monto
        
        return total.quantize(Decimal("0.01"))

    def _agrupar_por_comercio(
        self,
        transacciones: list[Transaction],
    ) -> dict[str, list[Transaction]]:
        """Agrupa transacciones por comercio normalizado."""
        grupos: dict[str, list[Transaction]] = defaultdict(list)
        
        for tx in transacciones:
            comercio_norm = self._normalizar_comercio(tx.comercio or "")
            if comercio_norm:
                grupos[comercio_norm].append(tx)
        
        return grupos

    def _normalizar_comercio(self, comercio: str) -> str:
        """Normaliza nombre de comercio para agrupación."""
        if not comercio:
            return ""
        
        # Mayúsculas
        norm = comercio.upper()
        
        # Remover números de referencia comunes
        norm = re.sub(r"\d{6,}", "", norm)  # Números largos
        norm = re.sub(r"\*+\d+", "", norm)  # ***1234
        norm = re.sub(r"#\d+", "", norm)  # #12345
        
        # Remover ubicaciones comunes
        norm = re.sub(r"\s+(SAN JOSE|HEREDIA|ALAJUELA|CARTAGO|CR|CRI|COSTA RICA)\b", "", norm)
        
        # Limpiar espacios
        norm = re.sub(r"\s+", " ", norm).strip()
        
        return norm

    def _analizar_grupo(
        self,
        comercio_norm: str,
        transacciones: list[Transaction],
        es_conocida: bool = False,
    ) -> DetectedSubscription | None:
        """
        Analiza un grupo de transacciones para detectar patrón de suscripción.

        Args:
            comercio_norm: Nombre normalizado del comercio.
            transacciones: Lista de transacciones del comercio.
            es_conocida: Si es una suscripción de servicio conocido.

        Returns:
            DetectedSubscription si se detecta patrón, None si no.
        """
        if len(transacciones) < 2 and not es_conocida:
            return None
        
        # Ordenar por fecha
        txs = sorted(transacciones, key=lambda x: x.fecha_transaccion)
        
        # Calcular montos
        montos = [tx.monto_original for tx in txs]
        monto_promedio = sum(montos) / len(montos)
        monto_min = min(montos)
        monto_max = max(montos)
        
        # Calcular variación de monto
        if len(montos) > 1 and monto_promedio > 0:
            try:
                variacion = (stdev([float(m) for m in montos]) / float(monto_promedio)) * 100
            except Exception:
                variacion = 0.0
        else:
            variacion = 0.0
        
        # Calcular días entre cobros
        if len(txs) >= 2:
            dias_entre = []
            for i in range(1, len(txs)):
                dias = (txs[i].fecha_transaccion - txs[i-1].fecha_transaccion).days
                if dias > 0:
                    dias_entre.append(dias)
            
            if not dias_entre:
                return None
            
            dias_promedio = mean(dias_entre)
        else:
            # Para suscripciones conocidas con solo 1 cobro, asumir mensual
            dias_promedio = 30.0
        
        # Determinar frecuencia
        frecuencia = self._determinar_frecuencia(dias_promedio)
        if not frecuencia and not es_conocida:
            return None
        
        frecuencia = frecuencia or SubscriptionFrequency.MONTHLY
        
        # Calcular confianza
        confianza = self._calcular_confianza(
            cantidad_cobros=len(txs),
            variacion_monto=variacion,
            dias_promedio=dias_promedio,
            frecuencia=frecuencia,
            es_conocida=es_conocida,
        )
        
        if confianza < 40 and not es_conocida:
            return None
        
        return DetectedSubscription(
            comercio=txs[0].comercio or comercio_norm,
            comercio_normalizado=comercio_norm,
            monto_promedio=Decimal(str(monto_promedio)).quantize(Decimal("0.01")),
            monto_min=monto_min,
            monto_max=monto_max,
            frecuencia=frecuencia,
            dias_promedio_entre_cobros=dias_promedio,
            ultimo_cobro=txs[-1].fecha_transaccion,
            primer_cobro=txs[0].fecha_transaccion,
            cantidad_cobros=len(txs),
            confianza=confianza,
            transaccion_ids=[tx.id for tx in txs],
            variacion_monto=round(variacion, 2),
        )

    def _determinar_frecuencia(
        self,
        dias_promedio: float,
    ) -> SubscriptionFrequency | None:
        """Determina la frecuencia basada en días promedio."""
        for frecuencia, (min_dias, max_dias) in self.FREQUENCY_RANGES.items():
            if min_dias <= dias_promedio <= max_dias:
                return frecuencia
        return None

    def _calcular_confianza(
        self,
        cantidad_cobros: int,
        variacion_monto: float,
        dias_promedio: float,
        frecuencia: SubscriptionFrequency,
        es_conocida: bool,
    ) -> int:
        """Calcula score de confianza (0-100)."""
        score = 50  # Base
        
        # Bonus por cantidad de cobros
        if cantidad_cobros >= 6:
            score += 20
        elif cantidad_cobros >= 4:
            score += 15
        elif cantidad_cobros >= 3:
            score += 10
        elif cantidad_cobros >= 2:
            score += 5
        
        # Bonus/penalización por variación de monto
        if variacion_monto < 1:
            score += 15  # Monto muy consistente
        elif variacion_monto < 5:
            score += 10
        elif variacion_monto < 10:
            score += 5
        elif variacion_monto > 20:
            score -= 15  # Monto muy variable
        
        # Bonus por frecuencia conocida
        if frecuencia in [SubscriptionFrequency.MONTHLY, SubscriptionFrequency.ANNUAL]:
            score += 10  # Frecuencias más comunes
        
        # Bonus por ser suscripción conocida
        if es_conocida:
            score += 20
        
        # Normalizar a 0-100
        return max(0, min(100, score))
