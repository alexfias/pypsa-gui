# src/pypsa_gui/workflows/recorder.py

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from pypsa_gui.workflows.models import WorkflowRecord
from pypsa_gui.workflows.operations import WorkflowOperation


class WorkflowRecorder:
    """Record scientifically meaningful workflow operations.

    The recorder stores domain-level modelling operations rather than
    low-level GUI events such as button clicks, tab changes, or text edits.
    """

    def __init__(self, workflow: WorkflowRecord | None = None) -> None:
        self.workflow = workflow if workflow is not None else WorkflowRecord()

    def record(
        self,
        operation: WorkflowOperation | str,
        parameters: Mapping[str, Any] | None = None,
    ) -> None:
        """Append one operation to the workflow.

        Parameters are normalized into JSON-compatible values before they are
        stored. This helps ensure deterministic serialization later.
        """

        operation_name = (
            operation.value
            if isinstance(operation, WorkflowOperation)
            else str(operation)
        )

        normalized_parameters = self._normalize(
            dict(parameters or {})
        )

        self.workflow.add_step(
            operation=operation_name,
            parameters=normalized_parameters,
        )

    def record_load_network(
        self,
        *,
        source_path: str | Path | None,
        checksum: str | None = None,
        network_name: str | None = None,
    ) -> None:
        """Record loading an existing PyPSA network."""

        self.record(
            WorkflowOperation.LOAD_NETWORK,
            {
                "source_path": source_path,
                "checksum": checksum,
                "network_name": network_name,
            },
        )

    def record_create_empty_network(
        self,
        *,
        name: str | None = None,
    ) -> None:
        """Record creation of a new empty network."""

        self.record(
            WorkflowOperation.CREATE_EMPTY_NETWORK,
            {
                "name": name,
            },
        )

    def record_create_scenario(
        self,
        definition: Any,
    ) -> None:
        """Record creation of a scenario from a scenario definition.

        The definition may be a dataclass, mapping, or plain Python object
        exposing attributes through ``__dict__``.
        """

        self.record(
            WorkflowOperation.CREATE_SCENARIO,
            self._object_to_mapping(definition),
        )

    def record_modify_network(
        self,
        *,
        modification: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> None:
        """Record a generic scientific network modification.

        This method is useful before more specific workflow operations have
        been introduced.
        """

        self.record(
            WorkflowOperation.MODIFY_NETWORK,
            {
                "modification": modification,
                "parameters": dict(parameters or {}),
            },
        )

    def record_optimization(
        self,
        *,
        solver: str,
        options: Mapping[str, Any] | None = None,
        formulation: str | None = None,
        status: str | None = None,
    ) -> None:
        """Record an optimization operation."""

        self.record(
            WorkflowOperation.OPTIMIZE,
            {
                "solver": solver,
                "formulation": formulation,
                "options": dict(options or {}),
                "status": status,
            },
        )

    def record_export_network(
        self,
        *,
        path: str | Path | None = None,
        format_name: str | None = None,
    ) -> None:
        """Record exporting the PyPSA network."""

        self.record(
            WorkflowOperation.EXPORT_NETWORK,
            {
                "path": path,
                "format": format_name,
            },
        )

    def record_export_report(
        self,
        *,
        path: str | Path | None = None,
        format_name: str = "pdf",
        template: str | None = None,
    ) -> None:
        """Record exporting a report."""

        self.record(
            WorkflowOperation.EXPORT_REPORT,
            {
                "path": path,
                "format": format_name,
                "template": template,
            },
        )

    def clear(self) -> None:
        """Remove all recorded workflow steps."""

        self.workflow.clear()

    @staticmethod
    def _object_to_mapping(value: Any) -> dict[str, Any]:
        """Convert a supported object into a dictionary."""

        if is_dataclass(value):
            return asdict(value)

        if isinstance(value, Mapping):
            return dict(value)

        if hasattr(value, "__dict__"):
            return {
                key: item
                for key, item in vars(value).items()
                if not key.startswith("_")
            }

        raise TypeError(
            "Workflow objects must be dataclasses, mappings, or objects "
            "with public attributes."
        )

    @classmethod
    def _normalize(cls, value: Any) -> Any:
        """Convert values into deterministic JSON-compatible structures."""

        if value is None:
            return None

        if isinstance(value, Enum):
            return cls._normalize(value.value)

        if isinstance(value, Path):
            return value.as_posix()

        if is_dataclass(value):
            return cls._normalize(asdict(value))

        if isinstance(value, Mapping):
            return {
                str(key): cls._normalize(item)
                for key, item in sorted(
                    value.items(),
                    key=lambda pair: str(pair[0]),
                )
            }

        if isinstance(value, tuple):
            return [cls._normalize(item) for item in value]

        if isinstance(value, list):
            return [cls._normalize(item) for item in value]

        if isinstance(value, set):
            normalized_items = [
                cls._normalize(item)
                for item in value
            ]
            return sorted(
                normalized_items,
                key=repr,
            )

        if isinstance(value, (str, int, float, bool)):
            return value

        if hasattr(value, "item"):
            try:
                return cls._normalize(value.item())
            except (TypeError, ValueError):
                pass

        return str(value)