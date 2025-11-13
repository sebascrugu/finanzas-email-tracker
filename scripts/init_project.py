"""
Script de inicialización del proyecto.

Este script ayuda a configurar el proyecto por primera vez:
- Verifica que Poetry esté instalado
- Instala dependencias
- Crea directorios necesarios
- Verifica que el archivo .env exista
"""

from pathlib import Path
import subprocess
import sys


def check_poetry() -> bool:
    """Verifica que Poetry esté instalado."""
    try:
        subprocess.run(
            ["poetry", "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
        print("✅ Poetry está instalado")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Poetry no está instalado")
        print("   Instálalo desde: https://python-poetry.org/docs/#installation")
        return False


def install_dependencies() -> bool:
    """Instala las dependencias del proyecto."""
    print("\n📦 Instalando dependencias con Poetry...")
    try:
        subprocess.run(["poetry", "install"], check=True)
        print("✅ Dependencias instaladas correctamente")
        return True
    except subprocess.CalledProcessError:
        print("❌ Error al instalar dependencias")
        return False


def create_directories() -> None:
    """Crea los directorios necesarios."""
    print("\n📁 Creando directorios necesarios...")
    directories = ["data", "logs"]

    for directory in directories:
        path = Path(directory)
        path.mkdir(exist_ok=True)
        print(f"   ✅ {directory}/")


def check_env_file() -> bool:
    """Verifica que exista el archivo .env."""
    print("\n🔍 Verificando archivo .env...")
    env_path = Path(".env")
    env_example_path = Path(".env.example")

    if env_path.exists():
        print("✅ Archivo .env encontrado")
        return True
    print("⚠️  Archivo .env no encontrado")
    if env_example_path.exists():
        print("   Copia .env.example a .env y configura tus credenciales:")
        print("   cp .env.example .env")
    return False


def main() -> None:
    """Función principal."""
    print("=" * 60)
    print("🚀 INICIALIZANDO PROYECTO: Finanzas Email Tracker")
    print("=" * 60)

    # Verificar Poetry
    if not check_poetry():
        sys.exit(1)

    # Instalar dependencias
    if not install_dependencies():
        sys.exit(1)

    # Crear directorios
    create_directories()

    # Verificar .env
    env_exists = check_env_file()

    # Resumen
    print("\n" + "=" * 60)
    print("📋 RESUMEN")
    print("=" * 60)
    print("✅ Poetry instalado")
    print("✅ Dependencias instaladas")
    print("✅ Directorios creados")

    if env_exists:
        print("✅ Archivo .env configurado")
    else:
        print("⚠️  Falta configurar .env")

    print("\n" + "=" * 60)
    print("🎉 SIGUIENTE PASO:")
    print("=" * 60)

    if not env_exists:
        print("1. Copia y configura el archivo .env:")
        print("   cp .env.example .env")
        print("   nano .env")
        print("\n2. Inicia el dashboard:")
    else:
        print("Inicia el dashboard:")

    print("   poetry run streamlit run src/finanzas_tracker/dashboard/app.py")
    print("\n¡Éxito! 🚀")


if __name__ == "__main__":
    main()


