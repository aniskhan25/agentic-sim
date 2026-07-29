# ADR 0005: Platform Manifest and Telemetry Normalization

## Status

Proposed.

## Context and Forces

`docs/evaluation_plan.md` requires "separate ROCm/x86 and CUDA/ARM platform manifests" as a Required Output, and Phase 9's exit criteria require that "platform manifests record all material differences" between LUMI and Roihu runs. `src/agentic_sim/models/platform_manifest.py::PlatformManifest` exists as a generic stub (`backend_name`, `accelerator`, `host_architecture`, `python_version`, `framework_versions`) with a docstring already anticipating this ADR: "Phase 9 extends this for ROCm/CUDA self-hosted deployments rather than redesigning it from scratch." It has never been constructed by any real code path — no engine, backend, or CLI command populates it today.

Separately, `evaluation_plan.md`'s Required Substrates section draws a sharp line: "controlled self-hosted inference on LUMI"/"Roihu" are the primary evidence sources; "Aitta, a workstation model server, a cloud OpenAI-compatible endpoint" are explicitly demoted to "optional portability observations," and "shared or managed endpoints are excluded from primary performance conclusions." Today's only real LLM-backed execution path (`AittaExecutionBackend`) is exactly this excluded managed-endpoint case. Nothing in code currently distinguishes "this run used a managed endpoint" from "this run used a self-hosted, platform-manifested deployment" — that distinction needs to be a recorded decision, not left implicit, before any self-hosted backend is built and its results start getting compared against Aitta-backed runs.

This ADR does not invent new architecture. It ratifies `evaluation_plan.md`'s already-stated requirements as the binding shape for `PlatformManifest`, and records the self-hosted-vs-managed-endpoint boundary as a decision rather than an unstated assumption.

## Decision

**Platform manifest fields.** `PlatformManifest` (`models/platform_manifest.py`) is extended, not redesigned, with fields generic enough to describe either LUMI (AMD/ROCm) or Roihu (NVIDIA/CUDA) without hardcoding either: `accelerator_count`, `accelerator_memory_gb`, `driver_version`, `serving_runtime`, `serving_runtime_version`, `interconnect`, `placement_level` (`"single_device"`/`"full_node"`, per `evaluation_plan.md`'s Placement levels), and `manifest_mode` (`"common_denominator"`/`"platform_tuned"`, per its B1/B2 sections). All new fields default to `None` — matching `ExecutionReceipt`'s established discipline of never faking a placeholder value for data that doesn't exist yet. `docs/lumi_deployment_manifest.md` is the concrete, versioned instance of this shape for LUMI; a matching Roihu document is the explicit remainder of roadmap item 17.

**Self-hosted versus managed endpoints.** A run's `PlatformManifest.manifest_mode` being set at all (non-`None`) marks it as a controlled, self-hosted, platform-manifested run eligible for primary performance evidence. Runs through `AittaExecutionBackend` (or any other managed/shared endpoint) never populate `manifest_mode`, `driver_version`, or `serving_runtime_version` — they remain "optional portability observations," per `evaluation_plan.md`'s own wording, never compared as primary performance evidence against self-hosted LUMI/Roihu results. This is a binding decision, not merely a documentation note: any future aggregation/reporting code that compares runs across backends must gate primary-evidence status on `manifest_mode` being populated, not infer it from `backend_name` alone (backend names are provider labels, not evidence-tier signals).

**Version fields are populated at deployment time, never invented.** `driver_version` and `serving_runtime_version` have no default and no computed fallback — `PlatformManifest.for_lumi(...)` requires them as keyword arguments. `evaluation_plan.md`'s own wording ("Hardware details are refreshed when experiments begin and recorded in every platform manifest") is adopted directly: this ADR does not pin a specific ROCm/vLLM version number, since none has been deployed yet.

## Alternatives Considered

- **A single "environment" free-form dict instead of typed fields.** Rejected: `evaluation_plan.md`'s B1/B2 lists name specific, recurring fields (driver/ROCm/CUDA version, serving-runtime revision, placement level, mode) that every LUMI/Roihu manifest will need — typed fields make missing data explicit (`None`) rather than silently absent from an untyped dict, matching this codebase's established "never a fake placeholder" convention elsewhere (`ExecutionReceipt`).
- **Inferring self-hosted-vs-managed from `backend_name` string matching.** Rejected: brittle (a future self-hosted backend might reasonably be named anything) and conflates a provider *label* with an evidence-tier *decision*. An explicit `manifest_mode` field, populated only by self-hosted deployment code paths, keeps the distinction a deliberate act rather than a string-matching heuristic.
- **Deferring the whole `PlatformManifest` extension until a real self-hosted backend exists.** Rejected: the shape is already fully specified by `evaluation_plan.md` today, and building it now (with no consumer yet, same as `PlatformManifest` itself has had since item 3) means the eventual self-hosted backend has a stable, already-tested target to populate rather than inventing the shape under time pressure during Phase 9.

## Consequences

- `docs/lumi_deployment_manifest.md` and any future Roihu equivalent are now expected to be expressed in terms of these exact fields, not ad hoc prose.
- No self-hosted `ExecutionBackend` exists yet, so `manifest_mode`/`driver_version`/`serving_runtime_version` are not populated by any real run today — this ADR states the target shape; it does not require building the backend now.
- Any future code that ranks or compares runs by performance must check `manifest_mode is not None` before treating a run as primary evidence, per the self-hosted/managed-endpoint decision above.
- This is Proposed, not Accepted — accepting it is a separate, explicit decision, not bundled into drafting it.

## Conformance / Verification Method

Today: `tests/test_models.py::test_platform_manifest_for_lumi_fills_known_hardware_constants` verifies `PlatformManifest.for_lumi(...)` populates the fixed LUMI hardware constants correctly and requires the run-time-only fields (`driver_version`, `serving_runtime_version`) to be supplied by the caller, never defaulted.

Once a self-hosted backend exists: conformance additionally means every self-hosted run populates a `PlatformManifest` with `manifest_mode` set, and any aggregation/reporting code that treats a run as primary performance evidence gates on that field being non-`None`. Until then, conformance to this ADR means: any new platform-manifest-adjacent code must be expressible in terms of the field definitions above without contradicting them.
