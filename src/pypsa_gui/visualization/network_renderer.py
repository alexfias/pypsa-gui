"""Topology and installed generation capacity rendering without a Qt dependency.

Coordinates are never written back to the network. Auto mode only uses complete,
finite longitude/latitude coordinates; schematic layouts are deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

import networkx as nx
import numpy as np
import pandas as pd
from matplotlib import colors
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnnotationBbox, DrawingArea
from matplotlib.patches import Wedge

CARRIER_COLORS = {
    "solar": "#e9bd32", "onwind": "#56a7cf", "offwind": "#296ba0",
    "wind": "#56a7cf", "gas": "#db775e", "OCGT": "#db775e",
    "CCGT": "#b95442", "hydro": "#449e87", "ror": "#71b89a",
    "biomass": "#85954d", "coal": "#525b65", "lignite": "#947255",
    "nuclear": "#9276b5", "other": "#adb5bd",
}
BRANCH_STYLES = {
    "lines": ("Line", "#7b8794", "solid"),
    "links": ("Link", "#5b72aa", "dashed"),
    "transformers": ("Transformer", "#ad6c38", "dotted"),
}


@dataclass
class Layout:
    positions: pd.DataFrame
    mode: str
    note: str


def geographic_positions(network) -> pd.DataFrame | None:
    buses = network.buses
    if buses.empty or not {"x", "y"}.issubset(buses.columns):
        return None
    xy = buses[["x", "y"]].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(xy.to_numpy()).all():
        return None
    if not xy.x.between(-180, 180).all() or not xy.y.between(-90, 90).all():
        return None
    # (0, 0) is PyPSA's default and cannot establish a geographic location.
    if ((xy.x == 0) & (xy.y == 0)).any():
        return None
    if len(xy) > 1 and len(xy.drop_duplicates()) == 1:
        return None
    return xy


def resolve_layout(network, mode: str = "Auto") -> Layout:
    if mode not in {"Auto", "Geographical", "Schematic"}:
        raise ValueError(f"Unknown layout: {mode}")
    xy = geographic_positions(network)
    if mode != "Schematic" and xy is not None:
        return Layout(xy, "Geographical", "Geographical layout · x/y treated as longitude/latitude")
    graph = nx.Graph()
    graph.add_nodes_from(network.buses.index)
    for attr in BRANCH_STYLES:
        table = getattr(network, attr)
        for row in table.itertuples():
            if row.bus0 in graph and row.bus1 in graph:
                graph.add_edge(row.bus0, row.bus1)
    # Lay out islands separately so isolated buses do not compress the main grid.
    components = sorted(nx.connected_components(graph), key=len, reverse=True)
    columns = max(1, int(np.ceil(np.sqrt(len(components)))))
    positions = {}
    for i, nodes in enumerate(components):
        subgraph = graph.subgraph(nodes)
        local = nx.spring_layout(subgraph, seed=42, iterations=80)
        shift = np.array([3.0 * (i % columns), -3.0 * (i // columns)])
        positions.update({bus: point + shift for bus, point in local.items()})
    frame = pd.DataFrame.from_dict(positions, orient="index", columns=["x", "y"])
    frame = frame.reindex(network.buses.index)
    note = "Schematic layout · distances have no geographical meaning"
    if mode != "Schematic":
        note += " · missing, default or unsuitable coordinates"
    return Layout(frame, "Schematic", note)


def installed_capacity_mix(network) -> pd.DataFrame:
    """p_nom is installed capacity, regardless of p_nom_opt defaults/results."""
    generators = network.generators
    if generators.empty:
        return pd.DataFrame(index=network.buses.index)
    data = generators[["bus", "carrier", "p_nom"]].copy()
    data["carrier"] = data.carrier.fillna("other").replace("", "other").astype(str)
    data["p_nom"] = pd.to_numeric(data.p_nom, errors="coerce")
    data = data[np.isfinite(data.p_nom) & (data.p_nom > 0)]
    return (data.groupby(["bus", "carrier"], sort=True).p_nom.sum()
            .unstack(fill_value=0.0).reindex(network.buses.index, fill_value=0.0))


def carrier_color(network, carrier: str):
    if carrier in network.carriers.index and "color" in network.carriers:
        value = network.carriers.at[carrier, "color"]
        if isinstance(value, str) and value and colors.is_color_like(value):
            return value
    if carrier in CARRIER_COLORS:
        return CARRIER_COLORS[carrier]
    if carrier.lower() in CARRIER_COLORS:
        return CARRIER_COLORS[carrier.lower()]
    # Stable across networks and processes, without collapsing unknown carriers.
    hue = int(hashlib.sha256(carrier.encode()).hexdigest()[:8], 16) / 0xffffffff
    return colors.to_hex(colors.hsv_to_rgb((hue, 0.48, 0.72)))


def _cached_basemap(ax):
    """Use local Cartopy data only; never trigger a download during rendering."""
    try:
        import cartopy
        from cartopy.io import shapereader
        from pathlib import Path
    except ImportError:
        return False
    drawn = False
    for name, category in [("coastline", "physical"), ("admin_0_boundary_lines_land", "cultural")]:
        for root in (cartopy.config["pre_existing_data_dir"], cartopy.config["data_dir"]):
            path = Path(root) / "shapefiles" / "natural_earth" / category / f"ne_110m_{name}.shp"
            if not path.is_file():
                continue
            try:
                reader = shapereader.Reader(path)
                segments = []
                for geometry in reader.geometries():
                    parts = geometry.geoms if hasattr(geometry, "geoms") else [geometry]
                    segments.extend(np.asarray(part.coords)[:, :2] for part in parts if part.geom_type == "LineString")
                reader.close()
                ax.add_collection(LineCollection(segments, colors="#d5dce1", linewidths=0.6, zorder=0))
                drawn = True
            except (OSError, ValueError):
                pass
            break
    return drawn


def render_network(figure, network, *, layout: Layout | None = None,
                   mode="Auto", capacity=True, labels=False, legend=True,
                   title=None):
    """Render to any Matplotlib Figure (Qt canvas or headless export).

    Pie radii are in display points, with area proportional to installed MW.
    Layout may be cached by the caller when only view controls change.
    """
    figure.clear()
    ax = figure.add_subplot(111)
    ax.set_facecolor("#f8fafc")
    figure.set_facecolor("white")
    if network is None or network.buses.empty:
        ax.text(.5, .5, "No network loaded.", ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return None
    layout = layout or resolve_layout(network, mode)
    xy = layout.positions
    if layout.mode == "Geographical":
        _cached_basemap(ax)
    handles = [Line2D([], [], linestyle="none", marker="o", markersize=4,
                      markerfacecolor="#334155", markeredgecolor="white", label="Bus")]
    for attr, (label, color, style) in BRANCH_STYLES.items():
        segments = []
        for row in getattr(network, attr).itertuples():
            if row.bus0 in xy.index and row.bus1 in xy.index:
                segments.append([xy.loc[row.bus0].to_numpy(), xy.loc[row.bus1].to_numpy()])
        if segments:
            collection = LineCollection(segments, colors=color, linewidths=1.3,
                                        linestyles=style, zorder=1)
            collection.set_gid(attr)
            ax.add_collection(collection)
            handles.append(Line2D([], [], color=color, linestyle=style, label=label))
            if attr == "transformers":
                mids = np.mean(segments, axis=1)
                ax.scatter(mids[:, 0], mids[:, 1], marker="D", s=28,
                           facecolors="white", edgecolors=color, zorder=2)
    ax.scatter(xy.x, xy.y, s=23, c="#334155", edgecolors="white", linewidths=.6, zorder=3)
    if labels:
        for bus, row in xy.iterrows():
            ax.annotate(str(bus), (row.x, row.y), xytext=(5, 5), textcoords="offset points",
                        fontsize=8, color="#334155", zorder=5)
    mix = installed_capacity_mix(network) if capacity else pd.DataFrame()
    if not mix.empty:
        totals = mix.sum(axis=1)
        maximum = float(totals.max())
        if maximum > 0:
            for bus, total in totals.items():
                if total <= 0:
                    continue
                radius = 18 * np.sqrt(total / maximum)
                area = DrawingArea(2 * radius, 2 * radius, clip=False)
                start = 0.0
                for carrier, value in mix.loc[bus].items():
                    if value <= 0:
                        continue
                    end = start + 360 * value / total
                    area.add_artist(Wedge((radius, radius), radius, start, end,
                                          facecolor=carrier_color(network, carrier),
                                          edgecolor="white", linewidth=.45))
                    start = end
                ax.add_artist(AnnotationBbox(area, xy.loc[bus].to_numpy(), frameon=False,
                                            pad=0, box_alignment=(.5, .5), zorder=4))
            handles += [Line2D([], [], marker="s", linestyle="none", markersize=8,
                               color=carrier_color(network, c), label=str(c))
                        for c in mix.columns if mix[c].sum() > 0]
            for fraction in (0.25, 1.0):
                handles.append(Line2D([], [], linestyle="none", marker="o",
                                      markersize=36 * np.sqrt(fraction),
                                      markerfacecolor="none", markeredgecolor="#64748b",
                                      label=f"{maximum * fraction:,.3g} MW"))
    if legend:
        ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1),
                  frameon=False, fontsize=9, labelspacing=1.0, borderaxespad=0,
                  ncol=2 if len(handles) > 12 else 1, handleheight=2.8, handlelength=3.0,
                  title="Components / installed capacity" if capacity else "Components")
    dx = float(xy.x.max() - xy.x.min())
    dy = float(xy.y.max() - xy.y.min())
    pad = max(dx, dy, 0.02 if layout.mode == "Geographical" else 1.0) * .12
    ax.set_xlim(float(xy.x.min()) - pad, float(xy.x.max()) + pad)
    ax.set_ylim(float(xy.y.min()) - pad, float(xy.y.max()) + pad)
    if layout.mode == "Geographical":
        ax.set_aspect(1 / max(np.cos(np.deg2rad(float(xy.y.mean()))), .15))
        ax.set_xlabel("Longitude [°]")
        ax.set_ylabel("Latitude [°]")
        ax.grid(color="#e2e8f0", linewidth=.5)
    else:
        ax.set_aspect("equal", adjustable="box")
        ax.set_axis_off()
    ax.set_title(title or ("Installed generation capacity" if capacity else "Network topology"),
                 loc="left", fontsize=13, pad=14, color="#1e293b")
    for spine in ax.spines.values():
        spine.set_visible(False)
    figure.subplots_adjust(left=.09, right=(.60 if len(handles) > 12 else .72) if legend else .96, bottom=.12, top=.9)
    return layout
