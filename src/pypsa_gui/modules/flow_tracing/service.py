# src/pypsa_gui/modules/flow_tracing/service.py
from __future__ import annotations

import pypsa

from pypsa_gui.modules.flow_tracing.adapter import extract_flow_tracing_inputs
from pypsa_gui.modules.flow_tracing.models import FlowTracingPreviewResult


def preview_flow_tracing(network: pypsa.Network) -> FlowTracingPreviewResult:
    inputs = extract_flow_tracing_inputs(network)

    text = (
        "Flow Tracing Module Preview\n"
        f"- Snapshots: {inputs.n_snapshots}\n"
        f"- Buses: {inputs.n_buses}\n"
        f"- Links: {inputs.n_links}\n"
        f"- Injections shape: {inputs.injections.shape}\n"
        f"- Loads shape: {inputs.loads.shape}\n"
        f"- Link flows shape: {inputs.link_flows.shape}\n"
        f"- Incidence shape: {inputs.incidence.shape}\n"
    )

    return FlowTracingPreviewResult(summary_text=text)