from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pypsa_gui.models.network_location import NetworkLocation
from pypsa_gui.services.time_series_library import TimeSeriesLibrary
from pypsa_gui.ui.pages.network_builder.component_dialogs import (
    GeneratorCreationDialog,
    GeneratorProfileMode,
    InternalBusCreationDialog,
    LoadCreationDialog,
    StorageUnitCreationDialog,
    StoreCreationDialog,
)


class LocationEditor(QWidget):
    """
    Editor for the internal PyPSA topology of one geographic location.

    The first version is intentionally list-based. A graphical internal
    topology view can replace or extend this widget later without changing
    the public set_context() interface.
    """

    back_requested = Signal()
    network_modified = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.network: Any | None = None
        self.location: NetworkLocation | None = None
        self.time_series_library = TimeSeriesLibrary()

        self._build_ui()
        self._set_editor_enabled(False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_context(
        self,
        network: Any | None,
        location: NetworkLocation | None,
    ) -> None:
        self.network = network
        self.location = location

        self.time_series_library.clear()

        if network is not None:
            self.time_series_library.register_network_profiles(
                network
            )

        enabled = (
            network is not None
            and location is not None
        )
        self._set_editor_enabled(enabled)

        if not enabled:
            self.location_title_label.setText(
                "No location selected"
            )
            self.coordinates_label.setText("")
            self.internal_buses_list.clear()
            self._set_component_counts(
                generators=0,
                loads=0,
                stores=0,
                storage_units=0,
            )
            return

        self.refresh()

    def refresh(self) -> None:
        if (
            self.network is None
            or self.location is None
        ):
            return

        self.location_title_label.setText(
            self.location.name
        )
        self.coordinates_label.setText(
            "Longitude: "
            f"{self.location.longitude:.4f} · "
            "Latitude: "
            f"{self.location.latitude:.4f}"
        )

        self._refresh_internal_buses()
        self._refresh_component_counts()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(14)

        header_layout = QHBoxLayout()

        self.back_button = QPushButton(
            "← Back to map"
        )
        self.back_button.clicked.connect(
            self.back_requested.emit
        )

        self.location_title_label = QLabel(
            "No location selected"
        )
        self.location_title_label.setStyleSheet(
            """
            QLabel {
                font-size: 22px;
                font-weight: 600;
            }
            """
        )

        header_layout.addWidget(
            self.back_button
        )
        header_layout.addWidget(
            self.location_title_label
        )
        header_layout.addStretch()

        root_layout.addLayout(
            header_layout
        )

        self.coordinates_label = QLabel()
        self.coordinates_label.setStyleSheet(
            """
            QLabel {
                color: #666666;
            }
            """
        )
        root_layout.addWidget(
            self.coordinates_label
        )

        buses_group = QGroupBox(
            "Internal buses"
        )
        buses_layout = QVBoxLayout(
            buses_group
        )

        self.internal_buses_list = QListWidget()
        buses_layout.addWidget(
            self.internal_buses_list
        )

        bus_buttons_layout = QHBoxLayout()

        self.add_bus_button = QPushButton(
            "Add internal bus"
        )
        self.add_bus_button.clicked.connect(
            self._on_add_internal_bus
        )

        bus_buttons_layout.addWidget(
            self.add_bus_button
        )
        bus_buttons_layout.addStretch()

        buses_layout.addLayout(
            bus_buttons_layout
        )

        root_layout.addWidget(
            buses_group
        )

        components_group = QGroupBox(
            "Attached components"
        )
        components_layout = QVBoxLayout(
            components_group
        )

        counts_layout = QFormLayout()

        self.generators_count_label = QLabel("0")
        self.loads_count_label = QLabel("0")
        self.stores_count_label = QLabel("0")
        self.storage_units_count_label = QLabel("0")

        counts_layout.addRow(
            "Generators",
            self.generators_count_label,
        )
        counts_layout.addRow(
            "Loads",
            self.loads_count_label,
        )
        counts_layout.addRow(
            "Stores",
            self.stores_count_label,
        )
        counts_layout.addRow(
            "Storage units",
            self.storage_units_count_label,
        )

        components_layout.addLayout(
            counts_layout
        )

        component_buttons_layout = QHBoxLayout()

        self.add_generator_button = QPushButton(
            "Add generator"
        )
        self.add_generator_button.clicked.connect(
            self._on_add_generator
        )

        self.add_load_button = QPushButton(
            "Add load"
        )
        self.add_load_button.clicked.connect(
            self._on_add_load
        )

        self.add_store_button = QPushButton(
            "Add store"
        )
        self.add_store_button.clicked.connect(
            self._on_add_store
        )

        self.add_storage_unit_button = QPushButton(
            "Add storage unit"
        )
        self.add_storage_unit_button.clicked.connect(
            self._on_add_storage_unit
        )

        component_buttons_layout.addWidget(
            self.add_generator_button
        )
        component_buttons_layout.addWidget(
            self.add_load_button
        )
        component_buttons_layout.addWidget(
            self.add_store_button
        )
        component_buttons_layout.addWidget(
            self.add_storage_unit_button
        )
        component_buttons_layout.addStretch()

        components_layout.addLayout(
            component_buttons_layout
        )

        root_layout.addWidget(
            components_group
        )
        root_layout.addStretch()

    def _set_editor_enabled(
        self,
        enabled: bool,
    ) -> None:
        for widget in (
            self.back_button,
            self.internal_buses_list,
            self.add_bus_button,
            self.add_generator_button,
            self.add_load_button,
            self.add_store_button,
            self.add_storage_unit_button,
        ):
            widget.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Refresh helpers
    # ------------------------------------------------------------------

    def _refresh_internal_buses(self) -> None:
        if (
            self.network is None
            or self.location is None
        ):
            return

        self.internal_buses_list.clear()

        valid_bus_names = []

        for bus_name in self.location.bus_names:
            if bus_name not in self.network.buses.index:
                continue

            valid_bus_names.append(
                bus_name
            )

            bus = self.network.buses.loc[
                bus_name
            ]
            carrier = str(
                bus.get(
                    "carrier",
                    "",
                )
            )

            label = bus_name

            if carrier:
                label = (
                    f"{bus_name} "
                    f"({carrier})"
                )

            self.internal_buses_list.addItem(
                label
            )

        if (
            valid_bus_names
            != self.location.bus_names
        ):
            self.location.bus_names = (
                valid_bus_names
            )

    def _refresh_component_counts(self) -> None:
        if (
            self.network is None
            or self.location is None
        ):
            return

        bus_names = set(
            self.location.bus_names
        )

        generators = self._count_components_on_buses(
            self.network.generators,
            bus_names,
        )
        loads = self._count_components_on_buses(
            self.network.loads,
            bus_names,
        )
        stores = self._count_components_on_buses(
            self.network.stores,
            bus_names,
        )
        storage_units = (
            self._count_components_on_buses(
                self.network.storage_units,
                bus_names,
            )
        )

        self._set_component_counts(
            generators=generators,
            loads=loads,
            stores=stores,
            storage_units=storage_units,
        )

    @staticmethod
    def _count_components_on_buses(
        components,
        bus_names: set[str],
    ) -> int:
        if (
            components.empty
            or "bus" not in components.columns
        ):
            return 0

        return int(
            components["bus"]
            .isin(bus_names)
            .sum()
        )

    def _set_component_counts(
        self,
        generators: int,
        loads: int,
        stores: int,
        storage_units: int,
    ) -> None:
        self.generators_count_label.setText(
            str(generators)
        )
        self.loads_count_label.setText(
            str(loads)
        )
        self.stores_count_label.setText(
            str(stores)
        )
        self.storage_units_count_label.setText(
            str(storage_units)
        )

    # ------------------------------------------------------------------
    # Internal bus creation
    # ------------------------------------------------------------------

    def _on_add_internal_bus(self) -> None:
        if (
            self.network is None
            or self.location is None
        ):
            return

        dialog = InternalBusCreationDialog(
            suggested_name=self._next_bus_name(),
            suggested_carrier="heat",
            parent=self,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        definition = dialog.definition()

        if definition.name in self.network.buses.index:
            QMessageBox.warning(
                self,
                "Bus Already Exists",
                (
                    f'A bus named "{definition.name}" '
                    "already exists."
                ),
            )
            return

        try:
            self.network.add(
                "Bus",
                definition.name,
                carrier=definition.carrier,
                x=self.location.longitude,
                y=self.location.latitude,
            )

            self.network.buses.loc[
                definition.name,
                "location",
            ] = self.location.id

            self.location.bus_names.append(
                definition.name
            )

        except Exception as exc:
            if definition.name in self.network.buses.index:
                self.network.remove(
                    "Bus",
                    definition.name,
                )

            QMessageBox.critical(
                self,
                "Add Bus Failed",
                "Could not add the bus:\n\n"
                f"{exc}",
            )
            return

        self.network_modified.emit()
        self.refresh()

    def _next_bus_name(self) -> str:
        if (
            self.network is None
            or self.location is None
        ):
            return "New bus"

        base_name = (
            f"{self.location.name} bus"
        )
        existing_names = set(
            self.network.buses.index.astype(str)
        )

        if base_name not in existing_names:
            return base_name

        index = 2

        while (
            f"{base_name} {index}"
            in existing_names
        ):
            index += 1

        return f"{base_name} {index}"

    # ------------------------------------------------------------------
    # Generator creation
    # ------------------------------------------------------------------

    def _on_add_generator(self) -> None:
        bus_names = self._valid_internal_bus_names()

        if not bus_names:
            self._show_no_internal_bus_warning()
            return

        available_profiles = (
            self.time_series_library.list_profiles()
        )

        dialog = GeneratorCreationDialog(
            bus_names=bus_names,
            suggested_name=self._next_component_name(
                table_name="generators",
                base_name="Generator",
            ),
            available_profiles=available_profiles,
            suggested_carrier="solar",
            parent=self,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        definition = dialog.definition()

        if definition.name in self.network.generators.index:
            QMessageBox.warning(
                self,
                "Generator Already Exists",
                (
                    f'A generator named "{definition.name}" '
                    "already exists."
                ),
            )
            return

        try:
            generator_attributes = {
                "bus": definition.bus,
                "carrier": definition.carrier,
                "p_nom": definition.p_nom,
                "p_nom_extendable": definition.extendable,
                "marginal_cost": definition.marginal_cost,
            }

            if (
                definition.profile_mode
                == GeneratorProfileMode.CONSTANT
            ):
                generator_attributes["p_max_pu"] = (
                    definition.constant_p_max_pu
                )

            self.network.add(
                "Generator",
                definition.name,
                **generator_attributes,
            )

            if (
                definition.profile_mode
                == GeneratorProfileMode.EXISTING
            ):
                if definition.profile_id is None:
                    raise ValueError(
                        "No availability profile was selected."
                    )

                self.time_series_library.apply_profile_to_generator(
                    network=self.network,
                    generator_name=definition.name,
                    profile_id=definition.profile_id,
                )

            elif (
                definition.profile_mode
                == GeneratorProfileMode.SCALED
            ):
                if (
                    definition.profile_id is None
                    or definition.target_capacity_factor is None
                ):
                    raise ValueError(
                        "The scaled profile configuration is incomplete."
                    )

                self.time_series_library.apply_profile_to_generator(
                    network=self.network,
                    generator_name=definition.name,
                    profile_id=definition.profile_id,
                    target_capacity_factor=(
                        definition.target_capacity_factor
                    ),
                )

        except Exception as exc:
            if definition.name in self.network.generators.index:
                self.network.remove(
                    "Generator",
                    definition.name,
                )

            QMessageBox.critical(
                self,
                "Add Generator Failed",
                "Could not add the generator:\n\n"
                f"{exc}",
            )
            return

        self.network_modified.emit()
        self.refresh()

    # ------------------------------------------------------------------
    # Load creation
    # ------------------------------------------------------------------

    def _on_add_load(self) -> None:
        bus_names = self._valid_internal_bus_names()

        if not bus_names:
            self._show_no_internal_bus_warning()
            return

        dialog = LoadCreationDialog(
            bus_names=bus_names,
            suggested_name=self._next_component_name(
                table_name="loads",
                base_name="Load",
            ),
            suggested_carrier="electricity",
            parent=self,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        definition = dialog.definition()

        if definition.name in self.network.loads.index:
            QMessageBox.warning(
                self,
                "Load Already Exists",
                f'A load named "{definition.name}" already exists.',
            )
            return

        try:
            self.network.add(
                "Load",
                definition.name,
                bus=definition.bus,
                carrier=definition.carrier,
                p_set=definition.p_set,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Add Load Failed",
                "Could not add the load:\n\n"
                f"{exc}",
            )
            return

        self.network_modified.emit()
        self.refresh()

    def _on_add_store(self) -> None:
        bus_names = self._valid_internal_bus_names()

        if not bus_names:
            self._show_no_internal_bus_warning()
            return

        dialog = StoreCreationDialog(
            bus_names=bus_names,
            suggested_name=self._next_component_name(
                table_name="stores",
                base_name="Store",
            ),
            suggested_carrier="heat",
            parent=self,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        definition = dialog.definition()

        if definition.name in self.network.stores.index:
            QMessageBox.warning(
                self,
                "Store Already Exists",
                f'A store named "{definition.name}" already exists.',
            )
            return

        try:
            self.network.add(
                "Store",
                definition.name,
                bus=definition.bus,
                carrier=definition.carrier,
                e_nom=definition.e_nom,
                e_nom_extendable=definition.extendable,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Add Store Failed",
                "Could not add the store:\n\n"
                f"{exc}",
            )
            return

        self.network_modified.emit()
        self.refresh()

    def _on_add_storage_unit(self) -> None:
        bus_names = self._valid_internal_bus_names()

        if not bus_names:
            self._show_no_internal_bus_warning()
            return

        dialog = StorageUnitCreationDialog(
            bus_names=bus_names,
            suggested_name=self._next_component_name(
                table_name="storage_units",
                base_name="Storage Unit",
            ),
            suggested_carrier="battery",
            parent=self,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        definition = dialog.definition()

        if definition.name in self.network.storage_units.index:
            QMessageBox.warning(
                self,
                "Storage Unit Already Exists",
                (
                    f'A storage unit named "{definition.name}" '
                    "already exists."
                ),
            )
            return

        try:
            self.network.add(
                "StorageUnit",
                definition.name,
                bus=definition.bus,
                carrier=definition.carrier,
                p_nom=definition.p_nom,
                p_nom_extendable=definition.extendable,
                max_hours=definition.max_hours,
                efficiency_store=definition.efficiency_store,
                efficiency_dispatch=definition.efficiency_dispatch,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Add Storage Unit Failed",
                "Could not add the storage unit:\n\n"
                f"{exc}",
            )
            return

        self.network_modified.emit()
        self.refresh()

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _valid_internal_bus_names(self) -> list[str]:
        if (
            self.network is None
            or self.location is None
        ):
            return []

        return [
            bus_name
            for bus_name in self.location.bus_names
            if bus_name in self.network.buses.index
        ]

    def _show_no_internal_bus_warning(self) -> None:
        QMessageBox.warning(
            self,
            "No Internal Bus",
            (
                "Add an internal bus before "
                "adding components."
            ),
        )

    def _next_component_name(
        self,
        table_name: str,
        base_name: str,
    ) -> str:
        if self.network is None:
            return f"{base_name} 1"

        table = getattr(
            self.network,
            table_name,
        )
        existing_names = set(
            table.index.astype(str)
        )

        index = 1

        while (
            f"{base_name} {index}"
            in existing_names
        ):
            index += 1

        return f"{base_name} {index}"
