import pytest
from src.integrations.integration_manager import IntegrationManager


@pytest.fixture
def integration_manager():
    return IntegrationManager()


def test_register_integration(integration_manager):
    mock_integration = object()
    integration_manager.register_integration("test", mock_integration)

    assert "test" in integration_manager.integrations
    assert integration_manager.integrations["test"] is mock_integration


def test_get_integration(integration_manager):
    mock_integration = object()
    integration_manager.register_integration("test", mock_integration)

    retrieved = integration_manager.get_integration("test")
    assert retrieved is mock_integration


def test_get_integration_not_found(integration_manager):
    assert integration_manager.get_integration("nonexistent") is None
