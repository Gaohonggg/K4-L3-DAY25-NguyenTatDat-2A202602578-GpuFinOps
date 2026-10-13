"""Demo: per-key $/request tracking + a hard budget stop. Run: python demo.py"""
from tracker import CostTracker, BudgetExceeded
import json
from pathlib import Path

t = CostTracker(budgets={"team-chat": 0.05, "team-eval": 100.0})
for i in range(40):
    try:
        t.complete("team-chat", "large", "Summarize this very long document " * 30)
    except BudgetExceeded as e:
        print(f"BLOCKED after {i} chat requests: {e}")
        break
for i in range(5):
    t.complete("team-eval", "small", "classify: positive or negative?", batch=True)

print("\nper-key spend:", t.report())
print("requests logged:", len(t.log))
evidence = {"backend": "mock", "budgets_usd": t.budgets,
            "spend_usd": dict(t.spend), "accepted_requests": len(t.log),
            "blocked_key": "team-chat",
            "requests": t.log}
# Use the accepted chat count; the eval loop reuses i.
evidence["blocked_after_requests"] = sum(r["key"] == "team-chat" for r in t.log)
out = Path(__file__).resolve().parents[2] / "outputs" / "bonus_tracker.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
print("Evidence:", out)
