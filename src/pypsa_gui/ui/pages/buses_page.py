from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import QHeaderView, QTableView, QVBoxLayout, QWidget


class BusesTableModel(QAbstractTableModel):
    def __init__(self, rows: list[dict[str, object]] | None = None, network=None) -> None:
        super().__init__()
        self._columns = ["name", "carrier", "unit", "v_nom", "x", "y"]
        self._editable_columns = {"carrier", "unit", "v_nom", "x", "y"}
        self._rows = rows or []
        self._network = network

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None

        row = self._rows[index.row()]
        column = self._columns[index.column()]
        value = row.get(column, "")

        if role in (Qt.DisplayRole, Qt.EditRole):
            return "" if value is None else str(value)

        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            return self._columns[section].replace("_", " ").title()

        return str(section + 1)

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemIsEnabled

        column = self._columns[index.column()]
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable

        if column in self._editable_columns:
            flags |= Qt.ItemIsEditable

        return flags

    def setData(self, index: QModelIndex, value, role: int = Qt.EditRole) -> bool:
        if role != Qt.EditRole or not index.isValid():
            return False

        row = self._rows[index.row()]
        column = self._columns[index.column()]

        if column not in self._editable_columns:
            return False

        bus_name = row["name"]

        try:
            if column in {"v_nom", "x", "y"}:
                parsed_value = float(value)
            else:
                parsed_value = str(value).strip()
        except ValueError:
            return False

        self._rows[index.row()][column] = parsed_value

        if self._network is not None and bus_name in self._network.buses.index:
            self._network.buses.at[bus_name, column] = parsed_value

        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
        return True

    def set_rows(self, rows: list[dict[str, object]], network=None) -> None:
        self.beginResetModel()
        self._rows = rows
        self._network = network
        self.endResetModel()


class BusesPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.network = None

        self.model = BusesTableModel()
        self.table = QTableView()
        self.table.setModel(self.model)

        self.table.setSortingEnabled(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setEditTriggers(QTableView.DoubleClicked | QTableView.EditKeyPressed)

        horizontal_header = self.table.horizontalHeader()
        horizontal_header.setSectionResizeMode(QHeaderView.Stretch)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)

    def set_network(self, network) -> None:
        self.network = network
        self.refresh()

    def refresh(self) -> None:
        if self.network is None:
            self.model.set_rows([], None)
            return

        buses = self.network.buses.reset_index()

        rows: list[dict[str, object]] = []
        for _, bus in buses.iterrows():
            rows.append(
                {
                    "name": bus.get("name", ""),
                    "carrier": bus.get("carrier", ""),
                    "unit": bus.get("unit", ""),
                    "v_nom": bus.get("v_nom", ""),
                    "x": bus.get("x", ""),
                    "y": bus.get("y", ""),
                }
            )

        self.model.set_rows(rows, self.network)