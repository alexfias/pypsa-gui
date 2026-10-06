# Local bus diagrams

Open **Components → Buses → Diagram**. The existing editable table is retained
under **Table**.

Select a bus in the searchable list. The diagram shows its busbar, every connected
line/transformer/link, and all attached generators, loads, storage and shunts.
Click neighbouring buses to navigate or equipment to inspect its static parameters.
Disable toolbar Pan/Zoom before clicking components.

## One continuous diagram

There is no pagination. The canvas widens with the number of connections, keeping
space for readable labels. Scroll horizontally to see the entire bus. Small buses
return to a smaller canvas. Use **Open diagram in separate window** to open a
maximized explorer; close it to return to the tab. Inspection remains available.

Long labels wrap and exceptionally long names end with an ellipsis. Hover to see
the full ID, or click for component details. The selected bus name and voltage are
in the title, away from connection labels.

PNG/SVG/PDF export includes the entire diagram, including offscreen connections.
Reset toolbar zoom with Home before exporting if you have zoomed into a subset.
Large buses produce wide images; SVG/PDF are useful when retaining vector quality.

Multi-terminal links have one labelled connection per remote terminal. Repeated
link names refer to the same component. No switches or switch states are inferred.

## Scope and validation

This is static topology one connection away. Result overlays, multiple-hop
expansion, drag-and-drop layout and pandapower import remain future work.
Symbols are simplified rather than an IEC-certified symbol set.

All 14 tests pass. Checks include complete connection coverage for crowded buses,
scrolling, label overlap, PNG/SVG/PDF exports, neighbour navigation, component
inspection, table integration and opening/closing the separate window. Qt tests
run offscreen; Windows desktop behaviour still needs manual checking.

Run from the project folder:

```sh
python -m pip install -e '.[dev]'
python -m pytest -q
pypsa-gui
```

## Files to update from the previous bus-diagram version

- `src/pypsa_gui/ui/pages/buses_page.py`
- `src/pypsa_gui/visualization/bus_diagram.py`
- `tests/test_bus_diagram.py`
- `docs/bus-diagrams.md`
- `docs/images/bus-diagram.png`

No new dependencies are required. This ZIP also includes the earlier geographical
and schematic map improvements.

## Technology symbols

The Symbols dropdown selects Technology (default) or Electrical mode. Technology
mode uses original vector pictograms for wind, PV, hydro, pumped hydro and batteries,
and labelled generator circles for gas, coal, biomass and nuclear. Generic storage
uses E; unknown generators retain G. Shapes and labels identify technologies without
relying only on colour. Carrier colours are shared with the map. Electrical mode
uses generic monochrome symbols. Neither mode claims IEC certification.

Selection uses the component's carrier, not its name. Aliases include onwind,
offwind-ac, offwind-dc, solar, PV, ror, OCGT, CCGT, lignite, biomass, battery, BESS
and PHS. A battery represented as a Link remains a link/converter symbol.

The vector symbol sheet is in `docs/images/technology-symbols.svg` with a PNG preview.
This update changes `buses_page.py`, `bus_diagram.py`, this guide and the screenshot;
it adds `visualization/technology_symbols.py` and `tests/test_technology_symbols.py`.
All 30 tests pass, including carrier classification, vector export and mode switching.
