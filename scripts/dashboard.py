"""
Artifact-based read-only dashboard for agentic-sim runs.

Launch (split artifact directory):
    streamlit run scripts/dashboard.py -- --root-dir /path/to/output

Launch (single run.json file):
    streamlit run scripts/dashboard.py -- --root-dir /path/to/run.json

Dependencies:
    pip install "agentic-sim[dashboard]"
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


# ── artifact loading ──────────────────────────────────────────────────────────

def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _find_run_dirs(root: Path) -> list[Path]:
    """Return all directories that contain a metadata.json, sorted newest-first."""
    # If root itself is a run dir, return it directly.
    if (root / "metadata.json").exists():
        return [root]
    dirs = sorted(
        {p.parent for p in root.glob("**/metadata.json")},
        key=lambda d: _read_json(d / "metadata.json").get("created_at", ""),
        reverse=True,
    )
    return dirs


def _load_run_dir(run_dir: Path) -> dict[str, Any]:
    return {
        "source": "split",
        "metadata": _read_json(run_dir / "metadata.json") or {},
        "config": _read_json(run_dir / "config.json") or {},
        "summary": _read_json(run_dir / "summary.json") or {},
        "ticks": _read_json(run_dir / "ticks.json") or [],
        "environment": _read_json(run_dir / "environment.json") or {},
        "traces": _read_json(run_dir / "traces.json") or [],
        "backend_metrics": _read_json(run_dir / "backend_metrics.json") or {},
    }


def _load_run_json(path: Path) -> dict[str, Any]:
    """Load a monolithic run.json produced by --output."""
    raw = json.loads(path.read_text())
    return {
        "source": "monolithic",
        "metadata": {"run_id": path.stem, "scenario": raw.get("environment", {}).get("scenario", "?")},
        "config": {},
        "summary": raw.get("summary", {}),
        "ticks": raw.get("ticks", []),
        "environment": raw.get("environment", {}),
        "traces": raw.get("traces", []),
        "backend_metrics": {},
    }


# ── view helpers ──────────────────────────────────────────────────────────────

def _tick_backend_rows(traces: list[dict]) -> list[dict]:
    rows = []
    for trace in traces:
        if trace.get("event_name") != "simulation_tick":
            continue
        payload = trace.get("payload", {})
        backend = payload.get("backend")
        if not isinstance(backend, dict):
            continue
        rows.append({"tick": payload.get("tick", "?"), **backend})
    return rows


def _agent_step_rows(traces: list[dict]) -> list[dict]:
    rows = []
    for trace in traces:
        if trace.get("event_name") != "agent_step":
            continue
        p = trace.get("payload", {})
        meta = p.get("metadata", {})
        rows.append({
            "agent_id": p.get("agent_id", ""),
            "role": meta.get("role", ""),
            "messages": p.get("messages", 0),
            "env_actions": p.get("environment_actions", 0),
            "latency_s": meta.get("latency_seconds"),
            "retry_count": meta.get("retry_count"),
            "invalid": bool(meta.get("model_output_invalid")),
            "guard_msg": meta.get("policy_guard_added_messages", 0),
            "guard_act": meta.get("policy_guard_added_actions", 0),
            "model": meta.get("model", ""),
            "timestamp": trace.get("timestamp", ""),
        })
    return rows


# ── views ─────────────────────────────────────────────────────────────────────

def view_summary(run: dict[str, Any]) -> None:
    summary = run["summary"]
    meta = run["metadata"]
    activations = summary.get("agent_activations", {})
    total_activations = sum(activations.values())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Steps", meta.get("steps", summary.get("environment_tick", "—")))
    c2.metric("Agent activations", total_activations)
    c3.metric("Messages emitted", summary.get("messages", "—"))
    c4.metric("Traces written", summary.get("traces", "—"))

    if not activations:
        st.info("No agent activation data.")
        return

    st.subheader("Agent activations")
    df_act = (
        pd.DataFrame(activations.items(), columns=["agent", "activations"])
        .sort_values("activations", ascending=False)
        .set_index("agent")
    )
    st.bar_chart(df_act)

    agent_steps = _agent_step_rows(run["traces"])
    if agent_steps:
        st.subheader("Messages sent per agent step")
        df_msg = (
            pd.DataFrame(agent_steps)
            .groupby("agent_id")[["messages", "env_actions"]]
            .sum()
            .sort_values("messages", ascending=False)
        )
        st.bar_chart(df_msg)


def view_tick_timeline(run: dict[str, Any]) -> None:
    ticks = run["ticks"]
    if not ticks:
        st.info("No tick data.")
        return

    df = (
        pd.DataFrame(ticks)
        .set_index("tick")[["processed_events", "activations", "messages_emitted"]]
    )
    st.subheader("Events, activations, and messages per tick")
    st.line_chart(df)

    tick_backend = _tick_backend_rows(run["traces"])
    if tick_backend:
        bdf = pd.DataFrame(tick_backend).set_index("tick")

        latency_col = "latency_seconds_total"
        if latency_col in bdf.columns and bdf[latency_col].notna().any():
            st.subheader("Backend total latency per tick (s)")
            st.bar_chart(bdf[[latency_col]])

        detail_cols = [c for c in ["agent_steps", "retry_count", "validation_failures"] if c in bdf.columns]
        if detail_cols:
            st.subheader("Per-tick backend summary")
            st.dataframe(bdf[detail_cols], use_container_width=True)
    else:
        st.caption("No per-tick backend data (non-Aitta backend or pre-Task-1 run).")


def view_backend(run: dict[str, Any]) -> None:
    bm = run["backend_metrics"]
    if not bm:
        st.info("No backend metrics — mock or rule backend, or monolithic run.json.")
        return

    lat = bm.get("latency_seconds", {})
    usage = bm.get("usage", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Backend steps", bm.get("backend_steps", "—"))
    c2.metric("Avg latency (s)", lat.get("avg", "—"))
    c3.metric("Total tokens", usage.get("total_tokens", "—"))
    c4.metric("Invalid outputs", bm.get("invalid_model_outputs", 0))

    c5, c6 = st.columns(2)
    c5.metric("Guard-added messages", bm.get("policy_guard_added_messages", 0))
    c6.metric("Guard-added actions", bm.get("policy_guard_added_actions", 0))

    if lat.get("count"):
        st.subheader("Latency summary (s)")
        lat_df = pd.DataFrame(
            [{"stat": k, "seconds": v} for k, v in lat.items() if k not in ("count",) and v is not None]
        ).set_index("stat")
        st.bar_chart(lat_df)

    if any(usage.get(k, 0) for k in ("prompt_tokens", "completion_tokens")):
        st.subheader("Token usage")
        tok_df = pd.DataFrame(
            [{"type": "prompt", "tokens": usage.get("prompt_tokens", 0)},
             {"type": "completion", "tokens": usage.get("completion_tokens", 0)}]
        ).set_index("type")
        st.bar_chart(tok_df)

    agent_steps = _agent_step_rows(run["traces"])
    aitta_steps = [r for r in agent_steps if r.get("latency_s") is not None]
    if aitta_steps:
        st.subheader("Latency by agent step")
        df_lat = pd.DataFrame(aitta_steps)[["agent_id", "role", "latency_s", "retry_count", "invalid", "guard_msg", "guard_act"]]
        st.dataframe(df_lat, use_container_width=True)


def view_traces(run: dict[str, Any]) -> None:
    traces = run["traces"]
    if not traces:
        st.info("No traces.")
        return

    event_names = sorted({t.get("event_name", "") for t in traces})
    selected = st.multiselect("Filter by event type", event_names, default=event_names)

    rows = []
    for t in traces:
        if t.get("event_name") not in selected:
            continue
        payload = t.get("payload", {})
        meta = payload.get("metadata", {})
        rows.append({
            "timestamp": t.get("timestamp", "")[:19],
            "event": t.get("event_name", ""),
            "agent_id": payload.get("agent_id", ""),
            "tick": payload.get("tick", ""),
            "messages": payload.get("messages", ""),
            "env_actions": payload.get("environment_actions", ""),
            "activations": payload.get("activations", ""),
            "latency_s": meta.get("latency_seconds", ""),
            "retry": meta.get("retry_count", ""),
            "invalid": meta.get("model_output_invalid", ""),
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    with st.expander("Raw JSON (first 50 matching traces)"):
        filtered = [t for t in traces if t.get("event_name") in selected]
        st.json(filtered[:50])


def view_config(run: dict[str, Any]) -> None:
    env = run["environment"]
    config = run["config"]
    meta = run["metadata"]

    st.subheader("Final environment state")
    col1, col2 = st.columns(2)
    col1.metric("Scenario", env.get("scenario", "—"))
    col1.metric("Final tick", env.get("tick", "—"))
    if env.get("variables"):
        col2.json(env["variables"])

    if config:
        st.subheader("Run configuration")
        st.json({k: v for k, v in config.items() if k != "backend_options"})
        if config.get("backend_options"):
            with st.expander("Backend options"):
                st.json(config["backend_options"])

    st.subheader("Run metadata")
    st.json({k: v for k, v in meta.items() if k != "backend_metrics"})


# ── run list ──────────────────────────────────────────────────────────────────

def _run_label(run_dir: Path) -> str:
    meta = _read_json(run_dir / "metadata.json") or {}
    run_id = meta.get("run_id", run_dir.name)
    scenario = meta.get("scenario", "?")
    backend = meta.get("backend", "?")
    created = meta.get("created_at", "")[:10]
    steps = meta.get("steps", "?")
    return f"{run_id}  ·  {scenario}  ·  {backend}  ·  {steps} steps  ·  {created}"


def _run_list_table(run_dirs: list[Path]) -> None:
    rows = []
    for d in run_dirs:
        meta = _read_json(d / "metadata.json") or {}
        bm = meta.get("backend_metrics", {})
        lat = bm.get("latency_seconds", {})
        rows.append({
            "run_id": meta.get("run_id", d.name),
            "scenario": meta.get("scenario", ""),
            "backend": meta.get("backend", ""),
            "steps": meta.get("steps", ""),
            "replicas": meta.get("agent_replicas", ""),
            "created_at": meta.get("created_at", "")[:19],
            "avg_latency_s": lat.get("avg"),
            "invalid_outputs": bm.get("invalid_model_outputs"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)


# ── main ──────────────────────────────────────────────────────────────────────

def _default_root() -> str:
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg in ("--root-dir", "--root_dir") and i + 1 < len(args):
            return args[i + 1]
    return ""


def main() -> None:
    st.set_page_config(page_title="agentic-sim", layout="wide", page_icon="🤖")
    st.title("agentic-sim dashboard")

    with st.sidebar:
        st.header("Artifact source")
        root_input = st.text_input(
            "Root directory (or run.json path)",
            value=_default_root(),
            help="Point at a directory with metadata.json files, or at a monolithic run.json.",
        )

    if not root_input:
        st.info("Enter an artifact directory or run.json path in the sidebar.")
        st.code("streamlit run scripts/dashboard.py -- --root-dir /path/to/output")
        return

    root = Path(root_input)
    if not root.exists():
        st.error(f"Path not found: `{root}`")
        return

    # Monolithic run.json
    if root.is_file() and root.suffix == ".json":
        run = _load_run_json(root)
        run_dirs: list[Path] = []
        selected_dir = root.parent
    else:
        run_dirs = _find_run_dirs(root)
        if not run_dirs:
            st.error(f"No runs found under `{root}`. Looking for directories containing `metadata.json`.")
            return

        with st.sidebar:
            st.header("Run selection")
            if len(run_dirs) > 1:
                st.caption(f"{len(run_dirs)} runs found")
            selected_dir = st.selectbox(
                "Select run",
                run_dirs,
                format_func=_run_label,
            )
        run = _load_run_dir(selected_dir)

    # Run header
    meta = run["metadata"]
    st.caption(
        f"**{meta.get('run_id', selected_dir.name)}** · "
        f"scenario: `{meta.get('scenario', '?')}` · "
        f"backend: `{meta.get('backend', '?')}` · "
        f"steps: {meta.get('steps', '?')} · "
        f"replicas: {meta.get('agent_replicas', '?')} · "
        f"created: {meta.get('created_at', '?')[:19]}"
    )

    tabs = st.tabs(["Summary", "Tick timeline", "Backend", "Traces", "Config & env", "All runs"])

    with tabs[0]:
        view_summary(run)
    with tabs[1]:
        view_tick_timeline(run)
    with tabs[2]:
        view_backend(run)
    with tabs[3]:
        view_traces(run)
    with tabs[4]:
        view_config(run)
    with tabs[5]:
        if run_dirs:
            st.subheader(f"All runs under `{root}`")
            _run_list_table(run_dirs)
        else:
            st.info("Single-file mode — no run list available.")


if __name__ == "__main__":
    main()
