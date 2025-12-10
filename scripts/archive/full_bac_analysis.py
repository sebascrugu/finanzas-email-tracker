#!/usr/bin/env python3
"""
Script para analizar TODOS los correos de BAC y verificar que el parser los maneje.

Este es el test definitivo para asegurar que no se pierda ningún tipo de correo.
"""

from datetime import datetime, timedelta
from collections import defaultdict
import unicodedata

from bs4 import BeautifulSoup

from finanzas_tracker.core.logging import setup_logging
from finanzas_tracker.parsers.bac_parser import BACParser
from finanzas_tracker.services.auth_manager import auth_manager

setup_logging()


def normalize_text(text: str) -> str:
    """Normaliza texto Unicode a forma NFC para comparaciones consistentes."""
    return unicodedata.normalize("NFC", text)

# Remitentes de BAC
BAC_SENDERS = [
    "notificacion@notificacionesbaccr.com",
    "alerta@baccredomatic.com",
    "servicio_al_cliente@baccredomatic.cr",
    "servicio-cliente@aviso.infobaccredomatic.com",
    "info@info.baccredomatic.net",
]


def main():
    """Analizar TODOS los correos de BAC."""
    print("🔄 Analizando TODOS los correos de BAC...\n")
    
    import requests
    
    token = auth_manager.get_access_token()
    if not token:
        print("❌ No se pudo obtener token de acceso")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Buscar TODOS los correos de BAC de los últimos 60 días
    start_date = datetime.now() - timedelta(days=60)
    start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    sender_filter = " or ".join([f"from/emailAddress/address eq '{s}'" for s in BAC_SENDERS])
    filter_query = f"receivedDateTime ge {start_date_str} and ({sender_filter})"
    
    params = {
        "$filter": filter_query,
        "$top": 200,  # Obtener todos
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
    
    print(f"📬 Total de correos de BAC: {len(emails)}\n")
    
    parser = BACParser()
    
    # Estadísticas
    stats = {
        "total": len(emails),
        "parseados": 0,
        "fallidos": 0,
        "marketing": 0,
        "config": 0,
        "pre_auth": 0,  # Pre-autorizaciones ($0)
        "por_tipo": defaultdict(int),
        "errores": [],
    }
    
    # Palabras clave de marketing
    marketing_keywords = [
        "promoción", "promocion", "oferta", "descuento", "ganate",
        "premio", "sorteo", "marchamo", "pick up", "gamer", "black friday",
        "beneficio", "exclusivo", "accedé", "conocé", "emergencia",
        "inscripción de promoción", "inscripcion de promocion",
        "crédito preaprobado", "credito preaprobado", "te respaldamos",
        "amex tiene para vos", "entrada gratis", "ventajas que se ven",
        "invertí en vos", "no consumís tus datos", "ela taubert", "grammy",
        "elegí tu auto",
    ]
    
    # Palabras clave de configuración (no son transacciones)
    config_keywords = [
        "cambio de pin", "afiliación", "desafiliación", "activación",
        "bac credomatic le informa", "afiliacion", "desafiliacion",
        "activacion de transferencias",
        "notificación de afiliación", "notificación de desafiliación",
    ]
    
    print("=" * 80)
    print("📊 PROCESANDO CORREOS...")
    print("=" * 80)
    
    for email in emails:
        subject = email.get("subject", "")
        # Normalizar Unicode para manejar NFC vs NFD
        subject_lower = normalize_text(subject.lower())
        sender = email.get("from", {}).get("emailAddress", {}).get("address", "")
        received = email.get("receivedDateTime", "")[:16]
        
        # Detectar marketing
        is_marketing = any(kw in subject_lower for kw in marketing_keywords)
        is_config = any(kw in subject_lower for kw in config_keywords)
        
        if is_marketing:
            stats["marketing"] += 1
            print(f"📢 [MARKETING] {subject[:60]}...")
            continue
        
        if is_config:
            stats["config"] += 1
            print(f"⚙️  [CONFIG] {subject[:60]}...")
            continue
        
        # Intentar parsear
        result = parser.parse(email)
        
        if result:
            stats["parseados"] += 1
            tipo = result.get("tipo_transaccion", "desconocido")
            stats["por_tipo"][tipo] += 1
            monto = result.get("monto_original", 0)
            moneda = result.get("moneda_original", "")
            print(f"✅ [{tipo.upper()}] {moneda} {monto:,.2f} - {subject[:50]}...")
        else:
            # Verificar si fue una pre-autorización ($0) ignorada
            body_html = email.get("body", {}).get("content", "")
            if "USD .00" in body_html or "CRC .00" in body_html or "USD 0.00" in body_html or "CAD .00" in body_html:
                stats["pre_auth"] += 1
                print(f"🔒 [PRE-AUTH] {subject[:60]}...")
            # Verificar si fue un aviso de configuración ignorado por el parser
            elif any(kw in subject_lower for kw in ["aviso bac", "activación", "afiliación", "desafiliación"]):
                stats["config"] += 1
                print(f"⚙️  [CONFIG-PARSER] {subject[:60]}...")
            else:
                stats["fallidos"] += 1
                stats["errores"].append({
                    "subject": subject,
                    "sender": sender,
                    "received": received,
                })
                print(f"❌ [FALLIDO] {subject[:60]}...")
    
    # Resumen final
    print("\n" + "=" * 80)
    print("📊 RESUMEN FINAL")
    print("=" * 80)
    
    print(f"\n📬 Total correos BAC: {stats['total']}")
    print(f"✅ Parseados correctamente: {stats['parseados']}")
    print(f"📢 Marketing filtrados: {stats['marketing']}")
    print(f"⚙️  Config filtrados: {stats['config']}")
    print(f"🔒 Pre-autorizaciones ($0): {stats['pre_auth']}")
    print(f"❌ Fallidos: {stats['fallidos']}")
    
    # Calcular tasa de éxito (transacciones reales)
    transacciones_reales = stats['parseados'] + stats['fallidos']
    if transacciones_reales > 0:
        tasa_exito = (stats['parseados'] / transacciones_reales) * 100
        print(f"\n📈 Tasa de éxito (transacciones reales): {tasa_exito:.1f}%")
    
    # Tasa de cobertura total (incluyendo pre-auth ignoradas correctamente)
    correos_procesados = stats['parseados'] + stats['pre_auth']
    correos_transaccionales = stats['parseados'] + stats['pre_auth'] + stats['fallidos']
    if correos_transaccionales > 0:
        cobertura_total = (correos_procesados / correos_transaccionales) * 100
        print(f"🎯 Cobertura total (incluyendo pre-auth): {correos_procesados}/{correos_transaccionales} = {cobertura_total:.1f}%")
    
    print(f"\n📋 POR TIPO DE TRANSACCIÓN:")
    for tipo, count in sorted(stats["por_tipo"].items(), key=lambda x: -x[1]):
        print(f"   {tipo}: {count}")
    
    if stats["errores"]:
        print(f"\n⚠️  CORREOS NO PARSEADOS ({len(stats['errores'])}):")
        for error in stats["errores"][:10]:  # Mostrar máx 10
            print(f"   - {error['subject'][:70]}")
            print(f"     Fecha: {error['received']}, Remitente: {error['sender']}")


if __name__ == "__main__":
    main()
