"""Validated, atomic edits of scalar component inputs and names."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
import re
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pypsa

from pypsa_gui.services.capacity_constraints import (
    META_KEY,
    validate_capacity_constraints,
)
from pypsa_gui.services.preprocessing import invalidate_results
from pypsa_gui.services.locations import LOCATION_META_KEY


@dataclass(frozen=True)
class NetworkEdit:
    component: str
    name: str
    attribute: str
    old_value: object
    new_value: object


def edit_block_reason(network, component_name, name, attribute) -> str | None:
    if network is None:
        return "No network loaded."
    if getattr(network, "_gui_edit_locked", False):
        return "Network inputs are locked while optimisation is running."
    component = network.components[component_name]
    if isinstance(component.static.index, pd.MultiIndex):
        return "Scalar table editing does not yet support stochastic component indices."
    if attribute == "name":
        return None
    if attribute in component.defaults.index:
        if component.defaults.at[attribute, "status"] == "Output":
            return "Calculated output; rerun optimisation to update this value."
    elif attribute not in component.static:
        return "Unknown component attribute."
    dynamic = component.dynamic.get(attribute)
    if dynamic is not None and name in dynamic.columns:
        return "This asset has a time-series override. Edit or remove that series before changing its static value."
    if attribute in component.static and not pd.api.types.is_scalar(
        component.static.at[name, attribute]
    ):
        return "Structured values cannot be edited as scalar text."
    return None


def _parse_value(component, attribute, value):
    text = str(value).strip()
    if attribute in component.defaults.index:
        definition = component.defaults.loc[attribute]
        kind, default = definition["typ"], definition["default"]
    else:
        dtype = component.static[attribute].dtype
        kind = (
            bool
            if pd.api.types.is_bool_dtype(dtype)
            else (
                int
                if pd.api.types.is_integer_dtype(dtype)
                else float if pd.api.types.is_numeric_dtype(dtype) else str
            )
        )
        default = np.nan if kind is float else ""
    if kind is str:
        return text
    if kind is bool:
        choices = {
            "true": True,
            "1": True,
            "yes": True,
            "false": False,
            "0": False,
            "no": False,
        }
        if text.lower() not in choices:
            raise ValueError("Enter true/false, yes/no, or 1/0 for a boolean input.")
        return choices[text.lower()]
    if kind is int:
        number = float(text)
        if not math.isfinite(number) or not number.is_integer():
            raise ValueError("Enter a finite whole number for an integer input.")
        return int(number)
    if kind is float:
        number = float(text) if text else float("nan")
        if math.isnan(number) and not pd.isna(default):
            raise ValueError(
                f"{attribute} requires a number; it cannot be blank or NaN."
            )
        if math.isinf(number) and not (
            isinstance(default, (int, float))
            and math.isinf(default)
            and number == default
        ):
            raise ValueError(f"{attribute} requires a finite number.")
        return number
    raise ValueError("This attribute cannot be edited as scalar text.")


def _validate_row(network, component, name, attribute, row):
    value = row[attribute]
    if re.fullmatch(r"bus\d*", attribute):
        optional = component.name == "GlobalConstraint" or attribute not in {
            "bus",
            "bus0",
            "bus1",
        }
        if not (optional and value == "") and value not in network.buses.index:
            raise ValueError(f"Bus {value!r} does not exist.")
    if attribute == "type" and component.name in {"Line", "Transformer"}:
        types = (
            network.line_types
            if component.name == "Line"
            else network.transformer_types
        )
        if value and value not in types.index:
            raise ValueError(f"Unknown {component.name.lower()} type {value!r}.")
    if attribute == "control" and value not in {"PQ", "PV", "Slack"}:
        raise ValueError("Generator control must be PQ, PV or Slack.")
    if (
        component.name == "GlobalConstraint"
        and attribute == "sense"
        and value not in {"=", "==", ">=", "<="}
    ):
        raise ValueError("Constraint sense must be =, ==, >= or <=.")
    if (
        component.name == "GlobalConstraint"
        and attribute == "type"
        and value
        not in {
            "primary_energy",
            "operational_limit",
            "tech_capacity_expansion_limit",
            "transmission_volume_expansion_limit",
            "transmission_expansion_cost_limit",
        }
    ):
        raise ValueError("Unsupported built-in global constraint type.")
    nonnegative = {
        "p_nom",
        "e_nom",
        "s_nom",
        "p_nom_min",
        "e_nom_min",
        "s_nom_min",
        "p_nom_max",
        "e_nom_max",
        "s_nom_max",
        "p_nom_set",
        "e_nom_set",
        "s_nom_set",
        "p_nom_mod",
        "e_nom_mod",
        "s_nom_mod",
        "max_hours",
        "length",
        "num_parallel",
        "min_up_time",
        "min_down_time",
        "up_time_before",
        "down_time_before",
        "build_year",
        "state_of_charge_initial",
        "ramp_limit_up",
        "ramp_limit_down",
        "ramp_limit_start_up",
        "ramp_limit_shut_down",
    }
    if attribute in nonnegative and value < 0:
        raise ValueError(f"{attribute} cannot be negative.")
    if attribute in {"v_nom", "lifetime"} and value <= 0:
        raise ValueError(f"{attribute} must be positive.")
    if attribute == "efficiency" and component.name == "Generator" and value <= 0:
        raise ValueError("Generator efficiency must be positive.")
    if attribute in {"efficiency_store", "efficiency_dispatch"} and not 0 < value <= 1:
        raise ValueError(
            "Storage efficiency must be greater than zero and at most one."
        )
    if attribute == "standing_loss" and not 0 <= value <= 1:
        raise ValueError("Standing loss must lie between zero and one.")
    # Validate only bounds affected by this edit, including dynamic counterparts.
    for lower, upper in [
        (f"{prefix}_nom_min", f"{prefix}_nom_max") for prefix in ("p", "e", "s")
    ] + [
        ("p_min_pu", "p_max_pu"),
        ("e_min_pu", "e_max_pu"),
        ("v_mag_pu_min", "v_mag_pu_max"),
        ("e_sum_min", "e_sum_max"),
    ]:
        if attribute not in {lower, upper} or lower not in row or upper not in row:
            continue
        bounds = []
        for key in (lower, upper):
            dynamic = component.dynamic.get(key)
            bounds.append(
                dynamic[name] if dynamic is not None and name in dynamic else row[key]
            )
        if np.any(bounds[0] > bounds[1]):
            raise ValueError(
                f"{lower} must not exceed {upper}, including at any snapshot."
            )
    for prefix in ("p", "e", "s"):
        if attribute not in {
            f"{prefix}_nom_min",
            f"{prefix}_nom_max",
            f"{prefix}_nom_set",
        }:
            continue
        target = row.get(f"{prefix}_nom_set", np.nan)
        if (
            pd.notna(target)
            and not row[f"{prefix}_nom_min"] <= target <= row[f"{prefix}_nom_max"]
        ):
            raise ValueError(f"{prefix}_nom_set must lie within its investment bounds.")


def edit_component(
    network: pypsa.Network,
    component_name: str,
    name: str,
    attribute: str,
    value,
    *,
    locations=None,
) -> NetworkEdit | None:
    """Prepare changed tables first; failure leaves inputs and results untouched.

    Only affected tables are copied, not a potentially large network/model.
    None means a validated no-op, which must not dirty a saved network.
    """
    component = network.components[component_name]
    if name not in component.static.index:
        raise ValueError(
            f"{component.name} {name!r} no longer exists. Refresh the table."
        )
    reason = edit_block_reason(network, component_name, name, attribute)
    if reason:
        raise ValueError(reason)
    old = name if attribute == "name" else component.static.at[name, attribute]
    parsed = (
        str(value).strip()
        if attribute == "name"
        else _parse_value(component, attribute, value)
    )
    old_missing, new_missing = pd.isna(old), pd.isna(parsed)
    if (old_missing and new_missing) or (
        not old_missing and not new_missing and old == parsed
    ):
        return None

    tables = {}
    dynamic = {}
    metadata = deepcopy(network.meta)
    updated_locations = deepcopy(locations) if locations is not None else None
    if attribute == "name":
        if not parsed:
            raise ValueError("Component names cannot be empty.")
        if parsed in component.static.index:
            raise ValueError(f"A {component.name} named {parsed!r} already exists.")
        for field, frame in component.dynamic.items():
            if parsed in frame.columns:
                raise ValueError(
                    f"A time-series column named {parsed!r} already exists in {field}."
                )
            if name in frame.columns:
                dynamic[field] = frame.rename(columns={name: parsed})
        tables[component.name] = component.static.rename(index={name: parsed})
        for other in network.components:
            columns = []
            if component.name == "Bus":
                columns = [
                    col for col in other.static.columns if re.fullmatch(r"bus\d*", col)
                ]
            elif component.name == "Carrier" and "carrier" in other.static:
                columns = ["carrier"]
            if columns:
                table = tables.get(other.name, other.static).copy()
                for col in columns:
                    table[col] = table[col].replace({name: parsed})
                tables[other.name] = table
        for definition in metadata.get(META_KEY, []):
            if definition["table"] == component.list_name:
                definition["names"] = sorted(
                    parsed if x == name else x for x in definition["names"]
                )
        if component.name == "Bus":
            for record in metadata.get(LOCATION_META_KEY, []):
                record["bus_names"] = [
                    parsed if bus == name else bus for bus in record["bus_names"]
                ]
                if record["name"] == name and record["bus_names"] == [parsed]:
                    record["name"] = parsed
        if component.name == "Bus" and updated_locations is not None:
            for location in updated_locations.values():
                location.bus_names = [
                    parsed if bus == name else bus for bus in location.bus_names
                ]
                if location.name == name and location.bus_names == [parsed]:
                    location.name = parsed
    else:
        row = component.static.loc[name].copy()
        row[attribute] = parsed
        _validate_row(network, component, name, attribute, row)
        table = component.static.copy()
        table.at[name, attribute] = parsed
        tables[component.name] = table
        if (
            component.name == "Bus"
            and attribute == "location"
            and updated_locations is not None
        ):
            for location in updated_locations.values():
                if location.id != parsed:
                    location.bus_names = [
                        bus for bus in location.bus_names if bus != name
                    ]

    # Check registered aggregate limits against the proposed inputs/selections.
    view = SimpleNamespace(
        meta=metadata,
        snapshots=network.snapshots,
        has_scenarios=getattr(network, "has_scenarios", False),
    )
    for c in network.components:
        setattr(view, c.list_name, tables.get(c.name, c.static))
    validate_capacity_constraints(view)
    for key, table in tables.items():
        network.components[key].static = table
    for field, frame in dynamic.items():
        component.dynamic[field] = frame
    network.meta = metadata
    if updated_locations is not None:
        locations.clear()
        locations.update(updated_locations)
    invalidate_results(network)
    return NetworkEdit(component.list_name, name, attribute, old, parsed)
