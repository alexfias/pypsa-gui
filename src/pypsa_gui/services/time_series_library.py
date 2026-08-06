from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from importlib import resources
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
import pypsa

from pypsa_gui.models.time_series_profile import (
    TimeSeriesProfile,
)


ExternalProfileFetcher = Callable[
    [Mapping[str, Any]],
    TimeSeriesProfile,
]


class TimeSeriesLibrary:
    """
    Central interface for generator availability profiles.

    Supported profile sources:

    - packaged profiles described by a JSON manifest;
    - existing ``network.generators_t.p_max_pu`` series;
    - user-imported CSV files;
    - externally fetched profiles through registered provider callbacks;
    - profiles created directly by application code.

    The generator dialog only interacts with this library and therefore
    does not need to know where a profile originated.
    """

    def __init__(self) -> None:
        self._profiles: dict[
            str,
            TimeSeriesProfile,
        ] = {}

        self._external_fetchers: dict[
            str,
            ExternalProfileFetcher,
        ] = {}

    # ------------------------------------------------------------------
    # Registry
    # ------------------------------------------------------------------

    def add_profile(
        self,
        profile: TimeSeriesProfile,
        *,
        replace: bool = False,
    ) -> None:
        if (
            profile.id in self._profiles
            and not replace
        ):
            raise ValueError(
                f'A profile with id "{profile.id}" already exists.'
            )

        self._profiles[
            profile.id
        ] = profile

    def remove_profile(
        self,
        profile_id: str,
    ) -> None:
        self._profiles.pop(
            profile_id,
            None,
        )

    def clear(
        self,
        *,
        keep_external_fetchers: bool = True,
    ) -> None:
        self._profiles.clear()

        if not keep_external_fetchers:
            self._external_fetchers.clear()

    def get_profile(
        self,
        profile_id: str,
    ) -> TimeSeriesProfile:
        try:
            return self._profiles[
                profile_id
            ]
        except KeyError as exc:
            raise KeyError(
                f'Unknown profile id: "{profile_id}".'
            ) from exc

    def list_profiles(
        self,
        carrier: str | None = None,
        region: str | None = None,
        source_type: str | None = None,
    ) -> list[TimeSeriesProfile]:
        profiles = list(
            self._profiles.values()
        )

        if carrier is not None:
            carrier_normalized = (
                carrier.strip().lower()
            )
            profiles = [
                profile
                for profile in profiles
                if profile.carrier.strip().lower()
                == carrier_normalized
            ]

        if region is not None:
            region_normalized = (
                region.strip().lower()
            )
            profiles = [
                profile
                for profile in profiles
                if profile.region.strip().lower()
                == region_normalized
            ]

        if source_type is not None:
            source_type_normalized = (
                source_type.strip().lower()
            )
            profiles = [
                profile
                for profile in profiles
                if profile.metadata.get(
                    "source_type",
                    "",
                ).strip().lower()
                == source_type_normalized
            ]

        return sorted(
            profiles,
            key=lambda profile: (
                profile.carrier.lower(),
                profile.name.lower(),
                profile.region.lower(),
            ),
        )

    def register_profiles(
        self,
        profiles: Iterable[
            TimeSeriesProfile
        ],
        *,
        replace: bool = False,
    ) -> None:
        for profile in profiles:
            self.add_profile(
                profile,
                replace=replace,
            )

    # ------------------------------------------------------------------
    # Packaged manifest profiles
    # ------------------------------------------------------------------

    def load_packaged_profiles(
        self,
        *,
        package: str = "pypsa_gui",
        manifest_relative_path: str = (
            "data/time_series/manifest.json"
        ),
        replace: bool = True,
    ) -> list[TimeSeriesProfile]:
        """
        Load profiles bundled with the installed application.

        The manifest path is resolved through ``importlib.resources`` so
        this also works after the project has been installed as a wheel.
        """
        package_root = resources.files(
            package
        )
        manifest_resource = package_root.joinpath(
            manifest_relative_path
        )

        if not manifest_resource.is_file():
            raise FileNotFoundError(
                "Packaged time-series manifest not found: "
                f"{manifest_relative_path}"
            )

        with manifest_resource.open(
            "r",
            encoding="utf-8",
        ) as handle:
            manifest = json.load(
                handle
            )

        if not isinstance(
            manifest,
            list,
        ):
            raise ValueError(
                "The time-series manifest must contain a JSON list."
            )

        manifest_directory = (
            manifest_resource.parent
        )
        loaded_profiles: list[
            TimeSeriesProfile
        ] = []

        for entry in manifest:
            profile = self._profile_from_manifest_entry(
                entry=entry,
                manifest_directory=manifest_directory,
            )

            self.add_profile(
                profile,
                replace=replace,
            )
            loaded_profiles.append(
                profile
            )

        return loaded_profiles

    def _profile_from_manifest_entry(
        self,
        *,
        entry: Mapping[str, Any],
        manifest_directory: Any,
    ) -> TimeSeriesProfile:
        required_fields = {
            "id",
            "name",
            "file",
            "carrier",
            "timestamp_column",
            "value_column",
        }

        missing_fields = sorted(
            required_fields
            - set(entry)
        )

        if missing_fields:
            raise ValueError(
                "Manifest entry is missing required fields: "
                + ", ".join(missing_fields)
            )

        relative_file = str(
            entry["file"]
        )
        profile_resource = (
            manifest_directory.joinpath(
                relative_file
            )
        )

        if not profile_resource.is_file():
            raise FileNotFoundError(
                "Profile file referenced by manifest was not found: "
                f"{relative_file}"
            )

        with profile_resource.open(
            "rb",
        ) as handle:
            frame = pd.read_csv(
                handle
            )

        timestamp_column = str(
            entry["timestamp_column"]
        )
        value_column = str(
            entry["value_column"]
        )

        if timestamp_column not in frame.columns:
            raise ValueError(
                f'Timestamp column "{timestamp_column}" '
                f'not found in "{relative_file}".'
            )

        if value_column not in frame.columns:
            raise ValueError(
                f'Value column "{value_column}" '
                f'not found in "{relative_file}".'
            )

        timestamp_format = entry.get(
            "timestamp_format"
        )
        day_first = bool(
            entry.get(
                "day_first",
                False,
            )
        )

        timestamps = pd.to_datetime(
            frame[timestamp_column],
            format=timestamp_format,
            dayfirst=day_first,
            errors="raise",
        )

        timezone = (
            entry.get(
                "temporal_scope",
                {},
            )
            or {}
        ).get(
            "timezone"
        )

        if timezone:
            if timestamps.dt.tz is None:
                timestamps = (
                    timestamps.dt.tz_localize(
                        timezone
                    )
                )
            else:
                timestamps = (
                    timestamps.dt.tz_convert(
                        timezone
                    )
                )

            # Keep the timezone in profile metadata, but use UTC-naive
            # timestamps internally because PyPSA snapshots are commonly
            # represented without timezone information.
            timestamps = (
                timestamps.dt.tz_convert("UTC")
                .dt.tz_localize(None)
            )

        values = pd.to_numeric(
            frame[value_column],
            errors="coerce",
        )

        if values.isna().any():
            invalid_count = int(
                values.isna().sum()
            )

            raise ValueError(
                f'Profile "{entry["id"]}" contains '
                f"{invalid_count} invalid or missing values."
            )

        series = pd.Series(
            values.to_numpy(
                dtype=float
            ),
            index=pd.DatetimeIndex(
                timestamps
            ),
            name=str(
                entry["name"]
            ),
        )

        spatial_scope = (
            entry.get(
                "spatial_scope",
                {},
            )
            or {}
        )
        source = (
            entry.get(
                "source",
                {},
            )
            or {}
        )
        temporal_scope = (
            entry.get(
                "temporal_scope",
                {},
            )
            or {}
        )

        region = (
            spatial_scope.get("code")
            or spatial_scope.get("name")
            or spatial_scope.get("type")
            or "unspecified"
        )

        metadata = {
            "source_type": "packaged",
            "profile_kind": str(
                entry.get(
                    "profile_kind",
                    "p_max_pu",
                )
            ),
            "units": str(
                entry.get(
                    "units",
                    "per_unit",
                )
            ),
            "file": relative_file,
            "spatial_scope_type": str(
                spatial_scope.get(
                    "type",
                    "",
                )
            ),
            "spatial_scope_code": str(
                spatial_scope.get(
                    "code",
                    "",
                )
            ),
            "spatial_scope_name": str(
                spatial_scope.get(
                    "name",
                    "",
                )
            ),
            "year": str(
                temporal_scope.get(
                    "year",
                    "",
                )
            ),
            "resolution": str(
                temporal_scope.get(
                    "resolution",
                    "",
                )
            ),
            "timezone": str(
                temporal_scope.get(
                    "timezone",
                    "",
                )
            ),
            "provider": str(
                source.get(
                    "provider",
                    "",
                )
            ),
            "source_method": str(
                source.get(
                    "method",
                    "",
                )
            ),
            "source_reference": str(
                source.get(
                    "reference",
                    "",
                )
                or ""
            ),
            "description": str(
                entry.get(
                    "description",
                    "",
                )
            ),
        }

        return TimeSeriesProfile(
            id=str(
                entry["id"]
            ),
            name=str(
                entry["name"]
            ),
            carrier=str(
                entry["carrier"]
            ),
            region=str(
                region
            ),
            values=series,
            source=str(
                source.get(
                    "provider",
                    "Packaged profile",
                )
            ),
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Existing network profiles
    # ------------------------------------------------------------------

    def register_network_profiles(
        self,
        network: pypsa.Network,
        *,
        region: str = "active network",
        source: str = "active network",
        replace: bool = True,
    ) -> list[TimeSeriesProfile]:
        """
        Register all time-varying generator availability profiles from
        the active network.
        """
        time_series = getattr(
            network.generators_t,
            "p_max_pu",
            None,
        )

        if (
            time_series is None
            or time_series.empty
        ):
            return []

        profiles: list[
            TimeSeriesProfile
        ] = []

        for generator_name in time_series.columns:
            values = time_series[
                generator_name
            ].dropna()

            if values.empty:
                continue

            carrier = ""

            if generator_name in network.generators.index:
                carrier = str(
                    network.generators.at[
                        generator_name,
                        "carrier",
                    ]
                )

            profile_id = (
                "network:generator:"
                f"{generator_name}"
            )

            profile = TimeSeriesProfile(
                id=profile_id,
                name=(
                    f"{generator_name} availability"
                ),
                carrier=carrier,
                region=region,
                values=values,
                source=source,
                metadata={
                    "source_type": "network",
                    "generator": str(
                        generator_name
                    ),
                    "profile_kind": "p_max_pu",
                },
            )

            self.add_profile(
                profile,
                replace=replace,
            )
            profiles.append(
                profile
            )

        return profiles

    # ------------------------------------------------------------------
    # User-created and CSV profiles
    # ------------------------------------------------------------------

    def create_profile(
        self,
        *,
        name: str,
        carrier: str,
        region: str,
        values: pd.Series,
        source: str | None = None,
        metadata: dict[str, str] | None = None,
        profile_id: str | None = None,
        replace: bool = False,
    ) -> TimeSeriesProfile:
        profile_metadata = dict(
            metadata or {}
        )
        profile_metadata.setdefault(
            "source_type",
            "generated",
        )

        profile = TimeSeriesProfile(
            id=profile_id or str(
                uuid4()
            ),
            name=name,
            carrier=carrier,
            region=region,
            values=values,
            source=source,
            metadata=profile_metadata,
        )

        self.add_profile(
            profile,
            replace=replace,
        )

        return profile

    def import_csv_profile(
        self,
        file_path: str | Path,
        *,
        name: str,
        carrier: str,
        region: str,
        value_column: str,
        timestamp_column: str,
        timestamp_format: str | None = None,
        day_first: bool = False,
        timezone: str | None = None,
        profile_id: str | None = None,
        replace: bool = False,
    ) -> TimeSeriesProfile:
        frame = pd.read_csv(
            file_path
        )

        if timestamp_column not in frame.columns:
            raise ValueError(
                "Timestamp column not found: "
                f"{timestamp_column}"
            )

        if value_column not in frame.columns:
            raise ValueError(
                "Value column not found: "
                f"{value_column}"
            )

        timestamps = pd.to_datetime(
            frame[timestamp_column],
            format=timestamp_format,
            dayfirst=day_first,
            errors="raise",
        )

        if timezone:
            if timestamps.dt.tz is None:
                timestamps = (
                    timestamps.dt.tz_localize(
                        timezone
                    )
                )
            else:
                timestamps = (
                    timestamps.dt.tz_convert(
                        timezone
                    )
                )

            # Keep the timezone in profile metadata, but use UTC-naive
            # timestamps internally because PyPSA snapshots are commonly
            # represented without timezone information.
            timestamps = (
                timestamps.dt.tz_convert("UTC")
                .dt.tz_localize(None)
            )

        values = pd.to_numeric(
            frame[value_column],
            errors="coerce",
        )

        if values.isna().any():
            raise ValueError(
                "The selected CSV column contains invalid or "
                "missing values."
            )

        series = pd.Series(
            values.to_numpy(
                dtype=float
            ),
            index=pd.DatetimeIndex(
                timestamps
            ),
            name=name,
        )

        return self.create_profile(
            name=name,
            carrier=carrier,
            region=region,
            values=series,
            source=str(
                file_path
            ),
            metadata={
                "source_type": "user_import",
                "file": str(
                    file_path
                ),
                "profile_kind": "p_max_pu",
            },
            profile_id=profile_id,
            replace=replace,
        )

    # ------------------------------------------------------------------
    # External providers
    # ------------------------------------------------------------------

    def register_external_fetcher(
        self,
        provider: str,
        fetcher: ExternalProfileFetcher,
        *,
        replace: bool = False,
    ) -> None:
        provider_key = (
            provider.strip().lower()
        )

        if not provider_key:
            raise ValueError(
                "Provider name cannot be empty."
            )

        if (
            provider_key in self._external_fetchers
            and not replace
        ):
            raise ValueError(
                f'An external fetcher named "{provider}" '
                "is already registered."
            )

        self._external_fetchers[
            provider_key
        ] = fetcher

    def list_external_providers(
        self,
    ) -> list[str]:
        return sorted(
            self._external_fetchers
        )

    def fetch_external_profile(
        self,
        provider: str,
        request: Mapping[str, Any],
        *,
        add_to_library: bool = True,
        replace: bool = False,
    ) -> TimeSeriesProfile:
        provider_key = (
            provider.strip().lower()
        )

        try:
            fetcher = self._external_fetchers[
                provider_key
            ]
        except KeyError as exc:
            raise KeyError(
                f'No external profile fetcher is registered '
                f'for "{provider}".'
            ) from exc

        profile = fetcher(
            request
        )

        if not isinstance(
            profile,
            TimeSeriesProfile,
        ):
            raise TypeError(
                "External fetchers must return a "
                "TimeSeriesProfile instance."
            )

        if add_to_library:
            self.add_profile(
                profile,
                replace=replace,
            )

        return profile

    # ------------------------------------------------------------------
    # Alignment and scaling
    # ------------------------------------------------------------------

    def aligned_values(
        self,
        profile_id: str,
        snapshots: pd.Index,
    ) -> pd.Series:
        return self.get_profile(
            profile_id
        ).aligned_to(
            snapshots
        )

    def scaled_values(
        self,
        profile_id: str,
        snapshots: pd.Index,
        target_capacity_factor: float,
    ) -> pd.Series:
        profile = self.get_profile(
            profile_id
        )
        aligned = profile.aligned_to(
            snapshots
        )

        return self.scale_to_capacity_factor(
            aligned,
            target_capacity_factor,
        )

    @staticmethod
    def scale_to_capacity_factor(
        values: pd.Series,
        target_capacity_factor: float,
        *,
        tolerance: float = 1e-8,
        max_iterations: int = 200,
    ) -> pd.Series:
        """
        Find a multiplier ``a`` such that:

        ``mean(clip(a * values, 0, 1)) == target_capacity_factor``.
        """
        if not 0.0 <= target_capacity_factor <= 1.0:
            raise ValueError(
                "Target capacity factor must lie between 0 and 1."
            )

        numeric = pd.to_numeric(
            values,
            errors="coerce",
        ).astype(float)

        if numeric.empty:
            raise ValueError(
                "Cannot scale an empty profile."
            )

        if numeric.isna().any():
            raise ValueError(
                "Profile values cannot contain NaN."
            )

        if (numeric < 0.0).any():
            raise ValueError(
                "Profile values cannot be negative."
            )

        if target_capacity_factor == 0.0:
            return pd.Series(
                0.0,
                index=numeric.index,
                name=numeric.name,
                dtype=float,
            )

        positive_share = float(
            (numeric > 0.0).mean()
        )

        if (
            target_capacity_factor
            > positive_share + tolerance
        ):
            raise ValueError(
                "The requested capacity factor is infeasible for "
                "this profile because too many snapshots are zero. "
                f"Maximum achievable mean: {positive_share:.6f}."
            )

        if float(
            numeric.max()
        ) == 0.0:
            raise ValueError(
                "A zero profile cannot be scaled to a positive "
                "capacity factor."
            )

        def mean_for(
            multiplier: float,
        ) -> float:
            return float(
                numeric.mul(
                    multiplier
                )
                .clip(
                    lower=0.0,
                    upper=1.0,
                )
                .mean()
            )

        lower = 0.0
        upper = 1.0

        while (
            mean_for(upper)
            < target_capacity_factor
        ):
            upper *= 2.0

            if upper > 1e12:
                raise ValueError(
                    "Could not find a scaling factor for the "
                    "requested capacity factor."
                )

        for _ in range(
            max_iterations
        ):
            midpoint = (
                lower + upper
            ) / 2.0
            midpoint_mean = mean_for(
                midpoint
            )

            if abs(
                midpoint_mean
                - target_capacity_factor
            ) <= tolerance:
                lower = midpoint
                upper = midpoint
                break

            if (
                midpoint_mean
                < target_capacity_factor
            ):
                lower = midpoint
            else:
                upper = midpoint

        multiplier = (
            lower + upper
        ) / 2.0

        scaled = numeric.mul(
            multiplier
        ).clip(
            lower=0.0,
            upper=1.0,
        )
        scaled.name = numeric.name

        return scaled

    # ------------------------------------------------------------------
    # Application to PyPSA
    # ------------------------------------------------------------------

    def apply_profile_to_generator(
        self,
        network: pypsa.Network,
        generator_name: str,
        profile_id: str,
        *,
        target_capacity_factor: float | None = None,
        initialize_default_snapshots: bool = True,
    ) -> pd.Series:
        if generator_name not in network.generators.index:
            raise KeyError(
                "Generator not found: "
                f"{generator_name}"
            )

        profile = self.get_profile(
            profile_id
        )

        if (
            initialize_default_snapshots
            and self._has_default_placeholder_snapshots(
                network
            )
        ):
            network.set_snapshots(
                profile.values.index
            )

        if target_capacity_factor is None:
            values = profile.aligned_to(
                network.snapshots
            )
        else:
            aligned = profile.aligned_to(
                network.snapshots
            )
            values = self.scale_to_capacity_factor(
                aligned,
                target_capacity_factor,
            )

        network.generators_t.p_max_pu.loc[
            :,
            generator_name,
        ] = values

        return values

    @staticmethod
    def _has_default_placeholder_snapshots(
        network: pypsa.Network,
    ) -> bool:
        """
        Return True for a newly created PyPSA network that still uses
        the single default placeholder snapshot, usually ``"now"``.
        """
        snapshots = network.snapshots

        if len(snapshots) != 1:
            return False

        return (
            str(snapshots[0])
            .strip()
            .lower()
            == "now"
        )

