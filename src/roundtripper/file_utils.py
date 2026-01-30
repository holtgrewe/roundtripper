"""Utility functions for file operations.

Adapted from confluence-markdown-exporter by Sebastian Penhouet.
https://github.com/Spenhouet/confluence-markdown-exporter
"""

import json
import re
import xml.dom.minidom
from pathlib import Path
from typing import Any


def format_xml(xml_content: str, max_line_length: int = 120) -> str:
    """Format XML with proper indentation and line wrapping.

    Parameters
    ----------
    xml_content
        Raw XML content to format.
    max_line_length
        Maximum line length before wrapping.

    Returns
    -------
    str
        Formatted XML string with proper indentation.
    """
    try:
        # Add XML declaration if not present for better parsing
        if not xml_content.strip().startswith("<?xml"):
            xml_content = '<?xml version="1.0" encoding="utf-8"?>' + xml_content

        # Parse and pretty-print the XML
        dom = xml.dom.minidom.parseString(xml_content)
        pretty_xml = dom.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")

        # Remove extra blank lines that minidom creates
        lines = [line for line in pretty_xml.split("\n") if line.strip()]

        # Join lines and handle wrapping for long lines
        result_lines = []
        for line in lines:
            # If line is too long and contains attributes, try to wrap
            if len(line) > max_line_length and "=" in line and "<" in line:
                # Simple wrapping: could be enhanced in the future
                result_lines.append(line)
            else:
                result_lines.append(line)

        return "\n".join(result_lines)
    except Exception:
        # If parsing fails, return original content
        return xml_content


def save_file(file_path: Path, content: str | bytes) -> None:
    """Save content to a file, creating parent directories as needed.

    Parameters
    ----------
    file_path
        Path to the file to create/overwrite.
    content
        Content to write (string or bytes).

    Raises
    ------
    TypeError
        If content is neither string nor bytes.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        with file_path.open("wb") as file:
            file.write(content)
    elif isinstance(content, str):
        with file_path.open("w", encoding="utf-8") as file:
            file.write(content)
    else:
        msg = "Content must be either a string or bytes."
        raise TypeError(msg)


def save_json(file_path: Path, data: dict[str, Any]) -> None:
    """Save data as JSON to a file.

    Parameters
    ----------
    file_path
        Path to the JSON file to create/overwrite.
    data
        Data to serialize as JSON.
    """
    content = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    save_file(file_path, content)


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename for cross-platform compatibility.

    Removes or replaces characters that are not allowed in filenames
    on Windows, macOS, and Linux.

    Parameters
    ----------
    filename
        The original filename.

    Returns
    -------
    str
        A sanitized filename string safe for all major operating systems.
    """
    # Replace characters not allowed in Windows filenames
    # Also replace characters that might be problematic on other systems
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars, "_", filename)

    # Trim spaces and dots from the end (Windows doesn't like them)
    sanitized = sanitized.rstrip(" .")

    # Trim spaces from the beginning
    sanitized = sanitized.lstrip(" ")

    # Reserved Windows names (case-insensitive)
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }

    # Check if the name (without extension) is reserved
    name_without_ext = sanitized.split(".")[0].upper()
    if name_without_ext in reserved:
        sanitized = f"_{sanitized}"

    # Ensure non-empty filename
    if not sanitized:
        sanitized = "_"

    return sanitized


def build_page_path(
    output_dir: Path,
    space_key: str,
    ancestors: list[str],
    page_title: str,
) -> Path:
    """Build the directory path for a page based on its hierarchy.

    Parameters
    ----------
    output_dir
        Base output directory.
    space_key
        The space key.
    ancestors
        List of ancestor page titles (from root to parent).
    page_title
        Title of the current page.

    Returns
    -------
    Path
        Full path to the page directory.
    """
    # Start with output_dir/SpaceKey
    path = output_dir / sanitize_filename(space_key)

    # Add ancestor directories
    for ancestor in ancestors:
        path = path / sanitize_filename(ancestor)

    # Add the page directory itself
    path = path / sanitize_filename(page_title)

    return path
