# Política de Seguridad - Finanzas Email Tracker

## 🔒 Información General

Este documento describe las prácticas de seguridad implementadas en el proyecto y cómo reportar vulnerabilidades.

---

## 🛡️ Prácticas de Seguridad Implementadas

### 1. Gestión de Credenciales y Secretos

#### ✅ Variables de Entorno
Todas las credenciales sensibles se gestionan mediante variables de entorno:

```bash
# ❌ NUNCA hacer esto:
ANTHROPIC_API_KEY = "sk-ant-api03-xxxxx"  # Hardcoded en código

# ✅ SIEMPRE hacer esto:
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")  # Desde .env
```

**Credenciales manejadas:**
- Azure AD Client ID, Tenant ID, Secret
- Anthropic API Key
- Correos electrónicos de usuario

#### ✅ Almacenamiento Seguro (Keyring)
Los tokens OAuth2 se almacenan en el keyring del sistema operativo:

```python
import keyring

# Almacenamiento seguro
keyring.set_password("finanzas-tracker", "oauth_token", token)

# Recuperación
token = keyring.get_password("finanzas-tracker", "oauth_token")
```

**Beneficios:**
- ✅ No almacena tokens en archivos de texto
- ✅ Usa encriptación del OS (Keychain en macOS, Credential Manager en Windows)
- ✅ Tokens no accesibles desde otros procesos

#### ✅ .gitignore Robusto
Archivos sensibles están excluidos del control de versiones:

```gitignore
# Credentials
.env
.env.local
*.pem
*.key

# Database (puede contener datos personales)
*.db
data/

# Tokens
tokens/
.token

# Logs (pueden contener info sensible)
logs/
*.log
```

---

### 2. Validación de Entrada

#### ✅ Pydantic para Validación
Todas las configuraciones se validan automáticamente:

```python
class Settings(BaseSettings):
    azure_client_secret: str = Field(min_length=20)  # No acepta vacío
    user_email: EmailStr  # Valida formato email
    email_fetch_days_back: int = Field(ge=1, le=365)  # Rango válido

    @field_validator("azure_client_secret")
    def validate_secrets(cls, value: str) -> str:
        if not value or value.strip() == "":
            raise ValueError("Los secretos no pueden estar vacíos")
        return value
```

**Protecciones:**
- ✅ Type safety (previene inyección de tipos)
- ✅ Validación de rangos y formatos
- ✅ Error messages claros

---

### 3. Seguridad de Base de Datos

#### ✅ Prevención de SQL Injection
Uso de SQLAlchemy ORM (parametrized queries automáticas):

```python
# ✅ SEGURO - SQLAlchemy previene inyección
session.query(Transaction).filter(
    Transaction.comercio == user_input  # Parametrizado automáticamente
)

# ❌ INSEGURO - Nunca hacemos esto:
session.execute(f"SELECT * FROM transactions WHERE comercio = '{user_input}'")
```

#### ✅ Constraints de Integridad
```python
class Transaction(Base):
    email_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,  # Previene duplicados maliciosos
        index=True,
    )
```

---

### 4. Manejo de APIs Externas

#### ✅ Timeouts Configurados
Todas las llamadas HTTP tienen timeout:

```python
response = requests.get(url, timeout=10)  # 10 segundos máximo
```

**Protecciones:**
- ✅ Previene DoS por APIs lentas
- ✅ Fail fast en caso de problemas de red

#### ✅ Rate Limiting (Implícito)
- Cache de tipos de cambio (reduce llamadas a APIs)
- Batch processing de correos (evita spam a Microsoft Graph)

---

### 5. Logging Seguro

#### ✅ Sanitización de Logs
Los logs NO incluyen información sensible:

```python
# ✅ SEGURO
logger.info(f"Procesando transacción de {comercio}")

# ❌ NUNCA hacer esto:
logger.info(f"API Key: {settings.anthropic_api_key}")
logger.info(f"Password: {user_password}")
```

#### ✅ Rotación de Logs
```python
log_rotation: str = "10 MB"
log_retention: str = "1 month"
```

---

### 6. Autenticación OAuth2

#### ✅ PKCE Flow (Proof Key for Code Exchange)
Implementación segura de OAuth2 con Microsoft:

```python
# 1. Genera code_verifier y code_challenge
code_verifier = secrets.token_urlsafe(64)
code_challenge = base64.b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
)

# 2. Usa PKCE en flujo de autenticación
# Previene ataques de intercepción
```

**Protecciones:**
- ✅ Previene ataques de autorización code interception
- ✅ No requiere client_secret en cliente
- ✅ Recomendado por Microsoft para apps públicas

---

## 🚨 Reportar Vulnerabilidades

### Proceso de Reporte

Si descubres una vulnerabilidad de seguridad, por favor **NO** abras un issue público. En su lugar:

1. **Email**: Envía un correo a `security@[tu-email].com`
2. **Incluye**:
   - Descripción detallada de la vulnerabilidad
   - Pasos para reproducirla
   - Impacto potencial
   - Versión afectada
   - (Opcional) Sugerencias de mitigación

3. **Respuesta**: Recibirás respuesta en máximo 48 horas
4. **Fix**: Trabajaremos en un fix y te mantendremos informado
5. **Disclosure**: Coordinaremos divulgación pública responsable

### Bug Bounty

Actualmente **NO** tenemos programa de bug bounty, pero reconocemos públicamente las contribuciones de seguridad.

---

## 🔐 Recomendaciones para Usuarios

### Setup Seguro

1. **Nunca compartas tu archivo `.env`**
   ```bash
   # Verifica que .env está en .gitignore
   cat .gitignore | grep ".env"
   ```

2. **Usa credenciales únicas**
   - Genera un Client Secret específico para esta app
   - No reutilices API keys de otros proyectos

3. **Permisos mínimos en Azure AD**
   ```
   Solo permisos necesarios:
   - Mail.Read (leer correos)
   - Mail.ReadBasic (metadatos)

   NO dar:
   - Mail.ReadWrite.All
   - Mail.Send
   ```

4. **Revisa tokens OAuth periódicamente**
   ```bash
   # Los tokens expiran, reautentica si es necesario
   poetry run python scripts/authenticate.py
   ```

### Monitoreo de Acceso

- Revisa el [Azure AD Sign-in logs](https://portal.azure.com/#view/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/~/SignIns)
- Verifica accesos inusuales a tu cuenta de Outlook
- Habilita 2FA en tu cuenta Microsoft

---

## 📋 Checklist de Seguridad

Antes de usar en producción:

- [ ] ✅ Archivo `.env` está en `.gitignore`
- [ ] ✅ Credenciales reales NO están en código
- [ ] ✅ Azure AD app tiene solo permisos necesarios
- [ ] ✅ Base de datos `finanzas.db` está en `.gitignore`
- [ ] ✅ Logs no contienen información sensible
- [ ] ✅ API Keys son únicas (no compartidas)
- [ ] ✅ Sistema operativo está actualizado
- [ ] ✅ Python dependencies están actualizadas

---

## 🔄 Auditoría de Dependencias

### Herramientas Automáticas

Verifica vulnerabilidades en dependencias:

```bash
# Safety (escanea vulnerabilidades conocidas)
poetry run safety check

# Bandit (análisis estático de código)
poetry run bandit -r src/

# Actualizar dependencias
poetry update
```

### Dependabot

Este proyecto usa GitHub Dependabot para:
- ✅ Alertas automáticas de vulnerabilidades
- ✅ Pull requests automáticos para actualizaciones de seguridad
- ✅ Escaneo semanal de dependencias

---

## 📚 Recursos de Seguridad

### Referencias
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Microsoft Security Best Practices](https://learn.microsoft.com/en-us/security/)
- [Anthropic API Security](https://docs.anthropic.com/claude/docs/security)
- [SQLAlchemy Security](https://docs.sqlalchemy.org/en/20/core/security.html)

### Estándares Seguidos
- ✅ **OWASP Top 10** compliance
- ✅ **CWE** (Common Weakness Enumeration) awareness
- ✅ **Principle of Least Privilege** en permisos
- ✅ **Defense in Depth** (múltiples capas de seguridad)

---

## 🆕 Changelog de Seguridad

### v0.1.0 (2025-11-19)
- ✅ Implementación de OAuth2 con PKCE
- ✅ Keyring para almacenamiento de tokens
- ✅ Validación con Pydantic
- ✅ SQLAlchemy ORM (previene SQL injection)
- ✅ Timeouts en requests HTTP
- ✅ Sanitización de logs

### Mejoras Planeadas
- [ ] Agregar security headers (CSP, HSTS) si se hace web app
- [ ] Implementar rate limiting explícito
- [ ] Agregar encryption at rest para DB
- [ ] Audit logs de accesos
- [ ] 2FA opcional para dashboard

---

## ⚠️ Limitaciones Conocidas

### Fuera de Scope (Aplicación Local)
- **No hay autenticación de usuarios**: App diseñada para uso personal/familiar local
- **No hay HTTPS**: App local, no expuesta a internet
- **No hay WAF**: No es aplicación web pública

### Contexto de Uso
Este software está diseñado para:
- ✅ Uso personal/familiar
- ✅ Ejecución local (no servidor)
- ✅ Datos almacenados localmente

**NO está diseñado para:**
- ❌ Hosting como servicio web multi-tenant
- ❌ Procesamiento de datos de terceros
- ❌ Exposición a internet público

---

## 📞 Contacto

Para preguntas de seguridad:
- **Email**: [Tu email de contacto]
- **GitHub Issues**: Solo para issues no sensibles
- **GPG Key**: [Opcional] Para comunicación encriptada

---

**Última actualización**: Noviembre 2025
**Versión**: 0.1.0
