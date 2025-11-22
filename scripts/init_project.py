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
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_dependencies() -> bool:
    """Instala las dependencias del proyecto."""
    try:
        subprocess.run(["poetry", "install"], check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def create_directories() -> None:
    """Crea los directorios necesarios."""
    directories = ["data", "logs"]

    for directory in directories:
        path = Path(directory)
        path.mkdir(exist_ok=True)


def check_env_file() -> bool:
    """Verifica que exista el archivo .env."""
    env_path = Path(".env")
    env_example_path = Path(".env.example")

    if env_path.exists():
        return True
    if env_example_path.exists():
        pass
    return False


def main() -> None:
    """Función principal."""

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

    if env_exists:
        pass
    else:
        pass

    if not env_exists:
        pass
    else:
        pass


if __name__ == "__main__":
    main()
