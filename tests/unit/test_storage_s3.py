"""Tests for the S3 storage backend with fully mocked aioboto3.

All S3 API calls are mocked -- no real AWS credentials or network access
is required.  Tests cover:

- save: put_object call parameters and content_type
- get: get_object call, body reading, NoSuchKey handling
- delete: delete_object call, idempotency, access-denied handling
- get_url: generate_presigned_url parameters
- list_keys: list_objects_v2 pagination and prefix filtering
- Configuration from environment variables
- Error handling: bucket not found, access denied, generic ClientError
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.exceptions import StorageError
from src.storage_s3 import S3StorageBackend


# ---------------------------------------------------------------------------
# Helpers for building mock S3 clients
# ---------------------------------------------------------------------------


def _client_error(code: str, message: str = "error") -> ClientError:
    """Build a botocore ClientError with the given error code."""
    return ClientError(
        {"Error": {"Code": code, "Message": message}},
        "TestOperation",
    )


class _MockBody:
    """Mimics the streaming body returned by get_object."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    async def read(self) -> bytes:
        return self._data


class _MockPaginator:
    """Mimics an aioboto3 paginator that yields pages asynchronously."""

    def __init__(self, pages: List[Dict[str, Any]]) -> None:
        self._pages = pages

    def paginate(self, **_kwargs) -> _MockPaginator:
        return self

    def __aiter__(self) -> _MockPaginator:
        self._index = 0
        return self

    async def __anext__(self) -> Dict[str, Any]:
        if self._index >= len(self._pages):
            raise StopAsyncIteration
        page = self._pages[self._index]
        self._index += 1
        return page


def _make_mock_s3(**overrides) -> AsyncMock:
    """Create a mock S3 client with sensible defaults.

    Any keyword argument overrides the corresponding method on the mock.
    """
    s3 = AsyncMock()
    s3.put_object = overrides.get("put_object", AsyncMock())
    s3.get_object = overrides.get("get_object", AsyncMock(return_value={"Body": _MockBody(b"")}))
    s3.delete_object = overrides.get("delete_object", AsyncMock())
    s3.generate_presigned_url = overrides.get(
        "generate_presigned_url",
        AsyncMock(return_value="https://s3.example.com/presigned"),
    )
    s3.get_paginator = overrides.get(
        "get_paginator",
        MagicMock(return_value=_MockPaginator([])),
    )
    return s3


# ---------------------------------------------------------------------------
# Fixture: patch aioboto3 session so client() returns our mock
# ---------------------------------------------------------------------------


@pytest.fixture()
def s3_backend(monkeypatch):
    """Return a (backend, mock_s3) tuple with aioboto3 fully patched.

    The mock S3 client is replaced via the backend._session attribute so
    that every ``async with self._session.client(...)`` yields the mock.
    """
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    monkeypatch.setenv("S3_REGION", "us-west-2")

    mock_s3 = _make_mock_s3()

    @asynccontextmanager
    async def _fake_client(*_args, **_kwargs):
        yield mock_s3

    session = MagicMock()
    session.client = _fake_client

    backend = S3StorageBackend(bucket="test-bucket", region="us-west-2")
    backend._session = session

    return backend, mock_s3


# ---------------------------------------------------------------------------
# Construction / environment
# ---------------------------------------------------------------------------


class TestS3StorageBackendInit:
    """Tests for S3StorageBackend initialization and configuration."""

    def test_bucket_from_constructor(self, monkeypatch):
        """Explicit bucket parameter should take precedence."""
        monkeypatch.delenv("S3_BUCKET", raising=False)
        backend = S3StorageBackend(bucket="my-bucket")
        assert backend.bucket == "my-bucket"

    def test_bucket_from_env(self, monkeypatch):
        """S3_BUCKET env var should be used when no parameter is given."""
        monkeypatch.setenv("S3_BUCKET", "env-bucket")
        backend = S3StorageBackend()
        assert backend.bucket == "env-bucket"

    def test_missing_bucket_raises(self, monkeypatch):
        """Omitting both parameter and env var should raise StorageError."""
        monkeypatch.delenv("S3_BUCKET", raising=False)
        with pytest.raises(StorageError, match="bucket name is required"):
            S3StorageBackend()

    def test_region_default(self, monkeypatch):
        """Default region should be us-east-1."""
        monkeypatch.setenv("S3_BUCKET", "b")
        monkeypatch.delenv("S3_REGION", raising=False)
        backend = S3StorageBackend()
        assert backend._region == "us-east-1"

    def test_region_from_env(self, monkeypatch):
        """S3_REGION env var should override the default."""
        monkeypatch.setenv("S3_BUCKET", "b")
        monkeypatch.setenv("S3_REGION", "eu-west-1")
        backend = S3StorageBackend()
        assert backend._region == "eu-west-1"

    def test_endpoint_url_from_env(self, monkeypatch):
        """S3_ENDPOINT_URL env var should be picked up."""
        monkeypatch.setenv("S3_BUCKET", "b")
        monkeypatch.setenv("S3_ENDPOINT_URL", "http://localhost:9000")
        backend = S3StorageBackend()
        assert backend._endpoint_url == "http://localhost:9000"

    def test_endpoint_url_from_param(self, monkeypatch):
        """endpoint_url parameter should take precedence over env."""
        monkeypatch.setenv("S3_BUCKET", "b")
        monkeypatch.setenv("S3_ENDPOINT_URL", "http://env")
        backend = S3StorageBackend(endpoint_url="http://param")
        assert backend._endpoint_url == "http://param"


# ---------------------------------------------------------------------------
# save
# ---------------------------------------------------------------------------


class TestS3StorageBackendSave:
    """Tests for S3StorageBackend.save()."""

    async def test_save_calls_put_object(self, s3_backend):
        """save() should call put_object with bucket, key, body, content_type."""
        backend, mock_s3 = s3_backend
        data = b"image-bytes"

        returned = await backend.save("assets/hero.png", data, "image/png")

        mock_s3.put_object.assert_awaited_once_with(
            Bucket="test-bucket",
            Key="assets/hero.png",
            Body=data,
            ContentType="image/png",
        )
        assert returned == "assets/hero.png"

    async def test_save_with_different_content_type(self, s3_backend):
        """save() should pass through arbitrary content types."""
        backend, mock_s3 = s3_backend

        await backend.save("data.json", b"{}", "application/json")

        call_kwargs = mock_s3.put_object.call_args.kwargs
        assert call_kwargs["ContentType"] == "application/json"

    async def test_save_client_error_wraps_in_storage_error(self, s3_backend):
        """A ClientError during put_object should be wrapped in StorageError."""
        backend, mock_s3 = s3_backend
        mock_s3.put_object.side_effect = _client_error("InternalError", "boom")

        with pytest.raises(StorageError, match="put_object failed"):
            await backend.save("fail.png", b"x", "image/png")

    async def test_save_validates_key(self, s3_backend):
        """save() should reject invalid keys before calling S3."""
        backend, mock_s3 = s3_backend

        with pytest.raises(ValueError):
            await backend.save("", b"x", "image/png")

        mock_s3.put_object.assert_not_awaited()


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


class TestS3StorageBackendGet:
    """Tests for S3StorageBackend.get()."""

    async def test_get_calls_get_object(self, s3_backend):
        """get() should call get_object and read the Body."""
        backend, mock_s3 = s3_backend
        payload = b"returned-data"
        mock_s3.get_object = AsyncMock(return_value={"Body": _MockBody(payload)})

        result = await backend.get("assets/hero.png")

        mock_s3.get_object.assert_awaited_once_with(
            Bucket="test-bucket",
            Key="assets/hero.png",
        )
        assert result == payload

    async def test_get_nosuchkey_raises_storage_error(self, s3_backend):
        """get() should wrap NoSuchKey ClientError in StorageError."""
        backend, mock_s3 = s3_backend
        mock_s3.get_object.side_effect = _client_error("NoSuchKey")

        with pytest.raises(StorageError, match="Key not found"):
            await backend.get("missing.png")

    async def test_get_generic_client_error_raises_storage_error(self, s3_backend):
        """get() should wrap non-NoSuchKey errors in StorageError."""
        backend, mock_s3 = s3_backend
        mock_s3.get_object.side_effect = _client_error("InternalError", "oops")

        with pytest.raises(StorageError, match="get_object failed"):
            await backend.get("assets/file.bin")

    async def test_get_validates_key(self, s3_backend):
        """get() should reject invalid keys."""
        backend, _ = s3_backend
        with pytest.raises(ValueError):
            await backend.get("path with spaces.png")


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestS3StorageBackendDelete:
    """Tests for S3StorageBackend.delete()."""

    async def test_delete_calls_delete_object(self, s3_backend):
        """delete() should call delete_object with the correct bucket and key."""
        backend, mock_s3 = s3_backend

        await backend.delete("assets/old.png")

        mock_s3.delete_object.assert_awaited_once_with(
            Bucket="test-bucket",
            Key="assets/old.png",
        )

    async def test_delete_is_idempotent(self, s3_backend):
        """delete() should not raise even when the key does not exist in S3."""
        backend, mock_s3 = s3_backend
        # S3 delete_object does not raise for missing keys by default
        mock_s3.delete_object = AsyncMock()

        # Should not raise
        await backend.delete("nonexistent.bin")

    async def test_delete_client_error_wraps(self, s3_backend):
        """A ClientError during delete_object should be wrapped."""
        backend, mock_s3 = s3_backend
        mock_s3.delete_object.side_effect = _client_error("AccessDenied")

        with pytest.raises(StorageError, match="delete_object failed"):
            await backend.delete("forbidden.bin")

    async def test_delete_validates_key(self, s3_backend):
        """delete() should reject invalid keys."""
        backend, _ = s3_backend
        with pytest.raises(ValueError):
            await backend.delete("../escape")


# ---------------------------------------------------------------------------
# get_url
# ---------------------------------------------------------------------------


class TestS3StorageBackendGetUrl:
    """Tests for S3StorageBackend.get_url()."""

    async def test_get_url_generates_presigned(self, s3_backend):
        """get_url() should call generate_presigned_url with correct params."""
        backend, mock_s3 = s3_backend
        mock_s3.generate_presigned_url = AsyncMock(
            return_value="https://s3.example.com/signed-url"
        )

        url = await backend.get_url("assets/img.png", expires_in=7200)

        mock_s3.generate_presigned_url.assert_awaited_once_with(
            "get_object",
            Params={"Bucket": "test-bucket", "Key": "assets/img.png"},
            ExpiresIn=7200,
        )
        assert url == "https://s3.example.com/signed-url"

    async def test_get_url_default_expiry(self, s3_backend):
        """get_url() default expires_in should be 3600 seconds."""
        backend, mock_s3 = s3_backend
        mock_s3.generate_presigned_url = AsyncMock(return_value="https://url")

        await backend.get_url("key.png")

        call_kwargs = mock_s3.generate_presigned_url.call_args
        assert call_kwargs.kwargs.get("ExpiresIn", call_kwargs[0][2] if len(call_kwargs[0]) > 2 else None) == 3600 or \
            mock_s3.generate_presigned_url.call_args[1].get("ExpiresIn") == 3600

    async def test_get_url_client_error_wraps(self, s3_backend):
        """A ClientError during URL generation should be wrapped."""
        backend, mock_s3 = s3_backend
        mock_s3.generate_presigned_url.side_effect = _client_error("InternalError")

        with pytest.raises(StorageError, match="presigned URL"):
            await backend.get_url("fail.png")

    async def test_get_url_validates_key(self, s3_backend):
        """get_url() should reject invalid keys."""
        backend, _ = s3_backend
        with pytest.raises(ValueError):
            await backend.get_url("")


# ---------------------------------------------------------------------------
# list_keys
# ---------------------------------------------------------------------------


class TestS3StorageBackendListKeys:
    """Tests for S3StorageBackend.list_keys()."""

    async def test_list_keys_single_page(self, s3_backend):
        """list_keys should collect keys from a single page of results."""
        backend, mock_s3 = s3_backend
        mock_s3.get_paginator = MagicMock(
            return_value=_MockPaginator([
                {
                    "Contents": [
                        {"Key": "campaigns/a/img1.png"},
                        {"Key": "campaigns/a/img2.png"},
                    ]
                }
            ])
        )

        keys = await backend.list_keys("campaigns/a")

        assert keys == ["campaigns/a/img1.png", "campaigns/a/img2.png"]

    async def test_list_keys_multiple_pages(self, s3_backend):
        """list_keys should handle paginated results correctly."""
        backend, mock_s3 = s3_backend
        mock_s3.get_paginator = MagicMock(
            return_value=_MockPaginator([
                {"Contents": [{"Key": "a/1.png"}]},
                {"Contents": [{"Key": "a/2.png"}]},
                {"Contents": [{"Key": "a/3.png"}]},
            ])
        )

        keys = await backend.list_keys("a")

        assert len(keys) == 3
        assert keys == ["a/1.png", "a/2.png", "a/3.png"]

    async def test_list_keys_empty_result(self, s3_backend):
        """list_keys should return empty list when no objects match."""
        backend, mock_s3 = s3_backend
        mock_s3.get_paginator = MagicMock(
            return_value=_MockPaginator([{"Contents": []}])
        )

        keys = await backend.list_keys("nothing")

        assert keys == []

    async def test_list_keys_page_without_contents(self, s3_backend):
        """list_keys should handle pages that have no Contents key."""
        backend, mock_s3 = s3_backend
        mock_s3.get_paginator = MagicMock(
            return_value=_MockPaginator([{}])
        )

        keys = await backend.list_keys("prefix")

        assert keys == []

    async def test_list_keys_client_error_wraps(self, s3_backend):
        """A ClientError during list_objects should be wrapped."""
        backend, mock_s3 = s3_backend

        paginator = MagicMock()

        class _ErrorPaginator:
            def paginate(self, **_kwargs):
                return self

            def __aiter__(self):
                return self

            async def __anext__(self):
                raise _client_error("NoSuchBucket", "bucket gone")

        mock_s3.get_paginator = MagicMock(return_value=_ErrorPaginator())

        with pytest.raises(StorageError, match="list_objects failed"):
            await backend.list_keys("prefix")

    async def test_list_keys_empty_prefix(self, s3_backend):
        """list_keys with empty prefix should still work."""
        backend, mock_s3 = s3_backend
        mock_s3.get_paginator = MagicMock(
            return_value=_MockPaginator([
                {"Contents": [{"Key": "file1.png"}, {"Key": "file2.png"}]}
            ])
        )

        keys = await backend.list_keys("")

        assert len(keys) == 2


# ---------------------------------------------------------------------------
# client_kwargs
# ---------------------------------------------------------------------------


class TestS3ClientKwargs:
    """Tests for _client_kwargs() helper."""

    def test_includes_region(self, monkeypatch):
        """_client_kwargs should always include region_name."""
        monkeypatch.setenv("S3_BUCKET", "b")
        backend = S3StorageBackend(region="ap-south-1")
        kwargs = backend._client_kwargs()
        assert kwargs["region_name"] == "ap-south-1"

    def test_includes_endpoint_url_when_set(self, monkeypatch):
        """_client_kwargs should include endpoint_url when configured."""
        monkeypatch.setenv("S3_BUCKET", "b")
        backend = S3StorageBackend(endpoint_url="http://minio:9000")
        kwargs = backend._client_kwargs()
        assert kwargs["endpoint_url"] == "http://minio:9000"

    def test_excludes_endpoint_url_when_none(self, monkeypatch):
        """_client_kwargs should omit endpoint_url when not configured."""
        monkeypatch.setenv("S3_BUCKET", "b")
        monkeypatch.delenv("S3_ENDPOINT_URL", raising=False)
        backend = S3StorageBackend()
        kwargs = backend._client_kwargs()
        assert "endpoint_url" not in kwargs
