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
