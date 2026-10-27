from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Tool:
    name: str
    capabilities: frozenset[str]
    required_scopes: frozenset[str]
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    priority: int = 0


@dataclass(frozen=True)
class ToolResult:
    tool: str
    value: dict[str, Any] | None
    error: str | None


@dataclass(frozen=True)
class OrchestrationResult:
    merged: dict[str, Any]
    results: tuple[ToolResult, ...]
    conflicts: tuple[str, ...]


class Orchestrator:
    def __init__(self, *, max_workers: int = 4):
        if max_workers < 1:
            raise ValueError("max_workers must be positive")
        self.max_workers = max_workers
        self.registry: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if not tool.name or not tool.capabilities or not callable(tool.handler):
            raise ValueError("tool needs a name, capability, and callable handler")
        if tool.name in self.registry:
            raise ValueError("duplicate tool: " + tool.name)
        self.registry[tool.name] = tool

    def execute(
        self,
        capability: str,
        payload: dict[str, Any],
        *,
        granted_scopes: set[str],
        timeout_seconds: float = 10,
        conflict_policy: str = "priority",
    ) -> OrchestrationResult:
        if timeout_seconds <= 0 or conflict_policy not in {"priority", "error"}:
            raise ValueError("invalid timeout or conflict policy")
        eligible = [
            tool
            for tool in self.registry.values()
            if capability in tool.capabilities
            and tool.required_scopes <= granted_scopes
        ]
        if not eligible:
            raise PermissionError("No permitted tool supports " + capability)
        outputs: dict[str, ToolResult] = {}
        pool = ThreadPoolExecutor(max_workers=min(self.max_workers, len(eligible)))
        try:
            futures = {
                pool.submit(tool.handler, dict(payload)): tool for tool in eligible
            }
            done, pending = wait(futures, timeout=timeout_seconds)
            for future in done:
                tool = futures[future]
                try:
                    value = future.result()
                    if not isinstance(value, dict) or any(
                        not isinstance(key, str) for key in value
                    ):
                        raise TypeError("tool response must be a dict with string keys")
                    outputs[tool.name] = ToolResult(tool.name, value, None)
                except Exception as exc:  # noqa: BLE001 - isolate failures from untrusted tool handlers
                    outputs[tool.name] = ToolResult(
                        tool.name, None, type(exc).__name__ + ": " + str(exc)
                    )
            for future in pending:
                future.cancel()
                outputs[futures[future].name] = ToolResult(
                    futures[future].name, None, "TimeoutError: tool deadline exceeded"
                )
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        ordered = sorted(eligible, key=lambda t: (-t.priority, t.name))
        merged: dict[str, Any] = {}
        conflicts: list[str] = []
        for tool in ordered:
            result = outputs[tool.name]
            if result.value is None:
                continue
            for key, value in result.value.items():
                if key in merged and merged[key] != value:
                    conflicts.append(key)
                else:
                    merged[key] = value
        if conflicts and conflict_policy == "error":
            raise ValueError(
                "Conflicting tool outputs: " + ", ".join(sorted(set(conflicts)))
            )
        return OrchestrationResult(
            merged,
            tuple(outputs[t.name] for t in ordered),
            tuple(sorted(set(conflicts))),
        )
