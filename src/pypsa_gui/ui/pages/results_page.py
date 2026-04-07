from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ResultsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)

        title = QLabel("Results", self)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold;")

        body = QLabel(
            "This page will later show optimisation and power flow results.",
            self,
        )
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setStyleSheet("font-size: 14px; padding: 24px;")

        layout.addWidget(title)
        layout.addWidget(body, stretch=1)