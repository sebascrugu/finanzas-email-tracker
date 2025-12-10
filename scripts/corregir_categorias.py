#!/usr/bin/env python3
"""Script para corregir categorías erróneas basado en feedback del usuario.

Este script:
1. Corrige las transacciones mal categorizadas
2. Crea subcategorías faltantes si es necesario
3. Registra las correcciones en el sistema de aprendizaje
"""

import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from uuid import uuid4

from sqlalchemy import create_engine, text

from finanzas_tracker.config.settings import settings

# Correcciones basadas en feedback del usuario
CORRECCIONES = [
    {
        "comercio_like": "MOVE",
        "comercio_exacto": "MOVE",
        "subcategoria_correcta": "Entretenimiento",  # Subcategoría
        "categoria_correcta": "Gustos",
        "razon": "Move Concerts - empresa de conciertos, no gimnasio",
    },
    {
        "comercio_like": "SERVI INDOOR",
        "comercio_exacto": "SERVI INDOOR", 
        "subcategoria_correcta": "Gasolinera",  # Nueva subcategoría
        "categoria_correcta": "Transporte",
        "razon": "Servi Indoor es gasolinera/servicentro",
    },
    {
        "comercio_like": "PRICE SMART%",
        "comercio_exacto": None,
        "subcategoria_correcta": "Supermercado",  # Nueva subcategoría
        "categoria_correcta": "Necesidades", 
        "razon": "PriceSmart es club de compras/supermercado mayorista",
    },
    {
        "comercio_like": "SUBWAY AYARCO",
        "comercio_exacto": "SUBWAY AYARCO",
        "subcategoria_correcta": "Comida",
        "categoria_correcta": "Necesidades",
        "razon": "Subway es restaurante de comida rápida",
    },
    {
        "comercio_like": "LEGADO BARBERIA",
        "comercio_exacto": "LEGADO BARBERIA",
        "subcategoria_correcta": "Cuidado Personal",  # Nueva subcategoría
        "categoria_correcta": "Necesidades",
        "razon": "Barbería es cuidado personal",
    },
    {
        "comercio_like": "GOAT",
        "comercio_exacto": "GOAT",
        "subcategoria_correcta": "Compras Online",  # Nueva subcategoría
        "categoria_correcta": "Gustos",
        "razon": "GOAT es plataforma de compra de sneakers/moda",
    },
    {
        "comercio_like": "FEELINGS",
        "comercio_exacto": "FEELINGS",
        "subcategoria_correcta": "Entretenimiento",
        "categoria_correcta": "Gustos",
        "razon": "Probablemente entretenimiento/ocio",
    },
    {
        "comercio_like": "SHOPSIMON",
        "comercio_exacto": "SHOPSIMON",
        "subcategoria_correcta": "Compras Online",
        "categoria_correcta": "Gustos",
        "razon": "Simon Property - tienda de outlets online",
    },
    {
        "comercio_like": "MC.DONALDS%",
        "comercio_exacto": None,
        "subcategoria_correcta": "Comida",
        "categoria_correcta": "Necesidades",
        "razon": "McDonald's es comida rápida",
    },
    {
        "comercio_like": "ON INC%",
        "comercio_exacto": None,
        "subcategoria_correcta": "Compras Online",
        "categoria_correcta": "Gustos",
        "razon": "ON Inc (OnFoot) - plataforma de e-commerce",
    },
    {
        "comercio_like": "VINDI%",
        "comercio_exacto": None,
        "subcategoria_correcta": "Supermercado",
        "categoria_correcta": "Necesidades",
        "razon": "Vindi es cadena de supermercados de Costa Rica",
    },
    {
        "comercio_like": "WEB CHECKOUT JPS%",
        "comercio_exacto": None,
        "subcategoria_correcta": "Servicios",
        "categoria_correcta": "Necesidades",
        "razon": "JPS - Jasec o servicio público",
    },
]


def main():
    """Ejecuta las correcciones."""
    engine = create_engine(settings.get_database_url())
    
    with engine.begin() as conn:
        # 1. Obtener categorías existentes
        result = conn.execute(text("""
            SELECT id, nombre FROM categories
        """)).fetchall()
        
        categorias = {r.nombre: r.id for r in result}
        print(f"📂 Categorías encontradas: {list(categorias.keys())}")
        
        # 2. Obtener subcategorías existentes
        result = conn.execute(text("""
            SELECT s.id, s.nombre, c.nombre as categoria_nombre
            FROM subcategories s
            JOIN categories c ON s.category_id = c.id
        """)).fetchall()
        
        subcategorias = {(r.nombre, r.categoria_nombre): r.id for r in result}
        print(f"📁 Subcategorías encontradas: {len(subcategorias)}")
        
        # 3. Crear subcategorías faltantes
        nuevas_subcategorias = set()
        for correccion in CORRECCIONES:
            subcat = correccion["subcategoria_correcta"]
            cat = correccion["categoria_correcta"]
            
            if (subcat, cat) not in subcategorias:
                nuevas_subcategorias.add((subcat, cat))
        
        for subcat, cat in nuevas_subcategorias:
            if cat not in categorias:
                print(f"⚠️ Categoría '{cat}' no existe, saltando...")
                continue
            
            # Iconos por subcategoría
            iconos = {
                "Gasolinera": "⛽",
                "Supermercado": "🛒",
                "Cuidado Personal": "💈",
                "Compras Online": "📦",
            }
            icono = iconos.get(subcat, "📌")
                
            new_id = str(uuid4())
            conn.execute(text("""
                INSERT INTO subcategories (id, nombre, category_id, icono, created_at)
                VALUES (:id, :nombre, :category_id, :icono, NOW())
            """), {
                "id": new_id,
                "nombre": subcat,
                "category_id": categorias[cat],
                "icono": icono,
            })
            subcategorias[(subcat, cat)] = new_id
            print(f"✅ Creada subcategoría: {subcat} → {cat} {icono}")
        
        # 4. Aplicar correcciones
        total_corregidas = 0
        
        for correccion in CORRECCIONES:
            subcat = correccion["subcategoria_correcta"]
            cat = correccion["categoria_correcta"]
            comercio_like = correccion["comercio_like"]
            razon = correccion["razon"]
            
            subcat_id = subcategorias.get((subcat, cat))
            if not subcat_id:
                print(f"⚠️ Subcategoría no encontrada: {subcat} → {cat}")
                continue
            
            # Actualizar transacciones
            result = conn.execute(text("""
                UPDATE transactions 
                SET subcategory_id = :subcategory_id,
                    categoria_sugerida_por_ia = :categoria,
                    confirmada = TRUE,
                    notas = COALESCE(notas, '') || :nota
                WHERE comercio ILIKE :comercio
                AND (confirmada IS NULL OR confirmada = FALSE)
                RETURNING id, comercio
            """), {
                "subcategory_id": subcat_id,
                "categoria": subcat,
                "comercio": comercio_like,
                "nota": f"\n[CORREGIDO] {razon}",
            })
            
            actualizadas = result.fetchall()
            if actualizadas:
                for row in actualizadas:
                    print(f"  📝 {row.comercio} → {subcat} ({cat})")
                    total_corregidas += 1
        
        # 5. Registrar en el sistema de aprendizaje
        print("\n📊 Registrando correcciones en sistema de aprendizaje...")
        
        # Obtener profile_id
        profile_result = conn.execute(text("""
            SELECT id FROM profiles WHERE email = 'sebastian.cruzguzman@outlook.com' LIMIT 1
        """)).fetchone()
        
        if profile_result:
            profile_id = profile_result.id
            
            # Crear o actualizar reglas de aprendizaje
            for correccion in CORRECCIONES:
                comercio = correccion["comercio_exacto"] or correccion["comercio_like"].replace('%', '')
                subcat = correccion["subcategoria_correcta"]
                
                # Insertar regla de categorización
                conn.execute(text("""
                    INSERT INTO categorization_rules (
                        id, pattern, pattern_type, category_result,
                        confidence, is_user_defined, usage_count, created_at
                    ) VALUES (
                        :id, :pattern, 'contains', :category_result,
                        0.95, TRUE, 1, NOW()
                    )
                    ON CONFLICT (pattern, pattern_type) 
                    DO UPDATE SET 
                        category_result = :category_result,
                        confidence = 0.95,
                        usage_count = categorization_rules.usage_count + 1,
                        updated_at = NOW()
                """), {
                    "id": str(uuid4()),
                    "pattern": comercio.lower(),
                    "category_result": subcat,
                })
                
        print(f"\n✅ Completado: {total_corregidas} transacciones corregidas")
        

if __name__ == "__main__":
    main()
