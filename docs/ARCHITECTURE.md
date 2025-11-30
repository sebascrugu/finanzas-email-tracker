# Arquitectura de Finanzas Tracker CR

## Vista General

```
┌──────────────────────────────────────────────────────────────────┐
│                        ARQUITECTURA                               │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ENTRADA DE DATOS          PROCESAMIENTO         ALMACENAMIENTO  │
│  ┌─────────────┐          ┌─────────────┐       ┌────────────┐  │
│  │ Emails BAC  │────┐     │  Parsers    │       │  SQLite    │  │
│  │ Emails      │────┼────▶│  Services   │──────▶│  (dev)     │  │
│  │ Popular     │────┘     │  AI Claude  │       │ PostgreSQL │  │
│  └─────────────┘          └──────┬──────┘       │  (prod)    │  │
│                                  │               └────────────┘  │
│                                  ▼                               │
│  INTERFACES                 ┌─────────────┐                     │
│  ┌─────────────┐           │  FastAPI    │                     │
│  │ Streamlit   │◀──────────│  REST API   │                     │
│  │ Dashboard   │           │             │                     │
│  └─────────────┘           └─────────────┘                     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Stack Tecnológico

| Capa | Tecnología | Versión |
|------|------------|---------|
| Runtime | Python | 3.11+ |
| API | FastAPI | 0.100+ |
| ORM | SQLAlchemy | 2.0+ |
| DB Dev | SQLite | 3.x |
| DB Prod | PostgreSQL | 16+ |
| Validation | Pydantic | 2.0+ |
| Dashboard | Streamlit | 1.30+ |
| AI | Claude API | claude-3 |

## Estructura de Carpetas

```
src/finanzas_tracker/
├── api/                 # FastAPI REST API
│   ├── main.py         # App principal
│   └── v1/             # Endpoints v1
│       └── endpoints/  # Routers
├── config/             # Settings
│   └── settings.py     # Pydantic Settings
├── core/               # Infraestructura
│   ├── database.py     # SQLAlchemy setup
│   ├── logging.py      # Logging config
│   └── cache.py        # TTL Cache
├── dashboard/          # Streamlit UI
│   ├── app.py          # Entry point
│   └── pages/          # 8 páginas
├── models/             # SQLAlchemy Models
│   ├── profile.py      # Multi-perfil
│   ├── card.py         # Tarjetas
│   ├── transaction.py  # Transacciones
│   ├── category.py     # Categorías 50/30/20
│   ├── budget.py       # Presupuestos
│   ├── income.py       # Ingresos
│   ├── merchant.py     # Comercios
│   ├── exchange_rate_cache.py
│   └── enums.py        # Enums centralizados
├── parsers/            # Email parsers
│   ├── bac_parser.py   # BAC Credomatic
│   └── popular_parser.py # Banco Popular
├── schemas/            # Pydantic Schemas
│   └── transaction.py  # DTOs
└── services/           # Business Logic
    ├── auth_manager.py # Microsoft Graph auth
    ├── email_fetcher.py # Fetch emails
    ├── transaction_processor.py # Core logic
    ├── categorizer.py  # AI categorization
    ├── duplicate_detector.py
    ├── exchange_rate.py
    ├── finance_chat.py # Chat con AI
    ├── insights.py     # AI insights
    └── merchant_service.py
```

## Modelos de Datos

### Diagrama de Relaciones

```
Profile (raíz)
├── Card (1:N)
│   └── Transaction (1:N)
├── Budget (1:N)
│   └── Subcategory (N:1)
├── Income (1:N)
└── Transaction (1:N)
    ├── Subcategory (N:1)
    └── Merchant (N:1)

Category (standalone)
└── Subcategory (1:N)

Merchant
└── MerchantVariant (1:N)

ExchangeRateCache (standalone)
```

### Modelos Core (9 total)

| Modelo | Tabla | Descripción |
|--------|-------|-------------|
| `Profile` | profiles | Usuario/contexto financiero |
| `Card` | cards | Tarjetas débito/crédito |
| `Transaction` | transactions | Transacciones bancarias |
| `Category` | categories | Categorías principales (50/30/20) |
| `Subcategory` | subcategories | Subcategorías detalladas |
| `Budget` | budgets | Presupuestos mensuales |
| `Income` | incomes | Fuentes de ingreso |
| `Merchant` | merchants | Comercios normalizados |
| `MerchantVariant` | merchant_variants | Variantes de nombres |
| `ExchangeRateCache` | exchange_rate_cache | Cache tipos de cambio |

## Servicios (10 total)

| Servicio | Responsabilidad |
|----------|-----------------|
| `AuthManager` | OAuth2 PKCE con Microsoft Graph |
| `EmailFetcher` | Extrae correos de Outlook |
| `TransactionProcessor` | Procesa y guarda transacciones |
| `TransactionCategorizer` | Categorización AI (3 niveles) |
| `DuplicateDetectorService` | Detecta transacciones duplicadas |
| `ExchangeRateService` | Tipos de cambio USD→CRC |
| `FinanceChatService` | Chat con AI sobre finanzas |
| `InsightsService` | Genera insights con AI |
| `MerchantNormalizationService` | Normaliza nombres de comercios |

## Parsers

### BAC Parser (`bac_parser.py`)
- SINPE Móvil enviado/recibido
- Compras con tarjeta
- Retiros ATM
- Pagos de servicios

### Popular Parser (`popular_parser.py`)
- Transacciones SINPE
- Compras y retiros
- Pagos automáticos

## Flujo de Datos

```
1. Usuario → Dashboard → Fetch Emails
2. EmailFetcher → Microsoft Graph API
3. Emails → Parser (BAC/Popular)
4. Parsed → DuplicateDetector
5. New transactions → TransactionProcessor
6. TransactionProcessor → Categorizer (AI)
7. Categorized → Database
8. Dashboard ← Database (queries)
```

## Sistema de Categorización

### 3 Niveles de Fallback

```
Nivel 1: Keywords
├── Match exacto → Categoría
└── No match → Nivel 2

Nivel 2: Histórico
├── Comercio conocido → Última categoría
└── Desconocido → Nivel 3

Nivel 3: Claude AI
├── Análisis contextual
│   ├── Hora del día
│   ├── Día de la semana
│   ├── Monto
│   └── Nombre comercio
└── Categoría + confianza
```

## Regla 50/30/20

| Categoría | % | Ejemplos |
|-----------|---|----------|
| Necesidades | 50% | Vivienda, Transporte, Comida, Salud |
| Gustos | 30% | Entretenimiento, Ropa, Restaurantes |
| Ahorros | 20% | Inversiones, Fondo emergencia |

## Seguridad

- **OAuth2 PKCE**: Login sin exponer secrets
- **Environment Variables**: Secrets en `.env`
- **Soft Deletes**: Nunca DELETE real (`deleted_at`)
- **Input Validation**: Pydantic en todo
- **No Sensitive Logging**: Montos/descripciones no se loggean
