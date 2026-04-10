# pypsa-gui

An experimental desktop GUI for inspecting, solving, and visualising PyPSA networks.

## Overview

`pypsa-gui` aims to provide a lightweight interactive workbench for PyPSA models without requiring the user to work directly in notebooks or ad-hoc scripts.

The project is currently focused on building a clean desktop application architecture that can gradually grow into a practical modelling and analysis tool for both research and teaching.

## Current workflow

The application is currently built around a simple exploratory workflow:

1. Load a PyPSA network from NetCDF or a CSV folder
2. Keep multiple loaded networks open as separate sessions
3. Switch the active session from the **Loaded Networks** dock
4. Inspect model structure through navigation pages
5. Run optimisation from the GUI
6. Save the active network back to NetCDF

## Current status

🚧 Early-stage MVP under active development.

The codebase is already structured around a modular GUI architecture, but the feature set is still incomplete and the UI is evolving quickly.

## What currently exists

### Core functionality

- Load PyPSA networks from `.nc`
- Load PyPSA networks from CSV folders
- Save the active network as `.nc`
- Maintain multiple loaded network sessions in memory
- Switch the active session from a dedicated dock
- Run optimisation from the GUI via a worker thread
- Basic application log dock

### UI structure

The GUI currently includes:

- a central page area
- a left-side navigation dock
- a right-side **Loaded Networks** dock
- a bottom log dock

The current medium-term navigation structure is:

- **Overview**
- **Components**
  - Buses
  - Generators
  - Loads
  - Lines
  - Links
  - Stores
  - Storage Units
  - Global Constraints
- **Analysis**
  - Summary
  - Prices
  - Congestion
  - Storage
  - Emissions
- **Plots**
  - Network Map
  - Time Series
  - Capacities
- **Run**
  - Power Flow
  - Optimisation
  - Solver Settings

## Near-term development focus

The current focus is on turning the GUI skeleton into a useful PyPSA workbench by adding the most important inspection and analysis views first.

Near-term priorities include:

- summary and overview pages
- more component tables
- better network-dependent page updates
- small but robust session-management UX improvements
- result views for optimisation outputs
- first plotting pages

## Planned features

### Inspection and editing

- Table-based inspection of static network components
- Editing of selected static input data
- Better presentation of component attributes and metadata
- Validation helpers for missing or inconsistent data

### Analysis and plots

- Network summary views
- Capacity views by carrier and component
- Time-series plots for dispatch and load
- Marginal price views
- Congestion-related views
- Storage state-of-charge views
- Map-based visualisation

### Session and workflow improvements

- Modified-state indicators for sessions
- Session rename / close actions
- Scenario comparison and diff tools
- Better save / save-as handling
- Cleaner feedback around long-running actions

## Architecture

The project follows a modular structure in which UI, state handling, and PyPSA-related operations are separated.

Current high-level structure:

- `models/` — application data models such as `NetworkSession`
- `services/` — IO, storage, optimisation, and other non-UI logic
- `ui/` — main window, docks, central panel, and pages
- `workers/` — threaded background workers for long-running tasks

Design principle:

> The GUI should stay thin. PyPSA interaction, session handling, and long-running operations should live outside the UI widgets wherever possible.

## Installation (development)

```bash
git clone https://github.com/<your-username>/pypsa-gui.git
cd pypsa-gui
pip install -e .
```

## Running

Depending on the installed entry point and local setup, one of the following should work:

```bash
python -m pypsa_gui.main
```

or

```bash
pypsa-gui
```

## Dependencies

- Python >= 3.10
- pypsa
- pandas
- PySide6
- matplotlib

Additional solver dependencies may be needed depending on how optimisation is configured in the local PyPSA setup.

## Motivation

Working with PyPSA often means switching between scripts, notebooks, CSV folders, and plots. That is flexible, but it can also make simple inspection and interactive exploration slower than necessary.

`pypsa-gui` aims to provide a unified interface for:

- debugging network inputs
- exploring model structure
- teaching energy system modelling
- testing small modelling ideas quickly
- building a more accessible entry point for PyPSA users

A GUI can also be useful for users in industry or applied projects who want to inspect models and results without working directly with code all the time.

## Roadmap

### MVP roadmap

- [x] Load `.nc` networks
- [x] Load CSV-folder networks
- [x] Save active network to `.nc`
- [x] Maintain multiple loaded sessions
- [x] Switch active session from a dock
- [x] Run optimisation from the GUI
- [ ] Show summary page
- [ ] Add more component pages
- [ ] Show first result plots
- [ ] Improve power-flow workflow
- [ ] Support editing of selected data

## Contributing

The project is still in an experimental phase and the structure will continue to evolve. Ideas, issues, and contributions are welcome.

## License

MIT License
