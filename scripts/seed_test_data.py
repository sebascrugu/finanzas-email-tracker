#!/usr/bin/env python3
"""
Script para cargar datos de prueba simulando un estado de cuenta típico de Costa Rica.

Ejecutar con: poetry run python scripts/seed_test_data.py
"""

import sys
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

# Agregar src al path
sys.path.insert(0, "src")

from finanzas_tracker.core.database import get_session
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.models.category import Category, Subcategory


def create_test_profile(session) -> Profile:
    """Crea un perfil de prueba."""
    profile = Profile(
        id=str(uuid4()),
        nombre="Sebastián Test",
        email_outlook="test@finanzas.cr",
        es_activo=True,
        activo=True,
    )
    session.add(profile)
    session.commit()
    print(f"✅ Perfil creado: {profile.nombre} ({profile.id})")
    return profile


def create_test_transactions(session, profile_id: str) -> list[Transaction]:
    """Crea transacciones de prueba simulando un mes típico en Costa Rica."""
    
    # Transacciones típicas de un mes
    transactions_data = [
        # Supermercados
        {"comercio": "Walmart Escazú", "monto": 45000, "tipo": "compra", "banco": "bac", "dias_atras": 2, "categoria": "Supermercado"},
        {"comercio": "Automercado Multiplaza", "monto": 32000, "tipo": "compra", "banco": "bac", "dias_atras": 5, "categoria": "Supermercado"},
        {"comercio": "Pricesmart Escazú", "monto": 89000, "tipo": "compra", "banco": "bac", "dias_atras": 8, "categoria": "Supermercado"},
        {"comercio": "MasxMenos Santa Ana", "monto": 18500, "tipo": "compra", "banco": "popular", "dias_atras": 12, "categoria": "Supermercado"},
        {"comercio": "Perimercados Lindora", "monto": 22000, "tipo": "compra", "banco": "bac", "dias_atras": 15, "categoria": "Supermercado"},
        
        # Restaurantes y comida
        {"comercio": "Starbucks Multiplaza", "monto": 4500, "tipo": "compra", "banco": "bac", "dias_atras": 1, "categoria": "Cafetería"},
        {"comercio": "McDonalds Escazú", "monto": 8500, "tipo": "compra", "banco": "bac", "dias_atras": 3, "categoria": "Comida rápida"},
        {"comercio": "Tacobell Forum", "monto": 6200, "tipo": "compra", "banco": "bac", "dias_atras": 4, "categoria": "Comida rápida"},
        {"comercio": "Restaurante La Terraza", "monto": 35000, "tipo": "compra", "banco": "bac", "dias_atras": 7, "categoria": "Restaurante"},
        {"comercio": "Pizza Hut Delivery", "monto": 15000, "tipo": "compra", "banco": "popular", "dias_atras": 10, "categoria": "Comida rápida"},
        {"comercio": "Soda Típica El Ranchito", "monto": 5500, "tipo": "compra", "banco": "bac", "dias_atras": 14, "categoria": "Restaurante"},
        
        # Gasolina y transporte
        {"comercio": "Gasolinera Total Santa Ana", "monto": 25000, "tipo": "compra", "banco": "bac", "dias_atras": 3, "categoria": "Gasolina"},
        {"comercio": "Shell Escazú", "monto": 22000, "tipo": "compra", "banco": "bac", "dias_atras": 10, "categoria": "Gasolina"},
        {"comercio": "Uber Costa Rica", "monto": 8500, "tipo": "compra", "banco": "bac", "dias_atras": 6, "categoria": "Transporte"},
        {"comercio": "DiDi Costa Rica", "monto": 5200, "tipo": "compra", "banco": "bac", "dias_atras": 11, "categoria": "Transporte"},
        
        # Servicios y suscripciones
        {"comercio": "Netflix", "monto": 8900, "tipo": "compra", "banco": "bac", "dias_atras": 20, "categoria": "Entretenimiento"},
        {"comercio": "Spotify Premium", "monto": 4900, "tipo": "compra", "banco": "bac", "dias_atras": 20, "categoria": "Entretenimiento"},
        {"comercio": "Amazon Prime", "monto": 6500, "tipo": "compra", "banco": "bac", "dias_atras": 18, "categoria": "Entretenimiento"},
        {"comercio": "ICE Electricidad", "monto": 45000, "tipo": "pago", "banco": "popular", "dias_atras": 15, "categoria": "Servicios"},
        {"comercio": "AyA Agua", "monto": 12000, "tipo": "pago", "banco": "popular", "dias_atras": 15, "categoria": "Servicios"},
        {"comercio": "Kolbi Internet", "monto": 28000, "tipo": "pago", "banco": "popular", "dias_atras": 16, "categoria": "Servicios"},
        
        # Farmacia y salud
        {"comercio": "Farmacia Fischel", "monto": 15500, "tipo": "compra", "banco": "bac", "dias_atras": 9, "categoria": "Farmacia"},
        {"comercio": "Farmacia Sucre", "monto": 8200, "tipo": "compra", "banco": "bac", "dias_atras": 13, "categoria": "Farmacia"},
        {"comercio": "Hospital CIMA", "monto": 75000, "tipo": "compra", "banco": "bac", "dias_atras": 22, "categoria": "Salud"},
        
        # Compras varias
        {"comercio": "Amazon.com", "monto": 45000, "tipo": "compra", "banco": "bac", "dias_atras": 7, "categoria": "Compras online", "notas": "Auriculares Sony"},
        {"comercio": "Ishop iCon", "monto": 125000, "tipo": "compra", "banco": "bac", "dias_atras": 25, "categoria": "Tecnología", "notas": "Case iPhone"},
        {"comercio": "Ekono Lindora", "monto": 18000, "tipo": "compra", "banco": "bac", "dias_atras": 17, "categoria": "Hogar"},
        
        # SINPE Móvil
        {"comercio": "SINPE a María López", "monto": 15000, "tipo": "sinpe", "banco": "bac", "dias_atras": 2, "categoria": "Transferencia"},
        {"comercio": "SINPE de Papá", "monto": 50000, "tipo": "sinpe", "banco": "bac", "dias_atras": 5, "categoria": "Transferencia", "notas": "Para el almuerzo"},
        {"comercio": "SINPE a Roommate", "monto": 150000, "tipo": "sinpe", "banco": "popular", "dias_atras": 1, "categoria": "Transferencia", "notas": "Parte del alquiler"},
        
        # Retiros de cajero
        {"comercio": "ATM BAC San José", "monto": 100000, "tipo": "retiro", "banco": "bac", "dias_atras": 12},
        {"comercio": "ATM Popular Escazú", "monto": 50000, "tipo": "retiro", "banco": "popular", "dias_atras": 19},
        
        # Compras en USD (convertidas)
        {"comercio": "Apple App Store", "monto": 5200, "tipo": "compra", "banco": "bac", "dias_atras": 4, "categoria": "Tecnología", "moneda": "USD", "monto_usd": 9.99},
        {"comercio": "Google Play", "monto": 2600, "tipo": "compra", "banco": "bac", "dias_atras": 8, "categoria": "Tecnología", "moneda": "USD", "monto_usd": 4.99},
    ]
    
    transactions = []
    now = datetime.now()
    
    for data in transactions_data:
        fecha = now - timedelta(days=data["dias_atras"])
        
        tx = Transaction(
            id=uuid4(),
            profile_id=profile_id,
            comercio=data["comercio"],
            tipo_transaccion=data["tipo"],
            monto_crc=Decimal(str(data["monto"])),
            monto_original=Decimal(str(data.get("monto_usd", data["monto"]))),
            moneda_original=data.get("moneda", "CRC"),
            banco=data["banco"],
            fecha_transaccion=fecha,
            email_id=f"test-{uuid4().hex[:8]}",
            categoria_sugerida_por_ia=data.get("categoria"),
            notas=data.get("notas"),
        )
        
        session.add(tx)
        transactions.append(tx)
    
    session.commit()
    print(f"✅ {len(transactions)} transacciones creadas")
    return transactions


def main() -> None:
    """Carga datos de prueba."""
    print("🚀 Cargando datos de prueba...\n")
    
    with get_session() as session:
        # Verificar si ya hay datos
        existing = session.query(Transaction).count()
        if existing > 5:
            print(f"⚠️  Ya existen {existing} transacciones. ¿Desea agregar más? (s/n)")
            response = input().strip().lower()
            if response != "s":
                print("Cancelado.")
                return
        
        # Crear perfil de prueba
        profile = create_test_profile(session)
        
        # Crear transacciones
        transactions = create_test_transactions(session, str(profile.id))
        
        # Resumen
        total_gastado = sum(t.monto_crc for t in transactions if t.tipo_transaccion == "compra")
        print(f"\n📊 Resumen:")
        print(f"   - Total transacciones: {len(transactions)}")
        print(f"   - Total gastado: ₡{total_gastado:,.0f}")
        print(f"   - Profile ID: {profile.id}")
        
        print("\n✅ Datos de prueba cargados exitosamente!")


if __name__ == "__main__":
    main()
