"""Shared physical weights and dense inputs for analysis and reports."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pypsa


def snapshot_weights(network: pypsa.Network, kind: str = "generators") -> pd.Series:
    """Return represented hours, never economic objective weights as a fallback.

    Generator weights count represented energy/hours; store weights describe the
    duration of storage transitions. Investment-period economic weights are not
    physical energy weights and are deliberately not applied here.
    """
    weights = network.snapshot_weightings
    if isinstance(weights, pd.DataFrame):
        if kind not in weights:
            raise ValueError(f"Missing snapshot weighting column {kind!r}.")
        weights = weights[kind]
    weights = weights.reindex(network.snapshots).astype(float)
    if not np.isfinite(weights).all() or (weights < 0).any():
        raise ValueError(f"Snapshot {kind} weights must be finite and non-negative.")
    return weights


def weighted_mean(values: pd.DataFrame | pd.Series, weights: pd.Series):
    weights = weights.reindex(values.index)
    if isinstance(values, pd.DataFrame):
        denominator = values.notna().multiply(weights, axis=0).sum()
    else:
        denominator = weights.where(values.notna()).sum()
    numerator = values.multiply(weights, axis=0).sum()
    if isinstance(denominator, pd.Series):
        return numerator / denominator.replace(0, np.nan)
    return numerator / denominator if denominator > 0 else float("nan")


def load_timeseries(network: pypsa.Network) -> pd.DataFrame:
    """Combine static p_set with per-load time-series overrides."""
    return network.get_switchable_as_dense("Load", "p_set")


def load_by_bus(network: pypsa.Network, electricity_only: bool = False) -> pd.DataFrame:
    values = load_timeseries(network)
    mapping = network.loads.bus.reindex(values.columns)
    if electricity_only:
        # Empty bus carriers are common in hand-built electricity networks.
        carriers = mapping.map(network.buses.carrier).fillna("").str.lower()
        selected = carriers.isin(["", "ac", "dc", "electricity", "electric"])
        values = values.loc[:, selected]
        mapping = mapping.loc[selected]
    return values.T.groupby(mapping).sum().T


def positive_generator_energy(network: pypsa.Network) -> pd.DataFrame:
    dispatch = network.generators_t.p.reindex(
        index=network.snapshots, columns=network.generators.index, fill_value=0.0
    )
    return dispatch.clip(lower=0).multiply(snapshot_weights(network), axis=0)
