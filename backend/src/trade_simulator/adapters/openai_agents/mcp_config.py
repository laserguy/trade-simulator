"""Optional MCP servers for the agents, read from mcp_servers.json.

No file means no MCP servers: the built-in tools are used. To add one later, list it in the file and
name which agents get it ("research", "trading"). Secrets are referenced as ${ENV_VAR}, never written
into the file. See mcp_servers.example.json.

Note: calls to MCP tools are not counted against the Tavily search limits (D13, D14).
"""

import json
import os
import re
from collections.abc import Mapping
from pathlib import Path

from agents.mcp import MCPServer, MCPServerStdio, MCPServerStreamableHttp

from trade_simulator.core.errors import ConfigError

AGENT_NAMES = frozenset({"research", "trading"})
_ENV_REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class McpServers:
    def __init__(self, servers: list[tuple[MCPServer, frozenset[str]]]) -> None:
        self._servers = servers

    def for_agent(self, agent_name: str) -> list[MCPServer]:
        return [server for server, agents in self._servers if agent_name in agents]

    def all(self) -> list[MCPServer]:
        return [server for server, _ in self._servers]


def load_mcp_servers(path: Path, env: Mapping[str, str] | None = None) -> McpServers:
    if not path.exists():
        return McpServers([])
    env = os.environ if env is None else env
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Cannot read MCP config {path.name}: {exc}") from exc
    return McpServers([_build(entry, env) for entry in config.get("servers", [])])


def _build(entry: dict, env: Mapping[str, str]) -> tuple[MCPServer, frozenset[str]]:
    name = entry.get("name", "unnamed")
    agents = frozenset(entry.get("agents", []))
    if not agents or not agents <= AGENT_NAMES:
        raise ConfigError(f"MCP server '{name}': 'agents' must list some of {sorted(AGENT_NAMES)}")

    transport = entry.get("transport")
    if transport == "stdio":
        params = {"command": entry["command"], "args": entry.get("args", [])}
        if "env" in entry:
            params["env"] = {**os.environ, **_expand(entry["env"], env, name)}
        server = MCPServerStdio(params=params, name=name, cache_tools_list=True)
    elif transport == "http":
        params = {"url": entry["url"], "headers": _expand(entry.get("headers", {}), env, name)}
        server = MCPServerStreamableHttp(params=params, name=name, cache_tools_list=True)
    else:
        raise ConfigError(f"MCP server '{name}': transport must be 'stdio' or 'http', got {transport!r}")
    return server, agents


def _expand(values: dict[str, str], env: Mapping[str, str], server_name: str) -> dict[str, str]:
    def substitute(match: re.Match) -> str:
        variable = match.group(1)
        if variable not in env:
            raise ConfigError(f"MCP server '{server_name}' needs environment variable {variable}")
        return env[variable]

    return {key: _ENV_REFERENCE.sub(substitute, value) for key, value in values.items()}
