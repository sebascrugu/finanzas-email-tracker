#!/usr/bin/env python3
"""
Script para analizar correos con monto = 0 (pre-autorizaciones).
"""

from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from finanzas_tracker.core.logging import setup_logging
from finanzas_tracker.services.auth_manager import auth_manager

setup_logging()


def main():
    """Analizar correos con monto = 0."""
    print("🔄 Buscando correos de monto cero...\n")
    
    import requests
    
    token = auth_manager.get_access_token()
    if not token:
        print("❌ No se pudo obtener token de acceso")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Buscar correos específicos
    start_date = datetime.now() - timedelta(days=60)
    start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Buscar correos de Amazon y Visa con monto problemático
    search_terms = ["AMAZON", "Visa", "OPENAI", "ANTHROPIC"]
    
    for term in search_terms:
        params = {
            "$filter": f"receivedDateTime ge {start_date_str} and contains(subject, '{term}')",
            "$top": 3,
            "$select": "id,subject,receivedDateTime,from,body",
            "$orderby": "receivedDateTime desc",
        }
        
        response = requests.get(
            "https://graph.microsoft.com/v1.0/me/messages",
            headers=headers,
            params=params,
        )
        
        if response.status_code != 200:
            continue
        
        data = response.json()
        emails = data.get("value", [])
        
        for email in emails:
            subject = email.get("subject", "")
            
            # Solo los que tienen "0.00" en el contenido
            body_html = email.get("body", {}).get("content", "")
            
            if "0.00" in body_html or "0,00" in body_html:
                soup = BeautifulSoup(body_html, "html.parser")
                text = soup.get_text(separator="\n", strip=True)
                
                print("=" * 80)
                print(f"📧 {subject}")
                print("-" * 80)
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                for line in lines[:25]:
                    print(f"  {line}")
                print("=" * 80)
                print("\n")
                break  # Solo mostrar uno por término


if __name__ == "__main__":
    main()
