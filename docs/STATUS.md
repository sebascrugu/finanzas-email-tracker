# 📊 Finanzas Tracker CR - Estado Actual (Real)

**Fecha:** 1 de Diciembre, 2025  
**Versión:** 0.1.0  
**Branch:** `clean-architecture`

> ⚠️ **Este documento solo describe lo que EXISTE en código.**  
> Para ideas futuras, ver [VISION.md](./VISION.md)

---

## 🎯 ¿Qué Es?

Sistema de finanzas personales para **Costa Rica** que:
- Lee automáticamente correos bancarios (BAC, Popular)
- Categoriza gastos con AI (Claude)
- Implementa presupuesto 50/30/20
- Tiene chat inteligente (RAG + pgvector)
- **Trackea patrimonio (cuentas, inversiones, metas)**

**Bancos soportados:** BAC Credomatic, Banco Popular

---

## 📊 Métricas Actuales

| Métrica | Valor |
|---------|-------|
| Tests | 419 |
| Coverage | 54% |
| Modelos SQLAlchemy | 16 |
| Endpoints API | ~55 |
| Páginas Dashboard | 8 |

---

## 🏗️ Stack Tecnológico

| Capa | Tecnología |
|------|------------|
| Backend | Python 3.11+, FastAPI |
| ORM | SQLAlchemy 2.0 |
| Base de Datos | PostgreSQL 16 + pgvector |
| AI | Claude (Anthropic), sentence-transformers |
| Dashboard | Streamlit |
| Email | Microsoft Graph API (MSAL) |
| Auth | JWT (PyJWT + bcrypt) |

---

## 📁 Estructura

```
src/finanzas_tracker/
├── api/              # FastAPI REST API
│   ├── routers/      # transactions, categories, budgets, profiles, ai, patrimony, auth
│   └── schemas/      # Pydantic request/response
├── core/             # Config, database, logging
├── models/           # SQLAlchemy models (14 modelos)
├── parsers/          # Email/PDF parsers
├── services/         # Business logic
├── mcp/              # MCP Server (Claude Desktop)
├── dashboard/        # Streamlit UI
└── repositories/     # Data access layer (parcial)
```

---

## ✅ Modelos Existentes (14)

### Core
| Modelo | Descripción | Campos Clave |
|--------|-------------|--------------|
| `User` | Autenticación JWT | email, password_hash, is_active |
| `Profile` | Usuario/contexto | email, nombre, icono |
| `Transaction` | Gasto/ingreso | monto, comercio, categoría, fecha |
| `Card` | Tarjeta bancaria | últimos 4, tipo, límite, fecha_corte, fecha_pago |
| `BillingCycle` | Ciclo facturación tarjeta | fecha_corte, fecha_pago, total, pago_mínimo |
| `CardPayment` | Pago a tarjeta | monto, tipo, fecha, ciclo |
| `Income` | Ingresos | tipo, monto, recurrencia |

### Categorización
| Modelo | Descripción |
|--------|-------------|
| `Category` | Categoría principal (necesidades/gustos/ahorros) |
| `Subcategory` | Subcategoría con keywords |
| `Budget` | Presupuesto mensual por categoría |
| `Merchant` | Comercio normalizado con variantes |

### Patrimonio (NUEVO ✨)
| Modelo | Descripción |
|--------|-------------|
| `Account` | Cuenta bancaria con saldo |
| `Investment` | CDP, ahorros a plazo, fondos |
| `Goal` | Meta financiera con progreso |

### AI/RAG
| Modelo | Descripción |
|--------|-------------|
| `TransactionEmbedding` | Vector para búsqueda semántica |
| `ExchangeRateCache` | Caché tipo de cambio USD/CRC |

---

## ✅ Servicios Funcionando

| Servicio | Función |
|----------|---------|
| `AuthService` | Autenticación JWT, registro, login |
| `PatrimonyService` | Cálculo de patrimonio neto |
| `CardService` | Gestión tarjetas, ciclos, pagos (NUEVO ✨) |
| `EmailFetcher` | Conecta Microsoft Graph, busca correos |
| `BACParser` | Parsea emails de BAC (100% precisión) |
| `PopularParser` | Parsea emails de Banco Popular |
| `BACPDFParser` | Parsea estados de cuenta PDF |
| `TransactionCategorizer` | Categoriza con keywords + Claude AI |
| `RAGService` | Chat inteligente con contexto |
| `EmbeddingService` | Genera embeddings para búsqueda |
| `InsightsService` | Análisis automáticos (8 tipos) |
| `ExchangeRateService` | Tipo de cambio USD/CRC |

---

## ✅ API REST

**Base:** `http://localhost:8000/api/v1`

### Authentication
```
POST   /auth/register     # Crear usuario
POST   /auth/login        # Login → JWT token
GET    /auth/me           # Usuario actual (protegido)
```

### Patrimonio
```
GET    /patrimony/summary              # Net worth total
GET    /patrimony/returns              # Rendimientos inversiones
GET    /patrimony/goals-progress       # Progreso de metas

GET    /patrimony/accounts             # Listar cuentas
POST   /patrimony/accounts             # Crear cuenta
GET    /patrimony/accounts/{id}        # Detalle cuenta
PATCH  /patrimony/accounts/{id}        # Actualizar saldo
DELETE /patrimony/accounts/{id}        # Eliminar cuenta

GET    /patrimony/investments          # Listar inversiones
POST   /patrimony/investments          # Crear inversión
PATCH  /patrimony/investments/{id}     # Actualizar
DELETE /patrimony/investments/{id}     # Eliminar

GET    /patrimony/goals                # Listar metas
POST   /patrimony/goals                # Crear meta
POST   /patrimony/goals/{id}/contribute # Agregar ahorro
DELETE /patrimony/goals/{id}           # Eliminar
```

### Tarjetas (NUEVO ✨)
```
GET    /cards                          # Listar tarjetas
GET    /cards/{id}                     # Resumen completo tarjeta
GET    /cards/{id}/interest-projection # Proyección intereses

GET    /cards/{id}/cycles              # Ciclos de facturación
POST   /cards/{id}/cycles              # Crear ciclo manual
POST   /cards/{id}/cycles/auto         # Crear ciclo automático
POST   /cards/{id}/cycles/{cid}/close  # Cerrar ciclo

GET    /cards/{id}/payments            # Historial pagos
POST   /cards/{id}/payments            # Registrar pago

GET    /cards/alerts/upcoming          # Alertas próximos vencimientos
GET    /cards/alerts/overdue           # Alertas vencidos
```

### Transactions
```
GET    /transactions
POST   /transactions  
GET    /transactions/{id}
PUT    /transactions/{id}
DELETE /transactions/{id}
POST   /transactions/ambiguous/{id}/confirm
```

### Categories, Budgets, Profiles
```
GET    /categories
GET    /categories/{id}/subcategories
GET    /budgets
POST   /budgets
PUT    /budgets/{id}
GET    /profiles
POST   /profiles
PUT    /profiles/{id}
```

### AI & RAG
```
GET    /ai/health
POST   /ai/chat
POST   /ai/search
POST   /ai/embeddings/generate
GET    /ai/embeddings/stats
```

---

## ✅ Dashboard Streamlit

8 páginas:

| Página | Función |
|--------|---------|
| `01_setup` | Configuración inicial, conexión email |
| `02_ingresos` | Gestión de ingresos recurrentes |
| `03_balance` | Balance general y patrimonio |
| `04_transacciones` | Lista y edición de transacciones |
| `05_desglose` | Desglose por categoría 50/30/20 |
| `06_merchants` | Top comercios y análisis |
| `07_chat` | Chat AI con RAG |
| `08_insights` | Insights automáticos |

---

## ✅ MCP Server

12 herramientas para Claude Desktop:

```python
# Configuración
set_profile(profile_id)
list_profiles()

# Consultas
get_transactions(days, category, min_amount)
get_spending_summary(period, group_by)
get_top_merchants(days, limit)

# Análisis
search_transactions(query)
get_monthly_comparison()

# Coaching
budget_coaching()
savings_opportunities()
cashflow_prediction()
spending_alert()
goal_advisor(amount, months, name)
```

---

## ❌ Lo Que Falta (Priorizado)

### 🔴 Urgente
| Feature | Estado |
|---------|--------|
| Deploy público | Configurado, pendiente deploy |
| Coverage → 70% | En 54% |
| UI Patrimonio en Streamlit | Falta página |

### 🟡 Importante (Próximo)
| Feature | Estado |
|---------|--------|
| Ciclos facturación tarjeta | Card existe, falta BillingCycle |
| Alertas fecha de pago | ❌ |
| Tracking deuda tarjeta | Parcial |

### 🔵 Después
| Feature | Estado |
|---------|--------|
| Detector suscripciones | ❌ |
| Streaks/gamification | ❌ |
| Frontend moderno | ❌ (solo Streamlit) |

> Ver [VISION.md](./VISION.md) para el plan completo

---

## 🧪 Tests

```
tests/
├── unit/           ~300 tests
├── integration/    ~50 tests
├── api/            ~40 tests
└── mcp/            ~30 tests
```

**Coverage actual: 54%** (meta: 70%+)

---

## 🚀 Cómo Correr

```bash
# Instalar
poetry install

# Base de datos
docker compose up -d

# Migraciones
poetry run alembic upgrade head

# API
poetry run uvicorn finanzas_tracker.api.main:app --reload

# Dashboard
poetry run streamlit run src/finanzas_tracker/dashboard/app.py

# Tests
poetry run pytest
```

---

## 📞 Contacto

- **Dev:** Sebastián Cruz
- **Repo:** github.com/sebascrugu/finanzas-email-tracker
