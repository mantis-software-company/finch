import json

from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtWidgets import QTreeWidgetItem

from finch.common import s3_session, ObjectType
from finch.common import StringUtils


class S3FileListFetchThread(QThread):
    file_list_fetched = pyqtSignal(str, QTreeWidgetItem)

    def __init__(self, bucket_or_folder, item):
        super().__init__()
        self.bucket = item.data(4, Qt.UserRole) if item.data(4, Qt.UserRole) else bucket_or_folder
        self.item = item
        self.folder = "" if not item.data(4, Qt.UserRole) else bucket_or_folder

    def get_files(self, bucket_name, prefix=""):
        resp = s3_session.resource.meta.client.list_objects(Bucket=bucket_name, Prefix=prefix, Delimiter="/")
        if 'CommonPrefixes' in resp:
            files = []
            folders = [{"name": x['Prefix'],  "file_size": StringUtils.format_size(0), "type": ObjectType.FOLDER, "last_modified": None, "bucket": bucket_name}
                       for x in
                       resp['CommonPrefixes']]
            if 'Contents' in resp:
                files = [{"name": f["Key"], "type": ObjectType.FILE,
                          "file_size": StringUtils.format_size(f['Size']),
                          "last_modified": StringUtils.format_datetime(f["LastModified"]),
                          "bucket": bucket_name}
                         for f in
                         resp["Contents"]]

            return folders + files
        elif 'Contents' in resp:
            return [{"name": f["Key"], "type": ObjectType.FILE,
                     "file_size": StringUtils.format_size(f['Size']),
                     "last_modified": StringUtils.format_datetime(f["LastModified"]),
                     "bucket": bucket_name}
                    for f in
                    resp["Contents"]]
        else:
            return []

    def run(self):
        _objs = self.get_files(bucket_name=self.bucket, prefix=self.folder)
        for _obj in _objs:
            if _obj["type"] == ObjectType.FILE:
                if _obj["name"][-1] != "/":
                    self.file_list_fetched.emit(json.dumps(_obj), self.item)
            else:
                self.file_list_fetched.emit(json.dumps(_obj), self.item)
