from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


CO2PolicyMode = Literal[
    "none",
    "price",
    "relative_cap",
    "absolute_cap",
]


@dataclass(frozen=True)
class CO2Policy:
    mode: CO2PolicyMode = "none"
    value: float | None = None


@dataclass(frozen=True)
class TechnologySettings:
    enabled: bool = True
    capital_cost_multiplier: float = 1.0
    marginal_cost_multiplier: float = 1.0


@dataclass(frozen=True)
class ScenarioDefinition:
    name: str
    countries: tuple[str, ...]
    preset: str = "Reference"
    co2_policy: CO2Policy = field(
        default_factory=CO2Policy
    )
    technologies: dict[str, TechnologySettings] = field(
        default_factory=dict
    )
    demand_multiplier: float = 1.0
    allow_interconnection: bool = True