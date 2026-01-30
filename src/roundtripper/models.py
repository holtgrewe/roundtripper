"""Pydantic models for Confluence data structures.

Based on confluence-markdown-exporter by Sebastian Penhouet.
https://github.com/Spenhouet/confluence-markdown-exporter
"""

from typing import Any

from pydantic import BaseModel, Field


class User(BaseModel):
    """Confluence user information."""

    account_id: str = ""
    username: str = ""
    display_name: str = ""
    public_name: str = ""
    email: str = ""

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "User":
        """Create a User from API response data.

        Parameters
        ----------
        data
            API response dictionary.

        Returns
        -------
        User
            User instance.
        """
        return cls(
            account_id=data.get("accountId", ""),
            username=data.get("username", ""),
            display_name=data.get("displayName", ""),
            public_name=data.get("publicName", ""),
            email=data.get("email", ""),
        )


class Version(BaseModel):
    """Page/attachment version information."""

    number: int = 0
    when: str = ""
    friendly_when: str = ""
    by: User = Field(default_factory=User)

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "Version":
        """Create a Version from API response data.

        Parameters
        ----------
        data
            API response dictionary.

        Returns
        -------
        Version
            Version instance.
        """
        return cls(
            number=data.get("number", 0),
            when=data.get("when", ""),
            friendly_when=data.get("friendlyWhen", ""),
            by=User.from_api_response(data.get("by", {})),
        )


class Label(BaseModel):
    """Confluence label/tag."""

    id: str = ""
    name: str = ""
    prefix: str = ""

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "Label":
        """Create a Label from API response data.

        Parameters
        ----------
        data
            API response dictionary.

        Returns
        -------
        Label
            Label instance.
        """
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            prefix=data.get("prefix", ""),
        )


class SpaceInfo(BaseModel):
    """Confluence space information."""

    key: str = ""
    name: str = ""
    description: str = ""
    homepage_id: int | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "SpaceInfo":
        """Create a SpaceInfo from API response data.

        Parameters
        ----------
        data
            API response dictionary.

        Returns
        -------
        SpaceInfo
            SpaceInfo instance.
        """
        homepage = data.get("homepage", {})
        homepage_id = homepage.get("id") if homepage else None
        if homepage_id is not None:
            homepage_id = int(homepage_id)

        return cls(
            key=data.get("key", ""),
            name=data.get("name", ""),
            description=data.get("description", {}).get("plain", {}).get("value", ""),
            homepage_id=homepage_id,
        )


class AttachmentInfo(BaseModel):
    """Confluence attachment information."""

    id: str = ""
    title: str = ""
    file_size: int = 0
    media_type: str = ""
    file_id: str = ""
    download_link: str = ""
    comment: str = ""
    version: Version = Field(default_factory=Version)
    raw_api_response: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "AttachmentInfo":
        """Create an AttachmentInfo from API response data.

        Parameters
        ----------
        data
            API response dictionary.

        Returns
        -------
        AttachmentInfo
            AttachmentInfo instance.
        """
        extensions = data.get("extensions", {})
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            file_size=extensions.get("fileSize", 0),
            media_type=extensions.get("mediaType", ""),
            file_id=extensions.get("fileId", ""),
            download_link=data.get("_links", {}).get("download", ""),
            comment=extensions.get("comment", ""),
            version=Version.from_api_response(data.get("version", {})),
            raw_api_response=data,
        )


class PageInfo(BaseModel):
    """Confluence page information."""

    id: int = 0
    title: str = ""
    space_key: str = ""
    body_storage: str = ""
    body_view: str = ""
    body_export_view: str = ""
    body_editor2: str = ""
    labels: list[Label] = Field(default_factory=list)
    ancestors: list[int] = Field(default_factory=list)
    version: Version = Field(default_factory=Version)
    raw_api_response: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "PageInfo":
        """Create a PageInfo from API response data.

        Parameters
        ----------
        data
            API response dictionary containing page data.

        Returns
        -------
        PageInfo
            PageInfo instance.
        """
        body = data.get("body", {})
        labels_data = data.get("metadata", {}).get("labels", {}).get("results", [])
        ancestors_data = data.get("ancestors", [])

        # Extract space key from expandable link or space object
        space_key = ""
        if "space" in data:
            space_key = data["space"].get("key", "")
        elif "_expandable" in data:
            space_link = data["_expandable"].get("space", "")
            if space_link:
                space_key = space_link.split("/")[-1]

        return cls(
            id=int(data.get("id", 0)),
            title=data.get("title", ""),
            space_key=space_key,
            body_storage=body.get("storage", {}).get("value", ""),
            body_view=body.get("view", {}).get("value", ""),
            body_export_view=body.get("export_view", {}).get("value", ""),
            body_editor2=body.get("editor2", {}).get("value", ""),
            labels=[Label.from_api_response(label) for label in labels_data],
            ancestors=[int(a.get("id", 0)) for a in ancestors_data],
            version=Version.from_api_response(data.get("version", {})),
            raw_api_response=data,
        )


class PullResult(BaseModel):
    """Result of a pull operation."""

    pages_downloaded: int = 0
    attachments_downloaded: int = 0
    pages_skipped: int = 0
    attachments_skipped: int = 0
    errors: list[str] = Field(default_factory=list)
