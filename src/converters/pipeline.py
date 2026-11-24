import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd
from ..readers import ReaderFactory
from ..validators import ValidationEngine, ValidationResult
from .transformers import apply_transformations, apply_column_mappings, get_column_mappings
from .writers import DataWriter

try:
    import yaml
except ImportError:
    yaml = None


class ConversionPipeline:
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
                try:
                    defaults.update(json.loads(p.read_text(encoding="utf-8")))
                except Exception:
                    pass
            return defaults

        if isinstance(config, (str, Path)):
            path = Path(config)
            if path.exists():
                content = path.read_text(encoding="utf-8")
                if path.suffix.lower() in (".yaml", ".yml") and yaml is not None:
                    loaded = yaml.safe_load(content)
                else:
                    loaded = json.loads(content)
                if isinstance(loaded, dict):
                    defaults.update(loaded)
            return defaults

        if isinstance(config, dict):
            defaults.update(config)
            return defaults

        raise TypeError("Конфигурация должна быть путем к файлу или словарем")

    @classmethod
    def read_to_dataframe(cls, file: Any) -> pd.DataFrame:
        path = file.path if hasattr(file, "path") else Path(file)
        return ReaderFactory.read(path)

    @classmethod
    def write_dataframe(
        cls,
        df: pd.DataFrame,
        target_path: Union[str, Path],
        target_format: Optional[str] = None,
    ) -> Path:
        return DataWriter.write(df, target_path, target_format)

    @classmethod
    def apply_transformations(
        cls,
        df: pd.DataFrame,
        schema: Union[str, Path, dict],
    ) -> pd.DataFrame:
        return apply_transformations(df, schema)

    @classmethod
    def apply_column_mappings(
        cls,
        df: pd.DataFrame,
        schema: Union[str, Path, dict],
    ) -> pd.DataFrame:
        return apply_column_mappings(df, schema)

    @classmethod
    def get_column_mappings(cls, schema: Union[str, Path, dict]) -> Dict[str, str]:
        return get_column_mappings(schema)

    @classmethod
    def convert_pipeline(
        cls,
        file: Any,
        target_format: str,
        schema_path: Optional[Union[str, Path]] = None,
        output_path: Optional[Union[str, Path]] = None,
        errors_path: Optional[Union[str, Path]] = None,
        report_path: Optional[Union[str, Path]] = None,
        config: Optional[Union[str, Path, dict]] = None,
    ) -> Tuple[Path, Optional[Path], ValidationResult]:
        cfg = cls.load_config(config)
        target_fmt = target_format.lstrip(".").lower()

        if target_fmt not in cls.SUPPORTED_OUTPUT_FORMATS:
            raise ValueError(
                f"Неподдерживаемый целевой формат: '{target_fmt}'. "
                f"Допустимые: {', '.join(sorted(cls.SUPPORTED_OUTPUT_FORMATS))}"
            )

        in_path = file.path if hasattr(file, "path") else Path(file)
        df = cls.read_to_dataframe(in_path)

        schema_to_use = schema_path or cfg.get("schema_path")
        val_result = None

        if schema_to_use and Path(schema_to_use).exists():
            val_result = ValidationEngine.validate(df, schema_to_use)

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
            inter_file = inter_dir / f"{in_path.stem}.parquet"
            cls.write_dataframe(valid_df, inter_file, "parquet")
            valid_df = pd.read_parquet(inter_file)

        if schema_to_use and Path(schema_to_use).exists():
            valid_df = cls.apply_column_mappings(valid_df, schema_to_use)

        if output_path:
            out_file = Path(output_path).resolve()
        else:
            out_dir = Path(cfg.get("output_dir", "data/output")).resolve()
            out_file = out_dir / f"{in_path.stem}.{target_fmt}"

        cls.write_dataframe(valid_df, out_file, target_fmt)

        err_file = None
        if not invalid_df.empty:
            if errors_path:
                err_file = Path(errors_path).resolve()
            else:
                err_dir = out_file.parent
                err_file = err_dir / "errors.csv"
            cls.write_dataframe(invalid_df, err_file, "csv")

        if report_path:
            val_result.generate_html_report(report_path)

        return out_file, err_file, val_result

    @classmethod
    def convert(
        cls,
        file: Any,
        target_format: str,
        output_dir: Optional[Union[str, Path]] = None,
        output_name: Optional[str] = None,
        config: Optional[Union[str, Path, dict]] = None,
        schema: Optional[Union[str, Path, dict]] = None,
        save_intermediate_parquet: Optional[bool] = None,
        apply_transforms: bool = True,
        apply_mapping: bool = True,
    ) -> Path:
        in_path = file.path if hasattr(file, "path") else Path(file)
        out_p = None
        if output_dir and output_name:
            out_p = Path(output_dir) / output_name
        elif output_dir:
            out_p = Path(output_dir) / f"{in_path.stem}.{target_format.lstrip('.')}"

        saved_path, _, _ = cls.convert_pipeline(
            file=file,
            target_format=target_format,
            schema_path=schema,
            output_path=out_p,
            config=config,
        )
        return saved_path

    @classmethod
    def convert_to_parquet(
        cls,
        file: Any,
        output_dir: Optional[Union[str, Path]] = None,
        output_name: Optional[str] = None,
    ) -> Path:
        in_path = file.path if hasattr(file, "path") else Path(file)
        target_dir = Path(output_dir or "data/processed").resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = output_name or f"{in_path.stem}.parquet"
        target_path = target_dir / filename
        df = cls.read_to_dataframe(file)
        return cls.write_dataframe(df, target_path, "parquet")


FileConverter = ConversionPipeline
