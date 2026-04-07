from __future__ import annotations

from PySide6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget

from pypsa_gui.ui.pages.buses_page import BusesPage


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
        self.network = None

        self._create_pages()

        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)

    def _add_page(self, name: str, widget: QWidget) -> None:
        self.pages[name] = widget
        self.stack.addWidget(widget)

    def _create_pages(self) -> None:
        self._add_page("Overview", PlaceholderPage("Overview"))
        self._add_page("Buses", BusesPage())
        self._add_page("Generators", PlaceholderPage("Generators"))
        self._add_page("Loads", PlaceholderPage("Loads"))
        self._add_page("Lines", PlaceholderPage("Lines"))
        self._add_page("Links", PlaceholderPage("Links"))
        self._add_page("Stores", PlaceholderPage("Stores"))
        self._add_page("Storage Units", PlaceholderPage("Storage Units"))
        self._add_page("Global Constraints", PlaceholderPage("Global Constraints"))
        self._add_page("Results", PlaceholderPage("Results"))
        self._add_page("Plots", PlaceholderPage("Plots"))

        self.show_page("Overview")

    def show_page(self, name: str) -> None:
        widget = self.pages.get(name)
        if widget is not None:
            self.stack.setCurrentWidget(widget)

    def set_network(self, network) -> None:
        self.network = network

        for page in self.pages.values():
            if hasattr(page, "set_network"):
                page.set_network(network)