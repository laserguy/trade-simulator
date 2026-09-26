from decimal import Decimal

from agents import OpenAIResponsesModel
from agents.extensions.models.litellm_model import LitellmModel

from trade_simulator.adapters.openai_agents.models import make_model
from trade_simulator.application.settings import ModelSelection
from trade_simulator.core.model_pricing import ModelOption


def selection(provider, model_id):
    return ModelSelection(ModelOption(provider, model_id, model_id, Decimal("1"), Decimal("1")), "key", None)


def test_openai_models_use_the_responses_api_with_the_saved_key():
    model = make_model(selection("openai", "gpt-6-luna"))

    assert isinstance(model, OpenAIResponsesModel)
    assert model.model == "gpt-6-luna"


def test_anthropic_models_go_through_litellm():
    model = make_model(selection("anthropic", "claude-sonnet-5"))

    assert isinstance(model, LitellmModel)
    assert model.model == "anthropic/claude-sonnet-5"
