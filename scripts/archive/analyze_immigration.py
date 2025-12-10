#!/usr/bin/env python3
"""Analizar el correo de Immigration Canada que falla."""

from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from finanzas_tracker.core.logging import setup_logging
from finanzas_tracker.services.auth_manager import auth_manager
from finanzas_tracker.parsers.bac_parser import BACParser

setup_logging()

def main():
    import requests
    
    token = auth_manager.get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    # Buscar el correo de Immigration Canada
    start_date = datetime.now() - timedelta(days=60)
    start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    params = {
        "$filter": f"receivedDateTime ge {start_date_str} and contains(subject, 'IMMIGRATION CANADA')",
        "$top": 5,
        "$select": "id,subject,receivedDateTime,from,body",
        "$orderby": "receivedDateTime desc",
    }
    
    response = requests.get(
        "https://graph.microsoft.com/v1.0/me/messages",
        headers=headers,
        params=params,
    )
    
    data = response.json()
    emails = data.get("value", [])
    
    print(f"📬 Encontrados: {len(emails)} correos de Immigration Canada\n")
    
    parser = BACParser()
    
    for email in emails:
        subject = email.get("subject", "")
        body_html = email.get("body", {}).get("content", "")
        soup = BeautifulSoup(body_html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        
        print("=" * 80)
        print(f"📧 {subject}")
        print("-" * 80)
        
        # Mostrar contenido
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines[:25]:
            print(f"   {line[:75]}")
        
        print("-" * 80)
        
        # Intentar parsear
        result = parser.parse(email)
        if result:
            print(f"✅ Parseado: {result.get('comercio')} - {result.get('moneda_original')} {result.get('monto_original')}")
        else:
            print(f"❌ No se pudo parsear")
        
        print("=" * 80)
        print()


if __name__ == "__main__":
    main()
