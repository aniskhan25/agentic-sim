# Storage

Storage is a boundary. The runtime currently includes:

- `InMemoryStateStore` for tests and fast local runs.
- `SQLiteStateStore` for inspectable local persistence.

The engine only depends on repository protocols for agents, events, messages, environment state, and traces.
