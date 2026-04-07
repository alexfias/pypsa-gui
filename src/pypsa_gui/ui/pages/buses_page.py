from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import QHeaderView, QTableView, QVBoxLayout, QWidget


class BusesTableModel(QAbstractTableModel):
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        super().__init__()
        self._columns = ["name", "carrier", "unit", "v_nom", "x", "y"]
        self._rows = rows or []

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

        if role == Qt.DisplayRole:
            return str(value)

        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            return self._columns[section].replace("_", " ").title()

        return str(section + 1)

    def set_rows(self, rows: list[dict[str, object]]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()


class BusesPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.network = None

        demo_rows = [
            {"name": "Bus 1", "carrier": "AC", "unit": "MW", "v_nom": 220, "x": 10.5, "y": 50.1},
            {"name": "Bus 2", "carrier": "AC", "unit": "MW", "v_nom": 220, "x": 11.2, "y": 51.0},
            {"name": "Bus 3", "carrier": "DC", "unit": "MW", "v_nom": 320, "x": 12.7, "y": 49.8},
        ]

        self.model = BusesTableModel(demo_rows)
        self.table = QTableView()
        self.table.setModel(self.model)

        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setEditTriggers(QTableView.NoEditTriggers)

        horizontal_header = self.table.horizontalHeader()
        horizontal_header.setSectionResizeMode(QHeaderView.Stretch)

        layout = QVBoxLayout()
        layout.addWidget(self.table)
        self.setLayout(layout)

    def set_network(self, network) -> None:
        self.network = network
        self.refresh()

    def refresh(self) -> None:
        if self.network is None:
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

        self.model.set_rows(rows)

    def set_network(self, network) -> None:
        self.network = network
        self.refresh()