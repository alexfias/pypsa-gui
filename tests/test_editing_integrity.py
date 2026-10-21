"""Editing must preserve model inputs/references and never silently lose work."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pypsa
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog

from pypsa_gui.models.session_view import SessionViewOptions
from pypsa_gui.models.solver_settings import SolverSettings
from pypsa_gui.services.capacity_constraints import META_KEY, apply_capacity_limit
from pypsa_gui.services.locations import (
    LOCATION_META_KEY,
    load_locations,
    serialise_locations,
    sync_locations,
)
from pypsa_gui.services.network_edits import edit_component
from pypsa_gui.services.network_io import save_network_to_netcdf
from pypsa_gui.services.optimisation import run_network_optimisation
from pypsa_gui.services.reporting.scenario_report import network_has_results
from pypsa_gui.ui.main_window import MainWindow
from pypsa_gui.ui.models.buses_table_model import BusesTableModel
from pypsa_gui.ui.pages.component_page import ComponentPage
from pypsa_gui.ui.pages.network_builder_page import NetworkBuilderPage


@pytest.fixture(scope="module", autouse=True)
def offline():
    with pypsa.option_context("general.allow_network_requests", False):
        yield


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialogs(monkeypatch):
    for kind in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, kind, Mock(return_value=QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "question", Mock(return_value=QMessageBox.Discard))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", Mock(return_value=("", "")))


def network():
    n = pypsa.Network()
    n.set_snapshots(pd.date_range("2025-01-01", periods=2, freq="h"))
    n.add("Carrier", "AC")
    n.add("Bus", ["A", "B", "C"], carrier="AC", x=[1, 2, 3], y=[4, 5, 6])
    n.add(
        "Generator",
        "G",
        bus="A",
        carrier="AC",
        p_nom=10,
        marginal_cost=5,
        p_max_pu=[0.5, 1],
    )
    n.add("Load", "L", bus="A", p_set=[2, 4])
    return n


def solve(n):
    return run_network_optimisation(
        n, SolverSettings(threads=1, extra_solver_options={"output_flag": False})
    )


def table_index(page, name, attribute):
    return page.model.index(
        next(i for i, row in enumerate(page.model._rows) if row["name"] == name),
        page.model._columns.index(attribute),
    )


def open_window(n, path=None):
    window = MainWindow()
    window._add_network_session(
        n, path, SessionViewOptions.from_workspace("full"), name="test"
    )
    return window


def test_generator_rename_preserves_profiles_caps_and_solve(tmp_path):
    n = network()
    n.generators.loc["G", "p_nom_extendable"] = True
    n.generators.loc["G", "capital_cost"] = 1
    apply_capacity_limit(n, "generators", ["G"], "<=", 10)
    assert solve(n) == ("ok", "optimal")
    old_objective = n.objective
    original = n.generators_t.p_max_pu["G"].copy()
    weights = n.snapshot_weightings.copy()
    edit_component(n, "generators", "G", "name", "Renamed G")
    assert "G" not in n.generators.index
    pd.testing.assert_series_equal(
        n.generators_t.p_max_pu["Renamed G"], original, check_names=False
    )
    pd.testing.assert_frame_equal(n.snapshot_weightings, weights)
    assert n.meta[META_KEY][0]["names"] == ["Renamed G"]
    assert not network_has_results(n) and n._model is None and n._objective is None
    path = tmp_path / "renamed.nc"
    save_network_to_netcdf(n, path)
    restored = pypsa.Network(path)
    assert solve(restored) == ("ok", "optimal")
    assert restored.objective == pytest.approx(old_objective)
    assert restored.generators_t.p["Renamed G"].tolist() == pytest.approx([2, 4])


def test_bus_rename_preserves_all_ports_global_constraint_and_locations():
    n = network()
    n.add("Line", "line", bus0="A", bus1="B", x=0.1)
    n.add("Link", "multi", bus0="B", bus1="C", bus2="A", efficiency2=-0.5)
    n.add("Store", "store", bus="A")
    n.add("StorageUnit", "battery", bus="A")
    n.add(
        "GlobalConstraint",
        "limit",
        type="tech_capacity_expansion_limit",
        bus="A",
        carrier_attribute="AC",
    )
    n.buses_t.v_mag_pu_set["A"] = [1, 1.05]
    locations = load_locations(n)
    n.meta[LOCATION_META_KEY] = serialise_locations(locations)
    location_id = next(
        key for key, value in locations.items() if "A" in value.bus_names
    )
    edit_component(n, "buses", "A", "name", "New A", locations=locations)
    for table, name, field in [
        ("generators", "G", "bus"),
        ("loads", "L", "bus"),
        ("lines", "line", "bus0"),
        ("links", "multi", "bus2"),
        ("stores", "store", "bus"),
        ("storage_units", "battery", "bus"),
        ("global_constraints", "limit", "bus"),
    ]:
        assert getattr(n, table).at[name, field] == "New A"
    assert n.buses_t.v_mag_pu_set["New A"].tolist() == [1, 1.05]
    assert locations[location_id].bus_names == ["New A"]
    assert locations[location_id].name == "New A"
    assert load_locations(n)[location_id].bus_names == ["New A"]


@pytest.mark.parametrize("new_name", ["", "B"])
def test_invalid_bus_rename_is_atomic(new_name):
    n = network()
    buses, generators = n.buses.copy(), n.generators.copy()
    with pytest.raises(ValueError):
        edit_component(n, "buses", "A", "name", new_name)
    pd.testing.assert_frame_equal(n.buses, buses)
    pd.testing.assert_frame_equal(n.generators, generators)


def test_rename_cannot_overwrite_an_orphaned_time_series():
    n = network()
    n.generators_t.p_max_pu["target"] = [0.1, 0.2]
    old = n.generators_t.p_max_pu.copy()
    with pytest.raises(ValueError, match="time-series column"):
        edit_component(n, "generators", "G", "name", "target")
    pd.testing.assert_frame_equal(n.generators_t.p_max_pu, old)
    assert "G" in n.generators.index


@pytest.mark.parametrize(
    "field,value",
    [
        ("p_nom", "-1"),
        ("p_nom", "nan"),
        ("p_nom", "inf"),
        ("p_nom", ""),
        ("p_nom_extendable", "perhaps"),
        ("min_up_time", "1.5"),
        ("efficiency", "0"),
        ("bus", "absent"),
        ("bus", ""),
        ("p_nom_min", "20"),
        ("p_min_pu", "0.8"),
        ("control", "invalid"),
    ],
)
def test_invalid_edits_leave_inputs_and_solved_results_untouched(field, value):
    n = network()
    n.generators.loc["G", "p_nom_max"] = 15
    n.generators_t.p = pd.DataFrame({"G": [2, 4]}, index=n.snapshots)
    n._objective = 30
    sentinel = object()
    n._model = sentinel
    before = n.generators.copy(deep=True)
    with pytest.raises(ValueError):
        edit_component(n, "generators", "G", field, value)
    pd.testing.assert_frame_equal(n.generators, before)
    assert network_has_results(n) and n._model is sentinel and n._objective == 30


def test_valid_boolean_optional_nan_infinity_and_signed_inputs():
    n = network()
    edit_component(n, "generators", "G", "p_nom_extendable", "yes")
    assert bool(n.generators.at["G", "p_nom_extendable"])
    edit_component(n, "generators", "G", "min_up_time", "2")
    assert n.generators.at["G", "min_up_time"] == 2
    edit_component(n, "generators", "G", "ramp_limit_up", "0.2")
    edit_component(n, "generators", "G", "ramp_limit_up", "")
    assert np.isnan(n.generators.at["G", "ramp_limit_up"])
    edit_component(n, "generators", "G", "p_nom_max", "20")
    edit_component(n, "generators", "G", "p_nom_max", "inf")
    assert np.isinf(n.generators.at["G", "p_nom_max"])
    edit_component(n, "generators", "G", "marginal_cost", "-5")
    assert n.generators.at["G", "marginal_cost"] == -5
    n.add("Link", "heatpump", bus0="A", bus1="B")
    edit_component(n, "links", "heatpump", "efficiency", "3")
    assert n.links.at["heatpump", "efficiency"] == 3


def test_capacity_constraint_conflict_is_detected_before_edit():
    n = network()
    n.generators.loc["G", "p_nom_extendable"] = True
    apply_capacity_limit(n, "generators", ["G"], ">=", 8)
    with pytest.raises(ValueError, match="conflicts"):
        edit_component(n, "generators", "G", "p_nom_max", "5")
    assert np.isinf(n.generators.at["G", "p_nom_max"])


def test_calculated_outputs_and_dynamic_overrides_are_read_only(app):
    page = ComponentPage("generators")
    n = network()
    page.set_network(n)
    for field in ("p_nom_opt", "p_max_pu"):
        index = table_index(page, "G", field)
        assert not page.model.flags(index) & Qt.ItemIsEditable
        assert page.model.data(index, Qt.ToolTipRole)
        assert not page.model.setData(index, "4")
        assert page.edit_error_label.text()
    assert n.generators_t.p_max_pu["G"].tolist() == [0.5, 1]
    page.close()


def test_legacy_bus_model_uses_validation_and_output_locks(app):
    n = network()
    model = BusesTableModel(n)
    voltage = model.index(0, model.columns.index("v_nom"))
    assert not model.setData(voltage, "-1")
    assert model.setData(voltage, "380")
    assert n.buses.at["A", "v_nom"] == 380
    assert (
        not model.flags(model.index(0, model.columns.index("control")))
        & Qt.ItemIsEditable
    )


def test_table_edits_dirty_only_active_session_refresh_views_and_record_workflow(
    app, dialogs
):
    n = network()
    n.generators_t.p = pd.DataFrame({"G": [2, 4]}, index=n.snapshots)
    window = open_window(n, Path("first.nc"))
    first = window.active_session()
    window._add_network_session(
        network(),
        Path("second.nc"),
        SessionViewOptions.from_workspace("full"),
        name="second",
    )
    second = window.active_session()
    window.network_store.set_active_session(first.id)
    window._refresh_active_session_ui()
    try:
        page = window.central_panel.pages["Generators"]
        page.filter_by_bus("A")
        page.search_box.setText("G")
        idx = table_index(page, "G", "p_nom")
        assert page.model.setData(idx, "10")  # No-op.
        assert not first.is_modified and network_has_results(n)
        assert page.model.setData(idx, "12")
        assert first.is_modified and not second.is_modified
        assert not network_has_results(n)
        app.processEvents()
        assert page.active_bus_filter == "A"
        assert page.search_box.text() == "G"
        assert not window.central_panel.pages[
            "Optimisation"
        ].export_report_button.isEnabled()
        step = first.workflow.steps[-1]
        assert step.parameters["parameters"]["attribute"] == "p_nom"
        assert step.parameters["parameters"]["new_value"] == 12
        # Renaming a filtered bus also updates filters and diagram selections.
        buses = window.central_panel.pages["Buses"]
        buses.selected_bus = "A"
        buses.manual_buses = ["A", "B"]
        assert buses.model.setData(table_index(buses, "A", "name"), "Renamed")
        app.processEvents()
        assert page.active_bus_filter == "Renamed"
        assert buses.selected_bus == "Renamed" and "Renamed" in buses.manual_buses
    finally:
        window.close()


def test_viewing_builder_does_not_change_network_inputs(app):
    n = network()
    old = n.buses.copy(deep=True)
    page = NetworkBuilderPage()
    page.set_network(n)
    page.refresh_network_contents()
    pd.testing.assert_frame_equal(n.buses, old)
    page.close()


def test_builder_edits_clear_results_and_lock_during_solve(app, dialogs):
    n = network()
    window = open_window(n, Path("existing.nc"))
    session = window.active_session()
    try:
        n.generators_t.p = pd.DataFrame({"G": [2, 4]}, index=n.snapshots)
        page = window.central_panel.pages["Network Builder"]
        n.add("Load", "new", bus="A", p_set=1)
        page._mark_network_modified()
        assert session.is_modified and not network_has_results(n)
        app.processEvents()
        assert window.central_panel.pages["Loads"].model.rowCount() == 2
        window._optimisation_session_id = session.id
        window._set_optimisation_running_state(True)
        assert not page.isEnabled() and not window.save_action.isEnabled()
        with pytest.raises(ValueError, match="locked"):
            edit_component(n, "generators", "G", "p_nom", "9")
        gen_page = window.central_panel.pages["Generators"]
        assert not gen_page.model.setData(table_index(gen_page, "G", "p_nom"), "9")
    finally:
        window._set_optimisation_running_state(False)
        window._optimisation_session_id = None
        window.close()


def test_locations_survive_rename_save_and_reload_without_input_mutation(tmp_path):
    n = network()
    locations = load_locations(n)
    key = next(key for key, item in locations.items() if "A" in item.bus_names)
    locations[key].name = "Custom site"
    edit_component(n, "buses", "A", "name", "New A", locations=locations)
    sync_locations(n, locations)
    before = n.buses.copy()
    path = tmp_path / "locations.nc"
    save_network_to_netcdf(n, path, locations=locations)
    pd.testing.assert_frame_equal(n.buses, before)
    restored = pypsa.Network(path)
    assert load_locations(restored)[key].name == "Custom site"
    assert load_locations(restored)[key].bus_names == ["New A"]


def test_failed_save_preserves_file_and_metadata(tmp_path, monkeypatch):
    n = network()
    path = tmp_path / "existing.nc"
    path.write_bytes(b"previous complete file")
    old_meta = deepcopy(n.meta)

    def fail(destination):
        Path(destination).write_bytes(b"incomplete export")
        raise OSError("disk full")

    monkeypatch.setattr(n, "export_to_netcdf", fail)
    with pytest.raises(OSError, match="disk full"):
        save_network_to_netcdf(n, path, locations=load_locations(n))
    assert path.read_bytes() == b"previous complete file"
    assert n.meta == old_meta
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize(
    "reply,accepted", [(QMessageBox.Cancel, False), (QMessageBox.Discard, True)]
)
def test_close_prompts_for_unsaved_changes(app, dialogs, monkeypatch, reply, accepted):
    window = open_window(network())
    try:
        monkeypatch.setattr(QMessageBox, "question", Mock(return_value=reply))
        event = QCloseEvent()
        window.closeEvent(event)
        assert event.isAccepted() == accepted
        assert window.active_session().is_modified
    finally:
        monkeypatch.setattr(
            QMessageBox, "question", Mock(return_value=QMessageBox.Discard)
        )
        window.close()


def test_close_save_cancel_or_export_failure_keeps_session_dirty(
    app, dialogs, monkeypatch, tmp_path
):
    window = open_window(network())
    try:
        monkeypatch.setattr(
            QMessageBox, "question", Mock(return_value=QMessageBox.Save)
        )
        event = QCloseEvent()
        window.closeEvent(event)  # File dialog cancelled.
        assert not event.isAccepted() and window.active_session().is_modified
        monkeypatch.setattr(
            QFileDialog,
            "getSaveFileName",
            Mock(return_value=(str(tmp_path / "network.nc"), "")),
        )
        monkeypatch.setattr(
            "pypsa_gui.ui.main_window.save_network_to_netcdf",
            Mock(side_effect=OSError("disk full")),
        )
        event = QCloseEvent()
        window.closeEvent(event)
        assert not event.isAccepted() and window.active_session().is_modified
        assert window.active_session().source_path is None
        QMessageBox.critical.assert_called_once()
    finally:
        monkeypatch.setattr(
            QMessageBox, "question", Mock(return_value=QMessageBox.Discard)
        )
        window.close()


def test_close_saves_every_dirty_session_to_its_own_file(
    app, dialogs, monkeypatch, tmp_path
):
    window = open_window(network(), tmp_path / "first.nc")
    first = window.active_session()
    first.is_modified = True
    second_network = network()
    second_network.generators.loc["G", "p_nom"] = 25
    window._add_network_session(
        second_network,
        tmp_path / "second.nc",
        SessionViewOptions.from_workspace("full"),
        name="second",
    )
    second = window.active_session()
    second.is_modified = True
    try:
        monkeypatch.setattr(
            QMessageBox, "question", Mock(return_value=QMessageBox.Save)
        )
        event = QCloseEvent()
        window.closeEvent(event)
        assert event.isAccepted()
        assert not first.is_modified and not second.is_modified
        assert window.active_session() is second
        assert pypsa.Network(tmp_path / "first.nc").generators.at["G", "p_nom"] == 10
        assert pypsa.Network(tmp_path / "second.nc").generators.at["G", "p_nom"] == 25
    finally:
        window.close()


def test_close_is_blocked_until_solver_thread_has_finished(app, dialogs):
    window = open_window(network())
    try:
        window.optimisation_running = True
        event = QCloseEvent()
        window.closeEvent(event)
        assert not event.isAccepted()
        QMessageBox.question.assert_not_called()
    finally:
        window.optimisation_running = False
        window.close()


def test_duplicate_builder_link_does_not_change_network_or_results(
    app, dialogs, monkeypatch
):
    from PySide6.QtWidgets import QDialog

    n = network()
    n.add("Link", "existing", bus0="A", bus1="B", p_nom=1)
    n.generators_t.p = pd.DataFrame({"G": [2, 4]}, index=n.snapshots)
    page = NetworkBuilderPage()
    page.set_network(n)
    changed = Mock()
    page.network_modified.connect(changed)
    dialog = Mock()
    dialog.exec.return_value = QDialog.Accepted
    dialog.values.return_value = {
        "name": "existing",
        "p_nom": 50,
        "efficiency": 1,
        "carrier": "AC",
    }
    monkeypatch.setattr(
        "pypsa_gui.ui.pages.network_builder_page.LinkCreationDialog",
        Mock(return_value=dialog),
    )
    page._create_link_between("A", "C")
    assert n.links.at["existing", "p_nom"] == 1
    assert n.links.at["existing", "bus1"] == "B"
    assert network_has_results(n)
    changed.assert_not_called()
    QMessageBox.warning.assert_called_once()
    page.close()


def test_failed_profile_scaling_does_not_change_placeholder_snapshots():
    from pypsa_gui.models.time_series_profile import TimeSeriesProfile
    from pypsa_gui.services.time_series_library import TimeSeriesLibrary

    n = pypsa.Network()
    n.add("Bus", "A")
    n.add("Generator", "G", bus="A")
    old_snapshots, old_weights = n.snapshots.copy(), n.snapshot_weightings.copy()
    library = TimeSeriesLibrary()
    library.add_profile(
        TimeSeriesProfile(
            "zero",
            "zero",
            "wind",
            "test",
            pd.Series([0, 0], index=pd.date_range("2025-01-01", periods=2, freq="h")),
        )
    )
    with pytest.raises(ValueError, match="infeasible"):
        library.apply_profile_to_generator(n, "G", "zero", target_capacity_factor=0.5)
    assert n.snapshots.equals(old_snapshots)
    pd.testing.assert_frame_equal(n.snapshot_weightings, old_weights)
    assert n.generators_t.p_max_pu.empty


def test_initial_profile_keeps_existing_single_snapshot_inputs():
    from pypsa_gui.models.time_series_profile import TimeSeriesProfile
    from pypsa_gui.services.time_series_library import TimeSeriesLibrary

    n = pypsa.Network()
    n.add("Bus", "A")
    n.add("Generator", "G", bus="A")
    n.add("Load", "L", bus="A", p_set=[7])
    library = TimeSeriesLibrary()
    snapshots = pd.date_range("2025-01-01", periods=2, freq="h")
    library.add_profile(
        TimeSeriesProfile(
            "wind", "wind", "wind", "test", pd.Series([0.2, 0.8], index=snapshots)
        )
    )
    library.apply_profile_to_generator(n, "G", "wind")
    assert n.snapshots.equals(snapshots)
    assert n.loads_t.p_set["L"].tolist() == [7, 7]
    assert n.generators_t.p_max_pu["G"].tolist() == [0.2, 0.8]


def test_workflow_edits_with_nan_infinity_are_standard_json():
    import json
    from pypsa_gui.workflows.recorder import WorkflowRecorder
    from pypsa_gui.workflows.serialization import workflow_to_dict

    recorder = WorkflowRecorder()
    recorder.record_modify_network(
        modification="component_edit",
        parameters={"old_value": np.float64(np.nan), "new_value": np.float64(np.inf)},
    )
    payload = json.dumps(workflow_to_dict(recorder.workflow), allow_nan=False)
    assert '"nan"' in payload and '"inf"' in payload


def test_queued_refresh_cannot_edit_a_newly_selected_session(app, dialogs):
    first_network = network()
    window = open_window(first_network, Path("first.nc"))
    first = window.active_session()
    try:
        page = window.central_panel.pages["Generators"]
        assert page.model.setData(table_index(page, "G", "name"), "First G")
        window._add_network_session(
            network(),
            Path("second.nc"),
            SessionViewOptions.from_workspace("full"),
            name="second",
        )
        second = window.active_session()
        app.processEvents()
        assert first.is_modified and not second.is_modified
        assert "First G" in first.network.generators.index
        assert "G" in second.network.generators.index
        assert window.central_panel.pages["Generators"].network is second.network
    finally:
        window.close()
