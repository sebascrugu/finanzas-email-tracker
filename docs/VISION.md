# 🚀 Finanzas Tracker CR - Visión y Roadmap

**Fecha:** 1 de Diciembre, 2025  
**Estado:** Ideas y planes futuros

> ⚠️ **Este documento describe lo que QUEREMOS construir.**  
> Para lo que existe HOY, ver [STATUS.md](./STATUS.md)

---

## 🎯 Visión

Convertirnos en **LA app de finanzas personales para Costa Rica** que:
1. Cualquier tico pueda usar (no solo nerds financieros)
2. Automatice el 80% del trabajo manual
3. Eduque mientras trackea
4. Sea tan adictiva como Instagram pero para tu bienestar financiero

---

## 📊 El Flujo Correcto

```
┌─────────────────────────────────────────────────────────────────┐
│  SETUP INICIAL: "¿Cuál es tu situación financiera hoy?"        │
│                                                                 │
│  1. 📧 Conectar email (Microsoft Graph)                         │
│  2. 📄 Subir PDF estado de cuenta                               │
│       ↓                                                         │
│     Detectamos automáticamente:                                 │
│       • Cuentas: Corriente BAC ***1234 (₡500,000)              │
│       • Tarjetas: VISA ***5678 (límite ₡2M, deuda ₡127K)       │
│       • Transacciones del mes                                   │
│                                                                 │
│  3. ✏️ "¿Querés agregar algo más?"                              │
│       • Inversiones (CDP, plazos)                               │
│       • Cuentas en otros bancos                                 │
│       • Metas (opcional)                                        │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  TRACKING CONTINUO (automático cada X horas):                   │
│                                                                 │
│  • Emails nuevos → Transacciones parseadas                      │
│  • Actualiza gastos por tarjeta                                 │
│  • Categoriza automáticamente (keywords + AI)                   │
│  • Calcula: "Llevás ₡85K de ₡150K presupuesto gustos"          │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  DASHBOARD:                                                     │
│                                                                 │
│  💰 Tu Patrimonio: ₡8,450,000 (+₡320,000 este mes)             │
│                                                                 │
│  📊 Desglose:                                                   │
│  ├── Cuentas: ₡2,100,000                                       │
│  ├── Inversiones: ₡6,500,000 (rendimiento: +₡45K)              │
│  └── Deudas: -₡150,000 (tarjeta crédito)                       │
│                                                                 │
│  💳 Tarjeta VISA BAC:                                           │
│  ├── Gastado este período: ₡127,000 / ₡2,000,000               │
│  ├── Fecha corte: 15 Dic                                        │
│  ├── Fecha pago: 28 Dic                                         │
│  └── ⚠️ Pagá antes del 28 para evitar intereses (52% anual)    │
│                                                                 │
│  📈 Presupuesto 50/30/20:                                       │
│  ├── Necesidades: ₡280K / ₡400K (70%) ██████████░░░             │
│  ├── Gustos: ₡85K / ₡150K (57%) █████████░░░░░░░                │
│  └── Ahorros: ₡120K / ₡150K (80%) ████████████░░░               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Priorización (Lo Que Importa)

### 🟢 Fundacional (YA EXISTE ✅)
```
✅ Transacciones (gastos/ingresos)
✅ Categorización 50/30/20
✅ Account (cuentas con saldos)
✅ Investment (inversiones con tasas)
✅ Goal (metas financieras)
✅ Card (modelo existe, necesita mejoras)
✅ JWT Auth
```

### 🟡 Próximo Sprint: Tarjetas de Crédito Completo
```
El modelo Card YA tiene:
├── ultimos_4_digitos
├── tipo (débito/crédito)
├── limite_credito
├── fecha_corte (día del mes)
├── fecha_vencimiento (día de pago)
├── current_balance
├── interest_rate_annual (52% típico BAC)
└── minimum_payment_percentage

LO QUE FALTA:
├── BillingCycle model (ciclo específico con fechas reales)
├── Cálculo automático de deuda actual del período
├── Alertas "Tu tarjeta vence en 3 días"
├── Historial de pagos a tarjeta
└── "Pagaste mínimo, vas a pagar ₡4,333 de intereses"
```

### 🔵 Después
```
- UI Patrimonio en Streamlit (página nueva)
- Detector de suscripciones
- Streaks/gamification
- Metas con UI bonita
```

---

## 🎮 Features de Engagement

### Streaks
```
🔥 Llevas 15 días sin compras impulsivas
🎯 Meta: 30 días → Desbloqueas badge "Disciplinado"
```

### 🔔 Sistema de Notificaciones de Tarjetas

```
FLUJO AUTOMÁTICO:

1. FECHA DE CORTE (ej: día 15)
   ├── Sistema detecta email de estado de cuenta ✅
   ├── Descarga automáticamente el PDF adjunto ✅
   ├── Parsea con BACPDFParser ✅
   ├── Crea BillingCycle con transacciones
   └── Notifica: "Tu estado de cuenta llegó: ₡127,000"

2. RECORDATORIO DE PAGO (3 días antes del vencimiento)
   └── Notifica: "Pagá tu tarjeta BAC antes del 28"
              "Total: ₡127,000 | Mínimo: ₡12,700"

3. FECHA DE PAGO (día 28)
   ├── Sistema busca email de confirmación de pago
   ├── Si NO llega:
   │   └── ⚠️ "No detectamos tu pago. ¿Ya pagaste?"
   └── Si llega:
       └── ✅ "Pago recibido: ₡127,000. ¡Bien!"

4. POST-VENCIMIENTO (si no pagó)
   └── 🚨 "Tu tarjeta venció ayer. Intereses: 52% anual"
```

### 📧 Lectura Automática de Estados de Cuenta

```
IMPLEMENTADO (StatementEmailService):

📬 Cada 4 horas el sistema:
   1. Busca correos de BAC con PDF adjunto
   2. Filtra por asunto "estado de cuenta"
   3. Descarga el PDF vía Microsoft Graph API
   4. Parsea con BACPDFParser
   5. Guarda en data/raw/statements/

API Endpoints:
   GET  /api/v1/statements/email/search      → Lista estados disponibles
   POST /api/v1/statements/email/process-all → Procesa todos pendientes
   POST /api/v1/statements/email/process/{id}→ Procesa uno específico

¡Ya no tienes que subir PDFs manualmente! 🎉
```

### Alertas Adicionales
```
💳 Tu tarjeta BAC vence en 3 días
   Total: ₡127,000 | Mínimo: ₡12,700
   [Pagar ahora] [Recordar mañana]
```

### Educación Contextual
```
📚 Veo que pagaste solo el mínimo de tu tarjeta.
   
   ¿Sabías que el interés de BAC es 52% anual?
   Sobre ₡100,000, pagarás ₡4,333 extra este mes.
   
   💡 Tip: Siempre paga el total si puedes.
```

### Celebraciones
```
🎉 ¡GOOOL! Llegaste al 80% de tu meta "Mundial 2026"

   ₡4,000,000 / ₡5,000,000
   ████████░░

   A este ritmo, llegas en Oct 2026 ✅
```

---

## 🧮 Calculadoras Inteligentes

### Contado vs Cuotas
```
Marchamo ₡350,000

📊 Análisis:
├── Contado: Pierdes ₡2,200 de intereses CDP
├── 6 cuotas: Pagas ₡5,250 de comisión
└── Diferencia: Contado ahorra ₡3,050

✅ Recomendación: Paga de contado
```

### Proyección de Metas
```
📈 A tu ritmo actual (₡150K/mes ahorro):

Meta                   | Tiempo    | Fecha
-----------------------|-----------|----------
Fondo emergencia ₡1.5M | 10 meses  | Oct 2026
Mundial ₡5M            | Ya tienes | ✅
Marchamo ₡350K         | 2 meses   | Feb 2026
```

### Simulador "¿Y si...?"
```
¿Qué pasa si...

[  ] Aumento de salario +₡200K/mes
[  ] Reduzco gustos a 20%
[  ] Cancelo Netflix + Spotify

Resultado: Llegas a tu meta 4 meses antes 🚀
```

---

## 🔧 Mejoras Técnicas

### Autenticación Real
```python
# JWT con PyJWT
@app.post("/auth/login")
async def login(email: str, password: str) -> Token:
    user = authenticate(email, password)
    token = create_jwt(user.id)
    return Token(access_token=token)
```

### Deploy
```
Railway (API + Worker)
  └── PostgreSQL + pgvector
  
Vercel (Frontend Next.js)

Supabase (Auth, opcional)
```

### Pipeline ETL
```
Prefect/Dagster
├── fetch_emails (cada hora)
├── parse_transactions
├── categorize_with_ai
├── generate_embeddings
└── update_balances
```

### RAG Mejorado
```python
# No prompts hardcodeados
class PromptTemplate:
    nombre: str
    version: str
    template: str
    activo: bool

# Evaluación con RAGAS
def evaluate_rag_quality():
    metrics = ["faithfulness", "answer_relevancy", "context_precision"]
    return ragas.evaluate(dataset, metrics)
```

---

## 📅 Roadmap

> Ver [HONEST_ANALYSIS.md](./HONEST_ANALYSIS.md) para el plan detallado con fechas

### Resumen (8 semanas)

| Sprint | Foco | Semanas |
|--------|------|---------|
| 0 | Credibilidad (tests, JWT, deploy) | 1 |
| 1 | Patrimonio MVP (Account, Investment, Goal) | 2-3 |
| 2 | Engagement (streaks, suscripciones, alertas) | 4-5 |
| 3 | Inteligencia CR (aguinaldo, liquidación) | 6-7 |
| 4 | Producción (frontend, beta usuarios) | 8 |

---

## 💭 Ideas Futuras

- 📱 App móvil (React Native)
- 🤝 Grupos familiares (compartir gastos)
- 🏆 Challenges entre amigos
- 📷 OCR de facturas físicas
- 🔗 Open Banking (cuando exista en CR)

---

## 🎯 Norte

> "La app de finanzas personales hecha para ticos"

---

*Documento vivo. Última actualización: 1 Dic 2025*
