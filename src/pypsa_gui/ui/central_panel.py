from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget

from pypsa_gui.models.session_view import PAGE_TO_SECTION
from pypsa_gui.ui.pages.buses_page import BusesPage
from pypsa_gui.ui.pages.component_page import ComponentPage
from pypsa_gui.ui.pages.overview_page import OverviewPage
from pypsa_gui.ui.pages.summary_page import SummaryPage


class PlaceholderPage(QWidget):
    def __init__(self, title: str) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        label = QLabel(f"{title} page placeholder")
        layout.addWidget(label)


class CentralPanel(QWidget):
    def __init__(
        self,
        enabled_sections: set[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.enabled_sections = enabled_sections or {
            "overview",
            "components",
            "analysis",
            "plots",
            "run",
        }

        self.stack = QStackedWidget()
        self.pages: dict[str, QWidget] = {}
        self._page_factories = self._build_page_factories()

        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)

        self.rebuild_pages(self.enabled_sections)

    def _build_page_factories(self) -> dict[str, Callable[[], QWidget]]:
        return {
            "Overview": OverviewPage,
            "Summary": SummaryPage,
            "Buses": BusesPage,
            "Generators": lambda: ComponentPage("generators"),
            "Loads": lambda: ComponentPage("loads"),
            "Lines": lambda: ComponentPage("lines"),
            "Links": lambda: ComponentPage("links"),
            "Stores": lambda: ComponentPage("stores"),
            "Storage Units": lambda: ComponentPage("storage_units"),
            "Global Constraints": lambda: ComponentPage("global_constraints"),
            "Prices": lambda: PlaceholderPage("Prices"),
            "Congestion": lambda: PlaceholderPage("Congestion"),
            "Storage": lambda: PlaceholderPage("Storage"),
            "Emissions": lambda: PlaceholderPage("Emissions"),
            "Network Map": lambda: PlaceholderPage("Network Map"),
            "Time Series": lambda: PlaceholderPage("Time Series"),
            "Capacities": lambda: PlaceholderPage("Capacities"),
            "Power Flow": lambda: PlaceholderPage("Power Flow"),
            "Optimisation": lambda: PlaceholderPage("Optimisation"),
            "Solver Settings": lambda: PlaceholderPage("Solver Settings"),
        }

    def rebuild_pages(self, enabled_sections: set[str]) -> None:
        self.enabled_sections = set(enabled_sections)
        self._clear_pages()

        for page_name, factory in self._page_factories.items():
            section_key = PAGE_TO_SECTION.get(page_name)
            if section_key not in self.enabled_sections:
                continue

            self._add_page(page_name, factory())

    def _clear_pages(self) -> None:
        self.pages.clear()

        while self.stack.count():
            widget = self.stack.widget(0)
            self.stack.removeWidget(widget)
            widget.deleteLater()

    def _add_page(self, name: str, widget: QWidget) -> None:
        self.pages[name] = widget
        self.stack.addWidget(widget)

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