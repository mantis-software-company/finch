import os
import time
from queue import Queue
from threading import Thread
from typing import List, Dict, Optional
from dataclasses import dataclass

from PyQt5.QtCore import QObject, pyqtSignal, QMutex, Qt, QThread
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QProgressBar, 
                            QLabel, QPushButton, QScrollArea, QWidget)

from finch.common import s3_session, StringUtils, center_window
from finch.error import show_error_dialog

@dataclass
class S3DownloadItem:
    bucket_name: str
    key: str
    destination: str
    filename: str
    total_size: Optional[int] = None
    downloaded: int = 0
    status: str = 'pending'  # pending, downloading, completed, failed
    start_time: float = 0.0
    last_update_time: float = 0.0
    last_downloaded: int = 0
    speed: float = 0.0  # bytes per second
    
    def __post_init__(self):
        # Create a unique filename that includes path structure
        base_name = os.path.basename(self.key)
        name, ext = os.path.splitext(base_name)
        
        if '/' in self.key:
            # Use bucket and path for uniqueness, but keep the extension proper
            path_hash = self.key.replace('/', '_').rsplit('.', 1)[0]
            self.filename = f"{self.bucket_name}_{path_hash}{ext}"
        else:
            self.filename = f"{self.bucket_name}_{name}{ext}"

class MultiS3Downloader(QObject):
    progress_updated = pyqtSignal(str, int, float)  # filename, percent, speed
    download_completed = pyqtSignal(str)  # filename
    download_failed = pyqtSignal(str, str)  # filename, error message

    def __init__(self, max_workers: int = 3):
        super().__init__()
        self.download_queue = Queue()
        self.downloads: Dict[str, S3DownloadItem] = {}
        self.max_workers = max_workers
        self.workers: List[Thread] = []
        self.cleanup_mutex = QMutex()
        self.is_cancelled = False

    def add_download(self, bucket_name: str, key: str, destination: str) -> str:
        """Add a download to the queue"""
        download_item = S3DownloadItem(
            bucket_name=bucket_name,
            key=key,
            destination=destination,
            filename=os.path.basename(key)  # Initial filename
        )
        
        # Get file size
        try:
            download_item.total_size = int(
                s3_session.resource.meta.client.head_object(
                    Bucket=bucket_name, 
                    Key=key
                )['ContentLength']
            )
        except Exception as e:
            self.download_failed.emit(download_item.filename, str(e))
            return None

        # Store with unique ID
        self.downloads[download_item.filename] = download_item
        self.download_queue.put(download_item)
        return download_item.filename

    def start_downloads(self):
        """Start the download workers"""
        for _ in range(self.max_workers):
            worker = Thread(target=self._download_worker, daemon=True)
            worker.start()
            self.workers.append(worker)

    def _download_worker(self):
        """Worker thread to process downloads"""
        while True:
            try:
                download_item = self.download_queue.get()
                if download_item is None:
                    break

                self._process_download(download_item)
                self.download_queue.task_done()
            except Exception as e:
                if download_item:
                    self.download_failed.emit(download_item.filename, str(e))
                print(f"Error in download worker: {e}")

    def cancel(self):
        """Cancel all downloads"""
        self.is_cancelled = True
        # Clear the queue
        while not self.download_queue.empty():
            try:
                self.download_queue.get_nowait()
            except:
                pass
        # Mark remaining downloads as cancelled
        for item in self.downloads.values():
            if item.status == 'pending' or item.status == 'downloading':
                item.status = 'cancelled'
                self.download_failed.emit(item.filename, "Download cancelled")

    def _process_download(self, item: S3DownloadItem):
        """Process a single download"""
        try:
            if self.is_cancelled:
                return

            item.status = 'downloading'
            item.start_time = time.time()
            item.last_update_time = item.start_time
            os.makedirs(item.destination, exist_ok=True)
            file_path = os.path.join(item.destination, item.filename)
            temp_file_path = f"{file_path}.part"

            def update_progress(bytes_amount):
                if self.is_cancelled:
                    raise InterruptedError("Download cancelled")
                    
                item.downloaded += bytes_amount
                current_time = time.time()
                time_diff = current_time - item.last_update_time
                
                # Update speed every 0.5 seconds
                if time_diff >= 0.5:
                    bytes_diff = item.downloaded - item.last_downloaded
                    item.speed = bytes_diff / time_diff
                    item.last_downloaded = item.downloaded
                    item.last_update_time = current_time
                
                if item.total_size:
                    percent = int((item.downloaded / item.total_size) * 100)
                    self.progress_updated.emit(item.filename, percent, item.speed)

            with open(temp_file_path, 'wb') as f:
                s3_session.resource.meta.client.download_fileobj(
                    item.bucket_name,
                    item.key,
                    f,
                    Callback=update_progress
                )

            if not self.is_cancelled:
                # Only rename the file if download wasn't cancelled
                os.replace(temp_file_path, file_path)
                item.status = 'completed'
                self.download_completed.emit(item.filename)
            else:
                # Clean up partial download
                try:
                    os.remove(temp_file_path)
                except:
                    pass

        except InterruptedError:
            item.status = 'cancelled'
            try:
                os.remove(temp_file_path)
            except:
                pass
            self.download_failed.emit(item.filename, "Download cancelled")
        except Exception as e:
            item.status = 'failed'
            try:
                os.remove(temp_file_path)
            except:
                pass
            self.download_failed.emit(item.filename, str(e))
            show_error_dialog(e, show_traceback=True)

    def cleanup(self):
        """Cleanup resources"""
        self.cleanup_mutex.lock()
        self.cancel()  # Cancel any ongoing downloads
        for _ in self.workers:
            self.download_queue.put(None)
        for worker in self.workers:
            worker.join()
        self.cleanup_mutex.unlock()

class DownloadProgressWidget(QWidget):
    def __init__(self, filename: str, full_path: str):
        super().__init__()
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 10)
        self.setLayout(self.layout)
        
        # Show the actual file path in the label
        self.label = QLabel(full_path)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.progress_bar)
    
    def update_progress(self, percent: int, speed: float = 0):
        speed_str = f" - {StringUtils.format_size(speed)}/s" if speed > 0 else ""
        self.label.setText(f"{self.label.text().split('...')[0]}... {percent}%{speed_str}")
        self.progress_bar.setValue(percent)

    def mark_cancelled(self):
        self.label.setText(f"{self.label.text().split('...')[0]} - Cancelled")
        self.progress_bar.setEnabled(False)

class CleanupThread(QThread):
    def __init__(self, downloader):
        super().__init__()
        self.downloader = downloader

    def run(self):
        self.downloader.cleanup()

class MultiDownloadProgressDialog(QDialog):
    def __init__(self, file_list: List[tuple[str, str]], local_file_path: str):
        """
        Initialize multi-file download dialog
        
        Args:
            file_list: List of tuples containing (bucket_name, key)
            local_file_path: Local destination path
        """
        super().__init__()
        self.setWindowTitle(f"Downloading {len(file_list)} files...")
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)
        center_window(self)
        
        # Main layout
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Scroll area for progress bars
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Container for progress bars
        self.progress_container = QWidget()
        self.progress_layout = QVBoxLayout()
        self.progress_container.setLayout(self.progress_layout)
        scroll.setWidget(self.progress_container)
        
        # Status label
        self.status_label = QLabel("Initializing downloads...")
        
        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.handle_cancel)
        
        # Add widgets to main layout
        layout.addWidget(self.status_label)
        layout.addWidget(scroll)
        layout.addWidget(self.cancel_button)
        
        # Initialize downloader
        self.downloader = MultiS3Downloader()
        self.downloader.progress_updated.connect(self._update_progress)
        self.downloader.download_completed.connect(self._handle_completion)
        self.downloader.download_failed.connect(self._handle_failure)
        
        self.total_files = len(file_list)
        self.completed_files = 0
        self.progress_widgets: Dict[str, DownloadProgressWidget] = {}
        
        # Create progress bars for each file
        for bucket_name, key in file_list:
            # Add download to queue and get the filename that will be used
            filename = self.downloader.add_download(bucket_name, key, local_file_path)
            if filename:  # Only create widget if download was added successfully
                # Show the full path in the UI but use the unique filename for tracking
                display_path = f"{bucket_name}/{key}"
                progress_widget = DownloadProgressWidget(filename, display_path)
                self.progress_widgets[filename] = progress_widget
                self.progress_layout.addWidget(progress_widget)
        
        # Start downloads
        self.downloader.start_downloads()

        # Add cleanup thread
        self.cleanup_thread = None
        
    def _update_progress(self, filename: str, percent: int, speed: float):
        if filename in self.progress_widgets:
            self.progress_widgets[filename].update_progress(percent, speed)
            self.status_label.setText(f"Downloading files... ({self.completed_files}/{self.total_files} completed)")

    def _handle_completion(self, filename: str):
        self.completed_files += 1
        if filename in self.progress_widgets:
            self.progress_widgets[filename].label.setText(
                f"{filename} - Completed"
            )
        
        if self.completed_files == self.total_files:
            self.status_label.setText("All downloads completed!")
            self.cancel_button.setText("Close")
        else:
            self.status_label.setText(f"Downloading files... ({self.completed_files}/{self.total_files} completed)")

    def _handle_failure(self, filename: str, error: str):
        if filename in self.progress_widgets:
            if error == "Download cancelled":
                self.progress_widgets[filename].mark_cancelled()
            else:
                self.progress_widgets[filename].label.setText(
                    f"{filename} - Failed: {error}"
                )
                show_error_dialog(f"Failed to download {filename}: {error}")

    def handle_cancel(self):
        """Handle cancel button click"""
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Canceling...")
        self.status_label.setText("Canceling downloads...")
        
        # Cancel downloads first
        self.downloader.cancel()
        
        # Then start cleanup in separate thread
        self.cleanup_thread = CleanupThread(self.downloader)
        self.cleanup_thread.finished.connect(self.close)
        self.cleanup_thread.start()

    def cleanup(self):
        """Cleanup resources"""
        if not self.cleanup_thread:
            self.handle_cancel()
        else:
            self.accept()

    def closeEvent(self, event):
        """Handle dialog close"""
        if not self.cleanup_thread:
            self.handle_cancel()
            event.ignore()
        else:
            event.accept()

