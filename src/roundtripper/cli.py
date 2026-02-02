"""CLI entry point for roundtripper."""

import logging
from inspect import BoundArguments
from typing import Annotated, Any, Callable

import cyclopts
from rich.console import Console
from rich.logging import RichHandler

from roundtripper import __version__
from roundtripper.confluence import app as app_confluence
from roundtripper.file_utils import is_xmllint_available

#: Logger instance.
LOGGER = logging.getLogger(__name__)

app = cyclopts.App(
    name="roundtripper",
    help="Roundtripping with Confluence",
    version=__version__,
    default_parameter=cyclopts.Parameter(parse=r"^[^_].*"),
)


@app.meta.default
def main(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
    verbose: bool = False,
) -> Any:  # pragma: no cover
    """Roundtripping with Confluence.

    Parameters
    ----------
    verbose
        Enable verbose mode.
    """
    # Setup rich console.
    rich_console = Console()
    rich_handler = RichHandler(console=rich_console)

    # Setup logging.
    lvl = logging.INFO
    FORMAT = "%(message)s"
    if verbose:
        lvl = logging.DEBUG
    logging.basicConfig(level=lvl, handlers=[rich_handler], format=FORMAT, datefmt="[%X]")

    # Check for xmllint availability
    if not is_xmllint_available():
        rich_console.print(
            "[yellow]Warning: xmllint is not available. XML output will not be formatted.[/yellow]"
        )
        rich_console.print("[yellow]Install xmllint for pretty-printed XML output:[/yellow]")
        rich_console.print("[yellow]  - Ubuntu/Debian: sudo apt-get install libxml2-utils[/yellow]")
        rich_console.print("[yellow]  - macOS: brew install libxml2[/yellow]")
        rich_console.print("[yellow]  - Fedora/RHEL: sudo dnf install libxml2[/yellow]")

    # Parse CLI and get ignored (non-parsed) parameters
    command: Callable[..., Any]
    bound: BoundArguments
    ignored: dict[str, Any]
    command, bound, ignored = app.parse_args(tokens, console=rich_console)  # type: ignore[assignment]

    # Inject ignored parameters
    ignored_kwargs: dict[str, Any] = {}
    for name in ignored:
        if name == "_console":
            ignored_kwargs[name] = rich_console
        elif name == "_handler":
            ignored_kwargs[name] = rich_handler

    return command(*bound.args, **bound.kwargs, **ignored_kwargs)


# Register sub-apps
app.command(app_confluence)


def cli() -> None:
    """CLI entry point for the roundtripper command."""
    app.meta()


if __name__ == "__main__":
    cli()
