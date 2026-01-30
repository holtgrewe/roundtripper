"""CLI entry point for roundtripper."""

import logging
from inspect import BoundArguments
from typing import Annotated, Any, Callable

import cyclopts
from rich.console import Console
from rich.logging import RichHandler

from roundtripper import __version__
from roundtripper.confluence import app as app_confluence

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
    app([])


if __name__ == "__main__":
    cli()
