from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QTextEdit,
    QToolBar,
)

from pypsa_gui.ui.central_panel import CentralPanel

import pypsa

print("DEBUG CentralPanel imported from:", CentralPanel.__module__)
print("DEBUG CentralPanel file:", __import__(CentralPanel.__module__, fromlist=["*"]).__file__)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("pypsa-gui")
        self.resize(1200, 800)

        self._create_actions()
        self._create_menu_bar()
        self._create_tool_bar()
        self._create_central_widget()
        self._create_navigation_dock()
        self._create_log_dock()
        self._show_welcome_message()

    def _create_actions(self) -> None:
        self.open_action = QAction("Open Network...", self)
        self.open_action.setStatusTip("Open a PyPSA network file")
        self.open_action.triggered.connect(self.on_open_network)

        self.save_action = QAction("Save", self)
        self.save_action.setStatusTip("Save the current network")
        self.save_action.triggered.connect(self.on_save_network)

        self.exit_action = QAction("Exit", self)
        self.exit_action.setStatusTip("Close the application")
        self.exit_action.triggered.connect(self.close)

        self.run_optimisation_action = QAction("Run Optimisation", self)
        self.run_optimisation_action.setStatusTip("Run PyPSA optimisation")
        self.run_optimisation_action.triggered.connect(self.on_run_optimisation)

        self.run_power_flow_action = QAction("Run Power Flow", self)
        self.run_power_flow_action.setStatusTip("Run PyPSA power flow")
        self.run_power_flow_action.triggered.connect(self.on_run_power_flow)

        self.about_action = QAction("About", self)
        self.about_action.setStatusTip("About pypsa-gui")
        self.about_action.triggered.connect(self.on_about)

    def _create_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        run_menu = menu_bar.addMenu("Run")
        run_menu.addAction(self.run_optimisation_action)
        run_menu.addAction(self.run_power_flow_action)

        help_menu = menu_bar.addMenu("Help")
        help_menu.addAction(self.about_action)

    def _create_tool_bar(self) -> None:
        tool_bar = QToolBar("Main Toolbar", self)
        tool_bar.setMovable(False)
        self.addToolBar(tool_bar)

        tool_bar.addAction(self.open_action)
        tool_bar.addAction(self.save_action)
        tool_bar.addSeparator()
        tool_bar.addAction(self.run_optimisation_action)
        tool_bar.addAction(self.run_power_flow_action)

    def _create_central_widget(self) -> None:
        self.central_panel = CentralPanel(self)
        self.setCentralWidget(self.central_panel)

    def _create_navigation_dock(self) -> None:
        self.navigation_list = QListWidget(self)
        self.navigation_list.addItems(
            [
                "Overview",
                "Buses",
                "Generators",
                "Loads",
                "Lines",
                "Links",
                "Stores",
                "Storage Units",
                "Global Constraints",
                "Results",
                "Plots",
            ]
        )
        self.navigation_list.setCurrentRow(0)
        self.navigation_list.currentTextChanged.connect(self.on_navigation_changed)

        dock = QDockWidget("Navigation", self)
        dock.setWidget(self.navigation_list)
        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

    def _create_log_dock(self) -> None:
        self.log_output = QTextEdit(self)
        self.log_output.setReadOnly(True)

        dock = QDockWidget("Log", self)
        dock.setWidget(self.log_output)
        dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.TopDockWidgetArea
        )

        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)

    def _show_welcome_message(self) -> None:
        self.log("Application started.")
        self.log("Ready.")

    def log(self, message: str) -> None:
        self.log_output.append(message)
        self.statusBar().showMessage(message, 3000)

    def on_open_network(self) -> None:
        self.log("Loading demo PyPSA network...")

        try:
            network = pypsa.examples.ac_dc_meshed()  # built-in example
            self.network = network

            self.log("Network loaded successfully.")

            # pass to central panel
            self.central_panel.set_network(network)

        except Exception as e:
            self.log(f"Error loading network: {e}")

    def on_save_network(self) -> None:
        self.log("Save clicked.")

    def on_run_optimisation(self) -> None:
        self.log("Run Optimisation clicked.")

    def on_run_power_flow(self) -> None:
        self.log("Run Power Flow clicked.")

    def on_navigation_changed(self, item_text: str) -> None:
        if not item_text:
            return

        self.log(f"Navigation changed to: {item_text}")
        self.central_panel.show_page(item_text)

    def on_about(self) -> None:
        QMessageBox.about(
            self,
            "About pypsa-gui",
            "pypsa-gui\n\n"
            "An experimental desktop GUI for inspecting, editing, "
            "solving, and visualising PyPSA networks.",
        )
        
