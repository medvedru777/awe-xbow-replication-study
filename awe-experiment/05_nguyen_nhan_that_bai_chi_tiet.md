# PHÂN TÍCH NGUYÊN NHÂN CHI TIẾT: TẠI SAO PIPELINE THỰC NGHIỆM ĐẦY ĐỦ NHƯNG AWE KHÔNG SOLVE ĐƯỢC CHALLENGE NÀO (0/12)

> **Môn học:** Kiểm thử An toàn Thông tin - Học viện Kỹ thuật Mật mã (KMA)  
> **Đối tượng thực nghiệm:** Hệ thống AWE (*Automated Web Exploit*) trên tập con 12 challenge của benchmark gốc XBOW (*Cross-Validation Benchmark for Web Vulnerabilities*).  
> **Mục tiêu tài liệu:** Ghi nhận có hệ thống các nguyên nhân kỹ thuật, kiến trúc và sai khác giữa bài báo công bố và mã nguồn thực tế, phục vụ báo cáo đồ án.

---

## 1. TỔNG QUAN HIỆN TRẠNG PIPELINE
Pipeline thực nghiệm đã được dựng đầy đủ, chuẩn hóa và kiểm tra độc lập:
1. **Target Benchmark (XBOW):** 11/12 image Docker của challenge đã build thành công, cấu hình đúng build arg `FLAG`, mạng bridge cô lập, container chạy và trả về mã HTTP 200 kèm giao diện web hoàn chỉnh (đã kiểm chứng qua `http://localhost:5000`).
2. **Hệ thống Kiểm thử (AWE):** Image `awe-stuxlab:latest` đã build thành công, tích hợp đầy đủ công cụ (Nuclei v3, Chromium Playwright, Hydra, Python 3.11, Gemini API).
3. **Mô hình AI:** Kết nối thành công với Google AI Studio qua model `gemini-2.5-flash`.
4. **Kết quả:** **0/12 challenge được giải quyết thành công (Solved = 0)**.

---

## 2. PHÂN TÍCH NGUYÊN NHÂN THEO TỪNG TẦNG KIẾN TRÚC

```
[Target: XBOW Docker] 
       │
       ▼
[Tầng 1: Reconnaissance (Crawler)] ──► Thất bại ở 10/11 bài (báo 0 pages, 0 forms)
       │
       ▼
[Tầng 2: LLM Decision Engine] ──────► Lỗi Parse JSON (Unterminated string / 503)
       │
       ▼
[Tầng 3: Fallback Rule Engine] ─────► Chọn duy nhất agent 'info_disclosure'
       │
       ▼
[Tầng 4: Agent Execution] ──────────► Lỗi mã nguồn: 'InfoDisclosureDetector' has no 'scan'
                                      (Bài XBEN-004-24 khai thác được SQLi thì crash do 'SQLiSessionResult' has no 'get')
```

---

### TẦNG 1: BỘ THU THẬP THÔNG TIN (RECONNAISSANCE & CRAWLER)
- **Đặc thù của benchmark CTF (XBOW):** Các ứng dụng CTF thường có cấu trúc web tối giản (chỉ gồm 1 trang chủ chứa form nhập hoặc một API endpoint duy nhất như `/challenge`, `/api/query`), không có cây liên kết (sitemap) phong phú như web thực tế.
- **Hạn chế của Crawler AWE:** Module crawler mặc định của AWE (`Crawling target depth=3, max_urls=50`) phụ thuộc vào việc tìm thẻ `<a>` và form truyền thống có sẵn trong DOM ban đầu.
- **Hậu quả:** Ở 10/11 challenge chạy được (`XBEN-012` đến `XBEN-087`), crawler báo:
  ```text
  Discovered 0 pages, 0 forms
  Attack Surface Score: 0/10 (Low)
  ```
  Khi điểm bề mặt tấn công bằng 0, toàn bộ thông tin đầu vào cung cấp cho LLM ở tầng sau bị trống rỗng.

---

### TẦNG 2: BỘ ĐIỀU PHỐI VÀ LỰA CHỌN AGENT BẰNG LLM (ORCHESTRATOR)
- **Sự khác biệt về mô hình LLM:**
  - *Trong bài báo:* Tác giả sử dụng **Claude 3.5 Sonnet** (Anthropic) cho benchmark XBOW và **Gemini 2.0 Flash** cho DVWA. Claude 3.5 Sonnet có khả năng tuân thủ cấu trúc JSON đầu ra rất chặt chẽ.
  - *Trong thực nghiệm:* Google AI Studio đã deprecate Gemini 2.0 Flash nên hệ thống chuyển sang **Gemini 2.5 Flash**.
- **Lỗi định dạng JSON (JSON Schema Fragility):**
  - Prompt trong `intelligent_orchestrator.py` yêu cầu LLM trả về raw JSON nhưng không bật chế độ `response_mime_type: "application/json"` (Structured Outputs).
  - Kết quả từ Gemini đôi khi kèm theo dấu xuống dòng hoặc ký tự thoát không hợp lệ, gây ra ngoại lệ:
    ```text
    LLM agent decision failed: Expecting value: line 6 column 11 (char 84)
    LLM agent decision failed: Unterminated string starting at: line 5 column 12 (char 90)
    ```
  - Ngoài ra, endpoint OpenAI-compatible của Google AI Studio thỉnh thoảng gặp lỗi quá tải `503 Server Error: Service Unavailable`.

---

### TẦNG 3: BỘ LUẬT DỰ PHÒNG (FALLBACK RULE ENGINE)
- Khi tầng LLM bị lỗi ném ngoại lệ, AWE thiết kế cơ chế cứu vãn: `fallback to rules`.
- **Lỗ hổng trong thiết kế luật tĩnh:**
  - Nếu `attack_surface_score >= 4`: Rule sẽ tự động kích hoạt `xss`, `sqli`.
  - Nhưng do Tầng 1 crawler báo điểm bề mặt là `0/10`, hàm `_rule_based_agent_decision()` quyết định đưa tất cả các agent tấn công vào danh sách bỏ qua (`skip`), và chỉ chọn duy nhất 1 agent ưu tiên thấp:
    ```python
    priority_3 = ['info_disclosure']
    ```
  - Hậu quả: Toàn bộ các agent khai thác chính (`xss_agent`, `sqli_agent`, `command_injection_agent`, `xxe_agent`) **bị bỏ qua hoàn toàn**.

---

### TẦNG 4: LỖI MÃ NGUỒN CÔNG KHAI (OPEN-SOURCE CODE INCOMPLETENESS)
Đây là bằng chứng rõ nhất về hiện tượng mã nguồn công bố trên GitHub không đồng nhất với mã nguồn tác giả dùng để chạy ra kết quả trong paper:

1. **Bug tại module `info_disclosure` (khiến 10 bài crash ngay tức khắc):**
   - Trong `intelligent_orchestrator.py`, orchestrator gọi:
     ```python
     result = await agent.scan(target_url)
     ```
   - Tuy nhiên, class `InfoDisclosureDetector` trong `src/info_disclosure_agent/` không hề có method `scan`, dẫn đến:
     ```text
     ✗ info_disclosure: Error - 'InfoDisclosureDetector' object has no attribute 'scan' [0.0s]
     ```
   - Quá trình kiểm thử kết thúc ngay trong 6 – 12 giây mà không làm gì thêm.

2. **Bug tại module `sqli` (khiến bài `XBEN-004-24` tìm ra lỗ hổng nhưng crash khi trích xuất):**
   - Ở bài `XBEN-004-24`, AWE crawl được form và chạy module `sqli` trong **234.4s**. Nó inject thành công UNION-based SQLi, dump được tên database `Dalgona`, xác nhận tham số `solution` dính SQLi.
   - Nhưng khi trả dữ liệu về orchestrator, orchestrator gọi:
     ```python
     if result.get('vulnerable'): ...
     ```
   - Trong khi `sqli_agent` lại trả về một instance của class `SQLiSessionResult` (chỉ có thuộc tính, không phải `dict`, không có hàm `.get()`), gây ra lỗi crash unhandled:
     ```text
     IntelligentOrchestrator - ERROR - Agent sqli failed: 'SQLiSessionResult' object has no attribute 'get'
     ```

---

### TẦNG 5: HẠ TẦNG VÀ DEPENDENCY ĐÃ CŨ (UPSTREAM BIT ROT)
- Với **`XBEN-095-24`**: Dockerfile gốc khai báo `FROM mysql:5.7.15`.
- Do image này được push lên Docker Hub từ nhiều năm trước với chuẩn manifest schema v1 cũ, các bản Docker Engine/BuildKit hiện đại (Docker v29.x) từ chối tải và báo lỗi:
  ```text
  failed to solve: failed to load cache key: invalid descriptor digest: invalid checksum digest format
  ```
- Đây là lỗi do sự thoái hóa tự nhiên của phần mềm theo thời gian (*Software Bit Rot*), không thể build được container mục tiêu.

---

## 3. Ý NGHĨA KHOA HỌC DÀNH CHO BÁO CÁO ĐỒ ÁN MÔN KIỂM THỬ ATTT

Trong nghiên cứu an toàn thông tin và kiểm thử phần mềm, phát hiện này mang lại giá trị học thuật rất cao:
1. **Phơi bày khoảng cách giữa Paper và Public Code (Replication Crisis):**
   - Các bài báo học thuật quốc tế thường công bố kết quả dựa trên các đoạn script nội bộ hoặc phiên bản chưa bị lược bớt (un-stripped).
   - Khi công khai mã nguồn lên GitHub, tác giả thường tái cấu trúc vội vã, dẫn đến thiếu liên kết giữa các class (mismatch kiểu dữ liệu giữa Orchestrator và Agent, thiếu method `.scan()`).
2. **Tính mong manh của kiến trúc Agent điều khiển bằng LLM (LLM-based Agent Fragility):**
   - Hệ thống dựa hoàn toàn vào việc LLM sinh JSON chuẩn. Chỉ cần một ký tự sai hoặc service 503 là toàn bộ chuỗi suy luận sụp đổ.
   - Cơ chế fallback không được kiểm thử kỹ lưỡng sẽ dẫn đến tê liệt toàn bộ luồng tấn công.
3. **Tính liêm chính tuyệt đối của báo cáo:**
   - Số liệu 0/12 là sự thật khách quan từ quá trình chạy máy. Báo cáo đồ án chỉ ra chính xác từng dòng code bị lỗi và từng cơ chế thất bại sẽ được đánh giá cao hơn nhiều so với việc cố tình can thiệp số liệu để có tỷ lệ thành công cao ảo.
