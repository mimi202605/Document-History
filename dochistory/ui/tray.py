"""System tray icon and context menu."""
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QPixmap
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu


class SystemTray(QObject):
    """System tray with monitor control and window management."""

    show_window_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    pause_monitoring_requested = pyqtSignal()
    resume_monitoring_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tray = QSystemTrayIcon(parent)
        self._setup_icon()
        self._setup_menu()
        self._monitoring_paused = False

    def _setup_icon(self):
        """Create a simple placeholder icon."""
        pixmap = QPixmap(16, 16)
        pixmap.fill()
        self._tray.setIcon(QIcon(pixmap))
        self._tray.setToolTip("DocHistory - 文档版本控制")

    def _setup_menu(self):
        menu = QMenu()

        self._show_action = QAction("显示主窗口", menu)
        self._show_action.triggered.connect(self.show_window_requested.emit)
        menu.addAction(self._show_action)

        menu.addSeparator()

        self._pause_action = QAction("暂停监控", menu)
        self._pause_action.triggered.connect(self._toggle_pause)
        menu.addAction(self._pause_action)

        menu.addSeparator()

        self._quit_action = QAction("退出", menu)
        self._quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(self._quit_action)

        self._tray.setContextMenu(menu)

    def _toggle_pause(self):
        if self._monitoring_paused:
            self._monitoring_paused = False
            self._pause_action.setText("暂停监控")
            self.resume_monitoring_requested.emit()
        else:
            self._monitoring_paused = True
            self._pause_action.setText("恢复监控")
            self.pause_monitoring_requested.emit()

    def show(self):
        self._tray.show()

    def hide(self):
        self._tray.hide()

    def show_message(self, title: str, message: str):
        """Show a tray notification."""
        self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 3000)
