"""Модуль основного движка валидации данных."""

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from .errors import SchemaError, ValidationErrorItem, ValidationResult
from .rules import is_empty_value
from .schema import FieldSchema, ValidationSchema


class ValidationEngine:
    """Движок валидации данных по набору правил и спецификации схемы."""

    def __init__(self, schema: Union[ValidationSchema, Dict[str, Any], str, Path]):
        if isinstance(schema, ValidationSchema):
            self.schema = schema
        elif isinstance(schema, dict):
            self.schema = ValidationSchema.from_dict(schema)
        elif isinstance(schema, (str, Path)):
            self.schema = ValidationSchema.from_file(schema)
        else:
            raise SchemaError(f"Неподдерживаемый тип схемы: {type(schema).__name__}")

    def reset(self) -> None:
        """Сбрасывает состояние всех правил (например, память уникальности)."""
        self.schema.reset_rules()

    def validate_row(self, row: Dict[str, Any], row_index: int = 1) -> List[ValidationErrorItem]:
        """Выполняет валидацию отдельной строки (записи) данных."""
        row_errors: List[ValidationErrorItem] = []

        for field_schema in self.schema.fields_list:
            field_name = field_schema.name
            value = row.get(field_name)

            for rule in field_schema.rules:
                error = rule.validate(value, row, field_name, row_index)
                if error:
                    row_errors.append(error)
                    # Если сработала ошибка обязательности (required), остальные проверки
                    # типа/диапазона для этого же поля бессмысленны
                    if rule.rule_name == "required":
                        break

        return row_errors

    def validate_records(
        self,
        records: Iterable[Dict[str, Any]],
        start_row_index: int = 1,
    ) -> ValidationResult:
        """Выполняет валидацию коллекции записей (словарей).

        Args:
            records: Итерируемый набор словарей {имя_поля: значение}.
            start_row_index: Начальный номер строки для отображения в отчетах об ошибках
                             (по умолчанию 1, или 2 если строка 1 - заголовки CSV/Excel).
        """
        self.reset()
        result = ValidationResult()

        for idx, row in enumerate(records):
            current_row_index = start_row_index + idx
            result.total_records += 1

            row_errors = self.validate_row(row, current_row_index)

            if row_errors:
                for err in row_errors:
                    result.add_error(err)
                result.invalid_records.append(row)
            else:
                result.valid_records.append(row)

        return result

    def validate_dataframe(
        self,
        df: Any,
        start_row_index: int = 2,
    ) -> ValidationResult:
        """Выполняет валидацию данных из pandas.DataFrame.

        Номер строки по умолчанию начинается со 2 (с учетом строки заголовка таблицы).
        """
        # Преобразуем DataFrame в список словарей, заменяя NaN/pd.NA на None
        records: List[Dict[str, Any]] = []
        try:
            import numpy as np  # type: ignore
            has_numpy = True
        except ImportError:
            has_numpy = False

        for row_dict in df.to_dict(orient="records"):
            clean_row: Dict[str, Any] = {}
            for k, v in row_dict.items():
                if is_empty_value(v):
                    clean_row[k] = None
                elif has_numpy and isinstance(v, (np.floating, np.integer)):
                    clean_row[k] = v.item()
                else:
                    clean_row[k] = v
            records.append(clean_row)

        return self.validate_records(records, start_row_index=start_row_index)

    def validate_file(
        self,
        file_path_or_file: Union[str, Path, Any],
        start_row_index: int = 2,
    ) -> ValidationResult:
        """Универсальная валидация файла данных (CSV, JSON, Excel, XML).

        Может использовать File/FileConverter из src, либо встроенные парсеры при отсутствии pandas.
        """
        # Проверяем, передан ли объект File из src.models
        if hasattr(file_path_or_file, "path"):
            path = Path(file_path_or_file.path).resolve()
        else:
            path = Path(file_path_or_file).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Файл данных не найден: {path}")

        # Попытка прочитать через src.FileConverter если доступен pandas
        try:
            from src.models import File
            from src.converter import FileConverter
            file_obj = File(path)
            df = FileConverter.read_to_dataframe(file_obj)
            return self.validate_dataframe(df, start_row_index=start_row_index)
        except Exception:
            # Fallback на встроенное чтение при отсутствии pandas или ошибках импорта
            pass

        suffix = path.suffix.lower()
        if suffix == ".json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return self.validate_records(data, start_row_index=1)
            elif isinstance(data, dict):
                return self.validate_records([data], start_row_index=1)
            else:
                raise ValueError("JSON должен содержать массив объектов или одиночный объект")

        elif suffix == ".csv":
            records = []
            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    records.append(dict(row))
            return self.validate_records(records, start_row_index=start_row_index)

        raise ValueError(
            f"Не удалось прочитать файл '{path}'. Убедитесь, что установлены зависимости или поддерживается формат."
        )
