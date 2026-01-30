"""Tests for API client factory."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import AnyHttpUrl, SecretStr

from roundtripper.api_client import ConfluenceClientFactory, get_confluence_client
from roundtripper.config import ApiDetails


class TestConfluenceClientFactory:
    """Tests for ConfluenceClientFactory."""

    def test_create_with_token_auth(self) -> None:
        """Test creating client with token (username + API token) authentication."""
        auth = ApiDetails(
            url=AnyHttpUrl("https://example.atlassian.net/wiki"),
            username=SecretStr("user@example.com"),
            api_token=SecretStr("test-token"),
        )
        connection_config: dict[str, int | bool | list[int]] = {
            "timeout": 30,
            "backoff_and_retry": True,
        }
        factory = ConfluenceClientFactory(connection_config)

        with patch("roundtripper.api_client.ConfluenceApiSdk") as mock_confluence_class:
            mock_client = MagicMock()
            mock_confluence_class.return_value = mock_client

            result = factory.create(auth)

            assert result is mock_client
            mock_confluence_class.assert_called_once_with(
                url="https://example.atlassian.net/wiki",
                username="user@example.com",
                password="test-token",
                token=None,
                **connection_config,
            )

    def test_create_with_pat_auth(self) -> None:
        """Test creating client with PAT authentication."""
        auth = ApiDetails(
            url=AnyHttpUrl("https://confluence.example.com"),
            pat=SecretStr("pat-token-123"),
        )
        connection_config: dict[str, int | bool | list[int]] = {"timeout": 30}
        factory = ConfluenceClientFactory(connection_config)

        with patch("roundtripper.api_client.ConfluenceApiSdk") as mock_confluence_class:
            mock_client = MagicMock()
            mock_confluence_class.return_value = mock_client

            result = factory.create(auth)

            assert result is mock_client
            # AnyHttpUrl adds trailing slash to URLs without path
            mock_confluence_class.assert_called_once_with(
                url="https://confluence.example.com/",
                username=None,
                password=None,
                token="pat-token-123",
                **connection_config,
            )

    def test_create_raises_connection_error(self) -> None:
        """Test that connection errors are raised properly."""
        auth = ApiDetails(
            url=AnyHttpUrl("https://example.com"),
            pat=SecretStr("token"),
        )
        factory = ConfluenceClientFactory({})

        with patch("roundtripper.api_client.ConfluenceApiSdk") as mock_confluence_class:
            mock_client = MagicMock()
            mock_client.get_all_spaces.side_effect = Exception("Network error")
            mock_confluence_class.return_value = mock_client

            with pytest.raises(ConnectionError, match="Confluence connection failed"):
                factory.create(auth)


class TestGetConfluenceClient:
    """Tests for get_confluence_client function."""

    def test_returns_client_when_settings_valid(self) -> None:
        """Test that client is returned when settings are valid."""
        with (
            patch("roundtripper.api_client.get_settings") as mock_get_settings,
            patch("roundtripper.api_client.ConfluenceApiSdk") as mock_confluence_class,
        ):
            mock_settings = MagicMock()
            mock_settings.auth.confluence = ApiDetails(
                url=AnyHttpUrl("https://example.com"),
                pat=SecretStr("token"),
            )
            mock_settings.connection_config.model_dump.return_value = {}
            mock_get_settings.return_value = mock_settings

            mock_client = MagicMock()
            mock_confluence_class.return_value = mock_client

            result = get_confluence_client()

            assert result is mock_client
