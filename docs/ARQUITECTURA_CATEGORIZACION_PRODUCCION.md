# 🏗️ Arquitectura de Categorización - Finanzas Tracker CR

## Documento Técnico y Estratégico

**Fecha:** Diciembre 2025  
**Autor:** GitHub Copilot + Sebastián Cruz  
**Versión:** 1.0  

---

## 📋 Índice

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Análisis del Mercado](#análisis-del-mercado)
3. [Arquitectura Propuesta](#arquitectura-propuesta)
4. [Modelo de Aprendizaje Continuo](#modelo-de-aprendizaje-continuo)
5. [Stack Tecnológico](#stack-tecnológico)
6. [Análisis de Costos](#análisis-de-costos)
7. [Viabilidad y Factibilidad](#viabilidad-y-factibilidad)
8. [Consideraciones Éticas](#consideraciones-éticas)
9. [Roadmap de Implementación](#roadmap-de-implementación)
10. [Conclusión](#conclusión)

---

## 🎯 Resumen Ejecutivo

### La Visión
Construir un sistema de categorización de transacciones financieras **específico para Costa Rica** que:
- Sea **gratuito o casi gratuito** de operar en fase inicial
- **Aprenda** de las correcciones de los usuarios
- Entienda el contexto local (SINPE, BAC, Popular, comercios ticos)
- Use metodología **50/30/20** adaptada a la realidad costarricense

### La Propuesta
Un sistema **híbrido de 4 capas** donde:
- **~90% de transacciones** se categorizan con reglas locales (gratis, instantáneo)
- **~8% adicional** se resuelven con embeddings y aprendizaje (gratis con modelos open source)
- **~2% restante** usa Claude API (bajo costo, solo casos difíciles)

### El Diferenciador
Ninguna app del mercado entiende Costa Rica. Copilot.money cobra $95/año y no sabe qué es "Automercado" o "SINPE Móvil". **Nosotros sí.**

---

## 📊 Análisis del Mercado

### Competencia Internacional

| App | Precio | Ventajas | Desventajas |
|-----|--------|----------|-------------|
| **Copilot.money** | $95/año | UX excelente, AI learning | Solo USA, no LATAM |
| **Monarch Money** | $99/año | Familiar, presupuestos | Solo USA |
| **YNAB** | $99/año | Metodología sólida | Manual, curva de aprendizaje |
| **Mint** | Gratis (cerró) | Era gratis | Ya no existe |

### APIs B2B (Para empresas, no consumidores)

| Servicio | Modelo | Costo | Notas |
|----------|--------|-------|-------|
| **Plaid Enrich** | Por transacción | ~$0.01-0.05/txn | Requiere Plaid connection |
| **Ntropy** | Por transacción | ~$0.005-0.02/txn | 100M+ merchants globales |
| **Stripe Financial Connections** | Incluido | Parte de Stripe | Solo con Stripe |

### Competencia en Costa Rica/LATAM

**No existe competencia directa.** Las apps bancarias de BAC y Popular:
- No tienen categorización inteligente
- No permiten ver múltiples bancos juntos
- No tienen metodología 50/30/20
- No aprenden de tus patrones

### 🎯 Oportunidad de Mercado

Costa Rica tiene:
- **76% adopción de SINPE Móvil** (una de las más altas del mundo)
- **~1.5M de usuarios bancarios digitales**
- **Cero apps locales** de finanzas personales con AI

---

## 🏗️ Arquitectura Propuesta

### Diagrama de Capas

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         NUEVA TRANSACCIÓN                                   │
│                    "SINPE MAMA ROSA CRC 50,000"                            │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  CAPA 1: DETERMINÍSTICA (Gratis, <1ms)                                     │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────────┐   │
│  │  Merchant DB    │ │  SINPE Patterns │ │  User History              │   │
│  │  (500+ CR)      │ │  (Regex)        │ │  (Este usuario ya          │   │
│  │                 │ │                 │ │   categorizó a "MAMA ROSA" │   │
│  │  Automercado→   │ │  SINPE+nombre→  │ │   como "Familia")          │   │
│  │  Supermercado   │ │  Transferencia  │ │                            │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────────────────┘   │
│                                                                             │
│  → Si confianza >= 80%: RETORNAR RESULTADO                                 │
│  → Tasa de éxito esperada: ~90%                                            │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │ fallback
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  CAPA 2: EMBEDDINGS + SIMILARITY (Gratis*, ~50ms)                          │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  SentenceTransformers (all-MiniLM-L6-v2) - Modelo open source       │  │
│  │                                                                      │  │
│  │  "SINPE MAMA ROSA" → vector [0.23, -0.45, 0.12, ...]                │  │
│  │                                                                      │  │
│  │  Buscar en pgvector transacciones similares ya categorizadas:       │  │
│  │  - "SINPE PAPA CARLOS" → Transferencias Familia (95% similar)       │  │
│  │  - "SINPE TIA ELENA" → Transferencias Familia (92% similar)         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  → Si confianza >= 85%: RETORNAR RESULTADO                                 │
│  → Tasa de éxito esperada: ~8% adicional                                   │
│  * Gratis si se corre localmente con SentenceTransformers                  │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │ fallback
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  CAPA 3: CLAUDE API (Pagado, ~500ms)                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  Prompt especializado con contexto CR:                               │  │
│  │                                                                      │  │
│  │  "Eres un experto en finanzas de Costa Rica. Categoriza esta        │  │
│  │   transacción según metodología 50/30/20:                           │  │
│  │   - Comercio: SINPE MAMA ROSA                                        │  │
│  │   - Monto: ₡50,000                                                   │  │
│  │   - Categorías disponibles: [lista de subcategorías]                │  │
│  │   - Historial del usuario: [contexto]"                              │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  → Solo se usa para ~2% de transacciones (las ambiguas)                    │
│  → Costo estimado: ~$0.002 por transacción                                 │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │ resultado
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  CAPA 4: FEEDBACK LOOP (Aprendizaje Continuo)                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  Cuando el usuario CORRIGE una categorización:                       │  │
│  │                                                                      │  │
│  │  1. Guardar en user_corrections:                                     │  │
│  │     {user_id, merchant_pattern, correct_category, timestamp}         │  │
│  │                                                                      │  │
│  │  2. Actualizar embedding de la transacción                           │  │
│  │                                                                      │  │
│  │  3. Si N usuarios corrigen igual → proponer a merchant_db global    │  │
│  │     (Ej: 5 usuarios dicen que "CAFE BRITT" es "Comida Social")      │  │
│  │                                                                      │  │
│  │  4. Re-entrenar modelo de embeddings mensualmente (opcional)         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Flujo de Datos

```
Usuario sube estado de cuenta
           │
           ▼
    ┌──────────────┐
    │  Email/PDF   │
    │   Parser     │
    └──────┬───────┘
           │ transacciones crudas
           ▼
    ┌──────────────┐
    │    Smart     │──→ Capa 1 (reglas)
    │ Categorizer  │──→ Capa 2 (embeddings)
    └──────┬───────┘──→ Capa 3 (Claude, si necesario)
           │
           ▼
    ┌──────────────┐
    │  Dashboard   │
    │   50/30/20   │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │   Usuario    │──→ Corrige categorías incorrectas
    │   Revisa     │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │  Feedback    │──→ Mejora el sistema para todos
    │    Loop      │
    └──────────────┘
```

---

## 🧠 Modelo de Aprendizaje Continuo

### Nivel 1: Aprendizaje por Usuario

```sql
-- Tabla: user_merchant_preferences
CREATE TABLE user_merchant_preferences (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    merchant_pattern VARCHAR(200) NOT NULL,  -- Ej: "SINPE MAMA%"
    subcategory_id UUID NOT NULL,
    times_used INTEGER DEFAULT 1,
    last_used TIMESTAMP DEFAULT NOW(),
    confidence DECIMAL(3,2) DEFAULT 0.95,
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(user_id, merchant_pattern)
);
```

**Cómo funciona:**
1. Usuario recibe transacción "SINPE MAMA ROSA"
2. Sistema sugiere "Transferencias" (genérico)
3. Usuario corrige a "Familia" (su subcategoría personalizada)
4. Sistema guarda: `{pattern: "SINPE MAMA%", category: "Familia"}`
5. Próxima vez que aparezca "SINPE MAMA [cualquier cosa]" → Familia

### Nivel 2: Identificación de Contactos SINPE

```sql
-- Tabla: user_contacts
CREATE TABLE user_contacts (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    phone_number VARCHAR(20),           -- Ej: "8888-1234"
    name_from_sinpe VARCHAR(200),       -- Ej: "ROSA MARIA CRUZ"
    alias VARCHAR(100),                 -- Ej: "Mamá"
    default_category_id UUID,           -- Ej: "Familia"
    relationship_type VARCHAR(50),      -- Ej: "family", "friend", "business"
    total_transactions INTEGER DEFAULT 0,
    total_amount DECIMAL(15,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(user_id, phone_number)
);
```

**Cómo funciona:**
1. Primera vez: "SINPE a 8888-1234 - ROSA CRUZ" → Usuario etiqueta como "Mamá"
2. Sistema aprende: `phone=8888-1234 → name="Mamá" → category="Familia"`
3. Próxima vez: Autocompleta el destinatario y sugiere categoría

### Nivel 3: Aprendizaje Colectivo (Crowdsourced)

```sql
-- Tabla: global_merchant_suggestions
CREATE TABLE global_merchant_suggestions (
    id UUID PRIMARY KEY,
    merchant_pattern VARCHAR(200) NOT NULL,  -- Ej: "CAFE BRITT"
    suggested_subcategory_id UUID NOT NULL,
    user_count INTEGER DEFAULT 1,            -- Cuántos usuarios sugirieron esto
    confidence_score DECIMAL(3,2),           -- Basado en consenso
    status VARCHAR(20) DEFAULT 'pending',    -- pending, approved, rejected
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(merchant_pattern, suggested_subcategory_id)
);
```

**Cómo funciona:**
1. Usuario A categoriza "CAFE BRITT" como "Comida Social"
2. Usuario B hace lo mismo
3. Usuario C, D, E también
4. Sistema detecta: 5+ usuarios = consenso
5. "CAFE BRITT" se agrega a `CR_MERCHANTS_DB` global
6. Todos los usuarios se benefician automáticamente

### Nivel 4: Fine-tuning de Modelo (Futuro)

Cuando tengamos suficientes datos (1000+ usuarios, 100K+ transacciones):

```python
# Dataset de entrenamiento generado automáticamente
training_data = [
    {"text": "SINPE MAMA ROSA", "label": "familia"},
    {"text": "AUTOMERCADO ESCAZU", "label": "supermercado"},
    {"text": "UBER *TRIP", "label": "transporte"},
    # ... miles más
]

# Fine-tune un modelo pequeño
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader

model = SentenceTransformer('all-MiniLM-L6-v2')
# ... fine-tuning con datos de CR
model.save("finanzas-cr-embeddings-v1")
```

---

## 🛠️ Stack Tecnológico

### Opción A: Mínimo Costo (Para 10 usuarios de prueba)

| Componente | Tecnología | Costo |
|------------|------------|-------|
| **Embeddings** | SentenceTransformers (local) | **$0** |
| **Base de datos** | PostgreSQL + pgvector (Render free) | **$0** |
| **Backend** | FastAPI (Render free tier) | **$0** |
| **Frontend** | Streamlit (Render free) o Vercel | **$0** |
| **LLM** | Claude API (solo fallback) | ~$2-5/mes* |

*Estimado: 500 transacciones/mes × 2% fallback × $0.002 = $0.02/mes

**Total: ~$2-5/mes** (solo Claude para casos difíciles)

### Opción B: Producción Pequeña (100 usuarios)

| Componente | Tecnología | Costo |
|------------|------------|-------|
| **Embeddings** | Voyage AI o local | $0-10/mes |
| **Base de datos** | Render Postgres Basic | $6/mes |
| **Backend** | Render Starter | $9/mes |
| **Frontend** | Vercel free | $0 |
| **LLM** | Claude API | ~$10-20/mes |

**Total: ~$25-45/mes**

### Opción C: Escala (1000+ usuarios)

| Componente | Tecnología | Costo |
|------------|------------|-------|
| **Embeddings** | Self-hosted GPU o API | $50-100/mes |
| **Base de datos** | Render Postgres Pro | $55/mes |
| **Backend** | Render Standard | $25/mes |
| **LLM** | Claude API + Caching | ~$50-100/mes |

**Total: ~$180-280/mes**

---

## 💰 Análisis de Costos Detallado

### Escenario: 10 usuarios de prueba

**Asumiendo:**
- 10 usuarios
- 100 transacciones/usuario/mes = 1,000 transacciones/mes
- 90% resueltas por reglas (gratis)
- 8% resueltas por embeddings locales (gratis)
- 2% requieren Claude = 20 transacciones/mes

**Costo Claude:**
- Claude Haiku: ~$0.00025 por 1K tokens input
- Prompt promedio: ~500 tokens
- 20 requests × 500 tokens = 10K tokens = $0.0025/mes

**Costo Total: ~$0.01/mes** 🎉

### Escenario: 100 usuarios

- 10,000 transacciones/mes
- 200 requieren Claude (2%)
- Claude: 100K tokens = $0.025/mes
- Hosting: $15/mes (Render básico)

**Costo Total: ~$15/mes**

### Escenario: 1000 usuarios

- 100,000 transacciones/mes
- 2,000 requieren Claude
- Claude: 1M tokens = $0.25/mes para Haiku, ~$2.50 para Sonnet
- Hosting: $80/mes (Render Standard + DB)

**Costo Total: ~$85/mes**

### 📊 Comparación con Competencia

| Servicio | Costo por 10K txn/mes | Notas |
|----------|------------------------|-------|
| **Ntropy** | $50-200 | API comercial |
| **Plaid Enrich** | $100-500 | Requiere Plaid |
| **Nuestro sistema** | ~$15 | Self-hosted + Claude fallback |

**Ahorro: 3-30x más barato**

---

## ✅ Viabilidad y Factibilidad

### ¿Es posible hacerlo gratis/casi gratis?

**SÍ, absolutamente.** Aquí está cómo:

#### 1. Embeddings Gratuitos

```python
# SentenceTransformers es 100% gratis y open source
from sentence_transformers import SentenceTransformer

# Este modelo es pequeño (80MB) y corre en cualquier laptop
model = SentenceTransformer('all-MiniLM-L6-v2')

# Generar embedding de una transacción
embedding = model.encode("AUTOMERCADO ESCAZU CRC 45000")
# → vector de 384 dimensiones, instantáneo, gratis
```

#### 2. Vector Search Gratuito

```sql
-- pgvector es extensión gratuita de PostgreSQL
CREATE EXTENSION vector;

-- Buscar transacciones similares
SELECT comercio, subcategory_id, 
       1 - (embedding <=> query_embedding) as similarity
FROM transactions
WHERE 1 - (embedding <=> query_embedding) > 0.85
ORDER BY similarity DESC
LIMIT 5;
```

#### 3. Hosting Gratuito (Free Tier)

| Servicio | Free Tier |
|----------|-----------|
| **Render** | 512MB RAM, 100GB bandwidth |
| **Railway** | $5 crédito/mes |
| **Fly.io** | 3 VMs gratis |
| **Vercel** | Frontend ilimitado |
| **Supabase** | 500MB Postgres gratis |

### ¿Es complicado de implementar?

**Nivel de complejidad: MEDIO**

Lo que ya tenemos:
- ✅ SmartCategorizer con capas 1-3 funcionando
- ✅ Merchant database de Costa Rica
- ✅ Patrones SINPE
- ✅ pgvector instalado
- ✅ Embeddings con Voyage AI

Lo que falta:
- ⏳ Tabla de user_merchant_preferences (1 día)
- ⏳ Tabla de user_contacts para SINPE (1 día)
- ⏳ Feedback loop cuando usuario corrige (2 días)
- ⏳ Global merchant suggestions (2 días)
- ⏳ Migrar embeddings a SentenceTransformers local (1 día)

**Estimado total: 1-2 semanas de desarrollo**

---

## 🤔 Consideraciones Éticas

### ✅ Lo que hacemos bien

1. **Privacidad de datos**
   - Datos financieros nunca salen del servidor
   - No vendemos datos a terceros
   - Usuario puede borrar sus datos completamente

2. **Transparencia**
   - Usuario ve qué categoría se asignó y por qué
   - Puede corregir cualquier categorización
   - Sistema explica: "Sugerido porque X"

3. **Aprendizaje ético**
   - Solo aprendemos de correcciones explícitas
   - No hacemos tracking sin consentimiento
   - Datos colectivos son anonimizados

### ⚠️ Consideraciones

1. **Sesgos en categorización**
   - Asegurarse que el sistema no discrimine
   - Revisar que categorías no tengan juicios de valor
   - "Gastos innecesarios" vs "Entretenimiento"

2. **Dependencia de AI**
   - Usuario siempre tiene control final
   - No tomar decisiones financieras automáticas
   - Solo sugerencias, nunca acciones

3. **Datos sensibles**
   - Transacciones revelan mucho sobre una persona
   - Encriptar en reposo y tránsito
   - Acceso mínimo necesario

---

## 🎮 ¿Es un Game Changer?

### Para Costa Rica: **SÍ**

**Por qué:**
1. **Nadie más lo hace** - Primer mover advantage
2. **Entendemos SINPE** - La competencia internacional no
3. **Contexto local** - Automercado, ICE, Kolbi, Peajes
4. **Metodología 50/30/20** - Adaptada a salarios ticos
5. **Precio** - Gratis o muy barato vs $99/año de YNAB

### Potencial de Crecimiento

```
Fase 1: Beta privada (10 usuarios)
        └── Validar concepto, iterar
        
Fase 2: Beta pública (100 usuarios)
        └── Word of mouth, feedback
        
Fase 3: Lanzamiento CR (1,000 usuarios)
        └── Marketing básico, partnerships bancos?
        
Fase 4: Expansión LATAM
        └── Guatemala, Panamá, Colombia
        └── Adaptar SINPE → Otros sistemas locales
```

### Modelo de Negocio Potencial

| Tier | Precio | Incluye |
|------|--------|---------|
| **Free** | $0 | 1 cuenta, categorización básica |
| **Pro** | $5/mes | Multi-cuenta, AI avanzado, insights |
| **Family** | $8/mes | 4 miembros, presupuestos compartidos |
| **Business** | $15/mes | API access, reportes |

---

## 🗺️ Roadmap de Implementación

### Semana 1: Fundamentos

- [ ] Migrar embeddings a SentenceTransformers (gratis)
- [ ] Crear tabla `user_merchant_preferences`
- [ ] Implementar feedback loop básico
- [ ] Tests de integración

### Semana 2: Aprendizaje

- [ ] Crear tabla `user_contacts` para SINPE
- [ ] Autocompletado de destinatarios
- [ ] UI para corregir categorías
- [ ] Dashboard mejorado

### Semana 3: Optimización

- [ ] Caching de embeddings
- [ ] Batch processing
- [ ] Métricas de precisión
- [ ] Logging de errores

### Semana 4: Preparar Deploy

- [ ] Dockerizar aplicación
- [ ] Setup en Render/Railway
- [ ] Variables de entorno
- [ ] Monitoreo básico

### Mes 2: Beta

- [ ] 10 usuarios de prueba
- [ ] Recolectar feedback
- [ ] Iterar en UX
- [ ] Implementar suggestions globales

---

## 🎯 Conclusión

### ¿Es viable? **SÍ**

### ¿Es factible con bajo presupuesto? **SÍ**
- Costo inicial: ~$0-5/mes
- Costo con 100 usuarios: ~$15-25/mes

### ¿Es un game changer para CR? **POTENCIALMENTE SÍ**
- Nadie más lo está haciendo
- El mercado está desatendido
- La tecnología existe y es accesible

### ¿Es ético? **SÍ**, si seguimos principios de:
- Transparencia
- Privacidad
- Control del usuario

### Recomendación Final

**Proceder con desarrollo.** El sistema híbrido propuesto:
1. Minimiza costos usando reglas locales + embeddings gratuitos
2. Usa Claude solo como fallback (2% de casos)
3. Aprende y mejora con cada usuario
4. Tiene potencial de escalabilidad real

---

## 📚 Referencias

- [SentenceTransformers](https://www.sbert.net/) - Embeddings gratuitos
- [pgvector](https://github.com/pgvector/pgvector) - Vector search en PostgreSQL
- [Ntropy](https://ntropy.com) - Referencia de arquitectura
- [Copilot.money Intelligence](https://copilot.money/intelligence) - Referencia de UX
- [Render Pricing](https://render.com/pricing) - Hosting económico

---

*Documento generado para Finanzas Tracker CR - Diciembre 2025*
