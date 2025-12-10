#!/usr/bin/env python3
"""Script de Análisis Profundo - Correos Históricos BAC.

Este script importa y analiza TODOS los correos históricos de BAC para:
1. Entender patrones de gasto de un usuario de 24 años en Costa Rica
2. Detectar tendencias del mercado costarricense
3. Generar insights profundos para el sistema de ML

Uso:
    python scripts/deep_analysis_historical.py --days 365
"""

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def fetch_bac_emails(days_back: int = 365) -> list[dict]:
    """
    Obtiene correos de BAC de los últimos N días.
    """
    from finanzas_tracker.services.email_fetcher import EmailFetcher
    
    logger.info(f"📧 Buscando correos de BAC de los últimos {days_back} días...")
    
    fetcher = EmailFetcher()
    
    try:
        # Usar el método correcto
        emails = fetcher.fetch_emails_for_current_user(
            days_back=days_back,
            bank="bac",  # Solo BAC por ahora
        )
        logger.info(f"📬 Total correos BAC encontrados: {len(emails)}")
        return emails
    except Exception as e:
        logger.error(f"Error obteniendo correos: {e}")
        return []


def parse_bac_emails(emails: list[dict]) -> list[dict]:
    """
    Parsea los correos de BAC para extraer transacciones.
    
    El BACParser espera el email completo con estructura:
    {
        "subject": "...",
        "body": {"content": "...", "contentType": "html"},
        "receivedDateTime": "...",
        ...
    }
    """
    from finanzas_tracker.parsers.bac_parser import BACParser
    
    logger.info("🔍 Parseando correos de BAC...")
    
    parser = BACParser()
    transactions = []
    
    for email in emails:
        try:
            subject = email.get("subject", "")
            
            # El parser espera el email completo (no solo el body)
            parsed = parser.parse(email)
            
            if parsed:
                # Agregar metadata del correo
                parsed["email_date"] = email.get("receivedDateTime") or email.get("date")
                parsed["email_subject"] = subject
                transactions.append(parsed)
                logger.debug(f"✓ Parseado: {parsed.get('comercio')} - {parsed.get('monto_original')}")
        except Exception as e:
            logger.debug(f"Error parseando email '{subject[:50]}': {e}")
    
    logger.info(f"✅ Transacciones extraídas: {len(transactions)}")
    return transactions


def analyze_transactions(transactions: list[dict]) -> dict:
    """
    Análisis profundo de las transacciones.
    """
    logger.info("📊 Analizando transacciones...")
    
    analysis = {
        "summary": {},
        "by_merchant": defaultdict(lambda: {"count": 0, "total": Decimal("0"), "amounts": []}),
        "by_day_of_week": defaultdict(lambda: {"count": 0, "total": Decimal("0")}),
        "by_hour": defaultdict(lambda: {"count": 0, "total": Decimal("0")}),
        "by_month": defaultdict(lambda: {"count": 0, "total": Decimal("0")}),
        "by_type": defaultdict(lambda: {"count": 0, "total": Decimal("0")}),
        "recurring": [],
        "top_merchants": [],
        "patterns": [],
    }
    
    day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    
    total_amount = Decimal("0")
    all_amounts = []
    
    for txn in transactions:
        # Campos del ParsedTransaction
        amount = Decimal(str(txn.get("monto_original", 0) or txn.get("monto", 0) or txn.get("amount", 0)))
        merchant = txn.get("comercio", "") or txn.get("merchant", "") or "DESCONOCIDO"
        merchant = merchant.upper().strip()
        
        # Fecha de la transacción (campo: fecha_transaccion)
        date_obj = txn.get("fecha_transaccion") or txn.get("email_date") or txn.get("date")
        if date_obj:
            try:
                if isinstance(date_obj, str):
                    # Intentar varios formatos
                    for fmt in ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"]:
                        try:
                            date = datetime.strptime(date_obj[:19], fmt.replace("Z", ""))
                            break
                        except ValueError:
                            continue
                    else:
                        date = datetime.now()
                else:
                    date = date_obj
                
                # Por día de la semana
                day_idx = date.weekday()
                analysis["by_day_of_week"][day_names[day_idx]]["count"] += 1
                analysis["by_day_of_week"][day_names[day_idx]]["total"] += amount
                
                # Por hora
                hour = date.hour
                analysis["by_hour"][hour]["count"] += 1
                analysis["by_hour"][hour]["total"] += amount
                
                # Por mes
                month_key = date.strftime("%Y-%m")
                analysis["by_month"][month_key]["count"] += 1
                analysis["by_month"][month_key]["total"] += amount
                
            except Exception:
                pass
        
        # Por comercio
        analysis["by_merchant"][merchant]["count"] += 1
        analysis["by_merchant"][merchant]["total"] += amount
        analysis["by_merchant"][merchant]["amounts"].append(float(amount))
        
        # Por tipo de transacción
        txn_type = txn.get("tipo", "compra")
        analysis["by_type"][txn_type]["count"] += 1
        analysis["by_type"][txn_type]["total"] += amount
        
        total_amount += amount
        all_amounts.append(float(amount))
    
    # Resumen
    analysis["summary"] = {
        "total_transactions": len(transactions),
        "total_amount": float(total_amount),
        "avg_amount": float(total_amount / len(transactions)) if transactions else 0,
        "min_amount": min(all_amounts) if all_amounts else 0,
        "max_amount": max(all_amounts) if all_amounts else 0,
    }
    
    # Top merchants
    merchants_sorted = sorted(
        analysis["by_merchant"].items(),
        key=lambda x: x[1]["total"],
        reverse=True
    )
    analysis["top_merchants"] = [
        {
            "merchant": m,
            "count": data["count"],
            "total": float(data["total"]),
            "avg": float(data["total"] / data["count"]) if data["count"] > 0 else 0,
        }
        for m, data in merchants_sorted[:30]
    ]
    
    # Detectar patrones recurrentes
    for merchant, data in analysis["by_merchant"].items():
        if data["count"] >= 3:
            amounts = data["amounts"]
            # Si los montos son consistentes (variación < 20%)
            if amounts:
                avg = sum(amounts) / len(amounts)
                variance = sum((a - avg) ** 2 for a in amounts) / len(amounts)
                std_dev = variance ** 0.5
                if avg > 0 and std_dev / avg < 0.2:
                    analysis["recurring"].append({
                        "merchant": merchant,
                        "count": data["count"],
                        "avg_amount": avg,
                        "consistency": 1 - (std_dev / avg if avg > 0 else 0),
                    })
    
    # Convertir defaultdicts a dicts regulares para JSON
    analysis["by_merchant"] = {k: {"count": v["count"], "total": float(v["total"])} 
                               for k, v in analysis["by_merchant"].items()}
    analysis["by_day_of_week"] = {k: {"count": v["count"], "total": float(v["total"])} 
                                  for k, v in analysis["by_day_of_week"].items()}
    analysis["by_hour"] = {k: {"count": v["count"], "total": float(v["total"])} 
                           for k, v in analysis["by_hour"].items()}
    analysis["by_month"] = {k: {"count": v["count"], "total": float(v["total"])} 
                            for k, v in analysis["by_month"].items()}
    analysis["by_type"] = {k: {"count": v["count"], "total": float(v["total"])} 
                           for k, v in analysis["by_type"].items()}
    
    return analysis


def generate_insights(analysis: dict) -> list[str]:
    """
    Genera insights en lenguaje natural.
    """
    insights = []
    summary = analysis["summary"]
    
    insights.append(f"📊 RESUMEN GENERAL")
    insights.append(f"  • Total transacciones: {summary['total_transactions']}")
    insights.append(f"  • Gasto total: ₡{summary['total_amount']:,.0f}")
    insights.append(f"  • Promedio por transacción: ₡{summary['avg_amount']:,.0f}")
    insights.append("")
    
    # Top 10 comercios
    insights.append("🏪 TOP 10 COMERCIOS (por gasto total)")
    for i, merchant in enumerate(analysis["top_merchants"][:10], 1):
        insights.append(
            f"  {i}. {merchant['merchant']}: "
            f"₡{merchant['total']:,.0f} ({merchant['count']} compras, "
            f"promedio ₡{merchant['avg']:,.0f})"
        )
    insights.append("")
    
    # Patrones por día de la semana
    insights.append("📅 GASTO POR DÍA DE LA SEMANA")
    day_data = sorted(analysis["by_day_of_week"].items(), 
                      key=lambda x: x[1]["total"], reverse=True)
    for day, data in day_data:
        insights.append(f"  • {day}: ₡{data['total']:,.0f} ({data['count']} transacciones)")
    insights.append("")
    
    # Horas pico
    insights.append("⏰ HORAS PICO DE GASTO")
    hour_data = sorted(analysis["by_hour"].items(), 
                       key=lambda x: x[1]["total"], reverse=True)[:5]
    for hour, data in hour_data:
        insights.append(f"  • {hour:02d}:00 - ₡{data['total']:,.0f} ({data['count']} transacciones)")
    insights.append("")
    
    # Gastos recurrentes
    if analysis["recurring"]:
        insights.append("🔄 GASTOS RECURRENTES DETECTADOS")
        for rec in sorted(analysis["recurring"], key=lambda x: x["avg_amount"], reverse=True)[:10]:
            insights.append(
                f"  • {rec['merchant']}: ~₡{rec['avg_amount']:,.0f} "
                f"({rec['count']} veces, consistencia {rec['consistency']:.0%})"
            )
        insights.append("")
    
    # Tendencia mensual
    if analysis["by_month"]:
        insights.append("📈 TENDENCIA MENSUAL")
        months = sorted(analysis["by_month"].items())
        for month, data in months[-6:]:  # Últimos 6 meses
            insights.append(f"  • {month}: ₡{data['total']:,.0f} ({data['count']} transacciones)")
    
    return insights


def save_results(analysis: dict, insights: list[str], output_dir: str = "data/analysis") -> None:
    """
    Guarda los resultados del análisis.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Guardar JSON con análisis completo
    json_path = os.path.join(output_dir, f"analysis_{timestamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"💾 Análisis guardado en: {json_path}")
    
    # Guardar insights en texto
    txt_path = os.path.join(output_dir, f"insights_{timestamp}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(insights))
    logger.info(f"📝 Insights guardados en: {txt_path}")


def main() -> None:
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(description="Análisis profundo de correos BAC históricos")
    parser.add_argument("--days", type=int, default=365, help="Días hacia atrás (max 365)")
    parser.add_argument("--output", type=str, default="data/analysis", help="Directorio de salida")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar resultados, no guardar")
    
    args = parser.parse_args()
    days = min(args.days, 365)  # Máximo 365 días
    
    print("=" * 70)
    print("🔬 ANÁLISIS PROFUNDO DE TRANSACCIONES BAC")
    print("=" * 70)
    print(f"📅 Período: últimos {days} días")
    print()
    
    # 1. Obtener correos
    emails = fetch_bac_emails(days)
    
    if not emails:
        print("❌ No se encontraron correos de BAC")
        print("Asegúrate de que:")
        print("  1. Estés autenticado con Microsoft Graph")
        print("  2. Tengas correos de BAC en tu bandeja de entrada")
        return
    
    # 2. Parsear correos
    transactions = parse_bac_emails(emails)
    
    if not transactions:
        print("⚠️ No se pudieron extraer transacciones de los correos")
        return
    
    # 3. Analizar
    analysis = analyze_transactions(transactions)
    
    # 4. Generar insights
    insights = generate_insights(analysis)
    
    # 5. Mostrar resultados
    print()
    print("=" * 70)
    for insight in insights:
        print(insight)
    print("=" * 70)
    
    # 6. Guardar
    if not args.dry_run:
        save_results(analysis, insights, args.output)
    
    print()
    print("✅ Análisis completado!")


if __name__ == "__main__":
    main()
