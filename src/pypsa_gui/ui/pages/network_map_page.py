from __future__ import annotations

import pypsa
from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from pypsa_gui.ui.widgets.figure_panel import FigurePanel
from pypsa_gui.visualization.network_renderer import render_network, resolve_layout


class NetworkMapPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.network: pypsa.Network | None = None
        self._layouts = {}
        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["Auto", "Geographical", "Schematic"])
        self.layout_combo.setToolTip("Auto assumes valid x/y coordinates are longitude/latitude. Choose Schematic for arbitrary coordinates.")
        self.metric_combo = QComboBox()
        self.metric_combo.addItems(["Installed generation capacity", "Topology"])
        self.labels_checkbox = QCheckBox("Bus labels")
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Layout:"))
        controls.addWidget(self.layout_combo)
        controls.addWidget(QLabel("View:"))
        controls.addWidget(self.metric_combo)
        controls.addWidget(self.labels_checkbox)
        controls.addStretch()
        self.panel = FigurePanel("Installed generation capacity", minimum_canvas_height=400)
        self.figure = self.panel.figure
        self.canvas = self.panel.canvas
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.panel, stretch=1)
        layout.addWidget(self.status_label)
        self.layout_combo.currentIndexChanged.connect(self._redraw)
        self.metric_combo.currentIndexChanged.connect(self._metric_changed)
        self.labels_checkbox.toggled.connect(self._redraw)
        self.panel.title_edit.editingFinished.connect(self._redraw)
        self.panel.legend_checkbox.toggled.connect(self._redraw)
        self._redraw()

    def set_network(self, network: pypsa.Network | None) -> None:
        self.network = network
        self._layouts.clear()
        self._redraw()

    def _metric_changed(self) -> None:
        self.panel.title_edit.setText("Installed generation capacity" if self.metric_combo.currentIndex() == 0 else "Network topology")
        self._redraw()

    def _redraw(self) -> None:
        mode = self.layout_combo.currentText()
        if self.network is not None and not self.network.buses.empty and mode not in self._layouts:
            self._layouts[mode] = resolve_layout(self.network, mode)
        result = render_network(
            self.figure, self.network, layout=self._layouts.get(mode), mode=mode,
            capacity=self.metric_combo.currentIndex() == 0,
            labels=self.labels_checkbox.isChecked(), legend=self.panel.show_legend(),
            title=self.panel.current_title(),
        )
        self.status_label.setText(result.note if result else "Load a network to explore its topology.")
        self.panel.toolbar.update()
        self.canvas.draw_idle()
