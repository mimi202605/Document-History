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
