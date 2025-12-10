#!/usr/bin/env python3
"""Script de Importación - Datos Históricos a Base de Datos.

Este script importa las transacciones históricas de correos BAC a la base de datos
y genera embeddings para el sistema de Smart Learning.

Uso:
    python scripts/import_historical_data.py --days 365
    python scripts/import_historical_data.py --days 365 --dry-run
"""

import argparse
import logging
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def fetch_and_parse_emails(days_back: int = 365) -> list[dict]:
    """
    Obtiene y parsea correos de BAC.
    
    Returns:
        Lista de transacciones parseadas
    """
    from finanzas_tracker.services.email_fetcher import EmailFetcher
    from finanzas_tracker.parsers.bac_parser import BACParser
    
    logger.info(f"📧 Buscando correos BAC de los últimos {days_back} días...")
    
    fetcher = EmailFetcher()
    parser = BACParser()
    
    try:
        emails = fetcher.fetch_emails_for_current_user(days_back=days_back, bank="bac")
        logger.info(f"📬 Encontrados: {len(emails)} correos BAC")
        
        transactions = []
        for email in emails:
            try:
                parsed = parser.parse(email)
                if parsed:
                    transactions.append(parsed)
            except Exception as e:
                logger.debug(f"Error parseando: {e}")
        
        logger.info(f"✅ Parseadas: {len(transactions)} transacciones")
        return transactions
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return []


def get_or_create_profile(db_session, profile_name: str = "sebastian") -> str:
    """
    Obtiene o crea un perfil de usuario.
    
    Returns:
        ID del perfil (string UUID)
    """
    from sqlalchemy import select
    from finanzas_tracker.models.profile import Profile
    
    # Buscar perfil existente por nombre
    stmt = select(Profile).where(Profile.nombre == profile_name)
    profile = db_session.execute(stmt).scalar_one_or_none()
    
    if profile:
        logger.info(f"📌 Usando perfil existente: {profile.nombre} (ID: {profile.id})")
        return profile.id
    
    # Buscar cualquier perfil existente como fallback
    stmt = select(Profile).limit(1)
    profile = db_session.execute(stmt).scalar_one_or_none()
    
    if profile:
        logger.info(f"📌 Usando perfil existente: {profile.nombre} (ID: {profile.id})")
        return profile.id
    
    # Crear perfil
    profile = Profile(
        nombre=profile_name,
        descripcion="Perfil importado automáticamente",
        email_outlook="sebastian.cruzguzman@outlook.com",
    )
    db_session.add(profile)
    db_session.commit()
    
    logger.info(f"📌 Perfil creado: {profile.nombre} (ID: {profile.id})")
    return profile.id


def categorize_transaction(comercio: str, tipo: str) -> tuple[int | None, str]:
    """
    Categorización básica basada en comercio.
    
    Returns:
        Tuple de (category_id, category_name)
    """
    comercio_lower = comercio.lower()
    
    # Mapeo básico de comercios a categorías (orden importa: más específico primero)
    category_rules = [
        # Servicios gubernamentales y utilities (primero para evitar falsos positivos)
        (["municipalidad", "aya", "ice", "cnfl", "jasec", "coopelesca", "gobierno"], 5, "Servicios"),
        (["cobro administracion", "condominio", "cuota"], 5, "Servicios"),
        (["claro", "kolbi", "liberty", "tigo"], 5, "Servicios"),
        
        # Entretenimiento
        (["club sport", "cartagines", "saprissa", "liga", "estadio", "fútbol", "futbol"], 3, "Entretenimiento"),
        (["e-ticket", "cinepolis", "cinemark", "teatro", "concierto"], 3, "Entretenimiento"),
        (["bet365", "apuesta", "casino", "bingo"], 3, "Entretenimiento"),
        (["netflix", "spotify", "disney", "hbo", "streaming"], 3, "Entretenimiento"),
        
        # Comida y bebidas
        (["subway", "mc donald", "mcdonald", "burger", "kfc", "taco bell", "wendy"], 1, "Comida"),
        (["bread house", "panaderia", "bakery", "cafe", "coffee", "starbucks"], 1, "Comida"),
        (["restaurante", "rest.", "food", "pizza", "sushi"], 1, "Comida"),
        (["dunkin", "donut", "krispy", "bagel"], 1, "Comida"),
        (["pollo", "chicken", "wing", "wingzone"], 1, "Comida"),
        (["bar ", "cantina", "sports bar", "pub"], 1, "Comida"),
        (["ayarco", "tacos", "chicharrones"], 1, "Comida"),
        
        # Supermercados
        (["pricesmart", "price smart", "walmart", "automercado", "mas x menos", "pali"], 2, "Supermercado"),
        (["supermercado", "fresh market", "perimercado"], 2, "Supermercado"),
        (["pequeño mundo", "minisuper"], 2, "Supermercado"),
        
        # Transporte
        (["uber", "didi", "beat", "indriver"], 4, "Transporte"),
        (["parqueo", "parking", "estacionamiento"], 4, "Transporte"),
        (["gasolinera", "gas station", "shell", "uno", "total", "delta"], 4, "Transporte"),
        
        # Tecnología
        (["anthropic", "openai", "claude"], 6, "Tecnología"),
        (["amazon", "apple", "google", "microsoft"], 6, "Tecnología"),
        (["steam", "playstation", "xbox", "nintendo"], 6, "Tecnología"),
        
        # Retiros
        (["retiro sin tarjeta", "atm", "cajero"], 7, "Retiros"),
        
        # Pagos de tarjeta
        (["pago tarjeta", "pago tc", "pago credito"], 8, "Pagos Tarjeta"),
        
        # Fitness
        (["gym", "gimnasio", "move", "smart fit", "world gym", "multispa"], 9, "Fitness"),
        (["servi indoor", "deporte", "sport"], 9, "Fitness"),
        (["yoga", "crossfit", "pilates"], 9, "Fitness"),
        
        # Salud
        (["farmacia", "pharmacy", "fischel", "sucre"], 10, "Salud"),
        (["hospital", "clinica", "clinic", "doctor", "dentista"], 10, "Salud"),
        
        # Compras
        (["zara", "h&m", "forever", "mango", "pull&bear"], 11, "Ropa"),
        (["office depot", "tienda"], 11, "Compras"),
    ]
    
    for keywords, cat_id, cat_name in category_rules:
        if any(kw in comercio_lower for kw in keywords):
            return cat_id, cat_name
    
    return None, "Sin categoría"


def import_to_database(
    transactions: list[dict],
    profile_id: str,
    db_session,
    dry_run: bool = False,
) -> dict:
    """
    Importa transacciones a la base de datos.
    
    Returns:
        Estadísticas de importación
    """
    from sqlalchemy import select
    from finanzas_tracker.models.transaction import Transaction
    
    stats = {
        "total": len(transactions),
        "imported": 0,
        "skipped": 0,
        "errors": 0,
        "categories": {},
    }
    
    for txn in transactions:
        try:
            email_id = txn.get("email_id", "")
            
            # Verificar si ya existe
            existing = db_session.execute(
                select(Transaction).where(Transaction.email_id == email_id)
            ).scalar_one_or_none()
            
            if existing:
                logger.debug(f"⏭️ Ya existe: {txn.get('comercio', '')[:30]}")
                stats["skipped"] += 1
                continue
            
            # Categorizar
            comercio = txn.get("comercio", "")
            cat_id, cat_name = categorize_transaction(
                comercio, 
                txn.get("tipo_transaccion", "compra")
            )
            
            stats["categories"][cat_name] = stats["categories"].get(cat_name, 0) + 1
            
            if dry_run:
                logger.info(f"🔄 [DRY-RUN] {comercio[:40]:40} → {cat_name}")
                stats["imported"] += 1
                continue
            
            # Calcular monto en CRC (ya debería estar en CRC la mayoría)
            monto = txn.get("monto_original", Decimal("0"))
            moneda = txn.get("moneda_original", "CRC")
            monto_crc = monto if moneda == "CRC" else monto * Decimal("505")  # aprox tipo de cambio
            
            # Crear transacción
            transaction = Transaction(
                profile_id=profile_id,
                email_id=email_id,
                banco="bac",
                comercio=comercio,
                monto_original=monto,
                moneda_original=moneda,
                monto_crc=monto_crc,
                fecha_transaccion=txn.get("fecha_transaccion", datetime.now()),
                tipo_transaccion=txn.get("tipo_transaccion", "compra"),
                ciudad=txn.get("ciudad"),
                pais=txn.get("pais", "Costa Rica"),
                subcategory_id=None,  # No tenemos IDs de subcategoría reales
                categoria_sugerida_por_ia=cat_name if cat_id else None,
                necesita_revision=cat_id is None,  # Marcar para revisión si no se categorizó
                confirmada=cat_id is not None,
                es_historica=True,  # Son transacciones históricas
                notas=f"Importado automáticamente. Categoría sugerida: {cat_name}",
            )
            
            db_session.add(transaction)
            stats["imported"] += 1
            logger.debug(f"✅ Importado: {comercio[:40]} → {cat_name}")
            
        except Exception as e:
            logger.error(f"Error importando transacción: {e}")
            stats["errors"] += 1
    
    if not dry_run:
        db_session.commit()
    
    return stats


def main() -> None:
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Importar transacciones históricas BAC a la base de datos"
    )
    parser.add_argument("--days", type=int, default=365, help="Días hacia atrás")
    parser.add_argument("--profile", type=str, default="sebastian", help="Nombre del perfil")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin guardar")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("📥 IMPORTACIÓN DE TRANSACCIONES HISTÓRICAS")
    print("=" * 70)
    print(f"📅 Período: últimos {args.days} días")
    print(f"👤 Perfil: {args.profile}")
    if args.dry_run:
        print("⚠️  MODO DRY-RUN: No se guardarán cambios")
    print()
    
    # 1. Obtener transacciones
    transactions = fetch_and_parse_emails(args.days)
    
    if not transactions:
        print("❌ No hay transacciones para importar")
        return
    
    # 2. Configurar base de datos
    from finanzas_tracker.core.database import get_db
    
    db = next(get_db())
    
    try:
        # 3. Obtener/crear perfil
        profile_id = get_or_create_profile(db, args.profile)
        
        # 4. Importar
        stats = import_to_database(
            transactions, 
            profile_id, 
            db, 
            dry_run=args.dry_run
        )
        
        # 5. Mostrar resultados
        print()
        print("=" * 70)
        print("📊 RESUMEN DE IMPORTACIÓN")
        print("=" * 70)
        print(f"  • Total procesadas: {stats['total']}")
        print(f"  • Importadas: {stats['imported']}")
        print(f"  • Omitidas (duplicadas): {stats['skipped']}")
        print(f"  • Errores: {stats['errors']}")
        print()
        
        if stats["categories"]:
            print("📂 POR CATEGORÍA:")
            for cat, count in sorted(stats["categories"].items(), key=lambda x: -x[1]):
                print(f"  • {cat}: {count}")
        
        print("=" * 70)
        
        if args.dry_run:
            print("⚠️  Ejecutar sin --dry-run para guardar cambios")
        else:
            print("✅ Importación completada!")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
