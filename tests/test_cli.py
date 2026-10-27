import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from capability_tool_orchestrator.__main__ import execute, main


def test_cli_runs_manifest_with_scopes(tmp_path, capsys):
    manifest = tmp_path / "tools.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "name": "catalog",
                    "kind": "static",
                    "capabilities": ["lookup"],
                    "scopes": ["read"],
                    "value": {"available": True},
                }
            ]
        )
    )
    assert (
        main(["--manifest", str(manifest), "run", "lookup", "{}", "--scope", "read"])
        == 0
    )
    assert json.loads(capsys.readouterr().out)["merged"] == {"available": True}


def test_product_posts_payload_to_http_tool(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            body = json.dumps({"received": payload["item"]}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        manifest = tmp_path / "tools.json"
        manifest.write_text(
            json.dumps(
                [
                    {
                        "name": "remote",
                        "kind": "http",
                        "url": f"http://127.0.0.1:{server.server_port}/",
                        "capabilities": ["lookup"],
                        "scopes": ["read"],
                    }
                ]
            )
        )
        result = execute(
            "run",
            {"capability": "lookup", "payload": '{"item":"42"}', "scopes": "read"},
            manifest=str(manifest),
            timeout=2,
        )
        assert result["merged"] == {"received": "42"}
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
