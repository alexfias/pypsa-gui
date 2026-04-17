# src/pypsa_gui/modules/flow_tracing/models.py
from __future__ import annotations

from dataclasses import dataclass
import pandas as pd
import numpy as np


@dataclass
class FlowTracingPreviewResult:
    summary_text: str


@dataclass
class FlowTracingRunResult:
    average_export_matrix: pd.DataFrame
    average_link_loading: pd.Series
    bus_names: list[str]
    link_names: list[str]
    n_snapshots: int