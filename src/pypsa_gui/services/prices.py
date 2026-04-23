from __future__ import annotations

from typing import Any

import pandas as pd
import pypsa


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

    if network.loads.empty:
        return pd.DataFrame(index=getattr(network, "snapshots", pd.Index([])))

    if not hasattr(network.loads_t, "p_set"):
        return pd.DataFrame(index=getattr(network, "snapshots", pd.Index([])))

    p_set = network.loads_t.p_set.copy()
    if p_set.empty:
        return pd.DataFrame(index=getattr(network, "snapshots", pd.Index([])))

    load_bus_map = network.loads["bus"]

    load_per_bus = {}
    for load_name in p_set.columns:
        if load_name not in load_bus_map.index:
            continue
        bus = load_bus_map.loc[load_name]
        load_per_bus.setdefault(bus, []).append(load_name)

    result = pd.DataFrame(index=p_set.index)
    for bus, load_names in load_per_bus.items():
        result[bus] = p_set[load_names].sum(axis=1)

    return result


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

    loads = loads.fillna(0.0)

    total_load = loads.sum(axis=1)
    weighted_sum = (prices * loads).sum(axis=1)

    result = weighted_sum.divide(total_load.where(total_load != 0.0))
    result = result.fillna(prices.mean(axis=1))
    return result


def get_average_price_by_bus(network: pypsa.Network | None) -> pd.Series:
    prices = get_nodal_prices(network)
    if prices.empty:
        return pd.Series(dtype=float)

    return prices.mean(axis=0).sort_values(ascending=False)


def get_negative_price_counts(network: pypsa.Network | None) -> pd.Series:
    prices = get_nodal_prices(network)
    if prices.empty:
        return pd.Series(dtype=int)

    return (prices < 0.0).sum(axis=0).sort_values(ascending=False)


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
        "avg_price": float(system_price.mean()) if not system_price.empty else None,
        "min_price": float(prices.min().min()),
        "max_price": float(prices.max().max()),
        "negative_hours": int((prices < 0.0).sum().sum()),
        "spread_95_5": float(system_price.quantile(0.95) - system_price.quantile(0.05))
        if not system_price.empty
        else None,
        "highest_avg_bus": avg_by_bus.index[0] if not avg_by_bus.empty else None,
        "lowest_avg_bus": avg_by_bus.index[-1] if not avg_by_bus.empty else None,
    }