import asyncio
from datetime import timedelta
from typing import Any, BinaryIO, Dict, Optional

from minio import Minio
from minio.error import S3Error

from .base import BaseFileSystem


class MinioFileSystem(BaseFileSystem):
    """MinIO implementation of the filesystem interface for OSS users.

    Handles both internal (container-to-container) and external (browser) access:
    - endpoint: Used for API operations (uploads, downloads from code)
    - public_endpoint: Used for generating browser-accessible presigned URLs

    Auto-detection logic:
    1. If MINIO_PUBLIC_ENDPOINT env var is set, use it (for production/custom domains)
    2. If endpoint is "minio:9000" (Docker internal), auto-use "localhost:9000" for browser
    3. Otherwise, endpoint works for both (e.g., "localhost:9000" in local non-Docker setup)
    """

    def __init__(
        self,
        endpoint: str = "localhost:9000",
        access_key: str = "minioadmin",
        secret_key: str = "minioadmin",
        bucket_name: str = "voice-audio",
        secure: bool = False,
        public_endpoint: Optional[str] = None,
    ):
        self.bucket_name = bucket_name
        self.endpoint = endpoint
        self.public_endpoint = public_endpoint or endpoint
        self.secure = secure
        self.access_key = access_key
        self.secret_key = secret_key

        # Client for internal operations (uploads, etc.)
        self.client = Minio(
            endpoint, access_key=access_key, secret_key=secret_key, secure=secure
        )

        # Ensure bucket exists (using internal client)
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except Exception as e:
            # Bucket might already exist or we might be in a restricted environment
            pass

    async def acreate_file(self, file_path: str, content: BinaryIO) -> bool:
        try:
            data = await content.read()

            def _put():
                self.client.put_object(
                    self.bucket_name,
                    file_path,
                    data=bytes(data),
                    length=len(data),
                )

            await asyncio.to_thread(_put)
            return True
        except S3Error:
            return False

    async def aupload_file(self, local_path: str, destination_path: str) -> bool:
        try:

            def _fput():
                self.client.fput_object(self.bucket_name, destination_path, local_path)

            await asyncio.to_thread(_fput)
            return True
        except S3Error:
            return False

    async def aget_signed_url(
        self, file_path: str, expiration: int = 3600, force_inline: bool = False
    ) -> Optional[str]:
        try:

            def _presign():
                response_headers = None
                if force_inline and file_path.endswith(".txt"):
                    response_headers = {
                        "response-content-type": "text/plain",
                        "response-content-disposition": "inline",
                    }

                # Generate URL with the main client
                url = self.client.presigned_get_object(
                    self.bucket_name,
                    file_path,
                    expires=timedelta(seconds=expiration),
                    response_headers=response_headers,
                )

                # If we have different public endpoint, replace it in the URL
                if self.endpoint != self.public_endpoint:
                    # Simple string replacement since presigned URLs are just strings
                    # Replace the endpoint in the URL
                    url = url.replace(
                        f"://{self.endpoint}/", f"://{self.public_endpoint}/"
                    )
                    url = url.replace(
                        f"Host={self.endpoint}", f"Host={self.public_endpoint}"
                    )

                return url

            url = await asyncio.to_thread(_presign)
            return url
        except S3Error:
            return None

    async def aget_file_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get MinIO object metadata."""
        try:

            def _stat():
                return self.client.stat_object(self.bucket_name, file_path)

            stat = await asyncio.to_thread(_stat)
            return {
                "size": stat.size,
                "created_at": stat.last_modified,
                "modified_at": stat.last_modified,
                "etag": stat.etag.strip('"') if stat.etag else None,
                "content_type": stat.content_type,
                "storage_class": None,  # MinIO doesn't have storage classes like S3
            }
        except S3Error:
            return None
