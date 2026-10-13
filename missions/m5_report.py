"""M5 — reproducible report, write-up and evidence from mission results."""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import json
from pathlib import Path
from missions._common import ROOT, load_csv, catalog_by_type
from finops import report, sustainability
from finops.rightsizing import analyze_rightsizing
from missions import m1_efficiency_audit, m2_inference_levers, m3_purchasing, m4_allocation

DAYS = 30


def table(headers: list[str], rows: list[list]) -> str:
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join("---" for _ in headers) + " |"] +
                     ["| " + " | ".join(str(v) for v in row) + " |" for row in rows])


def run(verbose: bool = True) -> dict:
    r1 = m1_efficiency_audit.run(verbose=False)
    r2 = m2_inference_levers.run(verbose=False)
    r3 = m3_purchasing.run(verbose=False)
    r4 = m4_allocation.run(verbose=False)
    a = r2["analysis"]
    infer_saved = (r2["baseline_daily_exact"] - r2["optimized_daily_exact"]) * DAYS
    purchase_saved = r3["on_demand_monthly_exact"] - r3["optimized_monthly_exact"]
    # No fleet-to-job mapping exists: exclude overlapping telemetry opportunities.
    levers = {"Inference": infer_saved, "Purchasing": purchase_saved,
              "Right-sizing": 0.0, "Idle shutdown": 0.0}
    baseline = r2["baseline_daily_exact"] * DAYS + r3["on_demand_monthly_exact"]
    optimized = baseline - sum(levers.values())
    total_pct = sum(levers.values()) / baseline * 100
    sched, size = r3["scheduling"], r1["rightsizing"]
    strict = analyze_rightsizing(load_csv("gpu_telemetry.csv"), catalog_by_type(), bandwidth_target=0.60)
    reasoning = a["groups"][1]
    n = sum(g["requests"] for g in a["groups"])
    traffic_pct = reasoning["requests"] / n * 100
    cost_pct = reasoning["cost_usd"] / r2["optimized_daily_exact"] * 100
    energy_pct = reasoning["energy_wh"] / a["total_energy_wh"] * 100
    wh = a["total_energy_wh"] / n
    sust = {"wh_per_query": wh, "carbon_g": sustainability.carbon_g(wh),
            "best_region": sched["cleanest"]}
    sections = [report.build_report(baseline, optimized, levers, sust,
                                   period="30-day recurring simulation (June 2026 prices)"),
        "## Phạm vi và phương pháp\n\n"
        "Dataset seed=25 gồm 264 bản ghi telemetry, 11 GPU, 2.400 requests/ngày và 8 workloads. "
        "Tổng tháng của lab giả định hai ngân sách độc lập: token API và GPU workloads. "
        "Nếu hai nguồn phí phục vụ cùng một dịch vụ, cần đối soát billing trước khi cộng. "
        "Telemetry không có khóa GPU → job; savings idle và right-sizing được báo cáo riêng, không cộng vào purchasing. "
        "Các cột $0 trong waterfall thể hiện cơ hội chưa đưa vào tổng. Giá và năng lượng là giả định của repo.",
        "## M2 — Baseline, optimized và từng lever\n\n"
        f"Mẫu số cố định: {r2['total_tokens']:,} input + output tokens/ngày, bao gồm cached input. "
        "Đo tuần tự baseline → cascade → cache → batch; thứ tự ảnh hưởng phần đóng góp từng lever.\n\n" +
        table(["Kịch bản", "USD/ngày", "USD/1M-token"],
              [[s["stage"], f"{s['cost_usd']:.6f}", f"{s['per_m']:.6f}"] for s in a["stages"]]) + "\n\n" +
        table(["Lever", "Savings USD/ngày", "Savings USD/30 ngày"],
              [[k, f"{v:.6f}", f"{v*DAYS:.2f}"] for k, v in a["lever_savings_daily"].items()]) +
        f"\n\nInference giảm {r2['savings_pct']:.1f}%. Cascade đóng góp lớn nhất trong inference vì chính sách "
        "generator định tuyến phần lớn requests sang model nhỏ. Cache giảm phần cached input; batch giảm cả request. "
        "0,5 × 0,1 = 0,05 chỉ đúng cho phần input cache hoàn toàn, không đúng cho mọi request có output. "
        "Batch phù hợp eval bất đồng bộ; không áp dụng cho chat cần phản hồi ngay.\n\n" +
        table(["Ngân sách tháng", "Baseline USD", "Optimized USD", "USD/1M-token trước", "USD/1M-token sau"], [
            ["Token API", f"{r2['baseline_daily_exact']*DAYS:.2f}", f"{r2['optimized_daily_exact']*DAYS:.2f}",
             r2["baseline_per_m"], r2["optimized_per_m"]],
            ["GPU workloads", f"{r3['on_demand_monthly_exact']:.2f}", f"{r3['optimized_monthly_exact']:.2f}", "N/A", "N/A"]]) +
        "\n\nKhông chia tiền training/dev cho token inference vì thiếu sản lượng token tương ứng.",
        "## M1 — GPU-Util lie và idle\n\n" +
        table(["GPU", "GPU-Util %", "MFU", "MBU"],
              [[r["gpu_id"], r["gpu_util_pct"], r["mfu"], r["mbu"]] for r in r1["lies"]]) +
        "\n\nGPU-Util đo thời gian có kernel hoạt động; MFU đo achieved/peak FLOPs. Kernel ít phép toán, "
        "memory stall hoặc overhead có thể giữ GPU bận nhưng FLOPs thấp. Telemetry tổng hợp chưa đủ để kết luận "
        "nguyên nhân riêng. Decode memory-bound có thể có MFU thấp hợp lý; cần xét MBU và roofline trước khi thay GPU. "
        f"gpu-h100-5 có 8 giờ idle: 8 × $2,50 = ${r1['idle_waste_daily']:.2f}/ngày, "
        f"${r1['idle_waste_daily']*DAYS:.2f}/30 ngày. Đây là cơ hội từ telemetry, chưa trừ vào bill M3.",
        "## M3 — Purchasing và thời hạn cam kết\n\n" +
        table(["Job", "GPU", "Tier", "On-demand USD/30 ngày", "Optimized USD/30 ngày"],
              [[r["job_id"], r["gpu_type"], r["tier"], f"{r['on_demand']:.2f}", f"{r['optimized']:.2f}"]
               for r in r3["recommendations"]]) +
        f"\n\nPurchasing giảm {r3['savings_pct']:.1f}%. Spot giả định interruption 0,05/giờ, "
        "checkpoint overhead 3%, rework 0,5 giờ/lần: effective hours = job hours × 1,055. "
        "Reserved trả đủ 24 giờ/ngày, kể cả giờ bỏ trống; L4 search hoạt động 18 giờ/ngày vẫn trả $1.296/tháng. "
        "Kịch bản tháng giả định pool có nhu cầu dài hạn đủ thời hạn cam kết; ngưỡng 55% của policy chỉ là xấp xỉ, "
        "chi phí còn kiểm tra giá reserved theo GPU.\n\n"
        f"Theo đúng days của job và không mua reserved mới: ${r3['actual_duration']['baseline_usd']:.2f} → "
        f"${r3['actual_duration']['optimized_usd']:.2f}, giảm {r3['actual_duration']['savings_pct']:.2f}%. "
        "Nhu cầu 3–30 ngày chưa đủ bằng chứng để cam kết 1–3 năm.",
        "## M4 — Showback, chargeback và FOCUS-style export\n\n" +
        table(["Team", "USD/ngày", "% chi phí (xấp xỉ do làm tròn)"],
              [[k, f"{v:.2f}", f"{v/r4['total_cost_usd']*100:.2f}"]
               for k, v in sorted(r4["by_team"].items(), key=lambda x: -x[1])]) +
        f"\n\nCoverage đủ team + project = {r4['tag_coverage']:.1%}, vượt gate 80%. "
        "Project thiếu tag cần xử lý trước khi chargeback phần đó. Schema FOCUS-style tối giản của lab chuẩn hóa "
        "billing account, kỳ phí, dịch vụ, tiền và tags để so sánh đa provider; không chứng nhận FOCUS đầy đủ. "
        f"Xuất {r4['export_rows']:,} rows: cost chính xác ${r4['total_cost_usd']:.6f}, "
        f"BilledCost CSV ${r4['focus_billed_usd']:.6f}; lệch ${r4['focus_billed_usd']-r4['total_cost_usd']:.6f} "
        f"do làm tròn 4 chữ số/row, trong giới hạn {r4['export_rows']} × $0,00005.",
        "## Extension #4 — Ngân sách reasoning\n\n" +
        table(["Traffic", "Requests", "Tokens", "USD/ngày", "Wh/ngày", "USD/1M-token"],
              [["Reasoning" if g["reasoning"] else "Thường", g["requests"], f"{g['tokens']:,}",
                f"{g['cost_usd']:.6f}", f"{g['energy_wh']:.3f}", f"{g['per_m']:.6f}"] for g in a["groups"]]) +
        f"\n\nReasoning chiếm {traffic_pct:.3f}% traffic, {cost_pct:.2f}% tiền và {energy_pct:.2f}% năng lượng. "
        "Cùng tokens và route, đổi cờ reasoning không đổi giá API; Wh tăng 80× theo giả định lab: "
        f"{a['same_tokens_nonreasoning_wh']:.3f} → {reasoning['energy_wh']:.3f} Wh. "
        "Chi phí reasoning cao do generator sinh output dài gấp 6, không phải surcharge từ cờ reasoning.\n\n" +
        table(["Cap", "Giữ reasoning", "Chuyển thường", "Savings USD/ngày", "Savings Wh/ngày", "Tokens sau"],
              [[f"{s['cap']:.0%}", s["reasoning_requests"], s["downgraded"], f"{s['savings_usd']:.6f}",
                f"{s['savings_wh']:.3f}", f"{s['total_tokens']:,}"] for s in a["reasoning_scenarios"]]) +
        "\n\nCap 10% không tác động vì traffic hiện tại thấp hơn cap. Mô phỏng giữ requests reasoning đắt nhất; "
        "phần chuyển thường giữ input/route/cache/batch, chia output cho 6 và bỏ hệ số năng lượng 80×. "
        "Đây là sensitivity analysis, chưa chứng minh chất lượng tương đương; không đưa savings vào M5. "
        "Rule đề xuất: reasoning cho task phức tạp hoặc confidence <0,7, có fallback và kiểm tra chất lượng. "
        "Dataset thiếu confidence nên chưa đánh giá rule này.",
        "## Extension #5 — Carbon-aware scheduling\n\n"
        "Chỉ xét training interruptible và dùng đúng days. Energy = GPU-hours × catalog watts, chưa gồm "
        "CPU/network/PUE/overhead spot. Tiền điện là so sánh riêng, không cộng thêm vào giá thuê GPU.\n\n" +
        table(["Training job", "GPU-hours", "kWh", "CO₂ us-east-1 kg", "CO₂ vùng sạch kg", "Giảm kg"],
              [[j["job_id"], f"{j['gpu_hours']:.0f}", f"{j['energy_wh']/1000:.3f}",
                f"{j['source_carbon_g']/1000:.3f}", f"{j['clean_carbon_g']/1000:.3f}",
                f"{j['carbon_saved_g']/1000:.3f}"] for j in sched["jobs"]]) + "\n\n" +
        table(["Vùng", "USD/kWh", "gCO₂/kWh", "Điện USD", "CO₂ kg"],
              [[r["region"], r["usd_per_kwh"], r["g_per_kwh"], f"{r['electricity_usd']:.2f}",
                f"{r['carbon_g']/1000:.3f}"] for r in sched["regions"]]) +
        f"\n\nSạch nhất {sched['cleanest']}; rẻ điện nhất {sched['cheapest']}; cân bằng {sched['balanced']} "
        "với trọng số 50/50 trên giá và carbon chuẩn hóa theo giá trị nhỏ nhất. "
        f"Chuyển training us-east-1 → vùng sạch giảm {sched['carbon_saved_g']/1000:.3f} kgCO₂e "
        f"({sched['carbon_savings_pct']:.2f}%). Training ít phụ thuộc latency phục vụ trực tiếp, nhưng vẫn cần "
        "kiểm tra data residency, phí transfer và GPU availability. Không có giá GPU theo vùng/giờ để tối ưu lịch thời gian.",
        "## Extension #2 — Right-sizing theo MBU\n\n" +
        table(["GPU type", "USD/GB-hour", "Peak BW TB/s"],
              [[r["gpu_type"], f"{r['usd_per_gb_hour']:.5f}", r["peak_bw_tbs"]] for r in size["catalog"]]) +
        "\n\nLọc inference memory-bound bằng achieved FLOPs/BW so với ridge point. Candidate phải đủ peak VRAM "
        "với headroom 15%, demand BW ≤75% peak và compute ≤50% peak. Đây là sàng lọc, cần benchmark trước khi thay.\n\n" +
        table(["GPU", "Hiện tại → đề xuất", "VRAM cần GB", "BW cần TB/s", "Peak BW hiện tại → đích", "Savings USD/tháng"],
              [[r["gpu_id"], f"{r['current']} → {r['target']}", f"{r['required_vram_gb']:.2f}",
                f"{r['required_bw_tbs']:.3f}", f"{r['current_bw_tbs']:.2f} → {r['target_bw_tbs']:.2f}",
                f"{r['monthly_savings_usd']:.2f}"] for r in size["recommendations"]]) +
        f"\n\nGiới hạn BW 60%: ${strict['monthly_savings_usd']:.2f}/tháng; "
        f"75%: ${size['monthly_savings_usd']:.2f}/tháng, ở on-demand 24/7. "
        "Tiết kiệm phụ thuộc headroom chấp nhận được. A100 cần khoảng 77–78 GB nên không thể chuyển sang GPU 24 GB. "
        "Giá/GB thấp không tự bảo đảm latency hoặc tổng tiền thấp. Benchmark P95, throughput và VRAM quyết định triển khai; "
        "cơ hội chưa cộng vào M5.",
        "## Hành động ưu tiên\n\n"
        "1. Đối soát phạm vi API/GPU; showback theo team/project và budget cap; xử lý project thiếu tag.\n"
        f"2. Cascade/cache/batch có đánh giá chất lượng: ${infer_saved:.2f}/tháng. Purchasing có cơ hội lớn nhất "
        f"trong mô hình (${purchase_saved:.2f}/tháng); dùng spot với checkpoint, reserved theo nhu cầu dài hạn.\n"
        "3. Tắt H100 sau giờ làm việc; benchmark right-sizing A10G, chuyển training sang vùng carbon thấp và giới hạn reasoning theo chất lượng task."]
    result = {"baseline_monthly": baseline, "optimized_monthly": optimized,
              "levers": levers, "total_savings_pct": total_pct}
    evidence = {"m1": r1, "m2": r2, "m3": r3, "m4": r4, "m5": result,
                "rightsizing_bw60": strict}
    cap5 = a["reasoning_scenarios"][1]
    writeup = f"""# GPU FinOps — Phân tích kết quả

## 1. Baseline và optimized

Inference phục vụ {r2['total_tokens']:,} tokens/ngày: ${r2['baseline_daily_exact']:.6f} → ${r2['optimized_daily_exact']:.6f}/ngày; ${r2['baseline_per_m']:.3f} → ${r2['optimized_per_m']:.3f}/1M-token, giảm {r2['savings_pct']:.1f}%. Tổng kịch bản tháng là ${baseline:.2f} → ${optimized:.2f}, giảm {total_pct:.2f}%. Tổng giả định hai ngân sách API và GPU độc lập; cần đối soát billing trước khi áp dụng thực tế. Không chia tiền training/dev cho token inference vì thiếu mẫu số tương ứng.

## 2. Đóng góp từng lever

Purchasing giảm ${purchase_saved:.2f}/tháng, lớn nhất trong kịch bản tổng. Trong inference, cascade giảm ${a['lever_savings_daily']['Cascade']*DAYS:.2f}, cache ${a['lever_savings_daily']['Cache']*DAYS:.2f}, batch ${a['lever_savings_daily']['Batch']*DAYS:.2f}/tháng. Tính tuần tự giúp tránh đếm trùng. Cascade hưởng chênh lệch giá model nhỏ/lớn; cache chỉ giảm input trùng; batch giảm toàn request nhưng không phù hợp chat cần latency thấp.

Reserved phải trả đủ giờ cam kết. L4 search hoạt động 18 giờ/ngày vẫn trả $1.296/tháng thay vì $972 nếu chỉ tính giờ chạy. Theo đúng days của job và chưa mua reserved mới: ${r3['actual_duration']['baseline_usd']:.2f} → ${r3['actual_duration']['optimized_usd']:.2f}, giảm {r3['actual_duration']['savings_pct']:.2f}%. Workloads 3–30 ngày chưa đủ bằng chứng để cam kết 1–3 năm; cần nhu cầu pool dài hạn.

## 3. GPU-Util lie và tác động tài chính

gpu-h100-4 có GPU-Util 98,2% nhưng MFU 0,194; gpu-a10g-1 có 96,9% nhưng MFU 0,268. GPU-Util phản ánh thời gian hoạt động, không phản ánh FLOPs hữu ích. Kernel ít phép toán, stall hoặc overhead có thể gây chênh lệch; telemetry chưa chỉ ra nguyên nhân riêng. Decode memory-bound cần xét MBU thay vì coi MFU thấp luôn là lãng phí.

gpu-h100-5 có 8 giờ idle/ngày, tương đương $20/ngày và $600/tháng. Right-sizing có cơ hội ${size['monthly_savings_usd']:.2f}/tháng ở mức bandwidth 75%. Hai khoản telemetry chưa cộng vào purchasing vì thiếu khóa GPU → job để loại bỏ phần trùng.

## 4. Extensions và kết quả

Reasoning: 201 requests chiếm {traffic_pct:.3f}% traffic, {cost_pct:.2f}% chi phí và {energy_pct:.2f}% năng lượng. Cùng tokens và route, giá API không đổi theo cờ reasoning; Wh tăng 80× theo giả định lab. Cap 10% không tiết kiệm. Cap 5% chuyển {cap5['downgraded']} requests sang thường, giảm ${cap5['savings_usd']:.6f} và {cap5['savings_wh']:.3f} Wh/ngày. Mô phỏng giữ requests đắt nhất, chia output phần chuyển cho 6 theo generator. Chưa chứng minh chất lượng tương đương; routing theo complexity/confidence cần đánh giá riêng.

Carbon scheduling: ba job training interruptible dùng {sched['total_energy_wh']/1000:.3f} kWh theo GPU-hours × watts. Chuyển us-east-1 → {sched['cleanest']} giảm {sched['carbon_saved_g']/1000:.3f} kgCO₂e ({sched['carbon_savings_pct']:.2f}%). Điện rẻ nhất là {sched['cheapest']}, khác vùng sạch nhất. So sánh tiền điện riêng, không cộng thêm vào bill thuê GPU; chưa gồm PUE, transfer và overhead spot. Training có thể chấp nhận xa vùng phục vụ hơn inference, nhưng cần kiểm tra residency và availability.

Right-sizing: so sánh giá/GB, bandwidth và compute, giữ 15% VRAM headroom và compute ≤50% peak. A100 cần khoảng 77–78 GB nên không chuyển sang GPU 24 GB. Demand bandwidth ≤60% peak không có cơ hội; nới lên 75% tạo cơ hội ${size['monthly_savings_usd']:.2f}/tháng. Đây là dự báo ở on-demand 24/7; benchmark P95 latency và throughput quyết định khả năng thay GPU.

## 5. Ba hành động đầu tiên

1. Đối soát bill API/GPU, showback theo team/project và budget cap. Coverage {r4['tag_coverage']:.1%} vượt gate 80%; xử lý project thiếu tag trước khi chargeback phần đó.
2. Triển khai cascade/cache/batch đã đánh giá chất lượng; spot có checkpoint. Chỉ mua reserved khi có nhu cầu pool dài hạn, vì purchasing savings phụ thuộc giờ cam kết thực.
3. Tắt GPU idle, benchmark right-sizing, chuyển training sang vùng carbon thấp và đặt budget reasoning theo chất lượng task.
"""
    out = Path(ROOT) / "outputs"
    out.mkdir(exist_ok=True)
    if (out / "bonus_tracker.json").exists():
        tracker = json.loads((out / "bonus_tracker.json").read_text())
        sections.append("## Bonus — Budget tracker và observability\n\n"
                        f"Mock tracker nhận {tracker['blocked_after_requests']} requests chat, "
                        f"spend ${tracker['spend_usd']['team-chat']:.6f}, rồi chặn request vượt cap $0,05. "
                        f"Eval dùng ${tracker['spend_usd']['team-eval']:.6f} với key riêng. "
                        "Kiểm tra bổ sung xác minh request bị chặn không tăng spend hoặc log. "
                        "Backend mock, token input ước lượng bằng số ký tự/4; chưa phải LiteLLM/OpenAI proxy thực. "
                        "Chi tiết: bonus_tracker.json.")
    if (out / "bonus_observability.json").exists():
        obs = json.loads((out / "bonus_observability.json").read_text())
        sections.append(f"Prometheus scrape {obs['exporter_gpu_count']} GPUs; target health={obs['target']['health']}; "
                        "MFU đối chiếu với M1, Grafana dashboard và datasource đã kiểm tra qua HTTP/API. "
                        f"Grafana {obs['grafana_health']['version']}, gồm {len(obs['panels'])} panels. "
                        "Các metrics là trung bình 24 giờ của telemetry tổng hợp, được scrape lặp lại, "
                        "không phải telemetry GPU live. FLOPs cost proxy = (1−MFU)×$/giờ không phải savings thu hồi được. "
                        "Bằng chứng: bonus_observability.json, bonus_metrics.prom và grafana_dashboard.jpg.")
    (out / "report.md").write_text("\n\n".join(sections) + "\n", encoding="utf-8")
    (out / "writeup.md").write_text(writeup, encoding="utf-8")
    (out / "analysis.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    png = report.savings_waterfall(levers, str(out / "savings.png"), baseline_usd=baseline)
    if verbose:
        print("== M5 Optimization Report ==")
        print((out / "report.md").read_text(encoding="utf-8"))
        print("Written: outputs/report.md + outputs/writeup.md + outputs/analysis.json" +
              (" + outputs/savings.png" if png else " (PNG not produced)"))
    return result


if __name__ == "__main__":
    run()
