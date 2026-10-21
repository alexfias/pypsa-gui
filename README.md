# pypsa-gui

An experimental desktop workbench for building, inspecting, optimising, and visualising PyPSA energy-system models.

The application combines a PySide6 interface with PyPSA, pandas, and Matplotlib. It is intended for teaching, model exploration, and research prototyping: load an existing network, build a small scenario, inspect components and results, and export figures or an analysis report.

![pypsa-gui screenshot](docs/images/screenshot.png)

**Status:** active prototype, package version `0.1.0`. The application now contains substantial modelling and analysis functionality, but some workflows are incomplete and numerical validation needs broader test coverage. See [Known limitations](#known-limitations) before using results in a study.

**Solver note:** the current GUI optimisation runner uses **Gurobi**. The Solver Settings page is not yet connected to that runner; choosing HiGHS there does not change the solver used.

## What is implemented

| Area | Current capabilities |
| --- | --- |
| Network files and sessions | Open NetCDF networks or PyPSA CSV folders; keep several networks in memory; switch the active network; save or save as NetCDF. |
| Scenario Builder | Create a country subset of the bundled teaching network, configure demand, technologies, investment costs, interconnection, and CO₂ policy. |
| Network Builder | Create an empty network, place locations on a map, add internal buses and assets, and connect locations with lines or links. |
| Component inspection | Inspect and edit static component tables; search, sort, show or hide columns, and copy selected cells in the general component pages. |
| Bus and location diagrams | Explore connected equipment, navigate to neighbouring buses, inspect parameters, group buses visually, and export diagrams. |
| Analysis | Network summary, nodal prices, line/link loading, storage operation, and generator-emissions views. |
| Plots | Geographical or schematic network maps, installed-generation capacity mixes, time-series selection and aggregation, and capacity/generation views. |
| Optimisation | Background execution, cancellation requests, a model-size preview, and PDF analysis reports for networks containing results. |
| Pre-run tools | Add load-shedding generators, change nominal capacities, and select every nth snapshot. These operations have limitations described below. |
| Workflow records | Display recorded operations, canonical and semantic identifiers, and export a workflow record as JSON. |
| Research modules | A module registration interface, a flow-tracing input preview, and an ML-surrogate configuration interface. The scientific backends are not complete. |

## Installation

Python **3.10 or newer** is declared in `pyproject.toml`. The supplied Conda environment selects Python **3.11**. Run installation commands from the directory containing `pyproject.toml`.

Clone the repository:

```bash
git clone https://github.com/alexfias/pypsa-gui.git
cd pypsa-gui
```

Alternatively, download and extract the repository ZIP, then open a terminal in its extracted project directory.

### Conda / Miniconda

```bash
conda env create -f environment.yml
conda activate pypsa-gui
pypsa-gui
```

The environment file already installs the project in editable mode. If you already have a suitable environment, activate it and run:

```bash
python -m pip install -e .
pypsa-gui
```

### Standard Python virtual environment

Create the environment:

```bash
python -m venv .venv
```

Activate it with the command for your shell:

| Shell | Command |
| --- | --- |
| Windows Command Prompt | `.venv\Scripts\activate.bat` |
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |
| Linux / macOS | `source .venv/bin/activate` |

Then install and launch:

```bash
python -m pip install -e .
pypsa-gui
```

The equivalent module entry point is:

```bash
python -m pypsa_gui.main
```

### Solving networks

Inspection, editing, and plotting do not require a Gurobi installation. Running optimisation through the current GUI does. Install its Python interface in the same environment:

```bash
python -m pip install gurobipy
```

Configure a Gurobi licence suitable for your model size; see the [official installation guide](https://support.gurobi.com/hc/en-us/articles/360044290292-How-do-I-install-Gurobi-for-Python).

Although `highspy` is a project dependency and HiGHS appears in Solver Settings, the runner currently calls Gurobi with `Method=2` and `Crossover=0`. Other settings on that page are not passed to the run either. A missing Gurobi installation or unsuitable licence therefore prevents GUI optimisation even when HiGHS is installed.

### Optional dependencies

```bash
python -m pip install -e ".[map]"
python -m pip install -e ".[dev]"
```

The `map` extra installs Cartopy; the `dev` extra installs pytest, Black, and Ruff. Geographical plotting works without Cartopy. The **Network Map** renderer uses locally cached Cartopy coastline and border data when available, and otherwise displays the network on longitude/latitude axes.

The base installation includes PyPSA, HiGHS, pandas, PySide6, Matplotlib, NetworkX, and ReportLab. Dependency versions are not currently locked.

## First walkthrough

1. Start `pypsa-gui`.
2. Use **File → Open NetCDF Network...** or **File → Open CSV Folder...**. For an included example, open `src/pypsa_gui/data/teaching/elec_s_37.nc` from the repository.
3. Choose **Full** to expose all sections. The **Loaded Networks** dock selects the active network.
4. Explore **Overview**, the component tables, and **Components → Buses**. Use the bus diagram to inspect equipment and neighbouring buses.
5. Open **Plots → Network Map**. Try Auto, Geographical, and Schematic layouts, and switch between topology and installed generation capacity.
6. If Gurobi is configured, open **Run → Optimisation**, optionally preview the model size, then run the model. Check the returned solver status before interpreting results.
7. Explore **Analysis** and **Plots**. Networks that already contain results can be inspected without rerunning optimisation. The Optimisation page also offers PDF report export.
8. Save the network through **File → Save As NetCDF...**. Export the workflow JSON separately from **Overview → Workflow** if needed.

Workspace presets control navigation: **Full** exposes all sections; **Lightweight** exposes Build, Components, and Run; **Analysis** exposes Overview, Analysis, and Plots. A Custom option selects individual sections.

## Building models

### Teaching scenarios

Open **Build → Scenario Builder** and select **one to three countries**. The current interface offers Germany, Denmark, the Netherlands, Belgium, France, Spain, Poland, and Norway, using the bundled `elec_s_37.nc` source network.

Available presets are **Reference**, **Cheap batteries**, **High CO₂ price**, **High demand**, and **No interconnection**. Further controls set demand scaling, technology inclusion, investment-cost multipliers, interconnection, and a CO₂ price or emissions cap. The builder adds standard battery and hydrogen-storage investment options and creates an unsolved network in a new session.

Country selection removes components outside the selected countries and connections to them; it does not model exchanges with the omitted system. The relative CO₂ target uses a demand-based reference of **0.35 tCO₂/MWh**, rather than historical emissions or a solved reference scenario. Presets and subsequent custom settings can combine, so inspect the scenario assumptions before comparing results.

### Networks from scratch

Open **Build → Network Builder → Create empty network**. Place locations, open a location to add internal buses, then add generators, loads, stores, or storage units. Use the line and link tools to connect locations.

Generator dialogs include technology presets and renewable-availability profiles. The bundled profile library contains example solar and onshore-wind profiles for Germany and Spain; profiles from a loaded network can also be registered. Technology costs are explicitly illustrative defaults, not a maintained cost database.

The separate **Start from template** option is currently disabled.

## Visualisation and reporting

- **Network Map:** deterministic schematic fallback for missing or unsuitable coordinates; lines, links, transformers, and isolated buses; carrier colours and generation-capacity pies. The installed-capacity view uses `generators.p_nom`, not `p_nom_opt`.
- **Bus diagrams:** all directly connected equipment, technology or electrical symbol modes, component details, neighbouring-bus navigation, scrollable canvases, and a separate-window explorer.
- **Location diagrams:** group buses by a matching, non-empty `buses.location` value, or select a manual group. Each bus retains its own busbar and equipment. Grouping is a visual operation and does not aggregate the network equations.
- **Time series:** select component types, fields, carriers, and assets; display individual series or aggregate them by sum, mean, or carrier.
- **Exports:** the shared figure panel exports PNG, SVG, and PDF. The optimisation report includes scenario assumptions, objective value, demand and generation, electricity-price statistics, capacities, storage, and generator emissions where data are available.

See the [network-map guide](docs/visualization-step-1.md) and [bus/location-diagram guide](docs/bus-diagrams.md) for detailed controls and rendering scope. Older implementation notes in those guides describe earlier snapshots of the project.

![Example location diagram](docs/images/location-diagram.png)

## Known limitations

The following distinctions matter when using the current version:

| Area | Limitation |
| --- | --- |
| Solver configuration | Solver Settings is not wired into optimisation; Gurobi and its options are hard-coded in the runner. Cancellation depends on the solver model exposing a termination method. |
| Power flow | The navigation page is a placeholder, and the menu action does not execute a power flow. |
| Component editing | Renaming a component in a general component table changes its static index without renaming its time-series columns. Avoid this operation for assets with time series. Validation and refresh after edits are incomplete. |
| Saving changes | Modified-state tracking is incomplete for table and pre-run edits. Closing the application does not prompt to save modified networks. Save explicitly; the session list and workspace state are not a persistent project format. |
| Temporal reduction | Pre-Run Tools keeps every nth snapshot without aggregating the intervening data or adjusting snapshot weights. This changes represented energy and duration; it is not a validated annual time-aggregation method. |
| Capacity controls | The pre-run capacity tool changes `p_nom` or `e_nom`; it does not implement the advertised inequalities as investment bounds or aggregate optimisation constraints. |
| Emissions and other totals | The Emissions page omits generator-efficiency correction and snapshot weighting. The PDF report applies both for generator emissions, so the two can disagree. Some other analysis views also count snapshots as hours. Both emissions views have a generator-focused scope. |
| Result validity | Editing inputs does not systematically invalidate old results. PDF availability is inferred from generator-dispatch data, not from a fresh successful solve. Rerun after input changes and inspect solver termination status. |
| Workflow records | Selected creation, loading, and optimisation operations are recorded. Not every edit is captured; workflow JSON is exported separately and is not a complete replayable project archive. |
| Research modules | Flow Tracing currently previews input arrays for link-based networks; it does not calculate flow attribution. ML Surrogate can save/load configuration, but dataset processing, training, and evaluation are placeholders. |

The map displays multi-terminal links between `bus0` and `bus1`; local bus/location diagrams provide more terminal detail. Symbols are simplified, not an IEC-certified symbol set. Pandapower import and automated scenario comparison are not implemented.

The bundled teaching network was exported by an older PyPSA version and may produce compatibility warnings. Check model assumptions, component data, snapshot weights, and solver results when using it with another PyPSA version. For emissions accounting, compare against [PyPSA's documented formulation](https://docs.pypsa.org/latest/user-guide/optimization/global-constraints/#primary-energy).

## Code structure

| Directory | Responsibility |
| --- | --- |
| `src/pypsa_gui/models/` | Network sessions, view options, locations, scenario definitions, solver settings, and profile/preset models. |
| `src/pypsa_gui/services/` | Network IO and storage, scenario construction, time-series/technology libraries, optimisation, analysis, and PDF reporting. |
| `src/pypsa_gui/ui/` | Main window, navigation, dialogs, tables, pages, and reusable figure widgets. |
| `src/pypsa_gui/visualization/` | Network, bus, and location renderers and technology symbols. |
| `src/pypsa_gui/workers/` | Background optimisation worker. |
| `src/pypsa_gui/workflows/` | Workflow operations, recording, JSON serialisation, and identifiers. |
| `src/pypsa_gui/modules/` | Research-module interface, registry, and initial modules. |
| `src/pypsa_gui/data/` | Bundled teaching network, technology presets, and example time-series profiles. |
| `tests/` | Automated renderer, diagram, export, and selected Qt-interaction checks. |

The intended design separates UI, session state, numerical services, and plotting. Some builders and reports remain large and would benefit from further separation. Expensive analysis-page data refreshes are deferred until those pages are opened; model previews and report generation still run on the UI thread.

To add a research module, implement `BaseResearchModule` from [modules/base.py](src/pypsa_gui/modules/base.py), describe its pages with `ModulePageDefinition`, and register it in [modules/registry.py](src/pypsa_gui/modules/registry.py). The current registry is explicit; dropping a file into the directory does not register it automatically.

## Development and validation

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

For a headless Linux run:

```bash
QT_QPA_PLATFORM=offscreen MPLBACKEND=Agg python -m pytest -q
```

The current suite contains **33 test cases** across four visualisation-focused test files. It passed during the October 2026 review with Python 3.12, PyPSA 1.4.0, PySide6 6.12.0, and pandas 3.0.6. This is evidence for the covered behaviour, not full application or cross-platform validation. The repository does not yet include a CI workflow or broad regression tests for optimisation, scenario construction, editing, and scientific metrics.

Priorities for the next development stage:

1. Connect solver settings to the runner and support HiGHS end to end.
2. Centralise validated network edits, safe renaming, result invalidation, and save-state tracking.
3. Share consistent weighted metrics between GUI pages and reports; correct temporal reduction and capacity controls.
4. Add regression tests for those workflows and run them in CI with a documented dependency set.
5. Implement power flow and complete research-module backends as separate, tested additions.

Contributions and issue reports are welcome. Include the relevant steps, a minimal network when possible, dependency versions, and the solver status or traceback.

## Licence

The application code is licensed under the [MIT License](LICENSE). Third-party dependencies and solvers retain their own licences.
