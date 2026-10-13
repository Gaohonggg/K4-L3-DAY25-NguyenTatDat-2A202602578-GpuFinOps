"""Verify running bonus services and save pushable HTTP/API evidence."""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from missions import m1_efficiency_audit


def fetch(url: str, authenticated: bool = False):
    headers = {}
    if authenticated:
        headers["Authorization"] = "Basic " + base64.b64encode(b"admin:admin").decode()
    with urlopen(Request(url, headers=headers), timeout=15) as response:
        return response.read().decode()


def main():
    metrics = fetch("http://127.0.0.1:9101/metrics")
    targets = json.loads(fetch("http://127.0.0.1:9090/api/v1/targets"))
    query = json.loads(fetch("http://127.0.0.1:9090/api/v1/query?query=gpu_mfu"))
    dashboard = json.loads(fetch("http://127.0.0.1:3300/api/dashboards/uid/gpu-cost-efficiency", True))
    health = json.loads(fetch("http://127.0.0.1:3300/api/health"))
    target = next(t for t in targets["data"]["activeTargets"] if t["labels"]["job"] == "gpu-cost-exporter")
    assert target["health"] == "up", target
    assert query["status"] == "success"
    values = {r["metric"]["gpu_id"]: float(r["value"][1]) for r in query["data"]["result"]}
    assert len(values) == 11
    for row in m1_efficiency_audit.run(False)["summary"]:
        assert abs(values[row["gpu_id"]] - row["mfu"]) <= 0.0006
    assert health["database"] == "ok"
    assert len(dashboard["dashboard"]["panels"]) == 5
    panel_results = {}
    for panel in dashboard["dashboard"]["panels"]:
        assert panel["datasource"]["uid"] == "gpu-cost-prometheus"
        expression = panel["targets"][0]["expr"]
        data = json.loads(fetch("http://127.0.0.1:9090/api/v1/query?" + urlencode({"query": expression})))
        assert data["status"] == "success" and len(data["data"]["result"]) == 11
        panel_results[panel["title"]] = len(data["data"]["result"])
    cost_panel = next(p for p in dashboard["dashboard"]["panels"] if p["type"] == "bargauge")
    assert cost_panel["targets"][0]["instant"] is True
    datasource = json.loads(fetch("http://127.0.0.1:3300/api/datasources/uid/gpu-cost-prometheus", True))
    assert datasource["url"] == "http://prometheus:9090"
    out = ROOT / "outputs"
    (out / "bonus_metrics.prom").write_text(metrics)
    evidence = {"exporter_gpu_count": len(values), "target": target,
                "prometheus_query": query, "grafana_health": health,
                "dashboard_uid": dashboard["dashboard"]["uid"],
                "panels": [p["title"] for p in dashboard["dashboard"]["panels"]],
                "panel_query_results": panel_results,
                "datasource_url": datasource["url"]}
    (out / "bonus_observability.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print("PASS: exporter 11 GPUs, Prometheus target up, MFU matches M1, Grafana database/dashboard/datasource OK")


if __name__ == "__main__":
    main()
