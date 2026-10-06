from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QSplitter, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)
from pypsa_gui.ui.pages.component_page import ComponentPage
from pypsa_gui.ui.widgets.figure_panel import FigurePanel
from pypsa_gui.visualization.bus_diagram import render_bus_diagram


class BusesPage(ComponentPage):
    def __init__(self) -> None:
        super().__init__("buses")
        # Preserve the existing editable table and its filtering/copy controls.
        outer = self.layout()
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        while outer.count():
            table_layout.addItem(outer.takeAt(0))
        for widget in (self.search_box, self.columns_button, self.filter_label,
                       self.clear_bus_filter_button, self.table):
            widget.setParent(table_widget)
        self.tabs = QTabWidget()
        diagram = QWidget()
        diagram_layout = QVBoxLayout(diagram)
        split = QSplitter(Qt.Horizontal)
        left = QWidget(); left_layout = QVBoxLayout(left)
        self.bus_search = QLineEdit(); self.bus_search.setPlaceholderText("Search buses / voltage…")
        self.bus_list = QListWidget()
        left_layout.addWidget(self.bus_search); left_layout.addWidget(self.bus_list)
        centre = QWidget(); centre_layout = QVBoxLayout(centre)
        self.panel = FigurePanel("Local single-line diagram", minimum_canvas_height=380)
        self.panel.legend_checkbox.hide()
        centre_layout.addWidget(self.panel, 1)
        controls = QHBoxLayout()
        self.previous = QPushButton("Previous feeders")
        self.next = QPushButton("Next feeders")
        self.page_label = QLabel()
        controls.addWidget(self.previous); controls.addWidget(self.page_label); controls.addWidget(self.next)
        centre_layout.addLayout(controls)
        self.hint = QLabel("Click a neighbouring bus to navigate; click equipment for parameters.\nStatic topology · one connection away · export shows the current feeder page.")
        self.hint.setWordWrap(True); centre_layout.addWidget(self.hint)
        right = QWidget(); right_layout = QVBoxLayout(right)
        self.detail_title = QLabel("Component details"); self.detail_title.setWordWrap(True)
        self.details = QTableWidget(0, 2)
        self.details.setHorizontalHeaderLabels(["Parameter", "Value"])
        self.details.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.details.horizontalHeader().setStretchLastSection(True)
        right_layout.addWidget(self.detail_title); right_layout.addWidget(self.details)
        split.addWidget(left); split.addWidget(centre); split.addWidget(right)
        split.setSizes([190, 800, 260]); split.setStretchFactor(1, 1)
        diagram_layout.addWidget(split)
        self.tabs.addTab(diagram, "Diagram"); self.tabs.addTab(table_widget, "Table")
        outer.addWidget(self.tabs)
        self.selected_bus = None
        self.feeder_page = 0
        self.targets = {}
        self.bus_search.textChanged.connect(self._filter_list)
        self.bus_list.currentItemChanged.connect(self._bus_changed)
        self.previous.clicked.connect(lambda: self._change_page(-1))
        self.next.clicked.connect(lambda: self._change_page(1))
        self.panel.title_edit.editingFinished.connect(self._draw)
        self.panel.canvas.mpl_connect("pick_event", self._picked)
        self.tabs.currentChanged.connect(self._tab_changed)
        self.table.selectionModel().currentChanged.connect(self._table_selected)
        self._draw()

    def refresh(self):
        super().refresh()
        if hasattr(self, "bus_list"):
            self._populate()

    def _populate(self):
        previous = self.selected_bus
        self.bus_list.blockSignals(True)
        self.bus_list.clear()
        if self.network is not None:
            for bus, row in self.network.buses.iterrows():
                item = QListWidgetItem(f"{bus}  ·  {row.v_nom:g} kV")
                item.setData(Qt.UserRole, str(bus)); self.bus_list.addItem(item)
        self.bus_list.blockSignals(False)
        self._filter_list(self.bus_search.text())
        self.select_bus(previous)
        if self.bus_list.currentItem() is None:
            self.selected_bus = None
            for i in range(self.bus_list.count()):
                if not self.bus_list.item(i).isHidden():
                    self.bus_list.setCurrentRow(i); break
        if self.bus_list.currentItem() is None:
            self.details.setRowCount(0); self.detail_title.setText("Component details")
            self._draw()

    def _filter_list(self, text):
        for i in range(self.bus_list.count()):
            item = self.bus_list.item(i)
            item.setHidden(text.casefold() not in item.text().casefold())

    def select_bus(self, bus):
        for i in range(self.bus_list.count()):
            item = self.bus_list.item(i)
            if item.data(Qt.UserRole) == bus:
                if item.isHidden():
                    self.bus_search.clear()
                self.bus_list.setCurrentItem(item)
                return

    def _bus_changed(self, current, previous=None):
        if current is None:
            return
        self.selected_bus = current.data(Qt.UserRole)
        self.feeder_page = 0
        self.panel.title_edit.setText(f"Bus {self.selected_bus} · local single-line diagram")
        self._show_details("buses", self.selected_bus)
        self._draw()

    def _draw(self):
        self.targets, pages = render_bus_diagram(
            self.panel.figure, self.network, self.selected_bus, self.feeder_page,
            title=self.panel.current_title(),
        )
        self.feeder_page = min(self.feeder_page, pages - 1)
        self.page_label.setText(f"Page {self.feeder_page + 1} / {pages}")
        self.previous.setEnabled(self.feeder_page > 0)
        self.next.setEnabled(self.feeder_page + 1 < pages)
        self.panel.toolbar.update(); self.panel.canvas.draw_idle()

    def _change_page(self, delta):
        self.feeder_page = max(0, self.feeder_page + delta); self._draw()

    def _picked(self, event):
        if self.panel.toolbar.mode or event.artist not in self.targets:
            return
        component, name = self.targets[event.artist]
        if component == "buses":
            self.select_bus(name)
        self._show_details(component, name)

    def _show_details(self, component, name):
        self.details.setRowCount(0)
        if self.network is None:
            return
        table = getattr(self.network, component)
        if name not in table.index:
            return
        self.detail_title.setText(f"{component.replace('_', ' ').title()} · {name}")
        row = table.loc[name]
        self.details.setRowCount(len(row))
        for i, (key, value) in enumerate(row.items()):
            self.details.setItem(i, 0, QTableWidgetItem(str(key)))
            self.details.setItem(i, 1, QTableWidgetItem(str(value)))
        self.details.resizeColumnToContents(0)

    def _table_selected(self, current, previous):
        if not current.isValid():
            return
        source = self.proxy_model.mapToSource(current)
        self.select_bus(str(self.model._rows[source.row()]["name"]))

    def _tab_changed(self, index):
        if index == 0:
            self._populate()

    def filter_by_bus(self, bus_name):
        super().filter_by_bus(bus_name)
        self.select_bus(bus_name)
        self.tabs.setCurrentIndex(0)
