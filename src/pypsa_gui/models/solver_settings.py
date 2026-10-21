# src/pypsa_gui/models/solver_settings.py
from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite


@dataclass
class SolverSettings:
    solver_name: str = "highs"

    assign_all_duals: bool = True
    transmission_losses: bool = False
    linearized_unit_commitment: bool = False

    # Shared method codes: 0 = primal simplex, 1 = dual simplex, 2 = IPM.
    # Gurobi additionally supports concurrent methods 3 and 4 here.
    method: int | None = None
    crossover: int | None = None
    presolve: int | None = None
    threads: int | None = None
    time_limit: float | None = None
    mip_gap: float | None = None
    feasibility_tol: float | None = None
    optimality_tol: float | None = None

    extra_solver_options: dict[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if self.solver_name not in {"highs", "gurobi"}:
            raise ValueError(f"Unsupported solver: {self.solver_name}")

        choices = {
            "method": (
                {None, 0, 1, 2, 3, 4}
                if self.solver_name == "gurobi"
                else {None, 0, 1, 2}
            ),
            "crossover": {None, 0, 1},
            "presolve": (
                {None, 0, 1, 2} if self.solver_name == "gurobi" else {None, 0, 1}
            ),
        }
        for name, allowed in choices.items():
            value = getattr(self, name)
            if value not in allowed:
                raise ValueError(f"Invalid {name} for {self.solver_name}: {value}")

        if self.threads is not None and (
            type(self.threads) is not int or self.threads < 1
        ):
            raise ValueError("Threads must be a positive integer or Auto.")

        for name in ("time_limit", "mip_gap", "feasibility_tol", "optimality_tol"):
            value = getattr(self, name)
            if value is None:
                continue
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
                or value < 0
                or (name.endswith("_tol") and value == 0)
            ):
                raise ValueError(f"Invalid {name}: {value}")

        if not isinstance(self.extra_solver_options, dict):
            raise ValueError("Extra solver options must be a JSON object, e.g. {}.")
        reserved = {
            "solver_name",
            "solver_options",
            "assign_all_duals",
            "transmission_losses",
            "linearized_unit_commitment",
            "extra_functionality",
            "io_api",
            "env",
            "remote",
            "problem_fn",
            "solution_fn",
            "log_to_console",
            "warmstart_fn",
            "basis_fn",
            "solver_dir",
        }
        for key, value in self.extra_solver_options.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("Solver option names must be non-empty strings.")
            if key in reserved:
                raise ValueError(f"{key!r} is not a native solver option.")
            if not isinstance(value, (str, bool, int, float)) or (
                isinstance(value, float) and not isfinite(value)
            ):
                raise ValueError(
                    f"Solver option {key!r} must have a finite scalar value."
                )

    def to_model_options(self) -> dict[str, bool]:
        self.validate()
        return {
            "transmission_losses": self.transmission_losses,
            "linearized_unit_commitment": self.linearized_unit_commitment,
        }

    def to_solver_options(self) -> dict[str, object]:
        self.validate()
        options: dict[str, object] = {}

        if self.solver_name == "gurobi":
            names = {
                "method": "Method",
                "crossover": "Crossover",
                "presolve": "Presolve",
                "threads": "Threads",
                "time_limit": "TimeLimit",
                "mip_gap": "MIPGap",
                "feasibility_tol": "FeasibilityTol",
                "optimality_tol": "OptimalityTol",
            }
        else:
            names = {
                "threads": "threads",
                "time_limit": "time_limit",
                "mip_gap": "mip_rel_gap",
                "feasibility_tol": "primal_feasibility_tolerance",
                "optimality_tol": "dual_feasibility_tolerance",
            }
            if self.method is not None:
                options["solver"] = "ipm" if self.method == 2 else "simplex"
                if self.method in {0, 1}:
                    options["simplex_strategy"] = 4 if self.method == 0 else 1
            if self.crossover is not None:
                options["run_crossover"] = "on" if self.crossover else "off"
            if self.presolve is not None:
                options["presolve"] = "on" if self.presolve else "off"

        for field_name, native_name in names.items():
            value = getattr(self, field_name)
            if value is not None:
                options[native_name] = value

        options.update(self.extra_solver_options)
        return options
