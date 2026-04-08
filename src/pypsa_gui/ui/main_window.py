from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QTextEdit,
    QToolBar,
)

import pypsa

from pypsa_gui.services.network_io import (
    load_network_from_csv_folder,
    load_network_from_netcdf,
    save_network_to_netcdf,
)
from pypsa_gui.ui.central_panel import CentralPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.network: pypsa.Network | None = None
        self.current_file_path: str | None = None

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
        self.open_netcdf_action = QAction("Open NetCDF Network...", self)
        self.open_netcdf_action.setStatusTip("Open a PyPSA network from a .nc file")
        self.open_netcdf_action.triggered.connect(self.on_open_netcdf_network)

        self.open_csv_action = QAction("Open CSV Folder...", self)
        self.open_csv_action.setStatusTip("Open a PyPSA network from a CSV folder")
        self.open_csv_action.triggered.connect(self.on_open_csv_folder)

        self.save_action = QAction("Save As NetCDF...", self)
        self.save_action.setStatusTip("Save the current network as a .nc file")
        self.save_action.triggered.connect(self.save_as_netcdf)

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
        file_menu.addAction(self.open_netcdf_action)
        file_menu.addAction(self.open_csv_action)
        file_menu.addSeparator()
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

        tool_bar.addAction(self.open_netcdf_action)
        tool_bar.addAction(self.open_csv_action)
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
        self.log("No network loaded.")

    def log(self, message: str) -> None:
        self.log_output.append(message)
        self.statusBar().showMessage(message, 3000)

    def _set_network(self, network: pypsa.Network) -> None:
        self.network = network
        self.central_panel.set_network(network)

        self.log("Network loaded successfully.")
        self.log(
            f"Network summary: "
            f"{len(network.buses)} buses, "
            f"{len(network.generators)} generators, "
            f"{len(network.loads)} loads, "
            f"{len(network.lines)} lines, "
            f"{len(network.links)} links"
        )

    def on_open_netcdf_network(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open PyPSA NetCDF Network",
            "",
            "NetCDF Files (*.nc);;All Files (*)",
        )

        if not file_path:
            self.log("Open NetCDF cancelled.")
            return

        self.log(f"Loading NetCDF network: {file_path}")

        try:
            network = load_network_from_netcdf(file_path)
            self.current_file_path = file_path
            self._set_network(network)
        except Exception as exc:
            self.log(f"Error loading NetCDF network: {exc}")
            QMessageBox.critical(
                self,
                "Load Error",
                f"Could not load NetCDF network:\n{exc}",
            )

    def on_open_csv_folder(self) -> None:
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Open PyPSA CSV Folder",
            "",
        )

        if not folder_path:
            self.log("Open CSV folder cancelled.")
            return

        self.log(f"Loading CSV network from folder: {folder_path}")

        try:
            network = load_network_from_csv_folder(folder_path)
            self.current_file_path = None
            self._set_network(network)
        except Exception as exc:
            self.log(f"Error loading CSV folder: {exc}")
            QMessageBox.critical(
                self,
                "Load Error",
                f"Could not load CSV network:\n{exc}",
            )

    def save_as_netcdf(self) -> None:
        if self.network is None:
            QMessageBox.information(
                self,
                "No Network Loaded",
                "There is no network loaded to save.",
            )
            return

        suggested_path = self.current_file_path or str(Path.home() / "network.nc")

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PyPSA Network As NetCDF",
            suggested_path,
            "NetCDF Files (*.nc)",
        )

        if not file_path:
            self.log("Save cancelled.")
            return

        if not file_path.endswith(".nc"):
            file_path += ".nc"

        try:
            save_network_to_netcdf(self.network, file_path)
            self.current_file_path = file_path
            self.setWindowTitle(f"pypsa-gui - {Path(file_path).name}")
            self.log(f"Network saved to: {file_path}")
        except Exception as exc:
            self.log(f"Error saving network: {exc}")
            QMessageBox.critical(
                self,
                "Save Failed",
                f"Could not save network:\n\n{exc}",
            )

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