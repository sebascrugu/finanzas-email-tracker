# 📋 Próximos Pasos - Finanzas Email Tracker

Este documento describe los siguientes pasos del proyecto después del setup inicial.

## ✅ Fase 1: Setup Inicial (COMPLETADO)

- [x] Estructura del proyecto con Poetry
- [x] Configuración de Pydantic Settings
- [x] Sistema de logging con Loguru
- [x] Configuración de Ruff para linting
- [x] Tests básicos con Pytest
- [x] Documentación inicial
- [x] CI/CD con GitHub Actions

## 🔄 Fase 2: Integración con Microsoft Graph API (SIGUIENTE)

### 2.1 Configuración de Azure AD
- [ ] Registrar aplicación en Azure Portal
- [ ] Configurar permisos de API (Mail.Read, Mail.ReadWrite)
- [ ] Obtener credenciales (Client ID, Tenant ID, Secret)
- [ ] Implementar flujo OAuth 2.0 con MSAL

### 2.2 Implementar Email Fetcher
**Archivo**: `src/finanzas_tracker/services/email_fetcher.py`

```python
class EmailFetcher:
    """Servicio para extraer correos de Outlook."""
    
    def authenticate(self) -> None:
        """Autenticar con Microsoft Graph usando MSAL."""
        pass
    
    def fetch_emails(self, days_back: int = 30) -> list[dict]:
        """Obtener correos de los últimos N días."""
        pass
    
    def filter_bank_emails(self, emails: list) -> list[dict]:
        """Filtrar solo correos de bancos BAC y Banco Popular."""
        pass
```

**Pasos**:
1. Implementar autenticación con MSAL
2. Obtener correos usando Microsoft Graph SDK
3. Filtrar correos por remitente (BAC y Banco Popular)
4. Guardar correos en formato estructurado
5. Escribir tests unitarios

**Referencias**:
- [Microsoft Graph Python SDK](https://github.com/microsoftgraph/msgraph-sdk-python)
- [MSAL Python](https://github.com/AzureAD/microsoft-authentication-library-for-python)

---

## 📧 Fase 3: Parser de Correos Bancarios

### 3.1 Implementar Parsers
**Archivos**: 
- `src/finanzas_tracker/services/email_parser.py`
- `src/finanzas_tracker/services/parsers/bac_parser.py`
- `src/finanzas_tracker/services/parsers/banco_popular_parser.py`

```python
class BACParser:
    """Parser específico para correos del BAC Credomatic."""
    
    def parse_email(self, html_content: str) -> Transaction:
        """Extraer información de transacción del HTML."""
        pass
    
    def extract_amount(self, content: str) -> float:
        """Extraer monto de la transacción."""
        pass
    
    def extract_merchant(self, content: str) -> str:
        """Extraer nombre del comercio."""
        pass
```

**Información a Extraer**:
- Monto y moneda (CRC, USD)
- Fecha y hora de la transacción
- Nombre del comercio
- Ciudad y país
- Últimos 4 dígitos de tarjeta
- Tipo de tarjeta (VISA, AMEX, etc.)
- Tipo de transacción (COMPRA, RETIRO, etc.)
- Número de autorización

**Pasos**:
1. Analizar estructura HTML de correos BAC
2. Analizar estructura de correos Banco Popular
3. Implementar parser con BeautifulSoup
4. Crear regex patterns para extracción de datos
5. Validar datos extraídos con Pydantic
6. Escribir tests con correos de ejemplo

---

## 🗄️ Fase 4: Modelos de Base de Datos

### 4.1 Diseñar Esquema
**Archivo**: `src/finanzas_tracker/models/transaction.py`

```python
class Transaction(Base):
    """Modelo de transacción bancaria."""
    __tablename__ = "transactions"
    
    id: int
    email_account: str  # De qué cuenta vino (user_email o mom_email)
    bank: str  # BAC o Banco Popular
    amount: float
    currency: str
    merchant: str
    transaction_date: datetime
    card_last_digits: str
    transaction_type: str
    category: str | None  # Categoría asignada por IA
    is_confirmed: bool  # Si el usuario confirmó la transacción
    is_fraudulent: bool  # Si se marcó como fraudulenta
    notes: str | None
    raw_email_id: str  # ID del correo original
    created_at: datetime
    updated_at: datetime
```

**Tablas Adicionales**:
- `categories` - Categorías de gastos
- `email_metadata` - Metadata de correos procesados
- `user_confirmations` - Confirmaciones de usuario

**Pasos**:
1. Definir modelos SQLAlchemy
2. Crear schemas Pydantic correspondientes
3. Configurar Alembic para migraciones
4. Crear migración inicial
5. Implementar repository pattern para acceso a datos

---

## 🤖 Fase 5: Categorización con Claude AI

### 5.1 Implementar AI Classifier
**Archivo**: `src/finanzas_tracker/services/ai_classifier.py`

```python
class AIClassifier:
    """Servicio para categorizar transacciones con Claude."""
    
    def categorize_transaction(self, transaction: Transaction) -> str:
        """Categorizar una transacción usando Claude."""
        pass
    
    def detect_anomalies(self, transaction: Transaction) -> bool:
        """Detectar si una transacción es anómala."""
        pass
    
    def suggest_budget(self, transactions: list[Transaction]) -> dict:
        """Sugerir presupuesto basado en patrones."""
        pass
```

**Categorías Propuestas**:
- 🍔 Comida y Restaurantes
- 🛒 Supermercado y Alimentos
- ⛽ Gasolina y Transporte
- 💊 Salud y Farmacia
- 🎬 Entretenimiento
- 🏠 Hogar y Servicios
- 👕 Ropa y Accesorios
- 📚 Educación
- 💰 Otros

**Pasos**:
1. Diseñar prompts efectivos para Claude
2. Implementar cliente de Anthropic API
3. Crear sistema de categorización
4. Implementar detección de anomalías
5. Cachear respuestas para transacciones similares
6. Manejar rate limits de API

---

## 📊 Fase 6: Dashboard con Streamlit

### 6.1 Páginas del Dashboard

#### Página Principal
- Resumen de gastos del mes
- Gráfico de tendencias
- Alertas de transacciones sin confirmar
- Alertas de anomalías

#### Página de Transacciones
- Lista de todas las transacciones
- Filtros: fecha, banco, categoría, monto
- Búsqueda por comercio
- Confirmación de transacciones
- Edición de categorías

#### Página de Análisis
- Gráficos por categoría
- Comparación mes a mes
- Top comercios
- Distribución por banco/tarjeta

#### Página de Configuración
- Gestión de categorías personalizadas
- Configuración de alertas
- Export de datos

**Pasos**:
1. Diseñar UI con Streamlit
2. Implementar páginas principales
3. Crear gráficos con Plotly
4. Agregar funcionalidad de export (Excel, CSV)
5. Implementar sistema de confirmación de transacciones

---

## 🔄 Fase 7: Automatización

### 7.1 Script Automatizado
**Archivo**: `scripts/scheduled_fetch.py`

Opciones de automatización:

#### macOS (launchd)
Crear archivo: `~/Library/LaunchAgents/com.finanzas.emailtracker.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.finanzas.emailtracker</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/poetry</string>
        <string>run</string>
        <string>python</string>
        <string>scripts/fetch_emails.py</string>
    </array>
    <key>StartInterval</key>
    <integer>3600</integer> <!-- Cada hora -->
    <key>WorkingDirectory</key>
    <string>/Users/tu-usuario/finanzas-email-tracker</string>
</dict>
</plist>
```

**Pasos**:
1. Implementar script robusto con manejo de errores
2. Configurar logging detallado
3. Implementar reintentos en caso de fallo
4. Configurar notificaciones (opcional)
5. Documentar setup de automatización

---

## 📈 Fase 8: Mejoras y Features Adicionales

### 8.1 Features Avanzados
- [ ] Detección de suscripciones recurrentes
- [ ] Alertas de gastos inusuales
- [ ] Comparación con meses anteriores
- [ ] Predicción de gastos futuros con IA
- [ ] Reportes PDF automatizados
- [ ] Integración con estados de cuenta (OCR)
- [ ] Multi-idioma (Inglés/Español)
- [ ] Modo oscuro en dashboard

### 8.2 Optimizaciones
- [ ] Cache de resultados de Claude
- [ ] Procesamiento en batch de correos
- [ ] Compresión de base de datos antigua
- [ ] Índices de base de datos optimizados

---

## 🧪 Testing y Calidad

### Por Implementar
- [ ] Tests de integración con Microsoft Graph (mocked)
- [ ] Tests de parsers con correos reales
- [ ] Tests de categorización con Claude
- [ ] Tests E2E del dashboard
- [ ] Coverage > 80%

---

## 📚 Documentación

### Por Completar
- [ ] Guía de configuración de Azure AD paso a paso
- [ ] Documentación de API interna
- [ ] Guía de troubleshooting
- [ ] Video tutorial de setup (opcional)

---

## 🎯 Orden Recomendado de Implementación

1. **Semana 1-2**: Fase 2 - Microsoft Graph API
2. **Semana 3**: Fase 3 - Parsers de correos
3. **Semana 4**: Fase 4 - Modelos de base de datos
4. **Semana 5**: Fase 5 - Categorización con Claude
5. **Semana 6-7**: Fase 6 - Dashboard completo
6. **Semana 8**: Fase 7 - Automatización
7. **Semana 9+**: Fase 8 - Mejoras y pulido

---

## 💡 Tips para el Desarrollo

1. **Commits frecuentes**: Haz commits pequeños y descriptivos
2. **Tests primero**: Escribe tests antes de implementar features complejos
3. **Documentación**: Documenta mientras programas, no después
4. **Iteración**: No intentes hacer todo perfecto de una vez
5. **Feedback**: Prueba el dashboard regularmente con datos reales

---

## 🔗 Referencias Útiles

- [Microsoft Graph API Docs](https://learn.microsoft.com/en-us/graph/)
- [Anthropic Claude API](https://docs.anthropic.com/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [SQLAlchemy 2.0 Docs](https://docs.sqlalchemy.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

---

¡Éxito con el proyecto! 🚀


