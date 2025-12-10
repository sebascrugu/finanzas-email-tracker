#!/usr/bin/env python3
"""
Script para probar el parser de BAC con correos reales de transferencias.
"""

from datetime import datetime, timedelta

from finanzas_tracker.core.logging import setup_logging
from finanzas_tracker.parsers.bac_parser import BACParser
from finanzas_tracker.services.auth_manager import auth_manager

setup_logging()


def main():
    """Probar el parser con correos reales."""
    print("🔄 Probando parser de BAC con correos reales...\n")
    
    import requests
    
    token = auth_manager.get_access_token()
    if not token:
        print("❌ No se pudo obtener token de acceso")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Buscar correos de transferencia
    start_date = datetime.now() - timedelta(days=35)
    start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    params = {
        "$filter": f"receivedDateTime ge {start_date_str} and contains(subject, 'Transferencia')",
        "$top": 10,
        "$select": "id,subject,receivedDateTime,from,body",
        "$orderby": "receivedDateTime desc",
    }
    
    response = requests.get(
        "https://graph.microsoft.com/v1.0/me/messages",
        headers=headers,
        params=params,
    )
    
    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        return
    
    data = response.json()
    emails = data.get("value", [])
    
    print(f"📬 Encontrados {len(emails)} correos de transferencia\n")
    
    # Crear parser
    parser = BACParser()
    
    # Procesar cada correo
    success = 0
    failed = 0
    
    for email in emails:
        subject = email.get("subject", "")
        received = email.get("receivedDateTime", "")[:16]
        
        print(f"\n{'='*70}")
        print(f"📧 {subject}")
        print(f"📅 {received}")
        print("-" * 70)
        
        # Parsear
        result = parser.parse(email)
        
        if result:
            success += 1
            print(f"✅ PARSEADO CORRECTAMENTE:")
            print(f"   Tipo: {result['tipo_transaccion']}")
            print(f"   Monto: {result['moneda_original']} {result['monto_original']:,.2f}")
            print(f"   Fecha: {result['fecha_transaccion']}")
            print(f"   Comercio: {result['comercio']}")
            if result.get("metadata"):
                print(f"   Destinatario: {result['metadata'].get('destinatario', 'N/A')}")
                print(f"   Concepto: {result['metadata'].get('concepto', 'N/A') or '(sin concepto)'}")
                print(f"   Referencia: {result['metadata'].get('referencia', 'N/A')}")
        else:
            failed += 1
            print(f"❌ NO SE PUDO PARSEAR")
    
    print(f"\n{'='*70}")
    print(f"📊 RESUMEN")
    print("=" * 70)
    print(f"   ✅ Parseados correctamente: {success}")
    print(f"   ❌ Fallidos: {failed}")
    print(f"   📈 Tasa de éxito: {success/(success+failed)*100:.1f}%")


if __name__ == "__main__":
    main()
