"""add learning tables for user preferences and contacts

Revision ID: f7a8b9c0d1e2
Revises: e9c12d4be588
Create Date: 2025-12-06 10:00:00.000000

Tablas para el sistema de aprendizaje:
- user_merchant_preferences: Preferencias de categorización por usuario
- user_contacts: Contactos SINPE aprendidos
- global_merchant_suggestions: Sugerencias crowdsourced
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "f7a8b9c0d1e2"
down_revision = "8e1de369a884"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Tabla: user_merchant_preferences
    # Preferencias de categorización personalizadas por usuario
    op.create_table(
        "user_merchant_preferences",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("merchant_pattern", sa.String(200), nullable=False, comment="Patrón del comercio (ej: 'UBER%', 'SINPE MARIA%')"),
        sa.Column("subcategory_id", sa.String(36), sa.ForeignKey("subcategories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("times_used", sa.Integer, default=1, comment="Veces que se ha usado esta preferencia"),
        sa.Column("confidence", sa.Numeric(3, 2), default=0.95, comment="Confianza de 0.00 a 1.00"),
        sa.Column("source", sa.String(50), default="user_correction", comment="Origen: user_correction, auto_detected"),
        sa.Column("user_label", sa.String(100), nullable=True, comment="Etiqueta personalizada del usuario (ej: 'Mamá')"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index(
        "ix_user_merchant_preferences_lookup",
        "user_merchant_preferences",
        ["profile_id", "merchant_pattern"],
    )

    # 2. Tabla: user_contacts
    # Contactos SINPE aprendidos del usuario
    op.create_table(
        "user_contacts",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("phone_number", sa.String(20), nullable=True, comment="Número SINPE (ej: 8888-1234)"),
        sa.Column("sinpe_name", sa.String(200), nullable=True, comment="Nombre como aparece en SINPE"),
        sa.Column("alias", sa.String(100), nullable=True, comment="Nombre que el usuario le pone (ej: 'Mamá')"),
        sa.Column("default_subcategory_id", sa.String(36), sa.ForeignKey("subcategories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("relationship_type", sa.String(50), nullable=True, comment="Tipo: family, friend, business, service"),
        sa.Column("total_transactions", sa.Integer, default=0),
        sa.Column("total_amount_crc", sa.Numeric(15, 2), default=0),
        sa.Column("last_transaction_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index(
        "ix_user_contacts_phone_lookup",
        "user_contacts",
        ["profile_id", "phone_number"],
        unique=True,
    )
    op.create_index(
        "ix_user_contacts_sinpe_name",
        "user_contacts",
        ["profile_id", "sinpe_name"],
    )

    # 3. Tabla: global_merchant_suggestions
    # Sugerencias de categorización crowdsourced
    op.create_table(
        "global_merchant_suggestions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("merchant_pattern", sa.String(200), nullable=False, comment="Patrón del comercio (ej: 'UBER%')"),
        sa.Column("suggested_subcategory_id", sa.String(36), sa.ForeignKey("subcategories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_count", sa.Integer, default=1, comment="Número de usuarios que sugirieron esto"),
        sa.Column("confidence_score", sa.Numeric(3, 2), comment="Score calculado de confianza"),
        sa.Column("status", sa.String(20), default="pending", comment="Estado: pending, approved, rejected"),
        sa.Column("approved_by", UUID(as_uuid=True), nullable=True, comment="Admin que aprobó"),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index(
        "ix_global_merchant_pattern_subcategory",
        "global_merchant_suggestions",
        ["merchant_pattern", "suggested_subcategory_id"],
        unique=True,
    )
    op.create_index(
        "ix_global_merchant_status",
        "global_merchant_suggestions",
        ["status"],
    )

    # 4. Agregar columnas a transactions para tracking de feedback
    # Usar IF NOT EXISTS para evitar errores si ya existen
    from sqlalchemy import inspect
    from alembic import op as alembic_op
    
    bind = alembic_op.get_bind()
    inspector = inspect(bind)
    existing_columns = [c['name'] for c in inspector.get_columns('transactions')]
    
    if "categoria_confirmada_usuario" not in existing_columns:
        op.add_column(
            "transactions",
            sa.Column(
                "categoria_confirmada_usuario",
                sa.Boolean,
                default=False,
                server_default=sa.text("false"),
                comment="True si el usuario confirmó/corrigió la categoría",
            ),
        )
    
    if "categoria_original_ia" not in existing_columns:
        op.add_column(
            "transactions",
            sa.Column(
                "categoria_original_ia",
                sa.String(100),
                nullable=True,
                comment="Categoría original sugerida por IA antes de corrección",
            ),
        )


def downgrade() -> None:
    # Remover columnas de transactions (si existen)
    from sqlalchemy import inspect
    from alembic import op as alembic_op
    
    bind = alembic_op.get_bind()
    inspector = inspect(bind)
    existing_columns = [c['name'] for c in inspector.get_columns('transactions')]
    
    if "categoria_original_ia" in existing_columns:
        op.drop_column("transactions", "categoria_original_ia")
    if "categoria_confirmada_usuario" in existing_columns:
        op.drop_column("transactions", "categoria_confirmada_usuario")

    # Remover tablas
    op.drop_table("global_merchant_suggestions")
    op.drop_table("user_contacts")
    op.drop_table("user_merchant_preferences")
