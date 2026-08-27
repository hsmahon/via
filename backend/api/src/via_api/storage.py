"""S3 presigned URLs for the direct browser-to-storage flow.

Provides :class:`Presigner` which issues short-lived PUT targets for uploads
and presigned GET URLs for playback. Keeps dual boto3 clients so SDK calls
use an internal endpoint while presigned URLs embed a public endpoint for
browsers, falling back to real S3 when overrides are unset.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mypy_boto3_s3.client import S3Client

__all__ = ["Presigner"]


class Presigner:
    """Issues short-lived PUT URLs for video uploads.

    Optional endpoint overrides for testing (LocalStack); when both
    ``s3_endpoint_url`` and ``s3_public_endpoint_url`` are ``None``, uses
    real S3. When set, SDK calls run against the internal
    ``s3_endpoint_url`` (container network) while presigned URLs embed the
    public ``s3_public_endpoint_url`` so browsers on the host can complete
    the upload.
    """

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint_url: str | None = None,
        public_endpoint_url: str | None = None,
        expiry_seconds: int = 900,
    ) -> None:
        """Initialize the presigner.

        Args:
            bucket: Target bucket for uploads.
            region: AWS region for signature.
            endpoint_url: Optional S3 endpoint override for testing
                (LocalStack); ``None`` uses real S3.
            public_endpoint_url: Optional endpoint embedded into generated
                URLs (LocalStack); ``None`` reuses the primary client.
            expiry_seconds: Lifetime of issued URLs.
        """
        self._bucket = bucket
        self._expiry = expiry_seconds
        self._client: S3Client = _make_client(region=region, endpoint_url=endpoint_url)
        self._public_client: S3Client = (
            _make_client(region=region, endpoint_url=public_endpoint_url)
            if public_endpoint_url
            else self._client
        )

    def create_upload_target(
        self, *, user_id: str, video_id: str, filename: str, content_type: str | None
    ) -> dict[str, Any]:
        """Generate a presigned PUT target for one video object.

        Args:
            user_id: Owner scoping the object key.
            video_id: Video identifier scoping the object key.
            filename: Original filename terminating the key.
            content_type: Optional content type constraint.

        Returns:
            Dictionary matching :class:`via_api.schemas.UploadTarget`.
        """
        key = f"videos/{user_id}/{video_id}/{filename}"
        params: dict[str, Any] = {"Bucket": self._bucket, "Key": key}
        if content_type:
            params["ContentType"] = content_type
        url = self._public_client.generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=self._expiry,
        )
        return {"url": url, "method": "PUT", "expires_in_seconds": self._expiry}

    def create_download_url(self, *, key: str) -> str:
        """Generate a presigned GET URL for video playback.

        Args:
            key: S3 object key to fetch.

        Returns:
            Presigned URL string expiring after ``expiry_seconds``.
        """
        return self._public_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=self._expiry,
        )


def _make_client(*, region: str, endpoint_url: str | None) -> S3Client:
    """Build an S3 client for signing or transfer.

    Args:
        region: AWS region.
        endpoint_url: Optional endpoint override for testing (LocalStack);
            ``None`` uses real S3.

    Returns:
        Configured boto3 S3 client with SigV4 signing for presigned URLs.
    """
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        region_name=region,
        endpoint_url=endpoint_url or None,
        config=Config(signature_version="s3v4"),
    )
