from pathlib import Path
from typing import Any, Dict, List, Union
import pandas as pd
from ..validators.schema import load_schema


def apply_single_transform(series: pd.Series, transform_def: Union[str, dict]) -> pd.Series:
    if isinstance(transform_def, str):
        norm_name = transform_def.strip().lower()

        if norm_name in ("trim", "strip"):
            return series.map(lambda x: x.strip() if isinstance(x, str) else x)

        if norm_name in ("lowercase", "lower"):
            return series.map(lambda x: x.lower() if isinstance(x, str) else x)

        if norm_name in ("uppercase", "upper"):
            return series.map(lambda x: x.upper() if isinstance(x, str) else x)

        if norm_name in ("timestamp_to_date", "to_date"):
            def _to_date(val):
                if pd.isna(val) or val is None or val == "":
                    return val
                try:
                    num = float(val)
                    unit = "ms" if num > 1e11 else "s"
                    return pd.to_datetime(num, unit=unit).strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    try:
                        return pd.to_datetime(val).strftime("%Y-%m-%d")
                    except Exception:
                        return val

            return series.map(_to_date)

    elif isinstance(transform_def, dict):
        if "replace" in transform_def or "dictionary" in transform_def:
            rep_dict = transform_def.get("replace") or transform_def.get("dictionary")
            if isinstance(rep_dict, dict):
                return series.map(lambda x: rep_dict.get(x, x))

    return series


def apply_transformations(
    df: pd.DataFrame,
    schema: Union[str, Path, dict],
) -> pd.DataFrame:
    schema_dict = load_schema(schema)
    fields = schema_dict.get("fields", [])
    res_df = df.copy()

    for fld in fields:
        name = fld.get("name")
        target_name = fld.get("target_name")
        col = name if name in res_df.columns else (target_name if target_name in res_df.columns else None)
        if not col:
            continue

        transforms = fld.get("transform") or fld.get("transforms") or fld.get("transformations")
        if not transforms:
            continue

        if isinstance(transforms, (str, dict)):
            transforms = [transforms]

        for tr in transforms:
            res_df[col] = apply_single_transform(res_df[col], tr)

    return res_df


def get_column_mappings(schema: Union[str, Path, dict]) -> Dict[str, str]:
    schema_dict = load_schema(schema)
    fields = schema_dict.get("fields", [])
    return {
        fld["name"]: fld["target_name"]
        for fld in fields
        if "name" in fld and fld.get("target_name")
    }


def apply_column_mappings(
    df: pd.DataFrame,
    schema: Union[str, Path, dict],
) -> pd.DataFrame:
    mappings = get_column_mappings(schema)
    if mappings:
        return df.rename(columns=mappings)
    return df
