"""Confluence API client for roundtripper.

Adapted from confluence-markdown-exporter by Sebastian Penhouet.
https://github.com/Spenhouet/confluence-markdown-exporter
"""

import logging
from typing import Any

from atlassian import Confluence as ConfluenceApiSdk

from roundtripper.config import ApiDetails
from roundtripper.config_store import get_settings

#: Logger instance.
LOGGER = logging.getLogger(__name__)


class ConfluenceClientFactory:
    """Factory for creating authenticated Confluence API clients with retry config."""

    def __init__(self, connection_config: dict[str, Any]) -> None:
        """Initialize the factory with connection configuration.

        Parameters
        ----------
        connection_config
            Connection configuration dictionary with retry/timeout settings.
        """
        self.connection_config = connection_config

    def create(self, auth: ApiDetails) -> ConfluenceApiSdk:
        """Create an authenticated Confluence client.

        Parameters
        ----------
        auth
            API details including URL and credentials.

        Returns
        -------
        ConfluenceApiSdk
            Authenticated Confluence API client.

        Raises
        ------
        ConnectionError
            If the connection to Confluence fails.
        """
        try:
            instance = ConfluenceApiSdk(
                url=str(auth.url),
                username=auth.username.get_secret_value() if auth.api_token else None,
                password=auth.api_token.get_secret_value() if auth.api_token else None,
                token=auth.pat.get_secret_value() if auth.pat else None,
                **self.connection_config,
            )
            # Test connection
            instance.get_all_spaces(limit=1)
        except Exception as e:
            msg = f"Confluence connection failed: {e}"
            raise ConnectionError(msg) from e
        return instance


def get_confluence_client() -> ConfluenceApiSdk:
    """Get an authenticated Confluence API client using current settings.

    Returns
    -------
    ConfluenceApiSdk
        Authenticated Confluence API client.

    Raises
    ------
    ConnectionError
        If the connection to Confluence fails.
    """
    settings = get_settings()
    auth = settings.auth.confluence
    connection_config = settings.connection_config.model_dump()

    return ConfluenceClientFactory(connection_config).create(auth)
