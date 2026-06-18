"""Side-by-side diff comparison window."""
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QTextBrowser, QLabel, QVBoxLayout, QPushButton,
)
from PyQt6.QtCore import Qt

from dochistory.utils.diff_utils import compute_diff, DiffType


class DiffWindow(QWidget):
    """Window showing side-by-side text diff between two versions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("版本差异比较")
        self.resize(1000, 600)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        self._header = QLabel("版本差异比较")
        self._header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._header)

        # Side-by-side text browsers
        content_layout = QHBoxLayout()

        left_container = QVBoxLayout()
        self._left_label = QLabel("旧版本")
        self._left_browser = QTextBrowser()
        self._left_browser.setReadOnly(True)
        left_container.addWidget(self._left_label)
        left_container.addWidget(self._left_browser)
        content_layout.addLayout(left_container)

        right_container = QVBoxLayout()
        self._right_label = QLabel("新版本")
        self._right_browser = QTextBrowser()
        self._right_browser.setReadOnly(True)
        right_container.addWidget(self._right_label)
        right_container.addWidget(self._right_browser)
        content_layout.addLayout(right_container)

        layout.addLayout(content_layout, stretch=1)

        # Close button
        self._close_btn = QPushButton("关闭")
        self._close_btn.clicked.connect(self.close)
        layout.addWidget(self._close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_versions(
        self,
        file_name: str,
        old_version: str,
        new_version: str,
        old_text: str,
        new_text: str,
    ):
        """Populate the diff view with two versions' text."""
        self._header.setText(f"版本差异: {file_name} ({old_version} → {new_version})")
        self._left_label.setText(f"旧版本 ({old_version})")
        self._right_label.setText(f"新版本 ({new_version})")

        diff_lines = compute_diff(old_text, new_text)
        left_html = self._build_html(diff_lines, side="old")
        right_html = self._build_html(diff_lines, side="new")

        self._left_browser.setHtml(left_html)
        self._right_browser.setHtml(right_html)

    def _build_html(self, diff_lines, side: str) -> str:
        """Build HTML with color highlighting for one side."""
        lines = []
        for dl in diff_lines:
            if side == "old":
                text = dl.old_line
                if dl.type == DiffType.ADDED:
                    continue  # Added lines don't appear in old
                color = self._color_for_type(dl.type, side="old")
            else:
                text = dl.new_line
                if dl.type == DiffType.REMOVED:
                    continue  # Removed lines don't appear in new
                color = self._color_for_type(dl.type, side="new")

            escaped = text.replace("<", "&lt;").replace(">", "&gt;")
            if color:
                lines.append(f'<div style="background-color:{color};padding:2px;">{escaped}</div>')
            else:
                lines.append(f'<div style="padding:2px;">{escaped}</div>')

        return "<br>".join(lines) if lines else "<i>(无内容)</i>"

    def _color_for_type(self, diff_type: DiffType, side: str) -> str:
        """Return background color for diff type. Empty string = no highlight."""
        if diff_type == DiffType.UNCHANGED:
            return ""
        if diff_type == DiffType.ADDED:
            return "#d4edda"  # light green
        if diff_type == DiffType.REMOVED:
            return "#f8d7da"  # light red
        if diff_type == DiffType.MODIFIED:
            return "#fff3cd"  # light yellow
        return ""
