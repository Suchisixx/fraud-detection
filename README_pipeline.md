# README Pipeline

## 1. Mục đích tài liệu

Tài liệu này giải thích riêng **luồng xử lý dữ liệu** của đồ án phát hiện gian lận với PaySim, theo đúng thứ tự:

1. Trước Bronze
2. Bronze
3. Silver
4. Gold
5. Kết quả AI
6. Streaming chạy như thế nào
7. Các đầu ra cuối cùng phục vụ demo và báo cáo

Mục tiêu là để nhóm có thể:

- giải thích kiến trúc pipeline một cách mạch lạc
- trả lời khi giảng viên hỏi “dữ liệu đi từ đâu tới đâu”
- phân biệt rõ phần **offline AI** và phần **online streaming**

---

## 2. Bức tranh tổng thể

```text
PaySim CSV
   ↓
data/raw/paysim.csv
   ↓
Offline preparation
   ├─ seed_blacklist
   └─ train_model
   ↓
simulate_stream
   ↓
data/stream_input/
   ↓
bronze_stream
   ↓
data/delta/bronze
   ↓
silver_stream
   ↓
data/delta/silver
   ↓
gold_stream
   ↓
data/delta/gold_scored
   ├─ data/delta/gold_alerts
   ├─ data/delta/gold_metrics
   └─ data/reports/*
```

Nói ngắn gọn:

- **PaySim CSV** là dữ liệu gốc
- **offline** dùng để chuẩn bị blacklist và huấn luyện mô hình AI
- **online streaming** dùng để mô phỏng dữ liệu đi vào hệ thống theo từng lô nhỏ
- **Gold** là nơi hợp nhất kết quả luật và AI để sinh cảnh báo cuối cùng

---

## 3. Giai đoạn trước Bronze

Đây là phần chuẩn bị trước khi chạy luồng streaming chính.

### 3.1. Dữ liệu gốc

File nguồn đầu vào của toàn bộ dự án là:

```text
data/raw/paysim.csv
```

Đây là bộ dữ liệu giao dịch ví điện tử mô phỏng từ PaySim, có các trường chính như:

- `step`
- `type`
- `amount`
- `nameOrig`
- `oldbalanceOrg`
- `newbalanceOrig`
- `nameDest`
- `oldbalanceDest`
- `newbalanceDest`
- `isFraud`
- `isFlaggedFraud`

### 3.2. Seed blacklist

Job:

```text
src/jobs/seed_blacklist.py
```

Vai trò:

- tạo danh sách đen ban đầu để phục vụ rule-based detection
- blacklist được sinh từ các tài khoản fraud đã biết trong PaySim
- kết quả được lưu để các tầng sau dùng lại

Đầu ra:

```text
data/reference/blacklist_seed.csv
data/delta/blacklist
```

Ý nghĩa:

- đây là **dữ liệu tham chiếu**
- Silver dùng nó để kiểm tra giao dịch có chạm vào blacklist hay không

### 3.3. Huấn luyện mô hình AI

Job:

```text
src/jobs/train_model.py
```

Vai trò:

- đọc dữ liệu lịch sử
- tạo đặc trưng giống với luồng streaming
- huấn luyện mô hình `RandomForestClassifier`
- lưu model lại để Gold dùng khi chạy online

Luồng huấn luyện:

```text
PaySim lịch sử
   ↓
chuẩn hóa cột
   ↓
làm sạch dữ liệu
   ↓
tạo feature
   ↓
áp dụng rule dùng chung
   ↓
lọc các giao dịch trọng tâm: TRANSFER, CASH_OUT
   ↓
train/test split
   ↓
huấn luyện Random Forest
   ↓
lưu model + metrics
```

Đầu ra của bước AI offline:

```text
data/delta/model
data/reports/training_metrics.json
data/reports/training_curves.png
```

Điểm quan trọng khi giải thích:

- **AI được train trước**
- lúc streaming chạy, Gold chỉ **load lại model đã lưu** để chấm điểm online
- như vậy online path không phải huấn luyện lại

---

## 4. Bronze

Job:

```text
src/jobs/bronze_stream.py
```

### 4.1. Dữ liệu đi vào Bronze từ đâu

Bronze không đọc thẳng từ `paysim.csv`.

Bronze đọc từ thư mục mô phỏng stream:

```text
data/stream_input/
```

Thư mục này được tạo bởi job:

```text
src/jobs/simulate_stream.py
```

### 4.2. `simulate_stream` làm gì

Job này cắt dữ liệu PaySim thành nhiều file CSV nhỏ để mô phỏng dữ liệu đi vào hệ thống theo thời gian thực.

Luồng:

```text
data/raw/paysim.csv
   ↓
tách thành nhiều batch nhỏ
   ↓
ghi từng batch vào data/stream_input/batch_xxxx/
```

Mỗi lần simulator ghi thêm một file batch mới, Spark Structured Streaming ở Bronze sẽ phát hiện và xử lý.

### 4.3. Bronze xử lý gì

Bronze là tầng ingest gần với dữ liệu gốc nhất.

Những gì Bronze làm:

- đọc CSV dạng stream
- dùng schema cố định để đọc ổn định
- chuẩn hóa tên cột
- thêm:
  - `txn_id`
  - `ingested_at`
  - `source_file`
- ghi vào Delta Bronze

Đầu ra:

```text
data/delta/bronze
```

Ý nghĩa của Bronze:

- lưu dữ liệu “gần như nguyên bản”
- làm tầng đầu tiên trong kiến trúc Bronze-Silver-Gold
- giúp truy vết giao dịch và nguồn file đầu vào

---

## 5. Silver

Job:

```text
src/jobs/silver_stream.py
```

Silver đọc trực tiếp từ:

```text
data/delta/bronze
```

và ghi ra:

```text
data/delta/silver
```

### 5.1. Silver làm sạch dữ liệu

Silver dùng các hàm trong:

```text
src/common/features.py
```

Các bước chính:

- chuẩn hóa tên cột về một convention thống nhất
- loại bỏ giao dịch lỗi rõ ràng
- loại bỏ dòng trùng theo `txn_id`

### 5.2. Silver tạo feature

Silver tạo các đặc trưng phục vụ cả AI lẫn luật nghiệp vụ, ví dụ:

- `error_balance_orig`
- `error_balance_dest`
- `amount_ratio`
- `is_zero_balance_after`
- `is_large_amount`
- `hour`
- `type_index`

Ý nghĩa:

- giúp dữ liệu có cấu trúc rõ ràng hơn
- giúp Gold và model AI có input nhất quán

### 5.3. Silver áp dụng rule engine

Silver dùng các hàm trong:

```text
src/common/rules.py
```

Các luật chính:

1. `rule_blacklist`
   Giao dịch có tài khoản nguồn hoặc đích nằm trong danh sách đen.

2. `rule_large_txn`
   Giao dịch `TRANSFER` hoặc `CASH_OUT` có số tiền lớn hơn ngưỡng cấu hình.

3. `rule_drain`
   Giao dịch làm tài khoản nguồn bị rút về 0.

4. `rule_blacklist_burst`
   Một tài khoản nguồn chuyển liên tục vào blacklist trong cùng một `step`.

Silver cũng tính thêm:

- `rule_score`
- `rule_score_normalized`
- `rule_alert`

Đây là kết quả rule-based detection ở mức trung gian.

### 5.4. Ý nghĩa của Silver

Silver là nơi:

- dữ liệu được làm sạch
- dữ liệu được enrich bằng feature engineering
- luật nghiệp vụ bắt đầu phát hiện rủi ro

Nói cách khác, Silver là tầng biến dữ liệu thô thành dữ liệu “có thể phân tích”.

---

## 6. Gold

Job:

```text
src/jobs/gold_stream.py
```

Gold đọc từ:

```text
data/delta/silver
```

và tạo ra các đầu ra cuối cùng ở:

```text
data/delta/gold_scored
data/delta/gold_alerts
data/delta/gold_metrics
data/reports/*
```

### 6.1. Gold kết hợp AI và Rule

Gold là tầng ra quyết định cuối cùng.

Khi một batch từ Silver đi vào Gold:

1. Gold load model đã huấn luyện sẵn từ:

```text
data/delta/model
```

2. Gold tách dữ liệu thành 2 nhóm:

- nhóm có dùng AI:
  - `TRANSFER`
  - `CASH_OUT`
- nhóm không dùng AI:
  - các loại giao dịch còn lại

3. Với nhóm có AI, Gold sinh:

- `ml_probability`
- `ml_prediction`

4. Với nhóm không dùng AI, Gold gán:

- `ml_probability = 0`
- `ml_prediction = 0`

5. Gold trộn điểm AI với điểm rule để tạo:

```text
composite_score = ml_probability * 0.7 + rule_score_normalized * 0.3
```

6. Gold sinh cờ cảnh báo cuối cùng:

- nếu `composite_score` vượt ngưỡng
- hoặc chạm blacklist
- hoặc vi phạm rule chuyển liên tục vào blacklist

Kết quả:

- `final_alert`
- `alert_reason`

### 6.2. Gold tạo những bảng gì

#### `gold_scored`

Toàn bộ giao dịch đã được chấm điểm.

Nơi này lưu:

- điểm AI
- điểm luật
- điểm tổng hợp
- cờ cảnh báo cuối

#### `gold_alerts`

Chỉ giữ các giao dịch bị cảnh báo.

Bảng này rất quan trọng khi demo vì có thể dùng để:

- mở ra cho giảng viên xem các giao dịch đáng ngờ
- giải thích lý do vì sao hệ thống gắn cờ

#### `gold_metrics`

Bảng thống kê tổng hợp theo loại giao dịch.

Dùng để:

- nhìn tổng thể số giao dịch
- số fraud
- số alert
- điểm trung bình

---

## 7. Kết quả AI nằm ở đâu

Phần AI trong hệ thống có **2 giai đoạn tách biệt**:

### 7.1. AI offline

Nơi train model:

```text
src/jobs/train_model.py
```

Đầu ra:

- `data/delta/model`
- `data/reports/training_metrics.json`
- `data/reports/training_curves.png`

Ý nghĩa:

- đây là phần chứng minh mô hình học máy có chất lượng
- dùng cho báo cáo và giải trình

### 7.2. AI online

Nơi dùng model trong streaming:

```text
src/jobs/gold_stream.py
```

Vai trò:

- load model đã train trước
- chấm điểm từng batch đi vào Gold
- tạo `ml_probability` và `ml_prediction`
- kết hợp với rule để ra `final_alert`

Điểm quan trọng:

- AI **không chạy độc lập**
- AI được dùng như một phần của hệ thống **hybrid detection**

---

## 8. Streaming chạy như thế nào

Đây là phần quan trọng nhất để demo.

### 8.1. Các tiến trình cần chạy

Thông thường sẽ có 4 cửa sổ:

1. `bronze_stream`
2. `silver_stream`
3. `gold_stream`
4. `simulate_stream`

### 8.2. Trình tự hoạt động

#### Bước 1

`bronze_stream`, `silver_stream`, `gold_stream` được bật trước để đứng chờ dữ liệu.

#### Bước 2

`simulate_stream` bắt đầu đẩy từng batch CSV vào `data/stream_input/`.

#### Bước 3

Bronze phát hiện file mới, ingest vào `data/delta/bronze`.

#### Bước 4

Silver đọc batch mới từ Bronze, làm sạch dữ liệu, tạo feature và áp rule, sau đó ghi vào `data/delta/silver`.

#### Bước 5

Gold đọc batch mới từ Silver, dùng model AI để chấm điểm, hợp nhất với điểm luật, rồi sinh cảnh báo cuối.

#### Bước 6

Gold cập nhật các đầu ra cho demo và báo cáo:

- `gold_scored`
- `gold_alerts`
- `gold_metrics`
- `latest_gold_batch.json`
- `evaluation_summary.csv`
- `top_risk_accounts.csv`
- `dashboard.png`

### 8.3. Tại sao gọi là near real-time

Hệ thống này dùng:

- Spark Structured Streaming
- trigger theo thời gian
- micro-batch

Vì vậy, đây là:

```text
near real-time theo micro-batch
```

chứ không phải stream mức mili-giây từng bản ghi.

Đây là câu nên dùng khi giảng viên hỏi sâu.

---

## 9. Kết quả cuối cùng của hệ thống

Sau khi pipeline chạy xong, nhóm có thể trình bày các đầu ra sau:

### 9.1. Bảng Delta

- `data/delta/gold_scored`
- `data/delta/gold_alerts`
- `data/delta/gold_metrics`

### 9.2. File báo cáo

- `data/reports/training_metrics.json`
- `data/reports/training_curves.png`
- `data/reports/evaluation_summary.csv`
- `data/reports/top_risk_accounts.csv`
- `data/reports/latest_gold_batch.json`
- `data/reports/dashboard.png`

### 9.3. Dashboard web

Dashboard web đọc từ `data/reports` để trình bày:

- batch mới nhất
- số cảnh báo
- chất lượng mô hình
- bảng so sánh rule, AI, hybrid
- top tài khoản rủi ro
- ảnh dashboard tổng hợp

---

## 10. Cách giải thích ngắn gọn khi bảo vệ

Có thể nói ngắn gọn như sau:

> Nhóm em tách hệ thống thành 2 phần. Phần offline dùng để chuẩn bị blacklist và huấn luyện mô hình AI từ dữ liệu lịch sử PaySim. Phần online dùng Spark Structured Streaming để mô phỏng dữ liệu đi vào theo từng micro-batch. Dữ liệu đi qua Bronze để ingest, qua Silver để làm sạch, tạo feature và áp luật nghiệp vụ, rồi vào Gold để kết hợp điểm rule và điểm AI thành cảnh báo cuối cùng. Kết quả cuối được lưu vào các bảng Delta và các file report để demo trên dashboard.

---

## 11. Kết luận

Luồng xử lý của đồ án có thể tóm lại thành 3 ý:

1. **Trước Bronze**
   Chuẩn bị dữ liệu tham chiếu và mô hình AI.

2. **Bronze → Silver → Gold**
   Dữ liệu được ingest, làm sạch, enrich, áp rule, chấm điểm AI và sinh cảnh báo.

3. **Kết quả cuối**
   Hệ thống sinh cả bảng Delta lẫn file báo cáo để phục vụ demo, dashboard và giải trình.
