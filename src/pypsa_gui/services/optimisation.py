from __future__ import annotations

from dataclasses import dataclass

import pypsa


@dataclass
class OptimisationPreview:
    variables: int
    constraints: int
    nonzeros: int | None
    matrix_rows: int | None
    matrix_cols: int | None
    matrix_density: float | None
    status: str


def run_network_optimisation(network: pypsa.Network):
    network.optimize.create_model()
    return network.optimize.solve_model(
        solver_name="gurobi",
        Method=2,
        Crossover=0,
    )


def preview_network_optimisation(network: pypsa.Network) -> OptimisationPreview:
    network.optimize.create_model()

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

    return OptimisationPreview(
        variables=variables,
        constraints=constraints,
        nonzeros=nonzeros,
        matrix_rows=matrix_rows,
        matrix_cols=matrix_cols,
        matrix_density=matrix_density,
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
    def __init__(self, network: pypsa.Network) -> None:
        self.network = network

    def run(self):
        return run_network_optimisation(self.network)

    def preview(self) -> OptimisationPreview:
        return preview_network_optimisation(self.network)

    def cancel(self) -> tuple[bool, str]:
        model = getattr(self.network, "model", None)
        if model is None:
            return False, "network.model is None"

        solver_model = getattr(model, "solver_model", None)
        if solver_model is None:
            return False, "network.model.solver_model is None"

        terminate = getattr(solver_model, "terminate", None)
        if terminate is None:
            return False, "solver_model has no terminate() method"

        terminate()
        return True, "Cancellation requested."