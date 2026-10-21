from __future__ import annotations

import numpy as np
import pandas as pd
import pypsa

from pypsa_gui.services.metrics import positive_generator_energy, snapshot_weights


def get_carrier_emission_factors(network: pypsa.Network) -> pd.Series:
    """
    Return carrier-specific emission factors in tCO2/MWh of primary energy.

    Falls back to 0.0 if the carrier table or the co2_emissions column
    is missing or incomplete.
    """
    if network.carriers.empty or "co2_emissions" not in network.carriers.columns:
        return pd.Series(0.0, index=network.carriers.index, dtype=float)

    return network.carriers["co2_emissions"].fillna(0.0).astype(float)


def get_generator_emission_rates(network: pypsa.Network) -> pd.DataFrame:
    """Generator-specific tCO2/MWh of output, using dynamic efficiency.

    Zero-factor assets do not need an efficiency correction. Invalid efficiency
    for an emitting asset is an error, not an implicit assumption of 100%.
    """
    factors = network.generators.carrier.map(
        get_carrier_emission_factors(network)
    ).fillna(0.0)
    if not np.isfinite(factors).all():
        raise ValueError("Carrier emission factors must be finite.")
    rates = pd.DataFrame(0.0, index=network.snapshots, columns=network.generators.index)
    emitting = factors.index[factors.ne(0)]
    if len(emitting):
        efficiency = network.get_switchable_as_dense("Generator", "efficiency").loc[
            :, emitting
        ]
        if (
            not np.isfinite(efficiency.to_numpy()).all()
            or (efficiency <= 0).any().any()
        ):
            raise ValueError(
                "Emitting generators must have finite, positive efficiency at every snapshot."
            )
        rates.loc[:, emitting] = (1.0 / efficiency).multiply(
            factors.loc[emitting], axis=1
        )
    return rates


def get_generator_emissions(network: pypsa.Network) -> pd.DataFrame:
    """Generator contribution to primary-energy CO2 accounting [tCO2/snapshot].

    Signed dispatch / efficiency * carrier tCO2/MWh_primary * generator hours.
    This does not include non-cyclic Store/StorageUnit inventory changes or
    separate Link/Process emissions in sector-coupled models.
    """
    if network.generators.empty or network.generators_t.p.empty:
        return pd.DataFrame(index=network.snapshots)
    dispatch = network.generators_t.p.reindex(
        index=network.snapshots, columns=network.generators.index, fill_value=0.0
    )
    return (dispatch * get_generator_emission_rates(network)).multiply(
        snapshot_weights(network), axis=0
    )


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

    return float(positive_generator_energy(network).sum().sum())


def get_average_emission_intensity(network: pypsa.Network) -> float:
    """
    Average operational emission intensity [gCO2/kWh].

    Carrier co2_emissions are expressed in tCO2/MWh of primary energy.
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

    energy = positive_generator_energy(network)
    emission_factors = get_carrier_emission_factors(network)
    generator_factors = network.generators["carrier"].map(emission_factors).fillna(0.0)
    total_generation = float(energy.sum().sum())
    if total_generation <= 0.0:
        return 0.0
    zero_emission_generators = generator_factors[generator_factors == 0.0].index
    zero_emission_generation = float(energy[zero_emission_generators].sum().sum())
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
