#!/usr/bin/env python3
"""Script para corregir transacciones existentes.

Arregla:
1. Depósitos/salarios -> excluir_de_presupuesto=True
2. Intereses -> excluir_de_presupuesto=True
3. Transferencias SINPE sin beneficiario claro -> necesita_reconciliacion_sinpe=True
4. Categorizar transacciones sin categoría
5. Crear Incomes a partir de depósitos de salario
"""

import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import select, update

from finanzas_tracker.core.database import get_session
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.models.income import Income
from finanzas_tracker.models.enums import TransactionType, Currency
from finanzas_tracker.services.smart_categorizer import SmartCategorizer


def fix_deposits_and_salaries() -> int:
    """Marca depósitos y salarios como excluir_de_presupuesto=True."""
    with get_session() as session:
        # Depósitos e intereses
        stmt = update(Transaction).where(
            Transaction.tipo_transaccion.in_([
                TransactionType.DEPOSIT,
                TransactionType.INTEREST_EARNED,
            ]),
            Transaction.excluir_de_presupuesto == False,  # noqa: E712
        ).values(excluir_de_presupuesto=True)
        
        result = session.execute(stmt)
        session.commit()
        
        return result.rowcount


def fix_sinpe_reconciliation() -> int:
    """Marca transferencias SINPE sin beneficiario claro para reconciliación."""
    
    with get_session() as session:
        # Obtener todas las transferencias
        stmt = select(Transaction).where(
            Transaction.tipo_transaccion == TransactionType.TRANSFER,
            Transaction.necesita_reconciliacion_sinpe == False,  # noqa: E712
            Transaction.deleted_at.is_(None),
        )
        
        transfers = list(session.execute(stmt).scalars())
        count = 0
        
        for tx in transfers:
            if _necesita_reconciliacion(tx.comercio):
                tx.necesita_reconciliacion_sinpe = True
                count += 1
        
        session.commit()
        return count


def _necesita_reconciliacion(comercio: str | None) -> bool:
    """Determina si una transacción SINPE necesita reconciliación."""
    if not comercio:
        return True
    
    # Si es solo números, es una referencia bancaria
    if comercio.replace(" ", "").replace("-", "").isdigit():
        return True
    
    # Descripciones genéricas
    genericos = [
        "sin_descripcion",
        "transferencia",
        "sinpe movil",
        "pago sinpe",
    ]
    comercio_lower = comercio.lower()
    for gen in genericos:
        if gen in comercio_lower:
            return True
    
    return False


def categorize_uncategorized() -> int:
    """Categoriza transacciones sin categoría."""
    categorizer = SmartCategorizer()
    
    with get_session() as session:
        # Incluir compras y transferencias (no depósitos/intereses)
        stmt = select(Transaction).where(
            Transaction.subcategory_id.is_(None),
            Transaction.deleted_at.is_(None),
            Transaction.tipo_transaccion.in_([
                TransactionType.PURCHASE,
                TransactionType.TRANSFER,
            ]),
        )
        
        transactions = list(session.execute(stmt).scalars())
        count = 0
        
        for tx in transactions:
            try:
                result = categorizer.categorize(
                    comercio=tx.comercio,
                    monto=tx.monto_crc,
                    profile_id=tx.profile_id,
                )
                if result.subcategory_id:
                    tx.subcategory_id = result.subcategory_id
                    # confidence ya viene 0-100, no multiplicar
                    tx.confianza_categoria = min(result.confidence, 100)
                    count += 1
            except Exception as e:
                print(f"⚠️ Error categorizando {tx.comercio}: {e}")
        
        session.commit()
        return count


def main() -> None:
    """Ejecuta todas las correcciones."""
    print("🔧 Corrigiendo transacciones existentes...\n")
    
    # 1. Depósitos y salarios
    deposits_fixed = fix_deposits_and_salaries()
    print(f"✅ {deposits_fixed} depósitos/intereses marcados como excluir_de_presupuesto")
    
    # 2. SINPE reconciliación
    sinpe_fixed = fix_sinpe_reconciliation()
    print(f"✅ {sinpe_fixed} transferencias marcadas para reconciliación SINPE")
    
    # 3. Categorización
    categorized = categorize_uncategorized()
    print(f"✅ {categorized} transacciones categorizadas")
    
    # 4. Crear ingresos desde depósitos de salario
    incomes_created = create_incomes_from_salaries()
    print(f"✅ {incomes_created} ingresos creados desde depósitos de salario")
    
    print(f"\n🎉 Correcciones completadas!")


def create_incomes_from_salaries() -> int:
    """Crea registros de Income a partir de depósitos de salario."""
    with get_session() as session:
        # Buscar depósitos que parecen ser salarios
        stmt = select(Transaction).where(
            Transaction.tipo_transaccion == TransactionType.DEPOSIT,
            Transaction.deleted_at.is_(None),
        )
        
        deposits = list(session.execute(stmt).scalars())
        created = 0
        
        for tx in deposits:
            comercio_lower = (tx.comercio or "").lower()
            
            # Verificar si es un salario
            es_salario = any(word in comercio_lower for word in [
                "salario", "nomina", "payroll", "planilla", "bosch"
            ])
            
            if not es_salario:
                continue
            
            # Verificar que no exista ya un income para esta transacción
            existing = session.execute(
                select(Income).where(
                    Income.profile_id == tx.profile_id,
                    Income.fecha_deposito == tx.fecha_transaccion.date() if tx.fecha_transaccion else None,
                    Income.monto_neto == tx.monto_crc,
                )
            ).scalar_one_or_none()
            
            if existing:
                continue
            
            # Crear income
            income = Income(
                id=str(uuid4()),
                profile_id=tx.profile_id,
                fuente="Bosch (Salario)",
                tipo="salario",
                monto_bruto=tx.monto_crc,
                monto_neto=tx.monto_crc,
                moneda=Currency.CRC,
                fecha_deposito=tx.fecha_transaccion.date() if tx.fecha_transaccion else None,
                notas=f"🏦 Creado desde transacción de depósito: {tx.email_id}",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            session.add(income)
            created += 1
        
        session.commit()
        return created


if __name__ == "__main__":
    main()
