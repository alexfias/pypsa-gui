from __future__ import annotations

from enum import Enum
from math import asin, cos, radians, sin, sqrt
from typing import Any
from uuid import uuid4

from matplotlib.backend_bases import MouseButton
from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg as FigureCanvas,
)
from matplotlib.backends.backend_qtagg import (
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QActionGroup
from pypsa_gui.models.network_location import NetworkLocation
from pypsa_gui.ui.pages.network_builder.location_editor import (
    LocationEditor,
)

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    CARTOPY_AVAILABLE = True
except ImportError:
    ccrs = None
    cfeature = None
    CARTOPY_AVAILABLE = False


class TopologyToolMode(str, Enum):
    SELECT = "select"
    ADD_LOCATION = "add_location"
    ADD_LINE = "add_line"
    ADD_LINK = "add_link"
    DELETE = "delete"
    PAN = "pan"
    ZOOM = "zoom"


class NetworkBuilderPage(QWidget):
    create_empty_network_requested = Signal()

    new_network_requested = Signal()
    open_network_requested = Signal()
    save_network_requested = Signal()
    save_network_as_requested = Signal()
    network_modified = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.network: Any | None = None
        self.locations: dict[str, NetworkLocation] = {}
        self.project_name = "Untitled Network"
        self.project_is_modified = False
        self.topology_tool_mode = TopologyToolMode.SELECT
        self.pending_connection_location: str | None = None
        self.selected_location_id: str | None = None

        self.page_stack = QStackedWidget(self)

        self.welcome_page = self._create_welcome_page()
        self.editor_page = self._create_editor_page()

        self.page_stack.addWidget(self.welcome_page)
        self.page_stack.addWidget(self.editor_page)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.page_stack)

        self.show_welcome_view()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_network(
        self,
        network: Any | None,
    ) -> None:
        self.set_network_context(
            network=network,
            locations=None,
        )

    def set_network_context(
        self,
        network: Any | None,
        locations: dict[str, NetworkLocation] | None,
    ) -> None:
        self.network = network

        if network is None:
            self.locations = {}
            self.selected_location_id = None

            if hasattr(
                self,
                "location_editor",
            ):
                self.location_editor.set_context(
                    network=None,
                    location=None,
                )

            self.show_welcome_view()
            return

        if locations is None:
            self.locations = self._infer_locations_from_network(
                network
            )
        else:
            self.locations = locations
            self._ensure_locations_for_unassigned_buses()

        self.selected_location_id = None
        self.location_editor.set_context(
            network=None,
            location=None,
        )
        self.show_editor_view()
        self.show_geographic_editor()
        self.refresh_map()

    def set_project_state(
        self,
        name: str,
        is_modified: bool,
    ) -> None:
        self.project_name = name or "Untitled Network"
        self.project_is_modified = is_modified
        self._refresh_project_title()

    def _refresh_project_title(self) -> None:
        if not hasattr(
            self,
            "network_title_label",
        ):
            return

        suffix = "*" if self.project_is_modified else ""
        self.network_title_label.setText(
            f"{self.project_name}{suffix}"
        )

    def _mark_network_modified(self) -> None:
        self.project_is_modified = True
        self._refresh_project_title()
        self.network_modified.emit()

    def show_welcome_view(self) -> None:
        self.page_stack.setCurrentWidget(
            self.welcome_page
        )

    def show_editor_view(self) -> None:
        self.page_stack.setCurrentWidget(
            self.editor_page
        )

    def show_geographic_editor(self) -> None:
        if hasattr(
            self,
            "editor_stack",
        ):
            self.editor_stack.setCurrentWidget(
                self.geographic_editor_page
            )

        if self.network is not None:
            self.refresh_map()

    def open_location(
        self,
        location_id: str,
    ) -> None:
        if self.network is None:
            return

        location = self.locations.get(
            location_id
        )

        if location is None:
            return

        self.selected_location_id = location_id

        self.location_editor.set_context(
            network=self.network,
            location=location,
        )
        self.editor_stack.setCurrentWidget(
            self.location_editor
        )

    def _on_location_editor_modified(self) -> None:
        self._mark_network_modified()
        self.refresh_map()

    # ------------------------------------------------------------------
    # Welcome page
    # ------------------------------------------------------------------

    def _create_welcome_page(self) -> QWidget:
        page = QWidget(self)

        root_layout = QVBoxLayout(page)
        root_layout.setContentsMargins(32, 32, 32, 32)
        root_layout.setSpacing(24)

        title = QLabel("Network Builder")
        title.setStyleSheet(
            """
            QLabel {
                font-size: 26px;
                font-weight: 600;
            }
            """
        )

        description = QLabel(
            "Create a new PyPSA network from scratch or start "
            "from a predefined template."
        )
        description.setWordWrap(True)
        description.setStyleSheet(
            """
            QLabel {
                font-size: 14px;
                color: #555555;
            }
            """
        )

        root_layout.addWidget(title)
        root_layout.addWidget(description)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(20)

        empty_network_card = self._create_option_card(
            title="Create empty network",
            description=(
                "Start with a new PyPSA network and add buses, "
                "generators, loads, lines, storage, and other "
                "components manually."
            ),
            button_text="Create empty network",
            enabled=True,
        )

        template_card = self._create_option_card(
            title="Start from template",
            description=(
                "Create a network from a predefined teaching "
                "or research template."
            ),
            button_text="Choose template",
            enabled=False,
        )

        self.create_empty_network_button = (
            empty_network_card.findChild(
                QPushButton,
                "option_button",
            )
        )

        if self.create_empty_network_button is not None:
            self.create_empty_network_button.clicked.connect(
                self.create_empty_network_requested.emit
            )

        cards_layout.addWidget(empty_network_card)
        cards_layout.addWidget(template_card)

        root_layout.addLayout(cards_layout)

        root_layout.addItem(
            QSpacerItem(
                0,
                0,
                QSizePolicy.Policy.Minimum,
                QSizePolicy.Policy.Expanding,
            )
        )

        return page

    def _create_option_card(
        self,
        title: str,
        description: str,
        button_text: str,
        enabled: bool,
    ) -> QFrame:
        card = QFrame(self)
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setMinimumWidth(280)
        card.setMaximumWidth(440)
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        card.setStyleSheet(
            """
            QFrame {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 8px;
            }

            QLabel {
                border: none;
                background: transparent;
            }

            QPushButton {
                min-height: 34px;
                padding: 4px 14px;
            }
            """
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            """
            QLabel {
                font-size: 18px;
                font-weight: 600;
            }
            """
        )

        description_label = QLabel(description)
        description_label.setWordWrap(True)
        description_label.setMinimumHeight(80)
        description_label.setStyleSheet(
            """
            QLabel {
                color: #555555;
            }
            """
        )

        button = QPushButton(button_text)
        button.setObjectName("option_button")
        button.setEnabled(enabled)

        if not enabled:
            button.setToolTip(
                "Templates will be added in a later version."
            )

        layout.addWidget(title_label)
        layout.addWidget(description_label)
        layout.addWidget(button)

        return card

    # ------------------------------------------------------------------
    # Editor page
    # ------------------------------------------------------------------

    def _create_editor_page(self) -> QWidget:
        page = QWidget(self)

        outer_layout = QVBoxLayout(page)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.editor_stack = QStackedWidget(page)

        self.geographic_editor_page = QWidget(
            self.editor_stack
        )
        root_layout = QVBoxLayout(
            self.geographic_editor_page
        )
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(10)

        header_layout = QHBoxLayout()

        self.network_title_label = QLabel(
            "Untitled Network"
        )
        self.network_title_label.setStyleSheet(
            """
            QLabel {
                font-size: 22px;
                font-weight: 600;
            }
            """
        )

        self.network_summary_label = QLabel(
            "0 locations · 0 buses · 0 lines · 0 links"
        )
        self.network_summary_label.setStyleSheet(
            """
            QLabel {
                color: #666666;
            }
            """
        )

        header_layout.addWidget(
            self.network_title_label
        )
        header_layout.addWidget(
            self.network_summary_label
        )
        header_layout.addStretch()

        root_layout.addLayout(header_layout)

        self.project_toolbar = self._create_project_toolbar(
            page
        )
        root_layout.addWidget(
            self.project_toolbar
        )

        self.topology_toolbar = (
            self._create_topology_toolbar(page)
        )
        root_layout.addWidget(
            self.topology_toolbar
        )

        self.tool_status_label = QLabel()
        self.tool_status_label.setWordWrap(True)
        self.tool_status_label.setStyleSheet(
            """
            QLabel {
                padding: 7px 10px;
                color: #444444;
                background-color: #f3f3f3;
                border: 1px solid #d8d8d8;
                border-radius: 4px;
            }
            """
        )

        root_layout.addWidget(
            self.tool_status_label
        )

        if not CARTOPY_AVAILABLE:
            warning = QLabel(
                "Cartopy is not installed. The coordinate grid "
                "is available, but coastlines cannot be displayed. "
                "Install the optional map dependencies to show the "
                "world map."
            )
            warning.setWordWrap(True)
            warning.setStyleSheet(
                """
                QLabel {
                    padding: 8px;
                    background-color: #fff4ce;
                    border: 1px solid #e5c365;
                    border-radius: 4px;
                }
                """
            )

            root_layout.addWidget(warning)

        self.figure = Figure(
            figsize=(9, 5),
            tight_layout=True,
        )

        self.canvas = FigureCanvas(
            self.figure
        )
        self.canvas.mpl_connect(
            "button_press_event",
            self._on_map_clicked,
        )

        self.navigation_toolbar = NavigationToolbar(
            self.canvas,
            page,
        )
        self.navigation_toolbar.setVisible(False)

        root_layout.addWidget(
            self.canvas,
            stretch=1,
        )

        self._create_map_axes()
        self.refresh_map()

        self._set_topology_tool_mode(
            TopologyToolMode.SELECT
        )
        self._refresh_project_title()

        self.location_editor = LocationEditor(
            self.editor_stack
        )
        self.location_editor.back_requested.connect(
            self.show_geographic_editor
        )
        self.location_editor.network_modified.connect(
            self._on_location_editor_modified
        )

        self.editor_stack.addWidget(
            self.geographic_editor_page
        )
        self.editor_stack.addWidget(
            self.location_editor
        )
        self.editor_stack.setCurrentWidget(
            self.geographic_editor_page
        )

        outer_layout.addWidget(
            self.editor_stack
        )

        return page

    # ------------------------------------------------------------------
    # Project toolbar
    # ------------------------------------------------------------------

    def _create_project_toolbar(
        self,
        parent: QWidget,
    ) -> QToolBar:
        toolbar = QToolBar(
            "Project tools",
            parent,
        )
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )

        new_action = QAction(
            "＋  New",
            toolbar,
        )
        new_action.setToolTip(
            "Create a new network."
        )
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(
            self.new_network_requested.emit
        )
        toolbar.addAction(
            new_action
        )

        open_action = QAction(
            "▣  Open",
            toolbar,
        )
        open_action.setToolTip(
            "Open an existing PyPSA network."
        )
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(
            self.open_network_requested.emit
        )
        toolbar.addAction(
            open_action
        )

        toolbar.addSeparator()

        save_action = QAction(
            "💾  Save",
            toolbar,
        )
        save_action.setToolTip(
            "Save the current network."
        )
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(
            self.save_network_requested.emit
        )
        toolbar.addAction(
            save_action
        )

        save_as_action = QAction(
            "💾  Save As",
            toolbar,
        )
        save_as_action.setToolTip(
            "Save the current network under a new name."
        )
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(
            self.save_network_as_requested.emit
        )
        toolbar.addAction(
            save_as_action
        )

        return toolbar

    # ------------------------------------------------------------------
    # Topology toolbar
    # ------------------------------------------------------------------

    def _create_topology_toolbar(
        self,
        parent: QWidget,
    ) -> QToolBar:
        toolbar = QToolBar(
            "Topology tools",
            parent,
        )

        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )

        self.topology_action_group = QActionGroup(
            toolbar
        )
        self.topology_action_group.setExclusive(True)

        self.select_action = self._create_topology_action(
            toolbar=toolbar,
            text="↖  Select",
            tooltip=(
                "Select a location, line, or link and inspect "
                "its properties."
            ),
            mode=TopologyToolMode.SELECT,
            shortcut="S",
        )

        self.add_location_action = self._create_topology_action(
            toolbar=toolbar,
            text="●  Location",
            tooltip=(
                "Place a geographical location with one default "
                "electricity bus."
            ),
            mode=TopologyToolMode.ADD_LOCATION,
            shortcut="B",
        )

        toolbar.addSeparator()

        self.add_line_action = self._create_topology_action(
            toolbar=toolbar,
            text="━  Line",
            tooltip=(
                "Create an electrical line between two buses."
            ),
            mode=TopologyToolMode.ADD_LINE,
            shortcut="L",
        )

        self.add_link_action = self._create_topology_action(
            toolbar=toolbar,
            text="⇄  Link",
            tooltip=(
                "Create a controllable link between two buses."
            ),
            mode=TopologyToolMode.ADD_LINK,
            shortcut="K",
        )

        toolbar.addSeparator()

        self.delete_action = self._create_topology_action(
            toolbar=toolbar,
            text="⌫  Delete",
            tooltip=(
                "Delete a selected topology component."
            ),
            mode=TopologyToolMode.DELETE,
            shortcut="Delete",
        )

        toolbar.addSeparator()

        self.pan_action = self._create_topology_action(
            toolbar=toolbar,
            text="✋  Pan",
            tooltip="Pan the map.",
            mode=TopologyToolMode.PAN,
            shortcut="P",
        )

        self.zoom_action = self._create_topology_action(
            toolbar=toolbar,
            text="🔍  Zoom",
            tooltip="Zoom to a rectangular area.",
            mode=TopologyToolMode.ZOOM,
            shortcut="Z",
        )

        home_action = QAction(
            "⌂  Home",
            toolbar,
        )
        home_action.setToolTip(
            "Reset the map to the full world view."
        )
        home_action.setStatusTip(
            "Reset the map to the full world view."
        )
        home_action.triggered.connect(
            self._reset_map_view
        )
        toolbar.addAction(
            home_action
        )

        toolbar.addSeparator()

        refresh_action = QAction(
            "⟳  Refresh",
            toolbar,
        )
        refresh_action.setToolTip(
            "Refresh the network map."
        )
        refresh_action.setStatusTip(
            "Refresh the network map."
        )
        refresh_action.triggered.connect(
            self.refresh_map
        )

        toolbar.addAction(
            refresh_action
        )

        self.select_action.setChecked(True)

        return toolbar

    def _create_topology_action(
        self,
        toolbar: QToolBar,
        text: str,
        tooltip: str,
        mode: TopologyToolMode,
        shortcut: str,
    ) -> QAction:
        action = QAction(
            text,
            toolbar,
        )

        action.setCheckable(True)
        action.setToolTip(tooltip)
        action.setStatusTip(tooltip)
        action.setShortcut(shortcut)

        action.triggered.connect(
            lambda checked, selected_mode=mode: (
                self._on_topology_action_triggered(
                    checked=checked,
                    mode=selected_mode,
                )
            )
        )

        self.topology_action_group.addAction(
            action
        )
        toolbar.addAction(
            action
        )

        return action

    def _on_topology_action_triggered(
        self,
        checked: bool,
        mode: TopologyToolMode,
    ) -> None:
        if not checked:
            return

        self._set_topology_tool_mode(
            mode
        )

    def _set_topology_tool_mode(
        self,
        mode: TopologyToolMode,
    ) -> None:
        self.pending_connection_location = None

        if hasattr(
            self,
            "navigation_toolbar",
        ):
            self._deactivate_matplotlib_navigation()

            if mode == TopologyToolMode.PAN:
                self.navigation_toolbar.pan()
            elif mode == TopologyToolMode.ZOOM:
                self.navigation_toolbar.zoom()

        self.topology_tool_mode = mode

        instructions = {
            TopologyToolMode.SELECT: (
                "Mode: Select — click a location to select it; "
                "double-click to open its internal topology."
            ),
            TopologyToolMode.ADD_LOCATION: (
                "Mode: Add location — click anywhere on the map "
                "to place a location with a default electricity bus."
            ),
            TopologyToolMode.ADD_LINE: (
                "Mode: Add line — select the first location."
            ),
            TopologyToolMode.ADD_LINK: (
                "Mode: Add link — select the first location."
            ),
            TopologyToolMode.DELETE: (
                "Mode: Delete — click a location, line, or link "
                "to remove it."
            ),
            TopologyToolMode.PAN: (
                "Mode: Pan — drag the map to move the view."
            ),
            TopologyToolMode.ZOOM: (
                "Mode: Zoom — drag a rectangle to zoom in."
            ),
        }

        if hasattr(
            self,
            "tool_status_label",
        ):
            self.tool_status_label.setText(
                instructions[mode]
            )

        if not hasattr(
            self,
            "canvas",
        ):
            return

        if mode == TopologyToolMode.SELECT:
            self.canvas.setCursor(
                Qt.CursorShape.ArrowCursor
            )
        elif mode == TopologyToolMode.DELETE:
            self.canvas.setCursor(
                Qt.CursorShape.ForbiddenCursor
            )
        elif mode == TopologyToolMode.PAN:
            self.canvas.setCursor(
                Qt.CursorShape.OpenHandCursor
            )
        else:
            self.canvas.setCursor(
                Qt.CursorShape.CrossCursor
            )

    def _deactivate_matplotlib_navigation(self) -> None:
        if not hasattr(
            self,
            "navigation_toolbar",
        ):
            return

        mode_text = str(
            getattr(
                self.navigation_toolbar,
                "mode",
                "",
            )
        ).lower()

        if "pan" in mode_text:
            self.navigation_toolbar.pan()
        elif "zoom" in mode_text:
            self.navigation_toolbar.zoom()

    def _reset_map_view(self) -> None:
        self._deactivate_matplotlib_navigation()

        if CARTOPY_AVAILABLE:
            self.map_axes.set_global()
        else:
            self.map_axes.set_xlim(
                -180,
                180,
            )
            self.map_axes.set_ylim(
                -90,
                90,
            )

        self.canvas.draw_idle()

    # ------------------------------------------------------------------
    # Map interaction
    # ------------------------------------------------------------------

    def _on_map_clicked(
        self,
        event,
    ) -> None:
        if self.network is None:
            return

        if event.button != MouseButton.LEFT:
            return

        if event.inaxes is not self.map_axes:
            return

        if event.xdata is None or event.ydata is None:
            return

        if self.topology_tool_mode in {
            TopologyToolMode.PAN,
            TopologyToolMode.ZOOM,
        }:
            return

        if self.topology_tool_mode == TopologyToolMode.ADD_LOCATION:
            self._create_location_at(
                longitude=float(event.xdata),
                latitude=float(event.ydata),
            )
            return

        if self.topology_tool_mode == TopologyToolMode.SELECT:
            location_id = self._find_location_near_event(
                event
            )

            if location_id is None:
                self.selected_location_id = None
                self.tool_status_label.setText(
                    "No location selected."
                )
                self.refresh_map()
                return

            self.selected_location_id = location_id
            location = self.locations[location_id]

            if bool(
                getattr(
                    event,
                    "dblclick",
                    False,
                )
            ):
                self.open_location(
                    location_id
                )
                return

            self.tool_status_label.setText(
                f'Selected location "{location.name}". '
                "Double-click it to open the internal topology."
            )
            self.refresh_map()
            return

        if self.topology_tool_mode in {
            TopologyToolMode.ADD_LINE,
            TopologyToolMode.ADD_LINK,
        }:
            location_id = self._find_location_near_event(event)

            if location_id is None:
                self.tool_status_label.setText(
                    "Click directly on an existing location."
                )
                return

            self._handle_connection_location_click(location_id)

    def _find_location_near_event(
        self,
        event,
        tolerance_pixels: float = 18.0,
    ) -> str | None:
        if not self.locations:
            return None

        click_x = float(event.x)
        click_y = float(event.y)
        nearest_id: str | None = None
        nearest_distance = float("inf")

        for location_id, location in self.locations.items():
            display_x, display_y = self.map_axes.transData.transform(
                (location.longitude, location.latitude)
            )
            distance = sqrt(
                (display_x - click_x) ** 2
                + (display_y - click_y) ** 2
            )
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_id = location_id

        if nearest_distance > tolerance_pixels:
            return None

        return nearest_id

    def _handle_connection_location_click(
        self,
        location_id: str,
    ) -> None:
        location = self.locations[location_id]

        if self.pending_connection_location is None:
            self.pending_connection_location = location_id
            component_label = (
                "line"
                if self.topology_tool_mode == TopologyToolMode.ADD_LINE
                else "link"
            )
            self.tool_status_label.setText(
                f'Selected first location "{location.name}". '
                f"Select the second location for the {component_label}."
            )
            self.refresh_map()
            return

        first_location_id = self.pending_connection_location
        second_location_id = location_id

        if first_location_id == second_location_id:
            self.tool_status_label.setText(
                "The second location must be different from the first location."
            )
            return

        self.pending_connection_location = None
        first_location = self.locations[first_location_id]
        second_location = self.locations[second_location_id]
        component_label = (
            "line"
            if self.topology_tool_mode == TopologyToolMode.ADD_LINE
            else "link"
        )

        bus0 = self._choose_location_bus(
            first_location,
            endpoint_label="From",
            component_label=component_label,
        )
        if bus0 is None:
            self.refresh_map()
            return

        bus1 = self._choose_location_bus(
            second_location,
            endpoint_label="To",
            component_label=component_label,
        )
        if bus1 is None:
            self.refresh_map()
            return

        if bus0 == bus1:
            QMessageBox.warning(
                self,
                "Invalid Connection",
                "A connection must use two different PyPSA buses.",
            )
            self.refresh_map()
            return

        if self.topology_tool_mode == TopologyToolMode.ADD_LINE:
            self._create_line_between(bus0, bus1)
        else:
            self._create_link_between(bus0, bus1)

    def _choose_location_bus(
        self,
        location: NetworkLocation,
        endpoint_label: str,
        component_label: str,
    ) -> str | None:
        valid_bus_names = [
            bus_name
            for bus_name in location.bus_names
            if self.network is not None
            and bus_name in self.network.buses.index
        ]

        if not valid_bus_names:
            QMessageBox.warning(
                self,
                "Location Has No Bus",
                f'The location "{location.name}" has no available PyPSA bus.',
            )
            return None

        if len(valid_bus_names) == 1:
            return valid_bus_names[0]

        selected_bus, accepted = QInputDialog.getItem(
            self,
            f"Choose {endpoint_label} Bus",
            (
                f"{endpoint_label} location: {location.name}\n"
                f"Choose the internal bus for the {component_label}:"
            ),
            valid_bus_names,
            0,
            False,
        )
        if not accepted:
            return None

        return str(selected_bus)

    def _create_line_between(
        self,
        bus0: str,
        bus1: str,
    ) -> None:
        if self.network is None:
            return

        distance_km = self._distance_between_buses_km(
            bus0,
            bus1,
        )

        dialog = LineCreationDialog(
            network=self.network,
            bus0=bus0,
            bus1=bus1,
            suggested_name=self._next_component_name(
                component="line",
                base_name="Line",
            ),
            distance_km=distance_km,
            parent=self,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._set_topology_tool_mode(
                TopologyToolMode.ADD_LINE
            )
            return

        values = dialog.values()

        try:
            attributes = {
                "bus0": bus0,
                "bus1": bus1,
                "length": values["length"],
                "s_nom": values["s_nom"],
            }

            if values["type"]:
                attributes["type"] = values["type"]
            else:
                attributes.update(
                    {
                        "r": values["r_per_km"]
                        * values["length"],
                        "x": values["x_per_km"]
                        * values["length"],
                        "b": values["b_per_km"]
                        * values["length"],
                    }
                )

            self.network.add(
                "Line",
                values["name"],
                **attributes,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Add Line Failed",
                "Could not add the line:\n\n"
                f"{exc}",
            )
            return

        self._mark_network_modified()
        self.refresh_map()
        self.tool_status_label.setText(
            f'Added line "{values["name"]}" from '
            f'"{bus0}" to "{bus1}" '
            f'({values["length"]:.1f} km).'
        )

    def _create_link_between(
        self,
        bus0: str,
        bus1: str,
    ) -> None:
        if self.network is None:
            return

        distance_km = self._distance_between_buses_km(
            bus0,
            bus1,
        )

        dialog = LinkCreationDialog(
            bus0=bus0,
            bus1=bus1,
            suggested_name=self._next_component_name(
                component="link",
                base_name="Link",
            ),
            distance_km=distance_km,
            parent=self,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._set_topology_tool_mode(
                TopologyToolMode.ADD_LINK
            )
            return

        values = dialog.values()

        try:
            self.network.add(
                "Link",
                values["name"],
                bus0=bus0,
                bus1=bus1,
                p_nom=values["p_nom"],
                efficiency=values["efficiency"],
                carrier=values["carrier"],
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Add Link Failed",
                "Could not add the link:\n\n"
                f"{exc}",
            )
            return

        self._mark_network_modified()
        self.refresh_map()
        self.tool_status_label.setText(
            f'Added link "{values["name"]}" from '
            f'"{bus0}" to "{bus1}". '
            f"Straight-line distance: {distance_km:.1f} km."
        )

    def _distance_between_buses_km(
        self,
        bus0: str,
        bus1: str,
    ) -> float:
        if self.network is None:
            return 0.0

        first = self.network.buses.loc[bus0]
        second = self.network.buses.loc[bus1]

        return self._haversine_distance_km(
            longitude0=float(first["x"]),
            latitude0=float(first["y"]),
            longitude1=float(second["x"]),
            latitude1=float(second["y"]),
        )

    @staticmethod
    def _haversine_distance_km(
        longitude0: float,
        latitude0: float,
        longitude1: float,
        latitude1: float,
    ) -> float:
        earth_radius_km = 6371.0088

        latitude0_rad = radians(latitude0)
        latitude1_rad = radians(latitude1)
        latitude_delta = radians(latitude1 - latitude0)
        longitude_delta = radians(longitude1 - longitude0)

        haversine = (
            sin(latitude_delta / 2.0) ** 2
            + cos(latitude0_rad)
            * cos(latitude1_rad)
            * sin(longitude_delta / 2.0) ** 2
        )

        return (
            2.0
            * earth_radius_km
            * asin(min(1.0, sqrt(haversine)))
        )

    def _next_component_name(
        self,
        component: str,
        base_name: str,
    ) -> str:
        if self.network is None:
            return f"{base_name} 1"

        table = getattr(
            self.network,
            f"{component}s",
        )
        existing_names = set(
            table.index.astype(str)
        )

        index = 1

        while f"{base_name} {index}" in existing_names:
            index += 1

        return f"{base_name} {index}"

    def _create_location_at(
        self,
        longitude: float,
        latitude: float,
    ) -> None:
        if self.network is None:
            return

        longitude = max(-180.0, min(180.0, longitude))
        latitude = max(-90.0, min(90.0, latitude))
        suggested_name = self._next_location_name()

        location_name, accepted = QInputDialog.getText(
            self,
            "Add Location",
            (
                "Location name:\n\n"
                f"Longitude: {longitude:.4f}\n"
                f"Latitude: {latitude:.4f}\n\n"
                "A default electricity bus will be created inside this location."
            ),
            text=suggested_name,
        )
        if not accepted:
            return

        location_name = location_name.strip()
        if not location_name:
            QMessageBox.warning(
                self,
                "Invalid Location Name",
                "The location name cannot be empty.",
            )
            return

        if any(
            existing.name == location_name
            for existing in self.locations.values()
        ):
            QMessageBox.warning(
                self,
                "Location Already Exists",
                f'A location named "{location_name}" already exists.',
            )
            return

        bus_name = self._unique_default_bus_name(location_name)
        location_id = str(uuid4())

        try:
            self.network.add(
                "Bus",
                bus_name,
                carrier="AC",
                x=longitude,
                y=latitude,
            )
            self.network.buses.loc[bus_name, "location"] = location_id
            self.locations[location_id] = NetworkLocation(
                id=location_id,
                name=location_name,
                longitude=longitude,
                latitude=latitude,
                bus_names=[bus_name],
            )
        except Exception as exc:
            if bus_name in self.network.buses.index:
                self.network.remove("Bus", bus_name)
            QMessageBox.critical(
                self,
                "Add Location Failed",
                "Could not add the location:\n\n"
                f"{exc}",
            )
            return

        self._mark_network_modified()
        self.refresh_map()
        self.tool_status_label.setText(
            f'Added location "{location_name}" with default bus '
            f'"{bus_name}" at ({longitude:.4f}, {latitude:.4f}).'
        )

    def _next_location_name(self) -> str:
        existing_names = {
            location.name
            for location in self.locations.values()
        }
        index = 1
        while f"Location {index}" in existing_names:
            index += 1
        return f"Location {index}"

    def _unique_default_bus_name(
        self,
        location_name: str,
    ) -> str:
        if self.network is None:
            return f"{location_name} electricity"

        base_name = f"{location_name} electricity"
        if base_name not in self.network.buses.index:
            return base_name

        index = 2
        while f"{base_name} {index}" in self.network.buses.index:
            index += 1
        return f"{base_name} {index}"

    def _infer_locations_from_network(
        self,
        network: Any,
    ) -> dict[str, NetworkLocation]:
        locations: dict[str, NetworkLocation] = {}

        if network.buses.empty:
            return locations

        has_location_column = "location" in network.buses.columns

        for bus_name, bus in network.buses.iterrows():
            if bus[["x", "y"]].isna().any():
                continue

            raw_location_id = (
                bus.get("location")
                if has_location_column
                else None
            )
            location_id = (
                str(raw_location_id)
                if raw_location_id is not None
                and str(raw_location_id).strip()
                and str(raw_location_id).lower() != "nan"
                else str(uuid4())
            )

            if location_id not in locations:
                locations[location_id] = NetworkLocation(
                    id=location_id,
                    name=str(bus_name),
                    longitude=float(bus["x"]),
                    latitude=float(bus["y"]),
                    bus_names=[],
                )

            locations[location_id].bus_names.append(str(bus_name))
            network.buses.loc[bus_name, "location"] = location_id

        return locations

    def _ensure_locations_for_unassigned_buses(
        self,
    ) -> None:
        if self.network is None:
            return

        assigned_bus_names = {
            bus_name
            for location in self.locations.values()
            for bus_name in location.bus_names
        }

        for bus_name, bus in self.network.buses.iterrows():
            if str(bus_name) in assigned_bus_names:
                continue
            if bus[["x", "y"]].isna().any():
                continue

            location_id = str(uuid4())
            self.locations[location_id] = NetworkLocation(
                id=location_id,
                name=str(bus_name),
                longitude=float(bus["x"]),
                latitude=float(bus["y"]),
                bus_names=[str(bus_name)],
            )
            self.network.buses.loc[bus_name, "location"] = location_id

    # ------------------------------------------------------------------
    # Map creation
    # ------------------------------------------------------------------

    def _create_map_axes(self) -> None:
        self.figure.clear()

        if CARTOPY_AVAILABLE:
            self.map_axes = self.figure.add_subplot(
                111,
                projection=ccrs.PlateCarree(),
            )

            self.map_axes.set_global()

            self.map_axes.add_feature(
                cfeature.LAND,
                facecolor="#f0f0f0",
            )
            self.map_axes.add_feature(
                cfeature.OCEAN,
                facecolor="#dceef8",
            )
            self.map_axes.add_feature(
                cfeature.COASTLINE,
                linewidth=0.6,
            )
            self.map_axes.add_feature(
                cfeature.BORDERS,
                linewidth=0.3,
            )

            self.map_axes.gridlines(
                draw_labels=True,
                linewidth=0.3,
                linestyle="--",
                alpha=0.6,
            )
        else:
            self.map_axes = self.figure.add_subplot(
                111
            )

            self.map_axes.set_xlim(
                -180,
                180,
            )
            self.map_axes.set_ylim(
                -90,
                90,
            )
            self.map_axes.set_xlabel(
                "Longitude"
            )
            self.map_axes.set_ylabel(
                "Latitude"
            )
            self.map_axes.grid(
                True,
                linewidth=0.4,
                linestyle="--",
                alpha=0.6,
            )

        self.map_axes.set_title(
            "Network geography"
        )

    # ------------------------------------------------------------------
    # Map rendering
    # ------------------------------------------------------------------

    def refresh_map(
        self,
        preserve_view: bool = True,
    ) -> None:
        if not hasattr(
            self,
            "map_axes",
        ):
            return

        previous_view = None

        if preserve_view:
            previous_view = self._current_map_view()

        self._create_map_axes()

        if previous_view is not None:
            self._restore_map_view(
                previous_view
            )

        location_count = len(self.locations)
        bus_count = 0
        line_count = 0
        link_count = 0

        if self.network is not None:
            bus_count = len(
                self.network.buses
            )
            line_count = len(
                self.network.lines
            )
            link_count = len(
                self.network.links
            )

            self._draw_connections()
            self._draw_locations()

        self.network_summary_label.setText(
            f"{location_count} locations · "
            f"{bus_count} buses · "
            f"{line_count} lines · "
            f"{link_count} links"
        )

        self.canvas.draw_idle()

    def _current_map_view(
        self,
    ) -> tuple[float, float, float, float] | None:
        if not hasattr(
            self,
            "map_axes",
        ):
            return None

        try:
            if CARTOPY_AVAILABLE:
                extent = self.map_axes.get_extent(
                    crs=ccrs.PlateCarree()
                )

                return (
                    float(extent[0]),
                    float(extent[1]),
                    float(extent[2]),
                    float(extent[3]),
                )

            x_min, x_max = self.map_axes.get_xlim()
            y_min, y_max = self.map_axes.get_ylim()

            return (
                float(x_min),
                float(x_max),
                float(y_min),
                float(y_max),
            )

        except Exception:
            return None

    def _restore_map_view(
        self,
        view: tuple[float, float, float, float],
    ) -> None:
        x_min, x_max, y_min, y_max = view

        if CARTOPY_AVAILABLE:
            self.map_axes.set_extent(
                [
                    x_min,
                    x_max,
                    y_min,
                    y_max,
                ],
                crs=ccrs.PlateCarree(),
            )
            return

        self.map_axes.set_xlim(
            x_min,
            x_max,
        )
        self.map_axes.set_ylim(
            y_min,
            y_max,
        )

    def _draw_locations(self) -> None:
        if not self.locations:
            return

        location_items = list(self.locations.items())
        longitudes = [
            location.longitude
            for _, location in location_items
        ]
        latitudes = [
            location.latitude
            for _, location in location_items
        ]
        colours = []

        for location_id, _ in location_items:
            if (
                self.pending_connection_location
                == location_id
            ):
                colours.append("#d62728")
            elif self.selected_location_id == location_id:
                colours.append("#ff7f0e")
            else:
                colours.append("#1f77b4")

        plot_arguments: dict[str, Any] = {
            "s": 65,
            "c": colours,
            "zorder": 5,
        }
        if CARTOPY_AVAILABLE:
            plot_arguments["transform"] = ccrs.PlateCarree()

        self.map_axes.scatter(
            longitudes,
            latitudes,
            **plot_arguments,
        )

        for _, location in location_items:
            annotation_arguments: dict[str, Any] = {
                "xy": (
                    location.longitude,
                    location.latitude,
                ),
                "xytext": (5, 5),
                "textcoords": "offset points",
                "fontsize": 8,
                "zorder": 6,
            }
            if CARTOPY_AVAILABLE:
                annotation_arguments["transform"] = ccrs.PlateCarree()

            self.map_axes.annotate(
                location.name,
                **annotation_arguments,
            )

    def _draw_connections(self) -> None:
        if self.network is None:
            return

        self._draw_component_connections(self.network.lines)
        self._draw_component_connections(self.network.links)

    def _draw_component_connections(
        self,
        components,
    ) -> None:
        if components.empty:
            return
        if "bus0" not in components.columns or "bus1" not in components.columns:
            return

        for _, component in components.iterrows():
            location0 = self._location_for_bus(str(component["bus0"]))
            location1 = self._location_for_bus(str(component["bus1"]))
            if location0 is None or location1 is None:
                continue

            plot_arguments: dict[str, Any] = {
                "linewidth": 1.2,
                "zorder": 4,
            }
            if CARTOPY_AVAILABLE:
                plot_arguments["transform"] = ccrs.PlateCarree()

            self.map_axes.plot(
                [location0.longitude, location1.longitude],
                [location0.latitude, location1.latitude],
                **plot_arguments,
            )

    def _location_for_bus(
        self,
        bus_name: str,
    ) -> NetworkLocation | None:
        for location in self.locations.values():
            if bus_name in location.bus_names:
                return location
        return None


class LineCreationDialog(QDialog):
    def __init__(
        self,
        network: Any,
        bus0: str,
        bus1: str,
        suggested_name: str,
        distance_km: float,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.network = network

        self.setWindowTitle("Create Line")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        summary = QLabel(
            f"<b>{bus0}</b> → <b>{bus1}</b><br>"
            f"Geodesic distance: {distance_km:.1f} km"
        )
        layout.addWidget(summary)

        form = QFormLayout()

        self.name_edit = QLineEdit(suggested_name)

        self.length_spin = QDoubleSpinBox()
        self.length_spin.setRange(0.001, 100000.0)
        self.length_spin.setDecimals(2)
        self.length_spin.setSuffix(" km")
        self.length_spin.setValue(max(distance_km, 0.001))

        self.capacity_spin = QDoubleSpinBox()
        self.capacity_spin.setRange(0.0, 1_000_000.0)
        self.capacity_spin.setDecimals(2)
        self.capacity_spin.setSuffix(" MVA")
        self.capacity_spin.setValue(1000.0)

        self.type_combo = QComboBox()
        self.type_combo.addItem(
            "Custom parameters",
            "",
        )

        line_types = getattr(
            network,
            "line_types",
            None,
        )

        if line_types is not None:
            for line_type in line_types.index.astype(str):
                self.type_combo.addItem(
                    line_type,
                    line_type,
                )

        self.r_per_km_spin = QDoubleSpinBox()
        self.r_per_km_spin.setRange(0.0, 1000.0)
        self.r_per_km_spin.setDecimals(6)
        self.r_per_km_spin.setSuffix(" Ω/km")
        self.r_per_km_spin.setValue(0.03)

        self.x_per_km_spin = QDoubleSpinBox()
        self.x_per_km_spin.setRange(0.0, 1000.0)
        self.x_per_km_spin.setDecimals(6)
        self.x_per_km_spin.setSuffix(" Ω/km")
        self.x_per_km_spin.setValue(0.30)

        self.b_per_km_spin = QDoubleSpinBox()
        self.b_per_km_spin.setRange(0.0, 1000.0)
        self.b_per_km_spin.setDecimals(9)
        self.b_per_km_spin.setSuffix(" S/km")
        self.b_per_km_spin.setValue(0.0)

        form.addRow(
            "Name",
            self.name_edit,
        )
        form.addRow(
            "Length",
            self.length_spin,
        )
        form.addRow(
            "Nominal capacity",
            self.capacity_spin,
        )
        form.addRow(
            "PyPSA line type",
            self.type_combo,
        )
        form.addRow(
            "Resistance",
            self.r_per_km_spin,
        )
        form.addRow(
            "Reactance",
            self.x_per_km_spin,
        )
        form.addRow(
            "Susceptance",
            self.b_per_km_spin,
        )

        layout.addLayout(form)

        note = QLabel(
            "The length is calculated automatically from the bus "
            "coordinates. It can be edited to represent a routed "
            "corridor. Selecting a PyPSA standard type lets PyPSA "
            "derive the electrical parameters from its type library."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(
            self._validate_and_accept
        )
        buttons.rejected.connect(
            self.reject
        )
        layout.addWidget(buttons)

        self.type_combo.currentIndexChanged.connect(
            self._update_custom_field_state
        )
        self._update_custom_field_state()

    def _update_custom_field_state(self) -> None:
        custom = not bool(
            self.type_combo.currentData()
        )

        self.r_per_km_spin.setEnabled(custom)
        self.x_per_km_spin.setEnabled(custom)
        self.b_per_km_spin.setEnabled(custom)

    def _validate_and_accept(self) -> None:
        name = self.name_edit.text().strip()

        if not name:
            QMessageBox.warning(
                self,
                "Invalid Line Name",
                "The line name cannot be empty.",
            )
            return

        if name in self.network.lines.index:
            QMessageBox.warning(
                self,
                "Line Already Exists",
                f'A line named "{name}" already exists.',
            )
            return

        self.accept()

    def values(self) -> dict[str, Any]:
        return {
            "name": self.name_edit.text().strip(),
            "length": self.length_spin.value(),
            "s_nom": self.capacity_spin.value(),
            "type": str(
                self.type_combo.currentData()
            ),
            "r_per_km": self.r_per_km_spin.value(),
            "x_per_km": self.x_per_km_spin.value(),
            "b_per_km": self.b_per_km_spin.value(),
        }


class LinkCreationDialog(QDialog):
    def __init__(
        self,
        bus0: str,
        bus1: str,
        suggested_name: str,
        distance_km: float,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle("Create Link")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        summary = QLabel(
            f"<b>{bus0}</b> → <b>{bus1}</b><br>"
            f"Straight-line distance: {distance_km:.1f} km"
        )
        layout.addWidget(summary)

        form = QFormLayout()

        self.name_edit = QLineEdit(suggested_name)

        self.capacity_spin = QDoubleSpinBox()
        self.capacity_spin.setRange(0.0, 1_000_000.0)
        self.capacity_spin.setDecimals(2)
        self.capacity_spin.setSuffix(" MW")
        self.capacity_spin.setValue(1000.0)

        self.efficiency_spin = QDoubleSpinBox()
        self.efficiency_spin.setRange(0.0, 1.0)
        self.efficiency_spin.setDecimals(4)
        self.efficiency_spin.setSingleStep(0.01)
        self.efficiency_spin.setValue(1.0)

        self.carrier_edit = QLineEdit("DC")

        form.addRow(
            "Name",
            self.name_edit,
        )
        form.addRow(
            "Nominal capacity",
            self.capacity_spin,
        )
        form.addRow(
            "Efficiency",
            self.efficiency_spin,
        )
        form.addRow(
            "Carrier",
            self.carrier_edit,
        )

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(
            self._validate_and_accept
        )
        buttons.rejected.connect(
            self.reject
        )
        layout.addWidget(buttons)

    def _validate_and_accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(
                self,
                "Invalid Link Name",
                "The link name cannot be empty.",
            )
            return

        self.accept()

    def values(self) -> dict[str, Any]:
        return {
            "name": self.name_edit.text().strip(),
            "p_nom": self.capacity_spin.value(),
            "efficiency": self.efficiency_spin.value(),
            "carrier": self.carrier_edit.text().strip(),
        }
