from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import Any

import pypsa
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QDoubleSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


ARCHITECTURES = [
    ("A", "Architecture A"),
    ("B", "Architecture B"),
    ("C", "Architecture C"),
    ("D", "Architecture D"),
    ("E", "Architecture E"),
    # ("F", "Architecture F"),  # easy to enable later
]


@dataclass
class MLSurrogateConfig:
    task_type: str = "line_loading"
    prediction_scope: str = "per_line"
    time_mode: str = "rolling_window"

    source_type: str = "active_session"
    dataset_path: str = ""
    window_length: int = 24
    train_split: int = 70
    val_split: int = 15
    test_split: int = 15
    normalization: str = "standard"

    architecture: str = "A"
    hidden_dim: int = 64
    num_layers: int = 2
    dropout: float = 0.0
    attention_heads: int = 4
    use_edge_features: bool = True
    residual_connections: bool = True

    epochs: int = 100
    batch_size: int = 32
    learning_rate: float = 1e-3
    loss_function: str = "mse"
    optimizer: str = "adam"
    early_stopping: bool = True
    patience: int = 10
    seed: int = 1234
    device: str = "auto"

    experiment_name: str = "ml_surrogate_run"
    output_dir: str = ""
    save_checkpoints: bool = True
    save_predictions: bool = True
    save_metrics: bool = True


class InfoCard(QGroupBox):
    def __init__(self, title: str, value: str = "-", parent: QWidget | None = None) -> None:
        super().__init__(title, parent)

        self.value_label = QLabel(value)
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setWordWrap(True)
        self.value_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        layout = QVBoxLayout(self)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class MLSurrogatePage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.network: pypsa.Network | None = None

        self.architecture_widgets: dict[str, QWidget] = {}

        self._build_ui()
        self._connect_signals()
        self._on_architecture_changed()
        self._update_summary()

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------
    def set_network(self, network: pypsa.Network | None) -> None:
        self.network = network
        self._append_log("Active PyPSA network updated.")
        self._update_summary()

    # -------------------------------------------------------------------------
    # UI construction
    # -------------------------------------------------------------------------
    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)

        title = QLabel("ML Surrogate")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")

        subtitle = QLabel(
            "Configure surrogate models to approximate selected PyPSA outputs "
            "from simulation data."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #666;")

        outer_layout.addWidget(title)
        outer_layout.addWidget(subtitle)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = self._create_left_panel()
        right_panel = self._create_right_panel()

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        outer_layout.addWidget(splitter)

    def _create_left_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        scroll_layout.addWidget(self._create_task_group())
        scroll_layout.addWidget(self._create_data_group())
        scroll_layout.addWidget(self._create_model_group())
        scroll_layout.addWidget(self._create_training_group())
        scroll_layout.addWidget(self._create_output_group())
        scroll_layout.addWidget(self._create_action_group())
        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        return container

    def _create_right_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        self.active_network_card = InfoCard("Active Network")
        self.task_card = InfoCard("Task")
        self.arch_card = InfoCard("Architecture")
        self.dataset_card = InfoCard("Dataset")
        self.training_card = InfoCard("Training")

        card_grid = QGridLayout()
        card_grid.addWidget(self.active_network_card, 0, 0)
        card_grid.addWidget(self.task_card, 0, 1)
        card_grid.addWidget(self.arch_card, 1, 0)
        card_grid.addWidget(self.dataset_card, 1, 1)
        card_grid.addWidget(self.training_card, 2, 0, 1, 2)

        card_group = QGroupBox("Run Summary")
        card_group.setLayout(card_grid)

        self.dataset_summary_label = QLabel("No dataset preview available yet.")
        self.dataset_summary_label.setWordWrap(True)
        self.dataset_summary_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        dataset_summary_group = QGroupBox("Dataset Summary")
        dataset_summary_layout = QVBoxLayout(dataset_summary_group)
        dataset_summary_layout.addWidget(self.dataset_summary_label)

        self.status_label = QLabel("Ready")
        self.status_label.setWordWrap(True)

        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)
        status_layout.addWidget(self.status_label)

        self.plot_placeholder = QLabel("Training curves and validation metrics will appear here.")
        self.plot_placeholder.setAlignment(Qt.AlignCenter)
        self.plot_placeholder.setMinimumHeight(180)
        self.plot_placeholder.setStyleSheet(
            "border: 1px solid #bbb; background: #fafafa; color: #666;"
        )

        plot_group = QGroupBox("Training Output")
        plot_layout = QVBoxLayout(plot_group)
        plot_layout.addWidget(self.plot_placeholder)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Logs will appear here...")

        log_group = QGroupBox("Logs")
        log_layout = QVBoxLayout(log_group)
        log_layout.addWidget(self.log_output)

        layout.addWidget(card_group)
        layout.addWidget(dataset_summary_group)
        layout.addWidget(status_group)
        layout.addWidget(plot_group)
        layout.addWidget(log_group)

        return container

    def _create_task_group(self) -> QGroupBox:
        group = QGroupBox("Task Setup")
        layout = QFormLayout(group)

        self.task_type_combo = QComboBox()
        self.task_type_combo.addItems(
            [
                "line_loading",
                "nodal_price",
                "dispatch",
                "congestion_classification",
                "storage_behaviour",
                "custom",
            ]
        )

        self.prediction_scope_combo = QComboBox()
        self.prediction_scope_combo.addItems(
            [
                "system_wide",
                "per_bus",
                "per_line",
                "per_generator",
                "per_storage_unit",
            ]
        )

        self.time_mode_combo = QComboBox()
        self.time_mode_combo.addItems(
            [
                "snapshot_wise",
                "rolling_window",
                "sequence_to_sequence",
            ]
        )

        layout.addRow("Task type:", self.task_type_combo)
        layout.addRow("Prediction scope:", self.prediction_scope_combo)
        layout.addRow("Time mode:", self.time_mode_combo)

        return group

    def _create_data_group(self) -> QGroupBox:
        group = QGroupBox("Data Source")
        layout = QFormLayout(group)

        self.source_type_combo = QComboBox()
        self.source_type_combo.addItems(
            [
                "active_session",
                "folder_of_runs",
                "prepared_dataset",
            ]
        )

        self.dataset_path_edit = QLineEdit()
        self.dataset_browse_button = QPushButton("Browse...")

        dataset_path_row = QWidget()
        dataset_path_layout = QHBoxLayout(dataset_path_row)
        dataset_path_layout.setContentsMargins(0, 0, 0, 0)
        dataset_path_layout.addWidget(self.dataset_path_edit)
        dataset_path_layout.addWidget(self.dataset_browse_button)

        self.window_length_spin = QSpinBox()
        self.window_length_spin.setRange(1, 10_000)
        self.window_length_spin.setValue(24)

        self.train_split_spin = QSpinBox()
        self.train_split_spin.setRange(0, 100)
        self.train_split_spin.setValue(70)

        self.val_split_spin = QSpinBox()
        self.val_split_spin.setRange(0, 100)
        self.val_split_spin.setValue(15)

        self.test_split_spin = QSpinBox()
        self.test_split_spin.setRange(0, 100)
        self.test_split_spin.setValue(15)

        self.normalization_combo = QComboBox()
        self.normalization_combo.addItems(
            [
                "none",
                "standard",
                "minmax",
            ]
        )

        layout.addRow("Source type:", self.source_type_combo)
        layout.addRow("Dataset / folder:", dataset_path_row)
        layout.addRow("Window length:", self.window_length_spin)
        layout.addRow("Train split (%):", self.train_split_spin)
        layout.addRow("Validation split (%):", self.val_split_spin)
        layout.addRow("Test split (%):", self.test_split_spin)
        layout.addRow("Normalization:", self.normalization_combo)

        return group

    def _create_model_group(self) -> QGroupBox:
        group = QGroupBox("Model Architecture")
        self.model_group_layout = QVBoxLayout(group)

        top_form = QFormLayout()

        self.architecture_combo = QComboBox()
        for arch_id, arch_label in ARCHITECTURES:
            self.architecture_combo.addItem(f"{arch_id} — {arch_label}", arch_id)

        top_form.addRow("Architecture:", self.architecture_combo)

        self.model_group_layout.addLayout(top_form)

        self.architecture_settings_group = QGroupBox("Architecture Parameters")
        self.architecture_settings_layout = QFormLayout(self.architecture_settings_group)
        self.model_group_layout.addWidget(self.architecture_settings_group)

        # Common controls reused by different architectures
        self.hidden_dim_spin = QSpinBox()
        self.hidden_dim_spin.setRange(1, 100_000)
        self.hidden_dim_spin.setValue(64)

        self.num_layers_spin = QSpinBox()
        self.num_layers_spin.setRange(1, 100)
        self.num_layers_spin.setValue(2)

        self.dropout_spin = QDoubleSpinBox()
        self.dropout_spin.setRange(0.0, 1.0)
        self.dropout_spin.setSingleStep(0.05)
        self.dropout_spin.setDecimals(2)
        self.dropout_spin.setValue(0.0)

        self.attention_heads_spin = QSpinBox()
        self.attention_heads_spin.setRange(1, 64)
        self.attention_heads_spin.setValue(4)

        self.use_edge_features_check = QCheckBox("Use edge features")
        self.use_edge_features_check.setChecked(True)

        self.residual_connections_check = QCheckBox("Use residual connections")
        self.residual_connections_check.setChecked(True)

        return group

    def _create_training_group(self) -> QGroupBox:
        group = QGroupBox("Training Parameters")
        layout = QFormLayout(group)

        self.epochs_spin = QSpinBox()
        self.epochs_spin.setRange(1, 1_000_000)
        self.epochs_spin.setValue(100)

        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 100_000)
        self.batch_size_spin.setValue(32)

        self.learning_rate_spin = QDoubleSpinBox()
        self.learning_rate_spin.setDecimals(6)
        self.learning_rate_spin.setRange(0.0, 10.0)
        self.learning_rate_spin.setSingleStep(0.0001)
        self.learning_rate_spin.setValue(0.001)

        self.loss_function_combo = QComboBox()
        self.loss_function_combo.addItems(["mse", "mae", "huber", "cross_entropy"])

        self.optimizer_combo = QComboBox()
        self.optimizer_combo.addItems(["adam", "adamw", "sgd"])

        self.early_stopping_check = QCheckBox("Enable early stopping")
        self.early_stopping_check.setChecked(True)

        self.patience_spin = QSpinBox()
        self.patience_spin.setRange(1, 10_000)
        self.patience_spin.setValue(10)

        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 999_999_999)
        self.seed_spin.setValue(1234)

        self.device_combo = QComboBox()
        self.device_combo.addItems(["auto", "cpu", "gpu"])

        layout.addRow("Epochs:", self.epochs_spin)
        layout.addRow("Batch size:", self.batch_size_spin)
        layout.addRow("Learning rate:", self.learning_rate_spin)
        layout.addRow("Loss function:", self.loss_function_combo)
        layout.addRow("Optimizer:", self.optimizer_combo)
        layout.addRow(self.early_stopping_check)
        layout.addRow("Patience:", self.patience_spin)
        layout.addRow("Random seed:", self.seed_spin)
        layout.addRow("Device:", self.device_combo)

        return group

    def _create_output_group(self) -> QGroupBox:
        group = QGroupBox("Outputs")
        layout = QFormLayout(group)

        self.experiment_name_edit = QLineEdit("ml_surrogate_run")

        self.output_dir_edit = QLineEdit()
        self.output_dir_button = QPushButton("Browse...")

        output_dir_row = QWidget()
        output_dir_layout = QHBoxLayout(output_dir_row)
        output_dir_layout.setContentsMargins(0, 0, 0, 0)
        output_dir_layout.addWidget(self.output_dir_edit)
        output_dir_layout.addWidget(self.output_dir_button)

        self.save_checkpoints_check = QCheckBox("Save checkpoints")
        self.save_checkpoints_check.setChecked(True)

        self.save_predictions_check = QCheckBox("Save predictions")
        self.save_predictions_check.setChecked(True)

        self.save_metrics_check = QCheckBox("Save metrics")
        self.save_metrics_check.setChecked(True)

        layout.addRow("Experiment name:", self.experiment_name_edit)
        layout.addRow("Output directory:", output_dir_row)
        layout.addRow(self.save_checkpoints_check)
        layout.addRow(self.save_predictions_check)
        layout.addRow(self.save_metrics_check)

        return group

    def _create_action_group(self) -> QGroupBox:
        group = QGroupBox("Actions")
        layout = QHBoxLayout(group)

        self.preview_button = QPushButton("Preview Dataset")
        self.save_config_button = QPushButton("Save Config")
        self.load_config_button = QPushButton("Load Config")
        self.train_button = QPushButton("Train Surrogate")
        self.evaluate_button = QPushButton("Evaluate")

        self.evaluate_button.setEnabled(False)

        layout.addWidget(self.preview_button)
        layout.addWidget(self.save_config_button)
        layout.addWidget(self.load_config_button)
        layout.addWidget(self.train_button)
        layout.addWidget(self.evaluate_button)

        return group

    # -------------------------------------------------------------------------
    # Signals
    # -------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        self.architecture_combo.currentIndexChanged.connect(self._on_architecture_changed)

        self.dataset_browse_button.clicked.connect(self._browse_dataset_path)
        self.output_dir_button.clicked.connect(self._browse_output_dir)

        self.preview_button.clicked.connect(self._preview_dataset)
        self.save_config_button.clicked.connect(self._save_config)
        self.load_config_button.clicked.connect(self._load_config)
        self.train_button.clicked.connect(self._train_surrogate)
        self.evaluate_button.clicked.connect(self._evaluate_surrogate)

        watched_widgets = [
            self.task_type_combo,
            self.prediction_scope_combo,
            self.time_mode_combo,
            self.source_type_combo,
            self.dataset_path_edit,
            self.window_length_spin,
            self.train_split_spin,
            self.val_split_spin,
            self.test_split_spin,
            self.normalization_combo,
            self.architecture_combo,
            self.hidden_dim_spin,
            self.num_layers_spin,
            self.dropout_spin,
            self.attention_heads_spin,
            self.use_edge_features_check,
            self.residual_connections_check,
            self.epochs_spin,
            self.batch_size_spin,
            self.learning_rate_spin,
            self.loss_function_combo,
            self.optimizer_combo,
            self.early_stopping_check,
            self.patience_spin,
            self.seed_spin,
            self.device_combo,
            self.experiment_name_edit,
            self.output_dir_edit,
            self.save_checkpoints_check,
            self.save_predictions_check,
            self.save_metrics_check,
        ]

        for widget in watched_widgets:
            if isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._update_summary)
            elif isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._update_summary)
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.valueChanged.connect(self._update_summary)
            elif isinstance(widget, QCheckBox):
                widget.toggled.connect(self._update_summary)

    # -------------------------------------------------------------------------
    # Dynamic architecture UI
    # -------------------------------------------------------------------------
    def _clear_architecture_settings(self) -> None:
        while self.architecture_settings_layout.rowCount() > 0:
            self.architecture_settings_layout.removeRow(0)

    def _on_architecture_changed(self) -> None:
        arch = self._selected_architecture_id()
        self._clear_architecture_settings()

        # A: simple feedforward baseline
        if arch == "A":
            self.architecture_settings_layout.addRow("Hidden dimension:", self.hidden_dim_spin)
            self.architecture_settings_layout.addRow("Number of layers:", self.num_layers_spin)
            self.architecture_settings_layout.addRow("Dropout:", self.dropout_spin)

        # B: slightly deeper / structured baseline
        elif arch == "B":
            self.architecture_settings_layout.addRow("Hidden dimension:", self.hidden_dim_spin)
            self.architecture_settings_layout.addRow("Number of layers:", self.num_layers_spin)
            self.architecture_settings_layout.addRow("Dropout:", self.dropout_spin)
            self.architecture_settings_layout.addRow(self.residual_connections_check)

        # C: temporal
        elif arch == "C":
            self.architecture_settings_layout.addRow("Hidden dimension:", self.hidden_dim_spin)
            self.architecture_settings_layout.addRow("Number of layers:", self.num_layers_spin)
            self.architecture_settings_layout.addRow("Dropout:", self.dropout_spin)

        # D: graph model
        elif arch == "D":
            self.architecture_settings_layout.addRow("Hidden dimension:", self.hidden_dim_spin)
            self.architecture_settings_layout.addRow("Number of message-passing layers:", self.num_layers_spin)
            self.architecture_settings_layout.addRow(self.use_edge_features_check)
            self.architecture_settings_layout.addRow(self.residual_connections_check)
            self.architecture_settings_layout.addRow("Dropout:", self.dropout_spin)

        # E: graph attention style
        elif arch == "E":
            self.architecture_settings_layout.addRow("Hidden dimension:", self.hidden_dim_spin)
            self.architecture_settings_layout.addRow("Number of attention layers:", self.num_layers_spin)
            self.architecture_settings_layout.addRow("Attention heads:", self.attention_heads_spin)
            self.architecture_settings_layout.addRow(self.use_edge_features_check)
            self.architecture_settings_layout.addRow(self.residual_connections_check)
            self.architecture_settings_layout.addRow("Dropout:", self.dropout_spin)

        else:
            self.architecture_settings_layout.addRow(
                QLabel("No parameter form defined for this architecture yet.")
            )

        self._append_log(f"Architecture changed to {arch}.")
        self._update_summary()

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------
    def _browse_dataset_path(self) -> None:
        source_type = self.source_type_combo.currentText()

        if source_type == "folder_of_runs":
            path = QFileDialog.getExistingDirectory(self, "Select Folder of Runs")
            if path:
                self.dataset_path_edit.setText(path)
        else:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Dataset or Network File",
                "",
                "All Files (*.*)",
            )
            if path:
                self.dataset_path_edit.setText(path)

    def _browse_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self.output_dir_edit.setText(path)

    def _preview_dataset(self) -> None:
        config = self._gather_config()

        split_sum = config.train_split + config.val_split + config.test_split
        if split_sum != 100:
            QMessageBox.warning(
                self,
                "Invalid split",
                "Train/validation/test splits must sum to 100.",
            )
            self.status_label.setText("Dataset preview failed: invalid split.")
            return

        if config.source_type != "active_session" and not config.dataset_path:
            QMessageBox.warning(
                self,
                "Missing dataset path",
                "Please select a dataset or folder first.",
            )
            self.status_label.setText("Dataset preview failed: missing path.")
            return

        source_desc = (
            "active loaded PyPSA network"
            if config.source_type == "active_session"
            else config.dataset_path
        )

        text = (
            f"Source: {source_desc}\n"
            f"Task: {config.task_type}\n"
            f"Scope: {config.prediction_scope}\n"
            f"Time mode: {config.time_mode}\n"
            f"Window length: {config.window_length}\n"
            f"Split: {config.train_split}/{config.val_split}/{config.test_split}\n"
            f"Normalization: {config.normalization}\n\n"
            f"Preview backend not implemented yet.\n"
            f"This area can later show sample count, feature count, target shape, "
            f"missing values, and snapshot coverage."
        )

        self.dataset_summary_label.setText(text)
        self.status_label.setText("Dataset preview completed (stub).")
        self._append_log("Dataset preview executed (stub).")

    def _save_config(self) -> None:
        config = self._gather_config()

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save ML Surrogate Config",
            f"{config.experiment_name}.json",
            "JSON Files (*.json)",
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(asdict(config), f, indent=2)
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", f"Could not save config:\n{exc}")
            self._append_log(f"Failed to save config: {exc}")
            return

        self.status_label.setText(f"Configuration saved to {path}")
        self._append_log(f"Configuration saved: {path}")

    def _load_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load ML Surrogate Config",
            "",
            "JSON Files (*.json)",
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Load failed", f"Could not load config:\n{exc}")
            self._append_log(f"Failed to load config: {exc}")
            return

        self._apply_config_dict(data)
        self.status_label.setText(f"Configuration loaded from {path}")
        self._append_log(f"Configuration loaded: {path}")

    def _train_surrogate(self) -> None:
        config = self._gather_config()

        split_sum = config.train_split + config.val_split + config.test_split
        if split_sum != 100:
            QMessageBox.warning(
                self,
                "Invalid split",
                "Train/validation/test splits must sum to 100.",
            )
            self.status_label.setText("Training failed: invalid split.")
            return

        self.status_label.setText("Training requested (stub backend).")
        self.plot_placeholder.setText(
            "Training not yet implemented.\n\n"
            "Later this area can show:\n"
            "- train / validation loss curves\n"
            "- metrics per epoch\n"
            "- checkpoint status"
        )

        self._append_log("Training requested.")
        self._append_log(f"Architecture: {config.architecture}")
        self._append_log(f"Task: {config.task_type}")
        self._append_log(f"Epochs: {config.epochs}, batch size: {config.batch_size}")
        self._append_log("Training backend not implemented yet.")

    def _evaluate_surrogate(self) -> None:
        self.status_label.setText("Evaluation not implemented yet.")
        self._append_log("Evaluation requested, but backend is not implemented yet.")

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _selected_architecture_id(self) -> str:
        data = self.architecture_combo.currentData()
        return str(data) if data is not None else "A"

    def _gather_config(self) -> MLSurrogateConfig:
        return MLSurrogateConfig(
            task_type=self.task_type_combo.currentText(),
            prediction_scope=self.prediction_scope_combo.currentText(),
            time_mode=self.time_mode_combo.currentText(),
            source_type=self.source_type_combo.currentText(),
            dataset_path=self.dataset_path_edit.text().strip(),
            window_length=self.window_length_spin.value(),
            train_split=self.train_split_spin.value(),
            val_split=self.val_split_spin.value(),
            test_split=self.test_split_spin.value(),
            normalization=self.normalization_combo.currentText(),
            architecture=self._selected_architecture_id(),
            hidden_dim=self.hidden_dim_spin.value(),
            num_layers=self.num_layers_spin.value(),
            dropout=self.dropout_spin.value(),
            attention_heads=self.attention_heads_spin.value(),
            use_edge_features=self.use_edge_features_check.isChecked(),
            residual_connections=self.residual_connections_check.isChecked(),
            epochs=self.epochs_spin.value(),
            batch_size=self.batch_size_spin.value(),
            learning_rate=self.learning_rate_spin.value(),
            loss_function=self.loss_function_combo.currentText(),
            optimizer=self.optimizer_combo.currentText(),
            early_stopping=self.early_stopping_check.isChecked(),
            patience=self.patience_spin.value(),
            seed=self.seed_spin.value(),
            device=self.device_combo.currentText(),
            experiment_name=self.experiment_name_edit.text().strip() or "ml_surrogate_run",
            output_dir=self.output_dir_edit.text().strip(),
            save_checkpoints=self.save_checkpoints_check.isChecked(),
            save_predictions=self.save_predictions_check.isChecked(),
            save_metrics=self.save_metrics_check.isChecked(),
        )

    def _apply_config_dict(self, data: dict[str, Any]) -> None:
        self.task_type_combo.setCurrentText(str(data.get("task_type", "line_loading")))
        self.prediction_scope_combo.setCurrentText(str(data.get("prediction_scope", "per_line")))
        self.time_mode_combo.setCurrentText(str(data.get("time_mode", "rolling_window")))

        self.source_type_combo.setCurrentText(str(data.get("source_type", "active_session")))
        self.dataset_path_edit.setText(str(data.get("dataset_path", "")))
        self.window_length_spin.setValue(int(data.get("window_length", 24)))
        self.train_split_spin.setValue(int(data.get("train_split", 70)))
        self.val_split_spin.setValue(int(data.get("val_split", 15)))
        self.test_split_spin.setValue(int(data.get("test_split", 15)))
        self.normalization_combo.setCurrentText(str(data.get("normalization", "standard")))

        arch = str(data.get("architecture", "A"))
        index = self.architecture_combo.findData(arch)
        if index >= 0:
            self.architecture_combo.setCurrentIndex(index)

        self.hidden_dim_spin.setValue(int(data.get("hidden_dim", 64)))
        self.num_layers_spin.setValue(int(data.get("num_layers", 2)))
        self.dropout_spin.setValue(float(data.get("dropout", 0.0)))
        self.attention_heads_spin.setValue(int(data.get("attention_heads", 4)))
        self.use_edge_features_check.setChecked(bool(data.get("use_edge_features", True)))
        self.residual_connections_check.setChecked(bool(data.get("residual_connections", True)))

        self.epochs_spin.setValue(int(data.get("epochs", 100)))
        self.batch_size_spin.setValue(int(data.get("batch_size", 32)))
        self.learning_rate_spin.setValue(float(data.get("learning_rate", 1e-3)))
        self.loss_function_combo.setCurrentText(str(data.get("loss_function", "mse")))
        self.optimizer_combo.setCurrentText(str(data.get("optimizer", "adam")))
        self.early_stopping_check.setChecked(bool(data.get("early_stopping", True)))
        self.patience_spin.setValue(int(data.get("patience", 10)))
        self.seed_spin.setValue(int(data.get("seed", 1234)))
        self.device_combo.setCurrentText(str(data.get("device", "auto")))

        self.experiment_name_edit.setText(str(data.get("experiment_name", "ml_surrogate_run")))
        self.output_dir_edit.setText(str(data.get("output_dir", "")))
        self.save_checkpoints_check.setChecked(bool(data.get("save_checkpoints", True)))
        self.save_predictions_check.setChecked(bool(data.get("save_predictions", True)))
        self.save_metrics_check.setChecked(bool(data.get("save_metrics", True)))

        self._on_architecture_changed()
        self._update_summary()

    def _update_summary(self) -> None:
        config = self._gather_config()

        network_name = "-"
        if self.network is not None:
            network_name = getattr(self.network, "name", "") or "Loaded network"

        dataset_text = config.source_type
        if config.dataset_path:
            dataset_text += f"\n{config.dataset_path}"

        training_text = (
            f"{config.epochs} epochs\n"
            f"batch={config.batch_size}\n"
            f"lr={config.learning_rate:g}"
        )

        task_text = f"{config.task_type}\n{config.prediction_scope}"
        arch_text = f"{config.architecture}\nwindow={config.window_length}"

        self.active_network_card.set_value(network_name)
        self.task_card.set_value(task_text)
        self.arch_card.set_value(arch_text)
        self.dataset_card.set_value(dataset_text)
        self.training_card.set_value(training_text)

        split_sum = config.train_split + config.val_split + config.test_split
        if split_sum == 100:
            self.status_label.setText("Ready")
        else:
            self.status_label.setText(
                f"Invalid split: train+val+test={split_sum} (must be 100)"
            )

    def _append_log(self, message: str) -> None:
        self.log_output.appendPlainText(message)