"""Carbon and electricity scenarios for interruptible training jobs."""
from __future__ import annotations

from .sustainability import REGION_CARBON, REGION_PRICE_KWH, carbon_g, energy_cost_usd


def analyze_scheduling(jobs: list[dict], catalog: dict, source: str = "us-east-1") -> dict:
    cleanest = min(REGION_CARBON, key=REGION_CARBON.get)
    cheapest = min(REGION_PRICE_KWH, key=REGION_PRICE_KWH.get)
    results = []
    for job in jobs:
        if job["kind"] != "train" or not int(job["interruptible"]):
            continue
        gpu_hours = float(job["hours_per_day"]) * int(job["days"]) * int(job["num_gpus"])
        wh = gpu_hours * float(catalog[job["gpu_type"]]["watts"])
        results.append({"job_id": job["job_id"], "gpu_hours": gpu_hours, "energy_wh": wh,
                        "source_carbon_g": carbon_g(wh, source),
                        "clean_carbon_g": carbon_g(wh, cleanest),
                        "carbon_saved_g": carbon_g(wh, source) - carbon_g(wh, cleanest)})
    total_wh = sum(r["energy_wh"] for r in results)
    regions = [{"region": region, "usd_per_kwh": REGION_PRICE_KWH[region],
                "g_per_kwh": intensity, "energy_kwh": total_wh / 1000,
                "electricity_usd": energy_cost_usd(total_wh, region),
                "carbon_g": carbon_g(total_wh, region)} for region, intensity in REGION_CARBON.items()]
    # Equal weights on normalized electricity and carbon costs; explicit policy choice.
    min_price, min_carbon = REGION_PRICE_KWH[cheapest], REGION_CARBON[cleanest]
    balanced = min(regions, key=lambda r: 0.5 * r["usd_per_kwh"] / min_price
                   + 0.5 * r["g_per_kwh"] / min_carbon)["region"]
    return {"jobs": results, "regions": regions, "source": source, "cleanest": cleanest,
            "cheapest": cheapest, "balanced": balanced, "total_energy_wh": total_wh,
            "carbon_saved_g": sum(r["carbon_saved_g"] for r in results),
            "carbon_savings_pct": (1 - REGION_CARBON[cleanest] / REGION_CARBON[source]) * 100}
