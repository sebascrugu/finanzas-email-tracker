"""Repositorios para acceso a datos.

Implementan el Repository Pattern para separar la lógica de acceso
a datos de la lógica de negocio en los services.

Uso:
    ```python
    from finanzas_tracker.repositories import (
        TransactionRepository,
        ProfileRepository,
    )

    repo = TransactionRepository(db)
    transactions = repo.get_by_profile(profile_id, mes=date(2024, 1, 1))
    ```
"""

from finanzas_tracker.repositories.base import BaseRepository
from finanzas_tracker.repositories.profile_repository import ProfileRepository
from finanzas_tracker.repositories.transaction_repository import TransactionRepository


__all__ = [
    "BaseRepository",
    "ProfileRepository",
    "TransactionRepository",
]
