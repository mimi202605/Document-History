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
        # Rename records a special version, so count may increase.
        assert versions_after >= versions_before

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
        # Move records a special version, so count may increase.
        assert versions_after >= versions_before


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
