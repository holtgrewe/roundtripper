"""Confluence push service for uploading content.

This module contains the business logic for pushing Confluence content.
"""

import hashlib
import json
import logging
from pathlib import Path

from atlassian import Confluence
from tqdm import tqdm

from roundtripper.models import PageInfo, PushResult

#: Logger instance.
LOGGER = logging.getLogger(__name__)


class PushService:
    """Service for pushing local content to Confluence."""

    def __init__(
        self,
        client: Confluence,
        *,
        dry_run: bool = False,
        force: bool = False,
    ) -> None:
        """Initialize the push service.

        Parameters
        ----------
        client
            Confluence API client (atlassian-python-api Confluence instance).
        dry_run
            If True, only show what would be pushed without actually pushing.
        force
            If True, push even if there are version conflicts.
        """
        self.client = client
        self.dry_run = dry_run
        self.force = force
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
        self._push_page_at_path(page_path)

        if recursive:
            child_pages = self._find_child_pages(page_path)
            LOGGER.debug("Found %d child pages to push", len(child_pages))
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
        all_pages = self._find_all_pages(space_path)
        LOGGER.info("Found %d pages to analyze", len(all_pages))
        LOGGER.debug("Page paths: %s", [str(p) for p in all_pages])

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

            # Check if content has changed
            if not self._has_content_changed(page_info, local_content):
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
            else:
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

            # Handle attachments
            self._push_attachments(page_path, page_info.id)

        except Exception as e:
            error_msg = f"Failed to push {page_path}: {e}"
            LOGGER.warning(error_msg)
            self.result.errors.append(error_msg)

    def _has_content_changed(self, page_info: PageInfo, local_content: str) -> bool:
        """Check if local content differs from stored content.

        Parameters
        ----------
        page_info
            Page metadata from stored JSON.
        local_content
            Current content from page.xml file.

        Returns
        -------
        bool
            True if content has changed, False otherwise.
        """
        stored_content = page_info.body_storage
        return local_content.strip() != stored_content.strip()

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
        self.client.update_page(
            page_id=page_info.id,
            title=page_info.title,
            body=content,
            type="page",
        )

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

        for attachment_file in attachment_files:
            metadata_file = attachment_file.with_suffix(attachment_file.suffix + ".json")

            if self._should_push_attachment(attachment_file, metadata_file):
                if self.dry_run:
                    LOGGER.info("📎 WOULD UPLOAD: %s", attachment_file.name)
                else:
                    LOGGER.debug(
                        "Uploading attachment: %s to page %d", attachment_file.name, page_id
                    )
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
