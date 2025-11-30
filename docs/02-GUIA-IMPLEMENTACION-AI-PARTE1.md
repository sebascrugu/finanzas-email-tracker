# Prompts Fases 3-6: RAG, MCP, Parsers, Deploy

---

## Archivo: docs/prompts/phase-3-rag.md

```markdown
# Fase 3: RAG con pgvector
## Prompts para AI Assistants

### Contexto de la Fase
```
Fase 3: Implementar búsqueda semántica y RAG usando pgvector.

Pre-requisitos:
- API REST funcionando
- pgvector configurado
- Columna embedding en transactions

Objetivo:
- Usuarios pueden hacer preguntas en lenguaje natural
- Sistema busca transacciones relevantes
- Claude genera respuestas basadas en datos reales
```

---

### Tarea 3.1: Servicio de Embeddings

**Prompt:**
```
Necesito crear un servicio para generar y gestionar embeddings de transacciones.

Requisitos:
1. Usar sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
2. Generar embeddings al crear/actualizar transacciones
3. Función para generar embedding de query (para búsqueda)
4. Batch processing para transacciones existentes

Contexto de cada transacción para embedding:
- Crear texto enriquecido que incluya: tipo (gasto/ingreso), monto,
  descripción, categoría, fecha, comercio, notas del usuario
- El texto debe ser en español para mejor matching

Por favor genera:
1. src/services/embedding_service.py
2. Función create_embedding(transaction) -> vector
3. Función create_query_embedding(question) -> vector
4. Función batch_embed_transactions(transactions) -> None
5. Tests básicos

Consideraciones:
- El modelo se carga una vez y se reutiliza
- Manejar transacciones sin categoría
- Loggear tiempo de generación
```

---

### Tarea 3.2: Búsqueda Semántica con pgvector

**Prompt:**
```
Necesito implementar búsqueda semántica usando pgvector.

Embedding service: [pegar código]
Tabla transactions con columna embedding: [pegar schema]

Requisitos:
1. Función search_similar_transactions(query, n=20, filters=None)
2. Filtros opcionales: fecha, categoría, monto mínimo/máximo
3. Usar distancia coseno (<=> operator en pgvector)
4. Retornar transacciones ordenadas por relevancia

Query SQL de referencia:
```sql
SELECT *, embedding <=> '[query_vector]' as distance
FROM transactions
WHERE deleted_at IS NULL
  AND tenant_id = :tenant_id  -- cuando aplique
ORDER BY embedding <=> '[query_vector]'
LIMIT :n
```

Por favor genera:
1. Función en TransactionService o nuevo SemanticSearchService
2. Manejo de caso cuando no hay embeddings
3. Test con query de ejemplo

Consideraciones:
- Si filtros reducen mucho los resultados, ajustar n
- Incluir score de similaridad en respuesta
- Threshold mínimo de similaridad (ej: 0.7)
```

---

### Tarea 3.3: RAG Chain Completo

**Prompt:**
```
Necesito implementar el pipeline RAG completo para preguntas financieras.

Services disponibles:
- EmbeddingService: [pegar]
- SemanticSearchService: [pegar]
- AnalyticsService: [pegar]

Pipeline RAG:
1. Recibir pregunta del usuario
2. Generar embedding de la pregunta
3. Buscar transacciones relevantes (top 20)
4. Obtener estadísticas contextuales:
   - Estado actual del presupuesto
   - Promedios históricos relevantes
   - Anomalías si la pregunta las menciona
5. Construir prompt con todo el contexto
6. Enviar a Claude y obtener respuesta
7. Retornar respuesta con sources

Por favor genera:
1. src/services/rag_service.py con clase RAGService
2. Método query(question: str) -> RAGResponse
3. Prompt template optimizado para finanzas en español
4. Manejo de casos:
   - Pregunta sin datos suficientes
   - Pregunta fuera de scope
   - Error de Claude
5. Schema RAGResponse con respuesta y sources

System prompt sugerido para Claude:
"Eres un asistente financiero personal para Costa Rica.
Responde basándote ÚNICAMENTE en los datos proporcionados.
Usa colones (₡) para montos. Sé específico con fechas y montos.
Si no hay datos suficientes, indícalo claramente.
Da recomendaciones prácticas cuando sea apropiado."
```

---

### Tarea 3.4: Endpoint de Chat AI

**Prompt:**
```
Necesito crear el endpoint /ai/chat para el RAG.

RAGService: [pegar código]

Requisitos:
1. POST /api/v1/ai/chat
2. Request: { "message": "¿por qué gasté tanto en marzo?" }
3. Response: { "response": "...", "sources": [...] }
4. Sources incluye transacciones usadas para la respuesta
5. Streaming opcional (para respuestas largas)

Consideraciones:
- Rate limiting (ej: 10 requests/minuto por user)
- Timeout de 30 segundos
- Loggear preguntas para análisis (sin PII)
- Cachear respuestas idénticas por 5 minutos

Por favor genera:
1. src/api/v1/endpoints/ai.py
2. Schemas de request/response
3. Test de integración
```

---

### Tarea 3.5: Script de Backfill de Embeddings

**Prompt:**
```
Necesito un script para generar embeddings de transacciones existentes.

EmbeddingService: [pegar código]

Requisitos:
1. Script CLI ejecutable: python -m scripts.backfill_embeddings
2. Procesar transacciones sin embedding en batches de 100
3. Mostrar progreso con barra
4. Guardar checkpoint por si se interrumpe
5. Modo --dry-run para verificar sin modificar

Por favor genera:
1. scripts/backfill_embeddings.py
2. Manejo de errores por transacción (no fallar todo el batch)
3. Logging de estadísticas al final
4. Estimación de tiempo restante
```

---

### Tarea 3.6: Tests de RAG

**Prompt:**
```
Necesito tests exhaustivos para el sistema RAG.

Componentes a testear:
1. EmbeddingService
2. Búsqueda semántica
3. RAGService
4. Endpoint /ai/chat

Preguntas de prueba (deben funcionar correctamente):
1. "¿Cuánto gasté en restaurantes este mes?"
2. "¿Por qué gasté tanto en noviembre?"
3. "¿Cuáles son mis gastos recurrentes?"
4. "¿Estoy dentro de mi presupuesto de alimentación?"
5. "Compara mis gastos de octubre vs noviembre"

Por favor genera:
1. tests/unit/test_embedding_service.py
2. tests/unit/test_rag_service.py
3. tests/integration/test_ai_chat.py
4. Fixtures con transacciones que permitan responder las preguntas

Usar mocks para Claude API en unit tests.
```

---

### Verificación de Fase 3

**Prompt:**
```
Verifica que la Fase 3 está completa:

1. [ ] EmbeddingService genera embeddings correctamente
2. [ ] Transacciones tienen embeddings (verificar % con NULL)
3. [ ] Búsqueda semántica retorna resultados relevantes
4. [ ] RAGService genera respuestas coherentes
5. [ ] Endpoint /ai/chat funciona
6. [ ] Respuestas incluyen sources
7. [ ] Latencia < 3 segundos
8. [ ] Tests pasan
9. [ ] Script de backfill ejecutado
10. [ ] Las 5 preguntas de prueba se responden correctamente

Ejecuta verificaciones y reporta resultados.
```
```

---

## Archivo: docs/prompts/phase-4-mcp.md

```markdown
# Fase 4: MCP Server Diferenciado
## Prompts para AI Assistants

### Contexto de la Fase
```
Fase 4: Crear MCP Server que va más allá de CRUD básico.

IMPORTANTE: Actual Budget ya tiene MCP con CRUD básico.
Nuestro diferenciador es: coaching inteligente + predicciones + Costa Rica.

Pre-requisitos:
- API REST funcionando
- RAG funcionando

Tools a implementar:
- Nivel 1: CRUD (como Actual Budget)
- Nivel 2: Análisis (anomalías, suscripciones)
- Nivel 3: Coaching (predicciones, recomendaciones) ← DIFERENCIADOR
```

---

### Tarea 4.1: Estructura Base MCP

**Prompt:**
```
Necesito crear la estructura base del MCP Server usando FastMCP.

Requisitos:
1. Servidor MCP que se conecta a la API REST
2. Configuración para Claude Desktop
3. Manejo de errores robusto
4. Logging de todas las operaciones

Estructura:
```
src/mcp/
├── __init__.py
├── server.py          # MCP Server principal
├── tools/
│   ├── __init__.py
│   ├── crud.py        # Nivel 1: CRUD
│   ├── analysis.py    # Nivel 2: Análisis
│   └── coaching.py    # Nivel 3: Coaching
└── config.py          # Configuración
```

Por favor genera:
1. src/mcp/server.py con estructura base
2. src/mcp/config.py con configuración
3. Ejemplo de un tool simple (get_transactions)
4. Instrucciones de configuración para Claude Desktop

El server debe llamar a la API REST, no a la DB directamente.
```

---

### Tarea 4.2: Tools Nivel 1 (CRUD)

**Prompt:**
```
Necesito implementar tools MCP de CRUD básico.

API endpoints disponibles: [listar endpoints]

Tools requeridos:

1. get_transactions
   - Filtros: start_date, end_date, category, min_amount, max_amount, limit
   - Retorna lista de transacciones

2. get_transaction_detail
   - Parámetro: transaction_id
   - Retorna transacción con todos los detalles

3. create_transaction
   - Parámetros: amount, description, date, category (opcional)
   - Crea y retorna transacción

4. categorize_transaction
   - Parámetros: transaction_id, category_id
   - Actualiza categoría

5. get_categories
   - Sin parámetros
   - Retorna lista de categorías con estadísticas

Por favor genera src/mcp/tools/crud.py con todos los tools.
Incluir documentación clara para que Claude entienda cuándo usar cada uno.
```

---

### Tarea 4.3: Tools Nivel 2 (Análisis)

**Prompt:**
```
Necesito implementar tools MCP de análisis.

Tools requeridos:

1. analyze_spending
   - Usa RAG para responder preguntas sobre gastos
   - Parámetro: question (string)
   - Retorna análisis detallado

2. detect_anomalies
   - Sin parámetros o sensitivity opcional
   - Retorna transacciones sospechosas

3. find_subscriptions
   - Sin parámetros
   - Retorna gastos recurrentes detectados

4. compare_periods
   - Parámetros: period1 (YYYY-MM), period2 (YYYY-MM)
   - Retorna comparativa de gastos

5. get_spending_trends
   - Parámetro: months (default 6)
   - Retorna tendencias de ingresos/gastos

Por favor genera src/mcp/tools/analysis.py
```

---

### Tarea 4.4: Tools Nivel 3 (Coaching) - EL DIFERENCIADOR

**Prompt:**
```
Necesito implementar tools MCP de coaching inteligente.
ESTOS SON LOS DIFERENCIADORES vs otros MCP servers de finanzas.

Tools requeridos:

1. budget_coaching
   Propósito: Analiza patrones y da recomendaciones personalizadas
   Output: Recomendaciones específicas basadas en datos
   Ejemplo:
   "Tu gasto en restaurantes aumentó 40% este mes. Basado en tu historial,
   esto suele pasar cuando trabajás desde casa (detecté más Uber Eats).
   Sugerencia: Preparar almuerzos podría ahorrarte ₡25,000/mes."

2. goal_advisor
   Propósito: Ayuda a alcanzar metas de ahorro
   Parámetros: goal_amount, deadline
   Output: Plan de ahorro con acciones específicas
   Ejemplo:
   "Para ahorrar ₡500,000 en 6 meses necesitás ₡83,333/mes.
   Tu promedio de ahorro actual es ₡45,000/mes.
   Para cerrar la brecha de ₡38,333, podés:
   - Reducir Uber Eats de ₡40,000 a ₡20,000
   - Cancelar Spotify (sin uso en 45 días): ₡5,000
   - Cocinar 2 veces más por semana: ₡15,000"

3. cashflow_prediction
   Propósito: Predice si alcanza el dinero para fin de mes
   Output: Predicción con nivel de confianza y alertas
   Ejemplo:
   "Proyección a fin de mes:
   - Ingresos restantes: ₡0 (ya recibiste salario)
   - Gastos proyectados: ₡180,000 (basado en patrón)
   - Balance actual: ₡250,000
   - Balance proyectado: ₡70,000 ✓
   
   Alerta: Tienes pago de tarjeta (₡50,000) el día 15.
   Balance después del pago: ₡20,000 ⚠️"

4. spending_alert
   Propósito: Identifica gastos problemáticos proactivamente
   Output: Alertas priorizadas con acciones sugeridas
   
5. savings_opportunities
   Propósito: Encuentra dónde se puede ahorrar
   Output: Lista priorizada de oportunidades con impacto

Por favor genera src/mcp/tools/coaching.py

IMPORTANTE: Estos tools deben usar RAG + analytics + lógica propia
para generar insights que un CRUD básico nunca podría dar.
```

---

### Tarea 4.5: Resources MCP

**Prompt:**
```
Necesito implementar Resources MCP para reportes.

Resources requeridos:

1. monthly_report/{year}/{month}
   - Reporte mensual completo en Markdown
   - Incluye: resumen, gastos por categoría, comparativa, recomendaciones

2. budget_summary
   - Estado actual del presupuesto 50/30/20
   - Dinámico (siempre actual)

3. category_breakdown/{period}
   - period: week/month/year
   - Desglose detallado por categoría

Por favor genera la implementación de resources en src/mcp/server.py
```

---

### Tarea 4.6: Configuración Claude Desktop

**Prompt:**
```
Necesito crear documentación completa para configurar el MCP Server con Claude Desktop.

Generar:
1. README de instalación paso a paso
2. Archivo de configuración de ejemplo para Claude Desktop
3. Troubleshooting de problemas comunes
4. Video script para demo de 3 minutos

Configuración de Claude Desktop (macOS):
~/Library/Application Support/Claude/claude_desktop_config.json

Configuración de Claude Desktop (Windows):
%APPDATA%\Claude\claude_desktop_config.json

El MCP server necesita:
- Python 3.11+
- Dependencias instaladas
- API corriendo en localhost:8000
- Variables de entorno configuradas
```

---

### Tarea 4.7: Tests de MCP

**Prompt:**
```
Necesito tests para el MCP Server.

Testear:
1. Cada tool de CRUD funciona
2. Cada tool de análisis funciona
3. Cada tool de coaching genera output útil
4. Resources retornan formato correcto
5. Manejo de errores (API caída, timeout, datos inválidos)

Por favor genera:
1. tests/unit/test_mcp_tools.py
2. tests/integration/test_mcp_server.py

Los tests deben mockear la API REST.
```

---

### Verificación de Fase 4

**Prompt:**
```
Verifica que la Fase 4 está completa:

1. [ ] MCP Server arranca sin errores
2. [ ] Tools Nivel 1 (CRUD) funcionan en Claude Desktop
3. [ ] Tools Nivel 2 (Análisis) funcionan
4. [ ] Tools Nivel 3 (Coaching) generan insights útiles
5. [ ] Resources retornan reportes formateados
6. [ ] Configuración Claude Desktop documentada
7. [ ] Video demo de 3 minutos grabado
8. [ ] Tests pasan
9. [ ] El coaching es claramente mejor que CRUD básico
10. [ ] Conversación de ejemplo funciona end-to-end

Probar esta conversación:
1. "¿Cómo van mis finanzas?"
2. "¿Por qué gasté tanto en restaurantes?"
3. "¿Cómo puedo ahorrar más?"
4. "¿Llegaré a fin de mes?"
5. "Anotar: hoy gasté 10 mil en almuerzo"
```
```

---

## Archivo: docs/prompts/phase-5-parsers.md

```markdown
# Fase 5: Parsing SINPE + Bancos CR
## Prompts para AI Assistants

### Contexto de la Fase
```
Fase 5: Implementar parsers para integración con bancos costarricenses.

Sin APIs bancarias, parsing es la única opción viable.

Fuentes a parsear:
1. SMS de SINPE Móvil
2. Emails de notificación BAC Credomatic
3. PDFs de estados de cuenta BAC
4. Emails de Banco Popular (si es posible)
```

---

### Tarea 5.1: Clase Base de Parsers

**Prompt:**
```
Necesito crear una clase base abstracta para parsers de bancos.

Requisitos:
1. Interface consistente para todos los parsers
2. Métodos abstractos para parsing de diferentes formatos
3. Validación de output
4. Logging de errores

Estructura:
```
src/parsers/
├── __init__.py
├── base.py              # Clase base abstracta
├── detector.py          # Detecta qué parser usar
├── sinpe/
│   └── sms_parser.py
├── bac/
│   ├── email_parser.py
│   └── pdf_parser.py
└── popular/
    └── email_parser.py
```

Output estándar de parsing:
```python
@dataclass
class ParsedTransaction:
    amount: Decimal
    currency: str  # CRC, USD
    description: str
    date: datetime
    type: str  # debit, credit
    source: str  # sinpe_sms, bac_email, bac_pdf
    raw_text: str  # Texto original
    confidence: float  # 0-1
    metadata: dict  # Datos adicionales específicos del banco
```

Por favor genera:
1. src/parsers/base.py con BaseParser
2. src/parsers/models.py con ParsedTransaction
3. src/parsers/detector.py que detecta el formato
```

---

### Tarea 5.2: Parser de SMS SINPE Móvil

**Prompt:**
```
Necesito parser para SMS de SINPE Móvil.

Formatos conocidos (ejemplos reales sanitizados):

Recepción:
"Ha recibido 15,000.00 Colones de MARIA PEREZ GONZALEZ por SINPE Movil, ALMUERZO. Comprobante 123456789"

Envío:
"Envio exitoso de 10,000.00 Colones a JUAN RODRIGUEZ MORA por SINPE Movil. Comprobante 987654321"

Variaciones:
- Con o sin descripción
- Diferentes bancos pueden variar ligeramente el formato
- Monto puede tener o no decimales
- Nombre puede tener 2, 3 o 4 palabras

Campos a extraer:
- tipo: recibido | enviado
- monto: Decimal
- moneda: siempre CRC para SINPE
- persona: nombre completo
- descripcion: texto después de la coma (opcional)
- comprobante: número de referencia

Por favor genera:
1. src/parsers/sinpe/sms_parser.py
2. Regex patterns para diferentes variaciones
3. Tests con 20+ ejemplos de SMS

El parser debe:
- Ser robusto ante variaciones
- Retornar confidence score
- Loggear formatos no reconocidos para análisis
```

---

### Tarea 5.3: Parser de Emails BAC

**Prompt:**
```
Necesito parser para emails de notificación de BAC Credomatic.

Tipos de notificación:
1. Compra con tarjeta (débito o crédito)
2. Transferencia enviada
3. Transferencia recibida
4. Retiro en ATM

Formato típico (HTML email):
- Subject contiene tipo de transacción y monto
- Body HTML con tabla de detalles
- Campos: comercio, monto, tarjeta (**** últimos 4), fecha/hora

Por favor genera:
1. src/parsers/bac/email_parser.py
2. Funciones para extraer datos de HTML (BeautifulSoup)
3. Patterns para diferentes tipos de notificación
4. Tests con ejemplos de cada tipo

Consideraciones:
- El formato HTML puede cambiar, ser flexible
- Algunos campos son opcionales
- Manejar USD y CRC
- Extraer últimos 4 dígitos de tarjeta para matching
```

---

### Tarea 5.4: Parser de PDFs BAC

**Prompt:**
```
Necesito parser para estados de cuenta PDF de BAC Credomatic.

Características del PDF:
- Tabla con transacciones del mes
- Header con datos de cuenta y período
- Columnas: fecha, descripción, débito, crédito, balance
- Múltiples páginas posibles

Estrategia de extracción:
1. Opción A: pdftotext + regex (rápido, menos preciso)
2. Opción B: Claude Vision (lento, muy preciso)
3. Opción C: tabula-py para tablas (balance entre ambos)

Por favor genera:
1. src/parsers/bac/pdf_parser.py
2. Implementar Opción C (tabula-py) como principal
3. Fallback a Opción B (Claude Vision) si tabula falla
4. Función para extraer metadata del header
5. Tests con PDFs de ejemplo (sanitizados)

Output debe incluir:
- Lista de transacciones
- Metadata: período, cuenta, saldo inicial/final
- Hash del PDF para evitar reprocesamiento
```

---

### Tarea 5.5: Sistema de Detección Automática

**Prompt:**
```
Necesito un sistema que detecte automáticamente qué parser usar.

Inputs posibles:
1. Texto de SMS → detectar si es SINPE
2. Email (subject + body) → detectar banco y tipo
3. Archivo PDF → detectar banco

Por favor genera:
1. src/parsers/detector.py con función detect_parser(input)
2. Retorna: parser apropiado o None si no se reconoce
3. Loggear formatos no reconocidos para análisis futuro

Patterns de detección:
- SINPE SMS: contiene "SINPE Movil" o "SINPE móvil"
- BAC Email: from contains "@baccredomatic" o "@notificacionesbaccr.com"
- Popular Email: from contains "@bancopopular.fi.cr"
- BAC PDF: primera página contiene "BAC CREDOMATIC"
```

---

### Tarea 5.6: Tests Exhaustivos de Parsers

**Prompt:**
```
Necesito tests exhaustivos para todos los parsers.

Requisitos:
1. Mínimo 20 ejemplos reales por parser (sanitizados)
2. Casos edge: formatos viejos, caracteres especiales, montos grandes
3. Tests de accuracy: % de campos extraídos correctamente
4. Tests de robustez: qué pasa con input malformado

Por favor genera:
1. tests/parsers/test_sinpe_parser.py
2. tests/parsers/test_bac_email_parser.py
3. tests/parsers/test_bac_pdf_parser.py
4. tests/parsers/fixtures/ con ejemplos de cada formato

Target de accuracy:
- SINPE SMS: >95%
- BAC Email: >90%
- BAC PDF: >85%
```

---

### Verificación de Fase 5

**Prompt:**
```
Verifica que la Fase 5 está completa:

1. [ ] Parser SINPE SMS funciona con >95% accuracy
2. [ ] Parser BAC Email funciona con >90% accuracy
3. [ ] Parser BAC PDF funciona con >85% accuracy
4. [ ] Detector automático identifica formato correctamente
5. [ ] Tests pasan con ejemplos reales
6. [ ] Formatos no reconocidos se loggean
7. [ ] Documentación de formatos soportados
8. [ ] UI para importar manualmente (si tiempo permite)

Ejecutar tests de accuracy y reportar resultados.
```
```

---

## Archivo: docs/prompts/phase-6-deploy.md

```markdown
# Fase 6: Polish y Deploy
## Prompts para AI Assistants

### Contexto de la Fase
```
Fase 6: Preparar el proyecto para mostrar a reclutadores y usuarios.

Objetivos:
1. Deploy accesible online
2. Documentación profesional
3. Video demo
4. Seguridad básica
5. CI/CD completo
```

---

### Tarea 6.1: Seguridad Básica

**Prompt:**
```
Necesito implementar seguridad básica para el proyecto.

Checklist OWASP ASVS Level 2:
1. [ ] Input validation en todos los endpoints
2. [ ] Rate limiting (10 req/min en /ai/chat, 100 req/min general)
3. [ ] Headers de seguridad (HSTS, CSP, etc)
4. [ ] Logging sin datos sensibles (no loggear amounts, descriptions)
5. [ ] SQL injection prevention (verificar que ORM se usa siempre)
6. [ ] Secrets en variables de entorno (no hardcoded)

Por favor genera:
1. Auditoría del código actual identificando vulnerabilidades
2. Middleware de rate limiting para FastAPI
3. Configuración de headers de seguridad
4. Review de logging para eliminar PII

No necesitamos auth completa aún, pero sí las bases de seguridad.
```

---

### Tarea 6.2: README Profesional Final

**Prompt:**
```
Necesito el README.md final profesional para el proyecto.

Secciones requeridas:
1. Header con badges (build, coverage, license, python version)
2. Hero image o GIF demo (placeholder por ahora)
3. Descripción en 1 párrafo
4. Features con iconos
5. Quick Start (< 5 minutos con Docker)
6. Arquitectura (diagrama ASCII o imagen)
7. Screenshots del dashboard
8. API Documentation link
9. MCP Server setup
10. Roadmap (público)
11. Contributing guidelines
12. License

Tono: Profesional, conciso, en español.
El README debe vender el proyecto a reclutadores Y usuarios potenciales.
```

---

### Tarea 6.3: Deploy a Producción

**Prompt:**
```
Necesito configurar deploy a producción.

Opciones evaluadas:
1. Streamlit Cloud (gratis, fácil, solo Streamlit)
2. Railway (fácil, PostgreSQL incluido, $5/mes)
3. Render (similar a Railway)
4. Fly.io (más control, más complejo)

Recomendación: Railway para todo o Streamlit Cloud + Supabase (PostgreSQL)

Por favor genera:
1. railway.toml o configuración equivalente
2. Dockerfile optimizado para producción
3. GitHub Action para deploy automático en merge a main
4. Instrucciones de setup inicial
5. Configuración de dominio custom (si aplica)

Consideraciones:
- PostgreSQL con pgvector debe funcionar
- Variables de entorno secretas
- Health checks
- Logs accesibles
```

---

### Tarea 6.4: CI/CD Completo

**Prompt:**
```
Necesito CI/CD completo con GitHub Actions.

Workflows requeridos:

1. ci.yml (en cada PR)
   - Lint (ruff)
   - Type check (mypy)
   - Tests (pytest)
   - Coverage report
   - Fail si coverage < 60%

2. deploy.yml (en merge a main)
   - Build Docker image
   - Push a registry
   - Deploy a Railway/Render
   - Notify en Discord/Slack (opcional)

3. release.yml (en tag)
   - Crear GitHub Release
   - Changelog automático
   - Docker image con tag de versión

Por favor genera todos los workflow files.
```

---

### Tarea 6.5: Video Demo

**Prompt:**
```
Necesito un script para grabar video demo de 5 minutos.

Estructura del video:
1. Intro (30s): Qué es y para quién
2. Dashboard Tour (90s): Mostrar features principales
3. MCP Demo (90s): Conversación con Claude Desktop
4. Parsers Demo (60s): Importar SMS/email
5. Cierre (30s): Cómo empezar, link a repo

Script detallado con:
- Qué decir en cada parte
- Qué mostrar en pantalla
- Transiciones
- Datos de demo a preparar

El video debe ser profesional pero auténtico (no sobre-producido).
```

---

### Tarea 6.6: Preparación para Entrevistas

**Prompt:**
```
Necesito preparar material para hablar del proyecto en entrevistas.

Generar:

1. Elevator pitch (30 segundos)
"Finanzas Tracker es un sistema de finanzas personales para Costa Rica 
que usa AI para categorizar transacciones automáticamente y un MCP Server 
que permite consultar tus finanzas desde Claude Desktop. Es el primero 
en soportar SINPE Móvil y bancos costarricenses."

2. Technical deep dive (5 minutos)
- Arquitectura y decisiones
- Desafíos técnicos resueltos
- Trade-offs considerados

3. Tres historias de decisiones técnicas
- Por qué pgvector en lugar de ChromaDB
- Cómo resolvimos la falta de APIs bancarias
- Diseño del MCP Server diferenciado

4. Métricas de impacto
- X transacciones procesadas
- Y% accuracy en categorización
- Z segundos latencia de RAG

5. Preguntas esperadas y respuestas
- "¿Por qué no usaste React?"
- "¿Cómo escalarías esto?"
- "¿Qué harías diferente?"
```

---

### Verificación Final

**Prompt:**
```
Verificación final del proyecto completo:

FUNCIONALIDAD
[ ] Dashboard Streamlit funciona
[ ] API REST responde correctamente
[ ] RAG responde preguntas de forma útil
[ ] MCP Server funciona en Claude Desktop
[ ] Parsers extraen datos correctamente

CALIDAD
[ ] Test coverage ≥60% general, ≥80% services
[ ] Lint pasa sin errores
[ ] Type check pasa
[ ] Sin vulnerabilidades conocidas

DOCUMENTACIÓN
[ ] README profesional completo
[ ] API docs en /docs
[ ] MCP setup documentado
[ ] CONTRIBUTING.md existe

DEPLOY
[ ] Demo online accesible
[ ] CI/CD funcionando
[ ] Deploy automático en merge

PORTFOLIO
[ ] Video demo grabado
[ ] Material de entrevista preparado
[ ] LinkedIn post listo

Ejecutar todas las verificaciones y reportar estado.
```
```

---

## Troubleshooting Común

```markdown
# Troubleshooting para AI Assistants

## Problemas Comunes y Soluciones

### 1. "El código generado no compila/corre"

**Causa probable**: Falta de contexto
**Solución**: Pegar código relacionado (imports, tipos, etc.)

**Prompt de recuperación:**
```
El código anterior tiene este error: [pegar error]

Contexto adicional:
- Imports disponibles: [listar]
- Tipos definidos: [pegar definiciones]
- Versiones: Python 3.11, FastAPI 0.100+, SQLAlchemy 2.0

Por favor corrige el código considerando este contexto.
```

### 2. "Los tests fallan"

**Prompt de diagnóstico:**
```
Los tests fallan con este error: [pegar error completo]

Test que falla: [pegar test]
Código siendo testeado: [pegar código]
Fixtures disponibles: [pegar fixtures]

¿Cuál es el problema y cómo lo arreglo?
```

### 3. "La migración de Alembic falla"

**Prompt de recuperación:**
```
La migración de Alembic falla con: [error]

Estado actual de la DB: [describir]
Migración intentada: [pegar código de migración]
Models actuales: [pegar models relevantes]

¿Cómo arreglo la migración?
```

### 4. "Docker no levanta"

**Prompt de diagnóstico:**
```
Docker Compose falla con: [error]

docker-compose.yml: [pegar]
Dockerfile: [pegar]
.env: [pegar sin secrets]

¿Qué está mal y cómo lo arreglo?
```

### 5. "MCP Server no aparece en Claude Desktop"

**Checklist de diagnóstico:**
```
1. ¿El server arranca manualmente? python -m src.mcp.server
2. ¿El config está en la ubicación correcta?
   - macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
   - Windows: %APPDATA%\Claude\claude_desktop_config.json
3. ¿El path al script es absoluto?
4. ¿Las variables de entorno están configuradas?
5. ¿Claude Desktop se reinició después del cambio?

Logs del MCP server: [pegar si hay]
```

### 6. "RAG retorna respuestas irrelevantes"

**Prompt de diagnóstico:**
```
El RAG retorna respuestas que no tienen sentido.

Pregunta del usuario: [pregunta]
Transacciones recuperadas: [pegar primeras 5]
Respuesta generada: [respuesta]

Posibles causas:
1. Embeddings de baja calidad
2. Threshold de similaridad muy bajo
3. Prompt de Claude mal diseñado
4. Datos insuficientes

¿Cómo diagnostico cuál es el problema?
```

### 7. "El parser no reconoce el formato"

**Prompt para agregar soporte:**
```
El parser no reconoce este formato:
[pegar ejemplo del formato no reconocido]

Parsers existentes: [listar]
Patterns actuales: [pegar regex/patterns]

Por favor:
1. Identifica qué es diferente en este formato
2. Actualiza el parser para soportarlo
3. Agrega test con este ejemplo
```
```
