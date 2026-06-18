"""File utility functions for DocHistory."""
import hashlib
import os
import re
import zlib
from pathlib import Path

SUPPORTED_EXTENSIONS = {".docx", ".doc", ".wps"}

# Patterns for temporary/lock files created by Word/WPS
TEMP_PATTERNS = [
    re.compile(r"^~"),             # Word temp: ~$file.docx, ~WRD0001, ~DFTxxxx
    re.compile(r"^\.~"),           # LibreOffice lock: .~lock.file.docx#
    re.compile(r"\.tmp$", re.IGNORECASE),  # .tmp extension
    re.compile(r"\.bak$", re.IGNORECASE),  # .bak backup files
]


def compute_md5(file_path: str) -> str:
    """Compute MD5 hash of a file's contents."""
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


def compress_data(data: bytes) -> bytes:
    """Compress bytes using zlib."""
    return zlib.compress(data, level=6)


def decompress_data(compressed: bytes) -> bytes:
    """Decompress zlib-compressed bytes."""
    return zlib.decompress(compressed)


def is_temp_file(file_path: str) -> bool:
    """Check if a file is a temporary/lock file that should be ignored."""
    basename = os.path.basename(file_path)
    for pattern in TEMP_PATTERNS:
        if pattern.search(basename):
            return True
    return False


def is_supported_file(file_path: str) -> bool:
    """Check if a file has a supported extension (.docx, .doc, .wps)."""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in SUPPORTED_EXTENSIONS


def get_data_dir() -> Path:
    """Get the application data directory (cross-platform)."""
    import platform
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:  # Linux and others
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "DocHistory"


def get_db_path() -> Path:
    """Get the database file path."""
    return get_data_dir() / "dochistory.db"
