import json
import os
from typing import List

import keyring
from PyQt5.QtCore import QAbstractTableModel, Qt, pyqtSignal, QItemSelectionModel
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget, QGridLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, \
    QTableView, QToolBar, QAction, QBoxLayout, QAbstractItemView, QHeaderView, QItemDelegate, QApplication, QStyle, \
    QStyledItemDelegate
from slugify import slugify

from finch.common import center_window, CONFIG_PATH, resource_path
from finch.error import show_error_dialog


class CredentialsManager:
    def __init__(self):
        with open(os.path.join(CONFIG_PATH, "credentials.json"), "r") as credential_file:
            try:
                self.credentials = json.loads(credential_file.read())
            except json.JSONDecodeError:
                self.credentials = []

    def append_credentials_file(self, cred_info):
        with open(os.path.join(CONFIG_PATH, "credentials.json"), "w+") as credential_file:
            self.credentials.append(cred_info)
            credential_file.write(json.dumps(self.credentials))

    def get_credential(self, name):
        cred_list = list(filter(lambda x: x['name'] == name, self.credentials))
        return cred_list[0] if len(cred_list) > 0 else []

    def get_credentials(self):
        return self.credentials

    def set_credentials(self, credentials):
        with open(os.path.join(CONFIG_PATH, "credentials.json"), "w+") as credential_file:
            credential_file.write(json.dumps(credentials))

    def list_credentials_names(self):
        return sorted([credential["name"] for credential in self.credentials])


class TempCredentialsData:
    def __init__(self):
        self.credentials_data = CredentialsManager().get_credentials()
        self._column_map = {"name": "Credential Name", "endpoint": "Service Endpoint", "access_key": "Access Key",
                            "secret_key": "Secret Key", "region": "Region"}
        self._data = []
        for cdata in self.credentials_data:
            d = {}
            for field in cdata:
                d[self._column_map[field]] = cdata[field]
                if field == "access_key":
                    d["Secret Key"] = "xxx"
            self._data.append(d)
        self._deleted_credentials = []

    def get_data(self) -> List[dict]:
        return self._data

    def get_value(self, row: int, col: int) -> str:
        if self._data:
            return self._data[row][self.get_columns()[col]]

    def set_value(self, row: int, col: int, data: str):
        self._data[row][self.get_columns()[col]] = data

    def get_columns(self):
        return list(self._column_map.values())

    def insert_row(self):
        d = {"Credential Name": "", "Service Endpoint": "https://s3.amazonaws.com", "Access Key": "", "Secret Key": "",
             "Region": "us-east-1"}
        self._data.append(d)

    def delete_row(self, index):
        d = self._data.pop(index)
        self._deleted_credentials.append(d)

    def persist_data(self):
        credentials_data = []
        inverted_map = {}
        for key in list(self._column_map.keys()):
            inverted_map[self._column_map[key]] = key

        for data in self._data:
            d = {}
            for field in data:
                if field == "Secret Key":
                    if data["Secret Key"] != 'xxx':
                        keyring.set_password(f'{slugify(data["Credential Name"])}@finch', data["Access Key"],
                                             data["Secret Key"])
                else:
                    d[inverted_map[field]] = data[field]
            credentials_data.append(d)

        CredentialsManager().set_credentials(credentials_data)

        self._deleted_credentials = []
        for credential in self._deleted_credentials:
            try:
                keyring.delete_password(f'{slugify(credential["Credential Name"])}@finch', credential["Access Key"])
            except keyring.errors.PasswordDeleteError as e:
                show_error_dialog('Keyring deletion error')


class CredentialsModel(QAbstractTableModel):

    def __init__(self, model, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self._model = model

    def rowCount(self, parent=None):
        return len(self._model.get_data())

    def columnCount(self, parent=None):
        return len(self._model.get_columns())

    def flags(self, index):
        if index.column() != 0:
            return Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable
        else:
            if index.data():
                return Qt.ItemIsEnabled | Qt.ItemIsSelectable
            else:
                return Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            if role == Qt.DisplayRole:
                return self._model.get_value(index.row(), index.column())
        return None

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._model.get_columns()[col]
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if value and index.column() == 0 and self.hasDuplicate(value):
            show_error_dialog("Credential name already exist")
        else:
            if value:
                self._model.set_value(index.row(), index.column(), value)
                self.dataChanged.emit(index, index, (Qt.DisplayRole,))
        return True

    def hasDuplicate(self, value):
        value = slugify(value)
        for i in range(self.rowCount()):
            if slugify(self.index(i, 0).data()) == value:
                return True

    def validateData(self):
        for i in range(self.rowCount()):
            for j in range(self.columnCount()):
                if self.index(i, j).data().strip() == '':
                    raise ValueError(f"Field {self._model.get_columns()[j]} cannot be empty")


class TableViewEditorDelegate(QItemDelegate):

    def setEditorData(self, editor, index):
        editor.setAutoFillBackground(True)
        editor.setText(index.data())


class PasswordDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)

        style = option.widget.style() or QApplication.style()
        hint = style.styleHint(QStyle.SH_LineEdit_PasswordCharacter)
        if len(index.data()) > 0:
            option.text = chr(hint) * 6


class ManageCredentialsWindow(QWidget):
    window_closed = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.credentials_manager = CredentialsManager()
        self.temp_credentials_data = TempCredentialsData()

        self.setWindowTitle("Manage Credentials")
        self.resize(700, 700)
        center_window(self)

        self.tool_layout = QBoxLayout(QBoxLayout.TopToBottom, self)
        self.tool_layout.setContentsMargins(0, 0, 0, 0)
        self.credential_toolbar = QToolBar("Credential")
        self.credential_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        add_row_action = QAction(self)
        add_row_action.setText("&Create Credential")
        add_row_action.setIcon(QIcon(resource_path('img/plus.svg')))
        add_row_action.triggered.connect(self.add_row)

        self.delete_row_action = QAction(self)
        self.delete_row_action.setText("&Delete Credential")
        self.delete_row_action.setIcon(QIcon(resource_path('img/trash.svg')))
        self.delete_row_action.triggered.connect(self.delete_row)

        # save_action = QAction(self)
        # save_action.setText("&Save Credentials")
        # save_action.setIcon(QtGui.QIcon.fromTheme("media-floppy-symbolic"))
        # save_action.triggered.connect(self.save_credentials)

        self.credential_toolbar.addAction(add_row_action)
        # self.credential_toolbar.addAction(save_action)

        self.table_data = QTableView()
        self.table_data.setModel(CredentialsModel(self.temp_credentials_data))
        self.selection = self.table_data.selectionModel()
        self.selection.selectionChanged.connect(self.handleSelectionChanged)
        self.table_data.model().layoutChanged.connect(self.handleTableLayoutChanged)
        self.table_data.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_data.setSelectionMode(QAbstractItemView.SingleSelection)
        header = self.table_data.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_data.setStyleSheet("""
        QTableView::item{
            padding: 5px 5px 5px 5px;
        }
        """)

        table_view_editor_delegate = TableViewEditorDelegate(self.table_data)
        self.table_data.setItemDelegate(table_view_editor_delegate)

        self.password_delegate = PasswordDelegate()
        self.table_data.setItemDelegateForColumn(3, self.password_delegate)

        layout = QVBoxLayout()
        self.tool_layout.addWidget(self.table_data)
        self.tool_layout.setMenuBar(self.credential_toolbar)
        self.tool_layout.addLayout(layout)

    def add_row(self):
        self.temp_credentials_data.insert_row()
        model = self.table_data.model()
        model.insertRow(model.rowCount())
        model.itemData(model.index(model.rowCount() - 1, 0))
        self.table_data.model().layoutChanged.emit()
        self.table_data.selectRow(model.rowCount() - 1)
        self.credential_toolbar.addAction(self.delete_row_action)

    def delete_row(self):
        indexes = self.table_data.selectedIndexes()
        row = indexes[0].row()
        self.temp_credentials_data.delete_row(row)
        self.table_data.model().layoutChanged.emit()
        self.credential_toolbar.removeAction(self.delete_row_action)

    def save_credentials(self):
        if self.table_data.model().rowCount() > 0:
            self.table_data.model().validateData()
        self.temp_credentials_data.persist_data()
        self.table_data.model().layoutChanged.emit()

    def handleSelectionChanged(self, selected, deselected):
        self.credential_toolbar.addAction(self.delete_row_action)

    def handleTableLayoutChanged(self):
        try:
            self.save_credentials()
        except Exception as e:
            print(e)
            pass
        if self.table_data.model().rowCount() == 0:
            self.credential_toolbar.removeAction(self.delete_row_action)

    def closeEvent(self, event):
        try:
            self.save_credentials()
            self.window_closed.emit()
            event.accept()
        except ValueError as e:
            show_error_dialog(f"Validation error: {e}")
            event.ignore()
        except Exception as e:
            show_error_dialog(f"Unknown error: {e}")
            event.ignore()