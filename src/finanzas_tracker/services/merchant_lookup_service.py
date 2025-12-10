"""Servicio de Búsqueda de Comercios Desconocidos con Claude.

Cuando encontramos un comercio que no está en la base de datos:
1. Claude intenta inferir qué tipo de negocio es por el nombre
2. Si no puede, hace una búsqueda conceptual
3. Pregunta al usuario para confirmar
4. Guarda el resultado para futuros usuarios

Ejemplos:
- "SPOON SAN JOSE" → Restaurante (Claude infiere por nombre)
- "INVU" → Servicios Financieros (Claude busca qué es INVU)
- "CFIA" → Gobierno/Trámites (Claude sabe que es el Colegio de Ingenieros)
"""

__all__ = [
    "MerchantLookupService",
    "MerchantInfo",
]

import logging
import re
from dataclasses import dataclass
from typing import cast
from uuid import uuid4

import anthropic
from sqlalchemy.orm import Session

from finanzas_tracker.config.settings import settings
from finanzas_tracker.core.claude_credits import can_use_claude, handle_claude_error
from finanzas_tracker.core.retry import retry_on_anthropic_error
from finanzas_tracker.models.merchant import Merchant


logger = logging.getLogger(__name__)


@dataclass
class MerchantInfo:
    """Información de un comercio identificado."""
    nombre_normalizado: str
    categoria: str
    subcategoria: str | None
    tipo_negocio: str
    es_ambiguo: bool
    categorias_posibles: list[str] | None
    descripcion: str | None
    confianza: float


class MerchantLookupService:
    """
    Servicio para identificar comercios desconocidos.
    
    Flujo:
    1. Recibe nombre raw del comercio (ej: "SUBWAY MOMENTUM PINARES")
    2. Busca en BD si ya existe normalizado
    3. Si no existe, Claude lo identifica
    4. Guarda en BD para futuros usuarios
    """

    # System prompt para Claude
    SYSTEM_PROMPT = """Eres un experto en comercios de Costa Rica y Centroamérica.
Tu trabajo es identificar qué tipo de negocio es un comercio basándote en su nombre.

Debes responder en JSON con esta estructura:
{
  "nombre_normalizado": "Nombre limpio del comercio (ej: 'Subway', 'McDonald's')",
  "categoria": "Categoría principal (ver lista abajo)",
  "subcategoria": "Más específico si aplica",
  "tipo_negocio": "Código del tipo (ver lista)",
  "es_ambiguo": true/false,
  "categorias_posibles": ["Lista", "si", "es_ambiguo"],
  "descripcion": "Breve descripción del negocio",
  "confianza": 0-100
}

CATEGORÍAS PRINCIPALES:
- Alimentación (restaurantes, cafeterías, comida rápida)
- Supermercado (abarrotes, tiendas de conveniencia)
- Transporte (gasolineras, parqueos, peajes)
- Entretenimiento (cine, streaming, deportes)
- Hogar (ferreterías, muebles, decoración)
- Salud (farmacias, clínicas, ópticas)
- Ropa y Accesorios (tiendas de ropa, zapaterías)
- Tecnología (electrónica, celulares, computadoras)
- Servicios (gimnasios, lavanderías, belleza)
- Gobierno/Trámites (CCSS, INVU, municipalidades)
- Educación (universidades, cursos, librerías)
- Servicios Financieros (bancos, seguros)

TIPOS DE NEGOCIO:
- food_service (restaurantes, cafés)
- retail (tiendas)
- gas_station (gasolineras)
- healthcare (salud)
- entertainment (entretenimiento)
- government (gobierno)
- financial (bancos, seguros)
- education (educación)
- professional_services (servicios profesionales)
- other

EJEMPLOS DE COSTA RICA QUE DEBES CONOCER:
- AUTOMERCADO, PALI, MAXI PALI, MAS X MENOS = Supermercado
- UBER, DIDI = Transporte
- RAPPI, HUGO = Delivery (puede ser comida o supermercado)
- CCSS, INS, ICE = Gobierno
- KOLBI, CLARO, LIBERTY = Telecomunicaciones
- PRICESMART, EPA = Retail grande (ambiguo)
- SPOON, ROSTI POLLO, QUIZNOS = Restaurantes

Si no reconoces el nombre, usa tu mejor juicio basándote en:
1. Palabras clave en el nombre (RESTAURANTE, FARMACIA, etc.)
2. Patrones comunes (nombres que terminan en S.A., LTDA)
3. Si no puedes identificarlo, pon confianza < 50

Responde solo en JSON válido."""

    def __init__(self, db: Session) -> None:
        """Inicializa el servicio."""
        self.db = db
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model

    def buscar_o_identificar(
        self,
        nombre_raw: str,
    ) -> MerchantInfo | None:
        """
        Busca un comercio en la BD o lo identifica con Claude.
        
        Args:
            nombre_raw: Nombre del comercio como viene del banco
            
        Returns:
            MerchantInfo con la información del comercio
        """
        if not nombre_raw or len(nombre_raw.strip()) < 2:
            return None
        
        nombre_limpio = self._limpiar_nombre(nombre_raw)
        
        # 1. Buscar en BD
        merchant = self._buscar_en_bd(nombre_limpio)
        if merchant:
            return self._merchant_a_info(merchant)
        
        # 2. Identificar con Claude
        info = self._identificar_con_claude(nombre_raw, nombre_limpio)
        
        # 3. Si tiene buena confianza, guardar en BD
        if info and info.confianza >= 0.70:
            self._guardar_en_bd(info)
        
        return info

    def _limpiar_nombre(self, nombre: str) -> str:
        """Limpia el nombre del comercio para búsqueda."""
        # Quitar números de sucursal
        limpio = re.sub(r"\s+\d+$", "", nombre.strip())
        # Quitar ubicación común
        limpio = re.sub(r"\s+(SAN JOSE|HEREDIA|ALAJUELA|CARTAGO|ESCAZU|SANTA ANA|MOMENTUM|PLAZA|MALL).*", "", limpio, flags=re.IGNORECASE)
        # Quitar espacios extras
        limpio = " ".join(limpio.split())
        return limpio.upper()

    def _buscar_en_bd(self, nombre: str) -> Merchant | None:
        """Busca el comercio en la base de datos."""
        # Buscar exacto
        merchant = self.db.query(Merchant).filter(
            Merchant.nombre_normalizado.ilike(nombre)
        ).first()
        
        if merchant:
            return merchant
        
        # Buscar parcial
        merchant = self.db.query(Merchant).filter(
            Merchant.nombre_normalizado.ilike(f"%{nombre}%")
        ).first()
        
        return merchant

    @retry_on_anthropic_error(max_attempts=2, max_wait=8)
    def _identificar_con_claude(
        self,
        nombre_raw: str,
        nombre_limpio: str,
    ) -> MerchantInfo | None:
        """Usa Claude para identificar el comercio."""
        can_use, reason = can_use_claude()
        if not can_use:
            logger.warning(f"Claude no disponible: {reason}")
            return self._info_por_defecto(nombre_limpio)
        
        try:
            prompt = f"""Identifica este comercio de Costa Rica:

Nombre raw: {nombre_raw}
Nombre limpio: {nombre_limpio}

Responde SOLO con el JSON, sin explicación adicional."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                temperature=0.2,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            
            first_block = response.content[0]
            if not hasattr(first_block, "text"):
                return self._info_por_defecto(nombre_limpio)
            
            return self._parse_respuesta_claude(cast(str, first_block.text), nombre_limpio)
            
        except anthropic.APIStatusError as e:
            handle_claude_error(e)
            return self._info_por_defecto(nombre_limpio)
        except Exception as e:
            logger.error(f"Error identificando comercio: {e}")
            return self._info_por_defecto(nombre_limpio)

    def _parse_respuesta_claude(
        self,
        response: str,
        nombre_fallback: str,
    ) -> MerchantInfo:
        """Parsea la respuesta JSON de Claude."""
        import json
        
        # Extraer JSON
        json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
        if not json_match:
            return self._info_por_defecto(nombre_fallback)
        
        try:
            data = json.loads(json_match.group())
            return MerchantInfo(
                nombre_normalizado=data.get("nombre_normalizado", nombre_fallback),
                categoria=data.get("categoria", "Otros"),
                subcategoria=data.get("subcategoria"),
                tipo_negocio=data.get("tipo_negocio", "other"),
                es_ambiguo=data.get("es_ambiguo", False),
                categorias_posibles=data.get("categorias_posibles"),
                descripcion=data.get("descripcion"),
                confianza=float(data.get("confianza", 50)) / 100,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Error parseando respuesta de Claude: {e}")
            return self._info_por_defecto(nombre_fallback)

    def _info_por_defecto(self, nombre: str) -> MerchantInfo:
        """Retorna info por defecto cuando no se puede identificar."""
        return MerchantInfo(
            nombre_normalizado=nombre,
            categoria="Otros",
            subcategoria=None,
            tipo_negocio="other",
            es_ambiguo=True,
            categorias_posibles=None,
            descripcion=None,
            confianza=0.30,
        )

    def _merchant_a_info(self, merchant: Merchant) -> MerchantInfo:
        """Convierte un Merchant de BD a MerchantInfo."""
        return MerchantInfo(
            nombre_normalizado=merchant.nombre_normalizado,
            categoria=merchant.categoria_principal,
            subcategoria=merchant.subcategoria,
            tipo_negocio=merchant.tipo_negocio,
            es_ambiguo=merchant.es_ambiguo,
            categorias_posibles=merchant.categorias_posibles,
            descripcion=merchant.que_vende,
            confianza=0.95,  # Alta confianza si está en BD
        )

    def _guardar_en_bd(self, info: MerchantInfo) -> None:
        """Guarda el comercio identificado en la BD."""
        # Verificar que no existe
        existing = self.db.query(Merchant).filter(
            Merchant.nombre_normalizado == info.nombre_normalizado
        ).first()
        
        if existing:
            return
        
        merchant = Merchant(
            id=str(uuid4()),
            nombre_normalizado=info.nombre_normalizado,
            categoria_principal=info.categoria,
            subcategoria=info.subcategoria,
            tipo_negocio=info.tipo_negocio,
            es_ambiguo=info.es_ambiguo,
            categorias_posibles=info.categorias_posibles,
            que_vende=info.descripcion,
        )
        
        self.db.add(merchant)
        self.db.commit()
        
        logger.info(f"🏪 Comercio guardado: {info.nombre_normalizado} ({info.categoria})")


def identificar_comercio(db: Session, nombre: str) -> MerchantInfo | None:
    """Helper para identificar un comercio rápidamente."""
    service = MerchantLookupService(db)
    return service.buscar_o_identificar(nombre)
