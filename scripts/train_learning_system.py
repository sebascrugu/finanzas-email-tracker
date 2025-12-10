#!/usr/bin/env python3
"""Script de entrenamiento del sistema de ML/Learning.

Este script procesa las transacciones históricas para:
1. Generar patrones a partir de transacciones categorizadas
2. Crear embeddings para búsqueda semántica
3. Detectar patrones recurrentes
4. Actualizar perfiles de aprendizaje de usuarios

Uso:
    # Entrenar desde todas las transacciones históricas
    python scripts/train_learning_system.py
    
    # Entrenar solo un perfil específico
    python scripts/train_learning_system.py --profile-id "123-abc"
    
    # Regenerar embeddings (después de cambiar modelo)
    python scripts/train_learning_system.py --regenerate-embeddings
    
    # Dry run (sin guardar cambios)
    python scripts/train_learning_system.py --dry-run
"""

import argparse
import logging
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finanzas_tracker.core.database import SessionLocal, engine
from finanzas_tracker.models.category import Subcategory
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.smart_learning import (
    GlobalPattern,
    PatternType,
    TransactionPattern,
    UserLearningProfile,
)
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.services.smart_learning_service import SmartLearningService


# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class LearningTrainer:
    """Entrena el sistema de ML desde transacciones históricas."""
    
    def __init__(self, db: Session, dry_run: bool = False) -> None:
        """Inicializa el trainer."""
        self.db = db
        self.dry_run = dry_run
        self.learning_service = SmartLearningService(db)
        
        # Estadísticas
        self.stats = {
            "profiles_processed": 0,
            "transactions_processed": 0,
            "patterns_created": 0,
            "patterns_updated": 0,
            "embeddings_generated": 0,
            "global_patterns_created": 0,
            "errors": 0,
        }
    
    def train_all(self) -> dict:
        """
        Entrena el sistema desde todas las transacciones.
        
        Returns:
            Estadísticas del entrenamiento
        """
        logger.info("🚀 Iniciando entrenamiento del sistema de ML...")
        start_time = datetime.now(UTC)
        
        # Obtener todos los perfiles
        profiles = self.db.query(Profile).all()
        logger.info(f"📊 Perfiles encontrados: {len(profiles)}")
        
        for profile in profiles:
            try:
                self._train_profile(profile.id)
            except Exception as e:
                logger.error(f"❌ Error en perfil {profile.id}: {e}")
                self.stats["errors"] += 1
        
        # Procesar patrones globales
        self._process_global_patterns()
        
        # Guardar cambios (si no es dry run)
        if not self.dry_run:
            self.db.commit()
            logger.info("✅ Cambios guardados en la base de datos")
        else:
            self.db.rollback()
            logger.info("🔄 DRY RUN - Cambios descartados")
        
        elapsed = (datetime.now(UTC) - start_time).total_seconds()
        self.stats["elapsed_seconds"] = round(elapsed, 2)
        
        self._print_stats()
        return self.stats
    
    def train_profile(self, profile_id: str) -> dict:
        """
        Entrena el sistema para un perfil específico.
        
        Args:
            profile_id: ID del perfil
            
        Returns:
            Estadísticas del entrenamiento
        """
        logger.info(f"🚀 Entrenando perfil: {profile_id}")
        
        self._train_profile(profile_id)
        
        if not self.dry_run:
            self.db.commit()
        else:
            self.db.rollback()
        
        self._print_stats()
        return self.stats
    
    def regenerate_embeddings(self, profile_id: str | None = None) -> dict:
        """
        Regenera los embeddings para patrones existentes.
        
        Args:
            profile_id: ID del perfil (None = todos)
            
        Returns:
            Estadísticas
        """
        logger.info("🔄 Regenerando embeddings...")
        
        query = self.db.query(TransactionPattern).filter(
            TransactionPattern.deleted_at.is_(None)
        )
        
        if profile_id:
            query = query.filter(TransactionPattern.profile_id == profile_id)
        
        patterns = query.all()
        logger.info(f"📊 Patrones a procesar: {len(patterns)}")
        
        for pattern in patterns:
            try:
                self.learning_service._generate_and_store_embedding(pattern)
                self.stats["embeddings_generated"] += 1
                
                if self.stats["embeddings_generated"] % 100 == 0:
                    logger.info(f"  → Procesados: {self.stats['embeddings_generated']}")
            except Exception as e:
                logger.error(f"❌ Error en patrón {pattern.id}: {e}")
                self.stats["errors"] += 1
        
        if not self.dry_run:
            self.db.commit()
        
        self._print_stats()
        return self.stats
    
    def _train_profile(self, profile_id: str) -> None:
        """Entrena el sistema para un perfil."""
        # Obtener transacciones categorizadas
        transactions = (
            self.db.query(Transaction)
            .filter(
                Transaction.profile_id == profile_id,
                Transaction.subcategory_id.isnot(None),
                Transaction.deleted_at.is_(None),
            )
            .order_by(Transaction.fecha_transaccion.desc())
            .all()
        )
        
        if not transactions:
            logger.debug(f"No hay transacciones para perfil {profile_id}")
            return
        
        logger.info(f"  📊 Transacciones del perfil: {len(transactions)}")
        self.stats["profiles_processed"] += 1
        
        # Agrupar por beneficiario para crear patrones
        beneficiario_patterns: dict[str, list[Transaction]] = {}
        
        for txn in transactions:
            self.stats["transactions_processed"] += 1
            
            # Patrones por beneficiario
            if txn.beneficiario:
                key = self.learning_service._normalize_text(txn.beneficiario)
                if key:
                    if key not in beneficiario_patterns:
                        beneficiario_patterns[key] = []
                    beneficiario_patterns[key].append(txn)
        
        # Crear patrones
        for pattern_key, txns in beneficiario_patterns.items():
            if len(txns) >= 2:  # Mínimo 2 ocurrencias
                self._create_pattern_from_transactions(
                    profile_id,
                    pattern_key,
                    txns,
                    PatternType.BENEFICIARIO,
                )
        
        # Crear/actualizar perfil de aprendizaje
        self._update_learning_profile(profile_id, transactions)
    
    def _create_pattern_from_transactions(
        self,
        profile_id: str,
        pattern_key: str,
        transactions: list[Transaction],
        pattern_type: PatternType,
    ) -> None:
        """Crea o actualiza un patrón desde transacciones."""
        # Verificar si ya existe
        existing = (
            self.db.query(TransactionPattern)
            .filter(
                TransactionPattern.profile_id == profile_id,
                TransactionPattern.pattern_text_normalized == pattern_key,
                TransactionPattern.deleted_at.is_(None),
            )
            .first()
        )
        
        # Determinar subcategoría más común
        subcat_counts: dict[str, int] = {}
        for txn in transactions:
            if txn.subcategory_id:
                subcat_counts[txn.subcategory_id] = subcat_counts.get(txn.subcategory_id, 0) + 1
        
        if not subcat_counts:
            return
        
        best_subcat = max(subcat_counts, key=lambda k: subcat_counts[k])
        consistency = subcat_counts[best_subcat] / len(transactions)
        
        # Calcular estadísticas de monto
        amounts = [txn.monto_crc for txn in transactions if txn.monto_crc]
        avg_amount = sum(amounts) / len(amounts) if amounts else Decimal("0")
        min_amount = min(amounts) if amounts else Decimal("0")
        max_amount = max(amounts) if amounts else Decimal("0")
        total_amount = sum(amounts) if amounts else Decimal("0")
        
        if existing:
            # Actualizar existente
            existing.times_matched = len(transactions)
            existing.subcategory_id = best_subcat
            existing.confidence = Decimal(str(round(consistency, 4)))
            existing.avg_amount = avg_amount
            existing.min_amount = min_amount
            existing.max_amount = max_amount
            existing.total_amount = total_amount
            existing.last_seen_at = datetime.now(UTC)
            self.stats["patterns_updated"] += 1
        else:
            # Crear nuevo
            original_text = transactions[0].beneficiario or pattern_key
            new_pattern = TransactionPattern(
                profile_id=profile_id,
                pattern_text=original_text,
                pattern_text_normalized=pattern_key,
                pattern_type=pattern_type,
                subcategory_id=best_subcat,
                times_matched=len(transactions),
                times_confirmed=len(transactions),
                confidence=Decimal(str(round(min(0.95, 0.7 + (len(transactions) * 0.05)), 4))),
                avg_amount=avg_amount,
                min_amount=min_amount,
                max_amount=max_amount,
                total_amount=total_amount,
            )
            
            # Generar embedding
            if not self.dry_run:
                self.learning_service._generate_and_store_embedding(new_pattern)
                self.stats["embeddings_generated"] += 1
            
            self.db.add(new_pattern)
            self.stats["patterns_created"] += 1
        
        # Detectar recurrencia
        if len(transactions) >= 3:
            self._detect_recurrence(transactions, existing if existing else new_pattern)
    
    def _detect_recurrence(
        self,
        transactions: list[Transaction],
        pattern: TransactionPattern,
    ) -> None:
        """Detecta si las transacciones son recurrentes."""
        # Verificar si aparecen en días similares del mes
        days = [
            txn.fecha_transaccion.day
            for txn in transactions
            if txn.fecha_transaccion
        ]
        
        if len(days) < 3:
            return
        
        # Calcular variación en días
        avg_day = sum(days) / len(days)
        variance = sum((d - avg_day) ** 2 for d in days) / len(days)
        
        # Si la variación es baja (±3 días), es recurrente
        if variance < 10:  # ~3 días de desviación
            pattern.is_recurring = True
            pattern.recurring_day = round(avg_day)
            
            # Determinar frecuencia
            dates = sorted([txn.fecha_transaccion for txn in transactions if txn.fecha_transaccion])
            if len(dates) >= 2:
                avg_gap = (dates[-1] - dates[0]).days / (len(dates) - 1)
                if avg_gap < 10:
                    pattern.recurring_frequency = "weekly"
                elif avg_gap < 20:
                    pattern.recurring_frequency = "biweekly"
                elif avg_gap < 45:
                    pattern.recurring_frequency = "monthly"
                else:
                    pattern.recurring_frequency = "yearly"
    
    def _update_learning_profile(
        self,
        profile_id: str,
        transactions: list[Transaction],
    ) -> None:
        """Actualiza o crea el perfil de aprendizaje."""
        existing = (
            self.db.query(UserLearningProfile)
            .filter(UserLearningProfile.profile_id == profile_id)
            .first()
        )
        
        if not existing:
            existing = UserLearningProfile(profile_id=profile_id)
            self.db.add(existing)
        
        # Actualizar estadísticas
        existing.total_transactions_categorized = len(transactions)
        
        # Calcular preferencias de categorías
        subcat_counts: dict[str, int] = {}
        for txn in transactions:
            if txn.subcategory_id:
                subcat_counts[txn.subcategory_id] = subcat_counts.get(txn.subcategory_id, 0) + 1
        
        existing.preferred_categories = subcat_counts
        existing.last_learning_at = datetime.now(UTC)
    
    def _process_global_patterns(self) -> None:
        """Procesa y crea patrones globales desde datos crowdsourced."""
        logger.info("🌍 Procesando patrones globales...")
        
        # Obtener patrones que aparecen en múltiples usuarios
        pattern_stats = (
            self.db.query(
                TransactionPattern.pattern_text_normalized,
                TransactionPattern.subcategory_id,
                func.count(TransactionPattern.profile_id.distinct()).label("user_count"),
            )
            .filter(
                TransactionPattern.is_global == False,  # noqa: E712
                TransactionPattern.deleted_at.is_(None),
            )
            .group_by(
                TransactionPattern.pattern_text_normalized,
                TransactionPattern.subcategory_id,
            )
            .having(func.count(TransactionPattern.profile_id.distinct()) >= 2)
            .all()
        )
        
        for pattern_text, subcat_id, user_count in pattern_stats:
            existing_global = (
                self.db.query(GlobalPattern)
                .filter(GlobalPattern.pattern_text_normalized == pattern_text)
                .first()
            )
            
            if existing_global:
                # Actualizar
                existing_global.user_count = user_count
                votes = existing_global.vote_distribution or {}
                votes[subcat_id] = votes.get(subcat_id, 0) + 1
                existing_global.vote_distribution = votes
                
                # Auto-aprobar si cumple condiciones
                if user_count >= 5:
                    existing_global.is_approved = True
                    existing_global.is_auto_approved = True
            else:
                # Crear nuevo
                new_global = GlobalPattern(
                    pattern_text=pattern_text,
                    pattern_text_normalized=pattern_text,
                    pattern_type=PatternType.BENEFICIARIO,
                    primary_subcategory_id=subcat_id,
                    user_count=user_count,
                    vote_distribution={subcat_id: user_count},
                    confidence=Decimal(str(min(0.9, 0.5 + (user_count * 0.1)))),
                    is_approved=user_count >= 5,
                    is_auto_approved=user_count >= 5,
                )
                self.db.add(new_global)
                self.stats["global_patterns_created"] += 1
    
    def _print_stats(self) -> None:
        """Imprime estadísticas del entrenamiento."""
        print("\n" + "=" * 60)
        print("📊 ESTADÍSTICAS DE ENTRENAMIENTO")
        print("=" * 60)
        
        for key, value in self.stats.items():
            label = key.replace("_", " ").title()
            print(f"  {label}: {value}")
        
        print("=" * 60 + "\n")


def main() -> None:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(
        description="Entrena el sistema de ML desde transacciones históricas"
    )
    parser.add_argument(
        "--profile-id",
        type=str,
        help="ID del perfil a entrenar (default: todos)",
    )
    parser.add_argument(
        "--regenerate-embeddings",
        action="store_true",
        help="Solo regenerar embeddings existentes",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No guardar cambios en la base de datos",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Mostrar más información",
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Crear sesión de base de datos
    db = SessionLocal()
    
    try:
        trainer = LearningTrainer(db, dry_run=args.dry_run)
        
        if args.regenerate_embeddings:
            trainer.regenerate_embeddings(args.profile_id)
        elif args.profile_id:
            trainer.train_profile(args.profile_id)
        else:
            trainer.train_all()
            
    except Exception as e:
        logger.error(f"❌ Error durante entrenamiento: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
