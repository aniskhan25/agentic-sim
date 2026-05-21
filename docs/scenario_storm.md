# Storm Scenario

The first scenario models a regional storm response. Agents represent a coordinator, hospital, utility operator, and forecaster. The environment tracks storm severity and affected regions, then emits structured update events when thresholds change.

When severity reaches the pressure threshold, the environment also emits a `storm_outage` event targeted to the coordinator and utility operator. This keeps incident behavior explicit and replayable without adding real weather feeds.

The scenario is intentionally small. Its purpose is to exercise event-driven activation, structured messaging, state persistence, and traceability without requiring real weather data or model serving.
