"""Streamlit demo UI for the Day 08 LangGraph support-ticket agent.

Run:
    streamlit run src/langgraph_agent_lab/ui_app.py
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from time import perf_counter
from typing import Any

import streamlit as st
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from langgraph_agent_lab.demo_scripts import DEMO_SCRIPTS, script_for
from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.scenarios import load_scenarios
from langgraph_agent_lab.state import Scenario, initial_state

SCENARIOS_PATH = Path(__file__).resolve().parents[2] / "data" / "sample" / "scenarios.jsonl"

ROUTE_PATHS: dict[str, str] = {
    "simple": "START → intake → classify → answer → finalize → END",
    "tool": "START → intake → classify → tool → evaluate → answer → finalize → END",
    "missing_info": "START → intake → classify → clarify → finalize → END",
    "risky": (
        "START → intake → classify → risky_action → approval → "
        "tool → evaluate → answer → finalize → END"
    ),
    "error": (
        "START → intake → classify → retry → tool → evaluate → "
        "(retry loop | answer | dead_letter) → finalize → END"
    ),
}

NODE_COLORS = {
    "intake": "#2563eb",
    "classify": "#7c3aed",
    "answer": "#059669",
    "tool": "#0891b2",
    "evaluate": "#ca8a04",
    "clarify": "#d97706",
    "risky_action": "#dc2626",
    "approval": "#e11d48",
    "retry": "#ea580c",
    "dead_letter": "#6b7280",
    "finalize": "#0f766e",
}


def _load_scenarios() -> list[Scenario]:
    return load_scenarios(SCENARIOS_PATH)


def _get_graph(*, use_interrupt: bool):
    os.environ["LANGGRAPH_INTERRUPT"] = "true" if use_interrupt else "false"
    if "checkpointer" not in st.session_state:
        st.session_state.checkpointer = build_checkpointer("memory")
    if (
        "graph" not in st.session_state
        or st.session_state.get("interrupt_mode") != use_interrupt
    ):
        st.session_state.graph = build_graph(checkpointer=st.session_state.checkpointer)
        st.session_state.interrupt_mode = use_interrupt
    return st.session_state.graph


def _extract_interrupt(result: dict[str, Any] | Any) -> dict[str, Any] | None:
    interrupts = None
    if isinstance(result, dict):
        interrupts = result.get("__interrupt__")
    if not interrupts:
        return None
    first = interrupts[0]
    value = getattr(first, "value", first)
    return value if isinstance(value, dict) else {"proposed_action": str(value)}


def _render_event_timeline(events: list[dict[str, Any]]) -> None:
    if not events:
        st.info("Chưa có event nào.")
        return
    for index, event in enumerate(events, start=1):
        node = str(event.get("node", "unknown"))
        color = NODE_COLORS.get(node, "#64748b")
        event_type = event.get("event_type", "")
        message = event.get("message", "")
        st.markdown(
            f"""
            <div style="border-left:4px solid {color};padding:0.55rem 0.85rem;margin:0.35rem 0;
                        background:#f8fafc;border-radius:0 8px 8px 0;">
              <div style="font-size:0.78rem;color:#64748b;">Bước {index}</div>
              <div style="font-weight:700;color:{color};">{node}</div>
              <div style="font-size:0.9rem;"><code>{event_type}</code> — {message}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_path_chips(events: list[dict[str, Any]]) -> None:
    nodes = [str(event.get("node", "?")) for event in events]
    if not nodes:
        return
    chips = " → ".join(
        f'<span style="background:{NODE_COLORS.get(node, "#64748b")};color:white;'
        f'padding:0.2rem 0.55rem;border-radius:999px;font-size:0.8rem;'
        f'margin-right:0.25rem;display:inline-block;">{node}</span>'
        for node in nodes
    )
    st.markdown(
        f'<div style="line-height:2.1;margin:0.5rem 0 1rem;">{chips}</div>',
        unsafe_allow_html=True,
    )


def _run_until_pause_or_end(
    graph: Any,
    payload: dict[str, Any] | Command,
    config: RunnableConfig,
) -> tuple[dict[str, Any], dict[str, Any] | None, float]:
    started = perf_counter()
    result = graph.invoke(payload, config=config)
    latency_ms = round((perf_counter() - started) * 1000, 1)
    interrupt_payload = _extract_interrupt(result)
    state = result if isinstance(result, dict) else {}
    if interrupt_payload is None:
        # Prefer full checkpoint state when available.
        try:
            snapshot = graph.get_state(config)
            if snapshot and snapshot.values:
                state = dict(snapshot.values)
        except Exception:
            pass
    return state, interrupt_payload, latency_ms


def _init_session() -> None:
    defaults: dict[str, Any] = {
        "run_state": None,
        "pending_interrupt": None,
        "thread_id": None,
        "latency_ms": None,
        "last_query": None,
        "last_expected": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def main() -> None:
    st.set_page_config(
        page_title="LangGraph Agent Demo — Day 08",
        page_icon="🧭",
        layout="wide",
    )
    _init_session()

    st.title("Day 08 — LangGraph Support Ticket Agent")
    st.caption(
        "Demo orchestration: conditional routing · retry loop · HITL approval · finalize"
    )

    with st.sidebar:
        st.header("Cấu hình demo")
        use_interrupt = st.toggle(
            "Real HITL (`LANGGRAPH_INTERRUPT`)",
            value=False,
            help="Bật interrupt() tại approval_node — demo Approve/Reject trên UI.",
        )
        st.divider()
        mode = st.radio(
            "Nguồn query",
            ["Sample scenario", "Custom query"],
            index=0,
        )
        scenarios = _load_scenarios()
        scenario_map = {f"{s.id} — {s.expected_route}": s for s in scenarios}

        selected: Scenario | None = None
        query = ""
        expected_route = "—"
        max_attempts = 3
        requires_approval = False

        if mode == "Sample scenario":
            label = st.selectbox("Scenario", list(scenario_map.keys()))
            selected = scenario_map[label]
            query = selected.query
            expected_route = selected.expected_route.value
            max_attempts = selected.max_attempts
            requires_approval = selected.requires_approval
            st.info(f"**Expected route:** `{expected_route}`")
            st.write(query)
        else:
            query = st.text_area(
                "Nhập ticket",
                value="Please lookup order status for order 12345",
                height=100,
            )
            expected_route = st.selectbox(
                "Expected route (để so sánh)",
                ["simple", "tool", "missing_info", "risky", "error"],
                index=1,
            )
            max_attempts = st.number_input("max_attempts", min_value=1, max_value=5, value=3)
            requires_approval = expected_route == "risky"

        st.divider()
        run_clicked = st.button("▶ Chạy graph", type="primary", use_container_width=True)

        if st.button("🗑 Reset demo", use_container_width=True):
            for key in (
                "run_state",
                "pending_interrupt",
                "thread_id",
                "latency_ms",
                "last_query",
                "last_expected",
                "graph",
                "checkpointer",
                "interrupt_mode",
            ):
                st.session_state.pop(key, None)
            st.rerun()

    scene_id = selected.id if selected is not None else None
    scene = script_for(
        scenario_id=scene_id,
        expected_route=expected_route if expected_route != "—" else None,
        mode=mode,
    )

    # Expected path hint
    path_key = expected_route if expected_route in ROUTE_PATHS else "simple"
    st.markdown(f"**Luồng kỳ vọng:** `{ROUTE_PATHS[path_key]}`")

    # Teleprompter — luôn hiện Nói + Giải thích theo scenario đang chọn
    with st.container(border=True):
        st.markdown(f"### 📜 {scene['title']}")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**🎙 Nói (đọc to)**")
            st.info(scene["say"])
            st.caption(f"Bấm: {scene['buttons']}")
        with c2:
            st.markdown("**💡 Giải thích (theo code)**")
            st.success(scene["explain"])
            st.caption(f"Code: `{scene['code_map']}`")
            st.caption(f"Nhìn UI: {scene['ui_hint']}")

    with st.sidebar:
        st.divider()
        st.subheader("Script nhanh")
        st.caption(scene["title"])
        st.write(f"**Bấm:** {scene['buttons']}")
        with st.expander("Xem Nói / Giải thích"):
            st.write(scene["say"])
            st.write(scene["explain"])
        with st.expander("Toàn bộ script (intro → outro)"):
            for key in (
                "intro",
                "S01_simple",
                "S02_tool",
                "S03_missing",
                "S04_risky",
                "S05_error",
                "S07_dead_letter",
                "outro",
            ):
                item = DEMO_SCRIPTS[key]
                st.markdown(f"**{item['title']}**")
                st.write(item["say"])
                st.caption(f"Giải thích: {item['explain']}")
                st.divider()

    if run_clicked:
        if not query.strip():
            st.error("Query không được trống.")
            st.stop()
        graph = _get_graph(use_interrupt=use_interrupt)
        thread_id = f"demo-{uuid.uuid4().hex[:10]}"
        if selected is not None:
            state = initial_state(selected)
            state["thread_id"] = thread_id
        else:
            custom = Scenario(
                id="CUSTOM",
                query=query.strip(),
                expected_route=expected_route,  # type: ignore[arg-type]
                requires_approval=requires_approval,
                max_attempts=int(max_attempts),
            )
            state = initial_state(custom)
            state["thread_id"] = thread_id

        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        with st.spinner("Đang chạy LangGraph…"):
            try:
                final_state, interrupt_payload, latency_ms = _run_until_pause_or_end(
                    graph, state, config
                )
            except Exception as exc:
                st.error(f"Chạy graph thất bại: {exc}")
                st.stop()

        st.session_state.thread_id = thread_id
        st.session_state.run_state = final_state
        st.session_state.pending_interrupt = interrupt_payload
        st.session_state.latency_ms = latency_ms
        st.session_state.last_query = query
        st.session_state.last_expected = expected_route

    # HITL panel
    if st.session_state.pending_interrupt:
        st.warning("⏸ Graph đang dừng tại **approval** — cần human-in-the-loop.")
        interrupt_data = st.session_state.pending_interrupt
        st.code(interrupt_data.get("proposed_action", ""), language=None)
        col_a, col_b = st.columns(2)
        with col_a:
            approve = st.button("✅ Approve", type="primary", use_container_width=True)
        with col_b:
            reject = st.button("❌ Reject", use_container_width=True)
        comment = st.text_input("Comment (optional)", value="")

        if approve or reject:
            graph = _get_graph(use_interrupt=True)
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            decision = {
                "approved": bool(approve),
                "reviewer": "streamlit-reviewer",
                "comment": comment or ("Approved in demo UI" if approve else "Rejected in demo UI"),
            }
            with st.spinner("Resume graph sau quyết định HITL…"):
                try:
                    final_state, interrupt_payload, latency_ms = _run_until_pause_or_end(
                        graph, Command(resume=decision), config
                    )
                except Exception as exc:
                    st.error(f"Resume thất bại: {exc}")
                    st.stop()
            st.session_state.run_state = final_state
            st.session_state.pending_interrupt = interrupt_payload
            st.session_state.latency_ms = latency_ms
            st.rerun()

    state = st.session_state.run_state
    if not state:
        st.markdown(
            """
            ### Hướng dẫn demo nhanh
            1. Chọn scenario bên trái — sidebar hiện sẵn **Script** (Bấm / Nói / Giải thích).
            2. Bấm **Chạy graph** — xem timeline node và câu trả lời.
            3. Bật **Real HITL** + chạy `S04_risky` / `S06_delete` để demo Approve/Reject.
            4. Script đầy đủ: `docs/DEMO_SCRIPT.md` (cùng nội dung với sidebar).
            """
        )
        with st.expander("Sơ đồ target graph"):
            st.code(
                """
START -> intake -> classify -> route
  simple       -> answer -> finalize -> END
  tool         -> tool -> evaluate -> answer -> finalize -> END
  tool (retry) -> tool -> evaluate -> retry -> tool -> ...
  missing_info -> clarify -> finalize -> END
  risky        -> risky_action -> approval -> tool -> evaluate -> answer -> finalize -> END
  error        -> retry -> tool -> evaluate -> retry -> ... (bounded)
  max retry    -> retry -> dead_letter -> finalize -> END
                """.strip(),
                language="text",
            )
        return

    events = list(state.get("events") or [])
    actual_route = state.get("route") or "—"
    expected = st.session_state.last_expected or "—"
    matched = actual_route == expected

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Route", str(actual_route))
    m2.metric("Expected", str(expected), delta="match" if matched else "mismatch")
    m3.metric("Nodes", len(events))
    m4.metric("Retries", sum(1 for e in events if e.get("node") == "retry"))
    m5.metric("Latency (ms)", st.session_state.latency_ms or 0)

    st.subheader("Đường đi thực tế (theo events)")
    _render_path_chips(events)

    left, right = st.columns([1.15, 1])
    with left:
        st.subheader("Timeline nodes")
        _render_event_timeline(events)
    with right:
        st.subheader("Kết quả")
        st.markdown("**Final answer**")
        st.write(state.get("final_answer") or "_(chưa có — có thể đang chờ HITL)_")
        if state.get("pending_question"):
            st.markdown("**Clarification**")
            st.info(state["pending_question"])
        if state.get("proposed_action"):
            st.markdown("**Proposed action**")
            st.warning(state["proposed_action"])
        if state.get("approval"):
            st.markdown("**Approval**")
            st.json(state["approval"])
        if state.get("tool_results"):
            st.markdown("**Tool results**")
            for item in state["tool_results"]:
                st.code(item, language=None)
        if state.get("errors"):
            st.markdown("**Errors / retries**")
            for err in state["errors"]:
                st.error(err)

        with st.expander("Raw state (debug)"):
            st.json(
                {
                    "thread_id": state.get("thread_id"),
                    "scenario_id": state.get("scenario_id"),
                    "query": state.get("query"),
                    "route": state.get("route"),
                    "risk_level": state.get("risk_level"),
                    "attempt": state.get("attempt"),
                    "max_attempts": state.get("max_attempts"),
                    "evaluation_result": state.get("evaluation_result"),
                }
            )


if __name__ == "__main__":
    main()
