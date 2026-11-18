from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Union
import pandas as pd


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
        target = Path(target_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        status_color = "#2e7d32" if self.is_valid else "#c62828"
        status_text = "УСПЕШНО" if self.is_valid else "ОБНАРУЖЕНЫ ОШИБКИ"

        rows_html = []
        for item in self.errors_table:
            val_display = str(item.get("value", ""))
            if len(val_display) > 60:
                val_display = val_display[:57] + "..."
            rows_html.append(
                f"<tr>"
                f"<td style='text-align:center;'>{item['row']}</td>"
                f"<td><b>{item['field']}</b></td>"
                f"<td><code>{val_display}</code></td>"
                f"<td><span style='background:#f5f5f5;padding:2px 6px;border-radius:4px;'>{item['rule']}</span></td>"
                f"<td>{item['message']}</td>"
                f"</tr>"
            )

        table_content = "\n".join(rows_html)
        if rows_html:
            error_section = f"""
            <h3>Список ошибок валидации ({len(self.errors_table)})</h3>
            <table style="width:100%; border-collapse: collapse; margin-top: 10px;">
                <thead>
                    <tr style="background:#f0f0f0; text-align:left;">
                        <th style="padding:8px; border:1px solid #ddd; text-align:center;">Строка</th>
                        <th style="padding:8px; border:1px solid #ddd;">Поле</th>
                        <th style="padding:8px; border:1px solid #ddd;">Значение</th>
                        <th style="padding:8px; border:1px solid #ddd;">Правило</th>
                        <th style="padding:8px; border:1px solid #ddd;">Сообщение</th>
                    </tr>
                </thead>
                <tbody>
                    {table_content}
                </tbody>
            </table>
            """
        else:
            error_section = "<p style='color:#2e7d32;font-size:16px;'>Все записи прошли валидацию без ошибок.</p>"

        html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>DataBridge - Отчёт валидации</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; margin: 30px; color: #333; }}
        .header {{ border-bottom: 2px solid #ddd; padding-bottom: 15px; margin-bottom: 20px; }}
        .badge {{ display: inline-block; padding: 6px 12px; border-radius: 4px; color: #fff; font-weight: bold; background: {status_color}; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 25px; }}
        .card {{ background: #fafafa; border: 1px solid #e0e0e0; padding: 15px; border-radius: 6px; }}
        .card-value {{ font-size: 24px; font-weight: bold; margin-top: 5px; }}
        table td, table th {{ padding: 8px 12px; border: 1px solid #e0e0e0; }}
        tr:nth-child(even) {{ background: #fdfdfd; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>Отчёт валидации данных (DataBridge)</h2>
        <span class="badge">{status_text}</span>
    </div>
    <div class="stats-grid">
        <div class="card">Всего записей:<div class="card-value">{self.total_records}</div></div>
        <div class="card">Успешно обработано:<div class="card-value" style="color:#2e7d32;">{self.valid_count}</div></div>
        <div class="card">Записей с ошибками:<div class="card-value" style="color:#c62828;">{len(self.invalid_indices)}</div></div>
    </div>
    {error_section}
</body>
</html>
"""
        target.write_text(html, encoding="utf-8")
        return target


class ParquetValidator:

    @staticmethod
    def load_schema(schema: Union[str, Path, dict]) -> dict:
        if isinstance(schema, (str, Path)):
            path = Path(schema)
            if not path.exists():
                raise FileNotFoundError(f"Файл схемы не найден: {path}")
            return json.loads(path.read_text(encoding="utf-8"))

        if isinstance(schema, dict):
            return schema

        raise TypeError("Схема должна быть путем к JSON-файлу или словарем.")

    @classmethod
    def validate(
        cls,
        data: Union[str, Path, pd.DataFrame],
        schema: Union[str, Path, dict],
    ) -> ValidationResult:
        schema_dict = cls.load_schema(schema)
        fields = schema_dict.get("fields", [])

        if isinstance(data, (str, Path)):
            path = Path(data)
            if not path.exists():
                raise FileNotFoundError(f"Файл не найден: {path}")
            if path.suffix.lower() == ".parquet":
                df = pd.read_parquet(path)
            else:
                from .models import File
                from .converter import FileConverter
                df = FileConverter.read_to_dataframe(File(path))
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

            is_empty = series.isna()
            if series.dtype == object or pd.api.types.is_string_dtype(series):
                is_empty = is_empty | (series.astype(str).str.strip() == "")

            if fld.get("required"):
                for idx in series.index[is_empty]:
                    invalid_indices.add(idx)
                    row_num = idx + 1
                    msg = f'поле "{name}" обязательно для заполнения'
                    errors.append(f"Строка {row_num}: {msg}")
                    errors_table.append({
                        "row": row_num,
                        "field": name,
                        "value": series.loc[idx],
                        "rule": "required",
                        "message": msg,
                    })

            valid_series = series[~is_empty]
            if valid_series.empty:
                continue

            if fld.get("unique"):
                dups = valid_series[valid_series.duplicated(keep="first")]
                for idx, val in dups.items():
                    invalid_indices.add(idx)
                    row_num = idx + 1
                    msg = f'поле "{name}" должно быть уникальным (дубликат: {val})'
                    errors.append(f"Строка {row_num}: {msg}")
                    errors_table.append({
                        "row": row_num,
                        "field": name,
                        "value": val,
                        "rule": "unique",
                        "message": msg,
                    })

            expected_type = fld.get("type")
            if expected_type == "integer":
                for idx, val in valid_series.items():
                    is_err = False
                    if isinstance(val, bool):
                        is_err = True
                    else:
                        try:
                            f_val = float(val)
                            if not f_val.is_integer():
                                is_err = True
                        except (ValueError, TypeError):
                            is_err = True
                    if is_err:
                        invalid_indices.add(idx)
                        row_num = idx + 1
                        msg = f'поле "{name}" не соответствует типу integer'
                        errors.append(f"Строка {row_num}: {msg}")
                        errors_table.append({
                            "row": row_num,
                            "field": name,
                            "value": val,
                            "rule": "type",
                            "message": msg,
                        })

            elif expected_type == "float":
                for idx, val in valid_series.items():
                    is_err = False
                    if isinstance(val, bool):
                        is_err = True
                    else:
                        try:
                            float(str(val).replace(",", "."))
                        except (ValueError, TypeError):
                            is_err = True
                    if is_err:
                        invalid_indices.add(idx)
                        row_num = idx + 1
                        msg = f'поле "{name}" не соответствует типу float'
                        errors.append(f"Строка {row_num}: {msg}")
                        errors_table.append({
                            "row": row_num,
                            "field": name,
                            "value": val,
                            "rule": "type",
                            "message": msg,
                        })

            elif expected_type == "boolean":
                allowed = {True, False, 1, 0, "true", "false", "1", "0", "yes", "no", "да", "нет"}
                for idx, val in valid_series.items():
                    norm = str(val).strip().lower() if isinstance(val, str) else val
                    if norm not in allowed:
                        invalid_indices.add(idx)
                        row_num = idx + 1
                        msg = f'поле "{name}" не соответствует типу boolean'
                        errors.append(f"Строка {row_num}: {msg}")
                        errors_table.append({
                            "row": row_num,
                            "field": name,
                            "value": val,
                            "rule": "type",
                            "message": msg,
                        })

            elif expected_type == "date":
                fmt = fld.get("format", "YYYY-MM-DD")
                py_fmt = fmt.replace("YYYY", "%Y").replace("MM", "%m").replace("DD", "%d")
                for idx, val in valid_series.items():
                    try:
                        pd.to_datetime(str(val), format=py_fmt)
                    except Exception:
                        invalid_indices.add(idx)
                        row_num = idx + 1
                        msg = f'поле "{name}" не соответствует формату даты ({fmt})'
                        errors.append(f"Строка {row_num}: {msg}")
                        errors_table.append({
                            "row": row_num,
                            "field": name,
                            "value": val,
                            "rule": "type",
                            "message": msg,
                        })

            min_val = fld.get("min")
            max_val = fld.get("max")
            if min_val is not None or max_val is not None:
                for idx, val in valid_series.items():
                    try:
                        if expected_type == "date":
                            fmt = fld.get("format", "YYYY-MM-DD")
                            py_fmt = fmt.replace("YYYY", "%Y").replace("MM", "%m").replace("DD", "%d")
                            dt_val = pd.to_datetime(str(val), format=py_fmt)
                            if min_val is not None and dt_val < pd.to_datetime(str(min_val), format=py_fmt):
                                invalid_indices.add(idx)
                                row_num = idx + 1
                                msg = f'поле "{name}" раньше минимальной даты ({min_val})'
                                errors.append(f"Строка {row_num}: {msg}")
                                errors_table.append({
                                    "row": row_num,
                                    "field": name,
                                    "value": val,
                                    "rule": "min",
                                    "message": msg,
                                })
                            if max_val is not None and dt_val > pd.to_datetime(str(max_val), format=py_fmt):
                                invalid_indices.add(idx)
                                row_num = idx + 1
                                msg = f'поле "{name}" позже максимальной даты ({max_val})'
                                errors.append(f"Строка {row_num}: {msg}")
                                errors_table.append({
                                    "row": row_num,
                                    "field": name,
                                    "value": val,
                                    "rule": "max",
                                    "message": msg,
                                })
                        else:
                            num = float(val)
                            if min_val is not None and num < min_val:
                                invalid_indices.add(idx)
                                row_num = idx + 1
                                msg = f'поле "{name}" вне диапазона ({val})'
                                errors.append(f"Строка {row_num}: {msg}")
                                errors_table.append({
                                    "row": row_num,
                                    "field": name,
                                    "value": val,
                                    "rule": "range",
                                    "message": msg,
                                })
                            if max_val is not None and num > max_val:
                                invalid_indices.add(idx)
                                row_num = idx + 1
                                msg = f'поле "{name}" вне диапазона ({val})'
                                errors.append(f"Строка {row_num}: {msg}")
                                errors_table.append({
                                    "row": row_num,
                                    "field": name,
                                    "value": val,
                                    "rule": "range",
                                    "message": msg,
                                })
                    except (ValueError, TypeError):
                        pass

            min_len = fld.get("min_length")
            max_len = fld.get("max_length")
            if min_len is not None or max_len is not None:
                for idx, val in valid_series.items():
                    s_len = len(str(val))
                    if min_len is not None and s_len < min_len:
                        invalid_indices.add(idx)
                        row_num = idx + 1
                        msg = f'поле "{name}" короче минимальной длины ({min_len})'
                        errors.append(f"Строка {row_num}: {msg}")
                        errors_table.append({
                            "row": row_num,
                            "field": name,
                            "value": val,
                            "rule": "min_length",
                            "message": msg,
                        })
                    if max_len is not None and s_len > max_len:
                        invalid_indices.add(idx)
                        row_num = idx + 1
                        msg = f'поле "{name}" длиннее максимальной длины ({max_len})'
                        errors.append(f"Строка {row_num}: {msg}")
                        errors_table.append({
                            "row": row_num,
                            "field": name,
                            "value": val,
                            "rule": "max_length",
                            "message": msg,
                        })

            pattern = fld.get("pattern")
            if pattern:
                regex = re.compile(pattern)
                for idx, val in valid_series.items():
                    if not regex.search(str(val)):
                        invalid_indices.add(idx)
                        row_num = idx + 1
                        msg = f'поле "{name}" не соответствует формату'
                        errors.append(f"Строка {row_num}: {msg}")
                        errors_table.append({
                            "row": row_num,
                            "field": name,
                            "value": val,
                            "rule": "pattern",
                            "message": msg,
                        })

        valid_count = total_records - len(invalid_indices)
        return ValidationResult(
            total_records=total_records,
            valid_count=valid_count,
            invalid_indices=invalid_indices,
            errors=errors,
            errors_table=errors_table,
        )
