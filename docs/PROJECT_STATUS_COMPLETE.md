# 📊 Finanzas Tracker CR - Estado Actual y Visión Futura

**Fecha:** 1 de Diciembre, 2025  
**Versión:** 0.1.0  
**Estado:** ~60% funcional, en desarrollo activo  
**Autor:** Sebastián Cruz (Ingeniería en Computación, recién graduado)

---

## 📑 Tabla de Contenidos

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Estado Actual - Lo Que Tenemos](#estado-actual)
3. [Arquitectura Técnica](#arquitectura-técnica)
4. [Modelos de Datos](#modelos-de-datos)
5. [Servicios y Lógica de Negocio](#servicios)
6. [API REST](#api-rest)
7. [Interfaces de Usuario](#interfaces-usuario)
8. [Tests y Calidad](#tests)
9. [Lo Que Falta - Gaps Actuales](#gaps)
10. [Visión Futura - Patrimonio-First](#vision-futura)
11. [Plan de Implementación](#plan-implementacion)
12. [Próximos Pasos Inmediatos](#proximos-pasos)

---

<a name="resumen-ejecutivo"></a>
## 1. 🎯 Resumen Ejecutivo

### ¿Qué es Finanzas Tracker CR?

**Primera aplicación de finanzas personales diseñada específicamente para Costa Rica** que:
- ✅ Lee automáticamente correos de BAC Credomatic y Banco Popular
- ✅ Parsea estados de cuenta PDF
- ✅ Categoriza gastos con AI (Claude)
- ✅ Implementa presupuesto 50/30/20
- ✅ Tiene chat inteligente con RAG (búsqueda semántica)
- ✅ Expone MCP Server para Claude Desktop

### Stack Tecnológico

| Capa | Tecnología |
|------|------------|
| **Backend** | Python 3.11+, FastAPI |
| **ORM** | SQLAlchemy 2.0 (async-ready) |
| **Base de Datos** | PostgreSQL 16 + pgvector |
| **AI** | Claude AI (Anthropic), sentence-transformers |
| **Dashboard** | Streamlit |
| **Auth** | MSAL (Microsoft Graph API) |
| **Tests** | pytest (419 tests) |
| **MCP** | FastMCP para Claude Desktop |

### Métricas Actuales

```
📁 Estructura de Código
├── src/finanzas_tracker/   ~50 archivos Python
├── tests/                   419 tests (32% coverage)
├── alembic/                 4 migraciones
└── docs/                    ~15 documentos

🎯 Funcionalidades
├── Parsing emails BAC:      100% éxito (157 emails probados)
├── Parsing emails Popular:  ~90% (menos probado)
├── Categorización AI:       Funcionando
├── Búsqueda semántica:      Funcionando (pgvector)
├── MCP Server:              10 tools, 4 resources, 4 prompts
└── Dashboard:               8 páginas Streamlit
```

---

<a name="estado-actual"></a>
## 2. 📦 Estado Actual - Lo Que Tenemos

### 2.1 Estructura del Proyecto

```
finanzas-email-tracker/
├── src/finanzas_tracker/
│   ├── api/                 # FastAPI REST API
│   │   ├── routers/         # 5 routers (transactions, categories, etc.)
│   │   ├── schemas/         # Pydantic schemas para API
│   │   ├── dependencies.py  # Inyección de dependencias
│   │   ├── errors.py        # Manejo global de errores
│   │   ├── middleware.py    # Correlation ID, logging
│   │   └── main.py          # App FastAPI principal
│   │
│   ├── core/                # Configuración central
│   │   ├── cache.py         # Sistema de caché simple
│   │   ├── constants.py     # Constantes globales
│   │   ├── database.py      # Conexión PostgreSQL + get_session()
│   │   ├── logging.py       # Loguru configurado
│   │   └── retry.py         # Decoradores de retry
│   │
│   ├── config/
│   │   └── settings.py      # Pydantic Settings (env vars)
│   │
│   ├── models/              # SQLAlchemy 2.0 Models
│   │   ├── base.py          # Mixins (Timestamp, SoftDelete, Tenant)
│   │   ├── budget.py        # Presupuestos por categoría/mes
│   │   ├── card.py          # Tarjetas (débito/crédito)
│   │   ├── category.py      # Categorías + Subcategorías
│   │   ├── embedding.py     # Embeddings para RAG
│   │   ├── enums.py         # Enums centralizados
│   │   ├── exchange_rate_cache.py
│   │   ├── income.py        # Ingresos (salario, etc.)
│   │   ├── merchant.py      # Comercios normalizados
│   │   ├── profile.py       # Perfiles (multi-usuario)
│   │   └── transaction.py   # Transacciones (modelo principal)
│   │
│   ├── parsers/             # Parsers de emails/PDFs
│   │   ├── base_parser.py   # Template Method Pattern
│   │   ├── bac_parser.py    # Parser BAC emails (668 líneas)
│   │   ├── bac_pdf_parser.py # Parser estados de cuenta PDF
│   │   └── popular_parser.py # Parser Banco Popular
│   │
│   ├── services/            # Lógica de negocio
│   │   ├── auth_manager.py           # OAuth2 Microsoft
│   │   ├── categorizer.py            # Categorización con AI
│   │   ├── duplicate_detector.py     # Detección de duplicados
│   │   ├── email_fetcher.py          # Microsoft Graph API
│   │   ├── embedding_service.py      # Generación embeddings
│   │   ├── embedding_events.py       # Auto-embeddings async
│   │   ├── exchange_rate.py          # Tipo de cambio BCCR
│   │   ├── finance_chat.py           # Chat con contexto
│   │   ├── insights.py               # Análisis automático
│   │   ├── merchant_service.py       # Normalización comercios
│   │   ├── rag_service.py            # RAG con Claude
│   │   └── transaction_processor.py  # Procesamiento central
│   │
│   ├── mcp/                 # MCP Server para Claude Desktop
│   │   ├── __main__.py      # Entry point
│   │   └── server.py        # 10 tools, 4 resources, 4 prompts
│   │
│   ├── dashboard/           # Streamlit UI
│   │   ├── app.py           # Página principal
│   │   ├── pages/           # 8 páginas
│   │   │   ├── 01_setup.py
│   │   │   ├── 02_ingresos.py
│   │   │   ├── 03_balance.py
│   │   │   ├── 04_transacciones.py
│   │   │   ├── 05_desglose.py
│   │   │   ├── 06_merchants.py
│   │   │   ├── 07_chat.py
│   │   │   └── 08_insights.py
│   │   ├── components/      # Componentes reutilizables
│   │   ├── helpers.py
│   │   ├── queries.py
│   │   └── styles.py
│   │
│   ├── repositories/        # (Parcialmente implementado)
│   └── utils/
│       └── parser_utils.py  # Utilidades de parsing
│
├── tests/
│   ├── unit/                # Tests unitarios
│   ├── integration/         # Tests de integración
│   ├── api/                 # Tests de API
│   ├── mcp/                 # Tests del MCP Server
│   └── conftest.py          # Fixtures globales
│
├── alembic/                 # Migraciones de BD
│   └── versions/            # 4 migraciones
│
├── scripts/                 # Scripts de utilidad
├── data/                    # Datos de prueba
└── docs/                    # Documentación
```

### 2.2 Modelos de Datos Existentes

#### Profile (Perfil de Usuario)
```python
class Profile:
    id: str (UUID)
    tenant_id: UUID | None          # Multi-tenancy futuro
    email_outlook: str              # Email para buscar correos
    nombre: str                     # "Personal", "Negocio", "Mamá"
    descripcion: str | None
    icono: str | None               # Emoji
    es_activo: bool
    
    # Relaciones
    cards: list[Card]
    budgets: list[Budget]
    transactions: list[Transaction]
    incomes: list[Income]
```

#### Transaction (Transacción)
```python
class Transaction:
    id: str (UUID)
    email_id: str                   # Para evitar duplicados
    profile_id: str                 # FK a Profile
    
    # Información de la transacción
    banco: BankName                 # bac, popular
    card_id: str | None             # FK a Card
    comercio: str                   # "STARBUCKS", "UBER"
    tipo_transaccion: TransactionType  # compra, transferencia, etc.
    
    # Montos
    monto_original: Decimal         # En moneda original
    moneda_original: Currency       # CRC, USD
    monto_crc: Decimal             # Convertido a colones
    tipo_cambio_usado: Decimal | None
    
    # Fecha y ubicación
    fecha_transaccion: datetime
    ciudad: str | None
    pais: str | None
    
    # Categorización
    subcategory_id: str | None      # FK a Subcategory
    categoria_sugerida_por_ia: str | None
    necesita_revision: bool
    confianza_categoria: int        # 0-100
    
    # Casos especiales
    tipo_especial: str | None       # dinero_ajeno, intermediaria
    excluir_de_presupuesto: bool
    relacionada_con: str | None
    es_desconocida: bool
    es_comercio_ambiguo: bool       # Walmart, Amazon, etc.
    
    # Anomaly Detection
    is_anomaly: bool
    anomaly_score: Decimal | None
    anomaly_reason: str | None
    
    # Soft delete + timestamps
    deleted_at, created_at, updated_at
```

#### Card (Tarjeta)
```python
class Card:
    id: str (UUID)
    profile_id: str
    
    ultimos_4_digitos: str          # "3640"
    tipo: CardType                  # debito, credito
    banco: BankName
    marca: str | None               # visa, mastercard
    
    # Solo para crédito
    limite_credito: Decimal | None
    fecha_corte: int | None         # Día del mes (1-31)
    fecha_vencimiento: int | None   # Día de pago
    current_balance: Decimal | None
    interest_rate_annual: Decimal | None
    minimum_payment_percentage: Decimal | None
    
    alias: str | None               # Nombre personalizado
    activa: bool
```

#### Income (Ingreso)
```python
class Income:
    id: str (UUID)
    profile_id: str
    
    tipo: IncomeType                # salario, freelance, venta
    descripcion: str
    monto_original: Decimal
    moneda_original: Currency
    monto_crc: Decimal
    fecha: date
    
    # Recurrencia
    es_recurrente: bool
    frecuencia: RecurrenceFrequency | None
    proximo_ingreso_esperado: date | None
    
    # Casos especiales
    tipo_especial: str | None       # dinero_ajeno, ajuste_inicial
    excluir_de_balance: bool
```

#### Category + Subcategory (50/30/20)
```python
class Category:
    tipo: CategoryType              # necesidades, gustos, ahorros
    nombre: str
    icono: str
    subcategories: list[Subcategory]

class Subcategory:
    category_id: str
    nombre: str                     # "Transporte", "Comida fuera"
    keywords: str | None            # Para auto-categorización
```

#### Budget (Presupuesto)
```python
class Budget:
    profile_id: str
    category_id: str                # FK a Subcategory
    mes: date                       # Primer día del mes
    amount_crc: Decimal            # Límite de gasto
```

### 2.3 Servicios Implementados

#### EmailFetcher
```python
# Conecta con Microsoft Graph API vía OAuth2
# Busca correos de BAC y Banco Popular
# Filtra marketing vs transacciones

fetcher = EmailFetcher()
emails = fetcher.fetch_bac_emails(days_back=30)
# Retorna: List[dict] con id, subject, body, receivedDateTime
```

#### BACParser / PopularParser
```python
# Template Method Pattern
# Parsea diferentes formatos de correos

parser = BACParser()
result = parser.parse(email_data)
# Retorna: ParsedTransaction | None
# {
#     "email_id": "...",
#     "banco": "bac",
#     "comercio": "STARBUCKS",
#     "monto_original": 5000.00,
#     "moneda_original": "CRC",
#     ...
# }
```

**Tipos de correos soportados (BAC):**
- ✅ Compras con tarjeta (formato estándar)
- ✅ Retiros sin tarjeta
- ✅ Transferencias enviadas
- ✅ Transferencias SINPE recibidas
- ✅ Pagos de tarjeta de crédito
- ❌ Pre-autorizaciones (ignoradas, monto $0)
- ❌ Marketing/promociones (filtradas)
- ❌ Configuración (afiliación SINPE, etc., filtradas)

#### TransactionCategorizer
```python
# Categorización en 3 niveles:
# 1. Aprendizaje del historial del usuario
# 2. Keywords de subcategorías
# 3. Claude AI para casos ambiguos

categorizer = TransactionCategorizer()
result = categorizer.categorize(
    comercio="WALMART",
    monto_crc=50000,
    tipo_transaccion="compra",
    profile_id="..."
)
# {
#     "subcategory_id": "...",
#     "categoria_sugerida": "Supermercado",
#     "necesita_revision": True,  # Es ambiguo
#     "confianza": 75,
#     "alternativas": ["Electrodomésticos", "Ropa"]
# }
```

#### RAGService (Chat Inteligente)
```python
# Combina búsqueda semántica (pgvector) + Claude AI

rag = RAGService(db)
response = rag.chat(
    query="¿Cuánto gasté en comida este mes?",
    profile_id="..."
)
# {
#     "answer": "Este mes gastaste ₡85,000 en comida...",
#     "sources": [...],  # Transacciones usadas como contexto
#     "model": "claude-3-haiku-...",
#     "usage": {"input_tokens": 500, "output_tokens": 200}
# }
```

#### InsightsService
```python
# Genera análisis automáticos:
# - Tendencias de gasto
# - Transacciones inusuales
# - Patrones de comportamiento
# - Recomendaciones AI

service = InsightsService()
insights = service.generate_insights(profile_id)
# [
#     Insight(
#         type=InsightType.SPENDING_INCREASE,
#         title="Gasto aumentado",
#         description="Has gastado 30% más que el mes pasado",
#         impact="negative",
#         recommendation="..."
#     ),
#     ...
# ]
```

### 2.4 API REST (FastAPI)

**Base URL:** `http://localhost:8000/api/v1`

#### Endpoints Disponibles

```yaml
# Transactions
GET    /transactions                    # Listar transacciones
GET    /transactions/{id}               # Obtener una
POST   /transactions                    # Crear
PUT    /transactions/{id}               # Actualizar
DELETE /transactions/{id}               # Soft delete
GET    /transactions/search             # Búsqueda con filtros
POST   /transactions/ambiguous/{id}/confirm  # Confirmar categoría

# Categories
GET    /categories                      # Listar categorías
GET    /categories/{id}/subcategories   # Subcategorías

# Budgets
GET    /budgets                         # Listar presupuestos
POST   /budgets                         # Crear
PUT    /budgets/{id}                    # Actualizar

# Profiles
GET    /profiles                        # Listar perfiles
GET    /profiles/{id}                   # Obtener uno
POST   /profiles                        # Crear
PUT    /profiles/{id}                   # Actualizar

# AI & RAG
GET    /ai/health                       # Estado del sistema AI
POST   /ai/chat                         # Chat con contexto
POST   /ai/search                       # Búsqueda semántica
POST   /ai/embeddings/generate          # Generar embeddings
GET    /ai/embeddings/stats             # Estadísticas
POST   /ai/analyze                      # Análisis con AI
```

**Headers requeridos:**
```
X-Profile-Id: {uuid}  # Perfil activo
Content-Type: application/json
```

### 2.5 MCP Server

**10 Herramientas en 3 niveles:**

```python
# ⚙️ Configuración
set_profile(profile_id)              # Establecer perfil activo
list_profiles()                      # Ver perfiles disponibles

# 📋 Nivel 1 - Consultas
get_transactions(days, category, min_amount)
get_spending_summary(period, group_by)
get_top_merchants(days, limit)

# 📊 Nivel 2 - Análisis
search_transactions(query)           # Búsqueda semántica
get_monthly_comparison()             # Mes actual vs anterior

# 🎯 Nivel 3 - Coaching (Diferenciador)
budget_coaching()                    # Score de salud financiera
savings_opportunities()              # Dónde ahorrar
cashflow_prediction()                # Predicción de flujo
spending_alert()                     # Alertas de patrones
goal_advisor(goal_amount, months, name)  # Planificación de metas
```

**4 Resources (Contexto automático):**
- `profile://current` - Info del perfil activo
- `finance://summary` - Resumen del mes
- `categories://list` - Categorías disponibles
- (más por agregar)

**4 Prompts (Plantillas):**
- `weekly_review` - Revisión semanal
- `savings_plan` - Plan de ahorro
- `monthly_checkup` - Chequeo mensual
- `quick_question` - Preguntas rápidas

### 2.6 Dashboard Streamlit

**8 páginas:**

| Página | Función |
|--------|---------|
| `app.py` (Home) | Dashboard principal, métricas del mes |
| `01_setup.py` | Configuración de perfil y conexión email |
| `02_ingresos.py` | Gestión de ingresos |
| `03_balance.py` | Balance mensual, 50/30/20 |
| `04_transacciones.py` | Lista de transacciones |
| `05_desglose.py` | Desglose por categoría |
| `06_merchants.py` | Gestión de comercios |
| `07_chat.py` | Chat con AI |
| `08_insights.py` | Análisis automático |

---

<a name="tests"></a>
## 3. 🧪 Tests y Calidad

### Estadísticas

```
Total tests: 419
Coverage: 32% (líneas ejecutadas)
Tiempo ejecución: ~44 segundos

Por módulo:
├── tests/unit/           ~300 tests
├── tests/integration/    ~50 tests
├── tests/api/            ~40 tests
└── tests/mcp/            ~30 tests
```

### Áreas Bien Cubiertas
- ✅ Parsers (BAC, Popular)
- ✅ Modelos (validaciones)
- ✅ MCP Server (todas las tools)
- ✅ API endpoints básicos

### Áreas con Gaps
- ⚠️ Services (embedding, RAG)
- ⚠️ Dashboard (sin tests)
- ⚠️ Flujos end-to-end

---

<a name="gaps"></a>
## 4. 🕳️ Lo Que Falta - Gaps Actuales

### 4.1 Gaps Funcionales Críticos

| Gap | Impacto | Dificultad |
|-----|---------|------------|
| **No hay concepto de "Patrimonio"** | No se puede ver cuánto dinero tiene el usuario | 🔴 Alto |
| **No hay cuentas bancarias** | No se sabe de dónde sale el dinero | 🔴 Alto |
| **No hay inversiones** | CDPs, ahorros a plazo no se trackean | 🔴 Alto |
| **Tarjetas crédito incompleto** | No hay ciclos de facturación, pagos | 🟡 Medio |
| **No hay metas** | No se pueden poner objetivos de ahorro | 🟡 Medio |
| **PDF reconciliación** | No compara email vs estado de cuenta | 🟡 Medio |
| **No hay deudas/préstamos** | No se trackean préstamos | 🟢 Bajo |

### 4.2 Gaps Técnicos

| Gap | Descripción |
|-----|-------------|
| **Sin autenticación real** | Solo header X-Profile-Id |
| **Sin frontend moderno** | Solo Streamlit (limitado) |
| **Sin mobile** | No hay app móvil |
| **Sin notificaciones** | No hay push/email alerts |
| **Sin sync real-time** | Hay que correr fetch manual |

### 4.3 Lo Que el Usuario Quiere pero No Puede Hacer

❌ "Quiero ver cuánto dinero tengo en total"
❌ "Quiero registrar mi CDP de ₡4M al 3.73%"
❌ "Quiero saber cuánto me falta para el mundial 2026"
❌ "Quiero ver mis pagos de tarjeta vs el estado de cuenta"
❌ "Quiero que me avise cuando se acerca el pago de la tarjeta"
❌ "Quiero saber si me conviene pagar de contado o a cuotas"

---

<a name="vision-futura"></a>
## 5. 🚀 Visión Futura - Patrimonio-First

### 5.1 Cambio de Paradigma

**Actual (Transaction-First):**
```
Correos → Transacciones → ??? (el usuario no ve el panorama completo)
```

**Propuesto (Patrimonio-First):**
```
1. Setup: ¿Cuál es tu situación financiera HOY?
   └── Cuentas, inversiones, tarjetas, metas

2. Tracking: Correos + PDFs actualizan automáticamente

3. Dashboard: "Tu patrimonio es ₡X (+₡Y este mes)"
```

### 5.2 Nuevos Modelos Propuestos

#### Account (Cuenta Bancaria)
```python
class Account:
    """Cuenta bancaria (corriente, ahorro, etc.)"""
    id: str
    profile_id: str
    
    banco: BankName
    tipo_cuenta: AccountType        # corriente, ahorro, planilla
    numero_cuenta: str | None       # Últimos 4 dígitos
    nombre: str                     # "Cuenta Planilla BAC"
    
    saldo_actual: Decimal           # Saldo al momento
    saldo_fecha: datetime           # Cuándo se actualizó
    
    # Para cuentas de ahorro
    tasa_interes: Decimal | None    # Si aplica
    
    activa: bool
```

#### Investment (Inversión)
```python
class Investment:
    """CDP, ahorro a plazo, fondos de inversión, etc."""
    id: str
    profile_id: str
    
    tipo: InvestmentType            # cdp, ahorro_plazo, fondo
    institucion: str                # "MultiMoney", "BAC"
    nombre: str                     # "CDP Nov 2025"
    
    monto_principal: Decimal        # Lo que se invirtió
    moneda: Currency
    
    tasa_interes_bruta: Decimal     # Ej: 3.73%
    tasa_interes_neta: Decimal | None  # Después de impuestos
    
    fecha_inicio: date
    fecha_vencimiento: date | None  # Si es a plazo
    
    # Rendimientos
    rendimiento_acumulado: Decimal  # Intereses ganados
    ultimo_calculo: datetime
    
    # Estado
    estado: InvestmentStatus        # activa, vencida, cancelada
```

#### Goal (Meta Financiera)
```python
class Goal:
    """Meta de ahorro o financiera."""
    id: str
    profile_id: str
    
    nombre: str                     # "Mundial 2026"
    descripcion: str | None
    icono: str | None
    
    monto_objetivo: Decimal         # ₡5,000,000
    monto_actual: Decimal           # ₡2,000,000
    moneda: Currency
    
    fecha_objetivo: date | None     # Junio 2026
    
    # Vinculación con cuenta de ahorro específica (opcional)
    account_id: str | None
    
    # Tracking
    es_activa: bool
    prioridad: int                  # 1 = más importante
```

#### Debt (Deuda/Préstamo)
```python
class Debt:
    """Préstamo, deuda, financiamiento."""
    id: str
    profile_id: str
    
    tipo: DebtType                  # prestamo_personal, hipoteca, etc.
    acreedor: str                   # "BAC", "Familiar"
    descripcion: str
    
    monto_original: Decimal
    saldo_pendiente: Decimal
    tasa_interes: Decimal | None
    
    cuota_mensual: Decimal | None
    fecha_inicio: date
    fecha_fin_estimada: date | None
    
    estado: DebtStatus              # activa, pagada
```

#### BillingCycle (Período de Facturación)
```python
class BillingCycle:
    """Período de facturación de tarjeta de crédito."""
    id: str
    card_id: str
    
    fecha_inicio: date              # Día después del corte anterior
    fecha_corte: date               # Fecha de cierre
    fecha_vencimiento: date         # Fecha límite de pago
    
    # Montos
    saldo_anterior: Decimal
    total_cargos: Decimal
    total_abonos: Decimal
    total_periodo: Decimal          # Lo que se debe
    pago_minimo: Decimal
    
    # Estado
    status: CycleStatus             # open, closed, paid, partial
    monto_pagado: Decimal
    fecha_pago: datetime | None
    
    # PDF
    pdf_imported: bool
    pdf_path: str | None
```

### 5.3 Nueva Vista de Patrimonio

```
📊 Patrimonio de Sebastián - 1 Dic 2025
═══════════════════════════════════════

💰 ACTIVOS LÍQUIDOS                     ₡10,500,000
├── Cuenta Planilla BAC                  ₡   350,000
├── Cuenta Corriente BAC                 ₡   150,000
├── MultiMoney (6% → 5.5% en Ene)        ₡ 6,000,000
└── CDP BAC (3.73%)                      ₡ 4,000,000

💳 PASIVOS (Deudas)                     -₡   127,000
├── BAC Visa (corte 17, pago 2)          ₡    85,000
└── BAC MC (corte 17, pago 2)            ₡    42,000

═══════════════════════════════════════
💎 PATRIMONIO NETO                      ₡10,373,000
   ↑ +₡XXX desde Nov 1
═══════════════════════════════════════

📈 INGRESOS ESPERADOS (Dic)
├── Quincena 1                          +₡   XXX,XXX
├── Quincena 2                          +₡   XXX,XXX
├── Intereses MultiMoney                +₡    30,000
└── Intereses CDP                       +₡    12,400

📉 GASTOS COMPROMETIDOS
├── Pago tarjetas (2 dic)               -₡   127,000
├── Marchamo (si aplica)                -₡   350,000
└── Gastos proyectados                  -₡   XXX,XXX

🎯 METAS
├── ⚽ Mundial 2026     ████████░░  80%  ₡4M/₡5M
├── 🚗 Marchamo 2026    ██░░░░░░░░  20%  ₡70K/₡350K
└── 💰 Fondo Emergencia ███░░░░░░░  33%  ₡500K/₡1.5M
```

### 5.4 Opciones de Input (Respuesta a Julián)

```
¿Cómo quieres trackear tus finanzas?

🔗 Conectar email (recomendado)
   → Automático, lee correos de BAC/Popular
   
📄 Subir estados de cuenta PDF
   → Semi-automático, subes el PDF mensual
   
📸 Foto a la factura
   → OCR lee el monto y comercio
   
✍️ Ingreso manual
   → Tú pones cada transacción
```

### 5.5 Funcionalidades AI Propuestas

```python
# 1. Predicciones
def predict_next_month_spending():
    """Basado en historial, ¿cuánto gastarás?"""
    pass

# 2. Simulaciones
def simulate_scenario(extra_income=0, reduced_spending=0):
    """Si gano X más o gasto Y menos, ¿cuándo llego a mi meta?"""
    pass

# 3. Alertas Inteligentes
def check_alerts():
    """
    - Fecha de pago próxima
    - Gasto inusual detectado
    - Meta en riesgo
    - Oportunidad de ahorro
    """
    pass

# 4. Optimización
def should_pay_cash_or_installments(amount, months, card_rate):
    """¿Conviene pagar de contado o a cuotas?"""
    # Considera: costo de oportunidad, comisiones, intereses
    pass

# 5. Coaching Financiero
def get_financial_advice():
    """
    Claude analiza tu situación y da consejos:
    - "Tienes ₡6M en MultiMoney al 6%, pero tu CDP solo da 3.73%..."
    - "Gastaste 40% en gustos, tu meta es 30%..."
    """
    pass
```

---

<a name="plan-implementacion"></a>
## 6. 📋 Plan de Implementación

### Fase 1: Fundamentos de Patrimonio (2-3 semanas)

```
Semana 1:
├── [ ] Crear modelo Account
├── [ ] Crear modelo Investment
├── [ ] Crear modelo Goal
├── [ ] Crear modelo Debt
├── [ ] Crear migraciones Alembic
└── [ ] Tests unitarios para nuevos modelos

Semana 2:
├── [ ] Crear AccountService
├── [ ] Crear InvestmentService (calcular intereses)
├── [ ] Crear GoalService (tracking de progreso)
├── [ ] Crear PatrimonyService (consolidar todo)
└── [ ] Tests de servicios

Semana 3:
├── [ ] API endpoints para Account, Investment, Goal
├── [ ] Streamlit: Página de Setup Inicial
├── [ ] Streamlit: Dashboard de Patrimonio
└── [ ] Tests API
```

### Fase 2: Tarjetas de Crédito Completo (2 semanas)

```
Semana 4:
├── [ ] Crear modelo BillingCycle
├── [ ] Crear modelo CardPayment
├── [ ] Crear modelo StatementTransaction
├── [ ] Actualizar Card con nuevos campos
├── [ ] Migraciones
└── [ ] Tests

Semana 5:
├── [ ] Crear CreditCardService
├── [ ] Lógica de detección de pagos
├── [ ] Lógica de reconciliación PDF vs emails
├── [ ] Alertas de fechas de pago
└── [ ] Tests
```

### Fase 3: Metas y Proyecciones (1-2 semanas)

```
Semana 6:
├── [ ] UI para crear/editar metas
├── [ ] Visualización de progreso
├── [ ] Proyección: "¿cuándo llegaré a mi meta?"
├── [ ] Alertas: "Meta en riesgo"
└── [ ] Integración con MCP Server
```

### Fase 4: AI Avanzado (2 semanas)

```
Semana 7-8:
├── [ ] Predicciones de gasto mensual
├── [ ] Simulador de escenarios
├── [ ] Calculadora contado vs cuotas
├── [ ] Coaching financiero con Claude
├── [ ] Insights mejorados
└── [ ] Tests
```

### Fase 5: Pulido y Producción (2 semanas)

```
Semana 9-10:
├── [ ] Autenticación real (OAuth2)
├── [ ] Deploy a producción
├── [ ] Documentación de usuario
├── [ ] Video demo
├── [ ] README pulido para GitHub
└── [ ] Preparar para compartir
```

---

<a name="proximos-pasos"></a>
## 7. 🎯 Próximos Pasos Inmediatos

### Esta Semana (1-7 Dic 2025)

1. **Modelo Account** - Para trackear cuentas bancarias
2. **Modelo Investment** - Para tu MultiMoney y CDP
3. **Modelo Goal** - Para el Mundial 2026 y marchamo
4. **Setup Inicial** - UI para que ingreses tu situación actual
5. **Vista de Patrimonio** - Dashboard consolidado

### Decisiones Pendientes

1. ¿Queremos frontend moderno (React/Next.js) o seguimos con Streamlit?
2. ¿Hosting? Vercel + Supabase? Railway? Self-hosted?
3. ¿Móvil nativo o PWA?
4. ¿Open source desde el inicio o después?

---

## 📞 Contacto

- **Desarrollador:** Sebastián Cruz
- **Repo:** sebascrugu/finanzas-email-tracker
- **Branch:** clean-architecture

---

*"La claridad financiera no es restricción, es libertad."*
