# src/pypsa_gui/services/network_io.py
from __future__ import annotations

from pathlib import Path
from copy import deepcopy
import os
import tempfile

import pypsa

from pypsa_gui.services.locations import LOCATION_META_KEY, serialise_locations


def load_network_from_netcdf(path: str | Path) -> pypsa.Network:
    return pypsa.Network(str(path))


def load_network_from_csv_folder(path: str | Path) -> pypsa.Network:
    network = pypsa.Network()
    network.import_from_csv_folder(str(path))
    return network


def save_network_to_netcdf(
    network: pypsa.Network, path: str | Path, *, locations=None
) -> None:
    """Replace a saved network only after a complete successful export."""
    if getattr(network, "_gui_edit_locked", False):
        raise ValueError("Wait for optimisation to finish before saving this network.")
    path = Path(path)
    original_meta = deepcopy(network.meta)
    if locations is not None:
        network.meta[LOCATION_META_KEY] = serialise_locations(locations)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=f".{path.stem}-", suffix=".nc", delete=False
        ) as stream:
            temporary = Path(stream.name)
        network.export_to_netcdf(str(temporary))
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        network.meta = original_meta
        raise
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
