import functools
import json
import os
import sys
from pathlib import Path

import boto3
import keyring
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QStyle, \
    QAction, QComboBox, QMenu, QInputDialog, \
    QMessageBox, QFileDialog, QSizePolicy
from slugify import slugify

from finch.about import AboutWindow
from finch.acl import ACLWindow
from finch.common import ObjectType, s3_session, apply_theme, center_window, CONFIG_PATH, StringUtils, resource_path, \
    TimeIntervalInputDialog
from finch.cors import CORSWindow
from finch.credentials import CredentialsManager, ManageCredentialsWindow
from finch.download import MultiDownloadProgressDialog
from finch.error import show_error_dialog
from finch.filelist import S3FileListFetchThread
from finch.upload import UploadDialog
from finch.widgets.search import SearchWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.credentials_manager = None
        self.credential_selector = None
        self.manage_credential_window = None
        self.download_dialog = None
        self.create_credential_window = None
        self.file_toolbar = None
        self.about_window = None
        self.upload_dialog = None

        self.credential_toolbar = self.addToolBar("Credentials")
        self.credential_toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)

        edit_credential_action = QAction(self)
        edit_credential_action.setText("&Manage Credentials")
        edit_credential_action.setIcon(QIcon(resource_path('img/credentials.svg')))
        edit_credential_action.triggered.connect(self.show_manage_credential_window)

        self.credential_toolbar.addAction(edit_credential_action)

        self.about_toolbar = self.addToolBar("About")
        self.about_toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        empty = QWidget()
        empty.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        show_about_action = QAction(self)
        show_about_action.setText("&About")
        show_about_action.setIcon(QIcon(resource_path(resource_path('img/about.svg'))))
        show_about_action.triggered.connect(self.open_about_window)
        self.about_toolbar.addWidget(empty)
        self.about_toolbar.addAction(show_about_action)

        self.s3_file_list_fetch_thread = None
        self.tree_widget = None
        self.icon_type = {
            ObjectType.FILE: self.style().standardIcon(QStyle.SP_FileIcon),
            ObjectType.FOLDER: self.style().standardIcon(QStyle.SP_DirIcon),
            ObjectType.BUCKET: self.style().standardIcon(QStyle.SP_DirIcon),
        }

        self.resize(1200, 700)
        self.setWindowTitle("Finch S3 Client")

        self.widget = QWidget()
        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignTop)
        self.widget.setLayout(self.layout)
        self.tree_widget_wrapper = QWidget()
        self.tree_widget_wrapper_lay = QVBoxLayout()
        self.tree_widget_wrapper.setLayout(self.tree_widget_wrapper_lay)
        self.fill_credentials()
        self.layout.addWidget(self.tree_widget_wrapper)
        self.setCentralWidget(self.widget)

        center_window(self)

    def fill_credentials(self, selected_index=0):
        """ Fills/Refreshes credential names in credential selector """
        self.credentials_manager = CredentialsManager()
        if self.credential_selector:
            self.layout.removeWidget(self.credential_selector)
        self.credential_selector = QComboBox()
        self.credential_selector.addItem("Select Credential", 0)
        self.credential_selector.addItems(self.credentials_manager.list_credentials_names())
        self.credential_selector.setCurrentIndex(selected_index)
        self.layout.insertWidget(0, self.credential_selector)
        self.credential_selector.currentIndexChanged.connect(self.show_s3_files)
        self.refresh_ui()

    def handle_selection(self, selected, deselected):
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            # No selection - disable relevant actions
            for idx, action in enumerate(self.file_toolbar.actions()):
                if idx in [0, 2, 3]:
                    action.setDisabled(True)
                else:
                    action.setDisabled(False)
            return

        # Check if all selected items are files
        all_files = all(item.text(1) == ObjectType.FILE for item in selected_items)
        single_selection = len(selected_items) == 1
        first_type = selected_items[0].text(1)

        for idx, action in enumerate(self.file_toolbar.actions()):
            if all_files:
                # Enable download and delete for files
                if idx in [2, 3, 4]:
                    action.setDisabled(False)
                else:
                    action.setDisabled(True)
            elif single_selection and first_type in [ObjectType.BUCKET, ObjectType.FOLDER]:
                # Enable create and delete for buckets/folders
                if idx in [0, 1, 2, 4]:
                    action.setDisabled(False)
                else:
                    action.setDisabled(True)
            else:
                # Mixed selection or multiple buckets/folders
                if idx in [0, 2, 3]:
                    action.setDisabled(True)
                else:
                    action.setDisabled(False)

    def show_s3_files(self, cred_index):
        if self.credential_selector.itemData(cred_index) != 0:
            try:
                cred_name = self.credential_selector.itemText(cred_index)
                cred = self.credentials_manager.get_credential(cred_name)
                s3_session.resource = boto3.resource('s3',
                                                     endpoint_url=cred['endpoint'],
                                                     aws_access_key_id=cred['access_key'],
                                                     aws_secret_access_key=keyring.get_password(
                                                         f'{slugify(cred["name"])}@finch',
                                                         cred['access_key']
                                                     ),
                                                     region_name=cred['region']
                                                     )
                self.removeToolBar(self.about_toolbar)
                self.removeToolBar(self.file_toolbar)
                self.file_toolbar = self.addToolBar("File")
                self.tree_widget_wrapper_lay.removeWidget(self.tree_widget)
                upload_file_action = QAction(self)
                upload_file_action.setText("&Upload")
                upload_file_action.setIcon(QIcon(resource_path('img/upload.svg')))
                upload_file_action.triggered.connect(self.upload_file)
                upload_file_action.setDisabled(True)

                create_action = QAction(self)
                create_action.setText("&Create")
                create_action.setIcon(QIcon(resource_path('img/new-folder.svg')))
                create_action.triggered.connect(self.global_create)

                delete_action = QAction(self)
                delete_action.setText("&Delete")
                delete_action.setIcon(QIcon(resource_path('img/trash.svg')))
                delete_action.triggered.connect(self.global_delete)
                delete_action.setDisabled(True)

                download_action = QAction(self)
                download_action.setText("&Download")
                download_action.setIcon(QIcon(resource_path('img/download.svg')))
                download_action.triggered.connect(self.download_files)
                download_action.setDisabled(True)

                refresh_action = QAction(self)
                refresh_action.setText("&Refresh")
                refresh_action.setIcon(QIcon(resource_path('img/refresh.svg')))
                refresh_action.triggered.connect(self.refresh_ui)

                search_action = QAction(self)
                search_action.setText("&Search")
                search_action.setIcon(QIcon(resource_path('img/search.svg')))
                search_action.triggered.connect(self.search)

                self.file_toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
                self.file_toolbar.addAction(upload_file_action)
                self.file_toolbar.addAction(create_action)
                self.file_toolbar.addAction(delete_action)
                self.file_toolbar.addAction(download_action)
                self.file_toolbar.addAction(refresh_action)
                self.file_toolbar.addAction(search_action)

                self.about_toolbar = self.addToolBar("About")
                self.about_toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
                empty = QWidget()
                empty.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                show_about_action = QAction(self)
                show_about_action.setText("&About")
                show_about_action.setIcon(QIcon(resource_path('img/about.svg')))
                show_about_action.triggered.connect(self.open_about_window)
                self.about_toolbar.addWidget(empty)
                self.about_toolbar.addAction(show_about_action)

                self.tree_widget = QTreeWidget()
                self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
                self.tree_widget.customContextMenuRequested.connect(self.open_context_menu)
                self.tree_widget.setSortingEnabled(True)
                self.tree_widget.sortByColumn(0, Qt.AscendingOrder)
                self.tree_widget.setSelectionMode(QTreeWidget.ExtendedSelection)
                header = self.tree_widget.header()
                header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
                header.setStretchLastSection(False)
                header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
                self.tree_widget.setColumnCount(4)
                self.tree_widget.setHeaderLabels(["Name", "Type", "Size", "Date"])
                self.tree_widget.itemExpanded.connect(self.add_files_to_tree)
                self.tree_widget.selectionModel().selectionChanged.connect(self.handle_selection)

                self.tree_widget_wrapper_lay.addWidget(self.tree_widget)

                self.add_buckets_to_tree()

            except Exception as e:
                show_error_dialog(e, show_traceback=True)

    def get_bucket_name_from_selected_item(self):
        """ Get bucket name data from bucket or file/folder item in treeview """
        indexes = self.tree_widget.selectedIndexes()
        if indexes:
            index = indexes[0]
            if self.tree_widget.itemFromIndex(index).data(4, Qt.UserRole):
                return self.tree_widget.itemFromIndex(index).data(4, Qt.UserRole)
            else:
                return index.data(Qt.DisplayRole)
        else:
            return None

    def get_object_key_from_selected_item(self):
        """ Get object key data from selected file/folder item in treeview """
        indexes = self.tree_widget.selectedIndexes()
        if indexes:
            index = indexes[0]
            return self.tree_widget.itemFromIndex(index).data(5, Qt.UserRole)
        else:
            return None

    # ############### Fill Treeview ############################

    def add_buckets_to_tree(self):
        """ Adds bucket items to treeview """
        try:
            buckets_obj = s3_session.resource.meta.client.list_buckets()
            buckets = [bucket for bucket in buckets_obj['Buckets']]
            for bucket in buckets:
                bucket_item = QTreeWidgetItem(self.tree_widget)
                bucket_item.setText(0, bucket['Name'])
                bucket_item.setIcon(0, self.icon_type[ObjectType.BUCKET])
                bucket_item.setText(1, ObjectType.BUCKET)
                bucket_item.setText(2, StringUtils.format_size(0))
                bucket_item.setText(3, StringUtils.format_datetime(bucket['CreationDate']))
                bucket_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
        except Exception as e:
            self.removeToolBar(self.file_toolbar)
            show_error_dialog(e, show_traceback=True)

    def add_files_to_tree(self, item):
        """ Runs `S3FileListFetchThread` """
        if item.childCount() == 0:
            bucket_or_folder = item.data(5, Qt.UserRole) if item.data(5, Qt.UserRole) else item.text(0)
            self.s3_file_list_fetch_thread = S3FileListFetchThread(bucket_or_folder, item)
            self.s3_file_list_fetch_thread.file_list_fetched.connect(self.add_file_item_to_tree)
            self.s3_file_list_fetch_thread.start()

    def add_file_item_to_tree(self, file, item):
        """ Adds file/folder items to treeview """
        file = json.loads(file)
        file_item = QTreeWidgetItem(item)
        file_item.setText(0, StringUtils.format_object_name(file["name"]))
        file_item.setIcon(0, self.icon_type[file["type"]])
        file_item.setText(1, file["type"])
        file_item.setText(2, file["file_size"])
        file_item.setText(3, file["last_modified"])
        file_item.setData(4, Qt.UserRole, file["bucket"])
        file_item.setData(5, Qt.UserRole, file["name"])
        if file["type"] == ObjectType.FOLDER:
            file_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)  # Make folders expandable

    # ############### Fill Context Menu ############################

    def open_context_menu(self, position):
        """ Initializes context menu on treeview """
        indexes = self.tree_widget.selectedIndexes()
        if indexes:
            if len(indexes) > 0:
                level = 0
                index = indexes[0]
                while index.parent().isValid():
                    index = index.parent()
                    level += 1

            menu = QMenu()
            if indexes[1].data() == ObjectType.BUCKET:
                delete_bucket_action = QAction("Delete Bucket")
                delete_bucket_action.setIcon(QIcon(resource_path('img/trash.svg')))
                delete_bucket_action.triggered.connect(self.delete_bucket)
                menu.addAction(delete_bucket_action)

                create_folder_action = QAction("Create Folder")
                create_folder_action.setIcon(QIcon(resource_path('img/new-folder.svg')))
                create_folder_action.triggered.connect(self.create_folder)
                menu.addAction(create_folder_action)

                tools_menu = menu.addMenu("Tools")
                tools_menu.setIcon(QIcon(resource_path('img/tools.svg')))

                cors_action = QAction(self)
                cors_action.setText("CORS Configurations")
                cors_action.setIcon(QIcon(resource_path('img/globe.svg')))
                cors_action.triggered.connect(self.show_cors_window)
                tools_menu.addAction(cors_action)

                acl_action = QAction(self)
                acl_action.setText("ACL Configuration")
                acl_action.setIcon(QIcon(resource_path('img/tools.svg')))
                acl_action.triggered.connect(self.show_acl_window)
                tools_menu.addAction(acl_action)

            elif indexes[1].data() == ObjectType.FOLDER:
                delete_folder_action = QAction("Delete Folder")
                delete_folder_action.setIcon(QIcon(resource_path('img/trash.svg')))
                delete_folder_action.triggered.connect(self.delete_folder)
                menu.addAction(delete_folder_action)

                create_folder_action = QAction("Create Folder")
                create_folder_action.setIcon(QIcon(resource_path('img/new-folder.svg')))
                create_folder_action.triggered.connect(self.create_folder)
                menu.addAction(create_folder_action)

            elif indexes[1].data() == ObjectType.FILE:
                download_file_action = QAction("Download File(s)")
                download_file_action.setIcon(QIcon(resource_path('img/save.svg')))
                download_file_action.triggered.connect(self.download_files)
                menu.addAction(download_file_action)

                delete_file_action = QAction("Delete File")
                delete_file_action.setIcon(QIcon(resource_path('img/trash.svg')))
                delete_file_action.triggered.connect(self.delete_file)
                menu.addAction(delete_file_action)

                tools_menu = menu.addMenu("Tools")
                tools_menu.setIcon(QIcon(resource_path('img/tools.svg')))

                presigned_url_action = QAction(self)
                presigned_url_action.setText("Get Presigned Download URL")
                presigned_url_action.setIcon(QIcon(resource_path('img/globe.svg')))
                presigned_url_action.triggered.connect(self.get_presigned_download_url)
                tools_menu.addAction(presigned_url_action)
                menu.addMenu(tools_menu)

            menu.exec_(self.tree_widget.viewport().mapToGlobal(position))

    # ############### Actions ############################

    def create_bucket(self) -> None:
        """ Create S3 Bucket """
        bucket_name, ok = QInputDialog.getText(self, 'Create Bucket', 'Please enter bucket name')
        if ok:
            try:
                s3_session.resource.create_bucket(Bucket=bucket_name)
            except Exception as e:
                show_error_dialog(e, show_traceback=True)
            self.refresh_ui()

    def create_folder(self) -> None:
        """ Create new folder in a S3 bucket or folder in any depth. """
        folder_name, ok = QInputDialog.getText(self, 'Create Folder', 'Please enter folder name')
        if ok:
            bucket_name = self.get_bucket_name_from_selected_item()
            parent_folder_name = self.get_object_key_from_selected_item()
            if parent_folder_name:
                folder_path = f"{parent_folder_name[:-1]}/{folder_name}/"
            else:
                folder_path = f"{folder_name}/"

            try:
                s3_session.resource.meta.client.put_object(Bucket=bucket_name, Body=b'',
                                                           Key=folder_path)
            except Exception as e:
                show_error_dialog(e, show_traceback=True)

            self.refresh_ui()

    def delete_bucket(self) -> None:
        """ Deletes selected S3 bucket. It deletes all objects and versions recursively before deleting the bucket."""
        bucket_name = self.get_bucket_name_from_selected_item()
        objects = s3_session.resource.meta.client.list_objects_v2(Bucket=bucket_name)
        if 'Contents' not in objects or len(objects['Contents']) == 0:
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Warning)
            dlg.setWindowTitle("Warning")
            dlg.setText("You are going to delete bucket. This this operation cannot be undone. Are you sure?")
            dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            status = dlg.exec()
            if status == QMessageBox.Yes:
                try:
                    s3_session.resource.Bucket(bucket_name).delete()
                except Exception as e:
                    show_error_dialog(e, show_traceback=True)
        else:
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Warning)
            dlg.setWindowTitle("Warning")
            dlg.setText(
                "You are going to delete non-empty bucket. All objects will deleted on this bucket. This this operation cannot be undone. Are you sure?")
            dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            status = dlg.exec()
            if status == QMessageBox.Yes:
                try:
                    bucket_versioning = s3_session.resource.BucketVersioning(bucket_name)
                    if bucket_versioning.status == 'Enabled':
                        s3_session.resource.Bucket(bucket_name).object_versions.delete()
                    else:
                        s3_session.resource.Bucket(bucket_name).objects.all().delete()
                    s3_session.resource.Bucket(bucket_name).delete()
                except Exception as e:
                    show_error_dialog(e, show_traceback=True)
            self.refresh_ui()

    def delete_folder(self) -> None:
        """ Deletes selected folder recursively """
        bucket_name = self.get_bucket_name_from_selected_item()
        folder_name = self.get_object_key_from_selected_item()
        bucket = s3_session.resource.Bucket(bucket_name)
        folder_objects = bucket.objects.filter(Prefix=folder_name)
        if list(folder_objects.limit(1)):
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Warning)
            dlg.setWindowTitle("Warning")
            dlg.setText("All objects will deleted on this folder. This this operation cannot be undone. Are you sure?")
            dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            status = dlg.exec()
            if status == QMessageBox.Yes:
                folder_objects.delete()
                self.refresh_ui()

    def delete_file(self) -> None:
        """ Deletes selected file """
        bucket_name = self.get_bucket_name_from_selected_item()
        object_key = self.get_object_key_from_selected_item()
        dlg = QMessageBox(self)
        dlg.setIcon(QMessageBox.Warning)
        dlg.setWindowTitle("Warning")
        dlg.setText("Selected file will deleted on bucket. This this operation cannot be undone. Are you sure?")
        dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        status = dlg.exec()
        if status == QMessageBox.Yes:
            s3_session.resource.Object(bucket_name, object_key).delete()
            self.refresh_ui()

    def global_create(self) -> None:
        """ Creates bucket or folder. It triggers after clicking 'Create' button in toolbox. """
        indexes = self.tree_widget.selectedIndexes()
        if len(indexes) == 0:
            self.create_bucket()
        else:
            object_type = indexes[1].data()
            if object_type == ObjectType.BUCKET:
                self.create_folder()
            elif object_type == ObjectType.FOLDER:
                self.create_folder()

    def global_delete(self) -> None:
        """ Deletes selected bucket, folder or file recursively. It triggers after clicking 'Delete' button in toolbox. """
        indexes = self.tree_widget.selectedIndexes()
        object_type = indexes[1].data()
        if object_type == ObjectType.BUCKET:
            self.delete_bucket()
        elif object_type == ObjectType.FOLDER:
            self.delete_folder()
        elif object_type == ObjectType.FILE:
            self.delete_file()

    def upload_file(self) -> None:
        """ Uploads selected files to selected bucket or folder """
        bucket_name = self.get_bucket_name_from_selected_item()
        folder_name = self.get_object_key_from_selected_item()
        file_dialog = QFileDialog()
        file_dialog.setWindowTitle("Select files to upload.")
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        if file_dialog.exec_():
            filenames = file_dialog.selectedFiles()
            for file in filenames:
                self.upload_dialog = UploadDialog(file, bucket_name, folder_name)
                self.upload_dialog.exec_()
                self.upload_dialog.cleanup()
            self.refresh_ui()


    def download_files(self) -> None:
        """Downloads multiple files to selected local folder path"""
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            return
        
        # Get all selected file keys with their bucket names
        file_list = []
        for item in selected_items:
            if item.text(1) == ObjectType.FILE:
                bucket_name = item.data(4, Qt.UserRole)
                file_key = item.data(5, Qt.UserRole)
                file_list.append((bucket_name, file_key))
        
        if not file_list:
            return
        
        # Get destination folder
        file_dialog = QFileDialog()
        file_dialog.setWindowTitle("Select folder to download")
        local_path = file_dialog.getExistingDirectory()
        if local_path:
            self.download_dialog = MultiDownloadProgressDialog(file_list, local_path)
            self.download_dialog.exec_()

    def show_manage_credential_window(self) -> None:
        """ Open credential management window """
        self.manage_credential_window = ManageCredentialsWindow()
        self.manage_credential_window.window_closed.connect(
            functools.partial(self.fill_credentials, self.credential_selector.currentIndex()))
        self.manage_credential_window.show()

    def refresh_ui(self) -> None:
        """ Refreshes the file treeview """
        self.removeToolBar(self.file_toolbar)
        self.show_s3_files(self.credential_selector.currentIndex())
        self.search_widget = SearchWidget(main_widget=self)
        if self.layout.itemAt(2):
            if isinstance(self.layout.itemAt(2).widget(), SearchWidget):
                for idx, action in enumerate(self.file_toolbar.actions()):
                    if idx in [5]:
                        action.setDisabled(True)

    def search(self):
        self.search_widget = SearchWidget(main_widget=self)
        for idx, action in enumerate(self.file_toolbar.actions()):
            if idx in [5]:
                action.setDisabled(True)
        self.layout.addWidget(self.search_widget)

    def show_cors_window(self) -> None:
        """ Open CORS configuration window """
        indexes = self.tree_widget.selectedIndexes()
        if indexes[1].data() == ObjectType.BUCKET:
            bucket_name = self.get_bucket_name_from_selected_item()
            # get bucket name and pass it to CORSWindow
            self.cors_window = CORSWindow(bucket_name=bucket_name)
            self.cors_window.show()

    def get_presigned_download_url(self):
        """ Opens a dialog to get presigned URL for a file """
        indexes = self.tree_widget.selectedIndexes()
        if indexes[1].data() == ObjectType.FILE:
            bucket_name = self.get_bucket_name_from_selected_item()
            file_key = self.get_object_key_from_selected_item()
            expires_dialog = TimeIntervalInputDialog(window_title="Expire Time ?",
                                                     default_unit=TimeIntervalInputDialog.TimeUnit.HOURS,
                                                     default_value=1,
                                                     max_seconds=604800)
            if expires_dialog.exec():
                print(expires_dialog.value)
                url = s3_session.resource.meta.client.generate_presigned_url('get_object',
                                                                         Params={'Bucket': bucket_name, 'Key': file_key},
                                                                         ExpiresIn=expires_dialog.value_as_seconds)
                QMessageBox.information(self, f"Presigned URL for {file_key}", url)

    def show_acl_window(self):
        """ Open Access Control List configuration window """
        indexes = self.tree_widget.selectedIndexes()
        if indexes[1].data() == ObjectType.BUCKET:
            bucket_name = self.get_bucket_name_from_selected_item()
            # get bucket name and pass it to ACLWindow
            # acl = s3_session.resource.meta.client.get_bucket_acl(Bucket=bucket_name)
            self.acl_window = ACLWindow(bucket_name=bucket_name)
            self.acl_window.show()

    def open_about_window(self) -> None:
        """ Open about window """
        self.about_window = AboutWindow()
        self.about_window.show()


def main():
    os.makedirs(CONFIG_PATH, exist_ok=True)
    Path(os.path.join(CONFIG_PATH, 'credentials.json')).touch()
    app = QApplication(sys.argv)
    app.setApplicationName('Finch S3 Client')
    app.setWindowIcon(QIcon(resource_path("img/icon.png")))
    apply_theme(app)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
