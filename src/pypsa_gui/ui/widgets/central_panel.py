from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class CentralPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)

        self.title_label = QLabel("pypsa-gui", self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 22px; font-weight: bold;")

        self.content_label = QLabel(
            "No network loaded yet.\n\n"
            "Use File → Open Network... to begin.\n"
            "Later this area will host tables, plots, and results.",
            self,
        )
        self.content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_label.setStyleSheet("font-size: 14px; padding: 24px;")

        layout.addWidget(self.title_label)
        layout.addWidget(self.content_label, stretch=1)

    def show_message(self, title: str, body: str) -> None:
        self.title_label.setText(title)
        self.content_label.setText(body)