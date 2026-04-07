from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class OverviewPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.network = None

        self.title_label = QLabel("Network Overview")

        self.figure = Figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.figure)

        layout = QVBoxLayout(self)
        layout.addWidget(self.title_label)
        layout.addWidget(self.canvas)

        self._show_empty_message()

    def set_network(self, network) -> None:
        self.network = network
        self.refresh()

    def refresh(self) -> None:
        if self.network is None or self.network.buses.empty:
            self._show_empty_message()
            return

        self.figure.clear()
        ax = self.figure.add_subplot(111)

        buses = self.network.buses

        # draw lines
        if not self.network.lines.empty:
            for _, line in self.network.lines.iterrows():
                bus0 = line["bus0"]
                bus1 = line["bus1"]

                if bus0 in buses.index and bus1 in buses.index:
                    x0 = buses.at[bus0, "x"]
                    y0 = buses.at[bus0, "y"]
                    x1 = buses.at[bus1, "x"]
                    y1 = buses.at[bus1, "y"]

                    if all(v == v for v in [x0, y0, x1, y1]):  # simple NaN check
                        ax.plot([x0, x1], [y0, y1], linewidth=1)

        # draw buses
        valid_buses = buses.dropna(subset=["x", "y"])
        if not valid_buses.empty:
            ax.scatter(valid_buses["x"], valid_buses["y"], s=30)

        ax.set_title("Network Map")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(True)

        self.canvas.draw()

    def _show_empty_message(self) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.5, "No network loaded yet", ha="center", va="center")
        ax.set_axis_off()
        self.canvas.draw()