# Architecture

The system is a small event-driven simulation kernel with explicit state, pluggable execution backends, structured messaging, and persistent traces.

The main loop is:

1. Pop ready events.
2. Plan agent activations.
3. Hydrate agent state and recent messages.
4. Build execution requests.
5. Execute batches through a backend.
6. Persist state updates, messages, events, and environment changes.
7. Write traces and advance the clock.

```mermaid
flowchart TD
    A([tick start]) --> B[pop ready events]
    B --> C{events ready?}
    C -- no --> Z([idle])
    C -- yes --> D[plan activations]
    D --> E[hydrate state + inbox]
    E --> F[build execution requests]
    F --> G[execute batch]
    G --> H[persist state · messages · events · env]
    H --> I[write traces · advance clock]
    I --> B
```

Storage, scheduling, execution, environment dynamics, and observability are independent boundaries. The engine coordinates them but does not own their internal logic.
