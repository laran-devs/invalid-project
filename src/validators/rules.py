"""Модуль правил валидации данных."""

import re
import math
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any, Dict, Optional, Union

from .errors import ValidationErrorItem


def is_empty_value(value: Any) -> bool:
    """Проверяет, является ли значение пустым (None, пустая строка, NaN)."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, float) and math.isnan(value):
        return True
    # Проверка на NaN, если value != value (IEEE 754)
    if value != value:
        return True
    return False


def convert_date_format_to_strftime(fmt: str) -> str:
    """Преобразует человекочитаемый формат даты (YYYY-MM-DD) в формат strftime (%Y-%m-%d)."""
    mapping = {
        "YYYY": "%Y",
        "YY": "%y",
        "MM": "%m",
        "DD": "%d",
        "HH": "%H",
        "mm": "%M",
        "ss": "%S",
    }
    result = fmt
    # Сначала длинные токены, затем короткие
    for token in ["YYYY", "YY", "MM", "DD", "HH", "mm", "ss"]:
        result = result.replace(token, mapping[token])
    return result


def parse_date(value: Any, date_format: Optional[str] = None) -> Optional[date]:
    """Пытается распарсить дату из строки или объекта datetime/date."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    if not isinstance(value, str):
        return None

    str_val = value.strip()
    if not str_val:
        return None

    # Если задан конкретный формат даты, проверяем строго по нему
    if date_format:
        py_fmt = convert_date_format_to_strftime(date_format)
        formats_to_try = [py_fmt]
        if date_format != py_fmt:
            formats_to_try.append(date_format)
        for fmt in formats_to_try:
            try:
                return datetime.strptime(str_val, fmt).date()
            except ValueError:
                pass
        return None

    # Если формат не задан, пробуем стандартные форматы по умолчанию
    default_formats = [
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%Y-%m-%d %H:%M:%S",
        "%d.%m.%Y %H:%M:%S",
    ]
    for fmt in default_formats:
        try:
            return datetime.strptime(str_val, fmt).date()
        except ValueError:
            continue

    # Попытка через fromisoformat
    try:
        return datetime.fromisoformat(str_val).date()
    except (ValueError, TypeError):
        pass

    return None


class Rule(ABC):
    """Базовый абстрактный класс правила валидации."""

    rule_name: str = "base"

    @abstractmethod
    def validate(
        self,
        value: Any,
        row: Dict[str, Any],
        field_name: str,
        row_index: int,
    ) -> Optional[ValidationErrorItem]:
        """Проверяет значение поля и возвращает ValidationErrorItem при ошибке или None."""
        pass


class RequiredRule(Rule):
    """Правило обязательности поля."""

    rule_name = "required"

    def __init__(self, required: bool = True):
        self.required = bool(required)

    def validate(
        self,
        value: Any,
        row: Dict[str, Any],
        field_name: str,
        row_index: int,
    ) -> Optional[ValidationErrorItem]:
        if not self.required:
            return None

        # Проверка отсутствия поля в записи или пустого значения
        if field_name not in row or is_empty_value(value):
            return ValidationErrorItem(
                row_index=row_index,
                field=field_name,
                value=value,
                rule=self.rule_name,
                message=f'поле "{field_name}" обязательно для заполнения',
            )
        return None


class TypeRule(Rule):
    """Правило проверки типа данных (integer, float, string, date, boolean)."""

    rule_name = "type"
    SUPPORTED_TYPES = {"integer", "int", "float", "number", "string", "str", "date", "boolean", "bool"}

    def __init__(self, expected_type: str, date_format: Optional[str] = None):
        self.expected_type = expected_type.lower().strip()
        self.date_format = date_format
        if self.expected_type not in self.SUPPORTED_TYPES:
            raise ValueError(
                f"Неподдерживаемый тип данных: '{expected_type}'. "
                f"Допустимые типы: {', '.join(sorted(self.SUPPORTED_TYPES))}"
            )

    def validate(
        self,
        value: Any,
        row: Dict[str, Any],
        field_name: str,
        row_index: int,
    ) -> Optional[ValidationErrorItem]:
        if is_empty_value(value):
            return None

        t = self.expected_type
        if t in ("integer", "int"):
            if isinstance(value, bool):
                return self._error(field_name, value, row_index, "целым числом")
            if isinstance(value, int):
                return None
            if isinstance(value, float):
                if value.is_integer():
                    return None
                return self._error(field_name, value, row_index, "целым числом")
            if isinstance(value, str):
                s = value.strip()
                if re.match(r"^-?\d+$", s):
                    return None
            return self._error(field_name, value, row_index, "целым числом")

        elif t in ("float", "number"):
            if isinstance(value, bool):
                return self._error(field_name, value, row_index, "числом")
            if isinstance(value, (int, float)):
                return None
            if isinstance(value, str):
                s = value.strip().replace(",", ".")
                try:
                    float(s)
                    return None
                except ValueError:
                    pass
            return self._error(field_name, value, row_index, "вещественным числом")

        elif t in ("string", "str"):
            return None

        elif t in ("boolean", "bool"):
            if isinstance(value, bool):
                return None
            if isinstance(value, (int, float)) and value in (0, 1):
                return None
            if isinstance(value, str):
                if value.strip().lower() in ("true", "false", "1", "0", "yes", "no", "да", "нет", "t", "f"):
                    return None
            return self._error(field_name, value, row_index, "логическим значением (true/false)")

        elif t == "date":
            parsed = parse_date(value, self.date_format)
            if parsed is None:
                fmt_desc = self.date_format or "YYYY-MM-DD"
                return ValidationErrorItem(
                    row_index=row_index,
                    field=field_name,
                    value=value,
                    rule=self.rule_name,
                    message=f'поле "{field_name}" не соответствует формату даты "{fmt_desc}"',
                )
            return None

        return None

    def _error(self, field_name: str, value: Any, row_index: int, expected_desc: str) -> ValidationErrorItem:
        return ValidationErrorItem(
            row_index=row_index,
            field=field_name,
            value=value,
            rule=self.rule_name,
            message=f'поле "{field_name}" должно быть {expected_desc} (получено "{value}")',
        )


class RangeRule(Rule):
    """Правило проверки допустимого диапазона (min/max) для чисел и дат."""

    rule_name = "range"

    def __init__(
        self,
        min_value: Optional[Union[int, float, str]] = None,
        max_value: Optional[Union[int, float, str]] = None,
        field_type: Optional[str] = None,
        date_format: Optional[str] = None,
    ):
        self.min_value = min_value
        self.max_value = max_value
        self.field_type = (field_type or "").lower().strip()
        self.date_format = date_format

    def validate(
        self,
        value: Any,
        row: Dict[str, Any],
        field_name: str,
        row_index: int,
    ) -> Optional[ValidationErrorItem]:
        if is_empty_value(value):
            return None

        # Проверка для дат
        if self.field_type == "date" or isinstance(value, (date, datetime)):
            val_date = parse_date(value, self.date_format)
            if val_date is None:
                return None  # Ошибка типа будет зафиксирована TypeRule

            if self.min_value is not None:
                min_date = parse_date(self.min_value, self.date_format)
                if min_date and val_date < min_date:
                    return ValidationErrorItem(
                        row_index=row_index,
                        field=field_name,
                        value=value,
                        rule=self.rule_name,
                        message=f'поле "{field_name}" вне диапазона ({value})',
                    )

            if self.max_value is not None:
                max_date = parse_date(self.max_value, self.date_format)
                if max_date and val_date > max_date:
                    return ValidationErrorItem(
                        row_index=row_index,
                        field=field_name,
                        value=value,
                        rule=self.rule_name,
                        message=f'поле "{field_name}" вне диапазона ({value})',
                    )
            return None

        # Проверка для чисел
        try:
            if isinstance(value, bool):
                return None
            num_val = float(str(value).strip().replace(",", "."))
        except (ValueError, TypeError):
            return None  # Ошибка типа будет зафиксирована TypeRule

        if self.min_value is not None:
            try:
                min_num = float(self.min_value)
                if num_val < min_num:
                    return ValidationErrorItem(
                        row_index=row_index,
                        field=field_name,
                        value=value,
                        rule=self.rule_name,
                        message=f'поле "{field_name}" вне диапазона ({value})',
                    )
            except (ValueError, TypeError):
                pass

        if self.max_value is not None:
            try:
                max_num = float(self.max_value)
                if num_val > max_num:
                    return ValidationErrorItem(
                        row_index=row_index,
                        field=field_name,
                        value=value,
                        rule=self.rule_name,
                        message=f'поле "{field_name}" вне диапазона ({value})',
                    )
            except (ValueError, TypeError):
                pass

        return None


class PatternRule(Rule):
    """Правило проверки значения регулярным выражением."""

    rule_name = "pattern"

    def __init__(self, pattern: str):
        self.pattern_str = pattern
        try:
            self.regex = re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Некорректное регулярное выражение '{pattern}': {e}")

    def validate(
        self,
        value: Any,
        row: Dict[str, Any],
        field_name: str,
        row_index: int,
    ) -> Optional[ValidationErrorItem]:
        if is_empty_value(value):
            return None

        val_str = str(value)
        if not self.regex.search(val_str):
            return ValidationErrorItem(
                row_index=row_index,
                field=field_name,
                value=value,
                rule=self.rule_name,
                message=f'поле "{field_name}" не соответствует формату',
            )
        return None


class LengthRule(Rule):
    """Правило проверки длины строки (min_length / max_length)."""

    rule_name = "length"

    def __init__(
        self,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
    ):
        self.min_length = min_length
        self.max_length = max_length

    def validate(
        self,
        value: Any,
        row: Dict[str, Any],
        field_name: str,
        row_index: int,
    ) -> Optional[ValidationErrorItem]:
        if is_empty_value(value):
            return None

        val_str = str(value)
        length = len(val_str)

        if self.min_length is not None and length < self.min_length:
            return ValidationErrorItem(
                row_index=row_index,
                field=field_name,
                value=value,
                rule="min_length",
                message=f'длина поля "{field_name}" меньше минимальной ({length} < {self.min_length})',
            )

        if self.max_length is not None and length > self.max_length:
            return ValidationErrorItem(
                row_index=row_index,
                field=field_name,
                value=value,
                rule="max_length",
                message=f'длина поля "{field_name}" превышает максимальную ({length} > {self.max_length})',
            )

        return None


class UniqueRule(Rule):
    """Правило проверки уникальности значений в столбце."""

    rule_name = "unique"

    def __init__(self, unique: bool = True):
        self.unique = bool(unique)
        self.seen_values: Dict[Any, int] = {}

    def reset(self) -> None:
        """Сбрасывает историю встреченных значений."""
        self.seen_values.clear()

    def validate(
        self,
        value: Any,
        row: Dict[str, Any],
        field_name: str,
        row_index: int,
    ) -> Optional[ValidationErrorItem]:
        if not self.unique or is_empty_value(value):
            return None

        # Нормализация для сравнения: числа как float/int, строки в стрипнутом виде
        norm_val = value
        if isinstance(value, str):
            norm_val = value.strip()

        if norm_val in self.seen_values:
            first_row = self.seen_values[norm_val]
            return ValidationErrorItem(
                row_index=row_index,
                field=field_name,
                value=value,
                rule=self.rule_name,
                message=f'значение поля "{field_name}" ({value}) не уникально (дубликат со строкой {first_row})',
            )

        self.seen_values[norm_val] = row_index
        return None
