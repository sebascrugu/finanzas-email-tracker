"""
Constantes globales del sistema.

Este módulo centraliza todos los valores mágicos y thresholds usados
en la aplicación para facilitar ajustes y mantenimiento.
"""

# ============================================================================
# CATEGORIZACIÓN AUTOMÁTICA
# ============================================================================

# Confianza mínima para auto-categorizar sin revisión manual
AUTO_CATEGORIZE_CONFIDENCE_THRESHOLD = 80

# Scores de confianza por tipo de match
HIGH_CONFIDENCE_SCORE = 90  # Match perfecto o aprendido del historial
MEDIUM_CONFIDENCE_SCORE = 75  # Match por keyword
LOW_CONFIDENCE_SCORE = 60  # Match ambiguo

# Longitud mínima de keyword para alta confianza
KEYWORD_MIN_LENGTH_FOR_HIGH_CONFIDENCE = 5

# Número mínimo de matches históricos para considerar patrón
MIN_HISTORICAL_MATCHES_FOR_PATTERN = 3

# ============================================================================
# PRESUPUESTO Y ALERTAS
# ============================================================================

# Thresholds de presupuesto (porcentaje gastado)
BUDGET_EXCEEDED_THRESHOLD = 100  # Rojo: presupuesto excedido
BUDGET_WARNING_THRESHOLD = 90  # Amarillo: advertencia
BUDGET_CAUTION_THRESHOLD = 75  # Naranja: precaución

# Regla 50/30/20
BUDGET_RULE_NECESSITIES = 50  # % para necesidades
BUDGET_RULE_WANTS = 30  # % para gustos
BUDGET_RULE_SAVINGS = 20  # % para ahorros

# ============================================================================
# MERCHANT NORMALIZATION
# ============================================================================

# Confianza mínima para match automático de merchant
MERCHANT_MATCH_CONFIDENCE_THRESHOLD = 85

# Palabras de ruido para normalización (ya definidas en merchant_service.py)
# Se mantienen en merchant_service.py por ser específicas de ese servicio

# ============================================================================
# EXCHANGE RATES
# ============================================================================

# Días de cache para tipos de cambio
EXCHANGE_RATE_CACHE_DAYS = 7

# Tipo de cambio por defecto (fallback)
DEFAULT_EXCHANGE_RATE_USD_TO_CRC = 530.0

# ============================================================================
# PAGINACIÓN Y LÍMITES
# ============================================================================

# Número máximo de transacciones a mostrar por página
MAX_TRANSACTIONS_PER_PAGE = 50

# Número máximo de resultados en búsquedas
MAX_SEARCH_RESULTS = 100

# Número de días para considerar transacción "reciente"
RECENT_TRANSACTION_DAYS = 7

# ============================================================================
# VALIDACIÓN
# ============================================================================

# Monto mínimo permitido para transacciones
# Nota: Usamos 0.01 para permitir transacciones pequeñas (ej: Amazon Prime $0.99)
# Las pre-autorizaciones ($0.00) se filtran aparte en el parser
MIN_TRANSACTION_AMOUNT = 0.01

# Monto máximo permitido para transacciones (en CRC)
MAX_TRANSACTION_AMOUNT = 100_000_000.0  # 100 millones

# Monedas soportadas
# CRC = Colones, USD = Dólares, CAD = Dólares Canadienses, EUR = Euros
SUPPORTED_CURRENCIES = ["CRC", "USD", "CAD", "EUR"]

# ============================================================================
# RETRY Y TIMEOUTS
# ============================================================================

# Número de reintentos para APIs externas
API_MAX_RETRIES = 3

# Tiempo de espera entre reintentos (segundos)
API_RETRY_DELAY = 2

# Timeout para llamadas HTTP (segundos)
HTTP_REQUEST_TIMEOUT = 30

# ============================================================================
# LOGGING Y DEBUGGING
# ============================================================================

# Nivel de log por defecto
DEFAULT_LOG_LEVEL = "INFO"

# Número de líneas de contexto en errores
ERROR_CONTEXT_LINES = 5
