# 🎯 Mejoras Pendientes (Basadas en Pruebas Reales)

Este documento captura las mejoras identificadas durante las pruebas del sistema en **Noviembre 2025**.

---

## 🔥 ALTA PRIORIDAD

### 1. Dashboard Web para Configuración ⭐⭐⭐
**Problema:** La terminal no es user-friendly para usuarios normales.

**Solución:**
- Crear interfaz web (Streamlit) para setup de usuario
- Formularios visuales en vez de CLI
- Validación en tiempo real
- Preview de configuración antes de guardar

**Impacto:** 🚀 CRÍTICO para adopción de usuarios no-técnicos

**Mockup:**
```
┌─────────────────────────────────────────┐
│  🎯 Configuración Inicial               │
├─────────────────────────────────────────┤
│                                         │
│  📧 Email: [___________________]        │
│  👤 Nombre: [__________________]        │
│  💰 Salario Neto Mensual: ₡[_______]   │
│                                         │
│  📊 Regla 50/30/20 (Recomendado)        │
│   ■ 50% Necesidades     ₡140,000       │
│   ■ 30% Gustos          ₡84,000        │
│   ■ 20% Ahorros         ₡56,000        │
│                                         │
│  💳 Tarjetas                             │
│   ■ **** 6380 (Crédito BAC)            │
│   ■ **** 3640 (Débito BAC)              │
│   [+ Agregar tarjeta]                   │
│                                         │
│          [💾 Guardar Configuración]     │
└─────────────────────────────────────────┘
```

---

### 2. Simplificar Regla 50/30/20 ⭐⭐⭐
**Problema:** La regla es OPCIONAL, pero sin ella el sistema no tiene sentido.

**Solución:**
- **Hacer la regla 50/30/20 obligatoria**
- Eliminar la opción de personalizar porcentajes (al menos en v1.0)
- Si el usuario quiere cambiar, que lo haga DESPUÉS en el dashboard

**Motivo:** 
- Sin presupuesto definido, no hay control
- Simplifica onboarding (menos decisiones = menos fricción)
- La mayoría de usuarios no sabe qué porcentajes usar

**Cambio en código:**
```python
# ❌ ANTES (opcional):
usar_recomendado = input("¿Usar distribución 50/30/20? (S/n): ")

# ✅ DESPUÉS (obligatorio):
logger.info("📊 Usaremos la regla 50/30/20:")
logger.info("  - 50% Necesidades (transporte, trabajo, personal)")
logger.info("  - 30% Gustos (comida, entretenimiento, shopping)")
logger.info("  - 20% Ahorros (ahorro regular, metas)")
pct_necesidades = Decimal("50.00")
pct_gustos = Decimal("30.00")
pct_ahorros = Decimal("20.00")
```

---

### 3. Aclarar "Salario NETO" ⭐⭐
**Problema:** El campo dice "NETO", pero podría ser más claro.

**Solución:**
```python
# ❌ ANTES:
salario_str = input("💵 Salario/Ingreso mensual NETO (en colones): ₡")

# ✅ DESPUÉS:
logger.info("💡 Tip: Usa tu salario NETO (después de deducciones)")
logger.info("    Ej: Si te depositan ₡280,000, ese es tu NETO")
salario_str = input("💵 Salario mensual NETO (lo que te depositan): ₡")
```

---

## 🎨 MEDIA PRIORIDAD

### 4. Validación de Tarjetas con Luhn Algorithm ⭐⭐
**Problema:** Se aceptan cualquier 4 dígitos sin validación.

**Solución:**
- Implementar Luhn algorithm para validar números de tarjeta
- Al menos validar que sean números
- Sugerir último extracto si el usuario no recuerda

---

### 5. Setup Wizard Multi-Paso ⭐⭐
**Problema:** Un solo formulario largo es abrumador.

**Solución:**
```
Paso 1/4: Información Personal     [●○○○]
Paso 2/4: Presupuesto               [●●○○]
Paso 3/4: Tarjetas                  [●●●○]
Paso 4/4: Confirmación              [●●●●]
```

---

### 6. Onboarding con Video/Tutorial ⭐
**Problema:** Usuario no sabe qué hacer después del setup.

**Solución:**
- Video de 2 minutos mostrando el flujo completo
- Tutorial interactivo en dashboard
- Checklist: ✅ Setup → ✅ Process → ✅ Review → ✅ Balance

---

## 🔮 BAJA PRIORIDAD (Futuro)

### 7. Importar Datos de Banco
- Conectar con API bancaria (si existe)
- Subir extracto PDF y parsear automáticamente
- Sincronización automática diaria

### 8. Notificaciones Push
- "Procesamos 15 transacciones nuevas"
- "Te queda 20% del presupuesto de Gustos"
- "¡Alcanzaste tu meta de ahorro!"

### 9. Multi-Idioma
- Inglés
- Portugués (Brasil)
- Otros países latinoamericanos

---

## 📝 Notas de Diseño

### Principios UX:
1. **Menos es más**: Cada campo que quitamos = menos fricción
2. **Defaults inteligentes**: Sugerir 50/30/20, auto-detectar banco por email
3. **Progressive disclosure**: No mostrar opciones avanzadas en setup inicial
4. **Instant feedback**: Validar en tiempo real, no al final

### Stack Sugerido para Dashboard:
- **Streamlit** (actual, ya en pyproject.toml)
  - ✅ Rápido de implementar
  - ✅ Python puro
  - ✅ Componentes listos
  - ❌ Limitado para UX muy custom

- **FastAPI + React** (futuro, si crecemos)
  - ✅ UX profesional
  - ✅ Altamente customizable
  - ❌ Más complejo
  - ❌ Requiere más tiempo

**Decisión:** Empezar con Streamlit, migrar a FastAPI+React si es necesario.

---

## 🎯 Roadmap de Implementación

### Fase 1: MVP Dashboard (Diciembre 2025)
- [ ] Dashboard básico de Streamlit
- [ ] Setup de usuario en web
- [ ] Ver transacciones y balance
- [ ] Filtros simples

### Fase 2: Mejoras UX (Enero 2026)
- [ ] Regla 50/30/20 obligatoria
- [ ] Setup wizard multi-paso
- [ ] Validaciones mejoradas
- [ ] Tutorial interactivo

### Fase 3: Features Avanzadas (Feb-Mar 2026)
- [ ] Gráficos y reportes
- [ ] Exportar a Excel/PDF
- [ ] Metas financieras
- [ ] Alertas predictivas

---

## 💡 Ideas de la Comunidad

Si tienes ideas, agrégalas aquí:

1. **[Tu idea]**: Descripción
2. **[Tu idea]**: Descripción

---

**Última actualización:** 14 de Noviembre, 2025  
**Responsable:** Sebastian Cruz  
**Estado:** En desarrollo activo 🚀

