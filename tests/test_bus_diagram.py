import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from types import SimpleNamespace
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
import pypsa
from pypsa_gui.visualization.bus_diagram import connections, render_bus_diagram


def example():
    n = pypsa.Network()
    for name, voltage in [('HV',110),('MV',20),('LV',.4),('isolated',20)]:
        n.add('Bus',name,v_nom=voltage)
    n.add('Transformer','T1',bus0='HV',bus1='MV',s_nom=40,x=.1)
    n.add('Line','feeder',bus0='MV',bus1='LV',s_nom=10,x=.1)
    n.add('Link','converter',bus0='MV',bus1='HV',bus2='LV',p_nom=5)
    n.add('Generator','Wind',bus='MV',p_nom=20)
    n.add('Load','Town',bus='MV',p_set=10)
    n.add('StorageUnit','Battery',bus='MV',p_nom=5,max_hours=4)
    n.add('Store','Energy',bus='MV',e_nom=20)
    return n


def test_complete_connections_and_multiport():
    branches, assets=connections(example(),'MV')
    assert len(branches)==4
    assert {b.neighbour for b in branches}=={'HV','LV'}
    assert {a.component for a in assets}=={'generators','loads','storage_units','stores'}


def test_renderer_pagination_exports(tmp_path):
    n=example()
    for i in range(12): n.add('Load',f'extra {i}',bus='MV',p_set=1)
    found=set()
    for page in range(3):
        fig=Figure(figsize=(12,7)); FigureCanvasAgg(fig)
        targets,pages=render_bus_diagram(fig,n,'MV',page)
        assert pages==3
        found.update(targets.values())
        fig.canvas.draw()
        fig.savefig(tmp_path/f'page-{page}.svg')
    assert all(('loads',f'extra {i}') in found for i in range(12))
    for bus in ['isolated','missing']:
        render_bus_diagram(fig,n,bus); fig.canvas.draw()


def test_page_navigation_table_and_refresh():
    from PySide6.QtWidgets import QApplication
    from pypsa_gui.ui.pages.buses_page import BusesPage
    app=QApplication.instance() or QApplication([])
    p=BusesPage(); p.resize(1450,800); p.set_network(example()); p.show()
    p.select_bus('MV'); app.processEvents()
    assert not p.search_box.isVisible()
    assert not p.table.isVisible()
    artist=next(a for a,t in p.targets.items() if t==('generators','Wind'))
    p._picked(SimpleNamespace(artist=artist))
    assert 'Wind' in p.detail_title.text()
    artist=next(a for a,t in p.targets.items() if t==('buses','HV'))
    p._picked(SimpleNamespace(artist=artist))
    assert p.selected_bus=='HV'
    p.filter_by_bus('MV'); assert p.selected_bus=='MV'
    p.tabs.setCurrentIndex(1); assert p.proxy_model.rowCount()==1
    p.clear_bus_filter(); assert p.proxy_model.rowCount()==4
    p.tabs.setCurrentIndex(0); app.processEvents()
    p.set_network(None); assert p.bus_list.count()==0
    p.close()
