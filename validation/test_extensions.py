"""Additional accounting and capacity checks; instructor tests remain unchanged."""
import csv
import importlib.util
from pathlib import Path

import pytest

from finops.inference import inference_analysis, price_request
from finops.rightsizing import analyze_rightsizing
from finops.scheduling import analyze_scheduling
from missions._common import ROOT, catalog_by_type, load_csv
from missions import m1_efficiency_audit, m2_inference_levers, m3_purchasing, m4_allocation, m5_report


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, Path(ROOT) / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inference_levers_reconcile_and_token_denominator_is_fixed():
    a = inference_analysis(load_csv("token_usage.csv"))
    stages = [r["cost_usd"] for r in a["stages"]]
    assert stages == sorted(stages, reverse=True)
    assert sum(a["lever_savings_daily"].values()) == pytest.approx(stages[0] - stages[-1])
    assert sum(g["cost_usd"] for g in a["groups"]) == pytest.approx(stages[-1])
    assert sum(g["tokens"] for g in a["groups"]) == a["total_tokens"]


def test_reasoning_cap_above_current_traffic_is_noop():
    a = inference_analysis(load_csv("token_usage.csv"))
    cap = a["reasoning_scenarios"][0]
    assert cap["downgraded"] == 0
    assert cap["savings_usd"] == cap["savings_wh"] == 0
    assert cap["total_tokens"] == a["total_tokens"]


def test_reasoning_controlled_comparison_and_caps():
    a = inference_analysis(load_csv("token_usage.csv"))
    assert a["groups"][1]["energy_wh"] == pytest.approx(a["same_tokens_nonreasoning_wh"] * 80)
    assert a["reasoning_scenarios"][2]["savings_wh"] > a["reasoning_scenarios"][1]["savings_wh"] > 0
    row = load_csv("token_usage.csv")[0]
    assert price_request(dict(row, is_reasoning="1")) == price_request(dict(row, is_reasoning="0"))


def test_rightsizing_never_violates_capacity_constraints():
    cat = catalog_by_type()
    a = analyze_rightsizing(load_csv("gpu_telemetry.csv"), cat)
    for r in a["recommendations"]:
        if r["target"] == r["current"]:
            continue
        c = cat[r["target"]]
        assert float(c["hbm_gb"]) >= r["required_vram_gb"]
        assert float(c["peak_bw_tbs"]) * a["bandwidth_target"] >= r["required_bw_tbs"]
        assert float(c["peak_tflops_fp16"]) * a["compute_target"] >= r["required_tflops"]
        assert r["savings_pct"] > 0


def test_large_memory_footprint_blocks_cheap_gpu():
    cat = catalog_by_type()
    tel = [{"gpu_id": "large-memory", "gpu_type": "A100", "workload": "infer",
            "achieved_bw_tbs": "0.3", "achieved_tflops": "20", "mem_used_gb": "75"}]
    a = analyze_rightsizing(tel, cat)
    assert a["recommendations"][0]["target"] == "A100"
    assert a["monthly_savings_usd"] == 0


def test_reserved_bills_idle_commitment_hours():
    result = m3_purchasing.run(False)
    search = next(r for r in result["recommendations"] if r["job_id"] == "job-infer-search")
    assert search["optimized"] == pytest.approx(24 * 30 * 4 * 0.45)
    assert search["actual_gpu_hours"] == 18 * 30 * 4
    assert result["actual_duration"]["optimized_usd"] < result["actual_duration"]["baseline_usd"]


def test_scheduling_uses_job_days_and_excludes_nontraining():
    a = analyze_scheduling(load_csv("workloads.csv"), catalog_by_type())
    assert len(a["jobs"]) == 3
    assert a["total_energy_wh"] == pytest.approx(1673.2 * 1000)
    assert a["carbon_saved_g"] == pytest.approx(585620)
    assert a["cheapest"] != a["cleanest"]


def test_allocation_export_reconciles_with_inference():
    m2 = m2_inference_levers.run(False)
    m4 = m4_allocation.run(False)
    assert m4["total_cost_usd"] == pytest.approx(m2["optimized_daily_exact"])
    with open(Path(ROOT) / "outputs/focus_export.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2400
    billed = sum(float(r["BilledCost"]) for r in rows)
    assert abs(billed - m4["total_cost_usd"]) <= len(rows) * 0.00005


def test_report_excludes_overlapping_fleet_opportunities():
    result = m5_report.run(False)
    assert result["levers"]["Right-sizing"] == result["levers"]["Idle shutdown"] == 0
    assert result["baseline_monthly"] - result["optimized_monthly"] == pytest.approx(sum(result["levers"].values()))


def test_tracker_rejection_preserves_spend_and_log():
    tracker = load_module("tracker_check", "bonus/litellm_tracker/tracker.py")
    t = tracker.CostTracker({"key": 0.005})
    t.complete("key", "large", "test")
    old_spend, old_len = t.spend["key"], len(t.log)
    with pytest.raises(tracker.BudgetExceeded):
        t.complete("key", "large", "test")
    assert t.spend["key"] == old_spend and len(t.log) == old_len
    t.complete("other", "small", "test", batch=True)
    assert t.spend["key"] == old_spend


def test_tracker_exact_budget_boundary_and_invalid_inputs():
    tracker = load_module("tracker_boundary", "bonus/litellm_tracker/tracker.py")
    cost = price_request({"input_tokens": "1", "output_tokens": "256", "route_tier": "large",
                          "cached_input_tokens": "0", "is_batch": "0"})
    t = tracker.CostTracker({"key": cost})
    t.complete("key", "large", "test")
    assert t.spend["key"] == cost
    with pytest.raises(ValueError):
        t.complete("key", "large", "test", max_output_tokens=-1)


def test_exporter_matches_mission_mfu():
    exporter = load_module("exporter_check", "bonus/docker/exporter.py")
    text = exporter.render()
    summary = m1_efficiency_audit.run(False)["summary"]
    for r in summary:
        prefix = f'gpu_mfu{{gpu_id="{r["gpu_id"]}",gpu_type="{r["gpu_type"]}"}} '
        line = next(line for line in text.splitlines() if line.startswith(prefix))
        assert float(line.split()[-1]) == pytest.approx(r["mfu"], abs=0.0006)
    assert text.count("\ngpu_power_w{") == 11
