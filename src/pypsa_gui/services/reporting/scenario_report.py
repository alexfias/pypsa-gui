from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import pypsa
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


RENEWABLE_CARRIER_KEYWORDS = (
    "solar",
    "wind",
    "onwind",
    "offwind",
    "hydro",
    "ror",
    "geothermal",
)


@dataclass(frozen=True)
class ScenarioReportMetrics:
    objective_eur: float | None
    demand_mwh: float
    generation_mwh: float
    renewable_generation_mwh: float
    renewable_share_percent: float | None
    emissions_tonnes: float | None
    generator_capacity_mw: pd.Series
    annual_generation_mwh: pd.Series
    storage_power_capacity_mw: pd.Series
    storage_energy_capacity_mwh: pd.Series


def network_has_results(network: pypsa.Network) -> bool:
    """
    Return True when the network appears to contain optimisation results.
    """

    if network is None:
        return False

    generators_t = getattr(network, "generators_t", None)

    if generators_t is None:
        return False

    dispatch = getattr(generators_t, "p", None)

    if dispatch is None or dispatch.empty:
        return False

    return dispatch.notna().any().any()


def generate_scenario_report(
    network: pypsa.Network,
    output_path: Path | str,
) -> Path:
    """
    Generate a PDF analysis report for a solved PyPSA network.

    Parameters
    ----------
    network:
        Solved PyPSA network.
    output_path:
        Destination PDF path.

    Returns
    -------
    pathlib.Path
        Path of the generated report.
    """

    if not network_has_results(network):
        raise ValueError(
            "The network does not contain optimisation results. "
            "Solve the network before generating a report."
        )

    report_path = Path(output_path).expanduser()

    if report_path.suffix.lower() != ".pdf":
        report_path = report_path.with_suffix(".pdf")

    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    metrics = _calculate_metrics(network)

    document = SimpleDocTemplate(
        str(report_path),
        pagesize=A4,
        rightMargin=1.7 * cm,
        leftMargin=1.7 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title=f"{_network_name(network)} - Analysis Report",
        author="PyPSA GUI",
    )

    story: list[Any] = []
    styles = _report_styles()

    story.extend(
        _build_title_section(
            network=network,
            styles=styles,
        )
    )

    story.extend(
        _build_scenario_section(
            network=network,
            styles=styles,
        )
    )

    story.extend(
        _build_key_results_section(
            metrics=metrics,
            styles=styles,
        )
    )

    story.append(PageBreak())

    story.extend(
        _build_capacity_section(
            metrics=metrics,
            styles=styles,
        )
    )

    story.extend(
        _build_generation_section(
            metrics=metrics,
            styles=styles,
        )
    )

    story.append(PageBreak())

    story.extend(
        _build_storage_section(
            metrics=metrics,
            styles=styles,
        )
    )

    story.extend(
        _build_interpretation_section(
            network=network,
            metrics=metrics,
            styles=styles,
        )
    )

    document.build(
        story,
        onFirstPage=_draw_page_footer,
        onLaterPages=_draw_page_footer,
    )

    return report_path


def _calculate_metrics(
    network: pypsa.Network,
) -> ScenarioReportMetrics:
    weights = _snapshot_weights(network)

    demand_mwh = _annual_demand(
        network=network,
        weights=weights,
    )

    annual_generation = _annual_generation_by_carrier(
        network=network,
        weights=weights,
    )

    generation_mwh = float(
        annual_generation.sum()
    )

    renewable_mask = annual_generation.index.to_series().apply(
        _is_renewable_carrier
    )

    renewable_generation_mwh = float(
        annual_generation.loc[renewable_mask].sum()
    )

    if generation_mwh > 0.0:
        renewable_share_percent = (
            100.0
            * renewable_generation_mwh
            / generation_mwh
        )
    else:
        renewable_share_percent = None

    return ScenarioReportMetrics(
        objective_eur=_network_objective(network),
        demand_mwh=demand_mwh,
        generation_mwh=generation_mwh,
        renewable_generation_mwh=renewable_generation_mwh,
        renewable_share_percent=renewable_share_percent,
        emissions_tonnes=_annual_generator_emissions(
            network=network,
            weights=weights,
        ),
        generator_capacity_mw=_generator_capacity_by_carrier(
            network
        ),
        annual_generation_mwh=annual_generation,
        storage_power_capacity_mw=_storage_power_capacity(
            network
        ),
        storage_energy_capacity_mwh=_storage_energy_capacity(
            network
        ),
    )


def _snapshot_weights(
    network: pypsa.Network,
) -> pd.Series:
    snapshot_weightings = getattr(
        network,
        "snapshot_weightings",
        None,
    )

    if snapshot_weightings is None:
        return pd.Series(
            1.0,
            index=network.snapshots,
            dtype=float,
        )

    if isinstance(snapshot_weightings, pd.Series):
        return (
            snapshot_weightings
            .reindex(network.snapshots)
            .fillna(1.0)
            .astype(float)
        )

    preferred_columns = (
        "generators",
        "objective",
        "stores",
    )

    for column in preferred_columns:
        if column in snapshot_weightings.columns:
            return (
                snapshot_weightings[column]
                .reindex(network.snapshots)
                .fillna(1.0)
                .astype(float)
            )

    return pd.Series(
        1.0,
        index=network.snapshots,
        dtype=float,
    )


def _annual_demand(
    network: pypsa.Network,
    weights: pd.Series,
) -> float:
    loads_t = getattr(network, "loads_t", None)

    if loads_t is not None:
        p_set = getattr(loads_t, "p_set", None)

        if p_set is not None and not p_set.empty:
            return float(
                p_set
                .multiply(weights, axis=0)
                .sum()
                .sum()
            )

        p = getattr(loads_t, "p", None)

        if p is not None and not p.empty:
            return float(
                p
                .multiply(weights, axis=0)
                .sum()
                .sum()
            )

    if (
        not network.loads.empty
        and "p_set" in network.loads.columns
    ):
        static_demand = float(
            network.loads["p_set"]
            .fillna(0.0)
            .sum()
        )

        return static_demand * float(weights.sum())

    return 0.0


def _annual_generation_by_carrier(
    network: pypsa.Network,
    weights: pd.Series,
) -> pd.Series:
    if network.generators.empty:
        return pd.Series(dtype=float)

    dispatch = getattr(
        network.generators_t,
        "p",
        pd.DataFrame(),
    )

    if dispatch.empty:
        return pd.Series(dtype=float)

    generator_energy = (
        dispatch
        .multiply(weights, axis=0)
        .sum(axis=0)
        .clip(lower=0.0)
    )

    carriers = (
        network.generators["carrier"]
        .reindex(generator_energy.index)
        .fillna("Unspecified")
        .astype(str)
    )

    result = (
        generator_energy
        .groupby(carriers)
        .sum()
        .sort_values(ascending=False)
    )

    return result[result.abs() > 1e-6]


def _generator_capacity_by_carrier(
    network: pypsa.Network,
) -> pd.Series:
    if network.generators.empty:
        return pd.Series(dtype=float)

    capacity = _optimised_or_nominal(
        table=network.generators,
        optimised_column="p_nom_opt",
        nominal_column="p_nom",
    )

    carriers = (
        network.generators["carrier"]
        .fillna("Unspecified")
        .astype(str)
    )

    result = (
        capacity
        .groupby(carriers)
        .sum()
        .sort_values(ascending=False)
    )

    return result[result.abs() > 1e-6]


def _storage_power_capacity(
    network: pypsa.Network,
) -> pd.Series:
    entries: list[pd.Series] = []

    if not network.storage_units.empty:
        storage_unit_capacity = _optimised_or_nominal(
            table=network.storage_units,
            optimised_column="p_nom_opt",
            nominal_column="p_nom",
        )

        storage_unit_carriers = (
            network.storage_units["carrier"]
            .fillna("Storage unit")
            .astype(str)
        )

        entries.append(
            storage_unit_capacity.groupby(
                storage_unit_carriers
            ).sum()
        )

    if not network.links.empty:
        link_capacity = _optimised_or_nominal(
            table=network.links,
            optimised_column="p_nom_opt",
            nominal_column="p_nom",
        )

        link_carriers = (
            network.links["carrier"]
            .fillna("Link")
            .astype(str)
        )

        storage_link_mask = link_carriers.str.contains(
            "battery|electroly|fuel cell|hydrogen",
            case=False,
            regex=True,
        )

        if storage_link_mask.any():
            entries.append(
                link_capacity.loc[storage_link_mask]
                .groupby(
                    link_carriers.loc[storage_link_mask]
                )
                .sum()
            )

    if not entries:
        return pd.Series(dtype=float)

    result = (
        pd.concat(entries)
        .groupby(level=0)
        .sum()
        .sort_values(ascending=False)
    )

    return result[result.abs() > 1e-6]


def _storage_energy_capacity(
    network: pypsa.Network,
) -> pd.Series:
    entries: list[pd.Series] = []

    if not network.storage_units.empty:
        power_capacity = _optimised_or_nominal(
            table=network.storage_units,
            optimised_column="p_nom_opt",
            nominal_column="p_nom",
        )

        if "max_hours" in network.storage_units.columns:
            max_hours = (
                network.storage_units["max_hours"]
                .fillna(0.0)
                .astype(float)
            )
        else:
            max_hours = pd.Series(
                0.0,
                index=network.storage_units.index,
            )

        energy_capacity = power_capacity * max_hours

        carriers = (
            network.storage_units["carrier"]
            .fillna("Storage unit")
            .astype(str)
        )

        entries.append(
            energy_capacity.groupby(carriers).sum()
        )

    if not network.stores.empty:
        store_capacity = _optimised_or_nominal(
            table=network.stores,
            optimised_column="e_nom_opt",
            nominal_column="e_nom",
        )

        carriers = (
            network.stores["carrier"]
            .fillna("Store")
            .astype(str)
        )

        entries.append(
            store_capacity.groupby(carriers).sum()
        )

    if not entries:
        return pd.Series(dtype=float)

    result = (
        pd.concat(entries)
        .groupby(level=0)
        .sum()
        .sort_values(ascending=False)
    )

    return result[result.abs() > 1e-6]


def _annual_generator_emissions(
    network: pypsa.Network,
    weights: pd.Series,
) -> float | None:
    if network.generators.empty:
        return None

    if "carrier" not in network.generators.columns:
        return None

    if "co2_emissions" not in network.carriers.columns:
        return None

    dispatch = getattr(
        network.generators_t,
        "p",
        pd.DataFrame(),
    )

    if dispatch.empty:
        return None

    generator_energy = (
        dispatch
        .multiply(weights, axis=0)
        .sum(axis=0)
        .clip(lower=0.0)
    )

    carrier_emissions = (
        network.generators["carrier"]
        .map(network.carriers["co2_emissions"])
        .fillna(0.0)
        .astype(float)
    )

    if "efficiency" in network.generators.columns:
        efficiency = (
            network.generators["efficiency"]
            .replace(0.0, pd.NA)
            .fillna(1.0)
            .astype(float)
        )
    else:
        efficiency = pd.Series(
            1.0,
            index=network.generators.index,
        )

    emissions = (
        generator_energy
        .reindex(network.generators.index)
        .fillna(0.0)
        * carrier_emissions
        / efficiency
    )

    return float(emissions.sum())


def _optimised_or_nominal(
    table: pd.DataFrame,
    optimised_column: str,
    nominal_column: str,
) -> pd.Series:
    if optimised_column in table.columns:
        optimised = pd.to_numeric(
            table[optimised_column],
            errors="coerce",
        )

        if optimised.notna().any():
            nominal = pd.to_numeric(
                table.get(
                    nominal_column,
                    pd.Series(0.0, index=table.index),
                ),
                errors="coerce",
            ).fillna(0.0)

            return optimised.fillna(nominal)

    if nominal_column in table.columns:
        return pd.to_numeric(
            table[nominal_column],
            errors="coerce",
        ).fillna(0.0)

    return pd.Series(
        0.0,
        index=table.index,
        dtype=float,
    )


def _network_objective(
    network: pypsa.Network,
) -> float | None:
    objective = getattr(
        network,
        "objective",
        None,
    )

    if objective is not None:
        try:
            return float(objective)
        except (TypeError, ValueError):
            pass

    model = getattr(
        network,
        "model",
        None,
    )

    model_objective = getattr(
        model,
        "objective",
        None,
    )

    value = getattr(
        model_objective,
        "value",
        None,
    )

    if value is not None:
        try:
            return float(value)
        except (TypeError, ValueError):
            pass

    meta = dict(
        getattr(network, "meta", {}) or {}
    )

    for key in (
        "objective",
        "objective_value",
        "system_cost",
    ):
        if key in meta:
            try:
                return float(meta[key])
            except (TypeError, ValueError):
                continue

    return None


def _is_renewable_carrier(
    carrier: str,
) -> bool:
    normalised = str(carrier).strip().casefold()

    return any(
        keyword in normalised
        for keyword in RENEWABLE_CARRIER_KEYWORDS
    )


def _build_title_section(
    network: pypsa.Network,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    return [
        Paragraph(
            "PyPSA GUI Scenario Analysis Report",
            styles["ReportTitle"],
        ),
        Spacer(1, 0.2 * cm),
        Paragraph(
            _network_name(network),
            styles["ReportSubtitle"],
        ),
        Spacer(1, 0.7 * cm),
    ]


def _build_scenario_section(
    network: pypsa.Network,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    meta = dict(
        getattr(network, "meta", {}) or {}
    )

    countries = meta.get(
        "scenario_builder_countries",
        _countries_from_network(network),
    )

    if isinstance(countries, (list, tuple, set)):
        country_text = ", ".join(
            str(country)
            for country in countries
        )
    else:
        country_text = str(countries or "Not specified")

    rows = [
        ["Property", "Value"],
        ["Countries", country_text],
        [
            "Scenario",
            str(
                meta.get(
                    "scenario_builder_scenario",
                    "Not specified",
                )
            ),
        ],
        [
            "Snapshots",
            f"{len(network.snapshots):,}",
        ],
        [
            "Generators",
            f"{len(network.generators):,}",
        ],
        [
            "Buses",
            f"{len(network.buses):,}",
        ],
        [
            "Generated",
            datetime.now().strftime(
                "%Y-%m-%d %H:%M"
            ),
        ],
    ]

    table = _styled_table(
        rows,
        column_widths=[
            5.0 * cm,
            11.5 * cm,
        ],
    )

    return [
        Paragraph(
            "Scenario overview",
            styles["Heading1"],
        ),
        table,
        Spacer(1, 0.6 * cm),
    ]


def _build_key_results_section(
    metrics: ScenarioReportMetrics,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    rows = [
        ["Indicator", "Result"],
        [
            "Total system cost",
            _format_currency(metrics.objective_eur),
        ],
        [
            "Annual electricity demand",
            _format_energy(metrics.demand_mwh),
        ],
        [
            "Annual generator output",
            _format_energy(metrics.generation_mwh),
        ],
        [
            "Renewable generation",
            _format_energy(
                metrics.renewable_generation_mwh
            ),
        ],
        [
            "Renewable generation share",
            _format_percent(
                metrics.renewable_share_percent
            ),
        ],
        [
            "Generator CO2 emissions",
            _format_emissions(
                metrics.emissions_tonnes
            ),
        ],
    ]

    return [
        Paragraph(
            "Key results",
            styles["Heading1"],
        ),
        _styled_table(
            rows,
            column_widths=[
                9.0 * cm,
                7.5 * cm,
            ],
        ),
        Spacer(1, 0.5 * cm),
    ]


def _build_capacity_section(
    metrics: ScenarioReportMetrics,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    elements: list[Any] = [
        Paragraph(
            "Installed generation capacity",
            styles["Heading1"],
        )
    ]

    if metrics.generator_capacity_mw.empty:
        elements.append(
            Paragraph(
                "No generator-capacity results are available.",
                styles["BodyText"],
            )
        )
        return elements

    figure = _bar_chart(
        values=metrics.generator_capacity_mw / 1_000.0,
        title="Generation capacity by technology",
        axis_label="Capacity [GW]",
    )

    elements.extend(
        [
            Image(
                figure,
                width=16.0 * cm,
                height=8.5 * cm,
            ),
            Spacer(1, 0.3 * cm),
            _series_table(
                metrics.generator_capacity_mw,
                value_heading="Capacity",
                formatter=_format_power,
            ),
        ]
    )

    return elements


def _build_generation_section(
    metrics: ScenarioReportMetrics,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    elements: list[Any] = [
        Spacer(1, 0.7 * cm),
        Paragraph(
            "Annual electricity generation",
            styles["Heading1"],
        ),
    ]

    if metrics.annual_generation_mwh.empty:
        elements.append(
            Paragraph(
                "No generator-dispatch results are available.",
                styles["BodyText"],
            )
        )
        return elements

    figure = _bar_chart(
        values=metrics.annual_generation_mwh / 1_000_000.0,
        title="Annual generation by technology",
        axis_label="Generation [TWh]",
    )

    elements.extend(
        [
            Image(
                figure,
                width=16.0 * cm,
                height=8.5 * cm,
            ),
            Spacer(1, 0.3 * cm),
            _series_table(
                metrics.annual_generation_mwh,
                value_heading="Generation",
                formatter=_format_energy,
            ),
        ]
    )

    return elements


def _build_storage_section(
    metrics: ScenarioReportMetrics,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    elements: list[Any] = [
        Paragraph(
            "Storage and conversion technologies",
            styles["Heading1"],
        )
    ]

    if metrics.storage_power_capacity_mw.empty:
        elements.append(
            Paragraph(
                "No storage power or conversion capacity was built.",
                styles["BodyText"],
            )
        )
    else:
        elements.extend(
            [
                Paragraph(
                    "Power capacity",
                    styles["Heading2"],
                ),
                _series_table(
                    metrics.storage_power_capacity_mw,
                    value_heading="Power capacity",
                    formatter=_format_power,
                ),
                Spacer(1, 0.5 * cm),
            ]
        )

    if metrics.storage_energy_capacity_mwh.empty:
        elements.append(
            Paragraph(
                "No storage energy capacity was built.",
                styles["BodyText"],
            )
        )
    else:
        elements.extend(
            [
                Paragraph(
                    "Energy capacity",
                    styles["Heading2"],
                ),
                _series_table(
                    metrics.storage_energy_capacity_mwh,
                    value_heading="Energy capacity",
                    formatter=_format_energy,
                ),
            ]
        )

    elements.append(
        Spacer(1, 0.8 * cm)
    )

    return elements


def _build_interpretation_section(
    network: pypsa.Network,
    metrics: ScenarioReportMetrics,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    dominant_capacity = _largest_entry_name(
        metrics.generator_capacity_mw
    )

    dominant_generation = _largest_entry_name(
        metrics.annual_generation_mwh
    )

    observations = [
        (
            "Largest generation capacity: "
            f"<b>{dominant_capacity}</b>."
        ),
        (
            "Largest annual generator contribution: "
            f"<b>{dominant_generation}</b>."
        ),
        (
            "Renewable generation share: "
            f"<b>{_format_percent(metrics.renewable_share_percent)}</b>."
        ),
    ]

    questions = [
        "Why does the technology with the highest capacity not necessarily "
        "provide the most annual electricity?",
        "What role do batteries and hydrogen storage play in this scenario?",
        "Which technology would be affected most strongly by changing the "
        "scenario assumption?",
        "Which result is driven by the selected country and which is driven "
        "by the scenario?",
        "What limitations should be considered when interpreting this model?",
    ]

    elements: list[Any] = [
        Paragraph(
            "Interpretation",
            styles["Heading1"],
        ),
        Paragraph(
            "Automatically identified observations",
            styles["Heading2"],
        ),
    ]

    for observation in observations:
        elements.append(
            Paragraph(
                f"- {observation}",
                styles["BodyText"],
            )
        )

    elements.extend(
        [
            Spacer(1, 0.5 * cm),
            Paragraph(
                "Questions for analysis",
                styles["Heading2"],
            ),
        ]
    )

    for number, question in enumerate(
        questions,
        start=1,
    ):
        elements.append(
            Paragraph(
                f"{number}. {question}",
                styles["BodyText"],
            )
        )
        elements.append(
            Spacer(1, 0.12 * cm)
        )

    return elements


def _bar_chart(
    values: pd.Series,
    title: str,
    axis_label: str,
) -> BytesIO:
    plotted_values = (
        values
        .dropna()
        .sort_values(ascending=True)
    )

    figure_height = max(
        4.0,
        0.45 * len(plotted_values) + 1.8,
    )

    figure, axis = plt.subplots(
        figsize=(8.0, figure_height)
    )

    axis.barh(
        plotted_values.index.astype(str),
        plotted_values.values,
    )

    axis.set_title(title)
    axis.set_xlabel(axis_label)
    axis.grid(
        axis="x",
        alpha=0.25,
    )

    figure.tight_layout()

    image_buffer = BytesIO()

    figure.savefig(
        image_buffer,
        format="png",
        dpi=160,
        bbox_inches="tight",
    )

    plt.close(figure)

    image_buffer.seek(0)

    return image_buffer


def _series_table(
    values: pd.Series,
    value_heading: str,
    formatter,
) -> Table:
    rows = [
        ["Technology", value_heading]
    ]

    for name, value in values.items():
        rows.append(
            [
                str(name),
                formatter(float(value)),
            ]
        )

    return _styled_table(
        rows,
        column_widths=[
            9.5 * cm,
            7.0 * cm,
        ],
    )


def _styled_table(
    rows: list[list[Any]],
    column_widths: list[float],
) -> Table:
    table = Table(
        rows,
        colWidths=column_widths,
        repeatRows=1,
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#E8EDF3"),
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#1F2933"),
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold",
                ),
                (
                    "FONTNAME",
                    (0, 1),
                    (-1, -1),
                    "Helvetica",
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    9,
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.35,
                    colors.HexColor("#B8C2CC"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    return table


def _report_styles() -> dict[str, ParagraphStyle]:
    sample_styles = getSampleStyleSheet()

    styles = {
        "ReportTitle": ParagraphStyle(
            "ReportTitle",
            parent=sample_styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=21,
            leading=25,
            alignment=TA_CENTER,
            spaceAfter=5,
        ),
        "ReportSubtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=sample_styles["Heading2"],
            fontName="Helvetica",
            fontSize=13,
            leading=16,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#4B5563"),
        ),
        "Heading1": ParagraphStyle(
            "ReportHeading1",
            parent=sample_styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            spaceBefore=5,
            spaceAfter=8,
        ),
        "Heading2": ParagraphStyle(
            "ReportHeading2",
            parent=sample_styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            spaceBefore=4,
            spaceAfter=5,
        ),
        "BodyText": ParagraphStyle(
            "ReportBodyText",
            parent=sample_styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            spaceAfter=4,
        ),
    }

    return styles


def _draw_page_footer(
    canvas,
    document,
) -> None:
    canvas.saveState()

    canvas.setStrokeColor(
        colors.HexColor("#D1D5DB")
    )

    canvas.line(
        1.7 * cm,
        1.25 * cm,
        A4[0] - 1.7 * cm,
        1.25 * cm,
    )

    canvas.setFont(
        "Helvetica",
        8,
    )

    canvas.setFillColor(
        colors.HexColor("#6B7280")
    )

    canvas.drawString(
        1.7 * cm,
        0.85 * cm,
        "Generated by PyPSA GUI",
    )

    canvas.drawRightString(
        A4[0] - 1.7 * cm,
        0.85 * cm,
        f"Page {document.page}",
    )

    canvas.restoreState()


def _network_name(
    network: pypsa.Network,
) -> str:
    name = getattr(
        network,
        "name",
        None,
    )

    if name:
        return str(name)

    return "PyPSA network"


def _countries_from_network(
    network: pypsa.Network,
) -> str:
    if (
        network.buses.empty
        or "country" not in network.buses.columns
    ):
        return "Not specified"

    countries = sorted(
        country
        for country in (
            network.buses["country"]
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
        )
        if country
    )

    return ", ".join(countries)


def _largest_entry_name(
    values: pd.Series,
) -> str:
    if values.empty:
        return "none"

    return str(values.idxmax())


def _format_currency(
    value: float | None,
) -> str:
    if value is None:
        return "Not available"

    absolute_value = abs(value)

    if absolute_value >= 1_000_000_000:
        return f"EUR {value / 1_000_000_000:,.2f} billion"

    if absolute_value >= 1_000_000:
        return f"EUR {value / 1_000_000:,.2f} million"

    return f"EUR {value:,.0f}"


def _format_power(
    value_mw: float,
) -> str:
    if abs(value_mw) >= 1_000.0:
        return f"{value_mw / 1_000.0:,.2f} GW"

    return f"{value_mw:,.1f} MW"


def _format_energy(
    value_mwh: float,
) -> str:
    if abs(value_mwh) >= 1_000_000.0:
        return f"{value_mwh / 1_000_000.0:,.2f} TWh"

    if abs(value_mwh) >= 1_000.0:
        return f"{value_mwh / 1_000.0:,.2f} GWh"

    return f"{value_mwh:,.1f} MWh"


def _format_emissions(
    value_tonnes: float | None,
) -> str:
    if value_tonnes is None:
        return "Not available"

    if abs(value_tonnes) >= 1_000_000.0:
        return f"{value_tonnes / 1_000_000.0:,.2f} Mt CO2"

    if abs(value_tonnes) >= 1_000.0:
        return f"{value_tonnes / 1_000.0:,.2f} kt CO2"

    return f"{value_tonnes:,.1f} t CO2"


def _format_percent(
    value: float | None,
) -> str:
    if value is None:
        return "Not available"

    return f"{value:,.1f}%"