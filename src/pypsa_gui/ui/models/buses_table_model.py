from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal


from pypsa_gui.services.network_edits import edit_component, edit_block_reason


class BusesTableModel(QAbstractTableModel):
    edit_applied = Signal(object)
    edit_rejected = Signal(str)

    def __init__(self, network=None) -> None:
        super().__init__()
        self.network = network
        self.columns = ["carrier", "x", "y", "v_nom", "control"]

    def set_network(self, network) -> None:
        self.beginResetModel()
        self.network = network
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid() or self.network is None:
            return 0
        return len(self.network.buses)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or self.network is None:
            return None

        if role not in (Qt.DisplayRole, Qt.EditRole):
            return None

        bus_name = self.network.buses.index[index.row()]
        column = self.columns[index.column()]
        value = self.network.buses.at[bus_name, column]

        if value is None:
            return ""
        return str(value)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ):
        if role != Qt.DisplayRole or self.network is None:
            return None

        if orientation == Qt.Horizontal:
            return self.columns[section]

        if orientation == Qt.Vertical:
            return self.network.buses.index[section]

        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemIsEnabled

        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if self.network is not None and not edit_block_reason(
            self.network,
            "buses",
            self.network.buses.index[index.row()],
            self.columns[index.column()],
        ):
            flags |= Qt.ItemIsEditable
        return flags

    def setData(self, index: QModelIndex, value, role: int = Qt.EditRole) -> bool:
        if role != Qt.EditRole or not index.isValid() or self.network is None:
            return False

        bus_name = self.network.buses.index[index.row()]
        column = self.columns[index.column()]

        try:
            change = edit_component(self.network, "buses", bus_name, column, value)
        except (ValueError, TypeError, KeyError) as exc:
            self.edit_rejected.emit(str(exc))
            return False
        if change is not None:
            self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
            self.edit_applied.emit(change)
        return True
