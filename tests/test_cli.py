"""Test the CLI entry point."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from rich.console import Console

import roundtripper.cli
from roundtripper.cli import app, cli
from roundtripper.config import ConfigModel
from roundtripper.config_store import save_app_data


@pytest.fixture
def console() -> Console:
    """Fixture for consistent Rich console output in tests."""
    return Console(
        width=70,
        force_terminal=True,
        highlight=False,
        color_system=None,
        legacy_windows=False,
    )


@pytest.fixture
def temp_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary config file for testing."""
    config_file = tmp_path / "roundtripper" / "config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("roundtripper.config_store.APP_CONFIG_PATH", config_file)
    return config_file


class TestCLIBehavior:
    """Test CLI behavior including argument parsing and output."""

    def test_no_command_shows_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that running with no command shows help."""
        with pytest.raises(SystemExit) as exc_info:
            app([])

        # Should exit with code 0 (help page)
        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        # Should show help output
        assert "roundtripper" in captured.out
        assert "Roundtripping with Confluence" in captured.out

    def test_help_page(self, capsys: pytest.CaptureFixture[str], console: Console) -> None:
        """Test that the help page is displayed correctly."""
        with pytest.raises(SystemExit) as exc_info:
            app(["--help"], console=console)

        # Help pages exit with code 0
        assert exc_info.value.code == 0

        actual = capsys.readouterr().out
        # Check for key elements in the help output
        assert "roundtripper" in actual
        assert "Roundtripping with Confluence" in actual
        assert "--help" in actual
        assert "--version" in actual

    def test_version_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that --version displays the version and exits."""
        with pytest.raises(SystemExit) as exc_info:
            app(["--version"])

        # Version flag exits with code 0
        assert exc_info.value.code == 0

        actual = capsys.readouterr().out
        # Version output should contain a version number
        assert actual.count(".") >= 2  # Simple check for version format

    def test_app_import(self) -> None:
        """Test that the app can be imported."""
        assert app is not None
        assert "roundtripper" in app.name

    def test_cli_entry_point(self, mocker: MockerFixture) -> None:
        """Test the cli() entry point function."""
        # Mock sys.argv to provide help arguments
        mocker.patch("sys.argv", ["roundtripper", "--help"])

        # Suppress the pytest warning since we're deliberately testing the CLI entry point
        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, message=".*Cyclopts.*")

            # Call cli() which should call app.meta([]) and show help
            with pytest.raises(SystemExit) as exc_info:
                cli()

        # Should exit with code 0 for help
        assert exc_info.value.code == 0

    def test_verbose_mode(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that --verbose flag enables debug logging."""
        # This should trigger the meta.default function with verbose=True
        with pytest.raises(SystemExit) as exc_info:
            app(["--verbose", "--help"])

        assert exc_info.value.code == 0
        # The help output should still be shown
        captured = capsys.readouterr()
        assert "roundtripper" in captured.out.lower()


class TestConfluenceConfigCommand:
    """Test confluence config command."""

    def test_config_show_flag(
        self, capsys: pytest.CaptureFixture[str], temp_config_file: Path
    ) -> None:
        """Test that --show flag displays current config."""
        # Create a config with known values
        config = ConfigModel()
        save_app_data(config)

        # Run the command with --show flag
        app(["confluence", "config", "--show"], result_action="return_value")

        captured = capsys.readouterr()
        assert "```json" in captured.out
        assert "connection_config" in captured.out
        assert "auth" in captured.out
        assert "confluence" in captured.out

    def test_config_interactive_menu(self, mocker: MockerFixture, temp_config_file: Path) -> None:
        """Test that config without --show opens interactive menu."""
        # Mock the interactive menu function at the top level where it's imported
        mock_menu = mocker.patch("roundtripper.confluence.main_config_menu_loop")

        # Run the command without --show flag
        app(["confluence", "config"], result_action="return_value")

        # Verify the interactive menu was called
        mock_menu.assert_called_once_with(None)

    def test_config_jump_to_parameter(self, mocker: MockerFixture, temp_config_file: Path) -> None:
        """Test that --jump-to parameter is passed to interactive menu."""
        # Mock the interactive menu function at the top level where it's imported
        mock_menu = mocker.patch("roundtripper.confluence.main_config_menu_loop")

        # Run the command with --jump-to
        app(
            ["confluence", "config", "--jump-to", "auth.confluence"],
            result_action="return_value",
        )

        # Verify the interactive menu was called with the right parameter
        mock_menu.assert_called_once_with("auth.confluence")

    def test_confluence_help(self, capsys: pytest.CaptureFixture[str], console: Console) -> None:
        """Test that confluence --help shows subcommands."""
        with pytest.raises(SystemExit) as exc_info:
            app(["confluence", "--help"], console=console)

        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "confluence" in captured.out.lower()
        assert "config" in captured.out.lower()

    def test_config_help(self, capsys: pytest.CaptureFixture[str], console: Console) -> None:
        """Test that confluence config --help shows options."""
        with pytest.raises(SystemExit) as exc_info:
            app(["confluence", "config", "--help"], console=console)

        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "config" in captured.out.lower()
        assert "--show" in captured.out.lower()
        assert "--jump-to" in captured.out.lower()

    def test_ping_help(self, capsys: pytest.CaptureFixture[str], console: Console) -> None:
        """Test that confluence ping --help shows help."""
        with pytest.raises(SystemExit) as exc_info:
            app(["confluence", "ping", "--help"], console=console)

        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "ping" in captured.out.lower()
        assert "test confluence api connection" in captured.out.lower()

    def test_ping_no_config(self, mocker: MockerFixture, temp_config_file: Path) -> None:
        """Test ping command with no configuration."""
        # Mock get_settings to return empty config
        from roundtripper.config import ApiDetails, AuthConfig, ConfigModel

        empty_config = ConfigModel(auth=AuthConfig(confluence=ApiDetails(url="")))
        mocker.patch("roundtripper.confluence.get_settings", return_value=empty_config)

        with pytest.raises(SystemExit) as exc_info:
            app(["confluence", "ping"], result_action="return_value")

        assert exc_info.value.code == 1

    def test_ping_success(self, mocker: MockerFixture, temp_config_file: Path) -> None:
        """Test ping command with successful connection."""
        from roundtripper.config import ConfigModel

        # Mock config with PAT
        test_config = ConfigModel.model_validate(
            {
                "auth": {
                    "confluence": {
                        "url": "https://example.atlassian.net",
                        "pat": "test-pat-token",
                    }
                }
            }
        )
        mocker.patch("roundtripper.confluence.get_settings", return_value=test_config)

        # Mock get_confluence_client to return a mock client
        mock_client = mocker.Mock()
        mock_client.get_all_spaces.return_value = {"results": [], "size": 1}
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        app(["confluence", "ping"], result_action="return_value")

        # Should not raise SystemExit on success
        mock_client.get_all_spaces.assert_called_once_with(limit=1)

    def test_ping_connection_failure(self, mocker: MockerFixture, temp_config_file: Path) -> None:
        """Test ping command with connection failure."""
        from roundtripper.config import ConfigModel

        test_config = ConfigModel.model_validate(
            {
                "auth": {
                    "confluence": {
                        "url": "https://example.atlassian.net",
                        "username": "user@example.com",
                        "api_token": "bad-token",
                    }
                }
            }
        )
        mocker.patch("roundtripper.confluence.get_settings", return_value=test_config)

        # Mock get_confluence_client to raise ConnectionError
        mocker.patch(
            "roundtripper.confluence.get_confluence_client",
            side_effect=ConnectionError("Authentication failed"),
        )

        with pytest.raises(SystemExit) as exc_info:
            app(["confluence", "ping"], result_action="return_value")

        assert exc_info.value.code == 1

    def test_ping_no_credentials(self, mocker: MockerFixture, temp_config_file: Path) -> None:
        """Test ping command with URL but no credentials."""
        from roundtripper.config import ConfigModel

        test_config = ConfigModel.model_validate(
            {"auth": {"confluence": {"url": "https://example.atlassian.net"}}}
        )
        mocker.patch("roundtripper.confluence.get_settings", return_value=test_config)

        with pytest.raises(SystemExit) as exc_info:
            app(["confluence", "ping"], result_action="return_value")

        assert exc_info.value.code == 1

    def test_ping_generic_exception(self, mocker: MockerFixture, temp_config_file: Path) -> None:
        """Test ping command with generic exception."""
        from roundtripper.config import ConfigModel

        test_config = ConfigModel.model_validate(
            {
                "auth": {
                    "confluence": {
                        "url": "https://example.atlassian.net",
                        "pat": "test-pat",
                    }
                }
            }
        )
        mocker.patch("roundtripper.confluence.get_settings", return_value=test_config)

        # Mock get_confluence_client to raise a generic exception
        mocker.patch(
            "roundtripper.confluence.get_confluence_client",
            side_effect=RuntimeError("Unexpected error"),
        )

        with pytest.raises(SystemExit) as exc_info:
            app(["confluence", "ping"], result_action="return_value")

        assert exc_info.value.code == 1

    def test_main_module_execution(self, mocker: MockerFixture) -> None:
        """Test __main__ execution path."""
        # Mock sys.argv to provide help arguments
        mocker.patch("sys.argv", ["roundtripper", "--help"])

        # Mock the cli function to verify it gets called
        _mock_cli = mocker.patch("roundtripper.cli.cli")

        # Execute the module's __main__ code directly
        if roundtripper.cli.__name__ != "__main__":
            # Simulate the __main__ block
            with pytest.raises(SystemExit) as exc_info:
                exec(
                    compile(
                        open(roundtripper.cli.__file__).read(), roundtripper.cli.__file__, "exec"
                    ),
                    {"__name__": "__main__", "__file__": roundtripper.cli.__file__},
                )

            # Should exit with code 0
            assert exc_info.value.code == 0


class TestConfluencePullCommand:
    """Tests for the confluence pull command."""

    def test_pull_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test pull command help shows required options."""
        app(["confluence", "pull", "--help"], result_action="return_value")

        captured = capsys.readouterr()
        assert "--space" in captured.out
        assert "--page-id" in captured.out
        assert "--output" in captured.out
        assert "--dry-run" in captured.out

    def test_pull_no_space_or_page_id(self, mocker: MockerFixture) -> None:
        """Test pull command fails without --space or --page-id."""
        with pytest.raises(SystemExit) as exc_info:
            app(["confluence", "pull"], result_action="return_value")

        assert exc_info.value.code == 1

    def test_pull_both_space_and_page_id(self, mocker: MockerFixture) -> None:
        """Test pull command fails with both --space and --page-id."""
        with pytest.raises(SystemExit) as exc_info:
            app(
                ["confluence", "pull", "--space", "SPACE", "--page-id", "123"],
                result_action="return_value",
            )

        assert exc_info.value.code == 1

    def test_pull_connection_error(self, mocker: MockerFixture, temp_config_file: Path) -> None:
        """Test pull command handles connection error."""
        mocker.patch(
            "roundtripper.confluence.get_confluence_client",
            side_effect=ConnectionError("Failed to connect"),
        )

        with pytest.raises(SystemExit) as exc_info:
            app(["confluence", "pull", "--space", "SPACE"], result_action="return_value")

        assert exc_info.value.code == 1

    def test_pull_space_success(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test pull command succeeds with --space."""
        from roundtripper.models import PullResult

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        mock_service_instance.pull_space.return_value = PullResult(
            pages_downloaded=5, attachments_downloaded=3
        )
        mocker.patch("roundtripper.confluence.PullService", return_value=mock_service_instance)

        app(
            ["confluence", "pull", "--space", "SPACE", "--output", str(tmp_path)],
            result_action="return_value",
        )

        mock_service_instance.pull_space.assert_called_once_with("SPACE")

    def test_pull_page_success(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test pull command succeeds with --page-id."""
        from roundtripper.models import PullResult

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        mock_service_instance.pull_page.return_value = PullResult(
            pages_downloaded=1, attachments_downloaded=0
        )
        mocker.patch("roundtripper.confluence.PullService", return_value=mock_service_instance)

        app(
            ["confluence", "pull", "--page-id", "12345", "--output", str(tmp_path)],
            result_action="return_value",
        )

        # Default is recursive=True
        mock_service_instance.pull_page.assert_called_once_with(12345, recursive=True)

    def test_pull_page_recursive(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test pull command with --no-recursive flag."""
        from roundtripper.models import PullResult

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        mock_service_instance.pull_page.return_value = PullResult(
            pages_downloaded=5, attachments_downloaded=0
        )
        mocker.patch("roundtripper.confluence.PullService", return_value=mock_service_instance)

        app(
            [
                "confluence",
                "pull",
                "--page-id",
                "12345",
                "--no-recursive",
                "--output",
                str(tmp_path),
            ],
            result_action="return_value",
        )

        mock_service_instance.pull_page.assert_called_once_with(12345, recursive=False)

    def test_pull_with_errors(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test pull command exits with error when result has errors."""
        from roundtripper.models import PullResult

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.api_client.get_confluence_client", return_value=mock_client)

        mock_service = mocker.MagicMock()
        mock_service.pull_space.return_value = PullResult(
            pages_downloaded=5, errors=["Error 1", "Error 2"]
        )
        mocker.patch("roundtripper.pull_service.PullService", return_value=mock_service)

        with pytest.raises(SystemExit) as exc_info:
            app(
                ["confluence", "pull", "--space", "SPACE", "--output", str(tmp_path)],
                result_action="return_value",
            )

        assert exc_info.value.code == 1

    def test_pull_with_more_than_five_errors(
        self,
        mocker: MockerFixture,
        temp_config_file: Path,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test pull command truncates error output when more than 5 errors."""
        from roundtripper.models import PullResult

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        # Create 7 errors to trigger the truncation message
        mock_service_instance.pull_space.return_value = PullResult(
            pages_downloaded=0,
            errors=[f"Error {i}" for i in range(7)],
        )
        mocker.patch("roundtripper.confluence.PullService", return_value=mock_service_instance)

        with pytest.raises(SystemExit) as exc_info:
            app(
                ["confluence", "pull", "--space", "SPACE", "--output", str(tmp_path)],
                result_action="return_value",
            )

        assert exc_info.value.code == 1
        # Check log messages - should show first 5 errors and a "more errors" message
        assert "Error 0" in caplog.text
        assert "2 more errors" in caplog.text

    def test_pull_dry_run(
        self,
        mocker: MockerFixture,
        temp_config_file: Path,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test pull command with --dry-run flag."""
        import logging

        from roundtripper.models import PullResult

        caplog.set_level(logging.INFO)

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        mock_service_instance.pull_space.return_value = PullResult(
            pages_downloaded=5, attachments_downloaded=3
        )
        mocker.patch("roundtripper.confluence.PullService", return_value=mock_service_instance)

        app(
            [
                "confluence",
                "pull",
                "--space",
                "SPACE",
                "--dry-run",
                "--output",
                str(tmp_path),
            ],
            result_action="return_value",
        )

        # Verify dry_run output is shown in logs
        assert "DRY RUN" in caplog.text

    def test_pull_verbose_flag(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test pull command with --verbose flag enables debug logging."""
        import logging

        from roundtripper.models import PullResult

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        mock_service_instance.pull_space.return_value = PullResult(
            pages_downloaded=1, attachments_downloaded=0
        )
        mocker.patch("roundtripper.confluence.PullService", return_value=mock_service_instance)

        app(
            ["confluence", "pull", "--space", "SPACE", "--output", str(tmp_path), "--verbose"],
            result_action="return_value",
        )

        # Verify debug logging is enabled for roundtripper logger
        assert logging.getLogger("roundtripper").level == logging.DEBUG


class TestConfluencePushCommand:
    """Tests for the confluence push command."""

    def test_push_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test push command help shows required options."""
        app(["confluence", "push", "--help"], result_action="return_value")

        captured = capsys.readouterr()
        assert "message" in captured.out.lower()
        assert "--page-path" in captured.out
        assert "--space-path" in captured.out
        assert "--recursive" in captured.out
        assert "--dry-run" in captured.out
        assert "--force" in captured.out

    def test_push_no_path_specified(self, mocker: MockerFixture) -> None:
        """Test push command fails without --page-path or --space-path."""
        with pytest.raises(SystemExit) as exc_info:
            app(["confluence", "push", "Test message"], result_action="return_value")

        assert exc_info.value.code == 1

    def test_push_both_paths_specified(self, mocker: MockerFixture, tmp_path: Path) -> None:
        """Test push command fails with both --page-path and --space-path."""
        page_path = tmp_path / "page"
        page_path.mkdir()
        space_path = tmp_path / "space"
        space_path.mkdir()

        with pytest.raises(SystemExit) as exc_info:
            app(
                [
                    "confluence",
                    "push",
                    "Test message",
                    "--page-path",
                    str(page_path),
                    "--space-path",
                    str(space_path),
                ],
                result_action="return_value",
            )

        assert exc_info.value.code == 1

    def test_push_nonexistent_path(self, mocker: MockerFixture, tmp_path: Path) -> None:
        """Test push command fails with nonexistent path."""
        with pytest.raises(SystemExit) as exc_info:
            app(
                [
                    "confluence",
                    "push",
                    "Test message",
                    "--page-path",
                    str(tmp_path / "nonexistent"),
                ],
                result_action="return_value",
            )

        assert exc_info.value.code == 1

    def test_push_connection_error(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test push command handles connection error."""
        page_path = tmp_path / "page"
        page_path.mkdir()

        mocker.patch(
            "roundtripper.confluence.get_confluence_client",
            side_effect=ConnectionError("Failed to connect"),
        )

        with pytest.raises(SystemExit) as exc_info:
            app(
                ["confluence", "push", "Test message", "--page-path", str(page_path)],
                result_action="return_value",
            )

        assert exc_info.value.code == 1

    def test_push_page_success(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test push command succeeds with --page-path."""
        from roundtripper.models import PushResult

        page_path = tmp_path / "page"
        page_path.mkdir()

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        mock_service_instance.push_page.return_value = PushResult(pages_updated=1, pages_skipped=0)
        mocker.patch("roundtripper.confluence.PushService", return_value=mock_service_instance)

        app(
            [
                "confluence",
                "push",
                "Update page",
                "--page-path",
                str(page_path),
                "--no-interactive",
            ],
            result_action="return_value",
        )

        mock_service_instance.push_page.assert_called_once_with(page_path, recursive=False)

    def test_push_page_recursive(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test push command with --recursive flag."""
        from roundtripper.models import PushResult

        page_path = tmp_path / "page"
        page_path.mkdir()

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        mock_service_instance.push_page.return_value = PushResult(pages_updated=3, pages_skipped=1)
        mocker.patch("roundtripper.confluence.PushService", return_value=mock_service_instance)

        app(
            [
                "confluence",
                "push",
                "Recursive update",
                "--page-path",
                str(page_path),
                "--recursive",
                "--no-interactive",
            ],
            result_action="return_value",
        )

        mock_service_instance.push_page.assert_called_once_with(page_path, recursive=True)

    def test_push_space_success(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test push command succeeds with --space-path."""
        from roundtripper.models import PushResult

        space_path = tmp_path / "SPACE"
        space_path.mkdir()

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        mock_service_instance.push_space.return_value = PushResult(pages_updated=5, pages_skipped=2)
        mocker.patch("roundtripper.confluence.PushService", return_value=mock_service_instance)

        app(
            ["confluence", "push", "Update space", "--space-path", str(space_path)],
            result_action="return_value",
        )

        mock_service_instance.push_space.assert_called_once_with(space_path)

    def test_push_with_conflicts(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test push command exits with error when conflicts exist."""
        from roundtripper.models import PushResult

        page_path = tmp_path / "page"
        page_path.mkdir()

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        mock_service_instance.push_page.return_value = PushResult(
            pages_updated=0,
            conflicts=["Conflict: Page 1 - local version 1, server version 3"],
        )
        mocker.patch("roundtripper.confluence.PushService", return_value=mock_service_instance)

        with pytest.raises(SystemExit) as exc_info:
            app(
                [
                    "confluence",
                    "push",
                    "Conflict test",
                    "--page-path",
                    str(page_path),
                    "--no-interactive",
                ],
                result_action="return_value",
            )

        assert exc_info.value.code == 1

    def test_push_with_more_than_five_conflicts(
        self,
        mocker: MockerFixture,
        temp_config_file: Path,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test push command truncates conflict output when more than 5 conflicts."""
        from roundtripper.models import PushResult

        page_path = tmp_path / "page"
        page_path.mkdir()

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        # Create 7 conflicts to trigger the truncation message
        mock_service_instance.push_page.return_value = PushResult(
            pages_updated=0,
            conflicts=[f"Conflict {i}" for i in range(7)],
        )
        mocker.patch("roundtripper.confluence.PushService", return_value=mock_service_instance)

        with pytest.raises(SystemExit) as exc_info:
            app(
                [
                    "confluence",
                    "push",
                    "Many conflicts",
                    "--page-path",
                    str(page_path),
                    "--no-interactive",
                ],
                result_action="return_value",
            )

        assert exc_info.value.code == 1
        # Check log messages - should show first 5 conflicts and a "more conflicts" message
        assert "Conflict 0" in caplog.text
        assert "2 more conflicts" in caplog.text

    def test_push_with_more_than_five_errors(
        self,
        mocker: MockerFixture,
        temp_config_file: Path,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test push command truncates error output when more than 5 errors."""
        from roundtripper.models import PushResult

        page_path = tmp_path / "page"
        page_path.mkdir()

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        # Create 7 errors to trigger the truncation message
        mock_service_instance.push_page.return_value = PushResult(
            pages_updated=0,
            errors=[f"Error {i}" for i in range(7)],
        )
        mocker.patch("roundtripper.confluence.PushService", return_value=mock_service_instance)

        with pytest.raises(SystemExit) as exc_info:
            app(
                [
                    "confluence",
                    "push",
                    "Many errors",
                    "--page-path",
                    str(page_path),
                    "--no-interactive",
                ],
                result_action="return_value",
            )

        assert exc_info.value.code == 1
        # Check log messages - should show first 5 errors and a "more errors" message
        assert "Error 0" in caplog.text
        assert "2 more errors" in caplog.text

    def test_push_with_errors(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test push command exits with error when errors occur."""
        from roundtripper.models import PushResult

        page_path = tmp_path / "page"
        page_path.mkdir()

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        mock_service_instance.push_page.return_value = PushResult(
            pages_updated=1,
            errors=["API Error: Permission denied"],
        )
        mocker.patch("roundtripper.confluence.PushService", return_value=mock_service_instance)

        with pytest.raises(SystemExit) as exc_info:
            app(
                [
                    "confluence",
                    "push",
                    "Error test",
                    "--page-path",
                    str(page_path),
                    "--no-interactive",
                ],
                result_action="return_value",
            )

        assert exc_info.value.code == 1

    def test_push_dry_run(
        self,
        mocker: MockerFixture,
        temp_config_file: Path,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test push command with --dry-run flag."""
        import logging

        from roundtripper.models import PushResult

        caplog.set_level(logging.INFO)

        page_path = tmp_path / "page"
        page_path.mkdir()

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        mock_service_instance.push_page.return_value = PushResult(pages_updated=0, pages_skipped=1)
        mocker.patch("roundtripper.confluence.PushService", return_value=mock_service_instance)

        app(
            ["confluence", "push", "Dry run test", "--page-path", str(page_path), "--dry-run"],
            result_action="return_value",
        )

        # Verify dry_run output is shown in logs
        assert "DRY RUN" in caplog.text

    def test_push_force_flag(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test push command passes --force flag to service."""
        from roundtripper.models import PushResult

        page_path = tmp_path / "page"
        page_path.mkdir()

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_class = mocker.patch("roundtripper.confluence.PushService")
        mock_service_instance = mocker.MagicMock()
        mock_service_instance.push_page.return_value = PushResult(pages_updated=1)
        mock_service_class.return_value = mock_service_instance

        app(
            [
                "confluence",
                "push",
                "Force push",
                "--page-path",
                str(page_path),
                "--force",
                "--no-interactive",
            ],
            result_action="return_value",
        )

        # Verify PushService was instantiated with force=True and interactive=False
        mock_service_class.assert_called_once_with(
            mock_client, message="Force push", dry_run=False, force=True, interactive=False
        )

    def test_push_verbose_flag(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test push command with --verbose flag enables debug logging."""
        import logging

        from roundtripper.models import PushResult

        page_path = tmp_path / "page"
        page_path.mkdir()

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        mock_service_instance.push_page.return_value = PushResult(pages_updated=1)
        mocker.patch("roundtripper.confluence.PushService", return_value=mock_service_instance)

        app(
            [
                "confluence",
                "push",
                "Verbose test",
                "--page-path",
                str(page_path),
                "--verbose",
                "--no-interactive",
            ],
            result_action="return_value",
        )

        # Verify debug logging is enabled for roundtripper logger
        assert logging.getLogger("roundtripper").level == logging.DEBUG


class TestDiffCommand:
    """Test the confluence diff command."""

    def test_diff_requires_space_or_page_id(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test that diff command requires --space or --page-id."""
        local_path = tmp_path / "local"
        local_path.mkdir()

        with pytest.raises(SystemExit) as exc_info:
            app(
                ["confluence", "diff", "--local-path", str(local_path)],
                result_action="return_value",
            )

        assert exc_info.value.code == 1

    def test_diff_rejects_both_space_and_page_id(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test that diff command rejects both --space and --page-id."""
        local_path = tmp_path / "local"
        local_path.mkdir()

        with pytest.raises(SystemExit) as exc_info:
            app(
                [
                    "confluence",
                    "diff",
                    "--local-path",
                    str(local_path),
                    "--space",
                    "SPACE",
                    "--page-id",
                    "12345",
                ],
                result_action="return_value",
            )

        assert exc_info.value.code == 1

    def test_diff_requires_existing_local_path(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test that diff command requires local path to exist."""
        local_path = tmp_path / "nonexistent"

        with pytest.raises(SystemExit) as exc_info:
            app(
                [
                    "confluence",
                    "diff",
                    "--local-path",
                    str(local_path),
                    "--space",
                    "SPACE",
                ],
                result_action="return_value",
            )

        assert exc_info.value.code == 1

    def test_diff_space_success_no_changes(
        self,
        mocker: MockerFixture,
        temp_config_file: Path,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test diff command with space when there are no changes."""
        import logging

        from roundtripper.models import DiffResult

        caplog.set_level(logging.INFO)

        local_path = tmp_path / "local"
        local_path.mkdir()

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        mock_service_instance.diff_space.return_value = DiffResult(has_differences=False)
        mocker.patch("roundtripper.confluence.DiffService", return_value=mock_service_instance)

        app(
            ["confluence", "diff", "--local-path", str(local_path), "--space", "SPACE"],
            result_action="return_value",
        )

        # Verify log message
        assert "no differences" in caplog.text

    def test_diff_space_with_changes(
        self,
        mocker: MockerFixture,
        temp_config_file: Path,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test diff command with space when there are changes."""
        import logging

        from roundtripper.models import DiffResult

        caplog.set_level(logging.INFO)

        local_path = tmp_path / "local"
        local_path.mkdir()

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        mock_service_instance.diff_space.return_value = DiffResult(has_differences=True)
        mocker.patch("roundtripper.confluence.DiffService", return_value=mock_service_instance)

        with pytest.raises(SystemExit) as exc_info:
            app(
                ["confluence", "diff", "--local-path", str(local_path), "--space", "SPACE"],
                result_action="return_value",
            )

        # Should exit with code 1 when differences exist
        assert exc_info.value.code == 1
        assert "differences found" in caplog.text

    def test_diff_page_recursive(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test diff command with page and recursive flag."""
        from roundtripper.models import DiffResult

        local_path = tmp_path / "local"
        local_path.mkdir()

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        mock_service_instance.diff_page.return_value = DiffResult(has_differences=False)
        mocker.patch("roundtripper.confluence.DiffService", return_value=mock_service_instance)

        app(
            [
                "confluence",
                "diff",
                "--local-path",
                str(local_path),
                "--page-id",
                "12345",
                "--recursive",
            ],
            result_action="return_value",
        )

        # Verify diff_page was called with recursive=True
        mock_service_instance.diff_page.assert_called_once_with(12345, recursive=True)

    def test_diff_page_non_recursive(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test diff command with page and --no-recursive flag."""
        from roundtripper.models import DiffResult

        local_path = tmp_path / "local"
        local_path.mkdir()

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        mock_service_instance.diff_page.return_value = DiffResult(has_differences=False)
        mocker.patch("roundtripper.confluence.DiffService", return_value=mock_service_instance)

        app(
            [
                "confluence",
                "diff",
                "--local-path",
                str(local_path),
                "--page-id",
                "12345",
                "--no-recursive",
            ],
            result_action="return_value",
        )

        # Verify diff_page was called with recursive=False
        mock_service_instance.diff_page.assert_called_once_with(12345, recursive=False)

    def test_diff_with_errors(
        self,
        mocker: MockerFixture,
        temp_config_file: Path,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test diff command exits with error when errors occur."""
        import logging

        from roundtripper.models import DiffResult

        caplog.set_level(logging.INFO)

        local_path = tmp_path / "local"
        local_path.mkdir()

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        mock_service_instance.diff_space.return_value = DiffResult(
            has_differences=False,
            errors=["API Error: Permission denied"],
        )
        mocker.patch("roundtripper.confluence.DiffService", return_value=mock_service_instance)

        with pytest.raises(SystemExit) as exc_info:
            app(
                ["confluence", "diff", "--local-path", str(local_path), "--space", "SPACE"],
                result_action="return_value",
            )

        assert exc_info.value.code == 1
        assert "Errors encountered" in caplog.text

    def test_diff_verbose_flag(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test diff command with --verbose flag enables debug logging."""
        import logging

        from roundtripper.models import DiffResult

        local_path = tmp_path / "local"
        local_path.mkdir()

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.confluence.get_confluence_client", return_value=mock_client)

        mock_service_instance = mocker.MagicMock()
        mock_service_instance.diff_space.return_value = DiffResult(has_differences=False)
        mocker.patch("roundtripper.confluence.DiffService", return_value=mock_service_instance)

        app(
            [
                "confluence",
                "diff",
                "--local-path",
                str(local_path),
                "--space",
                "SPACE",
                "--verbose",
            ],
            result_action="return_value",
        )

        # Verify debug logging is enabled for roundtripper logger
        assert logging.getLogger("roundtripper").level == logging.DEBUG

    def test_diff_connection_error(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test diff command handles connection errors."""
        local_path = tmp_path / "local"
        local_path.mkdir()

        mocker.patch(
            "roundtripper.confluence.get_confluence_client",
            side_effect=ConnectionError("Connection failed"),
        )

        with pytest.raises(SystemExit) as exc_info:
            app(
                ["confluence", "diff", "--local-path", str(local_path), "--space", "SPACE"],
                result_action="return_value",
            )

        assert exc_info.value.code == 1
