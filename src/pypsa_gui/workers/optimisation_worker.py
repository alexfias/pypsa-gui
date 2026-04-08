from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from pypsa_gui.services.optimisation import OptimisationRunner


class OptimisationWorker(QThread):
    finished_successfully = Signal(object)
    failed = Signal(str)

    def __init__(self, runner: OptimisationRunner) -> None:
        super().__init__()
        self.runner = runner

    def run(self) -> None:
        try:
            status = self.runner.run()
            self.finished_successfully.emit(status)
        except Exception as exc:
            self.failed.emit(str(exc))