"""Builder location state without mutating network inputs during display."""

from __future__ import annotations

from dataclasses import asdict
import math

import pandas as pd

from pypsa_gui.models.network_location import NetworkLocation

LOCATION_META_KEY = "pypsa_gui_locations"


def load_locations(network) -> dict[str, NetworkLocation]:
    locations = {}
    for record in network.meta.get(LOCATION_META_KEY, []):
        try:
            location = NetworkLocation(**record)
            if not all(
                math.isfinite(v) for v in (location.longitude, location.latitude)
            ):
                continue
            locations[location.id] = location
        except (TypeError, ValueError):
            continue
    sync_locations(network, locations)
    return locations


def sync_locations(network, locations) -> None:
    membership = {
        bus: key for key, location in locations.items() for bus in location.bus_names
    }
    grouped = {}
    for name, bus in network.buses.iterrows():
        if pd.isna(bus.x) or pd.isna(bus.y):
            continue
        raw = bus.get("location", "")
        key = (
            str(raw)
            if pd.notna(raw) and str(raw).strip()
            else membership.get(name, f"bus:{name}")
        )
        grouped.setdefault(key, []).append(str(name))
    for key in list(locations):
        if key not in grouped:
            del locations[key]
    for key, names in grouped.items():
        longitude, latitude = network.buses.loc[names, ["x", "y"]].mean()
        if key not in locations:
            locations[key] = NetworkLocation(
                key,
                names[0] if key.startswith("bus:") else key,
                float(longitude),
                float(latitude),
            )
        location = locations[key]
        location.bus_names = names
        location.longitude = float(longitude)
        location.latitude = float(latitude)


def serialise_locations(locations) -> list[dict]:
    return [asdict(location) for location in locations.values()]
