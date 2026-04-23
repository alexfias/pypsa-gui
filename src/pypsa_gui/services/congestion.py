from __future__ import annotations

import numpy as np
import pandas as pd
import pypsa


def _safe_abs_df(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    return df.abs().copy()


def _get_line_capacity(network: pypsa.Network) -> pd.Series:
    if network.lines.empty:
        return pd.Series(dtype=float)

    if "s_nom_opt" in network.lines.columns:
        return network.lines["s_nom_opt"].replace(0.0, np.nan)
    return network.lines["s_nom"].replace(0.0, np.nan)


def _get_link_capacity(network: pypsa.Network) -> pd.Series:
    if network.links.empty:
        return pd.Series(dtype=float)

    if "p_nom_opt" in network.links.columns:
        return network.links["p_nom_opt"].replace(0.0, np.nan)
    return network.links["p_nom"].replace(0.0, np.nan)


def get_line_loading(network: pypsa.Network) -> pd.DataFrame:
    """
    Line loading in p.u. from |p0| / capacity.
    """
    if network.lines.empty or not hasattr(network, "lines_t"):
        return pd.DataFrame(index=network.snapshots)

    if not hasattr(network.lines_t, "p0"):
        return pd.DataFrame(index=network.snapshots, columns=network.lines.index)

    flows = _safe_abs_df(network.lines_t.p0)
    cap = _get_line_capacity(network)

    return flows.divide(cap, axis=1)


def get_link_loading(network: pypsa.Network) -> pd.DataFrame:
    """
    Link loading in p.u. from |p0| / capacity.
    """
    if network.links.empty or not hasattr(network, "links_t"):
        return pd.DataFrame(index=network.snapshots)

    if not hasattr(network.links_t, "p0"):
        return pd.DataFrame(index=network.snapshots, columns=network.links.index)

    flows = _safe_abs_df(network.links_t.p0)
    cap = _get_link_capacity(network)

    return flows.divide(cap, axis=1)


def get_combined_congestion_table(network: pypsa.Network) -> pd.DataFrame:
    """
    Summary per line/link.
    """
    records: list[dict[str, float | int | str]] = []

    line_loading = get_line_loading(network)
    if not line_loading.empty:
        for asset in line_loading.columns:
            s = line_loading[asset].dropna()
            if s.empty:
                continue
            records.append(
                {
                    "component": "Line",
                    "name": asset,
                    "mean_loading": float(s.mean()),
                    "max_loading": float(s.max()),
                    "hours_above_90": int((s > 0.9).sum()),
                    "hours_above_100": int((s > 1.0).sum()),
                }
            )

    link_loading = get_link_loading(network)
    if not link_loading.empty:
        for asset in link_loading.columns:
            s = link_loading[asset].dropna()
            if s.empty:
                continue
            records.append(
                {
                    "component": "Link",
                    "name": asset,
                    "mean_loading": float(s.mean()),
                    "max_loading": float(s.max()),
                    "hours_above_90": int((s > 0.9).sum()),
                    "hours_above_100": int((s > 1.0).sum()),
                }
            )

    if not records:
        return pd.DataFrame(
            columns=[
                "component",
                "name",
                "mean_loading",
                "max_loading",
                "hours_above_90",
                "hours_above_100",
            ]
        )

    return pd.DataFrame(records).sort_values(
        ["hours_above_100", "max_loading"], ascending=False
    ).reset_index(drop=True)


def get_congestion_summary_stats(network: pypsa.Network) -> dict[str, float | int]:
    table = get_combined_congestion_table(network)

    if table.empty:
        return {
            "n_assets": 0,
            "avg_loading": 0.0,
            "max_loading": 0.0,
            "assets_above_90": 0,
            "assets_above_100": 0,
        }

    return {
        "n_assets": int(len(table)),
        "avg_loading": float(table["mean_loading"].mean()),
        "max_loading": float(table["max_loading"].max()),
        "assets_above_90": int((table["hours_above_90"] > 0).sum()),
        "assets_above_100": int((table["hours_above_100"] > 0).sum()),
    }


def get_system_congestion_time_series(network: pypsa.Network) -> pd.DataFrame:
    line_loading = get_line_loading(network)
    link_loading = get_link_loading(network)

    frames = []
    if not line_loading.empty:
        frames.append(line_loading)
    if not link_loading.empty:
        frames.append(link_loading)

    if not frames:
        return pd.DataFrame(
            index=network.snapshots,
            data={
                "mean_loading": 0.0,
                "max_loading": 0.0,
                "assets_above_90": 0,
                "assets_above_100": 0,
            },
        )

    combined = pd.concat(frames, axis=1)

    return pd.DataFrame(
        index=combined.index,
        data={
            "mean_loading": combined.mean(axis=1).fillna(0.0),
            "max_loading": combined.max(axis=1).fillna(0.0),
            "assets_above_90": (combined > 0.9).sum(axis=1),
            "assets_above_100": (combined > 1.0).sum(axis=1),
        },
    )


def get_top_congested_assets(
    network: pypsa.Network,
    metric: str = "hours_above_100",
    top_n: int = 10,
) -> pd.DataFrame:
    table = get_combined_congestion_table(network)
    if table.empty:
        return table

    if metric not in table.columns:
        metric = "hours_above_100"

    return table.sort_values(metric, ascending=False).head(top_n).reset_index(drop=True)


def _has_bus_coordinates(network: pypsa.Network) -> bool:
    if network.buses.empty:
        return False
    return (
        "x" in network.buses.columns
        and "y" in network.buses.columns
        and network.buses["x"].notna().any()
        and network.buses["y"].notna().any()
    )


def get_branch_map_data(
    network: pypsa.Network,
    metric: str = "mean_loading",
    threshold: float = 1.0,
) -> pd.DataFrame:
    """
    Returns a DataFrame for map plotting of lines and links with columns:
    component, name, bus0, bus1, x0, y0, x1, y1, value
    """
    if not _has_bus_coordinates(network):
        return pd.DataFrame()

    metric_frames: list[pd.DataFrame] = []

    line_loading = get_line_loading(network)
    if not network.lines.empty:
        if metric == "mean_loading":
            values = line_loading.mean(axis=0) if not line_loading.empty else pd.Series(dtype=float)
        elif metric == "max_loading":
            values = line_loading.max(axis=0) if not line_loading.empty else pd.Series(dtype=float)
        elif metric == "hours_congested":
            values = (line_loading > threshold).sum(axis=0) if not line_loading.empty else pd.Series(dtype=float)
        else:
            values = line_loading.mean(axis=0) if not line_loading.empty else pd.Series(dtype=float)

        if not values.empty:
            df = network.lines[["bus0", "bus1"]].copy()
            df["component"] = "Line"
            df["name"] = df.index
            df["value"] = values.reindex(df.index).fillna(0.0)
            metric_frames.append(df)

    link_loading = get_link_loading(network)
    if not network.links.empty:
        if metric == "mean_loading":
            values = link_loading.mean(axis=0) if not link_loading.empty else pd.Series(dtype=float)
        elif metric == "max_loading":
            values = link_loading.max(axis=0) if not link_loading.empty else pd.Series(dtype=float)
        elif metric == "hours_congested":
            values = (link_loading > threshold).sum(axis=0) if not link_loading.empty else pd.Series(dtype=float)
        else:
            values = link_loading.mean(axis=0) if not link_loading.empty else pd.Series(dtype=float)

        if not values.empty:
            df = network.links[["bus0", "bus1"]].copy()
            df["component"] = "Link"
            df["name"] = df.index
            df["value"] = values.reindex(df.index).fillna(0.0)
            metric_frames.append(df)

    if not metric_frames:
        return pd.DataFrame()

    branches = pd.concat(metric_frames, axis=0).reset_index(drop=True)

    buses = network.buses[["x", "y"]].copy()
    buses.columns = ["bus_x", "bus_y"]

    branches = branches.join(buses, on="bus0")
    branches = branches.rename(columns={"bus_x": "x0", "bus_y": "y0"})
    branches = branches.join(buses, on="bus1")
    branches = branches.rename(columns={"bus_x": "x1", "bus_y": "y1"})

    branches = branches.dropna(subset=["x0", "y0", "x1", "y1"])
    return branches


def get_bus_map_data(network: pypsa.Network) -> pd.DataFrame:
    """
    Returns bus coordinates for plotting.
    """
    if not _has_bus_coordinates(network):
        return pd.DataFrame()

    return network.buses[["x", "y"]].dropna().copy()