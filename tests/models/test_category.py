"""Tests for Category and Subcategory models."""

import pytest

from finanzas_tracker.models.category import Category, Subcategory
from finanzas_tracker.models.enums import CategoryType


class TestCategory:
    """Tests for Category model."""

    @pytest.fixture
    def category(self) -> Category:
        """Create a basic category for testing."""
        return Category(
            id="cat-uuid-1234",
            tipo=CategoryType.NECESSITIES,
            nombre="Transporte",
            descripcion="Gastos de transporte",
            icono="🚗",
        )

    def test_repr(self, category: Category) -> None:
        """Should return readable string representation."""
        repr_str = repr(category)
        assert "Category" in repr_str
        assert "necesidades" in repr_str
        assert "Transporte" in repr_str


class TestSubcategory:
    """Tests for Subcategory model."""

    @pytest.fixture
    def category(self) -> Category:
        """Create a category for subcategory testing."""
        return Category(
            id="cat-uuid-5678",
            tipo=CategoryType.WANTS,
            nombre="Entretenimiento",
        )

    @pytest.fixture
    def subcategory(self, category: Category) -> Subcategory:
        """Create a subcategory for testing."""
        subcat = Subcategory(
            id="subcat-uuid-1234",
            category_id=category.id,
            nombre="Netflix",
            descripcion="Streaming",
        )
        # Simulate relationship
        subcat.category = category
        return subcat

    def test_repr(self, subcategory: Subcategory) -> None:
        """Should return readable string representation."""
        repr_str = repr(subcategory)
        assert "Subcategory" in repr_str
        assert "Netflix" in repr_str
        assert "cat-uuid-5678" in repr_str

    def test_nombre_completo_with_category(self, subcategory: Subcategory) -> None:
        """Should return full name with category."""
        assert subcategory.nombre_completo == "Entretenimiento/Netflix"

    def test_nombre_completo_without_category(self) -> None:
        """Should return just nombre when no category."""
        subcat = Subcategory(
            category_id="some-id",
            nombre="Netflix",
        )
        # No category relationship set
        subcat.category = None

        assert subcat.nombre_completo == "Netflix"
