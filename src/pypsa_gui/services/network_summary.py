# src/pypsa_gui/services/network_summary.py
from __future__ import annotations

from pathlib import Path

import pypsa

def get_network_summary(network: pypsa.Network) -> dict[str, int]:
    return {
        "buses": len(network.buses),
        "generators": len(network.generators),
        "loads": len(network.loads),
        "lines": len(network.lines),
        "links": len(network.links),
        "stores": len(network.stores),
        "storage_units": len(network.storage_units),
    }