"""Small numerical examples with independently calculable expected results."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import Mock

import numpy as np
import pandas as pd
import pypsa
import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from pypsa_gui.models.session_view import SessionViewOptions
from pypsa_gui.models.solver_settings import SolverSettings
from pypsa_gui.services.capacity_constraints import (
    META_KEY,
    apply_capacity_limit,
    validate_capacity_constraints,
)
from pypsa_gui.services.congestion import (
    get_combined_congestion_table,
    get_branch_map_data,
)
from pypsa_gui.services.emissions import (
    get_generator_emissions,
    get_total_emissions,
    get_total_generation,
    get_average_emission_intensity,
    get_zero_emission_generation_share,
)
from pypsa_gui.services.metrics import load_timeseries, load_by_bus, snapshot_weights
from pypsa_gui.services.optimisation import (
    run_network_optimisation,
    preview_network_optimisation,
)
from pypsa_gui.services.preprocessing import (
    aggregate_snapshots,
    copy_for_preprocessing,
    commit_preprocessing,
)
from pypsa_gui.services.prices import (
    get_price_summary_stats,
    get_average_price_by_bus,
    get_negative_price_counts,
)
from pypsa_gui.services.reporting.scenario_report import (
    _calculate_metrics,
    network_has_results,
    generate_scenario_report,
)
from pypsa_gui.services.scenario_builder import (
    _annual_electricity_demand_mwh,
    _apply_co2_price,
)
from pypsa_gui.services.storage import (
    get_storage_dispatch_by_asset,
    get_storage_soc_by_asset,
    get_storage_unit_summary,
    get_charge_discharge_timeseries,
)
from pypsa_gui.ui.main_window import MainWindow
from pypsa_gui.ui.pages.emissions_page import EmissionsPage
from pypsa_gui.ui.pages.pre_run_tools_page import PreRunToolsPage


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module", autouse=True)
def offline_pypsa():
    # NetCDF import otherwise performs an unrelated online release check.
    with pypsa.option_context("general.allow_network_requests", False):
        yield


@pytest.fixture
def quiet_dialogs(monkeypatch):
    for name in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, name, Mock(return_value=QMessageBox.Ok))


def base_network(periods=2):
    n = pypsa.Network()
    n.set_snapshots(pd.date_range("2025-01-01", periods=periods, freq="h"))
    n.add("Carrier", "AC")
    n.add("Bus", "A", carrier="AC", x=0, y=0)
    return n


def solve(n):
    return run_network_optimisation(
        n, SolverSettings(threads=1, extra_solver_options={"output_flag": False})
    )


def emissions_network():
    n = base_network()
    n.snapshot_weightings.loc[:, "generators"] = [1, 3]
    n.snapshot_weightings.loc[:, "objective"] = [
        10,
        20,
    ]  # Never use these for physical CO2.
    n.add("Carrier", "gas", co2_emissions=0.2)
    n.add("Carrier", "wind", co2_emissions=0)
    n.add(
        "Generator",
        "gas",
        bus="A",
        carrier="gas",
        efficiency=[0.5, 0.25],
        p_nom=100,
        marginal_cost=[10, 20],
    )
    n.add("Generator", "wind", bus="A", carrier="wind", p_nom=100)
    n.generators_t.p = pd.DataFrame(
        {"gas": [10, 20], "wind": [20, 10]}, index=n.snapshots
    )
    return n


def test_emissions_and_report_share_efficiency_and_physical_weights():
    n = emissions_network()
    # 10/.5*.2*1 + 20/.25*.2*3 = 52 t; positive energy = 120 MWh.
    assert get_generator_emissions(n)["gas"].tolist() == pytest.approx([4, 48])
    assert get_total_emissions(n) == pytest.approx(52)
    assert get_total_generation(n) == pytest.approx(120)
    assert get_average_emission_intensity(n) == pytest.approx(1000 * 52 / 120)
    assert get_zero_emission_generation_share(n) == pytest.approx(100 * 50 / 120)
    report = _calculate_metrics(n)
    assert report.emissions_tonnes == pytest.approx(52)
    assert report.generation_mwh == pytest.approx(120)


def test_signed_emissions_keep_negative_dispatch_and_carrier_factors():
    n = emissions_network()
    n.generators_t.p.loc[n.snapshots[0], "gas"] = -10
    assert get_total_emissions(n) == pytest.approx(44)
    n.carriers.loc["gas", "co2_emissions"] = -0.2
    assert get_total_emissions(n) == pytest.approx(-44)
    assert _calculate_metrics(n).emissions_tonnes == pytest.approx(-44)


@pytest.mark.parametrize("invalid", [0, -0.1, float("nan"), float("inf")])
def test_invalid_emitting_efficiency_is_not_assumed_to_be_one(invalid):
    n = emissions_network()
    n.generators_t.efficiency.loc[n.snapshots[0], "gas"] = invalid
    with pytest.raises(ValueError, match="efficiency"):
        get_total_emissions(n)
    with pytest.raises(ValueError, match="efficiency"):
        _apply_co2_price(n, 100)


def test_emissions_page_handles_bad_efficiency_without_showing_old_results(app):
    n = emissions_network()
    page = EmissionsPage()
    page.set_network(n)
    n.generators_t.efficiency.iloc[0, 0] = 0
    page.refresh()
    assert page.total_emissions_card.value_label.text() == "-"
    assert "efficiency" in page.warning_label.text()
    page.close()


def test_carbon_price_respects_time_varying_efficiency_and_cost():
    n = emissions_network()
    _apply_co2_price(n, 100)
    assert n.generators_t.marginal_cost["gas"].tolist() == pytest.approx([50, 100])
    assert n.generators.at["wind", "marginal_cost"] == 0


def test_reported_emissions_match_binding_pypsa_primary_energy_constraint(tmp_path):
    n = emissions_network()
    n.generators_t.p = pd.DataFrame(index=n.snapshots)
    n.generators_t.marginal_cost["gas"] = 1
    n.generators.at["wind", "marginal_cost"] = 100
    n.add("Load", "load", bus="A", p_set=6)
    n.add(
        "GlobalConstraint",
        "CO2",
        type="primary_energy",
        carrier_attribute="co2_emissions",
        sense="<=",
        constant=8,
    )
    assert solve(n) == ("ok", "optimal")
    assert get_total_emissions(n) == pytest.approx(8)
    assert _calculate_metrics(n).emissions_tonnes == pytest.approx(8)
    path = generate_scenario_report(n, tmp_path / "report.pdf")
    assert path.read_bytes().startswith(b"%PDF")


def test_static_and_dynamic_loads_and_prices_match_report():
    n = base_network()
    n.snapshot_weightings.loc[:, "generators"] = [1, 3]
    n.add("Bus", "H", carrier="hydrogen")
    n.add("Load", "static", bus="A", p_set=2)
    n.add("Load", "dynamic", bus="A", p_set=[1, 3])
    n.add("Load", "hydrogen", bus="H", p_set=100)
    n.buses_t.marginal_price = pd.DataFrame(
        {"A": [-10, 30], "H": [1000, 1000]}, index=n.snapshots
    )
    assert load_by_bus(n, electricity_only=True)["A"].tolist() == [3, 5]
    assert _annual_electricity_demand_mwh(n) == pytest.approx(18)
    report = _calculate_metrics(n)
    assert report.demand_mwh == pytest.approx(
        418
    )  # All energy carriers in total demand.
    assert report.average_electricity_price_eur_per_mwh == pytest.approx(420 / 18)
    assert get_price_summary_stats(n)["avg_price"] == pytest.approx(420 / 18)
    assert get_average_price_by_bus(n)["A"] == pytest.approx(20)
    assert get_negative_price_counts(n)["A"] == pytest.approx(1)
    n.snapshot_weightings.loc[:, "generators"] = [0.5, 3]
    assert get_price_summary_stats(n)["negative_hours"] == pytest.approx(0.5)


def test_storage_energy_soc_and_round_trip_efficiency():
    n = base_network()
    n.snapshot_weightings.loc[:, "stores"] = [1, 3]
    n.add(
        "StorageUnit",
        "battery",
        bus="A",
        p_nom=10,
        efficiency_store=0.8,
        efficiency_dispatch=0.9,
    )
    n.storage_units_t.p = pd.DataFrame({"battery": [2, 4]}, index=n.snapshots)
    n.storage_units_t.state_of_charge = pd.DataFrame(
        {"battery": [10, 2]}, index=n.snapshots
    )
    assert get_storage_dispatch_by_asset(n)["battery"] == pytest.approx(14)
    assert get_storage_soc_by_asset(n)["battery"] == pytest.approx(4)
    assert get_storage_unit_summary(n)["avg_efficiency"] == pytest.approx(0.72)


def test_simultaneous_storage_charging_and_discharge_do_not_cancel():
    n = base_network()
    n.add("StorageUnit", ["charging", "discharging"], bus="A", p_nom=10)
    n.storage_units_t.p = pd.DataFrame(
        {"charging": [-2, -4], "discharging": [2, 4]}, index=n.snapshots
    )
    charge, discharge = get_charge_discharge_timeseries(n)
    assert charge.tolist() == discharge.tolist() == [2, 4]


def test_congestion_hours_means_and_maps_use_weights():
    n = base_network()
    n.add("Bus", "B", carrier="AC", x=1, y=1)
    n.add("Line", "line", bus0="A", bus1="B", s_nom=10, x=0.1)
    n.lines.at["line", "s_nom_opt"] = 10
    n.snapshot_weightings.loc[:, "generators"] = [0.5, 3]
    n.lines_t.p0 = pd.DataFrame({"line": [11, 5]}, index=n.snapshots)
    row = get_combined_congestion_table(n).iloc[0]
    assert row.hours_above_100 == pytest.approx(0.5)
    assert row.mean_loading == pytest.approx(2.05 / 3.5)
    assert get_branch_map_data(n, "hours_congested").iloc[0].value == pytest.approx(0.5)


def investment_network():
    n = base_network(1)
    n.add("Load", "load", bus="A", p_set=6)
    n.add("Generator", "fixed", bus="A", p_nom=3, marginal_cost=100)
    n.add(
        "Generator",
        "cheap",
        bus="A",
        p_nom_extendable=True,
        capital_cost=1,
        marginal_cost=1,
    )
    n.add(
        "Generator",
        "expensive",
        bus="A",
        p_nom_extendable=True,
        capital_cost=10,
        marginal_cost=1,
    )
    return n


@pytest.mark.parametrize(
    "sense,value,expected", [("<=", 8, 5), (">=", 10, 7), ("=", 10, 7)]
)
def test_aggregate_constraints_count_fixed_assets_and_optimise_allocation(
    sense, value, expected
):
    n = investment_network()
    apply_capacity_limit(n, "generators", n.generators.index.tolist(), sense, value)
    before = preview_network_optimisation(n)
    assert "GUI-capacity-0" in n.model.constraints
    assert before.constraints > 0
    assert solve(n) == ("ok", "optimal")
    assert n.generators.at["cheap", "p_nom_opt"] == pytest.approx(expected)
    assert n.generators.at["expensive", "p_nom_opt"] == pytest.approx(0)
    assert n.generators.at["cheap", "p_nom"] == 0  # No nominal rescaling.
    assert n.generators.at["fixed", "p_nom"] == 3


@pytest.mark.parametrize(
    "sense,value,expected", [("<=", 3, 3), (">=", 8, 8), ("=", 4, 4)]
)
def test_per_asset_bounds_constrain_actual_investment(sense, value, expected):
    n = investment_network()
    apply_capacity_limit(n, "generators", ["cheap"], sense, value, aggregate=False)
    assert solve(n) == ("ok", "optimal")
    assert n.generators.at["cheap", "p_nom_opt"] == pytest.approx(expected)


@pytest.mark.parametrize(
    "component,table,nominal",
    [
        ("Store", "stores", "e_nom"),
        ("StorageUnit", "storage_units", "p_nom"),
        ("Link", "links", "p_nom"),
    ],
)
def test_aggregate_capacity_limits_support_energy_storage_and_links(
    component, table, nominal
):
    n = investment_network()
    kwargs = {f"{nominal}_extendable": True, "capital_cost": 1}
    if component == "Link":
        n.add("Bus", "B", carrier="AC")
        kwargs.update(bus0="A", bus1="B")
    else:
        kwargs["bus"] = "A"
    n.add(component, "asset", **kwargs)
    apply_capacity_limit(n, table, ["asset"], ">=", 4)
    assert solve(n) == ("ok", "optimal")
    assert getattr(n, table).at["asset", nominal + "_opt"] == pytest.approx(4)


def test_fixed_capacity_conflicts_fail_without_editing_inputs():
    n = investment_network()
    original = n.generators.copy(deep=True)
    with pytest.raises(ValueError, match="fixed capacities"):
        apply_capacity_limit(n, "generators", ["fixed", "cheap"], "<=", 2)
    with pytest.raises(ValueError, match="fixed capacities"):
        apply_capacity_limit(
            n, "generators", ["fixed", "cheap"], ">=", 4, aggregate=False
        )
    pd.testing.assert_frame_equal(n.generators, original)
    assert META_KEY not in n.meta


def test_saved_capacity_limits_survive_netcdf_and_reject_missing_assets(tmp_path):
    n = investment_network()
    apply_capacity_limit(n, "generators", ["cheap", "expensive"], "<=", 5)
    path = tmp_path / "capacity.nc"
    n.export_to_netcdf(path)
    restored = pypsa.Network(path)
    assert restored.meta[META_KEY] == n.meta[META_KEY]
    assert solve(restored) == ("ok", "optimal")
    assert restored.generators.loc[
        ["cheap", "expensive"], "p_nom_opt"
    ].sum() == pytest.approx(5)
    restored.remove("Generator", "cheap")
    with pytest.raises(ValueError, match="missing"):
        validate_capacity_constraints(restored)


def aggregation_network():
    n = base_network(5)
    n.snapshot_weightings.loc[:, "generators"] = [1, 3, 2, 4, 0.5]
    n.snapshot_weightings.loc[:, "objective"] = [2, 6, 4, 8, 1]
    n.snapshot_weightings.loc[:, "stores"] = [0.5, 1.5, 1, 2, 0.25]
    n.add("Load", "static", bus="A", p_set=2)
    n.add("Load", "dynamic", bus="A", p_set=[1, 3, 5, 7, 9])
    n.add(
        "Generator",
        "generator",
        bus="A",
        p_nom=100,
        marginal_cost=10,
        p_max_pu=[0.5, 0.6, 0.7, 0.8, 0.9],
    )
    return n


def test_aggregation_preserves_energy_all_weights_and_last_partial_block():
    n = aggregation_network()
    original_weights = n.snapshot_weightings.sum()
    energy = float(load_timeseries(n).multiply(snapshot_weights(n), axis=0).sum().sum())
    availability = float(
        n.generators_t.p_max_pu.mul(snapshot_weights(n), axis=0).sum().sum()
    )
    assert solve(n) == ("ok", "optimal")
    original_objective = n.objective
    assert aggregate_snapshots(n, 2) == (5, 3)
    assert n.loads_t.p_set["dynamic"].tolist() == pytest.approx([2.5, 19 / 3, 9])
    pd.testing.assert_series_equal(n.snapshot_weightings.sum(), original_weights)
    assert n.snapshot_weightings.generators.tolist() == pytest.approx([4, 6, 0.5])
    assert float(
        load_timeseries(n).multiply(snapshot_weights(n), axis=0).sum().sum()
    ) == pytest.approx(energy)
    assert float(
        n.generators_t.p_max_pu.mul(snapshot_weights(n), axis=0).sum().sum()
    ) == pytest.approx(availability)
    assert not network_has_results(n)
    assert n._model is None and n._objective is None
    assert solve(n) == ("ok", "optimal")
    assert n.objective == pytest.approx(original_objective)


def test_aggregation_weights_storage_inflow_and_generator_fuel_coefficients():
    n = aggregation_network()
    n.add("StorageUnit", "reservoir", bus="A", p_nom=10, inflow=[1, 2, 3, 4, 5])
    n.generators_t.efficiency["generator"] = [0.2, 0.4, 0.5, 1, 0.8]
    inflow_energy = float(
        n.storage_units_t.inflow.mul(snapshot_weights(n, "stores"), axis=0).sum().sum()
    )
    assert aggregate_snapshots(n, 2) == (5, 3)
    assert float(
        n.storage_units_t.inflow.mul(snapshot_weights(n, "stores"), axis=0).sum().sum()
    ) == pytest.approx(inflow_energy)
    assert n.generators_t.efficiency.iloc[0, 0] == pytest.approx(
        4 / (1 / 0.2 + 3 / 0.4)
    )


def test_zero_weight_aggregation_block_and_noop():
    n = aggregation_network()
    n.snapshot_weightings.iloc[:2] = 0
    original = n.loads_t.p_set.copy()
    assert aggregate_snapshots(n, 1) == (5, 5)
    pd.testing.assert_frame_equal(n.loads_t.p_set, original)
    aggregate_snapshots(n, 2)
    assert n.snapshot_weightings.iloc[0].sum() == 0
    assert n.loads_t.p_set.iloc[0, 0] == pytest.approx(2)


def test_invalid_snapshot_weights_cannot_silently_change_energy():
    n = aggregation_network()
    n.snapshot_weightings.iloc[0, 0] = -1
    old_snapshots = n.snapshots.copy()
    with pytest.raises(ValueError, match="non-negative"):
        aggregate_snapshots(n, 2)
    assert n.snapshots.equals(old_snapshots)


@pytest.mark.parametrize(
    "unsupported",
    ["committable", "ramp_limit_up", "state_of_charge_set", "multi_period"],
)
def test_unsupported_aggregation_is_rejected_before_mutation(unsupported):
    n = aggregation_network()
    if unsupported == "committable":
        n.generators.loc[:, "committable"] = True
    elif unsupported == "ramp_limit_up":
        n.generators.loc[:, "ramp_limit_up"] = 0.2
    elif unsupported == "state_of_charge_set":
        n.add("StorageUnit", "battery", bus="A", state_of_charge_set=0)
    else:
        n.set_investment_periods([2030, 2040])
    snapshots, weights = n.snapshots.copy(), n.snapshot_weightings.copy()
    with pytest.raises(ValueError, match="support"):
        aggregate_snapshots(n, 2)
    assert n.snapshots.equals(snapshots)
    pd.testing.assert_frame_equal(n.snapshot_weightings, weights)


def test_preprocessing_copies_solved_network_and_clears_outputs_on_commit():
    n = investment_network()
    assert solve(n) == ("ok", "optimal")
    old_model = n.model
    candidate = copy_for_preprocessing(n)
    assert n.model is old_model and network_has_results(n)
    apply_capacity_limit(candidate, "generators", ["cheap"], "<=", 3)
    commit_preprocessing(n, candidate)
    assert n.meta[META_KEY]
    assert not network_has_results(n)
    assert solve(n) == ("ok", "optimal")
    assert n.generators.at["cheap", "p_nom_opt"] == pytest.approx(3)


def test_pre_run_ui_is_atomic_and_uses_correct_store_units(app, quiet_dialogs):
    n = aggregation_network()
    page = PreRunToolsPage()
    page.set_network(n)
    page.capacity_component_combo.setCurrentText("Stores")
    assert page.capacity_value_input.suffix() == " MWh"
    page.capacity_component_combo.setCurrentText("Generators")
    page.enable_load_shedding_checkbox.setChecked(True)
    page.enable_downsampling_checkbox.setChecked(True)
    n.generators.loc[:, "committable"] = True
    original = n.generators.copy(deep=True)
    page.apply_changes()
    QMessageBox.warning.assert_called_once()
    pd.testing.assert_frame_equal(n.generators, original)
    assert len(n.snapshots) == 5
    n.generators.loc[:, "committable"] = False
    assert page._estimate_bus_peak_load("A") == pytest.approx(11)
    page.close()


def test_pre_run_ui_marks_session_dirty_refreshes_and_clears_constraints(
    app, quiet_dialogs
):
    window = MainWindow()
    try:
        window._add_network_session(
            investment_network(),
            None,
            SessionViewOptions.from_workspace("full"),
            name="test",
        )
        session = window.active_session()
        session.is_modified = False
        page = window.central_panel.pages["Pre-Run Tools"]
        page.enable_capacity_checkbox.setChecked(True)
        page.capacity_mode_combo.setCurrentText("<=")
        page.capacity_value_input.setValue(8)
        page.apply_changes()
        assert session.is_modified
        assert session.network.meta[META_KEY][0]["value"] == 8
        assert solve(session.network) == ("ok", "optimal")
        page.clear_capacity_button.click()
        assert META_KEY not in session.network.meta
        assert not network_has_results(session.network)
        window.central_panel.set_optimisation_running(True)
        assert not page.isEnabled()
    finally:
        window.close()
