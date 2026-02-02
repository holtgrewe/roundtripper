"""Confluence diff service for comparing local and remote content.

This module contains the business logic for comparing local Confluence content
with remote content and displaying differences.
"""

import logging
import os
import subprocess
import tempfile
from pathlib import Path

from atlassian import Confluence

from roundtripper.models import DiffResult
from roundtripper.pull_service import PullService

#: Logger instance.
LOGGER = logging.getLogger(__name__)


class DiffService:
    """Service for comparing local and remote Confluence content."""

    def __init__(
        self,
        client: Confluence,
        local_path: Path,
    ) -> None:
        """Initialize the diff service.

        Parameters
        ----------
        client
            Confluence API client (atlassian-python-api Confluence instance).
        local_path
            Path to the local content to compare.
        """
        self.client = client
        self.local_path = local_path
        self.result = DiffResult()

    def diff_space(self, space_key: str) -> DiffResult:
        """Compare local space content with remote Confluence space.

        Parameters
        ----------
        space_key
            The space key to compare.

        Returns
        -------
        DiffResult
            Result of the diff operation.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            LOGGER.info("Pulling latest content from Confluence space: %s", space_key)
            pull_service = PullService(self.client, temp_path)
            pull_result = pull_service.pull_space(space_key)

            if pull_result.errors:
                LOGGER.warning("Errors occurred during pull:")
                for error in pull_result.errors:
                    LOGGER.warning("  - %s", error)
                    self.result.errors.append(error)

            # Run diff
            self._run_diff(self.local_path, temp_path)

        return self.result

    def diff_page(self, page_id: int, *, recursive: bool = False) -> DiffResult:
        """Compare local page content with remote Confluence page.

        Parameters
        ----------
        page_id
            The page ID to compare.
        recursive
            If True, also compare all descendant pages.

        Returns
        -------
        DiffResult
            Result of the diff operation.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            LOGGER.info("Pulling latest content from Confluence page: %d", page_id)
            pull_service = PullService(self.client, temp_path)
            pull_result = pull_service.pull_page(page_id, recursive=recursive)

            if pull_result.errors:
                LOGGER.warning("Errors occurred during pull:")
                for error in pull_result.errors:
                    LOGGER.warning("  - %s", error)
                    self.result.errors.append(error)

            # Run diff
            self._run_diff(self.local_path, temp_path)

        return self.result

    def _run_diff(self, local_path: Path, remote_path: Path) -> None:
        """Run diff and display results through pager.

        Parameters
        ----------
        local_path
            Path to local content.
        remote_path
            Path to remote (freshly pulled) content.
        """
        # Get the pager command from environment or use default
        pager = os.environ.get("PAGER", "less -R")

        # Build diff command
        # Use unified diff format with colors and context
        # Only compare XML files (like push does), exclude JSON metadata
        diff_cmd = [
            "diff",
            "-urN",  # unified format, recursive, show new files
            "--color=always",  # colored output
            "--exclude=*.json",  # exclude JSON metadata files
            str(local_path),
            str(remote_path),
        ]

        try:
            # Run diff command
            diff_result = subprocess.run(
                diff_cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # diff exits with 0 if no changes, 1 if changes found, >1 for errors
            if diff_result.returncode > 1:
                error_msg = f"Diff command failed: {diff_result.stderr}"
                LOGGER.error(error_msg)
                self.result.errors.append(error_msg)
                return

            diff_output = diff_result.stdout

            if not diff_output:
                LOGGER.info("")
                LOGGER.info("=" * 70)
                LOGGER.info("✓ No differences found")
                LOGGER.info("=" * 70)
                LOGGER.info("")
                LOGGER.info("Local content is identical to remote Confluence content.")
                self.result.has_differences = False
                return

            self.result.has_differences = True

            # Display through pager
            LOGGER.info("")
            LOGGER.info("=" * 70)
            LOGGER.info("Displaying differences")
            LOGGER.info("=" * 70)
            LOGGER.info("")

            pager_cmd = pager.split()
            pager_process = subprocess.Popen(
                pager_cmd,
                stdin=subprocess.PIPE,
                text=True,
            )

            pager_process.communicate(input=diff_output)

            if pager_process.returncode != 0:
                # Fallback to direct print if pager fails
                LOGGER.warning("Pager failed, printing diff directly:")
                print(diff_output)

        except subprocess.TimeoutExpired:
            error_msg = "Diff command timed out"
            LOGGER.error(error_msg)
            self.result.errors.append(error_msg)
        except FileNotFoundError as e:
            error_msg = f"Command not found: {e.filename}"
            LOGGER.error(error_msg)
            LOGGER.error("Please ensure 'diff' is installed on your system")
            self.result.errors.append(error_msg)
        except Exception as e:
            error_msg = f"Error running diff: {e}"
            LOGGER.error(error_msg)
            self.result.errors.append(error_msg)
