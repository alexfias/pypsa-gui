# src/pypsa_gui/models/network_session.py

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pypsa

from pypsa_gui.models.session_view import SessionViewOptions


@dataclass
class NetworkSession:
    id: str
    name: str
    network: pypsa.Network
    source_path: Path | None = None
    is_modified: bool = False
    view_options: SessionViewOptions = field(default_factory=SessionViewOptions)