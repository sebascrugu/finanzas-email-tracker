"""Add PDF reconciliation fields to onboarding_progress.

Revision ID: recon002
Revises: recon001
Create Date: 2025-11-23 17:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "recon002"
down_revision: Union[str, None] = "recon001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add PDF reconciliation tracking fields to onboarding_progress."""
    # Add new fields
    op.add_column(
        "onboarding_progress",
        sa.Column(
            "bank_statement_uploaded",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Si subió el estado de cuenta PDF durante onboarding",
        ),
    )

    op.add_column(
        "onboarding_progress",
        sa.Column(
            "bank_statement_id",
            sa.String(36),
            nullable=True,
            comment="ID del BankStatement procesado durante onboarding",
        ),
    )

    op.add_column(
        "onboarding_progress",
        sa.Column(
            "reconciliation_completed",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Si completó la reconciliación inicial con PDF",
        ),
    )

    op.add_column(
        "onboarding_progress",
        sa.Column(
            "reconciliation_summary",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
            comment="Resumen de la reconciliación inicial (matched, missing, etc.)",
        ),
    )

    op.add_column(
        "onboarding_progress",
        sa.Column(
            "transactions_added_from_pdf",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Número de transacciones agregadas automáticamente desde el PDF",
        ),
    )


def downgrade() -> None:
    """Remove PDF reconciliation fields from onboarding_progress."""
    op.drop_column("onboarding_progress", "transactions_added_from_pdf")
    op.drop_column("onboarding_progress", "reconciliation_summary")
    op.drop_column("onboarding_progress", "reconciliation_completed")
    op.drop_column("onboarding_progress", "bank_statement_id")
    op.drop_column("onboarding_progress", "bank_statement_uploaded")
