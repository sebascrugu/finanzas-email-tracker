"""
Script para auto-categorizar transacciones basado en patrones de Costa Rica.

Analiza el comercio/descripción y asigna la subcategoría correcta.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from decimal import Decimal

# Conexión
engine = create_engine('postgresql://finanzas:finanzas_dev_2024@localhost:5432/finanzas_tracker')

# IDs de subcategorías
SUBCATS = {
    # Necesidades
    "transporte": "8f493ce6-3812-4fe9-8e59-df84b29a7fd6",
    "trabajo": "7ccfaff8-de33-4359-8a02-a5a87929e152",
    "personal": "c6cd7093-c538-4f89-92d7-94eac6be8695",
    "vivienda": "117064a7-9d14-4061-8673-2ea28b3c7b7b",
    "supermercado": "3fd3f256-39f3-498b-98a1-ff60108bb7eb",
    # Gustos
    "comida_social": "b941a635-07ef-41f1-aee5-2d8489a2b41a",
    "entretenimiento": "705ee53c-834f-4155-a864-5a2593756f67",
    "shopping": "e0768479-ccd7-462b-b897-275736422559",
    "hobbies": "6e1283f8-05f5-48f6-81d7-e3034af5881b",
    # Ahorros
    "ahorro_regular": "c4e23cd7-be3e-4bd2-b6ff-4be661635a37",
    "inversiones": "2f0232ff-b138-4d16-b077-af044e5dcc27",
    "metas": "0f3ed773-3a31-4633-82d6-89e5a0631973",
}

def categorizar_transaccion(comercio: str, monto: float, tipo_tx: str | None) -> tuple[str | None, str]:
    """
    Categoriza una transacción basado en el comercio.
    
    Returns:
        (subcategory_id, razon)
    """
    comercio_lower = comercio.lower() if comercio else ""
    
    # === INGRESOS (tipo_transaccion = 'ingreso' o 'credito') ===
    if "salario" in comercio_lower or "bosch" in comercio_lower:
        return None, "INGRESO: Salario"
    
    # === TRANSFERENCIAS INTERNAS (SINPE a familiares) ===
    # Estos son transferencias, no "gastos" como tal
    if "sinpe sebastian,ernesto" in comercio_lower:
        return SUBCATS["ahorro_regular"], "Transferencia familiar (categorizado como ahorro)"
    
    # === ENTRETENIMIENTO / GUSTOS ===
    if any(x in comercio_lower for x in ["bet365", "apuesta"]):
        return SUBCATS["entretenimiento"], "Apuestas deportivas"
    
    if any(x in comercio_lower for x in ["supercell", "supercellstore", "clash", "brawl"]):
        return SUBCATS["entretenimiento"], "Videojuegos móviles"
    
    if any(x in comercio_lower for x in ["jps", "loteria", "lot nac"]):
        return SUBCATS["entretenimiento"], "Lotería/Juegos de azar"
    
    if any(x in comercio_lower for x in ["netflix", "spotify", "disney", "hbo", "youtube premium"]):
        return SUBCATS["entretenimiento"], "Streaming"
    
    if "amazon prime" in comercio_lower and monto < 10000:
        return SUBCATS["entretenimiento"], "Amazon Prime (suscripción)"
    
    # === SHOPPING ===
    if any(x in comercio_lower for x in ["amazon", "paypal", "ebay", "aliexpress"]):
        return SUBCATS["shopping"], "Compras online"
    
    if any(x in comercio_lower for x in ["crocs", "nike", "adidas", "zara", "h&m"]):
        return SUBCATS["shopping"], "Ropa/Zapatos"
    
    if "total imports" in comercio_lower:
        return SUBCATS["shopping"], "Compras importadas"
    
    # === HERRAMIENTAS / TRABAJO ===
    if any(x in comercio_lower for x in ["anthropic", "openai", "chatgpt", "claude"]):
        return SUBCATS["trabajo"], "Herramientas AI para trabajo"
    
    # === TRANSPORTE ===
    if any(x in comercio_lower for x in ["peaje", "compass", "gasolina", "gasolinera", "uber", "didi"]):
        return SUBCATS["transporte"], "Transporte/Peajes"
    
    if "atm" in comercio_lower or "retiro" in comercio_lower:
        return SUBCATS["personal"], "Retiro de efectivo"
    
    # === VIVIENDA ===
    if any(x in comercio_lower for x in ["cable", "internet", "ice", "kolbi", "tigo"]):
        return SUBCATS["vivienda"], "Servicios del hogar"
    
    # === PAGOS DE TARJETAS ===
    if "pago" in comercio_lower and ("****" in comercio_lower or "377" in comercio_lower or "530" in comercio_lower):
        return SUBCATS["personal"], "Pago de tarjeta de crédito"
    
    # === SINPE SIN DESCRIPCIÓN ===
    if "sinpe" in comercio_lower:
        descripcion = comercio_lower.replace("sinpe", "").replace("_", " ").strip()
        
        # Casos específicos
        if "funeral" in descripcion:
            return SUBCATS["personal"], "Contribución funeral"
        if "cable" in descripcion:
            return SUBCATS["vivienda"], "Pago cable/internet"
        if "donas" in descripcion or "comida" in descripcion:
            return SUBCATS["comida_social"], "Comida"
        if "pollas" in descripcion:
            return SUBCATS["entretenimiento"], "Apuestas/Pollas"
        if "pago" in descripcion:
            return SUBCATS["personal"], "Pago SINPE genérico"
        
        # SINPE sin descripción clara
        if monto > 50000:
            return SUBCATS["personal"], "Transferencia SINPE (monto alto)"
        return SUBCATS["personal"], "Transferencia SINPE pequeña"
    
    # === INTERESES (ignorar, monto 0) ===
    if "interes" in comercio_lower:
        return None, "Intereses bancarios (ignorar)"
    
    # === NÚMEROS SOLOS (probablemente SINPE a números) ===
    if comercio.isdigit():
        if monto > 50000:
            return SUBCATS["personal"], "Transferencia a número de teléfono"
        return SUBCATS["personal"], "SINPE a número"
    
    # === DEFAULT ===
    return None, "No categorizado - revisar manualmente"


def main():
    with Session(engine) as session:
        # Obtener todas las transacciones sin categorizar
        result = session.execute(text('''
            SELECT id, comercio, monto_crc, monto_original, tipo_transaccion
            FROM transactions 
            WHERE deleted_at IS NULL
            ORDER BY fecha_transaccion DESC
        '''))
        
        transacciones = list(result)
        print(f"\n=== PROCESANDO {len(transacciones)} TRANSACCIONES ===\n")
        
        categorized = 0
        skipped = 0
        ingresos = 0
        
        for row in transacciones:
            comercio = row.comercio or ""
            monto = float(row.monto_crc or row.monto_original or 0)
            
            subcat_id, razon = categorizar_transaccion(comercio, monto, row.tipo_transaccion)
            
            if "INGRESO" in razon:
                # Marcar como ingreso
                session.execute(text('''
                    UPDATE transactions 
                    SET tipo_transaccion = 'ingreso', 
                        notas = :razon,
                        excluir_de_presupuesto = true
                    WHERE id = :id
                '''), {"id": row.id, "razon": razon})
                print(f"💰 INGRESO: {comercio[:40]} | ₡{monto:,.0f}")
                ingresos += 1
                
            elif "Intereses" in razon or monto == 0:
                # Ignorar intereses
                session.execute(text('''
                    UPDATE transactions 
                    SET excluir_de_presupuesto = true,
                        notas = :razon
                    WHERE id = :id
                '''), {"id": row.id, "razon": razon})
                skipped += 1
                
            elif subcat_id:
                # Categorizar
                session.execute(text('''
                    UPDATE transactions 
                    SET subcategory_id = :subcat_id,
                        notas = :razon,
                        necesita_revision = false,
                        confianza_categoria = 90
                    WHERE id = :id
                '''), {"id": row.id, "subcat_id": subcat_id, "razon": razon})
                print(f"✅ {razon[:30]:30} | ₡{monto:>10,.0f} | {comercio[:35]}")
                categorized += 1
                
            else:
                print(f"❓ {razon[:30]:30} | ₡{monto:>10,.0f} | {comercio[:35]}")
        
        session.commit()
        
        print(f"\n=== RESUMEN ===")
        print(f"✅ Categorizadas: {categorized}")
        print(f"💰 Ingresos identificados: {ingresos}")
        print(f"⏭️  Omitidas (intereses): {skipped}")
        print(f"❓ Sin categorizar: {len(transacciones) - categorized - skipped - ingresos}")


if __name__ == "__main__":
    main()
