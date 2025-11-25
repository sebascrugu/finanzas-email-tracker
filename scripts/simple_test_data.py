#!/usr/bin/env python3
"""
Script simplificado para crear datos de prueba básicos para alertas.

Sin dependencias pesadas - solo lo esencial.
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Solo importar lo mínimo necesario
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Importar directamente Base sin pasar por __init__.py
import importlib.util
spec = importlib.util.spec_from_file_location("base", str(Path(__file__).parent.parent / "src/finanzas_tracker/models/base.py"))
base_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base_module)
Base = base_module.Base

# Configurar la base de datos
db_path = "data/finanzas.db"
engine = create_engine(f"sqlite:///{db_path}")

# Crear todas las tablas
Base.metadata.create_all(engine)

# Crear sesión
Session = sessionmaker(bind=engine)
session = Session()

print("✅ Base de datos inicializada correctamente!")
print(f"📁 Ruta: {db_path}")

# Verificar que la tabla de alertas existe
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"\n📊 Tablas creadas: {len(tables)}")
for table in sorted(tables):
    print(f"   - {table}")

session.close()
