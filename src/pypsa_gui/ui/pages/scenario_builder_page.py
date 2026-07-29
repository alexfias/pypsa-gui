from __future__ import annotations

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
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pypsa_gui.models.scenario_definition import (
    CO2Policy,
    ScenarioDefinition,
    TechnologySettings,
)


class ScenarioBuilderPage(QWidget):
    """Collect inputs for creating a small PyPSA teaching scenario."""

    scenario_requested = Signal(object)

    AVAILABLE_COUNTRIES = (
        ("DE", "Germany", "🇩🇪"),
        ("DK", "Denmark", "🇩🇰"),
        ("NL", "Netherlands", "🇳🇱"),
        ("BE", "Belgium", "🇧🇪"),
        ("FR", "France", "🇫🇷"),
        ("ES", "Spain", "🇪🇸"),
        ("PL", "Poland", "🇵🇱"),
        ("NO", "Norway", "🇳🇴"),
    )

    SCENARIOS = {
        "Reference": {
            "description": (
                "A balanced baseline scenario with standard technology costs, "
                "electricity demand, and cross-border transmission."
            ),
            "changes": "No preset modifications",
        },
        "Cheap batteries": {
            "description": (
                "Battery investment costs are reduced to explore how inexpensive "
                "short-duration storage changes the optimal electricity mix."
            ),
            "changes": "Battery capital cost reduced by the preset",
        },
        "High CO₂ price": {
            "description": (
                "A high carbon price penalises fossil-fuel generation and "
                "encourages renewable generation, storage, and electricity trade."
            ),
            "changes": "High CO₂ price applied by the preset",
        },
        "High demand": {
            "description": (
                "Electricity demand is increased to represent electrification "
                "of transport, heating, or industry."
            ),
            "changes": "Electricity demand increased by the preset",
        },
        "No interconnection": {
            "description": (
                "Cross-border transmission is removed so that each selected "
                "country must balance its electricity system independently."
            ),
            "changes": "Cross-border interconnectors disabled by the preset",
        },
    }

    TECHNOLOGIES = (
        ("solar", "Solar PV"),
        ("onshore_wind", "Onshore wind"),
        ("offshore_wind", "Offshore wind"),
        ("gas", "Gas generation"),
        ("coal", "Coal and lignite"),
        ("nuclear", "Nuclear"),
        ("hydro", "Hydro"),
        ("battery", "Battery storage"),
        ("hydrogen", "Hydrogen storage"),
    )

    MIN_COUNTRIES = 1
    MAX_COUNTRIES = 3

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.country_buttons: dict[str, QPushButton] = {}

        self.technology_enabled_boxes: dict[str, QCheckBox] = {}
        self.technology_capital_cost_spins: dict[
            str,
            QDoubleSpinBox,
        ] = {}

        self._build_ui()
        self._connect_signals()
        self._update_co2_controls()
        self._update_page()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        outer_layout.addWidget(scroll_area)

        content = QWidget()
        scroll_area.setWidget(content)

        main_layout = QVBoxLayout(content)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        title = QLabel("Scenario Builder")
        title.setStyleSheet(
            """
            QLabel {
                font-size: 22px;
                font-weight: 600;
            }
            """
        )
        main_layout.addWidget(title)

        subtitle = QLabel(
            "Create a small multi-country PyPSA scenario and configure "
            "its demand, climate policy, technologies, and investment costs."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #555555;")
        main_layout.addWidget(subtitle)

        main_layout.addWidget(self._create_general_group())
        main_layout.addWidget(self._create_country_group())
        main_layout.addWidget(self._create_policy_group())
        main_layout.addWidget(self._create_technology_group())
        main_layout.addWidget(self._create_preview_group())

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.create_button = QPushButton("Create Network")
        self.create_button.setMinimumWidth(160)
        self.create_button.setMinimumHeight(38)
        self.create_button.setEnabled(False)

        button_layout.addWidget(self.create_button)
        main_layout.addLayout(button_layout)
        main_layout.addStretch()

    def _create_general_group(self) -> QGroupBox:
        group = QGroupBox("General scenario settings")
        layout = QFormLayout(group)

        layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        self.name_edit = QLineEdit("New Scenario")
        self.name_edit.setPlaceholderText(
            "Enter a name for the network"
        )
        layout.addRow("Network name:", self.name_edit)

        self.scenario_combo = QComboBox()
        self.scenario_combo.addItems(self.SCENARIOS.keys())
        layout.addRow("Preset:", self.scenario_combo)

        self.scenario_description_label = QLabel()
        self.scenario_description_label.setWordWrap(True)
        self.scenario_description_label.setStyleSheet(
            """
            QLabel {
                padding: 8px;
                background-color: palette(alternate-base);
                border-radius: 4px;
            }
            """
        )
        layout.addRow("", self.scenario_description_label)

        self.demand_multiplier_spin = QDoubleSpinBox()
        self.demand_multiplier_spin.setRange(0.10, 5.00)
        self.demand_multiplier_spin.setDecimals(2)
        self.demand_multiplier_spin.setSingleStep(0.05)
        self.demand_multiplier_spin.setValue(1.00)
        self.demand_multiplier_spin.setSuffix(" ×")
        self.demand_multiplier_spin.setToolTip(
            "Multiply all selected-country electricity demand by this value."
        )
        layout.addRow(
            "Demand multiplier:",
            self.demand_multiplier_spin,
        )

        self.interconnection_checkbox = QCheckBox(
            "Allow transmission between selected countries"
        )
        self.interconnection_checkbox.setChecked(True)
        layout.addRow(
            "Interconnection:",
            self.interconnection_checkbox,
        )

        return group

    def _create_country_group(self) -> QGroupBox:
        group = QGroupBox("Countries")
        layout = QVBoxLayout(group)

        self.country_instruction_label = QLabel(
            f"Select between {self.MIN_COUNTRIES} and "
            f"{self.MAX_COUNTRIES} countries."
        )
        layout.addWidget(self.country_instruction_label)

        country_grid = QGridLayout()
        country_grid.setHorizontalSpacing(12)
        country_grid.setVerticalSpacing(8)

        for index, (code, name, flag) in enumerate(
            self.AVAILABLE_COUNTRIES
        ):
            button = QPushButton(
                f"{flag}  {name} ({code})"
            )
            button.setCheckable(True)
            button.setMinimumHeight(38)
            button.setProperty("country_code", code)

            row = index // 2
            column = index % 2

            country_grid.addWidget(
                button,
                row,
                column,
            )

            self.country_buttons[code] = button

        layout.addLayout(country_grid)

        self.country_status_label = QLabel()
        self.country_status_label.setWordWrap(True)
        layout.addWidget(self.country_status_label)

        return group

    def _create_policy_group(self) -> QGroupBox:
        group = QGroupBox("Climate policy")
        layout = QFormLayout(group)

        self.co2_policy_combo = QComboBox()
        self.co2_policy_combo.addItem(
            "No additional CO₂ policy",
            "none",
        )
        self.co2_policy_combo.addItem(
            "CO₂ price",
            "price",
        )
        self.co2_policy_combo.addItem(
            "Emissions reduction target",
            "relative_cap",
        )
        self.co2_policy_combo.addItem(
            "Advanced: Absolute CO₂ cap",
            "absolute_cap",
        )
        layout.addRow(
            "CO₂ policy:",
            self.co2_policy_combo,
        )

        self.co2_value_spin = QDoubleSpinBox()
        self.co2_value_spin.setRange(0.0, 1_000_000.0)
        self.co2_value_spin.setDecimals(2)
        self.co2_value_spin.setSingleStep(10.0)
        self.co2_value_spin.setValue(100.0)
        layout.addRow(
            "Policy value:",
            self.co2_value_spin,
        )

        self.co2_explanation_label = QLabel()
        self.co2_explanation_label.setWordWrap(True)
        self.co2_explanation_label.setStyleSheet(
            "color: #555555;"
        )
        layout.addRow(
            "",
            self.co2_explanation_label,
        )

        return group

    def _create_technology_group(self) -> QGroupBox:
        group = QGroupBox("Technologies")
        layout = QVBoxLayout(group)

        explanation = QLabel(
            "Choose which technologies are available and how their "
            "investment costs change. Existing capacity-expansion settings "
            "from the source network are preserved."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)

        grid.addWidget(
            QLabel("<b>Technology</b>"),
            0,
            0,
        )
        grid.addWidget(
            QLabel("<b>Enabled</b>"),
            0,
            1,
            Qt.AlignmentFlag.AlignCenter,
        )
        grid.addWidget(
            QLabel("<b>Capital cost</b>"),
            0,
            2,
            Qt.AlignmentFlag.AlignCenter,
        )

        for row, (key, label) in enumerate(
            self.TECHNOLOGIES,
            start=1,
        ):
            technology_label = QLabel(label)

            enabled_box = QCheckBox()
            enabled_box.setChecked(True)

            capital_cost_spin = QDoubleSpinBox()
            capital_cost_spin.setRange(0.0, 10.0)
            capital_cost_spin.setDecimals(2)
            capital_cost_spin.setSingleStep(0.10)
            capital_cost_spin.setValue(1.00)
            capital_cost_spin.setSuffix(" ×")
            capital_cost_spin.setToolTip(
                "Multiplier applied to the technology's capital cost."
            )

            grid.addWidget(
                technology_label,
                row,
                0,
            )
            grid.addWidget(
                enabled_box,
                row,
                1,
                Qt.AlignmentFlag.AlignCenter,
            )
            grid.addWidget(
                capital_cost_spin,
                row,
                2,
            )

            self.technology_enabled_boxes[key] = enabled_box
            self.technology_capital_cost_spins[
                key
            ] = capital_cost_spin

        grid.setColumnStretch(0, 1)
        layout.addLayout(grid)

        return group

    def _create_preview_group(self) -> QGroupBox:
        group = QGroupBox("Scenario preview")
        layout = QGridLayout(group)

        headings = (
            "Network name",
            "Countries",
            "Preset",
            "Demand",
            "CO₂ policy",
            "Interconnection",
            "Enabled technologies",
            "Disabled technologies",
            "Modified capital costs",
        )

        self.preview_name_label = QLabel()
        self.preview_countries_label = QLabel()
        self.preview_scenario_label = QLabel()
        self.preview_demand_label = QLabel()
        self.preview_co2_label = QLabel()
        self.preview_interconnection_label = QLabel()
        self.preview_enabled_technologies_label = QLabel()
        self.preview_disabled_technologies_label = QLabel()
        self.preview_costs_label = QLabel()

        values = (
            self.preview_name_label,
            self.preview_countries_label,
            self.preview_scenario_label,
            self.preview_demand_label,
            self.preview_co2_label,
            self.preview_interconnection_label,
            self.preview_enabled_technologies_label,
            self.preview_disabled_technologies_label,
            self.preview_costs_label,
        )

        for row, (heading, value_label) in enumerate(
            zip(headings, values)
        ):
            heading_label = QLabel(
                f"<b>{heading}</b>"
            )

            heading_label.setAlignment(
                Qt.AlignmentFlag.AlignTop
            )
            value_label.setWordWrap(True)

            layout.addWidget(
                heading_label,
                row,
                0,
                Qt.AlignmentFlag.AlignTop,
            )
            layout.addWidget(
                value_label,
                row,
                1,
            )

        layout.setColumnStretch(1, 1)

        return group

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self.name_edit.textChanged.connect(
            self._update_page
        )
        self.scenario_combo.currentTextChanged.connect(
            self._update_page
        )
        self.demand_multiplier_spin.valueChanged.connect(
            self._update_page
        )
        self.interconnection_checkbox.toggled.connect(
            self._update_page
        )

        self.co2_policy_combo.currentIndexChanged.connect(
            self._on_co2_policy_changed
        )
        self.co2_value_spin.valueChanged.connect(
            self._update_page
        )

        self.create_button.clicked.connect(
            self._emit_scenario_requested
        )

        for button in self.country_buttons.values():
            button.toggled.connect(
                self._on_country_selection_changed
            )

        for key in self.technology_enabled_boxes:
            self.technology_enabled_boxes[
                key
            ].toggled.connect(
                lambda checked, technology_key=key:
                self._on_technology_enabled_changed(
                    technology_key,
                    checked,
                )
            )

            self.technology_capital_cost_spins[
                key
            ].valueChanged.connect(
                self._update_page
            )

    # ------------------------------------------------------------------
    # Scenario data
    # ------------------------------------------------------------------

    def selected_country_codes(self) -> list[str]:
        return [
            code
            for code, button in self.country_buttons.items()
            if button.isChecked()
        ]

    def selected_country_names(self) -> list[str]:
        names_by_code = {
            code: name
            for code, name, _flag in self.AVAILABLE_COUNTRIES
        }

        return [
            names_by_code[code]
            for code in self.selected_country_codes()
            if code in names_by_code
        ]

    def technology_settings(
        self,
    ) -> dict[str, TechnologySettings]:
        settings: dict[str, TechnologySettings] = {}

        for key, _label in self.TECHNOLOGIES:
            settings[key] = TechnologySettings(
                enabled=self.technology_enabled_boxes[
                    key
                ].isChecked(),
                capital_cost_multiplier=(
                    self.technology_capital_cost_spins[
                        key
                    ].value()
                ),
                marginal_cost_multiplier=1.0,
            )

        return settings

    def co2_policy(self) -> CO2Policy:
        mode = self.co2_policy_combo.currentData()

        if mode == "none":
            return CO2Policy(
                mode="none",
                value=None,
            )

        return CO2Policy(
            mode=mode,
            value=self.co2_value_spin.value(),
        )

    def scenario_definition(
        self,
    ) -> ScenarioDefinition:
        return ScenarioDefinition(
            name=self.name_edit.text().strip(),
            countries=tuple(
                self.selected_country_codes()
            ),
            preset=self.scenario_combo.currentText(),
            co2_policy=self.co2_policy(),
            technologies=self.technology_settings(),
            demand_multiplier=(
                self.demand_multiplier_spin.value()
            ),
            allow_interconnection=(
                self.interconnection_checkbox.isChecked()
            ),
        )

    # ------------------------------------------------------------------
    # Page updates
    # ------------------------------------------------------------------

    def _on_country_selection_changed(
        self,
        _checked: bool,
    ) -> None:
        selected_codes = self.selected_country_codes()

        if len(selected_codes) >= self.MAX_COUNTRIES:
            for button in self.country_buttons.values():
                if not button.isChecked():
                    button.setEnabled(False)
        else:
            for button in self.country_buttons.values():
                button.setEnabled(True)

        self._update_page()

    def _on_co2_policy_changed(
        self,
        _index: int,
    ) -> None:
        self._update_co2_controls()
        self._update_page()

    def _update_co2_controls(self) -> None:
        mode = self.co2_policy_combo.currentData()

        self.co2_value_spin.setEnabled(
            mode != "none"
        )

        if mode == "none":
            self.co2_value_spin.setRange(
                0.0,
                1_000_000.0,
            )
            self.co2_value_spin.setDecimals(2)
            self.co2_value_spin.setSingleStep(10.0)
            self.co2_value_spin.setSuffix("")
            self.co2_explanation_label.setText(
                "No additional explicit CO₂ policy is applied. "
                "A selected preset may still modify CO₂ assumptions."
            )
            return

        if mode == "price":
            self.co2_value_spin.setRange(
                0.0,
                1_000.0,
            )
            self.co2_value_spin.setDecimals(1)
            self.co2_value_spin.setSingleStep(10.0)
            self.co2_value_spin.setSuffix(" €/tCO₂")
            self.co2_explanation_label.setText(
                "The value is added as a price for each tonne of CO₂ emitted."
            )
            return

        if mode == "relative_cap":
            self.co2_value_spin.setRange(
                0.0,
                100.0,
            )
            self.co2_value_spin.setDecimals(0)
            self.co2_value_spin.setSingleStep(5.0)
            self.co2_value_spin.setSuffix(" %")

            if self.co2_value_spin.value() > 100.0:
                self.co2_value_spin.setValue(70.0)

            self.co2_explanation_label.setText(
                "The reduction target is converted into an absolute cap "
                "using annual electricity demand and an assumed reference "
                "intensity of 0.35 tCO₂/MWh."
            )
            return

        if mode == "absolute_cap":
            self.co2_value_spin.setRange(
                0.0,
                10_000.0,
            )
            self.co2_value_spin.setDecimals(2)
            self.co2_value_spin.setSingleStep(1.0)
            self.co2_value_spin.setSuffix(" MtCO₂")
            self.co2_explanation_label.setText(
                "The value specifies the absolute annual CO₂ emissions cap "
                "in million tonnes."
            )

    def _on_technology_enabled_changed(
        self,
        technology_key: str,
        enabled: bool,
    ) -> None:
        self.technology_capital_cost_spins[
            technology_key
        ].setEnabled(enabled)

        self._update_page()

    def _update_page(
        self,
        *_args: object,
    ) -> None:
        definition = self.scenario_definition()

        scenario = self.SCENARIOS[
            definition.preset
        ]

        self.scenario_description_label.setText(
            scenario["description"]
        )

        self.preview_name_label.setText(
            definition.name
            if definition.name
            else "Not specified"
        )

        selected_codes = list(
            definition.countries
        )
        names_by_code = {
            code: name
            for code, name, _flag in self.AVAILABLE_COUNTRIES
        }

        if selected_codes:
            country_text = ", ".join(
                f"{names_by_code.get(code, code)} ({code})"
                for code in selected_codes
            )
        else:
            country_text = "None selected"

        self.preview_countries_label.setText(
            country_text
        )
        self.preview_scenario_label.setText(
            definition.preset
        )
        self.preview_demand_label.setText(
            f"{definition.demand_multiplier:.2f} ×"
        )
        self.preview_interconnection_label.setText(
            "Enabled"
            if definition.allow_interconnection
            else "Disabled"
        )

        if definition.co2_policy.mode == "none":
            co2_text = "No additional CO₂ policy"

        elif definition.co2_policy.mode == "price":
            co2_text = (
                f"CO₂ price: "
                f"{definition.co2_policy.value:.1f} €/tCO₂"
            )

        elif definition.co2_policy.mode == "relative_cap":
            co2_text = (
                f"Emissions reduction target: "
                f"{definition.co2_policy.value:.0f}% "
                "(demand-based reference)"
            )

        else:
            co2_text = (
                f"Absolute CO₂ cap: "
                f"{definition.co2_policy.value:.2f} MtCO₂"
            )

        self.preview_co2_label.setText(
            co2_text
        )

        labels_by_key = dict(
            self.TECHNOLOGIES
        )

        enabled_labels = [
            labels_by_key[key]
            for key, settings
            in definition.technologies.items()
            if settings.enabled
        ]

        disabled_labels = [
            labels_by_key[key]
            for key, settings
            in definition.technologies.items()
            if not settings.enabled
        ]

        self.preview_enabled_technologies_label.setText(
            ", ".join(enabled_labels)
            if enabled_labels
            else "None"
        )
        self.preview_disabled_technologies_label.setText(
            ", ".join(disabled_labels)
            if disabled_labels
            else "None"
        )

        modified_costs = [
            (
                f"{labels_by_key[key]} "
                f"{settings.capital_cost_multiplier:.2f} ×"
            )
            for key, settings
            in definition.technologies.items()
            if (
                settings.enabled
                and abs(
                    settings.capital_cost_multiplier - 1.0
                ) > 1e-9
            )
        ]

        self.preview_costs_label.setText(
            ", ".join(modified_costs)
            if modified_costs
            else "No additional cost multipliers"
        )

        number_selected = len(
            selected_codes
        )

        if number_selected < self.MIN_COUNTRIES:
            remaining = (
                self.MIN_COUNTRIES
                - number_selected
            )

            self.country_status_label.setText(
                f"Select {remaining} more "
                f"{'country' if remaining == 1 else 'countries'}."
            )
            self.country_status_label.setStyleSheet(
                "color: #8a5a00;"
            )
        else:
            self.country_status_label.setText(
                f"{number_selected} countries selected."
            )
            self.country_status_label.setStyleSheet(
                "color: #287a28;"
            )

        valid_name = bool(
            definition.name
        )
        valid_country_count = (
            self.MIN_COUNTRIES
            <= number_selected
            <= self.MAX_COUNTRIES
        )
        at_least_one_technology = any(
            settings.enabled
            for settings
            in definition.technologies.values()
        )

        self.create_button.setEnabled(
            valid_name
            and valid_country_count
            and at_least_one_technology
        )

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def _emit_scenario_requested(self) -> None:
        self.scenario_requested.emit(
            self.scenario_definition()
        )