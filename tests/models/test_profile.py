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
