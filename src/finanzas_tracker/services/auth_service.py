"""Servicio de autenticación JWT."""

__all__ = ["AuthService", "auth_service"]

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.config.settings import settings
from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.user import User

logger = get_logger(__name__)


class AuthService:
    """
    Servicio para autenticación y gestión de usuarios.

    Maneja:
    - Registro de usuarios
    - Login (validación de credenciales)
    - Generación de tokens JWT
    - Validación de tokens JWT
    - Hash de passwords con bcrypt
    """

    def __init__(self) -> None:
        """Inicializa el servicio de autenticación."""
        self.secret_key = settings.jwt_secret_key
        self.algorithm = settings.jwt_algorithm
        self.expire_minutes = settings.jwt_access_token_expire_minutes
        logger.info("AuthService inicializado")

    # =========================================================================
    # PASSWORD HASHING
    # =========================================================================

    def hash_password(self, password: str) -> str:
        """
        Hashea un password con bcrypt.

        Args:
            password: Password en texto plano

        Returns:
            Hash bcrypt del password
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verifica un password contra su hash.

        Args:
            plain_password: Password en texto plano
            hashed_password: Hash bcrypt almacenado

        Returns:
            True si coincide, False si no
        """
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )

    # =========================================================================
    # JWT TOKENS
    # =========================================================================

    def create_access_token(
        self,
        user_id: str,
        email: str,
        expires_delta: timedelta | None = None,
    ) -> str:
        """
        Crea un token JWT de acceso.

        Args:
            user_id: ID del usuario
            email: Email del usuario
            expires_delta: Tiempo de expiración custom (opcional)

        Returns:
            Token JWT firmado
        """
        if expires_delta:
            expire = datetime.now(UTC) + expires_delta
        else:
            expire = datetime.now(UTC) + timedelta(minutes=self.expire_minutes)

        payload = {
            "sub": user_id,
            "email": email,
            "exp": expire,
            "iat": datetime.now(UTC),
            "type": "access",
        }

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        logger.debug(f"Token creado para usuario {email}")
        return token

    def decode_token(self, token: str) -> dict | None:
        """
        Decodifica y valida un token JWT.

        Args:
            token: Token JWT a validar

        Returns:
            Payload del token si es válido, None si no

        Raises:
            jwt.ExpiredSignatureError: Si el token expiró
            jwt.InvalidTokenError: Si el token es inválido
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expirado")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Token inválido: {e}")
            return None

    # =========================================================================
    # USER MANAGEMENT
    # =========================================================================

    def get_user_by_email(self, db: Session, email: str) -> User | None:
        """
        Busca un usuario por email.

        Args:
            db: Sesión de base de datos
            email: Email a buscar

        Returns:
            Usuario si existe, None si no
        """
        stmt = select(User).where(
            User.email == email.lower(),
            User.deleted_at.is_(None),
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_user_by_id(self, db: Session, user_id: str) -> User | None:
        """
        Busca un usuario por ID.

        Args:
            db: Sesión de base de datos
            user_id: ID del usuario

        Returns:
            Usuario si existe, None si no
        """
        stmt = select(User).where(
            User.id == user_id,
            User.deleted_at.is_(None),
        )
        return db.execute(stmt).scalar_one_or_none()

    def create_user(
        self,
        db: Session,
        email: str,
        password: str,
        nombre: str,
    ) -> User:
        """
        Crea un nuevo usuario.

        Args:
            db: Sesión de base de datos
            email: Email del usuario
            password: Password en texto plano
            nombre: Nombre del usuario

        Returns:
            Usuario creado

        Raises:
            ValueError: Si el email ya existe
        """
        # Verificar que no exista
        existing = self.get_user_by_email(db, email)
        if existing:
            raise ValueError(f"El email {email} ya está registrado")

        # Crear usuario
        user = User(
            email=email.lower(),
            password_hash=self.hash_password(password),
            nombre=nombre,
            is_active=True,
            is_verified=False,  # TODO: Implementar verificación por email
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        logger.info(f"Usuario creado: {email}")
        return user

    def authenticate_user(
        self,
        db: Session,
        email: str,
        password: str,
    ) -> User | None:
        """
        Autentica un usuario con email y password.

        Args:
            db: Sesión de base de datos
            email: Email del usuario
            password: Password en texto plano

        Returns:
            Usuario si credenciales correctas, None si no
        """
        user = self.get_user_by_email(db, email)

        if not user:
            logger.warning(f"Login fallido: usuario no existe ({email})")
            return None

        if not user.is_active:
            logger.warning(f"Login fallido: usuario inactivo ({email})")
            return None

        if not self.verify_password(password, user.password_hash):
            logger.warning(f"Login fallido: password incorrecto ({email})")
            return None

        # Actualizar último login
        user.last_login = datetime.now(UTC)
        db.commit()

        logger.info(f"Login exitoso: {email}")
        return user

    def login(self, db: Session, email: str, password: str) -> dict | None:
        """
        Proceso completo de login: autenticar y generar token.

        Args:
            db: Sesión de base de datos
            email: Email del usuario
            password: Password en texto plano

        Returns:
            Dict con access_token y user info, o None si falla
        """
        user = self.authenticate_user(db, email, password)
        if not user:
            return None

        access_token = self.create_access_token(user.id, user.email)

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": self.expire_minutes * 60,  # En segundos
            "user": {
                "id": user.id,
                "email": user.email,
                "nombre": user.nombre,
            },
        }


# Singleton
auth_service = AuthService()
