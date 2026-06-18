"""Main window with GitHub Desktop style layout (Plan B)."""
import os

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit,
    QComboBox, QListWidget, QListWidgetItem, QPushButton, QSplitter,
    QFrame, QMessageBox, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from dochistory.core.database import Database
from dochistory.core.version_manager import VersionManager
from dochistory.core.document_parser import get_parser_for_file
from dochistory.utils.file_utils import decompress_data
from dochistory.ui.diff_window import DiffWindow
from dochistory.ui.settings_window import SettingsWindow


class MainWindow(QMainWindow):
    """Main application window - GitHub Desktop style layout."""

    request_quit = pyqtSignal()

    def __init__(self, db: Database, version_manager: VersionManager, parent=None):
        super().__init__(parent)
        self._db = db
        self._vm = version_manager
        self._diff_window = None
        self._settings_window = None
        self._current_folder_id = None
        self._current_file_id = None
        self.setWindowTitle("DocHistory - 文档版本控制")
        self.resize(900, 600)
        self._setup_ui()
        self._refresh_folders()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Top bar: folder dropdown + search
        top_bar = QHBoxLayout()
        self._folder_combo = QComboBox()
        self._folder_combo.currentIndexChanged.connect(self._on_folder_changed)
        top_bar.addWidget(QLabel("文件夹:"))
        top_bar.addWidget(self._folder_combo, stretch=1)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("搜索文件...")
        self._search_edit.textChanged.connect(self._on_search_changed)
        top_bar.addWidget(self._search_edit, stretch=1)

        self._settings_btn = QPushButton("设置")
        self._settings_btn.clicked.connect(self._open_settings)
        top_bar.addWidget(self._settings_btn)

        main_layout.addLayout(top_bar)

        # Splitter: left file list, right version timeline
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: file list
        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self._file_label = QLabel("文件")
        left_layout.addWidget(self._file_label)
        self._file_list = QListWidget()
        self._file_list.currentRowChanged.connect(self._on_file_selected)
        left_layout.addWidget(self._file_list)
        splitter.addWidget(left_frame)

        # Right: version timeline + actions
        right_frame = QFrame()
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self._file_title = QLabel("选择一个文件")
        self._file_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        right_layout.addWidget(self._file_title)

        self._version_label = QLabel("版本历史")
        right_layout.addWidget(self._version_label)

        self._version_list = QListWidget()
        right_layout.addWidget(self._version_list, stretch=1)

        # Action buttons
        btn_layout = QHBoxLayout()
        self._rollback_btn = QPushButton("回退到此版本")
        self._rollback_btn.clicked.connect(self._rollback)
        self._diff_btn = QPushButton("比较差异")
        self._diff_btn.clicked.connect(self._show_diff)
        self._export_btn = QPushButton("导出版本")
        self._export_btn.clicked.connect(self._export_version)
        self._note_btn = QPushButton("添加备注")
        self._note_btn.clicked.connect(self._add_note)
        for btn in [self._rollback_btn, self._diff_btn, self._export_btn, self._note_btn]:
            btn.setEnabled(False)
            btn_layout.addWidget(btn)
        right_layout.addLayout(btn_layout)

        splitter.addWidget(right_frame)
        splitter.setSizes([300, 600])
        main_layout.addWidget(splitter, stretch=1)

    def _refresh_folders(self):
        self._folder_combo.clear()
        folders = self._db.get_folders()
        for f in folders:
            self._folder_combo.addItem(f["path"], f["id"])
        if folders:
            self._current_folder_id = folders[0]["id"]
            self._refresh_files()

    def _on_folder_changed(self, index):
        if index >= 0:
            self._current_folder_id = self._folder_combo.itemData(index)
            self._refresh_files()

    def _refresh_files(self):
        self._file_list.clear()
        if self._current_folder_id is None:
            return
        files = self._db.get_files(self._current_folder_id)
        for f in files:
            versions = self._db.get_versions(f["id"])
            item_text = f"{f['relative_path']}  ({len(versions)} 版本)"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, f["id"])
            self._file_list.addItem(item)

    def _on_search_changed(self, text):
        for i in range(self._file_list.count()):
            item = self._file_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def _on_file_selected(self, row):
        if row < 0:
            self._current_file_id = None
            return
        item = self._file_list.item(row)
        self._current_file_id = item.data(Qt.ItemDataRole.UserRole)
        self._refresh_versions()

    def _refresh_versions(self):
        self._version_list.clear()
        if self._current_file_id is None:
            self._file_title.setText("选择一个文件")
            return

        files = self._db.get_files(self._current_folder_id)
        file_rec = None
        for f in files:
            if f["id"] == self._current_file_id:
                file_rec = f
                break
        if file_rec:
            self._file_title.setText(file_rec["relative_path"])

        versions = self._db.get_versions(self._current_file_id)
        self._version_label.setText(f"版本历史 ({len(versions)} 个版本)")
        for v in versions:
            auto_tag = "自动" if v["is_auto"] else "手动"
            note = v["note"] or ""
            item_text = f"v{v['version_number']}  {v['timestamp']}  [{auto_tag}]  {note}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, v["id"])
            self._version_list.addItem(item)

        # Enable buttons if versions exist
        has_versions = len(versions) > 0
        self._diff_btn.setEnabled(has_versions)
        self._export_btn.setEnabled(has_versions)
        self._rollback_btn.setEnabled(has_versions)
        self._note_btn.setEnabled(has_versions)

    def _get_selected_version_id(self):
        row = self._version_list.currentRow()
        if row < 0:
            return None
        return self._version_list.item(row).data(Qt.ItemDataRole.UserRole)

    def _rollback(self):
        version_id = self._get_selected_version_id()
        if version_id is None or self._current_file_id is None:
            return
        reply = QMessageBox.question(
            self, "确认回退",
            "确定要回退到此版本吗？当前未保存的修改将自动备份。",
        )
        if reply == QMessageBox.StandardButton.Yes:
            success = self._vm.rollback_to_version(self._current_file_id, version_id)
            if success:
                QMessageBox.information(self, "成功", "已回退到指定版本")
                self._refresh_versions()
            else:
                QMessageBox.warning(self, "失败", "回退失败")

    def _show_diff(self):
        if self._current_file_id is None:
            return
        versions = self._db.get_versions(self._current_file_id)
        if len(versions) < 2:
            QMessageBox.information(self, "提示", "需要至少2个版本才能比较差异")
            return

        # Use latest two versions for diff
        v_new = versions[0]
        v_old = versions[1]

        # Extract text from both versions
        old_data = self._db.get_version_data(v_old["id"])
        new_data = self._db.get_version_data(v_new["id"])
        if old_data is None or new_data is None:
            return

        old_bytes = decompress_data(old_data)
        new_bytes = decompress_data(new_data)

        # Write to temp files for parsing
        import tempfile
        old_fd, old_tmp = tempfile.mkstemp(suffix=".docx")
        new_fd, new_tmp = tempfile.mkstemp(suffix=".docx")
        try:
            with os.fdopen(old_fd, "wb") as f:
                f.write(old_bytes)
            with os.fdopen(new_fd, "wb") as f:
                f.write(new_bytes)

            parser = get_parser_for_file(old_tmp)
            try:
                old_text = parser.extract_text(old_tmp)
                new_text = parser.extract_text(new_tmp)
            except NotImplementedError:
                QMessageBox.warning(self, "不支持", "该格式不支持文本差异比较")
                return
        finally:
            os.remove(old_tmp)
            os.remove(new_tmp)

        file_rec = None
        for f in self._db.get_files(self._current_folder_id):
            if f["id"] == self._current_file_id:
                file_rec = f
                break

        file_name = file_rec["relative_path"] if file_rec else "unknown"
        self._diff_window = DiffWindow(self)
        self._diff_window.set_versions(
            file_name,
            f"v{v_old['version_number']}",
            f"v{v_new['version_number']}",
            old_text,
            new_text,
        )
        self._diff_window.show()

    def _export_version(self):
        version_id = self._get_selected_version_id()
        if version_id is None or self._current_file_id is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出版本", "", "Word文档 (*.docx)")
        if path:
            success = self._vm.export_version(self._current_file_id, version_id, path)
            if success:
                QMessageBox.information(self, "成功", f"已导出到 {path}")
            else:
                QMessageBox.warning(self, "失败", "导出失败")

    def _add_note(self):
        version_id = self._get_selected_version_id()
        if version_id is None:
            return
        # Simple inline note editing
        from PyQt6.QtWidgets import QInputDialog
        note, ok = QInputDialog.getText(self, "添加备注", "版本备注:")
        if ok and note:
            # Update note directly in DB
            self._db.set_version_note(version_id, note)
            self._refresh_versions()

    def _open_settings(self):
        self._settings_window = SettingsWindow(self._db, self)
        self._settings_window.settings_changed.connect(self._refresh_folders)
        self._settings_window.exec()

    def refresh(self):
        """Refresh the entire UI (called when files change)."""
        self._refresh_files()
        if self._current_file_id:
            self._refresh_versions()

    def closeEvent(self, event):
        """Minimize to tray instead of quitting."""
        event.ignore()
        self.hide()
