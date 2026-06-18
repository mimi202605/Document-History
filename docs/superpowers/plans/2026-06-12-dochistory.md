# DocHistory MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline desktop tool that tracks Word/WPS document modification history in real-time, with one-click rollback to any version.

**Architecture:** Three-layer architecture: PyQt6 GUI ↔ Core Engine (watchdog monitoring, document parsing, version management) ↔ SQLite3 storage. File snapshots stored as zlib-compressed blobs. GitHub Desktop style UI with system tray.

**Tech Stack:** Python 3.14, PyQt6 6.7+, watchdog 4.0+, python-docx 1.1+, sqlite3 (stdlib), zlib (stdlib), difflib (stdlib), pytest 9.0+

**Reference Spec:** `docs/superpowers/specs/2026-06-12-dochistory-design.md`

---

## File Structure

```
dochistory/
├── main.py                      # Entry point: create QApplication, init DB, start monitor, show window
├── core/
│   ├── __init__.py
│   ├── database.py              # Database class: all SQL, thread-safe with Lock
│   ├── file_monitor.py          # FileMonitor: watchdog Observer + debounce + on_moved/on_created
│   ├── document_parser.py       # BaseDocumentParser, DocxParser, Win32DocumentParser (stub)
│   └── version_manager.py       # VersionManager: create/query/rollback/cleanup, rename/move/save-as
├── ui/
│   ├── __init__.py
│   ├── main_window.py           # MainWindow: GitHub Desktop style layout (Plan B)
│   ├── diff_window.py           # DiffWindow: side-by-side text diff with color highlighting
│   ├── settings_window.py       # SettingsWindow: monitor paths, retention policy
│   └── tray.py                  # SystemTray: tray icon + context menu
├── utils/
│   ├── __init__.py
│   ├── file_utils.py            # MD5, zlib compress/decompress, temp file filter, data dir
│   └── diff_utils.py            # difflib wrapper: structured diff (added/removed/modified)
├── resources/
│   └── icons/                   # App icons (placeholder for MVP)
└── tests/
    ├── __init__.py
    ├── conftest.py              # Shared fixtures: temp DB, temp docx files
    ├── test_database.py
    ├── test_file_utils.py
    ├── test_document_parser.py
    ├── test_version_manager.py
    ├── test_diff_utils.py
    ├── test_file_monitor.py
    ├── test_rollback_flow.py
    ├── test_rename_move.py
    └── test_save_as.py
```

**Module responsibilities:**
- `database.py` — All SQL in one place. `Database` class with thread-safe `threading.Lock`. Methods: `add_folder`, `get_folders`, `get_files`, `create_version`, `get_versions`, `get_version_data`, `rollback_version`, `rename_file`, `move_file`, `deactivate_file`, `get_config`, `set_config`, `cleanup_versions`.
- `file_monitor.py` — `FileMonitor(QObject)` wraps watchdog `Observer`. Emits Qt signals: `file_saved(str)`, `file_moved(str, str)`, `file_created(str)`, `file_deleted(str)`. 500ms debounce via `threading.Timer`.
- `document_parser.py` — `BaseDocumentParser` ABC with `extract_text() -> str` and `get_snapshot(file_path) -> bytes`. `DocxParser` uses python-docx. `Win32DocumentParser` raises `NotImplementedError` on non-Windows.
- `version_manager.py` — `VersionManager(QObject)` orchestrates business logic. Methods: `create_version(file_path, note=None, is_auto=True)`, `get_versions(file_id)`, `rollback_to_version(file_id, version_id)`, `export_version(file_id, version_id, dest_path)`, `cleanup_old_versions(file_id)`, `handle_rename(src, dest)`, `handle_move(src, dest)`, `handle_save_as(new_file_path)`, `associate_history(new_file_id, source_file_id)`. Emits `version_created`, `file_renamed`, `rollback_done` signals.
- `file_utils.py` — `compute_md5(path) -> str`, `compress_data(data: bytes) -> bytes`, `decompress_data(data: bytes) -> bytes`, `is_temp_file(path) -> bool`, `is_supported_file(path) -> bool`, `get_data_dir() -> Path`, `get_db_path() -> Path`.
- `diff_utils.py` — `compute_diff(text_old: str, text_new: str) -> list[DiffLine]` where `DiffLine` has `type` (added/removed/unchanged/modified), `old_line`, `new_line`, `line_no`.
- `main_window.py` — `MainWindow(QMainWindow)`: top bar (folder dropdown + search), left file list, right version timeline + action buttons.
- `diff_window.py` — `DiffWindow(QWidget)`: two `QTextBrowser` side-by-side with HTML color highlighting.
- `settings_window.py` — `SettingsWindow(QDialog)`: monitor path management, retention config.
- `tray.py` — `SystemTray(QSystemTrayIcon)`: icon + context menu (pause/resume, show window, quit). Close event minimizes to tray.

---

## Task 1: Project Scaffolding

**Files:**
- Create: `dochistory/__init__.py` (empty)
- Create: `dochistory/core/__init__.py` (empty)
- Create: `dochistory/ui/__init__.py` (empty)
- Create: `dochistory/utils/__init__.py` (empty)
- Create: `dochistory/resources/icons/.gitkeep`
- Create: `tests/__init__.py` (empty)
- Create: `tests/conftest.py`
- Create: `requirements.txt`

- [ ] **Step 1: Create directory structure and empty init files**

Create all `__init__.py` files as empty files, plus `resources/icons/.gitkeep`.

- [ ] **Step 2: Create requirements.txt**

```
watchdog>=4.0.1
python-docx>=1.1.2
PyQt6>=6.7.0
pytest>=8.0
```

- [ ] **Step 3: Create conftest.py with shared fixtures**

```python
"""Shared test fixtures for DocHistory."""
import sqlite3
import tempfile
from pathlib import Path

import pytest
from docx import Document


@pytest.fixture
def temp_db_path(tmp_path):
    """Return a path for a temporary database file."""
    return tmp_path / "test_dochistory.db"


@pytest.fixture
def temp_docx(tmp_path):
    """Create a temporary docx file with given paragraphs. Returns path."""
    def _create(name="test.docx", paragraphs=None):
        if paragraphs is None:
            paragraphs = ["Hello World", "Second paragraph"]
        doc = Document()
        for p in paragraphs:
            doc.add_paragraph(p)
        path = tmp_path / name
        doc.save(str(path))
        return path
    return _create


@pytest.fixture
def temp_monitor_dir(tmp_path):
    """Create a temporary directory to use as a monitor folder."""
    monitor_dir = tmp_path / "monitored"
    monitor_dir.mkdir()
    return monitor_dir
```

- [ ] **Step 4: Verify test infrastructure works**

Run: `python -m pytest tests/ -v --collect-only`
Expected: "no tests ran" (collection succeeds, no errors)

- [ ] **Step 5: Commit**

```bash
git add dochistory/ tests/ requirements.txt
git commit -m "feat: scaffold project structure and test fixtures"
```

---

## Task 2: File Utilities (utils/file_utils.py)

**Files:**
- Create: `dochistory/utils/file_utils.py`
- Test: `tests/test_file_utils.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for file utility functions."""
import zlib
from pathlib import Path
from unittest.mock import patch

from dochistory.utils.file_utils import (
    compute_md5,
    compress_data,
    decompress_data,
    is_temp_file,
    is_supported_file,
    get_data_dir,
    get_db_path,
)


class TestComputeMd5:
    def test_returns_hex_string(self, tmp_path):
        path = tmp_path / "test.txt"
        path.write_bytes(b"hello world")
        result = compute_md5(str(path))
        assert isinstance(result, str)
        assert len(result) == 32

    def test_same_content_same_hash(self, tmp_path):
        p1 = tmp_path / "a.txt"
        p2 = tmp_path / "b.txt"
        p1.write_bytes(b"same content")
        p2.write_bytes(b"same content")
        assert compute_md5(str(p1)) == compute_md5(str(p2))

    def test_different_content_different_hash(self, tmp_path):
        p1 = tmp_path / "a.txt"
        p2 = tmp_path / "b.txt"
        p1.write_bytes(b"content a")
        p2.write_bytes(b"content b")
        assert compute_md5(str(p1)) != compute_md5(str(p2))


class TestCompressDecompress:
    def test_compress_decompress_roundtrip(self):
        original = b"Hello World " * 100
        compressed = compress_data(original)
        assert isinstance(compressed, bytes)
        assert decompress_data(compressed) == original

    def test_compressed_smaller_for_repetitive(self):
        original = b"AAAAAAAAAA" * 1000
        compressed = compress_data(original)
        assert len(compressed) < len(original)

    def test_decompress_invalid_raises(self):
        import pytest
        with pytest.raises(zlib.error):
            decompress_data(b"not compressed")


class TestIsTempFile:
    def test_word_temp_file_detected(self):
        assert is_temp_file("/path/~$report.docx") is True

    def test_tmp_extension_detected(self):
        assert is_temp_file("/path/report.tmp") is True

    def test_normal_file_not_temp(self):
        assert is_temp_file("/path/report.docx") is False

    def test_docx_lock_file(self):
        assert is_temp_file("/path/.~lock.report.docx#") is True


class TestIsSupportedFile:
    def test_docx_supported(self):
        assert is_supported_file("/path/report.docx") is True

    def test_doc_supported(self):
        assert is_supported_file("/path/report.doc") is True

    def test_wps_supported(self):
        assert is_supported_file("/path/report.wps") is True

    def test_txt_not_supported(self):
        assert is_supported_file("/path/report.txt") is False

    def test_case_insensitive(self):
        assert is_supported_file("/path/Report.DOCX") is True


class TestGetDataDir:
    def test_returns_path_object(self):
        result = get_data_dir()
        assert isinstance(result, Path)

    def test_contains_dochistory(self):
        result = get_data_dir()
        assert "DocHistory" in str(result)

    @patch("platform.system", return_value="Linux")
    def test_linux_uses_xdg(self, mock_system):
        result = get_data_dir()
        assert ".local/share" in str(result)


class TestGetDbPath:
    def test_returns_db_file(self):
        result = get_db_path()
        assert result.name == "dochistory.db"
        assert "DocHistory" in str(result)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_file_utils.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dochistory.utils.file_utils'`

- [ ] **Step 3: Write implementation**

```python
"""File utility functions for DocHistory."""
import hashlib
import os
import re
import zlib
from pathlib import Path

SUPPORTED_EXTENSIONS = {".docx", ".doc", ".wps"}

# Patterns for temporary/lock files created by Word/WPS
TEMP_PATTERNS = [
    re.compile(r"^~\$"),           # Word temp: ~$file.docx
    re.compile(r"^\.~lock\."),     # LibreOffice lock: .~lock.file.docx#
    re.compile(r"\.tmp$", re.IGNORECASE),  # .tmp extension
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_file_utils.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add dochistory/utils/file_utils.py tests/test_file_utils.py
git commit -m "feat: add file utilities (md5, compress, temp filter, data dir)"
```

---

## Task 3: Database Module (core/database.py)

**Files:**
- Create: `dochistory/core/database.py`
- Test: `tests/test_database.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for the Database module."""
import time
from pathlib import Path

import pytest

from dochistory.core.database import Database


@pytest.fixture
def db(temp_db_path):
    """Create a fresh Database instance."""
    database = Database(str(temp_db_path))
    yield database
    database.close()


class TestSchema:
    def test_tables_exist(self, db):
        tables = db.get_table_names()
        assert "monitored_folders" in tables
        assert "files" in tables
        assert "versions" in tables
        assert "config" in tables

    def test_default_config_inserted(self, db):
        assert db.get_config("max_versions_per_file") == "50"
        assert db.get_config("retention_days") == "30"
        assert db.get_config("auto_cleanup_enabled") == "1"
        assert db.get_config("compression_level") == "6"


class TestFolderManagement:
    def test_add_folder(self, db):
        folder_id = db.add_folder("/path/to/docs")
        assert folder_id > 0

    def test_add_duplicate_folder_raises(self, db):
        db.add_folder("/path/to/docs")
        with pytest.raises(ValueError):
            db.add_folder("/path/to/docs")

    def test_get_folders(self, db):
        db.add_folder("/path/a")
        db.add_folder("/path/b")
        folders = db.get_folders()
        assert len(folders) == 2
        assert folders[0]["path"] == "/path/a"

    def test_get_folders_only_active(self, db):
        fid = db.add_folder("/path/a")
        db.deactivate_folder(fid)
        folders = db.get_folders()
        assert len(folders) == 0

    def test_deactivate_folder(self, db):
        fid = db.add_folder("/path/a")
        db.deactivate_folder(fid)
        folders = db.get_folders(include_inactive=True)
        assert len(folders) == 1
        assert folders[0]["is_active"] == 0


class TestFileManagement:
    def test_add_file(self, db):
        folder_id = db.add_folder("/docs")
        file_id = db.add_file(folder_id, "report.docx", "abc123")
        assert file_id > 0

    def test_get_files_by_folder(self, db):
        folder_id = db.add_folder("/docs")
        db.add_file(folder_id, "a.docx", "hash_a")
        db.add_file(folder_id, "b.docx", "hash_b")
        files = db.get_files(folder_id)
        assert len(files) == 2

    def test_get_files_only_active(self, db):
        folder_id = db.add_folder("/docs")
        fid = db.add_file(folder_id, "a.docx", "hash_a")
        db.deactivate_file(fid)
        files = db.get_files(folder_id)
        assert len(files) == 0

    def test_find_file_by_path(self, db):
        folder_id = db.add_folder("/docs")
        db.add_file(folder_id, "report.docx", "hash1")
        found = db.find_file(folder_id, "report.docx")
        assert found is not None
        assert found["relative_path"] == "report.docx"

    def test_find_file_not_found(self, db):
        folder_id = db.add_folder("/docs")
        found = db.find_file(folder_id, "nonexistent.docx")
        assert found is None

    def test_rename_file(self, db):
        folder_id = db.add_folder("/docs")
        file_id = db.add_file(folder_id, "old.docx", "hash1")
        db.rename_file(file_id, "new.docx")
        found = db.find_file(folder_id, "new.docx")
        assert found is not None
        assert db.find_file(folder_id, "old.docx") is None

    def test_move_file(self, db):
        f1 = db.add_folder("/docs1")
        f2 = db.add_folder("/docs2")
        file_id = db.add_file(f1, "report.docx", "hash1")
        db.move_file(file_id, f2, "report.docx")
        assert len(db.get_files(f1)) == 0
        assert len(db.get_files(f2)) == 1


class TestVersionManagement:
    def test_create_version(self, db):
        folder_id = db.add_folder("/docs")
        file_id = db.add_file(folder_id, "report.docx", "hash1")
        version_id = db.create_version(file_id, 1, 1024, b"compressed_data")
        assert version_id > 0

    def test_get_versions(self, db):
        folder_id = db.add_folder("/docs")
        file_id = db.add_file(folder_id, "report.docx", "hash1")
        db.create_version(file_id, 1, 100, b"data1")
        db.create_version(file_id, 2, 200, b"data2", note="manual")
        versions = db.get_versions(file_id)
        assert len(versions) == 2
        # Newest first
        assert versions[0]["version_number"] == 2
        assert versions[0]["note"] == "manual"

    def test_get_version_data(self, db):
        folder_id = db.add_folder("/docs")
        file_id = db.add_file(folder_id, "report.docx", "hash1")
        vid = db.create_version(file_id, 1, 100, b"compressed_data")
        data = db.get_version_data(vid)
        assert data == b"compressed_data"

    def test_get_latest_version_number(self, db):
        folder_id = db.add_folder("/docs")
        file_id = db.add_file(folder_id, "report.docx", "hash1")
        db.create_version(file_id, 1, 100, b"d1")
        db.create_version(file_id, 2, 100, b"d2")
        assert db.get_latest_version_number(file_id) == 2

    def test_get_latest_version_number_no_versions(self, db):
        folder_id = db.add_folder("/docs")
        file_id = db.add_file(folder_id, "report.docx", "hash1")
        assert db.get_latest_version_number(file_id) == 0

    def test_cleanup_old_versions(self, db):
        folder_id = db.add_folder("/docs")
        file_id = db.add_file(folder_id, "report.docx", "hash1")
        for i in range(1, 6):
            db.create_version(file_id, i, 100, f"d{i}".encode())
        # Keep only latest 3
        deleted = db.cleanup_old_versions(file_id, max_versions=3)
        assert deleted == 2
        versions = db.get_versions(file_id)
        assert len(versions) == 3
        assert versions[0]["version_number"] == 5

    def test_update_file_hash(self, db):
        folder_id = db.add_folder("/docs")
        file_id = db.add_file(folder_id, "report.docx", "hash1")
        db.update_file_hash(file_id, "new_hash", 2048)
        found = db.find_file(folder_id, "report.docx")
        assert found["file_hash"] == "new_hash"


class TestConfig:
    def test_get_config_default(self, db):
        assert db.get_config("nonexistent", "default_val") == "default_val"

    def test_set_config(self, db):
        db.set_config("custom_key", "custom_value")
        assert db.get_config("custom_key") == "custom_value"

    def test_set_config_overwrite(self, db):
        db.set_config("max_versions_per_file", "100")
        assert db.get_config("max_versions_per_file") == "100"


class TestFindFileByHash:
    def test_find_file_by_hash(self, db):
        f1 = db.add_folder("/docs")
        db.add_file(f1, "report.docx", "special_hash")
        found = db.find_file_by_hash("special_hash")
        assert found is not None
        assert found["relative_path"] == "report.docx"

    def test_find_file_by_hash_not_found(self, db):
        assert db.find_file_by_hash("nonexistent") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_database.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

```python
"""SQLite database module for DocHistory."""
import sqlite3
import threading
from typing import Optional


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS monitored_folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_id INTEGER NOT NULL,
    relative_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    last_modified TIMESTAMP NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (folder_id) REFERENCES monitored_folders(id),
    UNIQUE(folder_id, relative_path)
);

CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    file_size INTEGER NOT NULL,
    modified_by TEXT,
    note TEXT,
    is_auto INTEGER DEFAULT 1,
    data BLOB NOT NULL,
    FOREIGN KEY (file_id) REFERENCES files(id),
    UNIQUE(file_id, version_number)
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

DEFAULT_CONFIG = {
    "max_versions_per_file": "50",
    "retention_days": "30",
    "auto_cleanup_enabled": "1",
    "compression_level": "6",
}


class Database:
    """Thread-safe SQLite database wrapper."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            self._conn.executescript(SCHEMA_SQL)
            for key, value in DEFAULT_CONFIG.items():
                self._conn.execute(
                    "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
                    (key, value),
                )
            self._conn.commit()

    def get_table_names(self) -> list[str]:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            return [row["name"] for row in cursor.fetchall()]

    # --- Config ---

    def get_config(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT value FROM config WHERE key = ?", (key,)
            )
            row = cursor.fetchone()
            return row["value"] if row else default

    def set_config(self, key: str, value: str):
        with self._lock:
            self._conn.execute(
                "INSERT INTO config (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            self._conn.commit()

    # --- Folder management ---

    def add_folder(self, path: str) -> int:
        with self._lock:
            try:
                cursor = self._conn.execute(
                    "INSERT INTO monitored_folders (path) VALUES (?)", (path,)
                )
                self._conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                raise ValueError(f"Folder already monitored: {path}")

    def get_folders(self, include_inactive: bool = False) -> list[dict]:
        with self._lock:
            if include_inactive:
                cursor = self._conn.execute("SELECT * FROM monitored_folders ORDER BY path")
            else:
                cursor = self._conn.execute(
                    "SELECT * FROM monitored_folders WHERE is_active = 1 ORDER BY path"
                )
            return [dict(row) for row in cursor.fetchall()]

    def deactivate_folder(self, folder_id: int):
        with self._lock:
            self._conn.execute(
                "UPDATE monitored_folders SET is_active = 0 WHERE id = ?", (folder_id,)
            )
            self._conn.commit()

    # --- File management ---

    def add_file(self, folder_id: int, relative_path: str, file_hash: str) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO files (folder_id, relative_path, file_hash, last_modified) "
                "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (folder_id, relative_path, file_hash),
            )
            self._conn.commit()
            return cursor.lastrowid

    def get_files(self, folder_id: int) -> list[dict]:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT * FROM files WHERE folder_id = ? AND is_active = 1 "
                "ORDER BY relative_path",
                (folder_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def find_file(self, folder_id: int, relative_path: str) -> Optional[dict]:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT * FROM files WHERE folder_id = ? AND relative_path = ?",
                (folder_id, relative_path),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_file_by_hash(self, file_hash: str) -> Optional[dict]:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT * FROM files WHERE file_hash = ? AND is_active = 1",
                (file_hash,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def rename_file(self, file_id: int, new_relative_path: str):
        with self._lock:
            self._conn.execute(
                "UPDATE files SET relative_path = ? WHERE id = ?",
                (new_relative_path, file_id),
            )
            self._conn.commit()

    def move_file(self, file_id: int, new_folder_id: int, new_relative_path: str):
        with self._lock:
            self._conn.execute(
                "UPDATE files SET folder_id = ?, relative_path = ? WHERE id = ?",
                (new_folder_id, new_relative_path, file_id),
            )
            self._conn.commit()

    def deactivate_file(self, file_id: int):
        with self._lock:
            self._conn.execute(
                "UPDATE files SET is_active = 0 WHERE id = ?", (file_id,)
            )
            self._conn.commit()

    def update_file_hash(self, file_id: int, new_hash: str, new_size: int):
        with self._lock:
            self._conn.execute(
                "UPDATE files SET file_hash = ?, last_modified = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (new_hash, file_id),
            )
            self._conn.commit()

    # --- Version management ---

    def create_version(
        self,
        file_id: int,
        version_number: int,
        file_size: int,
        data: bytes,
        note: Optional[str] = None,
        is_auto: bool = True,
        modified_by: Optional[str] = None,
    ) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO versions (file_id, version_number, timestamp, "
                "file_size, modified_by, note, is_auto, data) "
                "VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)",
                (file_id, version_number, file_size, modified_by, note,
                 1 if is_auto else 0, data),
            )
            self._conn.commit()
            return cursor.lastrowid

    def get_versions(self, file_id: int) -> list[dict]:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT id, file_id, version_number, timestamp, file_size, "
                "modified_by, note, is_auto FROM versions "
                "WHERE file_id = ? ORDER BY version_number DESC",
                (file_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_version_data(self, version_id: int) -> Optional[bytes]:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT data FROM versions WHERE id = ?", (version_id,)
            )
            row = cursor.fetchone()
            return row["data"] if row else None

    def get_latest_version_number(self, file_id: int) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT MAX(version_number) as max_ver FROM versions WHERE file_id = ?",
                (file_id,),
            )
            row = cursor.fetchone()
            return row["max_ver"] if row and row["max_ver"] else 0

    def cleanup_old_versions(self, file_id: int, max_versions: int) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT id FROM versions WHERE file_id = ? "
                "ORDER BY version_number DESC", (file_id,)
            )
            all_ids = [row["id"] for row in cursor.fetchall()]
            to_delete = all_ids[max_versions:]
            if to_delete:
                placeholders = ",".join("?" * len(to_delete))
                self._conn.execute(
                    f"DELETE FROM versions WHERE id IN ({placeholders})",
                    to_delete,
                )
                self._conn.commit()
            return len(to_delete)

    def close(self):
        with self._lock:
            self._conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_database.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add dochistory/core/database.py tests/test_database.py
git commit -m "feat: add SQLite database module with full schema and CRUD"
```

---

## Task 4: Document Parser (core/document_parser.py)

**Files:**
- Create: `dochistory/core/document_parser.py`
- Test: `tests/test_document_parser.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for document parsers."""
import pytest

from dochistory.core.document_parser import (
    BaseDocumentParser,
    DocxParser,
    Win32DocumentParser,
    get_parser_for_file,
)


class TestDocxParser:
    def test_extract_text(self, temp_docx):
        path = temp_docx("test.docx", ["Hello World", "Second paragraph"])
        parser = DocxParser()
        text = parser.extract_text(str(path))
        assert "Hello World" in text
        assert "Second paragraph" in text

    def test_extract_text_empty_doc(self, temp_docx):
        path = temp_docx("empty.docx", [])
        parser = DocxParser()
        text = parser.extract_text(str(path))
        assert text == ""

    def test_get_snapshot(self, temp_docx):
        path = temp_docx("test.docx", ["content"])
        parser = DocxParser()
        snapshot = parser.get_snapshot(str(path))
        assert isinstance(snapshot, bytes)
        assert len(snapshot) > 0

    def test_get_snapshot_roundtrip(self, temp_docx):
        path = temp_docx("test.docx", ["content here"])
        parser = DocxParser()
        snapshot = parser.get_snapshot(str(path))
        # Snapshot should be the raw file bytes
        with open(str(path), "rb") as f:
            original = f.read()
        assert snapshot == original


class TestWin32DocumentParser:
    def test_raises_not_implemented_on_non_windows(self):
        parser = Win32DocumentParser()
        with pytest.raises(NotImplementedError):
            parser.extract_text("/path/to/file.doc")

    def test_get_snapshot_raises_not_implemented(self):
        parser = Win32DocumentParser()
        with pytest.raises(NotImplementedError):
            parser.get_snapshot("/path/to/file.doc")


class TestGetParserForFile:
    def test_docx_returns_docx_parser(self):
        parser = get_parser_for_file("report.docx")
        assert isinstance(parser, DocxParser)

    def test_doc_returns_win32_parser(self):
        parser = get_parser_for_file("report.doc")
        assert isinstance(parser, Win32DocumentParser)

    def test_wps_returns_win32_parser(self):
        parser = get_parser_for_file("report.wps")
        assert isinstance(parser, Win32DocumentParser)

    def test_unsupported_raises(self):
        with pytest.raises(ValueError):
            get_parser_for_file("report.txt")


class TestBaseDocumentParser:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            BaseDocumentParser()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_document_parser.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

```python
"""Document parsers for different file formats."""
import os
from abc import ABC, abstractmethod


class BaseDocumentParser(ABC):
    """Abstract base class for document parsers."""

    @abstractmethod
    def extract_text(self, file_path: str) -> str:
        """Extract plain text content from a document."""
        pass

    @abstractmethod
    def get_snapshot(self, file_path: str) -> bytes:
        """Get a binary snapshot of the file for version storage."""
        pass


class DocxParser(BaseDocumentParser):
    """Parser for .docx files using python-docx."""

    def extract_text(self, file_path: str) -> str:
        from docx import Document
        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs]
        return "\n".join(paragraphs)

    def get_snapshot(self, file_path: str) -> bytes:
        with open(file_path, "rb") as f:
            return f.read()


class Win32DocumentParser(BaseDocumentParser):
    """Parser for .doc and .wps files using pywin32 COM interface.

    On non-Windows platforms, all methods raise NotImplementedError.
    """

    def extract_text(self, file_path: str) -> str:
        try:
            import win32com.client
        except ImportError:
            raise NotImplementedError(
                "doc/wps support requires Windows with Microsoft Word or WPS Office installed"
            )
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        try:
            doc = word.Documents.Open(file_path)
            text = doc.Content.Text
            doc.Close()
            return text
        finally:
            word.Quit()

    def get_snapshot(self, file_path: str) -> bytes:
        try:
            import win32com.client  # noqa: F401
        except ImportError:
            raise NotImplementedError(
                "doc/wps support requires Windows with Microsoft Word or WPS Office installed"
            )
        with open(file_path, "rb") as f:
            return f.read()


def get_parser_for_file(file_path: str) -> BaseDocumentParser:
    """Factory: return the appropriate parser based on file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".docx":
        return DocxParser()
    elif ext in (".doc", ".wps"):
        return Win32DocumentParser()
    else:
        raise ValueError(f"Unsupported file extension: {ext}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_document_parser.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add dochistory/core/document_parser.py tests/test_document_parser.py
git commit -m "feat: add document parsers (DocxParser + Win32 stub)"
```

---

## Task 5: Diff Utilities (utils/diff_utils.py)

**Files:**
- Create: `dochistory/utils/diff_utils.py`
- Test: `tests/test_diff_utils.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for diff utilities."""
from dochistory.utils.diff_utils import compute_diff, DiffLine, DiffType


class TestComputeDiff:
    def test_identical_text_no_changes(self):
        text = "line1\nline2\nline3"
        result = compute_diff(text, text)
        assert all(line.type == DiffType.UNCHANGED for line in result)
        assert len(result) == 3

    def test_added_line(self):
        old = "line1\nline2"
        new = "line1\nline2\nline3"
        result = compute_diff(old, new)
        added = [l for l in result if l.type == DiffType.ADDED]
        assert len(added) == 1
        assert added[0].new_line == "line3"

    def test_removed_line(self):
        old = "line1\nline2\nline3"
        new = "line1\nline3"
        result = compute_diff(old, new)
        removed = [l for l in result if l.type == DiffType.REMOVED]
        assert len(removed) == 1
        assert removed[0].old_line == "line2"

    def test_modified_line(self):
        old = "line1\nold line\nline3"
        new = "line1\nnew line\nline3"
        result = compute_diff(old, new)
        modified = [l for l in result if l.type == DiffType.MODIFIED]
        assert len(modified) == 1
        assert modified[0].old_line == "old line"
        assert modified[0].new_line == "new line"

    def test_empty_old_text(self):
        result = compute_diff("", "new content")
        added = [l for l in result if l.type == DiffType.ADDED]
        assert len(added) == 1

    def test_empty_new_text(self):
        result = compute_diff("old content", "")
        removed = [l for l in result if l.type == DiffType.REMOVED]
        assert len(removed) == 1

    def test_both_empty(self):
        result = compute_diff("", "")
        assert result == []

    def test_multiple_changes(self):
        old = "keep1\nremove1\nkeep2\nremove2"
        new = "keep1\nadd1\nkeep2\nadd2"
        result = compute_diff(old, new)
        types = [l.type for l in result]
        assert DiffType.ADDED in types
        assert DiffType.REMOVED in types
        assert DiffType.UNCHANGED in types
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_diff_utils.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

```python
"""Diff utilities using difflib."""
import difflib
from dataclasses import dataclass
from enum import Enum


class DiffType(Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class DiffLine:
    type: DiffType
    old_line: str
    new_line: str
    old_line_no: int
    new_line_no: int


def compute_diff(text_old: str, text_new: str) -> list[DiffLine]:
    """Compute line-level diff between two texts.

    Returns a list of DiffLine objects representing the changes.
    Uses difflib's SequenceMatcher for intelligent matching.
    """
    if not text_old and not text_new:
        return []

    old_lines = text_old.splitlines() if text_old else []
    new_lines = text_new.splitlines() if text_new else []

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    result = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                result.append(DiffLine(
                    type=DiffType.UNCHANGED,
                    old_line=old_lines[i1 + k],
                    new_line=new_lines[j1 + k],
                    old_line_no=i1 + k + 1,
                    new_line_no=j1 + k + 1,
                ))
        elif tag == "replace":
            # Pair up replaced lines; excess goes to added/removed
            old_slice = old_lines[i1:i2]
            new_slice = new_lines[j1:j2]
            max_len = max(len(old_slice), len(new_slice))
            for k in range(max_len):
                old_l = old_slice[k] if k < len(old_slice) else ""
                new_l = new_slice[k] if k < len(new_slice) else ""
                if old_l and new_l:
                    result.append(DiffLine(
                        type=DiffType.MODIFIED,
                        old_line=old_l,
                        new_line=new_l,
                        old_line_no=i1 + k + 1,
                        new_line_no=j1 + k + 1,
                    ))
                elif new_l:
                    result.append(DiffLine(
                        type=DiffType.ADDED,
                        old_line="",
                        new_line=new_l,
                        old_line_no=0,
                        new_line_no=j1 + k + 1,
                    ))
                elif old_l:
                    result.append(DiffLine(
                        type=DiffType.REMOVED,
                        old_line=old_l,
                        new_line="",
                        old_line_no=i1 + k + 1,
                        new_line_no=0,
                    ))
        elif tag == "delete":
            for k in range(i2 - i1):
                result.append(DiffLine(
                    type=DiffType.REMOVED,
                    old_line=old_lines[i1 + k],
                    new_line="",
                    old_line_no=i1 + k + 1,
                    new_line_no=0,
                ))
        elif tag == "insert":
            for k in range(j2 - j1):
                result.append(DiffLine(
                    type=DiffType.ADDED,
                    old_line="",
                    new_line=new_lines[j1 + k],
                    old_line_no=0,
                    new_line_no=j1 + k + 1,
                ))

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_diff_utils.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add dochistory/utils/diff_utils.py tests/test_diff_utils.py
git commit -m "feat: add diff utilities with difflib-based line comparison"
```

---

## Task 6: Version Manager (core/version_manager.py)

**Files:**
- Create: `dochistory/core/version_manager.py`
- Test: `tests/test_version_manager.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for the VersionManager."""
import os
from pathlib import Path

import pytest
from docx import Document

from dochistory.core.database import Database
from dochistory.core.version_manager import VersionManager


@pytest.fixture
def vm(tmp_path):
    """Create a VersionManager with a temp database."""
    db_path = tmp_path / "test.db"
    db = Database(str(db_path))
    manager = VersionManager(db)
    yield manager, db
    db.close()


@pytest.fixture
def monitored_file(vm, tmp_path):
    """Create a monitored folder with a docx file."""
    manager, db = vm
    monitor_dir = tmp_path / "monitored"
    monitor_dir.mkdir()
    folder_id = db.add_folder(str(monitor_dir))

    docx_path = monitor_dir / "report.docx"
    doc = Document()
    doc.add_paragraph("Initial content")
    doc.save(str(docx_path))

    return monitor_dir, folder_id, docx_path


class TestCreateVersion:
    def test_create_first_version(self, vm, monitored_file):
        manager, db = vm
        monitor_dir, folder_id, docx_path = monitored_file
        version = manager.create_version(str(docx_path), folder_id)
        assert version is not None
        assert version["version_number"] == 1

    def test_create_second_version(self, vm, monitored_file):
        manager, db = vm
        monitor_dir, folder_id, docx_path = monitored_file
        manager.create_version(str(docx_path), folder_id)
        # Modify file
        doc = Document(str(docx_path))
        doc.add_paragraph("New content")
        doc.save(str(docx_path))
        version = manager.create_version(str(docx_path), folder_id)
        assert version["version_number"] == 2

    def test_skip_unchanged_file(self, vm, monitored_file):
        manager, db = vm
        monitor_dir, folder_id, docx_path = monitored_file
        v1 = manager.create_version(str(docx_path), folder_id)
        v2 = manager.create_version(str(docx_path), folder_id)
        assert v2 is None  # No new version for unchanged file

    def test_manual_version_with_note(self, vm, monitored_file):
        manager, db = vm
        monitor_dir, folder_id, docx_path = monitored_file
        version = manager.create_version(
            str(docx_path), folder_id, note="Manual checkpoint", is_auto=False
        )
        assert version["note"] == "Manual checkpoint"
        assert version["is_auto"] == 0


class TestGetVersions:
    def test_get_versions_ordered_newest_first(self, vm, monitored_file):
        manager, db = vm
        monitor_dir, folder_id, docx_path = monitored_file
        manager.create_version(str(docx_path), folder_id)
        doc = Document(str(docx_path))
        doc.add_paragraph("v2")
        doc.save(str(docx_path))
        manager.create_version(str(docx_path), folder_id)

        file_rec = db.find_file(folder_id, "report.docx")
        versions = manager.get_versions(file_rec["id"])
        assert len(versions) == 2
        assert versions[0]["version_number"] == 2


class TestRollback:
    def test_rollback_restores_content(self, vm, monitored_file):
        manager, db = vm
        monitor_dir, folder_id, docx_path = monitored_file
        v1 = manager.create_version(str(docx_path), folder_id)

        # Modify and create v2
        doc = Document(str(docx_path))
        doc.add_paragraph("Modified content")
        doc.save(str(docx_path))
        manager.create_version(str(docx_path), folder_id)

        # Rollback to v1
        file_rec = db.find_file(folder_id, "report.docx")
        manager.rollback_to_version(file_rec["id"], v1["id"])

        # Verify content restored
        restored_doc = Document(str(docx_path))
        texts = [p.text for p in restored_doc.paragraphs]
        assert "Initial content" in texts
        assert "Modified content" not in texts

    def test_rollback_creates_backup(self, vm, monitored_file):
        manager, db = vm
        monitor_dir, folder_id, docx_path = monitored_file
        v1 = manager.create_version(str(docx_path), folder_id)

        doc = Document(str(docx_path))
        doc.add_paragraph("Modified")
        doc.save(str(docx_path))
        manager.create_version(str(docx_path), folder_id)

        file_rec = db.find_file(folder_id, "report.docx")
        versions_before = len(manager.get_versions(file_rec["id"]))
        manager.rollback_to_version(file_rec["id"], v1["id"])
        versions_after = len(manager.get_versions(file_rec["id"]))
        # Should have backup + original 2 versions
        assert versions_after == versions_before + 1


class TestExportVersion:
    def test_export_creates_file(self, vm, monitored_file, tmp_path):
        manager, db = vm
        monitor_dir, folder_id, docx_path = monitored_file
        v1 = manager.create_version(str(docx_path), folder_id)

        export_path = tmp_path / "exported.docx"
        file_rec = db.find_file(folder_id, "report.docx")
        manager.export_version(file_rec["id"], v1["id"], str(export_path))
        assert export_path.exists()

        # Verify exported content
        doc = Document(str(export_path))
        texts = [p.text for p in doc.paragraphs]
        assert "Initial content" in texts


class TestCleanup:
    def test_cleanup_removes_old_versions(self, vm, monitored_file):
        manager, db = vm
        monitor_dir, folder_id, docx_path = monitored_file
        for i in range(5):
            doc = Document(str(docx_path))
            doc.add_paragraph(f"version {i}")
            doc.save(str(docx_path))
            manager.create_version(str(docx_path), folder_id)

        file_rec = db.find_file(folder_id, "report.docx")
        manager.cleanup_old_versions(file_rec["id"], max_versions=3)
        versions = manager.get_versions(file_rec["id"])
        assert len(versions) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_version_manager.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

```python
"""Version management business logic."""
import getpass
import os
import tempfile
import time
from typing import Optional

from dochistory.core.database import Database
from dochistory.core.document_parser import get_parser_for_file
from dochistory.utils.file_utils import (
    compute_md5,
    compress_data,
    decompress_data,
    is_supported_file,
    is_temp_file,
)


class VersionManager:
    """Manages document version creation, query, rollback, and cleanup."""

    def __init__(self, db: Database):
        self._db = db

    def create_version(
        self,
        file_path: str,
        folder_id: int,
        note: Optional[str] = None,
        is_auto: bool = True,
    ) -> Optional[dict]:
        """Create a new version of a file. Returns None if unchanged."""
        if not os.path.exists(file_path):
            return None
        if is_temp_file(file_path) or not is_supported_file(file_path):
            return None

        relative_path = os.path.basename(file_path)
        file_hash = compute_md5(file_path)

        # Find or create file record
        file_rec = self._db.find_file(folder_id, relative_path)
        if file_rec is None:
            file_id = self._db.add_file(folder_id, relative_path, file_hash)
            file_rec = self._db.find_file(folder_id, relative_path)
        else:
            # Skip if hash unchanged
            if file_rec["file_hash"] == file_hash:
                return None
            self._db.update_file_hash(file_rec["id"], file_hash, os.path.getsize(file_path))

        file_id = file_rec["id"]

        # Retry reading file (may be locked by Word)
        snapshot = self._read_with_retry(file_path)
        if snapshot is None:
            return None

        compressed = compress_data(snapshot)
        version_number = self._db.get_latest_version_number(file_id) + 1
        modified_by = getpass.getuser()

        version_id = self._db.create_version(
            file_id=file_id,
            version_number=version_number,
            file_size=os.path.getsize(file_path),
            data=compressed,
            note=note,
            is_auto=is_auto,
            modified_by=modified_by,
        )

        # Auto-cleanup
        max_versions = int(self._db.get_config("max_versions_per_file", "50"))
        self._db.cleanup_old_versions(file_id, max_versions)

        versions = self._db.get_versions(file_id)
        for v in versions:
            if v["id"] == version_id:
                return v
        return None

    def _read_with_retry(self, file_path: str, max_retries: int = 3, delay: float = 0.2) -> Optional[bytes]:
        """Read file bytes with retry for locked files."""
        parser = get_parser_for_file(file_path)
        for attempt in range(max_retries):
            try:
                return parser.get_snapshot(file_path)
            except (PermissionError, OSError):
                if attempt < max_retries - 1:
                    time.sleep(delay)
        return None

    def get_versions(self, file_id: int) -> list[dict]:
        """Get all versions of a file, newest first."""
        return self._db.get_versions(file_id)

    def rollback_to_version(self, file_id: int, version_id: int) -> bool:
        """Rollback a file to a specific version. Creates backup first."""
        # Get file record
        versions = self._db.get_versions(file_id)
        latest = versions[0] if versions else None
        target = None
        for v in versions:
            if v["id"] == version_id:
                target = v
                break
        if target is None:
            return False

        # Get file path
        file_rec = self._get_file_record(file_id)
        if file_rec is None:
            return False
        file_path = self._get_full_path(file_rec)

        # Create backup if current file differs from latest version
        if latest and os.path.exists(file_path):
            current_hash = compute_md5(file_path)
            if current_hash != file_rec["file_hash"]:
                self._create_backup_version(file_id, file_path)

        # Restore target version
        compressed_data = self._db.get_version_data(version_id)
        if compressed_data is None:
            return False

        data = decompress_data(compressed_data)
        self._atomic_write(file_path, data)

        # Update file hash
        new_hash = compute_md5(file_path)
        self._db.update_file_hash(file_id, new_hash, len(data))

        return True

    def export_version(self, file_id: int, version_id: int, dest_path: str) -> bool:
        """Export a specific version to a new file."""
        compressed_data = self._db.get_version_data(version_id)
        if compressed_data is None:
            return False
        data = decompress_data(compressed_data)
        with open(dest_path, "wb") as f:
            f.write(data)
        return True

    def cleanup_old_versions(self, file_id: int, max_versions: int):
        """Delete old versions beyond max_versions count."""
        self._db.cleanup_old_versions(file_id, max_versions)

    def _create_backup_version(self, file_id: int, file_path: str):
        """Create a backup version before rollback."""
        snapshot = self._read_with_retry(file_path)
        if snapshot is None:
            return
        compressed = compress_data(snapshot)
        version_number = self._db.get_latest_version_number(file_id) + 1
        self._db.create_version(
            file_id=file_id,
            version_number=version_number,
            file_size=os.path.getsize(file_path),
            data=compressed,
            note="回退前自动备份",
            is_auto=True,
            modified_by=getpass.getuser(),
        )

    def _atomic_write(self, file_path: str, data: bytes):
        """Atomically write data to a file via temp file + rename."""
        dir_path = os.path.dirname(file_path)
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, prefix=".dochistory_tmp_")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp_path, file_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def _get_file_record(self, file_id: int) -> Optional[dict]:
        """Get file record by ID."""
        folders = self._db.get_folders(include_inactive=True)
        for folder in folders:
            files = self._db.get_files(folder["id"])
            for f in files:
                if f["id"] == file_id:
                    return {**f, "_folder_path": folder["path"]}
        return None

    def _get_full_path(self, file_rec: dict) -> str:
        """Get full filesystem path from file record."""
        return os.path.join(file_rec["_folder_path"], file_rec["relative_path"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_version_manager.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add dochistory/core/version_manager.py tests/test_version_manager.py
git commit -m "feat: add version manager with create/rollback/export/cleanup"
```

---

## Task 7: File Monitor (core/file_monitor.py)

**Files:**
- Create: `dochistory/core/file_monitor.py`
- Test: `tests/test_file_monitor.py`

- [ ] **Step 1: Write failing tests**

```python
"""Integration tests for FileMonitor."""
import time
from pathlib import Path

import pytest
from docx import Document

from dochistory.core.file_monitor import FileMonitor


@pytest.fixture
def monitor():
    """Create a FileMonitor instance."""
    m = FileMonitor()
    yield m
    m.stop_all()


class TestFileMonitor:
    def test_detect_modified_docx(self, monitor, temp_monitor_dir):
        events = []
        monitor.file_saved.connect(lambda p: events.append(p))

        monitor.add_watch(str(temp_monitor_dir))
        docx_path = temp_monitor_dir / "test.docx"
        Document().save(str(docx_path))

        # Wait for debounce + processing
        time.sleep(1.5)
        assert any("test.docx" in e for e in events)

    def test_ignore_temp_files(self, monitor, temp_monitor_dir):
        events = []
        monitor.file_saved.connect(lambda p: events.append(p))

        monitor.add_watch(str(temp_monitor_dir))
        # Create a temp file
        (temp_monitor_dir / "~$test.docx").write_text("temp")

        time.sleep(1.5)
        assert len(events) == 0

    def test_ignore_unsupported_files(self, monitor, temp_monitor_dir):
        events = []
        monitor.file_saved.connect(lambda p: events.append(p))

        monitor.add_watch(str(temp_monitor_dir))
        (temp_monitor_dir / "notes.txt").write_text("text")

        time.sleep(1.5)
        assert len(events) == 0

    def test_debounce_multiple_saves(self, monitor, temp_monitor_dir):
        events = []
        monitor.file_saved.connect(lambda p: events.append(p))

        monitor.add_watch(str(temp_monitor_dir))
        docx_path = temp_monitor_dir / "test.docx"
        doc = Document()
        doc.save(str(docx_path))

        # Rapidly modify
        for i in range(3):
            doc = Document()
            doc.add_paragraph(f"line {i}")
            doc.save(str(docx_path))
            time.sleep(0.1)

        time.sleep(1.5)
        # Should only have 1-2 events due to debounce (initial + final)
        assert len(events) <= 2

    def test_detect_rename(self, monitor, temp_monitor_dir):
        moved_events = []
        monitor.file_moved.connect(lambda s, d: moved_events.append((s, d)))

        monitor.add_watch(str(temp_monitor_dir))
        docx_path = temp_monitor_dir / "old.docx"
        Document().save(str(docx_path))
        time.sleep(0.5)

        new_path = temp_monitor_dir / "new.docx"
        docx_path.rename(new_path)

        time.sleep(1.5)
        assert len(moved_events) == 1
        assert "old.docx" in moved_events[0][0]
        assert "new.docx" in moved_events[0][1]

    def test_detect_new_file(self, monitor, temp_monitor_dir):
        created_events = []
        monitor.file_created.connect(lambda p: created_events.append(p))

        monitor.add_watch(str(temp_monitor_dir))
        docx_path = temp_monitor_dir / "new.docx"
        Document().save(str(docx_path))

        time.sleep(1.5)
        assert any("new.docx" in e for e in created_events)

    def test_pause_resume(self, monitor, temp_monitor_dir):
        events = []
        monitor.file_saved.connect(lambda p: events.append(p))

        monitor.add_watch(str(temp_monitor_dir))
        monitor.pause()

        docx_path = temp_monitor_dir / "test.docx"
        Document().save(str(docx_path))

        time.sleep(1.5)
        assert len(events) == 0

        monitor.resume()
        doc = Document(str(docx_path))
        doc.add_paragraph("new")
        doc.save(str(docx_path))

        time.sleep(1.5)
        assert len(events) > 0

    def test_remove_watch(self, monitor, temp_monitor_dir):
        events = []
        monitor.file_saved.connect(lambda p: events.append(p))

        monitor.add_watch(str(temp_monitor_dir))
        monitor.remove_watch(str(temp_monitor_dir))

        docx_path = temp_monitor_dir / "test.docx"
        Document().save(str(docx_path))

        time.sleep(1.5)
        assert len(events) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_file_monitor.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

```python
"""File system monitor using watchdog with debounce."""
import os
import threading

from PyQt6.QtCore import QObject, pyqtSignal
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from dochistory.utils.file_utils import is_supported_file, is_temp_file


class _DebouncedHandler(FileSystemEventHandler):
    """Watchdog handler with debounce for on_modified."""

    def __init__(self, monitor: "FileMonitor"):
        self._monitor = monitor
        self._timers: dict[str, threading.Timer] = {}

    def on_modified(self, event):
        if event.is_directory:
            return
        file_path = event.src_path
        if is_temp_file(file_path) or not is_supported_file(file_path):
            return
        self._debounce(file_path)

    def on_created(self, event):
        if event.is_directory:
            return
        file_path = event.src_path
        if is_temp_file(file_path) or not is_supported_file(file_path):
            return
        self._monitor.file_created.emit(file_path)
        # Also trigger save for new files
        self._debounce(file_path)

    def on_moved(self, event):
        src_path = event.src_path
        dest_path = event.dest_path
        if is_temp_file(dest_path):
            return
        if not is_supported_file(dest_path):
            return
        self._monitor.file_moved.emit(src_path, dest_path)

    def on_deleted(self, event):
        if event.is_directory:
            return
        file_path = event.src_path
        if is_temp_file(file_path) or not is_supported_file(file_path):
            return
        self._monitor.file_deleted.emit(file_path)

    def _debounce(self, file_path: str):
        """Debounce: 500ms window, only last modification triggers."""
        if file_path in self._timers:
            self._timers[file_path].cancel()
        timer = threading.Timer(0.5, self._emit_save, args=[file_path])
        self._timers[file_path] = timer
        timer.start()

    def _emit_save(self, file_path: str):
        self._timers.pop(file_path, None)
        self._monitor.file_saved.emit(file_path)

    def cancel_all(self):
        for timer in self._timers.values():
            timer.cancel()
        self._timers.clear()


class FileMonitor(QObject):
    """Monitors folders for document changes with debounce."""

    file_saved = pyqtSignal(str)
    file_moved = pyqtSignal(str, str)
    file_created = pyqtSignal(str)
    file_deleted = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._observers: dict[str, Observer] = {}
        self._handlers: dict[str, _DebouncedHandler] = {}
        self._paused = False
        self._lock = threading.Lock()

    def add_watch(self, path: str):
        """Start monitoring a folder."""
        with self._lock:
            if path in self._observers:
                return
            handler = _DebouncedHandler(self)
            observer = Observer()
            observer.schedule(handler, path, recursive=True)
            observer.start()
            self._observers[path] = observer
            self._handlers[path] = handler

    def remove_watch(self, path: str):
        """Stop monitoring a folder."""
        with self._lock:
            if path not in self._observers:
                return
            self._handlers[path].cancel_all()
            self._observers[path].stop()
            del self._observers[path]
            del self._handlers[path]

    def pause(self):
        """Pause all monitoring (events ignored)."""
        self._paused = True

    def resume(self):
        """Resume monitoring."""
        self._paused = False

    def is_paused(self) -> bool:
        return self._paused

    def stop_all(self):
        """Stop all observers and clean up."""
        with self._lock:
            for handler in self._handlers.values():
                handler.cancel_all()
            for observer in self._observers.values():
                observer.stop()
                observer.join(timeout=5)
            self._observers.clear()
            self._handlers.clear()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_file_monitor.py -v`
Expected: All tests PASS (may be flaky on timing; if so, increase sleep values)

- [ ] **Step 5: Commit**

```bash
git add dochistory/core/file_monitor.py tests/test_file_monitor.py
git commit -m "feat: add file monitor with watchdog, debounce, rename/move detection"
```

---

## Task 8: Rename/Move Tracking Integration

**Files:**
- Modify: `dochistory/core/version_manager.py` (add `handle_rename`, `handle_move`, `handle_save_as`, `associate_history`)
- Test: `tests/test_rename_move.py`

- [ ] **Step 1: Write failing tests**

```python
"""Integration tests for rename and move tracking."""
import time
from pathlib import Path

import pytest
from docx import Document

from dochistory.core.database import Database
from dochistory.core.version_manager import VersionManager


@pytest.fixture
def setup(tmp_path):
    """Create DB, monitor dir, and a docx file with one version."""
    db = Database(str(tmp_path / "test.db"))
    manager = VersionManager(db)
    monitor_dir = tmp_path / "monitored"
    monitor_dir.mkdir()
    folder_id = db.add_folder(str(monitor_dir))

    docx_path = monitor_dir / "report.docx"
    doc = Document()
    doc.add_paragraph("Initial content")
    doc.save(str(docx_path))
    manager.create_version(str(docx_path), folder_id)

    return manager, db, monitor_dir, folder_id, docx_path


class TestRenameTracking:
    def test_rename_updates_path(self, setup):
        manager, db, monitor_dir, folder_id, docx_path = setup
        new_path = monitor_dir / "renamed.docx"
        docx_path.rename(new_path)

        manager.handle_rename(str(docx_path), str(new_path), folder_id)

        assert db.find_file(folder_id, "renamed.docx") is not None
        assert db.find_file(folder_id, "report.docx") is None

    def test_rename_preserves_versions(self, setup):
        manager, db, monitor_dir, folder_id, docx_path = setup
        file_rec = db.find_file(folder_id, "report.docx")
        versions_before = len(db.get_versions(file_rec["id"]))

        new_path = monitor_dir / "renamed.docx"
        docx_path.rename(new_path)
        manager.handle_rename(str(docx_path), str(new_path), folder_id)

        file_rec = db.find_file(folder_id, "renamed.docx")
        versions_after = len(db.get_versions(file_rec["id"]))
        assert versions_after == versions_before

    def test_rename_records_special_version(self, setup):
        manager, db, monitor_dir, folder_id, docx_path = setup
        new_path = monitor_dir / "renamed.docx"
        docx_path.rename(new_path)
        manager.handle_rename(str(docx_path), str(new_path), folder_id)

        file_rec = db.find_file(folder_id, "renamed.docx")
        versions = db.get_versions(file_rec["id"])
        rename_versions = [v for v in versions if v["note"] and "重命名" in v["note"]]
        assert len(rename_versions) >= 1


class TestMoveTracking:
    def test_move_between_folders(self, setup, tmp_path):
        manager, db, monitor_dir, folder_id, docx_path = setup
        dir2 = tmp_path / "monitored2"
        dir2.mkdir()
        folder2_id = db.add_folder(str(dir2))

        new_path = dir2 / "report.docx"
        docx_path.rename(new_path)
        manager.handle_move(str(docx_path), str(new_path), folder_id, folder2_id)

        assert db.find_file(folder_id, "report.docx") is None
        assert db.find_file(folder2_id, "report.docx") is not None

    def test_move_preserves_versions(self, setup, tmp_path):
        manager, db, monitor_dir, folder_id, docx_path = setup
        dir2 = tmp_path / "monitored2"
        dir2.mkdir()
        folder2_id = db.add_folder(str(dir2))

        file_rec = db.find_file(folder_id, "report.docx")
        versions_before = len(db.get_versions(file_rec["id"]))

        new_path = dir2 / "report.docx"
        docx_path.rename(new_path)
        manager.handle_move(str(docx_path), str(new_path), folder_id, folder2_id)

        file_rec = db.find_file(folder2_id, "report.docx")
        versions_after = len(db.get_versions(file_rec["id"]))
        assert versions_after == versions_before


class TestMoveOutOfMonitor:
    def test_move_out_deactivates_file(self, setup, tmp_path):
        manager, db, monitor_dir, folder_id, docx_path = setup
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()

        new_path = outside_dir / "report.docx"
        docx_path.rename(new_path)
        manager.handle_move_out(str(docx_path), folder_id)

        file_rec = db.find_file(folder_id, "report.docx")
        assert file_rec["is_active"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_rename_move.py -v`
Expected: FAIL with `AttributeError: 'VersionManager' object has no attribute 'handle_rename'`

- [ ] **Step 3: Add rename/move methods to VersionManager**

Add these methods to the `VersionManager` class in `dochistory/core/version_manager.py`:

```python
    def handle_rename(self, old_path: str, new_path: str, folder_id: int):
        """Handle file rename within the same monitored folder."""
        old_name = os.path.basename(old_path)
        new_name = os.path.basename(new_path)
        file_rec = self._db.find_file(folder_id, old_name)
        if file_rec is None:
            return
        self._db.rename_file(file_rec["id"], new_name)
        # Record a special version noting the rename
        self._record_rename_version(file_rec["id"], old_name, new_name)

    def handle_move(self, old_path: str, new_path: str, old_folder_id: int, new_folder_id: int):
        """Handle file move between monitored folders."""
        relative_name = os.path.basename(new_path)
        file_rec = self._db.find_file(old_folder_id, relative_name)
        if file_rec is None:
            # Try old name
            old_name = os.path.basename(old_path)
            file_rec = self._db.find_file(old_folder_id, old_name)
        if file_rec is None:
            return
        self._db.move_file(file_rec["id"], new_folder_id, relative_name)
        self._record_rename_version(file_rec["id"], os.path.basename(old_path), relative_name)

    def handle_move_out(self, old_path: str, folder_id: int):
        """Handle file moved out of monitored folders."""
        old_name = os.path.basename(old_path)
        file_rec = self._db.find_file(folder_id, old_name)
        if file_rec is None:
            return
        self._db.deactivate_file(file_rec["id"])

    def handle_save_as(self, new_file_path: str, folder_id: int) -> Optional[dict]:
        """Handle a new file created via 'Save As'. Creates first version.
        Returns the version record, or None if creation failed."""
        return self.create_version(new_file_path, folder_id, note="另存为新文件", is_auto=True)

    def find_save_as_source(self, new_file_path: str) -> Optional[dict]:
        """Check if a new file's hash matches any existing file version.
        Returns the source file record if a match is found."""
        if not os.path.exists(new_file_path):
            return None
        new_hash = compute_md5(new_file_path)
        return self._db.find_file_by_hash(new_hash)

    def associate_history(self, new_file_id: int, source_file_id: int):
        """Copy all versions from source file to new file (for Save As inheritance)."""
        source_versions = self._db.get_versions(source_file_id)
        # Get current latest version number of new file
        current_max = self._db.get_latest_version_number(new_file_id)
        for i, sv in enumerate(reversed(source_versions)):
            data = self._db.get_version_data(sv["id"])
            if data is None:
                continue
            version_num = current_max + i + 1
            note = f"继承自源文件 (原版本 v{sv['version_number']})"
            if i == len(source_versions) - 1:
                note = "另存为: 继承源文件历史"
            self._db.create_version(
                file_id=new_file_id,
                version_number=version_num,
                file_size=sv["file_size"],
                data=data,
                note=note,
                is_auto=True,
                modified_by=sv.get("modified_by"),
            )

    def _record_rename_version(self, file_id: int, old_name: str, new_name: str):
        """Record a special version entry for rename events."""
        version_number = self._db.get_latest_version_number(file_id) + 1
        # Use empty data placeholder (rename doesn't change content)
        # Store current snapshot if file exists
        file_rec = self._get_file_record(file_id)
        if file_rec and os.path.exists(self._get_full_path(file_rec)):
            snapshot = self._read_with_retry(self._get_full_path(file_rec))
            if snapshot:
                data = compress_data(snapshot)
            else:
                data = b""
        else:
            data = b""
        self._db.create_version(
            file_id=file_id,
            version_number=version_number,
            file_size=0,
            data=data,
            note=f"重命名: {old_name} → {new_name}",
            is_auto=True,
            modified_by=getpass.getuser(),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_rename_move.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add dochistory/core/version_manager.py tests/test_rename_move.py
git commit -m "feat: add rename/move/save-as tracking to version manager"
```

---

## Task 9: Save-As Tracking Integration

**Files:**
- Test: `tests/test_save_as.py`

- [ ] **Step 1: Write failing tests**

```python
"""Integration tests for Save As tracking."""
import os
from pathlib import Path

import pytest
from docx import Document

from dochistory.core.database import Database
from dochistory.core.version_manager import VersionManager


@pytest.fixture
def setup(tmp_path):
    """Create DB, monitor dir, source file with multiple versions."""
    db = Database(str(tmp_path / "test.db"))
    manager = VersionManager(db)
    monitor_dir = tmp_path / "monitored"
    monitor_dir.mkdir()
    folder_id = db.add_folder(str(monitor_dir))

    source_path = monitor_dir / "source.docx"
    doc = Document()
    doc.add_paragraph("Version 1 content")
    doc.save(str(source_path))
    manager.create_version(str(source_path), folder_id)

    doc = Document(str(source_path))
    doc.add_paragraph("Version 2 content")
    doc.save(str(source_path))
    manager.create_version(str(source_path), folder_id)

    return manager, db, monitor_dir, folder_id, source_path


class TestSaveAsDetection:
    def test_find_source_by_hash(self, setup):
        manager, db, monitor_dir, folder_id, source_path = setup
        # Copy source to new file (simulates Save As)
        new_path = monitor_dir / "copy.docx"
        os.copyfile(str(source_path), str(new_path))

        source = manager.find_save_as_source(str(new_path))
        assert source is not None
        assert source["relative_path"] == "source.docx"

    def test_no_source_for_unique_file(self, setup, tmp_path):
        manager, db, monitor_dir, folder_id, source_path = setup
        new_path = monitor_dir / "unique.docx"
        doc = Document()
        doc.add_paragraph("Completely unique content")
        doc.save(str(new_path))

        source = manager.find_save_as_source(str(new_path))
        assert source is None


class TestAssociateHistory:
    def test_associate_copies_versions(self, setup):
        manager, db, monitor_dir, folder_id, source_path = setup
        # Create new file (Save As)
        new_path = monitor_dir / "copy.docx"
        os.copyfile(str(source_path), str(new_path))
        manager.handle_save_as(str(new_path), folder_id)

        new_file = db.find_file(folder_id, "copy.docx")
        source_file = db.find_file(folder_id, "source.docx")
        source_versions = db.get_versions(source_file["id"])

        manager.associate_history(new_file["id"], source_file["id"])

        new_versions = db.get_versions(new_file["id"])
        # Should have: 1 original + 2 inherited = 3
        assert len(new_versions) >= 3

    def test_source_file_unchanged_after_associate(self, setup):
        manager, db, monitor_dir, folder_id, source_path = setup
        new_path = monitor_dir / "copy.docx"
        os.copyfile(str(source_path), str(new_path))
        manager.handle_save_as(str(new_path), folder_id)

        source_file = db.find_file(folder_id, "source.docx")
        source_versions_before = len(db.get_versions(source_file["id"]))

        new_file = db.find_file(folder_id, "copy.docx")
        manager.associate_history(new_file["id"], source_file["id"])

        source_versions_after = len(db.get_versions(source_file["id"]))
        assert source_versions_after == source_versions_before

    def test_independent_evolution_after_associate(self, setup):
        manager, db, monitor_dir, folder_id, source_path = setup
        new_path = monitor_dir / "copy.docx"
        os.copyfile(str(source_path), str(new_path))
        manager.handle_save_as(str(new_path), folder_id)

        new_file = db.find_file(folder_id, "copy.docx")
        source_file = db.find_file(folder_id, "source.docx")
        manager.associate_history(new_file["id"], source_file["id"])

        # Modify source file
        doc = Document(str(source_path))
        doc.add_paragraph("Source only change")
        doc.save(str(source_path))
        manager.create_version(str(source_path), folder_id)

        # Modify new file
        doc = Document(str(new_path))
        doc.add_paragraph("Copy only change")
        doc.save(str(new_path))
        manager.create_version(str(new_path), folder_id)

        source_versions = db.get_versions(source_file["id"])
        new_versions = db.get_versions(new_file["id"])
        # Source should have 3 (2 original + 1 new), new should have 4 (1 + 2 inherited + 1 new)
        assert len(source_versions) == 3
        assert len(new_versions) >= 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_save_as.py -v`
Expected: Some tests may pass (methods added in Task 8), verify all pass

- [ ] **Step 3: Run tests to verify they pass**

Run: `python -m pytest tests/test_save_as.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_save_as.py
git commit -m "test: add save-as tracking integration tests"
```

---

## Task 10: Rollback Flow Integration Test

**Files:**
- Test: `tests/test_rollback_flow.py`

- [ ] **Step 1: Write failing tests**

```python
"""Integration tests for the complete rollback flow."""
import os
from pathlib import Path

import pytest
from docx import Document

from dochistory.core.database import Database
from dochistory.core.version_manager import VersionManager


@pytest.fixture
def setup(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    manager = VersionManager(db)
    monitor_dir = tmp_path / "monitored"
    monitor_dir.mkdir()
    folder_id = db.add_folder(str(monitor_dir))

    docx_path = monitor_dir / "report.docx"
    doc = Document()
    doc.add_paragraph("Version 1")
    doc.save(str(docx_path))
    v1 = manager.create_version(str(docx_path), folder_id)

    doc = Document(str(docx_path))
    doc.add_paragraph("Version 2")
    doc.save(str(docx_path))
    v2 = manager.create_version(str(docx_path), folder_id)

    doc = Document(str(docx_path))
    doc.add_paragraph("Version 3")
    doc.save(str(docx_path))
    v3 = manager.create_version(str(docx_path), folder_id)

    return manager, db, monitor_dir, folder_id, docx_path, [v1, v2, v3]


class TestRollbackFlow:
    def test_rollback_to_v1(self, setup):
        manager, db, monitor_dir, folder_id, docx_path, versions = setup
        v1, v2, v3 = versions
        file_rec = db.find_file(folder_id, "report.docx")

        manager.rollback_to_version(file_rec["id"], v1["id"])

        doc = Document(str(docx_path))
        texts = [p.text for p in doc.paragraphs]
        assert "Version 1" in texts
        assert "Version 2" not in texts
        assert "Version 3" not in texts

    def test_rollback_creates_backup(self, setup):
        manager, db, monitor_dir, folder_id, docx_path, versions = setup
        v1, v2, v3 = versions
        file_rec = db.find_file(folder_id, "report.docx")
        versions_before = len(db.get_versions(file_rec["id"]))

        manager.rollback_to_version(file_rec["id"], v1["id"])

        versions_after = len(db.get_versions(file_rec["id"]))
        assert versions_after == versions_before + 1

    def test_rollback_then_continue_editing(self, setup):
        manager, db, monitor_dir, folder_id, docx_path, versions = setup
        v1, v2, v3 = versions
        file_rec = db.find_file(folder_id, "report.docx")

        manager.rollback_to_version(file_rec["id"], v1["id"])

        # Continue editing after rollback
        doc = Document(str(docx_path))
        doc.add_paragraph("After rollback")
        doc.save(str(docx_path))
        v_new = manager.create_version(str(docx_path), folder_id)

        assert v_new is not None
        assert v_new["version_number"] > v3["version_number"]

    def test_export_version(self, setup, tmp_path):
        manager, db, monitor_dir, folder_id, docx_path, versions = setup
        v1, v2, v3 = versions
        file_rec = db.find_file(folder_id, "report.docx")

        export_path = tmp_path / "exported.docx"
        manager.export_version(file_rec["id"], v1["id"], str(export_path))

        assert export_path.exists()
        doc = Document(str(export_path))
        texts = [p.text for p in doc.paragraphs]
        assert "Version 1" in texts
        assert "Version 2" not in texts
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/test_rollback_flow.py -v`
Expected: All tests PASS (uses existing VersionManager implementation)

- [ ] **Step 3: Commit**

```bash
git add tests/test_rollback_flow.py
git commit -m "test: add complete rollback flow integration tests"
```

---

## Task 11: System Tray (ui/tray.py)

**Files:**
- Create: `dochistory/ui/tray.py`

- [ ] **Step 1: Write the tray module**

```python
"""System tray icon and context menu."""
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QPixmap
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu


class SystemTray(QObject):
    """System tray with monitor control and window management."""

    show_window_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    pause_monitoring_requested = pyqtSignal()
    resume_monitoring_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tray = QSystemTrayIcon(parent)
        self._setup_icon()
        self._setup_menu()
        self._monitoring_paused = False

    def _setup_icon(self):
        """Create a simple placeholder icon."""
        pixmap = QPixmap(16, 16)
        pixmap.fill()
        self._tray.setIcon(QIcon(pixmap))
        self._tray.setToolTip("DocHistory - 文档版本控制")

    def _setup_menu(self):
        menu = QMenu()

        self._show_action = QAction("显示主窗口", menu)
        self._show_action.triggered.connect(self.show_window_requested.emit)
        menu.addAction(self._show_action)

        menu.addSeparator()

        self._pause_action = QAction("暂停监控", menu)
        self._pause_action.triggered.connect(self._toggle_pause)
        menu.addAction(self._pause_action)

        menu.addSeparator()

        self._quit_action = QAction("退出", menu)
        self._quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(self._quit_action)

        self._tray.setContextMenu(menu)

    def _toggle_pause(self):
        if self._monitoring_paused:
            self._monitoring_paused = False
            self._pause_action.setText("暂停监控")
            self.resume_monitoring_requested.emit()
        else:
            self._monitoring_paused = True
            self._pause_action.setText("恢复监控")
            self.pause_monitoring_requested.emit()

    def show(self):
        self._tray.show()

    def hide(self):
        self._tray.hide()

    def show_message(self, title: str, message: str):
        """Show a tray notification."""
        self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 3000)
```

- [ ] **Step 2: Verify it imports correctly**

Run: `python -c "from dochistory.ui.tray import SystemTray; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add dochistory/ui/tray.py
git commit -m "feat: add system tray with pause/resume/quit menu"
```

---

## Task 12: Diff Window (ui/diff_window.py)

**Files:**
- Create: `dochistory/ui/diff_window.py`

- [ ] **Step 1: Write the diff window module**

```python
"""Side-by-side diff comparison window."""
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QTextBrowser, QLabel, QVBoxLayout, QPushButton,
)
from PyQt6.QtCore import Qt

from dochistory.utils.diff_utils import compute_diff, DiffType


class DiffWindow(QWidget):
    """Window showing side-by-side text diff between two versions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("版本差异比较")
        self.resize(1000, 600)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        self._header = QLabel("版本差异比较")
        self._header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._header)

        # Side-by-side text browsers
        content_layout = QHBoxLayout()

        left_container = QVBoxLayout()
        self._left_label = QLabel("旧版本")
        self._left_browser = QTextBrowser()
        self._left_browser.setReadOnly(True)
        left_container.addWidget(self._left_label)
        left_container.addWidget(self._left_browser)
        content_layout.addLayout(left_container)

        right_container = QVBoxLayout()
        self._right_label = QLabel("新版本")
        self._right_browser = QTextBrowser()
        self._right_browser.setReadOnly(True)
        right_container.addWidget(self._right_label)
        right_container.addWidget(self._right_browser)
        content_layout.addLayout(right_container)

        layout.addLayout(content_layout, stretch=1)

        # Close button
        self._close_btn = QPushButton("关闭")
        self._close_btn.clicked.connect(self.close)
        layout.addWidget(self._close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_versions(
        self,
        file_name: str,
        old_version: str,
        new_version: str,
        old_text: str,
        new_text: str,
    ):
        """Populate the diff view with two versions' text."""
        self._header.setText(f"版本差异: {file_name} ({old_version} → {new_version})")
        self._left_label.setText(f"旧版本 ({old_version})")
        self._right_label.setText(f"新版本 ({new_version})")

        diff_lines = compute_diff(old_text, new_text)
        left_html = self._build_html(diff_lines, side="old")
        right_html = self._build_html(diff_lines, side="new")

        self._left_browser.setHtml(left_html)
        self._right_browser.setHtml(right_html)

    def _build_html(self, diff_lines, side: str) -> str:
        """Build HTML with color highlighting for one side."""
        lines = []
        for dl in diff_lines:
            if side == "old":
                text = dl.old_line
                if dl.type == DiffType.ADDED:
                    continue  # Added lines don't appear in old
                color = self._color_for_type(dl.type, side="old")
            else:
                text = dl.new_line
                if dl.type == DiffType.REMOVED:
                    continue  # Removed lines don't appear in new
                color = self._color_for_type(dl.type, side="new")

            escaped = text.replace("<", "&lt;").replace(">", "&gt;")
            if color:
                lines.append(f'<div style="background-color:{color};padding:2px;">{escaped}</div>')
            else:
                lines.append(f'<div style="padding:2px;">{escaped}</div>')

        return "<br>".join(lines) if lines else "<i>(无内容)</i>"

    def _color_for_type(self, diff_type: DiffType, side: str) -> str:
        """Return background color for diff type. Empty string = no highlight."""
        if diff_type == DiffType.UNCHANGED:
            return ""
        if diff_type == DiffType.ADDED:
            return "#d4edda"  # light green
        if diff_type == DiffType.REMOVED:
            return "#f8d7da"  # light red
        if diff_type == DiffType.MODIFIED:
            return "#fff3cd"  # light yellow
        return ""
```

- [ ] **Step 2: Verify it imports correctly**

Run: `python -c "from dochistory.ui.diff_window import DiffWindow; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add dochistory/ui/diff_window.py
git commit -m "feat: add diff comparison window with color highlighting"
```

---

## Task 13: Settings Window (ui/settings_window.py)

**Files:**
- Create: `dochistory/ui/settings_window.py`

- [ ] **Step 1: Write the settings window module**

```python
"""Settings window for monitor paths and retention policy."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton,
    QSpinBox, QCheckBox, QGroupBox, QFormLayout, QMessageBox, QFileDialog,
)
from PyQt6.QtCore import pyqtSignal

from dochistory.core.database import Database


class SettingsWindow(QDialog):
    """Settings dialog for configuring monitor paths and retention."""

    settings_changed = pyqtSignal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self._db = db
        self.setWindowTitle("设置")
        self.resize(500, 400)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Monitor paths group
        paths_group = QGroupBox("监控文件夹")
        paths_layout = QVBoxLayout()

        self._paths_list = QListWidget()
        paths_layout.addWidget(self._paths_list)

        btn_layout = QHBoxLayout()
        self._add_btn = QPushButton("添加文件夹")
        self._add_btn.clicked.connect(self._add_folder)
        self._remove_btn = QPushButton("移除")
        self._remove_btn.clicked.connect(self._remove_folder)
        btn_layout.addWidget(self._add_btn)
        btn_layout.addWidget(self._remove_btn)
        btn_layout.addStretch()
        paths_layout.addLayout(btn_layout)

        paths_group.setLayout(paths_layout)
        layout.addWidget(paths_group)

        # Retention policy group
        retention_group = QGroupBox("版本保留策略")
        retention_layout = QFormLayout()

        self._max_versions = QSpinBox()
        self._max_versions.setRange(1, 999)
        self._max_versions.setSuffix(" 个")
        retention_layout.addRow("每文件最大版本数:", self._max_versions)

        self._retention_days = QSpinBox()
        self._retention_days.setRange(1, 3650)
        self._retention_days.setSuffix(" 天")
        retention_layout.addRow("保留天数:", self._retention_days)

        self._auto_cleanup = QCheckBox("启用自动清理")
        retention_layout.addRow(self._auto_cleanup)

        retention_group.setLayout(retention_layout)
        layout.addWidget(retention_group)

        # Save/close buttons
        btn_layout2 = QHBoxLayout()
        self._save_btn = QPushButton("保存")
        self._save_btn.clicked.connect(self._save)
        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout2.addStretch()
        btn_layout2.addWidget(self._save_btn)
        btn_layout2.addWidget(self._cancel_btn)
        layout.addLayout(btn_layout2)

    def _load_settings(self):
        # Load folders
        folders = self._db.get_folders(include_inactive=True)
        self._paths_list.clear()
        for f in folders:
            status = "✓" if f["is_active"] else "✗"
            self._paths_list.addItem(f"{status} {f['path']}")

        # Load config
        max_ver = self._db.get_config("max_versions_per_file", "50")
        self._max_versions.setValue(int(max_ver))

        days = self._db.get_config("retention_days", "30")
        self._retention_days.setValue(int(days))

        auto = self._db.get_config("auto_cleanup_enabled", "1")
        self._auto_cleanup.setChecked(auto == "1")

    def _add_folder(self):
        path = QFileDialog.getExistingDirectory(self, "选择监控文件夹")
        if path:
            try:
                self._db.add_folder(path)
                self._load_settings()
            except ValueError:
                QMessageBox.warning(self, "提示", "该文件夹已在监控列表中")

    def _remove_folder(self):
        current = self._paths_list.currentRow()
        if current < 0:
            return
        folders = self._db.get_folders(include_inactive=True)
        if current < len(folders):
            self._db.deactivate_folder(folders[current]["id"])
            self._load_settings()

    def _save(self):
        self._db.set_config("max_versions_per_file", str(self._max_versions.value()))
        self._db.set_config("retention_days", str(self._retention_days.value()))
        self._db.set_config("auto_cleanup_enabled", "1" if self._auto_cleanup.isChecked() else "0")
        self.settings_changed.emit()
        self.accept()
```

- [ ] **Step 2: Verify it imports correctly**

Run: `python -c "from dochistory.ui.settings_window import SettingsWindow; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add dochistory/ui/settings_window.py
git commit -m "feat: add settings window for monitor paths and retention"
```

---

## Task 14: Main Window (ui/main_window.py)

**Files:**
- Create: `dochistory/ui/main_window.py`

- [ ] **Step 1: Write the main window module**

```python
"""Main window with GitHub Desktop style layout (Plan B)."""
import os

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit,
    QComboBox, QListWidget, QListWidgetItem, QPushButton, QSplitter,
    QFrame, QMessageBox, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from dochistory.core.database import Database
from dochistory.core.version_manager import VersionManager
from dochistory.core.document_parser import get_parser_for_file
from dochistory.utils.file_utils import decompress_data
from dochistory.ui.diff_window import DiffWindow
from dochistory.ui.settings_window import SettingsWindow


class MainWindow(QMainWindow):
    """Main application window - GitHub Desktop style layout."""

    request_quit = pyqtSignal()

    def __init__(self, db: Database, version_manager: VersionManager, parent=None):
        super().__init__(parent)
        self._db = db
        self._vm = version_manager
        self._diff_window = None
        self._settings_window = None
        self._current_folder_id = None
        self._current_file_id = None
        self.setWindowTitle("DocHistory - 文档版本控制")
        self.resize(900, 600)
        self._setup_ui()
        self._refresh_folders()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Top bar: folder dropdown + search
        top_bar = QHBoxLayout()
        self._folder_combo = QComboBox()
        self._folder_combo.currentIndexChanged.connect(self._on_folder_changed)
        top_bar.addWidget(QLabel("文件夹:"))
        top_bar.addWidget(self._folder_combo, stretch=1)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("搜索文件...")
        self._search_edit.textChanged.connect(self._on_search_changed)
        top_bar.addWidget(self._search_edit, stretch=1)

        self._settings_btn = QPushButton("设置")
        self._settings_btn.clicked.connect(self._open_settings)
        top_bar.addWidget(self._settings_btn)

        main_layout.addLayout(top_bar)

        # Splitter: left file list, right version timeline
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: file list
        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self._file_label = QLabel("文件")
        left_layout.addWidget(self._file_label)
        self._file_list = QListWidget()
        self._file_list.currentRowChanged.connect(self._on_file_selected)
        left_layout.addWidget(self._file_list)
        splitter.addWidget(left_frame)

        # Right: version timeline + actions
        right_frame = QFrame()
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self._file_title = QLabel("选择一个文件")
        self._file_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        right_layout.addWidget(self._file_title)

        self._version_label = QLabel("版本历史")
        right_layout.addWidget(self._version_label)

        self._version_list = QListWidget()
        right_layout.addWidget(self._version_list, stretch=1)

        # Action buttons
        btn_layout = QHBoxLayout()
        self._rollback_btn = QPushButton("回退到此版本")
        self._rollback_btn.clicked.connect(self._rollback)
        self._diff_btn = QPushButton("比较差异")
        self._diff_btn.clicked.connect(self._show_diff)
        self._export_btn = QPushButton("导出版本")
        self._export_btn.clicked.connect(self._export_version)
        self._note_btn = QPushButton("添加备注")
        self._note_btn.clicked.connect(self._add_note)
        for btn in [self._rollback_btn, self._diff_btn, self._export_btn, self._note_btn]:
            btn.setEnabled(False)
            btn_layout.addWidget(btn)
        right_layout.addLayout(btn_layout)

        splitter.addWidget(right_frame)
        splitter.setSizes([300, 600])
        main_layout.addWidget(splitter, stretch=1)

    def _refresh_folders(self):
        self._folder_combo.clear()
        folders = self._db.get_folders()
        for f in folders:
            self._folder_combo.addItem(f["path"], f["id"])
        if folders:
            self._current_folder_id = folders[0]["id"]
            self._refresh_files()

    def _on_folder_changed(self, index):
        if index >= 0:
            self._current_folder_id = self._folder_combo.itemData(index)
            self._refresh_files()

    def _refresh_files(self):
        self._file_list.clear()
        if self._current_folder_id is None:
            return
        files = self._db.get_files(self._current_folder_id)
        for f in files:
            versions = self._db.get_versions(f["id"])
            item_text = f"{f['relative_path']}  ({len(versions)} 版本)"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, f["id"])
            self._file_list.addItem(item)

    def _on_search_changed(self, text):
        for i in range(self._file_list.count()):
            item = self._file_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def _on_file_selected(self, row):
        if row < 0:
            self._current_file_id = None
            return
        item = self._file_list.item(row)
        self._current_file_id = item.data(Qt.ItemDataRole.UserRole)
        self._refresh_versions()

    def _refresh_versions(self):
        self._version_list.clear()
        if self._current_file_id is None:
            self._file_title.setText("选择一个文件")
            return

        files = self._db.get_files(self._current_folder_id)
        file_rec = None
        for f in files:
            if f["id"] == self._current_file_id:
                file_rec = f
                break
        if file_rec:
            self._file_title.setText(file_rec["relative_path"])

        versions = self._db.get_versions(self._current_file_id)
        self._version_label.setText(f"版本历史 ({len(versions)} 个版本)")
        for v in versions:
            auto_tag = "自动" if v["is_auto"] else "手动"
            note = v["note"] or ""
            item_text = f"v{v['version_number']}  {v['timestamp']}  [{auto_tag}]  {note}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, v["id"])
            self._version_list.addItem(item)

        # Enable buttons if versions exist
        has_versions = len(versions) > 0
        self._diff_btn.setEnabled(has_versions)
        self._export_btn.setEnabled(has_versions)
        self._rollback_btn.setEnabled(has_versions)
        self._note_btn.setEnabled(has_versions)

    def _get_selected_version_id(self):
        row = self._version_list.currentRow()
        if row < 0:
            return None
        return self._version_list.item(row).data(Qt.ItemDataRole.UserRole)

    def _rollback(self):
        version_id = self._get_selected_version_id()
        if version_id is None or self._current_file_id is None:
            return
        reply = QMessageBox.question(
            self, "确认回退",
            "确定要回退到此版本吗？当前未保存的修改将自动备份。",
        )
        if reply == QMessageBox.StandardButton.Yes:
            success = self._vm.rollback_to_version(self._current_file_id, version_id)
            if success:
                QMessageBox.information(self, "成功", "已回退到指定版本")
                self._refresh_versions()
            else:
                QMessageBox.warning(self, "失败", "回退失败")

    def _show_diff(self):
        if self._current_file_id is None:
            return
        versions = self._db.get_versions(self._current_file_id)
        if len(versions) < 2:
            QMessageBox.information(self, "提示", "需要至少2个版本才能比较差异")
            return

        # Use latest two versions for diff
        v_new = versions[0]
        v_old = versions[1]

        # Extract text from both versions
        old_data = self._db.get_version_data(v_old["id"])
        new_data = self._db.get_version_data(v_new["id"])
        if old_data is None or new_data is None:
            return

        old_bytes = decompress_data(old_data)
        new_bytes = decompress_data(new_data)

        # Write to temp files for parsing
        import tempfile
        old_fd, old_tmp = tempfile.mkstemp(suffix=".docx")
        new_fd, new_tmp = tempfile.mkstemp(suffix=".docx")
        try:
            with os.fdopen(old_fd, "wb") as f:
                f.write(old_bytes)
            with os.fdopen(new_fd, "wb") as f:
                f.write(new_bytes)

            parser = get_parser_for_file(old_tmp)
            try:
                old_text = parser.extract_text(old_tmp)
                new_text = parser.extract_text(new_tmp)
            except NotImplementedError:
                QMessageBox.warning(self, "不支持", "该格式不支持文本差异比较")
                return
        finally:
            os.remove(old_tmp)
            os.remove(new_tmp)

        file_rec = None
        for f in self._db.get_files(self._current_folder_id):
            if f["id"] == self._current_file_id:
                file_rec = f
                break

        file_name = file_rec["relative_path"] if file_rec else "unknown"
        self._diff_window = DiffWindow(self)
        self._diff_window.set_versions(
            file_name,
            f"v{v_old['version_number']}",
            f"v{v_new['version_number']}",
            old_text,
            new_text,
        )
        self._diff_window.show()

    def _export_version(self):
        version_id = self._get_selected_version_id()
        if version_id is None or self._current_file_id is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出版本", "", "Word文档 (*.docx)")
        if path:
            success = self._vm.export_version(self._current_file_id, version_id, path)
            if success:
                QMessageBox.information(self, "成功", f"已导出到 {path}")
            else:
                QMessageBox.warning(self, "失败", "导出失败")

    def _add_note(self):
        version_id = self._get_selected_version_id()
        if version_id is None:
            return
        # Simple inline note editing
        from PyQt6.QtWidgets import QInputDialog
        note, ok = QInputDialog.getText(self, "添加备注", "版本备注:")
        if ok and note:
            # Update note directly in DB
            self._db.set_version_note(version_id, note)
            self._refresh_versions()

    def _open_settings(self):
        self._settings_window = SettingsWindow(self._db, self)
        self._settings_window.settings_changed.connect(self._refresh_folders)
        self._settings_window.exec()

    def refresh(self):
        """Refresh the entire UI (called when files change)."""
        self._refresh_files()
        if self._current_file_id:
            self._refresh_versions()

    def closeEvent(self, event):
        """Minimize to tray instead of quitting."""
        event.ignore()
        self.hide()
```

- [ ] **Step 2: Add `set_version_note` to Database**

Add this method to the `Database` class in `dochistory/core/database.py`:

```python
    def set_version_note(self, version_id: int, note: str):
        with self._lock:
            self._conn.execute(
                "UPDATE versions SET note = ? WHERE id = ?",
                (note, version_id),
            )
            self._conn.commit()
```

- [ ] **Step 3: Verify it imports correctly**

Run: `python -c "from dochistory.ui.main_window import MainWindow; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add dochistory/ui/main_window.py dochistory/core/database.py
git commit -m "feat: add main window with GitHub Desktop style layout"
```

---

## Task 15: Application Entry Point (main.py)

**Files:**
- Create: `dochistory/main.py`

- [ ] **Step 1: Write the entry point**

```python
"""DocHistory application entry point."""
import os
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

from dochistory.core.database import Database
from dochistory.core.file_monitor import FileMonitor
from dochistory.core.version_manager import VersionManager
from dochistory.ui.main_window import MainWindow
from dochistory.ui.tray import SystemTray
from dochistory.utils.file_utils import get_db_path, is_supported_file, is_temp_file


class DocHistoryApp:
    """Main application coordinator."""

    def __init__(self):
        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)

        # Initialize core
        db_path = get_db_path()
        os.makedirs(os.path.dirname(str(db_path)), exist_ok=True)
        self._db = Database(str(db_path))
        self._vm = VersionManager(self._db)
        self._monitor = FileMonitor()

        # Initialize UI
        self._window = MainWindow(self._db, self._vm)
        self._tray = SystemTray()

        self._setup_connections()
        self._start_monitoring()

    def _setup_connections(self):
        # Monitor signals → version creation
        self._monitor.file_saved.connect(self._on_file_saved)
        self._monitor.file_moved.connect(self._on_file_moved)
        self._monitor.file_created.connect(self._on_file_created)
        self._monitor.file_deleted.connect(self._on_file_deleted)

        # Tray signals
        self._tray.show_window_requested.connect(self._window.show)
        self._tray.quit_requested.connect(self._quit)
        self._tray.pause_monitoring_requested.connect(self._monitor.pause)
        self._tray.resume_monitoring_requested.connect(self._monitor.resume)

    def _start_monitoring(self):
        folders = self._db.get_folders()
        for f in folders:
            self._monitor.add_watch(f["path"])

    def _find_folder_id_for_path(self, file_path: str):
        """Find which monitored folder a file belongs to."""
        folders = self._db.get_folders()
        for f in folders:
            if file_path.startswith(f["path"]):
                return f["id"]
        return None

    def _on_file_saved(self, file_path: str):
        folder_id = self._find_folder_id_for_path(file_path)
        if folder_id is None:
            return
        version = self._vm.create_version(file_path, folder_id)
        if version:
            self._window.refresh()

    def _on_file_moved(self, src_path: str, dest_path: str):
        old_folder_id = self._find_folder_id_for_path(src_path)
        new_folder_id = self._find_folder_id_for_path(dest_path)

        if old_folder_id and new_folder_id:
            if old_folder_id == new_folder_id:
                self._vm.handle_rename(src_path, dest_path, old_folder_id)
            else:
                self._vm.handle_move(src_path, dest_path, old_folder_id, new_folder_id)
        elif old_folder_id and not new_folder_id:
            self._vm.handle_move_out(src_path, old_folder_id)
        elif not old_folder_id and new_folder_id:
            # File moved into monitored area
            self._vm.create_version(dest_path, new_folder_id)

        self._window.refresh()

    def _on_file_created(self, file_path: str):
        folder_id = self._find_folder_id_for_path(file_path)
        if folder_id is None:
            return
        # Check if this might be a Save As
        source = self._vm.find_save_as_source(file_path)
        if source:
            # Create first version
            self._vm.handle_save_as(file_path, folder_id)
            self._tray.show_message(
                "检测到新文件",
                f"新文件 {os.path.basename(file_path)} 可能从 {source['relative_path']} 另存而来。"
                f"可在主窗口中关联历史。",
            )
        else:
            self._vm.create_version(file_path, folder_id)
        self._window.refresh()

    def _on_file_deleted(self, file_path: str):
        folder_id = self._find_folder_id_for_path(file_path)
        if folder_id is None:
            return
        relative_path = os.path.basename(file_path)
        file_rec = self._db.find_file(folder_id, relative_path)
        if file_rec:
            self._db.deactivate_file(file_rec["id"])
            self._window.refresh()

    def _quit(self):
        self._monitor.stop_all()
        self._tray.hide()
        self._db.close()
        self._app.quit()

    def run(self):
        self._tray.show()
        self._window.show()
        return self._app.exec()


def main():
    app = DocHistoryApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it imports correctly**

Run: `python -c "from dochistory.main import DocHistoryApp; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add dochistory/main.py
git commit -m "feat: add application entry point with full signal wiring"
```

---

## Task 16: Run Full Test Suite

- [ ] **Step 1: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Fix any failures**

If tests fail, fix the implementation. Common issues:
- Timing-sensitive file monitor tests: increase sleep durations
- Import errors: check `__init__.py` files exist
- Database locking: ensure `threading.Lock` is used correctly

- [ ] **Step 3: Commit any fixes**

```bash
git add -A
git commit -m "test: ensure full test suite passes"
```

---

## Task 17: Smoke Test - Manual Launch

- [ ] **Step 1: Launch the application**

Run: `python -m dochistory.main` (requires display; in headless env, skip and document)

If headless: `QT_QPA_PLATFORM=offscreen python -c "from dochistory.main import DocHistoryApp; app = DocHistoryApp(); print('App initialized successfully')" 2>&1 | head -5`

Expected: "App initialized successfully" or window appears

- [ ] **Step 2: Document manual test checklist**

Create a note (not a file) with the manual test checklist:
1. Launch app → window appears with tray icon
2. Open Settings → add a monitor folder → save
3. Create a .docx file in that folder → version v1 appears in UI
4. Edit and save the .docx → version v2 appears
5. Select v1 → click "回退到此版本" → file content reverts
6. Select two versions → click "比较差异" → diff window shows changes
7. Close window → app minimizes to tray (monitoring continues)
8. Tray right-click → "退出" → app exits cleanly

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test: verify smoke test and document manual checklist"
```

---

## Self-Review Notes

**Spec coverage check:**
- ✅ Real-time file monitoring (Task 7)
- ✅ Auto version recording (Task 6)
- ✅ Version rollback (Task 6, 10)
- ✅ Diff comparison (Task 5, 12)
- ✅ Offline operation (all local)
- ✅ File rename/move tracking (Task 8)
- ✅ Save-as tracking (Task 8, 9)
- ✅ System tray (Task 11)
- ✅ Settings window (Task 13)
- ✅ GitHub Desktop style UI (Task 14)
- ✅ Auto cleanup (Task 6)
- ✅ Manual version with note (Task 6)
- ✅ Export version (Task 6)
- ✅ Database schema (Task 3)
- ✅ Document parser with stub (Task 4)
- ✅ Debounce (Task 7)
- ✅ Temp file filtering (Task 2)
- ✅ Thread safety (Task 3)
- ✅ Atomic write (Task 6)
- ✅ Retry on locked file (Task 6)
- ✅ Entry point wiring (Task 15)

**Type consistency check:**
- `Database.create_version` signature consistent across tasks
- `VersionManager.create_version` takes `file_path` and `folder_id` consistently
- `FileMonitor` signals: `file_saved(str)`, `file_moved(str, str)`, `file_created(str)`, `file_deleted(str)` — consistent in Task 7 and Task 15
- `DiffLine` fields: `type`, `old_line`, `new_line`, `old_line_no`, `new_line_no` — consistent in Task 5 and Task 12
