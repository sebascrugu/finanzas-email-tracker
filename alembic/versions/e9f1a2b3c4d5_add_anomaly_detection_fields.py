"""add anomaly detection fields to transactions

Revision ID: e9f1a2b3c4d5
Revises: d8e9f0a1b2c3
Create Date: 2025-11-22 21:35:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e9f1a2b3c4d5"
down_revision: Union[str, None] = "d8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add anomaly detection fields to transactions table."""

    # Add is_anomaly boolean field
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_anomaly",
                sa.Boolean(),
                nullable=False,
                server_default="0",
                comment="Si la transacción fue detectada como anómala por ML",
            )
        )
        batch_op.create_index("ix_transactions_is_anomaly", ["is_anomaly"], unique=False)

        batch_op.add_column(
            sa.Column(
                "anomaly_score",
                sa.Numeric(precision=5, scale=4),
                nullable=True,
                comment="Score de anomalía (-1 a 1, donde < 0 es anómalo). Isolation Forest output.",
            )
        )

        batch_op.add_column(
            sa.Column(
                "anomaly_reason",
                sa.String(length=255),
                nullable=True,
                comment="Razón de por qué se marcó como anómala (ej: 'Monto inusualmente alto')",
            )
        )


def downgrade() -> None:
    """Remove anomaly detection fields from transactions table."""

    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.drop_index("ix_transactions_is_anomaly")
        batch_op.drop_column("anomaly_reason")
        batch_op.drop_column("anomaly_score")
        batch_op.drop_column("is_anomaly")
