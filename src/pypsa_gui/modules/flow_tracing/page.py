# src/pypsa_gui/modules/flow_tracing/page.py
from __future__ import annotations

import pypsa
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pypsa_gui.modules.flow_tracing.service import preview_flow_tracing


class FlowTracingPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.network: pypsa.Network | None = None

        self.info_label = QLabel("No network loaded.")
        self.run_button = QPushButton("Run Flow Tracing")
        self.output = QTextEdit()
        self.output.setReadOnly(True)

        self.run_button.clicked.connect(self._on_run_clicked)

        layout = QVBoxLayout(self)
        layout.addWidget(self.info_label)
        layout.addWidget(self.run_button)
        layout.addWidget(self.output)

        self._update_state()

    def set_network(self, network: pypsa.Network | None) -> None:
        self.network = network
        self.output.clear()
        self._update_state()

    def _update_state(self) -> None:
        has_network = self.network is not None
        self.run_button.setEnabled(has_network)

        if self.network is None:
            self.info_label.setText("No network loaded.")
            return

        self.info_label.setText(
            f"Loaded network: "
            f"{len(self.network.buses)} buses, "
            f"{len(self.network.lines)} lines, "
            f"{len(self.network.links)} links"
        )

    def _on_run_clicked(self) -> None:
        if self.network is None:
            return

        result = preview_flow_tracing(self.network)
        self.output.setPlainText(result.summary_text)