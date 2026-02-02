"""Tests for DiffService."""

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from roundtripper.diff_service import DiffService
from roundtripper.models import DiffResult


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock Confluence client."""
    client = MagicMock()
    client.url = "https://example.atlassian.net/wiki"
    return client


@pytest.fixture
def local_content_dir(tmp_path: Path) -> Path:
    """Create a local content directory structure."""
    local_dir = tmp_path / "local"
    page_dir = local_dir / "SPACE" / "Test Page"
    page_dir.mkdir(parents=True)

    # Create page.xml and page.json
    (page_dir / "page.xml").write_text("<p>Local content</p>")
    (page_dir / "page.json").write_text('{"id": "12345", "version": {"number": 1}}')

    return local_dir


@pytest.fixture
def diff_service(mock_client: MagicMock, local_content_dir: Path) -> DiffService:
    """Create a DiffService instance with mock client."""
    return DiffService(client=mock_client, local_path=local_content_dir)


class TestDiffServiceInit:
    """Tests for DiffService initialization."""

    def test_initialization(self, mock_client: MagicMock, local_content_dir: Path) -> None:
        """Test service initialization."""
        service = DiffService(client=mock_client, local_path=local_content_dir)
        assert service.client == mock_client
        assert service.local_path == local_content_dir
        assert isinstance(service.result, DiffResult)


class TestDiffSpace:
    """Tests for diffing a space."""

    def test_diff_space_no_changes(
        self,
        diff_service: DiffService,
        mock_client: MagicMock,
        local_content_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        """Test diffing when there are no changes."""
        # Mock get_space and related calls
        space_data: dict[str, Any] = {
            "key": "SPACE",
            "name": "Test Space",
            "homepage": {"id": "12345"},
        }
        mock_client.get_space.return_value = space_data

        page_data: dict[str, Any] = {
            "id": "12345",
            "title": "Test Page",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": "<p>Local content</p>"}},
            "version": {"number": 1},
            "ancestors": [],
        }
        mock_client.get_page_by_id.return_value = page_data

        # Mock search for descendants
        mock_client.get.return_value = {"results": [], "_links": {}}

        # Mock attachments
        mock_client.get_attachments_from_content.return_value = {"results": []}

        # Mock subprocess.run for diff command
        mock_run = mocker.patch("subprocess.run")
        # diff returns 0 when there are no changes
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = diff_service.diff_space("SPACE")

        assert result.has_differences is False
        assert len(result.errors) == 0

    def test_diff_space_with_changes(
        self,
        diff_service: DiffService,
        mock_client: MagicMock,
        local_content_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        """Test diffing when there are changes."""
        # Mock get_space and related calls
        space_data: dict[str, Any] = {
            "key": "SPACE",
            "name": "Test Space",
            "homepage": {"id": "12345"},
        }
        mock_client.get_space.return_value = space_data

        page_data: dict[str, Any] = {
            "id": "12345",
            "title": "Test Page",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": "<p>Remote content changed</p>"}},
            "version": {"number": 2},
            "ancestors": [],
        }
        mock_client.get_page_by_id.return_value = page_data

        # Mock search for descendants
        mock_client.get.return_value = {"results": [], "_links": {}}

        # Mock attachments
        mock_client.get_attachments_from_content.return_value = {"results": []}

        # Mock subprocess.run for diff command
        mock_run = mocker.patch("subprocess.run")
        # diff returns 1 when there are changes
        diff_output = (
            "--- local/SPACE/Test Page/page.xml\n"
            "+++ remote/SPACE/Test Page/page.xml\n"
            "@@ -1 +1 @@\n"
            "-<p>Local content</p>\n"
            "+<p>Remote content changed</p>\n"
        )
        mock_run.return_value = MagicMock(returncode=1, stdout=diff_output, stderr="")

        # Mock Popen for pager
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        result = diff_service.diff_space("SPACE")

        assert result.has_differences is True
        assert len(result.errors) == 0
        # Verify pager was called
        mock_popen.assert_called_once()

    def test_diff_space_pull_errors(
        self,
        diff_service: DiffService,
        mock_client: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """Test diffing when pull encounters errors."""
        # Mock get_space
        space_data: dict[str, Any] = {
            "key": "SPACE",
            "name": "Test Space",
            "homepage": {"id": "12345"},
        }
        mock_client.get_space.return_value = space_data

        # Mock page fetch to fail
        mock_client.get_page_by_id.side_effect = Exception("API Error")

        # Mock search for descendants
        mock_client.get.return_value = {"results": [], "_links": {}}

        # Mock subprocess.run for diff command
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = diff_service.diff_space("SPACE")

        # Pull errors should be captured
        assert len(result.errors) > 0


class TestDiffPage:
    """Tests for diffing a single page."""

    def test_diff_page_no_changes(
        self,
        diff_service: DiffService,
        mock_client: MagicMock,
        local_content_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        """Test diffing a single page with no changes."""
        page_data: dict[str, Any] = {
            "id": "12345",
            "title": "Test Page",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": "<p>Local content</p>"}},
            "version": {"number": 1},
            "ancestors": [],
        }
        mock_client.get_page_by_id.return_value = page_data

        # Mock attachments
        mock_client.get_attachments_from_content.return_value = {"results": []}

        # Mock subprocess.run for diff command
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = diff_service.diff_page(12345)

        assert result.has_differences is False
        assert len(result.errors) == 0

    def test_diff_page_recursive(
        self,
        diff_service: DiffService,
        mock_client: MagicMock,
        local_content_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        """Test diffing a page with recursive option."""
        parent_data: dict[str, Any] = {
            "id": "12345",
            "title": "Test Page",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": "<p>Local content</p>"}},
            "version": {"number": 1},
            "ancestors": [],
        }

        # Child page
        child_data: dict[str, Any] = {
            "id": "67890",
            "title": "Child Page",
            "space": {"key": "SPACE"},
            "body": {"storage": {"value": "<p>Child content</p>"}},
            "version": {"number": 1},
            "ancestors": [{"id": "12345"}],
        }

        def get_page_by_id_side_effect(page_id: int | str, expand: str = "") -> dict[str, Any]:
            if str(page_id) == "12345":
                return parent_data
            if str(page_id) == "67890":
                return child_data
            return {}

        mock_client.get_page_by_id.side_effect = get_page_by_id_side_effect

        # Mock search for descendants
        mock_client.get.return_value = {
            "results": [{"id": "67890"}],
            "_links": {},
        }

        # Mock attachments
        mock_client.get_attachments_from_content.return_value = {"results": []}

        # Mock subprocess.run for diff command
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = diff_service.diff_page(12345, recursive=True)

        assert result.has_differences is False
        assert len(result.errors) == 0


class TestRunDiff:
    """Tests for the internal _run_diff method."""

    def test_diff_command_failure(
        self,
        diff_service: DiffService,
        local_content_dir: Path,
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """Test when diff command fails."""
        remote_dir = tmp_path / "remote"
        remote_dir.mkdir()

        # Mock subprocess.run to simulate diff failure (returncode > 1)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=2,
            stdout="",
            stderr="diff: error occurred",
        )

        diff_service._run_diff(local_content_dir, remote_dir)

        assert len(diff_service.result.errors) > 0
        assert "Diff command failed" in diff_service.result.errors[0]

    def test_diff_command_timeout(
        self,
        diff_service: DiffService,
        local_content_dir: Path,
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """Test when diff command times out."""
        remote_dir = tmp_path / "remote"
        remote_dir.mkdir()

        # Mock subprocess.run to raise TimeoutExpired
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = subprocess.TimeoutExpired("diff", 30)

        diff_service._run_diff(local_content_dir, remote_dir)

        assert len(diff_service.result.errors) > 0
        assert "timed out" in diff_service.result.errors[0]

    def test_diff_command_not_found(
        self,
        diff_service: DiffService,
        local_content_dir: Path,
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """Test when diff command is not found."""
        remote_dir = tmp_path / "remote"
        remote_dir.mkdir()

        # Mock subprocess.run to raise FileNotFoundError
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = FileNotFoundError()
        mock_run.side_effect.filename = "diff"

        diff_service._run_diff(local_content_dir, remote_dir)

        assert len(diff_service.result.errors) > 0
        assert "not found" in diff_service.result.errors[0]

    def test_pager_fallback(
        self,
        diff_service: DiffService,
        local_content_dir: Path,
        tmp_path: Path,
        mocker: MockerFixture,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test fallback to direct print when pager fails."""
        remote_dir = tmp_path / "remote"
        remote_dir.mkdir()

        diff_output = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new\n"

        # Mock subprocess.run for diff command
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=1, stdout=diff_output, stderr="")

        # Mock Popen for pager to fail
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = MagicMock()
        mock_process.returncode = 1  # Pager failed
        mock_popen.return_value = mock_process

        diff_service._run_diff(local_content_dir, remote_dir)

        # Should have fallen back to direct print
        captured = capsys.readouterr()
        assert diff_output in captured.out

    def test_custom_pager_env(
        self,
        diff_service: DiffService,
        local_content_dir: Path,
        tmp_path: Path,
        mocker: MockerFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test using custom pager from environment."""
        remote_dir = tmp_path / "remote"
        remote_dir.mkdir()

        # Set custom pager
        monkeypatch.setenv("PAGER", "cat")

        diff_output = "--- a/file.txt\n+++ b/file.txt\n"

        # Mock subprocess.run for diff command
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=1, stdout=diff_output, stderr="")

        # Mock Popen for pager
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        diff_service._run_diff(local_content_dir, remote_dir)

        # Verify pager was called with "cat" command
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        assert call_args[0][0] == ["cat"]

    def test_diff_generic_exception(
        self,
        diff_service: DiffService,
        local_content_dir: Path,
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """Test handling of generic exceptions during diff."""
        remote_dir = tmp_path / "remote"
        remote_dir.mkdir()

        # Mock subprocess.run to raise a generic exception
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = RuntimeError("Unexpected error")

        diff_service._run_diff(local_content_dir, remote_dir)

        assert len(diff_service.result.errors) > 0
        assert "Error running diff" in diff_service.result.errors[0]

    def test_diff_page_with_pull_errors(
        self,
        diff_service: DiffService,
        mock_client: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """Test diffing a page when pull encounters errors."""
        # Mock page fetch to fail
        mock_client.get_page_by_id.side_effect = Exception("API Error")

        # Mock subprocess.run for diff command
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = diff_service.diff_page(12345)

        # Pull errors should be captured
        assert len(result.errors) > 0
