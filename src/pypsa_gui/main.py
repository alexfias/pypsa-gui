import sys

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

import pypsa


from pypsa_gui.ui.main_window import MainWindow
from pypsa_gui.services.network_loader import (
    load_network_from_netcdf,
    load_network_from_csv_folder,
)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("pypsa-gui")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

def _open_netcdf_network(self) -> None:
    file_path, _ = QFileDialog.getOpenFileName(
        self,
        "Open PyPSA NetCDF Network",
        "",
        "NetCDF Files (*.nc);;All Files (*)",
    )
    if not file_path:
        return

    try:
        network = load_network_from_netcdf(file_path)
        self._set_network(network)
        self.statusBar().showMessage(f"Loaded network: {file_path}", 5000)
    except Exception as exc:
        QMessageBox.critical(self, "Load Error", f"Could not load network:\n{exc}")


def _open_csv_network(self) -> None:
    folder_path = QFileDialog.getExistingDirectory(
        self,
        "Open PyPSA CSV Folder",
        "",
    )
    if not folder_path:
        return

    try:
        network = load_network_from_csv_folder(folder_path)
        self._set_network(network)
        self.statusBar().showMessage(f"Loaded CSV network: {folder_path}", 5000)
    except Exception as exc:
        QMessageBox.critical(self, "Load Error", f"Could not load network:\n{exc}")

def _set_network(self, network: pypsa.Network) -> None:
    self.network = network
    self.central_panel.set_network(network)

if __name__ == "__main__":
    main()