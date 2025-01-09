import json

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QTreeWidgetItem, QStyle
)

from finch.common import s3_session, ObjectType, StringUtils, resource_path


class SearchWidget(QWidget):
    def __init__(self, main_widget: QWidget):
        super().__init__()
        self.main_widget = main_widget
        self.icon_type = self._initialize_icons()
        self._init_ui()

    def showEvent(self, event):
        """Ensure search input gets focus when the widget is shown."""
        super().showEvent(event)
        self.search_input.setFocus()

    def close(self):
        super().close()
        for idx, action in enumerate(self.main_widget.file_toolbar.actions()):
            if idx in [5]:
                action.setDisabled(False)
        self.main_widget.layout.removeWidget(self)


    def _initialize_icons(self):
        """Initialize icon mapping for different object types."""
        style = self.style()
        return {
            ObjectType.FILE: style.standardIcon(QStyle.SP_FileIcon),
            ObjectType.FOLDER: style.standardIcon(QStyle.SP_DirIcon),
            ObjectType.BUCKET: style.standardIcon(QStyle.SP_DirIcon),
        }

    def _init_ui(self):
        """Initialize UI components."""
        layout = QHBoxLayout()
        self.search_input = QLineEdit(placeholderText="Search")
        self.search_input.returnPressed.connect(self._on_search)
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self._on_search)
        self.close_button = QPushButton("")
        self.close_button.setIcon(QIcon(resource_path('img/close.svg')))
        self.close_button.setFlat(True)
        self.close_button.setStyleSheet("QPushButton { background-color: transparent }")
        self.close_button.clicked.connect(self.close)

        layout.addWidget(self.search_input)
        layout.addWidget(self.search_button)
        layout.addWidget(self.close_button)
        self.setLayout(layout)

    def _on_search(self):
        """Handle search button click."""
        search_term = self.search_input.text()
        self.main_widget.tree_widget.clear()
        self._search_and_populate(search_term)

        for i in range(self.main_widget.tree_widget.topLevelItemCount()):
            self._expand_and_select(self.main_widget.tree_widget.topLevelItem(i), search_term)

    def _search_and_populate(self, search_term):
        """Search S3 and populate the tree widget."""
        buckets = self._get_s3_buckets()
        items = self._search_s3_objects(buckets, search_term)

        for bucket in buckets:
            bucket_item = self._create_tree_item(
                name=bucket['Name'], object_type=ObjectType.BUCKET, date=bucket['CreationDate']
            )

            self.main_widget.tree_widget.addTopLevelItem(bucket_item)

            bucket_objects = [
                (item['Key'], item['Size'], item['LastModified'])
                for name, item in items if name == bucket['Name']
            ]
            tree_structure = self._build_tree_structure(bucket_objects)
            self._add_items_to_tree(bucket_item, tree_structure)

    def _get_s3_buckets(self):
        """Retrieve list of S3 buckets."""
        return s3_session.resource.meta.client.list_buckets()['Buckets']

    def _search_s3_objects(self, buckets, search_term):
        """Search for objects in S3 matching the search term."""
        items = []
        for bucket in buckets:
            paginator = s3_session.resource.meta.client.get_paginator('list_objects_v2')
            for obj in paginator.paginate(Bucket=bucket['Name']).search(
                f"Contents[?contains(Key, `{json.dumps(search_term)}`)][]"
            ):
                if obj:
                    items.append((bucket['Name'], obj))
        return items

    def _build_tree_structure(self, objects):
        """Build a nested dictionary representing the folder structure."""
        tree = {}
        for path, size, date in objects:
            current = tree
            *folders, filename = path.split('/')
            for folder in folders:
                current = current.setdefault(folder, {})
            current[filename] = {"_info": (size, date)}
        return tree

    def _add_items_to_tree(self, parent_item, tree_dict):
        """Recursively add items to the tree widget."""
        for key, value in tree_dict.items():
            if key == "_info":
                continue

            item = self._create_tree_item(name=key, object_type=ObjectType.FOLDER)
            parent_item.addChild(item)

            if "_info" in value:
                size, date = value["_info"]
                item = self._create_tree_item(name=key, object_type=ObjectType.FILE, size=size, date=date)

            self._add_items_to_tree(item, value)

    def _expand_and_select(self, item, search_term):
        """Recursively expand and select matching items."""
        if item.childCount():
            item.setExpanded(True)
        if search_term in item.text(0):
            item.setSelected(True)
        for i in range(item.childCount()):
            self._expand_and_select(item.child(i), search_term)

    def _create_tree_item(self, name, object_type, size=0, date=None):
        """Create a QTreeWidgetItem with the given texts, type, icon, size, and date."""
        item = QTreeWidgetItem()
        item.setText(0, name)
        item.setIcon(0, self.icon_type[object_type])
        item.setText(1, object_type)
        item.setText(2, StringUtils.format_size(size))
        item.setText(3, StringUtils.format_datetime(date))
        return item