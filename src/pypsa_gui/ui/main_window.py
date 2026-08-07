from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pypsa
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QTextEdit,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
)

from pypsa_gui.models.network_session import NetworkSession
from pypsa_gui.models.scenario_definition import (
    ScenarioDefinition,
)
from pypsa_gui.models.session_view import (
    NAVIGATION_STRUCTURE,
    SECTION_TITLES,
    SessionViewOptions,
)
from pypsa_gui.modules.registry import create_module_registry
from pypsa_gui.services.network_io import (
    load_network_from_csv_folder,
    load_network_from_netcdf,
    save_network_to_netcdf,
)
from pypsa_gui.services.network_store import NetworkStore
from pypsa_gui.services.optimisation import OptimisationRunner
from pypsa_gui.services.scenario_builder import (
    build_scenario_network,
)
from pypsa_gui.ui.central_panel import CentralPanel
from pypsa_gui.ui.dialogs.workspace_selection_dialog import (
    WorkspaceSelectionDialog,
)
from pypsa_gui.workers.optimisation_worker import (
    OptimisationWorker,
)
from pypsa_gui.workflows.models import WorkflowRecord
from pypsa_gui.workflows.recorder import WorkflowRecorder


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.network_store = NetworkStore()
        self.modules = create_module_registry()

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

    def active_session(
            self,
    ) -> NetworkSession | None:
        return self.network_store.get_active_session()

    def active_network(
            self,
    ) -> pypsa.Network | None:
        session = self.active_session()

        return (
            session.network
            if session is not None
            else None
        )

    def active_file_path(
            self,
    ) -> Path | None:
        session = self.active_session()

        return (
            session.source_path
            if session is not None
            else None
        )

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _create_actions(self) -> None:
        self.open_netcdf_action = QAction(
            "Open NetCDF Network...",
            self,
        )
        self.open_netcdf_action.setStatusTip(
            "Open a PyPSA network from a .nc file"
        )
        self.open_netcdf_action.triggered.connect(
            self.on_open_netcdf_network
        )

        self.open_csv_action = QAction(
            "Open CSV Folder...",
            self,
        )
        self.open_csv_action.setStatusTip(
            "Open a PyPSA network from a CSV folder"
        )
        self.open_csv_action.triggered.connect(
            self.on_open_csv_folder
        )

        self.save_action = QAction(
            "Save",
            self,
        )
        self.save_action.setStatusTip(
            "Save the current network"
        )
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(
            self.save_network
        )

        self.save_as_action = QAction(
            "Save As NetCDF...",
            self,
        )
        self.save_as_action.setStatusTip(
            "Save the current network under a new name"
        )
        self.save_as_action.setShortcut("Ctrl+Shift+S")
        self.save_as_action.triggered.connect(
            self.save_as_netcdf
        )

        self.exit_action = QAction(
            "Exit",
            self,
        )
        self.exit_action.setStatusTip(
            "Close the application"
        )
        self.exit_action.triggered.connect(
            self.close
        )

        self.run_optimisation_action = QAction(
            "Run Optimisation",
            self,
        )
        self.run_optimisation_action.setStatusTip(
            "Run PyPSA optimisation"
        )
        self.run_optimisation_action.triggered.connect(
            self.on_run_optimisation
        )

        self.cancel_optimisation_action = QAction(
            "Cancel Optimisation",
            self,
        )
        self.cancel_optimisation_action.setStatusTip(
            "Cancel the running optimisation"
        )
        self.cancel_optimisation_action.triggered.connect(
            self.on_cancel_optimisation
        )
        self.cancel_optimisation_action.setEnabled(False)

        self.run_power_flow_action = QAction(
            "Run Power Flow",
            self,
        )
        self.run_power_flow_action.setStatusTip(
            "Run PyPSA power flow"
        )
        self.run_power_flow_action.triggered.connect(
            self.on_run_power_flow
        )

        self.about_action = QAction(
            "About",
            self,
        )
        self.about_action.setStatusTip(
            "About pypsa-gui"
        )
        self.about_action.triggered.connect(
            self.on_about
        )

    def _create_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")
        file_menu.addAction(
            self.open_netcdf_action
        )
        file_menu.addAction(
            self.open_csv_action
        )
        file_menu.addSeparator()
        file_menu.addAction(
            self.save_action
        )
        file_menu.addAction(
            self.save_as_action
        )
        file_menu.addSeparator()
        file_menu.addAction(
            self.exit_action
        )

        run_menu = menu_bar.addMenu("Run")
        run_menu.addAction(
            self.run_optimisation_action
        )
        run_menu.addAction(
            self.cancel_optimisation_action
        )
        run_menu.addAction(
            self.run_power_flow_action
        )

        help_menu = menu_bar.addMenu("Help")
        help_menu.addAction(
            self.about_action
        )

    def _create_tool_bar(self) -> None:
        tool_bar = QToolBar(
            "Main Toolbar",
            self,
        )
        tool_bar.setMovable(False)

        self.addToolBar(tool_bar)

        tool_bar.addAction(
            self.open_netcdf_action
        )
        tool_bar.addAction(
            self.open_csv_action
        )
        tool_bar.addAction(
            self.save_action
        )
        tool_bar.addAction(
            self.save_as_action
        )
        tool_bar.addSeparator()
        tool_bar.addAction(
            self.run_optimisation_action
        )
        tool_bar.addAction(
            self.cancel_optimisation_action
        )
        tool_bar.addAction(
            self.run_power_flow_action
        )

    def _create_central_widget(self) -> None:
        self.central_panel = CentralPanel(
            parent=self
        )

        self.central_panel.scenario_requested.connect(
            self.on_scenario_requested
        )

        self.central_panel.create_empty_network_requested.connect(
            self.on_create_empty_network
        )

        self.central_panel.new_network_requested.connect(
            self.on_create_empty_network
        )
        self.central_panel.open_network_requested.connect(
            self.on_open_netcdf_network
        )
        self.central_panel.save_network_requested.connect(
            self.save_network
        )
        self.central_panel.save_network_as_requested.connect(
            self.save_as_netcdf
        )
        self.central_panel.network_modified.connect(
            self.on_network_builder_modified
        )

        self.central_panel.run_optimisation_requested.connect(
            self.on_run_optimisation
        )

        self.setCentralWidget(
            self.central_panel
        )

    def _create_navigation_dock(self) -> None:
        self.navigation_tree = QTreeWidget(
            self
        )
        self.navigation_tree.setHeaderHidden(True)
        self.navigation_tree.itemClicked.connect(
            self.on_navigation_item_clicked
        )

        dock = QDockWidget(
            "Navigation",
            self,
        )
        dock.setWidget(
            self.navigation_tree
        )
        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea,
            dock,
        )

        self._rebuild_navigation_tree()

    def _rebuild_navigation_tree(self) -> None:
        self.navigation_tree.blockSignals(True)
        self.navigation_tree.clear()

        session = self.active_session()

        if session is None:
            enabled_sections = {
                "overview",
                "build",
                "components",
                "analysis",
                "plots",
                "run",
                "research_modules",
            }
            network = None
        else:
            enabled_sections = (
                session.view_options.enabled_sections
            )
            network = session.network

        section_order = [
            "overview",
            "build",
            "components",
            "analysis",
            "plots",
            "run",
            "research_modules",
        ]

        for section_key in section_order:
            if section_key not in enabled_sections:
                continue

            title = SECTION_TITLES[
                section_key
            ]

            children = list(
                NAVIGATION_STRUCTURE.get(
                    section_key,
                    [],
                )
            )

            if section_key == "research_modules":
                for module in self.modules:
                    module.set_network(
                        network
                    )

                    if not module.is_available(
                            network
                    ):
                        continue

                    for page_def in module.get_pages():
                        children.append(
                            page_def.title
                        )

            if not children:
                continue

            parent_item = QTreeWidgetItem(
                [title]
            )

            for child_name in children:
                QTreeWidgetItem(
                    parent_item,
                    [child_name],
                )

            self.navigation_tree.addTopLevelItem(
                parent_item
            )

        self.navigation_tree.expandAll()
        self.navigation_tree.blockSignals(False)

    def _create_loaded_networks_dock(
            self,
    ) -> None:
        self.loaded_networks_list = QListWidget(
            self
        )
        self.loaded_networks_list.itemClicked.connect(
            self.on_loaded_network_clicked
        )

        dock = QDockWidget(
            "Loaded Networks",
            self,
        )
        dock.setWidget(
            self.loaded_networks_list
        )
        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea,
            dock,
        )

    def on_navigation_item_clicked(
            self,
            item: QTreeWidgetItem,
            column: int,
    ) -> None:
        del column

        page_name = item.text(0)

        if item.childCount() > 0:
            self.log(
                f"Navigation category selected: {page_name}"
            )
            return

        self.log(
            f"Navigation changed to: {page_name}"
        )

        self.central_panel.set_current_page(
            page_name
        )

    def _create_log_dock(self) -> None:
        self.log_output = QTextEdit(
            self
        )
        self.log_output.setReadOnly(True)

        dock = QDockWidget(
            "Log",
            self,
        )
        dock.setWidget(
            self.log_output
        )
        dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.TopDockWidgetArea
        )

        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea,
            dock,
        )

    def _show_welcome_message(self) -> None:
        self.log(
            "Application started."
        )
        self.log(
            "No network loaded."
        )

    # ------------------------------------------------------------------
    # Logging and UI state
    # ------------------------------------------------------------------

    def log(
            self,
            message: str,
    ) -> None:
        self.log_output.append(
            message
        )
        self.statusBar().showMessage(
            message,
            3000,
        )

    def _set_optimisation_running_state(
            self,
            is_running: bool,
    ) -> None:
        self.optimisation_running = is_running

        self.run_optimisation_action.setEnabled(
            not is_running
        )
        self.cancel_optimisation_action.setEnabled(
            is_running
        )
        self.run_power_flow_action.setEnabled(
            not is_running
        )

        self.central_panel.set_optimisation_running(
            is_running
        )

    # ------------------------------------------------------------------
    # Research modules
    # ------------------------------------------------------------------

    def _refresh_research_modules(self) -> None:
        network = self.active_network()

        self.central_panel.clear_module_pages()

        for module in self.modules:
            module.set_network(
                network
            )

            if not module.is_available(
                    network
            ):
                continue

            for page_def in module.get_pages():
                page = module.create_page(
                    page_def.key,
                    parent=self.central_panel,
                )

                if hasattr(
                        page,
                        "set_network",
                ):
                    page.set_network(
                        network
                    )
                elif hasattr(
                        page,
                        "update_from_network",
                ):
                    page.update_from_network(
                        network
                    )

                self.central_panel.add_module_page(
                    page_def.title,
                    page,
                )

    # ------------------------------------------------------------------
    # Session and network handling
    # ------------------------------------------------------------------

    def _refresh_active_session_ui(self) -> None:
        session = self.active_session()

        default_sections = {
            "overview",
            "build",
            "components",
            "analysis",
            "plots",
            "run",
            "research_modules",
        }

        required_sections = (
            default_sections
            if session is None
            else set(
                session.view_options.enabled_sections
            )
        )

        pages_rebuilt = (
                self.central_panel.enabled_sections
                != required_sections
        )

        if pages_rebuilt:
            self.central_panel.rebuild_pages(
                required_sections
            )

        if session is None:
            if pages_rebuilt:
                self._refresh_research_modules()
            else:
                for module in self.modules:
                    module.set_network(
                        None
                    )

                self.central_panel.clear_module_pages()

            self.central_panel.set_network_context(
                network=None,
                locations=None,
            )
            self.central_panel.set_workflow(None)

            self._rebuild_navigation_tree()
            self.setWindowTitle(
                "pypsa-gui"
            )
            self._refresh_loaded_networks_dock()

            return

        # Research-module widgets must be recreated when the page
        # structure changed or when research modules are enabled but
        # their pages are currently missing. The latter occurs when the
        # first network is created from the initial no-network state:
        # enabled_sections can remain unchanged even though module pages
        # were previously cleared.
        research_modules_enabled = (
            "research_modules"
            in required_sections
        )

        module_pages_missing = (
            research_modules_enabled
            and not self.central_panel.has_module_pages()
        )

        if pages_rebuilt or module_pages_missing:
            self._refresh_research_modules()
        else:
            for module in self.modules:
                module.set_network(
                    session.network
                )

        self.central_panel.set_network_context(
            network=session.network,
            locations=session.locations,
        )
        self.central_panel.set_workflow(
            session.workflow
        )
        self.central_panel.set_network_builder_project_state(
            name=session.name,
            is_modified=session.is_modified,
        )

        self._rebuild_navigation_tree()

        self.log(
            f"Switched to network: {session.name}"
        )
        self.log(
            "Network summary: "
            f"{len(session.network.buses)} buses, "
            f"{len(session.network.generators)} generators, "
            f"{len(session.network.loads)} loads, "
            f"{len(session.network.lines)} lines, "
            f"{len(session.network.links)} links"
        )

        modified_suffix = (
            "*"
            if session.is_modified
            else ""
        )

        self.setWindowTitle(
            "pypsa-gui - "
            f"{session.name}{modified_suffix}"
        )

        self._refresh_loaded_networks_dock()

    def _add_network_session(
            self,
            network: pypsa.Network,
            source_path: Path | None,
            view_options: SessionViewOptions,
            name: str | None = None,
            workflow: WorkflowRecord | None = None,
    ) -> None:
        session_name = name or (
            source_path.stem
            if source_path is not None
            else "unsaved network"
        )

        session = NetworkSession(
            id=str(uuid4()),
            name=session_name,
            network=network,
            source_path=source_path,
            is_modified=False,
            view_options=view_options,
            workflow=workflow or WorkflowRecord(),
        )

        self.network_store.add_session(
            session
        )

        self._refresh_active_session_ui()

    def _refresh_loaded_networks_dock(
            self,
    ) -> None:
        self.loaded_networks_list.blockSignals(
            True
        )
        self.loaded_networks_list.clear()

        active_session = self.active_session()

        for session in self.network_store.list_sessions():
            modified_suffix = (
                "*"
                if session.is_modified
                else ""
            )
            label = f"{session.name}{modified_suffix}"

            if session is active_session:
                label = f"● {label}"

            item = QListWidgetItem(
                label
            )
            item.setData(
                Qt.ItemDataRole.UserRole,
                session.id,
            )

            self.loaded_networks_list.addItem(
                item
            )

        if active_session is not None:
            for row in range(
                    self.loaded_networks_list.count()
            ):
                item = (
                    self.loaded_networks_list.item(
                        row
                    )
                )

                if (
                        item.data(
                            Qt.ItemDataRole.UserRole
                        )
                        == active_session.id
                ):
                    self.loaded_networks_list.setCurrentRow(
                        row
                    )
                    break

        self.loaded_networks_list.blockSignals(
            False
        )

    def on_loaded_network_clicked(
            self,
            item: QListWidgetItem,
    ) -> None:
        session_id = item.data(
            Qt.ItemDataRole.UserRole
        )

        if session_id is None:
            return

        if self.optimisation_running:
            self.log(
                "Cannot switch sessions while "
                "optimisation is running."
            )
            return

        self.network_store.set_active_session(
            session_id
        )

        self._refresh_active_session_ui()

        session = self.active_session()

        if session is not None:
            self.log(
                "Switched active session to: "
                f"{session.name}"
            )

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
            self.log(
                "Open NetCDF cancelled."
            )
            return

        view_options = self._ask_for_view_options()

        if view_options is None:
            self.log(
                "Workspace selection cancelled."
            )
            return

        self.log(
            f"Loading NetCDF network: {file_path}"
        )

        try:
            network = load_network_from_netcdf(
                file_path
            )

            workflow = WorkflowRecord()

            recorder = WorkflowRecorder(workflow)

            recorder.record_create_empty_network(
                name=network_name,
            )

            self._add_network_session(
                network=network,
                source_path=Path(file_path),
                view_options=view_options,
                workflow=workflow,
            )
        except Exception as exc:
            self.log(
                "Error loading NetCDF network: "
                f"{exc}"
            )

            QMessageBox.critical(
                self,
                "Load Error",
                "Could not load NetCDF network:"
                "\n"
                f"{exc}",
            )

    def on_open_csv_folder(self) -> None:
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Open PyPSA CSV Folder",
            "",
        )

        if not folder_path:
            self.log(
                "Open CSV folder cancelled."
            )
            return

        view_options = self._ask_for_view_options()

        if view_options is None:
            self.log(
                "Workspace selection cancelled."
            )
            return

        self.log(
            "Loading CSV network from folder: "
            f"{folder_path}"
        )

        try:
            network = load_network_from_csv_folder(
                folder_path
            )

            workflow = WorkflowRecord()
            recorder = WorkflowRecorder(workflow)
            recorder.record_load_network(
                source_path=folder_path,
                network_name=Path(folder_path).name,
            )

            self._add_network_session(
                network=network,
                source_path=Path(folder_path),
                view_options=view_options,
                workflow=workflow,
            )
        except Exception as exc:
            self.log(
                "Error loading CSV folder: "
                f"{exc}"
            )

            QMessageBox.critical(
                self,
                "Load Error",
                "Could not load CSV network:"
                "\n"
                f"{exc}",
            )

    def save_network(self) -> None:
        session = self.active_session()

        if session is None:
            QMessageBox.information(
                self,
                "No Network Loaded",
                "There is no network loaded to save.",
            )
            return

        if (
                session.source_path is None
                or session.source_path.suffix != ".nc"
        ):
            self.save_as_netcdf()
            return

        try:
            save_network_to_netcdf(
                session.network,
                session.source_path,
            )

            session.is_modified = False

            self.central_panel.set_network_builder_project_state(
                name=session.name,
                is_modified=False,
            )
            self._refresh_loaded_networks_dock()

            self.setWindowTitle(
                f"pypsa-gui - {session.name}"
            )

            self.log(
                "Network saved to: "
                f"{session.source_path}"
            )

        except Exception as exc:
            self.log(
                f"Error saving network: {exc}"
            )

            QMessageBox.critical(
                self,
                "Save Failed",
                "Could not save network:"
                "\n\n"
                f"{exc}",
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
            if (
                    session.source_path is not None
                    and session.source_path.suffix
                    == ".nc"
            )
            else str(
                Path.home()
                / f"{session.name}.nc"
            )
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PyPSA Network As NetCDF",
            default_path,
            "NetCDF Files (*.nc)",
        )

        if not file_path:
            self.log(
                "Save cancelled."
            )
            return

        if not file_path.endswith(".nc"):
            file_path += ".nc"

        try:
            save_network_to_netcdf(
                session.network,
                file_path,
            )

            session.source_path = Path(
                file_path
            )
            session.name = Path(
                file_path
            ).stem
            session.is_modified = False

            self.central_panel.set_network_builder_project_state(
                name=session.name,
                is_modified=False,
            )

            self.setWindowTitle(
                f"pypsa-gui - {session.name}"
            )

            self._refresh_loaded_networks_dock()

            self.log(
                f"Network saved to: {file_path}"
            )
        except Exception as exc:
            self.log(
                f"Error saving network: {exc}"
            )

            QMessageBox.critical(
                self,
                "Save Failed",
                "Could not save network:"
                "\n\n"
                f"{exc}",
            )

    def on_network_builder_modified(self) -> None:
        session = self.active_session()

        if session is None:
            return

        session.is_modified = True

        self.central_panel.set_network_builder_project_state(
            name=session.name,
            is_modified=True,
        )
        self._refresh_loaded_networks_dock()

        self.setWindowTitle(
            f"pypsa-gui - {session.name}*"
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
                "Please load a network before "
                "running optimisation.",
            )
            return

        if self.optimisation_running:
            self.log(
                "Optimisation is already running."
            )
            return

        self.log(
            "Starting optimisation for: "
            f"{session.name}"
        )

        self.optimisation_runner = OptimisationRunner(
            session.network
        )

        self.optimisation_worker = OptimisationWorker(
            self.optimisation_runner
        )

        self.optimisation_worker.finished_successfully.connect(
            self._on_optimisation_finished
        )
        self.optimisation_worker.failed.connect(
            self._on_optimisation_failed
        )
        self.optimisation_worker.finished.connect(
            self._on_optimisation_thread_finished
        )

        self._set_optimisation_running_state(
            True
        )

        self.optimisation_worker.start()

    def on_cancel_optimisation(self) -> None:
        if (
                not self.optimisation_running
                or self.optimisation_runner is None
        ):
            self.log(
                "No optimisation is currently running."
            )
            return

        (
            was_cancel_signal_sent,
            message,
        ) = self.optimisation_runner.cancel()

        if was_cancel_signal_sent:
            self.log(
                message
            )
            self.statusBar().showMessage(
                "Cancelling optimisation...",
                3000,
            )
        else:
            self.log(
                "Could not cancel optimisation: "
                f"{message}"
            )
            self.statusBar().showMessage(
                "Cancellation not available.",
                3000,
            )

    def _on_optimisation_finished(
            self,
            status,
    ) -> None:
        session = self.active_session()

        self.log(
            "Optimisation finished. "
            f"Status: {status}"
        )

        if session is not None:
            recorder = WorkflowRecorder(
                session.workflow
            )
            recorder.record_optimization(
                solver="gurobi",
                options={
                    "Method": 2,
                    "Crossover": 0,
                },
                status=str(status),
            )
            self.central_panel.set_workflow(
                session.workflow
            )

            session.is_modified = True

            # Rebuild the pages with the solved network.
            self._refresh_active_session_ui()

            # Ensure that the PDF report button is enabled.
            self.central_panel.refresh_optimisation_results_state()

        QMessageBox.information(
            self,
            "Optimisation Finished",
            "Optimisation completed."
            "\n\n"
            f"Status: {status}",
        )

    def _on_optimisation_failed(
            self,
            error_message: str,
    ) -> None:
        self.log(
            "Optimisation failed: "
            f"{error_message}"
        )

        self.central_panel.set_optimisation_running(
            False
        )

        QMessageBox.critical(
            self,
            "Optimisation Failed",
            "Could not run optimisation:"
            "\n\n"
            f"{error_message}",
        )

    def _on_optimisation_thread_finished(
            self,
    ) -> None:
        self._set_optimisation_running_state(
            False
        )

        self.central_panel.refresh_optimisation_results_state()

        self.optimisation_worker = None
        self.optimisation_runner = None

    # ------------------------------------------------------------------
    # Other actions
    # ------------------------------------------------------------------

    def on_run_power_flow(self) -> None:
        self.log(
            "Run Power Flow clicked."
        )

    def on_navigation_changed(
            self,
            item_text: str,
    ) -> None:
        if not item_text:
            return

        self.log(
            f"Navigation changed to: {item_text}"
        )

        self.central_panel.show_page(
            item_text
        )

    def on_about(self) -> None:
        QMessageBox.about(
            self,
            "About pypsa-gui",
            "pypsa-gui\n\n"
            "An experimental desktop GUI for "
            "inspecting, editing, solving, and "
            "visualising PyPSA networks.",
        )

    def closeEvent(
            self,
            event,
    ) -> None:
        worker_running = (
                self.optimisation_worker is not None
                and self.optimisation_worker.isRunning()
        )

        if not worker_running:
            event.accept()
            return

        reply = QMessageBox.question(
            self,
            "Optimisation running",
            "An optimisation is still running. "
            "Close the application anyway?",
            QMessageBox.Yes
            | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

    def _ask_for_view_options(
            self,
    ) -> SessionViewOptions | None:
        dialog = WorkspaceSelectionDialog(
            self
        )

        if (
                dialog.exec()
                != QDialog.DialogCode.Accepted
        ):
            return None

        return SessionViewOptions(
            workspace_name=(
                dialog.selected_workspace_name()
            ),
            enabled_sections=(
                dialog.selected_enabled_sections()
            ),
        )

    def _next_empty_network_name(self) -> str:
        existing_names = {
            session.name
            for session in self.network_store.list_sessions()
        }

        base_name = "New network"

        if base_name not in existing_names:
            return base_name

        index = 2

        while f"{base_name} {index}" in existing_names:
            index += 1

        return f"{base_name} {index}"

    def on_create_empty_network(self) -> None:
        suggested_name = self._next_empty_network_name()

        network_name, accepted = QInputDialog.getText(
            self,
            "New Network",
            "Network name:",
            text=suggested_name,
        )

        if not accepted:
            self.log(
                "New network creation cancelled."
            )
            return

        network_name = network_name.strip()

        if not network_name:
            QMessageBox.warning(
                self,
                "Invalid Network Name",
                "The network name cannot be empty.",
            )
            return

        existing_names = {
            session.name
            for session in self.network_store.list_sessions()
        }

        if network_name in existing_names:
            QMessageBox.warning(
                self,
                "Network Name Already Used",
                (
                    f'A loaded network named "{network_name}" '
                    "already exists."
                ),
            )
            return

        self.log(
            f'Creating empty PyPSA network "{network_name}".'
        )

        try:
            network = pypsa.Network()

            workflow = WorkflowRecord()
            recorder = WorkflowRecorder(workflow)
            recorder.record_create_empty_network(
                name=network_name,
            )

            self._add_network_session(
                network=network,
                source_path=None,
                view_options=SessionViewOptions(
                    workspace_name="Network Builder",
                    enabled_sections={
                        "overview",
                        "build",
                        "components",
                        "analysis",
                        "plots",
                        "run",
                        "research_modules",
                    },
                ),
                name=network_name,
                workflow=workflow,
            )

            session = self.active_session()

            if session is not None:
                session.is_modified = True

                self.central_panel.set_network_builder_project_state(
                    name=session.name,
                    is_modified=True,
                )
                self._refresh_loaded_networks_dock()

                self.setWindowTitle(
                    f"pypsa-gui - {session.name}*"
                )

            self.central_panel.show_page(
                "Network Builder"
            )

            self.log(
                f'Empty network "{network_name}" created.'
            )

        except Exception as exc:
            self.log(
                "Could not create empty network: "
                f"{exc}"
            )

            QMessageBox.critical(
                self,
                "Network Builder",
                "Could not create an empty network:"
                "\n\n"
                f"{exc}",
            )

    def on_scenario_requested(
            self,
            definition: ScenarioDefinition,
    ) -> None:
        self.log(
            "Scenario request received"
        )
        self.log(
            str(definition)
        )

        try:
            network = build_scenario_network(
                definition=definition,
            )

            workflow = WorkflowRecord()
            recorder = WorkflowRecorder(workflow)
            recorder.record_create_scenario(
                definition,
            )

            self._add_network_session(
                network=network,
                source_path=None,
                view_options=SessionViewOptions(
                    workspace_name="Scenario",
                    enabled_sections={
                        "overview",
                        "build",
                        "components",
                        "analysis",
                        "plots",
                        "run",
                        "research_modules",
                    },
                ),
                name=definition.name,
                workflow=workflow,
            )
        except Exception as exc:
            self.log(
                str(exc)
            )

            QMessageBox.critical(
                self,
                "Scenario Builder",
                str(exc),
            )