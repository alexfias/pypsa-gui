import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
import pandas as pd
import pypsa
import pytest
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.offsetbox import AnnotationBbox
from pypsa_gui.visualization.network_renderer import (
    carrier_color, installed_capacity_mix, render_network, resolve_layout,
)


def small_network():
    n = pypsa.Network()
    for bus in ["A", "B", "C", "isolated"]:
        n.add("Bus", bus)
    n.add("Line", "line", bus0="A", bus1="B", x=.1, s_nom=100)
    n.add("Link", "link", bus0="A", bus1="C", p_nom=10)
    n.add("Transformer", "transformer", bus0="B", bus1="C", x=.1, s_nom=20)
    n.add("Carrier", "solar", color="#123456")
    n.add("Generator", "g1", bus="A", carrier="solar", p_nom=100)
    n.add("Generator", "g2", bus="B", carrier="custom", p_nom=25)
    return n


def test_installed_not_optimized():
    n = small_network()
    n.generators["p_nom_opt"] = [999, 0]
    mix = installed_capacity_mix(n)
    assert mix.loc["A", "solar"] == 100
    assert mix.loc["B", "custom"] == 25
    assert mix.loc["isolated"].sum() == 0
    assert carrier_color(n, "solar") == "#123456"


def test_fallback_deterministic_without_mutation():
    n = small_network()
    before = n.buses.copy(deep=True)
    a, b = resolve_layout(n), resolve_layout(n)
    assert a.mode == "Schematic"
    pd.testing.assert_frame_equal(a.positions, b.positions)
    pd.testing.assert_frame_equal(before, n.buses)
    assert len(a.positions.drop_duplicates()) == 4


@pytest.mark.parametrize("invalid", [np.nan, np.inf, 181])
def test_invalid_coordinate_fallback(invalid):
    n = small_network()
    n.buses["x"] = [10, 11, 12, invalid]
    n.buses["y"] = [50, 51, 52, 53]
    assert resolve_layout(n, "Geographical").mode == "Schematic"


def test_geographic_and_forced_schematic():
    n = small_network()
    n.buses["x"] = [10, 11, 12, 13]
    n.buses["y"] = [50, 51, 52, 53]
    assert resolve_layout(n).mode == "Geographical"
    assert resolve_layout(n, "Schematic").mode == "Schematic"


def test_render_branches_pies_and_exports(tmp_path):
    n = small_network()
    fig = Figure(figsize=(10, 7))
    FigureCanvasAgg(fig)
    render_network(fig, n, labels=True)
    fig.canvas.draw()
    ax = fig.axes[0]
    assert {c.get_gid() for c in ax.collections} >= {"lines", "links", "transformers"}
    pies = [a for a in ax.artists if isinstance(a, AnnotationBbox)]
    assert len(pies) == 2
    assert pies[0].offsetbox.width / pies[1].offsetbox.width == 2
    texts = [t.get_text() for t in ax.get_legend().get_texts()]
    assert "custom" in texts and "solar" in texts and "coal" not in texts
    for extension in ["png", "svg", "pdf"]:
        path = tmp_path / f"network.{extension}"
        fig.savefig(path, bbox_inches="tight")
        assert path.stat().st_size > 1000


def test_empty_single_and_no_generation():
    for n in [None, pypsa.Network(), small_network()]:
        fig = Figure()
        FigureCanvasAgg(fig)
        render_network(fig, n, capacity=False)
        fig.canvas.draw()
    n = pypsa.Network()
    n.add("Bus", "only")
    fig = Figure()
    FigureCanvasAgg(fig)
    render_network(fig, n)
    fig.canvas.draw()


def test_qt_page_controls():
    from PySide6.QtWidgets import QApplication
    from pypsa_gui.ui.pages.network_map_page import NetworkMapPage
    app = QApplication.instance() or QApplication([])
    page = NetworkMapPage()
    page.resize(1100, 760)
    page.set_network(small_network())
    page.show()
    app.processEvents()
    assert "Schematic" in page.status_label.text()
    page.labels_checkbox.setChecked(True)
    page.metric_combo.setCurrentIndex(1)
    page.panel.legend_checkbox.setChecked(False)
    app.processEvents()
    assert not page.figure.axes[0].get_legend()
    page.panel.toolbar.home()
    page.set_network(None)
    app.processEvents()
    page.close()
