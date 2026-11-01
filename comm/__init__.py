"""V2X communication layer (WP3): TrackMsg contract, deterministic discrete-event channel, AoI, admission, store, relay, telemetry.
I9: this package may import only stdlib, numpy, jsonschema, perception.*, comm.* and backend.observation. It must never import truth-side modules
(enforced by tests/comm/test_com10_isolation_and_policy.py). All time is SIMULATION time; nothing here reads the wall clock."""
