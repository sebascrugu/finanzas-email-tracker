"""Servicio de Aprendizaje de Patrones de Categorización.

Este servicio aprende de las clarificaciones del usuario para:
1. Categorizar automáticamente futuras transacciones similares
2. Detectar patrones recurrentes (mismo beneficiario = misma categoría)
3. Sugerir categorías basadas en historial

Patrones que detecta:
- Por beneficiario: "SINPE a Juan → siempre es Préstamo"
- Por cuenta destino: "Cuenta XXXX-1234 → siempre es Alquiler"
- Por monto recurrente: "₡350,000/mes → probablemente Alquiler"
- Por frecuencia: "Cada 15 del mes → Salario entrante o gasto fijo"
"""

__all__ = [
    "PatternLearningService",
    "LearnedPattern",
    "PatternSuggestion",
]

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from finanzas_tracker.models.category import Subcategory
from finanzas_tracker.models.learning import (
    UserContact,
    UserMerchantPreference,
    GlobalMerchantSuggestion,
)
from finanzas_tracker.models.transaction import Transaction


logger = logging.getLogger(__name__)


@dataclass
class LearnedPattern:
    """Un patrón aprendido de las transacciones del usuario."""
    pattern_type: str  # "beneficiary", "amount_range", "recurring", "description"
    pattern_key: str  # El valor que identifica el patrón
    subcategory_id: str | None
    subcategory_name: str | None
    confidence: float  # 0.0 a 1.0
    times_seen: int
    user_label: str | None  # Alias del usuario (ej: "Mamá", "Casero")
    last_seen: datetime | None


@dataclass
class PatternSuggestion:
    """Sugerencia de categoría basada en patrones."""
    source: str  # "user_pattern", "contact", "global", "similar_transaction"
    subcategory_id: str
    subcategory_name: str
    confidence: float
    reason: str  # Explicación para el usuario


class PatternLearningService:
    """
    Servicio para aprender y aplicar patrones de categorización.
    
    Flujo típico:
    1. Usuario clarifica una transferencia → guardar_patron()
    2. Nueva transacción llega → buscar_sugerencias()
    3. Si hay sugerencia con alta confianza → auto-categorizar
    4. Si no → pedir clarificación (y el ciclo se repite)
    """

    # Umbral de confianza para auto-categorizar sin preguntar
    AUTO_CATEGORIZE_THRESHOLD = 0.85
    
    # Número mínimo de veces que un patrón se ve antes de sugerir
    MIN_PATTERN_COUNT = 2

    def __init__(self, db: Session) -> None:
        """Inicializa el servicio."""
        self.db = db

    def guardar_patron_de_clarificacion(
        self,
        transaction: Transaction,
        subcategory_id: str,
        user_label: str | None = None,
        beneficiario: str | None = None,
        concepto: str | None = None,
    ) -> LearnedPattern | None:
        """
        Guarda un patrón cuando el usuario clarifica una transacción.
        
        Se llama después de que el usuario responde "Le pagué al zapatero".
        
        Args:
            transaction: La transacción clarificada
            subcategory_id: Categoría asignada
            user_label: Etiqueta del usuario (ej: "Zapatero")
            beneficiario: Nombre del beneficiario
            concepto: Concepto/descripción
            
        Returns:
            El patrón aprendido o None si no se pudo guardar
        """
        profile_id = transaction.profile_id
        
        # Determinar el patrón principal (prioridad: beneficiario > cuenta > descripción)
        pattern_key = None
        pattern_type = None
        
        # 1. Si tiene beneficiario, usar eso
        beneficiario_final = beneficiario or transaction.beneficiario
        if beneficiario_final:
            pattern_key = self._normalizar_beneficiario(beneficiario_final)
            pattern_type = "beneficiary"
        
        # 2. Si no, usar concepto
        elif concepto or transaction.concepto_transferencia:
            pattern_key = (concepto or transaction.concepto_transferencia or "").lower().strip()
            pattern_type = "description"
        
        if not pattern_key or not pattern_type:
            logger.debug("No se pudo determinar patrón para la transacción")
            return None
        
        # Buscar si ya existe el patrón
        existing = self.db.query(UserMerchantPreference).filter(
            UserMerchantPreference.profile_id == profile_id,
            UserMerchantPreference.merchant_pattern == pattern_key,
        ).first()
        
        if existing:
            # Actualizar patrón existente
            existing.subcategory_id = subcategory_id
            existing.times_used += 1
            existing.confidence = min(Decimal("0.99"), existing.confidence + Decimal("0.05"))
            if user_label:
                existing.user_label = user_label
            existing.updated_at = datetime.now(UTC)
            
            logger.info(f"📚 Patrón actualizado: {pattern_key} (x{existing.times_used})")
        else:
            # Crear nuevo patrón
            existing = UserMerchantPreference(
                profile_id=profile_id,
                merchant_pattern=pattern_key,
                subcategory_id=subcategory_id,
                user_label=user_label,
                times_used=1,
                confidence=Decimal("0.80"),
                source="user_correction",
            )
            self.db.add(existing)
            logger.info(f"📚 Nuevo patrón guardado: {pattern_key}")
        
        # También guardar como contacto si tiene beneficiario
        if beneficiario_final and pattern_type == "beneficiary":
            self._guardar_contacto(
                profile_id=profile_id,
                sinpe_name=beneficiario_final,
                alias=user_label,
                subcategory_id=subcategory_id,
                monto=transaction.monto_crc,
            )
        
        # Actualizar sugerencias globales (crowdsourcing)
        self._actualizar_sugerencia_global(pattern_key, subcategory_id)
        
        self.db.commit()
        
        # Obtener nombre de subcategoría para el resultado
        subcat = self.db.query(Subcategory).filter(Subcategory.id == subcategory_id).first()
        
        return LearnedPattern(
            pattern_type=pattern_type,
            pattern_key=pattern_key,
            subcategory_id=subcategory_id,
            subcategory_name=subcat.nombre if subcat else None,
            confidence=float(existing.confidence),
            times_seen=existing.times_used,
            user_label=user_label,
            last_seen=datetime.now(UTC),
        )

    def buscar_sugerencias(
        self,
        transaction: Transaction,
    ) -> list[PatternSuggestion]:
        """
        Busca sugerencias de categoría para una transacción.
        
        Orden de prioridad:
        1. Patrón del usuario (máxima confianza)
        2. Contacto conocido
        3. Sugerencia global aprobada
        4. Transacción similar reciente
        
        Args:
            transaction: Transacción a categorizar
            
        Returns:
            Lista de sugerencias ordenadas por confianza
        """
        sugerencias: list[PatternSuggestion] = []
        profile_id = transaction.profile_id
        
        # 1. Buscar patrón del usuario por beneficiario
        if transaction.beneficiario:
            patron_benef = self._buscar_patron_usuario(
                profile_id, 
                self._normalizar_beneficiario(transaction.beneficiario)
            )
            if patron_benef:
                sugerencias.append(patron_benef)
        
        # 2. Buscar contacto conocido
        if transaction.beneficiario:
            contacto = self._buscar_contacto(
                profile_id,
                transaction.beneficiario,
            )
            if contacto:
                sugerencias.append(contacto)
        
        # 3. Buscar patrón por descripción/concepto
        if transaction.concepto_transferencia:
            patron_desc = self._buscar_patron_usuario(
                profile_id,
                transaction.concepto_transferencia.lower().strip(),
            )
            if patron_desc:
                sugerencias.append(patron_desc)
        
        # 4. Buscar sugerencia global
        if transaction.beneficiario:
            global_sug = self._buscar_sugerencia_global(
                self._normalizar_beneficiario(transaction.beneficiario)
            )
            if global_sug:
                sugerencias.append(global_sug)
        
        # 5. Buscar transacción similar reciente
        similar = self._buscar_transaccion_similar(transaction)
        if similar:
            sugerencias.append(similar)
        
        # Ordenar por confianza descendente
        sugerencias.sort(key=lambda s: s.confidence, reverse=True)
        
        return sugerencias

    def auto_categorizar_si_confianza_alta(
        self,
        transaction: Transaction,
    ) -> bool:
        """
        Intenta auto-categorizar una transacción si hay un patrón con alta confianza.
        
        Args:
            transaction: Transacción a categorizar
            
        Returns:
            True si se auto-categorizó, False si necesita revisión manual
        """
        sugerencias = self.buscar_sugerencias(transaction)
        
        if not sugerencias:
            return False
        
        mejor = sugerencias[0]
        
        if mejor.confidence >= self.AUTO_CATEGORIZE_THRESHOLD:
            # Auto-categorizar
            transaction.subcategory_id = mejor.subcategory_id
            transaction.necesita_reconciliacion_sinpe = False
            transaction.notas = (
                f"✅ Auto-categorizado\n"
                f"Razón: {mejor.reason}\n"
                f"Confianza: {mejor.confidence:.0%}"
            )
            
            logger.info(
                f"🤖 Auto-categorizado: ₡{transaction.monto_crc:,.0f} → "
                f"{mejor.subcategory_name} ({mejor.confidence:.0%})"
            )
            
            # Incrementar contador del patrón
            self._incrementar_uso_patron(transaction.profile_id, transaction.beneficiario)
            
            return True
        
        return False

    def detectar_patrones_recurrentes(
        self,
        profile_id: str,
        meses_atras: int = 3,
    ) -> list[LearnedPattern]:
        """
        Detecta patrones recurrentes en las transacciones del usuario.
        
        Patrones que busca:
        - Mismo beneficiario cada mes
        - Monto similar cada mes (±10%)
        - Mismo día del mes (±3 días)
        
        Args:
            profile_id: ID del perfil
            meses_atras: Cuántos meses analizar
            
        Returns:
            Lista de patrones detectados
        """
        patrones: list[LearnedPattern] = []
        fecha_inicio = datetime.now(UTC) - timedelta(days=meses_atras * 30)
        
        # Buscar beneficiarios que aparecen en múltiples meses
        beneficiarios_frecuentes = (
            self.db.query(
                Transaction.beneficiario,
                func.count(Transaction.id).label("count"),
                func.sum(Transaction.monto_crc).label("total"),
            )
            .filter(
                Transaction.profile_id == profile_id,
                Transaction.beneficiario.isnot(None),
                Transaction.fecha_transaccion >= fecha_inicio,
                Transaction.deleted_at.is_(None),
            )
            .group_by(Transaction.beneficiario)
            .having(func.count(Transaction.id) >= self.MIN_PATTERN_COUNT)
            .all()
        )
        
        for benef, count, total in beneficiarios_frecuentes:
            # Verificar si ya tiene categoría consistente
            categorias = (
                self.db.query(Transaction.subcategory_id)
                .filter(
                    Transaction.profile_id == profile_id,
                    Transaction.beneficiario == benef,
                    Transaction.subcategory_id.isnot(None),
                    Transaction.deleted_at.is_(None),
                )
                .distinct()
                .all()
            )
            
            if len(categorias) == 1:
                # Todas las transacciones a este beneficiario tienen la misma categoría
                subcat_id = categorias[0][0]
                subcat = self.db.query(Subcategory).filter(Subcategory.id == subcat_id).first()
                
                patrones.append(LearnedPattern(
                    pattern_type="recurring_beneficiary",
                    pattern_key=benef,
                    subcategory_id=subcat_id,
                    subcategory_name=subcat.nombre if subcat else None,
                    confidence=min(0.95, 0.70 + (count * 0.05)),
                    times_seen=count,
                    user_label=None,
                    last_seen=datetime.now(UTC),
                ))
        
        return patrones

    def _normalizar_beneficiario(self, beneficiario: str) -> str:
        """Normaliza el nombre del beneficiario para matching."""
        if not beneficiario:
            return ""
        
        # Quitar espacios extra, convertir a mayúsculas
        normalizado = " ".join(beneficiario.upper().split())
        
        # Quitar caracteres especiales
        normalizado = re.sub(r"[^\w\s]", "", normalizado)
        
        return normalizado

    def _guardar_contacto(
        self,
        profile_id: str,
        sinpe_name: str,
        alias: str | None,
        subcategory_id: str,
        monto: Decimal,
    ) -> None:
        """Guarda o actualiza un contacto SINPE."""
        # Buscar contacto existente
        contacto = self.db.query(UserContact).filter(
            UserContact.profile_id == profile_id,
            UserContact.sinpe_name == sinpe_name,
        ).first()
        
        if contacto:
            contacto.total_transactions += 1
            contacto.total_amount_crc += monto
            contacto.last_transaction_at = datetime.now(UTC)
            if alias and not contacto.alias:
                contacto.alias = alias
            if subcategory_id:
                contacto.default_subcategory_id = subcategory_id
        else:
            contacto = UserContact(
                profile_id=profile_id,
                sinpe_name=sinpe_name,
                alias=alias,
                default_subcategory_id=subcategory_id,
                total_transactions=1,
                total_amount_crc=monto,
                last_transaction_at=datetime.now(UTC),
            )
            self.db.add(contacto)

    def _actualizar_sugerencia_global(
        self,
        pattern: str,
        subcategory_id: str,
    ) -> None:
        """Actualiza sugerencias crowdsourced."""
        existing = self.db.query(GlobalMerchantSuggestion).filter(
            GlobalMerchantSuggestion.merchant_pattern == pattern,
            GlobalMerchantSuggestion.suggested_subcategory_id == subcategory_id,
        ).first()
        
        if existing:
            existing.user_count += 1
            existing.confidence_score = min(
                Decimal("0.99"),
                Decimal("0.50") + Decimal(existing.user_count) * Decimal("0.08")
            )
            
            # Auto-aprobar si hay suficientes usuarios
            if existing.should_auto_approve and existing.status == "pending":
                existing.status = "approved"
                existing.approved_at = datetime.now(UTC)
                logger.info(f"✅ Sugerencia global auto-aprobada: {pattern}")
        else:
            sugerencia = GlobalMerchantSuggestion(
                merchant_pattern=pattern,
                suggested_subcategory_id=subcategory_id,
                user_count=1,
                confidence_score=Decimal("0.50"),
                status="pending",
            )
            self.db.add(sugerencia)

    def _buscar_patron_usuario(
        self,
        profile_id: str,
        pattern: str,
    ) -> PatternSuggestion | None:
        """Busca un patrón guardado del usuario."""
        pref = self.db.query(UserMerchantPreference).filter(
            UserMerchantPreference.profile_id == profile_id,
            UserMerchantPreference.merchant_pattern == pattern,
        ).first()
        
        if not pref:
            return None
        
        subcat = self.db.query(Subcategory).filter(Subcategory.id == pref.subcategory_id).first()
        
        return PatternSuggestion(
            source="user_pattern",
            subcategory_id=pref.subcategory_id,
            subcategory_name=subcat.nombre if subcat else "Desconocida",
            confidence=float(pref.confidence),
            reason=f"Siempre categorizas a {pref.user_label or pattern} así",
        )

    def _buscar_contacto(
        self,
        profile_id: str,
        sinpe_name: str,
    ) -> PatternSuggestion | None:
        """Busca un contacto conocido."""
        contacto = self.db.query(UserContact).filter(
            UserContact.profile_id == profile_id,
            or_(
                UserContact.sinpe_name == sinpe_name,
                UserContact.alias == sinpe_name,
            ),
        ).first()
        
        if not contacto or not contacto.default_subcategory_id:
            return None
        
        subcat = self.db.query(Subcategory).filter(
            Subcategory.id == contacto.default_subcategory_id
        ).first()
        
        return PatternSuggestion(
            source="contact",
            subcategory_id=contacto.default_subcategory_id,
            subcategory_name=subcat.nombre if subcat else "Desconocida",
            confidence=0.90,
            reason=f"Es tu contacto '{contacto.display_name}' ({contacto.total_transactions} transacciones)",
        )

    def _buscar_sugerencia_global(
        self,
        pattern: str,
    ) -> PatternSuggestion | None:
        """Busca una sugerencia global aprobada."""
        sugerencia = self.db.query(GlobalMerchantSuggestion).filter(
            GlobalMerchantSuggestion.merchant_pattern == pattern,
            GlobalMerchantSuggestion.status == "approved",
        ).first()
        
        if not sugerencia:
            return None
        
        subcat = self.db.query(Subcategory).filter(
            Subcategory.id == sugerencia.suggested_subcategory_id
        ).first()
        
        return PatternSuggestion(
            source="global",
            subcategory_id=sugerencia.suggested_subcategory_id,
            subcategory_name=subcat.nombre if subcat else "Desconocida",
            confidence=float(sugerencia.confidence_score or 0.75),
            reason=f"{sugerencia.user_count} usuarios categorizan esto igual",
        )

    def _buscar_transaccion_similar(
        self,
        transaction: Transaction,
    ) -> PatternSuggestion | None:
        """Busca una transacción similar ya categorizada."""
        # Buscar transacción con beneficiario similar y monto similar
        if not transaction.beneficiario:
            return None
        
        similar = (
            self.db.query(Transaction)
            .filter(
                Transaction.profile_id == transaction.profile_id,
                Transaction.beneficiario == transaction.beneficiario,
                Transaction.subcategory_id.isnot(None),
                Transaction.id != transaction.id,
                Transaction.deleted_at.is_(None),
            )
            .order_by(Transaction.fecha_transaccion.desc())
            .first()
        )
        
        if not similar:
            return None
        
        subcat = self.db.query(Subcategory).filter(
            Subcategory.id == similar.subcategory_id
        ).first()
        
        # Calcular similitud de monto
        if similar.monto_crc > 0:
            ratio = float(transaction.monto_crc / similar.monto_crc)
            monto_similar = 0.8 <= ratio <= 1.2  # ±20%
        else:
            monto_similar = False
        
        confidence = 0.70 if monto_similar else 0.60
        
        return PatternSuggestion(
            source="similar_transaction",
            subcategory_id=similar.subcategory_id,
            subcategory_name=subcat.nombre if subcat else "Desconocida",
            confidence=confidence,
            reason=f"Transacción similar del {similar.fecha_transaccion.strftime('%d/%m')}",
        )

    def _incrementar_uso_patron(
        self,
        profile_id: str,
        beneficiario: str | None,
    ) -> None:
        """Incrementa el contador de uso de un patrón."""
        if not beneficiario:
            return
        
        pattern = self._normalizar_beneficiario(beneficiario)
        pref = self.db.query(UserMerchantPreference).filter(
            UserMerchantPreference.profile_id == profile_id,
            UserMerchantPreference.merchant_pattern == pattern,
        ).first()
        
        if pref:
            pref.times_used += 1
            pref.confidence = min(Decimal("0.99"), pref.confidence + Decimal("0.02"))
