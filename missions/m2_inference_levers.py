"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv
from finops import pricing
from finops.inference import MODEL_PRICES, inference_analysis



def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    analysis = inference_analysis(rows)
    base_cost = analysis["stages"][0]["cost_usd"]
    opt_cost = analysis["stages"][-1]["cost_usd"]
    total_tokens = analysis["total_tokens"]

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")
        for s in analysis["stages"]:
            print(f"  {s['stage']:8}: ${s['cost_usd']:.6f}/day; ${s['per_m']:.6f}/1M-token")
        for g in analysis["groups"]:
            print(f"  reasoning={g['reasoning']}: {g['requests']} requests, "
                  f"${g['cost_usd']:.6f}, {g['energy_wh']:.3f} Wh")
        for s in analysis["reasoning_scenarios"]:
            print(f"  reasoning cap={s['cap']:.0%}: downgrade {s['downgraded']} requests; "
                  f"save ${s['savings_usd']:.6f}/day and {s['savings_wh']:.3f} Wh/day")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "analysis": analysis, "baseline_daily_exact": base_cost, "optimized_daily_exact": opt_cost,
    }


if __name__ == "__main__":
    run()
