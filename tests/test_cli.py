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
        assert "0.0.0" in actual

    def test_app_import(self) -> None:
        """Test that the app can be imported."""
        assert app is not None
        assert "roundtripper" in app.name

    def test_cli_entry_point(self, mocker: MockerFixture) -> None:
        """Test the cli() entry point function."""
        # Mock sys.argv to provide help arguments
        mocker.patch("sys.argv", ["roundtripper", "--help"])

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
        # Mock the interactive menu function - import happens inside config function
        mock_menu = mocker.patch("roundtripper.config_interactive.main_config_menu_loop")

        # Run the command without --show flag
        app(["confluence", "config"], result_action="return_value")

        # Verify the interactive menu was called
        mock_menu.assert_called_once_with(None)

    def test_config_jump_to_parameter(self, mocker: MockerFixture, temp_config_file: Path) -> None:
        """Test that --jump-to parameter is passed to interactive menu."""
        # Mock the interactive menu function - import happens inside config function
        mock_menu = mocker.patch("roundtripper.config_interactive.main_config_menu_loop")

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

        # Mock httpx.Client
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"size": 1}

        mock_client = mocker.Mock()
        mock_client.__enter__ = mocker.Mock(return_value=mock_client)
        mock_client.__exit__ = mocker.Mock(return_value=None)
        mock_client.get.return_value = mock_response

        mocker.patch("roundtripper.confluence.httpx.Client", return_value=mock_client)

        with pytest.raises(SystemExit) as exc_info:
            app(["confluence", "ping"], result_action="return_value")

        assert exc_info.value.code == 0

    def test_ping_success_no_size(self, mocker: MockerFixture, temp_config_file: Path) -> None:
        """Test ping command with successful connection but no size in response."""
        from roundtripper.config import ConfigModel

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

        # Mock httpx.Client with response lacking "size" field
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}

        mock_client = mocker.Mock()
        mock_client.__enter__ = mocker.Mock(return_value=mock_client)
        mock_client.__exit__ = mocker.Mock(return_value=None)
        mock_client.get.return_value = mock_response

        mocker.patch("roundtripper.confluence.httpx.Client", return_value=mock_client)

        with pytest.raises(SystemExit) as exc_info:
            app(["confluence", "ping"], result_action="return_value")

        assert exc_info.value.code == 0

    def test_ping_auth_failure(self, mocker: MockerFixture, temp_config_file: Path) -> None:
        """Test ping command with authentication failure."""
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

        # Mock httpx.Client with 401 response
        mock_response = mocker.Mock()
        mock_response.status_code = 401

        mock_client = mocker.Mock()
        mock_client.__enter__ = mocker.Mock(return_value=mock_client)
        mock_client.__exit__ = mocker.Mock(return_value=None)
        mock_client.get.return_value = mock_response

        mocker.patch("roundtripper.confluence.httpx.Client", return_value=mock_client)

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

    def test_ping_forbidden(self, mocker: MockerFixture, temp_config_file: Path) -> None:
        """Test ping command with 403 forbidden response."""
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

        # Mock httpx.Client with 403 response
        mock_response = mocker.Mock()
        mock_response.status_code = 403

        mock_client = mocker.Mock()
        mock_client.__enter__ = mocker.Mock(return_value=mock_client)
        mock_client.__exit__ = mocker.Mock(return_value=None)
        mock_client.get.return_value = mock_response

        mocker.patch("roundtripper.confluence.httpx.Client", return_value=mock_client)

        with pytest.raises(SystemExit) as exc_info:
            app(["confluence", "ping"], result_action="return_value")

        assert exc_info.value.code == 1

    def test_ping_unexpected_response(self, mocker: MockerFixture, temp_config_file: Path) -> None:
        """Test ping command with unexpected response code."""
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

        # Mock httpx.Client with 500 response
        mock_response = mocker.Mock()
        mock_response.status_code = 500
        mock_response.reason_phrase = "Internal Server Error"

        mock_client = mocker.Mock()
        mock_client.__enter__ = mocker.Mock(return_value=mock_client)
        mock_client.__exit__ = mocker.Mock(return_value=None)
        mock_client.get.return_value = mock_response

        mocker.patch("roundtripper.confluence.httpx.Client", return_value=mock_client)

        with pytest.raises(SystemExit) as exc_info:
            app(["confluence", "ping"], result_action="return_value")

        assert exc_info.value.code == 1

    def test_ping_timeout(self, mocker: MockerFixture, temp_config_file: Path) -> None:
        """Test ping command with timeout."""
        import httpx

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

        # Mock httpx.Client to raise TimeoutException
        mock_client = mocker.Mock()
        mock_client.__enter__ = mocker.Mock(return_value=mock_client)
        mock_client.__exit__ = mocker.Mock(return_value=None)
        mock_client.get.side_effect = httpx.TimeoutException("Request timeout")

        mocker.patch("roundtripper.confluence.httpx.Client", return_value=mock_client)

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

        # Mock httpx.Client to raise a generic exception
        mock_client = mocker.Mock()
        mock_client.__enter__ = mocker.Mock(return_value=mock_client)
        mock_client.__exit__ = mocker.Mock(return_value=None)
        mock_client.get.side_effect = ValueError("Unexpected error")

        mocker.patch("roundtripper.confluence.httpx.Client", return_value=mock_client)

        with pytest.raises(SystemExit) as exc_info:
            app(["confluence", "ping"], result_action="return_value")

        assert exc_info.value.code == 1

    def test_ping_connection_error(self, mocker: MockerFixture, temp_config_file: Path) -> None:
        """Test ping command with connection error."""
        import httpx

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

        # Mock httpx.Client to raise ConnectError
        mock_client = mocker.Mock()
        mock_client.__enter__ = mocker.Mock(return_value=mock_client)
        mock_client.__exit__ = mocker.Mock(return_value=None)
        mock_client.get.side_effect = httpx.ConnectError("Connection failed")

        mocker.patch("roundtripper.confluence.httpx.Client", return_value=mock_client)

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
            "roundtripper.api_client.get_confluence_client",
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
        mocker.patch("roundtripper.api_client.get_confluence_client", return_value=mock_client)

        mock_service = mocker.MagicMock()
        mock_service.pull_space.return_value = PullResult(
            pages_downloaded=5, attachments_downloaded=3
        )
        mocker.patch("roundtripper.pull_service.PullService", return_value=mock_service)

        with pytest.raises(SystemExit) as exc_info:
            app(
                ["confluence", "pull", "--space", "SPACE", "--output", str(tmp_path)],
                result_action="return_value",
            )

        assert exc_info.value.code == 0
        mock_service.pull_space.assert_called_once_with("SPACE")

    def test_pull_page_success(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test pull command succeeds with --page-id."""
        from roundtripper.models import PullResult

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.api_client.get_confluence_client", return_value=mock_client)

        mock_service = mocker.MagicMock()
        mock_service.pull_page.return_value = PullResult(
            pages_downloaded=1, attachments_downloaded=0
        )
        mocker.patch("roundtripper.pull_service.PullService", return_value=mock_service)

        with pytest.raises(SystemExit) as exc_info:
            app(
                ["confluence", "pull", "--page-id", "12345", "--output", str(tmp_path)],
                result_action="return_value",
            )

        assert exc_info.value.code == 0
        # Default is recursive=True
        mock_service.pull_page.assert_called_once_with(12345, recursive=True)

    def test_pull_page_recursive(
        self, mocker: MockerFixture, temp_config_file: Path, tmp_path: Path
    ) -> None:
        """Test pull command with --no-recursive flag."""
        from roundtripper.models import PullResult

        mock_client = mocker.MagicMock()
        mocker.patch("roundtripper.api_client.get_confluence_client", return_value=mock_client)

        mock_service = mocker.MagicMock()
        mock_service.pull_page.return_value = PullResult(
            pages_downloaded=5, attachments_downloaded=0
        )
        mocker.patch("roundtripper.pull_service.PullService", return_value=mock_service)

        with pytest.raises(SystemExit) as exc_info:
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

        assert exc_info.value.code == 0
        mock_service.pull_page.assert_called_once_with(12345, recursive=False)

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
        mocker.patch("roundtripper.api_client.get_confluence_client", return_value=mock_client)

        mock_service = mocker.MagicMock()
        # Create 7 errors to trigger the truncation message
        mock_service.pull_space.return_value = PullResult(
            pages_downloaded=0,
            errors=[f"Error {i}" for i in range(7)],
        )
        mocker.patch("roundtripper.pull_service.PullService", return_value=mock_service)

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
        mocker.patch("roundtripper.api_client.get_confluence_client", return_value=mock_client)

        mock_service = mocker.MagicMock()
        mock_service.pull_space.return_value = PullResult(
            pages_downloaded=5, attachments_downloaded=3
        )
        mocker.patch("roundtripper.pull_service.PullService", return_value=mock_service)

        with pytest.raises(SystemExit) as exc_info:
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

        assert exc_info.value.code == 0
        # Verify dry_run output is shown in logs
        assert "DRY RUN" in caplog.text
