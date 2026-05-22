# Supply Chain Scenario

The supply-chain scenario models a regional logistics network under rising demand and shipment delays. Agents represent a coordinator, suppliers, warehouses, transport operators, and retailers. The environment tracks demand, inventory, delayed shipments, transport capacity, and risk level.

Each environment tick increases demand and delayed shipments, then emits a `supply_chain_update` event. When delays grow, it also emits a `shipment_delay` event. When regional inventory drops below demand pressure, it emits an `inventory_shortage` event.

The scenario is deterministic. Its purpose is to prove that the runtime can run more than one domain without changing the engine loop. Scenario-specific behavior lives in the environment, profiles, config, and deterministic rule backend.

Run the small example:

```bash
PYTHONPATH=src python3 -m agentic_sim.cli run \
  --config configs/supply_chain_small.json
```

Run the scale smoke test:

```bash
PYTHONPATH=src python3 -m agentic_sim.cli run \
  --config configs/supply_chain_scale.json
```
