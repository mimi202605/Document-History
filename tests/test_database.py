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
