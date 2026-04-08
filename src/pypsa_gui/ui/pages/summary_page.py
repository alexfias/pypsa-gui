from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
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

        self.snapshots_card = SummaryCard("Snapshots")
        self.buses_card = SummaryCard("Buses")
        self.generators_card = SummaryCard("Generators")
        self.loads_card = SummaryCard("Loads")
        self.lines_card = SummaryCard("Lines")
        self.links_card = SummaryCard("Links")
        self.stores_card = SummaryCard("Stores")
        self.storage_units_card = SummaryCard("Storage Units")
        self.figure = Figure(figsize=(4, 3))
        self.canvas = FigureCanvas(self.figure)

        grid = QGridLayout()
        grid.addWidget(self.snapshots_card, 0, 0)
        grid.addWidget(self.buses_card, 0, 1)
        grid.addWidget(self.generators_card, 0, 2)
        grid.addWidget(self.loads_card, 1, 0)
        grid.addWidget(self.lines_card, 1, 1)
        grid.addWidget(self.links_card, 1, 2)
        grid.addWidget(self.stores_card, 2, 0)
        grid.addWidget(self.storage_units_card, 2, 1)


        layout = QVBoxLayout(self)
        layout.addLayout(grid)
        layout.addWidget(self.canvas)
        layout.addStretch()





    def update_summary(self, network) -> None:
        if network is None:
            self.snapshots_card.set_value("-")
            self.buses_card.set_value("-")
            self.generators_card.set_value("-")
            self.loads_card.set_value("-")
            self.lines_card.set_value("-")
            self.links_card.set_value("-")
            self.stores_card.set_value("-")
            self.storage_units_card.set_value("-")
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

    def _plot_system_cost(self, network) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        if hasattr(network, "objective") and network.objective is not None:
            cost = network.objective
            ax.bar(["System Cost"], [cost])
            ax.set_ylabel("Cost")
            ax.set_title("Total System Cost")
        else:
            ax.text(0.5, 0.5, "No optimisation results",
                    ha="center", va="center")

        self.canvas.draw()

    def _clear_plot(self) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        self.canvas.draw()