# PLAN DEFINITIVO: Finanzas Tracker Costa Rica
## Basado en Investigación de Mercado - Noviembre 2025

---

## RESUMEN EJECUTIVO

### Lo que la investigación reveló:

1. **El mercado existe**: Costa Rica tiene 4.2M usuarios potenciales, 76% adopción SINPE Móvil, y CERO apps de finanzas personales locales.

2. **La competencia ya tiene MCP**: Actual Budget tiene `actual-mcp` con CRUD básico. Tu MCP necesita ser DIFERENTE, no solo existir.

3. **Maybe Finance murió dos veces**: Gastaron $1M+ y fracasaron. Lección: no sobre-ingeniería, no 18 meses para MVP.

4. **ChromaDB es innecesario**: pgvector en PostgreSQL te da lo mismo con menos complejidad.

5. **El 87% de hiring managers valoran portfolios**: Pero quieren ver apps DEPLOYED que funcionen, no código bonito que no corre.

### Decisiones tecnológicas finales:

| Componente | Decisión | Razón |
|------------|----------|-------|
| Database | PostgreSQL + pgvector | Una sola DB para todo, ACID para finanzas |
| Backend | FastAPI | 84k stars, usado por Anthropic/OpenAI, ya lo conocés |
| Frontend | Streamlit (MVP) → Reflex (futuro) | Rápido para MVP, migración gradual después |
| Vector Search | pgvector (NO ChromaDB) | Menos complejidad, misma DB |
| AI | Claude API (Haiku para categorizacion, Sonnet para RAG) | Ya lo tenés integrado |
| MCP | Sí, pero DIFERENCIADO | No solo CRUD, coaching + predicción |

---

## FASE 0: PREPARACIÓN DE DATOS (Semana 1)
### Prioridad: CRÍTICA - Sin datos reales todo es teoría

**Objetivo**: Tener 500+ transacciones reales tuyas para validar todo.

### 0.1 Organizar tus estados de cuenta

```bash
# Estructura de carpetas
mkdir -p data/raw/bac_pdf
mkdir -p data/raw/sinpe_sms
mkdir -p data/processed
mkdir -p data/test_fixtures
```

Acciones:
- [ ] Recopilar TODOS tus PDFs del BAC (últimos 12 meses mínimo)
- [ ] Exportar historial de SMS de SINPE Móvil (screenshots o export)
- [ ] Identificar formato exacto de notificaciones email del BAC

### 0.2 Crear parser de PDF del BAC con Claude Vision

```python
# src/parsers/bac_pdf_parser.py
"""
Parser para estados de cuenta PDF del BAC Credomatic.
Usa Claude Vision para extracción - más robusto que regex.
"""
import anthropic
import base64
from pathlib import Path
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pdf2image import convert_from_path

@dataclass
class ParsedTransaction:
    fecha: date
    descripcion: str
    monto: Decimal
    tipo: str  # DEBITO | CREDITO
    referencia: str | None = None
    comercio_normalizado: str | None = None

@dataclass 
class StatementMetadata:
    numero_cuenta: str
    periodo_inicio: date
    periodo_fin: date
    saldo_anterior: Decimal
    saldo_final: Decimal

class BACPDFParser:
    """Extrae transacciones de estados de cuenta BAC usando Claude Vision."""
    
    def __init__(self):
        self.client = anthropic.Anthropic()
    
    def parse(self, pdf_path: str) -> dict:
        """
        Procesa un PDF completo del BAC.
        
        Returns:
            {
                "metadata": StatementMetadata,
                "transactions": list[ParsedTransaction],
                "raw_extraction": str  # Para debugging
            }
        """
        images = convert_from_path(pdf_path, dpi=200)
        all_transactions = []
        metadata = None
        
        for i, image in enumerate(images):
            result = self._extract_page(image, is_first_page=(i == 0))
            
            if result.get("transactions"):
                all_transactions.extend(result["transactions"])
            
            if i == 0 and result.get("metadata"):
                metadata = result["metadata"]
        
        # Deduplicar por referencia si existe
        unique_txns = self._deduplicate(all_transactions)
        
        return {
            "metadata": metadata,
            "transactions": unique_txns,
            "source_file": pdf_path,
            "pages_processed": len(images)
        }
    
    def _extract_page(self, image, is_first_page: bool) -> dict:
        """Extrae datos de una página usando Claude Vision."""
        import io
        
        # Convertir imagen a base64
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        prompt = self._build_extraction_prompt(is_first_page)
        
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_base64
                        }
                    },
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        
        return self._parse_response(response.content[0].text)
    
    def _build_extraction_prompt(self, include_metadata: bool) -> str:
        prompt = """Extrae TODAS las transacciones de este estado de cuenta del BAC Credomatic Costa Rica.

Para cada transacción devuelve:
- fecha: YYYY-MM-DD
- descripcion: texto original del comercio/concepto
- monto: número (negativo para débitos/gastos, positivo para créditos/depósitos)
- tipo: "DEBITO" o "CREDITO"
- referencia: número de referencia si existe

"""
        if include_metadata:
            prompt += """También extrae metadata del encabezado:
- numero_cuenta: últimos 4 dígitos o número completo
- periodo_inicio: YYYY-MM-DD
- periodo_fin: YYYY-MM-DD
- saldo_anterior: número
- saldo_final: número

"""
        
        prompt += """Responde ÚNICAMENTE con JSON válido, sin explicaciones:
{
    "metadata": {...} o null,
    "transactions": [
        {"fecha": "...", "descripcion": "...", "monto": -15000, "tipo": "DEBITO", "referencia": "..."},
        ...
    ]
}"""
        return prompt
    
    def _parse_response(self, text: str) -> dict:
        import json
        try:
            # Limpiar posibles markdown code blocks
            clean = text.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
                clean = clean.strip()
            return json.loads(clean)
        except json.JSONDecodeError:
            return {"metadata": None, "transactions": []}
    
    def _deduplicate(self, transactions: list) -> list:
        """Elimina duplicados basado en fecha + monto + descripción."""
        seen = set()
        unique = []
        for txn in transactions:
            key = (txn.get("fecha"), txn.get("monto"), txn.get("descripcion", "")[:30])
            if key not in seen:
                seen.add(key)
                unique.append(txn)
        return unique
```

### 0.3 Crear parser de SMS/Notificaciones SINPE Móvil

```python
# src/parsers/sinpe_parser.py
"""
Parser para notificaciones de SINPE Móvil.
Formato típico: "Ha recibido 15,000.00 Colones de NOMBRE por SINPE Movil, DESCRIPCION. Comprobante 123456"
"""
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

@dataclass
class SINPETransaction:
    tipo: str  # RECIBIDO | ENVIADO
    monto: Decimal
    moneda: str  # CRC | USD
    contraparte: str  # Nombre de quien envía/recibe
    descripcion: str | None
    comprobante: str | None
    fecha: datetime | None
    raw_text: str

class SINPEParser:
    """Parser para mensajes de SINPE Móvil."""
    
    # Patrones de mensajes SINPE
    PATTERNS = {
        "recibido": re.compile(
            r"Ha recibido\s+([\d,]+\.?\d*)\s+(Colones|Dolares)\s+de\s+(.+?)\s+por SINPE",
            re.IGNORECASE
        ),
        "enviado": re.compile(
            r"Ha enviado\s+([\d,]+\.?\d*)\s+(Colones|Dolares)\s+a\s+(.+?)\s+por SINPE",
            re.IGNORECASE
        ),
        "comprobante": re.compile(r"Comprobante\s+(\d+)", re.IGNORECASE),
        "descripcion": re.compile(r"SINPE\s+(?:Movil|Móvil),?\s*(.+?)\.?\s*(?:Comprobante|$)", re.IGNORECASE)
    }
    
    def parse(self, text: str, fecha: datetime = None) -> SINPETransaction | None:
        """
        Parsea un mensaje de SINPE Móvil.
        
        Args:
            text: Contenido del SMS o notificación
            fecha: Fecha del mensaje (si se conoce)
            
        Returns:
            SINPETransaction o None si no es mensaje SINPE válido
        """
        text = text.strip()
        
        # Detectar tipo (recibido o enviado)
        tipo = None
        match = None
        
        if m := self.PATTERNS["recibido"].search(text):
            tipo = "RECIBIDO"
            match = m
        elif m := self.PATTERNS["enviado"].search(text):
            tipo = "ENVIADO"
            match = m
        
        if not match:
            return None
        
        # Extraer datos básicos
        monto_str = match.group(1).replace(",", "")
        monto = Decimal(monto_str)
        
        moneda_raw = match.group(2).lower()
        moneda = "USD" if "dolar" in moneda_raw else "CRC"
        
        contraparte = match.group(3).strip()
        
        # Extraer comprobante
        comprobante = None
        if m := self.PATTERNS["comprobante"].search(text):
            comprobante = m.group(1)
        
        # Extraer descripción
        descripcion = None
        if m := self.PATTERNS["descripcion"].search(text):
            descripcion = m.group(1).strip()
            # Limpiar si termina en comprobante
            if descripcion and "Comprobante" in descripcion:
                descripcion = descripcion.split("Comprobante")[0].strip()
        
        # Ajustar monto según tipo
        if tipo == "ENVIADO":
            monto = -monto  # Gastos son negativos
        
        return SINPETransaction(
            tipo=tipo,
            monto=monto,
            moneda=moneda,
            contraparte=contraparte,
            descripcion=descripcion,
            comprobante=comprobante,
            fecha=fecha,
            raw_text=text
        )
    
    def parse_bulk(self, messages: list[dict]) -> list[SINPETransaction]:
        """
        Parsea múltiples mensajes.
        
        Args:
            messages: Lista de {"text": "...", "date": datetime}
        """
        results = []
        for msg in messages:
            parsed = self.parse(msg.get("text", ""), msg.get("date"))
            if parsed:
                results.append(parsed)
        return results
```

### 0.4 Script de procesamiento inicial

```python
# scripts/process_initial_data.py
"""
Procesa todos los datos iniciales (PDFs + SINPE) y genera fixtures de test.
"""
import asyncio
import json
from pathlib import Path
from datetime import datetime

async def main():
    from src.parsers.bac_pdf_parser import BACPDFParser
    from src.parsers.sinpe_parser import SINPEParser
    
    # Directorios
    raw_dir = Path("data/raw")
    output_dir = Path("data/processed")
    output_dir.mkdir(exist_ok=True)
    
    all_transactions = []
    
    # 1. Procesar PDFs del BAC
    pdf_parser = BACPDFParser()
    pdf_dir = raw_dir / "bac_pdf"
    
    if pdf_dir.exists():
        for pdf_file in sorted(pdf_dir.glob("*.pdf")):
            print(f"Procesando: {pdf_file.name}")
            try:
                result = pdf_parser.parse(str(pdf_file))
                
                # Guardar resultado individual
                output_file = output_dir / f"{pdf_file.stem}.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, default=str, ensure_ascii=False)
                
                # Agregar a consolidado
                for txn in result.get("transactions", []):
                    txn["source"] = "BAC_PDF"
                    txn["source_file"] = pdf_file.name
                    all_transactions.append(txn)
                
                print(f"  ✓ {len(result.get('transactions', []))} transacciones")
            except Exception as e:
                print(f"  ✗ Error: {e}")
    
    # 2. Procesar mensajes SINPE (si hay archivo de export)
    sinpe_parser = SINPEParser()
    sinpe_file = raw_dir / "sinpe_sms" / "messages.json"
    
    if sinpe_file.exists():
        print(f"\nProcesando SINPE: {sinpe_file}")
        with open(sinpe_file, "r", encoding="utf-8") as f:
            messages = json.load(f)
        
        sinpe_txns = sinpe_parser.parse_bulk(messages)
        print(f"  ✓ {len(sinpe_txns)} transacciones SINPE")
        
        for txn in sinpe_txns:
            all_transactions.append({
                "fecha": txn.fecha.isoformat() if txn.fecha else None,
                "descripcion": f"SINPE {txn.tipo}: {txn.contraparte}",
                "monto": float(txn.monto),
                "tipo": "CREDITO" if txn.tipo == "RECIBIDO" else "DEBITO",
                "referencia": txn.comprobante,
                "contraparte": txn.contraparte,
                "source": "SINPE_SMS",
                "moneda": txn.moneda
            })
    
    # 3. Guardar consolidado
    consolidated = {
        "processed_at": datetime.now().isoformat(),
        "total_transactions": len(all_transactions),
        "sources": {
            "BAC_PDF": len([t for t in all_transactions if t.get("source") == "BAC_PDF"]),
            "SINPE_SMS": len([t for t in all_transactions if t.get("source") == "SINPE_SMS"])
        },
        "transactions": sorted(all_transactions, key=lambda x: x.get("fecha", ""), reverse=True)
    }
    
    with open(output_dir / "all_transactions.json", "w", encoding="utf-8") as f:
        json.dump(consolidated, f, indent=2, default=str, ensure_ascii=False)
    
    print(f"\n{'='*50}")
    print(f"RESUMEN:")
    print(f"  Total transacciones: {len(all_transactions)}")
    print(f"  De BAC PDFs: {consolidated['sources']['BAC_PDF']}")
    print(f"  De SINPE SMS: {consolidated['sources']['SINPE_SMS']}")
    print(f"\nArchivos generados en: {output_dir}")
    
    # 4. Generar fixtures para tests
    if len(all_transactions) >= 50:
        fixtures = all_transactions[:50]  # Primeras 50 para tests
        fixtures_file = Path("data/test_fixtures/sample_transactions.json")
        fixtures_file.parent.mkdir(exist_ok=True)
        with open(fixtures_file, "w", encoding="utf-8") as f:
            json.dump(fixtures, f, indent=2, default=str, ensure_ascii=False)
        print(f"  Fixtures de test: {fixtures_file}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Entregables Fase 0:
- [ ] 500+ transacciones reales en `data/processed/all_transactions.json`
- [ ] Parser de BAC funcionando con tus PDFs reales
- [ ] Parser de SINPE funcionando
- [ ] Fixtures de test generadas

**Tiempo estimado**: 1 semana

---

## FASE 1: FUNDAMENTOS SÓLIDOS (Semanas 2-3)
### Prioridad: CRÍTICA - Base para todo lo demás

### 1.1 Configurar PostgreSQL + pgvector

**docker-compose.yml**:

```yaml
version: '3.8'

services:
  db:
    image: pgvector/pgvector:pg16
    container_name: finanzas_db
    environment:
      POSTGRES_DB: finanzas
      POSTGRES_USER: finanzas
      POSTGRES_PASSWORD: ${DB_PASSWORD:-desarrollo123}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init_db.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U finanzas"]
      interval: 5s
      timeout: 5s
      retries: 5

  # Redis para cache (opcional pero recomendado)
  redis:
    image: redis:7-alpine
    container_name: finanzas_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

**scripts/init_db.sql**:

```sql
-- Habilitar extensiones necesarias
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- Para búsqueda fuzzy

-- Índice para búsqueda de texto
CREATE INDEX IF NOT EXISTS idx_gin_trgm ON transactions USING gin (descripcion gin_trgm_ops);
```

### 1.2 Actualizar modelos SQLAlchemy para multi-tenancy

**CRÍTICO**: Agregar `tenant_id` desde AHORA. Aunque seas el único usuario, esto te prepara para SaaS sin migración dolorosa.

```python
# src/models/base.py
"""Base models with multi-tenancy support."""
from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, DateTime, String, Boolean, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, declared_attr

Base = declarative_base()

class TenantMixin:
    """Mixin que agrega tenant_id a todos los modelos."""
    
    @declared_attr
    def tenant_id(cls):
        return Column(
            UUID(as_uuid=True), 
            nullable=False, 
            index=True,
            default=uuid4  # Default para desarrollo single-tenant
        )

class TimestampMixin:
    """Mixin para timestamps automáticos."""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SoftDeleteMixin:
    """Mixin para soft delete."""
    deleted_at = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    
    def soft_delete(self):
        self.deleted_at = datetime.utcnow()
        self.is_deleted = True
    
    def restore(self):
        self.deleted_at = None
        self.is_deleted = False
```

```python
# src/models/transaction.py
"""Transaction model with vector embedding support."""
from decimal import Decimal
from datetime import date
from sqlalchemy import Column, Integer, String, Numeric, Date, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from .base import Base, TenantMixin, TimestampMixin, SoftDeleteMixin

class Transaction(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    """Transacción financiera."""
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True)
    
    # Datos core
    fecha = Column(Date, nullable=False, index=True)
    descripcion = Column(String(500), nullable=False)
    descripcion_normalizada = Column(String(500))  # Para búsqueda
    
    # Montos
    monto_original = Column(Numeric(15, 2), nullable=False)
    moneda_original = Column(String(3), default="CRC")  # CRC, USD
    monto_crc = Column(Numeric(15, 2), nullable=False)  # Siempre en colones
    tipo_cambio = Column(Numeric(10, 4))  # Si fue conversión
    
    # Clasificación
    tipo = Column(String(20), nullable=False)  # DEBITO, CREDITO
    categoria_id = Column(Integer, ForeignKey("categorias.id"))
    subcategoria_id = Column(Integer, ForeignKey("subcategorias.id"))
    
    # AI/ML
    categoria_sugerida = Column(String(100))
    confianza_categoria = Column(Numeric(5, 2))  # 0.00 - 1.00
    necesita_revision = Column(Boolean, default=False)
    
    # Embedding para búsqueda semántica (384 dims = MiniLM)
    embedding = Column(Vector(384))
    
    # Metadata
    comercio = Column(String(255))
    comercio_normalizado = Column(String(255))
    referencia = Column(String(100))
    
    # Origen
    source = Column(String(50))  # BAC_PDF, BAC_EMAIL, SINPE_SMS, MANUAL
    source_file = Column(String(255))
    email_id = Column(String(255), unique=True)  # Para deduplicación
    
    # Contexto usuario
    notas = Column(Text)
    tags = Column(JSONB, default=list)
    
    # Anomalías
    es_anomalia = Column(Boolean, default=False)
    anomalia_score = Column(Numeric(5, 4))
    anomalia_razon = Column(String(255))
    
    # Relaciones
    categoria = relationship("Categoria", back_populates="transactions")
    persona_asociada_id = Column(Integer, ForeignKey("personas.id"))
    persona = relationship("Persona", back_populates="transactions")
    
    # Índices
    __table_args__ = (
        # Índice compuesto para queries comunes
        Index('idx_txn_tenant_fecha', 'tenant_id', 'fecha'),
        Index('idx_txn_tenant_categoria', 'tenant_id', 'categoria_id'),
        # Índice para vector search
        Index(
            'idx_txn_embedding',
            'embedding',
            postgresql_using='ivfflat',
            postgresql_with={'lists': 100},
            postgresql_ops={'embedding': 'vector_cosine_ops'}
        ),
    )
    
    @property
    def es_gasto(self) -> bool:
        return self.monto_original < 0
    
    @property
    def es_ingreso(self) -> bool:
        return self.monto_original > 0
    
    @property
    def monto_display(self) -> str:
        """Formato para mostrar: ₡15,000 o $50.00"""
        simbolo = "₡" if self.moneda_original == "CRC" else "$"
        return f"{simbolo}{abs(self.monto_original):,.2f}"
```

```python
# src/models/persona.py
"""Modelo para personas/contactos financieros (tu idea de relaciones)."""
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base, TenantMixin, TimestampMixin

class Persona(Base, TenantMixin, TimestampMixin):
    """
    Persona con la que tenés relación financiera.
    Ej: mamá, roommate, cliente freelance, etc.
    """
    __tablename__ = "personas"
    
    id = Column(Integer, primary_key=True)
    
    nombre = Column(String(255), nullable=False)
    nombre_normalizado = Column(String(255), index=True)  # MAYÚSCULAS para matching
    
    # Tipo de relación
    tipo_relacion = Column(String(50))  # familia, amigo, trabajo, comercio
    
    # Contacto
    telefono = Column(String(20))  # Para matching con SINPE
    email = Column(String(255))
    
    # Metadata
    notas = Column(Text)
    metadata = Column(JSONB, default=dict)
    
    # Relaciones
    transactions = relationship("Transaction", back_populates="persona")
    
    @classmethod
    def normalizar_nombre(cls, nombre: str) -> str:
        """Normaliza nombre para matching fuzzy."""
        import unicodedata
        # Remover acentos
        normalized = unicodedata.normalize('NFKD', nombre)
        normalized = ''.join(c for c in normalized if not unicodedata.combining(c))
        # Mayúsculas, sin espacios extra
        return ' '.join(normalized.upper().split())
```

### 1.3 Migración Alembic

```python
# alembic/versions/001_initial_schema.py
"""Initial schema with pgvector support."""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

def upgrade():
    # Habilitar extensiones
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
    
    # Tabla de categorías
    op.create_table(
        'categorias',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('tenant_id', sa.UUID, nullable=False, index=True),
        sa.Column('nombre', sa.String(100), nullable=False),
        sa.Column('tipo', sa.String(20)),  # NECESIDAD, GUSTO, AHORRO
        sa.Column('icono', sa.String(10)),
        sa.Column('color', sa.String(7)),
        sa.Column('keywords', sa.ARRAY(sa.String)),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    
    # Tabla de subcategorías
    op.create_table(
        'subcategorias',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('tenant_id', sa.UUID, nullable=False, index=True),
        sa.Column('categoria_id', sa.Integer, sa.ForeignKey('categorias.id')),
        sa.Column('nombre', sa.String(100), nullable=False),
        sa.Column('keywords', sa.ARRAY(sa.String)),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    
    # Tabla de personas
    op.create_table(
        'personas',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('tenant_id', sa.UUID, nullable=False, index=True),
        sa.Column('nombre', sa.String(255), nullable=False),
        sa.Column('nombre_normalizado', sa.String(255), index=True),
        sa.Column('tipo_relacion', sa.String(50)),
        sa.Column('telefono', sa.String(20)),
        sa.Column('email', sa.String(255)),
        sa.Column('notas', sa.Text),
        sa.Column('metadata', sa.JSON, default={}),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, onupdate=sa.func.now()),
    )
    
    # Tabla de transacciones (principal)
    op.create_table(
        'transactions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('tenant_id', sa.UUID, nullable=False),
        
        # Core
        sa.Column('fecha', sa.Date, nullable=False),
        sa.Column('descripcion', sa.String(500), nullable=False),
        sa.Column('descripcion_normalizada', sa.String(500)),
        
        # Montos
        sa.Column('monto_original', sa.Numeric(15, 2), nullable=False),
        sa.Column('moneda_original', sa.String(3), default='CRC'),
        sa.Column('monto_crc', sa.Numeric(15, 2), nullable=False),
        sa.Column('tipo_cambio', sa.Numeric(10, 4)),
        
        # Clasificación
        sa.Column('tipo', sa.String(20), nullable=False),
        sa.Column('categoria_id', sa.Integer, sa.ForeignKey('categorias.id')),
        sa.Column('subcategoria_id', sa.Integer, sa.ForeignKey('subcategorias.id')),
        
        # AI/ML
        sa.Column('categoria_sugerida', sa.String(100)),
        sa.Column('confianza_categoria', sa.Numeric(5, 2)),
        sa.Column('necesita_revision', sa.Boolean, default=False),
        sa.Column('embedding', Vector(384)),
        
        # Metadata
        sa.Column('comercio', sa.String(255)),
        sa.Column('comercio_normalizado', sa.String(255)),
        sa.Column('referencia', sa.String(100)),
        
        # Origen
        sa.Column('source', sa.String(50)),
        sa.Column('source_file', sa.String(255)),
        sa.Column('email_id', sa.String(255), unique=True),
        
        # Usuario
        sa.Column('notas', sa.Text),
        sa.Column('tags', sa.JSON, default=[]),
        sa.Column('persona_asociada_id', sa.Integer, sa.ForeignKey('personas.id')),
        
        # Anomalías
        sa.Column('es_anomalia', sa.Boolean, default=False),
        sa.Column('anomalia_score', sa.Numeric(5, 4)),
        sa.Column('anomalia_razon', sa.String(255)),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, onupdate=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime),
        sa.Column('is_deleted', sa.Boolean, default=False),
    )
    
    # Índices
    op.create_index('idx_txn_tenant_fecha', 'transactions', ['tenant_id', 'fecha'])
    op.create_index('idx_txn_tenant_categoria', 'transactions', ['tenant_id', 'categoria_id'])
    op.create_index('idx_txn_descripcion_trgm', 'transactions', ['descripcion'], 
                    postgresql_using='gin', postgresql_ops={'descripcion': 'gin_trgm_ops'})

def downgrade():
    op.drop_table('transactions')
    op.drop_table('personas')
    op.drop_table('subcategorias')
    op.drop_table('categorias')
```

### 1.4 Tests - Alcanzar 80% en lógica financiera

```python
# tests/conftest.py
"""Fixtures compartidas para tests."""
import pytest
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.base import Base

# Test database (SQLite in-memory para velocidad)
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def db_engine():
    """Engine de test."""
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="function")
def db_session(db_engine):
    """Session de test con rollback automático."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()

@pytest.fixture
def tenant_id():
    """UUID de tenant para tests."""
    return uuid4()

@pytest.fixture
def sample_transactions():
    """Transacciones de prueba realistas de Costa Rica."""
    return [
        {
            "fecha": date(2024, 11, 15),
            "descripcion": "UBER *TRIP HELP.UBER.COM",
            "monto_original": Decimal("-8500.00"),
            "moneda_original": "CRC",
            "tipo": "DEBITO",
            "source": "BAC_EMAIL"
        },
        {
            "fecha": date(2024, 11, 14),
            "descripcion": "AUTOMERCADO ESCAZU",
            "monto_original": Decimal("-45230.00"),
            "moneda_original": "CRC",
            "tipo": "DEBITO",
            "source": "BAC_PDF"
        },
        {
            "fecha": date(2024, 11, 13),
            "descripcion": "TRANSFERENCIA SINPE MAMA",
            "monto_original": Decimal("-25000.00"),
            "moneda_original": "CRC",
            "tipo": "DEBITO",
            "source": "SINPE_SMS"
        },
        {
            "fecha": date(2024, 11, 1),
            "descripcion": "DEPOSITO NOMINA BOSCH",
            "monto_original": Decimal("850000.00"),
            "moneda_original": "CRC",
            "tipo": "CREDITO",
            "source": "BAC_PDF"
        },
        {
            "fecha": date(2024, 11, 10),
            "descripcion": "NETFLIX.COM",
            "monto_original": Decimal("-15.99"),
            "moneda_original": "USD",
            "tipo": "DEBITO",
            "source": "BAC_EMAIL"
        },
    ]

@pytest.fixture
def mock_claude_response(mocker):
    """Mock para Claude API."""
    mock = mocker.patch('anthropic.Anthropic')
    mock.return_value.messages.create.return_value.content = [
        mocker.Mock(text='{"categoria": "Transporte", "confianza": 0.92}')
    ]
    return mock
```

```python
# tests/test_categorization_service.py
"""Tests para el servicio de categorización."""
import pytest
from decimal import Decimal

from src.services.categorization_service import CategorizationService

class TestCategorizationService:
    """Tests del servicio de categorización 3-tier."""
    
    def test_keyword_match_uber(self, db_session, tenant_id):
        """Uber debe categorizarse como Transporte por keyword."""
        service = CategorizationService(db_session)
        
        result = service.categorize(
            descripcion="UBER *TRIP HELP.UBER.COM",
            monto=Decimal("-8500"),
            tenant_id=tenant_id
        )
        
        assert result.categoria == "Transporte"
        assert result.metodo == "keyword"
        assert result.confianza >= 0.9
    
    def test_keyword_match_supermercado(self, db_session, tenant_id):
        """Supermercados deben categorizarse como Alimentación."""
        service = CategorizationService(db_session)
        
        for descripcion in ["AUTOMERCADO", "WALMART", "MASXMENOS", "PALI"]:
            result = service.categorize(
                descripcion=descripcion,
                monto=Decimal("-25000"),
                tenant_id=tenant_id
            )
            assert result.categoria == "Alimentación", f"Falló para {descripcion}"
    
    def test_sinpe_transfer_detection(self, db_session, tenant_id):
        """Transferencias SINPE deben detectarse correctamente."""
        service = CategorizationService(db_session)
        
        result = service.categorize(
            descripcion="TRANSFERENCIA SINPE MARIA PEREZ",
            monto=Decimal("-50000"),
            tenant_id=tenant_id
        )
        
        assert result.categoria == "Transferencias"
        assert result.es_transferencia == True
    
    def test_historical_learning(self, db_session, tenant_id):
        """Si ya categorizaste algo, debe usar esa categoría."""
        service = CategorizationService(db_session)
        
        # Simular categorización previa
        service.record_categorization(
            descripcion_normalizada="RESTAURANTE NUESTRA TIERRA",
            categoria="Restaurantes",
            tenant_id=tenant_id
        )
        
        # Nueva transacción similar
        result = service.categorize(
            descripcion="RESTAURANTE NUESTRA TIERRA SAN JOSE",
            monto=Decimal("-18500"),
            tenant_id=tenant_id
        )
        
        assert result.categoria == "Restaurantes"
        assert result.metodo == "historical"
    
    def test_unknown_goes_to_ai(self, db_session, tenant_id, mock_claude_response):
        """Comercios desconocidos deben ir a Claude."""
        service = CategorizationService(db_session)
        
        result = service.categorize(
            descripcion="TIENDA RANDOM XYZ 12345",
            monto=Decimal("-15000"),
            tenant_id=tenant_id
        )
        
        # Debe haber llamado a Claude
        assert mock_claude_response.return_value.messages.create.called
        assert result.metodo == "ai"
    
    def test_income_detection(self, db_session, tenant_id):
        """Ingresos deben detectarse por monto positivo."""
        service = CategorizationService(db_session)
        
        result = service.categorize(
            descripcion="DEPOSITO NOMINA EMPRESA XYZ",
            monto=Decimal("850000"),
            tenant_id=tenant_id
        )
        
        assert result.es_ingreso == True
        assert result.categoria in ["Salario", "Ingresos"]


class TestAnomalyDetection:
    """Tests para detección de anomalías."""
    
    def test_high_amount_anomaly(self, db_session, tenant_id, sample_transactions):
        """Montos muy altos deben marcarse como anomalía."""
        from src.services.anomaly_service import AnomalyService
        
        service = AnomalyService(db_session)
        
        # Entrenar con transacciones normales
        service.train(sample_transactions, tenant_id)
        
        # Transacción anormalmente alta
        result = service.detect({
            "descripcion": "COMPRA TIENDA X",
            "monto": Decimal("-500000"),  # 5x el promedio
            "fecha": "2024-11-20"
        })
        
        assert result.es_anomalia == True
        assert result.score < 0  # Isolation Forest: negativo = anomalía


class TestBudgetCalculations:
    """Tests para cálculos de presupuesto."""
    
    def test_50_30_20_calculation(self, db_session, tenant_id):
        """El sistema 50/30/20 debe calcularse correctamente."""
        from src.services.budget_service import BudgetService
        
        service = BudgetService(db_session)
        
        ingreso_mensual = Decimal("1000000")  # ₡1M
        
        budget = service.calculate_50_30_20(ingreso_mensual)
        
        assert budget["necesidades"] == Decimal("500000")
        assert budget["gustos"] == Decimal("300000")
        assert budget["ahorros"] == Decimal("200000")
    
    def test_budget_status_calculation(self, db_session, tenant_id, sample_transactions):
        """El estado del presupuesto debe calcularse vs gastos reales."""
        from src.services.budget_service import BudgetService
        
        service = BudgetService(db_session)
        
        # Configurar presupuesto
        service.set_budget(
            tenant_id=tenant_id,
            categoria="Alimentación",
            monto=Decimal("150000"),
            mes="2024-11"
        )
        
        # Agregar gastos
        gastos_alimentacion = [t for t in sample_transactions 
                              if "AUTOMERCADO" in t["descripcion"]]
        
        status = service.get_status(tenant_id, "2024-11")
        
        assert "Alimentación" in status
        assert status["Alimentación"]["presupuestado"] == Decimal("150000")
        assert status["Alimentación"]["porcentaje_usado"] >= 0
```

### 1.5 Configuración de CI/CD

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_DB: test_finanzas
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install poetry
          poetry install
      
      - name: Run tests with coverage
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/test_finanzas
        run: |
          poetry run pytest --cov=src --cov-report=xml --cov-fail-under=80
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install ruff
      - run: ruff check src/
      - run: ruff format --check src/
```

### Entregables Fase 1:
- [ ] PostgreSQL + pgvector funcionando en Docker
- [ ] Modelos SQLAlchemy con tenant_id
- [ ] Migraciones Alembic aplicadas
- [ ] Tests al 80%+ en lógica de negocio
- [ ] CI/CD configurado en GitHub Actions

**Tiempo estimado**: 2 semanas

---

## FASE 2: API REST CON FASTAPI (Semanas 4-5)
### Prioridad: ALTA - Base para MCP y cualquier frontend

### 2.1 Estructura del proyecto

```
finanzas-tracker/
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app
│   │   ├── deps.py              # Dependencies (DB, auth)
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py        # Router principal
│   │       └── endpoints/
│   │           ├── transactions.py
│   │           ├── categories.py
│   │           ├── budgets.py
│   │           ├── analytics.py
│   │           ├── personas.py
│   │           └── ai.py        # Chat RAG
│   ├── core/
│   │   ├── config.py
│   │   └── security.py
│   ├── models/                  # SQLAlchemy models
│   ├── schemas/                 # Pydantic schemas
│   │   ├── transaction.py
│   │   ├── budget.py
│   │   └── common.py
│   ├── services/                # Business logic
│   │   ├── transaction_service.py
│   │   ├── categorization_service.py
│   │   ├── budget_service.py
│   │   ├── anomaly_service.py
│   │   ├── embedding_service.py
│   │   └── rag_service.py
│   └── parsers/                 # Email/PDF parsers
├── mcp_server/                  # MCP Server (Fase 3)
├── tests/
├── alembic/
├── data/
└── docker-compose.yml
```

### 2.2 FastAPI Main App

```python
# src/api/main.py
"""FastAPI application for Finanzas Tracker."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1.router import api_router
from src.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    print("🚀 Finanzas Tracker API iniciando...")
    yield
    # Shutdown
    print("👋 Finanzas Tracker API cerrando...")

app = FastAPI(
    title="Finanzas Tracker API",
    description="""
    API para gestión de finanzas personales con AI.
    
    ## Features
    - Categorización automática con Claude AI
    - Detección de anomalías con ML
    - Búsqueda semántica con embeddings
    - Chat RAG para consultas en lenguaje natural
    
    ## Bancos soportados
    - BAC Credomatic (PDF, Email)
    - SINPE Móvil (SMS)
    """,
    version="2.0.0",
    lifespan=lifespan
)

# CORS para frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas
app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "database": "connected"  # TODO: check real connection
    }
```

### 2.3 Schemas Pydantic

```python
# src/schemas/transaction.py
"""Schemas para transacciones."""
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class MonedaEnum(str, Enum):
    CRC = "CRC"
    USD = "USD"

class TipoTransaccionEnum(str, Enum):
    DEBITO = "DEBITO"
    CREDITO = "CREDITO"

class TransactionBase(BaseModel):
    """Base schema para transacciones."""
    fecha: date
    descripcion: str = Field(..., min_length=1, max_length=500)
    monto_original: Decimal
    moneda_original: MonedaEnum = MonedaEnum.CRC
    tipo: TipoTransaccionEnum
    notas: Optional[str] = None

class TransactionCreate(TransactionBase):
    """Schema para crear transacción."""
    categoria_id: Optional[int] = None
    persona_asociada_id: Optional[int] = None
    tags: list[str] = []

class TransactionUpdate(BaseModel):
    """Schema para actualizar transacción."""
    categoria_id: Optional[int] = None
    subcategoria_id: Optional[int] = None
    notas: Optional[str] = None
    tags: Optional[list[str]] = None
    persona_asociada_id: Optional[int] = None

class TransactionResponse(TransactionBase):
    """Schema de respuesta."""
    id: int
    monto_crc: Decimal
    tipo_cambio: Optional[Decimal] = None
    
    # Categorización
    categoria_id: Optional[int] = None
    categoria_nombre: Optional[str] = None
    categoria_sugerida: Optional[str] = None
    confianza_categoria: Optional[Decimal] = None
    necesita_revision: bool = False
    
    # Comercio
    comercio: Optional[str] = None
    comercio_normalizado: Optional[str] = None
    
    # Anomalía
    es_anomalia: bool = False
    anomalia_score: Optional[Decimal] = None
    
    # Metadata
    source: Optional[str] = None
    persona_asociada_id: Optional[int] = None
    tags: list[str] = []
    
    created_at: datetime
    
    class Config:
        from_attributes = True

class TransactionList(BaseModel):
    """Schema para lista paginada."""
    items: list[TransactionResponse]
    total: int
    page: int
    page_size: int
    pages: int

# Schema para entrada en lenguaje natural
class NaturalLanguageInput(BaseModel):
    """Input para crear transacción desde texto natural."""
    texto: str = Field(
        ...,
        min_length=5,
        max_length=500,
        examples=[
            "Hoy le transferí 10 mil a mi mamá para comida de los perros",
            "Ayer gasté 15 rojos en Uber Eats",
            "El viernes pagué 50 mil del gimnasio"
        ]
    )

class NaturalLanguageResult(BaseModel):
    """Resultado del parsing de lenguaje natural."""
    transaction: TransactionResponse
    parsed_data: dict  # Datos extraídos por Claude
    confianza: Decimal
```

### 2.4 Endpoints principales

```python
# src/api/v1/endpoints/transactions.py
"""Endpoints de transacciones."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from datetime import date
from typing import Optional
from uuid import UUID

from src.api.deps import get_db, get_current_tenant
from src.schemas.transaction import (
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
    TransactionList,
    NaturalLanguageInput,
    NaturalLanguageResult
)
from src.services.transaction_service import TransactionService
from src.services.nl_transaction_service import NLTransactionService

router = APIRouter()

@router.get("/", response_model=TransactionList)
def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    categoria_id: Optional[int] = None,
    tipo: Optional[str] = None,
    search: Optional[str] = None,
    solo_anomalias: bool = False,
    solo_sin_categoria: bool = False,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant)
):
    """
    Lista transacciones con filtros y paginación.
    
    - **search**: Búsqueda semántica en descripción
    - **solo_anomalias**: Solo transacciones marcadas como anomalías
    - **solo_sin_categoria**: Solo transacciones sin categorizar
    """
    service = TransactionService(db)
    
    result = service.list_transactions(
        tenant_id=tenant_id,
        page=page,
        page_size=page_size,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        categoria_id=categoria_id,
        tipo=tipo,
        search=search,
        solo_anomalias=solo_anomalias,
        solo_sin_categoria=solo_sin_categoria
    )
    
    return result

@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    data: TransactionCreate,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant)
):
    """Crea una nueva transacción manualmente."""
    service = TransactionService(db)
    return service.create(tenant_id, data)

@router.post("/natural-language", response_model=NaturalLanguageResult)
async def create_from_natural_language(
    data: NaturalLanguageInput,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant)
):
    """
    Crea transacción desde lenguaje natural.
    
    Ejemplos:
    - "Hoy le transferí 10 mil a mi mamá para comida de los perros"
    - "Ayer gasté 15 rojos en Uber Eats"
    - "El viernes pagué 50 mil del gimnasio"
    - "Recibí 500 dólares de mi salario"
    
    Entiende jerga tica:
    - "mil" = 1000 colones
    - "rojos" = colones
    - "verdes" = dólares
    """
    service = NLTransactionService(db)
    return await service.parse_and_create(tenant_id, data.texto)

@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant)
):
    """Obtiene una transacción por ID."""
    service = TransactionService(db)
    txn = service.get(tenant_id, transaction_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transacción no encontrada")
    return txn

@router.patch("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    data: TransactionUpdate,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant)
):
    """Actualiza una transacción."""
    service = TransactionService(db)
    txn = service.update(tenant_id, transaction_id, data)
    if not txn:
        raise HTTPException(status_code=404, detail="Transacción no encontrada")
    return txn

@router.post("/{transaction_id}/categorize", response_model=TransactionResponse)
def recategorize_transaction(
    transaction_id: int,
    categoria_id: int,
    crear_regla: bool = Query(False, description="Crear regla para futuras transacciones similares"),
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant)
):
    """
    Recategoriza una transacción.
    
    Si `crear_regla=True`, el sistema aprenderá de esta corrección
    y categorizará automáticamente transacciones similares en el futuro.
    """
    service = TransactionService(db)
    return service.recategorize(tenant_id, transaction_id, categoria_id, crear_regla)

@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant)
):
    """Elimina una transacción (soft delete)."""
    service = TransactionService(db)
    if not service.delete(tenant_id, transaction_id):
        raise HTTPException(status_code=404, detail="Transacción no encontrada")
```

```python
# src/api/v1/endpoints/analytics.py
"""Endpoints de analytics."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Literal
from uuid import UUID

from src.api.deps import get_db, get_current_tenant
from src.services.analytics_service import AnalyticsService
from src.services.anomaly_service import AnomalyService
from src.services.subscription_service import SubscriptionService

router = APIRouter()

@router.get("/spending-by-category")
def spending_by_category(
    periodo: Literal["semana", "mes", "año"] = "mes",
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant)
):
    """
    Desglose de gastos por categoría.
    
    Retorna total gastado en cada categoría para el periodo seleccionado.
    """
    service = AnalyticsService(db)
    return service.spending_by_category(tenant_id, periodo)

@router.get("/budget-status")
def budget_status(
    mes: str = Query(None, regex=r"^\d{4}-\d{2}$", description="Formato: YYYY-MM"),
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant)
):
    """
    Estado del presupuesto 50/30/20 para el mes indicado.
    
    Retorna:
    - Presupuesto por categoría
    - Gastado por categoría
    - % utilizado
    - Días restantes del mes
    """
    service = AnalyticsService(db)
    return service.budget_status(tenant_id, mes)

@router.get("/monthly-trends")
def monthly_trends(
    meses: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant)
):
    """
    Tendencias de ingresos/gastos por mes.
    
    Retorna datos para gráfica de líneas/barras.
    """
    service = AnalyticsService(db)
    return service.monthly_trends(tenant_id, meses)

@router.get("/anomalies")
def detect_anomalies(
    sensibilidad: float = Query(0.1, ge=0.01, le=0.5),
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant)
):
    """
    Detecta transacciones anómalas usando Isolation Forest.
    
    - **sensibilidad**: Menor = más estricto (menos anomalías)
    """
    service = AnomalyService(db)
    return service.get_anomalies(tenant_id, sensibilidad)

@router.get("/subscriptions")
def detected_subscriptions(
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant)
):
    """
    Lista suscripciones/pagos recurrentes detectados automáticamente.
    
    Incluye:
    - Frecuencia detectada
    - Monto promedio
    - Costo anual estimado
    - Próximo cobro esperado
    """
    service = SubscriptionService(db)
    return service.detect_subscriptions(tenant_id)

@router.get("/end-of-month-prediction")
def predict_end_of_month(
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant)
):
    """
    Predice si llegarás a fin de mes basado en:
    - Gastos actuales
    - Patrón histórico
    - Ingresos esperados
    
    Retorna:
    - Proyección de gastos
    - Balance esperado
    - Estado (bien/cuidado/peligro)
    - Recomendaciones
    """
    service = AnalyticsService(db)
    return service.predict_end_of_month(tenant_id)

@router.get("/personas-top")
def top_personas(
    limite: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant)
):
    """
    Personas con las que más transaccionás.
    
    Útil para: "¿Cuánto le he dado a mi mamá este año?"
    """
    service = AnalyticsService(db)
    return service.top_personas(tenant_id, limite)
```

```python
# src/api/v1/endpoints/ai.py
"""Endpoints de AI/RAG."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from uuid import UUID

from src.api.deps import get_db, get_current_tenant
from src.services.rag_service import RAGService

router = APIRouter()

class ChatRequest(BaseModel):
    mensaje: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        examples=[
            "¿Por qué gasté tanto en restaurantes este mes?",
            "¿Cuánto gasto en Uber mensualmente?",
            "¿Llegaré a fin de mes?",
            "¿Tengo suscripciones que no uso?"
        ]
    )

class ChatResponse(BaseModel):
    respuesta: str
    transacciones_referenciadas: int
    confianza: float

@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(
    request: ChatRequest,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant)
):
    """
    Chat con asistente financiero usando RAG.
    
    El sistema busca transacciones relevantes en tu historial
    y genera respuestas fundamentadas en tus datos reales.
    
    **Ejemplos de preguntas:**
    - "¿Por qué gasté tanto en marzo?"
    - "¿Cuánto gasto en comida fuera mensualmente?"
    - "¿Cuáles son mis gastos hormiga?"
    - "¿Cómo va mi presupuesto de entretenimiento?"
    - "¿Cuánto le he transferido a mi mamá este año?"
    """
    service = RAGService(db)
    return await service.chat(tenant_id, request.mensaje)
```

### 2.5 Servicio RAG con pgvector

```python
# src/services/rag_service.py
"""Servicio RAG para consultas en lenguaje natural."""
import anthropic
from sqlalchemy.orm import Session
from sqlalchemy import text
from uuid import UUID
from decimal import Decimal

from src.services.embedding_service import EmbeddingService
from src.services.analytics_service import AnalyticsService

class RAGService:
    """Pipeline RAG para consultas financieras."""
    
    def __init__(self, db: Session):
        self.db = db
        self.embeddings = EmbeddingService()
        self.analytics = AnalyticsService(db)
        self.client = anthropic.Anthropic()
    
    async def chat(self, tenant_id: UUID, pregunta: str) -> dict:
        """
        Procesa una pregunta usando RAG.
        
        1. Genera embedding de la pregunta
        2. Busca transacciones relevantes con pgvector
        3. Obtiene estadísticas relevantes
        4. Genera respuesta con Claude
        """
        # 1. Generar embedding de la pregunta
        query_embedding = self.embeddings.embed_text(pregunta)
        
        # 2. Búsqueda vectorial en PostgreSQL
        transactions = self._vector_search(tenant_id, query_embedding, limit=20)
        
        # 3. Obtener estadísticas relevantes
        stats = self._get_relevant_stats(tenant_id, pregunta)
        
        # 4. Construir contexto
        context = self._build_context(transactions, stats)
        
        # 5. Generar respuesta
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system="""Sos un asistente financiero personal para Costa Rica.

REGLAS IMPORTANTES:
- Respondé ÚNICAMENTE basándote en los datos proporcionados
- Usá colones (₡) para CRC y dólares ($) para USD
- Si no tenés datos suficientes, decilo claramente
- Sé específico: mencioná fechas, montos, comercios
- Dá recomendaciones prácticas cuando sea apropiado
- Respondé en español de Costa Rica (vos, mae si es apropiado)
- Sé conciso pero completo""",
            messages=[{
                "role": "user",
                "content": f"""Basándote en estos datos financieros del usuario:

{context}

Pregunta: {pregunta}

Respondé de forma útil y específica."""
            }]
        )
        
        return {
            "respuesta": response.content[0].text,
            "transacciones_referenciadas": len(transactions),
            "confianza": 0.9 if len(transactions) > 5 else 0.7
        }
    
    def _vector_search(self, tenant_id: UUID, embedding: list[float], limit: int = 20) -> list:
        """Búsqueda vectorial usando pgvector."""
        # Query con pgvector
        query = text("""
            SELECT 
                id, fecha, descripcion, monto_original, moneda_original,
                tipo, comercio, notas, categoria_id,
                1 - (embedding <=> :embedding) as similarity
            FROM transactions
            WHERE tenant_id = :tenant_id
                AND is_deleted = false
                AND embedding IS NOT NULL
            ORDER BY embedding <=> :embedding
            LIMIT :limit
        """)
        
        result = self.db.execute(query, {
            "tenant_id": str(tenant_id),
            "embedding": str(embedding),  # pgvector acepta string
            "limit": limit
        })
        
        return [dict(row._mapping) for row in result]
    
    def _get_relevant_stats(self, tenant_id: UUID, pregunta: str) -> dict:
        """Obtiene estadísticas según la pregunta."""
        stats = {}
        pregunta_lower = pregunta.lower()
        
        # Siempre incluir estado del presupuesto
        stats["budget"] = self.analytics.budget_status(tenant_id)
        
        # Detectar qué más necesitamos
        if any(w in pregunta_lower for w in ["categoría", "categoria", "gasto", "gastado"]):
            stats["by_category"] = self.analytics.spending_by_category(tenant_id, "mes")
        
        if any(w in pregunta_lower for w in ["mes", "mensual", "tendencia"]):
            stats["trends"] = self.analytics.monthly_trends(tenant_id, 6)
        
        if any(w in pregunta_lower for w in ["suscripción", "suscripciones", "netflix", "spotify"]):
            from src.services.subscription_service import SubscriptionService
            sub_service = SubscriptionService(self.db)
            stats["subscriptions"] = sub_service.detect_subscriptions(tenant_id)
        
        if any(w in pregunta_lower for w in ["mamá", "mama", "papá", "papa", "familia", "transferí"]):
            stats["top_personas"] = self.analytics.top_personas(tenant_id, 5)
        
        return stats
    
    def _build_context(self, transactions: list, stats: dict) -> str:
        """Construye contexto estructurado para el prompt."""
        parts = []
        
        # Estado del presupuesto
        if "budget" in stats:
            b = stats["budget"]
            parts.append(f"""=== ESTADO DEL PRESUPUESTO ===
Ingreso mensual: ₡{b.get('ingreso_mensual', 0):,.0f}
Total gastado: ₡{b.get('total_gastado', 0):,.0f}
Restante: ₡{b.get('restante', 0):,.0f}
Días restantes: {b.get('dias_restantes', 0)}""")
        
        # Por categoría
        if "by_category" in stats:
            parts.append("\n=== GASTOS POR CATEGORÍA (este mes) ===")
            for cat, monto in sorted(stats["by_category"].items(), key=lambda x: -x[1]):
                parts.append(f"- {cat}: ₡{monto:,.0f}")
        
        # Top personas
        if "top_personas" in stats and stats["top_personas"]:
            parts.append("\n=== PERSONAS FRECUENTES ===")
            for p in stats["top_personas"][:5]:
                parts.append(f"- {p['nombre']}: ₡{p['total']:,.0f} ({p['cantidad']} transacciones)")
        
        # Transacciones relevantes
        if transactions:
            parts.append(f"\n=== TRANSACCIONES RELEVANTES ({len(transactions)}) ===")
            for t in transactions[:15]:
                monto = t['monto_original']
                simbolo = "₡" if t['moneda_original'] == "CRC" else "$"
                tipo = "Gasto" if float(monto) < 0 else "Ingreso"
                parts.append(f"- {t['fecha']}: {t['descripcion']} → {simbolo}{abs(float(monto)):,.0f} ({tipo})")
        
        return "\n".join(parts)
```

```python
# src/services/embedding_service.py
"""Servicio de embeddings usando sentence-transformers."""
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from sqlalchemy import text
import numpy as np

class EmbeddingService:
    """Genera embeddings para búsqueda semántica."""
    
    def __init__(self):
        # Modelo multilingüe que soporta español
        # 384 dimensiones, rápido y preciso
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    
    def embed_text(self, text: str) -> list[float]:
        """Genera embedding de un texto."""
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def embed_transaction(self, transaction) -> list[float]:
        """
        Genera embedding enriquecido de una transacción.
        Incluye contexto para mejor búsqueda semántica.
        """
        # Construir texto enriquecido
        parts = [
            transaction.descripcion,
            f"Monto: {abs(transaction.monto_original):,.0f}",
            f"Tipo: {'gasto' if transaction.monto_original < 0 else 'ingreso'}",
        ]
        
        if transaction.comercio:
            parts.append(f"Comercio: {transaction.comercio}")
        
        if transaction.categoria:
            parts.append(f"Categoría: {transaction.categoria.nombre}")
        
        if transaction.notas:
            parts.append(f"Notas: {transaction.notas}")
        
        text = " | ".join(parts)
        return self.embed_text(text)
    
    def update_transaction_embedding(self, db: Session, transaction_id: int):
        """Actualiza el embedding de una transacción en la DB."""
        from src.models.transaction import Transaction
        
        txn = db.query(Transaction).get(transaction_id)
        if txn:
            embedding = self.embed_transaction(txn)
            
            # Actualizar directamente con SQL para pgvector
            db.execute(
                text("UPDATE transactions SET embedding = :embedding WHERE id = :id"),
                {"embedding": str(embedding), "id": transaction_id}
            )
            db.commit()
```

### Entregables Fase 2:
- [ ] FastAPI funcionando con 20+ endpoints
- [ ] Swagger docs en `/docs`
- [ ] Endpoint de chat RAG funcionando
- [ ] Búsqueda vectorial con pgvector
- [ ] Entrada en lenguaje natural funcionando

**Tiempo estimado**: 2 semanas

---

## FASE 3: MCP SERVER DIFERENCIADO (Semanas 6-7)
### Prioridad: ALTA - Tu diferenciador #1

### ¿Por qué diferenciado?

Actual Budget ya tiene `actual-mcp` con CRUD básico. Tu MCP necesita hacer cosas que ellos NO hacen:

1. **Coaching inteligente** - No solo datos, sino recomendaciones
2. **Predicción** - ¿Llegaré a fin de mes?
3. **Contexto Costa Rica** - SINPE, colones, comercios locales
4. **Entrada en lenguaje natural** - "Anotar: compré..."

### 3.1 Implementación del MCP Server

```python
# mcp_server/server.py
"""
MCP Server para Finanzas Personales Costa Rica.
Diferenciado: No solo CRUD, sino coaching + predicción + NL.
"""
from mcp.server.fastmcp import FastMCP
from datetime import date, datetime
from typing import Optional
import httpx

# Crear servidor MCP
mcp = FastMCP(
    name="Finanzas Costa Rica",
    instructions="""Servidor MCP para finanzas personales en Costa Rica.

CAPACIDADES ÚNICAS (vs otros MCP de finanzas):
1. Coaching inteligente con recomendaciones personalizadas
2. Predicción de fin de mes basada en patrones
3. Soporte nativo para SINPE Móvil y colones
4. Entrada en lenguaje natural tico

MONEDAS: CRC (colones, ₡), USD (dólares, $)
JERGA: "mil" = 1000, "rojos" = colones, "verdes" = dólares
"""
)

API_BASE = "http://localhost:8000/api/v1"


# ============================================================
# TOOLS BÁSICOS (similares a actual-mcp pero mejorados)
# ============================================================

@mcp.tool()
async def get_transactions(
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    categoria: Optional[str] = None,
    limite: int = 20
) -> list[dict]:
    """
    Obtiene transacciones recientes con filtros.
    
    Args:
        fecha_desde: YYYY-MM-DD
        fecha_hasta: YYYY-MM-DD  
        categoria: Nombre de categoría
        limite: Máximo de resultados (default 20)
    """
    params = {"page_size": limite}
    if fecha_desde:
        params["fecha_desde"] = fecha_desde
    if fecha_hasta:
        params["fecha_hasta"] = fecha_hasta
    if categoria:
        params["categoria"] = categoria
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/transactions", params=params)
        data = response.json()
        return data.get("items", [])


@mcp.tool()
async def get_budget_status(mes: Optional[str] = None) -> dict:
    """
    Estado del presupuesto 50/30/20.
    
    Args:
        mes: YYYY-MM (default: mes actual)
        
    Returns:
        Presupuesto por categoría, gastado, restante, % usado
    """
    params = {}
    if mes:
        params["mes"] = mes
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/analytics/budget-status", params=params)
        return response.json()


@mcp.tool()
async def get_spending_by_category(periodo: str = "mes") -> dict:
    """
    Desglose de gastos por categoría.
    
    Args:
        periodo: "semana", "mes", o "año"
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/analytics/spending-by-category",
            params={"periodo": periodo}
        )
        return response.json()


# ============================================================
# TOOLS DIFERENCIADOS (lo que otros MCP NO tienen)
# ============================================================

@mcp.tool()
async def coaching_financiero(pregunta: str) -> str:
    """
    🎯 DIFERENCIADOR: Coaching con AI basado en TUS datos.
    
    No solo responde preguntas, sino que da recomendaciones
    personalizadas basadas en tu historial real.
    
    Args:
        pregunta: Cualquier pregunta sobre tus finanzas
        
    Ejemplos:
        - "¿Por qué gasté tanto en restaurantes?"
        - "¿Cómo puedo ahorrar más?"
        - "¿Cuáles son mis gastos hormiga?"
        - "¿Estoy gastando bien en entretenimiento?"
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{API_BASE}/ai/chat",
            json={"mensaje": pregunta}
        )
        data = response.json()
        return data.get("respuesta", "No pude analizar tus datos.")


@mcp.tool()
async def prediccion_fin_de_mes() -> dict:
    """
    🎯 DIFERENCIADOR: Predice si llegarás a fin de mes.
    
    Analiza:
    - Gastos actuales vs históricos
    - Velocidad de gasto
    - Ingresos esperados
    
    Returns:
        - proyeccion_gastos: Cuánto gastarás al final del mes
        - balance_esperado: Ingresos - gastos proyectados
        - estado: "bien" | "cuidado" | "peligro"
        - recomendaciones: Lista de acciones sugeridas
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/analytics/end-of-month-prediction")
        return response.json()


@mcp.tool()
async def detectar_suscripciones() -> list[dict]:
    """
    🎯 DIFERENCIADOR: Detecta suscripciones automáticamente.
    
    Analiza patrones de cobros recurrentes y detecta:
    - Netflix, Spotify, etc.
    - Gimnasios
    - Servicios mensuales
    
    Returns:
        Lista de suscripciones con:
        - nombre
        - monto_promedio
        - frecuencia
        - costo_anual
        - proximo_cobro
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/analytics/subscriptions")
        return response.json()


@mcp.tool()
async def registrar_transaccion(descripcion: str) -> dict:
    """
    🎯 DIFERENCIADOR: Registra transacción en lenguaje natural.
    
    Entiende jerga costarricense:
    - "mil" = 1000 colones
    - "rojos" = colones
    - "verdes" = dólares
    - "hoy", "ayer", "el viernes" = fechas
    
    Args:
        descripcion: Texto natural describiendo la transacción
        
    Ejemplos:
        - "Hoy le transferí 10 mil a mi mamá para comida de los perros"
        - "Ayer gasté 15 rojos en Uber Eats"
        - "El viernes pagué 50 mil del gimnasio"
        - "Recibí 500 verdes de mi salario"
    
    Returns:
        Transacción creada con categoría asignada automáticamente
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{API_BASE}/transactions/natural-language",
            json={"texto": descripcion}
        )
        data = response.json()
        
        if "transaction" in data:
            txn = data["transaction"]
            return {
                "mensaje": f"✓ Registrado: {txn['descripcion']}",
                "monto": txn["monto_original"],
                "categoria": txn.get("categoria_nombre", "Sin categoría"),
                "fecha": txn["fecha"]
            }
        return {"error": "No pude procesar la transacción"}


@mcp.tool()
async def analizar_persona(nombre: str) -> dict:
    """
    🎯 DIFERENCIADOR: Análisis de transacciones con una persona.
    
    Responde preguntas como:
    - "¿Cuánto le he dado a mi mamá este año?"
    - "¿Cuánto me debe Juan?"
    
    Args:
        nombre: Nombre de la persona
        
    Returns:
        - total_enviado: Monto total transferido a esta persona
        - total_recibido: Monto total recibido de esta persona  
        - balance: Diferencia (positivo = te deben)
        - transacciones: Últimas transacciones con esta persona
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/analytics/personas-top",
            params={"limite": 50}
        )
        personas = response.json()
        
        # Buscar persona por nombre (fuzzy)
        nombre_upper = nombre.upper()
        for p in personas:
            if nombre_upper in p.get("nombre", "").upper():
                return p
        
        return {"mensaje": f"No encontré transacciones con '{nombre}'"}


@mcp.tool()
async def detectar_anomalias(sensibilidad: float = 0.1) -> list[dict]:
    """
    🎯 DIFERENCIADOR: Detecta gastos inusuales con ML.
    
    Usa Isolation Forest para identificar transacciones
    que se desvían del patrón normal.
    
    Args:
        sensibilidad: 0.01-0.5 (menor = más estricto)
        
    Returns:
        Lista de transacciones anómalas con:
        - descripcion
        - monto
        - razon: Por qué es anómala
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/analytics/anomalies",
            params={"sensibilidad": sensibilidad}
        )
        return response.json()


# ============================================================
# RESOURCES (datos consultables)
# ============================================================

@mcp.resource("resumen/mensual/{year}/{month}")
async def resumen_mensual(year: int, month: int) -> str:
    """
    Genera resumen del mes en formato legible.
    """
    mes = f"{year}-{month:02d}"
    
    async with httpx.AsyncClient() as client:
        # Obtener datos
        budget = await client.get(f"{API_BASE}/analytics/budget-status", params={"mes": mes})
        budget_data = budget.json()
        
        spending = await client.get(f"{API_BASE}/analytics/spending-by-category", params={"periodo": "mes"})
        spending_data = spending.json()
    
    # Formatear resumen
    lines = [
        f"# Resumen Financiero - {month}/{year}",
        "",
        "## Estado General",
        f"- Ingresos: ₡{budget_data.get('ingreso_mensual', 0):,.0f}",
        f"- Gastos: ₡{budget_data.get('total_gastado', 0):,.0f}",
        f"- Balance: ₡{budget_data.get('restante', 0):,.0f}",
        "",
        "## Por Categoría",
    ]
    
    for cat, monto in sorted(spending_data.items(), key=lambda x: -x[1]):
        lines.append(f"- {cat}: ₡{monto:,.0f}")
    
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### 3.2 Configuración para Claude Desktop

```json
// macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
// Windows: %APPDATA%\Claude\claude_desktop_config.json
{
  "mcpServers": {
    "finanzas-cr": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/ruta/a/tu/proyecto/finanzas-tracker",
      "env": {
        "API_BASE": "http://localhost:8000/api/v1"
      }
    }
  }
}
```

### 3.3 Demo para portfolio

Crear video de 2-3 minutos mostrando:

```
Usuario: "¿Cómo van mis finanzas este mes?"

Claude: [Usa get_budget_status + spending_by_category]
"Este mes llevas gastado ₡485,000 de tu presupuesto de ₡600,000.
Te quedan ₡115,000 para los próximos 8 días.

Por categoría:
- Alimentación: ₡180,000 (92% del presupuesto) ⚠️
- Transporte: ₡85,000 (67%)
- Entretenimiento: ₡65,000 (45%)

El gasto en alimentación está alto. ¿Querés que analice por qué?"

Usuario: "Sí, ¿por qué gasté tanto en alimentación?"

Claude: [Usa coaching_financiero]
"Analizando tus transacciones de alimentación...

Detecté estos factores:
1. 8 visitas a restaurantes (vs 4 el mes pasado)
2. 3 pedidos de Uber Eats el fin de semana
3. Ticket promedio en supermercados subió 15%

Top gastos:
- Restaurante La Princesa: ₡35,000
- Automercado x3: ₡52,000
- Uber Eats: ₡28,000

Recomendación: Reducir restaurantes a 4/mes ahorraría ~₡40,000."

Usuario: "Anotá: hoy le di 10 mil a mi mamá para comida de los perros"

Claude: [Usa registrar_transaccion]
"✓ Registrado:
- Monto: ₡10,000 (gasto)
- Categoría: Transferencias
- Destinatario: Mamá
- Nota: Comida de perros
- Fecha: Hoy"
```

### Entregables Fase 3:
- [ ] MCP Server con 10+ tools diferenciados
- [ ] Configurado en Claude Desktop
- [ ] Video demo de 2-3 minutos
- [ ] README con instrucciones de instalación

**Tiempo estimado**: 2 semanas

---

## FASE 4: POLISH PARA PORTFOLIO (Semanas 8-9)
### Prioridad: MEDIA - Pero crítico para entrevistas

### 4.1 Documentación profesional

```markdown
# README.md

# Finanzas Tracker Costa Rica 🇨🇷

Sistema de finanzas personales con AI, diseñado específicamente para Costa Rica.

[![Tests](https://github.com/tuuser/finanzas-tracker/actions/workflows/ci.yml/badge.svg)](...)
[![Coverage](https://codecov.io/gh/tuuser/finanzas-tracker/branch/main/graph/badge.svg)](...)

## ✨ Features

- **Categorización automática** con Claude AI (3-tier: keywords → histórico → AI)
- **MCP Server** para integración con Claude Desktop/ChatGPT
- **Búsqueda semántica** con pgvector para consultas en lenguaje natural
- **Detección de anomalías** con Isolation Forest
- **Soporte para SINPE Móvil** - Parseo de notificaciones
- **Multi-moneda** - Colones (₡) y Dólares ($) con conversión automática

## 🚀 Quick Start

```bash
# Clonar
git clone https://github.com/tuuser/finanzas-tracker.git
cd finanzas-tracker

# Levantar con Docker
docker-compose up -d

# La API estará en http://localhost:8000
# Docs en http://localhost:8000/docs
```

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENTS                              │
│  Claude Desktop │ ChatGPT │ Streamlit │ Mobile (futuro)│
└────────────────────────┬────────────────────────────────┘
                         │ MCP Protocol / REST API
┌────────────────────────▼────────────────────────────────┐
│                   FASTAPI BACKEND                        │
│  • REST API (20+ endpoints)                             │
│  • MCP Server (10+ tools)                               │
│  • RAG Pipeline (pgvector + Claude)                     │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                 POSTGRESQL + PGVECTOR                    │
│  • Transacciones │ Categorías │ Personas                │
│  • Embeddings (384 dims) │ Multi-tenant ready           │
└─────────────────────────────────────────────────────────┘
```

## 📊 Métricas

- **500+** transacciones procesadas de estados de cuenta BAC
- **94%** accuracy en categorización automática
- **<2s** latencia promedio en búsqueda RAG
- **80%+** test coverage en lógica de negocio

## 🎯 Diferenciadores vs Competencia

| Feature | Firefly III | Actual Budget | Este Proyecto |
|---------|-------------|---------------|---------------|
| MCP Server | ❌ | ✅ (básico) | ✅ (coaching + NL) |
| RAG Chat | ❌ | ❌ | ✅ |
| SINPE Móvil | ❌ | ❌ | ✅ |
| Lenguaje Natural | ❌ | ❌ | ✅ |
| Costa Rica focused | ❌ | ❌ | ✅ |

## 🛠️ Stack Técnico

- **Backend**: FastAPI, SQLAlchemy 2.0, Pydantic
- **Database**: PostgreSQL 16 + pgvector
- **AI**: Claude API (Haiku para categorización, Sonnet para RAG)
- **ML**: scikit-learn (Isolation Forest para anomalías)
- **Embeddings**: sentence-transformers (MiniLM multilingual)
- **Testing**: pytest, 80%+ coverage
```

### 4.2 Diagrama de arquitectura

Crear diagrama profesional (draw.io o similar) mostrando:
- Flujo de datos desde PDFs/SMS hasta dashboard
- Componentes del sistema
- Integración MCP

### 4.3 Métricas para CV

En tu CV/LinkedIn:

```
Finanzas Tracker CR - Sistema de finanzas personales con AI

• Diseñé MCP Server con 10+ tools permitiendo integración con Claude Desktop,
  diferenciado por coaching inteligente y entrada en lenguaje natural
  
• Implementé RAG pipeline con pgvector reduciendo latencia de búsqueda a <2s
  y logrando 94% accuracy en respuestas fundamentadas
  
• Construí ETL pipeline procesando estados de cuenta BAC con Claude Vision,
  extrayendo 500+ transacciones con 98% accuracy
  
• Logré 80%+ test coverage en lógica de negocio usando pytest
  
• Arquitectura multi-tenant lista para SaaS con PostgreSQL + pgvector

Stack: Python, FastAPI, PostgreSQL, pgvector, Claude API, MCP Protocol
```

### 4.4 Deploy para demo

Opciones gratuitas/baratas:

1. **Railway** - PostgreSQL + API gratis hasta cierto límite
2. **Render** - Free tier para web services
3. **Streamlit Cloud** - Gratis para dashboard público

```yaml
# railway.toml (ejemplo)
[build]
builder = "nixpacks"

[deploy]
startCommand = "uvicorn src.api.main:app --host 0.0.0.0 --port $PORT"
```

---

## TIMELINE FINAL

```
SEMANA 1:     FASE 0 - Procesar tus PDFs del BAC
              └─ Meta: 500+ transacciones reales

SEMANA 2-3:   FASE 1 - Fundamentos
              └─ PostgreSQL + pgvector + Tests 80%

SEMANA 4-5:   FASE 2 - FastAPI
              └─ 20+ endpoints + RAG funcionando

SEMANA 6-7:   FASE 3 - MCP Server
              └─ 10+ tools diferenciados

SEMANA 8-9:   FASE 4 - Polish
              └─ Docs + Deploy + Video demo

TOTAL: ~9 semanas (2 meses trabajando 10-15 hrs/semana)
```

---

## PRÓXIMO PASO INMEDIATO

**Esta semana:**

1. Localizar todos tus PDFs del BAC
2. Crear estructura de carpetas:
   ```bash
   mkdir -p data/raw/bac_pdf data/raw/sinpe_sms data/processed
   ```
3. Implementar `BACPDFParser` y procesar UN PDF de prueba
4. Levantar PostgreSQL con Docker

**Comando para empezar:**
```bash
# Instalar dependencias
pip install anthropic pdf2image sentence-transformers pgvector sqlalchemy fastapi

# Levantar PostgreSQL
docker-compose up -d db

# Probar parser con un PDF
python -c "
from src.parsers.bac_pdf_parser import BACPDFParser
import asyncio

async def test():
    parser = BACPDFParser()
    result = await parser.parse('data/raw/bac_pdf/tu_estado.pdf')
    print(f'Transacciones: {len(result[\"transactions\"])}')
    
asyncio.run(test())
"
```

¿Empezamos con la Fase 0 esta semana?
