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
