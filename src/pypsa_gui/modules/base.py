# src/pypsa_gui/modules/base.py
from __future__ import annotations

from dataclasses import dataclass

import pypsa
from PySide6.QtWidgets import QWidget


@dataclass
class ModulePageDefinition:
    key: str
    title: str
    section: str = "research_modules"
    order: int = 100


class BaseResearchModule:
    id = "base"
    name = "Base Module"

    def __init__(self) -> None:
        self.network: pypsa.Network | None = None

    def set_network(self, network: pypsa.Network | None) -> None:
        self.network = network

    def is_available(self, network: pypsa.Network | None) -> bool:
        return network is not None

    def get_pages(self) -> list[ModulePageDefinition]:
        return []

    def create_page(self, page_key: str, parent: QWidget | None = None) -> QWidget:
        raise NotImplementedError