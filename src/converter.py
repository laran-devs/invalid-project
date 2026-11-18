import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd
from .models import File
from .validator import ParquetValidator, ValidationResult


class FileConverter:

    SUPPORTED_OUTPUT_FORMATS = {"csv", "json", "xml", "xlsx"}

    @staticmethod
    def load_config(config: Optional[Union[str, Path, dict]] = None) -> dict:
        defaults = {
            "save_intermediate_parquet": True,
            "intermediate_dir": "data/processed",
            "output_dir": "data/output",
            "schema_path": "schema.json",
        }
        if config is None:
            p = Path("config.json")
            if p.exists():
                defaults.update(json.loads(p.read_text(encoding="utf-8")))
            return defaults

        if isinstance(config, (str, Path)):
            path = Path(config)
            if path.exists():
                defaults.update(json.loads(path.read_text(encoding="utf-8")))
            return defaults

        if isinstance(config, dict):
            defaults.update(config)
            return defaults

        raise TypeError("Конфигурация должна быть путем к JSON-файлу или словарем")

    @staticmethod
    def _apply_single_transform(series: pd.Series, transform_def: Union[str, dict]) -> pd.Series:
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

    @classmethod
    def apply_transformations(
        cls,
        df: pd.DataFrame,
        schema: Union[str, Path, dict],
    ) -> pd.DataFrame:
        schema_dict = ParquetValidator.load_schema(schema)
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
                res_df[col] = cls._apply_single_transform(res_df[col], tr)

        return res_df

    @staticmethod
    def get_column_mappings(schema: Union[str, Path, dict]) -> Dict[str, str]:
        schema_dict = ParquetValidator.load_schema(schema)
        fields = schema_dict.get("fields", [])
        return {
            fld["name"]: fld["target_name"]
            for fld in fields
            if "name" in fld and fld.get("target_name")
        }

    @classmethod
    def apply_column_mappings(
        cls,
        df: pd.DataFrame,
        schema: Union[str, Path, dict],
    ) -> pd.DataFrame:
        mappings = cls.get_column_mappings(schema)
        if mappings:
            return df.rename(columns=mappings)
        return df

    @staticmethod
    def read_to_dataframe(file: File) -> pd.DataFrame:
        match file.format:
            case "csv":
                return pd.read_csv(
                    file.path,
                    sep=None,
                    engine="python",
                    encoding="utf-8-sig",
                )

            case "json":
                return pd.read_json(file.path)

            case "xml":
                return pd.read_xml(file.path)

            case "xlsx":
                return pd.read_excel(file.path, sheet_name=0, engine="openpyxl")

            case "xls":
                try:
                    return pd.read_excel(file.path, sheet_name=0, engine="xlrd")
                except ImportError:
                    return pd.read_excel(file.path, sheet_name=0)

            case _:
                raise ValueError(
                    f"Неподдерживаемый формат для чтения: '{file.format}'. "
                    f"Допустимые: {', '.join(sorted(File.SUPPORTED_FORMATS))}"
                )

    @classmethod
    def write_dataframe(
        cls,
        df: pd.DataFrame,
        target_path: Union[str, Path],
        target_format: Optional[str] = None,
    ) -> Path:
        target = Path(target_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        fmt = (target_format or target.suffix.lstrip(".")).lower()

        match fmt:
            case "csv":
                df.to_csv(target, index=False, encoding="utf-8-sig")

            case "json":
                df.to_json(
                    target,
                    orient="records",
                    force_ascii=False,
                    indent=2,
                    date_format="iso",
                )

            case "xml":
                df.to_xml(
                    target,
                    index=False,
                    root_name="data",
                    row_name="row",
                    encoding="utf-8",
                )

            case "xlsx":
                df.to_excel(target, index=False, engine="openpyxl")

            case "parquet":
                df.to_parquet(
                    target,
                    engine="pyarrow",
                    compression="snappy",
                    index=False,
                )

            case "xls":
                raise ValueError(
                    "Запись в устаревший формат '.xls' не поддерживается. "
                    "Для Excel используйте формат '.xlsx'."
                )

            case _:
                raise ValueError(
                    f"Неподдерживаемый формат для записи: '{fmt}'. "
                    f"Допустимые форматы: {', '.join(sorted(cls.SUPPORTED_OUTPUT_FORMATS))}"
                )

        return target

    @classmethod
    def convert_pipeline(
        cls,
        file: File,
        target_format: str,
        schema_path: Optional[Union[str, Path]] = None,
        output_path: Optional[Union[str, Path]] = None,
        errors_path: Optional[Union[str, Path]] = None,
        config: Optional[Union[str, Path, dict]] = None,
    ) -> Tuple[Path, Optional[Path], ValidationResult]:
        cfg = cls.load_config(config)
        target_fmt = target_format.lstrip(".").lower()

        if target_fmt not in cls.SUPPORTED_OUTPUT_FORMATS:
            raise ValueError(
                f"Неподдерживаемый целевой формат: '{target_fmt}'. "
                f"Допустимые: {', '.join(sorted(cls.SUPPORTED_OUTPUT_FORMATS))}"
            )

        df = cls.read_to_dataframe(file)

        schema_to_use = schema_path or cfg.get("schema_path")
        val_result = None

        if schema_to_use and Path(schema_to_use).exists():
            val_result = ParquetValidator.validate(df, schema_to_use)

        if val_result is not None and len(val_result.invalid_indices) > 0:
            invalid_indices_list = sorted(list(val_result.invalid_indices))
            invalid_df = df.iloc[invalid_indices_list].copy()
            valid_df = df.drop(index=invalid_indices_list).copy()
        else:
            invalid_df = pd.DataFrame()
            valid_df = df.copy()

        if val_result is None:
            val_result = ValidationResult(
                total_records=len(df),
                valid_count=len(df),
                invalid_indices=set(),
                errors=[],
                errors_table=[],
            )

        if schema_to_use and Path(schema_to_use).exists():
            valid_df = cls.apply_transformations(valid_df, schema_to_use)

        if cfg.get("save_intermediate_parquet", True):
            inter_dir = Path(cfg.get("intermediate_dir", "data/processed")).resolve()
            inter_file = inter_dir / f"{file.path.stem}.parquet"
            cls.write_dataframe(valid_df, inter_file, "parquet")

        if schema_to_use and Path(schema_to_use).exists():
            valid_df = cls.apply_column_mappings(valid_df, schema_to_use)

        if output_path:
            out_file = Path(output_path).resolve()
        else:
            out_dir = Path(cfg.get("output_dir", "data/output")).resolve()
            out_file = out_dir / f"{file.path.stem}.{target_fmt}"

        cls.write_dataframe(valid_df, out_file, target_fmt)

        err_file = None
        if not invalid_df.empty:
            if errors_path:
                err_file = Path(errors_path).resolve()
            else:
                err_dir = out_file.parent
                err_file = err_dir / "errors.csv"
            cls.write_dataframe(invalid_df, err_file, "csv")

        return out_file, err_file, val_result

    @classmethod
    def convert(
        cls,
        file: File,
        target_format: str,
        output_dir: Optional[Union[str, Path]] = None,
        output_name: Optional[str] = None,
        config: Optional[Union[str, Path, dict]] = None,
        schema: Optional[Union[str, Path, dict]] = None,
        save_intermediate_parquet: Optional[bool] = None,
        apply_transforms: bool = True,
        apply_mapping: bool = True,
    ) -> Path:
        out_p = None
        if output_dir and output_name:
            out_p = Path(output_dir) / output_name
        elif output_dir:
            out_p = Path(output_dir) / f"{file.path.stem}.{target_format.lstrip('.')}"

        saved_path, _, _ = cls.convert_pipeline(
            file=file,
            target_format=target_format,
            schema_path=schema,
            output_path=out_p,
            config=config,
        )
        return saved_path
