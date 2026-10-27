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
3. The registry is process local. Load trusted tool definitions at startup and keep side effects and idempotency in each handler.
4. Run `pytest -q` in CI before deployment.
5. Define workload specific evaluation cases, latency objectives, and rollback criteria before serving real users.

## Execution policy

The registry maps names to `Tool` records with capability sets, required scopes, priority, and a handler. A request selects only tools matching the capability and a subset of granted scopes. Eligible handlers receive copies of the payload and execute in a bounded thread pool. The overall deadline produces explicit timeout results and partial output.

Registration rejects unnamed tools, empty capability sets, non-callable handlers, and duplicate names. A handler must return a dictionary with string keys. Invalid responses and handler exceptions become per-tool errors so another permitted tool can still provide a partial result.

Merge order is deterministic: descending priority, then tool name. The first value for a key wins; different later values are reported as conflicts. Use `conflict_policy="error"` to fail a workflow instead. A timed-out Python thread cannot be forcefully terminated, so handlers must configure network timeouts and be safe if they finish after the orchestration call returns.
