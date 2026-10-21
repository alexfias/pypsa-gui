from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy

import linopy
import pypsa

from pypsa_gui.models.solver_settings import SolverSettings


@dataclass
class OptimisationPreview:
    variables: int
    constraints: int
    nonzeros: int | None
    matrix_rows: int | None
    matrix_cols: int | None
    matrix_density: float | None
    estimated_ram_low_gb: float | None
    estimated_ram_high_gb: float | None
    status: str


def validate_solver_configuration(settings: SolverSettings) -> dict[str, object]:
    """Reject unavailable solvers and invalid HiGHS options before model creation."""
    options = settings.to_solver_options()
    if settings.solver_name not in linopy.available_solvers:
        package = "highspy" if settings.solver_name == "highs" else "gurobipy"
        message = (
            f"{settings.solver_name} is not available. Install {package} in the "
            "environment running pypsa-gui, then restart the application."
        )
        if settings.solver_name == "gurobi":
            message += " Gurobi also requires a suitable licence; you can select HiGHS instead."
        raise ValueError(message)

    if settings.solver_name == "highs":
        import highspy

        checker = highspy.Highs()
        checker.setOptionValue("output_flag", False)
        # Linopy does not check setOptionValue's return code. Validate explicitly
        # so a misspelled option cannot silently leave the solver at its default.
        for key in sorted(options, key=lambda name: name == "output_flag"):
            try:
                status = checker.setOptionValue(key, options[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid HiGHS option {key!r}: {options[key]!r}"
                ) from exc
            if status != highspy.HighsStatus.kOk:
                raise ValueError(
                    f"Invalid HiGHS option {key!r}: {options[key]!r}. "
                    "Use native HiGHS option names and valid values."
                )
    return options


def run_network_optimisation(
    network: pypsa.Network,
    settings: SolverSettings | None = None,
):
    settings = deepcopy(settings) if settings is not None else SolverSettings()
    options = validate_solver_configuration(settings)
    network.optimize.create_model(**settings.to_model_options())
    if settings.solver_name == "highs":
        # Forcing an LP algorithm in HiGHS can drop integer/quadratic terms.
        if options.get("solver", "choose") != "choose" and network.model.type != "LP":
            raise ValueError(
                "Use Automatic method for mixed-integer or quadratic HiGHS models "
                "and remove any 'solver' override from Extra solver options. "
                "A forced LP method could ignore integrality or quadratic terms."
            )
        import highspy

        # The GUI runs one optimisation at a time. HiGHS keeps a process-wide
        # thread pool; reset it between runs so changes to Threads take effect.
        reset_scheduler = getattr(highspy.Highs, "resetGlobalScheduler", None)
        if callable(reset_scheduler):
            reset_scheduler(True)
    return network.optimize.solve_model(
        solver_name=settings.solver_name,
        solver_options=options,
        assign_all_duals=settings.assign_all_duals,
    )


def preview_network_optimisation(
    network: pypsa.Network,
    settings: SolverSettings | None = None,
) -> OptimisationPreview:
    settings = settings if settings is not None else SolverSettings()
    network.optimize.create_model(**settings.to_model_options())

    model = getattr(network, "model", None)
    if model is None:
        raise RuntimeError("PyPSA did not attach a model to network.model.")

    variables = int(getattr(model, "nvars", 0) or 0)
    constraints = int(getattr(model, "ncons", 0) or 0)

    nonzeros: int | None = None
    matrix_rows: int | None = None
    matrix_cols: int | None = None
    matrix_density: float | None = None

    try:
        matrix = model.constraints.to_matrix()
        matrix_rows, matrix_cols = matrix.shape
        nonzeros = int(matrix.nnz)

        if matrix_rows > 0 and matrix_cols > 0:
            matrix_density = nonzeros / (matrix_rows * matrix_cols)
    except Exception:
        pass

    ram_low, ram_high = _estimate_lp_ram_gb(
        nonzeros,
        variables,
        constraints,
    )

    return OptimisationPreview(
        variables=variables,
        constraints=constraints,
        nonzeros=nonzeros,
        matrix_rows=matrix_rows,
        matrix_cols=matrix_cols,
        matrix_density=matrix_density,
        estimated_ram_low_gb=ram_low,
        estimated_ram_high_gb=ram_high,
        status=_classify_model_size(variables, constraints),
    )


def _classify_model_size(variables: int, constraints: int) -> str:
    size = variables + constraints
    if size < 100_000:
        return "Small"
    if size < 1_000_000:
        return "Medium"
    if size < 5_000_000:
        return "Large"
    return "Very Large"


class OptimisationRunner:
    def __init__(
        self,
        network: pypsa.Network,
        settings: SolverSettings | None = None,
    ) -> None:
        self.network = network
        # Each run owns a snapshot; subsequent UI edits cannot alter its options.
        self.settings = deepcopy(settings) if settings is not None else SolverSettings()

    def validate(self) -> None:
        validate_solver_configuration(self.settings)

    def run(self):
        return run_network_optimisation(self.network, self.settings)

    def preview(self) -> OptimisationPreview:
        return preview_network_optimisation(self.network, self.settings)

    def cancel(self) -> tuple[bool, str]:
        model = getattr(self.network, "model", None)
        if model is None:
            return False, "network.model is None"

        solver_model = getattr(model, "solver_model", None)
        if solver_model is None:
            return False, "network.model.solver_model is None"

        for method in ("terminate", "cancelSolve"):
            terminate = getattr(solver_model, method, None)
            if callable(terminate):
                try:
                    terminate()
                except Exception as exc:
                    return False, f"Solver could not accept cancellation: {exc}"
                return True, "Cancellation requested."
        return False, "The running solver does not expose a cancellation method."


def _estimate_lp_ram_gb(
    nonzeros: int | None,
    variables: int,
    constraints: int,
) -> tuple[float | None, float | None]:
    if nonzeros is None:
        return None, None

    # Base sparse matrix + vectors
    base_bytes = nonzeros * 24 + variables * 16 + constraints * 16

    # Solver overhead (LP, barrier-ish)
    low_bytes = base_bytes * 3.0
    high_bytes = base_bytes * 8.0

    gb = 1024**3
    return low_bytes / gb, high_bytes / gb
