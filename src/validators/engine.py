from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
import pandas as pd
from .schema import load_schema
from .rules import (
    check_required,
    check_unique,
    check_type,
    check_range,
    check_length,
    check_pattern,
)


@dataclass
class ValidationResult:
    total_records: int
    valid_count: int
    invalid_indices: Set[int] = field(default_factory=set)
    errors: List[str] = field(default_factory=list)
    errors_table: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.invalid_indices) == 0

    def __bool__(self) -> bool:
        return self.is_valid

    def summary(
        self,
        output_file: Optional[Union[str, Path]] = None,
        errors_file: Optional[Union[str, Path]] = None,
        report_file: Optional[Union[str, Path]] = None,
    ) -> str:
        lines = [
            f"Всего записей: {self.total_records}",
            f"Успешно обработано: {self.valid_count}",
            f"Ошибок: {len(self.invalid_indices)}",
        ]
        for err in self.errors:
            lines.append(f"  - {err}")

        if output_file:
            lines.append(f"Результат сохранён: {output_file}")
        if errors_file:
            lines.append(f"Ошибки сохранены: {errors_file}")
        if report_file:
            lines.append(f"Отчёт сохранён: {report_file}")

        return "\n".join(lines)

    def generate_html_report(self, target_path: Union[str, Path]) -> Path:
        from ..reporters.html_reporter import HTMLReporter
        return HTMLReporter.generate(self, target_path)


class ValidationEngine:

    @staticmethod
    def load_schema(schema: Union[str, Path, dict]) -> dict:
        return load_schema(schema)

    @classmethod
    def validate(
        cls,
        data: Union[str, Path, pd.DataFrame],
        schema: Union[str, Path, dict],
    ) -> ValidationResult:
        schema_dict = cls.load_schema(schema)
        fields = schema_dict.get("fields", [])

        if isinstance(data, (str, Path)):
            path = Path(data).resolve()
            if not path.exists():
                raise FileNotFoundError(f"Файл не найден: {path}")
            if path.suffix.lower() == ".parquet":
                df = pd.read_parquet(path)
            else:
                from ..readers import ReaderFactory
                df = ReaderFactory.read(path)
        elif isinstance(data, pd.DataFrame):
            df = data
        else:
            raise TypeError("Данные должны быть путем к файлу или pd.DataFrame.")

        errors: List[str] = []
        errors_table: List[Dict[str, Any]] = []
        invalid_indices: Set[int] = set()
        total_records = len(df)

        for fld in fields:
            name = fld.get("name")
            target_name = fld.get("target_name")
            if not name:
                continue

            col_name = name if name in df.columns else (target_name if target_name and target_name in df.columns else None)

            if col_name is None:
                if fld.get("required"):
                    for idx in df.index:
                        invalid_indices.add(idx)
                        row_num = idx + 1
                        msg = f'поле "{name}" отсутствует в данных'
                        errors.append(f"Строка {row_num}: {msg}")
                        errors_table.append({
                            "row": row_num,
                            "field": name,
                            "value": None,
                            "rule": "required",
                            "message": msg,
                        })
                continue

            series = df[col_name]

            if fld.get("required"):
                req_idx, req_err, req_tbl = check_required(series, name)
                invalid_indices.update(req_idx)
                errors.extend(req_err)
                errors_table.extend(req_tbl)

            is_empty = series.isna()
            if series.dtype == object or pd.api.types.is_string_dtype(series):
                is_empty = is_empty | (series.astype(str).str.strip() == "")
            valid_series = series[~is_empty]
            if valid_series.empty:
                continue

            if fld.get("unique"):
                u_idx, u_err, u_tbl = check_unique(valid_series, name)
                invalid_indices.update(u_idx)
                errors.extend(u_err)
                errors_table.extend(u_tbl)

            expected_type = fld.get("type")
            if expected_type:
                date_fmt = fld.get("format", "YYYY-MM-DD")
                t_idx, t_err, t_tbl = check_type(valid_series, name, expected_type, date_fmt)
                invalid_indices.update(t_idx)
                errors.extend(t_err)
                errors_table.extend(t_tbl)

            min_val = fld.get("min")
            max_val = fld.get("max")
            if min_val is not None or max_val is not None:
                r_idx, r_err, r_tbl = check_range(
                    valid_series,
                    name,
                    min_val,
                    max_val,
                    is_date=(expected_type == "date"),
                    date_format=fld.get("format", "YYYY-MM-DD"),
                )
                invalid_indices.update(r_idx)
                errors.extend(r_err)
                errors_table.extend(r_tbl)

            min_len = fld.get("min_length")
            max_len = fld.get("max_length")
            if min_len is not None or max_len is not None:
                l_idx, l_err, l_tbl = check_length(valid_series, name, min_len, max_len)
                invalid_indices.update(l_idx)
                errors.extend(l_err)
                errors_table.extend(l_tbl)

            pattern = fld.get("pattern")
            if pattern:
                p_idx, p_err, p_tbl = check_pattern(valid_series, name, pattern)
                invalid_indices.update(p_idx)
                errors.extend(p_err)
                errors_table.extend(p_tbl)

        valid_count = total_records - len(invalid_indices)
        return ValidationResult(
            total_records=total_records,
            valid_count=valid_count,
            invalid_indices=invalid_indices,
            errors=errors,
            errors_table=errors_table,
        )
