import json
from pathlib import Path
from typing import Any, Dict, Union

try:
    import yaml
except ImportError:
    yaml = None


def load_schema(schema: Union[str, Path, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(schema, dict):
        return schema

    path = Path(schema).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Файл схемы не найден: {path}")

    content = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        if yaml is None:
            raise ImportError("Пакет PyYAML не установлен для чтения YAML-схем.")
        loaded = yaml.safe_load(content)
        if not isinstance(loaded, dict):
            raise ValueError(f"Некорректная структура YAML схемы: {path}")
        return loaded

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        if yaml is not None:
            try:
                loaded = yaml.safe_load(content)
                if isinstance(loaded, dict):
                    return loaded
            except Exception:
                pass
        raise ValueError(f"Не удалось распарсить файл схемы: {path}")
