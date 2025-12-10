"""add_onboarding_fields_to_profile

Revision ID: 123e1ab89fe0
Revises: 88802a30080f
Create Date: 2025-12-07 10:17:30.232935

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '123e1ab89fe0'
down_revision: str | Sequence[str] | None = '88802a30080f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Agregar campos de onboarding al perfil."""
    # Agregar campo onboarding_completado con default False
    op.add_column(
        'profiles',
        sa.Column(
            'onboarding_completado',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
            comment='Si el usuario completó el onboarding inicial'
        )
    )
    
    # Agregar campo onboarding_step para tracking
    op.add_column(
        'profiles',
        sa.Column(
            'onboarding_step',
            sa.String(length=50),
            nullable=True,
            comment='Paso actual del onboarding (para resumir si cierra)'
        )
    )


def downgrade() -> None:
    """Remover campos de onboarding."""
    op.drop_column('profiles', 'onboarding_step')
    op.drop_column('profiles', 'onboarding_completado')
