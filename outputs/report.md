# NimbusAI — GPU Cost Optimization Report

**Period:** 30-day recurring simulation (June 2026 prices)

**Baseline spend:** $27,133.62

**Optimized spend:** $16,205.83

**Projected savings:** $10,927.80  (**40.27%**)

## Savings by lever

| Lever | Savings (USD) |
|---|---|
| Inference | $1,211.69 |
| Purchasing | $9,716.11 |
| Right-sizing | $0.00 |
| Idle shutdown | $0.00 |

## Sustainability

- Energy per query: 13.20 Wh
- Carbon per query: 5.015 gCO2e
- Cleanest region: europe-north1

_Figures are June-2026 as-of snapshots; re-baseline before acting._

## Phạm vi và phương pháp

Dataset seed=25 gồm 264 bản ghi telemetry, 11 GPU, 2.400 requests/ngày và 8 workloads. Tổng tháng của lab giả định hai ngân sách độc lập: token API và GPU workloads. Nếu hai nguồn phí phục vụ cùng một dịch vụ, cần đối soát billing trước khi cộng. Telemetry không có khóa GPU → job; savings idle và right-sizing được báo cáo riêng, không cộng vào purchasing. Các cột $0 trong waterfall thể hiện cơ hội chưa đưa vào tổng. Giá và năng lượng là giả định của repo.

## M2 — Baseline, optimized và từng lever

Mẫu số cố định: 7,533,027 input + output tokens/ngày, bao gồm cached input. Đo tuần tự baseline → cascade → cache → batch; thứ tự ảnh hưởng phần đóng góp từng lever.

| Kịch bản | USD/ngày | USD/1M-token |
| --- | --- | --- |
| baseline | 48.874161 | 6.487984 |
| cascade | 11.475643 | 1.523377 |
| cache | 10.279188 | 1.364549 |
| batch | 8.484623 | 1.126323 |

| Lever | Savings USD/ngày | Savings USD/30 ngày |
| --- | --- | --- |
| Cascade | 37.398518 | 1121.96 |
| Cache | 1.196455 | 35.89 |
| Batch | 1.794565 | 53.84 |

Inference giảm 82.6%. Cascade đóng góp lớn nhất trong inference vì chính sách generator định tuyến phần lớn requests sang model nhỏ. Cache giảm phần cached input; batch giảm cả request. 0,5 × 0,1 = 0,05 chỉ đúng cho phần input cache hoàn toàn, không đúng cho mọi request có output. Batch phù hợp eval bất đồng bộ; không áp dụng cho chat cần phản hồi ngay.

| Ngân sách tháng | Baseline USD | Optimized USD | USD/1M-token trước | USD/1M-token sau |
| --- | --- | --- | --- | --- |
| Token API | 1466.22 | 254.54 | 6.488 | 1.126 |
| GPU workloads | 25667.40 | 15951.29 | N/A | N/A |

Không chia tiền training/dev cho token inference vì thiếu sản lượng token tương ứng.

## M1 — GPU-Util lie và idle

| GPU | GPU-Util % | MFU | MBU |
| --- | --- | --- | --- |
| gpu-h100-4 | 98.2 | 0.194 | 0.207 |
| gpu-a10g-1 | 96.9 | 0.268 | 0.302 |

GPU-Util đo thời gian có kernel hoạt động; MFU đo achieved/peak FLOPs. Kernel ít phép toán, memory stall hoặc overhead có thể giữ GPU bận nhưng FLOPs thấp. Telemetry tổng hợp chưa đủ để kết luận nguyên nhân riêng. Decode memory-bound có thể có MFU thấp hợp lý; cần xét MBU và roofline trước khi thay GPU. gpu-h100-5 có 8 giờ idle: 8 × $2,50 = $20.00/ngày, $600.00/30 ngày. Đây là cơ hội từ telemetry, chưa trừ vào bill M3.

## M3 — Purchasing và thời hạn cam kết

| Job | GPU | Tier | On-demand USD/30 ngày | Optimized USD/30 ngày |
| --- | --- | --- | --- | --- |
| job-train-llm | H100 | spot | 12000.00 | 7596.00 |
| job-train-embed | A100 | spot | 2148.00 | 1392.60 |
| job-finetune | H100 | spot | 900.00 | 569.70 |
| job-infer-chat | A10G | reserved | 4320.00 | 2592.00 |
| job-infer-rag | A100 | reserved | 3866.40 | 2160.00 |
| job-infer-search | L4 | reserved | 1728.00 | 1296.00 |
| job-dev-sandbox | A10G | spot | 480.00 | 202.56 |
| job-batch-eval | H100 | spot | 225.00 | 142.43 |

Purchasing giảm 37.9%. Spot giả định interruption 0,05/giờ, checkpoint overhead 3%, rework 0,5 giờ/lần: effective hours = job hours × 1,055. Reserved trả đủ 24 giờ/ngày, kể cả giờ bỏ trống; L4 search hoạt động 18 giờ/ngày vẫn trả $1.296/tháng. Kịch bản tháng giả định pool có nhu cầu dài hạn đủ thời hạn cam kết; ngưỡng 55% của policy chỉ là xấp xỉ, chi phí còn kiểm tra giá reserved theo GPU.

Theo đúng days của job và không mua reserved mới: $16539.40 → $14039.24, giảm 15.12%. Nhu cầu 3–30 ngày chưa đủ bằng chứng để cam kết 1–3 năm.

## M4 — Showback, chargeback và FOCUS-style export

| Team | USD/ngày | % chi phí (xấp xỉ do làm tròn) |
| --- | --- | --- |
| assistant | 2.59 | 30.53 |
| search | 2.49 | 29.35 |
| eval | 1.79 | 21.10 |
| rag | 1.60 | 18.86 |

Coverage đủ team + project = 91.8%, vượt gate 80%. Project thiếu tag cần xử lý trước khi chargeback phần đó. Schema FOCUS-style tối giản của lab chuẩn hóa billing account, kỳ phí, dịch vụ, tiền và tags để so sánh đa provider; không chứng nhận FOCUS đầy đủ. Xuất 2,400 rows: cost chính xác $8.484623, BilledCost CSV $8.482100; lệch $-0.002523 do làm tròn 4 chữ số/row, trong giới hạn 2400 × $0,00005.

## Extension #4 — Ngân sách reasoning

| Traffic | Requests | Tokens | USD/ngày | Wh/ngày | USD/1M-token |
| --- | --- | --- | --- | --- | --- |
| Thường | 2199 | 6,291,871 | 7.088159 | 1887.561 | 1.126558 |
| Reasoning | 201 | 1,241,156 | 1.396464 | 29787.744 | 1.125132 |

Reasoning chiếm 8.375% traffic, 16.46% tiền và 94.04% năng lượng. Cùng tokens và route, đổi cờ reasoning không đổi giá API; Wh tăng 80× theo giả định lab: 372.347 → 29787.744 Wh. Chi phí reasoning cao do generator sinh output dài gấp 6, không phải surcharge từ cờ reasoning.

| Cap | Giữ reasoning | Chuyển thường | Savings USD/ngày | Savings Wh/ngày | Tokens sau |
| --- | --- | --- | --- | --- | --- |
| 10% | 201 | 0 | 0.000000 | 0.000 | 7,533,027 |
| 5% | 120 | 81 | 0.030077 | 8578.703 | 7,382,642 |
| 2% | 48 | 153 | 0.095134 | 21838.013 | 7,057,357 |

Cap 10% không tác động vì traffic hiện tại thấp hơn cap. Mô phỏng giữ requests reasoning đắt nhất; phần chuyển thường giữ input/route/cache/batch, chia output cho 6 và bỏ hệ số năng lượng 80×. Đây là sensitivity analysis, chưa chứng minh chất lượng tương đương; không đưa savings vào M5. Rule đề xuất: reasoning cho task phức tạp hoặc confidence <0,7, có fallback và kiểm tra chất lượng. Dataset thiếu confidence nên chưa đánh giá rule này.

## Extension #5 — Carbon-aware scheduling

Chỉ xét training interruptible và dùng đúng days. Energy = GPU-hours × catalog watts, chưa gồm CPU/network/PUE/overhead spot. Tiền điện là so sánh riêng, không cộng thêm vào giá thuê GPU.

| Training job | GPU-hours | kWh | CO₂ us-east-1 kg | CO₂ vùng sạch kg | Giảm kg |
| --- | --- | --- | --- | --- | --- |
| job-train-llm | 2240 | 1568.000 | 595.840 | 47.040 | 548.800 |
| job-train-embed | 200 | 80.000 | 30.400 | 2.400 | 28.000 |
| job-finetune | 36 | 25.200 | 9.576 | 0.756 | 8.820 |

| Vùng | USD/kWh | gCO₂/kWh | Điện USD | CO₂ kg |
| --- | --- | --- | --- | --- |
| us-east-1 | 0.12 | 380 | 200.78 | 635.816 |
| us-west-2 | 0.07 | 120 | 117.12 | 200.784 |
| europe-north1 | 0.09 | 30 | 150.59 | 50.196 |
| europe-central2 | 0.18 | 660 | 301.18 | 1104.312 |
| us-east-wa | 0.055 | 90 | 92.03 | 150.588 |

Sạch nhất europe-north1; rẻ điện nhất us-east-wa; cân bằng europe-north1 với trọng số 50/50 trên giá và carbon chuẩn hóa theo giá trị nhỏ nhất. Chuyển training us-east-1 → vùng sạch giảm 585.620 kgCO₂e (92.11%). Training ít phụ thuộc latency phục vụ trực tiếp, nhưng vẫn cần kiểm tra data residency, phí transfer và GPU availability. Không có giá GPU theo vùng/giờ để tối ưu lịch thời gian.

## Extension #2 — Right-sizing theo MBU

| GPU type | USD/GB-hour | Peak BW TB/s |
| --- | --- | --- |
| H100 | 0.03125 | 3.35 |
| H200 | 0.02801 | 4.8 |
| A100 | 0.02237 | 2.0 |
| A10G | 0.04167 | 0.6 |
| L4 | 0.03333 | 0.3 |
| B200 | 0.02651 | 8.0 |
| MI300X | 0.01016 | 5.3 |

Lọc inference memory-bound bằng achieved FLOPs/BW so với ridge point. Candidate phải đủ peak VRAM với headroom 15%, demand BW ≤75% peak và compute ≤50% peak. Đây là sàng lọc, cần benchmark trước khi thay.

| GPU | Hiện tại → đề xuất | VRAM cần GB | BW cần TB/s | Peak BW hiện tại → đích | Savings USD/tháng |
| --- | --- | --- | --- | --- | --- |
| gpu-a100-0 | A100 → A100 | 77.86 | 0.707 | 2.00 → 2.00 | 0.00 |
| gpu-a100-1 | A100 → A100 | 77.05 | 0.677 | 2.00 → 2.00 | 0.00 |
| gpu-a10g-0 | A10G → L4 | 23.34 | 0.182 | 0.60 → 0.30 | 144.00 |
| gpu-a10g-1 | A10G → L4 | 23.46 | 0.212 | 0.60 → 0.30 | 144.00 |

Giới hạn BW 60%: $0.00/tháng; 75%: $288.00/tháng, ở on-demand 24/7. Tiết kiệm phụ thuộc headroom chấp nhận được. A100 cần khoảng 77–78 GB nên không thể chuyển sang GPU 24 GB. Giá/GB thấp không tự bảo đảm latency hoặc tổng tiền thấp. Benchmark P95, throughput và VRAM quyết định triển khai; cơ hội chưa cộng vào M5.

## Hành động ưu tiên

1. Đối soát phạm vi API/GPU; showback theo team/project và budget cap; xử lý project thiếu tag.
2. Cascade/cache/batch có đánh giá chất lượng: $1211.69/tháng. Purchasing có cơ hội lớn nhất trong mô hình ($9716.11/tháng); dùng spot với checkpoint, reserved theo nhu cầu dài hạn.
3. Tắt H100 sau giờ làm việc; benchmark right-sizing A10G, chuyển training sang vùng carbon thấp và giới hạn reasoning theo chất lượng task.

## Bonus — Budget tracker và observability

Mock tracker nhận 10 requests chat, spend $0.046050, rồi chặn request vượt cap $0,05. Eval dùng $0.000260 với key riêng. Kiểm tra bổ sung xác minh request bị chặn không tăng spend hoặc log. Backend mock, token input ước lượng bằng số ký tự/4; chưa phải LiteLLM/OpenAI proxy thực. Chi tiết: bonus_tracker.json.

Prometheus scrape 11 GPUs; target health=up; MFU đối chiếu với M1, Grafana dashboard và datasource đã kiểm tra qua HTTP/API. Grafana 13.2.3, gồm 5 panels. Các metrics là trung bình 24 giờ của telemetry tổng hợp, được scrape lặp lại, không phải telemetry GPU live. FLOPs cost proxy = (1−MFU)×$/giờ không phải savings thu hồi được. Bằng chứng: bonus_observability.json, bonus_metrics.prom và grafana_dashboard.jpg.
