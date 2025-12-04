#!/usr/bin/env python3
"""
Script para buscar TODOS los correos de BAC sin ningún filtro de marketing.

Objetivo: Encontrar las transferencias que podrían estar siendo filtradas.
"""

from datetime import datetime, timedelta

from finanzas_tracker.core.logging import get_logger, setup_logging
from finanzas_tracker.services.auth_manager import auth_manager

setup_logging()
logger = get_logger(__name__)

# Remitentes de BAC
BAC_SENDERS = [
    "notificacion@notificacionesbaccr.com",
    "alerta@baccredomatic.com",
    "servicio_al_cliente@baccredomatic.cr",
    "servicio-cliente@aviso.infobaccredomatic.com",
    "info@info.baccredomatic.net",
]


def main():
    """Buscar todos los correos de BAC sin filtro."""
    print("🔄 Buscando TODOS los correos de BAC (sin filtro de marketing)...\n")
    
    # Obtener token
    token = auth_manager.get_access_token()
    if not token:
        print("❌ No se pudo obtener token de acceso")
        return
    
    import requests
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Calcular fecha de hace 35 días
    start_date = datetime.utcnow() - timedelta(days=35)
    start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Construir filtro SOLO por remitente y fecha
    sender_filter = " or ".join([f"from/emailAddress/address eq '{s}'" for s in BAC_SENDERS])
    filter_query = f"receivedDateTime ge {start_date_str} and ({sender_filter})"
    
    params = {
        "$filter": filter_query,
        "$top": 100,
        "$select": "id,subject,receivedDateTime,from",
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
    
    print(f"📬 Total de correos de BAC: {len(emails)}")
    print("\n" + "=" * 80)
    print("📋 LISTA DE TODOS LOS CORREOS")
    print("=" * 80)
    
    # Categorizar
    transferencias = []
    compras = []
    retiros = []
    pagos = []
    marketing = []
    otros = []
    
    for email in emails:
        subject = email.get("subject", "")
        subject_lower = subject.lower()
        sender = email.get("from", {}).get("emailAddress", {}).get("address", "")
        received = email.get("receivedDateTime", "")[:16].replace("T", " ")
        
        # Clasificar
        if "transferencia" in subject_lower:
            transferencias.append((received, subject, sender))
        elif "transacción" in subject_lower or "transaccion" in subject_lower:
            compras.append((received, subject, sender))
        elif "retiro" in subject_lower:
            retiros.append((received, subject, sender))
        elif "pago" in subject_lower:
            pagos.append((received, subject, sender))
        elif any(kw in subject_lower for kw in ["promoción", "promocion", "oferta", "descuento", "ganate", "premio", "marchamo", "festejamos", "gamer"]):
            marketing.append((received, subject, sender))
        else:
            otros.append((received, subject, sender))
    
    # Imprimir por categoría
    print(f"\n🔄 TRANSFERENCIAS ({len(transferencias)}):")
    for received, subject, sender in transferencias:
        print(f"  [{received}] {subject}")
    
    print(f"\n🛒 COMPRAS ({len(compras)}):")
    for received, subject, sender in compras[:5]:  # Solo primeras 5
        print(f"  [{received}] {subject}")
    if len(compras) > 5:
        print(f"  ... y {len(compras) - 5} más")
    
    print(f"\n💵 RETIROS ({len(retiros)}):")
    for received, subject, sender in retiros:
        print(f"  [{received}] {subject}")
    
    print(f"\n💳 PAGOS ({len(pagos)}):")
    for received, subject, sender in pagos:
        print(f"  [{received}] {subject}")
    
    print(f"\n📢 MARKETING ({len(marketing)}):")
    for received, subject, sender in marketing:
        print(f"  [{received}] {subject}")
    
    print(f"\n❓ OTROS ({len(otros)}):")
    for received, subject, sender in otros:
        print(f"  [{received}] {subject}")
    
    # Resumen
    print("\n" + "=" * 80)
    print("📊 RESUMEN")
    print("=" * 80)
    print(f"  Transferencias: {len(transferencias)}")
    print(f"  Compras: {len(compras)}")
    print(f"  Retiros: {len(retiros)}")
    print(f"  Pagos: {len(pagos)}")
    print(f"  Marketing: {len(marketing)}")
    print(f"  Otros: {len(otros)}")
    print(f"  TOTAL: {len(emails)}")


if __name__ == "__main__":
    main()
