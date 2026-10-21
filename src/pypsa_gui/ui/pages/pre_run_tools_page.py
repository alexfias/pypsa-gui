from __future__ import annotations

import fnmatch

import pypsa
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


from pypsa_gui.services.capacity_constraints import (
    META_KEY,
    apply_capacity_limit,
    validate_capacity_constraints,
)
from pypsa_gui.services.metrics import load_timeseries
from pypsa_gui.services.preprocessing import (
    aggregate_snapshots,
    copy_for_preprocessing,
    commit_preprocessing,
)


class PreRunToolsPage(QWidget):
    network_modified = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.network: pypsa.Network | None = None

        root_layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root_layout.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)

        self.content_layout = QVBoxLayout(container)
        self.content_layout.setAlignment(Qt.AlignTop)

        self._build_load_shedding_group()
        self._build_capacity_constraints_group()
        self._build_downsampling_group()
        self._build_actions_group()

        self.preview_box = QTextEdit()
        self.preview_box.setReadOnly(True)
        self.preview_box.setPlaceholderText(
            "Preview of pre-run changes will appear here."
        )
        self.content_layout.addWidget(self.preview_box)

        self.content_layout.addStretch()

        self._refresh_state()

    def set_network(self, network: pypsa.Network | None) -> None:
        self.network = network
        self._refresh_state()

    def _refresh_state(self) -> None:
        has_network = self.network is not None

        for widget in [
            self.load_shedding_group,
            self.capacity_group,
            self.downsampling_group,
            self.actions_group,
        ]:
            widget.setEnabled(has_network)

        if not has_network:
            self.preview_box.setPlainText("No network loaded.")
        else:
            self.preview_box.setPlainText("Ready to configure pre-run tools.")

        self._update_load_shedding_enabled()
        self._update_load_shedding_mode()
        self._update_capacity_enabled()
        self._update_downsampling_enabled()

    def _build_load_shedding_group(self) -> None:
        self.load_shedding_group = QGroupBox("Load Shedding")
        layout = QFormLayout(self.load_shedding_group)

        self.enable_load_shedding_checkbox = QCheckBox(
            "Enable automatic load shedding generators"
        )
        self.enable_load_shedding_checkbox.setChecked(False)
        self.enable_load_shedding_checkbox.stateChanged.connect(
            self._update_load_shedding_enabled
        )
        layout.addRow(self.enable_load_shedding_checkbox)

        self.load_shedding_carrier_input = QLineEdit("load_shedding")
        layout.addRow("Carrier name:", self.load_shedding_carrier_input)

        self.load_shedding_cost_input = QDoubleSpinBox()
        self.load_shedding_cost_input.setRange(0.0, 1_000_000.0)
        self.load_shedding_cost_input.setDecimals(2)
        self.load_shedding_cost_input.setValue(10_000.0)
        self.load_shedding_cost_input.setSuffix(" €/MWh")
        layout.addRow("Penalty cost:", self.load_shedding_cost_input)

        self.load_shedding_p_nom_mode = QComboBox()
        self.load_shedding_p_nom_mode.addItems(
            [
                "Fixed value per bus",
                "Multiple of load at bus",
            ]
        )
        self.load_shedding_p_nom_mode.currentTextChanged.connect(
            self._update_load_shedding_mode
        )
        layout.addRow("Capacity definition:", self.load_shedding_p_nom_mode)

        self.load_shedding_fixed_capacity_input = QDoubleSpinBox()
        self.load_shedding_fixed_capacity_input.setRange(0.0, 1_000_000.0)
        self.load_shedding_fixed_capacity_input.setDecimals(2)
        self.load_shedding_fixed_capacity_input.setValue(1_000.0)
        self.load_shedding_fixed_capacity_input.setSuffix(" MW")
        layout.addRow("Fixed capacity:", self.load_shedding_fixed_capacity_input)

        self.load_shedding_multiple_input = QDoubleSpinBox()
        self.load_shedding_multiple_input.setRange(0.0, 1_000.0)
        self.load_shedding_multiple_input.setDecimals(2)
        self.load_shedding_multiple_input.setValue(2.0)
        layout.addRow("Load multiplier:", self.load_shedding_multiple_input)

        self.content_layout.addWidget(self.load_shedding_group)

    def _build_capacity_constraints_group(self) -> None:
        self.capacity_group = QGroupBox("Capacity Constraints")
        layout = QGridLayout(self.capacity_group)

        self.enable_capacity_checkbox = QCheckBox("Enable capacity constraints")
        self.enable_capacity_checkbox.setChecked(False)
        self.enable_capacity_checkbox.stateChanged.connect(
            self._update_capacity_enabled
        )
        layout.addWidget(self.enable_capacity_checkbox, 0, 0, 1, 2)

        self.capacity_component_combo = QComboBox()
        self.capacity_component_combo.addItems(
            [
                "Generators",
                "Links",
                "Stores",
                "Storage Units",
            ]
        )

        self.capacity_carrier_input = QLineEdit()
        self.capacity_carrier_input.setPlaceholderText("e.g. solar, onwind, battery")

        self.capacity_name_pattern_input = QLineEdit("*")
        self.capacity_name_pattern_input.setPlaceholderText("Name pattern, e.g. DE*")

        self.capacity_mode_combo = QComboBox()
        self.capacity_mode_combo.addItems(["=", ">=", "<="])

        self.capacity_scope_combo = QComboBox()
        self.capacity_scope_combo.addItems(
            [
                "Total capacity of all matches",
                "Limit each matching asset individually",
            ]
        )

        self.capacity_value_input = QDoubleSpinBox()
        self.capacity_value_input.setRange(0.0, 1_000_000_000.0)
        self.capacity_value_input.setDecimals(3)
        self.capacity_value_input.setValue(0.0)
        self.capacity_value_input.setSuffix(" MW")

        layout.addWidget(QLabel("Component:"), 1, 0)
        layout.addWidget(self.capacity_component_combo, 1, 1)

        layout.addWidget(QLabel("Carrier filter:"), 2, 0)
        layout.addWidget(self.capacity_carrier_input, 2, 1)

        layout.addWidget(QLabel("Name pattern:"), 3, 0)
        layout.addWidget(self.capacity_name_pattern_input, 3, 1)

        layout.addWidget(QLabel("Constraint:"), 4, 0)
        layout.addWidget(self.capacity_mode_combo, 4, 1)

        layout.addWidget(QLabel("Scope:"), 5, 0)
        layout.addWidget(self.capacity_scope_combo, 5, 1)

        layout.addWidget(QLabel("Value:"), 6, 0)
        layout.addWidget(self.capacity_value_input, 6, 1)

        self.capacity_component_combo.currentTextChanged.connect(
            self._update_capacity_units
        )
        self.capacity_note = QLabel(
            "Limits constrain extendable capacity; fixed assets retain their capacity and count "
            "toward totals. Per-asset limits tighten existing investment bounds."
        )
        self.capacity_note.setWordWrap(True)
        layout.addWidget(self.capacity_note, 7, 0, 1, 2)
        self.clear_capacity_button = QPushButton("Clear GUI Total Capacity Limits")
        self.clear_capacity_button.clicked.connect(self.clear_capacity_constraints)
        layout.addWidget(self.clear_capacity_button, 8, 0, 1, 2)
        self.content_layout.addWidget(self.capacity_group)

    def _build_downsampling_group(self) -> None:
        self.downsampling_group = QGroupBox("Temporal Downsampling")
        layout = QFormLayout(self.downsampling_group)

        self.enable_downsampling_checkbox = QCheckBox("Enable temporal downsampling")
        self.enable_downsampling_checkbox.setChecked(False)
        self.enable_downsampling_checkbox.stateChanged.connect(
            self._update_downsampling_enabled
        )
        layout.addRow(self.enable_downsampling_checkbox)

        self.downsampling_step_input = QSpinBox()
        self.downsampling_step_input.setRange(1, 10_000)
        self.downsampling_step_input.setValue(3)
        layout.addRow("Average blocks of n snapshots:", self.downsampling_step_input)

        note = QLabel(
            "Sums snapshot weights and averages input profiles. Preserves represented duration "
            "and weighted demand, but smooths peaks and changes storage/correlation detail. "
            "Unit commitment, ramp limits, state targets and multi-period networks are unsupported."
        )
        note.setWordWrap(True)
        layout.addRow(note)
        self.content_layout.addWidget(self.downsampling_group)

    def _build_actions_group(self) -> None:
        self.actions_group = QGroupBox("Actions")
        layout = QHBoxLayout(self.actions_group)

        self.preview_button = QPushButton("Preview Changes")
        self.preview_button.clicked.connect(self.preview_changes)

        self.apply_button = QPushButton("Apply Changes")
        self.apply_button.clicked.connect(self.apply_changes)

        layout.addWidget(self.preview_button)
        layout.addWidget(self.apply_button)

        self.content_layout.addWidget(self.actions_group)

    def _update_load_shedding_enabled(self) -> None:
        enabled = self.enable_load_shedding_checkbox.isChecked()

        for widget in [
            self.load_shedding_carrier_input,
            self.load_shedding_cost_input,
            self.load_shedding_p_nom_mode,
            self.load_shedding_fixed_capacity_input,
            self.load_shedding_multiple_input,
        ]:
            widget.setEnabled(enabled)

        self._update_load_shedding_mode()

    def _update_load_shedding_mode(self) -> None:
        enabled = self.enable_load_shedding_checkbox.isChecked()
        mode = self.load_shedding_p_nom_mode.currentText()
        is_fixed = mode == "Fixed value per bus"

        self.load_shedding_fixed_capacity_input.setEnabled(enabled and is_fixed)
        self.load_shedding_multiple_input.setEnabled(enabled and not is_fixed)

    def _update_capacity_enabled(self) -> None:
        enabled = self.enable_capacity_checkbox.isChecked()

        for widget in [
            self.capacity_component_combo,
            self.capacity_carrier_input,
            self.capacity_name_pattern_input,
            self.capacity_mode_combo,
            self.capacity_scope_combo,
            self.capacity_value_input,
        ]:
            widget.setEnabled(enabled)

    def _update_downsampling_enabled(self) -> None:
        enabled = self.enable_downsampling_checkbox.isChecked()
        self.downsampling_step_input.setEnabled(enabled)

    def preview_changes(self) -> None:
        if self.network is None:
            self.preview_box.setPlainText("No network loaded.")
            return

        lines: list[str] = []
        for definition in self.network.meta.get(META_KEY, []):
            lines.append(
                f"Applied total limit: {definition['table']} [{', '.join(definition['names'])}] "
                f"{definition['sense']} {definition['value']:g}"
            )

        if self.enable_load_shedding_checkbox.isChecked():
            n_buses = len(self.network.buses.index)
            lines.append("Load Shedding")
            lines.append(f"- Would add load shedding generators at {n_buses} buses.")
            lines.append(
                f"- Carrier: {self.load_shedding_carrier_input.text().strip() or 'load_shedding'}"
            )
            lines.append(
                f"- Marginal cost: {self.load_shedding_cost_input.value():.2f} €/MWh"
            )

            mode = self.load_shedding_p_nom_mode.currentText()
            if mode == "Fixed value per bus":
                lines.append(
                    f"- Fixed capacity per bus: {self.load_shedding_fixed_capacity_input.value():.2f} MW"
                )
            else:
                lines.append(
                    f"- Capacity = peak load at bus × {self.load_shedding_multiple_input.value():.2f}"
                )

        if self.enable_capacity_checkbox.isChecked():
            matches = self._get_capacity_matches()
            if matches is not None:
                table_name, df = matches
                if lines:
                    lines.append("")
                lines.append("Capacity Constraints")
                lines.append(f"- Matching {table_name}: {len(df)} assets")
                lines.append(
                    f"- Constraint: {self.capacity_mode_combo.currentText()} "
                    f"{self.capacity_value_input.value():.3f}{self.capacity_value_input.suffix()}"
                )
                lines.append(f"- Scope: {self.capacity_scope_combo.currentText()}")

        if self.enable_downsampling_checkbox.isChecked():
            step = self.downsampling_step_input.value()
            old_n = len(self.network.snapshots)
            new_n = len(self.network.snapshots[::step])
            if lines:
                lines.append("")
            lines.append("Temporal Downsampling")
            lines.append(f"- Snapshots: {old_n} -> {new_n}")
            lines.append(
                f"- Rule: weighted averages of consecutive blocks of {step}; sum all weights"
            )

        if not lines:
            lines.append("No changes configured.")

        self.preview_box.setPlainText("\n".join(lines))

    def apply_changes(self) -> None:
        if self.network is None:
            QMessageBox.warning(self, "No network", "Please load a network first.")
            return

        enabled = any(
            widget.isChecked()
            for widget in (
                self.enable_load_shedding_checkbox,
                self.enable_capacity_checkbox,
                self.enable_downsampling_checkbox,
            )
        )
        if not enabled:
            QMessageBox.information(
                self, "No changes", "No pre-run tools were enabled."
            )
            return
        summary: list[str] = []
        try:
            candidate = copy_for_preprocessing(self.network)
            if self.enable_load_shedding_checkbox.isChecked():
                added = self._apply_load_shedding(candidate)
                summary.append(f"Added {added} load shedding generators.")
            if self.enable_capacity_checkbox.isChecked():
                summary.append(self._apply_capacity_constraints(candidate))
            if self.enable_downsampling_checkbox.isChecked():
                old_n, new_n = self._apply_downsampling(candidate)
                summary.append(
                    f"Averaged snapshots from {old_n} to {new_n}; summed snapshot weights."
                )
            validate_capacity_constraints(candidate)
        except (ValueError, TypeError, KeyError) as exc:
            QMessageBox.warning(
                self, "Invalid pre-run changes", f"No changes were applied.\n\n{exc}"
            )
            return
        commit_preprocessing(self.network, candidate)
        summary.append("Previous results cleared; run optimisation again.")
        self.network_modified.emit()
        self.preview_box.setPlainText("\n".join(summary))
        QMessageBox.information(self, "Changes applied", "\n".join(summary))

    def _update_capacity_units(self) -> None:
        self.capacity_value_input.setSuffix(
            " MWh" if self.capacity_component_combo.currentText() == "Stores" else " MW"
        )

    def clear_capacity_constraints(self) -> None:
        if self.network is None or not self.network.meta.get(META_KEY):
            return
        candidate = copy_for_preprocessing(self.network)
        candidate.meta.pop(META_KEY, None)
        commit_preprocessing(self.network, candidate)
        self.network_modified.emit()
        self.preview_box.setPlainText(
            "GUI total capacity limits cleared. Per-asset bounds remain in component tables. Rerun optimisation."
        )

    def _get_capacity_matches(self, network=None) -> tuple[str, object] | None:
        network = network if network is not None else self.network
        if network is None:
            return None

        component_name = self.capacity_component_combo.currentText()
        carrier_filter = self.capacity_carrier_input.text().strip()
        pattern = self.capacity_name_pattern_input.text().strip() or "*"

        mapping = {
            "Generators": ("generators", network.generators),
            "Links": ("links", network.links),
            "Stores": ("stores", network.stores),
            "Storage Units": ("storage_units", network.storage_units),
        }

        table_name, df = mapping[component_name]
        if df.empty:
            return table_name, df

        mask = df.index.to_series().apply(lambda x: fnmatch.fnmatch(str(x), pattern))

        if carrier_filter and "carrier" in df.columns:
            mask &= df["carrier"].astype(str) == carrier_filter

        return table_name, df.loc[mask]

    def _apply_load_shedding(self, network=None) -> int:
        network = network if network is not None else self.network
        assert network is not None

        carrier = self.load_shedding_carrier_input.text().strip() or "load_shedding"
        marginal_cost = self.load_shedding_cost_input.value()
        mode = self.load_shedding_p_nom_mode.currentText()

        if carrier not in network.carriers.index:
            network.add("Carrier", carrier, co2_emissions=0.0)
        added = 0

        for bus_name in network.buses.index:
            gen_name = f"{bus_name} load shedding"

            if gen_name in network.generators.index:
                continue

            if mode == "Fixed value per bus":
                p_nom = self.load_shedding_fixed_capacity_input.value()
            else:
                p_nom = (
                    self._estimate_bus_peak_load(bus_name, network)
                    * self.load_shedding_multiple_input.value()
                )

            network.add(
                "Generator",
                gen_name,
                bus=bus_name,
                carrier=carrier,
                p_nom=p_nom,
                marginal_cost=marginal_cost,
            )
            added += 1

        return added

    def _estimate_bus_peak_load(self, bus_name: str, network=None) -> float:
        network = network if network is not None else self.network
        assert network is not None
        names = network.loads.index[network.loads.bus == bus_name]
        if names.empty:
            return 0.0
        return max(0.0, float(load_timeseries(network)[names].sum(axis=1).max()))

    def _apply_capacity_constraints(self, network=None) -> str:
        network = network if network is not None else self.network
        matches = self._get_capacity_matches(network)
        if matches is None:
            raise ValueError("No network loaded.")
        table_name, selected = matches
        return apply_capacity_limit(
            network,
            table_name,
            list(selected.index),
            self.capacity_mode_combo.currentText(),
            self.capacity_value_input.value(),
            aggregate=self.capacity_scope_combo.currentText()
            == "Total capacity of all matches",
        )

    def _apply_downsampling(self, network=None) -> tuple[int, int]:
        network = network if network is not None else self.network
        assert network is not None
        return aggregate_snapshots(network, self.downsampling_step_input.value())
