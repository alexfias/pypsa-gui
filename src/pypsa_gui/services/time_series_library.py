from __future__ import annotations

from collections.abc import Iterable
from uuid import uuid4

import pandas as pd
import pypsa

from pypsa_gui.models.time_series_profile import TimeSeriesProfile


class TimeSeriesLibrary:
    """Registry and utility service for generator availability profiles."""

    def __init__(self) -> None:
        self._profiles: dict[str, TimeSeriesProfile] = {}

    def add_profile(
        self,
        profile: TimeSeriesProfile,
        *,
        replace: bool = False,
    ) -> None:
        if profile.id in self._profiles and not replace:
            raise ValueError(
                f'A profile with id "{profile.id}" already exists.'
            )
        self._profiles[profile.id] = profile

    def remove_profile(self, profile_id: str) -> None:
        self._profiles.pop(profile_id, None)

    def clear(self) -> None:
        self._profiles.clear()

    def get_profile(self, profile_id: str) -> TimeSeriesProfile:
        try:
            return self._profiles[profile_id]
        except KeyError as exc:
            raise KeyError(f'Unknown profile id: "{profile_id}".') from exc

    def list_profiles(
        self,
        carrier: str | None = None,
        region: str | None = None,
    ) -> list[TimeSeriesProfile]:
        profiles = list(self._profiles.values())

        if carrier is not None:
            key = carrier.strip().lower()
            profiles = [
                p for p in profiles if p.carrier.strip().lower() == key
            ]

        if region is not None:
            key = region.strip().lower()
            profiles = [
                p for p in profiles if p.region.strip().lower() == key
            ]

        return sorted(
            profiles,
            key=lambda p: (
                p.region.lower(),
                p.carrier.lower(),
                p.name.lower(),
            ),
        )

    def register_network_profiles(
        self,
        network: pypsa.Network,
        *,
        region: str = "network",
        source: str = "active network",
        replace: bool = True,
    ) -> list[TimeSeriesProfile]:
        frame = getattr(network.generators_t, "p_max_pu", None)

        if frame is None or frame.empty:
            return []

        profiles: list[TimeSeriesProfile] = []

        for generator_name in frame.columns:
            values = frame[generator_name].dropna()
            if values.empty:
                continue

            carrier = ""
            if generator_name in network.generators.index:
                carrier = str(
                    network.generators.at[generator_name, "carrier"]
                )

            profile = TimeSeriesProfile(
                id=f"network:generator:{generator_name}",
                name=f"{generator_name} availability",
                carrier=carrier,
                region=region,
                values=values,
                source=source,
                metadata={
                    "generator": str(generator_name),
                    "kind": "p_max_pu",
                },
            )
            self.add_profile(profile, replace=replace)
            profiles.append(profile)

        return profiles

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
        profile = TimeSeriesProfile(
            id=profile_id or str(uuid4()),
            name=name,
            carrier=carrier,
            region=region,
            values=values,
            source=source,
            metadata=metadata or {},
        )
        self.add_profile(profile, replace=replace)
        return profile

    def import_csv_profile(
        self,
        file_path: str,
        *,
        name: str,
        carrier: str,
        region: str,
        value_column: str | None = None,
        timestamp_column: str | None = None,
        profile_id: str | None = None,
    ) -> TimeSeriesProfile:
        frame = pd.read_csv(file_path)

        if timestamp_column is not None:
            if timestamp_column not in frame.columns:
                raise ValueError(
                    f"Timestamp column not found: {timestamp_column}"
                )
            frame[timestamp_column] = pd.to_datetime(
                frame[timestamp_column]
            )
            frame = frame.set_index(timestamp_column)

        candidate_columns = [
            c for c in frame.columns if c != timestamp_column
        ]

        if value_column is None:
            if not candidate_columns:
                raise ValueError(
                    "The CSV file contains no profile value column."
                )
            value_column = candidate_columns[0]

        if value_column not in frame.columns:
            raise ValueError(f"Value column not found: {value_column}")

        values = pd.to_numeric(frame[value_column], errors="coerce")
        if values.isna().any():
            raise ValueError(
                "The selected CSV column contains non-numeric or missing values."
            )

        return self.create_profile(
            name=name,
            carrier=carrier,
            region=region,
            values=values,
            source=file_path,
            profile_id=profile_id,
        )

    def aligned_values(
        self,
        profile_id: str,
        snapshots: pd.Index,
    ) -> pd.Series:
        return self.get_profile(profile_id).aligned_to(snapshots)

    def scaled_values(
        self,
        profile_id: str,
        snapshots: pd.Index,
        target_capacity_factor: float,
    ) -> pd.Series:
        profile = self.get_profile(profile_id)
        aligned = profile.aligned_to(snapshots)
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
        if not 0.0 <= target_capacity_factor <= 1.0:
            raise ValueError(
                "Target capacity factor must lie between 0 and 1."
            )

        numeric = pd.to_numeric(values, errors="coerce").astype(float)

        if numeric.empty:
            raise ValueError("Cannot scale an empty profile.")
        if numeric.isna().any():
            raise ValueError("Profile values cannot contain NaN.")
        if (numeric < 0.0).any():
            raise ValueError("Profile values cannot be negative.")

        if target_capacity_factor == 0.0:
            return pd.Series(
                0.0,
                index=numeric.index,
                name=numeric.name,
                dtype=float,
            )

        positive_share = float((numeric > 0.0).mean())
        if target_capacity_factor > positive_share + tolerance:
            raise ValueError(
                "The requested capacity factor is infeasible for this "
                "profile because too many snapshots are zero. "
                f"Maximum achievable mean: {positive_share:.6f}."
            )

        if float(numeric.max()) == 0.0:
            raise ValueError(
                "A zero profile cannot be scaled to a positive capacity factor."
            )

        def mean_for(multiplier: float) -> float:
            return float(
                numeric.mul(multiplier)
                .clip(lower=0.0, upper=1.0)
                .mean()
            )

        lower = 0.0
        upper = 1.0

        while mean_for(upper) < target_capacity_factor:
            upper *= 2.0
            if upper > 1e12:
                raise ValueError(
                    "Could not find a scaling factor for the requested capacity factor."
                )

        for _ in range(max_iterations):
            midpoint = (lower + upper) / 2.0
            midpoint_mean = mean_for(midpoint)

            if abs(midpoint_mean - target_capacity_factor) <= tolerance:
                lower = midpoint
                upper = midpoint
                break

            if midpoint_mean < target_capacity_factor:
                lower = midpoint
            else:
                upper = midpoint

        multiplier = (lower + upper) / 2.0
        scaled = numeric.mul(multiplier).clip(lower=0.0, upper=1.0)
        scaled.name = numeric.name
        return scaled

    def apply_profile_to_generator(
        self,
        network: pypsa.Network,
        generator_name: str,
        profile_id: str,
        *,
        target_capacity_factor: float | None = None,
    ) -> pd.Series:
        if generator_name not in network.generators.index:
            raise KeyError(f"Generator not found: {generator_name}")

        if target_capacity_factor is None:
            values = self.aligned_values(
                profile_id,
                network.snapshots,
            )
        else:
            values = self.scaled_values(
                profile_id,
                network.snapshots,
                target_capacity_factor,
            )

        network.generators_t.p_max_pu.loc[:, generator_name] = values
        return values

    def register_profiles(
        self,
        profiles: Iterable[TimeSeriesProfile],
        *,
        replace: bool = False,
    ) -> None:
        for profile in profiles:
            self.add_profile(profile, replace=replace)
