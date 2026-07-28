# Architecture Decision Records

This directory contains binding decisions for the portable causal execution architecture. The canonical architecture specification is [../target_architecture.md](../target_architecture.md), and implementation sequencing is tracked in [../research_roadmap.md](../research_roadmap.md).

## Process

Use numbered files such as `0001-observational-semantics-and-commit.md`. Each record should contain:

1. title and status;
2. context and forces;
3. decision;
4. alternatives considered;
5. consequences;
6. conformance or verification method.

Accepted records are changed through a superseding ADR rather than silently rewritten after implementation depends on them.

## Initial Decisions

| ID | Decision | Status |
| --- | --- | --- |
| 0001 | Observational equivalence, activation identity, execution receipt, and atomic commit | Proposed |
| 0002 | Runtime-owned provider, store, clock, and telemetry ports | Proposed |
| 0003 | Causal readiness, conflicts, and permitted concurrency | Proposed |
| 0004 | Validation, repair, policy-completion, and fallback ordering | Proposed |
| 0005 | Platform manifest and telemetry normalization | Proposed |

The first record must be accepted before substantial asynchronous scheduler work begins.
