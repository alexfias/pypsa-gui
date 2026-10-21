"""Import balanced, static pandapower exports without importing pandapower.

Only plain tables/scalars are decoded; serialized Python objects are never
instantiated. This also keeps pandapower's pandas dependency out of the GUI.
Electrical units follow the pandapower line/trafo and PyPSA component docs:
https://pandapower.readthedocs.io/en/stable/elements/line.html
https://pandapower.readthedocs.io/en/stable/elements/trafo.html
https://docs.pypsa.org/latest/user-guide/components/transformers/
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd
import pypsa
import networkx as nx

IMPORT_META_KEY = "pypsa_gui_pandapower_import"
SUPPORTED = {
    "bus",
    "load",
    "gen",
    "sgen",
    "ext_grid",
    "line",
    "trafo",
    "shunt",
    "switch",
}
INFORMATION = {
    "bus_geodata",
    "line_geodata",
    "measurement",
    "group",
    "dtypes",
    "parameters",
    "user_pf_options",
    "poly_cost",
    "pwl_cost",
}


@dataclass(frozen=True)
class PandapowerImportResult:
    network: pypsa.Network
    notes: tuple[str, ...]

    def summary(self) -> str:
        n = self.network
        return (
            f"Imported {len(n.buses)} buses, {len(n.lines)} lines, "
            f"{len(n.transformers)} transformers, {len(n.generators)} generators "
            f"and {len(n.loads)} loads.\n\n" + "\n\n".join(self.notes)
        )


def _read_export(path: Path) -> dict:
    if path.suffix.lower() == ".json":
        with path.open(encoding="utf-8-sig") as stream:
            document = json.load(stream)
        if not isinstance(document, dict) or document.get("_class") != "pandapowerNet":
            raise ValueError(
                "Select a network exported with pandapower.to_json(net, path)."
            )
        raw = document.get("_object")
        if isinstance(raw, str):
            raw = json.loads(raw)
        if not isinstance(raw, dict):
            raise ValueError("The pandapower JSON network object is malformed.")
        data = {}
        for key, value in raw.items():
            if isinstance(value, dict) and value.get("_class") == "DataFrame":
                if (
                    value.get("orient", "split") != "split"
                    or value.get("is_multiindex")
                    or value.get("is_multicolumn")
                ):
                    raise ValueError(f"Unsupported table layout in {key}.")
                payload = value.get("_object")
                payload = json.loads(payload) if isinstance(payload, str) else payload
                if (
                    not isinstance(payload, dict)
                    or not {"data", "columns", "index"} <= payload.keys()
                ):
                    raise ValueError(f"Malformed pandapower table: {key}.")
                data[key] = pd.DataFrame(
                    payload["data"], columns=payload["columns"], index=payload["index"]
                )
            else:
                data[key] = value
    elif path.suffix.lower() == ".xlsx":
        try:
            data = pd.read_excel(path, sheet_name=None, index_col=0, engine="openpyxl")
        except ImportError as exc:
            raise ImportError(
                'Excel import needs openpyxl. Install it with: python -m pip install -e ".[pandapower]"'
            ) from exc
        parameters = data.pop("parameters", pd.DataFrame())
        if len(parameters) != 1 or "f_hz" not in parameters:
            raise ValueError(
                "Select a workbook exported with pandapower.to_excel(net, path)."
            )
        data.update(parameters.iloc[0].to_dict())
    else:
        raise ValueError(
            "Select a pandapower .json or .xlsx export. Export other formats with pandapower.to_json first."
        )
    version = str(data.get("format_version", data.get("version", "")))
    if version.split(".")[0] not in {"2", "3"}:
        raise ValueError(
            "Only pandapower 2.x/3.x exports are supported. Re-export older networks with a current pandapower version."
        )
    return data


def load_network_from_pandapower(path: str | Path) -> PandapowerImportResult:
    """Read a JSON/Excel export into a fresh, unsolved PyPSA network."""
    path = Path(path)
    result = convert_pandapower_network(_read_export(path))
    result.network.meta[IMPORT_META_KEY]["source_path"] = str(path)
    return result


def _number(row, key, default=None, *, minimum=None, positive=False) -> float:
    value = row.get(key, default)
    if value is None or (np.isscalar(value) and pd.isna(value)):
        value = default
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a finite number.") from exc
    if (
        not math.isfinite(value)
        or (positive and value <= 0)
        or (minimum is not None and value < minimum)
    ):
        raise ValueError(f"Invalid {key}: {value}.")
    return value


def _flag(row, key, default=True) -> bool:
    value = row.get(key, default)
    if value is None or (np.isscalar(value) and pd.isna(value)):
        return default
    if value in (True, 1, "True", "true"):
        return True
    if value in (False, 0, "False", "false"):
        return False
    raise ValueError(f"Invalid boolean {key}: {value!r}.")


def _table(data, key) -> pd.DataFrame:
    value = data.get(key)
    if value is None:
        return pd.DataFrame()
    if not isinstance(value, pd.DataFrame):
        raise ValueError(f"{key} is not a plain pandapower table.")
    if not value.index.is_unique or not value.columns.is_unique:
        raise ValueError(f"{key} contains duplicate indices or columns.")
    for index in value.index:
        if not isinstance(index, (int, np.integer)) or index < 0:
            raise ValueError(f"{key} must have non-negative integer indices.")
    return value


def _active(frame) -> pd.DataFrame:
    if frame.empty:
        return frame
    return frame.loc[[i for i, row in frame.iterrows() if _flag(row, "in_service")]]


def _origin(table, index, row) -> dict:
    label = row.get("name")
    return {
        "pandapower_table": table,
        "pandapower_index": str(index),
        "pandapower_name": "" if label is None or pd.isna(label) else str(label),
    }


def _coordinates(data, index, row):
    geo = row.get("geo")
    if isinstance(geo, str) and geo:
        try:
            # Excel encodes the GeoJSON string a second time.
            for _ in range(2):
                if isinstance(geo, str):
                    geo = json.loads(geo)
            if geo is not None and geo.get("type") == "Point":
                x, y = geo["coordinates"][:2]
                if math.isfinite(float(x)) and math.isfinite(float(y)):
                    return float(x), float(y)
        except (ValueError, TypeError, AttributeError, KeyError):
            pass
    legacy = data.get("bus_geodata")
    if isinstance(legacy, pd.DataFrame) and index in legacy.index:
        return _number(legacy.loc[index], "x"), _number(legacy.loc[index], "y")
    return 0.0, 0.0


def convert_pandapower_network(data: Mapping) -> PandapowerImportResult:
    """Convert a pandapowerNet or decoded export; never mutate the source.

    This is a balanced static model, not a pandapower OPF/time-series replay.
    Unknown active equipment and unsupported electrical models fail explicitly.
    """
    if not isinstance(data, Mapping):
        raise ValueError("Expected a pandapower network mapping.")
    notes = [
        "Converted one balanced, static operating point. Pandapower results, controllers, time-series profiles and OPF costs are not imported. Review generator bounds and costs before optimisation.",
        "Generator p_set preserves source dispatch and fixes it during optimisation in recent PyPSA versions. Set p_set to NaN for generators you want to redispatch. Slack p_set is left unset. Generator p_nom is a normalisation base; review installed MW capacities before capacity analysis.",
        "Reactive-power limits and unbalanced/short-circuit calculations are not represented by PyPSA's linear optimisation. Slack voltage angles are referenced to zero. The GUI power-flow action remains a placeholder.",
    ]
    for key, value in data.items():
        if (
            key.startswith(("_", "res_"))
            or key in SUPPORTED | INFORMATION
            or key.endswith("_std_types")
        ):
            continue
        if isinstance(value, pd.DataFrame) and not _active(value).empty:
            raise ValueError(
                f"Unsupported active pandapower table: {key}. Remove or convert it before importing."
            )
        if key == "profiles" and isinstance(value, dict) and value:
            raise ValueError(
                "Time-series profiles are not supported. Export a static network without profiles/controllers."
            )
    if any(not _table(data, key).empty for key in ("poly_cost", "pwl_cost")):
        notes.append(
            "The source contains OPF cost tables. These costs were not converted; configure PyPSA costs explicitly before solving."
        )
    tables = {key: _table(data, key) for key in SUPPORTED}
    active = {key: _active(value) for key, value in tables.items()}
    buses = active["bus"]
    if buses.empty:
        raise ValueError("The network contains no in-service AC buses.")
    if "vn_kv" not in buses:
        raise ValueError(
            "Missing bus.vn_kv; old kW-based exports must be re-exported with a current pandapower version."
        )
    frequency = _number(data, "f_hz", 50, positive=True)
    parent = {i: i for i in buses.index}

    def root(i):
        while parent[i] != i:
            i = parent[i]
        return i

    def require_bus(i):
        if i not in tables["bus"].index:
            raise ValueError(f"Reference to missing pandapower bus {i}.")
        return i in parent

    disconnected = {"line": set(), "trafo": set()}
    for index, row in active["switch"].iterrows():
        bus, element, kind = row.get("bus"), row.get("element"), row.get("et")
        live = require_bus(bus)
        closed = _flag(row, "closed")
        if kind == "b":
            other_live = require_bus(element)
            if not (live and other_live and closed):
                continue
            if _number(row, "z_ohm", 0) != 0:
                raise ValueError(
                    f"Switch {index}: non-zero bus-switch impedance is unsupported."
                )
            if not np.isclose(
                _number(buses.loc[bus], "vn_kv", positive=True),
                _number(buses.loc[element], "vn_kv", positive=True),
            ):
                raise ValueError(
                    f"Switch {index}: cannot fuse buses with different nominal voltages."
                )
            a, b = root(bus), root(element)
            parent[max(a, b)] = min(a, b)
        elif kind in {"l", "t"}:
            table, ports = (
                ("line", ("from_bus", "to_bus"))
                if kind == "l"
                else ("trafo", ("hv_bus", "lv_bus"))
            )
            if (
                element not in tables[table].index
                or bus not in tables[table].loc[element, list(ports)].values
            ):
                raise ValueError(f"Switch {index}: invalid {table} terminal reference.")
            if not closed:
                disconnected[table].add(element)
        else:
            raise ValueError(f"Switch {index}: unsupported element type {kind!r}.")

    n = pypsa.Network()
    n.name = str(data.get("name") or "Imported pandapower network")
    n.add("Carrier", "AC")
    bus_map = {i: f"bus {root(i)}" for i in buses.index}
    bus_records = []
    for index, row in buses.iterrows():
        if root(index) != index:
            continue
        x, y = _coordinates(data, index, row)
        bus_records.append(
            dict(
                name=bus_map[index],
                v_nom=_number(row, "vn_kv", positive=True),
                carrier="AC",
                x=x,
                y=y,
                **_origin("bus", index, row),
            )
        )
    frame = pd.DataFrame(bus_records).set_index("name")
    n.add("Bus", frame.index, **frame)
    if len(n.buses) != len(buses):
        notes.append(
            f"Fused {len(buses) - len(n.buses)} buses through closed ideal bus-bus switches. Original bus-to-bus mapping is saved in network metadata."
        )
    if any(disconnected.values()):
        notes.append(
            "Open line/transformer switches omit the entire disconnected branch, including its charging/magnetising admittance; this is an approximation for single-ended open branches."
        )
    omitted = {}

    def connected(table, index, row, ports):
        states = [require_bus(row.get(port)) for port in ports]
        keep = all(states) and index not in disconnected.get(table, set())
        if not keep:
            omitted[table] = omitted.get(table, 0) + 1
        return keep

    records = {}

    def add(component, name, **attributes):
        records.setdefault(component, []).append({"name": name, **attributes})

    voltage_setpoints = {}
    for table in ("load", "gen", "sgen", "ext_grid", "shunt"):
        for index, row in active[table].iterrows():
            if not connected(table, index, row, ("bus",)):
                continue
            name, bus = f"{table} {index}", bus_map[row["bus"]]
            origin = _origin(table, index, row)
            if table == "shunt":
                if _flag(row, "step_dependency_table", False):
                    raise ValueError(
                        f"{name}: shunt characteristic tables are unsupported."
                    )
                v = _number(row, "vn_kv", n.buses.at[bus, "v_nom"], positive=True)
                step = _number(row, "step", 1, minimum=0)
                add(
                    "ShuntImpedance",
                    name,
                    bus=bus,
                    g=_number(row, "p_mw") * step / v**2,
                    b=-_number(row, "q_mvar") * step / v**2,
                    **origin,
                )
                continue
            scale = _number(row, "scaling", 1, minimum=0)
            p = _number(row, "p_mw", 0 if table == "ext_grid" else None) * scale
            q = _number(row, "q_mvar", 0) * scale
            if table == "load":
                if _flag(row, "controllable", False):
                    raise ValueError(f"{name}: controllable loads are unsupported.")
                if any(
                    _number(row, key, 0) != 0
                    for key in row.index
                    if key.startswith(("const_z", "const_i"))
                ):
                    raise ValueError(
                        f"{name}: voltage-dependent ZIP loads are unsupported."
                    )
                add("Load", name, bus=bus, p_set=p, q_set=q, **origin)
                continue
            control = "PQ" if table == "sgen" else "PV"
            if table == "ext_grid" or _flag(row, "slack", False):
                control = "Slack"
            if control != "PQ":
                vm = _number(row, "vm_pu", 1, positive=True)
                if bus in voltage_setpoints and not np.isclose(
                    voltage_setpoints[bus], vm
                ):
                    raise ValueError(
                        f"Conflicting voltage setpoints at {bus} (including fused buses)."
                    )
                voltage_setpoints[bus] = vm
                n.buses.at[bus, "v_mag_pu_set"] = vm
            # ext_grid.controllable concerns OPF voltage/bound enforcement;
            # it never fixes the slack's active power to the zero placeholder.
            controllable = table == "ext_grid" or _flag(
                row, "controllable", table != "sgen"
            )
            lower = _bound(row, "min_p_mw", -math.inf if table == "ext_grid" else 0)
            upper = _bound(row, "max_p_mw", math.inf)
            if not controllable:
                lower = upper = p
            if lower > upper:
                raise ValueError(f"{name}: min_p_mw exceeds max_p_mw.")
            rating = max(
                [1.0, abs(p), _number(row, "sn_mva", 0, minimum=0)]
                + [abs(v) for v in (lower, upper) if math.isfinite(v)]
            )
            add(
                "Generator",
                name,
                bus=bus,
                carrier="AC",
                control=control,
                p_set=math.nan if control == "Slack" else p,
                q_set=q,
                p_nom=rating,
                p_min_pu=lower / rating,
                p_max_pu=upper / rating,
                **origin,
            )

    for index, row in active["line"].iterrows():
        if not connected("line", index, row, ("from_bus", "to_bus")):
            continue
        bus0, bus1 = bus_map[row["from_bus"]], bus_map[row["to_bus"]]
        if bus0 == bus1:
            raise ValueError(
                f"line {index}: both terminals become the same bus after switch fusion."
            )
        voltage = n.buses.at[bus0, "v_nom"]
        if not np.isclose(voltage, n.buses.at[bus1, "v_nom"]):
            raise ValueError(
                f"line {index}: nominal terminal voltages differ; use a transformer."
            )
        length = _number(row, "length_km", positive=True)
        parallel = _number(row, "parallel", 1, positive=True)
        r = _number(row, "r_ohm_per_km", minimum=0) * length / parallel
        x = _number(row, "x_ohm_per_km") * length / parallel
        if r == x == 0:
            raise ValueError(
                f"line {index}: zero impedance is unsupported; use an ideal bus switch."
            )
        add(
            "Line",
            f"line {index}",
            bus0=bus0,
            bus1=bus1,
            length=length,
            r=r,
            x=x,
            b=2
            * math.pi
            * frequency
            * _number(row, "c_nf_per_km", 0, minimum=0)
            * 1e-9
            * length
            * parallel,
            g=_number(row, "g_us_per_km", 0, minimum=0) * 1e-6 * length * parallel,
            s_nom=math.sqrt(3)
            * voltage
            * _number(row, "max_i_ka", positive=True)
            * parallel,
            s_max_pu=_number(row, "df", 1, positive=True)
            * _number(row, "max_loading_percent", 100, minimum=0)
            / 100,
            **_origin("line", index, row),
        )

    for index, row in active["trafo"].iterrows():
        if not connected("trafo", index, row, ("hv_bus", "lv_bus")):
            continue
        _add_transformer(n, index, row, bus_map, add)

    for component, rows in records.items():
        frame = pd.DataFrame(rows).set_index("name")
        n.add(component, frame.index, **frame)
    topology = nx.Graph()
    topology.add_nodes_from(n.buses.index)
    for branches in (n.lines, n.transformers):
        topology.add_edges_from(zip(branches.bus0, branches.bus1))
    for island in nx.connected_components(topology):
        slacks = n.generators[
            (n.generators.control == "Slack") & n.generators.bus.isin(island)
        ]
        if len(slacks) > 1:
            raise ValueError(
                "Multiple slack generators/external grids in one connected island are unsupported. Select one slack source per island before importing."
            )

    inactive = sum(len(tables[key]) - len(active[key]) for key in SUPPORTED)
    if inactive or omitted:
        notes.append(
            f"Excluded {inactive} out-of-service elements and {sum(omitted.values())} elements disconnected by bus status or open switches."
        )
    if len(n.generators) and (
        np.isinf(n.generators.p_max_pu).any() or np.isinf(n.generators.p_min_pu).any()
    ):
        notes.append(
            "Some dispatch bounds were absent and remain unlimited. p_nom is a normalisation base, not an inferred installed capacity; set physical capacities and bounds before capacity analysis or optimisation."
        )
    notes.append(
        "Bus coordinates are copied without reprojection; use a schematic layout for non-geographical coordinates. Original names are retained in pandapower_name columns."
    )
    n.meta[IMPORT_META_KEY] = {
        "version": 1,
        "source_format": "pandapower",
        "pandapower_version": str(data.get("version", "unknown")),
        "bus_mapping": {str(i): name for i, name in bus_map.items()},
        "bus_labels": {
            str(i): _origin("bus", i, row)["pandapower_name"]
            for i, row in buses.iterrows()
        },
        "notes": notes,
    }
    return PandapowerImportResult(n, tuple(notes))


def _bound(row, key, default):
    value = row.get(key)
    if value is None or pd.isna(value):
        return default
    value = float(value)
    if (
        math.isnan(value)
        or (key == "min_p_mw" and value == math.inf)
        or (key == "max_p_mw" and value == -math.inf)
    ):
        raise ValueError(f"Invalid generator bound {key}.")
    return value


def _add_transformer(n, index, row, bus_map, add):
    name = f"trafo {index}"
    bus0, bus1 = bus_map[row["hv_bus"]], bus_map[row["lv_bus"]]
    if bus0 == bus1:
        raise ValueError(f"{name}: both terminals become the same bus.")
    for column, bus in (("vn_hv_kv", bus0), ("vn_lv_kv", bus1)):
        if not np.isclose(
            _number(row, column, positive=True), n.buses.at[bus, "v_nom"]
        ):
            raise ValueError(
                f"{name}: transformer rated voltages must match its buses."
            )
    if _flag(row, "tap_dependency_table", False) or _flag(
        row, "tap_phase_shifter", False
    ):
        raise ValueError(
            f"{name}: characteristic/phase-shifting tap changers are unsupported."
        )
    for key in ("leakage_resistance_ratio_hv", "leakage_reactance_ratio_hv"):
        if not np.isclose(_number(row, key, 0.5), 0.5):
            raise ValueError(
                f"{name}: asymmetric transformer leakage impedances are unsupported."
            )
    if pd.notna(row.get("tap2_pos")):
        raise ValueError(f"{name}: a second tap changer is unsupported.")
    tap_type = row.get("tap_changer_type")
    if pd.notna(tap_type) and tap_type not in ("", "Ratio"):
        raise ValueError(f"{name}: unsupported tap changer type {tap_type!r}.")
    position = _number(row, "tap_pos", _number(row, "tap_neutral", 0))
    neutral = _number(row, "tap_neutral", 0)
    if _number(row, "tap_step_degree", 0) != 0:
        raise ValueError(f"{name}: angled tap steps are unsupported.")
    tap = 1 + (position - neutral) * _number(row, "tap_step_percent", 0) / 100
    side = row.get("tap_side")
    if tap <= 0 or (tap != 1 and side not in ("hv", "lv")):
        raise ValueError(f"{name}: invalid tap ratio or side.")
    rating = _number(row, "sn_mva", positive=True)
    parallel = _number(row, "parallel", 1, positive=True)
    r = _number(row, "vkr_percent", minimum=0) / 100
    z = _number(row, "vk_percent", positive=True) / 100
    y = _number(row, "i0_percent", 0, minimum=0) / 100
    g = _number(row, "pfe_kw", 0, minimum=0) / (1000 * rating)
    if z < r or y + 1e-12 < g:
        raise ValueError(f"{name}: inconsistent short-circuit or no-load parameters.")
    # Per unit on the combined parallel rating; PyPSA converts to its 1 MVA base.
    add(
        "Transformer",
        name,
        bus0=bus0,
        bus1=bus1,
        model="t",
        s_nom=rating * parallel,
        r=r,
        x=math.sqrt(max(0, z * z - r * r)),
        g=g,
        b=-math.sqrt(max(0, y * y - g * g)),
        tap_ratio=tap,
        tap_side=1 if side == "lv" else 0,
        phase_shift=_number(row, "shift_degree", 0),
        s_max_pu=_number(row, "df", 1, positive=True)
        * _number(row, "max_loading_percent", 100, minimum=0)
        / 100,
        **_origin("trafo", index, row),
    )
