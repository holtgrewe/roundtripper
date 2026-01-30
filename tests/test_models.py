"""Tests for Pydantic models."""

from roundtripper.models import (
    AttachmentInfo,
    Label,
    PageInfo,
    PullResult,
    PushResult,
    SpaceInfo,
    User,
    Version,
)


class TestUser:
    """Tests for User model."""

    def test_default_values(self) -> None:
        """Test that default values are set."""
        user = User()
        assert user.account_id == ""
        assert user.username == ""
        assert user.display_name == ""
        assert user.public_name == ""
        assert user.email == ""

    def test_from_api_response(self) -> None:
        """Test creating User from API response."""
        data = {
            "accountId": "123",
            "username": "jdoe",
            "displayName": "John Doe",
            "publicName": "John",
            "email": "john@example.com",
        }
        user = User.from_api_response(data)
        assert user.account_id == "123"
        assert user.username == "jdoe"
        assert user.display_name == "John Doe"
        assert user.public_name == "John"
        assert user.email == "john@example.com"

    def test_from_empty_response(self) -> None:
        """Test creating User from empty response."""
        user = User.from_api_response({})
        assert user.account_id == ""
        assert user.username == ""


class TestVersion:
    """Tests for Version model."""

    def test_default_values(self) -> None:
        """Test that default values are set."""
        version = Version()
        assert version.number == 0
        assert version.when == ""
        assert version.friendly_when == ""
        assert version.by.username == ""

    def test_from_api_response(self) -> None:
        """Test creating Version from API response."""
        data = {
            "number": 5,
            "when": "2024-01-15T10:30:00Z",
            "friendlyWhen": "Jan 15, 2024",
            "by": {"username": "jdoe", "displayName": "John Doe"},
        }
        version = Version.from_api_response(data)
        assert version.number == 5
        assert version.when == "2024-01-15T10:30:00Z"
        assert version.friendly_when == "Jan 15, 2024"
        assert version.by.username == "jdoe"


class TestLabel:
    """Tests for Label model."""

    def test_from_api_response(self) -> None:
        """Test creating Label from API response."""
        data = {"id": "123", "name": "important", "prefix": "global"}
        label = Label.from_api_response(data)
        assert label.id == "123"
        assert label.name == "important"
        assert label.prefix == "global"


class TestSpaceInfo:
    """Tests for SpaceInfo model."""

    def test_from_api_response(self) -> None:
        """Test creating SpaceInfo from API response."""
        data = {
            "key": "SPACE",
            "name": "My Space",
            "description": {"plain": {"value": "Space description"}},
            "homepage": {"id": "12345"},
        }
        space = SpaceInfo.from_api_response(data)
        assert space.key == "SPACE"
        assert space.name == "My Space"
        assert space.description == "Space description"
        assert space.homepage_id == 12345

    def test_from_api_response_no_homepage(self) -> None:
        """Test creating SpaceInfo when homepage is None."""
        data = {"key": "SPACE", "name": "My Space"}
        space = SpaceInfo.from_api_response(data)
        assert space.homepage_id is None


class TestAttachmentInfo:
    """Tests for AttachmentInfo model."""

    def test_from_api_response(self) -> None:
        """Test creating AttachmentInfo from API response."""
        data = {
            "id": "att123",
            "title": "document.pdf",
            "extensions": {
                "fileSize": 1024,
                "mediaType": "application/pdf",
                "fileId": "file-123",
                "comment": "Uploaded document",
            },
            "_links": {"download": "/download/attachments/123/document.pdf"},
            "version": {"number": 1},
        }
        attachment = AttachmentInfo.from_api_response(data)
        assert attachment.id == "att123"
        assert attachment.title == "document.pdf"
        assert attachment.file_size == 1024
        assert attachment.media_type == "application/pdf"
        assert attachment.file_id == "file-123"
        assert attachment.download_link == "/download/attachments/123/document.pdf"
        assert attachment.comment == "Uploaded document"
        assert attachment.version.number == 1
        assert attachment.raw_api_response == data


class TestPageInfo:
    """Tests for PageInfo model."""

    def test_from_api_response(self) -> None:
        """Test creating PageInfo from API response."""
        data = {
            "id": "12345",
            "title": "My Page",
            "space": {"key": "SPACE"},
            "body": {
                "storage": {"value": "<p>Storage content</p>"},
                "view": {"value": "<p>View content</p>"},
                "export_view": {"value": "<p>Export content</p>"},
                "editor2": {"value": "<p>Editor content</p>"},
            },
            "metadata": {"labels": {"results": [{"id": "1", "name": "tag1", "prefix": "global"}]}},
            "ancestors": [{"id": "100"}, {"id": "200"}],
            "version": {"number": 3},
        }
        page = PageInfo.from_api_response(data)
        assert page.id == 12345
        assert page.title == "My Page"
        assert page.space_key == "SPACE"
        assert page.body_storage == "<p>Storage content</p>"
        assert page.body_view == "<p>View content</p>"
        assert page.body_export_view == "<p>Export content</p>"
        assert page.body_editor2 == "<p>Editor content</p>"
        assert len(page.labels) == 1
        assert page.labels[0].name == "tag1"
        assert page.ancestors == [100, 200]
        assert page.version.number == 3
        assert page.raw_api_response == data

    def test_from_api_response_with_expandable_space(self) -> None:
        """Test extracting space key from _expandable link."""
        data = {
            "id": "12345",
            "title": "Page",
            "_expandable": {"space": "/rest/api/space/MYSPACE"},
        }
        page = PageInfo.from_api_response(data)
        assert page.space_key == "MYSPACE"


class TestPullResult:
    """Tests for PullResult model."""

    def test_default_values(self) -> None:
        """Test that default values are set."""
        result = PullResult()
        assert result.pages_downloaded == 0
        assert result.attachments_downloaded == 0
        assert result.pages_skipped == 0
        assert result.attachments_skipped == 0
        assert result.errors == []

    def test_can_add_errors(self) -> None:
        """Test adding errors to result."""
        result = PullResult()
        result.errors.append("Error 1")
        result.errors.append("Error 2")
        assert len(result.errors) == 2


class TestPushResult:
    """Tests for PushResult model."""

    def test_default_values(self) -> None:
        """Test that default values are set."""
        result = PushResult()
        assert result.pages_updated == 0
        assert result.pages_created == 0
        assert result.pages_skipped == 0
        assert result.attachments_uploaded == 0
        assert result.attachments_skipped == 0
        assert result.conflicts == []
        assert result.errors == []

    def test_can_add_conflicts(self) -> None:
        """Test adding conflicts to result."""
        result = PushResult()
        result.conflicts.append("Conflict 1")
        result.conflicts.append("Conflict 2")
        assert len(result.conflicts) == 2

    def test_can_add_errors(self) -> None:
        """Test adding errors to result."""
        result = PushResult()
        result.errors.append("Error 1")
        assert len(result.errors) == 1
