# ADR-001: PostgreSQL + pgvector como único storage

## Estado
**Aceptado** - Enero 2025

## Contexto

El proyecto necesita:
1. **Almacenamiento transaccional** - CRUD de transacciones, categorías, perfiles
2. **Búsqueda vectorial** - Para RAG y categorización inteligente con embeddings
3. **Precisión financiera** - Manejo exacto de decimales para montos

Las opciones consideradas fueron:

| Opción | Pros | Contras |
|--------|------|---------|
| PostgreSQL + ChromaDB | Especialización | 2 DBs, complejidad operacional |
| PostgreSQL + Pinecone | Managed, escalable | Costo, vendor lock-in, latencia |
| PostgreSQL + pgvector | Un solo DB, simplicidad | Menos features que DBs dedicados |
| SQLite + ChromaDB | Simple para dev | No escala, sin Decimal nativo |

## Decisión

Usamos **PostgreSQL 16 con extensión pgvector** como único sistema de almacenamiento.

```yaml
# docker-compose.yml
services:
  db:
    image: pgvector/pgvector:pg16
```

### Implementación

```sql
-- Habilitar extensión
CREATE EXTENSION vector;

-- Tabla de embeddings
CREATE TABLE transaction_embeddings (
    id SERIAL PRIMARY KEY,
    transaction_id INTEGER REFERENCES transactions(id),
    embedding vector(1536),  -- OpenAI ada-002 dimension
    model_version VARCHAR(50)
);

-- Índice para búsqueda rápida
CREATE INDEX ON transaction_embeddings 
USING ivfflat (embedding vector_cosine_ops);
```

## Consecuencias

### Positivas
- **Simplicidad operacional**: Un solo servicio de DB para mantener
- **Transacciones ACID**: Embeddings y datos en la misma transacción
- **Tipo Numeric nativo**: Precisión exacta para dinero
- **Menor costo**: No hay servicio de vector DB separado
- **Menor latencia**: No hay network hop a otro servicio

### Negativas
- **Escalabilidad limitada**: pgvector no escala como Pinecone para billones de vectors
- **Menos features**: No tiene metadata filtering avanzado
- **Performance**: Más lento que DBs vectoriales dedicados para datasets grandes

### Riesgos Mitigados
- **Volumen esperado**: <100K transacciones/año por usuario, pgvector maneja bien
- **Si necesitamos migrar**: Los embeddings son portables, solo cambiar storage layer

## Referencias

- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [Supabase Vector Guide](https://supabase.com/docs/guides/ai)
- [PostgreSQL Numeric Type](https://www.postgresql.org/docs/current/datatype-numeric.html)
