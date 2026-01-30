"""Interactive configuration menu for roundtripper.

Adapted from confluence-markdown-exporter by Sebastian Penhouet.
https://github.com/Spenhouet/confluence-markdown-exporter
"""

# pragma: exclude file

from pathlib import Path
from typing import Any, Literal, get_args, get_origin

import jmespath
import questionary
from pydantic import BaseModel, SecretStr, ValidationError
from questionary import Choice, Style

from roundtripper.config import ConfigModel
from roundtripper.config_store import (
    get_app_config_path,
    get_settings,
    reset_to_defaults,
    set_setting,
)

custom_style = Style(
    [
        ("key", "fg:#00b8d4 bold"),  # cyan bold for key
        ("value", "fg:#888888 italic"),  # gray italic for value
        ("pointer", "fg:#00b8d4 bold"),
        ("highlighted", "fg:#00b8d4 bold"),
    ]
)


def _get_field_type(model: type[BaseModel], key: str) -> type | None:
    """Get the type annotation for a field in a Pydantic model.

    Parameters
    ----------
    model
        The Pydantic model class.
    key
        The field name.

    Returns
    -------
    type | None
        The type annotation, or None if not found.
    """
    if hasattr(model, "model_fields"):  # Pydantic v2
        return model.model_fields[key].annotation
    return model.__annotations__[key]


def _get_submodel(model: type[BaseModel], key: str) -> type[BaseModel] | None:
    """Get the submodel type for a nested field.

    Parameters
    ----------
    model
        The Pydantic model class.
    key
        The field name.

    Returns
    -------
    type[BaseModel] | None
        The submodel type if the field is a BaseModel, None otherwise.
    """
    if hasattr(model, "model_fields"):
        sub = model.model_fields[key].annotation
    else:
        sub = model.__annotations__[key]
    # Only return submodel if it's a subclass of BaseModel
    if isinstance(sub, type):
        try:
            if issubclass(sub, BaseModel):
                return sub
        except TypeError:
            # sub is not a class or not suitable for issubclass
            return None
    return None


def _get_field_metadata(model: type[BaseModel], key: str) -> dict:
    """Get metadata for a field (title, description, examples).

    Parameters
    ----------
    model
        The Pydantic model class.
    key
        The field name.

    Returns
    -------
    dict
        Dictionary with title, description, and examples keys.
    """
    # Support jmespath-style dot-separated paths for nested fields
    if "." in key:
        keys = key.split(".")
        key = keys[-1]

    # Returns dict with title, description, examples for a field
    if hasattr(model, "model_fields"):  # Pydantic v2
        field = model.model_fields[key]
        return {
            "title": getattr(field, "title", None),
            "description": getattr(field, "description", None),
            "examples": getattr(field, "examples", None),
        }
    # Pydantic v1 fallback
    field = model.model_fields[key]
    return {
        "title": getattr(field, "title", None),
        "description": getattr(field, "description", None),
        "examples": getattr(field, "example", None),
    }


def _format_prompt_message(key_name: str, model: type[BaseModel]) -> str:
    """Format a prompt message with field metadata.

    Parameters
    ----------
    key_name
        The field name.
    model
        The Pydantic model class.

    Returns
    -------
    str
        Formatted prompt message.
    """
    meta = _get_field_metadata(model, key_name)
    lines = []
    # Title
    if meta["title"]:
        lines.append(f"{meta['title']}\n")
    else:
        lines.append(f"{key_name}\n")

    # Description
    if meta["description"]:
        lines.append(meta["description"])

    # Examples
    if meta["examples"]:
        ex = meta["examples"]
        if isinstance(ex, list | tuple) and ex:
            lines.append("\nExamples:")
            lines.extend(f"  • {example}" for example in ex)
    # Instruction
    lines.append(f"\nChange {meta['title'] or key_name} to:")
    return "\n".join(lines)


def _validate_int(val: str) -> bool | str:
    """Validate that a string is an integer.

    Parameters
    ----------
    val
        The value to validate.

    Returns
    -------
    bool | str
        True if valid, error message string otherwise.
    """
    return val.isdigit() or "Must be an integer"


def _validate_pydantic(val: Any, model: type[BaseModel], key_name: str) -> bool | str:
    """Validate a value against a Pydantic model field.

    Parameters
    ----------
    val
        The value to validate.
    model
        The Pydantic model class.
    key_name
        The field name.

    Returns
    -------
    bool | str
        True if valid, error message string otherwise.
    """
    try:
        data = model().model_dump()
        data[key_name] = val
        model(**data)
    except ValidationError as e:
        return str(e.errors()[0]["msg"])
    else:
        return True


def _prompt_literal(prompt_message: str, field_type: type, current_value: Any) -> Any:
    """Prompt for a Literal value using select menu.

    Parameters
    ----------
    prompt_message
        The prompt message.
    field_type
        The field type (Literal).
    current_value
        Current value to use as default.

    Returns
    -------
    Any
        Selected value.
    """
    options = list(get_args(field_type))
    return questionary.select(
        prompt_message,
        choices=[str(opt) for opt in options],
        default=str(current_value),
        style=custom_style,
    ).ask()


def _prompt_bool(prompt_message: str, current_value: Any) -> bool:
    """Prompt for a boolean value.

    Parameters
    ----------
    prompt_message
        The prompt message.
    current_value
        Current value to use as default.

    Returns
    -------
    bool
        Boolean value.
    """
    return questionary.confirm(
        prompt_message, default=bool(current_value), style=custom_style
    ).ask()


def _prompt_path(
    prompt_message: str,
    current_value: Any,
    model: type[BaseModel],
    key_name: str,
) -> Any:
    """Prompt for a Path value.

    Parameters
    ----------
    prompt_message
        The prompt message.
    current_value
        Current value to use as default.
    model
        The Pydantic model class for validation.
    key_name
        The field name.

    Returns
    -------
    object
        Path value.
    """
    return questionary.path(
        prompt_message,
        default=str(current_value),
        validate=lambda val: _validate_pydantic(val, model, key_name),
        style=custom_style,
    ).ask()


def _prompt_int(prompt_message: str, current_value: Any) -> int | None:
    """Prompt for an integer value.

    Parameters
    ----------
    prompt_message
        The prompt message.
    current_value
        Current value to use as default.

    Returns
    -------
    int
        Integer value or None if cancelled.
    """
    answer = questionary.text(
        prompt_message,
        default=str(current_value),
        validate=_validate_int,
        style=custom_style,
    ).ask()
    if answer is not None:
        try:
            return int(answer)
        except ValueError:
            questionary.print("Invalid integer value.")
    return None


def _prompt_list(prompt_message: str, current_value: Any) -> list[Any] | None:
    """Prompt for a list value (comma-separated).

    Parameters
    ----------
    prompt_message
        The prompt message.
    current_value
        Current value to use as default.

    Returns
    -------
    list[Any] | None
        List value or None if cancelled.
    """
    default_val = ""
    val_type = str
    if isinstance(current_value, list):
        default_val = ",".join(map(str, current_value))
        if len(current_value) > 0:
            val_type = type(current_value[0])
    answer = questionary.text(
        prompt_message + " (comma-separated)",
        default=default_val,
        style=custom_style,
    ).ask()
    if answer is not None:
        answer = answer.strip().lstrip("[").rstrip("]").strip(",").replace(" ", "")
        try:
            return [val_type(x.strip()) for x in answer.split(",") if x.strip()]
        except ValueError:
            questionary.print("Input should be a list (e.g. 1,2,3 or [1,2,3]).")
    return None


def _prompt_str(
    prompt_message: str,
    current_value: Any,
    model: type[BaseModel],
    key_name: str,
) -> str | None:
    """Prompt for a string value.

    Parameters
    ----------
    prompt_message
        The prompt message.
    current_value
        Current value to use as default.
    model
        The Pydantic model class for validation.
    key_name
        The field name.

    Returns
    -------
    str | None
        String value.
    """
    return questionary.text(
        prompt_message,
        default=str(current_value),
        validate=lambda val: _validate_pydantic(val, model, key_name),
        style=custom_style,
    ).ask()


def get_model_by_path(model: type[BaseModel], path: str) -> type[BaseModel]:
    """Traverse a Pydantic model class using a dot-separated path.

    Parameters
    ----------
    model
        The root Pydantic model class.
    path
        Dot-separated path to the submodel.

    Returns
    -------
    type[BaseModel]
        The submodel class at the given path.
    """
    keys = path.split(".")
    for key in keys:
        sub = _get_submodel(model, key)
        if sub is not None:
            model = sub
        else:
            break
    return model


def _main_config_menu(settings: dict, default: tuple[str, bool] | None = None) -> tuple:
    """Display the main configuration menu.

    Parameters
    ----------
    settings
        Current settings dictionary.
    default : tuple[str, bool] | None
        Default selection (key, is_submenu).

    Returns
    -------
    tuple
        Selected (key, is_submenu) tuple.
    """
    choices = []
    for k, v in settings.items():
        meta = _get_field_metadata(ConfigModel, k)
        display_title = meta["title"] if meta and meta["title"] else k
        if isinstance(v, dict):
            choices.append(
                Choice(
                    title=[
                        ("class:key", str(display_title)),
                        ("class:value", "  [submenu]"),
                    ],
                    value=(k, True),
                )
            )
        else:
            display_val = "Not set" if isinstance(v, str | SecretStr) and str(v) == "" else v
            choices.append(
                Choice(
                    title=[
                        ("class:key", str(display_title)),
                        ("class:value", f"  {display_val}"),
                    ],
                    value=(k, False),
                )
            )
    choices.append(Choice(title="[Reset config to defaults]", value=("__reset__", False)))
    choices.append(Choice(title="[Exit]", value=("__exit__", False)))
    # Find the matching Choice value for default
    default_value = None
    if default is not None:
        for c in choices:
            if hasattr(c, "value") and c.value == default:
                default_value = c.value
                break
    return questionary.select(
        f"Config file location: {get_app_config_path()}\n\nSelect a config to change (or reset):",
        choices=choices,
        style=custom_style,
        default=default_value,
    ).ask() or (None, False)


def _prompt_for_new_value(
    key_name: str,
    current_value: Any,
    model: type[BaseModel],
) -> Any:
    """Prompt user for a new value based on field type.

    Parameters
    ----------
    key_name
        The field name.
    current_value
        Current value.
    model
        The Pydantic model class.

    Returns
    -------
    Any
        New value or None if cancelled.
    """
    field_type = _get_field_type(model, key_name)
    origin = get_origin(field_type)
    prompt_message = _format_prompt_message(key_name, model)
    if field_type is None:
        field_type = str  # Default to string if no type found
    if origin is Literal:
        return _prompt_literal(prompt_message, field_type, current_value)
    if field_type is bool:
        return _prompt_bool(prompt_message, current_value)
    if field_type is Path:
        return _prompt_path(prompt_message, current_value, model, key_name)
    if field_type is int:
        return _prompt_int(prompt_message, current_value)
    if field_type is list or origin is list:
        return _prompt_list(prompt_message, current_value)
    if isinstance(current_value, SecretStr):
        return _prompt_str(prompt_message, current_value.get_secret_value(), model, key_name)
    return _prompt_str(prompt_message, current_value, model, key_name)


def _reset_and_reload(parent_key: str | None, display_title: str | None = None) -> None:
    """Reset config section and reload from disk, with confirmation.

    Parameters
    ----------
    parent_key : str | None
        The config path to reset, or None to reset all.
    display_title : str | None
        Display title for the section being reset.
    """
    if parent_key is None:
        confirm_msg = "Are you sure you want to reset all config to defaults?"
    else:
        confirm_msg = f"Are you sure you want to reset section '{display_title}' to defaults?"
    confirm = questionary.confirm(confirm_msg, style=custom_style).ask()
    if not confirm:
        return
    reset_to_defaults(parent_key if parent_key else None)
    if display_title:
        questionary.print(f"Section '{display_title}' reset to defaults.")
    else:
        questionary.print("Config reset to defaults.")


def _get_choices(config_dict: dict, model: type[BaseModel]) -> list:
    """Get menu choices for a config section.

    Parameters
    ----------
    config_dict
        Configuration dictionary.
    model
        The Pydantic model class.

    Returns
    -------
    list
        List of Choice objects.
    """
    choices = []
    for k, v in config_dict.items():
        if v is None:
            continue
        meta = _get_field_metadata(model, k)
        display_title = meta["title"] if meta and meta["title"] else k
        if isinstance(v, dict):
            choices.append(
                Choice(
                    title=[
                        ("class:key", str(display_title)),
                        ("class:value", "  [submenu]"),
                    ],
                    value=k,
                )
            )
        else:
            display_val = "Not set" if isinstance(v, str | SecretStr) and str(v) == "" else v
            choices.append(
                Choice(
                    title=[
                        ("class:key", str(display_title)),
                        ("class:value", f"  {display_val}"),
                    ],
                    value=k,
                )
            )
    choices.append(Choice(title="[Reset this group to defaults]", value="__reset_section__"))
    choices.append(Choice(title="[Back]", value="__back__"))
    return choices


def _edit_dict_config_loop(
    config_dict: dict,
    model: type[BaseModel],
    parent_key: str,
    parent_model: type[BaseModel],
    last_selected: str | None = None,
) -> str | None:
    """Edit a configuration section with a menu loop.

    Parameters
    ----------
    config_dict
        Configuration dictionary for this section.
    model
        The Pydantic model for this section.
    parent_key
        The config path for this section.
    parent_model
        The parent Pydantic model.
    last_selected : str | None
        Last selected key (for cursor positioning).

    Returns
    -------
    str | None
        Last selected key or None.
    """
    selected_key = last_selected
    while True:
        choices = _get_choices(config_dict, model)
        meta = None
        if hasattr(parent_model, "model_fields") and parent_key:
            meta = _get_field_metadata(parent_model, parent_key)
        display_title = meta["title"] if meta and meta["title"] else parent_key
        key = questionary.select(
            f"Edit options for '{display_title}':",
            choices=choices,
            style=custom_style,
            default=selected_key,
        ).ask()
        if key == "__back__" or key is None:
            return selected_key
        if key == "__reset_section__":
            _reset_and_reload(parent_key, display_title)
            # Reload the updated config_dict for this section from disk
            updated = get_settings().model_dump()
            if parent_key:
                # Traverse to the correct nested dict for jmespath/dot-paths
                keys = parent_key.split(".")
                sub = updated
                for k in keys:
                    sub = sub[k]
                config_dict.clear()
                config_dict.update(sub)
            else:
                config_dict.clear()
                config_dict.update(updated)
            selected_key = None
            continue
        current_value = config_dict[key] if key else None
        submodel = _get_submodel(model, key)
        if isinstance(current_value, dict) and submodel is not None:
            # Always set selected_key to the submenu key after returning
            _edit_dict_config_loop(
                current_value,
                submodel,
                f"{parent_key}.{key}" if parent_key else key,
                model,
                last_selected=None,
            )
            selected_key = key
        else:
            while True:
                value_cast = _prompt_for_new_value(key, current_value, model)
                if value_cast is not None:
                    try:
                        set_setting(f"{parent_key}.{key}" if parent_key else key, value_cast)
                        config_dict[key] = value_cast
                        questionary.print(f"{parent_key}.{key} updated to {value_cast}.")
                        selected_key = key
                        break
                    except (ValueError, TypeError) as e:
                        questionary.print(f"Error: {e}")
                        retry = questionary.confirm("Try again?", style=custom_style).ask()
                        if not retry:
                            break
                else:
                    break
            # After editing, keep cursor at this entry
            selected_key = key


def _edit_dict_config(
    config_dict: dict,
    model: type[BaseModel],
    parent_key: str,
    parent_model: type[BaseModel],
    last_selected: str | None = None,
) -> str | None:
    """Edit a configuration section.

    Parameters
    ----------
    config_dict
        Configuration dictionary for this section.
    model
        The Pydantic model for this section.
    parent_key
        The config path for this section.
    parent_model
        The parent Pydantic model.
    last_selected : str | None
        Last selected key (for cursor positioning).

    Returns
    -------
    str | None
        Last selected key or None.
    """
    return _edit_dict_config_loop(config_dict, model, parent_key, parent_model, last_selected)


def main_config_menu_loop(jump_to: str | None = None) -> None:
    """Run the main configuration menu loop.

    Parameters
    ----------
    jump_to : str | None
        Optional config path to jump to directly (e.g., "auth.confluence").
    """
    settings = get_settings().model_dump()
    if jump_to:
        submenu = jmespath.search(jump_to, settings)
        submodel = get_model_by_path(ConfigModel, jump_to)
        parent_path = jump_to.rsplit(".", 1)[0] if "." in jump_to else None
        parent_model = get_model_by_path(ConfigModel, parent_path) if parent_path else ConfigModel
        _edit_dict_config(submenu, submodel, jump_to, parent_model)
        return
    last_selected = None
    while True:
        settings = get_settings().model_dump()
        key, is_dict = _main_config_menu(settings, default=last_selected)
        if key == "__reset__":
            _reset_and_reload(None)
            last_selected = None
            continue
        if key == "__exit__" or key is None:
            break
        last_selected = (key, is_dict)
        current_value = settings[key]
        if is_dict:
            submodel = _get_submodel(ConfigModel, key)
            if submodel is not None:
                returned_key = _edit_dict_config(
                    current_value, submodel, key, ConfigModel, last_selected=None
                )
                last_selected = (key, is_dict) if returned_key is None else (returned_key, True)
        else:
            while True:
                value_cast = _prompt_for_new_value(key, current_value, ConfigModel)
                if value_cast is None or value_cast == current_value:
                    # User cancelled or made no change: do not update config
                    break
                try:
                    set_setting(key, value_cast)
                    questionary.print(f"{key} updated to {value_cast}.")
                    last_selected = (key, is_dict)
                    break
                except (ValueError, TypeError) as e:
                    questionary.print(f"Error: {e}")
                    retry = questionary.confirm("Try again?", style=custom_style).ask()
                    if not retry:
                        break
