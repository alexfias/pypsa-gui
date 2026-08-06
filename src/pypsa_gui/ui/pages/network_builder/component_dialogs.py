from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True)
class GeneratorDefinition:
    name: str
    bus: str
    carrier: str
    p_nom: float
    marginal_cost: float
    extendable: bool


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

        self.marginal_cost_spin = QDoubleSpinBox()
        self.marginal_cost_spin.setRange(
            -1_000_000.0,
            1_000_000.0,
        )
        self.marginal_cost_spin.setDecimals(4)
        self.marginal_cost_spin.setSuffix(" currency/MWh")
        self.marginal_cost_spin.setValue(0.0)

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
            "Marginal cost",
            self.marginal_cost_spin,
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

        self.accept()

    def definition(self) -> GeneratorDefinition:
        return GeneratorDefinition(
            name=self.name_edit.text().strip(),
            bus=self.bus_combo.currentText(),
            carrier=self.carrier_edit.text().strip(),
            p_nom=self.p_nom_spin.value(),
            marginal_cost=self.marginal_cost_spin.value(),
            extendable=bool(
                self.extendable_combo.currentData()
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
