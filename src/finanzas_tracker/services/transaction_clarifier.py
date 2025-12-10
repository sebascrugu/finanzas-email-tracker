"""Servicio de clarificación de transacciones con Claude AI.

Permite conversaciones naturales para identificar transacciones:
- "Le pagué al zapatero por arreglar mis botas"
- "Es el alquiler de diciembre"
- "Fue una cena con mis papás"
"""

__all__ = ["TransactionClarifierService", "ClarificationResult"]

import logging
import re
from dataclasses import dataclass
from typing import cast

import anthropic
from sqlalchemy.orm import Session

from finanzas_tracker.config.settings import settings
from finanzas_tracker.core.claude_credits import can_use_claude, handle_claude_error
from finanzas_tracker.core.retry import retry_on_anthropic_error
from finanzas_tracker.models.category import Category, Subcategory
from finanzas_tracker.models.transaction import Transaction


logger = logging.getLogger(__name__)


@dataclass
class ClarificationResult:
    """Resultado de una clarificación de transacción."""

    descripcion: str
    beneficiario: str | None
    categoria_sugerida: str | None
    subcategoria_sugerida: str | None
    confianza: float  # 0.0 a 1.0
    respuesta_usuario: str  # Para mostrar al usuario


class TransactionClarifierService:
    """
    Servicio para clarificar transacciones mediante chat natural.

    Usa Claude para entender descripciones como:
    - "Le pagué a Juan por el arreglo del carro"
    - "Es mi cuota del gimnasio"
    - "Fue para comprar comida para el perro"
    """

    # System prompt para Claude
    SYSTEM_PROMPT = """Eres un asistente de finanzas personales para Costa Rica.
Tu trabajo es ayudar a categorizar transacciones bancarias basándote en la explicación del usuario.

Cuando el usuario te explique de qué fue un gasto, debes extraer:
1. **descripcion**: Un resumen corto y claro del gasto (máx 50 caracteres)
2. **beneficiario**: A quién le pagó (si lo menciona), o null
3. **categoria**: La categoría más apropiada de esta lista:
   - Alimentación (restaurantes, supermercados, cafeterías)
   - Transporte (uber, taxi, gasolina, bus, parqueo)
   - Entretenimiento (cine, streaming, juegos, salidas)
   - Hogar (alquiler, servicios, mantenimiento)
   - Salud (doctor, farmacia, gimnasio)
   - Ropa y Accesorios (tiendas de ropa, zapaterías)
   - Educación (cursos, libros, matrícula)
   - Servicios Financieros (transferencias a familiares, préstamos)
   - Mascotas (veterinario, comida de mascota)
   - Tecnología (gadgets, accesorios tech)
   - Otros (si no encaja en ninguna)

4. **subcategoria**: Más específico dentro de la categoría
5. **confianza**: Del 0 al 100, qué tan seguro estás

Responde SIEMPRE en formato JSON así:
{
  "descripcion": "Arreglo de zapatos",
  "beneficiario": "Zapatero",
  "categoria": "Ropa y Accesorios",
  "subcategoria": "Zapatería",
  "confianza": 85,
  "mensaje": "Entendido, registré el pago al zapatero por arreglo de zapatos"
}

Si el usuario no da suficiente información, pregunta amablemente.
Responde en español costarricense (mae, tuanis, pura vida).
"""

    def __init__(self, db: Session) -> None:
        """Inicializa el servicio."""
        self.db = db
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model
        logger.info("TransactionClarifierService inicializado")

    def _get_categories_context(self) -> str:
        """Obtiene las categorías disponibles para contexto."""
        categories = self.db.query(Category).all()
        subcategories = self.db.query(Subcategory).all()

        context = "Categorías disponibles:\n"
        for cat in categories:
            subs = [s.nombre for s in subcategories if s.category_id == cat.id]
            context += f"- {cat.nombre}: {', '.join(subs)}\n"

        return context

    @retry_on_anthropic_error(max_attempts=3, max_wait=16)
    def _call_claude(self, messages: list[dict]) -> str:
        """Llama a Claude con retry logic."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=512,
            temperature=0.3,
            system=self.SYSTEM_PROMPT,
            messages=messages,
        )
        first_block = response.content[0]
        if not hasattr(first_block, "text"):
            return '{"error": "No pude procesar tu mensaje"}'
        return cast(str, first_block.text)

    def clarify_transaction(
        self,
        transaction: Transaction,
        user_message: str,
        conversation_history: list[dict] | None = None,
    ) -> ClarificationResult:
        """
        Clarifica una transacción basándose en la explicación del usuario.

        Args:
            transaction: La transacción a clarificar
            user_message: Explicación del usuario (ej: "Le pagué al zapatero")
            conversation_history: Historial de la conversación (opcional)

        Returns:
            ClarificationResult con la información extraída
        """
        # Verificar disponibilidad de Claude
        can_use, reason = can_use_claude()
        if not can_use:
            logger.warning(f"Claude no disponible: {reason}")
            return ClarificationResult(
                descripcion=user_message[:50],
                beneficiario=None,
                categoria_sugerida=None,
                subcategoria_sugerida=None,
                confianza=0.0,
                respuesta_usuario="⚠️ El asistente AI no está disponible. Guardé tu descripción directamente.",
            )

        try:
            # Construir contexto de la transacción
            txn_context = f"""
Transacción a clarificar:
- Monto: ₡{transaction.monto_crc:,.2f}
- Fecha: {transaction.fecha_transaccion.strftime('%d/%m/%Y')}
- Beneficiario conocido: {transaction.beneficiario or 'No identificado'}
- Concepto actual: {transaction.concepto_transferencia or 'Sin concepto'}
"""

            # Construir mensajes
            messages = conversation_history or []
            messages.append({
                "role": "user",
                "content": f"{txn_context}\n\nEl usuario dice: {user_message}",
            })

            # Llamar a Claude
            response_text = self._call_claude(messages)
            logger.debug(f"Respuesta de Claude: {response_text}")

            # Parsear JSON
            result = self._parse_response(response_text, user_message)
            return result

        except anthropic.APIStatusError as e:
            if handle_claude_error(e):
                return ClarificationResult(
                    descripcion=user_message[:50],
                    beneficiario=None,
                    categoria_sugerida=None,
                    subcategoria_sugerida=None,
                    confianza=0.0,
                    respuesta_usuario="⚠️ Créditos de AI agotados. Guardé tu descripción.",
                )
            raise

        except Exception as e:
            logger.error(f"Error clarificando transacción: {e}")
            return ClarificationResult(
                descripcion=user_message[:50],
                beneficiario=None,
                categoria_sugerida=None,
                subcategoria_sugerida=None,
                confianza=0.0,
                respuesta_usuario=f"⚠️ Hubo un error: {e}. Guardé tu descripción.",
            )

    def _parse_response(self, response_text: str, fallback: str) -> ClarificationResult:
        """Parsea la respuesta JSON de Claude."""
        import json

        # Intentar extraer JSON del texto
        json_match = re.search(r"\{[^{}]*\}", response_text, re.DOTALL)
        if not json_match:
            return ClarificationResult(
                descripcion=fallback[:50],
                beneficiario=None,
                categoria_sugerida=None,
                subcategoria_sugerida=None,
                confianza=0.5,
                respuesta_usuario=response_text,
            )

        try:
            data = json.loads(json_match.group())
            return ClarificationResult(
                descripcion=data.get("descripcion", fallback)[:50],
                beneficiario=data.get("beneficiario"),
                categoria_sugerida=data.get("categoria"),
                subcategoria_sugerida=data.get("subcategoria"),
                confianza=float(data.get("confianza", 50)) / 100,
                respuesta_usuario=data.get("mensaje", "✅ Entendido"),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Error parseando respuesta de Claude: {e}")
            return ClarificationResult(
                descripcion=fallback[:50],
                beneficiario=None,
                categoria_sugerida=None,
                subcategoria_sugerida=None,
                confianza=0.3,
                respuesta_usuario=response_text,
            )

    def apply_clarification(
        self,
        transaction: Transaction,
        result: ClarificationResult,
    ) -> None:
        """
        Aplica la clarificación a la transacción y guarda el patrón para aprendizaje.

        Args:
            transaction: Transacción a actualizar
            result: Resultado de la clarificación
        """
        from finanzas_tracker.services.pattern_learning_service import PatternLearningService
        
        # Actualizar descripción/concepto
        if result.descripcion:
            transaction.concepto_transferencia = result.descripcion

        # Actualizar beneficiario si no tenía
        if result.beneficiario and not transaction.beneficiario:
            transaction.beneficiario = result.beneficiario
            transaction.comercio = f"SINPE a {result.beneficiario}"

        # Buscar subcategoría si se sugirió
        subcategory_id = None
        if result.subcategoria_sugerida:
            subcat = (
                self.db.query(Subcategory)
                .filter(Subcategory.nombre.ilike(f"%{result.subcategoria_sugerida}%"))
                .first()
            )
            if subcat:
                transaction.subcategory_id = subcat.id
                subcategory_id = subcat.id

        # Si no encontró subcategoría pero sí categoría, buscar por categoría
        elif result.categoria_sugerida and not transaction.subcategory_id:
            cat = (
                self.db.query(Category)
                .filter(Category.nombre.ilike(f"%{result.categoria_sugerida}%"))
                .first()
            )
            if cat:
                # Buscar primera subcategoría de esa categoría
                subcat = (
                    self.db.query(Subcategory)
                    .filter(Subcategory.category_id == cat.id)
                    .first()
                )
                if subcat:
                    transaction.subcategory_id = subcat.id
                    subcategory_id = subcat.id

        # Marcar como revisada
        transaction.necesita_reconciliacion_sinpe = False

        # ========================================
        # GUARDAR PATRÓN PARA APRENDIZAJE
        # ========================================
        if subcategory_id:
            try:
                learning_service = PatternLearningService(self.db)
                patron = learning_service.guardar_patron_de_clarificacion(
                    transaction=transaction,
                    subcategory_id=subcategory_id,
                    user_label=result.beneficiario,
                    beneficiario=result.beneficiario or transaction.beneficiario,
                    concepto=result.descripcion,
                )
                if patron:
                    logger.info(
                        f"📚 Patrón guardado: {patron.pattern_key} → "
                        f"{patron.subcategory_name} (confianza: {patron.confidence:.0%})"
                    )
            except Exception as e:
                logger.warning(f"No se pudo guardar patrón de aprendizaje: {e}")

        # Guardar cambios
        self.db.commit()
        logger.info(f"Transacción {transaction.id} clarificada: {result.descripcion}")


# Función helper para uso rápido
def clarify_with_claude(
    db: Session,
    transaction: Transaction,
    user_message: str,
) -> ClarificationResult:
    """Helper para clarificar rápidamente una transacción."""
    service = TransactionClarifierService(db)
    return service.clarify_transaction(transaction, user_message)
