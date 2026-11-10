"""Лаконичный валидатор данных Parquet по JSON-схеме."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Union
import pandas as pd


@dataclass
class ValidationResult:
    """Результат валидации данных."""

    is_valid: bool
    total_records: int
    errors: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.is_valid

    def summary(self) -> str:
        if self.is_valid:
            return f"Валидация успешна! Всего записей: {self.total_records}, ошибок: 0."
        header = f"Ошибок найдено: {len(self.errors)} (всего записей: {self.total_records}):"
        error_lines = "\n".join(f"  - {err}" for err in self.errors)
        return f"{header}\n{error_lines}"


class ParquetValidator:
    """Валидатор Parquet-файлов и DataFrame по схеме JSON."""

    @staticmethod
    def load_schema(schema: Union[str, Path, dict]) -> dict:
        """Загружает JSON-схему из файла или словаря."""
        if isinstance(schema, (str, Path)):
            with open(schema, "r", encoding="utf-8") as f:
                return json.load(f)
        return schema

    @classmethod
    def validate(
        cls,
        data: Union[str, Path, pd.DataFrame],
        schema: Union[str, Path, dict],
    ) -> ValidationResult:
        """
        Проверяет данные Parquet (путь к файлу или pd.DataFrame) по схеме JSON.
        Возвращает ValidationResult.
        """
        schema_dict = cls.load_schema(schema)
        fields = schema_dict.get("fields", [])

        if isinstance(data, (str, Path)):
            path = Path(data)
            if not path.exists():
                raise FileNotFoundError(f"Файл не найден: {path}")
            df = pd.read_parquet(path)
        elif isinstance(data, pd.DataFrame):
            df = data
        else:
            raise TypeError("Данные должны быть путем к Parquet-файлу или pd.DataFrame")

        errors: List[str] = []
        total_records = len(df)

        for fld in fields:
            name = fld.get("name")
            if not name:
                continue

            if name not in df.columns:
                if fld.get("required"):
                    errors.append(f"Обязательное поле '{name}' отсутствует в данных")
                continue

            series = df[name]

            # 1. Проверка на обязательность (required)
            is_empty = series.isna()
            if series.dtype == object or pd.api.types.is_string_dtype(series):
                is_empty = is_empty | (series.astype(str).str.strip() == "")

            if fld.get("required"):
                for row_idx in series.index[is_empty]:
                    errors.append(f"Строка {row_idx + 1}: поле '{name}' обязательно для заполнения")

            # Для остальных правил проверяем только непустые значения
            valid = series[~is_empty]
            if valid.empty:
                continue

            # 2. Проверка уникальности (unique)
            if fld.get("unique"):
                dups = valid[valid.duplicated(keep="first")]
                for row_idx, val in dups.items():
                    errors.append(f"Строка {row_idx + 1}: поле '{name}' содержит дубликат значения '{val}'")

            # 3. Проверка типов данных
            expected_type = fld.get("type")
            if expected_type == "integer":
                for row_idx, val in valid.items():
                    if isinstance(val, bool):
                        errors.append(f"Строка {row_idx + 1}: поле '{name}' должно быть integer, получено '{val}'")
                    else:
                        try:
                            f_val = float(val)
                            if not f_val.is_integer():
                                errors.append(f"Строка {row_idx + 1}: поле '{name}' должно быть integer, получено '{val}'")
                        except (ValueError, TypeError):
                            errors.append(f"Строка {row_idx + 1}: поле '{name}' должно быть integer, получено '{val}'")

            elif expected_type == "float":
                for row_idx, val in valid.items():
                    if isinstance(val, bool):
                        errors.append(f"Строка {row_idx + 1}: поле '{name}' должно быть float, получено '{val}'")
                    else:
                        try:
                            float(str(val).replace(",", "."))
                        except (ValueError, TypeError):
                            errors.append(f"Строка {row_idx + 1}: поле '{name}' должно быть float, получено '{val}'")

            elif expected_type == "boolean":
                allowed = {True, False, 1, 0, "true", "false", "1", "0", "yes", "no", "да", "нет"}
                for row_idx, val in valid.items():
                    norm = str(val).strip().lower() if isinstance(val, str) else val
                    if norm not in allowed:
                        errors.append(f"Строка {row_idx + 1}: поле '{name}' должно быть boolean, получено '{val}'")

            elif expected_type == "date":
                fmt = fld.get("format", "YYYY-MM-DD")
                py_fmt = fmt.replace("YYYY", "%Y").replace("MM", "%m").replace("DD", "%d")
                for row_idx, val in valid.items():
                    try:
                        pd.to_datetime(str(val), format=py_fmt)
                    except Exception:
                        errors.append(f"Строка {row_idx + 1}: поле '{name}' не соответствует формату даты '{fmt}' ('{val}')")

            # 4. Проверка диапазонов значений (min / max)
            min_val = fld.get("min")
            max_val = fld.get("max")
            if min_val is not None or max_val is not None:
                for row_idx, val in valid.items():
                    try:
                        num = float(val)
                        if min_val is not None and num < min_val:
                            errors.append(f"Строка {row_idx + 1}: поле '{name}' ({val}) меньше минимума ({min_val})")
                        if max_val is not None and num > max_val:
                            errors.append(f"Строка {row_idx + 1}: поле '{name}' ({val}) больше максимума ({max_val})")
                    except (ValueError, TypeError):
                        pass

            # 5. Проверка длины строк (min_length / max_length)
            min_len = fld.get("min_length")
            max_len = fld.get("max_length")
            if min_len is not None or max_len is not None:
                for row_idx, val in valid.items():
                    str_len = len(str(val))
                    if min_len is not None and str_len < min_len:
                        errors.append(f"Строка {row_idx + 1}: длина '{name}' ({str_len}) меньше минимальной ({min_len})")
                    if max_len is not None and str_len > max_len:
                        errors.append(f"Строка {row_idx + 1}: длина '{name}' ({str_len}) больше максимальной ({max_len})")

            # 6. Проверка по регулярному выражению (pattern)
            pattern = fld.get("pattern")
            if pattern:
                regex = re.compile(pattern)
                for row_idx, val in valid.items():
                    if not regex.search(str(val)):
                        errors.append(f"Строка {row_idx + 1}: поле '{name}' ('{val}') не соответствует формату")

        return ValidationResult(
            is_valid=len(errors) == 0,
            total_records=total_records,
            errors=errors,
        )
