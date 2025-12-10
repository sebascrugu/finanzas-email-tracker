#!/usr/bin/env python3
"""
Script para analizar todos los correos de BAC de noviembre 2025.

Objetivo: Entender todos los tipos de correos que BAC envía y asegurarnos
que el parser los maneje correctamente.

Uso:
    poetry run python scripts/analyze_bac_emails.py
"""

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from finanzas_tracker.core.logging import get_logger, setup_logging
from finanzas_tracker.services.email_fetcher import EmailFetcher

setup_logging()
logger = get_logger(__name__)


def extract_email_info(email: dict) -> dict:
    """Extrae información clave de un correo."""
    subject = email.get("subject", "")
    sender = email.get("from", {}).get("emailAddress", {}).get("address", "")
    received = email.get("receivedDateTime", "")
    body_content = email.get("body", {}).get("content", "")
    
    # Parsear el HTML
    soup = BeautifulSoup(body_content, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    
    # Detectar tipo de correo
    email_type = classify_email_type(subject, text)
    
    # Extraer datos clave según el tipo
    extracted_data = extract_data_by_type(email_type, soup, text, subject)
    
    return {
        "id": email.get("id", ""),
        "subject": subject,
        "sender": sender,
        "received": received,
        "type": email_type,
        "extracted": extracted_data,
        "text_preview": text[:500] if text else "",
    }


def classify_email_type(subject: str, text: str) -> str:
    """Clasifica el tipo de correo de BAC."""
    subject_lower = subject.lower()
    text_lower = text.lower()
    
    # Transferencia Local (enviada o recibida)
    if "transferencia local" in subject_lower or "transferencia local" in text_lower:
        if "realizó una transferencia" in text_lower:
            return "TRANSFERENCIA_ENVIADA"
        elif "recibió" in text_lower or "abono" in text_lower:
            return "TRANSFERENCIA_RECIBIDA"
        return "TRANSFERENCIA_OTRO"
    
    # Transferencia SINPE (es lo mismo que transferencia, pero el número de referencia es diferente)
    if "sinpe" in subject_lower or "sinpe" in text_lower:
        return "SINPE"  # Realmente es transferencia
    
    # Compra/Cargo
    if "notificación de transacción" in subject_lower or "notificacion de transaccion" in subject_lower:
        return "COMPRA"
    
    # Retiro sin tarjeta
    if "retiro sin tarjeta" in subject_lower:
        return "RETIRO_SIN_TARJETA"
    
    # Retiro ATM
    if "retiro" in subject_lower and "atm" in text_lower:
        return "RETIRO_ATM"
    
    # Pago de tarjeta
    if "pago" in subject_lower and ("tarjeta" in text_lower or "crédito" in text_lower):
        return "PAGO_TARJETA"
    
    # Depósito
    if "depósito" in subject_lower or "deposito" in subject_lower:
        return "DEPOSITO"
    
    # Abono/Ingreso
    if "abono" in subject_lower or "ingreso" in subject_lower:
        return "INGRESO"
    
    # Marketing/Promociones
    marketing_keywords = [
        "promoción", "promocion", "oferta", "descuento", "ganate",
        "premio", "sorteo", "marchamo", "pick up", "gamer",
    ]
    if any(kw in subject_lower for kw in marketing_keywords):
        return "MARKETING"
    
    # Configuración de cuenta
    config_keywords = [
        "cambio de pin", "cambio de clave", "afiliación", "desafiliación",
    ]
    if any(kw in subject_lower for kw in config_keywords):
        return "CONFIGURACION"
    
    return "DESCONOCIDO"


def extract_data_by_type(email_type: str, soup: BeautifulSoup, text: str, subject: str) -> dict:
    """Extrae datos específicos según el tipo de correo."""
    data = {}
    
    if email_type in ["COMPRA", "TRANSFERENCIA_ENVIADA", "TRANSFERENCIA_RECIBIDA", "SINPE"]:
        # Extraer monto
        monto_match = re.search(r"([\d.,]+)\s*(CRC|USD|₡|\$)", text)
        if monto_match:
            data["monto"] = monto_match.group(1)
            data["moneda"] = monto_match.group(2)
        
        # Extraer fecha
        fecha_match = re.search(r"(\d{2}-\d{2}-\d{4})", text)
        if fecha_match:
            data["fecha"] = fecha_match.group(1)
        
        # Extraer hora
        hora_match = re.search(r"(\d{2}:\d{2}:\d{2})", text)
        if hora_match:
            data["hora"] = hora_match.group(1)
        
        # Extraer número de referencia
        ref_match = re.search(r"referencia[:\s]+(\w+)", text, re.IGNORECASE)
        if ref_match:
            data["referencia"] = ref_match.group(1)
        
        # Para transferencias, extraer destinatario/origen
        if "TRANSFERENCIA" in email_type:
            # Buscar nombre de persona
            nombre_match = re.search(r"Estimado\(a\)\s+([A-Z_\s]+)\s*:", text)
            if nombre_match:
                data["destinatario"] = nombre_match.group(1).replace("_", " ").strip()
            
            # Buscar cuenta
            cuenta_match = re.search(r"cuenta\s+N°?\s*\*+(\d+)", text, re.IGNORECASE)
            if cuenta_match:
                data["cuenta_parcial"] = cuenta_match.group(1)
            
            # Buscar concepto
            concepto_match = re.search(r"concepto de:\s*([^\n]+)", text, re.IGNORECASE)
            if concepto_match:
                data["concepto"] = concepto_match.group(1).strip()
        
        # Para compras, extraer comercio
        if email_type == "COMPRA":
            comercio_match = re.search(r"Comercio[:\s]+([^\n]+)", text)
            if comercio_match:
                data["comercio"] = comercio_match.group(1).strip()
    
    return data


def analyze_emails(emails: list[dict]) -> dict:
    """Analiza y agrupa los correos por tipo."""
    analysis = {
        "total": len(emails),
        "by_type": defaultdict(list),
        "by_sender": defaultdict(int),
        "by_date": defaultdict(int),
        "unknown_subjects": [],
    }
    
    for email in emails:
        info = extract_email_info(email)
        analysis["by_type"][info["type"]].append(info)
        analysis["by_sender"][info["sender"]] += 1
        
        # Extraer solo la fecha (sin hora)
        if info["received"]:
            date_str = info["received"][:10]
            analysis["by_date"][date_str] += 1
        
        if info["type"] == "DESCONOCIDO":
            analysis["unknown_subjects"].append(info["subject"])
    
    return analysis


def print_analysis(analysis: dict) -> None:
    """Imprime el análisis de forma legible."""
    print("\n" + "=" * 80)
    print("📊 ANÁLISIS DE CORREOS BAC - NOVIEMBRE 2025")
    print("=" * 80)
    
    print(f"\n📬 Total de correos: {analysis['total']}")
    
    print("\n📋 POR TIPO DE CORREO:")
    print("-" * 40)
    for tipo, correos in sorted(analysis["by_type"].items(), key=lambda x: -len(x[1])):
        print(f"  {tipo}: {len(correos)}")
    
    print("\n📤 POR REMITENTE:")
    print("-" * 40)
    for sender, count in sorted(analysis["by_sender"].items(), key=lambda x: -x[1]):
        print(f"  {sender}: {count}")
    
    print("\n📅 POR FECHA:")
    print("-" * 40)
    for date, count in sorted(analysis["by_date"].items()):
        print(f"  {date}: {count}")
    
    if analysis["unknown_subjects"]:
        print("\n⚠️ ASUNTOS NO CLASIFICADOS:")
        print("-" * 40)
        for subject in analysis["unknown_subjects"][:20]:  # Mostrar máx 20
            print(f"  - {subject}")
    
    # Detalles por tipo
    print("\n" + "=" * 80)
    print("📝 DETALLES POR TIPO")
    print("=" * 80)
    
    for tipo, correos in analysis["by_type"].items():
        if correos and tipo != "MARKETING":
            print(f"\n{'='*60}")
            print(f"📌 {tipo} ({len(correos)} correos)")
            print("=" * 60)
            
            for i, email in enumerate(correos[:3]):  # Mostrar primeros 3
                print(f"\n  [{i+1}] {email['subject']}")
                print(f"      Fecha: {email['received'][:19]}")
                if email["extracted"]:
                    for k, v in email["extracted"].items():
                        print(f"      {k}: {v}")
                print(f"      Preview: {email['text_preview'][:200]}...")


def save_analysis(analysis: dict, output_path: Path) -> None:
    """Guarda el análisis en un archivo JSON."""
    # Convertir defaultdict a dict para JSON
    serializable = {
        "total": analysis["total"],
        "by_type": {k: v for k, v in analysis["by_type"].items()},
        "by_sender": dict(analysis["by_sender"]),
        "by_date": dict(analysis["by_date"]),
        "unknown_subjects": analysis["unknown_subjects"],
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n💾 Análisis guardado en: {output_path}")


def main():
    """Función principal."""
    print("🔄 Iniciando análisis de correos BAC...")
    
    # Crear el EmailFetcher
    fetcher = EmailFetcher()
    
    # Probar conexión
    if not fetcher.test_connection():
        print("❌ No se pudo conectar con Microsoft Graph API")
        print("   Ejecuta: poetry run python -c 'from finanzas_tracker.services.auth_manager import auth_manager; auth_manager.get_access_token()'")
        return
    
    # Buscar correos de BAC de los últimos 35 días (todo noviembre + algo de diciembre)
    print("\n🔍 Buscando correos de BAC...")
    emails = fetcher.fetch_emails_for_current_user(days_back=35, bank="bac")
    
    if not emails:
        print("❌ No se encontraron correos de BAC")
        return
    
    print(f"✅ Encontrados {len(emails)} correos de BAC")
    
    # Analizar los correos
    print("\n🔬 Analizando correos...")
    analysis = analyze_emails(emails)
    
    # Imprimir análisis
    print_analysis(analysis)
    
    # Guardar análisis
    output_dir = Path("data/test_fixtures")
    output_dir.mkdir(parents=True, exist_ok=True)
    save_analysis(analysis, output_dir / "bac_email_analysis_nov2025.json")
    
    print("\n✅ Análisis completado!")


if __name__ == "__main__":
    main()
