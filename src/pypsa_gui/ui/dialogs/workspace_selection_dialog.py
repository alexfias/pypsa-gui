# src/pypsa_gui/ui/dialogs/workspace_selection_dialog.py

from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from pypsa_gui.models.session_view import WORKSPACE_PRESETS


SECTION_LABELS: dict[str, str] = {
    "overview": "Overview",
    "components": "Components",
    "analysis": "Analysis",
    "plots": "Plots",
    "run": "Run",
}

SECTION_ORDER = ["overview", "components", "analysis", "plots", "run"]


class WorkspaceSelectionDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Choose Workspace")
        self.setModal(True)
        self.resize(360, 320)

        self.full_radio = QRadioButton("Full")
        self.lightweight_radio = QRadioButton("Lightweight")
        self.analysis_radio = QRadioButton("Analysis")
        self.custom_radio = QRadioButton("Custom")

        self.full_radio.setChecked(True)

        self.workspace_buttons = QButtonGroup(self)
        self.workspace_buttons.addButton(self.full_radio)
        self.workspace_buttons.addButton(self.lightweight_radio)
        self.workspace_buttons.addButton(self.analysis_radio)
        self.workspace_buttons.addButton(self.custom_radio)

        self.custom_checkboxes: dict[str, QCheckBox] = {}
        custom_group = QGroupBox("Custom Sections")
        custom_layout = QVBoxLayout(custom_group)

        for section_key in SECTION_ORDER:
            checkbox = QCheckBox(SECTION_LABELS[section_key])
            checkbox.setChecked(section_key in WORKSPACE_PRESETS["full"])
            checkbox.setEnabled(False)
            self.custom_checkboxes[section_key] = checkbox
            custom_layout.addWidget(checkbox)

        self.workspace_buttons.buttonToggled.connect(self._on_workspace_changed)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select which main sections should be active:"))
        layout.addWidget(self.full_radio)
        layout.addWidget(self.lightweight_radio)
        layout.addWidget(self.analysis_radio)
        layout.addWidget(self.custom_radio)
        layout.addWidget(custom_group)
        layout.addStretch()
        layout.addWidget(button_box)

    def _on_workspace_changed(self) -> None:
        is_custom = self.custom_radio.isChecked()
        for checkbox in self.custom_checkboxes.values():
            checkbox.setEnabled(is_custom)

    def selected_workspace_name(self) -> str:
        if self.full_radio.isChecked():
            return "full"
        if self.lightweight_radio.isChecked():
            return "lightweight"
        if self.analysis_radio.isChecked():
            return "analysis"
        return "custom"

    def selected_enabled_sections(self) -> set[str]:
        workspace_name = self.selected_workspace_name()

        if workspace_name != "custom":
            return set(WORKSPACE_PRESETS[workspace_name])

        enabled_sections = {
            section_key
            for section_key, checkbox in self.custom_checkboxes.items()
            if checkbox.isChecked()
        }

        return enabled_sections or {"overview"}