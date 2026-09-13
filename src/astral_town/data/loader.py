"""JSON/YAML loading without executing constructors."""

import json
from importlib.resources import files
from pathlib import Path

import yaml


def loads(text: str, suffix: str) -> dict:
    if suffix == ".json":
        data = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        data = yaml.safe_load(text)
    else:
        raise ValueError(f"Unsupported configuration format: {suffix}")
    if not isinstance(data, dict):
        raise ValueError("Configuration must be an object/mapping")
    return data


def load_file(path: str | Path) -> dict:
    path = Path(path)
    return loads(path.read_text(encoding="utf-8"), path.suffix)


def load_builtin(name: str = "rules.json") -> dict:
    if Path(name).name != name:
        raise ValueError("Expected a packaged data filename")
    return loads(files("astral_town.data").joinpath(name).read_text(encoding="utf-8"), Path(name).suffix)
