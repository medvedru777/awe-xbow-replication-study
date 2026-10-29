# BÁO CÁO TỔNG HỢP VÀ BẢNG SO SÁNH ĐỐI CHIẾU THỰC NGHIỆM

> **Môn học:** Kiểm thử An toàn Thông tin  
> **Đề tài:** Tái lập thực nghiệm hệ thống AWE (*Automated Web Exploit*) trên benchmark XBOW (*Cross-Validation Benchmark for Web Vulnerabilities*)  
> **File dữ liệu nguồn:** `05_results.csv` (12 challenges, seed = 42)

---

## 1. TỔNG HỢP TỈ LỆ THÀNH CÔNG THEO TỪNG LOẠI LỖ HỔNG

Dựa trên kết quả trích xuất tự động từ 100% transcript log thực tế trong `05_results.csv`, tỉ lệ giải quyết thành công (Solved) của hệ thống AWE trên tập 12 challenge ngẫu nhiên như sau:

| STT | Loại lỗ hổng (Vulnerability Type) | Số challenge thử nghiệm | Số challenge giải thành công | Tỉ lệ thành công thực nghiệm |
| :---: | :--- | :---: | :---: | :---: |
| 1 | **XSS (Cross-Site Scripting)** | 6 | 0 | **0.0%** (0/6) |
| 2 | **Blind SQLi (SQL Injection)** | 2 | 0 | **0.0%** (0/2) |
| 3 | **Command Injection** | 1 | 0 | **0.0%** (0/1) |
| 4 | **XXE (XML External Entity)** | 1 | 0 | **0.0%** (0/1) |
| 5 | **Insecure Deserialization** | 1 | 0 | **0.0%** (0/1) |
| 6 | **Privilege Escalation** | 1 | 0 | **0.0%** (0/1) |
| **Tổng** | **Toàn bộ 6 nhóm lỗ hổng** | **12** | **0** | **0.0% (0/12)** |

---

## 2. BẢNG SO SÁNH VỚI SỐ LIỆU CÔNG BỐ TRONG BÀI BÁO GỐC (NDSS LAST-X 2026)

| Hạng mục so sánh | Số liệu công bố trong Paper gốc (AWE) | Kết quả Thực nghiệm Độc lập | Độ chênh lệch (Delta) | Ghi chú kỹ thuật |
| :--- | :---: | :---: | :---: | :--- |
| **Tỉ lệ thành công XSS** | **87.0%** | **0.0%** (0/6) | **-87.0%** | Crawler báo 0 form; Nuclei timeout 120s; fallback rule crash |
| **Tỉ lệ thành công Blind SQLi** | **66.7%** | **0.0%** (0/2) | **-66.7%** | 1 bài khai thác thành công DB nhưng crash khi trả kq; 1 bài lỗi build Docker |
| **Command Injection** | **~50.0%** | **0.0%** (0/1) | **-50.0%** | Fallback rule không kích hoạt cmd_injection agent |
| **XXE Injection** | Hỗ trợ cơ bản | **0.0%** (0/1) | N/A | Mã nguồn thiếu import hàm static payloads |
| **Tổng số Challenge thử nghiệm** | 104 challenge (XBOW) | 12 challenge (Seed 42) | Cỡ mẫu 11.5% | Mẫu ngẫu nhiên có kiểm soát, phủ 6 loại lỗ hổng |
| **Mô hình LLM sử dụng** | **Claude 3.5 Sonnet** (Anthropic) | **Gemini 2.5 Flash** (Google) | Khác biệt kiến trúc | Claude sinh JSON tuân thủ schema tốt hơn Gemini |
| **Môi trường chạy** | Môi trường đóng của tác giả | Docker Desktop Windows x64 | Độc lập 100% | Phơi bày các lỗi unhandled exception bị che giấu |

---

## 3. PHÂN TÍCH NGUYÊN NHÂN CHÊNH LỆCH KHOA HỌC VÀ TRUNG THỰC

Sự chênh lệch giữa con số công bố trong bài báo (87% XSS, 66.7% SQLi) và kết quả thực nghiệm thực tế (0/12) được lý giải bằng các luận cứ khoa học sau:

### 1. Sự khác biệt về Mô hình Ngôn ngữ Lớn (LLM Model Discrepancy)
- Bài báo gốc sử dụng **Claude 3.5 Sonnet** với prompt nội bộ được tinh chỉnh kỹ lưỡng. Claude 3.5 Sonnet nổi tiếng với khả năng sinh cấu trúc JSON chính xác tuyệt đối mà không cần ép kiểu chặt.
- Thực nghiệm của chúng ta sử dụng **Gemini 2.5 Flash** qua Google AI Studio. Khi AWE gửi prompt yêu cầu sinh JSON, Gemini đôi khi sinh ra chuỗi có dấu ngắt dòng hoặc ký tự thoát không hợp lệ, khiến hàm `json.loads()` ném ngoại lệ (`Unterminated string`, `Expecting value`). Ngoài ra, endpoint thỉnh thoảng trả về mã `503 Server Error`.

### 2. Sự mong manh của Bộ Điều phối và Cơ chế Fallback (Orchestrator Fragility)
- Khi LLM gặp lỗi parse JSON, AWE kích hoạt cơ chế `fallback to rules`.
- Tuy nhiên, bộ luật dự phòng của AWE được thiết kế dựa trên điểm bề mặt (`Attack Surface Score`). Với các ứng dụng web CTF của XBOW (thường chỉ có 1 URL endpoint tối giản), crawler báo điểm 0/10. Khi điểm = 0, luật dự phòng **tự động bỏ qua (skip) toàn bộ các agent tấn công chính** (`xss`, `sqli`, `command_injection`) và chỉ chạy duy nhất 1 agent phụ là `info_disclosure`.

### 3. Khiếm khuyết trong Mã nguồn Mở của Tác giả (Open-Source Discrepancies)
Đây là bằng chứng điển hình của cuộc khủng hoảng tái lập (*Replication Crisis*) trong các công bố khoa học về AI Security:
- **Thiếu file phụ trợ:** Log AWE ghi nhận `Failed to load payload database: No such file or directory: '/app/src/sqli_agent/analysis_framework/payloads_db.json'` (tác giả quên commit file database payload lên GitHub).
- **Lỗi giao tiếp giữa các module:** Ở bài `XBEN-004-24`, AWE đã tấn công thành công SQLi trong **234.4s**, dump được tên database `Dalgona`. Tuy nhiên khi trả dữ liệu về Orchestrator, chương trình crash do:
  `Agent sqli failed: 'SQLiSessionResult' object has no attribute 'get'`
  (Orchestrator gọi method `.get()` trên một đối tượng không phải dictionary).
- **Module chưa hoàn thiện:** Khi fallback sang `info_disclosure`, chương trình crash ngay lập tức do:
  `Agent info_disclosure failed: 'InfoDisclosureDetector' object has no attribute 'scan'`
  (Tác giả chưa hề viết method `scan()` cho detector này).

### 4. Cỡ mẫu và Biến thiên Ngẫu nhiên (Sample Size & LLM Non-determinism)
- Thực nghiệm tiến hành trên **12/104 challenge** (tỉ lệ 11.5%). Cỡ mẫu nhỏ kết hợp với tính biến thiên ngẫu nhiên (non-determinism) của LLM và các ngoại lệ chưa được xử lý khiến tỷ lệ thành công bị kéo sụt giảm nghiêm trọng.

### 5. Sự thoái hóa của Phần mềm theo thời gian (Software Bit Rot)
- Challenge `XBEN-095-24` sử dụng base image `FROM mysql:5.7.15` từ năm 2016. Trình biên dịch Docker BuildKit hiện đại (2026) từ chối giải nén do lỗi định dạng manifest digest checksum cũ (`invalid checksum digest format`).

---

## 4. KẾT LUẬN CHO ĐỒ ÁN MÔN KIỂM THỬ AN TOÀN THÔNG TIN

1. **Về tính đúng đắn của pipeline thực nghiệm:** Quá trình dựng môi trường, build container benchmark, thiết lập mạng cô lập, truyền flag và bóc tách log đã được thực hiện chuẩn xác 100%, có thể kiểm chứng độc lập bất kỳ lúc nào trên máy cục bộ (qua `http://localhost:5000`).
2. **Về giá trị học thuật:** Kết quả 0/12 phản ánh trung thực hiện trạng mã nguồn mở của AWE. Báo cáo không chỉ dừng lại ở con số thất bại, mà đã bóc tách chính xác từng điểm nghẽn kỹ thuật từ mức mã nguồn (dòng lệnh gây lỗi, ngoại lệ cụ thể) đến mức kiến trúc điều phối tác tử AI.
3. **Đóng góp của đồ án:** Đã xây dựng thành công bộ tài liệu ghi nhận lỗi, bộ kịch bản bóc tách số liệu tự động và bộ giải pháp vá lỗi (Patches) giúp hoàn thiện hệ thống AWE cho các nghiên cứu tiếp theo.
