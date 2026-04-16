from __future__ import annotations

import pandas as pd
import pypsa
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Patch, Wedge

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
except ImportError:  # pragma: no cover
    ccrs = None
    cfeature = None


class NetworkMapPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.network: pypsa.Network | None = None

        self.metric_combo = QComboBox()
        self.metric_combo.addItems(["Generation capacity mix"])
        self.metric_combo.currentIndexChanged.connect(self._redraw)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("View:"))
        controls_layout.addWidget(self.metric_combo)
        controls_layout.addStretch()

        self.figure = Figure(figsize=(8, 6))
        self.canvas = FigureCanvas(self.figure)

        layout = QVBoxLayout(self)
        layout.addLayout(controls_layout)
        layout.addWidget(self.canvas)

        self._redraw()

    def set_network(self, network: pypsa.Network | None) -> None:
        self.network = network
        self._redraw()

    def _redraw(self) -> None:
        self.figure.clear()

        if ccrs is None or cfeature is None:
            ax = self.figure.add_subplot(111)
            ax.text(
                0.5,
                0.5,
                "Cartopy is not installed.\nInstall cartopy to use the map view.",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_axis_off()
            self.canvas.draw()
            return

        ax = self.figure.add_subplot(111, projection=ccrs.PlateCarree())
        ax.set_title("Generation Capacity Map")

        ax.add_feature(cfeature.LAND, alpha=0.3)
        ax.add_feature(cfeature.OCEAN, alpha=0.2)
        ax.add_feature(cfeature.COASTLINE, linewidth=0.8)
        ax.add_feature(cfeature.BORDERS, linewidth=0.5)

        if self.network is None or self.network.buses.empty:
            ax.text(
                0.5,
                0.5,
                "No network loaded.",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            self.canvas.draw()
            return

        buses = self.network.buses.copy()

        if "x" not in buses.columns or "y" not in buses.columns:
            ax.text(
                0.5,
                0.5,
                "Buses do not contain x/y coordinates.",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            self.canvas.draw()
            return

        buses = buses.dropna(subset=["x", "y"])
        if buses.empty:
            ax.text(
                0.5,
                0.5,
                "No valid bus coordinates available.",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            self.canvas.draw()
            return

        self._plot_lines(ax, buses)
        self._plot_links(ax, buses)
        self._plot_bus_capacity_pies(ax, buses)
        self._add_carrier_legend(ax)

        xs = buses["x"]
        ys = buses["y"]

        x_min = float(xs.min())
        x_max = float(xs.max())
        y_min = float(ys.min())
        y_max = float(ys.max())

        x_pad = max((x_max - x_min) * 0.08, 1.0)
        y_pad = max((y_max - y_min) * 0.08, 1.0)

        ax.set_extent(
            [x_min - x_pad, x_max + x_pad, y_min - y_pad, y_max + y_pad],
            crs=ccrs.PlateCarree(),
        )

        self.figure.subplots_adjust(top=0.92)
        self.canvas.draw()

    def _plot_lines(self, ax, buses: pd.DataFrame) -> None:
        if self.network is None or self.network.lines.empty:
            return

        for _, line in self.network.lines.iterrows():
            bus0 = line.get("bus0")
            bus1 = line.get("bus1")

            if bus0 not in buses.index or bus1 not in buses.index:
                continue

            x0, y0 = buses.at[bus0, "x"], buses.at[bus0, "y"]
            x1, y1 = buses.at[bus1, "x"], buses.at[bus1, "y"]

            ax.plot(
                [x0, x1],
                [y0, y1],
                linewidth=0.7,
                alpha=0.6,
                transform=ccrs.PlateCarree(),
                zorder=1,
            )

    def _plot_links(self, ax, buses: pd.DataFrame) -> None:
        if self.network is None or self.network.links.empty:
            return

        for _, link in self.network.links.iterrows():
            bus0 = link.get("bus0")
            bus1 = link.get("bus1")

            if bus0 not in buses.index or bus1 not in buses.index:
                continue

            x0, y0 = buses.at[bus0, "x"], buses.at[bus0, "y"]
            x1, y1 = buses.at[bus1, "x"], buses.at[bus1, "y"]

            ax.plot(
                [x0, x1],
                [y0, y1],
                linestyle="--",
                linewidth=0.7,
                alpha=0.5,
                transform=ccrs.PlateCarree(),
                zorder=1,
            )

    def _plot_bus_capacity_pies(self, ax, buses: pd.DataFrame) -> None:
        capacities = self._compute_generation_capacity_by_bus_and_carrier(buses.index)

        if capacities.empty:
            return

        totals = capacities.sum(axis=1)
        max_total = float(totals.max()) if not totals.empty else 0.0

        if max_total <= 0:
            return

        map_width = max(float(buses["x"].max() - buses["x"].min()), 1.0)
        min_radius = 0.01 * map_width
        max_radius = 0.04 * map_width

        carrier_colors = {
            "solar": "gold",
            "onwind": "skyblue",
            "offwind": "dodgerblue",
            "wind": "steelblue",
            "gas": "tomato",
            "hydro": "mediumseagreen",
            "ror": "seagreen",
            "biomass": "olive",
            "coal": "dimgray",
            "lignite": "saddlebrown",
            "nuclear": "purple",
            "other": "lightgray",
        }

        for bus in capacities.index:
            if bus not in buses.index:
                continue

            x = float(buses.at[bus, "x"])
            y = float(buses.at[bus, "y"])

            row = capacities.loc[bus]
            total = float(row.sum())
            if total <= 0:
                continue

            radius = min_radius + (total / max_total) ** 0.5 * (max_radius - min_radius)

            start_angle = 0.0
            for carrier, value in row.items():
                value = float(value)
                if value <= 0:
                    continue

                angle = 360.0 * value / total
                color = carrier_colors.get(str(carrier).lower(), "lightgray")

                wedge = Wedge(
                    center=(x, y),
                    r=radius,
                    theta1=start_angle,
                    theta2=start_angle + angle,
                    facecolor=color,
                    edgecolor="black",
                    linewidth=0.4,
                    transform=ccrs.PlateCarree(),
                    zorder=3,
                )
                ax.add_patch(wedge)

                start_angle += angle

    def _compute_generation_capacity_by_bus_and_carrier(
        self,
        bus_index: pd.Index,
    ) -> pd.DataFrame:
        if self.network is None or self.network.generators.empty:
            return pd.DataFrame(index=bus_index)

        generators = self.network.generators.copy()

        if "bus" not in generators.columns or "carrier" not in generators.columns:
            return pd.DataFrame(index=bus_index)

        capacity_column = "p_nom_opt" if "p_nom_opt" in generators.columns else "p_nom"

        capacities = (
            generators.groupby(["bus", "carrier"])[capacity_column]
                .sum()
                .unstack(fill_value=0.0)
        )

        capacities = capacities.reindex(bus_index, fill_value=0.0)

        preferred_order = [
            "solar",
            "onwind",
            "offwind",
            "wind",
            "gas",
            "hydro",
            "ror",
            "biomass",
            "coal",
            "lignite",
            "nuclear",
        ]

        normalized_columns = {str(col).lower(): col for col in capacities.columns}
        selected_columns = [normalized_columns[c] for c in preferred_order if c in normalized_columns]
        other_columns = [col for col in capacities.columns if col not in selected_columns]

        result = capacities[selected_columns].copy() if selected_columns else pd.DataFrame(index=capacities.index)

        if other_columns:
            result["other"] = capacities[other_columns].sum(axis=1)

        return result

    def _add_carrier_legend(self, ax) -> None:
        carrier_colors = {
            "solar": "gold",
            "onwind": "skyblue",
            "offwind": "dodgerblue",
            "wind": "steelblue",
            "gas": "tomato",
            "hydro": "mediumseagreen",
            "ror": "seagreen",
            "biomass": "olive",
            "coal": "dimgray",
            "lignite": "saddlebrown",
            "nuclear": "purple",
            "other": "lightgray",
        }

        handles = [
            Patch(facecolor=color, edgecolor="black", label=carrier)
            for carrier, color in carrier_colors.items()
        ]

        ax.legend(
            handles=handles,
            loc="lower left",
            fontsize=8,
            frameon=True,
        )