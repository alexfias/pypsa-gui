from __future__ import annotations

import pandas as pd
import pypsa
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class CapacitiesPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.network: pypsa.Network | None = None

        self.view_combo = QComboBox()
        self.view_combo.addItems(
            [
                "Installed capacity per node",
                "Generation per node",
            ]
        )
        self.view_combo.currentIndexChanged.connect(self._redraw)

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["MW", "GW"])
        self.unit_combo.currentIndexChanged.connect(self._redraw)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(
            [
                "Sort by total descending",
                "Sort alphabetically",
            ]
        )
        self.sort_combo.currentIndexChanged.connect(self._redraw)

        self.top_n_combo = QComboBox()
        self.top_n_combo.addItems(["All", "5", "10", "20", "30"])
        self.top_n_combo.currentIndexChanged.connect(self._redraw)

        self.normalize_checkbox = QCheckBox("Show shares")
        self.normalize_checkbox.stateChanged.connect(self._redraw)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("View:"))
        controls_layout.addWidget(self.view_combo)
        controls_layout.addWidget(QLabel("Unit:"))
        controls_layout.addWidget(self.unit_combo)
        controls_layout.addWidget(QLabel("Order:"))
        controls_layout.addWidget(self.sort_combo)
        controls_layout.addWidget(QLabel("Top N:"))
        controls_layout.addWidget(self.top_n_combo)
        controls_layout.addWidget(self.normalize_checkbox)
        controls_layout.addStretch()

        self.figure = Figure(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)

        layout = QVBoxLayout(self)
        layout.addLayout(controls_layout)
        layout.addWidget(self.canvas)

        self._redraw()

    def set_network(self, network: pypsa.Network | None) -> None:
        self.network = network
        self._redraw()

    def _redraw(self) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        if self.network is None:
            ax.text(
                0.5,
                0.5,
                "No network loaded.",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_axis_off()
            self.canvas.draw()
            return

        view_name = self.view_combo.currentText()

        if view_name == "Installed capacity per node":
            df = self._compute_capacity_by_bus_and_carrier()
            title = "Installed Generation Capacity per Node"
            ylabel = "Capacity"
        else:
            df = self._compute_generation_by_bus_and_carrier()
            title = "Generation per Node"
            ylabel = "Generation"

        if df.empty:
            ax.text(
                0.5,
                0.5,
                "No data available for this view.",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_axis_off()
            self.canvas.draw()
            return

        df = self._prepare_plot_dataframe(df)

        if df.empty:
            ax.text(
                0.5,
                0.5,
                "No plottable data available.",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_axis_off()
            self.canvas.draw()
            return

        if self.normalize_checkbox.isChecked():
            row_sums = df.sum(axis=1).replace(0.0, pd.NA)
            df = df.div(row_sums, axis=0).fillna(0.0)
            ylabel = "Share"
            title += " (Shares)"

        unit_label, scale_factor = self._get_unit_scale(view_name)
        if not self.normalize_checkbox.isChecked():
            df = df / scale_factor
            ylabel = f"{ylabel} [{unit_label}]"

        carrier_colors = self._carrier_colors(df.columns)

        df.plot(
            kind="bar",
            stacked=True,
            ax=ax,
            color=[carrier_colors.get(str(col).lower(), "lightgray") for col in df.columns],
            width=0.85,
        )

        ax.set_title(title, fontsize=11)
        ax.set_xlabel("Node")
        ax.set_ylabel(ylabel)
        ax.tick_params(axis="x", labelrotation=45)

        if self.normalize_checkbox.isChecked():
            ax.set_ylim(0.0, 1.0)

        ax.legend(title="Carrier", fontsize=8, title_fontsize=9)
        self.figure.subplots_adjust(bottom=0.22, top=0.9)
        self.canvas.draw()

    def _compute_capacity_by_bus_and_carrier(self) -> pd.DataFrame:
        if self.network is None or self.network.generators.empty:
            return pd.DataFrame()

        generators = self.network.generators.copy()

        if "bus" not in generators.columns or "carrier" not in generators.columns:
            return pd.DataFrame()

        capacity_column = "p_nom_opt" if "p_nom_opt" in generators.columns else "p_nom"

        df = (
            generators.groupby(["bus", "carrier"])[capacity_column]
            .sum()
            .unstack(fill_value=0.0)
        )

        return self._reorder_and_group_carriers(df)

    def _compute_generation_by_bus_and_carrier(self) -> pd.DataFrame:
        if self.network is None:
            return pd.DataFrame()

        if self.network.generators.empty:
            return pd.DataFrame()

        if not hasattr(self.network, "generators_t"):
            return pd.DataFrame()

        if not hasattr(self.network.generators_t, "p"):
            return pd.DataFrame()

        dispatch = self.network.generators_t.p
        if dispatch.empty:
            return pd.DataFrame()

        available_generators = self.network.generators.index.intersection(dispatch.columns)
        if available_generators.empty:
            return pd.DataFrame()

        total_generation = dispatch[available_generators].sum(axis=0)

        meta = self.network.generators.loc[available_generators, ["bus", "carrier"]].copy()
        meta["generation"] = total_generation

        df = (
            meta.groupby(["bus", "carrier"])["generation"]
            .sum()
            .unstack(fill_value=0.0)
        )

        return self._reorder_and_group_carriers(df)

    def _prepare_plot_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        df = df.loc[df.sum(axis=1) > 0.0].copy()
        if df.empty:
            return df

        sort_mode = self.sort_combo.currentText()
        if sort_mode == "Sort by total descending":
            df = df.loc[df.sum(axis=1).sort_values(ascending=False).index]
        else:
            df = df.sort_index()

        top_n_text = self.top_n_combo.currentText()
        if top_n_text != "All":
            top_n = int(top_n_text)
            df = df.head(top_n)

        return df

    def _reorder_and_group_carriers(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        preferred_order = [
            "solar",
            "onwind",
            "offwind",
            "wind",
            "gas",
            "hydro",
            "ror",
            "biomass",
            "coal",
            "lignite",
            "nuclear",
        ]

        normalized_columns = {str(col).lower(): col for col in df.columns}
        selected_columns = [normalized_columns[c] for c in preferred_order if c in normalized_columns]
        other_columns = [col for col in df.columns if col not in selected_columns]

        result = df[selected_columns].copy() if selected_columns else pd.DataFrame(index=df.index)

        if other_columns:
            result["other"] = df[other_columns].sum(axis=1)

        return result

    def _carrier_colors(self, carriers) -> dict[str, str]:
        base = {
            "solar": "gold",
            "onwind": "skyblue",
            "offwind": "dodgerblue",
            "wind": "steelblue",
            "gas": "tomato",
            "hydro": "mediumseagreen",
            "ror": "seagreen",
            "biomass": "olive",
            "coal": "dimgray",
            "lignite": "saddlebrown",
            "nuclear": "purple",
            "other": "lightgray",
        }
        return {str(carrier).lower(): base.get(str(carrier).lower(), "lightgray") for carrier in carriers}

    def _get_unit_scale(self, view_name: str) -> tuple[str, float]:
        if self.normalize_checkbox.isChecked():
            return "", 1.0

        unit = self.unit_combo.currentText()

        if view_name == "Installed capacity per node":
            if unit == "GW":
                return "GW", 1e3
            return "MW", 1.0

        if unit == "GW":
            return "GWh", 1e3
        return "MWh", 1.0