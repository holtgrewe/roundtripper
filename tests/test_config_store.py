"""Tests for configuration storage."""

import json
from pathlib import Path

import pytest

from roundtripper.config import ConfigModel, ConnectionConfig
from roundtripper.config_store import (
    get_app_config_path,
    get_default_value_by_path,
    get_settings,
    load_app_data,
    reset_to_defaults,
    save_app_data,
    set_setting,
)


@pytest.fixture
def temp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary config directory for testing."""
    config_dir = tmp_path / "roundtripper"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"

    # Patch the module-level variable
    monkeypatch.setattr("roundtripper.config_store.APP_CONFIG_PATH", config_file)

    return config_dir


class TestGetAppConfigPath:
    """Test get_app_config_path function."""

    def test_default_xdg_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that default path uses XDG standard."""
        monkeypatch.delenv("ROUNDTRIPPER_CONFIG_PATH", raising=False)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        path = get_app_config_path()
        assert ".config/roundtripper/config.json" in str(path)
        assert path.name == "config.json"

    def test_xdg_config_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that XDG_CONFIG_HOME is respected."""
        xdg_dir = tmp_path / "xdg_config"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_dir))
        monkeypatch.delenv("ROUNDTRIPPER_CONFIG_PATH", raising=False)

        path = get_app_config_path()
        assert path == xdg_dir / "roundtripper" / "config.json"

    def test_custom_env_variable(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that ROUNDTRIPPER_CONFIG_PATH env var takes precedence."""
        custom_path = tmp_path / "custom" / "config.json"
        monkeypatch.setenv("ROUNDTRIPPER_CONFIG_PATH", str(custom_path))

        path = get_app_config_path()
        assert path == custom_path

    def test_creates_parent_directories(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that parent directories are created."""
        config_path = tmp_path / "deep" / "nested" / "path" / "config.json"
        monkeypatch.setenv("ROUNDTRIPPER_CONFIG_PATH", str(config_path))

        path = get_app_config_path()
        assert path.parent.exists()


class TestLoadAppData:
    """Test load_app_data function."""

    def test_load_nonexistent_file(
        self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test loading when config file doesn't exist."""
        config_file = temp_config_dir / "config.json"
        monkeypatch.setattr("roundtripper.config_store.APP_CONFIG_PATH", config_file)

        data = load_app_data()
        assert isinstance(data, dict)
        assert "connection_config" in data
        assert "auth" in data

    def test_load_valid_file(self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading a valid config file."""
        config_file = temp_config_dir / "config.json"
        monkeypatch.setattr("roundtripper.config_store.APP_CONFIG_PATH", config_file)

        # Create a valid config file
        config = ConfigModel.model_validate(
            {
                "connection_config": {"verify_ssl": False},
                "auth": {"confluence": {"url": "https://example.atlassian.net"}},
            }
        )
        config_file.write_text(config.model_dump_json())

        data = load_app_data()
        assert data["connection_config"]["verify_ssl"] is False
        assert "example.atlassian.net" in str(data["auth"]["confluence"]["url"])

    def test_load_invalid_json(
        self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test loading when config file has invalid JSON."""
        config_file = temp_config_dir / "config.json"
        monkeypatch.setattr("roundtripper.config_store.APP_CONFIG_PATH", config_file)

        config_file.write_text("{ invalid json }")

        # Should return defaults on error
        data = load_app_data()
        assert isinstance(data, dict)
        assert "connection_config" in data

    def test_load_invalid_schema(
        self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test loading when config file has invalid schema."""
        config_file = temp_config_dir / "config.json"
        monkeypatch.setattr("roundtripper.config_store.APP_CONFIG_PATH", config_file)

        config_file.write_text('{"invalid": "schema"}')

        # Should return defaults on validation error
        data = load_app_data()
        assert isinstance(data, dict)
        assert "connection_config" in data


class TestSaveAppData:
    """Test save_app_data function."""

    def test_save_config(self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test saving configuration to file."""
        config_file = temp_config_dir / "config.json"
        monkeypatch.setattr("roundtripper.config_store.APP_CONFIG_PATH", config_file)

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

        save_app_data(config)

        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert data["connection_config"]["verify_ssl"] is False
        assert "user@example.com" in data["auth"]["confluence"]["username"]

    def test_save_creates_file(
        self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that save creates file if it doesn't exist."""
        config_file = temp_config_dir / "config.json"
        monkeypatch.setattr("roundtripper.config_store.APP_CONFIG_PATH", config_file)

        assert not config_file.exists()

        save_app_data(ConfigModel())

        assert config_file.exists()


class TestGetSettings:
    """Test get_settings function."""

    def test_get_default_settings(
        self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test getting settings when no config file exists."""
        config_file = temp_config_dir / "config.json"
        monkeypatch.setattr("roundtripper.config_store.APP_CONFIG_PATH", config_file)

        settings = get_settings()
        assert isinstance(settings, ConfigModel)
        assert settings.connection_config.verify_ssl is True

    def test_get_saved_settings(
        self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test getting settings from saved config."""
        config_file = temp_config_dir / "config.json"
        monkeypatch.setattr("roundtripper.config_store.APP_CONFIG_PATH", config_file)

        # Save a config
        config = ConfigModel(connection_config=ConnectionConfig(verify_ssl=False))
        save_app_data(config)

        # Retrieve it
        settings = get_settings()
        assert settings.connection_config.verify_ssl is False


class TestSetSetting:
    """Test set_setting function."""

    def test_set_simple_setting(
        self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test setting a simple value."""
        config_file = temp_config_dir / "config.json"
        monkeypatch.setattr("roundtripper.config_store.APP_CONFIG_PATH", config_file)

        set_setting("connection_config.verify_ssl", False)

        settings = get_settings()
        assert settings.connection_config.verify_ssl is False

    def test_set_nested_setting(
        self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test setting a nested value."""
        config_file = temp_config_dir / "config.json"
        monkeypatch.setattr("roundtripper.config_store.APP_CONFIG_PATH", config_file)

        set_setting("auth.confluence.url", "https://example.atlassian.net")

        settings = get_settings()
        assert "example.atlassian.net" in str(settings.auth.confluence.url)

    def test_set_invalid_value(
        self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that setting invalid value raises ValueError."""
        config_file = temp_config_dir / "config.json"
        monkeypatch.setattr("roundtripper.config_store.APP_CONFIG_PATH", config_file)

        with pytest.raises(ValueError):
            set_setting("connection_config.max_backoff_retries", "not_a_number")

    def test_set_creates_nested_path(
        self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that set_setting creates intermediate nested dicts."""
        config_file = temp_config_dir / "config.json"
        monkeypatch.setattr("roundtripper.config_store.APP_CONFIG_PATH", config_file)

        # Start with empty config
        config_file.write_text("{}")

        set_setting("connection_config.verify_ssl", False)

        settings = get_settings()
        assert settings.connection_config.verify_ssl is False

    def test_set_overwrites_non_dict(
        self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that set_setting overwrites non-dict values when creating paths."""
        config_file = temp_config_dir / "config.json"
        monkeypatch.setattr("roundtripper.config_store.APP_CONFIG_PATH", config_file)

        # Start with a config where connection_config is a string instead of dict
        config_file.write_text('{"connection_config": "wrong_type"}')

        # This should overwrite the string and create the proper nested structure
        set_setting("connection_config.verify_ssl", False)

        settings = get_settings()
        assert settings.connection_config.verify_ssl is False


class TestGetDefaultValueByPath:
    """Test get_default_value_by_path function."""

    def test_get_entire_default(self) -> None:
        """Test getting entire default config."""
        defaults = get_default_value_by_path(None)
        assert isinstance(defaults, dict)
        assert "connection_config" in defaults
        assert "auth" in defaults

    def test_get_section_default(self) -> None:
        """Test getting default for a section."""
        defaults = get_default_value_by_path("connection_config")
        assert isinstance(defaults, dict)
        assert "verify_ssl" in defaults
        assert defaults["verify_ssl"] is True

    def test_get_nested_default(self) -> None:
        """Test getting default for a nested path."""
        default = get_default_value_by_path("connection_config.verify_ssl")
        assert default is True

    def test_get_dict_based_path(self) -> None:
        """Test getting value from dict-based path (edge case)."""
        # The function returns model_dump() if no path given, which is a dict
        # This exercises the dict traversal code path
        defaults = get_default_value_by_path("auth")
        assert isinstance(defaults, dict)
        assert "confluence" in defaults

    def test_get_invalid_path(self) -> None:
        """Test that invalid path raises KeyError."""
        with pytest.raises(KeyError, match="Invalid config path"):
            get_default_value_by_path("invalid.path.here")


class TestResetToDefaults:
    """Test reset_to_defaults function."""

    def test_reset_entire_config(
        self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test resetting entire config to defaults."""
        config_file = temp_config_dir / "config.json"
        monkeypatch.setattr("roundtripper.config_store.APP_CONFIG_PATH", config_file)

        # Set custom values
        set_setting("connection_config.verify_ssl", False)
        assert get_settings().connection_config.verify_ssl is False

        # Reset all
        reset_to_defaults(None)

        settings = get_settings()
        assert settings.connection_config.verify_ssl is True

    def test_reset_section(self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test resetting a specific section."""
        config_file = temp_config_dir / "config.json"
        monkeypatch.setattr("roundtripper.config_store.APP_CONFIG_PATH", config_file)

        # Set custom values
        set_setting("connection_config.verify_ssl", False)
        set_setting("connection_config.max_backoff_retries", 10)

        # Reset only connection_config section
        reset_to_defaults("connection_config")

        settings = get_settings()
        assert settings.connection_config.verify_ssl is True
        assert settings.connection_config.max_backoff_retries == 5

    def test_reset_single_value(
        self, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test resetting a single value."""
        config_file = temp_config_dir / "config.json"
        monkeypatch.setattr("roundtripper.config_store.APP_CONFIG_PATH", config_file)

        # Set custom value
        set_setting("connection_config.verify_ssl", False)

        # Reset only that value
        reset_to_defaults("connection_config.verify_ssl")

        settings = get_settings()
        assert settings.connection_config.verify_ssl is True
