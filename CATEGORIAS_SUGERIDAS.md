# 📋 Categorías y Subcategorías Sugeridas

Este documento define la estructura completa de categorías para el sistema de finanzas.

## 🏗️ Estructura Base (Regla 50/30/20)

### 1️⃣ **NECESIDADES** (50%)
Gastos esenciales para vivir

### 2️⃣ **GUSTOS** (30%)
Gastos discrecionales y entretenimiento

### 3️⃣ **AHORROS** (20%)
Ahorro e inversiones

---

## 📊 NECESIDADES (50%)

### 🏠 **Vivienda**
- Alquiler
- Servicios públicos (agua, luz, internet)
- Mantenimiento del hogar
- Seguro de hogar

### 🚗 **Transporte**
- Gasolina
- Mantenimiento vehículo
- Seguro vehículo
- **Peajes y Parking** (Compass BAC)
- Transporte público
- Uber/Taxi

### 🍽️ **Alimentación**
- Supermercado
- Carnicería/Verdulería
- Panadería

### 💊 **Salud**
- Medicamentos
- Consultas médicas
- Seguro médico
- Emergencias

### 👔 **Trabajo**
- Almuerzos oficina
- Ropa trabajo
- Herramientas/Equipamiento
- Capacitación

### 👨‍👩‍👧 **Familia**
- **Ayuda a abuela** (nuevo)
- Ayuda a otros familiares
- Pensión alimenticia

### 🧾 **Obligaciones Financieras**
- **Seguros de tarjeta**
- **Comisiones bancarias**
- Impuestos
- Servicios financieros

---

## 🎉 GUSTOS (30%)

### 🍔 **Comida Social**
- Restaurantes
- Fast food
- Cafeterías
- Delivery

### 🎮 **Entretenimiento**
- Streaming (Netflix, Spotify, etc.)
- Videojuegos
- Cine
- Conciertos/Eventos

### ⚽ **Deportes y Hobbies**
- **Fútbol semanal** (nuevo)
- Gimnasio
- Equipo deportivo
- Otros hobbies

### 🛍️ **Compras No Esenciales**
- Ropa casual
- Accesorios
- Electrónicos
- Decoración

### ✈️ **Viajes y Ocio**
- Vacaciones
- Paseos
- Hoteles

### 🎲 **Otros Gustos**
- **Lotería** (nuevo)
- Apuestas
- Regalos

---

## 💰 AHORROS (20%)

### 🏦 **Ahorro Emergencia**
- Fondo de emergencia
- Ahorro a la vista

### 📈 **Inversiones**
- CDPs
- ETFs
- Fondos de inversión
- Ahorro programado

### 🎯 **Metas Específicas**
- Marchamo carro
- Viaje específico
- Compra grande planificada

---

## 🔧 CATEGORÍAS ESPECIALES

### ⚠️ **Sin Categorizar**
- Transacciones que Claude no pudo categorizar
- Pendientes de revisión manual

### 🔄 **Transferencias Intermediarias**
- Alquiler (mamá → tu → casero)
- Compras para otros
- Dinero de paso

### 💸 **Reembolsos**
- Refunds de compras
- Devoluciones
- Reembolsos de seguros

### 🤝 **Gastos Compartidos**
- Fútbol semanal
- Salidas grupales
- Regalos grupales

### 👪 **Ayuda Familiar**
- Mamá → Abuela
- Otros familiares

---

## 🏷️ KEYWORDS PARA AUTO-CATEGORIZACIÓN

### Transporte:
```
gasolina, gasolinera, shell, delta, uno, recope, taller, mecanico, 
lavado, lavadero, peaje, parking, parqueo, compass, uber, taxi, 
bus, tren
```

### Supermercado:
```
walmart, automercado, pali, mas x menos, fresh market, pricesmart,
megasuper, saretto, auto mercado
```

### Fast Food:
```
mcdonalds, burger king, kfc, subway, pizza hut, dominos, taco bell,
wendys, arbys, papa johns, little caesars
```

### Restaurantes:
```
restaurante, soda, marisqueria, pizzeria, cafeteria, cafe, sushi,
chilis, applebees, olive garden, ihop
```

### Farmacias:
```
farmacia, botica, fischel, clinica, caja, ebais, hospital
```

### Streaming:
```
netflix, spotify, amazon prime, disney, hbo, apple music, youtube,
paramount, crunchyroll
```

### Deportes:
```
gimnasio, gym, cancha, futbol, soccer, natacion, piscina
```

### Servicios:
```
kolbi, claro, movistar, ice, kölbi, recibo, agua, luz, electricidad,
internet, cable, tigo
```

---

## 💡 NOTAS DE IMPLEMENTACIÓN

1. **Compass BAC**: Categorizar como "Necesidades/Transporte/Peajes y Parking"
2. **Fútbol semanal**: "Gustos/Deportes" + `tipo_especial=SHARED`
3. **Ayuda a abuela**: "Necesidades/Familia/Ayuda a abuela"
4. **Lotería**: "Gustos/Otros Gustos/Lotería"
5. **Seguros tarjeta**: "Necesidades/Obligaciones Financieras/Seguros de tarjeta"
6. **Intereses**: "Necesidades/Obligaciones Financieras/Intereses bancarios"

---

## 🎯 REGLAS DE CATEGORIZACIÓN

### Regla 1: Frecuencia
- Si es recurrente y esencial → Necesidades
- Si es recurrente y opcional → Gustos

### Regla 2: Prioridad
- ¿Puedes vivir sin esto? → Gustos
- ¿Es indispensable? → Necesidades

### Regla 3: Contexto
- Almuerzo trabajo → Necesidades/Trabajo
- Almuerzo fin de semana → Gustos/Comida Social

### Regla 4: Montos
- Compras >₡50,000 siempre necesitan revisión
- Compras <₡1,000 se auto-aprueban (alta confianza)

---

**Última actualización:** Nov 14, 2025

