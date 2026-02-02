"""Tests for file utility functions."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from roundtripper.file_utils import (
    build_page_path,
    format_xml,
    is_xmllint_available,
    sanitize_filename,
    save_file,
    save_json,
)


class TestIsXmllintAvailable:
    """Tests for is_xmllint_available function."""

    def test_xmllint_available(self) -> None:
        """Test detection when xmllint is available."""
        with patch("shutil.which", return_value="/usr/bin/xmllint"):
            assert is_xmllint_available() is True

    def test_xmllint_not_available(self) -> None:
        """Test detection when xmllint is not available."""
        with patch("shutil.which", return_value=None):
            assert is_xmllint_available() is False


class TestFormatXml:
    """Tests for format_xml function."""

    def test_format_simple_xml_with_xmllint(self) -> None:
        """Test formatting simple XML content with xmllint."""
        xml = "<root><child>value</child></root>"

        # Mock subprocess.run to simulate xmllint
        # Note: The function now wraps input with <root> tags
        formatted_output = (
            '<?xml version="1.0"?>\n<root>\n  <root>\n'
            "    <child>value</child>\n  </root>\n</root>\n"
        )
        mock_result = MagicMock()
        mock_result.stdout = formatted_output.encode("utf-8")

        with (
            patch("roundtripper.file_utils.is_xmllint_available", return_value=True),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            formatted = format_xml(xml)

            # Verify xmllint was called with wrapped input
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == ["xmllint", "--format", "-"]
            assert call_args[1]["input"] == f"<root>{xml}</root>".encode("utf-8")

            # Verify output: wrapper is removed, XML declaration is removed
            assert "<?xml" not in formatted
            assert formatted.count("<root>") == 1  # Only the original root
            assert "<child>value</child>" in formatted

    def test_format_xml_without_xmllint(self) -> None:
        """Test formatting returns original content when xmllint is not available."""
        xml = "<root><child>value</child></root>"

        with patch("roundtripper.file_utils.is_xmllint_available", return_value=False):
            formatted = format_xml(xml)

            # Should return original content unchanged
            assert formatted == xml

    def test_format_xml_with_attributes(self) -> None:
        """Test formatting XML with attributes."""
        xml = '<root attr="value"><child>text</child></root>'

        # Output includes wrapper tags that will be removed
        formatted_output = (
            '<?xml version="1.0"?>\n<root>\n  <root attr="value">\n'
            "    <child>text</child>\n  </root>\n</root>\n"
        )
        mock_result = MagicMock()
        mock_result.stdout = formatted_output.encode("utf-8")

        with (
            patch("roundtripper.file_utils.is_xmllint_available", return_value=True),
            patch("subprocess.run", return_value=mock_result),
        ):
            formatted = format_xml(xml)

            # Verify XML declaration is removed
            assert "<?xml" not in formatted
            assert 'attr="value"' in formatted
            assert "<child>text</child>" in formatted

    def test_format_xml_handles_subprocess_error(self) -> None:
        """Test that subprocess errors are handled gracefully."""
        import subprocess

        xml = "<root><child>value</child></root>"

        with (
            patch("roundtripper.file_utils.is_xmllint_available", return_value=True),
            patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(1, "xmllint", stderr=b"error"),
            ),
        ):
            formatted = format_xml(xml)

            # Should return original content on error
            assert formatted == xml

    def test_format_xml_handles_timeout(self) -> None:
        """Test that timeout is handled gracefully."""
        import subprocess

        xml = "<root><child>value</child></root>"

        with (
            patch("roundtripper.file_utils.is_xmllint_available", return_value=True),
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired("xmllint", 10)),
        ):
            formatted = format_xml(xml)

            # Should return original content on timeout
            assert formatted == xml

    def test_format_xml_preserves_content(self) -> None:
        """Test that XML content is preserved."""
        xml = "<ac:structured-macro><ac:parameter>Test</ac:parameter></ac:structured-macro>"

        # Output includes wrapper tags that will be removed
        formatted_output = (
            '<?xml version="1.0"?>\n<root>\n'
            "  <ac:structured-macro>\n"
            "    <ac:parameter>Test</ac:parameter>\n"
            "  </ac:structured-macro>\n"
            "</root>\n"
        )
        mock_result = MagicMock()
        mock_result.stdout = formatted_output.encode("utf-8")

        with (
            patch("roundtripper.file_utils.is_xmllint_available", return_value=True),
            patch("subprocess.run", return_value=mock_result),
        ):
            formatted = format_xml(xml)

            assert "ac:structured-macro" in formatted
            assert "ac:parameter" in formatted
            assert "Test" in formatted
            assert "Test" in formatted

    def test_format_xml_with_multiple_root_elements(self) -> None:
        """Test formatting XML fragments with multiple root elements."""
        # This is the scenario from the issue - multiple paragraphs without a single root
        xml = "<p>One</p><p>Two</p>"

        formatted_output = '<?xml version="1.0"?>\n<root>\n  <p>One</p>\n  <p>Two</p>\n</root>\n'
        mock_result = MagicMock()
        mock_result.stdout = formatted_output.encode("utf-8")

        with (
            patch("roundtripper.file_utils.is_xmllint_available", return_value=True),
            patch("subprocess.run", return_value=mock_result),
        ):
            formatted = format_xml(xml)

            # Should have both paragraphs properly formatted
            assert "<p>One</p>" in formatted
            assert "<p>Two</p>" in formatted
            # Should not contain the temporary root wrapper
            assert "<root>" not in formatted
            assert "</root>" not in formatted
            # Should not contain XML declaration
            assert "<?xml" not in formatted


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_simple_filename(self) -> None:
        """Test that simple filenames pass through unchanged."""
        assert sanitize_filename("hello") == "hello"
        assert sanitize_filename("my-page") == "my-page"
        assert sanitize_filename("page_name") == "page_name"

    def test_removes_invalid_characters(self) -> None:
        """Test that invalid characters are replaced."""
        assert sanitize_filename("file<name>") == "file_name_"
        assert sanitize_filename("file:name") == "file_name"
        assert sanitize_filename("file/name") == "file_name"
        assert sanitize_filename("file\\name") == "file_name"
        assert sanitize_filename("file|name") == "file_name"
        assert sanitize_filename("file?name") == "file_name"
        assert sanitize_filename("file*name") == "file_name"
        assert sanitize_filename('file"name') == "file_name"

    def test_trims_trailing_spaces_and_dots(self) -> None:
        """Test that trailing spaces and dots are trimmed."""
        assert sanitize_filename("file.") == "file"
        assert sanitize_filename("file..") == "file"
        assert sanitize_filename("file ") == "file"
        assert sanitize_filename("file  ") == "file"
        assert sanitize_filename("file. ") == "file"

    def test_trims_leading_spaces(self) -> None:
        """Test that leading spaces are trimmed."""
        assert sanitize_filename(" file") == "file"
        assert sanitize_filename("  file") == "file"

    def test_reserved_windows_names(self) -> None:
        """Test that reserved Windows names are prefixed."""
        assert sanitize_filename("CON") == "_CON"
        assert sanitize_filename("PRN") == "_PRN"
        assert sanitize_filename("NUL") == "_NUL"
        assert sanitize_filename("COM1") == "_COM1"
        assert sanitize_filename("LPT1") == "_LPT1"
        assert sanitize_filename("con") == "_con"  # Case-insensitive
        assert sanitize_filename("AUX.txt") == "_AUX.txt"

    def test_empty_filename(self) -> None:
        """Test that empty filenames become underscore."""
        assert sanitize_filename("") == "_"
        assert sanitize_filename("...") == "_"  # Dots stripped, becomes empty
        assert sanitize_filename("   ") == "_"  # Spaces stripped, becomes empty


class TestSaveFile:
    """Tests for save_file function."""

    def test_save_string_content(self, tmp_path: Path) -> None:
        """Test saving string content to file."""
        file_path = tmp_path / "test.txt"
        save_file(file_path, "Hello, World!")

        assert file_path.exists()
        assert file_path.read_text() == "Hello, World!"

    def test_save_bytes_content(self, tmp_path: Path) -> None:
        """Test saving bytes content to file."""
        file_path = tmp_path / "test.bin"
        save_file(file_path, b"\x00\x01\x02\x03")

        assert file_path.exists()
        assert file_path.read_bytes() == b"\x00\x01\x02\x03"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test that parent directories are created."""
        file_path = tmp_path / "a" / "b" / "c" / "test.txt"
        save_file(file_path, "content")

        assert file_path.exists()
        assert file_path.read_text() == "content"

    def test_raises_on_invalid_content_type(self, tmp_path: Path) -> None:
        """Test that invalid content type raises TypeError."""
        file_path = tmp_path / "test.txt"
        with pytest.raises(TypeError, match="Content must be either"):
            save_file(file_path, 123)  # type: ignore[arg-type]


class TestSaveJson:
    """Tests for save_json function."""

    def test_save_simple_dict(self, tmp_path: Path) -> None:
        """Test saving a simple dictionary as JSON."""
        file_path = tmp_path / "test.json"
        save_json(file_path, {"key": "value", "number": 42})

        assert file_path.exists()
        content = file_path.read_text()
        assert '"key": "value"' in content
        assert '"number": 42' in content

    def test_save_nested_dict(self, tmp_path: Path) -> None:
        """Test saving nested dictionary as JSON."""
        file_path = tmp_path / "test.json"
        save_json(file_path, {"outer": {"inner": "value"}})

        assert file_path.exists()
        content = file_path.read_text()
        assert '"outer"' in content
        assert '"inner"' in content


class TestBuildPagePath:
    """Tests for build_page_path function."""

    def test_simple_path(self, tmp_path: Path) -> None:
        """Test building a simple page path."""
        path = build_page_path(tmp_path, "SPACEKEY", [], "My Page")
        assert path == tmp_path / "SPACEKEY" / "My Page"

    def test_path_with_ancestors(self, tmp_path: Path) -> None:
        """Test building path with ancestor pages."""
        path = build_page_path(tmp_path, "SPACE", ["Parent", "Child"], "Grandchild")
        assert path == tmp_path / "SPACE" / "Parent" / "Child" / "Grandchild"

    def test_path_sanitizes_names(self, tmp_path: Path) -> None:
        """Test that page names are sanitized."""
        path = build_page_path(tmp_path, "SPACE", ["Parent/Name"], "Page:Title")
        assert path == tmp_path / "SPACE" / "Parent_Name" / "Page_Title"
