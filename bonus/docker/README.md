# Bonus — Prometheus + Grafana cost dashboard

The real observability stack (deck §10), wired to the lab's synthetic telemetry. A
tiny stdlib exporter turns telemetry into GPU **cost** metrics — including
`gpu_wasted_cost_usd_per_hr = (1 - MFU) * $/hr`, a FLOPs-based cost proxy.
It is not recoverable savings: memory-bound inference can have low MFU.

```bash
# from this folder:
docker compose up                       # Grafana: http://localhost:3300 (admin/admin)
#                                         Prometheus: http://localhost:9090
```

No Docker? The exporter is pure-Python:

```bash
python exporter.py                      # then: curl http://localhost:9101/metrics
```

Open the **"GPU Cost & Efficiency"** dashboard and compare *GPU-Util %* vs *MFU* — the
util-lie GPUs jump out. MBU and observed power provide additional context.

Verify the stack from the project root:

```bash
.venv/bin/python validation/verify_observability.py
```

Evidence: `outputs/bonus_observability.json`, `outputs/bonus_metrics.prom`, and
`outputs/grafana_dashboard.jpg`. Runtime logs stay in ignored `logs/`.
