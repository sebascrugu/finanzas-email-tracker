# 💰 Finanzas Tracker CR

<div align="center">

### **Sistema de Finanzas Personales con IA para Costa Rica**

*Parsing automático de emails de BAC Credomatic y Banco Popular*

[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Poetry](https://img.shields.io/badge/dependency%20manager-poetry-blue.svg?logo=poetry)](https://python-poetry.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/ORM-SQLAlchemy%202.0-red.svg)](https://www.sqlalchemy.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![AI Powered](https://img.shields.io/badge/AI-Claude-blueviolet.svg?logo=anthropic)](https://www.anthropic.com/)

</div>

---

## 🌟 ¿Qué hace?

Automatiza el tracking de tus finanzas extrayendo transacciones de **correos bancarios** y categorizándolas con **AI**:

1. 📧 **Extrae transacciones** de correos de BAC/Popular (Outlook)
2. 🤖 **Categoriza automáticamente** con Claude AI (regla 50/30/20)
3. 📊 **Dashboard interactivo** en Streamlit con insights
4. 💬 **Chat con IA** para consultar tus finanzas

---

## ✨ Features

| Feature | Descripción |
|---------|-------------|
| **🏦 Multi-Banco** | BAC Credomatic y Banco Popular con parsers especializados |
| **📱 SINPE Móvil** | Soporte nativo para el sistema de pagos de Costa Rica |
| **🤖 AI Categorization** | Claude categoriza según contexto (hora, monto, comercio) |
| **👥 Multi-Perfil** | Separa finanzas: personal, negocio, familia |
| **💱 Multi-Moneda** | CRC y USD con tipos de cambio automáticos |
| **📈 Presupuesto 50/30/20** | Necesidades, Gustos, Ahorros |
| **🔍 Detección Duplicados** | Evita importar la misma transacción dos veces |
| **🏪 Merchants** | Normaliza comercios (AUTOPISTA1 → Autopistas del Sol) |

---

## 🚀 Quick Start

### Requisitos

- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation)
- Cuenta Outlook/Microsoft 365
- [Anthropic API Key](https://console.anthropic.com/)
- [Azure AD App](https://portal.azure.com/) para Microsoft Graph

### Instalación

```bash
# 1. Clonar
git clone https://github.com/tu-usuario/finanzas-email-tracker.git
cd finanzas-email-tracker

# 2. Instalar dependencias
poetry install

# 3. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus API keys

# 4. Inicializar base de datos
poetry run alembic upgrade head

# 5. Cargar categorías
poetry run python scripts/seed_data.py

# 6. Lanzar dashboard
poetry run streamlit run src/finanzas_tracker/dashboard/app.py
```

Abre http://localhost:8501 🎉

### 🔐 API REST

```bash
# Iniciar API
poetry run uvicorn finanzas_tracker.api.main:app --reload

# Documentación OpenAPI
open http://localhost:8000/docs
```

**Endpoints de Auth:**
```bash
# Registrar usuario
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "password123", "nombre": "Test"}'

# Login → obtener JWT
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "password123"}'

# Usar token en requests
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <tu-token>"
```

### 🚀 Deploy a Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template)

```bash
# 1. Conectar repo a Railway
# 2. Agregar PostgreSQL addon
# 3. Configurar variables de entorno (ver .env.railway.example)
# 4. Deploy automático con push a main
```

---

## 🏗️ Arquitectura

```
src/finanzas_tracker/
├── api/              # FastAPI REST endpoints
├── config/           # Settings con Pydantic
├── core/             # Database, logging, cache
├── dashboard/        # Streamlit UI (8 páginas)
├── models/           # SQLAlchemy 2.0 models (9)
├── parsers/          # BAC y Popular parsers
├── schemas/          # Pydantic schemas
└── services/         # Business logic (10)
```

### Stack Técnico

| Capa | Tecnología |
|------|------------|
| **Backend** | Python 3.11, FastAPI, SQLAlchemy 2.0 |
| **Database** | PostgreSQL 16 + pgvector |
| **Frontend** | Streamlit |
| **AI** | Anthropic Claude, RAG con embeddings |
| **Auth** | JWT (PyJWT + bcrypt), Microsoft Graph OAuth2 |
| **Testing** | pytest, coverage |
| **Deploy** | Docker, Railway |

---

## 📁 Modelos de Datos

```
Profile ──┬── Card ──── Transaction ──── Subcategory ──── Category
          ├── Budget
          └── Income

Merchant ──── MerchantVariant
ExchangeRateCache (standalone)
```

**10 modelos limpios** sin overengineering:
- `User`: Autenticación JWT
- `Profile`: Multi-perfil por email
- `Card`: Tarjetas débito/crédito
- `Transaction`: Transacciones con categorización AI
- `Category`/`Subcategory`: Sistema 50/30/20
- `Budget`: Presupuestos mensuales
- `Income`: Ingresos (salario, freelance, etc)
- `Merchant`/`MerchantVariant`: Normalización de comercios
- `ExchangeRateCache`: Cache de tipos de cambio

---

## 🤖 ¿Cómo funciona la AI?

**Categorización en 3 pasos:**

1. **Keywords** - Detección rápida por palabras clave (McDonalds → Comida)
2. **Histórico** - Si el comercio ya fue categorizado antes, reusar
3. **Claude AI** - Análisis contextual para casos complejos

```python
# Ejemplo: "Uber Eats 11:45pm viernes ₡15,000"
# → Claude analiza: hora nocturna + viernes + Uber Eats + monto
# → Categoría: Entretenimiento (no Transporte)
```

---

## 📊 Dashboard

8 páginas organizadas:

| Página | Función |
|--------|---------|
| Setup | Crear perfil y configurar tarjetas |
| Ingresos | Gestionar fuentes de ingreso |
| Balance | Vista general del mes |
| Transacciones | Lista y edición de transacciones |
| Desglose | Gráficos por categoría |
| Merchants | Normalización de comercios |
| Chat | Consultas en lenguaje natural |
| Insights | Análisis AI de patrones |

---

## 🔒 Seguridad

- ✅ OAuth2 PKCE para Microsoft Graph
- ✅ Variables de entorno para secrets
- ✅ Validación Pydantic en todas las entradas
- ✅ Soft deletes (nunca DELETE real)
- ✅ No logging de datos sensibles

---

## 🧪 Tests

```bash
# Ejecutar tests
poetry run pytest

# Con coverage
poetry run pytest --cov=src/finanzas_tracker --cov-report=html
```

---

## 📝 Convenciones

- **Type hints obligatorios** en todo el código
- **SQLAlchemy 2.0** style (select(), Mapped)
- **Pydantic 2.0** para validación
- **Soft deletes** con `deleted_at`
- **Logging** (nunca print)
- **snake_case** para variables, **PascalCase** para clases

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para más detalles.

---

## 📄 License

MIT License - Ver [LICENSE](LICENSE)

---

<div align="center">

**Hecho con ❤️ para Costa Rica 🇨🇷**

*¿Preguntas? Abre un issue*

</div>
