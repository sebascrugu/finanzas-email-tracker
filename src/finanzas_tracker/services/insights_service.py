"""Servicio de Insights Inteligentes para Finanzas.

Genera alertas, predicciones y recomendaciones basadas en:
- Comparación con meses anteriores
- Patrones de gasto
- Tendencias
- Metodología 50/30/20
"""

__all__ = [
    "InsightsService",
    "Insight",
    "InsightType",
]

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import func, select, and_
from sqlalchemy.orm import Session

from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.models.category import Subcategory


logger = logging.getLogger(__name__)


class InsightType(Enum):
    """Tipos de insights."""
    ALERT = "alert"  # Algo negativo que necesita atención
    WARNING = "warning"  # Cuidado, podrías tener problemas
    SUCCESS = "success"  # Algo positivo
    INFO = "info"  # Información neutral
    PREDICTION = "prediction"  # Predicción del futuro


@dataclass
class Insight:
    """Un insight o alerta para el usuario."""
    tipo: InsightType
    titulo: str
    mensaje: str
    categoria: str | None = None  # Si aplica a una categoría específica
    monto: Decimal | None = None
    porcentaje_cambio: float | None = None
    icono: str = "💡"
    prioridad: int = 0  # 0 = baja, 1 = media, 2 = alta


class InsightsService:
    """
    Servicio para generar insights inteligentes.
    
    Genera:
    - Alertas de gastos inusuales
    - Predicciones de fin de mes
    - Comparaciones con meses anteriores
    - Sugerencias de ahorro
    """
    
    # Umbrales de configuración
    UMBRAL_AUMENTO_ALERTA = 50  # % de aumento para generar alerta
    UMBRAL_AUMENTO_WARNING = 25  # % de aumento para generar warning
    DIAS_MINIMOS_PREDICCION = 5  # Mínimo de días para hacer predicciones
    
    def __init__(self, db: Session) -> None:
        """Inicializa el servicio."""
        self.db = db
    
    def generar_insights(
        self,
        profile_id: str,
        mes: int | None = None,
        ano: int | None = None,
    ) -> list[Insight]:
        """
        Genera todos los insights para un perfil y mes.
        
        Args:
            profile_id: ID del perfil
            mes: Mes a analizar (default: actual)
            ano: Año a analizar (default: actual)
            
        Returns:
            Lista de insights ordenados por prioridad
        """
        hoy = date.today()
        mes = mes or hoy.month
        ano = ano or hoy.year
        
        insights: list[Insight] = []
        
        # 1. Alertas de gastos por categoría
        insights.extend(self._alertas_gastos_categoria(profile_id, mes, ano))
        
        # 2. Predicción de fin de mes
        prediccion = self._prediccion_fin_mes(profile_id, mes, ano)
        if prediccion:
            insights.append(prediccion)
        
        # 3. Análisis 50/30/20
        insights.extend(self._analisis_503020(profile_id, mes, ano))
        
        # 4. Patrones de gasto
        insights.extend(self._patrones_gasto(profile_id, mes, ano))
        
        # Ordenar por prioridad (alta primero)
        insights.sort(key=lambda x: (-x.prioridad, x.tipo.value))
        
        return insights
    
    def _alertas_gastos_categoria(
        self,
        profile_id: str,
        mes: int,
        ano: int,
    ) -> list[Insight]:
        """Genera alertas para categorías con gastos inusuales."""
        insights: list[Insight] = []
        
        # Obtener gastos por categoría este mes
        gastos_mes = self._gastos_por_categoria(profile_id, mes, ano)
        
        # Obtener gastos del mes anterior
        mes_anterior = mes - 1 if mes > 1 else 12
        ano_anterior = ano if mes > 1 else ano - 1
        gastos_anterior = self._gastos_por_categoria(profile_id, mes_anterior, ano_anterior)
        
        for categoria, monto_actual in gastos_mes.items():
            monto_anterior = gastos_anterior.get(categoria, Decimal("0"))
            
            if monto_anterior > 0:
                cambio_pct = float((monto_actual - monto_anterior) / monto_anterior * 100)
                
                if cambio_pct >= self.UMBRAL_AUMENTO_ALERTA:
                    insights.append(Insight(
                        tipo=InsightType.ALERT,
                        titulo=f"Aumento significativo en {categoria}",
                        mensaje=f"Este mes gastaste {cambio_pct:.0f}% más que el mes anterior "
                               f"(₡{monto_actual:,.0f} vs ₡{monto_anterior:,.0f})",
                        categoria=categoria,
                        monto=monto_actual,
                        porcentaje_cambio=cambio_pct,
                        icono="🚨",
                        prioridad=2,
                    ))
                elif cambio_pct >= self.UMBRAL_AUMENTO_WARNING:
                    insights.append(Insight(
                        tipo=InsightType.WARNING,
                        titulo=f"Incremento en {categoria}",
                        mensaje=f"Gastaste {cambio_pct:.0f}% más este mes en esta categoría",
                        categoria=categoria,
                        monto=monto_actual,
                        porcentaje_cambio=cambio_pct,
                        icono="⚠️",
                        prioridad=1,
                    ))
                elif cambio_pct <= -30:  # Reducción significativa
                    insights.append(Insight(
                        tipo=InsightType.SUCCESS,
                        titulo=f"Ahorro en {categoria}",
                        mensaje=f"Excelente! Gastaste {abs(cambio_pct):.0f}% menos este mes",
                        categoria=categoria,
                        monto=monto_actual,
                        porcentaje_cambio=cambio_pct,
                        icono="🎉",
                        prioridad=0,
                    ))
        
        return insights
    
    def _prediccion_fin_mes(
        self,
        profile_id: str,
        mes: int,
        ano: int,
    ) -> Insight | None:
        """Predice cuánto se habrá gastado al final del mes."""
        hoy = date.today()
        
        # Solo predecir para el mes actual
        if mes != hoy.month or ano != hoy.year:
            return None
        
        # Necesitamos suficientes días para predecir
        if hoy.day < self.DIAS_MINIMOS_PREDICCION:
            return None
        
        # Obtener total gastado hasta hoy
        inicio_mes = date(ano, mes, 1)
        
        stmt = select(func.sum(Transaction.monto_crc)).where(
            and_(
                Transaction.profile_id == profile_id,
                Transaction.fecha_transaccion >= inicio_mes,
                Transaction.fecha_transaccion <= hoy,
                Transaction.tipo_transaccion != "ingreso",
                Transaction.es_transferencia_interna.is_(False),
                Transaction.deleted_at.is_(None),
            )
        )
        
        result = self.db.execute(stmt).scalar()
        total_hasta_hoy = result or Decimal("0")
        
        if total_hasta_hoy <= 0:
            return None
        
        # Calcular días del mes
        if mes == 12:
            dias_mes = 31
        else:
            dias_mes = (date(ano, mes + 1, 1) - timedelta(days=1)).day
        
        # Proyección lineal
        promedio_diario = total_hasta_hoy / hoy.day
        proyeccion = promedio_diario * dias_mes
        
        # Obtener presupuesto si existe
        presupuesto_mes = self._obtener_presupuesto_mes(profile_id, mes, ano)
        
        if presupuesto_mes and presupuesto_mes > 0:
            if proyeccion > presupuesto_mes:
                exceso = proyeccion - presupuesto_mes
                return Insight(
                    tipo=InsightType.WARNING,
                    titulo="Proyección de exceso de presupuesto",
                    mensaje=f"A este ritmo, terminarás el mes con ₡{proyeccion:,.0f} gastados. "
                           f"Eso es ₡{exceso:,.0f} más que tu presupuesto de ₡{presupuesto_mes:,.0f}",
                    monto=proyeccion,
                    icono="📊",
                    prioridad=2,
                )
            else:
                ahorro = presupuesto_mes - proyeccion
                return Insight(
                    tipo=InsightType.SUCCESS,
                    titulo="Buen ritmo de gastos",
                    mensaje=f"Proyección: ₡{proyeccion:,.0f}. "
                           f"Podrías ahorrar ₡{ahorro:,.0f} este mes",
                    monto=proyeccion,
                    icono="✅",
                    prioridad=0,
                )
        else:
            # Sin presupuesto, solo informar
            return Insight(
                tipo=InsightType.PREDICTION,
                titulo="Proyección de gastos del mes",
                mensaje=f"A tu ritmo actual (₡{promedio_diario:,.0f}/día), "
                       f"terminarás el mes con ₡{proyeccion:,.0f} gastados",
                monto=proyeccion,
                icono="📈",
                prioridad=0,
            )
    
    def _analisis_503020(
        self,
        profile_id: str,
        mes: int,
        ano: int,
    ) -> list[Insight]:
        """Analiza si el usuario cumple con la metodología 50/30/20."""
        insights: list[Insight] = []
        
        # Obtener gastos por tipo
        inicio_mes = date(ano, mes, 1)
        if mes == 12:
            fin_mes = date(ano + 1, 1, 1) - timedelta(days=1)
        else:
            fin_mes = date(ano, mes + 1, 1) - timedelta(days=1)
        
        # Query para gastos por tipo (necesidades, gustos, ahorros)
        stmt = select(
            Subcategory.tipo_gasto,
            func.sum(Transaction.monto_crc),
        ).join(
            Subcategory, Transaction.subcategory_id == Subcategory.id
        ).where(
            and_(
                Transaction.profile_id == profile_id,
                Transaction.fecha_transaccion >= inicio_mes,
                Transaction.fecha_transaccion <= fin_mes,
                Transaction.tipo_transaccion != "ingreso",
                Transaction.es_transferencia_interna.is_(False),
                Transaction.deleted_at.is_(None),
            )
        ).group_by(Subcategory.tipo_gasto)
        
        resultados = self.db.execute(stmt).all()
        gastos_por_tipo = {tipo: monto for tipo, monto in resultados if tipo}
        
        total = sum(gastos_por_tipo.values()) or Decimal("1")
        
        # Calcular porcentajes
        pct_necesidades = float(gastos_por_tipo.get("necesidades", 0) / total * 100)
        pct_gustos = float(gastos_por_tipo.get("gustos", 0) / total * 100)
        pct_ahorros = float(gastos_por_tipo.get("ahorros", 0) / total * 100)
        
        # Generar insights según cumplimiento
        if pct_necesidades > 60:
            insights.append(Insight(
                tipo=InsightType.WARNING,
                titulo="Necesidades superan el 50%",
                mensaje=f"Tus necesidades representan {pct_necesidades:.0f}% de tus gastos. "
                       "Considera revisar si algunos gastos pueden reducirse.",
                porcentaje_cambio=pct_necesidades - 50,
                icono="🏠",
                prioridad=1,
            ))
        
        if pct_gustos > 40:
            insights.append(Insight(
                tipo=InsightType.ALERT,
                titulo="Gustos superan el 30%",
                mensaje=f"Tus gustos representan {pct_gustos:.0f}% de tus gastos. "
                       "Podrías estar gastando demasiado en entretenimiento.",
                porcentaje_cambio=pct_gustos - 30,
                icono="🎮",
                prioridad=2,
            ))
        
        if pct_ahorros >= 20:
            insights.append(Insight(
                tipo=InsightType.SUCCESS,
                titulo="Excelente ahorro!",
                mensaje=f"Estás ahorrando {pct_ahorros:.0f}% de tus gastos. "
                       "¡Sigue así!",
                porcentaje_cambio=pct_ahorros - 20,
                icono="🎯",
                prioridad=0,
            ))
        elif pct_ahorros < 10:
            insights.append(Insight(
                tipo=InsightType.ALERT,
                titulo="Bajo nivel de ahorro",
                mensaje=f"Solo estás ahorrando {pct_ahorros:.0f}%. "
                       "Intenta llegar al menos al 20%.",
                porcentaje_cambio=pct_ahorros - 20,
                icono="💰",
                prioridad=2,
            ))
        
        return insights
    
    def _patrones_gasto(
        self,
        profile_id: str,
        mes: int,
        ano: int,
    ) -> list[Insight]:
        """Detecta patrones de gasto (fines de semana, comercios frecuentes)."""
        insights: list[Insight] = []
        
        inicio_mes = date(ano, mes, 1)
        if mes == 12:
            fin_mes = date(ano + 1, 1, 1) - timedelta(days=1)
        else:
            fin_mes = date(ano, mes + 1, 1) - timedelta(days=1)
        
        # Detectar comercio más frecuente
        stmt = select(
            Transaction.comercio,
            func.count(Transaction.id).label("count"),
            func.sum(Transaction.monto_crc).label("total"),
        ).where(
            and_(
                Transaction.profile_id == profile_id,
                Transaction.fecha_transaccion >= inicio_mes,
                Transaction.fecha_transaccion <= fin_mes,
                Transaction.tipo_transaccion != "ingreso",
                Transaction.deleted_at.is_(None),
                Transaction.comercio.isnot(None),
            )
        ).group_by(
            Transaction.comercio
        ).order_by(
            func.count(Transaction.id).desc()
        ).limit(1)
        
        result = self.db.execute(stmt).first()
        
        if result and result.count >= 3:
            comercio, count, total = result.comercio, result.count, result.total
            insights.append(Insight(
                tipo=InsightType.INFO,
                titulo=f"Comercio frecuente: {comercio}",
                mensaje=f"Has visitado {comercio} {count} veces este mes, "
                       f"gastando un total de ₡{total:,.0f}",
                monto=total,
                icono="🏪",
                prioridad=0,
            ))
        
        return insights
    
    def _gastos_por_categoria(
        self,
        profile_id: str,
        mes: int,
        ano: int,
    ) -> dict[str, Decimal]:
        """Obtiene gastos agrupados por categoría para un mes."""
        inicio_mes = date(ano, mes, 1)
        if mes == 12:
            fin_mes = date(ano + 1, 1, 1) - timedelta(days=1)
        else:
            fin_mes = date(ano, mes + 1, 1) - timedelta(days=1)
        
        stmt = select(
            Subcategory.nombre,
            func.sum(Transaction.monto_crc),
        ).join(
            Subcategory, Transaction.subcategory_id == Subcategory.id
        ).where(
            and_(
                Transaction.profile_id == profile_id,
                Transaction.fecha_transaccion >= inicio_mes,
                Transaction.fecha_transaccion <= fin_mes,
                Transaction.tipo_transaccion != "ingreso",
                Transaction.es_transferencia_interna.is_(False),
                Transaction.deleted_at.is_(None),
            )
        ).group_by(Subcategory.nombre)
        
        resultados = self.db.execute(stmt).all()
        return {nombre: monto for nombre, monto in resultados if nombre}
    
    def _obtener_presupuesto_mes(
        self,
        profile_id: str,
        mes: int,
        ano: int,
    ) -> Decimal | None:
        """Obtiene el presupuesto total del mes."""
        from finanzas_tracker.models.budget import Budget
        
        stmt = select(func.sum(Budget.monto_mensual)).where(
            and_(
                Budget.profile_id == profile_id,
                Budget.activo.is_(True),
                Budget.deleted_at.is_(None),
            )
        )
        
        result = self.db.execute(stmt).scalar()
        return result if result else None
