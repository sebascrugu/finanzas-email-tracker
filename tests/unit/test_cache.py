"""Tests for the caching system."""

import time

import pytest

from finanzas_tracker.core.cache import TTLCache, cached_query, invalidate_profile_cache


class TestTTLCache:
    """Tests for TTL Cache class."""

    def test_cache_set_and_get(self) -> None:
        """Should store and retrieve values."""
        cache = TTLCache(ttl_seconds=60)
        cache.set("key1", "value1")

        assert cache.get("key1") == "value1"

    def test_cache_expiration(self) -> None:
        """Should expire values after TTL."""
        cache = TTLCache(ttl_seconds=1)  # 1 second TTL
        cache.set("key1", "value1")

        # Should exist immediately
        assert cache.get("key1") == "value1"

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired
        assert cache.get("key1") is None

    def test_cache_miss(self) -> None:
        """Should return None for non-existent keys."""
        cache = TTLCache()
        assert cache.get("nonexistent") is None

    def test_cache_invalidate_specific_key(self) -> None:
        """Should invalidate specific key."""
        cache = TTLCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.invalidate("key1")

        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_cache_invalidate_all(self) -> None:
        """Should invalidate all keys."""
        cache = TTLCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.invalidate()

        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_cache_stats(self) -> None:
        """Should return cache statistics."""
        cache = TTLCache(ttl_seconds=300)
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        stats = cache.get_stats()

        assert stats["total_keys"] == 2
        assert stats["ttl_seconds"] == 300


class TestCachedQuery:
    """Tests for cached_query decorator."""

    def test_cached_query_decorator(self) -> None:
        """Should cache function results."""
        call_count = 0

        @cached_query(ttl_seconds=60, profile_aware=False)
        def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call - should execute
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call with same args - should use cache
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Not incremented

        # Different args - should execute
        result3 = expensive_function(10)
        assert result3 == 20
        assert call_count == 2

    def test_cached_query_profile_aware(self) -> None:
        """Should cache per profile_id."""
        call_count = 0

        @cached_query(ttl_seconds=60, profile_aware=True)
        def get_data(profile_id: str, value: int) -> int:
            nonlocal call_count
            call_count += 1
            return value * 2

        # Different profiles should not share cache
        result1 = get_data("profile1", 5)
        assert result1 == 10
        assert call_count == 1

        result2 = get_data("profile2", 5)
        assert result2 == 10
        assert call_count == 2  # Different profile, should execute

        # Same profile should use cache
        result3 = get_data("profile1", 5)
        assert result3 == 10
        assert call_count == 2  # No increment, used cache

    def test_cached_query_expiration(self) -> None:
        """Should re-execute after cache expiration."""
        call_count = 0

        @cached_query(ttl_seconds=1, profile_aware=False)
        def function_with_expiry(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call
        result1 = function_with_expiry(5)
        assert result1 == 10
        assert call_count == 1

        # Wait for expiration
        time.sleep(1.1)

        # Second call after expiration - should re-execute
        result2 = function_with_expiry(5)
        assert result2 == 10
        assert call_count == 2

    def test_cached_query_with_kwargs(self) -> None:
        """Should handle keyword arguments."""
        call_count = 0

        @cached_query(ttl_seconds=60, profile_aware=False)
        def function_with_kwargs(x: int, multiplier: int = 2) -> int:
            nonlocal call_count
            call_count += 1
            return x * multiplier

        # Different kwargs should be different cache entries
        result1 = function_with_kwargs(5, multiplier=2)
        assert result1 == 10
        assert call_count == 1

        result2 = function_with_kwargs(5, multiplier=3)
        assert result2 == 15
        assert call_count == 2

        # Same kwargs should use cache
        result3 = function_with_kwargs(5, multiplier=2)
        assert result3 == 10
        assert call_count == 2  # No increment


class TestInvalidateProfileCache:
    """Tests for profile cache invalidation."""

    def test_invalidate_profile_cache(self) -> None:
        """Should invalidate profile cache without errors."""
        # Should not raise any errors
        invalidate_profile_cache("profile123")
