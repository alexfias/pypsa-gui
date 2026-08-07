from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from pypsa_gui.models.technology_preset import TechnologyPreset


class TechnologyLibrary:
    def __init__(self) -> None:
        self._presets: dict[str, TechnologyPreset] = {}

    def add_preset(
        self,
        preset: TechnologyPreset,
        *,
        replace: bool = False,
    ) -> None:
        if preset.id in self._presets and not replace:
            raise ValueError(
                f'A technology preset with id "{preset.id}" already exists.'
            )
        self._presets[preset.id] = preset

    def get_preset(self, preset_id: str) -> TechnologyPreset:
        try:
            return self._presets[preset_id]
        except KeyError as exc:
            raise KeyError(
                f'Unknown technology preset id: "{preset_id}".'
            ) from exc

    def list_presets(
        self,
        *,
        component_type: str | None = None,
        carrier: str | None = None,
        category: str | None = None,
    ) -> list[TechnologyPreset]:
        presets = list(self._presets.values())

        if component_type is not None:
            target = component_type.strip().lower()
            presets = [
                preset
                for preset in presets
                if preset.component_type.strip().lower() == target
            ]

        if carrier is not None:
            target = carrier.strip().lower()
            presets = [
                preset
                for preset in presets
                if preset.carrier.strip().lower() == target
            ]

        if category is not None:
            target = category.strip().lower()
            presets = [
                preset
                for preset in presets
                if preset.category.strip().lower() == target
            ]

        return sorted(
            presets,
            key=lambda preset: (
                preset.category.lower(),
                preset.name.lower(),
            ),
        )

    def load_packaged_presets(
        self,
        *,
        package: str = "pypsa_gui",
        manifest_relative_path: str = "data/technologies/manifest.json",
        replace: bool = True,
    ) -> list[TechnologyPreset]:
        package_root = resources.files(package)
        manifest_resource = package_root.joinpath(
            manifest_relative_path
        )

        if not manifest_resource.is_file():
            raise FileNotFoundError(
                f"Technology manifest not found: {manifest_relative_path}"
            )

        with manifest_resource.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)

        return self._load_manifest_entries(
            manifest,
            replace=replace,
        )

    def load_manifest_file(
        self,
        file_path: str | Path,
        *,
        replace: bool = True,
    ) -> list[TechnologyPreset]:
        with Path(file_path).open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)

        return self._load_manifest_entries(
            manifest,
            replace=replace,
        )

    def _load_manifest_entries(
        self,
        manifest: Any,
        *,
        replace: bool,
    ) -> list[TechnologyPreset]:
        if not isinstance(manifest, list):
            raise ValueError(
                "Technology manifest must contain a JSON list."
            )

        presets: list[TechnologyPreset] = []

        for entry in manifest:
            preset = self._preset_from_entry(entry)
            self.add_preset(
                preset,
                replace=replace,
            )
            presets.append(preset)

        return presets

    @staticmethod
    def _preset_from_entry(
        entry: dict[str, Any],
    ) -> TechnologyPreset:
        defaults = entry["defaults"]
        source = entry.get("source", {}) or {}

        return TechnologyPreset(
            id=str(entry["id"]),
            name=str(entry["name"]),
            component_type=str(entry["component_type"]),
            carrier=str(entry["carrier"]),
            capital_cost=float(defaults["capital_cost"]),
            marginal_cost=float(defaults["marginal_cost"]),
            efficiency=float(defaults["efficiency"]),
            lifetime=float(defaults["lifetime"]),
            p_nom_extendable=bool(
                defaults.get("p_nom_extendable", True)
            ),
            default_p_max_pu=float(
                defaults.get("p_max_pu", 1.0)
            ),
            profile_carrier=(
                str(entry["profile_carrier"])
                if entry.get("profile_carrier") is not None
                else None
            ),
            category=str(entry.get("category", "Other")),
            description=str(entry.get("description", "")),
            source_provider=(
                str(source["provider"])
                if source.get("provider") is not None
                else None
            ),
            source_year=(
                int(source["year"])
                if source.get("year") is not None
                else None
            ),
            source_reference=(
                str(source["reference"])
                if source.get("reference") is not None
                else None
            ),
            metadata={
                str(key): str(value)
                for key, value in (
                    entry.get("metadata", {}) or {}
                ).items()
            },
        )
