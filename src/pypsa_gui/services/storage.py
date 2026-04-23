from __future__ import annotations

import pandas as pd
import pypsa


def _empty_series(index: pd.Index | None = None) -> pd.Series:
    if index is None:
        return pd.Series(dtype=float)
    return pd.Series(0.0, index=index, dtype=float)


def get_storage_unit_names(network: pypsa.Network) -> list[str]:
    if network.storage_units.empty:
        return []
    return list(network.storage_units.index)


def get_storage_unit_summary(network: pypsa.Network) -> dict[str, float]:
    if network is None or network.storage_units.empty:
        return {
            "n_assets": 0,
            "total_power_mw": 0.0,
            "total_energy_mwh": 0.0,
            "avg_efficiency": 0.0,
        }

    su = network.storage_units

    power_col = "p_nom_opt" if "p_nom_opt" in su.columns else "p_nom"
    energy_col = "max_hours"

    total_power = su[power_col].fillna(0.0).sum()

    if energy_col in su.columns:
        total_energy = (su[power_col].fillna(0.0) * su[energy_col].fillna(0.0)).sum()
    else:
        total_energy = 0.0

    eff_cols = [c for c in ["efficiency_store", "efficiency_dispatch"] if c in su.columns]
    if eff_cols:
        avg_eff = su[eff_cols].mean(axis=1).mean()
    else:
        avg_eff = 0.0

    return {
        "n_assets": int(len(su)),
        "total_power_mw": float(total_power),
        "total_energy_mwh": float(total_energy),
        "avg_efficiency": float(avg_eff),
    }


def get_storage_dispatch_timeseries(
    network: pypsa.Network,
    storage_name: str | None = None,
) -> pd.Series:
    if (
        network is None
        or network.storage_units.empty
        or not hasattr(network, "storage_units_t")
        or "p" not in network.storage_units_t
    ):
        return _empty_series(network.snapshots if network is not None else None)

    p = network.storage_units_t.p

    if storage_name and storage_name in p.columns:
        return p[storage_name]

    return p.sum(axis=1)


def get_storage_soc_timeseries(
    network: pypsa.Network,
    storage_name: str | None = None,
) -> pd.Series:
    if (
        network is None
        or network.storage_units.empty
        or not hasattr(network, "storage_units_t")
        or "state_of_charge" not in network.storage_units_t
    ):
        return _empty_series(network.snapshots if network is not None else None)

    soc = network.storage_units_t.state_of_charge

    if storage_name and storage_name in soc.columns:
        return soc[storage_name]

    return soc.sum(axis=1)


def get_charge_discharge_timeseries(
    network: pypsa.Network,
    storage_name: str | None = None,
) -> tuple[pd.Series, pd.Series]:
    dispatch = get_storage_dispatch_timeseries(network, storage_name)

    # In PyPSA storage_units_t.p:
    # positive = discharge to system
    # negative = charging from system
    discharge = dispatch.clip(lower=0.0)
    charge = (-dispatch.clip(upper=0.0))

    return charge, discharge


def get_storage_dispatch_by_asset(network: pypsa.Network) -> pd.Series:
    if (
        network is None
        or network.storage_units.empty
        or not hasattr(network, "storage_units_t")
        or "p" not in network.storage_units_t
    ):
        return pd.Series(dtype=float)

    p = network.storage_units_t.p
    # total discharged energy proxy over modeled horizon
    return p.clip(lower=0.0).sum(axis=0).sort_values(ascending=False)


def get_storage_soc_by_asset(network: pypsa.Network) -> pd.Series:
    if (
        network is None
        or network.storage_units.empty
        or not hasattr(network, "storage_units_t")
        or "state_of_charge" not in network.storage_units_t
    ):
        return pd.Series(dtype=float)

    soc = network.storage_units_t.state_of_charge
    return soc.mean(axis=0).sort_values(ascending=False)


def get_storage_power_by_bus(network: pypsa.Network) -> pd.Series:
    if network is None or network.storage_units.empty:
        return pd.Series(dtype=float)

    su = network.storage_units.copy()
    power_col = "p_nom_opt" if "p_nom_opt" in su.columns else "p_nom"

    return (
        su.groupby("bus")[power_col]
        .sum()
        .sort_values(ascending=False)
    )