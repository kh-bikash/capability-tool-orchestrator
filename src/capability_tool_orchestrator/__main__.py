"""Run scoped, config-driven HTTP or static tools from CLI and browser."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .engine import Orchestrator, Tool
from .web import serve

WEB_ACTIONS = {
    "run": [
        ("capability", "Capability", "text", True),
        ("payload", "JSON payload", "textarea", True),
        ("scopes", "Granted scopes, comma separated", "text", False),
    ]
}


def _handler(spec: dict, timeout: float):
    kind = spec.get("kind")
    if kind == "static":
        value = spec["value"]
        if not isinstance(value, dict):
            raise ValueError("static tool value must be an object")
        return lambda _: dict(value)
    if kind != "http":
        raise ValueError("tool kind must be static or http")
    url = spec["url"]
    parsed = urlparse(url)
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    ):
        raise ValueError("HTTP tools require HTTPS or loopback")
    bearer_env = spec.get("bearer_env")

    def call(payload: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if bearer_env:
            token = os.environ.get(bearer_env)
            if not token:
                raise RuntimeError("missing tool credential environment variable")
            headers["Authorization"] = "Bearer " + token
        request = Request(
            url,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=timeout) as response:
            data = json.load(response)
        if not isinstance(data, dict):
            raise TypeError("tool response must be a JSON object")
        return data

    return call


def execute(action: str, values: dict, *, manifest: str, timeout: float) -> object:
    if action != "run":
        raise ValueError("unknown action")
    config = json.loads(Path(manifest).read_text(encoding="utf-8"))
    if not isinstance(config, list) or not config:
        raise ValueError("manifest must contain a nonempty tool array")
    orchestrator = Orchestrator()
    for spec in config:
        orchestrator.register(
            Tool(
                spec["name"],
                frozenset(spec["capabilities"]),
                frozenset(spec.get("scopes", [])),
                _handler(spec, timeout),
                int(spec.get("priority", 0)),
            )
        )
    payload = json.loads(values["payload"])
    if not isinstance(payload, dict):
        raise TypeError("payload must be a JSON object")
    raw_scopes = values.get("scopes", "")
    scopes = (
        set(raw_scopes)
        if isinstance(raw_scopes, list)
        else {value.strip() for value in raw_scopes.split(",") if value.strip()}
    )
    result = orchestrator.execute(
        values["capability"], payload, granted_scopes=scopes, timeout_seconds=timeout
    )
    return {
        "merged": result.merged,
        "results": [entry.__dict__ for entry in result.results],
        "conflicts": result.conflicts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scoped multi-tool execution")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--timeout", type=float, default=10)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("capability")
    run.add_argument("payload", help="JSON object")
    run.add_argument("--scope", dest="scopes", action="append", default=[])
    browser = commands.add_parser("serve")
    browser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)
    if args.command == "serve":
        serve(
            "Capability Tool Orchestrator",
            WEB_ACTIONS,
            lambda action, values: execute(
                action, values, manifest=args.manifest, timeout=args.timeout
            ),
            port=args.port,
        )
    else:
        print(
            json.dumps(
                execute(
                    args.command,
                    vars(args),
                    manifest=args.manifest,
                    timeout=args.timeout,
                ),
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
