"""Import invariants and comparison with independent pandapower AC results."""

import builtins
from copy import deepcopy
import json
import math
import os
from pathlib import Path
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pandas as pd
import pypsa
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from pypsa_gui.models.session_view import SessionViewOptions
from pypsa_gui.models.solver_settings import SolverSettings
from pypsa_gui.services.network_io import save_network_to_netcdf
from pypsa_gui.services.optimisation import run_network_optimisation
from pypsa_gui.services.pandapower_import import (
    IMPORT_META_KEY,
    _read_export,
    convert_pandapower_network,
    load_network_from_pandapower,
)
from pypsa_gui.ui.main_window import MainWindow

DATA = Path(__file__).parent / "data"


@pytest.fixture(autouse=True)
def offline():
    with pypsa.option_context("general.allow_network_requests", False):
        yield


@pytest.fixture
def source():
    return _read_export(DATA / "pandapower_balanced.json")


@pytest.mark.parametrize("suffix", ["json", "xlsx"])
@pytest.mark.parametrize("side", ["hv", "lv"])
def test_ac_power_flow_matches_pandapower(suffix, side):
    if suffix == "xlsx":
        pytest.importorskip("openpyxl")
    data = _read_export(DATA / f"pandapower_balanced.{suffix}")
    data["trafo"].loc[0, "tap_side"] = side
    n = convert_pandapower_network(data).network
    reference = json.loads((DATA / "pandapower_expected.json").read_text())["cases"][
        side
    ]
    assert n.generators_t.p.empty  # Source result tables are deliberately ignored.
    assert n.pf(x_tol=1e-8)["converged"].all().all()
    for bus in n.buses.index:
        expected = reference["res_bus"][bus.split()[1]]
        assert n.buses_t.v_mag_pu.at["now", bus] == pytest.approx(
            expected["vm_pu"], abs=1e-8
        )
        assert np.rad2deg(n.buses_t.v_ang.at["now", bus]) == pytest.approx(
            expected["va_degree"], abs=1e-7
        )
    for table, prefix, result_table, columns in (
        (
            n.lines_t,
            "line",
            "res_line",
            ("p_from_mw", "q_from_mvar", "p_to_mw", "q_to_mvar"),
        ),
        (
            n.transformers_t,
            "trafo",
            "res_trafo",
            ("p_hv_mw", "q_hv_mvar", "p_lv_mw", "q_lv_mvar"),
        ),
    ):
        for i, values in reference[result_table].items():
            for field, expected in zip(("p0", "q0", "p1", "q1"), columns):
                assert table[field].at["now", f"{prefix} {i}"] == pytest.approx(
                    values[expected], abs=1e-6
                )


def test_units_status_names_and_source_unchanged(source):
    original = deepcopy(source)
    result = convert_pandapower_network(source)
    n = result.network
    assert list(n.buses.index) == ["bus 10", "bus 20", "bus 30", "bus 40"]
    assert n.loads.at["load 1", "bus"] == "bus 40"
    assert n.loads.at["load 0", "p_set"] == pytest.approx(10.8)
    assert n.generators.at["sgen 0", "p_set"] == pytest.approx(0.8)
    assert n.generators.at["sgen 0", "q_set"] == pytest.approx(0.16)
    assert (
        n.generators.at["sgen 0", "p_min_pu"] == n.generators.at["sgen 0", "p_max_pu"]
    )
    line = n.lines.loc["line 0"]
    assert line.r == pytest.approx(0.06 * 10 / 2)
    assert line.x == pytest.approx(0.2 * 10 / 2)
    assert line.b == pytest.approx(2 * math.pi * 50 * 8e-9 * 10 * 2)
    assert line.g == pytest.approx(0.01e-6 * 10 * 2)
    assert line.s_nom == pytest.approx(math.sqrt(3) * 110 * 0.5 * 2)
    assert line.s_max_pu == pytest.approx(0.8 * 0.9)
    assert n.transformers.at["trafo 0", "s_nom"] == 80
    assert n.transformers.at["trafo 0", "r"] == pytest.approx(0.005)
    assert n.transformers.at["trafo 0", "tap_ratio"] == pytest.approx(1.025)
    assert n.buses.at["bus 40", "pandapower_name"] == "Demand"
    assert n.meta[IMPORT_META_KEY]["bus_labels"]["50"] == "Demand"
    assert n.buses.at["bus 10", "x"] == pytest.approx(9.1)
    assert "OPF cost" in result.summary()
    for key, value in source.items():
        if isinstance(value, pd.DataFrame):
            pd.testing.assert_frame_equal(value, original[key])


def test_inactive_equipment_and_open_switches(source):
    source["bus"].loc[50, "in_service"] = False
    source["gen"].loc[0, "in_service"] = False
    source["switch"].loc[1] = {"bus": 30, "element": 1, "et": "l", "closed": False}
    result = convert_pandapower_network(source)
    assert "bus 50" not in result.network.buses.index
    assert "gen 0" not in result.network.generators.index
    assert "load 1" not in result.network.loads.index
    assert "line 1" not in result.network.lines.index
    assert "single-ended open branches" in result.summary()
    assert "out-of-service" in result.summary()


def test_switch_chains_and_open_bus_switch(source):
    source["bus"].loc[60] = source["bus"].loc[50]
    source["bus"].loc[70] = source["bus"].loc[50]
    source["switch"].loc[1] = {"bus": 50, "element": 60, "et": "b", "closed": True}
    source["switch"].loc[2] = {"bus": 60, "element": 40, "et": "b", "closed": True}
    source["switch"].loc[3] = {"bus": 60, "element": 70, "et": "b", "closed": False}
    n = convert_pandapower_network(source).network
    assert "bus 60" not in n.buses.index
    assert "bus 70" in n.buses.index
    assert n.meta[IMPORT_META_KEY]["bus_mapping"]["60"] == "bus 40"


@pytest.mark.parametrize(
    "table, column, value, message",
    [
        ("line", "max_i_ka", -1, "max_i_ka"),
        ("line", "x_ohm_per_km", float("inf"), "x_ohm_per_km"),
        ("line", "from_bus", 999, "missing pandapower bus"),
        ("load", "controllable", True, "controllable loads"),
        ("load", "const_z_p_percent", 20, "ZIP loads"),
        ("trafo", "tap_changer_type", "Ideal", "tap changer type"),
        ("trafo", "tap_step_degree", 10, "angled tap"),
        ("trafo", "vn_lv_kv", 21, "rated voltages"),
        ("trafo", "tap_dependency_table", True, "characteristic"),
        ("trafo", "leakage_resistance_ratio_hv", 0.7, "asymmetric"),
        ("trafo", "vkr_percent", 50, "inconsistent"),
        ("switch", "z_ohm", 1, "non-zero bus-switch"),
        ("switch", "closed", "maybe", "boolean"),
        ("gen", "slack", True, "Multiple slack"),
        ("gen", "min_p_mw", 100, "exceeds"),
    ],
)
def test_unsupported_or_invalid_data_fails_without_mutation(
    source, table, column, value, message
):
    if isinstance(value, str) and column in source[table]:
        source[table][column] = source[table][column].astype(object)
    source[table].loc[0, column] = value
    before = deepcopy(source)
    with pytest.raises(ValueError, match=message):
        convert_pandapower_network(source)
    for key, frame in before.items():
        if isinstance(frame, pd.DataFrame):
            pd.testing.assert_frame_equal(source[key], frame)


@pytest.mark.parametrize(
    "table", ["storage", "trafo3w", "impedance", "controller", "custom_device"]
)
def test_unsupported_active_equipment_is_not_silently_discarded(source, table):
    source[table] = pd.DataFrame({"in_service": [True]}, index=[0])
    with pytest.raises(ValueError, match=table):
        convert_pandapower_network(source)
    source[table].loc[0, "in_service"] = False
    assert len(convert_pandapower_network(source).network.buses) == 4


def test_missing_generator_bounds_are_explicit_and_can_solve(source):
    source["ext_grid"] = source["ext_grid"].drop(columns=["max_p_mw", "min_p_mw"])
    n = convert_pandapower_network(source).network
    assert n.generators.at["ext_grid 0", "p_max_pu"] == math.inf
    assert n.generators.at["ext_grid 0", "p_min_pu"] == -math.inf
    assert any("unlimited" in note for note in n.meta[IMPORT_META_KEY]["notes"])
    # Add explicit bounded dispatch and costs for a meaningful economic solve.
    n.generators.loc[
        "ext_grid 0", ["p_min_pu", "p_max_pu", "p_nom", "marginal_cost"]
    ] = [0, 1, 40, 10]
    n.generators.loc["gen 0", "marginal_cost"] = 5
    n.generators.loc["gen 0", "p_set"] = np.nan
    assert pd.isna(n.generators.at["ext_grid 0", "p_set"])
    assert run_network_optimisation(
        n, SolverSettings(threads=1, extra_solver_options={"output_flag": False})
    ) == ("ok", "optimal")
    assert n.generators_t.p.sum(axis=1).iloc[0] == pytest.approx(n.loads.p_set.sum())


def test_netcdf_roundtrip_preserves_import_metadata(tmp_path):
    n = load_network_from_pandapower(DATA / "pandapower_balanced.json").network
    path = tmp_path / "converted.nc"
    save_network_to_netcdf(n, path)
    restored = pypsa.Network(path)
    assert restored.meta[IMPORT_META_KEY] == n.meta[IMPORT_META_KEY]
    assert restored.buses.at["bus 40", "pandapower_name"] == "Demand"
    assert restored.transformers.at["trafo 0", "tap_ratio"] == pytest.approx(1.025)
    assert restored.generators_t.p.empty


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"not": "a network"}, "pandapower.to_json"),
        ({"_class": "pandapowerNet", "_object": []}, "malformed"),
        ({"_class": "pandapowerNet", "_object": {"version": "1.6"}}, "2.x/3.x"),
    ],
)
def test_rejects_unrelated_or_legacy_json(tmp_path, payload, message):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match=message):
        load_network_from_pandapower(path)


def test_json_import_does_not_import_pandapower_or_instantiate_objects(
    monkeypatch, tmp_path
):
    original_import = builtins.__import__

    def guarded(name, *args, **kwargs):
        assert not name.startswith("pandapower")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    document = json.loads((DATA / "pandapower_balanced.json").read_text())
    document["_object"]["custom_object"] = {
        "_class": "callable",
        "_module": "does_not_exist",
        "_object": "ignored data",
    }
    path = tmp_path / "network.JSON"
    path.write_text(json.dumps(document))
    assert len(load_network_from_pandapower(path).network.buses) == 4


def test_missing_excel_dependency_has_install_hint(monkeypatch):
    monkeypatch.setattr(pd, "read_excel", Mock(side_effect=ImportError("openpyxl")))
    with pytest.raises(ImportError, match="pip install"):
        load_network_from_pandapower(DATA / "pandapower_balanced.xlsx")


def test_rejects_pickle_and_malformed_json(tmp_path):
    with pytest.raises(ValueError, match=".json or .xlsx"):
        load_network_from_pandapower(tmp_path / "net.p")
    path = tmp_path / "bad.json"
    path.write_text("{")
    with pytest.raises(ValueError):
        load_network_from_pandapower(path)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, monkeypatch):
    for kind in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, kind, Mock(return_value=QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "question", Mock(return_value=QMessageBox.Discard))
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        Mock(return_value=(str(DATA / "pandapower_balanced.json"), "")),
    )
    w = MainWindow()
    monkeypatch.setattr(
        w,
        "_ask_for_view_options",
        Mock(return_value=SessionViewOptions.from_workspace("full")),
    )
    yield w
    w.optimisation_running = False
    w.close()
    w.deleteLater()
    app.processEvents()


def test_import_menu_new_dirty_session_and_safe_save(window, monkeypatch, tmp_path):
    window.import_pandapower_action.trigger()
    session = window.active_session()
    assert session.source_path is None
    assert session.is_modified
    assert session.workflow.steps[0].parameters["source_format"] == "pandapower"
    assert session.workflow.steps[0].parameters["import_notes"]
    QMessageBox.information.assert_called_once()
    target = tmp_path / "converted.nc"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", Mock(return_value=(str(target), ""))
    )
    assert window.save_network()
    assert session.source_path == target
    assert not session.is_modified
    assert target.is_file()


@pytest.mark.parametrize("stage", ["file", "workspace", "conversion"])
def test_cancel_or_failure_keeps_active_session(window, monkeypatch, stage):
    n = pypsa.Network()
    n.add("Bus", "original")
    window._add_network_session(n, None, SessionViewOptions.from_workspace("full"))
    session = window.active_session()
    if stage == "file":
        monkeypatch.setattr(QFileDialog, "getOpenFileName", Mock(return_value=("", "")))
    elif stage == "workspace":
        window._ask_for_view_options.return_value = None
    else:
        monkeypatch.setattr(
            "pypsa_gui.ui.main_window.load_network_from_pandapower",
            Mock(side_effect=ValueError("unsupported equipment")),
        )
    window.on_import_pandapower_network()
    assert window.active_session() is session
    assert len(window.network_store.list_sessions()) == 1
    assert session.is_modified
    if stage == "conversion":
        assert "unsupported equipment" in QMessageBox.critical.call_args.args[2]


def test_import_locked_during_optimisation(window):
    window._set_optimisation_running_state(True)
    assert not window.import_pandapower_action.isEnabled()
    window.on_import_pandapower_network()
    QFileDialog.getOpenFileName.assert_not_called()
    assert not window.network_store.list_sessions()
    window._set_optimisation_running_state(False)
    assert window.import_pandapower_action.isEnabled()
