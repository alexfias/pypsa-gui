from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pypsa_gui.models.time_series_profile import TimeSeriesProfile

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class InternalBusDefinition:
    name: str
    carrier: str


class GeneratorProfileMode(str, Enum):
    CONSTANT = "constant"
    EXISTING = "existing"
    SCALED = "scaled"


@dataclass(frozen=True)
class GeneratorDefinition:
    name: str
    bus: str
    carrier: str
    p_nom: float
    capital_cost: float
    marginal_cost: float
    efficiency: float
    lifetime: float
    extendable: bool
    profile_mode: GeneratorProfileMode
    constant_p_max_pu: float
    profile_id: str | None
    target_capacity_factor: float | None


@dataclass(frozen=True)
class LoadDefinition:
    name: str
    bus: str
    p_set: float
    carrier: str


@dataclass(frozen=True)
class StoreDefinition:
    name: str
    bus: str
    carrier: str
    e_nom: float
    extendable: bool


@dataclass(frozen=True)
class StorageUnitDefinition:
    name: str
    bus: str
    carrier: str
    p_nom: float
    max_hours: float
    efficiency_store: float
    efficiency_dispatch: float
    extendable: bool


class InternalBusCreationDialog(QDialog):
    def __init__(
        self,
        suggested_name: str,
        suggested_carrier: str = "heat",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle("Add Internal Bus")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(
            suggested_name
        )
        self.carrier_edit = QLineEdit(
            suggested_carrier
        )

        form.addRow(
            "Bus name",
            self.name_edit,
        )
        form.addRow(
            "Carrier",
            self.carrier_edit,
        )

        layout.addLayout(form)

        note = QLabel(
            "The new bus will inherit the geographic coordinates "
            "of the selected location."
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

    def _validate_and_accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(
                self,
                "Invalid Bus Name",
                "The bus name cannot be empty.",
            )
            return

        if not self.carrier_edit.text().strip():
            QMessageBox.warning(
                self,
                "Invalid Carrier",
                "The bus carrier cannot be empty.",
            )
            return

        self.accept()

    def definition(self) -> InternalBusDefinition:
        return InternalBusDefinition(
            name=self.name_edit.text().strip(),
            carrier=self.carrier_edit.text().strip(),
        )


class GeneratorCreationDialog(QDialog):
    def __init__(
        self,
        bus_names: list[str],
        suggested_name: str,
        available_profiles: list[TimeSeriesProfile],
        suggested_carrier: str = "solar",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle("Add Generator")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(
            suggested_name
        )

        self.bus_combo = QComboBox()
        self.bus_combo.addItems(
            bus_names
        )

        self.carrier_edit = QLineEdit(
            suggested_carrier
        )

        self.p_nom_spin = QDoubleSpinBox()
        self.p_nom_spin.setRange(
            0.0,
            1_000_000.0,
        )
        self.p_nom_spin.setDecimals(3)
        self.p_nom_spin.setSuffix(" MW")
        self.p_nom_spin.setValue(100.0)

        self.capital_cost_spin = QDoubleSpinBox()
        self.capital_cost_spin.setRange(
            0.0,
            1_000_000_000.0,
        )
        self.capital_cost_spin.setDecimals(4)
        self.capital_cost_spin.setSuffix(
            " currency/MW"
        )
        self.capital_cost_spin.setValue(0.0)

        self.marginal_cost_spin = QDoubleSpinBox()
        self.marginal_cost_spin.setRange(
            -1_000_000.0,
            1_000_000.0,
        )
        self.marginal_cost_spin.setDecimals(4)
        self.marginal_cost_spin.setSuffix(" currency/MWh")
        self.marginal_cost_spin.setValue(0.0)

        self.efficiency_spin = QDoubleSpinBox()
        self.efficiency_spin.setRange(
            0.0,
            1.0,
        )
        self.efficiency_spin.setDecimals(4)
        self.efficiency_spin.setSingleStep(0.01)
        self.efficiency_spin.setValue(1.0)

        self.lifetime_spin = QDoubleSpinBox()
        self.lifetime_spin.setRange(
            0.0,
            1_000.0,
        )
        self.lifetime_spin.setDecimals(2)
        self.lifetime_spin.setSuffix(" years")
        self.lifetime_spin.setValue(25.0)

        self.extendable_combo = QComboBox()
        self.extendable_combo.addItem(
            "No",
            False,
        )
        self.extendable_combo.addItem(
            "Yes",
            True,
        )

        self.profile_mode_combo = QComboBox()
        self.profile_mode_combo.addItem(
            "Constant availability",
            GeneratorProfileMode.CONSTANT,
        )
        self.profile_mode_combo.addItem(
            "Use existing time series",
            GeneratorProfileMode.EXISTING,
        )
        self.profile_mode_combo.addItem(
            "Scale existing time series",
            GeneratorProfileMode.SCALED,
        )

        self.constant_p_max_pu_spin = QDoubleSpinBox()
        self.constant_p_max_pu_spin.setRange(0.0, 1.0)
        self.constant_p_max_pu_spin.setDecimals(4)
        self.constant_p_max_pu_spin.setSingleStep(0.05)
        self.constant_p_max_pu_spin.setValue(1.0)

        self.profile_combo = QComboBox()

        if not available_profiles:
            self.profile_combo.addItem(
                "No time-series profiles available",
                None,
            )
        else:
            for profile in available_profiles:
                source_type = profile.metadata.get(
                    "source_type",
                    "profile",
                )

                self.profile_combo.addItem(
                    (
                        f"{profile.name} — "
                        f"{profile.region} — "
                        f"CF {profile.capacity_factor:.3f} — "
                        f"{source_type}"
                    ),
                    profile.id,
                )

        self.target_capacity_factor_spin = QDoubleSpinBox()
        self.target_capacity_factor_spin.setRange(0.0, 1.0)
        self.target_capacity_factor_spin.setDecimals(4)
        self.target_capacity_factor_spin.setSingleStep(0.01)
        self.target_capacity_factor_spin.setValue(0.35)

        form.addRow(
            "Generator name",
            self.name_edit,
        )
        form.addRow(
            "Bus",
            self.bus_combo,
        )
        form.addRow(
            "Carrier",
            self.carrier_edit,
        )
        form.addRow(
            "Nominal capacity",
            self.p_nom_spin,
        )
        form.addRow(
            "Capital cost",
            self.capital_cost_spin,
        )
        form.addRow(
            "Marginal cost",
            self.marginal_cost_spin,
        )
        form.addRow(
            "Efficiency",
            self.efficiency_spin,
        )
        form.addRow(
            "Lifetime",
            self.lifetime_spin,
        )
        form.addRow(
            "Extendable",
            self.extendable_combo,
        )
        form.addRow(
            "Availability mode",
            self.profile_mode_combo,
        )
        form.addRow(
            "Constant p_max_pu",
            self.constant_p_max_pu_spin,
        )
        form.addRow(
            "Time-series profile",
            self.profile_combo,
        )
        form.addRow(
            "Target capacity factor",
            self.target_capacity_factor_spin,
        )

        layout.addLayout(form)

        self._available_profiles = list(
            available_profiles
        )

        self.profile_mode_combo.currentIndexChanged.connect(
            self._update_profile_controls
        )
        self.carrier_edit.textChanged.connect(
            self._refresh_profile_choices
        )
        self._refresh_profile_choices()

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

    def _refresh_profile_choices(self) -> None:
        selected_profile_id = (
            self.profile_combo.currentData()
        )
        carrier = (
            self.carrier_edit.text()
            .strip()
            .lower()
        )

        matching_profiles = [
            profile
            for profile in self._available_profiles
            if (
                not carrier
                or not profile.carrier
                or profile.carrier.strip().lower()
                == carrier
            )
        ]

        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()

        if not matching_profiles:
            self.profile_combo.addItem(
                "No matching time-series profiles",
                None,
            )
        else:
            selected_index = 0

            for index, profile in enumerate(
                matching_profiles
            ):
                source_type = profile.metadata.get(
                    "source_type",
                    "profile",
                )

                self.profile_combo.addItem(
                    (
                        f"{profile.name} — "
                        f"{profile.region} — "
                        f"CF {profile.capacity_factor:.3f} — "
                        f"{source_type}"
                    ),
                    profile.id,
                )

                if profile.id == selected_profile_id:
                    selected_index = index

            self.profile_combo.setCurrentIndex(
                selected_index
            )

        self.profile_combo.blockSignals(False)
        self._update_profile_controls()

    def _update_profile_controls(self) -> None:
        mode = self.profile_mode_combo.currentData()

        self.constant_p_max_pu_spin.setEnabled(
            mode == GeneratorProfileMode.CONSTANT
        )
        self.profile_combo.setEnabled(
            mode in {
                GeneratorProfileMode.EXISTING,
                GeneratorProfileMode.SCALED,
            }
        )
        self.target_capacity_factor_spin.setEnabled(
            mode == GeneratorProfileMode.SCALED
        )

    def _validate_and_accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(
                self,
                "Invalid Generator Name",
                "The generator name cannot be empty.",
            )
            return

        if not self.bus_combo.currentText():
            QMessageBox.warning(
                self,
                "No Bus Selected",
                "Select a bus for the generator.",
            )
            return

        if not self.carrier_edit.text().strip():
            QMessageBox.warning(
                self,
                "Invalid Carrier",
                "The generator carrier cannot be empty.",
            )
            return

        mode = self.profile_mode_combo.currentData()

        if (
            mode in {
                GeneratorProfileMode.EXISTING,
                GeneratorProfileMode.SCALED,
            }
            and self.profile_combo.currentData() is None
        ):
            QMessageBox.warning(
                self,
                "No Profile Selected",
                "Select a time-series profile.",
            )
            return

        self.accept()

    def definition(self) -> GeneratorDefinition:
        return GeneratorDefinition(
            name=self.name_edit.text().strip(),
            bus=self.bus_combo.currentText(),
            carrier=self.carrier_edit.text().strip(),
            p_nom=self.p_nom_spin.value(),
            capital_cost=self.capital_cost_spin.value(),
            marginal_cost=self.marginal_cost_spin.value(),
            efficiency=self.efficiency_spin.value(),
            lifetime=self.lifetime_spin.value(),
            extendable=bool(
                self.extendable_combo.currentData()
            ),
            profile_mode=self.profile_mode_combo.currentData(),
            constant_p_max_pu=(
                self.constant_p_max_pu_spin.value()
            ),
            profile_id=(
                str(self.profile_combo.currentData())
                if self.profile_combo.currentData() is not None
                else None
            ),
            target_capacity_factor=(
                self.target_capacity_factor_spin.value()
                if (
                    self.profile_mode_combo.currentData()
                    == GeneratorProfileMode.SCALED
                )
                else None
            ),
        )


class LoadCreationDialog(QDialog):
    def __init__(
        self,
        bus_names: list[str],
        suggested_name: str,
        suggested_carrier: str = "electricity",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle("Add Load")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(
            suggested_name
        )

        self.bus_combo = QComboBox()
        self.bus_combo.addItems(
            bus_names
        )

        self.carrier_edit = QLineEdit(
            suggested_carrier
        )

        self.p_set_spin = QDoubleSpinBox()
        self.p_set_spin.setRange(
            0.0,
            1_000_000.0,
        )
        self.p_set_spin.setDecimals(3)
        self.p_set_spin.setSuffix(" MW")
        self.p_set_spin.setValue(100.0)

        form.addRow(
            "Load name",
            self.name_edit,
        )
        form.addRow(
            "Bus",
            self.bus_combo,
        )
        form.addRow(
            "Carrier",
            self.carrier_edit,
        )
        form.addRow(
            "Constant demand",
            self.p_set_spin,
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
                "Invalid Load Name",
                "The load name cannot be empty.",
            )
            return

        if not self.bus_combo.currentText():
            QMessageBox.warning(
                self,
                "No Bus Selected",
                "Select a bus for the load.",
            )
            return

        self.accept()

    def definition(self) -> LoadDefinition:
        return LoadDefinition(
            name=self.name_edit.text().strip(),
            bus=self.bus_combo.currentText(),
            p_set=self.p_set_spin.value(),
            carrier=self.carrier_edit.text().strip(),
        )


class StoreCreationDialog(QDialog):
    def __init__(
        self,
        bus_names: list[str],
        suggested_name: str,
        suggested_carrier: str = "heat",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle("Add Store")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(
            suggested_name
        )

        self.bus_combo = QComboBox()
        self.bus_combo.addItems(
            bus_names
        )

        self.carrier_edit = QLineEdit(
            suggested_carrier
        )

        self.e_nom_spin = QDoubleSpinBox()
        self.e_nom_spin.setRange(
            0.0,
            1_000_000_000.0,
        )
        self.e_nom_spin.setDecimals(3)
        self.e_nom_spin.setSuffix(" MWh")
        self.e_nom_spin.setValue(100.0)

        self.extendable_combo = QComboBox()
        self.extendable_combo.addItem(
            "No",
            False,
        )
        self.extendable_combo.addItem(
            "Yes",
            True,
        )

        form.addRow(
            "Store name",
            self.name_edit,
        )
        form.addRow(
            "Bus",
            self.bus_combo,
        )
        form.addRow(
            "Carrier",
            self.carrier_edit,
        )
        form.addRow(
            "Energy capacity",
            self.e_nom_spin,
        )
        form.addRow(
            "Extendable",
            self.extendable_combo,
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
                "Invalid Store Name",
                "The store name cannot be empty.",
            )
            return

        if not self.bus_combo.currentText():
            QMessageBox.warning(
                self,
                "No Bus Selected",
                "Select a bus for the store.",
            )
            return

        self.accept()

    def definition(self) -> StoreDefinition:
        return StoreDefinition(
            name=self.name_edit.text().strip(),
            bus=self.bus_combo.currentText(),
            carrier=self.carrier_edit.text().strip(),
            e_nom=self.e_nom_spin.value(),
            extendable=bool(
                self.extendable_combo.currentData()
            ),
        )


class StorageUnitCreationDialog(QDialog):
    def __init__(
        self,
        bus_names: list[str],
        suggested_name: str,
        suggested_carrier: str = "battery",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle("Add Storage Unit")
        self.setMinimumWidth(430)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(
            suggested_name
        )

        self.bus_combo = QComboBox()
        self.bus_combo.addItems(
            bus_names
        )

        self.carrier_edit = QLineEdit(
            suggested_carrier
        )

        self.p_nom_spin = QDoubleSpinBox()
        self.p_nom_spin.setRange(
            0.0,
            1_000_000.0,
        )
        self.p_nom_spin.setDecimals(3)
        self.p_nom_spin.setSuffix(" MW")
        self.p_nom_spin.setValue(100.0)

        self.max_hours_spin = QDoubleSpinBox()
        self.max_hours_spin.setRange(
            0.0,
            100_000.0,
        )
        self.max_hours_spin.setDecimals(3)
        self.max_hours_spin.setSuffix(" h")
        self.max_hours_spin.setValue(4.0)

        self.efficiency_store_spin = QDoubleSpinBox()
        self.efficiency_store_spin.setRange(
            0.0,
            1.0,
        )
        self.efficiency_store_spin.setDecimals(4)
        self.efficiency_store_spin.setValue(0.9)

        self.efficiency_dispatch_spin = QDoubleSpinBox()
        self.efficiency_dispatch_spin.setRange(
            0.0,
            1.0,
        )
        self.efficiency_dispatch_spin.setDecimals(4)
        self.efficiency_dispatch_spin.setValue(0.9)

        self.extendable_combo = QComboBox()
        self.extendable_combo.addItem(
            "No",
            False,
        )
        self.extendable_combo.addItem(
            "Yes",
            True,
        )

        form.addRow(
            "Storage unit name",
            self.name_edit,
        )
        form.addRow(
            "Bus",
            self.bus_combo,
        )
        form.addRow(
            "Carrier",
            self.carrier_edit,
        )
        form.addRow(
            "Nominal power",
            self.p_nom_spin,
        )
        form.addRow(
            "Maximum duration",
            self.max_hours_spin,
        )
        form.addRow(
            "Charging efficiency",
            self.efficiency_store_spin,
        )
        form.addRow(
            "Discharging efficiency",
            self.efficiency_dispatch_spin,
        )
        form.addRow(
            "Extendable",
            self.extendable_combo,
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
                "Invalid Storage Unit Name",
                "The storage unit name cannot be empty.",
            )
            return

        if not self.bus_combo.currentText():
            QMessageBox.warning(
                self,
                "No Bus Selected",
                "Select a bus for the storage unit.",
            )
            return

        self.accept()

    def definition(self) -> StorageUnitDefinition:
        return StorageUnitDefinition(
            name=self.name_edit.text().strip(),
            bus=self.bus_combo.currentText(),
            carrier=self.carrier_edit.text().strip(),
            p_nom=self.p_nom_spin.value(),
            max_hours=self.max_hours_spin.value(),
            efficiency_store=self.efficiency_store_spin.value(),
            efficiency_dispatch=self.efficiency_dispatch_spin.value(),
            extendable=bool(
                self.extendable_combo.currentData()
            ),
        )
