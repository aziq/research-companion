import uuid
from pathlib import Path

_STORAGE_DIR = Path(__file__).parent.parent / "data" / "files"


def save_file(data: bytes, suffix: str) -> str:
    """Save bytes to the persistent file store. Returns a path string relative to the project root."""
    _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{suffix}"
    path = _STORAGE_DIR / name
    path.write_bytes(data)
    return str(path.relative_to(Path(__file__).parent.parent))


def save_file_from_path(src: str, suffix: str = "") -> str:
    """Copy an existing file into the store. Returns relative path."""
    import shutil
    _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    src_path = Path(src)
    if not suffix:
        suffix = src_path.suffix
    name = f"{uuid.uuid4().hex}{suffix}"
    dest = _STORAGE_DIR / name
    shutil.copy2(src, dest)
    return str(dest.relative_to(Path(__file__).parent.parent))


def full_path(relative: str) -> Path:
    """Resolve a stored relative path back to an absolute Path."""
    return Path(__file__).parent.parent / relative
