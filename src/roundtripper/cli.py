"""CLI entry point for roundtripper."""

from cyclopts import App

from roundtripper import __version__

app = App(name="roundtripper", help="Roundtripping with Confluence", version=__version__)


def _main_logic() -> str:
    """Business logic for the main command.

    This is separated from the CLI presentation layer for easier testing.

    Returns
    -------
    str
        A greeting message.
    """
    return "Hello from roundtripper!"


@app.default
def main() -> None:
    """Main entry point.

    Processes the command and displays the result.
    """
    result = _main_logic()
    print(result)


def cli() -> None:
    """CLI entry point for the roundtripper command."""
    app([])


if __name__ == "__main__":
    cli()
