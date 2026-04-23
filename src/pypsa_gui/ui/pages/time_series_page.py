from __future__ import annotations

import pypsa
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pypsa_gui.services.time_series import (
    TimeSeriesSummary,
    aggregate_time_series,
    build_time_series_summary,
    filter_time_series_dataframe,
    get_available_carriers,
    get_available_component_types,
    get_available_time_series_fields,
    get_component_names,
    get_time_series_dataframe,
)


class InfoCard(QGroupBox):
    def __init__(self, title: str, value: str = "-", parent: QWidget | None = None) -> None:
        super().__init__(title, parent)

        self.value_label = QLabel(value)
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setStyleSheet("font-size: 18px; font-weight: bold;")

        layout = QVBoxLayout(self)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class PlotCard(QGroupBox):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)

        self.figure = Figure(figsize=(12, 7))
        self.canvas = FigureCanvas(self.figure)

        self.setMinimumHeight(650)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)

    def clear(self) -> None:
        self.figure.clear()
        self.canvas.draw_idle()


class TimeSeriesPage(QWidget):
    AGGREGATION_MODES = ["By carrier", "Sum", "Mean", "Individual"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.network: pypsa.Network | None = None

        root_layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root_layout.addWidget(scroll)

        container = QWidget()
        container.setMinimumWidth(900)
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll.setWidget(container)

        self.content_layout = QVBoxLayout(container)
        self.content_layout.setAlignment(Qt.AlignTop)
        self.content_layout.setSpacing(12)

        self._build_controls()
        self._build_plot()
        self._build_summary_cards()
        self.content_layout.addStretch()

        self._set_empty_state("Load a network to explore time series.")

    def _build_controls(self) -> None:
        group = QGroupBox("Time Series Controls")
        layout = QVBoxLayout(group)

        form_layout = QGridLayout()

        self.component_combo = QComboBox()
        self.field_combo = QComboBox()
        self.aggregation_combo = QComboBox()
        self.aggregation_combo.addItems(self.AGGREGATION_MODES)

        self.carrier_combo = QComboBox()
        self.carrier_combo.addItem("All carriers")

        form_layout.addWidget(QLabel("Component type"), 0, 0)
        form_layout.addWidget(self.component_combo, 0, 1)

        form_layout.addWidget(QLabel("Variable"), 0, 2)
        form_layout.addWidget(self.field_combo, 0, 3)

        form_layout.addWidget(QLabel("Aggregation"), 1, 0)
        form_layout.addWidget(self.aggregation_combo, 1, 1)

        form_layout.addWidget(QLabel("Carrier filter"), 1, 2)
        form_layout.addWidget(self.carrier_combo, 1, 3)

        layout.addLayout(form_layout)

        selector_row = QHBoxLayout()

        component_group = QGroupBox("Components")
        component_layout = QVBoxLayout(component_group)

        self.component_list = QListWidget()
        self.component_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.component_list.setMinimumHeight(220)
        component_layout.addWidget(self.component_list)

        button_row = QHBoxLayout()
        self.select_all_button = QPushButton("Select all")
        self.clear_selection_button = QPushButton("Clear selection")
        button_row.addWidget(self.select_all_button)
        button_row.addWidget(self.clear_selection_button)
        component_layout.addLayout(button_row)

        selector_row.addWidget(component_group, stretch=1)
        layout.addLayout(selector_row)

        self.refresh_button = QPushButton("Refresh Plot")
        layout.addWidget(self.refresh_button, alignment=Qt.AlignRight)

        self.content_layout.addWidget(group)

        self.component_combo.currentTextChanged.connect(self._on_component_changed)
        self.field_combo.currentTextChanged.connect(self._refresh_plot)
        self.aggregation_combo.currentTextChanged.connect(self._refresh_plot)
        self.carrier_combo.currentTextChanged.connect(self._on_carrier_changed)
        self.refresh_button.clicked.connect(self._refresh_plot)
        self.select_all_button.clicked.connect(self._select_all_components)
        self.clear_selection_button.clicked.connect(self.component_list.clearSelection)
        self.component_list.itemSelectionChanged.connect(self._refresh_plot)

    def _build_summary_cards(self) -> None:
        layout = QGridLayout()

        self.snapshots_card = InfoCard("Snapshots")
        self.series_card = InfoCard("Series")
        self.min_card = InfoCard("Min")
        self.max_card = InfoCard("Max")
        self.mean_card = InfoCard("Mean")

        layout.addWidget(self.snapshots_card, 0, 0)
        layout.addWidget(self.series_card, 0, 1)
        layout.addWidget(self.min_card, 0, 2)
        layout.addWidget(self.max_card, 0, 3)
        layout.addWidget(self.mean_card, 0, 4)

        wrapper = QGroupBox("Summary")
        wrapper.setLayout(layout)
        self.content_layout.addWidget(wrapper)

    def _build_plot(self) -> None:
        self.plot_card = PlotCard("Time Series Plot")
        self.content_layout.addWidget(self.plot_card, stretch=1)

    def set_network(self, network: pypsa.Network | None) -> None:
        self.network = network
        self._populate_component_types()

    def _populate_component_types(self) -> None:
        self.component_combo.blockSignals(True)
        self.component_combo.clear()

        if self.network is not None:
            component_types = get_available_component_types(self.network)
            self.component_combo.addItems(component_types)

            if "Generators" in component_types:
                self.component_combo.setCurrentText("Generators")

        self.component_combo.blockSignals(False)

        if self.component_combo.count() == 0:
            self._clear_controls()
            self._set_empty_state("No time series data available in this network.")
            return

        self._on_component_changed()

    def _on_component_changed(self) -> None:
        self._populate_fields()
        self._populate_carriers()
        self._populate_components()
        self._refresh_plot()

    def _populate_fields(self) -> None:
        self.field_combo.blockSignals(True)
        self.field_combo.clear()

        if self.network is None:
            self.field_combo.blockSignals(False)
            return

        component_type = self.component_combo.currentText()
        fields = get_available_time_series_fields(self.network, component_type)
        self.field_combo.addItems(fields)

        if component_type == "Generators" and "p" in fields:
            self.field_combo.setCurrentText("p")
        elif component_type == "Loads" and "p" in fields:
            self.field_combo.setCurrentText("p")
        elif component_type == "Storage Units" and "state_of_charge" in fields:
            self.field_combo.setCurrentText("state_of_charge")
        elif fields:
            self.field_combo.setCurrentIndex(0)

        self.field_combo.blockSignals(False)

    def _populate_carriers(self) -> None:
        self.carrier_combo.blockSignals(True)
        self.carrier_combo.clear()
        self.carrier_combo.addItem("All carriers")

        if self.network is not None:
            component_type = self.component_combo.currentText()
            carriers = get_available_carriers(self.network, component_type)
            self.carrier_combo.addItems(carriers)

        self.carrier_combo.blockSignals(False)

    def _populate_components(self) -> None:
        self.component_list.blockSignals(True)
        self.component_list.clear()

        if self.network is None:
            self.component_list.blockSignals(False)
            return

        component_type = self.component_combo.currentText()
        carrier = self.carrier_combo.currentText()
        names = get_component_names(self.network, component_type, carrier=carrier)

        for name in names:
            item = QListWidgetItem(name)
            self.component_list.addItem(item)

        self.component_list.blockSignals(False)

    def _on_carrier_changed(self) -> None:
        self._populate_components()
        self._refresh_plot()

    def _select_all_components(self) -> None:
        for i in range(self.component_list.count()):
            item = self.component_list.item(i)
            item.setSelected(True)
        self._refresh_plot()

    def _get_selected_component_names(self) -> list[str]:
        return [item.text() for item in self.component_list.selectedItems()]

    def _refresh_plot(self) -> None:
        if self.network is None:
            self._set_empty_state("Load a network to explore time series.")
            return

        component_type = self.component_combo.currentText()
        field = self.field_combo.currentText()
        aggregation = self.aggregation_combo.currentText()
        carrier = self.carrier_combo.currentText()
        selected_names = self._get_selected_component_names()

        if not component_type or not field:
            self._set_empty_state("No valid component type or time series field selected.")
            return

        raw_df = get_time_series_dataframe(self.network, component_type, field)
        if raw_df.empty:
            self._set_empty_state("Selected time series is not available.")
            return

        filtered_df = filter_time_series_dataframe(
            self.network,
            component_type,
            raw_df,
            carrier=carrier,
            component_names=selected_names if selected_names else None,
        )

        if filtered_df.empty:
            if aggregation.lower() != "individual" and not selected_names:
                filtered_df = filter_time_series_dataframe(
                    self.network,
                    component_type,
                    raw_df,
                    carrier=carrier,
                    component_names=None,
                )

        if filtered_df.empty:
            self._set_empty_state("No data matches the current filter selection.")
            return

        plot_df = aggregate_time_series(self.network, component_type, filtered_df, aggregation)
        if plot_df.empty:
            self._set_empty_state("Could not aggregate the selected time series.")
            return

        self._draw_plot(plot_df, component_type, field, aggregation)
        self._update_summary(build_time_series_summary(plot_df))

    def _draw_plot(
        self,
        df,
        component_type: str,
        field: str,
        aggregation: str,
    ) -> None:
        self.plot_card.figure.clear()

        max_series_to_plot = 25
        plot_df = df.iloc[:, :max_series_to_plot]

        n_series = len(plot_df.columns)
        base_height = 7.0
        extra_height = min(n_series * 0.18, 5.0)
        figure_height = base_height + extra_height
        self.plot_card.figure.set_size_inches(12, figure_height)

        ax = self.plot_card.figure.add_subplot(111)

        for column in plot_df.columns:
            ax.plot(plot_df.index, plot_df[column], label=str(column), linewidth=1.5)

        ax.set_title(f"{component_type} — {field} ({aggregation})")
        ax.set_xlabel("Snapshot")
        ax.set_ylabel(field)
        ax.grid(True, alpha=0.3)
        ax.margins(x=0.01)

        if len(plot_df.columns) <= 12:
            ax.legend(loc="best")

        self.plot_card.figure.tight_layout()
        self.plot_card.canvas.draw_idle()

    def _update_summary(self, summary: TimeSeriesSummary) -> None:
        self.snapshots_card.set_value(str(summary.snapshots))
        self.series_card.set_value(str(summary.series_count))
        self.min_card.set_value(self._format_number(summary.value_min))
        self.max_card.set_value(self._format_number(summary.value_max))
        self.mean_card.set_value(self._format_number(summary.value_mean))

    def _set_empty_state(self, message: str) -> None:
        self.plot_card.figure.clear()
        self.plot_card.figure.set_size_inches(12, 7)

        ax = self.plot_card.figure.add_subplot(111)
        ax.text(
            0.5,
            0.5,
            message,
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        ax.set_axis_off()
        self.plot_card.canvas.draw_idle()

        self._update_summary(
            TimeSeriesSummary(
                snapshots=0,
                series_count=0,
                value_min=None,
                value_max=None,
                value_mean=None,
            )
        )

    def _clear_controls(self) -> None:
        self.field_combo.clear()
        self.carrier_combo.clear()
        self.carrier_combo.addItem("All carriers")
        self.component_list.clear()

    @staticmethod
    def _format_number(value: float | None) -> str:
        if value is None:
            return "-"
        return f"{value:.2f}"