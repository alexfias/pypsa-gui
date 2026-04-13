from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QTextEdit,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QDialog,
)

import pypsa

from pypsa_gui.models.network_session import NetworkSession
from pypsa_gui.models.session_view import (
    NAVIGATION_STRUCTURE,
    SECTION_TITLES,
    SessionViewOptions,
)
from pypsa_gui.services.network_io import (
    load_network_from_csv_folder,
    load_network_from_netcdf,
    save_network_to_netcdf,
)
from pypsa_gui.services.network_store import NetworkStore
from pypsa_gui.services.optimisation import OptimisationRunner
from pypsa_gui.ui.central_panel import CentralPanel
from pypsa_gui.workers.optimisation_worker import OptimisationWorker
from pypsa_gui.ui.dialogs.workspace_selection_dialog import (
    WorkspaceSelectionDialog,
)

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.network_store = NetworkStore()

        self.optimisation_runner: OptimisationRunner | None = None
        self.optimisation_worker: OptimisationWorker | None = None
        self.optimisation_running = False

        self.setWindowTitle("pypsa-gui")
        self.resize(1200, 800)

        self._create_actions()
        self._create_menu_bar()
        self._create_tool_bar()
        self._create_central_widget()
        self._create_navigation_dock()
        self._create_loaded_networks_dock()
        self._create_log_dock()
        self._show_welcome_message()

    # ------------------------------------------------------------------
    # Active session helpers
    # ------------------------------------------------------------------

    def active_session(self) -> NetworkSession | None:
        return self.network_store.get_active_session()

    def active_network(self) -> pypsa.Network | None:
        session = self.active_session()
        return session.network if session is not None else None

    def active_file_path(self) -> Path | None:
        session = self.active_session()
        return session.source_path if session is not None else None

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

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

        self.cancel_optimisation_action = QAction("Cancel Optimisation", self)
        self.cancel_optimisation_action.setStatusTip(
            "Cancel the running optimisation"
        )
        self.cancel_optimisation_action.triggered.connect(
            self.on_cancel_optimisation
        )
        self.cancel_optimisation_action.setEnabled(False)

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
        run_menu.addAction(self.cancel_optimisation_action)
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
        tool_bar.addAction(self.cancel_optimisation_action)
        tool_bar.addAction(self.run_power_flow_action)

    def _create_central_widget(self) -> None:
        self.central_panel = CentralPanel(parent=self)
        self.setCentralWidget(self.central_panel)

    def _create_navigation_dock(self) -> None:
        self.navigation_tree = QTreeWidget(self)
        self.navigation_tree.setHeaderHidden(True)
        self.navigation_tree.itemClicked.connect(self.on_navigation_item_clicked)

        dock = QDockWidget("Navigation", self)
        dock.setWidget(self.navigation_tree)
        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        self._rebuild_navigation_tree()

    def _rebuild_navigation_tree(self) -> None:
        self.navigation_tree.blockSignals(True)
        self.navigation_tree.clear()

        session = self.active_session()
        if session is None:
            enabled_sections = {"overview", "components", "analysis", "plots", "run"}
        else:
            enabled_sections = session.view_options.enabled_sections

        section_order = ["overview", "components", "analysis", "plots", "run"]

        for section_key in section_order:
            if section_key not in enabled_sections:
                continue

            title = SECTION_TITLES[section_key]
            children = NAVIGATION_STRUCTURE[section_key]

            parent_item = QTreeWidgetItem([title])

            for child_name in children:
                QTreeWidgetItem(parent_item, [child_name])

            self.navigation_tree.addTopLevelItem(parent_item)

        self.navigation_tree.expandAll()
        self.navigation_tree.blockSignals(False)

    def _create_loaded_networks_dock(self) -> None:
        self.loaded_networks_list = QListWidget(self)
        self.loaded_networks_list.itemClicked.connect(
            self.on_loaded_network_clicked
        )

        dock = QDockWidget("Loaded Networks", self)
        dock.setWidget(self.loaded_networks_list)
        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def on_navigation_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        page_name = item.text(0)

        if item.childCount() > 0:
            self.log(f"Navigation category selected: {page_name}")
            return

        self.log(f"Navigation changed to: {page_name}")
        self.central_panel.set_current_page(page_name)

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

    # ------------------------------------------------------------------
    # Logging and UI state
    # ------------------------------------------------------------------

    def log(self, message: str) -> None:
        self.log_output.append(message)
        self.statusBar().showMessage(message, 3000)

    def _set_optimisation_running_state(self, is_running: bool) -> None:
        self.optimisation_running = is_running
        self.run_optimisation_action.setEnabled(not is_running)
        self.cancel_optimisation_action.setEnabled(is_running)
        self.run_power_flow_action.setEnabled(not is_running)

    # ------------------------------------------------------------------
    # Session and network handling
    # ------------------------------------------------------------------

    def _refresh_active_session_ui(self) -> None:
        session = self.active_session()

        self._rebuild_navigation_tree()

        if session is None:
            self.central_panel.rebuild_pages(
                {"overview", "components", "analysis", "plots", "run"}
            )
            self.setWindowTitle("pypsa-gui")
            self._refresh_loaded_networks_dock()
            return

        self.central_panel.rebuild_pages(session.view_options.enabled_sections)
        self.central_panel.update_network_dependent_pages(session.network)

        self.log("Network loaded successfully.")
        self.log(
            f"Network summary: "
            f"{len(session.network.buses)} buses, "
            f"{len(session.network.generators)} generators, "
            f"{len(session.network.loads)} loads, "
            f"{len(session.network.lines)} lines, "
            f"{len(session.network.links)} links"
        )

        if session.source_path is not None:
            self.setWindowTitle(f"pypsa-gui - {session.source_path.name}")
        else:
            self.setWindowTitle(f"pypsa-gui - {session.name}")

        self._refresh_loaded_networks_dock()

    def _add_network_session(
            self,
            network: pypsa.Network,
            source_path: Path | None,
            view_options: SessionViewOptions,
            name: str | None = None,
    ) -> None:
        session_name = name or (
            source_path.stem if source_path is not None else "unsaved network"
        )

        session = NetworkSession(
            id=str(uuid4()),
            name=session_name,
            network=network,
            source_path=source_path,
            is_modified=False,
            view_options=view_options,
        )

        self.network_store.add_session(session)
        self._refresh_active_session_ui()

    def _refresh_loaded_networks_dock(self) -> None:
        self.loaded_networks_list.blockSignals(True)
        self.loaded_networks_list.clear()

        active_session = self.active_session()

        for session in self.network_store.list_sessions():
            label = session.name
            if session is active_session:
                label = f"● {label}"

            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, session.id)
            self.loaded_networks_list.addItem(item)

        if active_session is not None:
            for row in range(self.loaded_networks_list.count()):
                item = self.loaded_networks_list.item(row)
                if item.data(Qt.ItemDataRole.UserRole) == active_session.id:
                    self.loaded_networks_list.setCurrentRow(row)
                    break

        self.loaded_networks_list.blockSignals(False)

    def on_loaded_network_clicked(self, item: QListWidgetItem) -> None:
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id is None:
            return

        if self.optimisation_running:
            self.log("Cannot switch sessions while optimisation is running.")
            return

        self.network_store.set_active_session(session_id)
        self._refresh_active_session_ui()

        session = self.active_session()
        if session is not None:
            self.log(f"Switched active session to: {session.name}")

    # ------------------------------------------------------------------
    # File loading and saving
    # ------------------------------------------------------------------

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

        view_options = self._ask_for_view_options()
        if view_options is None:
            self.log("Workspace selection cancelled.")
            return

        self.log(f"Loading NetCDF network: {file_path}")

        try:
            network = load_network_from_netcdf(file_path)
            self._add_network_session(
                network=network,
                source_path=Path(file_path),
                view_options=view_options,
            )
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

        view_options = self._ask_for_view_options()
        if view_options is None:
            self.log("Workspace selection cancelled.")
            return

        self.log(f"Loading CSV network from folder: {folder_path}")

        try:
            network = load_network_from_csv_folder(folder_path)
            self._add_network_session(
                network=network,
                source_path=Path(folder_path),
                view_options=view_options,
            )
        except Exception as exc:
            self.log(f"Error loading CSV folder: {exc}")
            QMessageBox.critical(
                self,
                "Load Error",
                f"Could not load CSV network:\n{exc}",
            )
            
    def save_as_netcdf(self) -> None:
        session = self.active_session()

        if session is None:
            QMessageBox.information(
                self,
                "No Network Loaded",
                "There is no network loaded to save.",
            )
            return

        default_path = (
            str(session.source_path)
            if session.source_path is not None and session.source_path.suffix == ".nc"
            else str(Path.home() / f"{session.name}.nc")
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PyPSA Network As NetCDF",
            default_path,
            "NetCDF Files (*.nc)",
        )

        if not file_path:
            self.log("Save cancelled.")
            return

        if not file_path.endswith(".nc"):
            file_path += ".nc"

        try:
            save_network_to_netcdf(session.network, file_path)
            session.source_path = Path(file_path)
            session.name = Path(file_path).stem
            session.is_modified = False
            self.setWindowTitle(f"pypsa-gui - {Path(file_path).name}")
            self._refresh_loaded_networks_dock()
            self.log(f"Network saved to: {file_path}")
        except Exception as exc:
            self.log(f"Error saving network: {exc}")
            QMessageBox.critical(
                self,
                "Save Failed",
                f"Could not save network:\n\n{exc}",
            )

    # ------------------------------------------------------------------
    # Optimisation
    # ------------------------------------------------------------------

    def on_run_optimisation(self) -> None:
        session = self.active_session()

        if session is None:
            QMessageBox.information(
                self,
                "No Network Loaded",
                "Please load a network before running optimisation.",
            )
            return

        if self.optimisation_running:
            self.log("Optimisation is already running.")
            return

        self.log(f"Starting optimisation for: {session.name}")

        self.optimisation_runner = OptimisationRunner(session.network)
        self.optimisation_worker = OptimisationWorker(self.optimisation_runner)

        self.optimisation_worker.finished_successfully.connect(
            self._on_optimisation_finished
        )
        self.optimisation_worker.failed.connect(self._on_optimisation_failed)
        self.optimisation_worker.finished.connect(
            self._on_optimisation_thread_finished
        )

        self._set_optimisation_running_state(True)
        self.optimisation_worker.start()

    def on_cancel_optimisation(self) -> None:
        if not self.optimisation_running or self.optimisation_runner is None:
            self.log("No optimisation is currently running.")
            return

        was_cancel_signal_sent, message = self.optimisation_runner.cancel()

        if was_cancel_signal_sent:
            self.log(message)
            self.statusBar().showMessage("Cancelling optimisation...", 3000)
        else:
            self.log(f"Could not cancel optimisation: {message}")
            self.statusBar().showMessage("Cancellation not available.", 3000)

    def _on_optimisation_finished(self, status) -> None:
        session = self.active_session()

        self.log(f"Optimisation finished. Status: {status}")

        if session is not None:
            session.is_modified = True
            self.central_panel.set_network(session.network)

        QMessageBox.information(
            self,
            "Optimisation Finished",
            f"Optimisation completed.\n\nStatus: {status}",
        )

    def _on_optimisation_failed(self, error_message: str) -> None:
        self.log(f"Optimisation failed: {error_message}")

        QMessageBox.critical(
            self,
            "Optimisation Failed",
            f"Could not run optimisation:\n\n{error_message}",
        )

    def _on_optimisation_thread_finished(self) -> None:
        self._set_optimisation_running_state(False)
        self.optimisation_worker = None
        self.optimisation_runner = None

    # ------------------------------------------------------------------
    # Other actions
    # ------------------------------------------------------------------

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

    def closeEvent(self, event) -> None:
        worker_running = (
            hasattr(self, "optimisation_worker")
            and self.optimisation_worker is not None
            and self.optimisation_worker.isRunning()
        )

        if not worker_running:
            event.accept()
            return

        reply = QMessageBox.question(
            self,
            "Optimisation running",
            "An optimisation is still running. Close the application anyway?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

    def _ask_for_view_options(self) -> SessionViewOptions | None:
        dialog = WorkspaceSelectionDialog(self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        return SessionViewOptions(
            workspace_name=dialog.selected_workspace_name(),
            enabled_sections=dialog.selected_enabled_sections(),
        )