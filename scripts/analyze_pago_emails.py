#!/usr/bin/env python3
"""
Script para analizar el correo de Notificación de Pago de BAC.
"""

from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from finanzas_tracker.core.logging import setup_logging
from finanzas_tracker.parsers.bac_parser import BACParser
from finanzas_tracker.services.auth_manager import auth_manager

setup_logging()


def main():
    """Analizar correo de pago de tarjeta."""
    print("🔄 Buscando correos de Pago de BAC...\n")
    
    import requests
    
    token = auth_manager.get_access_token()
    if not token:
        print("❌ No se pudo obtener token de acceso")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Buscar correos de Pago
    start_date = datetime.now() - timedelta(days=60)
    start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    params = {
        "$filter": f"receivedDateTime ge {start_date_str} and contains(subject, 'Pago')",
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
    
    print(f"📬 Encontrados {len(emails)} correos con 'Pago'\n")
    
    parser = BACParser()
    
    for email in emails:
        subject = email.get("subject", "")
        sender = email.get("from", {}).get("emailAddress", {}).get("address", "")
        received = email.get("receivedDateTime", "")[:16]
        body_html = email.get("body", {}).get("content", "")
        
        soup = BeautifulSoup(body_html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        
        print("=" * 80)
        print(f"📧 ASUNTO: {subject}")
        print(f"📤 REMITENTE: {sender}")
        print(f"📅 FECHA: {received}")
        print("-" * 80)
        print("CONTENIDO COMPLETO:")
        print("-" * 80)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines[:50]:
            print(f"  {line}")
        print("-" * 80)
        
        # Intentar parsear
        print("\n🔬 RESULTADO DEL PARSER:")
        result = parser.parse(email)
        
        if result:
            print(f"  ✅ PARSEADO:")
            print(f"     Tipo: {result['tipo_transaccion']}")
            print(f"     Monto: {result['moneda_original']} {result['monto_original']:,.2f}")
            print(f"     Fecha: {result['fecha_transaccion']}")
            print(f"     Comercio: {result['comercio']}")
            if result.get("metadata"):
                for k, v in result["metadata"].items():
                    print(f"     {k}: {v}")
        else:
            print("  ❌ NO SE PUDO PARSEAR")
        
        print("=" * 80)
        print("\n")


if __name__ == "__main__":
    main()
