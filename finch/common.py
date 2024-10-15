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
from PyQt5.QtWidgets import QDesktopWidget

s3_session = boto3.session.Session()

CONFIG_PATH = os.path.join(Path.home(), ".config/finch")
DATETIME_FORMAT = "%d %b %Y %H:%M"


def apply_theme(app):
    """ Apply Dark Theme """
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
        return dt.strftime(DATETIME_FORMAT)

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
