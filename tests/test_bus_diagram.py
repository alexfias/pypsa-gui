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


def test_renderer_all_connections_exports(tmp_path):
    n=example()
    for i in range(12): n.add('Load',f'extra {i}',bus='MV',p_set=1)
    fig=Figure(figsize=(12,7)); FigureCanvasAgg(fig)
    targets=render_bus_diagram(fig,n,'MV')
    found=set(targets.values())
    assert all(('loads',f'extra {i}') in found for i in range(12))
    assert ('generators','Wind') in found
    assert fig.get_figwidth()>25
    fig.canvas.draw()
    for ext in ['svg','png','pdf']:
        path=tmp_path/f'complete.{ext}'
        fig.savefig(path)
        assert path.stat().st_size>1000
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


def test_detach_restore_and_long_labels(tmp_path):
    from PySide6.QtWidgets import QApplication
    from pypsa_gui.ui.pages.buses_page import BusesPage
    from matplotlib.text import Text
    app=QApplication.instance() or QApplication([])
    n=example()
    for i in range(6):
        n.add('Generator',f'MV offwind-ac extremely long generator label {i}',bus='HV',p_nom=5)
    p=BusesPage(); p.resize(1000,700); p.set_network(n); p.select_bus('HV'); p.show()
    app.processEvents(); p.panel.canvas.draw()
    renderer=p.panel.canvas.get_renderer()
    labels=[a for a in p.targets if isinstance(a,Text) and a.get_position()[1]==-2.9]
    boxes=[a.get_window_extent(renderer) for a in labels]
    assert len(boxes)==6
    assert all(not a.overlaps(b) for i,a in enumerate(boxes) for b in boxes[i+1:])
    assert p.diagram_scroll.horizontalScrollBar().maximum()>0
    p._open_window(); app.processEvents()
    assert p._diagram_window is not None
    assert p.diagram_widget.isVisible()
    assert p.panel.canvas.isVisible()
    p.select_bus('MV')
    p._diagram_window.close(); app.processEvents()
    assert p._diagram_window is None
    assert p.tabs.widget(0) is p.diagram_widget
    assert p.selected_bus=='MV'
    p._open_window(); app.processEvents(); p._diagram_window.close(); app.processEvents()
    p.close()


def test_wide_scrollable_bus_keeps_every_asset():
    from PySide6.QtWidgets import QApplication
    from pypsa_gui.ui.pages.buses_page import BusesPage
    app=QApplication.instance() or QApplication([])
    n=example()
    for i in range(20): n.add('Load',f'load {i}',bus='MV',p_set=1)
    p=BusesPage(); p.resize(1100,800); p.set_network(n); p.select_bus('MV'); p.show()
    app.processEvents()
    assert all(('loads',f'load {i}') in p.targets.values() for i in range(20))
    assert p.panel.canvas.width()>=4480
    assert p.diagram_scroll.horizontalScrollBar().maximum()>0
    p.select_bus('isolated'); app.processEvents()
    assert p.panel.canvas.minimumWidth()==1000
    p.close()
