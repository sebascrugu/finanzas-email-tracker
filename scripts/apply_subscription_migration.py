#!/usr/bin/env python3
"""Script temporal para aplicar la migración de subscriptions sin keyring."""

from pathlib import Path
import sys


# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Evitar que se carguen servicios estableciendo variable de entorno
import os


os.environ["SKIP_SERVICES_INIT"] = "1"

from sqlalchemy import create_engine, text


# Crear engine directamente sin importar servicios
engine = create_engine("sqlite:///data/finanzas.db")

# SQL para crear la tabla subscriptions
create_table_sql = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id VARCHAR(26) NOT NULL,
    profile_id VARCHAR(26) NOT NULL,
    merchant_id VARCHAR(26),
    comercio VARCHAR(255) NOT NULL,
    monto_promedio NUMERIC(10, 2) NOT NULL,
    monto_min NUMERIC(10, 2) NOT NULL,
    monto_max NUMERIC(10, 2) NOT NULL,
    frecuencia_dias INTEGER NOT NULL,
    primera_fecha_cobro DATE NOT NULL,
    ultima_fecha_cobro DATE NOT NULL,
    proxima_fecha_estimada DATE NOT NULL,
    occurrences_count INTEGER NOT NULL,
    confidence_score NUMERIC(5, 2) NOT NULL,
    is_active BOOLEAN NOT NULL,
    is_confirmed BOOLEAN NOT NULL,
    notas TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    deleted_at DATETIME,
    PRIMARY KEY (id),
    FOREIGN KEY(profile_id) REFERENCES profiles (id),
    FOREIGN KEY(merchant_id) REFERENCES merchants (id)
);
"""

# Crear índices
create_indexes_sql = [
    "CREATE INDEX IF NOT EXISTS ix_subscriptions_profile_id ON subscriptions (profile_id);",
    "CREATE INDEX IF NOT EXISTS ix_subscriptions_merchant_id ON subscriptions (merchant_id);",
    "CREATE INDEX IF NOT EXISTS ix_subscriptions_is_active ON subscriptions (is_active);",
    "CREATE INDEX IF NOT EXISTS ix_subscriptions_proxima_fecha_estimada ON subscriptions (proxima_fecha_estimada);",
    "CREATE INDEX IF NOT EXISTS ix_subscriptions_deleted_at ON subscriptions (deleted_at);",
]

# Ejecutar SQL
try:
    with engine.connect() as conn:
        # Crear tabla
        print("Creando tabla subscriptions...")  # noqa: T201
        conn.execute(text(create_table_sql))
        conn.commit()
        print("✅ Tabla creada")  # noqa: T201

        # Crear índices
        print("\nCreando índices...")  # noqa: T201
        for idx_sql in create_indexes_sql:
            conn.execute(text(idx_sql))
        conn.commit()
        print("✅ Índices creados")  # noqa: T201

        # Actualizar alembic_version (si existe)
        print("\nActualizando alembic_version...")  # noqa: T201
        try:
            conn.execute(text("UPDATE alembic_version SET version_num = 'f0a1b2c3d4e5';"))
            conn.commit()
            print("✅ alembic_version actualizado")  # noqa: T201
        except Exception:
            print("ℹ️  alembic_version no existe (ok para nuevas instalaciones)")  # noqa: T201, RUF001

        print("\n✅ Migración completada exitosamente")  # noqa: T201

except Exception as e:
    print(f"❌ Error: {e}")  # noqa: T201
    sys.exit(1)
