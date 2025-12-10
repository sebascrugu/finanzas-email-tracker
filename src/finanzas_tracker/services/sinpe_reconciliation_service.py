"""
Servicio de Reconciliación de SINPEs y Transferencias.

Este servicio se encarga de:
1. Detectar transacciones SINPE/transferencias con descripciones ambiguas
2. Buscar correos de transferencia y hacer match con transacciones del PDF
3. Crear preguntas pendientes para el usuario
4. Procesar las respuestas del usuario
5. Actualizar las transacciones con la información correcta
6. Aprender de las respuestas para futuras transacciones
"""

from datetime import datetime, UTC, timedelta
from decimal import Decimal
import json
import re
from typing import Any
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.pending_question import (
    PendingQuestion,
    QuestionPriority,
    QuestionStatus,
    QuestionType,
)
from finanzas_tracker.models.transaction import Transaction


logger = get_logger(__name__)


@dataclass
class TransferenciaCorreo:
    """Datos extraídos de un correo de transferencia."""
    beneficiario: str
    monto: Decimal
    fecha: datetime
    concepto: str
    referencia: str
    email_date: datetime


class SinpeReconciliationService:
    """
    Servicio para reconciliar transacciones SINPE y transferencias.
    
    Las transferencias SINPE son complicadas porque:
    - El usuario pone descripciones a veces útiles ("Alquiler Dic")
    - A veces pone cosas sin sentido o bromas ("Funeral_Cartago")
    - A veces no pone nada ("pago", "transferencia")
    - El número de referencia no es útil para el usuario
    
    Este servicio detecta cuáles necesitan clarificación y genera
    preguntas para que el usuario las responda.
    """

    # Conceptos que claramente no aportan información
    CONCEPTOS_INUTILES = {
        "pago",
        "pagos", 
        "transferencia",
        "transferencias",
        "sinpe",
        "deposito",
        "depositos",
        "sin descripcion",
        "sin descripción",
        "n/a",
        "na",
        "-",
        ".",
        "",
    }

    # Palabras clave que indican que SÍ es una descripción útil
    PALABRAS_UTILES = {
        "alquiler",
        "renta",
        "salario",
        "sueldo",
        "pago de",
        "cuota",
        "mensualidad",
        "servicio",
        "luz",
        "agua",
        "internet",
        "cable",
        "telefono",
        "celular",
        "electricidad",
        "gasolina",
        "comida",
        "almuerzo",
        "cena",
        "desayuno",
        "super",
        "compra",
        "reembolso",
        "devolucion",
        "prestamo",
        "deuda",
    }

    def __init__(self, db: Session) -> None:
        """Inicializa el servicio."""
        self.db = db

    def reconciliar_con_correos(
        self,
        profile_id: str,
        fecha_corte: datetime | None = None,
    ) -> dict[str, int]:
        """
        Busca correos de transferencia y hace match con transacciones del PDF.
        
        Proceso:
        1. Determinar rango de fechas correcto:
           - Desde: 28 del mes anterior a fecha_corte
           - Hasta: Hoy
        2. Buscar correos de "Notificación de Transferencia" de BAC
        3. Extraer beneficiario, monto, fecha, concepto
        4. Buscar transacciones SINPE/transferencias y hacer match
        5. Si hay match único → Actualizar transacción con datos del correo
        6. Si hay múltiples matches → Dejar para preguntar al usuario
        
        Args:
            profile_id: ID del perfil
            fecha_corte: Fecha de corte del estado de cuenta (si no se pasa, se calcula)
            
        Returns:
            Dict con estadísticas
        """
        from finanzas_tracker.services.auth_manager import AuthManager
        import requests
        from dateutil.relativedelta import relativedelta
        
        stats = {
            "correos_encontrados": 0,
            "matches_exactos": 0,
            "sin_match": 0,
            "multiples_matches": 0,
            "ya_reconciliados": 0,
            "transferencias_totales": 0,
        }
        
        # 1. Determinar fecha de corte si no se pasó
        if not fecha_corte:
            # Buscar la transacción más antigua del perfil para estimar fecha de corte
            from sqlalchemy import func
            fecha_min = self.db.query(func.min(Transaction.fecha_transaccion)).filter(
                Transaction.profile_id == profile_id,
                Transaction.deleted_at.is_(None),
            ).scalar()
            
            if fecha_min:
                # Asumir que la fecha de corte es el último día del mes de la transacción más antigua
                # O usar hoy menos 30 días como fallback
                fecha_corte = fecha_min
            else:
                fecha_corte = datetime.now(UTC) - timedelta(days=30)
        
        # 2. Calcular rango de búsqueda:
        # Desde: 28 del mes anterior a fecha_corte
        # Hasta: Hoy
        if fecha_corte.tzinfo is None:
            fecha_corte = fecha_corte.replace(tzinfo=UTC)
        
        # Calcular 28 del mes anterior
        mes_anterior = fecha_corte - relativedelta(months=1)
        start_date = datetime(mes_anterior.year, mes_anterior.month, 28, tzinfo=UTC)
        end_date = datetime.now(UTC)
        
        logger.info(
            f"🔍 Buscando correos de transferencia: {start_date.strftime('%d/%m/%Y')} → {end_date.strftime('%d/%m/%Y')}"
        )
        
        # 3. Obtener token de Outlook
        try:
            auth = AuthManager()
            token = auth.get_access_token()
            if not token:
                logger.warning("No hay token de Outlook disponible")
                return stats
        except Exception as e:
            logger.warning(f"No se pudo obtener token de Outlook: {e}")
            return stats
        
        # 4. Buscar correos de transferencia
        headers = {"Authorization": f"Bearer {token}"}
        
        params = {
            "$filter": (
                f"receivedDateTime ge {start_date.isoformat()} "
                f"and from/emailAddress/address eq 'alerta@baccredomatic.com' "
                f"and contains(subject, 'Transferencia')"
            ),
            "$select": "id,subject,receivedDateTime,body",
            "$orderby": "receivedDateTime desc",
            "$top": 200,  # Aumentar límite para buscar más correos
        }
        
        try:
            response = requests.get(
                "https://graph.microsoft.com/v1.0/me/messages",
                headers=headers,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            emails = response.json().get("value", [])
        except Exception as e:
            logger.error(f"Error buscando correos de transferencia: {e}")
            return stats
        
        stats["correos_encontrados"] = len(emails)
        logger.info(f"📧 Encontrados {len(emails)} correos de transferencia")
        
        # 5. Extraer datos de cada correo
        transferencias_correo: list[TransferenciaCorreo] = []
        for email in emails:
            try:
                data = self._extraer_datos_correo_transferencia(email)
                if data:
                    transferencias_correo.append(data)
            except Exception as e:
                logger.debug(f"Error extrayendo datos de correo: {e}")
        
        logger.info(f"📝 Extraídos datos de {len(transferencias_correo)} transferencias de correos")
        
        # 6. Buscar TODAS las transferencias del perfil (no solo las marcadas)
        todas_transferencias = self.db.query(Transaction).filter(
            Transaction.profile_id == profile_id,
            Transaction.deleted_at.is_(None),
            Transaction.tipo_transaccion == "transferencia",
        ).all()
        
        stats["transferencias_totales"] = len(todas_transferencias)
        stats["auto_categorizados_patron"] = 0
        logger.info(f"🔍 {len(todas_transferencias)} transferencias totales en el perfil")
        
        # Inicializar servicio de aprendizaje
        from finanzas_tracker.services.pattern_learning_service import PatternLearningService
        learning_service = PatternLearningService(self.db)
        
        # 7. Para cada transferencia, intentar hacer match con correos
        for txn in todas_transferencias:
            # Si ya tiene beneficiario claro y concepto claro, saltar
            if txn.beneficiario and self._es_descripcion_clara(txn.concepto_transferencia):
                stats["ya_reconciliados"] += 1
                txn.necesita_reconciliacion_sinpe = False
                continue
            
            # ========================================
            # PRIMERO: Intentar auto-categorizar con patrones aprendidos
            # ========================================
            if learning_service.auto_categorizar_si_confianza_alta(txn):
                stats["auto_categorizados_patron"] += 1
                continue
            
            # Buscar match en correos
            matches = self._buscar_match_correo(txn, transferencias_correo)
            
            if len(matches) == 1:
                # Match exacto - actualizar transacción con datos del correo
                correo = matches[0]
                txn.beneficiario = correo.beneficiario
                txn.concepto_transferencia = correo.concepto
                
                # Intentar auto-categorizar ahora que tiene beneficiario
                if learning_service.auto_categorizar_si_confianza_alta(txn):
                    stats["auto_categorizados_patron"] += 1
                    continue
                
                # Si el concepto es claro, marcar como reconciliado
                if self._es_descripcion_clara(correo.concepto):
                    txn.comercio = f"SINPE a {correo.beneficiario}"
                    txn.necesita_reconciliacion_sinpe = False
                    txn.notas = (
                        f"✅ Reconciliado automáticamente\n"
                        f"Beneficiario: {correo.beneficiario}\n"
                        f"Concepto: {correo.concepto}\n"
                        f"Ref: {correo.referencia}"
                    )
                    stats["matches_exactos"] += 1
                    logger.info(
                        f"✅ Match claro: ₡{txn.monto_crc:,.0f} → {correo.beneficiario} ({correo.concepto})"
                    )
                else:
                    # Tiene match pero concepto no es claro - necesita revisión
                    txn.comercio = f"SINPE a {correo.beneficiario}"
                    txn.necesita_reconciliacion_sinpe = True
                    txn.notas = (
                        f"🔍 Match encontrado, necesita clarificación\n"
                        f"Beneficiario: {correo.beneficiario}\n"
                        f"Concepto: {correo.concepto or '(sin descripción)'}\n"
                        f"Ref: {correo.referencia}"
                    )
                    stats["sin_match"] += 1  # Cuenta como "necesita revisión"
                    logger.info(
                        f"🔍 Match pero sin concepto claro: ₡{txn.monto_crc:,.0f} → {correo.beneficiario}"
                    )
            elif len(matches) > 1:
                # Múltiples matches - necesita pregunta al usuario
                txn.necesita_reconciliacion_sinpe = True
                stats["multiples_matches"] += 1
                logger.info(
                    f"⚠️ Múltiples matches para ₡{txn.monto_crc:,.0f}: {len(matches)}"
                )
            else:
                # Sin match de correo - marcar para revisión
                txn.necesita_reconciliacion_sinpe = True
                stats["sin_match"] += 1
        
        self.db.commit()
        
        logger.info(
            f"📊 Reconciliación: {stats['matches_exactos']} exactos, "
            f"{stats['multiples_matches']} múltiples, {stats['sin_match']} sin match"
        )
        
        return stats

    def _extraer_datos_correo_transferencia(
        self, 
        email: dict,
    ) -> TransferenciaCorreo | None:
        """
        Extrae beneficiario, monto, fecha y concepto de un correo de transferencia.
        
        Formatos soportados:
        - "Estimado(a) NOMBRE COMPLETO :" → Beneficiario
        - "monto de 18.000,00 CRC" → Monto
        - "día DD-MM-YYYY" → Fecha
        - "concepto de: TEXTO" → Concepto
        - "referencia es NUMERO" → Referencia
        """
        body_html = email.get("body", {}).get("content", "")
        email_date_str = email.get("receivedDateTime", "")
        
        # Limpiar HTML
        text = re.sub(r"<[^>]+>", " ", body_html)
        text = re.sub(r"\s+", " ", text).strip()
        
        # Extraer beneficiario: "Estimado(a) NOMBRE :"
        benef_match = re.search(r"Estimado\(a\)\s+([^:]+):", text)
        if not benef_match:
            return None
        beneficiario = benef_match.group(1).strip()
        
        # Limpiar beneficiario (quitar BAC Cred si aparece)
        beneficiario = re.sub(r"^BAC Cred\(a\)\s*", "", beneficiario).strip()
        
        # Extraer monto: "monto de 18.000,00 CRC" o "monto de 18,000.00 CRC"
        monto_match = re.search(r"monto de ([\d.,]+)\s*(?:CRC|Colones)?", text, re.IGNORECASE)
        if not monto_match:
            return None
        
        monto_str = monto_match.group(1)
        # Normalizar formato de monto (puede ser 18.000,00 o 18,000.00)
        if "," in monto_str and "." in monto_str:
            # Determinar cuál es el separador decimal
            if monto_str.rfind(",") > monto_str.rfind("."):
                # Formato europeo: 18.000,00
                monto_str = monto_str.replace(".", "").replace(",", ".")
            else:
                # Formato US: 18,000.00
                monto_str = monto_str.replace(",", "")
        elif "," in monto_str:
            # Solo coma, asumir decimal
            monto_str = monto_str.replace(",", ".")
        
        try:
            monto = Decimal(monto_str)
        except:
            return None
        
        # Extraer fecha: "día DD-MM-YYYY" o "Día y hora DD/MM/YYYY"
        fecha_match = re.search(r"(?:día|Día y hora)\s*(\d{2}[-/]\d{2}[-/]\d{4})", text)
        if fecha_match:
            fecha_str = fecha_match.group(1).replace("/", "-")
            try:
                fecha = datetime.strptime(fecha_str, "%d-%m-%Y")
            except:
                fecha = datetime.now(UTC)
        else:
            # Usar fecha del correo
            try:
                fecha = datetime.fromisoformat(email_date_str.replace("Z", "+00:00"))
            except:
                fecha = datetime.now(UTC)
        
        # Extraer concepto: "concepto de: TEXTO" o "por concepto de TEXTO"
        concepto_match = re.search(r"(?:por )?concepto de:?\s*([^\n.]+)", text, re.IGNORECASE)
        concepto = concepto_match.group(1).strip() if concepto_match else ""
        
        # Limpiar concepto (quitar caracteres raros)
        concepto = re.sub(r"[_]+", " ", concepto).strip()
        
        # Extraer referencia
        ref_match = re.search(r"referencia (?:es|es:)?\s*(\d+)", text, re.IGNORECASE)
        referencia = ref_match.group(1) if ref_match else ""
        
        # Fecha del correo para comparación
        try:
            email_dt = datetime.fromisoformat(email_date_str.replace("Z", "+00:00"))
        except:
            email_dt = datetime.now(UTC)
        
        return TransferenciaCorreo(
            beneficiario=beneficiario,
            monto=monto,
            fecha=fecha,
            concepto=concepto,
            referencia=referencia,
            email_date=email_dt,
        )

    def _buscar_match_correo(
        self,
        txn: Transaction,
        transferencias: list[TransferenciaCorreo],
        tolerancia_dias: int = 2,
    ) -> list[TransferenciaCorreo]:
        """
        Busca correos que coincidan con una transacción por monto y fecha.
        
        Args:
            txn: Transacción a buscar
            transferencias: Lista de transferencias extraídas de correos
            tolerancia_dias: Días de tolerancia para el match de fecha
            
        Returns:
            Lista de transferencias que coinciden (idealmente 1)
        """
        matches = []
        
        txn_monto = txn.monto_crc
        txn_fecha = txn.fecha_transaccion
        
        if not txn_fecha:
            return matches
        
        # Hacer fecha naive para comparación si es necesario
        if txn_fecha.tzinfo:
            txn_fecha = txn_fecha.replace(tzinfo=None)
        
        for trans in transferencias:
            # Match por monto (exacto)
            if abs(trans.monto - txn_monto) > Decimal("0.01"):
                continue
            
            # Match por fecha (con tolerancia)
            trans_fecha = trans.fecha
            if trans_fecha.tzinfo:
                trans_fecha = trans_fecha.replace(tzinfo=None)
            
            diferencia_dias = abs((txn_fecha - trans_fecha).days)
            
            if diferencia_dias <= tolerancia_dias:
                matches.append(trans)
        
        return matches

    def analizar_transacciones_pendientes(
        self,
        profile_id: str,
        limite: int = 50,
    ) -> list[PendingQuestion]:
        """
        Analiza transacciones que necesitan reconciliación y crea preguntas.
        
        Args:
            profile_id: ID del perfil
            limite: Máximo de transacciones a analizar
            
        Returns:
            Lista de preguntas creadas
        """
        # Buscar transacciones SINPE/transferencias que necesitan reconciliación
        stmt = (
            select(Transaction)
            .where(
                Transaction.profile_id == profile_id,
                Transaction.deleted_at.is_(None),
                Transaction.tipo_transaccion == "transferencia",
                Transaction.necesita_reconciliacion_sinpe == True,
            )
            .order_by(Transaction.monto_crc.desc())  # Mayores primero
            .limit(limite)
        )
        
        transacciones = list(self.db.execute(stmt).scalars().all())
        
        if not transacciones:
            logger.info("No hay transacciones pendientes de reconciliación SINPE")
            return []
        
        logger.info(f"Encontradas {len(transacciones)} transacciones para reconciliar")
        
        preguntas_creadas = []
        for txn in transacciones:
            # Verificar si ya existe una pregunta para esta transacción
            pregunta_existente = self.db.query(PendingQuestion).filter(
                PendingQuestion.transaction_id == txn.id,
                PendingQuestion.status == QuestionStatus.PENDIENTE,
            ).first()
            
            if pregunta_existente:
                continue
            
            # Crear pregunta
            pregunta = self._crear_pregunta_sinpe(txn)
            self.db.add(pregunta)
            preguntas_creadas.append(pregunta)
        
        if preguntas_creadas:
            self.db.commit()
            logger.info(f"Creadas {len(preguntas_creadas)} preguntas nuevas")
        
        return preguntas_creadas

    def detectar_transacciones_ambiguas(
        self,
        profile_id: str,
    ) -> int:
        """
        Analiza TODAS las transferencias y marca las que necesitan reconciliación.
        
        Útil para correr después de una importación masiva o para
        re-analizar transacciones existentes.
        
        Returns:
            Número de transacciones marcadas
        """
        stmt = (
            select(Transaction)
            .where(
                Transaction.profile_id == profile_id,
                Transaction.deleted_at.is_(None),
                Transaction.tipo_transaccion == "transferencia",
                # Solo las que no han sido marcadas aún
                Transaction.necesita_reconciliacion_sinpe.is_(None) | 
                (Transaction.necesita_reconciliacion_sinpe == False),
            )
        )
        
        transacciones = list(self.db.execute(stmt).scalars().all())
        marcadas = 0
        
        for txn in transacciones:
            if self._es_descripcion_ambigua(txn):
                txn.necesita_reconciliacion_sinpe = True
                marcadas += 1
            else:
                txn.necesita_reconciliacion_sinpe = False
        
        if marcadas > 0:
            self.db.commit()
            logger.info(f"Marcadas {marcadas} transacciones como ambiguas")
        
        return marcadas

    def _es_descripcion_ambigua(self, txn: Transaction) -> bool:
        """
        Determina si una transacción tiene descripción ambigua.
        
        Criterios:
        - Sin concepto/descripción
        - Concepto genérico ("pago", "transferencia")
        - Concepto muy corto
        - Concepto que parece número de referencia
        """
        # Usar concepto_transferencia si existe, sino comercio
        concepto = txn.concepto_transferencia or ""
        comercio = txn.comercio or ""
        
        # Si no hay concepto, revisar si el comercio tiene info útil
        if not concepto:
            # El comercio podría tener formato "SINPE a Bruno - Alquiler"
            if " - " in comercio:
                concepto = comercio.split(" - ", 1)[1]
            else:
                concepto = comercio
        
        concepto_lower = concepto.lower().strip()
        
        # Sin concepto
        if not concepto_lower:
            return True
        
        # Concepto inútil/genérico
        if concepto_lower in self.CONCEPTOS_INUTILES:
            return True
        
        # Muy corto (menos de 3 caracteres)
        if len(concepto_lower) < 3:
            return True
        
        # Es solo un número (referencia, teléfono, etc.)
        if re.match(r"^[\d\s\-_.]+$", concepto_lower):
            return True
        
        # Contiene palabra útil → NO es ambigua
        for palabra in self.PALABRAS_UTILES:
            if palabra in concepto_lower:
                return False
        
        # Por defecto, si tiene más de 5 caracteres y parece texto, no es ambigua
        if len(concepto_lower) >= 5 and re.search(r"[a-záéíóúñ]{3,}", concepto_lower):
            return False
        
        return True

    def _es_descripcion_clara(self, concepto: str | None) -> bool:
        """
        Determina si un concepto/descripción es suficientemente claro
        para NO necesitar revisión manual.
        
        Es lo opuesto de _es_descripcion_ambigua pero trabaja solo con el texto.
        
        Descripciones claras:
        - Contienen palabras clave útiles (alquiler, salario, luz, etc.)
        - Son descriptivas y tienen contexto
        
        Descripciones NO claras (necesitan revisión):
        - Nombres propios sin contexto ("sebastian_cruz", "funeral_cartago")
        - Conceptos genéricos ("pago", "transferencia")
        - Muy cortas o solo números
        """
        if not concepto:
            return False
        
        concepto_lower = concepto.lower().strip()
        
        # Limpiar underscores y caracteres especiales
        concepto_limpio = concepto_lower.replace("_", " ").strip()
        
        # Vacío o muy corto
        if len(concepto_limpio) < 3:
            return False
        
        # Conceptos inútiles
        if concepto_limpio in self.CONCEPTOS_INUTILES:
            return False
        
        # Solo números
        if re.match(r"^[\d\s\-_.]+$", concepto_limpio):
            return False
        
        # Contiene palabra útil → ES clara
        for palabra in self.PALABRAS_UTILES:
            if palabra in concepto_limpio:
                return True
        
        # Patrones que indican que NO es clara (nombres propios, usernames, etc.)
        patrones_no_claros = [
            r"^[a-z]+_[a-z]+$",  # nombre_apellido
            r"^[a-z]+\s+[a-z]+$",  # solo dos palabras cortas
            r"funeral",  # bromas tipo "funeral_cartago"
            r"^[A-Z]{2,}$",  # Solo mayúsculas (siglas sin contexto)
        ]
        
        for patron in patrones_no_claros:
            if re.search(patron, concepto_lower):
                return False
        
        # Si tiene más de 8 caracteres y parece una frase descriptiva, es clara
        if len(concepto_limpio) >= 8 and " " in concepto_limpio:
            return True
        
        # Por defecto, NO es clara (mejor preguntar)
        return False

    def _crear_pregunta_sinpe(self, txn: Transaction) -> PendingQuestion:
        """Crea una pregunta pendiente para una transacción SINPE."""
        beneficiario = txn.beneficiario or "desconocido"
        concepto = txn.concepto_transferencia or ""
        monto = txn.monto_crc
        fecha = txn.fecha_transaccion
        
        # Determinar prioridad por monto
        if monto >= 100_000:
            prioridad = QuestionPriority.ALTA
        elif monto >= 20_000:
            prioridad = QuestionPriority.MEDIA
        else:
            prioridad = QuestionPriority.BAJA
        
        # Construir pregunta
        if concepto and concepto.lower() not in self.CONCEPTOS_INUTILES:
            pregunta_texto = (
                f"SINPE de ₡{monto:,.0f} a {beneficiario}\n"
                f"Descripción: \"{concepto}\"\n"
                f"¿Qué fue este pago?"
            )
        else:
            pregunta_texto = (
                f"SINPE de ₡{monto:,.0f} a {beneficiario}\n"
                f"Sin descripción clara.\n"
                f"¿Qué fue este pago?"
            )
        
        # Contexto JSON para UI
        contexto = json.dumps({
            "beneficiario": beneficiario,
            "concepto_original": concepto,
            "monto": float(monto),
            "fecha": fecha.isoformat() if fecha else None,
            "subtipo": txn.subtipo_transaccion,
        })
        
        # Opciones sugeridas
        opciones = json.dumps([
            "Alquiler/Vivienda",
            "Servicios (luz, agua, internet)",
            "Comida/Restaurante",
            "Transporte",
            "Compras personales",
            "Pago a persona (préstamo, deuda)",
            "Entretenimiento",
            "Salud",
            "Otro (especificar)",
        ])
        
        return PendingQuestion(
            profile_id=txn.profile_id,
            transaction_id=txn.id,
            tipo=QuestionType.SINPE_SIN_DESCRIPCION,
            prioridad=prioridad,
            pregunta=pregunta_texto,
            contexto=contexto,
            opciones=opciones,
            monto_relacionado=monto,
            origen="reconciliacion",
        )

    def procesar_respuesta(
        self,
        pregunta_id: str,
        respuesta: str,
        categoria_id: str | None = None,
    ) -> bool:
        """
        Procesa la respuesta del usuario a una pregunta de reconciliación.
        
        Args:
            pregunta_id: ID de la pregunta
            respuesta: Texto de la respuesta del usuario
            categoria_id: ID de la subcategoría si se asignó una
            
        Returns:
            True si se procesó correctamente
        """
        pregunta = self.db.query(PendingQuestion).filter(
            PendingQuestion.id == pregunta_id,
        ).first()
        
        if not pregunta:
            logger.warning(f"Pregunta no encontrada: {pregunta_id}")
            return False
        
        # Marcar pregunta como respondida
        pregunta.responder(respuesta)
        
        # Actualizar transacción si existe
        if pregunta.transaction_id:
            txn = self.db.query(Transaction).filter(
                Transaction.id == pregunta.transaction_id,
            ).first()
            
            if txn:
                # Actualizar con la respuesta del usuario
                txn.notas = f"Usuario aclaró: {respuesta}"
                txn.necesita_reconciliacion_sinpe = False
                txn.necesita_revision = False
                
                if categoria_id:
                    txn.subcategory_id = categoria_id
                    txn.categoria_confirmada_usuario = True
                    txn.confirmada = True
                
                logger.info(
                    f"Transacción {txn.id} reconciliada: {respuesta}"
                )
        
        self.db.commit()
        return True

    def obtener_preguntas_pendientes(
        self,
        profile_id: str,
        limite: int = 20,
    ) -> list[PendingQuestion]:
        """
        Obtiene las preguntas pendientes de responder.
        
        Returns:
            Lista de preguntas pendientes ordenadas por prioridad y monto
        """
        stmt = (
            select(PendingQuestion)
            .where(
                PendingQuestion.profile_id == profile_id,
                PendingQuestion.status == QuestionStatus.PENDIENTE,
                PendingQuestion.deleted_at.is_(None),
            )
            .order_by(
                PendingQuestion.prioridad,  # ALTA primero
                PendingQuestion.monto_relacionado.desc(),
            )
            .limit(limite)
        )
        
        return list(self.db.execute(stmt).scalars().all())

    def resumen_reconciliacion(self, profile_id: str) -> dict[str, Any]:
        """
        Genera un resumen del estado de reconciliación.
        
        Returns:
            Dict con estadísticas
        """
        # Transferencias totales
        total_transferencias = self.db.query(Transaction).filter(
            Transaction.profile_id == profile_id,
            Transaction.deleted_at.is_(None),
            Transaction.tipo_transaccion == "transferencia",
        ).count()
        
        # Necesitan reconciliación
        necesitan_reconciliacion = self.db.query(Transaction).filter(
            Transaction.profile_id == profile_id,
            Transaction.deleted_at.is_(None),
            Transaction.necesita_reconciliacion_sinpe == True,
        ).count()
        
        # Preguntas pendientes
        preguntas_pendientes = self.db.query(PendingQuestion).filter(
            PendingQuestion.profile_id == profile_id,
            PendingQuestion.status == QuestionStatus.PENDIENTE,
        ).count()
        
        # Preguntas respondidas
        preguntas_respondidas = self.db.query(PendingQuestion).filter(
            PendingQuestion.profile_id == profile_id,
            PendingQuestion.status == QuestionStatus.RESPONDIDA,
        ).count()
        
        # Monto total pendiente de reconciliación
        from sqlalchemy import func
        monto_pendiente = self.db.query(func.sum(Transaction.monto_crc)).filter(
            Transaction.profile_id == profile_id,
            Transaction.deleted_at.is_(None),
            Transaction.necesita_reconciliacion_sinpe == True,
        ).scalar() or Decimal("0")
        
        return {
            "total_transferencias": total_transferencias,
            "necesitan_reconciliacion": necesitan_reconciliacion,
            "reconciliadas": total_transferencias - necesitan_reconciliacion,
            "preguntas_pendientes": preguntas_pendientes,
            "preguntas_respondidas": preguntas_respondidas,
            "monto_pendiente_crc": float(monto_pendiente),
            "porcentaje_reconciliado": (
                (total_transferencias - necesitan_reconciliacion) / total_transferencias * 100
                if total_transferencias > 0 else 100
            ),
        }
