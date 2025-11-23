"""add goal enhancements and milestones

Revision ID: g1h2i3j4k5l6
Revises: 2a1d446b3a68
Create Date: 2025-11-23 00:00:00.000000

Summary:
- Add new columns to savings_goals table for Phase 3 enhancements:
  - icon: emoji/icon for visual representation
  - priority: 1=High, 2=Medium, 3=Low
  - savings_type: manual, automatic, monthly_target
  - monthly_contribution_target: suggested monthly contribution
  - success_probability: ML-predicted probability of success (0-100)
  - last_ml_prediction_at: timestamp of last ML prediction
  - ai_recommendations: personalized recommendations from Claude
  - last_ai_analysis_at: timestamp of last AI analysis
- Create goal_milestones table for tracking progress history
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'g1h2i3j4k5l6'
down_revision: str | Sequence[str] | None = 'f0a1b2c3d4e5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create goal_milestones table
    op.create_table(
        'goal_milestones',
        sa.Column('id', sa.String(36), primary_key=True, comment='UUID único del hito'),
        sa.Column(
            'goal_id',
            sa.String(36),
            sa.ForeignKey('savings_goals.id', ondelete='CASCADE'),
            nullable=False,
            comment='ID de la meta asociada',
        ),
        sa.Column(
            'milestone_type',
            sa.String(50),
            nullable=False,
            comment="Tipo de hito: 'progress', 'contribution', 'alert', 'achievement'",
        ),
        sa.Column(
            'title',
            sa.String(200),
            nullable=False,
            comment="Título del hito (ej: 'Alcanzaste 25%')",
        ),
        sa.Column(
            'description',
            sa.Text(),
            nullable=True,
            comment='Descripción opcional del hito',
        ),
        sa.Column(
            'amount_at_milestone',
            sa.Numeric(15, 2),
            nullable=False,
            comment='Monto ahorrado al momento del hito',
        ),
        sa.Column(
            'percentage_at_milestone',
            sa.Numeric(5, 2),
            nullable=False,
            comment='Porcentaje de progreso al momento del hito (0-100)',
        ),
        sa.Column(
            'contribution_amount',
            sa.Numeric(15, 2),
            nullable=True,
            comment='Monto de la contribución (si aplica)',
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            comment='Fecha del hito',
        ),
    )

    # Add index on goal_id for faster queries
    op.create_index('ix_goal_milestones_goal_id', 'goal_milestones', ['goal_id'])

    # Add new columns to savings_goals table
    with op.batch_alter_table('savings_goals', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'icon',
                sa.String(10),
                nullable=True,
                comment="Emoji/icono de la meta (ej: '✈️', '🏠', '⚽')",
            )
        )
        batch_op.add_column(
            sa.Column(
                'priority',
                sa.Integer(),
                nullable=False,
                server_default='3',
                comment='Prioridad de la meta (1=Alta, 2=Media, 3=Baja)',
            )
        )
        batch_op.add_column(
            sa.Column(
                'savings_type',
                sa.String(50),
                nullable=False,
                server_default='manual',
                comment="Tipo de ahorro: 'manual', 'automatic', 'monthly_target'",
            )
        )
        batch_op.add_column(
            sa.Column(
                'monthly_contribution_target',
                sa.Numeric(15, 2),
                nullable=True,
                comment='Meta de contribución mensual sugerida/configurada',
            )
        )
        batch_op.add_column(
            sa.Column(
                'success_probability',
                sa.Numeric(5, 2),
                nullable=True,
                comment='Probabilidad de éxito calculada por ML (0-100)',
            )
        )
        batch_op.add_column(
            sa.Column(
                'last_ml_prediction_at',
                sa.DateTime(timezone=True),
                nullable=True,
                comment='Última vez que se calculó la predicción ML',
            )
        )
        batch_op.add_column(
            sa.Column(
                'ai_recommendations',
                sa.Text(),
                nullable=True,
                comment='Recomendaciones personalizadas generadas por Claude AI',
            )
        )
        batch_op.add_column(
            sa.Column(
                'last_ai_analysis_at',
                sa.DateTime(timezone=True),
                nullable=True,
                comment='Última vez que Claude analizó esta meta',
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop new columns from savings_goals table
    with op.batch_alter_table('savings_goals', schema=None) as batch_op:
        batch_op.drop_column('last_ai_analysis_at')
        batch_op.drop_column('ai_recommendations')
        batch_op.drop_column('last_ml_prediction_at')
        batch_op.drop_column('success_probability')
        batch_op.drop_column('monthly_contribution_target')
        batch_op.drop_column('savings_type')
        batch_op.drop_column('priority')
        batch_op.drop_column('icon')

    # Drop goal_milestones table
    op.drop_index('ix_goal_milestones_goal_id', table_name='goal_milestones')
    op.drop_table('goal_milestones')
