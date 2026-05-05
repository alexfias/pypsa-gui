from __future__ import annotations

from typing import Any

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class OverviewPage(QWidget):
    open_component_requested = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()

        self.network = None
        self.selected_bus: str | None = None

        self.title_label = QLabel("Network Overview")

        self.figure = Figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.mpl_connect("button_press_event", self._on_map_click)

        self.bus_details = QTextEdit()
        self.bus_details.setReadOnly(True)
        self.bus_details.setMinimumHeight(220)
        self.bus_details.setPlaceholderText(
            "Click a bus on the map to inspect attached components."
        )

        self.open_buses_button = QPushButton("Open Bus")
        self.open_generators_button = QPushButton("Open Generators")
        self.open_loads_button = QPushButton("Open Loads")
        self.open_lines_button = QPushButton("Open Lines")
        self.open_links_button = QPushButton("Open Links")

        self.component_buttons = [
            self.open_buses_button,
            self.open_generators_button,
            self.open_loads_button,
            self.open_lines_button,
            self.open_links_button,
        ]

        for button in self.component_buttons:
            button.setEnabled(False)

        self.open_buses_button.clicked.connect(
            lambda: self._request_component_page("buses")
        )
        self.open_generators_button.clicked.connect(
            lambda: self._request_component_page("generators")
        )
        self.open_loads_button.clicked.connect(
            lambda: self._request_component_page("loads")
        )
        self.open_lines_button.clicked.connect(
            lambda: self._request_component_page("lines")
        )
        self.open_links_button.clicked.connect(
            lambda: self._request_component_page("links")
        )

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.open_buses_button)
        button_layout.addWidget(self.open_generators_button)
        button_layout.addWidget(self.open_loads_button)
        button_layout.addWidget(self.open_lines_button)
        button_layout.addWidget(self.open_links_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.title_label)
        layout.addWidget(self.canvas)
        layout.addWidget(self.bus_details)
        layout.addLayout(button_layout)

        self._show_empty_message()

    def set_network(self, network: Any) -> None:
        self.network = network
        self.selected_bus = None
        self.refresh()

    def refresh(self) -> None:
        if self.network is None or self.network.buses.empty:
            self._show_empty_message()
            return

        self.figure.clear()
        ax = self.figure.add_subplot(111)

        buses = self.network.buses
        valid_buses = buses.dropna(subset=["x", "y"])

        selected_lines = set()
        selected_links = set()
        neighbour_buses = set()

        if self.selected_bus is not None:
            selected_lines = set(
                self.network.lines[
                    (self.network.lines.bus0 == self.selected_bus)
                    | (self.network.lines.bus1 == self.selected_bus)
                ].index
            )

            selected_links = set(
                self.network.links[
                    (self.network.links.bus0 == self.selected_bus)
                    | (self.network.links.bus1 == self.selected_bus)
                ].index
            )

            for _, line in self.network.lines.loc[list(selected_lines)].iterrows():
                neighbour_buses.add(line.bus0)
                neighbour_buses.add(line.bus1)

            for _, link in self.network.links.loc[list(selected_links)].iterrows():
                neighbour_buses.add(link.bus0)
                neighbour_buses.add(link.bus1)

            neighbour_buses.discard(self.selected_bus)

        if not self.network.lines.empty:
            for line_name, line in self.network.lines.iterrows():
                self._plot_branch(
                    ax=ax,
                    buses=buses,
                    bus0=line["bus0"],
                    bus1=line["bus1"],
                    linewidth=2.5 if line_name in selected_lines else 1.0,
                    alpha=1.0 if line_name in selected_lines else 0.35,
                    zorder=3 if line_name in selected_lines else 1,
                )

        if not self.network.links.empty:
            for link_name, link in self.network.links.iterrows():
                self._plot_branch(
                    ax=ax,
                    buses=buses,
                    bus0=link["bus0"],
                    bus1=link["bus1"],
                    linewidth=2.5 if link_name in selected_links else 1.0,
                    alpha=1.0 if link_name in selected_links else 0.25,
                    linestyle="--",
                    zorder=3 if link_name in selected_links else 1,
                )

        if not valid_buses.empty:
            ax.scatter(valid_buses["x"], valid_buses["y"], s=30, alpha=0.8, zorder=4)

        neighbour_buses = [b for b in neighbour_buses if b in valid_buses.index]
        if neighbour_buses:
            neighbours = valid_buses.loc[neighbour_buses]
            ax.scatter(
                neighbours["x"],
                neighbours["y"],
                s=75,
                marker="o",
                facecolors="none",
                edgecolors="black",
                linewidths=1.5,
                zorder=5,
            )

        if self.selected_bus in valid_buses.index:
            bus = valid_buses.loc[self.selected_bus]
            ax.scatter(
                [bus["x"]],
                [bus["y"]],
                s=150,
                marker="o",
                facecolors="none",
                edgecolors="black",
                linewidths=2.5,
                zorder=6,
            )

        ax.set_title("Network Map")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(True)

        self.canvas.draw()

    def _plot_branch(
        self,
        ax,
        buses: pd.DataFrame,
        bus0: str,
        bus1: str,
        linewidth: float = 1.0,
        alpha: float = 1.0,
        linestyle: str = "-",
        zorder: int = 1,
    ) -> None:
        if bus0 not in buses.index or bus1 not in buses.index:
            return

        x0 = buses.at[bus0, "x"]
        y0 = buses.at[bus0, "y"]
        x1 = buses.at[bus1, "x"]
        y1 = buses.at[bus1, "y"]

        if not all(v == v for v in [x0, y0, x1, y1]):
            return

        ax.plot(
            [x0, x1],
            [y0, y1],
            linewidth=linewidth,
            alpha=alpha,
            linestyle=linestyle,
            zorder=zorder,
        )

    def _on_map_click(self, event) -> None:
        if self.network is None:
            return

        if event.xdata is None or event.ydata is None or event.inaxes is None:
            return

        buses = self.network.buses.dropna(subset=["x", "y"])

        if buses.empty:
            return

        dx = buses["x"] - event.xdata
        dy = buses["y"] - event.ydata
        distances = (dx**2 + dy**2) ** 0.5

        bus_name = distances.idxmin()
        distance = distances.loc[bus_name]

        xlim = event.inaxes.get_xlim()
        ylim = event.inaxes.get_ylim()
        tolerance = 0.025 * max(abs(xlim[1] - xlim[0]), abs(ylim[1] - ylim[0]))

        if distance > tolerance:
            self.bus_details.setText("No bus selected. Click closer to a bus marker.")
            self.selected_bus = None
            self._set_component_buttons_enabled(False)
            self.refresh()
            return

        self.selected_bus = str(bus_name)
        self._show_bus_details(self.selected_bus)
        self.refresh()

    def _show_bus_details(self, bus_name: str) -> None:
        if self.network is None:
            return

        n = self.network
        bus = n.buses.loc[bus_name]

        generators = n.generators[n.generators.bus == bus_name]
        loads = n.loads[n.loads.bus == bus_name]
        stores = n.stores[n.stores.bus == bus_name]
        storage_units = n.storage_units[n.storage_units.bus == bus_name]

        lines = n.lines[(n.lines.bus0 == bus_name) | (n.lines.bus1 == bus_name)]
        links = n.links[(n.links.bus0 == bus_name) | (n.links.bus1 == bus_name)]

        generator_capacity = self._capacity_sum(generators)
        load_capacity = self._capacity_sum(loads)
        store_energy_capacity = self._capacity_sum(
            stores, preferred_columns=("e_nom_opt", "e_nom")
        )
        storage_unit_capacity = self._capacity_sum(storage_units)

        generator_dispatch = self._time_series_sum(
            n, "generators_t", "p", generators.index
        )
        load_dispatch = self._time_series_sum(n, "loads_t", "p", loads.index)

        def names(df: pd.DataFrame, max_items: int = 8) -> str:
            if df.empty:
                return "None"

            values = list(df.index.astype(str))

            if len(values) > max_items:
                shown = values[:max_items]
                return ", ".join(shown) + f", ... ({len(values)} total)"

            return ", ".join(values)

        text = f"""
Bus: {bus_name}

Coordinates:
  x: {bus.get("x", "-")}
  y: {bus.get("y", "-")}

Aggregated metrics:
  Generation capacity: {self._format_mw(generator_capacity)}
  Load nominal capacity: {self._format_mw(load_capacity)}
  Store energy capacity: {self._format_mwh(store_energy_capacity)}
  Storage unit power capacity: {self._format_mw(storage_unit_capacity)}
  Mean generator dispatch: {self._format_mw(generator_dispatch)}
  Mean load: {self._format_mw(load_dispatch)}

Attached components:
  Generators: {len(generators)}
    {names(generators)}

  Loads: {len(loads)}
    {names(loads)}

  Stores: {len(stores)}
    {names(stores)}

  Storage units: {len(storage_units)}
    {names(storage_units)}

Connected branches:
  Lines: {len(lines)}
    {names(lines)}

  Links: {len(links)}
    {names(links)}
"""

        self.bus_details.setText(text.strip())
        self._set_component_buttons_enabled(True)

    def _request_component_page(self, component_type: str) -> None:
        if self.selected_bus is None:
            return

        self.open_component_requested.emit(component_type, self.selected_bus)

    def _set_component_buttons_enabled(self, enabled: bool) -> None:
        for button in self.component_buttons:
            button.setEnabled(enabled)

    def _capacity_sum(
        self,
        df: pd.DataFrame,
        preferred_columns: tuple[str, ...] = ("p_nom_opt", "p_nom"),
    ) -> float | None:
        for column in preferred_columns:
            if column in df.columns:
                return float(df[column].fillna(0.0).sum())
        return None

    def _time_series_sum(
        self,
        network: Any,
        component_timeseries_name: str,
        field: str,
        component_index: pd.Index,
    ) -> float | None:
        if len(component_index) == 0:
            return None

        component_timeseries = getattr(network, component_timeseries_name, None)
        if component_timeseries is None:
            return None

        dataframe = getattr(component_timeseries, field, None)
        if dataframe is None or dataframe.empty:
            return None

        columns = [c for c in component_index if c in dataframe.columns]
        if not columns:
            return None

        return float(dataframe[columns].sum(axis=1).mean())

    def _format_mw(self, value: float | None) -> str:
        if value is None:
            return "-"

        if abs(value) >= 1000:
            return f"{value / 1000:.2f} GW"

        return f"{value:.2f} MW"

    def _format_mwh(self, value: float | None) -> str:
        if value is None:
            return "-"

        if abs(value) >= 1000:
            return f"{value / 1000:.2f} GWh"

        return f"{value:.2f} MWh"

    def _show_empty_message(self) -> None:
        self.figure.clear()
        self.selected_bus = None

        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.5, "No network loaded yet", ha="center", va="center")
        ax.set_axis_off()

        self.bus_details.setText(
            "No network loaded. Load a PyPSA network to inspect buses."
        )
        self._set_component_buttons_enabled(False)

        self.canvas.draw()