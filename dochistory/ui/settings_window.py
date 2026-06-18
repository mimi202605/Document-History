"""Settings window for monitor paths and retention policy."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton,
    QSpinBox, QCheckBox, QGroupBox, QFormLayout, QMessageBox, QFileDialog,
)
from PyQt6.QtCore import pyqtSignal

from dochistory.core.database import Database


class SettingsWindow(QDialog):
    """Settings dialog for configuring monitor paths and retention."""

    settings_changed = pyqtSignal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self._db = db
        self.setWindowTitle("设置")
        self.resize(500, 400)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Monitor paths group
        paths_group = QGroupBox("监控文件夹")
        paths_layout = QVBoxLayout()

        self._paths_list = QListWidget()
        paths_layout.addWidget(self._paths_list)

        btn_layout = QHBoxLayout()
        self._add_btn = QPushButton("添加文件夹")
        self._add_btn.clicked.connect(self._add_folder)
        self._remove_btn = QPushButton("移除")
        self._remove_btn.clicked.connect(self._remove_folder)
        btn_layout.addWidget(self._add_btn)
        btn_layout.addWidget(self._remove_btn)
        btn_layout.addStretch()
        paths_layout.addLayout(btn_layout)

        paths_group.setLayout(paths_layout)
        layout.addWidget(paths_group)

        # Retention policy group
        retention_group = QGroupBox("版本保留策略")
        retention_layout = QFormLayout()

        self._max_versions = QSpinBox()
        self._max_versions.setRange(1, 999)
        self._max_versions.setSuffix(" 个")
        retention_layout.addRow("每文件最大版本数:", self._max_versions)

        self._retention_days = QSpinBox()
        self._retention_days.setRange(1, 3650)
        self._retention_days.setSuffix(" 天")
        retention_layout.addRow("保留天数:", self._retention_days)

        self._auto_cleanup = QCheckBox("启用自动清理")
        retention_layout.addRow(self._auto_cleanup)

        retention_group.setLayout(retention_layout)
        layout.addWidget(retention_group)

        # Save/close buttons
        btn_layout2 = QHBoxLayout()
        self._save_btn = QPushButton("保存")
        self._save_btn.clicked.connect(self._save)
        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout2.addStretch()
        btn_layout2.addWidget(self._save_btn)
        btn_layout2.addWidget(self._cancel_btn)
        layout.addLayout(btn_layout2)

    def _load_settings(self):
        # Load folders
        folders = self._db.get_folders(include_inactive=True)
        self._paths_list.clear()
        for f in folders:
            status = "✓" if f["is_active"] else "✗"
            self._paths_list.addItem(f"{status} {f['path']}")

        # Load config
        max_ver = self._db.get_config("max_versions_per_file", "50")
        self._max_versions.setValue(int(max_ver))

        days = self._db.get_config("retention_days", "30")
        self._retention_days.setValue(int(days))

        auto = self._db.get_config("auto_cleanup_enabled", "1")
        self._auto_cleanup.setChecked(auto == "1")

    def _add_folder(self):
        path = QFileDialog.getExistingDirectory(self, "选择监控文件夹")
        if path:
            try:
                self._db.add_folder(path)
                self._load_settings()
            except ValueError:
                QMessageBox.warning(self, "提示", "该文件夹已在监控列表中")

    def _remove_folder(self):
        current = self._paths_list.currentRow()
        if current < 0:
            return
        folders = self._db.get_folders(include_inactive=True)
        if current < len(folders):
            self._db.deactivate_folder(folders[current]["id"])
            self._load_settings()

    def _save(self):
        self._db.set_config("max_versions_per_file", str(self._max_versions.value()))
        self._db.set_config("retention_days", str(self._retention_days.value()))
        self._db.set_config("auto_cleanup_enabled", "1" if self._auto_cleanup.isChecked() else "0")
        self.settings_changed.emit()
        self.accept()
