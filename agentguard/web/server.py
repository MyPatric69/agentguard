"""AgentGuard Web Server — FastAPI bridge for the web UI."""
from __future__ import annotations

import asyncio
import fcntl
import json
import os
import pty
import select
import struct
import subprocess
import termios
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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


@app.get("/api/project-info")
async def project_info(path: str = "."):
    """Return absolute path and project name."""
    abs_path = str(Path(path).resolve())
    name = Path(abs_path).name
    return {"name": name, "path": abs_path}


@app.websocket("/ws/terminal")
async def terminal_ws(websocket: WebSocket, path: str = "."):
    """WebSocket endpoint that spawns a PTY bash shell in the project directory."""
    await websocket.accept()

    pid, fd = pty.fork()

    if pid == 0:
        abs_path = str(Path(path).resolve())
        os.chdir(abs_path)
        os.execvp("bash", ["bash", "--login"])
    else:
        try:
            async def pty_to_ws():
                while True:
                    await asyncio.sleep(0.01)
                    try:
                        r, _, _ = select.select([fd], [], [], 0)
                        if r:
                            data = os.read(fd, 1024)
                            await websocket.send_bytes(data)
                    except OSError:
                        break

            async def ws_to_pty():
                while True:
                    try:
                        msg = await websocket.receive()
                        if "bytes" in msg:
                            data = msg["bytes"]
                            if data[0:1] == b'\x01' and len(data) == 5:
                                cols = struct.unpack('H', data[1:3])[0]
                                rows = struct.unpack('H', data[3:5])[0]
                                fcntl.ioctl(fd, termios.TIOCSWINSZ,
                                            struct.pack('HHHH', rows, cols, 0, 0))
                            else:
                                os.write(fd, data)
                        elif "text" in msg:
                            os.write(fd, msg["text"].encode())
                    except (WebSocketDisconnect, Exception):
                        break

            await asyncio.gather(pty_to_ws(), ws_to_pty())
        finally:
            try:
                os.kill(pid, 9)
                os.waitpid(pid, 0)
            except Exception:
                pass
            try:
                os.close(fd)
            except Exception:
                pass


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
