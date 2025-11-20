"""Seed de merchants comunes en Costa Rica."""

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.merchant import Merchant, MerchantVariant


logger = get_logger(__name__)


# Lista de merchants comunes en Costa Rica con sus variantes
COMMON_MERCHANTS = [
    {
        "nombre_normalizado": "Subway",
        "categoria_principal": "Restaurante",
        "subcategoria": "Comida Rápida",
        "tipo_negocio": "food_service",
        "que_vende": "Sándwiches, ensaladas, bebidas",
        "variantes": [
            {"nombre_raw": "SUBWAY MOMENTUM", "ciudad": "San José"},
            {"nombre_raw": "SUBWAY AMERICA FREE ZO", "ciudad": "Heredia"},
            {"nombre_raw": "SUBWAY ESCAZU", "ciudad": "Escazú"},
            {"nombre_raw": "SUBWAY MALL SAN PEDRO", "ciudad": "San José"},
        ],
    },
    {
        "nombre_normalizado": "Walmart",
        "categoria_principal": "Supermercado",
        "subcategoria": "Retail",
        "tipo_negocio": "retail",
        "que_vende": "Alimentos, productos del hogar, electrónica, ropa",
        "variantes": [
            {"nombre_raw": "WALMART SUPERCENTER", "ciudad": "Escazú"},
            {"nombre_raw": "WALMART", "ciudad": "San José"},
            {"nombre_raw": "WALMART ESCAZU", "ciudad": "Escazú"},
        ],
    },
    {
        "nombre_normalizado": "Dunkin Donuts",
        "categoria_principal": "Restaurante",
        "subcategoria": "Cafetería",
        "tipo_negocio": "food_service",
        "que_vende": "Donas, café, desayunos",
        "variantes": [
            {"nombre_raw": "DUNKIN DONUTS", "ciudad": "San José"},
            {"nombre_raw": "DUNKIN", "ciudad": "San José"},
        ],
    },
    {
        "nombre_normalizado": "Auto Mercado",
        "categoria_principal": "Supermercado",
        "subcategoria": "Premium",
        "tipo_negocio": "retail",
        "que_vende": "Alimentos, productos gourmet, vinos",
        "variantes": [
            {"nombre_raw": "AUTO MERCADO", "ciudad": "Escazú"},
            {"nombre_raw": "AUTOMERCADO", "ciudad": "San José"},
        ],
    },
    {
        "nombre_normalizado": "McDonalds",
        "categoria_principal": "Restaurante",
        "subcategoria": "Comida Rápida",
        "tipo_negocio": "food_service",
        "que_vende": "Hamburguesas, papas fritas, bebidas",
        "variantes": [
            {"nombre_raw": "MCDONALDS", "ciudad": "San José"},
            {"nombre_raw": "MC DONALDS", "ciudad": "San José"},
        ],
    },
    {
        "nombre_normalizado": "Mas X Menos",
        "categoria_principal": "Supermercado",
        "subcategoria": "Retail",
        "tipo_negocio": "retail",
        "que_vende": "Alimentos, productos del hogar",
        "variantes": [
            {"nombre_raw": "MAS X MENOS", "ciudad": "San José"},
            {"nombre_raw": "MASXMENOS", "ciudad": "San José"},
        ],
    },
    {
        "nombre_normalizado": "Starbucks",
        "categoria_principal": "Restaurante",
        "subcategoria": "Cafetería",
        "tipo_negocio": "food_service",
        "que_vende": "Café, bebidas, snacks",
        "variantes": [
            {"nombre_raw": "STARBUCKS", "ciudad": "San José"},
            {"nombre_raw": "STARBUCKS COFFEE", "ciudad": "San José"},
        ],
    },
    {
        "nombre_normalizado": "Uber",
        "categoria_principal": "Transporte",
        "subcategoria": "Rideshare",
        "tipo_negocio": "transportation",
        "que_vende": "Transporte privado",
        "variantes": [
            {"nombre_raw": "UBER", "ciudad": "San José"},
            {"nombre_raw": "UBER TRIP", "ciudad": "San José"},
        ],
    },
    {
        "nombre_normalizado": "Uber Eats",
        "categoria_principal": "Delivery",
        "subcategoria": "Comida a domicilio",
        "tipo_negocio": "food_delivery",
        "que_vende": "Servicio de entrega de comida",
        "variantes": [
            {"nombre_raw": "UBER EATS", "ciudad": "San José"},
            {"nombre_raw": "UBEREATS", "ciudad": "San José"},
        ],
    },
    {
        "nombre_normalizado": "Netflix",
        "categoria_principal": "Entretenimiento",
        "subcategoria": "Streaming",
        "tipo_negocio": "entertainment",
        "que_vende": "Streaming de películas y series",
        "variantes": [
            {"nombre_raw": "NETFLIX", "ciudad": None},
            {"nombre_raw": "NETFLIX.COM", "ciudad": None},
        ],
    },
    {
        "nombre_normalizado": "Spotify",
        "categoria_principal": "Entretenimiento",
        "subcategoria": "Música",
        "tipo_negocio": "entertainment",
        "que_vende": "Streaming de música",
        "variantes": [
            {"nombre_raw": "SPOTIFY", "ciudad": None},
            {"nombre_raw": "SPOTIFY AB", "ciudad": None},
        ],
    },
    {
        "nombre_normalizado": "Amazon",
        "categoria_principal": "E-commerce",
        "subcategoria": "Retail Online",
        "tipo_negocio": "retail",
        "que_vende": "Productos variados online",
        "variantes": [
            {"nombre_raw": "AMAZON", "ciudad": None},
            {"nombre_raw": "AMAZON.COM", "ciudad": None},
            {"nombre_raw": "AMZN", "ciudad": None},
        ],
    },
]


def seed_merchants():
    """
    Crea merchants comunes en la base de datos si no existen.

    Se ejecuta automáticamente al iniciar la aplicación.
    """
    with get_session() as session:
        # Verificar si ya existen merchants
        count = session.query(Merchant).count()
        if count > 0:
            logger.debug(f"Merchants ya existen ({count}), saltando seed")
            return

        logger.info("Creando merchants comunes...")

        for merchant_data in COMMON_MERCHANTS:
            try:
                # Crear merchant
                merchant = Merchant(
                    nombre_normalizado=merchant_data["nombre_normalizado"],
                    categoria_principal=merchant_data["categoria_principal"],
                    subcategoria=merchant_data.get("subcategoria"),
                    tipo_negocio=merchant_data["tipo_negocio"],
                    que_vende=merchant_data.get("que_vende"),
                )
                session.add(merchant)
                session.flush()  # Para obtener el ID

                # Crear variantes
                for variante_data in merchant_data["variantes"]:
                    variante = MerchantVariant(
                        merchant_id=merchant.id,
                        nombre_raw=variante_data["nombre_raw"],
                        ciudad=variante_data.get("ciudad"),
                        pais="Costa Rica",
                        confianza_match=1.0,
                    )
                    session.add(variante)

                logger.info(
                    f"Merchant creado: {merchant.nombre_normalizado} "
                    f"({len(merchant_data['variantes'])} variantes)"
                )

            except Exception as e:
                logger.error(f"Error creando merchant {merchant_data['nombre_normalizado']}: {e}")
                session.rollback()
                continue

        session.commit()
        logger.info(f"✅ {len(COMMON_MERCHANTS)} merchants comunes creados")
