from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class WorkflowStep:
    """One scientific workflow operation."""

    operation: str
    parameters: dict[str, Any]


@dataclass
class WorkflowRecord:
    """Scientific workflow consisting of ordered operations."""

    schema_version: int = 1
    framework: str = "pypsa"
    interface: str = "pypsa-gui"

    source: dict[str, Any] = field(default_factory=dict)

    steps: list[WorkflowStep] = field(default_factory=list)

    def add_step(self, operation: str, parameters: dict[str, Any]) -> None:
        self.steps.append(
            WorkflowStep(
                operation=operation,
                parameters=parameters,
            )
        )

    def clear(self) -> None:
        self.steps.clear()