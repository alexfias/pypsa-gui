import pytest
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from pypsa_gui.visualization.technology_symbols import technology, draw_symbol


@pytest.mark.parametrize('component,carrier,expected', [
 ('generators','offwind-ac','wind'),('generators','onwind','wind'),
 ('generators','solar','solar'),('generators','CCGT','gas'),
 ('generators','OCGT','gas'),('generators','ror','hydro'),
 ('generators','lignite','coal'),('generators','biomass','biomass'),
 ('generators','nuclear','nuclear'),('generators','unknown','generator'),
 ('storage_units','battery','battery'),('storage_units','PHS','pumped hydro'),
 ('stores','H2','storage'),('loads','solar','load')])
def test_carrier_mapping(component,carrier,expected):
    assert technology(component,carrier)==expected


def test_symbols_export_as_vectors(tmp_path):
    fig=Figure(figsize=(12,5)); FigureCanvasAgg(fig)
    carriers=['onwind','solar','ror','OCGT','coal','biomass','nuclear','unknown']
    for i,carrier in enumerate(carriers):
        ax=fig.add_subplot(2,4,i+1); ax.set_xlim(-.6,.6); ax.set_ylim(-.6,.6)
        assert draw_symbol(ax,0,0,'generators',carrier)
        assert not ax.images
    fig.canvas.draw()
    for suffix in ('svg','pdf'):
        path=tmp_path/f'symbols.{suffix}'; fig.savefig(path)
        assert path.stat().st_size>1000


def test_symbol_mode_keeps_selection():
    from PySide6.QtWidgets import QApplication
    from test_bus_diagram import example
    from pypsa_gui.ui.pages.buses_page import BusesPage
    app=QApplication.instance() or QApplication([])
    p=BusesPage(); p.set_network(example()); p.select_bus('MV')
    targets=set(p.targets.values())
    p.symbol_combo.setCurrentText('Electrical'); app.processEvents()
    assert set(p.targets.values())==targets
    assert p.selected_bus=='MV'
    p.close()
