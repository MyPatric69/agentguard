"""Desktop notifications for AgentGuard events."""

from __future__ import annotations

import subprocess
import sys


def notify_cost(total_usd: float, model: str, level: str, project: str) -> None:
    """Send desktop notification for cost threshold breach."""
    if level == "warn":
        title = "AgentGuard Warning"
    elif level == "critical":
        title = "AgentGuard Critical"
    else:
        title = "AgentGuard Alert"
    message = f"Session cost: ${total_usd:.2f} ({model}) — {level} threshold exceeded"
    _send_notification(title, message)
    _play_sound(level)


def _send_notification(title: str, message: str) -> None:
    """Cross-platform desktop notification. Never raises."""
    try:
        if sys.platform == "darwin":
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script], timeout=5, check=False)
        elif sys.platform.startswith("linux"):
            subprocess.run(["notify-send", title, message], timeout=5, check=False)
        elif sys.platform == "win32":
            try:
                from win10toast import ToastNotifier  # type: ignore[import-not-found]

                ToastNotifier().show_toast(title, message, duration=5)
            except ImportError:
                pass
    except Exception:
        pass


def _play_sound(level: str) -> None:
    """Play platform-native alert sound. Never raises."""
    try:
        if sys.platform == "darwin":
            if level == "warn":
                sound = "Tink"
            elif level == "critical":
                sound = "Basso"
            else:
                sound = "Funk"
            subprocess.run(
                ["afplay", f"/System/Library/Sounds/{sound}.aiff"],
                timeout=3,
                check=False,
            )
    except Exception:
        pass
