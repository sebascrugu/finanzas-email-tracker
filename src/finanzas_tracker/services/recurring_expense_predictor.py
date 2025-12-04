"""RecurringExpensePredictor - Predictor de gastos recurrentes.

Predice próximos gastos basándose en historial de transacciones
y suscripciones detectadas. Genera alertas de vencimientos.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum
import logging
import statistics

from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.models import Transaction
from finanzas_tracker.services.subscription_detector import (
    DetectedSubscription,
    SubscriptionDetector,
)


logger = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    """Nivel de alerta para gastos próximos."""

    INFO = "info"
    WARNING = "warning"
    URGENT = "urgent"


class ExpenseType(str, Enum):
    """Tipo de gasto recurrente."""

    SUBSCRIPTION = "subscription"  # Suscripción (Netflix, Spotify)
    UTILITY = "utility"  # Servicio público (agua, luz, internet)
    LOAN = "loan"  # Préstamo o cuota
    RENT = "rent"  # Alquiler
    INSURANCE = "insurance"  # Seguro
    OTHER = "other"


@dataclass
class PredictedExpense:
    """Representa un gasto predecido próximo."""

    comercio: str
    monto_estimado: Decimal
    fecha_estimada: date
    tipo: ExpenseType
    confianza: int  # 0-100
    dias_restantes: int
    nivel_alerta: AlertLevel
    monto_min: Decimal | None = None
    monto_max: Decimal | None = None
    historial_montos: list[Decimal] = field(default_factory=list)
    notas: str = ""

    def to_dict(self) -> dict:
        """Convierte a diccionario para serialización."""
        return {
            "comercio": self.comercio,
            "monto_estimado": float(self.monto_estimado),
            "monto_min": float(self.monto_min) if self.monto_min else None,
            "monto_max": float(self.monto_max) if self.monto_max else None,
            "fecha_estimada": self.fecha_estimada.isoformat(),
            "tipo": self.tipo.value,
            "confianza": self.confianza,
            "dias_restantes": self.dias_restantes,
            "nivel_alerta": self.nivel_alerta.value,
            "notas": self.notas,
        }


@dataclass
class ExpenseSummary:
    """Resumen de gastos proyectados para un período."""

    periodo_inicio: date
    periodo_fin: date
    total_estimado: Decimal
    gastos: list[PredictedExpense]
    por_tipo: dict[ExpenseType, Decimal] = field(default_factory=dict)
    alertas_urgentes: int = 0

    def to_dict(self) -> dict:
        """Convierte a diccionario."""
        return {
            "periodo_inicio": self.periodo_inicio.isoformat(),
            "periodo_fin": self.periodo_fin.isoformat(),
            "total_estimado": float(self.total_estimado),
            "cantidad_gastos": len(self.gastos),
            "alertas_urgentes": self.alertas_urgentes,
            "por_tipo": {k.value: float(v) for k, v in self.por_tipo.items()},
            "gastos": [g.to_dict() for g in self.gastos],
        }


# Patrones de servicios públicos de Costa Rica
UTILITY_PATTERNS: dict[str, str] = {
    "AYA": "Agua (AYA)",
    "ASADA": "Agua Local",
    "ICE": "Electricidad/Internet ICE",
    "CNFL": "Electricidad CNFL",
    "ESPH": "Electricidad ESPH",
    "JASEC": "Electricidad JASEC",
    "COOPELESCA": "Electricidad Coopelesca",
    "COOPEGUANACASTE": "Electricidad Guanacaste",
    "KOLBI": "Telecomunicaciones Kolbi",
    "CLARO": "Telecomunicaciones Claro",
    "MOVISTAR": "Telecomunicaciones Movistar",
    "LIBERTY": "Cable/Internet Liberty",
    "TIGO": "Cable/Internet Tigo",
    "CABLETICA": "Cable Cabletica",
}

# Patrones de préstamos/cuotas
LOAN_PATTERNS: list[str] = [
    "CUOTA",
    "PRESTAMO",
    "CREDITO PERSONAL",
    "HIPOTECA",
    "FINANCIAMIENTO",
    "MARCHAMO",  # Marchamo de vehículo
]

# Patrones de seguros
INSURANCE_PATTERNS: list[str] = [
    "INS ",
    "SEGURO",
    "ASEGURADORA",
    "POLIZA",
    "CCSS",  # Caja Costarricense de Seguro Social
]

# Patrones de alquiler
RENT_PATTERNS: list[str] = [
    "ALQUILER",
    "RENTA",
    "ARRENDAMIENTO",
    "CASA",
    "APARTAMENTO",
]


class RecurringExpensePredictor:
    """Predictor de gastos recurrentes y alertas de vencimiento."""

    def __init__(self, db: Session) -> None:
        """Inicializa el predictor.

        Args:
            db: Sesión de base de datos.
        """
        self.db = db
        self.subscription_detector = SubscriptionDetector(db)
        logger.info("RecurringExpensePredictor inicializado")

    def predecir_gastos(
        self,
        profile_id: str,
        dias_adelante: int = 30,
        confianza_minima: int = 50,
    ) -> list[PredictedExpense]:
        """Predice gastos próximos para un perfil.

        Args:
            profile_id: ID del perfil.
            dias_adelante: Días hacia adelante para predecir.
            confianza_minima: Confianza mínima requerida (0-100).

        Returns:
            Lista de gastos predecidos ordenados por fecha.
        """
        predicciones: list[PredictedExpense] = []
        hoy = date.today()
        fecha_limite = hoy + timedelta(days=dias_adelante)

        # 1. Obtener suscripciones detectadas
        suscripciones = self.subscription_detector.detectar_suscripciones(
            profile_id, confianza_minima=confianza_minima
        )

        for sub in suscripciones:
            # Calcular próximo cobro
            proximo_cobro = self._calcular_proximo_cobro(sub, hoy)

            if proximo_cobro and proximo_cobro <= fecha_limite:
                dias_restantes = (proximo_cobro - hoy).days

                prediccion = PredictedExpense(
                    comercio=sub.comercio,
                    monto_estimado=sub.monto_promedio,
                    monto_min=sub.monto_min,
                    monto_max=sub.monto_max,
                    fecha_estimada=proximo_cobro,
                    tipo=self._clasificar_tipo(sub.comercio_normalizado),
                    confianza=sub.confianza,
                    dias_restantes=dias_restantes,
                    nivel_alerta=self._determinar_alerta(dias_restantes, sub.monto_promedio),
                )
                predicciones.append(prediccion)

        # 2. Buscar gastos recurrentes adicionales no detectados como suscripción
        predicciones.extend(
            self._detectar_gastos_periodicos(profile_id, dias_adelante, confianza_minima)
        )

        # Ordenar por fecha
        predicciones.sort(key=lambda x: x.fecha_estimada)

        logger.info(
            "Predichos %d gastos para profile %s (próximos %d días)",
            len(predicciones),
            profile_id[:8],
            dias_adelante,
        )

        return predicciones

    def generar_resumen_mensual(
        self,
        profile_id: str,
        mes: int | None = None,
        anio: int | None = None,
    ) -> ExpenseSummary:
        """Genera resumen de gastos proyectados para un mes.

        Args:
            profile_id: ID del perfil.
            mes: Mes (1-12). Si es None, usa el mes actual.
            anio: Año. Si es None, usa el año actual.

        Returns:
            Resumen con todos los gastos proyectados.
        """
        hoy = date.today()

        if mes is None:
            mes = hoy.month
        if anio is None:
            anio = hoy.year

        # Calcular rango del mes
        inicio_mes = date(anio, mes, 1)
        if mes == 12:
            fin_mes = date(anio + 1, 1, 1) - timedelta(days=1)
        else:
            fin_mes = date(anio, mes + 1, 1) - timedelta(days=1)

        # Calcular días adelante desde hoy
        if inicio_mes > hoy:
            dias_desde_hoy = (fin_mes - hoy).days
        else:
            dias_desde_hoy = (fin_mes - hoy).days

        # Obtener predicciones
        predicciones = self.predecir_gastos(
            profile_id,
            dias_adelante=max(dias_desde_hoy, 60),
            confianza_minima=40,
        )

        # Filtrar solo las del mes solicitado
        gastos_mes = [p for p in predicciones if inicio_mes <= p.fecha_estimada <= fin_mes]

        # Calcular totales
        total = sum(g.monto_estimado for g in gastos_mes)

        # Agrupar por tipo
        por_tipo: dict[ExpenseType, Decimal] = {}
        for gasto in gastos_mes:
            por_tipo[gasto.tipo] = por_tipo.get(gasto.tipo, Decimal("0")) + gasto.monto_estimado

        # Contar alertas urgentes
        alertas_urgentes = sum(1 for g in gastos_mes if g.nivel_alerta == AlertLevel.URGENT)

        return ExpenseSummary(
            periodo_inicio=inicio_mes,
            periodo_fin=fin_mes,
            total_estimado=total,
            gastos=gastos_mes,
            por_tipo=por_tipo,
            alertas_urgentes=alertas_urgentes,
        )

    def get_alertas_vencimiento(
        self,
        profile_id: str,
        dias_alerta: int = 7,
    ) -> list[PredictedExpense]:
        """Obtiene alertas de vencimientos próximos.

        Args:
            profile_id: ID del perfil.
            dias_alerta: Días para considerar como alerta (default 7).

        Returns:
            Lista de gastos con vencimiento próximo.
        """
        predicciones = self.predecir_gastos(
            profile_id,
            dias_adelante=dias_alerta,
            confianza_minima=60,
        )

        # Filtrar solo los de nivel warning o urgent
        alertas = [
            p for p in predicciones if p.nivel_alerta in (AlertLevel.WARNING, AlertLevel.URGENT)
        ]

        logger.info(
            "Encontradas %d alertas de vencimiento para profile %s",
            len(alertas),
            profile_id[:8],
        )

        return alertas

    def estimar_flujo_caja(
        self,
        profile_id: str,
        saldo_inicial: Decimal,
        dias: int = 30,
    ) -> dict[date, Decimal]:
        """Estima el flujo de caja futuro.

        Args:
            profile_id: ID del perfil.
            saldo_inicial: Saldo inicial de cuenta.
            dias: Días a proyectar.

        Returns:
            Diccionario fecha -> saldo proyectado.
        """
        predicciones = self.predecir_gastos(profile_id, dias_adelante=dias, confianza_minima=50)

        hoy = date.today()
        flujo: dict[date, Decimal] = {}
        saldo = saldo_inicial

        for dia in range(dias + 1):
            fecha = hoy + timedelta(days=dia)

            # Restar gastos de este día
            gastos_dia = sum(p.monto_estimado for p in predicciones if p.fecha_estimada == fecha)

            saldo -= gastos_dia
            flujo[fecha] = saldo

        return flujo

    def _calcular_proximo_cobro(
        self,
        sub: DetectedSubscription,
        desde: date,
    ) -> date | None:
        """Calcula fecha del próximo cobro.

        Args:
            sub: Suscripción detectada.
            desde: Fecha desde la cual calcular.

        Returns:
            Fecha del próximo cobro o None.
        """
        ultimo = sub.ultimo_cobro
        dias = int(sub.dias_promedio_entre_cobros)

        # Calcular próximo cobro después de 'desde'
        proximo = ultimo + timedelta(days=dias)

        # Si el próximo es antes de 'desde', avanzar períodos
        while proximo < desde:
            proximo += timedelta(days=dias)

        return proximo

    def _clasificar_tipo(self, comercio: str) -> ExpenseType:
        """Clasifica el tipo de gasto según el comercio.

        Args:
            comercio: Nombre normalizado del comercio.

        Returns:
            Tipo de gasto.
        """
        comercio_upper = comercio.upper()

        # Verificar servicios públicos
        for patron, _ in UTILITY_PATTERNS.items():
            if patron in comercio_upper:
                return ExpenseType.UTILITY

        # Verificar préstamos
        for patron in LOAN_PATTERNS:
            if patron in comercio_upper:
                return ExpenseType.LOAN

        # Verificar seguros
        for patron in INSURANCE_PATTERNS:
            if patron in comercio_upper:
                return ExpenseType.INSURANCE

        # Verificar alquiler
        for patron in RENT_PATTERNS:
            if patron in comercio_upper:
                return ExpenseType.RENT

        # Por defecto es suscripción
        return ExpenseType.SUBSCRIPTION

    def _determinar_alerta(
        self,
        dias_restantes: int,
        monto: Decimal,
    ) -> AlertLevel:
        """Determina el nivel de alerta según proximidad y monto.

        Args:
            dias_restantes: Días hasta el vencimiento.
            monto: Monto del gasto.

        Returns:
            Nivel de alerta.
        """
        # Gastos grandes (> ₡50,000) tienen umbral más alto
        es_grande = monto > Decimal("50000")

        if dias_restantes <= 2:
            return AlertLevel.URGENT
        if dias_restantes <= 5:
            return AlertLevel.WARNING if es_grande else AlertLevel.INFO
        if dias_restantes <= 7 and es_grande:
            return AlertLevel.WARNING
        return AlertLevel.INFO

    def _detectar_gastos_periodicos(
        self,
        profile_id: str,
        dias_adelante: int,
        confianza_minima: int,
    ) -> list[PredictedExpense]:
        """Detecta gastos periódicos que no son suscripciones típicas.

        Busca patrones como pagos de servicios públicos, cuotas de préstamos, etc.

        Args:
            profile_id: ID del perfil.
            dias_adelante: Días hacia adelante.
            confianza_minima: Confianza mínima.

        Returns:
            Lista de gastos predecidos adicionales.
        """
        predicciones: list[PredictedExpense] = []
        hoy = date.today()
        fecha_limite = hoy + timedelta(days=dias_adelante)

        # Buscar transacciones de los últimos 6 meses
        fecha_inicio = hoy - timedelta(days=180)

        stmt = select(Transaction).where(
            Transaction.profile_id == profile_id,
            Transaction.fecha_transaccion >= fecha_inicio,
            Transaction.es_transferencia_interna.is_(False),
            Transaction.deleted_at.is_(None),
        )

        txs = self.db.execute(stmt).scalars().all()

        # Agrupar por comercio
        por_comercio: dict[str, list[Transaction]] = {}
        for tx in txs:
            comercio = self._normalizar_comercio(tx.comercio)
            if comercio not in por_comercio:
                por_comercio[comercio] = []
            por_comercio[comercio].append(tx)

        # Analizar cada grupo
        for comercio, transacciones in por_comercio.items():
            if len(transacciones) < 2:
                continue

            # Verificar si es servicio público o cuota
            tipo = self._clasificar_tipo(comercio)
            if tipo == ExpenseType.SUBSCRIPTION:
                # Ya procesado por SubscriptionDetector
                continue

            # Ordenar por fecha
            transacciones.sort(key=lambda x: x.fecha_transaccion)

            # Calcular intervalo promedio
            intervalos = []
            for i in range(1, len(transacciones)):
                delta = (
                    transacciones[i].fecha_transaccion - transacciones[i - 1].fecha_transaccion
                ).days
                if 20 <= delta <= 40:  # Aproximadamente mensual
                    intervalos.append(delta)

            if not intervalos:
                continue

            # Calcular estadísticas
            intervalo_promedio = statistics.mean(intervalos)
            montos = [tx.monto_original for tx in transacciones]
            monto_promedio = statistics.mean(montos)

            # Calcular próxima fecha
            ultima_fecha = transacciones[-1].fecha_transaccion
            proxima_fecha = ultima_fecha + timedelta(days=int(intervalo_promedio))

            if proxima_fecha < hoy:
                # Ajustar si ya pasó
                while proxima_fecha < hoy:
                    proxima_fecha += timedelta(days=int(intervalo_promedio))

            if proxima_fecha > fecha_limite:
                continue

            # Calcular confianza
            confianza = min(90, 50 + len(transacciones) * 5)
            if confianza < confianza_minima:
                continue

            dias_restantes = (proxima_fecha - hoy).days

            prediccion = PredictedExpense(
                comercio=comercio,
                monto_estimado=Decimal(str(monto_promedio)),
                monto_min=min(montos),
                monto_max=max(montos),
                fecha_estimada=proxima_fecha,
                tipo=tipo,
                confianza=confianza,
                dias_restantes=dias_restantes,
                nivel_alerta=self._determinar_alerta(dias_restantes, Decimal(str(monto_promedio))),
                historial_montos=list(montos[-6:]),  # Últimos 6
            )
            predicciones.append(prediccion)

        return predicciones

    def _normalizar_comercio(self, comercio: str) -> str:
        """Normaliza nombre de comercio para agrupar."""
        import re

        resultado = comercio.upper().strip()

        # Remover números de referencia largos
        resultado = re.sub(r"\d{6,}", "", resultado)

        # Remover ***XXXX (últimos 4 dígitos de tarjeta)
        resultado = re.sub(r"\*{3}\d{4}", "", resultado)

        # Limpiar espacios
        resultado = re.sub(r"\s+", " ", resultado).strip()

        return resultado


def generar_reporte_gastos_proximos(
    db: Session,
    profile_id: str,
    dias: int = 30,
) -> dict:
    """Genera reporte de gastos próximos.

    Función de conveniencia para uso desde API o CLI.

    Args:
        db: Sesión de base de datos.
        profile_id: ID del perfil.
        dias: Días a proyectar.

    Returns:
        Diccionario con reporte completo.
    """
    predictor = RecurringExpensePredictor(db)

    predicciones = predictor.predecir_gastos(profile_id, dias_adelante=dias)
    alertas = predictor.get_alertas_vencimiento(profile_id)

    return {
        "generado_en": date.today().isoformat(),
        "dias_proyectados": dias,
        "total_gastos": len(predicciones),
        "total_estimado": float(sum(p.monto_estimado for p in predicciones)),
        "alertas_urgentes": len([a for a in alertas if a.nivel_alerta == AlertLevel.URGENT]),
        "alertas_warning": len([a for a in alertas if a.nivel_alerta == AlertLevel.WARNING]),
        "gastos": [p.to_dict() for p in predicciones],
        "alertas": [a.to_dict() for a in alertas],
    }
