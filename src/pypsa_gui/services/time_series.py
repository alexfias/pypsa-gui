from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pypsa


@dataclass
class TimeSeriesSummary:
    snapshots: int
    series_count: int
    value_min: float | None
    value_max: float | None
    value_mean: float | None


_COMPONENT_ATTRS: dict[str, tuple[str, str]] = {
    "Generators": ("generators", "generators_t"),
    "Loads": ("loads", "loads_t"),
    "Storage Units": ("storage_units", "storage_units_t"),
    "Stores": ("stores", "stores_t"),
    "Links": ("links", "links_t"),
    "Lines": ("lines", "lines_t"),
    "Buses": ("buses", "buses_t"),
}


def get_available_component_types(network: pypsa.Network) -> list[str]:
    available: list[str] = []

    for label, (static_attr, dynamic_attr) in _COMPONENT_ATTRS.items():
        static_df = getattr(network, static_attr, None)
        dynamic_obj = getattr(network, dynamic_attr, None)

        if static_df is None or dynamic_obj is None:
            continue

        if getattr(static_df, "empty", True):
            # Buses can still be useful even if empty should not happen, but keep consistent
            continue

        fields = get_available_time_series_fields(network, label)
        if fields:
            available.append(label)

    return available


def get_available_time_series_fields(network: pypsa.Network, component_type: str) -> list[str]:
    if component_type not in _COMPONENT_ATTRS:
        return []

    _, dynamic_attr = _COMPONENT_ATTRS[component_type]
    dynamic_obj = getattr(network, dynamic_attr, None)
    if dynamic_obj is None:
        return []

    fields: list[str] = []

    # PyPSA *_t objects usually expose time-dependent DataFrames as attributes.
    for name in dir(dynamic_obj):
        if name.startswith("_"):
            continue

        try:
            value = getattr(dynamic_obj, name)
        except Exception:
            continue

        if isinstance(value, pd.DataFrame) and not value.empty:
            fields.append(name)

    return sorted(fields)


def get_component_dataframe(network: pypsa.Network, component_type: str) -> pd.DataFrame:
    if component_type not in _COMPONENT_ATTRS:
        return pd.DataFrame()

    static_attr, _ = _COMPONENT_ATTRS[component_type]
    df = getattr(network, static_attr, None)
    if df is None:
        return pd.DataFrame()

    return df


def get_time_series_dataframe(
    network: pypsa.Network,
    component_type: str,
    field: str,
) -> pd.DataFrame:
    if component_type not in _COMPONENT_ATTRS:
        return pd.DataFrame()

    _, dynamic_attr = _COMPONENT_ATTRS[component_type]
    dynamic_obj = getattr(network, dynamic_attr, None)
    if dynamic_obj is None:
        return pd.DataFrame()

    try:
        df = getattr(dynamic_obj, field)
    except Exception:
        return pd.DataFrame()

    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    return df.copy()


def get_available_carriers(network: pypsa.Network, component_type: str) -> list[str]:
    static_df = get_component_dataframe(network, component_type)
    if static_df.empty or "carrier" not in static_df.columns:
        return []

    carriers = static_df["carrier"].dropna().astype(str).sort_values().unique().tolist()
    return carriers


def get_component_names(
    network: pypsa.Network,
    component_type: str,
    carrier: str | None = None,
) -> list[str]:
    static_df = get_component_dataframe(network, component_type)
    if static_df.empty:
        return []

    df = static_df.copy()

    if carrier and carrier != "All carriers" and "carrier" in df.columns:
        df = df[df["carrier"].astype(str) == carrier]

    return df.index.astype(str).tolist()


def filter_time_series_dataframe(
    network: pypsa.Network,
    component_type: str,
    df: pd.DataFrame,
    carrier: str | None = None,
    component_names: list[str] | None = None,
) -> pd.DataFrame:
    if df.empty:
        return df

    static_df = get_component_dataframe(network, component_type)
    if static_df.empty:
        return df.iloc[:, 0:0]

    selected_columns = pd.Index(df.columns)

    if carrier and carrier != "All carriers" and "carrier" in static_df.columns:
        carrier_components = static_df.index[static_df["carrier"].astype(str) == carrier]
        selected_columns = selected_columns.intersection(carrier_components)

    if component_names:
        selected_columns = selected_columns.intersection(pd.Index(component_names))

    return df.loc[:, selected_columns]


def aggregate_time_series(
    network: pypsa.Network,
    component_type: str,
    df: pd.DataFrame,
    mode: str,
) -> pd.DataFrame:
    if df.empty:
        return df

    mode = mode.lower().strip()

    if mode == "individual":
        return df

    if mode == "sum":
        return pd.DataFrame({"sum": df.sum(axis=1)})

    if mode == "mean":
        return pd.DataFrame({"mean": df.mean(axis=1)})

    if mode == "by carrier":
        static_df = get_component_dataframe(network, component_type)
        if static_df.empty or "carrier" not in static_df.columns:
            return pd.DataFrame({"sum": df.sum(axis=1)})

        carriers = static_df.reindex(df.columns)["carrier"].fillna("unknown").astype(str)

        grouped: dict[str, pd.Series] = {}
        for carrier_name in sorted(carriers.unique()):
            cols = carriers[carriers == carrier_name].index.intersection(df.columns)
            if len(cols) == 0:
                continue
            grouped[carrier_name] = df.loc[:, cols].sum(axis=1)

        if not grouped:
            return pd.DataFrame({"sum": df.sum(axis=1)})

        return pd.DataFrame(grouped)

    return df


def build_time_series_summary(df: pd.DataFrame) -> TimeSeriesSummary:
    if df.empty:
        return TimeSeriesSummary(
            snapshots=0,
            series_count=0,
            value_min=None,
            value_max=None,
            value_mean=None,
        )

    stacked = df.stack()
    if stacked.empty:
        return TimeSeriesSummary(
            snapshots=len(df.index),
            series_count=len(df.columns),
            value_min=None,
            value_max=None,
            value_mean=None,
        )

    return TimeSeriesSummary(
        snapshots=len(df.index),
        series_count=len(df.columns),
        value_min=float(stacked.min()),
        value_max=float(stacked.max()),
        value_mean=float(stacked.mean()),
    )