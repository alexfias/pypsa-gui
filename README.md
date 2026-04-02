# pypsa-gui

An experimental desktop GUI for inspecting, editing, solving, and
visualising PyPSA networks.

## Overview

`pypsa-gui` aims to provide a lightweight, interactive workbench for
working with PyPSA models without relying on notebooks or scripts.

The tool focuses on a simple workflow:

1.  Load a PyPSA network (`.nc`)
2.  Inspect input data as tables
3.  Modify network parameters
4.  Run optimisation or power flow
5.  Visualise results

## Status

🚧 Early-stage MVP (under active development)

The current focus is on building a clean and extensible architecture.\
Features and APIs may change frequently.

## Planned Features

### Core

-   Load and save PyPSA networks (`.nc`)
-   Table-based inspection of network components
-   Editing of static input data (e.g. generators, loads, lines)
-   Run optimisation (`lopf`) and power flow

### Visualisation

-   Installed capacity by carrier
-   Dispatch time series
-   Marginal prices
-   Storage state of charge

### UX Improvements (later)

-   Time series editing
-   Scenario comparison / diff
-   Validation checks
-   Map-based visualisation
-   Batch editing tools

## Architecture

The project follows a modular structure:

-   `core/` --- PyPSA interaction (IO, simulation, results)
-   `app/` --- application state and controller logic
-   `ui/` --- PySide6 GUI components

Design principle:

> The GUI does not directly manipulate PyPSA.\
> All interactions go through a controller layer.

## Installation (development)

``` bash
git clone https://github.com/<your-username>/pypsa-gui.git
cd pypsa-gui

pip install -e .
```

## Running

``` bash
python -m pypsa_gui.main
```

## Dependencies

-   Python ≥ 3.10
-   pypsa
-   pandas
-   PySide6
-   matplotlib

## Motivation

Working with PyPSA often involves switching between:

-   notebooks
-   CSV files
-   scripts
-   plots

This project aims to provide a unified interface that simplifies:

-   debugging models
-   exploring scenarios
-   teaching energy system modelling
-   rapid experimentation

## Roadmap (MVP)

-   [ ] Load `.nc` networks
-   [ ] Display static component tables
-   [ ] Edit table entries
-   [ ] Save modified networks
-   [ ] Run optimisation
-   [ ] Show basic result plots

## Contributing

This project is currently in an early experimental phase.\
Contributions and ideas are welcome, but the structure may evolve
rapidly.

## License

MIT License
