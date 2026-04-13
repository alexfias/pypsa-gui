from __future__ import annotations

from dataclasses import dataclass, field

WORKSPACE_PRESETS: dict[str, set[str]] = {
    "full": {"overview", "components", "analysis", "plots", "run"},
    "lightweight": {"components", "run"},
    "analysis": {"overview", "analysis", "plots"},
}

NAVIGATION_STRUCTURE: dict[str, list[str]] = {
    "overview": [],
    "components": [
        "Buses",
        "Generators",
        "Loads",
        "Lines",
        "Links",
        "Stores",
        "Storage Units",
        "Global Constraints",
    ],
    "analysis": [
        "Summary",
        "Prices",
        "Congestion",
        "Storage",
        "Emissions",
    ],
    "plots": [
        "Network Map",
        "Time Series",
        "Capacities",
    ],
    "run": [
        "Power Flow",
        "Optimisation",
        "Solver Settings",
    ],
}

SECTION_TITLES: dict[str, str] = {
    "overview": "Overview",
    "components": "Components",
    "analysis": "Analysis",
    "plots": "Plots",
    "run": "Run",
}

PAGE_TO_SECTION: dict[str, str] = {
    "Overview": "overview",
    "Buses": "components",
    "Generators": "components",
    "Loads": "components",
    "Lines": "components",
    "Links": "components",
    "Stores": "components",
    "Storage Units": "components",
    "Global Constraints": "components",
    "Summary": "analysis",
    "Prices": "analysis",
    "Congestion": "analysis",
    "Storage": "analysis",
    "Emissions": "analysis",
    "Network Map": "plots",
    "Time Series": "plots",
    "Capacities": "plots",
    "Power Flow": "run",
    "Optimisation": "run",
    "Solver Settings": "run",
}


@dataclass
class SessionViewOptions:
    workspace_name: str = "full"
    enabled_sections: set[str] = field(
        default_factory=lambda: set(WORKSPACE_PRESETS["full"])
    )