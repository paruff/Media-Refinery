from typing import Dict, Any

class IntegrationManager:
    """
    Manages integrations with external services.
    """

    def __init__(self):
        self.integrations: Dict[str, Any] = {}

    def register_integration(self, name: str, integration: Any) -> None:
        """
        Registers a new integration.

        Args:
            name (str): The name of the integration.
            integration (Any): The integration instance.
        """
        self.integrations[name] = integration

    def get_integration(self, name: str) -> Any:
        """
        Retrieves an integration by name.

        Args:
            name (str): The name of the integration.

        Returns:
            Any: The integration instance, or None if not found.
        """
        return self.integrations.get(name)