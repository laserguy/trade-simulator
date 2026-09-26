"""Use case: API keys and model choice (D9).

Models are offered only for providers that have a key. Keys come only from Settings, never from the
environment, so there is one place to manage them. Keys never leave this service except to call the
provider; views show them masked.
"""

from dataclasses import dataclass

from trade_simulator.application.ports import SettingsStore
from trade_simulator.core.errors import ConfigError, TradeSimulatorError
from trade_simulator.core.model_pricing import ModelCatalogue, ModelOption

PROVIDERS = ("openai", "anthropic")
MODEL_SETTING = "model_id"


class SettingsError(TradeSimulatorError):
    """An invalid settings change was requested."""


@dataclass(frozen=True)
class ProviderStatus:
    provider: str
    has_key: bool
    masked_key: str | None


@dataclass(frozen=True)
class SettingsView:
    providers: tuple[ProviderStatus, ...]
    models: tuple[ModelOption, ...]
    selected_model_id: str | None
    catalogue_as_of: str


@dataclass(frozen=True)
class ModelSelection:
    option: ModelOption
    api_key: str
    tracing_api_key: str | None  # traces need an OpenAI key, whichever model runs (D25)


class SettingsService:
    def __init__(
        self,
        *,
        store: SettingsStore,
        catalogue: ModelCatalogue,
        default_model_id: str,
    ) -> None:
        self._store = store
        self._catalogue = catalogue
        self._default_model_id = default_model_id

    def view(self) -> SettingsView:
        keys = self._keys()
        selected = self._selected_option(keys)
        return SettingsView(
            providers=tuple(self._status(provider, keys) for provider in PROVIDERS),
            models=self._catalogue.for_providers(keys),
            selected_model_id=selected.model_id if selected else None,
            catalogue_as_of=self._catalogue.as_of.isoformat(),
        )

    def set_api_key(self, provider: str, api_key: str | None) -> None:
        if provider not in PROVIDERS:
            raise SettingsError(f"Unknown provider '{provider}'; expected one of {', '.join(PROVIDERS)}")
        value = api_key.strip() if api_key else None
        self._store.save_setting(_key_setting(provider), value or None)

    def select_model(self, model_id: str) -> None:
        option = self._catalogue.find(model_id)
        if option is None:
            raise SettingsError(f"Unknown model '{model_id}'")
        if option.provider not in self._keys():
            raise SettingsError(f"Add an {option.provider} API key before choosing {option.label}")
        self._store.save_setting(MODEL_SETTING, model_id)

    def current_selection(self) -> ModelSelection:
        keys = self._keys()
        option = self._selected_option(keys)
        if option is None:
            raise ConfigError("No LLM API key: add an OpenAI or Anthropic API key in Settings")
        return ModelSelection(option=option, api_key=keys[option.provider], tracing_api_key=keys.get("openai"))

    def secrets(self) -> list[str]:
        """Every saved key, for scrubbing logs (D19)."""
        return list(self._keys().values())

    def _keys(self) -> dict[str, str]:
        saved = self._store.load_settings()
        return {p: saved[_key_setting(p)] for p in PROVIDERS if saved.get(_key_setting(p))}

    def _selected_option(self, keys: dict[str, str]) -> ModelOption | None:
        available = self._catalogue.for_providers(keys)
        if not available:
            return None
        for model_id in (self._store.load_settings().get(MODEL_SETTING), self._default_model_id):
            option = next((o for o in available if o.model_id == model_id), None)
            if option:
                return option
        return min(available, key=lambda o: o.input_usd_per_million + o.output_usd_per_million)

    def _status(self, provider: str, keys: dict[str, str]) -> ProviderStatus:
        key = keys.get(provider)
        if key is None:
            return ProviderStatus(provider, False, None)
        return ProviderStatus(provider, True, f"…{key[-4:]}")


def _key_setting(provider: str) -> str:
    return f"{provider}_api_key"
