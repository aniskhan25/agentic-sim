# Target Architecture: Portable Causal Execution

## Status and Scope

This document is the canonical architecture specification for the research system described in [research_roadmap.md](research_roadmap.md). The roadmap owns sequencing and milestones; this document owns component responsibilities, dependency direction, execution semantics, commit behavior, and delivery gates.

The architecture is a maintainability and research-validity requirement, not a standalone novelty claim. It exists to make the causal scheduling contribution explicit, testable, replaceable, and measurable.

## Execution Path

```text
scenario and environment
        |
        v
causal activation specification
        |
        v
scheduling and placement policy
        |
        v
provider-neutral execution request
        |
        +---- local deterministic backend
        +---- OpenAI-compatible managed endpoint
        +---- local/self-hosted model server
        +---- LUMI AMD/ROCm model service
        +---- Roihu NVIDIA/CUDA model service
        +---- other distributed or HPC model service
        |
        v
proposal -> schema validation -> semantic validation
        -> optional repair -> fallback or policy completion
        |
        v
atomic idempotent commit and execution receipt
```

Stable boundaries separate:

- scenario semantics;
- causal execution planning;
- provider placement and request dispatch;
- proposal validation and policy enforcement;
- atomic state commit;
- provenance and measurement.

## Package Responsibilities

The system follows a ports-and-adapters dependency rule. Existing modules migrate one boundary at a time rather than through a repository-wide rewrite.

```text
agentic_sim/
    domain/              # Pure simulation values and semantic rules
        agents
        events
        messages
        state
        contracts
        causality

    runtime/             # Provider-neutral use cases and policies
        activation_planner
        scheduler
        dispatcher
        validation
        commit
        replay
        engine

    ports/               # Narrow interfaces owned by the runtime
        execution
        state_store
        telemetry
        clock

    adapters/            # Replaceable infrastructure implementations
        execution/
            deterministic
            openai_compatible
            self_hosted
        storage/
            memory
            sqlite
        telemetry/
            local
            rocm
            cuda

    scenarios/           # Scenario composition, fixtures, and contracts
        storm
        supply_chain
        synthetic

    observability/       # Provider-neutral receipts and artifact views
    config/              # Parsing and validation at the application edge
    cli/                 # Composition root and user entry points
```

Dependency direction:

```text
                    composition root
                   /                \
         concrete scenarios    concrete adapters
              |       \             /
              v        v           v
            domain <- runtime -> ports
```

The composition root may know concrete scenarios and adapters. Runtime policy depends on domain values and runtime-owned ports. Scenarios depend on domain values and may implement a runtime-owned scenario or environment port. Adapters implement ports. Domain code depends on none of these outer layers.

## Architectural Rules

1. **Scenarios describe behavior, not infrastructure.** A scenario may define agents, fixtures, contracts, and environment transitions. It may not select Aitta, vLLM, ROCm, CUDA, Slurm, SQLite, or HTTP behavior.
2. **Adapters translate; they do not decide simulation policy.** Provider adapters serialize requests, invoke services, normalize responses, and expose capabilities. They do not add required messages or scenario actions.
3. **Schedulers decide; they do not execute or mutate.** A scheduler consumes immutable readiness and capability snapshots and returns an explainable execution plan.
4. **Validators assess proposals; they do not commit.** Schema, semantic, and contract validation return structured decisions and provenance.
5. **The commit layer is the sole mutation path.** In one atomic transaction, it verifies state versions and idempotency, applies accepted state and environment changes, writes messages and events, advances the causal frontier, and records the execution receipt. A failure commits none of these effects.
6. **Telemetry observes.** Metrics do not affect behavior unless routed explicitly through a typed scheduling-policy input.
7. **Configuration is parsed at the edge.** Core components receive typed configuration rather than reading environment variables or provider-specific dictionaries.
8. **Public interfaces are small and typed.** Prefer immutable dataclasses, enums, and narrow protocols over unstructured dictionaries at component boundaries.
9. **Provider errors are normalized.** Timeouts, capacity failures, malformed responses, cancellation, and unsupported capabilities have provider-neutral categories.
10. **Performance-sensitive paths remain visible.** Batching, store access, serialization, validation, and tracing costs are measured independently.
11. **Abstractions earn their cost.** Add an interface only for a necessary test boundary or multiple implementations, and retain it only when its complexity and performance cost remain justified.

These rules are enforced through automated dependency checks, adapter conformance suites, architectural tests, and decision records.

## Change-Isolation Requirements

The architecture must support:

- adding an OpenAI-compatible provider through an adapter, configuration wiring, and conformance tests without scenario changes;
- adding a storage backend without scheduling or validation changes;
- adding a scenario without provider-adapter changes;
- adding a contract type without transport changes;
- adding ROCm or CUDA telemetry without changing simulation results;
- changing a scheduling policy without changing commit or storage implementations.

## Core Data Model

### Activation specification

A provider-neutral activation record contains at least:

- activation and agent identifiers;
- triggering event and causal-parent identifiers;
- logical time;
- state and environment versions read;
- declared read and write scopes;
- input context or a content-addressed reference;
- expected output schema;
- semantic contract identifier;
- priority and optional logical deadline;
- model capability requirements;
- retry, repair, and fallback policy identifiers.

The first implementation may use conservative read and write scopes. More precise conflict detection follows only after the semantics and verifier are tested.

### Provider capabilities

Capabilities describe what a provider can do; configuration describes how to connect to it. Both remain separate from scenario code.

```python
ProviderCapabilities(
    supports_concurrency=True,
    supports_server_batching=False,
    supports_structured_output=True,
    supports_prefix_caching=False,
    max_context_tokens=32768,
    observable_token_usage=True,
    observable_energy=False,
)
```

### Execution receipt

Every activation attempt emits a receipt containing:

- activation ID and attempt number;
- provider, model, and model revision when available;
- request, prompt, and raw-response hashes;
- state version read and commit version written;
- causal parents;
- dispatch, queue, inference, validation, and commit timings;
- token usage and provider cost when available;
- accelerator, host architecture, serving-runtime, and environment identifiers;
- schema and semantic validation outcomes;
- repair, policy-completion, and fallback provenance;
- final commit status;
- error or rejection reason.

Raw model content may be stored separately or redacted, but its hash and provenance remain stable.

## Observational Semantics

Semantic preservation is defined before concurrent execution. For a run \(r\), the observation projection \(O(r)\) contains scenario-visible committed behavior:

- committed activation identities and causal-parent relationships;
- versioned agent and environment state transitions;
- committed messages, including sender, recipient, logical time, and normalized payload;
- committed environment actions and externally visible effects;
- contract, rejection, repair, policy-completion, and fallback outcomes;
- scenario barriers, deadlines, and invariant outcomes.

The projection excludes wall-clock timing, provider telemetry, dispatch order, and the relative commit order of independent activations when those values are not visible to scenario behavior. Raw natural-language text is excluded only when it is neither persisted as scenario state nor interpreted by subsequent activations; its hash and provenance remain auditable.

Given the same workload identity, configuration, seed, and deterministic or response-replayed model outputs:

- **strict equivalence:** the canonical committed trace and observation projection are identical to the sequential reference;
- **causal equivalence:** the same behavior and required `happens-before` edges are present, while topological order may differ for independent, non-conflicting activations;
- **relaxed equivalence:** differences are permitted only within workload-declared staleness or approximation bounds and are reported explicitly.

Fresh-model replay does not assert output equality. It preserves workload identity, causal well-formedness, commit invariants, and contract accounting while reporting behavioral divergence.

## Atomic Commit Protocol

One commit transaction contains:

- accepted agent and environment mutations;
- outgoing messages and events;
- causal-frontier advancement;
- state-version and conflict checks;
- the activation idempotency key;
- behavior provenance;
- the final execution receipt.

The state-store port provides all-or-nothing behavior for this unit. Recovery may retry an uncommitted proposal but must never expose a partial commit or apply an activation twice.

## Required Architecture Decision Records

Decision records live under [adr/](adr/) and initially cover:

- activation specification ownership and shape;
- observational equivalence and causal ordering;
- execution proposal and receipt boundaries;
- atomic commit, state versioning, and idempotency;
- synchronous and asynchronous provider interfaces;
- validation, repair, policy completion, and fallback ordering;
- platform manifests and telemetry normalization.

The first ADR must settle observational equivalence, activation identity, receipt ownership, and atomic commit semantics before substantial scheduler implementation.

## Cross-Cutting Delivery Gates

Every implementation phase must pass these gates.

### Correctness

- unit tests cover new domain and policy behavior;
- provider, store, and telemetry adapters pass shared conformance suites;
- deterministic behavior signatures change only for documented semantic changes;
- fault paths are testable without live services.

### Architecture

- dependency rules run automatically;
- provider and platform names do not leak into domain or runtime policy;
- public interfaces and ownership decisions are documented;
- material decisions add or update an ADR.

### Understandability

- modules and functions have one identifiable responsibility;
- control flow is explicit rather than hidden in global state or callback side effects;
- examples exercise public interfaces;
- terminology is consistent across code, traces, configuration, and documentation.

### Performance

- deterministic microbenchmarks separate scheduler, context construction, batching, validation, commit, storage, serialization, and tracing costs;
- baselines are versioned before performance-sensitive refactors;
- optimizations include evidence and preserve causal and contract validation;
- regressions beyond an agreed tolerance require explanation or explicit acceptance.

### Repository quality

- formatting, static analysis, and tests use documented commands;
- optional provider dependencies remain isolated extras;
- generated artifacts, credentials, and machine-local paths stay outside source control;
- raw research artifacts use stable schemas and version identifiers.
