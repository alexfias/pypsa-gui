"""Local single-line diagrams. Static topology only; no inferred switches."""
from dataclasses import dataclass
import math
import textwrap

from matplotlib.patches import Circle, Rectangle, Polygon


@dataclass(frozen=True)
class Connection:
    component: str
    name: str
    neighbour: str | None = None
    port: str = ""


def connections(network, bus):
    branches, assets = [], []
    for component in ("lines", "transformers", "links"):
        table = getattr(network, component)
        ports = [c for c in table.columns if c.startswith("bus") and c[3:].isdigit()]
        for name, row in table.iterrows():
            local = [p for p in ports if row[p] == bus]
            if not local:
                continue
            for port in ports:
                other = row[port]
                if other in network.buses.index and (other != bus or len(local) > 1):
                    branches.append(Connection(component, str(name), str(other), port))
    for component in ("generators", "loads", "storage_units", "stores", "shunt_impedances"):
        table = getattr(network, component)
        for name in table.index[table.bus == bus] if "bus" in table else []:
            assets.append(Connection(component, str(name)))
    return branches, assets


def bus_label(network, bus):
    voltage = network.buses.at[bus, "v_nom"]
    return f"{bus}\n{voltage:g} kV"


def render_bus_diagram(figure, network, bus, page=0, page_size=6, title=None):
    """Return artist->(component,id) pick targets and number of feeder pages."""
    figure.clear()
    ax = figure.add_subplot(111)
    ax.set_axis_off()
    ax.set_aspect("equal")
    figure.set_facecolor("white")
    targets = {}
    if network is None or bus not in network.buses.index:
        ax.text(.5, .5, "Select a bus to inspect its connections.", ha="center", transform=ax.transAxes)
        return targets, 1
    branches, assets = connections(network, bus)
    pages = max(1, math.ceil(max(len(branches), len(assets)) / page_size))
    page = min(max(page, 0), pages - 1)
    branches = branches[page * page_size:(page + 1) * page_size]
    assets = assets[page * page_size:(page + 1) * page_size]
    count = max(len(branches), len(assets), 1)
    width = max(3, (count - 1) * 2.4 + 1.4)

    def pick(artist, component, name):
        artist.set_picker(6)
        targets[artist] = (component, name)
        return artist

    def line(xs, ys, component, name, **kwargs):
        artist, = ax.plot(xs, ys, **kwargs)
        return pick(artist, component, name)

    def text(x, y, label, component, name, **kwargs):
        artist = ax.text(x, y, label, ha="center", va="center", fontsize=9, **kwargs)
        return pick(artist, component, name)

    line([-.7, width - .7], [0, 0], "buses", bus, color="#174e73", linewidth=5)
    text(width / 2 - .7, .6, bus_label(network, bus), "buses", bus,
         color="#174e73", fontweight="bold")
    palette = {"lines": "#526675", "links": "#5678a6", "transformers": "#ad6c38"}
    for i, item in enumerate(branches):
        x = i * 2.4
        color = palette[item.component]
        style = "--" if item.component == "links" else "-"
        line([x, x], [0, 3.1], item.component, item.name, color=color, linestyle=style)
        if item.component == "transformers":
            for y in (1.7, 2.05):
                patch = Circle((x, y), .27, facecolor="white", edgecolor=color, linewidth=1.5, zorder=3)
                ax.add_patch(patch); pick(patch, item.component, item.name)
        elif item.component == "links":
            patch = Rectangle((x-.25, 1.6), .5, .5, facecolor="white", edgecolor=color, zorder=3)
            ax.add_patch(patch); pick(patch, item.component, item.name)
            text(x, 1.85, "L", item.component, item.name, zorder=4, color=color)
        line([x-.45, x+.45], [3.1, 3.1], "buses", item.neighbour, color="#174e73", linewidth=4)
        text(x, 3.65, bus_label(network, item.neighbour), "buses", item.neighbour, color="#174e73")
        label = f"{item.component[:-1].replace('_', ' ').title()} {item.name}"
        if item.component == "links":
            label += f" ({item.port})"
        text(x+.6, 1.0, '\n'.join(textwrap.wrap(label, 15)), item.component, item.name, color=color)
    symbols = {"generators": "G", "loads": "Load", "storage_units": "Storage", "stores": "Store", "shunt_impedances": "Shunt"}
    for i, item in enumerate(assets):
        x = i * 2.4
        line([x, x], [0, -1.8], item.component, item.name, color="#526675")
        if item.component == "generators":
            patch = Circle((x, -2), .3, facecolor="white", edgecolor="#3d876c", linewidth=1.5, zorder=3)
        elif item.component == "loads":
            patch = Polygon([(x-.25,-1.8),(x+.25,-1.8),(x,-2.3)], facecolor="white", edgecolor="#ae6856", linewidth=1.5, zorder=3)
        else:
            patch = Rectangle((x-.4, -2.3), .8, .6, facecolor="#edf4f7", edgecolor="#526675", zorder=3)
        ax.add_patch(patch); pick(patch, item.component, item.name)
        if item.component != "loads":
            text(x, -2, "G" if item.component == "generators" else ("S" if item.component == "shunt_impedances" else "E"), item.component, item.name, zorder=4)
        text(x, -2.9, '\n'.join(textwrap.wrap(f"{symbols[item.component]}: {item.name}", 18)), item.component, item.name)
    if not branches and not assets:
        ax.text(width/2-.7, -1.6, "No connected equipment", ha="center", color="#64748b")
    ax.set_xlim(-1.0, width)
    ax.set_ylim(-3.6, 4.4)
    ax.set_title(title or f"Bus {bus} · local single-line diagram", loc="left", fontsize=12, pad=15)
    figure.subplots_adjust(left=.04, right=.98, top=.9, bottom=.06)
    return targets, pages
