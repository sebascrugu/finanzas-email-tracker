#!/usr/bin/env python3
"""Script rápido para probar el parser de estados de cuenta."""

import sys
import json
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from finanzas_tracker.parsers.bac_statement_parser import BACStatementParser

def main():
    """Prueba el parser con el archivo de ejemplo."""
    test_file = Path('data/test_statement.txt')

    if not test_file.exists():
        print(f"❌ Archivo no encontrado: {test_file}")
        return

    print("="*60)
    print("🧪 PROBANDO PARSER DE ESTADOS DE CUENTA BAC")
    print("="*60)

    # Leer archivo
    with open(test_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Parsear
    parser = BACStatementParser()

    try:
        cuentas, transacciones = parser.parse_file(content)

        print(f"\n✅ Parseo exitoso!")
        print(f"\n📋 CUENTAS DETECTADAS: {len(cuentas)}")
        print("-" * 60)

        for i, cuenta in enumerate(cuentas, 1):
            print(f"\nCuenta {i}:")
            print(f"  IBAN: {cuenta.cuenta_iban}")
            print(f"  Moneda: {cuenta.moneda}")
            print(f"  Saldo anterior: {cuenta.moneda} {cuenta.saldo_anterior:,.2f}")
            print(f"  Saldo final: {cuenta.moneda} {cuenta.saldo_final:,.2f}")
            print(f"  Total débitos: {cuenta.moneda} {cuenta.total_debitos:,.2f}")
            print(f"  Total créditos: {cuenta.moneda} {cuenta.total_creditos:,.2f}")

        print(f"\n💳 TRANSACCIONES EXTRAÍDAS: {len(transacciones)}")
        print("-" * 60)

        # Agrupar por cuenta
        txs_por_cuenta = {}
        for tx in transacciones:
            if tx.cuenta_iban not in txs_por_cuenta:
                txs_por_cuenta[tx.cuenta_iban] = []
            txs_por_cuenta[tx.cuenta_iban].append(tx)

        for iban, txs in txs_por_cuenta.items():
            print(f"\nCuenta {iban}: {len(txs)} transacciones")

            # Mostrar primeras 5
            print("\nPrimeras 5 transacciones:")
            for tx in txs[:5]:
                simbolo = "🔴" if tx.tipo == "DEBITO" else "🟢"
                print(f"  {simbolo} {tx.fecha.strftime('%Y-%m-%d')} | {tx.concepto[:40]:40s} | {tx.tipo:7s} | {tx.moneda} {tx.monto:>10,.2f}")

        # Estadísticas
        print("\n📊 ESTADÍSTICAS")
        print("-" * 60)

        total_debitos = sum(tx.monto for tx in transacciones if tx.tipo == "DEBITO")
        total_creditos = sum(tx.monto for tx in transacciones if tx.tipo == "CREDITO")

        print(f"Total débitos: ₡{total_debitos:,.2f}")
        print(f"Total créditos: ₡{total_creditos:,.2f}")
        print(f"Balance: ₡{total_creditos - total_debitos:,.2f}")

        # Tipos de transacción más comunes
        tipos_concepto = {}
        for tx in transacciones:
            concepto_base = tx.concepto.split()[0]  # Primera palabra
            tipos_concepto[concepto_base] = tipos_concepto.get(concepto_base, 0) + 1

        print("\nTipos de transacción más frecuentes:")
        for concepto, count in sorted(tipos_concepto.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {concepto:30s}: {count:3d}")

        # Guardar JSON de prueba
        output_file = Path('data/test_output.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'cuentas': [
                    {
                        'iban': c.cuenta_iban,
                        'moneda': c.moneda,
                        'saldo_final': float(c.saldo_final),
                        'total_debitos': float(c.total_debitos),
                        'total_creditos': float(c.total_creditos),
                    }
                    for c in cuentas
                ],
                'transacciones': [tx.to_dict() for tx in transacciones]
            }, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Output guardado en: {output_file}")

        print("\n✅ TEST COMPLETADO EXITOSAMENTE")

    except Exception as e:
        print(f"\n❌ Error durante el parseo:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == '__main__':
    exit(main())
