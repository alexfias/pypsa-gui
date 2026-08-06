from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pypsa_gui.workflows.models import WorkflowRecord
from pypsa_gui.workflows.serialization import (
    workflow_id,
    workflow_to_json,
)


class WorkflowPage(QWidget):
    """Display and export the scientific workflow of the active session."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._workflow: WorkflowRecord | None = None

        self.title_label = QLabel("Scientific Workflow")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold;")

        self.summary_label = QLabel("No active workflow.")
        self.summary_label.setWordWrap(True)

        self.id_label = QLabel("Workflow ID: —")
        self.id_label.setTextInteractionFlags(
            self.id_label.textInteractionFlags()
        )
        self.id_label.setWordWrap(True)

        self.json_view = QPlainTextEdit()
        self.json_view.setReadOnly(True)
        self.json_view.setPlaceholderText(
            "The workflow of the active network will appear here."
        )

        self.copy_id_button = QPushButton("Copy ID")
        self.copy_id_button.clicked.connect(self._copy_id)

        self.export_button = QPushButton("Export JSON...")
        self.export_button.clicked.connect(self._export_json)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.copy_id_button)
        button_layout.addWidget(self.export_button)
        button_layout.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(self.title_label)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.id_label)
        layout.addLayout(button_layout)
        layout.addWidget(self.json_view, 1)

        self._refresh()

    def set_workflow(
        self,
        workflow: WorkflowRecord | None,
    ) -> None:
        self._workflow = workflow
        self._refresh()

    def _refresh(self) -> None:
        workflow = self._workflow

        if workflow is None:
            self.summary_label.setText("No active workflow.")
            self.id_label.setText("Workflow ID: —")
            self.json_view.clear()
            self.copy_id_button.setEnabled(False)
            self.export_button.setEnabled(False)
            return

        step_count = len(workflow.steps)
        step_word = "step" if step_count == 1 else "steps"

        self.summary_label.setText(
            f"Framework: {workflow.framework} | "
            f"Interface: {workflow.interface} | "
            f"{step_count} recorded {step_word}"
        )
        self.id_label.setText(
            f"Workflow ID: {workflow_id(workflow)}"
        )
        self.json_view.setPlainText(
            workflow_to_json(workflow)
        )
        self.copy_id_button.setEnabled(True)
        self.export_button.setEnabled(True)

    def _copy_id(self) -> None:
        if self._workflow is None:
            return

        QApplication.clipboard().setText(
            workflow_id(self._workflow)
        )

    def _export_json(self) -> None:
        if self._workflow is None:
            return

        default_name = (
            f"workflow-{workflow_id(self._workflow)[:12]}.json"
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Scientific Workflow",
            str(Path.home() / default_name),
            "JSON Files (*.json)",
        )

        if not file_path:
            return

        if not file_path.lower().endswith(".json"):
            file_path += ".json"

        try:
            Path(file_path).write_text(
                workflow_to_json(self._workflow),
                encoding="utf-8",
            )
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Workflow Export Failed",
                "Could not export the workflow:\n\n"
                f"{exc}",
            )
