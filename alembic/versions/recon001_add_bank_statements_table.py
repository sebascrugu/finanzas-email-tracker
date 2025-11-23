"""Add bank_statements table for PDF reconciliation.

Revision ID: recon001
Revises: perf001
Create Date: 2025-11-23 16:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "recon001"
down_revision: Union[str, None] = "perf001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create bank_statements table."""
    # Create bank_statements table
    op.create_table(
        "bank_statements",
        # ID
        sa.Column("id", sa.String(36), nullable=False, comment="UUID único del estado de cuenta"),
        # Profile relationship
        sa.Column(
            "profile_id",
            sa.String(36),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
            comment="ID del perfil al que pertenece este estado de cuenta",
        ),
        # Statement info
        sa.Column("banco", sa.String(50), nullable=False, comment="Banco: bac o popular"),
        sa.Column(
            "cuenta_iban",
            sa.String(50),
            nullable=False,
            comment="IBAN de la cuenta (ej: CR72 0102 0000 9661 5395 99)",
        ),
        sa.Column(
            "fecha_corte",
            sa.Date,
            nullable=False,
            comment="Fecha de corte del estado de cuenta",
        ),
        sa.Column(
            "periodo",
            sa.String(20),
            nullable=False,
            comment="Período del estado (ej: '2025-10', 'Octubre 2025')",
        ),
        # PDF metadata
        sa.Column(
            "pdf_filename", sa.String(255), nullable=False, comment="Nombre original del archivo PDF"
        ),
        sa.Column(
            "pdf_hash",
            sa.String(64),
            nullable=True,
            comment="Hash SHA-256 del PDF para detectar duplicados",
        ),
        # Extracted data
        sa.Column(
            "saldo_inicial",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            comment="Saldo inicial del período",
        ),
        sa.Column(
            "saldo_final",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            comment="Saldo final del período",
        ),
        sa.Column(
            "total_debitos",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            comment="Total de débitos en el período",
        ),
        sa.Column(
            "total_creditos",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            comment="Total de créditos en el período",
        ),
        # Reconciliation stats
        sa.Column(
            "total_transactions_pdf",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="Total de transacciones encontradas en el PDF",
        ),
        sa.Column(
            "matched_count",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="Transacciones que hicieron match con emails",
        ),
        sa.Column(
            "missing_in_emails_count",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="Transacciones en PDF pero no en emails",
        ),
        sa.Column(
            "missing_in_statement_count",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="Transacciones en emails pero no en PDF",
        ),
        sa.Column(
            "discrepancies_count",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="Transacciones con discrepancias (monto diferente, etc.)",
        ),
        # Report JSON
        sa.Column(
            "reconciliation_report",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
            comment="Reporte completo de reconciliación en JSON",
        ),
        # Processing status
        sa.Column(
            "processing_status",
            sa.String(50),
            nullable=False,
            server_default="pending",
            comment="Estado: pending, processing, completed, failed",
        ),
        sa.Column(
            "error_message",
            sa.Text,
            nullable=True,
            comment="Mensaje de error si falló el procesamiento",
        ),
        # User notes
        sa.Column(
            "notas",
            sa.Text,
            nullable=True,
            comment="Notas adicionales del usuario sobre la reconciliación",
        ),
        # Soft delete
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Fecha de eliminación (soft delete)",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="Fecha de creación del registro",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="Fecha de última actualización",
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Fecha en que se completó el procesamiento",
        ),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index(
        "ix_bank_statements_profile_id", "bank_statements", ["profile_id"], unique=False
    )
    op.create_index(
        "ix_bank_statements_banco", "bank_statements", ["banco"], unique=False
    )
    op.create_index(
        "ix_bank_statements_fecha_corte", "bank_statements", ["fecha_corte"], unique=False
    )
    op.create_index(
        "ix_bank_statements_pdf_hash", "bank_statements", ["pdf_hash"], unique=False
    )
    op.create_index(
        "ix_bank_statements_processing_status",
        "bank_statements",
        ["processing_status"],
        unique=False,
    )
    op.create_index(
        "ix_bank_statements_deleted_at", "bank_statements", ["deleted_at"], unique=False
    )
    op.create_index(
        "ix_bank_statements_created_at", "bank_statements", ["created_at"], unique=False
    )

    # Composite indexes
    op.create_index(
        "ix_bank_statements_profile_fecha",
        "bank_statements",
        ["profile_id", "fecha_corte"],
        unique=False,
    )
    op.create_index(
        "ix_bank_statements_profile_banco",
        "bank_statements",
        ["profile_id", "banco"],
        unique=False,
    )
    op.create_index(
        "ix_bank_statements_status", "bank_statements", ["processing_status"], unique=False
    )


def downgrade() -> None:
    """Drop bank_statements table."""
    # Drop indexes first
    op.drop_index("ix_bank_statements_status", table_name="bank_statements")
    op.drop_index("ix_bank_statements_profile_banco", table_name="bank_statements")
    op.drop_index("ix_bank_statements_profile_fecha", table_name="bank_statements")
    op.drop_index("ix_bank_statements_created_at", table_name="bank_statements")
    op.drop_index("ix_bank_statements_deleted_at", table_name="bank_statements")
    op.drop_index("ix_bank_statements_processing_status", table_name="bank_statements")
    op.drop_index("ix_bank_statements_pdf_hash", table_name="bank_statements")
    op.drop_index("ix_bank_statements_fecha_corte", table_name="bank_statements")
    op.drop_index("ix_bank_statements_banco", table_name="bank_statements")
    op.drop_index("ix_bank_statements_profile_id", table_name="bank_statements")

    # Drop table
    op.drop_table("bank_statements")
