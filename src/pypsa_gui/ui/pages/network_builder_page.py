from __future__ import annotations

from typing import Any

from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg as FigureCanvas,
)
from matplotlib.backends.backend_qtagg import (
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
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


class NetworkBuilderPage(QWidget):
    create_empty_network_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.network: Any | None = None

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
        self.network = network

        if network is None:
            self.show_welcome_view()
            return

        self.show_editor_view()
        self.refresh_map()

    def show_welcome_view(self) -> None:
        self.page_stack.setCurrentWidget(
            self.welcome_page
        )

    def show_editor_view(self) -> None:
        self.page_stack.setCurrentWidget(
            self.editor_page
        )

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

        root_layout = QVBoxLayout(page)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        header_layout = QHBoxLayout()

        title = QLabel("Network Builder")
        title.setStyleSheet(
            """
            QLabel {
                font-size: 22px;
                font-weight: 600;
            }
            """
        )

        self.network_summary_label = QLabel(
            "0 buses · 0 lines · 0 links"
        )

        self.network_summary_label.setStyleSheet(
            """
            QLabel {
                color: #666666;
            }
            """
        )

        self.add_bus_button = QPushButton("Add bus")
        self.add_bus_button.setToolTip(
            "Bus placement will be implemented next."
        )
        self.add_bus_button.setEnabled(False)

        self.refresh_button = QPushButton("Refresh map")
        self.refresh_button.clicked.connect(
            self.refresh_map
        )

        header_layout.addWidget(title)
        header_layout.addWidget(
            self.network_summary_label
        )
        header_layout.addStretch()
        header_layout.addWidget(
            self.add_bus_button
        )
        header_layout.addWidget(
            self.refresh_button
        )

        root_layout.addLayout(header_layout)

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

        self.navigation_toolbar = NavigationToolbar(
            self.canvas,
            page,
        )

        root_layout.addWidget(
            self.navigation_toolbar
        )
        root_layout.addWidget(
            self.canvas,
            stretch=1,
        )

        self._create_map_axes()
        self.refresh_map()

        return page

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

    def refresh_map(self) -> None:
        if not hasattr(
            self,
            "map_axes",
        ):
            return

        self._create_map_axes()

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

            self._draw_buses()
            self._draw_connections()

        self.network_summary_label.setText(
            f"{bus_count} buses · "
            f"{line_count} lines · "
            f"{link_count} links"
        )

        self.canvas.draw_idle()

    def _draw_buses(self) -> None:
        if self.network is None:
            return

        buses = self.network.buses

        if buses.empty:
            return

        if (
            "x" not in buses.columns
            or "y" not in buses.columns
        ):
            return

        valid_buses = buses[
            buses["x"].notna()
            & buses["y"].notna()
        ]

        if valid_buses.empty:
            return

        plot_arguments: dict[str, Any] = {
            "s": 45,
            "zorder": 5,
        }

        if CARTOPY_AVAILABLE:
            plot_arguments["transform"] = (
                ccrs.PlateCarree()
            )

        self.map_axes.scatter(
            valid_buses["x"],
            valid_buses["y"],
            **plot_arguments,
        )

        for bus_name, bus in valid_buses.iterrows():
            annotation_arguments: dict[str, Any] = {
                "xy": (
                    bus["x"],
                    bus["y"],
                ),
                "xytext": (5, 5),
                "textcoords": "offset points",
                "fontsize": 8,
                "zorder": 6,
            }

            if CARTOPY_AVAILABLE:
                annotation_arguments["transform"] = (
                    ccrs.PlateCarree()
                )

            self.map_axes.annotate(
                str(bus_name),
                **annotation_arguments,
            )

    def _draw_connections(self) -> None:
        if self.network is None:
            return

        buses = self.network.buses

        if buses.empty:
            return

        self._draw_component_connections(
            self.network.lines,
            buses,
        )

        self._draw_component_connections(
            self.network.links,
            buses,
        )

    def _draw_component_connections(
        self,
        components,
        buses,
    ) -> None:
        if components.empty:
            return

        if (
            "bus0" not in components.columns
            or "bus1" not in components.columns
        ):
            return

        for _, component in components.iterrows():
            bus0_name = component["bus0"]
            bus1_name = component["bus1"]

            if (
                bus0_name not in buses.index
                or bus1_name not in buses.index
            ):
                continue

            bus0 = buses.loc[bus0_name]
            bus1 = buses.loc[bus1_name]

            if (
                bus0.get("x") is None
                or bus0.get("y") is None
                or bus1.get("x") is None
                or bus1.get("y") is None
            ):
                continue

            if (
                bus0[["x", "y"]].isna().any()
                or bus1[["x", "y"]].isna().any()
            ):
                continue

            plot_arguments: dict[str, Any] = {
                "linewidth": 1.2,
                "zorder": 4,
            }

            if CARTOPY_AVAILABLE:
                plot_arguments["transform"] = (
                    ccrs.PlateCarree()
                )

            self.map_axes.plot(
                [
                    bus0["x"],
                    bus1["x"],
                ],
                [
                    bus0["y"],
                    bus1["y"],
                ],
                **plot_arguments,
            )