from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass(frozen=True)
class TimeSeriesProfile:
    """Reusable generator-availability time series."""

    id: str
    name: str
    carrier: str
    region: str
    values: pd.Series
    source: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        values = pd.to_numeric(self.values.copy(), errors="coerce")

        if values.empty:
            raise ValueError("A time-series profile cannot be empty.")
        if values.isna().any():
            raise ValueError(
                "Profile values must be numeric and cannot contain NaN."
            )
        if (values < 0.0).any():
            raise ValueError("Profile values cannot be negative.")

        object.__setattr__(self, "values", values.astype(float))

    @property
    def capacity_factor(self) -> float:
        return float(self.values.mean())

    @property
    def minimum(self) -> float:
        return float(self.values.min())

    @property
    def maximum(self) -> float:
        return float(self.values.max())

    def aligned_to(self, snapshots: pd.Index) -> pd.Series:
        aligned = self.values.reindex(snapshots)

        if aligned.isna().any():
            missing_count = int(aligned.isna().sum())
            raise ValueError(
                "The profile does not cover all network snapshots. "
                f"Missing values: {missing_count}."
            )

        aligned.name = self.name
        return aligned.astype(float)

    def with_values(
        self,
        values: pd.Series,
        *,
        name: str | None = None,
        profile_id: str | None = None,
    ) -> TimeSeriesProfile:
        return TimeSeriesProfile(
            id=profile_id or self.id,
            name=name or self.name,
            carrier=self.carrier,
            region=self.region,
            values=values,
            source=self.source,
            metadata=dict(self.metadata),
        )
