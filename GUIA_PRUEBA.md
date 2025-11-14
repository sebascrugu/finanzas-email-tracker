# 🚀 Guía Rápida: Cómo Probar el Sistema

## 📋 Pasos para Probar Todo el Sistema

### **Paso 1: Iniciar el Dashboard** 🖥️

Abre una terminal y ejecuta:

```bash
make dashboard
```

O simplemente:

```bash
make dash
```

Esto abrirá automáticamente tu navegador en **http://localhost:8501**

---

### **Paso 2: Configurar Usuario (Si es la primera vez)** ⚙️

1. En el navegador, ve a la página **"⚙️ Setup"** (menú lateral)
2. Completa el formulario:
   - 📧 **Email:** Tu email de Outlook
   - 👤 **Nombre:** Tu nombre completo
   - 💵 **Salario NETO:** Tu salario mensual en colones
   - 💳 **Tarjetas:** Agrega al menos una tarjeta (últimos 4 dígitos)
3. Click en **"✅ Guardar Configuración"**
4. ¡Listo! 🎉

> 💡 **Nota:** Si ya tenés usuario configurado, este paso se omite.

---

### **Paso 3: Agregar Ingresos (Opcional pero recomendado)** 💰

1. Ve a la página **"💰 Ingresos"** (menú lateral)
2. Click en el tab **"➕ Agregar Ingreso"**
3. Completa:
   - Tipo de ingreso (Salario, Venta, etc.)
   - Monto (en CRC o USD)
   - Fecha
   - Si es recurrente (ej: salario mensual)
4. Click en **"✅ Guardar Ingreso"**

> 💡 **Tip:** Si es tu salario, marcá "Es recurrente" y elegí "Mensual"

---

### **Paso 4: Procesar Correos Bancarios** 📧

En el **dashboard**, ve a la página **"📝 Transacciones"** y:

1. Click en el botón **"📧 Procesar Correos Bancarios"**
2. Espera mientras el sistema:
   - ✅ Se conecta a tu Outlook
   - ✅ Busca correos de transacciones bancarias
   - ✅ Extrae los datos (monto, comercio, fecha, etc.)
   - ✅ Convierte USD a CRC automáticamente
   - ✅ Categoriza con IA (Claude)
   - ✅ Guarda en la base de datos
3. Verás las estadísticas del proceso (correos procesados, transacciones nuevas, etc.)
4. Click en **"🔄 Recargar Página"** si hay transacciones para revisar

> ⏱️ **Tiempo:** Puede tardar 1-5 minutos dependiendo de cuántos correos tengas

> 💡 **Alternativa rápida:** También podés clickear el botón **"📧 Procesar Correos"** desde el Dashboard principal

---

### **Paso 5: Revisar y Categorizar Transacciones** 📝

1. En el dashboard, ve a **"📝 Transacciones"** (menú lateral)
2. Verás todas las transacciones que necesitan revisión
3. Para cada transacción:
   - **Opción A:** Click en **"✅ Aceptar Sugerencia IA"** (si la sugerencia es correcta)
   - **Opción B:** Click en una categoría (Necesidades/Gustos/Ahorros)
   - **Si es SINPE/Transferencia:** Te preguntará el tipo especial (normal, intermediaria, etc.)
4. ¡Listo! La transacción queda categorizada ✅

> 💡 **Tip:** El sistema aprende de tus decisiones anteriores (detección de patrones)

---

### **Paso 6: Ver el Balance** 📊

1. Ve a **"📊 Balance"** (menú lateral)
2. Selecciona el mes que querés ver
3. Verás:
   - 💰 Total de ingresos
   - 💸 Total de gastos
   - ✅ Balance (positivo/negativo)
   - 📈 Progreso de gastos (%)
   - 📋 Desglose por categoría

---

### **Paso 7: Ver el Dashboard Principal** 🏠

1. Ve a **"🏠 Dashboard"** (página principal)
2. Verás un resumen del mes actual:
   - Métricas principales (ingresos, gastos, balance)
   - Progreso de gastos
   - Acciones rápidas

---

## 🎯 Flujo Completo de Prueba

```bash
# 1. Iniciar dashboard (terminal)
make dashboard

# 2. En el navegador (TODO desde aquí):
#    → Setup (si es primera vez)
#    → Ingresos (agregar salario)
#    → Transacciones → Click "Procesar Correos"
#    → Transacciones → Categorizar
#    → Balance (ver resultados)
#    → Dashboard (resumen)
```

✅ **¡TODO desde la interfaz web! No necesitás la terminal para usar la app.**

---

## 🐛 Si Algo No Funciona

### **Error: "No hay usuario configurado"**
→ Ve a **Setup** y completa el formulario

### **Error: "No hay transacciones para revisar"**
→ Ejecuta `make process` para procesar correos

### **Error: "No se puede conectar a Outlook"**
→ Verifica que tengas el archivo `.env` con tus credenciales:
```bash
cp .env.example .env
# Luego edita .env con tus datos
```

### **El dashboard no abre**
→ Verifica que Streamlit esté instalado:
```bash
poetry install
```

---

## 💡 Comandos Útiles

```bash
# Ver todos los comandos disponibles
make help

# Iniciar el dashboard (NECESARIO)
make dashboard

# ═══════════════════════════════════════════════════
# Los siguientes son opcionales (solo para desarrollo):
# ═══════════════════════════════════════════════════

# Procesar transacciones desde terminal (alternativa a usar el botón)
make process

# Ver balance rápido en terminal
make balance

# Gestionar ingresos desde terminal
make income

# Limpiar base de datos (CUIDADO: borra todo)
make migrate
```

> ⚠️ **Importante:** Como usuario normal, solo necesitás `make dashboard`. Todo lo demás se hace desde la interfaz web.

---

## ✅ Checklist de Prueba

- [ ] Dashboard inicia correctamente (`make dashboard`)
- [ ] Setup de usuario funciona (página web)
- [ ] Puedo agregar ingresos (página web)
- [ ] Botón "Procesar Correos" funciona (página web)
- [ ] Puedo categorizar transacciones (página web)
- [ ] El balance muestra datos correctos (página web)
- [ ] La detección de patrones funciona (página web)
- [ ] Las sugerencias de IA aparecen (página web)
- [ ] Las estadísticas de procesamiento se muestran correctamente
- [ ] El botón "Recargar Página" funciona después de procesar

---

## 🎉 ¡Listo!

Si completaste todos los pasos, **¡el sistema está funcionando perfectamente!** 🚀

**Próximos pasos:**
- Procesar más correos históricos
- Categorizar todas las transacciones
- Explorar el dashboard y balance
- Agregar más ingresos si es necesario

