import os.path
import pathlib
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Union

import boto3
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import QDesktopWidget, QDialog, QVBoxLayout, QDialogButtonBox, QHBoxLayout, QComboBox, QWidget, \
    QDoubleSpinBox

from finch.error import show_error_dialog

s3_session = boto3.session.Session()

CONFIG_PATH = os.path.join(Path.home(), ".config/finch")
DATETIME_FORMAT = "%d %b %Y %H:%M"


def apply_theme(app):
    """ Apply Dark Theme """
    # Use light theme by default in Windows due color incompatibilities.
    if sys.platform != "win32":
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(35, 35, 35))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, QColor(25, 25, 25))
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, QColor(35, 35, 35))
        palette.setColor(QPalette.Active, QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, Qt.darkGray)
        palette.setColor(QPalette.Disabled, QPalette.WindowText, Qt.darkGray)
        palette.setColor(QPalette.Disabled, QPalette.Text, Qt.darkGray)
        palette.setColor(QPalette.Disabled, QPalette.Light, QColor(53, 53, 53))
        app.setPalette(palette)


def center_window(self):
    """ Center windows to screen """
    geometry = self.frameGeometry()
    center_point = QDesktopWidget().availableGeometry().center()
    geometry.moveCenter(center_point)
    self.move(geometry.topLeft())


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = pathlib.Path(__file__).parent.resolve()
    return os.path.join(base_path, relative_path)


class ObjectType(str, Enum):
    """ Enum for S3 object types """
    BUCKET = "Bucket"
    FOLDER = "Folder"
    FILE = "File"


class StringUtils:
    def format_object_name(filename: str) -> str:
        """ Function for getting file and folder names from full object path"""
        arr = filename.split('/')
        if arr[-1]:
            return arr[-1]
        else:
            return arr[-2]

    def format_datetime(dt: datetime) -> str:
        """ Function for format dates """
        if dt:
            return dt.strftime(DATETIME_FORMAT)
        else:
            return ''

    def remove_trailing_zeros(x: str) -> str:
        """ Function for removing trailing zeros from floats """
        return x.rstrip('0').rstrip('.')

    def format_size(file_size: Union[int, float], decimal_places=2) -> str:
        """ Function for formatting file sizes to human-readable forms """
        for unit in ['Bytes', 'Kilobytes', 'Megabytes', 'Gigabytes']:
            if file_size < 1024.0 or unit == 'Gigabytes':
                break
            file_size /= 1024.0
        return f'{StringUtils.remove_trailing_zeros(f"{file_size:.{decimal_places}f}"): >8} {unit}'

    def format_list_with_conjunction(items: list, conjunction='and') -> str:
        """Format list items with proper punctuation and conjunction.
        Example: ['a', 'b', 'c'] -> 'a, b and c'"""
        if len(items) > 1:
            return f"{', '.join(items[:-1])} {conjunction} {items[-1]}"
        return items[0] if items else ''


class TimeIntervalInputDialog(QDialog):
    """Dialog for entering time interval"""

    class TimeUnit(Enum):
        SECONDS = 1
        MINUTES = 60
        HOURS = 60 * 60
        DAYS = 24 * 60 * 60

    def __init__(self, parent=None, window_title: str = "Please Enter Time Interval", max_seconds: int = None,
                 default_unit: "TimeIntervalInputDialog.TimeUnit" = TimeUnit.SECONDS, default_value: int = None,
                 allow_zero: bool = False):

        """
        Initialize the TimeIntervalInputDialog.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
            window_title (str, optional): The title of the dialog window. Defaults to "Please Enter Time Interval".
            max_seconds (int, optional): The maximum allowed time interval in seconds. Defaults to TimeUnit.SECONDS.
            default_unit (TimeIntervalInputDialog.TimeUnit, optional): The default time unit. Defaults to None.
            default_value (int, optional): The default value for the time input. Defaults to None.
            allow_zero (bool, optional): Whether to allow zero as a valid time interval. Defaults to False.
        """

        super().__init__(parent)
        self.value = None
        self.unit = None
        self.value_as_seconds = None
        self.max_seconds = max_seconds
        self.allow_zero = allow_zero
        self.setWindowTitle(window_title)
        layout = QVBoxLayout()
        time_widget = QWidget()
        time_wiget_layout = QHBoxLayout()
        self.time_value_input = QDoubleSpinBox()
        self.time_value_input.setMaximum(2147483647)
        self.time_value_input.setDecimals(3)  # Limit to three decimal places for seconds
        if default_value is not None:
            self.time_value_input.setValue(default_value)

        self.time_unit_combobox = QComboBox()
        self.time_unit_combobox.addItems(list(map(lambda unit: unit.lower(), self.TimeUnit._member_names_)))

        self.time_unit_combobox.setCurrentText(default_unit.name.lower())
        self.unit = default_unit

        self.time_unit_combobox.currentIndexChanged.connect(self.update_value)
        time_wiget_layout.addWidget(self.time_value_input)
        time_wiget_layout.addWidget(self.time_unit_combobox)
        time_widget.setLayout(time_wiget_layout)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.on_accept)
        layout.addWidget(time_widget)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def on_accept(self):
        """
        Handle the acceptance of the dialog.

        This method is called when the user clicks the OK button. It validates the entered time interval,
        shows error messages if necessary, and sets the final values if the input is valid.
        """
        value = self.time_value_input.value()
        value_as_seconds = value * self.unit.value
        if not self.allow_zero and value_as_seconds == 0:
            show_error_dialog("Time interval cannot be zero second")
        else:
            if value_as_seconds > self.max_seconds:
                show_error_dialog(f"Maximum allowed time interval is {self.max_seconds} seconds")
            else:
                self.value = value
                self.value_as_seconds = value_as_seconds
                self.accept()

    def update_value(self, index: int):
        """
        Update the time value when the time unit is changed.

        This method recalculates the time value based on the newly selected time unit.

        Args:
            index (int): The index of the newly selected time unit in the combo box.
        """
        current_value = self.time_value_input.value()
        current_unit = self.unit
        new_unit = self.TimeUnit[self.time_unit_combobox.currentText().upper()]

        new_value = (current_value * current_unit.value) / new_unit.value
        self.time_unit_combobox.setCurrentIndex(index)
        self.time_value_input.setValue(new_value)
        self.unit = new_unit
