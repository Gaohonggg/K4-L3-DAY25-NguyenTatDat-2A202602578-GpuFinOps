"""Request-level scenario accounting shared by missions and allocation."""
from __future__ import annotations

from .pricing import request_cost, dollars_per_million
from .sustainability import wh_per_query

MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}
STAGES = ("baseline", "cascade", "cache", "batch")


def price_request(row: dict, stage: str = "batch", output_tokens: int | None = None) -> float:
    if stage not in STAGES:
        raise ValueError(f"Unknown inference stage: {stage}")
    inp = int(row["input_tokens"])
    out = int(row["output_tokens"]) if output_tokens is None else output_tokens
    tier = "large" if stage == "baseline" else row["route_tier"]
    pin, pout = MODEL_PRICES[tier]
    return request_cost(
        inp, out, pin, pout,
        cached_in=int(row["cached_input_tokens"]) if stage in ("cache", "batch") else 0,
        batch=stage == "batch" and bool(int(row["is_batch"])),
    )


def inference_analysis(rows: list[dict]) -> dict:
    totals = {stage: sum(price_request(r, stage) for r in rows) for stage in STAGES}
    tokens = sum(int(r["input_tokens"]) + int(r["output_tokens"]) for r in rows)
    stages = [{"stage": stage, "cost_usd": totals[stage],
               "per_m": dollars_per_million(totals[stage], tokens)} for stage in STAGES]
    savings = {name: totals[before] - totals[after] for name, before, after in (
        ("Cascade", "baseline", "cascade"), ("Cache", "cascade", "cache"),
        ("Batch", "cache", "batch"))}
    groups = []
    for reasoning in (False, True):
        subset = [r for r in rows if bool(int(r["is_reasoning"])) == reasoning]
        count_tokens = sum(int(r["input_tokens"]) + int(r["output_tokens"]) for r in subset)
        cost = sum(price_request(r) for r in subset)
        energy = sum(wh_per_query(int(r["input_tokens"]) + int(r["output_tokens"]),
                                  is_reasoning=reasoning) for r in subset)
        groups.append({"reasoning": reasoning, "requests": len(subset), "tokens": count_tokens,
                       "cost_usd": cost, "energy_wh": energy,
                       "per_m": dollars_per_million(cost, count_tokens)})
    # Controlled comparison: keep the same tokens and routing, remove only the energy multiplier.
    reasoning_rows = [r for r in rows if int(r["is_reasoning"])]
    same_tokens_wh = sum(wh_per_query(int(r["input_tokens"]) + int(r["output_tokens"]))
                         for r in reasoning_rows)
    scenarios = []
    original_energy = sum(g["energy_wh"] for g in groups)
    # Explicit synthetic counterfactual: generator multiplies reasoning output by six.
    # Keep expensive reasoning requests up to the cap; downgrade the remainder.
    ranked = sorted(reasoning_rows, key=lambda r: (-price_request(r), r["ts"]))
    for cap in (0.10, 0.05, 0.02):
        keep = min(len(ranked), int(len(rows) * cap))
        downgraded = ranked[keep:]
        saved_usd = saved_wh = 0.0
        removed_tokens = 0
        for r in downgraded:
            inp, out = int(r["input_tokens"]), int(r["output_tokens"])
            ordinary_out = out // 6
            removed_tokens += out - ordinary_out
            saved_usd += price_request(r) - price_request(r, output_tokens=ordinary_out)
            saved_wh += wh_per_query(inp + out, is_reasoning=True) - wh_per_query(inp + ordinary_out)
        scenarios.append({"cap": cap, "reasoning_requests": keep, "downgraded": len(downgraded),
                          "savings_usd": saved_usd, "savings_wh": saved_wh,
                          "cost_usd": totals["batch"] - saved_usd,
                          "energy_wh": original_energy - saved_wh,
                          "total_tokens": tokens - removed_tokens})
    return {"stages": stages, "lever_savings_daily": savings, "groups": groups,
            "total_tokens": tokens, "total_energy_wh": original_energy,
            "same_tokens_nonreasoning_wh": same_tokens_wh, "reasoning_scenarios": scenarios}
