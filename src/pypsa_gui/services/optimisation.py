from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pypsa

def run_network_optimisation(network: pypsa.Network):
    status = network.optimize(
        solver_name="gurobi",
        Method=2,
        Crossover=0,
    )
    return status


class OptimisationRunner:
    def __init__(self, network):
        self.network = network
        self._terminated = False

    def run(self):
        return self.network.optimize(
            solver_name="gurobi",
            Method=2,
            Crossover=0,
        )

    def terminate(self):
        if hasattr(self.network, "model") and self.network.model is not None:
            try:
                self.network.model.solver_model.terminate()
            except Exception:
                pass


class OptimisationWorker(QThread):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, runner):
        super().__init__()
        self.runner = runner

    def run(self):
        try:
            result = self.runner.run()
            self.finished.emit(result)
        except Exception as e:
            self.failed.emit(str(e))