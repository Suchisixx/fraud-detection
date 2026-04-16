# README_DATA

## 1. Mục đích của tài liệu 

Tài liệu dùng để giải trình phần **dữ liệu, luồng lưu trữ, xử lý, tối ưu hóa, giám sát và thuật toán nòng cốt** của đồ án phát hiện gian lận thời gian thực với bộ dữ liệu **PaySim**.

Đây là phần nên dùng khi cho các câu như:

- Nhóm lấy dữ liệu từ đâu
- Dữ liệu có định dạng gì
- Schema của dữ liệu là gì
- Hệ thống lưu dữ liệu theo quy trình nào
- Dùng kiểu lưu trữ nào, chia tầng dữ liệu ra sao
- Dữ liệu được xử lý như thế nào
- Nhóm tối ưu hệ thống bằng cách nào
- Nhóm giám sát pipeline ở đâu
- Thuật toán lõi là gì
- Khối lượng dữ liệu đã xử lý là bao nhiêu
- Ước lượng thời gian chạy như thế nào

## 2. Nguồn dữ liệu

### 2.1. Bộ dữ liệu sử dụng

Nhóm sử dụng bộ dữ liệu **PaySim** từ Kaggle.

PaySim là bộ dữ liệu mô phỏng giao dịch tài chính số, thường được dùng để nghiên cứu:

- phát hiện gian lận giao dịch
- phát hiện rửa tiền
- phát hiện hành vi bất thường trong ví điện tử

### 2.2. Lý do chọn PaySim

Nhóm chọn PaySim vì:

- dữ liệu phù hợp bài toán giao dịch ví điện tử
- có nhãn gian lận `isFraud`
- có thể mô phỏng phát hiện gian lận theo thời gian thực bằng Spark Streaming
- đủ lớn để thể hiện kiến trúc dữ liệu và tối ưu xử lý

### 2.3. Giới hạn của dữ liệu

PaySim **không có dữ liệu đăng nhập**, không có:

- IP đăng nhập
- thiết bị đăng nhập
- vị trí đăng nhập
- sinh trắc học

Vì vậy đồ án **không tuyên bố phát hiện đăng nhập lạ từ dữ liệu nguồn**, mà tập trung vào:

- phát hiện giao dịch bất thường
- phát hiện giao dịch liên quan blacklist
- phát hiện chuyển tiền liên tục vào blacklist
- phát hiện giao dịch rủi ro cao bằng mô hình lai

## 3. Định dạng dữ liệu

### 3.1. Kiểu file đầu vào

Dữ liệu nguồn đầu vào là:

- **file CSV**

Đường dẫn chuẩn trong dự án:

```text
data/raw/paysim.csv
```

### 3.2. Định dạng lưu trữ trong pipeline

Sau khi vào hệ thống, dữ liệu không còn chỉ ở dạng CSV mà được lưu theo **Delta Lake** ở các tầng:

- Bronze
- Silver
- Gold

Các bảng Delta được lưu trong:

```text
data/delta/
```

### 3.3. Lợi ích của Delta Lake

Nhóm chọn Delta Lake vì:

- phù hợp với Spark
- hỗ trợ lưu dữ liệu dạng bảng
- có checkpoint và transaction log
- dễ tổ chức theo kiến trúc nhiều tầng
- thuận tiện cho việc đọc lại, demo và giải trình

## 4. Schema dữ liệu

### 4.1. Schema dữ liệu gốc

Schema dữ liệu gốc được định nghĩa rõ trong file:

- [src/common/schemas.py](<D:/Download/files (4)/src/common/schemas.py:1>)

Các cột chính:

- `step`: thời điểm nghiệp vụ trong dữ liệu mô phỏng
- `type`: loại giao dịch
- `amount`: số tiền giao dịch
- `nameOrig`: tài khoản nguồn
- `oldbalanceOrg`: số dư nguồn trước giao dịch
- `newbalanceOrig`: số dư nguồn sau giao dịch
- `nameDest`: tài khoản đích
- `oldbalanceDest`: số dư đích trước giao dịch
- `newbalanceDest`: số dư đích sau giao dịch
- `isFraud`: nhãn gian lận
- `isFlaggedFraud`: cờ gian lận được đánh dấu sẵn trong dữ liệu

### 4.2. Kiểu dữ liệu

Nhóm không để Spark tự đoán schema mà khai báo rõ:

- `IntegerType`
- `DoubleType`
- `StringType`
- `TimestampType`

Việc này giúp:

- đọc dữ liệu ổn định hơn
- tránh sai kiểu
- dễ giải trình với giảng viên

### 4.3. Schema sau xử lý

Khi vào Bronze, Silver, Gold, dữ liệu được mở rộng thêm các cột như:

- `txn_id`
- `ingested_at`
- `source_file`
- `error_balance_orig`
- `error_balance_dest`
- `amount_ratio`
- `is_zero_balance_after`
- `is_large_amount`
- `hour`
- `type_index`
- `rule_blacklist`
- `rule_large_txn`
- `rule_drain`
- `rule_blacklist_burst`
- `rule_score`
- `rule_score_normalized`
- `rule_alert`
- `ml_probability`
- `ml_prediction`
- `composite_score`
- `final_alert`
- `alert_reason`

## 5. Khối lượng dữ liệu

### 5.1. Dữ liệu gốc

Theo log thực tế của nhóm:

- tổng số dòng dữ liệu: **1,048,575**
- số dòng gian lận: **1,142**
- tỷ lệ gian lận: khoảng **0.11%**

Đây là dữ liệu **mất cân bằng mạnh**, nên phù hợp để trình bày bài toán fraud detection thực tế.

### 5.2. Dữ liệu dùng khi demo realtime

Trong demo, nhóm không đẩy toàn bộ 1 triệu dòng cùng lúc mà mô phỏng streaming:

- số batch: **15**
- mỗi batch: **500 dòng**
- tổng dữ liệu demo: **7,500 dòng**

Cấu hình hiện tại:

- mỗi batch gồm khoảng `75` dòng gian lận
- và `425` dòng bình thường

Việc tăng tỷ lệ gian lận khi demo giúp:

- dễ quan sát cảnh báo hơn
- dễ trình bày kết quả trên dashboard
- không làm thay đổi dữ liệu gốc, chỉ thay đổi cách lấy mẫu demo

## 6. Luồng quy trình lưu dữ liệu

### 6.1. Tổng quan luồng dữ liệu

```text
PaySim CSV
   ↓
data/raw/paysim.csv
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
   ↓
data/delta/gold_alerts
data/delta/gold_metrics
```

### 6.2. Giải thích từng tầng

#### Tầng Raw

Nơi lưu dữ liệu gốc chưa xử lý:

```text
data/raw/paysim.csv
```

Mục đích:

- giữ bản dữ liệu đầu vào
- làm nguồn huấn luyện
- làm nguồn mô phỏng streaming

#### Tầng Stream Input

```text
data/stream_input/
```

Mục đích:

- simulator chia dữ liệu thành các lô nhỏ
- mỗi lô được ghi thành file CSV riêng
- Bronze stream đọc từng file như dữ liệu đến theo thời gian thực

#### Tầng Bronze

```text
data/delta/bronze
```

Mục đích:

- nhận dữ liệu gần như nguyên bản từ streaming input
- chuẩn hóa tên cột
- gắn thêm `txn_id`, `ingested_at`, `source_file`

Bronze là tầng ingest dữ liệu, chưa áp dụng logic nghiệp vụ sâu.

#### Tầng Silver

```text
data/delta/silver
```

Mục đích:

- làm sạch dữ liệu
- loại dữ liệu lỗi
- loại trùng
- tạo đặc trưng
- áp dụng luật nghiệp vụ

Silver là tầng phân tích nghiệp vụ chính.

#### Tầng Gold

```text
data/delta/gold_scored
data/delta/gold_alerts
data/delta/gold_metrics
```

Mục đích:

- chấm điểm bằng mô hình học máy
- kết hợp điểm luật và điểm mô hình
- tạo cảnh báo cuối cùng
- tạo bảng thống kê phục vụ báo cáo

### 6.3. Dữ liệu tham chiếu

Ngoài luồng chính, dự án có dữ liệu tham chiếu:

```text
data/reference/blacklist_seed.csv
```

Mục đích:

- lưu seed ban đầu cho danh sách đen
- tránh tạo blacklist động trong luồng online
- tránh label leakage khi giải trình

## 7. Quy trình xử lý dữ liệu

### 7.1. Bước 1: Nạp dữ liệu

Spark đọc file CSV với schema cố định, không dùng infer schema.

### 7.2. Bước 2: Chuẩn hóa cột

Một số cột được đổi tên từ kiểu gốc sang kiểu đồng nhất trong hệ thống:

- `nameOrig` -> `nameorig`
- `nameDest` -> `namedest`
- `isFraud` -> `isfraud`
- `isFlaggedFraud` -> `isflaggedfraud`

### 7.3. Bước 3: Tạo khóa giao dịch

Hệ thống tạo `txn_id` từ các trường chính của giao dịch để:

- định danh giao dịch
- chống trùng
- hỗ trợ theo dõi qua các tầng dữ liệu

### 7.4. Bước 4: Làm sạch dữ liệu

Các bước làm sạch:

- bỏ giao dịch có `amount <= 0`
- bỏ dòng thiếu tài khoản nguồn hoặc đích
- loại trùng theo `txn_id`

### 7.5. Bước 5: Tạo đặc trưng

Các đặc trưng quan trọng:

- `error_balance_orig`
- `error_balance_dest`
- `amount_ratio`
- `is_zero_balance_after`
- `is_large_amount`
- `hour`
- `type_index`

### 7.6. Bước 6: Áp dụng luật nghiệp vụ

Các luật:

- giao dịch chạm danh sách đen
- giao dịch lớn bất thường
- giao dịch làm cạn tài khoản
- giao dịch liên tục vào blacklist

### 7.7. Bước 7: Chấm điểm mô hình

Gold stream tải mô hình đã huấn luyện và tính:

- `ml_probability`
- `ml_prediction`

### 7.8. Bước 8: Kết hợp điểm

Điểm cuối được tính:

```text
composite_score = ml_probability * 0.7 + rule_score_normalized * 0.3
```

Sau đó sinh:

- `final_alert`
- `alert_reason`

## 8. Thuật toán nòng cốt

### 8.1. Thành phần thuật toán

Phần nòng cốt của đồ án không chỉ là một mô hình duy nhất mà là **mô hình lai** gồm:

- luật nghiệp vụ
- mô hình học máy Random Forest

### 8.2. Tại sao không chỉ dùng học máy

Nếu chỉ dùng học máy:

- khó giải thích nhanh trong phần demo
- một số trường hợp blacklist cần chặn ngay theo luật
- khó trình bày tính nghiệp vụ

Nếu chỉ dùng luật:

- bỏ sót các mẫu gian lận phức tạp
- khó mở rộng khi hành vi gian lận thay đổi

### 8.3. Thuật toán máy học

Mô hình đang dùng:

- `RandomForestClassifier`

Lý do chọn:

- phù hợp dữ liệu tabular
- khá ổn định
- dễ giải thích hơn một số mô hình phức tạp
- chạy được trên môi trường local demo

### 8.4. Điểm mạnh của mô hình lai

- luật giúp phản ứng nhanh với mẫu rõ ràng
- mô hình giúp nhận ra mẫu gian lận phi tuyến
- điểm tổng hợp giúp cân bằng giữa độ chính xác và khả năng bao phủ

## 9. Tối ưu hóa hệ thống

### 9.1. Tối ưu kiến trúc

Nhóm tách rõ:

- luồng offline: seed blacklist, train model
- luồng online: bronze, silver, gold

Điều này giúp:

- giảm tải cho phần realtime
- dễ demo
- dễ giải trình

### 9.2. Tối ưu Spark

Trong cấu hình Spark, nhóm đã tối ưu cho local:

- giảm `spark.sql.shuffle.partitions`
- bật `adaptive query execution`
- tắt Spark UI trong môi trường nhẹ
- giảm overhead không cần thiết

### 9.3. Tối ưu lưu trữ

Các bảng Delta được:

- partition theo `type`

Mục tiêu:

- tăng khả năng pruning
- giảm đọc dữ liệu không cần thiết

### 9.4. Tối ưu join

Blacklist là bảng nhỏ nên được:

- `broadcast join`

Điều này giúp:

- giảm chi phí shuffle
- tăng tốc khi áp dụng luật blacklist

### 9.5. Tối ưu demo realtime

Nhóm dùng micro-batch:

- dễ quan sát từng lô dữ liệu
- giúp giảng viên thấy được pipeline đang xử lý theo luồng
- giảm rủi ro quá tải máy local

## 10. Giám sát và lấy thông tin ở đâu

### 10.1. Giám sát trong phạm vi đồ án

Hiện tại nhóm giám sát ở mức application bằng:

- log theo batch trong terminal Bronze
- log theo batch trong terminal Silver
- log theo batch trong terminal Gold
- bảng `gold_metrics`
- file `latest_gold_batch.json`
- dashboard ảnh `dashboard.png`

### 10.2. Các vị trí lấy thông tin

#### Log xử lý

Xem trực tiếp ở terminal khi chạy:

- Bronze
- Silver
- Gold

#### Bảng cảnh báo

```text
data/delta/gold_alerts
```

#### Bảng thống kê

```text
data/delta/gold_metrics
```

#### Dashboard

```text
data/reports/dashboard.png
```

#### Chỉ số huấn luyện

```text
data/reports/training_metrics.json
```

### 10.3. Nếu mở rộng production

Nếu triển khai thực tế, nhóm có thể bổ sung:

- Spark UI
- Prometheus
- Grafana
- log tập trung
- cảnh báo độ trễ pipeline

Nhưng trong phạm vi môn học, nhóm tập trung vào:

- log nghiệp vụ
- bảng metrics
- dashboard đầu ra

## 11. Khối lượng dữ liệu đã xử lý

### 11.1. Khối lượng toàn bộ

Nhóm đã nạp và xử lý:

- hơn **1 triệu dòng dữ liệu gốc**

### 11.2. Khối lượng huấn luyện

Theo log huấn luyện:

- `fraud_train_rows = 1142`
- `normal_train_rows = 459252`

Do dữ liệu mất cân bằng, nhóm lấy mẫu lớp bình thường theo tỷ lệ để huấn luyện hiệu quả hơn.

### 11.3. Khối lượng demo realtime

Trong demo streaming:

- tổng dữ liệu mô phỏng: **7,500 dòng**

## 12. Ước lượng thời gian xử lý

### 12.1. Thời gian mô phỏng streaming

Cấu hình simulator hiện tại:

- 15 batch
- mỗi batch cách nhau khoảng 8 giây

Chỉ riêng phần phát dữ liệu đã mất khoảng:

- `14 x 8 = 112 giây`

Cộng thêm thời gian xử lý ở Bronze, Silver, Gold, toàn bộ demo thường rơi vào:

- khoảng **2 đến 3 phút**

### 12.2. Thời gian huấn luyện

Thời gian huấn luyện phụ thuộc:

- cấu hình máy
- RAM
- số CPU
- tốc độ đọc dữ liệu

Với môi trường local Docker, huấn luyện thường mất từ vài phút trở xuống đến vài phút tùy máy.

### 12.3. Cách trả lời khi bị hỏi

Có thể trả lời:

- “Dữ liệu gốc của nhóm có hơn 1 triệu bản ghi. Khi demo realtime, nhóm mô phỏng 7,500 giao dịch theo 15 micro-batch để đảm bảo trực quan và phù hợp cấu hình local. Tổng thời gian demo khoảng 2 đến 3 phút.”

## 13. Kết quả mô hình

Theo kết quả huấn luyện thực tế:

- `AUC-ROC = 1.0`
- `AUC-PR = 0.9999`
- `Accuracy = 0.9977`
- `Precision = 0.9952`
- `Recall = 0.9904`
- `F1 = 0.9928`

### 13.1. Cách giải thích kết quả cao

Nhóm nên giải thích:

- PaySim là dữ liệu mô phỏng nên mẫu gian lận khá rõ
- vì vậy mô hình có thể đạt điểm rất cao
- trong thực tế production, dữ liệu sẽ nhiễu hơn và khó hơn
- giá trị đồ án nằm ở cả kiến trúc streaming và mô hình lai, không chỉ ở con số accuracy

## 14. Câu trả lời mẫu ngắn gọn khi bảo vệ

### 14.1. Về nguồn dữ liệu

“Nhóm em sử dụng bộ dữ liệu PaySim từ Kaggle, dữ liệu dạng CSV, mô phỏng giao dịch ví điện tử và có nhãn gian lận.”

### 14.2. Về schema

“Nhóm em khai báo schema rõ ràng bằng Spark thay vì để hệ thống tự suy đoán, giúp dữ liệu ổn định và dễ kiểm soát kiểu dữ liệu.”

### 14.3. Về quy trình lưu trữ

“Nhóm em tổ chức dữ liệu theo kiến trúc Bronze-Silver-Gold trên Delta Lake. Bronze là dữ liệu ingest, Silver là dữ liệu sạch và đã tạo đặc trưng, Gold là dữ liệu đã chấm điểm và sinh cảnh báo.”

### 14.4. Về xử lý dữ liệu

“Hệ thống chuẩn hóa dữ liệu, loại trùng, tạo khóa giao dịch, sinh đặc trưng, áp luật nghiệp vụ, sau đó dùng mô hình Random Forest và điểm lai để ra cảnh báo cuối cùng.”

### 14.5. Về tối ưu

“Nhóm em tối ưu bằng cách partition bảng theo loại giao dịch, giảm shuffle partitions cho local, dùng broadcast join với blacklist nhỏ và tách phần huấn luyện khỏi phần realtime.”

### 14.6. Về giám sát

“Trong phạm vi đồ án, nhóm em giám sát bằng log theo batch, bảng metrics tổng hợp và dashboard đầu ra.”

### 14.7. Về thuật toán

“Thuật toán nòng cốt là mô hình lai giữa rule-based và Random Forest. Luật giúp bám sát nghiệp vụ, còn Random Forest học các mẫu gian lận phức tạp hơn.”

### 14.8. Về khối lượng dữ liệu

“Nhóm em xử lý hơn 1 triệu bản ghi dữ liệu gốc. Khi demo realtime, nhóm em dùng 15 micro-batch với tổng 7,500 giao dịch.”

## 15. Những gì dự án đã có và những gì còn có thể mở rộng

### 15.1. Dự án đã có

- dữ liệu nguồn rõ ràng
- schema rõ ràng
- kiến trúc Bronze-Silver-Gold
- pipeline realtime
- blacklist
- feature engineering
- mô hình máy học
- dashboard
- bảng cảnh báo và metrics

### 15.2. Có thể mở rộng thêm nếu cần

- dashboard realtime tương tác
- giám sát hạ tầng bằng Grafana
- thêm dữ liệu đăng nhập để xử lý anomaly đăng nhập thật
- thêm lưu lịch sử model và thời gian huấn luyện chi tiết

## 16. Kết luận

Từ góc nhìn dữ liệu, đồ án đã có đủ các thành phần quan trọng để trả lời câu hỏi cuối kì:

- dữ liệu lấy từ đâu
- định dạng và schema là gì
- pipeline lưu dữ liệu ra sao
- dữ liệu được xử lý như thế nào
- hệ thống tối ưu thế nào
- phần giám sát nằm ở đâu
- thuật toán nòng cốt là gì
- đã xử lý bao nhiêu dữ liệu
- thời gian xử lý ước lượng bao lâu

Tài liệu này có thể dùng trực tiếp để ôn phần hỏi đáp khi bảo vệ.
