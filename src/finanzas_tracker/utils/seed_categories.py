"""Utilidad para crear las categorías y subcategorías iniciales."""

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.category import Category, Subcategory

logger = get_logger(__name__)


def seed_categories() -> None:
    """
    Crea las categorías y subcategorías iniciales en la base de datos.

    Categorías principales:
    - Necesidades (60% recomendado)
    - Gustos (25% recomendado)
    - Ahorros (15% recomendado)
    """
    with get_session() as session:
        # Verificar si ya existen categorías
        existing = session.query(Category).count()
        if existing > 0:
            logger.info(f"Ya existen {existing} categorías, omitiendo seed")
            return

        logger.info("Creando categorías y subcategorías iniciales...")

        # 1. NECESIDADES
        cat_necesidades = Category(
            tipo="necesidades",
            nombre="Necesidades",
            descripcion="Gastos esenciales para vivir (transporte, trabajo, personal)",
            icono="💰",
        )
        session.add(cat_necesidades)
        session.flush()  # Para obtener el ID

        # Subcategorías de Necesidades
        subcats_necesidades = [
            Subcategory(
                category_id=cat_necesidades.id,
                nombre="Transporte",
                descripcion="Gasolina, seguro del carro, mantenimiento, lavados",
                icono="🚗",
                keywords="gasolina,seguro,carro,vehiculo,lavado,mantenimiento,autopista,peaje",
            ),
            Subcategory(
                category_id=cat_necesidades.id,
                nombre="Trabajo",
                descripcion="Almuerzos en la oficina, transporte al trabajo",
                icono="💼",
                keywords="almuerzo,oficina,trabajo,comida trabajo",
            ),
            Subcategory(
                category_id=cat_necesidades.id,
                nombre="Personal",
                descripcion="Corte de pelo, farmacia, productos de higiene",
                icono="💇",
                keywords="corte pelo,barberia,peluqueria,farmacia,medicina,higiene,salud",
            ),
            Subcategory(
                category_id=cat_necesidades.id,
                nombre="Vivienda",
                descripcion="Alquiler, servicios (agua, luz, internet)",
                icono="🏠",
                keywords="alquiler,agua,luz,electricidad,internet,cable,servicios",
            ),
            Subcategory(
                category_id=cat_necesidades.id,
                nombre="Supermercado",
                descripcion="Comida del hogar, productos básicos",
                icono="🛒",
                keywords="automercado,walmart,pricesmart,supermercado,mas x menos",
            ),
        ]
        session.add_all(subcats_necesidades)

        # 2. GUSTOS
        cat_gustos = Category(
            tipo="gustos",
            nombre="Gustos",
            descripcion="Gastos discrecionales (comida, entretenimiento, shopping)",
            icono="🎮",
        )
        session.add(cat_gustos)
        session.flush()

        # Subcategorías de Gustos
        subcats_gustos = [
            Subcategory(
                category_id=cat_gustos.id,
                nombre="Comida Social",
                descripcion="Salidas a restaurantes, cafés con amigos",
                icono="🍔",
                keywords="restaurante,cafe,starbucks,dunkin,mcdonalds,burger,pizza,sushi,comida rapida",
            ),
            Subcategory(
                category_id=cat_gustos.id,
                nombre="Entretenimiento",
                descripcion="Cine, streaming, videojuegos, apuestas",
                icono="🎬",
                keywords="cine,netflix,spotify,apple,xbox,playstation,steam,bet365,apuestas,juegos",
            ),
            Subcategory(
                category_id=cat_gustos.id,
                nombre="Shopping",
                descripcion="Ropa, zapatos, accesorios, electrónica",
                icono="👕",
                keywords="ropa,zapatos,tienda,mall,electronics,tecnologia,amazon",
            ),
            Subcategory(
                category_id=cat_gustos.id,
                nombre="Hobbies",
                descripcion="Actividades recreativas, deportes, cursos",
                icono="🎨",
                keywords="deporte,gym,curso,hobby,libro,arte",
            ),
        ]
        session.add_all(subcats_gustos)

        # 3. AHORROS
        cat_ahorros = Category(
            tipo="ahorros",
            nombre="Ahorros",
            descripcion="Ahorro regular, inversiones, fondos de emergencia",
            icono="💎",
        )
        session.add(cat_ahorros)
        session.flush()

        # Subcategorías de Ahorros
        subcats_ahorros = [
            Subcategory(
                category_id=cat_ahorros.id,
                nombre="Ahorro Regular",
                descripcion="Ahorro mensual para emergencias o metas",
                icono="🏦",
                keywords="ahorro,transferencia ahorro,cuenta ahorro",
            ),
            Subcategory(
                category_id=cat_ahorros.id,
                nombre="Inversiones",
                descripcion="Inversiones en fondos, acciones, criptomonedas",
                icono="📈",
                keywords="inversion,bolsa,cripto,bitcoin,acciones",
            ),
            Subcategory(
                category_id=cat_ahorros.id,
                nombre="Metas",
                descripcion="Ahorro para metas específicas (marchamo, vacaciones)",
                icono="🎯",
                keywords="meta,marchamo,vacaciones,viaje",
            ),
        ]
        session.add_all(subcats_ahorros)

        # Commit de todo
        session.commit()

        total_subcats = (
            len(subcats_necesidades) + len(subcats_gustos) + len(subcats_ahorros)
        )
        logger.success(
            f"✅ Creadas 3 categorías principales y {total_subcats} subcategorías"
        )


if __name__ == "__main__":
    seed_categories()

