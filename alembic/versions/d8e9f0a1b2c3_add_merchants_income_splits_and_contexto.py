"""add merchants, income splits, and contexto fields

Revision ID: d8e9f0a1b2c3
Revises: c7d4e5f6a1b2
Create Date: 2025-11-21 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, None] = "c7d4e5f6a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add merchant normalization, income splits, and contexto fields."""

    # ========================================================================
    # 1. CREATE MERCHANTS TABLE
    # ========================================================================
    op.create_table(
        "merchants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "nombre_normalizado",
            sa.String(length=100),
            nullable=False,
            comment="Nombre normalizado del comercio (ej: 'Subway')",
        ),
        sa.Column(
            "categoria_principal",
            sa.String(length=50),
            nullable=True,
            comment="Categoría principal (ej: 'Restaurante')",
        ),
        sa.Column(
            "subcategoria",
            sa.String(length=50),
            nullable=True,
            comment="Subcategoría (ej: 'Comida Rápida')",
        ),
        sa.Column(
            "tipo_negocio",
            sa.String(length=50),
            nullable=True,
            comment="Tipo de negocio (food_service, retail, etc.)",
        ),
        sa.Column("que_vende", sa.Text(), nullable=True, comment="Descripción de productos/servicios"),
        sa.Column("logo_url", sa.String(length=255), nullable=True, comment="URL del logo del comercio"),
        sa.Column("sitio_web", sa.String(length=255), nullable=True, comment="Sitio web oficial"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_merchants")),
    )
    op.create_index(op.f("ix_merchants_nombre_normalizado"), "merchants", ["nombre_normalizado"], unique=False)

    # ========================================================================
    # 2. CREATE MERCHANT_VARIANTS TABLE
    # ========================================================================
    op.create_table(
        "merchant_variants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("merchant_id", sa.String(length=36), nullable=False),
        sa.Column(
            "nombre_raw",
            sa.String(length=200),
            nullable=False,
            comment="Nombre como aparece en el correo (ej: 'SUBWAY MOMENTUM')",
        ),
        sa.Column("ciudad", sa.String(length=100), nullable=True, comment="Ciudad donde se ubica"),
        sa.Column("pais", sa.String(length=50), nullable=False, server_default="Costa Rica"),
        sa.Column(
            "confianza_match",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default="100.0",
            comment="Nivel de confianza del match (0-100)",
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["merchant_id"], ["merchants.id"], name=op.f("fk_merchant_variants_merchant_id_merchants"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_merchant_variants")),
        sa.UniqueConstraint("nombre_raw", "ciudad", "pais", name=op.f("uq_merchant_variants_nombre_ciudad_pais")),
    )
    op.create_index(op.f("ix_merchant_variants_merchant_id"), "merchant_variants", ["merchant_id"], unique=False)
    op.create_index(op.f("ix_merchant_variants_nombre_raw"), "merchant_variants", ["nombre_raw"], unique=False)

    # ========================================================================
    # 3. CREATE INCOME_SPLITS TABLE
    # ========================================================================
    op.create_table(
        "income_splits",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("income_id", sa.String(length=36), nullable=False),
        sa.Column("transaction_id", sa.String(length=36), nullable=False),
        sa.Column(
            "monto_asignado",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            comment="Monto del ingreso asignado a este gasto",
        ),
        sa.Column("proposito", sa.Text(), nullable=True, comment="Propósito del gasto (ej: 'Dona para mamá')"),
        sa.Column(
            "confianza_match",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default="100.0",
            comment="Nivel de confianza del match (0-100)",
        ),
        sa.Column(
            "sugerido_por_ai",
            sa.Boolean(),
            nullable=False,
            server_default="0",
            comment="Si fue sugerido automáticamente por IA",
        ),
        sa.Column("razonamiento_ai", sa.Text(), nullable=True, comment="Explicación de la IA para la vinculación"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["income_id"], ["incomes.id"], name=op.f("fk_income_splits_income_id_incomes"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name=op.f("fk_income_splits_transaction_id_transactions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_income_splits")),
    )
    op.create_index(op.f("ix_income_splits_income_id"), "income_splits", ["income_id"], unique=False)
    op.create_index(op.f("ix_income_splits_transaction_id"), "income_splits", ["transaction_id"], unique=False)

    # ========================================================================
    # 4. ADD NEW FIELDS TO INCOMES TABLE
    # ========================================================================
    op.add_column(
        "incomes",
        sa.Column(
            "contexto",
            sa.Text(),
            nullable=True,
            comment="Contexto del ingreso en lenguaje natural",
        ),
    )
    op.add_column(
        "incomes",
        sa.Column(
            "tipo_especial",
            sa.String(length=50),
            nullable=True,
            comment="Tipo especial: dinero_ajeno, intermediaria, etc.",
        ),
    )
    op.add_column(
        "incomes",
        sa.Column(
            "excluir_de_presupuesto",
            sa.Boolean(),
            nullable=False,
            server_default="0",
            comment="Excluir de cálculos de presupuesto mensual",
        ),
    )
    op.add_column(
        "incomes",
        sa.Column(
            "es_dinero_ajeno",
            sa.Boolean(),
            nullable=False,
            server_default="0",
            comment="Si el dinero es de otra persona",
        ),
    )
    op.add_column(
        "incomes",
        sa.Column(
            "requiere_desglose",
            sa.Boolean(),
            nullable=False,
            server_default="0",
            comment="Si requiere desglose por gastos específicos",
        ),
    )
    op.add_column(
        "incomes",
        sa.Column(
            "monto_usado",
            sa.Numeric(precision=15, scale=2),
            nullable=True,
            comment="Monto usado del dinero ajeno",
        ),
    )
    op.add_column(
        "incomes",
        sa.Column(
            "monto_sobrante",
            sa.Numeric(precision=15, scale=2),
            nullable=True,
            comment="Monto sobrante que te quedaste",
        ),
    )

    # ========================================================================
    # 5. ADD NEW FIELDS TO TRANSACTIONS TABLE
    # ========================================================================
    op.add_column(
        "transactions",
        sa.Column("merchant_id", sa.String(length=36), nullable=True, comment="ID del comercio normalizado"),
    )
    op.add_column(
        "transactions",
        sa.Column(
            "contexto",
            sa.Text(),
            nullable=True,
            comment="Contexto del gasto en lenguaje natural",
        ),
    )
    op.create_foreign_key(
        op.f("fk_transactions_merchant_id_merchants"),
        "transactions",
        "merchants",
        ["merchant_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_transactions_merchant_id"), "transactions", ["merchant_id"], unique=False)

    # ========================================================================
    # 6. ADD NEW INDEXES FOR PERFORMANCE
    # ========================================================================
    op.create_index(op.f("ix_transactions_created_at"), "transactions", ["created_at"], unique=False)
    op.create_index(op.f("ix_categories_nombre"), "categories", ["nombre"], unique=False)


def downgrade() -> None:
    """Remove merchant normalization, income splits, and contexto fields."""

    # Indexes
    op.drop_index(op.f("ix_categories_nombre"), table_name="categories")
    op.drop_index(op.f("ix_transactions_created_at"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_merchant_id"), table_name="transactions")

    # Transaction foreign key and columns
    op.drop_constraint(op.f("fk_transactions_merchant_id_merchants"), "transactions", type_="foreignkey")
    op.drop_column("transactions", "contexto")
    op.drop_column("transactions", "merchant_id")

    # Income columns
    op.drop_column("incomes", "monto_sobrante")
    op.drop_column("incomes", "monto_usado")
    op.drop_column("incomes", "requiere_desglose")
    op.drop_column("incomes", "es_dinero_ajeno")
    op.drop_column("incomes", "excluir_de_presupuesto")
    op.drop_column("incomes", "tipo_especial")
    op.drop_column("incomes", "contexto")

    # Income splits table
    op.drop_index(op.f("ix_income_splits_transaction_id"), table_name="income_splits")
    op.drop_index(op.f("ix_income_splits_income_id"), table_name="income_splits")
    op.drop_table("income_splits")

    # Merchant variants table
    op.drop_index(op.f("ix_merchant_variants_nombre_raw"), table_name="merchant_variants")
    op.drop_index(op.f("ix_merchant_variants_merchant_id"), table_name="merchant_variants")
    op.drop_table("merchant_variants")

    # Merchants table
    op.drop_index(op.f("ix_merchants_nombre_normalizado"), table_name="merchants")
    op.drop_table("merchants")
