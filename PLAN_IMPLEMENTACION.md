# 🚀 Plan de Implementación - Finanzas Tracker CR con IA

## Visión General

Crear un sistema de finanzas personales inteligente que:
1. **Importa automáticamente** transacciones de estados de cuenta (PDF) y correos
2. **Reconcilia inteligentemente** SINPEs/transferencias con correos de notificación
3. **Aprende de los usuarios** para categorizar automáticamente en el futuro
4. **Usa Claude AI** para entender lenguaje natural y resolver ambigüedades

---

## 📋 Fases de Implementación

### Fase 1: Arreglar Importación y Match ✅ COMPLETADA
**Objetivo:** El flujo básico funciona correctamente

| Tarea | Estado | Descripción |
|-------|--------|-------------|
| 1.1 Buscar correos desde fecha correcta | ✅ | Desde 28 del mes anterior a fecha_corte hasta hoy |
| 1.2 Match PDF ↔ Correos por monto+fecha+referencia | ✅ | Tolerancia ±2 días |
| 1.3 TODAS las transferencias a revisión | ✅ | Excepto descripciones muy claras (alquiler, salario, etc.) |
| 1.4 Mostrar contexto real en revisión | ✅ | Beneficiario, concepto, fecha real del correo |

---

### Fase 2: Chatbox con Claude para Revisión ✅ COMPLETADA
**Objetivo:** El usuario habla con Claude en lenguaje natural para clarificar transacciones

| Tarea | Estado | Descripción |
|-------|--------|-------------|
| 2.1 Crear servicio TransactionClarifierService | ✅ | Usa Claude API con retry y manejo de errores |
| 2.2 Integrar chatbox en Streamlit | ✅ | UI tipo chatbox con entrada de texto |
| 2.3 Prompt engineering para categorización | ✅ | Claude entiende contexto financiero CR |
| 2.4 Procesar respuestas de Claude | ✅ | Extrae descripción, beneficiario, categoría |
| 2.5 Modo manual como fallback | ✅ | Si Claude no está disponible o usuario prefiere |

**Ejemplo de interacción:**
```
Claude: "Veo un SINPE de ₡18,000 el 28/Nov. ¿A quién le pagaste?"
Usuario: "Eso fue para el zapatero que me arregló unos zapatos"
Claude: "Perfecto, lo categorizo como 'Servicios > Reparaciones'. ¿Correcto?"
Usuario: "Sí"
Claude: "Listo ✅ ¿Y este otro SINPE de ₡5,000 del 30/Nov?"
```

---

### Fase 3: Aprendizaje de Patrones (ML/Embeddings) ✅ COMPLETADA
**Objetivo:** El sistema aprende y sugiere automáticamente

| Tarea | Estado | Descripción |
|-------|--------|-------------|
| 3.1 Servicio PatternLearningService | ✅ | Guarda patrones de clarificaciones |
| 3.2 Guardar al clarificar | ✅ | Integrado en TransactionClarifierService |
| 3.3 Auto-categorizar en reconciliación | ✅ | Integrado en SinpeReconciliationService |
| 3.4 Sugerencias en UI | ✅ | Botón "Sí, así es" / "No, es otra cosa" |
| 3.5 Contactos SINPE | ✅ | UserContact guarda beneficiarios conocidos |

**Patrones que detecta:**
- Por beneficiario normalizado: "JUAN PEREZ" → siempre es préstamo
- Por transacción similar: misma persona, monto parecido
- Por contacto conocido: "Mamá" → Personal/Familia
- Crowdsourced: 5+ usuarios categorizan igual → se aprueba globalmente

---

### Fase 4: Búsqueda de Comercios Desconocidos ✅ COMPLETADA
**Objetivo:** Claude identifica qué tipo de negocio es un comercio desconocido

| Tarea | Estado | Descripción |
|-------|--------|-------------|
| 4.1 Detectar comercios desconocidos | ✅ | No está en base de datos |
| 4.2 Claude identifica el comercio | ✅ | Por nombre y patrones |
| 4.3 Guardar en base de datos de comercios | ✅ | Para futuros usuarios |
| 4.4 Integrar en TransactionProcessor | ✅ | Se usa automáticamente al procesar |

---

### Fase 5: Dashboard Inteligente ✅ COMPLETADA
**Objetivo:** Insights y recomendaciones personalizadas

| Tarea | Estado | Descripción |
|-------|--------|-------------|
| 5.1 Resumen mensual con gráficos | ✅ | Gastos por categoría, tendencias |
| 5.2 Alertas de gastos inusuales | ✅ | "Este mes gastaste 50% más en restaurantes" |
| 5.3 Predicciones | ✅ | "A este ritmo, terminarás el mes con X" |
| 5.4 Comparación con presupuesto 50/30/20 | ✅ | Necesidades/Gustos/Ahorros |
| 5.5 InsightsService | ✅ | Servicio central de insights inteligentes |

---

## 🛠️ Stack Técnico

| Componente | Tecnología |
|------------|------------|
| Backend | Python 3.11+, FastAPI |
| Base de datos | PostgreSQL 16 + pgvector |
| Frontend | Streamlit |
| IA/LLM | Claude API (Anthropic) |
| Embeddings | text-embedding-3-small (OpenAI) o Claude |
| Vectores | pgvector para similitud |
| Email | Microsoft Graph API (Outlook), Gmail API |
| PDF Parser | Custom BAC parser |

---

## 📅 Timeline Estimado

| Fase | Duración | Prioridad |
|------|----------|-----------|
| Fase 1: Importación y Match | 1-2 días | 🔴 ALTA |
| Fase 2: Chatbox con Claude | 2-3 días | 🔴 ALTA |
| Fase 3: Aprendizaje/ML | 3-5 días | 🟡 MEDIA |
| Fase 4: Búsqueda comercios | 1-2 días | 🟡 MEDIA |
| Fase 5: Dashboard | 2-3 días | 🟢 BAJA |

---

## 🎯 Siguiente Paso Inmediato

**FASE 1.1 - Arreglar rango de búsqueda de correos:**

```python
# ANTES (incorrecto):
dias_atras = 45  # Fijo

# DESPUÉS (correcto):
# Si fecha_corte = 30/Nov/2025
# Buscar desde: 28/Oct/2025 (28 del mes anterior)
# Hasta: Hoy (9/Dic/2025)
```

**FASE 1.3 - Todas las transferencias a revisión:**

```python
# ANTES: Solo las "ambiguas"
# DESPUÉS: TODAS excepto las muy claras

DESCRIPCIONES_CLARAS = {
    "alquiler", "renta", "salario", "sueldo", 
    "luz", "agua", "internet", "electricidad"
}
```

---

## ✅ Criterios de Éxito

1. **Usuario nuevo** puede importar sus transacciones en <2 minutos
2. **Revisión con Claude** es conversacional y natural
3. **Segunda importación** tiene >80% de transacciones auto-categorizadas
4. **Después de 3 meses**, el sistema aprende patrones del usuario

---

## 📝 Notas

- **Priorizar UX sobre features** - Mejor pocas cosas que funcionen bien
- **Claude es el cerebro** - Delegar decisiones complejas a la IA
- **Aprender de errores** - Si usuario corrige, guardar para mejorar
- **Costa Rica first** - Optimizado para BAC, Popular, SINPE Móvil

---

*Última actualización: 9 de Diciembre, 2025*
