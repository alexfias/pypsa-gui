from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any


CANONICAL_SCHEMA_VERSION = 1


def canonical_workflow_dict(workflow: Any) -> dict[str, Any]:
    """
    Convert a workflow into a deterministic JSON-compatible dictionary.

    This representation is intended for exact workflow identity, not
    semantic searching.
    """
    data = _to_json_compatible(workflow)

    if not isinstance(data, dict):
        data = {"workflow": data}

    return {
        "schema_version": CANONICAL_SCHEMA_VERSION,
        "workflow": data,
    }


def canonical_workflow_json(workflow: Any) -> str:
    """
    Return the canonical JSON representation of a workflow.
    """
    return json.dumps(
        canonical_workflow_dict(workflow),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def canonical_workflow_hash(workflow: Any) -> str:
    """
    Return a SHA-256 hash identifying the exact canonical workflow.
    """
    canonical_json = canonical_workflow_json(workflow)

    return hashlib.sha256(
        canonical_json.encode("utf-8")
    ).hexdigest()


def short_canonical_workflow_hash(
    workflow: Any,
    length: int = 16,
) -> str:
    """
    Return a shortened canonical workflow hash for display purposes.

    The full SHA-256 hash should still be used whenever exact identity
    matters.
    """
    if length < 8:
        raise ValueError(
            "Canonical hash length must be at least 8 characters."
        )

    return canonical_workflow_hash(workflow)[:length]


def _to_json_compatible(value: Any) -> Any:
    """
    Recursively convert common Python objects into deterministic,
    JSON-compatible values.
    """
    if value is None:
        return None

    if isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Enum):
        return _to_json_compatible(value.value)

    if is_dataclass(value):
        return _to_json_compatible(
            asdict(value)
        )

    if isinstance(value, dict):
        return {
            str(key): _to_json_compatible(item)
            for key, item in sorted(
                value.items(),
                key=lambda item: str(item[0]),
            )
        }

    if isinstance(value, (list, tuple)):
        return [
            _to_json_compatible(item)
            for item in value
        ]

    if isinstance(value, set):
        converted = [
            _to_json_compatible(item)
            for item in value
        ]

        return sorted(
            converted,
            key=lambda item: json.dumps(
                item,
                sort_keys=True,
                default=str,
            ),
        )

    if hasattr(value, "to_dict"):
        return _to_json_compatible(
            value.to_dict()
        )

    if hasattr(value, "__dict__"):
        return _to_json_compatible(
            {
                key: item
                for key, item in vars(value).items()
                if not key.startswith("_")
            }
        )

    return str(value)