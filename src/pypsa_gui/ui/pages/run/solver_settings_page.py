# src/pypsa_gui/ui/pages/run/solver_settings_page.py
from __future__ import annotations

import json
from copy import deepcopy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pypsa_gui.models.solver_settings import SolverSettings


class SolverSettingsPage(QWidget):
    settings_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._settings = SolverSettings()

        root_layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root_layout.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)

        self.content_layout = QVBoxLayout(container)
        self.content_layout.setAlignment(Qt.AlignTop)

        instructions = QLabel(
            "Click Apply to use these settings for the active network's preview "
            "and optimisation. Settings are retained while the network is open. "
            "Without an active network, Apply sets defaults for new sessions."
        )
        instructions.setWordWrap(True)
        self.content_layout.addWidget(instructions)

        self._build_solver_group()
        self._build_general_group()
        self._build_numeric_group()
        self._build_extra_options_group()
        self._build_buttons()

        self.content_layout.addStretch()

        self.solver_combo.currentTextChanged.connect(self._update_solver_controls)
        self.load_settings(self._settings)

    def _build_solver_group(self) -> None:
        box = QGroupBox("Solver")
        layout = QFormLayout(box)

        self.solver_combo = QComboBox()
        self.solver_combo.addItems(["highs", "gurobi"])
        layout.addRow("Solver name:", self.solver_combo)

        self.content_layout.addWidget(box)

    def _build_general_group(self) -> None:
        box = QGroupBox("General")
        layout = QVBoxLayout(box)

        self.assign_duals_checkbox = QCheckBox("Assign all duals")
        self.transmission_losses_checkbox = QCheckBox("Include transmission losses")
        self.linearized_uc_checkbox = QCheckBox("Use linearized unit commitment")

        layout.addWidget(self.assign_duals_checkbox)
        layout.addWidget(self.transmission_losses_checkbox)
        layout.addWidget(self.linearized_uc_checkbox)

        self.content_layout.addWidget(box)

    def _build_numeric_group(self) -> None:
        box = QGroupBox("Solver options")
        layout = QFormLayout(box)

        self.method_spin = QSpinBox()
        self.method_spin.setRange(-1, 4)
        self.method_spin.setSpecialValueText("Auto")
        self.method_spin.setValue(-1)

        self.crossover_spin = QSpinBox()
        self.crossover_spin.setRange(-1, 1)
        self.crossover_spin.setSpecialValueText("Auto")
        self.crossover_spin.setValue(-1)

        self.presolve_spin = QSpinBox()
        self.presolve_spin.setRange(-1, 2)
        self.presolve_spin.setSpecialValueText("Auto")
        self.presolve_spin.setValue(-1)

        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(0, 256)
        self.threads_spin.setSpecialValueText("Auto")
        self.threads_spin.setValue(0)

        self.time_limit_spin = QDoubleSpinBox()
        self.time_limit_spin.setRange(0.0, 1_000_000.0)
        self.time_limit_spin.setDecimals(1)
        self.time_limit_spin.setSuffix(" s")
        self.time_limit_spin.setSpecialValueText("None")
        self.time_limit_spin.setValue(0.0)

        self.mip_gap_spin = QDoubleSpinBox()
        self.mip_gap_spin.setRange(-1.0, 1.0)
        self.mip_gap_spin.setDecimals(6)
        self.mip_gap_spin.setSingleStep(0.001)
        self.mip_gap_spin.setSpecialValueText("Default")
        self.mip_gap_spin.setValue(-1.0)

        self.feasibility_tol_spin = QDoubleSpinBox()
        self.feasibility_tol_spin.setRange(0.0, 1.0)
        self.feasibility_tol_spin.setDecimals(10)
        self.feasibility_tol_spin.setSingleStep(1e-6)
        self.feasibility_tol_spin.setSpecialValueText("None")
        self.feasibility_tol_spin.setValue(0.0)

        self.optimality_tol_spin = QDoubleSpinBox()
        self.optimality_tol_spin.setRange(0.0, 1.0)
        self.optimality_tol_spin.setDecimals(10)
        self.optimality_tol_spin.setSingleStep(1e-6)
        self.optimality_tol_spin.setSpecialValueText("None")
        self.optimality_tol_spin.setValue(0.0)

        layout.addRow("Method:", self.method_spin)
        layout.addRow("Crossover:", self.crossover_spin)
        layout.addRow("Presolve:", self.presolve_spin)
        layout.addRow("Threads:", self.threads_spin)
        layout.addRow("Time limit:", self.time_limit_spin)
        layout.addRow("MIP gap:", self.mip_gap_spin)
        layout.addRow("Feasibility tolerance:", self.feasibility_tol_spin)
        layout.addRow("Dual optimality tolerance:", self.optimality_tol_spin)
        self.optimality_tol_spin.setToolTip(
            "Gurobi OptimalityTol / HiGHS dual_feasibility_tolerance. "
            "Use Extra solver options for barrier/IPM convergence tolerances."
        )

        self.solver_hint = QLabel()
        self.solver_hint.setWordWrap(True)
        layout.addRow("", self.solver_hint)

        self.content_layout.addWidget(box)

    def _build_extra_options_group(self) -> None:
        box = QGroupBox("Extra solver options (JSON)")
        layout = QVBoxLayout(box)

        self.extra_options_edit = QPlainTextEdit()
        self.extra_options_edit.setMinimumHeight(140)

        layout.addWidget(self.extra_options_edit)
        hint = QLabel(
            "Use native option names for the selected solver. These values "
            "override matching options above. Review them when changing solvers."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.content_layout.addWidget(box)

    def _build_buttons(self) -> None:
        row = QHBoxLayout()

        self.apply_button = QPushButton("Apply")
        self.reset_button = QPushButton("Reset to defaults")

        self.apply_button.clicked.connect(self._on_apply_clicked)
        self.reset_button.clicked.connect(self._on_reset_clicked)

        row.addWidget(self.apply_button)
        row.addWidget(self.reset_button)
        row.addStretch()

        self.content_layout.addLayout(row)

    def _spin_optional_int(self, spin: QSpinBox, auto_values: set[int]) -> int | None:
        return None if spin.value() in auto_values else spin.value()

    def _update_solver_controls(self) -> None:
        is_highs = self.solver_combo.currentText() == "highs"
        for spin, maximum in (
            (self.method_spin, 2 if is_highs else 4),
            (self.presolve_spin, 1 if is_highs else 2),
        ):
            if spin.value() > maximum:
                spin.setValue(-1)
            spin.setMaximum(maximum)
        methods = (
            "Method: Auto, 0 = primal simplex, 1 = dual simplex, 2 = interior point."
        )
        if not is_highs:
            methods += " Gurobi: 3 = concurrent, 4 = deterministic concurrent."
        self.method_spin.setToolTip(methods)
        self.crossover_spin.setToolTip("Auto, 0 = off, 1 = on.")
        presolve = "Presolve: Auto, 0 = off, 1 = on."
        if not is_highs:
            presolve = "Presolve: Auto, 0 = off, 1 = conservative, 2 = aggressive."
        self.presolve_spin.setToolTip(presolve)
        self.solver_hint.setText(
            methods + " " + presolve + " Crossover: Auto, 0 = off, 1 = on. "
            "Auto/None/Default leaves the solver default unchanged."
            + (
                " For mixed-integer or quadratic HiGHS models, leave Method on Auto."
                if is_highs
                else ""
            )
        )
        self.extra_options_edit.setPlaceholderText(
            '{\n  "ipm_optimality_tolerance": 1e-8\n}'
            if is_highs
            else '{\n  "BarConvTol": 1e-8\n}'
        )

    def _spin_optional_float(
        self,
        spin: QDoubleSpinBox,
        unset_value: float = 0.0,
    ) -> float | None:
        return None if spin.value() == unset_value else spin.value()

    def collect_settings(self) -> SolverSettings:
        extra_text = self.extra_options_edit.toPlainText().strip()
        extra_options: dict[str, object] = {}

        if extra_text:
            extra_options = json.loads(extra_text)

        settings = SolverSettings(
            solver_name=self.solver_combo.currentText(),
            assign_all_duals=self.assign_duals_checkbox.isChecked(),
            transmission_losses=self.transmission_losses_checkbox.isChecked(),
            linearized_unit_commitment=self.linearized_uc_checkbox.isChecked(),
            method=self._spin_optional_int(self.method_spin, {-1}),
            crossover=self._spin_optional_int(self.crossover_spin, {-1}),
            presolve=self._spin_optional_int(self.presolve_spin, {-1}),
            threads=self._spin_optional_int(self.threads_spin, {0}),
            time_limit=self._spin_optional_float(self.time_limit_spin),
            mip_gap=self._spin_optional_float(self.mip_gap_spin, -1.0),
            feasibility_tol=self._spin_optional_float(self.feasibility_tol_spin),
            optimality_tol=self._spin_optional_float(self.optimality_tol_spin),
            extra_solver_options=extra_options,
        )
        settings.validate()
        return settings

    def load_settings(self, settings: SolverSettings) -> None:
        self._settings = deepcopy(settings)

        self.solver_combo.setCurrentText(settings.solver_name)
        self._update_solver_controls()
        self.assign_duals_checkbox.setChecked(settings.assign_all_duals)
        self.transmission_losses_checkbox.setChecked(settings.transmission_losses)
        self.linearized_uc_checkbox.setChecked(settings.linearized_unit_commitment)

        self.method_spin.setValue(
            settings.method if settings.method is not None else -1
        )
        self.crossover_spin.setValue(
            settings.crossover if settings.crossover is not None else -1
        )
        self.presolve_spin.setValue(
            settings.presolve if settings.presolve is not None else -1
        )
        self.threads_spin.setValue(
            settings.threads if settings.threads is not None else 0
        )
        self.time_limit_spin.setValue(
            settings.time_limit if settings.time_limit is not None else 0.0
        )
        self.mip_gap_spin.setValue(
            settings.mip_gap if settings.mip_gap is not None else -1.0
        )
        self.feasibility_tol_spin.setValue(
            settings.feasibility_tol if settings.feasibility_tol is not None else 0.0
        )
        self.optimality_tol_spin.setValue(
            settings.optimality_tol if settings.optimality_tol is not None else 0.0
        )

        if settings.extra_solver_options:
            self.extra_options_edit.setPlainText(
                json.dumps(settings.extra_solver_options, indent=2)
            )
        else:
            self.extra_options_edit.clear()

    def _on_apply_clicked(self) -> None:
        try:
            self._settings = self.collect_settings()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid solver settings", str(exc))
            return

        self.settings_changed.emit(self._settings)
        QMessageBox.information(self, "Solver settings", "Solver settings applied.")

    def _on_reset_clicked(self) -> None:
        self.load_settings(SolverSettings())
