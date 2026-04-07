from __future__ import annotations

from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from pypsa_gui.ui.widgets.pages.component_page import ComponentPage
from pypsa_gui.ui.widgets.pages.overview_page import OverviewPage
from pypsa_gui.ui.widgets.pages.plots_page import PlotsPage
from pypsa_gui.ui.widgets.pages.results_page import ResultsPage


class CentralPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)

        self.stack = QStackedWidget(self)

        self.pages: dict[str, QWidget] = {
            "Overview": OverviewPage(self),
            "Buses": ComponentPage("Buses", self),
            "Generators": ComponentPage("Generators", self),
            "Loads": ComponentPage("Loads", self),
            "Lines": ComponentPage("Lines", self),
            "Links": ComponentPage("Links", self),
            "Stores": ComponentPage("Stores", self),
            "Storage Units": ComponentPage("Storage Units", self),
            "Global Constraints": ComponentPage("Global Constraints", self),
            "Results": ResultsPage(self),
            "Plots": PlotsPage(self),
        }

        for page in self.pages.values():
            self.stack.addWidget(page)

        layout.addWidget(self.stack)

        self.show_page("Overview")

    def show_page(self, page_name: str) -> None:
        page = self.pages.get(page_name)
        if page is not None:
            self.stack.setCurrentWidget(page)