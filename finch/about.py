from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QDesktopWidget

from finch.common import center_window, resource_path


class AboutWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("About")
        self.resize(200, 300)
        center_window(self)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop)
        self.setLayout(layout)

        icon = QIcon(resource_path("img/icon.png")).pixmap(QSize(100, 100))
        icon_label = QLabel()
        icon_label.setPixmap(icon)
        icon_label.setAlignment(Qt.AlignCenter)
        title_label = QLabel("Finch S3 Client")
        title_label.setFont(QFont('sans', 30))
        subtitle_label = QLabel(
            'In memoriam of <a href="https://personofinterest.fandom.com/wiki/Root">root</a> and <a href="https://personofinterest.fandom.com/wiki/Harold_Finch">Harold Finch</a>')
        subtitle_font = QFont('sans', 12)
        subtitle_font.setItalic(True)
        subtitle_label.setFont(subtitle_font)
        version_label = QLabel('v1.0 ALPHA')
        version_label.setFont(subtitle_font)
        contributors_label = QLabel("<strong>Contributors:</strong>")
        contributors_label.setContentsMargins(0, 10, 0, 0)

        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addWidget(version_label)
        layout.addWidget(contributors_label)

        contributors = ['Furkan Kalkan <furkankalkan@mantis.com.tr>']
        for contributor in contributors:
            layout.addWidget(QLabel(contributor))
