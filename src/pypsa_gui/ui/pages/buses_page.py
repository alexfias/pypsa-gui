from __future__ import annotations

from pypsa_gui.ui.pages.component_page import ComponentPage


class BusesPage(ComponentPage):
    def __init__(self) -> None:
        super().__init__("buses")