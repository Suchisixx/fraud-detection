# Hệ Thống Phát Hiện Gian Lận Thời Gian Thực Với PaySim

## 1. Giới thiệu

Đây là đồ án xây dựng hệ thống phát hiện gian lận giao dịch ví điện tử theo thời gian thực trên bộ dữ liệu **PaySim**. Dự án mô phỏng bài toán quản trị rủi ro cho ví điện tử, trong đó hệ thống cần tự động nhận diện các hành vi bất thường như:

- giao dịch chạm vào tài khoản trong danh sách đen
- chuyển tiền giá trị lớn bất thường
- chuyển tiền làm cạn sạch số dư tài khoản nguồn
- chuyển tiền liên tục vào các tài khoản trong danh sách đen trong cùng một khoảng thời gian nghiệp vụ

Hệ thống sử dụng kiến trúc nhiều tầng với Spark Structured Streaming và Delta Lake:

- `Bronze`: tiếp nhận dữ liệu gốc dạng luồng
- `Silver`: làm sạch dữ liệu, tạo đặc trưng, áp dụng luật nghiệp vụ
- `Gold`: chấm điểm mô hình, hợp nhất điểm luật và điểm máy học, sinh cảnh báo

Phạm vi đồ án được chốt là **PaySim-only**. Vì PaySim không chứa sự kiện đăng nhập, dự án **không tuyên bố phát hiện đăng nhập lạ từ dữ liệu thật**, mà tập trung vào phát hiện bất thường trong hành vi giao dịch và tài khoản.

## 2. Mục tiêu đồ án

Mục tiêu chính của hệ thống:

- xây dựng pipeline xử lý dữ liệu theo thời gian thực
- phát hiện gian lận bằng mô hình lai giữa luật nghiệp vụ và học máy
- có thể demo trực quan bằng luồng dữ liệu giả lập
- có đầu ra đủ để giải trình theo các tiêu chí chấm: kiến trúc, hiệu năng, độ chính xác và tính chuyên nghiệp của báo cáo

## 3. Kiến trúc tổng thể

### 3.1. Luồng ngoại tuyến

Luồng này dùng để chuẩn bị trước khi demo:

- `seed_blacklist`: tạo bảng danh sách đen ban đầu
- `train_model`: huấn luyện mô hình Random Forest từ dữ liệu lịch sử

### 3.2. Luồng thời gian thực

Luồng chạy trong lúc demo:

- `simulate_stream`: cắt dữ liệu PaySim thành nhiều lô nhỏ và đẩy vào thư mục luồng
- `bronze_stream`: đọc CSV dạng streaming và ghi vào Delta Bronze
- `silver_stream`: làm sạch, tạo đặc trưng, áp dụng luật, ghi vào Delta Silver
- `gold_stream`: tải mô hình đã huấn luyện, chấm điểm từng lô dữ liệu, sinh cảnh báo và cập nhật bảng tổng hợp

### 3.3. Công thức chấm điểm lai

Hệ thống sử dụng công thức:

```text
diem_tong_hop = ml_probability * 0.7 + rule_score_normalized * 0.3
```

Giao dịch sẽ bị cảnh báo nếu:

- `diem_tong_hop` vượt ngưỡng
- hoặc chạm blacklist
- hoặc vi phạm luật chuyển liên tục vào blacklist

## 4. Cấu trúc thư mục

```text
.
|-- src/
|   |-- common/
|   |   |-- config.py
|   |   |-- features.py
|   |   |-- rules.py
|   |   |-- schemas.py
|   |   `-- spark.py
|   `-- jobs/
|       |-- seed_blacklist.py
|       |-- train_model.py
|       |-- bronze_stream.py
|       |-- silver_stream.py
|       |-- gold_stream.py
|       `-- simulate_stream.py
|-- scripts/
|   |-- run_train_docker.ps1
|   `-- run_demo_docker.ps1
`-- data/
    |-- raw/
    |-- reference/
    |-- stream_input/
    |-- delta/
    `-- reports/
```

Ý nghĩa:

- `src/common`: phần dùng chung như cấu hình, schema, Spark session, luật, feature engineering
- `src/jobs`: các tác vụ chính chạy độc lập
- `data/raw`: nơi đặt `paysim.csv`
- `data/reference`: dữ liệu tham chiếu, hiện dùng cho blacklist seed
- `data/stream_input`: nơi simulator đẩy micro-batch
- `data/delta`: nơi lưu các bảng Delta
- `data/reports`: nơi lưu biểu đồ, số liệu và file phục vụ báo cáo

## 5. Luật phát hiện gian lận

Tầng Silver hiện áp dụng 4 luật nghiệp vụ:

1. `rule_blacklist`
   Giao dịch có tài khoản nguồn hoặc tài khoản đích nằm trong danh sách đen.

2. `rule_large_txn`
   Giao dịch `TRANSFER` hoặc `CASH_OUT` có giá trị lớn hơn ngưỡng cấu hình.

3. `rule_drain`
   Giao dịch chuyển tiền làm số dư tài khoản nguồn về 0.

4. `rule_blacklist_burst`
   Một tài khoản nguồn chuyển liên tiếp đến các tài khoản blacklist trong cùng `step`, với số lần lớn hơn hoặc bằng ngưỡng cấu hình.

## 6. Mô hình học máy

Mô hình hiện dùng:

- thuật toán: `RandomForestClassifier`
- dữ liệu huấn luyện: các giao dịch `TRANSFER` và `CASH_OUT`
- đặc trưng:
  - số tiền giao dịch
  - số dư trước và sau giao dịch
  - sai lệch cân bằng số dư
  - tỷ lệ số tiền trên số dư
  - cờ tài khoản bị rút về 0
  - cờ giao dịch lớn
  - giờ giao dịch
  - loại giao dịch đã mã hóa

Mô hình được huấn luyện trước giờ demo, sau đó Gold stream dùng lại model đã lưu để chấm điểm theo thời gian thực.

## 7. Yêu cầu môi trường

### 7.1. Phần mềm cần có

- Docker Desktop
- PowerShell
- tối thiểu khoảng 4GB RAM trống cho container

### 7.2. Dung lượng đề xuất

Tùy kích thước dữ liệu và số lần chạy, nên chuẩn bị:

- dataset PaySim
- thư mục Delta
- mô hình đã train
- biểu đồ và file báo cáo

Khuyến nghị có ít nhất 3GB đến 5GB trống.

## 8. Chuẩn bị dữ liệu

Đặt file `paysim.csv` vào:

```text
data/raw/paysim.csv
```

Nếu chưa có blacklist seed riêng, hệ thống sẽ tự sinh từ các tài khoản gian lận đã biết trong PaySim và lưu lại vào:

```text
data/reference/blacklist_seed.csv
```

## 9. Cách chạy dự án

### 9.1. Khởi động Docker

```powershell
docker compose up -d --build
```

### 9.2. Tạo danh sách đen ban đầu

```powershell
docker compose exec fraud python -m src.jobs.seed_blacklist
```

### 9.3. Huấn luyện mô hình

```powershell
docker compose exec fraud python -m src.jobs.train_model
```

Kết quả sau bước này:

- mô hình lưu tại `data/delta/model`
- chỉ số huấn luyện lưu tại `data/reports/training_metrics.json`
- biểu đồ ROC, PR, ma trận nhầm lẫn lưu tại `data/reports/training_curves.png`

### 9.4. Chạy pipeline streaming

Mở 4 cửa sổ PowerShell.

Cửa sổ 1:

```powershell
docker compose exec fraud python -m src.jobs.bronze_stream
```

Cửa sổ 2:

```powershell
docker compose exec fraud python -m src.jobs.silver_stream
```

Cửa sổ 3:

```powershell
docker compose exec fraud python -m src.jobs.gold_stream
```

Cửa sổ 4:

```powershell
docker compose exec fraud python -m src.jobs.simulate_stream
```

Khi simulator chạy, dữ liệu sẽ được đẩy vào hệ thống theo từng lô nhỏ và 3 stream còn lại sẽ xử lý nối tiếp theo thời gian thực.

## 10. Script chạy nhanh

Huấn luyện nhanh:

```powershell
.\scripts\run_train_docker.ps1
```

Demo nhanh:

```powershell
.\scripts\run_demo_docker.ps1
```

### 10.1. Mở dashboard web để trình chiếu

Sau khi pipeline đã sinh các file trong `data/reports`, có thể mở dashboard web bằng:

```powershell
python -m src.web.dashboard_server
```

Dashboard mặc định chạy tại:

```text
http://127.0.0.1:8008
```

Dashboard sẽ tự làm mới mỗi 5 giây và đọc trực tiếp các file báo cáo như:

- `data/reports/latest_gold_batch.json`
- `data/reports/training_metrics.json`
- `data/reports/evaluation_summary.csv`
- `data/reports/top_risk_accounts.csv`
- `data/reports/dashboard.png`

## 11. Kết quả đầu ra quan trọng

Các file và bảng nên dùng khi demo:

- `data/delta/gold_alerts`
  Bảng cảnh báo gian lận cuối cùng

- `data/delta/gold_metrics`
  Bảng thống kê tổng hợp theo loại giao dịch

- `data/delta/gold_scored`
  Toàn bộ giao dịch đã được chấm điểm

- `data/reports/dashboard.png`
  Dashboard tổng hợp dùng để trình bày

- `data/reports/evaluation_summary.csv`
  Bảng so sánh luật, mô hình máy học và mô hình lai

- `data/reports/top_risk_accounts.csv`
  Danh sách tài khoản rủi ro cao

- `data/reports/training_metrics.json`
  Chỉ số huấn luyện mô hình

## 12. Cách demo đúng theo đề tài

### 12.1. Trình tự demo gợi ý

1. Giới thiệu bài toán quản trị rủi ro và bối cảnh ví điện tử.
2. Nói rõ phạm vi: dùng PaySim nên tập trung vào gian lận giao dịch, không demo đăng nhập lạ từ dữ liệu thật.
3. Trình bày sơ đồ Bronze, Silver, Gold.
4. Chạy hoặc trình bày bước seed blacklist và train model.
5. Mở 3 luồng streaming.
6. Chạy simulator.
7. Quan sát log từng batch ở Bronze, Silver, Gold.
8. Mở bảng `gold_alerts` và ảnh `dashboard.png`.
9. Kết luận hiệu quả hệ thống theo 3 nhóm: luật, mô hình, mô hình lai.

### 12.2. Câu nói nên dùng khi giải trình

- Hệ thống xử lý theo kiểu `micro-batch near real-time`, không phải streaming mức mili-giây.
- PaySim không có dữ liệu đăng nhập, nên đồ án không tuyên bố phát hiện đăng nhập lạ từ dữ liệu nguồn.
- Blacklist là dữ liệu tham chiếu được nạp trước, tránh rò rỉ nhãn vào luồng online.
- Gold layer là nơi hợp nhất điểm luật và điểm học máy để tăng tính thực tiễn.

## 13. Liên hệ với tiêu chí chấm điểm

### 13.1. Kiến trúc dữ liệu và khả năng mở rộng

Điểm mạnh để trình bày:

- pipeline nhiều tầng rõ ràng Bronze, Silver, Gold
- tách riêng luồng offline và online
- dữ liệu được partition theo `type`
- có thể mở rộng bằng cách tăng tài nguyên Spark hoặc triển khai trên cluster thay vì local container

### 13.2. Hiệu quả xử lý và tối ưu mã nguồn

Điểm mạnh để trình bày:

- giảm `shuffle partitions` cho môi trường local
- broadcast join với bảng blacklist nhỏ
- có `explain()` trong các job streaming để giải thích execution plan
- chỉ xử lý các cột cần thiết ở từng bước

### 13.3. Độ chính xác và giá trị thực tiễn

Điểm mạnh để trình bày:

- có rule-based để bám sát nghiệp vụ
- có ML-based để học mẫu gian lận phức tạp
- có hybrid score để cân bằng giữa độ bao phủ và độ chính xác
- có file đánh giá và dashboard hỗ trợ giải thích kết quả

### 13.4. Hình thức báo cáo và giải trình

Điểm mạnh để trình bày:

- README đầy đủ
- thư mục dự án gọn, tách rõ phần dùng chung và phần job
- có dashboard, file metrics, top tài khoản rủi ro
- có script chạy nhanh phục vụ demo

## 14. Dừng hệ thống

Dừng container:

```powershell
docker compose down
```

Xóa luôn trạng thái sinh ra trong quá trình chạy:

```powershell
docker compose down -v
```

## 15. Ghi chú quan trọng

- Dự án đã được Việt hóa phần tài liệu và nội dung hiển thị để thuận tiện khi nộp và demo.
- Tên file, tên module và tên kỹ thuật vẫn giữ ổn định để tránh làm gãy lệnh chạy.
- Nếu muốn chuyển tiếp toàn bộ tên file và tên module sang tiếng Việt, cần refactor thêm vì sẽ ảnh hưởng trực tiếp đến lệnh chạy, import và script hiện tại.
