from __future__ import annotations

import pandas as pd
import pypsa


def get_carrier_emission_factors(network: pypsa.Network) -> pd.Series:
    """
    Return carrier-specific emission factors in tCO2/MWh.

    Falls back to 0.0 if the carrier table or the co2_emissions column
    is missing or incomplete.
    """
    if network.carriers.empty or "co2_emissions" not in network.carriers.columns:
        return pd.Series(0.0, index=network.carriers.index, dtype=float)

    return network.carriers["co2_emissions"].fillna(0.0).astype(float)


def get_generator_emissions(network: pypsa.Network) -> pd.DataFrame:
    """
    Return generator emissions time series [tCO2 per snapshot].

    Emissions are computed from positive generator dispatch only:
        emissions = max(p, 0) * carrier_emission_factor
    """
    if network.generators.empty or network.generators_t.p.empty:
        return pd.DataFrame(index=network.snapshots)

    dispatch = network.generators_t.p.copy()
    dispatch = dispatch.reindex(columns=network.generators.index, fill_value=0.0)
    dispatch = dispatch.clip(lower=0.0)

    emission_factors = get_carrier_emission_factors(network)
    generator_factors = network.generators["carrier"].map(emission_factors).fillna(0.0)

    return dispatch.multiply(generator_factors, axis=1)


def get_system_emissions_series(network: pypsa.Network) -> pd.Series:
    """
    Total system emissions by snapshot [tCO2].
    """
    emissions = get_generator_emissions(network)
    if emissions.empty:
        return pd.Series(0.0, index=network.snapshots, dtype=float)

    return emissions.sum(axis=1)


def get_total_emissions(network: pypsa.Network) -> float:
    """
    Total emissions across all generators and snapshots [tCO2].
    """
    series = get_system_emissions_series(network)
    return float(series.sum())


def get_emissions_by_carrier(network: pypsa.Network) -> pd.Series:
    """
    Aggregate total emissions by generator carrier [tCO2].
    """
    emissions = get_generator_emissions(network)
    if emissions.empty:
        return pd.Series(dtype=float)

    totals_by_generator = emissions.sum(axis=0)
    carriers = network.generators["carrier"].reindex(totals_by_generator.index)

    return totals_by_generator.groupby(carriers).sum().sort_values(ascending=False)


def get_emissions_by_bus(network: pypsa.Network) -> pd.Series:
    """
    Aggregate total emissions by bus [tCO2].
    """
    emissions = get_generator_emissions(network)
    if emissions.empty:
        return pd.Series(dtype=float)

    totals_by_generator = emissions.sum(axis=0)
    buses = network.generators["bus"].reindex(totals_by_generator.index)

    return totals_by_generator.groupby(buses).sum().sort_values(ascending=False)


def get_total_generation(network: pypsa.Network) -> float:
    """
    Total positive generation [MWh].
    """
    if network.generators.empty or network.generators_t.p.empty:
        return 0.0

    dispatch = network.generators_t.p.reindex(columns=network.generators.index, fill_value=0.0)
    dispatch = dispatch.clip(lower=0.0)
    return float(dispatch.sum().sum())


def get_average_emission_intensity(network: pypsa.Network) -> float:
    """
    Average operational emission intensity [gCO2/kWh].

    Assumes carrier co2_emissions are expressed in tCO2/MWh.
    """
    total_generation = get_total_generation(network)
    if total_generation <= 0.0:
        return 0.0

    total_emissions = get_total_emissions(network)
    return 1000.0 * total_emissions / total_generation


def get_zero_emission_generation_share(network: pypsa.Network) -> float:
    """
    Share of positive generation from carriers with zero emission factor [%].
    """
    if network.generators.empty or network.generators_t.p.empty:
        return 0.0

    dispatch = network.generators_t.p.reindex(columns=network.generators.index, fill_value=0.0)
    dispatch = dispatch.clip(lower=0.0)

    emission_factors = get_carrier_emission_factors(network)
    generator_factors = network.generators["carrier"].map(emission_factors).fillna(0.0)

    total_generation = float(dispatch.sum().sum())
    if total_generation <= 0.0:
        return 0.0

    zero_emission_generators = generator_factors[generator_factors == 0.0].index
    zero_emission_generation = float(dispatch[zero_emission_generators].sum().sum())

    return 100.0 * zero_emission_generation / total_generation


def get_top_emitting_carrier(network: pypsa.Network) -> str:
    """
    Return the top emitting carrier as a formatted string.
    """
    by_carrier = get_emissions_by_carrier(network)
    if by_carrier.empty:
        return "-"

    carrier = str(by_carrier.index[0])
    value = float(by_carrier.iloc[0])
    return f"{carrier} ({value:,.2f} tCO₂)"


def get_emissions_summary_stats(network: pypsa.Network) -> dict[str, str]:
    """
    Summary stats formatted for display in KPI cards.
    """
    return {
        "total_emissions": f"{get_total_emissions(network):,.2f} tCO₂",
        "average_intensity": f"{get_average_emission_intensity(network):,.1f} gCO₂/kWh",
        "top_carrier": get_top_emitting_carrier(network),
        "zero_emission_share": f"{get_zero_emission_generation_share(network):,.1f} %",
    }


def has_emission_data(network: pypsa.Network) -> bool:
    """
    Whether the network contains at least one non-zero carrier emission factor.
    """
    emission_factors = get_carrier_emission_factors(network)
    return bool((emission_factors.fillna(0.0) != 0.0).any())