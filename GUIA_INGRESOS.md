# 💰 Guía del Sistema de Ingresos

Esta guía explica cómo usar el nuevo sistema de gestión de ingresos del tracker financiero.

---

## 🎯 ¿Para qué sirve?

El sistema de ingresos te permite:

1. **Registrar todos tus ingresos** (salario, ventas, freelance, etc.)
2. **Ver tu balance mensual** (cuánto ingresas vs. cuánto gastas)
3. **Trackear ingresos recurrentes** (salario quincenal/mensual)
4. **Conversión automática USD → CRC** con tipos de cambio históricos

---

## 🚀 Comandos Rápidos

```bash
# Ver balance rápido del mes actual
make balance

# Gestionar ingresos (menú interactivo completo)
make income
```

---

## 📊 Balance Rápido (`make balance`)

Muestra un resumen instantáneo de tu mes actual:

```
📊 BALANCE DE NOVIEMBRE 2025
================================================================================

💰 Ingresos:  ₡    1,200,000.00
💸 Gastos:    ₡      850,000.00
   ────────────────────────────────────────────────────────────────────────────
✅ Balance:   ₡      350,000.00 (POSITIVO)

📊 Has gastado el 70.8% de tus ingresos
✅ ¡Excelente control de gastos!
```

**Casos:**
- ✅ Balance positivo → Estás ahorrando
- ⚠️ Balance negativo → Gastas más de lo que ingresas
- 💡 Sin ingresos registrados → Te sugiere usar `make income`

---

## 💼 Gestión de Ingresos (`make income`)

Menú interactivo completo con 3 opciones:

### 1️⃣ Ver Balance del Mes Actual

Similar a `make balance` pero con más detalles:
- Número de ingresos registrados
- Número de transacciones (gastos)
- Recomendaciones personalizadas

### 2️⃣ Listar Todos Mis Ingresos

Muestra todos tus ingresos registrados:

```
📊 Tienes 3 ingreso(s) registrado(s):

1. 🔁 SALARIO
   💰 ₡1,000,000.00
   📅 15/11/2025
   🏢 Empresa X
   🔄 quincenal
   ⏭️  Próximo: 30/11/2025

2. 1️⃣ VENTA
   💰 ₡150,000.00 (originalmente $300.00 USD)
   📅 10/11/2025
   📝 Venta de PS5

3. 🔁 FREELANCE
   💰 ₡50,000.00
   📅 05/11/2025
   🔄 semanal
   ⏭️  Próximo: 12/11/2025
```

**Íconos:**
- 🔁 = Ingreso recurrente
- 1️⃣ = Ingreso único

### 3️⃣ Agregar Nuevo Ingreso

Proceso interactivo guiado paso a paso:

#### **Paso 1: Tipo de Ingreso**

```
¿Qué tipo de ingreso es?

  1. 💼 Salario
  2. 👴 Pensión
  3. 💻 Freelance
  4. 🛍️  Venta (ej: PS5, carro)
  5. 📈 Rendimiento inversión
  6. 🎁 Regalo/Ayuda
  7. 📦 Otro

Elige el tipo (1-7):
```

#### **Paso 2: Monto y Moneda**

```
💰 Monto (ej: 500000 o 1000): 1000000
Moneda (1=CRC, 2=USD): 1
```

**Si elegiste USD:**
```
🔄 Convirtiendo $1000 USD a CRC...
   Tipo de cambio: ₡508.50
   Monto en CRC: ₡508,500.00
```

#### **Paso 3: Fecha**

```
📅 ¿Cuándo recibiste este ingreso?
  1. Hoy
  2. Otra fecha

Elige opción (1-2): 2
Fecha (DD/MM/YYYY): 15/11/2025
```

#### **Paso 4: Fuente (Opcional)**

```
🏢 Fuente/Empresa (Enter para omitir): Mi Empresa S.A.
```

#### **Paso 5: Descripción (Opcional)**

```
📝 Descripción (Enter para omitir): Salario quincenal Nov 2025
```

#### **Paso 6: ¿Es Recurrente?**

```
🔄 ¿Este ingreso es recurrente?
  1. Sí (se repite regularmente)
  2. No (solo una vez)

Elige opción (1-2): 1
```

**Si es recurrente, pregunta frecuencia:**

```
¿Cada cuánto se repite?
  1. 📅 Semanal
  2. 📆 Quincenal (cada 2 semanas)
  3. 🗓️  Mensual
  4. 📊 Trimestral
  5. 📈 Anual

Elige frecuencia (1-5): 2
```

#### **Paso 7: Resumen y Confirmación**

```
────────────────────────────────────────────────────────────────────────────────
📋 RESUMEN:
────────────────────────────────────────────────────────────────────────────────
Tipo:        salario
Monto:       ₡1,000,000.00 CRC
Fecha:       15/11/2025
Fuente:      Mi Empresa S.A.
Descripción: Salario quincenal Nov 2025
Recurrente:  Sí (quincenal)
Próximo:     29/11/2025
────────────────────────────────────────────────────────────────────────────────

¿Guardar este ingreso? (S/n):
```

---

## 🎯 Casos de Uso Reales

### Caso 1: Salario Quincenal

```bash
make income
→ 3. Agregar nuevo ingreso
→ Tipo: 1 (Salario)
→ Monto: 500000 (CRC)
→ Fecha: Hoy
→ Fuente: Mi Empresa
→ Recurrente: Sí → Quincenal
→ ✅ DONE

# El sistema automáticamente:
# - Calcula el próximo salario (15 días después)
# - Te recordará registrar el siguiente (futuro)
```

### Caso 2: Venta de PS5 (USD)

```bash
make income
→ 3. Agregar nuevo ingreso
→ Tipo: 4 (Venta)
→ Monto: 300 (USD)
→ Fecha: 10/11/2025
→ Descripción: "Venta de PS5"
→ Recurrente: No
→ ✅ DONE

# El sistema automáticamente:
# - Busca el tipo de cambio del 10/11/2025
# - Convierte $300 → ₡152,550 (ej: TC 508.50)
# - Guarda ambos montos
```

### Caso 3: Freelance Semanal

```bash
make income
→ 3. Agregar nuevo ingreso
→ Tipo: 3 (Freelance)
→ Monto: 50000 (CRC)
→ Fecha: Hoy
→ Fuente: Cliente X
→ Descripción: "Proyecto web"
→ Recurrente: Sí → Semanal
→ ✅ DONE
```

### Caso 4: Regalo de Cumpleaños

```bash
make income
→ 3. Agregar nuevo ingreso
→ Tipo: 6 (Regalo)
→ Monto: 25000 (CRC)
→ Fecha: Hoy
→ Descripción: "Regalo cumpleaños tía"
→ Recurrente: No
→ ✅ DONE
```

---

## 📈 Interpretación del Balance

El sistema te da feedback automático según tu % gastado:

| % Gastado | Mensaje | Significado |
|-----------|---------|-------------|
| **0-75%** | ✅ ¡Excelente control! | Estás ahorrando bien |
| **76-90%** | 💡 Buen control, vigila gastos | Podrías ahorrar más |
| **91-99%** | ⚠️ ¡Cuidado! Más del 90% gastado | Riesgo de quedarte sin dinero |
| **100%+** | ⚠️ ¡Gastas más de lo que ingresas! | Situación crítica |

---

## 🔄 Frecuencias Soportadas

- **Semanal** → Cada 7 días
- **Quincenal** → Cada 15 días (2 veces al mes)
- **Mensual** → Mismo día cada mes
- **Bimestral** → Cada 2 meses
- **Trimestral** → Cada 3 meses
- **Semestral** → Cada 6 meses
- **Anual** → Cada año
- **Una vez** → No se repite

---

## 💡 Tips y Mejores Prácticas

### ✅ DO (Haz esto):

1. **Registra ingresos apenas los recibas**
   ```bash
   # Recibiste salario hoy → registra hoy
   make income
   ```

2. **Marca como recurrentes los ingresos fijos**
   - Salario quincenal/mensual
   - Pensión mensual
   - Freelance recurrente

3. **Usa descripciones claras**
   - ✅ "Salario Nov 2025"
   - ✅ "Venta PS5 a Juan"
   - ❌ "Plata"

4. **Convierte USD correctamente**
   - El sistema usa el tipo de cambio oficial del día
   - Guarda ambos montos (USD y CRC)

### ❌ DON'T (No hagas esto):

1. **No registres dinero intermediario**
   - ❌ Alquiler que solo pasas al casero
   - ❌ Dinero de mamá para comprarle algo
   - ✅ Solo TU ingreso real

2. **No duplices ingresos**
   - Si ya registraste tu salario, no lo vuelvas a registrar

3. **No confundas ingreso con préstamo**
   - Préstamo = no es ingreso (lo tienes que devolver)
   - Regalo/Ayuda = sí es ingreso

---

## 🎯 Próximas Mejoras (Futuro)

- [ ] Editar/Eliminar ingresos existentes
- [ ] Proyección de ingresos futuros
- [ ] Notificaciones de ingresos recurrentes próximos
- [ ] Gráficos de ingresos vs gastos
- [ ] Comparación mes actual vs mes anterior
- [ ] Exportar historial de ingresos a Excel/CSV

---

## 🐛 Troubleshooting

### "No hay usuario activo"

```bash
# Solución:
make setup-user
```

### "Tipo de cambio no disponible"

```bash
# El sistema intenta:
# 1. API Hacienda CR (oficial)
# 2. API exchangerate.host (fallback)
# 3. Valor por defecto (508.00)

# Si falla, revisa tu conexión a internet
```

### "Error al guardar ingreso"

```bash
# Posibles causas:
# 1. Base de datos corrupta → make migrate
# 2. Formato de monto inválido → usa solo números
# 3. Fecha inválida → usa DD/MM/YYYY
```

---

## 📞 ¿Necesitas Ayuda?

```bash
# Ver todos los comandos disponibles
make help

# Ver balance rápido
make balance

# Gestión completa de ingresos
make income
```

---

**¡Listo! Ahora puedes trackear tanto tus ingresos como tus gastos completos. 🎉**

