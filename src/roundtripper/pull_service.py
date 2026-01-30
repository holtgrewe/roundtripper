"""Confluence pull service for downloading content.

This module contains the business logic for pulling Confluence content.
"""

import logging
from pathlib import Path
from typing import Any

from tqdm import tqdm

from roundtripper.file_utils import build_page_path, save_file, save_json
from roundtripper.models import AttachmentInfo, PageInfo, PullResult, SpaceInfo

#: Logger instance.
LOGGER = logging.getLogger(__name__)


class PullService:
    """Service for pulling Confluence content to local storage."""

    def __init__(
        self,
        client: Any,
        output_dir: Path,
        *,
        dry_run: bool = False,
    ) -> None:
        """Initialize the pull service.

        Parameters
        ----------
        client
            Confluence API client (atlassian-python-api Confluence instance).
        output_dir
            Base output directory for downloaded content.
        dry_run
            If True, only show what would be downloaded without actually downloading.
        """
        self.client = client
        self.output_dir = output_dir
        self.dry_run = dry_run
        self.result = PullResult()
        self._ancestor_cache: dict[int, str] = {}

    def pull_space(self, space_key: str) -> PullResult:
        """Pull all pages from a Confluence space.

        Parameters
        ----------
        space_key
            The space key to pull.

        Returns
        -------
        PullResult
            Summary of the pull operation.
        """
        LOGGER.info("Fetching space info for: %s", space_key)

        space_data = self.client.get_space(space_key, expand="homepage")
        space = SpaceInfo.from_api_response(space_data)

        if space.homepage_id is None:
            LOGGER.warning("Space '%s' has no homepage. Nothing to pull.", space_key)
            return self.result

        # Get all descendant page IDs
        page_ids = self._get_all_descendant_ids(space.homepage_id)
        page_ids.insert(0, space.homepage_id)

        LOGGER.info("Found %d pages to pull", len(page_ids))

        # Pull each page with progress bar
        for page_id in tqdm(page_ids, desc="Pulling pages", disable=self.dry_run):
            self._pull_page(page_id)

        return self.result

    def pull_page(self, page_id: int, *, recursive: bool = False) -> PullResult:
        """Pull a specific page and optionally its descendants.

        Parameters
        ----------
        page_id
            The page ID to pull.
        recursive
            If True, also pull all descendant pages.

        Returns
        -------
        PullResult
            Summary of the pull operation.
        """
        if recursive:
            page_ids = self._get_all_descendant_ids(page_id)
            page_ids.insert(0, page_id)
            LOGGER.info("Found %d pages to pull (including descendants)", len(page_ids))

            for pid in tqdm(page_ids, desc="Pulling pages", disable=self.dry_run):
                self._pull_page(pid)
        else:
            self._pull_page(page_id)

        return self.result

    def _get_all_descendant_ids(self, page_id: int) -> list[int]:
        """Get all descendant page IDs for a given page.

        Parameters
        ----------
        page_id
            The parent page ID.

        Returns
        -------
        list[int]
            List of descendant page IDs.
        """
        url = "rest/api/content/search"
        params: dict[str, Any] = {
            "cql": f"type=page AND ancestor={page_id}",
            "limit": 100,
        }
        results: list[dict[str, Any]] = []

        try:
            response = self.client.get(url, params=params)
            results.extend(response.get("results", []))
            next_path = response.get("_links", {}).get("next")

            while next_path:
                response = self.client.get(next_path)
                results.extend(response.get("results", []))
                next_path = response.get("_links", {}).get("next")

        except Exception as e:
            LOGGER.warning("Error fetching descendants for page %d: %s", page_id, e)
            return []

        return [int(result["id"]) for result in results]

    def _pull_page(self, page_id: int) -> None:
        """Pull a single page and its attachments.

        Parameters
        ----------
        page_id
            The page ID to pull.
        """
        try:
            page_data = self.client.get_page_by_id(
                page_id,
                expand="body.storage,body.view,body.export_view,body.editor2,"
                "metadata.labels,ancestors,version,space",
            )
            page = PageInfo.from_api_response(page_data)
        except Exception as e:
            error_msg = f"Failed to fetch page {page_id}: {e}"
            LOGGER.warning(error_msg)
            self.result.errors.append(error_msg)
            return

        # Get ancestor titles for building path
        ancestor_titles = self._get_ancestor_titles(page)

        # Build output path
        page_dir = build_page_path(
            self.output_dir,
            page.space_key,
            ancestor_titles,
            page.title,
        )

        if self.dry_run:
            LOGGER.info("[DRY RUN] Would create: %s", page_dir)
            self.result.pages_downloaded += 1
            return

        # Check if page already exists with same version
        page_json_path = page_dir / "page.json"
        if self._is_up_to_date(page_json_path, page.version.number):
            LOGGER.debug("Page '%s' is up to date, skipping", page.title)
            self.result.pages_skipped += 1
        else:
            # Save page content (Confluence storage format)
            self._save_page_content(page_dir, page)
            self.result.pages_downloaded += 1

        # Pull attachments
        self._pull_attachments(page_id, page_dir)

    def _get_ancestor_titles(self, page: PageInfo) -> list[str]:
        """Get ancestor page titles for building directory path.

        Parameters
        ----------
        page
            The page to get ancestors for.

        Returns
        -------
        list[str]
            List of ancestor titles from root to parent.
        """
        titles = []
        for ancestor_id in page.ancestors:
            if ancestor_id in self._ancestor_cache:
                titles.append(self._ancestor_cache[ancestor_id])
            else:
                try:
                    ancestor_data = self.client.get_page_by_id(ancestor_id, expand="")
                    title = ancestor_data.get("title", f"Page-{ancestor_id}")
                    self._ancestor_cache[ancestor_id] = title
                    titles.append(title)
                except Exception:  # pragma: no cover
                    title = f"Page-{ancestor_id}"
                    self._ancestor_cache[ancestor_id] = title
                    titles.append(title)
        return titles

    def _is_up_to_date(self, json_path: Path, current_version: int) -> bool:
        """Check if a page is up to date based on version number.

        Parameters
        ----------
        json_path
            Path to the existing page.json file.
        current_version
            Current version number from the API.

        Returns
        -------
        bool
            True if the local version matches the current version.
        """
        if not json_path.exists():
            return False

        try:
            import json

            with json_path.open("r") as f:
                existing_data = json.load(f)
            existing_version = existing_data.get("version", {}).get("number", 0)
            return existing_version >= current_version
        except Exception:  # pragma: no cover
            return False

    def _save_page_content(self, page_dir: Path, page: PageInfo) -> None:
        """Save page content and metadata to disk.

        Parameters
        ----------
        page_dir
            Directory to save the page in.
        page
            Page information to save.
        """
        # Save Confluence storage format
        confluence_path = page_dir / "page.confluence"
        save_file(confluence_path, page.body_storage)

        # Save raw API response
        json_path = page_dir / "page.json"
        save_json(json_path, page.raw_api_response)

        LOGGER.debug("Saved page: %s", page.title)

    def _pull_attachments(self, page_id: int, page_dir: Path) -> None:
        """Pull all attachments for a page.

        Parameters
        ----------
        page_id
            The page ID to get attachments for.
        page_dir
            Directory where the page is stored.
        """
        attachments_dir = page_dir / "attachments"
        start = 0
        limit = 50

        while True:
            try:
                response = self.client.get_attachments_from_content(
                    page_id,
                    start=start,
                    limit=limit,
                    expand="version",
                )
            except Exception as e:  # pragma: no cover
                LOGGER.warning("Failed to fetch attachments for page %d: %s", page_id, e)
                break

            results = response.get("results", [])
            if not results:
                break

            for att_data in results:
                attachment = AttachmentInfo.from_api_response(att_data)
                self._download_attachment(attachment, attachments_dir)

            size = response.get("size", 0)
            if size < limit:
                break
            start += size

    def _download_attachment(self, attachment: AttachmentInfo, attachments_dir: Path) -> None:
        """Download a single attachment.

        Parameters
        ----------
        attachment
            Attachment information.
        attachments_dir
            Directory to save attachments in.
        """
        filename = attachment.title
        file_path = attachments_dir / filename
        json_path = attachments_dir / f"{filename}.json"

        if self.dry_run:  # pragma: no cover
            LOGGER.info("[DRY RUN] Would download: %s", filename)
            self.result.attachments_downloaded += 1
            return

        # Check if attachment is up to date
        if self._is_attachment_up_to_date(json_path, attachment.version.number):
            LOGGER.debug("Attachment '%s' is up to date, skipping", filename)
            self.result.attachments_skipped += 1
            return

        # Download attachment content
        try:
            download_url = str(self.client.url) + attachment.download_link
            response = self.client._session.get(download_url)
            response.raise_for_status()
            content = response.content
        except Exception as e:
            error_msg = f"Failed to download attachment '{filename}': {e}"
            LOGGER.warning(error_msg)
            self.result.errors.append(error_msg)
            return

        # Save attachment and metadata
        save_file(file_path, content)
        save_json(json_path, attachment.raw_api_response)

        self.result.attachments_downloaded += 1
        LOGGER.debug("Downloaded attachment: %s", filename)

    def _is_attachment_up_to_date(self, json_path: Path, current_version: int) -> bool:
        """Check if an attachment is up to date based on version number.

        Parameters
        ----------
        json_path
            Path to the existing attachment metadata JSON file.
        current_version
            Current version number from the API.

        Returns
        -------
        bool
            True if the local version matches the current version.
        """
        if not json_path.exists():
            return False

        try:
            import json

            with json_path.open("r") as f:
                existing_data = json.load(f)
            existing_version = existing_data.get("version", {}).get("number", 0)
            return existing_version >= current_version
        except Exception:  # pragma: no cover
            return False
