#!/usr/bin/env python3
"""
Script para ver correos de SINPE Tiempo Real y otros formatos raros.
"""

from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from finanzas_tracker.core.logging import setup_logging
from finanzas_tracker.services.auth_manager import auth_manager

setup_logging()


def main():
    """Ver detalles de correos especiales."""
    print("🔄 Buscando correos especiales...\n")
    
    import requests
    
    token = auth_manager.get_access_token()
    if not token:
        print("❌ No se pudo obtener token de acceso")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Buscar correos específicos
    start_date = datetime.now() - timedelta(days=35)
    start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Buscar correos de SINPE Tiempo Real
    params = {
        "$filter": f"receivedDateTime ge {start_date_str} and contains(subject, 'SINPE')",
        "$top": 5,
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
    
    print(f"📬 Encontrados {len(emails)} correos con 'SINPE'\n")
    
    for email in emails:
        subject = email.get("subject", "")
        received = email.get("receivedDateTime", "")[:16]
        body_html = email.get("body", {}).get("content", "")
        
        soup = BeautifulSoup(body_html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        
        print("=" * 80)
        print(f"📧 {subject}")
        print(f"📅 {received}")
        print("-" * 80)
        print("CONTENIDO:")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines[:40]:
            print(f"  {line}")
        print("=" * 80)
        print("\n")


if __name__ == "__main__":
    main()
