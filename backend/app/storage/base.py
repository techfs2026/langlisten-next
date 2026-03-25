from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """
    Abstract storage backend.
    Implementations: LocalStorage, MinioStorage.
    Switch via STORAGE_BACKEND env var — business logic never changes.
    """

    @abstractmethod
    async def save(self, data: bytes, filename: str) -> str:
        """
        Save file data and return the storage path / object key.
        Caller uses the returned path to retrieve the file later.
        """

    @abstractmethod
    def get_url(self, path: str) -> str:
        """
        Return a URL that serves the file at the given path.
        For local storage: /uploads/<filename>
        For MinIO: presigned URL or public URL
        """

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Delete the file at the given path / key."""