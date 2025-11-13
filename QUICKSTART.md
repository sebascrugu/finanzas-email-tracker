# 🚀 Guía de Inicio Rápido

Esta guía te ayudará a poner en marcha el proyecto en **menos de 10 minutos**.

## ✅ Pre-requisitos

- ✅ Python 3.11+ instalado
- ✅ Poetry instalado ([instalación](https://python-poetry.org/docs/#installation))
- ✅ Cuenta de **Outlook/Microsoft 365** (único proveedor soportado actualmente)
- ✅ Cuenta en **BAC Credomatic** o **Banco Popular** de Costa Rica
- ✅ Credenciales de Azure AD (instrucciones abajo)
- ✅ API Key de Anthropic Claude (instrucciones abajo)

> **📌 Nota:** Actualmente solo se soportan Outlook y los bancos mencionados. Se planea agregar más en el futuro.

## 📦 Paso 1: Instalar Poetry (si no lo tienes)

```bash
# macOS/Linux
curl -sSL https://install.python-poetry.org | python3 -

# Verificar instalación
poetry --version
```

## 🔧 Paso 2: Configurar el Proyecto

```bash
# Clonar el repositorio
git clone https://github.com/sebastiancruz/finanzas-email-tracker.git
cd finanzas-email-tracker

# Instalar dependencias
poetry install
```

## 🔑 Paso 3: Configurar Variables de Entorno

```bash
# Copiar el archivo de ejemplo
cp .env.example .env

# Editar con tu editor favorito
nano .env
# o
code .env
```

Necesitas configurar:
- Azure AD credentials (Client ID, Tenant ID, Secret)
- Tu correo de Outlook/Microsoft 365 (y opcionalmente más usuarios)
- API Key de Anthropic Claude

### 🔵 Obtener Credenciales de Azure AD

1. Ve a https://portal.azure.com/
2. Busca "Azure Active Directory" o "Entra ID"
3. Ve a "App registrations" → "New registration"
4. Nombre: `Finanzas Email Tracker`
5. Supported account types: "Accounts in this organizational directory only"
6. Redirect URI: `http://localhost:8501`
7. Click "Register"

Una vez registrada:
- Copia el **Application (client) ID** → `AZURE_CLIENT_ID`
- Copia el **Directory (tenant) ID** → `AZURE_TENANT_ID`
- Ve a "Certificates & secrets" → "New client secret"
- Copia el **Value** → `AZURE_CLIENT_SECRET`

Permisos necesarios:
- Ve a "API permissions"
- "Add a permission" → "Microsoft Graph" → "Delegated permissions"
- Agregar: `Mail.Read` y `Mail.ReadWrite`
- Click "Grant admin consent"

### 🤖 Obtener API Key de Claude

1. Ve a https://console.anthropic.com/
2. Crea una cuenta o inicia sesión
3. Ve a "API Keys"
4. "Create Key"
5. Copia la key → `ANTHROPIC_API_KEY`

## ✅ Paso 4: Verificar Instalación

```bash
# Verificar que no hay errores de linting
make lint

# Ejecutar tests (algunos fallarán hasta configurar credenciales reales)
make test

# Ver comandos disponibles
make help
```

## 🎯 Paso 5: Configurar Usuario y Categorías

```bash
# 1. Crear usuario en la base de datos
make setup-user

# 2. Poblar categorías iniciales (Necesidades/Gustos/Ahorros)
make seed
```

## 📧 Paso 6: Procesar Transacciones

```bash
# Extraer correos, parsear y categorizar con IA
make process

# Revisar y confirmar categorías sugeridas
make review
```

## 📊 Paso 7: Dashboard (Próximamente)

```bash
# Dashboard interactivo con Streamlit (Work in Progress)
make dashboard
```

## 🛠️ Comandos Útiles

```bash
# Flujo de trabajo principal
make setup-user           # Configurar usuario inicial
make seed                 # Poblar categorías
make process              # Procesar correos y categorizar
make review               # Revisar transacciones pendientes

# Testing y calidad
make test                 # Ejecutar tests
make coverage             # Tests con cobertura
make lint                 # Verificar código
make format               # Formatear automáticamente

# Utilidades
make logout               # Cerrar sesión de Microsoft
make clean                # Limpiar archivos temporales
make help                 # Ver todos los comandos
```

## 📂 Estructura del Proyecto

```
finanzas-email-tracker/
├── src/finanzas_tracker/    # Código fuente principal
│   ├── config/              # Configuración (settings.py)
│   ├── core/                # Funcionalidades core
│   ├── models/              # Modelos de BD
│   ├── schemas/             # Schemas Pydantic
│   ├── services/            # Lógica de negocio
│   ├── repositories/        # Acceso a datos
│   └── dashboard/           # Dashboard Streamlit
├── tests/                   # Tests
├── scripts/                 # Scripts ejecutables
├── data/                    # Base de datos SQLite
└── logs/                    # Archivos de log
```

## 🐛 Troubleshooting

### Error: "Poetry not found"
```bash
# Agregar Poetry al PATH
export PATH="$HOME/.local/bin:$PATH"
# Agregar a ~/.zshrc o ~/.bashrc para hacerlo permanente
```

### Error: "Python version not found"
```bash
# Instalar Python 3.11 con Homebrew (macOS)
brew install python@3.11

# O usar pyenv
pyenv install 3.11.0
pyenv local 3.11.0
```

### Error al conectar con Microsoft Graph
- Verifica que las credenciales en `.env` sean correctas
- Asegúrate de haber dado consent a los permisos en Azure Portal
- Verifica que el Redirect URI coincida: `http://localhost:8501`

### Error con Claude API
- Verifica que tu API Key sea válida
- Revisa que tengas créditos disponibles en Anthropic
- Verifica límites de rate limit

## 📚 Próximos Pasos

1. ✅ Setup completado
2. 🔐 Configurar `.env` con credenciales
3. 👤 Ejecutar `make setup-user`
4. 🏷️ Ejecutar `make seed`
5. 📧 Ejecutar `make process`
6. ✅ Ejecutar `make review`
7. 📊 Esperar dashboard (próximamente)

## 🐛 Troubleshooting Común

### "No module named 'finanzas_tracker'"
```bash
# Asegúrate de estar en el entorno de Poetry
poetry shell
# O ejecuta con poetry run
poetry run python scripts/process_transactions.py
```

### "Anthropic API error: credit balance too low"
- Ve a https://console.anthropic.com/
- Agrega créditos a tu cuenta
- Verifica que tu API key sea válida

### "No se puede obtener token de acceso"
- Verifica credenciales Azure AD en `.env`
- Confirma que diste consent a permisos en Azure Portal
- Ejecuta `make logout` y vuelve a intentar

## 🆘 Ayuda

- **Issues**: [GitHub Issues](https://github.com/sebastiancruz/finanzas-email-tracker/issues)
- **Documentación**: `README.md` completo
- **Logs**: Revisa `logs/` para debugging detallado

## 🎉 ¡Listo!

Ya tienes el proyecto configurado y funcionando. 

**Estado actual (Nov 2025)**:
- ✅ Extracción de correos con Microsoft Graph
- ✅ Parsing de BAC y Banco Popular
- ✅ Categorización inteligente con Claude AI
- ✅ Sistema de aprendizaje
- ✅ Conversión USD→CRC automática
- 🚧 Dashboard interactivo (en desarrollo)
- 🚧 Parsing de PDFs (planificado)

---

¿Preguntas? Abre un issue en GitHub.


