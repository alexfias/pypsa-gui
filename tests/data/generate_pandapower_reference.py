"""Regenerate fixtures in a separate environment with pandapower==3.5.6.

Run this script there; the main GUI/test environment needs no pandapower.
"""

from pathlib import Path
import json
import pandapower as pp

out = Path(__file__).resolve().parent
net = pp.create_empty_network(
    name="Balanced import reference", f_hz=50, add_stdtypes=False
)
a = pp.create_bus(net, 110, name="Grid", index=10, geodata=(9.1, 55.1))
b = pp.create_bus(net, 110, name="Substation", index=20, geodata=(9.2, 55.2))
c = pp.create_bus(net, 20, name="Medium voltage", index=30, geodata=(9.3, 55.3))
d = pp.create_bus(net, 20, name="Demand", index=40, geodata=(9.4, 55.4))
e = pp.create_bus(net, 20, name="Demand", index=50, geodata=(9.4, 55.4))
pp.create_ext_grid(net, a, vm_pu=1.01, min_p_mw=-40, max_p_mw=40)
pp.create_gen(net, b, p_mw=4, vm_pu=1.015, min_p_mw=0, max_p_mw=20)
pp.create_sgen(net, d, p_mw=1, q_mvar=0.2, scaling=0.8)
pp.create_load(net, d, p_mw=12, q_mvar=2, scaling=0.9)
pp.create_load(net, e, p_mw=1, q_mvar=0.2)
pp.create_line_from_parameters(
    net,
    a,
    b,
    length_km=10,
    r_ohm_per_km=0.06,
    x_ohm_per_km=0.2,
    c_nf_per_km=8,
    g_us_per_km=0.01,
    max_i_ka=0.5,
    parallel=2,
    df=0.8,
    max_loading_percent=90,
)
pp.create_line_from_parameters(
    net,
    c,
    d,
    length_km=2,
    r_ohm_per_km=0.2,
    x_ohm_per_km=0.1,
    c_nf_per_km=20,
    max_i_ka=0.4,
)
pp.create_transformer_from_parameters(
    net,
    b,
    c,
    sn_mva=40,
    vn_hv_kv=110,
    vn_lv_kv=20,
    vk_percent=10,
    vkr_percent=0.5,
    pfe_kw=30,
    i0_percent=0.1,
    shift_degree=15,
    tap_side="hv",
    tap_neutral=0,
    tap_min=-4,
    tap_max=4,
    tap_step_percent=1.25,
    tap_pos=2,
    tap_changer_type="Ratio",
    parallel=2,
    df=0.9,
)
pp.create_shunt(net, c, q_mvar=-1, p_mw=0.02, step=2, max_step=3)
pp.create_switch(net, d, e, et="b", closed=True)
pp.create_poly_cost(net, 0, "gen", cp1_eur_per_mw=5)
reference = {"pandapower_version": pp.__version__, "cases": {}}
for side in ("hv", "lv"):
    net.trafo.loc[0, "tap_side"] = side
    pp.runpp(
        net,
        calculate_voltage_angles=True,
        init="flat",
        trafo_model="t",
        tolerance_mva=1e-10,
        numba=False,
    )
    reference["cases"][side] = {
        key: net[key].to_dict(orient="index")
        for key in ("res_bus", "res_line", "res_trafo", "res_ext_grid", "res_gen")
    }
net.trafo.loc[0, "tap_side"] = "hv"
pp.to_json(net, str(out / "pandapower_balanced.json"))
pp.to_excel(net, str(out / "pandapower_balanced.xlsx"), include_results=False)
(out / "pandapower_expected.json").write_text(json.dumps(reference, indent=2))
print("Generated pandapower", pp.__version__, "JSON, Excel and AC reference results.")
