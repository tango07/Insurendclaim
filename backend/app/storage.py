"""File storage behind a small interface so it can be swapped for S3/GCS/Azure Blob later."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Protocol

# Allowed types: extension -> (content types accepted, magic-byte prefixes or None for text)
ALLOWED_TYPES: dict[str, tuple[set[str], list[bytes] | None]] = {
    ".jpg": ({"image/jpeg"}, [b"\xff\xd8\xff"]),
    ".jpeg": ({"image/jpeg"}, [b"\xff\xd8\xff"]),
    ".png": ({"image/png"}, [b"\x89PNG"]),
    ".webp": ({"image/webp"}, [b"RIFF"]),
    ".heic": ({"image/heic", "image/heif", "application/octet-stream"}, None),
    ".pdf": ({"application/pdf"}, [b"%PDF"]),
    ".txt": ({"text/plain"}, None),
}


class FileValidationError(ValueError):
    pass


def validate_file(filename: str, content_type: str | None, data: bytes, max_bytes: int) -> str:
    """Returns the normalised content type or raises FileValidationError with a user-friendly message."""
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_TYPES:
        allowed = ", ".join(sorted({e.lstrip('.').upper() for e in ALLOWED_TYPES}))
        raise FileValidationError(f"'{filename}': file type not allowed. Allowed types: {allowed}.")
    if len(data) == 0:
        raise FileValidationError(f"'{filename}': file is empty.")
    if len(data) > max_bytes:
        raise FileValidationError(f"'{filename}': file is {len(data) / 1048576:.1f} MB; the limit is {max_bytes / 1048576:.0f} MB.")
    types, magic = ALLOWED_TYPES[ext]
    if magic and not any(data.startswith(m) for m in magic):
        raise FileValidationError(f"'{filename}': file content does not match its {ext} extension.")
    ct = (content_type or "").split(";")[0].strip().lower()
    return ct if ct in types else next(iter(types))


class Storage(Protocol):
    def save(self, data: bytes, filename: str) -> str: ...
    def read(self, key: str) -> bytes: ...


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, filename: str) -> str:
        key = f"{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
        (self.root / key).write_bytes(data)
        return key

    def read(self, key: str) -> bytes:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise FileNotFoundError(key)
        return path.read_bytes()
