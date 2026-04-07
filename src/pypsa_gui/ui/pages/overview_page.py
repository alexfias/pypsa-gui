from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class OverviewPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)

        title = QLabel("Overview", self)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold;")

        body = QLabel(
            "No network loaded yet.\n\n"
            "Use File → Open Network... to begin.\n"
            "This page will later show basic network metadata and summaries.",
            self,
        )
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setStyleSheet("font-size: 14px; padding: 24px;")

        layout.addWidget(title)
        layout.addWidget(body, stretch=1)