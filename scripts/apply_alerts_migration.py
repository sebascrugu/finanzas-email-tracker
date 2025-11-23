#!/usr/bin/env python3
"""Script temporal para aplicar la migración de alerts, alert_configs, credit_cards y savings_goals sin keyring."""

import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Evitar que se carguen servicios estableciendo variable de entorno
import os

os.environ["SKIP_SERVICES_INIT"] = "1"

from sqlalchemy import create_engine, text

# Crear engine directamente sin importar servicios
engine = create_engine("sqlite:///data/finanzas.db")

# SQL para crear la tabla alerts
create_alerts_table_sql = """
CREATE TABLE IF NOT EXISTS alerts (
    id VARCHAR(36) NOT NULL,
    profile_id VARCHAR(26) NOT NULL,
    transaction_id VARCHAR(26),
    subscription_id VARCHAR(26),
    budget_id VARCHAR(26),
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    read_at DATETIME,
    resolved_at DATETIME,
    dismissed_at DATETIME,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE CASCADE,
    FOREIGN KEY(transaction_id) REFERENCES transactions (id) ON DELETE SET NULL,
    FOREIGN KEY(subscription_id) REFERENCES subscriptions (id) ON DELETE SET NULL,
    FOREIGN KEY(budget_id) REFERENCES budgets (id) ON DELETE SET NULL
);
"""

# SQL para crear la tabla alert_configs
create_alert_configs_table_sql = """
CREATE TABLE IF NOT EXISTS alert_configs (
    id VARCHAR(36) NOT NULL,
    profile_id VARCHAR(26) NOT NULL,
    enable_anomaly_alerts BOOLEAN NOT NULL DEFAULT 1,
    enable_subscription_alerts BOOLEAN NOT NULL DEFAULT 1,
    enable_budget_alerts BOOLEAN NOT NULL DEFAULT 1,
    enable_category_spike_alerts BOOLEAN NOT NULL DEFAULT 1,
    enable_international_alerts BOOLEAN NOT NULL DEFAULT 1,
    enable_high_spending_alerts BOOLEAN NOT NULL DEFAULT 0,
    enable_unusual_time_alerts BOOLEAN NOT NULL DEFAULT 0,
    enable_multiple_purchase_alerts BOOLEAN NOT NULL DEFAULT 0,
    enable_credit_card_closing_alerts BOOLEAN NOT NULL DEFAULT 1,
    enable_savings_goal_alerts BOOLEAN NOT NULL DEFAULT 1,
    subscription_alert_days_ahead INTEGER NOT NULL DEFAULT 3,
    credit_card_alert_days INTEGER NOT NULL DEFAULT 3,
    savings_goal_alert_frequency INTEGER NOT NULL DEFAULT 7,
    budget_alert_threshold NUMERIC(5, 2) NOT NULL DEFAULT 85.0,
    category_spike_threshold NUMERIC(5, 2) NOT NULL DEFAULT 3.0,
    high_spending_threshold NUMERIC(15, 2),
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE CASCADE,
    UNIQUE (profile_id)
);
"""

# SQL para crear la tabla credit_cards
create_credit_cards_table_sql = """
CREATE TABLE IF NOT EXISTS credit_cards (
    id VARCHAR(36) NOT NULL,
    profile_id VARCHAR(26) NOT NULL,
    last_four_digits VARCHAR(4) NOT NULL,
    card_nickname VARCHAR(100),
    bank_name VARCHAR(100),
    closing_day INTEGER NOT NULL,
    payment_due_day INTEGER NOT NULL,
    credit_limit NUMERIC(15, 2),
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    deleted_at DATETIME,
    PRIMARY KEY (id),
    FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE CASCADE
);
"""

# SQL para crear la tabla savings_goals
create_savings_goals_table_sql = """
CREATE TABLE IF NOT EXISTS savings_goals (
    id VARCHAR(36) NOT NULL,
    profile_id VARCHAR(26) NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    target_amount NUMERIC(15, 2) NOT NULL,
    current_amount NUMERIC(15, 2) NOT NULL DEFAULT 0,
    deadline DATE,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    is_completed BOOLEAN NOT NULL DEFAULT 0,
    completed_at DATETIME,
    category VARCHAR(100),
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    deleted_at DATETIME,
    PRIMARY KEY (id),
    FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE CASCADE
);
"""

# Crear índices para alerts
create_alerts_indexes_sql = [
    "CREATE INDEX IF NOT EXISTS ix_alerts_profile_id ON alerts (profile_id);",
    "CREATE INDEX IF NOT EXISTS ix_alerts_transaction_id ON alerts (transaction_id);",
    "CREATE INDEX IF NOT EXISTS ix_alerts_subscription_id ON alerts (subscription_id);",
    "CREATE INDEX IF NOT EXISTS ix_alerts_budget_id ON alerts (budget_id);",
    "CREATE INDEX IF NOT EXISTS ix_alerts_alert_type ON alerts (alert_type);",
    "CREATE INDEX IF NOT EXISTS ix_alerts_severity ON alerts (severity);",
    "CREATE INDEX IF NOT EXISTS ix_alerts_status ON alerts (status);",
    "CREATE INDEX IF NOT EXISTS ix_alerts_created_at ON alerts (created_at);",
    "CREATE INDEX IF NOT EXISTS ix_alerts_profile_status ON alerts (profile_id, status);",
]

# Crear índices para alert_configs
create_alert_configs_indexes_sql = [
    "CREATE INDEX IF NOT EXISTS ix_alert_configs_profile_id ON alert_configs (profile_id);",
]

# Crear índices para credit_cards
create_credit_cards_indexes_sql = [
    "CREATE INDEX IF NOT EXISTS ix_credit_cards_profile_id ON credit_cards (profile_id);",
    "CREATE INDEX IF NOT EXISTS ix_credit_cards_is_active ON credit_cards (is_active);",
]

# Crear índices para savings_goals
create_savings_goals_indexes_sql = [
    "CREATE INDEX IF NOT EXISTS ix_savings_goals_profile_id ON savings_goals (profile_id);",
    "CREATE INDEX IF NOT EXISTS ix_savings_goals_is_active ON savings_goals (is_active);",
    "CREATE INDEX IF NOT EXISTS ix_savings_goals_is_completed ON savings_goals (is_completed);",
]

# Ejecutar SQL
try:
    with engine.connect() as conn:
        # Crear tabla alerts
        print("Creando tabla alerts...")
        conn.execute(text(create_alerts_table_sql))
        conn.commit()
        print("✅ Tabla alerts creada")

        # Crear tabla alert_configs
        print("\nCreando tabla alert_configs...")
        conn.execute(text(create_alert_configs_table_sql))
        conn.commit()
        print("✅ Tabla alert_configs creada")

        # Crear tabla credit_cards
        print("\nCreando tabla credit_cards...")
        conn.execute(text(create_credit_cards_table_sql))
        conn.commit()
        print("✅ Tabla credit_cards creada")

        # Crear tabla savings_goals
        print("\nCreando tabla savings_goals...")
        conn.execute(text(create_savings_goals_table_sql))
        conn.commit()
        print("✅ Tabla savings_goals creada")

        # Crear índices para alerts
        print("\nCreando índices para alerts...")
        for idx_sql in create_alerts_indexes_sql:
            conn.execute(text(idx_sql))
        conn.commit()
        print("✅ Índices de alerts creados")

        # Crear índices para alert_configs
        print("\nCreando índices para alert_configs...")
        for idx_sql in create_alert_configs_indexes_sql:
            conn.execute(text(idx_sql))
        conn.commit()
        print("✅ Índices de alert_configs creados")

        # Crear índices para credit_cards
        print("\nCreando índices para credit_cards...")
        for idx_sql in create_credit_cards_indexes_sql:
            conn.execute(text(idx_sql))
        conn.commit()
        print("✅ Índices de credit_cards creados")

        # Crear índices para savings_goals
        print("\nCreando índices para savings_goals...")
        for idx_sql in create_savings_goals_indexes_sql:
            conn.execute(text(idx_sql))
        conn.commit()
        print("✅ Índices de savings_goals creados")

        # Actualizar alembic_version (si existe)
        print("\nActualizando alembic_version...")
        try:
            conn.execute(text("UPDATE alembic_version SET version_num = 'a1b2c3d4e5f6';"))
            conn.commit()
            print("✅ alembic_version actualizado")
        except Exception:
            print("ℹ️  alembic_version no existe (ok para nuevas instalaciones)")

        print("\n✅ Migración completada exitosamente")
        print("\n📋 Tablas creadas:")
        print("  - alerts (alertas inteligentes)")
        print("  - alert_configs (configuración de alertas)")
        print("  - credit_cards (tarjetas de crédito)")
        print("  - savings_goals (metas de ahorro)")
        print("\n💡 Las alertas se generarán automáticamente al procesar correos")
        print("💡 Agrega tarjetas y metas para recibir alertas personalizadas")

except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
