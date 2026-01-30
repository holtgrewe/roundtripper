"""Tests for PushService."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from roundtripper.push_service import PushService, compute_content_hash


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock Confluence client."""
    client = MagicMock()
    client.url = "https://example.atlassian.net/wiki"
    return client


@pytest.fixture
def push_service(mock_client: MagicMock) -> PushService:
    """Create a PushService instance with mock client."""
    return PushService(client=mock_client)


def create_page_directory(
    base_path: Path,
    title: str,
    content: str = "<p>Content</p>",
    page_id: int = 12345,
    version: int = 1,
    space_key: str = "SPACE",
    ancestors: list[dict[str, Any]] | None = None,
) -> Path:
    """Create a page directory with confluence and json files.

    Parameters
    ----------
    base_path
        Base directory to create the page in.
    title
        Page title (used as directory name).
    content
        Page content for page.xml.
    page_id
        Confluence page ID.
    version
        Page version number.
    space_key
        Space key.
    ancestors
        List of ancestor dictionaries.

    Returns
    -------
    Path
        Path to the created page directory.
    """
    page_dir = base_path / title
    page_dir.mkdir(parents=True, exist_ok=True)

    # Create page.xml
    xml_file = page_dir / "page.xml"
    xml_file.write_text(content, encoding="utf-8")

    # Create page.json with metadata
    metadata: dict[str, Any] = {
        "id": str(page_id),
        "title": title,
        "space": {"key": space_key},
        "body": {"storage": {"value": content}},
        "version": {"number": version},
        "ancestors": ancestors or [],
    }
    json_file = page_dir / "page.json"
    json_file.write_text(json.dumps(metadata), encoding="utf-8")

    return page_dir


class TestPushServiceInit:
    """Tests for PushService initialization."""

    def test_default_settings(self, mock_client: MagicMock) -> None:
        """Test default settings are applied."""
        service = PushService(client=mock_client)
        assert service.dry_run is False
        assert service.force is False

    def test_dry_run_flag(self, mock_client: MagicMock) -> None:
        """Test dry run flag is set."""
        service = PushService(client=mock_client, dry_run=True)
        assert service.dry_run is True

    def test_force_flag(self, mock_client: MagicMock) -> None:
        """Test force flag is set."""
        service = PushService(client=mock_client, force=True)
        assert service.force is True


class TestPushPage:
    """Tests for pushing a single page."""

    def test_push_page_unchanged(
        self, push_service: PushService, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Test that unchanged pages are skipped."""
        page_dir = create_page_directory(tmp_path, "Test Page")

        result = push_service.push_page(page_dir)

        assert result.pages_skipped == 1
        assert result.pages_updated == 0
        mock_client.update_page.assert_not_called()

    def test_push_page_changed(
        self, push_service: PushService, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Test pushing a modified page."""
        # Create page with stored content
        page_dir = create_page_directory(tmp_path, "Test Page", content="<p>Original</p>")

        # Modify the local content
        xml_file = page_dir / "page.xml"
        xml_file.write_text("<p>Modified content</p>", encoding="utf-8")

        # Mock version check
        mock_client.get_page_by_id.return_value = {"version": {"number": 1}}

        result = push_service.push_page(page_dir)

        assert result.pages_updated == 1
        assert result.pages_skipped == 0
        mock_client.update_page.assert_called_once()

    def test_push_page_dry_run(self, mock_client: MagicMock, tmp_path: Path) -> None:
        """Test dry run doesn't actually push."""
        service = PushService(client=mock_client, dry_run=True)
        page_dir = create_page_directory(tmp_path, "Test Page", content="<p>Original</p>")

        # Modify the local content
        xml_file = page_dir / "page.xml"
        xml_file.write_text("<p>Modified content</p>", encoding="utf-8")

        # Mock version check
        mock_client.get_page_by_id.return_value = {"version": {"number": 1}}

        result = service.push_page(page_dir)

        # No update in dry run, but change should be detected
        assert result.pages_updated == 0
        assert result.pages_skipped == 0
        mock_client.update_page.assert_not_called()

    def test_push_page_version_conflict(
        self, push_service: PushService, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Test version conflict detection."""
        page_dir = create_page_directory(
            tmp_path, "Test Page", content="<p>Original</p>", version=1
        )

        # Modify the local content
        xml_file = page_dir / "page.xml"
        xml_file.write_text("<p>Modified content</p>", encoding="utf-8")

        # Server has newer version
        mock_client.get_page_by_id.return_value = {"version": {"number": 3}}

        result = push_service.push_page(page_dir)

        assert len(result.conflicts) == 1
        assert "local version 1" in result.conflicts[0]
        assert "server version 3" in result.conflicts[0]
        mock_client.update_page.assert_not_called()

    def test_push_page_force_conflict(self, mock_client: MagicMock, tmp_path: Path) -> None:
        """Test force push ignores conflicts."""
        service = PushService(client=mock_client, force=True)
        page_dir = create_page_directory(
            tmp_path, "Test Page", content="<p>Original</p>", version=1
        )

        # Modify the local content
        xml_file = page_dir / "page.xml"
        xml_file.write_text("<p>Modified content</p>", encoding="utf-8")

        # Server has newer version
        mock_client.get_page_by_id.return_value = {"version": {"number": 3}}

        result = service.push_page(page_dir)

        assert len(result.conflicts) == 0
        assert result.pages_updated == 1
        mock_client.update_page.assert_called_once()

    def test_push_page_missing_files(self, push_service: PushService, tmp_path: Path) -> None:
        """Test handling of missing page files."""
        empty_dir = tmp_path / "Empty Page"
        empty_dir.mkdir()

        result = push_service.push_page(empty_dir)

        assert result.pages_skipped == 0
        assert result.pages_updated == 0

    def test_push_page_version_check_exception(
        self, push_service: PushService, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Test that version check exceptions don't block the push."""
        page_dir = create_page_directory(
            tmp_path, "Test Page", content="<p>Original</p>", version=1
        )

        # Modify the local content
        xml_file = page_dir / "page.xml"
        xml_file.write_text("<p>Modified content</p>", encoding="utf-8")

        # Version check fails with exception (get_page_by_id is used for version check)
        # but update_page succeeds
        mock_client.get_page_by_id.side_effect = Exception("Network error")
        mock_client.update_page.return_value = {}

        result = push_service.push_page(page_dir)

        # Version check exception is caught and logged, update proceeds
        assert result.errors == []
        assert result.pages_updated == 1
        mock_client.update_page.assert_called_once()

    def test_push_page_recursive(
        self, push_service: PushService, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Test recursive page pushing."""
        # Create parent page
        parent_dir = create_page_directory(
            tmp_path, "Parent Page", content="<p>Parent</p>", page_id=1
        )

        # Create child page
        child_dir = create_page_directory(
            parent_dir, "Child Page", content="<p>Child Original</p>", page_id=2
        )

        # Modify the child content
        child_confluence = child_dir / "page.xml"
        child_confluence.write_text("<p>Child Modified</p>", encoding="utf-8")

        # Mock version checks
        mock_client.get_page_by_id.return_value = {"version": {"number": 1}}

        result = push_service.push_page(parent_dir, recursive=True)

        # Parent unchanged, child changed
        assert result.pages_skipped == 1
        assert result.pages_updated == 1


class TestPushSpace:
    """Tests for pushing an entire space."""

    def test_push_space_multiple_pages(
        self, push_service: PushService, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Test pushing multiple pages in a space."""
        space_dir = tmp_path / "SPACE"
        space_dir.mkdir()

        # Create pages with different states
        create_page_directory(space_dir, "Page 1", content="<p>Page 1</p>", page_id=1)
        page2_dir = create_page_directory(
            space_dir, "Page 2", content="<p>Page 2 Original</p>", page_id=2
        )

        # Modify page 2
        page2_confluence = page2_dir / "page.xml"
        page2_confluence.write_text("<p>Page 2 Modified</p>", encoding="utf-8")

        # Mock version checks
        mock_client.get_page_by_id.return_value = {"version": {"number": 1}}

        result = push_service.push_space(space_dir)

        assert result.pages_skipped == 1  # Page 1 unchanged
        assert result.pages_updated == 1  # Page 2 modified


class TestPushAttachments:
    """Tests for attachment handling."""

    def test_push_new_attachment(
        self, push_service: PushService, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Test pushing a new attachment."""
        page_dir = create_page_directory(tmp_path, "Test Page")

        # Create attachments directory with a new file
        attachments_dir = page_dir / "attachments"
        attachments_dir.mkdir()

        attachment_file = attachments_dir / "test.pdf"
        attachment_file.write_bytes(b"PDF content")

        # Modify page to trigger push
        xml_file = page_dir / "page.xml"
        xml_file.write_text("<p>Modified</p>", encoding="utf-8")

        mock_client.get_page_by_id.return_value = {"version": {"number": 1}}

        result = push_service.push_page(page_dir)

        assert result.attachments_uploaded == 1
        mock_client.attach_file.assert_called_once()

    def test_push_unchanged_attachment(
        self, push_service: PushService, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Test that unchanged attachments are skipped."""
        page_dir = create_page_directory(tmp_path, "Test Page")

        # Create attachments directory with file and metadata
        attachments_dir = page_dir / "attachments"
        attachments_dir.mkdir()

        attachment_file = attachments_dir / "test.pdf"
        attachment_content = b"PDF content"
        attachment_file.write_bytes(attachment_content)

        # Create metadata with matching size
        metadata_file = attachments_dir / "test.pdf.json"
        metadata: dict[str, Any] = {"extensions": {"fileSize": len(attachment_content)}}
        metadata_file.write_text(json.dumps(metadata), encoding="utf-8")

        # Modify page to trigger push
        xml_file = page_dir / "page.xml"
        xml_file.write_text("<p>Modified</p>", encoding="utf-8")

        mock_client.get_page_by_id.return_value = {"version": {"number": 1}}

        result = push_service.push_page(page_dir)

        assert result.attachments_skipped == 1
        assert result.attachments_uploaded == 0
        mock_client.attach_file.assert_not_called()

    def test_push_modified_attachment(
        self, push_service: PushService, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Test pushing a modified attachment."""
        page_dir = create_page_directory(tmp_path, "Test Page")

        # Create attachments directory with file and metadata
        attachments_dir = page_dir / "attachments"
        attachments_dir.mkdir()

        attachment_file = attachments_dir / "test.pdf"
        attachment_file.write_bytes(b"New content - longer than before")

        # Create metadata with different (smaller) size
        metadata_file = attachments_dir / "test.pdf.json"
        metadata: dict[str, Any] = {"extensions": {"fileSize": 10}}
        metadata_file.write_text(json.dumps(metadata), encoding="utf-8")

        # Modify page to trigger push
        xml_file = page_dir / "page.xml"
        xml_file.write_text("<p>Modified</p>", encoding="utf-8")

        mock_client.get_page_by_id.return_value = {"version": {"number": 1}}

        result = push_service.push_page(page_dir)

        assert result.attachments_uploaded == 1
        mock_client.attach_file.assert_called_once()


class TestErrorHandling:
    """Tests for error handling."""

    def test_handles_api_error_gracefully(
        self, push_service: PushService, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Test that API errors are caught and recorded."""
        page_dir = create_page_directory(tmp_path, "Test Page", content="<p>Original</p>")

        # Modify content
        xml_file = page_dir / "page.xml"
        xml_file.write_text("<p>Modified</p>", encoding="utf-8")

        # Mock version check success but update failure
        mock_client.get_page_by_id.return_value = {"version": {"number": 1}}
        mock_client.update_page.side_effect = Exception("API Error")

        result = push_service.push_page(page_dir)

        assert len(result.errors) == 1
        assert "API Error" in result.errors[0]


class TestFindPages:
    """Tests for finding pages in directory structure."""

    def test_find_child_pages(self, push_service: PushService, tmp_path: Path) -> None:
        """Test finding child pages recursively."""
        parent_dir = create_page_directory(tmp_path, "Parent")
        child1_dir = create_page_directory(parent_dir, "Child 1")
        child2_dir = create_page_directory(parent_dir, "Child 2")
        grandchild_dir = create_page_directory(child1_dir, "Grandchild")

        children = push_service._find_child_pages(parent_dir)

        assert len(children) == 3
        assert child1_dir in children
        assert child2_dir in children
        assert grandchild_dir in children

    def test_find_all_pages_in_space(self, push_service: PushService, tmp_path: Path) -> None:
        """Test finding all pages in a space directory."""
        space_dir = tmp_path / "SPACE"
        space_dir.mkdir()

        page1_dir = create_page_directory(space_dir, "Page 1")
        page2_dir = create_page_directory(space_dir, "Page 2")
        nested_dir = create_page_directory(page1_dir, "Nested Page")

        all_pages = push_service._find_all_pages(space_dir)

        assert len(all_pages) == 3
        assert page1_dir in all_pages
        assert page2_dir in all_pages
        assert nested_dir in all_pages


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_compute_content_hash(self) -> None:
        """Test content hash computation."""
        content = "Hello, World!"
        hash1 = compute_content_hash(content)
        hash2 = compute_content_hash(content)
        hash3 = compute_content_hash("Different content")

        assert hash1 == hash2
        assert hash1 != hash3
        assert len(hash1) == 64  # SHA256 hex digest length


class TestDryRunBehavior:
    """Tests specifically for dry-run behavior."""

    def test_dry_run_with_attachments(self, mock_client: MagicMock, tmp_path: Path) -> None:
        """Test dry run with attachment changes."""
        service = PushService(client=mock_client, dry_run=True)
        page_dir = create_page_directory(tmp_path, "Test Page", content="<p>Original</p>")

        # Modify content
        xml_file = page_dir / "page.xml"
        xml_file.write_text("<p>Modified</p>", encoding="utf-8")

        # Add new attachment
        attachments_dir = page_dir / "attachments"
        attachments_dir.mkdir()
        (attachments_dir / "new.pdf").write_bytes(b"content")

        mock_client.get_page_by_id.return_value = {"version": {"number": 1}}

        service.push_page(page_dir)

        # No actual updates should happen
        mock_client.update_page.assert_not_called()
        mock_client.attach_file.assert_not_called()

    def test_dry_run_shows_conflicts(self, mock_client: MagicMock, tmp_path: Path) -> None:
        """Test dry run still detects conflicts."""
        service = PushService(client=mock_client, dry_run=True, force=True)
        page_dir = create_page_directory(
            tmp_path, "Test Page", content="<p>Original</p>", version=1
        )

        # Modify content
        xml_file = page_dir / "page.xml"
        xml_file.write_text("<p>Modified</p>", encoding="utf-8")

        # Server has newer version
        mock_client.get_page_by_id.return_value = {"version": {"number": 5}}

        result = service.push_page(page_dir)

        # With force=True, no conflicts recorded (would be pushed)
        assert len(result.conflicts) == 0
        mock_client.update_page.assert_not_called()
