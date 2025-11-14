# 💰 Finanzas Email Tracker

Sistema automatizado para rastrear y categorizar transacciones bancarias desde correos de Outlook usando Inteligencia Artificial.

[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Poetry](https://img.shields.io/badge/poetry-dependency%20manager-blue.svg)](https://python-poetry.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

## 📋 Descripción

Esta aplicación permite monitorear automáticamente correos electrónicos de notificaciones bancarias, extraer información de transacciones, categorizarlas inteligentemente usando Claude AI, y visualizarlas en un dashboard interactivo con Streamlit.

**🏦 Bancos Soportados Actualmente:**
- ✅ BAC Credomatic (Costa Rica)
- ✅ Banco Popular de Costa Rica
- 📧 Solo Outlook/Microsoft 365

**🔜 Próximamente:** Se planea agregar soporte para más bancos y proveedores de correo.

> **🚀 Quick Start**: Si ya sabes lo que haces, ve directo a [QUICKSTART.md](QUICKSTART.md)

### ✨ Características Principales

- 📧 **Extracción Automática de Correos**: Conexión con Microsoft Graph API para leer correos de Outlook/Microsoft 365
- 🏦 **Multi-Banco**: BAC Credomatic y Banco Popular (Costa Rica) — más bancos próximamente
- 🤖 **Categorización Inteligente con IA**: Usa Claude 3.5 Haiku para clasificar gastos automáticamente
- 🧠 **Sistema de Aprendizaje**: Aprende de tus decisiones para mejorar la categorización
- 💰 **Gestión de Ingresos**: Trackea salarios, ventas, freelance y más (recurrentes o únicos)
- 📊 **Balance Mensual**: Ve ingresos vs gastos y tu salud financiera en tiempo real
- 💱 **Conversión de Divisas**: USD→CRC automática con tipos de cambio históricos reales (API Hacienda CR)
- 🔍 **Detección de Patrones**: Identifica transacciones recurrentes y sugiere categorías automáticamente
- 🎯 **Transacciones Especiales**: Maneja transferencias intermediarias, gastos compartidos, ayudas familiares
- 📈 **Dashboard Interactivo**: Visualización con Streamlit para revisar y confirmar transacciones
- 🔒 **Seguridad**: Manejo seguro de credenciales con variables de entorno
- 💾 **Base de Datos Robusta**: SQLite con soft deletes, constraints y índices optimizados
- 👥 **Multi-Usuario**: Soporte para múltiples cuentas y presupuestos

## 🛠️ Stack Tecnológico

- **Lenguaje**: Python 3.11+
- **Gestión de Dependencias**: Poetry
- **ORM**: SQLAlchemy 2.0 + Alembic
- **Validación**: Pydantic 2.0
- **API de Correos**: Microsoft Graph API (MSAL)
- **IA**: Anthropic Claude API
- **Dashboard**: Streamlit
- **Logging**: Loguru
- **Linting**: Ruff
- **Testing**: Pytest

## 📦 Requisitos Previos

- Python 3.11 o superior
- Poetry instalado ([Instrucciones de instalación](https://python-poetry.org/docs/#installation))
- Cuenta de **Outlook/Microsoft 365** (actualmente el único proveedor de correo soportado)
- Cuenta bancaria en **BAC Credomatic** o **Banco Popular** de Costa Rica
- API Key de Anthropic Claude
- Credenciales de Azure AD (para Microsoft Graph API)

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/sebastiancruz/finanzas-email-tracker.git
cd finanzas-email-tracker
```

### 2. Instalar dependencias con Poetry

```bash
# Instalar Poetry si no lo tienes
curl -sSL https://install.python-poetry.org | python3 -

# Instalar dependencias del proyecto
poetry install
```

### 3. Configurar variables de entorno

```bash
# Copiar el archivo de ejemplo
cp .env.example .env

# Editar .env con tus credenciales
nano .env
```

### 4. Configurar Azure AD para Microsoft Graph API

1. Ve a [Azure Portal](https://portal.azure.com/)
2. Registra una nueva aplicación en Azure AD
3. Configura los permisos API:
   - `Mail.Read` - Leer correos del usuario
   - `Mail.ReadWrite` - Leer y marcar correos (opcional)
4. Genera un Client Secret
5. Copia `Client ID`, `Tenant ID` y `Client Secret` al archivo `.env`

### 5. Obtener API Key de Anthropic

1. Ve a [Anthropic Console](https://console.anthropic.com/)
2. Crea una cuenta o inicia sesión
3. Genera una API Key
4. Copia la API Key al archivo `.env`

### 6. Inicializar la base de datos

```bash
# Crear las carpetas necesarias
mkdir -p data logs

# Ejecutar migraciones (cuando estén disponibles)
poetry run alembic upgrade head
```

## 💻 Uso

### Configuración Inicial

```bash
# 1. Configurar usuario en la base de datos
make setup-user

# 2. Poblar categorías iniciales
make seed
```

### Procesamiento de Transacciones

```bash
# Procesar correos y extraer transacciones (con categorización IA)
make process

# Revisar y confirmar transacciones categorizadas
make review
```

### Gestión de Ingresos 💰

```bash
# Ver balance rápido del mes (ingresos vs gastos)
make balance

# Gestión completa de ingresos (menú interactivo)
make income
#   1. Ver balance mensual detallado
#   2. Listar todos mis ingresos
#   3. Agregar nuevo ingreso (salario, venta, freelance, etc.)
```

> 📚 **Guía completa**: Ver [GUIA_INGRESOS.md](GUIA_INGRESOS.md) para instrucciones detalladas

### Dashboard Interactivo (Próximamente)

```bash
# Ejecutar dashboard Streamlit
make dashboard
```

### Testing y Calidad de Código

```bash
# Ejecutar todos los tests
make test

# Ver cobertura de código
make coverage

# Linting y formateo
make lint
make format
```

### Otros Comandos Útiles

```bash
# Ver todos los comandos disponibles
make help

# Cerrar sesión de Microsoft
make logout

# Limpiar cache y archivos temporales
make clean
```

## 📁 Estructura del Proyecto

```
finanzas-email-tracker/
├── src/
│   └── finanzas_tracker/
│       ├── config/                    # Configuración y settings
│       │   └── settings.py           # Variables de entorno con Pydantic
│       ├── core/                      # Funcionalidades core
│       │   ├── database.py           # SQLAlchemy setup y sesiones
│       │   └── logging.py            # Configuración de Loguru
│       ├── models/                    # Modelos SQLAlchemy
│       │   ├── user.py               # Usuario multi-cuenta
│       │   ├── budget.py             # Presupuestos con historial
│       │   ├── category.py           # Categorías y subcategorías
│       │   ├── card.py               # Tarjetas débito/crédito
│       │   ├── income.py             # Ingresos (salarios, ventas, etc.)
│       │   ├── transaction.py        # Transacciones bancarias
│       │   └── enums.py              # Enumeraciones tipo-seguras
│       ├── services/                  # Lógica de negocio
│       │   ├── auth_manager.py       # Autenticación Microsoft Graph
│       │   ├── email_fetcher.py      # Extracción de correos
│       │   ├── transaction_processor.py  # Procesamiento de transacciones
│       │   ├── exchange_rate.py      # Conversión USD->CRC
│       │   └── categorizer.py        # Categorización con Claude AI
│       ├── parsers/                   # Parsers de correos HTML
│       │   ├── bac_parser.py         # Parser para BAC Credomatic
│       │   └── popular_parser.py     # Parser para Banco Popular
│       ├── utils/                     # Utilidades
│       │   └── seed_categories.py    # Seed de categorías iniciales
│       └── dashboard/                 # Dashboard Streamlit (WIP)
├── scripts/                           # Scripts ejecutables
│   ├── setup_user.py                 # Configuración inicial de usuario
│   ├── process_transactions.py       # Procesamiento de correos
│   ├── review_transactions.py        # Revisión interactiva con detección de patrones
│   ├── manage_income.py              # Gestión de ingresos (menú completo)
│   ├── quick_balance.py              # Balance rápido del mes
│   └── migrate_db.py                 # Migración de schema de BD
├── tests/                             # Tests unitarios e integración
├── data/                              # Base de datos SQLite (gitignored)
├── logs/                              # Archivos de log (gitignored)
├── .env.example                       # Template de configuración
├── .gitignore                         # Archivos ignorados
├── Makefile                           # Comandos útiles
├── pyproject.toml                     # Configuración Poetry
├── ruff.toml                          # Configuración Ruff
├── LICENSE                            # Licencia MIT
├── QUICKSTART.md                      # Guía rápida de inicio
├── GUIA_INGRESOS.md                   # Guía completa de gestión de ingresos
├── CATEGORIAS_SUGERIDAS.md            # Documentación de categorías
└── README.md                          # Este archivo
```

## 🔐 Seguridad

- **NUNCA** compartas tu archivo `.env` — contiene credenciales sensibles
- **NUNCA** subas credenciales a Git
- Las API Keys están protegidas con variables de entorno
- La base de datos SQLite es local y no se sincroniza
- Solo tú tienes acceso a tus datos bancarios
- La aplicación funciona 100% en tu computadora local

## 🏦 Bancos y Proveedores Soportados

### 📧 Proveedores de Correo
- ✅ **Outlook/Microsoft 365** (mediante Microsoft Graph API)
- 🔜 Gmail (planificado)
- 🔜 Otros proveedores (a petición)

### 🏦 Bancos (Costa Rica)

**BAC Credomatic**
- ✅ Notificaciones de transacciones
- ✅ Tarjetas de crédito y débito
- ✅ Transferencias y SINPE
- ✅ Retiros sin tarjeta
- ✅ Extracción de: monto, fecha, comercio, número de tarjeta

**Banco Popular**
- ✅ Notificaciones de transacciones
- ✅ Tarjetas de crédito y débito
- ✅ Extracción de: monto, fecha, comercio, número de tarjeta

### 🔜 Próximamente
- Más bancos de Costa Rica (Scotiabank, BCR, etc.)
- Bancos de otros países latinoamericanos
- Soporte para Gmail y otros proveedores de correo
- Parsing de estados de cuenta PDF

## 🤝 Contribuciones

Este es un proyecto personal, pero las sugerencias y mejoras son bienvenidas. Si encuentras un bug o tienes una idea:

1. Abre un Issue describiendo el problema o sugerencia
2. Si quieres contribuir código, abre un Pull Request

## 📝 Roadmap

- [x] Setup inicial del proyecto
- [x] Implementar extracción de correos con Microsoft Graph
- [x] Parser de correos para BAC y Banco Popular
- [x] Integración con Claude para categorización inteligente
- [x] Sistema de confirmación de transacciones con IA
- [x] Multi-usuario y multi-presupuestos
- [x] Categorías y subcategorías granulares
- [x] Conversión automática de USD a CRC con tipos de cambio históricos (API Hacienda CR)
- [x] Gestión de tarjetas (débito/crédito) con límites y fechas de corte
- [x] Sistema de aprendizaje de categorización
- [x] Gestión completa de ingresos (salarios, ventas, freelance)
- [x] Ingresos recurrentes (quincenales, mensuales)
- [x] Balance mensual (ingresos vs gastos)
- [x] Detección de patrones en transacciones
- [x] Manejo de transferencias intermediarias y gastos compartidos
- [x] Soft deletes y constraints de BD robustos
- [ ] Dashboard interactivo con Streamlit
- [ ] Parsing de estados de cuenta (PDF)
- [ ] Reconciliación de correos vs estados de cuenta
- [ ] Reportes mensuales y comparativos
- [ ] Exportación a Excel/PDF
- [ ] Detección de anomalías y alertas predictivas (ML)
- [ ] Gestión de compras a cuotas (tasa cero)
- [ ] Tracking de cashback y puntos
- [ ] Soporte para más bancos (a petición)

## 📄 Licencia

Este proyecto es de código abierto y está disponible bajo la licencia MIT.

## 👤 Autor

**Sebastian Cruz**  
Ingeniero en Computación | Costa Rica 🇨🇷

## 💡 Motivación

Este proyecto nace de la necesidad de tener un control real y automatizado de finanzas personales en Costa Rica, donde la mayoría de soluciones disponibles son:
- 🚫 De otros países (no soportan bancos locales)
- 🚫 Requieren acceso bancario directo (inseguro)
- 🚫 Son de pago y costosas
- 🚫 No usan IA para categorización inteligente

**Finanzas Email Tracker** es 100% local, seguro, gratuito (excepto API de Claude) y diseñado específicamente para el contexto costarricense.

## 🙏 Agradecimientos

- Microsoft Graph API por facilitar el acceso a correos
- Anthropic por Claude API
- La comunidad de Python y open source

---

**Nota**: Esta aplicación es para uso personal y educativo. No me hago responsable del uso indebido de credenciales o datos bancarios.


