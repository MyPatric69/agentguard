"""AgentGuard — Governance layer for autonomous AI agents."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("agentguard")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

__author__ = "AgentGuard Contributors"
