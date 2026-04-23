from __future__ import annotations

import pypsa
from PySide6.QtWidgets import QWidget

from pypsa_gui.modules.base import BaseResearchModule, ModulePageDefinition
from pypsa_gui.modules.ml_surrogate.page import MLSurrogatePage


class MLSurrogateModule(BaseResearchModule):
    id = "ml_surrogate"
    name = "ML Surrogate"

    def __init__(self) -> None:
        super().__init__()
        self._page: MLSurrogatePage | None = None

    def set_network(self, network: pypsa.Network | None) -> None:
        super().set_network(network)
        if self._page is not None:
            self._page.set_network(network)

    def get_pages(self) -> list[ModulePageDefinition]:
        return [
            ModulePageDefinition(
                key="ml_surrogate",
                title="ML Surrogate",
                section="research_modules",
                order=20,
            )
        ]

    def create_page(self, page_key: str, parent: QWidget | None = None) -> QWidget:
        if page_key != "ml_surrogate":
            raise ValueError(f"Unknown page key for {self.name}: {page_key}")

        if self._page is None:
            self._page = MLSurrogatePage(parent)
            self._page.set_network(self.network)

        return self._page