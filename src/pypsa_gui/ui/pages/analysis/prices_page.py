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

from pypsa_gui.services.prices import (
    get_average_price_by_bus,
    get_nodal_prices,
    get_price_summary_stats,
    get_system_price_series,
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
    def __init__(
        self,
        title: str,
        minimum_height: int = 320,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, parent)

        self.figure = Figure(figsize=(6, 3), constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(minimum_height)

        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)

    def clear(self) -> None:
        self.figure.clear()

    def draw(self) -> None:
        self.canvas.draw_idle()


class PricesPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.network: pypsa.Network | None = None

        self.avg_price_card = InfoCard("Average Price")
        self.min_price_card = InfoCard("Minimum Price")
        self.max_price_card = InfoCard("Maximum Price")
        self.neg_hours_card = InfoCard("Negative-Price Hours")
        self.spread_card = InfoCard("95–5 Spread")
        self.high_bus_card = InfoCard("Highest Avg Bus")
        self.low_bus_card = InfoCard("Lowest Avg Bus")

        self.system_price_plot = PlotCard("System Price Time Series", minimum_height=360)
        self.duration_curve_plot = PlotCard("Price Duration Curve", minimum_height=320)
        self.avg_bus_plot = PlotCard("Average Price by Bus", minimum_height=340)
        self.heatmap_plot = PlotCard("Price Heatmap", minimum_height=420)
        self.bus_price_plot = PlotCard("Selected Bus Price Time Series", minimum_height=360)

        self.bus_selector = QComboBox()
        self.bus_selector.currentIndexChanged.connect(self._refresh_selected_bus_plot)

        self._build_ui()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        container = QWidget()
        root = QVBoxLayout(container)

        cards_layout = QGridLayout()
        cards_layout.addWidget(self.avg_price_card, 0, 0)
        cards_layout.addWidget(self.min_price_card, 0, 1)
        cards_layout.addWidget(self.max_price_card, 0, 2)
        cards_layout.addWidget(self.neg_hours_card, 0, 3)
        cards_layout.addWidget(self.spread_card, 1, 0)
        cards_layout.addWidget(self.high_bus_card, 1, 1)
        cards_layout.addWidget(self.low_bus_card, 1, 2)

        selector_group = QGroupBox("Bus Selection")
        selector_layout = QVBoxLayout(selector_group)
        selector_layout.addWidget(self.bus_selector)

        plots_layout = QVBoxLayout()
        plots_layout.addWidget(self.system_price_plot)
        plots_layout.addWidget(self.duration_curve_plot)
        plots_layout.addWidget(self.avg_bus_plot)
        plots_layout.addWidget(self.heatmap_plot)
        plots_layout.addWidget(selector_group)
        plots_layout.addWidget(self.bus_price_plot)

        root.addLayout(cards_layout)
        root.addLayout(plots_layout)
        root.addStretch()

        scroll_area.setWidget(container)
        outer_layout.addWidget(scroll_area)

    def set_network(self, network: pypsa.Network | None) -> None:
        self.network = network
        self._populate_bus_selector()
        self.refresh()

    def refresh(self) -> None:
        self._refresh_summary_cards()
        self._refresh_system_price_plot()
        self._refresh_duration_curve()
        self._refresh_avg_bus_plot()
        self._refresh_heatmap_plot()
        self._refresh_selected_bus_plot()

    def _populate_bus_selector(self) -> None:
        self.bus_selector.blockSignals(True)
        self.bus_selector.clear()

        prices = get_nodal_prices(self.network)
        if not prices.empty:
            self.bus_selector.addItems([str(col) for col in prices.columns])

        self.bus_selector.blockSignals(False)

    def _format_value(self, value: float | int | str | None, suffix: str = "") -> str:
        if value is None:
            return "-"
        if isinstance(value, float):
            return f"{value:.2f}{suffix}"
        return f"{value}{suffix}"

    def _refresh_summary_cards(self) -> None:
        stats = get_price_summary_stats(self.network)

        self.avg_price_card.set_value(self._format_value(stats["avg_price"], " €/MWh"))
        self.min_price_card.set_value(self._format_value(stats["min_price"], " €/MWh"))
        self.max_price_card.set_value(self._format_value(stats["max_price"], " €/MWh"))
        self.neg_hours_card.set_value(self._format_value(stats["negative_hours"]))
        self.spread_card.set_value(self._format_value(stats["spread_95_5"], " €/MWh"))
        self.high_bus_card.set_value(self._format_value(stats["highest_avg_bus"]))
        self.low_bus_card.set_value(self._format_value(stats["lowest_avg_bus"]))

    def _refresh_system_price_plot(self) -> None:
        self.system_price_plot.clear()
        ax = self.system_price_plot.figure.add_subplot(111)

        series = get_system_price_series(self.network, weighted=True)
        if series.empty:
            ax.text(0.5, 0.5, "No price data available", ha="center", va="center")
            ax.set_axis_off()
        else:
            ax.plot(series.index, series.values)
            ax.set_ylabel("€/MWh")
            ax.grid(True, alpha=0.3)

        self.system_price_plot.draw()

    def _refresh_duration_curve(self) -> None:
        self.duration_curve_plot.clear()
        ax = self.duration_curve_plot.figure.add_subplot(111)

        series = get_system_price_series(self.network, weighted=True)
        if series.empty:
            ax.text(0.5, 0.5, "No price data available", ha="center", va="center")
            ax.set_axis_off()
        else:
            sorted_prices = series.sort_values(ascending=False).reset_index(drop=True)
            ax.plot(sorted_prices.index, sorted_prices.values)
            ax.set_xlabel("Sorted Hour")
            ax.set_ylabel("€/MWh")
            ax.grid(True, alpha=0.3)

        self.duration_curve_plot.draw()

    def _refresh_avg_bus_plot(self) -> None:
        self.avg_bus_plot.clear()
        ax = self.avg_bus_plot.figure.add_subplot(111)

        avg_by_bus = get_average_price_by_bus(self.network)
        if avg_by_bus.empty:
            ax.text(0.5, 0.5, "No price data available", ha="center", va="center")
            ax.set_axis_off()
        else:
            avg_by_bus.plot(kind="bar", ax=ax)
            ax.set_ylabel("€/MWh")
            ax.grid(True, axis="y", alpha=0.3)
            ax.tick_params(axis="x", rotation=45)
            for label in ax.get_xticklabels():
                label.set_horizontalalignment("right")

        self.avg_bus_plot.draw()

    def _refresh_heatmap_plot(self) -> None:
        self.heatmap_plot.clear()
        ax = self.heatmap_plot.figure.add_subplot(111)

        prices = get_nodal_prices(self.network)
        if prices.empty:
            ax.text(0.5, 0.5, "No price data available", ha="center", va="center")
            ax.set_axis_off()
            self.heatmap_plot.draw()
            return

        heatmap_data = prices.T.values

        im = ax.imshow(
            heatmap_data,
            aspect="auto",
            interpolation="nearest",
            origin="lower",
        )

        ax.set_ylabel("Bus")
        ax.set_xlabel("Snapshot")

        ax.set_yticks(range(len(prices.columns)))
        ax.set_yticklabels([str(col) for col in prices.columns])

        if len(prices.index) > 1:
            n_ticks = min(8, len(prices.index))
            tick_positions = [int(i * (len(prices.index) - 1) / max(n_ticks - 1, 1)) for i in range(n_ticks)]
            ax.set_xticks(tick_positions)
            ax.set_xticklabels([str(prices.index[i]) for i in tick_positions], rotation=30, ha="right")

        self.heatmap_plot.figure.colorbar(im, ax=ax, label="€/MWh")
        self.heatmap_plot.draw()

    def _refresh_selected_bus_plot(self) -> None:
        self.bus_price_plot.clear()
        ax = self.bus_price_plot.figure.add_subplot(111)

        prices = get_nodal_prices(self.network)
        selected_bus = self.bus_selector.currentText()

        if prices.empty or not selected_bus or selected_bus not in prices.columns:
            ax.text(0.5, 0.5, "No bus selected", ha="center", va="center")
            ax.set_axis_off()
        else:
            series = prices[selected_bus]
            ax.plot(series.index, series.values)
            ax.set_ylabel("€/MWh")
            ax.grid(True, alpha=0.3)

        self.bus_price_plot.draw()