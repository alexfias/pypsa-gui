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

from pypsa_gui.services.storage import (
    get_charge_discharge_timeseries,
    get_storage_dispatch_by_asset,
    get_storage_dispatch_timeseries,
    get_storage_power_by_bus,
    get_storage_soc_by_asset,
    get_storage_soc_timeseries,
    get_storage_unit_names,
    get_storage_unit_summary,
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

        self.figure = Figure(figsize=(6, 3))
        self.canvas = FigureCanvas(self.figure)

        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)


class StoragePage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.network: pypsa.Network | None = None

        self.storage_selector = QComboBox()
        self.storage_selector.currentIndexChanged.connect(self.refresh)

        self.asset_count_card = InfoCard("Storage Units", "-")
        self.total_power_card = InfoCard("Total Power", "-")
        self.total_energy_card = InfoCard("Approx. Energy", "-")
        self.avg_eff_card = InfoCard("Avg. Efficiency", "-")

        self.soc_plot = PlotCard("State of Charge")
        self.charge_discharge_plot = PlotCard("Charging vs Discharging")
        self.dispatch_by_asset_plot = PlotCard("Discharged Energy by Asset")
        self.power_by_bus_plot = PlotCard("Installed Storage Power by Bus")
        self.avg_soc_by_asset_plot = PlotCard("Average State of Charge by Asset")

        self._build_ui()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setAlignment(Qt.AlignTop)  # IMPORTANT

        # --- Filters ---
        filter_box = QGroupBox("Filters")
        filter_layout = QVBoxLayout(filter_box)
        filter_layout.addWidget(QLabel("Storage Unit"))
        filter_layout.addWidget(self.storage_selector)

        # --- Cards ---
        cards_layout = QGridLayout()
        cards_layout.addWidget(self.asset_count_card, 0, 0)
        cards_layout.addWidget(self.total_power_card, 0, 1)
        cards_layout.addWidget(self.total_energy_card, 0, 2)
        cards_layout.addWidget(self.avg_eff_card, 0, 3)

        # --- Add everything ---
        container_layout.addWidget(filter_box)
        container_layout.addLayout(cards_layout)

        # Give plots a minimum height so scrolling kicks in
        for plot in [
            self.soc_plot,
            self.charge_discharge_plot,
            self.dispatch_by_asset_plot,
            self.power_by_bus_plot,
            self.avg_soc_by_asset_plot,
        ]:
            plot.setMinimumHeight(250)
            container_layout.addWidget(plot)

        container_layout.addStretch()  # keeps everything top-aligned

        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

    def set_network(self, network: pypsa.Network | None) -> None:
        self.network = network
        self._populate_storage_selector()
        self.refresh()

    def _populate_storage_selector(self) -> None:
        self.storage_selector.blockSignals(True)
        self.storage_selector.clear()
        self.storage_selector.addItem("All Storage Units")

        if self.network is not None:
            for name in get_storage_unit_names(self.network):
                self.storage_selector.addItem(name)

        self.storage_selector.blockSignals(False)

    def _selected_storage_name(self) -> str | None:
        text = self.storage_selector.currentText()
        if text == "All Storage Units":
            return None
        return text

    def refresh(self) -> None:
        self._update_cards()
        self._plot_soc()
        self._plot_charge_discharge()
        self._plot_dispatch_by_asset()
        self._plot_power_by_bus()
        self._plot_avg_soc_by_asset()

    def _update_cards(self) -> None:
        if self.network is None:
            self.asset_count_card.set_value("-")
            self.total_power_card.set_value("-")
            self.total_energy_card.set_value("-")
            self.avg_eff_card.set_value("-")
            return

        summary = get_storage_unit_summary(self.network)
        self.asset_count_card.set_value(f"{summary['n_assets']}")
        self.total_power_card.set_value(f"{summary['total_power_mw']:.1f} MW")
        self.total_energy_card.set_value(f"{summary['total_energy_mwh']:.1f} MWh")
        self.avg_eff_card.set_value(f"{100 * summary['avg_efficiency']:.1f} %")

    def _plot_soc(self) -> None:
        fig = self.soc_plot.figure
        fig.clear()
        ax = fig.add_subplot(111)

        if self.network is not None:
            series = get_storage_soc_timeseries(self.network, self._selected_storage_name())
            if not series.empty:
                ax.plot(series.index, series.values)
                ax.set_ylabel("MWh")
                ax.set_title("State of Charge")
            else:
                ax.text(0.5, 0.5, "No state of charge data available", ha="center", va="center")
        else:
            ax.text(0.5, 0.5, "No network loaded", ha="center", va="center")

        fig.autofmt_xdate()
        fig.tight_layout()
        self.soc_plot.canvas.draw()

    def _plot_charge_discharge(self) -> None:
        fig = self.charge_discharge_plot.figure
        fig.clear()
        ax = fig.add_subplot(111)

        if self.network is not None:
            charge, discharge = get_charge_discharge_timeseries(
                self.network, self._selected_storage_name()
            )
            if not charge.empty or not discharge.empty:
                ax.plot(charge.index, charge.values, label="Charge")
                ax.plot(discharge.index, discharge.values, label="Discharge")
                ax.set_ylabel("MW")
                ax.set_title("Charging and Discharging")
                ax.legend()
            else:
                ax.text(0.5, 0.5, "No dispatch data available", ha="center", va="center")
        else:
            ax.text(0.5, 0.5, "No network loaded", ha="center", va="center")

        fig.autofmt_xdate()
        fig.tight_layout()
        self.charge_discharge_plot.canvas.draw()

    def _plot_dispatch_by_asset(self) -> None:
        fig = self.dispatch_by_asset_plot.figure
        fig.clear()
        ax = fig.add_subplot(111)

        if self.network is not None:
            data = get_storage_dispatch_by_asset(self.network).head(15)
            if not data.empty:
                ax.bar(data.index.astype(str), data.values)
                ax.set_ylabel("MWh")
                ax.set_title("Total Discharged Energy by Asset")
                ax.tick_params(axis="x", rotation=45)
            else:
                ax.text(0.5, 0.5, "No storage dispatch data available", ha="center", va="center")
        else:
            ax.text(0.5, 0.5, "No network loaded", ha="center", va="center")

        fig.tight_layout()
        self.dispatch_by_asset_plot.canvas.draw()

    def _plot_power_by_bus(self) -> None:
        fig = self.power_by_bus_plot.figure
        fig.clear()
        ax = fig.add_subplot(111)

        if self.network is not None:
            data = get_storage_power_by_bus(self.network).head(15)
            if not data.empty:
                ax.bar(data.index.astype(str), data.values)
                ax.set_ylabel("MW")
                ax.set_title("Installed Storage Power by Bus")
                ax.tick_params(axis="x", rotation=45)
            else:
                ax.text(0.5, 0.5, "No storage units available", ha="center", va="center")
        else:
            ax.text(0.5, 0.5, "No network loaded", ha="center", va="center")

        fig.tight_layout()
        self.power_by_bus_plot.canvas.draw()

    def _plot_avg_soc_by_asset(self) -> None:
        fig = self.avg_soc_by_asset_plot.figure
        fig.clear()
        ax = fig.add_subplot(111)

        if self.network is not None:
            data = get_storage_soc_by_asset(self.network).head(15)
            if not data.empty:
                ax.bar(data.index.astype(str), data.values)
                ax.set_ylabel("MWh")
                ax.set_title("Average State of Charge by Asset")
                ax.tick_params(axis="x", rotation=45)
            else:
                ax.text(0.5, 0.5, "No state of charge data available", ha="center", va="center")
        else:
            ax.text(0.5, 0.5, "No network loaded", ha="center", va="center")

        fig.tight_layout()
        self.avg_soc_by_asset_plot.canvas.draw()