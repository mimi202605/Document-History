"""File system monitor using watchdog with debounce."""
import os
import threading

from PyQt6.QtCore import QObject, pyqtSignal
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from dochistory.utils.file_utils import is_supported_file, is_temp_file


class _DebouncedHandler(FileSystemEventHandler):
    """Watchdog handler with debounce for on_modified."""

    def __init__(self, monitor: "FileMonitor"):
        self._monitor = monitor
        self._timers: dict[str, threading.Timer] = {}
        self._timers_lock = threading.Lock()
        self._delete_timers: dict[str, threading.Timer] = {}
        self._delete_timers_lock = threading.Lock()

    def on_modified(self, event):
        if event.is_directory:
            return
        file_path = event.src_path
        if is_temp_file(file_path) or not is_supported_file(file_path):
            return
        self._debounce(file_path)

    def on_created(self, event):
        if event.is_directory:
            return
        file_path = event.src_path
        if is_temp_file(file_path) or not is_supported_file(file_path):
            return
        if self._monitor._paused:
            return
        self._monitor.file_created.emit(file_path)
        # Also trigger save for new files
        self._debounce(file_path)

    def on_moved(self, event):
        src_path = event.src_path
        dest_path = event.dest_path
        if is_temp_file(dest_path):
            return
        if not is_supported_file(dest_path):
            return
        if self._monitor._paused:
            return
        # Word/WPS atomic save: temp file renamed to original filename.
        # Treat as a save event for the destination, not a rename.
        if is_temp_file(src_path):
            self._debounce(dest_path)
            return
        self._monitor.file_moved.emit(src_path, dest_path)

    def on_deleted(self, event):
        if event.is_directory:
            return
        file_path = event.src_path
        if is_temp_file(file_path) or not is_supported_file(file_path):
            return
        if self._monitor._paused:
            return
        # Debounce deletion: Word's atomic save deletes the original then
        # recreates it via rename. If the file reappears within the window,
        # cancel the deletion notification.
        self._debounce_delete(file_path)

    def _debounce(self, file_path: str):
        """Debounce: 500ms window, only last modification triggers."""
        with self._timers_lock:
            if file_path in self._timers:
                self._timers[file_path].cancel()
            timer = threading.Timer(0.5, self._emit_save, args=[file_path])
            self._timers[file_path] = timer
        timer.start()

    def _emit_save(self, file_path: str):
        with self._timers_lock:
            self._timers.pop(file_path, None)
        if self._monitor._paused:
            return
        self._monitor.file_saved.emit(file_path)

    def _debounce_delete(self, file_path: str):
        """Debounce deletion: wait 1s, cancel if file reappears (atomic save)."""
        with self._delete_timers_lock:
            if file_path in self._delete_timers:
                self._delete_timers[file_path].cancel()
            timer = threading.Timer(1.0, self._emit_delete, args=[file_path])
            self._delete_timers[file_path] = timer
        timer.start()

    def _emit_delete(self, file_path: str):
        with self._delete_timers_lock:
            self._delete_timers.pop(file_path, None)
        if self._monitor._paused:
            return
        # Only emit if file is truly gone (not recreated by atomic save)
        if os.path.exists(file_path):
            return
        self._monitor.file_deleted.emit(file_path)


    def cancel_all(self):
        with self._timers_lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()
        with self._delete_timers_lock:
            for timer in self._delete_timers.values():
                timer.cancel()
            self._delete_timers.clear()


class FileMonitor(QObject):
    """Monitors folders for document changes with debounce."""

    file_saved = pyqtSignal(str)
    file_moved = pyqtSignal(str, str)
    file_created = pyqtSignal(str)
    file_deleted = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._observers: dict[str, Observer] = {}
        self._handlers: dict[str, _DebouncedHandler] = {}
        self._paused = False
        self._lock = threading.Lock()

    def add_watch(self, path: str):
        """Start monitoring a folder."""
        with self._lock:
            if path in self._observers:
                return
            handler = _DebouncedHandler(self)
            observer = Observer()
            observer.schedule(handler, path, recursive=True)
            observer.start()
            self._observers[path] = observer
            self._handlers[path] = handler

    def remove_watch(self, path: str):
        """Stop monitoring a folder."""
        with self._lock:
            if path not in self._observers:
                return
            self._handlers[path].cancel_all()
            self._observers[path].stop()
            del self._observers[path]
            del self._handlers[path]

    def pause(self):
        """Pause all monitoring (events ignored)."""
        self._paused = True

    def resume(self):
        """Resume monitoring."""
        self._paused = False

    def is_paused(self) -> bool:
        return self._paused

    def stop_all(self):
        """Stop all observers and clean up."""
        with self._lock:
            for handler in self._handlers.values():
                handler.cancel_all()
            for observer in self._observers.values():
                observer.stop()
                observer.join(timeout=5)
            self._observers.clear()
            self._handlers.clear()
