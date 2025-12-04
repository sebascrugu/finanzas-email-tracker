# 🔄 Flujo Completo del Sistema de Finanzas

**Fecha:** 3 de Diciembre, 2025  
**Estado:** Documentación de diseño  
**Autor:** Sebastian Cruz + GitHub Copilot

---

## 📋 Tabla de Contenidos

1. [Visión General](#visión-general)
2. [Fase 1: Registro y Onboarding](#fase-1-registro-y-onboarding)
3. [Fase 2: Operación Continua](#fase-2-operación-continua)
4. [Fase 3: Reconciliación Mensual](#fase-3-reconciliación-mensual)
5. [Conceptos Críticos](#conceptos-críticos)
6. [Modelo de Datos](#modelo-de-datos)
7. [Casos Edge](#casos-edge)

---

## 🎯 Visión General

El sistema automatiza el tracking de finanzas personales para usuarios en Costa Rica, integrándose con BAC Credomatic vía email. El flujo tiene tres fases principales:

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  REGISTRO   │────▶│ OPERACIÓN DIARIA │────▶│ RECONCILIACIÓN  │
│  (1 vez)    │     │   (continuo)     │     │   (mensual)     │
└─────────────┘     └──────────────────┘     └─────────────────┘
```

---

## 📝 Fase 1: Registro y Onboarding

### 1.1 Flujo de Registro

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PASO 1: CREAR CUENTA                                                       │
│  └── Email + Password                                                       │
│  └── Crear Profile en BD                                                    │
│                                                                             │
│  PASO 2: CONECTAR EMAIL (Microsoft Graph)                                   │
│  └── OAuth2 con Outlook                                                     │
│  └── Guardar token de acceso                                                │
│                                                                             │
│  PASO 3: BÚSQUEDA AUTOMÁTICA DE ESTADOS DE CUENTA                           │
│  │                                                                          │
│  ├── 🔍 Buscar emails de "estadodecuenta@baccredomatic.cr" (tarjetas)       │
│  └── 🔍 Buscar emails de "estadosdecuenta@baccredomatic.cr" (cuentas)       │
│                                                                             │
│  PASO 4: DETERMINAR FECHA BASE                                              │
│  │                                                                          │
│  ├── ✅ SI encontró estado de cuenta (últimos 45 días):                     │
│  │   └── FECHA_BASE = fecha_corte del PDF más reciente                      │
│  │   └── Extraer saldos automáticamente del PDF                             │
│  │   └── Registrar cuentas/tarjetas detectadas                              │
│  │                                                                          │
│  └── ❌ NO encontró estado de cuenta:                                       │
│      └── FECHA_BASE = fecha_registro (hoy)                                  │
│      └── Pedir al usuario que ingrese manualmente:                          │
│          • Saldo de cada cuenta                                             │
│          • Límite y deuda de cada tarjeta                                   │
│                                                                             │
│  PASO 5: ESTABLECER PATRIMONIO INICIAL                                      │
│  └── patrimonio = Σ(saldos_cuentas) - Σ(deudas_tarjetas)                    │
│  └── Guardar snapshot: PatrimonioSnapshot(fecha=FECHA_BASE, monto=X)        │
│                                                                             │
│  PASO 6: IMPORTAR HISTORIAL (OPCIONAL)                                      │
│  └── Buscar transacciones desde (FECHA_BASE - 60 días) hasta FECHA_BASE     │
│  └── Marcar TODAS como `es_historica = True`                                │
│  └── ⚠️ NO afectan el patrimonio actual                                     │
│  └── Solo sirven para análisis de patrones de gasto                         │
│                                                                             │
│  PASO 7: IMPORTAR TRANSACCIONES POST-REGISTRO                               │
│  └── Si hay días entre FECHA_BASE y HOY:                                    │
│      └── Buscar emails de alertas de transacciones                          │
│      └── Estas SÍ afectan patrimonio (`es_historica = False`)               │
│      └── Calcular saldo actual = saldo_base + ingresos - gastos             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Ejemplo Práctico

```
Escenario:
  - Usuario se registra: 3 de Diciembre 2025
  - Último estado de cuenta encontrado: corte 15 de Noviembre 2025
  - Saldo en PDF: ₡500,000

Proceso:
  1. FECHA_BASE = 15/Nov/2025
  2. Patrimonio inicial (al 15/Nov) = ₡500,000
  3. Importar historial: transacciones del 15/Sep al 15/Nov (es_historica=True)
  4. Importar recientes: transacciones del 16/Nov al 3/Dic (es_historica=False)
  5. Calcular saldo actual:
     - Gastos 16/Nov-3/Dic: ₡85,000
     - Ingresos 16/Nov-3/Dic: ₡0
     - Saldo estimado HOY: ₡500,000 - ₡85,000 = ₡415,000
```

---

## ⚡ Fase 2: Operación Continua

### 2.1 Fetch Automático de Emails

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  📬 CADA 4-6 HORAS (configurable)                                           │
│                                                                             │
│  Buscar nuevos emails de BAC:                                               │
│                                                                             │
│  TIPO A: ALERTAS DE TRANSACCIONES                                           │
│  ├── Remitente: notificaciones@baccredomatic.cr                             │
│  ├── Asunto: "Compra aprobada", "SINPE enviado", etc.                       │
│  └── Acción:                                                                │
│      └── Parsear email                                                      │
│      └── Crear Transaction con estado = "pendiente"                         │
│      └── Categorizar automáticamente                                        │
│      └── Si es cuenta débito → Actualizar saldo estimado                    │
│      └── Si es tarjeta crédito → Solo registrar (no afecta patrimonio)      │
│                                                                             │
│  TIPO B: ESTADOS DE CUENTA (mensual)                                        │
│  ├── Remitente: estadodecuenta@ o estadosdecuenta@                          │
│  ├── Asunto: "Estado de cuenta"                                             │
│  ├── Adjunto: PDF                                                           │
│  └── Acción:                                                                │
│      └── Descargar PDF                                                      │
│      └── Parsear con BACPDFParser / BACCreditCardParser                     │
│      └── 🔄 INICIAR PROCESO DE RECONCILIACIÓN                               │
│                                                                             │
│  TIPO C: CONFIRMACIONES DE PAGO                                             │
│  ├── "Pago recibido en tu tarjeta"                                          │
│  └── Acción:                                                                │
│      └── Marcar como transferencia interna                                  │
│      └── Reducir deuda de tarjeta                                           │
│      └── Reducir saldo de cuenta origen                                     │
│      └── Patrimonio neto NO cambia                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Actualización de Patrimonio en Tiempo Real

```python
# Pseudocódigo del flujo

def procesar_transaccion_nueva(tx: Transaction):
    """Procesa una transacción nueva y actualiza patrimonio."""
    
    # 1. Determinar si afecta patrimonio
    if tx.es_historica:
        return  # No afecta, solo para análisis
    
    # 2. Categorizar tipo de transacción
    if es_pago_tarjeta(tx):
        # Transferencia interna - patrimonio neto no cambia
        tx.tipo = "transferencia_interna"
        cuenta = get_cuenta_origen(tx)
        tarjeta = get_tarjeta_destino(tx)
        
        cuenta.saldo -= tx.monto
        tarjeta.deuda -= tx.monto
        # Patrimonio = saldo - deuda = igual
        
    elif tx.es_tarjeta_credito:
        # Solo aumenta deuda, no afecta cuentas
        tarjeta = get_tarjeta(tx)
        tarjeta.deuda += tx.monto
        # Patrimonio baja por aumento de deuda
        
    else:  # Débito, transferencia, SINPE
        cuenta = get_cuenta(tx)
        if tx.tipo == "credito":  # Ingreso
            cuenta.saldo += tx.monto
        else:  # Gasto
            cuenta.saldo -= tx.monto
    
    # 3. Recalcular patrimonio total
    patrimonio = sum(c.saldo for c in cuentas) - sum(t.deuda for t in tarjetas)
    guardar_snapshot(patrimonio, fecha=now())
```

---

## 🔄 Fase 3: Reconciliación Mensual

### 3.1 ¿Qué es la Reconciliación?

Cuando llega el estado de cuenta mensual (PDF), comparamos las transacciones que el banco reporta contra las que nosotros tenemos registradas de los emails de alertas.

### 3.2 Proceso de Reconciliación

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  📄 LLEGA ESTADO DE CUENTA (PDF)                                            │
│                                                                             │
│  PASO 1: PARSEAR PDF                                                        │
│  └── Extraer todas las transacciones del período                            │
│  └── Extraer saldo final                                                    │
│  └── Extraer fecha de corte                                                 │
│                                                                             │
│  PASO 2: OBTENER TRANSACCIONES EN BD                                        │
│  └── SELECT * FROM transactions                                             │
│      WHERE fecha BETWEEN inicio_periodo AND fin_periodo                     │
│      AND card_id = X (o account_id = Y)                                     │
│                                                                             │
│  PASO 3: ALGORITMO DE MATCHING                                              │
│  │                                                                          │
│  │  Para cada transacción del PDF:                                          │
│  │    Buscar match en BD por:                                               │
│  │      - Fecha (±1 día de tolerancia)                                      │
│  │      - Monto (±5% tolerancia para tipo de cambio)                        │
│  │      - Comercio (fuzzy matching)                                         │
│  │                                                                          │
│  PASO 4: CLASIFICAR RESULTADOS                                              │
│  │                                                                          │
│  ├── ✅ MATCH PERFECTO                                                      │
│  │   └── PDF.tx == BD.tx                                                    │
│  │   └── Marcar BD.tx como reconciliada = True                              │
│  │   └── Cambiar estado: "pendiente" → "confirmada"                         │
│  │                                                                          │
│  ├── 🆕 NUEVA (en PDF, no en BD)                                            │
│  │   └── Transacción que no teníamos                                        │
│  │   └── Crear nueva transacción en BD                                      │
│  │   └── Generar alerta: "Transacción no detectada previamente"             │
│  │   └── Posibles causas:                                                   │
│  │       • Cobro recurrente (Netflix, Spotify)                              │
│  │       • Email de alerta no llegó                                         │
│  │       • Transacción en sucursal/cajero                                   │
│  │                                                                          │
│  ├── 🔍 HUÉRFANA (en BD, no en PDF)                                         │
│  │   └── Tenemos registro pero banco no la reporta                          │
│  │   └── Marcar como estado = "huerfana"                                    │
│  │   └── Generar alerta: "Esta transacción no apareció"                     │
│  │   └── Posibles causas:                                                   │
│  │       • Reversión/cancelación                                            │
│  │       • Transacción pendiente (aparecerá próximo mes)                    │
│  │       • Error de nuestro parser                                          │
│  │                                                                          │
│  ├── ⚠️ DISCREPANCIA DE MONTO                                               │
│  │   └── Misma transacción, diferente monto                                 │
│  │   └── Actualizar monto en BD                                             │
│  │   └── Registrar: monto_original, monto_ajustado, razon_ajuste            │
│  │   └── Generar alerta con diferencia                                      │
│  │   └── Posibles causas:                                                   │
│  │       • Propina agregada (restaurantes)                                  │
│  │       • Tipo de cambio ajustado (compras USD)                            │
│  │       • Cobro parcial → total (hoteles, gasolineras)                     │
│  │                                                                          │
│  └── 🚨 DUPLICADO SOSPECHOSO                                                │
│      └── 2+ transacciones muy similares mismo día                           │
│      └── Generar alerta: "Posible doble cobro"                              │
│      └── Usuario debe confirmar si es correcto                              │
│                                                                             │
│  PASO 5: VERIFICAR SALDO                                                    │
│  └── saldo_calculado = saldo_anterior + ingresos - gastos                   │
│  └── saldo_pdf = lo que dice el estado de cuenta                            │
│  └── diferencia = saldo_pdf - saldo_calculado                               │
│  └── Si diferencia > ₡100 → Investigar                                      │
│                                                                             │
│  PASO 6: GENERAR REPORTE                                                    │
│  └── ReconciliationReport con estadísticas                                  │
│  └── Lista de alertas para el usuario                                       │
│  └── Actualizar saldo real de la cuenta/tarjeta                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Algoritmo de Matching (Detallado)

```python
def encontrar_match(tx_pdf: Transaction, transacciones_bd: list) -> MatchResult:
    """
    Busca la transacción de BD que mejor matchea con la del PDF.
    
    Criterios de matching (en orden de peso):
    1. Referencia exacta (si disponible) - 100% match
    2. Fecha + Monto + Comercio similar - 95%+ match
    3. Fecha + Monto (comercio diferente) - 80% match
    4. Solo monto similar en rango de fechas - 60% match
    """
    
    candidatos = []
    
    for tx_bd in transacciones_bd:
        score = 0
        
        # Criterio 1: Referencia exacta
        if tx_pdf.referencia and tx_pdf.referencia == tx_bd.referencia_banco:
            return MatchResult(tx_bd, score=100, tipo="exacto")
        
        # Criterio 2: Fecha cercana
        diff_dias = abs((tx_pdf.fecha - tx_bd.fecha).days)
        if diff_dias == 0:
            score += 40
        elif diff_dias == 1:
            score += 30
        elif diff_dias <= 3:
            score += 15
        else:
            continue  # Muy lejos, descartar
        
        # Criterio 3: Monto similar
        diff_monto = abs(tx_pdf.monto - tx_bd.monto) / tx_pdf.monto
        if diff_monto == 0:
            score += 40
        elif diff_monto < 0.05:  # 5% tolerancia
            score += 30
        elif diff_monto < 0.15:  # 15% tolerancia
            score += 15
        else:
            continue  # Monto muy diferente
        
        # Criterio 4: Comercio similar
        similitud = fuzzy_match(tx_pdf.comercio, tx_bd.comercio)
        score += similitud * 20  # Max 20 puntos
        
        candidatos.append(MatchResult(tx_bd, score, tipo="fuzzy"))
    
    if not candidatos:
        return None
    
    # Retornar el mejor candidato
    mejor = max(candidatos, key=lambda x: x.score)
    
    if mejor.score >= 80:
        return mejor
    elif mejor.score >= 60:
        mejor.requiere_confirmacion = True
        return mejor
    else:
        return None  # No hay match confiable
```

---

## 🎯 Conceptos Críticos

### 5.1 Diferencia: Cuenta Corriente vs Tarjeta de Crédito

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  💳 TARJETA DE CRÉDITO                    🏦 CUENTA CORRIENTE/AHORROS       │
│  ─────────────────────────                ─────────────────────────────     │
│                                                                             │
│  • Es un PASIVO (deuda)                   • Es un ACTIVO (dinero tuyo)      │
│                                                                             │
│  • Compras NO salen de tu                 • Compras SÍ salen de tu          │
│    cuenta inmediatamente                    cuenta inmediatamente           │
│                                                                             │
│  • Solo cuando PAGAS la                   • Cada transacción mueve          │
│    tarjeta, sale dinero                     dinero real                     │
│                                                                             │
│  • Afecta patrimonio como                 • Afecta patrimonio               │
│    AUMENTO de deuda                         directamente                    │
│                                                                             │
│  Fórmula de Patrimonio:                                                     │
│  ──────────────────────                                                     │
│  PATRIMONIO = Σ(Cuentas) + Σ(Inversiones) - Σ(Deudas_Tarjetas)             │
│                                                                             │
│  Ejemplo:                                                                   │
│  ─────────                                                                  │
│  Cuenta BAC:     ₡500,000                                                   │
│  CDP:            ₡1,000,000                                                 │
│  Deuda VISA:    -₡127,000                                                   │
│  ────────────────────────                                                   │
│  PATRIMONIO:    ₡1,373,000                                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Pagos de Tarjeta = Transferencia Interna

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  Cuando pagas tu tarjeta BAC desde tu cuenta BAC:                           │
│                                                                             │
│  ANTES:                           DESPUÉS:                                  │
│  ───────                          ────────                                  │
│  Cuenta:  ₡500,000                Cuenta:  ₡373,000 (-₡127,000)             │
│  Deuda:   ₡127,000                Deuda:   ₡0       (-₡127,000)             │
│  ───────────────────              ───────────────────                       │
│  Patrimonio: ₡373,000             Patrimonio: ₡373,000                      │
│                                                                             │
│  ⚠️ EL PATRIMONIO NO CAMBIA                                                 │
│                                                                             │
│  Por eso los pagos de tarjeta son "transferencias internas"                 │
│  y NO deben contarse como gastos en el presupuesto.                         │
│                                                                             │
│  En la BD:                                                                  │
│  ─────────                                                                  │
│  Transaction {                                                              │
│    tipo: "transferencia_interna",                                           │
│    cuenta_origen_id: "cuenta_corriente_bac",                                │
│    cuenta_destino_id: "visa_bac",                                           │
│    excluir_de_presupuesto: true                                             │
│  }                                                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Transacciones Históricas vs Activas

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  FECHA_BASE = Momento en que establecemos el patrimonio inicial             │
│                                                                             │
│  ┌──────────────────────────┬──────────────────────────────────────┐        │
│  │      HISTÓRICAS          │            ACTIVAS                   │        │
│  │   (es_historica=true)    │      (es_historica=false)            │        │
│  ├──────────────────────────┼──────────────────────────────────────┤        │
│  │                          │                                      │        │
│  │  • Antes de FECHA_BASE   │  • Después de FECHA_BASE             │        │
│  │                          │                                      │        │
│  │  • NO afectan patrimonio │  • SÍ afectan patrimonio             │        │
│  │    (ya están incluidas   │    (son movimientos nuevos)          │        │
│  │     en el saldo base)    │                                      │        │
│  │                          │                                      │        │
│  │  • Solo para análisis:   │  • Actualización en tiempo real:     │        │
│  │    - Patrones de gasto   │    - Saldo de cuentas                │        │
│  │    - Categorías          │    - Deuda de tarjetas               │        │
│  │    - Comercios frecuentes│    - Patrimonio neto                 │        │
│  │                          │                                      │        │
│  └──────────────────────────┴──────────────────────────────────────┘        │
│                                                                             │
│  Timeline:                                                                  │
│  ─────────────────────────────────────────────────────────────────────────  │
│  ◀─── PASADO ───|─── FECHA_BASE ───|─── FUTURO ───▶                         │
│     históricas  │                  │    activas                             │
│  (no afectan)   │   patrimonio     │  (sí afectan)                          │
│                 │    inicial       │                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.4 Estados de una Transacción

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  CICLO DE VIDA DE UNA TRANSACCIÓN                                           │
│                                                                             │
│  ┌───────────┐    ┌────────────┐    ┌──────────────┐    ┌───────────────┐   │
│  │ PENDIENTE │───▶│ CONFIRMADA │───▶│ RECONCILIADA │ o  │  CANCELADA    │   │
│  └───────────┘    └────────────┘    └──────────────┘    └───────────────┘   │
│        │                │                   │                   │           │
│        │                │                   │                   │           │
│   Viene del        El banco la         Apareció en          No apareció     │
│   email de         procesó             el estado de         en el PDF       │
│   alerta           (1-3 días)          cuenta (PDF)         (reversa)       │
│                                                                             │
│                                                                             │
│  ESTADOS ESPECIALES:                                                        │
│  ───────────────────                                                        │
│                                                                             │
│  • HUÉRFANA: La teníamos pero no apareció en el PDF                         │
│    └── Esperar 1 ciclo más, si no aparece → marcar cancelada                │
│                                                                             │
│  • CON_DISCREPANCIA: El monto del PDF es diferente al que teníamos          │
│    └── Ajustar monto y registrar la razón                                   │
│                                                                             │
│  • DUPLICADO_SOSPECHOSO: Parece un doble cobro                              │
│    └── Requiere confirmación del usuario                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📐 Modelo de Datos

### 6.1 Campos Nuevos en Transaction

```python
class Transaction(Base):
    """Transacción bancaria."""
    
    # ... campos existentes ...
    
    # ═══════════════════════════════════════════════════════════════════
    # NUEVOS CAMPOS PARA FLUJO COMPLETO
    # ═══════════════════════════════════════════════════════════════════
    
    # Control de afectación a patrimonio
    es_historica: bool = False
    """True = antes de FECHA_BASE, no afecta patrimonio actual."""
    
    fecha_registro_sistema: datetime
    """Cuándo importamos esta transacción al sistema."""
    
    # Estado del ciclo de vida
    estado: str = "pendiente"
    """
    Estados posibles:
    - pendiente: Recién importada del email
    - confirmada: El banco la procesó (>3 días o apareció en movimientos)
    - reconciliada: Apareció en estado de cuenta mensual
    - cancelada: Fue revertida/no apareció después de 2 ciclos
    - huerfana: No apareció en el estado de cuenta (investigar)
    """
    
    # Reconciliación
    reconciliacion_id: str | None = None
    """ID del ReconciliationReport donde se verificó."""
    
    reconciliada_en: datetime | None = None
    """Fecha/hora de reconciliación."""
    
    # Transferencias internas
    es_transferencia_interna: bool = False
    """True si es pago de tarjeta u otra transferencia entre cuentas propias."""
    
    cuenta_origen_id: str | None = None
    cuenta_destino_id: str | None = None
    
    # Discrepancias
    monto_original_estimado: Decimal | None = None
    """Monto que calculamos inicialmente (del email)."""
    
    monto_ajustado: Decimal | None = None
    """Monto real según estado de cuenta (si diferente)."""
    
    razon_ajuste: str | None = None
    """tipo_cambio | propina | correccion | otro"""
    
    # Referencia bancaria
    referencia_banco: str | None = None
    """Número de referencia del banco (para matching exacto)."""
```

### 6.2 Nuevo Modelo: ReconciliationReport

```python
class ReconciliationReport(Base):
    """Reporte de reconciliación mensual."""
    
    __tablename__ = "reconciliation_reports"
    
    id: str  # UUID
    tenant_id: UUID | None
    profile_id: str
    
    # Cuenta o tarjeta reconciliada
    card_id: str | None
    account_id: str | None
    
    # Período
    periodo_inicio: date
    periodo_fin: date
    fecha_corte: date  # Fecha de corte del estado de cuenta
    fecha_ejecutada: datetime  # Cuándo se corrió la reconciliación
    
    # Fuente
    pdf_filename: str
    pdf_path: str
    email_id: str  # ID del email de Outlook
    
    # Estadísticas
    total_transacciones_pdf: int
    total_transacciones_bd: int
    
    transacciones_matched: int
    transacciones_nuevas: int  # Solo en PDF
    transacciones_huerfanas: int  # Solo en BD
    discrepancias_monto: int
    duplicados_sospechosos: int
    
    # Saldos
    saldo_anterior: Decimal
    saldo_final_pdf: Decimal
    saldo_calculado: Decimal
    diferencia_saldo: Decimal
    
    # Estado
    estado: str = "pendiente_revision"
    """
    - pendiente_revision: Hay alertas que el usuario debe revisar
    - aprobado: Usuario confirmó que todo está bien
    - con_problemas: Hay discrepancias sin resolver
    """
    
    notas_usuario: str | None = None
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
```

### 6.3 Nuevo Modelo: PatrimonioSnapshot

```python
class PatrimonioSnapshot(Base):
    """Snapshot del patrimonio en un momento dado."""
    
    __tablename__ = "patrimonio_snapshots"
    
    id: str  # UUID
    tenant_id: UUID | None
    profile_id: str
    
    fecha: date
    
    # Desglose
    total_cuentas: Decimal  # Suma de saldos de cuentas
    total_inversiones: Decimal  # CDPs, plazos, etc.
    total_deudas: Decimal  # Deudas de tarjetas
    
    patrimonio_neto: Decimal  # cuentas + inversiones - deudas
    
    # Metadata
    tipo: str = "automatico"
    """
    - inicial: Al momento del registro
    - automatico: Generado diariamente
    - reconciliacion: Después de reconciliar estado de cuenta
    - manual: Ajuste manual del usuario
    """
    
    notas: str | None = None
    
    created_at: datetime
```

### 6.4 Nuevo Enum: TransactionStatus

```python
class TransactionStatus(str, Enum):
    """Estados de una transacción."""
    
    PENDING = "pendiente"
    CONFIRMED = "confirmada"
    RECONCILED = "reconciliada"
    CANCELLED = "cancelada"
    ORPHAN = "huerfana"
    DISPUTED = "en_disputa"
```

---

## ⚠️ Casos Edge

### 7.1 Suscripciones y Cobros Recurrentes

```
PROBLEMA:
  Netflix, Spotify, gimnasio, etc. a veces NO generan email de alerta.
  Solo aparecen en el estado de cuenta mensual.

SOLUCIÓN:
  1. Durante reconciliación, detectar transacciones "nuevas"
  2. Analizar patrón: mismo comercio, mismo monto, cada mes
  3. Marcar como "suscripcion_detectada"
  4. Preguntar al usuario: "Detectamos que pagas Netflix ₡9,990/mes"
  5. Si confirma, agregar a lista de suscripciones
  6. Próximo mes, esperarla y no marcar como "nueva sorpresa"
```

### 7.2 Retiros de Cajero

```
PROBLEMA:
  - Usuario retira ₡50,000 del cajero
  - El sistema lo registra como gasto
  - PERO el usuario gastó ese efectivo en algo más
  - No sabemos en qué

SOLUCIÓN:
  1. Detectar retiros de cajero (concepto incluye "ATM", "CAJERO")
  2. Marcar como "retiro_efectivo"
  3. Crear categoría especial "Efectivo"
  4. OPCIONALMENTE: Preguntar "¿En qué gastaste los ₡50,000?"
  5. Permitir subdividir el retiro en gastos específicos
```

### 7.3 Transacciones en Dólares

```
PROBLEMA:
  - Email de alerta dice "Compra $50.00 en AMAZON"
  - Estimamos: ₡26,000 (tipo de cambio del día)
  - Estado de cuenta dice: ₡26,750 (tipo de cambio del banco)
  - Diferencia: ₡750

SOLUCIÓN:
  1. Guardar monto_original = 50 USD
  2. Guardar monto_estimado_crc = 26,000
  3. En reconciliación, actualizar a monto_real_crc = 26,750
  4. Calcular diferencia_tc = 750
  5. Si diferencia > 5%, alertar al usuario
```

### 7.4 Transacciones Pendientes que Nunca Llegan

```
PROBLEMA:
  - Hicimos una compra el 25/Nov
  - Email de alerta llegó
  - PERO el comercio nunca la cobró (canceló la transacción)
  - Nunca aparece en el estado de cuenta

SOLUCIÓN:
  1. Después de reconciliación, marcar como "huerfana"
  2. Si sigue huérfana en el SIGUIENTE estado de cuenta:
     - Cambiar estado a "cancelada"
     - Revertir el impacto en patrimonio (si era débito)
     - Notificar: "La compra en X nunca se cobró"
```

### 7.5 Pagos en Cuotas (TCC)

```
PROBLEMA:
  - Compraste una TV de ₡500,000 en 12 cuotas
  - El email dice "Compra aprobada ₡500,000"
  - PERO cada mes solo te cobran ₡41,666

SOLUCIÓN:
  1. Detectar patrón de cuotas en el email/concepto
  2. Crear registro especial:
     Transaction {
       monto_total: 500,000,
       es_cuotas: true,
       num_cuotas: 12,
       monto_cuota: 41,666
     }
  3. No afectar patrimonio por 500K
  4. Cada mes, reconciliar la cuota de 41,666
```

---

## 📊 Diagrama de Arquitectura Final

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FINANZAS TRACKER CR                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌──────────────────────────────────────────────────┐   │
│  │             │    │                   SERVICIOS                       │   │
│  │   OUTLOOK   │◀──▶│  ┌────────────────┐  ┌─────────────────────────┐ │   │
│  │   (EMAIL)   │    │  │ EmailFetcher   │  │ TransactionProcessor    │ │   │
│  │             │    │  │                │  │  • Categorización       │ │   │
│  └─────────────┘    │  │ • Alertas      │  │  • Duplicados           │ │   │
│                     │  │ • Estados Cta  │  │  • Patrimonio           │ │   │
│                     │  └────────────────┘  └─────────────────────────┘ │   │
│                     │                                                   │   │
│                     │  ┌────────────────┐  ┌─────────────────────────┐ │   │
│                     │  │ PDFParser      │  │ ReconciliationService   │ │   │
│                     │  │                │  │  • Matching             │ │   │
│                     │  │ • Credit Card  │  │  • Discrepancias        │ │   │
│                     │  │ • Bank Account │  │  • Reportes             │ │   │
│                     │  └────────────────┘  └─────────────────────────┘ │   │
│                     │                                                   │   │
│                     │  ┌────────────────┐  ┌─────────────────────────┐ │   │
│                     │  │ PatrimonioSvc  │  │ NotificationService     │ │   │
│                     │  │                │  │  • Alertas              │ │   │
│                     │  │ • Snapshots    │  │  • Discrepancias        │ │   │
│                     │  │ • Cálculos     │  │  • Recordatorios        │ │   │
│                     │  └────────────────┘  └─────────────────────────┘ │   │
│                     └──────────────────────────────────────────────────┘   │
│                                          │                                  │
│                                          ▼                                  │
│                     ┌──────────────────────────────────────────────────┐   │
│                     │                  BASE DE DATOS                    │   │
│                     │  ┌──────────────┐  ┌─────────────────────────┐   │   │
│                     │  │ Transactions │  │ ReconciliationReports   │   │   │
│                     │  │ • 207 filas  │  │                         │   │   │
│                     │  └──────────────┘  └─────────────────────────┘   │   │
│                     │  ┌──────────────┐  ┌─────────────────────────┐   │   │
│                     │  │ Cards        │  │ PatrimonioSnapshots     │   │   │
│                     │  │ BillingCycles│  │                         │   │   │
│                     │  └──────────────┘  └─────────────────────────┘   │   │
│                     │  ┌──────────────┐  ┌─────────────────────────┐   │   │
│                     │  │ Accounts     │  │ Subscriptions           │   │   │
│                     │  │              │  │ (suscripciones)         │   │   │
│                     │  └──────────────┘  └─────────────────────────┘   │   │
│                     └──────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ✅ Resumen

Este documento define el flujo completo del sistema desde el registro hasta la reconciliación mensual. Los puntos clave son:

1. **FECHA_BASE** marca el inicio del tracking activo
2. **Transacciones históricas** no afectan patrimonio
3. **Reconciliación mensual** verifica exactitud
4. **Tarjetas de crédito** funcionan diferente a cuentas débito
5. **Pagos de tarjeta** son transferencias internas
6. **Estados de transacción** permiten tracking del ciclo de vida

---

*Documento creado: 3 Diciembre 2025*  
*Próximo paso: Ver PLAN_IMPLEMENTACION.md*
