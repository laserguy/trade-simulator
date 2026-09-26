"""App configuration from environment variables (backend/.env).

Data-provider keys live here (D10). LLM keys and the model choice live only in Settings (D9).
Each external tool's provider is chosen by config, and only the chosen provider's key is needed (D38):
MARKET_DATA_PROVIDER (default finnhub), SEARCH_PROVIDER (default tavily), PRICE_HISTORY_PROVIDER
(default tiingo; its key is optional, and without it charts are unavailable).
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from trade_simulator.core.errors import ConfigError

BACKEND_DIR = Path(__file__).resolve().parents[3]
DEFAULT_MODEL = "gpt-6-luna"  # cheapest current OpenAI model; see D9 in WHY.md
DEFAULT_SEARCH_PROVIDER = "tavily"
# Each external tool (D38): provider name -> the environment variable holding its key (None = no key needed).
MARKET_DATA_PROVIDER_KEYS: dict[str, str | None] = {"finnhub": "FINNHUB_API_KEY"}
SEARCH_PROVIDER_KEYS: dict[str, str | None] = {"tavily": "TAVILY_API_KEY"}
PRICE_HISTORY_PROVIDER_KEYS: dict[str, str | None] = {"tiingo": "TIINGO_API_KEY"}


@dataclass(frozen=True)
class AppConfig:
    market_data_provider: str
    market_data_api_key: str | None
    search_provider: str
    search_api_key: str | None
    price_history_provider: str
    price_history_api_key: str | None  # optional: without it, charts are simply unavailable
    database_path: Path
    log_path: Path
    mcp_config_path: Path
    prompts_dir: Path
    model_catalogue_path: Path
    frontend_dist: Path

    def secrets(self) -> list[str]:
        """Data-provider keys that must never appear in logs (D19). LLM keys come from Settings."""
        keys = (self.market_data_api_key, self.search_api_key, self.price_history_api_key)
        return [key for key in keys if key]


def load_config(env: Mapping[str, str] | None = None, base_dir: Path = BACKEND_DIR) -> AppConfig:
    env = os.environ if env is None else env
    market, market_key_name = _provider(env, "MARKET_DATA_PROVIDER", "finnhub", MARKET_DATA_PROVIDER_KEYS)
    search, search_key_name = _provider(env, "SEARCH_PROVIDER", DEFAULT_SEARCH_PROVIDER, SEARCH_PROVIDER_KEYS)
    history, history_key_name = _provider(env, "PRICE_HISTORY_PROVIDER", "tiingo", PRICE_HISTORY_PROVIDER_KEYS)

    required = [name for name in (market_key_name, search_key_name) if name]
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise ConfigError(f"Missing settings in backend/.env: {', '.join(missing)}")
    return AppConfig(
        market_data_provider=market,
        market_data_api_key=env.get(market_key_name) if market_key_name else None,
        search_provider=search,
        search_api_key=env.get(search_key_name) if search_key_name else None,
        price_history_provider=history,
        price_history_api_key=(env.get(history_key_name) or None) if history_key_name else None,
        database_path=base_dir / "data" / "trade_simulator.sqlite3",
        log_path=base_dir / "logs" / "app.log",
        mcp_config_path=base_dir / "mcp_servers.json",
        prompts_dir=BACKEND_DIR / "prompts",
        model_catalogue_path=BACKEND_DIR / "model_catalogue.json",
        frontend_dist=BACKEND_DIR.parent / "frontend" / "dist",
    )


def _provider(env: Mapping[str, str], setting: str, default: str, keys: dict[str, str | None]) -> tuple[str, str | None]:
    name = env.get(setting) or default
    if name not in keys:
        raise ConfigError(f"Unknown {setting} '{name}'; expected one of {', '.join(keys)}")
    return name, keys[name]
