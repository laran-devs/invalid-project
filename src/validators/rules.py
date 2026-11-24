import re
from typing import Any, Dict, List, Optional, Set, Tuple
import pandas as pd


def check_required(
    series: pd.Series,
    field_name: str,
) -> Tuple[Set[int], List[str], List[Dict[str, Any]]]:
    invalid_indices = set()
    errors = []
    errors_table = []

    is_empty = series.isna()
    if series.dtype == object or pd.api.types.is_string_dtype(series):
        is_empty = is_empty | (series.astype(str).str.strip() == "")

    for idx in series.index[is_empty]:
        invalid_indices.add(idx)
        row_num = idx + 1
        msg = f'поле "{field_name}" обязательно для заполнения'
        errors.append(f"Строка {row_num}: {msg}")
        errors_table.append({
            "row": row_num,
            "field": field_name,
            "value": series.loc[idx],
            "rule": "required",
            "message": msg,
        })

    return invalid_indices, errors, errors_table


def check_unique(
    series: pd.Series,
    field_name: str,
) -> Tuple[Set[int], List[str], List[Dict[str, Any]]]:
    invalid_indices = set()
    errors = []
    errors_table = []

    dups = series[series.duplicated(keep="first")]
    for idx, val in dups.items():
        invalid_indices.add(idx)
        row_num = idx + 1
        msg = f'поле "{field_name}" должно быть уникальным (дубликат: {val})'
        errors.append(f"Строка {row_num}: {msg}")
        errors_table.append({
            "row": row_num,
            "field": field_name,
            "value": val,
            "rule": "unique",
            "message": msg,
        })

    return invalid_indices, errors, errors_table


def check_type(
    series: pd.Series,
    field_name: str,
    expected_type: str,
    date_format: str = "YYYY-MM-DD",
) -> Tuple[Set[int], List[str], List[Dict[str, Any]]]:
    invalid_indices = set()
    errors = []
    errors_table = []

    if expected_type == "integer":
        for idx, val in series.items():
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
                msg = f'поле "{field_name}" не соответствует типу integer'
                errors.append(f"Строка {row_num}: {msg}")
                errors_table.append({
                    "row": row_num,
                    "field": field_name,
                    "value": val,
                    "rule": "type",
                    "message": msg,
                })

    elif expected_type == "float":
        for idx, val in series.items():
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
                msg = f'поле "{field_name}" не соответствует типу float'
                errors.append(f"Строка {row_num}: {msg}")
                errors_table.append({
                    "row": row_num,
                    "field": field_name,
                    "value": val,
                    "rule": "type",
                    "message": msg,
                })

    elif expected_type == "boolean":
        allowed = {True, False, 1, 0, "true", "false", "1", "0", "yes", "no", "да", "нет"}
        for idx, val in series.items():
            norm = str(val).strip().lower() if isinstance(val, str) else val
            if norm not in allowed:
                invalid_indices.add(idx)
                row_num = idx + 1
                msg = f'поле "{field_name}" не соответствует типу boolean'
                errors.append(f"Строка {row_num}: {msg}")
                errors_table.append({
                    "row": row_num,
                    "field": field_name,
                    "value": val,
                    "rule": "type",
                    "message": msg,
                })

    elif expected_type == "date":
        py_fmt = date_format.replace("YYYY", "%Y").replace("MM", "%m").replace("DD", "%d")
        for idx, val in series.items():
            try:
                pd.to_datetime(str(val), format=py_fmt)
            except Exception:
                invalid_indices.add(idx)
                row_num = idx + 1
                msg = f'поле "{field_name}" не соответствует формату даты ({date_format})'
                errors.append(f"Строка {row_num}: {msg}")
                errors_table.append({
                    "row": row_num,
                    "field": field_name,
                    "value": val,
                    "rule": "type",
                    "message": msg,
                })

    return invalid_indices, errors, errors_table


def check_range(
    series: pd.Series,
    field_name: str,
    min_val: Optional[Any],
    max_val: Optional[Any],
    is_date: bool = False,
    date_format: str = "YYYY-MM-DD",
) -> Tuple[Set[int], List[str], List[Dict[str, Any]]]:
    invalid_indices = set()
    errors = []
    errors_table = []

    if min_val is None and max_val is None:
        return invalid_indices, errors, errors_table

    py_fmt = date_format.replace("YYYY", "%Y").replace("MM", "%m").replace("DD", "%d")

    for idx, val in series.items():
        try:
            if is_date:
                dt_val = pd.to_datetime(str(val), format=py_fmt)
                if min_val is not None and dt_val < pd.to_datetime(str(min_val), format=py_fmt):
                    invalid_indices.add(idx)
                    row_num = idx + 1
                    msg = f'поле "{field_name}" раньше минимальной даты ({min_val})'
                    errors.append(f"Строка {row_num}: {msg}")
                    errors_table.append({
                        "row": row_num,
                        "field": field_name,
                        "value": val,
                        "rule": "min",
                        "message": msg,
                    })
                if max_val is not None and dt_val > pd.to_datetime(str(max_val), format=py_fmt):
                    invalid_indices.add(idx)
                    row_num = idx + 1
                    msg = f'поле "{field_name}" позже максимальной даты ({max_val})'
                    errors.append(f"Строка {row_num}: {msg}")
                    errors_table.append({
                        "row": row_num,
                        "field": field_name,
                        "value": val,
                        "rule": "max",
                        "message": msg,
                    })
            else:
                num = float(val)
                if min_val is not None and num < min_val:
                    invalid_indices.add(idx)
                    row_num = idx + 1
                    msg = f'поле "{field_name}" вне диапазона ({val})'
                    errors.append(f"Строка {row_num}: {msg}")
                    errors_table.append({
                        "row": row_num,
                        "field": field_name,
                        "value": val,
                        "rule": "range",
                        "message": msg,
                    })
                if max_val is not None and num > max_val:
                    invalid_indices.add(idx)
                    row_num = idx + 1
                    msg = f'поле "{field_name}" вне диапазона ({val})'
                    errors.append(f"Строка {row_num}: {msg}")
                    errors_table.append({
                        "row": row_num,
                        "field": field_name,
                        "value": val,
                        "rule": "range",
                        "message": msg,
                    })
        except (ValueError, TypeError):
            pass

    return invalid_indices, errors, errors_table


def check_length(
    series: pd.Series,
    field_name: str,
    min_length: Optional[int],
    max_length: Optional[int],
) -> Tuple[Set[int], List[str], List[Dict[str, Any]]]:
    invalid_indices = set()
    errors = []
    errors_table = []

    if min_length is None and max_length is None:
        return invalid_indices, errors, errors_table

    for idx, val in series.items():
        s_len = len(str(val))
        if min_length is not None and s_len < min_length:
            invalid_indices.add(idx)
            row_num = idx + 1
            msg = f'поле "{field_name}" короче минимальной длины ({min_length})'
            errors.append(f"Строка {row_num}: {msg}")
            errors_table.append({
                "row": row_num,
                "field": field_name,
                "value": val,
                "rule": "min_length",
                "message": msg,
            })
        if max_length is not None and s_len > max_length:
            invalid_indices.add(idx)
            row_num = idx + 1
            msg = f'поле "{field_name}" длиннее максимальной длины ({max_length})'
            errors.append(f"Строка {row_num}: {msg}")
            errors_table.append({
                "row": row_num,
                "field": field_name,
                "value": val,
                "rule": "max_length",
                "message": msg,
            })

    return invalid_indices, errors, errors_table


def check_pattern(
    series: pd.Series,
    field_name: str,
    pattern: str,
) -> Tuple[Set[int], List[str], List[Dict[str, Any]]]:
    invalid_indices = set()
    errors = []
    errors_table = []

    regex = re.compile(pattern)
    for idx, val in series.items():
        if not regex.search(str(val)):
            invalid_indices.add(idx)
            row_num = idx + 1
            msg = f'поле "{field_name}" не соответствует формату'
            errors.append(f"Строка {row_num}: {msg}")
            errors_table.append({
                "row": row_num,
                "field": field_name,
                "value": val,
                "rule": "pattern",
                "message": msg,
            })

    return invalid_indices, errors, errors_table
