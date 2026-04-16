# README Architecture

## 1. Mục đích tài liệu

Tài liệu này dùng để giải thích **kiến trúc tổng thể** của đồ án theo góc nhìn hệ thống, không chỉ theo luồng dữ liệu.

Nội dung tập trung vào các ý mà giảng viên thường hỏi:

- hệ thống được tổ chức như thế nào
- vì sao chọn kiến trúc Bronze - Silver - Gold
- khả năng mở rộng ra sao
- khả năng chịu tải và vận hành thế nào
- hệ thống có tối ưu gì
- hệ thống có điểm mạnh và giới hạn gì trong phạm vi đồ án

Tài liệu này nên dùng cùng với:

- [README.md](</D:/Download/files (4)/README.md>)
- [README_data.md](</D:/Download/files (4)/README_data.md>)
- [README_pipeline.md](</D:/Download/files (4)/README_pipeline.md>)

---

## 2. Kiến trúc tổng thể

### 2.1. Kiến trúc logic

Hệ thống được chia thành 2 phần lớn:

1. **Offline preparation**
   Chuẩn bị trước khi demo hoặc trước khi chạy online.

2. **Online streaming pipeline**
   Xử lý dữ liệu theo micro-batch gần thời gian thực.

Sơ đồ logic:

```text
Offline
  ├─ seed_blacklist
  └─ train_model

Online
  ├─ simulate_stream
  ├─ bronze_stream
  ├─ silver_stream
  └─ gold_stream
```

### 2.2. Kiến trúc dữ liệu

Hệ thống đi theo mô hình nhiều tầng:

```text
Raw → Stream Input → Bronze → Silver → Gold → Reports / Dashboard
```

Ý nghĩa từng tầng:

- **Raw**
  lưu dữ liệu gốc PaySim
- **Stream Input**
  mô phỏng dữ liệu đến theo từng lô
- **Bronze**
  ingest dữ liệu gần nguyên bản
- **Silver**
  làm sạch, enrich, áp dụng rule
- **Gold**
  hợp nhất AI và rule để sinh cảnh báo cuối
- **Reports**
  phục vụ giải trình, dashboard và demo

### 2.3. Kiến trúc thực thi

Trong môi trường hiện tại, hệ thống chạy bằng:

- `Docker`
- `PySpark`
- `Delta Lake`
- `Python jobs` tách độc lập

Container chính được định nghĩa trong:

- [docker-compose.yml](</D:/Download/files (4)/docker-compose.yml:1>)
- [Dockerfile](</D:/Download/files (4)/Dockerfile:1>)

Điểm này giúp:

- môi trường đồng nhất giữa các máy
- giảm lỗi lệ thuộc môi trường
- dễ demo và dễ đóng gói

---

## 3. Thành phần kiến trúc chính

### 3.1. Tầng lưu trữ

Hệ thống dùng 2 kiểu lưu trữ chính:

1. **CSV**
   dùng cho dữ liệu gốc và mô phỏng stream input

2. **Delta Lake**
   dùng cho Bronze, Silver, Gold và model

Lý do chọn Delta:

- hợp với Spark
- có transaction log
- có checkpoint cho streaming
- đọc ghi dạng bảng thuận tiện
- phù hợp trình bày kiến trúc dữ liệu nhiều tầng

### 3.2. Tầng xử lý

Engine xử lý chính là:

- `PySpark`
- `Spark Structured Streaming`

Vai trò:

- đọc dữ liệu dạng micro-batch
- xử lý phân tán
- tạo pipeline rõ ràng giữa các tầng dữ liệu

### 3.3. Tầng phát hiện gian lận

Khối fraud detection là mô hình lai gồm:

- **rule-based detection**
- **machine learning detection**

Trong đó:

- Silver phụ trách phần rule
- Gold phụ trách phần hợp nhất rule + AI

Lý do chọn mô hình lai:

- rule giúp giải thích nhanh và bám nghiệp vụ
- AI giúp phát hiện các mẫu gian lận khó hơn
- mô hình lai cân bằng giữa độ chính xác và tính thực tiễn

### 3.4. Tầng trình bày

Hệ thống có 2 lớp trình bày:

1. **Terminal logs**
   để theo dõi batch khi chạy pipeline

2. **Reports + Web dashboard**
   để trình chiếu, báo cáo và bảo vệ

Đầu ra chính:

- `training_metrics.json`
- `evaluation_summary.csv`
- `top_risk_accounts.csv`
- `latest_gold_batch.json`
- `dashboard.png`
- dashboard web một trang

---

## 4. Vì sao chọn kiến trúc Bronze - Silver - Gold

Kiến trúc này phù hợp với môn Big Data vì:

- tách rõ vai trò giữa ingest, xử lý và phân tích
- giúp dữ liệu được kiểm soát tốt hơn qua từng tầng
- thuận tiện giải thích với giảng viên
- dễ mở rộng thêm bước mới mà không phá toàn bộ pipeline

### 4.1. Lợi ích về quản trị dữ liệu

- Bronze giữ dữ liệu gần nguyên bản
- Silver giữ dữ liệu sạch và đã enrich
- Gold giữ dữ liệu đã sẵn sàng cho phân tích và cảnh báo

### 4.2. Lợi ích về phát triển hệ thống

- dễ tách lỗi theo tầng
- dễ kiểm tra dữ liệu từng bước
- dễ tối ưu từng job
- dễ demo vì có thể mở từng tầng để giải thích

### 4.3. Lợi ích về mở rộng

Nếu sau này cần:

- thêm feature mới
- thêm rule mới
- thay đổi model AI
- thêm dashboard khác

thì có thể chỉnh từng tầng mà không phải viết lại toàn bộ hệ thống.

---

## 5. Khả năng mở rộng của hệ thống

Đây là phần quan trọng để trả lời tiêu chí “scalable architecture”.

### 5.1. Mở rộng theo dữ liệu

Hiện tại hệ thống chạy local container để demo, nhưng về kiến trúc có thể mở rộng khi dữ liệu tăng vì:

- xử lý dựa trên Spark thay vì pandas cho phần lõi
- dữ liệu được chia tầng rõ ràng
- Delta tables được partition theo `type`
- pipeline chia thành nhiều job độc lập

Điều này nghĩa là:

- khi dữ liệu tăng, có thể tăng tài nguyên Spark
- hoặc chuyển từ local sang cluster mà không phải đổi toàn bộ logic

### 5.2. Mở rộng theo tài nguyên

Hiện tại cấu hình đang hướng tới local demo:

- `SPARK_MASTER=local[2]`
- `SPARK_SHUFFLE_PARTITIONS=8`
- `SPARK_DRIVER_MEMORY=2g`
- Docker memory limit khoảng `4g`

Tức là:

- đây là cấu hình tối ưu cho máy cá nhân
- không phải cấu hình production

Nếu cần mở rộng, hướng đúng là:

- tăng số core
- tăng driver memory
- tăng tài nguyên máy hoặc chuyển sang cluster
- thay file-based stream input bằng middleware như Kafka

### 5.3. Mở rộng theo chức năng

Kiến trúc hiện tại hỗ trợ mở rộng tương đối dễ:

- thêm rule mới ở `rules.py`
- thêm feature mới ở `features.py`
- đổi model AI ở `train_model.py`
- thêm service hiển thị hoặc API phục vụ dashboard

Đây là điểm mạnh vì kiến trúc đã tách rõ:

- config
- feature engineering
- rule engine
- training
- streaming jobs
- presentation layer

---

## 6. Khả năng chịu tải và xử lý batch

### 6.1. Cách hệ thống chịu tải hiện tại

Hệ thống không nhận stream vô hạn theo từng event thật, mà dùng:

```text
micro-batch near real-time
```

Điều này giúp:

- giảm áp lực tức thời lên máy local
- dễ quan sát quá trình xử lý
- ổn định hơn cho buổi demo

### 6.2. Cơ chế khống chế tải

Trong hệ thống hiện tại đã có các cơ chế giúp hạn chế quá tải:

- `maxFilesPerTrigger` ở Bronze để giới hạn số file mỗi lần xử lý
- trigger interval riêng cho Bronze, Silver, Gold
- simulator chia dữ liệu thành batch nhỏ
- mật độ fraud trong demo được điều chỉnh để dễ quan sát mà không phải đẩy toàn bộ dữ liệu lớn cùng lúc

### 6.3. Dấu hiệu hệ thống đang chịu tải tốt ở mức demo

Nhóm có thể giải thích rằng hệ thống đang kiểm soát được tải ở mức demo vì:

- mỗi job ghi log theo batch
- có thể quan sát số dòng xử lý mỗi lô
- có thể đo thời gian xử lý batch ở terminal và file `latest_gold_batch.json`
- pipeline vẫn ra được output liên tục qua Bronze, Silver, Gold

### 6.4. Nếu dữ liệu tăng mạnh thì sao

Đây là cách trả lời đúng hướng:

- về kiến trúc thì hệ thống **có khả năng mở rộng**
- nhưng với cấu hình local hiện tại, nếu dữ liệu tăng gấp nhiều lần thì cần:
  - tăng tài nguyên Spark
  - giảm các thao tác nặng trong từng batch
  - tránh đọc lại toàn bộ bảng Gold sau mỗi lô
  - tránh đưa quá nhiều dữ liệu về pandas

Nói cách khác:

- **kiến trúc đi đúng hướng scale**
- **implementation hiện tại tối ưu cho demo nhiều hơn production**

---

## 7. Tối ưu hóa hiện có trong hệ thống

### 7.1. Tối ưu Spark

Trong cấu hình Spark hiện tại đã có:

- giảm `spark.sql.shuffle.partitions`
- bật `spark.sql.adaptive.enabled`
- bật `spark.sql.adaptive.coalescePartitions.enabled`
- bật `parquet filter pushdown`
- bật `delta optimize write`
- dùng `offHeap` memory

Những cấu hình này giúp:

- giảm overhead trên máy local
- giảm partition thừa
- tăng hiệu quả đọc ghi dữ liệu

### 7.2. Tối ưu lưu trữ

Các bảng Delta chính được partition theo `type`.

Điều này giúp:

- truy vấn theo loại giao dịch hiệu quả hơn
- giảm lượng dữ liệu phải đọc không cần thiết

### 7.3. Tối ưu join

Blacklist là bảng nhỏ nên được xử lý theo kiểu:

- `broadcast join`

Điều này giúp:

- giảm shuffle
- tăng tốc áp dụng rule blacklist

### 7.4. Tối ưu bằng cache

Hiện tại cache rõ ràng nhất nằm ở `simulate_stream`:

- cache tập fraud
- cache tập normal
- unpersist sau khi dùng xong

Điều này giúp:

- tránh đọc lại toàn bộ tập khi simulator sinh nhiều batch
- làm demo mượt hơn

### 7.5. Tối ưu bằng tách offline và online

Đây là một tối ưu kiến trúc rất quan trọng:

- train model ở offline
- online chỉ load model để scoring

Lợi ích:

- giảm tải cho pipeline realtime
- tránh huấn luyện lại trong khi demo
- làm Gold chỉ tập trung vào scoring và alerting

---

## 8. Độ bền và khả năng phục hồi

### 8.1. Checkpoint

Mỗi luồng streaming đều có checkpoint riêng:

- Bronze checkpoint
- Silver checkpoint
- Gold checkpoint

Vai trò:

- lưu trạng thái xử lý stream
- giúp job tiếp tục đúng logic khi restart

### 8.2. Delta transaction log

Delta Lake lưu `_delta_log`, giúp:

- giữ trạng thái bảng
- hỗ trợ đọc ghi có cấu trúc hơn
- dễ quản lý dữ liệu qua nhiều lần chạy

### 8.3. Tách job độc lập

Mỗi job là một module riêng:

- dễ restart từng thành phần
- dễ cô lập lỗi
- dễ phân vai trong nhóm

Đây là điểm tốt về mặt vận hành và trình bày kiến trúc.

---

## 9. Giới hạn hiện tại của hệ thống

Để trả lời chắc khi bảo vệ, nhóm nên nói rõ các giới hạn sau.

### 9.1. Giới hạn dữ liệu

PaySim không có:

- dữ liệu đăng nhập
- IP
- thiết bị
- vị trí đăng nhập

Vì vậy hệ thống hiện tại **không tuyên bố phát hiện đăng nhập lạ từ dữ liệu thật**.

### 9.2. Giới hạn về realtime

Hệ thống là:

- micro-batch near real-time

không phải:

- event-by-event realtime mức mili-giây

### 9.3. Giới hạn về scale production

Hiện tại vẫn còn một số điểm chưa phải tối ưu production, ví dụ:

- có dùng `.count()` để log batch
- có dùng `.toPandas()` trong một số bước báo cáo / biểu đồ
- Gold đang đọc lại toàn bộ `gold_scored` để cập nhật metrics và dashboard

Nói cách khác:

- hệ thống phù hợp để chứng minh kiến trúc Big Data và demo học thuật
- chưa phải hệ production scale lớn hoàn chỉnh

---

## 10. Liên hệ trực tiếp với tiêu chí chấm điểm

### 10.1. Kiến trúc dữ liệu và khả năng mở rộng

Điểm mạnh:

- có pipeline nhiều tầng rõ ràng
- tách offline và online
- dùng Delta Lake
- partition dữ liệu
- có thể nâng cấp từ local lên cluster

### 10.2. Hiệu quả xử lý và tối ưu mã nguồn

Điểm mạnh:

- dùng Spark Structured Streaming
- có broadcast join
- có tối ưu Spark config
- có checkpoint
- có execution plan để giải thích

### 10.3. Độ chính xác và giá trị thực tiễn

Điểm mạnh:

- có rule bám sát nghiệp vụ
- có AI học từ dữ liệu lịch sử
- có hybrid score để cân bằng rule và model
- có metrics và dashboard giải thích kết quả

### 10.4. Hình thức báo cáo và giải trình

Điểm mạnh:

- tài liệu tách riêng theo từng mục
- có log, bảng Delta, file report và dashboard
- có thể trình bày luồng dữ liệu và kiến trúc một cách rõ ràng

---

## 11. Cách nói ngắn gọn khi giảng viên hỏi về kiến trúc

Có thể trả lời như sau:

> Nhóm em thiết kế hệ thống theo kiến trúc nhiều tầng Raw - Bronze - Silver - Gold trên Spark và Delta Lake. Phần offline dùng để seed blacklist và train model AI, còn phần online dùng Structured Streaming để xử lý dữ liệu theo micro-batch. Silver là tầng xử lý nghiệp vụ chính, Gold là tầng hợp nhất điểm luật và điểm AI để sinh cảnh báo cuối cùng. Kiến trúc này giúp hệ thống dễ mở rộng, dễ giải thích, phù hợp với tiêu chí Big Data và đủ ổn định để demo trên môi trường local container.

---

## 12. Kết luận

Về mặt kiến trúc, đồ án hiện tại có thể được mô tả như sau:

- **đúng hướng Big Data**
  vì dùng Spark, Delta Lake, pipeline nhiều tầng và xử lý phân tán
- **đúng hướng scalable architecture**
  vì có thể tăng tài nguyên hoặc chuyển sang cluster mà không đổi toàn bộ logic
- **đúng hướng chịu tải ở mức demo**
  vì dùng micro-batch, giới hạn trigger, checkpoint và chia nhỏ dữ liệu đầu vào
- **chưa phải production hoàn chỉnh**
  nhưng đã đủ tốt để chứng minh tư duy kiến trúc, xử lý dữ liệu lớn và bài toán fraud detection theo thời gian thực trong phạm vi môn học
