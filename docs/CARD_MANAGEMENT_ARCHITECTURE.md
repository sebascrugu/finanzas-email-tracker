# Arquitectura: Sistema de Gestión de Tarjetas y Pagos

## 🎯 Objetivo

Diseñar un sistema robusto para el manejo de tarjetas de crédito y débito que:
1. Distinga correctamente entre tipos de tarjetas
2. Rastree períodos de facturación de tarjetas de crédito
3. Maneje pagos de tarjeta sin duplicar gastos
4. Reconcilie transacciones con estados de cuenta PDF
5. Detecte anomalías y cargos sospechosos

---

## 📋 Escenarios Críticos

### Escenario 1: Compra con Tarjeta de Débito
```
Usuario compra café en Starbucks ₡5,000 con tarjeta de débito
→ El dinero SALE inmediatamente del patrimonio
→ Es un GASTO REAL en ese momento
→ No hay deuda pendiente
```

### Escenario 2: Compra con Tarjeta de Crédito
```
Usuario compra café en Starbucks ₡5,000 con tarjeta de crédito
→ El dinero NO sale del patrimonio todavía
→ Se acumula como DEUDA en la tarjeta
→ Afecta el saldo de la tarjeta
→ El GASTO REAL ocurre cuando SE PAGA la tarjeta
```

### Escenario 3: Pago de Tarjeta de Crédito (Pago Total)
```
Usuario recibe email: "Pago a tarjeta BAC Visa ₡150,000"
Período: Nov 15 - Dic 15, Total del estado: ₡150,000

→ Esto es un GASTO porque sale dinero del patrimonio
→ Las transacciones individuales de ese período NO son gastos dobles
→ Se debe marcar el período como PAGADO
→ La tarjeta queda en saldo ₡0
```

### Escenario 4: Pago de Tarjeta de Crédito (Pago Parcial/Mínimo)
```
Usuario paga ₡50,000 de un total de ₡150,000

→ ₡50,000 es el GASTO real que sale del patrimonio
→ ₡100,000 queda como DEUDA pendiente
→ Se generan INTERESES sobre el saldo no pagado
→ Importante trackear esto para alerta de intereses
```

### Escenario 5: Transacciones Sin Email
```
- Seguros automáticos (INS, otros)
- Suscripciones que no generan notificación
- Cargos recurrentes de servicios (Netflix, Compass, etc.)

→ NO aparecen en emails
→ SÍ aparecen en el estado de cuenta PDF
→ Necesitamos reconciliar para detectar estas "transacciones fantasma"
```

### Escenario 6: Cargo Duplicado/Fraudulento
```
Usuario ve en PDF: "Compra Amazon $50.00" dos veces el mismo día

→ Puede ser duplicado fraudulento
→ Puede ser compra legítima (dos pedidos)
→ Sistema debe ALERTAR para que usuario confirme
```

### Escenario 7: Transacción en Email pero No en PDF
```
Transacción parseada de email pero no aparece en estado de cuenta

→ Puede ser que se revirtió/rechazó
→ Puede ser pre-autorización que no se completó
→ Puede ser error de parseo (fecha diferente)
```

### Escenario 8: Múltiples Tarjetas del Mismo Banco
```
Usuario tiene:
- BAC Visa Crédito (termina 1234)
- BAC Mastercard Débito (termina 5678)
- BAC Visa Débito (termina 9012)

→ El email de BAC incluye últimos 4 dígitos
→ Debemos vincular correctamente cada transacción a su tarjeta
→ Usuario debe poder setear cuál es crédito vs débito
```

### Escenario 9: Devolución/Refund en Tarjeta de Crédito
```
Usuario compró algo por ₡10,000 el 20 Nov
Devolución procesada el 5 Dic (₡10,000 crédito)

→ ¿Qué pasa si el pago del período Nov ya se hizo?
→ El crédito aplica al siguiente período
→ Reduce la deuda del siguiente ciclo
```

### Escenario 10: Compra en Cuotas
```
Usuario compra TV ₡500,000 en 12 cuotas sin intereses
Cuota mensual: ₡41,666.67

→ ¿Es un gasto de ₡500,000 o 12 gastos de ₡41,667?
→ Para presupuesto: cada cuota es el gasto del mes
→ Para patrimonio: la deuda total es ₡500,000 - lo pagado
```

---

## 🏗️ Arquitectura Propuesta

### Nuevos Modelos

#### 1. BillingCycle (Período de Facturación)
```python
class BillingCycle(Base):
    """Un período de facturación de una tarjeta de crédito."""
    
    __tablename__ = "billing_cycles"
    
    id: Mapped[str]  # UUID
    tenant_id: Mapped[UUID | None]  # Multi-tenancy
    card_id: Mapped[str]  # FK a Card (solo tarjetas de crédito)
    
    # Período
    fecha_inicio: Mapped[date]  # Fecha de corte anterior + 1
    fecha_corte: Mapped[date]   # Fecha de cierre del período
    fecha_vencimiento: Mapped[date]  # Fecha límite de pago
    
    # Montos del estado de cuenta
    saldo_anterior: Mapped[Decimal]  # Saldo del ciclo anterior
    total_cargos: Mapped[Decimal]    # Total de compras/cargos
    total_abonos: Mapped[Decimal]    # Devoluciones, pagos anticipados
    total_periodo: Mapped[Decimal]   # Lo que se debe pagar
    pago_minimo: Mapped[Decimal]     # Mínimo requerido
    
    # Estado del pago
    status: Mapped[str]  # pending, partial, paid, overdue
    monto_pagado: Mapped[Decimal]    # Cuánto se ha pagado
    fecha_pago: Mapped[datetime | None]  # Cuándo se pagó
    
    # Reconciliación con PDF
    pdf_imported: Mapped[bool]  # Si se importó el estado de cuenta
    pdf_path: Mapped[str | None]  # Ruta al PDF guardado
    
    # Auditoría
    deleted_at, created_at, updated_at
```

#### 2. CardPayment (Pago a Tarjeta)
```python
class CardPayment(Base):
    """Un pago realizado a una tarjeta de crédito."""
    
    __tablename__ = "card_payments"
    
    id: Mapped[str]  # UUID
    tenant_id: Mapped[UUID | None]
    card_id: Mapped[str]  # FK a Card
    billing_cycle_id: Mapped[str | None]  # FK a BillingCycle (si aplica)
    
    # Detalles del pago
    monto: Mapped[Decimal]
    fecha_pago: Mapped[datetime]
    metodo_pago: Mapped[str]  # transferencia, sinpe, efectivo, otra_tarjeta
    
    # Origen del pago (de dónde salió el dinero)
    cuenta_origen: Mapped[str | None]  # "Cuenta corriente BAC", etc.
    card_origen_id: Mapped[str | None]  # Si pagó con otra tarjeta (débito)
    
    # Referencia al email/transacción que lo detectó
    email_id: Mapped[str | None]  # ID del correo
    transaction_id: Mapped[str | None]  # Si se creó Transaction primero
    
    # Tipo de pago
    tipo: Mapped[str]  # total, parcial, minimo, adelanto
    
    # Auditoría
    deleted_at, created_at, updated_at
```

#### 3. StatementTransaction (Transacción del Estado de Cuenta)
```python
class StatementTransaction(Base):
    """
    Transacción importada de un estado de cuenta PDF.
    Se usa para reconciliación con transacciones de emails.
    """
    
    __tablename__ = "statement_transactions"
    
    id: Mapped[str]  # UUID
    billing_cycle_id: Mapped[str]  # FK a BillingCycle
    
    # Datos del PDF
    fecha: Mapped[date]
    descripcion: Mapped[str]
    monto: Mapped[Decimal]
    moneda: Mapped[str]
    referencia: Mapped[str | None]  # Número de referencia si existe
    
    # Reconciliación
    matched_transaction_id: Mapped[str | None]  # FK a Transaction
    match_confidence: Mapped[Decimal]  # 0-100%
    match_status: Mapped[str]  # matched, unmatched, disputed, ignored
    
    # Para transacciones sin email
    created_as_transaction: Mapped[bool]  # Si se creó Transaction desde aquí
```

### Modificaciones a Modelos Existentes

#### Card (Agregar campos)
```python
# Agregar a Card:
es_tarjeta_fisica: Mapped[bool] = True  # vs virtual/digital
dia_corte: Mapped[int | None]  # 1-31, día del mes de corte
dias_para_pago: Mapped[int | None]  # Días después del corte para pagar
requiere_reconciliacion: Mapped[bool] = True  # Si debe verificar con PDF
```

#### Transaction (Agregar campos)
```python
# Agregar a Transaction:
billing_cycle_id: Mapped[str | None]  # FK a BillingCycle (solo crédito)
es_pago_tarjeta: Mapped[bool] = False  # Si es pago a tarjeta crédito
card_payment_id: Mapped[str | None]  # FK a CardPayment si es pago
source: Mapped[str] = "email"  # email, pdf_import, manual
```

### Enums Nuevos

```python
class BillingCycleStatus(str, Enum):
    OPEN = "open"           # Período en curso, acumulando cargos
    CLOSED = "closed"       # Cerrado, esperando pago
    PAID = "paid"           # Pagado completamente
    PARTIAL = "partial"     # Pago parcial hecho
    OVERDUE = "overdue"     # Vencido sin pagar

class PaymentType(str, Enum):
    TOTAL = "total"         # Pago total del período
    PARTIAL = "partial"     # Pago parcial
    MINIMUM = "minimum"     # Solo mínimo
    ADVANCE = "advance"     # Pago adelantado (antes de corte)

class TransactionSource(str, Enum):
    EMAIL = "email"         # Parseada de correo
    PDF_IMPORT = "pdf_import"  # Importada de estado de cuenta
    MANUAL = "manual"       # Ingresada manualmente
    API = "api"            # Desde integración bancaria (futuro)
```

---

## 🔄 Flujos de Proceso

### Flujo 1: Transacción Nueva (Email)
```
1. Email llega → Parser detecta transacción
2. Extraer últimos 4 dígitos de tarjeta
3. Buscar Card con esos dígitos
   - Si no existe: Crear Card (tipo UNKNOWN, preguntar después)
   - Si existe: Vincular
4. Si Card.tipo == CREDITO:
   - Buscar BillingCycle activo (status=OPEN)
   - Si no existe: Crear nuevo BillingCycle
   - Vincular Transaction al BillingCycle
   - Actualizar BillingCycle.total_cargos
5. Guardar Transaction
```

### Flujo 2: Pago de Tarjeta Detectado
```
1. Email llega → Parser detecta "Pago a tarjeta"
2. Extraer: monto, últimos 4 dígitos destino
3. Buscar Card destino
4. Crear CardPayment:
   - monto = monto del pago
   - billing_cycle_id = ciclo pendiente más antiguo
5. Actualizar BillingCycle:
   - monto_pagado += monto
   - Si monto_pagado >= total_periodo: status = PAID
   - Si no: status = PARTIAL
6. Crear Transaction con:
   - tipo_transaccion = PAGO_TARJETA
   - es_pago_tarjeta = True
   - card_id = tarjeta ORIGEN (de donde salió el dinero)
   - card_payment_id = el CardPayment creado
7. Si tarjeta origen es DEBITO:
   - Este ES un gasto (sale del patrimonio)
   - Afecta presupuesto
8. Si es transferencia de cuenta:
   - Este ES un gasto (sale de cuenta corriente)
```

### Flujo 3: Importar Estado de Cuenta PDF
```
1. Usuario sube PDF de estado de cuenta
2. Parsear PDF → Lista de transacciones
3. Crear/encontrar BillingCycle correspondiente
4. Para cada transacción del PDF:
   a. Buscar match en Transactions existentes:
      - fecha ±1 día
      - monto exacto
      - comercio similar (fuzzy match)
   b. Si match encontrado:
      - Crear StatementTransaction
      - matched_transaction_id = la transacción
      - match_status = matched
   c. Si NO match:
      - Crear StatementTransaction
      - match_status = unmatched
      - ALERTAR: "Transacción sin email detectada"
5. Revisar Transactions sin match en PDF:
   - ALERTAR: "Transacción en email sin coincidencia en PDF"
```

### Flujo 4: Configuración Inicial de Tarjeta
```
1. Sistema detecta nueva tarjeta (4 dígitos nuevos)
2. Crear Card con tipo = UNKNOWN
3. En próxima sesión, preguntar usuario:
   - "Detecté una tarjeta ***1234, ¿es crédito o débito?"
   - Si crédito: "¿Cuál es tu fecha de corte?"
   - Si crédito: "¿Cuántos días tienes para pagar después del corte?"
4. Actualizar Card con info
5. Si crédito: Crear primer BillingCycle
```

---

## 💰 Impacto en Presupuesto y Patrimonio

### Reglas de Cálculo

| Tipo Tarjeta | Tipo Transacción | ¿Afecta Presupuesto? | ¿Afecta Patrimonio? |
|--------------|------------------|----------------------|---------------------|
| Débito | Compra | ✅ Sí | ✅ Sí (resta) |
| Débito | Transferencia | ✅ Sí | ✅ Sí (resta) |
| Crédito | Compra | ❌ No (hasta pago) | ❌ No (es deuda) |
| Crédito | Pago Total | ✅ Sí | ✅ Sí (resta) |
| Crédito | Pago Parcial | ✅ Sí (lo pagado) | ✅ Sí (lo pagado) |
| Cualquiera | Ingreso | ✅ Sí | ✅ Sí (suma) |

### Fórmula de Patrimonio

```python
patrimonio_liquido = (
    sum(cuentas_bancarias.saldo)  # Dinero disponible
    - sum(tarjetas_credito.saldo_pendiente)  # Deudas de tarjetas
    - sum(prestamos.saldo_pendiente)  # Otros préstamos
)
```

### Gastos del Mes (para presupuesto)

```python
gastos_mes = (
    # Transacciones de débito
    sum(transactions.monto WHERE card.tipo == DEBITO)
    
    # Pagos a tarjetas de crédito (el dinero que salió)
    + sum(card_payments.monto WHERE fecha IN mes_actual)
    
    # NO incluir compras con crédito (ya se contará cuando se pague)
)
```

---

## ⚠️ Alertas y Notificaciones

### Alertas Automáticas

1. **Fecha de pago próxima**
   - 3 días antes: "Tu tarjeta ****1234 vence en 3 días. Total: ₡150,000"

2. **Transacción sin email detectada**
   - "En tu estado de cuenta hay ₡15,000 de 'NETFLIX' que no detectamos por email"

3. **Posible duplicado**
   - "Detectamos 2 cargos de ₡25,000 en 'AMAZON' el mismo día. ¿Son correctos?"

4. **Monto inusual**
   - "El cargo de ₡500,000 en 'BEST BUY' es 10x mayor a tu promedio"

5. **Intereses por pago parcial**
   - "Pagaste ₡50,000 de ₡150,000. Se generarán intereses (~2%) sobre ₡100,000"

---

## 🗃️ Migraciones Necesarias

### Migración 1: Nuevas Tablas
```sql
CREATE TABLE billing_cycles (...)
CREATE TABLE card_payments (...)  
CREATE TABLE statement_transactions (...)
```

### Migración 2: Modificar Cards
```sql
ALTER TABLE cards ADD COLUMN dia_corte INTEGER;
ALTER TABLE cards ADD COLUMN dias_para_pago INTEGER;
ALTER TABLE cards ADD COLUMN es_tarjeta_fisica BOOLEAN DEFAULT TRUE;
ALTER TABLE cards ADD COLUMN requiere_reconciliacion BOOLEAN DEFAULT TRUE;
```

### Migración 3: Modificar Transactions
```sql
ALTER TABLE transactions ADD COLUMN billing_cycle_id VARCHAR(36) REFERENCES billing_cycles(id);
ALTER TABLE transactions ADD COLUMN es_pago_tarjeta BOOLEAN DEFAULT FALSE;
ALTER TABLE transactions ADD COLUMN card_payment_id VARCHAR(36) REFERENCES card_payments(id);
ALTER TABLE transactions ADD COLUMN source VARCHAR(20) DEFAULT 'email';
```

---

## 🔮 Futuras Extensiones

1. **Proyección de gastos**: Estimar cuánto será el próximo estado de cuenta
2. **Optimización de pagos**: Sugerir cuánto pagar para minimizar intereses
3. **Análisis de cuotas**: Trackear compras a meses sin intereses
4. **Integración bancaria**: Conectar directo con API del banco (Open Banking)
5. **Múltiples estados de cuenta**: Manejar consolidados de varias tarjetas

---

## ✅ Checklist de Implementación

- [ ] Crear enums nuevos (BillingCycleStatus, PaymentType, TransactionSource)
- [ ] Crear modelo BillingCycle
- [ ] Crear modelo CardPayment
- [ ] Crear modelo StatementTransaction
- [ ] Modificar modelo Card (agregar campos)
- [ ] Modificar modelo Transaction (agregar campos)
- [ ] Crear migraciones Alembic
- [ ] Actualizar BACParser para detectar pagos de tarjeta
- [ ] Crear CardService para gestión de tarjetas
- [ ] Crear BillingCycleService para ciclos de facturación
- [ ] Crear ReconciliationService para comparar email vs PDF
- [ ] Actualizar TransactionService para manejar tipos de tarjeta
- [ ] Crear endpoints API para configurar tarjetas
- [ ] Crear flujo en Streamlit para onboarding de tarjetas
- [ ] Integrar con sistema de alertas existente
- [ ] Escribir tests para cada escenario

---

*Documento creado: 2025-01-XX*
*Última actualización: [pendiente]*
