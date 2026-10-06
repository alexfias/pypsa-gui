import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pandas as pd
import pypsa
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from pypsa_gui.visualization.location_diagram import location_buses, group_data, render_location_diagram
from pypsa_gui.visualization.bus_diagram import bus_label


def example():
    n=pypsa.Network()
    for name,carrier,loc in [('Electricity','AC','Site A'),('Heat','heat','Site A'),('EV','Li-ion','Site A'),('Grid','AC','Site B'),('Ungrouped','heat',''),('Other','heat','')]:
        n.add('Bus',name,carrier=carrier,v_nom=20,location=loc)
    n.add('Link','Heat pump',bus0='Electricity',bus1='Heat',p_nom=5,efficiency=3)
    n.add('Link','EV charger',bus0='Electricity',bus1='EV',p_nom=3)
    n.add('Line','Supply',bus0='Grid',bus1='Electricity',x=.1,s_nom=20)
    n.add('Generator','PV',bus='Electricity',carrier='solar',p_nom=10)
    n.add('Load','Heating',bus='Heat',p_set=5)
    n.add('Store','Car battery',bus='EV',carrier='battery',e_nom=50)
    return n


def test_grouping_does_not_merge_empty_locations_or_mutate():
    n=example(); before=n.buses.copy(deep=True)
    assert location_buses(n,'Electricity')==['Electricity','Heat','EV']
    assert location_buses(n,'Ungrouped')==['Ungrouped']
    n.buses.at['Other','location']=None
    assert location_buses(n,'Electricity')==['Electricity','Heat','EV']
    n.buses.at['Other','location']=''
    pd.testing.assert_frame_equal(n.buses,before)
    assert 'kV' not in bus_label(n,'Heat')
    assert '20 kV' in bus_label(n,'Electricity')


def test_internal_links_once_and_remote_ports(tmp_path):
    n=example()
    n.add('Link','Three terminal',bus0='Electricity',bus1='Heat',bus2='Grid',p_nom=1)
    buses,rows,links=group_data(n,['Electricity','Heat','EV'])
    assert len(links)==3
    assert sum(name=='Heat pump' for _,name,_ in links)==1
    assert not any(b.name=='Heat pump' for branches,_ in rows.values() for b in branches)
    fig=Figure(); FigureCanvasAgg(fig)
    targets=render_location_diagram(fig,n,buses)
    assert ('buses','Grid') in targets.values()
    assert ('stores','Car battery') in targets.values()
    fig.canvas.draw()
    for ext in ['svg','pdf','png']: fig.savefig(tmp_path/f'location.{ext}')


def test_ui_modes_and_group_reset():
    from PySide6.QtWidgets import QApplication
    from pypsa_gui.ui.pages.buses_page import BusesPage
    app=QApplication.instance() or QApplication([])
    p=BusesPage(); p.set_network(example()); p.select_bus('Electricity')
    p.view_combo.setCurrentText('Location'); app.processEvents()
    assert p._group_buses()==['Electricity','Heat','EV']
    assert p.panel.canvas.minimumHeight()>700
    p.manual_buses=['Grid','Heat']; p.view_combo.setCurrentText('Manual group')
    assert p._group_buses()==['Electricity','Grid','Heat']
    p.view_combo.setCurrentText('Bus'); assert p.panel.canvas.minimumHeight()==700
    p.set_network(None); assert p.manual_buses==[]
    p.close()
