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

    def test_win32_parser_get_snapshot_reads_bytes(self, tmp_path):
        # get_snapshot 仅读取原始字节，在非 Windows 平台也应正常工作
        path = tmp_path / "test.doc"
        content = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1fake doc binary content"
        path.write_bytes(content)
        parser = Win32DocumentParser()
        snapshot = parser.get_snapshot(str(path))
        assert snapshot == content

    def test_win32_parser_get_snapshot_on_wps_file(self, tmp_path):
        # .wps 文件同样应能读取原始字节
        path = tmp_path / "test.wps"
        content = b"wps file binary content"
        path.write_bytes(content)
        parser = Win32DocumentParser()
        snapshot = parser.get_snapshot(str(path))
        assert snapshot == content

    def test_get_parser_for_doc_returns_win32_parser(self):
        # 验证 .doc 文件返回 Win32DocumentParser 实例
        parser = get_parser_for_file("test.doc")
        assert isinstance(parser, Win32DocumentParser)


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
