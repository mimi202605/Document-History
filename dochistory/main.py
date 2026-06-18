"""DocHistory application entry point."""
import os
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

from dochistory.core.database import Database
from dochistory.core.file_monitor import FileMonitor
from dochistory.core.version_manager import VersionManager
from dochistory.ui.main_window import MainWindow
from dochistory.ui.tray import SystemTray
from dochistory.utils.file_utils import get_db_path, is_supported_file, is_temp_file


class DocHistoryApp:
    """Main application coordinator."""

    def __init__(self):
        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)

        # Initialize core
        db_path = get_db_path()
        os.makedirs(os.path.dirname(str(db_path)), exist_ok=True)
        self._db = Database(str(db_path))
        self._vm = VersionManager(self._db)
        self._monitor = FileMonitor()

        # Initialize UI
        self._window = MainWindow(self._db, self._vm)
        self._tray = SystemTray()

        self._setup_connections()
        self._start_monitoring()

    def _setup_connections(self):
        # Monitor signals → version creation
        self._monitor.file_saved.connect(self._on_file_saved)
        self._monitor.file_moved.connect(self._on_file_moved)
        self._monitor.file_created.connect(self._on_file_created)
        self._monitor.file_deleted.connect(self._on_file_deleted)

        # Tray signals
        self._tray.show_window_requested.connect(self._window.show)
        self._tray.quit_requested.connect(self._quit)
        self._tray.pause_monitoring_requested.connect(self._monitor.pause)
        self._tray.resume_monitoring_requested.connect(self._monitor.resume)

    def _start_monitoring(self):
        folders = self._db.get_folders()
        for f in folders:
            self._monitor.add_watch(f["path"])

    def _find_folder_id_for_path(self, file_path: str):
        """Find which monitored folder a file belongs to."""
        folders = self._db.get_folders()
        for f in folders:
            if file_path.startswith(f["path"]):
                return f["id"]
        return None

    def _on_file_saved(self, file_path: str):
        folder_id = self._find_folder_id_for_path(file_path)
        if folder_id is None:
            return
        version = self._vm.create_version(file_path, folder_id)
        if version:
            self._window.refresh()

    def _on_file_moved(self, src_path: str, dest_path: str):
        old_folder_id = self._find_folder_id_for_path(src_path)
        new_folder_id = self._find_folder_id_for_path(dest_path)

        if old_folder_id and new_folder_id:
            if old_folder_id == new_folder_id:
                self._vm.handle_rename(src_path, dest_path, old_folder_id)
            else:
                self._vm.handle_move(src_path, dest_path, old_folder_id, new_folder_id)
        elif old_folder_id and not new_folder_id:
            self._vm.handle_move_out(src_path, old_folder_id)
        elif not old_folder_id and new_folder_id:
            # File moved into monitored area
            self._vm.create_version(dest_path, new_folder_id)

        self._window.refresh()

    def _on_file_created(self, file_path: str):
        folder_id = self._find_folder_id_for_path(file_path)
        if folder_id is None:
            return
        # Check if this might be a Save As
        source = self._vm.find_save_as_source(file_path)
        if source:
            # Create first version
            self._vm.handle_save_as(file_path, folder_id)
            self._tray.show_message(
                "检测到新文件",
                f"新文件 {os.path.basename(file_path)} 可能从 {source['relative_path']} 另存而来。"
                f"可在主窗口中关联历史。",
            )
        else:
            self._vm.create_version(file_path, folder_id)
        self._window.refresh()

    def _on_file_deleted(self, file_path: str):
        folder_id = self._find_folder_id_for_path(file_path)
        if folder_id is None:
            return
        relative_path = os.path.basename(file_path)
        file_rec = self._db.find_file(folder_id, relative_path)
        if file_rec:
            self._db.deactivate_file(file_rec["id"])
            self._window.refresh()

    def _quit(self):
        self._monitor.stop_all()
        self._tray.hide()
        self._db.close()
        self._app.quit()

    def run(self):
        self._tray.show()
        self._window.show()
        return self._app.exec()


def main():
    app = DocHistoryApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
