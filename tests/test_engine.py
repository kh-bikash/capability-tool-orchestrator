import pytest
from capability_tool_orchestrator.engine import Orchestrator, Tool


def test_permissions_parallel_merge_and_conflict():
    orch = Orchestrator(max_workers=2)
    orch.register(Tool("primary", frozenset({"lookup"}), frozenset({"read"}), lambda _: {"x": 1}, 10))
    orch.register(Tool("secondary", frozenset({"lookup"}), frozenset(), lambda _: {"x": 2, "y": 3}))
    result = orch.execute("lookup", {}, granted_scopes={"read"})
    assert result.merged == {"x": 1, "y": 3} and result.conflicts == ("x",)
    assert orch.execute("lookup", {}, granted_scopes=set()).merged == {"x": 2, "y": 3}
    with pytest.raises(PermissionError):
        orch.execute("write", {}, granted_scopes={"read"})
