"""Capacity-constrained screening of inference GPU replacements."""
from __future__ import annotations

from collections import defaultdict


def analyze_rightsizing(telemetry: list[dict], catalog: dict,
                       bandwidth_target: float = 0.75, compute_target: float = 0.50,
                       memory_headroom: float = 1.15, days: int = 30) -> dict:
    """Screen candidates using observed peaks; recommendations require a benchmark."""
    if not (0 < bandwidth_target <= 1 and 0 < compute_target <= 1):
        raise ValueError("Capacity targets must be in (0, 1]")
    if memory_headroom < 1 or days <= 0:
        raise ValueError("Memory headroom must be >=1 and days must be positive")
    groups = defaultdict(list)
    for row in telemetry:
        if row["workload"] == "infer":
            groups[row["gpu_id"]].append(row)
    catalog_metrics = [{"gpu_type": name,
                        "usd_per_gb_hour": float(c["on_demand_hr"]) / float(c["hbm_gb"]),
                        "peak_bw_tbs": float(c["peak_bw_tbs"])} for name, c in catalog.items()]
    recommendations = []
    for gid, samples in sorted(groups.items()):
        current = samples[0]["gpu_type"]
        c = catalog[current]
        bw = max(float(r["achieved_bw_tbs"]) for r in samples)
        flops = max(float(r["achieved_tflops"]) for r in samples)
        memory = max(float(r["mem_used_gb"]) for r in samples) * memory_headroom
        avg_bw = sum(float(r["achieved_bw_tbs"]) for r in samples) / len(samples)
        avg_flops = sum(float(r["achieved_tflops"]) for r in samples) / len(samples)
        intensity = avg_flops / avg_bw if avg_bw else float("inf")
        ridge = float(c["peak_tflops_fp16"]) / float(c["peak_bw_tbs"])
        memory_bound = intensity < ridge
        mbu = avg_bw / float(c["peak_bw_tbs"])
        candidates = []
        if memory_bound and mbu < bandwidth_target:
            for name, target in catalog.items():
                if (float(target["on_demand_hr"]) < float(c["on_demand_hr"])
                        and float(target["hbm_gb"]) >= memory
                        and float(target["peak_bw_tbs"]) * bandwidth_target >= bw
                        and float(target["peak_tflops_fp16"]) * compute_target >= flops):
                    candidates.append(name)
        target = min(candidates, key=lambda n: float(catalog[n]["on_demand_hr"])) if candidates else current
        rate = float(c["on_demand_hr"])
        target_rate = float(catalog[target]["on_demand_hr"])
        recommendations.append({"gpu_id": gid, "current": current, "target": target,
                                "memory_bound": memory_bound, "mbu": mbu,
                                "required_vram_gb": memory, "required_bw_tbs": bw,
                                "required_tflops": flops,
                                "current_bw_tbs": float(c["peak_bw_tbs"]),
                                "target_bw_tbs": float(catalog[target]["peak_bw_tbs"]),
                                "current_usd_per_gb_hour": rate / float(c["hbm_gb"]),
                                "target_usd_per_gb_hour": target_rate / float(catalog[target]["hbm_gb"]),
                                "savings_pct": (1 - target_rate / rate) * 100,
                                "monthly_savings_usd": (rate - target_rate) * 24 * days,
                                "reason": "Meets VRAM, bandwidth and compute constraints" if candidates else
                                "No cheaper candidate satisfies all screening constraints"})
    return {"catalog": catalog_metrics, "recommendations": recommendations,
            "monthly_savings_usd": sum(r["monthly_savings_usd"] for r in recommendations),
            "bandwidth_target": bandwidth_target, "compute_target": compute_target,
            "memory_headroom": memory_headroom}
