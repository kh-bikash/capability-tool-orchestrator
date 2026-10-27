# Capability Tool Orchestrator

Route a capability to permitted tools, execute them concurrently, and merge outputs with deterministic priority rules.

Set `timeout_seconds` to bound orchestration latency and `conflict_policy="error"` when conflicting outputs must stop the workflow. Timed out handlers are cancelled when possible; in-flight Python threads must still implement their own I/O timeouts.

## Quick start

Requires Python 3.11 or newer. From this repository:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
pytest -q
```

This project uses deterministic tests and needs no model key for verification.

```python
from capability_tool_orchestrator.engine import Orchestrator, Tool

orchestrator = Orchestrator(max_workers=2)
orchestrator.register(Tool("catalog", frozenset({"lookup"}), frozenset({"read"}), lambda q: {"item": q["id"]}, priority=10))
print(orchestrator.execute("lookup", {"id": "42"}, granted_scopes={"read"}))
```

## Architecture

Capability request -> scope filter -> bounded thread pool -> per-tool result capture -> priority ordered merge -> conflict list.

See [ARCHITECTURE.md](ARCHITECTURE.md) for components, state, failure behavior, and operations.

## Deployment and safety

The orchestrator does not cancel slow Python threads. Set timeouts in individual handlers. Conflicting values keep the highest priority tool's value and are listed for caller review.

Install this as a library in an authenticated application or worker. Register trusted handlers and keep application secrets outside source control.

## Verification

`pytest -q` runs deterministic tests. GitHub Actions runs the same suite on pushes and pull requests.

## License

MIT. See [LICENSE](LICENSE).
