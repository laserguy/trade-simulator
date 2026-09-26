"""Turns the Settings model choice into an SDK model object (D9).

OpenAI models use the Responses API directly; Anthropic models go through the SDK's LiteLLM extension,
so agents, tools and MCP servers work the same whichever provider is chosen.
"""

from agents import Model, OpenAIResponsesModel
from agents.extensions.models.litellm_model import LitellmModel
from openai import AsyncOpenAI

from trade_simulator.application.settings import ModelSelection
from trade_simulator.core.errors import ConfigError


def make_model(selection: ModelSelection) -> Model:
    option = selection.option
    if option.provider == "openai":
        return OpenAIResponsesModel(model=option.model_id, openai_client=AsyncOpenAI(api_key=selection.api_key))
    if option.provider == "anthropic":
        return LitellmModel(model=f"anthropic/{option.model_id}", api_key=selection.api_key)
    raise ConfigError(f"Unsupported model provider '{option.provider}'")
