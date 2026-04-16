# README Preprocessing

## 1. Mục đích tài liệu

Tài liệu này dùng để giải thích riêng phần **tiền xử lý dữ liệu** trong đồ án phát hiện gian lận với PaySim.

Mục tiêu là làm rõ:

- dữ liệu gốc của dự án là gì
- trước khi đưa vào AI và rule thì dữ liệu được xử lý như thế nào
- tại sao phải có bước tiền xử lý
- mỗi bước tiền xử lý ảnh hưởng ra sao tới kết quả cuối

Tài liệu này bám đúng vào code hiện tại của dự án.

---

## 2. Dữ liệu gốc của dự án

Nguồn dữ liệu đầu vào chính là bộ:

- **PaySim**

File gốc trong dự án:

```text
data/raw/paysim.csv
```

Schema gốc được khai báo ở:

- [src/common/schemas.py](<D:/Download/files (4)/src/common/schemas.py:13>)

Các cột đầu vào chính:

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

Đây là dữ liệu giao dịch ví điện tử mô phỏng, nhưng ở trạng thái ban đầu nó vẫn là dữ liệu thô, chưa phù hợp để:

- chạy rule engine
- huấn luyện AI
- dùng trực tiếp trong streaming pipeline

Vì vậy dự án cần một lớp tiền xử lý rõ ràng.

---

## 3. Vì sao phải tiền xử lý dữ liệu

Nếu dùng dữ liệu PaySim thô ngay lập tức, hệ thống sẽ gặp một số vấn đề:

- tên cột chưa thống nhất giữa các tầng
- có thể có dòng không hợp lệ cho bài toán giao dịch
- có thể có dòng trùng
- mô hình AI chưa có đủ đặc trưng để học
- rule engine chưa có dữ liệu ở dạng thuận tiện để áp dụng

Nói ngắn gọn:

- dữ liệu thô mới chỉ là **nguyên liệu**
- tiền xử lý là bước biến nguyên liệu đó thành **dữ liệu sẵn sàng cho phân tích và phát hiện gian lận**

---

## 4. Tiền xử lý trong dự án diễn ra ở đâu

Phần tiền xử lý nằm chủ yếu ở:

- [src/common/features.py](<D:/Download/files (4)/src/common/features.py:1>)
- [src/jobs/bronze_stream.py](<D:/Download/files (4)/src/jobs/bronze_stream.py:1>)
- [src/jobs/silver_stream.py](<D:/Download/files (4)/src/jobs/silver_stream.py:1>)

Luồng tiền xử lý:

```text
PaySim gốc
   ↓
đọc bằng schema cố định
   ↓
chuẩn hóa tên cột
   ↓
tạo txn_id và metadata
   ↓
làm sạch dữ liệu
   ↓
tạo đặc trưng
   ↓
áp dụng rule nghiệp vụ
```

---

## 5. Bước 1: Đọc dữ liệu bằng schema cố định

### 5.1. Cách làm trong dự án

Khi dữ liệu được đưa vào hệ thống, Spark không tự đoán schema mà dùng schema cố định:

- [PAYSIM_SCHEMA](<D:/Download/files (4)/src/common/schemas.py:13>)

Ví dụ:

- `step` là `IntegerType`
- `amount` là `DoubleType`
- `type` là `StringType`
- `isFraud` là `IntegerType`

### 5.2. Ý nghĩa

Bước này giúp:

- tránh việc Spark infer schema sai
- đảm bảo các batch stream có cấu trúc thống nhất
- giảm rủi ro lỗi kiểu dữ liệu ở Bronze, Silver, Gold
- dễ giải trình với giảng viên hơn

### 5.3. Vì sao đây là tiền xử lý

Vì ngay tại bước đầu vào, dự án đã chuẩn hóa cách hiểu dữ liệu.

Đây là bước tiền xử lý ở mức:

- **schema preprocessing**

---

## 6. Bước 2: Chuẩn hóa tên cột

### 6.1. Cách làm trong dự án

Hàm:

- [normalize_transaction_columns](<D:/Download/files (4)/src/common/features.py:37>)

thực hiện đổi tên cột từ chuẩn gốc của PaySim sang chuẩn thống nhất trong nội bộ hệ thống.

Ví dụ:

- `nameOrig` → `nameorig`
- `oldbalanceOrg` → `oldbalanceorig`
- `newbalanceOrig` → `newbalanceorig`
- `nameDest` → `namedest`
- `isFraud` → `isfraud`
- `isFlaggedFraud` → `isflaggedfraud`

### 6.2. Ý nghĩa

Nếu không đổi tên cột ngay từ đầu, từng module sẽ phải tự nhớ tên cột gốc khác nhau, rất dễ dẫn tới:

- sai column name
- lệch logic giữa train và streaming
- lỗi khi join hoặc khi tính feature

Sau khi chuẩn hóa, toàn bộ pipeline dùng chung một convention.

### 6.3. Đây là loại tiền xử lý gì

Đây là:

- **structural preprocessing**

tức là chuẩn hóa cấu trúc dữ liệu trước khi xử lý sâu hơn.

---

## 7. Bước 3: Tạo `txn_id` và metadata

### 7.1. Tạo `txn_id`

Trong [features.py](<D:/Download/files (4)/src/common/features.py:49>), hệ thống tạo `txn_id` bằng cách băm nhiều trường chính của giao dịch lại với nhau.

Các trường tham gia gồm:

- `step`
- `type`
- `amount`
- `nameorig`
- `namedest`
- `oldbalanceorig`
- `newbalanceorig`
- `oldbalancedest`
- `newbalancedest`

### 7.2. Ý nghĩa của `txn_id`

`txn_id` dùng để:

- định danh giao dịch
- chống trùng dữ liệu
- theo dõi một giao dịch xuyên suốt từ Bronze đến Gold

### 7.3. Metadata khác

Ở Bronze, hệ thống còn gắn thêm:

- `ingested_at`
- `source_file`

trong:

- [src/jobs/bronze_stream.py](<D:/Download/files (4)/src/jobs/bronze_stream.py:53>)

Ý nghĩa:

- biết giao dịch được ingest lúc nào
- biết nó đến từ file batch nào
- hỗ trợ giám sát pipeline

---

## 8. Bước 4: Làm sạch dữ liệu

### 8.1. Cách làm trong dự án

Hàm:

- [clean_transactions](<D:/Download/files (4)/src/common/features.py:71>)

thực hiện các bước làm sạch sau:

1. bỏ giao dịch có `amount <= 0`
2. bỏ dòng thiếu tài khoản nguồn `nameorig`
3. bỏ dòng thiếu tài khoản đích `namedest`
4. loại bỏ dòng trùng theo `txn_id`

### 8.2. Ý nghĩa từng bước

#### Bỏ giao dịch có `amount <= 0`

Những giao dịch như vậy không phù hợp với ngữ nghĩa thông thường của bài toán chuyển tiền và có thể làm nhiễu rule hoặc model.

#### Bỏ dòng thiếu tài khoản nguồn hoặc đích

Nếu thiếu `nameorig` hoặc `namedest` thì:

- không thể kiểm tra blacklist đúng
- không thể phân tích quan hệ giao dịch
- không đủ thông tin để giải thích alert

#### Loại trùng theo `txn_id`

Điều này giúp:

- tránh một giao dịch bị tính nhiều lần
- tránh tăng giả số alert
- tránh sai lệch metric đánh giá

### 8.3. Điểm đáng chú ý

Hệ thống hiện tại **không điền giá trị thiếu bằng mean/median**, mà chủ yếu loại bỏ các dòng không đủ điều kiện nghiệp vụ.

Đây là lựa chọn hợp lý với bài toán fraud transaction, vì:

- việc điền bừa số dư hoặc tài khoản có thể tạo tín hiệu giả
- dữ liệu giao dịch tài chính thường cần sự nhất quán cao

---

## 9. Bước 5: Tạo đặc trưng

Đây là phần rất quan trọng trong tiền xử lý.

Hàm:

- [add_feature_columns](<D:/Download/files (4)/src/common/features.py:87>)

### 9.1. Các đặc trưng được tạo

#### `error_balance_orig`

```text
oldbalanceorig - amount - newbalanceorig
```

Ý nghĩa:

- đo sai lệch cân bằng số dư phía tài khoản nguồn
- giúp phát hiện giao dịch bất thường về mặt số dư

#### `error_balance_dest`

```text
newbalancedest - oldbalancedest - amount
```

Ý nghĩa:

- đo sai lệch cân bằng ở tài khoản đích
- hỗ trợ phát hiện hành vi bất thường trong luồng tiền

#### `amount_ratio`

```text
amount / (oldbalanceorig + 1)
```

Ý nghĩa:

- thể hiện số tiền giao dịch lớn tới mức nào so với số dư ban đầu
- đây là tín hiệu quan trọng cho hành vi rút mạnh hoặc chuyển tiền bất thường

#### `is_zero_balance_after`

Ý nghĩa:

- kiểm tra sau giao dịch, tài khoản nguồn có bị rút về 0 hay không
- rất hữu ích cho fraud pattern kiểu rút cạn tài khoản

#### `is_large_amount`

Ý nghĩa:

- biến ngưỡng số tiền lớn thành cờ nhị phân
- giúp rule engine và model dễ dùng hơn

#### `hour`

```text
step % 24
```

Ý nghĩa:

- chuyển `step` sang khái niệm gần với giờ trong ngày
- giúp mô hình nhìn được tín hiệu thời điểm giao dịch

#### `type_index`

Ý nghĩa:

- mã hóa loại giao dịch từ chuỗi sang số
- giúp mô hình AI có thể dùng biến `type`

### 9.2. Đây là loại tiền xử lý gì

Đây là:

- **feature engineering preprocessing**

Nghĩa là không chỉ làm sạch, mà còn biến dữ liệu thành dạng có ý nghĩa hơn cho fraud detection.

---

## 10. Bước 6: Áp dụng rule nghiệp vụ như một lớp enrich dữ liệu

Sau khi làm sạch và tạo feature, hệ thống tiếp tục áp dụng rule trong:

- [src/common/rules.py](<D:/Download/files (4)/src/common/rules.py:100>)

Các cột mới được thêm vào:

- `rule_blacklist`
- `rule_large_txn`
- `rule_drain`
- `rule_blacklist_burst`
- `rule_score`
- `rule_score_normalized`
- `rule_alert`

### Ý nghĩa

Bước này biến một giao dịch từ dạng:

- “đã sạch”

thành dạng:

- “đã được diễn giải theo ngữ nghĩa gian lận”

Đây cũng có thể xem là một lớp tiền xử lý ở mức:

- **business preprocessing**

---

## 11. Tiền xử lý cho AI offline

Phần train model ở:

- [src/jobs/train_model.py](<D:/Download/files (4)/src/jobs/train_model.py:49>)

không tự viết một pipeline preprocessing riêng, mà dùng lại chính:

- `build_silver_frame()`
- `apply_rule_engine()`

Điểm này rất tốt vì:

- giữ preprocessing giống nhau giữa offline và online
- tránh tình trạng train một kiểu, lúc chạy thật lại xử lý kiểu khác

Ngoài ra, trước khi train model còn có thêm các bước:

### 11.1. Chỉ giữ loại giao dịch trọng tâm

Model AI chỉ học trên:

- `TRANSFER`
- `CASH_OUT`

Lý do:

- đây là các loại giao dịch có ý nghĩa fraud rõ hơn trong PaySim

### 11.2. Cân bằng dữ liệu

Vì fraud rất ít nên hệ thống lấy mẫu lại lớp âm để giảm mất cân bằng.

Ý nghĩa:

- tránh model chỉ học dự đoán “không fraud”
- tăng khả năng học được tín hiệu fraud

### 11.3. Chuẩn bị vector cho model

Hệ thống dùng:

- `VectorAssembler`
- `StandardScaler`

để chuyển các feature thành đầu vào chuẩn cho Random Forest pipeline.

---

## 12. Tóm tắt các lớp tiền xử lý trong dự án

Có thể chia phần preprocessing của dự án thành 5 lớp:

### 12.1. Schema preprocessing

- khai báo schema rõ ràng

### 12.2. Structural preprocessing

- đổi tên cột
- tạo `txn_id`
- thêm metadata

### 12.3. Cleaning preprocessing

- bỏ dòng không hợp lệ
- bỏ thiếu nguồn/đích
- bỏ trùng

### 12.4. Feature preprocessing

- tạo feature từ số dư, amount, type, thời gian

### 12.5. Business preprocessing

- áp dụng luật nghiệp vụ
- biến dữ liệu thành dạng có ý nghĩa fraud

---

## 13. Điểm mạnh và giới hạn của phần tiền xử lý

### 13.1. Điểm mạnh

- schema rõ ràng
- logic preprocess dùng chung cho train và streaming
- có chống trùng
- có feature engineering gắn với nghiệp vụ
- không chỉ làm sạch kỹ thuật mà còn enrich nghiệp vụ

### 13.2. Giới hạn

- chưa có bước imputation phức tạp cho missing numeric
- chưa có encoding nâng cao ngoài `type_index`
- chưa có pipeline xử lý outlier riêng biệt
- một số phần vẫn tối ưu cho demo hơn là production scale lớn

---

## 14. Cách nói ngắn gọn khi bảo vệ

Có thể trả lời như sau:

> Trong dự án của nhóm em, tiền xử lý dữ liệu không chỉ là đổi tên cột hay bỏ dòng lỗi. Nhóm em chia preprocessing thành nhiều lớp: đọc dữ liệu bằng schema cố định, chuẩn hóa tên cột, tạo mã giao dịch `txn_id`, loại bỏ giao dịch không hợp lệ và dòng trùng, sau đó tạo các đặc trưng như sai lệch số dư, tỷ lệ số tiền trên số dư, cờ rút cạn tài khoản và giờ giao dịch. Cuối cùng dữ liệu còn được enrich bằng rule nghiệp vụ để vừa phục vụ AI vừa phục vụ cảnh báo theo luật.

---

## 15. Kết luận

Tiền xử lý trong dự án của bạn có vai trò:

- làm cho dữ liệu sạch hơn
- làm cho dữ liệu nhất quán hơn
- làm cho dữ liệu mang ý nghĩa nghiệp vụ hơn
- làm cho dữ liệu dùng được cho cả AI và rule engine

Nói cách khác:

- nếu không có preprocessing, hệ thống chỉ có dữ liệu giao dịch thô
- nhờ preprocessing, hệ thống mới biến dữ liệu đó thành input có thể phát hiện gian lận một cách có cơ sở
