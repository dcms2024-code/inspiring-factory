import json
from typing import Any, Dict


def parse_json_strict(text: str) -> Dict[str, Any]:
    """
    Parse a JSON object from a model response.

    The pipeline requires the model to output ONLY JSON. If it doesn't, we fail
    fast so the prompt can be adjusted.
    """
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object at top-level.")
    return data
