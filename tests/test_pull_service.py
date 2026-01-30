"""Tests for PullService."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from roundtripper.pull_service import PullService


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock Confluence client."""
    client = MagicMock()
    client.url = "https://example.atlassian.net/wiki"
    return client


@pytest.fixture
def pull_service(mock_client: MagicMock, tmp_path: Path) -> PullService:
    """Create a PullService instance with mock client."""
    return PullService(client=mock_client, output_dir=tmp_path)


class TestPullServiceInit:
    """Tests for PullService initialization."""

    def test_custom_output_dir(self, mock_client: MagicMock, tmp_path: Path) -> None:
        """Test custom output directory is set."""
        service = PullService(client=mock_client, output_dir=tmp_path)
        assert service.output_dir == tmp_path

    def test_dry_run_flag(self, mock_client: MagicMock, tmp_path: Path) -> None:
        """Test dry run flag is set."""
        service = PullService(client=mock_client, output_dir=tmp_path, dry_run=True)
        assert service.dry_run is True


class TestPullPage:
    """Tests for pulling a single page."""

    def test_pull_page_basic(
        self, pull_service: PullService, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Test pulling a single page."""
        page_data: dict[str, Any] = {
            "id": "12345",
            "title": "Test Page",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": "<p>Content</p>"}},
            "version": {"number": 1},
            "ancestors": [],
        }
        mock_client.get_page_by_id.return_value = page_data
        mock_client.get_attachments_from_content.return_value = {"results": []}

        result = pull_service.pull_page(page_id=12345)

        assert result.pages_downloaded == 1
        assert result.attachments_downloaded == 0
        # Note: spaces preserved in directory names
        assert (tmp_path / "SPACE" / "Test Page" / "page.confluence").exists()
        assert (tmp_path / "SPACE" / "Test Page" / "page.json").exists()

    def test_pull_page_with_ancestors(
        self, pull_service: PullService, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Test pulling page with ancestor path."""
        page_data: dict[str, Any] = {
            "id": "12345",
            "title": "Child Page",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": "<p>Content</p>"}},
            "version": {"number": 1},
            "ancestors": [
                {"id": "1"},  # Just IDs in the ancestors
                {"id": "2"},
            ],
        }

        # Mock both the main page fetch and ancestor lookups
        def get_page_by_id_side_effect(page_id: int | str, expand: str = "") -> dict[str, Any]:
            page_id_str = str(page_id)
            if page_id_str == "12345":
                return page_data
            if page_id_str == "1":
                return {"id": "1", "title": "Root"}
            if page_id_str == "2":
                return {"id": "2", "title": "Parent"}
            return {"id": page_id_str, "title": f"Page-{page_id}"}

        mock_client.get_page_by_id.side_effect = get_page_by_id_side_effect
        mock_client.get_attachments_from_content.return_value = {"results": []}

        result = pull_service.pull_page(page_id=12345)

        assert result.pages_downloaded == 1
        expected_path = tmp_path / "SPACE" / "Root" / "Parent" / "Child Page"
        assert (expected_path / "page.confluence").exists()

    def test_pull_page_dry_run(self, mock_client: MagicMock, tmp_path: Path) -> None:
        """Test dry run doesn't write files."""
        service = PullService(client=mock_client, output_dir=tmp_path, dry_run=True)
        page_data: dict[str, Any] = {
            "id": "12345",
            "title": "Test Page",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": "<p>Content</p>"}},
            "version": {"number": 1},
            "ancestors": [],
        }
        mock_client.get_page_by_id.return_value = page_data
        mock_client.get_attachments_from_content.return_value = {"results": []}

        result = service.pull_page(page_id=12345)

        assert result.pages_downloaded == 1
        assert not (tmp_path / "SPACE").exists()

    def test_pull_page_skips_unchanged(self, mock_client: MagicMock, tmp_path: Path) -> None:
        """Test that unchanged pages are skipped on re-pull."""
        page_data: dict[str, Any] = {
            "id": "12345",
            "title": "Test Page",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": "<p>Content</p>"}},
            "version": {"number": 1},
            "ancestors": [],
        }
        mock_client.get_page_by_id.return_value = page_data
        mock_client.get_attachments_from_content.return_value = {"results": []}

        # First pull downloads the page
        service1 = PullService(client=mock_client, output_dir=tmp_path)
        result1 = service1.pull_page(page_id=12345)
        assert result1.pages_downloaded == 1
        assert result1.pages_skipped == 0

        # Second pull should skip (same version already exists)
        service2 = PullService(client=mock_client, output_dir=tmp_path)
        result2 = service2.pull_page(page_id=12345)
        assert result2.pages_skipped == 1
        assert result2.pages_downloaded == 0

    def test_pull_page_recursive(
        self, pull_service: PullService, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Test recursive page pulling."""
        parent_data: dict[str, Any] = {
            "id": "100",
            "title": "Parent",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": "<p>Parent</p>"}},
            "version": {"number": 1},
            "ancestors": [],
        }
        child_data: dict[str, Any] = {
            "id": "200",
            "title": "Child",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": "<p>Child</p>"}},
            "version": {"number": 1},
            "ancestors": [{"id": "100"}],
        }

        # Mock the descendant search API (used by _get_all_descendant_ids)
        mock_client.get.return_value = {
            "results": [{"id": "200"}],
            "_links": {},  # No 'next' link = single page of results
        }

        # Mock page fetches - need more entries for ancestor lookup
        def get_page_by_id_side_effect(page_id: int | str, expand: str = "") -> dict[str, Any]:
            page_id_str = str(page_id)
            if page_id_str == "100":
                return parent_data
            if page_id_str == "200":
                return child_data
            return {"id": page_id_str, "title": f"Page-{page_id}"}

        mock_client.get_page_by_id.side_effect = get_page_by_id_side_effect
        mock_client.get_attachments_from_content.return_value = {"results": []}

        result = pull_service.pull_page(page_id=100, recursive=True)

        assert result.pages_downloaded == 2


class TestPullAttachments:
    """Tests for pulling attachments."""

    def test_pull_attachments(
        self, pull_service: PullService, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Test pulling attachments for a page."""
        page_data: dict[str, Any] = {
            "id": "12345",
            "title": "Test Page",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": "<p>Content</p>"}},
            "version": {"number": 1},
            "ancestors": [],
        }
        attachment_data: dict[str, Any] = {
            "results": [
                {
                    "id": "att1",
                    "title": "file.pdf",
                    "extensions": {"fileSize": 1024, "mediaType": "application/pdf"},
                    "_links": {"download": "/download/attachments/12345/file.pdf"},
                    "version": {"number": 1},
                }
            ]
        }

        mock_client.get_page_by_id.return_value = page_data
        mock_client.get_attachments_from_content.return_value = attachment_data
        # Mock the session.get() for downloading attachments
        mock_response = MagicMock()
        mock_response.content = b"file content"
        mock_client._session.get.return_value = mock_response

        result = pull_service.pull_page(page_id=12345)

        assert result.attachments_downloaded == 1
        attachment_path = tmp_path / "SPACE" / "Test Page" / "attachments" / "file.pdf"
        assert attachment_path.exists()

    def test_skip_unchanged_attachments(self, mock_client: MagicMock, tmp_path: Path) -> None:
        """Test that unchanged attachments are skipped."""
        page_data: dict[str, Any] = {
            "id": "12345",
            "title": "Test Page",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": "<p>Content</p>"}},
            "version": {"number": 1},
            "ancestors": [],
        }
        attachment_data: dict[str, Any] = {
            "results": [
                {
                    "id": "att1",
                    "title": "file.pdf",
                    "extensions": {"fileSize": 1024, "mediaType": "application/pdf"},
                    "_links": {"download": "/download/attachments/12345/file.pdf"},
                    "version": {"number": 1},
                }
            ]
        }

        mock_client.get_page_by_id.return_value = page_data
        mock_client.get_attachments_from_content.return_value = attachment_data
        # Mock the session.get() for downloading attachments
        mock_response = MagicMock()
        mock_response.content = b"file content"
        mock_client._session.get.return_value = mock_response

        # First pull downloads the page and attachment
        service1 = PullService(client=mock_client, output_dir=tmp_path)
        service1.pull_page(page_id=12345)

        # Second pull should skip attachment (same version)
        mock_client.get_page_by_id.return_value = {
            **page_data,
            "version": {"number": 2},  # New page version
        }
        service2 = PullService(client=mock_client, output_dir=tmp_path)
        result = service2.pull_page(page_id=12345)

        assert result.attachments_skipped == 1


class TestPullSpace:
    """Tests for pulling an entire space."""

    def test_pull_space_basic(
        self, pull_service: PullService, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Test pulling all pages from a space."""
        space_data = {"key": "SPACE", "name": "Test Space", "homepage": {"id": "100"}}
        page_data: dict[str, Any] = {
            "id": "100",
            "title": "Home",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": "<p>Home</p>"}},
            "version": {"number": 1},
            "ancestors": [],
        }

        mock_client.get_space.return_value = space_data
        # Mock descendant search - no descendants for home page
        mock_client.get.return_value = {"results": [], "_links": {}}
        mock_client.get_page_by_id.return_value = page_data
        mock_client.get_attachments_from_content.return_value = {"results": []}

        result = pull_service.pull_space(space_key="SPACE")

        assert result.pages_downloaded == 1

    def test_pull_space_no_homepage(
        self, pull_service: PullService, mock_client: MagicMock
    ) -> None:
        """Test pulling a space with no homepage returns early."""
        space_data = {"key": "SPACE", "name": "Test Space"}
        mock_client.get_space.return_value = space_data

        result = pull_service.pull_space(space_key="SPACE")

        # Should return with no pages downloaded since no homepage
        assert result.pages_downloaded == 0


class TestErrorHandling:
    """Tests for error handling in PullService."""

    def test_handles_api_error_gracefully(
        self, pull_service: PullService, mock_client: MagicMock
    ) -> None:
        """Test that API errors are captured in result."""
        mock_client.get_page_by_id.side_effect = Exception("API Error")

        result = pull_service.pull_page(page_id=12345)

        assert result.pages_downloaded == 0
        assert len(result.errors) == 1
        assert "API Error" in result.errors[0]

    def test_handles_attachment_download_error(
        self, pull_service: PullService, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Test that attachment download errors don't stop page pull."""
        page_data: dict[str, Any] = {
            "id": "12345",
            "title": "Test Page",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": "<p>Content</p>"}},
            "version": {"number": 1},
            "ancestors": [],
        }
        attachment_data: dict[str, Any] = {
            "results": [
                {
                    "id": "att1",
                    "title": "file.pdf",
                    "extensions": {},
                    "_links": {"download": "/download/file.pdf"},
                    "version": {"number": 1},
                }
            ]
        }

        mock_client.get_page_by_id.return_value = page_data
        mock_client.get_attachments_from_content.return_value = attachment_data
        # Mock the session.get() to fail on download
        mock_client._session.get.side_effect = Exception("Download failed")

        result = pull_service.pull_page(page_id=12345)

        assert result.pages_downloaded == 1
        assert result.attachments_downloaded == 0
        assert len(result.errors) == 1

    def test_handles_descendant_fetch_error(
        self, pull_service: PullService, mock_client: MagicMock
    ) -> None:
        """Test that errors fetching descendants are handled gracefully."""
        mock_client.get.side_effect = Exception("CQL query failed")

        # Pull with recursive=True triggers _get_all_descendant_ids
        page_data: dict[str, Any] = {
            "id": "100",
            "title": "Page",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": ""}},
            "version": {"number": 1},
            "ancestors": [],
        }
        mock_client.get_page_by_id.return_value = page_data
        mock_client.get_attachments_from_content.return_value = {"results": []}

        result = pull_service.pull_page(page_id=100, recursive=True)

        # Should still pull the main page despite descendant fetch error
        assert result.pages_downloaded == 1


class TestPagination:
    """Tests for pagination handling in PullService."""

    def test_descendant_pagination(
        self, pull_service: PullService, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Test that descendant search handles pagination correctly."""
        # First response has a 'next' link
        first_response = {
            "results": [{"id": "200"}],
            "_links": {"next": "/rest/api/content/search?cursor=abc"},
        }
        # Second response has no 'next' link
        second_response = {
            "results": [{"id": "300"}],
            "_links": {},
        }
        mock_client.get.side_effect = [first_response, second_response]

        page_100: dict[str, Any] = {
            "id": "100",
            "title": "Parent",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": ""}},
            "version": {"number": 1},
            "ancestors": [],
        }
        page_200: dict[str, Any] = {
            "id": "200",
            "title": "Child 1",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": ""}},
            "version": {"number": 1},
            "ancestors": [{"id": "100"}],
        }
        page_300: dict[str, Any] = {
            "id": "300",
            "title": "Child 2",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": ""}},
            "version": {"number": 1},
            "ancestors": [{"id": "100"}],
        }

        def get_page_by_id_side_effect(page_id: int | str, expand: str = "") -> dict[str, Any]:
            page_id_str = str(page_id)
            if page_id_str == "100":
                return page_100
            if page_id_str == "200":
                return page_200
            if page_id_str == "300":
                return page_300
            return {"id": page_id_str, "title": f"Page-{page_id}"}

        mock_client.get_page_by_id.side_effect = get_page_by_id_side_effect
        mock_client.get_attachments_from_content.return_value = {"results": []}

        result = pull_service.pull_page(page_id=100, recursive=True)

        # Should pull all 3 pages (parent + 2 children from paginated results)
        assert result.pages_downloaded == 3

    def test_attachment_pagination(
        self, pull_service: PullService, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Test that attachment fetching handles pagination correctly."""
        page_data: dict[str, Any] = {
            "id": "12345",
            "title": "Test Page",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": "<p>Content</p>"}},
            "version": {"number": 1},
            "ancestors": [],
        }
        # First response with size < limit (should break pagination)
        attachment_data: dict[str, Any] = {
            "results": [
                {
                    "id": "att1",
                    "title": "file1.pdf",
                    "extensions": {},
                    "_links": {"download": "/download/file1.pdf"},
                    "version": {"number": 1},
                }
            ],
            "size": 1,  # Less than the limit of 50, triggers break
        }

        mock_client.get_page_by_id.return_value = page_data
        mock_client.get_attachments_from_content.return_value = attachment_data

        mock_response = MagicMock()
        mock_response.content = b"file content"
        mock_client._session.get.return_value = mock_response

        result = pull_service.pull_page(page_id=12345)

        assert result.pages_downloaded == 1
        assert result.attachments_downloaded == 1
        # Verify get_attachments_from_content was only called once
        assert mock_client.get_attachments_from_content.call_count == 1

    def test_attachment_pagination_multiple_pages(
        self, pull_service: PullService, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Test that attachment fetching continues when size >= limit."""
        page_data: dict[str, Any] = {
            "id": "12345",
            "title": "Test Page",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": "<p>Content</p>"}},
            "version": {"number": 1},
            "ancestors": [],
        }
        # First response with size == limit (should continue)
        first_attachment_response: dict[str, Any] = {
            "results": [
                {
                    "id": "att1",
                    "title": "file1.pdf",
                    "extensions": {},
                    "_links": {"download": "/download/file1.pdf"},
                    "version": {"number": 1},
                }
            ],
            "size": 50,  # Equal to limit, should continue to next page
        }
        # Second response with size < limit (should break)
        second_attachment_response: dict[str, Any] = {
            "results": [
                {
                    "id": "att2",
                    "title": "file2.pdf",
                    "extensions": {},
                    "_links": {"download": "/download/file2.pdf"},
                    "version": {"number": 1},
                }
            ],
            "size": 1,  # Less than limit, triggers break on line 307
        }

        mock_client.get_page_by_id.return_value = page_data
        mock_client.get_attachments_from_content.side_effect = [
            first_attachment_response,
            second_attachment_response,
        ]

        mock_response = MagicMock()
        mock_response.content = b"file content"
        mock_client._session.get.return_value = mock_response

        result = pull_service.pull_page(page_id=12345)

        assert result.pages_downloaded == 1
        assert result.attachments_downloaded == 2
        # Should have been called twice - once for each page
        assert mock_client.get_attachments_from_content.call_count == 2
