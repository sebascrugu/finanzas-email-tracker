"""Servicio de categorización inteligente de transacciones con Claude AI."""

import json
from typing import Any

import anthropic

from finanzas_tracker.config.settings import settings
from finanzas_tracker.core.constants import (
    AUTO_CATEGORIZE_CONFIDENCE_THRESHOLD,
    HIGH_CONFIDENCE_SCORE,
    KEYWORD_MIN_LENGTH_FOR_HIGH_CONFIDENCE,
    MEDIUM_CONFIDENCE_SCORE,
)
from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.core.retry import retry_on_anthropic_error
from finanzas_tracker.models.category import Subcategory


logger = get_logger(__name__)


class TransactionCategorizer:
    """
    Servicio para categorizar transacciones usando:
    1. Keywords automáticos (gasolinera → Transporte)
    2. Claude AI para casos ambiguos (Walmart → ¿supermercado o shopping?)
    3. Aprendizaje de patrones del usuario
    """

    def __init__(self) -> None:
        """Inicializa el categorizador."""
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        logger.info("TransactionCategorizer inicializado")

    def categorize(
        self,
        comercio: str,
        monto_crc: float,
        tipo_transaccion: str,
        profile_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Categoriza una transacción.

        Args:
            comercio: Nombre del comercio
            monto_crc: Monto en colones
            tipo_transaccion: Tipo de transacción
            profile_id: ID del perfil (para aprendizaje del historial)

        Returns:
            dict con:
            - subcategory_id: ID de la subcategoría (si está seguro)
            - categoria_sugerida: Nombre de la subcategoría sugerida
            - necesita_revision: Si necesita revisión manual
            - confianza: Nivel de confianza (0-100)
            - alternativas: Lista de alternativas posibles
            - razon: Razón de la sugerencia
        """
        logger.info(f"Categorizando: {comercio} - ₡{monto_crc:,.2f}")

        # 0. Aprendizaje: buscar transacciones anteriores del mismo comercio
        learned_match = self._categorize_from_history(comercio, profile_id)
        if learned_match:
            logger.debug(
                f"🧠 Aprendido de historial: {learned_match['categoria_sugerida']} "
                f"(confianza: {learned_match['confianza']}%)"
            )
            return learned_match

        # 1. Intentar categorización por keywords
        keyword_match = self._categorize_by_keywords(comercio)
        if keyword_match:
            logger.debug(
                f" Match por keywords: {keyword_match['categoria_sugerida']} "
                f"(confianza: {keyword_match['confianza']}%)"
            )
            return keyword_match

        # 2. Usar Claude AI para casos ambiguos
        logger.debug(f" Usando Claude AI para: {comercio}")
        return self._categorize_with_claude(
            comercio=comercio,
            monto_crc=monto_crc,
            tipo_transaccion=tipo_transaccion,
        )

    def _categorize_by_keywords(self, comercio: str) -> dict[str, Any] | None:
        """
        Intenta categorizar usando keywords de las subcategorías.

        Retorna None si no encuentra match claro.
        """
        comercio_lower = comercio.lower()

        with get_session() as session:
            # Obtener todas las subcategorías con keywords
            subcategories = (
                session.query(Subcategory).filter(Subcategory.keywords.isnot(None)).all()
            )

            matches = []
            for subcat in subcategories:
                if not subcat.keywords:
                    continue

                keywords = [k.strip().lower() for k in subcat.keywords.split(",")]

                # Buscar keywords en el nombre del comercio
                for keyword in keywords:
                    if keyword in comercio_lower:
                        # Calcular confianza basada en qué tan específico es el match
                        confianza = (
                            HIGH_CONFIDENCE_SCORE
                            if len(keyword) > KEYWORD_MIN_LENGTH_FOR_HIGH_CONFIDENCE
                            else MEDIUM_CONFIDENCE_SCORE
                        )
                        matches.append(
                            {
                                "subcategory_id": subcat.id,
                                "categoria_sugerida": subcat.nombre_completo,
                                "confianza": confianza,
                                "keyword_matched": keyword,
                            }
                        )

            if not matches:
                return None

            # Si hay un solo match con buena confianza → asignar automáticamente
            first_match_confianza = matches[0]["confianza"]
            if (
                len(matches) == 1
                and isinstance(first_match_confianza, int | float)
                and first_match_confianza >= AUTO_CATEGORIZE_CONFIDENCE_THRESHOLD
            ):
                return {
                    "subcategory_id": matches[0]["subcategory_id"],
                    "categoria_sugerida": matches[0]["categoria_sugerida"],
                    "necesita_revision": False,
                    "confianza": matches[0]["confianza"],
                    "alternativas": [],
                    "razon": f"Match automático por keyword: '{matches[0]['keyword_matched']}'",
                }

            # Si hay múltiples matches → necesita revisión
            if len(matches) > 1:
                # Ordenar por confianza
                matches.sort(key=lambda x: float(x["confianza"]) if isinstance(x["confianza"], int | float) else 0, reverse=True)
                return {
                    "subcategory_id": None,
                    "categoria_sugerida": matches[0]["categoria_sugerida"],
                    "necesita_revision": True,
                    "confianza": matches[0]["confianza"],
                    "alternativas": [m["categoria_sugerida"] for m in matches[1:3]],
                    "razon": "Múltiples categorías posibles, necesita confirmación",
                }

            return None

    @retry_on_anthropic_error(max_attempts=3, max_wait=16)
    def _call_claude_api(self, prompt: str) -> str:
        """
        Llama a Claude API con retry logic.

        Args:
            prompt: Prompt para Claude

        Returns:
            str: Respuesta de Claude (texto)

        Raises:
            anthropic.APIError: Si la llamada falla después de todos los intentos
        """
        response = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=1000,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        first_block = response.content[0]
        if not hasattr(first_block, "text"):
            return ""
        return first_block.text.strip()

    def _categorize_with_claude(
        self,
        comercio: str,
        monto_crc: float,
        tipo_transaccion: str,
    ) -> dict[str, Any]:
        """
        Usa Claude AI para categorizar transacciones ambiguas.
        """
        # Obtener las categorías disponibles
        with get_session() as session:
            subcategories = session.query(Subcategory).all()

            # Crear lista de categorías para Claude
            categorias_disponibles = []
            for subcat in subcategories:
                categorias_disponibles.append(
                    {
                        "id": subcat.id,
                        "nombre": subcat.nombre_completo,
                        "descripcion": subcat.descripcion or "",
                        "ejemplos": subcat.keywords or "",
                    }
                )

        # Preparar el prompt para Claude
        prompt = f"""Eres un asistente experto en categorización de gastos personales en Costa Rica.

TRANSACCIÓN A CATEGORIZAR:
- Comercio: {comercio}
- Monto: ₡{monto_crc:,.2f}
- Tipo: {tipo_transaccion}

CATEGORÍAS DISPONIBLES:
{json.dumps(categorias_disponibles, indent=2, ensure_ascii=False)}

INSTRUCCIONES:
1. Analiza el comercio y determina la categoría más apropiada
2. Si el comercio puede pertenecer a múltiples categorías, lista todas las posibilidades
3. Asigna un nivel de confianza (0-100) a tu recomendación principal
4. Si la confianza es < 70%, marca necesita_revision = true

Responde ÚNICAMENTE con un JSON válido en este formato:
{{
  "subcategory_id": "id de la subcategoría recomendada",
  "categoria_sugerida": "Categoría/Subcategoría",
  "necesita_revision": true/false,
  "confianza": 85,
  "alternativas": ["alternativa1", "alternativa2"],
  "razon": "Explicación breve de por qué elegiste esta categoría"
}}"""

        try:
            # Llamar a Claude con retry logic
            response_text = self._call_claude_api(prompt)

            # Limpiar si viene con markdown
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            result: dict[str, Any] = json.loads(response_text)

            logger.debug(
                f" Claude: {result['categoria_sugerida']} " f"(confianza: {result['confianza']}%)"
            )

            return result

        except anthropic.APIConnectionError as e:
            logger.error(f"Error de conexion con Claude API: {e}")
            return self._fallback_result("Error de conexion con API")
        except anthropic.RateLimitError as e:
            logger.warning(f"Rate limit de Claude API: {e}")
            return self._fallback_result("Limite de API excedido")
        except anthropic.APIStatusError as e:
            logger.error(f"Error de estado de Claude API ({e.status_code}): {e.message}")
            return self._fallback_result(f"Error API: {e.status_code}")
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Error parseando respuesta de Claude: {e}")
            return self._fallback_result("Error parseando respuesta")
        except Exception as e:
            logger.error(f"Error inesperado en categorizacion: {type(e).__name__}: {e}")
            return self._fallback_result(f"Error inesperado: {e}")

    def _fallback_result(self, razon: str) -> dict[str, Any]:
        """Resultado de fallback cuando falla la categorizacion."""
        return {
            "subcategory_id": None,
            "categoria_sugerida": "Sin categorizar",
            "necesita_revision": True,
            "confianza": 0,
            "alternativas": [],
            "razon": razon,
        }

    def _categorize_with_claude_enhanced(
        self,
        comercio: str,
        monto_crc: float,
        tipo_transaccion: str,
        fecha: str | None = None,
        ubicacion: str | None = None,
    ) -> dict[str, Any]:
        """
        Versión mejorada con análisis contextual profundo usando Sonnet.

        Análisis adicional:
        - Contexto temporal (hora del día, día de la semana)
        - Monto (bajo/medio/alto)
        - Ubicación si está disponible
        - Tipo de transacción

        Usa Claude Sonnet para mejor razonamiento contextual.
        """
        from datetime import datetime

        # Análisis contextual
        context_hints = []

        # Análisis de monto
        if monto_crc < 5000:
            context_hints.append("Monto bajo - posiblemente snack, café, o compra menor")
        elif monto_crc > 50000:
            context_hints.append("Monto alto - posiblemente compra mayor, electrónica, o servicio")

        # Análisis temporal si hay fecha
        if fecha:
            try:
                dt = datetime.fromisoformat(fecha)
                hora = dt.hour
                dia_semana = dt.strftime("%A")

                if 6 <= hora <= 10:
                    context_hints.append(f"Hora: mañana ({hora}h) - posible desayuno o café")
                elif 12 <= hora <= 14:
                    context_hints.append(f"Hora: almuerzo ({hora}h)")
                elif 18 <= hora <= 22:
                    context_hints.append(f"Hora: noche ({hora}h) - posible cena")
                elif hora >= 23 or hora <= 2:
                    context_hints.append(
                        f"Hora: madrugada ({hora}h) - posible entretenimiento nocturno"
                    )

                if dia_semana in ["Friday", "Saturday"]:
                    context_hints.append(
                        f"Día: {dia_semana} - fin de semana, posible entretenimiento"
                    )
            except (ValueError, TypeError):
                pass

        # Obtener categorías
        with get_session() as session:
            subcategories = session.query(Subcategory).all()
            categorias_disponibles = [
                {
                    "id": subcat.id,
                    "nombre": subcat.nombre_completo,
                    "descripcion": subcat.descripcion or "",
                    "ejemplos": subcat.keywords or "",
                }
                for subcat in subcategories
            ]

        # Prompt mejorado con contexto
        context_str = "\n".join(f"- {hint}" for hint in context_hints)

        prompt = f"""Eres un experto en finanzas personales en Costa Rica con análisis contextual avanzado.

TRANSACCIÓN:
- **Comercio**: {comercio}
- **Monto**: ₡{monto_crc:,.2f}
- **Tipo**: {tipo_transaccion}
{f"- **Ubicación**: {ubicacion}" if ubicacion else ""}

CONTEXTO ADICIONAL:
{context_str if context_hints else "No hay contexto temporal disponible"}

CATEGORÍAS DISPONIBLES:
{json.dumps(categorias_disponibles, indent=2, ensure_ascii=False)[:1500]}...

ANÁLISIS REQUERIDO:
1. Considera el CONTEXTO (hora, monto, día) para mejor precisión
2. Ejemplo: "Uber a las 11pm viernes" → probablemente Entretenimiento, no Transporte laboral
3. Ejemplo: "Walmart ₡8,000 sábado" → probablemente Supermercado, no shopping
4. Si hay ambigüedad real, marca necesita_revision = true
5. Explica tu razonamiento considerando el contexto

Responde ÚNICAMENTE con JSON:
{{
  "subcategory_id": "id",
  "categoria_sugerida": "Nombre",
  "necesita_revision": true/false,
  "confianza": 85,
  "alternativas": ["alt1", "alt2"],
  "razon": "Razón CONSIDERANDO EL CONTEXTO"
}}"""

        try:
            # Usar Haiku para análisis contextual (rápido y económico)
            response = self.client.messages.create(
                model=settings.claude_model,
                max_tokens=800,
                temperature=0.2,  # Más determinístico
                messages=[{"role": "user", "content": prompt}],
            )

            first_block = response.content[0]
            if not hasattr(first_block, "text"):
                return self._categorize_with_claude(comercio, monto_crc, tipo_transaccion)
            response_text = first_block.text.strip()

            # Parsear JSON
            if response_text.startswith("```json"):
                response_text = response_text.replace("```json", "").replace("```", "").strip()

            result: dict[str, Any] = json.loads(response_text)

            # Agregar flag de análisis mejorado
            result["enhanced_analysis"] = True
            result["context_used"] = context_hints

            logger.info(
                f"✨ Análisis contextual: {comercio} → {result['categoria_sugerida']} "
                f"(confianza: {result['confianza']}%)"
            )

            return result

        except Exception as e:
            logger.error(f"Error en análisis contextual: {e}")
            # Fallback a categorización simple
            return self._categorize_with_claude(comercio, monto_crc, tipo_transaccion)

    def categorize_smart(
        self,
        comercio: str,
        monto_crc: float,
        tipo_transaccion: str,
        profile_id: str | None = None,
        fecha: str | None = None,
        ubicacion: str | None = None,
        use_enhanced: bool = True,
    ) -> dict[str, Any]:
        """
        Versión inteligente que decide automáticamente cuándo usar análisis profundo.

        Usa análisis enhanced (Sonnet + contexto) cuando:
        - No hay match en historial
        - No hay match claro por keywords
        - El comercio es conocidamente ambiguo (Walmart, Amazon, etc.)

        Args:
            comercio: Nombre del comercio
            monto_crc: Monto en colones
            tipo_transaccion: Tipo de transacción
            profile_id: ID del perfil (para aprendizaje del historial)
            fecha: Fecha de la transacción (ISO format)
            ubicacion: Ubicación de la transacción
            use_enhanced: Si usar análisis enhanced para casos ambiguos

        Returns:
            dict con resultado de categorización
        """
        logger.info(f"Categorizando smart: {comercio} - ₡{monto_crc:,.2f}")

        # 1. Aprendizaje histórico
        learned = self._categorize_from_history(comercio, profile_id)
        if learned:
            return learned

        # 2. Keywords
        keyword_match = self._categorize_by_keywords(comercio)
        if keyword_match and keyword_match.get("confianza", 0) >= 80:
            return keyword_match

        # 3. Decidir si usar enhanced
        comercios_ambiguos = [
            "walmart",
            "amazon",
            "uber",
            "rappi",
            "mercado",
            "shopping",
            "mall",
            "plaza",
            "centro",
        ]

        es_ambiguo = any(amb in comercio.lower() for amb in comercios_ambiguos)

        if use_enhanced and (es_ambiguo or not keyword_match):
            logger.info(f"🔍 Usando análisis contextual profundo para: {comercio}")
            return self._categorize_with_claude_enhanced(
                comercio, monto_crc, tipo_transaccion, fecha, ubicacion
            )

        # 4. Categorización estándar
        return self._categorize_with_claude(comercio, monto_crc, tipo_transaccion)

    def _categorize_from_history(
        self,
        comercio: str,
        profile_id: str | None,
    ) -> dict[str, Any] | None:
        """
        Busca en transacciones anteriores para aprender del historial.

        Si el usuario ya categorizo este comercio antes, usa esa categoria.

        Args:
            comercio: Nombre del comercio
            profile_id: ID del perfil del usuario

        Returns:
            dict con categorizacion o None si no encuentra historial
        """
        if not profile_id:
            return None

        try:
            with get_session() as session:
                # Importar Transaction aquí para evitar import circular
                from finanzas_tracker.models.transaction import Transaction

                # Buscar transacciones anteriores del mismo comercio que estén categorizadas
                similar_transaction = (
                    session.query(Transaction)
                    .filter(
                        Transaction.profile_id == profile_id,
                        Transaction.comercio == comercio,
                        Transaction.subcategory_id.isnot(None),
                        Transaction.necesita_revision == False,
                    )
                    .order_by(Transaction.fecha_transaccion.desc())
                    .first()
                )

                if similar_transaction and similar_transaction.subcategory:
                    # Encontramos una transacción anterior categorizada
                    subcat = similar_transaction.subcategory
                    return {
                        "subcategory_id": subcat.id,
                        "categoria_sugerida": subcat.nombre_completo,
                        "necesita_revision": False,
                        "confianza": 95,  # Alta confianza por aprendizaje
                        "alternativas": [],
                        "razon": f"Aprendido del historial (usaste esta categoría antes para '{comercio}')",
                    }

                return None

        except (AttributeError, TypeError) as e:
            logger.debug(f"Error de datos buscando en historial: {e}")
            return None
        except Exception as e:
            logger.debug(f"Error DB buscando en historial: {type(e).__name__}: {e}")
            return None

    def get_subcategory_by_name(self, nombre_completo: str) -> str | None:
        """
        Busca una subcategoría por su nombre completo.

        Args:
            nombre_completo: Nombre en formato "Categoría/Subcategoría"

        Returns:
            ID de la subcategoría o None
        """
        with get_session() as session:
            # Separar categoría y subcategoría
            if "/" in nombre_completo:
                _, subcat_name = nombre_completo.split("/", 1)
            else:
                subcat_name = nombre_completo

            subcat = (
                session.query(Subcategory).filter(Subcategory.nombre == subcat_name.strip()).first()
            )

            return subcat.id if subcat else None
