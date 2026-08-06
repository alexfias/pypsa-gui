from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pypsa_gui.models.network_location import NetworkLocation
from pypsa_gui.models.session_view import PAGE_TO_SECTION
from pypsa_gui.ui.pages.analysis.prices_page import PricesPage
from pypsa_gui.ui.pages.analysis.storage_page import StoragePage
from pypsa_gui.ui.pages.buses_page import BusesPage
from pypsa_gui.ui.pages.capacities_page import CapacitiesPage
from pypsa_gui.ui.pages.component_page import ComponentPage
from pypsa_gui.ui.pages.congestion_page import CongestionPage
from pypsa_gui.ui.pages.emissions_page import EmissionsPage
from pypsa_gui.ui.pages.network_builder_page import (
    NetworkBuilderPage,
)
from pypsa_gui.ui.pages.network_map_page import NetworkMapPage
from pypsa_gui.ui.pages.optimisation_page import OptimisationPage
from pypsa_gui.ui.pages.overview_page import OverviewPage
from pypsa_gui.ui.pages.pre_run_tools_page import PreRunToolsPage
from pypsa_gui.ui.pages.run.solver_settings_page import (
    SolverSettingsPage,
)
from pypsa_gui.ui.pages.scenario_builder_page import (
    ScenarioBuilderPage,
)
from pypsa_gui.ui.pages.summary_page import SummaryPage
from pypsa_gui.ui.pages.time_series_page import TimeSeriesPage


class PlaceholderPage(QWidget):
    def __init__(self, title: str) -> None:
        super().__init__()

        layout = QVBoxLayout(self)

        label = QLabel(f"{title} page placeholder")
        layout.addWidget(label)


class CentralPanel(QWidget):
    scenario_requested = Signal(object)
    create_empty_network_requested = Signal()
    run_optimisation_requested = Signal()

    new_network_requested = Signal()
    open_network_requested = Signal()
    save_network_requested = Signal()
    save_network_as_requested = Signal()
    network_modified = Signal()

    def __init__(
        self,
        enabled_sections: set[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.enabled_sections = enabled_sections or {
            "overview",
            "build",
            "components",
            "analysis",
            "plots",
            "run",
            "research_modules",
        }

        self.stack = QStackedWidget()
        self.pages: dict[str, QWidget] = {}

        self._core_page_factories = self._build_page_factories()
        self._module_pages: dict[str, QWidget] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)

        self.rebuild_pages(self.enabled_sections)

    def _build_page_factories(
        self,
    ) -> dict[str, Callable[[], QWidget]]:
        return {
            "Overview": OverviewPage,
            "Scenario Builder": ScenarioBuilderPage,
            "Network Builder": NetworkBuilderPage,
            "Summary": SummaryPage,
            "Buses": BusesPage,
            "Generators": lambda: ComponentPage("generators"),
            "Loads": lambda: ComponentPage("loads"),
            "Lines": lambda: ComponentPage("lines"),
            "Links": lambda: ComponentPage("links"),
            "Stores": lambda: ComponentPage("stores"),
            "Storage Units": lambda: ComponentPage(
                "storage_units"
            ),
            "Global Constraints": lambda: ComponentPage(
                "global_constraints"
            ),
            "Prices": PricesPage,
            "Congestion": CongestionPage,
            "Storage": StoragePage,
            "Emissions": EmissionsPage,
            "Network Map": NetworkMapPage,
            "Time Series": TimeSeriesPage,
            "Capacities": CapacitiesPage,
            "Power Flow": lambda: PlaceholderPage(
                "Power Flow"
            ),
            "Optimisation": OptimisationPage,
            "Solver Settings": SolverSettingsPage,
            "Pre-Run Tools": PreRunToolsPage,
        }

    def rebuild_pages(
        self,
        enabled_sections: set[str],
    ) -> None:
        self.enabled_sections = set(enabled_sections)
        self._clear_pages()

        for page_name, factory in (
            self._core_page_factories.items()
        ):
            section_key = PAGE_TO_SECTION.get(page_name)

            if section_key not in self.enabled_sections:
                continue

            self._add_page(
                page_name,
                factory(),
            )

        # Research-module pages are recreated separately
        # by MainWindow.

    def _clear_pages(self) -> None:
        while self.stack.count():
            widget = self.stack.widget(0)

            self.stack.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()

        self.pages.clear()
        self._module_pages.clear()

    def _add_page(
        self,
        name: str,
        widget: QWidget,
    ) -> None:
        self.pages[name] = widget
        self.stack.addWidget(widget)

        if (
            name == "Overview"
            and isinstance(widget, OverviewPage)
        ):
            widget.open_component_requested.connect(
                self.open_component_from_overview
            )

        if (
            name == "Scenario Builder"
            and isinstance(widget, ScenarioBuilderPage)
        ):
            widget.scenario_requested.connect(
                self.scenario_requested.emit
            )

        if (
            name == "Network Builder"
            and isinstance(widget, NetworkBuilderPage)
        ):
            widget.create_empty_network_requested.connect(
                self.create_empty_network_requested.emit
            )
            widget.new_network_requested.connect(
                self.new_network_requested.emit
            )
            widget.open_network_requested.connect(
                self.open_network_requested.emit
            )
            widget.save_network_requested.connect(
                self.save_network_requested.emit
            )
            widget.save_network_as_requested.connect(
                self.save_network_as_requested.emit
            )
            widget.network_modified.connect(
                self.network_modified.emit
            )

        if (
            name == "Optimisation"
            and isinstance(widget, OptimisationPage)
        ):
            widget.run_optimisation_requested.connect(
                self.run_optimisation_requested.emit
            )

    def clear_module_pages(self) -> None:
        for page_name, widget in list(
            self._module_pages.items()
        ):
            if self.pages.get(page_name) is not widget:
                continue

            self.stack.removeWidget(widget)
            self.pages.pop(page_name, None)

            widget.setParent(None)
            widget.deleteLater()

        self._module_pages.clear()

    def add_module_page(
        self,
        name: str,
        widget: QWidget,
    ) -> None:
        if name in self.pages:
            return

        self._module_pages[name] = widget

        self._add_page(
            name,
            widget,
        )

    def set_current_page(
        self,
        name: str,
    ) -> None:
        widget = self.pages.get(name)

        if widget is not None:
            self.stack.setCurrentWidget(widget)

    def show_page(
        self,
        name: str,
    ) -> None:
        self.set_current_page(name)

    def update_network_dependent_pages(
        self,
        network: Any,
        locations: dict[str, NetworkLocation] | None = None,
    ) -> None:
        for page in self.pages.values():
            if isinstance(page, NetworkBuilderPage):
                page.set_network_context(
                    network=network,
                    locations=locations,
                )
            elif hasattr(page, "set_network"):
                page.set_network(network)
            elif hasattr(page, "update_from_network"):
                page.update_from_network(network)
            elif hasattr(page, "update_summary"):
                page.update_summary(network)

    def set_network(
        self,
        network: Any,
    ) -> None:
        self.update_network_dependent_pages(
            network=network,
            locations=None,
        )

    def set_network_context(
        self,
        network: Any,
        locations: dict[str, NetworkLocation] | None,
    ) -> None:
        self.update_network_dependent_pages(
            network=network,
            locations=locations,
        )

    def set_network_builder_project_state(
        self,
        name: str,
        is_modified: bool,
    ) -> None:
        page = self.pages.get(
            "Network Builder"
        )

        if isinstance(page, NetworkBuilderPage):
            page.set_project_state(
                name=name,
                is_modified=is_modified,
            )

    def refresh_optimisation_results_state(
        self,
    ) -> None:
        """
        Refresh the Optimisation page after a solve completed.

        This enables the PDF report button when solved results
        are available on the currently assigned network.
        """

        page = self.pages.get("Optimisation")

        if isinstance(page, OptimisationPage):
            page.refresh_results_state()

    def set_optimisation_running(
        self,
        running: bool,
    ) -> None:
        """
        Update the Optimisation page while a solve is running.
        """

        page = self.pages.get("Optimisation")

        if isinstance(page, OptimisationPage):
            page.set_optimisation_running(running)

    def open_component_from_overview(
        self,
        component_type: str,
        bus_name: str,
    ) -> None:
        page_name_by_component = {
            "buses": "Buses",
            "generators": "Generators",
            "loads": "Loads",
            "lines": "Lines",
            "links": "Links",
        }

        page_name = page_name_by_component.get(
            component_type
        )

        if page_name is None:
            return

        self.show_page(page_name)

        page = self.pages.get(page_name)

        if (
            page is not None
            and hasattr(page, "filter_by_bus")
        ):
            page.filter_by_bus(bus_name)
