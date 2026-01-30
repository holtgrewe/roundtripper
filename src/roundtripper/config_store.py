"""Storage and retrieval of application configuration for roundtripper.

Uses XDG Base Directory specification for config file location.
Adapted from confluence-markdown-exporter by Sebastian Penhouet.
https://github.com/Spenhouet/confluence-markdown-exporter
"""

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from roundtripper.config import AuthConfig, ConfigModel, ConnectionConfig


def get_app_config_path() -> Path:
    """Determine the path to the app config file using XDG standard.

    The config file location is determined by:
    1. ROUNDTRIPPER_CONFIG_PATH environment variable if set
    2. XDG_CONFIG_HOME/roundtripper/config.json if XDG_CONFIG_HOME is set
    3. ~/.config/roundtripper/config.json (XDG default)

    Creates parent directories if they don't exist.

    Returns
    -------
    Path
        Path to the configuration file.
    """
    config_env = os.environ.get("ROUNDTRIPPER_CONFIG_PATH")
    if config_env:
        path = Path(config_env)
    else:
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config_home:
            config_dir = Path(xdg_config_home) / "roundtripper"
        else:
            config_dir = Path.home() / ".config" / "roundtripper"
        path = config_dir / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


APP_CONFIG_PATH = get_app_config_path()


def load_app_data() -> dict[str, dict]:
    """Load application data from the config file.

    Returns a validated dict. If the file doesn't exist or is invalid,
    returns the default configuration.

    Returns
    -------
    dict[str, dict]
        Configuration data as a dictionary.
    """
    if not APP_CONFIG_PATH.exists():
        return ConfigModel().model_dump()

    try:
        data = json.loads(APP_CONFIG_PATH.read_text())
        return ConfigModel(**data).model_dump()
    except (json.JSONDecodeError, ValidationError):
        return ConfigModel().model_dump()


def save_app_data(config_model: ConfigModel) -> None:
    """Save application data to the config file.

    Uses Pydantic's model_dump_json which properly handles SecretStr serialization.

    Parameters
    ----------
    config_model
        The configuration model to save.
    """
    json_str = config_model.model_dump_json(indent=2)
    APP_CONFIG_PATH.write_text(json_str)


def get_settings() -> ConfigModel:
    """Get the current application settings as a ConfigModel instance.

    Returns
    -------
    ConfigModel
        Current configuration settings.
    """
    data = load_app_data()
    return ConfigModel(
        connection_config=ConnectionConfig(**data.get("connection_config", {})),
        auth=AuthConfig(**data.get("auth", {})),
    )


def _set_by_path(obj: dict, path: str, value: Any) -> None:
    """Set a value in a nested dictionary by dot-notation path.

    Parameters
    ----------
    obj
        The dictionary to modify.
    path
        Dot-notation path (e.g., 'auth.confluence.url').
    value
        The value to set.
    """
    keys = path.split(".")
    current = obj
    for k in keys[:-1]:
        if k not in current or not isinstance(current[k], dict):  # pragma: no cover
            current[k] = {}
        current = current[k]
    current[keys[-1]] = value


def set_setting(path: str, value: Any) -> None:
    """Set a setting by dot-path and save to config file.

    Parameters
    ----------
    path
        Dot-separated path to the setting (e.g., "auth.confluence.url").
    value
        The value to set.

    Raises
    ------
    ValueError
        If the value is invalid according to the Pydantic model.
    """
    data = load_app_data()
    _set_by_path(data, path, value)
    try:
        settings = ConfigModel.model_validate(data)
    except ValidationError as e:
        raise ValueError(str(e)) from e
    save_app_data(settings)


def get_default_value_by_path(path: str | None = None) -> Any:
    """Get the default value for a given config path.

    Parameters
    ----------
    path
        Dot-separated path to the setting. If None, returns the entire default config.

    Returns
    -------
    Any
        The default value for the given path.

    Raises
    ------
    KeyError
        If the path is invalid.
    """
    model = ConfigModel()
    if not path:
        return model.model_dump()
    keys = path.split(".")
    current: Any = model
    for k in keys:
        if hasattr(current, k):
            current = getattr(current, k)
        elif isinstance(current, dict) and k in current:  # pragma: no cover
            current = current[k]
        else:
            msg = f"Invalid config path: {path}"
            raise KeyError(msg)

    if isinstance(current, BaseModel):
        return current.model_dump()
    return current


def reset_to_defaults(path: str | None = None) -> None:
    """Reset the whole config, a section, or a single option to its default value.

    Parameters
    ----------
    path
        Dot-separated path to reset. If None, resets the entire config.
    """
    if path is None:
        save_app_data(ConfigModel())
        return
    data = load_app_data()
    default_value = get_default_value_by_path(path)
    _set_by_path(data, path, default_value)
    settings = ConfigModel.model_validate(data)
    save_app_data(settings)
