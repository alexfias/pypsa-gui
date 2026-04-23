from __future__ import annotations

import fnmatch

import pypsa
from PySide6.QtCore import Qt
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


class PreRunToolsPage(QWidget):
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
        self.preview_box.setPlaceholderText("Preview of pre-run changes will appear here.")
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

        self.enable_load_shedding_checkbox = QCheckBox("Enable automatic load shedding generators")
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
        self.load_shedding_p_nom_mode.addItems([
            "Fixed value per bus",
            "Multiple of load at bus",
        ])
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
        self.capacity_component_combo.addItems([
            "Generators",
            "Links",
            "Stores",
            "Storage Units",
        ])

        self.capacity_carrier_input = QLineEdit()
        self.capacity_carrier_input.setPlaceholderText("e.g. solar, onwind, battery")

        self.capacity_name_pattern_input = QLineEdit("*")
        self.capacity_name_pattern_input.setPlaceholderText("Name pattern, e.g. DE*")

        self.capacity_mode_combo = QComboBox()
        self.capacity_mode_combo.addItems(["=", ">=", "<="])

        self.capacity_scope_combo = QComboBox()
        self.capacity_scope_combo.addItems([
            "Total capacity of all matches",
            "Set each matching asset individually",
        ])

        self.capacity_value_input = QDoubleSpinBox()
        self.capacity_value_input.setRange(-1_000_000.0, 1_000_000_000.0)
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
        layout.addRow("Keep every n-th snapshot:", self.downsampling_step_input)

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

        if self.enable_load_shedding_checkbox.isChecked():
            n_buses = len(self.network.buses.index)
            lines.append("Load Shedding")
            lines.append(f"- Would add load shedding generators at {n_buses} buses.")
            lines.append(f"- Carrier: {self.load_shedding_carrier_input.text().strip() or 'load_shedding'}")
            lines.append(f"- Marginal cost: {self.load_shedding_cost_input.value():.2f} €/MWh")

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
                    f"{self.capacity_value_input.value():.3f} MW"
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
            lines.append(f"- Rule: keep every {step}-th snapshot")

        if not lines:
            lines.append("No changes configured.")

        self.preview_box.setPlainText("\n".join(lines))

    def apply_changes(self) -> None:
        if self.network is None:
            QMessageBox.warning(self, "No network", "Please load a network first.")
            return

        summary: list[str] = []

        if self.enable_load_shedding_checkbox.isChecked():
            added = self._apply_load_shedding()
            summary.append(f"Added {added} load shedding generators.")

        if self.enable_capacity_checkbox.isChecked():
            capacity_msg = self._apply_capacity_constraints()
            if capacity_msg:
                summary.append(capacity_msg)

        if self.enable_downsampling_checkbox.isChecked():
            old_n, new_n = self._apply_downsampling()
            summary.append(f"Downsampled snapshots from {old_n} to {new_n}.")

        if not summary:
            QMessageBox.information(self, "No changes", "No pre-run tools were enabled.")
            return

        self.preview_box.setPlainText("\n".join(summary))
        QMessageBox.information(self, "Changes applied", "\n".join(summary))

    def _get_capacity_matches(self) -> tuple[str, object] | None:
        if self.network is None:
            return None

        component_name = self.capacity_component_combo.currentText()
        carrier_filter = self.capacity_carrier_input.text().strip()
        pattern = self.capacity_name_pattern_input.text().strip() or "*"

        mapping = {
            "Generators": ("generators", self.network.generators),
            "Links": ("links", self.network.links),
            "Stores": ("stores", self.network.stores),
            "Storage Units": ("storage_units", self.network.storage_units),
        }

        table_name, df = mapping[component_name]
        if df.empty:
            return table_name, df

        mask = df.index.to_series().apply(lambda x: fnmatch.fnmatch(str(x), pattern))

        if carrier_filter and "carrier" in df.columns:
            mask &= df["carrier"].astype(str) == carrier_filter

        return table_name, df.loc[mask]

    def _apply_load_shedding(self) -> int:
        assert self.network is not None

        carrier = self.load_shedding_carrier_input.text().strip() or "load_shedding"
        marginal_cost = self.load_shedding_cost_input.value()
        mode = self.load_shedding_p_nom_mode.currentText()

        added = 0

        for bus_name in self.network.buses.index:
            gen_name = f"{bus_name} load shedding"

            if gen_name in self.network.generators.index:
                continue

            if mode == "Fixed value per bus":
                p_nom = self.load_shedding_fixed_capacity_input.value()
            else:
                p_nom = self._estimate_bus_peak_load(bus_name) * self.load_shedding_multiple_input.value()

            self.network.add(
                "Generator",
                gen_name,
                bus=bus_name,
                carrier=carrier,
                p_nom=p_nom,
                marginal_cost=marginal_cost,
            )
            added += 1

        return added

    def _estimate_bus_peak_load(self, bus_name: str) -> float:
        assert self.network is not None

        loads = self.network.loads
        if loads.empty:
            return 0.0

        bus_loads = loads.index[loads["bus"] == bus_name]
        if len(bus_loads) == 0:
            return 0.0

        if hasattr(self.network, "loads_t") and hasattr(self.network.loads_t, "p_set"):
            ts = self.network.loads_t.p_set
            available = [col for col in bus_loads if col in ts.columns]
            if available:
                return float(ts[available].sum(axis=1).max())

        return 0.0

    def _apply_capacity_constraints(self) -> str | None:
        if self.network is None:
            return None

        matches = self._get_capacity_matches()
        if matches is None:
            return None

        table_name, df = matches
        if df.empty:
            return f"No matching assets found in {table_name}."

        mode = self.capacity_mode_combo.currentText()
        scope = self.capacity_scope_combo.currentText()
        value = self.capacity_value_input.value()

        if table_name in {"generators", "links", "storage_units"}:
            nominal_col = "p_nom"
        elif table_name == "stores":
            nominal_col = "e_nom"
        else:
            return None

        if nominal_col not in df.columns:
            return f"Column {nominal_col} not available in {table_name}."

        network_df = getattr(self.network, table_name)

        if scope == "Set each matching asset individually":
            for idx in df.index:
                if mode == "=":
                    network_df.at[idx, nominal_col] = value
                elif mode == ">=":
                    current = float(network_df.at[idx, nominal_col])
                    network_df.at[idx, nominal_col] = max(current, value)
                elif mode == "<=":
                    current = float(network_df.at[idx, nominal_col])
                    network_df.at[idx, nominal_col] = min(current, value)

            return f"Updated {len(df)} assets in {table_name}."

        total_current = float(df[nominal_col].sum())

        if mode == "=":
            target_total = value
        elif mode == ">=":
            target_total = max(total_current, value)
        else:
            target_total = min(total_current, value)

        if total_current <= 0 and len(df) > 0:
            share = target_total / len(df)
            for idx in df.index:
                network_df.at[idx, nominal_col] = share
        elif total_current > 0:
            factor = target_total / total_current
            for idx in df.index:
                current = float(network_df.at[idx, nominal_col])
                network_df.at[idx, nominal_col] = current * factor

        return (
            f"Scaled total {nominal_col} in {table_name} "
            f"from {total_current:.3f} to {target_total:.3f}."
        )

    def _apply_downsampling(self) -> tuple[int, int]:
        assert self.network is not None

        step = self.downsampling_step_input.value()
        old_n = len(self.network.snapshots)
        new_snapshots = self.network.snapshots[::step]
        self.network.set_snapshots(new_snapshots)
        new_n = len(self.network.snapshots)

        return old_n, new_n