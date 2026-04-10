# src/pypsa_gui/models/network_session.py

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pypsa


@dataclass
class NetworkSession:
    id: str
    name: str
    network: pypsa.Network
    source_path: Path | None = None
    is_modified: bool = False