"""Regression checks for settings propagation and real HiGHS optimisation."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace
import time
from unittest.mock import Mock

import pandas as pd
import pypsa
import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from pypsa_gui.models.session_view import SessionViewOptions
from pypsa_gui.models.solver_settings import SolverSettings
from pypsa_gui.services.optimisation import (
    OptimisationRunner,
    preview_network_optimisation,
    run_network_optimisation,
    validate_solver_configuration,
)
from pypsa_gui.ui.main_window import MainWindow
from pypsa_gui.ui.pages.run.solver_settings_page import SolverSettingsPage


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def quiet_dialogs(monkeypatch):
    for name in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, name, Mock(return_value=QMessageBox.Ok))


def small_network():
    network = pypsa.Network()
    network.set_snapshots(pd.date_range("2026-01-01", periods=3, freq="h"))
    network.add("Carrier", "AC")
    network.add("Bus", "A", carrier="AC", x=10, y=56)
    network.add("Generator", "G", bus="A", carrier="AC", p_nom=10, marginal_cost=10)
    network.add("Load", "L", bus="A", p_set=5)
    return network


def test_gurobi_configuration_reaches_the_correct_pypsa_calls(monkeypatch):
    monkeypatch.setattr("linopy.available_solvers", ["gurobi"])
    optimise = SimpleNamespace(
        create_model=Mock(), solve_model=Mock(return_value=("ok", "optimal"))
    )
    settings = SolverSettings(
        solver_name="gurobi",
        method=2,
        crossover=0,
        presolve=2,
        threads=3,
        time_limit=60,
        mip_gap=0,
        feasibility_tol=1e-6,
        optimality_tol=1e-7,
        assign_all_duals=False,
        transmission_losses=True,
        linearized_unit_commitment=True,
        extra_solver_options={"BarConvTol": 1e-8},
    )
    assert run_network_optimisation(SimpleNamespace(optimize=optimise), settings) == (
        "ok",
        "optimal",
    )
    optimise.create_model.assert_called_once_with(
        transmission_losses=True,
        linearized_unit_commitment=True,
    )
    optimise.solve_model.assert_called_once_with(
        solver_name="gurobi",
        assign_all_duals=False,
        solver_options={
            "Method": 2,
            "Crossover": 0,
            "Presolve": 2,
            "Threads": 3,
            "TimeLimit": 60,
            "MIPGap": 0,
            "FeasibilityTol": 1e-6,
            "OptimalityTol": 1e-7,
            "BarConvTol": 1e-8,
        },
    )


@pytest.mark.parametrize("method", [None, 0, 1, 2])
def test_highs_solves_and_receives_native_options(method):
    network = small_network()
    settings = SolverSettings(
        method=method,
        crossover=1,
        presolve=0,
        threads=1,
        time_limit=30,
        mip_gap=0,
        feasibility_tol=1e-6,
        optimality_tol=1e-6,
        extra_solver_options={"output_flag": False, "ipm_optimality_tolerance": 1e-8},
    )
    assert run_network_optimisation(network, settings) == ("ok", "optimal")
    assert network.objective == pytest.approx(150)
    assert network.generators_t.p["G"].tolist() == pytest.approx([5, 5, 5])
    native = network.model.solver_model
    for key, value in settings.to_solver_options().items():
        assert native.getOptionValue(key)[1] == value


@pytest.mark.parametrize("threads", [1, 2])
def test_highs_thread_setting_can_change_between_runs(threads):
    network = small_network()
    settings = SolverSettings(
        threads=threads, extra_solver_options={"output_flag": False}
    )
    assert run_network_optimisation(network, settings) == ("ok", "optimal")
    assert network.model.solver_model.getOptionValue("threads")[1] == threads


@pytest.mark.parametrize(
    "extra", [{"Crossover": 0}, {"time_limit": -1}, {"not_a_highs_option": 1}]
)
def test_invalid_native_options_are_rejected_before_model_build(extra):
    network = SimpleNamespace(optimize=SimpleNamespace(create_model=Mock()))
    with pytest.raises(ValueError, match="Invalid HiGHS option"):
        run_network_optimisation(network, SolverSettings(extra_solver_options=extra))
    network.optimize.create_model.assert_not_called()


def test_missing_solver_is_reported_without_fallback(monkeypatch):
    monkeypatch.setattr("linopy.available_solvers", ["highs"])
    with pytest.raises(ValueError, match="gurobipy"):
        validate_solver_configuration(SolverSettings(solver_name="gurobi"))


def test_preview_uses_model_flags_without_requiring_a_solver(monkeypatch):
    monkeypatch.setattr("linopy.available_solvers", [])
    network = SimpleNamespace(
        optimize=SimpleNamespace(create_model=Mock()),
        model=SimpleNamespace(nvars=3, ncons=4),
    )
    settings = SolverSettings(
        solver_name="gurobi",
        transmission_losses=True,
        linearized_unit_commitment=True,
    )
    result = preview_network_optimisation(network, settings)
    assert (result.variables, result.constraints) == (3, 4)
    network.optimize.create_model.assert_called_once_with(
        transmission_losses=True,
        linearized_unit_commitment=True,
    )


def test_runner_owns_an_independent_settings_snapshot():
    settings = SolverSettings(
        time_limit=30, extra_solver_options={"output_flag": False}
    )
    runner = OptimisationRunner(small_network(), settings)
    settings.solver_name = "gurobi"
    settings.extra_solver_options["output_flag"] = True
    assert runner.settings.solver_name == "highs"
    assert runner.settings.extra_solver_options == {"output_flag": False}


@pytest.mark.parametrize(
    "extra",
    [[], {"threads": [2]}, {"time_limit": float("nan")}, {"solver_name": "gurobi"}],
)
def test_extra_options_must_be_native_scalar_options(extra):
    with pytest.raises(ValueError):
        SolverSettings(extra_solver_options=extra).to_solver_options()


def test_highs_keeps_integrality_and_rejects_forced_lp_methods():
    network = small_network()
    network.generators.loc["G", "marginal_cost"] = 1
    network.generators.loc["G", "committable"] = True
    network.generators.loc["G", "p_min_pu"] = 0.8
    network.add("Generator", "backup", bus="A", p_nom=10, marginal_cost=10)
    settings = SolverSettings(threads=1, extra_solver_options={"output_flag": False})
    assert run_network_optimisation(network, settings) == ("ok", "optimal")
    assert network.objective == pytest.approx(150)
    assert network.generators_t.p["G"].abs().max() < 1e-7
    # A relaxed commitment could supply demand for only 15 cost units.
    with pytest.raises(ValueError, match="Use Automatic method"):
        run_network_optimisation(network, SolverSettings(method=2))


def test_settings_page_rejects_non_object_json_and_preserves_zero_gap(
    app, quiet_dialogs
):
    page = SolverSettingsPage()
    try:
        assert page.collect_settings().mip_gap is None
        page.mip_gap_spin.setValue(0)
        assert page.collect_settings().mip_gap == 0
        page.extra_options_edit.setPlainText("[]")
        changed = Mock()
        page.settings_changed.connect(changed)
        page.apply_button.click()
        changed.assert_not_called()
        QMessageBox.warning.assert_called_once()
        page.extra_options_edit.clear()
        page.solver_combo.setCurrentText("gurobi")
        page.method_spin.setValue(4)
        page.presolve_spin.setValue(2)
        page.solver_combo.setCurrentText("highs")
        assert page.collect_settings().method is None
        assert page.collect_settings().presolve is None
    finally:
        page.close()


def test_applied_settings_survive_session_switches_and_page_rebuilds(
    app, quiet_dialogs
):
    window = MainWindow()
    try:
        window._add_network_session(
            small_network(),
            None,
            SessionViewOptions.from_workspace("lightweight"),
            name="A",
        )
        first = window.active_session()
        page = window.central_panel.pages["Solver Settings"]
        page.time_limit_spin.setValue(17)
        page.method_spin.setValue(1)
        page.apply_button.click()
        window._add_network_session(
            small_network(),
            None,
            SessionViewOptions.from_workspace("analysis"),
            name="B",
        )
        assert window.active_session().solver_settings.time_limit is None
        window.network_store.set_active_session(first.id)
        window._refresh_active_session_ui()
        restored = window.central_panel.pages["Solver Settings"].collect_settings()
        assert (restored.time_limit, restored.method) == (17, 1)
        assert window.central_panel.pages["Optimisation"].solver_settings == restored
    finally:
        window.close()
        app.processEvents()


@pytest.mark.parametrize("trigger", ["menu", "page"])
def test_applied_settings_drive_a_real_gui_solve_and_workflow(
    app, quiet_dialogs, trigger
):
    window = MainWindow()
    try:
        window._add_network_session(
            small_network(), None, SessionViewOptions.from_workspace("lightweight")
        )
        page = window.central_panel.pages["Solver Settings"]
        page.threads_spin.setValue(1)
        page.time_limit_spin.setValue(30)
        page.linearized_uc_checkbox.setChecked(True)
        page.assign_duals_checkbox.setChecked(False)
        page.extra_options_edit.setPlainText('{"output_flag": false}')
        page.apply_button.click()
        expected = window.active_session().solver_settings
        optimisation_page = window.central_panel.pages["Optimisation"]
        optimisation_page.preview_button.click()
        assert window.active_network()._linearized_uc
        if trigger == "menu":
            window.run_optimisation_action.trigger()
        else:
            optimisation_page.run_button.click()
        assert window.optimisation_running
        assert not page.isEnabled()
        deadline = time.monotonic() + 30
        while window.optimisation_running and time.monotonic() < deadline:
            app.processEvents()
            QTest.qWait(5)
        assert not window.optimisation_running, "The GUI solve did not finish."
        assert window.active_network().objective == pytest.approx(150)
        record = window.active_session().workflow.steps[-1].parameters
        assert record["solver"] == "highs"
        assert record["options"] == expected.to_solver_options()
        assert record["model_options"] == expected.to_model_options()
        assert record["assign_all_duals"] is False
        assert "optimal" in record["status"]
        assert page.isEnabled()
        QMessageBox.critical.assert_not_called()
    finally:
        if window.optimisation_worker is not None:
            window.optimisation_worker.wait(30000)
        window.close()
        app.processEvents()
