from __future__ import annotations

from time import perf_counter

from multiagent_demo.engine.clock import SimulationClock
from multiagent_demo.environment.base import Environment
from multiagent_demo.execution import BatchBuilder, ContextBuilder
from multiagent_demo.execution.base import ExecutionBackend
from multiagent_demo.messaging import MessageRouter
from multiagent_demo.models import Event, ExecutionResult, SimulationTickResult
from multiagent_demo.observability import TraceWriter
from multiagent_demo.scheduling import SchedulerInput
from multiagent_demo.scheduling.base import Scheduler
from multiagent_demo.state.base import RuntimeStore


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
        tracer: TraceWriter | None = None,
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
        self.tracer = tracer or TraceWriter()
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
            self.tracer.write(
                self.store,
                "agent_step",
                {
                    "agent_id": str(result.agent_id),
                    "messages": len(result.outgoing_messages),
                    "environment_actions": len(result.environment_actions),
                    "metadata": result.metadata,
                },
            )
            traces_written += 1
        timings["result_application_ms"] = _elapsed_ms(started)

        started = perf_counter()
        if environment_actions:
            transition = self.environment.apply_actions(
                self.store.environment.get(), environment_actions
            )
            self.store.environment.put(transition.state)
            self.store.events.put_many(transition.emitted_events)
            emitted_events.extend(transition.emitted_events)
        timings["environment_actions_ms"] = _elapsed_ms(started)

        started = perf_counter()
        self.store.events.put_many(emitted_events)
        timings["event_persistence_ms"] = _elapsed_ms(started)
        timings["total_ms"] = _elapsed_ms(step_start)
        self.tracer.write(
            self.store,
            "simulation_tick",
            {
                "tick": self.store.environment.get().tick,
                "processed_events": len(ready_events),
                "activations": len(activations),
                "batches": len(batches),
                "messages_emitted": emitted_messages,
                "timing_ms": timings,
            },
        )
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
