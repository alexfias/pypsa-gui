# src/pypsa_gui/workflows/operations.py

from __future__ import annotations

from enum import StrEnum


class WorkflowOperation(StrEnum):
    LOAD_NETWORK = "load_network"
    CREATE_SCENARIO = "create_scenario"
    CREATE_EMPTY_NETWORK = "create_empty_network"
    MODIFY_NETWORK = "modify_network"
    OPTIMIZE = "optimize"
    EXPORT_NETWORK = "export_network"
    EXPORT_REPORT = "export_report"