# Glossary

Terms used across `docs/research_roadmap.md`, `docs/target_architecture.md`, and `docs/evaluation_plan.md`, defined against what they mean in the current code today — not as aspirational architecture. Where the roadmap's term differs from the name already used in code, both are given.

**Event** — an `Event` (`models/event.py`): something that happened in the simulation (an environment transition, a message delivery, a scenario trigger). Carries `event_type`, `target_scope`, `payload`, `priority`, and `correlation_id`. Events are routed by role or agent ID via `target_scope`, and drive which agents get a chance to act each tick.

**Activation** — an `Activation` (`models/execution.py:16-22`): one agent's opportunity to act in response to one triggering event. Fields: `activation_id`, `agent_id`, `trigger_event_id`, `activation_reason`, `priority`, `ready_at`. `FIFOScheduler` decides which activations exist each tick from ready events and the agent roster. There is currently no `attempt_number` — see ADR 0001.

**Proposal** — the raw structure parsed from a backend's output before validation or policy completion: the `proposal` dict inside `AittaExecutionBackend._try_parse`/`_result_from_proposal` (`execution/aitta_backend.py`). May be marked `model_output_invalid` if it couldn't be parsed as JSON after extraction and repair.

**Validated result** — the proposal after (a) schema parsing into typed `Message`/`EnvironmentAction` objects (`_messages`/`_environment_actions` in `aitta_backend.py`, which reject malformed shapes) and (b) semantic validation against the role's contract (`role_policy.semantic_violations`, `execution/role_policy.py`). Today this is tracked as metadata fields (`semantic_valid`, `must_not_violations`), not yet a dedicated typed object — defining that type is Phase 1 item 3 of the roadmap.

**Commit** — persisting an activation's effects into simulation state: in `SimulationEngine.step()` (`engine/simulation_engine.py`), the block that calls `store.agents.put_state`, `router.deliver`, `environment.apply_actions`, and `store.events.put_many`. This is **not yet atomic** — see ADR 0001's Consequences section.

**Policy completion** — what the code and tests call the "policy guard": `role_policy.ensure_required_messages`/`ensure_required_actions` (`execution/role_policy.py`), tracked via the `policy_guard_added_messages`/`policy_guard_added_actions` metadata fields. Deterministically fills in any required message or environment action the model's proposal omitted, computed from ground-truth request data, never from the model's output.

**Fallback** — what happens when a proposal is unusable even after extraction and the bounded re-prompt retry: the backend substitutes a stub proposal (`{"metadata": {"model_output_invalid": True, ...}}`, `_try_parse` in `aitta_backend.py`) and policy completion supplies all required behavior. Tracked via `model_output_invalid`.

**Useful agent step** — a committed activation whose final result satisfies its contracts (zero `must_not` violations, every `must` requirement present). Approximated today by the `useful_step` metadata field (`aitta_backend.py`), aggregated into `useful_agent_steps_per_second` in `_backend_metrics`/`aggregate_run_stats` (`observability/artifacts.py`) using `simulation_tick` trace wall-clock time, not summed per-step latency.
