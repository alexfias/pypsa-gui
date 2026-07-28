from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd
import pypsa


SCENARIO_NAMES = {
    "Reference",
    "Cheap batteries",
    "High CO₂ price",
    "High demand",
    "No interconnection",
}

MIN_COUNTRIES = 2
MAX_COUNTRIES = 3

BATTERY_COST_FACTOR = 0.5
HIGH_DEMAND_FACTOR = 1.25
HIGH_CO2_PRICE_EUR_PER_TONNE = 200.0


def default_source_network_path() -> Path:
    """
    Return the packaged PyPSA-Eur teaching-network path.

    Expected location:

        pypsa_gui/data/teaching/elec_s_37.nc
    """

    package_directory = Path(__file__).resolve().parents[1]

    return (
        package_directory
        / "data"
        / "teaching"
        / "elec_s_37.nc"
    )


def available_countries(
    source_network_path: Path | str | None = None,
) -> list[str]:
    """
    Return the country codes available in the source network.
    """

    source_path = _resolve_source_path(source_network_path)
    network = pypsa.Network(source_path)

    _validate_country_column(network)

    countries = (
        network.buses["country"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    return sorted(
        country
        for country in countries.unique()
        if country
    )


def build_scenario_network(
    countries: list[str],
    scenario: str,
    source_network_path: Path | str | None = None,
    snapshots: Iterable | None = None,
) -> pypsa.Network:
    """
    Extract selected countries from a PyPSA-Eur network and apply a scenario.

    Parameters
    ----------
    countries:
        Country codes selected by the user, for example
        ``["DE", "DK", "NL"]``.
    scenario:
        One of the names in ``SCENARIO_NAMES``.
    source_network_path:
        Optional alternative source network. When omitted, the packaged
        ``elec_s_37.nc`` network is used.
    snapshots:
        Optional subset of source-network snapshots. When omitted, all
        snapshots are retained.

    Returns
    -------
    pypsa.Network
        An unsolved network containing only the selected countries.
    """

    selected_countries = _normalise_and_validate_inputs(
        countries=countries,
        scenario=scenario,
    )

    source_path = _resolve_source_path(source_network_path)
    source = pypsa.Network(source_path)

    _validate_country_column(source)
    _validate_selected_countries(
        source=source,
        countries=selected_countries,
    )

    selected_snapshots = _validate_snapshots(
        source=source,
        snapshots=snapshots,
    )

    # Network.copy preserves static component data and time series.
    network = source.copy(
        snapshots=selected_snapshots,
    )

    _extract_country_subnetwork(
        network=network,
        countries=selected_countries,
    )

    _apply_scenario(
        network=network,
        scenario=scenario,
    )

    network.name = _build_network_name(
        countries=selected_countries,
        scenario=scenario,
    )

    network.meta = {
        **dict(getattr(network, "meta", {}) or {}),
        "scenario_builder_source": str(source_path),
        "scenario_builder_countries": selected_countries,
        "scenario_builder_scenario": scenario,
    }

    network.consistency_check()

    return network


def _resolve_source_path(
    source_network_path: Path | str | None,
) -> Path:
    if source_network_path is None:
        source_path = default_source_network_path()
    else:
        source_path = Path(source_network_path)

    source_path = source_path.expanduser().resolve()

    if not source_path.exists():
        raise FileNotFoundError(
            "The Scenario Builder source network was not found:\n"
            f"{source_path}\n\n"
            "Place elec_s_37.nc in:\n"
            "pypsa_gui/data/teaching/elec_s_37.nc"
        )

    if not source_path.is_file():
        raise FileNotFoundError(
            f"The Scenario Builder source path is not a file: {source_path}"
        )

    return source_path


def _normalise_and_validate_inputs(
    countries: list[str],
    scenario: str,
) -> list[str]:
    selected_countries = [
        str(country).strip().upper()
        for country in countries
        if str(country).strip()
    ]

    # Remove duplicates while preserving the UI selection order.
    selected_countries = list(
        dict.fromkeys(selected_countries)
    )

    if not MIN_COUNTRIES <= len(selected_countries) <= MAX_COUNTRIES:
        raise ValueError(
            f"Select between {MIN_COUNTRIES} and "
            f"{MAX_COUNTRIES} countries."
        )

    if scenario not in SCENARIO_NAMES:
        available = ", ".join(sorted(SCENARIO_NAMES))

        raise ValueError(
            f"Unknown scenario: {scenario}. "
            f"Available scenarios are: {available}"
        )

    return selected_countries


def _validate_country_column(network: pypsa.Network) -> None:
    if "country" not in network.buses.columns:
        raise ValueError(
            "The source network does not contain a "
            "'country' column in network.buses."
        )


def _validate_selected_countries(
    source: pypsa.Network,
    countries: list[str],
) -> None:
    available = set(
        source.buses["country"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    unavailable = [
        country
        for country in countries
        if country not in available
    ]

    if unavailable:
        raise ValueError(
            "The following countries are unavailable in the "
            f"source network: {', '.join(unavailable)}"
        )


def _validate_snapshots(
    source: pypsa.Network,
    snapshots: Iterable | None,
) -> pd.Index:
    if snapshots is None:
        return source.snapshots

    selected_snapshots = pd.Index(snapshots)

    missing_snapshots = selected_snapshots.difference(
        source.snapshots
    )

    if not missing_snapshots.empty:
        raise ValueError(
            "Some requested snapshots do not exist in the "
            "source network."
        )

    if selected_snapshots.empty:
        raise ValueError(
            "At least one snapshot must be selected."
        )

    return selected_snapshots


def _extract_country_subnetwork(
    network: pypsa.Network,
    countries: list[str],
) -> None:
    """
    Remove components outside the selected countries.

    Components connected to buses are removed before their buses, ensuring
    that the resulting network does not contain references to missing buses.
    """

    bus_country = (
        network.buses["country"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    selected_bus_names = network.buses.index[
        bus_country.isin(countries)
    ]

    selected_bus_set = set(selected_bus_names)

    # One-port components connected through a single "bus" column.
    for component_name, table_name in (
        ("Generator", "generators"),
        ("Load", "loads"),
        ("StorageUnit", "storage_units"),
        ("Store", "stores"),
        ("ShuntImpedance", "shunt_impedances"),
    ):
        table = getattr(network, table_name, None)

        if table is None or table.empty or "bus" not in table.columns:
            continue

        remove_names = table.index[
            ~table["bus"].isin(selected_bus_set)
        ]

        _remove_components(
            network=network,
            component_name=component_name,
            names=remove_names,
        )

    # Branch components may contain bus0, bus1, and potentially additional
    # bus columns. A branch is retained only when every populated bus belongs
    # to the selected subnetwork.
    for component_name, table_name in (
        ("Line", "lines"),
        ("Link", "links"),
        ("Transformer", "transformers"),
    ):
        table = getattr(network, table_name, None)

        if table is None or table.empty:
            continue

        bus_columns = [
            column
            for column in table.columns
            if column.startswith("bus")
        ]

        if not bus_columns:
            continue

        keep_mask = pd.Series(
            True,
            index=table.index,
            dtype=bool,
        )

        for bus_column in bus_columns:
            bus_values = table[bus_column].fillna("").astype(str)

            # Empty optional bus ports do not invalidate a component.
            port_is_valid = (
                bus_values.eq("")
                | bus_values.isin(selected_bus_set)
            )

            keep_mask &= port_is_valid

        remove_names = table.index[~keep_mask]

        _remove_components(
            network=network,
            component_name=component_name,
            names=remove_names,
        )

    remove_buses = network.buses.index[
        ~network.buses.index.isin(selected_bus_set)
    ]

    _remove_components(
        network=network,
        component_name="Bus",
        names=remove_buses,
    )


def _apply_scenario(
    network: pypsa.Network,
    scenario: str,
) -> None:
    if scenario == "Reference":
        return

    if scenario == "Cheap batteries":
        _apply_cheap_batteries(network)
        return

    if scenario == "High CO₂ price":
        _apply_high_co2_price(network)
        return

    if scenario == "High demand":
        _apply_high_demand(network)
        return

    if scenario == "No interconnection":
        _remove_cross_border_branches(network)
        return

    raise ValueError(f"Scenario is not implemented: {scenario}")


def _apply_cheap_batteries(
    network: pypsa.Network,
) -> None:
    """
    Reduce capital costs of components whose carrier contains 'battery'.
    """

    for table_name in (
        "storage_units",
        "stores",
        "links",
    ):
        table = getattr(network, table_name, None)

        if (
            table is None
            or table.empty
            or "carrier" not in table.columns
            or "capital_cost" not in table.columns
        ):
            continue

        battery_mask = (
            table["carrier"]
            .fillna("")
            .astype(str)
            .str.contains(
                "battery",
                case=False,
                regex=False,
            )
        )

        table.loc[battery_mask, "capital_cost"] *= (
            BATTERY_COST_FACTOR
        )


def _apply_high_demand(
    network: pypsa.Network,
) -> None:
    if "p_set" in network.loads.columns:
        network.loads["p_set"] *= HIGH_DEMAND_FACTOR

    if (
        hasattr(network, "loads_t")
        and "p_set" in network.loads_t
        and not network.loads_t.p_set.empty
    ):
        network.loads_t.p_set *= HIGH_DEMAND_FACTOR


def _apply_high_co2_price(
    network: pypsa.Network,
) -> None:
    """
    Add a CO₂-price contribution to generator marginal costs.

    The carrier's ``co2_emissions`` value is divided by generator efficiency.
    Existing marginal costs are retained and the CO₂ cost is added.
    """

    if network.generators.empty:
        return

    if "carrier" not in network.generators.columns:
        return

    if "co2_emissions" not in network.carriers.columns:
        raise ValueError(
            "The source network's carriers do not provide "
            "'co2_emissions' values."
        )

    emissions = (
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

    carbon_cost = (
        HIGH_CO2_PRICE_EUR_PER_TONNE
        * emissions
        / efficiency
    )

    if "marginal_cost" not in network.generators.columns:
        network.generators["marginal_cost"] = 0.0

    network.generators["marginal_cost"] = (
        network.generators["marginal_cost"]
        .fillna(0.0)
        .astype(float)
        + carbon_cost
    )


def _remove_cross_border_branches(
    network: pypsa.Network,
) -> None:
    bus_country = (
        network.buses["country"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    for component_name, table_name in (
        ("Line", "lines"),
        ("Link", "links"),
        ("Transformer", "transformers"),
    ):
        table = getattr(network, table_name, None)

        if (
            table is None
            or table.empty
            or "bus0" not in table.columns
            or "bus1" not in table.columns
        ):
            continue

        country_0 = table["bus0"].map(bus_country)
        country_1 = table["bus1"].map(bus_country)

        cross_border_mask = (
            country_0.notna()
            & country_1.notna()
            & country_0.ne(country_1)
        )

        _remove_components(
            network=network,
            component_name=component_name,
            names=table.index[cross_border_mask],
        )


def _remove_components(
    network: pypsa.Network,
    component_name: str,
    names: Iterable,
) -> None:
    """
    Remove components one at a time for compatibility across PyPSA versions.
    """

    for name in list(names):
        network.remove(component_name, name)


def _build_network_name(
    countries: list[str],
    scenario: str,
) -> str:
    country_part = "-".join(countries)

    scenario_part = (
        scenario
        .lower()
        .replace("₂", "2")
        .replace(" ", "-")
    )

    return f"{country_part}-{scenario_part}"