from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ComponentPage(QWidget):
    def __init__(self, component_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.component_name = component_name

        layout = QVBoxLayout(self)

        self.title_label = QLabel(component_name, self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 22px; font-weight: bold;")

        self.body_label = QLabel(
            f"This is the placeholder page for {component_name}.\n\n"
            "Later this page will show the corresponding PyPSA table.",
            self,
        )
        self.body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body_label.setStyleSheet("font-size: 14px; padding: 24px;")

        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label, stretch=1)

    def set_message(self, message: str) -> None:
        self.body_label.setText(message)