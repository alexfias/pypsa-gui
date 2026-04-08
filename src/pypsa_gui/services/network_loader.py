# src/pypsa_gui/services/network_loader.py
from pathlib import Path
import pypsa


def load_network_from_netcdf(path: str | Path) -> pypsa.Network:
    return pypsa.Network(str(path))


def load_network_from_csv_folder(path: str | Path) -> pypsa.Network:
    n = pypsa.Network()
    n.import_from_csv_folder(str(path))
    return n