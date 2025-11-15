# 🚀 Guía de Prueba Rápida - Sistema Simplificado

## 📋 Resumen

Esta guía te lleva paso a paso para probar **todo el sistema** desde cero.

**Tiempo estimado:** 10-15 minutos

---

## ✅ PASO 1: Verificar que el Dashboard esté corriendo

1. Abre tu navegador
2. Ve a: `http://localhost:8501`
3. Deberías ver la **página de bienvenida** con el botón "🎉 Crear Mi Primer Perfil"

**Si no está corriendo:**
```bash
cd /Users/sebastiancruz/Desktop/finanzas-email-tracker
make dashboard
```

---

## ✅ PASO 2: Crear Tu Primer Perfil

1. **Click en "🎉 Crear Mi Primer Perfil"** (o ve a **⚙️ Setup** en el menú lateral)

2. **Llena el formulario:**

   **📧 Email de Outlook:**
   - `sebastiancruz@hotmail.com` (o tu email real)

   **📝 Nombre del perfil:**
   - `Personal` (o el nombre que quieras)

   **😀 Icono:**
   - `👤` (o cualquier emoji)

   **📄 Descripción (opcional):**
   - `Mis finanzas personales`

   **💵 Salario NETO mensual:**
   - `280000` (o tu salario real en colones)

3. **Agregar Tarjetas:**

   Agrega al menos **2 tarjetas** (ejemplo):
   
   **Tarjeta 1:**
   - Últimos 4: `1234`
   - Tipo: `debito`
   - Banco: `bac`
   - Alias: `BAC Principal`
   - Click **"➕"**

   **Tarjeta 2:**
   - Últimos 4: `5678`
   - Tipo: `credito`
   - Banco: `bac`
   - Alias: `BAC Crédito`
   - Click **"➕"**

4. **Click "🎉 Crear Perfil"**

5. **✅ Resultado esperado:**
   - Mensaje: "✅ Perfil 'Personal' creado exitosamente!"
   - Confetti 🎉
   - Redirección automática al Dashboard

---

## ✅ PASO 3: Verificar el Dashboard

Deberías ver:

**Sidebar:**
- Nombre del perfil: `👤 Personal`
- Presupuesto: `₡280,000/mes`
- Tarjetas: `2`
- Bancos: `BAC`

**Dashboard Principal:**
- Título: `🏠 Dashboard - 👤 Personal`
- Métricas:
  - 💰 Ingresos: `₡0` (0 ingresos)
  - 💸 Gastos: `₡0` (0 transacciones)
  - 📊 Balance: `₡0`
  - 📝 Sin Revisar: `0`

**Si todo se ve bien → ✅ Dashboard funcionando**

---

## ✅ PASO 4: Agregar un Ingreso

1. **Ve a "💰 Ingresos"** (menú lateral)

2. **Tab "➕ Agregar Ingreso"**

3. **Llena el formulario:**
   - **Tipo:** `💼 Salario`
   - **Descripción:** `Salario Nov 2025`
   - **Monto:** `280000`
   - **Moneda:** `CRC`
   - **Fecha:** Hoy (o la fecha que quieras)
   - **Recurrente:** ✅ Sí
   - **Frecuencia:** `Mensual`

4. **Click "💾 Guardar Ingreso"**

5. **✅ Resultado esperado:**
   - Mensaje: "✅ ¡Ingreso registrado exitosamente!"
   - Confetti 🎉
   - Próximo ingreso esperado mostrado

6. **Verifica en "📋 Mis Ingresos":**
   - Deberías ver tu ingreso listado
   - Con icono 🔁 (recurrente)

---

## ✅ PASO 5: Procesar Correos Bancarios

1. **Ve a "📝 Transacciones"** (menú lateral)

2. **Click en "📧 Procesar Correos Bancarios"**

3. **Lo que pasará:**
   - 🔍 Se conectará a tu Outlook
   - 📧 Buscará correos de **BAC** (tus tarjetas)
   - 🤖 Categorizará automáticamente con IA
   - 💾 Guardará transacciones

4. **Estadísticas que verás:**
   ```
   ✅ ¡Proceso completado!
   📧 Correos procesados: X
   ✅ Nuevas: Y
   🤖 Auto-categorizadas: Z
   🔄 Duplicadas: W
   ❌ Errores: 0
   ```

5. **Si hay transacciones nuevas:**
   - Verás: `📝 X transacción(es) necesitan tu revisión`
   - **Recarga la página** (F5)

---

## ✅ PASO 6: Categorizar Transacciones

1. **En "📝 Transacciones"**, deberías ver tus transacciones pendientes

2. **Para cada transacción:**

   **PASO 1: Seleccionar Categoría Principal**
   - **Necesidades** (50%): Alquiler, servicios, comida, transporte
   - **Gustos** (30%): Restaurantes, entretenimiento, compras
   - **Ahorros** (20%): Inversiones, transferencias a ahorros

   **PASO 2: Seleccionar Subcategoría**
   - Ej: Necesidades → Alimentación → Supermercado
   - Ej: Gustos → Entretenimiento → Streaming

   **PASO 3: (Solo para Transferencias/SINPEs)**
   - Si es transferencia o SINPE, el sistema preguntará:
     - **Normal**: Gasto regular
     - **Intermediaria**: Dinero que pasó pero no es tuyo
     - **Compartida**: Gasto dividido con otros
     - **Personal de otros**: Compra para otra persona

   **PASO 4: Confirmar**
   - Click **"✅ Guardar y Continuar"**

3. **✅ Resultado esperado:**
   - Transacción categorizada
   - Pasa automáticamente a la siguiente
   - Al final: "✅ ¡Excelente! No hay transacciones pendientes"

---

## ✅ PASO 7: Verificar el Balance

1. **Ve a "📊 Balance"** (menú lateral)

2. **Deberías ver:**
   - **💰 Ingresos:** `₡280,000` (tu salario)
   - **💸 Gastos:** `₡X` (suma de tus transacciones)
   - **📊 Balance:** `₡Y` (Ingresos - Gastos)

3. **Progreso de Gastos:**
   - Barra de progreso
   - Porcentaje gastado del mes
   - Mensaje según tu gasto

4. **Detalles:**
   - Lista de ingresos del mes
   - Gastos agrupados por categoría

---

## ✅ PASO 8: Verificar el Dashboard Actualizado

1. **Vuelve a "🏠 Dashboard"** (o "app" en el menú)

2. **Deberías ver métricas actualizadas:**
   - 💰 Ingresos: `₡280,000`
   - 💸 Gastos: `₡X` (tus transacciones)
   - 📊 Balance: `₡Y`
   - 📝 Sin Revisar: `0` (si categorizaste todo)

3. **Progreso de Gastos:**
   - Barra de progreso actualizada
   - Porcentaje gastado
   - Mensaje según tu situación

---

## ✅ PASO 9: Crear Segundo Perfil (Opcional)

**Prueba el sistema multi-perfil:**

1. **Ve a "⚙️ Setup"**

2. **Tab "➕ Crear Perfil"**

3. **Crea un segundo perfil:**
   - Email: `mama@hotmail.com` (ejemplo)
   - Nombre: `Mamá`
   - Icono: `👵`
   - Salario: `300000`
   - Tarjeta: `****9999` (debito, popular)

4. **Click "🎉 Crear Perfil"**

5. **Cambiar de perfil:**
   - En el **sidebar**, verás selector de perfiles
   - Cambia a "👵 Mamá"
   - El dashboard se actualiza automáticamente

6. **Procesar correos del segundo perfil:**
   - Solo buscará correos de **Banco Popular** (tarjeta de mamá)

---

## 🐛 Problemas Comunes y Soluciones

### ❌ "No se encontraron correos"
**Solución:**
- Verifica que tengas correos bancarios en Outlook (últimos 30 días)
- Verifica que las tarjetas del perfil correspondan a los bancos correctos
- Si tienes tarjetas BAC, debe buscar correos de BAC

### ❌ "Sin perfil activo"
**Solución:**
- Ve a **Setup** → Tab "📋 Mis Perfiles"
- Click en **"⭐ Activar"** en el perfil que quieras usar

### ❌ Claude API Error
**Solución:**
- Verifica que tengas créditos en tu cuenta de Claude
- Revisa que `ANTHROPIC_API_KEY` esté en tu `.env`
- Modelo usado: `claude-haiku-4-5-20251001`

### ❌ Error al procesar correos
**Solución:**
- Verifica que tengas configurado `MICROSOFT_CLIENT_ID` y `MICROSOFT_CLIENT_SECRET` en `.env`
- Verifica que tengas permisos de lectura de correos en Azure AD

---

## ✅ Checklist de Prueba

Marca cada paso cuando lo completes:

- [ ] Dashboard carga correctamente
- [ ] Crear perfil funciona
- [ ] Agregar tarjetas funciona
- [ ] Agregar ingreso funciona
- [ ] Procesar correos funciona
- [ ] Categorizar transacciones funciona
- [ ] Balance muestra datos correctos
- [ ] Dashboard se actualiza con datos
- [ ] Crear segundo perfil funciona
- [ ] Cambiar entre perfiles funciona
- [ ] Procesar correos por perfil funciona

---

## 🎯 Qué Observar Durante la Prueba

1. **Flujo de usuario:**
   - ¿Es intuitivo?
   - ¿Hay pasos confusos?
   - ¿Falta información?

2. **Rendimiento:**
   - ¿Carga rápido?
   - ¿Procesa correos rápido?
   - ¿La categorización con IA es rápida?

3. **Datos:**
   - ¿Los montos son correctos?
   - ¿Las categorías se asignan bien?
   - ¿El balance es correcto?

4. **UI/UX:**
   - ¿Se ve bien?
   - ¿Hay elementos desordenados?
   - ¿Falta algo?

---

## 📝 Notas Durante la Prueba

**Anota cualquier problema o mejora que encuentres:**

1. _________________________________________________
2. _________________________________________________
3. _________________________________________________

---

## 🎉 ¡Listo!

Una vez que completes todos los pasos, tendrás:
- ✅ Sistema completamente probado
- ✅ Datos de prueba en la BD
- ✅ Conocimiento de todos los flujos
- ✅ Lista de mejoras/bugs encontrados

**¡A probar!** 🚀

