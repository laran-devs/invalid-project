"""Модуль схемы и конфигурации правил валидации."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .errors import SchemaError
from .rules import (
    LengthRule,
    PatternRule,
    RangeRule,
    RequiredRule,
    Rule,
    TypeRule,
    UniqueRule,
)


class FieldSchema:
    """Конфигурация правил для одного поля."""

    def __init__(
        self,
        name: str,
        type: Optional[str] = None,
        required: bool = False,
        unique: bool = False,
        min: Optional[Union[int, float, str]] = None,
        max: Optional[Union[int, float, str]] = None,
        pattern: Optional[str] = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        format: Optional[str] = None,
        **extra_kwargs: Any,
    ):
        if not name or not isinstance(name, str):
            raise SchemaError("Каждое поле в схеме должно иметь непустое строковое имя 'name'")

        self.name = name
        self.type = type
        self.required = bool(required)
        self.unique = bool(unique)
        self.min = min
        self.max = max
        self.pattern = pattern
        self.min_length = min_length
        self.max_length = max_length
        self.format = format
        self.extra = extra_kwargs

        self.rules: List[Rule] = self._build_rules()

    def _build_rules(self) -> List[Rule]:
        rules: List[Rule] = []

        # 1. Проверка обязательности
        if self.required:
            rules.append(RequiredRule(required=True))

        # 2. Проверка типа данных
        if self.type:
            try:
                rules.append(TypeRule(expected_type=self.type, date_format=self.format))
            except ValueError as e:
                raise SchemaError(f"Ошибка в конфигурации поля '{self.name}': {e}") from e

        # 3. Проверка диапазона (min / max)
        if self.min is not None or self.max is not None:
            rules.append(
                RangeRule(
                    min_value=self.min,
                    max_value=self.max,
                    field_type=self.type,
                    date_format=self.format,
                )
            )

        # 4. Проверка паттерна (regex)
        if self.pattern:
            try:
                rules.append(PatternRule(pattern=self.pattern))
            except ValueError as e:
                raise SchemaError(f"Ошибка в конфигурации поля '{self.name}': {e}") from e

        # 5. Проверка длины строки
        if self.min_length is not None or self.max_length is not None:
            rules.append(LengthRule(min_length=self.min_length, max_length=self.max_length))

        # 6. Проверка уникальности
        if self.unique:
            rules.append(UniqueRule(unique=True))

        return rules

    def reset_rules(self) -> None:
        """Сбрасывает контекст правил с состоянием (например, UniqueRule)."""
        for r in self.rules:
            if isinstance(r, UniqueRule):
                r.reset()


def _parse_simple_yaml(text: str) -> Dict[str, Any]:
    """Встроенный устойчивый парсер YAML-конфигураций схемы DataBridge.

    Позволяет загружать YAML-конфигурации без обязательной внешней зависимости PyYAML.
    """
    lines = text.splitlines()
    fields: List[Dict[str, Any]] = []
    current_field: Optional[Dict[str, Any]] = None

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        # Пропуск пустых строк и комментариев
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("fields:"):
            continue

        # Начало нового элемента списка: '  - name: id' или '  - '
        if stripped.startswith("-"):
            if current_field is not None:
                fields.append(current_field)
            current_field = {}
            rest = stripped.lstrip("-").strip()
            if rest:
                _parse_yaml_key_val_into_dict(rest, current_field)
            continue

        # Свойства текущего элемента: '    type: integer'
        if current_field is not None:
            _parse_yaml_key_val_into_dict(stripped, current_field)

    if current_field is not None:
        fields.append(current_field)

    return {"fields": fields}


def _parse_yaml_key_val_into_dict(line: str, target: Dict[str, Any]) -> None:
    """Парсит строку 'key: value' и записывает в словарь с приведением типов."""
    if ":" not in line:
        return
    k, v = line.split(":", 1)
    key = k.strip()
    val_str = v.strip()

    # Снятие кавычек и обработка escape-последовательностей
    if val_str.startswith('"') and val_str.endswith('"'):
        inner = val_str[1:-1]
        try:
            target[key] = inner.encode("utf-8").decode("unicode_escape")
        except Exception:
            target[key] = inner.replace(r"\\", "\\")
        return
    elif val_str.startswith("'") and val_str.endswith("'"):
        target[key] = val_str[1:-1].replace("''", "'")
        return

    # Приведение типов булевых, чисел, None
    lower_val = val_str.lower()
    if lower_val in ("true", "yes", "on"):
        target[key] = True
    elif lower_val in ("false", "no", "off"):
        target[key] = False
    elif lower_val in ("null", "none", "~", ""):
        target[key] = None
    else:
        try:
            target[key] = int(val_str)
        except ValueError:
            try:
                target[key] = float(val_str)
            except ValueError:
                target[key] = val_str


class ValidationSchema:
    """Конфигурация схемы валидации данных."""

    def __init__(self, fields: List[FieldSchema]):
        self.fields_list: List[FieldSchema] = fields
        self.fields: Dict[str, FieldSchema] = {f.name: f for f in fields}

    def reset_rules(self) -> None:
        """Сбрасывает состояние правил (например, уникальности) перед новой валидацией."""
        for f in self.fields_list:
            f.reset_rules()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationSchema":
        """Создает схему из словаря формата {'fields': [...]}."""
        if not isinstance(data, dict):
            raise SchemaError(f"Конфигурация схемы должна быть объектом/словарём, получено: {type(data).__name__}")

        raw_fields = data.get("fields")
        if raw_fields is None or not isinstance(raw_fields, list):
            raise SchemaError("В конфигурации схемы обязателен список 'fields'")

        field_schemas: List[FieldSchema] = []
        for i, item in enumerate(raw_fields):
            if not isinstance(item, dict):
                raise SchemaError(f"Элемент fields[{i}] должен быть словарём")
            field_schemas.append(FieldSchema(**item))

        return cls(fields=field_schemas)

    @classmethod
    def from_json(cls, source: Union[str, Path]) -> "ValidationSchema":
        """Загружает схему из файла JSON или JSON-строки."""
        path = Path(source)
        if path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(str(source))
        return cls.from_dict(data)

    @classmethod
    def from_yaml(cls, source: Union[str, Path]) -> "ValidationSchema":
        """Загружает схему из файла YAML или YAML-строки."""
        path = Path(source)
        if path.is_file():
            text = path.read_text(encoding="utf-8")
        else:
            text = str(source)

        try:
            import yaml  # type: ignore
            data = yaml.safe_load(text)
        except (ImportError, Exception):
            # Резервный надежный парсер, если pyyaml отсутствует
            data = _parse_simple_yaml(text)

        return cls.from_dict(data)

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "ValidationSchema":
        """Автоматически определяет формат (.json, .yaml, .yml) и загружает схему."""
        file_path = Path(path).resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"Файл схемы не найден: {file_path}")

        suffix = file_path.suffix.lower()
        if suffix == ".json":
            return cls.from_json(file_path)
        elif suffix in (".yaml", ".yml"):
            return cls.from_yaml(file_path)
        else:
            # Пробуем как JSON, затем как YAML
            try:
                return cls.from_json(file_path)
            except Exception:
                return cls.from_yaml(file_path)
