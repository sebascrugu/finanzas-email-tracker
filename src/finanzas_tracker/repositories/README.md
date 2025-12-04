# Repositories

## ¿Qué es el Patrón Repository?

El **Repository Pattern** separa la lógica de acceso a datos (queries SQL) de la lógica de negocio (services).

```
Service (lógica) → Repository (datos) → Database
```

## Estado Actual

| Repository | Estado | Uso |
|------------|--------|-----|
| `BaseRepository` | ✅ Completo | CRUD genérico |
| `ProfileRepository` | ✅ Completo | Perfiles |
| `TransactionRepository` | ✅ Completo | Transacciones |

## ¿Por qué existe?

Algunos services usan directamente SQLAlchemy (queries en el service).
Otros usan repositories (queries en el repository).

**Eventual consistencia:** Migrar todo a usar repositories para:
1. Tests más fáciles (mockear repository, no DB)
2. Queries reusables
3. Separación clara de responsabilidades

## Cómo Usar

```python
from finanzas_tracker.repositories import ProfileRepository

# En un service
class MyService:
    def __init__(self, db: Session) -> None:
        self.profile_repo = ProfileRepository(db)
    
    def get_user_data(self, profile_id: str):
        profile = self.profile_repo.get(profile_id)
        # ... lógica de negocio
```

## TODO

- [ ] Crear repositories para todos los modelos
- [ ] Migrar services a usar repositories
- [ ] Tests para repositories
