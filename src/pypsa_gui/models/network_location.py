from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NetworkLocation:
    id: str
    name: str
    longitude: float
    latitude: float
    bus_names: list[str] = field(
        default_factory=list
    )