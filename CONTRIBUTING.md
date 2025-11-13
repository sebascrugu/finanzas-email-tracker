# Contribuyendo a Finanzas Email Tracker

¡Gracias por tu interés en contribuir! Este proyecto es principalmente personal, pero las sugerencias y mejoras son bienvenidas.

## 🐛 Reportar Bugs

Si encuentras un bug:

1. Verifica que no exista un issue similar
2. Abre un nuevo issue con:
   - Descripción clara del problema
   - Pasos para reproducirlo
   - Comportamiento esperado vs actual
   - Tu versión de Python y sistema operativo

## 💡 Sugerir Mejoras

Para sugerir una mejora:

1. Abre un issue describiendo tu idea
2. Explica por qué sería útil
3. Si es posible, proporciona ejemplos

## 🔧 Contribuir Código

### Setup de Desarrollo

1. Fork el repositorio
2. Clona tu fork:
```bash
git clone https://github.com/tu-usuario/finanzas-email-tracker.git
cd finanzas-email-tracker
```

3. Instala las dependencias:
```bash
poetry install
```

4. Crea una rama para tu feature:
```bash
git checkout -b feature/mi-nueva-feature
```

### Estándares de Código

- ✅ Usa type hints en todas las funciones
- ✅ Escribe docstrings para funciones públicas
- ✅ Sigue PEP 8 (Ruff lo verifica automáticamente)
- ✅ Escribe tests para nuevas funcionalidades
- ✅ Asegúrate de que pasen todos los tests

### Verificar tu Código

Antes de hacer commit:

```bash
# Verificar linting
poetry run ruff check .

# Formatear código
poetry run ruff format .

# Ejecutar tests
poetry run pytest

# Type checking
poetry run mypy src/
```

### Hacer un Pull Request

1. Asegúrate de que todos los tests pasen
2. Asegúrate de que no haya errores de linting
3. Haz commit de tus cambios con mensajes descriptivos
4. Push a tu fork
5. Abre un Pull Request con:
   - Descripción clara de los cambios
   - Referencia a issues relacionados
   - Screenshots si es relevante

## 📝 Convenciones de Commits

Usamos commits descriptivos:

- `feat: agregar nueva funcionalidad`
- `fix: corregir bug en parser de correos`
- `docs: actualizar README`
- `test: agregar tests para email_fetcher`
- `refactor: mejorar estructura de database.py`
- `style: formatear código con ruff`

## 🙏 Código de Conducta

- Sé respetuoso y profesional
- Acepta críticas constructivas
- Enfócate en lo mejor para el proyecto

## ❓ Preguntas

Si tienes preguntas, abre un issue con la etiqueta "question".

---

¡Gracias por contribuir! 🎉


