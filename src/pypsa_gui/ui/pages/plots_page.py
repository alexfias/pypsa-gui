from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlotsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)

        title = QLabel("Plots", self)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold;")

        body = QLabel(
            "This page will later host plots such as capacities, dispatch, "
            "marginal prices, and storage state of charge.",
            self,
        )
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setStyleSheet("font-size: 14px; padding: 24px;")

        layout.addWidget(title)
        layout.addWidget(body, stretch=1)