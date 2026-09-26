from pathlib import Path

import pytest

from trade_simulator.adapters.config import BACKEND_DIR, DEFAULT_MODEL, load_config
from trade_simulator.core.errors import ConfigError

KEYS = {"FINNHUB_API_KEY": "f-1", "TAVILY_API_KEY": "t-1"}


def test_loads_data_keys_and_paths(tmp_path):
    config = load_config(env=KEYS, base_dir=tmp_path)

    assert config.database_path == tmp_path / "data" / "trade_simulator.sqlite3"
    assert config.model_catalogue_path == BACKEND_DIR / "model_catalogue.json"
    assert config.secrets() == ["f-1", "t-1"]


def test_llm_keys_are_not_required_because_they_live_in_settings(tmp_path):
    load_config(env=KEYS, base_dir=tmp_path)  # no LLM keys needed here: they are entered in Settings


def test_missing_data_keys_are_named_without_values(tmp_path):
    with pytest.raises(ConfigError) as error:
        load_config(env={"FINNHUB_API_KEY": "f-1"}, base_dir=tmp_path)

    assert "TAVILY_API_KEY" in str(error.value)
    assert "f-1" not in str(error.value)


def test_search_provider_defaults_to_tavily_and_needs_its_key(tmp_path):
    config = load_config(env=KEYS, base_dir=tmp_path)

    assert config.search_provider == "tavily"
    assert config.search_api_key == "t-1"


def test_search_key_is_only_required_for_the_provider_in_use(tmp_path):
    with pytest.raises(ConfigError, match="SEARCH_PROVIDER"):
        load_config(env={"FINNHUB_API_KEY": "f-1", "SEARCH_PROVIDER": "carrier-pigeon"}, base_dir=tmp_path)


def test_market_data_and_price_history_providers_are_chosen_by_config(tmp_path):
    config = load_config(env={**KEYS, "TIINGO_API_KEY": "p-1"}, base_dir=tmp_path)

    assert config.market_data_provider == "finnhub"
    assert config.price_history_provider == "tiingo"
    assert config.price_history_api_key == "p-1"
    assert "p-1" in config.secrets()


def test_missing_price_history_key_does_not_stop_the_app(tmp_path):
    config = load_config(env=KEYS, base_dir=tmp_path)

    assert config.price_history_api_key is None


def test_unknown_market_data_provider_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="MARKET_DATA_PROVIDER"):
        load_config(env={**KEYS, "MARKET_DATA_PROVIDER": "abacus"}, base_dir=tmp_path)


def test_default_model_is_the_low_cost_one():
    assert DEFAULT_MODEL == "gpt-6-luna"


def test_backend_dir_points_at_backend_folder():
    assert (BACKEND_DIR / "prompts").is_dir()
    assert isinstance(BACKEND_DIR, Path)
