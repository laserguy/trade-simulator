import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from trade_simulator.core.errors import ConfigError
from trade_simulator.core.model_pricing import ModelCatalogue, ModelOption


def load_model_catalogue(path: Path) -> ModelCatalogue:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ModelCatalogue(
            as_of=date.fromisoformat(data["as_of"]),
            options=tuple(
                ModelOption(
                    provider=m["provider"],
                    model_id=m["model_id"],
                    label=m["label"],
                    input_usd_per_million=Decimal(m["input"]),
                    output_usd_per_million=Decimal(m["output"]),
                    note=m.get("note", ""),
                )
                for m in data["models"]
            ),
        )
    except (OSError, ValueError, KeyError) as exc:
        raise ConfigError(f"Invalid model catalogue {path.name}: {exc}") from exc
