"""Tests for dashboard helpers."""

from unittest.mock import MagicMock, patch

import pytest

from finanzas_tracker.models.profile import Profile


class TestGetActiveProfile:
    """Tests for get_active_profile function."""

    @pytest.fixture(autouse=True)
    def clear_cache(self) -> None:
        """Clear cache before each test."""
        from finanzas_tracker.dashboard.helpers import get_active_profile

        # Clear the cache between tests
        if hasattr(get_active_profile, "invalidate_cache"):
            get_active_profile.invalidate_cache()

    @patch("finanzas_tracker.dashboard.helpers.get_session")
    def test_get_active_profile_returns_active_profile(self, mock_session: MagicMock) -> None:
        """Should return the active profile."""
        # Setup mock profile
        mock_profile = Profile(
            id="test-profile-123",
            email_outlook="test@example.com",
            nombre="Test Profile",
            es_activo=True,
            activo=True,
        )

        # Mock the session query chain
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_profile
        mock_session.return_value.__enter__.return_value.query.return_value = mock_query

        from finanzas_tracker.dashboard.helpers import get_active_profile

        result = get_active_profile()

        assert result is not None
        assert result.id == "test-profile-123"
        assert result.es_activo is True

    @patch("finanzas_tracker.dashboard.helpers.get_session")
    def test_get_active_profile_returns_none_when_no_active(self, mock_session: MagicMock) -> None:
        """Should return None when no active profile exists."""
        # Mock empty result
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_session.return_value.__enter__.return_value.query.return_value = mock_query

        from finanzas_tracker.dashboard.helpers import get_active_profile

        result = get_active_profile()
        assert result is None


class TestRequireProfile:
    """Tests for require_profile function."""

    @patch("finanzas_tracker.dashboard.helpers.get_active_profile")
    def test_require_profile_returns_profile_when_exists(self, mock_get_profile: MagicMock) -> None:
        """Should return profile when active profile exists."""
        mock_profile = Profile(
            id="test-profile-456",
            email_outlook="test@example.com",
            nombre="Active Profile",
            es_activo=True,
            activo=True,
        )
        mock_get_profile.return_value = mock_profile

        from finanzas_tracker.dashboard.helpers import require_profile

        result = require_profile()

        assert result is not None
        assert result.id == "test-profile-456"

    @patch("finanzas_tracker.dashboard.helpers.get_active_profile")
    @patch("streamlit.warning")
    @patch("streamlit.info")
    @patch("streamlit.stop")
    def test_require_profile_stops_when_no_profile(
        self,
        mock_stop: MagicMock,
        mock_info: MagicMock,
        mock_warning: MagicMock,
        mock_get_profile: MagicMock,
    ) -> None:
        """Should show warning and stop when no active profile."""
        mock_get_profile.return_value = None

        from finanzas_tracker.dashboard.helpers import require_profile

        require_profile()

        mock_warning.assert_called_once()
        mock_info.assert_called_once()
        mock_stop.assert_called_once()
