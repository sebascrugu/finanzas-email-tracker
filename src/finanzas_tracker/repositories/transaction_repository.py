"""Repository para Transacciones."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.repositories.base import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    """
    Repositorio para operaciones de Transacciones.

    Extiende BaseRepository con queries específicas para transacciones
    financieras: filtros por fecha, monto, categoría, etc.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(Transaction, db)

    def get_by_profile(
        self,
        profile_id: str | UUID,
        *,
        skip: int = 0,
        limit: int = 50,
        mes: date | None = None,
        categoria_id: str | None = None,
        tipo: str | None = None,
        banco: str | None = None,
        desde: date | None = None,
        hasta: date | None = None,
    ) -> list[Transaction]:
        """
        Lista transacciones de un perfil con filtros opcionales.

        Args:
            profile_id: ID del perfil
            skip: Registros a saltar
            limit: Máximo de registros
            mes: Filtrar por mes (usa año y mes de la fecha)
            categoria_id: Filtrar por subcategoría
            tipo: Filtrar por tipo de transacción
            banco: Filtrar por banco
            desde: Fecha inicial
            hasta: Fecha final

        Returns:
            Lista de transacciones ordenadas por fecha desc
        """
        profile_id_str = str(profile_id) if isinstance(profile_id, UUID) else profile_id

        stmt = select(self.model).where(
            self.model.profile_id == profile_id_str,
            self.model.deleted_at.is_(None),
        )

        # Aplicar filtros
        if mes:
            stmt = stmt.where(
                func.extract("year", self.model.fecha_transaccion) == mes.year,
                func.extract("month", self.model.fecha_transaccion) == mes.month,
            )

        if categoria_id:
            stmt = stmt.where(self.model.subcategory_id == categoria_id)

        if tipo:
            stmt = stmt.where(self.model.tipo_transaccion == tipo)

        if banco:
            stmt = stmt.where(self.model.banco == banco)

        if desde:
            stmt = stmt.where(
                self.model.fecha_transaccion >= datetime.combine(desde, datetime.min.time())
            )

        if hasta:
            stmt = stmt.where(
                self.model.fecha_transaccion <= datetime.combine(hasta, datetime.max.time())
            )

        stmt = stmt.order_by(self.model.fecha_transaccion.desc()).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def count_by_profile(
        self,
        profile_id: str | UUID,
        *,
        mes: date | None = None,
        categoria_id: str | None = None,
        tipo: str | None = None,
        banco: str | None = None,
        desde: date | None = None,
        hasta: date | None = None,
    ) -> int:
        """Cuenta transacciones de un perfil con los mismos filtros."""
        profile_id_str = str(profile_id) if isinstance(profile_id, UUID) else profile_id

        stmt = select(func.count()).where(
            self.model.profile_id == profile_id_str,
            self.model.deleted_at.is_(None),
        )

        if mes:
            stmt = stmt.where(
                func.extract("year", self.model.fecha_transaccion) == mes.year,
                func.extract("month", self.model.fecha_transaccion) == mes.month,
            )

        if categoria_id:
            stmt = stmt.where(self.model.subcategory_id == categoria_id)

        if tipo:
            stmt = stmt.where(self.model.tipo_transaccion == tipo)

        if banco:
            stmt = stmt.where(self.model.banco == banco)

        if desde:
            stmt = stmt.where(
                self.model.fecha_transaccion >= datetime.combine(desde, datetime.min.time())
            )

        if hasta:
            stmt = stmt.where(
                self.model.fecha_transaccion <= datetime.combine(hasta, datetime.max.time())
            )

        return self.db.execute(stmt).scalar() or 0

    def get_by_email_id(self, email_id: str) -> Transaction | None:
        """Busca transacción por ID de email (para detección de duplicados)."""
        stmt = select(self.model).where(
            self.model.email_id == email_id,
            self.model.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_total_by_month(
        self,
        profile_id: str | UUID,
        year: int,
        month: int,
    ) -> Decimal:
        """Obtiene el total gastado en un mes."""
        profile_id_str = str(profile_id) if isinstance(profile_id, UUID) else profile_id

        stmt = select(func.sum(self.model.monto_crc)).where(
            self.model.profile_id == profile_id_str,
            self.model.deleted_at.is_(None),
            func.extract("year", self.model.fecha_transaccion) == year,
            func.extract("month", self.model.fecha_transaccion) == month,
        )

        result = self.db.execute(stmt).scalar()
        return Decimal(str(result)) if result else Decimal("0")

    def get_by_category(
        self,
        profile_id: str | UUID,
        subcategory_id: str,
        *,
        limit: int = 20,
    ) -> list[Transaction]:
        """Lista transacciones recientes de una categoría."""
        profile_id_str = str(profile_id) if isinstance(profile_id, UUID) else profile_id

        stmt = (
            select(self.model)
            .where(
                self.model.profile_id == profile_id_str,
                self.model.subcategory_id == subcategory_id,
                self.model.deleted_at.is_(None),
            )
            .order_by(self.model.fecha_transaccion.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())
