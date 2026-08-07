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
from pypsa_gui.workflows.semantic import (
    build_semantic_signature,
)
from pypsa_gui.workflows.serialization import (
    workflow_id,
    workflow_to_json,
)


class WorkflowPage(QWidget):
    """Display and export the scientific workflow of the active session."""

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._workflow: WorkflowRecord | None = None

        self.title_label = QLabel(
            "Scientific Workflow"
        )
        self.title_label.setStyleSheet(
            "font-size: 18px; font-weight: bold;"
        )

        self.summary_label = QLabel(
            "No active workflow."
        )
        self.summary_label.setWordWrap(True)

        # ------------------------------------------------------------------
        # Searchable ID
        # ------------------------------------------------------------------

        self.search_id_label = QLabel(
            "Search ID: —"
        )
        self.search_id_label.setWordWrap(True)

        # ------------------------------------------------------------------
        # Canonical ID
        # ------------------------------------------------------------------

        self.canonical_id_label = QLabel(
            "Canonical ID: —"
        )
        self.canonical_id_label.setWordWrap(True)

        # ------------------------------------------------------------------
        # Buttons
        # ------------------------------------------------------------------

        self.copy_search_id_button = QPushButton(
            "Copy Search ID"
        )
        self.copy_search_id_button.clicked.connect(
            self._copy_search_id
        )

        self.copy_canonical_id_button = QPushButton(
            "Copy Canonical ID"
        )
        self.copy_canonical_id_button.clicked.connect(
            self._copy_canonical_id
        )

        self.export_button = QPushButton(
            "Export JSON..."
        )
        self.export_button.clicked.connect(
            self._export_json
        )

        button_layout = QHBoxLayout()

        button_layout.addWidget(
            self.copy_search_id_button
        )
        button_layout.addWidget(
            self.copy_canonical_id_button
        )
        button_layout.addWidget(
            self.export_button
        )

        button_layout.addStretch(1)

        # ------------------------------------------------------------------
        # JSON view
        # ------------------------------------------------------------------

        self.json_view = QPlainTextEdit()
        self.json_view.setReadOnly(True)
        self.json_view.setPlaceholderText(
            "The workflow of the active network will appear here."
        )

        # ------------------------------------------------------------------
        # Layout
        # ------------------------------------------------------------------

        layout = QVBoxLayout(self)

        layout.addWidget(
            self.title_label
        )
        layout.addWidget(
            self.summary_label
        )

        layout.addSpacing(6)

        layout.addWidget(
            self.search_id_label
        )
        layout.addWidget(
            self.canonical_id_label
        )

        layout.addSpacing(6)

        layout.addLayout(
            button_layout
        )

        layout.addSpacing(6)

        layout.addWidget(
            self.json_view,
            1,
        )

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
            self.summary_label.setText(
                "No active workflow."
            )

            self.search_id_label.setText(
                "Search ID: —"
            )

            self.canonical_id_label.setText(
                "Canonical ID: —"
            )

            self.json_view.clear()

            self.copy_search_id_button.setEnabled(
                False
            )
            self.copy_canonical_id_button.setEnabled(
                False
            )
            self.export_button.setEnabled(
                False
            )

            return

        step_count = len(
            workflow.steps
        )

        step_word = (
            "step"
            if step_count == 1
            else "steps"
        )

        self.summary_label.setText(
            f"Framework: {workflow.framework} | "
            f"Interface: {workflow.interface} | "
            f"{step_count} recorded {step_word}"
        )

        semantic = build_semantic_signature(
            workflow
        )

        search_id = semantic.searchable_id

        canonical_id = workflow_id(
            workflow
        )

        self.search_id_label.setText(
            f"Search ID: {search_id}"
        )

        self.canonical_id_label.setText(
            f"Canonical ID: {canonical_id}"
        )

        self.json_view.setPlainText(
            workflow_to_json(
                workflow
            )
        )

        self.copy_search_id_button.setEnabled(
            True
        )

        self.copy_canonical_id_button.setEnabled(
            True
        )

        self.export_button.setEnabled(
            True
        )

    def _copy_search_id(self) -> None:
        if self._workflow is None:
            return

        search_id = build_semantic_signature(
            self._workflow
        ).searchable_id

        QApplication.clipboard().setText(
            search_id
        )

    def _copy_canonical_id(self) -> None:
        if self._workflow is None:
            return

        QApplication.clipboard().setText(
            workflow_id(
                self._workflow
            )
        )

    def _export_json(self) -> None:
        if self._workflow is None:
            return

        canonical_id = workflow_id(
            self._workflow
        )

        default_name = (
            f"workflow-{canonical_id[:12]}.json"
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Scientific Workflow",
            str(
                Path.home()
                / default_name
            ),
            "JSON Files (*.json)",
        )

        if not file_path:
            return

        if not file_path.lower().endswith(
            ".json"
        ):
            file_path += ".json"

        try:
            Path(file_path).write_text(
                workflow_to_json(
                    self._workflow
                ),
                encoding="utf-8",
            )

        except OSError as exc:
            QMessageBox.critical(
                self,
                "Workflow Export Failed",
                "Could not export the workflow:\n\n"
                f"{exc}",
            )