from __future__ import annotations

import matplotlib as mpl
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
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pypsa_gui.services.congestion import (
    get_branch_map_data,
    get_bus_map_data,
    get_combined_congestion_table,
    get_congestion_summary_stats,
    get_system_congestion_time_series,
    get_top_congested_assets,
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
        min_height: int = 320,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, parent)

        self.figure = Figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.figure)

        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)

        self.setMinimumHeight(min_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)

    def clear(self) -> None:
        self.figure.clear()

    def draw(self) -> None:
        self.canvas.draw_idle()


class CongestionPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.network: pypsa.Network | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        root_layout.addWidget(self.scroll_area)

        self.scroll_content = QWidget()
        self.scroll_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.content_layout = QVBoxLayout(self.scroll_content)
        self.content_layout.setContentsMargins(12, 12, 12, 12)
        self.content_layout.setSpacing(12)
        self.content_layout.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.scroll_content)

        cards_layout = QGridLayout()
        cards_layout.setSpacing(10)

        self.assets_card = InfoCard("Monitored Assets")
        self.avg_loading_card = InfoCard("Average Loading")
        self.max_loading_card = InfoCard("Maximum Loading")
        self.overloaded_card = InfoCard("Assets > 100%")

        cards_layout.addWidget(self.assets_card, 0, 0)
        cards_layout.addWidget(self.avg_loading_card, 0, 1)
        cards_layout.addWidget(self.max_loading_card, 1, 0)
        cards_layout.addWidget(self.overloaded_card, 1, 1)

        cards_box = QGroupBox("Congestion Overview")
        cards_box.setLayout(cards_layout)
        self.content_layout.addWidget(cards_box)

        controls_box = QGroupBox("Settings")
        controls_layout = QGridLayout(controls_box)

        self.top_metric_combo = QComboBox()
        self.top_metric_combo.addItems(
            [
                "hours_above_100",
                "hours_above_90",
                "max_loading",
                "mean_loading",
            ]
        )
        self.top_metric_combo.currentTextChanged.connect(self.refresh)

        controls_layout.addWidget(QLabel("Top assets by:"), 0, 0)
        controls_layout.addWidget(self.top_metric_combo, 0, 1)

        self.content_layout.addWidget(controls_box)

        self.system_loading_plot = PlotCard("System Congestion Over Time", min_height=320)
        self.top_assets_plot = PlotCard("Top Congested Assets", min_height=320)
        self.loading_hist_plot = PlotCard("Loading Distribution", min_height=320)
        self.threshold_plot = PlotCard("Assets Above Threshold Over Time", min_height=320)
        self.avg_loading_map_plot = PlotCard("Network Map: Average Branch Loading", min_height=420)
        self.congested_hours_map_plot = PlotCard("Network Map: Congested Hours", min_height=420)

        self.content_layout.addWidget(self.system_loading_plot)
        self.content_layout.addWidget(self.top_assets_plot)
        self.content_layout.addWidget(self.loading_hist_plot)
        self.content_layout.addWidget(self.threshold_plot)
        self.content_layout.addWidget(self.avg_loading_map_plot)
        self.content_layout.addWidget(self.congested_hours_map_plot)

        self.content_layout.addStretch(1)

    def set_network(self, network: pypsa.Network | None) -> None:
        self.network = network
        self.refresh()

    def refresh(self) -> None:
        self._update_cards()
        self._update_system_loading_plot()
        self._update_top_assets_plot()
        self._update_loading_histogram()
        self._update_threshold_plot()
        self._update_avg_loading_map()
        self._update_congested_hours_map()

    def _update_cards(self) -> None:
        if self.network is None:
            self.assets_card.set_value("-")
            self.avg_loading_card.set_value("-")
            self.max_loading_card.set_value("-")
            self.overloaded_card.set_value("-")
            return

        stats = get_congestion_summary_stats(self.network)
        self.assets_card.set_value(str(stats["n_assets"]))
        self.avg_loading_card.set_value(f'{100 * float(stats["avg_loading"]):.1f}%')
        self.max_loading_card.set_value(f'{100 * float(stats["max_loading"]):.1f}%')
        self.overloaded_card.set_value(str(stats["assets_above_100"]))

    def _update_system_loading_plot(self) -> None:
        self.system_loading_plot.clear()
        ax = self.system_loading_plot.figure.add_subplot(111)

        if self.network is None:
            ax.text(0.5, 0.5, "No network loaded", ha="center", va="center")
            ax.set_axis_off()
            self.system_loading_plot.draw()
            return

        ts = get_system_congestion_time_series(self.network)
        if ts.empty:
            ax.text(0.5, 0.5, "No congestion data available", ha="center", va="center")
            ax.set_axis_off()
            self.system_loading_plot.draw()
            return

        ax.plot(ts.index, 100 * ts["mean_loading"], label="Mean loading")
        ax.plot(ts.index, 100 * ts["max_loading"], label="Max loading")
        ax.set_ylabel("Loading [%]")
        ax.set_xlabel("Snapshot")
        ax.set_title("System loading across all monitored branches")
        ax.legend()
        ax.grid(True, alpha=0.3)

        self.system_loading_plot.figure.tight_layout()
        self.system_loading_plot.draw()

    def _update_top_assets_plot(self) -> None:
        self.top_assets_plot.clear()
        ax = self.top_assets_plot.figure.add_subplot(111)

        if self.network is None:
            ax.text(0.5, 0.5, "No network loaded", ha="center", va="center")
            ax.set_axis_off()
            self.top_assets_plot.draw()
            return

        metric = self.top_metric_combo.currentText()
        df = get_top_congested_assets(self.network, metric=metric, top_n=10)

        if df.empty:
            ax.text(0.5, 0.5, "No congestion data available", ha="center", va="center")
            ax.set_axis_off()
            self.top_assets_plot.draw()
            return

        labels = [f'{row["component"]}: {row["name"]}' for _, row in df.iterrows()]
        values = df[metric].values

        ax.barh(labels[::-1], values[::-1])
        ax.set_title(f"Top congested assets by {metric}")
        ax.set_xlabel(metric.replace("_", " ").title())
        ax.grid(True, axis="x", alpha=0.3)

        self.top_assets_plot.figure.tight_layout()
        self.top_assets_plot.draw()

    def _update_loading_histogram(self) -> None:
        self.loading_hist_plot.clear()
        ax = self.loading_hist_plot.figure.add_subplot(111)

        if self.network is None:
            ax.text(0.5, 0.5, "No network loaded", ha="center", va="center")
            ax.set_axis_off()
            self.loading_hist_plot.draw()
            return

        table = get_combined_congestion_table(self.network)
        if table.empty:
            ax.text(0.5, 0.5, "No congestion data available", ha="center", va="center")
            ax.set_axis_off()
            self.loading_hist_plot.draw()
            return

        ax.hist(100 * table["mean_loading"], bins=20)
        ax.set_xlabel("Average loading [%]")
        ax.set_ylabel("Number of assets")
        ax.set_title("Distribution of average branch loading")
        ax.grid(True, alpha=0.3)

        self.loading_hist_plot.figure.tight_layout()
        self.loading_hist_plot.draw()

    def _update_threshold_plot(self) -> None:
        self.threshold_plot.clear()
        ax = self.threshold_plot.figure.add_subplot(111)

        if self.network is None:
            ax.text(0.5, 0.5, "No network loaded", ha="center", va="center")
            ax.set_axis_off()
            self.threshold_plot.draw()
            return

        ts = get_system_congestion_time_series(self.network)
        if ts.empty:
            ax.text(0.5, 0.5, "No congestion data available", ha="center", va="center")
            ax.set_axis_off()
            self.threshold_plot.draw()
            return

        ax.plot(ts.index, ts["assets_above_90"], label="Assets > 90%")
        ax.plot(ts.index, ts["assets_above_100"], label="Assets > 100%")
        ax.set_xlabel("Snapshot")
        ax.set_ylabel("Number of assets")
        ax.set_title("Congested branches over time")
        ax.legend()
        ax.grid(True, alpha=0.3)

        self.threshold_plot.figure.tight_layout()
        self.threshold_plot.draw()

    def _draw_branch_map(
        self,
        plot_card: PlotCard,
        metric: str,
        title: str,
        colorbar_label: str,
    ) -> None:
        plot_card.clear()
        ax = plot_card.figure.add_subplot(111)

        if self.network is None:
            ax.text(0.5, 0.5, "No network loaded", ha="center", va="center")
            ax.set_axis_off()
            plot_card.draw()
            return

        branches = get_branch_map_data(self.network, metric=metric, threshold=1.0)
        buses = get_bus_map_data(self.network)

        if branches.empty or buses.empty:
            ax.text(
                0.5,
                0.5,
                "No map data available\n(buses need x/y coordinates)",
                ha="center",
                va="center",
            )
            ax.set_axis_off()
            plot_card.draw()
            return

        values = branches["value"].astype(float)
        vmin = float(values.min()) if len(values) else 0.0
        vmax = float(values.max()) if len(values) else 1.0
        if vmax <= vmin:
            vmax = vmin + 1e-9

        cmap = mpl.cm.viridis
        norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)

        for _, row in branches.iterrows():
            ax.plot(
                [row["x0"], row["x1"]],
                [row["y0"], row["y1"]],
                color=cmap(norm(float(row["value"]))),
                linewidth=2.0,
                alpha=0.9,
                zorder=1,
            )

        ax.scatter(
            buses["x"],
            buses["y"],
            s=10,
            color="black",
            alpha=0.8,
            zorder=2,
        )

        sm = mpl.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = plot_card.figure.colorbar(sm, ax=ax)
        cbar.set_label(colorbar_label)

        ax.set_title(title)
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(True, alpha=0.2)

        plot_card.figure.tight_layout()
        plot_card.draw()

    def _update_avg_loading_map(self) -> None:
        self._draw_branch_map(
            self.avg_loading_map_plot,
            metric="mean_loading",
            title="Average branch loading",
            colorbar_label="Mean loading [p.u.]",
        )

    def _update_congested_hours_map(self) -> None:
        self._draw_branch_map(
            self.congested_hours_map_plot,
            metric="hours_congested",
            title="Congested hours per branch",
            colorbar_label="Hours above 100%",
        )