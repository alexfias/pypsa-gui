# Local bus diagrams (step 1b)

Open **Components → Buses**. The new **Diagram** tab is the default; the existing
editable table remains available under **Table**.

- Search the bus list by name or voltage, then select a bus.
- The central horizontal busbar shows the selected bus and its nominal voltage.
- Above it are connected lines, transformers and links leading to neighbouring buses.
- Below it are generators, loads, storage units, stores and shunt impedances.
- Click a neighbouring busbar/name to navigate. Click equipment or its label to
  inspect its static parameters in the right panel. Disable Pan/Zoom before clicking.
- Use Previous/Next feeders for crowded buses (six branches and six attached assets
  per page). The busbar is repeated across pages; all components remain accessible.
- Pan, zoom, reset and export PNG/SVG/PDF using the shared figure controls. An export
  contains the current feeder page only.
- Selecting a row in Table selects that bus for the Diagram tab. Overview bus links
  also open the diagram. The table's existing search, sorting, copying and editing
  remain in place.

This first version shows static topology one connection away. Navigate by clicking
neighbours to explore further. It does not yet overlay time-dependent results,
expand multiple hops, support dragging/saved positions or import pandapower.
The symbols are simplified engineering symbols, not an IEC-certified symbol set.
A multi-terminal link has one labelled feeder per remote terminal; repeated link
names refer to the same component, not separate devices. No switch state is inferred.

## Installation

Copy the changed files into your step-1 repository, then run `python -m pip install -e .`.
No dependencies were added beyond step 1.

Files changed/added for this step:

- `src/pypsa_gui/ui/pages/buses_page.py`
- `src/pypsa_gui/visualization/bus_diagram.py`
- `tests/test_bus_diagram.py`
- `docs/bus-diagrams.md`
- `docs/images/bus-diagram.png`

Tests cover multi-terminal links, complete asset inclusion across feeder pages,
SVG rendering, empty/isolated buses, clickable component details, neighbour navigation,
table filtering and clearing the network. GUI tests use Qt's offscreen platform;
Windows desktop behaviour still needs a manual check.
