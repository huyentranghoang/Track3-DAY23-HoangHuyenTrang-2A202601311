# Bản thuyết trình Demo — Day 08 LangGraph Agent

**Thời lượng:** 6–8 phút · **UI:** `streamlit run demo_app.py` hoặc `make demo`

Cách dùng: mỗi scene = **Bấm** → **Nói** → **Chỉ UI**. Sidebar UI cũng hiện cùng nội dung.

---

## Luồng tổng (nói 1 lần ở intro)

```
START → intake → classify
                    │
        ┌───────────┼───────────┬────────────┬────────────┐
        ▼           ▼           ▼            ▼            ▼
     answer       tool      clarify    risky_action     retry
        │           │           │            │            │
        │        evaluate       │        approval    (attempt < max?)
        │         │   │         │         │    │       │         │
        │    success  needs_    │    approve reject   tool   dead_letter
        │         │   retry     │         │    │       │         │
        │         ▼     ▼       │         ▼    ▼       │         │
        │      answer  retry    │       tool clarify   │         │
        │         │             │         │    │       │         │
        └─────────┴─────────────┴─────────┴────┴───────┴─────────┘
                              finalize → END
```

**4 router cần nhớ:**
| Router | Quyết định |
|---|---|
| `route_after_classify` | simple / tool / missing_info / risky / error |
| `route_after_evaluate` | success → answer · needs_retry → retry |
| `route_after_approval` | approve → tool · reject → clarify |
| `route_after_retry` | attempt < max → tool · hết lượt → dead_letter |

---

## 0. Mở đầu (~30s)

**Bấm:** Mở UI, nhìn sidebar — chưa Chạy.

**Nói:**

> Em xin demo **LangGraph support-ticket agent**.  
> Không phải chain tuyến tính: hệ thống **điều phối theo state** — LLM phân loại intent, route có điều kiện, retry có giới hạn, HITL cho hành động rủi ro, và **mọi nhánh đều qua `finalize → END`**.

**Chỉ UI:** Timeline trái = path node; phải = kết quả sau khi chạy.

**Nhớ nếu bị hỏi:** Graph 11 node · 4 conditional edge · `AgentState` có fact + lịch sử append-only (`events`, `tool_results`, `errors`).

---

## 1. Simple — `S01_simple` (~45s)

**Bấm:** `S01_simple` · HITL **tắt** · **Chạy graph**

**Nói:**

> Khách hỏi reset password.  
> `intake` chuẩn hóa → `classify` (LLM structured) chọn **simple** → `answer` (LLM grounded) → `finalize`.

**Chỉ UI:** Path `intake → classify → answer → finalize` · Route = `simple`

**Nhấn mạnh:** Classify/answer dùng **LLM thật**, không hard-code scenario ID (grading có hidden scenarios).

---

## 2. Tool — `S02_tool` (~40s)

**Bấm:** `S02_tool` · **Chạy graph**

**Nói:**

> Classify ra **tool** → `tool_node` mock lookup → `evaluate` không thấy ERROR → **success** → answer → finalize.

**Chỉ UI:** Có `tool_results` · Retries = 0 · không vòng retry

**Nhấn mạnh:** Edge cố định `tool → evaluate`; điều kiện nằm ở `route_after_evaluate`.

---

## 3. Missing info — `S03_missing` (~30s)

**Bấm:** `S03_missing` · **Chạy graph**

**Nói:**

> Query “Can you fix it?” thiếu context. Classify → **missing_info** → `clarify` hỏi lại (`pending_question`) — **không bịa** câu trả lời.

**Chỉ UI:** Clarification / `pending_question` · Path `classify → clarify → finalize`

---

## 4. Risky + HITL — `S04_risky` (~90s) ⭐ scene quan trọng

**Bấm:**
1. Bật **Real HITL**
2. **Reset**
3. `S04_risky` → **Chạy**
4. Khi dừng: **Approve** (hoặc **Reject** nếu còn giờ)

**Nói:**

> Refund là hành động rủi ro.  
> `risky_action` soạn đề xuất → `approval` gọi **`interrupt(...)`** — graph **dừng**, checkpoint giữ state theo `thread_id`.  
> UI Approve/Reject → resume bằng `Command(resume=...)`.  
> **Approved** → tool · **Rejected** → clarify — **không thực thi** hành động rủi ro khi reject.

**Chỉ UI:** Panel vàng Approve/Reject · sau Approve có tool/answer · sau Reject có clarification

**Nhấn mạnh:** Đây là HITL thật (interrupt/resume), không chỉ mock auto-approve.

*(Optional nếu còn giờ: `S06_delete` + Reject — cùng pattern destructive.)*

---

## 5. Retry — `S05_error` (~60s)

**Bấm:** HITL **tắt** · `S05_error` · **Chạy graph**

**Nói:**

> Classify → **error** → `retry` tăng `attempt`.  
> Còn lượt → gọi lại `tool`. Tool cố ý trả `ERROR` khi attempt thấp → `evaluate` = needs_retry → vòng lại.  
> Khi tool OK → answer → finalize.

**Chỉ UI:** Retries ≥ 1 · timeline lặp `retry → tool → evaluate`

**Nhấn mạnh:** Lợi thế LangGraph vs chain tuyến tính = **vòng lặp có điều kiện + state**.

---

## 6. Dead letter — `S07_dead_letter` (~45s)

**Bấm:** `S07_dead_letter` · **Chạy graph**

**Nói:**

> `max_attempts=1`. Retry xong → `attempt >= max` → **`dead_letter`** → trả lời thất bại có kiểm soát → finalize.  
> Retry **bắt buộc bounded** — không có guard này graph có thể loop vô hạn.

**Chỉ UI:** Timeline có node `dead_letter`

---

## 7. Kết thúc (~20s)

**Nói:**

> Tóm lại: LLM classify + answer · graph 11 node / 4 router · retry có biên · HITL cho risky · mọi path qua finalize.  
> Em sẵn sàng trả lời chi tiết một route hoặc một failure mode.

---

## Checklist live (đúng thứ tự)

| # | Scene | Thời gian |
|---|---|---|
| 1 | Intro | 30s |
| 2 | `S01_simple` | 45s |
| 3 | `S02_tool` | 40s |
| 4 | `S03_missing` | 30s |
| 5 | Real HITL + `S04_risky` (Approve/Reject) | 90s |
| 6 | `S05_error` | 60s |
| 7 | `S07_dead_letter` | 45s |
| 8 | Outro | 20s |

Nếu thiếu giờ: bỏ S02 hoặc S03; **giữ S04 + S05 + S07** (HITL / retry / dead letter).

---

## Q&A nhanh (không đọc hết — chỉ khi bị hỏi)

| Câu hỏi | Trả lời |
|---|---|
| Vì sao không hard-code scenario? | Grading có hidden scenarios; route từ LLM + state. |
| Retry dừng thế nào? | `route_after_retry`: so `attempt` với `max_attempts` → tool hoặc dead_letter. |
| Reject risky đi đâu? | `route_after_approval` → `clarify`, không gọi tool. |
| LLM bắt buộc ở đâu? | `classify_node` (structured) + `answer_node` (grounded). |
| Persistence? | Checkpointer + `thread_id` — interrupt/resume giữ state. |

---

*Không cần giải thích cài thư viện khi demo — chỉ UI + luồng graph.*
