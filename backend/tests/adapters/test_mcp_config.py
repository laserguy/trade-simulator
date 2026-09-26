import json

import pytest
from agents.mcp import MCPServerStdio, MCPServerStreamableHttp

from trade_simulator.adapters.openai_agents.mcp_config import load_mcp_servers
from trade_simulator.core.errors import ConfigError


def write(tmp_path, data):
    path = tmp_path / "mcp_servers.json"
    path.write_text(json.dumps(data))
    return path


def test_missing_config_file_means_no_mcp_servers(tmp_path):
    assert load_mcp_servers(tmp_path / "absent.json", env={}).for_agent("research") == []


def test_stdio_and_http_servers_are_built_and_assigned_to_agents(tmp_path):
    path = write(
        tmp_path,
        {
            "servers": [
                {
                    "name": "market",
                    "transport": "stdio",
                    "command": "uvx",
                    "args": ["some-mcp"],
                    "env": {"API_KEY": "${MARKET_KEY}"},
                    "agents": ["research"],
                },
                {
                    "name": "news",
                    "transport": "http",
                    "url": "https://mcp.example.com/mcp",
                    "headers": {"Authorization": "Bearer ${NEWS_KEY}"},
                    "agents": ["research", "trading"],
                },
            ]
        },
    )

    servers = load_mcp_servers(path, env={"MARKET_KEY": "m1", "NEWS_KEY": "n1"})

    research = servers.for_agent("research")
    assert [s.name for s in research] == ["market", "news"]
    assert isinstance(research[0], MCPServerStdio)
    assert isinstance(research[1], MCPServerStreamableHttp)
    assert [s.name for s in servers.for_agent("trading")] == ["news"]


def test_missing_secret_is_reported_by_name_only(tmp_path):
    path = write(
        tmp_path,
        {"servers": [{"name": "x", "transport": "stdio", "command": "c", "env": {"K": "${NOPE}"}, "agents": ["research"]}]},
    )

    with pytest.raises(ConfigError, match="NOPE"):
        load_mcp_servers(path, env={})


def test_unknown_transport_is_rejected(tmp_path):
    path = write(tmp_path, {"servers": [{"name": "x", "transport": "carrier-pigeon", "agents": ["research"]}]})

    with pytest.raises(ConfigError):
        load_mcp_servers(path, env={})


def test_unknown_agent_name_is_rejected(tmp_path):
    path = write(tmp_path, {"servers": [{"name": "x", "transport": "stdio", "command": "c", "agents": ["janitor"]}]})

    with pytest.raises(ConfigError):
        load_mcp_servers(path, env={})
