# README Big Data Defense

## 1. Mục đích tài liệu

Tài liệu này tổng hợp **toàn bộ kiến thức Big Data đang được áp dụng thật trong dự án**, theo cách có thể dùng trực tiếp để:

- ôn trước khi bảo vệ
- trả lời câu hỏi phản biện của giảng viên
- phân biệt rõ cái gì nhóm **đã làm thật**
- cái gì nhóm **mới ở mức định hướng / mở rộng**

Điểm quan trọng:

- nội dung trong tài liệu này **bám sát code và output thật trong repo**
- không tô vẽ theo kiểu production nếu dự án hiện tại chưa đạt tới mức đó

---

## 2. Một câu mô tả ngắn gọn về dự án dưới góc nhìn Big Data

> Đây là một hệ thống xử lý dữ liệu lớn cho bài toán phát hiện gian lận giao dịch ví điện tử, sử dụng PySpark, Spark Structured Streaming và Delta Lake để xây pipeline nhiều tầng Raw → Bronze → Silver → Gold; kết hợp rule-based detection và machine learning để tạo cảnh báo gần thời gian thực theo micro-batch.

Nếu muốn nói ngắn hơn nữa:

> Dự án là một pipeline Big Data nhiều tầng, có xử lý phân tán, streaming micro-batch, Delta Lake, rule engine, AI scoring và dashboard báo cáo.

---

## 3. Những kiến thức Big Data nào thực sự đang được áp dụng trong dự án

### 3.1. Kiến trúc dữ liệu nhiều tầng

Dự án áp dụng kiến trúc:

```text
Raw → Stream Input → Bronze → Silver → Gold → Reports / Dashboard
```

Ý nghĩa Big Data:

- tách biệt từng vai trò của dữ liệu
- không trộn ingest, cleaning, feature engineering và alerting vào một chỗ
- dễ mở rộng
- dễ giám sát
- dễ giải trình

Đây là tư duy rất đặc trưng của:

- data lake / lakehouse
- modern data pipeline

### 3.2. Xử lý phân tán bằng Spark

Engine xử lý chính là:

- `PySpark`

Điều này thể hiện ở:

- các job đọc dữ liệu bằng Spark DataFrame
- xử lý bằng Spark SQL functions
- training pipeline cũng dùng Spark ML

Ý nghĩa Big Data:

- hệ thống không phụ thuộc vào pandas cho phần lõi
- dữ liệu được xử lý theo mô hình phân tán
- kiến trúc có thể mở rộng theo tài nguyên Spark

### 3.3. Streaming bằng Spark Structured Streaming

Dự án dùng:

- `spark.readStream`
- `writeStream.foreachBatch`
- `checkpointLocation`
- `trigger(processingTime=...)`

Ý nghĩa:

- dữ liệu được xử lý dưới dạng **micro-batch**
- không phải chạy một lần rồi xong như batch processing thuần
- pipeline có khả năng nhận dữ liệu mới liên tục

### 3.4. Delta Lake

Hệ thống dùng Delta Lake cho các tầng:

- `bronze`
- `silver`
- `blacklist`
- `gold_scored`
- `gold_alerts`
- `gold_metrics`
- `model`

Ý nghĩa Big Data:

- lưu dữ liệu theo dạng bảng
- có `_delta_log`
- hỗ trợ checkpoint và quản lý trạng thái tốt hơn so với chỉ dùng CSV
- phù hợp với kiến trúc lakehouse đơn giản

### 3.5. Schema-on-read có kiểm soát

Thay vì infer schema, hệ thống khai báo:

- `PAYSIM_SCHEMA`
- `BRONZE_SCHEMA`
- `SILVER_SCHEMA`

Ý nghĩa:

- ổn định khi đọc stream
- giảm lỗi kiểu dữ liệu
- dễ giải thích dữ liệu đi qua từng tầng

### 3.6. Feature engineering trên dữ liệu giao dịch

Dự án không chỉ ingest dữ liệu thô mà còn:

- chuẩn hóa cột
- tạo `txn_id`
- loại trùng
- tạo `amount_ratio`
- tạo `error_balance_orig`
- tạo `error_balance_dest`
- tạo `hour`
- tạo `type_index`

Ý nghĩa Big Data:

- đây là bước biến raw transaction thành analytical-ready data
- rất quan trọng cho cả rule engine và AI

### 3.7. Rule-based detection như một lớp business logic

Hệ thống áp dụng:

- blacklist rule
- large transaction rule
- drain rule
- blacklist burst rule

Ý nghĩa:

- đưa tri thức nghiệp vụ vào pipeline
- tăng tính thực tiễn
- làm hệ thống dễ giải thích hơn

### 3.8. Machine learning trên pipeline Big Data

Hệ thống dùng:

- `RandomForestClassifier`
- `VectorAssembler`
- `StandardScaler`

trên dữ liệu đã qua Silver preprocessing.

Ý nghĩa:

- không chỉ có pipeline dữ liệu, mà còn có lớp AI tích hợp vào Big Data flow
- model được huấn luyện offline, rồi tải lại ở Gold để scoring online

### 3.9. Hybrid analytics

Gold không chỉ dùng AI hoặc chỉ dùng rule.

Nó tính:

```text
composite_score = ml_probability * 0.7 + rule_score_normalized * 0.3
```

Ý nghĩa:

- đây là cách kết hợp giữa business rules và data-driven prediction
- giúp tăng giá trị thực tiễn của hệ thống

### 3.10. Reporting layer và presentation layer

Hệ thống có:

- `gold_metrics`
- `evaluation_summary.csv`
- `training_metrics.json`
- `top_risk_accounts.csv`
- `dashboard.png`
- dashboard web

Ý nghĩa:

- pipeline không chỉ xử lý xong là hết
- mà còn tạo đầu ra có thể phân tích, giám sát và trình bày

---

## 4. Dự án đang xử lý dữ liệu theo kiểu nào

### 4.1. Batch hay streaming?

Câu trả lời đúng là:

- **streaming theo kiểu micro-batch**

Không phải:

- batch một lần duy nhất
- cũng không phải event-by-event instant streaming ở mức mili-giây

### 4.2. Micro-batch hiện tại chạy ra sao

Theo cấu hình thật trong dự án:

- `SIMULATOR_BATCH_SIZE = 500`
- `SIMULATOR_BATCHES = 15`
- `SIMULATOR_SLEEP_SECONDS = 8`
- `SIMULATOR_FRAUD_RATIO = 0.15`

Nghĩa là demo hiện tại:

- phát khoảng `15` lô
- mỗi lô `500` dòng
- nghỉ khoảng `8` giây giữa hai lô
- mỗi lô khoảng `75` fraud và `425` bình thường

### 4.3. Nguồn stream hiện tại là gì

Nguồn gốc dữ liệu vẫn là:

- `data/raw/paysim.csv`

Nhưng stream không đọc trực tiếp từ file đó.

Luồng thật là:

```text
raw paysim.csv
   ↓
simulate_stream.py
   ↓
data/stream_input/
   ↓
bronze_stream.py
```

Nói cách khác:

- đây là **file-based simulated streaming**
- dùng để mô phỏng dữ liệu đến theo thời gian thực

### 4.4. Nếu giảng viên hỏi “vậy có phải realtime thật không?”

Câu trả lời tốt nhất:

> Hệ thống hiện tại là near real-time theo micro-batch. Vì dữ liệu nguồn là PaySim dạng file tĩnh nên nhóm mô phỏng streaming bằng cách đẩy dữ liệu vào từng lô nhỏ. Kiến trúc vẫn đúng theo Structured Streaming, nhưng nguồn vào hiện tại là simulated stream chứ chưa phải Kafka hay giao dịch thật từ production system.

---

## 5. Khả năng mở rộng của hệ thống ra sao

### 5.1. Câu trả lời ngắn

> Về mặt kiến trúc, hệ thống có khả năng mở rộng. Về mặt triển khai hiện tại, hệ thống đang tối ưu cho local demo chứ chưa phải production scale lớn.

### 5.2. Vì sao nói là có khả năng mở rộng

Vì dự án đã có các đặc điểm kiến trúc đúng hướng:

- dùng Spark thay vì pandas cho lõi xử lý
- dữ liệu được tách tầng rõ ràng
- dùng Delta Lake
- partition dữ liệu theo `type`
- tách offline và online
- dùng streaming theo micro-batch

Điều đó nghĩa là:

- nếu tăng tài nguyên, pipeline có thể tiếp tục mở rộng
- nếu chuyển từ local sang cluster, logic tổng thể không cần viết lại từ đầu

### 5.3. Vì sao nói là chưa phải production scale lớn

Vì trong implementation hiện tại vẫn còn các điểm thiên về demo:

- cấu hình Spark là `local[2]`
- `spark.driver.memory = 2g`
- `spark.sql.shuffle.partitions = 8`
- stream source vẫn là file-based stream
- Gold đọc lại toàn bộ `gold_scored` để tạo report
- có một số `.toPandas()` ở phần report / train metrics

Tức là:

- **kiến trúc scale được**
- nhưng **cấu hình và cách triển khai hiện tại** vẫn là mức học thuật / demo

---

## 6. Khả năng chịu tải hiện tại ra sao

### 6.1. Mức chịu tải thực tế hiện tại

Dựa trên dự án đang có, mức chịu tải phù hợp nhất để mô tả là:

- chạy ổn ở mức **demo local**
- xử lý được dữ liệu theo lô nhỏ
- có thể cho thấy pipeline liên tục nhận và xử lý dữ liệu

### 6.2. Cơ chế giúp chịu tải

Nhóm đã có một số kỹ thuật giúp kiểm soát tải:

- chia dữ liệu thành nhiều micro-batch nhỏ
- giới hạn `maxFilesPerTrigger`
- trigger theo thời gian riêng cho từng tầng
- cache ở simulator
- broadcast join với blacklist nhỏ
- partition Delta table theo `type`
- dùng AQE và coalesce partition

### 6.3. Nếu dữ liệu tăng lên gấp 10 lần thì sao

Câu trả lời nên trung thực:

> Nếu dữ liệu tăng gấp 10 lần thì kiến trúc vẫn đi đúng hướng, nhưng triển khai local hiện tại sẽ cần tối ưu thêm. Ví dụ cần tăng tài nguyên Spark, thay file source bằng Kafka, giảm việc đọc lại toàn bộ bảng Gold sau mỗi batch, và hạn chế các bước chuyển dữ liệu về pandas.

Đây là câu trả lời rất ổn vì:

- không khoe quá
- vẫn cho thấy nhóm hiểu vấn đề scale

---

## 7. Dự án đã tối ưu những gì thật

### 7.1. Tối ưu Spark config

Ở [spark.py](</D:/Download/files (4)/src/common/spark.py:39>), hệ thống đã:

- giảm `shuffle.partitions`
- bật `adaptive query execution`
- bật `coalescePartitions`
- bật `parquet filter pushdown`
- bật `delta optimize write`
- dùng `offHeap memory`

Ý nghĩa:

- tối ưu cho môi trường local
- giảm partition dư
- giảm overhead trong demo

### 7.2. Tối ưu join

Blacklist là bảng nhỏ nên được:

- `broadcast join`

Ý nghĩa:

- giảm shuffle
- tăng tốc rule blacklist

### 7.3. Tối ưu lưu trữ

Các bảng Delta chính được:

- `partitionBy("type")`

Ý nghĩa:

- tăng khả năng pruning
- giảm đọc dữ liệu không cần thiết

### 7.4. Tối ưu bằng cache

Ở `simulate_stream.py`, nhóm cache:

- fraud pool
- normal pool

và `unpersist()` sau khi dùng.

Ý nghĩa:

- giảm đọc lại toàn bộ tập dữ liệu khi simulator tạo nhiều batch

### 7.5. Tối ưu kiến trúc

Tối ưu quan trọng nhất là:

- huấn luyện AI offline
- scoring online ở Gold

Điều này giúp:

- phần realtime không phải train lại model
- Gold chỉ tập trung vào scoring và alerting

---

## 8. Dự án có những cơ chế độ bền và phục hồi nào

### 8.1. Checkpoint

Mỗi stream có checkpoint riêng:

- Bronze checkpoint
- Silver checkpoint
- Gold checkpoint

Ý nghĩa:

- lưu trạng thái xử lý
- giúp stream có thể tiếp tục logic khi restart

### 8.2. Delta transaction log

Delta Lake có `_delta_log`, giúp:

- quản lý trạng thái bảng
- đảm bảo dữ liệu ở dạng bảng có tổ chức hơn
- hỗ trợ pipeline nhiều tầng

### 8.3. Tách job độc lập

Mỗi job là một module riêng:

- dễ restart từng phần
- dễ tìm lỗi
- dễ phân công trong nhóm

---

## 9. Dự án có áp dụng AI theo hướng Big Data không

Có, nhưng phải nói đúng mức.

### 9.1. Đã áp dụng

- training bằng Spark ML pipeline
- feature engineering trên dữ liệu giao dịch
- chống mất cân bằng bằng negative sampling
- offline training, online scoring
- so sánh Rule vs ML vs Hybrid

### 9.2. Chưa phải production AI platform

Chưa có:

- model registry chuyên nghiệp
- online feature store
- data drift monitoring
- tự động retrain
- serving ở quy mô cluster thực

Nên nếu giảng viên hỏi sâu, câu tốt là:

> Dự án đã áp dụng AI trong pipeline Big Data ở mức huấn luyện và scoring tích hợp với Spark/Delta, nhưng chưa mở rộng tới kiến trúc MLOps production hoàn chỉnh.

---

## 10. Những gì dự án chưa làm hoặc mới ở mức giả lập

Đây là phần rất quan trọng để trả lời chắc.

### 10.1. Chưa có nguồn giao dịch thật

Hiện tại dữ liệu giao dịch chính vẫn là:

- PaySim

Tức là:

- dữ liệu mô phỏng
- không phải giao dịch thật từ ví điện tử thật

### 10.2. Chưa dùng Kafka

Streaming source hiện tại là:

- file-based simulated streaming

chứ chưa phải:

- Kafka
- Pub/Sub
- event bus thật

### 10.3. Chưa có production-grade observability

Hiện giám sát chủ yếu là:

- terminal logs
- metrics files
- dashboard báo cáo

Chưa có:

- Prometheus
- Grafana
- distributed tracing

### 10.4. Chưa tối ưu hết cho scale rất lớn

Các điểm cần thành thật:

- có `.count()` trong mỗi batch để log
- có `.toPandas()` ở một số bước
- Gold đọc lại toàn bảng để tạo report

---

## 11. Khả năng thực tế của hệ thống hiện tại nên mô tả thế nào

Đây là câu hỏi “khả năng ra sao”.

Mô tả tốt nhất là:

### 11.1. Hệ thống làm tốt ở mức nào

- xử lý được pipeline nhiều tầng rõ ràng
- xử lý được micro-batch streaming
- tạo được cảnh báo fraud gần thời gian thực
- tích hợp được rule + AI
- có output đầy đủ để báo cáo và demo

### 11.2. Hệ thống phù hợp với ngữ cảnh nào

- phù hợp với đồ án Big Data
- phù hợp môi trường local demo
- phù hợp chứng minh kiến trúc và tư duy xử lý dữ liệu lớn

### 11.3. Hệ thống chưa nên tự nhận là gì

Không nên tự nhận là:

- realtime production fraud engine hoàn chỉnh
- hệ thống dùng dữ liệu thật của ngân hàng / ví điện tử
- hệ thống chịu tải production quy mô doanh nghiệp lớn ngay bây giờ

---

## 12. Các câu hỏi phản biện rất dễ gặp và cách trả lời

### 12.1. “Dự án của em Big Data ở chỗ nào?”

Trả lời:

> Big Data ở đây thể hiện ở kiến trúc nhiều tầng, xử lý phân tán bằng Spark, streaming micro-batch bằng Structured Streaming, lưu trữ bằng Delta Lake, và khả năng mở rộng khi dữ liệu tăng hoặc khi chuyển từ local sang môi trường có nhiều tài nguyên hơn.

### 12.2. “Có phải realtime thật không?”

Trả lời:

> Hệ thống hiện tại là near real-time theo micro-batch. Nguồn vào được mô phỏng từ PaySim nên chưa phải event streaming thật như Kafka, nhưng pipeline online vẫn dùng Structured Streaming với checkpoint và trigger rõ ràng.

### 12.3. “Nếu tăng dữ liệu gấp 10 lần thì sao?”

Trả lời:

> Về kiến trúc thì hệ thống vẫn đi đúng hướng scale vì dùng Spark, Delta và chia tầng rõ ràng. Tuy nhiên để chịu tải tốt hơn ở mức đó, cần tăng tài nguyên Spark, giảm các thao tác đọc lại toàn bảng, hạn chế đưa dữ liệu về pandas và có thể thay file stream bằng Kafka.

### 12.4. “Sao không dùng pandas?”

Trả lời:

> Vì mục tiêu của đồ án là xử lý dữ liệu lớn và kiến trúc có khả năng mở rộng, nên nhóm chọn PySpark làm engine xử lý chính. Pandas chỉ xuất hiện ở một số bước nhỏ phục vụ report hoặc biểu đồ, không phải lõi của pipeline.

### 12.5. “Sao không dùng Kafka?”

Trả lời:

> Nhóm ưu tiên hoàn thiện end-to-end pipeline trước trên file-based simulated streaming để phù hợp thời gian và môi trường local. Nếu mở rộng tiếp, Kafka là hướng thay thế hợp lý cho phần stream source.

### 12.6. “Tối ưu gì rồi?”

Trả lời:

> Nhóm đã tối ưu bằng cách giảm shuffle partitions cho local, bật AQE, partition Delta theo loại giao dịch, broadcast join với blacklist, dùng checkpoint cho từng stream và cache trong simulator để giảm đọc lặp.

### 12.7. “Điểm yếu của hệ thống là gì?”

Trả lời:

> Điểm yếu hiện tại là dữ liệu giao dịch vẫn là mô phỏng, streaming source chưa phải Kafka, một số bước còn tối ưu cho demo như `.toPandas()` và Gold đọc lại toàn bảng để sinh report. Tuy nhiên kiến trúc tổng thể vẫn đúng hướng Big Data và có khả năng mở rộng tiếp.

---

## 13. Cách trình bày 90 giây nếu thầy hỏi bất ngờ

Có thể nói theo mạch này:

> Dự án của nhóm em áp dụng Big Data ở ba lớp chính. Thứ nhất là lớp kiến trúc dữ liệu, với pipeline Raw → Bronze → Silver → Gold và lưu trữ bằng Delta Lake. Thứ hai là lớp xử lý, dùng PySpark và Spark Structured Streaming để xử lý dữ liệu theo micro-batch gần thời gian thực, có checkpoint và có tối ưu như partition, AQE, broadcast join. Thứ ba là lớp phân tích, khi Silver áp dụng rule nghiệp vụ còn Gold kết hợp AI và rule để tạo cảnh báo cuối. Hiện tại hệ thống chạy tốt ở mức local demo và đúng hướng scalable architecture, nhưng nhóm cũng nhận thức rõ rằng để lên production scale lớn thì cần nguồn stream thật như Kafka, thêm tài nguyên Spark và tối ưu tiếp các bước report.

---

## 14. Kết luận

Tổng hợp lại, những kiến thức Big Data đã và đang được áp dụng thật trong dự án gồm:

- kiến trúc dữ liệu nhiều tầng
- xử lý phân tán với Spark
- Structured Streaming theo micro-batch
- Delta Lake và checkpoint
- schema rõ ràng
- feature engineering trên dữ liệu giao dịch
- rule-based analytics
- machine learning tích hợp vào pipeline
- hybrid scoring
- reporting layer và dashboard
- tối ưu ở mức local demo

Nói ngắn gọn:

> Dự án không chỉ là một mô hình AI nhỏ, mà là một hệ thống Big Data hoàn chỉnh ở mức đồ án: có ingest, processing, storage, streaming, analytics, alerting và presentation.
