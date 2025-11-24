"""Add card fields for alert system (balance, interest rate, expiration).

Revision ID: alert001
Revises: recon002
Create Date: 2025-11-24 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "alert001"
down_revision: Union[str, None] = "recon002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add fields to cards table for alert functionality."""
    # Add current_balance field for high interest projection alerts
    op.add_column(
        "cards",
        sa.Column(
            "current_balance",
            sa.Numeric(precision=15, scale=2),
            nullable=True,
            comment="Saldo actual de la tarjeta de crédito en colones",
        ),
    )

    # Add interest_rate_annual field
    op.add_column(
        "cards",
        sa.Column(
            "interest_rate_annual",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
            comment="Tasa de interés anual en % (ej: 52.00 para 52%)",
        ),
    )

    # Add minimum_payment_percentage field
    op.add_column(
        "cards",
        sa.Column(
            "minimum_payment_percentage",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
            comment="Porcentaje de pago mínimo (ej: 2.50 para 2.5%)",
        ),
    )

    # Add card_expiration_date field for card expiration alerts
    op.add_column(
        "cards",
        sa.Column(
            "card_expiration_date",
            sa.Date(),
            nullable=True,
            comment="Fecha de vencimiento del plástico (mes/año)",
        ),
    )


def downgrade() -> None:
    """Remove card fields for alert functionality."""
    op.drop_column("cards", "card_expiration_date")
    op.drop_column("cards", "minimum_payment_percentage")
    op.drop_column("cards", "interest_rate_annual")
    op.drop_column("cards", "current_balance")
