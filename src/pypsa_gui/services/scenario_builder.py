from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd
import pypsa

from pypsa_gui.models.scenario_definition import (
    CO2Policy,
    ScenarioDefinition,
    TechnologySettings,
)


SCENARIO_NAMES = {
    "Reference",
    "Cheap batteries",
    "High CO₂ price",
    "High demand",
    "No interconnection",
}

MIN_COUNTRIES = 1
MAX_COUNTRIES = 3

BATTERY_COST_FACTOR = 0.5
HIGH_DEMAND_FACTOR = 1.25
HIGH_CO2_PRICE_EUR_PER_TONNE = 200.0


# ------------------------------------------------------------------
# Standard storage assumptions
# ------------------------------------------------------------------

BATTERY_MAX_HOURS = 4.0
BATTERY_CHARGE_EFFICIENCY = 0.95
BATTERY_DISCHARGE_EFFICIENCY = 0.95
BATTERY_STANDING_LOSS = 0.001
BATTERY_CAPITAL_COST_EUR_PER_MW = 220_000.0

HYDROGEN_ELECTROLYSER_EFFICIENCY = 0.70
HYDROGEN_FUEL_CELL_EFFICIENCY = 0.50
HYDROGEN_STORE_STANDING_LOSS = 0.0001

ELECTROLYSER_CAPITAL_COST_EUR_PER_MW = 500_000.0
FUEL_CELL_CAPITAL_COST_EUR_PER_MW = 800_000.0
HYDROGEN_STORE_CAPITAL_COST_EUR_PER_MWH = 10_000.0


# ------------------------------------------------------------------
# Technology mapping
# ------------------------------------------------------------------

TECHNOLOGY_CARRIERS: dict[str, set[str]] = {
    "solar": {
        "solar",
    },
    "onshore_wind": {
        "onwind",
        "onshore wind",
    },
    "offshore_wind": {
        "offwind",
        "offwind-ac",
        "offwind-dc",
        "offshore wind",
    },
    "gas": {
        "gas",
        "ocgt",
        "ccgt",
    },
    "coal": {
        "coal",
        "lignite",
    },
    "nuclear": {
        "nuclear",
    },
    "hydro": {
        "hydro",
        "ror",
        "phs",
        "reservoir",
    },
    "battery": {
        "battery",
    },
    "hydrogen": {
        "hydrogen",
        "h2",
        "electrolyser",
        "electrolyzer",
        "fuel cell",
    },
}


COMPONENT_TECHNOLOGY_SPECS = (
    (
        "Generator",
        "generators",
        "p_nom_extendable",
    ),
    (
        "StorageUnit",
        "storage_units",
        "p_nom_extendable",
    ),
    (
        "Store",
        "stores",
        "e_nom_extendable",
    ),
    (
        "Link",
        "links",
        "p_nom_extendable",
    ),
)


# ------------------------------------------------------------------
# Source network
# ------------------------------------------------------------------

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


# ------------------------------------------------------------------
# Public builder
# ------------------------------------------------------------------

def build_scenario_network(
    definition: ScenarioDefinition,
    source_network_path: Path | str | None = None,
    snapshots: Iterable | None = None,
) -> pypsa.Network:
    """
    Build a teaching scenario from the packaged PyPSA-Eur network.

    The builder:

    1. loads the source network;
    2. selects the requested countries;
    3. adds standard battery and hydrogen investment options;
    4. applies the selected preset;
    5. applies custom demand, technology, cost, and CO₂ settings;
    6. optionally removes cross-border interconnections.

    Parameters
    ----------
    definition:
        Complete Scenario Builder configuration.
    source_network_path:
        Optional alternative source network. When omitted, the packaged
        ``elec_s_37.nc`` network is used.
    snapshots:
        Optional subset of source-network snapshots. When omitted, all
        snapshots are retained.

    Returns
    -------
    pypsa.Network
        An unsolved network containing the configured scenario.
    """

    _validate_definition(definition)

    selected_countries = _normalise_and_validate_inputs(
        countries=list(definition.countries),
        scenario=definition.preset,
    )

    source_path = _resolve_source_path(
        source_network_path
    )

    source = pypsa.Network(
        source_path
    )

    _validate_country_column(
        source
    )

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

    # Add standard storage before applying presets and custom settings.
    _add_standard_storage_options(
        network=network,
        countries=selected_countries,
    )

    # Retain the existing preset behaviour.
    _apply_preset(
        network=network,
        preset=definition.preset,
    )

    # Apply user-defined settings after the preset. This allows explicit
    # advanced settings to modify the preset assumptions.
    _apply_demand_multiplier(
        network=network,
        multiplier=definition.demand_multiplier,
    )

    _apply_technology_settings(
        network=network,
        settings=definition.technologies,
    )

    _apply_co2_policy(
        network=network,
        policy=definition.co2_policy,
    )

    if not definition.allow_interconnection:
        _remove_cross_border_branches(
            network
        )

    _remove_unused_non_electric_buses(
        network
    )

    network.name = (
        definition.name.strip()
        or _build_network_name(
            countries=selected_countries,
            scenario=definition.preset,
        )
    )

    network.meta = {
        **dict(
            getattr(
                network,
                "meta",
                {},
            )
            or {}
        ),
        "scenario_builder_source": str(source_path),
        "scenario_builder_name": network.name,
        "scenario_builder_countries": selected_countries,
        "scenario_builder_preset": definition.preset,
        "scenario_builder_co2_mode": (
            definition.co2_policy.mode
        ),
        "scenario_builder_co2_value": (
            definition.co2_policy.value
        ),
        "scenario_builder_demand_multiplier": (
            definition.demand_multiplier
        ),
        "scenario_builder_allow_interconnection": (
            definition.allow_interconnection
        ),
        "scenario_builder_technologies": {
            technology: {
                "enabled": settings.enabled,
                "allow_expansion": settings.allow_expansion,
                "capital_cost_multiplier": (
                    settings.capital_cost_multiplier
                ),
                "marginal_cost_multiplier": (
                    settings.marginal_cost_multiplier
                ),
            }
            for technology, settings
            in definition.technologies.items()
        },
        "scenario_builder_standard_battery": True,
        "scenario_builder_standard_hydrogen_storage": True,
    }

    network.consistency_check()

    return network


# ------------------------------------------------------------------
# General validation
# ------------------------------------------------------------------

def _validate_definition(
    definition: ScenarioDefinition,
) -> None:
    if not isinstance(
        definition,
        ScenarioDefinition,
    ):
        raise TypeError(
            "definition must be a ScenarioDefinition instance."
        )

    if definition.demand_multiplier <= 0:
        raise ValueError(
            "Demand multiplier must be greater than zero."
        )

    _validate_co2_policy(
        definition.co2_policy
    )

    for (
        technology,
        settings,
    ) in definition.technologies.items():
        if technology not in TECHNOLOGY_CARRIERS:
            available = ", ".join(
                sorted(
                    TECHNOLOGY_CARRIERS
                )
            )

            raise ValueError(
                f"Unknown technology: {technology}. "
                f"Available technologies are: {available}"
            )

        _validate_technology_settings(
            technology=technology,
            settings=settings,
        )


def _validate_co2_policy(
    policy: CO2Policy,
) -> None:
    allowed_modes = {
        "none",
        "price",
        "absolute_cap",
    }

    if policy.mode not in allowed_modes:
        available = ", ".join(
            sorted(
                allowed_modes
            )
        )

        raise ValueError(
            f"Unknown CO₂ policy mode: {policy.mode}. "
            f"Available modes are: {available}"
        )

    if policy.mode == "none":
        return

    if policy.value is None:
        raise ValueError(
            "A value is required for the selected CO₂ policy."
        )

    if policy.value < 0:
        raise ValueError(
            "The CO₂ policy value cannot be negative."
        )


def _validate_technology_settings(
    technology: str,
    settings: TechnologySettings,
) -> None:
    if settings.capital_cost_multiplier < 0:
        raise ValueError(
            "Capital-cost multiplier for "
            f"{technology} cannot be negative."
        )

    if settings.marginal_cost_multiplier < 0:
        raise ValueError(
            "Marginal-cost multiplier for "
            f"{technology} cannot be negative."
        )


def _resolve_source_path(
    source_network_path: Path | str | None,
) -> Path:
    if source_network_path is None:
        source_path = default_source_network_path()
    else:
        source_path = Path(
            source_network_path
        )

    source_path = (
        source_path
        .expanduser()
        .resolve()
    )

    if not source_path.exists():
        raise FileNotFoundError(
            "The Scenario Builder source network was not found:\n"
            f"{source_path}\n\n"
            "Place elec_s_37.nc in:\n"
            "pypsa_gui/data/teaching/elec_s_37.nc"
        )

    if not source_path.is_file():
        raise FileNotFoundError(
            "The Scenario Builder source path is not a file: "
            f"{source_path}"
        )

    return source_path


def _normalise_and_validate_inputs(
    countries: list[str],
    scenario: str,
) -> list[str]:
    selected_countries = [
        str(country)
        .strip()
        .upper()
        for country in countries
        if str(country).strip()
    ]

    # Remove duplicates while preserving UI selection order.
    selected_countries = list(
        dict.fromkeys(
            selected_countries
        )
    )

    if not MIN_COUNTRIES <= len(selected_countries) <= MAX_COUNTRIES:
        raise ValueError(
            f"Select between {MIN_COUNTRIES} and "
            f"{MAX_COUNTRIES} countries."
        )

    if scenario not in SCENARIO_NAMES:
        available = ", ".join(
            sorted(
                SCENARIO_NAMES
            )
        )

        raise ValueError(
            f"Unknown scenario preset: {scenario}. "
            f"Available presets are: {available}"
        )

    return selected_countries


def _validate_country_column(
    network: pypsa.Network,
) -> None:
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

    selected_snapshots = pd.Index(
        snapshots
    )

    missing_snapshots = (
        selected_snapshots
        .difference(
            source.snapshots
        )
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


# ------------------------------------------------------------------
# Country selection
# ------------------------------------------------------------------

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
        bus_country.isin(
            countries
        )
    ]

    selected_bus_set = set(
        selected_bus_names
    )

    # One-port components connected through one bus column.
    for component_name, table_name in (
        (
            "Generator",
            "generators",
        ),
        (
            "Load",
            "loads",
        ),
        (
            "StorageUnit",
            "storage_units",
        ),
        (
            "Store",
            "stores",
        ),
        (
            "ShuntImpedance",
            "shunt_impedances",
        ),
    ):
        table = getattr(
            network,
            table_name,
            None,
        )

        if (
            table is None
            or table.empty
            or "bus" not in table.columns
        ):
            continue

        remove_names = table.index[
            ~table["bus"].isin(
                selected_bus_set
            )
        ]

        _remove_components(
            network=network,
            component_name=component_name,
            names=remove_names,
        )

    # Branch components can contain bus0, bus1, and additional bus columns.
    for component_name, table_name in (
        (
            "Line",
            "lines",
        ),
        (
            "Link",
            "links",
        ),
        (
            "Transformer",
            "transformers",
        ),
    ):
        table = getattr(
            network,
            table_name,
            None,
        )

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
            bus_values = (
                table[bus_column]
                .fillna("")
                .astype(str)
            )

            # Empty optional bus ports do not invalidate a component.
            port_is_valid = (
                bus_values.eq("")
                | bus_values.isin(
                    selected_bus_set
                )
            )

            keep_mask &= port_is_valid

        remove_names = table.index[
            ~keep_mask
        ]

        _remove_components(
            network=network,
            component_name=component_name,
            names=remove_names,
        )

    remove_buses = network.buses.index[
        ~network.buses.index.isin(
            selected_bus_set
        )
    ]

    _remove_components(
        network=network,
        component_name="Bus",
        names=remove_buses,
    )


# ------------------------------------------------------------------
# Standard storage
# ------------------------------------------------------------------

def _add_standard_storage_options(
    network: pypsa.Network,
    countries: list[str],
) -> None:
    """
    Add one battery and one hydrogen-storage chain per selected country.

    Storage is connected to one representative electricity bus in each
    country. Existing components with the same names are left unchanged.
    """

    for carrier in (
        "battery",
        "hydrogen",
        "electrolyser",
        "fuel cell",
    ):
        _ensure_carrier(
            network=network,
            carrier=carrier,
        )

    for country in countries:
        electricity_bus = _representative_electricity_bus(
            network=network,
            country=country,
        )

        _add_battery_storage(
            network=network,
            country=country,
            electricity_bus=electricity_bus,
        )

        _add_hydrogen_storage(
            network=network,
            country=country,
            electricity_bus=electricity_bus,
        )


def _ensure_carrier(
    network: pypsa.Network,
    carrier: str,
) -> None:
    if carrier not in network.carriers.index:
        network.add(
            "Carrier",
            carrier,
        )


def _representative_electricity_bus(
    network: pypsa.Network,
    country: str,
) -> str:
    country_mask = (
        network.buses["country"]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq(country)
    )

    country_buses = network.buses.loc[
        country_mask
    ]

    if country_buses.empty:
        raise ValueError(
            f"No electricity bus was found for country {country}."
        )

    # Prefer an AC bus when the source network provides bus carriers.
    if "carrier" in country_buses.columns:
        ac_mask = (
            country_buses["carrier"]
            .fillna("")
            .astype(str)
            .str.casefold()
            .eq("ac")
        )

        ac_buses = country_buses.index[
            ac_mask
        ]

        if len(ac_buses) > 0:
            return str(
                ac_buses[0]
            )

    return str(
        country_buses.index[0]
    )


def _add_battery_storage(
    network: pypsa.Network,
    country: str,
    electricity_bus: str,
) -> None:
    """
    Add a four-hour extendable battery StorageUnit.

    StorageUnit capital cost is specified per MW of power capacity. The
    corresponding energy capacity is determined by ``max_hours``.
    """

    name = f"{country} battery"

    if name in network.storage_units.index:
        return

    network.add(
        "StorageUnit",
        name,
        bus=electricity_bus,
        carrier="battery",
        p_nom=0.0,
        p_nom_extendable=True,
        max_hours=BATTERY_MAX_HOURS,
        efficiency_store=BATTERY_CHARGE_EFFICIENCY,
        efficiency_dispatch=BATTERY_DISCHARGE_EFFICIENCY,
        standing_loss=BATTERY_STANDING_LOSS,
        capital_cost=BATTERY_CAPITAL_COST_EUR_PER_MW,
        marginal_cost=0.0,
        cyclic_state_of_charge=True,
    )


def _add_hydrogen_storage(
    network: pypsa.Network,
    country: str,
    electricity_bus: str,
) -> None:
    """
    Add an extendable hydrogen-storage chain.

    The chain consists of:

    electricity bus -> electrolyser -> hydrogen bus
    hydrogen bus -> hydrogen store
    hydrogen bus -> fuel cell -> electricity bus
    """

    hydrogen_bus = f"{country} hydrogen"
    electrolyser = f"{country} electrolyser"
    hydrogen_store = f"{country} hydrogen store"
    fuel_cell = f"{country} fuel cell"

    electricity_bus_data = network.buses.loc[
        electricity_bus
    ]

    if hydrogen_bus not in network.buses.index:
        bus_attributes = {
            "carrier": "hydrogen",
            "country": country,
        }

        # Place the hydrogen bus at the same coordinates as the selected
        # electricity bus so it appears sensibly on network maps.
        for coordinate in (
            "x",
            "y",
        ):
            if coordinate not in network.buses.columns:
                continue

            value = electricity_bus_data.get(
                coordinate
            )

            if pd.notna(value):
                bus_attributes[coordinate] = value

        network.add(
            "Bus",
            hydrogen_bus,
            **bus_attributes,
        )

    if electrolyser not in network.links.index:
        network.add(
            "Link",
            electrolyser,
            bus0=electricity_bus,
            bus1=hydrogen_bus,
            carrier="electrolyser",
            p_nom=0.0,
            p_nom_extendable=True,
            efficiency=HYDROGEN_ELECTROLYSER_EFFICIENCY,
            capital_cost=ELECTROLYSER_CAPITAL_COST_EUR_PER_MW,
            marginal_cost=0.0,
        )

    if hydrogen_store not in network.stores.index:
        network.add(
            "Store",
            hydrogen_store,
            bus=hydrogen_bus,
            carrier="hydrogen",
            e_nom=0.0,
            e_nom_extendable=True,
            e_cyclic=True,
            standing_loss=HYDROGEN_STORE_STANDING_LOSS,
            capital_cost=HYDROGEN_STORE_CAPITAL_COST_EUR_PER_MWH,
            marginal_cost=0.0,
        )

    if fuel_cell not in network.links.index:
        network.add(
            "Link",
            fuel_cell,
            bus0=hydrogen_bus,
            bus1=electricity_bus,
            carrier="fuel cell",
            p_nom=0.0,
            p_nom_extendable=True,
            efficiency=HYDROGEN_FUEL_CELL_EFFICIENCY,
            capital_cost=FUEL_CELL_CAPITAL_COST_EUR_PER_MW,
            marginal_cost=0.0,
        )


# ------------------------------------------------------------------
# Presets
# ------------------------------------------------------------------

def _apply_preset(
    network: pypsa.Network,
    preset: str,
) -> None:
    if preset == "Reference":
        return

    if preset == "Cheap batteries":
        _apply_technology_cost_multiplier(
            network=network,
            carriers=TECHNOLOGY_CARRIERS["battery"],
            capital_cost_multiplier=BATTERY_COST_FACTOR,
            marginal_cost_multiplier=1.0,
        )
        return

    if preset == "High CO₂ price":
        _apply_co2_price(
            network=network,
            price_eur_per_tonne=(
                HIGH_CO2_PRICE_EUR_PER_TONNE
            ),
        )
        return

    if preset == "High demand":
        _apply_demand_multiplier(
            network=network,
            multiplier=HIGH_DEMAND_FACTOR,
        )
        return

    if preset == "No interconnection":
        _remove_cross_border_branches(
            network
        )
        return

    raise ValueError(
        f"Scenario preset is not implemented: {preset}"
    )


# ------------------------------------------------------------------
# Demand
# ------------------------------------------------------------------

def _apply_demand_multiplier(
    network: pypsa.Network,
    multiplier: float,
) -> None:
    if multiplier <= 0:
        raise ValueError(
            "Demand multiplier must be greater than zero."
        )

    if multiplier == 1.0:
        return

    if "p_set" in network.loads.columns:
        network.loads["p_set"] = (
            network.loads["p_set"]
            .fillna(0.0)
            .astype(float)
            * multiplier
        )

    if (
        hasattr(
            network,
            "loads_t",
        )
        and "p_set" in network.loads_t
        and not network.loads_t.p_set.empty
    ):
        network.loads_t.p_set = (
            network.loads_t.p_set
            * multiplier
        )


# ------------------------------------------------------------------
# Technology configuration
# ------------------------------------------------------------------

def _apply_technology_settings(
    network: pypsa.Network,
    settings: dict[str, TechnologySettings],
) -> None:
    for technology, technology_settings in settings.items():
        carriers = TECHNOLOGY_CARRIERS.get(
            technology
        )

        if carriers is None:
            raise ValueError(
                f"Unknown technology: {technology}"
            )

        _configure_technology(
            network=network,
            carriers=carriers,
            settings=technology_settings,
        )


def _configure_technology(
    network: pypsa.Network,
    carriers: set[str],
    settings: TechnologySettings,
) -> None:
    normalised_carriers = {
        str(carrier).casefold()
        for carrier in carriers
    }

    for (
        component_name,
        table_name,
        extendable_column,
    ) in COMPONENT_TECHNOLOGY_SPECS:
        table = getattr(
            network,
            table_name,
            None,
        )

        if (
            table is None
            or table.empty
            or "carrier" not in table.columns
        ):
            continue

        carrier_mask = (
            table["carrier"]
            .fillna("")
            .astype(str)
            .str.casefold()
            .isin(normalised_carriers)
        )

        if not carrier_mask.any():
            continue

        matching_names = table.index[
            carrier_mask
        ]

        if not settings.enabled:
            _remove_components(
                network=network,
                component_name=component_name,
                names=matching_names,
            )
            continue

        if extendable_column in table.columns:
            table.loc[
                carrier_mask,
                extendable_column,
            ] = bool(
                settings.allow_expansion
            )

        if "capital_cost" in table.columns:
            table.loc[
                carrier_mask,
                "capital_cost",
            ] = (
                table.loc[
                    carrier_mask,
                    "capital_cost",
                ]
                .fillna(0.0)
                .astype(float)
                * settings.capital_cost_multiplier
            )

        if "marginal_cost" in table.columns:
            table.loc[
                carrier_mask,
                "marginal_cost",
            ] = (
                table.loc[
                    carrier_mask,
                    "marginal_cost",
                ]
                .fillna(0.0)
                .astype(float)
                * settings.marginal_cost_multiplier
            )


def _apply_technology_cost_multiplier(
    network: pypsa.Network,
    carriers: set[str],
    capital_cost_multiplier: float,
    marginal_cost_multiplier: float,
) -> None:
    settings = TechnologySettings(
        enabled=True,
        allow_expansion=True,
        capital_cost_multiplier=capital_cost_multiplier,
        marginal_cost_multiplier=marginal_cost_multiplier,
    )

    _configure_technology(
        network=network,
        carriers=carriers,
        settings=settings,
    )


# ------------------------------------------------------------------
# CO₂ policy
# ------------------------------------------------------------------

def _apply_co2_policy(
    network: pypsa.Network,
    policy: CO2Policy,
) -> None:
    if policy.mode == "none":
        return

    if policy.value is None:
        raise ValueError(
            "A value is required for the selected CO₂ policy."
        )

    if policy.value < 0:
        raise ValueError(
            "The CO₂ policy value cannot be negative."
        )

    if policy.mode == "price":
        _apply_co2_price(
            network=network,
            price_eur_per_tonne=policy.value,
        )
        return

    if policy.mode == "absolute_cap":
        _apply_absolute_co2_cap(
            network=network,
            limit_mt_co2=policy.value,
        )
        return

    raise ValueError(
        f"Unknown CO₂ policy mode: {policy.mode}"
    )


def _apply_co2_price(
    network: pypsa.Network,
    price_eur_per_tonne: float,
) -> None:
    """
    Add a CO₂-price contribution to generator marginal costs.

    The carrier's ``co2_emissions`` value is divided by generator efficiency.
    Existing marginal costs are retained and the CO₂ cost is added.
    """

    if price_eur_per_tonne < 0:
        raise ValueError(
            "The CO₂ price cannot be negative."
        )

    if price_eur_per_tonne == 0:
        return

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
        .map(
            network.carriers["co2_emissions"]
        )
        .fillna(0.0)
        .astype(float)
    )

    if "efficiency" in network.generators.columns:
        efficiency = (
            network.generators["efficiency"]
            .replace(
                0.0,
                pd.NA,
            )
            .fillna(1.0)
            .astype(float)
        )
    else:
        efficiency = pd.Series(
            1.0,
            index=network.generators.index,
        )

    carbon_cost = (
        price_eur_per_tonne
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


def _apply_absolute_co2_cap(
    network: pypsa.Network,
    limit_mt_co2: float,
) -> None:
    """
    Apply an absolute annual CO₂ cap.

    The value supplied by the UI is in MtCO₂ and is converted to tonnes.
    """

    if limit_mt_co2 < 0:
        raise ValueError(
            "The absolute CO₂ limit cannot be negative."
        )

    limit_tonnes = (
        limit_mt_co2
        * 1_000_000.0
    )

    constraint_name = (
        "scenario_builder_co2_limit"
    )

    if (
        constraint_name
        in network.global_constraints.index
    ):
        network.global_constraints.loc[
            constraint_name,
            "type",
        ] = "primary_energy"

        network.global_constraints.loc[
            constraint_name,
            "carrier_attribute",
        ] = "co2_emissions"

        network.global_constraints.loc[
            constraint_name,
            "sense",
        ] = "<="

        network.global_constraints.loc[
            constraint_name,
            "constant",
        ] = limit_tonnes

        return

    network.add(
        "GlobalConstraint",
        constraint_name,
        type="primary_energy",
        carrier_attribute="co2_emissions",
        sense="<=",
        constant=limit_tonnes,
    )


# ------------------------------------------------------------------
# Interconnection
# ------------------------------------------------------------------

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
        (
            "Line",
            "lines",
        ),
        (
            "Link",
            "links",
        ),
        (
            "Transformer",
            "transformers",
        ),
    ):
        table = getattr(
            network,
            table_name,
            None,
        )

        if (
            table is None
            or table.empty
            or "bus0" not in table.columns
            or "bus1" not in table.columns
        ):
            continue

        country_0 = table["bus0"].map(
            bus_country
        )

        country_1 = table["bus1"].map(
            bus_country
        )

        cross_border_mask = (
            country_0.notna()
            & country_1.notna()
            & country_0.ne(country_1)
        )

        _remove_components(
            network=network,
            component_name=component_name,
            names=table.index[
                cross_border_mask
            ],
        )


# ------------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------------

def _remove_unused_non_electric_buses(
    network: pypsa.Network,
) -> None:
    """
    Remove unused auxiliary buses after technology filtering.

    Electricity buses are retained even when they currently have no attached
    components. This avoids accidentally deleting selected country buses.
    """

    used_buses: set[str] = set()

    for table_name in (
        "generators",
        "loads",
        "storage_units",
        "stores",
        "shunt_impedances",
    ):
        table = getattr(
            network,
            table_name,
            None,
        )

        if (
            table is None
            or table.empty
            or "bus" not in table.columns
        ):
            continue

        used_buses.update(
            table["bus"]
            .dropna()
            .astype(str)
        )

    for table_name in (
        "lines",
        "links",
        "transformers",
    ):
        table = getattr(
            network,
            table_name,
            None,
        )

        if table is None or table.empty:
            continue

        bus_columns = [
            column
            for column in table.columns
            if column.startswith("bus")
        ]

        for bus_column in bus_columns:
            used_buses.update(
                table[bus_column]
                .dropna()
                .astype(str)
                .loc[
                    lambda values: values.ne("")
                ]
            )

    if "carrier" in network.buses.columns:
        auxiliary_bus_mask = (
            network.buses["carrier"]
            .fillna("")
            .astype(str)
            .str.casefold()
            .isin(
                {
                    "hydrogen",
                    "h2",
                    "battery",
                }
            )
        )
    else:
        auxiliary_bus_mask = pd.Series(
            False,
            index=network.buses.index,
            dtype=bool,
        )

    remove_names = network.buses.index[
        auxiliary_bus_mask
        & ~network.buses.index.isin(
            used_buses
        )
    ]

    _remove_components(
        network=network,
        component_name="Bus",
        names=remove_names,
    )


def _remove_components(
    network: pypsa.Network,
    component_name: str,
    names: Iterable,
) -> None:
    """
    Remove components one at a time for compatibility across PyPSA versions.
    """

    for name in list(
        names
    ):
        network.remove(
            component_name,
            name,
        )


# ------------------------------------------------------------------
# Naming
# ------------------------------------------------------------------

def _build_network_name(
    countries: list[str],
    scenario: str,
) -> str:
    country_part = "-".join(
        countries
    )

    scenario_part = (
        scenario
        .lower()
        .replace(
            "₂",
            "2",
        )
        .replace(
            " ",
            "-",
        )
    )

    return (
        f"{country_part}-{scenario_part}"
    )