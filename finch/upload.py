import os

from PyQt5.QtCore import QObject, pyqtSignal, QThread, QMutex
from PyQt5.QtWidgets import QProgressDialog

from finch.common import s3_session


class S3Uploader(QObject):
    progress_updated = pyqtSignal(int)

    def __init__(self, file_path, bucket_name, folder):
        super().__init__()
        self.file_path = file_path
        self.bucket_name = bucket_name
        self.folder = folder
        self.uploaded_size = 0

    def run(self):
        file_name = self.file_path.split('/')[-1]
        total_size = os.path.getsize(self.file_path)
        if self.folder:
            s3_path = f"{self.folder}/{file_name}"
        else:
            s3_path = file_name
        with open(self.file_path, 'rb') as f:
            s3_session.resource.meta.client.upload_fileobj(f, self.bucket_name, s3_path,
                                                           Callback=lambda bytes_amount: self.update_progress(
                                                               bytes_amount, total_size))

    def update_progress(self, bytes_amount, total_size):
        self.uploaded_size += bytes_amount
        percent = int((self.uploaded_size / total_size) * 100)
        self.progress_updated.emit(percent)


class UploadDialog(QProgressDialog):
    def __init__(self, file_path, bucket_name, folder=None):
        super().__init__(f"Uploading file {os.path.basename(file_path)}...", "Cancel", 0, 100)
        if folder:
            folder = folder[:-1]
        self.uploader_thread = QThread(parent=self)
        self.uploader = S3Uploader(file_path, bucket_name, folder)
        self.uploader.moveToThread(self.uploader_thread)
        self.uploader.progress_updated.connect(self.setValue)
        self.uploader_thread.started.connect(self.uploader.run)
        self.uploader_thread.start()
        self.cleanup_mutex = QMutex()

    def show(self):
        self.uploader_thread.start()
        super().show()

    def cleanup(self):
        self.cleanup_mutex.lock()
        self.uploader_thread.quit()
        self.uploader_thread.wait()
        self.cleanup_mutex.unlock()
        self.close()
