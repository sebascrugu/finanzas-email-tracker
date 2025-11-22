"""Tests for Profile model."""

import pytest

from finanzas_tracker.models.profile import Profile


class TestProfileProperties:
    """Tests for Profile model properties."""

    @pytest.fixture
    def profile(self) -> Profile:
        """Create a basic profile for testing."""
        return Profile(
            id="test-uuid-1234",
            email_outlook="test@example.com",
            nombre="Personal",
            descripcion="Mi perfil personal",
            icono="👤",
            es_activo=True,
            activo=True,
        )

    def test_nombre_completo_with_icon(self, profile: Profile) -> None:
        """Should return name with icon."""
        assert profile.nombre_completo == "👤 Personal"

    def test_nombre_completo_without_icon(self, profile: Profile) -> None:
        """Should return just name when no icon."""
        profile.icono = None
        assert profile.nombre_completo == "Personal"

    def test_nombre_completo_empty_icon(self, profile: Profile) -> None:
        """Should return just name when icon is empty string."""
        profile.icono = ""
        assert profile.nombre_completo == "Personal"

    def test_bancos_asociados_empty(self, profile: Profile) -> None:
        """Should return empty list when no cards."""
        profile.cards = []
        assert profile.bancos_asociados == []

    def test_repr(self, profile: Profile) -> None:
        """Should return readable string representation."""
        repr_str = repr(profile)
        assert "Profile" in repr_str
        assert "Personal" in repr_str
        assert "test@example.com" in repr_str


class TestProfileMethods:
    """Tests for Profile model methods."""

    @pytest.fixture
    def profile(self) -> Profile:
        """Create a profile for testing."""
        return Profile(
            id="test-uuid-5678",
            email_outlook="business@example.com",
            nombre="Negocio",
            es_activo=False,
            activo=True,
        )

    def test_activar(self, profile: Profile) -> None:
        """Should set es_activo to True."""
        assert profile.es_activo is False
        profile.activar()
        assert profile.es_activo is True

    def test_desactivar(self, profile: Profile) -> None:
        """Should set es_activo to False."""
        profile.es_activo = True
        profile.desactivar()
        assert profile.es_activo is False

    def test_activar_already_active(self, profile: Profile) -> None:
        """Should remain True if already active."""
        profile.es_activo = True
        profile.activar()
        assert profile.es_activo is True


class TestProfileValidations:
    """Tests for Profile model validations."""

    def test_validate_nombre_not_empty(self) -> None:
        """Should reject empty or whitespace-only nombre."""
        with pytest.raises(ValueError, match="El nombre del perfil no puede estar vacío"):
            Profile(
                email_outlook="test@example.com",
                nombre="   ",  # Whitespace only
                es_activo=True,
                activo=True,
            )

    def test_validate_email_outlook_not_empty(self) -> None:
        """Should reject empty email_outlook."""
        with pytest.raises(ValueError, match="El email de Outlook no puede estar vacío"):
            Profile(
                email_outlook="   ",  # Whitespace only
                nombre="Test",
                es_activo=True,
                activo=True,
            )

    def test_validate_email_outlook_invalid_format(self) -> None:
        """Should reject invalid email format."""
        with pytest.raises(ValueError, match="Formato de email inválido"):
            Profile(
                email_outlook="notanemail",  # No @ symbol
                nombre="Test",
                es_activo=True,
                activo=True,
            )

    def test_bancos_asociados_with_cards(self) -> None:
        """Should return banco from active cards."""
        from finanzas_tracker.models.card import Card
        from finanzas_tracker.models.enums import BankName

        card1 = Card(
            profile_id="profile-123",
            banco=BankName.BAC,
            ultimos_4_digitos="1234",
            activa=True,
        )
        card2 = Card(
            profile_id="profile-123",
            banco=BankName.POPULAR,
            ultimos_4_digitos="5678",
            activa=True,
        )

        profile = Profile(
            email_outlook="test@example.com",
            nombre="Test",
            es_activo=True,
            activo=True,
        )
        profile.cards = [card1, card2]

        bancos = profile.bancos_asociados
        assert len(bancos) == 2
        assert "bac" in bancos or "popular" in bancos
