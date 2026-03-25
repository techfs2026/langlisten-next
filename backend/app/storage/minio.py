"""
MinIO storage backend.

Not used in MVP (STORAGE_BACKEND=local), but interface is fully implemented
so switching to MinIO only requires changing the env var.

Requires: pip install minio
(not in requirements.txt yet — add when needed)
"""

import io
from app.storage.base import StorageBackend
from app.core.config import settings


class MinioStorage(StorageBackend):

    def __init__(self) -> None:
        # lazy import so minio package is only required when actually used
        from minio import Minio
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_bucket
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    async def save(self, data: bytes, filename: str) -> str:
        """
        Upload bytes to MinIO.
        Returns the object key (filename), which is stored in file_path.
        """
        self.client.put_object(
            self.bucket,
            filename,
            io.BytesIO(data),
            length=len(data),
        )
        return filename

    def get_url(self, path: str) -> str:
        """
        Return a presigned URL valid for 7 days.
        For public buckets, use direct URL instead.
        """
        from datetime import timedelta
        url = self.client.presigned_get_object(
            self.bucket,
            path,
            expires=timedelta(days=7),
        )
        return url

    async def delete(self, path: str) -> None:
        self.client.remove_object(self.bucket, path)