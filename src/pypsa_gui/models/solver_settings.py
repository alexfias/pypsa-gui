# src/pypsa_gui/models/solver_settings.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SolverSettings:
    solver_name: str = "gurobi"

    assign_all_duals: bool = True
    transmission_losses: bool = False
    linearized_unit_commitment: bool = False

    method: int | None = 2
    crossover: int | None = 0
    presolve: int | None = None
    threads: int | None = None
    time_limit: float | None = None
    mip_gap: float | None = None
    feasibility_tol: float | None = None
    optimality_tol: float | None = None

    extra_solver_options: dict[str, object] = field(default_factory=dict)

    def to_solver_options(self) -> dict[str, object]:
        options: dict[str, object] = {}

        if self.method is not None:
            options["Method"] = self.method
        if self.crossover is not None:
            options["Crossover"] = self.crossover
        if self.presolve is not None:
            options["Presolve"] = self.presolve
        if self.threads is not None:
            options["Threads"] = self.threads
        if self.time_limit is not None:
            options["TimeLimit"] = self.time_limit
        if self.mip_gap is not None:
            options["MIPGap"] = self.mip_gap
        if self.feasibility_tol is not None:
            options["FeasibilityTol"] = self.feasibility_tol
        if self.optimality_tol is not None:
            options["OptimalityTol"] = self.optimality_tol

        options.update(self.extra_solver_options)
        return options