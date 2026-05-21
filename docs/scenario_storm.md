# Storm Scenario

The first scenario models a regional storm response. Agents represent a coordinator, hospital, utility operator, and forecaster. The environment tracks storm severity and affected regions, then emits structured update events when thresholds change.

The scenario is intentionally small. Its purpose is to exercise event-driven activation, structured messaging, state persistence, and traceability without requiring real weather data or model serving.
