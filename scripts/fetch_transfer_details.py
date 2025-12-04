#!/usr/bin/env python3
"""
Script para obtener el contenido completo de las transferencias de BAC.
"""

from datetime import datetime, timedelta

from finanzas_tracker.core.logging import get_logger, setup_logging
from finanzas_tracker.services.auth_manager import auth_manager

setup_logging()
logger = get_logger(__name__)


def main():
    """Obtener contenido de transferencias."""
    print("🔄 Buscando transferencias de BAC...\n")
    
    import requests
    
    token = auth_manager.get_access_token()
    if not token:
        print("❌ No se pudo obtener token de acceso")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Buscar correos con "transferencia" en el asunto
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
        print(response.text)
        return
    
    data = response.json()
    emails = data.get("value", [])
    
    print(f"📬 Encontradas {len(emails)} transferencias\n")
    
    from bs4 import BeautifulSoup
    
    for i, email in enumerate(emails[:5]):  # Solo las primeras 5
        subject = email.get("subject", "")
        received = email.get("receivedDateTime", "")[:16]
        body_html = email.get("body", {}).get("content", "")
        
        # Extraer texto
        soup = BeautifulSoup(body_html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        
        print("=" * 80)
        print(f"📧 [{i+1}] {subject}")
        print(f"📅 Fecha: {received}")
        print("-" * 80)
        print("CONTENIDO:")
        print("-" * 80)
        # Mostrar las primeras líneas relevantes
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines[:30]:
            print(line)
        print("=" * 80)
        print("\n")


if __name__ == "__main__":
    main()
