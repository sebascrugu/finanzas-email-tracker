# 🔄 Sistema de Reconciliación con Estados de Cuenta PDF

## 📋 Descripción General

El sistema de reconciliación de PDFs permite **validar que todas las transacciones de tu estado de cuenta bancario estén en el sistema**, detectando:

- ✅ **Correos no recibidos** - Transacciones en el PDF pero no en tus emails
- ⚠️ **Transacciones duplicadas** - Emails duplicados que no deberían estar
- 💰 **Discrepancias** - Diferencias de monto entre PDF y emails
- 📊 **Completitud** - % de matching entre fuentes de datos

## 🎯 Casos de Uso

### 1. **Validación Mensual**
Procesa tu estado de cuenta mensual para validar que recibiste todos los correos de notificación del banco.

### 2. **Detección de Correos Perdidos**
Identifica transacciones que el banco registró pero de las que nunca recibiste notificación por correo.

### 3. **Auditoría de Datos**
Verifica que no haya duplicados o transacciones con montos incorrectos en tu sistema.

### 4. **Completar Historial**
Agrega transacciones faltantes para tener un registro 100% completo y confiable.

---

## 🏗️ Arquitectura del Sistema

### Componentes Principales

```
┌─────────────────────────────────────────────────────────────┐
│                  1. Upload PDF                              │
│  Usuario sube estado de cuenta (BAC/Popular)               │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│          2. Claude Vision API                               │
│  Extrae tabla de transacciones del PDF                     │
│  • Fecha, comercio, monto, tipo, referencia                │
│  • Metadata: saldo inicial/final, totales                  │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│          3. Fuzzy Matching Algorithm                        │
│  Compara PDF vs Emails usando:                             │
│  • Nombre de comercio (exact/fuzzy match)                  │
│  • Monto (exact, ±1%, ±5%)                                  │
│  • Fecha (misma, ±1 día, ±3 días)                          │
│  → Score 0-100 con confidence levels                       │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│          4. Reconciliation Report                           │
│  Genera reporte con:                                        │
│  • ✅ Matched (high/medium/low confidence)                  │
│  • ⚠️ Missing in emails                                     │
│  • ❓ Missing in statement                                  │
│  • 💰 Discrepancies                                         │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│          5. Storage & Dashboard                             │
│  Guarda en DB (BankStatement model)                        │
│  Muestra en UI con acciones:                               │
│  • Ver detalles de cada match                              │
│  • Agregar transacciones faltantes                         │
│  • Exportar reporte                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Modelos de Datos

### BankStatement

```python
class BankStatement:
    """Estado de cuenta bancario procesado."""

    # Identificación
    id: str  # UUID
    profile_id: str

    # Info del estado
    banco: BankName  # BAC/Popular
    cuenta_iban: str  # "CR72 0102 0000 9661 5395 99"
    fecha_corte: date  # 2025-10-31
    periodo: str  # "Octubre 2025"

    # Metadata del PDF
    pdf_filename: str
    pdf_hash: str  # SHA-256 para detectar duplicados

    # Datos extraídos
    saldo_inicial: Decimal
    saldo_final: Decimal
    total_debitos: Decimal
    total_creditos: Decimal

    # Estadísticas de reconciliación
    total_transactions_pdf: int
    matched_count: int
    missing_in_emails_count: int
    missing_in_statement_count: int
    discrepancies_count: int

    # Reporte JSON completo
    reconciliation_report: dict

    # Estado
    processing_status: str  # pending/processing/completed/failed
```

### Schemas de Reconciliación

**ParsedPDFTransaction**
```python
@dataclass
class ParsedPDFTransaction:
    fecha: date
    referencia: str
    comercio: str
    tipo_transaccion: TransactionType
    monto: Decimal
    moneda: Currency
    row_number: int
```

**MatchResult**
```python
@dataclass
class MatchResult:
    pdf_transaction: ParsedPDFTransaction
    email_transaction: Transaction | None
    match_score: float  # 0-100
    match_confidence: str  # high/medium/low/no_match
    match_reasons: list[str]
    status: str  # matched/missing_in_email/discrepancy
```

**ReconciliationReport**
```python
@dataclass
class ReconciliationReport:
    statement_id: str
    summary: ReconciliationSummary
    matched_transactions: list[MatchResult]
    missing_in_emails: list[ParsedPDFTransaction]
    missing_in_statement: list[Transaction]
    discrepancies: list[MatchResult]
```

---

## 🔧 Servicios

### PDFReconciliationService

**Método Principal:**
```python
def process_bank_statement(
    pdf_content: bytes,
    profile_id: str,
    banco: BankName,
    fecha_corte: date | None = None,
    pdf_filename: str = "statement.pdf",
) -> ReconciliationReport:
    """
    Procesa un estado de cuenta PDF completo.

    Returns:
        ReconciliationReport con resultados completos
    """
```

**Flujo Interno:**
1. **Validación** - Hash del PDF para detectar duplicados
2. **Extracción** - Claude Vision API → Transacciones estructuradas
3. **Matching** - Fuzzy matching con scoring algorithm
4. **Clasificación** - High/Medium/Low confidence + discrepancias
5. **Storage** - Guardar en BankStatement + Report JSON
6. **Return** - ReconciliationReport completo

---

## 🎨 UI Dashboard

### Página: `12_Reconciliacion.py`

**Sección 1: Upload**
- File uploader (PDF)
- Selector de banco (BAC/Popular)
- Date picker para fecha de corte
- Botón "Procesar Estado de Cuenta"

**Sección 2: Resumen**
- Métricas clave:
  - Total PDF vs Total Emails
  - Matched count y %
  - Missing in emails/PDF
  - Discrepancies
- Status visual: Perfect ✅ / Good 👍 / Needs Review ⚠️

**Sección 3: Detalles (Tabs)**
- **Tab 1: Matched** - Tabla con todas las transacciones matched
  - Filtro por confidence (high/medium/low)
  - Expandible para ver detalles PDF vs Email
- **Tab 2: Missing in Emails** - Transacciones faltantes
  - Botón "Agregar" por transacción
  - Botón "Agregar todas"
- **Tab 3: Missing in PDF** - Transacciones extras en emails
- **Tab 4: Discrepancies** - Diferencias de monto/fecha

**Sección 4: Historial**
- Lista de estados procesados anteriormente
- Filtros por banco, fecha, status
- Re-abrir reportes anteriores

---

## 🚀 Cómo Usar

### 1. Preparación

```bash
# Instalar dependencias (si es necesario)
poetry install

# Aplicar migración de base de datos
poetry run alembic upgrade head

# Iniciar dashboard
poetry run streamlit run src/finanzas_tracker/dashboard/app.py
```

### 2. Navegar a Reconciliación

1. Ir a la página **"🔄 Reconciliación"** en el sidebar
2. Seleccionar tab **"📤 Nuevo Estado de Cuenta"**

### 3. Procesar Estado de Cuenta

1. **Upload PDF**
   - Click en "Sube tu estado de cuenta PDF"
   - Selecciona el archivo PDF del banco

2. **Configurar**
   - **Banco**: BAC o Popular
   - **Fecha de corte**: Fecha del estado (ej: 2025-10-31)

3. **Procesar**
   - Click en "🔄 Procesar Estado de Cuenta"
   - Espera mientras Claude Vision extrae las transacciones
   - Espera el matching con tus emails

4. **Revisar Resultados**
   - Ver resumen general
   - Explorar cada sección:
     - ✅ Matched - Transacciones correctamente matched
     - ⚠️ Faltantes en Emails - Correos no recibidos
     - 💰 Discrepancias - Diferencias encontradas

5. **Tomar Acciones**
   - Agregar transacciones faltantes al sistema
   - Revisar discrepancias manualmente
   - Exportar reporte (próximamente)

---

## 🧪 Ejemplo con tu PDF de BAC

### PDF: `_Extracto_202510_0000_2424_48540997.pdf`

**Datos Extraídos:**
```json
{
  "cuenta_iban": "CR72 0102 0000 9661 5395 99",
  "fecha_corte": "2025-10-31",
  "periodo": "Octubre 2025",
  "saldo_inicial": -1599.49,
  "saldo_final": 120000.42,
  "total_debitos": 338642.91,
  "total_creditos": 460242.82,
  "transactions": [
    {
      "fecha": "2025-09-27",
      "referencia": "093006688",
      "concepto": "COMPASS RUTA 32 RUTA 2",
      "tipo": "debito",
      "monto": 150.00
    },
    // ... 41 transacciones más
  ]
}
```

**Resultados Esperados:**
- **Total PDF**: 42 transacciones
- **Matched**: ~38-40 (90-95%)
- **Missing in Emails**: 2-4 transacciones
  - Ejemplo: COMPASS del 27/SEP (posible correo no recibido)
  - Ejemplo: SINPE MOVIL (no genera email)
- **Discrepancies**: 0 (todos los montos coinciden)

---

## 🔍 Algoritmo de Matching

### Scoring System

**Total Score: 100 puntos**

| Criterio | Puntos Máximos | Condiciones |
|----------|---------------|-------------|
| **Comercio** | 30 | - Exact match: 30<br>- Substring match: 25<br>- No match: skip |
| **Monto** | 40 | - Exact (±₡0.01): 40<br>- ±1%: 30<br>- ±5%: 20<br>- >5%: skip |
| **Fecha** | 30 | - Misma fecha: 30<br>- ±1 día: 20<br>- ±3 días: 10 |

**Confidence Levels:**
- **High**: Score ≥ 90% → Auto-match
- **Medium**: Score 70-90% → Sugerencia para revisión
- **Low**: Score 50-70% → Requiere revisión manual
- **No Match**: Score < 50% → Missing in emails

### Ejemplo de Matching

```python
# PDF
{
  "fecha": "2025-10-03",
  "comercio": "COMPASS RUTA 32 RUTA 2",
  "monto": 150.00
}

# Email
{
  "fecha_transaccion": "2025-10-03",
  "comercio": "Compass Ruta 32",
  "monto_crc": 150.00
}

# Scoring
comercio_score = 25  # Substring match
monto_score = 40     # Exact match
fecha_score = 30     # Same date
total_score = 95     # HIGH CONFIDENCE ✅
```

---

## 🛠️ Configuración Avanzada

### Claude Vision API

**Modelo usado:** `claude-3-5-sonnet-20241022`

**Parámetros:**
- `max_tokens`: 8000 (para PDFs grandes)
- `temperature`: 0 (determinístico para extracción)

**Costo estimado:**
- ~$0.10 - $0.30 por PDF (dependiendo del tamaño)
- Input: PDF completo (~20-50 páginas típico)
- Output: JSON estructurado (~2000 tokens)

### Personalización del Prompt

Editar `PDFReconciliationService._build_extraction_prompt()`:

```python
def _build_extraction_prompt(self, banco: BankName) -> str:
    # Personalizar prompt según formato del banco
    if banco == BankName.BAC:
        return """Eres un experto en BAC Credomatic..."""
    elif banco == BankName.POPULAR:
        return """Eres un experto en Banco Popular..."""
```

---

## 🐛 Troubleshooting

### Error: "PDF ya procesado anteriormente"

**Causa:** El hash del PDF ya existe en la base de datos.

**Solución:**
- Si quieres re-procesar, elimina el statement anterior del historial
- O modifica el PDF ligeramente (agregar una nota)

### Error: "No se pudo parsear respuesta de Claude"

**Causa:** Claude no retornó JSON válido.

**Solución:**
1. Verifica que el PDF sea legible (no escaneo de mala calidad)
2. Revisa logs para ver la respuesta cruda de Claude
3. Ajusta el prompt si es necesario

### Missing transacciones incorrectas

**Causa:** Fuzzy matching no es lo suficientemente flexible.

**Solución:**
- Ajustar threshold de similarity en `_find_matching_candidates()`
- Modificar scoring weights (comercio vs monto vs fecha)

---

## 📊 Métricas & Performance

### Tiempos Estimados

- **Extracción PDF** (Claude Vision): 10-30s
- **Matching** (100 transacciones): 1-3s
- **Storage**: <1s
- **Total**: ~15-35s por PDF

### Precisión Esperada

- **Matching accuracy**: 90-95% auto-matched con high confidence
- **False positives**: <1%
- **False negatives**: ~5-10% (requieren revisión manual)

---

## 🚦 Próximos Pasos

### Features a Implementar

- [ ] **Agregar transacciones faltantes** - Un click para agregar al sistema
- [ ] **Exportar reporte** - PDF/Excel con detalles completos
- [ ] **Categorización automática** - Categorizar transacciones nuevas con IA
- [ ] **Alertas inteligentes** - Notificar cuando falten correos importantes
- [ ] **Soporte multi-banco** - Agregar más bancos de Costa Rica
- [ ] **Análisis histórico** - Tendencias de correos perdidos por mes
- [ ] **API pública** - Endpoint para integración externa

### Mejoras Técnicas

- [ ] **Caching de resultados** - Evitar re-procesar PDFs idénticos
- [ ] **Batch processing** - Procesar múltiples PDFs a la vez
- [ ] **OCR fallback** - Si PDF es imagen escaneada
- [ ] **Machine Learning** - Mejorar matching con modelo entrenado

---

## 🤝 Contribuir

¿Ideas para mejorar el sistema de reconciliación?

1. Fork el repo
2. Crea una branch: `git checkout -b feature/mejora-matching`
3. Commit cambios: `git commit -m "Mejora matching algorithm"`
4. Push: `git push origin feature/mejora-matching`
5. Abre un Pull Request

---

## 📄 Licencia

Este proyecto está bajo la licencia MIT.

---

## 💬 Soporte

¿Preguntas? ¿Problemas?

- 📧 Email: tu-email@ejemplo.com
- 🐛 Issues: [GitHub Issues](https://github.com/tu-usuario/finanzas-email-tracker/issues)
- 📚 Docs: [Documentation](https://github.com/tu-usuario/finanzas-email-tracker/docs)

---

**¡Desarrollado con ❤️ en Costa Rica! 🇨🇷**
