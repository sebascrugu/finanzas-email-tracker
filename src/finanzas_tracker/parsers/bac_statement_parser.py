"""
Parser para estados de cuenta del BAC en formato texto.

Extrae información de cuentas y transacciones desde archivos TXT o PDFs convertidos.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple
from loguru import logger


@dataclass
class BACAccountInfo:
    """Información de una cuenta del estado."""

    nombre_titular: str
    email_titular: str
    cuenta_iban: str
    moneda: str
    saldo_anterior: Decimal
    saldo_final: Decimal
    saldo_promedio: Decimal
    total_debitos: Decimal
    total_creditos: Decimal
    fecha_corte: datetime


@dataclass
class BACStatementTransaction:
    """Transacción extraída del estado de cuenta."""

    numero_referencia: str
    fecha: datetime
    concepto: str
    monto: Decimal
    tipo: str  # 'DEBITO' o 'CREDITO'
    cuenta_iban: str
    moneda: str

    def to_dict(self) -> dict:
        """Convierte a diccionario para JSON."""
        return {
            'numero_referencia': self.numero_referencia,
            'fecha': self.fecha.isoformat(),
            'concepto': self.concepto,
            'monto': float(self.monto),
            'tipo': self.tipo,
            'cuenta_iban': self.cuenta_iban,
            'moneda': self.moneda
        }


class BACStatementParser:
    """Parser para estados de cuenta del BAC."""

    def __init__(self):
        # Patrones regex
        self.pattern_fecha_corte = re.compile(r'Fecha de corte:\s*(\d{2})/([A-Z]{3})/(\d{2})')
        self.pattern_titular = re.compile(r'Nombre:\s*(.+?)(?:\n|$)')
        self.pattern_email = re.compile(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})')
        self.pattern_iban = re.compile(r'Cuenta IBAN:\s*(CR\d{2}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{2})')
        self.pattern_moneda = re.compile(r'Moneda:\s*(COLONES|U\.S\. DOLLAR|DOLARES)')

        # Patrón para el cuadro resumen
        self.pattern_resumen = re.compile(
            r'TOTAL MONTO\s+TOTAL MONTO\s+SALDO PROMEDIO\s+SALDO ANTERIOR\s+SALDO A LA FECHA\s*\n'
            r'\d+\s+([\d,]+\.\d{2})\s+\d+\s+([\d,]+\.\d{2})\s+([\d,\-]+\.\d{2})\s+([\d,\-]+\.\d{2})\s+([\d,]+\.\d{2})'
        )

        # Meses en español a número
        self.meses = {
            'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
            'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12
        }

    def parse_file(self, file_content: str) -> Tuple[List[BACAccountInfo], List[BACStatementTransaction]]:
        """
        Parsea el contenido completo de un estado de cuenta.

        Args:
            file_content: Contenido del archivo en texto

        Returns:
            Tupla de (cuentas, transacciones)
        """
        logger.info("Iniciando parseo de estado de cuenta BAC")

        # Extraer fecha de corte (para el año)
        fecha_corte = self._extract_fecha_corte(file_content)
        if not fecha_corte:
            logger.error("No se pudo extraer fecha de corte del estado")
            raise ValueError("No se encontró fecha de corte en el estado")

        logger.info(f"Fecha de corte: {fecha_corte}")

        # Extraer nombre titular
        titular = self._extract_titular(file_content)

        # Extraer email
        email = self._extract_email(file_content)

        # Dividir el archivo por cuentas (cada cuenta tiene su propio IBAN)
        secciones_cuenta = self._split_by_accounts(file_content)

        cuentas = []
        transacciones = []

        for seccion in secciones_cuenta:
            # Extraer info de la cuenta
            cuenta_info = self._parse_account_info(seccion, titular, email, fecha_corte)
            if cuenta_info:
                cuentas.append(cuenta_info)

                # Extraer transacciones de esta cuenta
                txs = self._parse_transactions(seccion, cuenta_info.cuenta_iban,
                                               cuenta_info.moneda, fecha_corte.year)
                transacciones.extend(txs)

        logger.info(f"Parseadas {len(cuentas)} cuentas y {len(transacciones)} transacciones")

        return cuentas, transacciones

    def _extract_fecha_corte(self, content: str) -> Optional[datetime]:
        """Extrae la fecha de corte del estado."""
        match = self.pattern_fecha_corte.search(content)
        if match:
            dia, mes_str, anio = match.groups()
            mes = self.meses.get(mes_str.upper())
            if mes:
                # Asume 20XX para años de 2 dígitos
                anio_completo = 2000 + int(anio)
                return datetime(anio_completo, mes, int(dia))
        return None

    def _extract_titular(self, content: str) -> str:
        """Extrae el nombre del titular."""
        match = self.pattern_titular.search(content)
        if match:
            return match.group(1).strip()
        return "Titular desconocido"

    def _extract_email(self, content: str) -> str:
        """Extrae el email del titular."""
        match = self.pattern_email.search(content)
        if match:
            return match.group(1)
        return ""

    def _split_by_accounts(self, content: str) -> List[str]:
        """Divide el contenido por cuentas usando IBAN como delimitador."""
        # Buscar todas las ocurrencias de "Cuenta IBAN:"
        secciones = re.split(r'(?=Cuenta IBAN:)', content)
        # Filtrar secciones vacías
        return [s for s in secciones if 'Cuenta IBAN:' in s]

    def _parse_account_info(self, seccion: str, titular: str, email: str,
                           fecha_corte: datetime) -> Optional[BACAccountInfo]:
        """Extrae información de una cuenta."""
        # IBAN
        iban_match = self.pattern_iban.search(seccion)
        if not iban_match:
            return None

        iban = iban_match.group(1).replace(' ', '')

        # Moneda
        moneda_match = self.pattern_moneda.search(seccion)
        if not moneda_match:
            return None

        moneda_raw = moneda_match.group(1)
        moneda = 'CRC' if 'COLON' in moneda_raw else 'USD'

        # Resumen (saldos y totales)
        resumen_match = self.pattern_resumen.search(seccion)
        if not resumen_match:
            logger.warning(f"No se encontró cuadro resumen para cuenta {iban}")
            return None

        total_debitos = Decimal(resumen_match.group(1).replace(',', ''))
        total_creditos = Decimal(resumen_match.group(2).replace(',', ''))
        saldo_promedio = Decimal(resumen_match.group(3).replace(',', ''))
        saldo_anterior = Decimal(resumen_match.group(4).replace(',', ''))
        saldo_final = Decimal(resumen_match.group(5).replace(',', ''))

        return BACAccountInfo(
            nombre_titular=titular,
            email_titular=email,
            cuenta_iban=iban,
            moneda=moneda,
            saldo_anterior=saldo_anterior,
            saldo_final=saldo_final,
            saldo_promedio=saldo_promedio,
            total_debitos=total_debitos,
            total_creditos=total_creditos,
            fecha_corte=fecha_corte
        )

    def _parse_transactions(self, seccion: str, iban: str, moneda: str,
                           anio: int) -> List[BACStatementTransaction]:
        """Extrae transacciones de una sección de cuenta."""
        transacciones = []

        # Buscar bloque de transacciones (desde NO. REFERENCIA hasta ÚLTIMA LÍNEA)
        tx_block_pattern = re.compile(
            r'NO\. REFERENCIA\s+FECHA\s+CONCEPTO\s+DÉBITOS\s+CRÉDITOS\s*\n(.*?)(?=ÚLTIMA LÍNEA|SERVICIO AL CLIENTE)',
            re.DOTALL
        )

        tx_block_match = tx_block_pattern.search(seccion)
        if not tx_block_match:
            logger.warning(f"No se encontró bloque de transacciones para {iban}")
            return transacciones

        tx_block = tx_block_match.group(1)

        # Patrón para cada línea de transacción
        # Formato: REFERENCIA FECHA CONCEPTO [DEBITO] [CREDITO]
        tx_pattern = re.compile(
            r'^(\d+)\s+'  # Número de referencia
            r'([A-Z]{3})/(\d{2})\s+'  # Fecha (MES/DIA)
            r'(.+?)\s+'  # Concepto (captura hasta encontrar monto)
            r'([\d,]+\.\d{2})?(?:\s+([\d,]+\.\d{2}))?$',  # Débito y/o Crédito
            re.MULTILINE
        )

        for match in tx_pattern.finditer(tx_block):
            referencia = match.group(1)
            mes_str = match.group(2)
            dia = match.group(3)
            concepto = match.group(4).strip()
            debito = match.group(5)
            credito = match.group(6)

            # Convertir fecha
            mes = self.meses.get(mes_str.upper())
            if not mes:
                logger.warning(f"Mes inválido: {mes_str}")
                continue

            fecha = datetime(anio, mes, int(dia))

            # Determinar tipo y monto
            if debito:
                tipo = 'DEBITO'
                monto = Decimal(debito.replace(',', ''))
            elif credito:
                tipo = 'CREDITO'
                monto = Decimal(credito.replace(',', ''))
            else:
                logger.warning(f"Transacción sin monto: {referencia}")
                continue

            tx = BACStatementTransaction(
                numero_referencia=referencia,
                fecha=fecha,
                concepto=concepto,
                monto=monto,
                tipo=tipo,
                cuenta_iban=iban,
                moneda=moneda
            )

            transacciones.append(tx)

        logger.info(f"Extraídas {len(transacciones)} transacciones de cuenta {iban}")
        return transacciones


def parse_statement_file(file_path: str) -> Tuple[List[BACAccountInfo], List[BACStatementTransaction]]:
    """
    Función helper para parsear un archivo de estado de cuenta.

    Args:
        file_path: Ruta al archivo TXT o PDF (convertido a texto)

    Returns:
        Tupla de (cuentas, transacciones)
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    parser = BACStatementParser()
    return parser.parse_file(content)
