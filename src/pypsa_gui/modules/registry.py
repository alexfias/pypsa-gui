# src/pypsa_gui/modules/registry.py
from __future__ import annotations

from pypsa_gui.modules.base import BaseResearchModule
from pypsa_gui.modules.flow_tracing.module import FlowTracingModule
#from pypsa_gui.modules.battery_degradation.module import BatteryDegradationModule
#from pypsa_gui.modules.reserves.module import ReservesModule
#from pypsa_gui.modules.scenario_generator.module import ScenarioGeneratorModule


def create_module_registry() -> list[BaseResearchModule]:
    return [
        FlowTracingModule(),
        #BatteryDegradationModule(),
        #ReservesModule(),
        #ScenarioGeneratorModule(),
    ]