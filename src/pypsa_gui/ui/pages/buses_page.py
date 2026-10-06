from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QScrollArea, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QSplitter, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)
from pypsa_gui.visualization.location_diagram import location_buses, location_canvas_size, render_location_diagram
from pypsa_gui.visualization.bus_diagram import bus_label
from pypsa_gui.ui.pages.component_page import ComponentPage
from pypsa_gui.ui.widgets.figure_panel import FigurePanel
from pypsa_gui.visualization.bus_diagram import render_bus_diagram, diagram_canvas_width


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
        self.window_button = QPushButton("Open diagram in separate window")
        self.window_button.clicked.connect(self._open_window)
        outer.addWidget(self.window_button)
        self._diagram_window = None
        diagram = QWidget()
        self.diagram_widget = diagram
        diagram_layout = QVBoxLayout(diagram)
        split = QSplitter(Qt.Horizontal)
        left = QWidget(); left_layout = QVBoxLayout(left)
        self.bus_search = QLineEdit(); self.bus_search.setPlaceholderText("Search buses / voltage…")
        self.bus_list = QListWidget()
        left_layout.addWidget(self.bus_search); left_layout.addWidget(self.bus_list)
        centre = QWidget(); centre_layout = QVBoxLayout(centre)
        self.manual_buses = []
        self.view_combo = QComboBox()
        self.view_combo.addItems(["Bus", "Location", "Manual group"])
        self.group_button = QPushButton("Choose buses…")
        self.group_button.clicked.connect(self._choose_buses)
        self.group_status = QLabel()
        self.group_status.setWordWrap(True)
        centre_layout.addWidget(self.view_combo)
        centre_layout.addWidget(self.group_button)
        centre_layout.addWidget(self.group_status)
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(["Technology", "Electrical"])
        self.symbol_combo.setToolTip("Technology pictograms or generic electrical symbols; not an IEC-certified symbol set.")
        centre_layout.addWidget(QLabel("Symbols:"))
        centre_layout.addWidget(self.symbol_combo)
        self.panel = FigurePanel("Local single-line diagram", minimum_canvas_height=380)
        self.panel.legend_checkbox.hide()
        # Preserve readable text at narrow dock widths; scroll instead of squeezing.
        self.panel.layout().removeWidget(self.panel.canvas)
        self.diagram_scroll = QScrollArea()
        self.diagram_scroll.setWidgetResizable(True)
        self.panel.canvas.setMinimumSize(1000, 700)
        self.diagram_scroll.setWidget(self.panel.canvas)
        self.panel.layout().addWidget(self.diagram_scroll, 1)
        centre_layout.addWidget(self.panel, 1)
        self.hint = QLabel("Click a neighbouring bus to navigate; click equipment for parameters.\nScroll for the full diagram; hover for full names. Export includes every connection, including offscreen content.")
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
        self.targets = {}
        self.view_combo.currentTextChanged.connect(self._view_changed)
        self.symbol_combo.currentTextChanged.connect(self._draw)
        self.bus_search.textChanged.connect(self._filter_list)
        self.bus_list.currentItemChanged.connect(self._bus_changed)
        self.panel.title_edit.editingFinished.connect(self._draw)
        self.panel.canvas.mpl_connect("pick_event", self._picked)
        self.panel.canvas.mpl_connect("motion_notify_event", self._hover)
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
                item = QListWidgetItem(bus_label(self.network, bus).replace("\n", " · "))
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
        self._update_title()
        self._show_details("buses", self.selected_bus)
        self._draw()

    def _draw(self):
        grouped = self.view_combo.currentText() != "Bus"
        buses = self._group_buses()
        width, height = location_canvas_size(self.network, buses) if grouped else (diagram_canvas_width(self.network, self.selected_bus), 700)
        self.panel.canvas.setMinimumSize(width, height)
        self.panel.canvas.resize(max(width, self.diagram_scroll.viewport().width()),
                                 max(height, self.diagram_scroll.viewport().height()))
        if grouped:
            self.targets = render_location_diagram(self.panel.figure, self.network, buses,
                title=self.panel.current_title(), resize_figure=False, symbol_mode=self.symbol_combo.currentText())
            self.group_status.setText(f"{len(buses)} buses · visual grouping only · crossings without dots are not junctions" +
                (" · No matching location; use Choose buses." if len(buses) == 1 and self.view_combo.currentText() == "Location" else ""))
        else:
            self.targets = render_bus_diagram(self.panel.figure, self.network, self.selected_bus,
                title=self.panel.current_title(), resize_figure=False, symbol_mode=self.symbol_combo.currentText())
            self.group_status.setText("")
        self.panel.toolbar.update(); self.panel.canvas.draw_idle()


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

    def _hover(self, event):
        for artist, (component, name) in reversed(list(self.targets.items())):
            if artist.contains(event)[0]:
                self.panel.canvas.setToolTip(f"{component.replace('_', ' ').title()}: {name}")
                return
        self.panel.canvas.setToolTip("")

    def _open_window(self):
        if self._diagram_window is not None:
            self._diagram_window.raise_()
            self._diagram_window.activateWindow()
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Bus diagram explorer")
        dialog.setModal(False)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        self._diagram_window = dialog
        self.tabs.removeTab(0)
        self._window_placeholder = QLabel("Diagram is open in a separate window. Close that window to return it here.")
        self._window_placeholder.setWordWrap(True)
        self.tabs.insertTab(0, self._window_placeholder, "Diagram")
        layout = QVBoxLayout(dialog)
        layout.addWidget(self.diagram_widget)
        self.diagram_widget.show()
        dialog.finished.connect(self._restore_diagram)
        dialog.showMaximized()

    def _restore_diagram(self, result=0):
        self.tabs.removeTab(0)
        self.tabs.insertTab(0, self.diagram_widget, "Diagram")
        self._window_placeholder.deleteLater()
        self._diagram_window = None
        self.tabs.setCurrentIndex(0)

    def set_network(self, network):
        if network is not self.network:
            self.manual_buses = []
        super().set_network(network)

    def _group_buses(self):
        if self.network is None or self.selected_bus not in self.network.buses.index:
            return []
        if self.view_combo.currentText() == "Location":
            return location_buses(self.network, self.selected_bus)
        if self.view_combo.currentText() == "Manual group":
            return list(dict.fromkeys([self.selected_bus] + [b for b in self.manual_buses if b in self.network.buses.index]))
        return [self.selected_bus]

    def _update_title(self):
        if self.network is None or self.selected_bus not in self.network.buses.index:
            return
        mode = self.view_combo.currentText()
        self.panel.title_edit.setText((bus_label(self.network,self.selected_bus).replace("\n", " · ") if mode == "Bus" else f"{mode} · {self.selected_bus}") + " · single-line diagram")

    def _view_changed(self):
        self._update_title()
        self._draw()

    def _choose_buses(self):
        if self.network is None:
            return
        dialog = QDialog(self); dialog.setWindowTitle("Choose buses to show together")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("The selected bus is always included. This does not modify the model."))
        search = QLineEdit(); search.setPlaceholderText("Search buses…"); layout.addWidget(search)
        listing = QListWidget(); layout.addWidget(listing)
        selected = set(self._group_buses())
        for bus in self.network.buses.index:
            item=QListWidgetItem(str(bus)); item.setData(Qt.UserRole,str(bus))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if bus in selected else Qt.Unchecked)
            listing.addItem(item)
        search.textChanged.connect(lambda text: [listing.item(i).setHidden(text.casefold() not in listing.item(i).text().casefold()) for i in range(listing.count())])
        buttons=QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        dialog.resize(500,600)
        if dialog.exec() == QDialog.Accepted:
            self.manual_buses=[listing.item(i).data(Qt.UserRole) for i in range(listing.count()) if listing.item(i).checkState()==Qt.Checked]
            self.view_combo.setCurrentText("Manual group")
            self._view_changed()
