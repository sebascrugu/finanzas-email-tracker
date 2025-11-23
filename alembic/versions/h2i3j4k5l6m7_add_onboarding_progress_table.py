"""add onboarding progress table

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2025-11-23 06:00:00.000000

Summary:
- Create onboarding_progress table for wizard state persistence
- Tracks progress through 6-step onboarding wizard
- Allows pause/resume functionality
- Stores temporary wizard data (profile_id, detected cards count, etc.)
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'h2i3j4k5l6m7'
down_revision: str | Sequence[str] | None = 'g1h2i3j4k5l6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create onboarding_progress table
    op.create_table(
        'onboarding_progress',
        sa.Column('id', sa.String(36), primary_key=True, comment='UUID único del progreso'),
        sa.Column(
            'email',
            sa.String(255),
            unique=True,
            nullable=False,
            comment='Email del usuario (único por onboarding)',
        ),
        # Progreso general
        sa.Column(
            'current_step',
            sa.Integer(),
            nullable=False,
            server_default='1',
            comment='Paso actual del wizard (1-6)',
        ),
        sa.Column(
            'is_completed',
            sa.Boolean(),
            nullable=False,
            server_default='0',
            comment='Si completó todo el onboarding',
        ),
        # Estado de cada paso
        sa.Column(
            'step1_welcome',
            sa.String(20),
            nullable=False,
            server_default='not_started',
            comment='Estado del paso 1: Bienvenida',
        ),
        sa.Column(
            'step2_profile',
            sa.String(20),
            nullable=False,
            server_default='not_started',
            comment='Estado del paso 2: Crear Perfil',
        ),
        sa.Column(
            'step3_email',
            sa.String(20),
            nullable=False,
            server_default='not_started',
            comment='Estado del paso 3: Conectar Email',
        ),
        sa.Column(
            'step4_cards',
            sa.String(20),
            nullable=False,
            server_default='not_started',
            comment='Estado del paso 4: Detectar Tarjetas',
        ),
        sa.Column(
            'step5_income',
            sa.String(20),
            nullable=False,
            server_default='not_started',
            comment='Estado del paso 5: Configurar Ingreso',
        ),
        sa.Column(
            'step6_import',
            sa.String(20),
            nullable=False,
            server_default='not_started',
            comment='Estado del paso 6: Primera Importación',
        ),
        # Datos temporales del wizard
        sa.Column(
            'profile_id',
            sa.String(36),
            nullable=True,
            comment='ID del perfil creado',
        ),
        sa.Column(
            'detected_cards_count',
            sa.Integer(),
            nullable=True,
            comment='Número de tarjetas detectadas',
        ),
        sa.Column(
            'imported_transactions_count',
            sa.Integer(),
            nullable=True,
            comment='Número de transacciones importadas',
        ),
        # Metadata
        sa.Column(
            'wizard_version',
            sa.String(10),
            nullable=False,
            server_default='1.0',
            comment='Versión del wizard para compatibilidad futura',
        ),
        sa.Column(
            'notes',
            sa.Text(),
            nullable=True,
            comment='Notas adicionales o errores encontrados',
        ),
        # Timestamps
        sa.Column(
            'started_at',
            sa.DateTime(timezone=True),
            nullable=False,
            comment='Cuándo empezó el onboarding',
        ),
        sa.Column(
            'completed_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Cuándo completó el onboarding',
        ),
        sa.Column(
            'last_activity_at',
            sa.DateTime(timezone=True),
            nullable=False,
            comment='Última actividad en el wizard',
        ),
    )

    # Add indices for faster queries
    op.create_index('ix_onboarding_progress_email', 'onboarding_progress', ['email'])
    op.create_index('ix_onboarding_progress_is_completed', 'onboarding_progress', ['is_completed'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indices
    op.drop_index('ix_onboarding_progress_is_completed', table_name='onboarding_progress')
    op.drop_index('ix_onboarding_progress_email', table_name='onboarding_progress')

    # Drop table
    op.drop_table('onboarding_progress')
