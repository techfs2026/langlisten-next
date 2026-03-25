from functools import lru_cache

from app.storage.base import StorageBackend
from app.core.config import settings


@lru_cache(maxsize=1)
def get_storage() -> StorageBackend:
    """
    Factory function. Returns a singleton storage backend instance.
    Switch backend by setting STORAGE_BACKEND=local|minio in .env.
    """
    if settings.storage_backend == "minio":
        from app.storage.minio import MinioStorage
        return MinioStorage()

    from app.storage.local import LocalStorage
    return LocalStorage()