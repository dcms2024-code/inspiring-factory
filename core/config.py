import json
import os
from typing import Any, Dict


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def default_channel_config_path() -> str:
    return os.path.join(repo_root(), "config", "channel_inspirational_science_es.json")


def default_figures_path() -> str:
    return os.path.join(repo_root(), "config", "figures_inspirational.json")
