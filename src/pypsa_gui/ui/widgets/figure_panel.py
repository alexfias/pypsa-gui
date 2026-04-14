from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class FigurePanel(QWidget):
    def __init__(
        self,
        default_title: str,
        minimum_canvas_height: int = 300,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.figure = Figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(minimum_canvas_height)

        self.title_edit = QLineEdit(default_title)
        self.legend_checkbox = QCheckBox("Show legend")
        self.legend_checkbox.setChecked(True)
        self.save_button = QPushButton("Save Figure")

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Title:"))
        controls_layout.addWidget(self.title_edit, stretch=1)
        controls_layout.addWidget(self.legend_checkbox)
        controls_layout.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.addLayout(controls_layout)
        layout.addWidget(self.canvas)

        self.save_button.clicked.connect(self.save_figure)

    def current_title(self) -> str:
        return self.title_edit.text().strip()

    def show_legend(self) -> bool:
        return self.legend_checkbox.isChecked()

    def save_figure(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Figure",
            str(Path.home() / "figure.png"),
            "PNG Files (*.png);;SVG Files (*.svg);;PDF Files (*.pdf)",
        )

        if not file_path:
            return

        self.figure.savefig(file_path, bbox_inches="tight")