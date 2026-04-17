from __future__ import annotations

import pypsa
from PySide6.QtWidgets import QWidget

from pypsa_gui.modules.base import BaseResearchModule, ModulePageDefinition
from pypsa_gui.modules.flow_tracing.page import FlowTracingPage


class FlowTracingModule(BaseResearchModule):
    id = "flow_tracing"
    name = "Flow Tracing"

    def is_available(self, network: pypsa.Network | None) -> bool:
        return network is not None

    def get_pages(self) -> list[ModulePageDefinition]:
        return [
            ModulePageDefinition(
                key="flow_tracing",
                title="Flow Tracing",
                section="research_modules",
                order=10,
            )
        ]

    def create_page(self, page_key: str, parent: QWidget | None = None) -> QWidget:
        page = FlowTracingPage(parent=parent)
        page.set_network(self.network)
        return page