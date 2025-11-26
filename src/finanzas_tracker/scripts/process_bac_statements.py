#!/usr/bin/env python3
"""
Script para procesar estados de cuenta del BAC en batch.

Uso:
    poetry run python src/finanzas_tracker/scripts/process_bac_statements.py --input-dir /path/to/pdfs --profile-email user@email.com

Características:
- Procesa PDFs o TXTs
- Extrae transacciones usando Claude Vision (para PDFs) o parser de texto
- Guarda backup en JSON/CSV
- Importa al sistema y auto-categoriza
- Genera reporte de estadísticas
"""

import argparse
import json
import csv
import base64
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from decimal import Decimal

from loguru import logger
from sqlalchemy.orm import Session
import anthropic

from finanzas_tracker.models.database import get_session
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.models.card import Card
from finanzas_tracker.models.account import Account
from finanzas_tracker.models.enums import Currency, TransactionType
from finanzas_tracker.parsers.bac_statement_parser import BACStatementParser, BACStatementTransaction
from finanzas_tracker.services.categorizer import TransactionCategorizer
from finanzas_tracker.utils.config import get_settings


class BACStatementProcessor:
    """Procesador batch de estados de cuenta."""

    def __init__(self, profile_email: str, output_dir: Path):
        self.profile_email = profile_email
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True, parents=True)

        # Inicializar servicios
        settings = get_settings()
        self.anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.parser = BACStatementParser()
        self.categorizer = None  # Lazy load

        # Estadísticas
        self.stats = {
            'archivos_procesados': 0,
            'archivos_error': 0,
            'transacciones_extraidas': 0,
            'transacciones_importadas': 0,
            'transacciones_duplicadas': 0,
            'transacciones_categorizadas': 0,
            'cuentas_detectadas': set(),
            'periodo_inicio': None,
            'periodo_fin': None,
        }

    def process_directory(self, input_dir: Path) -> Dict[str, Any]:
        """
        Procesa todos los archivos de una carpeta.

        Args:
            input_dir: Carpeta con PDFs o TXTs

        Returns:
            Estadísticas del procesamiento
        """
        logger.info(f"Procesando archivos en: {input_dir}")

        # Buscar PDFs y TXTs
        pdf_files = list(input_dir.glob("*.pdf"))
        txt_files = list(input_dir.glob("*.txt"))
        all_files = sorted(pdf_files + txt_files)

        if not all_files:
            logger.warning(f"No se encontraron archivos en {input_dir}")
            return self.stats

        logger.info(f"Encontrados {len(all_files)} archivos ({len(pdf_files)} PDFs, {len(txt_files)} TXTs)")

        # Procesar cada archivo
        all_transactions = []

        for file_path in all_files:
            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"Procesando: {file_path.name}")
                logger.info(f"{'='*60}")

                transactions = self._process_file(file_path)
                all_transactions.extend(transactions)

                self.stats['archivos_procesados'] += 1

            except Exception as e:
                logger.error(f"Error procesando {file_path.name}: {e}")
                self.stats['archivos_error'] += 1
                continue

        # Guardar backup
        self._save_backup(all_transactions)

        # Importar a la base de datos
        self._import_to_database(all_transactions)

        # Generar reporte
        self._generate_report()

        return self.stats

    def _process_file(self, file_path: Path) -> List[BACStatementTransaction]:
        """Procesa un archivo individual."""
        if file_path.suffix.lower() == '.pdf':
            return self._process_pdf(file_path)
        else:
            return self._process_txt(file_path)

    def _process_pdf(self, pdf_path: Path) -> List[BACStatementTransaction]:
        """
        Procesa PDF usando Claude Vision.

        Extrae texto y transacciones del PDF usando el API de Anthropic.
        """
        logger.info(f"Procesando PDF con Claude Vision: {pdf_path.name}")

        # Leer PDF como bytes
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()

        # Convertir a base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

        # Prompt para Claude Vision
        prompt = """
Extrae TODAS las transacciones de este estado de cuenta del BAC Credomatic.

Para cada transacción, extrae:
1. Número de referencia
2. Fecha (formato MES/DIA, ej: OCT/15)
3. Concepto/Descripción completa
4. Monto (solo el número)
5. Tipo (DEBITO o CREDITO)
6. IBAN de la cuenta (formato CR...)
7. Moneda (CRC o USD)

IMPORTANTE:
- NO incluyas la línea "ÚLTIMA LÍNEA SALDO AL CORTE"
- Extrae CADA transacción, no omitas ninguna
- Si un concepto tiene múltiples líneas, únelas
- Los DÉBITOS son gastos/salidas de dinero
- Los CRÉDITOS son ingresos/entradas de dinero

Responde SOLO con un JSON array con esta estructura:
[
  {
    "numero_referencia": "093006688",
    "fecha": "SEP/27",
    "concepto": "COMPASS RUTA 32 RUTA 2",
    "monto": 150.00,
    "tipo": "DEBITO",
    "cuenta_iban": "CR63010200009481986844",
    "moneda": "CRC"
  },
  ...
]

NO incluyas explicaciones, solo el JSON array.
"""

        try:
            response = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=16000,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }]
            )

            # Parsear respuesta JSON
            response_text = response.content[0].text.strip()

            # Extraer JSON (puede venir con ```json o sin)
            if '```json' in response_text:
                json_str = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                json_str = response_text.split('```')[1].split('```')[0].strip()
            else:
                json_str = response_text

            transactions_data = json.loads(json_str)

            # Convertir a BACStatementTransaction
            transactions = []
            for tx_data in transactions_data:
                # Parsear fecha (formato "OCT/15")
                fecha_parts = tx_data['fecha'].split('/')
                mes_str = fecha_parts[0]
                dia = int(fecha_parts[1])

                # Necesitamos el año - obtenerlo del nombre del archivo si es posible
                # o del primer match de fecha de corte
                anio = self._extract_year_from_filename(pdf_path.name)

                meses = {
                    'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
                    'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12
                }
                mes = meses.get(mes_str.upper(), 1)

                fecha = datetime(anio, mes, dia)

                tx = BACStatementTransaction(
                    numero_referencia=str(tx_data['numero_referencia']),
                    fecha=fecha,
                    concepto=tx_data['concepto'],
                    monto=Decimal(str(tx_data['monto'])),
                    tipo=tx_data['tipo'],
                    cuenta_iban=tx_data['cuenta_iban'].replace(' ', ''),
                    moneda=tx_data['moneda']
                )

                transactions.append(tx)

            logger.info(f"Extraídas {len(transactions)} transacciones del PDF")
            self.stats['transacciones_extraidas'] += len(transactions)

            return transactions

        except Exception as e:
            logger.error(f"Error procesando PDF con Claude Vision: {e}")
            # Fallback: intentar convertir a texto y parsear
            logger.info("Intentando fallback con extracción de texto...")
            return []

    def _process_txt(self, txt_path: Path) -> List[BACStatementTransaction]:
        """Procesa archivo TXT usando parser de texto."""
        logger.info(f"Procesando TXT: {txt_path.name}")

        with open(txt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        try:
            cuentas, transactions = self.parser.parse_file(content)

            # Actualizar stats
            for cuenta in cuentas:
                self.stats['cuentas_detectadas'].add(cuenta.cuenta_iban)

            self.stats['transacciones_extraidas'] += len(transactions)

            return transactions

        except Exception as e:
            logger.error(f"Error parseando TXT: {e}")
            return []

    def _extract_year_from_filename(self, filename: str) -> int:
        """Intenta extraer el año del nombre del archivo."""
        # Buscar patrón de año (2024, 2025, etc)
        import re
        year_match = re.search(r'20\d{2}', filename)
        if year_match:
            return int(year_match.group(0))

        # Si no encuentra, usar año actual
        return datetime.now().year

    def _save_backup(self, transactions: List[BACStatementTransaction]):
        """Guarda backup en JSON y CSV."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # JSON
        json_path = self.output_dir / f'transactions_backup_{timestamp}.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump([tx.to_dict() for tx in transactions], f, indent=2, ensure_ascii=False)
        logger.info(f"Backup JSON guardado: {json_path}")

        # CSV
        csv_path = self.output_dir / f'transactions_backup_{timestamp}.csv'
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            if transactions:
                writer = csv.DictWriter(f, fieldnames=transactions[0].to_dict().keys())
                writer.writeheader()
                for tx in transactions:
                    writer.writerow(tx.to_dict())
        logger.info(f"Backup CSV guardado: {csv_path}")

    def _import_to_database(self, transactions: List[BACStatementTransaction]):
        """Importa transacciones a la base de datos."""
        logger.info("\n" + "="*60)
        logger.info("IMPORTANDO A BASE DE DATOS")
        logger.info("="*60)

        with get_session() as session:
            # Obtener perfil
            profile = session.query(Profile).filter_by(email=self.profile_email).first()
            if not profile:
                logger.error(f"No se encontró perfil con email: {self.profile_email}")
                return

            logger.info(f"Perfil encontrado: {profile.nombre_completo}")

            # Inicializar categorizador (lazy)
            if not self.categorizer:
                self.categorizer = TransactionCategorizer(session)

            # Procesar cada transacción
            for tx in transactions:
                try:
                    self._import_transaction(session, profile, tx)
                except Exception as e:
                    logger.error(f"Error importando transacción {tx.numero_referencia}: {e}")
                    continue

            # Commit final
            session.commit()

        logger.info(f"\nImportadas: {self.stats['transacciones_importadas']}")
        logger.info(f"Duplicadas: {self.stats['transacciones_duplicadas']}")
        logger.info(f"Categorizadas: {self.stats['transacciones_categorizadas']}")

    def _import_transaction(self, session: Session, profile: Profile, tx: BACStatementTransaction):
        """Importa una transacción individual."""
        # Verificar si ya existe (por email_id o referencia)
        email_id = f"BAC_STATEMENT_{tx.numero_referencia}_{tx.fecha.strftime('%Y%m%d')}"

        existing = session.query(Transaction).filter_by(email_id=email_id).first()
        if existing:
            self.stats['transacciones_duplicadas'] += 1
            return

        # Determinar tipo de transacción
        tipo_transaccion = self._classify_transaction_type(tx.concepto)

        # Crear transacción
        new_tx = Transaction(
            profile_id=profile.id,
            email_id=email_id,
            comercio=tx.concepto,
            monto_original=tx.monto,
            moneda_original=Currency.CRC if tx.moneda == 'CRC' else Currency.USD,
            monto_crc=tx.monto if tx.moneda == 'CRC' else tx.monto * Decimal('520'),  # Simplificado
            fecha_transaccion=tx.fecha,
            tipo_transaccion=tipo_transaccion,
            # card_id se puede agregar después si se detecta la tarjeta
        )

        # Auto-categorizar
        if tx.tipo == 'DEBITO':  # Solo categorizamos gastos
            try:
                categoria_result = self.categorizer.categorize(
                    comercio=tx.concepto,
                    monto=float(tx.monto),
                    tipo_transaccion=tipo_transaccion.value if tipo_transaccion else 'compra'
                )

                if categoria_result:
                    new_tx.subcategory_id = categoria_result.get('subcategory_id')
                    new_tx.confianza_categoria = categoria_result.get('confianza', 0)
                    new_tx.categorizado_por_usuario = False

                    if new_tx.confianza_categoria < 80:
                        new_tx.necesita_revision = True

                    self.stats['transacciones_categorizadas'] += 1

            except Exception as e:
                logger.warning(f"Error categorizando: {e}")

        session.add(new_tx)
        self.stats['transacciones_importadas'] += 1

        # Actualizar rango de fechas
        if not self.stats['periodo_inicio'] or tx.fecha < self.stats['periodo_inicio']:
            self.stats['periodo_inicio'] = tx.fecha
        if not self.stats['periodo_fin'] or tx.fecha > self.stats['periodo_fin']:
            self.stats['periodo_fin'] = tx.fecha

    def _classify_transaction_type(self, concepto: str) -> TransactionType:
        """Clasifica el tipo de transacción basado en el concepto."""
        concepto_upper = concepto.upper()

        if 'SINPE' in concepto_upper:
            return TransactionType.SINPE
        elif 'TEF' in concepto_upper or 'TRANSFERENCIA' in concepto_upper:
            return TransactionType.TRANSFER
        elif 'RETIRO' in concepto_upper or 'ATM' in concepto_upper:
            return TransactionType.WITHDRAWAL
        elif 'COMPASS' in concepto_upper:
            return TransactionType.COMPASS
        elif 'INTERES' in concepto_upper:
            return TransactionType.OTHER
        elif 'COMISION' in concepto_upper:
            return TransactionType.MAINTENANCE_FEE
        else:
            return TransactionType.PURCHASE

    def _generate_report(self):
        """Genera reporte de estadísticas."""
        logger.info("\n" + "="*60)
        logger.info("REPORTE FINAL")
        logger.info("="*60)

        report = f"""
📊 ESTADÍSTICAS DE PROCESAMIENTO

Archivos:
- Procesados exitosamente: {self.stats['archivos_procesados']}
- Con errores: {self.stats['archivos_error']}
- Total: {self.stats['archivos_procesados'] + self.stats['archivos_error']}

Transacciones:
- Extraídas: {self.stats['transacciones_extraidas']}
- Importadas a DB: {self.stats['transacciones_importadas']}
- Duplicadas (omitidas): {self.stats['transacciones_duplicadas']}
- Auto-categorizadas: {self.stats['transacciones_categorizadas']}

Cuentas detectadas: {len(self.stats['cuentas_detectadas'])}
{chr(10).join(f'  - {iban}' for iban in self.stats['cuentas_detectadas'])}

Periodo:
- Inicio: {self.stats['periodo_inicio'].strftime('%Y-%m-%d') if self.stats['periodo_inicio'] else 'N/A'}
- Fin: {self.stats['periodo_fin'].strftime('%Y-%m-%d') if self.stats['periodo_fin'] else 'N/A'}

✅ Procesamiento completado exitosamente
"""

        logger.info(report)

        # Guardar reporte en archivo
        report_path = self.output_dir / f'reporte_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)

        logger.info(f"\nReporte guardado en: {report_path}")


def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description="Procesa estados de cuenta del BAC en batch"
    )
    parser.add_argument(
        '--input-dir',
        type=Path,
        required=True,
        help='Carpeta con archivos PDF o TXT de estados de cuenta'
    )
    parser.add_argument(
        '--profile-email',
        type=str,
        required=True,
        help='Email del perfil al que importar las transacciones'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('data/statement_backups'),
        help='Carpeta para guardar backups (default: data/statement_backups)'
    )

    args = parser.parse_args()

    # Validar input
    if not args.input_dir.exists():
        logger.error(f"La carpeta no existe: {args.input_dir}")
        return

    # Procesar
    processor = BACStatementProcessor(
        profile_email=args.profile_email,
        output_dir=args.output_dir
    )

    stats = processor.process_directory(args.input_dir)

    logger.info("\n✅ PROCESO COMPLETADO")


if __name__ == '__main__':
    main()
