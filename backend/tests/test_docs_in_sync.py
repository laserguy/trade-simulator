"""Doc drift checks: the docs must describe the code as it is (CLAUDE.md, ARCHITECTURE.md).

A failure here means code changed without its docs. Fix the doc named in the message, not this test.
"""

import re
from pathlib import Path

from trade_simulator.adapters import agent_map, config
from trade_simulator.application.run_mode import RUN_MODE_SETTING
from trade_simulator.application.settings import MODEL_SETTING, PROVIDERS

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
PACKAGE = BACKEND / "src" / "trade_simulator"
FRONTEND_SRC = ROOT / "frontend" / "src"

ARCHITECTURE = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
PROBLEM_STATEMENT = (ROOT / "PROBLEM_STATEMENT.md").read_text(encoding="utf-8")
WHY = (ROOT / "WHY.md").read_text(encoding="utf-8")

# Paths the doc names that only exist once the app has run, or are optional user files.
RUNTIME_PATHS = {"data/trade_simulator.sqlite3", "logs/app.log", "../frontend/dist", "mcp_servers.json"}
# Where a relative path in the doc may be rooted.
PATH_BASES = (ROOT, BACKEND, PACKAGE, FRONTEND_SRC)
SOURCE_DIRS = (PACKAGE, BACKEND / "tests", BACKEND / "prompts", FRONTEND_SRC)


def _missing(names, text: str) -> list[str]:
    return sorted(name for name in names if name not in text)


def test_every_decision_in_the_problem_statement_has_a_why_entry_and_back():
    stated = set(re.findall(r"^\| (D\d+) \|", PROBLEM_STATEMENT, re.MULTILINE))
    explained = set(re.findall(r"^### (D\d+):", WHY, re.MULTILINE))
    assert stated - explained == set(), "Decisions missing from WHY.md"
    assert explained - stated == set(), "Decisions in WHY.md missing from PROBLEM_STATEMENT.md"


def test_every_source_file_is_mapped_in_architecture():
    files = [p for p in PACKAGE.rglob("*.py") if p.name != "__init__.py"]
    files += [p for p in FRONTEND_SRC.rglob("*.ts*") if ".test." not in p.name]
    missing = _missing({p.name for p in files}, ARCHITECTURE)
    assert not missing, f"Add these files to ARCHITECTURE.md: {missing}"


def test_every_database_table_is_listed_in_architecture():
    schema = (PACKAGE / "adapters" / "sqlite_repository.py").read_text(encoding="utf-8")
    tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", schema))
    assert tables, "No tables found; has the schema moved?"
    missing = _missing({f"`{t}`" for t in tables}, ARCHITECTURE)
    assert not missing, f"Add these tables to ARCHITECTURE.md: {missing}"


def test_every_api_endpoint_is_listed_in_architecture():
    api = (PACKAGE / "adapters" / "web" / "api.py").read_text(encoding="utf-8")
    endpoints = {
        f"{method.upper()} {_generic(path)}"
        for method, path in re.findall(r'@app\.(get|post|put|delete|patch)\("([^"]+)"', api)
    }
    assert endpoints, "No endpoints found; has the API moved?"
    missing = _missing(endpoints, _generic(ARCHITECTURE))
    assert not missing, f"Add these endpoints to ARCHITECTURE.md: {missing}"


def test_every_config_variable_is_in_env_example_and_architecture():
    env_example = (BACKEND / ".env.example").read_text(encoding="utf-8")
    tables = (config.MARKET_DATA_PROVIDER_KEYS, config.SEARCH_PROVIDER_KEYS, config.PRICE_HISTORY_PROVIDER_KEYS)
    key_names = {name for table in tables for name in table.values() if name}
    settings = set(re.findall(r'_provider\(env, "(\w+)"', (PACKAGE / "adapters" / "config.py").read_text("utf-8")))
    variables = key_names | settings
    assert settings, "No provider settings found; has config.py changed shape?"
    missing = _missing(variables, env_example)
    assert not missing, f"Add these variables to backend/.env.example: {missing}"
    missing = _missing(variables, ARCHITECTURE)
    assert not missing, f"Add these variables to ARCHITECTURE.md: {missing}"


def test_every_stored_setting_is_listed_in_architecture():
    keys = {f"`{p}_api_key`" for p in PROVIDERS} | {f"`{MODEL_SETTING}`", f"`{RUN_MODE_SETTING}`"}
    missing = _missing(keys, ARCHITECTURE)
    assert not missing, f"Add these settings keys to ARCHITECTURE.md: {missing}"


def test_every_path_named_in_architecture_exists():
    missing = [token for token in _path_tokens(ARCHITECTURE) if not _exists(token)]
    assert not missing, f"ARCHITECTURE.md names paths that no longer exist: {missing}"


def test_agent_map_numbers_match_the_code():
    html = agent_map.AGENT_MAP_PATH.read_bytes().decode("utf-8")
    assert agent_map.fill_numbers(html, agent_map.current_numbers()) == html, (
        "docs/agent-map.html shows out-of-date numbers. Run: cd backend && uv run trade-sim agent-map, "
        "then republish it (see CLAUDE.md)"
    )


def test_agent_map_covers_every_agent_tool_trigger_and_order_rule():
    html = agent_map.AGENT_MAP_PATH.read_text(encoding="utf-8")
    problems = agent_map.coverage_problems(agent_map.coverage_in(html), agent_map.current_structure())
    assert not problems, (
        "docs/agent-map.html no longer matches the agents (D45). Update its drawings and text, then the "
        f"'agent-map covers' list at the top, then republish it (see CLAUDE.md): {problems}"
    )


def _generic(text: str) -> str:
    """`/api/runs/{run_id}` and `/api/runs/{id}` both become `/api/runs/{}`."""
    return re.sub(r"\{[^}]*\}", "{}", text)


def _path_tokens(text: str) -> list[str]:
    tokens = []
    for token in re.findall(r"`([^`\s]+)`", text):
        if any(c in token for c in "*<>|{") or token.startswith("/"):
            continue  # patterns, placeholders, and API paths are not files
        if "/" in token or re.search(r"\.(py|md|json|tsx?|toml)$", token):
            tokens.append(token)
    return tokens


def _exists(token: str) -> bool:
    if token in RUNTIME_PATHS:
        return True
    if any((base / token).exists() for base in PATH_BASES):
        return True
    if "/" not in token:  # a bare file name continuing the previous path in the same table row
        return any(next(d.rglob(token), None) for d in SOURCE_DIRS)
    return False
