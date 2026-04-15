from __future__ import annotations

import pypsa
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pypsa_gui.services.optimisation import preview_network_optimisation


class InfoCard(QGroupBox):
    def __init__(self, title: str, value: str = "-", parent: QWidget | None = None) -> None:
        super().__init__(title, parent)

        self.value_label = QLabel(value)
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setStyleSheet("font-size: 18px; font-weight: bold;")

        layout = QVBoxLayout(self)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class OptimisationPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.network: pypsa.Network | None = None

        self.preview_button = QPushButton("Preview Model")
        self.preview_button.clicked.connect(self._preview_model)

        self.status_label = QLabel("Load a network and click 'Preview Model'.")
        self.status_label.setWordWrap(True)

        self.variables_card = InfoCard("Variables")
        self.constraints_card = InfoCard("Constraints")
        self.nonzeros_card = InfoCard("Nonzeros")
        self.size_card = InfoCard("Estimated Size")

        metrics_layout = QGridLayout()
        metrics_layout.addWidget(self.variables_card, 0, 0)
        metrics_layout.addWidget(self.constraints_card, 0, 1)
        metrics_layout.addWidget(self.nonzeros_card, 1, 0)
        metrics_layout.addWidget(self.size_card, 1, 1)

        metrics_group = QGroupBox("Dry Run Info")
        metrics_group.setLayout(metrics_layout)

        self.matrix_shape_label = QLabel("-")
        self.matrix_density_label = QLabel("-")

        details_layout = QFormLayout()
        details_layout.addRow("Matrix shape:", self.matrix_shape_label)
        details_layout.addRow("Matrix density:", self.matrix_density_label)

        details_group = QGroupBox("Details")
        details_group.setLayout(details_layout)

        layout = QVBoxLayout(self)
        layout.addWidget(self.preview_button)
        layout.addWidget(self.status_label)
        layout.addWidget(metrics_group)
        layout.addWidget(details_group)
        layout.addStretch()

        self.preview_button.setEnabled(False)

    def set_network(self, network: pypsa.Network | None) -> None:
        self.network = network
        self.preview_button.setEnabled(network is not None)

        if network is None:
            self.status_label.setText("No network loaded.")
        else:
            self.status_label.setText("Ready to preview optimisation model.")

        self._clear_preview()

    def _clear_preview(self) -> None:
        self.variables_card.set_value("-")
        self.constraints_card.set_value("-")
        self.nonzeros_card.set_value("-")
        self.size_card.set_value("-")
        self.matrix_shape_label.setText("-")
        self.matrix_density_label.setText("-")

    def _preview_model(self) -> None:
        if self.network is None:
            self.status_label.setText("No network loaded.")
            return

        self.preview_button.setEnabled(False)
        self.status_label.setText("Building optimisation model...")
        self.repaint()

        try:
            preview = preview_network_optimisation(self.network)
        except Exception as exc:
            self.status_label.setText(f"Preview failed: {exc}")
            self.preview_button.setEnabled(True)
            return

        self.variables_card.set_value(f"{preview.variables:,}")
        self.constraints_card.set_value(f"{preview.constraints:,}")
        self.nonzeros_card.set_value("-" if preview.nonzeros is None else f"{preview.nonzeros:,}")
        self.size_card.set_value(preview.status)

        if preview.matrix_rows is not None and preview.matrix_cols is not None:
            self.matrix_shape_label.setText(f"{preview.matrix_rows:,} × {preview.matrix_cols:,}")
        else:
            self.matrix_shape_label.setText("-")

        if preview.matrix_density is not None:
            self.matrix_density_label.setText(f"{preview.matrix_density:.6f}")
        else:
            self.matrix_density_label.setText("-")

        self.status_label.setText("Model preview created successfully.")
        self.preview_button.setEnabled(True)