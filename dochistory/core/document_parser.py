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

    On non-Windows platforms, extract_text raises NotImplementedError.
    get_snapshot only reads raw bytes and works on all platforms.
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
        # get_snapshot 仅读取原始字节，不需要 win32com，所有平台均可执行
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
