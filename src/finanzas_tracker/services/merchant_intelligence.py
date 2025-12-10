"""Servicio de Inteligencia de Comercios - Investigación automática.

Este servicio investiga comercios desconocidos usando:
1. Base de datos local de comercios conocidos
2. Búsqueda en internet (via Claude/APIs)
3. Confirmación con el usuario cuando hay incertidumbre

Esto permite categorizar correctamente comercios como:
- "MOVE" → Move Concerts (Entretenimiento), no Fitness
- "SERVI INDOOR" → Gasolinera Indoor (Transporte), no Fitness
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

import anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.core.logging import get_logger


logger = get_logger(__name__)


class ConfidenceLevel(Enum):
    """Nivel de confianza en la categorización."""
    
    HIGH = "high"           # 90%+ - Categorizar automáticamente
    MEDIUM = "medium"       # 60-90% - Categorizar pero marcar para revisión
    LOW = "low"             # 30-60% - Preguntar al usuario
    UNKNOWN = "unknown"     # <30% - Investigar y preguntar


@dataclass
class MerchantIntelligence:
    """Resultado de investigación de un comercio."""
    
    merchant_name: str
    merchant_name_normalized: str
    business_type: str  # Tipo de negocio (restaurante, gasolinera, tienda, etc.)
    suggested_category: str
    suggested_subcategory: str | None
    confidence: ConfidenceLevel
    confidence_score: float  # 0.0 - 1.0
    source: str  # "local_db", "ai_research", "user_confirmed"
    reasoning: str  # Explicación de por qué se categorizó así
    country: str  # País del comercio (para contexto CR)
    is_costa_rica_business: bool
    keywords: list[str]
    alternative_categories: list[dict]  # Otras posibles categorías


# Base de conocimiento local de Costa Rica
CR_MERCHANT_DATABASE = {
    # Gasolineras
    "servi indoor": {
        "type": "gasolinera",
        "category": "Transporte",
        "subcategory": "Gasolina",
        "confidence": 0.95,
        "keywords": ["gas", "gasolina", "combustible"],
    },
    "delta": {
        "type": "gasolinera", 
        "category": "Transporte",
        "subcategory": "Gasolina",
        "confidence": 0.90,
    },
    "total": {
        "type": "gasolinera",
        "category": "Transporte", 
        "subcategory": "Gasolina",
        "confidence": 0.85,
    },
    "uno": {
        "type": "gasolinera",
        "category": "Transporte",
        "subcategory": "Gasolina", 
        "confidence": 0.70,  # "UNO" puede ser otras cosas
    },
    
    # Entretenimiento - Conciertos/Eventos
    "move": {
        "type": "ticketera_eventos",
        "category": "Entretenimiento",
        "subcategory": "Conciertos",
        "confidence": 0.85,
        "keywords": ["move concerts", "conciertos", "eventos", "boletos"],
        "note": "Move Concerts CR - Ticketera de eventos y conciertos",
    },
    "move concerts": {
        "type": "ticketera_eventos",
        "category": "Entretenimiento",
        "subcategory": "Conciertos",
        "confidence": 0.99,
    },
    "e-ticket": {
        "type": "ticketera_eventos",
        "category": "Entretenimiento",
        "subcategory": "Eventos",
        "confidence": 0.90,
    },
    
    # Supermercados
    "pricesmart": {
        "type": "supermercado_mayorista",
        "category": "Supermercado",
        "subcategory": "Mayorista",
        "confidence": 0.99,
    },
    "price smart": {
        "type": "supermercado_mayorista",
        "category": "Supermercado",
        "subcategory": "Mayorista", 
        "confidence": 0.99,
    },
    "automercado": {
        "type": "supermercado",
        "category": "Supermercado",
        "subcategory": "Supermercado",
        "confidence": 0.99,
    },
    "walmart": {
        "type": "supermercado_grande",
        "category": "Supermercado",
        "subcategory": "Supermercado",
        "confidence": 0.95,
    },
    "mas x menos": {
        "type": "supermercado",
        "category": "Supermercado",
        "subcategory": "Supermercado",
        "confidence": 0.99,
    },
    "pali": {
        "type": "supermercado_descuento",
        "category": "Supermercado",
        "subcategory": "Supermercado",
        "confidence": 0.99,
    },
    
    # Comida rápida
    "mcdonald": {
        "type": "comida_rapida",
        "category": "Comida",
        "subcategory": "Fast Food",
        "confidence": 0.99,
    },
    "mc donald": {
        "type": "comida_rapida",
        "category": "Comida",
        "subcategory": "Fast Food",
        "confidence": 0.99,
    },
    "subway": {
        "type": "comida_rapida",
        "category": "Comida",
        "subcategory": "Fast Food",
        "confidence": 0.99,
    },
    "dunkin": {
        "type": "cafeteria",
        "category": "Comida",
        "subcategory": "Café",
        "confidence": 0.95,
    },
    "taco bell": {
        "type": "comida_rapida",
        "category": "Comida",
        "subcategory": "Fast Food",
        "confidence": 0.99,
    },
    
    # Cafeterías
    "bread house": {
        "type": "panaderia_cafeteria",
        "category": "Comida",
        "subcategory": "Panadería",
        "confidence": 0.95,
    },
    "starbucks": {
        "type": "cafeteria",
        "category": "Comida",
        "subcategory": "Café",
        "confidence": 0.99,
    },
    
    # Entretenimiento - Deportes
    "club sport cartagines": {
        "type": "club_deportivo",
        "category": "Entretenimiento",
        "subcategory": "Deportes",
        "confidence": 0.99,
        "keywords": ["fútbol", "cartaginés", "estadio"],
    },
    "saprissa": {
        "type": "club_deportivo",
        "category": "Entretenimiento",
        "subcategory": "Deportes",
        "confidence": 0.95,
    },
    
    # Apuestas
    "bet365": {
        "type": "apuestas_online",
        "category": "Entretenimiento",
        "subcategory": "Apuestas",
        "confidence": 0.99,
        "note": "Sitio de apuestas deportivas",
    },
    
    # Tecnología
    "anthropic": {
        "type": "servicio_ai",
        "category": "Tecnología",
        "subcategory": "Suscripciones",
        "confidence": 0.99,
        "note": "Claude AI - Servicio de inteligencia artificial",
    },
    "amazon": {
        "type": "ecommerce",
        "category": "Compras",
        "subcategory": "Online",
        "confidence": 0.85,  # Puede ser muchas cosas
    },
    "amazon prime": {
        "type": "suscripcion",
        "category": "Suscripciones",
        "subcategory": "Streaming",
        "confidence": 0.95,
    },
    
    # Transporte
    "uber": {
        "type": "transporte_app",
        "category": "Transporte",
        "subcategory": "Ride-sharing",
        "confidence": 0.99,
    },
    "didi": {
        "type": "transporte_app",
        "category": "Transporte",
        "subcategory": "Ride-sharing",
        "confidence": 0.99,
    },
    "parqueo": {
        "type": "estacionamiento",
        "category": "Transporte",
        "subcategory": "Parqueo",
        "confidence": 0.90,
    },
    
    # Servicios públicos
    "municipalidad": {
        "type": "gobierno_local",
        "category": "Servicios",
        "subcategory": "Impuestos",
        "confidence": 0.95,
    },
    "ice": {
        "type": "servicio_publico",
        "category": "Servicios",
        "subcategory": "Electricidad/Internet",
        "confidence": 0.95,
    },
    "aya": {
        "type": "servicio_publico",
        "category": "Servicios",
        "subcategory": "Agua",
        "confidence": 0.99,
    },
    
    # Gimnasios (los reales)
    "smart fit": {
        "type": "gimnasio",
        "category": "Fitness",
        "subcategory": "Gimnasio",
        "confidence": 0.99,
    },
    "world gym": {
        "type": "gimnasio",
        "category": "Fitness",
        "subcategory": "Gimnasio",
        "confidence": 0.99,
    },
    "multispa": {
        "type": "gimnasio",
        "category": "Fitness",
        "subcategory": "Gimnasio",
        "confidence": 0.95,
    },
}


class MerchantIntelligenceService:
    """
    Servicio de inteligencia para identificar y categorizar comercios.
    
    Estrategia de 4 capas:
    1. Base de datos local de comercios conocidos de CR
    2. Búsqueda por embeddings de comercios similares
    3. Investigación con Claude AI
    4. Confirmación con el usuario si hay incertidumbre
    """
    
    def __init__(self, db: Session | None = None):
        self.db = db
        self.client: anthropic.Anthropic | None = None
        self._init_anthropic()
        logger.info("MerchantIntelligenceService inicializado")
    
    def _init_anthropic(self) -> None:
        """Inicializa cliente de Anthropic si hay API key."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            self.client = anthropic.Anthropic(api_key=api_key)
            logger.info("Cliente Anthropic configurado para investigación")
        else:
            logger.warning("Sin ANTHROPIC_API_KEY - investigación AI deshabilitada")
    
    def investigate_merchant(
        self,
        merchant_name: str,
        amount: Decimal | None = None,
        city: str | None = None,
        country: str | None = None,
        transaction_type: str | None = None,
    ) -> MerchantIntelligence:
        """
        Investiga un comercio para determinar su categoría.
        
        Args:
            merchant_name: Nombre del comercio (ej: "SERVI INDOOR")
            amount: Monto de la transacción (para contexto)
            city: Ciudad de la transacción
            country: País de la transacción
            transaction_type: Tipo de transacción (compra, etc.)
        
        Returns:
            MerchantIntelligence con toda la información recopilada
        """
        merchant_normalized = self._normalize_merchant_name(merchant_name)
        
        # Capa 1: Buscar en base de datos local
        local_result = self._search_local_database(merchant_normalized)
        if local_result and local_result.confidence_score >= 0.85:
            logger.info(f"Comercio '{merchant_name}' encontrado en BD local: {local_result.suggested_category}")
            return local_result
        
        # Capa 2: Buscar por embeddings (si hay DB)
        if self.db:
            embedding_result = self._search_by_embedding(merchant_normalized)
            if embedding_result and embedding_result.confidence_score >= 0.80:
                logger.info(f"Comercio '{merchant_name}' encontrado por embedding: {embedding_result.suggested_category}")
                return embedding_result
        
        # Capa 3: Investigar con Claude AI
        if self.client:
            ai_result = self._research_with_ai(
                merchant_name=merchant_name,
                merchant_normalized=merchant_normalized,
                amount=amount,
                city=city,
                country=country or "Costa Rica",
                transaction_type=transaction_type,
            )
            if ai_result:
                logger.info(f"Comercio '{merchant_name}' investigado por AI: {ai_result.suggested_category}")
                return ai_result
        
        # Si todo falla, retornar con baja confianza
        logger.warning(f"Comercio '{merchant_name}' no identificado - requiere confirmación manual")
        return MerchantIntelligence(
            merchant_name=merchant_name,
            merchant_name_normalized=merchant_normalized,
            business_type="desconocido",
            suggested_category="Sin categoría",
            suggested_subcategory=None,
            confidence=ConfidenceLevel.UNKNOWN,
            confidence_score=0.0,
            source="none",
            reasoning="No se pudo identificar este comercio. Se requiere confirmación del usuario.",
            country=country or "Costa Rica",
            is_costa_rica_business=True,
            keywords=[],
            alternative_categories=[],
        )
    
    def _normalize_merchant_name(self, name: str) -> str:
        """Normaliza el nombre del comercio para búsqueda."""
        # Limpiar y normalizar
        normalized = name.lower().strip()
        
        # Remover caracteres especiales comunes en nombres de comercios
        normalized = re.sub(r'[*\-_#@!$%^&()+=\[\]{}|\\:";\'<>,.?/]', ' ', normalized)
        
        # Remover números de sucursal, fechas, etc.
        normalized = re.sub(r'\b\d{2,}\b', '', normalized)  # Números de 2+ dígitos
        normalized = re.sub(r'\b(sucursal|suc|tienda|store)\b', '', normalized)
        
        # Remover ubicaciones comunes
        locations = ['tres rios', 'san jose', 'heredia', 'cartago', 'alajuela', 
                     'escazu', 'curridabat', 'pinares', 'ayarco', 'america free']
        for loc in locations:
            normalized = normalized.replace(loc, '')
        
        # Colapsar espacios múltiples
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _search_local_database(self, merchant_normalized: str) -> MerchantIntelligence | None:
        """Busca en la base de datos local de comercios conocidos."""
        # Buscar coincidencia exacta
        if merchant_normalized in CR_MERCHANT_DATABASE:
            data = CR_MERCHANT_DATABASE[merchant_normalized]
            return self._create_intelligence_from_db(merchant_normalized, data)
        
        # Buscar coincidencia parcial
        for key, data in CR_MERCHANT_DATABASE.items():
            if key in merchant_normalized or merchant_normalized in key:
                # Ajustar confianza por match parcial
                adjusted_confidence = data.get("confidence", 0.8) * 0.9
                return self._create_intelligence_from_db(
                    merchant_normalized, 
                    {**data, "confidence": adjusted_confidence}
                )
        
        return None
    
    def _create_intelligence_from_db(
        self, 
        merchant_name: str, 
        data: dict
    ) -> MerchantIntelligence:
        """Crea MerchantIntelligence desde datos de la base local."""
        confidence_score = data.get("confidence", 0.8)
        
        if confidence_score >= 0.90:
            confidence = ConfidenceLevel.HIGH
        elif confidence_score >= 0.70:
            confidence = ConfidenceLevel.MEDIUM
        elif confidence_score >= 0.40:
            confidence = ConfidenceLevel.LOW
        else:
            confidence = ConfidenceLevel.UNKNOWN
        
        return MerchantIntelligence(
            merchant_name=merchant_name,
            merchant_name_normalized=merchant_name,
            business_type=data.get("type", "desconocido"),
            suggested_category=data.get("category", "Sin categoría"),
            suggested_subcategory=data.get("subcategory"),
            confidence=confidence,
            confidence_score=confidence_score,
            source="local_db",
            reasoning=data.get("note", f"Identificado como {data.get('type', 'comercio')} en base de datos local de Costa Rica."),
            country="Costa Rica",
            is_costa_rica_business=True,
            keywords=data.get("keywords", []),
            alternative_categories=[],
        )
    
    def _search_by_embedding(self, merchant_normalized: str) -> MerchantIntelligence | None:
        """Busca comercios similares usando embeddings."""
        # TODO: Implementar búsqueda por embeddings cuando tengamos suficientes datos
        # Por ahora retornamos None
        return None
    
    def _research_with_ai(
        self,
        merchant_name: str,
        merchant_normalized: str,
        amount: Decimal | None,
        city: str | None,
        country: str,
        transaction_type: str | None,
    ) -> MerchantIntelligence | None:
        """Investiga el comercio usando Claude AI."""
        if not self.client:
            return None
        
        prompt = f"""Eres un experto en comercios de Costa Rica. Necesito identificar qué tipo de negocio es este:

COMERCIO: {merchant_name}
NOMBRE NORMALIZADO: {merchant_normalized}
MONTO: {amount or 'No especificado'} CRC
CIUDAD: {city or 'No especificada'}
PAÍS: {country}
TIPO DE TRANSACCIÓN: {transaction_type or 'compra'}

Por favor investiga qué tipo de negocio es este comercio y responde en JSON:

{{
    "business_type": "tipo de negocio (ej: gasolinera, restaurante, supermercado, ticketera, etc.)",
    "category": "categoría principal (Comida, Transporte, Entretenimiento, Servicios, Tecnología, Salud, Compras, Supermercado, Fitness, Suscripciones)",
    "subcategory": "subcategoría específica",
    "confidence": 0.0-1.0,
    "reasoning": "explicación de por qué llegaste a esta conclusión",
    "is_costa_rica_business": true/false,
    "keywords": ["palabras", "clave", "relacionadas"],
    "alternative_categories": [
        {{"category": "otra opción", "probability": 0.0-1.0}}
    ]
}}

IMPORTANTE:
- En Costa Rica, "SERVI INDOOR" es una cadena de GASOLINERAS, NO un gimnasio
- "MOVE" en Costa Rica usualmente es "Move Concerts", una ticketera de conciertos y eventos
- Si no estás seguro, indica confidence bajo
- Responde SOLO el JSON, sin explicaciones adicionales
"""
        
        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = message.content[0].text.strip()
            
            # Extraer JSON de la respuesta
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                logger.warning(f"No se pudo parsear respuesta AI para '{merchant_name}'")
                return None
            
            data = json.loads(json_match.group())
            
            confidence_score = float(data.get("confidence", 0.5))
            
            if confidence_score >= 0.85:
                confidence = ConfidenceLevel.HIGH
            elif confidence_score >= 0.60:
                confidence = ConfidenceLevel.MEDIUM
            elif confidence_score >= 0.30:
                confidence = ConfidenceLevel.LOW
            else:
                confidence = ConfidenceLevel.UNKNOWN
            
            return MerchantIntelligence(
                merchant_name=merchant_name,
                merchant_name_normalized=merchant_normalized,
                business_type=data.get("business_type", "desconocido"),
                suggested_category=data.get("category", "Sin categoría"),
                suggested_subcategory=data.get("subcategory"),
                confidence=confidence,
                confidence_score=confidence_score,
                source="ai_research",
                reasoning=data.get("reasoning", "Investigado con AI"),
                country=country,
                is_costa_rica_business=data.get("is_costa_rica_business", True),
                keywords=data.get("keywords", []),
                alternative_categories=data.get("alternative_categories", []),
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de AI: {e}")
            return None
        except Exception as e:
            logger.error(f"Error en investigación AI: {e}")
            return None
    
    def should_ask_user(self, intelligence: MerchantIntelligence) -> bool:
        """Determina si debemos preguntar al usuario."""
        return intelligence.confidence in [ConfidenceLevel.LOW, ConfidenceLevel.UNKNOWN]
    
    def get_question_for_user(self, intelligence: MerchantIntelligence) -> dict:
        """Genera la pregunta para el usuario."""
        if intelligence.confidence == ConfidenceLevel.UNKNOWN:
            return {
                "question": f"No reconozco el comercio '{intelligence.merchant_name}'. ¿Qué tipo de negocio es?",
                "type": "open_ended",
                "suggestions": [
                    "Restaurante/Comida",
                    "Supermercado",
                    "Gasolinera",
                    "Entretenimiento/Eventos",
                    "Tecnología/Suscripción",
                    "Transporte",
                    "Otro"
                ],
            }
        else:
            alternatives = [
                intelligence.suggested_category,
                *[alt["category"] for alt in intelligence.alternative_categories[:3]]
            ]
            return {
                "question": f"El comercio '{intelligence.merchant_name}' parece ser {intelligence.business_type}. ¿Es correcto categorizarlo como '{intelligence.suggested_category}'?",
                "type": "confirmation",
                "suggested": intelligence.suggested_category,
                "alternatives": alternatives,
                "reasoning": intelligence.reasoning,
            }
    
    def learn_from_correction(
        self,
        merchant_name: str,
        original_category: str,
        correct_category: str,
        correct_subcategory: str | None = None,
        business_type: str | None = None,
    ) -> None:
        """Aprende de una corrección del usuario."""
        # Normalizar nombre
        normalized = self._normalize_merchant_name(merchant_name)
        
        # Agregar a la base de datos en memoria (en producción iría a la BD)
        CR_MERCHANT_DATABASE[normalized] = {
            "type": business_type or "user_defined",
            "category": correct_category,
            "subcategory": correct_subcategory,
            "confidence": 0.99,  # Usuario siempre tiene razón
            "note": f"Corregido por usuario. Original: {original_category}",
            "keywords": [],
        }
        
        logger.info(f"Aprendido: '{merchant_name}' → {correct_category} (corregido de {original_category})")
        
        # TODO: Persistir en base de datos
        # TODO: Generar embedding del comercio para similarity search
