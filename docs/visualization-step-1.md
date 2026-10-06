# Network visualization: step 1

Open **Plots → Network Map** in the Full or Analysis workspace.

- **Auto** uses complete, finite x/y coordinates within longitude/latitude bounds.
  Default (0, 0), wholly coincident, missing or invalid coordinates fall back to
  a deterministic schematic layout. Select **Schematic** explicitly for arbitrary
  diagram coordinates: numerical bounds alone cannot establish a coordinate system.
- **Geographical** uses longitude/latitude; unsuitable coordinates still fall back
  with an explanation below the figure. Coordinates are never changed in the model.
- **Topology** shows all buses, lines, links and transformers, including islands.
  Transformers use dotted brown connections and diamond symbols.
- **Installed generation capacity** always uses `generators.p_nom`, not the mere
  presence of `p_nom_opt`. This includes generators only, not storage power.
  Circle area is proportional to MW; radii are display-sized so circles remain round.
  Only carriers with positive installed capacity appear in the legend. Explicit
  carrier colours are respected, with stable fallbacks for unknown carriers.
- Toggle bus labels, edit the title, or hide the legend. The toolbar offers Home
  (reset), Back/Forward, Pan and Zoom. Save Figure exports PNG (200 dpi), SVG or PDF.
- The geographical layout works without Cartopy. If Cartopy is installed and its
  110m coastline/border shapefiles are already cached, those outlines are drawn.
  No map data is downloaded by the GUI. Without cached data, longitude/latitude
  axes and the network are shown without a basemap.

## Install and run

From the extracted project directory, in your usual Python environment:

```sh
python -m pip install -e .
pypsa-gui
```

NetworkX is now an explicit dependency. All other application dependencies remain
unchanged. Existing map extras remain optional.

## Quick manual check

1. Load the bundled `elec_s_37.nc`: Auto should choose Geographical.
2. Switch to Schematic, then Topology; toggle labels and the legend.
3. Pan/zoom, then use Home to reset the view. Export a figure.
4. Load/create a small network without coordinates, including a transformer and
   an isolated bus: every bus should appear in the schematic.

## Validation

Automated checks cover installed-vs-optimized capacity, invalid coordinates,
layout determinism and non-mutation, branches, proportional pie sizes, legends,
empty/single-bus networks, three export formats and Qt page controls. Run:

```sh
python -m pip install -e '.[dev]'
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

The implementation was exercised with PyPSA 1.3.0 and an offscreen PySide6 GUI,
and the bundled 37-bus network was rendered and visually inspected. The bundled
network is from PyPSA 0.15.0 and raises a version warning when loaded by 1.3.0.
Native desktop interaction on Windows has not been tested here.

## Scope

This step introduces a reusable Qt-independent renderer and integrates it into
Network Map. FigurePanel also gains a navigation toolbar and export error handling.
Existing congestion/price/storage pages are otherwise unchanged. Pandapower import,
optimized-capacity selection, snapshot controls and click-to-inspect remain later
steps. Parallel branches currently overlap; multi-terminal links are displayed
between bus0 and bus1 only.
