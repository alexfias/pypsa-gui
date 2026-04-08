from __future__ import annotations

import pypsa


def run_network_optimisation(network: pypsa.Network):
    network.optimize.create_model()
    return network.optimize.solve_model(
        solver_name="gurobi",
        Method=2,
        Crossover=0,
    )


class OptimisationRunner:
    def __init__(self, network: pypsa.Network) -> None:
        self.network = network

    def run(self):
        return run_network_optimisation(self.network)

    def cancel(self) -> tuple[bool, str]:
        model = getattr(self.network, "model", None)
        if model is None:
            return False, "network.model is None"

        print("model type:", type(model))
        print("model dir:", dir(model))

        solver_model = getattr(model, "solver_model", None)
        print("solver_model:", solver_model)

        if solver_model is None:
            return False, "network.model.solver_model is None"

        terminate = getattr(solver_model, "terminate", None)
        if terminate is None:
            return False, "solver_model has no terminate() method"

        terminate()
        return True, "Cancellation requested."