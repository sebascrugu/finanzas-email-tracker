"""
Sistema de Categorización Híbrido de 4 Capas - Nivel FAANG.

Este módulo implementa un sistema de categorización de transacciones
inspirado en las mejores prácticas de Plaid, Ntropy y Stripe.

Arquitectura:
1. Capa Determinística: Reglas exactas, historial, keywords
2. Capa de Embeddings: Similitud semántica con pgvector
3. Capa LLM: Claude para casos ambiguos
4. Feedback Loop: Aprendizaje continuo

Autor: Sebastian Cruz
Versión: 2.0.0
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any
import logging
import re

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from finanzas_tracker.config.settings import settings
from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.claude_credits import can_use_claude, handle_claude_error
from finanzas_tracker.models.category import Subcategory
from finanzas_tracker.models.learning import UserMerchantPreference, UserContact
from finanzas_tracker.models.transaction import Transaction


logger = logging.getLogger(__name__)


class CategorizationSource(StrEnum):
    """Fuente de la categorización."""
    HISTORY = "history"           # Aprendido del historial del usuario
    MERCHANT_DB = "merchant_db"   # Base de datos de comercios conocidos
    MCC_CODE = "mcc_code"         # Código MCC del comercio
    KEYWORD = "keyword"           # Match por keywords
    EMBEDDING = "embedding"       # Similitud semántica
    LLM = "llm"                   # Claude AI
    USER_OVERRIDE = "user"        # Corrección manual del usuario
    FALLBACK = "fallback"         # Default cuando todo falla


@dataclass
class CategorizationResult:
    """Resultado de categorización con metadata completa."""
    subcategory_id: str | None
    subcategory_name: str
    category_type: str  # necesidades, gustos, ahorros
    confidence: int  # 0-100
    source: CategorizationSource
    needs_review: bool
    alternatives: list[dict] = field(default_factory=list)
    reasoning: str = ""
    context: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convierte a diccionario para compatibilidad con código existente."""
        return {
            "subcategory_id": self.subcategory_id,
            "categoria_sugerida": self.subcategory_name,
            "necesita_revision": self.needs_review,
            "confianza": self.confidence,
            "alternativas": [a.get("nombre", "") for a in self.alternatives],
            "razon": self.reasoning,
            "source": self.source.value,
            "category_type": self.category_type,
        }


# ============================================================================
# BASE DE CONOCIMIENTO DE COSTA RICA
# ============================================================================

# Comercios conocidos de Costa Rica con su categoría
# Formato: "pattern": (subcategory_name, category_type, confidence)
CR_MERCHANTS_DB: dict[str, tuple[str, str, int]] = {
    # === BANCOS Y FINANCIERAS ===
    "bac credomatic": ("Transferencias", "necesidades", 95),
    "banco popular": ("Transferencias", "necesidades", 95),
    "banco nacional": ("Transferencias", "necesidades", 95),
    "bcr": ("Transferencias", "necesidades", 95),
    "scotiabank": ("Transferencias", "necesidades", 95),
    "davivienda": ("Transferencias", "necesidades", 95),
    
    # === SUPERMERCADOS ===
    "automercado": ("Supermercado", "necesidades", 98),
    "walmart": ("Supermercado", "necesidades", 85),  # Puede ser shopping
    "pricesmart": ("Supermercado", "necesidades", 85),
    "mas x menos": ("Supermercado", "necesidades", 98),
    "pali": ("Supermercado", "necesidades", 98),
    "maxi pali": ("Supermercado", "necesidades", 98),
    "megasuper": ("Supermercado", "necesidades", 98),
    "fresh market": ("Supermercado", "necesidades", 95),
    "small market": ("Supermercado", "necesidades", 95),
    
    # === GASOLINERAS ===
    "total": ("Transporte", "necesidades", 95),
    "shell": ("Transporte", "necesidades", 95),
    "uno": ("Transporte", "necesidades", 95),
    "delta": ("Transporte", "necesidades", 95),
    "gasolinera": ("Transporte", "necesidades", 98),
    "combustible": ("Transporte", "necesidades", 98),
    
    # === TRANSPORTE ===
    "uber": ("Transporte", "necesidades", 90),  # Puede ser entretenimiento
    "didi": ("Transporte", "necesidades", 90),
    "peaje": ("Transporte", "necesidades", 99),
    "compass": ("Transporte", "necesidades", 99),
    "autopista": ("Transporte", "necesidades", 99),
    
    # === COMIDA RÁPIDA ===
    "mcdonalds": ("Comida Social", "gustos", 95),
    "burger king": ("Comida Social", "gustos", 95),
    "wendys": ("Comida Social", "gustos", 95),
    "subway": ("Comida Social", "gustos", 95),
    "taco bell": ("Comida Social", "gustos", 95),
    "kfc": ("Comida Social", "gustos", 95),
    "pizza hut": ("Comida Social", "gustos", 95),
    "dominos": ("Comida Social", "gustos", 95),
    "papa johns": ("Comida Social", "gustos", 95),
    "starbucks": ("Comida Social", "gustos", 95),
    "dunkin": ("Comida Social", "gustos", 95),
    "quiznos": ("Comida Social", "gustos", 95),
    
    # === CAFETERÍAS CR ===
    "spoon": ("Comida Social", "gustos", 95),
    "bagelmens": ("Comida Social", "gustos", 95),
    "pan piña": ("Comida Social", "gustos", 95),
    "musmanni": ("Comida Social", "gustos", 90),
    "cafe britt": ("Comida Social", "gustos", 95),
    
    # === ENTRETENIMIENTO ===
    "netflix": ("Entretenimiento", "gustos", 99),
    "spotify": ("Entretenimiento", "gustos", 99),
    "disney": ("Entretenimiento", "gustos", 99),
    "hbo": ("Entretenimiento", "gustos", 99),
    "amazon prime": ("Entretenimiento", "gustos", 99),
    "apple music": ("Entretenimiento", "gustos", 99),
    "youtube premium": ("Entretenimiento", "gustos", 99),
    "playstation": ("Entretenimiento", "gustos", 99),
    "xbox": ("Entretenimiento", "gustos", 99),
    "steam": ("Entretenimiento", "gustos", 99),
    "nintendo": ("Entretenimiento", "gustos", 99),
    "supercell": ("Entretenimiento", "gustos", 99),
    "supercellstore": ("Entretenimiento", "gustos", 99),  # Clash of Clans, etc
    "fs *supercell": ("Entretenimiento", "gustos", 99),  # Variante con prefijo
    "riot games": ("Entretenimiento", "gustos", 99),
    "epic games": ("Entretenimiento", "gustos", 99),
    "bet365": ("Entretenimiento", "gustos", 99),
    "betcris": ("Entretenimiento", "gustos", 99),
    "jps": ("Entretenimiento", "gustos", 99),
    "lot nac": ("Entretenimiento", "gustos", 99),  # Lotería Nacional
    "loteria": ("Entretenimiento", "gustos", 99),
    "cine": ("Entretenimiento", "gustos", 98),
    "cinepolis": ("Entretenimiento", "gustos", 99),
    "nova cinemas": ("Entretenimiento", "gustos", 99),
    "ccm": ("Entretenimiento", "gustos", 99),
    
    # === SHOPPING ONLINE ===
    "amazon": ("Shopping", "gustos", 85),  # Puede ser suscripción
    "paypal": ("Shopping", "gustos", 80),  # Muy genérico
    "ebay": ("Shopping", "gustos", 90),
    "aliexpress": ("Shopping", "gustos", 90),
    "temu": ("Shopping", "gustos", 90),
    "shein": ("Shopping", "gustos", 95),
    "crocs": ("Shopping", "gustos", 98),
    "nike": ("Shopping", "gustos", 98),
    "adidas": ("Shopping", "gustos", 98),
    
    # === TIENDAS CR ===
    "epa": ("Vivienda", "necesidades", 90),  # Puede ser hobbies
    "construplaza": ("Vivienda", "necesidades", 90),
    "gollo": ("Shopping", "gustos", 85),
    "la curacao": ("Shopping", "gustos", 85),
    "importadora monge": ("Shopping", "gustos", 85),
    "ekono": ("Shopping", "gustos", 90),
    "arenas": ("Shopping", "gustos", 95),
    
    # === FARMACIAS ===
    "farmacia": ("Personal", "necesidades", 95),
    "fischel": ("Personal", "necesidades", 95),
    "la bomba": ("Personal", "necesidades", 95),
    "chavarria": ("Personal", "necesidades", 95),
    "sucre": ("Personal", "necesidades", 95),
    
    # === SERVICIOS ===
    "ice": ("Vivienda", "necesidades", 98),
    "kolbi": ("Vivienda", "necesidades", 98),
    "tigo": ("Vivienda", "necesidades", 98),
    "claro": ("Vivienda", "necesidades", 98),
    "movistar": ("Vivienda", "necesidades", 98),
    "cabletica": ("Vivienda", "necesidades", 98),
    "liberty": ("Vivienda", "necesidades", 98),
    "aya": ("Vivienda", "necesidades", 98),
    "cnfl": ("Vivienda", "necesidades", 98),
    "jasec": ("Vivienda", "necesidades", 98),
    
    # === TRABAJO / HERRAMIENTAS ===
    "anthropic": ("Trabajo", "necesidades", 95),
    "openai": ("Trabajo", "necesidades", 95),
    "chatgpt": ("Trabajo", "necesidades", 95),
    "github": ("Trabajo", "necesidades", 95),
    "aws": ("Trabajo", "necesidades", 95),
    "google cloud": ("Trabajo", "necesidades", 95),
    "azure": ("Trabajo", "necesidades", 95),
    "vercel": ("Trabajo", "necesidades", 95),
    "heroku": ("Trabajo", "necesidades", 95),
    "digitalocean": ("Trabajo", "necesidades", 95),
    "notion": ("Trabajo", "necesidades", 95),
    "slack": ("Trabajo", "necesidades", 95),
    "zoom": ("Trabajo", "necesidades", 95),
    
    # === RETIROS ATM ===
    "atm": ("Personal", "necesidades", 90),
    "retiro": ("Personal", "necesidades", 90),
    "cajero": ("Personal", "necesidades", 90),
}

# Patrones de SINPE y transferencias
SINPE_PATTERNS: dict[str, tuple[str, str, int]] = {
    r"sinpe.*pago": ("Transferencias", "necesidades", 70),
    r"sinpe.*cable": ("Vivienda", "necesidades", 85),
    r"sinpe.*internet": ("Vivienda", "necesidades", 85),
    r"sinpe.*luz": ("Vivienda", "necesidades", 85),
    r"sinpe.*agua": ("Vivienda", "necesidades", 85),
    r"sinpe.*alquiler": ("Vivienda", "necesidades", 90),
    r"sinpe.*comida|sinpe.*donas|sinpe.*pizza": ("Comida Social", "gustos", 85),
    r"sinpe.*funeral": ("Personal", "necesidades", 90),
    r"sinpe.*pollas": ("Entretenimiento", "gustos", 90),
    r"salario|sueldo|planilla": ("_INGRESO_", "ingreso", 99),
    r"bosch": ("_INGRESO_", "ingreso", 99),
}


class SmartCategorizer:
    """
    Categorizador inteligente de 4 capas.
    
    Diseñado para:
    - Alta precisión (>95% en comercios conocidos)
    - Bajo costo (minimiza llamadas a LLM)
    - Aprendizaje continuo
    - Específico para Costa Rica
    """
    
    def __init__(self, session: Session | None = None) -> None:
        """Inicializa el categorizador."""
        self._session = session
        self._subcategories_cache: dict[str, Subcategory] | None = None
        logger.info("SmartCategorizer inicializado")
    
    @property
    def session(self) -> Session:
        """Obtiene la sesión de base de datos."""
        if self._session is None:
            raise RuntimeError("No hay sesión de base de datos configurada")
        return self._session
    
    def categorize(
        self,
        comercio: str,
        monto: Decimal | float,
        profile_id: str | None = None,
        fecha: str | None = None,
        tipo_transaccion: str | None = None,
    ) -> CategorizationResult:
        """
        Categoriza una transacción usando el sistema de 4 capas.
        
        Args:
            comercio: Nombre del comercio
            monto: Monto de la transacción
            profile_id: ID del perfil del usuario
            fecha: Fecha de la transacción (ISO format)
            tipo_transaccion: Tipo de transacción
            
        Returns:
            CategorizationResult con la categoría y metadata
        """
        comercio_clean = self._clean_merchant_name(comercio)
        monto_float = float(monto) if isinstance(monto, Decimal) else monto
        
        logger.debug(f"Categorizando: '{comercio}' -> '{comercio_clean}' (₡{monto_float:,.0f})")
        
        # CAPA 1: Determinística
        result = self._layer1_deterministic(comercio_clean, monto_float, profile_id)
        if result and result.confidence >= 80:
            logger.info(f"✅ Capa 1 ({result.source.value}): {result.subcategory_name} ({result.confidence}%)")
            return result
        
        # CAPA 2: Embeddings (si está disponible)
        embedding_result = self._layer2_embeddings(comercio_clean, monto_float, profile_id)
        if embedding_result and embedding_result.confidence >= 85:
            logger.info(f"🔍 Capa 2 (embedding): {embedding_result.subcategory_name} ({embedding_result.confidence}%)")
            return embedding_result
        
        # CAPA 3: LLM (solo si las capas anteriores no fueron suficientes)
        if not result or result.confidence < 70:
            llm_result = self._layer3_llm(comercio_clean, monto_float, fecha, tipo_transaccion)
            if llm_result:
                logger.info(f"🤖 Capa 3 (LLM): {llm_result.subcategory_name} ({llm_result.confidence}%)")
                return llm_result
        
        # Si la capa 1 dio algo pero con baja confianza, usarlo
        if result:
            result.needs_review = True
            return result
        
        # Fallback
        return self._fallback_result(comercio)
    
    def _clean_merchant_name(self, comercio: str) -> str:
        """Limpia y normaliza el nombre del comercio."""
        if not comercio:
            return ""
        
        # Convertir a minúsculas
        clean = comercio.lower().strip()
        
        # Remover caracteres especiales excepto letras, números y espacios
        clean = re.sub(r'[^\w\s]', ' ', clean)
        
        # Remover códigos de referencia largos (strings de 8+ chars con números y letras mezclados)
        # Ej: "847831OY3", "AB12CD34EF" - pero NO marcas como "bet365"
        clean = re.sub(r'\b(?=[A-Za-z]*\d)(?=\d*[A-Za-z])[A-Za-z0-9]{8,}\b', '', clean)
        
        # Remover palabras de ruido (solo términos bancarios/ubicaciones)
        noise_words = [
            'san jose', 'costa rica', 'heredia', 'alajuela', 'cartago',
            'www', 'http', 'https', 'com', 'net', 'org',
            'sucursal', 'agencia', 'tienda', 'local',
            'debit', 'credit', 'visa', 'mastercard', 'amex',
            'pos', 'tpv', 'pin',
        ]
        for word in noise_words:
            clean = re.sub(rf'\b{word}\b', ' ', clean)
        
        # Limpiar espacios múltiples
        clean = re.sub(r'\s+', ' ', clean).strip()
        
        return clean
    
    def _layer1_deterministic(
        self,
        comercio: str,
        monto: float,
        profile_id: str | None,
    ) -> CategorizationResult | None:
        """
        Capa 1: Reglas determinísticas.
        
        Orden de prioridad:
        0. Preferencias del usuario (correcciones manuales - MÁXIMA prioridad)
        1. Historial del usuario (transacciones anteriores)
        2. Contactos SINPE aprendidos
        3. Base de datos de comercios de CR
        4. Patrones SINPE
        5. Keywords de subcategorías
        """
        # 1.0 Preferencias del usuario (correcciones manuales)
        if profile_id:
            pref_result = self._check_user_preferences(comercio, profile_id)
            if pref_result:
                return pref_result
        
        # 1.1 Historial del usuario
        if profile_id:
            history_result = self._check_user_history(comercio, profile_id)
            if history_result:
                return history_result
        
        # 1.2 Contactos SINPE aprendidos
        if profile_id:
            contact_result = self._check_sinpe_contacts(comercio, profile_id)
            if contact_result:
                return contact_result
        
        # 1.3 Base de datos de comercios CR
        merchant_result = self._check_merchant_db(comercio)
        if merchant_result:
            return merchant_result
        
        # 1.4 Patrones SINPE
        sinpe_result = self._check_sinpe_patterns(comercio, monto)
        if sinpe_result:
            return sinpe_result
        
        # 1.5 Keywords de subcategorías
        keyword_result = self._check_keywords(comercio)
        if keyword_result:
            return keyword_result
        
        return None
    
    def _check_user_preferences(self, comercio: str, profile_id: str) -> CategorizationResult | None:
        """
        Busca en las preferencias guardadas del usuario (correcciones manuales).
        
        Estas tienen MÁXIMA prioridad porque el usuario explícitamente
        corrigió la categorización.
        """
        try:
            with get_session() as session:
                # Buscar preferencia que coincida con el patrón del comercio
                pref = (
                    session.query(UserMerchantPreference)
                    .filter(
                        UserMerchantPreference.profile_id == profile_id,
                        UserMerchantPreference.activa == True,
                    )
                    .all()
                )
                
                comercio_lower = comercio.lower()
                for p in pref:
                    # El patrón puede ser exacto o wildcard con %
                    pattern = p.merchant_pattern.lower().replace('%', '')
                    if pattern in comercio_lower or comercio_lower in pattern:
                        # Obtener subcategoría
                        subcat = session.query(Subcategory).filter(
                            Subcategory.id == p.subcategory_id
                        ).first()
                        
                        if subcat:
                            # Incrementar contador de uso
                            p.times_used = (p.times_used or 0) + 1
                            session.commit()
                            
                            return CategorizationResult(
                                subcategory_id=subcat.id,
                                subcategory_name=subcat.nombre,
                                category_type=subcat.category.tipo if subcat.category else "necesidades",
                                confidence=99,  # Máxima confianza - el usuario lo configuró
                                source=CategorizationSource.USER_OVERRIDE,
                                needs_review=False,
                                reasoning=f"Tu preferencia guardada: '{p.user_label or p.merchant_pattern}' → {subcat.nombre}",
                            )
        except Exception as e:
            logger.debug(f"Error buscando preferencias del usuario: {e}")
        
        return None
    
    def _check_sinpe_contacts(self, comercio: str, profile_id: str) -> CategorizationResult | None:
        """
        Busca en los contactos SINPE aprendidos del usuario.
        
        Si el usuario marcó un número como "Mamá", usamos esa info.
        """
        try:
            # Extraer número de teléfono del comercio si es SINPE
            phone_match = re.search(r'(\d{8})', comercio)
            if not phone_match:
                return None
            
            phone = phone_match.group(1)
            
            with get_session() as session:
                contact = (
                    session.query(UserContact)
                    .filter(
                        UserContact.profile_id == profile_id,
                        UserContact.phone_number == phone,
                    )
                    .first()
                )
                
                if contact and contact.default_subcategory_id:
                    subcat = session.query(Subcategory).filter(
                        Subcategory.id == contact.default_subcategory_id
                    ).first()
                    
                    if subcat:
                        return CategorizationResult(
                            subcategory_id=subcat.id,
                            subcategory_name=subcat.nombre,
                            category_type=subcat.category.tipo if subcat.category else "necesidades",
                            confidence=98,
                            source=CategorizationSource.USER_OVERRIDE,
                            needs_review=False,
                            reasoning=f"Contacto conocido: {contact.alias or contact.sinpe_name} → {subcat.nombre}",
                        )
        except Exception as e:
            logger.debug(f"Error buscando contactos SINPE: {e}")
        
        return None
    
    def _check_user_history(self, comercio: str, profile_id: str) -> CategorizationResult | None:
        """Busca en el historial del usuario."""
        try:
            with get_session() as session:
                # Buscar transacciones anteriores del mismo comercio categorizadas
                similar = (
                    session.query(Transaction)
                    .filter(
                        Transaction.profile_id == profile_id,
                        Transaction.comercio.ilike(f"%{comercio}%"),
                        Transaction.subcategory_id.isnot(None),
                        Transaction.necesita_revision == False,
                        Transaction.deleted_at.is_(None),
                    )
                    .order_by(Transaction.fecha_transaccion.desc())
                    .first()
                )
                
                if similar and similar.subcategory:
                    subcat = similar.subcategory
                    return CategorizationResult(
                        subcategory_id=subcat.id,
                        subcategory_name=subcat.nombre,
                        category_type=subcat.category.tipo if subcat.category else "necesidades",
                        confidence=95,
                        source=CategorizationSource.HISTORY,
                        needs_review=False,
                        reasoning=f"Aprendido del historial: usaste '{subcat.nombre}' antes para este comercio",
                    )
        except Exception as e:
            logger.debug(f"Error buscando en historial: {e}")
        
        return None
    
    def _check_merchant_db(self, comercio: str) -> CategorizationResult | None:
        """Busca en la base de datos de comercios de CR."""
        comercio_lower = comercio.lower()
        
        for pattern, (subcat_name, cat_type, confidence) in CR_MERCHANTS_DB.items():
            if pattern in comercio_lower:
                # Obtener ID de subcategoría
                subcat_id = self._get_subcategory_id(subcat_name)
                
                return CategorizationResult(
                    subcategory_id=subcat_id,
                    subcategory_name=subcat_name,
                    category_type=cat_type,
                    confidence=confidence,
                    source=CategorizationSource.MERCHANT_DB,
                    needs_review=confidence < 90,
                    reasoning=f"Comercio conocido: '{pattern}' → {subcat_name}",
                )
        
        return None
    
    def _check_sinpe_patterns(self, comercio: str, monto: float) -> CategorizationResult | None:
        """Analiza patrones de SINPE y transferencias."""
        comercio_lower = comercio.lower()
        
        for pattern, (subcat_name, cat_type, confidence) in SINPE_PATTERNS.items():
            if re.search(pattern, comercio_lower):
                # Caso especial: ingreso
                if subcat_name == "_INGRESO_":
                    return CategorizationResult(
                        subcategory_id=None,
                        subcategory_name="Ingreso",
                        category_type="ingreso",
                        confidence=confidence,
                        source=CategorizationSource.KEYWORD,
                        needs_review=False,
                        reasoning="Detectado como ingreso (salario)",
                        context={"is_income": True},
                    )
                
                subcat_id = self._get_subcategory_id(subcat_name)
                return CategorizationResult(
                    subcategory_id=subcat_id,
                    subcategory_name=subcat_name,
                    category_type=cat_type,
                    confidence=confidence,
                    source=CategorizationSource.KEYWORD,
                    needs_review=confidence < 80,
                    reasoning=f"Patrón SINPE: '{pattern}'",
                )
        
        # SINPE genérico basado en monto
        if "sinpe" in comercio_lower:
            if monto > 100000:
                return CategorizationResult(
                    subcategory_id=self._get_subcategory_id("Transferencias"),
                    subcategory_name="Transferencias",
                    category_type="necesidades",
                    confidence=60,
                    source=CategorizationSource.KEYWORD,
                    needs_review=True,
                    reasoning=f"SINPE genérico (monto alto: ₡{monto:,.0f})",
                )
            else:
                return CategorizationResult(
                    subcategory_id=self._get_subcategory_id("Personal"),
                    subcategory_name="Personal",
                    category_type="necesidades",
                    confidence=50,
                    source=CategorizationSource.KEYWORD,
                    needs_review=True,
                    reasoning="SINPE sin descripción clara",
                )
        
        return None
    
    def _check_keywords(self, comercio: str) -> CategorizationResult | None:
        """Busca match por keywords de subcategorías."""
        comercio_lower = comercio.lower()
        
        with get_session() as session:
            subcategories = (
                session.query(Subcategory)
                .filter(Subcategory.keywords.isnot(None))
                .all()
            )
            
            best_match = None
            best_confidence = 0
            
            for subcat in subcategories:
                if not subcat.keywords:
                    continue
                
                keywords = [k.strip().lower() for k in subcat.keywords.split(",")]
                
                for keyword in keywords:
                    if keyword and keyword in comercio_lower:
                        # Confianza basada en longitud del keyword
                        confidence = 85 if len(keyword) > 5 else 70
                        
                        if confidence > best_confidence:
                            best_confidence = confidence
                            best_match = CategorizationResult(
                                subcategory_id=subcat.id,
                                subcategory_name=subcat.nombre,
                                category_type=subcat.category.tipo if subcat.category else "necesidades",
                                confidence=confidence,
                                source=CategorizationSource.KEYWORD,
                                needs_review=confidence < 80,
                                reasoning=f"Keyword match: '{keyword}'",
                            )
            
            return best_match
    
    def _layer2_embeddings(
        self,
        comercio: str,
        monto: float,
        profile_id: str | None,
    ) -> CategorizationResult | None:
        """
        Capa 2: Búsqueda por similitud semántica.
        
        Usa embeddings pre-generados para encontrar transacciones similares
        y heredar su categoría.
        """
        try:
            # Por ahora, solo búsqueda por similitud de texto
            # TODO: Implementar con embeddings reales cuando se configure Voyage AI
            
            with get_session() as session:
                # Buscar transacciones similares por nombre de comercio
                similar_txns = (
                    session.query(Transaction)
                    .filter(
                        Transaction.subcategory_id.isnot(None),
                        Transaction.necesita_revision == False,
                        Transaction.deleted_at.is_(None),
                        # Buscar comercios que contengan palabras similares
                        Transaction.comercio.ilike(f"%{comercio[:10]}%"),
                    )
                    .limit(5)
                    .all()
                )
                
                if similar_txns:
                    # Contar categorías más comunes
                    cat_counts: dict[str, int] = {}
                    for txn in similar_txns:
                        if txn.subcategory:
                            key = txn.subcategory.id
                            cat_counts[key] = cat_counts.get(key, 0) + 1
                    
                    if cat_counts:
                        best_cat_id = max(cat_counts, key=cat_counts.get)
                        count = cat_counts[best_cat_id]
                        
                        if count >= 2:  # Al menos 2 coincidencias
                            # Obtener subcategoría
                            subcat = session.query(Subcategory).get(best_cat_id)
                            if subcat:
                                return CategorizationResult(
                                    subcategory_id=subcat.id,
                                    subcategory_name=subcat.nombre,
                                    category_type=subcat.category.tipo if subcat.category else "necesidades",
                                    confidence=85,
                                    source=CategorizationSource.EMBEDDING,
                                    needs_review=False,
                                    reasoning=f"Similar a {count} transacciones previas",
                                )
        except Exception as e:
            logger.debug(f"Error en capa de embeddings: {e}")
        
        return None
    
    def _layer3_llm(
        self,
        comercio: str,
        monto: float,
        fecha: str | None,
        tipo_transaccion: str | None,
    ) -> CategorizationResult | None:
        """
        Capa 3: Claude AI para casos difíciles.
        
        Solo se usa cuando las capas anteriores no dan suficiente confianza.
        Usa enfoque reactivo: intenta llamar y maneja errores de créditos.
        """
        try:
            # Verificar si podemos usar Claude (sin hacer llamada a la API)
            can_use, reason = can_use_claude()
            if not can_use:
                logger.info(f"⏭️ Saltando capa LLM: {reason}")
                return None
            
            import anthropic
            
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            
            # Obtener subcategorías disponibles
            with get_session() as session:
                subcats = session.query(Subcategory).all()
                categorias_json = [
                    {
                        "id": s.id,
                        "nombre": s.nombre,
                        "tipo": s.category.tipo if s.category else "necesidades",
                    }
                    for s in subcats
                ]
            
            prompt = f"""Eres un experto en finanzas personales de Costa Rica.

Categoriza esta transacción:
- Comercio: {comercio}
- Monto: ₡{monto:,.0f}
- Tipo: {tipo_transaccion or 'desconocido'}

Categorías disponibles:
{categorias_json}

Responde SOLO con JSON:
{{"id": "...", "nombre": "...", "confianza": 80, "razon": "..."}}"""

            response = client.messages.create(
                model=settings.claude_model,  # Haiku 4.5 - rápido y económico
                max_tokens=200,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            
            import json
            text = response.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("```")[1].replace("json", "").strip()
            
            result = json.loads(text)
            
            return CategorizationResult(
                subcategory_id=result.get("id"),
                subcategory_name=result.get("nombre", "Sin categoría"),
                category_type="necesidades",  # TODO: obtener del resultado
                confidence=result.get("confianza", 70),
                source=CategorizationSource.LLM,
                needs_review=result.get("confianza", 70) < 80,
                reasoning=result.get("razon", "Categorizado por IA"),
            )
        
        except anthropic.APIStatusError as e:
            # Manejar error de créditos y actualizar estado global
            if handle_claude_error(e):
                logger.info("⏭️ Capa LLM: Créditos agotados, saltando")
                return None
            logger.error(f"Error de API en capa LLM: {e}")
            return None
            
        except Exception as e:
            logger.error(f"Error en capa LLM: {e}")
            return None
    
    def _fallback_result(self, comercio: str) -> CategorizationResult:
        """Resultado de fallback cuando no se puede categorizar."""
        return CategorizationResult(
            subcategory_id=None,
            subcategory_name="Sin categorizar",
            category_type="necesidades",
            confidence=0,
            source=CategorizationSource.FALLBACK,
            needs_review=True,
            reasoning=f"No se pudo categorizar: '{comercio}'",
        )
    
    def _get_subcategory_id(self, nombre: str) -> str | None:
        """Obtiene el ID de una subcategoría por nombre."""
        try:
            with get_session() as session:
                subcat = (
                    session.query(Subcategory)
                    .filter(Subcategory.nombre == nombre)
                    .first()
                )
                return subcat.id if subcat else None
        except Exception:
            return None
    
    # ========================================================================
    # FEEDBACK LOOP - Aprendizaje continuo
    # ========================================================================
    
    def record_user_correction(
        self,
        transaction_id: str,
        correct_subcategory_id: str,
        profile_id: str,
    ) -> None:
        """
        Registra una corrección del usuario para mejorar el modelo.
        
        Este feedback se usa para:
        1. Actualizar el historial del usuario
        2. Mejorar la precisión futura para comercios similares
        """
        try:
            with get_session() as session:
                # Actualizar la transacción
                txn = session.query(Transaction).get(transaction_id)
                if txn:
                    txn.subcategory_id = correct_subcategory_id
                    txn.necesita_revision = False
                    txn.confianza_categoria = 100
                    txn.notas = (txn.notas or "") + " [Corregido por usuario]"
                    session.commit()
                    
                    logger.info(
                        f"📝 Corrección registrada: {txn.comercio} → {correct_subcategory_id}"
                    )
        except Exception as e:
            logger.error(f"Error registrando corrección: {e}")


# Función de conveniencia para uso simple
def categorize_transaction(
    comercio: str,
    monto: float,
    profile_id: str | None = None,
) -> dict[str, Any]:
    """
    Función de conveniencia para categorizar una transacción.
    
    Returns:
        dict compatible con el formato anterior de TransactionCategorizer
    """
    categorizer = SmartCategorizer()
    result = categorizer.categorize(comercio, monto, profile_id)
    return result.to_dict()
