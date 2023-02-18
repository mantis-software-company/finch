import os.path

from PyQt5.QtCore import QObject, pyqtSignal, QThread, QMutex
from PyQt5.QtWidgets import QProgressDialog

from finch.common import s3_session
from finch.error import show_error_dialog


class S3Downloader(QObject):
    progress_updated = pyqtSignal(int)

    def __init__(self, bucket_name, key, local_file_path):
        super().__init__()
        self.bucket_name = bucket_name
        self.key = key
        self.local_file_path = os.path.join(local_file_path, os.path.basename(key))
        self.total_bytes = int(
            s3_session.resource.meta.client.head_object(Bucket=self.bucket_name, Key=self.key)['ContentLength'])
        self.downloaded_size = 0

    def run(self):
        try:
            with open(self.local_file_path, 'wb') as f:
                s3_session.resource.meta.client.download_fileobj(self.bucket_name, self.key, f,
                                                                 Callback=self.update_progress)
        except Exception as e:
            show_error_dialog(str(e))

    def update_progress(self, bytes_downloaded):
        self.downloaded_size += bytes_downloaded
        percent = int(self.downloaded_size / self.total_bytes * 100)
        self.progress_updated.emit(percent)


class DownloadProgressDialog(QProgressDialog):
    def __init__(self, bucket_name, key, local_file_path, ):
        super().__init__(f"Downloading file {os.path.basename(key)}...", "Cancel", 0, 100)
        self.downloader_thread = QThread(parent=self)
        self.downloader = S3Downloader(bucket_name, key, local_file_path)
        self.downloader.moveToThread(self.downloader_thread)
        self.downloader.progress_updated.connect(self.setValue)
        self.downloader_thread.started.connect(self.downloader.run)
        self.downloader_thread.start()
        self.cleanup_mutex = QMutex()

    def show(self):
        self.downloader_thread.start()
        super().show()

    def cleanup(self):
        self.cleanup_mutex.lock()
        self.downloader_thread.quit()
        self.downloader_thread.wait()
        self.cleanup_mutex.unlock()
        self.close()
