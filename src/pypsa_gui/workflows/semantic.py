from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from pypsa_gui.workflows.models import WorkflowRecord


SEMANTIC_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class WorkflowSemanticSignature:
    """
    Search-oriented description of a scientific workflow.

    This is intentionally less detailed than the canonical workflow.
    It describes what kind of workflow was performed rather than every
    exact parameter value.
    """

    sources: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()
    technologies: tuple[str, ...] = ()
    policies: tuple[str, ...] = ()
    operations: tuple[str, ...] = ()
    analyses: tuple[str, ...] = ()

    @property
    def searchable_id(self) -> str:
        parts = [f"PF{SEMANTIC_SCHEMA_VERSION}"]

        _append_group(parts, "SRC", self.sources)
        _append_group(parts, "REG", self.regions)
        _append_group(parts, "TECH", self.technologies)
        _append_group(parts, "POL", self.policies)
        _append_group(parts, "OP", self.operations)
        _append_group(parts, "ANA", self.analyses)

        return "-".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SEMANTIC_SCHEMA_VERSION,
            "searchable_id": self.searchable_id,
            "sources": list(self.sources),
            "regions": list(self.regions),
            "technologies": list(self.technologies),
            "policies": list(self.policies),
            "operations": list(self.operations),
            "analyses": list(self.analyses),
        }

    def search_terms(self) -> set[str]:
        """
        Return all semantic tokens in a flat set.

        This will later be useful for simple workflow searching.
        """
        terms: set[str] = set()

        terms.update(self.sources)
        terms.update(self.regions)
        terms.update(self.technologies)
        terms.update(self.policies)
        terms.update(self.operations)
        terms.update(self.analyses)

        return terms


def build_semantic_signature(
    workflow: WorkflowRecord,
) -> WorkflowSemanticSignature:
    """
    Build a semantic/searchable description from a WorkflowRecord.
    """
    sources: set[str] = set()
    regions: set[str] = set()
    technologies: set[str] = set()
    policies: set[str] = set()
    operations: set[str] = set()
    analyses: set[str] = set()

    for step in workflow.steps:
        operation = _normalise_token(step.operation)
        parameters = step.parameters or {}

        _extract_source(
            operation,
            parameters,
            sources,
        )

        _extract_regions(
            operation,
            parameters,
            regions,
        )

        _extract_technologies(
            operation,
            parameters,
            technologies,
        )

        _extract_policies(
            operation,
            parameters,
            policies,
        )

        _extract_operations(
            operation,
            parameters,
            operations,
        )

        _extract_analyses(
            operation,
            parameters,
            analyses,
        )

    return WorkflowSemanticSignature(
        sources=tuple(sorted(sources)),
        regions=tuple(sorted(regions)),
        technologies=tuple(sorted(technologies)),
        policies=tuple(sorted(policies)),
        operations=tuple(sorted(operations)),
        analyses=tuple(sorted(analyses)),
    )


def searchable_workflow_id(
    workflow: WorkflowRecord,
) -> str:
    return build_semantic_signature(
        workflow
    ).searchable_id


def _extract_source(
    operation: str,
    parameters: dict[str, Any],
    output: set[str],
) -> None:
    if operation == "create_empty_network":
        output.add("build")

    elif operation in {
        "load_network",
        "open_network",
        "load_netcdf",
        "open_netcdf",
        "import_netcdf",
        "load_csv",
        "import_csv",
    }:
        output.add("load")

    elif operation in {
        "create_scenario",
        "apply_scenario",
        "build_scenario",
    }:
        output.add("scenario")

    source = _first_value(
        parameters,
        "source",
        "source_type",
        "network_source",
    )

    if source is not None:
        token = _normalise_token(source)

        if token:
            output.add(token)


def _extract_regions(
    operation: str,
    parameters: dict[str, Any],
    output: set[str],
) -> None:
    del operation

    for key in (
        "country",
        "countries",
        "region",
        "regions",
        "zone",
        "zones",
    ):
        value = parameters.get(key)

        for item in _as_values(value):
            token = _normalise_region(item)

            if token:
                output.add(token)


def _extract_technologies(
    operation: str,
    parameters: dict[str, Any],
    output: set[str],
) -> None:
    technology_related = (
        "generator" in operation
        or "storage" in operation
        or "store" in operation
        or "technology" in operation
        or "carrier" in operation
        or "link" in operation
    )

    if technology_related:
        for key in (
            "carrier",
            "technology",
            "technology_id",
            "tech",
            "preset",
            "preset_id",
        ):
            value = parameters.get(key)

            for item in _as_values(value):
                token = _normalise_technology(item)

                if token:
                    output.add(token)

    for key in (
        "technologies",
        "enabled_technologies",
        "carriers",
    ):
        value = parameters.get(key)

        for item in _as_values(value):
            token = _normalise_technology(item)

            if token:
                output.add(token)

    if "battery" in operation:
        output.add("battery")

    if (
        "hydrogen" in operation
        or operation.startswith("h2_")
        or operation.endswith("_h2")
    ):
        output.add("hydrogen")


def _extract_policies(
    operation: str,
    parameters: dict[str, Any],
    output: set[str],
) -> None:
    if "co2" in operation or "carbon" in operation:
        if (
            "price" in operation
            or "tax" in operation
        ):
            output.add("co2_price")

        elif (
            "cap" in operation
            or "limit" in operation
        ):
            output.add("co2_cap")

        else:
            output.add("co2")

    policy = _first_value(
        parameters,
        "policy",
        "policy_type",
        "co2_policy",
        "carbon_policy",
    )

    if policy is not None:
        token = _normalise_token(policy)

        if token not in {
            "",
            "none",
            "no_policy",
        }:
            output.add(token)

    if parameters.get("co2_price") is not None:
        output.add("co2_price")

    if parameters.get("carbon_price") is not None:
        output.add("co2_price")

    if parameters.get("co2_cap") is not None:
        output.add("co2_cap")

    if parameters.get("carbon_cap") is not None:
        output.add("co2_cap")

    if parameters.get("emissions_cap") is not None:
        output.add("co2_cap")


def _extract_operations(
    operation: str,
    parameters: dict[str, Any],
    output: set[str],
) -> None:
    del parameters

    if operation in {
        "optimize",
        "optimise",
        "optimization",
        "optimisation",
        "run_optimization",
        "run_optimisation",
        "solve",
    }:
        output.add("optimize")

    elif (
        "optimize" in operation
        or "optimise" in operation
    ):
        output.add("optimize")

    if operation in {
        "power_flow",
        "run_power_flow",
        "pf",
        "run_pf",
    }:
        output.add("power_flow")

    if operation in {
        "save_network",
        "save_netcdf",
    }:
        output.add("save")

    if operation.startswith("export_"):
        output.add("export")


def _extract_analyses(
    operation: str,
    parameters: dict[str, Any],
    output: set[str],
) -> None:
    del parameters

    mappings = {
        "summary": (
            "summary",
            "analyse_summary",
            "analyze_summary",
        ),
        "prices": (
            "prices",
            "price_analysis",
            "analyse_prices",
            "analyze_prices",
        ),
        "congestion": (
            "congestion",
            "analyse_congestion",
            "analyze_congestion",
        ),
        "storage": (
            "storage_analysis",
            "analyse_storage",
            "analyze_storage",
        ),
        "emissions": (
            "emissions",
            "emission_analysis",
            "analyse_emissions",
            "analyze_emissions",
        ),
        "capacities": (
            "capacities",
            "capacity_analysis",
            "analyse_capacities",
            "analyze_capacities",
        ),
        "network_map": (
            "network_map",
            "plot_network_map",
        ),
        "time_series": (
            "time_series",
            "timeseries",
            "plot_time_series",
        ),
    }

    for semantic_name, operation_names in mappings.items():
        if operation in operation_names:
            output.add(semantic_name)
            return


def _normalise_token(
    value: Any,
) -> str:
    text = str(value).strip()

    if not text:
        return ""

    text = unicodedata.normalize(
        "NFKD",
        text,
    )

    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )

    text = text.casefold()

    text = re.sub(
        r"[^a-z0-9]+",
        "_",
        text,
    )

    return text.strip("_")


def _normalise_region(
    value: Any,
) -> str:
    text = str(value).strip()

    if not text:
        return ""

    if re.fullmatch(
        r"[A-Za-z]{2,3}",
        text,
    ):
        return text.upper()

    return _normalise_token(text)


def _normalise_technology(
    value: Any,
) -> str:
    token = _normalise_token(value)

    aliases = {
        "pv": "solar",
        "solar_pv": "solar",
        "photovoltaic": "solar",

        "onwind": "wind_onshore",
        "onshore_wind": "wind_onshore",
        "wind_onshore": "wind_onshore",

        "offwind": "wind_offshore",
        "offwind_ac": "wind_offshore",
        "offwind_dc": "wind_offshore",
        "offshore_wind": "wind_offshore",
        "wind_offshore": "wind_offshore",

        "battery_storage": "battery",
        "battery_store": "battery",
        "battery_storage_unit": "battery",

        "h2": "hydrogen",
        "hydrogen_storage": "hydrogen",
    }

    return aliases.get(
        token,
        token,
    )


def _first_value(
    parameters: dict[str, Any],
    *keys: str,
) -> Any:
    for key in keys:
        if key not in parameters:
            continue

        value = parameters[key]

        if value is not None:
            return value

    return None


def _as_values(
    value: Any,
) -> list[Any]:
    if value is None:
        return []

    if isinstance(value, dict):
        return [
            key
            for key, enabled in value.items()
            if bool(enabled)
        ]

    if isinstance(
        value,
        (list, tuple, set),
    ):
        return list(value)

    return [value]


def _append_group(
    parts: list[str],
    prefix: str,
    values: tuple[str, ...],
) -> None:
    if not values:
        return

    joined = ".".join(values)

    parts.append(
        f"{prefix}[{joined}]"
    )