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

    def set_version_note(self, version_id: int, note: str):
        with self._lock:
            self._conn.execute(
                "UPDATE versions SET note = ? WHERE id = ?",
                (note, version_id),
            )
            self._conn.commit()

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
