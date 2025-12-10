"""
Servicio de Feedback Loop para aprendizaje continuo.

Este servicio registra cuando un usuario corrige una categorización
y aprende de esa corrección para mejorar futuras predicciones.

Flujo:
1. Usuario corrige categoría de una transacción
2. Se guarda preferencia del usuario (personal)
3. Se propone mejora global (crowdsourced)
4. Se actualiza embedding si aplica
5. Próximas transacciones similares usan la preferencia
"""

__all__ = ["FeedbackService", "record_user_correction"]

import logging
import re
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finanzas_tracker.core.database import get_session
from finanzas_tracker.models.learning import (
    GlobalMerchantSuggestion,
    UserContact,
    UserMerchantPreference,
)
from finanzas_tracker.models.transaction import Transaction


logger = logging.getLogger(__name__)


class FeedbackService:
    """
    Servicio de aprendizaje continuo.
    
    Cuando un usuario corrige una categorización:
    1. Guarda la preferencia del usuario (máxima prioridad futura)
    2. Si es SINPE, aprende el contacto
    3. Propone mejora global si hay consenso
    """
    
    # Mínimo de usuarios para auto-aprobar sugerencia global
    MIN_USERS_FOR_AUTO_APPROVE = 5
    
    def __init__(self, session: Session) -> None:
        """
        Inicializa el servicio.
        
        Args:
            session: Sesión de SQLAlchemy
        """
        self.session = session
    
    def record_correction(
        self,
        transaction_id: str,
        new_subcategory_id: str,
        user_label: str | None = None,
        profile_id: str | None = None,
    ) -> dict[str, bool]:
        """
        Registra cuando un usuario corrige una categorización.
        
        Args:
            transaction_id: ID de la transacción corregida
            new_subcategory_id: Nueva categoría correcta
            user_label: Etiqueta personalizada (ej: "Mamá", "Gym")
            profile_id: ID del perfil del usuario
            
        Returns:
            Dict con resultados: preference_saved, contact_learned, global_proposed
        """
        results = {
            "preference_saved": False,
            "contact_learned": False,
            "global_proposed": False,
        }
        
        # 1. Obtener transacción
        transaction = self.session.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        ).scalar_one_or_none()
        
        if not transaction:
            logger.error(f"Transacción {transaction_id} no encontrada")
            return results
        
        # Usar profile_id de la transacción si no se proporcionó
        if not profile_id:
            profile_id = transaction.profile_id
        
        # Guardar categoría original antes de cambiar
        categoria_original = transaction.subcategory_id
        
        # 2. Crear patrón del comercio
        merchant_pattern = self._create_merchant_pattern(transaction.comercio)
        
        # 3. Guardar preferencia del usuario
        if self._save_user_preference(
            profile_id=profile_id,
            merchant_pattern=merchant_pattern,
            subcategory_id=new_subcategory_id,
            user_label=user_label,
        ):
            results["preference_saved"] = True
        
        # 4. Actualizar la transacción
        transaction.subcategory_id = new_subcategory_id
        transaction.categoria_confirmada_usuario = True
        transaction.necesita_revision = False
        if categoria_original:
            transaction.categoria_original_ia = str(categoria_original)
        
        # 5. Si es SINPE, aprender el contacto
        if "SINPE" in transaction.comercio.upper():
            if self._learn_sinpe_contact(
                transaction=transaction,
                profile_id=profile_id,
                subcategory_id=new_subcategory_id,
                user_label=user_label,
            ):
                results["contact_learned"] = True
        
        # 6. Proponer mejora global (crowdsourced)
        if self._propose_global_improvement(
            merchant_pattern=merchant_pattern,
            subcategory_id=new_subcategory_id,
        ):
            results["global_proposed"] = True
        
        self.session.commit()
        
        logger.info(
            f"✅ Corrección registrada: {merchant_pattern} → {new_subcategory_id}"
            f" (label: {user_label})"
        )
        
        return results
    
    def _create_merchant_pattern(self, comercio: str) -> str:
        """
        Crea un patrón generalizable del comercio.
        
        Ejemplos:
            "SINPE MARIA ROSA CRUZ" → "SINPE MARIA%"
            "UBER *TRIP 12345" → "UBER%"
            "AUTOMERCADO ESCAZU" → "AUTOMERCADO%"
        """
        comercio = comercio.upper().strip()
        
        # Remover códigos de referencia (8+ caracteres alfanuméricos)
        comercio = re.sub(r"\b[A-Z0-9]{8,}\b", "", comercio)
        comercio = re.sub(r"\*\w+", "", comercio)
        
        # Para SINPE, mantener primer nombre pero generalizar
        if comercio.startswith("SINPE"):
            parts = comercio.split()
            if len(parts) >= 2:
                # "SINPE MARIA ROSA" → "SINPE MARIA%"
                return f"SINPE {parts[1]}%"
            return "SINPE%"
        
        # Para otros, tomar primera palabra significativa
        words = comercio.split()
        if words:
            first_word = words[0]
            # Si la primera palabra es muy corta (ej: "FS"), incluir la segunda
            if len(first_word) <= 2 and len(words) > 1:
                return f"{first_word} {words[1]}%"
            return f"{first_word}%"
        
        return comercio
    
    def _save_user_preference(
        self,
        profile_id: str | None,
        merchant_pattern: str,
        subcategory_id: str,
        user_label: str | None = None,
    ) -> bool:
        """
        Guarda o actualiza preferencia del usuario.
        
        Returns:
            True si se guardó/actualizó correctamente
        """
        try:
            # Buscar si ya existe
            existing = self.session.execute(
                select(UserMerchantPreference).where(
                    UserMerchantPreference.profile_id == profile_id,
                    UserMerchantPreference.merchant_pattern == merchant_pattern,
                )
            ).scalar_one_or_none()
            
            if existing:
                # Actualizar
                existing.subcategory_id = subcategory_id
                existing.times_used += 1
                existing.confidence = min(Decimal("0.99"), existing.confidence + Decimal("0.01"))
                if user_label:
                    existing.user_label = user_label
                logger.debug(f"Preferencia actualizada: {merchant_pattern} (x{existing.times_used})")
            else:
                # Crear nueva
                preference = UserMerchantPreference(
                    profile_id=profile_id,
                    merchant_pattern=merchant_pattern,
                    subcategory_id=subcategory_id,
                    user_label=user_label,
                    source="user_correction",
                )
                self.session.add(preference)
                logger.debug(f"Nueva preferencia creada: {merchant_pattern}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error guardando preferencia: {e}")
            return False
    
    def _learn_sinpe_contact(
        self,
        transaction: Transaction,
        profile_id: str | None,
        subcategory_id: str,
        user_label: str | None = None,
    ) -> bool:
        """
        Aprende un contacto SINPE del usuario.
        
        Returns:
            True si se aprendió correctamente
        """
        try:
            # Extraer nombre del SINPE
            comercio = transaction.comercio.upper()
            match = re.search(r"SINPE\s+(.+)", comercio)
            if not match:
                return False
            
            sinpe_name = match.group(1).strip()
            
            # Extraer número de teléfono si está disponible
            phone_match = re.search(r"(\d{4}[-\s]?\d{4})", comercio)
            phone_number = phone_match.group(1) if phone_match else None
            
            # Buscar si ya existe (por nombre o teléfono)
            existing = None
            if phone_number:
                existing = self.session.execute(
                    select(UserContact).where(
                        UserContact.profile_id == profile_id,
                        UserContact.phone_number == phone_number,
                    )
                ).scalar_one_or_none()
            
            if not existing:
                # Buscar por nombre similar
                existing = self.session.execute(
                    select(UserContact).where(
                        UserContact.profile_id == profile_id,
                        UserContact.sinpe_name.ilike(f"%{sinpe_name[:10]}%"),
                    )
                ).scalar_one_or_none()
            
            monto = transaction.monto_crc or Decimal("0")
            
            if existing:
                # Actualizar estadísticas
                existing.total_transactions += 1
                existing.total_amount_crc += monto
                existing.last_transaction_at = datetime.now(UTC)
                
                # Actualizar alias y categoría si se proporcionaron
                if user_label:
                    existing.alias = user_label
                if not existing.default_subcategory_id:
                    existing.default_subcategory_id = subcategory_id
                
                logger.debug(f"Contacto actualizado: {existing.display_name}")
            else:
                # Crear nuevo contacto
                contact = UserContact(
                    profile_id=profile_id,
                    phone_number=phone_number,
                    sinpe_name=sinpe_name,
                    alias=user_label,
                    default_subcategory_id=subcategory_id,
                    total_transactions=1,
                    total_amount_crc=monto,
                    last_transaction_at=datetime.now(UTC),
                )
                self.session.add(contact)
                logger.debug(f"Nuevo contacto creado: {sinpe_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error aprendiendo contacto SINPE: {e}")
            return False
    
    def _propose_global_improvement(
        self,
        merchant_pattern: str,
        subcategory_id: str,
    ) -> bool:
        """
        Propone mejora global si hay suficiente consenso.
        
        Returns:
            True si se propuso/actualizó correctamente
        """
        try:
            # Buscar si ya existe sugerencia
            existing = self.session.execute(
                select(GlobalMerchantSuggestion).where(
                    GlobalMerchantSuggestion.merchant_pattern == merchant_pattern,
                    GlobalMerchantSuggestion.suggested_subcategory_id == subcategory_id,
                )
            ).scalar_one_or_none()
            
            if existing:
                existing.user_count += 1
                # Calcular confianza: base 0.70 + 0.05 por cada usuario
                existing.confidence_score = min(
                    Decimal("0.99"),
                    Decimal("0.70") + (Decimal(existing.user_count) * Decimal("0.05")),
                )
                
                # Auto-aprobar si hay consenso
                if existing.should_auto_approve and existing.status == "pending":
                    existing.status = "approved"
                    existing.approved_at = datetime.now(UTC)
                    logger.info(f"🌐 Auto-aprobada sugerencia global: {merchant_pattern}")
                
                logger.debug(
                    f"Sugerencia global actualizada: {merchant_pattern} "
                    f"(usuarios: {existing.user_count})"
                )
            else:
                # Crear nueva sugerencia
                suggestion = GlobalMerchantSuggestion(
                    merchant_pattern=merchant_pattern,
                    suggested_subcategory_id=subcategory_id,
                    confidence_score=Decimal("0.75"),
                )
                self.session.add(suggestion)
                logger.debug(f"Nueva sugerencia global: {merchant_pattern}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error proponiendo mejora global: {e}")
            return False
    
    def get_user_preference(
        self,
        profile_id: str,
        comercio: str,
    ) -> UserMerchantPreference | None:
        """
        Busca preferencia del usuario para un comercio.
        
        Args:
            profile_id: ID del perfil
            comercio: Nombre del comercio
            
        Returns:
            Preferencia si existe, None si no
        """
        comercio_upper = comercio.upper()
        
        # Buscar por patrón LIKE
        preferences = self.session.execute(
            select(UserMerchantPreference)
            .where(UserMerchantPreference.profile_id == profile_id)
            .order_by(UserMerchantPreference.times_used.desc())
        ).scalars().all()
        
        for pref in preferences:
            # Convertir patrón a regex (% → .*)
            pattern = pref.merchant_pattern.replace("%", ".*")
            if re.match(pattern, comercio_upper):
                return pref
        
        return None
    
    def get_sinpe_contact(
        self,
        profile_id: str,
        comercio: str,
    ) -> UserContact | None:
        """
        Busca contacto SINPE para un comercio.
        
        Args:
            profile_id: ID del perfil
            comercio: Nombre del comercio (ej: "SINPE MARIA ROSA")
            
        Returns:
            Contacto si existe, None si no
        """
        if "SINPE" not in comercio.upper():
            return None
        
        # Extraer nombre
        match = re.search(r"SINPE\s+(.+)", comercio.upper())
        if not match:
            return None
        
        sinpe_name = match.group(1).strip()
        
        # Buscar por nombre similar (primeras 10 letras)
        return self.session.execute(
            select(UserContact)
            .where(
                UserContact.profile_id == profile_id,
                UserContact.sinpe_name.ilike(f"%{sinpe_name[:10]}%"),
            )
            .order_by(UserContact.total_transactions.desc())
        ).scalar_one_or_none()


def record_user_correction(
    transaction_id: str,
    new_subcategory_id: str,
    user_label: str | None = None,
    profile_id: str | None = None,
) -> dict[str, bool]:
    """
    Helper para registrar corrección desde cualquier parte de la app.
    
    Args:
        transaction_id: ID de la transacción corregida
        new_subcategory_id: Nueva categoría correcta
        user_label: Etiqueta personalizada (ej: "Mamá")
        profile_id: ID del perfil (opcional, se toma de la transacción)
        
    Returns:
        Dict con resultados del registro
    """
    with get_session() as session:
        service = FeedbackService(session)
        return service.record_correction(
            transaction_id=transaction_id,
            new_subcategory_id=new_subcategory_id,
            user_label=user_label,
            profile_id=profile_id,
        )
