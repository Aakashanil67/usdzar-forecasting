"""
render_docs.py - Every number the documents quote, taken from the outputs.

README.md and docs/METHODOLOGY.md are rendered from docs/templates/*.tmpl by
replacing {{key}} with a value built here from data/processed/*.json (and the
raw series metadata). make_report.py and build_notebook.py import fill() and
KEYS; make_presentation.js reads data/processed/doc_keys.json, which this
script writes. A key that does not exist is an error, so a document cannot
quote a number that was not produced.

Run:  python src/render_docs.py
"""
import datetime as dt
import json
import re
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
PROC, RAW = BASE / "data" / "processed", BASE / "data" / "raw"
TEMPLATES = BASE / "docs" / "templates"

NICE = {"AR1_log": "AR(1), log level (benchmark)", "AR1_level": "AR(1), level",
        "AR1_log_roll": "AR(1), 5-year window", "AR1_log_vc": "AR(1), mean-corrected",
        "RW": "Random walk", "RW_drift": "Random walk with drift",
        "CARRY": "Carry", "RIDGE": "Ridge", "GBM": "Gradient boosting",
        "COMBO": "Combination", "EQUAL3": "Equal-weight RW + carry + ridge",
        "RW_CARRY": "Adaptive RW + carry", "RW_RIDGE": "Adaptive RW + ridge"}
ROW_ORDER = ["AR1_log", "AR1_level", "AR1_log_roll", "AR1_log_vc", "RW",
             "RW_drift", "CARRY", "RIDGE", "GBM", "COMBO", "EQUAL3",
             "RW_CARRY", "RW_RIDGE"]
CORE_FIVE = ["RW", "CARRY", "RIDGE", "GBM", "COMBO"]
RW_FAMILY = ["RW", "CARRY", "RIDGE", "COMBO", "EQUAL3", "RW_CARRY", "RW_RIDGE"]


def load(name):
    return json.loads((PROC / name).read_text(encoding="utf-8"))


def long_date(iso):
    d = dt.date.fromisoformat(str(iso)[:10])
    return f"{d.day} {d:%B %Y}"


def join_and(items):
    items = [str(i) for i in items]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def f(x, nd=4):
    return f"{x:.{nd}f}"


def sgn(x, nd=4):
    return f"{x:+.{nd}f}"


def md_table(rows, align=None):
    """rows[0] is the header. align is a string of l/r/c per column."""
    align = align or "l" + "r" * (len(rows[0]) - 1)
    rule = {"l": ":---", "r": "---:", "c": ":---:"}
    out = ["| " + " | ".join(rows[0]) + " |",
           "|" + "|".join(rule[a] for a in align) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(out)


def build_tables(met, tests, val, diag, timing):
    base = met["AR1_log"]["rmse"]
    by = {(c["model"], c["benchmark"]): c for c in tests["comparisons"]}
    order = sorted(ROW_ORDER, key=lambda m: met[m]["rmse"])
    rank = {m: i + 1 for i, m in enumerate(order)}

    results = [["Model", "RMSE", "MAE", "RMSE below AR(1)", "Rank", "Calls a rise"]]
    for m in ROW_ORDER:
        rel = "" if m == "AR1_log" else f"{100 * (1 - met[m]['rmse'] / base):+.2f}%"
        results.append([NICE[m], f(met[m]["rmse"]), f(met[m]["mae"]), rel,
                        str(rank[m]), f"{100 * met[m]['up_share']:.0f}%"])

    def dm_cells(m, b):
        c = by.get((m, b))
        if c is None:
            return ["-", "-", "-"]
        r = c["by_lag"]["3"]
        holm = f(c["p_holm"], 3) if "p_holm" in c else "n/a"
        return [f"{r['dm']:+.2f}", f(r["p"], 3), holm]

    dm = [["Model", "DM vs AR(1)", "p", "Holm p", "DM vs RW", "p", "Holm p"]]
    for m in ROW_ORDER:
        name = NICE[m] + (" (prespecified)" if m == "COMBO" else "")
        dm.append([name] + dm_cells(m, "AR1_log") + dm_cells(m, "RW"))

    plan = {}
    for b, tab in tests["planning"]["vs"].items():
        plan[b] = [["RMSE cut", "Origins needed", "Years of weekly origins",
                    f"Power with {tab['current_n']} origins"]]
        for r in tab["rows"]:
            plan[b].append([f"{r['rmse_reduction_pct']}%", f"{r['origins_needed']:,}",
                            f(r["years_of_weekly_origins"], 1),
                            f"{100 * r['power_at_current_n']:.0f}%"])

    years = [["Year", "AR(1)", "Random walk", "Combination", "Equal weights",
              "Lower of AR(1) and combination"]]
    for y, r in met["_yearly"].items():
        years.append([y, f(r["AR1_log"]), f(r["RW"]), f(r["COMBO"]), f(r["EQUAL3"]),
                      "Combination" if r["COMBO"] < r["AR1_log"] else "AR(1)"])

    ridge_note = {"f": "full set", "c": "compact set"}
    top = [["Ridge variant", "Decay", "Sharpness", "Validation RMSE"]]
    for g in val["grid"][:5]:
        tag = g["ridge"]
        top.append([f"{tag} ({ridge_note[tag[6]]}, "
                    f"{'no ' if tag.endswith('0') else ''}intercept)",
                    f(g["delta"], 2), f(g["theta"], 0), f(g["rmse"], 5)])

    tim = [["Model", "Base timing", "Predictors one week later", "Change"]]
    for m, v in timing["base"]["rmse"].items():
        e = timing["extra_week"]["rmse"][m]
        tim.append([NICE[m], f(v), f(e), sgn(e - v, 5)])

    ex = diag["worked_example"]
    by_forecast = sorted(ex["forecast"], key=ex["forecast"].get, reverse=True)
    worked = [["Model", "Forecast", "Error"]] + [
        [NICE[m], f(ex["forecast"][m]), sgn(ex["error"][m])] for m in by_forecast]

    w = diag["weights"]["by_year"]
    weights = [["Year", "Random walk, mean", "Carry, mean", "Ridge, mean",
                "Smallest weight", "Largest weight"]]
    for y, g in w.items():
        weights.append([y] + [f(g[m]["mean"], 3) for m in ("RW", "CARRY", "RIDGE")]
                       + [f(min(g[m]["min"] for m in g), 3),
                          f(max(g[m]["max"] for m in g), 3)])
    return dict(results=results, dm=dm, plan_rw=plan["RW"], plan_ar1=plan["AR1_log"],
                years=years, validation_top5=top, timing=tim, worked=worked,
                weights_by_year=weights)


def check_claims(met, tests, diag, ablation_gaps, rw_half_width):
    """The templates make qualitative statements around the numbers. Refuse to
    render if the outputs no longer support one of them."""
    by = {(c["model"], c["benchmark"]): c for c in tests["comparisons"]}
    wo = diag["weights"]["overall"]
    claims = {
        "gradient boosting has the highest RMSE of all models":
            max(met[m]["rmse"] for m in ROW_ORDER) == met["GBM"]["rmse"],
        "the AR(1) never forecasts a rise": met["AR1_log"]["up_share"] == 0,
        "the combination and carry forecast a rise at every origin":
            met["COMBO"]["up_share"] == 1 == met["CARRY"]["up_share"],
        "neither prespecified interval excludes zero":
            all(c["rmse_difference_ci95"][0] < 0 < c["rmse_difference_ci95"][1]
                for c in (by[("COMBO", "AR1_log")], by[("COMBO", "RW")])),
        "neither prespecified p-value is below 0.05":
            all(by[("COMBO", b)]["by_lag"]["3"]["p"] > 0.05 for b in ("AR1_log", "RW")),
        "no exploratory comparison survives the Holm adjustment":
            all(c["p_holm"] >= 0.05 for c in tests["comparisons"] if "p_holm" in c),
        "the ablation gaps are inside the interval half-width":
            max(ablation_gaps) < rw_half_width,
        "the weights stay within 0.1 of each other":
            max(v["max"] for v in wo.values()) - min(v["min"] for v in wo.values()) < 0.1,
        "component errors are almost perfectly correlated":
            diag["max_component_error_correlation"]["value"] > 0.99,
        "the AR(1)'s implied mean is below spot at every origin":
            diag["ar1_implied_mean"]["n_below_spot"] == diag["n"],
    }
    broken = [c for c, ok in claims.items() if not ok]
    if broken:
        raise SystemExit("templates assert claims the outputs no longer support: "
                         + "; ".join(broken))


def build_keys():
    met, tests = load("metrics.json"), load("statistical_tests.json")
    val, diag = load("validation_metrics.json"), load("diagnostics.json")
    timing, prov = load("timing_sensitivity.json"), load("provenance.json")
    log = pd.read_csv(PROC / "forecast_log.csv", parse_dates=["origin", "target_date"])
    weekly = pd.read_csv(PROC / "weekly.csv", parse_dates=["friday"])
    k = {}

    # ---- window, sample, provenance
    n = met["COMBO"]["n"]
    assert n == len(log) == diag["n"]
    k.update(n_origins=str(n), first_origin=long_date(log.origin.min()),
             last_origin=long_date(log.origin.max()),
             last_target=long_date(log.target_date.max()),
             n_targets_in_2025=str(int((log.target_date <= "2025-12-31").sum())),
             history_start_year=str(weekly.friday.min().year),
             econdata_n=f"{prov['econdata_observations']:,}",
             econdata_first=long_date(prov["econdata_first_date"]),
             overlap_n=f"{prov['overlapping_observations']:,}",
             overlap_max_diff=f(prov["max_abs_difference"], 6),
             overlap_mismatches=str(prov["mismatching_observations"]),
             window_overlap_n=f"{prov['forecast_window_observations']:,}",
             usd_broad_first_vintage=long_date(pd.read_csv(
                 RAW / "vintages" / "DTWEXBGS.csv")["realtime_start"].min()))

    # ---- accuracy, one block of keys per model
    for m in ROW_ORDER:
        k[f"rmse_{m.lower()}"] = f(met[m]["rmse"])
        k[f"mae_{m.lower()}"] = f(met[m]["mae"])
        k[f"strict_{m.lower()}"] = f(met["_targets_within_window"][m])
    ar1, combo, rw = (met[m]["rmse"] for m in ("AR1_log", "COMBO", "RW"))
    k["gain_vs_ar1"] = f(100 * (1 - combo / ar1), 2)
    k["gain_vs_rw"] = f(100 * (1 - combo / rw), 2)
    k["combo_minus_rw_rmse"] = f(abs(combo - rw), 5)
    k["rmse_spread_rw_family"] = f(max(met[m]["rmse"] for m in RW_FAMILY)
                                   - min(met[m]["rmse"] for m in RW_FAMILY), 5)
    k["equal3_vs_combo_gap"] = f(abs(met["EQUAL3"]["rmse"] - combo), 5)
    k["equal3_vs_combo_word"] = "lower" if met["EQUAL3"]["rmse"] < combo else "higher"
    k["n_beat_ar1"] = str(sum(met[m]["rmse"] < ar1 for m in CORE_FIVE))
    k["n_core_models"] = str(len(CORE_FIVE))
    k["gbm_worse_than_ar1_pct"] = f(100 * (met["GBM"]["rmse"] / ar1 - 1), 1)
    k["gbm_worse_than_rw_pct"] = f(100 * (met["GBM"]["rmse"] / rw - 1), 1)
    k["rw_rank"] = str(1 + sum(met[m]["rmse"] < rw for m in ROW_ORDER))
    k["combo_rank"] = str(1 + sum(met[m]["rmse"] < combo for m in ROW_ORDER))
    k["n_models"] = str(len(ROW_ORDER))
    k["n_rw_family"] = str(len(RW_FAMILY))
    abl = [abs(met[m]["rmse"] - combo) for m in ("EQUAL3", "RW_CARRY", "RW_RIDGE")]
    k["ablation_max_gap"] = f(max(abl), 5)
    k["rw_drift_up_pct"] = f(100 * met["RW_drift"]["up_share"], 0)

    ahead = [y for y, r in met["_yearly"].items() if r["COMBO"] < r["AR1_log"]]
    behind = [y for y in met["_yearly"] if y not in ahead]
    k.update(years_ahead_n=str(len(ahead)), years_n=str(len(met["_yearly"])),
             years_ahead=join_and(ahead), years_behind=join_and(behind) or "none",
             behind_year=behind[-1] if behind else "")
    if behind:
        y = behind[-1]
        k.update(behind_ar1=f(met["_yearly"][y]["AR1_log"]),
                 behind_combo=f(met["_yearly"][y]["COMBO"]),
                 behind_rw=f(met["_yearly"][y]["RW"]))

    # ---- tests
    by = {(c["model"], c["benchmark"]): c for c in tests["comparisons"]}
    for tag, b in (("ar1", "AR1_log"), ("rw", "RW")):
        c = by[("COMBO", b)]
        r3 = c["by_lag"]["3"]
        ps = [r["p"] for r in c["by_lag"].values()]
        k.update({f"dm_combo_{tag}": f"{r3['dm']:+.2f}",
                  f"p_combo_{tag}": f(r3["p"], 3),
                  f"ci_combo_{tag}_lo": sgn(r3["ci95"][0]),
                  f"ci_combo_{tag}_hi": sgn(r3["ci95"][1]),
                  f"rmse_ci_combo_{tag}_lo": sgn(c["rmse_difference_ci95"][0]),
                  f"rmse_ci_combo_{tag}_hi": sgn(c["rmse_difference_ci95"][1]),
                  f"rmse_diff_combo_{tag}": sgn(c["rmse_difference"], 5),
                  f"p_combo_{tag}_min": f(min(ps), 3), f"p_combo_{tag}_max": f(max(ps), 3),
                  f"auto_lag_{tag}": str(c["by_lag"]["auto"]["lag"])})
    fam = {frozenset((c["model"], c["benchmark"])): c for c in tests["comparisons"]
           if c["role"] == "exploratory"}
    lo, hi = by[("COMBO", "RW")]["rmse_difference_ci95"]
    k["rmse_ci_half_rw"] = f((hi - lo) / 2, 4)
    k["n_exploratory"] = str(tests["exploratory_family_size"])
    assert len(fam) == tests["exploratory_family_size"]
    k["n_exploratory_unadjusted"] = str(sum(c["by_lag"]["3"]["p"] < 0.05
                                            for c in fam.values()))
    k["min_holm_p"] = f(min(c["p_holm"] for c in fam.values()), 3)
    k["n_holm_significant"] = str(sum(c["p_holm"] < 0.05 for c in fam.values()))
    k["gbm_p_vs_ar1"] = f(by[("GBM", "AR1_log")]["by_lag"]["3"]["p"], 3)
    k["gbm_p_vs_rw"] = f(by[("GBM", "RW")]["by_lag"]["3"]["p"], 3)
    ro = tests["rolling"]
    k.update(roll_share=f(100 * ro["share_of_windows_ahead_of_benchmark"], 1),
             roll_best=f(ro["best_window_ratio"]), roll_worst=f(ro["worst_window_ratio"]),
             roll_windows=str(ro["n_complete_windows"]), roll_weeks=str(ro["window_weeks"]))

    # ---- planning table
    for b, tag in (("RW", "rw"), ("AR1_log", "ar1")):
        tab = tests["planning"]["vs"][b]
        k[f"plan_{tag}_sd"] = f(tab["assumed_sd_loss_differential"])
        k[f"plan_{tag}_mse"] = f(tab["assumed_benchmark_mse"])
        for r in tab["rows"]:
            c = r["rmse_reduction_pct"]
            k[f"plan_{tag}_{c}_n"] = f"{r['origins_needed']:,}"
            k[f"plan_{tag}_{c}_years"] = f(r["years_of_weekly_origins"], 1)
            k[f"plan_{tag}_{c}_power"] = f"{100 * r['power_at_current_n']:.0f}"
    k["planning_assumptions"] = "\n".join(f"- {a}" for a in tests["planning"]["assumptions"])

    # ---- diagnostics
    acc, dev = diag["accuracy"], diag["deviation_from_spot"]
    k["realized_up_pct"] = f(100 * diag["realized_up_share"], 1)
    k["combo_up_pct"] = f(100 * acc["COMBO"]["up_share"], 0)
    k["combo_dir_acc_pct"] = f(100 * acc["COMBO"]["dir_acc"], 1)
    k["ar1_up_pct"] = f(100 * acc["AR1_log"]["up_share"], 0)
    k["ar1_mean_dev_pct"] = f(dev["AR1_log"]["mean_pct"], 3)
    k["combo_mean_abs_dev_pct"] = f(dev["COMBO"]["mean_abs_pct"], 3)
    k["ar1_bias"] = sgn(acc["AR1_log"]["bias"])
    k["combo_bias"] = sgn(acc["COMBO"]["bias"])
    k["rw_bias"] = sgn(acc["RW"]["bias"])
    k["ar1_bias_share_pct"] = f(100 * acc["AR1_log"]["bias_sq_share_of_mse"], 2)
    k["combo_bias_share_pct"] = f(100 * acc["COMBO"]["bias_sq_share_of_mse"], 2)
    mse_gap = ar1 ** 2 - combo ** 2
    k["bias_share_of_gap_pct"] = f(100 * (acc["AR1_log"]["bias_sq"]
                                          - acc["COMBO"]["bias_sq"]) / mse_gap, 0)
    k["mse_gap"] = f(mse_gap, 5)
    mc = diag["max_component_error_correlation"]
    k["max_err_corr"] = f(mc["value"], 5)
    k["max_err_corr_pair"] = f"{NICE[mc['pair'][0]].lower()} and {NICE[mc['pair'][1]].lower()}"
    k["gbm_err_corr_min"] = f(min(diag["error_correlation"]["GBM"][m]
                                  for m in ("AR1_log", "RW", "CARRY", "RIDGE")), 2)
    wo = diag["weights"]["overall"]
    k["w_min"] = f(min(v["min"] for v in wo.values()), 3)
    k["w_max"] = f(max(v["max"] for v in wo.values()), 3)
    for m, v in wo.items():
        k[f"w_mean_{m.lower()}"] = f(v["mean"], 3)
    mech = diag["ar1_implied_mean"]
    k.update(phi_min=f(mech["phi_min"]), phi_max=f(mech["phi_max"]),
             one_minus_phi_min=f(1 - mech["phi_max"]), one_minus_phi_max=f(1 - mech["phi_min"]),
             mu_min=f(mech["mu_min"], 2), mu_max=f(mech["mu_max"], 2),
             n_below_spot=str(mech["n_below_spot"]), mean_gap=f(mech["mean_gap"], 2),
             min_gap=f(mech["min_gap"], 2), spot_first=f(mech["spot_first"], 2),
             spot_peak=f(mech["spot_peak"], 2))
    cs = diag["cumulative_se"]
    k.update(cum_peak=f(cs["peak"], 2), cum_peak_date=long_date(cs["peak_origin"]),
             cum_final=f(cs["final"], 2))
    for y, v in cs["end_of_year"].items():
        k[f"cum_end_{y}"] = f(v, 2)

    ex = diag["worked_example"]
    fc = ex["forecast"]
    k.update(ex_origin=long_date(ex["origin"]), ex_target=long_date(ex["target_date"]),
             ex_spot=f(ex["spot"]), ex_realized=f(ex["realized"]),
             ex_carry_diff=f(ex["carry_diff"]),
             ex_carry_scaled=f(ex["carry_diff"] * 28 / 365),
             ex_forecast_low=f(min(fc.values()), 3), ex_forecast_high=f(max(fc.values()), 3),
             ex_spread_cents=f(100 * (max(fc.values()) - min(fc.values())), 0),
             ex_move_cents=f(100 * abs(ex["realized"] - ex["spot"]), 0),
             ex_ar1_mu=f(ex["ar1"]["mu"], 2), ex_ar1_phi=f(ex["ar1"]["phi"], 6),
             ex_ar1_c=f(ex["ar1"]["c"], 6), ex_ar1_n=f"{ex['ar1']['n_obs']:,}",
             ex_half_life=f(ex["ar1"]["half_life_weeks"], 0),
             ex_spot_short=f(ex["spot"], 2))
    for m, v in fc.items():
        k[f"ex_fc_{m.lower()}"] = f(v)
        k[f"ex_err_{m.lower()}"] = sgn(ex["error"][m])
    for m, v in ex["weights"].items():
        k[f"ex_w_{m.lower()}"] = f(v, 3)
    k["ex_worst_model"] = NICE[max(ex["error"], key=lambda m: abs(ex["error"][m]))]
    k["ex_all_too_low"] = ("Every model forecast too low"
                           if all(v < 0 for v in ex["error"].values()) else
                           "The forecasts missed in both directions")

    # ---- selection on the validation era
    vw, cfg = val["validation_window"], val["chosen_config"]
    ve = val["validation_era"]
    k.update(val_first=long_date(vw["first_origin"]), val_last=long_date(vw["last_origin"]),
             val_last_target=long_date(vw["last_target"]),
             val_n=str(ve["COMBO"]["n"]), n_grid=str(len(val["grid"])),
             chosen_delta=f(cfg["delta"], 2), chosen_theta=f(cfg["theta"], 0),
             chosen_ridge_tag=cfg["ridge"],
             chosen_ridge_desc=("the full predictor set" if cfg["ridge"][6] == "f"
                                else "the compact predictor set")
             + (", no intercept" if cfg["ridge"].endswith("0") else ", with intercept"),
             val_rmse_combo=f(ve["COMBO"]["rmse"]), val_rmse_ar1=f(ve["AR1_log"]["rmse"]),
             val_rmse_rw=f(ve["RW"]["rmse"]),
             val_top5_gap=f(val["grid"][4]["rmse"] - val["grid"][0]["rmse"], 5),
             val_grid_spread=f(val["grid"][-1]["rmse"] - val["grid"][0]["rmse"], 5),
             gbm_grid_n=str(len(val["gbm"]["grid"])),
             gbm_retune_every=str(val["gbm"]["retune_every"]),
             gbm_cv_folds=str(val["gbm"]["cv_folds"]),
             gbm_n_retunes=str(len(val["gbm"]["trials"])),
             gbm_configs_in_force=str(len(val["gbm"]["judged_origins_by_config"])))

    # ---- timing sensitivity
    tb, te = timing["base"]["rmse"], timing["extra_week"]["rmse"]
    k.update(timing_combo_base=f(tb["COMBO"]), timing_combo_extra=f(te["COMBO"]),
             timing_gbm_base=f(tb["GBM"]), timing_gbm_extra=f(te["GBM"]),
             timing_gbm_change=f(abs(te["GBM"] - tb["GBM"])),
             timing_max_other_change=f(max(abs(te[m] - tb[m]) for m in tb
                                           if m != "GBM"), 5),
             timing_extra_chosen_same=("the same configuration"
                                       if timing["extra_week"]["chosen"] == timing["base"]["chosen"]
                                       else "a different configuration"))

    check_claims(met, tests, diag, abl, (hi - lo) / 2)
    tables = build_tables(met, tests, val, diag, timing)
    for name, rows in tables.items():
        k[f"table_{name}"] = md_table(rows, "l" + "r" * (len(rows[0]) - 1))
    return k, tables


KEYS, TABLES = build_keys()
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def fill(text, keys=None):
    """Replace every {{key}}; an unknown key raises."""
    keys = keys or KEYS
    return _PLACEHOLDER.sub(lambda m: keys[m.group(1)], text)


def render(template: Path) -> str:
    return fill(template.read_text(encoding="utf-8"))


OUTPUTS = {"README.md.tmpl": BASE / "README.md",
           "METHODOLOGY.md.tmpl": BASE / "docs" / "METHODOLOGY.md"}


def main() -> None:
    for tmpl, out in OUTPUTS.items():
        out.write_text(render(TEMPLATES / tmpl), encoding="utf-8", newline="\n")
        print("written:", out.relative_to(BASE))
    (PROC / "doc_keys.json").write_text(
        json.dumps({"keys": KEYS, "tables": TABLES}, indent=1, ensure_ascii=False,
                   sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print("written: data/processed/doc_keys.json")


if __name__ == "__main__":
    main()
