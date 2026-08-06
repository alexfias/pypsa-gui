# src/pypsa_gui/models/network_session.py

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pypsa

from pypsa_gui.models.network_location import NetworkLocation
from pypsa_gui.models.session_view import SessionViewOptions
from pypsa_gui.workflows.models import WorkflowRecord


@dataclass
class NetworkSession:
    id: str
    name: str
    network: pypsa.Network
    source_path: Path | None = None
    is_modified: bool = False

    view_options: SessionViewOptions = field(
        default_factory=SessionViewOptions
    )

    locations: dict[str, NetworkLocation] = field(
        default_factory=dict
    )

    workflow: WorkflowRecord = field(
        default_factory=WorkflowRecord
    )