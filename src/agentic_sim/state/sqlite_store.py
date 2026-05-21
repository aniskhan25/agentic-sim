from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from agentic_sim.models import (
    AgentId,
    AgentProfile,
    AgentState,
    AgentStatus,
    EnvironmentState,
    Event,
    EventType,
    Message,
    MessageType,
    TraceRecord,
)
from agentic_sim.utils.serialization import to_jsonable
from agentic_sim.utils.time import from_iso, to_iso


class SQLiteStateStore:
    """SQLite-backed implementation of the runtime repository protocols."""

    def __init__(self, path: str | Path, environment: EnvironmentState | None = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.agents = self
        self.events = self
        self.messages = self
        self.environment = self
        self.traces = self
        self._migrate()
        if environment is not None:
            self.put(environment)

    def close(self) -> None:
        self.conn.close()

    def _migrate(self) -> None:
        self.conn.executescript(
            """
            create table if not exists agent_profiles (
                agent_id text primary key,
                payload text not null
            );
            create table if not exists agent_states (
                agent_id text primary key,
                payload text not null
            );
            create table if not exists events (
                event_id text primary key,
                scheduled_for text not null,
                priority integer not null,
                payload text not null
            );
            create table if not exists messages (
                message_id text primary key,
                recipient_id text not null,
                created_at text not null,
                priority integer not null,
                payload text not null
            );
            create table if not exists environment (
                singleton integer primary key check (singleton = 1),
                payload text not null
            );
            create table if not exists traces (
                trace_id text primary key,
                timestamp text not null,
                event_name text not null,
                payload text not null
            );
            """
        )
        self.conn.commit()

    def get_profile(self, agent_id: AgentId) -> AgentProfile:
        row = self.conn.execute(
            "select payload from agent_profiles where agent_id = ?", (str(agent_id),)
        ).fetchone()
        if row is None:
            raise KeyError(agent_id)
        return _profile_from_dict(json.loads(row["payload"]))

    def put_profile(self, profile: AgentProfile) -> None:
        self.conn.execute(
            "insert or replace into agent_profiles(agent_id, payload) values (?, ?)",
            (str(profile.agent_id), json.dumps(to_jsonable(profile))),
        )
        self.conn.commit()

    def list_profiles(self) -> list[AgentProfile]:
        rows = self.conn.execute("select payload from agent_profiles").fetchall()
        return [_profile_from_dict(json.loads(row["payload"])) for row in rows]

    def get_state(self, agent_id: AgentId) -> AgentState:
        row = self.conn.execute(
            "select payload from agent_states where agent_id = ?", (str(agent_id),)
        ).fetchone()
        if row is None:
            raise KeyError(agent_id)
        return _state_from_dict(json.loads(row["payload"]))

    def put_state(self, state: AgentState) -> None:
        self.conn.execute(
            "insert or replace into agent_states(agent_id, payload) values (?, ?)",
            (str(state.agent_id), json.dumps(to_jsonable(state))),
        )
        self.conn.commit()

    def put(self, item: Event | Message | EnvironmentState | TraceRecord) -> None:
        if isinstance(item, Event):
            self.conn.execute(
                """
                insert or replace into events(event_id, scheduled_for, priority, payload)
                values (?, ?, ?, ?)
                """,
                (
                    item.event_id,
                    to_iso(item.scheduled_for),
                    item.priority,
                    json.dumps(to_jsonable(item)),
                ),
            )
        elif isinstance(item, Message):
            self.conn.execute(
                """
                insert or replace into messages(message_id, recipient_id, created_at, priority, payload)
                values (?, ?, ?, ?, ?)
                """,
                (
                    item.message_id,
                    str(item.recipient_id),
                    to_iso(item.created_at),
                    item.priority,
                    json.dumps(to_jsonable(item)),
                ),
            )
        elif isinstance(item, EnvironmentState):
            self.conn.execute(
                "insert or replace into environment(singleton, payload) values (1, ?)",
                (json.dumps(to_jsonable(item)),),
            )
        elif isinstance(item, TraceRecord):
            self.conn.execute(
                "insert or replace into traces(trace_id, timestamp, event_name, payload) values (?, ?, ?, ?)",
                (
                    item.trace_id,
                    to_iso(item.timestamp),
                    item.event_name,
                    json.dumps(to_jsonable(item.payload)),
                ),
            )
        else:
            raise TypeError(f"unsupported store item: {type(item)!r}")
        self.conn.commit()

    def put_many(self, items: list[Event] | list[Message]) -> None:
        for item in items:
            self.put(item)

    def pop_ready(self, now: datetime, limit: int | None = None) -> list[Event]:
        query = """
            select event_id, payload from events
            where scheduled_for <= ?
            order by priority desc, scheduled_for asc
        """
        params: tuple[Any, ...] = (to_iso(now),)
        if limit is not None:
            query += " limit ?"
            params = (to_iso(now), limit)
        rows = self.conn.execute(query, params).fetchall()
        events = [_event_from_dict(json.loads(row["payload"])) for row in rows]
        self.conn.executemany(
            "delete from events where event_id = ?",
            [(event.event_id,) for event in events],
        )
        self.conn.commit()
        return events

    def count_pending(self) -> int:
        row = self.conn.execute("select count(*) as count from events").fetchone()
        return int(row["count"])

    def inbox(self, agent_id: AgentId, limit: int = 10) -> list[Message]:
        rows = self.conn.execute(
            """
            select payload from messages
            where recipient_id = ?
            order by priority desc, created_at asc
            limit ?
            """,
            (str(agent_id), limit),
        ).fetchall()
        return [_message_from_dict(json.loads(row["payload"])) for row in rows]

    def count(self) -> int:
        row = self.conn.execute("select count(*) as count from messages").fetchone()
        return int(row["count"])

    def get(self) -> EnvironmentState:
        row = self.conn.execute("select payload from environment where singleton = 1").fetchone()
        if row is None:
            raise RuntimeError("environment state has not been initialized")
        return _environment_from_dict(json.loads(row["payload"]))

    def list(self) -> list[TraceRecord]:
        rows = self.conn.execute("select * from traces order by timestamp asc").fetchall()
        return [
            TraceRecord(
                trace_id=row["trace_id"],
                timestamp=from_iso(row["timestamp"]),
                event_name=row["event_name"],
                payload=json.loads(row["payload"]),
            )
            for row in rows
        ]


def _profile_from_dict(data: dict[str, Any]) -> AgentProfile:
    return AgentProfile(
        agent_id=AgentId(data["agent_id"]),
        role=data["role"],
        name=data["name"],
        region=data["region"],
        capabilities=list(data.get("capabilities", [])),
        authority_level=int(data.get("authority_level", 0)),
        backend=data.get("backend", "mock"),
    )


def _state_from_dict(data: dict[str, Any]) -> AgentState:
    return AgentState(
        agent_id=AgentId(data["agent_id"]),
        status=AgentStatus(data.get("status", AgentStatus.IDLE.value)),
        current_goal=data.get("current_goal", ""),
        working_memory=dict(data.get("working_memory", {})),
        pending_tasks=list(data.get("pending_tasks", [])),
        inbox_cursor=data.get("inbox_cursor"),
        last_active_at=from_iso(data["last_active_at"]) if data.get("last_active_at") else None,
        metrics=dict(data.get("metrics", {})),
    )


def _event_from_dict(data: dict[str, Any]) -> Event:
    return Event(
        event_id=data["event_id"],
        event_type=EventType(data["event_type"]),
        created_at=from_iso(data["created_at"]),
        scheduled_for=from_iso(data["scheduled_for"]),
        source=data["source"],
        target_scope=dict(data.get("target_scope", {})),
        payload=dict(data.get("payload", {})),
        priority=int(data.get("priority", 0)),
        correlation_id=data.get("correlation_id"),
    )


def _message_from_dict(data: dict[str, Any]) -> Message:
    return Message(
        message_id=data["message_id"],
        sender_id=AgentId(data["sender_id"]),
        recipient_id=AgentId(data["recipient_id"]),
        message_type=MessageType(data["message_type"]),
        priority=int(data.get("priority", 0)),
        created_at=from_iso(data["created_at"]),
        payload=dict(data.get("payload", {})),
        thread_id=data.get("thread_id"),
        reply_to=data.get("reply_to"),
        correlation_id=data.get("correlation_id"),
    )


def _environment_from_dict(data: dict[str, Any]) -> EnvironmentState:
    return EnvironmentState(
        scenario=data["scenario"],
        tick=int(data["tick"]),
        updated_at=from_iso(data["updated_at"]),
        variables=dict(data.get("variables", {})),
    )
