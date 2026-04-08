from __future__ import annotations

from PySide6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget

from pypsa_gui.ui.pages.buses_page import BusesPage
from pypsa_gui.ui.pages.summary_page import SummaryPage
from pypsa_gui.ui.pages.overview_page import OverviewPage


class PlaceholderPage(QWidget):
    def __init__(self, title: str) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        label = QLabel(f"{title} page placeholder")
        layout.addWidget(label)


class CentralPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.stack = QStackedWidget()
        self.pages: dict[str, QWidget] = {}

        self._create_pages()

        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)

    def _add_page(self, name: str, widget: QWidget) -> None:
        self.pages[name] = widget
        self.stack.addWidget(widget)

    def _create_pages(self) -> None:
        self._add_page("Overview", OverviewPage())
        self._add_page("Summary", SummaryPage())
        self._add_page("Buses", BusesPage())
        self._add_page("Generators", PlaceholderPage("Generators"))
        self._add_page("Loads", PlaceholderPage("Loads"))
        self._add_page("Lines", PlaceholderPage("Lines"))
        self._add_page("Links", PlaceholderPage("Links"))
        self._add_page("Stores", PlaceholderPage("Stores"))
        self._add_page("Storage Units", PlaceholderPage("Storage Units"))
        self._add_page("Global Constraints", PlaceholderPage("Global Constraints"))
        self._add_page("Prices", PlaceholderPage("Prices"))
        self._add_page("Congestion", PlaceholderPage("Congestion"))
        self._add_page("Storage", PlaceholderPage("Storage"))
        self._add_page("Emissions", PlaceholderPage("Emissions"))
        self._add_page("Network Map", PlaceholderPage("Network Map"))
        self._add_page("Time Series", PlaceholderPage("Time Series"))
        self._add_page("Capacities", PlaceholderPage("Capacities"))
        self._add_page("Power Flow", PlaceholderPage("Power Flow"))
        self._add_page("Optimisation", PlaceholderPage("Optimisation"))
        self._add_page("Solver Settings", PlaceholderPage("Solver Settings"))

    def set_current_page(self, name: str) -> None:
        widget = self.pages.get(name)
        if widget is not None:
            self.stack.setCurrentWidget(widget)

    def show_page(self, name: str) -> None:
        self.set_current_page(name)

    def update_network_dependent_pages(self, network) -> None:
        for page in self.pages.values():
            if hasattr(page, "set_network"):
                page.set_network(network)
            elif hasattr(page, "update_from_network"):
                page.update_from_network(network)
            elif hasattr(page, "update_summary"):
                page.update_summary(network)

    def set_network(self, network) -> None:
        self.update_network_dependent_pages(network)