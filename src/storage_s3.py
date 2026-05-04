"""Amazon S3 (and S3-compatible) storage backend."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import aioboto3
import structlog
from botocore.exceptions import ClientError

from src.exceptions import StorageError
from src.storage_backend import StorageBackend, validate_storage_key

logger = structlog.get_logger(__name__)


class S3StorageBackend(StorageBackend):
    """Store assets in an S3-compatible object store.

    Configuration is read from the environment:

    * ``S3_BUCKET`` -- bucket name (required)
    * ``S3_REGION`` -- AWS region (default ``us-east-1``)
    * ``S3_ENDPOINT_URL`` -- custom endpoint for MinIO / LocalStack
    * ``AWS_ACCESS_KEY_ID`` -- credentials (falls back to default chain)
    * ``AWS_SECRET_ACCESS_KEY``

    Args:
        bucket: Override bucket name.
        region: Override region.
        endpoint_url: Override endpoint URL.
    """

    def __init__(
        self,
        bucket: str | None = None,
        region: str | None = None,
        endpoint_url: str | None = None,
    ) -> None:
        self._bucket = bucket or os.getenv("S3_BUCKET", "")
        if not self._bucket:
            raise StorageError(
                "S3 bucket name is required.  Set S3_BUCKET env var "
                "or pass 'bucket' to the constructor."
            )
        self._region = region or os.getenv("S3_REGION", "us-east-1")
        self._endpoint_url: Optional[str] = endpoint_url or os.getenv(
            "S3_ENDPOINT_URL"
        )
        self._session = aioboto3.Session()
        logger.info(
            "storage.s3.init",
            bucket=self._bucket,
            region=self._region,
            endpoint_url=self._endpoint_url or "default",
        )

    @property
    def bucket(self) -> str:
        return self._bucket

    def _client_kwargs(self) -> Dict[str, Any]:
        """Build keyword arguments for ``session.client('s3', ...)``."""
        kwargs: Dict[str, Any] = {"region_name": self._region}
        if self._endpoint_url:
            kwargs["endpoint_url"] = self._endpoint_url
        return kwargs

    # ----- StorageBackend interface -----------------------------------------

    async def save(self, key: str, data: bytes, content_type: str) -> str:
        """Upload *data* to S3 under *key*."""
        validate_storage_key(key)
        try:
            async with self._session.client("s3", **self._client_kwargs()) as s3:
                await s3.put_object(
                    Bucket=self._bucket,
                    Key=key,
                    Body=data,
                    ContentType=content_type,
                )
            logger.info(
                "storage.s3.saved",
                key=key,
                bucket=self._bucket,
                size=len(data),
                content_type=content_type,
            )
            return key
        except ClientError as exc:
            raise StorageError(
                f"S3 put_object failed for key '{key}': {exc}"
            ) from exc

    async def get(self, key: str) -> bytes:
        """Download the object stored under *key*."""
        validate_storage_key(key)
        try:
            async with self._session.client("s3", **self._client_kwargs()) as s3:
                response = await s3.get_object(
                    Bucket=self._bucket, Key=key
                )
                data = await response["Body"].read()
            logger.debug(
                "storage.s3.get",
                key=key,
                bucket=self._bucket,
                size=len(data),
            )
            return data
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchKey":
                raise StorageError(f"Key not found in S3: {key}") from exc
            raise StorageError(
                f"S3 get_object failed for key '{key}': {exc}"
            ) from exc

    async def delete(self, key: str) -> None:
        """Delete the S3 object.  Idempotent -- no error if absent."""
        validate_storage_key(key)
        try:
            async with self._session.client("s3", **self._client_kwargs()) as s3:
                await s3.delete_object(
                    Bucket=self._bucket, Key=key
                )
            logger.info(
                "storage.s3.deleted",
                key=key,
                bucket=self._bucket,
            )
        except ClientError as exc:
            raise StorageError(
                f"S3 delete_object failed for key '{key}': {exc}"
            ) from exc

    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned download URL for *key*.

        Args:
            key: Storage key.
            expires_in: URL lifetime in seconds (default 1 hour).

        Returns:
            A presigned URL string.
        """
        validate_storage_key(key)
        try:
            async with self._session.client("s3", **self._client_kwargs()) as s3:
                url = await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self._bucket, "Key": key},
                    ExpiresIn=expires_in,
                )
            logger.debug(
                "storage.s3.presigned_url",
                key=key,
                bucket=self._bucket,
                expires_in=expires_in,
            )
            return url
        except ClientError as exc:
            raise StorageError(
                f"Failed to generate presigned URL for key '{key}': {exc}"
            ) from exc

    async def list_keys(self, prefix: str) -> List[str]:
        """List object keys matching *prefix* in the bucket."""
        if prefix:
            validate_storage_key(prefix.rstrip("/") or "campaigns")
        keys: List[str] = []
        try:
            async with self._session.client("s3", **self._client_kwargs()) as s3:
                paginator = s3.get_paginator("list_objects_v2")
                async for page in paginator.paginate(
                    Bucket=self._bucket, Prefix=prefix
                ):
                    for obj in page.get("Contents", []):
                        keys.append(obj["Key"])
            logger.debug(
                "storage.s3.list_keys",
                prefix=prefix,
                bucket=self._bucket,
                count=len(keys),
            )
            return keys
        except ClientError as exc:
            raise StorageError(
                f"S3 list_objects failed for prefix '{prefix}': {exc}"
            ) from exc
