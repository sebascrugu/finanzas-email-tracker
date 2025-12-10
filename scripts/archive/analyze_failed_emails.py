#!/usr/bin/env python3
"""
Script para analizar específicamente los correos fallidos.
Necesitamos ver el contenido real de los que tienen monto = 0.
"""

from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from finanzas_tracker.core.logging import setup_logging
from finanzas_tracker.parsers.bac_parser import BACParser
from finanzas_tracker.services.auth_manager import auth_manager

setup_logging()

BAC_SENDERS = [
    "notificacion@notificacionesbaccr.com",
    "alerta@baccredomatic.com",
]


def main():
    """Analizar todos los correos fallidos."""
    print("🔄 Analizando correos fallidos...\n")
    
    import requests
    
    token = auth_manager.get_access_token()
    if not token:
        print("❌ No se pudo obtener token de acceso")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    parser = BACParser()
    
    start_date = datetime.now() - timedelta(days=60)
    start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Buscar TODOS los correos de BAC
    sender_filter = " or ".join([f"from/emailAddress/address eq '{s}'" for s in BAC_SENDERS])
    params = {
        "$filter": f"receivedDateTime ge {start_date_str} and ({sender_filter})",
        "$top": 200,
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
    
    failed_emails = []
    
    for email in emails:
        subject = email.get("subject", "")
        body_html = email.get("body", {}).get("content", "")
        from_addr = email.get("from", {}).get("emailAddress", {}).get("address", "")
        received = email.get("receivedDateTime", "")[:10]
        
        email_data = {
            "id": email.get("id"),
            "subject": subject,
            "from": from_addr,
            "body": body_html,
            "receivedDateTime": received,
        }
        
        result = parser.parse(email_data)
        
        if result is None:
            failed_emails.append({
                "subject": subject,
                "date": received,
                "body_html": body_html,
            })
    
    print(f"\n📋 CORREOS FALLIDOS: {len(failed_emails)}\n")
    
    for i, email in enumerate(failed_emails[:10], 1):
        soup = BeautifulSoup(email["body_html"], "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        
        print("=" * 80)
        print(f"❌ [{i}] {email['subject'][:70]}")
        print(f"   📅 {email['date']}")
        print("-" * 80)
        
        # Mostrar primeras 20 líneas
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines[:20]:
            print(f"   {line[:75]}")
        
        print("=" * 80)
        print()


if __name__ == "__main__":
    main()
