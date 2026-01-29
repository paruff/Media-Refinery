import pytest
from src.integrations.integration_manager import IntegrationManager

class MockIntegration:
    def __init__(self, name):
        self.name = name

    def perform_action(self):
        return f"Action performed by {self.name}"

@pytest.fixture
def integration_manager():
    return IntegrationManager()

def test_integration_manager_with_mock_integration(integration_manager):
    mock_integration = MockIntegration("TestIntegration")
    integration_manager.register_integration("mock", mock_integration)

    retrieved = integration_manager.get_integration("mock")
    assert retrieved is not None
    assert retrieved.perform_action() == "Action performed by TestIntegration"