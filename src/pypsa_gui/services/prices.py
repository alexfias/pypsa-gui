from __future__ import annotations

from typing import Any

import pandas as pd
import pypsa

from pypsa_gui.services.metrics import load_by_bus, snapshot_weights, weighted_mean


def get_nodal_prices(network: pypsa.Network | None) -> pd.DataFrame:
    if network is None:
        return pd.DataFrame()

    if not hasattr(network, "buses_t"):
        return pd.DataFrame()

    prices = getattr(network.buses_t, "marginal_price", None)
    if prices is None:
        return pd.DataFrame()

    if prices.empty:
        return pd.DataFrame()

    return prices.copy()


def get_bus_load_timeseries(network: pypsa.Network | None) -> pd.DataFrame:
    if network is None:
        return pd.DataFrame()

    return load_by_bus(network, electricity_only=True)


def get_system_price_series(
    network: pypsa.Network | None,
    weighted: bool = True,
) -> pd.Series:
    prices = get_nodal_prices(network)
    if prices.empty:
        return pd.Series(dtype=float)

    if not weighted:
        return prices.mean(axis=1)

    loads = get_bus_load_timeseries(network)
    if loads.empty:
        return prices.mean(axis=1)

    prices, loads = prices.align(loads, join="left", axis=0)
    prices, loads = prices.align(loads, join="left", axis=1)

    loads = loads.fillna(0.0).clip(lower=0).where(prices.notna(), 0)

    total_load = loads.sum(axis=1)
    weighted_sum = (prices * loads).sum(axis=1)

    result = weighted_sum.divide(total_load.where(total_load != 0.0))
    result = result.fillna(prices.mean(axis=1))
    return result


def get_average_price_by_bus(network: pypsa.Network | None) -> pd.Series:
    prices = get_nodal_prices(network)
    if prices.empty:
        return pd.Series(dtype=float)

    return weighted_mean(prices, snapshot_weights(network)).sort_values(ascending=False)


def get_negative_price_counts(network: pypsa.Network | None) -> pd.Series:
    prices = get_nodal_prices(network)
    if prices.empty:
        return pd.Series(dtype=int)

    return (
        (prices < 0.0)
        .multiply(snapshot_weights(network), axis=0)
        .sum()
        .sort_values(ascending=False)
    )


def get_price_summary_stats(network: pypsa.Network | None) -> dict[str, Any]:
    prices = get_nodal_prices(network)
    if prices.empty:
        return {
            "avg_price": None,
            "min_price": None,
            "max_price": None,
            "negative_hours": None,
            "spread_95_5": None,
            "highest_avg_bus": None,
            "lowest_avg_bus": None,
        }

    system_price = get_system_price_series(network, weighted=True)
    avg_by_bus = get_average_price_by_bus(network)

    return {
        "avg_price": get_electricity_price_statistics(network)[0],
        "min_price": float(prices.min().min()),
        "max_price": float(prices.max().max()),
        "negative_hours": float(get_negative_price_counts(network).sum()),
        "spread_95_5": (
            weighted_price_quantile(system_price, snapshot_weights(network), 0.95)
            - weighted_price_quantile(system_price, snapshot_weights(network), 0.05)
            if not system_price.empty
            else None
        ),
        "highest_avg_bus": avg_by_bus.index[0] if not avg_by_bus.empty else None,
        "lowest_avg_bus": avg_by_bus.index[-1] if not avg_by_bus.empty else None,
    }


def weighted_price_quantile(values: pd.Series, weights: pd.Series, q: float) -> float:
    """Inverse weighted empirical CDF (represented-hour price duration curve)."""
    ordered = values.dropna().sort_values()
    weights = weights.reindex(ordered.index)
    if weights.sum() <= 0 or ordered.empty:
        return float("nan")
    cumulative = weights.cumsum() / weights.sum()
    return float(ordered.iloc[min(cumulative.searchsorted(q), len(ordered) - 1)])


def get_electricity_price_statistics(network: pypsa.Network):
    """Demand-and-duration weighted average/stddev, and observed min/max.

    Only buses serving positive electricity demand enter these statistics.
    """
    prices = get_nodal_prices(network)
    loads = load_by_bus(network, electricity_only=True).clip(lower=0)
    columns = prices.columns.intersection(loads.columns)
    if columns.empty:
        return None, None, None, None
    prices = prices.reindex(index=network.snapshots, columns=columns)
    energy = loads[columns].multiply(snapshot_weights(network), axis=0)
    valid = prices.notna() & energy.gt(0)
    energy = energy.where(valid, 0)
    denominator = float(energy.sum().sum())
    if denominator <= 0:
        return None, None, None, None
    mean = float((prices * energy).sum().sum() / denominator)
    variance = float(((prices - mean) ** 2 * energy).sum().sum() / denominator)
    return (
        mean,
        float(prices.where(valid).min().min()),
        float(prices.where(valid).max().max()),
        max(variance, 0) ** 0.5,
    )
