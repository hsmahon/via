"""S3 presigned upload URLs for the direct client-to-storage flow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mypy_boto3_s3.client import S3Client

__all__ = ["Presigner"]


class Presigner:
    """Issues short-lived PUT URLs for video uploads.

    Uses two endpoint settings: SDK calls run against the internal
    ``s3_endpoint_url`` (container network), while presigned URLs embed the
    public ``s3_public_endpoint_url`` so browsers on the host can complete
    the upload. In production both are unset (real S3).
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
            endpoint_url: Internal S3-compatible endpoint, if any.
            public_endpoint_url: Endpoint embedded into generated URLs.
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


def _make_client(*, region: str, endpoint_url: str | None) -> S3Client:
    """Build an S3 client for signing or transfer.

    Args:
        region: AWS region.
        endpoint_url: Optional S3-compatible endpoint override.

    Returns:
        Configured boto3 S3 client.
    """
    import boto3

    return boto3.client("s3", region_name=region, endpoint_url=endpoint_url or None)
