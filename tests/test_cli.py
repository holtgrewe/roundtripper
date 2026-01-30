"""Test the CLI entry point."""

import pytest
from pytest_mock import MockerFixture
from rich.console import Console

import roundtripper.cli
from roundtripper.cli import _main_logic, app, cli, main


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


class TestBusinessLogic:
    """Test business logic independent of CLI."""

    def test_main_logic_returns_greeting(self) -> None:
        """Test that _main_logic returns the expected greeting."""
        result = _main_logic()
        assert result == "Hello from roundtripper!"
        assert isinstance(result, str)


class TestCLIBehavior:
    """Test CLI behavior including argument parsing and output."""

    def test_main_command_with_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that the main command prints the correct output."""
        # Use result_action="return_value" to avoid sys.exit being called
        result = app([], result_action="return_value")

        # Check stdout
        captured = capsys.readouterr()
        assert captured.out == "Hello from roundtripper!\n"

        # The function returns None
        assert result is None

    def test_main_command_direct_call(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test calling the main function directly."""
        main()
        captured = capsys.readouterr()
        assert captured.out == "Hello from roundtripper!\n"

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

    def test_cli_entry_point(
        self, capsys: pytest.CaptureFixture[str], mocker: MockerFixture
    ) -> None:
        """Test the cli() entry point function."""
        # Mock sys.argv to provide empty arguments
        mocker.patch("sys.argv", ["roundtripper"])

        # Call cli() which should call app([]) and exit
        with pytest.raises(SystemExit) as exc_info:
            cli()

        # Should exit successfully
        assert exc_info.value.code == 0

        # Verify output
        captured = capsys.readouterr()
        assert "Hello from roundtripper!" in captured.out

    def test_main_module_execution(self, mocker: MockerFixture) -> None:
        """Test __main__ execution path."""
        # Mock sys.argv to provide empty arguments
        mocker.patch("sys.argv", ["roundtripper"])

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

            # Should exit successfully
            assert exc_info.value.code == 0
