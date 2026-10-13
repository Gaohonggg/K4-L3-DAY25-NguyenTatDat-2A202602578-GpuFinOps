# GPU FinOps — Phân tích kết quả

## 1. Baseline và optimized

Inference phục vụ 7,533,027 tokens/ngày: $48.874161 → $8.484623/ngày; $6.488 → $1.126/1M-token, giảm 82.6%. Tổng kịch bản tháng là $27133.62 → $16205.83, giảm 40.27%. Tổng giả định hai ngân sách API và GPU độc lập; cần đối soát billing trước khi áp dụng thực tế. Không chia tiền training/dev cho token inference vì thiếu mẫu số tương ứng.

## 2. Đóng góp từng lever

Purchasing giảm $9716.11/tháng, lớn nhất trong kịch bản tổng. Trong inference, cascade giảm $1121.96, cache $35.89, batch $53.84/tháng. Tính tuần tự giúp tránh đếm trùng. Cascade hưởng chênh lệch giá model nhỏ/lớn; cache chỉ giảm input trùng; batch giảm toàn request nhưng không phù hợp chat cần latency thấp.

Reserved phải trả đủ giờ cam kết. L4 search hoạt động 18 giờ/ngày vẫn trả $1.296/tháng thay vì $972 nếu chỉ tính giờ chạy. Theo đúng days của job và chưa mua reserved mới: $16539.40 → $14039.24, giảm 15.12%. Workloads 3–30 ngày chưa đủ bằng chứng để cam kết 1–3 năm; cần nhu cầu pool dài hạn.

## 3. GPU-Util lie và tác động tài chính

gpu-h100-4 có GPU-Util 98,2% nhưng MFU 0,194; gpu-a10g-1 có 96,9% nhưng MFU 0,268. GPU-Util phản ánh thời gian hoạt động, không phản ánh FLOPs hữu ích. Kernel ít phép toán, stall hoặc overhead có thể gây chênh lệch; telemetry chưa chỉ ra nguyên nhân riêng. Decode memory-bound cần xét MBU thay vì coi MFU thấp luôn là lãng phí.

gpu-h100-5 có 8 giờ idle/ngày, tương đương $20/ngày và $600/tháng. Right-sizing có cơ hội $288.00/tháng ở mức bandwidth 75%. Hai khoản telemetry chưa cộng vào purchasing vì thiếu khóa GPU → job để loại bỏ phần trùng.

## 4. Extensions và kết quả

Reasoning: 201 requests chiếm 8.375% traffic, 16.46% chi phí và 94.04% năng lượng. Cùng tokens và route, giá API không đổi theo cờ reasoning; Wh tăng 80× theo giả định lab. Cap 10% không tiết kiệm. Cap 5% chuyển 81 requests sang thường, giảm $0.030077 và 8578.703 Wh/ngày. Mô phỏng giữ requests đắt nhất, chia output phần chuyển cho 6 theo generator. Chưa chứng minh chất lượng tương đương; routing theo complexity/confidence cần đánh giá riêng.

Carbon scheduling: ba job training interruptible dùng 1673.200 kWh theo GPU-hours × watts. Chuyển us-east-1 → europe-north1 giảm 585.620 kgCO₂e (92.11%). Điện rẻ nhất là us-east-wa, khác vùng sạch nhất. So sánh tiền điện riêng, không cộng thêm vào bill thuê GPU; chưa gồm PUE, transfer và overhead spot. Training có thể chấp nhận xa vùng phục vụ hơn inference, nhưng cần kiểm tra residency và availability.

Right-sizing: so sánh giá/GB, bandwidth và compute, giữ 15% VRAM headroom và compute ≤50% peak. A100 cần khoảng 77–78 GB nên không chuyển sang GPU 24 GB. Demand bandwidth ≤60% peak không có cơ hội; nới lên 75% tạo cơ hội $288.00/tháng. Đây là dự báo ở on-demand 24/7; benchmark P95 latency và throughput quyết định khả năng thay GPU.

## 5. Ba hành động đầu tiên

1. Đối soát bill API/GPU, showback theo team/project và budget cap. Coverage 91.8% vượt gate 80%; xử lý project thiếu tag trước khi chargeback phần đó.
2. Triển khai cascade/cache/batch đã đánh giá chất lượng; spot có checkpoint. Chỉ mua reserved khi có nhu cầu pool dài hạn, vì purchasing savings phụ thuộc giờ cam kết thực.
3. Tắt GPU idle, benchmark right-sizing, chuyển training sang vùng carbon thấp và đặt budget reasoning theo chất lượng task.
