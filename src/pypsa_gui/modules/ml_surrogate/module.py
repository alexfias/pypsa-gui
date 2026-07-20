from __future__ import annotations

import pypsa
from PySide6.QtWidgets import QWidget

from pypsa_gui.modules.base import BaseResearchModule, ModulePageDefinition
from pypsa_gui.modules.ml_surrogate.page import MLSurrogatePage


class MLSurrogateModule(BaseResearchModule):
    id = "ml_surrogate"
    name = "ML Surrogate"

    def set_network(self, network: pypsa.Network | None) -> None:
        # Only store the network in the module.
        # Do not try to update a previously created page,
        # because that page may already have been deleted by Qt.
        super().set_network(network)

    def get_pages(self) -> list[ModulePageDefinition]:
        return [
            ModulePageDefinition(
                key="ml_surrogate",
                title="ML Surrogate",
                section="research_modules",
                order=20,
            )
        ]

    def create_page(
        self,
        page_key: str,
        parent: QWidget | None = None,
    ) -> QWidget:
        if page_key != "ml_surrogate":
            raise ValueError(
                f"Unknown page key for {self.name}: {page_key}"
            )

        # Always create a fresh widget.
        page = MLSurrogatePage(parent)
        page.set_network(self.network)
        return page