import traceback
from typing import Union

from PyQt5.QtWidgets import QMessageBox


class ErrorDialog(QMessageBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.show_traceback = None
        self.setWindowTitle("Error")
        self.setIcon(QMessageBox.Critical)
        self.extra_info = None

    def exec_(self):
        if self.show_traceback:
            detailed_text = traceback.format_exc()
            if self.extra_info:
                detailed_text += f"\n\nExtra Info:\n{self.extra_info}"
            self.setDetailedText(detailed_text)
        super().exec_()

    def setShowTraceback(self, show_traceback):
        self.show_traceback = show_traceback

    def setExtraInfo(self, extra_info):
        self.extra_info = extra_info


def show_error_dialog(error: Union[Exception, str], show_traceback=False, extra_info=None) -> None:
    msg = ErrorDialog()
    if isinstance(error, Exception):
        msg.setText(str(error))
    elif isinstance(error, str):
        msg.setText(error)
    msg.setShowTraceback(show_traceback)
    msg.setExtraInfo(extra_info)
    msg.exec_()
