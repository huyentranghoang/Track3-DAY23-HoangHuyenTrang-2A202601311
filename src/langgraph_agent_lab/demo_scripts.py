"""Lời nói + giải thích theo từng scenario — hiện trên UI demo và docs/DEMO_SCRIPT.md.

Mỗi scene có:
- buttons: thao tác UI cần bấm
- say: đọc to khi demo
- explain: giải thích vì sao / map sang file code (không đọc hết nếu thiếu giờ)
- ui_hint: chỉ vào đâu trên màn hình
"""

from __future__ import annotations

from typing import TypedDict


class SceneScript(TypedDict):
    title: str
    say: str
    explain: str
    ui_hint: str
    buttons: str
    code_map: str


DEMO_SCRIPTS: dict[str, SceneScript] = {
    "intro": {
        "title": "0. Mở đầu (~30s)",
        "buttons": "Mở UI · chưa cần Chạy graph.",
        "say": (
            "Em xin demo LangGraph support-ticket agent. "
            "Hệ thống không trả lời tuyến tính như một chain cố định, "
            "mà điều phối theo state: phân loại intent bằng LLM, "
            "route có điều kiện, vòng retry có giới hạn, "
            "human-in-the-loop cho hành động rủi ro, "
            "và mọi nhánh đều kết thúc ở finalize rồi END."
        ),
        "explain": (
            "Vì sao dùng LangGraph: cần branching, loop, và dừng chờ người duyệt — "
            "LCEL tuyến tính làm kém tự nhiên. "
            "Graph 11 node trong graph.py; 4 hàm route trong routing.py; "
            "AgentState trong state.py gồm fact hiện tại + lịch sử append-only "
            "(events, tool_results, errors) nhờ reducer add để đo metrics."
        ),
        "ui_hint": "Sidebar chọn scenario. Sau khi chạy: timeline trái, kết quả phải.",
        "code_map": "graph.py · routing.py · state.py",
    },
    "S01_simple": {
        "title": "A. Simple path — S01 (~45s)",
        "buttons": "Chọn S01_simple · HITL tắt · Chạy graph.",
        "say": (
            "Scenario S01: khách hỏi cách reset password. "
            "Đầu tiên intake chuẩn hóa query. "
            "Tiếp theo classify_node gọi LLM với structured output, "
            "trả về route bằng simple. "
            "Router route_after_classify đưa sang answer. "
            "answer_node gọi LLM để viết câu trả lời grounded, rồi finalize ghi audit event."
        ),
        "explain": (
            "Điểm chấm quan trọng: classify và answer phải gọi LLM thật, "
            "không hard-code theo scenario ID — bài có hidden scenarios. "
            "Structured output giúp route ổn định hơn parse text tự do."
        ),
        "ui_hint": "Path chips: intake → classify → answer → finalize. Metric Route = simple (match).",
        "code_map": "nodes.intake_node → nodes.classify_node → routing.route_after_classify → nodes.answer_node → nodes.finalize_node",
    },
    "S02_tool": {
        "title": "B. Tool + evaluate — S02 (~40s)",
        "buttons": "Chọn S02_tool · Chạy graph.",
        "say": (
            "S02 cần tra cứu order. Classify chọn route tool. "
            "tool_node chạy mock lookup và ghi tool_results. "
            "evaluate_node xem kết quả — không có ERROR nên evaluation_result = success. "
            "Router sau evaluate đi answer, rồi finalize."
        ),
        "explain": (
            "Edge cố định trong graph: tool luôn tới evaluate. "
            "Điều kiện nằm ở route_after_evaluate: success → answer, needs_retry → retry. "
            "Tách 'gọi tool' và 'đánh giá chất lượng' giúp retry loop rõ ràng."
        ),
        "ui_hint": "Xem Tool results bên phải; Retries = 0; không có vòng retry trên timeline.",
        "code_map": "nodes.tool_node → nodes.evaluate_node → routing.route_after_evaluate → answer → finalize",
    },
    "S03_missing": {
        "title": "C. Missing info — S03 (~30s)",
        "buttons": "Chọn S03_missing · Chạy graph.",
        "say": (
            "S03 query rất mơ hồ: 'Can you fix it?'. "
            "Classify chọn missing_info. "
            "ask_clarification_node tạo pending_question và dùng luôn làm final_answer. "
            "Agent không bịa chi tiết thiếu — hỏi lại rồi finalize."
        ),
        "explain": (
            "Đây là failure mode 'thiếu thông tin' được xử lý an toàn: "
            "ưu tiên clarify hơn hallucinate. "
            "Trong prompt classify, missing_info đứng trước simple để câu ngắn mơ hồ không bị đẩy sang simple."
        ),
        "ui_hint": "Ô Clarification / pending_question. Path: classify → clarify → finalize.",
        "code_map": "routing.route_after_classify(missing_info→clarify) · nodes.ask_clarification_node",
    },
    "S04_risky": {
        "title": "D. Risky + HITL — S04 (~90s)",
        "buttons": "Bật Real HITL → Reset → S04_risky → Chạy → Approve (hoặc Reject).",
        "say": (
            "S04 yêu cầu refund và gửi email — hành động có side effect, route risky. "
            "risky_action_node soạn proposed_action. "
            "Khi bật Real HITL, approval_node gọi interrupt: graph dừng, "
            "checkpoint giữ state theo thread_id. "
            "Trên UI em Approve hoặc Reject, rồi resume bằng Command(resume). "
            "Approved thì vào tool; Rejected thì vào clarify — không thực thi hành động rủi ro."
        ),
        "explain": (
            "HITL tắt = mock auto-approve (chạy CI/offline). "
            "HITL bật = interrupt/resume đúng kiểu production. "
            "route_after_approval đọc approval.approved. "
            "Reject là hoàn thành an toàn của workflow, không phải 'tool đã chạy thành công'."
        ),
        "ui_hint": "Panel vàng Approve/Reject. Sau Approve: tool + answer. Sau Reject: clarification.",
        "code_map": "nodes.risky_action_node → nodes.approval_node(interrupt) · routing.route_after_approval · Command(resume)",
    },
    "S06_delete": {
        "title": "D′. Risky delete — S06 (optional)",
        "buttons": "Real HITL ON · S06_delete · Chạy · Reject.",
        "say": (
            "S06 xóa tài khoản cũng đi risky path. "
            "Em Reject để chứng minh router đưa sang clarify, không gọi tool."
        ),
        "explain": "Cùng pattern HITL với S04; dùng khi muốn nhấn hành động destructive.",
        "ui_hint": "Sau Reject: không có tool success; có clarification.",
        "code_map": "Giống S04 — nhấn Reject để show branch rejected→clarify",
    },
    "S05_error": {
        "title": "E. Retry loop — S05 (~60s)",
        "buttons": "HITL tắt · S05_error · Chạy graph.",
        "say": (
            "S05 mô phỏng lỗi tạm thời. Classify ra error, router đưa vào retry. "
            "retry_or_fallback_node tăng attempt và ghi errors. "
            "route_after_retry: nếu attempt còn nhỏ hơn max_attempts thì gọi lại tool. "
            "tool_node cố ý trả chuỗi ERROR khi attempt còn thấp. "
            "evaluate thấy ERROR → needs_retry → vòng lại. "
            "Khi tool thành công → answer → finalize."
        ),
        "explain": (
            "Đây là lợi thế LangGraph so với chain tuyến tính: "
            "vòng lặp có điều kiện dựa trên state (evaluation_result, attempt). "
            "evaluate là cổng 'done?' của retry loop."
        ),
        "ui_hint": "Metric Retries ≥ 1. Timeline có vòng retry → tool → evaluate.",
        "code_map": "routing.route_after_classify(error→retry) · retry_or_fallback_node · route_after_retry · tool · evaluate",
    },
    "S07_dead_letter": {
        "title": "F. Dead letter — S07 (~45s)",
        "buttons": "S07_dead_letter · Chạy graph.",
        "say": (
            "S07 đặt max_attempts bằng 1. "
            "Retry tăng attempt; vì attempt đã không còn nhỏ hơn max, "
            "route_after_retry đi dead_letter. "
            "dead_letter_node trả lời thất bại có kiểm soát, rồi vẫn finalize. "
            "Retry bắt buộc phải bounded."
        ),
        "explain": (
            "Thiếu so sánh attempt với max_attempts → loop vô hạn → grading fail. "
            "Dead letter là tầng cuối: retry → (fallback) → dead letter, "
            "vẫn có final_answer và audit event."
        ),
        "ui_hint": "Timeline có dead_letter. Final answer là thông báo không hoàn thành được.",
        "code_map": "routing.route_after_retry(attempt>=max→dead_letter) · nodes.dead_letter_node → finalize",
    },
    "custom": {
        "title": "Custom query",
        "buttons": "Custom query · nhập ticket · Chạy graph.",
        "say": (
            "Với query tùy chỉnh, classify_node vẫn gọi LLM để chọn route — "
            "em không map cứng theo ID scenario."
        ),
        "explain": "So Expected route trên sidebar với Route thực tế trên thanh metric.",
        "ui_hint": "Path chips + final_answer sau khi chạy.",
        "code_map": "Cùng graph — route quyết định bởi LLM classify + routers",
    },
    "outro": {
        "title": "Kết thúc (~20s)",
        "buttons": "Không bắt buộc — chỉ tóm tắt.",
        "say": (
            "Tóm lại: LLM classify và answer, graph 11 node với 4 router, "
            "retry có biên, HITL cho risky, mọi path qua finalize. "
            "Em sẵn sàng trả lời chi tiết một route hoặc một failure mode."
        ),
        "explain": (
            "Q&A nhanh — "
            "Không hard-code scenario vì có hidden tests; "
            "Retry dừng bằng so attempt với max_attempts; "
            "Reject risky → clarify, không gọi tool; "
            "LLM bắt buộc ở classify (structured) và answer (grounded)."
        ),
        "ui_hint": "Có thể mở Raw state nếu được hỏi về thread_id / persistence.",
        "code_map": "cli.run-scenarios → metrics.json · reports/lab_report.md",
    },
}


ROUTE_TO_DEFAULT_SCENE: dict[str, str] = {
    "simple": "S01_simple",
    "tool": "S02_tool",
    "missing_info": "S03_missing",
    "risky": "S04_risky",
    "error": "S05_error",
}


def script_for(
    *,
    scenario_id: str | None,
    expected_route: str | None,
    mode: str,
) -> SceneScript:
    if mode == "Custom query":
        return DEMO_SCRIPTS["custom"]
    if scenario_id and scenario_id in DEMO_SCRIPTS:
        return DEMO_SCRIPTS[scenario_id]
    if expected_route and expected_route in ROUTE_TO_DEFAULT_SCENE:
        return DEMO_SCRIPTS[ROUTE_TO_DEFAULT_SCENE[expected_route]]
    return DEMO_SCRIPTS["intro"]
