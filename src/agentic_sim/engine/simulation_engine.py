from __future__ import annotations

from time import perf_counter
from typing import Any

from agentic_sim.engine.clock import SimulationClock
from agentic_sim.environment.base import Environment
from agentic_sim.execution import BatchBuilder, ContextBuilder
from agentic_sim.execution.base import ExecutionBackend
from agentic_sim.messaging import MessageRouter
from agentic_sim.models import Event, ExecutionResult, SimulationTickResult, TraceRecord
from agentic_sim.scheduling import SchedulerInput
from agentic_sim.scheduling.base import Scheduler
from agentic_sim.state.base import RuntimeStore


class SimulationEngine:
    """Thin orchestration layer for one event-driven simulation loop."""

    def __init__(
        self,
        *,
        store: RuntimeStore,
        scheduler: Scheduler,
        backend: ExecutionBackend,
        environment: Environment,
        clock: SimulationClock | None = None,
        context_builder: ContextBuilder | None = None,
        batch_builder: BatchBuilder | None = None,
        router: MessageRouter | None = None,
        max_events_per_tick: int = 32,
    ):
        self.store = store
        self.scheduler = scheduler
        self.backend = backend
        self.environment = environment
        self.clock = clock or SimulationClock.start()
        self.context_builder = context_builder or ContextBuilder()
        self.batch_builder = batch_builder or BatchBuilder()
        self.router = router or MessageRouter()
        self.max_events_per_tick = max_events_per_tick

    def run(self, steps: int) -> list[SimulationTickResult]:
        return [self.step() for _ in range(steps)]

    def step(self) -> SimulationTickResult:
        step_start = perf_counter()
        timings: dict[str, float] = {}

        started = perf_counter()
        ready_events = self.store.events.pop_ready(self.clock.now, limit=self.max_events_per_tick)
        if not ready_events:
            ready_events = self._advance_environment()
        timings["event_loading_ms"] = _elapsed_ms(started)

        event_by_id = {event.event_id: event for event in ready_events}
        started = perf_counter()
        activations = self.scheduler.plan(
            SchedulerInput(
                now=self.clock.now,
                events=ready_events,
                agent_profiles=self.store.agents.list_profiles(),
            )
        )
        timings["scheduling_ms"] = _elapsed_ms(started)

        started = perf_counter()
        requests = [
            self.context_builder.build(
                activation=activation,
                triggering_event=event_by_id[activation.trigger_event_id],
                store=self.store,
            )
            for activation in activations
        ]
        timings["context_building_ms"] = _elapsed_ms(started)

        started = perf_counter()
        batches = self.batch_builder.group(requests)
        timings["batching_ms"] = _elapsed_ms(started)
        results: list[ExecutionResult] = []
        started = perf_counter()
        for batch in batches:
            results.extend(self.backend.run_batch(batch))
        timings["backend_execution_ms"] = _elapsed_ms(started)

        emitted_messages = 0
        traces_written = 0
        environment_actions = []
        emitted_events: list[Event] = []

        started = perf_counter()
        for result in results:
            self.store.agents.put_state(result.updated_state)
            emitted_messages += len(result.outgoing_messages)
            self.router.deliver(result.outgoing_messages, self.store)
            environment_actions.extend(result.environment_actions)
            emitted_events.extend(result.emitted_events)
            self.store.traces.put(TraceRecord.create(
                event_name="agent_step",
                payload={
                    "agent_id": str(result.agent_id),
                    "messages": len(result.outgoing_messages),
                    "environment_actions": len(result.environment_actions),
                    "metadata": result.metadata,
                },
            ))
            traces_written += 1
        timings["result_application_ms"] = _elapsed_ms(started)

        started = perf_counter()
        if environment_actions:
            transition = self.environment.apply_actions(
                self.store.environment.get(), environment_actions
            )
            self.store.environment.put(transition.state)
            emitted_events.extend(transition.emitted_events)
        timings["environment_actions_ms"] = _elapsed_ms(started)

        started = perf_counter()
        self.store.events.put_many(emitted_events)
        timings["event_persistence_ms"] = _elapsed_ms(started)
        timings["total_ms"] = _elapsed_ms(step_start)
        self.store.traces.put(TraceRecord.create(
            event_name="simulation_tick",
            payload={
                "tick": self.store.environment.get().tick,
                "processed_events": len(ready_events),
                "activations": len(activations),
                "batches": len(batches),
                "messages_emitted": emitted_messages,
                "timing_ms": timings,
                "backend": _tick_backend_summary(results),
            },
        ))
        traces_written += 1
        self.clock.advance()
        return SimulationTickResult(
            tick=self.store.environment.get().tick,
            processed_events=len(ready_events),
            activations=len(activations),
            messages_emitted=emitted_messages,
            traces_written=traces_written,
        )

    def _advance_environment(self) -> list[Event]:
        transition = self.environment.tick(self.store.environment.get(), self.clock.now)
        self.store.environment.put(transition.state)
        return transition.emitted_events


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)


def _tick_backend_summary(results: list[ExecutionResult]) -> dict[str, Any]:
    latencies: list[float] = []
    retry_count = 0
    validation_failures = 0
    model_names: set[str] = set()
    for result in results:
        m = result.metadata
        lat = m.get("latency_seconds")
        if isinstance(lat, (int, float)):
            latencies.append(float(lat))
        retry_count += int(m.get("retry_count", 0))
        if m.get("model_output_invalid"):
            validation_failures += 1
        model = m.get("model")
        if isinstance(model, str):
            model_names.add(model)
    return {
        "model": next(iter(model_names)) if len(model_names) == 1 else (sorted(model_names) or None),
        "latency_seconds_total": round(sum(latencies), 3) if latencies else None,
        "retry_count": retry_count,
        "validation_failures": validation_failures,
        "agent_steps": len(results),
    }
