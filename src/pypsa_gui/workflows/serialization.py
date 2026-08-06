from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from .models import WorkflowRecord


def workflow_to_dict(
    workflow: WorkflowRecord,
) -> dict:
    return asdict(workflow)


def workflow_to_json(
    workflow: WorkflowRecord,
) -> str:
    return json.dumps(
        workflow_to_dict(workflow),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )


def workflow_id(
    workflow: WorkflowRecord,
) -> str:
    canonical = json.dumps(
        workflow_to_dict(workflow),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()