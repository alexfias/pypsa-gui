# Architecture

## Main Components

- MainWindow: main application shell
- CentralPanel: manages pages (QStackedWidget)
- Pages: Overview, Components, Analysis, etc.
- Services: network_io, optimisation

## Data Flow

Network → loaded into session → passed to pages → visualised/modified

## Design Principles

- Modular pages
- Separation of UI and logic
- Extendable for research modules