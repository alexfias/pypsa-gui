"""Validated pre-run transformations; solved outputs never become new inputs."""

from __future__ import annotations

from copy import deepcopy

import numpy as np
import pandas as pd
import pypsa

from pypsa_gui.services.metrics import snapshot_weights


def invalidate_results(network: pypsa.Network) -> None:
    for component in network.components:
        outputs = component.defaults.index[component.defaults.status.eq("Output")]
        for attribute in outputs:
            if attribute in component.dynamic:
                component.dynamic[attribute] = pd.DataFrame(index=network.snapshots)
            if attribute in component.static:
                component.static[attribute] = component.defaults.at[
                    attribute, "default"
                ]
    # PyPSA exposes these as read-only public properties.
    network._model = None
    network._objective = None
    network._objective_constant = None


def copy_for_preprocessing(network: pypsa.Network) -> pypsa.Network:
    # Native solver objects cannot be deep-copied. The candidate needs input
    # data only; avoid modifying the live network even temporarily.
    model = getattr(network, "_model", None)
    candidate = deepcopy(network, {id(model): None} if model is not None else {})
    invalidate_results(candidate)
    return candidate


def commit_preprocessing(network: pypsa.Network, candidate: pypsa.Network) -> None:
    """Keep the network identity used by pages and session state."""
    network.set_snapshots(candidate.snapshots)
    network.snapshot_weightings = candidate.snapshot_weightings.copy()
    for component in candidate.components:
        target = network.components[component.name]
        target.static = component.static.copy(deep=True)
        for attribute, frame in component.dynamic.items():
            target.dynamic[attribute] = frame.copy(deep=True)
    network.meta = deepcopy(candidate.meta)
    invalidate_results(network)


def aggregate_snapshots(network: pypsa.Network, step: int) -> tuple[int, int]:
    """Average consecutive input blocks and sum each weighting column.

    The last, possibly shorter block gets only its actual original weights.
    This preserves represented duration and weighted load/availability/inflow,
    but is an approximation for peaks, correlations and storage operation.
    """
    if isinstance(step, bool) or not isinstance(step, int) or step < 1:
        raise ValueError("The aggregation block size must be a positive integer.")
    old_n = len(network.snapshots)
    if step == 1 or old_n < 2:
        return old_n, old_n
    if isinstance(network.snapshots, pd.MultiIndex) or getattr(
        network, "has_scenarios", False
    ):
        raise ValueError(
            "Temporal averaging currently supports single-period, deterministic networks."
        )
    if not network.snapshots.is_unique or not network.snapshots.is_monotonic_increasing:
        raise ValueError("Temporal averaging requires unique, ordered snapshots.")
    for component in network.components:
        if component.static.empty:
            continue
        for flag in ("committable", "maintainable"):
            if flag in component.static and component.static[flag].any():
                raise ValueError(
                    "Temporal averaging does not support unit commitment or maintenance scheduling."
                )
        for attribute in (
            "ramp_limit_up",
            "ramp_limit_down",
            "state_of_charge_set",
            "e_set",
        ):
            static = component.static.get(attribute, pd.Series(dtype=float))
            dynamic = component.dynamic.get(attribute, pd.DataFrame())
            if static.notna().any() or dynamic.notna().any().any():
                raise ValueError(
                    f"Temporal averaging does not support {component.name}.{attribute}; remove or reformulate it first."
                )
        if "delay" in component.static and component.static["delay"].ne(0).any():
            raise ValueError("Temporal averaging does not support transport delays.")

    groups = np.arange(old_n) // step
    new_snapshots = network.snapshots[::step]
    weights = {
        kind: snapshot_weights(network, kind)
        for kind in network.snapshot_weightings.columns
    }
    new_weights = network.snapshot_weightings.groupby(groups).sum()
    new_weights.index = new_snapshots
    aggregated = {}
    # Build all data first. Invalid inputs must not leave a half-reduced network.
    for component in network.components:
        for attribute, frame in component.dynamic.items():
            if frame.empty or component.defaults.at[attribute, "status"] == "Output":
                continue
            if not all(pd.api.types.is_numeric_dtype(dtype) for dtype in frame.dtypes):
                raise ValueError(
                    f"Cannot average non-numeric {component.name}.{attribute}."
                )
            frame = frame.reindex(network.snapshots)
            kind = "generators"
            if component.name in {"Store", "StorageUnit"}:
                kind = "stores"
            if "cost" in attribute:
                kind = "objective"
            weight = weights[kind]
            # Average fuel-per-output coefficients for generator efficiency.
            reciprocal = component.name == "Generator" and attribute == "efficiency"
            if reciprocal:
                if (frame <= 0).any().any() or not np.isfinite(frame.to_numpy()).all():
                    raise ValueError("Cannot average invalid generator efficiencies.")
                frame = 1.0 / frame
            numerator = frame.multiply(weight, axis=0).groupby(groups).sum(min_count=1)
            denominator = frame.notna().multiply(weight, axis=0).groupby(groups).sum()
            result = numerator / denominator.replace(0, np.nan)
            # Zero-weight blocks carry no energy but still require input values.
            result = result.where(denominator.ne(0), frame.groupby(groups).mean())
            if reciprocal:
                result = 1.0 / result
            result.index = new_snapshots
            aggregated[component.name, attribute] = result
    network.set_snapshots(new_snapshots)
    network.snapshot_weightings = new_weights
    for (component, attribute), frame in aggregated.items():
        network.components[component].dynamic[attribute] = frame
    invalidate_results(network)
    return old_n, len(new_snapshots)
