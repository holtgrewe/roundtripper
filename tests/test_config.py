"""Tests for configuration models."""

from roundtripper.config import ApiDetails, AuthConfig, ConfigModel, ConnectionConfig


class TestConnectionConfig:
    """Test ConnectionConfig model."""

    def test_default_values(self) -> None:
        """Test that ConnectionConfig has correct default values."""
        config = ConnectionConfig()
        assert config.backoff_and_retry is True
        assert config.backoff_factor == 2
        assert config.max_backoff_seconds == 60
        assert config.max_backoff_retries == 5
        assert config.retry_status_codes == [413, 429, 502, 503, 504]
        assert config.verify_ssl is True

    def test_custom_values(self) -> None:
        """Test creating ConnectionConfig with custom values."""
        config = ConnectionConfig(
            backoff_and_retry=False,
            backoff_factor=3,
            max_backoff_seconds=120,
            max_backoff_retries=10,
            retry_status_codes=[500, 502],
            verify_ssl=False,
        )
        assert config.backoff_and_retry is False
        assert config.backoff_factor == 3
        assert config.max_backoff_seconds == 120
        assert config.max_backoff_retries == 10
        assert config.retry_status_codes == [500, 502]
        assert config.verify_ssl is False

    def test_model_dump(self) -> None:
        """Test that model_dump returns correct structure."""
        config = ConnectionConfig()
        data = config.model_dump()
        assert isinstance(data, dict)
        assert "backoff_and_retry" in data
        assert "backoff_factor" in data


class TestApiDetails:
    """Test ApiDetails model."""

    def test_default_values(self) -> None:
        """Test that ApiDetails has correct default values."""
        api = ApiDetails()
        assert api.url == ""
        assert api.username.get_secret_value() == ""
        assert api.api_token.get_secret_value() == ""
        assert api.pat.get_secret_value() == ""

    def test_with_credentials(self) -> None:
        """Test creating ApiDetails with credentials."""
        api = ApiDetails.model_validate(
            {
                "url": "https://example.atlassian.net",
                "username": "user@example.com",
                "api_token": "token123",
                "pat": "pat456",
            }
        )
        assert str(api.url) == "https://example.atlassian.net/"
        assert api.username.get_secret_value() == "user@example.com"
        assert api.api_token.get_secret_value() == "token123"
        assert api.pat.get_secret_value() == "pat456"

    def test_secret_serialization(self) -> None:
        """Test that SecretStr fields are properly serialized to JSON."""
        api = ApiDetails.model_validate(
            {
                "url": "https://example.atlassian.net",
                "username": "user@example.com",
                "api_token": "token123",
            }
        )
        json_str = api.model_dump_json()
        assert "user@example.com" in json_str
        assert "token123" in json_str

    def test_url_validation(self) -> None:
        """Test URL validation."""
        # Valid URL
        api = ApiDetails.model_validate({"url": "https://example.atlassian.net"})
        assert api.url != ""

        # Empty string is allowed as default
        api = ApiDetails(url="")
        assert api.url == ""


class TestAuthConfig:
    """Test AuthConfig model."""

    def test_default_values(self) -> None:
        """Test that AuthConfig has correct default values."""
        auth = AuthConfig()
        assert auth.confluence.url == ""
        assert auth.confluence.username.get_secret_value() == ""

    def test_with_confluence_config(self) -> None:
        """Test creating AuthConfig with Confluence credentials."""
        auth = AuthConfig.model_validate(
            {
                "confluence": {
                    "url": "https://example.atlassian.net",
                    "username": "user@example.com",
                    "api_token": "token123",
                }
            }
        )
        assert str(auth.confluence.url) == "https://example.atlassian.net/"
        assert auth.confluence.username.get_secret_value() == "user@example.com"


class TestConfigModel:
    """Test ConfigModel (top-level configuration)."""

    def test_default_values(self) -> None:
        """Test that ConfigModel has correct default values."""
        config = ConfigModel()
        assert isinstance(config.connection_config, ConnectionConfig)
        assert isinstance(config.auth, AuthConfig)

    def test_nested_structure(self) -> None:
        """Test that nested structure works correctly."""
        config = ConfigModel.model_validate(
            {
                "connection_config": {"verify_ssl": False},
                "auth": {
                    "confluence": {
                        "url": "https://example.atlassian.net",
                        "username": "user@example.com",
                    }
                },
            }
        )
        assert config.connection_config.verify_ssl is False
        assert str(config.auth.confluence.url) == "https://example.atlassian.net/"

    def test_model_dump(self) -> None:
        """Test that model_dump returns correct structure."""
        config = ConfigModel()
        data = config.model_dump()
        assert isinstance(data, dict)
        assert "connection_config" in data
        assert "auth" in data
        assert "confluence" in data["auth"]

    def test_model_validation(self) -> None:
        """Test that model validation works."""
        # Valid data
        data = {
            "connection_config": {"verify_ssl": True},
            "auth": {"confluence": {"url": "https://example.atlassian.net"}},
        }
        config = ConfigModel(**data)
        assert config.connection_config.verify_ssl is True

    def test_json_round_trip(self) -> None:
        """Test JSON serialization and deserialization."""
        original = ConfigModel.model_validate(
            {
                "auth": {
                    "confluence": {
                        "url": "https://example.atlassian.net",
                        "username": "user@example.com",
                        "api_token": "token123",
                    }
                }
            }
        )
        json_str = original.model_dump_json()
        data = original.model_validate_json(json_str)
        assert data.auth.confluence.username.get_secret_value() == "user@example.com"
