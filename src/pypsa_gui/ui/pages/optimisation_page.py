from __future__ import annotations

from pathlib import Path

import pypsa
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pypsa_gui.services.optimisation import preview_network_optimisation
from pypsa_gui.services.reporting import (
    generate_scenario_report,
    network_has_results,
)


class InfoCard(QGroupBox):
    def __init__(
        self,
        title: str,
        value: str = "-",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, parent)

        self.value_label = QLabel(value)
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setStyleSheet(
            "font-size: 18px; font-weight: bold;"
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class OptimisationPage(QWidget):
    run_optimisation_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.network: pypsa.Network | None = None

        self.preview_button = QPushButton(
            "Preview Model"
        )
        self.preview_button.clicked.connect(
            self._preview_model
        )

        self.run_button = QPushButton(
            "Run Optimisation"
        )
        self.run_button.clicked.connect(
            self.run_optimisation_requested.emit
        )

        self.export_report_button = QPushButton(
            "Generate Analysis Report"
        )
        self.export_report_button.clicked.connect(
            self._export_analysis_report
        )

        self.status_label = QLabel(
            "Load a network and preview or run the model."
        )
        self.status_label.setWordWrap(True)

        self.variables_card = InfoCard(
            "Variables"
        )
        self.constraints_card = InfoCard(
            "Constraints"
        )
        self.nonzeros_card = InfoCard(
            "Nonzeros"
        )
        self.size_card = InfoCard(
            "Estimated Size"
        )

        metrics_layout = QGridLayout()
        metrics_layout.addWidget(
            self.variables_card,
            0,
            0,
        )
        metrics_layout.addWidget(
            self.constraints_card,
            0,
            1,
        )
        metrics_layout.addWidget(
            self.nonzeros_card,
            1,
            0,
        )
        metrics_layout.addWidget(
            self.size_card,
            1,
            1,
        )

        metrics_group = QGroupBox(
            "Dry Run Info"
        )
        metrics_group.setLayout(
            metrics_layout
        )

        self.matrix_shape_label = QLabel("-")
        self.matrix_density_label = QLabel("-")
        self.ram_label = QLabel("-")

        details_layout = QFormLayout()
        details_layout.addRow(
            "Matrix shape:",
            self.matrix_shape_label,
        )
        details_layout.addRow(
            "Matrix density:",
            self.matrix_density_label,
        )
        details_layout.addRow(
            "Estimated RAM:",
            self.ram_label,
        )

        details_group = QGroupBox(
            "Details"
        )
        details_group.setLayout(
            details_layout
        )

        report_description = QLabel(
            "Generate a PDF summary for the currently "
            "loaded solved network."
        )
        report_description.setWordWrap(True)

        report_layout = QVBoxLayout()
        report_layout.addWidget(
            report_description
        )
        report_layout.addWidget(
            self.export_report_button
        )

        report_group = QGroupBox(
            "Results Report"
        )
        report_group.setLayout(
            report_layout
        )

        action_layout = QHBoxLayout()
        action_layout.addWidget(
            self.preview_button
        )
        action_layout.addWidget(
            self.run_button
        )

        layout = QVBoxLayout(self)
        layout.addLayout(
            action_layout
        )
        layout.addWidget(
            self.status_label
        )
        layout.addWidget(
            metrics_group
        )
        layout.addWidget(
            details_group
        )
        layout.addWidget(
            report_group
        )
        layout.addStretch()

        self.preview_button.setEnabled(False)
        self.run_button.setEnabled(False)
        self.export_report_button.setEnabled(False)

    def set_network(
        self,
        network: pypsa.Network | None,
    ) -> None:
        self.network = network

        has_network = network is not None
        has_results = bool(
            network_has_results(network)
        ) if network is not None else False

        self.preview_button.setEnabled(
            has_network
        )
        self.run_button.setEnabled(
            has_network
        )
        self.export_report_button.setEnabled(
            has_results
        )

        if network is None:
            self.status_label.setText(
                "No network loaded."
            )
        elif has_results:
            self.status_label.setText(
                "Solved network loaded. "
                "The analysis report is available."
            )
        else:
            self.status_label.setText(
                "Ready to preview or run the "
                "optimisation model."
            )

        self._clear_preview()

    def refresh_results_state(self) -> None:
        """
        Refresh the page after optimisation finished elsewhere.
        """

        has_results = (
            self.network is not None
            and network_has_results(self.network)
        )

        self.export_report_button.setEnabled(
            has_results
        )

        if has_results:
            self.status_label.setText(
                "Optimisation completed successfully. "
                "You can now generate an analysis report."
            )

    def set_optimisation_running(
        self,
        running: bool,
    ) -> None:
        """
        Update controls while optimisation is running.

        This can be called from MainWindow when the toolbar
        optimisation starts or finishes.
        """

        has_network = self.network is not None

        self.preview_button.setEnabled(
            has_network and not running
        )
        self.run_button.setEnabled(
            has_network and not running
        )

        if running:
            self.export_report_button.setEnabled(
                False
            )
            self.status_label.setText(
                "Running optimisation..."
            )
        else:
            self.refresh_results_state()

    def _clear_preview(self) -> None:
        self.variables_card.set_value("-")
        self.constraints_card.set_value("-")
        self.nonzeros_card.set_value("-")
        self.size_card.set_value("-")
        self.matrix_shape_label.setText("-")
        self.matrix_density_label.setText("-")
        self.ram_label.setText("-")

    def _preview_model(self) -> None:
        if self.network is None:
            self.status_label.setText(
                "No network loaded."
            )
            return

        self.preview_button.setEnabled(False)
        self.run_button.setEnabled(False)

        self.status_label.setText(
            "Building optimisation model..."
        )
        self.repaint()

        try:
            preview = preview_network_optimisation(
                self.network
            )
        except Exception as exc:
            self.status_label.setText(
                f"Preview failed: {exc}"
            )
        else:
            self.variables_card.set_value(
                f"{preview.variables:,}"
            )
            self.constraints_card.set_value(
                f"{preview.constraints:,}"
            )
            self.nonzeros_card.set_value(
                "-"
                if preview.nonzeros is None
                else f"{preview.nonzeros:,}"
            )
            self.size_card.set_value(
                preview.status
            )

            if (
                preview.matrix_rows is not None
                and preview.matrix_cols is not None
            ):
                self.matrix_shape_label.setText(
                    f"{preview.matrix_rows:,} × "
                    f"{preview.matrix_cols:,}"
                )
            else:
                self.matrix_shape_label.setText("-")

            if preview.matrix_density is not None:
                self.matrix_density_label.setText(
                    f"{preview.matrix_density:.6f}"
                )
            else:
                self.matrix_density_label.setText("-")

            if (
                preview.estimated_ram_low_gb
                is not None
                and preview.estimated_ram_high_gb
                is not None
            ):
                self.ram_label.setText(
                    f"{preview.estimated_ram_low_gb:.1f} – "
                    f"{preview.estimated_ram_high_gb:.1f} GB"
                )
            else:
                self.ram_label.setText("-")

            self.status_label.setText(
                "Model preview created successfully."
            )
        finally:
            self.preview_button.setEnabled(True)
            self.run_button.setEnabled(True)

    def _export_analysis_report(self) -> None:
        if self.network is None:
            QMessageBox.warning(
                self,
                "No network loaded",
                "Load and solve a network before "
                "generating a report.",
            )
            return

        if not network_has_results(self.network):
            QMessageBox.warning(
                self,
                "No optimisation results",
                "The currently loaded network does not "
                "contain solved optimisation results.",
            )
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Analysis Report",
            f"{self._safe_network_name()}"
            "-analysis-report.pdf",
            "PDF files (*.pdf)",
        )

        if not output_path:
            return

        self.export_report_button.setEnabled(
            False
        )
        self.status_label.setText(
            "Generating analysis report..."
        )
        self.repaint()

        try:
            report_path = generate_scenario_report(
                network=self.network,
                output_path=Path(output_path),
            )
        except Exception as exc:
            self.status_label.setText(
                "Report generation failed."
            )

            QMessageBox.critical(
                self,
                "Report generation failed",
                "The PDF report could not be generated."
                "\n\n"
                f"{exc}",
            )
        else:
            self.status_label.setText(
                "Analysis report generated successfully."
            )

            QMessageBox.information(
                self,
                "Report generated",
                "The analysis report was created "
                "successfully."
                "\n\n"
                f"{report_path}",
            )
        finally:
            self.export_report_button.setEnabled(
                self.network is not None
                and network_has_results(self.network)
            )

    def _safe_network_name(self) -> str:
        if (
            self.network is None
            or not getattr(
                self.network,
                "name",
                None,
            )
        ):
            return "pypsa-network"

        name = str(
            self.network.name
        ).strip()

        invalid_characters = (
            "/",
            "\\",
            ":",
            "*",
            "?",
            '"',
            "<",
            ">",
            "|",
        )

        for character in invalid_characters:
            name = name.replace(
                character,
                "-",
            )

        name = "-".join(
            name.split()
        )

        return name or "pypsa-network"