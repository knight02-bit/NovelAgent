"""Shared test fixtures and configuration."""

import pytest


@pytest.fixture
def fixed_seed() -> int:
    """Fixed seed for reproducible tests."""
    return 42
