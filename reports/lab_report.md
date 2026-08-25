# Day 08 LangGraph Agent Lab Report

## 1. Student metadata

| Field | Value |
|---|---|
| Name | Hoàng Huyền Trang (2A202601311) |
| Repository / commit | https://github.com/huyentranghoang/Track3-DAY23-HoangHuyenTrang-2A202601311 (`6d8252d`) |
| Date | 2026-08-25 |

## 2. Metrics summary

| Metric | Value |
|---|---:|
| Total scenarios | 7 |
| Success rate | 100% |
| Average nodes visited | 6.43 |
| Total retries | 3 |
| Total approval-node visits | 2 |
| Resume success demonstrated | no |

Validated locally with `make grade-local` → `Metrics valid. success_rate=100.00%`.
Full pytest suite (`make test`) also passes.

## 3. Scenario results

| Scenario | Expected route | Actual route | Success | Nodes | Retries | Approval visits | Approval observed | Latency (ms) | Errors |
|---|---|---|---|---:|---:|---:|---|---:|---|
| S01_simple | simple | simple | yes | 4 | 0 | 0 | no | 4233 | — |
| S02_tool | tool | tool | yes | 6 | 0 | 0 | no | 8883 | — |
| S03_missing | missing_info | missing_info | yes | 4 | 0 | 0 | no | 660 | — |
| S04_risky | risky | risky | yes | 8 | 0 | 1 | yes | 32342 | — |
| S05_error | error | error | yes | 10 | 2 | 0 | no | 7879 | Retry 1…; Retry 2… |
| S06_delete | risky | risky | yes | 8 | 0 | 1 | yes | 4489 | — |
| S07_dead_letter | error | error | yes | 5 | 1 | 0 | no | 10878 | Retry 1… |

Supporting artifacts:

- `outputs/metrics.json` — grading metrics
- `outputs/audit_events.jsonl` — append-only node event stream
- `outputs/persistence_evidence.json` — per-`thread_id` checkpoint history counts (`history_proven: true`)

## 4. Architecture

Support-ticket agent built as an 11-node LangGraph `StateGraph`:

`intake → classify → (conditional) → … → finalize → END`

| Node | Role |
|---|---|
| `intake` | Normalize query |
| `classify` | LLM structured intent → `route` + `risk_level` |
| `answer` | LLM grounded final response |
| `tool` | Mock tool; injects transient ERROR for error-route retries |
| `evaluate` | Heuristic gate: `needs_retry` vs `success` |
| `clarify` | Ask for missing info |
| `risky_action` | Draft `proposed_action` |
| `approval` | Mock approve by default; real `interrupt()` when enabled |
| `retry` | Increment `attempt`, append error |
| `dead_letter` | Exhausted retries → safe terminal answer |
| `finalize` | Final audit event on every path |

Four conditional routers:

1. `route_after_classify` — simple/tool/missing_info/risky/error
2. `route_after_evaluate` — success → answer · needs_retry → retry
3. `route_after_retry` — attempt < max → tool · else → dead_letter
4. `route_after_approval` — approved → tool · rejected → clarify

Compiled Mermaid diagram: `docs/graph.mmd`.

## 5. State and reducers

| Field | Reducer | Why |
|---|---|---|
| `query`, `route`, `risk_level`, `attempt`, `max_attempts`, `evaluation_result`, `pending_question`, `proposed_action`, `approval`, `final_answer` | overwrite | Current workflow facts |
| `messages`, `tool_results`, `errors`, `events` | append (`operator.add`) | Audit / history for metrics |

Student-required fields `evaluation_result`, `pending_question`, `proposed_action`, and `approval` are present and serializable (approval stored as `dict`, not a live Pydantic instance).

## 6. Failure analysis

1. **Tool retry → dead letter.** Error-route tool calls fail while `attempt < 2`. `evaluate` sets `needs_retry`, `retry` increments the counter, and `route_after_retry` bounds the loop. S05 recovers after two retries; S07 (`max_attempts=1`) goes to `dead_letter` then `finalize`. No unbounded loop.
2. **Risky action without approval.** Risky path always builds `proposed_action` and visits `approval`. Rejected/missing approval routes to `clarify` — a **safe workflow completion**, not a successful side-effect. With mock approve, S04/S06 continue to tool → answer.

## 7. Persistence and recovery

- Backend: `MemorySaver` via `configs/lab.yaml` (`checkpointer: memory`).
- Each scenario uses `thread_id = thread-{scenario_id}`.
- CLI records `get_state_history()` snapshot counts in `outputs/persistence_evidence.json` (`history_proven: true`).
- Contract test uses thread `contract-history` and asserts multiple snapshots with matching `thread_id`.

Caveat: in-process memory checkpoints are not durable across process kill. This report does **not** claim SQLite/Postgres crash recovery. `resume_success` remains **no**.

## 8. Extension work

| Extension | Evidence |
|---|---|
| Real HITL (`interrupt` / `Command(resume=…)`) | `nodes.approval_node` + Streamlit Approve/Reject when `LANGGRAPH_INTERRUPT=true` |
| Streamlit demo UI | `demo_app.py`, `make demo`, script `docs/DEMO_SCRIPT.md` |
| Graph diagram | `docs/graph.mmd` from `draw_mermaid()` |
| Optional web UI | `web/app.py` (`make web`) |

## 9. Improvement plan

If I had one more day I would: (1) wire SQLite checkpointer and prove crash-resume so `resume_success` can be true; (2) upgrade `evaluate_node` to LLM-as-judge with heuristic fallback; (3) split LLM vs tool latency in metrics; (4) add auth around HITL reviewers.
