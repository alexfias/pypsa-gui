"""Investment bounds and persistent, explicitly selected aggregate limits."""

from __future__ import annotations

from copy import deepcopy
import math

import numpy as np
import pandas as pd
import pypsa

META_KEY = "pypsa_gui_capacity_constraints"
COMPONENTS = {
    "generators": ("Generator", "p_nom"),
    "links": ("Link", "p_nom"),
    "stores": ("Store", "e_nom"),
    "storage_units": ("StorageUnit", "p_nom"),
}


def _validate_selection(network, table_name, names, sense, value):
    if table_name not in COMPONENTS or sense not in {"=", ">=", "<="}:
        raise ValueError("Unsupported capacity component or constraint sense.")
    if not math.isfinite(value) or value < 0:
        raise ValueError("Capacity limits must be finite and non-negative.")
    if not names or len(names) != len(set(names)):
        raise ValueError("Select at least one matching asset, without duplicates.")
    table = getattr(network, table_name)
    missing = set(names) - set(table.index)
    if missing:
        raise ValueError(
            f"Capacity constraint references missing {table_name}: {sorted(missing)}."
        )
    selected = table.loc[names]
    if "active" in selected and not selected.active.all():
        raise ValueError("Capacity constraints must select active assets only.")
    return selected, COMPONENTS[table_name][1]


def _capacity_range(selected, nominal):
    extendable = selected[f"{nominal}_extendable"].astype(bool)
    lower = (
        selected[nominal].where(~extendable, selected[f"{nominal}_min"]).astype(float)
    )
    upper = (
        selected[nominal].where(~extendable, selected[f"{nominal}_max"]).astype(float)
    )
    # PyPSA's optional fixed investment target is an additional equality.
    if f"{nominal}_set" in selected:
        target = selected[f"{nominal}_set"]
        mask = extendable & target.notna()
        lower.loc[mask] = np.maximum(lower.loc[mask], target.loc[mask])
        upper.loc[mask] = np.minimum(upper.loc[mask], target.loc[mask])
    if (
        not np.isfinite(lower).all()
        or upper.isna().any()
        or (lower < 0).any()
        or (lower > upper).any()
    ):
        raise ValueError("Selected assets have invalid or conflicting capacity bounds.")
    return lower, upper, extendable


def _check_feasible(lower, upper, sense, value):
    tolerance = 1e-8 * max(1.0, abs(value))
    if (sense in {"=", "<="} and lower > value + tolerance) or (
        sense in {"=", ">="} and upper < value - tolerance
    ):
        raise ValueError(
            f"Capacity {sense} {value:g} conflicts with fixed capacities or existing bounds "
            f"(feasible range {lower:g} to {upper:g}). Edit fixed assets or bounds explicitly."
        )


def apply_capacity_limit(network, table_name, names, sense, value, *, aggregate=True):
    """Tighten per-asset investment bounds, or register a true sum constraint.

    Existing fixed assets remain fixed and contribute their nominal capacity.
    Selection is frozen by name; later deletion/renaming cannot silently alter it.
    """
    names = sorted(str(name) for name in names)
    selected, nominal = _validate_selection(network, table_name, names, sense, value)
    lower, upper, extendable = _capacity_range(selected, nominal)
    if aggregate:
        if isinstance(network.snapshots, pd.MultiIndex) or getattr(
            network, "has_scenarios", False
        ):
            raise ValueError(
                "GUI aggregate capacity limits currently support single-period, deterministic networks."
            )
        _check_feasible(float(lower.sum()), float(upper.sum()), sense, value)
        definition = {
            "table": table_name,
            "names": names,
            "sense": sense,
            "value": float(value),
        }
        definitions = deepcopy(network.meta.get(META_KEY, []))
        # Reapplying the same selection and sense replaces its limit.
        definitions = [
            d
            for d in definitions
            if (d["table"], d["names"], d["sense"]) != (table_name, names, sense)
        ]
        definitions.append(definition)
        network.meta[META_KEY] = definitions
        return (
            f"Registered total {nominal} {sense} {value:g} across {len(names)} assets."
        )

    # Validate every row before changing any bounds.
    for name in names:
        _check_feasible(float(lower[name]), float(upper[name]), sense, value)
    table = getattr(network, table_name)
    adjustable = selected.index[extendable]
    if sense in {"=", ">="}:
        table.loc[adjustable, f"{nominal}_min"] = np.maximum(
            lower.loc[adjustable], value
        )
    if sense in {"=", "<="}:
        table.loc[adjustable, f"{nominal}_max"] = np.minimum(
            upper.loc[adjustable], value
        )
    return f"Applied {nominal} {sense} {value:g} to each asset ({len(adjustable)} extendable, {len(names) - len(adjustable)} fixed and checked)."


def validate_capacity_constraints(network: pypsa.Network) -> None:
    definitions = getattr(network, "meta", {}).get(META_KEY, [])
    if not isinstance(definitions, list):
        raise ValueError("Invalid GUI capacity constraint metadata.")
    if definitions and (
        isinstance(network.snapshots, pd.MultiIndex)
        or getattr(network, "has_scenarios", False)
    ):
        raise ValueError(
            "GUI aggregate capacity limits currently support single-period, deterministic networks."
        )
    for definition in definitions:
        try:
            selected, nominal = _validate_selection(
                network,
                definition["table"],
                definition["names"],
                definition["sense"],
                definition["value"],
            )
            lower, upper, _ = _capacity_range(selected, nominal)
            _check_feasible(
                float(lower.sum()),
                float(upper.sum()),
                definition["sense"],
                definition["value"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("Invalid GUI capacity constraint metadata.") from exc


def add_capacity_constraints(network: pypsa.Network) -> None:
    """Add registered limits after create_model and before solve_model."""
    validate_capacity_constraints(network)
    for index, definition in enumerate(getattr(network, "meta", {}).get(META_KEY, [])):
        table_name, names = definition["table"], definition["names"]
        component, nominal = COMPONENTS[table_name]
        selected = getattr(network, table_name).loc[names]
        extendable = selected[f"{nominal}_extendable"].astype(bool)
        fixed = float(selected.loc[~extendable, nominal].sum())
        if not extendable.any():
            continue  # Already checked against the fixed total.
        variable = network.model.variables[f"{component}-{nominal}"]
        # PyPSA versions use either 'name' or a component-specific asset axis.
        dimension = variable.dims[0]
        expression = variable.sel(
            {dimension: selected.index[extendable].tolist()}
        ).sum()
        network.model.add_constraints(
            expression,
            "==" if definition["sense"] == "=" else definition["sense"],
            definition["value"] - fixed,
            name=f"GUI-capacity-{index}",
        )
