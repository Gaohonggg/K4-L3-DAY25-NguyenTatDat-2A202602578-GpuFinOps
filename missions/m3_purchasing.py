"""M3 — Purchasing Strategy: break-even, tier choice, spot-checkpoint sim (deck §4).

Run: python missions/m3_purchasing.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num, catalog_by_type
from finops import pricing
from finops.scheduling import analyze_scheduling

DAYS = 30


def run(verbose: bool = True) -> dict:
    jobs = load_csv("workloads.csv")
    cat = catalog_by_type()
    on_demand_monthly = optimized_monthly = 0.0
    recs = []
    for j in jobs:
        gtype = j["gpu_type"]
        ngpu = int(num(j["num_gpus"]))
        hpd = num(j["hours_per_day"])
        interruptible = bool(int(num(j["interruptible"])))
        c = cat[gtype]
        gpu_hours = hpd * DAYS * ngpu
        od = num(c["on_demand_hr"])
        on_demand_cost = gpu_hours * od

        tier = pricing.recommend_tier(hpd, interruptible)
        if tier == "spot":
            sim = pricing.spot_checkpoint_cost(gpu_hours, num(c["spot_hr"]), od)
            opt_cost = sim["spot_cost"]
        elif tier == "reserved":
            # Monthly recurring scenario: pay all committed hours, including unused hours.
            opt_cost = 24 * DAYS * ngpu * num(c["reserved_3yr_hr"])
            if opt_cost >= on_demand_cost:
                tier = "on_demand"
                opt_cost = on_demand_cost
        else:
            opt_cost = on_demand_cost

        on_demand_monthly += on_demand_cost
        optimized_monthly += opt_cost
        recs.append({"job_id": j["job_id"], "gpu_type": gtype, "tier": tier,
                     "on_demand": on_demand_cost, "optimized": opt_cost,
                     "actual_gpu_hours": hpd * num(j["days"]) * ngpu,
                     "job_days": int(num(j["days"]))})

    savings = on_demand_monthly - optimized_monthly
    savings_pct = savings / on_demand_monthly * 100 if on_demand_monthly else 0.0

    scheduling = analyze_scheduling(jobs, cat)
    # Actual job-duration scenario: no new 1/3-year commitment justified by <=30 days alone.
    actual_baseline = actual_optimized = 0.0
    for j, rec in zip(jobs, recs):
        c = cat[j["gpu_type"]]
        hours = rec["actual_gpu_hours"]
        od = hours * num(c["on_demand_hr"])
        opt = pricing.spot_checkpoint_cost(hours, num(c["spot_hr"]), num(c["on_demand_hr"]))["spot_cost"] \
            if int(j["interruptible"]) else od
        actual_baseline += od
        actual_optimized += min(od, opt)
    actual = {"baseline_usd": actual_baseline, "optimized_usd": actual_optimized,
              "savings_pct": (1 - actual_optimized / actual_baseline) * 100}
    if verbose:
        print("== M3 Purchasing Strategy ==")
        print(f"break-even utilization @ 45% reserved discount = {pricing.break_even_utilization(0.45):.0%}")
        print(f"{'job':18}{'gpu':7}{'tier':11}{'on-demand':>12}{'optimized':>12}")
        for r in recs:
            print(f"{r['job_id']:18}{r['gpu_type']:7}{r['tier']:11}${r['on_demand']:>11,.2f}${r['optimized']:>11,.2f}")
        print(f"\nmonthly: on-demand ${on_demand_monthly:,.0f} -> optimized ${optimized_monthly:,.0f}  ({savings_pct:.1f}% saved)")
        print(f"Actual job durations (no new reserved commitment): ${actual_baseline:.2f} -> "
              f"${actual_optimized:.2f} ({actual['savings_pct']:.1f}% saved)")
        for r in scheduling["regions"]:
            print(f"  {r['region']:16}: ${r['usd_per_kwh']:.3f}/kWh, {r['g_per_kwh']} g/kWh; "
                  f"electricity=${r['electricity_usd']:.2f}; carbon={r['carbon_g']/1000:.3f} kg")
        print(f"Training carbon saved: {scheduling['carbon_saved_g']/1000:.3f} kg "
              f"({scheduling['carbon_savings_pct']:.2f}%); cleanest={scheduling['cleanest']}; "
              f"cheapest={scheduling['cheapest']}; balanced={scheduling['balanced']}")

    return {"recommendations": recs, "on_demand_monthly": round(on_demand_monthly),
            "optimized_monthly": round(optimized_monthly), "savings_pct": round(savings_pct, 1),
            "on_demand_monthly_exact": on_demand_monthly, "optimized_monthly_exact": optimized_monthly,
            "actual_duration": actual, "scheduling": scheduling}


if __name__ == "__main__":
    run()
