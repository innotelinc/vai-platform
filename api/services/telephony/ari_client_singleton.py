"""Singleton holder for the current ARI client instance.

This module provides a thread-safe singleton that holds the current
ARI client instance, which can be updated during reconnections.
"""

from typing import Optional

from loguru import logger

from api.services.telephony.ari_client import AsyncARIClient


class ARIClientSingleton:
    """Singleton holder for the current ARI client instance."""

    _instance: Optional["ARIClientSingleton"] = None
    _client: Optional[AsyncARIClient] = None

    def __new__(cls):
        """Ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def set_client(self, client: AsyncARIClient) -> None:
        """Update the ARI client instance.

        Args:
            client: The new ARI client instance.
        """
        self._client = client
        logger.info("ARI client singleton updated with new client instance")

    def get_client(self) -> Optional[AsyncARIClient]:
        """Get the current ARI client instance.

        Returns:
            The current ARI client, or None if not set.
        """
        return self._client

    def clear(self) -> None:
        """Clear the current client instance."""
        self._client = None
        logger.info("ARI client singleton cleared")


# Global singleton instance
ari_client_singleton = ARIClientSingleton()
