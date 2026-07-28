from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ScenarioBuilderPage(QWidget):
    """
    UI for creating a new PyPSA scenario.

    At this stage the page only collects the user input.
    Later it will emit the configuration so that MainWindow
    (or a ScenarioBuilder service) can construct a pypsa.Network.
    """

    scenario_requested = Signal(dict)

    AVAILABLE_COUNTRIES = (
        ("DE", "Germany"),
        ("DK", "Denmark"),
        ("NL", "Netherlands"),
        ("BE", "Belgium"),
        ("FR", "France"),
        ("ES", "Spain"),
        ("PL", "Poland"),
        ("NO", "Norway"),
    )

    AVAILABLE_SCENARIOS = (
        "Reference",
        "Cheap batteries",
        "High CO₂ price",
        "High demand",
        "No interconnection",
    )

    MIN_COUNTRIES = 2
    MAX_COUNTRIES = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._build_ui()
        self._connect_signals()
        self._update_summary()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Scenario Builder")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        description = QLabel(
            "Create a new PyPSA scenario by selecting a small set of "
            "countries and a predefined scenario."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        # ----------------------------------------------------------
        # Scenario settings
        # ----------------------------------------------------------

        settings_box = QGroupBox("Scenario")
        settings_layout = QFormLayout(settings_box)

        self.name_edit = QLineEdit("New Scenario")
        settings_layout.addRow("Network name:", self.name_edit)

        self.scenario_combo = QComboBox()
        self.scenario_combo.addItems(self.AVAILABLE_SCENARIOS)
        settings_layout.addRow("Scenario:", self.scenario_combo)

        layout.addWidget(settings_box)

        # ----------------------------------------------------------
        # Countries
        # ----------------------------------------------------------

        countries_box = QGroupBox("Countries")
        countries_layout = QVBoxLayout(countries_box)

        countries_layout.addWidget(
            QLabel(
                f"Select between {self.MIN_COUNTRIES} "
                f"and {self.MAX_COUNTRIES} countries."
            )
        )

        self.country_list = QListWidget()

        for code, name in self.AVAILABLE_COUNTRIES:
            item = QListWidgetItem(f"{name} ({code})")
            item.setData(Qt.ItemDataRole.UserRole, code)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.country_list.addItem(item)

        countries_layout.addWidget(self.country_list)
        layout.addWidget(countries_box)

        # ----------------------------------------------------------
        # Summary
        # ----------------------------------------------------------

        summary_box = QGroupBox("Summary")
        summary_layout = QVBoxLayout(summary_box)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)

        summary_layout.addWidget(self.summary_label)

        layout.addWidget(summary_box)

        # ----------------------------------------------------------
        # Buttons
        # ----------------------------------------------------------

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.create_button = QPushButton("Create Network")
        self.create_button.setEnabled(False)

        button_layout.addWidget(self.create_button)

        layout.addLayout(button_layout)
        layout.addStretch()

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self.country_list.itemChanged.connect(
            self._on_country_selection_changed
        )

        self.name_edit.textChanged.connect(self._update_summary)
        self.scenario_combo.currentTextChanged.connect(
            self._update_summary
        )

        self.create_button.clicked.connect(
            self._emit_scenario_requested
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _selected_items(self) -> list[QListWidgetItem]:
        items = []

        for row in range(self.country_list.count()):
            item = self.country_list.item(row)

            if item.checkState() == Qt.CheckState.Checked:
                items.append(item)

        return items

    def selected_country_codes(self) -> list[str]:
        return [
            str(item.data(Qt.ItemDataRole.UserRole))
            for item in self._selected_items()
        ]

    def scenario_definition(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "countries": self.selected_country_codes(),
            "scenario": self.scenario_combo.currentText(),
        }

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_country_selection_changed(
        self,
        changed_item: QListWidgetItem,
    ) -> None:
        selected = self._selected_items()

        if len(selected) > self.MAX_COUNTRIES:
            self.country_list.blockSignals(True)
            changed_item.setCheckState(Qt.CheckState.Unchecked)
            self.country_list.blockSignals(False)

        self._update_summary()

    def _update_summary(self, *_args) -> None:
        definition = self.scenario_definition()

        countries = definition["countries"]

        self.summary_label.setText(
            f"Name: {definition['name']}\n"
            f"Countries: {', '.join(countries) if countries else 'None'}\n"
            f"Scenario: {definition['scenario']}"
        )

        valid = (
            self.MIN_COUNTRIES
            <= len(countries)
            <= self.MAX_COUNTRIES
            and bool(definition["name"])
        )

        self.create_button.setEnabled(valid)

    def _emit_scenario_requested(self) -> None:
        self.scenario_requested.emit(
            self.scenario_definition()
        )