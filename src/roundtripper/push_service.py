"""Confluence push service for uploading content.

This module contains the business logic for pushing Confluence content.
"""

import difflib
import hashlib
import json
import logging
from pathlib import Path

from atlassian import Confluence
from tqdm import tqdm

from roundtripper.file_utils import format_xml
from roundtripper.models import PageInfo, PushResult
from roundtripper.pull_service import PullService

#: Logger instance.
LOGGER = logging.getLogger(__name__)


class PushService:
    """Service for pushing local content to Confluence."""

    def __init__(
        self,
        client: Confluence,
        message: str,
        *,
        dry_run: bool = False,
        force: bool = False,
        interactive: bool = True,
    ) -> None:
        """Initialize the push service.

        Parameters
        ----------
        client
            Confluence API client (atlassian-python-api Confluence instance).
        message
            Version comment/message for updates.
        dry_run
            If True, only show what would be pushed without actually pushing.
        force
            If True, push even if there are version conflicts.
        interactive
            If True, prompt for confirmation before updating each page.
        """
        self.client = client
        self.message = message
        self.dry_run = dry_run
        self.force = force
        self.interactive = interactive
        self.result = PushResult()

    def push_page(self, page_path: Path, *, recursive: bool = False) -> PushResult:
        """Push a single page (and optionally descendants) to Confluence.

        Parameters
        ----------
        page_path
            Path to the page directory containing page.xml and page.json.
        recursive
            If True, also push all child pages in subdirectories.

        Returns
        -------
        PushResult
            Summary of the push operation.
        """
        LOGGER.debug("Starting push_page: path=%s, recursive=%s", page_path, recursive)
        LOGGER.info("Analyzing page at: %s", page_path)
        self._push_page_at_path(page_path)

        if recursive:
            LOGGER.info("Discovering child pages for recursive push...")
            child_pages = self._find_child_pages(page_path)
            LOGGER.debug("Found %d child pages to push", len(child_pages))
            if child_pages:
                LOGGER.info("Found %d child pages, starting push...", len(child_pages))
            for child_path in tqdm(child_pages, desc="Pushing child pages", disable=self.dry_run):
                self._push_page_at_path(child_path)

        return self.result

    def push_space(self, space_path: Path) -> PushResult:
        """Push all pages in a space directory to Confluence.

        Parameters
        ----------
        space_path
            Path to the space directory containing page subdirectories.

        Returns
        -------
        PushResult
            Summary of the push operation.
        """
        LOGGER.debug("Starting push_space: path=%s", space_path)
        LOGGER.info("Discovering all pages in space directory...")
        all_pages = self._find_all_pages(space_path)
        LOGGER.info("Found %d pages to analyze", len(all_pages))
        LOGGER.debug("Page paths: %s", [str(p) for p in all_pages])
        LOGGER.info("Starting push operations...")

        for page_path in tqdm(all_pages, desc="Pushing pages", disable=self.dry_run):
            self._push_page_at_path(page_path)

        return self.result

    def _push_page_at_path(self, page_path: Path) -> None:
        """Push a single page at the given path.

        Parameters
        ----------
        page_path
            Path to the page directory.
        """
        xml_file = page_path / "page.xml"
        json_file = page_path / "page.json"

        if not xml_file.exists() or not json_file.exists():
            LOGGER.warning("Skipping %s: missing page.xml or page.json", page_path)
            return

        try:
            # Load local content and metadata
            LOGGER.debug("Loading page files from %s", page_path)
            local_content = xml_file.read_text(encoding="utf-8")
            with json_file.open(encoding="utf-8") as f:
                local_metadata = json.load(f)

            page_info = PageInfo.from_api_response(local_metadata)
            LOGGER.debug(
                "Loaded page: id=%d, title=%s, version=%d",
                page_info.id,
                page_info.title,
                page_info.version.number,
            )

            # Check if content has changed and get server content for diff
            LOGGER.debug("Checking if content has changed for: %s", page_info.title)
            server_content = self._get_server_content(page_info)
            if not self._has_content_changed_with_server(local_content, server_content):
                LOGGER.debug("Skipping %s: content unchanged", page_info.title)
                self.result.pages_skipped += 1
                return

            # Check for version conflicts
            LOGGER.debug("Checking version conflict for page %d", page_info.id)
            conflict = self._check_version_conflict(page_info)
            if conflict and not self.force:
                LOGGER.debug("Version conflict detected: %s", conflict)
                self.result.conflicts.append(conflict)
                return

            # Push the page
            if self.dry_run:
                if conflict:
                    LOGGER.info(
                        "📝 WOULD UPDATE (force): %s (v%d → v%d)",
                        page_info.title,
                        page_info.version.number,
                        page_info.version.number + 1,
                    )
                else:
                    LOGGER.info(
                        "📝 WOULD UPDATE: %s (v%d → v%d)",
                        page_info.title,
                        page_info.version.number,
                        page_info.version.number + 1,
                    )
                # Show diff in dry-run mode
                self._show_diff(page_info.title, server_content, local_content)
            else:
                # Show diff if interactive mode
                if self.interactive:
                    self._show_diff(page_info.title, server_content, local_content)
                    LOGGER.info("")
                    response = input(f"Update '{page_info.title}'? [Y/n/q]: ").strip().lower()
                    if response == "q":
                        LOGGER.info("Quitting at user request")
                        raise SystemExit(0)
                    if response == "n":
                        LOGGER.info("Skipped: %s", page_info.title)
                        self.result.pages_skipped += 1
                        return
                    # Empty or 'y' continues

                LOGGER.debug(
                    "Calling update_page: page_id=%d, title=%s",
                    page_info.id,
                    page_info.title,
                )
                self._update_page(page_info, local_content)
                LOGGER.info(
                    "✓ Updated: %s (v%d → v%d)",
                    page_info.title,
                    page_info.version.number,
                    page_info.version.number + 1,
                )
                self.result.pages_updated += 1

                # Immediately refresh local files to avoid version conflicts next time
                LOGGER.debug("Refreshing local files after push: %s", page_path)
                self._refresh_local_page(page_info.id, page_path)

            # Handle attachments
            self._push_attachments(page_path, page_info.id)

        except Exception as e:
            error_msg = f"Failed to push {page_path}: {e}"
            LOGGER.warning(error_msg)
            self.result.errors.append(error_msg)

    def _get_server_content(self, page_info: PageInfo) -> str:
        """Fetch current content from server.

        Parameters
        ----------
        page_info
            Page metadata from stored JSON.

        Returns
        -------
        str
            Server content or stored content as fallback, formatted for comparison.
        """
        try:
            # Fetch current content from server with storage format
            server_response = self.client.get_page_by_id(
                page_info.id, expand="body.storage,version"
            )
            assert isinstance(server_response, dict)
            server_content = server_response.get("body", {}).get("storage", {}).get("value", "")
            # Format server XML to match local formatted XML for accurate comparison
            return format_xml(server_content)
        except Exception as e:  # pragma: no cover
            # If we can't fetch from server, fall back to stored content
            LOGGER.warning(
                "Could not fetch server content for page %d: %s. Using stored content.",
                page_info.id,
                e,
            )
            return page_info.body_storage

    def _has_content_changed_with_server(self, local_content: str, server_content: str) -> bool:
        """Check if local content differs from server content.

        Parameters
        ----------
        local_content
            Current content from page.xml file.
        server_content
            Current content from server.

        Returns
        -------
        bool
            True if content has changed, False otherwise.
        """
        # Compare normalized content (strip whitespace)
        local_normalized = local_content.strip()
        server_normalized = server_content.strip()
        return local_normalized != server_normalized

    def _show_diff(self, title: str, server_content: str, local_content: str) -> None:
        """Show unified diff between server and local content.

        Parameters
        ----------
        title
            Page title for display.
        server_content
            Current content from server.
        local_content
            New content from local file.
        """
        # Split into lines for difflib
        server_lines = server_content.splitlines(keepends=True)
        local_lines = local_content.splitlines(keepends=True)

        # Generate unified diff
        diff = difflib.unified_diff(
            server_lines,
            local_lines,
            fromfile=f"server/{title}",
            tofile=f"local/{title}",
            lineterm="",
        )

        # Print diff with some formatting
        diff_lines = list(diff)
        if diff_lines:
            LOGGER.info("")
            LOGGER.info("=" * 70)
            LOGGER.info("Diff for: %s", title)
            LOGGER.info("=" * 70)
            LOGGER.info("")
            for line in diff_lines:
                # Color the diff output
                if line.startswith("+++") or line.startswith("---"):
                    print(f"\033[1m{line}\033[0m", end="")  # Bold
                elif line.startswith("+"):
                    print(f"\033[32m{line}\033[0m", end="")  # Green
                elif line.startswith("-"):
                    print(f"\033[31m{line}\033[0m", end="")  # Red
                elif line.startswith("@@"):
                    print(f"\033[36m{line}\033[0m", end="")  # Cyan
                else:  # pragma: no cover
                    print(line, end="")
            print()

    def _refresh_local_page(self, page_id: int, page_path: Path) -> None:
        """Refresh local page files after successful push.

        Parameters
        ----------
        page_id
            The page ID that was just updated.
        page_path
            Path to the local page directory.
        """
        try:
            # Create a temporary PullService to refresh this page
            # Use the page's parent directory as output since pull creates the page dir
            pull_service = PullService(self.client, page_path.parent, dry_run=False)
            pull_service._pull_page(page_id)
            LOGGER.debug("Successfully refreshed local files for page %d", page_id)
        except Exception as e:  # pragma: no cover
            LOGGER.warning("Failed to refresh local files after push: %s", e)
            LOGGER.warning("You may need to manually pull this page to avoid version conflicts")

    def _check_version_conflict(self, page_info: PageInfo) -> str | None:
        """Check if server version is newer than local metadata.

        Parameters
        ----------
        page_info
            Page metadata from local JSON.

        Returns
        -------
        str | None
            Conflict message if conflict detected, None otherwise.
        """
        try:
            server_response = self.client.get_page_by_id(page_info.id, expand="version")
            assert isinstance(server_response, dict)
            server_version = server_response.get("version", {}).get("number", 0)
            LOGGER.debug(
                "Version check: page_id=%d, local=%d, server=%d",
                page_info.id,
                page_info.version.number,
                server_version,
            )

            if server_version > page_info.version.number:
                return (
                    f"Conflict: {page_info.title} - "
                    f"local version {page_info.version.number}, "
                    f"server version {server_version}"
                )
        except Exception as e:
            LOGGER.debug("Could not check version for page %d: %s", page_info.id, e)

        return None

    def _update_page(self, page_info: PageInfo, content: str) -> None:
        """Update a page on Confluence.

        Parameters
        ----------
        page_info
            Page metadata.
        content
            New content to push.
        """
        LOGGER.debug(
            "Calling Confluence API update_page: page_id=%d, title=%s",
            page_info.id,
            page_info.title,
        )
        self.client.update_page(
            page_id=page_info.id,
            title=page_info.title,
            body=content,
            type="page",
            version_comment=self.message,
        )
        LOGGER.debug("API call successful for page %d", page_info.id)

    def _push_attachments(self, page_path: Path, page_id: int) -> None:
        """Push attachments for a page.

        Parameters
        ----------
        page_path
            Path to the page directory.
        page_id
            Confluence page ID.
        """
        attachments_dir = page_path / "attachments"
        if not attachments_dir.exists():
            LOGGER.debug("No attachments directory at %s", attachments_dir)
            return

        attachment_files = [f for f in attachments_dir.iterdir() if f.suffix != ".json"]
        LOGGER.debug("Found %d attachment files in %s", len(attachment_files), attachments_dir)

        if attachment_files:
            LOGGER.info("Analyzing %d attachments...", len(attachment_files))

        for attachment_file in attachment_files:
            metadata_file = attachment_file.with_suffix(attachment_file.suffix + ".json")

            if self._should_push_attachment(attachment_file, metadata_file):
                if self.dry_run:
                    LOGGER.info("📎 WOULD UPLOAD: %s", attachment_file.name)
                else:
                    LOGGER.debug(
                        "Uploading attachment: %s to page %d", attachment_file.name, page_id
                    )
                    LOGGER.info("Uploading: %s", attachment_file.name)
                    self._upload_attachment(page_id, attachment_file)
                    LOGGER.info("✓ Uploaded: %s", attachment_file.name)
                    self.result.attachments_uploaded += 1
            else:
                LOGGER.debug("Skipping unchanged attachment: %s", attachment_file.name)
                self.result.attachments_skipped += 1

    def _should_push_attachment(self, attachment_file: Path, metadata_file: Path) -> bool:
        """Check if an attachment should be pushed.

        Parameters
        ----------
        attachment_file
            Path to the attachment file.
        metadata_file
            Path to the attachment metadata JSON file.

        Returns
        -------
        bool
            True if the attachment should be pushed.
        """
        if not metadata_file.exists():
            # New attachment, should push
            return True

        # Compare file hash with stored metadata
        with metadata_file.open(encoding="utf-8") as f:
            metadata = json.load(f)

        stored_size = metadata.get("extensions", {}).get("fileSize", 0)
        current_size = attachment_file.stat().st_size

        return current_size != stored_size

    def _upload_attachment(self, page_id: int, attachment_file: Path) -> None:
        """Upload an attachment to a page.

        Parameters
        ----------
        page_id
            Confluence page ID.
        attachment_file
            Path to the attachment file.
        """
        self.client.attach_file(
            filename=str(attachment_file),
            page_id=str(page_id),
            name=attachment_file.name,
        )

    def _find_child_pages(self, page_path: Path) -> list[Path]:
        """Find all child page directories under a page.

        Parameters
        ----------
        page_path
            Path to the parent page directory.

        Returns
        -------
        list[Path]
            List of paths to child page directories.
        """
        child_pages: list[Path] = []

        for item in page_path.iterdir():
            if item.is_dir() and item.name != "attachments":
                xml_file = item / "page.xml"
                if xml_file.exists():
                    child_pages.append(item)
                    # Recursively find grandchildren
                    child_pages.extend(self._find_child_pages(item))

        return child_pages

    def _find_all_pages(self, space_path: Path) -> list[Path]:
        """Find all page directories in a space.

        Parameters
        ----------
        space_path
            Path to the space directory.

        Returns
        -------
        list[Path]
            List of paths to all page directories.
        """
        all_pages: list[Path] = []

        def find_pages_recursive(directory: Path) -> None:
            for item in directory.iterdir():
                if item.is_dir():
                    xml_file = item / "page.xml"
                    if xml_file.exists():
                        all_pages.append(item)
                    # Always search subdirectories (except attachments)
                    if item.name != "attachments":
                        find_pages_recursive(item)

        find_pages_recursive(space_path)
        return all_pages


def compute_content_hash(content: str) -> str:
    """Compute SHA256 hash of content.

    Parameters
    ----------
    content
        Content to hash.

    Returns
    -------
    str
        Hex digest of the hash.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
