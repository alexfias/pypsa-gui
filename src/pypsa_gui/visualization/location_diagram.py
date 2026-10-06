"""Read-only grouped-bus diagrams; grouping never changes network topology."""
import pandas as pd
from matplotlib.patches import Circle, Rectangle
from .bus_diagram import connections, short_label, bus_label
from .technology_symbols import draw_symbol
from .network_renderer import carrier_color


def location_buses(network, selected):
    if network is None or selected not in network.buses.index:
        return []
    if 'location' not in network.buses:
        return [selected]
    value = network.buses.at[selected, 'location']
    if pd.isna(value) or not str(value).strip():
        return [selected]
    matches = network.buses.index[network.buses["location"].eq(value).fillna(False)]
    return [selected] + [b for b in matches if b != selected]


def group_data(network, buses):
    buses = list(dict.fromkeys(b for b in buses if b in network.buses.index))
    internal = []
    for component in ('lines', 'transformers', 'links'):
        for name, row in getattr(network, component).iterrows():
            terminals = [(p, row[p]) for p in row.index
                         if p.startswith('bus') and p[3:].isdigit() and row[p] in network.buses.index]
            inside = [(p, b) for p, b in terminals if b in buses]
            if len(inside) >= 2:
                internal.append((component, name, terminals))
    keys = {(c, str(n)) for c, n, _ in internal}
    rows = {}
    for bus in buses:
        branches, assets = connections(network, bus)
        rows[bus] = ([b for b in branches if (b.component, b.name) not in keys], assets)
    return buses, rows, internal


def location_canvas_size(network, buses):
    if network is None or not buses:
        return 1000, 700
    buses, rows, internal = group_data(network, buses)
    columns = max([max(len(a), len(b), 1) for a, b in rows.values()] or [1])
    return max(1100, 180 * columns + 260 * len(internal) + 420), max(700, 600 * len(buses) + 160)


def render_location_diagram(figure, network, buses, title=None, symbol_mode='Technology', resize_figure=True):
    if resize_figure:
        width, height = location_canvas_size(network, buses)
        figure.set_size_inches(width / 100, height / 100)
    figure.clear(); ax = figure.add_subplot(111); ax.set_axis_off(); ax.set_aspect('equal')
    targets = {}
    if network is None or not buses:
        ax.text(.5,.5,'Select buses to inspect a location.',ha='center',transform=ax.transAxes)
        return targets
    buses, rows, internal = group_data(network, buses)
    columns = max([max(len(a), len(b), 1) for a, b in rows.values()] or [1])
    end = max(3, (columns - 1) * 2.4 + 1.2)
    ys = {bus: -8 * i for i, bus in enumerate(buses)}
    def pick(artist, component, name):
        artist.set_picker(6); targets[artist] = (component, str(name)); return artist
    def line(xs, yvalues, component, name, color='#526675', **kw):
        a, = ax.plot(xs,yvalues,color=color,zorder=2,**kw); return pick(a,component,name)
    def label(x,y,value,component,name,color='#334155',**kw):
        a=ax.text(x,y,value,ha='center',va='center',fontsize=9,color=color,zorder=5,
                  bbox=dict(facecolor='white',edgecolor='none',pad=2),**kw)
        return pick(a,component,name)
    def device(x,y,component,name):
        color='#ad6c38' if component=='transformers' else '#5678a6'
        if component=='transformers':
            for offset in (-.16,.16):
                p=Circle((x,y+offset),.25,facecolor='white',edgecolor=color,zorder=4)
                ax.add_patch(p);pick(p,component,name)
        elif component=='links':
            p=Rectangle((x-.28,y-.28),.56,.56,facecolor='white',edgecolor=color,zorder=4)
            ax.add_patch(p);pick(p,component,name);label(x,y,'L',component,name,color)
    for bus in buses:
        y=ys[bus]; branches, assets=rows[bus]
        line([-.7,end],[y,y],'buses',bus,color='#174e73',linewidth=4)
        label(-2.5,y,bus_label(network,bus),'buses',bus,color='#174e73',fontweight='bold')
        for i,item in enumerate(branches):
            x=i*2.4
            line([x,x],[y,y+2.8],item.component,item.name,linestyle='--' if item.component=='links' else '-')
            device(x,y+1.8,item.component,item.name)
            line([x-.4,x+.4],[y+2.8,y+2.8],'buses',item.neighbour,color='#174e73',linewidth=3)
            label(x,y+3.45,bus_label(network,item.neighbour),'buses',item.neighbour)
            label(x,y+.85,short_label(f'{item.component[:-1]} {item.name}'),item.component,item.name)
        for i,item in enumerate(assets):
            x=i*2.4; row=getattr(network,item.component).loc[item.name]; carrier=str(row.get('carrier',''))
            line([x,x],[y,y-1.8],item.component,item.name)
            for a in draw_symbol(ax,x,y-2,item.component,carrier,mode=symbol_mode,color=carrier_color(network,carrier)):
                pick(a,item.component,item.name)
            label(x,y-2.95,short_label(f'{item.component.replace("_", " ")}: {item.name}'),item.component,item.name)
    # One lane per component; multi-terminal links are drawn once, with named ports.
    for i,(component,name,terminals) in enumerate(internal):
        x=end+2.7*(i+1)
        inside=[(p,b) for p,b in terminals if b in ys]
        low=min(ys[b] for _,b in inside); high=max(ys[b] for _,b in inside)
        line([x,x],[low,high],component,name,linestyle='--' if component=='links' else '-')
        for port,bus in inside:
            y=ys[bus]
            line([end,x],[y,y],component,name)
            a,=ax.plot([x],[y],'o',color='#526675',markersize=4,zorder=4);pick(a,component,name)
            label(x,y+.35,port,component,name)
        mid=(low+high)/2
        device(x,mid,component,name)
        label(x,mid-.9,short_label(f'{component[:-1]} {name}'),component,name)
        outside=[(p,b) for p,b in terminals if b not in ys]
        # Explicit remote terminal labels keep mixed internal/external links complete.
        for j,(port,bus) in enumerate(outside):
            top=high+2.0+j*1.35
            line([x,x],[high,top],component,name,linestyle='--')
            label(x,top,f'{port} →\n{bus_label(network,bus)}','buses',bus)
    remote_max=max([sum(b not in ys for _,b in t) for _,_,t in internal] or [0])
    ax.set_xlim(-4.2,end+2.7*len(internal)+1.5)
    ax.set_ylim(min(ys.values())-3.7,max(4.3,3+1.35*remote_max))
    ax.set_title(short_label(title or 'Location · connected buses',70,2),loc='left',fontsize=12,pad=16)
    figure.subplots_adjust(left=.03,right=.97,top=.95,bottom=.04)
    return targets
