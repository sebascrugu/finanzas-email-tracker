# Architecture Decision Records (ADRs)

Este directorio contiene los Architecture Decision Records del proyecto Finanzas Tracker CR.

## ¿Qué son los ADRs?

Los ADRs documentan decisiones arquitectónicas importantes junto con su contexto y consecuencias. Son útiles para:

- Entender *por qué* se tomó una decisión
- Onboarding de nuevos desarrolladores
- Evitar re-discutir decisiones ya tomadas
- Documentar trade-offs

## Formato

Cada ADR sigue esta estructura:

```markdown
# ADR-XXX: Título

## Estado
[Propuesto | Aceptado | Deprecado | Supersedido por ADR-YYY]

## Contexto
¿Cuál era el problema o necesidad?

## Decisión
¿Qué decidimos hacer?

## Consecuencias
- Positivas
- Negativas
- Riesgos
```

## Índice de ADRs

| ID | Título | Estado |
|----|--------|--------|
| [ADR-001](./001-postgresql-pgvector.md) | PostgreSQL + pgvector como único storage | Aceptado |
| [ADR-002](./002-repository-pattern.md) | Repository Pattern para acceso a datos | Aceptado |
| [ADR-003](./003-soft-delete.md) | Soft Delete obligatorio | Aceptado |
| [ADR-004](./004-decimal-for-money.md) | Decimal para campos monetarios | Aceptado |

## Cómo agregar un nuevo ADR

1. Crear archivo `XXX-titulo-corto.md`
2. Usar el template de arriba
3. Agregar al índice en este README
4. Commit con mensaje: `docs: add ADR-XXX titulo`
