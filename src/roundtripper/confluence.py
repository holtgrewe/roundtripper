"""Confluence commands for roundtripper."""

import logging
import sys
from typing import Any

import cyclopts
import httpx

from roundtripper.config_store import get_settings

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
    from roundtripper.config_interactive import main_config_menu_loop

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
        sys.exit(1)

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
        auth_header = {"Authorization": f"Bearer {pat}"}
    elif username and api_token:
        LOGGER.info("Auth method: Basic Auth (username + API token)")
        auth_header = {}  # httpx.BasicAuth will handle this
    else:
        LOGGER.error("✗ No authentication credentials configured")
        LOGGER.info("Run 'roundtripper confluence config' to set credentials")
        sys.exit(1)

    LOGGER.info("")
    LOGGER.info("Attempting to connect to Confluence API...")

    try:
        # Test connection with /rest/api/space endpoint (lightweight)
        test_url = f"{url_str.rstrip('/')}/rest/api/space"

        client_kwargs: dict[str, Any] = {
            "timeout": 10.0,
            "verify": settings.connection_config.verify_ssl,
        }

        if pat:
            client_kwargs["headers"] = auth_header
        else:
            client_kwargs["auth"] = (username, api_token)

        with httpx.Client(**client_kwargs) as client:
            response = client.get(test_url, params={"limit": 1})

            if response.status_code == 200:
                LOGGER.info("✓ Connection successful!")
                data = response.json()
                if "size" in data:
                    LOGGER.info("✓ Successfully retrieved space list")
                LOGGER.info("")
                LOGGER.info("=" * 70)
                LOGGER.info("✓ All checks passed!")
                LOGGER.info("=" * 70)
                sys.exit(0)
            elif response.status_code == 401:
                LOGGER.error("✗ Authentication failed (401 Unauthorized)")
                LOGGER.error("Please check your credentials")
                sys.exit(1)
            elif response.status_code == 403:
                LOGGER.error("✗ Access forbidden (403 Forbidden)")
                LOGGER.error("Your credentials may lack necessary permissions")
                sys.exit(1)
            else:
                LOGGER.error(
                    "✗ Unexpected response: %d %s",
                    response.status_code,
                    response.reason_phrase,
                )
                sys.exit(1)

    except httpx.ConnectError as e:
        LOGGER.error("✗ Connection failed: %s", e)
        LOGGER.error("Please check:")
        LOGGER.error("  - Confluence URL is correct")
        LOGGER.error("  - Network connectivity")
        LOGGER.error("  - SSL/TLS settings")
        sys.exit(1)
    except httpx.TimeoutException:
        LOGGER.error("✗ Connection timeout")
        LOGGER.error("The server took too long to respond")
        sys.exit(1)
    except Exception as e:
        LOGGER.error("✗ Unexpected error: %s", e)
        sys.exit(1)
