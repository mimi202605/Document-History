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
