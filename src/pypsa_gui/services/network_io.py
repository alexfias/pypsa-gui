# src/pypsa_gui/services/network_io.py
from __future__ import annotations

from pathlib import Path

import pypsa


def load_network_from_netcdf(path: str | Path) -> pypsa.Network:
    return pypsa.Network(str(path))


def load_network_from_csv_folder(path: str | Path) -> pypsa.Network:
    network = pypsa.Network()
    network.import_from_csv_folder(str(path))
    return network


def save_network_to_netcdf(network: pypsa.Network, path: str | Path) -> None:
    network.export_to_netcdf(str(path))