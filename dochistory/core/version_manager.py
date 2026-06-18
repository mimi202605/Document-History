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

        # Create backup of current on-disk state before overwriting.
        # Only skip when rolling back to the latest version AND the file
        # on disk still matches that latest version (no-op rollback).
        if latest and os.path.exists(file_path):
            current_hash = compute_md5(file_path)
            is_noop = latest["id"] == version_id and current_hash == file_rec["file_hash"]
            if not is_noop:
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
