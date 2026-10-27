# Architecture

## Goal

Route a capability to permitted tools, execute them concurrently, and merge outputs with deterministic priority rules.

## Request path

Capability request -> scope filter -> bounded thread pool -> per-tool result capture -> priority ordered merge -> conflict list.

## Components

- `src/capability_tool_orchestrator/engine.py`: policy and state transitions for this project.

- `tests/test_engine.py`: deterministic behavior and failure tests.
- `.github/workflows/ci.yml`: install and test gate.


## State and failure behavior

The orchestrator does not cancel slow Python threads. Set timeouts in individual handlers. Conflicting values keep the highest priority tool's value and are listed for caller review.

The application should propagate failed operations to its caller or queue so the caller can decide whether to retry. Input and handler output are treated as untrusted at the integration boundary.

## Operations checklist

1. Set secrets through a secret manager and rotate them regularly.
2. Put the service or integrating application behind TLS and authentication.
3. Persist SQLite files on durable storage and back them up; migrate to a managed database for high write volume or multiple replicas.
4. Run `pytest -q` in CI before deployment.
5. Define workload specific evaluation cases, latency objectives, and rollback criteria before serving real users.
