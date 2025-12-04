# 📋 Plan de Implementación - Finanzas Tracker CR

**Fecha:** 3 de Diciembre, 2025  
**Duración estimada:** 4-5 semanas  
**Referencia:** [FLUJO_COMPLETO.md](./FLUJO_COMPLETO.md)

---

## 📊 Estado Actual (Lo que YA existe)

| Componente | Estado | Notas |
|------------|--------|-------|
| Modelo Transaction | ✅ Funcional | Falta agregar campos nuevos |
| Modelo Card | ✅ Funcional | - |
| Modelo BillingCycle | ✅ Funcional | - |
| Modelo Profile | ✅ Funcional | - |
| BACPDFParser (cuentas) | ✅ Funcional | 129 tx parseadas |
| BACCreditCardParser | ✅ Funcional | - |
| StatementEmailService | ✅ Funcional | Fetch emails + consolidación |
| CreditCardStatementService | ✅ Funcional | - |
| BankAccountStatementService | ✅ Funcional | - |
| TransactionCategorizer | ✅ Funcional | - |
| JWT Auth | ✅ Funcional | - |
| API REST (FastAPI) | ✅ Parcial | Falta endpoints nuevos |

---

## 🎯 Lo que FALTA implementar

### Prioridad ALTA (Crítico para el flujo)

| # | Componente | Complejidad | Tiempo Est. |
|---|------------|-------------|-------------|
| 1 | Campos nuevos en Transaction | Baja | 2h |
| 2 | Migración Alembic | Baja | 1h |
| 3 | TransactionStatus enum | Baja | 30min |
| 4 | Modelo ReconciliationReport | Media | 2h |
| 5 | Modelo PatrimonioSnapshot | Media | 2h |
| 6 | ReconciliationService | Alta | 8h |
| 7 | PatrimonioService | Media | 4h |
| 8 | Detección pago tarjeta | Media | 3h |

### Prioridad MEDIA (Mejoras importantes)

| # | Componente | Complejidad | Tiempo Est. |
|---|------------|-------------|-------------|
| 9 | Modelo Account (mejorado) | Media | 3h |
| 10 | Tracking saldo cuentas | Media | 4h |
| 11 | Detección suscripciones | Media | 4h |
| 12 | Notificaciones/Alertas | Media | 4h |
| 13 | Onboarding flow | Alta | 6h |

### Prioridad BAJA (Nice to have)

| # | Componente | Complejidad | Tiempo Est. |
|---|------------|-------------|-------------|
| 14 | Manejo retiros cajero | Baja | 2h |
| 15 | Transacciones en cuotas | Media | 4h |
| 16 | UI para reconciliación | Alta | 8h |

---

## 📅 Plan Detallado por Semana

### 🗓️ SEMANA 1: Fundamentos de Datos

**Objetivo:** Preparar la base de datos para el flujo completo

#### Día 1-2: Actualizar Modelo Transaction

```python
# Agregar estos campos a Transaction:

# Control de afectación a patrimonio
es_historica: bool = Column(Boolean, default=False)
fecha_registro_sistema: datetime = Column(DateTime, default=datetime.utcnow)

# Estado del ciclo de vida
estado: str = Column(String(50), default="pendiente")
# pendiente | confirmada | reconciliada | cancelada | huerfana

# Reconciliación
reconciliacion_id: str = Column(String(50), nullable=True)
reconciliada_en: datetime = Column(DateTime, nullable=True)

# Transferencias internas
es_transferencia_interna: bool = Column(Boolean, default=False)
cuenta_origen_id: str = Column(String(50), nullable=True)
cuenta_destino_id: str = Column(String(50), nullable=True)

# Discrepancias
monto_original_estimado: Decimal = Column(Numeric(12, 2), nullable=True)
monto_ajustado: Decimal = Column(Numeric(12, 2), nullable=True)
razon_ajuste: str = Column(String(100), nullable=True)

# Referencia bancaria
referencia_banco: str = Column(String(100), nullable=True)
```

**Tareas:**
- [ ] Agregar campos al modelo Transaction
- [ ] Crear enum TransactionStatus
- [ ] Actualizar esquemas Pydantic (TransactionCreate, TransactionResponse)
- [ ] Crear migración Alembic

#### Día 3-4: Nuevos Modelos

**ReconciliationReport:**
```python
class ReconciliationReport(Base):
    __tablename__ = "reconciliation_reports"
    
    id = Column(String(50), primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=True)
    profile_id = Column(String(50), nullable=False, index=True)
    
    card_id = Column(String(50), nullable=True)
    account_id = Column(String(50), nullable=True)
    
    periodo_inicio = Column(Date, nullable=False)
    periodo_fin = Column(Date, nullable=False)
    fecha_corte = Column(Date, nullable=False)
    fecha_ejecutada = Column(DateTime, nullable=False)
    
    pdf_filename = Column(String(200))
    pdf_path = Column(String(500))
    email_id = Column(String(200))
    
    total_transacciones_pdf = Column(Integer, default=0)
    total_transacciones_bd = Column(Integer, default=0)
    transacciones_matched = Column(Integer, default=0)
    transacciones_nuevas = Column(Integer, default=0)
    transacciones_huerfanas = Column(Integer, default=0)
    discrepancias_monto = Column(Integer, default=0)
    duplicados_sospechosos = Column(Integer, default=0)
    
    saldo_anterior = Column(Numeric(12, 2))
    saldo_final_pdf = Column(Numeric(12, 2))
    saldo_calculado = Column(Numeric(12, 2))
    diferencia_saldo = Column(Numeric(12, 2))
    
    estado = Column(String(50), default="pendiente_revision")
    notas_usuario = Column(Text, nullable=True)
    
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**PatrimonioSnapshot:**
```python
class PatrimonioSnapshot(Base):
    __tablename__ = "patrimonio_snapshots"
    
    id = Column(String(50), primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=True)
    profile_id = Column(String(50), nullable=False, index=True)
    
    fecha = Column(Date, nullable=False)
    
    total_cuentas = Column(Numeric(12, 2), default=0)
    total_inversiones = Column(Numeric(12, 2), default=0)
    total_deudas = Column(Numeric(12, 2), default=0)
    patrimonio_neto = Column(Numeric(12, 2), nullable=False)
    
    tipo = Column(String(50), default="automatico")
    # inicial | automatico | reconciliacion | manual
    
    notas = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
```

**Tareas:**
- [ ] Crear modelo ReconciliationReport
- [ ] Crear modelo PatrimonioSnapshot
- [ ] Crear esquemas Pydantic correspondientes
- [ ] Crear migración Alembic
- [ ] Registrar modelos en __init__.py

#### Día 5: Testing y Documentación

**Tareas:**
- [ ] Tests unitarios para nuevos modelos
- [ ] Correr migraciones en local
- [ ] Verificar que nada se rompa
- [ ] Actualizar docstrings

---

### 🗓️ SEMANA 2: Servicios Core

**Objetivo:** Implementar la lógica de negocio principal

#### Día 1-2: PatrimonioService

```python
# src/finanzas_tracker/services/patrimonio_service.py

class PatrimonioService:
    """Servicio para calcular y trackear patrimonio."""
    
    def __init__(self) -> None:
        self.logger = get_logger(__name__)
    
    def calcular_patrimonio_actual(self, profile_id: str) -> PatrimonioSnapshot:
        """Calcula el patrimonio actual sumando cuentas - deudas."""
        pass
    
    def crear_snapshot(
        self,
        profile_id: str,
        tipo: str = "automatico",
    ) -> PatrimonioSnapshot:
        """Crea un snapshot del patrimonio actual."""
        pass
    
    def establecer_patrimonio_inicial(
        self,
        profile_id: str,
        saldos_cuentas: list[dict],
        deudas_tarjetas: list[dict],
        fecha_base: date,
    ) -> PatrimonioSnapshot:
        """Establece el patrimonio inicial al registrarse."""
        pass
    
    def actualizar_por_transaccion(
        self,
        profile_id: str,
        transaccion: Transaction,
    ) -> None:
        """Actualiza el patrimonio después de una transacción."""
        pass
    
    def obtener_historial(
        self,
        profile_id: str,
        desde: date | None = None,
        hasta: date | None = None,
    ) -> list[PatrimonioSnapshot]:
        """Obtiene el historial de patrimonio."""
        pass
```

**Tareas:**
- [ ] Crear PatrimonioService
- [ ] Implementar cálculo de patrimonio
- [ ] Implementar snapshots diarios
- [ ] Tests unitarios

#### Día 3-5: ReconciliationService

```python
# src/finanzas_tracker/services/reconciliation_service.py

@dataclass
class MatchResult:
    """Resultado de matching de una transacción."""
    transaccion_pdf: BACTransaction
    transaccion_bd: Transaction | None
    score: int  # 0-100
    tipo: str  # exacto | fuzzy | nuevo | huerfana
    requiere_confirmacion: bool = False
    discrepancia_monto: Decimal | None = None


class ReconciliationService:
    """Servicio para reconciliar estados de cuenta."""
    
    def __init__(self) -> None:
        self.logger = get_logger(__name__)
        self.pdf_parser = BACPDFParser()
        self.credit_parser = BACCreditCardParser()
    
    def reconciliar_estado_cuenta(
        self,
        pdf_path: str,
        profile_id: str,
        card_id: str | None = None,
        account_id: str | None = None,
    ) -> ReconciliationReport:
        """
        Reconcilia un estado de cuenta con las transacciones en BD.
        
        1. Parsea el PDF
        2. Obtiene transacciones del período en BD
        3. Ejecuta algoritmo de matching
        4. Genera reporte con discrepancias
        """
        pass
    
    def _encontrar_match(
        self,
        tx_pdf: BACTransaction,
        transacciones_bd: list[Transaction],
    ) -> MatchResult:
        """Busca la mejor coincidencia para una transacción."""
        pass
    
    def _detectar_duplicados_sospechosos(
        self,
        transacciones: list[BACTransaction],
    ) -> list[tuple[BACTransaction, BACTransaction]]:
        """Detecta posibles cobros duplicados."""
        pass
    
    def _verificar_saldo(
        self,
        saldo_pdf: Decimal,
        saldo_anterior: Decimal,
        transacciones: list[Transaction],
    ) -> tuple[Decimal, Decimal]:
        """Verifica que el saldo calculado coincida con el PDF."""
        pass
    
    def aprobar_reconciliacion(
        self,
        report_id: str,
        notas: str | None = None,
    ) -> ReconciliationReport:
        """Marca una reconciliación como aprobada."""
        pass
    
    def resolver_huerfana(
        self,
        transaction_id: str,
        accion: str,  # cancelar | mantener | investigar
    ) -> Transaction:
        """Resuelve una transacción huérfana."""
        pass
```

**Tareas:**
- [ ] Crear ReconciliationService
- [ ] Implementar algoritmo de matching
- [ ] Implementar detección de duplicados
- [ ] Implementar verificación de saldo
- [ ] Tests con datos reales

---

### 🗓️ SEMANA 3: Integración y Detecciones

**Objetivo:** Conectar todo y agregar detecciones inteligentes

#### Día 1-2: Detección de Pagos de Tarjeta

```python
# src/finanzas_tracker/services/internal_transfer_detector.py

class InternalTransferDetector:
    """Detecta transferencias internas (pagos de tarjeta, etc)."""
    
    PATRONES_PAGO_TARJETA = [
        r"PAGO TARJETA",
        r"PAG\.?\s*T\.?C\.?",
        r"PAGO VISA",
        r"PAGO MASTERCARD",
        r"PAGO AMEX",
        r"PAGO A SU TARJETA",
    ]
    
    def es_pago_tarjeta(self, tx: Transaction) -> bool:
        """Detecta si la transacción es un pago de tarjeta."""
        pass
    
    def vincular_pago_con_tarjeta(
        self,
        tx: Transaction,
        tarjetas: list[Card],
    ) -> Card | None:
        """Encuentra la tarjeta correspondiente al pago."""
        pass
    
    def procesar_pago_tarjeta(
        self,
        tx: Transaction,
        profile_id: str,
    ) -> tuple[Transaction, Card]:
        """Procesa un pago de tarjeta actualizando saldos."""
        pass
```

**Tareas:**
- [ ] Crear InternalTransferDetector
- [ ] Detectar patrones de pago de tarjeta
- [ ] Actualizar saldos de cuenta y tarjeta
- [ ] Marcar como transferencia interna
- [ ] Tests

#### Día 3-4: Actualizar Servicios Existentes

**Modificar StatementEmailService:**
```python
# Agregar llamada a reconciliación cuando llega estado de cuenta

def process_statement(self, ...):
    # ... código existente ...
    
    # NUEVO: Si es estado de cuenta mensual, iniciar reconciliación
    if statement_type in ["credit_card", "bank_account"]:
        reconciliation_service = ReconciliationService()
        report = reconciliation_service.reconciliar_estado_cuenta(
            pdf_path=pdf_path,
            profile_id=profile_id,
            card_id=card_id,
            account_id=account_id,
        )
        
        if report.discrepancias_monto > 0 or report.transacciones_huerfanas > 0:
            # Generar alerta
            self._generar_alerta_reconciliacion(report)
```

**Modificar BankAccountStatementService:**
```python
# Agregar marcado de transacciones históricas

def _create_transaction(self, tx, profile_id, fecha_base):
    # ... código existente ...
    
    # NUEVO: Determinar si es histórica
    es_historica = tx.fecha < fecha_base
    
    transaction = Transaction(
        # ... campos existentes ...
        es_historica=es_historica,
        estado="pendiente" if not es_historica else "historica",
    )
```

**Tareas:**
- [ ] Actualizar StatementEmailService
- [ ] Actualizar BankAccountStatementService
- [ ] Actualizar CreditCardStatementService
- [ ] Tests de integración

#### Día 5: API Endpoints

```python
# src/finanzas_tracker/api/routers/reconciliation.py

router = APIRouter(prefix="/reconciliation", tags=["Reconciliación"])

@router.post("/run")
async def ejecutar_reconciliacion(
    pdf_id: str,
    profile_id: str = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> ReconciliationReportResponse:
    """Ejecuta reconciliación para un estado de cuenta."""
    pass

@router.get("/reports")
async def listar_reportes(
    profile_id: str = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> list[ReconciliationReportResponse]:
    """Lista todos los reportes de reconciliación."""
    pass

@router.get("/reports/{report_id}")
async def obtener_reporte(
    report_id: str,
    profile_id: str = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> ReconciliationReportResponse:
    """Obtiene detalles de un reporte de reconciliación."""
    pass

@router.post("/reports/{report_id}/approve")
async def aprobar_reconciliacion(
    report_id: str,
    notas: str | None = None,
    profile_id: str = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> ReconciliationReportResponse:
    """Aprueba una reconciliación."""
    pass

@router.post("/orphans/{transaction_id}/resolve")
async def resolver_huerfana(
    transaction_id: str,
    accion: str,  # cancelar | mantener
    profile_id: str = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> TransactionResponse:
    """Resuelve una transacción huérfana."""
    pass
```

**Tareas:**
- [ ] Crear router de reconciliación
- [ ] Crear router de patrimonio
- [ ] Registrar en main.py
- [ ] Documentar endpoints

---

### 🗓️ SEMANA 4: Onboarding y Polish

**Objetivo:** Implementar flujo de registro y pulir

#### Día 1-3: Flujo de Onboarding

```python
# src/finanzas_tracker/services/onboarding_service.py

@dataclass
class OnboardingResult:
    """Resultado del proceso de onboarding."""
    success: bool
    patrimonio_inicial: Decimal
    fecha_base: date
    cuentas_detectadas: list[Account]
    tarjetas_detectadas: list[Card]
    transacciones_historicas: int
    transacciones_recientes: int
    errores: list[str] | None = None


class OnboardingService:
    """Servicio para el proceso de registro de usuario."""
    
    def __init__(self) -> None:
        self.email_service = StatementEmailService()
        self.patrimonio_service = PatrimonioService()
        self.logger = get_logger(__name__)
    
    async def iniciar_onboarding(
        self,
        profile_id: str,
        email_outlook: str,
    ) -> OnboardingResult:
        """
        Ejecuta el proceso completo de onboarding.
        
        1. Busca estados de cuenta recientes
        2. Determina FECHA_BASE
        3. Extrae saldos y cuentas/tarjetas
        4. Importa historial
        5. Importa transacciones recientes
        """
        pass
    
    def _buscar_estado_cuenta_reciente(
        self,
        profile_id: str,
    ) -> tuple[str, date] | None:
        """Busca el estado de cuenta más reciente (últimos 45 días)."""
        pass
    
    def _detectar_cuentas_y_tarjetas(
        self,
        pdf_path: str,
    ) -> tuple[list[Account], list[Card]]:
        """Detecta cuentas y tarjetas del PDF."""
        pass
    
    def _importar_transacciones_historicas(
        self,
        profile_id: str,
        fecha_base: date,
        dias_atras: int = 60,
    ) -> int:
        """Importa transacciones históricas (no afectan patrimonio)."""
        pass
    
    def _importar_transacciones_recientes(
        self,
        profile_id: str,
        desde: date,
    ) -> int:
        """Importa transacciones desde fecha_base hasta hoy."""
        pass
```

**Tareas:**
- [ ] Crear OnboardingService
- [ ] Implementar búsqueda de estado de cuenta reciente
- [ ] Implementar detección de cuentas/tarjetas
- [ ] Implementar importación con fecha_base
- [ ] Endpoint POST /onboarding/start
- [ ] Tests

#### Día 4-5: Testing y Documentación

**Tareas:**
- [ ] Tests de integración end-to-end
- [ ] Correr todos los tests existentes
- [ ] Documentar APIs (OpenAPI)
- [ ] Actualizar README
- [ ] Code review y refactoring

---

### 🗓️ SEMANA 5: Extras y Estabilización

**Objetivo:** Implementar detecciones adicionales y estabilizar

#### Día 1-2: Detección de Suscripciones

```python
# src/finanzas_tracker/services/subscription_detector.py

@dataclass
class DetectedSubscription:
    """Suscripción detectada automáticamente."""
    comercio: str
    monto_promedio: Decimal
    frecuencia: str  # mensual | anual
    ultimo_cobro: date
    confianza: int  # 0-100


class SubscriptionDetector:
    """Detecta suscripciones/pagos recurrentes."""
    
    def detectar_suscripciones(
        self,
        transacciones: list[Transaction],
    ) -> list[DetectedSubscription]:
        """
        Analiza transacciones para detectar patrones recurrentes.
        
        Criterios:
        - Mismo comercio
        - Monto similar (±5%)
        - Frecuencia regular (mensual/anual)
        - Al menos 2 ocurrencias
        """
        pass
```

**Tareas:**
- [ ] Crear SubscriptionDetector
- [ ] Modelo Subscription
- [ ] Endpoint GET /subscriptions/detected
- [ ] Tests

#### Día 3: Alertas y Notificaciones

```python
# src/finanzas_tracker/services/alert_service.py

class AlertType(str, Enum):
    DUPLICADO_SOSPECHOSO = "duplicado_sospechoso"
    DISCREPANCIA_MONTO = "discrepancia_monto"
    TRANSACCION_HUERFANA = "transaccion_huerfana"
    RECONCILIACION_PENDIENTE = "reconciliacion_pendiente"
    PAGO_TARJETA_PROXIMO = "pago_tarjeta_proximo"


@dataclass
class Alert:
    id: str
    tipo: AlertType
    titulo: str
    mensaje: str
    prioridad: str  # alta | media | baja
    transaction_id: str | None
    report_id: str | None
    acciones: list[str]  # botones de acción
    fecha: datetime
    leida: bool = False


class AlertService:
    """Servicio para generar y gestionar alertas."""
    
    def generar_alerta(
        self,
        profile_id: str,
        tipo: AlertType,
        datos: dict,
    ) -> Alert:
        pass
    
    def obtener_alertas_pendientes(
        self,
        profile_id: str,
    ) -> list[Alert]:
        pass
    
    def marcar_como_leida(
        self,
        alert_id: str,
    ) -> None:
        pass
```

**Tareas:**
- [ ] Crear AlertService
- [ ] Modelo Alert en BD
- [ ] Endpoint GET /alerts
- [ ] Integrar con reconciliación

#### Día 4-5: Estabilización Final

**Tareas:**
- [ ] Correr suite completa de tests
- [ ] Fix bugs encontrados
- [ ] Performance testing
- [ ] Documentación final
- [ ] Preparar para deploy

---

## 📦 Entregables por Semana

| Semana | Entregable Principal | Archivos Nuevos |
|--------|---------------------|-----------------|
| 1 | Modelos actualizados + Migraciones | `enums.py`, migración, modelos |
| 2 | PatrimonioService + ReconciliationService | 2 servicios nuevos |
| 3 | Detecciones + API endpoints | detector, routers |
| 4 | OnboardingService completo | onboarding_service.py |
| 5 | Suscripciones + Alertas | 2 servicios + estabilización |

---

## 🧪 Criterios de Aceptación

### Semana 1
- [ ] Migración corre sin errores
- [ ] Tests existentes siguen pasando
- [ ] Nuevos modelos tienen tests

### Semana 2
- [ ] Patrimonio se calcula correctamente
- [ ] Reconciliación detecta matches con 80%+ precisión
- [ ] Tests de servicios pasan

### Semana 3
- [ ] Pagos de tarjeta se detectan automáticamente
- [ ] APIs responden correctamente
- [ ] Tests de integración pasan

### Semana 4
- [ ] Onboarding funciona end-to-end
- [ ] Usuario puede registrarse y ver patrimonio
- [ ] Importación histórica funciona

### Semana 5
- [ ] Suscripciones se detectan
- [ ] Alertas se generan correctamente
- [ ] Sistema estable para demo

---

## 🚀 Comando para Empezar

```bash
# Semana 1, Día 1:
cd /Users/sebastiancruz/Desktop/finanzas-email-tracker

# 1. Crear branch
git checkout -b feature/flujo-completo

# 2. Actualizar modelo Transaction
# (editar src/finanzas_tracker/models/transaction.py)

# 3. Crear migración
poetry run alembic revision --autogenerate -m "add_transaction_status_fields"

# 4. Aplicar migración
poetry run alembic upgrade head

# 5. Correr tests
poetry run pytest tests/ -v
```

---

## 📝 Notas Adicionales

1. **Mantener backward compatibility:** Los cambios no deben romper funcionalidad existente
2. **Tests primero:** Escribir tests antes de implementar cuando sea posible
3. **Commits pequeños:** Un commit por feature/fix
4. **Documentar:** Docstrings en todas las funciones nuevas

---

*Plan creado: 3 Diciembre 2025*  
*Próxima revisión: Fin de Semana 1*
