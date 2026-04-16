# README AI And Rule

## 1. Mục đích tài liệu

Tài liệu này giải thích riêng phần:

- **AI trong dự án được huấn luyện ra sao**
- **Rule trong dự án được định nghĩa như thế nào**
- **AI và Rule dựa vào đặc trưng nào của dữ liệu**
- **Gold kết hợp AI và Rule để ra cảnh báo cuối như thế nào**

Tài liệu này giúp nhóm trả lời các câu hỏi như:

- vì sao chọn Random Forest
- AI học từ đâu
- rule dựa vào cơ sở nào
- AI và rule khác nhau ở điểm nào
- vì sao hệ thống không chỉ dùng một trong hai

---

## 2. Bức tranh tổng thể

Khối phát hiện gian lận của dự án là:

```text
Hybrid detection = Rule-based detection + Machine learning detection
```

Nghĩa là hệ thống không chỉ dựa vào AI, cũng không chỉ dựa vào luật.

Thay vào đó:

- **Silver** tạo ra tín hiệu rule
- **Gold** tải model AI và sinh điểm máy học
- **Gold** trộn hai phần này thành điểm cuối

---

## 3. Phần Rule trong dự án

### 3.1. Rule nằm ở đâu

Rule engine được định nghĩa trong:

- [src/common/rules.py](<D:/Download/files (4)/src/common/rules.py:100>)

Rule được áp dụng chủ yếu ở:

- [src/jobs/silver_stream.py](<D:/Download/files (4)/src/jobs/silver_stream.py:40>)

### 3.2. Rule dựa vào đâu

Rule của hệ thống dựa trên:

1. **kiến thức nghiệp vụ**
2. **đặc điểm của bộ dữ liệu PaySim**
3. **mục tiêu của đề tài fraud detection**

Nói cách khác:

- rule không học từ dữ liệu như AI
- rule là những điều kiện được định nghĩa trước bằng logic nghiệp vụ

### 3.3. Các rule hiện có

#### Rule 1: `rule_blacklist`

Ý nghĩa:

- giao dịch có tài khoản nguồn hoặc tài khoản đích nằm trong danh sách đen

Cơ sở:

- trong thực tế, tài khoản đã nằm trong blacklist là tín hiệu rủi ro rất mạnh
- đây là rule dễ giải thích nhất khi bảo vệ

Rule này dùng:

- `nameorig`
- `namedest`
- bảng tham chiếu blacklist

#### Rule 2: `rule_large_txn`

Ý nghĩa:

- giao dịch `TRANSFER` hoặc `CASH_OUT` có số tiền lớn hơn ngưỡng cấu hình (200,000)

Cơ sở:

- giao dịch giá trị lớn thường là tín hiệu cần ưu tiên kiểm soát
- đặc biệt với loại giao dịch liên quan chuyển tiền ra ngoài hoặc rút tiền

Rule này dùng:

- `type`
- `amount`
- ngưỡng `LARGE_TXN_THRESHOLD`

#### Rule 3: `rule_drain`

Ý nghĩa:

- giao dịch làm số dư tài khoản nguồn về 0

Cơ sở:

- hành vi rút cạn tài khoản thường đáng nghi trong fraud scenarios

Rule này dùng:

- `type`
- `oldbalanceorig`
- `newbalanceorig`

#### Rule 4: `rule_blacklist_burst`

Ý nghĩa:

- một tài khoản nguồn chuyển liên tục vào các tài khoản blacklist trong cùng một `step`

Cơ sở:

- đây là pattern hành vi, không chỉ là một giao dịch đơn lẻ
- phù hợp với ý tưởng “chuyển tiền liên tục vào blacklist”

Rule này dùng:

- `nameorig`
- `step`
- `type`
- việc giao dịch có chạm blacklist hay không

### 3.4. Các cột rule sinh ra

Sau khi áp rule engine, dữ liệu có thêm:

- `rule_blacklist`
- `rule_large_txn`
- `rule_drain`
- `rule_blacklist_burst`
- `rule_score`
- `rule_score_normalized`
- `rule_alert`

Ý nghĩa:

- không chỉ biết giao dịch có vi phạm rule nào
- mà còn biết tổng mức độ rủi ro theo rule

### 3.5. Ưu điểm của Rule

- dễ giải thích
- bám sát nghiệp vụ
- phản ứng tốt với pattern rõ ràng
- không cần huấn luyện

### 3.6. Hạn chế của Rule

- khó bắt được các mẫu fraud phức tạp
- nếu hành vi gian lận thay đổi thì rule có thể bỏ sót
- rule thường cứng và phụ thuộc nhiều vào ngưỡng

---

## 4. Phần AI trong dự án

### 4.1. AI nằm ở đâu

Phần huấn luyện nằm ở:

- [src/jobs/train_model.py](<D:/Download/files (4)/src/jobs/train_model.py:74>)

Phần sử dụng model để scoring online nằm ở:

- [src/jobs/gold_stream.py](<D:/Download/files (4)/src/jobs/gold_stream.py:41>)

### 4.2. Mô hình đang dùng

Hệ thống hiện dùng:

- `RandomForestClassifier`

Lý do chọn:

- phù hợp dữ liệu tabular như PaySim
- khá ổn định
- dễ trình bày hơn nhiều mô hình quá phức tạp
- chạy được trong môi trường local demo

### 4.3. AI học từ dữ liệu nào

Model được train từ dữ liệu lịch sử PaySim.

Nếu đã có bảng Silver, hệ thống ưu tiên dùng:

- `data/delta/silver`

Nếu chưa có, job train sẽ:

- đọc `data/raw/paysim.csv`
- chạy lại cùng pipeline preprocessing
- tạo feature
- áp dụng rule dùng chung

Điểm mạnh:

- logic preprocessing của AI nhất quán với logic streaming

### 4.4. AI học trên loại giao dịch nào

Model chỉ học trên:

- `TRANSFER`
- `CASH_OUT`

Lý do:

- đây là 2 loại giao dịch có ý nghĩa fraud rõ nhất trong PaySim
- giúp mô hình tập trung vào nhóm có rủi ro cao hơn

### 4.5. Dữ liệu mất cân bằng được xử lý ra sao

PaySim có tỷ lệ fraud rất thấp.

Vì vậy dự án có bước:

- lấy toàn bộ fraud
- lấy mẫu một phần normal theo tỷ lệ cấu hình

Ý nghĩa:

- giảm mất cân bằng dữ liệu
- giúp model học được fraud pattern tốt hơn

### 4.6. Feature AI dùng là gì

Các feature chính được khai báo trong cấu hình:

- `amount`
- `oldbalanceorig`
- `newbalanceorig`
- `oldbalancedest`
- `newbalancedest`
- `error_balance_orig`
- `error_balance_dest`
- `amount_ratio`
- `is_zero_balance_after`
- `is_large_amount`
- `hour`
- `type_index`

Các feature này dựa vào:

1. số dư trước và sau giao dịch
2. quy mô giao dịch
3. mối quan hệ giữa số tiền và số dư
4. loại giao dịch
5. thời điểm giao dịch
6. các tín hiệu sai lệch cân bằng số dư

### 4.7. Dữ liệu được chuẩn bị cho model như thế nào

Trước khi đưa vào Random Forest, hệ thống dùng:

- `VectorAssembler`
- `StandardScaler`

Vai trò:

- gom các cột đặc trưng thành vector
- chuẩn hóa đầu vào để pipeline machine learning ổn định hơn

### 4.8. AI sinh ra đầu ra gì

Khi chấm điểm ở Gold, model sinh:

- `ml_probability`
- `ml_prediction`

Ý nghĩa:

- `ml_probability`: xác suất giao dịch là fraud theo mô hình
- `ml_prediction`: dự đoán nhị phân của mô hình

---

## 5. AI và Rule dựa vào đặc trưng nào của dữ liệu

### 5.1. Rule dựa vào gì

Rule chủ yếu dựa vào:

- điều kiện logic nghiệp vụ
- blacklist
- amount lớn
- tài khoản bị rút cạn
- hành vi chuyển dồn vào blacklist

Rule nhìn dữ liệu theo kiểu:

- “có vi phạm điều kiện này không?”

### 5.2. AI dựa vào gì

AI dựa vào:

- mẫu thống kê trong dữ liệu
- tổ hợp nhiều feature cùng lúc
- quan hệ phi tuyến giữa amount, số dư, loại giao dịch, thời gian

AI nhìn dữ liệu theo kiểu:

- “giao dịch này có giống các mẫu fraud đã học hay không?”

### 5.3. Điểm khác nhau

Rule:

- rõ ràng
- dễ giải thích
- cứng

AI:

- linh hoạt hơn
- học từ dữ liệu
- bắt được mẫu phức tạp hơn
- khó giải thích hơn rule

---

## 6. Gold kết hợp AI và Rule như thế nào

Đây là phần quan trọng nhất của hệ thống.

Trong Gold:

1. dữ liệu từ Silver đã có `rule_score_normalized`
2. model AI sinh `ml_probability`
3. hệ thống tính:

```text
composite_score = ml_probability * 0.7 + rule_score_normalized * 0.3
```

4. sau đó sinh:

- `final_alert`
- `alert_reason`

### Khi nào `final_alert = 1`

Nếu:

- `composite_score` vượt ngưỡng
- hoặc `rule_blacklist = 1`
- hoặc `rule_blacklist_burst = 1`

Điểm này cho thấy:

- có những trường hợp rule đủ mạnh để chặn trực tiếp
- không phải mọi alert đều chờ AI

---

## 7. AI được đánh giá ra sao

Phần đánh giá offline nằm trong:

- [src/jobs/train_model.py](<D:/Download/files (4)/src/jobs/train_model.py:110>)

Các chỉ số được tính:

- `AUC ROC`
- `AUC PR`
- `Accuracy`
- `Precision`
- `Recall`
- `F1`

Đầu ra:

- `data/reports/training_metrics.json`
- `data/reports/training_curves.png`

Ý nghĩa:

- chứng minh model có chất lượng trên dữ liệu test

Ngoài ra, Gold còn so sánh:

- Rule
- Máy học
- Lai

và lưu ở:

- `data/reports/evaluation_summary.csv`

Điểm này rất quan trọng khi bảo vệ, vì nhóm có thể nói:

- không chỉ train AI rồi để đó
- mà còn so sánh AI với rule và hybrid

---

## 8. Vì sao không chỉ dùng AI hoặc chỉ dùng Rule

### 8.1. Nếu chỉ dùng Rule

Ưu điểm:

- dễ hiểu
- dễ giải thích

Nhược điểm:

- dễ bỏ sót các mẫu gian lận phức tạp
- phụ thuộc ngưỡng cứng

### 8.2. Nếu chỉ dùng AI

Ưu điểm:

- linh hoạt hơn
- học được pattern phức tạp

Nhược điểm:

- khó giải thích
- không phản ứng trực tiếp tốt bằng rule với blacklist rõ ràng

### 8.3. Vì sao chọn Hybrid

Hybrid giúp:

- rule xử lý các mẫu rõ ràng, dễ giải thích
- AI phát hiện các pattern khó hơn
- hệ thống vừa có tính nghiệp vụ vừa có tính học từ dữ liệu

---

## 9. Điểm mạnh và giới hạn của AI và Rule trong dự án

### 9.1. Điểm mạnh

- rule bám sát đề tài blacklist và giao dịch bất thường
- AI có feature hợp lý cho dữ liệu PaySim
- train và online dùng logic preprocessing nhất quán
- Gold có composite score rõ ràng
- có đầu ra metrics để chứng minh hiệu quả

### 9.2. Giới hạn

- model hiện chỉ tập trung vào `TRANSFER` và `CASH_OUT`
- rule vẫn phụ thuộc ngưỡng cấu hình
- blacklist hiện được bootstrap từ dữ liệu lịch sử fraud đã biết
- hệ thống chưa dùng các mô hình phức tạp hơn hoặc dữ liệu đăng nhập thật

---

## 10. Cách nói ngắn gọn khi bảo vệ

Có thể trả lời như sau:

> Trong dự án của nhóm em, phần phát hiện gian lận là mô hình lai giữa rule-based và machine learning. Rule được xây dựng từ nghiệp vụ như chạm blacklist, giao dịch lớn, rút cạn tài khoản và chuyển liên tục vào blacklist. Còn AI dùng Random Forest, được huấn luyện trên dữ liệu lịch sử PaySim sau khi đã qua tiền xử lý và tạo feature như tỷ lệ số tiền trên số dư, sai lệch số dư, loại giao dịch và thời điểm giao dịch. Ở Gold layer, hệ thống kết hợp xác suất từ model và điểm rule để sinh cảnh báo cuối cùng, giúp vừa dễ giải thích vừa tăng khả năng phát hiện gian lận.

---

## 11. Kết luận

Phần AI và Rule trong dự án có thể tóm lại như sau:

- **Rule** đại diện cho tri thức nghiệp vụ đã biết
- **AI** đại diện cho khả năng học pattern từ dữ liệu lịch sử
- **Gold** là nơi hợp nhất hai phần này thành quyết định cuối

Đây chính là lý do hệ thống của bạn có tính thực tiễn hơn so với việc chỉ dùng một mô hình đơn lẻ.
