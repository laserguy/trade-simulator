from datetime import date
from decimal import Decimal

import pytest

from trade_simulator.adapters.sqlite_repository import SqliteRepository
from trade_simulator.application.settings import SettingsError, SettingsService
from trade_simulator.core.errors import ConfigError
from trade_simulator.core.model_pricing import ModelCatalogue, ModelOption

LUNA = ModelOption("openai", "gpt-6-luna", "GPT-6 Luna", Decimal("0.10"), Decimal("0.50"))
SOL = ModelOption("openai", "gpt-6-sol", "GPT-6 Sol", Decimal("2"), Decimal("10"))
HAIKU = ModelOption("anthropic", "claude-haiku-4-5", "Claude Haiku 4.5", Decimal("1"), Decimal("5"))
CATALOGUE = ModelCatalogue(date(2026, 9, 26), (LUNA, SOL, HAIKU))


@pytest.fixture
def store(tmp_path):
    repo = SqliteRepository(tmp_path / "sim.sqlite3")
    repo.initialize()
    return repo


def make(store):
    return SettingsService(store=store, catalogue=CATALOGUE, default_model_id="gpt-6-luna")


def test_no_keys_means_no_models_and_no_selection(store):
    service = make(store)

    view = service.view()
    assert view.models == ()
    assert view.selected_model_id is None
    with pytest.raises(ConfigError, match="API key"):
        service.current_selection()


def test_environment_keys_are_ignored_keys_come_only_from_settings(store, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-9999")

    assert make(store).view().models == ()


def test_only_models_of_providers_with_a_key_are_offered(store):
    service = make(store)
    service.set_api_key("anthropic", "sk-ant-secret-1234")

    view = service.view()
    assert [m.model_id for m in view.models] == ["claude-haiku-4-5"]
    assert view.selected_model_id == "claude-haiku-4-5"  # cheapest available when default isn't


def test_default_model_is_used_when_its_provider_has_a_key(store):
    service = make(store)
    service.set_api_key("openai", "sk-saved-9999")

    selection = service.current_selection()
    assert selection.option == LUNA
    assert selection.api_key == "sk-saved-9999"
    assert selection.tracing_api_key == "sk-saved-9999"


def test_keys_are_masked(store):
    service = make(store)
    service.set_api_key("anthropic", "sk-ant-secret-1234")

    providers = {p.provider: p for p in service.view().providers}
    assert providers["anthropic"].masked_key == "…1234"
    assert "secret" not in providers["anthropic"].masked_key
    assert providers["openai"].has_key is False


def test_selecting_a_model_persists(store):
    service = make(store)
    service.set_api_key("openai", "k")
    service.select_model("gpt-6-sol")

    assert make(store).current_selection().option == SOL


def test_cannot_select_model_without_its_providers_key(store):
    service = make(store)
    service.set_api_key("openai", "k")

    with pytest.raises(SettingsError):
        service.select_model("claude-haiku-4-5")


def test_removing_a_key_falls_back_to_an_available_model(store):
    service = make(store)
    service.set_api_key("openai", "k")
    service.set_api_key("anthropic", "a-key")
    service.select_model("claude-haiku-4-5")

    service.set_api_key("anthropic", None)

    assert service.current_selection().option == LUNA


def test_anthropic_only_has_no_tracing_key(store):
    service = make(store)
    service.set_api_key("anthropic", "a-key")

    assert service.current_selection().tracing_api_key is None


def test_unknown_provider_is_rejected(store):
    with pytest.raises(SettingsError):
        make(store).set_api_key("gemini", "k")


def test_secrets_lists_every_saved_key_for_log_scrubbing(store):
    service = make(store)
    service.set_api_key("openai", "sk-1")
    service.set_api_key("anthropic", "a-key")

    assert set(service.secrets()) == {"sk-1", "a-key"}
