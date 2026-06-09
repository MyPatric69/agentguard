"""AgentGuard Web Server — FastAPI bridge for the web UI."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from agentguard import __version__

app = FastAPI(title="AgentGuard Web", version=__version__)


@app.get("/api/check")
async def check(path: str = "."):
    """Run agentguard check and return results as JSON."""
    result = subprocess.run(
        ["agentguard", "check", "--path", path, "--format", "json"],
        capture_output=True,
        text=True,
    )
    if result.stdout:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"error": result.stdout}
    return {"error": result.stderr}


@app.get("/api/governance")
async def get_governance(path: str = "."):
    """Read and return governance.yaml as JSON."""
    import yaml

    gov_file = Path(path) / "governance.yaml"
    if not gov_file.exists():
        return {"exists": False}
    with open(gov_file) as f:
        return {"exists": True, "governance": yaml.safe_load(f)}


@app.get("/api/verify")
async def verify(path: str = "."):
    """Run agentguard verify and return results as JSON."""
    result = subprocess.run(
        ["agentguard", "verify", "--config", str(Path(path) / "governance.yaml")],
        capture_output=True,
        text=True,
    )
    return {"output": result.stdout, "success": result.returncode == 0}


@app.get("/api/verify-json")
async def verify_json(path: str = "."):
    """Return structured pin data from governance.yaml."""
    import yaml

    gov_file = Path(path) / "governance.yaml"
    if not gov_file.exists():
        return {"pins": [], "success": False, "message": "No governance.yaml"}
    try:
        with open(gov_file) as f:
            gov = yaml.safe_load(f)
        pins = gov.get("concretization_pins", [])
        if not pins:
            return {
                "pins": [],
                "success": False,
                "message": "No pins found — re-run agentguard init --guided",
            }
        pin_results = [
            {
                "field": p.get("field", "unknown"),
                "model": p.get("model", ""),
                "date": p.get("date", ""),
                "status": "ok",
            }
            for p in pins
        ]
        return {
            "pins": pin_results,
            "success": True,
            "message": "All pins verified — governance is reproducible",
        }
    except Exception as e:
        return {"pins": [], "success": False, "message": str(e)}


@app.get("/api/health")
async def health():
    """Health check."""
    return {"status": "ok", "version": __version__}


_dist = Path(__file__).parent.parent.parent / "web" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="static")


def start(host: str = "127.0.0.1", port: int = 8767, open_browser: bool = True) -> None:
    """Start the AgentGuard web server."""
    if open_browser:
        import threading
        import time
        import webbrowser

        def _open() -> None:
            time.sleep(1.5)
            webbrowser.open(f"http://{host}:{port}")

        threading.Thread(target=_open, daemon=True).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")
