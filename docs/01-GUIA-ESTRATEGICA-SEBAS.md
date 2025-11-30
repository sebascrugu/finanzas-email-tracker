# Guía Estratégica: Finanzas Tracker Costa Rica
## De Proyecto Personal a Producto Comercial

**Versión:** 1.0  
**Fecha:** Noviembre 2025  
**Para:** Sebas - Software Engineer  
**Objetivo:** Transformar el proyecto existente (50-60% completo) en un producto production-ready con diferenciadores únicos para el mercado costarricense

---

## Resumen Ejecutivo

### La Oportunidad
Costa Rica tiene **4.2 millones de usuarios potenciales** con 76% de adopción de SINPE Móvil, pero **ninguna app de finanzas personales local**. Las apps existentes (YNAB, Monarch, Lunch Money) no soportan colones, bancos ticos, ni SINPE.

### Tu Diferenciador Real
No es solo "otra app de finanzas con AI". Es:
1. **Primera app de finanzas personales para Costa Rica** con parsing de SINPE Móvil
2. **MCP Server inteligente** que va más allá de CRUD (coaching financiero, predicciones)
3. **Privacy-first, self-hosted** para mercado que desconfía de apps gringas con sus datos

### Qué Cambia vs. Tu Plan Original
| Aspecto | Plan Original | Nuevo Plan | Por Qué |
|---------|--------------|------------|---------|
| Vector DB | ChromaDB separado | pgvector en PostgreSQL | Una sola DB, ACID, más simple |
| Multi-tenancy | No considerado | tenant_id desde día 1 | Habilita SaaS sin reescribir |
| MCP Server | CRUD básico | Coaching + Predicciones | Actual Budget ya tiene CRUD |
| Test Coverage | 80% general | 80% en lógica financiera | Foco donde importa |
| Frontend | Migrar a React | Mantener Streamlit | Suficiente para MVP, migrar después |

---

## Arquitectura Objetivo

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ARQUITECTURA v2.0                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐     ┌──────────────────┐     ┌───────────────────┐    │
│  │    INPUTS       │     │     BACKEND      │     │    POSTGRESQL     │    │
│  │                 │     │                  │     │                   │    │
│  │ • Emails BAC    │────▶│   FastAPI        │────▶│  Datos relacionales│   │
│  │ • SMS SINPE     │     │   (REST API)     │     │  + pgvector       │    │
│  │ • PDFs estados  │     │                  │     │  (embeddings)     │    │
│  │ • Input manual  │     │   Services       │     │                   │    │
│  │ • Lenguaje nat. │     │   (tu código)    │     │  tenant_id en     │    │
│  └─────────────────┘     └────────┬─────────┘     │  todas las tablas │    │
│                                   │               └───────────────────┘    │
│                                   │                                        │
│                                   ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      MCP SERVER INTELIGENTE                          │  │
│  │                                                                      │  │
│  │  Nivel 1 (CRUD):        Nivel 2 (Análisis):    Nivel 3 (Coaching):  │  │
│  │  • get_transactions     • spending_patterns    • budget_coaching    │  │
│  │  • get_budgets          • anomaly_detection    • goal_recommendations│  │
│  │  • create_transaction   • subscription_finder  • cashflow_prediction │  │
│  │                                                                      │  │
│  │  Clientes: Claude Desktop, ChatGPT, Cursor, tu propia app           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      FRONTENDS                                       │  │
│  │                                                                      │  │
│  │  MVP: Streamlit Dashboard          Futuro: Reflex/React Native      │  │
│  │  • 13 páginas existentes           • Multi-usuario                  │  │
│  │  • Consume FastAPI                 • Mobile-first                   │  │
│  │  • Deploy: Streamlit Cloud         • Deploy: Vercel/Railway         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Plan de Fases

### Vista General del Timeline

```
FASE 0: Preparación y Limpieza ──────────────── Semana 1-2 (2 semanas)
        │
        ▼
FASE 1: Fundamentos de Producción ───────────── Semana 3-5 (3 semanas)
        │
        ▼
FASE 2: API REST Profesional ────────────────── Semana 6-8 (3 semanas)
        │
        ▼
FASE 3: RAG con pgvector ────────────────────── Semana 9-10 (2 semanas)
        │
        ▼
FASE 4: MCP Server Diferenciado ─────────────── Semana 11-12 (2 semanas)
        │
        ▼
FASE 5: Parsing SINPE + Bancos CR ───────────── Semana 13-14 (2 semanas)
        │
        ▼
FASE 6: Polish y Deploy ─────────────────────── Semana 15-16 (2 semanas)

TOTAL: 16 semanas (~4 meses part-time)
```

---

## FASE 0: Preparación y Limpieza
**Duración:** 2 semanas  
**Urgencia:** CRÍTICA - Sin esto, todo lo demás se complica

### Objetivo
Preparar el codebase existente para los cambios grandes que vienen. Auditar qué hay, qué funciona, qué hay que tirar.

### Por Qué Esta Fase Existe
Tu proyecto está al 50-60%. Antes de agregar features nuevas, necesitás:
1. Saber exactamente qué código funciona y qué no
2. Limpiar deuda técnica que va a estorbar
3. Establecer estructura de carpetas correcta
4. Configurar herramientas de desarrollo

### Entregables Concretos

#### Semana 1: Auditoría y Documentación
- [ ] **Inventario de código**: Lista de todos los archivos, qué hace cada uno, estado (funciona/parcial/roto)
- [ ] **Diagrama de arquitectura actual**: Cómo fluyen los datos hoy
- [ ] **Lista de dependencias**: Revisar pyproject.toml, identificar obsoletas
- [ ] **Identificar código muerto**: Archivos/funciones que no se usan
- [ ] **Documentar decisiones existentes**: Por qué se eligió cada tecnología

#### Semana 2: Limpieza y Estructura
- [ ] **Eliminar código muerto** identificado
- [ ] **Reorganizar estructura de carpetas** al estándar:
```
finanzas-tracker/
├── src/
│   ├── api/           # FastAPI (nuevo)
│   ├── core/          # Config, security, constants
│   ├── models/        # SQLAlchemy models
│   ├── schemas/       # Pydantic schemas
│   ├── services/      # Business logic
│   ├── parsers/       # Bank/SINPE parsers
│   └── mcp/           # MCP server (nuevo)
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── scripts/           # CLI utilities
├── alembic/           # Migrations
├── docs/              # Documentation
└── streamlit_app/     # Dashboard (existente)
```
- [ ] **Configurar pre-commit hooks**: ruff, mypy, pytest
- [ ] **Crear .env.example** con todas las variables necesarias
- [ ] **README.md profesional** con badges, quick start, arquitectura

### Métricas de Éxito
| Métrica | Target |
|---------|--------|
| Archivos documentados | 100% |
| Código muerto eliminado | 100% |
| Pre-commit hooks funcionando | ✓ |
| README completo | ✓ |

### Riesgos y Mitigaciones
| Riesgo | Probabilidad | Mitigación |
|--------|--------------|------------|
| Descubrir más deuda técnica de la esperada | Alta | Documentar pero no arreglar todo, priorizar |
| Romper funcionalidad existente | Media | Commit frecuente, branches por tarea |

---

## FASE 1: Fundamentos de Producción
**Duración:** 3 semanas  
**Urgencia:** CRÍTICA - Base para todo lo demás

### Objetivo
Transformar el proyecto de "funciona en mi máquina" a "production-ready" con PostgreSQL, pgvector, Docker, y tests.

### Por Qué Esta Fase Existe
1. **SQLite no escala**: No soporta concurrencia, no tiene pgvector
2. **Sin Docker no hay deploy**: Nadie va a instalar dependencias manualmente
3. **Sin tests no hay confianza**: Especialmente crítico para app financiera
4. **tenant_id ahora es gratis**: Agregarlo después requiere migración masiva

### Entregables Concretos

#### Semana 3: PostgreSQL + pgvector
- [ ] **docker-compose.yml** con PostgreSQL 16 + pgvector
- [ ] **Actualizar SQLAlchemy models** para PostgreSQL
- [ ] **Agregar tenant_id** a TODAS las tablas (UUID, nullable por ahora)
- [ ] **Migración Alembic** para nuevo schema
- [ ] **Script de seed** para datos de prueba
- [ ] **Habilitar pgvector extension** en PostgreSQL

#### Semana 4: Testing Infrastructure
- [ ] **pytest configurado** con fixtures
- [ ] **Fixtures de datos realistas** (transacciones, categorías, presupuestos)
- [ ] **Mocks para APIs externas** (Claude, email)
- [ ] **Tests para models** (CRUD básico)
- [ ] **Tests para services críticos**:
  - TransactionService
  - CategorizationService (tu lógica 3-tier)
  - BudgetService
- [ ] **Coverage report** configurado (pytest-cov)
- [ ] **GitHub Actions CI** corriendo tests en cada PR

#### Semana 5: Docker + Deploy Local
- [ ] **Dockerfile** multi-stage optimizado
- [ ] **docker-compose.yml completo** (API + DB + Redis opcional)
- [ ] **Health checks** configurados
- [ ] **Volúmenes** para persistencia
- [ ] **Variables de entorno** documentadas
- [ ] **Makefile** con comandos comunes:
  - `make dev` - Levantar todo para desarrollo
  - `make test` - Correr tests
  - `make lint` - Correr linters
  - `make migrate` - Correr migraciones

### Decisiones Técnicas Importantes

#### Por Qué pgvector en lugar de ChromaDB
| Aspecto | ChromaDB | pgvector |
|---------|----------|----------|
| Complejidad | DB separada | Mismo PostgreSQL |
| ACID compliance | No | Sí (crítico para finanzas) |
| Backup/restore | Separado | Junto con datos |
| Escalabilidad | Buena | Excelente con pgvectorscale |
| Costo en producción | Servicio separado | Incluido en Postgres |

#### Por Qué tenant_id Ahora
Agregar multi-tenancy después requiere:
1. Migración de TODOS los datos
2. Cambiar TODAS las queries
3. Riesgo de bugs de seguridad

Agregarlo ahora es solo un campo extra que se ignora hasta que lo necesités.

#### Estructura de tenant_id
```python
# En cada model
class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(UUID, nullable=True, index=True)  # Nullable por ahora
    # ... resto de campos
```

### Métricas de Éxito
| Métrica | Target |
|---------|--------|
| Test coverage (lógica financiera) | ≥80% |
| Test coverage (general) | ≥60% |
| docker-compose up funciona | ✓ |
| CI pipeline verde | ✓ |
| Migraciones automáticas | ✓ |

### Riesgos y Mitigaciones
| Riesgo | Probabilidad | Mitigación |
|--------|--------------|------------|
| Migración de datos falla | Media | Backup antes, script reversible |
| Tests lentos | Media | Usar SQLite in-memory para unit tests |
| Docker build lento | Baja | Multi-stage build, cache layers |

---

## FASE 2: API REST Profesional
**Duración:** 3 semanas  
**Urgencia:** ALTA - Base para MCP y cualquier frontend

### Objetivo
Crear API REST completa con FastAPI que exponga toda la funcionalidad. El dashboard Streamlit se convierte en cliente de esta API.

### Por Qué Esta Fase Existe
1. **Separación de concerns**: UI y lógica no deben estar mezclados
2. **Base para MCP**: El MCP server va a llamar a esta API
3. **Múltiples clientes**: Web, móvil, CLI, todos usan la misma API
4. **Documentación automática**: Swagger/OpenAPI gratis con FastAPI

### Entregables Concretos

#### Semana 6: Core API
- [ ] **FastAPI app base** con estructura correcta
- [ ] **Dependency injection** para DB sessions
- [ ] **Pydantic schemas** para request/response
- [ ] **Endpoints de transacciones**:
  - GET /transactions (con filtros: fecha, categoría, monto, búsqueda)
  - POST /transactions
  - GET /transactions/{id}
  - PUT /transactions/{id}
  - DELETE /transactions/{id} (soft delete)
  - POST /transactions/natural-language (crear desde texto)
- [ ] **Endpoints de categorías**:
  - GET /categories
  - GET /categories/{id}/transactions
- [ ] **Error handling** consistente con códigos HTTP correctos
- [ ] **Logging** estructurado (JSON)

#### Semana 7: Analytics API
- [ ] **Endpoints de presupuesto**:
  - GET /budgets (estado actual 50/30/20)
  - GET /budgets/{month} (mes específico)
  - PUT /budgets (actualizar límites)
- [ ] **Endpoints de analytics**:
  - GET /analytics/spending-by-category
  - GET /analytics/monthly-trends
  - GET /analytics/anomalies
  - GET /analytics/subscriptions (detectadas automáticamente)
  - GET /analytics/end-of-month-prediction
- [ ] **Endpoints de ingresos**:
  - GET /incomes
  - POST /incomes
  - GET /incomes/recurring

#### Semana 8: Integración y Docs
- [ ] **Migrar Streamlit** para consumir la API (no queries directos)
- [ ] **OpenAPI docs** revisados y con ejemplos
- [ ] **Postman/Insomnia collection** exportada
- [ ] **Tests de integración** para endpoints críticos
- [ ] **Rate limiting** básico (para preparar multi-tenant)
- [ ] **CORS** configurado correctamente

### Estructura de la API

```
src/api/
├── __init__.py
├── main.py              # FastAPI app, middleware, CORS
├── deps.py              # Dependencies (get_db, get_current_user)
└── v1/
    ├── __init__.py
    ├── router.py        # Incluye todos los routers
    └── endpoints/
        ├── transactions.py
        ├── categories.py
        ├── budgets.py
        ├── analytics.py
        ├── incomes.py
        └── ai.py        # Endpoints de RAG (fase 3)
```

### Patrones a Seguir

#### Request/Response Schemas
```python
# Siempre separar Create, Update, Response
class TransactionCreate(BaseModel):
    amount: Decimal
    description: str
    date: date
    category_id: int | None = None

class TransactionUpdate(BaseModel):
    amount: Decimal | None = None
    description: str | None = None
    category_id: int | None = None

class TransactionResponse(BaseModel):
    id: int
    amount: Decimal
    description: str
    date: date
    category: CategoryResponse | None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
```

#### Error Responses Consistentes
```python
class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    code: str  # Para i18n futuro

# Siempre usar HTTPException con detail estructurado
raise HTTPException(
    status_code=404,
    detail={"error": "Transaction not found", "code": "TXN_NOT_FOUND"}
)
```

### Métricas de Éxito
| Métrica | Target |
|---------|--------|
| Endpoints documentados | 100% |
| Tests de integración | ≥20 |
| Streamlit usando API | 100% de queries |
| Response time p95 | <200ms |

---

## FASE 3: RAG con pgvector
**Duración:** 2 semanas  
**Urgencia:** ALTA - Diferenciador de AI

### Objetivo
Implementar búsqueda semántica y RAG usando pgvector integrado en PostgreSQL. El usuario puede hacer preguntas en lenguaje natural sobre sus finanzas.

### Por Qué Esta Fase Existe
1. **Queries naturales**: "¿Por qué gasté tanto en marzo?" en vez de filtros
2. **Contexto para Claude**: RAG da datos reales, no alucinaciones
3. **Diferenciador**: Pocas apps de finanzas tienen esto bien implementado

### Entregables Concretos

#### Semana 9: Embeddings y Búsqueda
- [ ] **Modelo de embeddings** seleccionado e integrado:
  - Recomendado: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
  - 384 dimensiones, soporta español nativo, rápido
- [ ] **Columna embedding** en tabla transactions
- [ ] **Función de indexación** que genera embedding al crear/actualizar transacción
- [ ] **Índice HNSW** para búsqueda rápida
- [ ] **Función de búsqueda semántica** con filtros (fecha, categoría, monto)
- [ ] **Script de backfill** para transacciones existentes

#### Semana 10: RAG Chain
- [ ] **RAG service** que:
  1. Recibe pregunta en español
  2. Busca transacciones relevantes (top 20)
  3. Obtiene estadísticas actuales (presupuesto, tendencias)
  4. Construye prompt con contexto
  5. Genera respuesta con Claude
- [ ] **Endpoint /ai/chat** en la API
- [ ] **Prompt engineering** optimizado para finanzas CR
- [ ] **Manejo de casos edge**:
  - Pregunta sin datos suficientes
  - Pregunta fuera de scope (no financiera)
  - Datos contradictorios
- [ ] **Tests con preguntas reales** (mínimo 20 ejemplos)

### Arquitectura RAG

```
┌─────────────────────────────────────────────────────────────────────┐
│                         RAG PIPELINE                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Pregunta: "¿Por qué gasté tanto en restaurantes este mes?"       │
│                            │                                        │
│                            ▼                                        │
│   ┌─────────────────────────────────────────┐                      │
│   │  1. EMBEDDING DE LA PREGUNTA            │                      │
│   │     sentence-transformers → [0.1, ...]  │                      │
│   └─────────────────────────────────────────┘                      │
│                            │                                        │
│                            ▼                                        │
│   ┌─────────────────────────────────────────┐                      │
│   │  2. BÚSQUEDA EN PGVECTOR                │                      │
│   │     SELECT * FROM transactions          │                      │
│   │     WHERE embedding <-> query_emb < 0.5 │                      │
│   │     AND category = 'Restaurantes'       │                      │
│   │     ORDER BY embedding <-> query_emb    │                      │
│   │     LIMIT 20;                           │                      │
│   └─────────────────────────────────────────┘                      │
│                            │                                        │
│                            ▼                                        │
│   ┌─────────────────────────────────────────┐                      │
│   │  3. ENRIQUECER CONTEXTO                 │                      │
│   │     • Transacciones relevantes          │                      │
│   │     • Presupuesto actual                │                      │
│   │     • Promedio histórico                │                      │
│   │     • Anomalías detectadas              │                      │
│   └─────────────────────────────────────────┘                      │
│                            │                                        │
│                            ▼                                        │
│   ┌─────────────────────────────────────────┐                      │
│   │  4. PROMPT A CLAUDE                     │                      │
│   │     System: Eres asistente financiero   │                      │
│   │     Context: [datos enriquecidos]       │                      │
│   │     Question: [pregunta original]       │                      │
│   └─────────────────────────────────────────┘                      │
│                            │                                        │
│                            ▼                                        │
│   Respuesta: "Gastaste ₡85,000 en restaurantes este mes,           │
│               un 40% más que tu promedio de ₡60,000..."            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Texto Enriquecido para Embeddings
```
Cada transacción se convierte en texto rico para mejor búsqueda:

"Gasto de ₡25,000 en UBER EATS el 15 de noviembre 2025. 
Categoría: Restaurantes. Comercio: Uber Eats. 
Notas del usuario: Cena con amigos."

Este texto se embebe y almacena junto con la transacción.
```

### Métricas de Éxito
| Métrica | Target |
|---------|--------|
| Preguntas de prueba respondidas correctamente | ≥80% |
| Latencia de respuesta | <3 segundos |
| Relevancia de transacciones recuperadas | ≥90% |

---

## FASE 4: MCP Server Diferenciado
**Duración:** 2 semanas  
**Urgencia:** ALTA - Diferenciador principal para portfolio

### Objetivo
Crear MCP Server que va MÁS ALLÁ de CRUD básico. Actual Budget ya tiene MCP con CRUD; el tuyo debe ofrecer coaching inteligente y predicciones.

### Por Qué Esta Fase Existe
1. **Portfolio wow factor**: MCP es tecnología de punta (noviembre 2024)
2. **Diferenciación real**: No otro "get_transactions", sino "dame coaching financiero"
3. **Uso práctico**: Vos mismo lo vas a usar con Claude Desktop

### Entregables Concretos

#### Semana 11: MCP Básico + Análisis
- [ ] **MCP Server base** con FastMCP
- [ ] **Tools Nivel 1 (CRUD)**:
  - get_transactions (con filtros)
  - get_budget_status
  - create_transaction
  - categorize_transaction
- [ ] **Tools Nivel 2 (Análisis)**:
  - analyze_spending_pattern (usa RAG)
  - detect_anomalies
  - find_subscriptions
  - compare_periods
- [ ] **Resources**:
  - monthly_report/{year}/{month}
  - category_breakdown/{period}
- [ ] **Configuración Claude Desktop** documentada

#### Semana 12: Coaching Inteligente
- [ ] **Tools Nivel 3 (Coaching)** - EL DIFERENCIADOR:
  - budget_coaching: Analiza patrones y da recomendaciones personalizadas
  - goal_advisor: Sugiere cómo alcanzar metas de ahorro
  - cashflow_prediction: Predice si llegarás a fin de mes
  - spending_alert: Identifica gastos problemáticos proactivamente
  - savings_opportunities: Encuentra dónde podés ahorrar
- [ ] **Prompts de coaching** optimizados
- [ ] **Tests con conversaciones reales**
- [ ] **Video demo** de 3 minutos para portfolio

### Diferenciación vs Actual Budget MCP

| Feature | Actual Budget MCP | Tu MCP Server |
|---------|------------------|---------------|
| get_transactions | ✓ | ✓ |
| get_budget | ✓ | ✓ |
| update_transaction | ✓ | ✓ |
| **RAG search** | ✗ | ✓ |
| **Budget coaching** | ✗ | ✓ |
| **Cashflow prediction** | ✗ | ✓ |
| **SINPE Móvil parsing** | ✗ | ✓ |
| **Spanish/Costa Rica** | ✗ | ✓ |

### Ejemplo de Conversación con Coaching

```
Usuario: "Claude, ¿cómo puedo ahorrar más este mes?"

Claude: [Usa savings_opportunities + budget_coaching]

"Analizando tus patrones del último trimestre, encontré 3 oportunidades:

1. **Suscripciones sin usar** (₡15,000/mes)
   - Spotify Premium: No has escuchado música en 45 días
   - Gym: Solo 2 visitas en noviembre
   
2. **Delivery vs. Supermercado** (₡25,000/mes potencial)
   - Gastás ₡18,000/semana en Uber Eats
   - Tu ticket promedio de supermercado es ₡12,000
   - Cocinar 2 veces más por semana = ₡25,000 de ahorro
   
3. **Compras impulsivas nocturnas** (₡20,000/mes)
   - 8 compras después de las 10pm este mes
   - Promedio: ₡12,500 cada una
   - Tip: Activá el 'modo sueño' en apps de compras

Total potencial de ahorro: ₡60,000/mes

¿Querés que te ayude a configurar alertas para alguna de estas?"
```

### Métricas de Éxito
| Métrica | Target |
|---------|--------|
| Tools implementados | ≥15 |
| Nivel 3 (coaching) tools | ≥5 |
| Demo video creado | ✓ |
| Funciona en Claude Desktop | ✓ |

---

## FASE 5: Parsing SINPE + Bancos CR
**Duración:** 2 semanas  
**Urgencia:** MEDIA-ALTA - Diferenciador de mercado

### Objetivo
Implementar parsers robustos para notificaciones de SINPE Móvil y emails/PDFs de bancos costarricenses.

### Por Qué Esta Fase Existe
1. **Integración automática**: Sin APIs bancarias, parsing es la única opción
2. **Diferenciador local**: Ninguna app internacional hace esto
3. **Data real**: Más transacciones = mejor AI

### Entregables Concretos

#### Semana 13: SINPE Móvil + BAC
- [ ] **Parser de SMS SINPE Móvil**:
  - Formato: "Ha recibido X Colones de [NOMBRE] por SINPE Movil, [DESC]. Comprobante [NUM]"
  - Extraer: monto, remitente, descripción, número
- [ ] **Parser de emails BAC**:
  - Notificaciones de compra
  - Notificaciones de transferencia
  - Formato HTML específico de BAC
- [ ] **Parser de PDFs BAC**:
  - Estados de cuenta mensuales
  - Usar Claude Vision para extracción
- [ ] **Tests con ejemplos reales** (sanitizados)
- [ ] **Manejo de casos edge** (formatos viejos, errores de encoding)

#### Semana 14: Otros Bancos + Consolidación
- [ ] **Parser de emails Banco Popular**
- [ ] **Parser genérico** para bancos no soportados (best-effort)
- [ ] **Sistema de detección automática** de banco por formato
- [ ] **UI para importar** SMS/emails manualmente
- [ ] **Documentación** de formatos soportados
- [ ] **Guía para contribuir** nuevos parsers

### Arquitectura de Parsers

```
src/parsers/
├── __init__.py
├── base.py              # Clase base abstracta
├── detector.py          # Detecta qué parser usar
├── sinpe/
│   ├── __init__.py
│   └── sms_parser.py    # SMS de SINPE Móvil
├── bac/
│   ├── __init__.py
│   ├── email_parser.py  # Emails de notificación
│   └── pdf_parser.py    # Estados de cuenta PDF
├── popular/
│   ├── __init__.py
│   └── email_parser.py
└── generic/
    └── fallback_parser.py  # Best-effort para desconocidos
```

### Formato de SMS SINPE (Real)

```
Formato entrante:
"Ha recibido 15,000.00 Colones de MARIA PEREZ GONZALEZ por SINPE Movil, 
ALMUERZO. Comprobante 123456789"

Formato saliente:
"Envio exitoso de 10,000.00 Colones a JUAN RODRIGUEZ por SINPE Movil. 
Comprobante 987654321"

Campos a extraer:
- tipo: "recibido" | "enviado"
- monto: Decimal
- moneda: "CRC"
- persona: str (nombre completo)
- descripcion: str (después de la coma)
- comprobante: str
```

### Métricas de Éxito
| Métrica | Target |
|---------|--------|
| Formatos SINPE parseados | ≥95% accuracy |
| Formatos BAC parseados | ≥90% accuracy |
| Bancos soportados | ≥3 |
| Tests con data real | ≥50 ejemplos |

---

## FASE 6: Polish y Deploy
**Duración:** 2 semanas  
**Urgencia:** MEDIA - Necesario para mostrar

### Objetivo
Preparar el proyecto para ser mostrado a reclutadores, amigos, y eventualmente usuarios reales.

### Entregables Concretos

#### Semana 15: Polish
- [ ] **README.md profesional**:
  - Badges (tests, coverage, license)
  - GIF/video demo
  - Quick start (< 5 minutos)
  - Arquitectura visual
  - Roadmap
- [ ] **Documentación de API** completa con ejemplos
- [ ] **Guía de contribución** (CONTRIBUTING.md)
- [ ] **Changelog** (CHANGELOG.md)
- [ ] **Licencia** definida (recomiendo MIT para portfolio)
- [ ] **Seguridad básica**:
  - Argon2id para passwords (si hay auth)
  - Rate limiting
  - Input validation
  - SQL injection prevention (SQLAlchemy ya lo hace)
- [ ] **Métricas en dashboard**: Mostrar estadísticas de uso

#### Semana 16: Deploy
- [ ] **Deploy a Streamlit Cloud** (gratis, fácil)
- [ ] **CI/CD completo**:
  - Tests en cada PR
  - Deploy automático en merge a main
- [ ] **Monitoreo básico** (logs, errores)
- [ ] **Backup de datos** configurado
- [ ] **Video demo final** (5 minutos)
- [ ] **LinkedIn post** preparado
- [ ] **Preparar para entrevistas**:
  - 3 historias de decisiones técnicas
  - Trade-offs explicados
  - Métricas de impacto

### Checklist Final para Portfolio

```
[ ] ¿Funciona con un solo comando? (docker-compose up)
[ ] ¿Tiene demo accesible online?
[ ] ¿El README explica qué hace en 30 segundos?
[ ] ¿Hay tests que pasan?
[ ] ¿El código está limpio y documentado?
[ ] ¿Puedo explicar cada decisión técnica?
[ ] ¿Tiene algo único que otros proyectos no tienen?
[ ] ¿Lo usaría yo mismo diariamente?
```

### Métricas de Éxito
| Métrica | Target |
|---------|--------|
| Tiempo de setup para nuevo usuario | <5 minutos |
| Demo online accesible | ✓ |
| Video demo creado | ✓ |
| Uptime del demo | >95% |

---

## Después de las 16 Semanas

### Opciones de Crecimiento

1. **Agregar más bancos**: Guatemala, El Salvador, Panamá
2. **Mobile app**: Reflex o React Native
3. **Multi-usuario**: Activar tenant_id, agregar auth
4. **SaaS**: Pricing tiers, Stripe integration
5. **B2B**: Dashboard para contadores/financieros

### Prioridad Sugerida Post-MVP
1. Agregar autenticación y multi-usuario
2. Parser para 2-3 bancos más de CR
3. Mobile app básica
4. Explorar modelo de negocio (freemium?)

---

## Consejos Finales

### Para Trabajar con AI Assistants (Cursor/Copilot)

1. **Un objetivo por sesión**: No mezclar "arreglar tests" con "agregar feature"
2. **Contexto específico**: Incluir archivos relevantes, no todo el proyecto
3. **Validar output**: AI genera código plausible pero no siempre correcto
4. **Commits frecuentes**: Antes de pedir cambios grandes, commitear lo que funciona
5. **Tests primero**: Pedir tests antes de implementación ayuda a clarificar requirements

### Para Entrevistas

**Pregunta típica**: "Cuéntame sobre un desafío técnico en tu proyecto"

**Respuesta preparada**: 
"El mayor desafío fue la integración con bancos costarricenses sin APIs. 
Investigué alternativas: scraping (frágil y posiblemente ilegal), 
APIs de agregadores (no cubren CR), o parsing de notificaciones. 
Elegí parsing de SMS/emails porque es legal, estable (los formatos 
cambian poco), y respeta la privacidad del usuario. Implementé un 
sistema de parsers modulares con una clase base abstracta, detección 
automática de formato, y 95% de accuracy en SINPE Móvil validado 
con 50+ ejemplos reales."

### Mantenimiento de Motivación

- **Semana 1-4**: Setup es aburrido pero crítico. Celebrá tener CI verde.
- **Semana 5-8**: API es satisfactorio, ves progreso tangible.
- **Semana 9-12**: RAG y MCP son las partes "wow". Grabá demos.
- **Semana 13-16**: Parsing es tedioso pero diferenciador. Mantené el foco.

**Recordá**: El proyecto ya está al 50-60%. No estás empezando de cero. 
Cada fase construye sobre lo anterior. En 4 meses tenés algo que 
realmente te diferencia en el mercado laboral y que además te sirve 
a vos para manejar tus finanzas.

¡Éxitos! 🚀
