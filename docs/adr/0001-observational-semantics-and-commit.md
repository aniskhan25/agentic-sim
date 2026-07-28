# ADR 0001: Observational Equivalence, Activation Identity, Execution Receipt, and Atomic Commit

## Status

Accepted.

## Context and Forces

`docs/target_architecture.md` already specifies an observation projection with strict/causal/relaxed equivalence modes, an activation specification, an execution receipt shape, and an atomic commit protocol. None of that is binding yet — it is architecture prose, not a ratified decision. The roadmap's Phase 1 gates all later work (provider-neutral types, ports, and eventually the causal scheduler in Phase 6) behind exactly these four decisions being settled first: without a fixed notion of "same behavior" across execution modes, RQ2 (safe concurrency) cannot be tested at all — any reordering would be unfalsifiable as either preserving or violating semantics.

This ADR does not invent new architecture. It ratifies the relevant sections of `target_architecture.md` as the binding decision, and records where today's code already matches it, where it doesn't yet, and why the alternatives were rejected.

## Decision

**Activation identity.** The existing `Activation` dataclass (`src/agentic_sim/models/execution.py:16-22`) is adopted as-is: `(activation_id, agent_id, trigger_event_id, activation_reason, priority, ready_at)`, with `activation_id` as the durable identity key. This already exists in code and requires no change to adopt.

Gap: there is no `attempt_number` field. Today, `AittaExecutionBackend`'s bounded JSON-repair re-prompt (`_run_one`, `execution/aitta_backend.py`) issues multiple model calls for a single activation without modeling them as distinct attempts — retries are invisible above the backend. This is an accepted gap, not a defect: modeling attempts explicitly is scoped to Phase 1 item 3 (defining the formal activation/proposal/receipt types), not this ADR.

**Receipt ownership.** Today's `TraceRecord` (`models/trace.py:12-16`, written as `agent_step`/`simulation_tick` events) plus `ExecutionResult.metadata` is the interim execution receipt. It does not yet satisfy `target_architecture.md`'s full receipt shape: no request/prompt/response hashes, no explicit state-version-read/commit-version-written pair, no accelerator/serving-runtime identifiers. This ADR states what the eventual formal receipt type (Phase 1 item 3) must contain; it does not require building that type now.

**Atomic commit.** Today's commit path, `SimulationEngine.step()` (`engine/simulation_engine.py`), performs `store.agents.put_state(...)`, `router.deliver(...)`, `environment.apply_actions(...)`, and `store.events.put_many(...)` as separate calls — **not** a single atomic transaction. Accepting this ADR commits the project to the single-transaction target in `target_architecture.md`'s Atomic Commit Protocol section as the Phase 5 deliverable. It does not require refactoring `step()` now, and today's code is not retroactively "wrong" for predating this decision — Phase 5 is where it becomes binding.

**Observational equivalence.** Adopt the three-mode model from `target_architecture.md` (strict, causal, relaxed) and its observation projection `O(r)`, rather than requiring strict re-execution equivalence everywhere. See Alternatives.

## Alternatives Considered

- **Activation identity via content-addressed hash of input vs. an assigned ID.** Rejected content-hashing for now: it would require a stable, canonical serialization of the full activation context before any of that is defined, and buys nothing today since no distributed or multi-attempt execution exists yet to need content-addressing for deduplication. The assigned `activation_id` already in code is sufficient once paired with state-version checks in Phase 5.
- **Eventual-consistency or multi-step commit vs. one atomic transaction.** Rejected eventual consistency: there is no distributed state today (Design Principle 7: single-process causal scheduling precedes distributed state), so there is no forcing function for anything looser than one atomic per-tick transaction, and looser consistency would make the causal verifier (Phase 4) unable to make any hard guarantee.
- **Strict-only observational equivalence vs. the three-mode model.** Rejected strict-only: if "same behavior" only ever means "byte-identical trace to sequential execution," then Phase 4+'s introduction of any reordering — even provably safe, non-conflicting reordering — would trivially violate equivalence by definition, foreclosing RQ2 before it could be tested. The three-mode model (strict/causal/relaxed) makes it possible to state a reordering preserves *causal* equivalence without requiring it preserve *strict* equivalence.

## Consequences

- No code changes are required to accept this ADR. `test_replay.py`'s deterministic behavior-signature tests (storm and, as of this round, supply_chain) already demonstrate strict equivalence trivially, since no concurrency exists yet to make strict and causal modes diverge.
- Phase 1 items 3-4 (proposal/validation/activation/receipt/platform-manifest types; narrow execution/store/clock/telemetry ports) are now concretely scoped by this decision rather than open-ended.
- Phase 5's atomic-commit implementation is now a committed target, not an optional nice-to-have.
- These decisions are binding: any new activation, receipt, or commit-related code going forward must be expressible in terms of the identity/receipt/commit definitions above without contradicting them. Changing them requires a superseding ADR, not a silent rewrite (per `adr/README.md`'s process).

## Conformance / Verification Method

Today: the deterministic behavior-signature tests in `tests/test_replay.py` (`test_storm_run_has_deterministic_behavior_signature`, `test_supply_chain_run_has_deterministic_behavior_signature`) are the current verification of strict equivalence — re-running a scenario twice must produce an identical signature.

Once built: the causal verifier (Phase 4) will check causal equivalence (missing parents, conflicts, stale reads, duplicates, cycles), and the atomic-commit conformance suite (Phase 5) will check that no duplicate, late, or partial commit can occur. Until then, conformance to this ADR means: any new activation, receipt, or commit-related code must be expressible in terms of the identity/receipt/commit definitions above without contradicting them.
