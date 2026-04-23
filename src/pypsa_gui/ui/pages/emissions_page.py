from __future__ import annotations

import pypsa
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pypsa_gui.services.emissions import (
    get_emissions_by_bus,
    get_emissions_by_carrier,
    get_emissions_summary_stats,
    get_system_emissions_series,
    has_emission_data,
)


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


class PlotCard(QGroupBox):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)

        self.figure = Figure(figsize=(5, 3))
        self.canvas = FigureCanvas(self.figure)

        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)


class EmissionsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.network: pypsa.Network | None = None

        self.total_emissions_card = InfoCard("Total Emissions")
        self.average_intensity_card = InfoCard("Avg. Emission Intensity")
        self.top_carrier_card = InfoCard("Top Emitting Carrier")
        self.zero_emission_share_card = InfoCard("Zero-Emission Share")

        self.breakdown_mode_combo = QComboBox()
        self.breakdown_mode_combo.addItems(["By Carrier", "By Bus"])
        self.breakdown_mode_combo.currentIndexChanged.connect(self.update_plots)

        self.note_label = QLabel(
            "Operational emissions are currently calculated from positive generator dispatch "
            "using carrier-specific 'co2_emissions' factors."
        )
        self.note_label.setWordWrap(True)
        self.note_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.note_label.setStyleSheet("color: gray;")

        self.warning_label = QLabel("")
        self.warning_label.setWordWrap(True)
        self.warning_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.warning_label.setStyleSheet("color: #b36b00; font-style: italic;")

        self.breakdown_plot = PlotCard("Emission Breakdown")
        self.timeseries_plot = PlotCard("System Emissions Over Time")

        # Inner content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        cards_layout = QGridLayout()
        cards_layout.addWidget(self.total_emissions_card, 0, 0)
        cards_layout.addWidget(self.average_intensity_card, 0, 1)
        cards_layout.addWidget(self.top_carrier_card, 1, 0)
        cards_layout.addWidget(self.zero_emission_share_card, 1, 1)

        content_layout.addLayout(cards_layout)
        content_layout.addWidget(QLabel("Breakdown Mode:"))
        content_layout.addWidget(self.breakdown_mode_combo)
        content_layout.addWidget(self.note_label)
        content_layout.addWidget(self.warning_label)
        content_layout.addWidget(self.breakdown_plot)
        content_layout.addWidget(self.timeseries_plot)
        content_layout.addStretch()

        # Scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(content_widget)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        # Outer page layout
        outer_layout = QVBoxLayout(self)
        outer_layout.addWidget(scroll_area)

    def set_network(self, network: pypsa.Network | None) -> None:
        self.network = network
        self.refresh()

    def refresh(self) -> None:
        self.update_cards()
        self.update_warnings()
        self.update_plots()

    def update_cards(self) -> None:
        if self.network is None:
            self.total_emissions_card.set_value("-")
            self.average_intensity_card.set_value("-")
            self.top_carrier_card.set_value("-")
            self.zero_emission_share_card.set_value("-")
            return

        stats = get_emissions_summary_stats(self.network)
        self.total_emissions_card.set_value(stats["total_emissions"])
        self.average_intensity_card.set_value(stats["average_intensity"])
        self.top_carrier_card.set_value(stats["top_carrier"])
        self.zero_emission_share_card.set_value(stats["zero_emission_share"])

    def update_warnings(self) -> None:
        if self.network is None:
            self.warning_label.setText("")
            return

        if not has_emission_data(self.network):
            self.warning_label.setText(
                "No non-zero carrier 'co2_emissions' values were found. "
                "Results may be zero or incomplete."
            )
        else:
            self.warning_label.setText("")

    def update_plots(self) -> None:
        self._update_breakdown_plot()
        self._update_timeseries_plot()

    def _update_breakdown_plot(self) -> None:
        figure = self.breakdown_plot.figure
        figure.clear()
        ax = figure.add_subplot(111)

        if self.network is None:
            ax.set_title("No network loaded")
            ax.set_axis_off()
            self.breakdown_plot.canvas.draw()
            return

        mode = self.breakdown_mode_combo.currentText()

        if mode == "By Bus":
            series = get_emissions_by_bus(self.network)
            title = "Emissions by Bus"
            xlabel = "Bus"
        else:
            series = get_emissions_by_carrier(self.network)
            title = "Emissions by Carrier"
            xlabel = "Carrier"

        if series.empty:
            ax.text(0.5, 0.5, "No emission data available", ha="center", va="center")
            ax.set_axis_off()
            self.breakdown_plot.canvas.draw()
            return

        plot_series = series.head(15)

        ax.bar(plot_series.index.astype(str), plot_series.values)
        ax.set_title(title)
        ax.set_ylabel("tCO₂")
        ax.set_xlabel(xlabel)
        ax.tick_params(axis="x", rotation=45)

        figure.tight_layout()
        self.breakdown_plot.canvas.draw()

    def _update_timeseries_plot(self) -> None:
        figure = self.timeseries_plot.figure
        figure.clear()
        ax = figure.add_subplot(111)

        if self.network is None:
            ax.set_title("No network loaded")
            ax.set_axis_off()
            self.timeseries_plot.canvas.draw()
            return

        series = get_system_emissions_series(self.network)

        if series.empty:
            ax.text(0.5, 0.5, "No time series data available", ha="center", va="center")
            ax.set_axis_off()
            self.timeseries_plot.canvas.draw()
            return

        ax.plot(series.index, series.values)
        ax.set_title("System Emissions Over Time")
        ax.set_ylabel("tCO₂")
        ax.set_xlabel("Snapshot")
        ax.tick_params(axis="x", rotation=45)

        figure.tight_layout()
        self.timeseries_plot.canvas.draw()