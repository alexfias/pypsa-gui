from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TechnologyPreset:
    id: str
    name: str
    component_type: str
    carrier: str

    capital_cost: float
    marginal_cost: float
    efficiency: float
    lifetime: float

    p_nom_extendable: bool = True
    default_p_max_pu: float = 1.0
    profile_carrier: str | None = None

    category: str = "Other"
    description: str = ""
    source_provider: str | None = None
    source_year: int | None = None
    source_reference: str | None = None

    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def is_variable_renewable(self) -> bool:
        return self.profile_carrier is not None
