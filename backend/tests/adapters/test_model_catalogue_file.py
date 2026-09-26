from trade_simulator.adapters.config import BACKEND_DIR
from trade_simulator.adapters.model_catalogue_file import load_model_catalogue


def test_shipped_catalogue_has_both_providers_and_the_default_model():
    catalogue = load_model_catalogue(BACKEND_DIR / "model_catalogue.json")

    providers = {option.provider for option in catalogue.options}
    assert providers == {"openai", "anthropic"}
    assert catalogue.find("gpt-6-luna") is not None
    assert all(o.input_usd_per_million > 0 and o.output_usd_per_million > 0 for o in catalogue.options)
