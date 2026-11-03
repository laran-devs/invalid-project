"""Модуль представления ошибок валидации и результатов проверки."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ValidationErrorItem:
    """Представляет одну ошибку валидации поля в строке данных."""

    row_index: int
    field: str
    value: Any
    rule: str
    message: str

    def __str__(self) -> str:
        return f"Строка {self.row_index}: {self.message}"

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует ошибку в словарь (удобно для экспорта в CSV / JSON / отчёты)."""
        return {
            "row": self.row_index,
            "field": self.field,
            "value": "" if self.value is None else str(self.value),
            "rule": self.rule,
            "message": self.message,
        }


class SchemaError(ValueError):
    """Исключение, возникающее при синтаксической или логической ошибке в схеме валидации."""
    pass


@dataclass
class ValidationResult:
    """Результат выполнения валидации набора данных."""

    total_records: int = 0
    valid_records: List[Dict[str, Any]] = field(default_factory=list)
    invalid_records: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[ValidationErrorItem] = field(default_factory=list)
    errors_by_row: Dict[int, List[ValidationErrorItem]] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """True, если в данных нет ни одной ошибки."""
        return len(self.errors) == 0

    @property
    def valid_count(self) -> int:
        return len(self.valid_records)

    @property
    def errors_count(self) -> int:
        return len(self.errors)

    def add_error(self, error: ValidationErrorItem) -> None:
        """Добавляет ошибку в общий список и индексирует по строке."""
        self.errors.append(error)
        if error.row_index not in self.errors_by_row:
            self.errors_by_row[error.row_index] = []
        self.errors_by_row[error.row_index].append(error)

    def summary(self, max_display_errors: Optional[int] = None) -> str:
        """Формирует текстовую сводку согласно стандарту проекта DataBridge.

        Пример вывода:
            Всего записей: 150
            Успешно обработано: 142
            Ошибок: 8
              - Строка 5: поле "email" не соответствует формату
              - Строка 12: поле "age" вне диапазона (200)
        """
        lines = [
            f"Всего записей: {self.total_records}",
            f"Успешно обработано: {self.valid_count}",
            f"Ошибок: {self.errors_count}",
        ]

        errors_to_show = self.errors
        if max_display_errors is not None and len(errors_to_show) > max_display_errors:
            errors_to_show = errors_to_show[:max_display_errors]
            truncated = True
        else:
            truncated = False

        for err in errors_to_show:
            lines.append(f"  - {err}")

        if truncated:
            remaining = len(self.errors) - len(errors_to_show)
            lines.append(f"  ... и еще {remaining} ошибок")

        return "\n".join(lines)

    def print_summary(self, max_display_errors: Optional[int] = None) -> None:
        """Выводит сводку результатов валидации в консоль."""
        print(self.summary(max_display_errors=max_display_errors))

    def to_errors_dict_list(self) -> List[Dict[str, Any]]:
        """Возвращает список словарей со всеми ошибками для сохранения в errors.csv."""
        return [err.to_dict() for err in self.errors]
