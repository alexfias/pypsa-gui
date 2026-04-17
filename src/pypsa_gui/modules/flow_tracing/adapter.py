# src/pypsa_gui/modules/flow_tracing/adapter.py
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pypsa


@dataclass
class FlowTracingInputs:
    snapshots: pd.Index
    bus_names: list[str]
    link_names: list[str]
    incidence: np.ndarray          # shape: (N, L)
    link_flows: np.ndarray         # shape: (T, L), using links_t.p0
    loads: np.ndarray              # shape: (T, N)
    injections: np.ndarray         # shape: (T, N)
    capacities: np.ndarray         # shape: (L,)

    @property
    def n_snapshots(self) -> int:
        return len(self.snapshots)

    @property
    def n_buses(self) -> int:
        return len(self.bus_names)

    @property
    def n_links(self) -> int:
        return len(self.link_names)


class FlowTracingAdapterError(ValueError):
    pass


def extract_flow_tracing_inputs(network: pypsa.Network) -> FlowTracingInputs:
    _validate_network_for_flow_tracing(network)

    snapshots = network.snapshots
    bus_names = network.buses.index.tolist()
    link_names = network.links.index.tolist()

    bus_indexer = {name: i for i, name in enumerate(bus_names)}
    link_indexer = {name: i for i, name in enumerate(link_names)}

    incidence = _build_link_incidence_matrix(network, bus_indexer, link_indexer)
    link_flows = _extract_link_flows(network, link_names)
    loads = _extract_nodal_loads(network, snapshots, bus_names)
    injections = _extract_nodal_injections(network, snapshots, bus_names, loads)
    capacities = _extract_link_capacities(network, link_names)

    _validate_dimensions(
        snapshots=snapshots,
        bus_names=bus_names,
        link_names=link_names,
        incidence=incidence,
        link_flows=link_flows,
        loads=loads,
        injections=injections,
        capacities=capacities,
    )

    return FlowTracingInputs(
        snapshots=snapshots,
        bus_names=bus_names,
        link_names=link_names,
        incidence=incidence,
        link_flows=link_flows,
        loads=loads,
        injections=injections,
        capacities=capacities,
    )


def _validate_network_for_flow_tracing(network: pypsa.Network) -> None:
    if network is None:
        raise FlowTracingAdapterError("No network was provided.")

    if network.buses.empty:
        raise FlowTracingAdapterError("The network has no buses.")

    if network.links.empty:
        raise FlowTracingAdapterError(
            "The current flow-tracing adapter supports links, "
            "but the network has no links."
        )

    if len(network.snapshots) == 0:
        raise FlowTracingAdapterError("The network has no snapshots.")

    if not hasattr(network, "links_t") or not hasattr(network.links_t, "p0"):
        raise FlowTracingAdapterError(
            "Link flow results are not available. Run power flow or optimisation first."
        )

    if network.links_t.p0.empty:
        raise FlowTracingAdapterError(
            "Link flow results are empty. Run power flow or optimisation first."
        )

    missing_flows = [
        link for link in network.links.index
        if link not in network.links_t.p0.columns
    ]
    if missing_flows:
        raise FlowTracingAdapterError(
            "Link flow results are incomplete for some links."
        )


def _build_link_incidence_matrix(
    network: pypsa.Network,
    bus_indexer: dict[str, int],
    link_indexer: dict[str, int],
) -> np.ndarray:
    """
    Build directed incidence matrix K with shape (N, L).

    Convention:
    - K[bus0, l] = -1
    - K[bus1, l] = +1

    Positive links_t.p0 means flow from bus0 -> bus1.
    """
    n_buses = len(bus_indexer)
    n_links = len(link_indexer)

    incidence = np.zeros((n_buses, n_links), dtype=float)

    for link_name, link in network.links.iterrows():
        j = link_indexer[link_name]
        i0 = bus_indexer[link.bus0]
        i1 = bus_indexer[link.bus1]

        incidence[i0, j] = -1.0
        incidence[i1, j] = 1.0

    return incidence


def _extract_link_flows(network: pypsa.Network, link_names: list[str]) -> np.ndarray:
    return (
        network.links_t.p0.reindex(columns=link_names)
        .fillna(0.0)
        .to_numpy(dtype=float)
    )


def _extract_link_capacities(network: pypsa.Network, link_names: list[str]) -> np.ndarray:
    return (
        network.links.reindex(link_names)["p_nom_opt"]
        .fillna(network.links.reindex(link_names)["p_nom"])
        .fillna(0.0)
        .to_numpy(dtype=float)
    )


def _extract_nodal_loads(
    network: pypsa.Network,
    snapshots: pd.Index,
    bus_names: list[str],
) -> np.ndarray:
    loads_df = pd.DataFrame(0.0, index=snapshots, columns=bus_names)

    if network.loads.empty:
        return loads_df.to_numpy(dtype=float)

    p_set = (
        network.loads_t.p_set
        .reindex(index=snapshots, columns=network.loads.index)
        .fillna(0.0)
    )

    for load_name, load in network.loads.iterrows():
        bus = load.bus
        if bus in loads_df.columns:
            loads_df[bus] += p_set[load_name]

    return loads_df.to_numpy(dtype=float)


def _extract_nodal_injections(
    network: pypsa.Network,
    snapshots: pd.Index,
    bus_names: list[str],
    loads: np.ndarray,
) -> np.ndarray:
    injection_df = pd.DataFrame(0.0, index=snapshots, columns=bus_names)

    if not network.generators.empty and hasattr(network.generators_t, "p"):
        gen_p = (
            network.generators_t.p
            .reindex(index=snapshots, columns=network.generators.index)
            .fillna(0.0)
        )
        for gen_name, gen in network.generators.iterrows():
            bus = gen.bus
            if bus in injection_df.columns:
                injection_df[bus] += gen_p[gen_name]

    if not network.storage_units.empty and hasattr(network.storage_units_t, "p"):
        su_p = (
            network.storage_units_t.p
            .reindex(index=snapshots, columns=network.storage_units.index)
            .fillna(0.0)
        )
        for su_name, su in network.storage_units.iterrows():
            bus = su.bus
            if bus in injection_df.columns:
                injection_df[bus] += su_p[su_name]

    if not network.stores.empty and hasattr(network.stores_t, "p"):
        store_p = (
            network.stores_t.p
            .reindex(index=snapshots, columns=network.stores.index)
            .fillna(0.0)
        )
        for store_name, store in network.stores.iterrows():
            bus = store.bus
            if bus in injection_df.columns:
                injection_df[bus] += store_p[store_name]

    injection_df -= pd.DataFrame(loads, index=snapshots, columns=bus_names)

    return injection_df.to_numpy(dtype=float)


def _validate_dimensions(
    snapshots: pd.Index,
    bus_names: list[str],
    link_names: list[str],
    incidence: np.ndarray,
    link_flows: np.ndarray,
    loads: np.ndarray,
    injections: np.ndarray,
    capacities: np.ndarray,
) -> None:
    t = len(snapshots)
    n = len(bus_names)
    l = len(link_names)

    expected_shapes = {
        "incidence": (n, l),
        "link_flows": (t, l),
        "loads": (t, n),
        "injections": (t, n),
        "capacities": (l,),
    }

    actual_shapes = {
        "incidence": incidence.shape,
        "link_flows": link_flows.shape,
        "loads": loads.shape,
        "injections": injections.shape,
        "capacities": capacities.shape,
    }

    for name, expected in expected_shapes.items():
        actual = actual_shapes[name]
        if actual != expected:
            raise FlowTracingAdapterError(
                f"Invalid shape for {name}: expected {expected}, got {actual}."
            )