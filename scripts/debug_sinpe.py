#!/usr/bin/env python3
"""Debug por qué los correos de SINPE afiliación no se filtran."""

from datetime import datetime, timedelta

from finanzas_tracker.core.logging import setup_logging
from finanzas_tracker.services.auth_manager import auth_manager
from finanzas_tracker.parsers.bac_parser import BACParser

setup_logging()

def main():
    import requests
    
    token = auth_manager.get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    # Buscar correos de afiliación SINPE
    start_date = datetime.now() - timedelta(days=60)
    start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    params = {
        "$filter": f"receivedDateTime ge {start_date_str} and contains(subject, 'SINPE')",
        "$top": 10,
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
    
    print(f"📬 Correos con SINPE: {len(emails)}\n")
    
    parser = BACParser()
    
    for email in emails:
        subject = email.get("subject", "")
        subject_lower = subject.lower()
        
        print("=" * 80)
        print(f"📧 Subject: {subject}")
        print(f"   Lower:   {subject_lower}")
        print(f"   Repr:    {subject_lower!r}")
        
        # Show hex codes for special chars
        special_chars = []
        for i, c in enumerate(subject_lower):
            if ord(c) > 127:
                special_chars.append(f"{c!r}({ord(c):04X})")
        print(f"   Special: {special_chars}")
        
        # Test keywords
        config_keywords = [
            "aviso bac", "activación", "activacion",
            "afiliación sinpe", "desafiliación sinpe",
            "afiliacion sinpe", "desafiliacion sinpe",
            "afiliación", "afiliacion", "desafiliación", "desafiliacion",
            "cambio de pin", "cambio de clave",
        ]
        
        matched = []
        for kw in config_keywords:
            if kw in subject_lower:
                matched.append(kw)
        
        print(f"   Matched keywords: {matched}")
        
        # Parse
        result = parser.parse(email)
        if result:
            print(f"   ✅ Parseado: {result.get('tipo_transaccion')}")
        else:
            print(f"   ❌ No parseado (None)")
        
        print("=" * 80)
        print()


if __name__ == "__main__":
    main()
