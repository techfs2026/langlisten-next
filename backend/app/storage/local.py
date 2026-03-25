import aiofiles
from pathlib import Path

from app.storage.base import StorageBackend
from app.core.config import settings


class LocalStorage(StorageBackend):
    """
    Store files on the local filesystem under UPLOAD_DIR.
    The directory is also mounted as /uploads static route in main.py.
    """

    def __init__(self) -> None:
        self.base_dir = Path(settings.upload_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, data: bytes, filename: str) -> str:
        """
        Write bytes to disk.
        Returns the relative path (e.g. 'uploads/1234_audio.mp3'),
        which is stored in audio_materials.file_path.
        """
        dest = self.base_dir / filename
        async with aiofiles.open(dest, "wb") as f:
            await f.write(data)
        return str(dest)

    def get_url(self, path: str) -> str:
        """
        Convert storage path to a URL served by FastAPI StaticFiles.
        e.g. 'uploads/1234_audio.mp3' → '/uploads/1234_audio.mp3'
        """
        filename = Path(path).name
        return f"/uploads/{filename}"

    async def delete(self, path: str) -> None:
        dest = Path(path)
        if dest.exists():
            dest.unlink()