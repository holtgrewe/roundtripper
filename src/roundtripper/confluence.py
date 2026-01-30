"""Confluence commands for roundtripper."""

import logging
from pathlib import Path

import cyclopts

from roundtripper.api_client import get_confluence_client
from roundtripper.config_interactive import main_config_menu_loop
from roundtripper.config_store import get_settings
from roundtripper.pull_service import PullService

#: Logger instance.
LOGGER = logging.getLogger(__name__)

#: CLI application for Confluence commands.
app = cyclopts.App(name="confluence", help="Confluence-related commands")


@app.command
def config(
    *,
    jump_to: str | None = None,
    show: bool = False,
) -> None:
    """Configure Confluence settings.

    Parameters
    ----------
    jump_to
        Jump directly to a config submenu (e.g., 'auth.confluence').
    show
        Display current configuration as JSON instead of opening the interactive menu.
    """
    if show:
        current_settings = get_settings()
        json_output = current_settings.model_dump_json(indent=2)
        print(f"```json\n{json_output}\n```")
    else:
        main_config_menu_loop(jump_to)


@app.command
def ping() -> None:
    """Test Confluence API connection.

    Verifies that the configured Confluence credentials are valid
    and the API is accessible.
    """
    settings = get_settings()
    confluence_config = settings.auth.confluence

    # Check if configuration is complete
    if not confluence_config.url:
        LOGGER.error("✗ Confluence URL is not configured")
        LOGGER.info("Run 'roundtripper confluence config' to configure")
        raise SystemExit(1)

    url_str = str(confluence_config.url)
    LOGGER.info("=" * 70)
    LOGGER.info("Testing Confluence API Connection")
    LOGGER.info("=" * 70)
    LOGGER.info("")
    LOGGER.info("API URL: %s", url_str)

    # Determine authentication method
    username = confluence_config.username.get_secret_value()
    api_token = confluence_config.api_token.get_secret_value()
    pat = confluence_config.pat.get_secret_value()

    if pat:
        LOGGER.info("Auth method: Personal Access Token (PAT)")
    elif username and api_token:
        LOGGER.info("Auth method: Basic Auth (username + API token)")
    else:
        LOGGER.error("✗ No authentication credentials configured")
        LOGGER.info("Run 'roundtripper confluence config' to set credentials")
        raise SystemExit(1)

    LOGGER.info("")
    LOGGER.info("Attempting to connect to Confluence API...")

    try:
        # Use the real API client to test connection
        client = get_confluence_client()

        # Try to get space list (lightweight operation)
        client.get_all_spaces(limit=1)

        LOGGER.info("✓ Connection successful!")
        LOGGER.info("✓ Successfully retrieved space list")
        LOGGER.info("")
        LOGGER.info("=" * 70)
        LOGGER.info("✓ All checks passed!")
        LOGGER.info("=" * 70)

    except ConnectionError as e:
        LOGGER.error("✗ Connection failed: %s", e)
        LOGGER.error("Please check:")
        LOGGER.error("  - Confluence URL is correct")
        LOGGER.error("  - Authentication credentials are valid")
        LOGGER.error("  - Network connectivity")
        LOGGER.error("  - SSL/TLS settings")
        raise SystemExit(1) from e
    except Exception as e:
        LOGGER.error("✗ Unexpected error: %s", e)
        raise SystemExit(1) from e


@app.command
def pull(
    *,
    space: str | None = None,
    page_id: int | None = None,
    output: Path = Path("./confluence-export"),
    recursive: bool = True,
    dry_run: bool = False,
) -> None:
    """Pull Confluence content to local storage.

    Downloads pages and attachments from Confluence, preserving the original
    Confluence storage format and all API metadata.

    Parameters
    ----------
    space
        Space key to pull all pages from.
    page_id
        Specific page ID to pull.
    output
        Output directory for downloaded content.
    recursive
        When pulling a specific page, also pull all descendants.
    dry_run
        Show what would be downloaded without actually downloading.
    """
    if not space and not page_id:
        LOGGER.error("Either --space or --page-id must be specified")
        raise SystemExit(1)

    if space and page_id:
        LOGGER.error("Cannot specify both --space and --page-id")
        raise SystemExit(1)

    # Get Confluence client
    try:
        client = get_confluence_client()
    except ConnectionError as e:
        LOGGER.error("Failed to connect to Confluence: %s", e)
        LOGGER.info("Run 'roundtripper confluence ping' to test your connection")
        raise SystemExit(1) from e

    # Create pull service
    service = PullService(client, output, dry_run=dry_run)

    if dry_run:
        LOGGER.info("[DRY RUN] Showing what would be downloaded...")
        LOGGER.info("")

    # Perform pull
    if space:
        LOGGER.info("Pulling space: %s", space)
        result = service.pull_space(space)
    else:
        assert page_id is not None  # for type checker
        LOGGER.info("Pulling page: %d (recursive=%s)", page_id, recursive)
        result = service.pull_page(page_id, recursive=recursive)

    # Summary
    LOGGER.info("")
    LOGGER.info("=" * 70)
    LOGGER.info("Pull Summary")
    LOGGER.info("=" * 70)
    LOGGER.info("Pages downloaded: %d", result.pages_downloaded)
    LOGGER.info("Pages skipped (up to date): %d", result.pages_skipped)
    LOGGER.info("Attachments downloaded: %d", result.attachments_downloaded)
    LOGGER.info("Attachments skipped (up to date): %d", result.attachments_skipped)

    if result.errors:
        LOGGER.warning("Errors encountered: %d", len(result.errors))
        for error in result.errors[:5]:  # Show first 5 errors
            LOGGER.warning("  - %s", error)
        if len(result.errors) > 5:
            LOGGER.warning("  ... and %d more errors", len(result.errors) - 5)
        raise SystemExit(1)

    LOGGER.info("")
    LOGGER.info("✓ Pull completed successfully!")
    LOGGER.info("Output directory: %s", output.absolute())
