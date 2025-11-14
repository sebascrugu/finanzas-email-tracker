# 🎮 Guía de Prueba - Sistema de Perfiles

## 📋 Resumen

El sistema ahora soporta **múltiples perfiles** para separar diferentes contextos financieros (Personal, Negocio, Familia, etc.). Cada perfil tiene:
- Sus propias tarjetas bancarias
- Su propio presupuesto 50/30/20
- Sus propios ingresos
- Sus propias transacciones

**Solo busca correos de los bancos asociados a las tarjetas del perfil activo.**

---

## 🚀 Pasos para Probar

### 1️⃣ Iniciar el Sistema

```bash
# Abrir terminal en el proyecto
cd /Users/sebastiancruz/Desktop/finanzas-email-tracker

# Iniciar dashboard
make dashboard
```

La aplicación se abrirá automáticamente en tu navegador en `http://localhost:8501`

---

### 2️⃣ Primera Configuración (Usuario Nuevo)

#### **Paso A: Crear Usuario**
1. Ve a la página **⚙️ Setup** (menú lateral)
2. Completa el formulario:
   - **Email**: `sebastiancruz@hotmail.com`
   - **Nombre**: `Sebastian Cruz`
3. Click en **"➡️ Continuar"**

#### **Paso B: Crear Tu Primer Perfil (Personal)**
1. Llena el formulario:
   - **Nombre del perfil**: `Personal`
   - **Icono**: `👤` (o el emoji que quieras)
   - **Descripción**: `Mis finanzas personales`
   
2. **Presupuesto Mensual**:
   - **Salario NETO**: `280000` (o tu salario real)
   - El sistema calculará automáticamente:
     - 50% Necesidades: ₡140,000
     - 30% Gustos: ₡84,000
     - 20% Ahorros: ₡56,000

3. **Tarjetas Bancarias** (agrega todas las que uses):
   - Ejemplo 1:
     - Últimos 4: `1234`
     - Tipo: `debito`
     - Banco: `bac`
     - Alias: `BAC Principal`
   - Ejemplo 2:
     - Últimos 4: `5678`
     - Tipo: `credito`
     - Banco: `bac`
     - Alias: `BAC Crédito`
   - Click **"➕"** para agregar cada tarjeta

4. Click **"🎉 Crear Perfil"**

✅ **Resultado**: Perfil "Personal" creado y activado automáticamente

---

### 3️⃣ Procesar Correos Bancarios

1. Ve a la página **📝 Transacciones** (menú lateral)
2. Deberías ver: `📊 Perfil: 👤 Personal`
3. Click en **"📧 Procesar Correos Bancarios"**

**Lo que pasará:**
- 🔍 Se conectará a tu Outlook
- 📧 Buscará correos **SOLO de BAC** (porque tus tarjetas son BAC)
- 🤖 Categorizará automáticamente con IA (Claude Haiku 4.5)
- 💾 Guardará transacciones en el perfil "Personal"

**Estadísticas que verás:**
```
✅ ¡Proceso completado!
📧 Correos procesados: 30
✅ Nuevas: 27
🤖 Auto-categorizadas: 15
🔄 Duplicadas: 3
❌ Errores: 0
```

---

### 4️⃣ Revisar y Categorizar Transacciones

1. Recarga la página (F5)
2. Verás: `📝 Tienes X transacción(es) para revisar`

**Para cada transacción:**

#### **Paso 1: Seleccionar Categoría Principal**
- **Necesidades** (50%): Alquiler, servicios, comida esencial, transporte
- **Gustos** (30%): Restaurantes, entretenimiento, compras no esenciales
- **Ahorros** (20%): Inversiones, transferencias a ahorros

#### **Paso 2: Seleccionar Subcategoría**
- Ej: Necesidades → Transporte → Gasolina
- Ej: Gustos → Entretenimiento → Streaming
- Ej: Ahorros → Inversiones → CDP

#### **Paso 3: (Solo para Transferencias/SINPEs) Tipo Especial**
Si es una transferencia o SINPE, el sistema preguntará:
- **Normal**: Gasto/ingreso regular
- **Intermediaria**: Dinero que pasó por tu cuenta pero no es tuyo
  - Ej: Mamá te pasa plata para pagar el alquiler
  - Ej: Amigo te pasa para comprarle algo
- **Compartida**: Gasto dividido con otros
  - Ej: Futbol con amigos (cada uno paga su parte)
- **Personal de otros**: Compra para otra persona con su dinero

**Detección de Patrones:**
- Si ya marcaste antes el mismo comercio (ej: "JOHN DOE - ALQUILER"), el sistema te lo sugerirá automáticamente

#### **Paso 4: Confirmar**
- Click **"✅ Guardar y Continuar"**
- Automáticamente pasa a la siguiente transacción

---

### 5️⃣ Ver Dashboard y Balance

#### **Dashboard Principal** (🏠)
- **Ingresos del mes**: Total de ingresos registrados
- **Gastos del mes**: Total gastado (excluye intermediarias)
- **Balance**: Ingresos - Gastos
- **Progreso**: % de ingresos gastado

#### **Balance Detallado** (📊)
- Selector de mes
- Ingresos detallados por tipo
- Gastos agrupados por categoría
- Gráfica de progreso

#### **Ingresos** (💰)
1. Click en **"➕ Agregar Ingreso"**
2. Llena:
   - Tipo: Salario, Freelance, Venta, etc.
   - Monto y moneda
   - Fecha
   - Recurrente (opcional)
3. Click **"💾 Guardar Ingreso"**

---

### 6️⃣ Crear Segundo Perfil (Ej: Mamá)

**Escenario**: Quieres separar las finanzas de tu mamá

1. Ve a **⚙️ Setup**
2. Tab **"➕ Crear Perfil"**
3. Llena:
   - **Nombre**: `Mamá`
   - **Icono**: `👵`
   - **Descripción**: `Finanzas de mi mamá`
   - **Salario**: `300000` (su salario)
   - **Tarjetas**: 
     - Últimos 4: `9999`
     - Tipo: `debito`
     - Banco: `popular` ⚠️ **Importante: Banco Popular**
     - Alias: `Popular Mamá`
4. Click **"🎉 Crear Perfil"**

---

### 7️⃣ Cambiar de Perfil

1. En el **sidebar izquierdo**, verás: **"👤 Perfil Activo"**
2. Usa el selector dropdown para cambiar entre perfiles:
   - `👤 Personal`
   - `👵 Mamá`

**Lo que cambia automáticamente:**
- Dashboard muestra datos del perfil seleccionado
- Ingresos y gastos del perfil
- Al procesar correos, **solo busca del Banco Popular** (porque la tarjeta de mamá es Popular)
- Transacciones listadas son solo del perfil

---

### 8️⃣ Procesar Correos por Perfil

#### **Perfil Personal (BAC)**
1. Cambia a perfil `👤 Personal`
2. Ve a **📝 Transacciones**
3. Click **"📧 Procesar Correos Bancarios"**
4. **Solo busca correos de BAC** ✅

#### **Perfil Mamá (Popular)**
1. Cambia a perfil `👵 Mamá`
2. Ve a **📝 Transacciones**
3. Click **"📧 Procesar Correos Bancarios"**
4. **Solo busca correos de Banco Popular** ✅

---

## 🎯 Casos de Prueba Importantes

### ✅ Caso 1: Transacción Normal
- **Comercio**: WALMART
- **Categoría**: Necesidades → Alimentación → Supermercado
- **Tipo especial**: Normal

### ✅ Caso 2: Transferencia Intermediaria
- **Comercio**: JOHN DOE (dueño del apartamento)
- **Categoría**: Necesidades → Vivienda → Alquiler
- **Tipo especial**: Intermediaria
- **Relacionada con**: Mamá me pasó para pagar el alquiler
- **Excluir de presupuesto**: ✅ Sí

### ✅ Caso 3: Gasto Compartido (Futbol)
- **Comercio**: MARIA LOPEZ (líder de futbol)
- **Categoría**: Gustos → Entretenimiento → Deportes
- **Tipo especial**: Compartida
- **Relacionada con**: Futbol semanal con amigos
- **Excluir de presupuesto**: ❌ No (es tu gasto real)

### ✅ Caso 4: Gasolina (Patrón recurrente)
- **Primera vez**: Categoriza manualmente como Necesidades → Transporte → Gasolina
- **Segunda vez en misma estación**: Sistema sugiere automáticamente la categoría

### ✅ Caso 5: Retiro sin Tarjeta (BAC)
- **Categoría**: Necesidades → Efectivo → Retiro
- **Tipo especial**: Normal

---

## 🐛 Problemas Comunes

### ❌ "No se encontraron correos"
**Solución**: 
- Verifica que tengas correos bancarios en tu Outlook en los últimos 30 días
- Verifica que las tarjetas del perfil correspondan a los bancos correctos
- Si tienes tarjetas BAC, debe buscar correos de BAC
- Si tienes tarjetas Popular, debe buscar correos de Popular

### ❌ "No tienes tarjetas registradas"
**Solución**: 
- Ve a **Setup** → Tab "📋 Mis Perfiles"
- Edita el perfil y agrega tarjetas

### ❌ "Sin perfil activo"
**Solución**: 
- Ve a **Setup** → Tab "📋 Mis Perfiles"
- Click en **"⭐ Activar"** en el perfil que quieras usar

### ❌ Claude API Error
**Solución**: 
- Verifica que tengas créditos en tu cuenta de Claude
- Revisa que `ANTHROPIC_API_KEY` esté en tu `.env`
- Modelo usado: `claude-haiku-4-5-20251001`

---

## 📊 Métricas de Éxito

Al final de las pruebas deberías tener:

✅ **Perfil Personal**:
- X tarjetas BAC configuradas
- X transacciones procesadas y categorizadas
- Balance del mes calculado
- Ingresos registrados

✅ **Perfil Mamá** (opcional):
- X tarjetas Popular configuradas
- X transacciones procesadas
- Balance separado del perfil Personal

✅ **Dashboard**:
- Cambio fluido entre perfiles
- Métricas correctas por perfil
- Progreso de gastos actualizado

---

## 🎉 ¡Listo!

El sistema de perfiles está **100% funcional**. Ahora puedes:
- Separar finanzas personales vs. negocio
- Gestionar múltiples personas/contextos
- Procesar correos específicos por perfil
- Tener presupuestos independientes

**Periodo de Pruebas**: Nov-Dic 2025  
**Lanzamiento Oficial**: Enero 2026  

¡A probar! 🚀

