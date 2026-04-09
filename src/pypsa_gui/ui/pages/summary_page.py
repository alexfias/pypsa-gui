from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget, QScrollArea, QLayout

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class SummaryCard(QWidget):
    def __init__(self, title: str, value: str = "-", parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignCenter)

        self.value_label = QLabel(value)
        self.value_label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class SummaryPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        container = QWidget()
        self.scroll.setWidget(container)

        outer_layout = QVBoxLayout(self)
        outer_layout.addWidget(self.scroll)

        layout = QVBoxLayout(container)
        layout.setSizeConstraint(QLayout.SetMinAndMaxSize)

        self.snapshots_card = SummaryCard("Snapshots")
        self.buses_card = SummaryCard("Buses")
        self.generators_card = SummaryCard("Generators")
        self.loads_card = SummaryCard("Loads")
        self.lines_card = SummaryCard("Lines")
        self.links_card = SummaryCard("Links")
        self.stores_card = SummaryCard("Stores")
        self.storage_units_card = SummaryCard("Storage Units")

        grid = QGridLayout()
        grid.addWidget(self.snapshots_card, 0, 0)
        grid.addWidget(self.buses_card, 0, 1)
        grid.addWidget(self.generators_card, 0, 2)
        grid.addWidget(self.loads_card, 1, 0)
        grid.addWidget(self.lines_card, 1, 1)
        grid.addWidget(self.links_card, 1, 2)
        grid.addWidget(self.stores_card, 2, 0)
        grid.addWidget(self.storage_units_card, 2, 1)

        layout.addLayout(grid)

        self.system_cost_figure = Figure(figsize=(6, 3))
        self.system_cost_canvas = FigureCanvas(self.system_cost_figure)
        self.system_cost_canvas.setMinimumHeight(300)

        self.generation_figure = Figure(figsize=(6, 4))
        self.generation_canvas = FigureCanvas(self.generation_figure)
        self.generation_canvas.setMinimumHeight(350)

        layout.addWidget(QLabel("System Cost"))
        layout.addWidget(self.system_cost_canvas)

        layout.addWidget(QLabel("Generation by Carrier"))
        layout.addWidget(self.generation_canvas)

        layout.addStretch()

    def update_summary(self, network) -> None:
        if network is None:
            self._set_empty_cards()
            self._clear_system_cost_plot()
            self._clear_generation_plot()
            return

        self.snapshots_card.set_value(str(len(network.snapshots)))
        self.buses_card.set_value(str(len(network.buses)))
        self.generators_card.set_value(str(len(network.generators)))
        self.loads_card.set_value(str(len(network.loads)))
        self.lines_card.set_value(str(len(network.lines)))
        self.links_card.set_value(str(len(network.links)))
        self.stores_card.set_value(str(len(network.stores)))
        self.storage_units_card.set_value(str(len(network.storage_units)))

        self._plot_system_cost(network)
        self._plot_generation_by_carrier(network)

    def _set_empty_cards(self) -> None:
        self.snapshots_card.set_value("-")
        self.buses_card.set_value("-")
        self.generators_card.set_value("-")
        self.loads_card.set_value("-")
        self.lines_card.set_value("-")
        self.links_card.set_value("-")
        self.stores_card.set_value("-")
        self.storage_units_card.set_value("-")

    def _plot_system_cost(self, network) -> None:
        self.system_cost_figure.clear()
        ax = self.system_cost_figure.add_subplot(111)

        objective = getattr(network, "objective", None)

        if objective is None:
            ax.text(0.5, 0.5, "No optimisation results", ha="center", va="center")
            ax.set_xticks([])
            ax.set_yticks([])
        else:
            ax.bar(["System Cost"], [objective])
            ax.set_ylabel("Cost")
            ax.set_title("Total System Cost")

        self.system_cost_figure.tight_layout()
        self.system_cost_canvas.draw()

    def _clear_system_cost_plot(self) -> None:
        self.system_cost_figure.clear()
        ax = self.system_cost_figure.add_subplot(111)
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        ax.set_xticks([])
        ax.set_yticks([])
        self.system_cost_figure.tight_layout()
        self.system_cost_canvas.draw()

    def _plot_generation_by_carrier(self, network) -> None:
        self.generation_figure.clear()
        ax = self.generation_figure.add_subplot(111)

        generators = getattr(network, "generators", None)
        generators_t = getattr(network, "generators_t", None)

        if (
            generators is None
            or generators.empty
            or generators_t is None
            or not hasattr(generators_t, "p")
            or generators_t.p.empty
        ):
            ax.text(0.5, 0.5, "No generator dispatch data", ha="center", va="center")
            ax.set_xticks([])
            ax.set_yticks([])
            self.generation_figure.tight_layout()
            self.generation_canvas.draw()
            return

        dispatch = network.generators_t.p.sum(axis=0)
        carrier_series = network.generators.loc[dispatch.index, "carrier"]
        dispatch_by_carrier = dispatch.groupby(carrier_series).sum().sort_values(ascending=False)
        dispatch_by_carrier = dispatch_by_carrier.sort_values(ascending=False)

        if dispatch_by_carrier.empty:
            ax.text(0.5, 0.5, "No generation data", ha="center", va="center")
            ax.set_xticks([])
            ax.set_yticks([])
        else:
            ax.bar(dispatch_by_carrier.index.astype(str), dispatch_by_carrier.values)
            ax.set_title("Generation by Carrier")
            ax.set_ylabel("Total Generation")
            ax.tick_params(axis="x", rotation=45)

        self.generation_figure.tight_layout()
        self.generation_canvas.draw()

    def _clear_generation_plot(self) -> None:
        self.generation_figure.clear()
        ax = self.generation_figure.add_subplot(111)
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        ax.set_xticks([])
        ax.set_yticks([])
        self.generation_figure.tight_layout()
        self.generation_canvas.draw()