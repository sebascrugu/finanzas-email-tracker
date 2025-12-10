"""
Servicio de Onboarding Simplificado para nuevos usuarios.

Flujo simplificado en 3 pasos:
1. Conectar correo (o subir PDF manualmente)
2. Importar estados de cuenta automáticamente  
3. ¡Listo! Dashboard con datos reales

Lógica de importación:
- Buscar estado de cuenta más reciente (máximo 1 mes atrás)
- Si no hay, usuario puede subir PDF o empezar desde día 1 del mes actual
- Buscar correos desde (fecha_corte - 5 días) hasta HOY
- Generar preguntas para SINPEs sin descripción y comercios desconocidos
- Marcar datos como "tentativos" si no hay estado de cuenta base

NO preguntamos patrimonio ni presupuesto inicial.
Los datos vienen directamente del banco (PDF/correo).
El presupuesto se sugiere basado en el historial real.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
import logging
from pathlib import Path
import tempfile
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.models import (
    Account,
    BillingCycle,
    Card,
    PendingQuestion,
    QuestionType,
    QuestionPriority,
)
from finanzas_tracker.models.enums import (
    AccountType,
    BankName,
    CardType,
    Currency,
)


logger = logging.getLogger(__name__)


class OnboardingStep(str, Enum):
    """Pasos simplificados del onboarding (solo 3 pasos)."""

    # Nuevo flujo simplificado
    CONNECT_EMAIL = "connect_email"  # Paso 1: Conectar correo o subir PDF
    IMPORT_DATA = "import_data"  # Paso 2: Importar estados de cuenta
    READY = "ready"  # Paso 3: ¡Listo para usar!

    # Legacy steps (mantener para compatibilidad con datos existentes)
    REGISTERED = "registered"  # Usuario creado (legacy)
    PDF_UPLOADED = "pdf_uploaded"  # PDF procesado (legacy)
    ACCOUNTS_CONFIRMED = "accounts_confirmed"  # Cuentas confirmadas (legacy)
    CARDS_CONFIRMED = "cards_confirmed"  # Tarjetas confirmadas (legacy)
    BUDGET_SET = "budget_set"  # Presupuesto configurado (legacy)
    COMPLETED = "completed"  # Onboarding completo (legacy, usar READY)


@dataclass
class DetectedAccount:
    """Cuenta detectada del PDF."""

    numero_cuenta: str  # últimos 4 dígitos
    tipo: AccountType
    banco: BankName
    saldo: Decimal
    moneda: Currency = Currency.CRC
    nombre_sugerido: str = ""

    def to_dict(self) -> dict:
        """Convierte a diccionario para JSON."""
        return {
            "numero_cuenta": self.numero_cuenta,
            "tipo": self.tipo.value,
            "banco": self.banco.value,
            "saldo": float(self.saldo),
            "moneda": self.moneda.value,
            "nombre_sugerido": self.nombre_sugerido,
        }


@dataclass
class DetectedCard:
    """Tarjeta detectada del PDF."""

    ultimos_4_digitos: str
    marca: str | None  # VISA, Mastercard
    banco: BankName
    tipo_sugerido: CardType | None = None  # Si podemos inferir
    limite_credito: Decimal | None = None
    saldo_actual: Decimal | None = None
    fecha_corte: int | None = None  # día del mes
    fecha_pago: int | None = None  # día del mes

    def to_dict(self) -> dict:
        """Convierte a diccionario para JSON."""
        return {
            "ultimos_4_digitos": self.ultimos_4_digitos,
            "marca": self.marca,
            "banco": self.banco.value,
            "tipo_sugerido": self.tipo_sugerido.value if self.tipo_sugerido else None,
            "limite_credito": float(self.limite_credito) if self.limite_credito else None,
            "saldo_actual": float(self.saldo_actual) if self.saldo_actual else None,
            "fecha_corte": self.fecha_corte,
            "fecha_pago": self.fecha_pago,
        }


@dataclass
class OnboardingState:
    """Estado actual del onboarding simplificado."""

    user_id: str
    profile_id: str | None = None
    current_step: OnboardingStep = OnboardingStep.CONNECT_EMAIL  # Nuevo default
    
    # Datos detectados
    detected_accounts: list[DetectedAccount] = field(default_factory=list)
    detected_cards: list[DetectedCard] = field(default_factory=list)
    
    # Estado de conexión
    email_connected: bool = False
    pdf_processed: bool = False
    
    # Estado de datos
    tiene_estado_cuenta_base: bool = False  # Nuevo: ¿Tenemos un estado de cuenta de referencia?
    datos_tentativos: bool = False  # Nuevo: ¿Los datos son tentativos (sin estado de cuenta)?
    fecha_corte_base: date | None = None  # Nuevo: Fecha de corte del estado de cuenta base
    
    # Estadísticas de importación
    transactions_count: int = 0
    transactions_nuevas: int = 0  # Nuevo: Cuántas son nuevas (post-corte)
    statements_found: int = 0  # Cuántos PDFs encontramos
    statements_processed: int = 0  # Cuántos procesamos
    
    # Preguntas pendientes generadas
    preguntas_generadas: int = 0  # Nuevo
    
    # Datos inferidos del banco (no preguntamos al usuario)
    saldo_inicial_detectado: Decimal | None = None
    ingresos_mensuales_estimados: Decimal | None = None
    gastos_mensuales_promedio: Decimal | None = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # Storage para transacciones del PDF
    pdf_transactions: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convierte a diccionario para JSON/API."""
        return {
            "user_id": self.user_id,
            "profile_id": self.profile_id,
            "current_step": self.current_step.value,
            "detected_accounts": [a.to_dict() for a in self.detected_accounts],
            "detected_cards": [c.to_dict() for c in self.detected_cards],
            "pdf_processed": self.pdf_processed,
            "email_connected": self.email_connected,
            "transactions_count": self.transactions_count,
            "transactions_nuevas": self.transactions_nuevas,
            "statements_found": self.statements_found,
            "statements_processed": self.statements_processed,
            # Estado de datos
            "tiene_estado_cuenta_base": self.tiene_estado_cuenta_base,
            "datos_tentativos": self.datos_tentativos,
            "fecha_corte_base": self.fecha_corte_base.isoformat() if self.fecha_corte_base else None,
            "preguntas_generadas": self.preguntas_generadas,
            # Datos inferidos del banco
            "saldo_inicial": float(self.saldo_inicial_detectado) if self.saldo_inicial_detectado else None,
            "ingresos_estimados": float(self.ingresos_mensuales_estimados) if self.ingresos_mensuales_estimados else None,
            "gastos_promedio": float(self.gastos_mensuales_promedio) if self.gastos_mensuales_promedio else None,
            "progress_percent": self._calculate_progress(),
        }

    def _calculate_progress(self) -> int:
        """Calcula porcentaje de progreso (flujo simplificado de 3 pasos)."""
        # Mapear a porcentaje basado en los 3 pasos principales
        progress_map = {
            OnboardingStep.CONNECT_EMAIL: 0,
            OnboardingStep.IMPORT_DATA: 50,
            OnboardingStep.READY: 100,
            # Legacy steps mapean a completado
            OnboardingStep.REGISTERED: 0,
            OnboardingStep.PDF_UPLOADED: 33,
            OnboardingStep.ACCOUNTS_CONFIRMED: 50,
            OnboardingStep.CARDS_CONFIRMED: 66,
            OnboardingStep.BUDGET_SET: 83,
            OnboardingStep.COMPLETED: 100,
        }
        return progress_map.get(self.current_step, 0)


class OnboardingService:
    """
    Servicio para onboarding simplificado.

    Flujo principal (3 pasos):
    1. CONNECT_EMAIL: Usuario conecta su correo Outlook (o sube PDF)
    2. IMPORT_DATA: Sistema busca e importa estados de cuenta automáticamente
    3. READY: Dashboard listo con datos reales

    NO preguntamos:
    - Patrimonio (viene del saldo del estado de cuenta)
    - Presupuesto inicial (se sugiere basado en historial real)
    - Inveriones, metas, etc. (se configuran después opcionalmente)
    """

    def __init__(self, db: Session) -> None:
        """Inicializa el servicio."""
        self.db = db
        # Cache temporal de estados de onboarding (en producción usar Redis)
        self._states: dict[str, OnboardingState] = {}

    # =========================================================================
    # Estado del Onboarding
    # =========================================================================

    def start_onboarding(self, user_id: str) -> OnboardingState:
        """
        Inicia el proceso de onboarding para un usuario.

        Args:
            user_id: ID del usuario registrado

        Returns:
            Estado inicial del onboarding
        """
        state = OnboardingState(user_id=user_id)
        self._states[user_id] = state
        logger.info(f"Onboarding iniciado para usuario {user_id[:8]}...")
        return state

    def get_state(self, user_id: str) -> OnboardingState | None:
        """Obtiene el estado actual del onboarding."""
        return self._states.get(user_id)

    def update_step(self, user_id: str, step: OnboardingStep) -> OnboardingState | None:
        """Actualiza el paso actual del onboarding."""
        state = self._states.get(user_id)
        if state:
            state.current_step = step
            logger.info(f"Onboarding {user_id[:8]}... → {step.value}")
        return state

    # =========================================================================
    # FLUJO SIMPLIFICADO - Método Principal
    # =========================================================================

    def auto_discover_from_email(
        self,
        user_id: str,
        profile_id: str,
        max_days_back: int = 31,  # Máximo 1 mes atrás para estado de cuenta
    ) -> OnboardingState:
        """
        🚀 MÉTODO PRINCIPAL DEL ONBOARDING SIMPLIFICADO.

        Flujo:
        1. Buscar estado de cuenta más reciente (máx 1 mes atrás)
        2. Si lo encuentra:
           - Usarlo como base (fecha de corte)
           - Buscar correos desde (corte - 5 días) hasta HOY
        3. Si NO lo encuentra:
           - Marcar datos como "tentativos"
           - Buscar correos desde día 1 del mes actual hasta HOY
        4. Generar preguntas para SINPEs sin descripción

        Args:
            user_id: ID del usuario
            profile_id: ID del perfil
            max_days_back: Máximo días para buscar estado de cuenta (default: 31)

        Returns:
            Estado del onboarding con datos importados
        """
        from finanzas_tracker.services.statement_email_service import StatementEmailService

        # Iniciar o recuperar estado
        state = self._states.get(user_id)
        if not state:
            state = self.start_onboarding(user_id)

        state.profile_id = profile_id
        state.current_step = OnboardingStep.IMPORT_DATA

        logger.info(f"🔍 Iniciando onboarding para {user_id[:8]}... (máx {max_days_back} días atrás)")

        try:
            email_service = StatementEmailService()
            hoy = date.today()

            # =============================================
            # PASO 1: Buscar estado de cuenta (máx 1 mes)
            # =============================================
            statements = email_service.fetch_statement_emails(days_back=max_days_back)
            state.statements_found = len(statements)
            state.email_connected = True

            if statements:
                logger.info(f"📧 Encontrados {len(statements)} estados de cuenta")
                
                # Procesar el estado de cuenta más reciente primero
                results = email_service.process_all_pending(
                    profile_id=profile_id,
                    days_back=max_days_back,
                    save_pdfs=True,
                    save_to_db=True,
                )

                # Contabilizar y detectar fecha de corte
                total_txn = 0
                fecha_corte_detectada = None
                
                for result in results:
                    if result.error is None:
                        state.statements_processed += 1
                        total_txn += result.transactions_created
                        
                        # Intentar obtener fecha de corte del resultado
                        if hasattr(result, 'fecha_corte') and result.fecha_corte:
                            if fecha_corte_detectada is None or result.fecha_corte > fecha_corte_detectada:
                                fecha_corte_detectada = result.fecha_corte

                state.transactions_count = total_txn
                state.pdf_processed = True
                state.tiene_estado_cuenta_base = True
                state.datos_tentativos = False

                # Si detectamos fecha de corte, guardarla
                if fecha_corte_detectada:
                    state.fecha_corte_base = fecha_corte_detectada
                    logger.info(f"📅 Fecha de corte detectada: {fecha_corte_detectada}")
                
                # =============================================
                # PASO 2: Buscar correos adicionales (post-corte)
                # =============================================
                # Buscar desde (corte - 5 días) hasta hoy para capturar txns rezagadas
                if state.fecha_corte_base:
                    fecha_desde = state.fecha_corte_base - timedelta(days=5)
                    self._importar_correos_transacciones(
                        state, 
                        email_service, 
                        profile_id, 
                        fecha_desde, 
                        hoy
                    )

            else:
                # =============================================
                # SIN ESTADO DE CUENTA - Datos tentativos
                # =============================================
                logger.info("📭 No se encontraron estados de cuenta - modo tentativo")
                
                state.tiene_estado_cuenta_base = False
                state.datos_tentativos = True
                
                # Buscar desde día 1 del mes actual
                primer_dia_mes = date(hoy.year, hoy.month, 1)
                
                self._importar_correos_transacciones(
                    state,
                    email_service,
                    profile_id,
                    primer_dia_mes,
                    hoy
                )

            # =============================================
            # PASO 3: Inferir datos financieros
            # =============================================
            self._inferir_datos_financieros(state, profile_id)

            # =============================================
            # PASO 4: Generar preguntas pendientes
            # =============================================
            preguntas = self._generar_preguntas_pendientes(state, profile_id)
            state.preguntas_generadas = len(preguntas)

            # ¡Listo!
            state.current_step = OnboardingStep.READY

            logger.info(
                f"✅ Onboarding completado para {user_id[:8]}...: "
                f"{state.statements_processed} PDFs, "
                f"{state.transactions_count} transacciones"
                f"{' (TENTATIVAS)' if state.datos_tentativos else ''}, "
                f"{state.preguntas_generadas} preguntas generadas"
            )

        except Exception as e:
            logger.error(f"Error en auto_discover: {e}")
            # Aún así marcamos como listo, el usuario puede continuar
            state.current_step = OnboardingStep.READY
            state.datos_tentativos = True

        return state

    def _importar_correos_transacciones(
        self,
        state: OnboardingState,
        email_service: Any,
        profile_id: str,
        fecha_desde: date,
        fecha_hasta: date,
    ) -> None:
        """
        Importa transacciones de correos (notificaciones) en un rango de fechas.
        
        Esto captura compras del día a día que llegan por email.
        """
        # TODO: Implementar cuando tengamos el servicio de email de transacciones
        # Por ahora solo logueamos
        logger.info(
            f"📧 Buscando correos de transacciones desde {fecha_desde} hasta {fecha_hasta}"
        )
        
        # Aquí iría la lógica para:
        # 1. Buscar correos de BAC/Popular con notificaciones de compra
        # 2. Parsear cada uno
        # 3. Crear transacciones (marcando como tentativas si datos_tentativos=True)
        pass

    def _generar_preguntas_pendientes(
        self,
        state: OnboardingState,
        profile_id: str,
    ) -> list[PendingQuestion]:
        """
        Genera preguntas para transacciones que necesitan input del usuario.
        
        Tipos de preguntas:
        - SINPEs sin descripción clara
        - Comercios desconocidos
        - Transacciones con categoría ambigua
        
        Prioriza por monto (mayores primero).
        """
        from finanzas_tracker.models import Transaction
        
        preguntas = []
        
        try:
            # Buscar transacciones que necesitan revisión
            txns_revision = (
                self.db.query(Transaction)
                .filter(
                    Transaction.profile_id == profile_id,
                    Transaction.deleted_at.is_(None),
                    Transaction.necesita_revision == True,
                )
                .order_by(Transaction.monto_crc.desc())  # Mayores primero
                .limit(20)  # Máximo 20 preguntas para no abrumar
                .all()
            )
            
            for txn in txns_revision:
                pregunta = None
                
                # Detectar tipo de pregunta según la transacción
                if txn.tipo_transaccion and "sinpe" in str(txn.tipo_transaccion).lower():
                    # SINPE sin descripción
                    if not txn.comercio or txn.comercio.strip() == "" or txn.es_desconocida:
                        pregunta = PendingQuestion(
                            profile_id=profile_id,
                            transaction_id=txn.id,
                            tipo=QuestionType.SINPE_SIN_DESCRIPCION,
                            prioridad=QuestionPriority.ALTA if txn.monto_crc > 20000 else QuestionPriority.MEDIA,
                            pregunta=f"¿Qué es este SINPE de ₡{txn.monto_crc:,.0f}?",
                            contexto=f'{{"fecha": "{txn.fecha_transaccion.isoformat()}"}}',
                            opciones='["Comida", "Transporte", "Servicios", "Personal", "Otro..."]',
                            monto_relacionado=txn.monto_crc,
                            origen="onboarding",
                        )
                elif txn.es_desconocida or txn.es_comercio_ambiguo:
                    # Comercio desconocido o ambiguo
                    pregunta = PendingQuestion(
                        profile_id=profile_id,
                        transaction_id=txn.id,
                        tipo=QuestionType.COMERCIO_DESCONOCIDO if txn.es_desconocida else QuestionType.CATEGORIA_AMBIGUA,
                        prioridad=QuestionPriority.MEDIA,
                        pregunta=f"¿Qué tipo de comercio es '{txn.comercio}'?",
                        contexto=f'{{"comercio": "{txn.comercio}", "monto": {float(txn.monto_crc)}}}',
                        opciones='["Supermercado", "Restaurante", "Gasolinera", "Tienda", "Servicio", "Otro..."]',
                        monto_relacionado=txn.monto_crc,
                        origen="onboarding",
                    )
                
                if pregunta:
                    self.db.add(pregunta)
                    preguntas.append(pregunta)
            
            if preguntas:
                self.db.commit()
                logger.info(f"💬 Generadas {len(preguntas)} preguntas pendientes")
        
        except Exception as e:
            logger.error(f"Error generando preguntas: {e}")
            self.db.rollback()
        
        return preguntas

    def procesar_pdf_manual(
        self,
        user_id: str,
        profile_id: str,
        pdf_path: str | Path,
    ) -> OnboardingState:
        """
        Procesa un PDF subido manualmente por el usuario.
        
        Se usa cuando:
        - No se encontró estado de cuenta en el correo
        - Usuario prefiere subir manualmente
        
        Args:
            user_id: ID del usuario
            profile_id: ID del perfil
            pdf_path: Ruta al archivo PDF
        
        Returns:
            Estado del onboarding actualizado
        """
        from finanzas_tracker.parsers.bac_pdf_parser import BACPDFParser
        from finanzas_tracker.parsers.bac_credit_card_parser import BACCreditCardParser
        
        state = self._states.get(user_id)
        if not state:
            state = self.start_onboarding(user_id)
        
        state.profile_id = profile_id
        state.current_step = OnboardingStep.IMPORT_DATA
        
        logger.info(f"📄 Procesando PDF manual: {pdf_path}")
        
        try:
            pdf_path = Path(pdf_path)
            
            # Intentar con parser de estado de cuenta primero
            parser = BACPDFParser()
            result = parser.parse(str(pdf_path))
            
            if not result or not result.get("transactions"):
                # Intentar con parser de tarjeta de crédito
                cc_parser = BACCreditCardParser()
                result = cc_parser.parse(str(pdf_path))
            
            if result and result.get("transactions"):
                # Tenemos datos del PDF
                state.tiene_estado_cuenta_base = True
                state.datos_tentativos = False
                state.pdf_processed = True
                
                # Extraer fecha de corte si está disponible
                if result.get("fecha_corte"):
                    state.fecha_corte_base = result["fecha_corte"]
                
                # Guardar transacciones
                txn_count = self._guardar_transacciones_pdf(
                    result["transactions"],
                    profile_id,
                    result.get("banco", "bac")
                )
                state.transactions_count = txn_count
                state.statements_processed = 1
                
                logger.info(f"✅ PDF procesado: {txn_count} transacciones")
            else:
                logger.warning("⚠️ No se pudieron extraer transacciones del PDF")
                state.datos_tentativos = True
        
        except Exception as e:
            logger.error(f"Error procesando PDF: {e}")
            state.datos_tentativos = True
        
        # Continuar con el resto del flujo
        self._inferir_datos_financieros(state, profile_id)
        preguntas = self._generar_preguntas_pendientes(state, profile_id)
        state.preguntas_generadas = len(preguntas)
        state.current_step = OnboardingStep.READY
        
        return state

    def _guardar_transacciones_pdf(
        self,
        transactions: list[dict],
        profile_id: str,
        banco: str,
    ) -> int:
        """Guarda transacciones extraídas del PDF en la base de datos."""
        from finanzas_tracker.models import Transaction
        from finanzas_tracker.models.enums import TransactionType, TransactionStatus
        import uuid
        
        count = 0
        
        for txn_data in transactions:
            try:
                # Crear transacción
                txn = Transaction(
                    id=str(uuid.uuid4()),
                    email_id=f"pdf-manual-{uuid.uuid4().hex[:8]}",
                    profile_id=profile_id,
                    banco=BankName(banco) if banco else BankName.BAC,
                    tipo_transaccion=TransactionType.COMPRA,
                    comercio=txn_data.get("comercio", "Desconocido"),
                    monto_original=Decimal(str(txn_data.get("monto", 0))),
                    moneda_original=Currency.CRC,
                    monto_crc=Decimal(str(txn_data.get("monto", 0))),
                    fecha_transaccion=txn_data.get("fecha", datetime.now()),
                    estado=TransactionStatus.CONFIRMADA,
                    es_historica=True,  # Viene del PDF histórico
                    necesita_revision=txn_data.get("necesita_revision", False),
                )
                
                self.db.add(txn)
                count += 1
                
            except Exception as e:
                logger.warning(f"Error guardando transacción: {e}")
                continue
        
        if count > 0:
            self.db.commit()
        
        return count

    def _inferir_datos_financieros(self, state: OnboardingState, profile_id: str) -> None:
        """
        Infiere datos financieros del historial importado.

        En vez de preguntar al usuario, calculamos:
        - Saldo inicial (del último estado de cuenta)
        - Ingresos mensuales estimados (promedio de ingresos detectados)
        - Gastos mensuales promedio
        """
        from sqlalchemy import func, text

        try:
            # Obtener estadísticas de las transacciones importadas
            result = self.db.execute(
                text("""
                    SELECT 
                        -- Gastos promedio mensual
                        COALESCE(AVG(gastos_mes), 0) as gastos_promedio,
                        -- Ingresos promedio (transacciones con monto positivo grandes)
                        COALESCE(AVG(ingresos_mes), 0) as ingresos_promedio
                    FROM (
                        SELECT 
                            TO_CHAR(fecha_transaccion, 'YYYY-MM') as mes,
                            SUM(CASE WHEN tipo_transaccion = 'compra' THEN monto_crc ELSE 0 END) as gastos_mes,
                            SUM(CASE WHEN tipo_transaccion = 'ingreso' 
                                OR (tipo_transaccion = 'transferencia' AND monto_crc > 100000) 
                                THEN monto_crc ELSE 0 END) as ingresos_mes
                        FROM transactions
                        WHERE profile_id = :profile_id
                        AND deleted_at IS NULL
                        GROUP BY mes
                    ) monthly
                """),
                {"profile_id": profile_id}
            ).fetchone()

            if result:
                state.gastos_mensuales_promedio = Decimal(str(result[0])) if result[0] else None
                state.ingresos_mensuales_estimados = Decimal(str(result[1])) if result[1] else None

            # Obtener saldo del último estado procesado (aproximación)
            # Por ahora usamos la suma de transacciones como proxy
            saldo_result = self.db.execute(
                text("""
                    SELECT SUM(
                        CASE 
                            WHEN tipo_transaccion IN ('ingreso', 'transferencia') THEN monto_crc
                            ELSE -monto_crc
                        END
                    ) as saldo_neto
                    FROM transactions
                    WHERE profile_id = :profile_id
                    AND deleted_at IS NULL
                """),
                {"profile_id": profile_id}
            ).scalar()

            # Este es una aproximación, el saldo real viene del PDF metadata
            if saldo_result:
                state.saldo_inicial_detectado = abs(Decimal(str(saldo_result)))

        except Exception as e:
            logger.warning(f"No se pudo inferir datos financieros: {e}")

    def complete_simplified_onboarding(
        self,
        user_id: str,
    ) -> OnboardingState | None:
        """
        Marca el onboarding simplificado como completado.

        A diferencia del flujo antiguo, NO requiere:
        - Patrimonio inicial (ya lo tenemos del PDF)
        - Presupuesto (se sugiere después basado en datos reales)

        Args:
            user_id: ID del usuario

        Returns:
            Estado final
        """
        state = self._states.get(user_id)
        if not state:
            return None

        state.current_step = OnboardingStep.READY
        logger.info(f"🎉 Onboarding simplificado completado para {user_id[:8]}...")
        return state

    # =========================================================================
    # Procesamiento de PDF
    # =========================================================================

    def process_pdf(
        self,
        user_id: str,
        pdf_content: bytes,
        banco: BankName = BankName.BAC,
    ) -> OnboardingState:
        """
        Procesa un PDF de estado de cuenta y extrae cuentas/tarjetas.

        Args:
            user_id: ID del usuario
            pdf_content: Contenido del PDF en bytes
            banco: Banco del estado de cuenta

        Returns:
            Estado actualizado con detecciones
        """
        state = self._states.get(user_id)
        if not state:
            state = self.start_onboarding(user_id)

        # Importar parser
        from finanzas_tracker.parsers.bac_pdf_parser import BACPDFParser, BACStatementResult

        if banco == BankName.BAC:
            parser = BACPDFParser()
            # Parser expects a file path, so we write bytes to a temp file
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_content)
                tmp_path = Path(tmp.name)

            try:
                result: BACStatementResult = parser.parse(tmp_path)

                # Extraer cuentas detectadas
                state.detected_accounts = self._extract_accounts_from_pdf(result, banco)

                # Extraer tarjetas detectadas
                state.detected_cards = self._extract_cards_from_pdf(result, banco)

                # Contar transacciones
                state.transactions_count = len(result.transactions)

                state.pdf_processed = True
                state.current_step = OnboardingStep.PDF_UPLOADED

                logger.info(
                    f"PDF procesado: {len(state.detected_accounts)} cuentas, "
                    f"{len(state.detected_cards)} tarjetas, "
                    f"{state.transactions_count} transacciones"
                )

                # Guardar transacciones en el estado para importación posterior
                state.pdf_transactions = list(result.transactions)
            finally:
                # Clean up temp file
                tmp_path.unlink(missing_ok=True)
        else:
            logger.warning(f"Parser para {banco} no implementado en onboarding")

        return state

    def import_transactions_from_pdf(
        self,
        user_id: str,
        profile_id: str,
        fecha_base: date,
        importar_historicas: bool = True,
    ) -> dict:
        """
        Importa transacciones del PDF procesado.

        Las transacciones anteriores a fecha_base se marcan como históricas
        y no afectan el cálculo de patrimonio.

        Args:
            user_id: ID del usuario
            profile_id: ID del perfil
            fecha_base: Fecha límite para marcar como históricas
            importar_historicas: Si importar transacciones anteriores a fecha_base

        Returns:
            Diccionario con estadísticas de importación
        """
        from finanzas_tracker.models.enums import TransactionStatus
        from finanzas_tracker.models.transaction import Transaction
        from finanzas_tracker.services.internal_transfer_detector import InternalTransferDetector

        state = self._states.get(user_id)
        if not state or not hasattr(state, "_pdf_transactions"):
            return {"error": "No hay PDF procesado para este usuario"}

        transactions = state._pdf_transactions
        stats = {
            "total": len(transactions),
            "importadas": 0,
            "historicas": 0,
            "recientes": 0,
            "duplicadas": 0,
            "transferencias_internas": 0,
        }

        transfer_detector = InternalTransferDetector(self.db)

        for tx_data in transactions:
            fecha_tx = tx_data.get("fecha")
            if isinstance(fecha_tx, str):
                fecha_tx = datetime.strptime(fecha_tx, "%Y-%m-%d").date()

            es_historica = fecha_tx < fecha_base

            if es_historica and not importar_historicas:
                continue

            try:
                # Crear transacción
                transaction = Transaction(
                    profile_id=profile_id,
                    email_id=f"pdf_import_{user_id}_{tx_data.get('referencia', '')}_{fecha_tx}",
                    banco=tx_data.get("banco", "bac"),
                    comercio=tx_data.get("comercio", tx_data.get("descripcion", "")),
                    tipo_transaccion=tx_data.get("tipo", "compra"),
                    monto_original=Decimal(str(tx_data.get("monto", 0))),
                    monto_crc=Decimal(str(tx_data.get("monto_crc", tx_data.get("monto", 0)))),
                    moneda=tx_data.get("moneda", "CRC"),
                    fecha_transaccion=fecha_tx,
                    es_historica=es_historica,
                    estado=TransactionStatus.CONFIRMED.value
                    if es_historica
                    else TransactionStatus.PENDING.value,
                    referencia_banco=tx_data.get("referencia"),
                )

                self.db.add(transaction)
                self.db.flush()  # Para obtener el ID

                # Detectar transferencias internas
                if transfer_detector.es_transferencia_interna(transaction):
                    transfer_detector.procesar_pago_tarjeta(transaction, profile_id)
                    stats["transferencias_internas"] += 1

                stats["importadas"] += 1
                if es_historica:
                    stats["historicas"] += 1
                else:
                    stats["recientes"] += 1

            except Exception as e:
                if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                    stats["duplicadas"] += 1
                else:
                    logger.error(f"Error importando transacción: {e}")

        self.db.commit()

        logger.info(
            f"Importación completada: {stats['importadas']} transacciones "
            f"({stats['historicas']} históricas, {stats['recientes']} recientes)"
        )

        return stats

    def _extract_accounts_from_pdf(
        self,
        pdf_data: Any,
        banco: BankName,
    ) -> list[DetectedAccount]:
        """Extrae cuentas del resultado del parser."""
        accounts = []

        # Handle BACStatementResult dataclass
        if hasattr(pdf_data, "metadata"):
            metadata = pdf_data.metadata
            if hasattr(metadata, "cuentas") and metadata.cuentas:
                for cuenta in metadata.cuentas:
                    numero = cuenta.get("iban", "")[-4:] if cuenta.get("iban") else ""
                    if numero:
                        accounts.append(
                            DetectedAccount(
                                numero_cuenta=numero,
                                tipo=AccountType.CHECKING,
                                banco=banco,
                                saldo=Decimal(str(cuenta.get("saldo", 0))),
                                nombre_sugerido=f"Cuenta {banco.value.upper()} ***{numero}",
                            )
                        )
            return accounts

        # Legacy dict handling
        account_info = pdf_data.get("account_info", {}) if isinstance(pdf_data, dict) else {}

        if account_info:
            # Cuenta principal del estado
            numero = (
                account_info.get("account_number", "")[-4:]
                if account_info.get("account_number")
                else ""
            )
            if numero:
                accounts.append(
                    DetectedAccount(
                        numero_cuenta=numero,
                        tipo=AccountType.CHECKING,  # Asumir corriente por defecto
                        banco=banco,
                        saldo=Decimal(str(account_info.get("balance", 0))),
                        nombre_sugerido=f"Cuenta {banco.value.upper()} ***{numero}",
                    )
                )

        # También buscar en transacciones si hay referencias a otras cuentas
        # TODO: Implementar detección más sofisticada

        return accounts

    def _extract_cards_from_pdf(
        self,
        pdf_data: Any,
        banco: BankName,
    ) -> list[DetectedCard]:
        """Extrae tarjetas del resultado del parser."""
        cards: list[DetectedCard] = []
        seen_cards: set[str] = set()

        # Handle BACStatementResult dataclass
        if hasattr(pdf_data, "transactions"):
            transactions_list = pdf_data.transactions
        elif isinstance(pdf_data, dict):
            transactions_list = pdf_data.get("transactions", [])
        else:
            transactions_list = []

        for tx in transactions_list:
            # Handle both dict and BACTransaction dataclass
            if hasattr(tx, "cuenta_iban"):
                # BACTransaction - extract last 4 from IBAN
                card_digits = tx.cuenta_iban[-4:] if tx.cuenta_iban else None
            else:
                # Dict format
                card_digits = tx.get("ultimos_4_digitos") or tx.get("card_last_4")

            if card_digits and card_digits not in seen_cards:
                seen_cards.add(card_digits)

                # Intentar inferir tipo de tarjeta
                if hasattr(tx, "tipo"):
                    tx_type = tx.tipo
                else:
                    tx_type = tx.get("tipo", "") if isinstance(tx, dict) else ""
                es_credito = tx_type in ["interes_cobrado", "pago_servicio", "credito"]

                cards.append(
                    DetectedCard(
                        ultimos_4_digitos=card_digits,
                        marca=None,  # El parser no siempre lo tiene
                        banco=banco,
                        tipo_sugerido=CardType.CREDIT if es_credito else None,
                    )
                )

        # También buscar en info del estado de cuenta (dict format only)
        if isinstance(pdf_data, dict):
            card_info = pdf_data.get("card_info", {})
            if card_info:
                card_number = card_info.get("card_number", "")[-4:]
                if card_number and card_number not in seen_cards:
                    cards.append(
                        DetectedCard(
                            ultimos_4_digitos=card_number,
                            marca=card_info.get("brand"),
                            banco=banco,
                            tipo_sugerido=CardType.CREDIT,
                            limite_credito=Decimal(str(card_info.get("credit_limit", 0)))
                            if card_info.get("credit_limit")
                            else None,
                            saldo_actual=Decimal(str(card_info.get("balance", 0)))
                            if card_info.get("balance")
                            else None,
                            fecha_corte=card_info.get("cut_day"),
                            fecha_pago=card_info.get("due_day"),
                        )
                    )

        return cards

    # =========================================================================
    # Confirmación de Cuentas
    # =========================================================================

    def confirm_accounts(
        self,
        user_id: str,
        profile_id: str,
        confirmed_accounts: list[dict],
    ) -> list[Account]:
        """
        Crea las cuentas confirmadas por el usuario.

        Args:
            user_id: ID del usuario
            profile_id: ID del perfil
            confirmed_accounts: Lista de cuentas con datos confirmados/editados

        Returns:
            Lista de cuentas creadas
        """
        state = self._states.get(user_id)
        if not state:
            raise ValueError("No hay onboarding activo para este usuario")

        state.profile_id = profile_id
        created = []

        for acc_data in confirmed_accounts:
            account = Account(
                profile_id=profile_id,
                nombre=acc_data.get("nombre", f"Cuenta ***{acc_data['numero_cuenta']}"),
                banco=BankName(acc_data["banco"]),
                tipo=AccountType(acc_data["tipo"]),
                numero_cuenta=acc_data["numero_cuenta"],
                saldo=Decimal(str(acc_data["saldo"])),
                moneda=Currency(acc_data.get("moneda", "CRC")),
                es_cuenta_principal=acc_data.get("es_principal", False),
                incluir_en_patrimonio=True,
            )
            self.db.add(account)
            created.append(account)

        self.db.commit()
        for acc in created:
            self.db.refresh(acc)

        state.current_step = OnboardingStep.ACCOUNTS_CONFIRMED
        logger.info(f"Confirmadas {len(created)} cuentas para {user_id[:8]}...")

        return created

    # =========================================================================
    # Confirmación de Tarjetas
    # =========================================================================

    def confirm_cards(
        self,
        user_id: str,
        profile_id: str,
        confirmed_cards: list[dict],
    ) -> list[Card]:
        """
        Crea las tarjetas confirmadas por el usuario.

        Args:
            user_id: ID del usuario
            profile_id: ID del perfil
            confirmed_cards: Lista de tarjetas con datos confirmados/editados

        Returns:
            Lista de tarjetas creadas
        """
        state = self._states.get(user_id)
        if not state:
            raise ValueError("No hay onboarding activo para este usuario")

        created = []

        for card_data in confirmed_cards:
            card = Card(
                profile_id=profile_id,
                ultimos_4_digitos=card_data["ultimos_4_digitos"],
                tipo=CardType(card_data["tipo"]),
                banco=BankName(card_data["banco"]),
                marca=card_data.get("marca"),
                limite_credito=Decimal(str(card_data["limite_credito"]))
                if card_data.get("limite_credito")
                else None,
                fecha_corte=card_data.get("fecha_corte"),
                fecha_vencimiento=card_data.get("fecha_pago"),
                current_balance=Decimal(str(card_data.get("saldo_actual", 0))),
                interest_rate_annual=Decimal(str(card_data.get("tasa_interes", 52))),  # Default BAC
                minimum_payment_percentage=Decimal("10"),  # 10% típico
            )
            self.db.add(card)
            created.append(card)

        self.db.commit()

        # Crear ciclo de facturación inicial para tarjetas de crédito
        for card in created:
            self.db.refresh(card)
            if card.es_credito and card.fecha_corte:
                self._create_initial_billing_cycle(card)

        state.current_step = OnboardingStep.CARDS_CONFIRMED
        logger.info(f"Confirmadas {len(created)} tarjetas para {user_id[:8]}...")

        return created

    def _create_initial_billing_cycle(self, card: Card) -> BillingCycle | None:
        """Crea el ciclo de facturación inicial para una tarjeta."""
        from finanzas_tracker.services.card_service import CardService

        card_service = CardService(self.db)
        return card_service.create_next_cycle_for_card(card)

    # =========================================================================
    # Finalización
    # =========================================================================

    def complete_onboarding(
        self,
        user_id: str,
        fecha_base: date | None = None,
    ) -> OnboardingState | None:
        """
        Marca el onboarding como completado y establece patrimonio inicial.

        Args:
            user_id: ID del usuario
            fecha_base: Fecha base para el patrimonio (default: hoy)

        Returns:
            Estado final del onboarding
        """
        state = self._states.get(user_id)
        if not state or not state.profile_id:
            return state

        # Establecer patrimonio inicial usando PatrimonyService
        self._establecer_patrimonio_inicial(state.profile_id, fecha_base)

        state.current_step = OnboardingStep.COMPLETED
        logger.info(f"Onboarding completado para {user_id[:8]}...")
        return state

    def _establecer_patrimonio_inicial(
        self,
        profile_id: str,
        fecha_base: date | None = None,
    ) -> None:
        """
        Calcula y guarda el patrimonio inicial del usuario.

        Usa las cuentas y tarjetas confirmadas para calcular:
        - Total activos (saldos de cuentas)
        - Total deudas (saldos de tarjetas de crédito)
        - Patrimonio neto

        Args:
            profile_id: ID del perfil
            fecha_base: Fecha del snapshot inicial
        """
        from finanzas_tracker.services.patrimony_service import PatrimonyService

        patrimony_service = PatrimonyService(self.db)

        # Obtener cuentas
        accounts = (
            self.db.execute(
                select(Account).where(
                    Account.profile_id == profile_id,
                    Account.deleted_at.is_(None),
                    Account.incluir_en_patrimonio.is_(True),
                )
            )
            .scalars()
            .all()
        )

        # Obtener tarjetas de crédito con saldo
        cards = (
            self.db.execute(
                select(Card).where(
                    Card.profile_id == profile_id,
                    Card.deleted_at.is_(None),
                    Card.tipo == CardType.CREDIT,
                )
            )
            .scalars()
            .all()
        )

        # Preparar datos para el servicio de patrimonio
        # Note: saldos_cuentas and deudas_tarjetas are prepared but not directly
        # passed to establecer_patrimonio_inicial as it creates a snapshot from
        # existing account/card data in the database
        _saldos_cuentas = [
            {
                "cuenta_id": acc.id,
                "nombre": acc.nombre,
                "saldo": acc.saldo,
                "moneda": acc.moneda.value if hasattr(acc.moneda, "value") else acc.moneda,
            }
            for acc in accounts
        ]

        _deudas_tarjetas = [
            {
                "tarjeta_id": card.id,
                "ultimos_4": card.ultimos_4_digitos,
                "saldo": card.current_balance or Decimal("0"),
            }
            for card in cards
            if card.current_balance and card.current_balance > 0
        ]

        # Crear snapshot inicial - uses accounts/cards already in DB
        snapshot = patrimony_service.establecer_patrimonio_inicial(
            profile_id=profile_id,
            fecha_base=fecha_base or date.today(),
            notas=f"Onboarding: {len(_saldos_cuentas)} cuentas, {len(_deudas_tarjetas)} tarjetas",
        )

        logger.info(
            f"Patrimonio inicial establecido para {profile_id[:8]}...: "
            f"activos={snapshot.total_activos_crc:,.2f}, "
            f"deudas={snapshot.total_deudas_crc:,.2f}, "
            f"neto={snapshot.patrimonio_neto_crc:,.2f}"
        )

    def get_onboarding_summary(self, user_id: str) -> dict:
        """
        Obtiene un resumen del onboarding completado.

        Args:
            user_id: ID del usuario

        Returns:
            Resumen con cuentas, tarjetas y próximos pasos
        """
        state = self._states.get(user_id)
        if not state or not state.profile_id:
            return {"error": "Onboarding no encontrado"}

        # Contar entidades creadas
        accounts = (
            self.db.execute(
                select(Account).where(
                    Account.profile_id == state.profile_id,
                    Account.deleted_at.is_(None),
                )
            )
            .scalars()
            .all()
        )

        cards = (
            self.db.execute(
                select(Card).where(
                    Card.profile_id == state.profile_id,
                    Card.deleted_at.is_(None),
                )
            )
            .scalars()
            .all()
        )

        credit_cards = [c for c in cards if c.es_credito]

        return {
            "status": "completed"
            if state.current_step == OnboardingStep.COMPLETED
            else "in_progress",
            "progress_percent": state._calculate_progress(),
            "summary": {
                "cuentas_creadas": len(accounts),
                "tarjetas_creadas": len(cards),
                "tarjetas_credito": len(credit_cards),
                "transacciones_importadas": state.transactions_count,
            },
            "next_steps": self._get_next_steps(state, credit_cards),
        }

    def _get_next_steps(
        self,
        state: OnboardingState,
        credit_cards: list[Card],
    ) -> list[str]:
        """Genera sugerencias de próximos pasos."""
        steps = []

        if not state.email_connected:
            steps.append("📧 Conectar email para sync automático")

        if credit_cards:
            steps.append("💳 Revisar fechas de pago de tus tarjetas")

        steps.append("📊 Configurar tu presupuesto 50/30/20")
        steps.append("🎯 Crear tu primera meta de ahorro")

        return steps
