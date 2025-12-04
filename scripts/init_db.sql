-- =============================================================================
-- Script de inicialización de PostgreSQL para Finanzas Tracker CR
-- Se ejecuta automáticamente al crear el contenedor por primera vez
-- =============================================================================

-- Habilitar extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- Para generar UUIDs
CREATE EXTENSION IF NOT EXISTS "vector";          -- Para embeddings/pgvector
CREATE EXTENSION IF NOT EXISTS "pg_trgm";         -- Para búsqueda fuzzy de texto

-- Configurar parámetros de la base de datos
ALTER DATABASE finanzas_tracker SET timezone TO 'America/Costa_Rica';

-- Crear schema opcional para separar datos (futuro multi-tenant)
-- CREATE SCHEMA IF NOT EXISTS app;

-- Mensaje de confirmación
DO $$
BEGIN
    RAISE NOTICE '✅ Extensiones habilitadas: uuid-ossp, vector, pg_trgm';
    RAISE NOTICE '✅ Timezone configurado: America/Costa_Rica';
    RAISE NOTICE '✅ Base de datos lista para Finanzas Tracker CR';
END $$;
