"""Storage backends for encrypted document files."""

import contextlib
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import UUID

import aiofiles
import aiofiles.os


class StorageBackend(ABC):
    """Abstract interface for storing encrypted document files."""

    @abstractmethod
    async def store(self, document_id: UUID, side: str, data: bytes) -> str:
        """Store encrypted bytes and return a relative path for retrieval."""
        ...

    @abstractmethod
    async def retrieve(self, path: str) -> bytes:
        """Read encrypted bytes from a previously stored path."""
        ...

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Permanently remove the file at the given path."""
        ...


class LocalFileStorage(StorageBackend):
    """Stores encrypted files on the local filesystem.

    Path scheme:  ``{base_path}/{doc_id[:2]}/{doc_id[2:4]}/{doc_id}/{side}.enc``

    Sharding by the first few hex characters of the UUID prevents any single
    directory from accumulating too many entries.
    """

    def __init__(self, base_path: str) -> None:
        self._base = Path(base_path)

    def _resolve(self, path: str) -> Path:
        return self._base / path

    def _path_for(self, document_id: UUID, side: str) -> tuple[Path, str]:
        did = str(document_id)
        rel = Path(did[:2]) / did[2:4] / did / f"{side}.enc"
        return self._base / rel, str(rel)

    async def store(self, document_id: UUID, side: str, data: bytes) -> str:
        fs_path, rel_path = self._path_for(document_id, side)
        await aiofiles.os.makedirs(fs_path.parent, exist_ok=True)
        async with aiofiles.open(fs_path, "wb") as f:
            await f.write(data)
        return rel_path

    async def retrieve(self, path: str) -> bytes:
        fs_path = self._resolve(path)
        async with aiofiles.open(fs_path, "rb") as f:
            return await f.read()

    async def delete(self, path: str) -> None:
        fs_path = self._resolve(path)
        with contextlib.suppress(FileNotFoundError):
            await aiofiles.os.remove(fs_path)
