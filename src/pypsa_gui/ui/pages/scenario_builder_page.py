from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ScenarioBuilderPage(QWidget):
    """Collect inputs for creating a small PyPSA teaching scenario."""

    scenario_requested = Signal(dict)

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
            "technologies": (
                "Onshore wind, offshore wind, solar PV, gas generation, "
                "battery storage, and interconnectors"
            ),
            "changes": "No additional scenario modifications",
        },
        "Cheap batteries": {
            "description": (
                "Battery investment costs are reduced to explore how inexpensive "
                "short-duration storage changes the optimal electricity mix."
            ),
            "technologies": (
                "Onshore wind, offshore wind, solar PV, gas generation, "
                "low-cost battery storage, and interconnectors"
            ),
            "changes": "Battery capital cost reduced",
        },
        "High CO₂ price": {
            "description": (
                "A high carbon price penalises fossil-fuel generation and "
                "encourages renewable generation, storage, and electricity trade."
            ),
            "technologies": (
                "Onshore wind, offshore wind, solar PV, gas generation, "
                "battery storage, and interconnectors"
            ),
            "changes": "High marginal cost for CO₂-emitting generation",
        },
        "High demand": {
            "description": (
                "Electricity demand is increased to represent electrification "
                "of transport, heating, or industry."
            ),
            "technologies": (
                "Onshore wind, offshore wind, solar PV, gas generation, "
                "battery storage, and interconnectors"
            ),
            "changes": "Electricity demand increased",
        },
        "No interconnection": {
            "description": (
                "Cross-border transmission is removed so that each selected "
                "country must balance its electricity system independently."
            ),
            "technologies": (
                "Onshore wind, offshore wind, solar PV, gas generation, "
                "and battery storage"
            ),
            "changes": "Cross-border interconnectors disabled",
        },
    }

    MIN_COUNTRIES = 1
    MAX_COUNTRIES = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.country_buttons: dict[str, QPushButton] = {}

        self._build_ui()
        self._connect_signals()
        self._update_page()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
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
            "Create a small multi-country PyPSA scenario for optimisation "
            "and comparison."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #555555;")
        main_layout.addWidget(subtitle)

        main_layout.addWidget(self._create_scenario_group())
        main_layout.addWidget(self._create_country_group())
        main_layout.addWidget(self._create_preview_group())

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.create_button = QPushButton("Create Network")
        self.create_button.setMinimumWidth(150)
        self.create_button.setEnabled(False)
        button_layout.addWidget(self.create_button)

        main_layout.addLayout(button_layout)
        main_layout.addStretch()

    def _create_scenario_group(self) -> QGroupBox:
        group = QGroupBox("Scenario")
        layout = QFormLayout(group)
        layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        self.name_edit = QLineEdit("New Scenario")
        self.name_edit.setPlaceholderText("Enter a name for the network")
        layout.addRow("Network name:", self.name_edit)

        self.scenario_combo = QComboBox()
        self.scenario_combo.addItems(self.SCENARIOS.keys())
        layout.addRow("Scenario:", self.scenario_combo)

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
            button = QPushButton(f"{flag}  {name} ({code})")
            button.setCheckable(True)
            button.setMinimumHeight(38)
            button.setProperty("country_code", code)

            row = index // 2
            column = index % 2
            country_grid.addWidget(button, row, column)

            self.country_buttons[code] = button

        layout.addLayout(country_grid)

        self.country_status_label = QLabel()
        self.country_status_label.setWordWrap(True)
        layout.addWidget(self.country_status_label)

        return group

    def _create_preview_group(self) -> QGroupBox:
        group = QGroupBox("Scenario Preview")
        layout = QGridLayout(group)

        name_heading = QLabel("<b>Network name</b>")
        countries_heading = QLabel("<b>Countries</b>")
        scenario_heading = QLabel("<b>Scenario</b>")
        technologies_heading = QLabel("<b>Technologies</b>")
        changes_heading = QLabel("<b>Scenario changes</b>")

        self.preview_name_label = QLabel()
        self.preview_countries_label = QLabel()
        self.preview_scenario_label = QLabel()
        self.preview_technologies_label = QLabel()
        self.preview_changes_label = QLabel()

        self.preview_countries_label.setWordWrap(True)
        self.preview_technologies_label.setWordWrap(True)
        self.preview_changes_label.setWordWrap(True)

        layout.addWidget(name_heading, 0, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.preview_name_label, 0, 1)

        layout.addWidget(
            countries_heading,
            1,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        layout.addWidget(self.preview_countries_label, 1, 1)

        layout.addWidget(
            scenario_heading,
            2,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        layout.addWidget(self.preview_scenario_label, 2, 1)

        layout.addWidget(
            technologies_heading,
            3,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        layout.addWidget(self.preview_technologies_label, 3, 1)

        layout.addWidget(
            changes_heading,
            4,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        layout.addWidget(self.preview_changes_label, 4, 1)

        layout.setColumnStretch(1, 1)

        return group

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self.name_edit.textChanged.connect(self._update_page)
        self.scenario_combo.currentTextChanged.connect(self._update_page)
        self.create_button.clicked.connect(
            self._emit_scenario_requested
        )

        for button in self.country_buttons.values():
            button.toggled.connect(
                self._on_country_selection_changed
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
        selected_codes = set(self.selected_country_codes())

        return [
            name
            for code, name, _flag in self.AVAILABLE_COUNTRIES
            if code in selected_codes
        ]

    def scenario_definition(self) -> dict[str, object]:
        return {
            "name": self.name_edit.text().strip(),
            "countries": self.selected_country_codes(),
            "scenario": self.scenario_combo.currentText(),
        }

    # ------------------------------------------------------------------
    # Page updates
    # ------------------------------------------------------------------

    def _on_country_selection_changed(self, checked: bool) -> None:
        selected_codes = self.selected_country_codes()

        if len(selected_codes) >= self.MAX_COUNTRIES:
            for code, button in self.country_buttons.items():
                if not button.isChecked():
                    button.setEnabled(False)
        else:
            for button in self.country_buttons.values():
                button.setEnabled(True)

        self._update_page()

    def _update_page(self, *_args: object) -> None:
        definition = self.scenario_definition()

        name = str(definition["name"])
        selected_codes = list(definition["countries"])
        selected_names = self.selected_country_names()
        scenario_name = str(definition["scenario"])

        scenario = self.SCENARIOS[scenario_name]

        self.scenario_description_label.setText(
            scenario["description"]
        )

        self.preview_name_label.setText(
            name if name else "Not specified"
        )

        if selected_names:
            country_text = ", ".join(
                f"{name} ({code})"
                for name, code in zip(selected_names, selected_codes)
            )
        else:
            country_text = "None selected"

        self.preview_countries_label.setText(country_text)
        self.preview_scenario_label.setText(scenario_name)
        self.preview_technologies_label.setText(
            scenario["technologies"]
        )
        self.preview_changes_label.setText(
            scenario["changes"]
        )

        number_selected = len(selected_codes)

        if number_selected < self.MIN_COUNTRIES:
            remaining = self.MIN_COUNTRIES - number_selected
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

        valid_name = bool(name)
        valid_country_count = (
            self.MIN_COUNTRIES
            <= number_selected
            <= self.MAX_COUNTRIES
        )

        self.create_button.setEnabled(
            valid_name and valid_country_count
        )

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def _emit_scenario_requested(self) -> None:
        self.scenario_requested.emit(
            self.scenario_definition()
        )