import traceback
from typing import Union

from PyQt5.QtWidgets import QMessageBox


class ErrorDialog(QMessageBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.show_traceback = None
        self.setWindowTitle("Error")
        self.setIcon(QMessageBox.Critical)

    def exec_(self):
        if self.show_traceback:
            self.setDetailedText(traceback.format_exc())
        super().exec_()

    def setShowTraceback(self, show_traceback):
        self.show_traceback = show_traceback


def show_error_dialog(error: Union[Exception, str], show_traceback=False):
    msg = ErrorDialog()
    if isinstance(error, Exception):
        msg.setText(str(error))
    elif isinstance(error, str):
        msg.setText(error)
    msg.setShowTraceback(show_traceback)
    msg.exec_()
