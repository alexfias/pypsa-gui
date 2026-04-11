from __future__ import annotations

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QLineEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)


class ComponentTableModel(QAbstractTableModel):
    def __init__(self, component_name: str, network=None) -> None:
        super().__init__()
        self._component_name = component_name
        self._network = network
        self._rows: list[dict[str, object]] = []
        self._columns: list[str] = []
        self._editable_columns: set[str] = set()

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
            return "" if value is None or pd.isna(value) else str(value)

        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft | Qt.AlignVCenter

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

        column = self._columns[index.column()]
        if column not in self._editable_columns:
            return False

        row = self._rows[index.row()]
        component_id = row["name"]
        old_value = row.get(column, "")

        if column == "name":
            new_name = str(value).strip()
            if not new_name:
                return False

            old_name = row["name"]

            if new_name == old_name:
                return True

            if self._network is None:
                return False

            df = getattr(self._network, self._component_name, None)
            if df is None:
                return False

            if new_name in df.index:
                return False

            df.rename(index={old_name: new_name}, inplace=True)
            self._rows[index.row()]["name"] = new_name

            self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
            return True

        try:
            parsed_value = self._parse_value(value, old_value)
        except ValueError:
            return False

        self._rows[index.row()][column] = parsed_value

        if self._network is not None:
            df = getattr(self._network, self._component_name, None)
            if df is not None and component_id in df.index and column in df.columns:
                df.at[component_id, column] = parsed_value

        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
        return True

    def _parse_value(self, value, old_value):
        text = str(value).strip()

        if text == "":
            if old_value is None or pd.isna(old_value):
                return None
            return ""

        if isinstance(old_value, bool):
            return text.lower() in {"true", "1", "yes"}

        if isinstance(old_value, int) and not isinstance(old_value, bool):
            return int(text)

        if isinstance(old_value, float):
            return float(text)

        return text

    def set_table_data(
        self,
        rows: list[dict[str, object]],
        columns: list[str],
        editable_columns: set[str],
        network=None,
    ) -> None:
        self.beginResetModel()
        self._rows = rows
        self._columns = columns
        self._editable_columns = editable_columns
        self._network = network
        self.endResetModel()


class ComponentFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._filter_text = ""

    def set_filter_text(self, text: str) -> None:
        self._filter_text = text.casefold().strip()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self._filter_text:
            return True

        model = self.sourceModel()
        if model is None:
            return True

        for column in range(model.columnCount()):
            index = model.index(source_row, column, source_parent)
            value = model.data(index, Qt.DisplayRole)
            if value is not None and self._filter_text in str(value).casefold():
                return True

        return False


class ComponentPage(QWidget):
    def __init__(self, component_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.component_name = component_name
        self.network = None

        self.model = ComponentTableModel(component_name=component_name)

        self.proxy_model = ComponentFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search table...")
        self.search_box.textChanged.connect(self.proxy_model.set_filter_text)

        self.table = QTableView()
        self.table.setModel(self.proxy_model)

        self.table.setSortingEnabled(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setEditTriggers(QTableView.DoubleClicked | QTableView.EditKeyPressed)

        self.table.setHorizontalScrollMode(QTableView.ScrollPerPixel)
        self.table.setVerticalScrollMode(QTableView.ScrollPerPixel)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideRight)

        self.table.verticalHeader().setDefaultSectionSize(24)

        horizontal_header = self.table.horizontalHeader()
        horizontal_header.setSectionResizeMode(QHeaderView.Interactive)
        horizontal_header.setStretchLastSection(False)
        horizontal_header.setMinimumSectionSize(80)
        horizontal_header.setMaximumSectionSize(300)

        layout = QVBoxLayout(self)
        layout.addWidget(self.search_box)
        layout.addWidget(self.table)

    def set_network(self, network) -> None:
        self.network = network
        self.refresh()

    def refresh(self) -> None:
        if self.network is None:
            self.model.set_table_data([], [], set(), None)
            return

        df = getattr(self.network, self.component_name, None)
        if df is None:
            self.model.set_table_data([], [], set(), None)
            return

        df_reset = df.reset_index()
        columns = list(df_reset.columns)

        if "name" not in columns and len(columns) > 0:
            first_column = columns[0]
            rows: list[dict[str, object]] = []
            for _, row in df_reset.iterrows():
                row_dict = {column: row.get(column, "") for column in df_reset.columns}
                row_dict["name"] = row.get(first_column, "")
                rows.append(row_dict)

            columns = ["name"] + [col for col in columns if col != first_column]
        else:
            rows = []
            for _, row in df_reset.iterrows():
                rows.append({column: row.get(column, "") for column in columns})

        editable_columns = set(columns)

        self.model.set_table_data(rows, columns, editable_columns, self.network)

        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()

        name_column_index = columns.index("name") if "name" in columns else -1
        if name_column_index >= 0:
            self.table.setColumnWidth(name_column_index, 180)